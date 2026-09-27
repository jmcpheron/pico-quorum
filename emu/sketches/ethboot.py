# Boot screen, take 2: a 3-of-5 quorum that becomes the Ethereum diamond. A = next option, X stops.
#   tools/emu run ethboot                       watch it in the emulator
#   tools/bootgifs --sketch ethboot             capture each option as a GIF for docs/quorum-ui/v2/
#
#   1. Five owners arrive, all amber: ready to sign. Three ways in:
#        ring    they spin round a circle, trailing light, and slow to a stop
#        orbit   they orbit in space, tilted and far, and swing round to face us: just the dots.
#                The pick. Signing is green; green pours into the triangle, which holds a beat
#                and then turns: it's one face of the diamond, and the faces coming round are
#                Ethereum blue. A status line at the bottom names each boot step.
#        star    a star drawn in one stroke (iteration 1; it reads as a pentagram)
#   2. Three sign (the top, then the two bottom ones) and turn Ethereum blue. Their lines close
#      into the tall triangle those three make.
#   3. That triangle is one face of a pyramid seen head-on. The camera pulls back and up, the
#      pyramid turns, and an inverted pyramid rises underneath. Together they are the Ethereum
#      diamond, spinning on its axis.
#   4. It slows into the logo's own pose, a corner toward us, and the name comes up.
#
# Every frame is a function of its number (render("ring", i)), like emu/sketches/bootfx.py, so
# the GIFs are exact. The diamond is ten 3D points turned and projected each frame, then drawn as
# flat filled triangles (framebuf.poly, in C), back faces dropped and the rest painted far to near:
# at most four triangles a frame.
import math
from array import array
from machine import Timer
import lcd as L
import fonts as F
import quorum_ui as U

d = L.LCD()
keys = L.Keys()
OPTIONS = ("orbit", "ring", "star")     # orbit is the pick (iteration 2); the others for the record
RING_IN, ORBIT_IN = 40, 64          # frames the ring and orbit take to land; the star's is 20
FRAMES = {"ring": 170, "orbit": 248, "star": 150}     # literal: tools/bootgifs reads them
T = U.THEMES["dark"]
BG, INK, MUTED = T["bg"], T["text"], T["muted"]
WAIT = T["warn"]                    # amber: an owner who can sign and hasn't yet
ETH = (122, 146, 255)               # signed; Ethereum's periwinkle, lifted for a dark screen
ETH_DARK, ETH_LIGHT = (30, 36, 92), (218, 226, 255)      # the diamond's shading runs between
OK = T["ok"]                        # signed, in the orbit: the green of every other "signed"
OK_DARK, OK_LIGHT = (0, 96, 36), (120, 255, 150)         # the green triangle's shading
# What the drawing below uses; each option's draw function sets it for its frames.
#   sign     the colour an owner turns when it signs, and the quorum's lines
#   green    green pours into the triangle; it stays the diamond's green face as it turns away
#   status   the bottom line names boot steps (and the counter and "3 of 5 · ready" go)
#   clock    the frame the waiting owners breathe by, when the timeline is paused around them
STYLE = {"sign": ETH, "green": False, "status": False, "clock": None}
timer = None
n = 0


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
    F.text(d, s, (240 - F.width(s, font)) // 2, y, font, fg, bg)


def thick(x0, y0, x1, y1, rgb, t=3):
    c = col(rgb)
    for k in range(-(t // 2), t - t // 2):
        d.line(x0 + k, y0, x1 + k, y1, c)
        d.line(x0, y0 + k, x1, y1 + k, c)


def node(x, y, r, rgb):
    d.ellipse(x, y, r, r, col(rgb), True)


# ----------------------------------------------------------------------------- the star
# Five owners evenly round a circle, numbered clockwise from the top (the points of a star, which
# iteration 1 drew). The quorum is the top and the two at the bottom: a tall "golden" triangle,
# 36 degrees at the apex.
SX, SY, SR = 120, 116, 92
STAR = [(int(SX + SR * math.cos(math.radians(-90 + 72 * k))),
         int(SY + SR * math.sin(math.radians(-90 + 72 * k)))) for k in range(5)]
STROKE = (0, 2, 4, 1, 3, 0)         # the star in one stroke
DRAW0, DRAW1 = 2, 18                # the stroke's frames; each owner appears as the pen reaches them
SIGN_AT = {0: 22, 3: 31, 2: 40}     # who signs, and on which frame: top, left leg, right leg
TOP, LEFT, RIGHT = STAR[0], STAR[3], STAR[2]


def born_at(k):
    return DRAW0 + (DRAW1 - DRAW0) * STROKE.index(k) / 5


def draw_star(i, lines=True, hoop_too=True):
    gone = smooth(span(i, 46, 58))              # the two who didn't sign fade away
    line = mix(BG, WAIT, 0.32 * (1 - gone))
    if not lines and hoop_too:                  # the ring they spun in, in place of the star
        if gone < 1:
            hoop(SX, SY, SR, mix(BG, WAIT, RING_INK * (1 - gone)))
    t = span(i, DRAW0, DRAW1) * 5 if lines else 0   # the stroke, one edge after another
    for e in range(5):
        f = t - e
        if f <= 0 or gone >= 1:
            break
        (x0, y0), (x1, y1) = STAR[STROKE[e]], STAR[STROKE[e + 1]]
        f = min(1.0, f)
        thick(x0, y0, int(x0 + (x1 - x0) * f), int(y0 + (y1 - y0) * f), line, 2)
    # the quorum's edges, drawn as each leg signs, and the base once all three have
    for (a, b, at) in ((TOP, LEFT, SIGN_AT[3]), (TOP, RIGHT, SIGN_AT[2]), (LEFT, RIGHT, SIGN_AT[2] + 2)):
        f = ease(span(i, at, at + 6))
        if f > 0:
            thick(a[0], a[1], int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), STYLE["sign"], 3)
    if STYLE["green"]:                          # green pours in from the tip, then a flash
        pour(ease(span(i, 47, 54)), 1 - span(i, 54, 58) if i >= 54 else 0.0)
    else:
        fill = smooth(span(i, 48, 57))          # the triangle fills in: the pyramid's front face
        if fill > 0:
            draw_diamond(0.0, fill)
    for k, (x, y) in enumerate(STAR):
        born = ease(span(i, born_at(k), born_at(k) + 5))
        if born <= 0:
            continue
        at = SIGN_AT.get(k)
        if at is None:
            if gone < 1:
                node(x, y, int(9 * born), mix(BG, WAIT, 1 - gone))
            continue
        q = span(i, at, at + 9)
        if 0 < q < 1:                           # a ring goes out as it signs
            rr = int(12 + 18 * q)
            ring = col(mix(BG, STYLE["sign"], 1 - q))
            d.ellipse(x, y, rr, rr, ring)
            d.ellipse(x, y, rr + 1, rr + 1, ring)
        if i < at:                              # ready and waiting: a slow breath
            clock = i if STYLE["clock"] is None else STYLE["clock"]
            rgb = mix(WAIT, (255, 226, 150), 0.5 + 0.5 * math.sin(clock * 0.45 + k))
        else:
            rgb = mix(WAIT, STYLE["sign"], span(i, at, at + 3))
        node(x, y, int((9 + (3 if at <= i < at + 3 else 0)) * born), rgb)


def pour(f, flash):
    """The quorum's triangle filled with green down to fraction f of its height."""
    if f <= 0:
        return
    y = TOP[1] + (LEFT[1] - TOP[1]) * f
    xl, xr = TOP[0] + (LEFT[0] - TOP[0]) * f, TOP[0] + (RIGHT[0] - TOP[0]) * f
    rgb = mix(FACE_GREEN, (255, 255, 255), 0.45 * flash)
    d.poly(0, 0, array("h", [TOP[0], TOP[1], int(xr), int(y), int(xl), int(y)]), col(rgb), True)
    if f < 1:                                   # the surface, brighter
        thick(int(xl), int(y), int(xr), int(y), OK_LIGHT, 2)


def counter(i):
    if STYLE["status"]:
        return
    signed = sum(1 for at in SIGN_AT.values() if i >= at)
    out = 1 - span(i, 56, 62)
    if out <= 0:
        return
    if signed == 0:
        s, rgb = "3 of 5 to sign", mix(BG, MUTED, span(i, 8, 16))
    elif signed < 3:
        s, rgb = "%d of 3 signed" % signed, mix(BG, INK, out)
    else:
        s, rgb = "3 of 5 · quorum", mix(BG, ETH, out)
    center(s, 214, "sans14", rgb)


# ----------------------------------------------------------------------------- the diamond
# Model units: the top pyramid's apex at y = -1 and its square base at y = 0, half-side s (y points
# down, as on the screen). Below, after a gap, the inverted pyramid: the same square at y = GAP and
# its point at y = FOOT. Its top is open and never drawn, so from above the gap between the two is
# the same square outline shifted down: an even band at every angle, and at a corner-on pose the
# logo's V. s starts at the star triangle's proportions, so the face seen head-on at the start is
# exactly that triangle, and widens a little to the logo's.
S0 = (RIGHT[0] - LEFT[0]) / 2 / (LEFT[1] - TOP[1])      # half base / height of the star triangle
S1, GAP, FOOT = 0.37, 0.12, 0.97
EL = math.radians(30)               # how far above the diamond the camera ends up
K1, OY1 = 82, 86                    # the logo: pixels per unit, and where y = 0 lands
LIGHT = (-0.55, -0.55, 0.63)        # from the upper left, toward the viewer
_l = math.sqrt(sum(v * v for v in LIGHT))
LIGHT = tuple(v / _l for v in LIGHT)
# The front face's green, head-on: its normal is (0, -s, 1), so this is what draw_diamond gives it
_n = math.sqrt(S0 * S0 + 1)
FACE_GREEN = mix(OK_DARK, OK_LIGHT, 0.12 + 0.88 * max(0.0, (-S0 * LIGHT[1] + LIGHT[2]) / _n))


def box(s, y):
    """The four corners of a square of half-side s at height y, front edge first (z toward us)."""
    return [(-s, y, s), (s, y, s), (s, y, -s), (-s, y, -s)]


def draw_diamond(u, alpha=1.0, yaw=0.0, el=0.0, chev=None, chev_alpha=0.0, pts=None, green=0.0):
    """The diamond at zoom u (0 = the star's triangle filling the screen, 1 = the logo).
    chev is how far below its place the inverted pyramid is (None: not there yet). green: how
    much of the top pyramid's front face (the quorum's triangle) is still green."""
    s = S0 + (S1 - S0) * u
    k0 = LEFT[1] - TOP[1]
    k = k0 + (K1 - k0) * u                                              # pixels per unit
    ox, oy = 120, LEFT[1] + (OY1 - LEFT[1]) * u                         # where y = 0 lands
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


# ----------------------------------------------------------------------------- the turn
# The spin speeds up as the camera pulls back, runs, and slows to a stop at 45 + 90n degrees: a
# corner toward us, the logo's own pose. A square pyramid looks the same every 90 degrees, so on
# the device it can spin for as long as the boot takes and still land there.
SPIN0, SPIN1, SLOW0, SLOW1 = 58, 74, 124, 146
TURNS = 2
SPEED = (45 + 90 * TURNS) / ((SPIN1 - SPIN0) / 2 + (SLOW0 - SPIN1) + (SLOW1 - SLOW0) / 2)


def yaw_at(i):
    """Degrees a frame rise from 0 to SPEED, hold, and fall back to 0; this is their sum."""
    if i <= SPIN0:
        return 0.0
    a = min(i, SPIN1) - SPIN0
    deg = SPEED * a * a / (2 * (SPIN1 - SPIN0))
    if i > SPIN1:
        deg += SPEED * (min(i, SLOW0) - SPIN1)
    if i > SLOW0:
        b = min(i, SLOW1) - SLOW0
        deg += SPEED * (b - b * b / (2 * (SLOW1 - SLOW0)))
    return math.radians(deg)


def draw_star_to_eth(i, lines=True, hoop_too=True):
    d.fill(col(BG))
    counter(i)
    if i < 58:
        draw_star(i, lines, hoop_too)
        return
    u = smooth(span(i, 58, 98))
    rise = smooth(span(i, 74, 98))
    nodes = 1 - span(i, 60, 80)
    green = 1 - span(i, 92, 100) if STYLE["green"] else 0.0   # its face goes blue once it's round the back
    draw_diamond(u, 1.0, yaw_at(i), EL * u, 0.5 * (1 - rise) if rise > 0 else None, rise,
                 (int(9 * nodes), STYLE["sign"]) if nodes > 0.1 else None, green)
    t = ease(span(i, 100, 116))                     # the name
    if t > 0:
        yy = int(172 + 12 * (1 - t))
        center("PicoQuorum", yy, "bold26", mix(BG, INK, t))
        if not STYLE["status"]:
            center("3 of 5 · ready", yy + 34, "sans14", mix(BG, MUTED, t))


# ----------------------------------------------------------------------------- the ways in
# Both end with the owners exactly where the star had them, at frame 20 of the star's timeline
# (drawn, all waiting), and it carries on from there.
RING_INK = 0.28                     # the circle, as a fraction of amber


def hoop(cx, cy, r, rgb):
    c = col(rgb)
    d.ellipse(cx, cy, r, r, c)
    d.ellipse(cx, cy, r - 1, r - 1, c)


def spin_at(i, frames, turn):
    """Degrees still to go: turn at the start, 0 at the end, slowing all the way."""
    return turn * (1 - ease(i / frames))


def waiting(k, m):
    """An owner's amber at frame m of the star's timeline, breathing."""
    return mix(WAIT, (255, 226, 150), 0.5 + 0.5 * math.sin(m * 0.45 + k))


def lead_in(i, frames):
    """"3 of 5 to sign" fading in over the last half-second."""
    t = span(i, frames - 12, frames)
    if t > 0:
        center("3 of 5 to sign", 214, "sans14", mix(BG, MUTED, t))


def on_circle(k, deg, r=SR):
    a = math.radians(-90 + 72 * k + deg)
    return r * math.cos(a), r * math.sin(a)


def draw_ring(i):
    if i >= RING_IN:
        return draw_star_to_eth(i - RING_IN + 20, lines=False)
    d.fill(col(BG))
    hoop(SX, SY, SR, mix(BG, WAIT, RING_INK * ease(span(i, 0, 12))))
    spin = spin_at(i, RING_IN, -432)                    # 1.2 turns, clockwise, landing top-up
    tail = 80 * (1 - i / RING_IN) ** 1.5                # degrees of comet tail, shrinking as it slows
    for k in range(5):
        born = ease(span(i, 2 * k, 2 * k + 7))
        if born <= 0:
            continue
        if tail > 2:                                    # the tail, fading along the ring behind it
            x0, y0 = on_circle(k, spin)
            for j in range(1, 9):
                x1, y1 = on_circle(k, spin - tail * j / 8)
                thick(int(SX + x0), int(SY + y0), int(SX + x1), int(SY + y1),
                      mix(BG, WAIT, 0.9 * born * (1 - j / 9)), 3)
                x0, y0 = x1, y1
        x, y = on_circle(k, spin)
        node(int(SX + x), int(SY + y), int(9 * born), mix(BG, waiting(k, i - RING_IN + 20), born))
    lead_in(i, RING_IN)


def rnd(a):
    x = (a * 73856093) ^ 0x5bd1e995
    x = (x ^ (x >> 13)) * 1274126177
    return (x ^ (x >> 16)) & 0xffff


SPACE = [(rnd(3 * k) % 240, rnd(3 * k + 1) % 240, 40 + rnd(3 * k + 2) % 90) for k in range(28)]


def orbit_xy(k, spin, tilt, yaw, scale):
    """An owner on the circle, the circle tipped back by tilt and turned by yaw: screen x, y, depth."""
    x, y = on_circle(k, spin)
    y, z = y * math.cos(tilt), y * math.sin(tilt)       # tip the top away from us
    x, z = x * math.cos(yaw) + z * math.sin(yaw), -x * math.sin(yaw) + z * math.cos(yaw)
    p = 320 / (320 - z * scale)                         # nearer is bigger
    return SX + x * scale * p, SY + y * scale * p, z, p


# The orbit's timeline. The star's (which the rest is drawn in) pauses before each signature, so
# each boot step gets its moment: STALLS are (star frame, frames to hold there).
STALLS = ((20, 10), (30, 15), (39, 15), (58, 14))   # the last: the green triangle's beat


def star_frame(i):
    """The star's frame for the orbit's frame i (from the landing on)."""
    m = 20 + (i - ORBIT_IN)
    for (v, n) in STALLS:
        if m > v:
            m = max(v, m - n)
    return m


def orbit_frame(m):
    """The first orbit frame showing the star's frame m."""
    i = ORBIT_IN
    while star_frame(i) < m:
        i += 1
    return i


# The bottom line: (from frame, text, done). On the device each is a real step, and a signature
# lands when its step does (see docs/quorum-ui/v2/README.md, "On the device").
WIFI, CHIP, SAFE = (orbit_frame(SIGN_AT[k]) for k in (0, 3, 2))
NAME = orbit_frame(100)
STATUS = ((0, "Starting up", False), (22, "Joining WiFi", False),
          (WIFI, "WiFi connected", True), (WIFI + 12, "Checking the chip", False),
          (CHIP, "Chip verified", True), (CHIP + 12, "Finding the Safe", False),
          (SAFE, "Family Safe \u00b7 3 of 5", True), (orbit_frame(62), "Loading the queue", False),
          (NAME, "Ready", True))
SLIDE = 6                           # frames a line takes to slide in (and the old one out)


def status_line(i):
    now = 0
    while now + 1 < len(STATUS) and STATUS[now + 1][0] <= i:
        now += 1
    t = ease(span(i, STATUS[now][0], STATUS[now][0] + SLIDE)) if now or i >= SLIDE else ease(span(i, 0, 10))
    if now and t < 0.6:                             # the last one, leaving upward, gone early
        status_row(i, STATUS[now - 1], -int(18 * t), (1 - t / 0.6) ** 2)
    status_row(i, STATUS[now], int(18 * (1 - t)), t * t)


def status_row(i, st, dy, a):
    if a <= 0.02:
        return
    _, text, done = st
    font = "sans14"
    w = F.width(text, font) + 22
    x, y = (240 - w) // 2, 214 + dy
    if done:                                        # a green check
        d.ellipse(x + 7, y + 9, 7, 7, col(mix(BG, OK, a)), True)
        thick(x + 4, y + 9, x + 6, y + 12, T["on_ok"], 2)
        thick(x + 6, y + 12, x + 10, y + 6, T["on_ok"], 2)
    else:
        for k in range(8):                          # a small spinner
            ang = math.radians(k * 45)
            on = (i // 2) % 8 == k
            d.pixel(int(x + 7 + 5 * math.cos(ang)), int(y + 9 + 5 * math.sin(ang)),
                    col(mix(BG, INK if on else MUTED, a)))
            if on:
                d.ellipse(int(x + 7 + 5 * math.cos(ang)), int(y + 9 + 5 * math.sin(ang)), 1, 1,
                          col(mix(BG, INK, a)), True)
    F.text(d, text + ("" if done else "\u2026"), x + 22, y, font, mix(BG, INK if done else MUTED, a), BG)


def draw_orbit(i):
    STYLE.update(sign=OK, green=True, status=True, clock=i)
    if i >= ORBIT_IN:
        draw_star_to_eth(star_frame(i), lines=False, hoop_too=False)
        status_line(i)
        return
    d.fill(col(BG))
    face = smooth(span(i, 20, ORBIT_IN - 4))            # swinging round to face us
    tilt, yaw = math.radians(74) * (1 - face), math.radians(-28) * (1 - face)
    scale = 0.45 + 0.55 * ease(span(i, 10, ORBIT_IN - 6))
    fade = 1 - span(i, ORBIT_IN - 16, ORBIT_IN)
    for (x, y, b) in SPACE:                             # a few stars, drifting, gone by the landing
        c = mix(BG, (b, b, b + 20), fade * ease(span(i, 0, 8)))
        d.pixel(int(x - i * 0.4) % 240, y, col(c))
    spin = spin_at(i, ORBIT_IN, -864)                   # 2.4 turns, landing top-up
    owners = []
    for k in range(5):
        born = ease(span(i, 2 * k, 2 * k + 7))
        if born > 0:
            owners.append((orbit_xy(k, spin, tilt, yaw, scale), k, born))
    owners.sort(key=lambda o: o[0][2])                  # far ones first
    for ((x, y, z, p), k, born) in owners:
        near = 0.55 + 0.45 * min(1.0, max(0.0, (z / SR + 1) / 2 + face))
        node(int(x), int(y), max(1, int(9 * scale * p * born)), mix(BG, waiting(k, i), born * near))
    status_line(i)


def draw_ring_(i):
    STYLE.update(sign=ETH, green=False, status=False, clock=None)
    draw_ring(i)


def draw_star_(i):
    STYLE.update(sign=ETH, green=False, status=False, clock=None)
    draw_star_to_eth(i)


DRAW = {"ring": draw_ring_, "orbit": draw_orbit, "star": draw_star_}


def render(name, i):
    DRAW[name](i)
    d.show()


# ----------------------------------------------------------------------------- live
opt = 0


def tick(_):
    global n, opt
    for k in keys.pressed():
        if k == "A":
            opt, n = (opt + 1) % len(OPTIONS), 0
        elif k == "X":
            stop()
            return
    name = OPTIONS[opt]
    render(name, min(n, FRAMES[name] - 1))
    n += 1
    if n > FRAMES[name] + 30:            # hold the last frame a moment, then play it again
        n = 0


def start():
    global timer
    timer = Timer(period=50, mode=Timer.PERIODIC, callback=tick)


def stop():
    if timer:
        timer.deinit()


start()
