# The checklist direction: B's calm and C's rules (docs/quorum-ui/v3/DIRECTIONS.md). Every screen is
# one list, read top to bottom, the same shape each time:
#   the context line (which Safe, which nonce, which page)
#   the light and a title: what this is, in one word and a few
#   the facts, one a line, label ...... value
#   what you can do, as lines too: - SIGN ...... HOLD 2 S
#   what the device checked itself, in green
# Colour only on the line that is the reason (red: act, amber: caution) and on what you can do (cyan).
# Graphite, hairlines between groups, the console's own Atkinson Hyperlegible fonts: nothing added.
# No Reject: a cosigner can only not sign. A design study: no chip, no service, nothing signed.
#   tools/emu run ui_checklist      then turn or press A for the next screen
#   node emu/render-cosigner-ui.mjs ui_checklist docs/quorum-ui/v3/checklist/320 build1-2.4
import fonts as F
import lcd as L

W, H = L.W, L.H
WIDE = W >= 300
lcd = None

BG, WHITE, DIM, RULE = (16, 17, 20), (228, 228, 224), (118, 120, 128), (54, 56, 62)
RED, AMBER, GREEN, CYAN = (255, 82, 72), (255, 180, 40), (80, 214, 110), (80, 200, 225)
M = 10              # the margin
TOP = 66            # the first line of the list
STEP = 16           # one line


def col(rgb):
    return L.color(*rgb)


def pick(wide, narrow):
    return wide if WIDE else narrow


def cw():
    return F.width("0", "mono13")


class Page:
    """Draws one screen as a list, keeping the place of the next line."""

    def __init__(self, d, left, right, light, lrgb, title):
        self.d, self.y = d, TOP
        d.fill(col(BG))
        F.text(d, left, M, 5, "mono13", DIM, BG)
        F.text(d, right, W - M - F.width(right, "mono13"), 5, "mono13", DIM, BG)
        d.hline(0, 24, W, col(RULE))
        w = F.width(light, "bold14") + 16
        d.fill_rect(M, 31, w, 26, col(lrgb))
        F.text(d, light, M + 8, 35, "bold14", BG, lrgb)
        F.text(d, title, M + w + 10, 32, "bold18", WHITE, BG)

    def line(self, label, value="", lrgb=WHITE, vrgb=None, x=M):
        """label, a dotted leader, value flush right: one fact or one action."""
        d, y = self.d, self.y
        x1 = F.text(d, label, x, y, "mono13", lrgb, BG)
        if value:
            rx = W - M - F.width(value, "mono13")
            n = (rx - x1 - 4) // cw()
            if n > 1:
                F.text(d, " " + "." * (n - 1), x1, y, "mono13", RULE if lrgb == DIM else DIM, BG)
            F.text(d, value, rx, y, "mono13", vrgb or lrgb, BG)
        self.y += STEP

    def rule(self):
        self.d.hline(M, self.y + 3, W - 2 * M, col(RULE))
        self.y += 9

    def act(self, verb, how, on=True):
        self.line("- " + verb, how, CYAN if on else DIM, CYAN if on else DIM)

    def check(self, what, where):
        self.line("+ " + what, where, GREEN)


# ---- the screens ---------------------------------------------------------------------------------
def s_home(d):
    p = Page(d, "PICOQUORUM", "CHIP 3", "REVIEW", AMBER, pick("1 transaction waits", "1 to review"))
    p.line("FAMILY SAFE", "1 WAITING", WHITE, AMBER)
    p.line("OPS SAFE", "CLEAR", WHITE, GREEN)
    p.rule()
    p.line("KEY", "CHIP 3, SEALED")
    p.line("SERVICE", "OK", WHITE, GREEN)
    p.line("LAST", pick("0.05 ETH TO CAROL, 2 H", "0.05 ETH, 2 H"), DIM)
    p.rule()
    p.act("OPEN", "PUSH")
    p.act("SELECT", "TURN")


def s_send(d):
    p = Page(d, pick("FAMILY SAFE / BASE", "FAMILY SAFE"), "N41 1/1", "ROUTINE", GREEN, "Send 0.05 ETH")
    p.line("TO", "Carol")
    p.line("ADDRESS", pick("0x8F2A 03D1..6B0E 11C4", "0x8F2A..11C4"))
    p.line("ADDRESS BOOK", "YES", WHITE, GREEN)
    p.line("APPROVALS", "1 OF 2: ALICE")
    p.rule()
    p.act("SIGN", "HOLD 2 S")
    p.act("LEAVE", "PUSH")
    p.rule()
    p.check("CODE 7B10-44E2", "MADE HERE")


def s_warn(d):
    p = Page(d, pick("FAMILY SAFE / BASE", "FAMILY SAFE"), "N42 1/2", "WARNING", RED, "Takes control")
    p.line("ACTION", "ENABLE MODULE")
    p.line("MODULE", pick("0xC0FF EE25..9D54 4979", "0xC0FF..4979"))
    p.line("CODE", pick("UNKNOWN, NOT IN REGISTRY", "UNKNOWN"), RED)
    p.line("EFFECT", pick("MOVES ALL, NO SIGNATURES", "MOVES ALL, NO SIGS"), AMBER)
    p.line("QUEUE", pick("50 LIKE IT, N43 TO N92", "50 LIKE IT"), AMBER)
    p.rule()
    p.act("SIGN", "INHIBITED", False)
    p.act("LEAVE", "PUSH")
    p.act("CANCEL", pick("OTHER TX AT N42", "OTHER TX N42"))
    p.check("HASH 5A3C..9E21", "MADE HERE")


def s_upgrade(d):
    p = Page(d, pick("FAMILY SAFE / BASE", "FAMILY SAFE"), "N42 1/2", "CAUTION", AMBER, pick("Account upgrade", "Upgrade"))
    p.line("ACTION", "TURN ON ERC-4337")
    p.line("CALLS", "2, ONE BATCH")
    p.line(" 1", pick("enableModule", "enableModule"), DIM, WHITE)
    p.line(" 2", pick("setFallbackHandler", "setFallbackH.."), DIM, WHITE)
    p.line("TARGET", pick("Safe4337Module 0.3.0", "4337Module 0.3.0"))
    p.line("CODE", "VERIFIED, R12", WHITE, GREEN)
    p.line("TAKES EFFECT", "AFTER 48 H", WHITE, AMBER)
    p.rule()
    p.act("ARM", "TURN 12")
    p.act("SIGN", "THEN HOLD 3 S")


def s_conflict(d):
    p = Page(d, pick("FAMILY SAFE / BASE", "FAMILY SAFE"), "N42", "CAUTION", AMBER, pick("2 at nonce 42", "2 at N42"))
    p.line("A ENABLE MODULE", "BOB 1/2", RED, WHITE)
    p.line("B NO-OP", "ALICE 1/2", GREEN, WHITE)
    p.rule()
    p.line(pick("ONLY ONE CAN EXECUTE", "ONLY ONE EXECUTES"), "", AMBER)
    p.line(pick("B EXECUTING CANCELS A", "B CANCELS A"), "")
    p.rule()
    p.act("REVIEW B", "TURN")
    p.act("REVIEW A", "TURN")
    p.act("LEAVE", "PUSH")


def s_hold(d):
    p = Page(d, pick("FAMILY SAFE / BASE", "FAMILY SAFE"), "N41", "SIGNING", CYAN, "Keep holding")
    n = 20
    sw = (W - 2 * M) // n
    for i in range(n):
        d.fill_rect(M + i * sw, p.y + 2, sw - 3, 12, col(GREEN if i < 14 else RULE))
    p.y += 22
    p.line("ELAPSED", "1.4 / 2.0 S")
    p.line("SIGNS", pick("SAFETX 7B10..44E2", "7B10..44E2"))
    p.line("KEY", "CHIP 3")
    p.line("SENT", "NOTHING YET", WHITE, AMBER)
    p.rule()
    p.act("STOP", "LET GO")


def s_done(d):
    p = Page(d, pick("FAMILY SAFE / BASE", "FAMILY SAFE"), "N41", "SIGNED", GREEN, pick("2 of 2 approvals", "2 of 2"))
    p.line("SENT", pick("SAFE SERVICE, 14:02", "SERVICE 14:02"))
    p.line("NEXT", pick("ANY OWNER EXECUTES", "AN OWNER EXECUTES"))
    p.line("CODE", "7B10-44E2")
    p.line("KEY USE", "418")
    p.rule()
    p.act("HOME", "PUSH")
    p.rule()
    p.check("SIGNED HASH", "MADE HERE")


SCREENS = [("home", s_home), ("send", s_send), ("warn", s_warn), ("upgrade", s_upgrade),
           ("conflict", s_conflict), ("hold", s_hold), ("done", s_done)]
cur = 0


def draw(i):
    global lcd, cur
    if lcd is None:
        lcd = L.LCD()
    cur = i % len(SCREENS)

    def frame():
        SCREENS[cur][1](lcd)
        lcd.show()
    lcd.frames(frame)


def start():
    draw(0)
    try:
        from machine import Timer
        keys = L.Keys()

        def tick(_t):
            for k in keys.pressed():
                if k in ("down", "right", "A", "press", "D1"):
                    draw(cur + 1)
                elif k in ("up", "left", "B", "D1L"):
                    draw(cur - 1)
        Timer(period=60, mode=Timer.PERIODIC, callback=tick)
    except Exception as e:
        print("ui_checklist: no keys:", e)


start()
