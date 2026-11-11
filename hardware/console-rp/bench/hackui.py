# console-rp: a reimagined console UI, after the verify-code loader (loaders.py): a terminal on a CRT.
# Bench only, a prototype to try with the board's buttons; not the console's firmware. Two made-up
# transactions in a queue, a USDC send and a red page (an owner added). The Safe transaction hash is
# the real one, worked out here by firmware/safe_tx.py: while it runs, the screen shows the live
# Keccak state, whose first four lanes become the hash when the last pass ends.
#
# The buttons under the screen, as a VCR's: D0 ■ stop = Reject (one press), D1 ▶ play = Next, D2 ● rec
# = Sign, held 2 s (3 s on a red page), lit only once every page has been seen. Nothing here asks the
# key for anything: "signed" is a demo screen and says so.
#   put.py PORT firmware/qf_mono13.bin (with what bootanim.py and loaders.py need), then
#   rawrepl.py PORT hackui.py --follow 5      (RESET stops it)
import gc
import os
import math
import time
import random
import binascii
import machine
import framebuf
from array import array
from machine import Pin
import lcd as L
import fonts as F
import blockies
import keccak
import safe_tx

d = L.LCD()
W, H = L.W, L.H
BUF = d.buffer
BODY0, FOOT = 14, 116

NORMAL = {"bg": (6, 8, 12), "scan": (13, 16, 22), "ink": (232, 236, 240), "mute": (118, 128, 144),
          "dim": (44, 50, 62), "acc": (122, 146, 255), "ok": (52, 199, 89), "warn": (255, 184, 48),
          "bad": (255, 92, 84), "cyan": (0, 220, 255), "mag": (255, 0, 170)}
RED = dict(NORMAL, bg=(36, 4, 7), scan=(52, 9, 12), ink=(255, 222, 218), mute=(222, 128, 120),
           dim=(110, 34, 36), acc=(255, 92, 84))
th = NORMAL


def c(k):
    return L.color(*(th[k] if isinstance(k, str) else k))


def t8(s, x, y, k="ink"):
    d.text(s, x, y, c(k))


def tf(s, x, y, font, k="ink"):
    return F.text(d, s, x, y, font, th[k] if isinstance(k, str) else k, th["bg"])


def push_rows(y0, y1, dx=0):
    """Rows y0..y1 of the frame, whole width (one piece of the buffer), dx pixels sideways. The
    panel's RAM is 40 columns wider each side than the window, so |dx| <= 40 needs no clipping."""
    d._window(dx, y0, W, y1 - y0)
    d.dc(1); d.cs(0); d.spi.write(memoryview(BUF)[y0 * W * 2:y1 * W * 2]); d.cs(1)


GLITCH_MS = 55                          # how long each torn frame stays up


def glitch(frames=5, amp=10, y0=0, y1=H):
    """The frame in torn slices, calming frame by frame (fewer slices, smaller jumps), then whole."""
    for f in range(frames):
        calm = 1 - f / frames
        a = max(1, int(amp * calm))
        y = y0
        while y < y1:
            e = min(y1, y + random.randint(3, 16))
            push_rows(y, e, random.randint(-a, a) if random.random() < 0.3 * calm + 0.05 else 0)
            y = e
        time.sleep_ms(GLITCH_MS)
    push_rows(y0, y1)


# ----------------------------------------------------------------------------- the two effects
# The UI's glitch has two meanings (glitchfx.py compared three; FX1 and FX3 stayed):
#   tear_in  FX1: something arrives or changes. Torn slices of the new page (PAGE) and what is on the
#            screen (BUF, usually noise) trade places and jump sideways, calming until the page holds.
#            Harder for a red page.
#   lock_in  FX3: worked out here, and checked. The page rolls like a set losing vertical hold, a noise
#            bar at the seam, overshoots, and locks: the verify code, a key's address, Signed.
# Both start from PAGE (the page, drawn whole) and BUF (what is on the screen), and leave BUF = PAGE.
# refresh() redraws the noise in BUF now and then, so it keeps moving underneath.
def push_buf(src, sy, h, y, dx=0):
    d._window(dx, y, W, h)
    d.dc(1); d.cs(0); d.spi.write(memoryview(src)[sy * W * 2:(sy + h) * W * 2]); d.cs(1)


def tear_in(refresh=None, n=10, amp=22, y0=BODY0, y1=FOOT, ms=40):
    span_h = y1 - y0
    for f in range(n):
        p = f / (n - 1)
        if refresh and f % 4 == 0:
            refresh()
        a = int(amp * (1 - p))
        y = y0
        while y < y1:
            e = min(y1, y + random.randint(2, 11))
            r = random.random()
            if r < p ** 0.6:
                src, sy = PAGE, y
            elif r < p ** 0.6 + 0.15 * (1 - p):
                src, sy = PAGE, y0 + random.randint(0, span_h - (e - y))   # a slice from the wrong row
            else:
                src, sy = BUF, y
            push_buf(src, sy, e - y, y, random.randint(-a, a) if a and random.random() < 0.55 * (1 - p) + 0.05 else 0)
            y = e
        time.sleep_ms(ms)
    BUF[:] = PAGE
    push_rows(y0, y1)


def lock_in(refresh=None, dur=1400, y0=BODY0, y1=FOOT):
    span_h = y1 - y0
    t0, k = time.ticks_ms(), 0
    while True:
        t = time.ticks_diff(time.ticks_ms(), t0)
        if t >= dur:
            break
        u = t / dur
        roll = int(span_h * 0.9 * math.exp(-3.2 * u) * math.cos(9 * u))    # damped: overshoots, then holds
        jit = int(14 * (1 - u) ** 2)
        bar = max(0, int(10 * (1 - u)))
        y = y0
        while y < y1:
            sy = y0 + (y - y0 + roll) % span_h
            run = min(y1 - y, y0 + span_h - sy, random.randint(3, 9))
            dx = random.randint(-jit, jit) if jit and random.random() < 0.6 else 0
            if sy - y0 < bar:
                push_buf(BUF, y, run, y, dx)        # the bar at the seam: noise
            else:
                push_buf(PAGE, sy, run, y, dx)
            y += run
        k += 1
        if refresh and k % 5 == 0:
            refresh()
        time.sleep_ms(30)
    BUF[:] = PAGE
    push_rows(y0, y1)
    for dx in (3, -2, 1):               # one last twitch as it locks
        push_rows(y0, y1, dx)
        time.sleep_ms(50)
    push_rows(y0, y1)


def noise(pub=None, shown=0, y_from=0):
    """The body as a 30x12 grid of hex from os.urandom, read now, each digit shaded by its value; the
    first `shown` cells are pub's digits instead, in blue."""
    raw = binascii.hexlify(os.urandom(COLS * ROWS // 2)).decode()
    bg(max(BODY0, y_from), FOOT)
    for r in range(ROWS):
        y = ROW0 + 8 * r
        if y < y_from:
            continue
        rows = ["", "", "", "", ""]
        for col in range(COLS):
            i = r * COLS + col
            if i < shown:
                ch, k = pub[i], 4 if i >= shown - 6 else 3
            else:
                ch = raw[i]
                v = int(ch, 16)
                k = 0 if v < 6 else 1 if v < 11 else 2
            for j in range(5):
                rows[j] += ch if j == k else " "
        for j, rgb in enumerate(GREYS + (BLUE, BLUE_HI)):
            if rows[j].strip():
                d.text(rows[j], 0, y, L.color(*rgb))


def arrive(draw, *args, fx="tear", strong=False):
    """draw(*args) as a whole page, arriving out of fresh noise: torn in (FX1) or locked in (FX3)."""
    draw(*args)
    PAGE[:] = BUF
    push_rows(0, BODY0)
    push_rows(FOOT, H)
    noise()
    push_rows(BODY0, FOOT)
    time.sleep_ms(120)
    if fx == "lock":
        lock_in(noise)
    else:
        tear_in(noise, n=12 if strong else 9, amp=34 if strong else 22)


def bg(y0=0, y1=H):
    d.fill_rect(0, y0, W, y1 - y0, c("bg"))
    for y in range(max(y0, BODY0 + 1), min(y1, FOOT), 3):
        d.hline(0, y, W, c("scan"))


def header(left, right=""):
    if th is RED:
        d.fill_rect(0, 0, W, 13, c("bad"))
        d.text(left, 3, 3, c("bg"))
        d.text(right, W - 3 - 8 * len(right), 3, c("bg"))
    else:
        d.fill_rect(0, 0, W, 13, c("bg"))
        t8(left, 3, 3, "ink")
        t8(right, W - 3 - 8 * len(right), 3, "mute")
        d.hline(0, 13, W, c("dim"))


# ----------------------------------------------------------------------------- the three buttons
def sq(x, y, k):
    d.fill_rect(x, y + 1, 9, 9, c(k))


def tri(x, y, k):
    d.poly(x, y, array("h", [0, 0, 0, 10, 9, 5]), c(k), True)


def ring(cx, cy, frac, k):
    n = 20
    for i in range(int(n * frac)):
        a = -1.5708 + 6.2832 * i / n
        d.pixel(int(cx + 9 * _cos(a)), int(cy + 9 * _sin(a)), c(k))
        d.pixel(int(cx + 8 * _cos(a)), int(cy + 8 * _sin(a)), c(k))


def circ(x, y, k, frac=None):
    d.ellipse(x + 5, y + 5, 5, 5, c(k), True)
    if frac:
        ring(x + 5, y + 5, frac, k)


_cos, _sin = math.cos, math.sin
SHAPES = (sq, tri, circ)


def footer(slots, hold=None):
    """slots: three (label, colour) or None, for D0 ■, D1 ▶, D2 ●. hold: Sign's fraction held."""
    d.fill_rect(0, FOOT, W, H - FOOT, c("bg"))
    d.hline(0, FOOT, W, c("dim"))
    for i in range(3):
        x0 = i * 80
        if i:
            d.vline(x0, FOOT + 3, H - FOOT - 6, c("dim"))
        s = slots[i]
        k = s[1] if s else "dim"
        if i == 2:
            circ(x0 + 10, FOOT + 5, k, hold)
        else:
            SHAPES[i](x0 + 10, FOOT + 5, k)
        if s:
            t8(s[0], x0 + 26, FOOT + 7, k)


# ----------------------------------------------------------------------------- the transactions
SAFE = "0x7a3f5c2e9b1d4a6f8c0e2b4d6f8a1c3e5b7d9f02"
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
CAROL = "0x4b2e8f17c9a3d5e6f7081a2b3c4d5e6f7a8b9c0d"
NEWOWNER = "0xdeadbeef00000000000000000000000000beef42"


def pad(a):
    return "0" * 24 + a[2:] if isinstance(a, str) else "%064x" % a


TXS = [
    {"n": 7, "red": False, "title": "SEND 1,000 USDC", "who": CAROL, "to": USDC,
     "data": "0xa9059cbb" + pad(CAROL) + pad(1_000_000_000), "have": 1,
     "call": "transfer(addr,uint)", "target": "USDC 0x8335..2913"},
    {"n": 8, "red": True, "title": "ADD OWNER", "who": NEWOWNER, "to": SAFE,
     "data": "0x0d582f13" + pad(NEWOWNER) + pad(2), "have": 0,
     "call": "addOwnerWithThreshold", "target": "THE SAFE ITSELF"},
]
for t in TXS:
    t["hash"], t["state"] = None, None


def short(a):
    return a[:6] + "…" + a[-4:]


# ----------------------------------------------------------------------------- the hash, live
live = {"A": None, "n": 0, "busy": False}
_f = keccak._f


def _f_watched(A):
    live["A"] = A
    live["n"] += 1
    _f(A)


keccak._f = _f_watched                  # keccak256 finds _f by name on every block
STAGE = {1: "DATA", 2: "STRUCT", 3: "STRUCT", 4: "STRUCT", 5: "DOMAIN", 6: "FINAL"}
HEX = "0123456789abcdef"
HX, HY = 8, 32                          # the four rows of the hash


def lanes_hex():
    A = live["A"]
    if A is None:
        return "".join(HEX[random.getrandbits(4)] for _ in range(64))
    return "".join(binascii.hexlify(A[i][0].to_bytes(8, "little")).decode() for i in range(4))


def hash_rows(h, k="ink", locked=64, ab=False):
    """The 64 hex digits as four rows of 4 x 4, the first `locked` of them settled."""
    cw = F.width("0", "mono13")
    for r in range(4):
        x = HX
        for g in range(4):
            i0 = r * 16 + g * 4
            s = "".join(h[i] if i < locked else HEX[random.getrandbits(4)] for i in range(i0, i0 + 4))
            if ab and random.random() < 0.5:
                tf(s, x - 2, HY + 15 * r, "mono13", "cyan")
                tf(s, x + 2, HY + 15 * r, "mono13", "mag")
            tf(s, x, HY + 15 * r, "mono13", k)
            x += cw * 4 + cw
    return cw


def churn(_t=None):
    if live["busy"]:
        return
    live["busy"] = True
    try:
        n = live["n"]
        bg(HY - 2, 112)
        hash_rows(lanes_hex(), "acc")
        t8("PASS %d/6  %s" % (n, STAGE.get(n, "")), HX, 94, "mute")
        d.fill_rect(HX, 106, 224, 3, c("dim"))
        d.fill_rect(HX, 106, 224 * min(n, 6) // 6, 3, c("acc"))
        push_rows(HY - 2, 112)
    except Exception as e:
        print("churn:", e)
    finally:
        live["busy"] = False


def compute(tx):
    """The real safeTxHash, the screen showing the sponge as it goes. -> hex."""
    live["A"], live["n"] = None, 0
    safe_tx._domain_cache.clear()
    tm = machine.Timer(period=60, mode=machine.Timer.PERIODIC, callback=churn)
    t0 = time.ticks_ms()
    try:
        h = safe_tx.safe_tx_hash(8453, SAFE, tx["to"], 0, tx["data"], 0, nonce=tx["n"])
    finally:
        tm.deinit()
    while live["busy"]:
        pass
    ms = time.ticks_diff(time.ticks_ms(), t0)
    hx = binascii.hexlify(h).decode()
    print("hash #%d %s (%d ms, %d passes)" % (tx["n"], hx, ms, live["n"]))
    tx["ms"] = ms
    return hx


def reveal(hx):
    """The settled hash glitching into place."""
    n = 16
    for k in range(n):
        calm = 1 - k / n
        bg(HY - 2, 112)
        hash_rows(hx, "ink", locked=64 * (k + 1) // n, ab=random.random() < calm)
        a = max(1, int(10 * calm))
        y = HY - 2
        while y < 112:
            e = min(112, y + random.randint(3, 12))
            push_rows(y, e, random.randint(-a, a) if random.random() < 0.3 * calm else 0)
            y = e
        time.sleep_ms(60)
    bg(HY - 2, 112)
    hash_rows(hx, "ink")


# ----------------------------------------------------------------------------- screens
def draw_queue(sel):
    global th
    th = NORMAL
    bg()
    header("> QUEUE", "BASE 8453")
    for i, tx in enumerate(TXS):
        y = 18 + 34 * i
        on = i == sel
        if on:
            d.fill_rect(0, y, 3, 30, c("bad" if tx["red"] else "acc"))
        blockies.draw(d, tx["who"], 9, y + 3, 3)
        tf("#%d %s" % (tx["n"], tx["title"]), 40, y, "mono13", ("bad" if tx["red"] else "ink") if on else "mute")
        st = tx["state"]
        if st == "signed":
            t8("SIGNED (DEMO)", 40, y + 20, "ok")
        elif st == "rejected":
            t8("REJECTED", 40, y + 20, "bad")
        else:
            t8("%d OF 2 SIGNED" % tx["have"], 40, y + 20, "mute")
            for j in range(3):
                d.ellipse(160 + 10 * j, y + 23, 3, 3, c("ok") if j < tx["have"] else c("dim"), j < tx["have"])
    t8("SAFE 0x7a3f..9f02  2 OF 3", 8, 100, "dim")
    footer((("MENU", "ink"), ("NEXT", "ink"), ("OPEN", "acc")))


def cursor(on, x=3 + 8 * 8, y=3):
    d.fill_rect(x, y, 7, 8, c("ink") if on and th is NORMAL else c("bg") if th is NORMAL else c("bad"))
    push_rows(0, 13)


PAGES = ("WHAT", "DETAIL", "HASH", "VERIFY")


def draw_page(tx, p, seen):
    global th
    th = RED if tx["red"] else NORMAL
    bg()
    header(("!! " if tx["red"] else "> ") + "#%d %s" % (tx["n"], PAGES[p]), "%d/4" % (p + 1))
    if p == 0 and not tx["red"]:
        t8("SEND", 8, 20, "mute")
        x = tf("1,000.00", 8, 30, "monob28", "ink")
        tf("USDC", x + 6, 46, "mono13", "mute")
        t8("TO", 8, 74, "mute")
        blockies.draw(d, CAROL, 8, 84, 3)
        tf(short(CAROL), 40, 82, "mono13", "ink")
        t8("NOT IN ADDRESS BOOK", 40, 102, "warn")
    elif p == 0:
        t8("ADD OWNER", 8, 20, "mute")
        tf("0xdead…beef", 8, 30, "monob28", "ink")
        blockies.draw(d, NEWOWNER, 200, 76, 4)
        t8("THRESHOLD STAYS 2", 8, 72, "ink")
        t8("CHANGES WHO CONTROLS", 8, 86, "bad")
        t8("THE SAFE. NO UNDO.", 8, 97, "bad")
    elif p == 1:
        rows = (("CHAIN", "BASE (8453)"), ("SAFE", "0x7a3f..9f02"), ("TO", tx["target"]), ("CALL", tx["call"]),
                ("VALUE", "0 ETH"), ("OP", "CALL"), ("NONCE", str(tx["n"])), ("GAS", "0  0  0  NO REFUND"))
        for i, (k, v) in enumerate(rows):
            t8(k, 8, 19 + 12 * i, "mute")
            t8(v, 64, 19 + 12 * i, "ink")
    elif p == 2:
        t8("KECCAK256 // SAFE TX HASH", HX, 19, "acc")
        if tx["hash"]:
            hash_rows(tx["hash"], "ink")
            t8("WORKED OUT HERE IN %.1f S" % (tx["ms"] / 1000), HX, 94, "mute")
            t8("SERVICE: MATCH (DEMO)", HX, 104, "ok")
    else:
        h = tx["hash"]
        t8("READ IT TO THE PROPOSER", 8, 19, "mute")
        t8("THE HASH ENDS IN", 8, 30, "mute")
        tf(h[-8:-4] + " " + h[-4:], 8, 42, "monob28", "ok")
        blockies.draw(d, "0x" + h, 192, 36, 5)
        if seen:
            t8("HOLD", 8, 92, "ink")
            circ(44, 91, "ok")
            t8("%d S TO SIGN" % (3 if tx["red"] else 2), 60, 92, "ink")
    footer(review_slots(tx, p, seen))


def review_slots(tx, p, seen):
    return (("REJECT", "bad"), ("NEXT" if p < 3 else "FIRST", "ink"), ("SIGN", "ok") if seen else None)


def draw_end(tx, ok):
    global th
    th = NORMAL if ok else RED
    bg()
    header("> #%d" % tx["n"], "DONE")
    s = "SIGNED" if ok else "REJECTED"
    tf(s, (W - F.width(s, "monob28")) // 2, 30, "monob28", "ok" if ok else "bad")
    if ok:
        t8("DEMO: THE KEY WAS NOT ASKED", 12, 80, "warn")
        t8("ENDS IN " + tx["hash"][-8:], 12, 94, "mute")
    else:
        t8("NOTHING WAS SIGNED", 48, 84, "ink")
    footer((None, ("QUEUE", "ink"), None))


# ----------------------------------------------------------------------------- the verify page's entrance
# Grey hex noise; cells turning blue, each showing a character of the real hash; then the page (the
# green code and the blockie) locking in over them (FX3, lock_in); a green fringe.
PAGE = bytearray(W * H * 2)             # the finished page, drawn whole, for tear_in and lock_in
GREYS = ((34, 38, 46), (58, 64, 76), (88, 94, 108))
BLUE, BLUE_HI = (70, 92, 200), (190, 205, 255)
COLS, ROW0, ROWS = 30, BODY0 + 3, 12    # the 8x8 grid over the body
_order = list(range(COLS * ROWS))


def field(cells, hx, now, y_from=0):
    """The noise: each cell a grey 0-2, or blue (3, at the time it turned). Rows from y_from down."""
    bg(max(BODY0, y_from), FOOT)
    for r in range(ROWS):
        y = ROW0 + 8 * r
        if y < y_from:
            continue
        rows = ["", "", "", "", ""]
        for col in range(COLS):
            i = r * COLS + col
            v = cells[i]
            if v < 3:
                k, ch = v, HEX[random.getrandbits(4)]
            else:
                k, ch = 3 if time.ticks_diff(now, v) > 160 else 4, hx[i % 64]
            for j in range(5):
                rows[j] += ch if j == k else " "
        for j, rgb in enumerate(GREYS + (BLUE, BLUE_HI)):
            if rows[j].strip():
                d.text(rows[j], 0, y, L.color(*rgb))


def verify_in(tx, seen, full):
    hx = tx["hash"]
    draw_page(tx, 3, seen)
    PAGE[:] = BUF
    push_rows(0, BODY0)
    push_rows(FOOT, H)
    n = COLS * ROWS
    cells = [random.getrandbits(2) % 3 for _ in range(n)]
    if full:
        for i in range(n - 1, 0, -1):   # the order the cells turn blue in
            j = random.getrandbits(16) % (i + 1)
            _order[i], _order[j] = _order[j], _order[i]
        t0 = time.ticks_ms()
        while True:                     # grey for 0.7 s, then blue over 1.1 s, then 0.3 s all blue
            now = time.ticks_ms()
            el = time.ticks_diff(now, t0)
            if el > 2100:
                break
            if el > 700:
                for k in range(min(n, n * (el - 700) // 1100)):
                    i = _order[k]
                    if cells[i] < 3:
                        cells[i] = now
            field(cells, hx, now)
            push_rows(BODY0, FOOT)
    else:
        now = time.ticks_ms()
        for i in range(n):
            cells[i] = time.ticks_add(now, -1000)
        field(cells, hx, now)
        push_rows(BODY0, FOOT)
    # FX3: the page locks in over the blue field, the field the bar at its seam.
    lock_in(lambda: field(cells, hx, time.ticks_ms()))
    # The code fringes green and settles.
    code = hx[-8:-4] + " " + hx[-4:]
    for dx in (3, 2, 1):
        tf(code, 8 - dx, 42, "monob28", "cyan")
        tf(code, 8 + dx, 42, "monob28", (180, 255, 120))
        tf(code, 8, 42, "monob28", "ok")
        push_rows(36, 84)
        time.sleep_ms(70)
        BUF[:] = PAGE
    push_rows(36, 84)


# ----------------------------------------------------------------------------- keys
keys = [Pin(n, Pin.IN, Pin.PULL_UP) for n in (2, 3, 6)]
_prev = [False, False, False]


def pressed():
    """The index of a key that just went down, or None."""
    for i, p in enumerate(keys):
        v = p() == 0
        if v and not _prev[i]:
            _prev[i] = True
            time.sleep_ms(15)
            return i
        _prev[i] = v
    return None


def hold_sign(tx, p, seen):
    """D2 held: -> True once held long enough, False if let go first."""
    need = 3000 if tx["red"] else 2000
    t0 = time.ticks_ms()
    while keys[2]() == 0:
        el = time.ticks_diff(time.ticks_ms(), t0)
        bg(90, FOOT)
        t8("KEEP HOLDING  %.1f S" % max(0, (need - el) / 1000), 8, 94, "ok" if not tx["red"] else "bad")
        d.fill_rect(8, 106, 224, 5, c("dim"))
        d.fill_rect(8, 106, 224 * min(el, need) // need, 5, c("ok" if not tx["red"] else "bad"))
        footer(review_slots(tx, p, seen), hold=min(1, el / need))
        push_rows(90, H)
        if el >= need:
            _prev[2] = True
            return True
        time.sleep_ms(20)
    _prev[2] = False
    return False


# ----------------------------------------------------------------------------- the loop
def review(tx):
    p, seen = 0, False
    arrive(draw_page, tx, p, seen, strong=tx["red"])
    while True:
        k = pressed()
        if k is None:
            time.sleep_ms(10)
            continue
        print("key D%d on #%d page %d" % (k, tx["n"], p + 1))
        if k == 0:
            tx["state"] = "rejected"
            arrive(draw_end, tx, False, strong=True)
            return
        if k == 1:
            p = (p + 1) % 4
            if p == 2 and not tx["hash"]:
                draw_page(tx, p, seen)
                glitch(5, 8)
                tx["hash"] = compute(tx)
                reveal(tx["hash"])
            if p == 3:
                seen = True
                verify_in(tx, seen, not tx.get("shown"))
                tx["shown"] = True
            else:
                draw_page(tx, p, seen)
                glitch(5, 8)
        elif k == 2 and seen:
            if hold_sign(tx, p, seen):
                tx["state"] = "signed"
                arrive(draw_end, tx, True, fx="lock")
                return
            draw_page(tx, p, seen)
            push_rows(0, H)


def main():
    """The queue until D0 (Menu)."""
    for t in TXS:
        t["state"] = None
    sel = 0
    arrive(draw_queue, sel)
    blink, t_blink = True, time.ticks_ms()
    while True:
        k = pressed()
        if k == 0:
            return
        if k == 1:
            sel = (sel + 1) % len(TXS)
            draw_queue(sel)
            push_rows(0, H)
        elif k == 2:
            tx = TXS[sel]
            if tx["state"]:
                continue
            review(tx)
            while pressed() is None:
                time.sleep_ms(10)
            arrive(draw_queue, sel)
        if time.ticks_diff(time.ticks_ms(), t_blink) > 500:
            t_blink, blink = time.ticks_ms(), not blink
            cursor(blink)
        time.sleep_ms(10)


if __name__ == "__main__":                 # run, not imported (keypick_crt.py borrows the kit)
    gc.collect()
    print("hackui: D0 stop/reject, D1 play/next, D2 rec/sign (held); heap %d KB" % (gc.mem_free() // 1024))
    main()
