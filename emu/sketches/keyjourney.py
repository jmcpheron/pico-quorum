# keyjourney: two futuristic story skins for the Trust M signing ceremony (T1..T8), as static screens.
#   VESPER: a friendly starliner line that boards, tests, hallmarks and seals your "keypod".
#   SABLE LANTERN: a rainy neon district whose notary registry does the same for your "vial".
# Emulator: tools/emu run keyjourney   left/right = screen, up/down = theme, X = facts, B quits.
# One pill-shaped pod travels through all eight steps and its shell shows what has been done to it:
# dashed (not made yet) > teal (made) > green pip (tested) > gold band (hallmarked) > ID badge (your
# address) > tags (filed) > silver with a lock (SEALED) > green halo (delivered). It is drawn by one
# function, pod(), on every screen and in the journey rail under the header.
# Every screen keeps the real step code and the real values; the story is a skin, never the truth.
from array import array
from machine import Timer
from lcd import LCD, Keys, color
import blockies

lcd = LCD()
keys = Keys()
timer = None
OWNER = "0x7a3f9c0e4b12d8a6f5e3c1b0d9a8e7f6c5b4a391"
VT, VB = 20, 166
GREEN = (60, 255, 140)
GOLD = (240, 190, 60)
STEEL = (150, 162, 186)


def R(x, y, w, h, c):
    lcd.fill_rect(x, y, w, h, color(*c) if type(c) is tuple else c)


def E(cx, cy, rx, ry, c, f=True, m=15):
    lcd.ellipse(cx, cy, rx, ry, color(*c), f, m)


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


def BT(s, x, y, c, k=2):
    lcd.big_text(s, x, y, color(*c), k)


def mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def grad(y0, y1, a, b, band=3):
    n = (y1 - y0 + band - 1) // band
    for i in range(n):
        R(0, y0 + i * band, 240, band, mix(a, b, i / max(1, n - 1)))


def lcg(s):
    return (s * 1103515245 + 12345) & 0x7FFFFFFF


def stars(y0, y1, n, seed=5, c=(230, 230, 255)):
    s = seed
    for i in range(n):
        s = lcg(s)
        x = (s >> 8) % 240
        s = lcg(s)
        y = y0 + (s >> 8) % (y1 - y0)
        lcd.pixel(x, y, color(*mix((90, 90, 120), c, ((s >> 4) & 7) / 7)))
        if i % 7 == 0:
            lcd.pixel(x + 1, y, color(*c))


# ------------------------------------------------------------------ the pod

STATES = 8      # 0 not made .. 7 delivered


def pod(cx, cy, st, L=56, H=22):
    """The key pod. st: 0 ghost, 1 made, 2 tested, 3 hallmarked, 4 named, 5 filed, 6 sealed, 7 delivered."""
    h = H // 2
    x0 = cx - L // 2

    def fx(v):
        return x0 + v * L // 56
    if st == 0:
        c = color(110, 205, 225)
        for x in range(x0 + h, x0 + L - h, 6):
            lcd.hline(x, cy - h, 3, c)
            lcd.hline(x, cy + h - 1, 3, c)
        lcd.ellipse(x0 + h, cy, h, h, c, False, 6)
        lcd.ellipse(x0 + L - h, cy, h, h, c, False, 9)
        return
    if st >= 7:
        E(cx, cy, L // 2 + 5, h + 5, mix(GREEN, (0, 0, 0), .55), False)
        E(cx, cy, L // 2 + 3, h + 3, GREEN, False)
    sealed = st >= 6
    body = (178, 188, 208) if sealed else (46, 196, 196)
    edge = mix(body, (0, 0, 0), .5)
    hi = mix(body, (255, 255, 255), .55)
    E(x0 + h, cy, h, h, edge)
    E(x0 + L - h, cy, h, h, edge)
    R(x0 + h, cy - h, L - H, H, edge)
    E(x0 + h, cy, h - 1, h - 1, body)
    E(x0 + L - h, cy, h - 1, h - 1, body)
    R(x0 + h, cy - h + 1, L - H, H - 2, body)
    R(x0 + h, cy - h + 2, L - H, max(1, H // 8), hi)
    if st >= 2:                                     # tested: a green pip in the left cap
        pr = max(1, H // 7)
        E(fx(7), cy, pr + 1, pr + 1, (8, 40, 24))
        E(fx(7), cy, pr, pr, GREEN)
    if st >= 3:                                     # hallmarked: the maker's gold band
        bw = max(2, 5 * L // 56)
        R(fx(33), cy - h + 1, bw, H - 2, GOLD)
        R(fx(33), cy - h + 1, 1, H - 2, mix(GOLD, (0, 0, 0), .4))
    if st >= 4:                                     # named: your blockie, or a patch when small
        if H >= 16:
            sd = H - 8
            R(fx(15), cy - sd // 2, sd, sd, (10, 14, 34))
            blockies.draw(lcd, OWNER, fx(15) + (sd - 8) // 2, cy - 4, 1)
        else:
            R(fx(16), cy - 1, max(2, 3 * L // 56), max(2, H // 4), (170, 100, 240))
    if st >= 5 and H >= 16:                         # filed: the two record tags on strings
        for tx in (fx(14), fx(28)):
            lcd.vline(tx + 4, cy + h, 3, color(200, 200, 210))
            R(tx, cy + h + 3, 9, 7, (240, 230, 190))
            lcd.hline(tx + 1, cy + h + 5, 7, color(150, 120, 80))
    if sealed:                                      # sealed: a lock plate where the pod used to open
        if H >= 16:
            R(fx(42), cy - 5, 10, 10, (36, 40, 58))
            lcd.ellipse(fx(47), cy - 5, 3, 3, color(*GOLD), False, 3)
            R(fx(47) - 1, cy - 1, 2, 4, (210, 210, 220))
        else:
            R(fx(45), cy - 1, max(2, 4 * L // 56), max(2, H // 4), (255, 60, 50))


def rail(i, accent, noun="POD"):
    """The journey rail: 8 nodes for T1..T8, the pod sitting on the current one."""
    node = (0, 1, 2, 3, 4, 5, 6, 6, 7)[i]
    st = (0, 1, 2, 3, 4, 5, 5, 6, 7)[i]
    R(0, VT, 240, 12, (6, 8, 20))
    T(noun, 4, 22, accent)
    xs = [52 + n * 25 for n in range(8)]
    lcd.hline(xs[0], 26, xs[7] - xs[0], color(50, 56, 80))
    lcd.hline(xs[0], 26, xs[node] - xs[0], color(*accent))
    for n, x in enumerate(xs):
        c = (255, 70, 60) if n == 6 else accent
        if n < node:
            R(x - 1, 25, 3, 3, c)
        elif n > node:
            R(x - 1, 25, 3, 3, (60, 66, 90))
    pod(xs[node], 26, st, 24, 9)


# ------------------------------------------------------------------ the box

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


def box(accent, who, story, facts, red=False, hold=None, hint="A next     Y back    X facts"):
    R(0, VB, 240, 240 - VB, (10, 12, 26))
    R(0, VB, 240, 2, (255, 60, 60) if red else accent)
    T(who, 6, 171, (255, 120, 120) if red else accent)
    T(story[0], 6, 182, (245, 245, 245))
    T(story[1], 6, 192, (245, 245, 245))
    lcd.hline(6, 203, 228, color(60, 70, 100))
    T(facts[0], 6, 207, (140, 165, 205))
    T(facts[1], 6, 217, (140, 165, 205))
    if hold is not None:
        R(6, 228, 228, 9, (40, 10, 14))
        R(6, 228, int(228 * hold), 9, (230, 40, 40))
        lcd.rect(6, 228, 228, 9, color(255, 120, 120))
        CT("HOLD A", 229, (255, 255, 255))
    else:
        T(hint, 6, 229, (110, 118, 140))


def head(title, right, accent, red=False):
    R(0, 0, 240, VT, (110, 14, 20) if red else mix(accent, (0, 0, 0), .72))
    T(title, 6, 6, (255, 235, 235) if red else (255, 255, 255))
    T(right, 240 - 6 - 8 * len(right), 6, (255, 200, 200) if red else accent)


# ------------------------------------------------------------------ shared: the sealing press

def press(sealed, pal):
    """pal: (frame, ram, light_on, bed, panel). Ram hangs over the pod before, is raised after."""
    frame_c, ram_c, lamp, bed_c, panel_c = pal
    R(70, 40, 10, 88, frame_c)
    R(160, 40, 10, 88, frame_c)
    R(70, 40, 100, 14, frame_c)
    R(70, 40, 100, 3, mix(frame_c, (255, 255, 255), .3))
    ry = 46 if sealed else 62
    R(118, 54, 4, ry - 50, mix(frame_c, (0, 0, 0), .3))
    R(96, ry, 48, 24, ram_c)
    R(96, ry, 48, 3, mix(ram_c, (255, 255, 255), .35))
    for k in range(0, 48, 8):
        R(96 + k, ry + 20, 4, 4, (240, 200, 40))
        R(100 + k, ry + 20, 4, 4, (20, 20, 24))
    T("SEAL", 108, ry + 8, (20, 24, 36))
    R(84, 120, 72, 10, bed_c)
    R(84, 120, 72, 2, mix(bed_c, (255, 255, 255), .3))
    lc = (60, 255, 140) if sealed else (255, 50, 40)
    for x in (75, 165):
        E(x, 62, 5, 5, mix(lc, (0, 0, 0), .55))
        E(x, 62, 3, 3, lc)
    if sealed:                                    # steam and sparks
        for (dx, dy, r) in ((-18, -8, 5), (-8, -18, 6), (10, -14, 5), (20, -6, 4), (0, -28, 5)):
            E(120 + dx, 92 + dy, r, r, (200, 206, 220))
        for (dx, dy) in ((-30, -4), (32, -10), (-24, -20), (26, -22)):
            R(120 + dx, 96 + dy, 2, 2, (255, 220, 120))


# ------------------------------------------------------------------ theme 1: VESPER

CREAM, TEAL, NAVY, CORAL = (234, 230, 216), (44, 160, 170), (24, 40, 84), (240, 112, 92)
VACC = (110, 226, 232)


def logo_v(x, y, r, c=GOLD):
    E(x, y, r, r, c, False)
    k = r // 3
    P([(x, y - r + 2), (x + k, y - k), (x + r - 2, y), (x + k, y + k), (x, y + r - 2), (x - k, y + k),
       (x - r + 2, y), (x - k, y - k)], c)


def liner(win=None):
    R(0, VT, 240, 108, CREAM)
    R(0, 32, 240, 4, (250, 248, 240))
    for x in range(0, 240, 48):
        lcd.vline(x, 36, 64, color(*mix(CREAM, (0, 0, 0), .12)))
    R(0, 100, 240, 28, TEAL)
    R(0, 100, 240, 2, mix(TEAL, (255, 255, 255), .4))
    R(0, 128, 240, VB - 128, (176, 198, 214))
    for x in range(0, 240, 20):
        lcd.vline(x, 128, VB - 128, color(150, 176, 196))
    for y in range(140, VB, 12):
        lcd.hline(0, y, 240, color(150, 176, 196))
    R(0, 128, 240, 3, CORAL)
    if win:
        wx, ww = win
        R(wx - 3, 42, ww + 6, 54, (250, 248, 240))
        R(wx, 45, ww, 48, (6, 8, 26))
        stars(45, 93, 16, wx)
        E(wx + ww - 16, 78, 12, 12, (70, 130, 190))
        E(wx + ww - 19, 74, 6, 4, (140, 190, 230), False)


def rbot(x, y, s=2, lens=(80, 230, 220), arm_up=False):
    def r(a, b, w, h, c):
        R(x + a * s, y + b * s, w * s, h * s, c)
    r(3, 0, 2, 1, (170, 176, 190))
    E(x + 4 * s, y + 4 * s, 4 * s, 3 * s, (240, 240, 246))
    E(x + 4 * s, y + 4 * s, 2 * s + 1, 2 * s, (18, 26, 56))
    E(x + 4 * s, y + 4 * s, s, s, lens)
    E(x + 4 * s + s, y + 3 * s, max(1, s // 2), max(1, s // 2), (255, 255, 255))
    E(x + 4 * s, y + 10 * s, 3 * s, 4 * s, (236, 236, 244))
    r(3, 9, 2, 2, TEAL)
    if arm_up:
        r(-1, 3, 1, 5, (236, 236, 244))
    else:
        r(0, 8, 1, 4, (236, 236, 244))
    r(7, 8, 1, 4, (236, 236, 244))
    r(2, 14, 4, 2, (90, 100, 126))


def hero_space(x, y, s=2):
    def r(a, b, w, h, c):
        R(x + a * s, y + b * s, w * s, h * s, c)
    r(2, 11, 2, 4, (200, 206, 220))
    r(4, 11, 2, 4, (200, 206, 220))
    r(2, 15, 2, 1, (60, 66, 90))
    r(4, 15, 2, 1, (60, 66, 90))
    r(1, 5, 6, 6, (236, 240, 248))
    r(0, 5, 1, 5, (236, 240, 248))
    r(7, 5, 1, 5, (236, 240, 248))
    r(3, 6, 2, 2, CORAL)
    E(x + 4 * s, y + 2 * s + s // 2, 4 * s, 4 * s, (236, 240, 248))
    E(x + 4 * s, y + 2 * s + s // 2, 3 * s, 3 * s - 1, (28, 52, 110))
    R(x + 3 * s, y + s, s, s, (150, 190, 255))


def sign(x, y, w, text, c=GOLD, bg=NAVY):
    y = max(y, 36)
    R(x, y, w, 10, bg)
    lcd.rect(x, y, w, 10, color(*c))
    T(text, x + (w - 8 * len(text)) // 2, y + 1, c)


def v0():
    liner()
    R(96, 44, 48, 84, (250, 248, 240))
    R(102, 52, 36, 76, (30, 70, 110))
    E(120, 52, 18, 8, (30, 70, 110))
    for k in range(4):
        R(104 + k * 8, 62 + k * 3, 4, 60, (44, 100, 150))
    sign(88, 34, 64, "BOARDING")
    logo_v(36, 64, 11)
    T("VESPER", 12, 80, NAVY)
    logo_v(204, 64, 11)
    T("VESPER", 180, 80, NAVY)
    rbot(52, 96, 2)
    for k in range(5):
        L(70, 102, 156, 100 + k * 6, mix((20, 90, 70), (100, 255, 170), k / 4))
    hero_space(160, 96)
    R(64, 122, 34, 3, STEEL)
    pod(82, 114, 0, 34, 14)


def v1():
    liner()
    sign(90, 34, 60, "FAB BAY")
    R(78, 50, 84, 80, (150, 210, 226))
    R(82, 54, 76, 72, (8, 22, 50))
    E(120, 54, 38, 6, (150, 210, 226))
    for k in range(7):
        lcd.pixel(92 + k * 9, 58 + (k * 13) % 50, color(120, 200, 255))
    L(94, 50, 108, 84, (232, 238, 246))
    L(95, 50, 109, 84, (232, 238, 246))
    L(146, 50, 132, 84, (232, 238, 246))
    L(145, 50, 131, 84, (232, 238, 246))
    E(120, 92, 36, 16, mix((8, 22, 50), (60, 220, 220), .35), False)
    pod(120, 92, 1)
    for (sx, sy) in ((94, 80), (146, 78), (110, 110), (132, 108)):
        R(sx, sy, 2, 2, (200, 255, 255))
    hero_space(28, 96)
    rbot(178, 96, 2)
    R(170, 118, 44, 10, (90, 110, 140))
    for k in range(4):
        R(174 + k * 10, 121, 5, 3, (60, 255, 150) if k % 2 else (255, 190, 60))


def v2():
    liner()
    sign(94, 34, 52, "QC LINE")
    R(0, 116, 240, 12, (50, 56, 74))
    for x in range(0, 240, 16):
        P([(x, 118), (x + 6, 122), (x, 126)], (90, 100, 130), False)
    for gx in (64, 150):
        R(gx, 60, 6, 56, TEAL)
        R(gx + 30, 60, 6, 56, TEAL)
        R(gx, 56, 36, 6, TEAL)
        R(gx + 8, 62, 20, 54, mix(CREAM, GREEN, .35))
        E(gx + 18, 50, 5, 5, mix(GREEN, (0, 0, 0), .5))
        E(gx + 18, 50, 3, 3, GREEN)
    pod(120, 105, 2, 44, 18)
    hero_space(14, 96)
    rbot(196, 96, 2, lens=(255, 190, 80))


def v3():
    liner()
    sign(84, 34, 72, "ASSURANCE")
    logo_v(36, 62, 11)
    logo_v(204, 62, 11)
    R(60, 112, 120, 16, (150, 110, 80))
    R(60, 112, 120, 3, (190, 150, 110))
    R(126, 47, 8, 23, STEEL)
    R(122, 68, 16, 4, (110, 120, 146))
    R(112, 72, 36, 10, GOLD)
    R(112, 72, 36, 2, (255, 230, 150))
    for k in range(5):
        L(118 + k * 6, 84, 118 + k * 6 + (k - 2), 92, mix((60, 60, 20), GOLD, .7))
    pod(120, 102, 3, 56, 22)
    hero_space(24, 96)
    rbot(196, 96, 2, lens=(255, 200, 90))


def v4():
    liner()
    sign(88, 33, 64, "ID PLATE")
    R(68, 48, 104, 58, (150, 210, 226))
    R(72, 52, 96, 50, (10, 16, 36))
    blockies.draw(lcd, OWNER, 104, 55, 4)
    T("0x7a3f..a391", 76, 91, GOLD)
    R(100, 120, 40, 8, STEEL)
    pod(120, 110, 4, 56, 22)
    hero_space(22, 96)
    rbot(190, 96, 2)


def v5():
    liner()
    sign(88, 34, 64, "RECORDS")
    for r_ in range(3):
        for c_ in range(5):
            x, y = 22 + c_ * 42, 46 + r_ * 20
            hot = r_ == 1 and c_ in (1, 3)
            R(x, y, 40, 16, mix(TEAL, (255, 255, 255), .35) if hot else (196, 204, 214))
            R(x, y, 40, 16, GOLD, False) if False else None
            lcd.rect(x, y, 40, 16, color(120, 140, 160))
            R(x + 15, y + 12, 10, 2, (90, 100, 120))
            if hot:
                T("F1D0" if c_ == 1 else "F1D1", x + 4, y + 3, NAVY)
    pod(120, 108, 5, 56, 22)
    hero_space(14, 96)
    rbot(200, 96, 2)


def v6():
    liner()
    press(False, ((96, 108, 136), (170, 180, 200), (255, 50, 40), (70, 76, 96), (70, 80, 104)))
    pod(120, 108, 5)
    hero_space(14, 96)
    R(40, 108, 26, 20, (70, 80, 104))
    E(53, 112, 5, 5, (255, 40, 40))
    P([(40, 106), (66, 106), (62, 100), (44, 100)], (240, 200, 40))
    rbot(196, 96, 2)


def v7():
    liner()
    press(True, ((96, 108, 136), (170, 180, 200), (60, 255, 140), (70, 76, 96), (70, 80, 104)))
    pod(120, 108, 6)
    hero_space(14, 96)
    R(172, 52, 60, 28, (8, 40, 30))
    lcd.rect(172, 52, 60, 28, color(*GREEN))
    T("SEALED", 182, 58, GREEN)
    T("LOCKED", 182, 68, GOLD)
    R(40, 108, 26, 20, (70, 80, 104))
    E(53, 112, 5, 5, GREEN)
    rbot(196, 96, 2, arm_up=True)


def v8():
    liner(win=(20, 60))
    sign(68, 34, 112, "WELCOME ABOARD")
    R(96, 48, 48, 80, (250, 248, 240))
    R(102, 54, 36, 74, (120, 210, 200))
    logo_v(204, 64, 11)
    T("VESPER", 180, 80, NAVY)
    rbot(60, 96, 2, arm_up=True)
    hero_space(146, 96)
    R(126, 106, 18, 12, (60, 70, 96))
    R(130, 108, 10, 3, (10, 14, 30))
    pod(135, 92, 7, 40, 16)


def title_v():
    R(0, VT, 240, 220, (4, 6, 22))
    stars(VT, 240, 90, 21)
    E(200, 210, 80, 80, (40, 90, 150))
    E(196, 206, 70, 70, (60, 120, 180))
    logo_v(120, 68, 30)
    BT("VESPER", 48, 104, CREAM, 3)
    CT("ASSURANCE LINE", 134, VACC)
    CT("we keep what matters", 150, GOLD)


def legend(names, accent):
    R(0, VT, 240, 146, (8, 10, 24))
    for k in range(9):
        cx, cy = 42 + (k % 3) * 78, 46 + (k // 3) * 36 + (4 if k >= 6 else 0)
        if k == 8:
            T("one pod,", cx - 32, cy - 6, accent)
            T("8 stops", cx - 28, cy + 6, accent)
            continue
        pod(cx, cy, k, 56, 22)
        T(names[k], cx - 4 * len(names[k]), cy + 24 if k >= 5 else cy + 15, (200, 210, 230))


def end_legend_v():
    legend(("T1 unmade", "T2 made", "T3 tested", "T4 marked", "T5 named", "T6 filed", "T7 SEALED", "T8 seated"), VACC)


VESPER = {
    "name": "VESPER", "accent": VACC, "noun": "POD",
    "scenes": (title_v, v0, v1, v2, v3, v4, v5, v6, v7, v8, end_legend_v),
    "text": (
        ("VESPER BOARDING", "VESPER ASSURANCE LINE", ("Eight stops to seal a keypod.", "Nothing is hidden."),
         ("the real Trust M ceremony", "T1 to T8, steps unchanged")),
        ("T1  BOARDING CHECK", "GATE-BOT 7  (Infineon)", ("Welcome aboard. Checking the", "maker's hallmark... genuine."), None),
        ("T2  THE FAB BAY", "FAB BAY  (the chip)", ("Your pod is grown in here.", "It never leaves this bay."), None),
        ("T3  QUALITY CONTROL", "QC-BOT", ("Two checks down the line.", "The pod must pass both."), None),
        ("T4  ASSURANCE DESK", "ASSURANCE  (key E0F0)", ("Hallmark applied: this pod", "lives in this chip."), None),
        ("T5  YOUR ID PLATE", "PURSER-BOT", ("Your plate comes from your", "address. Match the terminal."), None),
        ("T6  THE RECORDS BAY", "ARCHIVIST", ("Two entries: your record and", "the maker's bond."), None),
        ("T7  THE SEALING PRESS", "VAULT MASTER", ("Last chance. Once pressed,", "the pod can't be re-made."), None),
        ("T7  POD SEALED", "VAULT MASTER", ("Sealed. It still signs, but", "can never be re-made."), None),
        ("T8  WELCOME ABOARD", "GATE-BOT 7", ("Your sealed pod is seated.", "Vesper keeps what matters."), None),
        ("THE POD'S JOURNEY", "THE SAME POD, EVERY SCREEN", ("Its shell shows what's done:", "silver + lock = sealed."),
         ("one pod, one shell per step", "the rail shows where it is")),
    ),
}

# ------------------------------------------------------------------ theme 2: SABLE LANTERN

MAG, CYA, AMB, NIGHT = (255, 60, 170), (60, 230, 255), (255, 180, 60), (10, 8, 30)
SACC = (255, 100, 200)


def neon(x, y, w, h, c, text=None, bg=NIGHT):
    R(x - 2, y - 2, w + 4, h + 4, mix(bg, c, .22))
    R(x, y, w, h, bg)
    lcd.rect(x, y, w, h, color(*c))
    lcd.rect(x + 1, y + 1, w - 2, h - 2, color(*mix(c, bg, .55)))
    if text:
        T(text, x + (w - 8 * len(text)) // 2, y + (h - 8) // 2, c)


def lantern(x, y, c=MAG, s=1):
    lcd.vline(x, y - 12 * s, 3 * s, color(*c))
    R(x - 4 * s, y - 9 * s, 8 * s, 2 * s, c)
    body = [(x - 4 * s, y - 7 * s), (x + 4 * s, y - 7 * s), (x + 6 * s, y), (x + 4 * s, y + 6 * s),
            (x - 4 * s, y + 6 * s), (x - 6 * s, y)]
    P(body, mix(NIGHT, c, .25))
    P(body, c, False)
    E(x, y, max(1, s), 2 * s, AMB)
    E(x, y - s, max(1, s // 2), max(1, s), (255, 240, 190))
    R(x - 4 * s, y + 6 * s, 8 * s, 2 * s, c)


def night_sky():
    grad(VT, 112, (8, 6, 26), (74, 20, 88))


def skyline(seed, base, hmin, hmax, col):
    x, s = 0, seed
    while x < 240:
        s = lcg(s)
        w = 14 + (s >> 8) % 22
        s = lcg(s)
        h = hmin + (s >> 8) % (hmax - hmin)
        R(x, base - h, w, h, col)
        for wy in range(base - h + 4, base - 3, 6):
            for wx in range(x + 3, x + w - 3, 5):
                s = lcg(s)
                if (s >> 10) % 5 == 0:
                    R(wx, wy, 2, 3, (AMB, CYA, MAG)[(s >> 14) % 3] if (s >> 12) % 3 else AMB)
        x += w + ((s >> 6) % 3)


def rain(n=70, seed=3):
    s = seed
    for k in range(n):
        s = lcg(s)
        x = (s >> 8) % 250
        s = lcg(s)
        y = VT + 12 + (s >> 8) % (VB - VT - 20)
        L(x, y, x - 2, y + 6, (72, 92, 134))


def wet(y0=128, streaks=((40, MAG), (100, CYA), (170, AMB), (214, MAG))):
    R(0, y0, 240, VB - y0, (12, 12, 26))
    lcd.hline(0, y0, 240, color(50, 46, 80))
    for (x, c) in streaks:
        for k in range(0, VB - y0 - 2, 3):
            R(x, y0 + 3 + k, 2, 2, mix((12, 12, 26), c, .55 - k / 90))


def punk(x, y, s=2):
    def r(a, b, w, h, c):
        R(x + a * s, y + b * s, w * s, h * s, c)
    r(2, 11, 2, 4, (20, 20, 34))
    r(4, 11, 2, 4, (20, 20, 34))
    r(2, 15, 2, 1, MAG)
    r(4, 15, 2, 1, MAG)
    r(1, 5, 6, 7, (30, 30, 52))
    r(0, 5, 1, 6, (30, 30, 52))
    r(7, 5, 1, 6, (30, 30, 52))
    r(1, 5, 6, 1, MAG)
    r(2, 1, 4, 4, (226, 178, 150))
    r(2, 0, 4, 2, (16, 16, 28))
    r(1, 1, 1, 3, (16, 16, 28))
    r(2, 3, 4, 1, CYA)


def android(x, y, s=2, eye=AMB):
    def r(a, b, w, h, c):
        R(x + a * s, y + b * s, w * s, h * s, c)
    r(2, 11, 2, 4, (30, 30, 50))
    r(4, 11, 2, 4, (30, 30, 50))
    r(1, 5, 6, 6, (44, 44, 76))
    r(0, 5, 1, 5, (44, 44, 76))
    r(7, 5, 1, 5, (44, 44, 76))
    r(3, 6, 2, 1, eye)
    r(2, 1, 4, 4, (208, 218, 236))
    r(2, 0, 4, 1, (30, 30, 50))
    r(3, 3, 1, 1, eye)
    r(5, 3, 1, 1, eye)


def drone(x, y, s=2, lens=(255, 60, 90)):
    E(x + 4 * s, y + 4 * s, 4 * s, 3 * s, (72, 78, 104))
    E(x + 4 * s, y + 3 * s, 3 * s, 2 * s, (96, 104, 134))
    E(x + 4 * s, y + 4 * s, 2 * s, 2 * s, (10, 10, 20))
    E(x + 4 * s, y + 4 * s, s, s, lens)
    R(x + 2 * s, y + 7 * s, 4 * s, s, mix(CYA, NIGHT, .35))
    R(x + 3 * s, y + 8 * s, 2 * s, s, mix(CYA, NIGHT, .6))
    R(x + 4 * s, y - 2 * s, 1, 2 * s, (120, 128, 150))


def bricks_dark(y0, y1, base=(22, 16, 38), line=(34, 26, 56)):
    R(0, y0, 240, y1 - y0, base)
    for i, y in enumerate(range(y0, y1, 8)):
        lcd.hline(0, y, 240, color(*line))
        for x in range(8 if i % 2 else 0, 240, 16):
            lcd.vline(x, y, 8, color(*line))


def s0():
    night_sky()
    skyline(3, 112, 30, 70, (14, 10, 34))
    skyline(9, 116, 10, 34, (26, 16, 52))
    neon(62, 36, 116, 14, MAG, "SABLE LANTERN")
    lantern(46, 46, MAG)
    lantern(194, 46, MAG)
    wet()
    R(6, 84, 46, 44, (24, 22, 44))
    R(12, 90, 34, 18, (14, 58, 78))
    lcd.rect(12, 90, 34, 18, color(*CYA))
    R(24, 96, 10, 12, (20, 20, 34))
    for k in range(0, 64, 8):
        R(52 + k, 108, 4, 4, (236, 236, 240))
        R(56 + k, 108, 4, 4, (220, 40, 70))
    drone(90, 72, 2)
    for k in range(5):
        L(106, 92, 168, 96 + k * 6, mix(NIGHT, CYA, .3 + k * .12))
    pod(98, 106, 0, 34, 14)
    punk(156, 96)
    rain()


def s1():
    R(0, VT, 240, 108, (14, 24, 34))
    R(0, 44, 240, 4, (40, 60, 72))
    R(14, 44, 6, 84, (40, 60, 72))
    R(222, 44, 6, 84, (40, 60, 72))
    R(0, 128, 240, VB - 128, (10, 14, 22))
    lcd.hline(0, 128, 240, color(60, 90, 100))
    neon(6, 52, 68, 14, CYA, "COLD LAB")
    R(76, 42, 88, 90, (70, 110, 120))
    R(80, 46, 80, 82, (6, 62, 66))
    R(80, 46, 80, 10, (12, 100, 104))
    for (bx, by, br) in ((92, 110, 3), (100, 96, 2), (148, 104, 3), (140, 82, 2), (96, 70, 2), (152, 62, 2)):
        E(bx, by, br, br, (120, 230, 220), False)
    R(72, 130, 96, 6, (40, 60, 72))
    for k in (100, 134):
        R(k, 34, 4, 12, (40, 60, 72))
    E(120, 88, 34, 16, mix((6, 62, 66), CYA, .3), False)
    pod(120, 88, 1)
    drone(188, 86, 2, lens=CYA)
    punk(28, 96)
    for (sx, sy) in ((110, 74), (136, 100), (128, 70)):
        R(sx, sy, 2, 2, (200, 255, 250))


def s2():
    night_sky()
    skyline(5, 128, 30, 84, (12, 8, 30))
    skyline(11, 128, 12, 44, (26, 14, 52))
    R(30, 60, 14, 68, (22, 18, 48))
    R(35, 44, 4, 16, (60, 56, 96))
    for (ly, lc) in ((42, GREEN), (66, GREEN)):
        E(37, ly, 4, 4, mix(NIGHT, lc, .4))
        E(37, ly, 2, 2, lc)
    R(0, 128, 240, VB - 128, (18, 16, 36))
    R(0, 124, 240, 5, (44, 40, 76))
    for t_ in range(1, 12):
        px = 150 + (40 - 150) * t_ // 12
        E(px, 98 + (44 - 98) * t_ // 12, 1, 1, CYA)
        E(px, 108 + (66 - 108) * t_ // 12, 1, 1, MAG)
    R(196, 84, 34, 44, (26, 22, 52))
    R(202, 92, 22, 14, (14, 58, 78))
    R(208, 96, 8, 10, (60, 60, 96))
    lcd.rect(202, 92, 22, 14, color(*CYA))
    punk(146, 96)
    R(162, 100, 16, 9, (60, 70, 96))
    pod(170, 84, 2, 38, 15)
    rain(40)


def s3():
    bricks_dark(VT, 128)
    neon(84, 36, 72, 14, AMB, "NOTARY")
    neon(12, 56, 34, 40, MAG)
    neon(194, 56, 34, 40, CYA)
    for k in range(3):
        R(18, 62 + k * 10, 22, 4, mix(NIGHT, MAG, .6))
        R(200, 62 + k * 10, 22, 4, mix(NIGHT, CYA, .6))
    wet()
    lcd.rect(60, 58, 120, 46, color(70, 60, 110))
    android(70, 68, 2)
    for k, w in enumerate((30, 24, 18)):
        E(122, 62 + k * 8, w, 4, mix(NIGHT, GOLD, .55 + k * .15), False)
    R(56, 104, 128, 24, (38, 30, 60))
    R(56, 104, 128, 3, AMB)
    pod(120, 93, 3)
    punk(200, 96)


def s4():
    bricks_dark(VT, 128, (16, 10, 30), (26, 18, 46))
    neon(58, 38, 124, 78, MAG)
    blockies.draw(lcd, OWNER, 92, 46, 7)
    R(58, 124, 124, 4, (60, 44, 96))
    wet()
    pod(120, 112, 4)
    drone(196, 66, 2, lens=MAG)
    for k in range(4):
        L(198, 88, 184, 68 + k * 8, mix(NIGHT, (MAG, CYA)[k % 2], .8))
    punk(20, 96)


def s5():
    R(0, VT, 240, 108, (12, 16, 28))
    neon(90, 34, 60, 12, CYA, "STACKS")
    for r_ in range(3):
        for c_ in range(5):
            x, y = 20 + c_ * 42, 50 + r_ * 20
            hot = r_ == 1 and c_ in (1, 3)
            R(x, y, 40, 16, mix((30, 40, 60), CYA, .35) if hot else (30, 40, 60))
            lcd.rect(x, y, 40, 16, color(*(CYA if hot else (60, 76, 104))))
            R(x + 33, y + 3, 3, 3, GREEN if (r_ + c_) % 2 else AMB)
            if hot:
                T("F1D0" if c_ == 1 else "F1D1", x + 4, y + 4, (230, 250, 255))
    wet()
    R(60, 116, 120, 12, (38, 30, 60))
    R(60, 116, 120, 3, CYA)
    pod(120, 105, 5)
    android(200, 86, 2)
    for x in range(192, 232, 6):
        lcd.vline(x, 84, 44, color(90, 96, 130))
    punk(14, 96)


def s6():
    R(0, VT, 240, 108, (16, 14, 30))
    R(176, 46, 46, 42, (60, 70, 96))
    R(180, 50, 38, 34, (8, 6, 24))
    R(181, 66, 6, 18, (40, 20, 70))
    R(190, 58, 8, 26, (20, 40, 80))
    R(202, 64, 10, 20, (60, 20, 70))
    lcd.rect(180, 50, 38, 34, color(*CYA))
    wet()
    press(False, ((60, 70, 96), (120, 132, 154), (255, 50, 40), (50, 56, 76), (60, 70, 96)))
    pod(120, 108, 5)
    drone(20, 84, 2, lens=AMB)
    punk(184, 96)
    R(174, 104, 4, 24, STEEL)
    E(176, 102, 5, 5, (255, 40, 60))
    rain(30)


def s7():
    R(0, VT, 240, 108, (16, 14, 30))
    neon(174, 46, 54, 14, GREEN, "SEALED")
    wet()
    press(True, ((60, 70, 96), (120, 132, 154), (60, 255, 140), (50, 56, 76), (60, 70, 96)))
    pod(120, 108, 6)
    drone(20, 84, 2, lens=GREEN)
    punk(184, 96)
    R(174, 104, 4, 24, STEEL)
    E(176, 102, 5, 5, GREEN)
    rain(30)


def s8():
    grad(VT, 124, (26, 10, 64), (255, 124, 130))
    E(120, 122, 60, 24, (255, 196, 150))
    skyline(7, 128, 24, 64, (32, 14, 54))
    skyline(2, 130, 8, 32, (50, 20, 70))
    R(0, 128, 240, VB - 128, (22, 18, 40))
    R(0, 124, 240, 5, (50, 44, 84))
    neon(146, 38, 76, 14, GREEN, "SIGNED IN")
    lantern(46, 52, MAG)
    drone(50, 88, 2, lens=CYA)
    punk(108, 96)
    R(128, 106, 18, 12, (60, 70, 96))
    R(132, 108, 10, 3, (10, 14, 30))
    pod(137, 92, 7, 40, 16)


def title_s():
    night_sky()
    skyline(3, 150, 40, 90, (14, 10, 34))
    skyline(9, 156, 14, 44, (26, 16, 52))
    lantern(120, 62, MAG, 3)
    BT("SABLE LANTERN", 16, 104, (250, 240, 250), 2)
    CT("REGISTRY & NOTARY", 130, CYA)
    CT("every key gets a witness", 146, AMB)
    rain(60)


def end_legend_s():
    legend(("T1 unmade", "T2 made", "T3 tested", "T4 marked", "T5 named", "T6 filed", "T7 SEALED", "T8 seated"), SACC)


SABLE = {
    "name": "SABLE LANTERN", "accent": SACC, "noun": "VIAL",
    "scenes": (title_s, s0, s1, s2, s3, s4, s5, s6, s7, s8, end_legend_s),
    "text": (
        ("LANTERN INTAKE", "SABLE LANTERN REGISTRY", ("Eight stops to seal a vial.", "Nothing is hidden."),
         ("the real Trust M ceremony", "T1 to T8, steps unchanged")),
        ("T1  CHECKPOINT", "GATE DRONE  (Infineon)", ("Halt. Maker's hallmark on", "your chip... genuine."), None),
        ("T2  THE COLD LAB", "THE VAT  (the chip)", ("Your vial is grown in here.", "It never leaves the glass."), None),
        ("T3  ROOFTOP PING", "RELAY OPERATOR", ("Ping the tower twice. It", "must answer both times."), None),
        ("T4  THE NOTARY", "NOTARY  (factory key E0F0)", ("Hallmark notarised: this", "vial lives in this chip."), None),
        ("T5  YOUR NEON GLYPH", "SIGN-PAINTER", ("Your glyph, drawn from your", "address. Match the terminal."), None),
        ("T6  THE STACKS", "CLERK", ("Two files: your record and", "the maker's bond."), None),
        ("T7  THE RESIN PRESS", "PRESS TECH", ("Last chance. Once pressed,", "the vial can't be re-made."), None),
        ("T7  VIAL SEALED", "PRESS TECH", ("Sealed. It still signs, but", "can never be re-made."), None),
        ("T8  SIGNED IN", "GATE DRONE", ("Sealed vial seated. Welcome", "to the Lantern, signer."), None),
        ("THE VIAL'S JOURNEY", "THE SAME VIAL, EVERY SCREEN", ("Its shell shows what's done:", "silver + lock = sealed."),
         ("one vial, one shell per step", "the rail shows where it is")),
    ),
}


THEMES = [VESPER, SABLE]

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


def _draw(t, j):
    th = THEMES[t]
    lcd.fill(0)
    th["scenes"][j]()
    title, who, story, fx = th["text"][j]
    step = j - 1                      # 0..8 for the steps; -1 and 9 are the two cards
    red = step in (6, 7)
    if 0 <= step <= 8:
        rail(step, th["accent"], th["noun"])
        head(title, "%d/9" % (step + 1), th["accent"], red)
        box(th["accent"], who, story, FACTS[step], red, 0.62 if step == 6 else None,
            "A continue         X facts" if step == 7 else "A next     Y back    X facts")
    else:
        head(title, "", th["accent"])
        box(th["accent"], who, story, fx, hint="A next     Y back")
    lcd.show()


def show(t, j):
    lcd.frames(_draw, t, j)


def check():
    for th in THEMES:
        for (title, who, story, fx) in th["text"]:
            for s in (who,) + tuple(story) + (fx or ()):
                if len(s) > 28:
                    print("TOO LONG", len(s), s)
            if len(title) > 26:
                print("TITLE LONG", len(title), title)
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
            if 1 <= cur[1] <= 9:
                cur[2] = not cur[2]
                (facts(cur[1] - 1) if cur[2] else show(cur[0], cur[1]))
            continue
        cur[2] = False
        if k == "right":
            cur[1] = (cur[1] + 1) % 11
        elif k == "left":
            cur[1] = (cur[1] - 1) % 11
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
    from machine import Timer as _T
    timer = _T(period=60, mode=_T.PERIODIC, callback=tick)
    print("keyjourney: left/right screen, up/down theme, X facts, B quits")


def stop():
    if timer:
        timer.deinit()


start()
