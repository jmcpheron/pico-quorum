# Maintenance is decided before importing the display or network. Latch the physical key so
# releasing it during startup cannot accidentally start the console.
import os
import board
from machine import Pin
board.MAINTENANCE = "maint" in os.listdir() or Pin(board.MAINT, Pin.IN, Pin.PULL_UP).value() == 0

def _normal_boot():
    # Runs before main.py: WiFi asked to join, the boot screen while it does, then the wait for it
    # and, if secrets.py enables it, the development console (passwordless; off by default). The
    # screen is best effort: WiFi comes up without it.
    # The WiFi wait is 12 s at most and any key skips it: the wallet, the chip map, the LAB and snake
    # work without a network, and wallet.py keeps retrying in the background.
    import time
    import net
    net.boot_at = time.ticks_ms()
    try:
        net.begin()                     # the radio joins while the boot screen comes up
    except Exception as e:
        print("wifi:", e)
    try:
        import splash
        import lcd
        splash.begin()
        _keys = lcd.Keys()
        _ssid = getattr(net.secrets, "WIFI_SSID", "") if net.secrets else ""

        def _spin(ms):
            splash.spin("wifi", ("join " + _ssid)[:12] + (" press skips" if lcd.KNOB else " A skips") if _ssid else "no secrets.py")
            return bool(_keys.pressed())
    except Exception as e:
        print("boot screen:", e)
        splash = _spin = None
    wlan = net.start(progress=_spin)
    if splash:
        splash.wifi_row(wlan, _ssid)
        splash.wifi_at = time.ticks_ms()    # for quorum's "boot ms" line in log.txt

if board.MAINTENANCE:
    Pin("LED", Pin.OUT).on()
    print("maintenance: USB ready; display, WiFi and console skipped")
else:
    _normal_boot()
