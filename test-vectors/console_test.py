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
            return Resp(200, {"count": len(txs), "results": txs[:limit]})
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


def fresh(prod=True, url="https://api.safe.global/tx-service/basesep", expect="auto", extra="", safe=True, keep=False):
    """A newly imported console with this secrets.py (and build.py when prod), started, not polled."""
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
    if prod:
        with open("build.py", "w") as f:
            f.write('IMAGE = "console"\nBUILD = "test"\nDATE = 1790000000\n')
    else:
        try:
            os.remove("build.py")
        except OSError:
            pass
    for m in ("secrets", "build", "image", "quorum", "signer", "net", "txservice", "atecc", "qlog", "watch"):
        sys.modules.pop(m, None)
    for f in os.listdir():
        if not keep and (f.startswith("counter-") or f == "slot.txt"):
            os.remove(f)
    import txservice
    txservice.requests = SVC
    import quorum as Q
    Q.start_timer = lambda: None
    Q.time = Clock()
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
    check(Q.truncated and len(Q.queue) == 3, "out of memory on the queue: the first 3 are shown, and it says so")


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
    check(Q.can_sign(Q.queue[0])[0] and Q.state == "crashed", "(the queue is still there, but the crashed state never reaches review)")
    Q.handle("A")
    check(Q.state == "crashed", "A does nothing on the crashed screen")


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
    SVC.safes[ETH_SAFE]["down"] = True
    Q.WATCH[1]["need_info"] = True
    Q.net_work()
    check(not Q.net_ok and "Vault" in Q.net_err and any(e["w"]["chain"] == CHAIN for e in Q.queue),
          "Ethereum's service down: said so by name, Base Sepolia's queue still shown")
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
    """The project Safe approving a PicoQuorum release (release.py): a delegatecall to the pinned
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
    check(bool(eo["why"]) and "no PicoQuorum release" in eo["why"], "a message with no release named: refused (it signs only releases)")


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
    2 s, 3 s when a page is red. Run in a device of its own (main_three): board.py is read once."""
    chip()
    Q = fresh(extra='BOARD = "feather-s3"')
    check(Q.THREE and (Q.L.W, Q.L.H) == (240, 135) and Q.U.__name__ == "quorum_ui_s" and Q.PRESS == "D2",
          "the Feather: three buttons, 240x135, the small screens' UI")
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

    Q.state, Q.sel, Q.foot = "home", 0, None
    tick("D1")
    check(Q.sel == 1, "home: D1 moves down the list (through tick)")
    tick("D1")
    tick("D1")
    check(Q.foot == "device", "D1 past the list: the Owners and Device choices")
    tick("D1L")
    tick("D2")
    check(Q.state == "owners", "D1 held moves back; D2 opens Owners")
    tick("D0")
    check(Q.state == "home", "D0: back home")
    Q.foot = "device"
    tick("D2")
    check(Q.state == "device", "D2 on Device opens it")
    tick("D2")
    check(Q.state == "chip", "Device: D2 on Chip opens the chip pages")
    tick("D0")
    tick("D0")
    check(Q.state == "home", "D0, D0: back to Device, then home")
    Q.foot = "device"
    tick("D0")
    check(Q.foot is None and Q.state == "home", "D0 on the choices: back onto the list")
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

    rail = Q.U.RAIL
    Q.msg = ""
    Q.open_entry(e)
    t = drawn()
    left = [s for s, x, y, f in t if x < rail]
    check(left == ["Reject", "Next", "See %d" % len(Q.unseen())], "the rail on a review: Reject, Next, See %d" % len(Q.unseen()))
    while Q.unseen():
        Q.three("D1")
    check([s for s, x, y, f in drawn() if x < rail] == ["Reject", "Next", "Sign"], "every page seen: Sign")
    ok = True
    for p in range(len(Q.pages)):
        Q.page = p
        for s, x, y, f in drawn():
            if y + fonts.height(f) > Q.L.H + 3 or (x < rail and s not in ("Reject", "Next", "Sign")):
                ok = False
                print("      page %d: %r at (%d, %d) in %s" % (p + 1, s, x, y, f))
    check(ok, "every page of a review fits 240x135, and only the rail is drawn left of it")
    Q.state = "home"
    check([s for s, x, y, f in drawn() if x < rail] == ["Next", "Open"], "the rail on home: Next, Open")
    Q.state = "pinfail"
    t = [s for s, x, y, f in drawn() if x < rail]
    check(t == ["Check"], "the rail on Not pinned: Check (%r)" % t)


def main_three():
    """case_three, alone in a fresh device: secrets.py names the Feather before board.py is read."""
    with open("secrets.py", "w") as f:
        f.write('BOARD = "feather-s3"\n')
    for m in ("board", "lcd", "fonts", "quorum_ui", "quorum_ui_s", "splash", "bootmark"):
        sys.modules.pop(m, None)
    print("-- three")
    try:
        case_three()
    except Exception as e:
        failed[0] += 1
        print("FAIL  case_three raised")
        sys.print_exception(e)
    print("%s: %d failed" % ("three", failed[0]))
    return failed[0]


def main():
    for case in (case_pin, case_owners_pages, case_refusals, case_sign, case_service, case_production, case_chips, case_multi, case_unsent, case_safes, case_watchdog, case_home, case_saver, case_release, case_passkey, case_release_approval, case_knob):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("%s: %d failed" % ("console", failed[0]))
    return failed[0]
