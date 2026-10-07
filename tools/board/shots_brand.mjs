// Mockups for docs/BRANDED-KEYS.md: the proposed bench (brand) and user (claim) screens, in the
// console's own look (tools/board/brand_screens.py, drawn with quorum_ui.py's kit and fonts) on the
// emulator. No firmware has these screens. The key and owner come from the virtual ATECC608 run
// through C1-C4, so they are new on every run.
//   node tools/board/shots_brand.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA, W, H } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/branded-keys");
mkdirSync(out, { recursive: true });
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16),
  files: { ...readWorkspace(), "ceremony_test.py": t("ceremony_test.py"),
           "brand_screens.py": readFileSync(join(ROOT, "tools/board/brand_screens.py"), "utf8") },
  shims: readShims(),
  onStdout: (l) => { if (/Traceback|Error/.test(l)) console.log(l); },
});
const py = (code) => dev.mp.runPython(code);
const shot = (name) => {
  writeFileSync(join(out, name + ".png"), encodePNG(W * 2, H * 2, scaleRGBA(frameToRGBA(dev.frame), W, H, 2)));
  console.log("shot", name);
};

py(`import ceremony_test as C, splash, hashlib
C.secrets(); C.fresh_chip()
c, S, P = C.ceremony()
for st in ("C1", "C2", "C3", "C4"):
    S.arm(); c.run(st)
KEY = c.fingerprint()
OWNER = c.owner()
BRAND = "0x" + hashlib.sha256(b"PicoQuorum brand v1" + bytes.fromhex(c.serial)).digest()[:20].hex()
import brand_screens as B, quorum_ui as U
U.use("dark")
d = splash.begin()`);

const screens = [
  ["b4-brand", `d.frames(B.b4_brand, d, "0042", 3)`],
  ["b6-data-lock", `d.frames(B.b6_lock, d)`],
  ["b7-ready", `d.frames(B.b7_ready, d, "0042", BRAND)`],
  ["u0-welcome", `d.frames(B.u0_welcome, d, "0042", 3)`],
  ["u1-brand-ok", `d.frames(B.u1_brand, d, "0042", BRAND)`],
  ["u2-make-key", `d.frames(B.u2_make, d)`],
  ["u3-test", `d.frames(B.u3_test, d)`],
  ["u4-seal", `d.frames(B.u4_seal, d, KEY)`],
  ["u5-owner", `d.frames(B.u5_done, d, OWNER)`],
  ["u1-brand-bad", `d.frames(B.u_bad, d)`],
];
for (const [name, code] of screens) {
  py(code);
  shot(name);
}
dev.dispose();
