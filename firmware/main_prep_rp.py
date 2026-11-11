# picoquorum-image: prepare-rp
# main.py of console-rp's bench image (prepare.py): a fresh ATECC608 made ready for the customer image,
# C1-C3 and the read-only P4, on the ceremony's three-button screen (setup_s.py). Never a key. Loaded on
# the bench over SWD with a bench secrets.py that holds ALLOW_LOCK = True and nothing else:
#   swdload.py --no-micropython --image build/prepare-rp-<sha> --secrets <bench secrets.py>
# That file stays out of the repository. When the chip is ready, the customer image goes on in its place
# (hardware/console-rp/README.md).
#
# The link on UART1 carries the log lines (each step's result) and status, and nothing else: no asks,
# and nothing it says reaches the chip.
try:
    import micropython
    micropython.kbd_intr(-1)
except BaseException:
    pass
import sys


class Host:
    """usblink's host: status only."""
    LINK_ASKS = ()

    def __init__(self, ui):
        self.ui = ui

    def link_status(self):
        import image
        import link
        c = self.ui.c
        st = {"mode": "prepare", "state": c.step(), "serial": c.serial, "profile": c.profile, "counter": c.counter,
              "image": image.IMAGE, "version": image.VERSION}
        st.update(link.status())
        return st


def run():
    import board
    if board.BOARD != "console-rp":
        raise RuntimeError("the prepare-rp image on a %s" % board.BOARD)
    import link
    link.start()
    import qlog
    qlog.TAP = link.log
    import usblink
    usblink.PORT = link
    import time
    import splash
    import lcd
    import signer
    import setup_s
    import prepare
    d = splash.begin()
    keys = lcd.Keys()
    splash.finish(keys, wait=False)
    sig = signer.load(soft=False)
    if sig.name != "atecc608":
        d.fill(lcd.BLACK)
        d.text("NO ATECC608 on the bus", 4, 60, lcd.RED)
        d.show()
        raise RuntimeError("no ATECC608 on the bus (%s)" % sig.name)
    ui = setup_s.UI(d, keys, sig, "dark", prepare.Ceremony(sig))
    usblink.host, usblink.mode = Host(ui), "prepare"
    qlog.write("prepare: chip %s, %s, step %s" % (ui.c.serial, ui.c.profile, ui.c.step()))
    while True:
        ui.tick(keys.pressed())         # "back" has nowhere to go: the screen stays
        ui.draw()
        usblink.poll(pump=True)
        time.sleep_ms(50)


try:
    run()
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

import usblink
usblink.run(None)
