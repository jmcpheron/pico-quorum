# Emulator `network`: WiFi is up from the start. The host (browser or node) does the real HTTP.
# For the Wi-Fi setup screen (wifisetup.py) the air holds a few made-up networks, and a join checks
# the password: "emulator" is open, "Home Wi-Fi" wants "correct horse", "Cafe Guest" "espresso99".
STA_IF = 0
AP_IF = 1
STAT_IDLE = 0
STAT_CONNECTING = 1
STAT_WRONG_PASSWORD = -3
STAT_NO_AP_FOUND = -2
STAT_CONNECT_FAIL = -1
STAT_GOT_IP = 3

_host = "picowallet"
_state = {"active": True, "connected": True, "status": STAT_GOT_IP}
_ap = {"active": False, "ssid": "", "key": ""}
AIR = {"emulator": ("", -50, 0), "Home Wi-Fi": ("correct horse", -48, 3), "Cafe Guest": ("espresso99", -71, 3),
       "Neighbors 5G": ("not-yours-123", -83, 3)}


def hostname(name=None):
    global _host
    if name is None:
        return _host
    _host = name


def country(c=None):
    return "US"


class WLAN:
    def __init__(self, iface=STA_IF):
        self.iface = iface

    def active(self, v=None):
        st = _ap if self.iface == AP_IF else _state
        if v is None:
            return st["active"]
        st["active"] = bool(v)

    def connect(self, ssid=None, key=None, **kw):
        net = AIR.get(ssid)
        if net is None:
            _state["connected"], _state["status"] = False, STAT_NO_AP_FOUND
        elif net[0] and net[0] != (key or ""):
            _state["connected"], _state["status"] = False, STAT_WRONG_PASSWORD
        else:
            _state["connected"], _state["status"] = True, STAT_GOT_IP

    def disconnect(self):
        _state["connected"], _state["status"] = False, STAT_IDLE

    def isconnected(self):
        if self.iface == AP_IF:
            return _ap["active"]
        return _state["active"] and _state["connected"]

    def status(self, param=None):
        if param == "rssi":
            return -50
        if param == "stations":
            return []
        return _state["status"] if _state["active"] else STAT_IDLE

    def ifconfig(self, cfg=None):
        return ("127.0.0.1", "255.255.255.0", "127.0.0.1", "127.0.0.1")

    def ipconfig(self, *a, **k):
        return ("127.0.0.1", "255.255.255.0")

    def config(self, *a, **k):
        if self.iface == AP_IF:
            for name in ("ssid", "essid", "key", "password"):
                if name in k:
                    _ap["key" if name in ("key", "password") else "ssid"] = k[name]
        if a and a[0] == "mac":
            return b"\x02emu\x00\x01"
        if a and a[0] in ("ssid", "essid"):
            return _ap["ssid"] if self.iface == AP_IF else "emulator"
        return None

    def scan(self):
        return [(n.encode(), b"\x02emu\x00\x01", 1, rssi, sec, False) for n, (_k, rssi, sec) in AIR.items()]
