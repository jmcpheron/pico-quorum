# Orbit loading artwork adapted from claude/happy-carson-dzf85b, d863ca1 (iteration 6).
# Visual branding only: the three green dots do not report actual transaction signatures.
# No timer, hardware ownership, network calls, or demo status messages.
import math
from array import array
import lcd as L
import fonts as F
T = {"bg": (11,13,17), "text": (242,244,247), "muted": (152,160,172),
     "warn": (255,184,48), "ok": (52,199,89), "on_ok": (6,30,12)}
d = None


RING_IN, ORBIT_IN = 40, 64

BG, INK, MUTED = T["bg"], T["text"], T["muted"]

WAIT = T["warn"]

ETH = (122, 146, 255)

ETH_DARK, ETH_LIGHT = (30, 36, 92), (218, 226, 255)

OK = T["ok"]

OK_DARK, OK_LIGHT = (0, 96, 36), (120, 255, 150)

def ease(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return 1 - (1 - t) ** 3

def smooth(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)

def span(i, a, b):
    return 0.0 if i <= a else 1.0 if i >= b else (i - a) / (b - a)

def mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))

def col(rgb):
    return L.color(*rgb)

def center(s, y, font, fg, bg=BG):
    d.text(s, (L.W - F.width(s, font)) // 2, y, font, fg, bg)

def thick(x0, y0, x1, y1, rgb, t=3):
    c = col(rgb)
    for k in range(-(t // 2), t - t // 2):
        d.line(x0 + k, y0, x1 + k, y1, c)
        d.line(x0, y0 + k, x1, y1 + k, c)

def node(x, y, r, rgb):
    d.ellipse(x, y, r, r, col(rgb), True)

SX, SY, SR = L.W // 2, 116, 92

STAR = [(int(SX + SR * math.cos(math.radians(-90 + 72 * k))),
         int(SY + SR * math.sin(math.radians(-90 + 72 * k)))) for k in range(5)]

STROKE = (0, 2, 4, 1, 3, 0)

DRAW0, DRAW1 = 2, 18

SIGN_AT = {0: 22, 3: 31, 2: 40}

TOP, LEFT, RIGHT = STAR[0], STAR[3], STAR[2]

S0 = (RIGHT[0] - LEFT[0]) / 2 / (LEFT[1] - TOP[1])

S1, GAP, FOOT = 0.37, 0.12, 0.97

EL = math.radians(30)

K1, OY1 = 82, 86

BACK_K, BACK_OY, BACK_DIM = 96, 104, 0.66

LIGHT = (-0.55, -0.55, 0.63)

_l = math.sqrt(sum(v * v for v in LIGHT))

LIGHT = tuple(v / _l for v in LIGHT)

_n = math.sqrt(S0 * S0 + 1)

FACE_GREEN = mix(OK_DARK, OK_LIGHT, 0.12 + 0.88 * max(0.0, (-S0 * LIGHT[1] + LIGHT[2]) / _n))

def box(s, y):
    """The four corners of a square of half-side s at height y, front edge first (z toward us)."""
    return [(-s, y, s), (s, y, s), (s, y, -s), (-s, y, -s)]

def draw_diamond(u, alpha=1.0, yaw=0.0, el=0.0, chev=None, chev_alpha=0.0, pts=None, green=0.0,
                 back=0.0):
    """The diamond at zoom u (0 = the star's triangle filling the screen, 1 = the logo).
    chev is how far below its place the inverted pyramid is (None: not there yet). green: how
    much of the top pyramid's front face (the quorum's triangle) is still green. back: how far
    it has gone into the background (1: centred, bigger and dim, behind the name)."""
    s = S0 + (S1 - S0) * u
    k0 = LEFT[1] - TOP[1]
    k = k0 + (K1 - k0) * u + (BACK_K - K1) * back                       # pixels per unit
    ox, oy = L.W // 2, LEFT[1] + (OY1 - LEFT[1]) * u + (BACK_OY - OY1) * back  # where y = 0 lands
    cy, sy = math.cos(yaw), math.sin(yaw)
    ce, se = math.cos(el), math.sin(el)

    def view(p):
        x, y, z = p
        x, z = x * cy + z * sy, -x * sy + z * cy                        # turn about the axis
        return x, y * ce + z * se, -y * se + z * ce                     # from a little above

    tris = []
    top, base = (0.0, -1.0, 0.0), box(s, 0.0)
    for j in range(4):
        tris.append(((top, base[j], base[(j + 1) % 4]), (0.0, -0.3, 0.0), alpha, 1, j))
    if chev is not None:
        rim, foot = box(s, GAP + chev), (0.0, FOOT + chev, 0.0)
        for j in range(4):
            tris.append(((rim[j], rim[(j + 1) % 4], foot), (0.0, GAP + 0.4 + chev, 0.0), chev_alpha, 0, j))
    polys = []
    for (tri, inside, a, layer, j) in tris:
        v = [view(p) for p in tri]
        ux, uy, uz = v[1][0] - v[0][0], v[1][1] - v[0][1], v[1][2] - v[0][2]
        wx, wy, wz = v[2][0] - v[0][0], v[2][1] - v[0][1], v[2][2] - v[0][2]
        nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        c = view(inside)
        if nx * (v[0][0] - c[0]) + ny * (v[0][1] - c[1]) + nz * (v[0][2] - c[2]) < 0:
            nx, ny, nz = -nx, -ny, -nz              # point it out of the solid
        m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        if nz / m < 0.02:
            continue                                # facing away, or edge-on
        lit = max(0.0, (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / m)
        rgb = mix(ETH_DARK, ETH_LIGHT, 0.12 + 0.88 * lit)
        dark = ETH_DARK
        if green > 0 and layer == 1 and j == 0:     # the quorum's face
            rgb = mix(rgb, mix(OK_DARK, OK_LIGHT, 0.12 + 0.88 * lit), green)
            dark = mix(ETH_DARK, OK_DARK, green)
        if a < 1:                                   # fade in through its own dark shade
            rgb = mix(mix(BG, dark, min(1.0, 2 * a)), rgb, a)
        if back > 0:
            rgb = mix(rgb, BG, BACK_DIM * back)
        polys.append((layer * 10 + (v[0][2] + v[1][2] + v[2][2]) / 3, v, rgb))
    polys.sort(key=lambda p: p[0])                  # the bottom pyramid first, then far to near
    for (_, v, rgb) in polys:
        xy = array("h", [0] * 6)
        for j in range(3):
            xy[2 * j] = int(ox + v[j][0] * k)
            xy[2 * j + 1] = int(oy + v[j][1] * k)
        d.poly(0, 0, xy, col(rgb), True)
    if pts:                                         # the signers, riding the corners they became
        r, rgb = pts
        for p in (top, base[0], base[1]):
            x, y, _ = view(p)
            node(int(ox + x * k), int(oy + y * k), r, rgb)

SPIN0, SPIN1, SLOW0, SLOW1 = 58, 74, 124, 146

TURNS = 2

SPEED = (45 + 90 * TURNS) / ((SPIN1 - SPIN0) / 2 + (SLOW0 - SPIN1) + (SLOW1 - SLOW0) / 2)

RING_INK = 0.28

def spin_at(i, frames, turn):
    """Degrees still to go: turn at the start, 0 at the end, slowing all the way."""
    return turn * (1 - ease(i / frames))

def waiting(k, m):
    """An owner's amber at frame m of the star's timeline, breathing."""
    return mix(WAIT, (255, 226, 150), 0.5 + 0.5 * math.sin(m * 0.45 + k))

def on_circle(k, deg, r=SR):
    a = math.radians(-90 + 72 * k + deg)
    return r * math.cos(a), r * math.sin(a)

def rnd(a):
    x = (a * 73856093) ^ 0x5bd1e995
    x = (x ^ (x >> 13)) * 1274126177
    return (x ^ (x >> 16)) & 0xffff

SPACE = [(rnd(3 * k) % L.W, rnd(3 * k + 1) % L.H, 40 + rnd(3 * k + 2) % 90) for k in range(28)]

def orbit_xy(k, spin, tilt, yaw, scale):
    """An owner on the circle, the circle tipped back by tilt and turned by yaw: screen x, y, depth."""
    x, y = on_circle(k, spin)
    y, z = y * math.cos(tilt), y * math.sin(tilt)       # tip the top away from us
    x, z = x * math.cos(yaw) + z * math.sin(yaw), -x * math.sin(yaw) + z * math.cos(yaw)
    p = 320 / (320 - z * scale)                         # nearer is bigger
    return SX + x * scale * p, SY + y * scale * p, z, p

LAND = ORBIT_IN

AT_TOP, AT_LEFT, AT_RIGHT = LAND + 12, LAND + 36, LAND + 60

POUR0, POUR1 = AT_RIGHT + 14, AT_RIGHT + 36

TURN = AT_RIGHT + 50

SIGNERS = ((0, AT_TOP), (3, AT_LEFT), (2, AT_RIGHT))

EDGES = ((TOP, LEFT, AT_LEFT), (TOP, RIGHT, AT_RIGHT), (LEFT, RIGHT, AT_RIGHT + 6))

def m_at(i):
    """The star's frame for the diamond, from the turn on."""
    return 58 + (i - TURN)

BACK0, BACK1 = 100, 128

TAG0, TAG_EACH = 134, 38

TAGS = ("Your keys, your quorum", "Nothing signs unseen", "Hardware approvals for Safe",
        "Every hash checked here")

V_BACK = 1.2

def yaw_orbit(m):
    """Like yaw_at, but it never stops: it eases down to V_BACK and keeps going."""
    if m <= SPIN0:
        return 0.0
    a = min(m, SPIN1) - SPIN0
    deg = SPEED * a * a / (2 * (SPIN1 - SPIN0))
    if m > SPIN1:
        deg += SPEED * (min(m, BACK0) - SPIN1)
    if m > BACK0:
        b, n = min(m, BACK1) - BACK0, BACK1 - BACK0
        deg += SPEED * b - (SPEED - V_BACK) * b * b / (2 * n)
    if m > BACK1:
        deg += V_BACK * (m - BACK1)
    return math.radians(deg)

READY = TURN + (BACK0 - 58)

def draw_orbit_in(i):
    d.fill(col(BG))
    face = smooth(span(i, 20, LAND - 4))                # swinging round to face us
    tilt, yaw = math.radians(74) * (1 - face), math.radians(-28) * (1 - face)
    scale = 0.45 + 0.55 * ease(span(i, 10, LAND - 6))
    fade = 1 - span(i, LAND - 16, LAND)
    for (x, y, b) in SPACE:                             # a few stars, drifting, gone by the landing
        c = mix(BG, (b, b, b + 20), fade * ease(span(i, 0, 8)))
        d.pixel(int(x - i * 0.4) % L.W, y, col(c))
    spin = spin_at(i, LAND, -864)                       # 2.4 turns, landing top-up
    owners = []
    for k in range(5):
        born = ease(span(i, 2 * k, 2 * k + 7))
        if born > 0:
            owners.append((orbit_xy(k, spin, tilt, yaw, scale), k, born))
    owners.sort(key=lambda o: o[0][2])                  # far ones first
    for ((x, y, z, p), k, born) in owners:
        near = 0.55 + 0.45 * min(1.0, max(0.0, (z / SR + 1) / 2 + face))
        node(int(x), int(y), max(1, int(9 * scale * p * born)), mix(BG, waiting(k, i), born * near))

def fill_up(f, glow):
    """The quorum's triangle filled with green from its base up to fraction f of its height."""
    if f <= 0:
        return
    y = LEFT[1] - (LEFT[1] - TOP[1]) * f                # the surface
    xl = LEFT[0] + (TOP[0] - LEFT[0]) * f
    xr = RIGHT[0] + (TOP[0] - RIGHT[0]) * f
    rgb = mix(FACE_GREEN, (200, 255, 215), 0.35 * glow)
    d.poly(0, 0, array("h", [LEFT[0], LEFT[1], RIGHT[0], RIGHT[1], int(xr), int(y), int(xl), int(y)]),
           col(rgb), True)
    if f < 1:                                           # the surface, brighter
        thick(int(xl), int(y), int(xr), int(y), OK_LIGHT, 2)

def draw_quorum(i):
    """Landed to the turn: three sign, their triangle closes and fills with green."""
    d.fill(col(BG))
    gone = smooth(span(i, AT_RIGHT + 8, AT_RIGHT + 28))             # the two who didn't sign
    for (a, b, at) in EDGES:
        f = smooth(span(i, at, at + 10))
        if f > 0:
            thick(a[0], a[1], int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), OK, 3)
    fill_up(smooth(span(i, POUR0, POUR1)), math.sin(math.pi * span(i, POUR1 - 8, TURN)))
    signed = dict(SIGNERS)
    for k, (x, y) in enumerate(STAR):
        at = signed.get(k)
        if at is None:
            if gone < 1:
                node(x, y, 9, mix(waiting(k, i), BG, gone))
            continue
        q = span(i, at, at + 16)
        if 0 < q < 1:                                   # a ring goes out as it signs
            rr = int(12 + 22 * ease(q))
            ring = col(mix(BG, OK, (1 - q) ** 2))
            d.ellipse(x, y, rr, rr, ring)
            d.ellipse(x, y, rr + 1, rr + 1, ring)
        c = smooth(span(i, at, at + 5))
        rgb = mix(waiting(k, i), OK, c)
        node(x, y, int(9 + 3 * math.sin(math.pi * span(i, at, at + 8))), rgb)

def quorum_mark(cx, cy, a):
    """The PicoQuorum mark, small: five owners, three signed, their triangle."""
    pts = [(int(cx + 12 * math.cos(math.radians(-90 + 72 * k))),
            int(cy + 12 * math.sin(math.radians(-90 + 72 * k)))) for k in range(5)]
    g = mix(BG, OK, a)
    d.poly(0, 0, array("h", [pts[0][0], pts[0][1], pts[2][0], pts[2][1], pts[3][0], pts[3][1]]),
           col(mix(BG, FACE_GREEN, a * 0.55)), True)
    for k in (1, 4):
        node(pts[k][0], pts[k][1], 2, mix(BG, WAIT, a * 0.8))
    for k in (0, 2, 3):
        node(pts[k][0], pts[k][1], 3, g)

def draw_orbit_out(i):
    """The turn on: the diamond, then behind the name, spinning for as long as it's up."""
    d.fill(col(BG))
    m = m_at(i)
    u = smooth(span(m, 58, 98))
    rise = smooth(span(m, 74, 98))
    nodes = 1 - span(m, 60, 80)
    back = smooth(span(m, BACK0, BACK1))
    draw_diamond(u, 1.0, yaw_orbit(m), EL * u, 0.5 * (1 - rise) if rise > 0 else None, rise,
                 (int(9 * nodes), OK) if nodes > 0.1 else None,
                 1 - span(m, 92, 100), back)               # its face goes blue round the back
    t = smooth(span(m, BACK0 + 18, BACK1 + 10))         # the name, in front, once it has dimmed
    if t > 0:
        w = F.width("PicoQuorum", "bold26") + 34
        x, y = (L.W - w) // 2, 82 + int(8 * (1 - t))
        quorum_mark(x + 13, y + 17, t)
        d.text("PicoQuorum", x + 34, y, "bold26", mix(BG, INK, t), BG)
    if m >= TAG0:                                       # a tagline, one after another
        n, f = divmod(m - TAG0, TAG_EACH)
        a = smooth(span(f, 0, 8)) * (1 - smooth(span(f, TAG_EACH - 8, TAG_EACH)))
        center(TAGS[n % len(TAGS)], 124 + int(6 * (1 - smooth(span(f, 0, 8)))), "sans14", mix(BG, MUTED, a))

class Commands:
    """Compute geometry once; send each command only to the strips its pixels touch.
    Text stays a text command rather than dozens of glyph blits replayed in every strip.
    The existing font renderer clips glyphs and handles palette lookup in the target strip.
    """

    def __init__(self, screen):
        self.screen = screen
        self.band_h = getattr(screen, "band_h", L.H)
        self.bands = [[] for _ in range((L.H + self.band_h - 1) // self.band_h)]

    def _add(self, fn, args, top, bottom):
        first = max(0, top // self.band_h)
        last = min(len(self.bands) - 1, bottom // self.band_h)
        entry = (fn, args)
        for band in range(first, last + 1):
            self.bands[band].append(entry)

    def fill(self, c):
        self._add(self.screen.fill, (c,), 0, L.H - 1)

    def pixel(self, x, y, c):
        self._add(self.screen.pixel, (x, y, c), y, y)

    def line(self, x0, y0, x1, y1, c):
        self._add(self.screen.line, (x0, y0, x1, y1, c), min(y0, y1), max(y0, y1))

    def ellipse(self, x, y, xr, yr, c, fill=False):
        self._add(self.screen.ellipse, (x, y, xr, yr, c, fill), y - yr, y + yr)

    def poly(self, x, y, coords, c, fill=False):
        top = bottom = coords[1]
        for i in range(3, len(coords), 2):
            top = min(top, coords[i])
            bottom = max(bottom, coords[i])
        self._add(self.screen.poly, (x, y, coords, c, fill), y + top, y + bottom)

    def text(self, s, x, y, font, fg, bg):
        # Match fonts.text's conservative bounds, including glyph overhangs.
        self._add(F.text, (self.screen, s, x, y, font, fg, bg), y - 4, y + F.height(font) + 3)

    def replay(self, screen):
        for fn, args in self.bands[screen.y0 // self.band_h]:
            fn(*args)
        screen.show()


def render(screen, i, status, status_color):
    global d
    d = Commands(screen)
    try:
        if i < LAND:
            draw_orbit_in(i)
        elif i < TURN:
            draw_quorum(i)
        else:
            draw_orbit_out(i)
        # Only real boot status, supplied by splash; never the demo's invented Safe or checks.
        while F.width(status, "sans14") > L.W - 20:
            status = status[:-1]
        center(status, L.H - 26, "sans14", status_color)
        screen.frames(d.replay, screen)
    finally:
        d = None
