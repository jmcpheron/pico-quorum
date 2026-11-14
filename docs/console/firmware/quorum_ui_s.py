# The console's screens for a small panel (board.py SMALL: the 1.8" as 160x128), drawn from
# quorum.py's state like quorum_ui.py, whose drawing kit and colours this borrows. The plan is
# docs/quorum-ui/SCREENS.md, "a pocket signer, one fact per screen": the same flow and the same
# six rules, cut into more, smaller pages. pages_of() says what they are; quorum.py counts them
# for "see every page" exactly as it counts the big ones.
#
# Every screen: a 16 px header (what this is, and which page of how many), the page, and an 18 px
# footer. On a review the footer holds the knob's three actions, SIGN, REJECT and BACK, lit only
# while the knob is on them; SIGN is green only once every page has been seen.
#
# The Feather (240x135, lcd.THREE) has no footer and no knob: a strip down the left edge, the rail,
# names what each of its three buttons does on this screen, level with the button (board.RAIL_Y):
# an icon over a word. On a review: Reject, Next, and Sign, which fills the strip while it is held.
# Home is four tabs (draw_tabs), each button working the strip level with it: D0 the tabs along the
# top, D1 the list in the middle, D2 the bar along the bottom, which says what it does.
#
# console-rp (240x135, THREE without RAIL_Y) has its three buttons under the screen: no rail, and an
# 18 px footer names them instead, D0 D1 D2 left to right (slots, from PR #91's QT Py footer). Sign's
# slot fills while it is held. These are its screens with no effects, for bring-up and the tests.
import time
import board
import lcd as L
import fonts as F
import blockies
import quorum_ui as B
from quorum_ui import c, txt, txt_r, fit, para, rrect, pill, mark, warn_sign, logo, ident, short, page_colors, thick_line

W, H = L.W, L.H
SLOTS = L.THREE and not board.RAIL_Y     # three buttons, named in a footer (console-rp)
RAIL = 36 if L.THREE and not SLOTS else 0     # the Feather's rail; the screens start right of it
X0 = RAIL
M = X0 + 5                      # side margin
R = W - 5
TW = R - M
CX = (X0 + W) // 2              # the middle of what the screens draw on
HEAD = 16                       # header strip
FOOT = H if RAIL else H - 18    # footer from here down (the Feather has none)
PER = 4 if L.THREE else 3       # four-character chunks a line, in an address or a hash
use = B.use


def txt_c(d, s, y, font, fg="text", bg="bg", x0=X0, x1=W):
    return B.txt_c(d, s, y, font, fg, bg, x0, x1)


# ----------------------------------------------------------------------------- pages
def tag(e):
    """#nonce, or #? for one the console couldn't read (quorum.bad_entry, big_entry)."""
    return "#%d" % e["n"] if e["n"] >= 0 else "#?"


def pages_of(e):
    """The small screen's pages for one transaction, in order: what it does, each call and each
    address in it on a page of its own, the calldata and its digest, who has approved, then the
    code to compare and the whole hash. A refused one: why, then its calls."""
    out = []
    for i, it in enumerate(e["r"]["items"]):
        out.append(("item", i))
        if it.get("amount") and it.get("text"):
            out.append(("text", i))
        if it.get("frm"):
            out.append(("frm", i))
        if it.get("to"):
            out.append(("to", i))
        if it.get("digest"):
            out.append(("calldata", i))
            out.append(("digest", i))
    if e["why"]:
        return [("refused", 0)] + out
    return [("head", 0)] + out + [("approvals", 0), ("verify", 0), ("hash", 0)]


def addr_lines(a):
    """40 hex as PER four-character chunks a line: 0x7099 7970 c518 / 12dc 3a01 0c7d / ..."""
    h = a[2:].lower() if a.startswith("0x") else a.lower()
    ch = [h[i:i + 4] for i in range(0, len(h), 4)]
    return ["0x" + " ".join(ch[:PER])] + ["  " + " ".join(ch[i:i + PER]) for i in range(PER, len(ch), PER)]


def header(d, left, right, fill="surface", ink="text", sub="muted", gap=6):
    """The top strip: left in bold, right in small type; gap pixels kept free between them.
    Returns the x where the right-hand text starts."""
    d.fill_rect(0, 0, W, HEAD, c(fill))
    xr = R
    if right:
        txt_r(d, right, R, 0, "sans12", sub, fill)
        xr = R - F.width(right, "sans12")
    txt(d, fit(left, xr - gap - M, "bold14"), M, -2, "bold14", ink, fill)
    return xr


def footer_msg(d, q, bg="bg"):
    """The last message over the footer (the Feather: along the bottom), if there is one. True
    when it drew."""
    if not q.msg:
        return False
    y = FOOT - 17 if L.THREE else FOOT
    d.fill_rect(X0, y, W - X0, FOOT - y if L.THREE else H - y, c(bg))
    txt_c(d, fit(q.msg, TW, "sans12"), y + 1, "sans12", "warn", bg)
    return True


BACK = ("Back", "raised", "text")
NEXT = ("Next", "raised", "text")
OPEN = ("Open", "raised", "text")
TAB = ("Tab", "raised", "text")
# The rail's icon for each word: the dot is open or OK (a remote's middle button), the arrow the
# next tab, the chevrons back and down.
ICONS = {"Back": "back", "Next": "down", "Full": "down", "Open": "dot", "OK": "dot", "Code": "dot", "Check": "dot",
         "Try": "dot", "Retry": "dot", "Hold": "dot", "Tab": "arrow", "Reject": "x", "No": "x", "Sign": "check",
         "Save": "check", "Allow": "check"}


def icon(d, kind, cx, cy, ink):
    """A 9 px icon centred on (cx, cy)."""
    col = c(ink)

    def seg(x0, y0, x1, y1):
        thick_line(d, x0, y0, x1, y1, ink, 2)
    if kind == "back":
        seg(cx + 2, cy - 4, cx - 2, cy); seg(cx - 2, cy, cx + 2, cy + 4)
    elif kind == "down":
        seg(cx - 4, cy - 2, cx, cy + 2); seg(cx, cy + 2, cx + 4, cy - 2)
    elif kind == "x":
        seg(cx - 3, cy - 3, cx + 3, cy + 3); seg(cx - 3, cy + 3, cx + 3, cy - 3)
    elif kind == "check":
        seg(cx - 4, cy, cx - 1, cy + 3); seg(cx - 1, cy + 3, cx + 4, cy - 3)
    elif kind == "arrow":
        d.fill_rect(cx - 6, cy - 1, 9, 2, col)
        seg(cx + 1, cy - 4, cx + 5, cy); seg(cx + 5, cy, cx + 1, cy + 4)
    elif kind == "dot":
        d.ellipse(cx, cy, 4, 4, col, True)
    elif kind == "eye":
        d.ellipse(cx, cy, 6, 3, col)
        d.ellipse(cx, cy, 1, 1, col, True)


def rail(d, q, labels=(None, None, None), bg="bg", hold=None, span=W):
    """The Feather: what D0, D1 and D2 do here, each label level with its button (an icon over a
    word, ICONS), and the last message along the bottom. labels: three (text, fill, ink), or None
    where a button does nothing. hold: (fraction, red) while Sign is held, the strip filling from
    the bottom. console-rp: the same in its footer (slots), across the left span px."""
    footer_msg(d, q, bg)
    if SLOTS:
        slots(d, labels, bg, hold, span)
        return
    d.fill_rect(0, 0, RAIL, H, c("surface"))
    if hold:
        h = int(H * min(1, hold[0]))
        d.fill_rect(0, H - h, RAIL, h, c("bad_bar" if hold[1] else "ok"))
    d.vline(RAIL, 0, H, c("raised"))
    for y, lab in zip(board.RAIL_Y, labels):
        if lab:
            s, fill, ink = lab
            ic = "eye" if s.startswith("See ") else ICONS.get(s)
            bh = 31 if ic else 16
            s = fit(s, RAIL - 2, "sans12")
            top = max(0, min(H - bh, y - bh // 2))
            rrect(d, 1, top, RAIL - 2, bh, 6 if ic else 7, fill)
            if ic:
                icon(d, ic, RAIL // 2, top + 8, ink)
            txt(d, s, 1 + (RAIL - 2 - F.width(s, "sans12")) // 2, top + (14 if ic else 0), "sans12", ink, fill)


CAPS = False                    # quorum_ui_crt: each slot starts with its button's cap, as on the case


def cap(d, i, x, y, ink):
    """The case's cap on D0, D1, D2 (cad/consoles/rp.py): a square, a circle, a triangle, 8 px."""
    col = c(ink)
    if i == 0:
        d.fill_rect(x, y + 1, 7, 7, col)
    elif i == 1:
        d.ellipse(x + 3, y + 4, 3, 3, col, True)
    else:
        for k in range(7):
            d.hline(x + 3 - k // 2, y + 1 + k, k // 2 * 2 + 1, col)


def slots(d, labels, bg, hold, span=W):
    """console-rp's footer: D0, D1 and D2 left to right, a slot each, empty where a button does
    nothing here. While Sign is held its slot fills from the left. A narrower span (the key's QR
    code beside it) is shared by the slots up to the last one in use."""
    d.fill_rect(0, FOOT, span, H - FOOT, c(bg))
    n = 3 if span >= W else 1 + max([i for i, lab in enumerate(labels) if lab] or [0])
    sw = (span - 2 - 2 * n) // n
    for i, lab in enumerate(labels):
        if not lab:
            continue
        s, fill, ink = lab
        x = 2 + i * (sw + 2)
        rrect(d, x, FOOT + 1, sw, H - FOOT - 2, 4, "surface" if hold and i == 2 else fill)
        if hold and i == 2:
            w = int(sw * min(1, hold[0]))
            on = "bad_bar" if hold[1] else "ok"
            if w >= 8:
                rrect(d, x, FOOT + 1, w, H - FOOT - 2, 4, on)
            fill, ink = (on if 2 * w >= sw else "surface"), "text"     # light on both: it straddles the edge
        g = 11 if CAPS else 0
        s = fit(s, sw - 4 - g, "sans12")
        x1 = x + (sw - F.width(s, "sans12") - g) // 2
        if CAPS:
            cap(d, i, x1, FOOT + 4, ink)
        txt(d, s, x1 + g, FOOT + 1, "sans12", ink, fill)


def footer_press(d, q, what, bg="bg"):
    """What a press does, after the knob's mark."""
    if footer_msg(d, q, bg):
        return
    B.knob_badge(d, M + 7, FOOT + 9, "raised", "text")
    x = txt(d, "press", M + 19, FOOT + 1, "sans12", "faint", bg)
    txt(d, what, x + 5, FOOT, "bold14", "text", bg)


def choices(d, q, items, focus, bg="bg"):
    """Pills the knob (D1 on the Feather) moves onto, right-aligned, the one in focus lit."""
    y = FOOT - 18 if L.THREE else FOOT + 1
    if not L.THREE:
        if footer_msg(d, q, bg):
            return
        B.knob_badge(d, M + 7, FOOT + 9, "raised", "text")
    x = R
    for key, label in reversed(items):
        on = key == focus
        x -= F.width(label, "sans12") + 12
        pill(d, label, x, y, "sans12", "stake" if on else "surface", "bg" if on else "muted")
        x -= 4


# ----------------------------------------------------------------------------- home
def draw_home(q):
    if L.THREE:
        return draw_tabs(q)
    d = q.d
    d.fill(c("bg"))
    n_own, need = len(q.owners()), q.threshold()
    right = ("%d/%d" % (need, n_own)) if n_own else ""
    ok = q.net_ok
    xr = header(d, q.SAFE["name"], right, gap=14)
    d.ellipse(xr - 7, 8, 3, 3, c("ok" if ok else "bad"), True)
    todo = sum(1 for e in q.queue if q.waiting(e))
    y = HEAD + 2
    txt(d, ("WAITING \u00b7 %d" % todo) if todo else ("QUEUE" if ok else "OFFLINE"), M, y,
        "bold14" if todo else "sans12", "warn" if todo else ("muted" if ok else "bad"))
    if q.queue:
        txt_r(d, "%d queued" % len(q.queue), R, y + 2, "sans12", "faint")
    y = 38
    if not q.queue:
        known = [w for w in q.WATCH if w["ok"] and q.owners(w)]
        added = not known or any(q.me in q.owners(w) for w in known)
        mark(d, ok and added, M + 13, y + 22, 10)
        txt(d, ("Nothing to sign" if added else "Not an owner yet") if ok else "No service", M + 29, y + 10, "bold14")
        if not ok:
            txt(d, fit(q.net_err, TW, "sans12"), M, y + 36, "sans12", "muted")
        elif not added:
            txt(d, fit("Add this key to the Safe: Key, below" if L.THREE else "Add this key to the Safe", TW, "sans12"),
                M, y + 36, "sans12", "muted")
    rows = 2 if q.outside else 3
    top = max(0, min(q.sel - (rows - 1), len(q.queue) - rows))
    for i in range(top, min(len(q.queue), top + rows)):
        e = q.queue[i]
        lvl = "red" if e["why"] else e["r"]["level"]
        sel = i == q.sel and not q.foot
        fill = "raised" if sel else "surface"
        rrect(d, X0 + 2, y, W - X0 - 4, 22, 4, fill)
        if lvl != "ok":
            d.fill_rect(X0 + 2, y + 4, 3, 14, c("bad" if lvl == "red" else "warn"))
        x = txt(d, tag(e), X0 + 8, y + 2, "mono13", "warn" if q.conflicts(e) else "faint", fill)
        if q.signed_by_me(e):
            st, sc = "done", "ok"
        elif e["h"] in q.declined:
            st, sc = "rej", "bad"
        elif e["why"]:
            st, sc = "\u2014", "bad"
        else:
            st, sc = "%d/%d" % (len(e["conf"]), q.threshold(e["w"])), "muted"
        txt_r(d, st, R - 2, y + 3, "sans12", sc, fill)
        xs = R - 2 - F.width(st, "sans12")
        what = ("Refused" if e["why"] else e["r"]["summary"])
        f = "bold14" if sel else "sans12"
        txt(d, fit(what, xs - x - 10, f), x + 5, y + (1 if sel else 3), f, {"red": "bad", "warn": "warn"}.get(lvl, "text"), fill)
        y += 24
    if q.outside:
        rrect(d, X0 + 2, y, W - X0 - 4, 22, 4, "warn_bg")
        warn_sign(d, X0 + 12, y + 11, 7)
        txt(d, fit("key used %d times elsewhere" % q.outside, TW - 24, "sans12"), X0 + 24, y + 3, "sans12", "warn_text", "warn_bg")
    choices(d, q, (("owners", "Owners"), ("device", "Device")) + ((("key", "Key"),) if L.THREE else ()), q.foot)
    if L.THREE:
        rail(d, q, (BACK if q.foot or q.browse else None, NEXT, OPEN if q.queue or q.foot else None))
    d.show()


# ----------------------------------------------------------------------------- home on three buttons
TAB_NAMES = {"queue": "Queue", "owners": "Owners", "key": "Key", "device": "Device"}
DEV_ROWS = {"chip": "Chip", "wifi": "Wi-Fi", "practice": "Practice", "about": "About"}


def tab_strip(d, q):
    """The tabs along the top, level with D0; the one in view lit. Queue says how many wait."""
    d.fill_rect(X0 + 1, 0, W - X0 - 1, HEAD + 1, c("surface"))
    todo = sum(1 for e in q.queue if q.waiting(e))
    x = M - 3
    for i, t in enumerate(q.TABS):
        on = i == q.tab
        name = TAB_NAMES[t] + (" %d" % todo if t == "queue" and todo else "")
        w = F.width(name, "sans12") + 12
        if on:
            rrect(d, x, 1, w, 15, 7, "stake")
        txt(d, name, x + 6, 0, "sans12", "bg" if on else ("warn" if t == "queue" and todo else "muted"),
            "stake" if on else "surface")
        x += w + 2


def safe_line(d, q, left, ink, font="sans12"):
    """Under the tabs: what this tab is about on the left, the Safe in view, its threshold and the
    service's dot on the right."""
    y = HEAD + 1
    n_own = len(q.owners())
    right = q.SAFE["name"] + (" %d/%d" % (q.threshold(), n_own) if n_own else "")
    wl = F.width(left, font)
    right = fit(right, R - M - wl - 20, "sans12")
    txt_r(d, right, R, y + 1, "sans12", "muted")
    d.ellipse(R - F.width(right, "sans12") - 7, y + 9, 3, 3, c("ok" if q.net_ok else "bad"), True)
    txt(d, left, M, y + (0 if font == "bold14" else 1), font, ink)


def row_box(d, y, on):
    fill = "raised" if on else "surface"
    rrect(d, X0 + 2, y, W - X0 - 4, 22, 4, fill)
    return fill


def rows(d, n, sel, y0, y1, draw_row):
    """Rows of 24 px from y0, as many as fit above y1, scrolled to keep sel in view; a thin bar
    on the right when they don't all fit."""
    k = (y1 - y0) // 24
    top = max(0, min(sel - k + 1, n - k)) if n > k else 0
    y = y0
    for i in range(top, min(n, top + k)):
        draw_row(i, y, i == sel)
        y += 24
    if n > k:
        h = y1 - y0
        bh = max(8, h * k // n)
        d.fill_rect(W - 2, y0, 2, h, c("surface"))
        d.fill_rect(W - 2, y0 + (h - bh) * top // (n - k), 2, bh, c("muted"))


def tx_row(d, q, e, y, on):
    lvl = "red" if e["why"] else e["r"]["level"]
    fill = row_box(d, y, on)
    if lvl != "ok":
        d.fill_rect(X0 + 2, y + 4, 3, 14, c("bad" if lvl == "red" else "warn"))
    x = txt(d, tag(e), X0 + 8, y + 2, "mono13", "warn" if q.conflicts(e) else "faint", fill)
    if q.signed_by_me(e):
        st, sc = "done", "ok"
    elif e["h"] in q.declined:
        st, sc = "rej", "bad"
    elif e["why"]:
        st, sc = "\u2014", "bad"
    else:
        st, sc = "%d/%d" % (len(e["conf"]), q.threshold(e["w"])), "muted"
    txt_r(d, st, R - 2, y + 3, "sans12", sc, fill)
    xs = R - 2 - F.width(st, "sans12")
    what = "Refused" if e["why"] else e["r"]["summary"]
    f = "bold14" if on else "sans12"
    txt(d, fit(what, xs - x - 10, f), x + 5, y + (1 if on else 3), f, {"red": "bad", "warn": "warn"}.get(lvl, "text"), fill)


def bar(d, q, what):
    """Along the bottom, level with D2: what it does here, after its dot."""
    if not what or q.msg:
        return
    y = H - 18 if RAIL else FOOT - 18   # console-rp: over its footer
    d.fill_rect(X0 + 1, y, W - X0 - 1, 18, c("raised"))
    icon(d, "dot", M + 2, y + 9, "text")
    txt(d, fit(what, R - M - 12, "sans12"), M + 12, y + 1, "sans12", "text", "raised")


def draw_tabs(q):
    d = q.d
    d.fill(c("bg"))
    tab_strip(d, q)
    t = q.TABS[q.tab]
    y0, y1 = HEAD + 20, (H if RAIL else FOOT) - 18
    what = None
    if t == "queue":
        ok = q.net_ok
        todo = sum(1 for e in q.queue if q.waiting(e))
        safe_line(d, q, ("WAITING \u00b7 %d" % todo) if todo else ("QUEUE" if ok else "OFFLINE"),
                  "warn" if todo else ("muted" if ok else "bad"), "bold14" if todo else "sans12")
        if not q.queue:
            known = [w for w in q.WATCH if w["ok"] and q.owners(w)]
            added = not known or any(q.me in q.owners(w) for w in known)
            mark(d, ok and added, M + 13, y0 + 22, 10)
            txt(d, ("Nothing to sign" if added else "Not an owner yet") if ok else "No service", M + 29, y0 + 10, "bold14")
            if not ok:
                txt(d, fit(q.net_err, TW, "sans12"), M, y0 + 36, "sans12", "muted")
            elif not added:
                txt(d, fit("Add this key to the Safe: the Key tab", TW, "sans12"), M, y0 + 36, "sans12", "muted")
        else:
            if q.outside:
                rrect(d, X0 + 2, y1 - 22, W - X0 - 4, 22, 4, "warn_bg")
                warn_sign(d, X0 + 12, y1 - 11, 7)
                txt(d, fit("key used %d times elsewhere" % q.outside, TW - 24, "sans12"), X0 + 24, y1 - 19, "sans12", "warn_text", "warn_bg")
                y1 -= 24
            rows(d, len(q.queue), q.sel, y0, y1, lambda i, y, on: tx_row(d, q, q.queue[i], y, on))
            e = q.queue[q.sel]
            what = "Open %s %s" % (tag(e), "Refused" if e["why"] else e["r"]["summary"])
    elif t == "owners":
        own = q.owners()
        safe_line(d, q, "OWNERS", "muted")
        sel = q.osel % len(own) if own else 0

        def owner_row(i, y, on):
            a = own[i]
            fill = row_box(d, y, on)
            blockies.draw(d, a.lower(), X0 + 6, y + 3, 2)
            nm = ident(q, a)[0]
            f = ("bold14" if on else "sans12") if nm else "mono13"
            x = txt(d, fit(nm or short(a), TW - (60 if a == q.me else 30), f), X0 + 28, y + (1 if on and nm else 3), f,
                    "text" if nm else "warn", fill)
            if a == q.me:
                pill(d, "you", x + 5, y + 3, "sans12", "stake", "bg")
        rows(d, len(own), sel, y0, y1, owner_row)
        if own:
            nm = ident(q, own[sel])[0]
            what = "Show %s in full" % (nm or short(own[sel]))
        else:
            txt(d, "Not read yet", M, y0 + 4, "sans12", "muted")
    elif t == "key":
        safe_line(d, q, "THIS KEY", "muted")
        if q.me:
            blockies.draw(d, q.me, M, y0 + 2, 6)
            x = M + 56
            txt(d, q.fingerprint() or "-", x, y0, "bold18")
            owner = q.me in q.owners()
            txt(d, fit("an owner" if owner else "not an owner yet", R - x, "sans12"), x, y0 + 24, "sans12",
                "ok" if owner else "warn")
            txt(d, q.me[:6] + "\u2026" + q.me[-4:], x, y0 + 40, "mono13", "stake")
            if q.counter is not None:
                txt(d, "use #%d" % q.counter, x, y0 + 58, "sans12", "faint")
            if q.key_ready():
                what = "Show its code, to add it to a Safe"
        else:
            txt(d, "No key", M, y0 + 4, "bold14")
    else:
        import image
        safe_line(d, q, "DEVICE", "muted")
        vals = {"chip": q.chip["name"] if q.chip else (q.serial[-8:] if q.serial else ""), "wifi": "",
                "practice": "ceremony", "about": image.VERSION or image.BUILD}

        def dev_row(i, y, on):
            k = q.DTAB[i]
            fill = row_box(d, y, on)
            f = "bold14" if on else "sans12"
            txt(d, DEV_ROWS[k], X0 + 8, y + (1 if on else 3), f, "text", fill)
            if vals[k]:
                txt_r(d, fit(vals[k], 90, "sans12"), R - 14, y + 3, "sans12", "muted", fill)
            thick_line(d, R - 7, y + 7, R - 3, y + 11, "text" if on else "muted", 2)
            thick_line(d, R - 3, y + 11, R - 7, y + 15, "text" if on else "muted", 2)
        rows(d, len(q.DTAB), q.dsel, y0, y1, dev_row)
        k = q.DTAB[q.dsel]
        what = {"chip": "Open the chip's pages", "wifi": "Restart into Wi-Fi setup", "practice": "Practise the ceremony",
                "about": "Open the device's facts"}[k]
    bar(d, q, what)
    rail(d, q, (TAB, NEXT if ((t == "queue" and len(q.queue) > 1) or (t == "owners" and len(q.owners()) > 1)
                              or t == "device") else None, OPEN if what else None))
    d.show()


def draw_who(q):
    """An owner from the Owners tab: who it is, the address in full and its picture."""
    d = q.d
    d.fill(c("bg"))
    a = q.who
    header(d, "Owner", "you" if a == q.me else "")
    nm = ident(q, a)[0]
    txt(d, fit(nm or "not in address book", TW, "bold14" if nm else "sans12"), M, HEAD + 3,
        "bold14" if nm else "sans12", "text" if nm else "warn")
    y = HEAD + 24
    for line in addr_lines(a):
        txt(d, line, M, y, "mono13", "stake")
        y += 16
    blockies.draw(d, a.lower(), R - 40, FOOT - 44 if SLOTS else H - 44, 5)
    rail(d, q, (BACK, None, None))
    d.show()


# ----------------------------------------------------------------------------- review pages
def action_bar(q, bg):
    d = q.d
    ok, why = q.can_sign(q.cur)
    ready = ok and not q.unseen()
    d.fill_rect(0, FOOT, W, H - FOOT, c(bg))
    if footer_msg(d, q, bg):
        return
    ws = (58, 54, W - 4 - 58 - 54 - 4)
    x = 2
    for i, (label, on, off, ink_on) in enumerate((("SIGN", "ok" if ready else "raised", "surface", "on_ok" if ready else "text"),
                                                   ("REJECT", "bad_bar", "bad_bg", "on_bad"),
                                                   ("BACK", "raised", "surface", "text"))):
        focus = q.act == i
        fill = on if focus else off
        rrect(d, x, FOOT + 1, ws[i], H - FOOT - 2, 4, fill)
        if focus:
            d.rect(x, FOOT + 1, ws[i], H - FOOT - 2, c("text"))
        txt_c(d, label, FOOT + 1, "sans12", ink_on if focus else ("bad_muted" if i == 1 else "muted"), fill, x, x + ws[i])
        x += ws[i] + 2


def review_labels(q):
    """The Feather's rail on a review: Reject; Next; Sign only once every page has been seen
    (until then D2 shows the next one unseen), grey when this key can't sign this."""
    ok, why = q.can_sign(q.cur)
    left = q.unseen()
    if not ok:
        d2 = ("Sign", "surface", "faint")
    elif left:
        d2 = ("See %d" % len(left), "raised", "warn")
    else:
        d2 = ("Sign", "ok", "on_ok")
    return (("Reject", "bad_bar", "on_bad"), NEXT, d2)


def item_of(q, i):
    return q.cur["r"]["items"][i]


def who_page(d, q, label, a, pc, bg, y):
    """label, who the address is, then all of it, and beside its short last line its blockie: the
    picture Safe{Wallet} and Etherscan draw for the same address."""
    name, lg, known = ident(q, a)
    x = txt(d, label, M, y, "sans12", pc["muted"], bg) + 5
    if lg:
        logo(d, lg, x + 6, y + 8, 6)
        txt(d, fit(name, R - x - 14, "bold14"), x + 14, y - 1, "bold14", pc["text"], bg)
    elif name:
        txt(d, fit(name, R - x, "bold14"), x, y - 1, "bold14", pc["text"], bg)
    elif label == "contract":
        txt(d, "unknown contract", x, y, "sans12", "warn" if bg == "bg" else pc["text"], bg)
    else:
        txt(d, "not in address book", x, y, "sans12", "warn" if bg == "bg" else pc["text"], bg)
    y += 20
    for line in addr_lines(a):
        txt(d, line, M, y, "mono13", pc["stake"], bg)
        y += 15
    s = 5 if L.THREE else 3             # 40 px on the Feather, 24 px on the 1.8"
    blockies.draw(d, a.lower(), R - 8 * s, min(y - 12, FOOT - 8 * s - 1), s)     # under the line above, over the footer


def draw_review(q):
    d, e = q.d, q.cur
    kind, i = q.pages[q.page]
    lvl = "ok"
    if kind in ("item", "text", "frm", "to", "calldata", "digest"):
        lvl = item_of(q, i)["level"]
    elif kind == "refused":
        lvl = "red"
    pc = page_colors(lvl)
    bg = pc["bg"]
    d.fill(c(bg))
    here = q.page + 1 if q.act is None else len(q.pages)
    head = tag(e)
    if kind in ("item", "text", "frm", "to", "calldata", "digest"):
        head += " " + item_of(q, i)["title"]
    elif kind == "head":
        head += " " + q.CFG["chains"].get(str(q.CHAIN), "")
    elif kind in ("approvals", "verify", "hash"):
        head += " " + kind
    header(d, head, "%d/%d" % (here, len(q.pages)), pc["head"], pc["on_head"], pc["on_head"] if lvl != "ok" else "muted")
    y = HEAD + 3
    if kind == "head":
        r = e["r"]
        con = r.get("contract")
        if con:
            name, lg, known = ident(q, con)
            if known and lg:
                logo(d, lg, M + 6, y + 8, 6)
                txt(d, fit(name, TW - 16, "sans12"), M + 15, y, "sans12", "ok")
            else:
                warn_sign(d, M + 6, y + 8, 7)
                txt(d, "unknown contract", M + 16, y, "sans12", "warn")
        else:
            txt(d, "transfer", M, y, "sans12", "muted")
        y += 18
        for line in F.wrap(r["summary"], TW, "bold18")[:3]:
            txt(d, line, M, y, "bold18", {"red": "bad", "warn": "warn"}.get(r["level"], "text"))
            y += 22
        reds = sum(1 for it in r["items"] if it["level"] == "red")
        if reds and y <= FOOT - 18:
            pill(d, "%d red page%s" % (reds, "s" if reds > 1 else ""), M, FOOT - 18, "sans12", "bad_bar", "on_bad")
    elif kind == "item":
        it = item_of(q, i)
        if e["why"]:
            pill(d, "only the service's claim", M, y, "sans12", "bad_bar", "on_bad")
            y += 18
        if it.get("amount"):
            a = it["amount"]
            f = "bold26" if F.width(a, "bold26") <= TW else "bold18"
            for line in F.wrap(a, TW, f)[:2]:
                txt(d, line, M, y, f, pc["stake"] if lvl == "red" else pc["text"], bg)
                y += F.height(f) - 6
        elif it.get("text"):
            para(d, it["text"], M, y, TW, "sans12", pc["text"], bg, 15, FOOT - 2)
        if it.get("amount") and not it.get("text") and it.get("contract") and y < FOOT - 18:
            name, lg, known = ident(q, it["contract"])
            x = txt(d, fit(("on " + name) if known else "unknown contract", TW - 21, "sans12"), M, FOOT - 18, "sans12",
                    pc["muted"] if known else "warn", bg)
            blockies.draw(d, it["contract"].lower(), x + 5, FOOT - 17, 2)     # the token contract's picture
    elif kind == "text":
        para(d, item_of(q, i)["text"], M, y, TW, "sans12", pc["text"], bg, 15, FOOT - 2)
    elif kind in ("frm", "to"):
        it = item_of(q, i)
        label = it.get("frm_label", "from") if kind == "frm" else it.get("label", "to")
        who_page(d, q, label, it[kind], pc, bg, y)
    elif kind == "calldata":
        it = item_of(q, i)
        txt(d, "function", M, y, "sans12", pc["muted"], bg)
        txt(d, it["selector"], M, y + 16, "bold26", pc["stake"], bg)
        txt(d, "%d bytes of calldata" % it["size"], M, y + 54, "sans12", pc["muted"], bg)
        txt(d, "compare the digest", M, y + 70, "sans12", pc["muted"], bg)
    elif kind == "digest":
        for line in B.hash_lines(item_of(q, i)["digest"], per=PER):
            txt(d, line, M, y, "mono13", pc["text"], bg)
            y += 15
    elif kind == "approvals":
        have, need = len(e["conf"]), q.threshold()
        ok, why = q.can_sign(e)
        txt(d, "%d of %d" % (have, need), M, y - 1, "bold18")
        if q.signed_by_me(e):
            s, col = "you signed", "ok"
        elif not ok:
            s, col = "you can't sign", "bad"
        elif have >= need:
            s, col = "already enough", "ok"
        else:
            s, col = "yours: %d of %d" % (have + 1, need), "ok" if have + 1 >= need else "muted"
        txt_r(d, s, R, y + 4, "sans12", col)
        y += 25
        for a in q.owners()[:4]:
            done = a in e["conf"]
            nm = "You" if a == q.me else (ident(q, a)[0] or short(a))
            d.ellipse(M + 4, y + 8, 4, 4, c("ok" if done else ("stake" if a == q.me else "faint")), done)
            txt(d, fit(nm, TW - 34, "sans12"), M + 13, y, "sans12", "text" if done or a == q.me else "muted")
            if L.THREE:                 # room for each owner's blockie, as on Owners
                blockies.draw(d, a.lower(), R - 16, y, 2)
            y += 18 if L.THREE else 16
        if not ok and y <= FOOT - 16:
            txt(d, fit(why, TW, "sans12"), M, FOOT - 16, "sans12", "bad")
    elif kind == "verify":
        txt(d, "Check with the", M, y, "sans12", "muted")
        txt(d, "proposer: ends in", M, y + 14, "sans12", "muted")
        code = e["mine"][-8:]
        txt(d, code[:4], M, y + 30, "monob28", "stake")
        txt(d, code[4:], M, y + 58, "monob28", "stake")
        blockies.draw(d, e["mine"], R - 40, y + 36, 5)
    elif kind == "hash":                # the Safe tx hash, computed here
        y -= 1
        for line in B.hash_lines(e["mine"], per=PER):
            txt(d, line, M, y, "mono13", "text")
            y += 15
    else:       # refused
        mark(d, False, M + 9, y + 10, 9)
        txt(d, "Refused", M + 24, y - 2, "bold18", "bad_text", bg)
        para(d, e["why"], M, y + 24, TW, "sans12", "bad_text", bg, 15, FOOT - 2)
    if L.THREE:
        hold = None
        if q.state == "hold":
            need = q.hold_need(q.cur)
            el = min(need, time.ticks_diff(time.ticks_ms(), q.hold_t0))
            red = need > q.HOLD_MS
            hold = (el / need, red)
            header(d, "Keep holding", "%.1f s" % ((need - el) / 1000), "bad_bar" if red else "ok",
                   "on_bad" if red else "on_ok", "on_bad" if red else "on_ok")
        labels = review_labels(q)
        rail(d, q, (labels[0], None, labels[2]) if hold else labels, bg, hold)     # D1 does nothing while Sign is held
    else:
        action_bar(q, bg)
        if q.state == "hold":
            draw_hold(q)
    d.show()


def draw_hold(q):
    d = q.d
    need = q.hold_need(q.cur)
    el = min(need, time.ticks_diff(time.ticks_ms(), q.hold_t0))
    red = need > q.HOLD_MS
    rrect(d, 8, 24, W - 16, 78, 8, "bad_bar" if red else "ok")
    rrect(d, 10, 26, W - 20, 74, 7, "surface")
    txt_c(d, "Keep holding", 30, "bold14", "text", "surface")
    rrect(d, 20, 56, W - 40, 10, 5, "raised")
    w = (W - 40) * el // need
    if w >= 10:
        rrect(d, 20, 56, w, 10, 5, "ok")
    txt_c(d, "%.1f s to go" % ((need - el) / 1000), 72, "sans12", "bad" if red else "muted", "surface")


# ----------------------------------------------------------------------------- the rest
def draw_working(q, title, sub):
    d = q.d
    d.fill(c("bg"))
    rrect(d, CX - 30, 24, 60, 6, 3, "raised")
    rrect(d, CX - 30, 24, 36, 6, 3, "stake")
    txt_c(d, title, 38, "bold18")
    if q.cur:
        txt_c(d, fit("%s %s" % (tag(q.cur), q.cur["r"]["summary"]), TW, "sans12"), 66, "sans12", "text")
    info = getattr(q, "work_info", None) or ()
    if info:                                    # the chip's own facts (quorum.chip_info): two fit here
        txt_c(d, fit(sub, TW, "sans12"), 84, "sans12", "muted")
        y = 100
        for line in info[:2]:
            txt_c(d, fit(line, TW, "sans12"), y, "sans12", "muted")
            y += 13
    else:
        para(d, sub, M, 84, TW, "sans12", "muted", "bg", 14, H)
    if L.THREE:
        rail(d, q)
    d.show()


def draw_result(q):
    d = q.d
    ok, title, lines = q.result
    d.fill(c("bg"))
    mark(d, ok, M + 12, 16, 12)
    txt(d, fit(title, TW - 30, "bold18"), M + 30, 4, "bold18")
    y = 34
    for k, s in enumerate(lines):
        for line in F.wrap(s, TW, "sans12"):
            if y > FOOT - 15:
                break
            txt(d, line, M, y, "sans12", ("ok" if ok else "bad") if k == 0 else "text")
            y += 14
    if L.THREE:
        rail(d, q, (BACK, None, ("Retry", "stake", "bg")) if not ok and q.unsent else (None, None, ("OK", "raised", "text")))
    elif not ok and q.unsent:
        choices(d, q, (("send", "Send again"), ("back", "Back")), ("send", "back")[q.ract])
    else:
        footer_press(d, q, "OK")
    d.show()


OWNERS_PER_PAGE = 4


def draw_owners(q):
    d = q.d
    d.fill(c("bg"))
    pages = q.owner_pages()
    q.opage = page = min(q.opage, pages - 1)
    header(d, "Owners", ("%d of %d" % (q.threshold(), len(q.owners())) if q.owners() else "") + (" \u00b7 %d/%d" % (page + 1, pages) if pages > 1 else ""))
    y = HEAD + 3
    for a in q.owners()[page * OWNERS_PER_PAGE:(page + 1) * OWNERS_PER_PAGE]:
        nm = ident(q, a)[0]
        x = txt(d, fit(nm or short(a), TW - (56 if a == q.me else 22), "bold14" if nm else "mono13"), M, y,
                "bold14" if nm else "mono13", "text" if nm else "warn")
        if a == q.me:
            pill(d, "you", x + 4, y + 1, "sans12", "stake", "bg")
        blockies.draw(d, a.lower(), R - 16, y + 1, 2)       # 16 px: the picture the Safe app shows for this owner
        y += 20
    k = "key " + (q.fingerprint() or "none")
    if q.counter is not None:
        k += " \u00b7 use #%d" % q.counter
    txt(d, fit(k, TW, "sans12"), M, FOOT - 16, "sans12", "faint")
    if L.THREE:
        rail(d, q, (BACK, NEXT if pages > 1 else None, None))
    else:
        footer_press(d, q, "Back")
    d.show()


def draw_device(q):
    import image, gc, chips
    d = q.d
    d.fill(c("bg"))
    header(d, "Device", image.IMAGE)
    name = q.chip["name"] + " " if q.chip else ""
    rows = [("chip", (name + (q.serial[-8:] if q.serial else (q.sig.name if q.sig else "none")))),
            ("slot", "%s%s %s" % (q.slot_label(), " locked" if q.row and q.row.get("locked") else "",
                                   chips.PROFILE_SHORT.get(q.profile, q.profile or "-"))),
            ("key", q.fingerprint() or "none"),
            ("pin", "ok" if q.pin_ok and q.EXPECT else ("dev: none" if q.pin_ok else "FAIL")),
            ("sec", "%d events" % q.sec) if q.sec is not None else
            ("uses", "#%d" % q.counter if q.counter is not None else "not counted"),
            ("free", "%d KB \u00b7 %s" % (gc.mem_free() // 1024, (image.VERSION or image.BUILD) + (" " + image.RELEASE[:4] if image.RELEASE else "")))]
    y = HEAD + 1
    for k, v in rows:
        txt(d, k, M, y, "sans12", "muted")
        txt_r(d, fit(v, TW - 36, "sans12"), R, y, "sans12", "bad" if v == "FAIL" else "text")
        y += 15
    if L.THREE:
        rail(d, q, (BACK, None, None))      # Chip, Wi-Fi and Practice are rows on the Device tab
    elif q.KNOB:
        choices(d, q, (("chip", "Chip"), ("practice", "Practice"), ("back", "Back")), q.dfoot)
    else:
        footer_press(d, q, "Back")
    d.show()


def chip_layout(pages):
    """The Chip pages split so each fits the small screen, one row a line."""
    per = (FOOT - 14 - HEAD - 1) // 13 + 1
    out = []
    for title, rows in pages:
        for i in range(0, len(rows), per):
            out.append((title, rows[i:i + per]))
    return out


def draw_chip(q):
    """The Chip pages on the small screen: one value a line, cut to fit."""
    d = q.d
    d.fill(c("bg"))
    title, rows = q.chip_pages[q.chip_page]
    header(d, title, "%d/%d" % (q.chip_page + 1, len(q.chip_pages)))
    y = HEAD + 1
    for k, v in rows:
        if y > FOOT - 14:
            break
        kw = 62 if L.THREE else 44         # the label column: the Feather has the room
        txt(d, fit(k, kw, "sans12"), M, y, "sans12", "muted")
        txt(d, fit(str(v), TW - kw - 4, "sans12"), M + kw + 4, y, "sans12", "bad" if str(v).startswith(("FAILED", "MISSING")) else "text")
        y += 13
    if L.THREE:
        rail(d, q, (BACK, NEXT if len(q.chip_pages) > 1 else None, None))
    else:
        footer_press(d, q, "Back")
    d.show()


_qr = (None, 0, b"")


def qr_of(text):
    """qrcode.encode_map, once per text: it scores all eight masks, too slow for every frame. A byte
    per module (_qr[2]), which draw_qr reads: a row as one int is 37 bits, past a small int on a
    32-bit board, so every shift of it made a new big int (76 KB of them a frame)."""
    global _qr
    if _qr[0] != text:
        import qrcode
        _qr = (text,) + qrcode.encode_map(text)
    return _qr[1]


def draw_qr(d, text, x0, y0, size):
    """text as a QR code, dark on white with a 2-module margin, its top left at (x0, y0). -> its
    side in px."""
    n = qr_of(text)
    m = _qr[2]
    q = 2 * size
    box = n * size + 2 * q
    d.fill_rect(x0, y0, box, box, L.WHITE)
    for r in range(n):
        i, x = r * n, 0
        while x < n:                    # one rectangle per run of dark modules
            if m[i + x]:
                e = x
                while e < n and m[i + e]:
                    e += 1
                d.fill_rect(x0 + q + x * size, y0 + q + r * size, (e - x) * size, size, L.BLACK)
                x = e
            else:
                x += 1
    return box


_ck = (None, None)


def checksummed(a):
    """txservice.checksum, once per address: a keccak, ~0.5 s and its big ints on console-rp."""
    global _ck
    if _ck[0] != a:
        import txservice
        _ck = (a, txservice.checksum(a))
    return _ck[1]


def draw_key(q):
    """The Feather's Key screen. Page 0: the app's set-up link for this key as a QR code (97
    characters, 37 modules at 3 px, 123 px with the margin) beside the short owner address and its
    picture, to compare with the page the phone opens. Page 1: the owner address in full. D1
    switches. The link holds only the public key; the owner address is a signer, not a wallet."""
    d = q.d
    d.fill(c("bg"))
    if q.kpage == 0:
        link = q.setup_link()
        n = qr_of(link)
        box = n * 3 + 12
        draw_qr(d, link, W - box, 0 if SLOTS else (H - box) // 2, 3)     # console-rp: over the footer's left
        col = W - box - 4 - M
        txt(d, fit("Set it up", col, "bold14"), M, 0, "bold14")
        txt(d, fit("Scan with", col, "sans12"), M, 18, "sans12", "muted")
        txt(d, fit("your phone", col, "sans12"), M, 31, "sans12", "muted")
        blockies.draw(d, q.me, M, 50, 3)
        txt(d, fit(q.me[:6], col, "mono13"), M + 30, 50, "mono13", "muted")
        txt(d, fit("\u2026" + q.me[-4:], col, "mono13"), M + 30, 64, "mono13", "muted")
        y = 86
        for line in ("A signer,", "not a wallet."):
            txt(d, fit(line, col, "sans12"), M, y, "sans12", "warn")
            y += 14
        labels = (BACK, ("Full", "raised", "text"), None)
    else:
        header(d, "Your key", q.chip["name"] if q.chip else "")
        y = HEAD + 3
        for line in addr_lines(checksummed(q.me)):
            txt(d, line, M, y, "mono13")
            y += 16
        blockies.draw(d, q.me, R - 24, HEAD + 31, 3)      # beside the short last line
        k = "key " + (q.fingerprint() or "none")
        if q.counter is not None:
            k += " \u00b7 use #%d" % q.counter
        txt(d, fit(k, TW, "sans12"), M, y + 2, "sans12", "faint")
        y += 18
        for line in F.wrap("A signer, not a wallet: never send funds to it.", TW, "sans12"):
            txt(d, line, M, y, "sans12", "warn")
            y += 14
        labels = (BACK, ("Code", "raised", "text"), None)
    rail(d, q, labels, span=W - box - 2 if SLOTS and q.kpage == 0 else W)
    d.show()


def notice(q, ok, title, lines, press=None, d2=None):
    """A plain page: a mark, a title and a few lines. The states where the console signs nothing.
    press: what the knob's press does; d2: the Feather's label for D2."""
    d = q.d
    d.fill(c("bg"))
    mark(d, ok, M + 11, 13, 10)
    txt(d, fit(title, TW - 28, "bold18"), M + 27, 1, "bold18")
    y = 30
    for k, s in enumerate(lines):
        for line in F.wrap(s, TW, "sans12"):
            if y > FOOT - 15:
                break
            txt(d, line, M, y, "sans12", "text" if k == 0 else "muted")
            y += 14
    if L.THREE:
        rail(d, q, (None, None, (d2, "raised", "text") if d2 else None))
    elif press:
        footer_press(d, q, press)
    d.show()


def draw_nochip(q):
    notice(q, False, "No chip", ["No secure element answered on I2C.", "The console only signs with a key inside the chip.",
                                 "It looks again every %d s." % (q.NOCHIP_EVERY_MS // 1000)], "Check again", "Check")


def draw_pinfail(q):
    exp = q.EXPECT or {}
    title = "Not the pinned key" if q.EXPECT else ("Not a pinned chip" if q.EXPECTS else "Not pinned")
    lines = [q.pin_why or "", "here   " + (q.serial[-8:] or "none"), "pinned " + (str(exp.get("serial", ""))[-8:] or "-"),
             "Nothing will be signed." if q.EXPECT else "tools/fw pin adds this chip."]
    notice(q, False, title, lines, "Check again", "Check")


def draw_unconfigured(q):
    if L.THREE and q.key_ready():
        notice(q, True, "Your key is ready", ["Next, it is added to a Safe.",
                                              board.NAMES["D2"] + " shows its code, for the person setting it up.",
                                              "secrets.py: no QUORUM_SAFES yet"], None, "Code")
    elif not q.me:
        notice(q, False, "No key yet", ["The chip has no key. It is made in the ceremony, on a computer.",
                                        board.NAMES["D2"] + ": practise it here. Nothing is written."],
               "Practice", "Try")
    else:
        notice(q, False, "No Safe", ["secrets.py has no QUORUM_SAFES.", "docs/guide/SETUP.md"])


def draw_crashed(q, why=""):
    import image
    notice(q, False, "Stopped", ["Failed %d times in a row; signs nothing now." % q.fails, why[:40],
                                "build " + image.BUILD, "Hold %s 3 s to restart." % board.NAMES["D2"] if L.THREE else "Hold the knob 3 s to restart."],
           None, "Hold")


def draw_ask(q):
    """An ask from the computer over USB (quorum.ask, usblink.py): its pages, then D2 held accepts,
    as a review's Sign; D0 refuses with one press. Nothing is saved until the hold completes."""
    d = q.d
    a = q.ask
    p = a["pages"][q.apage]
    n = len(a["pages"])
    red = any(x.get("red") for x in a["pages"])
    left = [i for i in range(n) if i not in q.aseen]
    d.fill(c("bg"))
    hold = None
    if q.ahold:
        need = q.ask_need()
        el = min(need, time.ticks_diff(time.ticks_ms(), q.ahold[0]))
        hold = (el / need, red)
        on = "on_bad" if red else "on_ok"
        header(d, "Keep holding", "%.1f s" % ((need - el) / 1000), "bad_bar" if red else "ok", on, on)
    else:
        header(d, p["title"], "USB %d/%d" % (q.apage + 1, n) if n > 1 else "USB",
               "bad_bar" if red else "surface", "on_bad" if red else "text", "on_bad" if red else "muted")
    y = HEAD + 3
    for k, s in enumerate(p["lines"]):
        font = "bold14" if k == 0 else "sans12"
        for line in F.wrap(s, TW - (28 if p.get("addr") and k == 0 else 0), font):
            if y > FOOT - 15:
                break
            txt(d, line, M, y, font, "text" if k == 0 else "muted")
            y += 16 if k == 0 else 14
    if p.get("addr"):
        y += 2
        for line in addr_lines(p["addr"]):
            txt(d, line, M, y, "mono13")
            y += 15
        blockies.draw(d, p["addr"], R - 24, HEAD + 3, 3)
    save = "Allow" if a["kind"] == "maint" else "Save"
    if L.THREE:
        d2 = ("See %d" % len(left), "raised", "warn") if left else (save, "bad_bar" if red else "ok", "on_bad" if red else "on_ok")
        rail(d, q, (("No", "bad_bar", "on_bad"), None if hold else (NEXT if n > 1 else None), d2), "bg", hold)
    elif not footer_msg(d, q):
        txt_c(d, fit("hold the knob: %s · B: no" % save.lower() if q.KNOB else "A held: %s · Y: no" % save.lower(),
                     TW, "sans12"), FOOT + 1, "sans12", "muted")
    d.show()


def draw(q):
    s = q.state
    if s == "ask":
        draw_ask(q)
    elif s == "nochip":
        draw_nochip(q)
    elif s == "pinfail":
        draw_pinfail(q)
    elif s == "unconfigured":
        draw_unconfigured(q)
    elif s == "crashed":
        draw_crashed(q)
    elif s == "chip":
        draw_chip(q)
    elif s == "device":
        draw_device(q)
    elif s in ("review", "hold"):
        draw_review(q)
    elif s == "result":
        draw_result(q)
    elif s == "owners":
        draw_owners(q)
    elif s == "key":
        draw_key(q)
    elif s == "who":
        draw_who(q)
    elif s == "working":
        draw_working(q, "Working", "")
    else:
        draw_home(q)
