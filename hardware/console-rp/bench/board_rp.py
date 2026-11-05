# Bench only: firmware/board.py's answers for a console-rp, so the console's own lcd.py, splash.py and
# bootmark.py run on the board unchanged (bootanim.py). Put on the board as /board.py with put.py.
# Not the console-rp's board profile: that goes in firmware/board.py when the firmware is written.
# Pins from PINS.md; the screen as the Feather's (BRINGUP.md: MADCTL 0x60, RAM at 40, 53, inversion on).
import time

BOARD, SCREEN = "console-rp", None
ESP32 = S3 = False
KNOB = DIAL = False
THREE = True
DC, CS, SCK, MOSI, RST, BL = 8, 9, 10, 11, 12, 13
BUTTONS = {"D0": 2, "D1": 3, "D2": 6}        # to GND, pulled up inside, pressed low
HIGH = ()
SPI_ID, SDA, SCL, LED = 1, 4, 5, 25
NOT_KEYS, POWER = (), None
NAMES = {"D0": "D0", "D1": "D1", "D2": "D2"}
PANEL_W, PANEL_H = W, H = 240, 135
MADCTL, RAM_X, RAM_Y = 0x60, 40, 53
SPI_BAUD = 24_000_000                       # SPI1's most on the RP2350 (HORSEPOWER.md)
INIT = "plain"
KEYS = dict(BUTTONS)
MAINT, SETUP = BUTTONS["D1"], BUTTONS["D2"]
RAIL_Y = None
BANDS = 1
X_OFF = Y_OFF = 0
SMALL = True
EPOCH = 0


def key_down(pin):
    from machine import Pin
    return Pin(pin, Pin.IN, Pin.PULL_UP).value() == 0


def unix():
    return time.time() + EPOCH


def timer(job, period, callback, hard=False):
    from machine import Timer
    return Timer(period=period, mode=Timer.PERIODIC, callback=callback, hard=hard)
