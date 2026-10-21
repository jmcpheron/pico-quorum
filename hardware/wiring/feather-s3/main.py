# Feather ESP32-S3 Reverse TFT: press a button, the ATECC608 does something. Read-only: no key is
# made, used or read, nothing is written or locked. Standalone; not part of the console image.
#   D0  32 random bytes from the chip's RNG, as hex and a colour grid
#   D1  SHA-256 on the chip, checked against MicroPython's hashlib
#   D2  the chip's self-test (RNG, ECDSA, ECDH, AES, SHA)
import sys
sys.path.insert(0, "/bench")
from machine import Pin
from binascii import hexlify
import hashlib, time
import tft
from tft import fb, text, rgb, W, H, BLACK, WHITE, GREY, RED, GREEN, YELLOW, BLUE
import atecc, chipcfg

d0 = Pin(0, Pin.IN, Pin.PULL_UP)      # low when pressed
d1 = Pin(1, Pin.IN, Pin.PULL_DOWN)    # high when pressed
d2 = Pin(2, Pin.IN, Pin.PULL_DOWN)

chip = atecc.ATECC608(sda=3, scl=4, addr=0x60)
head = ["", ""]
n_sha = 0


def header():
    try:
        cfg = chip.read_config_all()
        rev = chipcfg.REVISIONS.get(hexlify(chip.revision()).decode(), "?")
        head[0] = "%s %s" % (rev.replace("ATECC", ""), chipcfg.identify(cfg))
        head[1] = "%s  cfg %s data %s" % (hexlify(cfg[0:4] + cfg[8:13]).decode()[:10],
                                           "L" if cfg[87] == 0 else "o", "L" if cfg[86] == 0 else "o")
    except Exception as e:
        head[0], head[1] = "NO CHIP", str(e)[:30]


def frame(title, color):
    fb.fill(BLACK)
    text(head[0], 4, 3, YELLOW if head[0] != "NO CHIP" else RED, 1)
    text(head[1], 4, 13, GREY, 1)
    fb.hline(0, 23, W, GREY)
    text(title, 4, 28, color)
    fb.hline(0, H - 12, W, GREY)
    text("D0 random  D1 sha256  D2 test", 4, H - 9, GREY, 1)


def home():
    frame("PRESS A BUTTON", WHITE)
    try:
        text("counter 0  %d" % chip.counter(0), 4, 52, BLUE)
        text("counter 1  %d" % chip.counter(1), 4, 72, BLUE)
    except Exception as e:
        text(str(e)[:28], 4, 52, RED, 1)
    tft.show()


def do_random():
    t = time.ticks_ms()
    r = chip.random()
    ms = time.ticks_diff(time.ticks_ms(), t)
    frame("RANDOM %d ms" % ms, GREEN)
    h = hexlify(r).decode()
    for i in range(4):
        text(h[i * 16:(i + 1) * 16], 4, 50 + i * 15, WHITE, 1)
    for i, b in enumerate(r):         # each byte a cell, 3-3-2 colour
        x, y = 140 + (i % 8) * 12, 48 + (i // 8) * 15
        fb.fill_rect(x, y, 11, 14, rgb(b & 0xE0, (b << 3) & 0xE0, (b << 6) & 0xC0))
    if r == bytes([0xFF, 0xFF, 0, 0] * 8):
        text("test pattern: config open", 4, 110, YELLOW, 1)
    tft.show()


def do_sha():
    global n_sha
    n_sha += 1
    msg = b"PicoQuorum %d" % n_sha
    t = time.ticks_ms()
    h = chip.sha256(msg)
    ms = time.ticks_diff(time.ticks_ms(), t)
    ok = h == hashlib.sha256(msg).digest()
    frame("SHA256 %d ms" % ms, BLUE)
    text(msg.decode(), 4, 48, WHITE, 1)
    x = hexlify(h).decode()
    for i in range(3):
        text(x[i * 22:(i + 1) * 22], 4, 60 + i * 10, WHITE, 1)
    text("MATCH" if ok else "MISMATCH", 4, 94, GREEN if ok else RED)
    tft.show()


TESTS = ("RNG", "VERIFY", "SIGN", "ECDH", "AES", "SHA")


def do_test():
    frame("SELF-TEST ...", YELLOW)
    tft.show()
    t = time.ticks_ms()
    r = chip.selftest()
    ms = time.ticks_diff(time.ticks_ms(), t)
    frame("SELF-TEST %d ms" % ms, GREEN if r == 0 else RED)
    for i, name in enumerate(TESTS):
        ok = not r & (1 << i)
        text("%-6s %s" % (name, "ok" if ok else "FAIL"), 4 + (i // 3) * 120, 50 + (i % 3) * 20, GREEN if ok else RED)
    tft.show()


def run(job):
    try:
        job()
    except Exception as e:
        header()
        frame("CHIP ERROR", RED)
        text(str(e)[:29], 4, 52, WHITE, 1)
        text("check the plug, press again", 4, 66, GREY, 1)
        tft.show()


header()
run(home)
prev = (1, 0, 0)
while True:
    now = (d0(), d1(), d2())
    if now[0] == 0 and prev[0] == 1:
        run(do_random)
    elif now[1] and not prev[1]:
        run(do_sha)
    elif now[2] and not prev[2]:
        run(do_test)
    prev = now
    time.sleep_ms(30)
