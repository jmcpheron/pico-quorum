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
import os
import time
from binascii import hexlify
import blockies
import ceremony_ui
import quorum_ui as B
import quorum_ui_s as Q
import quorum_ui_crt as C
import signer as S
import keypick_s

W, H, M, R, TW, HEAD, FOOT = Q.W, Q.H, Q.M, Q.R, Q.TW, Q.HEAD, Q.FOOT
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
            self.c.run("K0")            # read only: no press needed
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

    def do_keep(self, st):
        super().do_keep(st)
        self.after()

    def do_finish(self, st):
        super().do_finish(st)
        self.after()

    def after(self):
        """The data lock done: C10 and the pin straight away, under a busy page."""
        self.done = False
        if self.result is None and self.c.step() == "C10":
            self.pin()

    def pin(self):
        self.d.frames(self._busy_page, "Checking the chip", "then pinning this console to it")
        out = self.step_run("C10")
        if not out[1]:
            self.result = out
        self.dirty = True

    # --- the pictures ----------------------------------------------------------------
    def draw(self):
        if not self.dirty:
            return
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

    def _busy_page(self, title, sub):
        d = self.d
        d.fill(B.c("bg"))
        Q.header(d, "Your key", "")
        B.txt(d, B.fit(title + "…", TW, "bold18"), M, 44, "bold18")
        B.txt(d, B.fit(sub, TW, "sans12"), M, 70, "sans12", "muted")
        self.foot((None, None, None))
        C.show(d)

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
        B.para(d, "Inside this chip, and it never leaves it. Make as many as you like.", M, HEAD + 32, bx - 10 - M,
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
        B.para(d, "Like it? Choose it. Or make another.", x, HEAD + 50, R - x, "sans12", "muted", "bg", 14, FOOT - 2)
        self.foot((None if why else ("New", "raised", "text"), ("Full", "raised", "text"), ("Choose", "ok", "on_ok")))
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
        self.foot((None if why else ("New", "raised", "text"), ("Pic", "raised", "text"), ("Choose", "ok", "on_ok")))
        self.show()

    def _keep(self, st):
        d, a, why = self.d, self.addr(), self.need("keep")
        d.fill(B.c("bad_bg"))
        Q.header(d, "Keep this key?", "for good", "bad_head", "on_bad", "bad_text")
        blockies.draw(d, a, R - 48, HEAD + 6, 6)
        B.txt(d, a[:6] + "…" + a[-4:], M, HEAD + 6, "mono13", "bad_text", "bad_bg")
        B.para(d, "It's sealed in the chip, then the chip locks: it can never be changed.", M, HEAD + 26, TW - 58,
               "sans12", "bad_text", "bad_bg", 14, FOOT - 20)
        if why:
            B.txt(d, B.fit(why, TW, "sans12"), M, FOOT - 17, "sans12", "bad_text", "bad_bg")
        else:
            B.txt(d, "Hold Keep 3 s", M, FOOT - 19, "bold14", "bad_text", "bad_bg")
        hold = self._hold()
        self.foot((BACK, None, None if why else ("Keep", "bad_bar", "on_bad")), True, (hold, True) if hold is not None else None)
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
