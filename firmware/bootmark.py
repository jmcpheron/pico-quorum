# The light boot screen: the PicoQuorum mark turning into Ethereum, as flat vectors. Five owners pop
# in, three sign and their triangle fills green. With no hold, that triangle is the front face of the
# Ethereum diamond seen head-on: it starts to turn, the signers ride its corners away, the two who
# didn't sign fade, the lower pyramid rises in and the green face goes blue round the back. The
# Ethereum logo, spinning. It slows, grows and dims, and the small mark and PicoQuorum fade in over
# it, then a tagline (taglines.py); it keeps turning for as long as the boot screen is up. The real
# boot status is the last line.
# The orbit (bootart.py) redraws and sends the whole panel every frame, about 110 ms a frame on the
# Pico. This sends only what changed since the last frame: a dot's square, an edge as far as it has
# got, the rows the green rose through, the box the diamond was in and is in now. A frame where
# nothing changed costs nothing.
#   secrets.BOOT_ART = "mark"  (the default) this, animated, about 3.7 s
#                      "still" the finished screen at once; only the status line changes after
#                      "orbit" the full orbit animation (bootart.py)
# Visual branding only: the three green dots do not report actual signatures.
import math
import framebuf
from array import array
import board
import lcd as L
import fonts as F
import taglines

LEAD_MS = 300           # black before the first frame (splash)
IN_MS = True            # splash passes render the time in ms (the orbit takes a frame number)
BG, INK, MUTED = (11, 13, 17), (242, 244, 247), (152, 160, 172)
OK, WAIT, WAIT_HI = (52, 199, 89), (255, 184, 48), (255, 226, 150)
OK_DARK, OK_LIGHT = (0, 96, 36), (120, 255, 150)        # bootart's green and Ethereum blue, shaded
ETH_DARK, ETH_LIGHT = (30, 36, 92), (218, 226, 255)
SIGNERS = (0, 3, 2)     # top, lower left, lower right: the quorum; 1 and 4 stay amber
SMALL = L.H < 200       # the 1.8": 160x128
R = 30 if SMALL else 62                     # the owners' circle
CX, CY = L.W // 2, 40 if SMALL else 84
DOT = 5 if SMALL else 8
EDGE = 2 if SMALL else 3
RING = 12 if SMALL else 22                  # how far a signer's ring goes out
NAME = "PicoQuorum"
NAME_FONT, NAME_Y = ("bold18", 43) if SMALL else ("bold26", 89)   # in front of the diamond
ICON_R = 8 if SMALL else 12                 # the small mark left of the name
ICON_W = 2 * ICON_R + 10
TAG_FONT, TAG_Y = "sans14", None if SMALL else 136     # no room for a tagline on the 1.8"
TAG_INK = (200, 205, 214)                   # a step brighter than the status line under it
STATUS_FONT = "sans12" if SMALL else "sans14"
STATUS_Y = L.H - (18 if SMALL else 26)
PTS = [(int(CX + R * math.cos(math.radians(-90 + 72 * k))),
        int(CY + R * math.sin(math.radians(-90 + 72 * k)))) for k in range(5)]
TOP, LEFT, RIGHT = PTS[0], PTS[3], PTS[2]

# The timeline, ms after the lead-in. No holds: each move starts as the one before it ends.
BORN, BORN_EACH = 0, 80                     # the five owners pop in, one after another
SIGN = {0: 450, 3: 750, 2: 1050}            # each signer turns green and a ring goes out
EDGES = ((TOP, LEFT, 750), (TOP, RIGHT, 1050), (LEFT, RIGHT, 1250))
EDGE_MS, RING_MS = 250, 420
SETTLE0, SETTLE1 = 1300, 1550               # the two who didn't sign shrink a little
POUR0, POUR1 = 1400, 1750                   # the triangle fills from its base up
TURN0, TURN1 = 1750, 2750                   # the diamond takes over from it and becomes the logo
RISE0 = 2100                                # the lower pyramid rises in
BACK0, BACK1 = 2750, 3250                   # it slows, grows and dims behind the name
NAME0, NAME1 = 2950, 3350                   # the small mark and the name fade in over it
TAG0, TAG1 = 3250, 3650                     # then the tagline
DURATION_MS = 3700                          # splash holds the boot screen this long
STILL = 1 << 30                             # "still": every element at its end

# The diamond is bootart.py's: a square pyramid (apex 1 unit up) over an inverted one, seen from up
# to 30° above, lit from the upper left, turned about its axis. Head-on (no turn, no tilt) its front
# face is exactly the quorum's triangle, so the filled triangle becomes it without a seam.
K0, OY0 = LEFT[1] - TOP[1], LEFT[1]         # pixels per unit, and where the base sits, head-on
S0 = (RIGHT[0] - LEFT[0]) / 2 / K0          # the triangle's half-base per unit of height
S1, GAP, FOOT = 0.37, 0.12, 0.97            # the logo's half-base, the gap, the lower tip
EL = math.radians(30)
K1, OY1, KB, OYB = (40, 52, 44, 54) if SMALL else (80, 100, 88, 104)   # the logo; behind the name
BACK_DIM = 0.66
SPIN_V, BACK_V, ACC = 0.30, 0.03, 400       # degrees a ms turning and behind the name; the run-up
_l = math.sqrt(0.55 * 0.55 * 2 + 0.63 * 0.63)
LIGHT = (-0.55 / _l, -0.55 / _l, 0.63 / _l)


def mix(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def span(t, a, b):
    return 0.0 if t <= a else 1.0 if t >= b else (t - a) / (b - a)


def ease(u):
    return 1 - (1 - u) ** 3


def smooth(u):
    return u * u * (3 - 2 * u)


# The front face lit head-on, and the triangle's fill: the same green, so the hand-off is seamless.
FACE = mix(OK_DARK, OK_LIGHT, 0.12 + 0.88 * max(0.0, (-S0 * LIGHT[1] + LIGHT[2]) / math.sqrt(S0 * S0 + 1)))
FILL = mix(BG, FACE, 0.55)


class Tile(framebuf.FrameBuffer):
    """A window of the screen in lcd's own buffer. y0/band_h as fonts.text expects of a strip."""

    def __init__(self, buf, w, h):
        super().__init__(buf, w, h, framebuf.RGB565)
        self.y0, self.band_h = 0, h


# ---- what is on screen at time t: each element's look, and how to draw it -------------------------
# A look is a small tuple; an element is repainted only when its look changes.

def dot_look(k, t):
    born = ease(span(t, BORN + BORN_EACH * k, BORN + BORN_EACH * k + 260))
    if born <= 0:
        return (0, BG)
    at = SIGN.get(k)
    if at is not None:
        if t >= TURN0:
            return (0, BG)                      # it rides its corner of the diamond now
        if t >= at:
            pop = math.sin(math.pi * span(t, at, at + 240))
            return (DOT + int(3 * pop), mix(WAIT, OK, span(t, at, at + 120)))
    # the waiting ones breathe, in 6 steps so a breath is a few repaints, not one a frame; once
    # the quorum has signed, the two left out settle smaller, then fade as the diamond turns
    gone = span(t, TURN0, TURN0 + 300)
    if gone >= 1:
        return (0, BG)
    b = int(3 + 3 * math.sin(t / 260 + k)) / 6
    r = DOT * born * (1 - 0.3 * span(t, SETTLE0, SETTLE1)) if at is None else DOT * born
    return (max(1, int(r + 0.5)), mix(mix(BG, mix(WAIT, WAIT_HI, b), born), BG, int(4 * gone) / 4))


def ring_look(k, t):
    at = SIGN.get(k)
    q = span(t, at, at + RING_MS) if at is not None else 0
    if not 0 < q < 1:
        return None
    return (DOT + 4 + int(RING * ease(q)), mix(BG, OK, (1 - q) ** 2))


def edge_look(e, t):
    """How far it has got (%), and how far it has faded into the face as the diamond turns (0-4)."""
    f = int(4 * span(t, TURN0, TURN0 + 200))
    return (0, 0) if f >= 4 else (int(100 * span(t, EDGES[e][2], EDGES[e][2] + EDGE_MS)), f)


def edge_at(e, pct):
    a, b, _ = EDGES[e]
    return a[0] + (b[0] - a[0]) * pct // 100, a[1] + (b[1] - a[1]) * pct // 100


def fill_look(t):
    """The height of the green, in rows up from the base (0: none, full: to the top). From the
    turn on, the diamond's face is the green."""
    return 0 if t >= TURN0 else int((LEFT[1] - TOP[1]) * span(t, POUR0, POUR1))


def name_look(t):
    a = span(t, NAME0, NAME1)
    return (int(8 * a), int(8 * (1 - ease(a))))         # the fade, and how far below its place


def tag_look(t):
    return int(8 * span(t, TAG0, TAG1)) if TAG_Y else 0


def yaw_at(t):
    """Degrees turned: it runs up, turns, slows behind the name and never stops."""
    if t >= STILL:
        return 45.0                             # the logo's own pose: a corner toward you
    a = t - TURN0
    if a <= 0:
        return 0.0
    deg = SPIN_V * min(a, ACC) ** 2 / (2 * ACC)
    if a > ACC:
        deg += SPIN_V * (min(t, BACK0) - TURN0 - ACC)
    if t > BACK0:
        b, n = min(t, BACK1) - BACK0, BACK1 - BACK0
        deg += SPIN_V * b - (SPIN_V - BACK_V) * b * b / (2 * n)
    if t > BACK1:
        deg += BACK_V * (t - BACK1)
    return deg


def eth_look(t):
    """None before the turn, else (zoom /64, yaw, rise /32, green /16, glow /8, back /32, node r)."""
    if t < TURN0:
        return None
    deg = yaw_at(t)
    green = 0 if t >= STILL else 1 - span(deg, 60, 120)     # the quorum's face goes blue round the back
    return (int(64 * smooth(span(t, TURN0, TURN1))),
            int(deg) % (360 if green > 0 else 90),      # the same every quarter turn once all blue
            int(32 * smooth(span(t, RISE0, TURN1))), int(16 * green), int(8 * span(t, TURN0, TURN0 + 300)),
            int(32 * smooth(span(t, BACK0, BACK1))), int(DOT * (1 - span(t, TURN0 + 50, TURN0 + 450)) + 0.5))


def box(s, y):
    """The four corners of a square of half-side s at height y, front edge first (z toward us)."""
    return ((-s, y, s), (s, y, s), (s, y, -s), (-s, y, -s))


def eth_geom(lk):
    """The diamond at this look: ([(depth, xy, colour)] far to near, [signer (x, y)], node r, box)."""
    zoom, deg, rise, green, glow, back, nr = lk
    u, rise, green, glow, back = zoom / 64, rise / 32, green / 16, glow / 8, back / 32
    s = S0 + (S1 - S0) * u
    k = K0 + (K1 - K0) * u + (KB - K1) * back
    oy = OY0 + (OY1 - OY0) * u + (OYB - OY1) * back
    cy, sy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    ce, se = math.cos(EL * u), math.sin(EL * u)

    def view(p):
        x, y, z = p
        x, z = x * cy + z * sy, -x * sy + z * cy                # turn about the axis
        return x, y * ce + z * se, -y * se + z * ce             # from a little above

    top, base = (0.0, -1.0, 0.0), box(s, 0.0)
    tris = [((top, base[j], base[(j + 1) % 4]), (0.0, -0.3, 0.0), 1, j) for j in range(4)]
    if rise > 0:                                # the lower pyramid, rising into place
        c = 0.5 * (1 - rise)
        rim, foot = box(s, GAP + c), (0.0, FOOT + c, 0.0)
        tris += [((rim[j], rim[(j + 1) % 4], foot), (0.0, GAP + 0.4 + c, 0.0), 0, j) for j in range(4)]
    polys = []
    x0 = y0 = 9999
    x1 = y1 = -9999
    for tri, inside, layer, j in tris:
        v = [view(p) for p in tri]
        ux, uy, uz = v[1][0] - v[0][0], v[1][1] - v[0][1], v[1][2] - v[0][2]
        wx, wy, wz = v[2][0] - v[0][0], v[2][1] - v[0][1], v[2][2] - v[0][2]
        nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        c = view(inside)
        if nx * (v[0][0] - c[0]) + ny * (v[0][1] - c[1]) + nz * (v[0][2] - c[2]) < 0:
            nx, ny, nz = -nx, -ny, -nz          # point it out of the solid
        m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        if nz / m < 0.02:
            continue                            # facing away, or edge-on
        lit = 0.12 + 0.88 * max(0.0, (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / m)
        rgb = mix(ETH_DARK, ETH_LIGHT, lit)
        if layer == 1 and j == 0 and green > 0:     # the quorum's face: the fill, brightening as it turns
            rgb = mix(rgb, mix(BG, mix(OK_DARK, OK_LIGHT, lit), 0.55 + 0.45 * glow), green)
        if layer == 0 and rise < 1:             # fade in through its own dark shade
            rgb = mix(mix(BG, ETH_DARK, min(1.0, 2 * rise)), rgb, rise)
        if back > 0:
            rgb = mix(rgb, BG, BACK_DIM * back)
        xy = array("h", [0] * 6)
        for i in range(3):
            px, py = int(CX + v[i][0] * k), int(oy + v[i][1] * k)
            xy[2 * i], xy[2 * i + 1] = px, py
            x0, x1, y0, y1 = min(x0, px), max(x1, px), min(y0, py), max(y1, py)
        polys.append((layer * 10 + (v[0][2] + v[1][2] + v[2][2]) / 3, xy, L.color(*rgb)))
    polys.sort(key=lambda p: p[0])              # the lower pyramid first, then far to near
    nodes = []
    if nr > 0:                                  # the signers, riding the corners they became
        for p in (top, base[0], base[1]):
            x, y, _ = view(p)
            px, py = int(CX + x * k), int(oy + y * k)
            nodes.append((px, py))
            x0, x1, y0, y1 = min(x0, px - nr), max(x1, px + nr), min(y0, py - nr), max(y1, py + nr)
    return polys, nodes, nr, (x0 - 1, y0 - 1, x1 - x0 + 3, y1 - y0 + 3)


def draw_fill(d, ox, oy, h):
    if h <= 0:
        return
    f = h / (LEFT[1] - TOP[1])
    y = LEFT[1] - h
    xl = int(LEFT[0] + (TOP[0] - LEFT[0]) * f)
    xr = int(RIGHT[0] + (TOP[0] - RIGHT[0]) * f)
    d.poly(-ox, -oy, array("h", [LEFT[0], LEFT[1], RIGHT[0], RIGHT[1], xr, y, xl, y]), L.color(*FILL), True)
    if h < LEFT[1] - TOP[1]:                    # the surface, brighter while it rises
        d.hline(xl - ox, y - oy, xr - xl + 1, L.color(*FACE))


def draw_edge(d, ox, oy, e, lk):
    pct, f = lk
    if pct <= 0:
        return
    a = EDGES[e][0]
    x1, y1 = edge_at(e, pct)
    c = L.color(*mix(OK, FILL, f / 4))
    for k in range(-(EDGE // 2), EDGE - EDGE // 2):
        d.line(a[0] + k - ox, a[1] - oy, x1 + k - ox, y1 - oy, c)
        d.line(a[0] - ox, a[1] + k - oy, x1 - ox, y1 + k - oy, c)


def draw_icon(d, ox, oy, cx, cy, a):
    """The PicoQuorum mark, small: five owners, three signed, their triangle. Rounded on the
    screen, then shifted, so every tile agrees on its pixels."""
    pts = [(int(cx + ICON_R * math.cos(math.radians(-90 + 72 * k))) - ox,
            int(cy + ICON_R * math.sin(math.radians(-90 + 72 * k))) - oy) for k in range(5)]
    d.poly(0, 0, array("h", [pts[0][0], pts[0][1], pts[2][0], pts[2][1], pts[3][0], pts[3][1]]),
           L.color(*mix(BG, FACE, a * 0.55)), True)
    for k in (1, 4):
        d.ellipse(pts[k][0], pts[k][1], 1 if SMALL else 2, 1 if SMALL else 2, L.color(*mix(BG, WAIT, a * 0.8)), True)
    for k in (0, 2, 3):
        d.ellipse(pts[k][0], pts[k][1], 2 if SMALL else 3, 2 if SMALL else 3, L.color(*mix(BG, OK, a)), True)


class Mark:
    def __init__(self, lcd, tagline=None):
        self.lcd = lcd
        self.tag = (taglines.pick() if tagline is None else tagline) if TAG_Y else ""
        self.tag_w = F.width(self.tag, TAG_FONT) if self.tag else 0
        self.name_w = ICON_W + F.width(NAME, NAME_FONT)
        self.shown = None       # the looks on the panel now; None: nothing yet (the panel is black)
        self.status = ("", MUTED, 0)   # text cut to fit, colour, width
        self.sent = 0           # bytes over SPI, for the record (test-vectors/run-bootmark.mjs)
        self.eth = None         # (look, eth_geom) of the diamond on the panel now
        self.eth_new = None     # and of the one being drawn

    def looks(self, t):
        return ([dot_look(k, t) for k in range(5)], [ring_look(k, t) for k in range(5)],
                [edge_look(e, t) for e in range(3)], fill_look(t), name_look(t), self.status,
                tag_look(t) if self.tag else 0, eth_look(t))

    def scene(self, d, ox, oy, lk):
        """Everything, shifted by (-ox, -oy) into d; framebuf clips what falls outside."""
        dots, rings, edges, fill, name, status, tag, _ = lk
        d.fill(L.color(*BG))
        if self.eth_new:
            polys, nodes, nr, _ = self.eth_new[1]
            for _, xy, c in polys:
                d.poly(-ox, -oy, xy, c, True)
            for x, y in nodes:
                d.ellipse(x - ox, y - oy, nr, nr, L.color(*OK), True)
        draw_fill(d, ox, oy, fill)
        for e in range(3):
            draw_edge(d, ox, oy, e, edges[e])
        for k in range(5):
            if rings[k]:
                r, rgb = rings[k]
                x, y = PTS[k]
                c = L.color(*rgb)
                d.ellipse(x - ox, y - oy, r, r, c)
                d.ellipse(x - ox, y - oy, r + 1, r + 1, c)
            r, rgb = dots[k]
            if rgb != BG:
                d.ellipse(PTS[k][0] - ox, PTS[k][1] - oy, r, r, L.color(*rgb), True)
        a, below = name
        if a:
            x, y = (L.W - self.name_w) // 2, NAME_Y + below
            draw_icon(d, ox, oy, x + ICON_R + 1, y + F.height(NAME_FONT) // 2 + 2, a / 8)
            F.text(d, NAME, x + ICON_W - ox, y - oy, NAME_FONT, mix(BG, INK, a / 8), BG)
        if tag:
            F.text(d, self.tag, (L.W - self.tag_w) // 2 - ox, TAG_Y - oy, TAG_FONT, mix(BG, TAG_INK, tag / 8), BG)
        s, rgb, w = status
        if s:
            F.text(d, s, (L.W - w) // 2 - ox, STATUS_Y - oy, STATUS_FONT, rgb, BG)

    def dirty(self, old, new):
        """The screen rectangles (x, y, w, h) that differ between two sets of looks."""
        out = []
        for k in range(5):
            if old[0][k] != new[0][k]:
                r = DOT + 4
                out.append((PTS[k][0] - r, PTS[k][1] - r, 2 * r + 1, 2 * r + 1))
            if old[1][k] != new[1][k]:
                r = DOT + 6 + RING
                out.append((PTS[k][0] - r, PTS[k][1] - r, 2 * r + 1, 2 * r + 1))
        for e in range(3):
            if old[2][e] != new[2][e]:
                # from its start to the further end: a shorter line's pixels are not a prefix of a
                # longer one's, so the piece drawn since the last frame alone leaves strays
                (x0, y0), (x1, y1) = EDGES[e][0], edge_at(e, max(old[2][e][0], new[2][e][0]))
                out.append((min(x0, x1) - EDGE, min(y0, y1) - EDGE, abs(x1 - x0) + 2 * EDGE + 1,
                            abs(y1 - y0) + 2 * EDGE + 1))
        if old[3] != new[3]:                    # only the rows the surface moved through
            lo, hi = sorted((old[3], new[3]))
            out.append((LEFT[0] - EDGE, LEFT[1] - hi - 1, RIGHT[0] - LEFT[0] + 2 * EDGE + 1, hi - lo + 3))
        if old[4] != new[4]:                    # the icon and the name, wherever they slid from
            out.append(((L.W - self.name_w) // 2 - 2, NAME_Y - 4, self.name_w + 4, F.height(NAME_FONT) + 16))
        if old[6] != new[6]:
            out.append(((L.W - self.tag_w) // 2 - 2, TAG_Y - 4, self.tag_w + 4, F.height(TAG_FONT) + 8))
        if old[5] != new[5]:
            out.append((0, STATUS_Y - 4, L.W, F.height(STATUS_FONT) + 8))
        if old[7] != new[7]:                    # the box it was in and the box it is in, as one
            bs = [g[1][3] for g in (self.eth, self.eth_new) if g]
            x0, y0 = min(b[0] for b in bs), min(b[1] for b in bs)
            out.append((x0, y0, max(b[0] + b[2] for b in bs) - x0, max(b[1] + b[3] for b in bs) - y0))
        return out

    def paint(self, x, y, w, h, lk):
        """One rectangle: drawn into lcd's buffer as many rows at a time as fit, each sent to its window."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(L.W, x + w), min(L.H, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        w = x1 - x0
        rows = min(y1 - y0, len(L._BUF) // (2 * w))
        lcd = self.lcd
        for top in range(y0, y1, rows):
            n = min(rows, y1 - top)
            d = Tile(L._BUF, w, n)
            self.scene(d, x0, top, lk)
            lcd._window(board.X_OFF + x0, board.Y_OFF + top, w, n)
            lcd.dc(1); lcd.cs(0); lcd.spi.write(memoryview(L._BUF)[:2 * w * n]); lcd.cs(1)
            self.sent += 2 * w * n

    def frame(self, t, status=None, status_rgb=MUTED):
        if status is not None and status != self.status[0]:
            while F.width(status, STATUS_FONT) > L.W - 20:
                status = status[:-1]
            self.status = (status, status_rgb, F.width(status, STATUS_FONT))
        elif status is not None:
            self.status = (status, status_rgb, self.status[2])
        lk = self.looks(t)
        e = lk[7]
        self.eth_new = None if e is None else self.eth if self.eth and self.eth[0] == e else (e, eth_geom(e))
        if self.shown is None:
            self.paint(0, 0, L.W, L.H, lk)
        else:
            for r in self.dirty(self.shown, lk):
                self.paint(r[0], r[1], r[2], r[3], lk)
        self.shown, self.eth = lk, self.eth_new


_mark = None


def render(screen, t, status, status_color, still=False):
    """splash's entry: t is ms since the lead-in. The first call paints the whole panel once and
    picks this boot's tagline."""
    global _mark
    if _mark is None or _mark.lcd is not screen:
        _mark = Mark(screen)
    _mark.frame(STILL if still else t, status, status_color)
