# The ceremony image's only app: the chip map (slots.py), full screen, on a 50 ms timer, with a
# banner first so nobody mistakes this board for a signing console. Every permanent action in the
# chip map still needs ALLOW_LOCK / ALLOW_GENKEY in secrets.py and the B+Y arm (signer.py).
import time
import machine
import lcd as L
import splash
import signer as S

d = keys = sig = ui = timer = None
_busy = False


def banner():
    d.fill(L.BLACK)
    d.center_text("CEREMONY IMAGE", 70, L.YELLOW, 2)
    y = 110
    for line in ("Not a signing console:", "no Safe, no service.", "", "The chip map, for setting", "up a chip. Any key opens it."):
        d.center_text(line, y, L.WHITE)
        y += 14
    d.show()


def tick(t):
    global _busy, ui
    if _busy:
        return
    _busy = True
    try:
        pressed = keys.pressed()
        if ui is None:
            if pressed:
                import slots
                ui = slots.SlotsUI(d, sig, lambda: None)
                ui.open("zones")
                ui.draw()
        elif ui.tick(pressed, keys) == "home":
            ui = None
            banner()
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
