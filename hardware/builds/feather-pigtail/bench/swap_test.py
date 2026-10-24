"""swap.py on the laptop: each screen drawn against a stand-in of the Feather and the emulator's
virtual ATECC608 (emu/core/shims/atecc_sim.py) on its bus, with keys swapped between scans. Checks
what each screen says, that every line fits 240 x 135, and that a scan sends the chip only reads:
no Write, Lock, Nonce or Sign, and GenKey only in its public-key mode. Not a board.
    python3 hardware/builds/feather-pigtail/bench/swap_test.py"""
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
        assert (sda.id, scl.id) == (3, 4), (sda.id, scl.id)

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


machine = types.ModuleType("machine")
machine.Pin, machine.SPI, machine.SoftI2C, machine.I2C = Pin, SPI, SoftI2C, SoftI2C
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
sys.path[:0] = [str(HERE), str(ROOT / "hardware/wiring/feather-s3"), str(ROOT / "firmware"), str(ROOT / "emu/core/shims")]
import tft
_text = tft.text


def text(s, x, y, c, k=2):        # tft.text draws k > 1 glyph by glyph; record the line instead
    lines.append((x, y, k, s))
    _text(s, x, y, c, 1)
    lines.pop()


tft.text = text
import atecc_sim
import swap
swap.text = text


def shown():
    return " | ".join(s for _x, _y, _k, s in lines)


def fits():
    return all(0 <= x and x + 8 * k * len(s) <= 240 and 0 <= y and y + 8 * k <= 135 for x, y, k, s in lines)


def overlap():
    boxes = [(x, y, x + 8 * k * len(s), y + 8 * k) for x, y, k, s in lines]
    return any(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
               for i, a in enumerate(boxes) for b in boxes[i + 1:])


def plug(serial, sealed):
    """A different key in the plug: a fresh chip with its own serial, or one through the ceremony."""
    atecc_sim._chip = None
    atecc_sim.present = True
    atecc_sim.wipe("608c")
    atecc_sim.chip().cfg[8:13] = bytes.fromhex(serial)
    if sealed:
        atecc_sim.provision_v1()


def screen(what, fn):
    sent.clear()
    fn()
    check(fits(), what + ": every line fits 240 x 135")
    check(not overlap(), what + ": no two lines overlap")
    bad = [s for s in sent if s[0] in (0x12, 0x17, 0x16, 0x41) or (s[0] == 0x40 and s[1] != 0)]
    check(not bad, what + ": only reads sent to the chip" + (" (got %r)" % bad if bad else ""))
    return shown()


def scanned(what):
    swap.busy()
    return screen(what, lambda: (swap.scan(), swap.summary()))


plug("aabbccddee", sealed=True)
s = scanned("a sealed key")
check("NEW KEY" in s and "608C" in s and "quorum-v1" in s, "sealed key: NEW KEY, 608C, quorum-v1")
check("config locked  data locked" in s, "sealed key: both zones locked")
import p256
fp = "%08x" % (p256.pubkey(atecc_sim.chip().keys[0])[0] >> 224)
check("slot 0  " + fp in s, "sealed key: slot 0's fingerprint, %s" % fp)
check((0x40, 0) in sent and (0x02, 0x80) in sent, "sealed key: the scan read the config and slot 0's public key")
check("36=gauge" in s and "60=key" in s, "sealed key: the gauge and the key named")

s = scanned("the same key again")
check("SAME KEY" in s, "the same key read again: SAME KEY")

s = screen("the slot table", swap.slot_table)
row0 = next(t for _x, _y, _k, t in lines if t.startswith(" 0 "))
check(row0.startswith(" 0 P256 L"), "slot table: slot 0 is a locked P-256 key (%r)" % row0)

s = screen("back", swap.summary)
check("SAME KEY" in s, "D0: back to the summary")

plug("1122334455", sealed=False)
s = scanned("a fresh key")
check("NEW KEY" in s and "config open  data open" in s, "fresh key: NEW KEY, both zones open")
check("no key in slot 0" in s, "fresh key: no key in slot 0")
check("1122334455" in s, "fresh key: its own serial")

atecc_sim.present = False
s = scanned("no key")
check("NO KEY" in s and "i2c 36=gauge" in s, "unplugged: NO KEY, the gauge still answers")
s = screen("slots with no key", swap.slot_table)
check("NO KEY" in s, "D1 with no key: the summary")

plug("aabbccddee", sealed=True)
s = scanned("the first key back")
check("NEW KEY" in s, "the first key back after another: NEW KEY (it differs from the last one read)")

src = (HERE / "swap.py").read_text()
calls = [c for c in ("sign(", "genkey_new", "genkey_attest", "write_", "lock_", "random(", "selftest(") if "." + c in src]
check(not calls, "swap.py calls no sign, genkey, write, lock, random or selftest" + (" (%s)" % calls if calls else ""))

print("\n%s" % ("all passed" if not failed else "%d FAILED" % failed))
sys.exit(1 if failed else 0)
