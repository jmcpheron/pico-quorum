# picoquorum-image: console-rp
# main.py of the console-rp image (hardware/console-rp: an RP2350 with no radio, its USB-C reaching only a
# CH343P on UART1). boot_rp.py started the boot art. This takes the link (link.py) and its line buffer
# first, while the heap is whole, then the console's big blocks, and starts the Safe console with the
# link as its way out. Then the loop is usblink's, which never returns: the computer gets the link's
# few lines (docs/USB-LINK.md), never a REPL and never the chip.
#
# No maintenance here: the USB-C can't reach a REPL, so nothing on this board could use one. The image
# comes and goes over SWD, on the bench (hardware/console-rp/bench/swdload.py).
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
    import fonts
    for _f in fonts.FILES:
        fonts.get(_f)
    import quorum
    quorum.NET, quorum.VIA = link, link     # the way out, and the transport txservice calls
    splash.pause(False)
    quorum.start()
    return quorum


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
