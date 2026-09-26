# picoquorum-image: console
# main.py of the production image (tools/fw push console copies this file to :main.py). boot.py
# already showed the splash and joined WiFi. This starts the Safe console on its timer and returns,
# so the USB REPL stays free for tools/fw (backup, verify, logs, config).
#
# Maintenance: hold B while plugging the board in, and keep holding it until the screen says
# MAINTENANCE (or tools/fw leaves a file named "maint" on the flash). Then nothing starts: no
# console, no watchdog, only the USB REPL, for a restore or a repair.
import sys
import os


def _plain(title, lines, color=None):
    """framebuf's own 8 px font: works when nothing else does."""
    import lcd
    import splash
    d = splash.begin()
    d.fill(lcd.BLACK)
    d.center_text(title, 60, color or lcd.YELLOW, 2)
    y = 100
    for line in lines:
        d.center_text(line[:29], y, lcd.WHITE)
        y += 14
    d.show()


def _maintenance():
    if "maint" in os.listdir():
        return True
    from machine import Pin
    return Pin(17, Pin.IN, Pin.PULL_UP).value() == 0      # B, lcd.KEYS


try:
    import image
    if _maintenance():
        print("maintenance: the console is not started")
        _plain("MAINTENANCE", ["USB only.", "The console is not running", "and nothing can sign.", "",
                               "tools/fw restore or push,", "then unplug and replug.", "", "build " + image.BUILD])
    else:
        import lcd     # first: grabs the framebuffer while the heap is fresh
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
