"""The console's ESP32 paths on the laptop: board.py's "esp32" profile, the knob on the pulse counter,
the screen on VSPI in bands, numbered timers, the clock counted from 2000, TLS checked on the board,
and bench1.py. MicroPython is a stand-in here, made from its v1.26 ESP32 port (ports/esp32:
machine_pin.c, machine_timer.c, machine_hw_spi.c, modules/machine.py, modtime.c): Pin("LED") and a
pin's hard interrupt are refused, a Timer needs a number and is never hard, time.time() counts from
2000. Not a board: hardware/wiring/ESP32.md says what has run where.
    python3 test-vectors/esp32_test.py"""
from pathlib import Path
import os
import sys
import time as _t
import types
from unittest.mock import patch

FW = Path(__file__).resolve().parents[1] / "firmware"
failed = 0
log = []


def check(ok, what):
    global failed
    print(("pass  " if ok else "FAIL  ") + what)
    failed += not ok


# ---- MicroPython 1.26 on an ESP32, only what the firmware calls
class Pin:
    IN, OUT, PULL_UP, PULL_DOWN, IRQ_RISING, IRQ_FALLING = 1, 3, 1, 2, 1, 2
    levels = {}

    def __init__(self, id, mode=None, pull=None, value=None):
        if not isinstance(id, int) or not 0 <= id <= 39 or id in (20, 24, 28, 29, 30, 31):
            raise ValueError("invalid pin")
        assert not 6 <= id <= 11, "GPIO%d is the module's flash" % id
        assert not (id >= 34 and (mode == Pin.OUT or pull == Pin.PULL_UP)), "GPIO%d is input only" % id
        self.id = id
        if value is not None:
            Pin.levels[id] = value
        log.append(("Pin", id))

    def value(self, v=None):
        if v is None:
            return Pin.levels.get(self.id, 1)
        Pin.levels[self.id] = v
    __call__ = value

    def on(self):
        Pin.levels[self.id] = 1

    def off(self):
        Pin.levels[self.id] = 0

    def toggle(self):
        Pin.levels[self.id] = 1 - Pin.levels.get(self.id, 0)

    def irq(self, handler=None, trigger=3, wake=None):      # no hard=
        log.append(("irq", self.id))


class Timer:
    PERIODIC, ONE_SHOT = 1, 0

    def __init__(self, id, *, mode=1, callback=None, period=None, tick_hz=1000, freq=None):  # no hard=
        if not 0 <= id < 4:
            raise ValueError("invalid Timer number")
        log.append(("Timer", id, period))

    def deinit(self):
        pass


class SPI:
    def __init__(self, id, baudrate=-1, *, polarity=-1, phase=-1, bits=-1, firstbit=-1, sck=None, mosi=None, miso=None):
        assert id in (1, 2), id
        log.append(("SPI", id, sck.id, mosi.id, miso))

    def write(self, b):
        pass


class PWM:
    def __init__(self, pin, freq=None, duty_u16=None):
        log.append(("PWM", pin.id))

    def freq(self, f):
        pass

    def duty_u16(self, d):
        pass


class Encoder:      # modules/machine.py: a PCNT unit, 4x quadrature
    def __init__(self, unit_id, phase_a, phase_b, *, phases=1, filter_ns=0):
        assert phases in (1, 2, 4) and filter_ns * 80 // 1000 <= 1023
        log.append(("Encoder", unit_id, phase_a.id, phase_b.id, phases))
        self.count = 0

    def value(self, value=None):
        r = self.count
        if value is not None:
            self.count = value
        return r


class SoftI2C:
    def __init__(self, sda, scl, freq=400000):
        log.append(("SoftI2C", sda.id, scl.id))

    def writeto(self, a, b):
        raise OSError(19)

    def scan(self):
        return [0x60]


class I2C(SoftI2C):
    def __init__(self, id, sda, scl, freq=400000):
        log.append(("I2C", id, sda.id, scl.id))


machine = types.SimpleNamespace(Pin=Pin, Timer=Timer, SPI=SPI, PWM=PWM, Encoder=Encoder, I2C=I2C, SoftI2C=SoftI2C,
                                WDT=lambda timeout=5000: log.append(("WDT", timeout)) or types.SimpleNamespace(feed=lambda: None),
                                disable_irq=lambda: 0, enable_irq=lambda s: None, reset=lambda: None)
T2000 = 946684800
mptime = types.SimpleNamespace(
    time=lambda: int(_t.time()) - T2000,
    gmtime=lambda t=None: _t.gmtime((int(_t.time()) - T2000 if t is None else t) + T2000),
    ticks_ms=lambda: int(_t.monotonic() * 1000), ticks_diff=lambda a, b: a - b, ticks_add=lambda a, b: a + b,
    sleep_ms=lambda ms: None, sleep_us=lambda us: None)
mptime.localtime = mptime.gmtime


class FrameBuffer:
    def __init__(self, buf, w, h, fmt):
        self.size = (len(buf), w, h)

    def fill(self, c):
        pass

    def fill_rect(self, x, y, w, h, c):
        pass

    def text(self, s, x, y, c=1):
        log.append(("text", s, y))

    def pixel(self, x, y, c=None):
        return 0


class SSLContext:
    def __init__(self, proto):
        self.roots = []

    def load_verify_locations(self, cadata):        # positional only, as in extmod/modtls_mbedtls.c
        self.roots.append(cadata)


mods = {"machine": machine, "time": mptime, "micropython": types.SimpleNamespace(alloc_emergency_exception_buf=lambda n: None),
        "framebuf": types.SimpleNamespace(FrameBuffer=FrameBuffer, RGB565=1, MONO_HLSB=0),
        "network": types.SimpleNamespace(STA_IF=0, AP_IF=1, hostname=lambda *a: None),
        "requests": types.SimpleNamespace(), "secrets": types.SimpleNamespace(),
        "tls": types.SimpleNamespace(SSLContext=SSLContext, PROTOCOL_TLS_CLIENT=0, CERT_REQUIRED=2)}
platform, cwd = sys.platform, os.getcwd()
sys.path.insert(0, str(FW))
os.chdir(FW)                            # vhttp reads the pinned roots, ca_*.bin
sys.platform = "esp32"
try:
    with patch.dict(sys.modules, mods):
        import board
        check(board.ESP32 and board.BOARD == "esp32" and board.KNOB, "an ESP32 is the esp32 profile, a knob board")
        check((board.DC, board.CS, board.SCK, board.MOSI, board.RST, board.BL) == (19, 5, 18, 23, 15, 4), "the screen's pins")
        check((board.SPI_ID, board.SDA, board.SCL, board.LED) == (2, 21, 22, 2), "SPI(2), the key's bus on 21/22, the LED on 2")
        check((board.ENC_A, board.ENC_B, board.ENC_SW, board.MAINT, board.SETUP) == (33, 32, 25, 25, 13),
              "the knob, read as on the Pico; maintenance on its push, Wi-Fi setup on Reject")
        check(board.BUTTONS == {"A": 27, "B": 26, "Y": 13}, "Sign, Back and Reject; no X")
        check((board.W, board.H, board.BANDS) == (320, 240, 8), "the 2.8\" as 320x240 in 8 bands")
        check(board.EPOCH == T2000 and abs(board.unix() - _t.time()) < 2, "unix() is Unix time on a clock counted from 2000")

        del log[:]
        board.timer("watch", 1000, lambda t: None, hard=True)
        board.timer("tick", 50, lambda t: None)
        check(log == [("Timer", 2, 1000), ("Timer", 1, 50)], "timers by number, never hard")

        import knob
        del log[:]
        k = knob.Knob()
        check(("Encoder", 0, 33, 32, 4) in log and not any(e[0] == "irq" for e in log), "the knob on the pulse counter, no pin interrupts")
        k.enc.count = 8
        check(k.pressed() == ["down", "down"], "8 steps: two detents clockwise")
        k.enc.count = -5
        check(k.pressed() == ["up"] and k.steps == -1 and not k.pending(), "-5 steps: one detent back, one step kept, nothing pending")
        k.enc.count = -3
        check(k.pending() and k.pressed() == ["up"] and k.steps == 0, "the kept step completes the next detent")
        Pin.levels[25] = 0
        k.since -= 1000
        check(k.held() and k.pressed() == ["press"], "the push")
        Pin.levels[25] = 1

        import lcd
        del log[:]
        lcd.LCD()
        check(("SPI", 2, 18, 23, None) in log and ("PWM", 4) in log, "the screen on VSPI's own pins, the backlight on 4")
        check(len(lcd._BUF) == 320 * 30 * 2, "one 19,200-byte band, not a 150 KB frame")
        keys = lcd.Keys()
        check(set(keys.pins) == {"A", "B", "Y"} and keys.knob is not None, "the keys: A, B, Y and the knob")

        import atecc
        del log[:]
        atecc.make_i2c(atecc.SDA, atecc.SCL, 100_000)
        check((atecc.SDA, atecc.SCL) == (21, 22) and log[-1] == ("SoftI2C", 21, 22), "the chip's bus on 21/22")

        import net
        check(net.led.id == 2, "the status LED on GPIO2")

        import watch
        del log[:]
        watch.start()
        check(log == [("Timer", 2, 1000), ("WDT", 8000)], "the watchdog: its feeder on timer 2 first, then the watchdog")

        import txservice
        check(txservice.ON_BOARD and txservice.RESERVE == 0, "TLS checked on the board; no reserve in MicroPython's heap")
        s = txservice.Service("https://api.safe.global/tx-service/base", "0x" + "11" * 20, verify=True)
        check(s.tls == "verified" and s._ctx.verify_mode == 2 and len(s._ctx.roots) == 3,
              "Safe's service over TLS checked against the 3 pinned roots, never MicroPython's requests")

        import vhttp
        try:
            vhttp.clock(floor=int(_t.time()) - 3600)
            check(True, "the clock is not refused for a build an hour old")
        except (OSError, ImportError):          # ImportError: it asked NTP (no ntptime here)
            check(False, "the clock is not refused for a build an hour old")
        try:
            vhttp.clock(floor=int(_t.time()) + 10 ** 6)
            check(False, "a clock behind the build is refused")
        except (OSError, ImportError):          # no ntptime here: it would have asked NTP
            check(True, "a clock behind the build is refused")

        import quorum_ui
        check(quorum_ui.clock_set() and quorum_ui.ago(board.unix() - 120) == "2m ago", "the clock card and 'ago' in Unix time")

        import tmcfg
        check(tmcfg._emu_ca() is None, "no emulator CA on an ESP32")

        import atecc as A
        A.ATECC608 = lambda *a, **kw: types.SimpleNamespace(
            serial=lambda: bytes(range(9)), revision=lambda: b"\x00\x00\x60\x03",
            lock_state=lambda: {"configLocked": False, "dataLocked": False})
        del log[:]
        import bench1
        check(("SPI", 2, 18, 23, None) in log and ("Encoder", 0, 33, 32, 4) in log and ("Timer", 1, 20) in log,
              "bench1: the screen on VSPI, the knob on the pulse counter, its tick on timer 1")
        check(bench1.scr.size == (320 * 30 * 2, 320, 30), "bench1: a 30-row band, not the whole frame")
        check([e[2] for e in log if e[:2] == ("text", "TL")] == [2 - 30 * i for i in range(8)], "bench1: each band drawn, shifted")
        check(bench1.st["probe"]["rev"] == "608B", "bench1: the chip read")
        bench1._enc.count = 9
        check(bench1.clicks() == 2, "bench1: 9 steps are 2 clicks")
        src = (FW / "bench1.py").read_text().replace("JACKS = False   ", "JACKS = True    ")
        try:
            exec(compile(src, "bench1 (JACKS)", "exec"), {"__name__": "bench1_jacks"})
            check(False, "bench1: no key jacks on an ESP32")
        except ValueError:
            check(True, "bench1: no key jacks on an ESP32")
finally:
    sys.platform = platform
    os.chdir(cwd)
    sys.path.remove(str(FW))
print("esp32: all pass" if not failed else "esp32: %d failed" % failed)
sys.exit(1 if failed else 0)
