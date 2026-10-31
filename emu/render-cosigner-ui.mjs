// Draws every screen of the UI study (emu/sketches/cosigner_ui.py) on the stompbox's panel, build1's
// 2.4" at 320x240, and writes them to docs/quorum-ui/v3/shots/<n>-<name>.png.
//   node emu/render-cosigner-ui.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import { loadMicroPython } from "./node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "./core/runtime.mjs";
import { encodePNG } from "./core/png.mjs";
import { readWorkspace, readShims } from "./core/workspace.mjs";

const OUT = "docs/quorum-ui/v3/shots";
mkdirSync(OUT, { recursive: true });
const dev = await createDevice({ loadMicroPython, keys: new Int32Array(16), files: readWorkspace(),
  shims: readShims(), heapsize: 2 * 1024 * 1024, secrets: 'BOARD="build1"\nSCREEN="2.4"', onStdout: console.log });
try {
  // The emulator's own display is 240x240, so the 320x240 panel is caught here instead: each band's
  // window and bytes land in a buffer, as the ST7789's RAM would hold them.
  dev.mp.runPython(`
import cosigner_ui as U, lcd as L, board, binascii, json
class Pin:
    def __call__(self, v): pass
class Panel:
    def __init__(self):
        self.ram = bytearray(L.W * L.H * 2)
    def window(self, x, y, w, h):
        self.win = (x - board.X_OFF, y - board.Y_OFF, w, h)
    def write(self, b):
        x, y, w, h = self.win
        for r in range(h):
            o = ((y + r) * L.W + x) * 2
            self.ram[o:o + 2 * w] = b[2 * r * w:2 * (r + 1) * w]
panel = Panel()
U.lcd = L.LCD()
U.lcd._window, U.lcd.spi, U.lcd.dc, U.lcd.cs = panel.window, panel, Pin(), Pin()
_names = json.dumps([n for n, _ in U.SCREENS])
_wh = json.dumps([L.W, L.H])
`);
  const names = JSON.parse(dev.mp.globals.get("_names"));
  const [w, h] = JSON.parse(dev.mp.globals.get("_wh"));
  names.forEach((name, i) => {
    dev.mp.runPython(`U.draw(${i})\n_hex = binascii.hexlify(panel.ram).decode()`);
    const file = `${OUT}/${String(i + 1).padStart(2, "0")}-${name}.png`;
    writeFileSync(file, encodePNG(w, h, frameToRGBA(Buffer.from(dev.mp.globals.get("_hex"), "hex"))));
    console.log("wrote", file);
  });
} finally { dev.dispose(); }
