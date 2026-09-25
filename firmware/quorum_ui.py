# The console's screens, drawn from quorum.py's state (passed in as q). Nothing here decides
# anything; it only draws. 240x240, the 8x8 font: 29 characters a line at scale 1, 14 at scale 2.
#
# The A/B/X/Y column runs down the right edge, A at the top and Y at the bottom, so on a review
# page SIGN is a bar across the top pointing at A and REJECT a bar across the bottom pointing at Y.
# SIGN stays grey until every page has been seen. A red page is red all over, and the one thing at
# stake on it (the address that gains power, the amount) is drawn in cyan, as on the chip map's red
# PERMANENT screen.
import time
import lcd as L
import theme as T
import blockies
import icons
from chipmap import wrap

BG, PANEL, INK = T.C["bg"], T.C["panel"], T.C["ink"]
OK, WARN, RED, LOST = T.C["safe"], T.C["rev"], T.C["perm"], T.C["lost"]
DIM, GREY, WHITE = T.C["dim"], T.C["grey"], L.WHITE
DEEP_RED = L.color(110, 8, 8)
DEEP_WARN = L.color(70, 56, 0)
CHAIN_RGB = {31337: (255, 150, 40), 8453: (0, 82, 255), 84532: (150, 90, 255), 1: (98, 126, 234)}
LEVEL = {"ok": OK, "warn": WARN, "red": RED}
TOP, BOTTOM = 26, 214          # review pages: content lives between the SIGN and REJECT bars


def chain_color(chain):
    return L.color(*CHAIN_RGB.get(chain, (120, 120, 120)))


def short(a):
    return a[:6] + ".." + a[-4:] if len(a) > 14 else a


def addr_lines(a):
    """40 hex in 4-character chunks, two lines: 0x7099 7970 c518 12dc 3a01 / 0c7d 01b5 ..."""
    h = a[2:].lower() if a.startswith("0x") else a.lower()
    ch = [h[i:i + 4] for i in range(0, len(h), 4)]
    return ["0x" + " ".join(ch[:5]), "  " + " ".join(ch[5:])]


def hash_lines(h, per=4):
    """64 hex in 4-character chunks, four to a line."""
    h = h[2:] if h.startswith("0x") else h
    ch = [h[i:i + 4] for i in range(0, len(h), 4)]
    return [" ".join(ch[i:i + per]) for i in range(0, len(ch), per)]


def tri_right(d, x, cy, size, c):
    for i in range(size // 2):
        d.vline(x + i, cy - (size // 2 - i), 2 * (size // 2 - i), c)


def name_of(q, a):
    return q.ctx["book"].get(a.lower()) if q.ctx else None


def dot(d, x, y, filled, c):
    d.ellipse(x, y, 3, 3, c, filled)


# ----------------------------------------------------------------------------- common parts
def sign_bar(q):
    d = q.d
    ok, why = q.can_sign(q.cur)
    left = q.unseen()
    if ok and not left:
        d.fill_rect(0, 0, 240, TOP - 2, OK)
        d.big_text("SIGN", 8, 4, L.BLACK, 2)
        d.text("hold A %d s" % (q.hold_need(q.cur) // 1000), 84, 8, L.BLACK)
        tri_right(d, 224, 12, 16, L.BLACK)
    else:
        d.fill_rect(0, 0, 240, TOP - 2, INK)
        d.big_text("SIGN", 8, 4, DIM, 2)
        d.text(("seen %d of %d pages" % (len(q.pages) - len(left), len(q.pages))) if ok else why[:17], 84, 8, GREY)
        tri_right(d, 224, 12, 16, DIM)


def reject_bar(q):
    d = q.d
    d.fill_rect(0, BOTTOM, 240, 240 - BOTTOM, L.color(170, 20, 20))
    d.big_text("REJECT", 8, BOTTOM + 5, WHITE, 2)
    d.text("B back", 120, BOTTOM + 9, L.color(255, 170, 170))
    tri_right(d, 224, BOTTOM + 13, 16, WHITE)


def page_dots(q, y=203):
    d = q.d
    n = len(q.pages)
    x0 = 120 - (n * 12) // 2 + 6
    for i in range(n):
        c = WHITE if i == q.page else (GREY if i in q.seen else DIM)
        dot(d, x0 + i * 12, y, i == q.page or i in q.seen, c)


def flash(q, y=198, bg=BG):
    """A message from say(): over the dots, for a few seconds."""
    if q.msg:
        q.d.fill_rect(0, y - 2, 240, 13, bg)
        q.d.center_text(q.msg[:30], y, WARN)
        return True
    return False


def text_block(d, s, x, y, c, bottom, w=29, step=11):
    for line in wrap(s, w):
        if y > bottom - 8:
            break
        d.text(line, x, y, c)
        y += step
    return y


# ----------------------------------------------------------------------------- home
def draw_home(q):
    d = q.d
    d.fill(BG)
    cc = chain_color(q.CHAIN)
    d.fill_rect(0, 0, 240, 14, cc)
    d.text("%s  chain %d" % (q.CFG["chains"].get(str(q.CHAIN), "CHAIN"), q.CHAIN), 4, 3, BG)
    status = "synced" if q.net_ok else "offline"
    d.text(status, 236 - 8 * len(status), 3, BG)
    blockies.draw(d, q.SAFE_ADDR, 6, 20, 3)
    d.big_text(q.SAFE["name"][:12], 38, 20, WHITE, 2)
    n_own, need = len(q.owners()), q.threshold()
    d.text(short(q.SAFE_ADDR), 38, 38, GREY)
    if n_own:
        d.text("%d of %d" % (need, n_own), 150, 38, WHITE)
    d.hline(0, 50, 240, INK)
    todo = sum(1 for e in q.queue if q.waiting(e))
    d.text("WAITING FOR YOU %d" % todo if todo else "QUEUE", 4, 56, WARN if todo else GREY)
    if q.info:
        s = "next #%s" % q.info.get("nonce", "?")
        d.text(s, 236 - 8 * len(s), 56, DIM)
    y = 72
    if not q.queue:
        if q.net_ok:
            d.center_text("nothing to sign", 110, WHITE, 2)
            d.center_text("the queue is empty", 134, GREY)
        else:
            d.center_text("no service", 104, RED, 2)
            d.center_text(q.net_err[:30], 128, GREY)
            d.center_text((q.BASE or "")[:30], 142, DIM)
    top = max(0, min(q.sel - 3, len(q.queue) - 7))
    for i in range(top, min(len(q.queue), top + 7)):
        e = q.queue[i]
        lvl = e["r"]["level"]
        if i == q.sel:
            d.fill_rect(0, y - 4, 240, 17, INK)
            d.fill_rect(0, y - 4, 3, 17, RED if e["why"] else LEVEL[lvl])
        num = "#%d" % e["n"]
        d.text(num, 6, y, WARN if q.conflicts(e) else (RED if e["why"] or lvl == "red" else WHITE))
        if e["why"]:
            what, wc = "REFUSED: " + ("other Safe" if "another Safe" in e["why"] else "bad hash"), RED
        else:
            what, wc = e["r"]["summary"], (WHITE if lvl == "ok" else LEVEL[lvl])
        if lvl == "red" and not e["why"]:
            what = "! " + what
        d.text(what[:20], 38, y, wc)
        if q.signed_by_me(e):
            st, sc = "YOU", OK
        elif e["h"] in q.declined:
            st, sc = "NO", RED
        elif e["why"]:
            st, sc = "--", RED
        else:
            st, sc = "%d/%d" % (len(e["conf"]), q.threshold()), GREY
        d.text(st, 236 - 8 * len(st), y, sc)
        y += 18
    if any(q.conflicts(e) for e in q.queue):
        d.text("yellow #: only one can run", 4, 196, WARN)
    if len(q.queue) > 7:
        d.text("%d/%d" % (q.sel + 1, len(q.queue)), 200, 196, DIM)
    d.hline(0, 208, 240, INK)
    fp = q.fingerprint()
    d.text(("key " + fp) if fp else "no key", 4, 213, GREY if fp else RED)
    mine = q.me and q.me in q.owners()
    s = "owner" if mine else ("not an owner" if q.owners() else "")
    d.text(s, 236 - 8 * len(s), 213, OK if mine else DIM)
    if not flash(q, 228, BG):
        d.center_text("A open  B owners  X chip", 228, DIM)
    d.show()


# ----------------------------------------------------------------------------- review pages
def draw_summary(q):
    d, e = q.d, q.cur
    r = e["r"]
    lvl = r["level"]
    d.text("TRANSACTION", 4, 32, GREY)
    d.big_text("#%d" % e["n"], 96, 29, WHITE, 2)
    tag = q.CFG["chains"].get(str(q.CHAIN), "")
    d.fill_rect(236 - 8 * len(tag) - 4, 29, 8 * len(tag) + 4, 14, chain_color(q.CHAIN))
    d.text(tag, 236 - 8 * len(tag) - 2, 32, BG)
    y = 50
    for line in wrap(r["summary"], 14)[:2]:
        d.big_text(line, 4, y, WHITE if lvl == "ok" else LEVEL[lvl], 2)
        y += 18
    items = r["items"]
    if len(items) == 1 and items[0].get("to"):
        to = items[0]["to"]
        nm = name_of(q, to)
        s = items[0].get("label", "to") + " " + (nm or short(to))
        if not nm and len(s) <= 19:
            s += " (unknown)"
        d.text(s, 4, y + 2, WARN if nm else GREY)
        y += 14
    elif len(items) > 1:
        for i, it in enumerate(items[:3]):
            d.text(("%d. %s" % (i + 1, it["what"]))[:29], 4, y + 2, WHITE if it["level"] == "ok" else LEVEL[it["level"]])
            y += 11
        y += 3
    y = max(y + 4, 108)
    have, need = len(e["conf"]), q.threshold()
    d.text("APPROVALS", 4, y, GREY)
    d.text("%d of %d so far" % (have, need), 88, y, WHITE)
    y += 14
    for a in q.owners()[:4]:
        done = a in e["conf"]
        nm = name_of(q, a) or short(a)
        c = OK if done else (LOST if a == q.me else DIM)
        dot(d, 10, y + 3, done, c)
        d.text(nm[:14] + (" (you)" if a == q.me else ""), 20, y, c)
        y += 11
    if len(q.owners()) > 4:
        d.text("+%d more" % (len(q.owners()) - 4), 20, y, DIM)
        y += 11
    ok, why = q.can_sign(e)
    if q.signed_by_me(e):
        line, c = "you signed this one", OK
    elif not ok:
        line, c = "you can't sign: " + why, RED
    elif have + 1 >= need:
        line, c = "yours makes %d of %d: ready" % (have + 1, need), OK
    else:
        line, c = "yours makes %d of %d" % (have + 1, need), WHITE
    d.text(line[:29], 4, y + 3, c)
    reds = sum(1 for it in items if it["level"] == "red")
    if reds:
        d.fill_rect(0, 186, 240, 12, DEEP_RED)
        d.center_text("%d RED PAGE%s: READ %s" % (reds, "S" if reds > 1 else "", "THEM" if reds > 1 else "IT"), 188, WHITE)
    if q.conflicts(e):
        d.center_text("another proposal shares #%d" % e["n"], 188 if not reds else 176, WARN)


def draw_item(q, i):
    d, e = q.d, q.cur
    it = e["r"]["items"][i]
    lvl = it["level"]
    n = len(e["r"]["items"])
    if lvl == "red":
        d.fill_rect(0, TOP, 240, BOTTOM - TOP, DEEP_RED)
        head, hc = RED, WHITE
    elif lvl == "warn":
        d.fill_rect(0, TOP, 240, BOTTOM - TOP, DEEP_WARN)
        head, hc = WARN, L.BLACK
    else:
        head, hc = PANEL, WHITE
    d.fill_rect(0, TOP, 240, 20, head)
    d.big_text(it["title"][:12], 4, TOP + 2, hc, 2)
    if n > 1:
        s = "%d/%d" % (i + 1, n)
        d.text(s, 236 - 8 * len(s), TOP + 6, hc)
    y = TOP + 26
    body = WHITE
    if e["why"]:
        d.fill_rect(0, TOP + 20, 240, 12, DEEP_RED)
        d.center_text("REFUSED: THE SERVICE'S CLAIM", TOP + 22, WHITE)
        y += 10
    if it.get("amount"):
        a = it["amount"]
        sc = 3 if len(a) <= 9 else 2
        if len(a) <= 14:
            d.big_text(a, 4, y, LOST if lvl == "red" else WHITE, sc)
            y += 8 * sc + 6
        else:
            y = text_block(d, a, 4, y, LOST if lvl == "red" else WHITE, BOTTOM, 29, 10) + 4
    for label, a in ((it.get("frm_label", "from"), it.get("frm")), (it.get("label", "to"), it.get("to"))):
        if not a:
            continue
        nm = name_of(q, a)
        d.text(label, 4, y, GREY)
        if nm:
            d.text(nm, 4 + 8 * (len(label) + 1), y, WARN if lvl != "red" else LOST)
        else:
            d.text("NOT IN ADDRESS BOOK", 4 + 8 * (len(label) + 1), y, WARN if lvl != "red" else L.color(255, 190, 190))
        y += 11
        for line in addr_lines(a):
            d.text(line, 4, y, LOST if lvl == "red" else body)
            y += 10
        y += 4
    if it.get("text"):
        y = text_block(d, it["text"], 4, y, body, 147 if it.get("digest") else 198)
    if it.get("digest"):
        y = 149         # always the same place, so the eye finds it
        d.text("calldata digest", 4, y, GREY)
        for line in hash_lines(it["digest"]):
            y += 9 if y > 149 else 12
            d.text(line, 4, y, body)


def draw_verify(q):
    d, e = q.d, q.cur
    d.center_text("CHECK WITH THE PROPOSER", 32, WHITE)
    d.center_text("the Safe tx hash ends in", 46, GREY)
    code = e["mine"][-8:]
    d.big_text(code[:4] + " " + code[4:], 12, 60, LOST, 3)
    blockies.draw(d, e["mine"], 6, 94, 5)
    y = 96
    for i, line in enumerate(hash_lines(e["mine"])):
        d.text(("0x" if i == 0 else "  ") + line, 52, y, WHITE)
        y += 11
    d.hline(0, 144, 240, INK)
    d.text("hashed here from the fields", 4, 150, OK)
    d.text("on the pages before this one", 4, 161, OK)
    d.text("chain %d  nonce %d  %s" % (q.CHAIN, e["n"], "DELEGATECALL" if int(e["t"]["operation"]) else "call"), 4, 176, DIM)
    d.text("Safe " + short(q.SAFE_ADDR), 4, 187, DIM)


def draw_refused(q):
    d, e = q.d, q.cur
    pink = L.color(255, 190, 190)
    d.fill_rect(0, TOP, 240, BOTTOM - TOP, DEEP_RED)
    icons.draw(d, "cross", 8, TOP + 8, WHITE, 2)
    d.big_text("REFUSED", 48, TOP + 8, WHITE, 3)
    y = text_block(d, e["why"], 4, TOP + 42, WHITE, 150) + 6
    d.text("the service asks to sign", 4, y, pink)
    d.text(e["h"][:12] + ".." + e["h"][-8:], 4, y + 11, WHITE)
    y += 26
    if e["mine"]:
        d.text("these fields hash to", 4, y, pink)
        d.text(e["mine"][:12] + ".." + e["mine"][-8:], 4, y + 11, LOST)
    if len(q.pages) > 1:
        d.text("down: what it claims", 4, 188, pink)


def draw_review(q):
    d = q.d
    d.fill(BG)
    kind, i = q.pages[q.page]
    if kind == "summary":
        draw_summary(q)
    elif kind == "item":
        draw_item(q, i)
    elif kind == "verify":
        draw_verify(q)
    else:
        draw_refused(q)
    sign_bar(q)
    if not flash(q, 200, BG if kind in ("summary", "verify") else d.pixel(0, 200)):
        page_dots(q, 205)
    reject_bar(q)
    if q.state == "hold":
        draw_hold(q)
    d.show()


def draw_hold(q):
    d = q.d
    need = q.hold_need(q.cur)
    el = min(need, time.ticks_diff(time.ticks_ms(), q.hold_t0))
    red = need > q.HOLD_MS
    d.fill_rect(14, 70, 212, 100, BG)
    d.rect(14, 70, 212, 100, RED if red else OK)
    d.center_text("KEEP HOLDING", 80, WHITE, 2)
    d.rect(24, 104, 192, 16, WHITE)
    d.fill_rect(26, 106, 188 * el // need, 12, OK)
    d.center_text("%d" % max(1, (need - el + 999) // 1000), 128, OK, 2)
    d.center_text("red: %d s, not %d" % (need // 1000, q.HOLD_MS // 1000) if red else "let go to cancel", 152, RED if red else GREY)


# ----------------------------------------------------------------------------- the rest
def draw_working(q, title, sub):
    d = q.d
    d.fill(BG)
    d.fill_rect(0, 0, 240, 26, T.C["config"])
    d.center_text(title, 5, WHITE, 2)
    if q.cur:
        d.center_text("#%d %s" % (q.cur["n"], q.cur["r"]["summary"][:22]), 90, WHITE)
    d.center_text(sub[:30], 110, GREY)
    d.show()


def draw_result(q):
    d = q.d
    ok, title, lines = q.result
    d.fill(BG)
    d.fill_rect(0, 0, 240, 26, OK if ok else RED)
    d.center_text(title, 5, L.BLACK if ok else WHITE, 2)
    icons.draw(d, "check" if ok else "cross", 88, 40, OK if ok else RED, 4)
    y = 116
    for i, s in enumerate(lines):
        for line in wrap(s, 29):
            d.center_text(line, y, WHITE if i else (OK if ok else RED))
            y += 14
    d.center_text("A ok" if ok or not q.unsent else "A send again   B back", 226, DIM)
    d.show()


def draw_owners(q):
    d = q.d
    d.fill(BG)
    d.fill_rect(0, 0, 240, 22, chain_color(q.CHAIN))
    d.text("OWNERS", 4, 7, BG)
    s = "%d of %d must approve" % (q.threshold(), len(q.owners())) if q.owners() else "unknown"
    d.text(s, 236 - 8 * len(s), 7, BG)
    y = 28
    for a in q.owners()[:5]:
        nm = name_of(q, a) or "NOT IN ADDRESS BOOK"
        d.text(nm + (" (you)" if a == q.me else ""), 4, y, LOST if a == q.me else WARN)
        y += 10
        for line in addr_lines(a):
            d.text(line, 4, y, WHITE)
            y += 9
        y += 4
    d.text("Safe", 4, 196, GREY)
    d.text(short(q.SAFE_ADDR) + "  nonce %s" % q.info.get("nonce", "?"), 44, 196, WHITE)
    d.text("this key " + (q.fingerprint() or "none"), 4, 208, GREY)
    d.center_text("B back", 226, DIM)
    d.show()


def draw_nochip(q):
    d = q.d
    d.fill(BG)
    d.fill_rect(0, 0, 240, 26, RED)
    d.center_text("NO CHIP", 5, WHITE, 2)
    y = 60
    for line in ("no ATECC608 answered on I2C", "", "the console signs only with", "a key inside the chip", "",
                 "wire the chip, then", "press A to look again"):
        d.center_text(line, y, WHITE)
        y += 16
    d.show()


def draw(q):
    s = q.state
    if s == "nochip":
        draw_nochip(q)
    elif s in ("review", "hold"):
        draw_review(q)
    elif s == "result":
        draw_result(q)
    elif s == "owners":
        draw_owners(q)
    elif s == "working":
        draw_working(q, "WORKING", "")
    else:
        draw_home(q)
