# The boot screen in pixel art: bootmark.py's story at 8 frames a second, on a grid of big pixels
# (4 px on the 240-row panels, 3 on the Feather, 2 on the 1.8"), in a small fixed palette with flat,
# banded shading. Five owners pop in, three sign and ring out, their edges join and the triangle
# fills green from the base up, with a dither. Then the triangle is the front face of the Ethereum
# diamond: it turns in 15° steps, like a sprite, and stops on the logo's pose, dimmed behind the
# name. The name drops in with a shadow, and the tagline types itself out. Stars twinkle behind.
# Then the chip's owner and name (set_chip) and the real boot status, as on the mark.
# Every moving part changes only on a step (STEP_MS), so between steps a frame sends nothing; a step
# sends only the rectangles that changed, as bootmark does. It stops on its last step rather than
# twinkling on: a still screen while the console starts, not one that seems to hang.
#   secrets.BOOT_ART = "pixel" (the default) this; "mark" and "still" bootmark.py; "orbit" bootart.py
# Visual branding only: the three green dots do not report actual signatures.
import math
import framebuf
from array import array
import board
import lcd as L
import taglines

LEAD_MS = 300           # black before the first frame (splash)
IN_MS = True            # splash passes render the time in ms
STEP_MS = 125           # one step of the animation: 8 a second
STILL = 1 << 30

# The palette: a night sky, cream ink, amber for the owners who haven't signed, and a four-tone
# ramp each for the quorum's green and Ethereum's blue. Shading picks a tone, never a blend.
BG = (24, 20, 37)
STARS = ((44, 38, 70), (78, 68, 120), (150, 140, 200))
INK, MUTED, SHADOW = (250, 240, 215), (140, 132, 170), (70, 40, 96)
AMBER, AMBER_HI, AMBER_DIM = (247, 168, 52), (255, 222, 120), (122, 76, 44)
GREEN = ((22, 72, 66), (34, 128, 84), (80, 196, 96), (184, 240, 120))
BLUE = ((36, 34, 88), (54, 72, 162), (86, 130, 230), (156, 212, 255))
BLUE_BACK = (BLUE, ((32, 28, 70), (44, 52, 118), (62, 88, 160), (100, 140, 190)),    # behind the name: the
             ((29, 25, 56), (36, 38, 88), (46, 60, 116), (66, 92, 140)))              # same ramp, two steps dimmer
BAD = (232, 74, 90)

W, H = L.W, L.H
SMALL = H < 200                             # the Feather (240x135) and the 1.8" (160x128)
P = 4 if not SMALL else 3 if W >= 200 else 2    # screen px per art pixel
CW, CH = W // P, H // P                     # the grid, in art pixels
GX, GY = (W - CW * P) // 2, (H - CH * P) // 2

# The mark, in art pixels: bootmark's circle of owners on this grid
R = round((30 if SMALL else 62) / P)
CX, CY = CW // 2, round((40 if SMALL else 84) / P)
DOT = 2
PTS = [(CX + round(R * math.cos(math.radians(-90 + 72 * k))),
        CY + round(R * math.sin(math.radians(-90 + 72 * k)))) for k in range(5)]
TOP, LEFT, RIGHT = PTS[0], PTS[3], PTS[2]

# Text, in screen px: the built-in 8x8 font, the name doubled
NAME = "PicoQuorum"
NAME_S = 2 if W >= 200 else 1               # the 1.8" draws it once, bold
NAME_Y = 43 if SMALL else 89
TAG_Y = None if SMALL else 136              # no room for a tagline on the small panels
TAG_COLS = (W - 16) // 8
CHIP_Y = None if SMALL else 164
CHIP_PX = 4
STATUS_Y = H - (12 if SMALL else 16)

# The timeline, in steps (STEP_MS each). No holds: each move starts as the one before it ends.
BORN = 0                                    # owner k pops in at step BORN + k
SIGN = {0: 4, 3: 6, 2: 8}                   # each signer turns green and a ring goes out
EDGES = ((TOP, LEFT, 6), (TOP, RIGHT, 8), (LEFT, RIGHT, 10))
SETTLE = 10                                 # the two who didn't sign dim
POUR = 10                                   # the triangle fills over 4 steps from here
TURN = 14                                   # the diamond takes over from the triangle
YAW = (0, 10, 25, 45, 65, 85, 105, 120, 130, 135)    # degrees at TURN, TURN + 1, ...: lands on 45 mod 90
ZOOM = (0, 0.16, 0.5, 0.84, 1)              # to the logo's size, smoothstep in 4 steps
RISE = 16                                   # the lower pyramid rises in over 4 steps
BACK = TURN + len(YAW) - 1                  # it stops, dims and grows a little behind the name
NAME0 = BACK                                # the name drops in over 3 steps
TAG0 = NAME0 + 3                            # then the tagline types itself, TAG_RATE letters a step
TAG_RATE = 9
END = TAG0 + 4                              # the last step: everything still from here
DURATION_MS = END * STEP_MS                 # splash holds the boot screen this long

# The diamond is bootmark's: a square pyramid over an inverted one, turned about its axis and seen
# from up to 30° above. Head-on its front face is the quorum's triangle.
K0, OY0 = LEFT[1] - TOP[1], LEFT[1]
S0 = (RIGHT[0] - LEFT[0]) / 2 / K0
S1, GAP, FOOT = 0.37, 0.12, 0.97
EL = math.radians(30)
K1, OY1, KB, OYB = [v / P for v in ((40, 52, 44, 54) if SMALL else (80, 100, 88, 104))]
_l = math.sqrt(0.55 * 0.55 * 2 + 0.63 * 0.63)
LIGHT = (-0.55 / _l, -0.55 / _l, 0.63 / _l)


def col(rgb):
    return L.color(*rgb)


def _stars():
    """Fixed places, from a small LCG so every boot is the same sky, kept off the text and the mark."""
    out, s = [], 7
    keep = [(NAME_Y - 4, NAME_Y + 8 * NAME_S + 6), (STATUS_Y - 4, H)]
    if TAG_Y:
        keep += [(TAG_Y - 4, TAG_Y + 22), (CHIP_Y - 4, CHIP_Y + 8 * CHIP_PX + 4)]
    while len(out) < (10 if SMALL else 16):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        x, y = s % CW, (s >> 12) % CH
        py = GY + y * P
        if any(a <= py + P and py <= b for a, b in keep):
            continue
        if (x - CX) ** 2 + (y - (CY + 2)) ** 2 < (R + 6) ** 2:
            continue
        out.append((x, y))
    return out


STAR_AT = _stars()


# ---- drawing in art pixels: (x, y) on the grid, shifted into a tile at screen (ox, oy) ---------------
def cells(d, ox, oy, x, y, w, h, c):
    d.fill_rect(GX + x * P - ox, GY + y * P - oy, w * P, h * P, c)


_disc = {}


def disc_rows(r):
    if r not in _disc:
        _disc[r] = [(dy, int(math.sqrt((r + 0.5) ** 2 - dy * dy))) for dy in range(-r, r + 1)]
    return _disc[r]


def disc(d, ox, oy, x, y, r, c):
    for dy, h in disc_rows(r):
        cells(d, ox, oy, x - h, y + dy, 2 * h + 1, 1, c)


_ring = {}


def ring(d, ox, oy, x, y, r, c):
    if r not in _ring:
        _ring[r] = [(i, j) for j in range(-r - 1, r + 2) for i in range(-r - 1, r + 2)
                    if r - 0.5 <= math.sqrt(i * i + j * j) < r + 0.5]
    for i, j in _ring[r]:
        cells(d, ox, oy, x + i, y + j, 1, 1, c)


def line_cells(a, b, pct):
    """The art pixels of the line from a to b, as far as pct (0-100) of the way."""
    (x0, y0), (x1, y1) = a, b
    n = max(abs(x1 - x0), abs(y1 - y0))
    m = n * pct // 100
    return [(x0 + round((x1 - x0) * i / n), y0 + round((y1 - y0) * i / n)) for i in range(m + 1)] if n else [a]


def tri_spans(v):
    """The rows of a triangle (three (x, y) in art pixels, floats): [(y, x0, x1)] by pixel centres."""
    ys = [p[1] for p in v]
    out = []
    for y in range(math.ceil(min(ys) - 0.5), math.floor(max(ys) - 0.5) + 1):
        yc = y + 0.5
        xs = []
        for i in range(3):
            (ax, ay), (bx, by) = v[i], v[(i + 1) % 3]
            if (ay <= yc <= by or by <= yc <= ay) and ay != by:
                xs.append(ax + (bx - ax) * (yc - ay) / (by - ay))
        if len(xs) >= 2:
            x0, x1 = math.ceil(min(xs) - 0.5), math.floor(max(xs) - 0.5)
            if x1 >= x0:
                out.append((y, x0, x1))
    return out


def text_spans(s):
    """The 8x8 font's lit runs for s: [(x, y, w)] in font pixels, to draw at any scale."""
    fb = framebuf.FrameBuffer(bytearray(len(s) * 8), len(s) * 8, 8, framebuf.MONO_HLSB)
    fb.text(s, 0, 0, 1)
    out = []
    for y in range(8):
        x = 0
        while x < len(s) * 8:
            if fb.pixel(x, y):
                x0 = x
                while x < len(s) * 8 and fb.pixel(x, y):
                    x += 1
                out.append((x0, y, x - x0))
            else:
                x += 1
    return out


NAME_SPANS = text_spans(NAME)
NAME_W = len(NAME) * 8 * NAME_S + (1 if NAME_S == 1 else 0)


def ascii(s):
    """The 8x8 font has only ASCII: the console's middle dots, ellipses and quotes, spelt in it."""
    for a, b in (("\u00b7", "-"), ("\u2026", ".."), ("\u2019", "'"), ("\u2018", "'"), ("\u2014", "-")):
        s = s.replace(a, b)
    return "".join(c if " " <= c <= "~" else "?" for c in s)


def wrap(s, cols):
    """At most two lines of cols letters, broken at spaces."""
    if len(s) <= cols:
        return [s]
    cut = s.rfind(" ", 0, cols + 1)
    cut = cut if cut > 0 else cols
    return [s[:cut], s[cut:].strip()[:cols]]


# ---- the diamond -----------------------------------------------------------------------------------
def box(s, y):
    return ((-s, y, s), (s, y, s), (s, y, -s), (-s, y, -s))


_geom = {}


def eth_geom(lk):
    """The diamond at this look: ([(rows, colour)] far to near, [signer (x, y)], node r, bbox in px)."""
    if lk in _geom:
        return _geom[lk]
    deg, u, rise, back, nr = lk
    green = deg < 75
    s = S0 + (S1 - S0) * u
    k = K0 + (K1 - K0) * u + (KB - K1) * back / 2
    oy = OY0 + (OY1 - OY0) * u + (OYB - OY1) * back / 2
    cy, sy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    ce, se = math.cos(EL * u), math.sin(EL * u)

    def view(p):
        x, y, z = p
        x, z = x * cy + z * sy, -x * sy + z * cy
        return x, y * ce + z * se, -y * se + z * ce

    top, base = (0.0, -1.0, 0.0), box(s, 0.0)
    tris = [((top, base[j], base[(j + 1) % 4]), (0.0, -0.3, 0.0), 1, j) for j in range(4)]
    if rise > 0:
        c = 0.5 * (1 - rise)
        rim, foot = box(s, GAP + c), (0.0, FOOT + c, 0.0)
        tris += [((rim[j], rim[(j + 1) % 4], foot), (0.0, GAP + 0.4 + c, 0.0), 0, j) for j in range(4)]
    polys = []
    for tri, inside, layer, j in tris:
        v = [view(p) for p in tri]
        ux, uy, uz = v[1][0] - v[0][0], v[1][1] - v[0][1], v[1][2] - v[0][2]
        wx, wy, wz = v[2][0] - v[0][0], v[2][1] - v[0][1], v[2][2] - v[0][2]
        nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        c = view(inside)
        if nx * (v[0][0] - c[0]) + ny * (v[0][1] - c[1]) + nz * (v[0][2] - c[2]) < 0:
            nx, ny, nz = -nx, -ny, -nz
        m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        if nz / m < 0.02:
            continue
        lit = max(0.0, (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / m)
        tone = min(3, int(lit * 4))
        if layer == 0 and rise < 1:
            tone = min(tone, int(4 * rise) - 1)     # it rises in through the darker tones
        if tone < 0:
            continue                                # still rising out of the dark
        ramp = GREEN if layer == 1 and j == 0 and green else BLUE_BACK[back]
        xy = [(CX + p[0] * k, oy + p[1] * k) for p in v]
        polys.append((layer * 10 + (v[0][2] + v[1][2] + v[2][2]) / 3, tri_spans(xy), ramp[tone]))
    polys.sort(key=lambda p: p[0])
    nodes = []
    if nr > 0:
        for p in (top, base[0], base[1]):
            x, y, _ = view(p)
            nodes.append((round(CX + x * k - 0.5), round(oy + y * k - 0.5)))
    x0 = y0 = 9999
    x1 = y1 = -9999
    for _, rows, _ in polys:
        for y, a, b in rows:
            x0, x1, y0, y1 = min(x0, a), max(x1, b), min(y0, y), max(y1, y)
    for x, y in nodes:
        x0, x1, y0, y1 = min(x0, x - nr), max(x1, x + nr), min(y0, y - nr), max(y1, y + nr)
    bb = (GX + x0 * P, GY + y0 * P, (x1 - x0 + 1) * P, (y1 - y0 + 1) * P) if x1 >= x0 else None
    g = ([(rows, col(rgb)) for _, rows, rgb in polys], nodes, nr, bb)
    if len(_geom) > 24:
        _geom.clear()
    _geom[lk] = g
    return g


# ---- what is on screen at step n: each element's look ------------------------------------------
# An element is (key, bbox in screen px, look); it is repainted only when its look changes.

def dot_look(k, n):
    if n < BORN + k:
        return None
    at = SIGN.get(k)
    if at is not None:
        if n >= TURN:
            return None                         # it rides its corner of the diamond now
        if n >= at:
            return (DOT + (n == at), GREEN[3] if n == at else GREEN[2])
        return (DOT + (n == BORN + k), AMBER)
    if n >= TURN:
        return None
    if n >= SETTLE:
        return (DOT - 1, AMBER_DIM)
    return (DOT + (n == BORN + k), AMBER_HI if (n // 3 + k) % 2 else AMBER)


def ring_look(k, n):
    at = SIGN.get(k)
    if at is None or not at <= n < at + 3:
        return None
    i = n - at
    return (DOT + 2 + 2 * i, GREEN[3 - i])


def edge_look(e, n):
    at = EDGES[e][2]
    if n < at or n >= TURN:
        return None
    return 50 if n == at else 100


def fill_look(n):
    if n < POUR or n >= TURN:
        return 0
    return min(4, n - POUR + 1)


def eth_look(n):
    if n < TURN:
        return None
    i = min(n - TURN, len(YAW) - 1)
    return (YAW[i], ZOOM[min(i, len(ZOOM) - 1)], min(4, max(0, n - RISE + 1)) / 4,
            min(2, max(0, n - BACK + 1)), max(0, DOT - (n - TURN)))


_chip = None        # (seed, text, rgb): set_chip


def set_chip(seed, text, ok=True):
    """The chip the console just read: its owner address (the blockie's seed) and a short line, red
    when it is not the pinned chip. None: no row. No room on the small panels."""
    global _chip
    if not CHIP_Y or not seed:
        _chip = None
        return
    text = ascii(text)[:(W - 20 - 8 * CHIP_PX - 10) // 8]
    _chip = (seed.lower(), text, INK if ok else BAD)


class Tile(framebuf.FrameBuffer):
    """A window of the screen in lcd's own buffer. y0/band_h as blockies expects of a strip."""

    def __init__(self, buf, w, h):
        super().__init__(buf, w, h, framebuf.RGB565)
        self.y0, self.band_h = 0, h


def _hit(a, x, y, w, h):
    return a is not None and a[0] < x + w and x < a[0] + a[2] and a[1] < y + h and y < a[1] + a[3]


class Pixel:
    def __init__(self, lcd, tagline=None):
        self.lcd = lcd
        tag = (taglines.pick() if tagline is None else tagline) if TAG_Y else ""
        self.tag = wrap(ascii(tag), TAG_COLS) if tag else []
        self.status = ("", MUTED)
        self.shown = None       # {key: (bbox, look)} on the panel now; None: nothing yet
        self.sent = 0           # bytes over SPI, for the record (test-vectors/run-bootpixel.mjs)
        self.last = None        # (n, status, chip) of the last frame: the same again sends nothing

    def elements(self, n):
        el = []
        for i, (x, y) in enumerate(STAR_AT):
            el.append(("*%d" % i, (GX + x * P, GY + y * P, P, P), STARS[((n + 5 * i) // 4) % 3]))
        lk = eth_look(n)
        if lk:
            el.append(("eth", eth_geom(lk)[3], lk))
        f = fill_look(n)
        if f:
            el.append(("fill", self.box(TOP[0] - R, TOP[1], 2 * R + 1, LEFT[1] - TOP[1] + 1), f))
        for e in range(3):
            lk = edge_look(e, n)
            if lk:
                a, b, _ = EDGES[e]
                el.append(("e%d" % e, self.box(min(a[0], b[0]), min(a[1], b[1]),
                                               abs(a[0] - b[0]) + 1, abs(a[1] - b[1]) + 1), lk))
        for k in range(5):
            lk = ring_look(k, n)
            if lk:
                r = lk[0] + 1
                el.append(("r%d" % k, self.box(PTS[k][0] - r, PTS[k][1] - r, 2 * r + 1, 2 * r + 1), lk))
            lk = dot_look(k, n)
            if lk:
                r = lk[0]
                el.append(("d%d" % k, self.box(PTS[k][0] - r, PTS[k][1] - r, 2 * r + 1, 2 * r + 1), lk))
        if n >= NAME0:
            i = min(2, n - NAME0)
            el.append(("name", ((W - NAME_W) // 2 - 1, NAME_Y - 9, NAME_W + NAME_S + 2, 9 * NAME_S + 11),
                       (i, (8, 4, 0)[i])))
        if self.tag and n >= TAG0:
            m = TAG_RATE * (n - TAG0 + 1)
            el.append(("tag", (0, TAG_Y, W, 8 * len(self.tag) + 4 * (len(self.tag) - 1)), m))
        if _chip:
            el.append(("chip", (0, CHIP_Y - 2, W, 8 * CHIP_PX + 4), _chip))
        if self.status[0]:
            el.append(("status", (0, STATUS_Y - 2, W, 12), self.status))
        return el

    @staticmethod
    def box(x, y, w, h):
        return (GX + x * P, GY + y * P, w * P, h * P)

    def draw(self, d, ox, oy, key, lk):
        c0 = key[0]
        if c0 == "*":
            i = int(key[1:])
            cells(d, ox, oy, STAR_AT[i][0], STAR_AT[i][1], 1, 1, col(lk))
        elif key == "eth":
            polys, nodes, nr, _ = eth_geom(lk)
            for rows, c in polys:
                for y, a, b in rows:
                    cells(d, ox, oy, a, y, b - a + 1, 1, c)
            for x, y in nodes:
                disc(d, ox, oy, x, y, nr, col(GREEN[3]))
        elif key == "fill":
            h = (LEFT[1] - TOP[1] + 1) * lk // 4
            ca, cb = col(GREEN[1]), col(GREEN[2])
            for y, a, b in tri_spans([(TOP[0] + 0.5, TOP[1]), (LEFT[0] + 0.5, LEFT[1] + 1), (RIGHT[0] + 0.5, RIGHT[1] + 1)]):
                if y <= LEFT[1] - h:
                    continue
                cells(d, ox, oy, a, y, b - a + 1, 1, ca)
                for x in range(a + (a + y) % 2, b + 1, 2):      # the dither: every other pixel lighter
                    cells(d, ox, oy, x, y, 1, 1, cb)
        elif c0 == "e":
            e = int(key[1:])
            c = col(GREEN[3])
            for x, y in line_cells(EDGES[e][0], EDGES[e][1], lk):
                cells(d, ox, oy, x, y, 1, 1, c)
        elif c0 == "r":
            k = int(key[1:])
            ring(d, ox, oy, PTS[k][0], PTS[k][1], lk[0], col(lk[1]))
        elif c0 == "d":
            k = int(key[1:])
            disc(d, ox, oy, PTS[k][0], PTS[k][1], lk[0], col(lk[1]))
        elif key == "name":
            i, drop = lk
            s, x, y = NAME_S, (W - NAME_W) // 2 - ox, NAME_Y - drop - oy
            ink = col((SHADOW, MUTED, INK)[i])
            if i:
                sh = col(SHADOW)
                for a, b, w in NAME_SPANS:
                    d.fill_rect(x + a * s + s, y + b * s + s, w * s + (s == 1), s, sh)
            for a, b, w in NAME_SPANS:
                d.fill_rect(x + a * s, y + b * s, w * s + (s == 1), s, ink)
        elif key == "tag":
            left, typing = lk, lk < sum(len(t) for t in self.tag)
            for j, line in enumerate(self.tag):
                part = line[:max(0, left)]
                x, y = (W - 8 * len(line)) // 2 - ox, TAG_Y + 12 * j - oy
                d.text(part, x, y, col(INK))
                if typing and left >= 0 and len(part) < len(line):
                    d.fill_rect(x + 8 * len(part) + 1, y, 6, 8, col(AMBER))     # the cursor, while it types
                    typing = False
                left -= len(line)
        elif key == "chip":
            seed, text, rgb = lk
            side = 8 * CHIP_PX
            x = (W - side - 10 - 8 * len(text)) // 2
            import blockies
            blockies.draw(d, seed, x - ox, CHIP_Y - oy, CHIP_PX)
            d.text(text, x + side + 10 - ox, CHIP_Y + (side - 8) // 2 - oy, col(rgb))
        elif key == "status":
            s, rgb = lk
            d.text(s, (W - 8 * len(s)) // 2 - ox, STATUS_Y - oy, col(rgb))

    def scene(self, d, ox, oy, w, h, els):
        d.fill(col(BG))
        for key, bb, lk in els:
            if _hit(bb, ox, oy, w, h):
                self.draw(d, ox, oy, key, lk)

    def paint(self, x, y, w, h, els):
        """One rectangle: drawn into lcd's buffer as many rows at a time as fit, each sent to its window."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        w = x1 - x0
        rows = min(y1 - y0, len(L._BUF) // (2 * w))
        lcd = self.lcd
        for top in range(y0, y1, rows):
            n = min(rows, y1 - top)
            d = Tile(L._BUF, w, n)
            self.scene(d, x0, top, w, n, els)
            lcd._window(board.X_OFF + x0, board.Y_OFF + top, w, n)
            lcd.dc(1); lcd.cs(0); lcd.spi.write(memoryview(L._BUF)[:2 * w * n]); lcd.cs(1)
            self.sent += 2 * w * n

    def frame(self, t, status=None, status_rgb=MUTED):
        if status is not None:      # splash's red for a failed step, its grey for the rest
            self.status = (ascii(status)[:(W - 8) // 8], BAD if status_rgb[0] > 200 and status_rgb[1] < 120 else MUTED)
        n = min(END, t // STEP_MS)
        if self.last == (n, self.status, _chip):
            return                              # between steps: nothing has changed
        self.last = (n, self.status, _chip)
        els = self.elements(n)
        if self.shown is None:
            self.paint(0, 0, W, H, els)
        else:
            new = {key: (bb, lk) for key, bb, lk in els}
            for key in set(self.shown) | set(new):
                a, b = self.shown.get(key), new.get(key)
                if a != b:
                    for bb in {a[0] if a else None, b[0] if b else None}:
                        if bb:
                            self.paint(bb[0], bb[1], bb[2], bb[3], els)
        self.shown = {key: (bb, lk) for key, bb, lk in els}


_pix = None


def render(screen, t, status, status_color, still=False):
    """splash's entry: t is ms since the lead-in. The first call paints the whole panel once and
    picks this boot's tagline."""
    global _pix
    if _pix is None or _pix.lcd is not screen:
        _pix = Pixel(screen)
    _pix.frame(STILL if still else t, status, status_color)
