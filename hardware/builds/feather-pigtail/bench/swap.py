# Feather pigtail: which key is plugged in? D2 reads again, so keys can be swapped and compared.
# Read-only: no key is made, used or read, nothing is written or locked. Standalone; not part of the
# console image. hardware/builds/feather-pigtail/README.md says how to wire and copy it.
#   D2  scan again    D1  the slot table    D0  back to the summary
import sys
sys.path.insert(0, "/bench")
from machine import Pin
from binascii import hexlify
import time
import tft
from tft import fb, text, W, H, BLACK, WHITE, GREY, RED, GREEN, YELLOW, BLUE
import atecc, chipcfg

SDA, SCL, KEY, GAUGE = 3, 4, 0x60, 0x36
NAMES = {KEY: "key", GAUGE: "gauge"}

d0 = Pin(0, Pin.IN, Pin.PULL_UP)      # low when pressed
d1 = Pin(1, Pin.IN, Pin.PULL_DOWN)    # high when pressed
d2 = Pin(2, Pin.IN, Pin.PULL_DOWN)

state = {"n": 0, "last": None, "found": [], "key": None}


def read_key():
    """What the key at 0x60 says about itself, by reads only: the config zone, Info, and slot 0's
    public key (GenKey's public-key mode, which writes nothing)."""
    chip = atecc.ATECC608(sda=SDA, scl=SCL, addr=KEY)
    cfg = chip.read_config_all()
    k = {"serial": hexlify(cfg[0:4] + cfg[8:13]).decode(),
         "rev": chipcfg.REVISIONS.get(hexlify(chip.revision()).decode(), "?").replace("ATECC", ""),
         "profile": chipcfg.identify(cfg), "cfg_locked": cfg[87] == 0, "data_locked": cfg[86] == 0,
         "slots": chip.slots(cfg, probe=False), "fp": None}
    s0 = k["slots"][0]
    if k["cfg_locked"] and s0["kind"] == "P256" and s0["pubInfo"]:
        try:
            k["fp"] = "%08x" % (chip.pubkey(0)[0] >> 224)
        except atecc.AteccError:
            pass
    return k


def scan():
    state["n"] += 1
    try:
        state["found"] = atecc.scan(SDA, SCL)
    except OSError:
        state["found"] = []
    state["key"] = None
    if KEY in state["found"]:
        try:
            state["key"] = read_key()
        except (atecc.AteccError, OSError) as e:
            state["key"] = {"error": str(e)}
    k = state["key"]
    serial = k.get("serial") if k else None
    state["new"] = serial is not None and serial != state["last"]
    if serial:
        state["last"] = serial


def frame(title, color):
    fb.fill(BLACK)
    text(title, 4, 3, color)
    text("scan %d" % state["n"], W - 60, 7, GREY, 1)
    fb.hline(0, 21, W, GREY)
    fb.hline(0, H - 12, W, GREY)
    text("D2 scan  D1 slots  D0 back", 4, H - 9, GREY, 1)


def addrs():
    s = " ".join("%02x%s" % (a, "" if a not in NAMES else "=" + NAMES[a]) for a in state["found"])
    return ("i2c " + (s or "none"))[:29]


def summary():
    k = state["key"]
    if not k:
        frame("NO KEY", RED)
        text("nothing at 0x60", 4, 28, WHITE, 1)
        text(addrs(), 4, 40, GREY, 1)
        text("check the plug, press D2", 4, 60, YELLOW, 1)
    elif "error" in k:
        frame("KEY ERROR", RED)
        text(k["error"][:29], 4, 28, WHITE, 1)
        text(addrs(), 4, 40, GREY, 1)
        text("check the plug, press D2", 4, 60, YELLOW, 1)
    else:
        frame("NEW KEY" if state["new"] else "SAME KEY", GREEN if state["new"] else BLUE)
        text(k["serial"], 4, 28, WHITE, 1)
        text("%s  %s" % (k["rev"], k["profile"]), 4, 40, YELLOW, 1)
        text("config %s  data %s" % ("locked" if k["cfg_locked"] else "open",
                                     "locked" if k["data_locked"] else "open"), 4, 52, WHITE, 1)
        if k["fp"]:
            text("slot 0  " + k["fp"], 4, 64, GREEN, 1)
        else:
            text("no key in slot 0", 4, 64, GREY, 1)
        text(addrs(), 4, 80, GREY, 1)
    tft.show()


def slot_table():
    k = state["key"]
    if not k or "error" in k:
        summary()
        return
    frame("SLOTS", WHITE)
    for s in k["slots"]:                # L locked, G GenKey may fill it, E signs outside digests
        flags = ("L" if s["locked"] else "") + ("G" if s["genKey"] else "") + ("E" if s["extSign"] else "")
        n = s["slot"]
        text("%2d %-4s %s" % (n, s["kind"], flags), 4 + (n // 8) * 120, 26 + (n % 8) * 11,
             GREEN if s["kind"] == "P256" else WHITE, 1)
    tft.show()


def busy():
    frame("SCANNING", YELLOW)
    tft.show()


def run():
    busy()
    scan()
    summary()
    prev = (1, 0, 0)
    while True:
        now = (d0(), d1(), d2())
        if now[2] and not prev[2]:
            busy()
            scan()
            summary()
        elif now[1] and not prev[1]:
            slot_table()
        elif now[0] == 0 and prev[0] == 1:
            summary()
        prev = now
        time.sleep_ms(30)
