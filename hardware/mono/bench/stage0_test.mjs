// stage0.py run whole on the emulator's MicroPython (the board's own 1.26), against a model of Mono:
// VKEY follows GPIO7 and KEY 2's bus follows VKEY, I2C1 is empty, the keys and the link follow a
// script, and time is counted, not waited for. It checks the lines stage0 sends down the link and
// the frame the emulator's ST7789 takes from its SPI stream, and writes that frame to stage0.png,
// the picture BRINGUP.md shows. No board: what a real Mono does is BRINGUP.md's to find out.
//   (cd emu && npm ci) && node hardware/mono/bench/stage0_test.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadMicroPython } from "../../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "../../../emu/core/runtime.mjs";
import { readShims } from "../../../emu/core/workspace.mjs";
import { encodePNG, scaleRGBA } from "../../../emu/core/png.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const W = 240, H = 135;

// The model. fault: "" a good board; "vkey" KEY 2's switch never turns on and no key answers on I2C0.
const MODEL = `
import machine, time, atecc_sim
FAULT = %FAULT%
VKEY, CLOCK, LOOPS, SAID = [0], [0], [0], []
HELD = {3: (10, 15)}                    # GPIO -> the loops it is held for: D1, once
HEARS = {30: b"hello\\r\\n", 40: b"fac", 41: b"ts\\r\\n"}     # the loop each piece arrives in: facts in two reads
def _sleep(ms):
    CLOCK[0] += ms
time.sleep_ms = _sleep
time.ticks_ms = lambda: CLOCK[0]
atecc_sim.present = not FAULT

class Done(BaseException):
    pass

class Pin(machine.Pin):
    def __init__(self, id, mode=-1, pull=-1, value=None, **kw):
        super().__init__(id, mode, pull, value)
        if id == 7:
            VKEY[0] = 1 if mode == machine.Pin.OUT and value and not FAULT else 0
    def value(self, v=None):
        if self.id == 7 and v is not None:
            VKEY[0] = 1 if v and not FAULT else 0
        if v is None and self.id in (14, 15):
            return VKEY[0]
        if v is None and self.id in HELD:
            a, b = HELD[self.id]
            return 0 if a <= LOOPS[0] < b else 1
        return super().value(v)
    def __call__(self, v=None):
        return self.value(v)

class I2C(machine.I2C):
    def scan(self):
        return [] if self.id == 1 else super().scan()

class UART:
    def __init__(self, *a, **k):
        pass
    def write(self, b):
        SAID.append(bytes(b, "utf8") if isinstance(b, str) else bytes(b))
    def any(self):                      # once a loop
        LOOPS[0] += 1
        if LOOPS[0] > 130:
            raise Done()
        return len(HEARS.get(LOOPS[0], b""))
    def read(self, n):
        return HEARS[LOOPS[0]]

machine.Pin, machine.I2C, machine.UART = Pin, I2C, UART
try:
    exec(open("stage0.py").read(), {"__name__": "stage0"})
except Done:
    pass
import binascii
OUT = binascii.hexlify(b"".join(SAID)).decode()
`;

async function run(fault) {
  let frame = null;
  const dev = await createDevice({
    loadMicroPython, keys: new Int32Array(16), board: "console-rp",
    files: { "stage0.py": readFileSync(join(HERE, "stage0.py"), "utf8") }, shims: readShims(),
    onStdout: (l) => { if (/Traceback|Error/.test(l)) { console.log(l); process.exitCode = 1; } },
    onFrame: (f) => { frame = Uint8Array.from(f); },
  });
  dev.mp.runPython(MODEL.replace("%FAULT%", JSON.stringify(fault)));
  const said = Buffer.from(dev.mp.globals.get("OUT"), "hex").toString("latin1").split("\r\n");
  dev.dispose();
  return { said, frame };
}

let failed = 0;
function check(what, ok) {
  console.log((ok ? "ok    " : "FAIL  ") + what);
  if (!ok) failed++;
}
const px = (f, x, y) => (f[(y * W + x) * 2] << 8) | f[(y * W + x) * 2 + 1];

const good = await run("");
const facts = good.said.filter((l) => l.startsWith("fact: ") || l.startsWith("FAIL: "));
console.log(good.said.join("\n"));
check("nine facts at the start, then nine again when asked", facts.length === 18 && good.said.filter((l) => l === "facts: 9").length === 2);
check("no fault on a good board", !facts.some((l) => l.startsWith("FAIL:")));
check("the key is read: revision, serial, both zones open",
  facts.some((l) => /^fact: ATECC608 rev [0-9a-f]{8}$/.test(l)) && facts.some((l) => /^fact: serial 0123[0-9a-f]{12}ee$/.test(l)) &&
  facts.includes("fact: data open, config open"));
check("KEY 2: off 00, on 11, I2C1 empty", facts.includes("fact: KEY 2: off 00 on 11, empty"));
check("what isn't `facts` is sent back", good.said.includes("heard: hello"));
check("the 2 s line carries D1's press", good.said.includes("Mono bring-up 1: D0 0 D1 1 D2 0"));
check("a whole frame through the window at column 40, row 53", good.frame && good.frame.length === W * H * 2);
check("the white frame on all four edges", [[0, 0], [W - 1, 0], [0, H - 1], [W - 1, H - 1], [120, 0], [120, H - 1], [0, 67], [W - 1, 67]]
  .every(([x, y]) => px(good.frame, x, y) === 0xffff));

const bad = await run("vkey");
check("a dead VKEY switch is a FAIL line", bad.said.includes("FAIL: KEY 2: off 00 on 00, not scanned"));
check("no key on I2C0 is a FAIL line", bad.said.includes("FAIL: no ATECC608 at 60"));

if (!failed) {
  const S = 3;
  writeFileSync(join(HERE, "stage0.png"), encodePNG(W * S, H * S, scaleRGBA(frameToRGBA(good.frame), W, H, S)));
  console.log("wrote stage0.png");
}
process.exit(failed || process.exitCode ? 1 : 0);
