# The owner's key on three buttons (240x135, lcd.THREE, not the knob Feather): the claim's U2-U4
# (claim.py) and the spare's S1-S3 (brand.py) as a customer sees them. Every other step, and every
# result that stopped, is setup_s.UI's.
#   Make    the chip makes a key (GenKey, slot 0). Nothing leaves it but the public half.
#   Pick    the owner address's blockie, big, and its two ends. D0 makes another, as many times as
#           anyone likes: until the seal, slot 0 can be made again, and no key here has signed for a
#           Safe. D1 shows the address in full. D2 goes on to Keep.
#   Keep    a red page: hold D2 3 s, and the test signatures run (U3), then the seal (U4), forever.
#   Done    the key sealed, its blockie and address; D2 hands back to setup_s.UI (U5, or the spare's S4).
# The gates: ALLOW_GENKEY and ALLOW_LOCK as on every ceremony (signer.flag). The arm is this
# screen's own: one D2 press for Make or another key, which can be made again; the 3 s hold on a red
# page for the seal, which can't be undone. It arms for the call alone and disarms after.
# A new key costs nothing on counter 0: claim.make_key keeps the public key GenKey returned and
# checks KeyValid, which counts nothing; a public-key read after the data lock counts a use.
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
KIND = {"U2": "make", "U3": "pick", "U4": "pick", "S1": "make", "S2": "pick", "S3": "pick"}
TEST = {"U3", "S2"}
SEAL = {"U4": "U4", "U3": "U4", "S2": "S3", "S3": "S3"}
MAKE = {"U3": "U2", "U4": "U2", "S2": "S1", "S3": "S1"}


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


ICONS = {"Back": "back", "Keep": "check", "OK": "check", "Full": "down", "Pic": "back"}


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
    def __init__(self, d, keys, sig, theme="dark", ceremony=None):
        U.use(theme)
        super().__init__(d, keys, sig, theme, ceremony)
        self.page = "pic"       # on Pick: "pic" the blockie, "full" the address, "keep" the red page
        self.tries = 0          # keys made this session
        self.done = False       # sealed here: the Done page until D2
        self.held_since = None  # D2 down on the red page
        self.fresh_press = False    # D2 let go since the red page opened: only then can a hold start
        self.why = ""
        self._addr = (None, "")

    # --- which screen ----------------------------------------------------------------
    def kind(self, st):
        if self.result is not None:
            return None
        if self.done:
            return "done"
        return KIND.get(st)

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
        if kind == "done":
            if "D2" in pressed:
                self.done, self.dirty = False, True
            return None
        if kind == "make":
            if "D0" in pressed:
                return "back"
            if "D2" in pressed:
                self.make(st)
            return None
        if self.page == "keep":
            if not raw.held("D2"):
                self.fresh_press = True
                if self.held_since is not None:
                    self.held_since, self.dirty = None, True
            if "D0" in pressed:
                self.page, self.held_since, self.dirty = "pic", None, True
                return None
            if raw.held("D2") and self.fresh_press and not self.why:
                if self.held_since is None:
                    self.held_since = time.ticks_ms()
                elif time.ticks_diff(time.ticks_ms(), self.held_since) >= ceremony_ui.HOLD_MS:
                    self.held_since = None
                    self.keep(st)
                self.dirty = True
            return None
        if "D0" in pressed:
            self.make(MAKE.get(st, st))
        elif "D1" in pressed:
            self.page, self.dirty = ("full" if self.page == "pic" else "pic"), True
        elif "D2" in pressed:
            self.page, self.fresh_press, self.held_since, self.dirty = "keep", False, None, True
            self.why = "" if S.flag("ALLOW_LOCK") else "ALLOW_LOCK is False on the board"
        return None

    def run_armed(self, step):
        """One step with the arm held for it alone."""
        S.arm(10)
        try:
            return (step,) + self.c.run(step)
        finally:
            S.disarm()

    def make(self, step):
        if not S.flag("ALLOW_GENKEY"):
            self.why, self.dirty = "ALLOW_GENKEY is False on the board", True
            return
        self.why = ""
        self.d.frames(self._busy_page, "Making a key", "inside the chip")
        out = self.run_armed(step)
        if out[1]:
            self.tries += 1
            self.addr()                 # under the busy page, not on the next frame
            self.page = "pic"
        else:
            self.result = out
        self.dirty = True

    def keep(self, st):
        self.d.frames(self._busy_page, "Keeping it", "test signatures, then the seal")
        if st in TEST:
            out = (st,) + self.c.run(st)        # signs two test digests: no gate, as U3 everywhere
            if not out[1]:
                self.result, self.page, self.dirty = out, "pic", True
                return
        out = self.run_armed(SEAL[st])
        self.page = "pic"
        if out[1]:
            self.done = True
        else:
            self.result = out
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
        if kind == "pick" and self.page == "keep":
            kind = "keep"
        elif kind == "pick" and self.page == "full":
            kind = "full"
        self.d.frames(getattr(self, "_" + kind), st)

    def _busy_page(self, title, sub):
        d = self.d
        d.fill(U.c("bg"))
        rail(d, (None, None, None))
        U.txt(d, U.fit(title + "…", TW, "bold18"), M, 40, "bold18")
        U.txt(d, U.fit(sub, TW, "sans12"), M, 66, "sans12", "muted")
        d.show()

    def _make(self, st):
        d = self.d
        d.fill(U.c("bg"))
        U.txt(d, "Make your key", M, 2, "bold18")
        y = U.para(d, "It's made inside this chip, and never leaves it.", M, 30, TW, "sans12", "text", "bg", 14, 74)
        U.para(d, "Make as many as you like, and keep the one you like.", M, y + 4, TW, "sans12", "muted", "bg", 14, 112)
        if self.why:
            U.txt(d, U.fit(self.why, TW, "sans12"), M, 116, "sans12", "bad")
        rail(d, (("Back", "raised", "text"), None, None if self.why else ("Make", "ok", "bg")))
        d.show()

    def _pick(self, st):
        d, a = self.d, self.addr()
        d.fill(U.c("bg"))
        blockies.draw(d, a, M, 11, 14)                      # 112 px
        x = M + 112 + 8
        cw = W - 5 - x
        U.txt(d, U.fit("Key %d" % self.tries if self.tries else "Your key", cw, "bold14"), x, 6, "bold14")
        U.txt(d, U.fit(a[:6], cw, "mono13"), x, 32, "mono13")
        U.txt(d, U.fit("…" + a[-4:], cw, "mono13"), x, 48, "mono13")
        U.para(d, "Like it? Keep it, or make another.", x, 74, cw, "sans12", "muted", "bg", 14, 130)
        if self.why:
            U.txt(d, U.fit(self.why, TW, "sans12"), M, 120, "sans12", "bad")
        rail(d, (None if self.why else ("New", "raised", "text"), ("Full", "raised", "text"), ("Keep", "ok", "bg")))
        d.show()

    def _full(self, st):
        d, a = self.d, self.addr()
        d.fill(U.c("bg"))
        U.txt(d, "Your key's address", M, 2, "bold14")
        y = 24
        for line in groups(a):
            U.txt(d, line, M, y, "mono13")
            y += 17
        blockies.draw(d, a, W - 5 - 32, 98, 4)
        U.para(d, "A signer, not a wallet: never send funds to it.", M, y + 4, TW - 38, "sans12", "warn", "bg", 14, 134)
        rail(d, (None, ("Pic", "raised", "text"), ("Keep", "ok", "bg")))
        d.show()

    def _keep(self, st):
        d, a = self.d, self.addr()
        d.fill(U.c("bad_bg"))
        U.txt(d, U.fit("Keep this key?", TW - 40, "bold18"), M, 2, "bold18", "bad_text", "bad_bg")
        blockies.draw(d, a, W - 5 - 32, 4, 4)
        U.txt(d, a[:6] + "…" + a[-4:], M, 28, "mono13", "bad_text", "bad_bg")
        y = U.para(d, "It's sealed in the chip for good: it can never be changed.", M, 50, TW, "sans12", "bad_text", "bad_bg", 14, 96)
        if self.why:
            U.txt(d, U.fit(self.why, TW, "sans12"), M, 116, "sans12", "bad_text", "bad_bg")
        else:
            U.txt(d, "Hold Keep 3 s", M, max(y + 6, 104), "bold14", "bad_text", "bad_bg")
        hold = None
        if self.held_since is not None:
            hold = time.ticks_diff(time.ticks_ms(), self.held_since) / ceremony_ui.HOLD_MS
        rail(d, (("Back", "raised", "text"), None, None if self.why else ("Keep", "bad_bar", "on_bad")), hold)
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
        U.txt(d, U.fit("…" + a[-4:], cw, "mono13"), x, 48, "mono13")
        U.para(d, "Sealed for good.", x, 70, cw, "sans12", "muted", "bg", 14, 90)
        U.para(d, "A signer, not a wallet.", M, 100, TW, "sans12", "warn", "bg", 14, 134)
        rail(d, (None, None, ("OK", "ok", "bg")))
        d.show()
