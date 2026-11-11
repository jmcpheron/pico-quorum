#!/usr/bin/env python3
# The relay: the computer's end of console-rp's link (firmware/link.py; hardware/console-usb/README.md,
# "The link"). The console asks, one JSON line on UART1; this checks the ask, makes the HTTPS call to
# the pinned service with the API key, and sends back what the service said. Nothing it sends is
# trusted: the console checks every answer as it checks Safe's service.
#
#   python3 tools/relay/relay.py PORT [options]           the CH343P, e.g. /dev/cu.usbmodem5CF90874511
#   python3 tools/relay/relay.py --tcp HOST:PORT [options] the emulator's UART
# options:
#   --safes chain:0xADDR[:name],...   send the safes ask once (accepted on the device: D2 held)
#   --allow-base URL                  one more base, http to this computer only (tools/mock-tx-service)
#   --hostile F,F,... --rate P        do F to a share P of the answers (FAULTS, below); --seed N
#   --run DIR                         where the logs go (default hardware/console-rp/bench/runs/<when>-<serial>)
#   --status-s S                      ask the console's status every S seconds (60)
#   --quiet                           print only faults, refusals and errors
#
# What it forwards: a GET of the Safe or its queue, and the POST of a confirmation, under a base in
# firmware/quorum_cfg.py "services". Anything else gets status 0 and nothing goes out. The API key is
# SAFE_API_KEY, from the environment or .env. It goes only on requests to api.safe.global, and never
# into a log or down the link. Standard library only.
#
# Logs, one JSON object a line: relay.jsonl (each request: path, status, bytes, ms, the body's
# SHA-256, a fault and what it should do), console.jsonl (the console's log lines), status.jsonl
# (its status every --status-s).
import hashlib
import json
import os
import random
import re
import select
import socket
import struct
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BAUD = 460800
HI_S = 2.0                  # the console counts the relay gone after 15 s of nothing (link.SEEN_MS)
UPSTREAM_S = 12             # the console gives up at 15 s (link.TIMEOUT_MS): answer before that
MAX_IN = 64 * 1024          # the longest line read from the console
MAX_POST = 4096
DEFAULT_MAX = 16 * 1024     # the longest answer until hello says the console's (link.MAX_LINE)
MAX_URL = 400
ADDR = r"0x[0-9a-fA-F]{40}"
PATHS = [("GET", re.compile(r"/api/v1/safes/%s/" % ADDR)),
         ("GET", re.compile(r"/api/v2/safes/%s/multisig-transactions/\?executed=false&nonce__gte=\d{1,20}&ordering=nonce&limit=\d{1,2}(&offset=\d{1,2})?" % ADDR)),
         ("POST", re.compile(r"/api/v1/multisig-transactions/0x[0-9a-fA-F]{64}/confirmations/"))]
SIM_PATHS = [("POST", re.compile(r"/sim/device")), ("POST", re.compile(r"/sim/declined"))]   # tools/quorum's, an allowed base only
# Each fault, and what the console should do with it.
FAULTS = {
    "garbage": "dropped and counted (garbage); the answer after it used",
    "overlong": "dropped to its newline (overlong); the answer after it used",
    "unsolicited": "an answer to no request: dropped (wrong_id)",
    "wrong-id": "the answer under another id first: dropped (wrong_id), the right one used",
    "dup": "the answer twice: the first used, the second dropped (dup)",
    "late": "no answer now (the console times out); it comes before the next answer: dropped (wrong_id)",
    "truncate": "half the body: the poll fails, nothing signed",
    "stall": "no answer: the console times out, the poll fails, nothing signed",
    "forge-queue": "the first transaction's value changed, its hash kept: REFUSED on the screen",
    "nested": "a body nested 5000 deep: the poll fails, nothing signed",
    "chatter": "hi and noise around the answer: the noise dropped, the answer used",
    "big": "the queue's first transaction padded past the console's line: read a few at a time, that one refused as too big",
    "lose-post": "a confirmation dropped, never sent on: the console times out, shows Not sent, and keeps it to send again",
}
GET_ONLY = ("truncate", "stall", "late", "nested", "forge-queue", "big")
POST_ONLY = ("lose-post",)


class Refused(Exception):
    pass


# ----------------------------------------------------------------------------- the pin
def services(path=None):
    """quorum_cfg.py's "services": {chainId: base}, read as web/config.mjs reads it."""
    src = open(path or os.path.join(ROOT, "firmware", "quorum_cfg.py")).read()
    cfg = json.loads(src[src.index("{", src.index("CFG =")):])
    return {int(k): v.rstrip("/") for k, v in cfg["services"].items()}


def plain(url):
    return isinstance(url, str) and len(url) <= MAX_URL and all(33 <= ord(c) < 127 for c in url) \
        and not any(s in url for s in ("..", "@", "#", "\\"))


def check(m, bases, allowed=()):
    """A request line from the console -> (method, url, body text or None). Raises Refused. The same
    rules as link.pinned, then only the paths txservice uses."""
    if not isinstance(m, dict) or m.get("t") != "req" or not isinstance(m.get("id"), int):
        raise Refused("not a request")
    method, url, body = m.get("m"), m.get("url"), m.get("body")
    if method not in ("GET", "POST") or not plain(url):
        raise Refused("not a plain GET or POST")
    base = next((b for b in list(bases) + list(allowed) if url.startswith(b + "/")), None)
    if base is None:
        raise Refused("not a pinned service")
    rest = url[len(base):]
    paths = PATHS + (SIM_PATHS if base in allowed else [])
    if not any(meth == method and rx.fullmatch(rest) for meth, rx in paths):
        raise Refused("not a path the console uses")
    if method == "GET":
        if body is not None:
            raise Refused("a GET with a body")
        return method, url, None
    if not isinstance(body, str) or len(body) > MAX_POST:
        raise Refused("a POST body is JSON text of at most %d bytes" % MAX_POST)
    try:
        b = json.loads(body)
    except ValueError:
        raise Refused("a POST body that isn't JSON")
    if "/confirmations/" in rest and not (isinstance(b, dict) and list(b) == ["signature"] and isinstance(b["signature"], str)
                                          and re.fullmatch(r"0x[0-9a-fA-F]{2,8000}", b["signature"])):
        raise Refused("a confirmation is {\"signature\": \"0x...\"} and nothing else")
    return method, url, body


def api_key():
    """SAFE_API_KEY from the environment, else from .env at the repository's root. Never printed."""
    k = os.environ.get("SAFE_API_KEY", "")
    if not k and os.path.exists(os.path.join(ROOT, ".env")):
        for line in open(os.path.join(ROOT, ".env")):
            name, sep, v = line.strip().partition("=")
            if sep and name.strip() == "SAFE_API_KEY":
                k = v.strip().strip('"').strip("'")
    return k


def headers_for(url, key):
    """The API key goes to Safe's own service over HTTPS, nowhere else."""
    h = {"Accept": "application/json", "User-Agent": "picoquorum-relay"}
    if key and url.startswith("https://api.safe.global/"):
        h["Authorization"] = "Bearer " + key
    return h


def fetch(method, url, body, key, timeout=UPSTREAM_S):
    """The call itself. -> (status, text). Raises on no answer at all."""
    headers = headers_for(url, key)
    data = None
    if body is not None:
        data, headers["Content-Type"] = body.encode(), "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


# ----------------------------------------------------------------------------- the port
class Port:
    """The CH343P through termios (raw, 8N1, no flow control), or a TCP socket. read() never blocks."""

    def __init__(self, path=None, tcp=None):
        self.sock = self.fd = None
        if tcp:
            host, _, p = tcp.rpartition(":")
            self.sock = socket.create_connection((host or "127.0.0.1", int(p)))
            self.sock.setblocking(False)
        else:
            self.fd = open_serial(path, BAUD)

    def fileno(self):
        return self.sock.fileno() if self.sock else self.fd

    def read(self):
        try:
            return self.sock.recv(65536) if self.sock else os.read(self.fd, 65536)
        except (BlockingIOError, InterruptedError):
            return b""

    def write(self, data):
        while data:
            select.select([], [self.fileno()], [], 1.0)
            try:
                n = self.sock.send(data) if self.sock else os.write(self.fd, data)
            except (BlockingIOError, InterruptedError):
                continue
            data = data[n:]


def open_serial(path, baud):
    import fcntl
    import termios
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    iflag &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR | termios.IGNCR
               | termios.ICRNL | termios.IXON | termios.IXOFF | termios.IXANY)
    oflag &= ~termios.OPOST
    lflag &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    cflag &= ~(termios.CSIZE | termios.PARENB | termios.CSTOPB | getattr(termios, "CRTSCTS", 0))
    cflag |= termios.CS8 | termios.CREAD | termios.CLOCAL
    cc[termios.VMIN], cc[termios.VTIME] = 0, 0
    speed = getattr(termios, "B%d" % baud, None)
    if speed is not None:
        ispeed = ospeed = speed
    termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])
    if speed is None:
        if sys.platform != "darwin":
            sys.exit("termios has no B%d here" % baud)
        fcntl.ioctl(fd, 0x80045402, struct.pack("I", baud))     # IOSSIOSPEED: macOS's way to any rate
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


# ----------------------------------------------------------------------------- the relay
class Relay:
    def __init__(self, port, run_dir, bases, allowed=(), key="", hostile=(), rate=0.0, seed=None, status_s=60,
                 safes=None, quiet=False, fetcher=fetch, clock=time.time, rename=False):
        self.port, self.bases, self.allowed, self.key = port, bases, tuple(allowed), key
        self.hostile, self.rate, self.rnd = list(hostile), rate, random.Random(seed)
        self.status_s, self.safes, self.quiet, self.fetch, self.clock = status_s, safes, quiet, fetcher, clock
        self.run_dir, self.rename = run_dir, rename     # rename: <when>-relay becomes <when>-<serial> once status names it
        self.max = DEFAULT_MAX
        self.buf = b""
        self.next_id = 1000
        self.asks = {}              # id -> (op, sent at, tries)
        self.hello = self.serial = None
        self.last_hi = self.last_status = 0.0
        self.late = None            # an answer held back by the "late" fault
        self.counts = {"req": 0, "refused": 0, "faults": 0, "noise": 0, "logs": 0, "upstream_errors": 0}
        os.makedirs(run_dir, exist_ok=True)
        self.files = {n: open(os.path.join(run_dir, n + ".jsonl"), "a") for n in ("relay", "console", "status")}

    # --- logs
    def log(self, name, **rec):
        rec = dict({"at": round(self.clock(), 3)}, **rec)
        line = json.dumps(rec)
        if self.key and self.key in line:          # never, but never written either
            line = line.replace(self.key, "[key]")
        self.files[name].write(line + "\n")
        self.files[name].flush()

    def say(self, s, loud=False):
        if loud or not self.quiet:
            print(s, flush=True)

    # --- out
    def send(self, obj_or_bytes):
        b = obj_or_bytes if isinstance(obj_or_bytes, bytes) else json.dumps(obj_or_bytes).encode()
        self.port.write(b + b"\n")

    def ask(self, op, **more):
        self.next_id += 1
        self.asks[self.next_id] = (op, self.clock(), more)
        self.send(dict({"id": self.next_id, "op": op}, **more))

    def tick(self):
        """hi, and the asks that are due or got no answer (a line can be lost while the board writes flash)."""
        now = self.clock()
        if now - self.last_hi >= HI_S:
            self.send({"t": "hi"})
            self.last_hi = now
        for mid, (op, at, more) in list(self.asks.items()):
            if now - at > (130 if op == "safes" else 3):
                del self.asks[mid]
                if op != "safes":
                    self.ask(op, **more)        # ask again under a new id
                else:
                    self.say("safes: no answer from the device", True)
        pending = {op for op, _, _ in self.asks.values()}
        if self.hello is None and "hello" not in pending:
            self.ask("hello")
        elif self.hello is not None and "status" not in pending and now - self.last_status >= self.status_s:
            self.last_status = now
            self.ask("status")
        if self.hello is not None and self.safes and "safes" not in pending:
            self.say("safes: asking the device; hold D2 on it to accept", True)
            self.ask("safes", safes=self.safes)
            self.safes = None

    # --- in
    def feed(self, data):
        self.buf += data
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            self.line(line.rstrip(b"\r"))
        if len(self.buf) > MAX_IN:
            self.counts["noise"] += 1
            self.log("relay", kind="noise", why="a line over %d bytes" % MAX_IN)
            self.buf = b""

    def line(self, raw):
        if not raw.strip():
            return
        try:
            m = json.loads(raw)
        except ValueError:
            m = None
        if not isinstance(m, dict):
            self.counts["noise"] += 1
            self.log("relay", kind="noise", bytes=len(raw), head=raw[:60].decode("utf-8", "replace"))
            return
        if m.get("t") == "log":
            self.counts["logs"] += 1
            self.log("console", m=str(m.get("m", ""))[:400])
            self.say("console: " + str(m.get("m", ""))[:200])
        elif m.get("t") == "req":
            self.request(m)
        elif "pq" in m:
            self.answered(m)
        else:
            self.counts["noise"] += 1
            self.log("relay", kind="noise", head=raw[:60].decode("utf-8", "replace"))

    def answered(self, m):
        a = self.asks.pop(m.get("id"), None)
        op = a[0] if a else None
        if op == "hello":
            self.hello = m
            self.max = int((m.get("link") or {}).get("max") or DEFAULT_MAX)
            self.say("hello: %s %s on %s, %s, answers up to %d bytes" % (m.get("image"), m.get("version") or m.get("build"),
                                                                       m.get("board"), m.get("mode"), self.max), True)
            self.log("relay", kind="hello", hello=m)
        elif op == "status":
            self.log("status", status=m)
            if self.serial is None and m.get("serial"):
                self.serial = m["serial"]
                if self.rename and re.fullmatch(r"[0-9a-f]{18}", self.serial):
                    to = self.run_dir[:-len("relay")] + self.serial
                    os.rename(self.run_dir, to)     # the open logs move with it
                    self.run_dir, self.rename = to, False
                self.say("status: serial %s, state %s; logs in %s" % (self.serial, m.get("state"), self.run_dir), True)
        elif op == "safes":
            self.say("safes: %s" % ("accepted" if m.get("ok") else "refused: " + str(m.get("why"))), True)
            self.log("relay", kind="safes", answer=m)
        else:
            self.log("relay", kind="answer", answer=m)

    def request(self, m):
        self.counts["req"] += 1
        t0 = self.clock()
        mid = m.get("id")
        try:
            method, url, body = check(m, self.bases, self.allowed)
        except Refused as e:
            self.counts["refused"] += 1
            self.log("relay", kind="refused", id=mid, why=str(e), url=str(m.get("url"))[:120])
            self.say("refused #%s: %s" % (mid, e), True)
            self.send({"t": "res", "id": mid, "status": 0, "err": str(e)})
            return
        fault = None
        if self.hostile and self.rnd.random() < self.rate:
            fault = self.rnd.choice([f for f in self.hostile if f not in (POST_ONLY if method == "GET" else GET_ONLY)] or [None])
        if fault == "late" and self.late is not None:
            fault = None                # one answer held back at a time
        rec = {"kind": "req", "id": mid, "m": method, "path": url.split("/api/", 1)[-1][:160], "fault": fault}
        if fault in ("stall", "lose-post"):
            self.counts["faults"] += 1
            self.log("relay", expect=FAULTS[fault], **rec)
            self.say("fault #%s %s: %s" % (mid, fault, FAULTS[fault]), True)
            return
        up0 = self.clock()
        try:
            status, text = self.fetch(method, url, body, self.key)
        except Exception as e:
            self.counts["upstream_errors"] += 1
            err = type(e).__name__ + ": " + str(e)[:60]
            self.send({"t": "res", "id": mid, "status": 0, "err": err})
            self.log("relay", status=0, err=err, ms=int((self.clock() - t0) * 1000), **rec)
            self.say("#%s %s %s: no answer (%s)" % (mid, method, rec["path"][:60], err), True)
            return
        up_ms = int((self.clock() - up0) * 1000)
        if fault == "big" and not re.search(r"&offset=0*[1-9]", url):
            text = pad(text, self.max)
        res = {"t": "res", "id": mid, "status": status, "body": text}
        line = json.dumps(res).encode()
        if len(line) > self.max:
            res = {"t": "res", "id": mid, "status": 0, "err": "answer too big: %d bytes" % len(line)}
            line = json.dumps(res).encode()
        sha = hashlib.sha256(text.encode()).hexdigest()[:16]
        self.deliver(mid, line, res, fault)
        if fault:
            self.counts["faults"] += 1
            self.say("fault #%s %s: %s" % (mid, fault, FAULTS[fault]), True)
        self.log("relay", status=res["status"], bytes=len(line), up_ms=up_ms, ms=int((self.clock() - t0) * 1000), sha256=sha,
                 expect=FAULTS.get(fault), **rec)
        self.say("#%s %s %s -> %s, %d bytes, %d ms" % (mid, method, rec["path"][:60], res["status"], len(line), up_ms))

    def deliver(self, mid, line, res, fault):
        """The answer, with whatever the fault does to it."""
        if self.late is not None:
            self.send(self.late)                # the answer held back last time: the console has moved on
            self.late = None
        if fault == "late":
            self.late = line
            return
        if fault == "garbage":
            for junk in (b"\x00\x00\xff\xfe", b"not json at all", b"[1, 2]", b'{"t": "zzz"}'):
                self.send(junk)
        elif fault == "overlong":
            self.send(b'{"t":"hi","pad":"' + b"x" * (self.max + 1000) + b'"}')
        elif fault == "unsolicited":
            self.send({"t": "res", "id": mid + 100000, "status": 200, "body": "{}"})
        elif fault == "wrong-id":
            self.send(dict(res, id=mid + 7))
        elif fault == "chatter":
            for _ in range(5):
                self.send({"t": "hi"})
            self.send(b"chatter chatter")
        elif fault == "truncate" and "body" in res:
            line = json.dumps(dict(res, body=res["body"][:len(res["body"]) // 2])).encode()
        elif fault == "nested":
            line = json.dumps(dict(res, status=200, body="[" * 5000)).encode()
        elif fault == "forge-queue" and "body" in res:
            line = json.dumps(dict(res, body=forge(res["body"]))).encode()
        self.send(line)
        if fault == "dup":
            self.send(line)

    def run(self):
        self.say("relay: logs in %s" % self.run_dir, True)
        while True:
            r, _, _ = select.select([self.port.fileno()], [], [], 0.1)
            if r:
                data = self.port.read()
                if not data and self.port.sock:
                    self.say("relay: the other end closed", True)
                    return
                self.feed(data)
            self.tick()


def forge(text):
    """A queue answer with its first transaction's value changed and its safeTxHash kept: what a
    lying service would send."""
    try:
        q = json.loads(text)
        r = q["results"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        return text
    r["value"] = str(int(r.get("value") or 0) + 10 ** 18)
    return json.dumps(q)


def pad(text, n):
    """A queue answer with its first transaction given an origin n long (Safe's service keeps the
    proposer's note there; it isn't hashed): a transaction too long for the console to read."""
    try:
        q = json.loads(text)
        q["results"][0]["origin"] = "x" * n
    except (ValueError, KeyError, IndexError, TypeError):
        return text
    return json.dumps(q)


def parse_safes(spec, chains):
    """'basesep:0xabc...:Name,base:0xdef...' -> the safes ask's list. Chain names are the service
    URLs' last parts (eth, base, basesep), or a chainId."""
    names = {base.rsplit("/", 1)[-1]: cid for cid, base in chains.items()}
    out = []
    for part in spec.split(","):
        c, _, rest = part.partition(":")
        addr, _, name = rest.partition(":")
        cid = names.get(c) or (int(c) if c.isdigit() else None)
        if cid not in chains or not re.fullmatch(ADDR, addr):
            sys.exit("--safes: %r is not chain:0xADDRESS[:name] on a chain with a service" % part)
        out.append({"chainId": cid, "address": addr, "name": name or "Safe"})
    return out


def main(argv):
    def opt(name, default=None):
        if name in argv:
            i = argv.index(name)
            v = argv[i + 1]
            del argv[i:i + 2]
            return v
        return default
    argv = list(argv)
    tcp, run_dir, allow = opt("--tcp"), opt("--run"), opt("--allow-base")
    hostile, rate, seed = opt("--hostile", ""), float(opt("--rate", "0.05")), opt("--seed")
    status_s, safes = float(opt("--status-s", "60")), opt("--safes")
    quiet = "--quiet" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not tcp and len(args) != 1:
        sys.exit("usage: relay.py PORT | --tcp HOST:PORT [--safes ...] [--hostile F,F --rate P] (see the top of this file)")
    hostile = [f for f in hostile.split(",") if f]
    bad = [f for f in hostile if f not in FAULTS]
    if bad:
        sys.exit("--hostile: no fault %s (there are %s)" % (bad, ", ".join(FAULTS)))
    allowed = ()
    if allow:
        if not re.fullmatch(r"http://(127\.0\.0\.1|localhost)(:\d+)?(/[\w./-]*)?", allow):
            sys.exit("--allow-base is plain http to this computer only (tools/mock-tx-service)")
        allowed = (allow.rstrip("/"),)
    chains = services()
    rename = run_dir is None
    if rename:
        run_dir = os.path.join(ROOT, "hardware", "console-rp", "bench", "runs", time.strftime("%Y%m%d-%H%M%S") + "-relay")
    key = api_key()
    print("relay: %s, pinned %s%s, API key %s%s" % (tcp or args[0], ", ".join(b.rsplit("/", 1)[-1] for b in chains.values()),
                                                   " + " + allowed[0] if allowed else "", "set" if key else "none",
                                                   ", hostile %s at %.2f" % (",".join(hostile), rate) if hostile else ""), flush=True)
    port = Port(None if tcp else args[0], tcp)
    r = Relay(port, run_dir, list(chains.values()), allowed, key, hostile, rate, None if seed is None else int(seed), status_s,
              parse_safes(safes, chains) if safes else None, quiet, rename=rename)
    try:
        r.run()
    except KeyboardInterrupt:
        pass
    print("relay: %s" % json.dumps(r.counts))


if __name__ == "__main__":
    main(sys.argv[1:])
