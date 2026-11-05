# console-rp's CRT look: the two effects the person at the bench kept (hardware/console-rp/bench/
# HORSEPOWER.md, "Screens tried on the bench"; hackui.py, glitchfx.py), scanlines, and noise.
#   tear  FX1: something arrives or changes. Slices of the new page land torn and shifted over what
#         the panel showed, calming until the page holds. Strong for a red page, short for a page turn.
#   lock  FX3: worked out here, and checked. The page rolls like a set losing vertical hold, a noise
#         bar at the seam, overshoots, and locks: the verify code, the key's address, Signed.
# The bench's effects traded slices between two whole frames. With the console running there is
# room for one (70 KB free, HORSEPOWER.md), so the panel is the other: it keeps what it showed until
# a slice of the new page, already drawn whole in lcd's frame, is sent over it. The noise is a strip
# of its own, 16 rows, from os.urandom.
#
# An effect never stands between the person and a button: any press stops it at once, the page goes
# out whole, and the press is kept for the console's tick (take_pressed), so Reject is still one
# press. Nothing moves on a page once it has arrived.
import os
import time
import random
import framebuf
import board
import lcd as L

FX = True                   # False: every page goes out whole (the tests, and a still screen)
NH = 16                     # rows in the noise strip
W, H = L.W, L.H
_taken = []                 # presses that stopped an effect, for the tick
_noise = _nfb = None
GREYS = ((40, 46, 58), (72, 80, 96), (110, 120, 138))


def take_pressed():
    """The presses that stopped an effect since the last call, oldest first."""
    out = _taken[:]
    del _taken[:]
    return out


def _stopped(keys):
    if keys is None:
        return False
    p = keys.pressed()
    if p:
        _taken.extend(p)
        return True
    return False


def _refresh(bg):
    """The noise strip again: two rows of hex from os.urandom, each digit shaded by its value."""
    global _noise, _nfb
    if _noise is None:
        _noise = bytearray(W * NH * 2)
        _nfb = framebuf.FrameBuffer(_noise, W, NH, framebuf.RGB565)
    _nfb.fill(bg)
    raw = os.urandom(W // 8)
    for r in range(2):
        for i in range(W // 8):
            v = raw[i] >> (4 * r) & 15
            _nfb.text("0123456789abcdef"[v], i * 8, r * 8, L.color(*GREYS[0 if v < 6 else 1 if v < 11 else 2]))


def _send(d, mv, y, h, dx=0):
    """h rows from mv to screen row y, dx pixels sideways. The panel's RAM is 40 columns wider each
    side than the window, so |dx| <= 40 lands in RAM nobody sees."""
    d._window(max(-40, min(40, dx)), y, W, h)
    d.dc(1)
    d.cs(0)
    d.spi.write(mv)
    d.cs(1)


def page(d, sy, h, y, dx=0):
    """Rows sy..sy+h of the page (lcd's frame) at screen row y."""
    _send(d, memoryview(d.buffer)[sy * W * 2:(sy + h) * W * 2], y, h, dx)


def noise(d, y, h, dx=0):
    """h rows of noise at screen row y, the strip repeated."""
    mv = memoryview(_noise)
    while h > 0:
        k = min(h, NH)
        _send(d, mv[:k * W * 2], y, k, dx)
        y, h = y + k, h - k


def whole(d, y0=0, y1=H):
    page(d, y0, y1 - y0, y0)


def tear(d, y0, y1, bg, keys=None, n=9, amp=22, ms=40):
    """FX1 over rows y0..y1: noise first, then the page in torn slices, calming. -> False if a press
    stopped it (the page is whole either way)."""
    _refresh(bg)
    whole(d, 0, y0)
    whole(d, y1, H)
    noise(d, y0, y1 - y0)
    span = y1 - y0
    for f in range(n):
        if _stopped(keys):
            whole(d, y0, y1)
            return False
        p = f / (n - 1)
        a = int(amp * (1 - p))
        if f % 3 == 2:
            _refresh(bg)
        y = y0
        while y < y1:
            e = min(y1, y + random.randint(2, 11))
            dx = random.randint(-a, a) if a and random.random() < 0.55 * (1 - p) + 0.05 else 0
            r = random.random()
            if r < p ** 0.6:
                page(d, y, e - y, y, dx)
            elif r < p ** 0.6 + 0.15 * (1 - p):
                page(d, y0 + random.randint(0, span - (e - y)), e - y, y, dx)     # a slice from the wrong row
            elif r < 0.85:
                noise(d, y, e - y, dx)
            # else: the panel keeps what it had there
            y = e
        time.sleep_ms(ms)
    whole(d, y0, y1)
    return True


def lock(d, y0, y1, bg, keys=None, dur=1100):
    """FX3 over rows y0..y1: the page rolls, a noise bar at the seam, overshoots and locks, then one
    last twitch. -> False if a press stopped it."""
    import math
    _refresh(bg)
    whole(d, 0, y0)
    whole(d, y1, H)
    span = y1 - y0
    t0, k = time.ticks_ms(), 0
    while True:
        t = time.ticks_diff(time.ticks_ms(), t0)
        if t >= dur:
            break
        if _stopped(keys):
            whole(d, y0, y1)
            return False
        u = t / dur
        roll = int(span * 0.9 * math.exp(-3.2 * u) * math.cos(9 * u))     # damped: overshoots, then holds
        jit = int(12 * (1 - u) ** 2)
        bar = max(0, int(10 * (1 - u)))
        y = y0
        while y < y1:
            sy = y0 + (y - y0 + roll) % span
            run = min(y1 - y, y0 + span - sy, random.randint(3, 9))
            dx = random.randint(-jit, jit) if jit and random.random() < 0.6 else 0
            if sy - y0 < bar:
                noise(d, y, run, dx)
            else:
                page(d, sy, run, y, dx)
            y += run
        k += 1
        if k % 5 == 0:
            _refresh(bg)
        time.sleep_ms(30)
    for dx in (3, -2, 1):               # one last twitch as it locks
        if _stopped(keys):
            break
        page(d, y0, span, y0, dx)
        time.sleep_ms(40)
    whole(d, y0, y1)
    return True


def play(d, fx, y0, y1, bg, keys=None, show=None):
    """fx: None (sent whole by show, else d.show), "tear", "strong" (a red page's), "short" (a page
    turn) or "lock"."""
    if not fx or not FX or board.BANDS != 1:
        return (show or d.show)()
    if fx == "lock":
        return lock(d, y0, y1, bg, keys)
    if fx == "strong":
        return tear(d, y0, y1, bg, keys, n=12, amp=34)
    if fx == "short":
        return tear(d, y0, y1, bg, keys, n=4, amp=10, ms=30)
    return tear(d, y0, y1, bg, keys)
