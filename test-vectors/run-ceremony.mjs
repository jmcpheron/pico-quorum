// The quorum v1 ceremony (test-vectors/ceremony_test.py) on MicroPython 1.26 in WebAssembly with
// the emulator's virtual ATECC608: a factory-fresh 608A, 608B and 608C sealed step by step, the refusals,
// and the console signing with the result. Must pass before a real fresh chip is touched.
//   (cd emu && npm ci) && node test-vectors/run-ceremony.mjs
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
  files: { ...readWorkspace(), "ceremony_test.py": t("ceremony_test.py"), "console_test.py": t("console_test.py") },
  shims: readShims(),
  onStdout: (l) => { out.push(l); if (!quiet || /^FAIL/.test(l)) console.log(l); },
});
dev.mp.runPython("import ceremony_test\n_failed = ceremony_test.main()");
const failed = dev.mp.globals.get("_failed");
dev.dispose();
if (quiet) console.log(out.filter((l) => /^pass/.test(l)).length + " pass, " + failed + " failed");
process.exit(failed ? 1 : 0);
