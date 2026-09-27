// Screenshots of the production console's new screens and the provisioning ceremony, drawn by the
// real firmware on the emulator (the console's test harness sets each state). For the review
// walkthrough in docs/firmware-production/.
//   node tools/board/shots.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA, W, H } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/firmware-production/shots");
mkdirSync(out, { recursive: true });
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16),
  files: { ...readWorkspace(), "console_test.py": t("console_test.py"), "ceremony_test.py": t("ceremony_test.py") },
  shims: readShims(),
  onStdout: (l) => { if (/Traceback|Error/.test(l)) console.log(l); },
});
const py = (code) => dev.mp.runPython(code);
const shot = (name) => {
  writeFileSync(join(out, name + ".png"), encodePNG(W * 2, H * 2, scaleRGBA(frameToRGBA(dev.frame), W, H, 2)));
  console.log("shot", name);
};

py(`import console_test as T, atecc_sim, p256
T.chip(counter=41)
Q = T.fresh()
T.serve(Q, [T.tx(Q, 0, value=10**15), T.tx(Q, 1, to=T.OTHER, op=1, data="0x12345678")])
Q.state = "device"; Q.U.draw(Q)`);
shot("50-device");
py(`Q.state = "home"; Q.U.draw(Q)`);
shot("51-home-pinned");
py(`Q.open_entry(Q.queue[1]); Q.U.draw(Q)`);
shot("52-delegatecall-refused");
py(`Q.state = "home"; e = Q.queue[0]
T.sign(Q, e, 2100); Q.U.draw(Q)`);
shot("53-signed-counter");
py(`atecc_sim.chip().counters[0] += 2; atecc_sim.chip().save()
Q = T.fresh(keep=True)
T.serve(Q, [T.tx(Q, 0, value=10**15)])
Q.U.draw(Q)`);
shot("54-outside-signatures");
py(`Q = T.fresh(expect={"serial": T.SERIAL, "slot": 0, "owner": T.owner_of(2), "locked": True}); Q.U.draw(Q)`);
shot("55-pin-fail");
py(`Q = T.fresh(expect=None); Q.U.draw(Q)`);
shot("56-not-pinned");
py(`Q = T.fresh(safe=False); Q.U.draw(Q)`);
shot("57-no-safe");
py(`Q = T.fresh(); Q.fails = 20; Q.U.draw_crashed(Q, "ZeroDivisionError('divide by zero',)")`);
shot("58-crashed");
py(`open("maint", "w").close()
import sys; sys.modules.pop("main_console", None)
import main_console
import os; os.remove("maint")`);
shot("59-maintenance");

// the ceremony, step by step, on a fresh virtual chip
py(`import ceremony_test as C
C.secrets(); C.fresh_chip()
c, S, P = C.ceremony()
class K:
    down = set()
    def held(self, k):
        return k in self.down
import splash
ui = P.UI(splash.begin(), K(), c.sig)
ui.dirty = True; ui.draw()`);
shot("60-ceremony-C1");
const steps = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"];
for (const [i, st] of steps.entries()) {
  py(`S.arm(); ui.result = ("${st}",) + ui.c.run("${st}"); ui.dirty = True; ui.draw()`);
  shot(`${61 + i * 2}-ceremony-${st}-result`);
  py(`ui.result = None; ui.dirty = True; ui.draw()`);
  if (i < steps.length - 1) shot(`${62 + i * 2}-ceremony-${steps[i + 1]}`);
}
py(`C.secrets(lock=False); import provision; c2, S2, P2 = C.ceremony()
C.fresh_chip(); c2, S2, P2 = C.ceremony(); c2.run("C1"); c2.run("C2")
ui = P2.UI(splash.begin(), K(), c2.sig); ui.dirty = True; ui.draw()`);
shot("80-ceremony-C3-not-allowed");
py(`import chipapp; chipapp.d = splash.begin(); chipapp.sig = c.sig; chipapp.identify(); chipapp.banner()`);
shot("81-ceremony-image-banner");

// Which chip is in: chips.json already knows chip #1 (dark), so the fresh virtual chip is chip 2 (light)
py(`import json
with open("chips.json", "w") as f:
    json.dump({"0123f3acfd2a826bee": {"n": 1, "name": "chip 1", "theme": "dark", "profile": "legacy-test", "first": 0}}, f)
C.secrets(); C.fresh_chip(); c, S, P = C.ceremony()
chipapp.sig = c.sig; chipapp.identify(); chipapp.banner()`);
shot("82-ceremony-banner-chip2-light");
py(`ui = P.UI(splash.begin(), K(), c.sig, chipapp.chip["theme"]); ui.dirty = True; ui.draw()`);
shot("83-ceremony-C1-light");
py(`S.arm(); ui.result = ("C1",) + ui.c.run("C1"); ui.dirty = True; ui.draw()`);
shot("84-ceremony-C1-result-light");
py(`for st in ("C2", "C3", "C4", "C5"):
    S.arm(); ui.c.run(st)
ui.result = None; ui.dirty = True; ui.draw()`);
shot("85-ceremony-C6-light");
py(`atecc_sim.provision_v1()
Q = T.fresh(expect=None, prod=False)
T.serve(Q, [T.tx(Q, 0, value=10**15)])
Q.U.draw(Q)`);
shot("86-console-chip2-light-home");
py(`Q.state = "device"; Q.U.draw(Q)`);
shot("87-console-chip2-light-device");
dev.dispose();
