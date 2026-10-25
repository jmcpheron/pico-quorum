# The ceremony image's only app, on a 50 ms timer: a banner first, so nobody mistakes this board
# for a signing console, then A for the provisioning ceremony (provision.py: quorum v1 on a fresh
# ATECC608; provision_tm.py: quorum-tm1 on a fresh Trust M) or X for the chip map (slots.py; on a
# Trust M, its objects' metadata, read-only). Every permanent action in either still needs
# ALLOW_LOCK / ALLOW_GENKEY in secrets.py and the arm (signer.py): B+Y, or on build1 a 3 s knob hold.
# On build1 the knob drives it: turn to choose, press to open. On the Feather (lcd.THREE) D2 opens
# PROVISION and setup_s.py draws the ceremony on its three buttons. Every screen is drawn through
# d.frames, so the strip-buffered 320x240 panel gets all of it.
import time
import board
import lcd as L
import splash
import signer as S

d = keys = sig = ui = prov = timer = None
chip = None         # this chip's entry in chips.json (name, theme): which chip is in, at a glance
profile = ""
_busy = False
sel = 0             # the knob's choice on the banner: 0 PROVISION, 1 the map
# The brand image (main_brand.py) sets these: its own screen for an ATECC608, make_ui(d, keys, sig,
# theme), and its banner.
make_ui = None
TITLE, LABEL = "CEREMONY IMAGE", "PROVISION (quorum v1)"
STATE = {"factory": "FRESH: ready for PROVISION", "quorum-v1": "sealed or in progress: quorum v1",
         "quorum-v2": "branded or in progress: quorum v2", "quorum-v3": "branded or in progress: quorum v3",
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


def choices():
    """The banner's entries: (label, what). The ATECC's chip map is button-driven, so on the knob
    and the Feather only a Trust M's read-only object map is offered next to PROVISION. The brand
    bench and the claim (make_ui, brand_ui.py) aren't on three buttons yet."""
    if L.THREE and make_ui:
        return []
    tm = sig is not None and sig.name == "trustm"
    out = [("PROVISION (Trust M)" if tm else LABEL, "prov")]
    if tm:
        out.append(("its objects", "map"))
    elif not L.KNOB and not L.THREE:
        out.append(("the chip map", "slots"))
    return out


def banner():
    d.frames(_banner, serial_tail())


def serial_tail():
    try:
        return sig.serial()[-8:] if S.is_chip(sig) else ""
    except Exception:
        return ""


def _banner(tail):
    import provision
    p = provision.palette(chip["theme"] if chip else "dark")
    d.fill(p["bg"])
    if L.THREE:
        return _banner_three(p, tail)
    d.center_text(TITLE, 40, p["accent"], 2)
    y = 70
    for line in ("Not a signing console:", "no Safe, no service."):
        d.center_text(line, y, p["fg"])
        y += 12
    y += 10
    if chip:
        d.center_text("%s  %s" % (chip["name"].upper(), tail), y, p["accent"], 1)
        d.center_text(STATE.get(profile, profile), y + 14, p["ok"] if profile == "factory" else p["fg"])
    else:
        d.center_text("NO CHIP on the bus", y, p["bad"])
    y += 44
    for i, (label, _) in enumerate(choices()):
        if L.KNOB:
            d.center_text(("> %s <" if i == sel else "  %s  ") % label, y, p["accent"] if i == sel else p["fg"])
        else:
            d.center_text(("A: " if i == 0 else "X: ") + label, y, p["fg"])
        y += 14
    if L.KNOB:
        d.center_text("turn: choose   press: open", y + 10, p["muted"])
    d.show()


def _banner_three(p, tail):
    """The banner on 240x135: what to press, level with the button it names (board.RAIL_Y)."""
    d.center_text(TITLE, 6, p["accent"], 2)
    d.center_text("Not a signing console:", 30, p["fg"])
    d.center_text("no Safe, no service.", 41, p["fg"])
    if chip:
        d.center_text("%s  %s" % (chip["name"].upper(), tail), 58, p["accent"])
        d.center_text(STATE.get(profile, profile), 70, p["ok"] if profile == "factory" else p["fg"])
    else:
        d.center_text("NO CHIP on the bus", 58, p["bad"])
    c = choices()
    if not c:
        d.center_text("not on three buttons yet", 100, p["muted"])
    for (label, _), key, y in zip(c, ("D2", "D1"), (board.RAIL_Y[2] - 4, 96)):
        d.text("%s: %s" % (board.NAMES[key], label), 4, y, p["fg"])
    d.show()


def open_choice(what):
    global prov, ui
    import provision
    if what == "prov" and chip is not None:
        ui_cls = provision.UI
        if L.THREE:
            import setup_s
            ui_cls = setup_s.UI
        if sig.name == "trustm":
            import provision_tm
            prov = ui_cls(d, keys, sig, chip["theme"], provision_tm.Ceremony(sig))
        else:
            prov = (make_ui or ui_cls)(d, keys, sig, chip["theme"])
        prov.draw()
    elif what == "map":
        import provision_tm
        ui = "map"
        provision_tm.draw_map(d, sig, provision.palette(chip["theme"] if chip else "dark"))
    elif what == "slots":
        import slots
        ui = slots.SlotsUI(d, sig, lambda: None)
        ui.open("zones")
        ui.draw()


def tick(t):
    global _busy, ui, prov, sel
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
        elif L.THREE:
            for (_, what), key in zip(choices(), ("D2", "D1")):
                if key in pressed:
                    open_choice(what)
                    break
        elif "A" in pressed:
            open_choice("prov")
        elif "X" in pressed and choices()[1:]:
            open_choice(choices()[1][1])
        elif ("up" in pressed or "down" in pressed) and len(choices()) > 1:
            sel = 1 - sel
            banner()
        elif "press" in pressed:
            open_choice(choices()[min(sel, len(choices()) - 1)][1])
    except Exception as e:
        import sys
        sys.print_exception(e)
    finally:
        _busy = False


def start_timer():
    global timer
    timer = board.timer("tick", 50, tick)


def start():
    global d, keys, sig
    splash.TITLE = "ceremony"
    d = splash.begin()
    keys = L.Keys()
    splash.finish(keys, wait=False)     # the boot art's code out of RAM before the ceremony's screens
    sig = S.load(soft=False)
    identify()
    banner()
    start_timer()


def stop():
    if timer:
        timer.deinit()
