# The UI lab's hands, on the emulator: presses the console's buttons through its own tick, with
# console_test's fake service, keys and clock and the virtual chip, and says what the screen showed
# after each press. tools/uilab/build.mjs runs it and writes the map and the explorer from what it
# returns. Nothing here draws or decides: every frame is one the firmware sent to the panel.
import sys
import json
import hashlib
import binascii
import console_test as T
import lcd as L

Q = None
_seen = set()       # the frames already handed to build.mjs, by id
_shown = []         # the frames the panel got since the last take(), oldest first
_new = {}           # id -> hex of the ones build.mjs has not had yet
_fx = []            # what the look's effect() answered since the last take(), when it has one
PRESS_MS = 3500     # the clock moves this much with each press: a person, reading. The last message (3 s) has gone
TICK_MS = 50        # the console's own timer


class _Gc:
    """The Device screen's free memory, one figure on every run. The emulator's heap is not a board's
    and moves a little each time, which would make that one picture a new file at every build."""

    def mem_free(self):
        return 1024 * 1024


def _frame(buf):
    i = binascii.hexlify(hashlib.sha256(buf).digest()).decode()[:12]
    if i not in _seen:
        _seen.add(i)
        _new[i] = binascii.hexlify(buf).decode()
    if not _shown or _shown[-1] != i:
        _shown.append(i)


def boot(name):
    """A console on board `name`, started, on home with nothing queued."""
    global Q
    c = T.chip(counter=7)
    # The virtual chip's key, the same on every run, so the same pictures come out: a test key made
    # from this sentence, an owner of nothing.
    c.keys[0] = int.from_bytes(hashlib.sha256(b"Picoquorum UI lab: the emulator's test key").digest(), "big")
    c.save()
    Q = T.fresh(extra='BOARD = "%s"' % name)
    import board
    assert board.BOARD == name and Q.THREE, board.BOARD
    try:
        import crt
        crt.FX = False      # a look with effects (console-rp's): each page goes out whole here
    except ImportError:
        pass
    import quorum_ui_s
    quorum_ui_s.time = Q.time                   # the hold's bar reads the clock the console does
    about = quorum_ui_s.draw_device

    def draw_device(q):                         # it imports gc itself: hand it _Gc for this one draw
        was = sys.modules.get("gc")
        sys.modules["gc"] = _Gc()
        try:
            about(q)
        finally:
            if was is None:
                del sys.modules["gc"]
            else:
                sys.modules["gc"] = was
    quorum_ui_s.draw_device = draw_device
    U = Q.U
    if hasattr(U, "effect"):                    # which effect it asks for is still recorded
        real = U.effect

        def spy(q, prev, now):
            fx = real(q, prev, now)
            _fx.append(fx)
            return fx
        U.effect = spy
    d = Q.d
    full = bytearray(L.W * L.H * 2)

    def show():
        n = len(d.buffer) // (2 * L.W)
        full[d.y0 * L.W * 2:(d.y0 + n) * L.W * 2] = d.buffer
        if d.y0 + n >= L.H:
            _frame(full)
    d.show = show
    return json.dumps({"board": name, "w": L.W, "h": L.H, "ui": U.__name__, "railY": list(board.RAIL_Y) if board.RAIL_Y else None,
                       "names": [board.NAMES[k] for k in ("D0", "D1", "D2")], "tabs": list(Q.TABS)})


def home(txs=(), **kw):
    """Back on home's first tab with this queue, nothing declined, no message, no key held."""
    Q.declined.clear()
    Q.keys.down.clear()
    Q.unsent = Q.ask = Q.incoming = None
    T.serve(Q, list(txs), **kw)
    Q.state, Q.tab, Q.sel, Q.osel, Q.dsel, Q.msg = "home", 0, 0, 0, 0, ""
    Q._n = 0                # the tick count: a hold's bar is drawn on even ticks, the same ones in every flow
    Q.dirty = True


def tick(*keys, ms=PRESS_MS):
    """One tick of the console's own loop, ms later, with these keys pressed. A tick that raised
    stops the walk: a flow is a test too."""
    Q.keys.pressed = lambda: list(keys)
    Q._busy, Q.splash_until = False, 0
    Q.time.now += ms
    Q.last_poll = Q.time.now            # no poll in the middle of a walk
    Q.tick(None)
    Q.keys.pressed = lambda: []
    assert not Q.fails, "the tick failed: " + open("log.txt").read()[-300:]


def view():
    """Which screen this is, as far as arriving at it goes: the state, and its tab or kind of page."""
    s = Q.state
    if s in ("review", "hold"):
        return s + "/" + Q.pages[Q.page][0]
    if s == "home":
        return "home/" + Q.TABS[Q.tab]
    if s == "key":
        return "key/" + ("code", "full")[Q.kpage]
    if s == "result":
        return "result/" + ("signed" if Q.result and Q.result[0] else "not-sent")
    if s == "ask":
        return "ask/" + Q.ask["kind"]
    return s


def take():
    """What happened since the last take(): the frames shown, where the console is now, and the
    frames build.mjs has not had yet."""
    e = Q.cur
    out = {"frames": _shown[:], "view": view(), "state": Q.state, "msg": Q.msg, "fx": [f for f in _fx if f],
           "red": bool(Q.state in ("review", "hold") and e and (e["why"] or e["r"]["level"] == "red")), "new": dict(_new)}
    del _shown[:]
    del _fx[:]
    _new.clear()
    return json.dumps(out)


def run(code):
    """A flow's setup or after, here, where Q is the console."""
    exec(code, globals())


def step(do):
    """One step of a flow: "D0" "D1" "D1L" "D2" (a press), "hold D2" (pressed and kept down),
    "wait 1200" (that many ms pass in 50 ms ticks, whatever is down stays down) or "release"."""
    w = do.split()
    if w[0] == "hold":
        Q.keys.down.add(w[1])
        tick(w[1])
    elif w[0] == "wait":
        for _ in range(int(w[1]) // TICK_MS):       # tick by tick, as the timer does: a hold's bar fills
            tick(ms=TICK_MS)
    elif w[0] == "release":
        Q.keys.down.clear()
        tick()
    else:
        tick(w[0])
    return take()


# The queues the flows are served, by name.
def _word(v):
    return "%064x" % (int(v, 16) if isinstance(v, str) else v)


def queue(name):
    if name == "three":         # a plain send, an unknown call (red), and one the service lies about (refused)
        return [T.tx(Q, 0, value=5 * 10**16), T.tx(Q, 1, to=T.OTHER, data="0xdeadbeef"), T.tx(Q, 2, tamper=True)]
    if name == "send":
        return [T.tx(Q, 0, value=5 * 10**16)]
    if name == "owner":         # the Safe swaps an owner: red
        return [T.tx(Q, 0, to=T.SAFE, data="0xe318b52b" + _word(1) + _word(T.BOB) + _word("0x90f79bf6eb2c4f870365e785982e1f101e93b906"))]
    return []


def ask_safes():
    """The computer on the USB link asks to set the Safes: on screen at the next tick."""
    import usblink
    usblink.send = lambda d: None
    usblink.host, usblink.mode, usblink.open_ask, usblink.time = Q, "console", None, Q.time
    usblink.handle(json.dumps({"id": 1, "op": "safes", "safes": [{"chainId": T.CHAIN, "address": T.SAFE, "name": "Family Safe"}]}))


def fail_posts(on):
    """Safe's service stops taking confirmations (on), or takes them again."""
    if on:
        T.SVC.post = lambda url, json=None, headers=None, timeout=None: (_ for _ in ()).throw(OSError(12))
    else:
        try:
            del T.SVC.post
        except AttributeError:
            pass
