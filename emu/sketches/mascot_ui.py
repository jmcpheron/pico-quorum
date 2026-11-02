# The v3 screens with Quo (mascot.py) in the band: docs/quorum-ui/v3/mascot/. v3's frame, palette, 8x8
# font and rules (cosigner_ui.py), with the band grown to 52 px to hold a 48 px face beside the title.
# Each review screen names its calls' classes; the band and the face are both picked from them by
# mascot.classify, the worst call first, so the face can never disagree with the band. The face adds to
# the band and the words: every screen reads the same with it covered up. Works at 320 x 240 and
# 240 x 240 (v3 rule 7): every string that doesn't fit 240 has a short form, pick(wide, narrow).
# A design study: nothing here reads a chip, a service or a key, and nothing signs. Made-up transactions.
#   tools/emu run mascot_ui        then turn or press A for the next screen; home blinks
#   node emu/render-cosigner-ui.mjs mascot_ui docs/quorum-ui/v3/mascot/320 build1-2.4
#   node emu/render-cosigner-ui.mjs mascot_ui docs/quorum-ui/v3/mascot/240 waveshare
import framebuf
import lcd as L
import mascot as M

W, H = L.W, L.H
WIDE = W >= 300
lcd = None

BG, PANEL, RULE = (24, 20, 37), (38, 32, 60), (66, 58, 100)
INK, MUTED, DIM = (250, 240, 215), (150, 142, 180), (96, 90, 128)
AMBER, GREEN, BLUE, RED = M.AMBER, M.GREEN, M.BLUE, M.RED
BANDS = {"red": ((96, 26, 46), RED), "amber": ((92, 60, 24), AMBER),
         "green": ((24, 72, 50), GREEN), "blue": ((30, 40, 96), BLUE)}
ICONS = {
    "ok": (0x00, 0x01, 0x03, 0x86, 0xCC, 0x78, 0x30, 0x00),
    "no": (0xC3, 0xE7, 0x7E, 0x3C, 0x3C, 0x7E, 0xE7, 0xC3),
    "warn": (0x18, 0x3C, 0x24, 0x66, 0x66, 0xFF, 0xE7, 0xFF),
    "lock": (0x18, 0x24, 0x24, 0x7E, 0x7E, 0x66, 0x7E, 0x7E),
    "knob": (0x3C, 0x66, 0xE7, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C),
    "push": (0x3C, 0x42, 0x99, 0xBD, 0xBD, 0x99, 0x42, 0x3C),
    "sign": (0x00, 0x18, 0x3C, 0x3C, 0x18, 0x7E, 0xFF, 0xFF),
}
TX = 66             # the band's text, right of the face
VX = 82             # a row's value
TOP = 84            # the first row under the band
blink = False       # home's face, one step in 24


def col(rgb):
    return L.color(*rgb)


def pick(wide, narrow):
    return wide if WIDE else narrow


_spans = {}


def text(d, s, x, y, rgb, scale=1):
    if scale == 1:
        d.text(s, x, y, col(rgb))
        return
    if s not in _spans:
        fb = framebuf.FrameBuffer(bytearray(len(s) * 8), len(s) * 8, 8, framebuf.MONO_HLSB)
        fb.text(s, 0, 0, 1)
        runs = []
        for j in range(8):
            i = 0
            while i < len(s) * 8:
                if fb.pixel(i, j):
                    i0 = i
                    while i < len(s) * 8 and fb.pixel(i, j):
                        i += 1
                    runs.append((i0, j, i - i0))
                else:
                    i += 1
        _spans[s] = runs
    c = col(rgb)
    for a, b, w in _spans[s]:
        d.fill_rect(x + a * scale, y + b * scale, w * scale, scale, c)


def icon(d, name, x, y, rgb):
    c = col(rgb)
    for j, r in enumerate(ICONS[name]):
        for i in range(8):
            if r & (0x80 >> i):
                d.pixel(x + i, y + j, c)


def tag(d, s, x, y, fg, bg):
    d.fill_rect(x, y - 2, 8 * len(s) + 6, 12, col(bg))
    text(d, s, x + 3, y, fg)


def wrap(s, cols):
    out, line = [], ""
    for w in s.split(" "):
        if line and len(line) + len(w) + 1 > cols:
            out.append(line)
            line = w
        else:
            line = (line + " " + w) if line else w
    return out + [line] if line else out


def para(d, s, x, y, rgb, cols=None):
    lines = wrap(s, cols or (W - x - 6) // 8)
    for i, ln in enumerate(lines):
        text(d, ln, x, y + 11 * i, rgb)
    return y + 11 * len(lines)


def topbar(d, left, right=""):
    d.fill_rect(0, 0, W, 18, col(PANEL))
    d.fill_rect(4, 3, 20, 12, col(AMBER))
    text(d, "PQ", 6, 5, BG)
    if 30 + 8 * len(left) > W - 8 * len(right) - 14:
        left = left.replace("  NONCE ", " #")
    text(d, left, 30, 5, INK)
    text(d, right, W - 8 * len(right) - 6, 5, MUTED)
    d.hline(0, 18, W, col(RULE))


def band(d, kind, face, title, sub=""):
    """v3's band, 52 px: the colour says what the transaction can do, Quo beside the title wears the
    same verdict. The title is doubled; if it won't fit one line it takes two, and the sub one."""
    bg, fg = BANDS[kind]
    d.fill_rect(0, 22, W, 52, col(bg))
    d.fill_rect(0, 22, 6, 52, col(fg))
    M.draw(d, face, 12, 24, 3, light=fg)
    if TX + 16 * len(title) <= W - 6:
        text(d, title, TX, 28, INK, 2)
        y, n = 48, 2
    else:
        a, b = wrap(title, (W - TX - 6) // 16)[:2]
        text(d, a, TX, 26, INK, 2)
        text(d, b, TX, 44, INK, 2)
        y, n = 63, 1
    for i, ln in enumerate(wrap(sub, (W - TX - 6) // 8)[:n]):
        text(d, ln, TX, y + 11 * i, fg)


def review(d, calls, title, sub):
    """The band and the face for a review page, from its calls' classes."""
    c = M.classify(calls)
    band(d, M.BAND[c], M.face_for("review", calls), title, sub)


def footer(d, items):
    d.fill_rect(0, H - 20, W, 20, col(PANEL))
    d.hline(0, H - 21, W, col(RULE))
    x = 6
    for name, label, rgb in items:
        icon(d, name, x, H - 14, rgb)
        text(d, label, x + 11, H - 14, rgb)
        x += 11 + 8 * len(label) + 12


def row(d, y, label, value, rgb=INK):
    text(d, label, 10, y, MUTED)
    text(d, value, VX, y, rgb)
    return y + 14


def check(d, y, ok, s):
    icon(d, "ok" if ok is True else "no" if ok is False else "warn", 10, y, GREEN if ok is True else RED if ok is False else AMBER)
    return para(d, s, 24, y, INK if ok is not None else AMBER) + 5


PAGES = ("knob", "PAGES", INK), ("push", "LEAVE", INK)


# ---- the screens ---------------------------------------------------------------------------------
def s_home(d):
    topbar(d, "PICOQUORUM", "CHIP 3")
    d.fill_rect(0, 22, W, 52, col(PANEL))
    M.draw(d, "blink" if blink else "idle", 12, 24, 3, light=AMBER)
    text(d, pick("QUORUM READY", "READY"), TX, 28, INK, 2)
    tag(d, "1 WAITING", TX, 52, BG, AMBER)
    y = TOP
    for i, (name, net, st, c) in enumerate((("FAMILY SAFE", "BASE  2 OF 3", "1 TO REVIEW", AMBER),
                                           ("OPS SAFE", "ETH  3 OF 5", "CLEAR", GREEN))):
        if i == 0:
            d.fill_rect(6, y - 5, W - 12, 30, col(PANEL))
            d.fill_rect(6, y - 5, 3, 30, col(AMBER))
        text(d, name, 16, y, INK)
        text(d, net, 16, y + 12, MUTED)
        text(d, st, W - 8 * len(st) - 14, y + 6, c)
        y += 34
    y = row(d, y + 2, "LAST", pick("0.05 ETH to Carol, 2 h ago", "0.05 ETH to Carol"))
    row(d, y, "KEY", pick("0x47C0..8F35, sealed", "0x47C0..8F35"))
    footer(d, [("knob", "SELECT", INK), ("push", "OPEN", INK), ("sign", "SIGN ONLY", DIM)])


def s_send(d):
    topbar(d, "FAMILY SAFE  NONCE 41", "1/2")
    review(d, ["pays"], "SENDS 0.05 ETH", pick("ROUTINE: A PAYMENT TO A KNOWN NAME", "A PAYMENT"))
    y = row(d, TOP, "TO", pick("Carol  0x9C4E 81D0 .. 21B7", "Carol 0x9C4E..21B7"))
    tag(d, "IN ADDRESS BOOK", VX, y, BG, GREEN)
    y = row(d, y + 16, "AMOUNT", pick("0.05 ETH, from the Safe", "0.05 ETH"))
    y = row(d, y, "CHAIN", "Base (8453)")
    y = row(d, y, "SIGNED", pick("1 of 2; yours makes 2", "1 of 2, yours: 2"))
    y = row(d, y, "HASH", pick("C04A 77D2 .. 1F07 9E21", "C04A..9E21"))
    text(d, pick("computed on this device", "computed here"), VX, y, DIM)
    footer(d, list(PAGES) + [("sign", "HOLD 2 S", INK)])


def s_swap(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "1/2")
    review(d, ["who_can_act"], "CHANGES SIGNERS", pick("SWAPS ONE OWNER. STILL 2 OF 3", "SWAPS ONE OWNER"))
    y = row(d, TOP, "OUT", pick("Bob    0x51A2 C0DE .. 77C0", "Bob 0x51A2..77C0"))
    y = row(d, y, "IN", pick("0x8D3F 02AA .. 6B11 C9E4", "0x8D3F..C9E4"))
    tag(d, pick("NEW TO THIS DEVICE", "NEW HERE"), VX, y, BG, AMBER)
    y = row(d, y + 16, "STAYS", pick("2 of 3 to sign", "2 of 3"))
    text(d, "EFFECT", 10, y, MUTED)
    y = para(d, "Bob can't sign any more. The new key can, with one other owner.", VX, y, INK)
    footer(d, list(PAGES) + [("sign", "HOLD 3 S", INK)])


def s_takeover(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "1/3")
    review(d, ["who_can_act", "takes_control"], "TAKES CONTROL", pick("ONE KEY COULD MOVE EVERYTHING", "ONE KEY, EVERYTHING"))
    y = row(d, TOP, "CALLS", pick("2, one batch (MultiSend)", "2, one batch"))
    text(d, "1", VX, y, AMBER)
    text(d, pick("swap Bob for 0x8D3F..C9E4", "swap Bob out"), VX + 16, y, INK)
    text(d, "2", VX, y + 12, RED)
    text(d, pick("threshold 2 of 3 to 1 of 3", "threshold 2 -> 1"), VX + 16, y + 12, INK)
    y += 30
    text(d, "EFFECT", 10, y, MUTED)
    para(d, pick("After this, the new key alone can move every asset in the Safe.",
                 "The new key alone could move it all."), VX, y, INK)
    footer(d, list(PAGES) + [("sign", "HOLD 3 S", RED)])


def s_attack(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "1/3")
    review(d, ["unknown_control"], "UNKNOWN MODULE", pick("COULD MOVE FUNDS WITHOUT THE OWNERS", "MOVES FUNDS"))
    y = row(d, TOP, "ACTION", "Enable a module")
    y = row(d, y, "MODULE", pick("0xC0FF EE25 .. 9D54 4979", "0xC0FF..4979"))
    tag(d, "UNKNOWN CODE", VX, y, INK, M.RED_D)
    if WIDE:
        tag(d, "NOT IN REGISTRY", VX + 110, y, INK, M.RED_D)
    y += 16
    text(d, "EFFECT", 10, y, MUTED)
    y = para(d, pick("Could move every asset in the Safe with no owner signing, until it is removed.",
                     "Could move it all, no owner signing."), VX, y, INK)
    row(d, y + 4, "FROM", pick("Safe service, proposer BOB", "service, BOB"))
    footer(d, list(PAGES) + [("lock", pick("SIGN LOCKED", "LOCKED"), DIM)])


def s_aa(d):
    topbar(d, "FAMILY SAFE  NONCE 43", "1/4")
    review(d, ["known_control"], "ACCOUNT UPGRADE", pick("CHANGES WHO CAN ACT: KNOWN CODE", "KNOWN CODE"))
    text(d, pick("Turn on ERC-4337 for this Safe", "Turn on ERC-4337"), 10, TOP, INK)
    y = row(d, TOP + 16, "CALLS", pick("2: module, fallback handler", "2, one batch"))
    y = row(d, y, "TO", pick("Safe4337Module 0.3.0", "Safe4337Module"))
    text(d, "CODE", 10, y, MUTED)
    tag(d, "VERIFIED", VX, y, BG, GREEN)
    if WIDE:
        text(d, "codehash in r12", VX + 78, y, INK)
    y = row(d, y + 14, "APPROVED", pick("r12, 2 of 3 owners, Oct 12", "r12, 2 of 3"))
    row(d, y, "DELAY", pick("48 h before it takes effect", "48 h"))
    footer(d, list(PAGES) + [("sign", pick("SIGN: 3 MORE", "3 MORE"), DIM)])


def s_refuse(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "3/3")
    band(d, "red", M.face_for("refused", ["unknown_control"]), "WILL NOT SIGN", pick("THIS DEVICE'S RULE, NOT A SETTING", "A RULE, NOT A SETTING"))
    y = para(d, "An unknown module is never signed here, however long Sign is held. To use one, "
                "add it to the registry: 2 of 3 owners and a 48 h wait.", 16, TOP + 2, INK)
    d.rect(8, TOP - 4, W - 16, y - TOP + 8, col(RED))
    y = row(d, y + 14, "CANCEL", pick("another tx at nonce 42", "nonce 42 only"))
    footer(d, list(PAGES) + [("lock", pick("SIGN LOCKED", "LOCKED"), DIM)])


def s_lie(d):
    topbar(d, "FAMILY SAFE  NONCE 44", "1/1")
    band(d, "red", M.face_for("refused", ["mismatch"]), "HASH MISMATCH", pick("THE SERVICE'S HASH IS NOT THIS TX", "NOT THIS TX"))
    y = row(d, TOP, "SERVICE", pick("5A3C 1F07 .. 77D2 9E21", "5A3C..9E21"), RED)
    y = row(d, y, "HERE", pick("B81D 0C4E .. 2F90 113A", "B81D..113A"), GREEN)
    text(d, pick("rebuilt here from the fields", "rebuilt here"), VX, y, DIM)
    y += 16
    para(d, "Safe's service says this is the transaction. Its hash doesn't match the fields, so "
            "nothing is signed.", 10, y, INK)
    footer(d, list(PAGES) + [("lock", pick("WILL NOT SIGN", "NO SIGN"), DIM)])


def s_hold(d):
    topbar(d, "FAMILY SAFE  NONCE 41", "SIGNING")
    band(d, "blue", M.face_for("holding"), "HOLDING 1.4 S", pick("LET GO TO CANCEL. NOTHING SENT YET", "LET GO TO CANCEL"))
    n = pick(10, 7)
    for i in range(n):
        d.fill_rect(10 + i * 30, TOP, 26, 20, col(BLUE if i < n * 7 // 10 else RULE))
    y = row(d, TOP + 32, "SIGNS", pick("SafeTx hash, computed here", "SafeTx hash"))
    text(d, pick("C04A 77D2 .. 1F07 9E21", "C04A..9E21"), VX, y, INK)
    row(d, y + 18, "KEY", pick("chip 3, P-256, sealed", "chip 3, sealed"))
    footer(d, [("sign", "KEEP HOLDING", BLUE)])


def s_done(d):
    topbar(d, "FAMILY SAFE  NONCE 41", "DONE")
    band(d, "green", M.face_for("signed"), "SIGNED", pick("2 OF 2. READY TO EXECUTE", "READY TO EXECUTE"))
    y = row(d, TOP, "SENT", pick("to Safe service, 14:02", "service, 14:02"))
    y = row(d, y, "PAYS", "0.05 ETH to Carol")
    y = row(d, y, "CODE", "9E21-C04A")
    row(d, y, "COUNTER", pick("use 418 of this key", "use 418"))
    footer(d, [("knob", "HOME", INK), ("push", "OK", INK)])


SCREENS = [("home", s_home), ("send", s_send), ("swap", s_swap), ("takeover", s_takeover),
           ("attack", s_attack), ("aa", s_aa), ("refuse", s_refuse), ("mismatch", s_lie),
           ("hold", s_hold), ("done", s_done)]
cur = 0


def draw(i):
    global lcd, cur
    if lcd is None:
        lcd = L.LCD()
    cur = i % len(SCREENS)

    def frame():
        lcd.fill(col(BG))
        SCREENS[cur][1](lcd)
        lcd.show()
    lcd.frames(frame)


def start():
    draw(0)
    try:
        from machine import Timer
        keys = L.Keys()
        step = [0]

        def tick(_t):           # 8 steps a second, as the boot screen: home blinks one step in 24
            global blink
            step[0] += 1
            b = cur == 0 and step[0] % 24 == 0
            if b != blink:
                blink = b
                draw(cur)
            for k in keys.pressed():
                if k in ("down", "right", "A", "press", "D1"):
                    draw(cur + 1)
                elif k in ("up", "left", "B", "D1L"):
                    draw(cur - 1)
        Timer(period=125, mode=Timer.PERIODIC, callback=tick)
    except Exception as e:
        print("mascot_ui: no keys:", e)


start()
