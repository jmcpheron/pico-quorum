// The light boot mark (firmware/bootmark.py) on each panel: every frame it sends only the rectangles
// that changed, so after any run of frames the panel must equal the whole scene painted afresh.
// Checked at every frame on 240x240 (Waveshare, strip-buffered), 320x240 (build1 2.8") and 160x128
// (build1 1.8", one frame buffer), with the tagline under the name where there is room. Prints the SPI bytes per frame against a whole-panel frame, and
// writes the Waveshare frames to emu/shots/bootmark/ (NNNN.png, 30 ms apart) plus a still per panel.
//   node test-vectors/run-bootmark.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { loadMicroPython } from '../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs';
import { createDevice, frameToRGBA } from '../emu/core/runtime.mjs';
import { encodePNG } from '../emu/core/png.mjs';
import { readWorkspace, readShims } from '../emu/core/workspace.mjs';

const OUT = 'emu/shots/bootmark';
mkdirSync(OUT, { recursive: true });
const STEP = 30;          // ms between frames: the pace draw() sees during the WiFi join and the hold
const END = 4500;
// Real boot status lines, changing at roughly the points the console's start() reaches them.
const STATUS = [[0, 'screen: ok'], [400, 'chip: probing i2c...'], [700, 'chip: ATECC608 · 3f9a…c21 · pinned'],
  [900, 'wifi: join emulator A skips'], [2600, 'wifi: 192.168.1.40'], [3000, 'app: safe svc api.safe.global'],
  [3400, 'app: Starting console']];

const PANELS = [
  { name: 'waveshare', secrets: '', w: 240, h: 240, real: true },
  { name: 'build1-2.8', secrets: 'BOARD="build1"\nSCREEN="2.8"', w: 320, h: 240 },
  { name: 'build1-1.8', secrets: 'BOARD="build1"\nSCREEN="1.8"', w: 160, h: 128 },
];

let failed = false;
for (const p of PANELS) {
  const dev = await createDevice({ loadMicroPython, keys: new Int32Array(16), files: readWorkspace(),
    shims: readShims(), heapsize: 2 * 1024 * 1024, secrets: p.secrets, onStdout: console.log });
  try {
    // A panel in Python: _window and spi.write land in `panel`, as the ST7789's RAM would. On the
    // Waveshare the real LCD is used as well, so the emulator's own SPI capture is checked too.
    dev.mp.runPython(`
import bootmark, lcd as L, board, binascii
TAG = 'See what you sign'
PW, PH = board.PANEL_W, board.PANEL_H
class Pin:
    def __call__(self, v): pass
class Panel:
    def __init__(self):
        self.ram = bytearray(PW * PH * 2)
        self.dc, self.cs, self.spi = Pin(), Pin(), self
    def _window(self, x, y, w, h):
        self.win = (x, y, w, h)
    def write(self, b):
        x, y, w, h = self.win
        assert len(b) == 2 * w * h, 'window and data disagree'
        for r in range(h):
            o = ((y + r) * PW + x) * 2
            self.ram[o:o + 2 * w] = b[2 * r * w:2 * (r + 1) * w]
STATUS = ${JSON.stringify(STATUS)}
def status_at(t):
    s = STATUS[0][1]
    for at, text in STATUS:
        if t >= at:
            s = text
    return s
def fresh(t, status):
    ref = Panel()
    m = bootmark.Mark(ref, TAG)
    m.frame(t, status)
    return ref.ram, m.sent
panel = Panel()
mark = bootmark.Mark(panel, TAG)
real = bootmark.Mark(L.LCD(), TAG) if ${p.real ? 'True' : 'False'} else None
sent = []
`);
    let frames = 0;
    for (let t = 0; t <= END; t += STEP, frames++) {
      dev.mp.runPython(`
_t = ${t}
_s = status_at(_t)
_before = mark.sent
mark.frame(_t, _s)
sent.append(mark.sent - _before)
_ref, _full = fresh(_t, _s)
assert panel.ram == _ref, 'frame at %d ms differs from a fresh paint' % _t
if real:
    real.frame(_t, _s)
    _hex = binascii.hexlify(panel.ram).decode()
`);
      if (p.real) {
        const bytes = Buffer.from(dev.mp.globals.get('_hex'), 'hex');
        const screen = dev.frame;
        if (!bytes.equals(Buffer.from(screen))) throw new Error(`emulator panel differs at ${t} ms`);
        writeFileSync(`${OUT}/${String(frames).padStart(4, '0')}.png`, encodePNG(240, 240, frameToRGBA(bytes)));
      }
    }
    // "still": everything at its end in one paint, then only the status line.
    dev.mp.runPython(`
still = Panel()
m = bootmark.Mark(still, TAG)
m.frame(bootmark.STILL, 'app: Starting console')
_one = m.sent
m.frame(bootmark.STILL, 'app: Starting console')
assert m.sent == _one, 'a still frame with nothing new sent something'
m.frame(bootmark.STILL, 'wifi: 192.168.1.40')
_status = m.sent - _one
_hex = binascii.hexlify(still.ram).decode()
import json
_stats = json.dumps([sum(sent), max(sent[1:]), len([s for s in sent if s == 0]), len(sent), _full, _status])
`);
    const bytes = Buffer.from(dev.mp.globals.get('_hex'), 'hex');
    writeFileSync(`${OUT}/still-${p.name}.png`, encodePNG(p.w, p.h, frameToRGBA(bytes)));
    const [total, peak, idle, n, full, status] = JSON.parse(dev.mp.globals.get('_stats'));
    const pct = (100 * total / (n * full)).toFixed(1);
    console.log(`bootmark ${p.name} ${p.w}x${p.h}: ${n} frames match a fresh paint; SPI ${total} B in all, ` +
      `${pct}% of whole-panel frames (${full} B each); busiest frame after the first ${peak} B; ` +
      `${idle} frames sent nothing; still: a status change sends ${status} B`);
  } catch (e) { console.error(`bootmark ${p.name}: ${String(e)}`); failed = true; } finally { dev.dispose(); }
}

// splash with the default art: the mark, a 0.3 s lead-in, the hold, and both art modules released.
{
  const dev = await createDevice({ loadMicroPython, keys: new Int32Array(16), files: readWorkspace(),
    shims: readShims(), heapsize: 2 * 1024 * 1024, secrets: '', onStdout: console.log });
  try {
    dev.mp.runPython(`
import splash, sys
splash.begin()
assert splash._art.__name__ == 'bootmark' and not splash._still
assert splash.BLACK_LEAD_MS + splash.ANIMATION_MS == 4000
assert splash._gap == 30
import bootmark as B
assert int(B.yaw_at(B.BACK1) + 0.5) % 90 == 45 and B.eth_look(B.BACK1 + 9000)[1] == 45 and B.yaw_at(B.BACK1 + 9000) == B.yaw_at(B.BACK1), 'the diamond lands on the logo pose'
# the console's boot: the art on a soft timer (splash.run) while the console starts
splash.run()
assert splash._timer is not None
n = splash._frame
splash.pause(); splash._tick(None)
assert splash._frame == n, 'a paused timer draws nothing'
splash.pause(False); splash._tick(None)
assert splash._frame == n + 1, 'a tick draws a frame'
splash.step('app', 'Starting console')
assert splash._frame == n + 1 and splash._status == 'app: Starting console', 'with the timer, step() leaves the frame to it'
splash.finish(wait=False)
assert splash._timer is None, 'finish() stops the timer'
assert splash._art is None and 'bootmark' not in sys.modules and 'bootart' not in sys.modules
assert 'taglines' not in sys.modules
import taglines, fonts as F
wide = [t for t in taglines.SERIOUS + taglines.FUN if F.width(t, 'sans14') > 220]
assert not wide, 'too wide for the 240x240: %r' % wide
assert taglines.pool() == taglines.SERIOUS and taglines.pick() in taglines.SERIOUS
assert sorted(taglines.cycle()) == sorted(taglines.SERIOUS)
`);
    console.log('bootmark: splash picks the mark by default, 4.0 s hold, released at finish; the diamond lands on the logo; the timer draws, pauses and stops; ' +
      'every tagline fits 220 px, serious by default');
  } catch (e) { console.error(`bootmark splash: ${String(e)}`); failed = true; } finally { dev.dispose(); }
}
if (failed) process.exitCode = 1;
