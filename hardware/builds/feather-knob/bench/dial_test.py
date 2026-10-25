"""dial.py on the laptop: its screen drawn against a stand-in of the ESP32-S3 TFT Feather and the
emulator's virtual ATECC608 (emu/core/shims/atecc_sim.py), with the knob turned and pushed. Checks
the pins (the screen's power on 21, the key's bus on 42/41, the knob on 17/16/15), what the screen
says, that every line fits 240 x 135, and that only reads reach the chip. Not a board.
    python3 hardware/builds/feather-knob/bench/dial_test.py"""
from pathlib import Path
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
failed = 0


def check(ok, what):
    global failed
    print(("pass  " if ok else "FAIL  ") + what)
    failed += not ok


# ---- MicroPython on the S3, only what tft.py, atecc.py and swap.py call
class Pin:
    IN, OUT, PULL_UP, PULL_DOWN = 1, 3, 1, 2
    levels = {}

    def __init__(self, id, mode=None, pull=None, value=None):
        self.id = id
        if value is not None:
            Pin.levels[id] = value
        elif id not in Pin.levels:
            Pin.levels[id] = 0 if pull == Pin.PULL_DOWN else 1

    def value(self, v=None):
        if v is None:
            return Pin.levels[self.id]
        Pin.levels[self.id] = v
    __call__ = value


class SPI:
    def __init__(self, *a, **k):
        pass

    def write(self, b):
        pass


sent = []          # every command packet the chip got: (opcode, p1)
gauge = [True]


class SoftI2C:
    def __init__(self, sda, scl, freq=100_000):
        assert (sda.id, scl.id) == (42, 41), (sda.id, scl.id)

    def writeto(self, a, b):
        import atecc_sim
        if a == 0:
            if atecc_sim.present:
                atecc_sim.chip().wake_token()
            raise OSError(19, "ENODEV")      # the wake token is never ACKed
        if a != 0x60 or not atecc_sim.present:
            raise OSError(19, "ENODEV")
        if b[0] == 3:
            sent.append((b[2], b[3]))
        atecc_sim.chip().write(b)

    def readfrom(self, a, n):
        import atecc_sim
        if a != 0x60 or not atecc_sim.present:
            raise OSError(19, "ENODEV")
        return atecc_sim.chip().read(n)

    def scan(self):
        import atecc_sim
        return ([0x36] if gauge[0] else []) + ([0x60] if atecc_sim.present and atecc_sim.chip().awake else [])


class Encoder:      # the S3's pulse counter
    count = 0

    def __init__(self, unit, a, b, phases=1, filter_ns=0):
        assert (unit, a.id, b.id, phases) == (0, 17, 16, 4), (unit, a.id, b.id, phases)

    def value(self, v=None):
        r = Encoder.count
        if v is not None:
            Encoder.count = v
        return r


machine = types.ModuleType("machine")
machine.Pin, machine.SPI, machine.SoftI2C, machine.I2C, machine.Encoder = Pin, SPI, SoftI2C, SoftI2C, Encoder
sys.modules["machine"] = machine

lines = []         # what the screen shows: (x, y, scale, text)


class FrameBuffer:
    def __init__(self, buf, w, h, fmt):
        self.main = (w, h) == (240, 135)

    def fill(self, c):
        if self.main:
            lines.clear()

    def text(self, s, x, y, c=1):
        if self.main:
            lines.append((x, y, 1, s))

    def fill_rect(self, *a):
        pass

    def hline(self, *a):
        pass


framebuf = types.ModuleType("framebuf")
framebuf.FrameBuffer, framebuf.RGB565, framebuf.MONO_HLSB = FrameBuffer, 1, 2
sys.modules["framebuf"] = framebuf
emu = types.ModuleType("_emu")
emu.chip_load, emu.chip_save = (lambda: None), (lambda s: None)
sys.modules["_emu"] = emu
time.sleep_ms = lambda ms: None
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_diff = lambda a, b: a - b

# the bench's own files, as /bench has them: tft.py and the stand-in board.py, then the firmware's
sys.path[:0] = [str(HERE), str(ROOT / "hardware/builds/feather-knob/bench"), str(ROOT / "firmware"), str(ROOT / "emu/core/shims")]
import tft
_text = tft.text


def text(s, x, y, c, k=2):        # tft.text draws k > 1 glyph by glyph; record the line instead
    lines.append((x, y, k, s))
    _text(s, x, y, c, 1)
    lines.pop()


tft.text = text
import atecc_sim
import dial
dial.text = text
check(Pin.levels.get(21) == 1, "GPIO21 high: the screen and the key's bus have power")


def shown():
    return " | ".join(s for _x, _y, _k, s in lines)


def fits():
    return all(0 <= x and x + 8 * k * len(s) <= 240 and 0 <= y and y + 8 * k <= 135 for x, y, k, s in lines)


last = [(1, 1)]


def step(what, first=False):
    sent.clear()
    if first:
        dial.scan()
        dial.draw()
    else:
        last[0] = dial.tick(last[0])
    check(fits(), what + ": every line fits 240 x 135")
    bad = [s for s in sent if s[0] in (0x12, 0x17, 0x16, 0x41, 0x40)]
    check(not bad, what + ": only reads sent to the chip" + (" (got %r)" % bad if bad else ""))
    return shown()


atecc_sim._chip = None
atecc_sim.present = True
atecc_sim.wipe("608c")
s = step("start", first=True)
check("detents +0" in s and "608C" in s and "factory" in s, "start: no turns, the key read (%s)" % s)
check("i2c 36 60" in s, "start: the gauge and the key on the bus")
Encoder.count = 4
s = step("a detent")
check("detents +1" in s and "steps +4, last move +4" in s, "one detent clockwise: 4 steps, one detent")
Encoder.count = -12
s = step("three back")
check("detents -2" in s and "steps -8, last move -12" in s, "three detents back: -8 in all")
atecc_sim.present = False
Pin.levels[15] = 0
s = step("push, no key")
check("push DOWN" in s and "no key at 0x60" in s and "scan 2" in s, "the push scans again: no key now")
Pin.levels[15] = 1
step("let go")
atecc_sim.present = True
Pin.levels[0] = 0
s = step("Boot")
check("Boot DOWN" in s and "no key at 0x60" in s, "Boot shown held; it doesn't scan")
Pin.levels[0] = 1
src = (HERE / "dial.py").read_text()
calls = [c for c in ("sign(", "genkey", "write_", "lock_", "pubkey(") if "." + c in src]
check(not calls, "dial.py calls no sign, genkey, write, lock or pubkey" + (" (%s)" % calls if calls else ""))
print("\n%s" % ("all passed" if not failed else "%d FAILED" % failed))
sys.exit(1 if failed else 0)
