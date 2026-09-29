# The ceremony image's only app, on a 50 ms timer: a banner first, so nobody mistakes this board
# for a signing console, then A for the provisioning ceremony (provision.py: quorum v1 on a fresh
# ATECC608; provision_tm.py: quorum-tm1 on a fresh Trust M) or X for the chip map (slots.py; on a
# Trust M, its objects' metadata, read-only). Every permanent action in either still needs
# ALLOW_LOCK / ALLOW_GENKEY in secrets.py and the B+Y arm (signer.py).
import time
import machine
import lcd as L
import splash
import signer as S

d = keys = sig = ui = prov = timer = None
chip = None         # this chip's entry in chips.json (name, theme): which chip is in, at a glance
profile = ""
_busy = False
STATE = {"factory": "FRESH: ready for PROVISION", "quorum-v1": "sealed or in progress: quorum v1",
         "quorum-tm1": "sealed: Trust M quorum-tm1", "quorum-tm1-open": "in progress: Trust M",
         "legacy-test": "test table (chip #1 style)", "unknown": "unknown table"}


def identify():
    """The chip on the bus: register it (chips.py) and say what it holds (sig.profile)."""
    global chip, profile
    chip, profile = None, ""
    if not S.is_chip(sig):
        return
    try:
        import chips
        profile = sig.profile()
        chip, new = chips.seen(sig.serial(), profile, kind=sig.name)
    except Exception as e:
        print("chip:", e)


def banner():
    import provision
    p = provision.palette(chip["theme"] if chip else "dark")
    d.fill(p["bg"])
    d.center_text("CEREMONY IMAGE", 40, p["accent"], 2)
    y = 70
    for line in ("Not a signing console:", "no Safe, no service."):
        d.center_text(line, y, p["fg"])
        y += 12
    y += 10
    if chip:
        d.center_text("%s  %s" % (chip["name"].upper(), sig.serial()[-8:]), y, p["accent"], 1)
        d.center_text(STATE.get(profile, profile), y + 14, p["ok"] if profile == "factory" else p["fg"])
    else:
        d.center_text("NO CHIP on the bus", y, p["bad"])
    y += 44
    for line in (("A: PROVISION (Trust M)", "X: its objects") if sig.name == "trustm" else ("A: PROVISION (quorum v1)", "X: the chip map")):
        d.center_text(line, y, p["fg"])
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
        elif ui == "map":
            if pressed:
                ui = None
                banner()
        elif ui is not None:
            if ui.tick(pressed, keys) == "home":
                ui = None
                banner()
        elif "A" in pressed and chip is not None:
            import provision
            if sig.name == "trustm":
                import provision_tm
                prov = provision.UI(d, keys, sig, chip["theme"], provision_tm.Ceremony(sig))
            else:
                prov = provision.UI(d, keys, sig, chip["theme"])
            prov.draw()
        elif "X" in pressed and sig.name == "trustm":
            import provision
            import provision_tm
            ui = "map"
            provision_tm.draw_map(d, sig, provision.palette(chip["theme"] if chip else "dark"))
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
    identify()
    banner()
    start_timer()


def stop():
    if timer:
        timer.deinit()
