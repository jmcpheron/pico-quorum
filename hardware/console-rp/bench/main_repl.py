# Bench only, never on a console that holds a key: MicroPython's REPL on UART1, the CH343P and the
# USB-C, so a computer can drive the board without J3's USB. Load it as /main.py (swdload.py); then
# rawrepl.py runs files over the USB-C's serial port. On a console the USB-C must never reach the
# REPL (README.md, "the link"): take this off before the board leaves the bench.
import os
import machine

os.dupterm(machine.UART(1, 115200, tx=machine.Pin(20), rx=machine.Pin(21)))
