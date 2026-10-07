# picoquorum-image: brand
# main.py of the brand image (tools/fw push brand): the bench half of a branded key
# (docs/BRANDED-KEYS.md, brand.py) after the ceremony image's banner, drawn in the console's look
# (brand_ui.py). Bench only: it is NOT a signing console, and no user's console carries it. This
# first build brands a spare with the public test key.
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
        import fonts   # then the big blocks, as main_console.py does
        for _f in fonts.FILES:
            fonts.get(_f)
        import chipapp
        import brand
        import brand_ui
        chipapp.make_ui = lambda d, keys, sig, theme: brand_ui.UI(d, keys, sig, theme, brand.Ceremony(sig))
        chipapp.TITLE, chipapp.LABEL = "BRAND BENCH", "BRAND (quorum v2, spare)"
        chipapp.start()
except Exception as e:
    try:
        with open("error.log", "w") as f:
            sys.print_exception(e, f)
    except Exception:
        pass
    sys.print_exception(e)
