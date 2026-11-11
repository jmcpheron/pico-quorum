# console-rp: the bench demos behind one menu, in the CRT look. Bench only. D1 ▶ moves, D2 ● opens;
# D0 ■ (Menu) on the queue or the key's intro comes back here.
#   REVIEW   hackui.py: a queue, a transaction's pages, the live hash, the verify code, hold to sign
#   KEY      keypick_crt.py: make a key, pick it by its blockie, keep it (no key is made)
#   GLITCH   the two effects the UI uses, FX1 tear and FX3 lock, on a page, again and again
#   put.py PORT hackui.py keypick_crt.py (with what they need), then rawrepl.py PORT demo.py --follow 5
import gc
import time
import hackui as H
import keypick_crt as KP

ITEMS = (("REVIEW A TRANSACTION", "THE HASH, WORKED OUT HERE"),
         ("MAKE YOUR KEY", "PICK IT BY ITS PICTURE"),
         ("THE TWO GLITCHES", "TEAR: ARRIVES. LOCK: CHECKED."))


def draw_menu(sel):
    H.th = H.NORMAL
    H.bg()
    H.header("> PICOQUORUM", "CONSOLE-RP")
    for i, (a, b) in enumerate(ITEMS):
        y = 19 + 32 * i
        on = i == sel
        if on:
            H.d.fill_rect(0, y, 3, 28, H.c("acc"))
        H.tf(a, 10, y, "mono13", "ink" if on else "mute")
        H.t8(b, 10, y + 18, "mute" if on else "dim")
    H.footer((None, ("NEXT", "ink"), ("OPEN", "acc")))


def glitches():
    """FX1 and FX3 in turn on the verify page of #7, until D0."""
    tx = H.TXS[0]
    if not tx["hash"]:
        tx["hash"] = H.compute(tx)
    fx = "tear"
    while True:
        H.arrive(lambda: (H.draw_page(tx, 3, True), H.footer((("MENU", "ink"), ("AGAIN", "ink"), ("SWAP", "acc")))), fx=fx)
        H.t8("FX1 TEAR" if fx == "tear" else "FX3 LOCK", 120, 3, "warn")
        H.push_rows(0, H.BODY0)
        k = None
        while k is None:
            k = H.pressed()
            time.sleep_ms(10)
        if k == 0:
            return
        if k == 2:
            fx = "lock" if fx == "tear" else "tear"


def main():
    sel = 0
    H.arrive(draw_menu, sel)
    while True:
        k = H.pressed()
        if k == 1:
            sel = (sel + 1) % len(ITEMS)
            draw_menu(sel)
            H.glitch(4, 8)
        elif k == 2:
            (H.main, KP.main, glitches)[sel]()
            gc.collect()
            H.arrive(draw_menu, sel)
        time.sleep_ms(10)


gc.collect()
print("demo: D1 next, D2 open, D0 back to this menu; heap %d KB" % (gc.mem_free() // 1024))
main()
