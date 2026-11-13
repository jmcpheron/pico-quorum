# The owner's key on console-rp: keypick_s's Make, Pick and Keep in the console's CRT look
# (quorum_ui_crt.py), on keyflow.OwnKey, the buttons under the screen as the console has them:
# D0 ■ out, D1 ● next, D2 ▲ do.
#   Make     what K0 found (no key yet, or one from before that Make replaces), then ▲ Make. The chip
#            makes the key; nothing leaves it but the public half.
#   Pick     the owner address's blockie, big, and its two ends, landed after a shuffle. ■ New makes
#            another, as many times as anyone likes (until the seal no key here has signed for a Safe),
#            ● Full shows the address in full, ▲ Choose goes on to Keep.
#   Keep     a red page: ▲ held 3 s runs the test signatures (C5), the seal (C6) and the data lock
#            (C7-C9) in one go, forever. ■ goes back.
#   Finish   (after a restart between the seal and the data lock) ▲ held 3 s: C7-C9.
#   Pin      (after a restart between the data lock and the pin) ▲: C10, then pin.json.
#   Done     the key sealed and pinned. ▲ starts the console (a restart).
#   Stop     red, nothing to press: a chip the bench never prepared, one set up as something else,
#            or one sealed by something other than this flow (keyflow.OwnKey).
# The permission is signer.own_key_step: on the console-rp image, a prepared quorum v1 chip, and this
# screen's arm, given for one call alone by the ▲ press (Make, New) or the 3 s hold (Keep, Finish),
# exactly as keypick_s.step_run gives it. Nothing else on the image arms the signer.
#
# The effects (crt.py): a K0 that found nothing locks in, a key lands and locks in, Sealed locks in;
# a red page arrives torn. None while ▲ is held, none on a shuffle frame.
#
# While the chip works (Make, then Keep's test signatures, seal, record, data lock and pin, 20 s or
# so), the busy page draws the key's chip: a light running round its legs, hex flickering in its
# body, now and then a slip sideways. A soft timer sends that one 60 x 60 corner, from the noise
# strip's memory (crt.tile), between the steps' own work; it stops before any other page is drawn.
# Beside it, Keep's steps tick off as each one passes: what the steps returned, not a show. Each
# step's result, K0's too, goes to the log (qlog: log.txt, and the computer over the link) as
# prepare.py's do.
import os
import time
from binascii import hexlify
import machine
import blockies
import ceremony_ui
import qlog
import crt
import quorum_ui as B
import quorum_ui_s as Q
import quorum_ui_crt as C
import signer as S
import keypick_s

W, H, M, R, TW, HEAD, FOOT = Q.W, Q.H, Q.M, Q.R, Q.TW, Q.HEAD, Q.FOOT
KEEP = (("C5", "Test signatures"), ("C6", "Seal"), ("C8", "Record"), ("C9", "Data lock"), ("C10", "Pin"))
TS, CB = 60, 32                     # the chip's picture, and its body, square
CX0, CY0 = 12, HEAD + (FOOT - HEAD - TS) // 2
RX, RY0, PITCH = 82, HEAD + 24, 15  # the steps beside it
_P = (17, 22, 27, 32, 37, 42)       # six legs a side, clockwise from the top left
LEGS = tuple([(x, 7, 3, 6) for x in _P] + [(47, y, 6, 3) for y in _P] +
             [(x, 47, 3, 6) for x in reversed(_P)] + [(7, y, 6, 3) for y in reversed(_P)])
GLOW = 7                            # legs lit behind the light, fading
OPS = {"make": ("ALLOW_GENKEY", "genkey0"), "keep": ("ALLOW_LOCK", "lock_slot0"), "finish": ("ALLOW_LOCK", "lock_data")}
STOP = {"unprepared": ("Not prepared", "This chip was never set up at the bench, so no key can be made in it here. Nothing on it has changed."),
        "other": ("Not this console's chip", "It is set up as something other than quorum v1. Nothing here uses it."),
        "elsewhere": ("Sealed elsewhere", "Its key was sealed, but not by this console. Nothing here locks or pins it.")}
TITLES = dict(ceremony_ui.TITLES, K0="No-key check")
OK = ("OK", "ok", "on_ok")
BACK = ("Back", "raised", "text")


class UI(keypick_s.UI):
    HOLD_KEY = {}                   # every hold on D2 ▲
    KEEP_BACK = "D0"
    NEW, CHOOSE = "D0", "D2"

    def __init__(self, d, keys, sig, ceremony):
        super().__init__(d, keys, sig, "dark", ceremony)
        C.use("crt")
        C.wrap(d)
        self._view = None           # what the screen showed, for the effect
        self._fx = None
        self._seed = "0x" + hexlify(os.urandom(20)).decode()     # Make's picture: random bytes, not a key
        self._todo, self._ok, self._now = (), set(), None        # the busy page's steps, passed, running
        self._busy = self._paint = False                         # the busy page up; the page going out
        self._tm, self._tile, self._f, self._col = None, None, 0, None

    def arm(self):
        pass                        # no 60 s arm here (ceremony_ui's D0+D1 hold): only step_run's, per call

    # --- which screen ----------------------------------------------------------------
    def kind(self, st):
        if self.result is not None:
            return "result"
        if st == "done":
            return "done"
        if st in STOP:
            return "stop"
        if st == "K0":
            return "k0"
        if st == "C10":
            return "pin"
        return super().kind(st)

    def need(self, kind):
        """Why this page's action can't run here, or "": own_key_step, or ALLOW_* on a dev board."""
        if kind not in OPS:
            return ""
        name, op = OPS[kind]
        return "" if S.flag(name) or S.own_key_step(self.c.cfg, op) else "not a chip prepared for this"

    # --- the buttons -----------------------------------------------------------------
    def tick(self, pressed):
        """-> "console" once the key is done and ▲ is pressed; else None."""
        st = self.c.step()
        kind = self.kind(st)
        if kind == "k0":
            self.log(("K0",) + tuple(self.c.run("K0")))      # read only: no press needed
            self.dirty = True
        elif kind == "result":
            if "D2" in pressed:
                self.result, self.dirty = None, True
        elif kind == "pin":
            if "D2" in pressed:
                self.pin()
        elif kind == "done":
            if "D2" in pressed:
                return "console"
        elif kind != "stop":
            super().tick(pressed)
        return None

    def step_run(self, step):
        """keypick_s's, its result in the log and on the busy page's list."""
        self._now = step
        self.rows()
        out = super().step_run(step)
        self._now = None
        if out[1]:
            self._ok.add(step)
        self.log(out)
        self.rows()
        return out

    def log(self, out):
        step, ok, checks, msg = out
        qlog.write("key %s %s %s: %s | %s" % (self.c.serial, step, "ok" if ok else "STOPPED",
                                              "; ".join("%s %s" % (k, "ok" if g else "FAIL") for k, g in checks), msg))

    def do_keep(self, st):
        self._todo, self._ok = KEEP, set()
        try:
            super().do_keep(st)
            self.after()
        finally:
            self.spin_stop()

    def do_finish(self, st):
        self._todo, self._ok = KEEP[2:], set()
        try:
            super().do_finish(st)
            self.after()
        finally:
            self.spin_stop()

    def after(self):
        """The data lock done: C10 and the pin straight away, under a busy page."""
        self.done = False
        if self.result is None and self.c.step() == "C10":
            self.pin()

    def pin(self):
        if not self._todo:
            self._todo, self._ok = KEEP[4:], set()
        try:
            self.d.frames(self._busy_page, "Checking the chip", "then pinning this console to it")
            out = self.step_run("C10")
        finally:
            self.spin_stop()
        if not out[1]:
            self.result = out
        self.dirty = True

    # --- the pictures ----------------------------------------------------------------
    def draw(self):
        if not self.dirty:
            return
        self.spin_stop()
        self._busy, self._todo = False, ()
        st = self.c.step()
        kind = self.kind(st)
        self.dirty = False
        if kind == "k0":
            return
        now = (kind, self.page if kind in ("pick", "full") else "", self.tries, self.result is not None)
        self._fx = None if self.held_since is not None or now == self._view else self.effect(self._view, now)
        self._view = now
        self.d.frames(getattr(self, "_" + kind), st)

    def effect(self, prev, now):
        k = now[0]
        if k == "result":
            return "lock" if self.result[1] else "strong"
        if k in ("stop", "keep", "finish"):
            return "strong"
        if k == "pick" and prev and prev[0] == "full":
            return "short"
        if k == "full":
            return "short"
        if k in ("make", "pick", "done"):
            return "lock"
        return "tear"

    def show(self, red=False):
        fx, self._fx = self._fx, None
        C.show(self.d, fx, red, self.keys.keys)

    def foot(self, labels, red=False, hold=None):
        Q.slots(self.d, labels, "bad_bg" if red else "bg", hold)

    # --- the busy page: the chip at work, and Keep's steps ----------------------------
    BUSY = {"Keeping it": "Sealing it"}     # keypick_s's titles, in this board's words (Seal, not Keep)

    def _busy_page(self, title, sub):
        self.spin_stop()
        d = self.d
        d.fill(B.c("bg"))
        Q.header(d, "Your key", "")
        title = self.BUSY.get(title, title)
        B.txt(d, B.fit(title + "…", R - RX, "bold14"), RX, HEAD + 4, "bold14")
        self._busy = True
        if self._todo:
            self.rows(push=False)
        else:
            B.para(d, sub, RX, RY0, R - RX, "sans12", "muted", "bg", 14, FOOT - 2)
        self.draw_chip(d, CX0, CY0, self._f)
        self.foot((None, None, None))
        C.show(d)
        self.spin_start()

    def rows(self, push=True):
        """Keep's steps beside the chip: passed (a check), running (a ring), to come (a dot)."""
        if not self._busy or not self._todo:
            return
        d, y0 = self.d, RY0 - 2
        d.fill_rect(RX - 2, y0, W - RX + 2, FOOT - y0, B.c("bg"))
        scan = B.c(C.SCAN["bg"])
        for y in range(HEAD + 2, FOOT, 3):
            if y >= y0:
                d.hline(RX - 2, y, W - RX + 2, scan)
        y = RY0
        for step, label in self._todo:
            if step in self._ok:
                B.mark(d, True, RX + 5, y + 7, 5)
            elif step == self._now:
                d.ellipse(RX + 5, y + 7, 4, 4, B.c("stake"))
            else:
                d.fill_rect(RX + 4, y + 6, 3, 3, B.c("faint"))
            B.txt(d, B.fit(label, R - RX - 16, "sans12"), RX + 16, y, "sans12",
                  "text" if step in self._ok or step == self._now else "faint")
            y += PITCH
        if push:
            self._paint = True          # the timer waits: one thing on the panel's bus at a time
            try:
                self.draw_chip(d, CX0, CY0, self._f)    # the chip as the panel shows it, under these rows
                crt.page(d, y0, FOOT - y0, y0)
            finally:
                self._paint = False

    def colours(self):
        if self._col is None:
            lit, dim = (200, 214, 255), B.rgb("raised")
            glow = [B.c(tuple(lit[i] + (dim[i] - lit[i]) * k // (GLOW - 1) for i in range(3))) for k in range(GLOW)]
            self._col = (B.c("bg"), B.c(C.SCAN["bg"]), glow, B.c("surface"), B.c("faint"), B.c("muted"), B.c("ok"))
        return self._col

    def draw_chip(self, fb, ox, oy, f):
        """The chip at frame f, its top left at (ox, oy): the light on leg f % 24, the body's hex."""
        bg, scan, glow, body, edge, muted, ok = self.colours()
        fb.fill_rect(ox, oy, TS, TS, bg)
        for y in range((HEAD + 2 - CY0) % 3, TS, 3):         # the page's scanlines, where it sits on screen
            fb.hline(ox, oy + y, TS, scan)
        head, n = f % len(LEGS), len(LEGS)
        for i, (x, y, w, h) in enumerate(LEGS):
            k = (head - i) % n
            fb.fill_rect(ox + x, oy + y, w, h, glow[k if k < GLOW else GLOW - 1])
        fb.fill_rect(ox + 14, oy + 14, CB, CB, body)
        fb.rect(ox + 14, oy + 14, CB, CB, edge)
        fb.fill_rect(ox + 17, oy + 17, 2, 2, edge)
        r = os.urandom(4)
        fb.text("%02x" % r[0], ox + 22, oy + 18, ok if r[2] < 16 else edge)
        fb.text("608", ox + 18, oy + 26, muted)
        fb.text("%02x" % r[1], ox + 22, oy + 35, ok if r[3] < 16 else edge)
        return r

    def spin_start(self):
        if not crt.FX or self._tm is not None:
            return
        if self._tile is None:
            self._tile = crt.tile(TS, TS)
        try:
            self._tm = machine.Timer(-1, mode=machine.Timer.PERIODIC, period=70, callback=self.spin)
        except Exception:
            self._tm = None             # no timer: the chip stays still, the steps go on

    def spin_stop(self):
        tm, self._tm = self._tm, None
        if tm is not None:
            tm.deinit()

    def spin(self, _t):
        """The timer's: the next frame of the chip, to its corner alone. It never raises into the steps."""
        if self._paint or self._tm is None:
            return
        self._paint = True
        try:
            self._f += 1
            fb, mv = self._tile
            r = self.draw_chip(fb, 0, 0, self._f)
            dx = r[2] % 7 - 3 if r[3] < 20 else 0       # now and then the picture slips sideways a frame
            crt.rect(self.d, mv, CX0 + dx, CY0, TS, TS)
        except Exception:
            self._tm = None
        finally:
            self._paint = False

    def _make(self, st):
        d, c, why = self.d, self.c, self.need("make")
        d.fill(B.c("bg"))
        Q.header(d, "Your key", "chip …" + c.serial[-6:])
        B.logo_mark(d, M + 10, HEAD + 16, 0.9)
        B.txt(d, "Made here.", M + 26, HEAD + 5, "bold18")
        side = 56
        bx, by = R - side, HEAD + 6
        B.rrect(d, bx - 3, by - 3, side + 6, side + 6, 6, "raised")
        blockies.draw(d, self._seed, bx, by, side // 8)
        B.para(d, "Inside this chip, and it never leaves it. Each try replaces the last.", M, HEAD + 32, bx - 10 - M,
               "sans12", "muted", "bg", 14, FOOT - 22)
        y = FOOT - 18
        if why:
            B.txt(d, B.fit(why, TW, "sans12"), M, y, "sans12", "bad")
        elif c.checked and all(k for _, k in c.checked):
            B.mark(d, True, M + 6, y + 8, 6)
            B.txt(d, B.fit("No key yet: a new chip", TW - 16, "sans12"), M + 16, y + 1, "sans12", "ok")
        elif c.checked:
            B.warn_sign(d, M + 6, y + 8, 6)
            old = "Old key, %d uses" % c.counter if c.counter else "An old key"
            B.txt(d, B.fit(old + ": Make replaces it", TW - 16, "sans12"), M + 16, y + 1, "sans12", "warn")
        self.foot((None, None, None if why else ("Make", "ok", "on_ok")))
        self.show()

    def _pick(self, st):
        self._pick_page(self.addr(), False)

    def _pick_page(self, a, spinning):
        """The picture big and its two ends. spinning: a shuffle frame, no ends and no buttons yet."""
        self.spin_stop()
        self._busy = False
        d, why = self.d, self.need("make")
        d.fill(B.c("bg"))
        Q.header(d, "Your key", "" if spinning else "made in the chip")
        side = 96
        blockies.draw(d, a, M, HEAD + 3, side // 8)
        x = M + side + 10
        if spinning:
            B.txt(d, "…", x, HEAD + 10, "mono13", "faint")
            self.foot((None, None, None))
            C.show(d)
            return
        keypick_s.ends(d, a, x, HEAD + 10)
        B.para(d, "Like it? Seal it in your signer. Or replace it.", x, HEAD + 50, R - x, "sans12", "muted", "bg", 14, FOOT - 2)
        self.foot((None if why else ("Replace", "raised", "text"), ("Full", "raised", "text"), ("Seal", "ok", "on_ok")))
        self.show()

    def _full(self, st):
        d, a, why = self.d, self.addr(), self.need("make")
        d.fill(B.c("bg"))
        Q.header(d, "Your key", "in full")
        y = HEAD + 4
        for line in Q.addr_lines(a):
            B.txt(d, line, M, y, "mono13")
            y += 17
        blockies.draw(d, a, R - 32, FOOT - 36, 4)
        B.para(d, "A signer, not a wallet: never send funds to it.", M, y + 4, TW - 40, "sans12", "warn", "bg", 14, FOOT - 2)
        self.foot((None if why else ("Replace", "raised", "text"), ("Pic", "raised", "text"), ("Seal", "ok", "on_ok")))
        self.show()

    def _keep(self, st):
        d, a, why = self.d, self.addr(), self.need("keep")
        d.fill(B.c("bad_bg"))
        Q.header(d, "Seal this key?", "for good", "bad_head", "on_bad", "bad_text")
        blockies.draw(d, a, R - 48, HEAD + 6, 6)
        B.txt(d, a[:6] + "…" + a[-4:], M, HEAD + 6, "mono13", "bad_text", "bad_bg")
        B.para(d, "It's sealed in the chip, then the chip locks: it can never be changed.", M, HEAD + 26, TW - 58,
               "sans12", "bad_text", "bad_bg", 14, FOOT - 20)
        if why:
            B.txt(d, B.fit(why, TW, "sans12"), M, FOOT - 17, "sans12", "bad_text", "bad_bg")
        else:
            B.txt(d, "Hold Seal 3 s", M, FOOT - 19, "bold14", "bad_text", "bad_bg")
        hold = self._hold()
        self.foot((BACK, None, None if why else ("Seal", "bad_bar", "on_bad")), True, (hold, True) if hold is not None else None)
        self.show(True)

    def _finish(self, st):
        d, why = self.d, self.need("finish")
        d.fill(B.c("bad_bg"))
        Q.header(d, "Finish", "for good", "bad_head", "on_bad", "bad_text")
        B.para(d, "Your key was sealed here. Last, the chip's record and its final lock: it can never be changed.",
               M, HEAD + 6, TW, "sans12", "bad_text", "bad_bg", 14, FOOT - 20)
        if why:
            B.txt(d, B.fit(why, TW, "sans12"), M, FOOT - 17, "sans12", "bad_text", "bad_bg")
        else:
            B.txt(d, "Hold Finish 3 s", M, FOOT - 19, "bold14", "bad_text", "bad_bg")
        hold = self._hold()
        self.foot((BACK, None, None if why else ("Finish", "bad_bar", "on_bad")), True, (hold, True) if hold is not None else None)
        self.show(True)

    def _pin(self, st):
        d = self.d
        d.fill(B.c("bg"))
        Q.header(d, "Your key", "sealed")
        B.mark(d, True, M + 9, HEAD + 14, 9)
        B.txt(d, "Sealed and locked", M + 24, HEAD + 4, "bold18")
        B.para(d, "Last: check the chip, and pin this console to it.", M, HEAD + 34, TW, "sans12", "muted", "bg", 14, FOOT - 2)
        self.foot((None, None, ("Check", "ok", "on_ok")))
        self.show()

    def _done(self, st):
        d, a = self.d, self.addr()
        d.fill(B.c("bg"))
        Q.header(d, "Your key", "pinned")
        B.mark(d, True, M + 9, HEAD + 14, 9)
        B.txt(d, "Sealed", M + 24, HEAD + 4, "bold18")
        blockies.draw(d, a, M, HEAD + 30, 8)
        x = M + 64 + 10
        keypick_s.ends(d, a, x, HEAD + 32)
        B.para(d, "A signer, not a wallet.", x, HEAD + 70, R - x, "sans12", "warn", "bg", 14, FOOT - 2)
        self.foot((None, None, ("Start", "ok", "on_ok")))
        self.show()

    def _stop(self, st):
        d, c = self.d, self.c
        title, why = STOP[st]
        if st == "other":
            why = "It is set up as %s, not quorum v1. Nothing here uses it." % c.profile
        d.fill(B.c("bad_bg"))
        Q.header(d, title, "", "bad_head", "on_bad", "bad_text")
        B.para(d, why, M, HEAD + 6, TW, "sans12", "bad_text", "bad_bg", 14, FOOT - 20)
        B.txt(d, B.fit("chip " + c.serial, TW, "mono13"), M, FOOT - 18, "mono13", "bad_muted", "bad_bg")
        self.foot((None, None, None), True)
        self.show(True)

    def _result(self, st):
        d = self.d
        step, ok, checks, msg = self.result
        red = not ok
        bg = "bad_bg" if red else "bg"
        d.fill(B.c(bg))
        Q.header(d, TITLES.get(step, step), "done" if ok else "stopped", "bad_head" if red else "surface",
                 "on_bad" if red else "text", "bad_text" if red else "muted")
        y = HEAD + 3
        for label, good in checks:
            if y > FOOT - 30:
                break
            B.mark(d, good, M + 5, y + 7, 5)
            B.txt(d, B.fit(label, TW - 14, "sans12"), M + 14, y, "sans12", ("bad_text" if red else "text") if good else "bad", bg)
            y += 14
        B.para(d, msg, M, y + 2, TW, "sans12", "bad_muted" if red else "muted", bg, 14, FOOT - 2)
        self.foot((None, None, OK), red)
        self.show(red)
