// Screenshots of the console on the QT Py cosigner: the 1.8" as 160x128, three buttons named in the
// footer (board "qtpy", quorum_ui_s with BAR). Drawn by the real firmware on the emulator with
// console_test's fake service and virtual chip, each frame copied out of show(). Every PNG is 3x,
// with a strip below the screen and a dot under each footer slot: D0, D1, D2, left to right.
// README.md lists them in order. For docs/quorum-ui/qtpy/.
//   node tools/board/shots_qtpy.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/quorum-ui/qtpy");
mkdirSync(out, { recursive: true });
const W = 160, H = 128, S = 3, EDGE = 14 * S;     // the strip below the screen, at 3x
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16), heapsize: 2 * 1024 * 1024,
  files: { ...readWorkspace(), "console_test.py": t("console_test.py") }, shims: readShims(),
  onStdout: (l) => { if (/Traceback|Error/.test(l)) console.log(l); },
});
const py = (code) => dev.mp.runPython(code);
const shots = [];

function shot(name, caption) {
  py(`import binascii\n_hex = binascii.hexlify(FULL).decode()`);
  const screen = scaleRGBA(frameToRGBA(Buffer.from(dev.mp.globals.get("_hex"), "hex")), W, H, S);
  const ow = W * S, oh = H * S + EDGE;
  const img = new Uint8ClampedArray(ow * oh * 4);
  img.set(screen, 0);
  for (let i = H * S * ow * 4; i < img.length; i += 4) img.set([24, 24, 28, 255], i);
  const sw = Math.floor((W - 8) / 3);
  for (let k = 0; k < 3; k++) {                                // D0, D1, D2 under their slots
    const cx = (2 + k * (sw + 2) + sw / 2) * S, cy = H * S + EDGE / 2;
    for (let y = cy - 10; y <= cy + 10; y++) for (let x = cx - 10; x <= cx + 10; x++)
      if ((x - cx) ** 2 + (y - cy) ** 2 <= 100) img.set([150, 150, 156, 255], (Math.round(y) * ow + Math.round(x)) * 4);
  }
  writeFileSync(join(out, `${name}.png`), encodePNG(ow, oh, img));
  shots.push([name, caption]);
  console.log("shot", name);
}

py(`with open("secrets.py", "w") as f:
    f.write('BOARD = "qtpy"\\n')
import sys
for m in ("board", "lcd", "fonts", "quorum_ui", "quorum_ui_s", "splash", "bootmark"):
    sys.modules.pop(m, None)
import console_test as T, board, lcd as L
T.chip(counter=7)
Q = T.fresh(extra='BOARD = "qtpy"')
U = Q.U
assert board.BOARD == "qtpy" and (L.W, L.H) == (160, 128) and U.BAR, board.BOARD
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
draw()`);
shot("01-home", "Home: the queue, two rows at a time. D1 moves down it, D2 opens the one in focus.");
py(`Q.sel, Q.foot = 2, "device"\ndraw()`);
shot("02-home-device", "D1 past the last row: Owners, Device and Key. D0 goes back onto the list.");
py(`Q.sel, Q.foot = 0, None\nQ.open_entry(Q.queue[0])\ndraw()`);
shot("03-review-head", "A review opens on what it does. Footer: Reject (one press, any page), Next, and \"See n\": D2 shows the next page not yet seen.");
py(`page("item")\ndraw()`);
shot("04-review-item", "The send: the amount, big.");
py(`page("to")\ndraw()`);
shot("05-review-to", "Who it goes to, the whole address in four-character chunks, and its blockie.");
py(`page("approvals")\ndraw()`);
shot("06-review-approvals", "Who has approved, and what this key's signature would make it.");
py(`page("verify")\ndraw()`);
shot("07-review-verify", "The code to compare with the proposer: the hash's last 8, and its blockie.");
py(`page("hash")\ndraw()`);
shot("08-review-hash", "The whole Safe transaction hash, worked out here. Every page seen: D2 says Sign.");
py(`Q.state, Q.hold_t0 = "hold", U.time.ticks_ms() - 1200\ndraw()`);
shot("09-hold", "D2 held: its slot fills. 2 s to sign; let go early and nothing is signed. D0 still rejects.");
py(`Q.state = "review"\nQ.open_entry(Q.queue[1])\ndraw()`);
shot("10-red-head", "An unknown call: red. Sign takes a 3 s hold.");
py(`page("calldata")\ndraw()`);
shot("11-red-calldata", "Its function selector and calldata size, on a red page.");
py(`for i in range(len(Q.pages)): Q.seen.add(i)
Q.state, Q.hold_t0 = "hold", U.time.ticks_ms() - 1800
draw()`);
shot("12-red-hold", "Holding Sign on a red transaction: the slot fills in red, 3 s.");
py(`Q.state = "review"\nQ.open_entry(Q.queue[2])\ndraw()`);
shot("13-refused", "A hash the fields don't produce: refused. Sign stays grey; D0 rejects.");
py(`Q.open_entry(Q.queue[0])\nQ.press_sign("D2")\ndraw()`);
shot("14-see-every-page", "D2 before every page is seen: it shows the next one and says how many are left.");
py(`Q.msg = ""
Q.state, Q.result = "result", (True, "Signed", ["Posted to Safe's service", "2 of 2: ready to execute", "Key use #8"])
Q.unsent = None
draw()`);
shot("15-result-signed", "Signed and posted. D2: OK.");
py(`Q.state, Q.result = "result", (False, "Not sent", ["Signed, but the service said:", "502 Bad Gateway"])
Q.unsent = (Q.queue[0], "0x00")
draw()
Q.unsent = None`);
shot("16-result-unsent", "Signed but not sent: D2 sends it again, D0 goes back.");
py(`Q.state, Q.opage = "owners", 0\ndraw()`);
shot("17-owners", "Owners: who can approve. D0 back.");
py(`Q.state, Q.dfoot = "device", "chip"\ndraw()`);
shot("18-device", "Device: the chip, its slot and key, the pin, uses, memory.");
py(`Q.open_key("home")\ndraw()`);
shot("19-key-code", "Key: the owner address as a QR code. A signer, not a wallet. D1 shows it in full.");
py(`Q.kpage = 1\ndraw()`);
shot("20-key-full", "The owner address in full, the key's fingerprint and use count.");
py(`Q.state = "nochip"\ndraw()`);
shot("21-nochip", "No chip on the bus: D2 checks again.");
dev.dispose();

const md = ["# The console on the QT Py cosigner", "",
  "Written by `node tools/board/shots_qtpy.mjs`: the real firmware on the emulator, the 1.8\" as 160 × 128,",
  "three buttons named in the footer (the grey dots: D0, D1, D2, left to right). The build is",
  "[hardware/builds/qtpy-cosigner](../../../hardware/builds/qtpy-cosigner/README.md).", "",
  "- **D0** (Boot): Reject on a review (one press, any page, even while Sign is held); Back anywhere else.",
  "- **D1**: next page or row; held 1 s, the one before.",
  "- **D2**: open; on a review, the next page not yet seen, then Sign: held 2 s, 3 s when a page is red.", ""];
for (const [n, c] of shots) md.push(`### ${n.replace(/^\d+-/, "").replace(/-/g, " ")}`, "", c, "", `![${n}](${n}.png)`, "");
writeFileSync(join(out, "README.md"), md.join("\n"));
console.log(`${shots.length} shots in ${out}`);
