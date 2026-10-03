# Which firmware image this board runs. `tools/fw build` writes build.py into the files it pushes
# (never committed): IMAGE is "console" (the production Safe console: nothing else on the board
# can use the chip), "ceremony" (the chip map and provisioning, for a fresh chip), or "dual" (both,
# for while a new chip is being set up: main_dual.py picks one at each boot from the chip on the
# bus). Without build.py this is a development board or the emulator, and everything stays as
# flexible as before.
#
# PRODUCTION: the console's rules (the ALLOW_* flags and the software key ignored, no network
# console). On by default for "dual"; main_dual.py turns it off only for the ceremony, and only
# when the chip on the bus is fresh.
# VERSION: the release, year.month.n (firmware/manifest.json "version"; git tag fw-<version>);
# BUILD: the commit it was built from.
try:
    import build as _b
    IMAGE, BUILD, DATE = _b.IMAGE, _b.BUILD, int(getattr(_b, "DATE", 0))
    VERSION = getattr(_b, "VERSION", "")
except ImportError:
    IMAGE, BUILD, DATE, VERSION = "dev", "dev", 0, ""

PRODUCTION = IMAGE in ("console", "dual")
