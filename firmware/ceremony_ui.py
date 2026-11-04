# The provisioning ceremony's screen: the steps, the B+Y arm and the holds, on A/B/X/Y or the knob
# (setup_s.py draws it on three buttons). The ceremony itself is passed in: provision.Ceremony and
# provision_tm.Ceremony change a fresh chip; practice.Practice, in the console image, changes nothing.
# Nothing here calls the chip. The arm is the signer's (signer.arm) unless a subclass keeps its own:
# arm(), armed() and need() are the only ways the screen asks about it.
import time
import signer as S

HOLD_MS = 3000
ARM_MS = 3000
# A hold starts only with this many seconds of the arm left: the 3 s hold, then the step's own work
# before its gated call (C6 signs and verifies a test digest first). With less, the arm can run out
# in between and the step is refused halfway (chip 3, 2026-10-22: one wasted signature). Arm again.
ARM_LEFT = 10
PERMANENT = ("C3", "C6", "C9")
GENKEY = ("C4",)
TITLES = {"C1": "Pre-flight", "C2": "Write quorum v1", "C3": "Lock the config", "C4": "Make the key",
          "C5": "Test signatures", "C6": "Seal slot 0", "C7": "Owner address", "C8": "Record + zero fill",
          "C9": "Lock the data zone", "C10": "Done", "other": "Not a fresh chip"}
WHAT = {
    "C1": "Reads the chip and saves its factory config. Changes nothing.",
    "C2": "Writes the quorum v1 table and reads it back. Reversible: the config zone is still open.",
    "C3": "Locks the config zone forever. The chip checks a CRC of the reviewed table and refuses if one bit differs.",
    "C4": "Makes a new P-256 key inside the chip, in slot 0. Until C6 it can be made again.",
    "C5": "Signs two test digests with the new key and checks both here. Counter 0 goes up by 2.",
    "C6": "Locks slot 0 forever: this key can never be replaced or overwritten.",
    "C7": "The address this key gets as a Safe owner. Compare it on the laptop: tools/fw verify --baseline.",
    "C8": "Zeros into slots 1-15, the record into the OTP zone. Rewritable until C9.",
    "C9": "Locks the data and OTP zones forever. The chip checks their CRC first.",
    "C10": "The chip is sealed. Enroll the owner address, then add it to the Safe.",
    "other": "This chip already has a locked config that is not quorum v1. The ceremony is for fresh chips.",
}


# ----------------------------------------------------------------------------- the screen
def palette(theme):
    """The ceremony's colours: dark (chip 1's) or light (chip 2's), from chips.json."""
    import lcd as L
    if theme == "light":
        return {"bg": L.color(255, 255, 255), "fg": L.color(0, 0, 0), "accent": L.color(0, 70, 170),
                "muted": L.color(100, 100, 100), "ok": L.color(0, 125, 0), "bad": L.color(200, 0, 0),
                "dim": L.color(215, 215, 215)}
    return {"bg": L.BLACK, "fg": L.WHITE, "accent": L.YELLOW, "muted": L.GREY, "ok": L.GREEN, "bad": L.RED, "dim": L.DARK}


class UI:
    """framebuf's 8 px font on the plain LCD: 29 characters a line. Drawn through d.frames, so the
    strip-buffered 320x240 panels (build1) get every strip. Driven by A/B/X/Y, or on build1 by the
    knob: a turn switches between "do it" and "back", a press does it; on a permanent or GenKey
    step one 3 s hold arms (the B+Y arm's place) and a second 3 s hold does it."""

    def __init__(self, d, keys, sig, theme="dark", ceremony=None):
        import lcd as L
        self.d, self.keys = d, keys
        self.knob = bool(getattr(L, "KNOB", False))
        self.choice = 0         # knob: 0 "do it", 1 "back"
        self.p = palette(theme)
        self.c = ceremony
        self.result = None      # (step, ok, checks, message) after a run
        self.hold = None
        self.rearm = False      # knob: this hold started with too little arm left, so it arms again
        self.armhold = None
        self.armnote = 0        # ticks when B+Y were let go before the arm took: "let go early" for a moment
        self.armdone = False    # the arm bar filled; the 60 s start when both keys are let go
        self.back = False       # Y went down alone: "back" when it comes up, unless B joins it first
        self.released = True    # A let go since the last result was dismissed: only then can a hold start
        self.dirty = True

    def need(self, st):
        if st in self.c.PERMANENT:
            return S.gate("lock")
        if st in self.c.GENKEY:
            return S.gate("genkey")
        return ""

    def arm(self):
        S.arm()

    def armed(self):
        """Seconds of the arm left."""
        return S.armed()

    def tick(self, pressed):
        """Returns "back" to leave."""
        if self.knob and not any(k in pressed for k in ("A", "B", "X", "Y")):
            return self.tick_knob(pressed)
        st = self.c.step()
        b, y = self.keys.held("B"), self.keys.held("Y")
        # The arm: B and Y held together, in either order. The bar fills over ARM_MS; once full it
        # stays full ("let go") however long they are held, and the 60 s start when both are up.
        if b and y:
            self.back = False
            if self.armdone:
                pass
            elif self.armhold is None:
                self.armhold = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), self.armhold) > ARM_MS:
                self.armhold, self.armdone = None, True
            self.dirty = True
            return None
        if self.armdone:
            if not b and not y:
                self.arm()
                self.armdone, self.dirty = False, True
            return None
        # Y alone is "back", on release, so a Y that lands before B is never taken as one
        if "Y" in pressed and not b:
            self.back = True
        if self.back and not y:
            self.back = False
            if self.result:
                self.result, self.dirty = None, True
                self.released = False
                return None
            return "back"
        if self.armhold is not None:
            self.armhold, self.armnote, self.dirty = None, time.ticks_ms(), True
        if self.armnote and time.ticks_diff(time.ticks_ms(), self.armnote) > 1500:
            self.armnote, self.dirty = 0, True
        if self.result:
            if "A" in pressed:
                self.result, self.dirty = None, True
                self.released = False
            return None
        if not self.keys.held("A"):
            self.released = True
        if st in self.c.FINAL:
            if "A" in pressed:
                self.result = (st,) + self.c.run(st)
                self.dirty = True
            return None
        if self.need(st):
            return None
        hold_ms = HOLD_MS if st in self.c.PERMANENT or st in self.c.GENKEY else 0
        if hold_ms:
            if self.keys.held("A") and self.released and (self.hold is not None or self.armed() >= ARM_LEFT):
                if self.hold is None:
                    self.hold = time.ticks_ms()
                if time.ticks_diff(time.ticks_ms(), self.hold) >= hold_ms:
                    self.hold = None
                    self.busy(st)
                    self.result = (st,) + self.c.run(st)
                self.dirty = True
            elif self.hold is not None:
                self.hold, self.dirty = None, True
        elif "A" in pressed:
            self.busy(st)
            self.result = (st,) + self.c.run(st)
            self.dirty = True
        if self.armed() and time.ticks_ms() % 1000 < 60:
            self.dirty = True
        return None

    def tick_knob(self, pressed):
        """The knob (build1): turn to choose do it / back, press to act, hold 3 s to arm and
        again to do a permanent or GenKey step."""
        st = self.c.step()
        held = self.keys.held("press")
        if not held:
            self.released = True
        if self.result:
            if "press" in pressed:
                self.result, self.dirty, self.released = None, True, False
            return None
        if "up" in pressed or "down" in pressed:
            self.choice, self.hold, self.dirty = 1 - self.choice, None, True
            return None
        if self.choice == 1:
            if "press" in pressed:
                self.choice = 0
                return "back"
            return None
        if st in self.c.FINAL:
            if "press" in pressed:
                self.result, self.dirty = (st,) + self.c.run(st), True
            return None
        gated = st in self.c.PERMANENT or st in self.c.GENKEY
        if not gated:
            if "press" in pressed:
                self.busy(st)
                self.result, self.dirty = (st,) + self.c.run(st), True
            return None
        why = self.need(st)
        if why and not why.startswith("not armed"):
            return None                     # an ALLOW_* flag is off: nothing to hold for
        if held and self.released:
            if self.hold is None:
                self.hold, self.rearm = time.ticks_ms(), self.armed() < ARM_LEFT
            if time.ticks_diff(time.ticks_ms(), self.hold) >= HOLD_MS:
                self.hold, self.released = None, False
                if self.rearm:
                    self.arm()                 # the first hold arms; let go, then hold again
                else:
                    self.busy(st)
                    self.result = (st,) + self.c.run(st)
            self.dirty = True
        elif self.hold is not None:
            self.hold, self.dirty = None, True
        if self.armed() and time.ticks_ms() % 1000 < 60:
            self.dirty = True
        return None

    def busy(self, st):
        self.d.frames(self._busy, st)

    def _busy(self, st):
        d = self.d
        d.fill(self.p["bg"])
        d.center_text(st + " " + self.c.TITLES[st], 100, self.p["accent"], 2)
        d.center_text("working...", 130, self.p["fg"])
        d.show()

    def lines(self, s, y, color, width=29):
        words, line = [], ""
        for w in s.split():
            while len(w) > width:           # an address: in pieces that fit
                words.append(w[:width])
                w = w[width:]
            words.append(w)
        for w in words:
            if len(line) + len(w) + 1 > width:
                self.d.text(line, 4, y, color)
                y, line = y + 11, w
            else:
                line = (line + " " + w).strip()
        if line:
            self.d.text(line, 4, y, color)
            y += 11
        return y

    def draw(self):
        if not self.dirty:
            return
        self.dirty = False
        c = self.c
        st = c.step()                       # once, not once per strip
        why = self.need(st) if st not in c.FINAL else ""
        pic = c.picture(st, bool(self.result))
        self.d.frames(self._paint, st, why, c.subtitle()[:29], c.note(), pic)

    def _paint(self, st, why, subtitle, note, pic=None):
        d, c = self.d, self.c
        d.fill(self.p["bg"])
        d.text(c.HEADER, 4, 4, self.p["accent"])
        d.text(subtitle, 4, 16, self.p["muted"])
        if self.result:
            st, ok, checks, msg = self.result
            d.text("%s %s: %s" % (st, c.TITLES[st], "OK" if ok else "STOPPED"), 4, 34, self.p["ok"] if ok else self.p["bad"])
            y = 50
            for label, good in checks:
                d.text(("ok " if good else "NO ") + label[:26], 4, y, self.p["ok"] if good else self.p["bad"])
                y += 11
            y = self.lines(msg, y + 6, self.p["fg"])
            if pic:
                import blockies
                blockies.draw(d, pic, 4, y + 8, 8)          # 64 px: the picture to compare in the Safe app
            d.text("press: continue" if self.knob else "A: continue", 4, 226, self.p["fg"])
            d.show()
            return
        n = c.index(st)
        d.text("%s/%d %s" % (st, c.NSTEPS, c.TITLES[st]) if n else c.TITLES[st], 4, 34, self.p["accent"] if st in c.PERMANENT else self.p["fg"])
        step_w = 230 // c.NSTEPS
        for i in range(1, c.NSTEPS + 1):
            d.fill_rect(4 + (i - 1) * step_w, 48, step_w - 3, 4, self.p["ok"] if i < n else (self.p["accent"] if i == n else self.p["dim"]))
        y = self.lines(c.WHAT[st], 60, self.p["fg"])
        y += 6
        if st in c.PERMANENT:
            y = self.lines("PERMANENT. It cannot be undone.", y, self.p["bad"])
        if c.key:
            d.text("key " + c.fingerprint(), 4, y + 4, self.p["muted"])
            y += 15
        if note:
            d.text(note[:29], 4, y, self.p["muted"])
        if pic:
            import blockies
            blockies.draw(d, pic, 4, 128, 6)                # 48 px, above the hold bar
            d.text("owner picture", 60, 148, self.p["muted"])
        if self.knob:
            self._paint_knob(st, why)
            d.show()
            return
        if self.armdone:
            d.text("armed: let go of B+Y", 4, 186, self.p["ok"])
            d.fill_rect(4, 198, 232, 6, self.p["ok"])
        elif self.armhold is not None:
            frac = min(1, time.ticks_diff(time.ticks_ms(), self.armhold) / ARM_MS)
            d.text("arming: keep holding B+Y", 4, 186, self.p["accent"])
            d.fill_rect(4, 198, 232, 6, self.p["dim"])
            d.fill_rect(4, 198, int(232 * frac), 6, self.p["accent"])
        elif self.armnote:
            d.text("let go early: not armed", 4, 190, self.p["bad"])
        elif why:
            y = self.lines(why, 190, self.p["bad"])
        elif st in c.PERMANENT or st in c.GENKEY:
            left = self.armed()
            d.text("armed %ds" % left if left else "", 4, 196, self.p["ok"])
            if self.hold is not None:
                frac = min(1, time.ticks_diff(time.ticks_ms(), self.hold) / HOLD_MS)
                d.fill_rect(4, 208, int(232 * frac), 6, self.p["bad"])
            if self.hold is None and left < ARM_LEFT:
                d.text("under %d s left: arm again" % ARM_LEFT, 4, 216, self.p["accent"])
            else:
                d.text("hold A 3 s to do it", 4, 216, self.p["fg"])
        else:
            d.text("A: do it", 4, 216, self.p["fg"])
        d.text("Y: back   B+Y 3 s: arm", 4, 228, self.p["muted"])
        d.show()

    def _paint_knob(self, st, why):
        """The bottom of a step screen on build1: what the knob does here, and the hold bar."""
        d, c = self.d, self.c
        gated = st in c.PERMANENT or st in c.GENKEY
        if self.choice == 0 and st not in c.FINAL and gated:
            left = self.armed()
            if why and not why.startswith("not armed"):
                self.lines(why, 186, self.p["bad"])
            else:
                doing = left >= ARM_LEFT if self.hold is None else not self.rearm
                d.text("armed %ds: hold 3 s to do it" % left if doing else
                       "%ds left: hold 3 s to re-arm" % left if left else "not armed: hold 3 s to arm", 4, 190,
                       self.p["ok"] if doing else self.p["accent"])
                if self.hold is not None:
                    frac = min(1, time.ticks_diff(time.ticks_ms(), self.hold) / HOLD_MS)
                    d.fill_rect(4, 202, 232, 6, self.p["dim"])
                    d.fill_rect(4, 202, int(232 * frac), 6, self.p["bad"] if left else self.p["accent"])
        pick = self.p["accent"]
        d.text(("> " if self.choice == 0 else "  ") + ("check" if st in c.FINAL else "do it"), 4, 214,
               pick if self.choice == 0 else self.p["fg"])
        d.text(("> " if self.choice == 1 else "  ") + "back", 120, 214, pick if self.choice == 1 else self.p["fg"])
        d.text("turn: choose   press: go", 4, 228, self.p["muted"])
