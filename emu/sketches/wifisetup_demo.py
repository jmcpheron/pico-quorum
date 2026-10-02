# wifisetup_demo: the Wi-Fi setup screen (firmware/wifisetup.py) on its timer, as a board with no
# Wi-Fi saved shows it at power-up. The emulator's air (emu/core/shims/network.py) has "Home Wi-Fi"
# (password "correct horse"), "Cafe Guest" ("espresso99"), "Neighbors 5G" and the open "emulator".
#   tools/emu run wifisetup_demo, then A for the list, A on a network, type, OK.
# The phone's page has no sockets here; send it a form from the REPL instead:
#   tools/emu exec 'wifisetup_demo.phone("Home Wi-Fi", "correct horse")'
import wifisetup
import wificfg


def phone(ssid, pw):
    """What the hotspot page does when the form is sent."""
    body = "ssid=%s&other=&pass=%s" % (ssid.replace(" ", "+"), pw.replace(" ", "+"))
    status, _ctype, page = wificfg.handle("POST", "/join", body, wifisetup.st)
    return status, wifisetup.st["state"], wifisetup.st["msg"]


def stop():
    wifisetup.stop()


wificfg.forget()
wifisetup.start()
