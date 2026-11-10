# The link: console-rp's way out. UART1 runs through the CH343P to the USB-C and the computer, which
# relays each request to one of the pinned services (quorum_cfg.py "services"), adds its own API key,
# and sends back what the service said. docs/USB-LINK.md, "The relay"; hardware/console-usb/README.md,
# "The link".
#
# One JSON object a line each way, 8N1 at 460800, no flow control (the CH343P's RTS and CTS go nowhere):
#   console -> computer  {"t":"req","id":7,"m":"GET","url":"<a pinned base>/api/..."}   ("body", the JSON
#                        text to send, on a POST)
#                        {"t":"log","m":"..."}     each line of log.txt as it is written; nothing comes back
#                        {"pq":1,...}              usblink's answers
#   computer -> console  {"t":"res","id":7,"status":200,"body":"..."}   status 0 and "err": the relay failed
#                        {"t":"hi"}                a relay is there; it says so every few seconds
#                        {"id":...,"op":...}       usblink's requests
# Nothing here names the chip, a digest or a signature, and nothing here writes a file. Nothing that
# comes back is trusted: it is what Safe's service would have said, and quorum.py checks it as it
# checks the service. A line that isn't one of these is dropped and counted.
#
# One reader and one writer: quorum's tick while the console runs (pump() as NET.poll_accept, and
# request() with the tick's timer stopped), else whatever loop has the board (usblink.run). Every
# line out goes through one queue, so a log can't land inside an answer.
# Measured on the bench (hardware/console-rp/bench/HORSEPOWER.md, "The link on UART1"): reading keeps up
# at 460800 with lines of 40 KB; what arrives while the board is busy waits in the 16 KB rxbuf; a
# line that arrives while the board writes flash is lost. So request() writes no file while it waits,
# and a computer whose ask gets no answer asks again.
import json
import time
import board
import quorum_cfg

KIND = "link"
BAUD = 460800
RXBUF = 16 * 1024           # an ask that arrives while the board hashes waits here (32766 at most on rp2)
TXBUF = 8 * 1024            # a whole answer fits, so writing it never waits
MAX_LINE = 24 * 1024        # the longest line read: a queue of 10 is about 13 KB, the relay sends at most this (70 KB free, HORSEPOWER.md)
MAX_OP = 2048               # an usblink request (usblink.MAX_LINE)
MAX_URL = 400
TIMEOUT_MS = 15000          # the relay gives up on the service at 12 s and answers status 0 first
SEEN_MS = 15000             # a relay that has said nothing for this long isn't there
OPS = 4                     # usblink requests waiting to be handled
OUT = 8                     # lines waiting to go out, logs apart
LOGS, LOG_LEN = 20, 300     # log lines waiting to go out: past that the oldest goes

led = None
up = False
boot_at = begun_at = 0      # as net.py's, for quorum's "boot ms" line
_u = None
_line = _mv = None
_n = 0                      # bytes of the current line so far
_skip = False               # dropping the rest of a line that was too long
_id = 0
_want = None                # the id request() waits for
_got = None                 # its answer, once here
_seen = None                # ticks_ms of the last good line from the computer
_ops, _out, _logs = [], [], []
_stats = {"in": 0, "out": 0, "garbage": 0, "overlong": 0, "unsolicited": 0, "wrong_id": 0, "dup": 0, "timeouts": 0,
          "requests": 0, "failed": 0, "ms": 0, "dropped_logs": 0, "dropped_ops": 0}


class LinkError(Exception):
    pass


class Response:
    """What txservice reads from vhttp's answers: status_code, content, close()."""

    def __init__(self, status, body):
        self.status_code, self.content = status, body

    def close(self):
        self.content = None


def start(port=None):
    """UART1 (board.LINK) and the line buffer, at boot while the heap is whole. port: a stand-in for
    the UART (any(), readinto(buf), write(bytes)), for the emulator and the tests."""
    global _u, _line, _mv, led
    from machine import Pin
    led = Pin(board.LED, Pin.OUT)
    if port is None:
        from machine import UART
        uid, tx, rx = board.LINK
        port = UART(uid, BAUD, tx=Pin(tx), rx=Pin(rx), rxbuf=RXBUF, txbuf=TXBUF, timeout=0)
    _u = port
    if _line is None:
        _line = bytearray(MAX_LINE)
        _mv = memoryview(_line)


# ----------------------------------------------------------------------------- the pin
def bases():
    """The services the console may ask through the computer: quorum_cfg's. A development load (no
    build.py: image.PRODUCTION off) adds secrets.QUORUM_URL, the laptop's tools/mock-tx-service for
    the bench soak. A production image never does."""
    out = [b.rstrip("/") for b in quorum_cfg.CFG.get("services", {}).values()]
    import image
    if not image.PRODUCTION:
        try:
            import secrets
            if getattr(secrets, "QUORUM_URL", ""):
                out.append(secrets.QUORUM_URL.rstrip("/"))
        except ImportError:
            pass
    return out


def pinned(url):
    """Whether url is a path under one of the pinned services, in plain ASCII: no spaces, no ".."
    or "@" or "#" or "\\" that a relay might read as something else."""
    if not isinstance(url, str) or len(url) > MAX_URL:
        return False
    if any(not 33 <= ord(ch) < 127 for ch in url):
        return False
    if ".." in url or "@" in url or "#" in url or "\\" in url:
        return False
    return any(url.startswith(b + "/") for b in bases())


# ----------------------------------------------------------------------------- in
def _handle(mv):
    """One line from the computer, a memoryview good only for this call."""
    global _seen, _got
    n = len(mv)
    if n and mv[n - 1] == 13:
        mv, n = mv[:n - 1], n - 1
    if not n:
        return
    if mv[0] != 0x7B:                      # "{": logs or noise, not ours
        _stats["garbage"] += 1
        return
    try:
        m = json.loads(mv)
    except Exception:
        _stats["garbage"] += 1
        return
    if not isinstance(m, dict):
        _stats["garbage"] += 1
        return
    t = m.get("t")
    if t == "res":
        mid = m.get("id")
        if _want is None:
            _stats["unsolicited"] += 1
        elif mid != _want:
            _stats["wrong_id"] += 1         # a late answer to one that timed out, or a made-up one
        elif _got is not None:
            _stats["dup"] += 1              # the first answer stands
        else:
            _got = m
    elif t == "hi":
        pass
    elif "op" in m and "id" in m and "t" not in m:
        if n > MAX_OP:
            _stats["overlong"] += 1
            return
        if len(_ops) >= OPS:
            _stats["dropped_ops"] += 1
            return
        _ops.append(bytes(mv).decode())
    else:
        _stats["garbage"] += 1
        return
    _stats["in"] += 1
    _seen = time.ticks_ms()


def _nl(s0):
    """Where the next newline is in the line so far, from s0; -1 for none. Copies nothing: a copy
    of each piece (up to 2 KB) to look in found no room in a day-old heap (board #2, 2026-11-10)."""
    if _FIND:
        return _line.find(b"\n", s0, _n)
    for i in range(s0, _n):
        if _line[i] == 10:
            return i
    return -1


_FIND = hasattr(bytearray, "find")


def _take():
    """Whatever has come, a whole line at a time. Never blocks."""
    global _n, _skip
    while _u.any():
        if _n >= MAX_LINE:                 # too long: drop it, and the rest of it up to its newline
            _stats["overlong"] += 1
            _n, _skip = 0, True
        k = _u.readinto(_mv[_n:min(MAX_LINE, _n + 2048)]) or 0
        if not k:
            break
        s0 = _n
        _n += k
        while True:
            end = _nl(s0)
            if end < 0:
                break
            if _skip:
                _skip = False
            else:
                _handle(_mv[:end])
            rest = _n - end - 1
            if rest:
                _line[0:rest] = bytes(_mv[end + 1:_n])
            _n, s0 = rest, 0


# ----------------------------------------------------------------------------- out
def _write(s):
    _u.write(s.encode() + b"\n" if isinstance(s, str) else s + b"\n")
    _stats["out"] += 1


def _flush():
    while _out:
        _write(_out.pop(0))
    while _logs:
        _write(_logs.pop(0))


def send_line(s):
    """usblink's answers: out at the next pump, whole."""
    if len(_out) >= OUT:
        _out.pop(0)
    _out.append(s)


def log(msg):
    """qlog.TAP: a copy of each log line for the computer. Never blocks, never fails."""
    try:
        if len(_logs) >= LOGS:
            _logs.pop(0)
            _stats["dropped_logs"] += 1
        _logs.append(json.dumps({"t": "log", "m": str(msg)[:LOG_LEN]}))
    except Exception:
        pass


def ops():
    """The usblink requests that came, oldest first."""
    while _ops:
        yield _ops.pop(0)


def pump():
    """Read what came, send what waits. The one call the running console makes each tick."""
    global up
    if _u is None:
        return
    _take()
    _flush()
    up = _seen is not None and time.ticks_diff(time.ticks_ms(), _seen) < SEEN_MS


# ----------------------------------------------------------------------------- a request
def request(method, url, body=None, timeout_ms=None):
    """One call to a pinned service through the computer. -> Response(status_code, content). Raises
    LinkError when the URL isn't pinned (nothing is sent), when no answer comes in time, or when the
    answer isn't one. Writes no file while it waits: a flash write would lose the answer."""
    global _id, _want, _got, up
    if method not in ("GET", "POST") or not pinned(url):
        raise LinkError("not a pinned service")
    timeout_ms = timeout_ms or TIMEOUT_MS
    _id += 1
    _want, _got = _id, None
    req = {"t": "req", "id": _id, "m": method, "url": url}
    if body is not None:
        req["body"] = json.dumps(body)
    _flush()
    _write(json.dumps(req))
    _stats["requests"] += 1
    try:
        import watch
        watch.extend(timeout_ms + 5000)
    except ImportError:
        pass
    t0 = time.ticks_ms()
    try:
        while _got is None:
            _take()
            if _got is not None:
                break
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                _stats["timeouts"] += 1
                up = False                  # until it says hi again: no more waits on nobody
                raise LinkError("relay: no answer")
            time.sleep_ms(2)
        m = _got
    finally:
        _want, _got = None, None
        _stats["ms"] += time.ticks_diff(time.ticks_ms(), t0)
    status, b = m.get("status"), m.get("body", "")
    if not isinstance(status, int) or not isinstance(b, str):
        _stats["failed"] += 1
        raise LinkError("relay: not an answer")
    if status == 0:
        _stats["failed"] += 1
        raise LinkError("relay: " + str(m.get("err", "failed"))[:40])
    return Response(status, b)


# ----------------------------------------------------------------------------- as quorum.NET
def short_err(e):
    """An error in the width of one status row."""
    if isinstance(e, LinkError):
        return str(e)[:23]
    return repr(e)[:23]


def ready(log_):
    """(ok, why) before a poll: a relay has said something lately."""
    pump()
    return (True, "") if up else (False, "no relay: open the app")


def status():
    """For usblink's status: the link's counts, and the heap free after a collect, for the soak's logs."""
    import gc
    gc.collect()
    d = dict(_stats)
    d["up"], d["max"], d["free"] = up, MAX_LINE, gc.mem_free()
    return {"link": d}


def poll_accept():
    pump()


def boot_join(splash, keys, knob):
    """quorum.start: a moment for a relay already running to say hi. -> ms since reset when one has."""
    t0 = time.ticks_ms()
    while not up and time.ticks_diff(time.ticks_ms(), t0) < 3000 and not keys.pressed():
        pump()
        splash.spin("wifi", "USB: waiting for the app")
        time.sleep_ms(50)
    import lcd
    splash.step("wifi", "USB: relay here" if up else "USB: no relay yet", lcd.GREEN if up else lcd.YELLOW)
    return time.ticks_ms() if up else 0
