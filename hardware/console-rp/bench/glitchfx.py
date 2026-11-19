# console-rp: three ways a page can arrive out of the noise, to compare on the board. Bench only. Each
# is a candidate for the UI's vocabulary: an effect that means something, as a colour does.
#   FX1 tear & settle   torn slices jump and swap with the noise, calming until the page holds:
#                       "something new is here"
#   FX2 block decode    the page lands tile by tile, some in the wrong place for a frame or two, like a
#                       stream decoding: "assembled here, piece by piece" (a hash, a key)
#   FX3 signal lock     the page rolls like a set losing vertical hold, a noise bar at the seam, the
#                       jitter dying away until it locks: "tuned in, locked on" (a result checked)
# The noise is os.urandom, fresh each time (keypick_crt.noise). The pages are hackui.py's verify page
# (the real hash of its #7), keypick_crt.py's pick page (an owner address worked out from random
# bytes: no key is made) and hackui.py's queue. The FX number is in the top right corner. At start it
# plays each FX once on the verify page, then waits for the buttons.
#   D0 ■ replay   D1 ▶ next FX   D2 ● next page
#   put.py PORT hackui.py keypick_crt.py (with what they need), then rawrepl.py PORT glitchfx.py --follow 5
import gc
import os
import time
import random
import machine
import lcd as L
import hackui as H
import keypick_crt as KP
import safe_tx
import webauthn

d, W, HH, BODY0, FOOT = H.d, H.W, H.H, H.BODY0, H.FOOT
BUF, PAGE = H.BUF, H.PAGE
BODY_H = FOOT - BODY0
NAMES = ("TEAR", "DECODE", "LOCK")


def push_from(buf, y0, y1, dx=0):
    """Rows y0..y1 of buf (whole width), dx pixels sideways (|dx| <= 40: the panel's hidden RAM)."""
    d._window(dx, y0, W, y1 - y0)
    d.dc(1); d.cs(0); d.spi.write(memoryview(buf)[y0 * W * 2:y1 * W * 2]); d.cs(1)


TW, TH = 16, 17                         # FX2's tiles: 15 x 6 over the body
_tile = bytearray(TW * TH * 2)
_tmv = memoryview(_tile)


def send_tile(src, sx, sy, dx, dy):
    """The TW x TH block of src at (sx, sy), sent to (dx, dy)."""
    mv = memoryview(src)
    for r in range(TH):
        o = ((sy + r) * W + sx) * 2
        _tmv[r * TW * 2:(r + 1) * TW * 2] = mv[o:o + TW * 2]
    d._window(dx, dy, TW, TH)
    d.dc(1); d.cs(0); d.spi.write(_tile); d.cs(1)


def rnd(a):
    return random.randint(-a, a) if a > 0 else 0


# ----------------------------------------------------------------------------- FX1 tear & settle
def fx_tear():
    n = 20
    for f in range(n):
        p = f / (n - 1)
        if f % 3 == 0:
            KP.noise()
        a = int(26 * (1 - p))
        y = BODY0
        while y < FOOT:
            e = min(FOOT, y + random.randint(2, 11))
            r = random.random()
            if r < p ** 0.6:
                src, sy = PAGE, y
            elif r < p ** 0.6 + 0.15 * (1 - p) and e - y < BODY_H:
                src, sy = PAGE, BODY0 + random.randint(0, BODY_H - (e - y))   # a slice from the wrong row
            else:
                src, sy = BUF, y
            dx = rnd(a) if random.random() < 0.55 * (1 - p) + 0.05 else 0
            d._window(dx, y, W, e - y)
            d.dc(1); d.cs(0); d.spi.write(memoryview(src)[sy * W * 2:(sy + e - y) * W * 2]); d.cs(1)
            y = e
        time.sleep_ms(55)
    push_from(PAGE, BODY0, FOOT)


# ----------------------------------------------------------------------------- FX2 block decode
def fx_decode():
    cols, rows = W // TW, BODY_H // TH
    tiles = [(c * TW, BODY0 + r * TH) for r in range(rows) for c in range(cols)]
    for i in range(len(tiles) - 1, 0, -1):
        j = random.getrandbits(16) % (i + 1)
        tiles[i], tiles[j] = tiles[j], tiles[i]
    wrong = []                          # (frames left, x, y): shown from the wrong place for now
    per, k, f = 6, 0, 0
    while k < len(tiles) or wrong:
        f += 1
        if f % 4 == 0:                  # the noise keeps moving under the tiles still to come
            KP.noise()
            for x, y in tiles[k:]:
                send_tile(BUF, x, y, x, y)
        keep = []
        for left, x, y in wrong:
            if left <= 1:
                send_tile(PAGE, x, y, x, y)
            else:
                keep.append((left - 1, x, y))
        wrong = keep
        for x, y in tiles[k:k + per]:
            if random.random() < 0.35:  # lands from a neighbour first
                sx = min(W - TW, max(0, x + TW * rnd(2)))
                sy = min(FOOT - TH, max(BODY0, y + TH * rnd(1)))
                send_tile(PAGE, sx, sy, x, y)
                wrong.append((random.randint(1, 3), x, y))
            else:
                send_tile(PAGE, x, y, x, y)
        k += per
        time.sleep_ms(40)
    push_from(PAGE, BODY0, FOOT)        # the rows under the last whole tile row, and anything missed


# ----------------------------------------------------------------------------- FX3 signal lock
def fx_lock():
    import math
    KP.noise()                          # the bar at the seam is noise
    t0 = time.ticks_ms()
    dur = 1500
    while True:
        t = time.ticks_diff(time.ticks_ms(), t0)
        if t >= dur:
            break
        u = t / dur
        roll = int(BODY_H * 0.9 * math.exp(-3.2 * u) * math.cos(9 * u))    # damped: overshoots, then holds
        jit = int(14 * (1 - u) ** 2)
        bar = max(0, int(10 * (1 - u)))
        y = BODY0
        while y < FOOT:
            src_y = BODY0 + (y - BODY0 + roll) % BODY_H
            run = min(FOOT - y, BODY0 + BODY_H - src_y, random.randint(3, 9))
            seam = (src_y - BODY0) < bar
            dx = rnd(jit) if random.random() < 0.6 else 0
            if seam:                    # the blanking bar: noise
                push_from(BUF, y, y + run, dx)
            else:
                d._window(dx, y, W, run)
                d.dc(1); d.cs(0); d.spi.write(memoryview(PAGE)[src_y * W * 2:(src_y + run) * W * 2]); d.cs(1)
            y += run
        if (t // 200) % 2 == 0:
            KP.noise()
        time.sleep_ms(30)
    push_from(PAGE, BODY0, FOOT)
    for dx in (3, -2, 1):               # one last twitch as it locks
        push_from(PAGE, BODY0, FOOT, dx)
        time.sleep_ms(50)
    push_from(PAGE, BODY0, FOOT)


FX = (fx_tear, fx_decode, fx_lock)


# ----------------------------------------------------------------------------- the pages
def setup():
    tx = H.TXS[0]
    safe_tx._domain_cache.clear()
    tx["hash"] = H.binascii.hexlify(safe_tx.safe_tx_hash(8453, H.SAFE, tx["to"], 0, tx["data"], 0, nonce=tx["n"])).decode()
    tx["ms"] = 0
    pub = H.binascii.hexlify(os.urandom(64)).decode()
    t = time.ticks_ms()
    addr = webauthn.owner_address("0x" + pub[:64], "0x" + pub[64:], KP.SIGNER)
    st = {"n": 1, "pub": pub, "addr": addr, "ms": time.ticks_diff(time.ticks_ms(), t)}
    print("pages ready: hash ..%s, owner %s" % (tx["hash"][-8:], addr))
    return (("VERIFY", lambda: H.draw_page(tx, 3, True)), ("KEY PICK", lambda: KP.draw_pick(st)),
            ("QUEUE", lambda: H.draw_queue(0)))


def compose(page, fx):
    """The page, a gallery footer, and the FX number big in the top right corner, into PAGE."""
    page()
    d.fill_rect(W - 58, 0, 58, 13, H.c("bg"))
    d.fill_rect(W - 58, 0, 2, 13, H.c("acc"))
    H.t8("FX%d" % (fx + 1), W - 52, 3, "warn")
    H.t8(NAMES[fx][:3], W - 26, 3, "mute")
    H.footer((("REPLAY", "ink"), ("NEXT FX", "ink"), ("PAGE", "acc")))
    PAGE[:] = BUF


def play(pages, pi, fx):
    name, page = pages[pi]
    compose(page, fx)
    push_from(PAGE, 0, BODY0)           # the header and the gallery footer at once
    push_from(PAGE, FOOT, HH)
    KP.noise()                          # the body starts as noise
    push_from(BUF, BODY0, FOOT)
    time.sleep_ms(350)
    t = time.ticks_ms()
    FX[fx]()
    print("FX%d %s on %s: %d ms" % (fx + 1, NAMES[fx], name, time.ticks_diff(time.ticks_ms(), t)))


def main():
    pages = setup()
    for fx in (0, 1, 2):                # a reel to start: each FX once on the verify page
        play(pages, 0, fx)
        time.sleep_ms(1500)
    pi, fx = 0, 0
    play(pages, pi, fx)
    while True:
        k = H.pressed()
        if k is None:
            time.sleep_ms(10)
            continue
        if k == 1:
            fx = (fx + 1) % 3
        elif k == 2:
            pi = (pi + 1) % len(pages)
        play(pages, pi, fx)


gc.collect()
print("glitchfx: D0 replay, D1 next FX, D2 next page; heap %d KB" % (gc.mem_free() // 1024))
main()
