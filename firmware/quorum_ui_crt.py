# console-rp's screens: quorum_ui_s's pages, the same ones in the same order (so "see every page"
# counts them as ever), in the CRT look the person at the bench chose (hardware/console-rp/bench/
# hackui.py). A dark set with scanlines under the page, the case's caps in the footer (D0 ■, D1 ●,
# D2 ▲: cad/consoles/rp.py), and an effect as a page arrives (crt.py):
#   tear    opening a transaction, a new one on home, an ask from the computer, a tab, Refused
#   strong  a red page's first arrival; after it the page is red and still
#   short   a page turn
#   lock    worked out here and checked: the verify code, the key's code, Signed
# None on a redraw of what is already there (a poll that changed nothing, a message, the hold
# filling): nothing moves on a page that asks for a decision.
# main_rp.py hands quorum this module as quorum.U; no other image carries it.
import board
import quorum_ui as B
import quorum_ui_s as S
import crt

B.THEMES["crt"] = {
    "bg": (6, 8, 12), "surface": (18, 22, 30), "raised": (34, 40, 52), "line": (44, 50, 62),
    "text": (232, 236, 240), "muted": (118, 128, 144), "faint": (80, 88, 102),
    "ok": (52, 199, 89), "on_ok": (6, 30, 12),
    "bad": (255, 92, 84), "bad_bar": (200, 38, 38), "on_bad": (255, 255, 255),
    "bad_bg": (36, 4, 7), "bad_head": (150, 24, 26), "bad_text": (255, 222, 218), "bad_muted": (222, 128, 120),
    "warn": (255, 184, 48), "on_warn": (40, 26, 0), "warn_bg": (40, 30, 6), "warn_head": (120, 86, 6),
    "warn_text": (255, 244, 222), "warn_muted": (220, 190, 130), "stake": (122, 146, 255),
}
SCAN = {"bg": (13, 16, 22), "bad_bg": (52, 9, 12), "warn_bg": (54, 42, 12)}     # every third row, under the page
S.CAPS = True               # quorum_ui_s's footer draws ■ ● ▲ before each word

# what quorum.py asks of its UI module, as quorum_ui_s has it (and the clock, from quorum_ui)
pages_of, short, chip_layout, clock_set = S.pages_of, S.short, S.chip_layout, B.clock_set
draw_working, draw_crashed = S.draw_working, S.draw_crashed
OWNERS_PER_PAGE, RECENT_PER_PAGE = S.OWNERS_PER_PAGE, B.RECENT_PER_PAGE
take_pressed = crt.take_pressed
FOOT, HEAD = S.FOOT, S.HEAD

_last = None                # what the screen showed at the last draw (view)
_d = None                   # the display, wrapped once (wrap)
_fx = None                  # the effect for the next show()


def use(name):
    """One look on this board, whichever chip is in."""
    B.use("crt")


def wrap(d):
    """d.fill draws scanlines on the page's background; d.show plays the effect draw() chose."""
    global _d
    if _d is d:
        return
    _d = d
    fill, show = d.fill, d.show

    def fill_scan(col):
        fill(col)
        for k, rgb in SCAN.items():
            if col == B.c(k):
                s = B.c(rgb)
                for y in range(HEAD + 2, FOOT, 3):
                    d.hline(0, y, S.W, s)
                break

    def show_fx():
        global _fx
        fx, _fx = _fx, None
        crt.play(d, fx, HEAD + 1, FOOT, _bg, _keys, show)
    d.fill, d.show = fill_scan, show_fx


_bg = 0
_keys = None


def view(q):
    """What is on the screen, as far as arriving goes."""
    s = q.state
    if s in ("review", "hold"):
        return ("review", q.cur["h"] if q.cur else None, q.page)
    if s == "home":
        return ("home", q.tab, tuple(e["h"] for e in q.queue))
    if s == "key":
        return ("key", q.kpage)
    if s == "result":
        return ("result", q.result[0] if q.result else None, q.result[1] if q.result else None)
    if s == "ask":
        return ("ask", q.apage)
    return (s,)


def effect(q, prev, now):
    """Which effect, from what the screen showed (prev) to what it shows now."""
    if q.state == "hold" or prev == now:
        return None
    s = now[0]
    if s == "review":
        e = q.cur
        red = bool(e and (e["why"] or e["r"]["level"] == "red"))
        kind = q.pages[q.page][0] if q.pages and q.page < len(q.pages) else ""
        if prev is None or prev[:2] != now[:2]:
            return "strong" if red else "tear"
        if kind == "verify":
            return "lock"
        return "short"
    if s == "result":
        return "lock" if now[1] else "strong"
    if s == "key":
        return "lock" if prev is None or prev[0] != "key" else "short"
    if s == "home" and prev and prev[0] == "home":
        if now[2] != prev[2] and set(now[2]) - set(prev[2]):
            return "tear"               # a transaction came
        return "short" if now[1] != prev[1] else None
    if s == "ask" and prev and prev[0] == "ask":
        return "short"
    return "tear"


def draw(q):
    global _last, _fx, _bg, _keys
    wrap(q.d)
    now = view(q)
    _fx = effect(q, _last, now)
    _last = now
    _keys = getattr(q, "keys", None)
    red = q.state in ("review", "hold") and q.cur and (q.cur["why"] or q.cur["r"]["level"] == "red")
    _bg = B.c("bad_bg" if red else "bg")
    S.draw(q)
    _fx = None                          # a screen that didn't show(): no effect left for the next
