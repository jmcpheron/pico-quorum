# Four directions for the cosigner's screens, the same four screens in each, so they can be compared:
# a control change from unknown code (the warning), a routine payment, holding to sign, and home.
#   A terminal     the built-in 8x8 font on an 8 px grid, pixel icons, coloured bands
#   B instrument   IBM Plex on graphite, hairlines, colour only for meaning
#   C annunciator  a cockpit's alert grammar: mono capitals on black, red/amber/cyan/green
#   D statement    light paper, Inter, one plain sentence a page, the details under it
# Controls in all four: turn = pages, push = open / leave (nothing sent), footswitch = sign, held.
# There is no Reject: a cosigner can only not sign. A design study for docs/quorum-ui/v3/DIRECTIONS.md:
# it reads no chip, asks no service and signs nothing. The transactions are made up.
#   tools/emu run ui_directions      then turn or press A for the next screen
#   node emu/render-cosigner-ui.mjs ui_directions docs/quorum-ui/v3/directions build1-2.4
import framebuf
import fonts as F
import lcd as L

W, H = L.W, L.H
WIDE = W >= 300
lcd = None


def col(rgb):
    return L.color(*rgb)


def wrap(s, w, font):
    return F.wrap(s, w, font)


def rrect(d, x, y, w, h, r, rgb):
    """A filled rectangle with round corners (framebuf has none)."""
    c = col(rgb)
    d.fill_rect(x + r, y, w - 2 * r, h, c)
    d.fill_rect(x, y + r, w, h - 2 * r, c)
    for cx, cy, q in ((x + r, y + r, 2), (x + w - r - 1, y + r, 1), (x + r, y + h - r - 1, 4), (x + w - r - 1, y + h - r - 1, 8)):
        d.ellipse(cx, cy, r, r, c, True, q)


# The made-up transactions, shared by all four
SAFE, NET = "Family Safe", "Base"
MODULE = ("0xC0FF EE25 .. 9D54 4979", "0xC0FF..4979")
CAROL = ("0x8F2A 03D1 .. 6B0E 11C4", "0x8F2A..11C4")
HASH = ("5A3C 1F07 .. 77D2 9E21", "5A3C..9E21")


def pick(pair):
    return pair[0] if WIDE else pair[1]


# ==== A: terminal ===================================================================================
class A:
    BG, PANEL, RULE = (24, 20, 37), (38, 32, 60), (66, 58, 100)
    INK, MUTED, DIM = (250, 240, 215), (150, 142, 180), (96, 90, 128)
    AMBER, GREEN, BLUE, RED = (247, 168, 52), (96, 206, 108), (110, 156, 240), (238, 84, 100)
    BANDS = {"red": ((96, 26, 46), RED), "green": ((24, 72, 50), GREEN), "blue": ((30, 40, 96), BLUE)}
    ICONS = {"warn": (0x18, 0x3C, 0x24, 0x66, 0x66, 0xFF, 0xE7, 0xFF), "ok": (0x00, 0x01, 0x03, 0x86, 0xCC, 0x78, 0x30, 0x00),
             "info": (0x18, 0x18, 0x00, 0x38, 0x18, 0x18, 0x3C, 0x00), "lock": (0x18, 0x24, 0x24, 0x7E, 0x7E, 0x66, 0x7E, 0x7E),
             "knob": (0x3C, 0x66, 0xE7, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C), "push": (0x3C, 0x42, 0x99, 0xBD, 0xBD, 0x99, 0x42, 0x3C),
             "foot": (0x00, 0x18, 0x3C, 0x3C, 0x18, 0x7E, 0xFF, 0xFF)}
    _sp = {}

    @classmethod
    def t(cls, d, s, x, y, rgb, scale=1):
        if scale == 1:
            d.text(s, x, y, col(rgb))
            return
        if s not in cls._sp:
            fb = framebuf.FrameBuffer(bytearray(len(s) * 8), len(s) * 8, 8, framebuf.MONO_HLSB)
            fb.text(s, 0, 0, 1)
            cls._sp[s] = [(i, j) for j in range(8) for i in range(len(s) * 8) if fb.pixel(i, j)]
        c = col(rgb)
        for i, j in cls._sp[s]:
            d.fill_rect(x + i * scale, y + j * scale, scale, scale, c)

    @classmethod
    def icon(cls, d, name, x, y, rgb, s=1):
        c = col(rgb)
        for j, row in enumerate(cls.ICONS[name]):
            for i in range(8):
                if row & (0x80 >> i):
                    d.fill_rect(x + i * s, y + j * s, s, s, c)

    @classmethod
    def frame(cls, d, left, right, band, title, sub, foot):
        d.fill(col(cls.BG))
        d.fill_rect(0, 0, W, 18, col(cls.PANEL))
        d.fill_rect(4, 3, 20, 12, col(cls.AMBER))
        cls.t(d, "PQ", 6, 5, cls.BG)
        cls.t(d, left, 30, 5, cls.INK)
        cls.t(d, right, W - 8 * len(right) - 6, 5, cls.MUTED)
        if band:
            bg, fg = cls.BANDS[band]
            d.fill_rect(0, 22, W, 34, col(bg))
            d.fill_rect(0, 22, 5, 34, col(fg))
            x = 10
            if WIDE:
                cls.icon(d, {"red": "warn", "green": "ok", "blue": "info"}[band], 12, 27, fg, 3)
                x = 44
            cls.t(d, title, x, 26, cls.INK, 2)
            cls.t(d, sub, x, 45, fg)
        d.fill_rect(0, H - 20, W, 20, col(cls.PANEL))
        x = 6
        for name, label, rgb in foot:
            cls.icon(d, name, x, H - 14, rgb)
            cls.t(d, label, x + 11, H - 14, rgb)
            x += 11 + 8 * len(label) + 10

    @classmethod
    def row(cls, d, y, label, value, rgb=None):
        cls.t(d, label, 10, y, cls.MUTED)
        cls.t(d, value, 76 if WIDE else 64, y, rgb or cls.INK)

    @classmethod
    def warn(cls, d):
        cls.frame(d, "FAMILY SAFE  N42", "1/3", "red", "TAKES CONTROL", "MOVES FUNDS WITHOUT OWNERS",
                  [("knob", "PAGES", cls.INK), ("push", "LEAVE", cls.INK), ("lock", "NO SIGN", cls.DIM)])
        cls.row(d, 66, "ACTION", "Enable a module")
        cls.row(d, 80, "MODULE", pick(MODULE))
        cls.row(d, 94, "CODE", pick(("UNKNOWN, NOT IN REGISTRY", "UNKNOWN")), cls.RED)
        cls.t(d, "EFFECT", 10, 112, cls.MUTED)
        x = 76 if WIDE else 64
        for i, ln in enumerate(cls.lines("Could move every asset with no owner signing, until removed.", (W - x - 6) // 8)):
            cls.t(d, ln, x, 112 + 11 * i, cls.INK)
        cls.row(d, 170, "FROM", "Safe service, BOB")
        cls.row(d, 184, "HASH", pick(HASH))
        cls.t(d, pick(("computed on this device", "made on this device")), x, 196, cls.DIM)

    @classmethod
    def send(cls, d):
        cls.frame(d, "FAMILY SAFE  N41", "1/2", "green", "ROUTINE", pick(("A PAYMENT TO SOMEONE YOU KNOW", "TO SOMEONE YOU KNOW")),
                  [("knob", "PAGES", cls.INK), ("push", "LEAVE", cls.INK), ("foot", "HOLD 2 S", cls.INK)])
        cls.row(d, 68, "SEND", "")
        cls.t(d, "0.05 ETH", 76 if WIDE else 64, 64, cls.INK, 2)
        cls.row(d, 90, "TO", "Carol (address book)")
        cls.row(d, 104, "", pick(CAROL), cls.MUTED)
        cls.row(d, 122, "ON", "Base")
        cls.row(d, 136, "SO FAR", "1 of 2: Alice")
        cls.row(d, 154, "CODE", "7B10-44E2")

    @classmethod
    def hold(cls, d):
        cls.frame(d, "FAMILY SAFE  N41", "SIGN", "blue", "HOLDING 1.4S", pick(("LET GO TO STOP. NOTHING SENT YET", "LET GO TO STOP")),
                  [("foot", "KEEP HOLDING", cls.BLUE)])
        n = 10
        sw = (W - 20) // n
        for i in range(n):
            d.fill_rect(10 + i * sw, 70, sw - 4, 24, col(cls.BLUE if i < 7 else cls.RULE))
        cls.row(d, 112, "SIGNS", pick(("SafeTx hash, made here", "SafeTx hash")))
        cls.row(d, 126, "", pick(HASH))
        cls.row(d, 144, "KEY", "chip 3, sealed")

    @classmethod
    def home(cls, d):
        cls.frame(d, "PICOQUORUM", "CHIP 3", None, "", "", [("knob", "SELECT", cls.INK), ("push", "OPEN", cls.INK)])
        cls.t(d, "READY", 10, 30, cls.INK, 2)
        cls.t(d, "1 TO REVIEW", W - 98, 34, cls.AMBER)
        for i, (name, sub, st, c) in enumerate((("FAMILY SAFE", "BASE  2 OF 3", "1 WAITING", cls.AMBER),
                                                ("OPS SAFE", "ETH  3 OF 5", "CLEAR", cls.GREEN))):
            y = 64 + 34 * i
            if i == 0:
                d.fill_rect(6, y - 6, W - 12, 30, col(cls.PANEL))
                d.fill_rect(6, y - 6, 3, 30, col(cls.AMBER))
            cls.t(d, name, 16, y, cls.INK)
            cls.t(d, sub, 16, y + 12, cls.MUTED)
            cls.t(d, st, W - 8 * len(st) - 14, y + 6, c)
        cls.t(d, "LAST SIGNED", 10, 146, cls.MUTED)
        cls.t(d, "0.05 ETH TO CAROL, 2 H AGO"[:(W - 20) // 8], 10, 158, cls.INK)

    @staticmethod
    def lines(s, cols):
        out, line = [], ""
        for w in s.split(" "):
            if len(line) + len(w) + (1 if line else 0) > cols:
                out.append(line)
                line = w
            else:
                line = (line + " " + w) if line else w
        return out + [line]


# ==== B: instrument =================================================================================
class B:
    FONTS = "plex"
    BG, INK, MUTED, LINE = (19, 20, 23), (236, 236, 232), (138, 141, 150), (50, 52, 58)
    RED, AMBER, GREEN, BLUE = (240, 84, 76), (240, 172, 64), (92, 200, 124), (112, 160, 255)
    M = 14

    @classmethod
    def frame(cls, d, left, right, status, rgb, hints):
        d.fill(col(cls.BG))
        F.text(d, left, cls.M, 10, "sans12", cls.MUTED, cls.BG)
        F.text(d, right, W - cls.M - F.width(right, "sans12"), 10, "sans12", cls.MUTED, cls.BG)
        if status:
            d.ellipse(cls.M + 4, 41, 4, 4, col(rgb), True)
            F.text(d, status, cls.M + 14, 32, "bold14", rgb, cls.BG)
        d.hline(cls.M, H - 30, W - 2 * cls.M, col(cls.LINE))
        x = cls.M
        for k, v, c in hints:
            x = F.text(d, k, x, H - 23, "bold14" if c else "sans12", c or cls.MUTED, cls.BG)
            x = F.text(d, " " + v, x, H - 23, "sans12", cls.MUTED, cls.BG) + (18 if WIDE else 10)

    @classmethod
    def field(cls, d, x, y, label, value, font="sans14", rgb=None, w=None):
        F.text(d, label, x, y, "sans12", cls.MUTED, cls.BG)
        for i, ln in enumerate(wrap(value, w or (W - x - cls.M), font)):
            F.text(d, ln, x, y + 16 + 19 * i, font, rgb or cls.INK, cls.BG)
        return y + 16 + 19 * len(wrap(value, w or (W - x - cls.M), font))

    @classmethod
    def warn(cls, d):
        cls.frame(d, "Family Safe · Base", "Nonce 42 · 1/3", "Takes control", cls.RED,
                  [("Turn", "pages", None), ("Push", "leave", None), ("Sign", "locked", None)])
        d.fill_rect(0, 30, 3, H - 66, col(cls.RED))
        F.text(d, "Enable a module", cls.M, 54, "bold26", cls.INK, cls.BG)
        y = cls.field(d, cls.M, 94, "Module", pick(MODULE), "mono13")
        F.text(d, "Unknown code · not in registry", cls.M, y + 1, "sans12", cls.RED, cls.BG)
        if WIDE:
            cls.field(d, cls.M, 146, "Effect", "Moves every asset, no owner signing.", w=W // 2 + 30)
            cls.field(d, W // 2 + 60, 146, "Hash, made here", "5A3C..9E21", "mono13")
        else:
            cls.field(d, cls.M, 146, "Effect", "Could move every asset with no owner signing.")

    @classmethod
    def send(cls, d):
        cls.frame(d, "Family Safe · Base", "Nonce 41 · 1/2", "Routine", cls.GREEN,
                  [("Turn", "pages", None), ("Push", "leave", None), ("Hold", "to sign", cls.INK)])
        x = F.text(d, "0.05", cls.M, 54, "bold26", cls.INK, cls.BG)
        F.text(d, " ETH", x, 54, "bold26", cls.MUTED, cls.BG)
        F.text(d, "to Carol", cls.M, 90, "sans14", cls.INK, cls.BG)
        F.text(d, pick(CAROL), cls.M, 110, "mono13", cls.MUTED, cls.BG)
        cls.field(d, cls.M, 140, "Approvals", "1 of 2: Alice", w=W // 2 - 20)
        cls.field(d, W // 2 + (10 if WIDE else 0), 140, "Code", "7B10-44E2", "mono13")

    @classmethod
    def hold(cls, d):
        cls.frame(d, "Family Safe · Base", "Nonce 41", "Signing", cls.BLUE,
                  [("Hold", "the footswitch", cls.INK), ("Let go", "to stop", None)])
        F.text(d, "Keep holding", cls.M, 54, "bold26", cls.INK, cls.BG)
        d.fill_rect(cls.M, 100, W - 2 * cls.M, 4, col(cls.LINE))
        d.fill_rect(cls.M, 100, (W - 2 * cls.M) * 7 // 10, 4, col(cls.BLUE))
        F.text(d, "1.4 of 2 s · nothing sent yet", cls.M, 112, "sans12", cls.MUTED, cls.BG)
        cls.field(d, cls.M, 144, "Signs the SafeTx hash made here", pick(HASH), "mono13")

    @classmethod
    def home(cls, d):
        cls.frame(d, "PicoQuorum", "Chip 3 · sealed", None, None, [("Turn", "select", None), ("Push", "open", None)])
        F.text(d, "Ready", cls.M, 32, "bold26", cls.INK, cls.BG)
        F.text(d, "1 to review", W - cls.M - F.width("1 to review", "sans14"), 42, "sans14", cls.AMBER, cls.BG)
        for i, (name, sub, st, c) in enumerate((("Family Safe", "Base · 2 of 3", "1 waiting", cls.AMBER),
                                                ("Ops Safe", "Ethereum · 3 of 5", "Clear", cls.GREEN))):
            y = 80 + 44 * i
            d.hline(cls.M, y - 8, W - 2 * cls.M, col(cls.LINE))
            if i == 0:
                d.fill_rect(cls.M - 8, y - 4, 3, 34, col(cls.AMBER))
            F.text(d, name, cls.M, y, "bold14", cls.INK, cls.BG)
            F.text(d, sub, cls.M, y + 18, "sans12", cls.MUTED, cls.BG)
            F.text(d, st, W - cls.M - F.width(st, "sans14"), y + 8, "sans14", c, cls.BG)


# ==== C: annunciator ================================================================================
class C:
    FONTS = None
    BG, WHITE, DIM = (0, 0, 0), (232, 232, 232), (110, 110, 110)
    RED, AMBER, GREEN, CYAN = (255, 64, 56), (255, 176, 0), (60, 220, 90), (60, 210, 230)

    @classmethod
    def cw(cls):
        return F.width("0", "mono13")

    @classmethod
    def line(cls, d, y, left, right="", rgb=None, rrgb=None, x=10):
        """A message line: left, a dotted leader, right flush to the edge, as in a cockpit checklist."""
        c = rgb or cls.WHITE
        x1 = F.text(d, left, x, y, "mono13", c, cls.BG)
        if right:
            rx = W - 10 - F.width(right, "mono13")
            n = (rx - x1 - 6) // cls.cw()
            if n > 1:
                F.text(d, " " + "." * (n - 1), x1, y, "mono13", cls.DIM, cls.BG)
            F.text(d, right, rx, y, "mono13", rrgb or c, cls.BG)

    @classmethod
    def frame(cls, d, left, right, light, lrgb, foot):
        d.fill(col(cls.BG))
        F.text(d, left, 10, 6, "mono13", cls.WHITE, cls.BG)
        F.text(d, right, W - 10 - F.width(right, "mono13"), 6, "mono13", cls.WHITE, cls.BG)
        d.hline(0, 26, W, col(cls.DIM))
        if light:
            w = F.width(light, "bold18") + 20
            d.fill_rect(10, 34, w, 30, col(lrgb))
            F.text(d, light, 20, 37, "bold18", cls.BG, lrgb)
        d.hline(0, H - 24, W, col(cls.DIM))
        x = 10
        for k, v, c in (foot if WIDE else foot[:2]):
            x = F.text(d, k + ":", x, H - 20, "mono13", cls.DIM, cls.BG)
            x = F.text(d, v, x, H - 20, "mono13", c, cls.BG) + (cls.cw() * 2 if WIDE else cls.cw())

    @classmethod
    def warn(cls, d):
        cls.frame(d, "FAMILY SAFE/BASE", "N42 1/3", "WARNING", cls.RED,
                  [("TURN", "PAGE", cls.CYAN), ("PUSH", "LEAVE", cls.CYAN), ("SIGN", "INHIB", cls.DIM)])
        x = 20 + F.width("WARNING", "bold18") + 20 + 8
        F.text(d, "CONTROL", x, 34, "mono13", cls.RED, cls.BG)
        F.text(d, "CHANGE", x, 50, "mono13", cls.RED, cls.BG)
        cls.line(d, 74, "MODULE ENABLE", "UNKNOWN", cls.RED)
        cls.line(d, 94, " TARGET", "0xC0FF..4979")
        cls.line(d, 112, " CODE NOT IN REGISTRY", "", cls.AMBER)
        cls.line(d, 130, " MOVES ASSETS, NO SIGS", "", cls.AMBER)
        cls.line(d, 152, "-SIGN", "INHIBITED", cls.CYAN, cls.DIM)
        cls.line(d, 170, "-CANCEL", "EXEC N42 TX", cls.CYAN)
        cls.line(d, 192, "HASH 5A3C..9E21", "DEVICE", cls.GREEN)

    @classmethod
    def send(cls, d):
        cls.frame(d, "FAMILY SAFE/BASE", "N41 1/2", None, None,
                  [("TURN", "PAGE", cls.CYAN), ("PUSH", "LEAVE", cls.CYAN), ("SIGN", "HOLD 2S", cls.CYAN)])
        F.text(d, "SEND 0.05 ETH", 10, 36, "bold18", cls.GREEN, cls.BG)
        cls.line(d, 74, " TO", "CAROL")
        cls.line(d, 92, " ADDR", "0x8F2A..11C4")
        cls.line(d, 110, " APPR", "1/2 ALICE")
        cls.line(d, 128, " CLASS", "ROUTINE", None, cls.GREEN)
        cls.line(d, 152, "-SIGN", "HOLD 2S", cls.CYAN)
        cls.line(d, 192, "CODE 7B10-44E2", "DEVICE", cls.GREEN)

    @classmethod
    def hold(cls, d):
        cls.frame(d, "FAMILY SAFE/BASE", "N41", "SIGNING", cls.CYAN, [("RELEASE", "ABORT", cls.CYAN)])
        n = 20
        sw = (W - 20) // n
        for i in range(n):
            d.fill_rect(10 + i * sw, 82, sw - 3, 18, col(cls.GREEN if i < 14 else (40, 40, 40)))
        cls.line(d, 112, " ELAPSED", "1.4/2.0 S")
        cls.line(d, 130, " SIGNS", "SAFETX 5A3C..9E21")
        cls.line(d, 148, " KEY", "CHIP 3 SEALED")
        cls.line(d, 170, " SENT", "NOTHING YET", None, cls.AMBER)

    @classmethod
    def home(cls, d):
        cls.frame(d, "PICOQUORUM", "CHIP 3", None, None, [("TURN", "SELECT", cls.CYAN), ("PUSH", "OPEN", cls.CYAN)])
        F.text(d, "STATUS", 10, 36, "bold18", cls.WHITE, cls.BG)
        cls.line(d, 74, "FAMILY SAFE", "1 PENDING", cls.WHITE, cls.AMBER)
        cls.line(d, 92, "OPS SAFE", "NORM", cls.WHITE, cls.GREEN)
        cls.line(d, 110, "KEY CHIP 3", "SEALED", cls.WHITE, cls.GREEN)
        cls.line(d, 128, "SERVICE", "OK", cls.WHITE, cls.GREEN)
        cls.line(d, 152, "LAST 0.05 ETH CAROL", "2H", cls.DIM)


# ==== D: statement ==================================================================================
class D:
    FONTS = "inter"
    BG, INK, MUTED, LINE = (247, 244, 237), (26, 26, 30), (112, 108, 102), (222, 216, 204)
    RED, AMBER, GREEN, BLUE = (200, 40, 40), (196, 120, 0), (24, 130, 70), (40, 90, 200)
    M = 14

    @classmethod
    def frame(cls, d, left, right, stripe):
        d.fill(col(cls.BG))
        if stripe:
            d.fill_rect(0, 0, W, 6, col(stripe))
        F.text(d, left, cls.M, 14, "sans12", cls.MUTED, cls.BG)
        F.text(d, right, W - cls.M - F.width(right, "sans12"), 14, "sans12", cls.MUTED, cls.BG)

    @classmethod
    def sentence(cls, d, y, s, font="bold18", first=None, frgb=None):
        """The page's one sentence. first: its opening word, in the page's colour."""
        lines = wrap(s, W - 2 * cls.M, font)
        for i, ln in enumerate(lines):
            x = cls.M
            if i == 0 and first and ln.startswith(first):
                x = F.text(d, first, x, y, font, frgb, cls.BG)
                ln = ln[len(first):]
            F.text(d, ln, x, y + (F.height(font) + 2) * i, font, cls.INK, cls.BG)
        return y + (F.height(font) + 2) * len(lines)

    @classmethod
    def small(cls, d, y, s, rgb=None, font="sans12"):
        for i, ln in enumerate(wrap(s, W - 2 * cls.M, font)):
            F.text(d, ln, cls.M, y + 16 * i, font, rgb or cls.MUTED, cls.BG)
        return y + 16 * len(wrap(s, W - 2 * cls.M, font))

    @classmethod
    def bar(cls, d, s, fill, ink):
        rrect(d, cls.M, H - 44, W - 2 * cls.M, 32, 8, fill)
        F.text(d, s, (W - F.width(s, "bold14")) // 2, H - 37, "bold14", ink, fill)

    @classmethod
    def warn(cls, d):
        cls.frame(d, pick(("Family Safe on Base · nonce 42", "Family Safe · nonce 42")), "1 of 3", cls.RED)
        y = cls.sentence(d, 36, "Stop. This would let an unknown contract move everything in the Safe.", "bold18", "Stop.", cls.RED)
        y = cls.small(d, y + 8, "Its code isn't in your registry, and no owner approved it. Bob proposed it from the Safe service.")
        F.text(d, "Module " + pick(MODULE), cls.M, y + 6, "mono13", cls.MUTED, cls.BG)
        cls.bar(d, pick(("This device won't sign it · push to leave", "Won't sign · push to leave")), cls.LINE, cls.INK)

    @classmethod
    def send(cls, d):
        cls.frame(d, pick(("Family Safe on Base · nonce 41", "Family Safe · nonce 41")), "1 of 2", cls.GREEN)
        y = cls.sentence(d, 32, "Send 0.05 ETH to Carol.", "bold26")
        y = cls.small(d, y + 6, "Carol is in your address book.")
        F.text(d, pick(CAROL), cls.M, y + 2, "mono13", cls.MUTED, cls.BG)
        cls.small(d, y + 26, "Alice approved it. Yours makes 2 of 2.", cls.INK, "sans14")
        cls.bar(d, pick(("Hold the footswitch to approve", "Hold footswitch to approve")), cls.INK, cls.BG)

    @classmethod
    def hold(cls, d):
        cls.frame(d, pick(("Family Safe on Base · nonce 41", "Family Safe · nonce 41")), "Signing", cls.BLUE)
        cls.sentence(d, 36, "Keep holding.", "bold26")
        rrect(d, cls.M, 92, W - 2 * cls.M, 16, 8, cls.LINE)
        rrect(d, cls.M, 92, (W - 2 * cls.M) * 7 // 10, 16, 8, cls.BLUE)
        cls.small(d, 120, "Let go to stop. Nothing is sent until the bar is full.", cls.INK, "sans14")
        cls.small(d, 170, "Signs the Safe transaction hash this device worked out: " + pick(HASH))

    @classmethod
    def home(cls, d):
        cls.frame(d, "PicoQuorum · chip 3", "Ready", None)
        y = cls.sentence(d, 36, "One transaction needs you.", "bold18")
        for i, (name, sub, st, c) in enumerate((("Family Safe", "Base · 2 of 3", "Review", cls.AMBER),
                                                ("Ops Safe", "Ethereum · 3 of 5", "Clear", cls.GREEN))):
            yy = y + 14 + 46 * i
            rrect(d, cls.M, yy, W - 2 * cls.M, 38, 6, (255, 253, 248) if i else (255, 246, 228))
            F.text(d, name, cls.M + 10, yy + 4, "bold14", cls.INK, (255, 253, 248) if i else (255, 246, 228))
            F.text(d, sub, cls.M + 10, yy + 21, "sans12", cls.MUTED, (255, 253, 248) if i else (255, 246, 228))
            F.text(d, st, W - cls.M - 10 - F.width(st, "bold14"), yy + 11, "bold14", c, (255, 253, 248) if i else (255, 246, 228))


DIRECTIONS = (("A-terminal", A), ("B-instrument", B), ("C-annunciator", C), ("D-statement", D))
SCREENS = [("%s-%s" % (n, s), k, s) for n, k in DIRECTIONS for s in ("warn", "send", "hold", "home")]
cur = 0


def draw(i):
    global lcd, cur
    if lcd is None:
        lcd = L.LCD()
    cur = i % len(SCREENS)
    _, k, s = SCREENS[cur]
    F.use(getattr(k, "FONTS", None))

    def frame():
        getattr(k, s)(lcd)
        lcd.show()
    lcd.frames(frame)
    F.use(None)


def start():
    draw(0)
    try:
        from machine import Timer
        keys = L.Keys()

        def tick(_t):
            for key in keys.pressed():
                if key in ("down", "right", "A", "press", "D1"):
                    draw(cur + 1)
                elif key in ("up", "left", "B", "D1L"):
                    draw(cur - 1)
        Timer(period=60, mode=Timer.PERIODIC, callback=tick)
    except Exception as e:
        print("ui_directions: no keys:", e)


start()
