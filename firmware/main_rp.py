# picoquorum-image: console-rp
# main.py of the console-rp image (hardware/console-rp: an RP2350 with no radio, its USB-C reaching only a
# CH343P on UART1). boot_rp.py started the boot art. This takes the link (link.py) and its line buffer
# first, while the heap is whole, then the console's big blocks, and starts the Safe console with the
# link as its way out. Then the loop is usblink's, which never returns: the computer gets the link's
# few lines (docs/USB-LINK.md), never a REPL and never the chip.
#
# No maintenance here: the USB-C can't reach a REPL, so nothing on this board could use one. The image
# comes and goes over SWD, on the bench (hardware/console-rp/bench/swdload.py).
#
# Which way it goes is read off the chip at every start (route):
#   no pin.json, the chip's config open           -> the key flow, which says Not prepared
#   no pin.json, a quorum v1 chip                 -> the key flow: the owner makes the key here
#                                                    (keyflow.OwnKey on keypick_rp's screens); once it is
#                                                    sealed and pinned, a restart into the console
#   anything else (pinned, no chip, another table) -> the console, which says what it sees
try:
    import micropython
    micropython.kbd_intr(-1)        # first: MicroPython turned Ctrl-C back on for this file
except BaseException:
    pass
import sys


def run():
    import board
    if board.BOARD != "console-rp":
        raise RuntimeError("the console-rp image on a %s" % board.BOARD)
    import link
    link.start()
    import qlog
    qlog.TAP = link.log             # each log line to the computer as well
    import usblink
    usblink.PORT = link
    import gc
    import lcd
    import splash
    splash.pause()
    gc.collect()
    import fonts                    # the big blocks while the heap is whole, whichever way it goes
    for _f in fonts.FILES:
        fonts.get(_f)
    import crt
    crt.reserve()                   # the effects' noise strip, 7.5 KB, before the heap breaks up
    path, sig = route()
    if path == "key":
        splash.pause(False)
        key_flow(sig)               # never returns
    import quorum
    import quorum_ui_crt
    quorum.NET, quorum.VIA = link, link     # the way out, and the transport txservice calls
    quorum.U = quorum_ui_crt                # its screens: quorum_ui_s's pages in the CRT look
    splash.pause(False)
    quorum.start()
    return quorum


def route():
    """("key", signer) when this chip is for the key flow: no pin.json, and its config open or locked as
    quorum v1. Else ("console", None)."""
    import qlog
    import policy
    import signer
    try:
        pins = policy.pins(policy.pin_file())
        s = signer.load(soft=False, pins=pins)
        if not pins and s.name == "atecc608":
            cfg = s.config()
            import chipcfg
            if cfg[87] != 0x00 or chipcfg.identify(cfg) == "quorum-v1":
                return "key", s
    except Exception as e:
        qlog.write("route: %r" % e)
    return "console", None


class KeyHost:
    """usblink's host while the key flow runs: status only, and no asks."""
    LINK_ASKS = ()

    def __init__(self, ui):
        self.ui = ui

    def link_status(self):
        import image
        import link
        c = self.ui.c
        st = {"mode": "key", "state": c.step(), "serial": c.serial, "profile": c.profile, "counter": c.counter,
              "image": image.IMAGE, "version": image.VERSION}
        st.update(link.status())
        return st


def key_flow(sig):
    """The owner's key in a loop of its own, the link answered from it. Done: a restart, and the
    console starts on the pin the flow wrote."""
    import time
    import machine
    import splash
    import lcd
    import qlog
    import link
    import usblink
    import crt
    import keyflow
    import keypick_rp
    d = splash.begin()
    keys = lcd.Keys()
    splash.finish(keys, wait=False)
    ui = keypick_rp.UI(d, keys, sig, keyflow.OwnKey(sig))
    usblink.host, usblink.mode = KeyHost(ui), "key"
    import gc
    gc.collect()
    qlog.write("key flow: %d bytes free" % gc.mem_free())
    last = None
    while True:
        st = ui.c.step()
        if st != last:
            qlog.write("key: %s, chip %s, counter %s" % (st, ui.c.serial, ui.c.counter))
            last = st
        if ui.tick(crt.take_pressed() + keys.pressed()) == "console":
            qlog.write("key: sealed and pinned, restarting into the console")
            for _ in range(5):
                link.pump()             # the log line out before the restart
                time.sleep_ms(20)
            machine.reset()
        ui.draw()
        usblink.poll(pump=True)
        time.sleep_ms(50)


_quorum = None
try:
    _quorum = run()
except Exception as e:
    try:
        with open("error.log", "w") as f:
            sys.print_exception(e, f)
    except Exception:
        pass
    sys.print_exception(e)
    try:
        import qlog
        qlog.write("STOPPED: %r" % e)
    except Exception:
        pass

# The link's from here, a console that stopped included. Never returns.
import usblink
usblink.run(_quorum)
