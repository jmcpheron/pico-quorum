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
    Q.handle("B")
    check(Q.state == "owners" and Q.opage == 0, "B on home: the Owners screen, page 1")
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
    Q.handle("B")
    Q.handle("down")
    Q.handle("A")
    check(Q.state == "home", "A leaves from any page")
    Q.handle("B")
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
    check("bootart" not in sys.modules, "the single-buffer 240x240 board never loads the boot animation (it ran the heap out at boot, 2026-09-29)")
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


def main():
    for case in (case_pin, case_owners_pages, case_refusals, case_sign, case_service, case_production, case_chips, case_multi, case_unsent, case_safes, case_watchdog):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("%s: %d failed" % ("console", failed[0]))
    return failed[0]
