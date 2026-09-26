# Which firmware image this board runs. `tools/fw build` writes build.py into the files it pushes
# (never committed): IMAGE is "console" (the production Safe console: nothing else on the board
# can use the chip) or "ceremony" (the chip map and provisioning, for a fresh chip). Without
# build.py this is a development board or the emulator, and everything stays as flexible as before.
try:
    import build as _b
    IMAGE, BUILD, DATE = _b.IMAGE, _b.BUILD, int(getattr(_b, "DATE", 0))
except ImportError:
    IMAGE, BUILD, DATE = "dev", "dev", 0

PRODUCTION = IMAGE == "console"
