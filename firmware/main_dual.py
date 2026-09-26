# picoquorum-image: dual
# main.py of the dual image (tools/fw push dual), for while a new chip is being set up. The board
# carries both the console and the ceremony and runs the one the chip on the bus needs, read at
# every boot:
#   the pinned chip (secrets.QUORUM_EXPECT)          -> the console, production rules
#   a fresh chip, or a quorum v1 chip not yet sealed -> the ceremony (provision.py)
#   anything else, or no chip                        -> the console (it says Not pinned / No chip)
# Once the new chip is sealed, enrolled and pinned, the board goes back to the console image.
#
# Maintenance works as on the other images: hold B at power-up, or leave a file named "maint".
import sys
import os
import gc


def _maintenance():
    if "maint" in os.listdir():
        return True
    from machine import Pin
    return Pin(17, Pin.IN, Pin.PULL_UP).value() == 0      # B, lcd.KEYS


def which():
    """("console" | "ceremony", serial, profile) for the chip on the bus. The ceremony only for a
    chip that is not the pinned one and is fresh, or half way through quorum v1 (data zone open)."""
    try:
        import secrets
        exp = getattr(secrets, "QUORUM_EXPECT", None)
    except ImportError:
        exp = None
    try:
        import atecc
        import chipcfg
        c = atecc.ATECC608()
        serial = "".join("%02x" % b for b in c.serial())
        cfg = c.read_config_all()
        profile = chipcfg.identify(cfg)
    except Exception:
        return "console", "", ""
    if exp and serial == str(exp.get("serial", "")).lower():
        return "console", serial, profile
    if profile == "factory" or (profile == "quorum-v1" and cfg[86] != 0x00):
        return "ceremony", serial, profile
    return "console", serial, profile


def run():
    import image
    if _maintenance():
        print("maintenance: nothing started")
        return
    path, serial, profile = which()
    gc.collect()
    print("dual: %s for chip %s (%s)" % (path, serial or "none", profile or "-"))
    if path == "ceremony":
        image.PRODUCTION = False        # the ceremony honours ALLOW_* (and still needs the arm and a hold)
        import lcd
        import chipapp
        chipapp.start()
    else:
        image.PRODUCTION = True
        import lcd                      # the big blocks first, as main_console.py does
        import fonts
        for _f in fonts.FILES:
            fonts.get(_f)
        import txservice
        txservice.reserve_early()
        import quorum
        quorum.start()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        try:
            with open("error.log", "w") as f:
                sys.print_exception(e, f)
        except Exception:
            pass
        sys.print_exception(e)
