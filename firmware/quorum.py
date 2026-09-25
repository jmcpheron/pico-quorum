# PicoQuorum's console: the Safe's queue, each transaction in plain language, and a signature from
# the chip only after the person has seen every page and held A. Polls Safe's transaction service
# over WiFi (for now tools/quorum's simulated Safe on the laptop).
#
# The loop is wallet.py's: one 50 ms Timer, keys every tick, redraw only when something changed,
# and the timer stopped around anything that blocks (HTTP, hashing, the chip). X opens the chip
# map (slots.py) exactly as in the wallet, LAB and snake included.
#
# Trust: the service is not trusted. Each transaction is rehashed here (safe_tx.py) from the same
# fields decode.py puts on the screen, with the chain and Safe pinned in quorum_cfg.py. If the
# service's safeTxHash or Safe differs, the transaction is REFUSED and cannot be signed. The chip
# signs the hash computed here, never a string the service sent: wrapped as a WebAuthn assertion
# (webauthn.py), because onchain this key owns the Safe through Safe's passkey signer.
#
#   import lcd; import quorum; quorum.start()      (main.py does this)
import sys, time, machine, network, gc
import lcd as L
import net
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
# The Safe this console signs for: QUORUM_SAFE in secrets.py (a Safe on Base Sepolia or Base, made
# in the Safe web app), else the pinned Family Safe on the laptop. Pinned on the device either way.
SAFE = (getattr(secrets, "QUORUM_SAFE", None) if secrets else None) or CFG["safes"][0]
CHAIN = SAFE["chainId"]
SAFE_ADDR = SAFE["address"].lower()
BASE = (getattr(secrets, "QUORUM_URL", None) or getattr(secrets, "APP_URL", None)) if secrets else None
NAME = getattr(secrets, "DEVICE_NAME", "picoquorum") if secrets else "picoquorum"
SSID = getattr(secrets, "WIFI_SSID", "") if secrets else ""
SOFT_OK = bool(getattr(secrets, "ALLOW_SOFT_KEY", False)) if secrets else False
POLL_MS = int(getattr(secrets, "QUORUM_POLL_S", 3) if secrets else 3) * 1000
IDLE_POLL_MS = int(getattr(secrets, "QUORUM_IDLE_POLL_S", 120) if secrets else 120) * 1000
IDLE_AFTER_MS = 10 * 60 * 1000
HOLD_MS, HOLD_RED_MS = 2000, 3000       # A held this long to sign; longer when any page is red

# Keys by role. The console's own controls (a guarded Sign button, a paging dial) remap here.
SIGN, REJECT, BACK = "A", "Y", "B"
NEXT, PREV = ("down", "right"), ("up", "left")

d = None
keys = None
sig = None          # the signer backend (the chip)
svc = None          # txservice.Service
timer = None
state = "boot"      # boot | home | review | hold | working | result | owners | chip | nochip
slots_ui = None     # the chip map, while it is open (chip_ui)
_chip_mods = ()     # the modules it loaded, dropped again when it closes
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
    ctx = decode.context(CFG, SAFE_ADDR, {me: "This key"} if me else None)
    cache.clear()
    last_announce = 0


def key_changed():
    """The chip map made or switched a key: everything about "me" starts over."""
    global last_poll
    read_key()
    last_poll = 0


def probe_chip():
    global sig, state, slots_ui
    sig = S.load()
    if sig.name != "atecc608" and not SOFT_OK:
        state = "nochip"
        return
    if state == "nochip":
        state = "boot"
    read_key()


def chip_ui():
    """The chip map (slots.py and the screens it imports), loaded on the first X and dropped on the
    way back home. It is about 80 KB of source compiled on the Pico; loaded at start it left the
    heap in pieces too small for HTTPS: with 116 KB free, no 8 KB block was left, and every call to
    api.safe.global failed with OSError 12 (2026-09-25, on the board)."""
    global slots_ui, _chip_mods
    if slots_ui is None:
        before = set(sys.modules)
        if svc:
            svc.release()       # the HTTPS reserve makes room for compiling the chip map
        gc.collect()
        import slots
        slots_ui = slots.SlotsUI(d, sig, key_changed)
        _chip_mods = tuple(m for m in sys.modules if m not in before)
    return slots_ui


def chip_done():
    global slots_ui, _chip_mods
    slots_ui = None
    for m in _chip_mods:
        sys.modules.pop(m, None)
    _chip_mods = ()
    gc.collect()
    if svc:
        svc.hold()


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
        if (t.get("safe") or "").lower() != SAFE_ADDR:
            e["why"] = "It is for another Safe, %s, not the one this console signs for." % U.short(t.get("safe") or "?")
        else:
            try:
                e["mine"] = decode.hx(safe_tx.from_service(CHAIN, t))
                if e["mine"] != h:
                    e["why"] = "The service wants a signature over a hash that these fields do not produce. Signing it could approve something else entirely."
            except Exception as ex:
                e["why"] = "Its fields do not hash: %s" % ex
        try:
            e["r"] = decode.review(t, ctx)
        except Exception as ex:
            e["r"] = {"summary": "Unreadable", "level": "red", "items": []}
            e["why"] = e["why"] or "It could not be decoded: %s" % ex
        cache[h] = e
    e["conf"] = [c["owner"].lower() for c in (t.get("confirmations") or [])]
    return e


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


def net_work():
    """One poll: the Safe, then its queue. Runs with the timer stopped."""
    global net_ok, net_err, info, queue, last_poll, last_announce, last_activity, dirty, sel, _snap
    last_poll = time.ticks_ms()
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
            info = svc.safe_info()
            if qx and me not in owners() and (last_announce == 0 or time.ticks_diff(time.ticks_ms(), last_announce) > 10000):
                last_announce = time.ticks_ms()     # the simulation adds this key as an owner; a real service says 404
                if svc.announce(NAME, qx, qy):
                    info = svc.safe_info()
            txs = svc.pending(int(info.get("nonce", 0)))
            queue = [entry(t) for t in txs]
            live = set(e["h"] for e in queue)
            for h in list(cache):
                if h not in live:
                    del cache[h]
            net_ok, net_err = True, ""
        except Exception as ex:
            net_ok, net_err = False, net.short_err(ex)
            _log("service: %r" % ex)
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


def sign_it():
    global state, result, dirty
    e = cur
    state = "working"
    U.draw_working(sys.modules[__name__], "Signing", "The chip signs the hash computed here")
    timer.deinit()
    try:
        t0 = time.ticks_ms()
        ad, fields, digest = webauthn.assertion(e["mine"])    # e["mine"]: checked equal to the service's hash in entry()
        r, s = sig.sign(digest)
        _log("signed #%d in %d ms" % (e["n"], time.ticks_diff(time.ticks_ms(), t0)))
        post(e, signature_for(e, ad, fields, r, s))
    except Exception as ex:
        result = (False, "Not signed", ["The chip said:", repr(ex)[:80]])
        _log("sign: %r" % ex)
    state, dirty = "result", True
    start_timer()


def post(e, signature):
    global result, unsent
    U.draw_working(sys.modules[__name__], "Sending", "To the transaction service")
    try:
        ok, detail = svc.confirm(e["h"], signature)
    except Exception as ex:
        ok, detail = False, net.short_err(ex)
    if ok:
        unsent = None
        have, need = len(e["conf"]) + 1, threshold()
        lines = ["#%d %s" % (e["n"], e["r"]["summary"]), "Approvals now %d of %d" % (have, need)]
        if have >= need:
            lines += ["Ready \u00b7 the proposer executes it"]
        else:
            lines += ["Waiting for %d more" % (need - have)]
        result = (True, "Signed", lines)
        _log("confirmed #%d" % e["n"])
    else:
        unsent = (e, signature)
        result = (False, "Not sent", ["Signed, but the service said:", detail[:90]])
        _log("confirm #%d refused: %s" % (e["n"], detail))


def reject():
    global state, dirty
    e = cur
    declined.add(e["h"])
    state, dirty = "home", True
    say("Rejected #%d on this console" % e["n"])
    if svc:
        timer.deinit()
        try:
            svc.declined(e["h"], NAME)     # the simulation logs it; a real service has no such thing
        finally:
            start_timer()


# ----------------------------------------------------------------------------- ui tick
def handle(k):
    global state, sel, dirty, last_poll
    if state == "nochip":
        if k == "A":
            probe_chip()
            dirty = True
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
            chip_ui().open("zones")
            state = "chip"
        dirty = True
    elif state == "owners":
        if k in (BACK, REJECT, SIGN, "left"):
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
    global _busy, _n, dirty, state, splash_until, msg, last_activity
    if _busy:
        return
    _busy = True
    try:
        _n += 1
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
        if state == "chip":
            if slots_ui.tick(pressed, keys) == "home":
                state, dirty = "home", True
                chip_done()
            pressed = ()
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
        if dirty:
            dirty = False
            if state == "chip":
                slots_ui.draw()
            elif state == "boot" and splash_until:
                splash.draw()
            else:
                U.draw(sys.modules[__name__])
    except Exception as e:
        _log("ui: %r" % e)
        sys.print_exception(e)
    finally:
        _busy = False


# ----------------------------------------------------------------------------- entry
def start_timer():
    global timer
    timer = machine.Timer(period=50, mode=machine.Timer.PERIODIC, callback=tick)


def start():
    global d, keys, svc, dirty, splash_until, last_activity
    splash.TITLE = "picoquorum"
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
    splash.step("chip", "none on i2c" if state == "nochip" else "%s key %s" % (sig.name, fingerprint() or "none"),
                L.RED if state == "nochip" or not qx else L.GREEN)
    w = network.WLAN(network.STA_IF)
    if secrets and not w.isconnected() and not net.tried:
        try:
            net.connect(progress=lambda ms: splash.spin("wifi", ("join " + SSID)[:12] + " A skips") or bool(keys.pressed()))
        except Exception as e:
            print("wifi:", e)
    splash.wifi_row(w, SSID if secrets else "")
    host = (BASE or "").replace("http://", "").replace("https://", "").rstrip("/")
    splash.step("app", ("safe svc " + host)[:24] if BASE else "no QUORUM_URL", L.GREY if BASE else L.RED)
    if BASE:
        svc = txservice.Service(BASE, txservice.checksum(SAFE_ADDR), getattr(secrets, "QUORUM_API_KEY", None))
    splash_until = time.ticks_add(time.ticks_ms(), 1500)
    last_activity = time.ticks_ms()
    dirty = True
    start_timer()


def stop():
    if timer:
        timer.deinit()
