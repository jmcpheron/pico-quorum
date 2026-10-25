# Which hardware this is, from secrets.BOARD, and its screen and input pins. Small on purpose: the
# main files read it before the framebuffer is allocated (the maintenance key), and lcd.py builds
# the screen and the keys from it.
#   "waveshare" (the default): Pico-LCD-1.3, 240x240 ST7789, joystick and A/B/X/Y
#   "build1": hardware/wiring/BREADBOARD.md and BUILD1.md: an EC11 knob (turn and press), A/B/X/Y
#             on the same pins once wired, and a screen on the same 8 wires (SCREEN):
#               "2.8" (or "2.0", "2.4"): 240x320 ST7789 run landscape as 320x240; the 2.8" is
#                     proven on the bench (2026-09-27), the 2.0" and 2.4" not yet
#               "1.8": 128x160 ST7735S run landscape as 160x128 (proven the same day)
#   "esp32": build1's screen (SCREEN as above) and knob on an ESP32 DevKit instead of a Pico
#            (hardware/wiring/ESP32.md). Always this one on an ESP32, whatever secrets.BOARD says:
#            the Pico's pin numbers are the ESP32's flash. Run on a WROOM-32 and a WROVER.
#   "feather-s3": Adafruit's Feather ESP32-S3 Reverse TFT (hardware/wiring/FEATHER-S3.md): its own
#            240x135 ST7789 and three buttons, D0 D1 D2, down the screen's left edge (THREE). On an
#            ESP32-S3 always this one or one of the next two; the emulator picks it with secrets.BOARD.
#   "picoquorum-key": PicoQuorumKey (hardware/picoquorum-key/docs/PINS.md), an S3 board of our own
#            with the Feather's screen and three buttons (THREE) on other pins, all pressed low. An S3
#            is this one when GPIO16 and 17, its key's bus, read high against the S3's own pull-downs:
#            only it has pull-ups there (4.7k). The Feather, console-s3 and the wings leave them free.
#   "feather-knob": Adafruit's ESP32-S3 TFT Feather (5483) with an EC11 knob on its header pins
#            (hardware/builds/feather-knob/README.md): the same screen on other pins, and Boot as its
#            only button. The Feather's three keys come from Boot and the knob (DIAL), so the console
#            and the ceremony run as on feather-s3. Only when secrets.BOARD names it, which comes
#            before the look at GPIO16/17: they are its knob's A2 and A1.
# W x H is what the apps draw, X_OFF where that sits on the panel (0 when they draw all of it).
# BANDS: retain full native resolution, but only buffer 30 rows at a time (19,200 bytes at 320 wide,
# 14,400 at 240). Any panel whose whole frame would be over 45 KB is drawn this way: the 240x240
# Waveshare's 115 KB frame left ~109 KB of heap once the console was imported, HTTPS could not find its
# 16 KB block and the console restarted over and over (OSError 12, 2026-09-29). The 1.8" (41 KB) keeps one frame.
# The previous 120-row buffer used 76,800 bytes and left too little headroom for TLS.
import sys
import time
ESP32 = sys.platform == "esp32"
S3 = False
if ESP32:
    try:
        import os
        S3 = "ESP32S3" in os.uname().machine
    except (AttributeError, ImportError):
        pass
try:
    import secrets as _s
    BOARD = getattr(_s, "BOARD", "waveshare")
    SCREEN = getattr(_s, "SCREEN", "2.8")
except ImportError:
    BOARD, SCREEN = "waveshare", "2.8"


def _pulled_up(*pins):
    """Whether every pin reads high with only the S3's internal pull-down on it (about 45k), so
    something on the board pulls it up harder. Inputs only, left with no pull after."""
    from machine import Pin
    ps = [Pin(n, Pin.IN, Pin.PULL_DOWN) for n in pins]
    time.sleep_us(100)
    up = all(p.value() for p in ps)
    for n in pins:
        Pin(n, Pin.IN, None)
    return up


if ESP32:
    BOARD = ("feather-knob" if BOARD == "feather-knob" else "picoquorum-key" if _pulled_up(16, 17) else "feather-s3") \
        if S3 else "esp32"
elif BOARD not in ("waveshare", "build1", "feather-s3", "picoquorum-key", "feather-knob"):
    print("board: unknown BOARD %r, using waveshare" % BOARD)
    BOARD = "waveshare"

KNOB = BOARD in ("build1", "esp32")
DIAL = BOARD == "feather-knob"
THREE = BOARD in ("feather-s3", "picoquorum-key") or DIAL
DC, CS, SCK, MOSI, RST, BL = 8, 9, 10, 11, 12, 13
BUTTONS = {"A": 15, "B": 17, "X": 19, "Y": 21}
SPI_ID, SDA, SCL, LED = 1, 4, 5, "LED"      # SDA, SCL: the key's I2C (atecc.py); LED: the status LED
HIGH = ()                   # buttons pulled down, pressed high (key_down); the rest are pulled up, pressed low
RAM_X = RAM_Y = 0           # where the picture starts in the panel's own RAM (lcd._window)
NOT_KEYS = ()               # I2C addresses on the key's bus that are never a key (atecc.KEY_ADDRS)
POWER = None                # a pin that must be high for the screen and the key's bus to have power
RAIL_Y = None               # THREE: the screen row level with each button, top to bottom (quorum_ui_s.rail)
NAMES = {"D0": "D0", "D1": "D1", "D2": "D2"}    # THREE: what the screens call each key
INIT = "plain" if KNOB else "waveshare"     # lcd.py's panel start-up
if ESP32:
    # tools/wiring-esp32 --check compares these with hardware/wiring/ESP32.md. The screen's clock
    # and data on VSPI's own pins (18, 23), so SPI(2) drives them without the GPIO matrix. Nothing on
    # the flash (6-11), a WROVER's PSRAM (16, 17), the boot pins that can stop a boot (0, 2, 12) or
    # the input-only pins (34-39, no pull-ups). CS (5) and RST (15) are boot pins too, but only
    # ever high at reset, which is their default. No X: the knob's press does what it does.
    # LED: the blue one on GPIO2 of DOIT-style boards; an Espressif DevKitC has none.
    DC, CS, SCK, MOSI, RST, BL = 19, 5, 18, 23, 15, 4
    BUTTONS = {"A": 27, "B": 26, "Y": 13}
    SPI_ID, SDA, SCL, LED = 2, 21, 22, 2
if THREE:
    # Adafruit's pinout, checked on the board 2026-10-20 (FEATHER-S3.md). GPIO7 powers the screen and
    # the STEMMA QT/I2C pull-ups. The MAX17048 battery gauge shares the key's bus at 0x36, an address
    # atecc.py would otherwise try as a key.
    DC, CS, SCK, MOSI, RST, BL = 40, 42, 36, 35, 41, 45
    BUTTONS = {"D0": 0, "D1": 1, "D2": 2}
    HIGH = (1, 2)
    SPI_ID, SDA, SCL, LED = 1, 3, 4, 13
    NOT_KEYS, POWER = (0x36,), 7
    # The 135x240 panel sits at column 40, row 53 of the ST7789's 240x320 RAM, landscape (MX|MV) with
    # the buttons on the left. Inversion on, as tft.py proved.
    PANEL_W, PANEL_H = W, H = 240, 135
    MADCTL, RAM_X, RAM_Y = 0x60, 40, 53
    SPI_BAUD = 40_000_000
    INIT = "plain"
    KEYS = dict(BUTTONS)
    # D0 is the S3's BOOT strap: held at reset it starts the ROM bootloader, so never a power-up key.
    MAINT, SETUP = BUTTONS["D1"], BUTTONS["D2"]
    # Level with D0, D1, D2: rows 0-14, 60-74 and 120-134, read off the board (stage0.py, 2026-10-22).
    RAIL_Y = (7, 67, 127)
elif KNOB and SCREEN == "1.8":
    # Proven on the bench: MY|MV landscape with the header on the right, inversion on (an IPS
    # panel), no RAM offset. The whole 40 KB frame fits, so the apps draw all of it.
    PANEL_W, PANEL_H = W, H = 160, 128
    MADCTL = 0xA0
    SPI_BAUD = 24_000_000
elif KNOB:
    PANEL_W, PANEL_H = W, H = 320, 240
    MADCTL = 0x60           # MX|MV: landscape with the header on the left, as Build 1's case holds it
                            # (2026-10-02); 0xA0 was the bench's way up, the header on the right
    SPI_BAUD = 24_000_000   # jumper wires: clean at 24 MHz on the 1.8"
if BOARD == "picoquorum-key":
    # The Feather's screen, buttons and rail on PicoQuorumKey's pins (PINS.md): the screen on the S3's
    # own SPI(1) pins, D0 D1 D2 on 42 41 40 to ground with the S3's pull-ups (HIGH empty), the key on
    # 16/17 with 4.7k pull-ups and nothing else on its bus, the LED on 48. Nothing to power up.
    DC, CS, SCK, MOSI, RST, BL = 9, 10, 12, 11, 14, 21
    BUTTONS = {"D0": 42, "D1": 41, "D2": 40}
    HIGH = ()
    SPI_ID, SDA, SCL, LED = 1, 16, 17, 48
    NOT_KEYS, POWER = (), None
    KEYS = dict(BUTTONS)
    MAINT, SETUP = BUTTONS["D1"], BUTTONS["D2"]
if KNOB:
    # A on GP2 and B on GP3 as wired (BREADBOARD.md); read the other way round, because this knob
    # counted clockwise as anticlockwise (2026-09-27). Swapping the two wires does the same.
    # The ESP32 the same way: A wired to GPIO32, B to GPIO33 (ESP32.md).
    ENC_A, ENC_B, ENC_SW = (33, 32, 25) if ESP32 else (3, 2, 1)
    KEYS = dict(BUTTONS)    # the knob is knob.py's; GP2/GP3 are never joystick keys here
    MAINT = ENC_SW          # held at power-up: maintenance (main_console.py, main_dual.py)
elif not THREE:
    PANEL_W, PANEL_H = W, H = 240, 240
    MADCTL = 0x70
    SPI_BAUD = 62_500_000
    KEYS = dict(BUTTONS, up=2, down=18, left=16, right=20, press=3)
    MAINT = BUTTONS["B"]
if not THREE:
    SETUP = BUTTONS["Y"]    # held at power-up: Wi-Fi setup (boot.py, wifisetup.py)
if DIAL:
    # The ESP32-S3 TFT Feather, from Adafruit's schematic (Adafruit-ESP32-S3-TFT-Feather-PCB): the
    # screen's CS, DC and RST on 7, 39, 40, the key's bus on the SDA/SCL pins (42, 41), and GPIO21
    # powering the screen and the I2C pull-ups. Screen set up as feather-s3's, as CircuitPython sets
    # up both. Boot (GPIO0) is D0. The knob on the 16-pin row: A on A1, B on A2, its push on A3,
    # C and the push's other leg to GND. lcd.Keys hands its detents and push on as D1, D1L and D2.
    DC, CS, RST = 39, 7, 40
    BUTTONS = {"D0": 0}
    HIGH = ()
    SDA, SCL, POWER = 42, 41, 21
    ENC_A, ENC_B, ENC_SW = 17, 16, 15
    KEYS = dict(BUTTONS)
    # Boot can't be held at power-up (the ROM bootloader), so the push is maintenance. Wi-Fi setup
    # comes from the Device screen, or by itself when no network is saved.
    MAINT = SETUP = ENC_SW
    NAMES = {"D0": "Boot", "D1": "turn", "D2": "push"}
# The Feather keeps its whole 64.8 KB frame: the S3's 2 MB of PSRAM has room, and 135 rows don't
# split into equal bands.
BANDS = 8 if W * H * 2 > 45_000 and not THREE else 1
X_OFF, Y_OFF = (PANEL_W - W) // 2, (PANEL_H - H) // 2
SMALL = W < 200 or H < 160  # a screen too small for the console's 240x240 pages (quorum_ui_s.py)

if POWER is not None:
    from machine import Pin as _Pin
    _Pin(POWER, _Pin.OUT, value=1)


def key_down(pin):
    """Whether the button on pin is held now, read with its own pull: a pulled-up button reads 0
    when pressed, one in HIGH (the Feather's D1 and D2, pulled down on the board) reads 1."""
    from machine import Pin
    if pin in HIGH:
        return Pin(pin, Pin.IN, Pin.PULL_DOWN).value() == 1
    return Pin(pin, Pin.IN, Pin.PULL_UP).value() == 0

# Seconds from 1970 to time.time()'s zero: MicroPython on the ESP32 counts from 2000, on the Pico
# and in the emulator from 1970. unix() is the clock to compare with anything from outside the
# board (the build's date, a chip's record, Safe's service) and to write anywhere that outlives it.
EPOCH = 946684800 if time.gmtime(0)[0] == 2000 else 0


def unix():
    return time.time() + EPOCH


# machine.Timer by job. The Pico's are virtual (id -1), as many as wanted, and may be hard. The
# ESP32 has four hardware timers, picked by number, and calls every callback from the scheduler:
# two jobs that run at once never share a number.
TIMERS = {"splash": 0, "tick": 1, "watch": 2, "setup": 3}


def timer(job, period, callback, hard=False):
    """A periodic machine.Timer for job (TIMERS) that calls callback every period ms."""
    from machine import Timer
    if ESP32:
        return Timer(TIMERS[job], period=period, mode=Timer.PERIODIC, callback=callback)
    if hard:
        return Timer(period=period, mode=Timer.PERIODIC, callback=callback, hard=True)
    return Timer(period=period, mode=Timer.PERIODIC, callback=callback)
