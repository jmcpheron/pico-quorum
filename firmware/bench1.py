# Build 1 bench test (hardware/wiring/BREADBOARD.md, BUILD1.md): the 2.0" ST7789 240x320 screen, the
# EC11 knob, and the ATECC608, wired straight to the Pico or behind the two key jacks. It only reads
# the chip: no config write, no lock, no GenKey.
# Pins match the table in tools/wiring-build1; `tools/wiring-build1 --check` says whether they still do.
# On an ESP32 (hardware/wiring/ESP32.md) the same parts on board.py's "esp32" pins, which
# `tools/wiring-esp32 --check` holds to that page. No jacks there.
#
# Run: `tools/usb push`, then `tools/usb` for the REPL and `import bench1`. On a board whose main.py
# starts the wallet, stop it first (`import wallet; wallet.stop()`) or boot with main.py held back:
# the wallet drives the same SPI pins and reads GP2/GP3 as the joystick. It runs from a 20 ms Timer
# so the REPL stays free; bench1.stop() ends it (and cuts key power with JACKS).
#
# JACKS = False (the default, hardware/wiring/BREADBOARD.md): the chip is wired straight to 3.3 V,
# GP4 and GP5. bench1 reads it at start and on every knob press, and never touches GP6 or GP7.
# JACKS = True (hardware/wiring/BUILD1.md): the chip lives in a key behind the two jacks, as below.
#
# On the screen and the REPL:
#   knob      turn: the count moves one per click. Press: scan the chip's bus now.
#             Hold 2 s: the full read-only chip report (chipcheck.py) on the REPL.
#   key       (JACKS only) DETECT (J1 ring 2) low for 200 ms -> key power (GP6) on -> scan -> read the chip.
#             DETECT high -> key power off at once and the I2C pins let go. Nothing that answers
#             at a known address within 3 tries -> power off again, "not a key" (a headset, say).
import time
import framebuf
from machine import Pin, SPI, PWM
import board

SCR_DC = 8
SCR_CS = 9
SCR_SCK = 10
SCR_MOSI = 11
SCR_RST = 12
SCR_BL = 13
ENC_A = 2
ENC_B = 3
ENC_SW = 1
KEY_SDA = 4
KEY_SCL = 5
KEY_PWR = 6
KEY_DETECT = 7
KEY_RST = 26            # J2 ring 1; left alone here (a Trust M key soft-resets over I2C)
KEY_ID = 27             # J2 ring 2; open on every Build 1 key
if board.ESP32:
    SCR_DC, SCR_CS, SCR_SCK, SCR_MOSI, SCR_RST, SCR_BL = board.DC, board.CS, board.SCK, board.MOSI, board.RST, board.BL
    ENC_A, ENC_B, ENC_SW = board.ENC_A, board.ENC_B, board.ENC_SW      # read as the console reads them
    KEY_SDA, KEY_SCL = board.SDA, board.SCL

JACKS = False           # True once the key jacks are wired (BUILD1.md); False: chip wired straight to 3V3
if JACKS and board.ESP32:
    raise ValueError("bench1: the key jacks are Build 1's, on a Pico; JACKS = False on an ESP32")
W, H = 320, 240         # landscape
BANDS = 8 if board.ESP32 else 1     # an ESP32 has no 150 KB block for the whole frame: 30 rows at a time
MADCTL = 0x60           # MX|MV: landscape. Upside down: 0xA0. Mirrored: flip 0x40 or 0x80. Red and blue swapped: add 0x08
INVERT = True           # IPS ST7789 panels want inversion on; colors look like a negative -> False
SPI_BAUD = 24_000_000   # jumper wires; garbage on screen -> 10_000_000, short soldered leads -> 62_500_000
STEPS_PER_CLICK = 4     # most EC11s: 4 quadrature steps per detent. Counts 2 per click -> 2
SETTLE_MS = 200         # DETECT must read low this long before key power goes on
HOLD_MS = 2000

KEY_ADDRS = {0x60: "ATECC608", 0x35: "ATECC608 (Trust&Go)", 0x6A: "ATECC608 (TrustFLEX)", 0x30: "OPTIGA Trust M"}


def rgb(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


BLACK, WHITE, GREY, DARK = rgb(0, 0, 0), rgb(255, 255, 255), rgb(130, 130, 130), rgb(40, 40, 40)
RED, GREEN, BLUE, YELLOW, ORANGE = rgb(255, 0, 0), rgb(0, 255, 0), rgb(0, 0, 255), rgb(255, 220, 0), rgb(255, 140, 0)


class Screen(framebuf.FrameBuffer):
    """A 240x320 ST7789 run landscape as 320x240. The console's own driver is lcd.py with board.py
    "build1" (hardware/wiring/BUILD1.md, firmware to do 1); this one stays the bench's reference.
    It holds rows y0 .. y0 + H // BANDS - 1 of the screen; frames(draw) draws once per band."""

    def __init__(self):
        self.cs = Pin(SCR_CS, Pin.OUT, value=1)
        self.dc = Pin(SCR_DC, Pin.OUT, value=1)
        self.rst = Pin(SCR_RST, Pin.OUT, value=1)
        self.spi = SPI(board.SPI_ID, SPI_BAUD, polarity=0, phase=0, sck=Pin(SCR_SCK), mosi=Pin(SCR_MOSI), miso=None)
        self.bl = PWM(Pin(SCR_BL))
        self.bl.freq(1000)
        self.bl.duty_u16(65535)
        self.y0 = 0
        self.buf = bytearray(W * (H // BANDS) * 2)
        super().__init__(self.buf, W, H // BANDS, framebuf.RGB565)
        self.rst(0); time.sleep_ms(20); self.rst(1); time.sleep_ms(150)
        self._cmd(0x01); time.sleep_ms(150)            # software reset
        self._cmd(0x11); time.sleep_ms(120)            # sleep out
        self._cmd(0x3A, b"\x55")                       # 16-bit color
        self._cmd(0x36, bytes([MADCTL]))
        self._cmd(0x21 if INVERT else 0x20)
        self._cmd(0x13)                                # normal display mode
        self._cmd(0x29); time.sleep_ms(20)             # display on

    def _cmd(self, c, data=None):
        self.dc(0); self.cs(0); self.spi.write(bytes([c])); self.cs(1)
        if data:
            self.dc(1); self.cs(0); self.spi.write(data); self.cs(1)

    def show(self):
        y1 = self.y0 + H // BANDS - 1
        self._cmd(0x2A, bytes([0, 0, (W - 1) >> 8, (W - 1) & 0xFF]))
        self._cmd(0x2B, bytes([self.y0 >> 8, self.y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._cmd(0x2C)
        self.dc(1); self.cs(0); self.spi.write(self.buf); self.cs(1)

    def frames(self, draw, *args):
        for y0 in range(0, H, H // BANDS):
            self.y0 = y0
            draw(*args)
        self.y0 = 0

    def big(self, s, x, y, c, scale=2):
        w = 8 * len(s)
        tmp = framebuf.FrameBuffer(bytearray(w), w, 8, framebuf.MONO_HLSB)
        tmp.text(s, 0, 0, 1)
        for yy in range(8):
            for xx in range(w):
                if tmp.pixel(xx, yy):
                    self.fill_rect(x + xx * scale, y + yy * scale, scale, scale, c)


class BandScreen(Screen):
    """Screen for BANDS > 1: drawing takes screen rows and lands in the band, framebuf clips the rest."""

    def fill_rect(self, x, y, w, h, c):
        super().fill_rect(x, y - self.y0, w, h, c)

    def text(self, s, x, y, c):
        super().text(s, x, y - self.y0, c)


if BANDS > 1:
    Screen = BandScreen


# --- knob: quadrature on two edge interrupts; on an ESP32, its pulse counter (knob.py says why) ---
_enc_a = Pin(ENC_A, Pin.IN, Pin.PULL_UP)
_enc_b = Pin(ENC_B, Pin.IN, Pin.PULL_UP)
_push = Pin(ENC_SW, Pin.IN, Pin.PULL_UP)
_QUAD = (0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0)
_enc_state = (_enc_a.value() << 1) | _enc_b.value()
_enc = None
steps = 0


def _enc_irq(_):
    global _enc_state, steps
    s = (_enc_a.value() << 1) | _enc_b.value()
    steps += _QUAD[(_enc_state << 2) | s]
    _enc_state = s


if board.ESP32:
    from machine import Encoder
    _enc = Encoder(0, _enc_a, _enc_b, phases=4, filter_ns=10_000)
else:
    _enc_a.irq(_enc_irq, Pin.IRQ_RISING | Pin.IRQ_FALLING, hard=True)    # knob.py says why hard
    _enc_b.irq(_enc_irq, Pin.IRQ_RISING | Pin.IRQ_FALLING, hard=True)


def count():
    """Quadrature steps since the start."""
    return _enc.value() if _enc else steps


def clicks():
    return int(count() / STEPS_PER_CLICK)


# --- key: detect, power, bus ---------------------------------------------------------------------
_detect = _pwr = None
if JACKS:
    _detect = Pin(KEY_DETECT, Pin.IN, Pin.PULL_UP)
    try:
        _pwr = Pin(KEY_PWR, Pin.OUT, value=0, drive=Pin.DRIVE_3)   # 12 mA drive where the port has it
    except (AttributeError, TypeError, ValueError):
        _pwr = Pin(KEY_PWR, Pin.OUT, value=0)


def release_bus():
    """SDA and SCL back to plain inputs, no pull-ups, so nothing feeds an unpowered chip through them."""
    Pin(KEY_SDA, Pin.IN, pull=None)
    Pin(KEY_SCL, Pin.IN, pull=None)


def power(on):
    if not JACKS:
        return          # the chip is on 3V3 all the time
    if not on:
        release_bus()
    _pwr.value(1 if on else 0)


def hexs(b):
    return "".join("%02x" % x for x in b)


def probe():
    """Scan up to 3 times; read the chip if an ATECC answers. Returns a dict for the screen."""
    import atecc
    found = []
    for _ in range(3):
        found = atecc.scan(KEY_SDA, KEY_SCL)
        if any(a in KEY_ADDRS for a in found):
            break
        time.sleep_ms(15)
    r = {"bus": found, "kind": None, "serial": None, "rev": None, "locks": None, "err": None}
    addr = next((a for a in found if a in KEY_ADDRS), None)
    print("key bus scan:", ["0x%02x" % a for a in found] or "nothing")
    if addr is None:
        return r
    r["kind"] = KEY_ADDRS[addr]
    if addr == 0x30:
        return r        # trustm.py is not wired into the bench yet (hardware/wiring/BUILD1.md, firmware to do 5)
    try:
        chip = atecc.ATECC608(KEY_SDA, KEY_SCL, addr=addr)
        r["serial"] = hexs(chip.serial())
        rev = bytes(chip.revision())
        r["rev"] = {b"\x00\x00\x60\x02": "608A", b"\x00\x00\x60\x03": "608B"}.get(rev, hexs(rev))
        r["locks"] = chip.lock_state()
        print("chip: %s serial %s, config %s, data %s" % (r["rev"], r["serial"],
              "LOCKED" if r["locks"]["configLocked"] else "open", "LOCKED" if r["locks"]["dataLocked"] else "open"))
    except Exception as e:
        r["err"] = str(e)
        print("chip read failed:", e)
    return r


# --- screen --------------------------------------------------------------------------------------
def draw(scr, st):
    scr.fill(BLACK)
    scr.text("TL", 2, 2, GREY)                          # top-left corner: orientation check
    scr.big("ESP32 BENCH" if board.ESP32 else "BUILD 1 BENCH", 56, 4, YELLOW)
    for i, (c, name) in enumerate(((RED, "RED"), (GREEN, "GRN"), (BLUE, "BLU"), (WHITE, "WHT"))):
        scr.fill_rect(8 + i * 78, 26, 72, 18, c)
        scr.text(name, 8 + i * 78 + 24, 31, BLACK if c in (GREEN, WHITE) else WHITE)
    y = 54
    def row(label, val, c=WHITE):
        nonlocal y
        scr.big(label, 8, y, GREY)
        scr.big(val, 112, y, c)
        y += 22
    row("KNOB", "%+d" % clicks())
    scr.text("%d steps" % count(), 230, y - 16, GREY)
    row("PUSH", "DOWN" if st["down"] else "up", GREEN if st["down"] else WHITE)
    if JACKS:
        row("DETECT", "key in" if st["present"] else "no key", GREEN if st["present"] else WHITE)
        row("POWER", "ON  GP6" if st["powered"] else "off", ORANGE if st["powered"] else WHITE)
    p = st["probe"]
    if p is None:
        row("BUS", "-")
    else:
        row("BUS", " ".join("%02x" % a for a in p["bus"])[:13] or "nothing", GREEN if p["kind"] else RED)
        if p["kind"]:
            row("CHIP", (p["rev"] or p["kind"])[:13], GREEN)
        if p["serial"]:
            scr.text("serial " + p["serial"], 8, y, WHITE); y += 12
        if p["locks"]:
            cl, dl = p["locks"]["configLocked"], p["locks"]["dataLocked"]
            scr.text("config %s   data %s" % ("LOCKED" if cl else "open", "LOCKED" if dl else "open"), 8, y, YELLOW if cl else WHITE); y += 12
        if p["err"]:
            scr.text(p["err"][:38], 8, y, RED); y += 12
    if st["msg"]:
        scr.text(st["msg"][:39], 8, 212, ORANGE)
    scr.text("press: scan   hold 2s: chip report", 8, 226, GREY)
    scr.show()


scr = None
timer = None
st = {"down": False, "present": False, "powered": False, "probe": None, "msg": ""}
_low_since = None
_refused = False                 # "not a key": stay off until the plug comes out
_down_at = None
_held = False
_last = None
_busy = False


def tick(_=None):
    global _low_since, _refused, _down_at, _held, _last, _busy
    if _busy:
        return
    _busy = True
    try:
        now = time.ticks_ms()
        # key presence and power
        present = JACKS and _detect.value() == 0
        if not JACKS:
            pass
        elif not present:
            _low_since = None
            _refused = False
            if st["powered"]:
                power(False); st["powered"] = False; st["probe"] = None
                st["msg"] = "key out: power cut"; print(st["msg"])
        else:
            if _low_since is None:
                _low_since = now
            if not st["powered"] and not _refused and time.ticks_diff(now, _low_since) >= SETTLE_MS:
                power(True); st["powered"] = True
                time.sleep_ms(5)
                st["probe"] = probe()
                if st["probe"]["kind"] is None:
                    power(False); st["powered"] = False; _refused = True
                    st["msg"] = "not a key: power cut, unplug to retry"
                else:
                    st["msg"] = "key in: %s" % st["probe"]["kind"]
                print(st["msg"])
        st["present"] = _low_since is not None and time.ticks_diff(now, _low_since) >= SETTLE_MS
        # knob push: press = scan, hold = chip report
        down = _push.value() == 0
        if down and _down_at is None:
            _down_at, _held = now, False
        elif down and not _held and time.ticks_diff(now, _down_at) >= HOLD_MS:
            _held = True
            st["msg"] = "chip report on the REPL"
            import chipcheck
            chipcheck.main()
            if JACKS and not st["powered"]:
                release_bus()
        elif not down and _down_at is not None:
            if not _held:
                st["probe"] = probe()
                st["msg"] = "scanned" + ("" if st["powered"] or not JACKS else " (GP6 off: 3V3-wired chip only)")
                if JACKS and not st["powered"]:
                    release_bus()
            _down_at = None
        st["down"] = down
        key = (count(), st["down"], st["present"], st["powered"], id(st["probe"]), st["msg"])
        if key != _last:
            scr.frames(draw, scr, st)
            _last = key
    finally:
        _busy = False


def start():
    global scr, timer
    power(False)
    scr = Screen()
    if not JACKS:
        st["probe"] = probe()
    scr.frames(draw, scr, st)
    timer = board.timer("tick", 20, tick)
    print("bench1 running: turn the knob, press it%s. bench1.stop() to stop." % (", plug the key" if JACKS else ""))


def stop():
    """Timer off, key power off, bus released."""
    if timer:
        timer.deinit()
    power(False)
    st["powered"] = False
    print("bench1: stopped" + (", key power off" if JACKS else ""))


start()
