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

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, dict(headers or {})))
        if "/multisig-transactions/" in url:
            if self.fail_pending:
                e, self.fail_pending = self.fail_pending, None
                raise e
            limit = int(url.split("limit=")[1].split("&")[0]) if "limit=" in url else 10
            return Resp(200, {"count": len(self.txs), "results": self.txs[:limit]})
        if "/safes/" in url:
            return Resp(200, self.info)
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
    lines = ['WIFI_SSID = "emulator"', 'WIFI_PASS = ""', 'HOSTNAME = "emu"', 'QUORUM_URL = "%s"' % url,
             'QUORUM_API_KEY = "test-key"', "ALLOW_LOCK = True", "ALLOW_GENKEY = True", "ALLOW_SOFT_KEY = True"]
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


def tx(Q, nonce, to=ALICE, value=0, data="0x", op=0, safe=SAFE, conf=(), tamper=False):
    t = {"safe": safe, "to": to, "value": str(value), "data": data if data != "0x" else None, "operation": op,
         "safeTxGas": "0", "baseGas": "0", "gasPrice": "0", "gasToken": ZERO, "refundReceiver": ZERO,
         "nonce": nonce, "confirmations": [{"owner": o} for o in conf]}
    try:
        h = safe_tx.from_service(CHAIN, dict(t, safe=SAFE))
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
    Q.need_info = True
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
    Q.need_info = True
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


def case_production():
    chip()
    Q = fresh()
    import signer
    check(not signer.flag("ALLOW_LOCK") and not signer.flag("ALLOW_GENKEY"), "production: ALLOW_LOCK/ALLOW_GENKEY in secrets.py count for nothing")
    check(Q.SOFT_OK is False, "production: ALLOW_SOFT_KEY counts for nothing")
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


def main():
    for case in (case_pin, case_refusals, case_sign, case_service, case_production, case_chips, case_watchdog):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("%s: %d failed" % ("console", failed[0]))
    return failed[0]
