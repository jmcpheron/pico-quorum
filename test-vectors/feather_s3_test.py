"""The Feather ESP32-S3 Reverse TFT's paths on the laptop: board.py's "feather-s3" profile, its screen
at (40, 53) in the panel's RAM, its three buttons (D0 pulled up, D1 and D2 pulled down; D1 held is
"D1L"), and the battery gauge at 0x36 never taken for the key. MicroPython is a stand-in, as in
esp32_test.py, with the S3's pins (0-21, 26-48) and os.uname() naming the S3. Then the same for
PicoQuorumKey ("picoquorum-key"), the S3 with pull-ups on GPIO16/17, and for the ESP32-S3 TFT
Feather with a knob ("feather-knob", hardware/builds/feather-knob): Boot and the knob as the three
keys. Not a board: hardware/wiring/FEATHER-S3.md says what has run on one.
    python3 test-vectors/feather_s3_test.py"""
from pathlib import Path
import os
import re
import sys
import types
from unittest.mock import patch

FW = Path(__file__).resolve().parents[1] / "firmware"
failed = 0
log = []
clock = [0]


def check(ok, what):
    global failed
    print(("pass  " if ok else "FAIL  ") + what)
    failed += not ok


# ---- MicroPython 1.26 on an ESP32-S3, only what these paths call
class Pin:
    IN, OUT, PULL_UP, PULL_DOWN = 1, 3, 1, 2
    levels = {}
    pulls = {}

    def __init__(self, id, mode=None, pull=None, value=None):
        if not isinstance(id, int) or not (0 <= id <= 21 or 26 <= id <= 48):
            raise ValueError("invalid pin")
        assert not 26 <= id <= 32, "GPIO%d is the module's flash" % id
        self.id = id
        if value is not None:
            Pin.levels[id] = value
        Pin.pulls[id] = pull

    def value(self, v=None):
        if v is None:
            return Pin.levels.get(self.id, 0 if Pin.pulls.get(self.id) == Pin.PULL_DOWN else 1)
        Pin.levels[self.id] = v
    __call__ = value

    def on(self):
        Pin.levels[self.id] = 1

    def off(self):
        Pin.levels[self.id] = 0


class SPI:
    def __init__(self, id, baudrate=-1, *, polarity=-1, phase=-1, sck=None, mosi=None, miso=None):
        assert id in (1, 2), id
        log.append(("SPI", id, baudrate, sck.id, mosi.id))

    def write(self, b):
        log.append(("w", bytes(b[:8]) if len(b) > 8 else bytes(b), len(b)))


class PWM:
    def __init__(self, pin, freq=None, duty_u16=None):
        log.append(("PWM", pin.id))

    def freq(self, f):
        pass

    def duty_u16(self, d):
        pass


class SoftI2C:
    answers = [0x36]

    def __init__(self, sda, scl, freq=400000):
        log.append(("SoftI2C", sda.id, scl.id))

    def writeto(self, a, b):
        raise OSError(19)

    def readfrom(self, a, n):
        raise OSError(19)

    def scan(self):
        return list(SoftI2C.answers)


class Encoder:      # the S3's pulse counter, as esp32_test.py has it
    def __init__(self, unit_id, phase_a, phase_b, *, phases=1, filter_ns=0):
        log.append(("Encoder", unit_id, phase_a.id, phase_b.id, phases))
        self.count = 0

    def value(self, value=None):
        r = self.count
        if value is not None:
            self.count = value
        return r


class FrameBuffer:
    def __init__(self, buf, w, h, fmt):
        self.size = (len(buf), w, h)


machine = types.SimpleNamespace(Pin=Pin, SPI=SPI, PWM=PWM, SoftI2C=SoftI2C, I2C=SoftI2C, Encoder=Encoder,
                                disable_irq=lambda: 0, enable_irq=lambda s: None)
mptime = types.SimpleNamespace(
    time=lambda: 0, gmtime=lambda t=None: (2000, 1, 1, 0, 0, 0, 5, 1),
    ticks_ms=lambda: clock[0], ticks_diff=lambda a, b: a - b, ticks_add=lambda a, b: a + b,
    sleep_ms=lambda ms: None, sleep_us=lambda us: None)
mods = {"machine": machine, "time": mptime,
        "framebuf": types.SimpleNamespace(FrameBuffer=FrameBuffer, RGB565=1, MONO_HLSB=0),
        "secrets": types.SimpleNamespace()}


def sent(cmd):
    """The data bytes of every command `cmd` sent to the panel, in order."""
    out = []
    w = [e for e in log if e[0] == "w"]
    for i, e in enumerate(w[:-1]):
        if e[1] == bytes([cmd]):
            out.append(w[i + 1][1])
    return out


platform, cwd = sys.platform, os.getcwd()
sys.path.insert(0, str(FW))
os.chdir(FW)
sys.platform = "esp32"
try:
    with patch.dict(sys.modules, mods), \
         patch("os.uname", lambda: types.SimpleNamespace(machine="Generic ESP32S3 module with ESP32S3")):
        import board
        check(board.S3 and board.BOARD == "feather-s3" and board.THREE and not board.KNOB and not board.DIAL,
              "an ESP32-S3 is the Feather: three buttons, no knob")
        check(board.NAMES == {"D0": "D0", "D1": "D1", "D2": "D2"}, "the screens name D0, D1, D2")
        check((board.DC, board.CS, board.SCK, board.MOSI, board.RST, board.BL) == (40, 42, 36, 35, 41, 45),
              "the screen's pins")
        check((board.SPI_ID, board.SPI_BAUD, board.SDA, board.SCL, board.LED) == (1, 40_000_000, 3, 4, 13),
              "SPI(1) at 40 MHz, the key's bus on 3/4, the LED on 13")
        check((board.W, board.H, board.PANEL_W, board.PANEL_H, board.BANDS, board.SMALL) == (240, 135, 240, 135, 1, True),
              "240x135 drawn whole, the small screens' UI")
        check((board.MADCTL, board.RAM_X, board.RAM_Y, board.X_OFF, board.Y_OFF) == (0x60, 40, 53, 0, 0),
              "landscape, buttons on the left, the picture at (40, 53) in the panel's RAM")
        check(board.BUTTONS == {"D0": 0, "D1": 1, "D2": 2} and board.HIGH == (1, 2),
              "D0, D1, D2; D1 and D2 pressed high")
        check((board.MAINT, board.SETUP) == (1, 2), "maintenance on D1, Wi-Fi setup on D2: never D0, the BOOT strap")
        check(board.RAIL_Y == (7, 67, 127), "the rows level with D0, D1, D2")
        check(Pin.levels.get(7) == 1, "GPIO7 high on import: the screen and the key's bus have power")

        import lcd
        del log[:]
        lcd.LCD()
        check(("SPI", 1, 40_000_000, 36, 35) in log and ("PWM", 45) in log, "the screen on SPI(1), the backlight on 45")
        check(len(lcd._BUF) == 240 * 135 * 2, "one 64,800-byte frame")
        check(sent(0x36) == [bytes([0x60])] and bytes([0x21]) in [e[1] for e in log if e[0] == "w"],
              "the plain ST7789 start: MADCTL 0x60, inversion on")
        del log[:]
        d = lcd.LCD.__new__(lcd.LCD)
        d.cs, d.dc, d.y0 = Pin(42), Pin(40), 0
        d.spi, d.buffer = SPI(1, sck=Pin(36), mosi=Pin(35)), lcd._BUF
        d.show()
        check(sent(0x2A) == [bytes([0, 40, 1, 23])] and sent(0x2B) == [bytes([0, 53, 0, 187])],
              "show() windows columns 40-279 and rows 53-187")

        Pin.levels.clear()
        keys = lcd.Keys()
        check(Pin.pulls[0] == Pin.PULL_UP and Pin.pulls[1] == Pin.PULL_DOWN and Pin.pulls[2] == Pin.PULL_DOWN,
              "D0 pulled up, D1 and D2 pulled down")
        check(keys.pressed() == [], "at rest: nothing pressed")
        Pin.levels[0] = 0
        check(keys.pressed() == ["D0"] and keys.held("D0"), "D0 reads low pressed")
        Pin.levels[0] = 1
        Pin.levels[2] = 1
        check(keys.pressed() == ["D2"] and keys.held("D2"), "D2 reads high pressed")
        Pin.levels[2] = 0
        check(keys.pressed() == [] and not keys.held("D2"), "D2 let go")
        Pin.levels[1] = 1
        check(keys.pressed() == [], "D1 down: nothing yet")
        clock[0] += 200
        Pin.levels[1] = 0
        check(keys.pressed() == ["D1"], "D1 let go within a second: D1")
        Pin.levels[1] = 1
        keys.pressed()
        clock[0] += 999
        check(keys.pressed() == [], "D1 held 999 ms: nothing")
        clock[0] += 1
        check(keys.pressed() == ["D1L"], "D1 held 1 s: D1L")
        clock[0] += 499
        check(keys.pressed() == [], "then nothing for 499 ms")
        clock[0] += 1
        check(keys.pressed() == ["D1L"], "and D1L again every 500 ms")
        Pin.levels[1] = 0
        check(keys.pressed() == [], "let go after a long press: no D1")

        Pin.levels.clear()
        check(not board.key_down(1) and Pin.pulls[1] == Pin.PULL_DOWN, "key_down: D1 at rest, read with its pull-down")
        Pin.levels[1] = 1
        check(board.key_down(1), "key_down: D1 held")
        Pin.levels[0] = 0
        check(board.key_down(0) and Pin.pulls[0] == Pin.PULL_UP, "key_down: D0 held, read with a pull-up")
        Pin.levels.clear()

        import atecc
        SoftI2C.answers = [0x36]
        check(0x36 in atecc.KNOWN_ADDRS and 0x36 not in atecc.KEY_ADDRS, "0x36 is never a key here")
        check(atecc.ATECC608().addr == 0x60, "the gauge alone on the bus: the driver still asks 0x60, never 0x36")
        SoftI2C.answers = [0x36, 0x60]
        check(atecc.ATECC608().addr == 0x60, "the gauge and a key: the key")
        sys.modules["image"] = types.SimpleNamespace(PRODUCTION=True)
        import signer
        SoftI2C.answers = [0x36]
        check(signer.detect() == [], "detect(): the gauge alone is no chip")
        SoftI2C.answers = [0x36, 0x60]
        check(signer.detect() == [("atecc608", 0x60)], "detect(): the key at 0x60 beside the gauge")
finally:
    sys.platform = platform
    os.chdir(cwd)
    sys.path.remove(str(FW))
    sys.modules.pop("image", None)

# PicoQuorumKey: the same S3 with 4.7k pull-ups on GPIO16/17, its key's bus. The Feather's screen,
# buttons and rail on its own pins, every button pulled up and pressed low, nothing to power up.
del log[:]
Pin.levels.clear()
Pin.pulls.clear()
Pin.levels.update({16: 1, 17: 1})
sys.path.insert(0, str(FW))
os.chdir(FW)
sys.platform = "esp32"
try:
    with patch.dict(sys.modules, mods), \
         patch("os.uname", lambda: types.SimpleNamespace(machine="Generic ESP32S3 module with ESP32S3")):
        import board
        check(board.BOARD == "picoquorum-key" and board.THREE and not board.KNOB,
              "an S3 with 16/17 pulled up is PicoQuorumKey: three buttons, no knob")
        check(Pin.pulls[16] is None and Pin.pulls[17] is None, "16/17 left with no pull after the look")
        check((board.DC, board.CS, board.SCK, board.MOSI, board.RST, board.BL) == (9, 10, 12, 11, 14, 21),
              "the screen's pins")
        check((board.SPI_ID, board.SPI_BAUD, board.SDA, board.SCL, board.LED) == (1, 40_000_000, 16, 17, 48),
              "SPI(1) at 40 MHz, the key's bus on 16/17, the LED on 48")
        check((board.W, board.H, board.BANDS, board.MADCTL, board.RAM_X, board.RAM_Y, board.RAIL_Y)
              == (240, 135, 1, 0x60, 40, 53, (7, 67, 127)), "the Feather's panel, picture and rail")
        check(board.BUTTONS == board.KEYS == {"D0": 42, "D1": 41, "D2": 40} and board.HIGH == (),
              "D0, D1, D2 on 42, 41, 40, all pressed low")
        check((board.MAINT, board.SETUP, board.POWER, board.NOT_KEYS) == (41, 40, None, ()),
              "maintenance on D1, Wi-Fi setup on D2; no power pin, nothing else on the key's bus")
        check(7 not in Pin.levels, "GPIO7 left alone")

        import lcd
        del log[:]
        lcd.LCD()
        check(("SPI", 1, 40_000_000, 12, 11) in log and ("PWM", 21) in log, "the screen on SPI(1), the backlight on 21")
        Pin.levels.clear()
        keys = lcd.Keys()
        check(all(Pin.pulls[n] == Pin.PULL_UP for n in (42, 41, 40)), "D0, D1, D2 pulled up")
        check(keys.pressed() == [], "at rest: nothing pressed")
        for k, n in (("D0", 42), ("D2", 40)):
            Pin.levels[n] = 0
            check(keys.pressed() == [k] and keys.held(k), k + " reads low pressed")
            Pin.levels[n] = 1
            check(keys.pressed() == [] and not keys.held(k), k + " let go")
        check(not board.key_down(41) and Pin.pulls[41] == Pin.PULL_UP, "key_down: D1 at rest, read with its pull-up")
        Pin.levels[41] = 0
        check(board.key_down(41), "key_down: D1 held")

        import atecc
        check((atecc.SDA, atecc.SCL) == (16, 17) and 0x36 in atecc.KEY_ADDRS, "the key's bus on 16/17; 0x36 may be a key here")
finally:
    sys.platform = platform
    os.chdir(cwd)
    sys.path.remove(str(FW))

# The ESP32-S3 TFT Feather with a knob (hardware/builds/feather-knob): only when secrets.BOARD
# names it. Its own pins, Boot as D0 and the knob as D1, D1L and D2.
for name in ("board", "lcd", "knob", "atecc", "signer"):
    sys.modules.pop(name, None)
Pin.levels.clear()
Pin.pulls.clear()
Pin.levels.update({16: 1, 17: 1})           # its knob's B and A at rest, pulled up: not PicoQuorumKey's bus
del log[:]
sys.path.insert(0, str(FW))
os.chdir(FW)
sys.platform = "esp32"
try:
    with patch.dict(sys.modules, dict(mods, secrets=types.SimpleNamespace(BOARD="feather-knob"))), \
         patch("os.uname", lambda: types.SimpleNamespace(machine="Generic ESP32S3 module with ESP32S3")):
        import board
        check(board.BOARD == "feather-knob" and board.THREE and board.DIAL and not board.KNOB,
              "knob: secrets.BOARD picks it on an S3; the Feather's screens, no big-screen knob")
        check(16 not in Pin.pulls and 17 not in Pin.pulls,
              "knob: the secret comes first, so 16/17 (its knob) are never probed for PicoQuorumKey")
        check((board.DC, board.CS, board.SCK, board.MOSI, board.RST, board.BL) == (39, 7, 36, 35, 40, 45),
              "knob: the 5483's screen pins")
        check((board.SDA, board.SCL, board.LED, board.POWER) == (42, 41, 13, 21),
              "knob: the key's bus on SDA/SCL (42/41), the LED on 13, power on 21")
        check(Pin.levels.get(21) == 1 and 7 not in Pin.levels, "knob: GPIO21 high on import, GPIO7 (its screen's CS) left alone")
        check((board.W, board.H, board.BANDS, board.SMALL, board.MADCTL, board.RAM_X, board.RAM_Y) == (240, 135, 1, True, 0x60, 40, 53),
              "knob: the same 240x135 screen, drawn whole")
        check(board.BUTTONS == {"D0": 0} and board.HIGH == () and board.KEYS == {"D0": 0}, "knob: Boot is D0, the only button")
        check((board.ENC_A, board.ENC_B, board.ENC_SW) == (17, 16, 15), "knob: A on A1, B on A2, the push on A3")
        check(board.MAINT == board.SETUP == 15, "knob: the push held at power-up is maintenance, never Boot")
        check(board.NAMES == {"D0": "Boot", "D1": "turn", "D2": "push"}, "knob: the screens say Boot, turn, push")
        used = [board.DC, board.CS, board.SCK, board.MOSI, board.RST, board.BL, board.SDA, board.SCL, board.POWER,
                board.LED, board.ENC_A, board.ENC_B, board.ENC_SW, 0]
        check(len(set(used)) == len(used), "knob: no pin used twice")

        import lcd
        del log[:]
        lcd.LCD()
        check(("SPI", 1, 40_000_000, 36, 35) in log and sent(0x36) == [bytes([0x60])], "knob: the screen starts as feather-s3's")
        del log[:]
        keys = lcd.Keys()
        check(("Encoder", 0, 17, 16, 4) in log and keys.knob is not None, "knob: on the pulse counter, A 17, B 16")
        check(Pin.pulls[0] == Pin.PULL_UP and Pin.pulls[15] == Pin.PULL_UP, "knob: Boot and the push pulled up")
        check(keys.pressed() == [], "knob: at rest, nothing")
        keys.knob.enc.count = 4
        check(keys.pressed() == ["D1"], "knob: a detent clockwise is D1")
        keys.knob.enc.count = -8
        check(keys.pressed() == ["D1L", "D1L"], "knob: two detents back are D1L twice")
        Pin.levels[15] = 0
        keys.knob.since -= 1000
        check(keys.pressed() == ["D2"] and keys.held("D2"), "knob: the push is D2, held while down")
        Pin.levels[15] = 1
        keys.knob.since -= 1000
        check(keys.pressed() == [] and not keys.held("D2"), "knob: the push let go")
        Pin.levels[0] = 0
        check(keys.pressed() == ["D0"] and keys.held("D0"), "knob: Boot is D0, low when pressed")
        Pin.levels[0] = 1
        check(keys.pressed() == [], "knob: Boot let go")

        import atecc
        SoftI2C.answers = [0x36, 0x60]
        check(atecc.SDA == 42 and atecc.SCL == 41 and atecc.ATECC608().addr == 0x60, "knob: the key at 0x60 on 42/41")
        import setup_s
        check(setup_s.PRESSED == {"D1L": "Y", "D2": "A"} and setup_s.HELD == {"A": "D2", "B": "D0", "Y": "D0"},
              "knob ceremony: Boot held is the arm (B and Y), back a detent back, the push the step, never the arm")
        check("D2" not in (setup_s.HELD["B"], setup_s.HELD["Y"]), "knob ceremony: the push is never part of the arm")
finally:
    sys.platform = platform
    os.chdir(cwd)
    sys.path.remove(str(FW))
    sys.modules.pop("image", None)

# Every button read at power-up goes through board.key_down, which knows each button's pull.
raw = [f"{p.name}:{i + 1}" for p in sorted(FW.glob("*.py")) for i, line in enumerate(p.read_text().splitlines())
       if re.search(r"Pin\(board\.(MAINT|SETUP)\b", line)]
check(not raw, "no Pin(board.MAINT/SETUP) left in firmware/: key_down reads them" + (" (%s)" % ", ".join(raw) if raw else ""))
print("feather-s3, picoquorum-key, feather-knob: all pass" if not failed else "feather-s3, picoquorum-key, feather-knob: %d failed" % failed)
sys.exit(1 if failed else 0)
