# The Wi-Fi networks this board has been given (wifi.json), and the parts of the Wi-Fi setup
# hotspot (wifisetup.py) that need no radio: the checks on a name and password, the form a phone
# fills in, the page it gets back, and the one-answer DNS that sends a phone's "is this a captive
# portal?" check to that page. Pure Python, so test-vectors/wifisetup_test.py runs it on the laptop.
#
# wifi.json is written only by the setup screen and read by net.py before secrets.py's WIFI_SSID.
# It holds Wi-Fi and nothing else: setup can never touch the pin, the Safes or the API key.
import json
import os

FILE = "wifi.json"
MAX_SAVED = 4           # the newest first; a fifth network pushes the oldest out
MAX_BODY = 1024         # a form bigger than this is not ours


def load(path=FILE):
    """[(ssid, password)], the most recently set up first. A missing or broken file is no networks."""
    try:
        with open(path) as f:
            d = json.load(f)
        return [(n["ssid"], n.get("pass", "")) for n in d["networks"] if n.get("ssid")]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def save(ssid, pw, path=FILE):
    """Put this network first, keep the others (but not a second copy of this one)."""
    nets = [(ssid, pw)] + [n for n in load(path) if n[0] != ssid]
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"networks": [{"ssid": s, "pass": p} for s, p in nets[:MAX_SAVED]]}, f)
    os.rename(tmp, path)        # a power cut leaves the old file or the new one, never half of one


def forget(path=FILE):
    try:
        os.remove(path)
    except OSError:
        pass


def check(ssid, pw):
    """Why this name and password cannot be a Wi-Fi network, or None. An empty password is an
    open network; otherwise WPA2 wants 8 to 63 printable ASCII characters (or 64 hex digits)."""
    if not ssid:
        return "Pick or type a network name"
    if len(ssid.encode()) > 32:
        return "A network name is at most 32 bytes"
    if not pw:
        return None
    if len(pw) == 64 and all(c in "0123456789abcdefABCDEF" for c in pw):
        return None
    if any(not " " <= c <= "~" for c in pw):
        return "The password has a character Wi-Fi does not allow"
    if len(pw) < 8:
        return "A Wi-Fi password is at least 8 characters"
    if len(pw) > 63:
        return "A Wi-Fi password is at most 63 characters"
    return None


def qr_join(ssid, pw):
    """The text of a QR code that a phone's camera turns into "join this network"."""
    esc = lambda s: "".join("\\" + c if c in "\\;,:\"" else c for c in s)
    return "WIFI:T:WPA;S:%s;P:%s;;" % (esc(ssid), esc(pw))


# ------------------------------------------------------------------------------------- the form

def unquote(s):
    """application/x-www-form-urlencoded value -> str."""
    s = s.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == "%" and _hex(s[i + 1:i + 3]):
            out.append(int(s[i + 1:i + 3], 16))
            i += 3
        else:
            out.extend(c.encode())
            i += 1
    try:
        return out.decode()
    except UnicodeError:
        return ""


def _hex(s):
    return len(s) == 2 and all(c in "0123456789abcdefABCDEF" for c in s)


def parse_form(body):
    if isinstance(body, (bytes, bytearray)):
        try:
            body = bytes(body).decode()
        except UnicodeError:
            return {}
    out = {}
    for part in body.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[unquote(k)] = unquote(v)
    return out


def parse_request(raw):
    """(method, path, headers, body) from the bytes a browser sent, or None if they are not a request."""
    head, sep, body = bytes(raw).partition(b"\r\n\r\n")
    if not sep:
        return None
    try:
        lines = head.decode().split("\r\n")
        method, path = lines[0].split(" ")[:2]
    except (UnicodeError, ValueError):
        return None
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return method, path, headers, body


def body_length(headers):
    try:
        return max(0, min(int(headers.get("content-length", "0")), MAX_BODY))
    except ValueError:
        return 0


# ------------------------------------------------------------------------------------- the page

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_CSS = ("body{font:17px system-ui,sans-serif;margin:0;padding:20px;background:#060a1a;color:#eef}"
        "h1{font-size:22px;margin:0 0 14px}label{display:block;margin:14px 0 6px;color:#aab}"
        "select,input{width:100%;box-sizing:border-box;font-size:18px;padding:11px;border-radius:9px;"
        "border:1px solid #3a4670;background:#141e3a;color:#fff}"
        "button{margin-top:20px;width:100%;font-size:19px;padding:14px;border:0;border-radius:10px;"
        "background:#2f7dff;color:#fff}.m{padding:12px;border-radius:9px;margin-bottom:8px}"
        ".bad{background:#4a1418;color:#ffb4ae}.ok{background:#0d3d24;color:#9ff0c0}.wait{background:#1d2a52}"
        "small{color:#8890a8}")


def page(st):
    """The setup page, for whatever state setup is in (st: wifisetup.st)."""
    state, ssid = st.get("state"), esc(st.get("ssid") or "")
    out = ["<!doctype html><html><head><meta charset=utf-8>"
           "<meta name=viewport content='width=device-width,initial-scale=1'><title>%s Wi-Fi</title>"
           % esc(st.get("name", "PicoQuorum"))]
    if state == "joining":
        out.append("<meta http-equiv=refresh content=3>")
    out.append("<style>%s</style></head><body><h1>Connect %s to <span style=white-space:nowrap>Wi-Fi</span></h1>"
               % (_CSS, esc(st.get("name", "PicoQuorum"))))
    if state == "joining":
        out.append("<p class='m wait'>Joining <b>%s</b>&hellip;</p><p>Watch the console's screen. "
                   "When it says <b>Connected</b> you are done and can close this page.</p></body></html>" % ssid)
        return "".join(out)
    if state == "ok":
        out.append("<p class='m ok'>Connected to <b>%s</b>. The console is restarting. "
                   "You can close this page.</p></body></html>" % ssid)
        return "".join(out)
    if st.get("msg"):
        out.append("<p class='m bad'>%s</p>" % esc(st["msg"]))
    out.append("<form method=post action=/join><label for=s>Your Wi-Fi network</label><select id=s name=ssid>")
    for name in st.get("nets", ()):
        sel = " selected" if name == st.get("ssid") else ""
        out.append("<option value=\"%s\"%s>%s</option>" % (esc(name), sel, esc(name)))
    out.append("<option value=''>Another network (type it below)</option></select>"
               "<label for=o>Network name, if it is not in the list</label>"
               "<input id=o name=other autocapitalize=off autocorrect=off spellcheck=false maxlength=32>"
               "<label for=p>Wi-Fi password</label>"
               "<input id=p name=pass type=password autocapitalize=off autocorrect=off spellcheck=false maxlength=64>"
               "<label style='display:flex;gap:8px;align-items:center'><input type=checkbox style='width:auto' "
               "onclick=\"p.type=this.checked?'text':'password'\">Show password</label>"
               "<button>Connect</button></form><p><small>Leave the password empty for an open network. "
               "This page only sets the console's Wi-Fi.</small></p></body></html>")
    return "".join(out)


def handle(method, path, body, st):
    """One request to the setup hotspot -> (status, content type, body bytes). Every path is the
    page, which is what makes a phone show it by itself as a sign-in page after it joins.
    A POST of the form asks wifisetup to join: st["pending"] = (ssid, password)."""
    if path.startswith("/favicon"):
        return "404 Not Found", "text/plain", b"not here"
    if method == "POST" and st.get("state") not in ("joining", "ok"):
        f = parse_form(body)
        ssid = (f.get("other") or "").strip() or f.get("ssid", "")
        pw = f.get("pass", "")
        why = check(ssid, pw)
        if why:
            st["msg"] = why
        else:
            st["pending"] = (ssid, pw)
            st["state"], st["ssid"], st["msg"] = "joining", ssid, ""
    return "200 OK", "text/html; charset=utf-8", page(st).encode()


def response(status, ctype, body):
    return ("HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nCache-Control: no-store\r\n"
            "Connection: close\r\n\r\n" % (status, ctype, len(body))).encode() + body


# ------------------------------------------------------------------------------------- DNS

def dns_reply(q, ip):
    """Answer one DNS query: every name is ip (4 bytes). Only A records get an answer; anything
    else (AAAA, say) gets an empty one, which sends the phone back to IPv4. None: not a query."""
    if len(q) < 17 or q[2] & 0x80 or q[4:6] != b"\x00\x01":
        return None
    i = 12
    while i < len(q) and q[i]:
        if q[i] & 0xC0:
            return None
        i += q[i] + 1
    end = i + 5
    if end > len(q):
        return None
    a = q[i + 1:i + 3] == b"\x00\x01"
    head = bytes(q[:2]) + b"\x81\x80\x00\x01" + (b"\x00\x01" if a else b"\x00\x00") + b"\x00\x00\x00\x00"
    ans = b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + bytes(ip) if a else b""
    return head + bytes(q[12:end]) + ans
