# picoquorum-image: ceremony
# main.py of the ceremony image (tools/fw push ceremony copies this file to :main.py): the chip
# map and, for a fresh chip, the provisioning ceremony (provision.py). It is NOT a signing console:
# it has no transaction service and no Safe. It exists on the board only while a chip is being
# set up, and tools/fw refuses to push it onto a board whose QUORUM_EXPECT pins the chip it holds.
#
# Maintenance works as on the console image: hold B at power-up, or leave a file named "maint".
import sys
import os


def _maintenance():
    if "maint" in os.listdir():
        return True
    from machine import Pin
    return Pin(17, Pin.IN, Pin.PULL_UP).value() == 0      # B, lcd.KEYS


try:
    if _maintenance():
        print("maintenance: nothing started")
    else:
        import lcd     # first: grabs the framebuffer while the heap is fresh
        import chipapp
        chipapp.start()
except Exception as e:
    try:
        with open("error.log", "w") as f:
            sys.print_exception(e, f)
    except Exception:
        pass
    sys.print_exception(e)
