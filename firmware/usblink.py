# The USB link: the few things a computer may ask a running console over its USB serial port, the
# app's Device page in Chrome (Web Serial) or tools/fw. docs/USB-LINK.md has the protocol.
#
# One JSON object a line each way. Every request carries an "id"; every answer starts {"pq":1,
# and carries the same id. Anything else the console prints (logs, tracebacks) is not an answer,
# and hosts skip it.
#   hello, status       read what the console already knows: no chip call, no password, no API key
#   wifi, safes, maint  asks: each is drawn on the console's screen, page by page, and happens only
#                       when the person there holds D2 (Sign elsewhere); D0 refuses with one press
#   cancel              takes an open ask off the screen
# The link never signs, never reads a key and never touches the chip. It writes wifi.json, safes.json
# or maint, each only from an ask the person accepted, and nothing else.
#
# run() owns stdin in a loop that never returns, with Ctrl-C off: while the console runs, the
# MicroPython REPL is out of reach over USB. It is there only in maintenance (the maintenance key
# held at power-up, or the maint file, which the maint ask writes).
import sys
import json
import time

PROTO = 1
MAX_LINE = 2048     # a request longer than this is not ours
ASK_S = 120         # an ask nobody answered on the device is refused after this long
MAX_NAME = 24       # a Safe's name, as policy.safes keeps it

host = None         # the module that answers: quorum (the console), wifisetup (Wi-Fi setup), or None
mode = "stopped"    # what host is: "console", "setup" or "stopped" (the console did not start)
open_ask = None     # {"id", "kind", "t"}: the ask on the console's screen
_buf = bytearray()
_poll = None
_in = None


def send(d):
    """One answer, written in one call so that nothing printed meanwhile lands inside it."""
    s = json.dumps(d)
    sys.stdout.write('{"pq":%d%s%s\n' % (PROTO, "," if len(s) > 2 else "", s[1:]))


def answer(mid, ok, why="", **more):
    d = {"id": mid, "ok": ok}
    if why:
        d["why"] = why
    d.update(more)
    send(d)


# ----------------------------------------------------------------------------- what may be asked
def check_wifi(m):
    """(item, why) for a wifi ask: {"ssid", "pass"}, with wificfg's own rules."""
    import wificfg
    ssid, pw = m.get("ssid"), m.get("pass", "")
    if not isinstance(ssid, str) or not isinstance(pw, str):
        return None, "ssid and pass are text"
    why = wificfg.check(ssid, pw)
    return (None, why) if why else ({"ssid": ssid, "pass": pw}, "")


def check_safes(m):
    """(item, why) for a safes ask: 1 to policy.MAX_SAFES of {"chainId", "address", "name"}, each
    on a chain the console has a service for. Nothing else in an entry: a Safe's own service ("url")
    comes only from secrets.py."""
    import policy
    import quorum_cfg
    given = m.get("safes")
    if not isinstance(given, list) or not given:
        return None, "safes is a list of one or more"
    if len(given) > policy.MAX_SAFES:
        return None, "at most %d Safes" % policy.MAX_SAFES
    services = quorum_cfg.CFG.get("services", {})
    for s in given:
        if not isinstance(s, dict) or any(k not in ("chainId", "address", "name") for k in s):
            return None, "each Safe is chainId, address and name, nothing else"
        if not isinstance(s.get("chainId"), int) or str(s["chainId"]) not in services:
            return None, "a chain the console has no service for"
        n = s.get("name", "Safe")
        if not isinstance(n, str) or len(n) > MAX_NAME or any(not " " <= ch <= "~" for ch in n):
            return None, "a name is up to %d plain characters" % MAX_NAME
    out, why = policy.safes(given, None)
    if why or len(out) != len(given):
        return None, why or "the same Safe twice"
    return out, ""


CHECKS = {"wifi": check_wifi, "safes": check_safes, "maint": lambda m: ({}, "")}


def hello():
    import image
    import board
    return {"proto": PROTO, "mode": mode, "board": board.BOARD, "image": image.IMAGE, "version": image.VERSION,
            "release": image.RELEASE, "build": image.BUILD}


# ----------------------------------------------------------------------------- requests
def handle(line):
    """One request line."""
    global open_ask
    try:
        m = json.loads(line)
    except ValueError:
        return send({"ok": False, "why": "not JSON"})
    if not isinstance(m, dict):
        return send({"ok": False, "why": "not an object"})
    mid, op = m.get("id"), m.get("op")
    if not isinstance(mid, int):
        return send({"ok": False, "why": "no id"})
    if op == "hello":
        return answer(mid, True, **hello())
    if op == "status":
        return answer(mid, True, **(host.link_status() if host else {"mode": mode}))
    if op == "cancel":
        if open_ask and host:
            host.link_cancel()
        return answer(mid, True)
    if op not in CHECKS:
        return answer(mid, False, "unknown op")
    if not host or op not in getattr(host, "LINK_ASKS", ()):
        return answer(mid, False, "not here: the console is in %s mode" % mode)
    if open_ask:
        return answer(mid, False, "busy: another ask is on the screen")
    item, why = CHECKS[op](m)
    if why:
        return answer(mid, False, why)
    why = host.link_ask(op, item)
    if why:
        return answer(mid, False, why)
    open_ask = {"id": mid, "kind": op, "t": time.ticks_ms()}


def done(ok, why=""):
    """The host's word on the open ask: accepted (and done) or refused."""
    global open_ask
    a, open_ask = open_ask, None
    if a:
        answer(a["id"], ok, why, kind=a["kind"])


def expired():
    """True once the open ask has waited ASK_S on the screen."""
    return bool(open_ask) and time.ticks_diff(time.ticks_ms(), open_ask["t"]) > ASK_S * 1000


# ----------------------------------------------------------------------------- the port
def _setup():
    global _poll, _in
    import select
    _in = getattr(sys.stdin, "buffer", sys.stdin)
    _poll = select.poll()
    _poll.register(sys.stdin, select.POLLIN)


def poll():
    """Whatever the host sent so far, a line at a time. Never blocks."""
    global _buf
    if _poll is None:
        _setup()
    for _ in range(MAX_LINE + 2):
        if not _poll.poll(0):
            return
        b = _in.read(1)
        if not b:
            return
        ch = b[0] if isinstance(b, (bytes, bytearray)) else ord(b)
        if ch == 10:
            line, _buf = bytes(_buf), bytearray()
            if line.strip():
                if line[:1] == b"{":
                    try:
                        handle(line.decode())
                    except Exception as e:     # a request must never stop the loop
                        sys.print_exception(e)
                        send({"ok": False, "why": "failed: %r" % e})
            return
        if ch == 13:
            continue
        if len(_buf) >= MAX_LINE:
            _buf = bytearray()
            send({"ok": False, "why": "line too long"})
            while _poll.poll(0) and _in.read(1) not in (b"\n", "\n", b""):
                pass                    # the rest of that line goes too
            return
        _buf.append(ch)


def keep_ctrl_c_out():
    """Ctrl-C (0x03) is just a byte from here on: nothing a host sends stops the running code."""
    try:
        import micropython
        micropython.kbd_intr(-1)
    except (ImportError, AttributeError):
        pass


def run(h=None, what="console"):
    """main.py's last line: the console runs on its timer, and this loop holds stdin for good, so
    the REPL never gets it. It never returns, whatever a request does."""
    global host, mode
    host, mode = h, what if h else "stopped"
    keep_ctrl_c_out()
    while True:
        try:
            poll()
            time.sleep_ms(20)
        except BaseException as e:      # noqa: nothing ends this loop, a KeyboardInterrupt included
            try:
                sys.print_exception(e)
            except BaseException:
                pass
