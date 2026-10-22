# Feather ESP32-S3 Reverse TFT: the checks before the console's board profile, run from RAM with
# `mpremote run` (needs /bench/tft.py on the board). Reads only: nothing is written to the chip or
# the battery gauge.
#   - the screen in 9 numbered bands of 15 rows, to see which rows each button sits beside
#   - each button's raw level with no pull of ours, and with the pull the profile will use
#   - the LED on GPIO13, blinked
#   - the MAX17048 gauge: VCELL, SOC, VERSION
import sys
sys.path.insert(0, "/bench")
from machine import Pin, SoftI2C
import time
import tft
from tft import fb, text, rgb, W, H, BLACK, WHITE

SECONDS = 180
BANDS = [rgb(170, 40, 40), rgb(40, 110, 170)]


def bands(note=""):
    for i in range(9):
        fb.fill_rect(0, i * 15, W, 15, BANDS[i % 2])
        text("%d" % i, 4, i * 15 + 4, WHITE, 1)
        text("%3d-%3d" % (i * 15, i * 15 + 14), 20, i * 15 + 4, WHITE, 1)
    text(note[:20], 90, 4, WHITE, 1)


i2c = SoftI2C(sda=Pin(3, Pin.IN, Pin.PULL_UP), scl=Pin(4, Pin.IN, Pin.PULL_UP), freq=100_000)


def gauge():
    try:
        v = i2c.readfrom_mem(0x36, 0x02, 2)
        s = i2c.readfrom_mem(0x36, 0x04, 2)
        ver = i2c.readfrom_mem(0x36, 0x08, 2)
        return "%.3f V  %.1f %%  version %04x" % ((v[0] << 8 | v[1]) * 78.125e-6, s[0] + s[1] / 256, ver[0] << 8 | ver[1])
    except OSError as e:
        return "gauge: %r" % e


print("buttons with no pull of ours:", [Pin(n, Pin.IN).value() for n in (0, 1, 2)])
d0 = Pin(0, Pin.IN, Pin.PULL_UP)
d1 = Pin(1, Pin.IN, Pin.PULL_DOWN)
d2 = Pin(2, Pin.IN, Pin.PULL_DOWN)
print("with D0 pull-up, D1/D2 pull-down, at rest:", d0(), d1(), d2())
print("gauge:", gauge())

led = Pin(13, Pin.OUT, value=0)
for _ in range(5):
    led(1); time.sleep_ms(250); led(0); time.sleep_ms(250)
print("LED on GPIO13 blinked 5 times")

bands("press D0 D1 D2")
tft.show()
print("watching the buttons for %d s" % SECONDS)
prev = (d0(), d1(), d2())
t0 = time.ticks_ms()
last_g = t0
while time.ticks_diff(time.ticks_ms(), t0) < SECONDS * 1000:
    now = (d0(), d1(), d2())
    if now != prev:
        ms = time.ticks_diff(time.ticks_ms(), t0)
        down = [n for n, v, act in zip(("D0", "D1", "D2"), now, (0, 1, 1)) if v == act]
        print("%6d ms  levels D0 %d D1 %d D2 %d  pressed: %s" % (ms, now[0], now[1], now[2], " ".join(down) or "-"))
        bands("down: " + (" ".join(down) or "-"))
        tft.show()
        prev = now
    if time.ticks_diff(time.ticks_ms(), last_g) > 30000:
        print("gauge:", gauge())
        last_g = time.ticks_ms()
    time.sleep_ms(20)
print("gauge:", gauge())
print("done")
