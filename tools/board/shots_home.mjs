// Screenshots of the console's home: the status screen (nothing waiting for this key), not an
// owner yet, others' transactions queued, the queue list when something waits, and the
// screensaver's cards, drawn by the real firmware on the emulator for both panels: the
// Waveshare's 240x240 and Build 1's 320x240. Each strip the console draws is copied into a whole
// frame (show() wrapped), so any panel size works. For docs/quorum-ui/v2/status/.
//   node tools/board/shots_home.mjs [outdir]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../emu/core/png.mjs";

const out = process.argv[2] || join(ROOT, "docs/quorum-ui/v2/status");
mkdirSync(out, { recursive: true });
const t = (f) => readFileSync(join(ROOT, "test-vectors", f), "utf8");
const PANELS = [{ name: "240", secrets: "", w: 240, h: 240 }, { name: "320", secrets: 'BOARD = "build1"\nSCREEN = "2.8"', w: 320, h: 240 }];

for (const p of PANELS) {
  const dev = await createDevice({
    loadMicroPython, keys: new Int32Array(16), heapsize: 2 * 1024 * 1024, secrets: p.secrets,
    files: { ...readWorkspace(), "console_test.py": t("console_test.py") }, shims: readShims(),
    onStdout: (l) => { if (/Traceback|Error/.test(l)) console.log(l); },
  });
  const py = (code) => dev.mp.runPython(code);
  const shot = (name) => {
    py(`import binascii\n_hex = binascii.hexlify(FULL).decode()`);
    const buf = Buffer.from(dev.mp.globals.get("_hex"), "hex");
    writeFileSync(join(out, `${name}-${p.name}.png`), encodePNG(p.w * 2, p.h * 2, scaleRGBA(frameToRGBA(buf), p.w, p.h, 2)));
    console.log("shot", `${name}-${p.name}`);
  };
  py(`import console_test as T, lcd as L, quorum_ui as U, sys
T.chip(counter=41)
Q = T.fresh(url=None, safe=False, extra=T.TWO)
T.SVC.info = {"address": T.SAFE, "nonce": 3, "threshold": 2, "version": "1.4.1", "owners": [Q.me, T.ALICE, T.BOB]}
T.SVC.txs = []
T.SVC.safes[T.ETH_SAFE] = {"info": {"address": T.ETH_SAFE, "nonce": 9, "threshold": 3, "version": "1.4.1",
                           "owners": [Q.me, T.ALICE, T.BOB, "0x3333333333333333333333333333333333333333", "0x4444444444444444444444444444444444444444"]}, "txs": []}
Q.net_work(); Q.net_work()
Q.state = "home"
FULL = bytearray(L.W * L.H * 2)
d = Q.d
def _show():
    n = len(d.buffer) // (2 * L.W)
    FULL[d.y0 * L.W * 2:(d.y0 + n) * L.W * 2] = d.buffer
d.show = _show
def draw():
    Q.dirty = False
    d.frames(U.draw, Q)
now = U.time.time()
Q.recent = [{"n": 8, "safe": T.ETH_SAFE.lower(), "chain": 1, "name": "Vault", "what": "Send 0.05 ETH", "t": now - 320},
            {"n": 2, "safe": T.SAFE.lower(), "chain": T.CHAIN, "name": "Test Safe", "what": "Batch: approve, swap", "t": now - 3 * 3600},
            {"n": 1, "safe": T.SAFE.lower(), "chain": T.CHAIN, "name": "Test Safe", "what": "Send 10 USDC", "t": now - 2 * 86400}]
import image
draw()`);
  shot("01-ready");
  py(`Q.hsel = 1\ndraw()`);
  shot("02-safe-in-focus");
  py(`Q.KNOB = True\nQ.hsel, Q.hfoot = 1, "recent"\ndraw()\nQ.KNOB, Q.hfoot, Q.hsel = False, None, 0`);
  shot("03-dial");
  py(`Q.sig.name = "passkey"      # as the browser console runs it: your passkey, not yet added
_own = (T.SVC.info["owners"], T.SVC.safes[T.ETH_SAFE]["info"]["owners"])
T.SVC.info["owners"] = [T.ALICE, T.BOB]
T.SVC.safes[T.ETH_SAFE]["info"]["owners"] = [T.ALICE, T.BOB, "0x3333333333333333333333333333333333333333"]
for w in Q.WATCH: w["need_info"] = True
Q.net_work(); Q.net_work()
draw()`);
  shot("04-passkey-not-owner-yet");
  py(`T.SVC.info["owners"], T.SVC.safes[T.ETH_SAFE]["info"]["owners"] = _own
for w in Q.WATCH: w["need_info"] = True
T.SVC.txs = [T.tx(Q, 3, value=10**15, conf=(Q.me,))]
Q.last_poll = 0
Q.net_work(); Q.net_work()
draw()`);
  shot("05-queued-for-others");
  py(`Q.sig.name = "atecc608"
T.SVC.txs = [T.tx(Q, 3, value=10**15)]
Q.WATCH[0]["need_info"] = True
Q.last_poll = 0
Q.net_work(); Q.net_work()
draw()`);
  shot("06-request-waiting");
  py(`T.SVC.txs = []
Q.WATCH[0]["need_info"] = True
Q.last_poll = 0
Q.net_work(); Q.net_work()
image.RELEASE = "4c86c7541a45eb43f24c48c178409de889c5f86d467c886d444e9e30b9a00e0b"
image.SEED, image.SHORT, image.VERSION, image.BUILD = "0x" + image.RELEASE, "4c86\u00b7c754", "2026.10.6", "abc1234"
Q.state = "saver"
_cards = [k for k, _ in Q.saver_cards()]
assert _cards == ["clock", "safe", "safe", "key", "recent", "release"], _cards`);
  for (const [i, n] of [[0, "clock"], [1, "safe"], [3, "key"], [4, "recent"], [5, "release"]]) {
    py(`Q.saver_card = ${i}\ndraw()`);
    shot(`${String(7 + [0, 1, 3, 4, 5].indexOf(i)).padStart(2, "0")}-saver-${n}`);
  }
  dev.dispose();
}
