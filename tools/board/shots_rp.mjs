// Screenshots of the console on console-rp: 240x135, three buttons under the screen named in its
// footer, in the CRT look (quorum_ui_crt.py: quorum_ui_s's pages, crt.py's scanlines and caps).
// Drawn by the real firmware on the emulator with console_test's fake relay, service and virtual chip,
// each page as it stands once its effect has played (crt.FX off), copied out of show(). Every PNG is
// 3x, with the case below the screen and each button's cap under its footer slot: D0 ■, D1 ●, D2 ▲.
// README.md lists them in order. For docs/quorum-ui/console-rp/.
//   node tools/board/shots_rp.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/quorum-ui/console-rp");
mkdirSync(out, { recursive: true });
const W = 240, H = 135, S = 3, EDGE = 18 * S;     // the case below the screen, at 3x
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const dev = await createDevice({
  loadMicroPython, keys: new Int32Array(16), heapsize: 2 * 1024 * 1024,
  files: { ...readWorkspace(), "console_test.py": t("console_test.py") }, shims: readShims(),
  onStdout: (l) => { if (/Traceback|Error/.test(l)) console.log(l); },
});
const py = (code) => dev.mp.runPython(code);
const shots = [];

function cap(img, ow, k, cx, cy) {
  const grey = [150, 150, 156, 255];
  for (let y = cy - 12; y <= cy + 12; y++) for (let x = cx - 12; x <= cx + 12; x++) {
    const dx = x - cx, dy = y - cy;
    const on = k === 0 ? Math.abs(dx) <= 9 && Math.abs(dy) <= 9
      : k === 1 ? dx * dx + dy * dy <= 100
      : dy >= -10 && dy <= 9 && Math.abs(dx) <= (dy + 10) / 2;
    if (on) img.set(grey, (y * ow + x) * 4);
  }
}

function shot(name, caption) {
  name = String(shots.length + 1).padStart(2, "0") + "-" + name;
  py(`import binascii\n_hex = binascii.hexlify(FULL).decode()`);
  const screen = scaleRGBA(frameToRGBA(Buffer.from(dev.mp.globals.get("_hex"), "hex")), W, H, S);
  const ow = W * S, oh = H * S + EDGE;
  const img = new Uint8ClampedArray(ow * oh * 4);
  img.set(screen, 0);
  for (let i = H * S * ow * 4; i < img.length; i += 4) img.set([24, 24, 28, 255], i);
  const sw = Math.floor((W - 8) / 3);
  for (let k = 0; k < 3; k++) cap(img, ow, k, Math.round((2 + k * (sw + 2) + sw / 2) * S), H * S + EDGE / 2);
  writeFileSync(join(out, `${name}.png`), encodePNG(ow, oh, img));
  shots.push([name, caption]);
  console.log("shot", name);
}

py(`with open("secrets.py", "w") as f:
    f.write('BOARD = "console-rp"\\n')
import sys
for m in ("board", "lcd", "fonts", "quorum_ui", "quorum_ui_s", "quorum_ui_crt", "crt", "splash", "bootmark"):
    sys.modules.pop(m, None)
import console_test as T, board, lcd as L
T.THREE_BOARD[0] = "console-rp"
T.chip(counter=7)
Q = T.fresh(relay=T.Relay())
import quorum_ui_crt, crt
crt.FX = False
Q.U = U = quorum_ui_crt
U.use("dark")
assert board.BOARD == "console-rp" and (L.W, L.H) == (240, 135) and Q.NET.KIND == "link", board.BOARD
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
Q.state, Q.msg, Q.tab = "home", "", 0
draw()`);
shot("home", "Home: four tabs, the Queue first. The footer names what each button under the screen does here: D0 ■ the next tab, D1 ● down the list, D2 ▲ what the bar above it says. A tab arrives with a short tear.");
py(`Q.tab = 1\ndraw()`);
shot("home-owners", "The Owners tab.");
py(`Q.tab = 2\ndraw()`);
shot("home-key", "The Key tab: this key's picture, fingerprint and owner address.");
py(`Q.tab = 3\ndraw()`);
shot("home-device", "The Device tab. No Wi-Fi row: console-rp has no radio; the computer on its USB-C relays.");
py(`Q.tab = 0\nQ.open_entry(Q.queue[0])\ndraw()`);
shot("review-head", "A transaction opens with a tear. D0 ■ rejects with one press on any page, D1 ● is the next page, D2 ▲ shows the next one not yet seen.");
py(`page("item")\ndraw()`);
shot("review-item", "What it does. A page turn is a short tear.");
py(`page("to")\ndraw()`);
shot("review-to", "Who it goes to, in full, and its blockie.");
py(`page("approvals")\ndraw()`);
shot("review-approvals", "Who has approved.");
py(`page("verify")\ndraw()`);
shot("review-verify", "The code to compare with the proposer. It was worked out here, so it locks in (FX3).");
py(`page("hash")\ndraw()`);
shot("review-hash", "The whole Safe transaction hash. Every page seen: D2 ▲ says Sign.");
py(`import quorum_ui_s as S\nQ.state, Q.hold_t0 = "hold", S.time.ticks_ms() - 1200     # the clock the page reads (Q.time is the test's)\ndraw()`);
shot("hold", "D2 ▲ held: its slot fills, 2 s. No effect while it fills. D0 ■ still rejects.");
py(`Q.state = "review"\nQ.open_entry(Q.queue[1])\ndraw()`);
shot("red-head", "An unknown call: red. It arrives with a strong tear, then stays red and still. Sign takes 3 s.");
py(`page("calldata")\ndraw()`);
shot("red-calldata", "Its function selector and calldata size, on a red page.");
py(`Q.state = "review"\nQ.open_entry(Q.queue[2])\ndraw()`);
shot("refused", "A hash the fields don't produce: refused, from the relay as from the service.");
py(`Q.msg = ""
Q.state, Q.result = "result", (True, "Signed", ["Posted through the relay", "2 of 2: ready to execute", "Key use #8"])
Q.unsent = None
draw()`);
shot("result-signed", "Signed and posted: it locks in. D2 ▲ OK.");
py(`Q.state, Q.result = "result", (False, "Not sent", ["Signed, but the relay said:", "relay: no answer"])
Q.unsent = (Q.queue[0], "0x00")
draw()
Q.unsent = None`);
shot("result-unsent", "Signed but not sent (the relay stopped): D2 ▲ sends it again, D0 ■ goes back.");
py(`Q.state = "device"\ndraw()`);
shot("device", "Device: the chip, its slot and key, the pin, uses, memory.");
py(`Q.open_key("home")\ndraw()`);
shot("key-code", "Key: the app's set-up link as a QR code, over the footer's left. It locks in.");
py(`Q.kpage = 1\ndraw()`);
shot("key-full", "The owner address in full.");
dev.dispose();

const md = ["# The console on console-rp", "",
  "Written by `node tools/board/shots_rp.mjs`: the real firmware on the emulator, 240 × 135, its three",
  "buttons under the screen (the grey caps below it: D0 ■, D1 ●, D2 ▲, as on the case). The screens",
  "are `quorum_ui_s`'s pages in the CRT look (`firmware/quorum_ui_crt.py`, `firmware/crt.py`). Each shot",
  "is the page once its effect has played. The effects are on the board only:",
  "- **tear** (FX1): something arrives or changes. Opening a transaction, a new one on home, a tab.",
  "  Strong for a red page, short for a page turn.",
  "- **lock** (FX3): worked out here and checked. The verify code, the key's code, Signed.",
  "- None on a redraw, and none while Sign is held. Any press stops an effect and still counts.", "",
  "The board is [hardware/console-rp](../../../hardware/console-rp/). Its way out is the relay on the",
  "computer ([tools/relay](../../../tools/relay/README.md)).", ""];
for (const [n, c] of shots) md.push(`### ${n.replace(/^\d+-/, "").replace(/-/g, " ")}`, "", c, "", `![${n}](${n}.png)`, "");
writeFileSync(join(out, "README.md"), md.join("\n"));
console.log(`${shots.length} shots in ${out}`);
