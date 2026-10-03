# picoquorum-image: dual
# main.py of the dual image (tools/fw push dual), for while a new chip is being set up. The board
# carries both the console and the ceremony and runs the one the chip on the bus needs, read at
# every boot:
#   a pinned chip (secrets.QUORUM_EXPECT, one or a list) -> the console, production rules
#   a fresh chip, or a quorum v1 chip not yet sealed -> the ceremony (provision.py)
#   a fresh Trust M, or one not yet sealed           -> the ceremony (provision_tm.py)
#   a sealed Trust M, spares open, ALLOW_LOCK on     -> the ceremony, for T9 (freeze the spares)
#   anything else, or no chip                        -> the console (it says Not pinned / No chip)
# Once the new chip is sealed, enrolled and pinned, the board goes back to the console image.
#
# Maintenance works as on the other images: hold B (build1: the knob pressed) at power-up, or leave
# a file named "maint".
import sys
import os
import gc


def _maintenance():
    if "maint" in os.listdir():
        return True
    from machine import Pin
    import board
    return getattr(board, "MAINTENANCE", False) or Pin(board.MAINT, Pin.IN, Pin.PULL_UP).value() == 0     # B, or the knob's push on build1


def which():
    """("console" | "ceremony", serial, profile) for the chip on the bus, an ATECC608 or a Trust M
    (signer.load finds it). The ceremony only for a chip that is not the pinned one and is fresh, or
    half way through its ceremony (quorum v1 with the data zone open; a Trust M not yet sealed), or
    a sealed Trust M whose spares are still open while ALLOW_LOCK asks for T9."""
    try:
        import secrets
        exp = getattr(secrets, "QUORUM_EXPECT", None)
        allow_lock = bool(getattr(secrets, "ALLOW_LOCK", False))
    except ImportError:
        exp, allow_lock = None, False
    import policy
    pinned = policy.pins(exp)
    try:
        import signer
        s = signer.load(soft=False, pins=pinned)
        if not signer.is_chip(s):
            return "console", "", ""
        serial = s.serial()
        profile = s.profile()
        if policy.pick(pinned, serial):
            return "console", serial, profile
        need = s.needs_ceremony()
        if not need and allow_lock and profile == "quorum-tm1":
            need = bool(s.spares_open())        # sealed before T9: only when asked for, never when pinned
    except Exception:
        return "console", "", ""
    if need:
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
