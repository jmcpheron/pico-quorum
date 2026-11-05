# console-rp: four loading screens after the boot mark (firmware/bootmark.py), laid out for the
# 240x135 panel, looping until RESET. Bench only: a look at what could be, not the console's. Uses the
# console's lcd.py, fonts.py, blockies.py and taglines.py unchanged (board_rp.py as board.py). Each
# frame repaints only the regions whose look changed, each from its own small buffer, as the mark does.
#   1 quorum ring    five owners on a turning circle; three sign, their triangle fills: 3 of 5
#   2 the chip wakes the key's chip, a light round its legs, the start's steps ticking off
#   3 diamond        the Ethereum diamond turning without stopping, one face the quorum's green
#   4 verify code    hash digits rolling and settling into a verify code, then the owner's blockie
# Visual only: no dot, step or code here reports anything real. Nothing touches the key.
import gc
import math
import time
import framebuf
from array import array
import lcd as L
import fonts as F
import blockies
import taglines

d = L.LCD()
W, H = L.W, L.H
d.w, d.h = W, H                         # as a Tile, for the first full frame
BG, INK, MUTED, DIM = (11, 13, 17), (242, 244, 247), (152, 160, 172), (52, 58, 70)
OK, WAIT = (52, 199, 89), (255, 184, 48)
OK_DARK, OK_LIGHT = (0, 96, 36), (120, 255, 150)
ETH, ETH_DARK, ETH_LIGHT = (122, 146, 255), (30, 36, 92), (218, 226, 255)
BODY, EDGE = (30, 34, 44), (90, 100, 120)


def clamp(u):
    return 0.0 if u < 0 else 1.0 if u > 1 else u


def span(t, a, b):
    return clamp((t - a) / (b - a))


def ease(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def mix(a, b, u):
    u = clamp(u)
    return (int(a[0] + (b[0] - a[0]) * u), int(a[1] + (b[1] - a[1]) * u), int(a[2] + (b[2] - a[2]) * u))


def col(rgb):
    return L.color(*rgb)


_SHARED = bytearray(240 * 64 * 2)       # every region is drawn in this one buffer, in turn


class Tile(framebuf.FrameBuffer):
    def __init__(self, w, h):
        self.buf, self.w, self.h = memoryview(_SHARED)[:w * h * 2], w, h
        super().__init__(self.buf, w, h, framebuf.RGB565)


_tiles = {}


def tile(w, h):
    t = _tiles.get((w, h))
    if t is None:
        if len(_tiles) > 12:
            _tiles.clear()
        t = _tiles[(w, h)] = Tile(w, h)
    return t


def send(t, x, y):
    d._window(x, y, t.w, t.h)
    d.dc(1); d.cs(0); d.spi.write(t.buf); d.cs(1)


def text(fb, ox, oy, s, x, y, font, rgb):
    F.text(fb, s, x - ox, y - oy, font, rgb, BG)


def caption(fb, ox, oy, s, g=1.0):
    text(fb, ox, oy, s, W - 4 - F.width(s, "sans12"), H - 16, "sans12", mix(BG, DIM, g))


def thick(fb, ox, oy, x0, y0, x1, y1, c):
    for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
        fb.line(int(x0) - ox + dx, int(y0) - oy + dy, int(x1) - ox + dx, int(y1) - oy + dy, c)


def play(scene, regions, ms):
    """The whole screen once, then each region again whenever its look changes, until ms. -> fps."""
    gc.collect()
    scene(d, 0, 0, 0)
    d.show()
    last = [None] * len(regions)
    t0 = time.ticks_ms()
    frames = 0
    while True:
        t = time.ticks_diff(time.ticks_ms(), t0)
        if t >= ms:
            break
        sent = False
        for i, (x, y, w, h, look) in enumerate(regions):
            k = look(t)
            if k != last[i]:
                last[i] = k
                fb = tile(w, h)
                scene(fb, x, y, t)
                send(fb, x, y)
                sent = True
        if sent:
            frames += 1
        else:
            time.sleep_ms(2)
    return frames * 1000 / ms


def fade_out(t, a, b):
    return 1.0 - span(t, a, b)


def q(u, n=12):
    return int(clamp(u) * n)


# ----------------------------------------------------------------------------- 1 quorum ring
class Ring:
    MS = 6400
    CX, CY, R, DOT = 62, 62, 40, 6
    SIGN = {0: 1200, 2: 1700, 3: 2200}       # top, lower right, lower left
    EDGES = ((0, 2, 1900, 2200), (2, 3, 2200, 2500), (3, 0, 2500, 2800))

    def __init__(self):
        self.lines = F.wrap(taglines.pick(), 108, "sans12")[:2]
        self.regions = ((0, 12, 126, 104, lambda t: t),
                        (126, 26, 114, 80, lambda t: (q(span(t, 3000, 3400)), q(span(t, 3500, 3900)),
                                                      q(fade_out(t, 5800, 6400)))))

    def pos(self, k, t):
        a = math.radians(-90 + 72 * k) + t * 2 * math.pi / 14000
        return self.CX + self.R * math.cos(a), self.CY + self.R * math.sin(a)

    def __call__(self, fb, ox, oy, t):
        g = fade_out(t, 5800, 6400)
        fb.fill(col(BG))
        p = [self.pos(k, t) for k in range(5)]
        f = span(t, 2800, 3300)
        if f:
            xy = array("h", [int(c) for k in (0, 2, 3) for c in p[k]])
            fb.poly(-ox, -oy, xy, col(mix(BG, OK_DARK, f * g)), True)
        for a, b, t0, t1 in self.EDGES:
            u = ease(span(t, t0, t1))
            if u:
                (x0, y0), (x1, y1) = p[a], p[b]
                thick(fb, ox, oy, x0, y0, x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, col(mix(BG, OK, g)))
        for k in range(5):
            x, y = p[k]
            r = int(self.DOT * ease(span(t, 150 + 100 * k, 450 + 100 * k)))
            s = self.SIGN.get(k)
            rgb = mix(WAIT, OK, span(t, s, s + 200)) if s else mix(WAIT, MUTED, span(t, 2800, 3300) * 0.6)
            if s:
                u = span(t, s, s + 500)
                if 0 < u < 1:
                    rr = int(self.DOT + 2 + 14 * u)
                    fb.ellipse(int(x) - ox, int(y) - oy, rr, rr, col(mix(OK, BG, u)))
                    fb.ellipse(int(x) - ox, int(y) - oy, rr + 1, rr + 1, col(mix(OK, BG, u)))
            if r:
                fb.ellipse(int(x) - ox, int(y) - oy, r, r, col(mix(BG, rgb, g)), True)
        if f:
            cx = int(sum(p[k][0] for k in (0, 2, 3)) / 3)
            cy = int(sum(p[k][1] for k in (0, 2, 3)) / 3)
            s = "3 of 5"
            text(fb, ox, oy, s, cx - F.width(s, "sans12") // 2, cy - 8, "sans12", mix(BG, INK, f * g))
        n = ease(span(t, 3000, 3400))
        if n:
            text(fb, ox, oy, "PicoQuorum", 130, 36 + int(6 * (1 - n)), "bold18", mix(BG, INK, n * g))
        u = span(t, 3500, 3900)
        for i, line in enumerate(self.lines):
            text(fb, ox, oy, line, 130, 66 + 16 * i, "sans12", mix(BG, MUTED, u * g))
        caption(fb, ox, oy, "1/4 quorum ring", g)


# ----------------------------------------------------------------------------- 2 the chip wakes
class Chip:
    MS = 6000
    CX, CY, S = 58, 60, 40
    STEPS = (("screen", "240 x 135", 700), ("key", "ATECC608", 1700), ("link", "USB-C", 2600), ("console", "ready", 3500))

    def __init__(self):
        self.regions = ((10, 12, 98, 98, lambda t: t // 30),
                        (116, 10, 124, 112, lambda t: t // 80 if t < 4000 else q(fade_out(t, 5400, 6000))))
        legs = []                              # 7 a side, clockwise from the top left
        h, n = self.S // 2, 7
        for i in range(n):
            o = -h + 4 + i * (self.S - 8) // (n - 1)
            legs.append((self.CX + o - 1, self.CY - h - 9, 3, 8))
        for i in range(n):
            o = -h + 4 + i * (self.S - 8) // (n - 1)
            legs.append((self.CX + h + 1, self.CY + o - 1, 8, 3))
        for i in range(n):
            o = h - 4 - i * (self.S - 8) // (n - 1)
            legs.append((self.CX + o - 1, self.CY + h + 1, 3, 8))
        for i in range(n):
            o = h - 4 - i * (self.S - 8) // (n - 1)
            legs.append((self.CX - h - 9, self.CY + o - 1, 8, 3))
        self.legs = legs

    def done(self, t):
        return sum(1 for s in self.STEPS if t >= s[2])

    def __call__(self, fb, ox, oy, t):
        g = fade_out(t, 5400, 6000)
        fb.fill(col(BG))
        ready = span(t, 3500, 3900)
        if ox < 116:
            self.chip(fb, ox, oy, t, g, ready)
        if ox + fb.w > 116:
            self.steps(fb, ox, oy, t, g, ready)
        caption(fb, ox, oy, "2/4 the chip wakes", g)

    def chip(self, fb, ox, oy, t, g, ready):
        head = t / 45
        n = len(self.legs)
        for i, (x, y, w, h) in enumerate(self.legs):
            k = (head - i) % n
            glow = max(0.0, 1 - k / 7)
            rgb = mix(mix(DIM, ETH_LIGHT, glow), OK, ready)
            fb.fill_rect(x - ox, y - oy, w, h, col(mix(BG, rgb, g)))
        h = self.S // 2
        pulse = span(t, 3500, 3700) - span(t, 3700, 4200)
        fb.fill_rect(self.CX - h - ox, self.CY - h - oy, self.S, self.S, col(mix(BG, mix(BODY, OK_DARK, pulse), g)))
        fb.rect(self.CX - h - ox, self.CY - h - oy, self.S, self.S, col(mix(BG, mix(EDGE, OK, ready), g)))
        fb.ellipse(self.CX - h + 6 - ox, self.CY - h + 6 - oy, 2, 2, col(mix(BG, EDGE, g)), True)
        s = "608"
        F.text(fb, s, self.CX - F.width(s, "sans12") // 2 - ox, self.CY - 8 - oy, "sans12",
               mix(BG, mix(MUTED, INK, ready), g), mix(BG, mix(BODY, OK_DARK, pulse), g))

    def steps(self, fb, ox, oy, t, g, ready):
        done = self.done(t)
        for i, (name, note, at) in enumerate(self.STEPS):
            y = 16 + 22 * i
            x = 122
            start = self.STEPS[i - 1][2] if i else 200
            if t >= at:
                u = span(t, at, at + 250)
                c = col(mix(BG, mix(OK_LIGHT, OK, u), g))
                thick(fb, ox, oy, x, y + 8, x + 4, y + 12, c)
                thick(fb, ox, oy, x + 4, y + 12, x + 11, y + 3, c)
                text(fb, ox, oy, name, x + 18, y, "sans14", mix(BG, INK, g))
                text(fb, ox, oy, note, x + 18 + F.width(name, "sans14") + 6, y + 2, "sans12", mix(BG, MUTED, u * g))
            elif t >= start:
                for j in range(6):                  # a small spinner
                    a = j * math.pi / 3
                    lit = (int(t / 80) - j) % 6
                    fb.ellipse(int(x + 6 + 5 * math.cos(a)) - ox, int(y + 8 + 5 * math.sin(a)) - oy, 1, 1,
                               col(mix(BG, mix(ETH_LIGHT, DIM, lit / 5), g)), True)
                text(fb, ox, oy, name, x + 18, y, "sans14", mix(BG, MUTED, g))
            else:
                fb.ellipse(x + 6 - ox, y + 8 - oy, 4, 4, col(mix(BG, DIM, g)))
                text(fb, ox, oy, name, x + 18, y, "sans14", mix(BG, DIM, g))
        bx, by, bw = 122, 106, 110
        fb.fill_rect(bx - ox, by - oy, bw, 3, col(mix(BG, BODY, g)))
        prev = self.STEPS[done - 1][2] if done else 0
        nxt = self.STEPS[done][2] if done < 4 else prev + 1
        frac = (done + (0 if done == 4 else span(t, prev, nxt) * 0.6)) / 4
        fb.fill_rect(bx - ox, by - oy, int(bw * frac), 3, col(mix(BG, mix(ETH, OK, ready), g)))


# ----------------------------------------------------------------------------- 3 diamond, turning
# The Ethereum logo in 3D, from its own SVG's proportions (256 x 417): the upper piece a tall point
# (y 0) widest at y 212 with a short point under it (y 288); the lower piece a chevron, its corners
# at y 236.6, its top dipping to y 312, its point at y 417. Seen from a little above (TILT), turned
# about its axis by yaw. Faces are kept when their outward normal faces the viewer, and drawn far
# to near, the lower piece first.
ETH_R, ETH_S, TILT = 128, 0.283, 0.22
LIGHT = (-0.42, -0.55, 0.72)


def _ring(y, yaw):
    return [(ETH_R * math.cos(yaw + k * math.pi / 2), y, ETH_R * math.sin(yaw + k * math.pi / 2)) for k in range(4)]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(u, v):
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def _dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def eth_faces(yaw, cx, cy):
    """-> [(three screen points, rgb)] to fill in order."""
    ce, se = math.cos(TILT), math.sin(TILT)

    def view(p):                            # tilted toward the viewer at +z; y is down
        return (p[0], p[1] * ce + p[2] * se, p[2] * ce - p[1] * se)

    P, Q = _ring(212, yaw), _ring(236.6, yaw)
    top, under, dip, tip = (0, 0, 0), (0, 288, 0), (0, 312, 0), (0, 417, 0)
    upper = [((top, P[k], P[(k + 1) % 4]), k == 0) for k in range(4)] + \
            [((under, P[k], P[(k + 1) % 4]), False) for k in range(4)]
    lower = [((tip, Q[k], Q[(k + 1) % 4]), False) for k in range(4)] + \
            [((dip, Q[k], Q[(k + 1) % 4]), None) for k in range(4)]       # None: the dip, kept dark
    out = []
    for piece, inside in ((lower, (0, 380, 0)), (upper, (0, 212, 0))):
        faces = []
        for tri, green in piece:
            v = [view(p) for p in tri]
            n = _cross(_sub(v[1], v[0]), _sub(v[2], v[0]))
            mid = ((v[0][0] + v[1][0] + v[2][0]) / 3, (v[0][1] + v[1][1] + v[2][1]) / 3, (v[0][2] + v[1][2] + v[2][2]) / 3)
            if _dot(n, _sub(mid, view(inside))) < 0:
                n = (-n[0], -n[1], -n[2])   # outward, away from the piece's inside
            if n[2] <= 0:
                continue                    # facing away
            m = math.sqrt(_dot(n, n)) or 1
            lit = max(0.0, _dot(n, LIGHT) / m)
            rgb = mix(BG, ETH_DARK, 0.7) if green is None else \
                mix(OK_DARK, OK_LIGHT, 0.25 + 0.75 * lit) if green else mix(ETH_DARK, ETH_LIGHT, 0.3 + 0.7 * lit)
            pts = [(cx + p[0] * ETH_S, cy + (p[1] - 208) * ETH_S) for p in v]
            faces.append((mid[2], pts, rgb))
        faces.sort(key=lambda f: f[0])
        out += [(p, c) for _, p, c in faces]
    return out


class Diamond:
    MS = 6000
    CX, CY = 62, 66

    def __init__(self):
        self.lines = F.wrap(taglines.pick(), 108, "sans12")[:2]
        self.regions = ((10, 4, 106, 126, lambda t: t),
                        (126, 60, 112, 22, lambda t: (t // 350) % 4),
                        (126, 26, 114, 34, lambda t: q(span(t, 0, 500))),
                        (126, 82, 114, 34, lambda t: q(span(t, 300, 800))))

    def faces(self, t):
        return eth_faces(t * 2 * math.pi / 3200, self.CX, self.CY + 2 * math.sin(t / 420))

    def __call__(self, fb, ox, oy, t):
        fb.fill(col(BG))
        g = ease(span(t, 0, 400))
        for p, rgb in self.faces(t):
            xy = array("h", [int(p[0][0]), int(p[0][1]), int(p[1][0]), int(p[1][1]), int(p[2][0]), int(p[2][1])])
            fb.poly(-ox, -oy, xy, col(mix(BG, rgb, g)), True)
        n = ease(span(t, 0, 500))
        text(fb, ox, oy, "PicoQuorum", 130, 32 + int(4 * (1 - n)), "bold18", mix(BG, INK, n))
        text(fb, ox, oy, "loading" + "." * ((t // 350) % 4), 130, 62, "sans14", mix(BG, MUTED, n))
        u = span(t, 300, 800)
        for i, line in enumerate(self.lines):
            text(fb, ox, oy, line, 130, 86 + 15 * i, "sans12", mix(BG, MUTED, u * 0.8))
        caption(fb, ox, oy, "3/4 diamond")


# ----------------------------------------------------------------------------- 4 verify code
class Verify:
    MS = 6400
    CODE = "f924aa08"
    HEX = "0123456789abcdef"
    SEED = "0x1f2e3d4c5b6a79881f2e3d4c5b6a79889a3b0c7d"
    LOCK0, STEP = 500, 150
    BX, BY, PX = 34, 74, 5

    def __init__(self):
        self.cw = F.width("0", "monob28")
        self.x0 = (W - self.cw * 9) // 2
        self.cells, self.pal = blockies._cells(self.SEED, 8, L.color)
        end = self.LOCK0 + self.STEP * 8
        self.regions = ((0, 6, W, 64, lambda t: t // 40 if t < end + 400 else q(fade_out(t, 5800, 6400))),
                        (28, 70, 212, 48, lambda t: t // 20 if t < 3000 else (q(span(t, 2900, 3300)), q(fade_out(t, 5800, 6400)))))

    def __call__(self, fb, ox, oy, t):
        g = fade_out(t, 5800, 6400)
        fb.fill(col(BG))
        text(fb, ox, oy, "verify code", (W - F.width("verify code", "sans12")) // 2, 8, "sans12", mix(BG, MUTED, span(t, 0, 300) * g))
        for i in range(8):
            x = self.x0 + self.cw * (i + (1 if i >= 4 else 0))
            lock = self.LOCK0 + self.STEP * i
            if t >= lock:
                c, rgb = self.CODE[i], mix(OK_LIGHT, INK, span(t, lock, lock + 350))
            else:
                c, rgb = self.HEX[(t // 45 + i * 5) % 16], mix(BG, DIM, span(t, 0, 200))
            text(fb, ox, oy, c, x, 26, "monob28", mix(BG, rgb, g))
        b0, b1 = 1900, 2900
        n = int(64 * span(t, b0, b1))
        if n and g > 0.5:                           # the blockie's colours are its own: cut, not faded
            for k in range(n):
                v = self.cells[k]
                fb.fill_rect(self.BX + (k % 8) * self.PX - ox, self.BY + (k // 8) * self.PX - oy, self.PX, self.PX,
                             self.pal[1 if v == 1 else 2] if v else self.pal[0])
            if n < 64:
                y = self.BY + (n // 8) * self.PX + self.PX // 2
                fb.hline(self.BX - 4 - ox, y - oy, 8 * self.PX + 8, col(ETH))
        u = span(t, 2900, 3300)
        if u:
            x = self.BX + 8 * self.PX + 10
            text(fb, ox, oy, "owner 0x1f2e…9a3b".replace("…", "..."), x, self.BY + 2, "sans14", mix(BG, INK, u * g))
            text(fb, ox, oy, "check it with the proposer", x, self.BY + 22, "sans12", mix(BG, MUTED, u * g))
        caption(fb, ox, oy, "4/4 verify code", g)


def main():
    plays = 0
    while True:
        for kind in (Ring, Chip, Diamond, Verify):
            for _ in range(2):
                scene = kind()
                fps = play(scene, scene.regions, scene.MS)
                plays += 1
                print("%s: %.1f fps" % (kind.__name__, fps))
                del scene
                gc.collect()


main()
