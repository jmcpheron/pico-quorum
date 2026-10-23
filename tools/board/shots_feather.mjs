// Screenshots of the console on the Feather ESP32-S3 Reverse TFT: 240x135, three buttons down the
// left edge (board "feather-s3", quorum_ui_s with its rail). Drawn by the real firmware on the
// emulator with console_test's fake service and virtual chip, each frame copied out of show().
// Every PNG is 3x, with the board's edge on the left and a dot level with each button (board.RAIL_Y),
// and README.md lists them in order. For docs/quorum-ui/feather/.
//   node tools/board/shots_feather.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/quorum-ui/feather");
mkdirSync(out, { recursive: true });
const W = 240, H = 135, S = 3, EDGE = 22 * S;     // the board left of the screen, at 3x
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16), heapsize: 2 * 1024 * 1024,
  files: { ...readWorkspace(), "console_test.py": t("console_test.py") }, shims: readShims(),
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
      img.set([24, 24, 28, 255], o);                       // the Feather's black board
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
for m in ("board", "lcd", "fonts", "quorum_ui", "quorum_ui_s", "splash", "bootmark"):
    sys.modules.pop(m, None)
import console_test as T, board, lcd as L
T.chip(counter=7)
Q = T.fresh(extra='BOARD = "feather-s3"')
U = Q.U
assert board.BOARD == "feather-s3" and (L.W, L.H) == (240, 135), board.BOARD
T.serve(Q, [T.tx(Q, 0, value=5 * 10**16), T.tx(Q, 1, to=T.OTHER, data="0xdeadbeef"), T.tx(Q, 2, tamper=True)])
FULL = bytearray(L.W * L.H * 2)
d = Q.d
def _show():
    n = len(d.buffer) // (2 * L.W)
    FULL[d.y0 * L.W * 2:(d.y0 + n) * L.W * 2] = d.buffer
d.show = _show
def draw():
    Q.dirty = False
    d.frames(U.draw, Q)
def page(kind):
    Q.page = [k for k, i in Q.pages].index(kind)
    Q.seen.add(Q.page)
Q.state, Q.msg = "home", ""
import json
_y = json.dumps(list(board.RAIL_Y))
draw()`);
railY = JSON.parse(dev.mp.globals.get("_y"));
shot("01-home", "Home: the queue. D1 moves down it, D2 opens the one in focus. Past the list, D1 reaches Owners and Device.");
py(`Q.sel, Q.foot = 2, "device"\ndraw()`);
shot("02-home-device", "D1 past the last row: the Owners and Device choices. D0 goes back onto the list.");
py(`Q.sel, Q.foot = 0, None\nQ.open_entry(Q.queue[0])\ndraw()`);
shot("03-review-head", "A review opens on what it does. Rail: Reject (one press, any page), Next, and \"See 5\": D2 shows the next page not yet seen.");
py(`page("item")\ndraw()`);
shot("04-review-item", "The send: the amount, big.");
py(`page("to")\ndraw()`);
shot("05-review-to", "Who it goes to, and the whole address in four-character chunks.");
py(`page("approvals")\ndraw()`);
shot("06-review-approvals", "Who has approved, and what this key's signature would make it.");
py(`page("verify")\ndraw()`);
shot("07-review-verify", "The code to compare with the proposer: the hash's last 8, and its blockie.");
py(`page("hash")\ndraw()`);
shot("08-review-hash", "The whole Safe transaction hash, worked out here. Every page seen: D2 says Sign.");
py(`Q.state, Q.hold_t0 = "hold", U.time.ticks_ms() - 1200\ndraw()`);
shot("09-hold", "D2 held: the rail fills from the bottom. 2 s to sign; let go early and nothing is signed.");
py(`Q.state = "review"\nQ.open_entry(Q.queue[1])\ndraw()`);
shot("10-red-head", "An unknown call: red. Sign takes a 3 s hold.");
py(`page("calldata")\ndraw()`);
shot("11-red-calldata", "Its function selector and calldata size, on a red page.");
py(`page("digest")\ndraw()`);
shot("12-red-digest", "The calldata's digest to compare.");
py(`for i in range(len(Q.pages)): Q.seen.add(i)
Q.state, Q.hold_t0 = "hold", U.time.ticks_ms() - 1800
draw()`);
shot("13-red-hold", "Holding Sign on a red transaction: the rail fills in red, 3 s.");
py(`Q.state = "review"\nQ.open_entry(Q.queue[2])\ndraw()`);
shot("14-refused", "A hash the fields don't produce: refused. Sign stays grey; D0 rejects.");
py(`Q.open_entry(Q.queue[0])\nQ.press_sign("D2")\ndraw()`);
shot("15-see-every-page", "D2 before every page is seen: it shows the next one and says how many are left.");
py(`Q.msg = ""
Q.state, Q.result = "result", (True, "Signed", ["Posted to Safe's service", "2 of 2: ready to execute", "Key use #8"])
Q.unsent = None
draw()`);
shot("16-result-signed", "Signed and posted. D2: OK.");
py(`Q.state, Q.result = "result", (False, "Not sent", ["Signed, but the service said:", "502 Bad Gateway"])
Q.unsent = (Q.queue[0], "0x00")
draw()
Q.unsent = None`);
shot("17-result-unsent", "Signed but not sent: D2 sends it again, D0 goes back.");
py(`Q.state, Q.opage = "owners", 0\ndraw()`);
shot("18-owners", "Owners: who can approve. D0 back.");
py(`Q.state, Q.dfoot = "device", "chip"\ndraw()`);
shot("19-device", "Device: the chip, its slot and key, the pin, uses, memory. D1 moves along Chip, Wi-Fi, Back; D2 opens.");
py(`Q.chip_back = "device"\nQ.open_chip()\ndraw()`);
shot("20-chip", "The chip's own pages. D1 pages, D0 back.");
py(`Q.state = "nochip"\ndraw()`);
shot("21-nochip", "No chip on the bus: D2 checks again.");
py(`Q.state, Q.pin_why, Q.EXPECT, Q.EXPECTS = "pinfail", "secrets.py has no QUORUM_EXPECT", None, []\ndraw()`);
shot("22-pinfail", "A chip that isn't pinned: nothing will be signed until tools/fw pin adds it. D2 checks again.");
py(`Q.state, Q.sel, Q.foot = "home", 0, "key"\ndraw()`);
shot("23-home-key", "Past Owners and Device, D1 reaches Key: this key's QR code.");
py(`Q.open_key("home")\ndraw()`);
shot("24-key-code", "Key: the owner address as a QR code, beside its start, end and picture. A signer, not a wallet. D1 shows it in full, D0 goes back.");
py(`Q.kpage = 1\ndraw()`);
shot("25-key-full", "The owner address in full, the key's fingerprint and use count.");
py(`_owners, _queue = Q.owners, Q.queue
Q.owners = lambda w=None: [T.OTHER]
Q.queue, Q.state, Q.foot = [], "home", None
draw()`);
shot("26-home-not-owner", "A Safe that doesn't list this key yet: Not an owner yet, and where its code is.");
py(`Q.owners, Q.queue = _owners, _queue
Q.state = "unconfigured"
draw()`);
shot("27-ready", "No Safe set yet, on a console being set up: the key is ready, D2 shows its code.");
dev.dispose();

const md = ["# The console on the Feather ESP32-S3 Reverse TFT", "",
  "Written by `node tools/board/shots_feather.mjs`: the real firmware on the emulator, 240 × 135, three",
  "buttons down the left edge (the grey dots: D0, D1, D2). The rail beside them says what each does here.", "",
  "- **D0**: Reject on a review (one press, any page, even while Sign is held); Back anywhere else.",
  "- **D1**: next page or row; held 1 s, the one before. On a review's first page, held: out without rejecting.",
  "- **D2**: open; on a review, the next page not yet seen, then Sign: held 2 s, 3 s when a page is red.", "",
  "Key shows the key's owner address as a QR code (docs/ONBOARDING.md). The status home and the claim on three buttons come next.", ""];
for (const [n, c] of shots) md.push(`### ${n.replace(/^\d+-/, "").replace(/-/g, " ")}`, "", c, "", `![${n}](${n}.png)`, "");
writeFileSync(join(out, "README.md"), md.join("\n"));
console.log(`${shots.length} shots in ${out}`);
