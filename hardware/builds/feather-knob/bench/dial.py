# The knob Feather's first check (hardware/builds/feather-knob/README.md): the screen, the knob, Boot
# and the key, before the console goes on. Read-only: no key is made, used or read, nothing is
# written or locked. Standalone; not part of the console image.
#   turn   the knob's raw quadrature steps and its detents (4 steps a detent on most EC11s)
#   push   scans the bus again and reads the key at 0x60
#   Boot   shown while held (never at power-up: it starts the ROM bootloader)
import sys
sys.path.insert(0, "/bench")
from machine import Pin, Encoder
from binascii import hexlify
import time
import tft
from tft import fb, text, W, H, BLACK, WHITE, GREY, RED, GREEN, YELLOW, BLUE
import atecc, chipcfg

SDA, SCL, KEY = 42, 41, 0x60
ENC_A, ENC_B, ENC_SW = 17, 16, 15     # A1, A2, A3: board.py's feather-knob profile

boot = Pin(0, Pin.IN, Pin.PULL_UP)
push = Pin(ENC_SW, Pin.IN, Pin.PULL_UP)
enc = Encoder(0, Pin(ENC_A, Pin.IN, Pin.PULL_UP), Pin(ENC_B, Pin.IN, Pin.PULL_UP), phases=4, filter_ns=10_000)

state = {"steps": 0, "moved": 0, "found": [], "key": "", "n": 0}


def scan():
    state["n"] += 1
    try:
        state["found"] = atecc.scan(SDA, SCL)
    except OSError:
        state["found"] = []
    state["key"] = ""
    if KEY in state["found"]:
        try:
            chip = atecc.ATECC608(sda=SDA, scl=SCL, addr=KEY)
            cfg = chip.read_config_all()
            rev = chipcfg.REVISIONS.get(hexlify(chip.revision()).decode(), "?").replace("ATECC", "")
            state["key"] = "%s %s %s" % (hexlify(cfg[0:4] + cfg[8:13]).decode()[-8:], rev, chipcfg.identify(cfg))
        except (atecc.AteccError, OSError) as e:
            state["key"] = "error: " + str(e)


def draw():
    s = state["steps"]
    fb.fill(BLACK)
    text("KNOB", 4, 3, WHITE)
    text("scan %d" % state["n"], W - 60, 7, GREY, 1)
    fb.hline(0, 21, W, GREY)
    text("detents %+d" % int(s / 4), 4, 26, GREEN)
    text("steps %+d, last move %+d" % (s, state["moved"]), 4, 44, GREY, 1)
    text("push " + ("DOWN" if push() == 0 else "up"), 4, 56, YELLOW if push() == 0 else WHITE, 1)
    text("Boot " + ("DOWN" if boot() == 0 else "up"), 120, 56, YELLOW if boot() == 0 else WHITE, 1)
    found = " ".join("%02x" % a for a in state["found"]) or "none"
    text(("i2c " + found)[:29], 4, 70, BLUE, 1)
    if state["key"]:
        text(("key " + state["key"])[:29], 4, 84, GREEN if not state["key"].startswith("error") else RED, 1)
    else:
        text("no key at 0x60", 4, 84, RED, 1)
    fb.hline(0, H - 12, W, GREY)
    text("turn: count   push: scan", 4, H - 9, GREY, 1)
    tft.show()


def tick(last):
    """One look at the knob and the buttons; last is (push, Boot) as they were. Returns them now."""
    d = enc.value(0)                    # read and zero in one call
    now = (push(), boot())
    if d:
        state["steps"] += d
        state["moved"] = d
    if now[0] == 0 and last[0] == 1:
        scan()
    if d or now != last:
        draw()
        print("steps", state["steps"], "push", now[0] == 0, "boot", now[1] == 0)
    return now


def run():
    scan()
    draw()
    last = (1, 1)
    while True:
        last = tick(last)
        time.sleep_ms(30)
