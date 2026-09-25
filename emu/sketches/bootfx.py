# Boot screen options for PicoQuorum. A cycles through them, X stops.
#   tools/emu run bootfx            watch them in the emulator
#   tools/bootgifs                  capture each one as a GIF for docs/quorum-ui/boot/
# Every frame is a function of its number (render(option, i)), so the GIFs are exact. start()
# plays them on a 50 ms timer, the rate the firmware's own loop runs at. On the board a busy
# frame may take longer; the animations only move a few things per frame to leave room.
#
#   quorum     three owners swirl in and link up; two vote, the check pops: 2 of 3, ready
#   plugin     the dual-plug key slides into the console's jack; its light comes on
#   hashrain   falling hex that settles into the name
#   checklist  the practical one: each boot step ticks off (screen, WiFi, chip, the Safe)
import math
from machine import Timer
import lcd as L
import fonts as F
import quorum_ui as U

d = L.LCD()
keys = L.Keys()
OPTIONS = ("quorum", "plugin", "hashrain", "checklist")
FRAMES = {"quorum": 66, "plugin": 60, "hashrain": 66, "checklist": 76}
T = U.THEMES["dark"]
BG, INK, MUTED, FAINT = T["bg"], T["text"], T["muted"], T["faint"]
OK, STAKE, RAISED, SURFACE = T["ok"], T["stake"], T["raised"], T["surface"]
KEY = "9fad2e82"            # the fingerprint shown in the demos
timer = None
opt = 0
n = 0


def ease(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return 1 - (1 - t) ** 3


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


def title(i, a, b, y, sub=None):
    """The name rising and fading in between frames a and b."""
    t = ease(span(i, a, b))
    if t <= 0:
        return
    yy = int(y + 14 * (1 - t))
    center("PicoQuorum", yy, "bold26", mix(BG, INK, t))
    if sub:
        center(sub, yy + 34, "sans14", mix(BG, MUTED, t))


# ----------------------------------------------------------------------------- the mark
# Three owners in a triangle, two of them filled: a quorum of 2 of 3. The logo in every option.
CX, CY, R = 120, 92, 54
ANG = (-90, 30, 150)


def node_xy(k, r=R, cx=CX, cy=CY, turn=0.0):
    a = math.radians(ANG[k]) + turn
    return int(cx + r * math.cos(a)), int(cy + r * math.sin(a))


def mark(cx, cy, r, node, filled=2):
    """The PicoQuorum mark at any size: r to the nodes, node radius."""
    pts = [node_xy(k, r, cx, cy) for k in range(3)]
    for a, b in ((0, 1), (1, 2), (2, 0)):
        thick(pts[a][0], pts[a][1], pts[b][0], pts[b][1], mix(BG, STAKE, 0.55), max(1, node // 4))
    for k, (x, y) in enumerate(pts):
        d.ellipse(x, y, node, node, col(OK if k < filled else RAISED), True)
        if k >= filled:
            d.ellipse(x, y, node - 2, node - 2, col(BG), True)


def draw_quorum(i):
    d.fill(col(BG))
    swirl = [ease(span(i, 2 * k - 4, 18 + 2 * k)) for k in range(3)]
    pts = []
    for k in range(3):
        e = swirl[k]
        pts.append(node_xy(k, R + 170 * (1 - e), turn=1.6 * (1 - e)))
    for j, (a, b) in enumerate(((0, 1), (1, 2), (2, 0))):
        t = ease(span(i, 20 + 4 * j, 30 + 4 * j))
        if t > 0:
            (x0, y0), (x1, y1) = pts[a], pts[b]
            thick(x0, y0, int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t), mix(BG, STAKE, 0.55))
    for k, (x, y) in enumerate(pts):
        voted = k < 2 and i >= 34 + 6 * k
        pop = 3 if voted and i < 37 + 6 * k else 0
        d.ellipse(x, y, 13 + pop, 13 + pop, col(OK if voted else RAISED), True)
        if not voted:
            d.ellipse(x, y, 10, 10, col(BG), True)
    if i >= 44:
        s = ease(span(i, 44, 50))
        r = int(15 * s) + (3 if 47 <= i <= 49 else 0)
        if r > 4:
            U.mark(d, True, CX, CY, r)
    title(i, 46, 60, 168, "2 of 3 · ready")


# ----------------------------------------------------------------------------- plug in
def draw_key(x, y, led):
    """The key, side view: a handle and its two plugs, the 1/4 inch above and the 3.5 mm below."""
    metal, tip, ring = col((200, 205, 214)), col((232, 236, 242)), col((56, 60, 68))
    d.fill_rect(x - 70, y - 8, 72, 16, metal)                           # 1/4" shaft
    d.fill_rect(x - 70, y - 8, 12, 16, tip)
    for bx in (x - 56, x - 36):
        d.fill_rect(bx, y - 8, 3, 16, ring)                              # insulating rings
    d.fill_rect(x - 50, y + 40, 52, 10, metal)                          # 3.5 mm shaft
    d.fill_rect(x - 50, y + 40, 8, 10, tip)
    d.fill_rect(x - 38, y + 40, 2, 10, ring)
    U.rrect(d, x, y - 30, 96, 100, 14, (52, 60, 74))                    # the handle
    U.rrect(d, x + 2, y - 28, 92, 96, 13, SURFACE)
    U.rrect(d, x + 10, y - 20, 76, 22, 6, RAISED)                       # label band
    F.text(d, KEY, x + 16, y - 19, "mono13", INK, RAISED)
    F.text(d, "QUORUM KEY", x + 12, y + 8, "sans12", MUTED, SURFACE)
    if led > 0.2:
        d.ellipse(x + 48, y + 44, 13, 13, col(mix(SURFACE, OK, led * 0.3)), True)
    d.ellipse(x + 48, y + 44, 7, 7, col(mix(RAISED, OK, led)), True)


def draw_plugin(i):
    d.fill(col(BG))
    e = ease(span(i, 2, 24))
    bump = (3 if i == 25 else -1 if i == 26 else 0)
    ky = 72
    kx = int(250 - (250 - 102) * e) + bump
    draw_key(kx, ky, span(i, 26, 34))
    U.rrect(d, -12, 26, 46, 124, 10, (52, 60, 74))                     # the console's jack block
    U.rrect(d, -12, 28, 44, 120, 9, RAISED)
    d.fill_rect(28, ky - 10, 4, 20, col((12, 14, 18)))                  # 1/4" socket
    d.fill_rect(28, ky + 38, 4, 14, col((12, 14, 18)))                  # 3.5 mm socket
    if i < 20:
        F.text(d, "insert key", 150, 150, "sans14", mix(BG, MUTED, 1 - span(i, 12, 20)), BG)
    if 24 <= i <= 31:
        t = span(i, 24, 31)
        for dx, dy in ((1, -1), (1, 1), (0, -1), (0, 1), (1, 0)):
            r0, r1 = int(10 + 16 * t), int(16 + 24 * t)
            thick(34 + dx * r0, ky + dy * r0, 34 + dx * r1, ky + dy * r1, mix(BG, (255, 214, 90), 1 - t), 2)
    title(i, 34, 50, 168, "key %s \u00b7 ready" % KEY)


# ----------------------------------------------------------------------------- hash rain
HEX = "0123456789abcdef"
COLS, ROWS = 20, 15


def rnd(a, b):
    """A fixed pseudo-random number for (a, b): the same rain every time."""
    x = (a * 73856093) ^ (b * 19349663) ^ 0x5bd1e995
    x = (x ^ (x >> 13)) * 1274126177
    return (x ^ (x >> 16)) & 0xffff


def draw_hashrain(i):
    d.fill(col(BG))
    fade = 1 - span(i, 44, 60)
    name = "PicoQuorum"
    nx = (240 - F.width(name, "bold26")) // 2
    for c in range(COLS):
        speed = 0.5 + (rnd(c, 1) % 100) / 100
        head = ((rnd(c, 2) % 30) + speed * i) % (ROWS + 12) - 4     # each column keeps falling
        for j in range(8):
            row = int(head) - j
            if row < 0 or row >= ROWS or fade <= 0:
                continue
            if (5 <= row <= 7 and i >= 24 or row == 8 and i >= 44) and 1 <= c <= 18:
                continue                      # the rows the name will take stay clear
            ch = HEX[rnd(c * 31 + row, i // 3 + j) % 16]
            t = (1 - j / 8) * fade
            fg = mix(BG, INK if j == 0 else STAKE, t)
            F.text(d, ch, c * 12 + 2, row * 16, "mono13", fg, BG)
    shown = int(len(name) * span(i, 26, 44))
    x = nx
    for k, ch in enumerate(name):
        w = F.width(ch, "bold26")
        if k < shown:
            F.text(d, ch, x, 88, "bold26", INK, BG)
        elif k == shown and i >= 26:
            F.text(d, HEX[rnd(k, i) % 16], x, 88, "bold26", STAKE, BG)
        x += w
    t = ease(span(i, 48, 60))
    if t > 0:
        center("0x5afe … a11e  ·  2 of 3", 132, "mono13", mix(BG, MUTED, t))


# ----------------------------------------------------------------------------- checklist
STEPS = (("Screen", "240 x 240", "ok", 6), ("WiFi", "joining HomeNet…", "192.168.4.40", 24),
         ("Chip", "probing I2C…", "ATECC608B · key " + KEY, 40),
         ("Safe", "asking the service…", "Family Safe · 2 of 3", 58))


def spinner(cx, cy, i):
    for k in range(8):
        a = math.radians(k * 45)
        on = (i // 2) % 8 == k
        d.ellipse(int(cx + 7 * math.cos(a)), int(cy + 7 * math.sin(a)), 2, 2, col(INK if on else RAISED), True)


def draw_checklist(i):
    d.fill(col(BG))
    mark(30, 30, 13, 4)
    F.text(d, "PicoQuorum", 52, 14, "bold18", INK, BG)
    F.text(d, "Safe approval console", 52, 36, "sans12", MUTED, BG)
    y = 62
    done = 0
    for k, (name, doing, result, at) in enumerate(STEPS):
        start = 0 if k == 0 else STEPS[k - 1][3]
        if i < start:
            break
        fin = i >= at
        if fin:
            done += 1
            U.mark(d, True, 24, y + 14, 9)
        else:
            spinner(24, y + 14, i)
        F.text(d, name, 44, y + 2, "bold14", INK, BG)
        F.text(d, result if fin else doing, 44, y + 20, "sans12", OK if fin else MUTED, BG)
        y += 34
    U.rrect(d, 20, 226, 200, 8, 4, RAISED)
    w = int(200 * min(1.0, (done + span(i, STEPS[min(done, 3)][3] - 16, STEPS[min(done, 3)][3])) / 4))
    if w >= 8:
        U.rrect(d, 20, 226, w, 8, 4, OK)
    if i >= 64:
        center("Ready", 203, "bold14", mix(BG, OK, ease(span(i, 64, 70))))


DRAW = {"quorum": draw_quorum, "plugin": draw_plugin, "hashrain": draw_hashrain, "checklist": draw_checklist}


def render(name, i):
    DRAW[name](i)
    d.show()


# ----------------------------------------------------------------------------- live
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
    if n > FRAMES[name] + 30:           # hold the last frame a moment, then play it again
        n = 0


def start():
    global timer
    timer = Timer(period=50, mode=Timer.PERIODIC, callback=tick)


def stop():
    if timer:
        timer.deinit()


start()
