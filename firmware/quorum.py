# PicoQuorum's console: the Safe's queue, each transaction in plain language, and a signature from
# the chip only after the person has seen every page and held A. Polls Safe's transaction service
# over WiFi (for now tools/quorum's simulated Safe on the laptop).
#
# The loop is wallet.py's: one 50 ms Timer, keys every tick, redraw only when something changed,
# and the timer stopped around anything that blocks (HTTP, hashing, the chip). X shows the device:
# build, chip, pin, signature counter. The chip map is not part of this image (tools/fw push
# ceremony has it), so nothing reachable from here can make, switch or lock a key.
#
# Pinned: secrets.QUORUM_EXPECT names each chip this board may use (one, or a list): its serial,
# the slot and the owner address its key must produce. At boot the chip on the bus picks its entry. The production image (image.PRODUCTION) signs nothing until they all match, and
# the check runs again right before every signature.
#
# Trust: the service is not trusted. Each transaction is rehashed here (safe_tx.py) from the same
# fields decode.py puts on the screen, with the chain and Safe pinned in quorum_cfg.py. If the
# service's safeTxHash or Safe differs, the transaction is REFUSED and cannot be signed. The chip
# signs the hash computed here, never a string the service sent: wrapped as a WebAuthn assertion
# (webauthn.py), because onchain this key owns the Safe through Safe's passkey signer.
#
#   import lcd; import quorum; quorum.start()      (main_console.py does this)
import sys, time, machine, network, gc
import lcd as L
import net
import image
import policy
import qlog
import watch
import chips
import signer as S
import safe_tx
import decode
import quorum_cfg
import txservice
import webauthn
import splash
import quorum_ui as U
try:
    import secrets
except ImportError:
    secrets = None

CFG = quorum_cfg.CFG
PROD = image.PRODUCTION
# The Safe this console signs for: QUORUM_SAFE in secrets.py (a Safe on Base Sepolia or Base, made
# in the Safe web app), else, on a development board only, the pinned Family Safe on the laptop.
# The production image with no QUORUM_SAFE stops on an "unconfigured" screen instead.
_SAFE = getattr(secrets, "QUORUM_SAFE", None) if secrets else None
UNCONFIGURED = PROD and not _SAFE
SAFE = _SAFE or CFG["safes"][0]
CHAIN = SAFE["chainId"]
SAFE_ADDR = SAFE["address"].lower()
BASE = (getattr(secrets, "QUORUM_URL", None) or getattr(secrets, "APP_URL", None)) if secrets else None
API_KEY = getattr(secrets, "QUORUM_API_KEY", None) if secrets else None
EXPECTS = policy.pins(getattr(secrets, "QUORUM_EXPECT", None) if secrets else None)
EXPECT = None       # the entry for the chip on the bus (probe_chip), from EXPECTS
NAME = getattr(secrets, "DEVICE_NAME", "picoquorum") if secrets else "picoquorum"
SSID = getattr(secrets, "WIFI_SSID", "") if secrets else ""
SOFT_OK = not PROD and bool(getattr(secrets, "ALLOW_SOFT_KEY", False) if secrets else False)
_poll, _idle = policy.poll_defaults(BASE, API_KEY)
POLL_MS = int(getattr(secrets, "QUORUM_POLL_S", _poll) if secrets else _poll) * 1000
IDLE_POLL_MS = int(getattr(secrets, "QUORUM_IDLE_POLL_S", _idle) if secrets else _idle) * 1000
IDLE_AFTER_MS = 10 * 60 * 1000
INFO_EVERY = 5          # the real service: the Safe's owners and nonce every 5th poll, or when the queue moves
CRASH_AFTER = 20        # this many failed ticks in a row: stop on the crashed screen, sign nothing
HOLD_MS, HOLD_RED_MS = 2000, 3000       # A held this long to sign; longer when any page is red

# Keys by role. The console's own controls (a guarded Sign button, a paging dial) remap here.
SIGN, REJECT, BACK = "A", "Y", "B"
NEXT, PREV = ("down", "right"), ("up", "left")

d = None
keys = None
sig = None          # the signer backend (the chip)
svc = None          # txservice.Service
timer = None
state = "boot"      # boot | home | review | hold | working | result | owners | device | nochip | pinfail | unconfigured | crashed
qx = qy = ""
me = ""             # this key's owner address, lowercase (see my_owner)
ctx = None          # decode.context: the pinned names plus "This key"
info = {}           # the service's view of the Safe: nonce, threshold, owners
queue = []          # entries (see entry()), lowest nonce first
cache = {}          # safeTxHash -> entry, so each transaction is hashed and decoded once
sel = 0             # the highlighted row on home
cur = None          # the entry being reviewed
pages = []          # its pages: ("summary"|"item"|"verify"|"refused", index)
page = 0
seen = set()        # pages of cur the person has looked at
hold_t0 = 0
result = None       # (ok, title, lines) after a signing attempt
unsent = None       # (entry, signature) when the service did not take it: A tries again
declined = set()    # safeTxHashes rejected on this console
serial = ""         # the chip's serial number
row = None          # atecc.decode_slot for the signing slot (None on a software key)
profile = ""        # which config the chip holds: quorum-v1, legacy-test, factory, unknown (chipcfg.identify)
chip = None         # its entry in chips.json: name and theme (chips.py; cosmetic only)
pin_ok = False      # the chip, slot and owner match QUORUM_EXPECT (always True on a dev board without one)
pin_why = ""
counter = None      # the chip's key-use counter (counter 0) when the slot has LimitedUse, else None
boot_count = None   # counter 0 as found at boot, before this console used the key itself
outside = 0         # signatures the chip made since this console last looked, not made by it
truncated = False   # the queue did not fit in memory: only the first few are shown
polls = 0           # since the Safe's info was last fetched
need_info = True
_txs_seen = None
fails = 0           # ticks in a row that raised
saved_checked = False   # send_saved() ran after this boot
net_ok = False
net_err = "starting"
last_poll = 0
last_announce = 0
last_activity = 0   # the last key press or change in the queue (see poll_every)
_snap = None
splash_until = 0
msg = ""
msg_until = 0
dirty = True
_busy = False
_n = 0
log = []


def say(s, secs=3):
    global msg, msg_until, dirty
    msg, dirty = s, True
    msg_until = time.ticks_add(time.ticks_ms(), secs * 1000)
    _log(s)


def _log(s):
    log.append(s)
    if len(log) > 30:
        log.pop(0)


# ----------------------------------------------------------------------------- the key
def my_owner():
    """This key's owner address: the SafeWebAuthnSignerProxy the passkey factory deploys for it,
    computed here from the key and the pinned factory (webauthn.owner_address). The simulated and
    the forked Safe use the same rule, and the factory's getSigner agrees (test-vectors)."""
    if not qx:
        return ""
    return webauthn.owner_address(qx, qy, CFG["signer"])


def read_key():
    global qx, qy, me, ctx, last_announce
    try:
        x, y = sig.pubkey()
        qx, qy = "0x%064x" % x, "0x%064x" % y
    except Exception as e:
        qx = qy = ""
        _log("no key: %r" % e)
    me = my_owner()
    ctx = decode.context(CFG, SAFE_ADDR, {me: "This key"} if me else None, chain=CHAIN)
    cache.clear()
    last_announce = 0


def probe_chip():
    global sig, state
    sig = S.load(soft=not PROD)     # the production image never falls back to a key on flash
    if sig.name != "atecc608" and not SOFT_OK:
        state = "nochip"
        return
    global EXPECT
    EXPECT = None
    if EXPECTS and sig.name == "atecc608":
        try:
            EXPECT = policy.pick(EXPECTS, sig.serial())
        except Exception:
            EXPECT = None
    if EXPECT:
        sig.slot = int(EXPECT.get("slot", 0))   # the pin names the slot; slot.txt does not count
    if state in ("nochip", "pinfail"):
        state = "boot"
    global boot_count
    try:
        # before reading the key: on a chip with its data zone locked (quorum v1) a public-key
        # read counts as a use of a LimitedUse key too (seen on chip 2, 2026-09-26)
        boot_count = sig.chip.counter(0) if sig.name == "atecc608" else None
    except Exception:
        boot_count = None
    read_key()
    check_pin()
    if not pin_ok and (PROD or EXPECTS):
        state = "pinfail"


def check_pin():
    """Is the chip in the board the one QUORUM_EXPECT pins, with the key it pins? Reads the chip's
    own config zone, so it works on chip #1's test table and on quorum v1 alike."""
    global serial, row, pin_ok, pin_why, profile, chip
    serial, row, profile, chip = "", None, "", None
    if sig.name == "atecc608":
        try:
            import atecc
            import chipcfg
            serial = sig.serial()
            cfg = sig.config()
            row = atecc.decode_slot(cfg, sig.slot)
            profile = chipcfg.identify(cfg)
        except Exception as e:
            pin_why = "chip: %r" % e
        chip, new = chips.seen(serial, profile or None)
        if chip:
            U.use(chip["theme"])            # which chip is in, at a glance: chip 1 dark, chip 2 light
            if new:
                qlog.write("new chip %s: %s, %s, theme %s" % (serial, chip["name"], profile, chip["theme"]))
    if EXPECT:
        pin_ok, pin_why = policy.expect_check(EXPECT, serial, sig.slot, row, me)
    elif EXPECTS:
        pin_ok, pin_why = False, "this chip is not one of the %d pinned" % len(EXPECTS)
    elif PROD:
        pin_ok, pin_why = False, "secrets.py has no QUORUM_EXPECT"
    else:
        pin_ok, pin_why = True, ""      # a development board without a pin signs as before
    qlog.write("pin %s: chip %s slot %d owner %s%s" % ("ok" if pin_ok else "FAIL", serial or sig.name, sig.slot, me or "none",
                                                     "" if pin_ok else " (%s)" % pin_why))


# ----------------------------------------------------------------------------- the counter
def counter_file():
    return "counter-%s.txt" % (serial or "soft")


def read_counter():
    """Counter 0, which the chip raises on every signature by a LimitedUse slot (chip #1's slot 0 and
    quorum v1's). None when the slot has no LimitedUse: then the number means nothing."""
    if sig.name != "atecc608" or not row or not row.get("limitedUse"):
        return None
    return sig.chip.counter(0)


def stored_counter():
    try:
        return int(open(counter_file()).read().strip())
    except Exception:
        return None


def store_counter(n):
    try:
        with open(counter_file(), "w") as f:
            f.write(str(n))
    except Exception as e:
        qlog.write("counter not saved: %r" % e)


def check_counter():
    """At start: has the key been used since this console last did? Counter 0 counts every use
    of a LimitedUse key: signatures, and on a quorum v1 chip (data zone locked) public-key reads
    too. So the count found at boot, before this console read the key itself, is the one compared
    with the saved one; the saved one is then the count after its own reads. An audit hint, not a
    lock: anyone on the chip's bus can raise the counter, but nobody can lower it."""
    global counter, outside
    try:
        counter = read_counter()
    except Exception as e:
        counter = None
        qlog.write("counter: %r" % e)
    if counter is None:
        return
    found = boot_count if boot_count is not None else counter
    what, n = policy.counter_check(stored_counter(), found)
    if what == "outside":
        outside = n
        qlog.write("counter %d: %d use%s of the key outside this console" % (found, n, "" if n == 1 else "s"))
    elif what == "backwards":
        qlog.write("counter %d is below the saved %s: another chip, or the file was changed" % (found, stored_counter()))
    elif what == "first":
        qlog.write("counter %d: first look" % found)
    store_counter(counter)


def own_reads(before):
    """After this console read the key again (Check again): any rise since `before`, the count
    found just ahead of the read, was its own. Save the count now, so it is not flagged later."""
    global counter, outside
    try:
        now = read_counter()
    except Exception:
        return
    if now is None:
        return
    if counter is None:
        check_counter()
        return
    if before is not None and before > counter:
        outside += before - counter          # uses between the last look and this one were not ours
        qlog.write("counter %d: %d use%s of the key outside this console" % (before, before - counter, "" if before - counter == 1 else "s"))
    counter = now
    store_counter(now)


def fingerprint():
    return qx[2:10] if qx else ""


# ----------------------------------------------------------------------------- the queue
def entry(t):
    """One transaction from the service, checked and decoded once (cached by its safeTxHash).
    Confirmations are refreshed on every poll; the fields cannot change without the hash changing."""
    h = (t.get("safeTxHash") or "").lower()
    e = cache.get(h)
    if e is None:
        e = {"h": h, "t": t, "n": int(t["nonce"]), "mine": "", "why": ""}
        if len(h) != 66:
            e["why"] = "It has no usable safeTxHash."
        elif (t.get("safe") or "").lower() != SAFE_ADDR:
            e["why"] = "It is for another Safe, %s, not the one this console signs for." % U.short(t.get("safe") or "?")
        else:
            try:
                e["mine"] = decode.hx(safe_tx.from_service(CHAIN, t))
                if e["mine"] != h:
                    e["why"] = "The service wants a signature over a hash that these fields do not produce. Signing it could approve something else entirely."
            except MemoryError:
                raise                   # not a verdict on the transaction: not cached, tried again next poll
            except Exception as ex:
                e["why"] = "Its fields do not hash: %s" % ex
        try:
            e["r"] = decode.review(t, ctx)
            e["why"] = e["why"] or e["r"].get("refuse", "")
        except MemoryError:
            raise
        except Exception as ex:
            e["r"] = {"summary": "Unreadable", "level": "red", "items": []}
            e["why"] = e["why"] or "It could not be decoded: %s" % ex
        cache[h] = e
    e["conf"] = [str(c.get("owner") or "").lower() for c in (t.get("confirmations") or []) if isinstance(c, dict)]
    return e


def bad_entry(t, i, ex):
    """A transaction the service sent that could not even be read: shown, refused, never signed."""
    h = str(t.get("safeTxHash") if isinstance(t, dict) else "") or "bad:%d" % i
    try:
        n = int(t.get("nonce"))
    except Exception:
        n = -1
    return {"h": h.lower(), "t": {}, "n": n, "mine": "", "conf": [],
            "why": "The service sent something that is not a transaction: %s" % repr(ex)[:60],
            "r": {"summary": "Malformed", "level": "red", "items": []}}


def signed_by_me(e):
    return bool(me) and me in e["conf"]


def owners():
    return [o.lower() for o in info.get("owners", [])]


def threshold():
    return int(info.get("threshold", 0) or 0)


def waiting(e):
    """Does this transaction want something from this key?"""
    return not e["why"] and not signed_by_me(e) and e["h"] not in declined


def safe_version():
    """The Safe's version as the service reports it ("1.4.1", "1.3.0+L2"), and whether this
    console's hash is right for it: safe_tx.py follows the EIP-712 domain of Safe 1.3.0 and later."""
    v = str(info.get("version") or "")
    try:
        nums = tuple(int(x) for x in v.split("+")[0].split(".")[:3])
    except ValueError:
        nums = ()
    return v, nums >= (1, 3, 0)


def can_sign(e):
    """(True, "") or (False, why not). Seeing every page is checked separately."""
    if e["why"]:
        return False, "refused"
    v, ok = safe_version()
    if v and not ok:
        return False, "old Safe v%s" % v
    if not qx:
        return False, "no key in the chip"
    if not pin_ok:
        return False, "key doesn't match the pin"
    if me not in owners():
        return False, "this key is not an owner"
    if signed_by_me(e):
        return False, "already signed by you"
    return True, ""


def conflicts(e):
    return sum(1 for x in queue if x["n"] == e["n"]) > 1


# ----------------------------------------------------------------------------- the service
def poll_every():
    """How often to ask the service. The real one counts requests against an API key's monthly
    quota, so after 10 quiet minutes the console asks only every QUORUM_IDLE_POLL_S; a key press or
    a change in the queue brings it back to QUORUM_POLL_S."""
    if time.ticks_diff(time.ticks_ms(), last_activity) > IDLE_AFTER_MS:
        return max(POLL_MS, IDLE_POLL_MS)
    return POLL_MS


def fetch_info():
    global info, polls, need_info
    got = svc.safe_info()
    ok, why = policy.valid_info(got, SAFE_ADDR)
    if not ok:
        raise ValueError("bad Safe info: " + why)
    info, polls, need_info = got, 0, False


def fetch_queue():
    """The pending transactions, each checked on its own: one the service mangled is shown as
    refused and cannot stop the others from being listed."""
    global truncated
    nonce = int(info.get("nonce", 0))
    try:
        txs, truncated = svc.pending(nonce), False
    except MemoryError:
        gc.collect()
        txs, truncated = svc.pending(nonce, limit=3), True
        qlog.once("queue truncated to 3: out of memory")
    out = []
    for i, t in enumerate(txs):
        try:
            out.append(entry(t))
        except Exception as ex:
            out.append(bad_entry(t, i, ex))
    return out


def net_work():
    """One poll: the Safe (every INFO_EVERY polls on the real service), then its queue. Runs with
    the timer stopped."""
    global net_ok, net_err, info, queue, last_poll, last_announce, last_activity, dirty, sel, _snap, polls, _txs_seen, declined
    last_poll = time.ticks_ms()
    watch.extend(45000)
    if svc is None:
        net_ok, net_err = False, "no QUORUM_URL in secrets.py"
        return
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), net.last_try) > 30000:
            net.retry()
            _log("wifi: retrying " + SSID)
        net_ok, net_err = False, "no wifi"
    else:
        if not net.up:
            net.joined()
        try:
            polls += 1
            if need_info or not info or svc.sim or polls >= INFO_EVERY:
                fetch_info()
            if svc.sim and qx and me not in owners() and (last_announce == 0 or time.ticks_diff(time.ticks_ms(), last_announce) > 10000):
                last_announce = time.ticks_ms()     # the simulation adds this key as an owner
                if svc.announce(NAME, qx, qy):
                    fetch_info()
            queue = fetch_queue()
            seen_now = tuple(e["h"] for e in queue)
            if _txs_seen is not None and seen_now != _txs_seen and polls:
                fetch_info()                        # something executed or arrived: owners and nonce may have moved
                queue = fetch_queue()
                seen_now = tuple(e["h"] for e in queue)
            _txs_seen = seen_now
            live = set(seen_now)
            for h in list(cache):
                if h not in live:
                    del cache[h]
            declined = set(h for h in declined if h in live)
            net_ok, net_err = True, ""
            if not saved_checked:
                send_saved()
        except Exception as ex:
            net_ok, net_err = False, net.short_err(ex)
            _log("service: %r" % ex)
            qlog.once("service: " + net_err)
    sel = max(0, min(sel, len(queue) - 1))
    snap = (net_ok, net_err, str(info.get("nonce")), threshold(), len(owners()),
            tuple((e["h"], len(e["conf"])) for e in queue))
    if snap != _snap:
        _snap, dirty = snap, True
        last_activity = time.ticks_ms()
    gc.collect()


# ----------------------------------------------------------------------------- review and sign
def pages_of(e):
    items = []
    for i, it in enumerate(e["r"]["items"]):
        items.append(("item", i))
        if it.get("digest"):
            items.append(("calldata", i))    # the raw call, on a page of its own
    if e["why"]:
        return [("refused", 0)] + items
    return [("summary", 0)] + items + [("verify", 0)]


def open_entry(e):
    global cur, pages, page, seen, state, dirty
    cur, pages, page, seen = e, pages_of(e), 0, {0}
    state, dirty = "review", True


def turn(step):
    global page, dirty
    page = max(0, min(len(pages) - 1, page + step))
    seen.add(page)
    dirty = True


def unseen():
    return [i for i in range(len(pages)) if i not in seen]


def hold_need(e):
    return HOLD_RED_MS if e["r"]["level"] == "red" else HOLD_MS


def press_sign():
    global state, hold_t0, page, dirty
    ok, why = can_sign(cur)
    if not ok:
        say("Can't sign: " + why)
        return
    left = unseen()
    if left:
        page = left[0]
        seen.add(page)
        say("See every page first \u00b7 %d more" % len(left))
        return
    state, hold_t0, dirty = "hold", time.ticks_ms(), True


def hold_tick():
    global state, dirty
    if keys.held(SIGN):
        if time.ticks_diff(time.ticks_ms(), hold_t0) >= hold_need(cur):
            sign_it()
        elif _n % 2 == 0:
            dirty = True        # the bar fills ten times a second
    else:
        state = "review"
        say("Let go early \u00b7 not signed")


def signature_for(e, ad, fields, r, s):
    """Layer 3: the confirmation as the transaction service stores it, a contract signature from
    this key's signer proxy carrying the WebAuthn assertion."""
    return decode.hx(webauthn.contract_signature(me, ad, fields, r, s))


def same_chip():
    """Right before a signature: the chip on the bus is still the one read at start. Its serial,
    read again from the chip; and the slot's public key too unless the slot is locked (a locked
    slot's key cannot change, and on a quorum v1 chip each read of it is a use of the key)."""
    if sig.name != "atecc608":
        return True
    s = "".join("%02x" % b for b in sig.chip.serial())
    if row and row.get("locked"):
        return s == serial
    x, y = sig.chip.pubkey(sig.slot)
    return s == serial and "0x%064x" % x == qx and "0x%064x" % y == qy


def sign_it():
    global state, result, dirty, counter, outside, unsent
    e = cur
    state = "working"
    unsent = None           # a failure below must never offer to resend an older signature
    U.draw_working(sys.modules[__name__], "Signing", "The chip signs the hash computed here")
    timer.deinit()
    watch.extend(30000)
    try:
        if not pin_ok or (EXPECT and sig.slot != int(EXPECT.get("slot", 0))):
            raise Exception("the key no longer matches the pin")
        c0 = read_counter()         # first: before anything this console does with the key
        if c0 is not None and counter is not None and c0 != counter:
            outside += c0 - counter
            qlog.write("counter %d before signing, %d expected: %d outside this console" % (c0, counter, c0 - counter))
        if not same_chip():
            raise Exception("the chip or its key changed since start")
        t0 = time.ticks_ms()
        ad, fields, digest = webauthn.assertion(e["mine"])    # e["mine"]: checked equal to the service's hash in entry()
        r, s = sig.sign(digest)
        counter = read_counter()
        if counter is not None:
            store_counter(counter)
        _log("signed #%d in %d ms" % (e["n"], time.ticks_diff(time.ticks_ms(), t0)))
        qlog.write("signed #%d %s counter %s" % (e["n"], e["h"], counter))
        post(e, signature_for(e, ad, fields, r, s))
    except Exception as ex:
        result = (False, "Not signed", ["The chip said:", repr(ex)[:80]])
        _log("sign: %r" % ex)
        qlog.write("sign #%d failed: %r" % (e["n"], ex))
    state, dirty = "result", True
    start_timer()


UNSENT_FILE = "unsent.json"


def save_unsent(e, signature):
    """A signature the service did not take: kept on flash (it is public once posted anyway), so a
    restart does not lose it; sent_saved() tries it again first thing after the next boot."""
    import json
    try:
        with open(UNSENT_FILE, "w") as f:
            json.dump({"h": e["h"], "n": e["n"], "sig": signature}, f)
    except OSError as ex:
        qlog.write("unsent not saved: %r" % ex)


def clear_unsent(h=None):
    import json, os
    try:
        if h is not None and json.load(open(UNSENT_FILE))["h"] != h:
            return
        os.remove(UNSENT_FILE)
    except (OSError, ValueError, KeyError):
        pass


def send_saved():
    """At the first good poll after a boot: a saved signature goes out while the heap is whole.
    Dropped once sent, or once its transaction is no longer in the queue (executed or replaced)."""
    import json
    global saved_checked
    saved_checked = True
    try:
        s = json.load(open(UNSENT_FILE))
    except (OSError, ValueError):
        return
    if s["h"] not in [e["h"] for e in queue]:
        qlog.write("saved signature for #%s dropped: no longer queued" % s.get("n"))
        clear_unsent()
        return
    try:
        ok, detail = svc.confirm(s["h"], s["sig"])
    except Exception as ex:
        ok, detail = False, net.short_err(ex)
    if ok:
        qlog.write("confirmed #%s (the saved signature, after a restart)" % s.get("n"))
        say("Sent the saved signature for #%s" % s.get("n"), 6)
        clear_unsent()
        globals()["need_info"] = True
    else:
        qlog.write("saved signature for #%s refused: %s" % (s.get("n"), detail[:80]))


def post(e, signature):
    global result, unsent, need_info
    U.draw_working(sys.modules[__name__], "Sending", "To the transaction service")
    watch.extend(45000)
    try:
        ok, detail = svc.confirm(e["h"], signature)
    except Exception as ex:
        ok, detail = False, net.short_err(ex)
    if ok:
        unsent = None
        clear_unsent(e["h"])
        have, need = len(e["conf"]) + 1, threshold()
        lines = ["#%d %s" % (e["n"], e["r"]["summary"]), "Approvals now %d of %d" % (have, need)]
        if have >= need:
            lines += ["Ready \u00b7 the proposer executes it"]
        else:
            lines += ["Waiting for %d more" % (need - have)]
        if counter is not None:
            lines += ["Key use #%d" % counter]
        result = (True, "Signed", lines)
        need_info = True
        _log("confirmed #%d" % e["n"])
        qlog.write("confirmed #%d" % e["n"])
    else:
        unsent = (e, signature)
        save_unsent(e, signature)
        result = (False, "Not sent", ["Signed, but the service said:", detail[:90]])
        _log("confirm #%d refused: %s" % (e["n"], detail))
        qlog.write("confirm #%d refused: %s" % (e["n"], detail[:80]))


def reject():
    global state, dirty, unsent
    e = cur
    declined.add(e["h"])
    if unsent and unsent[0]["h"] == e["h"]:
        unsent = None
    clear_unsent(e["h"])
    state, dirty = "home", True
    say("Rejected #%d on this console" % e["n"])
    if svc and svc.sim:
        timer.deinit()
        try:
            svc.declined(e["h"], NAME)     # the simulation logs it; a real service has no such thing
        finally:
            start_timer()


# ----------------------------------------------------------------------------- ui tick
def handle(k):
    global state, sel, dirty, last_poll
    if state in ("nochip", "pinfail"):
        if k == "A":
            probe_chip()            # counts first (boot_count), then reads the key: on a sealed chip, a use of it
            if state == "boot":
                state = "home"
                start_watch()
            own_reads(boot_count)
            dirty = True
    elif state == "crashed":
        if k == BACK:
            machine.reset()
    elif state in ("home", "boot"):
        if k == "down" and queue:
            sel = min(len(queue) - 1, sel + 1)
        elif k == "up":
            sel = max(0, sel - 1)
        elif k in (SIGN, "right") and queue:
            open_entry(queue[sel])
        elif k == BACK:
            state = "owners"
        elif k in ("X", "press"):
            state = "device"
        if outside:
            outside_seen()
        dirty = True
    elif state in ("owners", "device"):
        if k in (BACK, REJECT, SIGN, "left", "X"):
            state = "home"
        dirty = True
    elif state == "review":
        if k in NEXT:
            turn(1)
        elif k in PREV:
            turn(-1)
        elif k == BACK:
            state = "home"
            dirty = True
        elif k == REJECT:
            reject()
        elif k == SIGN:
            press_sign()
    elif state == "result":
        if k == SIGN and unsent:
            timer.deinit()
            try:
                post(*unsent)
            finally:
                start_timer()
        elif k in (SIGN, BACK, REJECT):
            state, last_poll = "home", 0     # poll now: the queue has moved
        dirty = True


def led_tick():
    if any(waiting(e) for e in queue):
        if _n % 10 == 0:
            net.led.toggle()        # blinks while something waits for this key
    elif _n % 20 == 0:
        net.led.value(1 if net.up else 0)


def tick(t):
    global _busy, _n, dirty, state, splash_until, msg, last_activity, fails
    if _busy:
        return
    _busy = True
    try:
        _n += 1
        watch.extend(5000)
        net.poll_accept()
        if state in ("home", "boot") and (last_poll == 0 or time.ticks_diff(time.ticks_ms(), last_poll) >= poll_every()):
            timer.deinit()      # no timer events pile up while HTTP and hashing block
            try:
                net_work()
            finally:
                start_timer()
        pressed = keys.pressed()
        if pressed:
            last_activity = time.ticks_ms()
        for k in pressed:
            handle(k)
        if state == "hold":
            hold_tick()
        if splash_until:
            if time.ticks_diff(splash_until, time.ticks_ms()) > 0:
                if _n % 3 == 0:
                    dirty = True
            else:
                splash_until, dirty = 0, True
                if state == "boot":
                    state = "home"
        if msg and time.ticks_diff(msg_until, time.ticks_ms()) <= 0:
            msg, dirty = "", True
        led_tick()
        if svc and svc.lost and state == "home":
            restart_for_memory()
        if dirty:
            dirty = False
            if state == "boot" and splash_until:
                splash.draw()
            else:
                U.draw(sys.modules[__name__])
        fails = 0
    except Exception as e:
        _log("ui: %r" % e)
        sys.print_exception(e)
        fails += 1
        if fails == 1:
            qlog.write("tick: %r" % e)
        if fails >= CRASH_AFTER and state != "crashed":
            crashed(e)
    finally:
        _busy = False


def crashed(e):
    """Too many failures in a row: stop somewhere plain that signs nothing, and say so."""
    global state, cur
    state, cur = "crashed", None
    qlog.write("crashed after %d failed ticks: %r" % (fails, e))
    try:
        with open("error.log", "w") as f:
            sys.print_exception(e, f)
    except Exception:
        pass
    try:
        U.draw_crashed(sys.modules[__name__], repr(e))
    except Exception:
        pass


def restart_for_memory():
    """The HTTPS reserve could not be taken back after a call: the heap has split, and every call
    from here would fail with OSError 12. Only on the home screen (never mid-review or signing):
    note it, keep any unsent signature (it is on flash already), and start again with a whole heap."""
    import os
    try:
        last = int(open("restart.txt").read())
    except (OSError, ValueError):
        last = 0
    now = time.time()
    if 0 < now - last < 600:
        return                  # at most one such restart every 10 minutes
    try:
        with open("restart.txt", "w") as f:
            f.write(str(now))
    except OSError:
        pass
    qlog.write("restart: the HTTPS reserve could not be taken back (heap in pieces)")
    machine.reset()


def outside_seen():
    """The person has seen the "signed outside this console" warning (any key on home)."""
    global outside, dirty
    outside, dirty = 0, True


# ----------------------------------------------------------------------------- entry
def start_timer():
    global timer
    timer = machine.Timer(period=50, mode=machine.Timer.PERIODIC, callback=tick)


def start_watch():
    """The watchdog, on the production image, once the chip is the pinned one (watch.py)."""
    if PROD and pin_ok and state not in ("pinfail", "nochip", "unconfigured"):
        watch.start()
        qlog.write("watchdog on")


def start():
    global d, keys, svc, dirty, splash_until, last_activity, state
    splash.TITLE = "picoquorum"
    qlog.write("boot %s %s reset cause %d" % (image.IMAGE, image.BUILD, machine.reset_cause()))
    U.use(getattr(secrets, "QUORUM_THEME", "dark") if secrets else "dark")
    # Every font now, while the heap is whole. They are loaded on first use otherwise, and bold26
    # alone is one 10.9 KB block: after a tour of the chip map the heap was too fragmented for it,
    # and every redraw of a review page failed with MemoryError (2026-09-25, on the board).
    import fonts
    for name in fonts.FILES:
        fonts.get(name)
    gc.collect()
    d = splash.begin()
    keys = L.Keys()
    splash.step("chip", "probing i2c...", L.GREY)
    probe_chip()
    if state == "nochip":
        splash.step("chip", "none on i2c", L.RED)
    else:
        pinned = " \u00b7 pinned" if EXPECT and pin_ok else (" \u00b7 PIN FAIL" if not pin_ok else "")
        name = (chip["name"] + " \u00b7 ") if chip else ""
        splash.step("chip", "%s%s%s" % (name, fingerprint() or "no key", pinned), L.RED if not qx or not pin_ok else L.GREEN)
        check_counter()
    w = network.WLAN(network.STA_IF)
    if secrets and not w.isconnected() and not net.tried:
        try:
            net.connect(progress=lambda ms: splash.spin("wifi", ("join " + SSID)[:12] + " A skips") or bool(keys.pressed()))
        except Exception as e:
            print("wifi:", e)
    splash.wifi_row(w, SSID if secrets else "")
    host = (BASE or "").replace("http://", "").replace("https://", "").rstrip("/")
    splash.step("app", ("safe svc " + host)[:24] if BASE else "no QUORUM_URL", L.GREY if BASE else L.RED)
    if UNCONFIGURED:
        state = "unconfigured"
    elif BASE:
        verify = PROD or bool(getattr(secrets, "QUORUM_TLS_VERIFY", True))
        svc = txservice.Service(BASE, txservice.checksum(SAFE_ADDR), API_KEY, verify=verify, floor=image.DATE)
    splash_until = time.ticks_add(time.ticks_ms(), 1500)
    last_activity = time.ticks_ms()
    dirty = True
    start_timer()
    start_watch()


def stop():
    if timer:
        timer.deinit()
