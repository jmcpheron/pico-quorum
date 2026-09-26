# The ceremony image's only app, on a 50 ms timer: a banner first, so nobody mistakes this board
# for a signing console, then A for the provisioning ceremony (provision.py: quorum v1 on a fresh
# chip) or any other key for the chip map (slots.py). Every permanent action in either still needs
# ALLOW_LOCK / ALLOW_GENKEY in secrets.py and the B+Y arm (signer.py).
import time
import machine
import lcd as L
import splash
import signer as S

d = keys = sig = ui = prov = timer = None
_busy = False


def banner():
    d.fill(L.BLACK)
    d.center_text("CEREMONY IMAGE", 60, L.YELLOW, 2)
    y = 100
    for line in ("Not a signing console:", "no Safe, no service.", "", "A: PROVISION a fresh chip", "   (quorum v1)",
                 "X: the chip map"):
        d.center_text(line, y, L.WHITE)
        y += 14
    d.show()


def tick(t):
    global _busy, ui, prov
    if _busy:
        return
    _busy = True
    try:
        pressed = keys.pressed()
        if prov is not None:
            if prov.tick(pressed) == "back":
                prov = None
                banner()
            else:
                prov.draw()
        elif ui is not None:
            if ui.tick(pressed, keys) == "home":
                ui = None
                banner()
        elif "A" in pressed:
            import provision
            prov = provision.UI(d, keys, sig)
            prov.draw()
        elif "X" in pressed:
            import slots
            ui = slots.SlotsUI(d, sig, lambda: None)
            ui.open("zones")
            ui.draw()
    except Exception as e:
        import sys
        sys.print_exception(e)
    finally:
        _busy = False


def start_timer():
    global timer
    timer = machine.Timer(period=50, mode=machine.Timer.PERIODIC, callback=tick)


def start():
    global d, keys, sig
    splash.TITLE = "ceremony"
    d = splash.begin()
    keys = L.Keys()
    sig = S.load(soft=False)
    banner()
    start_timer()


def stop():
    if timer:
        timer.deinit()
