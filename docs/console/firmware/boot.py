# Maintenance is decided before importing the display or network. Latch the physical key so
# releasing it during startup cannot accidentally start the console.
import os
import board
from machine import Pin
# A Wi-Fi setup request from the Device screen outranks a held key: on build1 the knob's press that
# chose Wi-Fi is also the maintenance key, and it may still be down as the board restarts (it was,
# 2026-10-01: Build 1 came up in maintenance). The request is taken once; the maint file always wins.
_ask = "wifisetup" in os.listdir()
board.MAINTENANCE = "maint" in os.listdir() or (not _ask and Pin(board.MAINT, Pin.IN, Pin.PULL_UP).value() == 0)


def _asked():
    """The console's Device screen asks for Wi-Fi setup by leaving a file named "wifisetup" and
    restarting: the way in on a board without a Y button (build1's knob). Taken once, so a setup
    that fails never comes back by itself."""
    if "wifisetup" not in os.listdir():
        return False
    try:
        os.remove("wifisetup")
    except OSError:
        pass
    return True


# Y held at power-up, or Wi-Fi on the Device screen: Wi-Fi setup even with a network saved (a new
# router, a new password).
board.WIFI_SETUP = not board.MAINTENANCE and (Pin(board.SETUP, Pin.IN, Pin.PULL_UP).value() == 0 or _asked())


def _wifi_setup(net):
    """Wi-Fi setup (wifisetup.py) when Y was held, or when no network is known and this image needs
    one (the ceremony image works offline). It restarts the board when it is done; if it fails,
    boot carries on without Wi-Fi."""
    if not board.WIFI_SETUP:
        if net.networks():
            return
        import image
        if image.IMAGE == "ceremony":
            return
    try:
        import wifisetup
        wifisetup.run()
    except Exception as e:
        import sys
        sys.print_exception(e)


def _normal_boot():
    # Runs before main.py: the boot screen, then WiFi and, if secrets.py enables it, the development
    # console (passwordless; off by default). The screen is best effort: WiFi comes up without it.
    # The WiFi wait is 12 s at most and any key skips it: the chip map, the LAB and snake work
    # without a network.
    # The console image does not wait here: its art draws itself on a timer (splash.run) and WiFi
    # joins while main.py imports and the console checks its chip; quorum.start waits for the rest.
    import time
    import net
    _wifi_setup(net)
    net.boot_at = time.ticks_ms()
    try:
        import image
        console = image.IMAGE == "console"
    except Exception:
        console = False
    try:
        import splash
        import lcd
        splash.begin()
        _keys = lcd.Keys()
        _ssid = net.ssid()

        def _spin(ms):
            splash.spin("wifi", ("join " + _ssid)[:12] + (" press skips" if lcd.KNOB else " A skips") if _ssid else "no Wi-Fi saved")
            return bool(_keys.pressed())
    except Exception as e:
        print("boot screen:", e)
        splash = _spin = None
    if console and splash and splash._art is not None:
        splash.run()
        try:
            net.begin()                 # the radio joins while the console starts
        except Exception as e:
            print("wifi:", e)
        return
    wlan = net.start(progress=_spin)
    if splash:
        splash.wifi_row(wlan, _ssid)
        splash.wifi_at = time.ticks_ms()    # for quorum's "boot ms" line in log.txt

if board.MAINTENANCE:
    Pin(board.LED, Pin.OUT).on()
    print("maintenance: USB ready; display, WiFi and console skipped")
else:
    _normal_boot()
