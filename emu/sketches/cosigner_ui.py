# Mock-ups of a redesigned console UI: retro, but for work. The boot screen's palette (bootpixel.py),
# the built-in 8x8 font on an 8 px grid, doubled for titles, and 8x8 pixel icons. Every review page
# has the same frame: a top bar (which Safe, which page), a band whose colour says what the
# transaction can do, the facts in label/value rows, and a footer that says what each control does.
# A design study for docs/quorum-ui/v3/, not the console: nothing here reads a chip, a service or a
# key, and nothing signs. The transactions are made up.
#   tools/emu run cosigner_ui     then turn (up/down) or press A for the next screen
#   node emu/render-cosigner-ui.mjs   writes every screen to docs/quorum-ui/v3/shots/
import framebuf
import lcd as L

W, H = L.W, L.H
lcd = None

BG, PANEL, RULE = (24, 20, 37), (38, 32, 60), (66, 58, 100)
INK, MUTED, DIM = (250, 240, 215), (150, 142, 180), (96, 90, 128)
AMBER, GREEN, BLUE, RED = (247, 168, 52), (96, 206, 108), (110, 156, 240), (238, 84, 100)
BANDS = {"red": ((96, 26, 46), RED), "amber": ((92, 60, 24), AMBER),
         "green": ((24, 72, 50), GREEN), "blue": ((30, 40, 96), BLUE)}

ICONS = {
    "warn": (0x18, 0x3C, 0x24, 0x66, 0x66, 0xFF, 0xE7, 0xFF),
    "ok": (0x00, 0x01, 0x03, 0x86, 0xCC, 0x78, 0x30, 0x00),
    "no": (0xC3, 0xE7, 0x7E, 0x3C, 0x3C, 0x7E, 0xE7, 0xC3),
    "lock": (0x18, 0x24, 0x24, 0x7E, 0x7E, 0x66, 0x7E, 0x7E),
    "knob": (0x3C, 0x66, 0xE7, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C),
    "push": (0x3C, 0x42, 0x99, 0xBD, 0xBD, 0x99, 0x42, 0x3C),
    "foot": (0x00, 0x18, 0x3C, 0x3C, 0x18, 0x7E, 0xFF, 0xFF),
    "info": (0x18, 0x18, 0x00, 0x38, 0x18, 0x18, 0x3C, 0x00),
    "chip": (0x5A, 0xFF, 0x81, 0xBD, 0xBD, 0x81, 0xFF, 0x5A),
}


def col(rgb):
    return L.color(*rgb)


_spans = {}


def text(d, s, x, y, rgb, scale=1):
    """The 8x8 font at any scale: doubled titles keep the same pixels, twice as big."""
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


def icon(d, name, x, y, rgb, scale=1):
    c = col(rgb)
    for j, row in enumerate(ICONS[name]):
        for i in range(8):
            if row & (0x80 >> i):
                d.fill_rect(x + i * scale, y + j * scale, scale, scale, c)


def tag(d, s, x, y, fg, bg):
    """A label in a box, like a status light: [ VERIFIED ]."""
    d.fill_rect(x, y - 2, 8 * len(s) + 6, 12, col(bg))
    text(d, s, x + 3, y, fg)
    return x + 8 * len(s) + 10


def wrap(s, cols):
    out, line = [], ""
    for w in s.split(" "):
        if len(line) + len(w) + (1 if line else 0) > cols:
            out.append(line)
            line = w
        else:
            line = (line + " " + w) if line else w
    return out + [line] if line else out


def para(d, s, x, y, rgb, cols=None):
    cols = cols or (W - x - 8) // 8
    for i, ln in enumerate(wrap(s, cols)):
        text(d, ln, x, y + 11 * i, rgb)
    return y + 11 * len(wrap(s, cols))


def topbar(d, left, right=""):
    d.fill_rect(0, 0, W, 18, col(PANEL))
    d.fill_rect(4, 3, 20, 12, col(AMBER))
    text(d, "PQ", 6, 5, BG)
    text(d, left, 30, 5, INK)
    text(d, right, W - 8 * len(right) - 6, 5, MUTED)
    d.hline(0, 18, W, col(RULE))


def band(d, kind, title, sub=""):
    """What the transaction can do, before anything else: red takes control or pays out more than
    it shows, amber changes who can act or is not fully read, green is routine, blue is this device."""
    bg, fg = BANDS[kind]
    d.fill_rect(0, 22, W, 34, col(bg))
    d.fill_rect(0, 22, 6, 34, col(fg))
    icon(d, {"red": "warn", "amber": "warn", "green": "ok", "blue": "info"}[kind], 12, 27, fg, 3)
    text(d, title, 44, 26, INK, 2)
    if sub:
        text(d, sub, 44, 45, fg)


def footer(d, items):
    """What each control does on this page: the knob's turn, its push, the footswitch."""
    d.fill_rect(0, H - 20, W, 20, col(PANEL))
    d.hline(0, H - 21, W, col(RULE))
    x = 6
    for name, label, rgb in items:
        icon(d, name, x, H - 14, rgb)
        text(d, label, x + 11, H - 14, rgb)
        x += 11 + 8 * len(label) + 12


def row(d, y, label, value, rgb=INK):
    text(d, label, 12, y, MUTED)
    text(d, value, 84, y, rgb)


def check(d, y, ok, s, cols=34):
    icon(d, "ok" if ok is True else "no" if ok is False else "warn", 12, y, GREEN if ok is True else RED if ok is False else AMBER)
    return para(d, s, 28, y, INK if ok is not None else AMBER, cols)


def blockie(d, x, y):
    import blockies
    blockies.draw(d, "0x47c0998c6a7a1955794071b9f4058e7814178f35", x, y, 2)


# ---- the screens ---------------------------------------------------------------------------------
def s_home(d):
    topbar(d, "PICOQUORUM", "CHIP 3")
    blockie(d, W - 72, 1)
    text(d, "QUORUM READY", 12, 30, INK, 2)
    tag(d, "1 WAITING", W - 92, 34, BG, AMBER)
    d.hline(12, 54, W - 24, col(RULE))
    for i, (name, net, q, st, c) in enumerate((("FAMILY SAFE", "BASE", "2 OF 3", "1 TO REVIEW", AMBER),
                                               ("OPS SAFE", "ETH", "3 OF 5", "CLEAR", GREEN))):
        y = 64 + 34 * i
        if i == 0:
            d.fill_rect(8, y - 6, W - 16, 30, col(PANEL))
            d.fill_rect(8, y - 6, 3, 30, col(AMBER))
        text(d, name, 18, y, INK)
        text(d, net + "  " + q, 18, y + 12, MUTED)
        text(d, st, W - 8 * len(st) - 18, y + 6, c)
    text(d, "LAST SIGNED", 12, 146, MUTED)
    text(d, "0.05 ETH TO CAROL  2 H AGO", 12, 158, INK)
    text(d, "THIS KEY", 12, 180, MUTED)
    text(d, "OWNER 0x47C0..8F35  SEALED", 12, 192, INK)
    footer(d, [("knob", "SELECT", INK), ("push", "OPEN", INK), ("foot", "SIGN ONLY", DIM)])


def s_attack1(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "1/3")
    band(d, "red", "TAKES CONTROL", "MOVES FUNDS WITHOUT THE OWNERS")
    row(d, 66, "ACTION", "Enable a module")
    row(d, 80, "MODULE", "0xC0FF EE25 .. 9D54 4979")
    tag(d, "UNKNOWN CODE", 84, 94, INK, (130, 30, 50))
    tag(d, "NOT IN REGISTRY", 194, 94, INK, (130, 30, 50))
    text(d, "EFFECT", 12, 114, MUTED)
    para(d, "Could move every asset in the Safe with no owner signing, until it is removed.",
         84, 114, INK, 28)
    row(d, 164, "FROM", "Safe service, proposer BOB")
    row(d, 178, "HASH", "5A3C 1F07 .. 77D2 9E21")
    text(d, "computed on this device", 84, 190, DIM)
    footer(d, [("knob", "PAGES", INK), ("push", "LEAVE", INK), ("lock", "SIGN LOCKED", DIM)])


def s_attack2(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "2/3")
    band(d, "red", "WHY IT IS RED")
    y = 66
    y = check(d, y, False, "The module's code is not in this Safe's registry. No owner has approved it.") + 6
    y = check(d, y, False, "50 more like it are queued, nonces 43 to 92. Signing future nonces in bulk "
                           "is how the Oct 29 exchange theft was set up.") + 6
    y = check(d, y, None, "Proposed from a laptop session 4 minutes ago.") + 6
    y = check(d, y, True, "The hash on page 1 was rebuilt here from these fields, not taken from the service.")
    footer(d, [("knob", "PAGES", INK), ("push", "LEAVE", INK), ("lock", "SIGN LOCKED", DIM)])


def s_attack3(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "3/3")
    band(d, "red", "WILL NOT SIGN", "THIS DEVICE'S RULE, NOT A SETTING")
    d.rect(12, 64, W - 24, 80, col(RED))
    para(d, "An unknown module is never signed here, however long the footswitch is held. "
            "To use one, add it to the registry first: 2 of 3 owners and a 48 h wait.", 20, 72, INK, 35)
    row(d, 154, "CANCEL", "Only another tx executed at")
    text(d, "nonce 42 cancels this one", 84, 166, INK)
    row(d, 186, "TELL", "co-signers code 9E21-C04A")
    footer(d, [("knob", "PAGES", INK), ("push", "LEAVE", INK), ("lock", "SIGN LOCKED", DIM)])


def s_7702(d):
    topbar(d, "HOT WALLET 14  EIP-7702", "1/2")
    band(d, "red", "DELEGATES ACCOUNT", "AN EOA'S CODE BECOMES A CONTRACT")
    row(d, 66, "DELEGATE", "0x7A1D 33C0 .. 51E9 0B5E")
    tag(d, "UNKNOWN CODE", 84, 80, INK, (130, 30, 50))
    row(d, 98, "CHAIN", "ANY (0)")
    tag(d, "EVERY CHAIN", 172, 98, INK, (130, 30, 50))
    row(d, 114, "NONCE", "1,043  + 49 queued to 1,092")
    text(d, "EFFECT", 12, 132, MUTED)
    para(d, "The contract can do anything this account can, on every chain, until the "
            "delegation is replaced. Pre-signed for 50 nonces, it stays live as the "
            "account keeps working.", 84, 132, INK, 28)
    footer(d, [("knob", "PAGES", INK), ("push", "LEAVE", INK), ("lock", "NEVER SIGNED", DIM)])


def s_aa1(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "1/4")
    band(d, "amber", "ACCOUNT UPGRADE", "CHANGES WHO CAN ACT: KNOWN CODE")
    text(d, "Turn on ERC-4337 for this Safe", 12, 64, INK)
    row(d, 80, "CALLS", "2, one batch (MultiSend)")
    text(d, "1", 84, 94, AMBER); text(d, "enableModule", 100, 94, INK)
    text(d, "2", 84, 106, AMBER); text(d, "setFallbackHandler", 100, 106, INK)
    row(d, 122, "BOTH TO", "Safe4337Module 0.3.0")
    text(d, "0x75CF 1146 .. 8FD5 C226", 84, 134, MUTED)
    text(d, "CODE", 12, 152, MUTED)
    tag(d, "VERIFIED", 84, 152, BG, GREEN)
    text(d, "codehash matches r12", 158, 152, INK)
    row(d, 168, "APPROVED", "r12 signed 2 of 3, Oct 12")
    row(d, 184, "DELAY", "48 h before it takes effect")
    footer(d, [("knob", "PAGES", INK), ("push", "LEAVE", INK), ("foot", "SIGN: 3 MORE", DIM)])


def s_aa2(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "2/4")
    band(d, "amber", "WHAT CHANGES")
    y = 66
    y = check(d, y, True, "Bundlers may submit operations for this Safe through EntryPoint 0.7.") + 5
    y = check(d, y, True, "Gas can come from the Safe or a paymaster.") + 5
    y = check(d, y, True, "Every operation still needs 2 of 3 owners: the module checks the Safe's own signatures.") + 5
    y = check(d, y, True, "Owners, threshold and other modules are unchanged.") + 5
    y = check(d, y, None, "New on this device: SafeOp approvals (EIP-712), shown and hashed the same way.")
    footer(d, [("knob", "PAGES", INK), ("push", "LEAVE", INK), ("foot", "SIGN: 2 MORE", DIM)])


def s_aa3(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "4/4")
    band(d, "amber", "ARM, THEN HOLD")
    text(d, "1  TURN THE KNOB TO ARM", 12, 70, INK)
    x0 = 12
    for i in range(12):
        d.fill_rect(x0 + i * 24, 86, 20, 14, col(AMBER if i < 8 else RULE))
    text(d, "8 OF 12", W - 68, 106, AMBER)
    text(d, "2  HOLD THE FOOTSWITCH 3 S", 12, 128, INK)
    text(d, "   (3 s: this page is amber)", 12, 140, MUTED)
    row(d, 166, "SIGNS", "SafeTx 5A3C..9E21")
    row(d, 180, "CODE", "9E21-C04A  read it out")
    footer(d, [("knob", "ARM", AMBER), ("push", "LEAVE", INK), ("foot", "HOLD 3 S", INK)])


def s_hold(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "SIGNING")
    band(d, "blue", "HOLDING  2.1 S", "LET GO TO CANCEL. NOTHING SENT YET")
    for i in range(10):
        d.fill_rect(12 + i * 30, 70, 26, 26, col(BLUE if i < 7 else RULE))
    row(d, 112, "SIGNS", "SafeTx hash, computed here")
    text(d, "5A3C 1F07 .. 77D2 9E21", 84, 124, INK)
    row(d, 142, "INTENT", "pq1 control 7F2A..C3B0")
    text(d, "the review shown, hashed", 84, 154, DIM)
    row(d, 172, "KEY", "chip 3, P-256, sealed")
    footer(d, [("foot", "KEEP HOLDING", BLUE)])


def s_done(d):
    topbar(d, "FAMILY SAFE  NONCE 42", "DONE")
    band(d, "green", "APPROVED", "2 OF 3 SIGNED. QUEUED: 48 H DELAY")
    row(d, 70, "SENT", "to Safe service, 14:02")
    row(d, 86, "AFTER", "Nov 2, 14:02. Any owner can")
    text(d, "cancel it until then.", 84, 98, INK)
    row(d, 116, "CODE", "9E21-C04A")
    row(d, 132, "COUNTER", "use 418 of this key")
    footer(d, [("knob", "HOME", INK), ("push", "OK", INK)])


SCREENS = [("home", s_home), ("attack-1", s_attack1), ("attack-2", s_attack2), ("attack-3", s_attack3),
           ("eip7702", s_7702), ("aa-1", s_aa1), ("aa-2", s_aa2), ("aa-3", s_aa3), ("hold", s_hold), ("done", s_done)]
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

        def tick(_t):
            for k in keys.pressed():
                if k in ("down", "right", "A", "press", "D1"):
                    draw(cur + 1)
                elif k in ("up", "left", "B", "D1L"):
                    draw(cur - 1)
        Timer(period=60, mode=Timer.PERIODIC, callback=tick)
    except Exception as e:
        print("cosigner_ui: no keys:", e)


start()
