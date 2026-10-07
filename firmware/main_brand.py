# picoquorum-image: brand
# main.py of the brand image (tools/fw push brand): the bench half of a branded key
# (docs/BRANDED-KEYS.md, brand.py) on the ceremony image's banner and screen. Bench only: it is
# NOT a signing console, and no user's console carries it. This first build brands a spare with the
# public test key.
#
# Maintenance works as on the other images: hold B (build1: the knob pressed) at power-up, or leave
# a file named "maint".
import sys
import os


def _maintenance():
    if "maint" in os.listdir():
        return True
    from machine import Pin
    import board
    return getattr(board, "MAINTENANCE", False) or Pin(board.MAINT, Pin.IN, Pin.PULL_UP).value() == 0     # B, or the knob's push on build1


try:
    if _maintenance():
        print("maintenance: nothing started")
    else:
        import lcd     # first: grabs the framebuffer while the heap is fresh
        import chipapp
        import brand
        chipapp.CEREMONY = brand.Ceremony
        chipapp.TITLE, chipapp.LABEL = "BRAND BENCH", "BRAND (quorum v2, spare)"
        chipapp.start()
except Exception as e:
    try:
        with open("error.log", "w") as f:
            sys.print_exception(e, f)
    except Exception:
        pass
    sys.print_exception(e)
