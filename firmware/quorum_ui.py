# The console's screens, drawn from quorum.py's state (passed in as q). Nothing here decides
# anything; it only draws.
#
# Type is Atkinson Hyperlegible (fonts.py), anti-aliased: a sans for words, a mono for addresses
# and hashes. Colours are named tokens in THEMES; use("dark") or use("light") picks a set. Text
# edges are mixed with what the text sits on, so every call names its background.
#
# The A/B/X/Y column runs down the right edge, A at the top and Y at the bottom. On a review page
# the SIGN bar runs across the top and ends in an A badge, REJECT across the bottom with a Y badge,
# and B (back) is labelled in the page row. SIGN stays grey until every page has been seen.
# With the knob (lcd.KNOB) the bottom bar holds three actions instead, SIGN, REJECT and BACK: they
# come after the last page as the knob turns, and a press on any page jumps to them. A red
# page is red all over, and the thing at stake (the address that gains power, the amount) is in
# the "stake" colour, as on the chip map's red PERMANENT screen.
#
# Who is being called: a contract pinned in quorum_cfg.py shows its logo and "known"; any other
# contract gets a warning triangle and "unknown contract". The logos are drawn here as coloured
# monograms, not copies of anyone's artwork.
from array import array
import time
import lcd as L
import fonts as F
import blockies
import decode

THEMES = {
    "dark": {
        "bg": (11, 13, 17), "surface": (24, 28, 36), "raised": (40, 47, 58), "line": (48, 55, 66),
        "text": (242, 244, 247), "muted": (152, 160, 172), "faint": (98, 106, 118),
        "ok": (52, 199, 89), "on_ok": (6, 30, 12),
        "bad": (255, 92, 84), "bad_bar": (200, 38, 38), "on_bad": (255, 255, 255),
        "bad_bg": (58, 12, 14), "bad_head": (150, 24, 26), "bad_text": (255, 234, 234), "bad_muted": (236, 160, 160),
        "warn": (255, 184, 48), "on_warn": (40, 26, 0), "warn_bg": (52, 38, 6), "warn_head": (120, 86, 6),
        "warn_text": (255, 244, 222), "warn_muted": (220, 190, 130), "stake": (112, 214, 255),
    },
    "light": {
        "bg": (245, 246, 248), "surface": (255, 255, 255), "raised": (222, 228, 236), "line": (214, 219, 226),
        "text": (16, 19, 24), "muted": (86, 94, 106), "faint": (150, 157, 168),
        "ok": (22, 150, 62), "on_ok": (255, 255, 255),
        "bad": (208, 36, 36), "bad_bar": (208, 36, 36), "on_bad": (255, 255, 255),
        "bad_bg": (254, 234, 234), "bad_head": (208, 36, 36), "bad_text": (64, 10, 10), "bad_muted": (150, 60, 60),
        "warn": (168, 102, 0), "on_warn": (40, 26, 0), "warn_bg": (255, 244, 220), "warn_head": (214, 142, 14),
        "warn_text": (60, 40, 0), "warn_muted": (130, 96, 30), "stake": (0, 104, 170),
    },
}
CHAIN = {31337: ((255, 149, 0), (26, 16, 0)), 8453: ((0, 82, 255), (255, 255, 255)),
         84532: ((150, 90, 255), (255, 255, 255)), 1: ((98, 126, 234), (255, 255, 255))}
LOGO = {"safe": ((18, 255, 128), (0, 0, 0), "S"), "uniswap": ((255, 0, 122), (255, 255, 255), "U"),
        "usdc": ((39, 117, 202), (255, 255, 255), "$")}
W, H = L.W, L.H                 # 240x240, or 320x240 on build1: x positions come from W
M = 10                          # side margin
R = W - M                       # right edge of text
TW = W - 2 * M                  # text width
OX = (W - 240) // 2             # centres a box laid out for 240 wide
TOP, BOTTOM = 30, 210           # review pages: content lives between the SIGN and REJECT bars
PAGE_ROW = 191                  # page dots and the B hint
T = {}
_565 = {}


def use(name):
    T.clear()
    T.update(THEMES.get(name, THEMES["dark"]))
    _565.clear()


use("dark")


def rgb(x):
    return T[x] if isinstance(x, str) else x


def c(x):
    x = rgb(x)
    v = _565.get(x)
    if v is None:
        v = _565[x] = L.color(*x)
    return v


# ----------------------------------------------------------------------------- drawing kit
def txt(d, s, x, y, font, fg="text", bg="bg"):
    return F.text(d, s, x, y, font, rgb(fg), rgb(bg))


def txt_r(d, s, xr, y, font, fg="text", bg="bg"):
    return F.text(d, s, xr - F.width(s, font), y, font, rgb(fg), rgb(bg))


def txt_c(d, s, y, font, fg="text", bg="bg", x0=0, x1=W):
    return F.text(d, s, x0 + (x1 - x0 - F.width(s, font)) // 2, y, font, rgb(fg), rgb(bg))


def fit(s, w, font):
    """s, cut with an ellipsis to fit w pixels."""
    if F.width(s, font) <= w:
        return s
    while s and F.width(s + "…", font) > w:
        s = s[:-1]
    return s + "…"


def para(d, s, x, y, w, font, fg, bg, pitch, bottom):
    """Wrapped text, stopping before bottom. Returns the y after it."""
    for line in F.wrap(s, w, font):
        if y + pitch > bottom:
            break
        txt(d, line, x, y, font, fg, bg)
        y += pitch
    return y


def rrect(d, x, y, w, h, r, col):
    col = c(col)
    d.fill_rect(x + r, y, w - 2 * r, h, col)
    d.fill_rect(x, y + r, r, h - 2 * r, col)
    d.fill_rect(x + w - r, y + r, r, h - 2 * r, col)
    d.ellipse(x + r, y + r, r, r, col, True, 2)
    d.ellipse(x + w - 1 - r, y + r, r, r, col, True, 1)
    d.ellipse(x + r, y + h - 1 - r, r, r, col, True, 4)
    d.ellipse(x + w - 1 - r, y + h - 1 - r, r, r, col, True, 8)


def pill(d, s, x, y, font, fill, ink):
    """Text in a rounded tag, top-left at (x, y). Returns its width."""
    w = F.width(s, font) + 12
    h = F.height(font)
    rrect(d, x, y, w, h, h // 2 - 1, fill)
    txt(d, s, x + 6, y, font, ink, fill)
    return w


def badge(d, key, cx, cy, fill, ink):
    """A button's letter in a circle, next to what it does."""
    d.ellipse(cx, cy, 9, 9, c(fill), True)
    w = F.width(key, "bold14")
    txt(d, key, cx - w // 2 + 1, cy - 10, "bold14", ink, fill)


def thick_line(d, x0, y0, x1, y1, col, t=3):
    col = c(col)
    for i in range(-(t // 2), t - t // 2):
        d.line(x0 + i, y0, x1 + i, y1, col)
        d.line(x0, y0 + i, x1, y1 + i, col)


def mark(d, ok, cx, cy, r):
    """A round check or cross."""
    d.ellipse(cx, cy, r, r, c("ok" if ok else "bad_bar"), True)
    ink = "on_ok" if ok else "on_bad"
    k = r * 45 // 100
    if ok:
        thick_line(d, cx - k, cy, cx - k // 3, cy + k * 2 // 3, ink, r // 6 + 1)
        thick_line(d, cx - k // 3, cy + k * 2 // 3, cx + k, cy - k * 2 // 3, ink, r // 6 + 1)
    else:
        thick_line(d, cx - k, cy - k, cx + k, cy + k, ink, r // 6 + 1)
        thick_line(d, cx - k, cy + k, cx + k, cy - k, ink, r // 6 + 1)


def warn_sign(d, cx, cy, r, fill="warn", ink="on_warn"):
    """A warning triangle with an exclamation mark, r pixels from centre to corner."""
    d.poly(cx, cy, array("h", [0, -r, r, r - 2, -r, r - 2]), c(fill), True)
    d.fill_rect(cx - 1, cy - r // 2 + 1, 2, r // 2 + 1, c(ink))
    d.fill_rect(cx - 1, cy + r // 2 + 1, 2, 2, c(ink))


def logo(d, key, cx, cy, r=8):
    """A known contract's monogram, or the warning triangle for an unknown one."""
    if key == "send":           # a plain transfer: an arrow, no contract
        col = c("muted")
        for k in (0, 1):
            d.hline(cx - 6, cy + k, 11, col)
            d.line(cx, cy - 5 + k, cx + 5, cy + k, col)
            d.line(cx, cy + 5 + k, cx + 5, cy + k, col)
    elif key == "refused":
        mark(d, False, cx, cy, r)
    elif key in LOGO:
        fill, ink, ch = LOGO[key]
        d.ellipse(cx, cy, r, r, c(fill), True)
        font = "bold14" if r >= 8 else "sans12"
        txt(d, ch, cx - F.width(ch, font) // 2 + 1, cy - (10 if r >= 8 else 8), font, ink, fill)
    else:
        warn_sign(d, cx, cy + 1, r)


def ident(q, a):
    """(name, logo, known) for an address: known contracts, this Safe, the address book."""
    return decode.identify(q.ctx, a) if q.ctx else (None, None, False)


def contract_chip(d, q, a, xr, y, fg, bg, room, font="sans12"):
    """Right-aligned in room pixels: [logo] Name for a known contract, the warning triangle and
    "Unknown contract" (or just "Unknown") for any other."""
    name, lg, known = ident(q, a)
    if known and lg:
        s = fit(name, room - 18, font)
        txt_r(d, s, xr, y, font, fg, bg)
        logo(d, lg, xr - F.width(s, font) - 12, y + F.height(font) // 2, 7)
    elif not known:
        s = "Unknown contract" if F.width("Unknown contract", font) + 22 <= room else "Unknown"
        txt_r(d, s, xr, y, font, fg, bg)
        warn_sign(d, xr - F.width(s, font) - 12, y + F.height(font) // 2, 8)


def short(a):
    return a[:6] + "…" + a[-4:] if len(a) > 14 else a


def addr_lines(a):
    """40 hex in 4-character chunks, two lines: 0x7099 7970 c518 12dc 3a01 / 0c7d 01b5 ..."""
    h = a[2:].lower() if a.startswith("0x") else a.lower()
    ch = [h[i:i + 4] for i in range(0, len(h), 4)]
    return ["0x" + " ".join(ch[:5]), "  " + " ".join(ch[5:])]


def hash_lines(h, per=4, size=4):
    """64 hex in chunks, per chunks to a line."""
    h = h[2:] if h.startswith("0x") else h
    ch = [h[i:i + size] for i in range(0, len(h), size)]
    return [" ".join(ch[i:i + per]) for i in range(0, len(ch), per)]


def chain_pill(d, q, x, y, right=False, full=True):
    fill, ink = CHAIN.get(q.CHAIN, ((120, 120, 120), (255, 255, 255)))
    s = q.CFG["chains"].get(str(q.CHAIN), "Chain")
    if full:
        s += " · %d" % q.CHAIN
    if right:
        x -= F.width(s, "sans12") + 12
    return pill(d, s, x, y, "sans12", fill, ink)


def version_pill(d, q, x, y):
    """Safe v1.4.1, red when this console's hash does not fit that version."""
    v, ok = q.safe_version()
    if not v:
        return 0
    return pill(d, "Safe v" + v, x, y, "sans12", "surface" if ok else "bad_bar", "muted" if ok else "on_bad")


def page_colors(level):
    if level == "red":
        return {"bg": "bad_bg", "head": "bad_head", "on_head": "on_bad", "text": "bad_text", "muted": "bad_muted",
                "stake": "stake"}
    if level == "warn":
        return {"bg": "warn_bg", "head": "warn_head", "on_head": "on_bad", "text": "warn_text", "muted": "warn_muted",
                "stake": "warn_text"}
    return {"bg": "bg", "head": "surface", "on_head": "text", "text": "text", "muted": "muted", "stake": "text"}


def footer_hints(d, q, hints, y=222, bg="bg"):
    """Key badges with what they do, or the last message if there is one. With the knob, only the
    first hint: what a press does."""
    if q.msg:
        d.fill_rect(0, y - 12, W, H - y + 12, c(bg))
        txt_c(d, q.msg, y - 9, "bold14", "warn", bg)
        return
    if q.KNOB:
        if hints:
            knob_badge(d, M + 6, y, "raised", "text")
            x = txt(d, "press", M + 19, y - 8, "sans12", "faint", bg)
            txt(d, hints[0][1], x + 6, y - 9, "bold14", "text", bg)
        return
    x = M + 6
    for key, what in hints:
        badge(d, key, x, y, "raised", "text")
        x = txt(d, what, x + 13, y - 8, "sans12", "muted", bg) + 16


def knob_badge(d, cx, cy, fill, ink):
    """The knob, seen from above: a disc with a pointer notch."""
    d.ellipse(cx, cy, 9, 9, c(fill), True)
    d.ellipse(cx, cy, 5, 5, c(ink), False)
    d.fill_rect(cx - 1, cy - 8, 2, 5, c(ink))


def knob_choices(d, q, items, focus, hint, y=222, bg="bg"):
    """A row of choices the knob turns onto, right-aligned, the one in focus lit; a hint on the left.
    items: (key, label); focus: the key in focus, or None."""
    if q.msg:
        d.fill_rect(0, y - 12, W, H - y + 12, c(bg))
        txt_c(d, q.msg, y - 9, "bold14", "warn", bg)
        return
    knob_badge(d, M + 6, y, "raised", "text")
    x = R
    for key, label in reversed(items):
        on = key == focus
        font = "bold14" if on else "sans12"
        x -= F.width(label, font) + 12       # pill()'s width
        pill(d, label, x, y - 9, font, "stake" if on else "surface", "bg" if on else "muted")
        x -= 6
    if F.width(hint, "sans12") <= x - M - 21:
        txt(d, hint, M + 19, y - 8, "sans12", "faint", bg)


def tag_for(q, a, it=None):
    """The one tag a paid address gets: ("lookalike", "not <name>"), ("pinned", ...), ("first", ...),
    ("seen", "paid 3 times before"), or None. Only for items that pay or allow someone (it given)."""
    if it and it.get("lookalike"):
        return "lookalike", "LOOKALIKE"
    if q.ctx and a.lower() in q.ctx.get("pinned", {}):
        return "pinned", "pinned"
    if not it or it.get("label", "to") not in decode.PAYS:
        return None
    n = it.get("seen", 0)
    if n:
        return "seen", "paid once before" if n == 1 else "paid %d times before" % n
    if ident(q, a)[2]:
        return None
    return "first", "first time"


def tag_pill(d, kind, s, x, y, pc, bg, right=False):
    """A tag_for() tag as a pill (or muted text for "seen"). right: x is its right edge."""
    if kind == "seen":
        if right:
            x -= F.width(s, "sans12")
        txt(d, s, x, y + 1, "sans12", pc["muted"], bg)
        return F.width(s, "sans12")
    plain = bg == "bg"
    fill, ink = {"lookalike": ("bad_bar", "on_bad"),
                 "pinned": ("surface" if plain else pc["head"], "ok" if plain else pc["on_head"]),
                 "first": ("warn_bg" if plain else pc["head"], "warn" if plain else pc["on_head"])}[kind]
    if right:
        x -= F.width(s, "sans12") + 12
    return pill(d, s, x, y, "sans12", fill, ink)


def who_line(d, q, label, a, y, pc, bg, it=None):
    """label + who the address is (logo and name, a pinned name and its ENS, a name from the book,
    or a flag) and its tag, then the address itself in full beside its identicon. Returns the y
    after it."""
    name, lg, known = ident(q, a)
    tag = tag_for(q, a, it)
    tw = 0
    if tag:
        tw = tag_pill(d, tag[0], tag[1], R, y, pc, bg, True) + 8
    x = txt(d, label + " ", M, y + 1, "sans12", pc["muted"], bg)
    room = R - tw - x
    if tag and tag[0] == "lookalike":
        warn_sign(d, x + 8, y + 9, 8, "bad_bar", "on_bad")
        txt(d, fit("looks like " + it["lookalike"], room - 20, "bold14"), x + 20, y, "bold14", pc["text"], bg)
    elif lg:
        logo(d, lg, x + 7, y + 9, 7)
        x = txt(d, fit(name, room - 18, "bold14"), x + 18, y, "bold14", pc["text"], bg)
        if F.width(" known", "sans12") <= R - tw - x:
            txt(d, " known", x, y + 1, "sans12", "ok" if bg == "bg" else pc["muted"], bg)
    elif name:
        ens = decode.ens_of(q.ctx, a) if q.ctx else None
        x = txt(d, fit(name, room, "bold14"), x, y, "bold14", pc["text"], bg)
        if ens and ens != name and F.width(" \u00b7 " + ens, "sans12") <= R - tw - x:
            txt(d, " \u00b7 " + ens, x, y + 1, "sans12", pc["muted"], bg)
    elif label == "contract":
        warn_sign(d, x + 8, y + 9, 8)
        txt(d, "unknown contract", x + 20, y, "bold14", "warn" if bg == "bg" else pc["text"], bg)
    else:
        txt(d, fit("not in the address book", room, "sans12"), x, y + 1, "sans12", "warn" if bg == "bg" else pc["text"], bg)
    y += 18
    x = M
    if W >= 300:                # the identicon fits beside the address only on the wider screen
        blockies.draw(d, a.lower(), M, y + 2, 3)
        x += 32
    for line in addr_lines(a):
        txt(d, line, x, y, "mono13", pc["stake"], bg)
        y += 15
    return y + 5


# ----------------------------------------------------------------------------- home
def refused_short(why):
    """The reason a transaction is refused, in a few words for its row on home."""
    for key, short in (("another Safe", "other Safe"), ("delegatecall", "delegatecall"), ("not a transaction", "malformed"),
                       ("Operation", "bad operation"), ("safeTxHash", "no hash"), ("hash", "bad hash"), ("decoded", "unreadable")):
        if key in why:
            return short
    return "see why"


def draw_home(q):
    d = q.d
    d.fill(c("bg"))
    ok = q.net_ok
    many = len(q.WATCH) > 1
    if many:        # several Safes: how many answered, and the pill is the highlighted row's chain
        down = sum(1 for w in q.WATCH if w["tried"] and not w["ok"])
        s = ("%d offline" % down) if down else "%d synced" % len(q.WATCH)
    else:
        s = "Synced" if ok else "Offline"
    x = M + chain_pill(d, q, M, 4, full=not many) + 6
    v, vok = q.safe_version()
    if v and (not vok or x + F.width("Safe v" + v, "sans12") + 12 < R - F.width(s, "sans12") - 14):
        version_pill(d, q, x, 4)        # when it fits; always when the version is one this console can't sign for
    txt_r(d, s, R, 4, "sans12", "muted")
    d.ellipse(R - F.width(s, "sans12") - 8, 12, 3, 3, c("ok" if ok else "bad"), True)
    blockies.draw(d, q.SAFE_ADDR, M, 30, 4)
    n_own, need = len(q.owners()), q.threshold()
    room = R - 52 - (F.width("%d of %d" % (need, n_own), "bold14") + 8 if n_own else 0)
    txt(d, fit(q.SAFE["name"], room, "bold18"), 52, 26, "bold18")
    txt(d, short(q.SAFE_ADDR), 52, 49, "mono13", "muted")
    if n_own:
        txt_r(d, "%d of %d" % (need, n_own), R, 28, "bold14")
        txt_r(d, "approvals", R, 46, "sans12", "muted")
    todo = sum(1 for e in q.queue if q.waiting(e))
    y = 72
    txt(d, ("WAITING FOR YOU · %d" % todo) if todo else "QUEUE", M, y, "bold14" if todo else "sans12",
        "warn" if todo else "muted")
    if any(q.conflicts(e) for e in q.queue):
        txt_r(d, "same # twice", R, y + 2, "sans12", "warn")
    elif q.queue:
        txt_r(d, "%d queued" % len(q.queue), R, y + 2, "sans12", "faint")
    y = 92
    if not q.queue:
        if q.net_ok:
            mark(d, True, W // 2, 132, 16)
            txt_c(d, "Nothing to sign", 154, "bold18")
            txt_c(d, "The queue is empty", 178, "sans14", "muted")
        else:
            mark(d, False, W // 2, 128, 16)
            txt_c(d, "No service", 150, "bold18")
            txt_c(d, q.net_err[:30], 174, "sans14", "muted")
            txt_c(d, (q.BASE or "")[:34], 192, "mono13", "faint")
    n = 3 if q.outside else 4        # the outside-signatures warning takes the fourth row
    top = max(0, min(q.sel - (n - 1), len(q.queue) - n))
    for i in range(top, min(len(q.queue), top + n)):
        e = q.queue[i]
        lvl = "red" if e["why"] else e["r"]["level"]
        sel = i == q.sel and not q.foot
        fill = "raised" if sel else "surface"
        rrect(d, 6, y, W - 12, 25, 5, fill)
        if lvl != "ok":
            d.fill_rect(6, y + 5, 3, 15, c("bad" if lvl == "red" else "warn"))
        txt(d, "#%d" % e["n"], 15, y + 4, "mono13", "warn" if q.conflicts(e) else "faint", fill)
        con = e["r"].get("contract")
        lg = "refused" if e["why"] else "send"
        if con and not e["why"]:
            name, lg, known = decode.identify(e["w"]["ctx"], con) if e.get("w") and e["w"]["ctx"] else ident(q, con)
            lg = lg if known and lg else None
        logo(d, lg, 51, y + 12, 7)
        if e["why"]:
            what = "Refused · " + refused_short(e["why"])
        else:
            what = e["r"]["summary"]
        f = "bold14" if sel else "sans14"
        txt(d, fit(what, W - 116, f), 63, y + 3, f, {"red": "bad", "warn": "warn"}.get(lvl, "text"), fill)
        if q.signed_by_me(e):
            st, sc = "Signed", "ok"
        elif e["h"] in q.declined:
            st, sc = "Rejected", "bad"
        elif e["why"]:
            st, sc = "—", "bad"
        else:
            st, sc = "%d/%d" % (len(e["conf"]), q.threshold(e["w"])), "muted"
        txt_r(d, st, R - 4, y + 4, "sans12", sc, fill)
        if many:        # which chain the row's Safe is on, in its pill colour
            d.fill_rect(R, y + 5, 3, 15, c(CHAIN.get(e["w"]["chain"], ((120, 120, 120), 0))[0]))
        y += 28
    if q.outside:
        rrect(d, 6, 190, W - 12, 24, 5, "warn_bg")
        warn_sign(d, 18, 202, 8)
        txt(d, fit("key used %d\u00d7 outside this console" % q.outside, W - 40, "sans12"),
            30, 196, "sans12", "warn_text", "warn_bg")
    if q.KNOB:
        knob_choices(d, q, (("owners", "Owners"), ("device", "Device")), q.foot, "turn \u00b7 press")
    else:
        footer_hints(d, q, (("A", "Open"), ("B", "Owners"), ("X", "Device")))
    d.show()


# ----------------------------------------------------------------------------- review pages
def sign_bar(q):
    d = q.d
    ok, why = q.can_sign(q.cur)
    left = q.unseen()
    if ok and not left:
        d.fill_rect(0, 0, W, TOP - 2, c("ok"))
        x = txt(d, "Ready to sign" if q.KNOB else "Hold to sign", M, 3, "bold18", "on_ok", "ok")
        txt(d, "hold %d s" % (q.hold_need(q.cur) // 1000) if q.KNOB else "%d s" % (q.hold_need(q.cur) // 1000),
            x + 8, 7, "sans14", "on_ok", "ok")
        if not q.KNOB:
            badge(d, "A", W - 15, 14, "on_ok", "ok")
    else:
        d.fill_rect(0, 0, W, TOP - 2, c("surface"))
        x = txt(d, "Sign" if ok else "Can't sign", M, 3, "bold18", "faint", "surface")
        note = ("%d of %d pages seen" % (len(q.pages) - len(left), len(q.pages))) if ok else why
        txt(d, fit(note, W - 36 - x, "sans12"), x + 8, 8, "sans12", "muted", "surface")
        if not q.KNOB:
            badge(d, "A", W - 15, 14, "raised", "faint")


def reject_bar(q):
    d = q.d
    d.fill_rect(0, BOTTOM, W, H - BOTTOM, c("bad_bar"))
    txt(d, "Reject", M, BOTTOM + 4, "bold18", "on_bad", "bad_bar")
    badge(d, "Y", W - 15, BOTTOM + 15, "on_bad", "bad_bar")


def action_bar(q):
    """The knob's bottom bar: SIGN, REJECT and BACK. Lit only while the knob is on them (q.act);
    SIGN is green only when it can be held."""
    d = q.d
    ok, why = q.can_sign(q.cur)
    ready = ok and not q.unseen()
    d.fill_rect(0, BOTTOM, W, H - BOTTOM, c("bg"))
    gap, x = 4, 4
    ws = ((W - 16) * 40 // 100, (W - 16) * 32 // 100)
    ws += (W - 16 - ws[0] - ws[1],)
    for i, (label, on, off, ink_on) in enumerate((("SIGN", "ok" if ready else "raised", "surface", "on_ok" if ready else "text"),
                                                   ("REJECT", "bad_bar", "bad_bg", "on_bad"),
                                                   ("BACK", "raised", "surface", "text"))):
        focus = q.act == i
        fill = on if focus else off
        rrect(d, x, BOTTOM + 2, ws[i], H - BOTTOM - 4, 6, fill)
        if focus:
            d.rect(x, BOTTOM + 2, ws[i], H - BOTTOM - 4, c("text"))
        font = "bold18" if focus else "sans14"
        ink = ink_on if focus else ("bad_muted" if i == 1 else "muted")
        txt_c(d, label, BOTTOM + (4 if focus else 6), font, ink, fill, x, x + ws[i])
        x += ws[i] + gap


def page_row(q, pc):
    d, bg = q.d, pc["bg"]
    if q.msg:
        txt_c(d, q.msg, PAGE_ROW - 2, "bold14", "warn" if bg == "bg" else pc["text"], bg)
        return
    n = len(q.pages)
    here = q.page if not q.KNOB or q.act is None else -1
    x0 = W // 2 - (n * 12) // 2 + 6
    for i in range(n):
        col = "text" if i == here else ("muted" if i in q.seen else "faint")
        d.ellipse(x0 + i * 12, PAGE_ROW + 8, 3, 3, c(col if bg == "bg" else pc["muted"] if i != here else pc["text"]),
                  i == here or i in q.seen)
    if q.KNOB:          # the actions come after the last page: a bar for them in the row of dots
        d.fill_rect(x0 + n * 12 - 3, PAGE_ROW + 6, 9, 4, c(pc["text"] if q.act is not None else pc["muted"]))
        if q.act is None:
            txt_r(d, "press: actions", R, PAGE_ROW, "sans12", pc["muted"], bg)
        return
    badge(d, "B", W - 54, PAGE_ROW + 8, "raised", "text")
    txt(d, "Back", W - 41, PAGE_ROW, "sans12", pc["muted"], bg)


def draw_summary(q):
    d, e = q.d, q.cur
    r = e["r"]
    lvl = r["level"]
    right = R - chain_pill(d, q, R, 33, True, False) - 6
    x = txt(d, "#%d" % e["n"], M, 33, "bold14", "muted")
    con = r.get("contract")
    if con:
        name, lg, known = ident(q, con)
        if known and lg:
            logo(d, lg, x + 14, 42, 8)
            room = right - x - 26
            if F.width(name + " known", "bold14") <= room:
                x = txt(d, name, x + 26, 33, "bold14")
                txt(d, " known", x, 34, "sans12", "ok")
            else:
                txt(d, fit(name, room, "bold14"), x + 26, 33, "bold14")
        elif not known:
            warn_sign(d, x + 14, 43, 8)
            txt(d, fit("Unknown contract", right - x - 26, "bold14"), x + 26, 33, "bold14", "warn")
    else:
        logo(d, "send", x + 14, 42, 8)
        txt(d, "transfer", x + 26, 34, "sans12", "muted")
    y = 54
    for line in F.wrap(r["summary"], TW, "bold26")[:2]:
        txt(d, line, M, y, "bold26", {"red": "bad", "warn": "warn"}.get(lvl, "text"))
        y += 29
    items = r["items"]
    if con and not ident(q, con)[2] and len(items) == 1:
        x = txt(d, "calls ", M, y + 2, "sans14", "muted")
        txt(d, short(con), x, y + 3, "mono13", "warn")
        y += 22
    elif len(items) == 1 and items[0].get("to") and items[0]["to"] != con:
        to = items[0]["to"]
        name, lg, known = ident(q, to)
        tag = tag_for(q, to, items[0])
        x = txt(d, items[0].get("label", "to") + " ", M, y + 2, "sans14", "muted")
        if tag and tag[0] == "lookalike":
            x = txt(d, short(to), x, y + 3, "mono13", "bad")
        elif lg:
            logo(d, lg, x + 7, y + 11, 7)
            x = txt(d, name, x + 18, y + 2, "bold14")
        elif name:
            x = txt(d, name, x, y + 2, "bold14")
        else:
            x = txt(d, short(to), x, y + 3, "mono13")
        if tag:
            tag_pill(d, tag[0], tag[1], x + 6, y + 2, page_colors("ok"), "bg")
        elif not name and not lg:
            pill(d, "unknown", x + 6, y + 2, "sans12", "warn_bg", "warn")
        y += 22
    elif len(items) > 1:
        for i, it in enumerate(items[:3]):
            txt(d, "%d" % (i + 1), M, y + 1, "sans12", "faint")
            txt(d, it["what"], M + 14, y, "sans14", {"red": "bad", "warn": "warn"}.get(it["level"], "text"))
            y += 18
        y += 2
    y += 4
    d.hline(M, y, TW, c("line"))
    y += 8
    have, need = len(e["conf"]), q.threshold()
    x = txt(d, "%d of %d" % (have, need), M, y, "bold14") + 12
    for a in q.owners():
        done = a in e["conf"]
        nm = "You" if a == q.me else (ident(q, a)[0] or short(a))
        w = 12 + F.width(nm, "sans14") + 12
        if x + w > W - 4:
            x, y = M + 58, y + 20
        col = "ok" if done else ("stake" if a == q.me else "faint")
        d.ellipse(x + 4, y + 10, 4, 4, c(col), done)
        txt(d, nm, x + 12, y, "sans14", "text" if done or a == q.me else "muted")
        x += w
    y += 23
    ok, why = q.can_sign(e)
    if q.signed_by_me(e):
        line, col = "You signed this one", "ok"
    elif not ok:
        line, col = "You can't sign: " + why, "bad"
    elif have + 1 >= need:
        line, col = "Yours makes it %d of %d · ready" % (have + 1, need), "ok"
    else:
        line, col = "Yours makes it %d of %d" % (have + 1, need), "text"
    txt(d, fit(line, TW, "bold14"), M, y, "bold14" if col == "ok" else "sans14", col)
    y += 22
    reds = sum(1 for it in items if it["level"] == "red")
    if reds:
        pill(d, "%d red page%s — read %s" % (reds, "s" if reds > 1 else "", "them" if reds > 1 else "it"),
             M, min(y, PAGE_ROW - 22), "bold14", "bad_bar", "on_bad")
    elif q.conflicts(e):
        txt(d, "Another proposal shares #%d" % e["n"], M, min(y, PAGE_ROW - 20), "sans14", "warn")


def item_head(d, q, it, pc, title, chip=True):
    d.fill_rect(0, TOP - 2, W, 26, c(pc["head"]))
    x = txt(d, title, M, TOP + 1, "bold14", pc["on_head"], pc["head"])
    if chip and it.get("contract"):
        contract_chip(d, q, it["contract"], R, TOP + 2, pc["on_head"], pc["head"], R - x - 12)


def draw_item(q, i):
    d, e = q.d, q.cur
    it = e["r"]["items"][i]
    lvl = it["level"]
    pc = page_colors(lvl)
    bg = pc["bg"]
    d.fill_rect(0, TOP - 2, W, BOTTOM - TOP + 2, c(bg))
    item_head(d, q, it, pc, it["title"], it.get("to") != it.get("contract"))
    y = TOP + 30
    if e["why"]:
        pill(d, "Refused · only the service's claim", M, y, "sans12", "bad_bar", "on_bad")
        y += 22
    if it.get("amount"):
        a = it["amount"]
        f = "bold26" if F.width(a, "bold26") <= TW else "bold18"
        for line in F.wrap(a, TW, f)[:2]:
            txt(d, line, M, y, f, pc["stake"] if lvl == "red" else pc["text"], bg)
            y += F.height(f) - 5
        y += 4
    for label, a in ((it.get("frm_label", "from"), it.get("frm")), (it.get("label", "to"), it.get("to"))):
        if a:
            y = who_line(d, q, label, a, y, pc, bg, it if a == it.get("to") else None)
    if it.get("text"):
        para(d, it["text"], M, y, TW, "sans14", pc["text"], bg, 17, PAGE_ROW - 2)


def draw_calldata(q, i):
    """The raw call behind an item nobody could fully decode: what to compare with the proposer."""
    d, e = q.d, q.cur
    it = e["r"]["items"][i]
    pc = page_colors(it["level"])
    bg = pc["bg"]
    d.fill_rect(0, TOP - 2, W, BOTTOM - TOP + 2, c(bg))
    item_head(d, q, it, pc, "CALLDATA")
    txt(d, "function", M, TOP + 30, "sans12", pc["muted"], bg)
    txt_r(d, "%d bytes of calldata" % it["size"], R, TOP + 30, "sans12", pc["muted"], bg)
    txt(d, it["selector"], M, TOP + 42, "monob28", pc["stake"], bg)
    y = TOP + 82
    txt(d, "digest (ERC-8213): compare it", M, y, "sans12", pc["muted"], bg)
    for line in hash_lines(it["digest"]):
        y += 14
        txt(d, line, M, y, "mono13", pc["text"], bg)


def draw_verify(q):
    d, e = q.d, q.cur
    txt_c(d, "Check with the proposer", 32, "bold18")
    txt_c(d, "The Safe tx hash ends in", 54, "sans12", "muted")
    code = e["mine"][-8:]
    txt_c(d, code[:4] + " " + code[4:], 64, "monob28", "stake")
    blockies.draw(d, e["mine"], M, 110, 5)
    y = 104
    for k, line in enumerate(hash_lines(e["mine"])):
        txt(d, ("0x" if k == 0 else "  ") + line, 58, y, "mono13", "text" if k == 3 else "muted")
        y += 14
    mark(d, True, M + 7, 173, 7)
    v, ok = q.safe_version()
    txt(d, "Hashed here, Safe v%s rules" % v if v else "Hashed here from the fields shown", M + 20, 165, "sans12",
        "ok" if ok or not v else "bad")


def draw_refused(q):
    d, e = q.d, q.cur
    bg = "bad_bg"
    d.fill_rect(0, TOP - 2, W, BOTTOM - TOP + 2, c(bg))
    mark(d, False, M + 13, TOP + 20, 13)
    txt(d, "Refused", M + 34, TOP + 3, "bold26", "bad_text", bg)
    y = para(d, e["why"], M, TOP + 42, TW, "sans14", "bad_text", bg, 17, TOP + 42 + 17 * 4) + 6
    txt(d, "asks for", M, y + 1, "sans12", "bad_muted", bg)
    txt(d, e["h"][:10] + "…" + e["h"][-8:], M + 66, y, "mono13", "bad_text", bg)
    if e["mine"]:
        txt(d, "fields are", M, y + 19, "sans12", "bad_muted", bg)
        txt(d, e["mine"][:10] + "…" + e["mine"][-8:], M + 66, y + 18, "mono13", "stake", bg)


def draw_review(q):
    d = q.d
    kind, i = q.pages[q.page]
    pc = page_colors("ok")
    d.fill(c("bg"))
    if kind == "summary":
        draw_summary(q)
    elif kind == "item":
        draw_item(q, i)
        pc = page_colors(q.cur["r"]["items"][i]["level"])
    elif kind == "calldata":
        draw_calldata(q, i)
        pc = page_colors(q.cur["r"]["items"][i]["level"])
    elif kind == "verify":
        draw_verify(q)
    else:
        draw_refused(q)
        pc = page_colors("red")
    sign_bar(q)
    page_row(q, pc)
    if q.KNOB:
        action_bar(q)
    else:
        reject_bar(q)
    if q.state == "hold":
        draw_hold(q)
    d.show()


def draw_hold(q):
    d = q.d
    need = q.hold_need(q.cur)
    el = min(need, time.ticks_diff(time.ticks_ms(), q.hold_t0))
    red = need > q.HOLD_MS
    rrect(d, OX + 14, 58, 212, 112, 10, "bad_bar" if red else "ok")
    rrect(d, OX + 16, 60, 208, 108, 9, "surface")
    txt_c(d, "Keep holding " + ("the knob" if q.hold_key == "press" else q.hold_key), 72, "bold18", "text", "surface")
    rrect(d, OX + 30, 104, 180, 14, 7, "raised")
    w = 180 * el // need
    if w >= 14:
        rrect(d, OX + 30, 104, w, 14, 7, "ok")
    txt_c(d, "%.1f s to go" % ((need - el) / 1000), 124, "sans14", "muted", "surface")
    txt_c(d, "Red: %d s, not %d" % (need // 1000, q.HOLD_MS // 1000) if red else "Let go to cancel", 144, "sans12",
          "bad" if red else "faint", "surface")


# ----------------------------------------------------------------------------- the rest
def draw_working(q, title, sub):
    d = q.d
    d.fill(c("bg"))
    rrect(d, OX + 70, 60, 100, 8, 4, "raised")
    rrect(d, OX + 70, 60, 60, 8, 4, "stake")
    txt_c(d, title, 86, "bold26")
    if q.cur:
        txt_c(d, "#%d %s" % (q.cur["n"], q.cur["r"]["summary"]), 126, "sans14", "text")
    txt_c(d, sub, 148, "sans12", "muted")
    d.show()


def draw_result(q):
    d = q.d
    ok, title, lines = q.result
    d.fill(c("bg"))
    mark(d, ok, W // 2, 56, 28)
    txt_c(d, title, 92, "bold26")
    y = 132
    for k, s in enumerate(lines):
        for line in F.wrap(s, TW, "sans14"):
            txt_c(d, line, y, "bold14" if k == 0 else "sans14", ("ok" if ok else "bad") if k == 0 else "text")
            y += 19
    if q.KNOB and not ok and q.unsent:
        knob_choices(d, q, (("send", "Send again"), ("back", "Back")), ("send", "back")[q.ract], "turn \u00b7 press")
    else:
        footer_hints(q.d, q, (("A", "Send again"), ("B", "Back")) if not ok and q.unsent else (("A", "OK"),))
    d.show()


def draw_owners(q):
    d = q.d
    d.fill(c("bg"))
    txt(d, fit(q.SAFE["name"], 110, "bold18") if len(q.WATCH) > 1 else "Owners", M, 4, "bold18")
    if q.owners():
        txt_r(d, "%d of %d must approve" % (q.threshold(), len(q.owners())), R, 9, "sans12", "muted")
    y = 34
    for a in q.owners()[:4]:
        nm = ident(q, a)[0]
        x = txt(d, nm or "Not in the address book", M, y, "bold14", "text" if nm else "warn")
        if a == q.me:
            pill(d, "you", x + 6, y + 1, "sans12", "stake", "bg")
        y += 19
        for line in addr_lines(a):
            txt(d, line, M, y, "mono13", "muted")
            y += 14
        y += 7
    version_pill(d, q, M, 193)
    k = "this key " + (q.fingerprint() or "none")
    if q.counter is not None:
        k += " \u00b7 use #%d" % q.counter
    txt_r(d, k, R, 195, "sans12", "faint")
    footer_hints(d, q, (("B", "Back"),))
    d.show()


def draw_nochip(q):
    d = q.d
    d.fill(c("bg"))
    mark(d, False, W // 2, 60, 22)
    txt_c(d, "No chip", 94, "bold26")
    y = 136
    for line in ("No ATECC608 answered on I2C.", "The console only signs with", "a key inside the chip.", "",
                 "Wire the chip, then press " + ("the knob." if q.KNOB else "A.")):
        txt_c(d, line, y, "sans14", "muted")
        y += 19
    d.show()


def notice(q, ok, title, lines, hints=()):
    """A plain page: a mark, a title and a few lines. The states where the console signs nothing."""
    d = q.d
    d.fill(c("bg"))
    mark(d, ok, W // 2, 44, 20)
    txt_c(d, title, 72, "bold26")
    y = 110
    for k, s in enumerate(lines):
        for line in F.wrap(s, TW, "sans14"):
            if y > 200:
                break
            txt_c(d, line, y, "sans14", "text" if k == 0 else "muted")
            y += 18
    if hints:
        footer_hints(d, q, hints)
    d.show()


def draw_pinfail(q):
    """The chip, slot or key is not the one secrets.QUORUM_EXPECT pins, or nothing is pinned."""
    d = q.d
    exp = q.EXPECT or {}
    d.fill(c("bg"))
    mark(d, False, W // 2, 36, 18)
    txt_c(d, "Not the pinned key" if q.EXPECT else ("Not a pinned chip" if q.EXPECTS else "Not pinned"), 60, "bold18")
    txt_c(d, fit(q.pin_why or "", W - 16, "sans14"), 84, "sans14", "bad")
    y = 110
    rows = (("chip", q.serial[-8:] or "none", str(exp.get("serial", ""))[-8:] or "-"),
            ("slot", str(q.sig.slot) if q.sig else "-", str(exp.get("slot", "-"))),
            ("owner", short(q.me) if q.me else "none", short(str(exp["owner"])) if exp.get("owner") else "-"))
    txt(d, "here", 64, y, "sans12", "muted")
    txt(d, "pinned", 156, y, "sans12", "muted")
    y += 16
    for k, a, b in rows:
        txt(d, k, M, y, "sans12", "muted")
        txt(d, fit(a, 88, "mono13"), 64, y, "mono13", "text" if a == b else "bad")
        txt(d, fit(b, 80, "mono13"), 156, y, "mono13", "text")
        y += 18
    txt_c(d, "Nothing will be signed." if q.EXPECT else "tools/fw pin adds this chip.", 190, "sans14", "muted")
    footer_hints(d, q, (("A", "Check again"),))
    d.show()


def draw_unconfigured(q):
    notice(q, False, "No Safe", ["secrets.py has no QUORUM_SAFES.", "This console signs only for the Safes",
                                "listed there (docs/guide/SETUP.md)."])


def draw_crashed(q, why=""):
    import image
    how = "Holding the knob 3 s restarts it" if q.KNOB else "B restarts it"
    notice(q, False, "Stopped", ["The console failed %d times in a row and signs nothing now." % q.fails,
                                why[:60], "build " + image.BUILD, how + "; error.log has the details."],
           () if q.KNOB else (("B", "Restart"),))


def draw_device(q):
    import image, gc
    d = q.d
    d.fill(c("bg"))
    txt(d, "Device", M, 4, "bold18")
    txt_r(d, image.IMAGE + " " + image.BUILD, R, 9, "sans12", "muted")
    import chips
    name = q.chip["name"] + " \u00b7 " if q.chip else ""
    rows = [("Chip", (name + (q.serial[-8:] if q.serial else (q.sig.name if q.sig else "none")))[:22]),
            ("Slot", "%d%s \u00b7 %s" % (q.sig.slot if q.sig else -1, " locked" if q.row and q.row.get("locked") else "",
                                         chips.PROFILE_SHORT.get(q.profile, q.profile or "-"))),
            ("Key", q.fingerprint() or "none"),
            ("Pin", "ok" if q.pin_ok and q.EXPECT else ("dev: none" if q.pin_ok else "FAIL")),
            ("Key uses", "#%d" % q.counter if q.counter is not None else "not counted"),
            ("Service", ("%s \u00b7 %d req" % (q.svc.tls, q.svc.requests)) if q.svc else "none"),
            ("Polls", "%d s / %d s idle" % (q.POLL_MS // 1000, q.IDLE_POLL_MS // 1000)),
            ("Memory", "%d KB free" % (gc.mem_free() // 1024))]
    y = 32
    for k, v in rows:
        txt(d, k, M, y, "sans14", "muted")
        txt_r(d, v, R, y, "mono13", "bad" if v == "FAIL" else "text")
        y += 20
    if q.net_err and not q.net_ok:
        txt(d, fit("Last error: " + q.net_err, TW, "sans12"), M, y + 2, "sans12", "warn")
    footer_hints(d, q, (("B", "Back"),))
    d.show()


def draw(q):
    s = q.state
    if s == "nochip":
        draw_nochip(q)
    elif s == "pinfail":
        draw_pinfail(q)
    elif s == "unconfigured":
        draw_unconfigured(q)
    elif s == "crashed":
        draw_crashed(q)
    elif s == "device":
        draw_device(q)
    elif s in ("review", "hold"):
        draw_review(q)
    elif s == "result":
        draw_result(q)
    elif s == "owners":
        draw_owners(q)
    elif s == "working":
        draw_working(q, "Working", "")
    else:
        draw_home(q)
