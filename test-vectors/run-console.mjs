// The console's decisions (test-vectors/console_test.py) on MicroPython 1.26 in WebAssembly, with
// the emulator's shims and its virtual ATECC608: the same firmware files the board runs.
//   (cd emu && npm ci) && node test-vectors/run-console.mjs
import { readFileSync } from "node:fs";
import { loadMicroPython } from "../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice } from "../emu/core/runtime.mjs";
import { readWorkspace, readShims } from "../emu/core/workspace.mjs";
import { softPasskey } from "../emu/core/softpasskey.mjs";

const quiet = process.argv.includes("--quiet");
const out = [];
const dev = await createDevice({
  loadMicroPython,
  keys: new Int32Array(16),
  files: { ...readWorkspace(), "console_test.py": readFileSync(new URL("console_test.py", import.meta.url), "utf8") },
  shims: readShims(),
  passkey: softPasskey(),         // off until console_test's case_passkey turns it on
  onStdout: (l) => { out.push(l); if (!quiet || /^FAIL/.test(l)) console.log(l); },
});
dev.mp.runPython("import console_test\n_failed = console_test.main()");
const failed = dev.mp.globals.get("_failed");
dev.dispose();
if (quiet) console.log(out.filter((l) => /^pass/.test(l)).length + " pass, " + failed + " failed");
process.exit(failed ? 1 : 0);
