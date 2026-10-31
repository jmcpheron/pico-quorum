// The pixel-art boot screen (firmware/bootpixel.py) on each panel: it moves only on a step (125 ms),
// so a frame between steps must send nothing, and after any run of frames the panel must equal the
// whole scene painted afresh. Checked every 30 ms, the pace splash draws at, on 240x240 (Waveshare,
// strip-buffered), 320x240 (build1 2.4"), 160x128 (build1 1.8", one frame buffer) and 240x135 (the
// Feather). Prints the SPI bytes against whole-panel frames, and writes each step of the Waveshare
// and build1 runs to emu/shots/bootpixel/<panel>/NN.png, plus a still per panel.
//   node test-vectors/run-bootpixel.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { loadMicroPython } from '../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs';
import { createDevice, frameToRGBA } from '../emu/core/runtime.mjs';
import { encodePNG } from '../emu/core/png.mjs';
import { readWorkspace, readShims } from '../emu/core/workspace.mjs';

const OUT = 'emu/shots/bootpixel';
const STEP = 30;
const END = 5000;
const STATUS = [[0, 'screen: ok'], [400, 'chip: probing i2c...'], [700, 'chip: ATECC608 · 3f9a…c21 · pinned'],
  [900, 'wifi: join emulator A skips'], [2600, 'wifi: 192.168.1.40'], [3000, 'app: safe svc api.safe.global'],
  [3400, 'app: Starting console']];

const PANELS = [
  { name: 'waveshare', secrets: '', w: 240, h: 240, steps: true },
  { name: 'build1-2.4', secrets: 'BOARD="build1"\nSCREEN="2.4"', w: 320, h: 240, steps: true },
  { name: 'build1-1.8', secrets: 'BOARD="build1"\nSCREEN="1.8"', w: 160, h: 128 },
  { name: 'feather-s3', secrets: 'BOARD="feather-s3"', w: 240, h: 135 },
];

let failed = false;
for (const p of PANELS) {
  mkdirSync(`${OUT}/${p.name}`, { recursive: true });
  const dev = await createDevice({ loadMicroPython, keys: new Int32Array(16), files: readWorkspace(),
    shims: readShims(), heapsize: 2 * 1024 * 1024, secrets: p.secrets, onStdout: console.log });
  try {
    dev.mp.runPython(`
import bootpixel as B, lcd as L, board, binascii
assert (L.W, L.H) == (${p.w}, ${p.h}), 'the panel: %dx%d' % (L.W, L.H)
TAG = 'If the service lies, it\\'s refused'     # the longest serious line: two lines on 240
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
        assert x >= 0 and y >= 0 and x + w <= PW and y + h <= PH, 'a window off the panel: %r' % (self.win,)
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
    m = B.Pixel(ref, TAG)
    m.frame(t, status)
    return ref.ram, m.sent
OWNER = '0x47c0998c6a7a1955794071b9f4058e7814178f35'
B.set_chip(None, '')
panel = Panel()
pix = B.Pixel(panel, TAG)
sent, steps = [], []
_last_n = -1
`);
    let frames = 0;
    for (let t = 0; t <= END; t += STEP, frames++) {
      dev.mp.runPython(`
_t = ${t}
_s = status_at(_t)
if _t >= 700:
    B.set_chip(OWNER, 'chip 3 \\u00b7 0x47c0\\u20268f35')
_before = pix.sent
_key = (min(B.END, _t // B.STEP_MS), pix.status, B._chip)
_same = pix.last is not None and _key[0] == pix.last[0] and _s == pix.status[0] and B._chip == pix.last[2]
pix.frame(_t, _s)
sent.append(pix.sent - _before)
if _same:
    assert pix.sent == _before, 'a frame between steps sent %d B at %d ms' % (pix.sent - _before, _t)
_ref, _full = fresh(_t, _s)
assert panel.ram == _ref, 'frame at %d ms differs from a fresh paint' % _t
_n = min(B.END, _t // B.STEP_MS)
_new_step = _n != _last_n
_last_n = _n
_hex = binascii.hexlify(panel.ram).decode() if _new_step else ''
`);
      const hex = dev.mp.globals.get('_hex');
      if (p.steps && hex) {
        const n = String(Math.min(Math.floor(t / 125), 99)).padStart(2, '0');
        writeFileSync(`${OUT}/${p.name}/${n}.png`, encodePNG(p.w, p.h, frameToRGBA(Buffer.from(hex, 'hex'))));
      }
    }
    dev.mp.runPython(`
still = Panel()
m = B.Pixel(still, TAG)
m.frame(B.STILL, 'app: Starting console')
_one = m.sent
m.frame(B.STILL, 'app: Starting console')
assert m.sent == _one, 'a still frame with nothing new sent something'
m.frame(B.STILL, 'wifi: 192.168.1.40')
_status = m.sent - _one
assert 0 < _status < PW * 20 * 2, 'a status change repaints more than its line: %d B' % _status
_hex = binascii.hexlify(still.ram).decode()
_n_steps = len([1 for s in sent if s])
import json
_stats = json.dumps([sum(sent), max(sent[1:]), _n_steps, len(sent), _full, _status])
`);
    const bytes = Buffer.from(dev.mp.globals.get('_hex'), 'hex');
    writeFileSync(`${OUT}/still-${p.name}.png`, encodePNG(p.w, p.h, frameToRGBA(bytes)));
    const [total, peak, busy, n, full, status] = JSON.parse(dev.mp.globals.get('_stats'));
    const pct = (100 * total / (n * full)).toFixed(1);
    console.log(`bootpixel ${p.name} ${p.w}x${p.h}: ${n} frames match a fresh paint; ${busy} of them sent anything; ` +
      `SPI ${total} B in all, ${pct}% of whole-panel frames (${full} B each); busiest after the first ${peak} B; ` +
      `still: a status change sends ${status} B`);
  } catch (e) { console.error(`bootpixel ${p.name}: ${String(e)}`); failed = true; } finally { dev.dispose(); }
}

// splash with the default art: this one, its lead-in and hold, and released at finish.
{
  const dev = await createDevice({ loadMicroPython, keys: new Int32Array(16), files: readWorkspace(),
    shims: readShims(), heapsize: 2 * 1024 * 1024, secrets: '', onStdout: console.log });
  try {
    dev.mp.runPython(`
import splash, sys
splash.begin()
assert splash._art.__name__ == 'bootpixel', splash._art
import bootpixel as B
assert splash.BLACK_LEAD_MS == B.LEAD_MS and splash.ANIMATION_MS == B.DURATION_MS
assert B.YAW[-1] % 90 == 45, 'the diamond lands on the logo pose'
assert all(B.YAW[i] <= B.YAW[i + 1] for i in range(len(B.YAW) - 1))
splash.step('app', 'Starting console')
splash.chip('0x47c0998c6a7a1955794071b9f4058e7814178f35', 'chip 3')
splash.finish(wait=False)
assert splash._art is None and 'bootpixel' not in sys.modules and 'taglines' not in sys.modules
`);
    console.log('bootpixel: splash picks it by default, its lead-in and hold, released at finish; the diamond lands on the logo pose');
  } catch (e) { console.error(`bootpixel splash: ${String(e)}`); failed = true; } finally { dev.dispose(); }
}
if (failed) process.exitCode = 1;
