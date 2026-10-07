# Which firmware image this board runs. `tools/fw build` writes build.py into the files it pushes
# (never committed): IMAGE is "console" (the production Safe console: nothing else on the board
# can use the chip), "ceremony" (the chip map and provisioning, for a fresh chip), "brand" (the
# bench half of a branded key, brand.py, on the ceremony's screen), or "dual" (both,
# for while a new chip is being set up: main_dual.py picks one at each boot from the chip on the
# bus). Without build.py this is a development board or the emulator, and everything stays as
# flexible as before.
#
# PRODUCTION: the console's rules (the ALLOW_* flags and the software key ignored, no network
# console). On by default for "dual"; main_dual.py turns it off only for the ceremony, and only
# when the chip on the bus is fresh.
# VERSION: the release, year.month.n (firmware/manifest.json "version"; git tag fw-<version>);
# BUILD: the commit it was built from.
# RELEASE: the release fingerprint, a SHA-256 of the image's source files (tools/releases/fingerprint.mjs).
# The emulator computes the same value over the files it runs, so a Pico and a browser running one
# release show the same blockie (seed "0x" + RELEASE) on the Device screen. "" without build.py.
try:
    import build as _b
    IMAGE, BUILD, DATE = _b.IMAGE, _b.BUILD, int(getattr(_b, "DATE", 0))
    VERSION = getattr(_b, "VERSION", "")
    RELEASE = getattr(_b, "RELEASE", "")
except ImportError:
    IMAGE, BUILD, DATE, VERSION, RELEASE = "dev", "dev", 0, "", ""

SEED = "0x" + RELEASE if RELEASE else ""          # the release's blockie
SHORT = RELEASE[:4] + "\u00b7" + RELEASE[4:8] if RELEASE else ""     # how screens name it: 4c86·c754

PRODUCTION = IMAGE in ("console", "dual")
