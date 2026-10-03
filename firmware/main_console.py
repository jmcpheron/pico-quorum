# picoquorum-image: console
# main.py of the production image (tools/fw push console copies this file to :main.py). boot.py
# already showed the splash and joined WiFi. This starts the Safe console on its timer and returns,
# so the USB REPL stays free for tools/fw (backup, verify, logs, config).
#
# Maintenance: hold B (on build1, the knob pressed down) while plugging the board in, and keep
# holding it until the onboard LED lights (or tools/fw leaves a file named "maint" on flash).
# The display stays off in maintenance. Then nothing starts: no
# console, no watchdog, only the USB REPL, for a restore or a repair.
import sys
import os


def _plain(title, lines, color=None):
    """framebuf's own 8 px font: works when nothing else does."""
    import lcd
    import splash
    splash.stop()               # the boot art's timer must not draw over this
    d = splash.begin()

    def draw():
        d.fill(lcd.BLACK)
        d.center_text(title, 60, color or lcd.YELLOW, 2)
        y = 100
        for line in lines:
            d.center_text(line[:(d.width - 8) // 8], y, lcd.WHITE)
            y += 14
        d.show()
    d.frames(draw)


def _maintenance():
    if "maint" in os.listdir():
        return True
    from machine import Pin
    import board
    return getattr(board, "MAINTENANCE", False) or Pin(board.MAINT, Pin.IN, Pin.PULL_UP).value() == 0     # B, or the knob's push on build1


try:
    import image
    if _maintenance():
        print("maintenance: the console is not started")
        # Leave the heap and USB free even when the display driver is broken.
        from machine import Pin
        Pin("LED", Pin.OUT).on()
    else:
        # The big blocks first, while the heap is still in one piece: the framebuffer (lcd), every
        # font (bold26 alone is 10.9 KB) and the 32 KB that HTTPS borrows for each call. Everything
        # imported after them fits in what is left; the other way round the heap ends up in pieces
        # too small for any of them (2026-09-26, on the board).
        # The boot art keeps moving on its timer (boot.py, splash.run) while this runs, except here:
        # its frames' small objects must not land between the big blocks.
        import gc
        import lcd
        import splash
        splash.pause()
        gc.collect()
        import fonts
        for _f in fonts.FILES:
            fonts.get(_f)
        import txservice
        txservice.reserve_early()
        splash.pause(False)
        import quorum
        quorum.start()
except Exception as e:
    try:
        with open("error.log", "w") as f:
            sys.print_exception(e, f)
    except Exception:
        pass
    sys.print_exception(e)
    try:
        import image
        _plain("STOPPED", ["The console did not start.", repr(e)[:29], repr(e)[29:58], "",
                           "error.log has the details.", "build " + image.BUILD])
    except Exception:
        pass
