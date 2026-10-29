# The QT Py cosigner's first check (hardware/builds/qtpy-cosigner/README.md): the screen, the three
# buttons and the key, before the console goes on. Read-only: no key is made, used or read, nothing
# is written or locked. Standalone; not part of the console image.
#   D0  the SDA pad (GPIO4), Reject and Back. Boot is not read
#   D1  the TX pad (GPIO32), Next
#   D2  the SCL pad (GPIO33), Sign. A press here scans the bus again and reads the key at 0x60
import sys
sys.path.insert(0, "/bench")
from machine import Pin
from binascii import hexlify
import time
import tft
from tft import fb, text, W, H, BLACK, WHITE, GREY, RED, GREEN, YELLOW, BLUE
import atecc, chipcfg

SDA, SCL, KEY = 22, 19, 0x60
KEYS = (("D0", 4), ("D1", 32), ("D2", 33))
pins = [Pin(n, Pin.IN, Pin.PULL_UP) for _, n in KEYS]

state = {"found": [], "key": [], "n": 0, "presses": [0, 0, 0]}


def lock(b):
    return "locked" if b == 0x00 else "open" if b == 0x55 else "%02x" % b


def scan():
    state["n"] += 1
    try:
        state["found"] = atecc.scan(SDA, SCL)
    except OSError:
        state["found"] = []
    state["key"] = []
    if KEY in state["found"]:
        try:
            chip = atecc.ATECC608(sda=SDA, scl=SCL, addr=KEY)
            cfg = chip.read_config_all()
            rev = chipcfg.REVISIONS.get(hexlify(chip.revision()).decode(), "?")
            state["key"] = [
                hexlify(cfg[0:4] + cfg[8:13]).decode(),
                rev.replace("ATECC", "") + " " + chipcfg.identify(cfg),
                "cfg %s data %s" % (lock(cfg[87]), lock(cfg[86])),
            ]
        except (atecc.AteccError, OSError) as e:
            state["key"] = ["error: " + str(e)]
    print("i2c", [hex(a) for a in state["found"]], "key", state["key"])


def draw():
    fb.fill(BLACK)
    text("QT PY COSIGNER", 2, 2, WHITE, 1)
    text("%d" % state["n"], W - 18, 2, GREY, 1)
    fb.hline(0, 11, W, GREY)
    for i, (name, n) in enumerate(KEYS):
        down = pins[i]() == 0
        x = 3 + i * 52
        fb.rect(x, 14, 50, 34, YELLOW if down else GREY, down)
        text(name, x + 9, 17, BLACK if down else WHITE)
        text("x%d" % state["presses"][i], x + 4, 37, BLACK if down else GREY, 1)
    found = " ".join("%02x" % a for a in state["found"]) or "none"
    text(("i2c " + found)[:20], 2, 52, BLUE, 1)
    y = 64
    if state["key"]:
        for line in state["key"]:
            text(line[:20], 2, y, RED if line.startswith("error") else GREEN, 1)
            y += 10
    else:
        text("no key at 0x60", 2, y, RED, 1)
    # four bars to check the colours: red, green, blue, white
    for i, c in enumerate((RED, GREEN, BLUE, WHITE)):
        fb.fill_rect(i * W // 4, 96, W // 4, 14, c)
    fb.hline(0, 113, W, GREY)
    text("held: box   D2: scan", 2, 117, GREY, 1)
    tft.show()


def run():
    scan()
    draw()
    last = [1, 1, 1]
    while True:
        now = [p() for p in pins]
        if now != last:
            for i in range(3):
                if now[i] == 0 and last[i] == 1:
                    state["presses"][i] += 1
            if now[2] == 0 and last[2] == 1:
                scan()
            draw()
            print(" ".join("%s %s" % (KEYS[i][0], "down" if now[i] == 0 else "up") for i in range(3)))
            last = now
        time.sleep_ms(30)
