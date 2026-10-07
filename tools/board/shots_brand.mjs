// Mockups for docs/BRANDED-KEYS.md: the proposed bench (BRAND) and user (CLAIM) steps, drawn by the
// real ceremony screen (firmware/provision.py UI) on the emulator. Only the words are new, and no
// firmware has them; the key and owner come from the virtual ATECC608 run through C1-C4.
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
  files: { ...readWorkspace(), "console_test.py": t("console_test.py"), "ceremony_test.py": t("ceremony_test.py") },
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
KEY = c.key
OWNER = c.owner()
SERIAL = c.serial
BRAND = "0x" + hashlib.sha256(b"PicoQuorum brand v1" + bytes.fromhex(SERIAL)).digest()[:20].hex()

class K:
    down = set()
    def held(self, k):
        return k in self.down

class Mock:
    NSTEPS = 6
    GENKEY = ()
    PERMANENT = ()
    FINAL = ()
    def __init__(self, header, nsteps, titles, what, permanent=(), genkey=(), key=None, note="", pic=None):
        self.HEADER, self.NSTEPS, self.TITLES, self.WHAT = header, nsteps, titles, what
        self.PERMANENT, self.GENKEY, self.key, self._note, self._pic = permanent, genkey, key, note, pic
        self.st = None
    def index(self, st):
        return int(st[1:]) if st[1:].isdigit() else 0
    def picture(self, st, result=False):
        return self._pic
    def subtitle(self):
        return "%s 608C" % SERIAL
    def note(self):
        return self._note
    def step(self):
        return self.st
    def fingerprint(self):
        return "%08x" % (self.key[0] >> 224)

BT = {"B1": "Pre-flight", "B2": "Write quorum v2", "B3": "Lock the config", "B4": "Brand",
      "B5": "Countersign", "B6": "Lock the data zone", "B7": "Label"}
BW = {"B4": "Writes the brand: PicoQuorum, batch 3, key 0042, the config CRC, into slot 8 and the OTP zone. No key is made here. Rewritable until B6.",
      "B5": "The brand key, PicoQuorum key 0000, signs this chip's brand. The signature goes into slot 8 beside it.",
      "B6": "Locks the data and OTP zones forever. The chip checks their CRC, brand included. After this nothing can put a key into slot 0 except the chip's own GenKey.",
      "B7": "Prints the label. The chip leaves the bench with no key in it."}
UT = {"U1": "Check the brand", "U2": "Make your key", "U3": "Test signatures", "U4": "Seal your key", "U5": "Your owner address"}
UW = {"U1": "Reads the brand and checks the bench's signature. Changes nothing.",
      "U2": "Makes your key inside the chip, in slot 0. Nobody chose it, the bench included. Until U4 you can make it again.",
      "U3": "Signs two test digests with your key and checks both here.",
      "U4": "Locks slot 0 forever: your key can never be replaced or overwritten.",
      "U5": "The address your key gets as a Safe owner."}

def show(m, st, result=None, theme="dark"):
    m.st = st
    ui = P.UI(splash.begin(), K(), c.sig, theme, ceremony=m)
    ui.result = result
    ui.dirty = True
    ui.draw()
    return ui
`);

// the bench
py(`S.arm(); m = Mock("BRAND quorum v2", 7, BT, BW, permanent=("B3", "B6"), note="counter 0: 0   slot 0: empty")
show(m, "B4")`);
shot("b4-brand");
py(`show(m, "B6")`);
shot("b6-data-lock");
py(`m._pic = BRAND
ui = show(m, "B7", ("B7", True, [("quorum v2, locked 00/00", True), ("brand signed: key 0000", True),
     ("slot 0 empty, not sealed", True), ("counter 0: 0", True), ("PrivWrite: never", True)],
     "Label 0042. The picture is the brand's: the user's console draws the same one."), "dark")
`);
shot("b7-label");

// the user
py(`S.arm(); m = Mock("CLAIM your PicoQuorum key", 5, UT, UW, permanent=("U4",), genkey=("U2",), pic=BRAND)
ui = show(m, "U1", ("U1", True, [("brand signed by PicoQuorum", True), ("batch 3, key 0042", True),
     ("locked at the bench 00/00", True), ("no key yet, slot 0 open", True), ("counter 0: 0, never used", True)],
     "Check the label: it says 0042 and shows this picture."), "light")`);
shot("u1-brand-ok");
py(`m._pic = None
show(m, "U2", None, "light")`);
shot("u2-make-key");
py(`m.key = KEY; m._note = "counter 0: 2"
show(m, "U4", None, "light")`);
shot("u4-seal");
py(`m._pic = OWNER
show(m, "U5", ("U5", True, [("slot 0 sealed", True), ("signs and verifies", True), ("counter 0: 3", True)],
     OWNER + " . Next, in the app: deploy it, then your starter Safe."), "light")`);
shot("u5-owner");
py(`m._pic = None; m.key = None
show(m, "U1", ("U1", False, [("brand signature", False), ("locked 00/00", True)],
     "This chip's brand doesn't verify. Don't use it as a key, and tell the project."), "light")`);
shot("u1-brand-bad");
dev.dispose();
