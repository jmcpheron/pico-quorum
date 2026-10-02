// Screenshots of the Trust M ceremony's last steps (T8 the seal checked, T9 freeze the spares, T10
// done) and the console's Chip page after them, drawn by the real firmware on the emulator's
// virtual Trust M (test-vectors/trustm_test.py sets each state). For docs/mainnet/ and the review.
//   node tools/board/shots_tm.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA, W, H } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/mainnet/shots");
mkdirSync(out, { recursive: true });
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16),
  files: { ...readWorkspace(), "trustm_test.py": t("trustm_test.py"), "console_test.py": t("console_test.py") },
  shims: readShims(),
  onStdout: (l) => { if (/Traceback|Error/.test(l)) console.log(l); },
});
const py = (code) => dev.mp.runPython(code);
const shot = (name) => {
  writeFileSync(join(out, name + ".png"), encodePNG(W * 2, H * 2, scaleRGBA(frameToRGBA(dev.frame), W, H, 2)));
  console.log("shot", name);
};

// a chip sealed before T9 existed, as TM1 is: key, record and binding sealed, every spare open
py(`import trustm_test as TT, trustm_sim, splash
TT.secrets(); TT.only_trustm(); trustm_sim.seal_as_quorum()
c, S, P = TT.ceremony()
import provision, chipapp
class K:
    def held(self, k):
        return False
chipapp.d = splash.begin(); chipapp.sig = c.sig; chipapp.keys = K(); chipapp.identify(); chipapp.banner()`);
shot("tm-01-banner-sealed");
py(`ui = provision.UI(splash.begin(), K(), c.sig, "dark", c); ui.dirty = True; ui.draw()`);
shot("tm-02-T8");
for (const [i, st] of ["T8", "T9", "T10"].entries()) {
  py(`S.arm(); ui.result = ("${st}",) + ui.c.run("${st}"); ui.dirty = True; ui.draw()`);
  shot(`tm-0${3 + i * 2}-${st}-result`);
  py(`ui.result = None; ui.dirty = True; ui.draw()`);
  if (st !== "T10") shot(`tm-0${4 + i * 2}-${st === "T8" ? "T9" : "T10"}`);
}

// T9 with a data object kept open for a later config record
py(`TT.secrets(extra='TRUSTM_KEEP_OPEN = ["F1D2"]\\n'); TT.only_trustm(); trustm_sim.seal_as_quorum()
c, S, P = TT.ceremony()
import provision
c.run("T8")
ui = provision.UI(splash.begin(), K(), c.sig, "dark", c); ui.dirty = True; ui.draw()`);
shot("tm-09-T9-keep-open");

// the console's Chip page, before and after T9
py(`TT.only_trustm(); trustm_sim.seal_as_quorum()
T, Q = TT.console()
import quorum_ui
splash.finish(wait=False)
Q.handle("X"); Q.handle("A"); Q.d.frames(quorum_ui.draw, Q)`);
shot("tm-10-chip-page-1");
py(`Q.handle("A"); Q.d.frames(quorum_ui.draw, Q)`);
shot("tm-11-chip-page-2-spares-open");
py(`sim = trustm_sim.chip()
import tmcfg
for o in tmcfg.SPARES:
    sim.objs[o]["meta"]["lcso"] = 7
sim.save()
T, Q = TT.console(keep=True)
splash.finish(wait=False)
Q.handle("X"); Q.handle("A"); Q.d.frames(quorum_ui.draw, Q)`);
py(`Q.handle("A"); Q.d.frames(quorum_ui.draw, Q)`);
shot("tm-12-chip-page-2-spares-frozen");
dev.dispose();
