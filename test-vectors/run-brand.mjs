// The bench half of a branded key (test-vectors/brand_test.py) on MicroPython 1.26 in WebAssembly with
// the emulator's virtual ATECC608: a fresh 608A, 608B and 608C branded with the test key, then a key
// made after the data lock and sealed, the refusals and the knob; then key 0000 pinned, B5 by a swap
// of chips, and the claim (U1-U5) with its refusals. Then the owner's key on PicoQuorumKey's three
// buttons (keypick_s.py). Must pass before a real spare is touched.
//   (cd emu && npm ci) && node test-vectors/run-brand.mjs
import { readFileSync } from "node:fs";
import { loadMicroPython } from "../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice } from "../emu/core/runtime.mjs";
import { readWorkspace, readShims } from "../emu/core/workspace.mjs";

const quiet = process.argv.includes("--quiet");
const out = [];
const t = (f) => readFileSync(new URL(f, import.meta.url), "utf8");
async function run(main) {
  const dev = await createDevice({
    loadMicroPython,
    keys: new Int32Array(16),
    files: { ...readWorkspace(), "brand_test.py": t("brand_test.py"), "console_test.py": t("console_test.py") },
    shims: readShims(),
    onStdout: (l) => { out.push(l); if (!quiet || /^FAIL/.test(l)) console.log(l); },
  });
  dev.mp.runPython(`import brand_test\n_failed = brand_test.${main}()`);
  const n = dev.mp.globals.get("_failed");
  dev.dispose();
  return n;
}
// PicoQuorumKey's three buttons in a device of their own: board.py reads secrets.BOARD once.
const failed = (await run("main")) + (await run("main_three"));
if (quiet) console.log(out.filter((l) => /^pass/.test(l)).length + " pass, " + failed + " failed");
process.exit(failed ? 1 : 0);
