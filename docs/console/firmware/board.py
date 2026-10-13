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
#            the Pico's pin numbers are the ESP32's flash. Not yet run on a board.
#   "cardputer": an M5Stack Cardputer v1.1 (ESP32-S3): its 240x135 ST7789V2, and its keyboard in
#            place of the knob (lcd.Keys). Always this one on an ESP32-S3. The key goes on the
#            Grove port through a 3.3 V adapter (hardware/bom/README.md). It needs the MicroPython
#            in tools/micropython-s3, which runs the modules from flash (ROMFS): on stock MicroPython
#            the console runs out of heap. On the bench with a key and two Safes (2026-10-12).
# W x H is what the apps draw, X_OFF where that sits on the panel (0 when they draw all of it).
# BANDS: retain full native resolution, but only buffer 30 rows at a time (19,200 bytes at 320 wide,
# 14,400 at 240). Any panel whose whole frame would be over 45 KB is drawn this way: the 240x240
# Waveshare's 115 KB frame left ~109 KB of heap once the console was imported, HTTPS could not find its
# 16 KB block and the console restarted over and over (OSError 12, 2026-09-29). The 1.8" (41 KB) keeps one frame.
# The previous 120-row buffer used 76,800 bytes and left too little headroom for TLS.
import sys
import time
ESP32 = sys.platform == "esp32"
try:
    import os as _os
    S3 = ESP32 and "ESP32S3" in _os.uname().machine
except Exception:
    S3 = False
try:
    import secrets as _s
    BOARD = getattr(_s, "BOARD", "waveshare")
    SCREEN = getattr(_s, "SCREEN", "2.8")
except ImportError:
    BOARD, SCREEN = "waveshare", "2.8"
if S3:
    BOARD = "cardputer"
elif ESP32:
    BOARD = "esp32"
elif BOARD not in ("waveshare", "build1"):
    print("board: unknown BOARD %r, using waveshare" % BOARD)
    BOARD = "waveshare"

KNOB = BOARD in ("build1", "esp32", "cardputer")
KEYBOARD = BOARD == "cardputer"
DC, CS, SCK, MOSI, RST, BL = 8, 9, 10, 11, 12, 13
BUTTONS = {"A": 15, "B": 17, "X": 19, "Y": 21}
SPI_ID, SDA, SCL, LED = 1, 4, 5, "LED"      # SDA, SCL: the key's I2C (atecc.py); LED: the status LED
if KEYBOARD:
    # The Stamp-S3A's own wiring (M5's Cardputer pin map), checked on the bench. The key on the
    # Grove port: G2 SDA (yellow), G1 SCL (white). LED: the RGB LED's data pin; it only flickers.
    DC, CS, SCK, MOSI, RST, BL = 34, 37, 36, 35, 33, 38
    BUTTONS = {}
    SPI_ID, SDA, SCL, LED = 2, 2, 1, 21
    # The keyboard: a 74HC138 picks one of 8 lines (ROW_SEL, 3 bits) and 7 inputs (COL_IN) read that
    # line's keys, low while down. A key is (line, input); its name is what the knob's event is called.
    ROW_SEL = (8, 9, 11)
    COL_IN = (13, 15, 3, 4, 5, 6, 7)
    KEYMAP = {(1, 5): "up", (0, 5): "down", (4, 5): "left", (4, 6): "right",    # ; . , /: their printed arrows
              (1, 6): "press",                                                  # Enter
              (3, 6): "B"}                                                      # Del: back
    # Held at power-up: Enter for maintenance (the knob's press elsewhere), S for Wi-Fi setup. Both
    # are on line 1, which is picked here and again after every scan (lcd.Keys), so boot.py and
    # main_console.py read each as a plain pin. Not G0: held at reset, it starts the ROM bootloader.
    from machine import Pin as _Pin
    for _p, _v in zip(ROW_SEL, (1, 0, 0)):
        _Pin(_p, _Pin.OUT, value=_v)
    KEYS = {}
    MAINT, SETUP = COL_IN[6], COL_IN[1]
elif ESP32:
    # tools/wiring-esp32 --check compares these with hardware/wiring/ESP32.md. The screen's clock
    # and data on VSPI's own pins (18, 23), so SPI(2) drives them without the GPIO matrix. Nothing on
    # the flash (6-11), a WROVER's PSRAM (16, 17), the boot pins that can stop a boot (0, 2, 12) or
    # the input-only pins (34-39, no pull-ups). CS (5) and RST (15) are boot pins too, but only
    # ever high at reset, which is their default. No X: the knob's press does what it does.
    # LED: the blue one on GPIO2 of DOIT-style boards; an Espressif DevKitC has none.
    DC, CS, SCK, MOSI, RST, BL = 19, 5, 18, 23, 15, 4
    BUTTONS = {"A": 27, "B": 26, "Y": 13}
    SPI_ID, SDA, SCL, LED = 2, 21, 22, 2
if KEYBOARD:
    PANEL_W, PANEL_H = W, H = 240, 135
    MADCTL = 0x60           # MX|MV: landscape, the keyboard below the screen
    SPI_BAUD = 40_000_000
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
if KNOB and not KEYBOARD:
    # A on GP2 and B on GP3 as wired (BREADBOARD.md); read the other way round, because this knob
    # counted clockwise as anticlockwise (2026-09-27). Swapping the two wires does the same.
    # The ESP32 the same way: A wired to GPIO32, B to GPIO33 (ESP32.md).
    ENC_A, ENC_B, ENC_SW = (33, 32, 25) if ESP32 else (3, 2, 1)
    KEYS = dict(BUTTONS)    # the knob is knob.py's; GP2/GP3 are never joystick keys here
    MAINT = ENC_SW          # held at power-up: maintenance (main_console.py, main_dual.py)
elif not KEYBOARD:
    PANEL_W, PANEL_H = W, H = 240, 240
    MADCTL = 0x70
    SPI_BAUD = 62_500_000
    KEYS = dict(BUTTONS, up=2, down=18, left=16, right=20, press=3)
    MAINT = BUTTONS["B"]
if not KEYBOARD:
    SETUP = BUTTONS["Y"]    # held at power-up: Wi-Fi setup (boot.py, wifisetup.py)
BANDS = 8 if W * H * 2 > 45_000 else 1
X_OFF, Y_OFF = (PANEL_W - W) // 2, (PANEL_H - H) // 2
if KEYBOARD:
    BANDS = 5               # 135 rows as 5 bands of 27 (12,960 bytes); 8 would leave rows out
    X_OFF, Y_OFF = 40, 52   # where the 240x135 glass sits in the controller's RAM (bench, 2026-10-11)
SMALL = W < 200 or H < 200  # a screen too small for the console's 240x240 pages (quorum_ui_s.py)

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
