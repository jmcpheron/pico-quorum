# gatescenes: three story skins for the Trust M signing ceremony (T1..T8), as static screens.
# Emulator: tools/emu run gatescenes   left/right = step, up/down = theme, X = facts, B quits.
# Every screen has the same layout: a header with the real step code, a scene, and a box that
# holds the story (white) above the real values (blue-grey). The story never replaces the facts.
# Themes: castle (destroy the drawbridge), harbor (burn the boats), station (cut the tether).
import time
from array import array
from machine import Timer
from lcd import LCD, Keys, color
import blockies

lcd = LCD()
keys = Keys()
timer = None
OWNER = "0x7a3f9c0e4b12d8a6f5e3c1b0d9a8e7f6c5b4a391"
VT, VB = 20, 166          # the scene lives between these rows


def R(x, y, w, h, c):
    lcd.fill_rect(x, y, w, h, color(*c) if type(c) is tuple else c)


def E(cx, cy, rx, ry, c, f=True):
    lcd.ellipse(cx, cy, rx, ry, color(*c), f)


def P(pts, c, f=True):
    a = array('h')
    for x, y in pts:
        a.append(x)
        a.append(y)
    lcd.poly(0, 0, a, color(*c), f)


def L(x0, y0, x1, y1, c):
    lcd.line(x0, y0, x1, y1, color(*c))


def T(s, x, y, c):
    lcd.text(s, x, y, color(*c))


def CT(s, y, c):
    lcd.text(s, (240 - 8 * len(s)) // 2, y, color(*c))


def mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def grad(y0, y1, a, b, band=3):
    n = (y1 - y0 + band - 1) // band
    for i in range(n):
        R(0, y0 + i * band, 240, band, mix(a, b, i / max(1, n - 1)))


def stars(y0, y1, n, seed=5, c=(230, 230, 255)):
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        x = (s >> 8) % 240
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        y = y0 + (s >> 8) % (y1 - y0)
        lcd.pixel(x, y, color(*mix((90, 90, 120), c, ((s >> 4) & 7) / 7)))
        if i % 7 == 0:
            lcd.pixel(x + 1, y, color(*c))


def bricks(x0, y0, x1, y1, base, line, bh=8, bw=16):
    R(x0, y0, x1 - x0, y1 - y0, base)
    row = 0
    for y in range(y0, y1, bh):
        lcd.hline(x0, y, x1 - x0, color(*line))
        for x in range(x0 + (0 if row % 2 == 0 else bw // 2), x1, bw):
            lcd.vline(x, y, bh, color(*line))
        row += 1


def crenels(x0, x1, y, c, w=6, gap=6, h=6):
    for x in range(x0, x1, w + gap):
        R(x, y - h, min(w, x1 - x), h, c)


def flame(x, y, s=1, hot=True):
    """A flame whose base is centred on x at row y."""
    P([(x - 5 * s, y), (x - 4 * s, y - 6 * s), (x - 1 * s, y - 10 * s), (x + 1 * s, y - 15 * s),
       (x + 3 * s, y - 9 * s), (x + 5 * s, y - 5 * s), (x + 5 * s, y)], (230, 70, 20))
    P([(x - 3 * s, y), (x - 2 * s, y - 5 * s), (x, y - 9 * s), (x + 2 * s, y - 5 * s), (x + 3 * s, y)], (255, 160, 30))
    P([(x - 1 * s, y), (x, y - 5 * s), (x + 1 * s, y)], (255, 240, 140))


def torch(x, y, s=1):
    R(x - 1, y, 3, 10, (110, 70, 40))
    R(x - 2, y - 1, 5, 2, (70, 60, 60))
    flame(x, y - 1, s)


def person(x, y, s, body=(200, 50, 50), hair=(90, 60, 30), legs=(60, 60, 90), kind=None, skin=(240, 196, 160)):
    """An 8x16 unit figure, top-left at x,y, each unit s pixels."""
    def r(a, b, w, h, c):
        R(x + a * s, y + b * s, w * s, h * s, c)
    r(2, 11, 2, 4, legs)
    r(4, 11, 2, 4, legs)
    r(2, 15, 2, 1, (40, 30, 30))
    r(4, 15, 2, 1, (40, 30, 30))
    r(1, 5, 6, 6, body)
    r(0, 5, 1, 5, body)
    r(7, 5, 1, 5, body)
    r(0, 10, 1, 1, skin)
    r(7, 10, 1, 1, skin)
    r(2, 1, 4, 4, skin)
    r(3, 3, 1, 1, (20, 20, 30))
    r(5, 3, 1, 1, (20, 20, 30))
    if kind == "helm":
        r(1, 0, 6, 4, (170, 176, 192))
        r(2, 3, 4, 1, (25, 25, 35))
        r(3, -1, 2, 1, (200, 40, 40))
        r(3, 5, 2, 1, (120, 126, 142))
    elif kind == "cap":
        r(2, 0, 4, 1, (30, 44, 100))
        r(1, 1, 6, 1, (30, 44, 100))
        r(3, 0, 2, 1, (240, 200, 60))
        r(2, 2, 4, 1, skin)
    elif kind == "hood":
        r(1, 0, 6, 2, hair)
        r(1, 2, 1, 3, hair)
        r(6, 2, 1, 3, hair)
    elif kind == "astro":
        E(x + 4 * s, y + 2 * s + s // 2, 4 * s, 4 * s, (236, 240, 248))
        E(x + 4 * s, y + 2 * s + s // 2, 3 * s, 3 * s - 1, (28, 52, 110))
        R(x + 3 * s, y + s, s, s, (150, 190, 255))
    else:
        r(2, 0, 4, 2, hair)
        r(1, 1, 1, 2, hair)
        r(6, 1, 1, 2, hair)


def robot(x, y, s, body=(140, 150, 170), eye=(80, 255, 160)):
    def r(a, b, w, h, c):
        R(x + a * s, y + b * s, w * s, h * s, c)
    r(3, 0, 1, 2, (90, 96, 110))
    r(2, 2, 4, 4, body)
    r(2, 3, 4, 2, (20, 24, 36))
    r(3, 3, 1, 1, eye)
    r(5, 3, 1, 1, eye)
    r(1, 6, 6, 6, body)
    r(3, 7, 2, 2, (60, 200, 130))
    r(0, 7, 1, 4, body)
    r(7, 7, 1, 4, body)
    r(2, 12, 1, 3, (90, 96, 110))
    r(5, 12, 1, 3, (90, 96, 110))
    r(1, 15, 3, 1, (60, 66, 80))
    r(4, 15, 3, 1, (60, 66, 80))


def scroll(x, y, w, h, seal=True):
    R(x, y, w, h, (238, 222, 176))
    R(x - 2, y - 1, 3, h + 2, (200, 176, 120))
    R(x + w - 1, y - 1, 3, h + 2, (200, 176, 120))
    for i in range(2, h - 3, 3):
        lcd.hline(x + 3, y + i, w - 8, color(150, 120, 80))
    if seal:
        E(x + w - 7, y + h - 3, 3, 3, (190, 30, 30))


def wax(x, y, r):
    E(x, y, r, r, (170, 24, 30))
    E(x, y, r - 2, r - 2, (205, 44, 44))
    E(x, y, r // 2, r // 2, (150, 20, 26))
    lcd.pixel(x - r // 3, y - r // 3, color(255, 170, 160))


def book(x, y, w, h, c, label=None):
    R(x, y, w, h, c)
    R(x, y, w, 2, mix(c, (255, 255, 255), .3))
    R(x, y + h - 2, w, 2, mix(c, (0, 0, 0), .4))
    R(x + 2, y + 2, 2, h - 4, mix(c, (0, 0, 0), .3))
    if label:
        T(label, x + 6, y + h // 2 - 4, (250, 240, 200))


def banner(x, y, w, h, seed, edge=(200, 170, 60), field=(24, 30, 70)):
    R(x - 3, y - 4, w + 6, 4, (110, 80, 50))
    R(x, y, w, h, field)
    P([(x, y + h), (x + w, y + h), (x + w // 2, y + h + 10)], field)
    R(x, y, w, 2, edge)
    R(x, y, 2, h, edge)
    R(x + w - 2, y, 2, h, edge)
    s = (w - 12) // 8
    blockies.draw(lcd, seed, x + (w - 8 * s) // 2, y + 8, s)


# ---------------------------------------------------------------- the box

FACTS = (
    ("cert vs Infineon CA 101: OK", "read-only, nothing changed"),
    ("GenKeyPair in E0F1, P-256", "redo any time before T7"),
    ("2 test signatures verified", "plain digest + WebAuthn"),
    ("E0F0 signs the binding", "checked under the cert key"),
    ("owner 0x7a3f...a391", "compare on laptop: getSigner"),
    ("F1D0 record, F1D1 binding", "written, read back, redoable"),
    ("F1D1 F1D0 E0F1: LcsO -> op", "arm B+Y, then hold A for 3s"),
    ("GenKeyPair refused forever", "sealed: E0F1 F1D0 F1D1"),
    ("record matches, binding ok", "next: pin it, join the Safe"),
)


def frame(theme, i, accent, title, who, story, hold=None):
    red = i in (6, 7)
    hb = (110, 14, 20) if red else mix(accent, (0, 0, 0), .72)
    R(0, 0, 240, VT, hb)
    T(title, 6, 6, (255, 235, 235) if red else (255, 255, 255))
    T("%d/9" % (i + 1), 240 - 6 - 24, 6, (255, 200, 200) if red else accent)
    R(0, VB, 240, 240 - VB, (10, 12, 26))
    R(0, VB, 240, 2, (255, 60, 60) if red else accent)
    T(who, 6, 171, (255, 120, 120) if red else accent)
    T(story[0], 6, 182, (245, 245, 245))
    T(story[1], 6, 192, (245, 245, 245))
    lcd.hline(6, 203, 228, color(60, 70, 100))
    T(FACTS[i][0], 6, 207, (140, 165, 205))
    T(FACTS[i][1], 6, 217, (140, 165, 205))
    if hold is not None:
        R(6, 228, 228, 9, (40, 10, 14))
        R(6, 228, int(228 * hold), 9, (230, 40, 40))
        lcd.rect(6, 228, 228, 9, color(255, 120, 120))
        CT("HOLD A", 229, (255, 255, 255))
    elif i == 7:
        T("A continue         X facts", 6, 229, (110, 118, 140))
    else:
        T("A next     Y back    X facts", 6, 229, (110, 118, 140))
    lcd.show()


# ---------------------------------------------------------------- castle

def sky_dusk():
    grad(VT, 110, (30, 26, 84), (244, 146, 96))


def hills(base_y=112):
    P([(0, base_y), (0, base_y - 22), (34, base_y - 40), (70, base_y - 14), (108, base_y - 34), (150, base_y - 12),
       (196, base_y - 38), (240, base_y - 18), (240, base_y)], (54, 40, 96))


def castle_front(open_gate=False, torch_lit=True):
    sky_dusk()
    hills(112)
    R(0, 128, 240, VB - 128, (66, 96, 58))
    R(92, 128, 56, VB - 128, (160, 138, 104))
    for k in range(0, 40, 10):
        lcd.hline(92 + (k // 10) * 3, 132 + k // 2 * 2, 40, color(130, 110, 82))
    bricks(0, 64, 240, 128, (112, 106, 124), (84, 78, 98))
    crenels(50, 190, 64, (112, 106, 124))
    for (tx) in (6, 190):
        bricks(tx, 38, tx + 44, 128, (122, 116, 134), (88, 82, 102))
        crenels(tx, tx + 44, 38, (122, 116, 134), 8, 6, 7)
        R(tx + 18, 58, 8, 14, (18, 14, 28))
        R(tx + 18, 58, 8, 2, (250, 190, 90))
    R(98, 92, 44, 36, (14, 10, 22))
    E(120, 92, 22, 16, (14, 10, 22))
    if open_gate:
        R(98, 92, 44, 36, (250, 190, 100))
        E(120, 92, 22, 16, (250, 190, 100))
        R(112, 104, 16, 24, (255, 230, 170))
    else:
        for x in range(100, 142, 6):
            R(x, 78, 2, 26, (96, 86, 66))
        for y in (84, 92, 100):
            R(98, y, 44, 2, (96, 86, 66))
    torch(84, 98)
    torch(156, 98)


def c0():
    castle_front()
    R(58, 78, 2, 52, (130, 96, 60))
    P([(55, 78), (59, 68), (63, 78)], (210, 214, 224))
    person(62, 96, 2, body=(60, 84, 170), kind="helm", legs=(70, 70, 84))
    person(162, 96, 2, body=(196, 56, 52), hair=(120, 70, 30))
    scroll(112, 110, 16, 12)
    for (sx, sy) in ((131, 106), (108, 108), (127, 120)):
        lcd.pixel(sx, sy, color(255, 255, 200))
        lcd.pixel(sx + 1, sy, color(255, 255, 200))


def room(wall=(52, 40, 66), floor=(84, 64, 50)):
    bricks(0, VT, 240, 128, wall, mix(wall, (0, 0, 0), .35))
    R(0, 128, 240, VB - 128, floor)
    for x in range(0, 240, 30):
        lcd.vline(x, 128, VB - 128, color(*mix(floor, (0, 0, 0), .35)))
    lcd.hline(0, 128, 240, color(*mix(floor, (0, 0, 0), .5)))


def c1():
    room((44, 34, 58), (76, 58, 46))
    R(26, 60, 64, 68, (36, 26, 32))
    R(30, 64, 56, 64, (18, 10, 12))
    R(24, 56, 68, 6, (96, 90, 104))
    for k in range(3):
        flame(44 + k * 14, 128, 2)
    E(58, 124, 26, 4, (255, 170, 60))
    R(150, 112, 44, 8, (90, 96, 108))
    R(158, 120, 28, 8, (70, 74, 86))
    R(146, 108, 52, 5, (130, 136, 150))
    # the key, glowing on the anvil
    R(160, 100, 22, 3, (255, 224, 120))
    E(184, 101, 6, 6, (255, 224, 120), False)
    E(184, 101, 5, 5, (255, 224, 120), False)
    R(170, 103, 3, 5, (255, 224, 120))
    R(176, 103, 3, 4, (255, 224, 120))
    E(170, 100, 20, 8, (255, 160, 60), False)
    person(108, 96, 2, body=(90, 60, 40), hair=(50, 40, 40), legs=(50, 44, 40))
    R(96, 96, 4, 26, (110, 80, 50))
    R(92, 92, 12, 6, (120, 126, 140))
    for (sx, sy) in ((176, 90), (188, 86), (196, 94), (168, 84)):
        R(sx, sy, 2, 2, (255, 220, 100))


def c2():
    sky_dusk()
    hills(112)
    R(0, 120, 240, VB - 120, (108, 84, 60))
    for x in range(0, 240, 12):
        lcd.vline(x, 120, 8, color(90, 68, 48))
    R(0, 118, 240, 3, (70, 50, 36))
    for x in range(8, 240, 24):
        R(x, 100, 3, 20, (100, 76, 50))
        R(x - 1, 96, 5, 4, (120, 92, 60))
    R(0, 110, 240, 3, (100, 76, 50))
    # the dummy
    R(150, 128, 4, 24, (120, 88, 56))
    R(138, 128, 28, 4, (120, 88, 56))
    E(152, 108, 11, 14, (200, 170, 110))
    R(140, 106, 24, 5, (150, 120, 76))
    R(144, 120, 16, 8, (200, 170, 110))
    E(152, 92, 7, 7, (190, 160, 100))
    T("x", 149, 88, (80, 50, 30))
    # two slash marks
    L(128, 96, 172, 132, (255, 250, 200))
    L(129, 96, 173, 132, (255, 250, 200))
    L(172, 92, 132, 130, (255, 250, 200))
    L(173, 92, 133, 130, (255, 250, 200))
    person(78, 100, 2, body=(196, 56, 52), hair=(120, 70, 30))
    R(96, 108, 3, 14, (200, 205, 220))
    R(94, 106, 7, 3, (140, 110, 60))
    person(30, 100, 2, body=(60, 84, 170), kind="helm", legs=(70, 70, 84))


def c3():
    room((58, 44, 70), (92, 64, 56))
    R(20, 88, 200, 8, (120, 82, 50))
    R(28, 96, 8, 32, (100, 68, 42))
    R(204, 96, 8, 32, (100, 68, 42))
    scroll(98, 76, 44, 14, False)
    wax(120, 82, 9)
    R(112, 92, 16, 6, (200, 30, 40))
    P([(110, 92), (114, 108), (118, 92)], (200, 30, 40))
    P([(122, 92), (126, 108), (130, 92)], (200, 30, 40))
    person(40, 96, 2, body=(180, 44, 120), hair=(220, 190, 80), kind="hood")
    R(72, 92, 6, 8, (250, 224, 130))
    R(74, 88, 2, 4, (250, 224, 130))
    torch(30, 60)
    torch(210, 60)
    person(176, 100, 2, body=(60, 84, 170), kind="helm", legs=(70, 70, 84))
    for (sx, sy) in ((100, 70), (140, 72), (120, 66)):
        lcd.pixel(sx, sy, color(255, 255, 210))
        lcd.pixel(sx + 1, sy, color(255, 255, 210))


def c4():
    room((40, 34, 66), (76, 58, 60))
    banner(88, 34, 64, 74, OWNER)
    person(30, 96, 2, body=(196, 56, 52), hair=(120, 70, 30))
    person(178, 96, 2, body=(180, 44, 120), hair=(220, 190, 80), kind="hood")
    torch(62, 62)
    torch(178, 62)
    R(0, 128, 240, 2, (40, 30, 30))


def c5():
    room((48, 40, 60), (84, 62, 48))
    R(40, 86, 160, 8, (128, 88, 54))
    R(48, 94, 8, 34, (104, 70, 44))
    R(184, 94, 8, 34, (104, 70, 44))
    book(62, 74, 44, 12, (150, 40, 44), "F1D0")
    book(134, 74, 44, 12, (40, 80, 150), "F1D1")
    R(112, 70, 16, 16, (238, 222, 176))
    for k in range(4):
        lcd.hline(115, 73 + k * 3, 10, color(140, 110, 70))
    L(122, 84, 138, 62, (240, 240, 240))
    L(123, 84, 139, 62, (200, 200, 210))
    person(114, 96, 2, body=(70, 110, 84), hair=(60, 50, 40), kind="hood")
    R(220, 40, 2, 6, (250, 240, 170))
    R(216, 46, 10, 20, (240, 230, 190))
    flame(221, 40, 1)
    torch(28, 60)
    for (sx, sy) in ((86, 68), (154, 68)):
        lcd.pixel(sx, sy, color(255, 255, 210))


def bridge(state):
    """state: 0 whole, 1 wrecked and burning."""
    grad(VT, 100, (8, 10, 36), (40, 30, 80))
    stars(VT, 90, 46)
    E(196, 44, 12, 12, (240, 240, 220))
    E(201, 41, 11, 11, (30, 26, 70))
    P([(0, 100), (0, 70), (30, 58), (60, 76), (84, 60), (110, 100)], (12, 22, 30))
    R(0, 128, 96, VB - 128, (34, 48, 40))
    R(170, 128, 70, VB - 128, (34, 48, 40))
    # moat
    R(70, 130, 100, VB - 130, (22, 46, 96))
    for (wx, wy) in ((80, 140), (110, 150), (140, 142), (90, 158), (128, 158)):
        lcd.hline(wx, wy, 10, color(90, 130, 200))
    # castle wall right
    bricks(170, 52, 240, 132, (72, 68, 90), (50, 46, 66))
    crenels(170, 240, 52, (72, 68, 90))
    R(184, 92, 34, 40, (14, 10, 22))
    E(201, 92, 17, 14, (14, 10, 22))
    R(186, 66, 8, 12, (250, 190, 90))
    R(70, 132, 100, 2, (50, 80, 130))
    if state == 0:
        # planks lying over the moat, chains up to the gate
        R(68, 124, 106, 8, (124, 84, 50))
        for x in range(70, 172, 8):
            lcd.vline(x, 124, 8, color(84, 54, 32))
        L(174, 124, 174, 92, (150, 150, 160))
        L(160, 124, 184, 90, (150, 150, 160))
        L(90, 124, 184, 90, (120, 120, 130))
        person(184, 100, 2, body=(196, 56, 52), hair=(120, 70, 30))
        R(180, 104, 3, 14, (110, 70, 40))
        flame(181, 104, 2)
    else:
        # the bridge is a few burning planks, chains hang from the gate
        R(68, 124, 24, 8, (60, 36, 24))
        R(96, 120, 18, 6, (60, 36, 24))
        P([(126, 116), (142, 124), (138, 130), (124, 122)], (60, 36, 24))
        P([(150, 128), (168, 122), (172, 132), (150, 134)], (46, 28, 20))
        R(70, 132, 100, VB - 132, (16, 34, 78))
        L(174, 92, 176, 112, (150, 150, 160))
        L(176, 112, 172, 126, (150, 150, 160))
        L(184, 90, 190, 118, (120, 120, 130))
        for (fx, fy, fs) in ((78, 125, 2), (104, 121, 2), (132, 123, 1), (158, 129, 2), (96, 118, 1)):
            flame(fx, fy, fs)
        for (gx, gy, gw) in ((76, 136, 40), (100, 142, 60), (84, 150, 30), (124, 138, 36), (140, 148, 24), (110, 156, 40)):
            lcd.hline(gx, gy, gw, color(200, 90, 40))
            lcd.hline(gx + 6, gy + 1, gw - 12, color(255, 170, 70))
        for (sx, sy) in ((88, 92), (112, 84), (140, 96), (100, 70), (156, 80), (126, 102)):
            R(sx, sy, 2, 2, (255, 200, 100))
        for k in range(5):
            E(96 + k * 10, 74 - k * 4, 7 + k, 5 + k // 2, (48, 44, 66))
        person(200, 100, 2, body=(196, 56, 52), hair=(120, 70, 30))


def c6():
    bridge(0)


def c7():
    bridge(1)


def c8():
    grad(VT, 100, (60, 100, 170), (250, 200, 130))
    bricks(0, 60, 240, 128, (122, 116, 134), (90, 84, 104))
    crenels(0, 240, 60, (122, 116, 134), 10, 8, 7)
    R(0, 128, 240, VB - 128, (112, 100, 92))
    for x in range(0, 240, 24):
        for y in range(132, VB, 12):
            lcd.rect(x + (12 if (y // 12) % 2 else 0), y, 24, 12, color(90, 80, 74))
    R(84, 76, 72, 52, (20, 14, 30))
    E(120, 76, 36, 22, (20, 14, 30))
    R(84, 76, 72, 52, (255, 210, 130))
    E(120, 76, 36, 22, (255, 210, 130))
    R(110, 96, 20, 32, (255, 240, 200))
    banner(24, 62, 40, 50, OWNER)
    banner(176, 62, 40, 50, OWNER)
    person(60, 96, 2, body=(60, 84, 170), kind="helm", legs=(70, 70, 84))
    R(56, 80, 2, 50, (130, 96, 60))
    P([(53, 80), (57, 70), (61, 80)], (210, 214, 224))
    person(112, 100, 2, body=(196, 56, 52), hair=(120, 70, 30))
    for (sx, sy) in ((100, 92), (146, 92), (120, 60)):
        lcd.pixel(sx, sy, color(255, 255, 220))
        lcd.pixel(sx + 1, sy, color(255, 255, 220))


CASTLE = {
    "name": "THE GATEHOUSE", "accent": (255, 200, 60),
    "scenes": (c0, c1, c2, c3, c4, c5, c6, c7, c8),
    "text": (
        ("T1  PAPERS, PLEASE", "GATEKEEPER  (Infineon)", ("Halt! Show me your papers.", "The crown's seal... genuine.")),
        ("T2  THE FORGE", "SMITH  (the chip)", ("Your key is forged in here,", "and never leaves this room.")),
        ("T3  TRIAL BY DUMMY", "CAPTAIN", ("Strike twice. The key must", "sign and I must see it.")),
        ("T4  THE ROYAL SEAL", "HERALD  (factory key E0F0)", ("By the crown's own signet:", "this key lives in this chip.")),
        ("T5  YOUR COAT OF ARMS", "HERALD", ("Your arms, drawn from your", "address. Match the board.")),
        ("T6  THE TOWN LEDGER", "SCRIBE", ("Two entries: your record", "and the crown's bond.")),
        ("T7  POINT OF NO RETURN", "YOU", ("Torch the drawbridge. No key", "can be forged here again.")),
        ("T7  THE BRIDGE IS ASH", "YOU", ("It burns. The key and its", "records are frozen for good.")),
        ("T8  WELCOME, SIGNER", "GATEKEEPER", ("The keep knows your arms.", "The gate is yours to pass.")),
    ),
}

# ---------------------------------------------------------------- harbor

def sea(y0, top=(40, 110, 170), bot=(16, 46, 104)):
    grad(y0, VB, top, bot, 4)
    for k in range(14):
        wx = (k * 47 + 13) % 230
        wy = y0 + 6 + (k * 23) % (VB - y0 - 8)
        lcd.hline(wx, wy, 12 + (k % 3) * 6, color(*mix(top, (255, 255, 255), .35)))


def ship(x, y, burning=False, flag=(220, 60, 60)):
    """A small three-quarter ship, x,y = left end at the waterline; 78 px long, 60 tall."""
    hull = (70, 44, 30) if burning else (112, 72, 44)
    P([(x, y - 14), (x + 66, y - 14), (x + 58, y), (x + 8, y)], hull)
    P([(x + 66, y - 14), (x + 79, y - 19), (x + 58, y)], mix(hull, (0, 0, 0), .25))
    R(x + 1, y - 14, 66, 3, mix(hull, (255, 255, 255), .25))
    R(x + 6, y - 8, 54, 2, (150, 110, 50) if burning else (222, 172, 60))
    R(x + 30, y - 58, 3, 46, (80, 54, 34))
    sail = (44, 36, 34) if burning else (238, 230, 205)
    P([(x + 34, y - 54), (x + 34, y - 20), (x + 62, y - 22), (x + 58, y - 48)], sail)
    P([(x + 28, y - 52), (x + 28, y - 22), (x + 8, y - 24), (x + 12, y - 46)], sail)
    if not burning:
        R(x + 33, y - 61, 11, 5, flag)
        for k in range(4):
            R(x + 12 + k * 12, y - 12, 4, 3, (40, 30, 24))
    else:
        for (fx, fy, fs) in ((x + 46, y - 30, 2), (x + 18, y - 32, 2), (x + 34, y - 14, 2), (x + 56, y - 14, 1)):
            flame(fx, fy, fs)


def dock(x0, x1, y, h=10):
    R(x0, y, x1 - x0, h, (132, 92, 58))
    for x in range(x0, x1, 12):
        lcd.vline(x, y, h, color(92, 62, 38))
    R(x0, y + h, x1 - x0, 2, (70, 48, 30))
    for x in range(x0 + 8, x1, 40):
        R(x, y + h, 5, 26, (84, 58, 36))


def h0():
    grad(VT, 100, (120, 176, 226), (252, 222, 176))
    sea(100)
    ship(150, 124)
    R(0, 100, 30, 20, (0, 0, 0)) if False else None
    dock(0, 152, 126)
    # customs shed
    R(6, 84, 46, 42, (150, 110, 74))
    P([(2, 84), (29, 66), (56, 84)], (168, 60, 52))
    R(20, 100, 18, 26, (60, 40, 30))
    R(10, 90, 8, 8, (250, 220, 130))
    R(40, 90, 8, 8, (250, 220, 130))
    person(66, 94, 2, body=(30, 44, 100), kind="cap", legs=(60, 60, 80))
    R(82, 108, 10, 12, (110, 80, 50))
    R(102, 96, 18, 2, (110, 80, 50)) if False else None
    person(122, 94, 2, body=(196, 56, 52), hair=(120, 70, 30))
    scroll(96, 106, 16, 12)
    for (sx, sy) in ((116, 102), (94, 104), (112, 118)):
        lcd.pixel(sx, sy, color(255, 255, 220))
        lcd.pixel(sx + 1, sy, color(255, 255, 220))
    E(210, 60, 14, 14, (255, 236, 180))


def h1():
    grad(VT, 80, (130, 190, 236), (252, 214, 170))
    E(196, 70, 16, 16, (255, 226, 150))
    sea(80, (60, 130, 186), (40, 100, 160))
    R(0, 96, 240, VB - 96, (232, 208, 152))
    P([(0, 96), (240, 96), (240, 104), (0, 108)], (250, 240, 214))
    for k in range(0, 240, 18):
        lcd.hline(k, 118 + (k * 7) % 30, 6, color(210, 184, 130))
    # palm
    P([(30, 130), (36, 130), (34, 60), (30, 60)], (120, 84, 50))
    for (dx, dy) in ((-26, 8), (-16, -6), (14, -6), (26, 10), (0, -12)):
        P([(32, 58), (32 + dx // 2, 52 + dy // 2 - 6), (32 + dx, 60 + dy)], (46, 130, 66))
    # the hole and the chest
    E(140, 136, 34, 9, (150, 118, 76))
    E(140, 134, 30, 7, (86, 62, 42))
    R(122, 120, 36, 16, (128, 82, 44))
    R(122, 120, 36, 4, (150, 100, 56))
    R(120, 126, 40, 3, (232, 184, 60))
    R(137, 124, 6, 8, (250, 220, 100))
    for (sx, sy) in ((116, 112), (140, 108), (162, 114), (128, 104), (152, 100)):
        R(sx, sy, 2, 2, (255, 240, 140))
    # X marks the spot
    L(186, 138, 204, 152, (170, 40, 40))
    L(187, 138, 205, 152, (170, 40, 40))
    L(204, 138, 186, 152, (170, 40, 40))
    L(205, 138, 187, 152, (170, 40, 40))
    person(74, 100, 2, body=(196, 56, 52), hair=(120, 70, 30))
    R(96, 106, 3, 26, (120, 90, 56))
    R(94, 130, 8, 4, (170, 176, 190))
    R(50, 132, 22, 8, (214, 190, 138))


def h2():
    grad(VT, 110, (10, 14, 46), (120, 76, 116))
    stars(VT, 80, 40)
    sea(110, (60, 60, 120), (10, 16, 50))
    ship(20, 128)
    # the two flashes
    P([(200, 60), (0, 40), (0, 74)], (250, 234, 160))
    P([(200, 62), (0, 86), (0, 108)], (150, 128, 130))
    R(208, 118, 30, 48, (70, 60, 74))
    P([(196, 118), (250, 118), (250, 132), (190, 132)], (58, 50, 62))
    R(212, 40, 22, 80, (238, 232, 226))
    for y in (52, 76, 100):
        R(212, y, 22, 10, (196, 50, 50))
    R(208, 34, 30, 6, (60, 54, 66))
    R(212, 20, 22, 14, (255, 236, 150))
    R(212, 18, 22, 3, (60, 54, 66))
    E(223, 27, 8, 8, (255, 250, 210))
    person(186, 102, 2, body=(60, 110, 84), kind="cap", legs=(50, 50, 70))


def h3():
    grad(VT, 128, (126, 182, 230), (252, 222, 184))
    R(0, 128, 240, VB - 128, (140, 108, 74))
    for x in range(0, 240, 20):
        lcd.vline(x, 128, VB - 128, color(112, 84, 56))
    # hull on the stocks
    P([(70, 66), (222, 66), (200, 132), (96, 132)], (120, 74, 44))
    P([(222, 66), (238, 56), (214, 132), (200, 132)], (92, 56, 34))
    for y in range(72, 132, 8):
        lcd.hline(72 + (y - 66) // 3, y, 150 - (y - 66) // 3, color(84, 52, 32))
    R(72, 66, 150, 4, (168, 116, 66))
    for x in (84, 134, 184):
        R(x, 130, 6, 14, (84, 58, 36))
    # the brand
    E(146, 100, 12, 12, (255, 170, 60), False)
    E(146, 100, 8, 8, (255, 110, 40), False)
    R(140, 99, 12, 3, (255, 210, 110))
    E(146, 100, 3, 3, (255, 240, 170))
    L(112, 132, 138, 106, (74, 74, 84))
    L(113, 132, 139, 106, (74, 74, 84))
    E(140, 104, 4, 4, (255, 120, 40))
    for (sx, sy) in ((150, 86), (162, 92), (128, 88), (166, 106), (134, 116)):
        R(sx, sy, 2, 2, (255, 230, 120))
    person(72, 100, 2, body=(90, 70, 50), hair=(60, 40, 30), legs=(60, 50, 44))
    person(28, 100, 2, body=(196, 56, 52), hair=(120, 70, 30))
    R(108, 108, 8, 6, (74, 74, 84))


def h4():
    grad(VT, 90, (240, 150, 100), (252, 214, 150))
    sea(90, (200, 140, 130), (60, 60, 120))
    E(120, 92, 46, 12, (255, 210, 130))
    ship(10, 116)
    ship(160, 112)
    dock(0, 240, 130)
    R(118, 26, 4, 106, (170, 130, 80))
    E(120, 24, 4, 4, (232, 184, 60))
    R(122, 30, 64, 52, (24, 30, 70))
    R(122, 30, 64, 3, (232, 184, 60))
    R(122, 30, 3, 52, (232, 184, 60))
    R(183, 30, 3, 52, (232, 184, 60))
    R(122, 79, 64, 3, (232, 184, 60))
    blockies.draw(lcd, OWNER, 134, 38, 5)
    person(56, 102, 2, body=(30, 44, 100), kind="cap", legs=(60, 60, 80))
    person(196, 102, 2, body=(196, 56, 52), hair=(120, 70, 30))


def h5():
    bricks(0, VT, 240, 128, (112, 74, 46), (82, 52, 32), 10, 240)
    R(0, 128, 240, VB - 128, (72, 46, 30))
    for x in range(0, 240, 40):
        lcd.vline(x, 128, VB - 128, color(52, 32, 20))
    E(44, 76, 24, 24, (200, 160, 70))
    E(44, 76, 20, 20, (60, 130, 190))
    grad(58, 94, (140, 190, 230), (60, 130, 190), 6) if False else None
    R(24, 78, 40, 12, (30, 90, 150))
    E(38, 68, 6, 4, (255, 255, 255))
    R(80, 96, 130, 8, (150, 100, 60))
    R(88, 104, 8, 24, (100, 66, 40))
    R(194, 104, 8, 24, (100, 66, 40))
    book(112, 84, 44, 12, (150, 40, 44), "F1D0")
    book(164, 84, 44, 12, (40, 80, 150), "F1D1")
    R(96, 80, 10, 16, (240, 214, 130))
    E(101, 76, 4, 4, (255, 240, 170))
    flame(101, 78, 1)
    person(140, 100, 2, body=(60, 110, 84), kind="cap", legs=(50, 50, 70))
    R(20, 104, 26, 24, (110, 70, 40))
    lcd.hline(20, 110, 26, color(70, 44, 26))
    lcd.hline(20, 120, 26, color(70, 44, 26))


def shore(burning):
    if burning:
        grad(VT, 100, (30, 14, 34), (200, 70, 40))
        sea(100, (150, 60, 50), (30, 20, 50))
    else:
        grad(VT, 100, (36, 30, 96), (246, 150, 100))
        sea(100, (120, 90, 140), (22, 34, 92))
    P([(240, 96), (240, VB), (120, VB), (150, 132), (190, 108)], (196, 170, 120) if not burning else (120, 90, 70))
    ship(6, 124, burning, (220, 60, 60))
    ship(90, 116, burning, (60, 120, 220))


def h6():
    shore(False)
    L(84, 112, 186, 122, (200, 180, 130))
    L(70, 124, 190, 124, (200, 180, 130))
    person(196, 96, 2, body=(196, 56, 52), hair=(120, 70, 30))
    R(192, 100, 3, 14, (110, 70, 40))
    flame(193, 100, 2)


def h7():
    shore(True)
    for (gx, gy, gw) in ((10, 132, 60), (96, 128, 60), (30, 142, 40), (110, 138, 40), (60, 152, 50)):
        lcd.hline(gx, gy, gw, color(230, 110, 50))
        lcd.hline(gx + 6, gy + 1, gw - 12, color(255, 190, 90))
    for k in range(5):
        E(50 + k * 8, 60 - k * 8, 8 + k, 6 + k // 2, (60, 44, 56))
        E(130 + k * 6, 52 - k * 7, 8 + k, 6 + k // 2, (60, 44, 56))
    person(196, 96, 2, body=(196, 56, 52), hair=(120, 70, 30))
    R(192, 116, 3, 12, (110, 70, 40))


def h8():
    grad(VT, 100, (250, 190, 130), (150, 204, 240))
    E(60, 96, 22, 22, (255, 240, 180))
    R(0, 100, 240, VB - 100, (120, 168, 84))
    P([(0, 108), (90, 100), (240, 110), (240, 122), (0, 130)], (236, 214, 160))
    P([(60, VB), (110, VB), (128, 118), (118, 118)], (196, 170, 120))
    for (hx, hy, w) in ((140, 84, 34), (184, 92, 40)):
        R(hx, hy, w, 26, (204, 170, 120))
        P([(hx - 4, hy), (hx + w // 2, hy - 18), (hx + w + 4, hy)], (176, 70, 56))
        R(hx + 6, hy + 8, 8, 8, (250, 224, 130))
        R(hx + w - 14, hy + 8, 8, 8, (250, 224, 130))
    R(14, 60, 3, 72, (170, 130, 80))
    R(17, 62, 30, 24, (24, 30, 70))
    blockies.draw(lcd, OWNER, 21, 65, 3)
    person(84, 100, 2, body=(196, 56, 52), hair=(120, 70, 30))
    person(46, 106, 2, body=(30, 44, 100), kind="cap", legs=(60, 60, 80))
    ship(160, 150)


HARBOR = {
    "name": "BURN THE BOATS", "accent": (90, 210, 232),
    "scenes": (h0, h1, h2, h3, h4, h5, h6, h7, h8),
    "text": (
        ("T1  CUSTOMS DOCK", "HARBORMASTER  (Infineon)", ("Manifest, captain. Stamped", "by the Infineon shipyard?")),
        ("T2  BURY THE TREASURE", "YOU  (the chip)", ("Bury it where none can see.", "No map. No copy. Ever.")),
        ("T3  SIGNAL LAMP TEST", "LIGHTKEEPER", ("Flash the lamp twice. The", "harbor must see it answer.")),
        ("T4  THE SHIPYARD BRAND", "SHIPWRIGHT  (key E0F0)", ("Branded on the hull: built", "here, and it holds this key.")),
        ("T5  RUN UP YOUR COLORS", "HARBORMASTER", ("Your flag, drawn from your", "address. Match the board.")),
        ("T6  THE SHIP'S LOG", "FIRST MATE", ("Two log entries: the record", "and the shipyard's bond.")),
        ("T7  BURN THE BOATS", "YOU", ("Torch the fleet. There is no", "sailing back to forge again.")),
        ("T7  NO WAY BACK", "YOU", ("The boats burn to the water.", "The key is frozen for good.")),
        ("T8  LAND HO, SIGNER", "HARBORMASTER", ("Welcome ashore. The town", "knows your colors.")),
    ),
}

# ---------------------------------------------------------------- station

def space(planet=True):
    R(0, VT, 240, VB - VT, (4, 6, 22))
    stars(VT, VB, 70, 11)
    if planet:
        E(196, 150, 70, 70, (40, 84, 140))
        E(190, 144, 60, 60, (56, 116, 176))
        E(176, 130, 30, 22, (120, 176, 220), False)


def panel_wall(y0=VT, y1=128, base=(44, 54, 78)):
    R(0, y0, 240, y1 - y0, base)
    for x in range(0, 240, 40):
        lcd.vline(x, y0, y1 - y0, color(*mix(base, (0, 0, 0), .5)))
        for y in range(y0 + 6, y1, 24):
            lcd.pixel(x + 3, y, color(*mix(base, (255, 255, 255), .4)))
            lcd.pixel(x + 36, y, color(*mix(base, (255, 255, 255), .4)))
    lcd.hline(0, y0 + 1, 240, color(*mix(base, (255, 255, 255), .3)))


def floor_grate(y0=128):
    R(0, y0, 240, VB - y0, (30, 34, 48))
    for x in range(0, 240, 12):
        lcd.vline(x, y0, VB - y0, color(58, 64, 84))
    for y in range(y0, VB, 8):
        lcd.hline(0, y, 240, color(58, 64, 84))
    R(0, y0, 240, 2, (255, 200, 40))
    for x in range(0, 240, 16):
        P([(x, y0 + 2), (x + 8, y0 + 2), (x + 4, y0 + 6)], (30, 34, 48)) if False else None


def window(x, y, w, h):
    R(x - 3, y - 3, w + 6, h + 6, (110, 120, 146))
    R(x, y, w, h, (4, 6, 22))
    stars(y, y + h, 16, x)
    E(x + w - 12, y + h - 4, 26, 26, (56, 116, 176))
    R(x - 3, y + h + 3, w + 6, 4, (30, 34, 48)) if False else None


def hero_space(x, y, s=2):
    person(x, y, s, body=(236, 240, 248), legs=(200, 206, 220), kind="astro")


def s0():
    panel_wall()
    window(136, 40, 88, 54)
    floor_grate()
    # dock ai on a podium, scanning
    R(30, 116, 34, 12, (70, 78, 104))
    robot(38, 84, 2)
    P([(58, 96), (96, 92), (96, 128), (58, 108)], (60, 200, 130)) if False else None
    for k in range(5):
        lcd.line(58, 100, 100, 92 + k * 8, color(*mix((40, 120, 90), (120, 255, 180), k / 4)))
    hero_space(100, 96)
    # id chit
    R(72, 70, 20, 14, (220, 230, 240))
    R(76, 74, 6, 6, (232, 184, 60))
    R(84, 74, 6, 2, (120, 130, 150))
    R(84, 78, 6, 2, (120, 130, 150))
    for (sx, sy) in ((92, 68), (70, 72), (90, 86)):
        lcd.pixel(sx, sy, color(200, 255, 220))
        lcd.pixel(sx + 1, sy, color(200, 255, 220))
    for x in (10, 20):
        R(x, 40, 6, 6, (255, 80, 60))


def s1():
    panel_wall()
    floor_grate()
    R(70, 44, 100, 84, (86, 132, 176))
    R(74, 48, 92, 80, (16, 28, 54))
    E(120, 48, 46, 8, (86, 132, 176))
    # laser arms
    L(90, 20, 112, 82, (150, 160, 180))
    L(91, 20, 113, 82, (150, 160, 180))
    L(150, 20, 128, 82, (150, 160, 180))
    L(149, 20, 127, 82, (150, 160, 180))
    L(112, 82, 120, 96, (255, 90, 90))
    L(128, 82, 120, 96, (255, 90, 90))
    # key card taking shape
    R(100, 96, 40, 4, (255, 224, 120))
    E(146, 98, 6, 6, (255, 224, 120), False)
    E(146, 98, 5, 5, (255, 224, 120), False)
    R(122, 100, 3, 6, (255, 224, 120))
    R(130, 100, 3, 5, (255, 224, 120))
    E(120, 98, 30, 14, (255, 190, 80), False)
    for (sx, sy) in ((104, 88), (150, 88), (120, 110), (136, 92)):
        R(sx, sy, 2, 2, (255, 240, 170))
    R(14, 90, 40, 38, (60, 68, 96))
    for k in range(6):
        R(20 + (k % 3) * 12, 96 + (k // 3) * 14, 6, 6, (60, 255, 150) if k % 2 else (255, 190, 60))
    hero_space(190, 96)


def s2():
    R(0, VT, 240, VB - VT, (10, 12, 26))
    # a tunnel in perspective
    P([(0, VT), (240, VT), (160, 70), (80, 70)], (26, 30, 52))
    P([(0, VB), (240, VB), (160, 120), (80, 120)], (34, 38, 60))
    P([(0, VT), (80, 70), (80, 120), (0, VB)], (20, 24, 44))
    P([(240, VT), (160, 70), (160, 120), (240, VB)], (20, 24, 44))
    R(80, 70, 80, 50, (6, 8, 20))
    for k in range(1, 4):
        lcd.rect(80 - k * 20, 70 - k * 16, 80 + k * 40, 50 + k * 32, color(60, 68, 100))
    # target
    for (r, c) in ((22, (230, 230, 240)), (16, (220, 60, 60)), (10, (230, 230, 240)), (5, (220, 60, 60))):
        E(120, 95, r, r, c)
    # two pulses
    for (x, y) in ((70, 96), (100, 96)):
        R(x, y - 1, 22, 3, (120, 255, 210))
        R(x + 2, y - 3, 16, 7, (40, 200, 160)) if False else None
        E(x + 22, y, 3, 3, (220, 255, 245))
    hero_space(30, 100)
    R(52, 108, 22, 5, (130, 138, 160))
    R(70, 106, 6, 9, (200, 60, 60))
    R(178, 104, 40, 24, (60, 68, 96))
    robot(190, 78, 2, eye=(255, 190, 60))


def s3():
    panel_wall()
    floor_grate()
    R(70, 106, 100, 22, (70, 78, 104))
    R(70, 106, 100, 3, (110, 120, 150))
    R(108, 98, 28, 8, (220, 230, 240))
    R(112, 100, 6, 4, (232, 184, 60))
    # holographic stamp
    P([(122, 30), (150, 30), (140, 96), (116, 96)], (30, 90, 110)) if False else None
    for k, w in enumerate((30, 26, 22, 18)):
        E(122, 40 + k * 14, w, 6, (60, 200, 230), False)
    R(120, 30, 4, 62, (80, 210, 240))
    E(122, 92, 12, 4, (200, 250, 255))
    # fleet command hologram
    person(22, 76, 3, body=(60, 190, 220), hair=(90, 220, 240), legs=(50, 160, 190), skin=(120, 220, 240))
    for y in range(76, 124, 4):
        lcd.hline(22, y, 24, color(10, 30, 50))
    hero_space(190, 96)
    for (sx, sy) in ((100, 52), (150, 60), (134, 78)):
        R(sx, sy, 2, 2, (200, 250, 255))


def s4():
    panel_wall()
    floor_grate()
    R(62, 30, 116, 100, (54, 64, 92))
    E(120, 78, 50, 50, (200, 160, 60))
    E(120, 78, 44, 44, (24, 30, 70))
    E(120, 78, 44, 44, (232, 190, 80), False)
    blockies.draw(lcd, OWNER, 98, 56, 5)
    for (bx, by) in ((66, 34), (172, 34), (66, 124), (172, 124)):
        R(bx, by, 6, 6, (140, 150, 176))
    robot(24, 96, 2)
    hero_space(190, 96)
    R(0, 40, 6, 6, (60, 255, 150))


def s5():
    panel_wall(base=(36, 44, 66))
    floor_grate()
    R(56, 34, 128, 94, (56, 66, 96))
    for (bx, label, c) in ((70, "F1D0", (150, 40, 44)), (122, "F1D1", (40, 80, 150))):
        R(bx, 52, 48, 22, (16, 22, 40))
        R(bx + 4, 56, 40, 14, c)
        T(label, bx + 8, 59, (250, 240, 200))
        R(bx + 40, 76, 4, 4, (60, 255, 150))
    for k in range(8):
        R(72 + k * 14, 92, 6, 6, (60, 255, 150) if k % 3 else (255, 190, 60))
    for k in range(8):
        R(72 + k * 14, 104, 6, 6, (255, 190, 60) if k % 4 else (60, 255, 150))
    robot(20, 88, 2)
    hero_space(196, 96)
    R(48, 70, 12, 3, (140, 150, 176))


def hull_ship(x, y, s=1):
    """A little spacecraft, nose to the right; x,y = left end, centre line."""
    P([(x, y - 12 * s), (x + 50 * s, y - 12 * s), (x + 80 * s, y), (x + 50 * s, y + 12 * s), (x, y + 12 * s)], (196, 204, 220))
    P([(x, y - 12 * s), (x - 10 * s, y - 20 * s), (x + 22 * s, y - 12 * s)], (140, 150, 176))
    P([(x, y + 12 * s), (x - 10 * s, y + 20 * s), (x + 22 * s, y + 12 * s)], (140, 150, 176))
    R(x - 8 * s, y - 6 * s, 8 * s, 12 * s, (90, 100, 130))
    P([(x + 46 * s, y - 8 * s), (x + 68 * s, y - 2 * s), (x + 46 * s, y + 2 * s)], (60, 120, 200))
    R(x + 10 * s, y - 2 * s, 30 * s, 2 * s, (232, 184, 60))


def s6():
    space()
    # station module, tube and ship
    R(0, 50, 64, 100, (96, 108, 138))
    R(0, 50, 64, 6, (140, 152, 180))
    for y in range(64, 150, 14):
        R(0, y, 64, 2, (60, 70, 100))
    R(64, 88, 84, 28, (140, 150, 176))
    for x in range(72, 154, 12):
        R(x, 88, 3, 28, (90, 100, 130))
    R(64, 88, 90, 4, (190, 200, 224))
    for x in (84, 118):
        E(x, 102, 5, 5, (255, 40, 40))
        E(x, 102, 2, 2, (255, 200, 200))
    hull_ship(150, 102)
    for x in range(160, 240, 1):
        pass
    P([(60, 60), (76, 60), (68, 74)], (255, 200, 40))
    R(67, 63, 2, 6, (30, 30, 40))
    R(67, 71, 2, 2, (30, 30, 40))
    hero_space(176, 118, 2) if False else None


def s7():
    space()
    R(0, 50, 64, 100, (96, 108, 138))
    R(0, 50, 64, 6, (140, 152, 180))
    for y in range(64, 150, 14):
        R(0, y, 64, 2, (60, 70, 100))
    # torn stub
    P([(64, 88), (100, 88), (92, 100), (100, 108), (90, 116), (64, 116)], (140, 150, 176))
    P([(64, 88), (100, 88), (96, 92), (64, 92)], (190, 200, 224))
    # blast
    E(112, 102, 22, 20, (255, 120, 40))
    E(112, 102, 15, 13, (255, 200, 80))
    E(112, 102, 7, 6, (255, 250, 220))
    for (dx, dy, w) in ((-40, -34, 8), (30, -30, 6), (46, 22, 10), (-30, 34, 6), (60, -6, 5), (22, 38, 5)):
        P([(112 + dx, 102 + dy), (112 + dx + w, 102 + dy + 3), (112 + dx + 2, 102 + dy + w)], (170, 180, 200))
    for (dx, dy) in ((-16, -26), (20, -22), (30, 12), (-24, 18), (4, -34), (36, -8)):
        R(112 + dx, 102 + dy, 3, 3, (255, 210, 100))
    # the ship, drifting away
    hull_ship(164, 102)
    P([(154, 96), (160, 102), (154, 108)], (255, 210, 80))


def s8():
    space()
    hull_ship(62, 88, 2)
    P([(60, 80), (44, 88), (60, 96)], (255, 210, 80)) if False else None
    E(58, 88, 10, 14, (255, 190, 80))
    E(52, 88, 6, 8, (255, 250, 200))
    E(140, 88, 8, 8, (36, 30, 70)) if False else None
    # patch on the hull
    R(112, 80, 20, 20, (24, 30, 70))
    lcd.rect(112, 80, 20, 20, color(232, 190, 80))
    blockies.draw(lcd, OWNER, 115, 83, 2)
    # far station
    R(6, 140, 34, 12, (96, 108, 138))
    R(16, 132, 4, 8, (140, 152, 180))
    hero_space(0, 0, 0) if False else None


STATION = {
    "name": "DOCKING BAY", "accent": (100, 240, 170),
    "scenes": (s0, s1, s2, s3, s4, s5, s6, s7, s8),
    "text": (
        ("T1  DOCKING CLEARANCE", "DOCK AI  (Infineon)", ("Scanning credentials...", "Hull ID genuine. Welcome.")),
        ("T2  THE FABRICATOR", "FAB-BAY  (the chip)", ("Key grown in a sealed bay.", "No one sees it. No copies.")),
        ("T3  TEST FIRE", "RANGE MASTER", ("Fire two test pulses. The", "key must sign, I must see.")),
        ("T4  FLEET COUNTERSIGN", "FLEET CMD  (key E0F0)", ("Fleet stamps your card: this", "key lives in this chip.")),
        ("T5  MISSION PATCH", "QUARTERMASTER", ("Your patch, drawn from your", "address. Match the board.")),
        ("T6  FLIGHT RECORDER", "SYSTEMS", ("Two cartridges: your record", "and the fleet's bond.")),
        ("T7  CUT THE TETHER", "YOU", ("Blow the docking tube. No", "forging another key here.")),
        ("T7  TETHER SEVERED", "YOU", ("The tube drifts off. The key", "is frozen for good.")),
        ("T8  CLEAR SKIES, SIGNER", "DOCK AI", ("Undocked, and all yours. The", "fleet knows your patch.")),
    ),
}

THEMES = [CASTLE, HARBOR, STATION]


PAGES = {
    0: ("T1  PRE-FLIGHT", (
        ("chip   OPTIGA Trust M", 0), ("serial 0a091b5c000b0062006c", 0), ("cert   Trust M CA 101", 0),
        ("cert#  1d560a9b", 0), ("vs pinned CA key: VALID", 1), ("time   1.4 s on the Pico", 0),
        ("LcsA   operational", 0), ("", 0), ("read-only. changes nothing.", 2))),
    1: ("T2  MAKE THE KEY", (
        ("GenKeyPair in E0F1", 0), ("curve  NIST P-256", 0), ("usage  Sign", 0), ("", 0),
        ("public half comes out ONCE;", 2), ("the chip never returns it", 2), ("", 0),
        ("needs ALLOW_GENKEY, arm,", 0), ("hold A 3 s. redo before T7", 0))),
    2: ("T3  TEST SIGNATURES", (
        ("two test digests signed", 0), ("plain digest: verified here", 1), ("WebAuthn assertion: verified", 1),
        ("low-s form checked", 0), ("", 0), ("read-only. changes nothing.", 2))),
    3: ("T4  BIND TO THE CHIP", (
        ("E0F0  Infineon factory key", 0), ("certified in E0E0", 0), ("signs: this chip holds", 0),
        ("       this key", 0), ("checked under the cert key", 1), ("", 0), ("stored later in F1D1", 0),
        ("read-only until T6", 2))),
    4: ("T5  OWNER ADDRESS", (
        ("0x7a3f9c0e4b12d8a6f5e3", 0), ("c1b0d9a8e7f6c5b4a391", 0), ("", 0),
        ("the arms are a picture of", 0), ("this address (a blockie)", 0), ("", 0),
        ("compare on the laptop with", 2), ("getSigner before T6", 2))),
    5: ("T6  RECORD + BINDING", (
        ("F1D0  record, 110 bytes", 0), ("  PQ v2, profile, serial,", 0), ("  key OID, qx, qy, owner", 0),
        ("F1D1  binding, 83 bytes", 0), ("  E0F0 (r,s), SHA-256(cert)", 0), ("", 0),
        ("written, then read back", 1), ("redoable until T7", 2))),
    6: ("T7  SEAL", (
        ("SEALS, NO WAY BACK", 3), ("E0F1  the Safe key", 0), ("F1D0  the record", 0),
        ("F1D1  the binding", 0), ("LcsO: creation->operational", 0), ("", 0),
        ("needs ALLOW_LOCK in secrets", 0), ("needs arm (B+Y), hold A 3 s", 0),
        ("afterwards GenKeyPair is", 3), ("refused; the key still signs", 1))),
    7: ("T7  SEALED", (
        ("E0F1  operational", 3), ("F1D0  operational", 3), ("F1D1  operational", 3), ("", 0),
        ("GenKeyPair on E0F1: refused", 3), ("the key still signs", 1), ("", 0),
        ("nothing can un-seal these", 2))),
    8: ("T8  DONE", (
        ("all three objects sealed", 1), ("record matches the key", 1), ("binding verifies", 1),
        ("key still signs a test", 1), ("", 0), ("registered in chips.json", 0),
        ("next: tools/fw pin", 2))),
}
CLR = ((200, 210, 230), (90, 255, 150), (255, 200, 60), (255, 90, 90))


def _facts(i):
    title, rows = PAGES[i]
    red = i in (6, 7)
    lcd.fill(0)
    R(0, 0, 240, 20, (110, 14, 20) if red else (36, 50, 84))
    T("FACTS  " + title, 6, 6, (255, 255, 255))
    R(0, 20, 240, 220, (8, 10, 22))
    y = 34
    for (txt, c) in rows:
        T(txt, 8, y, CLR[c])
        y += 14
    T("the story is a skin; this is", 8, 200, (110, 118, 140))
    T("what the chip is doing.", 8, 210, (110, 118, 140))
    T("X back to the story", 8, 226, (110, 118, 140))
    lcd.show()


def facts(i):
    lcd.frames(_facts, i)


def _draw(t, i):
    th = THEMES[t]
    lcd.fill(0)
    th["scenes"][i]()
    title, who, story = th["text"][i]
    frame(th["name"], i, th["accent"], title, who, story, hold=0.62 if i == 6 else None)


def show(t, i):
    lcd.frames(_draw, t, i)     # the 240x240 board draws in strips; every scene is redrawn per strip


def check():
    for th in THEMES:
        for (title, who, story) in th["text"]:
            for s in (title, who) + tuple(story):
                if len(s) > 28:
                    print("TOO LONG", len(s), s)
    for a, b in FACTS:
        for s in (a, b):
            if len(s) > 28:
                print("TOO LONG", len(s), s)


cur = [0, 0, False]


def tick(_):
    for k in keys.pressed():
        if k == "B":
            stop()
            return
        if k == "X":
            cur[2] = not cur[2]
            (facts(cur[1]) if cur[2] else show(cur[0], cur[1]))
            continue
        cur[2] = False
        if k == "right":
            cur[1] = (cur[1] + 1) % 9
        elif k == "left":
            cur[1] = (cur[1] - 1) % 9
        elif k == "down":
            cur[0] = (cur[0] + 1) % len(THEMES)
        elif k == "up":
            cur[0] = (cur[0] - 1) % len(THEMES)
        else:
            continue
        show(cur[0], cur[1])


def start():
    global timer
    check()
    show(cur[0], cur[1])
    timer = Timer(period=60, mode=Timer.PERIODIC, callback=tick)
    print("gatescenes: left/right step, up/down theme, X facts, B quits")


def stop():
    if timer:
        timer.deinit()


start()
