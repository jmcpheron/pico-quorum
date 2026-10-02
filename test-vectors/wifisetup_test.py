"""Wi-Fi setup on the laptop: wifi.json, the checks, the phone's form and page, the captive DNS
answer, which networks net.py knows, when boot.py opens setup, and the keyboard on both inputs.
    python3 test-vectors/wifisetup_test.py"""
from pathlib import Path
import os
import sys
import tempfile
import types
from unittest.mock import patch

FW = Path(__file__).resolve().parents[1] / "firmware"
sys.path.insert(0, str(FW))
import wificfg as W  # noqa: E402

failed = 0


def check(ok, what):
    global failed
    print(("pass  " if ok else "FAIL  ") + what)
    failed += not ok


tmp = tempfile.mkdtemp()
os.chdir(tmp)

# ---- wifi.json
check(W.load() == [], "no wifi.json: no networks")
W.save("Home", "correct horse")
W.save("Cafe", "espresso99")
W.save("Home", "new password")
check(W.load() == [("Home", "new password"), ("Cafe", "espresso99")], "newest first, one copy of each")
for i in range(6):
    W.save("n%d" % i, "password%d" % i)
check(len(W.load()) == W.MAX_SAVED and W.load()[0][0] == "n5", "at most %d kept, newest first" % W.MAX_SAVED)
check(not os.path.exists("wifi.json.tmp"), "no temporary file left behind")
open("wifi.json", "w").write("{not json")
check(W.load() == [], "a broken wifi.json is no networks")
W.forget()
check(not os.path.exists("wifi.json") and W.load() == [], "forget removes it")
W.forget()

# ---- the checks
check(W.check("", "") is not None, "a name is needed")
check(W.check("x" * 33, "") is not None, "a name is at most 32 bytes")
check(W.check("é" * 17, "") is not None, "32 bytes, not characters")
check(W.check("Open", "") is None, "empty password: an open network")
check(W.check("Home", "short") is not None, "under 8 characters refused")
check(W.check("Home", "g" * 64) is not None and W.check("Home", "ab" * 32) is None, "64 characters only as a hex key")
check(W.check("Home", "pässwort1") is not None, "non-ASCII password refused")
check(W.check("Home", "correct horse") is None, "a good password passes")

# ---- the form
check(W.unquote("a+b%20c%2B%3D%e2%80%a6") == "a b c+=…", "form decoding: +, %XX, UTF-8")
check(W.unquote("100%") == "100%" and W.unquote("%zz") == "%zz", "a stray % stays")
f = W.parse_form(b"ssid=Home+Wi-Fi&other=&pass=p%26ss%3Dw0rd!")
check(f == {"ssid": "Home Wi-Fi", "other": "", "pass": "p&ss=w0rd!"}, "parse_form")
r = W.parse_request(b"POST /join HTTP/1.1\r\nHost: x\r\nContent-Length: 12\r\n\r\nssid=a&pass=")
check(r and r[0] == "POST" and r[1] == "/join" and r[2]["content-length"] == "12" and r[3] == b"ssid=a&pass=",
      "parse_request")
check(W.parse_request(b"GET / HTTP/1.1\r\n") is None, "an unfinished request is not one")
check(W.body_length({"content-length": "999999"}) == W.MAX_BODY and W.body_length({"content-length": "x"}) == 0,
      "body length capped, nonsense is 0")

st = {"state": "idle", "nets": ["Home", "<b>evil</b>"], "msg": "", "pending": None}
status, ctype, body = W.handle("GET", "/hotspot-detect.html", b"", st)
check(status.startswith("200") and b"<form" in body, "any path is the setup page (the phone's captive check)")
check(b"<b>evil" not in body and b"&lt;b&gt;evil" in body, "network names are escaped")
check(W.handle("GET", "/favicon.ico", b"", st)[0].startswith("404"), "no favicon")
W.handle("POST", "/join", b"ssid=Home&other=&pass=short", st)
check(st["pending"] is None and "8" in st["msg"], "a short password is refused on the page")
W.handle("POST", "/join", b"ssid=Home&other=My+Net&pass=correct+horse", st)
check(st["pending"] == ("My Net", "correct horse") and st["state"] == "joining", "typed name wins over the list")
_, _, body = W.handle("POST", "/join", b"ssid=Other&pass=12345678", st)
check(st["pending"] == ("My Net", "correct horse") and b"refresh" in body, "a second form while joining is ignored")
st.update(state="ok", ssid="My Net")
check(b"Connected" in W.handle("GET", "/", b"", st)[2], "the page says connected")
resp = W.response("200 OK", "text/html", b"hi")
check(resp.startswith(b"HTTP/1.1 200 OK\r\n") and b"Content-Length: 2\r\n" in resp and resp.endswith(b"\r\n\r\nhi"),
      "response")

# ---- QR text
check(W.qr_join("A;B", 'p:"x') == 'WIFI:T:WPA;S:A\\;B;P:p\\:\\"x;;', "QR join text escapes ; : \"")

# ---- DNS
q = bytes.fromhex("123401000001000000000000") + b"\x07captive\x05apple\x03com\x00" + b"\x00\x01\x00\x01"
a = W.dns_reply(q, bytes([192, 168, 4, 1]))
check(a[:2] == q[:2] and a[2:4] == b"\x81\x80" and a[6:8] == b"\x00\x01" and a.endswith(bytes([192, 168, 4, 1])),
      "an A query gets the hotspot's address")
q6 = q[:-4] + b"\x00\x1c\x00\x01"
a6 = W.dns_reply(q6, bytes([192, 168, 4, 1]))
check(a6[6:8] == b"\x00\x00" and len(a6) == len(q6), "AAAA: no answer")
check(W.dns_reply(a, b"\0\0\0\0") is None and W.dns_reply(b"\0" * 5, b"\0\0\0\0") is None, "replies and junk ignored")

# ---- net.networks: wifi.json first, then secrets.py
class _Pin:
    IN, OUT, PULL_UP = 0, 1, 2

    def __init__(self, *a, **k):
        pass

    def on(self):
        pass

    def off(self):
        pass

    def value(self, *a):
        return 1


def _net(secrets):
    mods = {"machine": types.SimpleNamespace(Pin=_Pin), "network": types.SimpleNamespace(),
            "secrets": secrets}
    with patch.dict(sys.modules, mods):
        sys.modules.pop("net", None)
        import net
        sys.modules.pop("net", None)
    return net


n = _net(types.SimpleNamespace(WIFI_SSID="Dev", WIFI_PASS="devpass1"))
check(n.networks() == [("Dev", "devpass1")] and n.ssid() == "Dev", "secrets.py alone")
W.save("Home", "correct horse")
check(n.networks() == [("Home", "correct horse"), ("Dev", "devpass1")], "wifi.json before secrets.py")
W.save("Dev", "from setup")
check(n.networks() == [("Dev", "from setup"), ("Home", "correct horse")], "setup's copy of a name wins")
W.forget()
check(_net(types.SimpleNamespace(WIFI_SSID="your-ssid", WIFI_PASS="x")).networks() == [], "the example's placeholder is no network")
check(_net(None).networks() == [] and _net(None).ssid() == "", "no secrets.py, no wifi.json: nothing")

# ---- boot.py: when setup opens
boot = (FW / "boot.py").read_text()


def _boot(nets, image="console", y_held=False, files=(), maint_held=False):
    ran = []
    board = types.SimpleNamespace(MAINT=1, SETUP=2)

    class Pin(_Pin):
        def __init__(self, p, *a, **k):
            self.p = p

        def value(self, *a):
            return 0 if (self.p == 2 and y_held) or (self.p == 1 and maint_held) else 1

    net = types.SimpleNamespace(networks=lambda: nets, ssid=lambda: nets[0][0] if nets else "",
                                start=lambda progress=None: types.SimpleNamespace(isconnected=lambda: False))
    mods = {"board": board, "machine": types.SimpleNamespace(Pin=Pin), "net": net, "splash": None, "lcd": None,
            "time": types.SimpleNamespace(ticks_ms=lambda: 0),       # boot.py notes when it started (MicroPython's clock)
            "image": types.SimpleNamespace(IMAGE=image), "wifisetup": types.SimpleNamespace(run=lambda: ran.append(1))}
    with patch.dict(sys.modules, mods), patch("os.listdir", return_value=list(files)), patch("os.remove"):
        exec(compile(boot, "boot.py", "exec"), {"print": lambda *a: None})
    return bool(ran)


check(_boot([]), "no network known: setup")
check(not _boot([("Home", "pw")]), "a network known: no setup")
check(_boot([("Home", "pw")], y_held=True), "Y held at power-up: setup anyway")
check(not _boot([], image="ceremony"), "the ceremony image works offline: no setup")
check(_boot([("Home", "pw")], files=["wifisetup"]), "Device -> Wi-Fi (the wifisetup file): setup")
check(_boot([("Home", "pw")], files=["wifisetup"], maint_held=True),
      "the knob still down from that press (build1's maintenance key): setup, not maintenance")
check(not _boot([("Home", "pw")], maint_held=True), "the knob held with no request: maintenance, no setup")
check(not _boot([("Home", "pw")], files=["wifisetup", "maint"]), "the maint file beats a request")

# ---- the keyboard, on both inputs
def _kb(knob):
    L = types.SimpleNamespace(KNOB=knob, SMALL=False, W=240, H=240, color=lambda *a: 0, WHITE=0, BLACK=0)
    T = types.SimpleNamespace(RGB={"bg": (0, 0, 0), "config": (0, 0, 255), "learn": (255, 200, 0)})
    with patch.dict(sys.modules, {"network": types.SimpleNamespace(), "lcd": L, "theme": T}):
        sys.modules.pop("wifisetup", None)
        import wifisetup
        sys.modules.pop("wifisetup", None)
    return wifisetup


ws = _kb(True)
k = ws.Keyboard("t", "pass")
seen = set()
for _ in range(45):
    seen.add((k.r, k.c))
    k.move("down")
check(len(seen) == 45 and (k.r, k.c) == (0, 0), "knob: clockwise visits all 45 keys once, then wraps")
k.move("up")
check((k.r, k.c) == (4, 4), "knob: anticlockwise from the first key is OK")

ws = _kb(False)
k = ws.Keyboard("t", "pass")
k.move("left")
check((k.r, k.c) == (0, 9), "joystick: left wraps along the row")
for _ in range(4):
    k.move("down")
check((k.r, k.c) == (4, 4), "joystick: down to the bottom row lands under it (OK)")
k.move("down")
check((k.r, k.c) == (0, 8), "joystick: down from the bottom row wraps to the top")

typed = set()
for page in range(3):
    k.page = page
    for r in range(4):
        for c in range(10):
            k.r, k.c, k.text = r, c, ""
            k.type()
            typed.add(k.text)
k.r, k.c, k.text = 4, 2, ""
k.type()
typed.add(k.text)
missing = [chr(i) for i in range(32, 127) if chr(i) not in typed]
check(not missing, "every printable ASCII character can be typed" + (": missing %r" % "".join(missing) if missing else ""))
k.text = "ab"
k.r, k.c = 4, 3
k.type()
check(k.text == "a", "del deletes")
k.r, k.c = 4, 4
check(k.type() is True, "OK says done")
k = ws.Keyboard("t", "ssid", limit=3)
for _ in range(5):
    k.type()
check(k.text == "aaa", "the limit holds")

print("%d FAILED" % failed if failed else "wifisetup: all pass")
sys.exit(1 if failed else 0)
