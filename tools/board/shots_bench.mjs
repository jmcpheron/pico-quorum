// The brand bench as built (firmware/brand_ui.py over brand.py), on the emulator's virtual ATECC608
// driven by the knob: each step before, armed with the hold bar half full on a gated step, and its
// result. The mockups in docs/BRANDED-KEYS.md are tools/board/shots_brand.mjs; these are the firmware.
// The chip is new on every run, so the serial-free parts match and the key differs.
//   node tools/board/shots_bench.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA, W, H } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/branded-keys/bench");
mkdirSync(out, { recursive: true });
let failed = false;
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16),
  files: { ...readWorkspace(), "brand_test.py": readFileSync(join(ROOT, "test-vectors/brand_test.py"), "utf8") },
  shims: readShims(),
  onStdout: (l) => { if (/Traceback|Error|FAIL/.test(l)) { failed = true; console.log(l); } },
});
const py = (code) => dev.mp.runPython(code);
const shots = [];
const shot = (name) => {
  writeFileSync(join(out, name + ".png"), encodePNG(W * 2, H * 2, scaleRGBA(frameToRGBA(dev.frame), W, H, 2)));
  shots.push(name);
};

py(`import time, brand_test as T, splash, lcd as L
T.secrets(); T.fresh_chip()
c, B = T.ceremony()
L.KNOB = True
d = splash.begin()
import brand_ui
ui = brand_ui.UI(d, None, c.sig, "dark", c)
S = brand_ui.S
def paint():
    ui.dirty = True
    ui.draw()
def half():
    S.arm()
    ui.hold = time.ticks_add(time.ticks_ms(), -brand_ui.P.HOLD_MS // 2)
    paint()
def run(st):
    S.arm()
    ui.hold = None
    ui.result = (st,) + c.run(st)
    paint()
def done():
    ui.result = None
    S.disarm()`);

for (const st of ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "S1", "S2", "S3", "S4"]) {
  const gated = ["B3", "B6", "S1", "S3"].includes(st);
  py(`assert c.step() == "${st}", c.step()\npaint()`);
  shot(st.toLowerCase());
  if (gated) {
    py(`half()`);
    shot(st.toLowerCase() + "-hold");
  }
  py(`run("${st}")`);
  shot(st.toLowerCase() + "-done");
  py(`done()`);
}
dev.dispose();
console.log(`${shots.length} shots in ${out}` + (failed ? " (with errors above)" : ""));
process.exit(failed ? 1 : 0);
