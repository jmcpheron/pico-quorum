// Screenshots of the ceremony on the Feather ESP32-S3 Reverse TFT (setup_s.py): C1-C10 on the
// emulator's virtual 608C, drawn by the real firmware, each frame copied out of show(). Framed as
// shots_feather.mjs frames the console: 3x, the board's edge on the left with a dot level with each
// button. README.md lists them in order. For docs/quorum-ui/feather-setup/.
//   node tools/board/shots_feather_setup.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/quorum-ui/feather-setup");
mkdirSync(out, { recursive: true });
const W = 240, H = 135, S = 3, EDGE = 22 * S;
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16), heapsize: 2 * 1024 * 1024,
  files: { ...readWorkspace(), "ceremony_test.py": t("ceremony_test.py"), "console_test.py": t("console_test.py") },
  shims: readShims(),
  onStdout: (l) => { if (/Traceback|Error/.test(l)) console.log(l); },
});
const py = (code) => dev.mp.runPython(code);
const shots = [];
let railY = [];

function shot(name, caption) {
  py(`import binascii\n_hex = binascii.hexlify(FULL).decode()`);
  const screen = scaleRGBA(frameToRGBA(Buffer.from(dev.mp.globals.get("_hex"), "hex")), W, H, S);
  const ow = EDGE + W * S, oh = H * S;
  const img = new Uint8ClampedArray(ow * oh * 4);
  for (let y = 0; y < oh; y++) for (let x = 0; x < ow; x++) {
    const o = (y * ow + x) * 4;
    if (x >= EDGE) {
      const i = (y * W * S + x - EDGE) * 4;
      img.set(screen.subarray(i, i + 4), o);
    } else {
      img.set([24, 24, 28, 255], o);
    }
  }
  for (const by of railY) {
    const cy = Math.min(oh - 12, Math.max(12, by * S)), cx = EDGE / 2;
    for (let y = cy - 10; y <= cy + 10; y++) for (let x = cx - 10; x <= cx + 10; x++)
      if ((x - cx) ** 2 + (y - cy) ** 2 <= 100) img.set([150, 150, 156, 255], (y * ow + x) * 4);
  }
  writeFileSync(join(out, `${name}.png`), encodePNG(ow, oh, img));
  shots.push([name, caption]);
  console.log("shot", name);
}

py(`with open("secrets.py", "w") as f:
    f.write('BOARD = "feather-s3"\\n')
import sys
for m in ("board", "lcd", "splash", "bootmark"):
    sys.modules.pop(m, None)
import ceremony_test as CT, board, lcd as L, json
CT.secrets(extra='BOARD = "feather-s3"\\n')
CT.fresh_chip("608c")
c, S, P = CT.ceremony()
import splash, setup_s, chipapp
assert board.THREE and (L.W, L.H) == (240, 135)
class Keys:
    def held(self, k):
        return False
    def pressed(self):
        return []
d = splash.begin()
FULL = bytearray(L.W * L.H * 2)
def _show():
    FULL[:] = d.buffer
d.show = _show
chipapp.d, chipapp.keys, chipapp.sig = d, Keys(), c.sig
chipapp.identify()
chipapp.banner()
ui = setup_s.UI(d, Keys(), c.sig, "dark", c)
def draw():
    ui.dirty = True
    ui.draw()
def run(st):
    S.arm()
    ui.result = (st,) + c.run(st)
    draw()
def ok():
    ui.result = None
    S.disarm()
    draw()
_y = json.dumps(list(board.RAIL_Y))`);
railY = JSON.parse(dev.mp.globals.get("_y"));
shot("01-banner", "The banner: a fresh chip on the dual image. Not a signing console. D2 opens PROVISION.");
py(`draw()`);
shot("02-c1", "C1, the pre-flight: reads only. D0 back, D2 does it.");
py(`run("C1")`);
shot("03-c1-result", "C1's checks: the 608C, both zones open, the factory table, saved as a snapshot. D2: OK.");
py(`ok()\nrun("C2")`);
shot("04-c2-result", "C2 wrote quorum v1 and read it back. Compare the CRC with tools/check_config --summary on the laptop.");
py(`ok()`);
shot("05-c3", "C3, permanent: red. Not armed: D0+D1 held 3 s arms it (D2 does nothing until then).");
py(`ui.armhold = setup_s.time.ticks_ms() - 1800\ndraw()`);
shot("06-c3-arming", "D0+D1 held: the rail fills; 3 s to arm. Let go early and it isn't armed.");
py(`ui.armhold, ui.armdone = None, True\ndraw()`);
shot("07-c3-armed-letgo", "The arm took: let go of both.");
py(`ui.armdone = False\nS.arm()\ndraw()`);
shot("08-c3-armed", "Armed for 60 s: hold D2 3 s to lock.");
py(`ui.hold = setup_s.time.ticks_ms() - 1500\ndraw()`);
shot("09-c3-hold", "D2 held: the rail fills red. Let go before 3 s and nothing happens.");
py(`ui.hold = None\nrun("C3")`);
shot("10-c3-result", "C3 done: the config is locked, still quorum v1.");
py(`ok()`);
shot("11-c4", "C4: GenKey, armed and held like a permanent step.");
py(`run("C4")\n`);
shot("12-c4-result", "The new key, made inside the chip.");
py(`ok()\nrun("C5")`);
shot("13-c5-result", "C5: two test signatures checked here; counter 0 up by 2.");
py(`ok()`);
shot("14-c6", "C6, permanent: seal slot 0 so the key can never be replaced.");
py(`S._armed_until = setup_s.time.ticks_add(setup_s.time.ticks_ms(), 9000)\ndraw()`);
shot("14-c6-arm-again", "Under 10 s of the arm left: no hold starts, arm again. Chip 3's first C6 ran out partway.");
py(`run("C6")`);
shot("15-c6-result", "Slot 0 sealed: FE FF, the same key, it signs and verifies.");
py(`ok()\nrun("C7")`);
shot("16-c7-result", "C7: the owner address, to compare on the laptop with tools/fw verify --baseline.");
py(`ok()\nrun("C8")`);
shot("17-c8-result", "C8: zeros into slots 1-15, the record into OTP; the data CRC.");
py(`ok()`);
shot("18-c9", "C9, permanent: lock the data and OTP zones.");
py(`run("C9")`);
shot("19-c9-result", "C9 done.");
py(`ok()`);
shot("20-c10", "C10: the summary.");
py(`run("C10")`);
shot("21-c10-result", "Sealed: quorum v1 locked 00/00, slot 0 sealed, the record matches; set ALLOW_* back to False.");
py(`ui.result = None
CT.secrets(lock=False, extra='BOARD = "feather-s3"\\n')
CT.fresh_chip("608c")
c, S, P = CT.ceremony()
import setup_s
ui = setup_s.UI(d, Keys(), c.sig, "dark", c)
for st in ("C1", "C2"):
    c.run(st)
draw()`);
shot("22-c3-allow-off", "With ALLOW_LOCK False on the board, a permanent step says so and nothing arms it.");
dev.dispose();

const md = ["# The ceremony on the Feather ESP32-S3 Reverse TFT", "",
  "Written by `node tools/board/shots_feather_setup.mjs`: `setup_s.py` on the emulator, C1-C10 on a",
  "virtual 608C, 240 × 135, three buttons down the left edge (the grey dots: D0, D1, D2).", "",
  "- **D0**: back; on a result, OK.",
  "- **D0 + D1 held 3 s**: the arm, for 60 s (the Pico's B+Y). D2 is never part of it.",
  "- **D2**: do a step; on a permanent or GenKey step, held 3 s once armed. On a result, OK.", "",
  "ALLOW_LOCK and ALLOW_GENKEY in the board's `secrets.py` still gate every permanent step.", ""];
for (const [n, c] of shots) md.push(`### ${n.replace(/^\d+-/, "").replace(/-/g, " ")}`, "", c, "", `![${n}](${n}.png)`, "");
writeFileSync(join(out, "README.md"), md.join("\n"));
console.log(`${shots.length} shots in ${out}`);
