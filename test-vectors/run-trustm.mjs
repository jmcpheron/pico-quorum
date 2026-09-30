// The Trust M beside the ATECC608 (test-vectors/trustm_test.py) on MicroPython 1.26 in WebAssembly with
// the emulator's virtual Trust M and ATECC608: detection, the real chip's bytes, the quorum-tm1
// ceremony, the refusals, the console signing with the result. Must pass before a real Trust M is written.
//   (cd emu && npm install) && node test-vectors/run-trustm.mjs
import { readFileSync } from "node:fs";
import { loadMicroPython } from "../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice } from "../emu/core/runtime.mjs";
import { readWorkspace, readShims } from "../emu/core/workspace.mjs";

const quiet = process.argv.includes("--quiet");
const out = [];
const t = (f) => readFileSync(new URL(f, import.meta.url), "utf8");
const dev = await createDevice({
  loadMicroPython,
  keys: new Int32Array(16),
  files: { ...readWorkspace(), "trustm_test.py": t("trustm_test.py"), "console_test.py": t("console_test.py") },
  shims: readShims(),
  onStdout: (l) => { out.push(l); if (!quiet || /^FAIL/.test(l)) console.log(l); },
});
dev.mp.runPython("import trustm_test\n_failed = trustm_test.main()");
const failed = dev.mp.globals.get("_failed");
dev.dispose();
if (quiet) console.log(out.filter((l) => /^pass/.test(l)).length + " pass, " + failed + " failed");
process.exit(failed ? 1 : 0);
