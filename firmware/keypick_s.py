# The owner's key on three buttons (240x135, lcd.THREE, not the knob Feather), as a customer sees
# it. Three ceremonies use it: the dual image's own key on a fresh chip (provision.py, C1-C10, no
# brand), the claim of a branded chip (claim.py, U2-U4) and the brand bench's spare (brand.py,
# S1-S3). Every other step, and every result that stopped, is setup_s.UI's.
#   Start   (provision only) hold D2 3 s: C1-C3, the chip's table written and its config locked.
#   Make    the chip makes a key (GenKey, slot 0). Nothing leaves it but the public half.
#   Pick    the owner address's blockie, big, and its two ends, landed after a short shuffle. New (D2,
#           the bottom) makes another, as many times as anyone likes: until the seal, slot 0 can be
#           made again, and no key here has signed for a Safe. D1 shows the address in full.
#           Choose (D0, the top) goes on to Keep.
#   Keep    a red page: hold D0 3 s (D2 is Back), and the test signatures run (C5/U3), then the seal (C6/U4),
#           forever; on provision the record and the data lock follow (C7-C9).
#   Finish  (provision, after a restart between the seal and C9) hold D2 3 s: C7-C9.
#   Done    the key sealed, its blockie and address; D2 hands back to setup_s.UI (C10, U5, or S4).
# The gates: ALLOW_GENKEY and ALLOW_LOCK as on every ceremony (signer.flag). The arm is this
# screen's own: one D2 press for Make or another key, which can be made again; a 3 s hold on a page
# that says it can't be undone for each permanent run. It arms for each call alone and disarms after.
# A new key costs nothing on counter 0: after a data lock a public-key read counts a use, so
# claim.make_key keeps the public key GenKey returned; on provision the data zone is still open
# while keys are made, and reads count nothing.
import time
import board
import blockies
import quorum_ui as U
import signer as S
import setup_s
import ceremony_ui
from keccak import keccak256
from binascii import hexlify

W, H = board.W, board.H
RAIL = setup_s.RAIL
M = RAIL + 6
TW = W - 5 - M
KIND = {"U2": "make", "U3": "pick", "U4": "pick", "S1": "make", "S2": "pick", "S3": "pick",
        "C1": "start", "C2": "start", "C3": "start", "C4": "make", "C5": "pick", "C6": "pick",
        "C7": "finish", "C8": "finish", "C9": "finish"}
TEST = {"U3", "S2", "C5"}
SEAL = {"U4": "U4", "U3": "U4", "S2": "S3", "S3": "S3", "C5": "C6", "C6": "C6"}
MAKE = {"U3": "U2", "U4": "U2", "S2": "S1", "S3": "S1", "C5": "C4", "C6": "C4"}
START = ("C1", "C2", "C3")
FINISH = ("C7", "C8", "C9")
HOLD_KEY = {"keep": "D0"}                  # the red page holds on Choose's button; Start and Finish on D2
SHUFFLE_MS = (60, 60, 70, 80, 95, 110, 130, 160, 200, 250)     # each shuffle frame, slowing to a stop
PERM = ("C3", "C6", "C9", "U4", "S3")     # the runs that need ALLOW_LOCK; GenKey's are the MAKE steps'



def checksum(a):
    """EIP-55, as the Safe app and the phone show it (txservice.checksum, which this image lacks)."""
    a = a.lower().replace("0x", "")
    h = hexlify(keccak256(a.encode())).decode()
    return "0x" + "".join(ch.upper() if int(h[i], 16) >= 8 else ch for i, ch in enumerate(a))


def icon(d, kind, cx, cy, ink):
    seg = lambda x0, y0, x1, y1: U.thick_line(d, x0, y0, x1, y1, ink, 2)
    if kind == "back":
        seg(cx + 2, cy - 4, cx - 2, cy); seg(cx - 2, cy, cx + 2, cy + 4)
    elif kind == "check":
        seg(cx - 4, cy, cx - 1, cy + 3); seg(cx - 1, cy + 3, cx + 4, cy - 3)
    elif kind == "down":
        seg(cx - 4, cy - 2, cx, cy + 2); seg(cx, cy + 2, cx + 4, cy - 2)
    else:
        d.ellipse(cx, cy, 4, 4, U.c(ink), True)


ICONS = {"Back": "back", "Keep": "check", "Choose": "check", "New": "dot", "OK": "check", "Full": "down", "Pic": "back", "Start": "check", "Finish": "check"}


def rail(d, labels, hold=None, bg="surface"):
    """What D0, D1, D2 do, level with each button: (word, fill, ink) or None. hold: the fraction
    of the 3 s, filling red from the bottom."""
    d.fill_rect(0, 0, RAIL, H, U.c(bg))
    if hold:
        h = int(H * min(1, hold))
        d.fill_rect(0, H - h, RAIL, h, U.c("bad_bar"))
    d.vline(RAIL, 0, H, U.c("raised"))
    for y, lab in zip(board.RAIL_Y, labels):
        if lab:
            s, fill, ink = lab
            top = max(0, min(H - 31, y - 15))
            U.rrect(d, 1, top, RAIL - 2, 31, 6, fill)
            icon(d, ICONS.get(s, "dot"), RAIL // 2, top + 8, ink)
            s = U.fit(s, RAIL - 2, "sans12")
            U.txt(d, s, 1 + (RAIL - 2 - U.F.width(s, "sans12")) // 2, top + 14, "sans12", ink, fill)


def welcome(d, frame):
    """The dual image's first screen for a customer: the PicoQuorum mark, what happens next in
    plain words, and a blockie that changes every frame, a picture of what's coming. Each one is
    drawn from random bytes on this board, not a key: no key exists until Make."""
    import os
    U.use("dark")
    d.fill(U.c("bg"))
    U.logo_mark(d, M + 10, 14, 1.0)
    U.txt(d, "PicoQuorum", M + 25, 2, "bold18")
    side = 72
    bx, by = W - 5 - side, 32
    seed = "0x" + hexlify(os.urandom(20)).decode()
    U.rrect(d, bx - 3, by - 3, side + 6, side + 6, 6, "raised")
    blockies.draw(d, seed, bx, by, side // 8)
    cw = bx - 8 - M
    y = 34
    for line in ("Your key,", "made here."):
        U.txt(d, U.fit(line, cw, "bold14"), M, y, "bold14")
        y += 18
    U.para(d, "Pick the one you like.", M, y + 4, cw, "sans12", "muted", "bg", 14, 112)
    U.txt(d, U.fit("Press Start to begin", TW, "sans12"), M, 116, "sans12", "ok")
    rail(d, (None, None, ("Start", "ok", "bg")))
    d.show()


def choose_bar(d, right):
    """Choose this, across the top from D0's end of the rail: what the top button does, plainly."""
    U.rrect(d, 1, 1, right - 1, 27, 7, "ok")
    icon(d, "check", 15, 14, "bg")
    U.txt(d, "Choose this", 28, 5, "bold14", "bg", "ok")


def ends(d, a, x, y):
    """The address's first four and last four under each other, in cyan, "0x" and the dots as the text,
    the two groups lined up."""
    lead = U.F.width("0x", "mono13")
    hi = (0, 229, 255) if sum(U.rgb("bg")) < 384 else (0, 128, 160)     # cyan, darker on a light theme
    U.txt(d, "0x", x, y, "mono13")
    U.txt(d, a[2:6], x + lead, y, "mono13", hi)
    U.txt(d, "\u2026", x + lead - U.F.width("\u2026", "mono13"), y + 16, "mono13")
    U.txt(d, a[-4:], x + lead, y + 16, "mono13", hi)


def groups(a):
    """0x and 40 hex as lines of four-character groups that fit TW in mono13."""
    out, line = [], ""
    for g in [a[:6]] + [a[i:i + 4] for i in range(6, len(a), 4)]:
        nxt = (line + " " + g).strip()
        if line and U.F.width(nxt, "mono13") > TW:
            out.append(line)
            nxt = g
        line = nxt
    return out + [line]


class UI(setup_s.UI):
    # which button does what, the Feather's: Choose at the top (D0), New at the bottom (D2), the red
    # Keep page held on Choose's button with D2 as Back. keypick_rp.UI has console-rp's.
    HOLD_KEY = HOLD_KEY
    KEEP_BACK = "D2"
    NEW, CHOOSE = "D2", "D0"

    def __init__(self, d, keys, sig, theme="dark", ceremony=None):
        U.use(theme)
        super().__init__(d, keys, sig, theme, ceremony)
        self.page = "pic"       # on Pick: "pic" the blockie, "full" the address, "keep" the red page
        self.tries = 0          # keys made this session
        self.done = False       # sealed here: the Done page until D2
        self.held_since = None  # D2 down on a hold page
        self.fresh_press = False    # D2 let go since the page opened: only then can a hold start
        self._addr = (None, "")

    # --- which screen ----------------------------------------------------------------
    def kind(self, st):
        if self.result is not None:
            return None
        if self.done:
            return "done"
        k = KIND.get(st)
        if k == "pick" and self.page in ("keep", "full"):
            return self.page
        return k

    def need(self, kind):
        """Why this page's action can't run: an ALLOW_* flag off, or ""."""
        want = {"start": ("ALLOW_LOCK", "ALLOW_GENKEY"), "make": ("ALLOW_GENKEY",), "keep": ("ALLOW_LOCK",),
                "finish": ("ALLOW_LOCK",)}.get(kind, ())
        off = [f for f in want if not S.flag(f)]
        return " and ".join(off) + " off on the board" if off else ""

    def addr(self):
        """The owner address of the key in slot 0, worked out once a key (two keccaks, ~0.7 s)."""
        k = self.c.key
        if self._addr[0] != k:
            self._addr = (k, checksum(self.c.owner()) if k else "")
        return self._addr[1]

    # --- the buttons -----------------------------------------------------------------
    def tick(self, pressed):
        st = self.c.step()
        kind = self.kind(st)
        if kind is None:
            return super().tick(pressed)
        raw = self.keys.keys
        hk = self.HOLD_KEY.get(kind, "D2")
        if not raw.held(hk):
            self.fresh_press = True
            if self.held_since is not None:
                self.held_since, self.dirty = None, True
        if kind == "done":
            if "D2" in pressed:
                self.done, self.dirty = False, True
            return None
        if kind in ("start", "keep", "finish"):
            if (self.KEEP_BACK if kind == "keep" else "D0") in pressed:      # Back: the button that doesn't hold
                self.held_since, self.dirty = None, True
                if kind == "keep":
                    self.page = "pic"
                    return None
                return "back"
            if raw.held(hk) and self.fresh_press and not self.need(kind):
                if self.held_since is None:
                    self.held_since = time.ticks_ms()
                elif time.ticks_diff(time.ticks_ms(), self.held_since) >= ceremony_ui.HOLD_MS:
                    self.held_since, self.fresh_press = None, False
                    getattr(self, "do_" + kind)(st)
                self.dirty = True
            return None
        if kind == "make":
            if "D0" in pressed:
                return "back"
            if "D2" in pressed and not self.need("make"):
                self.make(st)
            return None
        if self.NEW in pressed and not self.need("make"):
            self.make(MAKE.get(st, st))
        elif "D1" in pressed:
            self.page, self.dirty = ("full" if self.page == "pic" else "pic"), True
        elif self.CHOOSE in pressed:
            self.page, self.fresh_press, self.held_since, self.dirty = "keep", False, None, True
        return None

    def step_run(self, step):
        """One step; a permanent one or a GenKey with the arm held for that call alone."""
        if step in PERM or step in MAKE.values():
            S.arm(10)
            try:
                return (step,) + self.c.run(step)
            finally:
                S.disarm()
        return (step,) + self.c.run(step)

    def chain(self, steps):
        """Run the steps the ceremony asks for while they are in steps; the first that stops is the
        result page. True when all ran."""
        while self.c.step() in steps:
            out = self.step_run(self.c.step())
            if not out[1]:
                self.result = out
                return False
        return True

    def make(self, step):
        self.d.frames(self._busy_page, "Making a key", "inside the chip")
        out = self.step_run(step)
        if out[1]:
            self.tries += 1
            self.addr()                 # under the busy page, not on the next frame
            self.page = "pic"
            self.shuffle()
        else:
            self.result = out
        self.dirty = True

    def shuffle(self):
        """The new key lands after a shuffle that slows down, as a slot machine's reel does. The key
        is already made: the shuffled pictures are drawn from random bytes on this board, not keys."""
        import os
        sleep = getattr(time, "sleep_ms", None)
        for ms in SHUFFLE_MS:
            self.d.frames(self._pick_page, "0x" + hexlify(os.urandom(20)).decode(), True)
            if sleep:
                sleep(ms)

    def do_start(self, st):
        self.d.frames(self._busy_page, "Setting up the chip", "its table, then its config lock")
        self.chain(START)
        self.dirty = True

    def do_keep(self, st):
        self.d.frames(self._busy_page, "Keeping it", "test signatures, then the seal")
        self.page = "pic"
        if st in TEST:
            out = self.step_run(st)             # signs two test digests: no gate, as C5 and U3 everywhere
            if not out[1]:
                self.result, self.dirty = out, True
                return
        out = self.step_run(SEAL[st])
        if out[1] and self.c.step() in FINISH:
            self.d.frames(self._busy_page, "Locking the chip", "its record, then its data lock")
            self.done = self.chain(FINISH)
        elif out[1]:
            self.done = True
        else:
            self.result = out
        self.dirty = True

    def do_finish(self, st):
        self.d.frames(self._busy_page, "Locking the chip", "its record, then its data lock")
        self.done = self.chain(FINISH)
        self.dirty = True

    # --- the pictures ----------------------------------------------------------------
    def draw(self):
        if not self.dirty:
            return
        st = self.c.step()
        kind = self.kind(st)
        if kind is None:
            return super().draw()
        self.dirty = False
        self.d.frames(getattr(self, "_" + kind), st)

    def _busy_page(self, title, sub):
        d = self.d
        d.fill(U.c("bg"))
        rail(d, (None, None, None))
        U.txt(d, U.fit(title + "\u2026", TW, "bold18"), M, 40, "bold18")
        U.txt(d, U.fit(sub, TW, "sans12"), M, 66, "sans12", "muted")
        d.show()

    def _hold(self):
        if self.held_since is None:
            return None
        return time.ticks_diff(time.ticks_ms(), self.held_since) / ceremony_ui.HOLD_MS

    def _start(self, st):
        d, why = self.d, self.need("start")
        d.fill(U.c("bg"))
        U.txt(d, "Set up your key", M, 2, "bold18")
        y = U.para(d, "This console makes its own key, inside its chip. First the chip is set up for it, for good.",
                   M, 30, TW, "sans12", "text", "bg", 14, 100)
        if why:
            U.para(d, why, M, y + 4, TW, "sans12", "bad", "bg", 14, 134)
        else:
            U.txt(d, "Hold Start 3 s", M, max(y + 6, 104), "bold14", "text")
        rail(d, (("Back", "raised", "text"), None, None if why else ("Start", "ok", "bg")), self._hold())
        d.show()

    def _finish(self, st):
        d, why = self.d, self.need("finish")
        d.fill(U.c("bg"))
        U.txt(d, "Finish setting up", M, 2, "bold18")
        y = U.para(d, "Your key is sealed. Last, the chip's record and its final lock.", M, 30, TW, "sans12", "text", "bg", 14, 100)
        if why:
            U.para(d, why, M, y + 4, TW, "sans12", "bad", "bg", 14, 134)
        else:
            U.txt(d, "Hold Finish 3 s", M, max(y + 6, 104), "bold14", "text")
        rail(d, (("Back", "raised", "text"), None, None if why else ("Finish", "ok", "bg")), self._hold())
        d.show()

    def _make(self, st):
        d, why = self.d, self.need("make")
        d.fill(U.c("bg"))
        U.txt(d, "Make your key", M, 2, "bold18")
        y = U.para(d, "It's made inside this chip, and never leaves it.", M, 30, TW, "sans12", "text", "bg", 14, 74)
        U.para(d, "Make as many as you like, and keep the one you like.", M, y + 4, TW, "sans12", "muted", "bg", 14, 112)
        if why:
            U.txt(d, U.fit(why, TW, "sans12"), M, 116, "sans12", "bad")
        rail(d, (("Back", "raised", "text"), None, None if why else ("Make", "ok", "bg")))
        d.show()

    def _pick(self, st):
        self._pick_page(self.addr(), False)

    def _pick_page(self, a, spinning):
        """The picture big, its two ends, and the rail: Choose at the top, New at the bottom.
        spinning: a shuffle frame, the ends and the buttons not shown yet."""
        d, why = self.d, self.need("make")
        d.fill(U.c("bg"))
        side = 96
        blockies.draw(d, a, M, 33, side // 8)               # 96 px, under the Choose bar
        x = M + side + 8
        cw = W - 5 - x
        U.txt(d, U.fit("Your key", cw, "bold14"), x, 34, "bold14")     # no number: each key is new, not one of a list
        if spinning:
            U.txt(d, U.fit("\u2026", cw, "mono13"), x, 58, "mono13", "faint")
            rail(d, (None, None, None))
        else:
            ends(d, a, x, 58)
            U.para(d, "Made in the chip.", x, 98, cw, "sans12", "muted", "bg", 14, 134)
            rail(d, (None, ("Full", "raised", "text"), None if why else ("New", "raised", "text")))
            choose_bar(d, M + side)
        d.show()

    def _full(self, st):
        d, a = self.d, self.addr()
        d.fill(U.c("bg"))
        y = 34
        for line in groups(a):
            U.txt(d, line, M, y, "mono13")
            y += 17
        blockies.draw(d, a, W - 5 - 32, 98, 4)
        U.para(d, "A signer, not a wallet: never send funds to it.", M, y + 4, TW - 38, "sans12", "warn", "bg", 14, 134)
        rail(d, (None, ("Pic", "raised", "text"), None))
        choose_bar(d, W - 5)
        d.show()

    def _keep(self, st):
        d, a, why = self.d, self.addr(), self.need("keep")
        d.fill(U.c("bad_bg"))
        U.txt(d, U.fit("Keep this key?", TW - 40, "bold18"), M, 2, "bold18", "bad_text", "bad_bg")
        blockies.draw(d, a, W - 5 - 32, 4, 4)
        U.txt(d, a[:6] + "\u2026" + a[-4:], M, 28, "mono13", "bad_text", "bad_bg")
        y = U.para(d, "It's sealed in the chip for good: it can never be changed.", M, 50, TW, "sans12", "bad_text", "bad_bg", 14, 96)
        if why:
            U.txt(d, U.fit(why, TW, "sans12"), M, 116, "sans12", "bad_text", "bad_bg")
        else:
            U.txt(d, "Hold Keep 3 s", M, max(y + 6, 104), "bold14", "bad_text", "bad_bg")
        rail(d, (None if why else ("Keep", "bad_bar", "on_bad"), None, ("Back", "raised", "text")), self._hold())
        d.show()

    def _done(self, st):
        d, a = self.d, self.addr()
        d.fill(U.c("bg"))
        U.mark(d, True, M + 9, 12, 9)
        U.txt(d, U.fit("Your key is ready", TW - 24, "bold18"), M + 24, 1, "bold18")
        blockies.draw(d, a, M, 30, 8)                       # 64 px
        x = M + 64 + 8
        cw = W - 5 - x
        U.txt(d, U.fit(a[:6], cw, "mono13"), x, 32, "mono13")
        U.txt(d, U.fit("\u2026" + a[-4:], cw, "mono13"), x, 48, "mono13")
        U.para(d, "Sealed for good.", x, 70, cw, "sans12", "muted", "bg", 14, 90)
        U.para(d, "A signer, not a wallet.", M, 100, TW, "sans12", "warn", "bg", 14, 134)
        rail(d, (None, None, ("OK", "ok", "bg")))
        d.show()
