// Full-panel captures and pixel equality for the production orbit on the 320x240 strip driver.
import { mkdirSync, writeFileSync } from 'node:fs';
import { loadMicroPython } from '../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs';
import { createDevice, frameToRGBA } from '../emu/core/runtime.mjs';
import { encodePNG } from '../emu/core/png.mjs';
import { readWorkspace, readShims } from '../emu/core/workspace.mjs';
const dev = await createDevice({loadMicroPython, keys: new Int32Array(16), files: readWorkspace(),
  shims: readShims(), heapsize: 2*1024*1024, secrets: 'BOARD="build1"\nSCREEN="2.8"', onStdout: console.log});
try {
  dev.mp.runPython(`
import bootart, lcd, framebuf, binascii
full = bytearray(320*240*2)
class Capture(lcd.LCD):
    def show(self):
        full[self.y0*640:(self.y0+self.band_h)*640] = self.buffer
class Reference(framebuf.FrameBuffer):
    y0 = 0
    band_h = 240
    def frames(self, draw, *args): draw(*args)
    def show(self): pass
refbuf = bytearray(len(full))
ref = Reference(refbuf, 320, 240, framebuf.RGB565)
d = Capture()
`);
  mkdirSync('emu/shots/boot-native', {recursive:true});
  for (const i of [12, 64, 110, 150, 186, 214, 256, 300, 340]) {
    dev.mp.runPython(`bootart.render(d, ${i}, 'Starting console', (152,160,172))\nbootart.render(ref, ${i}, 'Starting console', (152,160,172))\nassert full == refbuf, 'strip seam'\nassert bootart.d is None\n_hex = binascii.hexlify(full).decode()`);
    const bytes = Buffer.from(dev.mp.globals.get('_hex'), 'hex');
    writeFileSync(`emu/shots/boot-native/${i}.png`, encodePNG(320,240,frameToRGBA(bytes)));
  }
  dev.mp.runPython(`
import splash, sys
splash.begin()
assert all(b == 0 for b in lcd._BUF)
class Clock:
    now = 0
    def ticks_ms(self): return self.now
    def ticks_diff(self, a, b): return a - b
class Art:
    frames = []
    def render(self, screen, i, *args): self.frames.append(i)
clock = Clock()
art = Art()
splash.time = clock
splash._art = art
splash._t0 = 0
clock.now = 3999
splash.draw()
assert art.frames == []
clock.now = 4000
splash.draw()
clock.now = 4030
splash.draw()
assert art.frames == [0, 1]
assert splash.BLACK_LEAD_MS + splash.ANIMATION_MS == 13600
splash.finish(wait=False)
assert splash._art is None and 'bootart' not in sys.modules
`);
  console.log('bootart: nine native frames match; black lead-in, timing and release pass');
} catch(e) { console.error(String(e)); process.exitCode=1; } finally { dev.dispose(); }
