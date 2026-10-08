# Wi-Fi setup: what a board with no Wi-Fi shows at power-up (boot.py), and what holding Y at
# power-up opens on any board. Two ways in, on one screen:
#   - a phone: the console makes its own hotspot and shows a QR code that joins it. The phone then
#     opens the setup page by itself (every web address on the hotspot leads to it), and the
#     person picks their network and types the password there.
#   - the console alone: a list of the networks it can see, then an on-screen keyboard. The
#     Waveshare joystick moves around the keyboard; the build1 knob walks along it one key at a
#     time, and pressing types.
# Either way the console joins the network itself before saving it to wifi.json (wificfg.py), so a
# wrong password is caught here and not at the next boot. Then it restarts.
#
# Nothing else is reachable from here: the hotspot page sets Wi-Fi and nothing more, and the
# console is not running (boot.py starts this before main.py and never returns to it).
#
#   wifisetup.run()     blocking, from boot.py: never returns (restarts the board)
#   wifisetup.start()   the same on a timer, for the emulator (emu/sketches/wifisetup_demo.py)
import os
import time
import network
import board
import lcd as L
import theme as T
import wificfg

AP_IP = "192.168.4.1"
JOIN_S = 20             # a join that has not finished by now has failed
STA_IDLE, STA_CONNECTING = 0, 1
NAME = "PicoQuorum"

# Shared with wificfg.handle (the phone's page): state, ssid, msg, nets, pending.
st = {"state": "idle", "ssid": "", "msg": "", "nets": [], "pending": None, "name": NAME}
view = "qr"             # qr | list | kbd | join | done
qr_mode = "join"        # join: the hotspot's QR; url: a phone is on it, the page's QR
sel = 0                 # list row
scan = []               # [(ssid, rssi, secured)]
kb = None               # the keyboard
ap = sta = web = dns = None
ap_ssid = ap_pass = ""
can_cancel = False
_d = _keys = _timer = None
_dirty = True
_t_join = 0
_t_done = 0
_origin = "qr"          # where a failed join goes back to
_busy = False
_frame = 0


# ------------------------------------------------------------------------------------- radio

def _rand(n, alphabet="abcdefghjkmnpqrstuvwxyz23456789"):
    return "".join(alphabet[b % len(alphabet)] for b in os.urandom(n))


def _scan():
    """The networks in range, strongest first, each name once."""
    global scan
    best = {}
    try:
        for s, _bssid, _ch, rssi, sec, *_ in sta.scan():
            try:
                name = s.decode()
            except UnicodeError:
                continue
            if name and (name not in best or rssi > best[name][0]):
                best[name] = (rssi, bool(sec))
    except Exception as e:
        print("wifisetup: scan:", e)
    scan = sorted(((n, r, s) for n, (r, s) in best.items()), key=lambda x: -x[1])[:12]
    st["nets"] = [n for n, _r, _s in scan]


def _start_ap():
    """The setup hotspot, its web page on :80 and its DNS on :53. Without sockets (the emulator)
    the QR still shows; only the phone's page is missing."""
    global ap, web, dns, ap_ssid, ap_pass
    mac = sta.config("mac") or b"\0\0"
    ap_ssid = "%s-%02X%02X" % (NAME, mac[-2], mac[-1])
    ap_pass = _rand(8)
    ap = network.WLAN(network.AP_IF)
    try:
        ap.config(ssid=ap_ssid, key=ap_pass)
        ap.active(True)
    except Exception as e:
        print("wifisetup: hotspot:", e)
    try:
        import socket
        a = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
        web = socket.socket()
        web.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        web.bind(a)
        web.listen(2)
        web.setblocking(False)
        dns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns.bind(socket.getaddrinfo("0.0.0.0", 53)[0][-1])
        dns.setblocking(False)
    except Exception as e:
        print("wifisetup: no setup page:", e)
        web = dns = None
    print("wifisetup: hotspot %s, password %s, page http://%s/" % (ap_ssid, ap_pass, AP_IP))


def _stop_ap():
    for s in (web, dns):
        try:
            s.close()
        except Exception:
            pass
    try:
        ap.active(False)
    except Exception:
        pass


def _serve():
    """At most one DNS answer and one web request per call; neither blocks while nothing waits."""
    global qr_mode, _dirty
    if dns:
        try:
            q, addr = dns.recvfrom(512)
            r = wificfg.dns_reply(q, bytes(int(x) for x in AP_IP.split(".")))
            if r:
                dns.sendto(r, addr)
        except OSError:
            pass
    if web:
        try:
            conn, _addr = web.accept()
        except OSError:
            return
        try:
            conn.settimeout(3)
            raw = b""
            while b"\r\n\r\n" not in raw and len(raw) < 4096:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                raw += chunk
            req = wificfg.parse_request(raw)
            if req:
                method, path, headers, body = req
                want = wificfg.body_length(headers)
                while len(body) < want:
                    chunk = conn.recv(want - len(body))
                    if not chunk:
                        break
                    body += chunk
                status, ctype, page = wificfg.handle(method, path, body, st)
                conn.sendall(wificfg.response(status, ctype, page))
                if qr_mode == "join":
                    qr_mode, _dirty = "url", True       # a phone is on the hotspot
        except OSError as e:
            print("wifisetup: page:", e)
        finally:
            conn.close()


def _phone_on():
    try:
        n = ap.status("stations")
        return isinstance(n, (list, tuple)) and len(n) > 0
    except Exception:
        return False


def join(ssid, pw, origin):
    """Start joining (the hotspot stays up) and show the joining screen; _poll_join finishes it."""
    global view, _t_join, _origin, _dirty
    st.update(state="joining", ssid=ssid, msg="", pending=None)
    st["pw"] = pw
    _origin = origin
    view, _t_join, _dirty = "join", time.ticks_ms(), True
    try:
        sta.disconnect()
    except Exception:
        pass
    try:
        sta.connect(ssid, pw) if pw else sta.connect(ssid)
    except Exception as e:
        _failed("couldn't start: %s" % e)


def _failed(why):
    global view, _dirty
    st.update(state="failed", msg="%s: %s" % (st["ssid"], why))
    st.pop("pw", None)
    try:
        sta.disconnect()
    except Exception:
        pass
    view, _dirty = _origin, True
    if view == "kbd" and kb:
        kb.note = why


def _poll_join():
    global view, _t_done, _dirty
    s = sta.status()
    waited = time.ticks_diff(time.ticks_ms(), _t_join)
    if sta.isconnected():
        wificfg.save(st["ssid"], st.pop("pw", ""))
        st["state"] = "ok"
        view, _t_done, _dirty = "done", time.ticks_ms(), True
        print("wifisetup: joined %s, saved" % st["ssid"])
    elif s == getattr(network, "STAT_WRONG_PASSWORD", -3) and waited > 1500:
        _failed("wrong password")
    elif s == getattr(network, "STAT_NO_AP_FOUND", -2) and waited > 1500:
        _failed("network not found")
    elif s == getattr(network, "STAT_CONNECT_FAIL", -1) and waited > 1500:
        _failed("couldn't connect")
    elif waited > JOIN_S * 1000:
        _failed("no answer in %d s" % JOIN_S)


# ------------------------------------------------------------------------------------- keyboard

PAGES = (("abcdefghij", "klmnopqrst", "uvwxyz-_.@", "1234567890"),
         ("ABCDEFGHIJ", "KLMNOPQRST", "UVWXYZ-_.@", "1234567890"),
         ("!?#$%&*+=/", "()[]{}<>:;", "'\"`~^|\\,.@", "1234567890"))
SPECIAL = 5             # the last row: case, symbols, space, delete, OK, each two keys wide


class Keyboard:
    """Text entry for both inputs. Joystick: up/down/left/right move on the grid. Knob: "down"
    (clockwise) and "up" step through every key in reading order, wrapping at the ends."""

    def __init__(self, title, what, text="", limit=63):
        self.title, self.what, self.text, self.limit = title, what, text, limit
        self.page, self.r, self.c = 0, 0, 0
        self.note = ""

    def width(self, r):
        return SPECIAL if r == 4 else 10

    def move(self, k):
        r, c = self.r, self.c
        if L.KNOB:
            step = 1 if k == "down" else -1
            c += step
            if c >= self.width(r):
                r, c = (r + 1) % 5, 0
            elif c < 0:
                r = (r - 1) % 5
                c = self.width(r) - 1
        elif k in ("left", "right"):
            c = (c + (1 if k == "right" else -1)) % self.width(r)
        else:
            nr = (r + (1 if k == "down" else -1)) % 5
            if nr == 4:
                c = c // 2
            elif r == 4:
                c = c * 2
            r = nr
        self.r, self.c = r, c

    def label(self, i):
        return (("ABC" if self.page == 0 else "abc"), ("#+=" if self.page != 2 else "abc"),
                "space" if not L.SMALL else "spc", "del", "OK")[i]

    def type(self):
        """The key under the cursor: True when OK was pressed."""
        if self.r < 4:
            if len(self.text) < self.limit:
                self.text += PAGES[self.page][self.r][self.c]
        elif self.c == 0:
            self.page = 1 if self.page == 0 else 0
        elif self.c == 1:
            self.page = 2 if self.page != 2 else 0
        elif self.c == 2:
            if len(self.text) < self.limit:
                self.text += " "
        elif self.c == 3:
            self.text = self.text[:-1]
        else:
            return True
        self.note = ""
        return False


# ------------------------------------------------------------------------------------- keys

def _list_items():
    items = [("net", n, sec) for n, _r, sec in scan]
    items += [("other", "Other network…", False), ("rescan", "Scan again", False), ("qr", "Use a phone instead", False)]
    if can_cancel:
        items.append(("cancel", "Keep the saved Wi-Fi", False))
    return items


def _key(k):
    global view, sel, kb, _dirty, qr_mode
    ok = k in ("A", "press")
    back = k == "Y"
    _dirty = True
    if view == "qr":
        if ok:
            view, sel = "list", 0
        elif k == "X" and can_cancel:
            _restart()
        elif k == "B":
            qr_mode = "url" if qr_mode == "join" else "join"
    elif view == "list":
        items = _list_items()
        if k in ("down", "right"):
            sel = (sel + 1) % len(items)
        elif k in ("up", "left"):
            sel = (sel - 1) % len(items)
        elif back:
            view = "qr"
        elif ok:
            what, name, sec = items[sel]
            if what == "net" and sec:
                kb = Keyboard("Password for " + name, "pass")
                kb.ssid = name
                view = "kbd"
            elif what == "net":
                join(name, "", "list")
            elif what == "other":
                kb = Keyboard("Network name", "ssid", limit=32)
                view = "kbd"
            elif what == "rescan":
                _draw_busy("Looking for networks…")
                _scan()
                sel = 0
            elif what == "qr":
                view = "qr"
            else:
                _restart()
    elif view == "kbd":
        if k in ("up", "down", "left", "right"):
            kb.move(k)
        elif k == "B":
            kb.text = kb.text[:-1]
        elif back:
            view = "list"
        elif ok:
            if kb.r == 4 and kb.c == 3 and not kb.text:
                view = "list"           # del on an empty field: back (the knob has no Y)
            elif kb.type():
                _submit()


def _submit():
    global kb, view
    if kb.what == "ssid":
        name = kb.text
        why = wificfg.check(name, "")
        if why:
            kb.note = why
            return
        kb = Keyboard("Password for " + name, "pass")
        kb.ssid = name
        kb.note = "Leave it empty for an open network"
        return
    why = wificfg.check(kb.ssid, kb.text)
    if why:
        kb.note = why
        return
    join(kb.ssid, kb.text, "kbd")


def _restart():
    _stop_ap()
    import machine
    machine.reset()


# ------------------------------------------------------------------------------------- drawing

BG = T.RGB["bg"]
INK, DIM, ACC = (238, 240, 255), (136, 144, 168), T.RGB["config"]
BAD, GOOD = (255, 110, 100), (60, 220, 130)
BIG = not L.SMALL


def _f():
    import fonts
    return fonts


def tx(s, x, y, font, fg, bg=BG):
    if BIG:
        return _f().text(_d, s, x, y, font, fg, bg)
    s = s.replace(ELL, "")              # framebuf's 8 px font has no ellipsis; fit() adds "~" instead
    _d.text(s, x, y, L.color(*fg))
    return x + 8 * len(s)


def tw(s, font):
    return _f().width(s, font) if BIG else 8 * len(s)


def th(font):
    return _f().height(font) if BIG else 10


def ctx(s, y, font, fg, bg=BG):
    tx(s, (L.W - tw(s, font)) // 2, y, font, fg, bg)


ELL = "…"


def fit(s, w, font):
    """s cut with an ellipsis to w pixels."""
    e = ELL if BIG else "~"
    if tw(s, font) <= w:
        return s
    while s and tw(s + e, font) > w:
        s = s[:-1]
    return s + e


def hint():
    return ("turn to pick, press to choose" if L.KNOB else "A choose · Y back")


_qrc = (None, 0, None)


def _enc(text):
    """qrcode.encode, once per text: it scores all eight masks, too slow for every band of a frame."""
    global _qrc
    if _qrc[0] != text:
        import qrcode
        _qrc = (text,) + qrcode.encode(text)
    return _qrc[1], _qrc[2]


def _qr(text, x0, y0, size):
    n, rows = _enc(text)
    q = 2 * size
    box = n * size + 2 * q
    _d.fill_rect(x0, y0, box, box, L.WHITE)
    for r in range(n):
        bits, c = rows[r], 0
        while c < n:                    # one rectangle per run of dark modules
            if bits >> c & 1:
                e = c
                while e < n and bits >> e & 1:
                    e += 1
                _d.fill_rect(x0 + q + c * size, y0 + q + r * size, (e - c) * size, size, L.BLACK)
                c = e
            else:
                c += 1
    return box


def _qr_size(text, room):
    return max(1, room // (_enc(text)[0] + 4))


def _draw():
    _d.fill(L.color(*BG))
    {"qr": _draw_qr, "list": _draw_list, "kbd": _draw_kbd, "join": _draw_join, "done": _draw_done}[view]()
    _d.show()


def _title(s, color=INK):
    """The top line; an error goes there too, a size smaller so that it fits."""
    f = "bold18" if color != BAD else "bold14"
    ctx(fit(s, L.W - 8, f), (4 if f == "bold18" else 7) if BIG else 2, f, color)


def _draw_qr():
    W, H = L.W, L.H
    url = qr_mode == "url"
    text = ("http://%s/" % AP_IP) if url else wificfg.qr_join(ap_ssid, ap_pass)
    if not BIG:
        size = _qr_size(text, H - 4)
        x = _qr(text, 1, 2, size) + 3       # 7 characters of the 8 px font fit beside it
        for i, s in enumerate(["Open", "the page", "on the", "phone"] if url else ["Scan me", "to set", "up", "Wi-Fi"]):
            tx(s, x, 4 + i * 11, "", INK)
        tx("press", x, H - 26, "", DIM)
        tx("to type", x, H - 15, "", DIM)
        return
    msg = st.get("msg")
    _title(msg if msg else ("Open the page on your phone" if url else "Scan to set up Wi-Fi"), BAD if msg else INK)
    top = 4 + th("bold18") + 4
    foot = 3 * (th("sans12") + 2) + 4
    size = _qr_size(text, H - top - foot)
    y = top + _qr(text, (W - _box(text, size)) // 2, top, size) + 4
    if url:
        ctx("If no page opened, go to", y, "sans12", DIM)
        ctx("http://%s" % AP_IP, y + 16, "bold14", INK)
    else:
        ctx("Point your phone's camera here, or join", y, "sans12", DIM)
        x = (W - tw(ap_ssid + "  " + ap_pass, "bold14")) // 2
        x = tx(ap_ssid + "  ", x, y + 16, "bold14", INK)
        tx(ap_pass, x, y + 16, "bold14", T.RGB["learn"])
    ctx(("press: set up on this screen" if L.KNOB else "A: set up on this screen") +
        ("" if L.KNOB or not can_cancel else " · X: cancel"), H - th("sans12") - 2, "sans12", DIM)


def _box(text, size):
    return (_enc(text)[0] + 4) * size


def _draw_list():
    W, H = L.W, L.H
    msg = st.get("msg")
    _title(msg if msg else "Choose your Wi-Fi", BAD if msg else INK)
    items = _list_items()
    row = 26 if BIG else 12
    top = (4 + th("bold18") + 6) if BIG else 14
    n = (H - top - (th("sans12") + 4 if BIG else 0)) // row
    first = min(max(0, sel - n // 2), max(0, len(items) - n))
    for i in range(first, min(len(items), first + n)):
        what, name, sec = items[i]
        y = top + (i - first) * row
        on = i == sel
        bg = ACC if on else BG
        if on:
            _d.fill_rect(2, y, W - 4, row - 2, L.color(*ACC))
        fg = INK if what == "net" or on else DIM
        pad = (row - 2 - th("sans14")) // 2 if BIG else 1
        tx(fit(name, W - (40 if BIG else 30), "sans14"), 10 if BIG else 4, y + pad, "sans14", fg, bg)
        if what == "net":
            rssi = scan[i][1]
            bars = 3 if rssi > -60 else 2 if rssi > -75 else 1
            for b in range(3):
                h = 3 + b * 3
                _d.fill_rect(W - 22 + b * 5, y + row - 6 - h, 3, h, L.color(*(fg if b < bars else (60, 70, 100))))
            if sec and BIG:
                _d.rect(W - 36, y + row // 2 - 2, 8, 6, L.color(*fg))     # a padlock: body
                _d.rect(W - 34, y + row // 2 - 6, 4, 5, L.color(*fg))     # and shackle
    if BIG:
        ctx(hint(), H - th("sans12") - 2, "sans12", DIM)


def _draw_kbd():
    W, H = L.W, L.H
    tx(fit(kb.title, W - 8, "sans14"), 4, 2 if BIG else 0, "sans14", DIM)
    fy = (4 + th("sans14")) if BIG else 10
    fh = (th("mono13") + 8) if BIG else 12
    _d.fill_rect(2, fy, W - 4, fh, L.color(20, 30, 58))
    shown = kb.text
    while shown and tw(shown + "_", "mono13") > W - 14:
        shown = shown[1:]               # the end of a long password, where the typing is
    x = tx(shown, 7, fy + (4 if BIG else 2), "mono13", INK, (20, 30, 58))
    _d.fill_rect(x + 1, fy + 3, 2, fh - 6, L.color(*ACC))
    gy = fy + fh + (4 if BIG else 2)
    note_h = (th("sans12") + 2) if BIG else 0
    rh = (H - gy - note_h) // 5
    cw = W // 10
    x0 = (W - cw * 10) // 2
    rows = PAGES[kb.page]
    for r in range(5):
        for c in range(kb.width(r)):
            wide = 2 if r == 4 else 1
            x, y, w = x0 + c * cw * wide, gy + r * rh, cw * wide
            on = r == kb.r and c == kb.c
            bg = ACC if on else ((26, 36, 66) if r == 4 else BG)
            if on or r == 4:
                _d.fill_rect(x + 1, y + 1, w - 2, rh - 2, L.color(*bg))
            s = rows[r][c] if r < 4 else kb.label(c)
            font = "bold18" if r < 4 else "sans12"
            tx(s, x + (w - tw(s, font)) // 2, y + (rh - th(font)) // 2 + (1 if BIG else 0), font, INK if r < 4 or on else DIM, bg)
    if BIG:
        if kb.note:
            ctx(fit(kb.note, W - 8, "sans12"), H - th("sans12") - 1, "sans12", BAD)
        else:
            ctx("turn to move, press to type" if L.KNOB else "A type · B delete · Y back", H - th("sans12") - 1, "sans12", DIM)


def _draw_join():
    W, H = L.W, L.H
    _title("Joining")
    ctx(fit(st["ssid"], W - 8, "bold18"), H // 2 - 30, "bold18", INK)
    for i in range(5):
        on = (_frame // 3) % 5 == i
        _d.fill_rect(W // 2 - 44 + i * 18, H // 2 + 4, 10, 10, L.color(*(ACC if on else (40, 50, 80))))
    if BIG:
        ctx("This takes up to %d seconds" % JOIN_S, H // 2 + 30, "sans12", DIM)


def _draw_done():
    W, H = L.W, L.H
    _title("Connected", GOOD)
    ctx(fit(st["ssid"], W - 8, "bold18"), H // 2 - 20, "bold18", INK)
    ctx("Saved. Restarting…", H // 2 + 14, "sans14" if BIG else "", DIM)


def _draw_busy(s):
    def draw():
        _d.fill(L.color(*BG))
        ctx(s, L.H // 2 - 8, "sans14", INK)
        _d.show()
    _d.frames(draw)


# ------------------------------------------------------------------------------------- loop

def _setup():
    global sta, _d, _keys, can_cancel, view
    import net
    import splash
    can_cancel = bool(net.networks())
    _d = splash.begin()
    _keys = L.Keys()
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.disconnect()
    except Exception:
        pass
    _draw_busy("Looking for networks…")
    _scan()
    _start_ap()
    view = "qr"


def step():
    """One pass: keys, the hotspot's page and DNS, the join in progress, the screen."""
    global _busy, _dirty, _frame, qr_mode
    if _busy:
        return
    _busy = True
    try:
        _frame += 1
        for k in _keys.pressed():
            _key(k)
        _serve()
        if st.get("pending") and view != "join":
            ssid, pw = st["pending"]
            join(ssid, pw, "qr")
        if view == "join":
            _poll_join()
            _dirty = _dirty or _frame % 3 == 0
        if view == "qr" and qr_mode == "join" and _frame % 40 == 0 and _phone_on():
            qr_mode, _dirty = "url", True
        if view == "done" and time.ticks_diff(time.ticks_ms(), _t_done) > 2500:
            _restart()
        if _dirty:
            _dirty = False
            _d.frames(_draw)
    finally:
        _busy = False


def run():
    """From boot.py. Never returns: a saved network (or a cancel) restarts the board."""
    _setup()
    while True:
        step()
        time.sleep_ms(30)


def start():
    """The same on a timer, so the emulator's REPL stays free (tools/emu exec, --key)."""
    global _timer
    _setup()
    _timer = board.timer("setup", 40, lambda t: step())


def stop():
    if _timer:
        _timer.deinit()
    _stop_ap()
