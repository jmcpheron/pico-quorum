# The console's decisions, on real MicroPython (WebAssembly) with the virtual ATECC608: what it
# refuses, when it signs, the pin, the counter, what it sends to the service. Run by
# test-vectors/run-console.mjs; every case prints pass/FAIL and main() returns the failures.
#
# Nothing here runs a timer: each case imports a fresh quorum with its own secrets.py and build.py,
# swaps in a fake service, fake keys and a fake clock, and calls the console's own functions in
# the order its tick would.
import sys, os, json
import atecc_sim
import safe_tx
import webauthn
import p256

failed = [0]
CHAIN = 84532
SAFE = "0x5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a"
OTHER = "0x6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b"
ALICE = "0x1111111111111111111111111111111111111111"
BOB = "0x2222222222222222222222222222222222222222"
ZERO = "0x0000000000000000000000000000000000000000"
MULTISEND = "0x9641d764fc13c8b624c04430c7356c1c7c8102e2"
SERIAL = "0123e100e1e1e1e1ee"     # the virtual chip's (atecc_sim.FRESH bytes 0-3, 8-12)


def check(ok, what):
    print(("pass  " if ok else "FAIL  ") + what)
    if not ok:
        failed[0] += 1


# ----------------------------------------------------------------------------- fakes
class Resp:
    def __init__(self, code, body):
        self.status_code, self.body = code, body
        self.content = json.dumps(body).encode()

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    def close(self):
        pass


class Service:
    """Safe's transaction service, as far as the console can tell. Records every request."""

    def __init__(self):
        self.calls = []
        self.info = {}
        self.txs = []
        self.posted = []
        self.fail_pending = None
        self.safes = {}         # another Safe's address -> {"info", "txs", "down"}; the rest get info and txs

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, dict(headers or {})))
        info, txs = self.info, self.txs
        for a, o in self.safes.items():
            if a in url.lower():
                if o.get("down"):
                    raise OSError(110)
                info, txs = o["info"], o["txs"]
        if "/multisig-transactions/" in url:
            if self.fail_pending:
                e, self.fail_pending = self.fail_pending, None
                raise e
            limit = int(url.split("limit=")[1].split("&")[0]) if "limit=" in url else 10
            at = int(url.split("offset=")[1].split("&")[0]) if "offset=" in url else 0
            return Resp(200, {"count": len(txs), "results": txs[at:at + limit]})
        if "/safes/" in url:
            return Resp(200, info)
        return Resp(404, {})

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, dict(headers or {})))
        if "/confirmations/" in url:
            self.posted.append((url, json))
            return Resp(201, {})
        if url.endswith("/sim/device"):
            return Resp(200, {"owner": None})
        return Resp(404, {"detail": "not found"})

    def sim_calls(self):
        return [c for c in self.calls if "/sim/" in c[1]]


class Keys:
    def __init__(self):
        self.down = set()

    def pressed(self):
        return []

    def held(self, k):
        return k in self.down


class Clock:
    """quorum's `time`: ticks move only when a test says so."""

    def __init__(self):
        self.now = 100000

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return a - b

    def ticks_add(self, a, b):
        return a + b

    def sleep_ms(self, ms):
        self.now += ms

    def gmtime(self, *a):
        import time
        return time.gmtime(*a)

    def time(self):
        import time
        return time.time()


class Timer:
    def deinit(self):
        pass


SVC = Service()


class Relay:
    """The computer on console-rp's UART1 (link.py), as the port link.start takes: it answers each
    request from SVC as tools/relay would, and does to the next answers whatever a test puts in
    faults (each a function of the request -> the raw lines to send instead). Every line the
    console wrote is kept, as text."""

    def __init__(self):
        self.inq = b""
        self.part = b""         # a line written in pieces (link._write: head, then the rest), so far
        self.wrote = []
        self.reqs = []
        self.faults = []
        self.max = None         # the longest answer sent, as hello's link.max tells the real relays

    def any(self):
        return len(self.inq)

    def readinto(self, mv):
        n = min(len(mv), len(self.inq))
        mv[0:n] = self.inq[:n]
        self.inq = self.inq[n:]
        return n

    def raw(self, b):
        self.inq += (b.encode() if isinstance(b, str) else b) + b"\n"

    def hi(self):
        self.raw('{"t":"hi"}')

    def write(self, b, off=0, n=None):
        b = (b.encode() if isinstance(b, str) else bytes(b))[off:None if n is None else off + n]
        self.part += b
        *lines, self.part = self.part.split(b"\n")
        for line in lines:
            self.wrote.append(line.decode())
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("t") == "req":
                self.reqs.append(m)
                for out in (self.faults.pop(0)(m) if self.faults else [self.res(m)]):
                    self.raw(out)
        return len(b)

    def res(self, m, body=None, status=None):
        """The answer SVC gives to m, as the relay sends it."""
        if body is None:
            try:
                r = SVC.get(m["url"]) if m["m"] == "GET" else SVC.post(m["url"], json=json.loads(m.get("body", "null")))
            except Exception as e:
                return json.dumps({"t": "res", "id": m["id"], "status": 0, "err": repr(e)})
            status, body = r.status_code, r.content.decode()
        line = json.dumps({"t": "res", "id": m["id"], "status": 200 if status is None else status, "body": body})
        if self.max and len(line) > self.max:
            return json.dumps({"t": "res", "id": m["id"], "status": 0, "err": "answer too big: %d bytes" % len(line)})
        return line

    def sent(self, t):
        """The lines of kind t ("req", "log", or "pq" for usblink's answers) the console wrote."""
        out = []
        for w in self.wrote:
            try:
                m = json.loads(w)
            except ValueError:
                continue
            if m.get("t") == t or (t == "pq" and "pq" in m):
                out.append(m)
        return out


RELAY = [None]          # fresh's Relay on console-rp: serve() has it say hi before each poll


# ----------------------------------------------------------------------------- setup
def chip(legacy=True, lock0=True, counter=0):
    """The virtual chip: chip #1's test table with a fresh key in slot 0 (and slot 2), slot 0 locked."""
    c = atecc_sim.chip()
    atecc_sim.provision(0)
    c.keys[2] = p256.rand_scalar()
    if lock0:
        c.cfg[88] &= 0xFE
    c.counters = [counter, 0]
    c.save()
    return c


def owner_of(slot):
    import quorum_cfg
    c = atecc_sim.chip()
    x, y = p256.pubkey(c.keys[slot])
    return webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"])


def fresh(prod=True, url="https://api.safe.global/tx-service/basesep", expect="auto", extra="", safe=True, keep=False, relay=None,
          clock=None):
    """A newly imported console with this secrets.py (and build.py when prod), started, not polled.
    On console-rp its way out is link.py, on a Relay (relay, or a new one): RELAY[0]."""
    lines = ['WIFI_SSID = "emulator"', 'WIFI_PASS = ""', 'HOSTNAME = "emu"',
             'QUORUM_API_KEY = "test-key"', "ALLOW_LOCK = True", "ALLOW_GENKEY = True", "ALLOW_SOFT_KEY = True"]
    if url:
        lines.append('QUORUM_URL = "%s"' % url)
    if safe:
        lines.append('QUORUM_SAFE = {"chainId": %d, "address": "%s", "name": "Test Safe"}' % (CHAIN, SAFE))
    if expect == "auto":
        expect = {"serial": SERIAL, "slot": 0, "owner": owner_of(0), "locked": True}
    if expect:
        lines.append("QUORUM_EXPECT = " + json.dumps(expect).replace("true", "True").replace("false", "False"))
    with open("secrets.py", "w") as f:
        f.write("\n".join(lines) + "\n" + extra + "\n")
    import board
    rp = board.BOARD == "console-rp"
    if prod:
        with open("build.py", "w") as f:
            f.write('IMAGE = "%s"\nBUILD = "test"\nDATE = 1790000000\n' % ("console-rp" if rp else "console"))
    else:
        try:
            os.remove("build.py")
        except OSError:
            pass
    for m in ("secrets", "build", "image", "quorum", "signer", "net", "link", "txservice", "atecc", "qlog", "watch"):
        sys.modules.pop(m, None)
    for f in os.listdir():
        if not keep and (f.startswith("counter-") or f in ("slot.txt", "safes.json")):
            os.remove(f)
    import txservice
    txservice.requests = SVC
    import quorum as Q
    Q.start_timer = lambda: None
    Q.time = clock or Clock()
    RELAY[0] = None
    if rp:
        import link
        import qlog
        RELAY[0] = relay = relay or Relay()
        link.time = Q.time
        link.start(port=relay)
        qlog.TAP = link.log
        relay.hi()                      # a relay already running: start() hears it
        Q.NET = Q.VIA = link
    else:
        import net
        Q.NET = net
    Q.start()
    Q.keys = Keys()
    Q.timer = Timer()
    if Q.state == "boot":
        Q.state = "home"
    SVC.__init__()
    return Q


def tx(Q, nonce, to=ALICE, value=0, data="0x", op=0, safe=SAFE, conf=(), tamper=False, chain=CHAIN, hsafe=SAFE):
    """A transaction as the service serves it for `safe`, its safeTxHash over (chain, hsafe)."""
    t = {"safe": safe, "to": to, "value": str(value), "data": data if data != "0x" else None, "operation": op,
         "safeTxGas": "0", "baseGas": "0", "gasPrice": "0", "gasToken": ZERO, "refundReceiver": ZERO,
         "nonce": nonce, "confirmations": [{"owner": o} for o in conf]}
    try:
        h = safe_tx.from_service(chain, dict(t, safe=hsafe))
    except ValueError:
        h = bytes(32)
    if tamper:
        h = bytes([h[0] ^ 1]) + h[1:]
    t["safeTxHash"] = "0x" + "".join("%02x" % b for b in h)
    return t


def serve(Q, txs, owners=None, threshold=2, version="1.4.1"):
    SVC.info = {"address": SAFE, "nonce": 0, "threshold": threshold, "version": version,
                "owners": owners if owners is not None else [Q.me, ALICE, BOB]}
    SVC.txs = txs
    if RELAY[0]:
        RELAY[0].hi()
    Q.last_poll = 0
    Q.WATCH[0]["need_info"] = True
    Q.net_work()


def sign(Q, e, hold_ms):
    """Open e, see every page, hold A for hold_ms. -> did a confirmation get posted?"""
    n = len(SVC.posted)
    Q.open_entry(e)
    while Q.unseen():
        Q.turn(1)
    Q.press_sign()
    if Q.state != "hold":
        return False
    Q.keys.down.add("A")
    Q.time.now += hold_ms
    Q.hold_tick()
    Q.keys.down.discard("A")
    if Q.state == "hold":
        Q.hold_tick()       # let go
    return len(SVC.posted) > n


# ----------------------------------------------------------------------------- cases
def case_pin():
    chip()
    Q = fresh()
    check(Q.state == "home" and Q.pin_ok, "the pinned chip, slot and owner: the console starts")
    check(Q.serial == SERIAL and Q.row["locked"], "it read the chip's serial and slot 0's lock")
    Q = fresh(expect={"serial": "0123ffffffffffffff", "slot": 0, "owner": owner_of(0), "locked": True})
    check(Q.state == "pinfail" and "chip" in Q.pin_why, "another chip's serial: pinfail")
    Q = fresh(expect={"serial": SERIAL, "slot": 0, "owner": owner_of(2), "locked": True})
    check(Q.state == "pinfail" and "owner" in Q.pin_why, "a different owner address: pinfail")
    with open("slot.txt", "w") as f:
        f.write("2")
    Q = fresh()
    check(Q.sig.slot == 0 and Q.pin_ok, "slot.txt says 2: ignored, the pin's slot 0 is used")
    Q = fresh(expect={"serial": SERIAL, "slot": 2, "owner": owner_of(2), "locked": True})
    check(Q.state == "pinfail" and "not locked" in Q.pin_why, "a pinned slot that is not locked: pinfail")
    Q = fresh(expect=None)
    check(Q.state == "pinfail" and "QUORUM_EXPECT" in Q.pin_why, "production with no QUORUM_EXPECT: nothing is signable")
    Q = fresh(prod=False, expect=None)
    check(Q.state == "home" and Q.pin_ok, "a development board without a pin works as before")
    Q = fresh(safe=False)
    check(Q.state == "unconfigured" and Q.svc is None, "production with no QUORUM_SAFE: unconfigured, no service")
    # The owner address (two keccaks, ~0.7 s on the Pico) is remembered by the hash of its inputs.
    try:
        os.remove("owners.txt")
    except OSError:
        pass
    import webauthn
    o0, o2 = owner_of(0), owner_of(2)       # the test's own expectations, before counting
    pin0 = {"serial": SERIAL, "slot": 0, "owner": o0, "locked": True}
    real, n = webauthn.keccak256, [0]

    def counted(b):
        n[0] += 1
        return real(b)
    webauthn.keccak256 = counted
    try:
        Q = fresh(expect=pin0)
        first = n[0]
        n[0] = 0
        Q = fresh(expect=pin0)
        check(first == 2 and n[0] == 0 and Q.me == o0 and Q.pin_ok,
              "the owner address: computed once (two keccaks), then remembered by its inputs' hash")
        n[0] = 0
        Q = fresh(expect={"serial": SERIAL, "slot": 2, "owner": o2, "locked": True})
        check(n[0] == 2 and Q.me == o2, "another key's owner is computed, not taken from the remembered one")
    finally:
        webauthn.keccak256 = real


def case_refusals():
    chip()
    Q = fresh()
    good = tx(Q, 0)
    txs = [good, tx(Q, 1, safe=OTHER), tx(Q, 2, tamper=True), tx(Q, 3, op=2),
           tx(Q, 4, to=OTHER, op=1, data="0x12345678"),
           {"safeTxHash": "0x" + "ab" * 32, "safe": SAFE},            # no nonce, no fields
           tx(Q, 5, to=MULTISEND, op=1, data="0x8d80ff0a" + "00" * 64)]
    serve(Q, txs)
    by = {e["n"]: e for e in Q.queue}
    check(len(Q.queue) == 7 and Q.net_ok, "a malformed transaction among good ones: all 7 listed, the poll succeeded")
    check(Q.can_sign(by[0]) == (True, ""), "the plain transfer is signable")
    check("another Safe" in by[1]["why"], "another Safe's transaction: refused")
    check("hash" in by[2]["why"], "a hash the fields don't produce: refused")
    check(bool(by[3]["why"]), "operation 2: refused")
    check("delegatecall" in by[4]["why"].lower(), "a delegatecall to an unpinned contract: refused")
    bad = [e for e in Q.queue if e["r"]["summary"] == "Malformed"]
    check(len(bad) == 1 and bad[0]["why"] and Q.can_sign(bad[0])[0] is False, "the malformed one: refused, not signable")
    check(not by[5]["why"] or "delegatecall" not in by[5]["why"].lower(), "a multiSend delegatecall to the pinned batcher is not refused as a delegatecall")
    for n in (1, 2, 3, 4):
        check(not sign(Q, by[n], 5000), "#%d cannot be signed however long A is held" % n)
    check(not sign(Q, bad[0], 5000), "the malformed one cannot be signed")
    serve(Q, [good], owners=[ALICE, BOB])
    check(Q.can_sign(Q.queue[0]) == (False, "this key is not an owner"), "not an owner: can't sign")
    serve(Q, [good], version="1.1.1")
    check(Q.can_sign(Q.queue[0])[1].startswith("old Safe"), "a Safe older than 1.3.0: can't sign")
    serve(Q, [tx(Q, 0, conf=[Q.me])])
    check(Q.can_sign(Q.queue[0]) == (False, "already signed by you"), "already signed: can't sign again")
    Q.pin_ok = False
    serve(Q, [good])
    check(Q.can_sign(Q.queue[0]) == (False, "key doesn't match the pin"), "the pin failing after start: can't sign")
    import decode, quorum_cfg
    anvil = list(quorum_cfg.CFG["book"])[0]
    check(decode.name(Q.ctx, anvil) is None, "on Base Sepolia the laptop's Anvil names are not used (%s)" % anvil[:10])
    check(decode.name(Q.ctx, Q.me) == "This key", "this key is still named")


def case_sign():
    c = chip(counter=5)
    key0 = c.keys[0]
    Q = fresh()
    check(Q.counter == 5 and Q.outside == 0, "counter read at start: 5, first look")
    serve(Q, [tx(Q, 0), tx(Q, 1, to=OTHER, data="0xdeadbeef")])
    e = Q.queue[0]
    Q.open_entry(e)
    Q.press_sign()
    check(Q.state == "review" and "See every page" in Q.msg, "A before every page was seen: not armed")
    signed = []
    real = Q.sig.sign

    def spy(digest, slot=None):
        r, s = real(digest, slot)
        signed.append((digest, r, s))
        return r, s
    Q.sig.sign = spy
    check(not sign(Q, e, 1900), "held 1.9 s: nothing signed")
    check(sign(Q, e, 2100), "held 2.1 s: signed and posted")
    url, body = SVC.posted[-1]
    digest, r, s = signed[-1]
    x, y = Q.sig.pubkey()
    ad, fields, want = webauthn.assertion(e["mine"])
    check(digest == want and p256.verify(x, y, digest, r, s), "the chip signed the WebAuthn digest of the hash computed here, and it verifies")
    check(body["signature"] == Q.signature_for(e, ad, fields, r, s) and e["h"] in url, "the posted confirmation is that signature, for that hash")
    check(Q.counter == 6 and c.counters[0] == 6, "counter 5 -> 6 after one signature")
    check(open("counter-%s.txt" % SERIAL).read() == "6", "the new count is saved")
    check(any("Key use #6" in l for l in Q.result[2]), "the result screen shows key use #6")
    Q.row = dict(Q.row, locked=False)       # an unlocked slot: its key is read again before signing
    c.keys[0] = p256.rand_scalar()          # another key in slot 0 while the console runs
    before = len(SVC.posted)
    Q.unsent = (Q.queue[1], "0xold")
    check(not sign(Q, Q.queue[1], 3100) and len(SVC.posted) == before and not Q.result[0],
          "the chip's key changed since start: not signed")
    check(Q.unsent is None, "and no older signature is offered for sending again")
    c.keys[0] = key0
    Q.row = dict(Q.row, locked=True)
    c.cfg[12] ^= 1                          # a sealed slot: another chip (another serial) is caught
    check(not sign(Q, Q.queue[1], 3100) and "changed" in Q.result[2][1], "a different chip swapped in while running: not signed")
    c.cfg[12] ^= 1
    red = Q.queue[1]
    check(red["r"]["level"] == "red" and not red["why"], "an unknown call is red but signable")
    check(not sign(Q, red, 2500), "red, held 2.5 s: nothing signed")
    check(sign(Q, red, 3100), "red, held 3.1 s: signed")
    c.counters[0] += 3
    c.save()
    Q = fresh(keep=True)
    check(Q.outside == 3, "3 signatures made while the console was not looking: flagged at start")
    Q.handle("A")
    check(Q.outside == 0, "any key on home clears the warning (it stays in log.txt)")
    check("outside this console" in open("log.txt").read(), "and the log has it")


def case_service():
    chip()
    Q = fresh()
    serve(Q, [tx(Q, 0)], owners=[ALICE, BOB])
    check(not SVC.sim_calls(), "https: no /sim/ calls, even when this key is not an owner")
    check(all(c[2].get("Authorization") == "Bearer test-key" for c in SVC.calls), "https: the API key goes with each call")
    check(Q.POLL_MS == 20000 and Q.IDLE_POLL_MS == 600000, "https with a key: polls every 20 s, 600 s when idle")
    n = len(SVC.calls)
    Q.net_work()
    check(len(SVC.calls) == n + 1, "the next poll asks only for the queue (the Safe's info is cached)")
    SVC.txs = [tx(Q, 0), tx(Q, 1)]
    n = len(SVC.calls)
    Q.net_work()
    check(len(SVC.calls) == n + 3, "the queue changed: the Safe's info is fetched again, then the queue")
    Q.open_entry(Q.queue[0])
    Q.reject()
    check(not SVC.sim_calls(), "rejecting on https does not tell the service anything")
    SVC.info = {"address": SAFE, "nonce": 0, "threshold": 5, "owners": [ALICE, BOB]}
    Q.WATCH[0]["need_info"] = True
    Q.net_work()
    check(not Q.net_ok and "bad Safe info" in repr(Q.log[-1]), "threshold 5 of 2 owners: the Safe's info is refused")
    Q = fresh(url="http://192.168.0.2:8787")
    serve(Q, [tx(Q, 0)], owners=[ALICE, BOB])
    check(SVC.sim_calls() and not any(c[2].get("Authorization") for c in SVC.calls), "http (the laptop's simulation): announce, and never the API key")
    check(Q.POLL_MS == 3000, "http: polls every 3 s")
    Q = fresh()
    SVC.info = {"address": SAFE, "nonce": 0, "threshold": 2, "owners": [Q.me, ALICE, BOB]}
    SVC.txs = [tx(Q, n) for n in range(10)]
    SVC.fail_pending = MemoryError()
    Q.net_work()
    asked = [c[1] for c in SVC.calls if "/multisig-transactions/" in c[1]]
    check(len(Q.queue) == 10 and [e["n"] for e in Q.queue] == list(range(10)) and not any(e["why"] for e in Q.queue)
          and "offset=3" in asked[-3] and "offset=9" in asked[-1], "out of memory on the queue: read 3 at a time, all 10 listed")


def case_owners_pages():
    """A 3-of-5 or longer Safe: the Owners screen scrolls (down/right, up/left, or the dial) instead of cutting the list."""
    import quorum_ui
    chip()
    Q = fresh()
    five = [Q.me] + ["0x%040x" % (0x1000 + i) for i in range(1, 7)]      # seven owners
    serve(Q, [], owners=five, threshold=3)
    check(Q.owner_pages() == 3 and quorum_ui.OWNERS_PER_PAGE == 3, "seven owners: three pages of three")
    seen = []
    Q.handle("A")
    check(Q.state == "owners" and Q.opage == 0, "A on home (its one Safe in focus): the Owners screen, page 1")
    for _ in range(3):
        quorum_ui.draw(Q)
        page = Q.owners()[Q.opage * 3:(Q.opage + 1) * 3]
        seen += page
        Q.handle("down")
    check(Q.opage == 2 and seen == Q.owners(), "down pages through: every owner was on a page, once")
    Q.handle("down")
    check(Q.opage == 2, "down on the last page stays there")
    Q.handle("up")
    Q.handle("left")
    check(Q.opage == 0 and Q.state == "owners", "up and left go back a page")
    Q.handle("left")
    check(Q.state == "home", "left on page 1 leaves, as before")
    Q.handle("A")
    Q.handle("down")
    Q.handle("A")
    check(Q.state == "home", "A leaves from any page")
    Q.handle("A")
    check(Q.opage == 0, "opening Owners again starts on page 1")
    Q.KNOB = True
    Q.knob("down")
    Q.knob("down")
    check(Q.state == "owners" and Q.opage == 2, "the dial: turns page (the second turn of two lands on the last)")
    for _ in range(3):
        Q.knob("up")
    check(Q.opage == 0, "the dial turned back to page 1")
    Q.knob("press")
    check(Q.state == "home", "a press leaves")
    Q.KNOB = False


def case_production():
    chip()
    Q = fresh()
    import signer
    check(not signer.flag("ALLOW_LOCK") and not signer.flag("ALLOW_GENKEY"), "production: ALLOW_LOCK/ALLOW_GENKEY in secrets.py count for nothing")
    check(Q.SOFT_OK is False, "production: ALLOW_SOFT_KEY counts for nothing")
    import splash, time

    class Boom:
        def render(self, *a):
            raise MemoryError("allocating 1280 bytes")
    splash.begin()
    was, t0 = splash._art, splash._t0
    splash._art, splash._t0, splash._finished = Boom(), time.ticks_add(time.ticks_ms(), -30000), False
    try:
        splash.draw()
        ok = True
    except MemoryError:
        ok = False
    splash._art, splash._t0 = was, t0
    check(ok, "a boot-animation frame that runs out of memory is skipped, not fatal (it took the console down, 2026-09-30)")
    import lcd
    check(lcd.BANDS == 8 and len(lcd._BUF) == 14400, "the 240x240 board is strip-buffered (14 KB, not a 115 KB frame: that left HTTPS no room, 2026-09-29)")
    Q = fresh(url=None, extra='APP_URL = "http://10.9.8.7:3001"\n')
    check(Q.WATCH[0]["base"] == "https://api.safe.global/tx-service/basesep", "production: a leftover APP_URL is ignored, Safe's own service for the chain is used")
    Q = fresh(url=None, prod=False, extra='APP_URL = "http://10.9.8.7:3001"\n')
    check(Q.WATCH[0]["base"] == "http://10.9.8.7:3001", "a development console still falls back to APP_URL")
    Q = fresh(prod=False)
    import signer
    check(signer.flag("ALLOW_LOCK"), "a development board still honours ALLOW_LOCK")
    pin = {"serial": SERIAL, "slot": 0, "owner": owner_of(0), "locked": True}
    for f in ("key.bin",):
        if f in os.listdir():
            os.remove(f)
    atecc_sim.present = False
    try:
        Q = fresh(expect=pin)
        check(Q.state == "nochip" and Q.sig.name == "none", "production with no chip on the bus: NO CHIP, and no software key")
        check("key.bin" not in os.listdir(), "no key.bin is written")
        Q = fresh(prod=False, expect=None)
        check(Q.sig.name == "pico-soft", "a development board with ALLOW_SOFT_KEY still falls back to the software key")
    finally:
        atecc_sim.present = True
    chip()
    Q = fresh()
    serve(Q, [tx(Q, 0)])
    Q.keys.pressed = lambda: []
    bad = Q.U.draw
    Q.U.draw = lambda q: 1 / 0
    Q.dirty = True
    for i in range(Q.CRASH_AFTER):
        Q._busy = False
        Q.dirty = True
        Q.tick(None)
    Q.U.draw = bad
    check(Q.state == "crashed", "20 failed ticks in a row: the crashed screen")
    at = [l for l in open("log.txt").read().split("\n") if "  at " in l and "in tick" in l]
    check(len(at) == 1 and "console_test.py:" in at[-1] and "quorum.py:" in at[-1],
          "the first failure's frames in the log, once: %s" % (at[-1][-70:] if at else "none"))
    check(not Q.queue and not Q.W["cache"] and Q.state == "crashed",
          "the queue and its cache dropped, so the crashed screen has room to draw; nothing to review")
    Q.handle("A")
    check(Q.state == "crashed", "A does nothing on the crashed screen")


class FlipClock(Clock):
    """A Clock that puts the virtual chip back on the bus at the console's first wait of `at` ms."""

    def __init__(self, at):
        Clock.__init__(self)
        self.at = at

    def sleep_ms(self, ms):
        if ms == self.at:
            atecc_sim.present = True
        Clock.sleep_ms(self, ms)


def logged_after(mark):
    """What the console logged after mark (log.1.txt, then log.txt: a rotation can split them)."""
    text = ""
    for name in ("log.1.txt", "log.txt"):
        try:
            with open(name) as f:
                text += f.read()
        except OSError:
            pass
    return text.rsplit(mark, 1)[-1]


def log_mark(name):
    import time
    mark = "-- test mark %s %d" % (name, time.ticks_ms())
    with open("log.txt", "a") as f:
        f.write(mark + "\n")
    return mark


def case_nochip():
    """A start that finds no chip clocks the bus free and looks again, past the 608's watchdog, and
    logs why each time (board #2, 2026-11-10: one start in 100 found none, the next found it). No
    chip looks again by itself every 30 s; Not pinned never does: each look there reads the key."""
    chip()
    fresh()
    uses = atecc_sim.chip().counters[0]     # what a plain start costs
    chip()
    mark = log_mark("flip")
    atecc_sim.present = False
    try:
        Q = fresh(clock=FlipClock(1500))
    finally:
        atecc_sim.present = True
    log = logged_after(mark)
    check(Q.NOCHIP_GAP_MS == 1500 and Q.state == "home" and Q.sig.name == "atecc608" and Q.pin_ok,
          "a start whose first look finds no chip looks again 1.5 s on, finds it, and comes up pinned")
    check("no chip, look 1 of 4: nothing answers on I2C0; scan empty; SDA high" in log and "chip found on look 2 of 4" in log,
          "it logs the miss, why, the bus, and the look that found it")
    check(atecc_sim.chip().counters[0] == uses, "the same uses of the key as a plain start: a miss reads nothing")
    mark = log_mark("none")
    atecc_sim.present = False
    try:
        Q = fresh()
        log = logged_after(mark)
        check(Q.state == "nochip" and Q.time.now - 100000 >= 3 * Q.NOCHIP_GAP_MS, "no chip at all: four looks, 1.5 s apart, then No chip")
        check(all("no chip, look %d of 4" % i in log for i in (1, 2, 3, 4)), "each look is logged")
        Q.keys.pressed = lambda: []
        atecc_sim.present = True
        Q.time.now += Q.NOCHIP_EVERY_MS - 1000
        Q.tick(None)
        check(Q.state == "nochip", "back on the bus: No chip doesn't look before its 30 s")
        Q.time.now += 2000
        Q.tick(None)
        check(Q.state == "home" and Q.pin_ok, "30 s on it looks by itself, finds the chip and comes up pinned")
    finally:
        atecc_sim.present = True
    Q = fresh(expect={"serial": "0123ffffffffffffff", "slot": 0, "owner": owner_of(0), "locked": True})
    n = list(atecc_sim.chip().counters)
    ops = []
    real = atecc_sim.Chip.execute

    def spy(self, op, p1, p2, data):
        ops.append(op)
        return real(self, op, p1, p2, data)
    atecc_sim.Chip.execute = spy
    try:
        Q.keys.pressed = lambda: []
        Q.time.now += 3 * Q.NOCHIP_EVERY_MS
        Q.tick(None)
    finally:
        atecc_sim.Chip.execute = real
    check(Q.state == "pinfail" and not ops and atecc_sim.chip().counters == n, "Not pinned never looks by itself: nothing asked of the chip")


def case_chips():
    """chips.json: each chip seen gets a number and a theme (1 dark, 2 light); the console uses it."""
    import quorum_ui
    if "chips.json" in os.listdir():
        os.remove("chips.json")
    chip()
    Q = fresh()
    check(Q.chip and Q.chip["name"] == "chip 1" and Q.chip["theme"] == "dark" and Q.profile == "legacy-test",
          "the first chip seen: chip 1, dark, test table")
    check(quorum_ui.T == quorum_ui.THEMES["dark"], "the console draws chip 1 in the dark theme")
    c = atecc_sim.chip()
    c.cfg[8:13] = bytes([0x42, 0x42, 0x42, 0x42, 0xEE])      # another chip on the bus
    c.save()
    Q = fresh(expect=None, prod=False)
    check(Q.chip["name"] == "chip 2" and Q.chip["theme"] == "light", "a second chip: chip 2, light")
    check(quorum_ui.T == quorum_ui.THEMES["light"], "the console draws chip 2 in the light theme")
    Q = fresh(expect={"serial": SERIAL, "slot": 0, "owner": owner_of(0), "locked": True})
    check(Q.state == "pinfail" and Q.chip["name"] == "chip 2", "chip 2 on a board pinned to chip 1: named, and still refused by the pin")
    c.cfg[8:13] = bytes.fromhex(SERIAL[8:])
    c.save()
    Q = fresh()
    check(Q.chip["name"] == "chip 1" and quorum_ui.T == quorum_ui.THEMES["dark"] and Q.pin_ok, "chip 1 back: chip 1 again, dark, pinned")
    with open("chips.json", "w") as f:
        f.write("{not json")
    Q = fresh()
    check(Q.chip["name"] == "chip 1" and Q.pin_ok, "a damaged chips.json starts over and changes nothing about the pin")
    import json as J
    check(len(J.load(open("chips.json"))) == 1, "and is written whole again")


def case_multi():
    """Several pinned chips: the one on the bus picks its entry at boot; any other is refused."""
    chip()
    mine = {"serial": SERIAL, "slot": 0, "owner": owner_of(0), "locked": True}
    other = {"serial": "0123aaaaaaaaaaaaee", "slot": 0, "owner": "0x" + "11" * 20, "locked": True}
    Q = fresh(expect=[other, mine])
    check(Q.state == "home" and Q.pin_ok and Q.EXPECT["serial"] == SERIAL, "two chips pinned: this one finds its entry and signs")
    serve(Q, [tx(Q, 0)])
    check(sign(Q, Q.queue[0], 2100), "and a signature goes through")
    Q = fresh(expect=[other])
    check(Q.state == "pinfail" and "not one of the 1 pinned" in Q.pin_why, "a list without this chip: refused")
    bad = dict(mine, owner=owner_of(2))
    Q = fresh(expect=[other, bad])
    check(Q.state == "pinfail" and "owner" in Q.pin_why, "its entry with the wrong owner: refused all the same")


def case_memory():
    """Board #2, 2026-11-11, nine queued on a 2 of 2: the console ran out of memory between the chip's
    signature and the service. An entry keeps only its hash's fields. No room in one piece: the key is
    not used. A signature that can't be saved for memory is still held for A. A 201 marks the row at
    once, a saved one sent after a restart too, and the highlight goes on to the next one waiting."""
    chip()
    Q = fresh()
    a, b, c = tx(Q, 0, value=1, conf=[ALICE]), tx(Q, 1, value=2, conf=[ALICE]), tx(Q, 2, value=3, conf=[ALICE])
    serve(Q, [a, b, c])
    e = Q.queue[0]
    check("t" not in e and e["f"] == Q.signed_fields(a) and e["conf"] == [ALICE.lower()],
          "an entry keeps the fields its hash covers, not the service's whole transaction")

    calls = []
    real_sign = Q.sig.sign
    Q.sig.sign = lambda d: calls.append(1) or real_sign(d)
    c0 = Q.read_counter()
    Q.SIGN_ROOM = 1 << 30
    try:
        posted = sign(Q, e, 2100)
    finally:
        Q.SIGN_ROOM = 4096
    check(not posted and not calls and Q.read_counter() == c0 and Q.state == "result" and not Q.result[0]
          and "The key was not used." in Q.result[2] and Q.reset_at and not Q.unsent,
          "no room in one piece before signing: the chip is never asked, nothing posted, and a restart is set")
    Q.reset_at = 0

    import builtins
    real_post = SVC.post
    try:
        SVC.post = lambda url, json=None, headers=None, timeout=None: (_ for _ in ()).throw(OSError(12))
        Q.open = lambda *x, **k: (_ for _ in ()).throw(MemoryError("memory allocation failed"))   # quorum's files only
        posted = sign(Q, e, 2100)
    finally:
        SVC.post, Q.open = real_post, builtins.open
    check(not posted and len(calls) == 1 and Q.result[1] == "Not sent" and Q.unsent and Q.unsent[0] is e,
          "the service unreachable and the save failing for memory: Not sent, the signature held")
    n = len(SVC.posted)
    Q.handle(Q.SIGN)
    check(len(SVC.posted) == n + 1 and len(calls) == 1 and Q.result[0] and not Q.unsent and Q.signed_by_me(e),
          "A sends the held signature, with no new use of the key, and the row is marked at once")
    Q.handle(Q.SIGN)
    check(Q.state == "home" and Q.sel == 1, "OK: home, the highlight on the next one that waits (#1)")
    check(isinstance(Q._room, bytearray) and len(Q._room) == Q.SIGN_ROOM, "the signing room is set aside again after it")
    held = Q._room
    posted = sign(Q, Q.queue[1], 2100)
    check(posted and Q._room is not held and len(Q._room) == Q.SIGN_ROOM,
          "a signature hands the room over before the chip signs, and takes it again after")
    Q.handle(Q.SIGN)

    marked = Q.signed_by_me(Q.queue[1])
    check(posted and marked and Q.sel == 2 and len(calls) == 2, "signed #1: marked, the highlight on #2")
    Q.open_entry(Q.queue[2])
    Q.reject()
    check(Q.state == "home" and Q.sel == 2, "#2 rejected and nothing else waits: the highlight stays")

    SVC.post = lambda url, json=None, headers=None, timeout=None: (_ for _ in ()).throw(OSError(12))
    try:
        posted = sign(Q, Q.queue[2], 2100)
    finally:
        SVC.post = real_post
    kept = "unsent.json" in os.listdir()
    Q = fresh(keep=True)                    # a restart: the service still lists only Alice for #2
    serve(Q, [a, b, c])
    check(kept and not posted and SVC.posted and c["safeTxHash"] in SVC.posted[-1][0] and Q.signed_by_me(Q.queue[2])
          and not Q.waiting(Q.queue[2]),
          "a saved signature sent after a restart marks its row: it is not offered again")


def case_unsent():
    """A signature the service did not take survives a restart and goes out after the next boot;
    a lost HTTPS reserve restarts the console, but only on home."""
    chip()
    Q = fresh()
    t = tx(Q, 0)
    serve(Q, [t])
    real_post = SVC.post
    SVC.post = lambda url, json=None, headers=None, timeout=None: (_ for _ in ()).throw(OSError(12))
    try:
        check(not sign(Q, Q.queue[0], 2100) and Q.unsent and "unsent.json" in os.listdir(), "OSError 12 on the confirmation: kept in RAM and on flash")
    finally:
        SVC.post = real_post
    import txservice
    check(txservice.why(422, {"nonFieldErrors": ["Signature is not valid"]}) == "HTTP 422: Signature is not valid"
          and txservice.why(400, {"detail": "no"}) == "HTTP 400: no" and txservice.why(502, {}) == "HTTP 502"
          and txservice.why(400, {"signature": ["bad"]}) == "HTTP 400: signature: bad" and txservice.why(201, {}) == "",
          "a refused confirmation says what the service said (detail, nonFieldErrors, any field), never nothing")
    Q = fresh(keep=True)                    # a restart (the RAM copy is gone)
    serve(Q, [t])
    check(SVC.posted and t["safeTxHash"] in SVC.posted[-1][0] and "unsent.json" not in os.listdir(),
          "after the restart, the first good poll sends the saved signature and forgets it")
    with open("unsent.json", "w") as f:
        f.write('{"h": "0x' + "ab" * 32 + '", "n": 9, "sig": "0x00"}')
    Q = fresh(keep=True)
    n = len(SVC.posted)
    serve(Q, [t])
    check(len(SVC.posted) == n and "unsent.json" not in os.listdir(), "a saved signature whose transaction left the queue is dropped, not sent")
    resets = []
    Q.machine.reset = lambda: resets.append(1)
    for f in ("restart.txt",):
        if f in os.listdir():
            os.remove(f)
    Q.svc.lost = True
    Q.open_entry(Q.queue[0])
    Q._busy = False
    Q.tick(None)
    check(not resets, "the reserve lost during a review: no restart")
    Q.state = "home"
    Q._busy = False
    Q.tick(None)
    check(resets == [1] and "restart" in open("log.txt").read(), "back on home: the console restarts, and says why in log.txt")

    # A heap in pieces (no PROBE_B bytes in one piece, after a collect): a restart after STARVED_N
    # checks in a row on home or a result, never in a review, never before STARVED_UP_MS up
    time = Q.time                           # quorum's clock here (Clock): every tick reads it
    Q.svc.lost = False

    def checks(n, b):
        Q.PROBE_B = b
        for _ in range(n):
            Q.probe_t = time.ticks_add(time.ticks_ms(), -Q.PROBE_MS)
            Q._busy = False
            Q.tick(None)
    del resets[:]
    Q.STARVED_UP_MS, Q.up_long, Q.starved = 0, False, 0
    Q.started = time.ticks_ms()
    Q.open_entry(Q.queue[0])
    checks(Q.STARVED_N + 2, 1 << 30)
    in_review = list(resets)
    Q.state = "home"
    checks(Q.STARVED_N - 1, 1 << 30)
    checks(1, 64)                           # one good check: the count starts again
    checks(Q.STARVED_N - 1, 1 << 30)
    early = list(resets)
    checks(1, 1 << 30)
    check(not in_review and not early and resets == [1] and "no 1073741824 bytes in one piece for 30 s" in open("log.txt").read(),
          "a heap in pieces: no restart in a review, none before %d checks in a row, then a restart, and log.txt says why" % Q.STARVED_N)
    del resets[:]
    Q.STARVED_UP_MS, Q.up_long, Q.starved = 10 ** 9, False, 0
    Q.started = time.ticks_ms()
    Q.state = "result"
    checks(Q.STARVED_N * 3, 1 << 30)
    check(not resets and Q.starved == Q.STARVED_N * 3, "the same just after a start: no restart (no loop of restarts)")
    Q.PROBE_B = 2048

    # A screen that only shows, left alone: back to home after BROWSE_IDLE_MS, where it polls. Not a review
    Q.state, Q.svc.lost = "review", False
    Q.open_entry(Q.queue[0])
    Q.last_key = time.ticks_add(time.ticks_ms(), -Q.BROWSE_IDLE_MS - 1000)
    Q._busy = False
    Q.tick(None)
    stayed = Q.state == "review"
    went = []
    for s in Q.BROWSE:
        Q.state = s
        Q.last_key = time.ticks_add(time.ticks_ms(), -Q.BROWSE_IDLE_MS + 60000)
        Q._busy = False
        Q.tick(None)
        kept = Q.state == s
        Q.last_key = time.ticks_add(time.ticks_ms(), -Q.BROWSE_IDLE_MS - 1000)
        Q._busy = False
        Q.tick(None)
        went.append(kept and Q.state in ("home", "saver"))
    check(stayed and all(went), "%s: kept a minute after a key, home after %d s alone; a review stays" % ("/".join(Q.BROWSE), Q.BROWSE_IDLE_MS // 1000))


def case_watchdog():
    import machine
    try:
        machine.WDT(timeout=9000)
        ok = False
    except ValueError:
        ok = True
    check(ok, "the watchdog refuses 9000 ms, as rp2 does (8388 at most)")
    import watch
    watch.start()
    check(machine.WDT.started == watch.TIMEOUT_MS, "watch.start runs the watchdog at %d ms" % watch.TIMEOUT_MS)
    before = machine.WDT.feeds
    watch._feed(None)
    check(machine.WDT.feeds == before + 1, "fed while the deadline is ahead")
    watch._deadline = watch.time.ticks_add(watch.time.ticks_ms(), -1)
    watch._feed(None)
    check(machine.WDT.feeds == before + 1, "not fed once the deadline has passed")


ETH_SAFE = "0x7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c"
USDC_ETH = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
TWO = ('QUORUM_SAFES = [{"chainId": %d, "address": "%s", "name": "Test Safe"},\n'
       '                {"chainId": 1, "address": "%s", "name": "Vault"}]' % (CHAIN, SAFE, ETH_SAFE))


def case_safes():
    """Several Safes on several chains: each asked about at its own chain's service, in turn, one
    queue on home, each transaction hashed with its own Safe's chain."""
    import policy, decode, quorum_cfg
    got, why = policy.safes([{"chainId": 1, "address": ETH_SAFE}, {"chainId": 1, "address": ETH_SAFE.upper().replace("0X", "0x")},
                             {"chainId": 8453, "address": "0x12"}, {"address": SAFE}], None)
    check(len(got) == 1 and got[0]["name"] == "Safe" and why, "QUORUM_SAFES: a duplicate, a bad address and a missing chainId are dropped, and it says so")
    got, why = policy.safes([{"chainId": c, "address": SAFE} for c in (1, 10, 8453, 84532, 137)], None)
    check(len(got) == policy.MAX_SAFES and "more than" in why, "more than %d Safes: only the first %d are watched" % (policy.MAX_SAFES, policy.MAX_SAFES))
    got, why = policy.safes(None, {"chainId": CHAIN, "address": SAFE, "name": "One"})
    check(len(got) == 1 and got[0]["chainId"] == CHAIN and not why, "QUORUM_SAFE (one Safe) still works")
    eth = decode.context(quorum_cfg.CFG, ETH_SAFE, chain=1)
    fork = decode.context(quorum_cfg.CFG, SAFE, chain=31337)
    check(USDC_ETH in eth["tokens"] and USDC_BASE not in eth["tokens"] and MULTISEND in eth["batchers"],
          "on Ethereum: Ethereum's USDC is known, Base's is not, MultiSend (every chain) is pinned")
    check(USDC_BASE in fork["tokens"] and USDC_ETH not in fork["tokens"], "the Anvil fork of Base (31337) uses Base's lists")

    chip()
    Q = fresh(url=None, safe=False, extra=TWO)
    check(len(Q.WATCH) == 2 and Q.state == "home", "two Safes in QUORUM_SAFES: both watched")
    check(Q.WATCH[0]["base"].endswith("/tx-service/basesep") and Q.WATCH[1]["base"].endswith("/tx-service/eth"),
          "each Safe's service comes from its chain, not from secrets.py")
    SVC.info = {"address": SAFE, "nonce": 0, "threshold": 2, "version": "1.4.1", "owners": [Q.me, ALICE, BOB]}
    SVC.txs = [tx(Q, 0)]
    good_eth = tx(Q, 7, safe=ETH_SAFE, chain=1, hsafe=ETH_SAFE, to=BOB)
    replay = tx(Q, 8, safe=ETH_SAFE, chain=CHAIN, hsafe=ETH_SAFE)       # hashed for Base Sepolia, served as Ethereum's
    SVC.safes[ETH_SAFE] = {"info": {"address": ETH_SAFE, "nonce": 7, "threshold": 1, "version": "1.4.1", "owners": [Q.me, BOB]},
                           "txs": [good_eth, replay]}
    Q.net_work()
    Q.net_work()
    urls = [c[1] for c in SVC.calls]
    check(any("/tx-service/basesep/" in u for u in urls) and any("/tx-service/eth/" in u and ETH_SAFE[2:] in u.lower() for u in urls),
          "one poll each: Base Sepolia's service, then Ethereum's")
    check(len(Q.queue) == 3 and Q.net_ok, "home: one queue with both Safes' transactions")
    by = {e["n"]: e for e in Q.queue}
    check(by[0]["w"]["chain"] == CHAIN and by[7]["w"]["chain"] == 1, "each entry knows its Safe")
    check(Q.can_sign(by[7]) == (True, ""), "Ethereum's transaction, hashed for chain 1: signable")
    check("hash" in by[8]["why"], "a transaction hashed for another chain: refused (no replay across chains)")
    check(Q.threshold(by[7]["w"]) == 1 and Q.threshold(by[0]["w"]) == 2, "each Safe's own threshold")
    n = len(SVC.calls)
    Q.net_work()
    check(len(SVC.calls) == n + 1 and "/tx-service/basesep/" in SVC.calls[-1][1], "then in turn: one Safe per poll, not both")
    Q.open_entry(by[7])
    check(Q.CHAIN == 1 and Q.SAFE_ADDR == ETH_SAFE, "reviewing Ethereum's transaction puts that Safe in view")
    check(sign(Q, by[7], 2100) and "/tx-service/eth/" in SVC.posted[-1][0], "its confirmation goes to Ethereum's service")
    Q.handle("A")
    check(Q.state == "home" and Q.rr == 1 and Q.last_poll == 0, "back on home: that Safe is asked about next, now")
    mark = log_mark("eth down")
    SVC.safes[ETH_SAFE]["down"] = True
    Q.WATCH[1]["need_info"] = True
    Q.net_work()
    check(not Q.net_ok and "Vault" in Q.net_err and any(e["w"]["chain"] == CHAIN for e in Q.queue),
          "Ethereum's service down: said so by name, Base Sepolia's queue still shown")
    at = [l for l in logged_after(mark).split("\n") if "  at " in l]    # this poll's, not an older case's (a rotation hid that)
    check(len(at) == 1 and "txservice.py:" in at[0] and " in _get" in at[0], "where the poll failed, in the log: %s" % (at[-1][-70:] if at else "none"))
    SVC.safes[ETH_SAFE]["down"] = False

    # a signature the service did not take, for the second Safe, survives a restart and goes to its service
    real_post = SVC.post
    SVC.post = lambda url, json=None, headers=None, timeout=None: (_ for _ in ()).throw(OSError(12))
    Q.net_work()
    e = [x for x in Q.queue if x["n"] == 7][0]
    e["conf"] = []
    try:
        sign(Q, e, 2100)
    finally:
        SVC.post = real_post
    saved = json.load(open("unsent.json"))
    check(saved.get("chain") == 1 and saved.get("safe") == ETH_SAFE, "the saved signature names its chain and Safe")
    Q = fresh(url=None, safe=False, extra=TWO, keep=True)
    SVC.info = {"address": SAFE, "nonce": 0, "threshold": 2, "version": "1.4.1", "owners": [Q.me, ALICE, BOB]}
    SVC.txs = [tx(Q, 0)]
    SVC.safes[ETH_SAFE] = {"info": {"address": ETH_SAFE, "nonce": 7, "threshold": 1, "owners": [Q.me, BOB]}, "txs": [good_eth]}
    Q.net_work()
    check("unsent.json" in os.listdir() and not SVC.posted, "after a restart, Base Sepolia's poll leaves Ethereum's saved signature alone")
    Q.net_work()
    check(SVC.posted and "/tx-service/eth/" in SVC.posted[-1][0] and "unsent.json" not in os.listdir(),
          "Ethereum's poll sends it, to Ethereum's service")

    Q = fresh(url=None, safe=False, extra='QUORUM_SAFES = [{"chainId": 10, "address": "%s", "name": "OP"}]' % SAFE)
    Q.net_work()
    check(not Q.net_ok and "no service for chain 10" in Q.net_err, "a chain with no pinned service: said so, nothing asked")
    Q = fresh(url="http://192.168.0.2:8787", safe=False, extra=TWO)
    check(all(w["base"] == "http://192.168.0.2:8787" for w in Q.WATCH), "QUORUM_URL (the laptop) overrides every Safe's service")
    Q = fresh(url=None, safe=False, extra='QUORUM_SAFES = [{"chainId": %d, "address": "%s", "name": "A"}, {"chainId": 31337, "address": "%s", "name": "B", "url": "http://10.0.0.2:8788"}]' % (CHAIN, SAFE, ETH_SAFE))
    check(Q.WATCH[0]["base"].endswith("/basesep") and Q.WATCH[1]["base"] == "http://10.0.0.2:8788", "a Safe's own \"url\" overrides its chain's service, for that Safe only")


def drawn_texts(Q):
    """Every string one draw puts on the screen."""
    import fonts
    import quorum_ui as U
    out, real = [], fonts.text
    fonts.text = lambda d, t, *a, **k: (out.append(t), real(d, t, *a, **k))[1]
    try:
        U.draw(Q)
    finally:
        fonts.text = real
    return out


def case_home():
    """Home when nothing waits for this key: the status screen (this key, whether it is ready, the
    Safes it watches); the queue list when something does, as before."""
    chip()
    Q = fresh(url=None, safe=False, extra=TWO)
    SVC.info = {"address": SAFE, "nonce": 0, "threshold": 2, "version": "1.4.1", "owners": [Q.me, ALICE, BOB]}
    SVC.txs = []
    SVC.safes[ETH_SAFE] = {"info": {"address": ETH_SAFE, "nonce": 7, "threshold": 1, "version": "1.4.1", "owners": [Q.me, BOB]}, "txs": []}
    check(Q.readiness() == "starting", "before any Safe answers: starting")
    Q.net_work()
    Q.net_work()
    try:
        os.remove(Q.RECENT_FILE)
    except OSError:
        pass
    Q.recent = []
    t = drawn_texts(Q)
    check(Q.status_home() and Q.readiness() == "ready" and "Ready to approve" in t and "SAFES" in t,
          "nothing queued, an owner of both: the status screen says Ready to approve, and lists the Safes")
    check("Test Safe" in t and "2 of 3" in t and "1 of 2" in t, "each Safe's row: its name and how many must approve")
    Q.hsel = 0
    Q.handle("down")
    check(Q.hsel == 1, "down: the second Safe")
    Q.handle("A")
    check(Q.state == "owners" and Q.SAFE_ADDR == ETH_SAFE, "A: that Safe's Owners")
    Q.handle("B")
    Q.handle("B")
    check(Q.state == "recent", "B on home: Recent")
    Q.handle("B")
    Q.handle("X")
    check(Q.state == "device", "X: Device")
    Q.handle("B")
    check(Q.state == "home", "B: home")
    Q.KNOB = True
    Q.hsel = 1
    Q.knob("down")
    check(Q.hfoot == "recent", "the dial: past the last Safe, Recent")
    Q.knob("down")
    Q.knob("press")
    check(Q.state == "device" and Q.hfoot is None, "then Device; a press opens it")
    Q.handle("B")
    Q.knob("up")
    Q.knob("press")
    check(Q.state == "owners" and Q.SAFE_ADDR == SAFE, "turned back to the first Safe; a press opens its Owners")
    Q.knob("press")
    Q.KNOB = False

    # not an owner of anything yet: the one thing to do next, with this key's address
    SVC.info["owners"] = [ALICE, BOB]
    SVC.safes[ETH_SAFE]["info"]["owners"] = [BOB]
    for w in Q.WATCH:
        w["need_info"] = True
    Q.net_work()
    Q.net_work()
    t = drawn_texts(Q)
    check(Q.readiness() == "not_owner" and "Not an owner yet" in t and ("Add " + Q.U.short(Q.me)) in t and t.count("not owner") == 2,
          "owner of neither: Not an owner yet, Add <this key's address>, and each row says not owner")
    SVC.info["owners"] = [Q.me, ALICE, BOB]
    SVC.safes[ETH_SAFE]["info"]["owners"] = [Q.me, BOB]
    for w in Q.WATCH:
        w["need_info"] = True

    SVC.txs = [tx(Q, 0)]
    Q.last_poll = 0
    Q.net_work()
    Q.net_work()
    check(Q.queue and not Q.status_home(), "a transaction waiting for this key: the queue list, as before")
    e = [x for x in Q.queue if x["n"] == 0][0]
    signed = sign(Q, e, 2100)
    Q.handle("A")
    SVC.txs[0]["confirmations"].append({"owner": Q.me})     # the service lists this key's confirmation
    Q.last_poll = 0
    Q.net_work()
    Q.net_work()
    t = drawn_texts(Q)
    check(signed and Q.status_home() and "1 waiting for others \u00b7 Y shows" in t and "1 queued" in t,
          "signed, still queued for others: the status screen says so, and the Safe's row counts it")
    Q.handle("Y")
    check(not Q.status_home() and Q.browse == "list", "Y: the list")
    Q.handle("B")
    check(Q.status_home() and Q.state == "home", "B: back to the status screen")
    check(Q.recent[0]["n"] == 0, "and that signature is the newest in Recent")
    try:
        os.remove(Q.RECENT_FILE)
    except OSError:
        pass


def case_saver():
    """A quiet minute on the status screen: the screensaver, dimmed, turning over cards; any key
    wakes it (and does nothing else); a request for this key wakes it to the queue list."""
    import time
    chip()
    Q = fresh(url=None, safe=False, extra=TWO)
    SVC.info = {"address": SAFE, "nonce": 4, "threshold": 2, "version": "1.4.1", "owners": [Q.me, ALICE, BOB]}
    SVC.txs = []
    SVC.safes[ETH_SAFE] = {"info": {"address": ETH_SAFE, "nonce": 7, "threshold": 1, "version": "1.4.1", "owners": [Q.me, BOB]}, "txs": []}
    Q.net_work()
    Q.net_work()
    Q.state, Q.recent = "home", [{"n": 3, "safe": SAFE.lower(), "chain": CHAIN, "name": "Test Safe", "what": "Send 1 ETH", "t": time.time() - 300}]
    bl = []
    Q.d.backlight = lambda p: bl.append(p)
    now = Q.time.ticks_ms()             # the console's own clock (Clock: moves when told)
    Q.last_activity = Q.time.ticks_add(now, -(Q.SAVER_MS - 1000))
    check(Q.saver_tick(now, []) == [] and Q.state == "home", "59 quiet seconds: still home")
    Q.last_activity = Q.time.ticks_add(now, -Q.SAVER_MS)
    Q.saver_tick(now, [])
    check(Q.state == "saver" and bl[-1] == Q.SAVER_DIM, "a quiet minute: the screensaver, backlight dimmed")
    kinds = [k for k, _ in Q.saver_cards()]
    check(kinds == ["clock", "safe", "safe", "key", "recent"], "its cards: the time, each Safe, this key, the last approval (%s)" % kinds)
    texts = []
    for i in range(len(kinds)):
        Q.saver_card = i
        texts += drawn_texts(Q)
    check("Test Safe" in texts and "LAST APPROVAL" in texts and "you're an owner" in texts and "owner of 2 Safes" in texts and "next #4 \u00b7 nothing queued" in texts,
          "each card draws: a Safe (next #, owner), this key (owner of 2 Safes), the last approval")
    Q.saver_card = 0
    Q.saver_tick(Q.time.ticks_add(now, Q.SAVER_CARD_MS), [])
    check(Q.saver_card == 1, "every few seconds, the next card")
    left = Q.saver_tick(Q.time.ticks_add(now, Q.SAVER_CARD_MS + 10), ["A"])
    check(left == [] and Q.state == "home" and bl[-1] == 100, "a key wakes it, full brightness, and does nothing else")
    Q.last_activity = Q.time.ticks_add(now, -Q.SAVER_MS)
    Q.saver_tick(now, [])
    SVC.txs = [tx(Q, 4)]
    Q.WATCH[0]["need_info"] = True
    Q.last_poll = 0
    Q.net_work()
    Q.saver_tick(now, [])
    check(Q.state == "home" and not Q.status_home() and bl[-1] == 100, "asleep, and a request for this key arrives: awake, on the queue list")
    Q.last_activity = Q.time.ticks_add(now, -10 * Q.SAVER_MS)
    Q.saver_tick(now, [])
    check(Q.state == "home", "with a request waiting, never the screensaver")
    Q = fresh(url=None, safe=False, extra=TWO + "\nQUORUM_SAVER_S = 0")
    Q.state = "home"
    Q.last_activity = Q.time.ticks_add(Q.time.ticks_ms(), -3600000)
    Q.saver_tick(Q.time.ticks_ms(), [])
    check(Q.SAVER_MS == 0 and Q.state == "home", "QUORUM_SAVER_S = 0: no screensaver")


def case_release():
    """The release fingerprint (image.RELEASE, from build.py): its blockie on the screensaver's
    release card and on the Device screen, with its short name; without one, neither."""
    chip()
    Q = fresh(url=None, safe=False, extra=TWO)
    SVC.info = {"address": SAFE, "nonce": 0, "threshold": 2, "version": "1.4.1", "owners": [Q.me, ALICE, BOB]}
    SVC.txs = []
    SVC.safes[ETH_SAFE] = {"info": {"address": ETH_SAFE, "nonce": 7, "threshold": 1, "version": "1.4.1", "owners": [Q.me, BOB]}, "txs": []}
    Q.net_work()
    Q.net_work()
    Q.recent = []
    import image
    import blockies
    import fonts
    import quorum_ui as U
    drawn, texts = [], []
    real_draw, real_text = blockies.draw, fonts.text
    blockies.draw = lambda d, seed, x, y, scale, *a, **k: (drawn.append((seed, scale)), real_draw(d, seed, x, y, scale, *a, **k))
    fonts.text = lambda d, t, *a, **k: (texts.append(t), real_text(d, t, *a, **k))[1]
    try:
        check(Q.status_home(), "the status screen is home")
        U.draw(Q)
        check(image.SEED not in [x for x, _ in drawn] and not image.RELEASE and "release" not in [k for k, _ in Q.saver_cards()],
              "no build.py: no release blockie, no release card")
        image.RELEASE = "4c86c7541a45eb43f24c48c178409de889c5f86d467c886d444e9e30b9a00e0b"
        image.SEED, image.SHORT = "0x" + image.RELEASE, "4c86\u00b7c754"
        image.VERSION, image.BUILD = "2026.10.6", "abc1234"
        Q.state = "saver"
        Q.saver_card = [k for k, _ in Q.saver_cards()].index("release")
        drawn[:], texts[:] = [], []
        U.draw(Q)
        check((image.SEED, 6) in drawn and "Release 4c86\u00b7c754" in texts, "the screensaver's release card: its blockie, Release 4c86\u00b7c754")
        Q.state = "home"
        Q.handle("X")
        Q.net_err = None
        drawn[:], texts[:] = [], []
        U.draw(Q)
        check(Q.state == "device" and [sc for x, sc in drawn if x == image.SEED] == [2, 2], "Device: the blockie in the header and on the Release row")
        check("4c86\u00b7c754" in texts and "Release" in texts, "Device: the Release row names it 4c86\u00b7c754")
        Q.net_err, Q.net_ok = "OSError -1", False
        drawn[:], texts[:] = [], []
        U.draw(Q)
        check([sc for x, sc in drawn if x == image.SEED] == [2] and "Release" not in texts, "with a last error to show: the header blockie only")
    finally:
        blockies.draw, fonts.text = real_draw, real_text
        image.RELEASE = image.SEED = image.SHORT = image.VERSION = ""
        Q.handle("B")


def case_passkey():
    """The browser emulator's passkey as the key (emu/core/shims/passkey.py; a software passkey
    here, core/softpasskey.mjs): the same console and checks, the owner follows from its key, and
    the posted signature is the passkey's own WebAuthn assertion over the hash computed on screen,
    packed as a chip's and valid the way the Safe checks it."""
    import _emu
    import hashlib
    import quorum_cfg
    chip()
    _emu.passkey_use(True)
    try:
        Q = fresh(prod=False, expect=None)
        check(Q.sig.name == "passkey" and Q.state == "home", "the page picked a passkey: the console uses it, not the chip on the bus")
        x, y = Q.sig.pubkey()
        check(Q.me == webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"]), "its owner address follows from the passkey's key, as for a chip")
        check(any("passkey" in l.lower() for l in Q.chip_info()) and "browser" in " ".join(Q.chip_info()), "the signing screen names the passkey, and that the browser draws it")
        try:
            Q.sig.sign(b"\x00" * 32)
            check(False, "a passkey refuses a bare digest")
        except Exception:
            check(True, "a passkey refuses a bare digest")
        serve(Q, [tx(Q, 0)])
        e = Q.queue[0]
        check(sign(Q, e, 2100), "held 2.1 s: the passkey signed, and it was posted")
        url, body = SVC.posted[-1]
        b = bytes.fromhex(body["signature"][2:])
        data = b[65 + 32:]
        word = lambda i: int.from_bytes(data[i:i + 32], "big")
        ad = data[word(0) + 32:word(0) + 32 + word(word(0))]
        fields = data[word(32) + 32:word(32) + 32 + word(word(32))].decode()
        r, s_ = word(64), word(96)
        cdj = '{"type":"webauthn.get","challenge":"%s",%s}' % (webauthn.b64url(bytes.fromhex(e["mine"][2:])), fields)
        digest = hashlib.sha256(ad + hashlib.sha256(cdj.encode()).digest()).digest()
        check(b[12:32] == bytes.fromhex(Q.me[2:]) and e["h"] in url, "a contract signature from this key's owner, for that hash")
        check(p256.verify(x, y, digest, r, s_) and ad[32] & 0x04, "the passkey's assertion over the hash computed here verifies as the Safe checks it, with UV")
        check('"origin":"http://localhost:4242"' in fields, "the browser's own clientData fields ride along in the signature")
        n = len(SVC.posted)
        real = Q.sig.assertion
        Q.sig.assertion = lambda c: (_ for _ in ()).throw(Exception("NotAllowedError: the person cancelled"))
        Q.handle("A")           # off the result screen
        serve(Q, [tx(Q, 0, to=OTHER, data="0xdeadbeef")])
        check(not sign(Q, Q.queue[0], 3100) and len(SVC.posted) == n and not Q.result[0] and "cancelled" in " ".join(Q.result[2]),
              "a cancelled passkey prompt: Not signed, nothing posted, and the reason shown")
        Q.sig.assertion = real
    finally:
        _emu.passkey_use(False)


def case_release_approval():
    """The project Safe approving a Picoquorum release (release.py): a delegatecall to the pinned
    SignMessageLib, its release named in the origin note. The console reads it, shows the release
    and its fingerprint's blockie (and whether this console runs it), and signs it like any other
    transaction; a note that doesn't give the calldata's digest is refused."""
    import release
    import blockies
    import quorum_ui as U
    chip()
    Q = fresh()
    import image                # after fresh(), which imports it anew
    LIB = "0xd53cd0ab83d845ac265be939c57f53ad838012c9"
    fp, man = "4c86c7541a45eb43f24c48c178409de889c5f86d467c886d444e9e30b9a00e0b", "5f" * 32
    d = release.digest("2026.10.6", fp, man)
    data = "0x85a5affe" + "%064x" % 32 + "%064x" % 32 + "".join("%02x" % b for b in d)
    good = tx(Q, 0, to=LIB, data=data, op=1)
    good["origin"] = '{"pq":{"v":"2026.10.6","f":"%s","m":"%s"}}' % (fp, man)
    serve(Q, [good])
    e = Q.queue[0]
    check(not e["why"] and e["r"]["summary"] == "Approve release 2026.10.6", "an approval for release 2026.10.6: read, not refused")
    image.RELEASE = fp
    drawn, texts = [], []
    real_draw, real_text = blockies.draw, U.F.text
    blockies.draw = lambda dd, seed, x, y, scale, *a, **k: (drawn.append(seed), real_draw(dd, seed, x, y, scale, *a, **k))
    U.F.text = lambda dd, t, *a, **k: (texts.append(t), real_text(dd, t, *a, **k))[1]
    try:
        Q.open_entry(e)
        while Q.cur and Q.page < len(e["r"]["items"]) and e["r"]["items"][Q.page].get("title") != "RELEASE":
            Q.turn(1)
        U.draw_item(Q, 0)
        check(("0x" + fp) in drawn and "firmware 4c86\u00b7c754" in texts, "its page shows the release's firmware fingerprint and blockie")
        check("the release running here" in texts, "and that it is the release this console runs")
        image.RELEASE = "ab" * 32
        texts[:] = []
        U.draw_item(Q, 0)
        check("not the release running here" in texts, "on a console running another release, it says so")
    finally:
        blockies.draw, U.F.text = real_draw, real_text
        image.RELEASE = ""
    Q.handle("B")
    check(sign(Q, e, 3100), "held: the console signs the approval like any transaction")
    Q.handle("A")
    bad = tx(Q, 1, to=LIB, data=data, op=1)
    bad["origin"] = '{"pq":{"v":"2026.10.7","f":"%s","m":"%s"}}' % (fp, man)
    other = tx(Q, 2, to=LIB, data=data, op=1)       # its own hash: decodes are cached by safeTxHash
    serve(Q, [good, bad])
    eb = [x for x in Q.queue if x["n"] == 1][0]
    check(bool(eb["why"]) and "doesn't match" in eb["why"], "a note naming another release than the calldata's digest: refused")
    serve(Q, [good, other])
    eo = [x for x in Q.queue if x["n"] == 2][0]
    check(bool(eo["why"]) and "no Picoquorum release" in eo["why"], "a message with no release named: refused (it signs only releases)")


class TurningKnob:
    """knob.Knob as quorum.poll sees it: something turned, or not."""

    def __init__(self):
        self.moved = False

    def pending(self):
        return self.moved


def case_knob():
    """Build 1's knob: a turn that only moves the focus redraws its bands, not the screen; a poll
    waits until the keys are quiet, stops between its calls when the knob turns, and the turns
    that piled up meanwhile move the focus at most BACKLOG places."""
    Q = fresh()
    serve(Q, [])
    Q.net_work()
    Q.KNOB = True
    check(Q.status_home() and Q.state == "home", "nothing waits: the status home")
    bands = []
    real = Q.U.draw
    Q.U.draw = lambda q: bands.append(Q.d.y0)

    def tick(pressed=()):
        Q.keys.pressed = lambda: list(pressed)
        Q._busy = False
        Q.tick(None)

    Q.last_poll, Q.splash_until = Q.time.now, 0      # the boot's splash is over
    Q.dirty, Q.dirty_rows, Q.hsel, Q.hfoot = False, None, 0, None
    tick(["down"])
    check(Q.hfoot is not None and 0 < len(bands) < 4, "a turn on the status home: only the focus' bands are drawn (%d)" % len(bands))
    del bands[:]
    Q.say("hello")
    Q.dirty = False
    tick(["down"])
    check(len(bands) == Q.L.BANDS, "a turn while a message shows: the whole screen")
    Q.msg = ""
    Q.state = "device"
    Q.dirty = False
    del bands[:]
    tick(["down"])
    check(len(bands) == 1, "a turn on Device: only the footer's band")
    Q.state = "home"

    n = len(SVC.calls)
    Q.last_poll, Q.last_key = 0, Q.time.now
    tick()
    check(len(SVC.calls) == n, "a poll is due, but the knob turned just now: it waits")
    Q.time.now += Q.QUIET_MS
    tick()
    check(len(SVC.calls) > n, "the keys quiet for QUIET_MS: it polls")

    Q.keys.knob = TurningKnob()
    Q.keys.knob.moved = True
    SVC.txs = [tx(Q, 0)]
    n = len(SVC.calls)
    Q.WATCH[0]["need_info"] = True
    Q.last_poll = 0
    Q.net_work()
    got = [c[1] for c in SVC.calls[n:]]
    check(len(got) == 1 and "/multisig-transactions/" not in got[0] and not Q.queue and Q.last_poll == 0,
          "the knob turns during a poll: it stops after the call under way, the queue as it was, asked again next")
    Q.keys.knob.moved = False
    Q.net_work()
    check(len(Q.queue) == 1, "the knob still: the poll runs to the end")
    check(Q.backlog(["down"] * 6 + ["press"]) == ["down"] * 3 + ["press"], "turns piled up during a poll: at most BACKLOG of them")
    Q.U.draw = real

    Q.state, Q.hsel, Q.hfoot = "home", 0, None
    tick(["A"])
    check(Q.state == "home" and Q.msg == Q.SIGN_ONLY, "the Sign button on the status home: opens nothing, says it only signs")
    Q.msg = ""

    # What reaches the panel after a turn's few bands is what a whole frame would have put there.
    panel = bytearray(Q.L.W * Q.L.H * 2)

    def show():
        o = Q.d.y0 * Q.L.W * 2
        panel[o:o + len(Q.d.buffer)] = Q.d.buffer
    Q.d.show = show

    def same(what, k="down", skip=None):
        """skip: (y0, y1), rows that change by themselves between any two frames."""
        Q.last_poll, Q.dirty = Q.time.now, True
        tick()
        tick([k])
        partial = bytearray(panel)
        Q.dirty = True
        tick()
        whole = bytearray(panel)
        if skip:
            a, b = skip[0] * Q.L.W * 2, skip[1] * Q.L.W * 2
            partial[a:b] = whole[a:b] = bytes(b - a)
        check(whole == partial, what)

    Q.keys.knob = None
    SVC.txs = []
    Q.last_poll = 0
    Q.net_work()
    Q.state, Q.hsel, Q.hfoot = "home", 0, None
    same("the status home, off the Safe row onto the footer: the same pixels as a whole frame")
    same("the status home, along the footer: the same pixels")
    same("the status home, back along the footer: the same pixels", "up")
    same("the status home, back onto the Safe row: the same pixels", "up")
    Q.state, Q.dfoot = "device", "chip"
    same("Device, along the footer: the same pixels", skip=(172, 192))     # its Memory row
    Q.state = "home"
    SVC.txs = [tx(Q, 0), tx(Q, 1, to=BOB), tx(Q, 2)]
    Q.WATCH[0]["need_info"] = True
    Q.last_poll = 0
    Q.net_work()
    Q.sel, Q.foot = 0, None
    check(not Q.status_home(), "transactions waiting: the list")
    same("the list, row to row: the same pixels")
    Q.sel = len(Q.queue) - 1
    same("the list, off the last row onto the footer: the same pixels")
    Q.foot = None
    Q.open_entry(Q.queue[0])
    Q.act = 0
    same("a review, SIGN to REJECT: the same pixels")
    same("a review, REJECT back to SIGN: the same pixels", "up")
    while Q.unseen():
        Q.turn(1)
    Q.act = None
    Q.keys.down.add("A")
    tick(["A"])
    Q.keys.down.discard("A")
    check(Q.state == "hold" and Q.msg != Q.SIGN_ONLY, "the Sign button on a review: it signs (the hold begins)")


def case_three():
    """The Feather's three buttons (board "feather-s3", 240x135, quorum_ui_s with its rail). D0
    rejects with one press on any review page, even during the hold, and goes back elsewhere; D1
    moves on and, held (D1L), moves back; D2 opens, walks the pages not yet seen, and held signs:
    2 s, 3 s when a page is red. Run in a device of its own (main_three): board.py is read once.
    The same for PicoQuorumKey (main_pqk): the Feather's buttons and screen on other pins. And for
    the knob Feather (main_knob), where Boot is D0 and the knob's detents and push are D1, D1L, D2.
    And for console-rp (main_rp): its buttons under the screen, named in a footer, and every call
    to the service through the relay on UART1."""
    chip()
    Q = fresh(extra='BOARD = "%s"' % THREE_BOARD[0])
    if THREE_BOARD[0] == "feather-knob":
        import board
        check(board.DIAL and board.NAMES["D2"] == "push" and (board.SDA, board.SCL) == (42, 41),
              "the knob Feather: Boot and the knob as D0-D2, the key on 42/41")
    if THREE_BOARD[0] == "console-rp":
        import board
        check(Q.U.SLOTS and not Q.U.RAIL and board.KEYS == {"D0": 2, "D1": 3, "D2": 6} and not board.HIGH
              and (board.SDA, board.SCL, board.LINK) == (4, 5, (1, 20, 21)) and not board.RADIO and Q.NET.KIND == "link",
              "console-rp: D0 D1 D2 on 2/3/6 pressed low, the key on 4/5, a footer, no rail, no radio, the link on UART1")
    check(Q.L.BOARD == THREE_BOARD[0] and Q.THREE and (Q.L.W, Q.L.H) == (240, 135) and Q.U.__name__ == "quorum_ui_s" and Q.PRESS == "D2",
          THREE_BOARD[0] + ": three buttons, 240x135, the small screens' UI")
    good, red = tx(Q, 0), tx(Q, 1, to=OTHER, data="0xdeadbeef")
    refused = [tx(Q, 2, safe=OTHER), tx(Q, 3, tamper=True), tx(Q, 4, op=2), tx(Q, 5, to=OTHER, op=1, data="0x12345678")]
    serve(Q, [good, red] + refused)
    by = {e["n"]: e for e in Q.queue}

    def tick(*pressed):
        Q.keys.pressed = lambda: list(pressed)
        Q._busy, Q.last_poll, Q.splash_until = False, Q.time.now, 0
        Q.tick(None)

    def to_hold(e):
        """Open e and press D2 until the hold starts (each press first shows a page not yet
        seen). -> the presses it took, or None if it never started."""
        Q.open_entry(e)
        for n in range(1, 40):
            Q.three("D2")
            if Q.state == "hold":
                return n
        return None

    def sign3(e, hold_ms):
        """D2 to the hold, held hold_ms. -> did a confirmation get posted?"""
        n = len(SVC.posted)
        if to_hold(e) is None:
            return False
        Q.keys.down.add("D2")
        Q.time.now += hold_ms
        Q.hold_tick()
        Q.keys.down.discard("D2")
        if Q.state == "hold":
            Q.hold_tick()
        return len(SVC.posted) > n

    for n in (2, 3, 4, 5):
        check(by[n]["why"] and not sign3(by[n], 5000) and Q.state == "review",
              "#%d refused: D2 never starts a hold, whatever is held" % n)
    Q.open_entry(by[0])
    pages = len(Q.pages)
    took = to_hold(by[0])
    check(pages > 2 and took == pages, "D2 before every page is seen shows the next unseen one: %d presses, then the hold" % took)
    Q.state = "review"
    check(not sign3(by[0], 1999), "held 1.999 s: nothing signed")
    check(sign3(by[0], 2000) and Q.state == "result", "held 2 s: signed and posted")
    check(not sign3(by[1], 2999), "red, held 2.999 s: nothing signed")
    check(sign3(by[1], 3000), "red, held 3 s: signed")

    serve(Q, [tx(Q, 0), tx(Q, 1, to=OTHER, data="0xdeadbeef")])
    e, r = Q.queue
    n0 = len(SVC.posted)
    for p in range(len(Q.pages) if Q.open_entry(e) is None else 0):
        Q.open_entry(e)
        while Q.page < p:
            Q.three("D1")
        Q.declined.discard(e["h"])
        Q.three("D0")
        check(Q.state == "home" and e["h"] in Q.declined and len(SVC.posted) == n0,
              "D0 on page %d of %d: rejected with one press, nothing posted" % (p + 1, len(Q.pages)))
    Q.declined.discard(r["h"])
    Q.open_entry(r)
    Q.three("D1")
    Q.three("D0")
    check(Q.state == "home" and r["h"] in Q.declined, "D0 on a red transaction's page: rejected")
    Q.declined.discard(e["h"])
    to_hold(e)
    Q.keys.down.add("D2")
    Q.time.now += 1000
    Q.hold_tick()
    Q.three("D0")
    Q.keys.down.discard("D2")
    check(Q.state == "home" and e["h"] in Q.declined and len(SVC.posted) == n0, "D0 during the hold: rejected, nothing signed")

    Q.declined.discard(e["h"])
    Q.open_entry(e)
    Q.three("D1")
    Q.three("D1")
    Q.three("D1L")
    check(Q.state == "review" and Q.page == 1, "D1 twice then D1 held: back one page")
    Q.three("D1L")
    Q.three("D1L")
    check(Q.state == "home" and e["h"] not in Q.declined, "D1 held on the first page: out, not rejected")
    Q.open_entry(e)
    while Q.page < len(Q.pages) - 1:
        Q.three("D1")
    Q.three("D1")
    check(Q.state == "review" and Q.page == 0, "D1 on the last page: round to the first")

    # Home: four tabs, D0 the next one, D1 the next row and round (held: up), D2 what the bar says
    Q.state, Q.sel, Q.tab, Q.osel, Q.dsel = "home", 0, 0, 0, 0
    tick("D1")
    check(Q.sel == 1 and Q.tab == 0, "home: the Queue tab; D1 moves down it (through tick)")
    tick("D1")
    check(Q.sel == 0, "D1 on the last row: round to the first")
    tick("D1L")
    check(Q.sel == 1, "D1 held: up, round to the last")
    tick("D2")
    check(Q.state == "review" and Q.cur is Q.queue[1], "D2 on the Queue tab: the one in focus opens")
    Q.three("D1L")
    check(Q.state == "home" and Q.tab == 0, "out of it without rejecting: the Queue tab again")
    tick("D0")
    check(Q.state == "home" and Q.tab == 1, "D0: the next tab, Owners")
    tick("D1")
    tick("D2")
    check(Q.state == "who" and Q.who == Q.owners()[1], "Owners: D1 then D2 shows that owner in full")
    tick("D0")
    check(Q.state == "home" and Q.tab == 1, "D0: back on the Owners tab")
    tick("D0")
    tick("D0")
    check(Q.tab == 3, "D0, D0: Key, then Device")
    tick("D2")
    check(Q.state == "chip" and Q.chip_back == "home", "Device: D2 on Chip opens the chip pages")
    tick("D0")
    check(Q.state == "home" and Q.tab == 3, "D0: back on the Device tab")
    for _ in range(len(Q.DTAB) - 1):
        tick("D1")
    tick("D2")
    check(Q.state == "device", "Device: D1 to the last row, D2: About, the device's facts")
    tick("D0")
    tick("D0")
    check(Q.state == "home" and Q.tab == 0, "D0: back on the tab; D0 again: round to Queue")
    Q.open_entry(e)
    tick("D2")
    check(Q.state == "review" and 1 in Q.seen, "a review through tick: D2 shows the next page")

    import fonts

    def drawn():
        out, real = [], fonts.text
        fonts.text = lambda d, t, x, y, font, *a, **k: (out.append((t, x, y, font)), real(d, t, x, y, font, *a, **k))[1]
        try:
            Q.U.draw(Q)
        finally:
            fonts.text = real
        return out

    rail, foot = Q.U.RAIL, Q.U.FOOT if Q.U.SLOTS else Q.L.H

    def edge(x, y):
        """Where the buttons are named: left of the Feather's rail, or in console-rp's footer."""
        return x < rail or y >= foot

    Q.msg = ""
    Q.open_entry(e)
    t = drawn()
    left = [s for s, x, y, f in t if edge(x, y)]
    check(left == ["Reject", "Next", "See %d" % len(Q.unseen())], "the rail on a review: Reject, Next, See %d" % len(Q.unseen()))
    while Q.unseen():
        Q.three("D1")
    check([s for s, x, y, f in drawn() if edge(x, y)] == ["Reject", "Next", "Sign"], "every page seen: Sign")
    ok = True
    for p in range(len(Q.pages)):
        Q.page = p
        for s, x, y, f in drawn():
            if y + fonts.height(f) > Q.L.H + 3 or (edge(x, y) and s not in ("Reject", "Next", "Sign")):
                ok = False
                print("      page %d: %r at (%d, %d) in %s" % (p + 1, s, x, y, f))
    check(ok, "every page of a review fits 240x135, and only the buttons' names are drawn by them")
    Q.state, Q.tab = "home", 0
    check([s for s, x, y, f in drawn() if edge(x, y)] == ["Tab", "Next", "Open"], "the rail on home: Tab, Next, Open")
    ok = True
    for Q.tab in range(len(Q.TABS)):
        t = drawn()
        if not any(s.startswith("Queue") for s, x, y, f in t) or not any(s == "Device" for s, x, y, f in t):
            ok = False
        for s, x, y, f in t:
            if y + fonts.height(f) > Q.L.H + 3 or x + fonts.width(s, f) > Q.L.W + 1 or (edge(x, y) and s not in ("Tab", "Next", "Open")):
                ok = False
                print("      tab %s: %r at (%d, %d) in %s" % (Q.TABS[Q.tab], s, x, y, f))
    Q.tab = 0
    check(ok, "each tab fits 240x135, the tabs along its top, only the rail left of it")
    Q.state = "pinfail"
    t = [s for s, x, y, f in drawn() if edge(x, y)]
    check(t == ["Check"], "the rail on Not pinned: Check (%r)" % t)

    # The Key screen (docs/ONBOARDING.md): this key's owner address as a QR code, then in full
    def fits(where):
        bad = [(s, x, y) for s, x, y, f in drawn() if y + fonts.height(f) > Q.L.H + 3 or x + fonts.width(s, f) > Q.L.W
               or (edge(x, y) and s not in ("Back", "Full", "Code", "Next", "Open"))]
        if bad:
            print("      %s: %r" % (where, bad[:3]))
        return not bad
    import txservice
    Q.state, Q.tab = "home", Q.TABS.index("key")
    t = " ".join(s for s, x, y, f in drawn())
    check(Q.fingerprint() in t and "an owner" in t, "the Key tab: this key's fingerprint, and that it is an owner")
    tick("D2")
    t = drawn()
    link = "https://picoquorum.app/app/#/k/" + Q.compressed()
    check(Q.state == "key" and Q.kpage == 0 and Q.U._qr[0] == link and len(link) == 97 and Q.U._qr[1] == 37
          and Q.compressed()[2:] == Q.qx[2:] and int(Q.compressed()[:2]) == 2 + int(Q.qy, 16) % 2,
          "D2 on Key: the app's set-up link (the compressed key), as a 37-module QR code")
    t = " ".join(s for s, x, y, f in t)
    check(Q.me[:6] in t and Q.me[-4:] in t and "not a wallet." in t, "beside it: the short owner address, and a signer, not a wallet")
    check([s for s, x, y, f in drawn() if edge(x, y)] == ["Back", "Full"] and fits("key code"), "the code page: rail Back, Full; it fits")
    tick("D1")
    t = " ".join(s for s, x, y, f in drawn())
    check(Q.kpage == 1 and Q.me[2:6] in t and "not a wallet" in t and fits("key full"),
          "D1: the address in full, and that it is a signer, not a wallet")
    tick("D0")
    check(Q.state == "home" and Q.tab == Q.TABS.index("key"), "D0 on the code: back on the Key tab")
    owners, queue = Q.owners, Q.queue
    Q.owners = lambda w=None: [OTHER]
    Q.queue, Q.tab = [], 0
    t = " ".join(s for s, x, y, f in drawn())
    Q.owners, Q.queue = owners, queue
    check("Not an owner yet" in t, "a Safe that doesn't list this key: Not an owner yet")

    # Blockies: each address page draws its address's picture, a token's amount its contract's, and
    # approvals and Owners one for each owner; every one on the screen and clear of the text
    import blockies
    a1, a2, a3 = "0x70997970c51812dc3a010c7d01b50e0d17dc79c8", "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc", \
        "0x90f79bf6eb2c4f870365e785982e1f101e93b906"
    usdc = "0x036cbd53842c5426634e7929541ec2318f3dcf7e"        # Base Sepolia's, in quorum_cfg's tokens

    def word(v):
        return "%064x" % (int(v, 16) if isinstance(v, str) else v)

    def packed(to, value, data=""):
        return "00" + to[2:] + word(value) + word(len(data) // 2) + data

    calls = packed(a1, 10**15) + packed(usdc, 0, "a9059cbb" + word(a2) + word(5 * 10**6))
    n = len(calls) // 2
    calls += "00" * (-n % 32)
    serve(Q, [tx(Q, 0, to=a1, value=3 * 10**15), tx(Q, 1, to=usdc, data="0xa9059cbb" + word(a2) + word(25 * 10**6)),
              tx(Q, 2, to=SAFE, data="0xe318b52b" + word(1) + word(BOB) + word(a3)),
              tx(Q, 3, to=MULTISEND, op=1, data="0x8d80ff0a" + word(32) + word(n) + calls)], owners=[Q.me, a1, ALICE, BOB])

    def pictures():
        """-> (seed, x, y, px) of each blockie one draw makes, and its texts"""
        out, real = [], blockies.draw
        blockies.draw = lambda d, seed, x, y, s, *a, **k: (out.append((seed, x, y, 8 * s)), real(d, seed, x, y, s, *a, **k))[1]
        try:
            t = drawn()
        finally:
            blockies.draw = real
        return out, t

    def clear(pics, t):
        bad = [p for p in pics if p[1] < rail or p[1] + p[3] > Q.L.W or p[2] < Q.U.HEAD or p[2] + p[3] > foot]
        for s, x, y, f in t:
            bad += [(s, p) for p in pics if x < p[1] + p[3] and p[1] < x + fonts.width(s, f) and y < p[2] + p[3] and p[2] < y + fonts.height(f)]
        return bad

    Q.state, Q.msg = "review", ""
    seen, ok = [], True
    for e in Q.queue:
        Q.open_entry(e)
        for p, (kind, i) in enumerate(Q.pages):
            Q.page = p
            pics, t = pictures()
            it = e["r"]["items"][i] if kind in ("item", "frm", "to") else {}
            amount = kind == "item" and it.get("amount") and not it.get("text") and it.get("contract")
            want = it[kind].lower() if kind in ("frm", "to") else (it["contract"] if amount else None)
            if want:
                seen.append((e["r"]["items"][i]["title"], kind))
            bad = clear(pics, t)
            if want and want not in [s for s, x, y, px in pics] or bad:
                ok = False
                print("      #%d page %d %s: %r %r" % (e["n"], p + 1, kind, [s for s, x, y, px in pics], bad[:2]))
    check(ok and ("SEND USDC", "item") in seen and ("SWAP OWNER", "frm") in seen and ("SWAP OWNER", "to") in seen
          and seen.count(("SEND ETH", "to")) == 2, "a blockie on every address page (to, replaces, new owner, each call in a "
          "batch) and beside a token's amount, clear of the text (%d)" % len(seen))
    Q.page = [k for k, i in Q.pages].index("approvals")
    pics, t = pictures()
    want = [a.lower() for a in Q.owners()[:4]]
    check([s for s, x, y, px in pics] == want and not clear(pics, t), "approvals: each owner's blockie beside it")
    Q.state, Q.opage = "owners", 0
    pics, t = pictures()
    check([s for s, x, y, px in pics] == want and not clear(pics, t), "Owners: each owner's blockie")

    Q = fresh(safe=False, extra='BOARD = "%s"' % THREE_BOARD[0])
    t = " ".join(s for s, x, y, f in drawn())
    check(Q.state == "unconfigured" and Q.key_ready() and "Your key is ready" in t and fits("ready"),
          "no Safe yet: Your key is ready")
    Q.three("D2")
    check(Q.state == "key", "D2 there: the key's code")
    Q.three("D0")
    check(Q.state == "unconfigured", "D0: back to the ready screen")
    Q = fresh(safe=False, expect={"serial": "0123000000000000ee", "slot": 0, "owner": OTHER, "locked": True}, extra='BOARD = "%s"' % THREE_BOARD[0])
    Q.three("D2")
    check(Q.state == "unconfigured" and not Q.key_ready() and "No Safe" in " ".join(s for s, x, y, f in drawn()),
          "pinned to another chip, no Safe: no code for this one, D2 does nothing")


def case_link():
    """The USB link (usblink.py, docs/USB-LINK.md): what a computer may read and ask, and that
    nothing is written, and the chip never asked anything, until the person accepts on the screen.
    On the Waveshare (Y refuses, the joystick pages, A held accepts) and on three buttons (D0, D1,
    D2): main() and main_three() both run it."""
    import usblink
    import fonts
    three = THREE_BOARD[0] if LINK_THREE[0] else None
    NO, PAGE, YES = ("D0", "D1", "D2") if three else ("Y", "down", "A")
    for f in ("safes.json", "maint"):
        try:
            os.remove(f)
        except OSError:
            pass
    chip()
    extra = 'WIFI_PASS = "hunter2hunter2"' + ('\nBOARD = "%s"' % three if three else "")
    Q = fresh(extra=extra)
    sent = []
    real_send = usblink.send
    usblink.send = lambda d: sent.append(d)
    usblink.host, usblink.mode, usblink.open_ask, usblink.time = Q, "console", None, Q.time
    calls = []

    class Spy:
        def __init__(self, real):
            self.real = real

        def __getattr__(self, n):
            v = getattr(self.real, n)
            if callable(v):             # a method: something asked of the chip (a label, its name, is not)
                calls.append(n)
            return v
    real_sig, Q.sig = Q.sig, Spy(Q.sig)

    def req(d):
        del sent[:]
        usblink.handle(d if isinstance(d, str) else json.dumps(d))
        return sent[-1] if sent else None

    def tick(*pressed):
        Q.keys.pressed = lambda: list(pressed)
        Q._busy, Q.last_poll, Q.splash_until = False, Q.time.now, 0
        Q.tick(None)

    def hold(k, ms):
        Q.keys.down.add(k)
        Q.time.now += ms
        tick()
        Q.keys.down.discard(k)

    def on_screen():
        out, real = [], fonts.text
        fonts.text = lambda d, t, *a, **k: (out.append(t), real(d, t, *a, **k))[1]
        try:
            Q.U.draw(Q)
        finally:
            fonts.text = real
        return " ".join(out)

    r = req({"id": 1, "op": "hello"})
    check(r["ok"] and r["id"] == 1 and r["proto"] == 1 and r["mode"] == "console" and r["image"] == "console", "hello: protocol, mode and image")
    r = req({"id": 2, "op": "status"})
    s = json.dumps(r)
    check(r["ok"] and r["serial"] == SERIAL and r["owner"] == Q.me and r["pinned"] and r["key"][2:] == Q.qx[2:]
          and r["safes"][0]["address"] == SAFE.lower() and r["safesFrom"] == "secrets.py", "status: the chip, the key, the pin and the Safes")
    check("hunter2" not in s and "test-key" not in s and r["wifi"]["saved"] == ["emulator"], "status: network names, never a password or the API key")
    check(req("not json")["ok"] is False and req("[1]")["ok"] is False and req({"op": "hello"})["why"] == "no id"
          and req({"id": 3, "op": "sign", "hash": "0x" + "11" * 32})["why"] == "unknown op", "garbage, no id and a sign request: refused")
    serve(Q, [tx(Q, 0)])
    Q.open_entry(Q.queue[0])
    r = req({"id": 9, "op": "wifi", "ssid": "Cafe", "pass": "12345678"})
    check(r["ok"] is False and r["why"].startswith("busy") and Q.state == "review" and not usblink.open_ask, "a review is never interrupted")
    Q.state, Q.cur, Q.queue = "home", None, []
    a = {"chainId": CHAIN, "address": OTHER, "name": "New"}
    bad = [({"id": 4, "op": "safes", "safes": [a] * 5}, "at most"),
           ({"id": 4, "op": "safes", "safes": [dict(a, chainId=31337)]}, "no service"),
           ({"id": 4, "op": "safes", "safes": [dict(a, url="http://evil")]}, "nothing else"),
           ({"id": 4, "op": "safes", "safes": [dict(a, address="0x12")]}, "bad address"),
           ({"id": 4, "op": "safes", "safes": [a, a]}, "twice"),
           ({"id": 4, "op": "safes", "safes": []}, "one or more"),
           ({"id": 4, "op": "safes", "safes": [dict(a, name="\n" * 3)]}, "plain"),
           ({"id": 4, "op": "wifi", "ssid": "home", "pass": "short"}, "at least 8")]
    for m, why in bad:
        r = req(m)
        check(r and r["ok"] is False and why in r["why"] and not usblink.open_ask and Q.state == "home", "refused before the screen: " + why)

    r = req({"id": 10, "op": "safes", "safes": [a]})
    check(r is None and usblink.open_ask and Q.state == "home", "a good ask: no answer yet")
    tick()
    check(Q.state == "ask" and len(Q.ask["pages"]) == 2 and "New" in on_screen(), "the next tick puts it on the screen: the Safe, then what changes")
    check(req({"id": 11, "op": "wifi", "ssid": "x", "pass": "12345678"})["why"].startswith("busy"), "a second ask meanwhile: busy")
    tick(YES)
    check(Q.ahold is None and Q.apage == 1, "the accept key first shows the page not yet seen")
    tick(YES)
    Q.keys.down.add(YES)
    Q.time.now += 1000
    tick()
    Q.keys.down.discard(YES)
    tick()
    check(Q.state == "ask" and Q.ahold is None and "safes.json" not in os.listdir(), "let go after 1 s: nothing saved")
    tick(NO)
    check(Q.state == "home" and sent[-1]["id"] == 10 and sent[-1]["ok"] is False and "refused" in sent[-1]["why"]
          and "safes.json" not in os.listdir(), "%s refuses with one press: answered, nothing saved" % NO)

    req({"id": 12, "op": "safes", "safes": [a, {"chainId": 8453, "address": ALICE, "name": "Base one"}]})
    tick()
    tick(PAGE)
    tick(PAGE)
    tick(YES)
    hold(YES, Q.HOLD_MS)
    saved = json.load(open("safes.json"))["safes"] if "safes.json" in os.listdir() else None
    check(sent[-1]["id"] == 12 and sent[-1]["ok"] is True and saved and [x["address"] for x in saved] == [OTHER, ALICE]
          and Q.reset_at and Q.state == "home", "every page seen, held %d s: safes.json written, answered, a restart due" % (Q.HOLD_MS // 1000))
    Q.reset_at = 0
    Q.sig = real_sig
    Q = fresh(extra=extra, keep=True)
    check(Q.SAFES_FROM == "safes.json" and [w["addr"] for w in Q.WATCH] == [OTHER, ALICE] and not any("url" in w["safe"] for w in Q.WATCH),
          "after the restart: the console watches safes.json's Safes, ahead of secrets.py")
    usblink.host, usblink.time = Q, Q.time
    real_sig, Q.sig = Q.sig, Spy(Q.sig)

    req({"id": 13, "op": "maint"})
    tick()
    tick(YES)
    hold(YES, Q.HOLD_MS)
    check("maint" not in os.listdir() and Q.state == "ask", "maint is red: %d s is not enough" % (Q.HOLD_MS // 1000))
    tick(YES)
    hold(YES, Q.HOLD_RED_MS)
    check("maint" in os.listdir() and sent[-1]["id"] == 13 and sent[-1]["ok"], "held %d s: the maint file, for the restart into maintenance" % (Q.HOLD_RED_MS // 1000))
    os.remove("maint")
    Q.reset_at = 0

    req({"id": 14, "op": "wifi", "ssid": "Cafe", "pass": "12345678"})
    tick()
    Q.time.now += usblink.ASK_S * 1000 + 1
    tick()
    check(Q.state == "home" and sent[-1]["id"] == 14 and not sent[-1]["ok"] and "in time" in sent[-1]["why"], "nobody there: refused after %d s" % usblink.ASK_S)
    req({"id": 15, "op": "wifi", "ssid": "Cafe", "pass": "12345678"})
    tick()
    req({"id": 16, "op": "cancel"})
    tick()
    check(Q.state == "home" and any(x.get("id") == 15 and not x["ok"] and "cancelled" in x["why"] for x in sent), "cancel takes it off the screen")

    check(not calls, "the link asked the chip nothing" + (": %s" % calls if calls else ""))
    Q.sig = real_sig
    usblink.send = real_send

    # On the S3's own USB one long write loses its front (usblink.send): an answer goes out in
    # writes of at most PIECE bytes, which together are the whole line.
    pieces = []

    class _Sys:
        class stdout:
            @staticmethod
            def write(t):
                pieces.append(t)
    real_sys, usblink.sys = usblink.sys, _Sys
    usblink.send({"id": 1, "ok": True, "pad": "x" * 600})
    usblink.sys = real_sys
    line = "".join(pieces)
    check(len(pieces) > 9 and all(len(p) <= usblink.PIECE for p in pieces) and line.startswith('{"pq":1,') and line.endswith("\n")
          and json.loads(line)["pad"] == "x" * 600, "a long answer goes out in writes of %d bytes at most, and is whole" % usblink.PIECE)
    import time
    usblink.time, usblink.host, usblink.open_ask = time, None, None
    for f in ("safes.json", "maint"):
        try:
            os.remove(f)
        except OSError:
            pass


def case_setup_link():
    """The link during Wi-Fi setup (a new board's first screen): status names the hotspot and the
    saved networks, never a password; the one ask is a network, joined only after the choose key is
    held 2 s; Y refuses. Nothing else may be asked."""
    import usblink
    import wificfg
    import wifisetup as WS
    sent, joined = [], []
    real_send, real_join = usblink.send, WS.join
    usblink.send = lambda d: sent.append(d)
    WS.join = lambda ssid, pw, origin: joined.append((ssid, pw, origin))
    clock = Clock()
    WS.time, usblink.time = clock, clock
    keys = Keys()
    WS._keys, WS.ap_ssid, WS.view, WS._link = keys, "Picoquorum-TEST", "qr", usblink
    WS._draw = lambda: None
    usblink.host, usblink.mode, usblink.open_ask = WS, "setup", None
    wificfg.save("home", "a-secret-pass")

    def req(d):
        del sent[:]
        usblink.handle(json.dumps(d))
        return sent[-1] if sent else None
    r = req({"id": 1, "op": "status"})
    check(r["mode"] == "setup" and r["hotspot"] == "Picoquorum-TEST" and r["wifi"]["saved"] == ["home"] and "a-secret" not in json.dumps(r),
          "setup: status names the hotspot and saved networks, never a password")
    check(req({"id": 2, "op": "safes", "safes": [{"chainId": CHAIN, "address": OTHER, "name": "x"}]})["why"].startswith("not here"),
          "setup: only a network may be asked")
    r = req({"id": 3, "op": "wifi", "ssid": "Cafe", "pass": "12345678"})
    check(r is None and WS.view == "usb" and WS.usb["ssid"] == "Cafe", "a network ask: on the screen, no answer yet")
    WS._key("Y")
    check(WS.view == "qr" and sent[-1]["id"] == 3 and not sent[-1]["ok"] and not joined, "Y refuses: back to the QR, nothing joined")
    req({"id": 4, "op": "wifi", "ssid": "Cafe", "pass": "12345678"})
    WS._key("A")
    keys.down.add("A")
    clock.now += 1000
    WS._usb_tick()
    check(not joined and WS.view == "usb", "held 1 s: not yet")
    clock.now += 1000
    WS._usb_tick()
    keys.down.discard("A")
    check(joined == [("Cafe", "12345678", "qr")] and sent[-1]["id"] == 4 and sent[-1]["ok"], "held 2 s: it joins, and answers")
    usblink.send, WS.join = real_send, real_join
    import time
    WS.time, usblink.time, usblink.host, usblink.open_ask, WS._link = time, time, None, None, None
    wificfg.forget()


def case_practice():
    """The ceremony as practice (practice.py): from the unconfigured screen when the chip has no key,
    and from Device. Its ten steps, the arm and the holds on this board's buttons, through the
    console's own tick, and nothing written: a spy on the virtual chip sees only Read and Info, its
    state is the same after, the signer's own arm stays off with ALLOW_* True, and a USB ask waits.
    main() runs it on the Waveshare, main_three() on three buttons."""
    import atecc_sim
    three = THREE_BOARD[0] if LINK_THREE[0] else None
    dial = three == "feather-knob"
    atecc_sim.wipe("608c")
    for f in os.listdir():
        if f.startswith("snapshot-"):
            os.remove(f)
    Q = fresh(safe=False, expect=None, url=None, extra='BOARD = "%s"' % three if three else "")
    if three:
        DO, ARM, BACK = "D2", (("D0",) if dial else ("D0", "D1")), ("D1L" if dial else "D0")
    else:
        DO, ARM, BACK = "A", ("B", "Y"), "Y"
    want = {"model": "ATECC608C", "keySealed": False, "configLocked": False, "dataLocked": False}
    check(Q.state == "unconfigured" and not Q.me and Q.facts == want and Q.link_status()["chip"] == want,
          "a factory 608C: unconfigured, no key, and the chip's model and locks in the link's status")

    def tick(*pressed):
        Q.keys.pressed = lambda: list(pressed)
        Q._busy, Q.last_poll, Q.splash_until = False, Q.time.now, 0
        Q.tick(None)

    def hold(names, ms):
        Q.keys.down = set(names)
        for _ in range(ms // 100):
            Q.time.now += 100
            tick()
        Q.keys.down = set()
        tick()

    c = atecc_sim.chip()
    before = (bytes(c.cfg), dict(c.keys), list(c.counters), bytes(c.otp), sorted(c.data))
    ops = []
    real = atecc_sim.Chip.execute

    def spy(self, op, p1, p2, data):
        ops.append(op)
        return real(self, op, p1, p2, data)
    atecc_sim.Chip.execute = spy
    drawn = []
    real_text = Q.d.text

    def text(t, x, y, col):
        drawn.append(t)
        return real_text(t, x, y, col)
    Q.d.text = text
    try:
        tick(DO)
        check(Q.state == "practice" and Q.prac_back == "unconfigured", "no key: %s opens the practice" % DO)
        import practice, ceremony_ui
        mods = [practice, ceremony_ui]
        if three:
            import setup_s
            mods.append(setup_s)
        for m in mods:
            m.time = Q.time
        P = Q.prac
        tick()
        check(any("Practice: writes nothing" in t for t in drawn), "every step says: practice, writes nothing")
        seen = []
        for st in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"):
            if st == "C3":
                hold([DO], 3500)
                check(P.c.step() == "C3" and P.result is None, "C3 not armed: %s held does nothing" % DO)
                hold(ARM, 3200)
                check(P.armed() >= 55 and Q.S.armed() == 0, "the arm (%s 3 s): the practice's own clock; the signer's stays off" % "+".join(ARM))
            if st in ("C3", "C4", "C6", "C9"):
                hold([DO], 3100)
            else:
                tick(DO)
            seen.append(P.result[:2] if P.result else (P.c.step(), None))
            tick(DO)
            tick()
        check(seen == [(s, True) for s in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10")],
              "C1-C10 walked, each with its own result (%s)" % seen)
        tick(BACK)
        check(Q.state == "unconfigured" and Q.prac is None, "back: where it came from")
        if three:
            Q.state, Q.tab, Q.dsel = "home", Q.TABS.index("device"), 0
            for _ in range(Q.DTAB.index("practice")):      # its row: no Wi-Fi row on console-rp
                tick("D1")
        else:
            Q.state, Q.dfoot = "device", "chip"
        tick("D2" if three else "X")
        back = "home" if three else "device"
        check(Q.state == "practice" and Q.prac_back == back,
              "%s: %s opens the practice" % ("the Device tab" if three else "Device", "D1 to it, D2" if three else "X"))
        check(Q.link_ask("wifi", {"ssid": "x", "pass": ""}) and Q.incoming is None, "a USB ask waits while it is open")
        tick(BACK)
        check(Q.state == back, "back: " + ("the Device tab" if three else "Device"))
    finally:
        atecc_sim.Chip.execute = real
        Q.d.text = real_text
    c = atecc_sim.chip()
    check(ops and all(op in (atecc_sim.OP_READ, atecc_sim.OP_INFO) for op in ops),
          "the chip was asked only Read and Info (%d commands)" % len(ops))
    check((bytes(c.cfg), dict(c.keys), list(c.counters), bytes(c.otp), sorted(c.data)) == before
          and not any(f.startswith("snapshot-") for f in os.listdir()),
          "the chip is as it was: config, keys, counters, OTP and data; no snapshot saved")
    check(Q.S.armed() == 0 and Q.S._armed_until is None, "the signer was never armed")


def case_relay():
    """console-rp's way out (link.py): every call to Safe's service goes as a line on UART1 to the
    computer, which relays it to a pinned service and adds its own API key. What comes back is
    untrusted, as the service is: each hostile answer ends refused or dropped, never signed, and
    the console goes on. Nothing goes out but to a pinned service, and never the API key."""
    import usblink
    chip()
    relay = Relay()
    Q = fresh(relay=relay)
    import link                         # fresh's own, imported anew
    import qlog
    base = "https://api.safe.global/tx-service/basesep"
    check(Q.NET is link and Q.VIA is link and Q.svc.link and Q.svc.api_key is None and Q.svc.headers == {} and Q.svc.tls == "relay"
          and link.up, "the console's way out is the link: no API key, no headers, no TLS here; the relay said hi at start")
    check("network" not in sys.modules and "net" not in sys.modules and "vhttp" not in sys.modules and "wifisetup" not in sys.modules,
          "no network, net, vhttp or wifisetup module was imported")
    good, red = tx(Q, 0), tx(Q, 1, to=OTHER, data="0xdeadbeef")
    serve(Q, [good, red])
    reqs = relay.sent("req")
    check(len(Q.queue) == 2 and Q.net_ok and len(reqs) >= 2 and all(r["url"].startswith(base + "/api/") and r["m"] == "GET" for r in reqs)
          and any("/safes/" in r["url"] for r in reqs) and any("/multisig-transactions/" in r["url"] for r in reqs),
          "polled through the relay: the Safe and its queue, GETs under the pinned base only")

    # Signing: the confirmation is a POST through the relay, with the signature and nothing else
    usblink.PORT, usblink.host, usblink.mode, usblink.time = link, Q, "console", Q.time
    by = {e["n"]: e for e in Q.queue}
    Q.open_entry(by[0])
    for _ in range(40):
        Q.three("D2")
        if Q.state == "hold":
            break
    Q.keys.down.add("D2")
    Q.time.now += 2000
    Q.hold_tick()
    Q.keys.down.discard("D2")
    if Q.state == "hold":
        Q.hold_tick()
    post = [r for r in relay.sent("req") if r["m"] == "POST"]
    check(len(SVC.posted) == 1 and len(post) == 1 and post[0]["url"] == base + "/api/v1/multisig-transactions/%s/confirmations/" % by[0]["h"]
          and list(json.loads(post[0]["body"])) == ["signature"], "signed with D2 held: one POST through the relay, the signature only")
    every = "\n".join(relay.wrote)
    check("test-key" not in every and "Authorization" not in every and "Bearer" not in every,
          "secrets.py's API key never goes down the link: the relay adds its own")
    logs = relay.sent("log")
    check(any("confirmed" in m["m"] or "signed" in m["m"] for m in logs) and all(len(m["m"]) <= link.LOG_LEN for m in logs),
          "the log's lines go to the computer too, %d so far, each at most %d characters" % (len(logs), link.LOG_LEN))

    def poll_with(*faults):
        """One poll, the relay doing faults to the next answers. -> the requests it saw."""
        n = len(relay.reqs)
        relay.faults = list(faults)
        relay.hi()
        Q.last_poll = 0
        Q.WATCH[0]["need_info"] = True
        Q.net_work()
        relay.faults = []
        return relay.reqs[n:]

    def stats():
        return dict(link._stats)

    # Garbage, NUL, bytes that aren't UTF-8, JSON that isn't ours: each dropped and counted
    s0 = stats()
    for junk in (b"\x00\x00\x00", b"\xff\xfe\x80{", b"hello there", b"[1, 2, 3]", b'{"t":"zzz"}', b"{not json", b'"a string"', b"\r"):
        relay.raw(junk)
    serve(Q, [good, red])
    check(stats()["garbage"] - s0["garbage"] == 7 and len(Q.queue) == 2 and Q.net_ok,
          "garbage, NULs, non-UTF-8 and foreign JSON: dropped and counted, the poll still good")

    # A line longer than the buffer: dropped to its newline, the next line read whole
    s0 = stats()
    relay.raw(b'{"t":"hi","pad":"' + b"a" * (link.MAX_LINE + 5000) + b'"}')
    serve(Q, [good, red])
    check(stats()["overlong"] - s0["overlong"] == 1 and len(Q.queue) == 2 and Q.net_ok, "a line longer than %d bytes: dropped whole, the next read" % link.MAX_LINE)

    # A MicroPython with no bytearray.find: the newlines found byte by byte, the same lines taken
    had, link._FIND = link._FIND, False
    s0 = stats()
    relay.raw(b"hello there")
    relay.raw(b'{"t":"hi","pad":"' + b"a" * (link.MAX_LINE + 5000) + b'"}')
    serve(Q, [good, red])
    link._FIND = had
    check(had and stats()["garbage"] - s0["garbage"] == 1 and stats()["overlong"] - s0["overlong"] == 1 and len(Q.queue) == 2 and Q.net_ok,
          "no bytearray.find: newlines found by the byte, garbage and an overlong line dropped, the poll good")

    # An answer's body is read in place: its escapes undone in _line, a memoryview handed on, never a
    # str the body's size (2.4 KB of them found no room on board #2, 2026-11-10)
    def esc(t, slash=False):
        """t as a JSON string literal, escaped the way CPython's json.dumps does (ensure_ascii)."""
        o = ['"']
        for ch in t:
            c = ord(ch)
            if ch in '"\\':
                o.append("\\" + ch)
            elif ch == "/" and slash:
                o.append("\\/")
            elif ch in "\b\f\n\r\t":
                o.append("\\" + "bfnrt"["\b\f\n\r\t".index(ch)])
            elif c < 0x20 or c > 0x7E:
                if c > 0xFFFF:
                    c -= 0x10000
                    o.append("\\u%04x\\u%04x" % (0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF)))
                else:
                    o.append("\\u%04x" % c)
            else:
                o.append(ch)
        return "".join(o) + '"'

    def take(line, want=7):
        link._want, link._got = want, None
        relay.raw(line)
        link._take()
        got = link._got
        try:
            return got and (type(got["body"]).__name__, json.loads(got["body"]))
        finally:
            link._want = link._got = None
            link._take()

    doc = {"s": 'q"b\\s/f\b\f\n\r\t\x01', "u": "\u00e9 \u20ac \U0001F600", "n": [1, 2.5, None, True, {"body": "x"}]}
    for find in (True, False):
        link._FIND = find
        lines = ['{"t": "res", "id": 7, "status": 200, "body": %s}' % esc(json.dumps(doc)),
                 '{"body":%s,"status":200,"id":7,"t":"res"}' % esc(json.dumps(doc), slash=True),
                 '{"t":"res","note":"a \\"body\\": \\"x\\"","id":7,"status":200,"body":%s}' % esc(json.dumps(doc))]
        got = [take(l) for l in lines]
        check(all(g == ("memoryview", doc) for g in got),
              "an answer's body read in place%s: every escape undone (quote, backslash, slash, b f n r t, \\u, a surrogate pair), "
              "in three layouts, a decoy \\\"body\\\" passed over" % ("" if find else ", with no bytearray.find"))
        s0 = stats()
        bad = [take('{"t": "res", "id": 7, "status": 200, "body": "%s"}' % b) for b in ("\\ud800x", "\\udc00", "\\x", "a\\u12", "ab\\")]
        check(not any(bad) and stats()["garbage"] - s0["garbage"] == 5,
              "a lone surrogate, a bad escape, a short \\u, a body ending in a backslash: each dropped as garbage%s" % ("" if find else " (no find)"))
    link._FIND = had
    # the line after the answer, in the same read, waits: the body isn't written over before it is parsed
    link._want, link._got = 7, None
    relay.raw('{"t": "res", "id": 7, "status": 200, "body": %s}\n{"id": 61, "op": "hello"}' % esc(json.dumps(doc)))
    link._take()
    body_ok = link._got is not None and json.loads(link._got["body"]) == doc
    link._want = link._got = None
    link.pump()
    usblink.poll()
    link.pump()
    check(body_ok and [m for m in relay.sent("pq") if m.get("id") == 61], "a line right behind the answer: kept until the answer is parsed, then answered")
    # a 10 KB body: no block its size made to read it
    import gc
    big = json.dumps({"results": ["x" * 90 for _ in range(110)]})
    link._want, link._got = 7, None
    relay.inq += ('{"t": "res", "id": 7, "status": 200, "body": %s}' % esc(big)).encode()
    link._take()                            # all of it but the newline (the fake relay's copies are its own)
    relay.inq += b"\n"
    gc.collect()
    gc.disable()
    a0 = gc.mem_alloc()
    link._take()                            # the newline: the line handled
    used = gc.mem_alloc() - a0
    gc.enable()
    ok = link._got is not None and bytes(link._got["body"]).decode() == big
    link._want = link._got = None
    link._take()
    check(ok and used < 1024, "a %d-byte body read with %d bytes allocated" % (len(big), used))

    # An answer nobody asked for, and a wrong id first: neither is taken
    s0 = stats()
    relay.raw(json.dumps({"t": "res", "id": 9999, "status": 200, "body": "{}"}))
    link.pump()
    forged = json.dumps({"count": 1, "results": [tx(Q, 0, to=OTHER, value=10**18)]})
    wrong = lambda m: [json.dumps({"t": "res", "id": m["id"] + 7, "status": 200, "body": forged}), relay.res(m)]
    poll_with(wrong, wrong)
    check(stats()["unsolicited"] - s0["unsolicited"] == 1 and stats()["wrong_id"] - s0["wrong_id"] == 2 and len(Q.queue) == 2
          and Q.queue[0]["h"] == good["safeTxHash"], "an unsolicited answer and a wrong id: dropped, the right answer used")

    # The same id twice: the first stands, and the second is dropped. The link stops reading at the
    # answer it waits for, so the second is read after the request has returned: no longer awaited
    # (unsolicited), or not the next request's id (wrong id)
    s0 = stats()
    dup = lambda m: [relay.res(m), json.dumps({"t": "res", "id": m["id"], "status": 200, "body": forged})]
    poll_with(dup, dup)
    link.pump()                             # the second answer to the last request, still unread
    late = sum(stats()[k] - s0[k] for k in ("dup", "wrong_id", "unsolicited"))
    check(late == 2 and len(Q.queue) == 2 and Q.queue[0]["h"] == good["safeTxHash"],
          "an answer sent twice: the first stands, the second dropped (%d)" % late)

    # A truncated body, a deeply nested one, a status 0, a body that isn't text: the poll fails, nothing breaks
    for name, f in (("truncated", lambda m: [relay.res(m, body='{"count": 1, "results": [{"safe": "0x5a')]),
                    ("nested", lambda m: [relay.res(m, body="[" * 3000)]),
                    ("status 0", lambda m: [json.dumps({"t": "res", "id": m["id"], "status": 0, "err": "upstream timeout"})]),
                    ("not text", lambda m: [json.dumps({"t": "res", "id": m["id"], "status": 200, "body": 5})]),
                    ("status as text", lambda m: [json.dumps({"t": "res", "id": m["id"], "status": "200", "body": "{}"})])):
        n = len(SVC.posted)
        poll_with(f, f)
        st = Q.state
        check(not Q.WATCH[0]["ok"] and Q.WATCH[0]["err"] and st not in ("crashed",) and len(SVC.posted) == n,
              "%s: the poll fails (%s), the console goes on" % (name, Q.WATCH[0]["err"]))
    poll_with()
    check(Q.WATCH[0]["ok"] and len(Q.queue) == 2, "then a good answer: the Safe is back")
    n = len(relay.reqs)
    poll_with(lambda m: [relay.res(m)], lambda m: [relay.res(m, body="[" * 5000)])
    asked = [r for r in relay.reqs[n:] if "/multisig-transactions/" in r["url"]]
    check(not Q.WATCH[0]["ok"] and "nested" in Q.WATCH[0]["err"] and len(asked) == 1,
          "a queue nested 5000 deep: refused before json.loads, not taken for one too long (%s)" % Q.WATCH[0]["err"])

    # A queue longer than the console's line (link.MAX_LINE): the relay says so, the console reads it a
    # few at a time, and one transaction too long even alone is refused in its place, the rest listed
    import quorum_ui_s
    relay.max = link.MAX_LINE
    big = tx(Q, 1, data="0x" + "ab" * (link.MAX_LINE // 2))
    n, p0 = len(relay.reqs), len(SVC.posted)
    serve(Q, [good, big, tx(Q, 2), tx(Q, 3), tx(Q, 4)])
    asked = [r["url"] for r in relay.reqs[n:] if "/multisig-transactions/" in r["url"]]
    q = Q.WATCH[0]["queue"]
    check(Q.WATCH[0]["ok"] and [e["n"] for e in q] == [0, -1, 2, 3, 4] and "too long" in q[1]["why"]
          and quorum_ui_s.tag(q[1]) == "#?" and not Q.waiting(q[1]) and Q.waiting(q[0]) and not any(e["why"] for e in q if e is not q[1])
          and any("limit=1&offset=1" in u for u in asked) and len(SVC.posted) == p0,
          "one transaction past the line: the queue read 3 at a time, that one alone refused in its place (#?), the other 4 listed")
    relay.max = None
    serve(Q, [good, red])

    # A relay that stops answering: the request gives up at the timeout, the watchdog fed past it
    import watch
    fed, real_extend = [], watch.extend
    watch.extend = lambda ms: (fed.append(ms), real_extend(ms))
    s0 = stats()
    t0 = Q.time.now
    poll_with(lambda m: [])
    watch.extend = real_extend
    check(stats()["timeouts"] - s0["timeouts"] == 1 and Q.time.now - t0 >= link.TIMEOUT_MS and not Q.WATCH[0]["ok"]
          and link.TIMEOUT_MS + 5000 in fed and not link.up, "a relay that stops: the request gives up after %d ms, the watchdog extended "
          "past it, and the link is down until it says hi" % link.TIMEOUT_MS)
    n = len(relay.reqs)
    Q.last_poll = 0
    Q.net_work()
    check(len(relay.reqs) == n and not Q.net_ok and "relay" in Q.net_err, "down: no request waits on nobody (%s)" % Q.net_err)
    poll_with()
    check(Q.net_ok and len(Q.queue) == 2, "it says hi again: polled")

    # A forged queue through the relay: refused here, as from the service, and nothing posted. Through
    # the console's own tick: D2 pressed, then held 5 s.
    def tick(*pressed):
        Q.keys.pressed = lambda: list(pressed)
        Q._busy, Q.last_poll, Q.splash_until = False, Q.time.now, 0
        Q.tick(None)
    n = len(SVC.posted)
    serve(Q, [tx(Q, 0, tamper=True), tx(Q, 1, safe=OTHER)])
    refused = all(e["why"] for e in Q.queue)
    states = set()
    for e in Q.queue:
        Q.open_entry(e)
        for _ in range(10):
            tick("D2")
            states.add(Q.state)
        Q.keys.down.add("D2")
        for _ in range(50):
            Q.time.now += 100
            tick()
            states.add(Q.state)
        Q.keys.down.discard("D2")
        Q.state = "home"
    check(refused and len(Q.queue) == 2 and len(SVC.posted) == n and states == {"review"},
          "a forged hash and another Safe's transaction through the relay: refused, D2 never starts a hold, nothing posted")

    # A refusal is for the fields it was given. The real transaction after a forged one under its hash
    # gets its own look; a checked one keeps its fields when forged ones come after it.
    good = tx(Q, 0, value=5)
    forged = dict(good, value=str(10 ** 18 + 5))
    seen = []
    for t in (forged, good, forged):
        serve(Q, [t])
        seen.append(Q.queue[0])
    check(seen[0]["why"] and not seen[1]["why"] and seen[1]["mine"] == good["safeTxHash"] and seen[2] is seen[1]
          and seen[2]["f"][Q.SIGNED.index("value")] == "5" and len(SVC.posted) == n,
          "forged, then the real one under its hash: the real one checks out; forged again: the checked fields kept")

    # Only a pinned service, in plain ASCII: anything else raises before a byte goes out
    n = len(relay.wrote)
    bad = [base + "olia/api/v1/safes/", base, "https://api.safe.global/tx-service/basesep@evil.example/api/",
           base + "/../eth/api/v1/safes/", base + "/api/v1/safes/#x", base + "/api/v1/safes/ x", base + "/api\\v1",
           base + "/api/v1/safes/\u00e9", base + "/api/" + "a" * link.MAX_URL, "https://evil.example/api/v1/safes/",
           "http://api.safe.global/tx-service/basesep/api/v1/safes/", 5, None]
    raised = 0
    for u in bad:
        try:
            link.request("GET", u)
        except link.LinkError:
            raised += 1
    try:
        link.request("DELETE", base + "/api/v1/safes/")
    except link.LinkError:
        raised += 1
    check(raised == len(bad) + 1 and len(relay.wrote) == n and not relay.part,
          "off-pin, prefix tricks (basesepolia, @, ..), #, spaces, \\, non-ASCII, too long, plain http, DELETE: %d refused, nothing sent" % raised)
    check(link.pinned(base + "/api/v1/safes/") and link.pinned("https://api.safe.global/tx-service/eth/api/v1/safes/"),
          "the pinned bases themselves pass")

    # The link's asks while a request waits: queued, then answered once it is done
    def op_in(m):
        return [json.dumps({"id": 41, "op": "hello"}), json.dumps({"id": 42, "op": "status"}), relay.res(m)]
    poll_with(op_in)
    usblink.poll()
    link.pump()
    pq = {m["id"]: m for m in relay.sent("pq") if m.get("id") in (41, 42)}
    check(set(pq) == {41, 42} and pq[41]["link"]["max"] == link.MAX_LINE and pq[41]["image"] == "console-rp"
          and "link" in pq[42] and "wifi" not in pq[42] and pq[42]["link"]["requests"] > 0,
          "hello and status sent mid-request: queued, answered after; hello says the longest line, status the link's counts")

    def op(d):
        n = len(relay.wrote)
        relay.raw(json.dumps(d))
        link.pump()
        usblink.poll()
        link.pump()
        out = [m for m in relay.sent("pq") if m.get("id") == d["id"]]
        return out[-1] if out else None

    a = op({"id": 51, "op": "wifi", "ssid": "x", "password": "hunter2hunter2"})
    b = op({"id": 52, "op": "maint"})
    check(a and not a["ok"] and b and not b["ok"] and "wifi.json" not in os.listdir() and "maint" not in os.listdir() and Q.ask is None,
          "the wifi and maint asks: refused on console-rp, nothing written")
    Q.open_entry(Q.queue[0])
    c = op({"id": 53, "op": "safes", "safes": [{"chainId": CHAIN, "address": SAFE, "name": "x"}]})
    Q.tick(None)
    check(c and not c["ok"] and "busy" in c.get("why", "") and Q.state == "review", "a safes ask during a review: busy, the review stays")
    Q.state = "home"
    usblink.open_ask = None

    # The log copy never blocks: past LOGS waiting, the oldest goes
    s0 = stats()
    for i in range(link.LOGS + 5):
        qlog.write("line %d" % i)
    link.pump()
    check(stats()["dropped_logs"] - s0["dropped_logs"] == 5 and relay.sent("log")[-1]["m"].endswith("line %d" % (link.LOGS + 4)),
          "%d log lines at once: the last %d go out, the oldest 5 dropped and counted" % (link.LOGS + 5, link.LOGS))
    # A status answer goes out with no copy of itself: json.dumps makes the line once, and the link
    # writes it as it is (on board #2 six copies of 1 KB each found no room, 2026-11-10)
    class Sink:
        n = 0

        def any(self):
            return 0

        def write(self, b, off=0, n=None):
            self.n += len(b) - off
            return len(b) - off
    import gc
    relay.raw(json.dumps({"id": 54, "op": "status"}))
    link.pump()
    had, sink = link._u, Sink()
    link._u = sink
    gc.collect()
    gc.disable()
    a0 = gc.mem_alloc()
    usblink.dumps = json.dumps(Q.link_status())        # what the answer's fields cost to gather and dump
    a1 = gc.mem_alloc()
    usblink.poll()
    link.pump()
    a2 = gc.mem_alloc()
    gc.enable()
    del usblink.dumps
    link._u = had
    made, sent = a1 - a0, a2 - a1
    check(sink.n > 500 and sent < made + sink.n,
          "a status answer of %d bytes: %d bytes allocated to answer, %d to gather and dump its fields: no copy of the line" % (sink.n, sent, made))
    every = "\n".join(relay.wrote)
    check("test-key" not in every and "hunter2" not in every, "no API key, and not the password the wifi ask carried, in any line out")

    # A base that isn't pinned (secrets.QUORUM_URL): the console polls nothing, and nothing goes out
    relay = Relay()
    Q = fresh(url="https://evil.example/tx-service", relay=relay)
    serve(Q, [tx(Q, 0)])
    check(not relay.sent("req") and not Q.net_ok and "pinned" in Q.WATCH[0]["err"],
          "a QUORUM_URL off the pin: no request goes out (%s)" % Q.WATCH[0]["err"])
    relay = Relay()
    Q = fresh(url="http://127.0.0.1:8787", relay=relay)
    serve(Q, [tx(Q, 0)])
    check(not relay.sent("req") and not Q.net_ok, "the laptop's mock in QUORUM_URL, on a production image: refused too")
    relay = Relay()
    Q = fresh(prod=False, url="http://127.0.0.1:8787", relay=relay)
    serve(Q, [tx(Q, 0)])
    check(Q.net_ok and len(Q.queue) == 1 and all(r["url"].startswith("http://127.0.0.1:8787/") for r in relay.sent("req")),
          "a development load (no build.py): secrets.QUORUM_URL is pinned too, for the bench soak on the mock")


def case_crt():
    """console-rp's CRT screens (quorum_ui_crt.py, crt.py): quorum_ui_s's pages, an effect only when
    something arrives, none on a redraw or during the hold, and any press stops an effect and still
    reaches the console: D0 during a red page's tear rejects it, with one press."""
    import fonts
    chip()
    Q = fresh(relay=Relay())
    import quorum_ui_crt, quorum_ui_s, crt
    Q.U = quorum_ui_crt
    Q.U.use("dark")
    crt.time = Q.time
    played, real_play = [], crt.play
    crt.play = lambda d, fx, *a, **k: (played.append(fx), real_play(d, fx, *a, **k))[1]
    good, red = tx(Q, 0), tx(Q, 1, to=OTHER, data="0xdeadbeef")
    serve(Q, [good, red])
    by = {e["n"]: e for e in Q.queue}

    def fx(do=None):
        del played[:]
        if do:
            do()
        Q.U.draw(Q)
        return played[-1] if played else None
    Q.state, Q.tab = "home", 0
    fx()
    check(fx() is None, "home drawn again, nothing changed: no effect")
    check(fx(lambda: Q.open_entry(by[0])) == "tear", "a transaction opens: tear")
    check(fx(lambda: Q.three("D1")) == "short", "a page turn: a short tear")
    check(fx() is None, "the same page again: still")
    v = [k for k, i in Q.pages].index("verify")
    check(fx(lambda: setattr(Q, "page", v)) == "lock", "the verify code, worked out here: lock")
    Q.seen.update(range(len(Q.pages)))
    Q.press_sign()
    check(Q.state == "hold" and fx() is None and fx() is None, "the hold: no effect while it fills")
    Q.state = "home"
    Q.declined.discard(by[1]["h"])
    check(fx(lambda: Q.open_entry(by[1])) == "strong" and Q.U._bg == Q.U.B.c("bad_bg"), "a red transaction: a strong tear, on red")
    Q.state, Q.kpage = "key", 0
    check(fx() == "lock", "the key's code: lock")
    Q.state, Q.result = "result", (True, "Signed", ["#0"])
    check(fx() == "lock", "Signed: lock")
    Q.state, Q.tab = "home", 0
    fx()
    check(fx(lambda: setattr(Q, "tab", 1)) == "short", "another tab: a short tear")
    Q.tab = 0
    fx()
    serve(Q, [good, red, tx(Q, 2)])
    check(fx() == "tear", "a new transaction on home: tear")

    # D0 during a red page's tear: the tear stops, the page goes out whole, and the press rejects it
    Q.state = "home"
    Q.U.draw(Q)
    r = [e for e in Q.queue if e["n"] == 1][0]
    Q.declined.discard(r["h"])
    calls = [0]

    def pressed():
        calls[0] += 1
        return ["D0"] if calls[0] == 2 else []
    Q.keys.pressed = pressed
    t0 = Q.time.now
    Q.open_entry(r)
    Q.U.draw(Q)
    took = Q.time.now - t0
    held = crt.take_pressed()
    crt._taken.extend(held)
    check(held == ["D0"] and took < 200, "D0 during the tear: it stops after %d ms, the press kept" % took)
    Q.keys.pressed = lambda: []
    Q._busy, Q.last_poll, Q.splash_until = False, Q.time.now, 0
    Q.tick(None)
    check(Q.state == "home" and r["h"] in Q.declined and not crt.take_pressed(), "and the tick takes it: rejected, with that one press")

    # Every screen draws in the CRT look, its footer with the caps
    caps, real_cap = [], quorum_ui_s.cap
    quorum_ui_s.cap = lambda d, i, x, y, ink: (caps.append(i), real_cap(d, i, x, y, ink))[1]
    crt.FX = False
    ok = True
    for st in ("home", "owners", "device", "chip", "key", "who", "result", "pinfail", "nochip", "unconfigured", "review"):
        Q.state = st
        if st == "review":
            Q.open_entry(Q.queue[0])
        if st == "chip":
            Q.open_chip()
        if st == "who":
            Q.who = Q.owners()[0]
        try:
            Q.U.draw(Q)
        except Exception as e:
            ok = False
            print("      %s: %r" % (st, e))
    check(ok and set(caps) == {0, 1, 2}, "every screen draws in the CRT look; the footer's caps ■ ● ▲ on D0 D1 D2")
    quorum_ui_s.cap = real_cap
    crt.FX = True
    crt.play = real_play
    Q.state = "home"


LINK_THREE = [False]
THREE_BOARD = ["feather-s3"]


def main_three(board="feather-s3"):
    """case_three, alone in a fresh device: secrets.py names the board before board.py is read."""
    THREE_BOARD[0] = board
    with open("secrets.py", "w") as f:
        f.write('BOARD = "%s"\n' % board)
    for m in ("board", "lcd", "fonts", "quorum_ui", "quorum_ui_s", "splash", "bootmark"):
        sys.modules.pop(m, None)
    print("-- three, " + board)
    try:
        case_three()
    except Exception as e:
        failed[0] += 1
        print("FAIL  case_three raised")
        sys.print_exception(e)
    print("-- link, " + board)
    LINK_THREE[0] = True
    try:
        case_link()
    except Exception as e:
        failed[0] += 1
        print("FAIL  case_link raised")
        sys.print_exception(e)
    print("-- practice, " + board)
    try:
        case_practice()
    except Exception as e:
        failed[0] += 1
        print("FAIL  case_practice raised")
        sys.print_exception(e)
    LINK_THREE[0] = False
    print("%s: %d failed" % (board, failed[0]))
    return failed[0]


def main_pqk():
    return main_three("picoquorum-key")


def main_rp():
    """console-rp alone in a device: the three-button case on its footer and over the relay, the
    relay's own case, and the practice on its bottom row. Not case_link: its Wi-Fi and maint asks
    are the radio boards'; case_relay checks they are refused here."""
    THREE_BOARD[0] = "console-rp"
    with open("secrets.py", "w") as f:
        f.write('BOARD = "console-rp"\n')
    for m in ("board", "lcd", "fonts", "quorum_ui", "quorum_ui_s", "splash", "bootmark"):
        sys.modules.pop(m, None)
    LINK_THREE[0] = True                # case_practice: on this board's three buttons
    for case in (case_three, case_relay, case_practice, case_crt, case_nochip):
        print("-- %s, console-rp" % case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    LINK_THREE[0] = False
    print("console-rp: %d failed" % failed[0])
    return failed[0]


def main_knob():
    return main_three("feather-knob")


def main():
    for case in (case_pin, case_owners_pages, case_refusals, case_sign, case_service, case_production, case_chips, case_multi, case_unsent, case_memory, case_safes, case_watchdog, case_home, case_saver, case_release, case_passkey, case_release_approval, case_knob, case_link, case_setup_link, case_practice, case_nochip):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("%s: %d failed" % ("console", failed[0]))
    return failed[0]
