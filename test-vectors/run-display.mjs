// Compare every pixel from the strip renderer with a full native-resolution framebuffer.
import { loadMicroPython } from '../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs';
import { createDevice } from '../emu/core/runtime.mjs';
import { readWorkspace, readShims } from '../emu/core/workspace.mjs';
const dev = await createDevice({ loadMicroPython, keys: new Int32Array(16),
  files: readWorkspace(), shims: readShims(), heapsize: 2 * 1024 * 1024,
  secrets: 'BOARD = "build1"\nSCREEN = "2.8"', onStdout: console.log });
try {
  dev.mp.runPython(`
import lcd, framebuf, fonts
from array import array
assert (lcd.W, lcd.H, lcd.BANDS) == (320, 240, 8)
d = lcd.LCD()
assert len(d.buffer) == 19200
full = bytearray(320 * 240 * 2)
class Reference(framebuf.FrameBuffer):
    y0 = 0
    band_h = 240
r = Reference(full, 320, 240, framebuf.RGB565)
def scene(f):
    f.fill(lcd.BLACK)
    f.rect(0, 0, 320, 240, lcd.WHITE)
    f.line(0, 0, 319, 239, lcd.RED)
    f.line(319, 0, 0, 239, lcd.GREEN)
    for y in range(25, 240, 30):
        f.fill_rect(12, y, 31, 13, lcd.BLUE)
        f.text('320x240', 65, y, lcd.WHITE)
        f.ellipse(230, y, 14, 9, lcd.YELLOW, True)
        f.poly(270, y, array('h', [0, -8, 18, 0, 0, 8]), lcd.RED, True)
scene(r)
for y in range(0, 240, 30):
    d.y0 = y
    scene(d)
    assert d.buffer == full[y * 640:(y + 30) * 640], ('pixels', y)
# The anti-aliased glyph blitter must agree across every strip boundary, too.
for y in range(0, 240, 30):
    d.y0 = y
    d.fill(lcd.BLACK)
    r.fill(lcd.BLACK)
    for ty in range(20, 240, 30):
        fonts.text(d, 'Full resolution', 5, ty, 'sans14', (255,255,255), (0,0,0))
        fonts.text(r, 'Full resolution', 5, ty, 'sans14', (255,255,255), (0,0,0))
    assert d.buffer == full[y * 640:(y + 30) * 640], ('glyphs', y)
seen = []
d.frames(lambda: seen.append(d.y0))
assert seen == list(range(0, 240, 30)) and d.y0 == 0
try:
    d.frames(lambda: 1/0)
except ZeroDivisionError:
    pass
assert d.y0 == 0
print('display: all 76,800 pixels match; glyph seams and frame cleanup pass')
`);
} finally { dev.dispose(); }
