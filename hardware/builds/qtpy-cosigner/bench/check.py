# The QT Py cosigner's first check (hardware/builds/qtpy-cosigner/README.md): the screen, the three
# buttons and the key, before the console goes on. Read-only: no key is made or used, nothing is
# written or locked. Slot 0's public key is read (GenKey's public mode, as the console does) for its
# owner address: the Safe passkey signer proxy webauthn.py works out, with its blockie and QR code.
# Standalone; not part of the console image.
#   D0  the SDA pad (GPIO4), Reject and Back. Boot is not read
#   D1  the TX pad (GPIO32), Next: the owner page and back
#   D2  the SCL pad (GPIO33), Sign. A press here scans the bus again and reads the key at 0x60
import sys
sys.path.insert(0, "/bench")
from machine import Pin
from binascii import hexlify
import time
import tft
sys.modules["lcd"] = tft              # blockies.draw imports lcd.color; this is the bench's
from tft import fb, text, W, H, BLACK, WHITE, GREY, RED, GREEN, YELLOW, BLUE
import atecc, chipcfg, blockies, qrcode, webauthn
from keccak import keccak256
from quorum_cfg import CFG

SDA, SCL, KEY = 22, 19, 0x60
KEYS = (("D0", 4), ("D1", 32), ("D2", 33))
pins = [Pin(n, Pin.IN, Pin.PULL_UP) for _, n in KEYS]

state = {"found": [], "key": [], "n": 0, "presses": [0, 0, 0], "owner": None, "page": 0}
# Keys on record (docs/STATUS.md): serial -> slot 0's owner address
KNOWN = {"0123f3acfd2a826bee": ("chip #1", "0x2843705391b7e2cf06b0b964b532ad9891535e53"),
         "01230e6b8fa23e70ee": ("chip #2", "0x99edaccad92537b9146dd0804635bc6def7f6b88")}


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
            state["serial"] = hexlify(cfg[0:4] + cfg[8:13]).decode()
            state["key"] = [
                state["serial"],
                rev.replace("ATECC", "") + " " + chipcfg.identify(cfg),
                "cfg %s data %s" % (lock(cfg[87]), lock(cfg[86])),
            ]
            qx, qy = chip.pubkey(0)
            state["owner"] = checksum(webauthn.owner_address(qx, qy, CFG["signer"]))
        except (atecc.AteccError, OSError) as e:
            state["key"] = ["error: " + str(e)]
    print("i2c", [hex(a) for a in state["found"]], "key", state["key"], "owner", state["owner"])


def checksum(a):
    """EIP-55 mixed case, as txservice.checksum."""
    a = a.lower().replace("0x", "")
    h = hexlify(keccak256(a.encode())).decode()
    return "0x" + "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(a))


def draw_owner():
    """Slot 0's owner address: its start and end, its blockie, whether it is the one on record for
    this serial, and the whole address as a QR code (29 modules at 3 px)."""
    fb.fill(BLACK)
    a = state["owner"]
    if not a:
        text("no owner", 4, 4, RED)
        text("no key in slot 0", 4, 28, GREY, 1)
        tft.show()
        return
    n, rows = qrcode.encode(a)
    k = 3
    box = (n + 4) * k
    x0, y0 = W - box, 0
    fb.fill_rect(x0, y0, box, box, WHITE)
    for r in range(n):
        for c in range(n):
            if rows[r] >> c & 1:
                fb.fill_rect(x0 + (c + 2) * k, y0 + (r + 2) * k, k, k, BLACK)
    text("OWNER", 2, 2, WHITE, 1)
    text(a[:6], 2, 16, GREY, 1)
    text(".." + a[-4:], 2, 26, GREY, 1)
    blockies.draw(fb, a.lower(), 2, 40, 3, color=tft.rgb)
    name, want = KNOWN.get(state.get("serial"), (None, None))
    if want:
        ok = want == a.lower()
        text(name, 2, 70, GREEN if ok else RED, 1)
        text("match" if ok else "DIFFERS", 2, 80, GREEN if ok else RED, 1)
    else:
        text("not on", 2, 70, YELLOW, 1)
        text("record", 2, 80, YELLOW, 1)
    text(a[2:22], 0, H - 20, WHITE, 1)
    text(a[22:], 0, H - 10, WHITE, 1)
    tft.show()


def draw():
    if state["page"]:
        draw_owner()
        return
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
    text("D1: owner   D2: scan", 2, 117, GREY, 1)
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
            if now[1] == 0 and last[1] == 1:
                state["page"] ^= 1
            if now[2] == 0 and last[2] == 1:
                scan()
            draw()
            print(" ".join("%s %s" % (KEYS[i][0], "down" if now[i] == 0 else "up") for i in range(3)))
            last = now
        time.sleep_ms(30)
