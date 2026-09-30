# The light boot screen: the PicoQuorum mark as flat vectors (five owners, three sign, their
# triangle fills green, the other two stay amber), the name under it, the real boot status last.
# The orbit (bootart.py) redraws and sends the whole panel every frame, about 110 ms a frame on
# the Pico. This sends only what changed since the last frame: a dot's square, an edge as far as
# it has got, the rows the green rose through. Most frames are a few KB of SPI and a dozen
# framebuf calls, and a frame where nothing changed costs nothing.
#   secrets.BOOT_ART = "mark"  (the default) this, animated, about 3.5 s
#                      "still" the finished mark at once; only the status line changes after
#                      "orbit" the full orbit animation (bootart.py)
# Visual branding only: the three green dots do not report actual signatures.
import math
import framebuf
from array import array
import board
import lcd as L
import fonts as F

LEAD_MS = 300           # black before the first frame (splash)
IN_MS = True            # splash passes render the time in ms (the orbit takes a frame number)
BG, INK, MUTED = (11, 13, 17), (242, 244, 247), (152, 160, 172)
OK, WAIT, WAIT_HI = (52, 199, 89), (255, 184, 48), (255, 226, 150)
FACE = (95, 222, 126)   # the orbit's lit green face (bootart.FACE_GREEN)
SIGNERS = (0, 3, 2)     # top, lower left, lower right: the quorum; 1 and 4 stay amber
SMALL = L.H < 200       # the 1.8": 160x128
R = 30 if SMALL else 62                     # the owners' circle
CX, CY = L.W // 2, 40 if SMALL else 92
DOT = 5 if SMALL else 8
EDGE = 2 if SMALL else 3
RING = 12 if SMALL else 22                  # how far a signer's ring goes out
NAME_FONT, NAME_Y = ("bold18", 78) if SMALL else ("bold26", 172)
STATUS_FONT = "sans12" if SMALL else "sans14"
STATUS_Y = L.H - (18 if SMALL else 26)
PTS = [(int(CX + R * math.cos(math.radians(-90 + 72 * k))),
        int(CY + R * math.sin(math.radians(-90 + 72 * k)))) for k in range(5)]
TOP, LEFT, RIGHT = PTS[0], PTS[3], PTS[2]

# The timeline, ms after the lead-in
BORN, BORN_EACH = 0, 110                    # the five owners pop in, one after another
SIGN = {0: 750, 3: 1250, 2: 1750}           # each signer turns green and a ring goes out
EDGES = ((TOP, LEFT, 1250), (TOP, RIGHT, 1750), (LEFT, RIGHT, 2050))
EDGE_MS, RING_MS = 300, 420
SETTLE0, SETTLE1 = 2050, 2450               # the two who didn't sign shrink a little
POUR0, POUR1 = 2350, 2900                   # the triangle fills from its base up
NAME0, NAME1 = 2700, 3300                   # the name fades in
DURATION_MS = 3500                          # splash holds the boot screen this long
STILL = 1 << 30                             # "still": every element at its end


def mix(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def span(t, a, b):
    return 0.0 if t <= a else 1.0 if t >= b else (t - a) / (b - a)


def ease(u):
    return 1 - (1 - u) ** 3


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
    if at is not None and t >= at:
        pop = math.sin(math.pi * span(t, at, at + 240))
        return (DOT + int(3 * pop), mix(WAIT, OK, span(t, at, at + 120)))
    # the waiting ones breathe, in 6 steps so a breath is a few repaints, not one a frame; once
    # the quorum has signed, the two left out settle smaller, as in the small mark
    b = int(3 + 3 * math.sin(t / 260 + k)) / 6 if t < STILL else 0.5
    r = DOT * born * (1 - 0.3 * span(t, SETTLE0, SETTLE1)) if at is None else DOT * born
    return (max(1, int(r + 0.5)), mix(BG, mix(WAIT, WAIT_HI, b), born))


def ring_look(k, t):
    at = SIGN.get(k)
    q = span(t, at, at + RING_MS) if at is not None else 0
    if not 0 < q < 1:
        return None
    return (DOT + 4 + int(RING * ease(q)), mix(BG, OK, (1 - q) ** 2))


def edge_look(e, t):
    return int(100 * span(t, EDGES[e][2], EDGES[e][2] + EDGE_MS))


def edge_at(e, pct):
    a, b, _ = EDGES[e]
    return a[0] + (b[0] - a[0]) * pct // 100, a[1] + (b[1] - a[1]) * pct // 100


def fill_look(t):
    """The height of the green, in rows up from the base (0: none, full: to the top)."""
    return int((LEFT[1] - TOP[1]) * span(t, POUR0, POUR1))


def name_look(t):
    return int(8 * span(t, NAME0, NAME1))


def draw_fill(d, ox, oy, h):
    if h <= 0:
        return
    f = h / (LEFT[1] - TOP[1])
    y = LEFT[1] - h
    xl = int(LEFT[0] + (TOP[0] - LEFT[0]) * f)
    xr = int(RIGHT[0] + (TOP[0] - RIGHT[0]) * f)
    d.poly(-ox, -oy, array("h", [LEFT[0], LEFT[1], RIGHT[0], RIGHT[1], xr, y, xl, y]),
           L.color(*mix(BG, FACE, 0.55)), True)
    if h < LEFT[1] - TOP[1]:                    # the surface, brighter while it rises
        d.hline(xl - ox, y - oy, xr - xl + 1, L.color(*FACE))


def draw_edge(d, ox, oy, e, pct):
    if pct <= 0:
        return
    a = EDGES[e][0]
    x1, y1 = edge_at(e, pct)
    c = L.color(*OK)
    for k in range(-(EDGE // 2), EDGE - EDGE // 2):
        d.line(a[0] + k - ox, a[1] - oy, x1 + k - ox, y1 - oy, c)
        d.line(a[0] - ox, a[1] + k - oy, x1 - ox, y1 + k - oy, c)


class Mark:
    def __init__(self, lcd):
        self.lcd = lcd
        self.shown = None       # the looks on the panel now; None: nothing yet (the panel is black)
        self.status = ("", MUTED, 0)   # text cut to fit, colour, width
        self.sent = 0           # bytes over SPI, for the record (test-vectors/run-bootmark.mjs)

    def looks(self, t):
        return ([dot_look(k, t) for k in range(5)], [ring_look(k, t) for k in range(5)],
                [edge_look(e, t) for e in range(3)], fill_look(t), name_look(t), self.status)

    def scene(self, d, ox, oy, lk):
        """Everything, shifted by (-ox, -oy) into d; framebuf clips what falls outside."""
        dots, rings, edges, fill, name, status = lk
        d.fill(L.color(*BG))
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
        if name:
            w = F.width("PicoQuorum", NAME_FONT)
            F.text(d, "PicoQuorum", (L.W - w) // 2 - ox, NAME_Y - oy, NAME_FONT, mix(BG, INK, name / 8), BG)
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
                (x0, y0), (x1, y1) = EDGES[e][0], edge_at(e, max(old[2][e], new[2][e]))
                out.append((min(x0, x1) - EDGE, min(y0, y1) - EDGE, abs(x1 - x0) + 2 * EDGE + 1,
                            abs(y1 - y0) + 2 * EDGE + 1))
        if old[3] != new[3]:                    # only the rows the surface moved through
            lo, hi = sorted((old[3], new[3]))
            out.append((LEFT[0] - EDGE, LEFT[1] - hi - 1, RIGHT[0] - LEFT[0] + 2 * EDGE + 1, hi - lo + 3))
        if old[4] != new[4]:
            w = F.width("PicoQuorum", NAME_FONT)
            out.append(((L.W - w) // 2 - 2, NAME_Y - 4, w + 4, F.height(NAME_FONT) + 8))
        if old[5] != new[5]:
            out.append((0, STATUS_Y - 4, L.W, F.height(STATUS_FONT) + 8))
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
        if self.shown is None:
            self.paint(0, 0, L.W, L.H, lk)
        else:
            for r in self.dirty(self.shown, lk):
                self.paint(r[0], r[1], r[2], r[3], lk)
        self.shown = lk


_mark = None


def render(screen, t, status, status_color, still=False):
    """splash's entry: t is ms since the lead-in. The first call paints the whole panel once."""
    global _mark
    if _mark is None or _mark.lcd is not screen:
        _mark = Mark(screen)
    _mark.frame(STILL if still else t, status, status_color)
