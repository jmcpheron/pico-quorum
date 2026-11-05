# boot.py of the console-rp image (firmware/manifest.json "boot": tools/fw build copies it to boot.py).
# console-rp has no radio and no maintenance key (board.py): this is boot.py without either. Ctrl-C
# off first, as boot.py does; then the boot art, drawing itself on its timer while main.py loads.
try:
    import micropython
    micropython.kbd_intr(-1)
except Exception:
    pass
import board
board.MAINTENANCE = board.WIFI_SETUP = False
try:
    import splash
    splash.begin()
    if splash._art is not None:
        splash.run()
except Exception as e:
    print("boot screen:", e)
