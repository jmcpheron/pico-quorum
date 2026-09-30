# The console's screens for a small panel (board.py SMALL: the 1.8" as 160x128), drawn from
# quorum.py's state like quorum_ui.py, whose drawing kit and colours this borrows. The plan is
# docs/quorum-ui/SCREENS.md, "a pocket signer, one fact per screen": the same flow and the same
# six rules, cut into more, smaller pages. pages_of() says what they are; quorum.py counts them
# for "see every page" exactly as it counts the big ones.
#
# Every screen: a 16 px header (what this is, and which page of how many), the page, and an 18 px
# footer. On a review the footer holds the knob's three actions, SIGN, REJECT and BACK, lit only
# while the knob is on them; SIGN is green only once every page has been seen.
import time
import lcd as L
import fonts as F
import blockies
import quorum_ui as B
from quorum_ui import c, txt, txt_r, txt_c, fit, para, rrect, pill, mark, warn_sign, logo, ident, short, page_colors

W, H = L.W, L.H
M = 5                           # side margin
R = W - M
TW = W - 2 * M
HEAD = 16                       # header strip
FOOT = H - 18                   # footer from here down
use = B.use


# ----------------------------------------------------------------------------- pages
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
    """40 hex as 3 four-character chunks a line: 0x7099 7970 c518 / 12dc 3a01 0c7d / ..."""
    h = a[2:].lower() if a.startswith("0x") else a.lower()
    ch = [h[i:i + 4] for i in range(0, len(h), 4)]
    return ["0x" + " ".join(ch[:3])] + ["  " + " ".join(ch[i:i + 3]) for i in range(3, len(ch), 3)]


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
    """The last message over the footer, if there is one. True when it drew."""
    if not q.msg:
        return False
    d.fill_rect(0, FOOT, W, H - FOOT, c(bg))
    txt_c(d, fit(q.msg, TW, "sans12"), FOOT + 1, "sans12", "warn", bg)
    return True


def footer_press(d, q, what, bg="bg"):
    """What a press does, after the knob's mark."""
    if footer_msg(d, q, bg):
        return
    B.knob_badge(d, M + 7, FOOT + 9, "raised", "text")
    x = txt(d, "press", M + 19, FOOT + 1, "sans12", "faint", bg)
    txt(d, what, x + 5, FOOT, "bold14", "text", bg)


def choices(d, q, items, focus, bg="bg"):
    """Pills the knob turns onto, right-aligned, the one in focus lit."""
    if footer_msg(d, q, bg):
        return
    B.knob_badge(d, M + 7, FOOT + 9, "raised", "text")
    x = R
    for key, label in reversed(items):
        on = key == focus
        x -= F.width(label, "sans12") + 12
        pill(d, label, x, FOOT + 1, "sans12", "stake" if on else "surface", "bg" if on else "muted")
        x -= 4


# ----------------------------------------------------------------------------- home
def draw_home(q):
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
        mark(d, ok, 18, y + 22, 10)
        txt(d, "Nothing to sign" if ok else "No service", 34, y + 10, "bold14")
        if not ok:
            txt(d, fit(q.net_err, TW, "sans12"), M, y + 36, "sans12", "muted")
    rows = 2 if q.outside else 3
    top = max(0, min(q.sel - (rows - 1), len(q.queue) - rows))
    for i in range(top, min(len(q.queue), top + rows)):
        e = q.queue[i]
        lvl = "red" if e["why"] else e["r"]["level"]
        sel = i == q.sel and not q.foot
        fill = "raised" if sel else "surface"
        rrect(d, 2, y, W - 4, 22, 4, fill)
        if lvl != "ok":
            d.fill_rect(2, y + 4, 3, 14, c("bad" if lvl == "red" else "warn"))
        x = txt(d, "#%d" % e["n"], 8, y + 2, "mono13", "warn" if q.conflicts(e) else "faint", fill)
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
        rrect(d, 2, y, W - 4, 22, 4, "warn_bg")
        warn_sign(d, 12, y + 11, 7)
        txt(d, fit("key used %d times elsewhere" % q.outside, W - 30, "sans12"), 24, y + 3, "sans12", "warn_text", "warn_bg")
    choices(d, q, (("owners", "Owners"), ("device", "Device")), q.foot)
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


def item_of(q, i):
    return q.cur["r"]["items"][i]


def who_page(d, q, label, a, pc, bg, y):
    """label, who the address is, then all of it."""
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
    head = "#%d" % e["n"]
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
            txt(d, fit(("on " + name) if known else "unknown contract", TW, "sans12"), M, FOOT - 18, "sans12",
                pc["muted"] if known else "warn", bg)
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
        for line in B.hash_lines(item_of(q, i)["digest"], per=3):
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
            txt(d, fit(nm, TW - 14, "sans12"), M + 13, y, "sans12", "text" if done or a == q.me else "muted")
            y += 16
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
        for line in B.hash_lines(e["mine"], per=3):
            txt(d, line, M, y, "mono13", "text")
            y += 15
    else:       # refused
        mark(d, False, M + 9, y + 10, 9)
        txt(d, "Refused", M + 24, y - 2, "bold18", "bad_text", bg)
        para(d, e["why"], M, y + 24, TW, "sans12", "bad_text", bg, 15, FOOT - 2)
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
    rrect(d, W // 2 - 30, 24, 60, 6, 3, "raised")
    rrect(d, W // 2 - 30, 24, 36, 6, 3, "stake")
    txt_c(d, title, 38, "bold18")
    if q.cur:
        txt_c(d, fit("#%d %s" % (q.cur["n"], q.cur["r"]["summary"]), TW, "sans12"), 66, "sans12", "text")
    info = getattr(q, "work_info", None) or ()
    if info:                                    # the chip's own facts (quorum.chip_info): two fit here
        txt_c(d, fit(sub, TW, "sans12"), 84, "sans12", "muted")
        y = 100
        for line in info[:2]:
            txt_c(d, fit(line, TW, "sans12"), y, "sans12", "muted")
            y += 13
    else:
        para(d, sub, M, 84, TW, "sans12", "muted", "bg", 14, H)
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
    if not ok and q.unsent:
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
        x = txt(d, fit(nm or short(a), TW - 30, "bold14" if nm else "mono13"), M, y, "bold14" if nm else "mono13",
                "text" if nm else "warn")
        if a == q.me:
            pill(d, "you", x + 4, y + 1, "sans12", "stake", "bg")
        y += 20
    k = "key " + (q.fingerprint() or "none")
    if q.counter is not None:
        k += " \u00b7 use #%d" % q.counter
    txt(d, fit(k, TW, "sans12"), M, FOOT - 16, "sans12", "faint")
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
            ("free", "%d KB \u00b7 %s" % (gc.mem_free() // 1024, image.BUILD))]
    y = HEAD + 1
    for k, v in rows:
        txt(d, k, M, y, "sans12", "muted")
        txt_r(d, fit(v, TW - 36, "sans12"), R, y, "sans12", "bad" if v == "FAIL" else "text")
        y += 15
    if q.KNOB:
        choices(d, q, (("chip", "Chip"), ("back", "Back")), q.dfoot)
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
        txt(d, fit(k, 44, "sans12"), M, y, "sans12", "muted")
        txt(d, fit(str(v), TW - 48, "sans12"), M + 48, y, "sans12", "bad" if str(v).startswith(("FAILED", "MISSING")) else "text")
        y += 13
    footer_press(d, q, "Back")
    d.show()


def notice(q, ok, title, lines, press=None):
    """A plain page: a mark, a title and a few lines. The states where the console signs nothing."""
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
    if press:
        footer_press(d, q, press)
    d.show()


def draw_nochip(q):
    notice(q, False, "No chip", ["No secure element answered on I2C.", "The console only signs with a key inside the chip."],
           "Check again")


def draw_pinfail(q):
    exp = q.EXPECT or {}
    title = "Not the pinned key" if q.EXPECT else ("Not a pinned chip" if q.EXPECTS else "Not pinned")
    lines = [q.pin_why or "", "here   " + (q.serial[-8:] or "none"), "pinned " + (str(exp.get("serial", ""))[-8:] or "-"),
             "Nothing will be signed." if q.EXPECT else "tools/fw pin adds this chip."]
    notice(q, False, title, lines, "Check again")


def draw_unconfigured(q):
    notice(q, False, "No Safe", ["secrets.py has no QUORUM_SAFES.", "docs/guide/SETUP.md"])


def draw_crashed(q, why=""):
    import image
    notice(q, False, "Stopped", ["Failed %d times in a row; signs nothing now." % q.fails, why[:40],
                                "build " + image.BUILD, "Hold the knob 3 s to restart."])


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
    elif s == "working":
        draw_working(q, "Working", "")
    else:
        draw_home(q)
