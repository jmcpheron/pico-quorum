# The provisioning ceremony for a fresh ATECC608: PicoQuorum's own config, quorum v1
# (chipcfg.py; the reasoning and the runbook are in docs/PROVISIONING.md). One linear screen in the
# ceremony image. The step is worked out from the chip's own state every time, so a reboot at any
# point resumes where the chip is.
#
#   C1  pre-flight: read-only checks, the factory config saved as snapshot-<serial>.bin
#   C2  write quorum v1 and read it back (reversible: the config zone is still open)
#   C3  lock the config zone, the chip checking a CRC of the reviewed table   PERMANENT
#   C4  GenKey in slot 0 (a new key; replaceable until C6)
#   C5  test signatures (a plain digest and a WebAuthn assertion), verified here
#   C6  lock slot 0: the key can never be replaced                            PERMANENT
#   C7  the owner address this key gets on the Safe, to compare on the laptop
#   C8  zeros into slots 1-15 and the record into the OTP zone (rewritable until C9)
#   C9  lock the data and OTP zones, the chip checking their CRC               PERMANENT
#   C10 final checks and the summary
#
# Permanent steps need ALLOW_LOCK (C4 ALLOW_GENKEY) in secrets.py, the B+Y arm (held 3 s) and A
# held 3 s. Nothing here signs anything but its own test digests. Logic (Ceremony) and screen (UI)
# are apart so test-vectors/run-ceremony.mjs can walk the whole thing on the virtual chip.
import time
import hashlib
import atecc
import chipcfg
import signer as S
import p256

TABLE = chipcfg.QUORUM_V1
HOLD_MS = 3000
ARM_MS = 3000
PERMANENT = ("C3", "C6", "C9")
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


# ----------------------------------------------------------------------------- chip writes
# Here, not in signer.py, so the console image (which carries signer.py) holds none of them.
def write_table(sig, table):
    """REVERSIBLE while the config zone is open: write `table` with this chip's own bytes kept and
    read it back. The chip's original bytes are snapshotted first."""
    sig.save_snapshot()
    sig._slots = None
    cfg = sig.chip.read_config_all()
    return sig.chip.write_config(chipcfg.expected_image(cfg, table))


def lock_config_crc(sig, table):
    """PERMANENT. Lock the config zone with the CRC of exactly `table` (plus the chip's own bytes):
    the chip refuses if what it holds differs by one bit. Needs ALLOW_LOCK and the arm."""
    if not S._allowed("ALLOW_LOCK"):
        raise Exception(S._refused("lock"))
    sig._slots = None
    cfg = sig.chip.read_config_all()
    image = chipcfg.expected_image(cfg, table)
    sig.chip.lock_config(expect=image, summary=chipcfg.summary(image))
    return "config zone locked (CRC %04x)" % chipcfg.summary(image)


def write_record_and_fill(sig, record, table):
    """REVERSIBLE until the data lock (it can be written again, never read back before it): zeros into
    every slot that is not a private key, the 64-byte record into the OTP zone. -> the data CRC."""
    for n, b in chipcfg.zero_slots(table).items():
        # whole 32-byte blocks, the last one starting at the slot's tail (the chip keeps what fits):
        # 4-byte writes into these secret slots are refused before the data lock (chip 2, silicon)
        for blk in range((atecc.SLOT_BYTES[n] + 31) // 32):
            sig.chip.write_data(n, blk, (b[blk * 32:blk * 32 + 32] + bytes(32))[:32])
    sig.chip.write_otp(0, record[:32])
    sig.chip.write_otp(1, record[32:64])
    return chipcfg.data_summary(table, chipcfg.zero_slots(table), record)


def lock_data_crc(sig, summary):
    """PERMANENT. Lock the data and OTP zones; the chip refuses unless they match `summary`."""
    if not S._allowed("ALLOW_LOCK"):
        raise Exception(S._refused("lock"))
    sig._slots = None
    sig.chip.lock_data(summary=summary)
    return "data zone locked (CRC %04x)" % summary


class Ceremony:
    # what the screen (UI) needs to know about a ceremony; provision_tm.Ceremony has its own
    HEADER = "PROVISION quorum v1"
    NSTEPS = 10
    PERMANENT = PERMANENT
    GENKEY = ("C4",)
    FINAL = ("C10", "other")
    TITLES = TITLES
    WHAT = WHAT

    def index(self, st):
        return int(st[1:]) if st[0] == "C" else 0

    def picture(self, st, result=False):
        """The address whose blockie the screen draws, or None (the ATECC ceremony shows none)."""
        return None

    def subtitle(self):
        return "%s %s" % (self.serial, chipcfg.REVISIONS.get(self.revision, self.revision)[-4:])

    def note(self):
        return "counter 0: %d" % self.counter if self.counter is not None else ""

    def __init__(self, sig):
        self.sig = sig
        self.chip = sig.chip
        self.owner_seen = False     # C7 was shown this session
        self.tested = False         # C5 passed this session: only then is C6 (the seal) offered
        self.record = None          # C8's record, this session (the chip cannot read it back before C9)
        self.summary = None
        self.read()

    # --- where the chip is ---------------------------------------------------------
    def read(self):
        c = self.chip
        self.cfg = c.read_config_all()
        self.serial = "".join("%02x" % b for b in c.serial())
        self.revision = "".join("%02x" % b for b in c.revision())
        self.profile = chipcfg.identify(self.cfg)
        self.config_locked = self.cfg[87] == 0x00
        self.data_locked = self.cfg[86] == 0x00
        self.slot0 = atecc.decode_slot(self.cfg, 0)
        self.key = None
        self.counter = None
        if self.config_locked:
            try:
                self.key = c.pubkey(0)
            except atecc.AteccError:
                self.key = None
            try:
                self.counter = c.counter(0)
            except atecc.AteccError:
                pass
        return self

    def step(self):
        if not self.config_locked:
            if self.profile == "quorum-v1":
                return "C3"
            return "C1" if self.sig.snapshot() is None else "C2"
        if self.profile != "quorum-v1":
            return "other"
        if self.key is None:
            return "C4"
        if not self.slot0["locked"]:
            # The seal only after the test signatures passed, in this session: a failed C5 raises
            # the counter too, so the counter cannot say whether the key works. After a reboot, C5
            # again: two more counts, nothing lost.
            return "C6" if self.tested else "C5"
        if not self.data_locked:
            if not self.owner_seen:
                return "C7"
            return "C8" if self.record is None else "C9"
        return "C10"

    def owner(self):
        import webauthn
        import quorum_cfg
        x, y = self.key
        return webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"])

    def fingerprint(self):
        return "%08x" % (self.key[0] >> 224) if self.key else "none"

    # --- the steps: each returns (ok, [(check, ok), ...], message) -------------------
    def run(self, step):
        fn = getattr(self, "c" + step[1:]) if step.startswith("C") else self.cother
        try:
            out = fn()
        except Exception as e:
            out = (False, [], "%s" % e)
        self.read()
        return out

    def c1(self):
        c = self.chip
        cfg = self.cfg
        rnd = c.random()
        checks = [("answers at 0x60", c.addr == 0x60),
                  ("rev %s %s" % (self.revision, chipcfg.REVISIONS.get(self.revision, "?")), self.revision in chipcfg.REVISIONS
                   and self.revision == "".join("%02x" % b for b in cfg[4:8])),
                  ("zones unlocked (55 55)", cfg[86] == 0x55 and cfg[87] == 0x55),
                  ("no slot locked (FF FF)", cfg[88] == 0xFF and cfg[89] == 0xFF),
                  ("I2C address byte C0", cfg[16] == 0xC0),
                  ("Random: unlocked pattern", rnd == bytes([0xFF, 0xFF, 0, 0]) * 8),
                  ("self-test passes", c.selftest() == 0),
                  ("table: %s" % self.profile, self.profile == "factory")]
        ok = all(k for _, k in checks)
        if ok:
            self.sig.save_snapshot()
        return ok, checks, "factory config saved as %s" % self.sig.snapshot_path() if ok else "stop here: this is not a fresh chip as expected"

    def c2(self):
        n = write_table(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        crc = chipcfg.config_summary(cfg)
        checks = [("written, %d bytes changed" % n, True), ("reads back as quorum v1", chipcfg.identify(cfg) == "quorum-v1"),
                  ("config CRC %04x" % crc, True)]
        return all(k for _, k in checks), checks, "compare the CRC on the laptop: tools/check_config --summary <snapshot>"

    def c3(self):
        msg = lock_config_crc(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        live = self.chip.random() != bytes([0xFF, 0xFF, 0, 0]) * 8
        s0 = atecc.decode_slot(cfg, 0)
        checks = [("config locked (87 = 00)", cfg[87] == 0x00), ("still quorum v1", chipcfg.identify(cfg) == "quorum-v1"),
                  ("Random is live", live), ("slot 0: P-256, ext sign", s0["kind"] == "P256" and s0["genKey"] and s0["extSign"] and not s0["intSign"])]
        return all(k for _, k in checks), checks, msg

    def c4(self):
        x, y = self.sig.genkey(0)
        valid = self.chip.info(1, 0)[0] == 1
        try:
            self.chip.genkey_new(1)
            refused = False
        except atecc.AteccError:
            refused = True
        checks = [("new key %08x" % (x >> 224), True), ("KeyValid", valid), ("public key reads back", self.chip.pubkey(0) == (x, y)),
                  ("GenKey on slot 1 refused", refused)]
        return all(k for _, k in checks), checks, "the key exists only inside the chip"

    def _sign_ok(self, digest):
        r, s = self.sig.sign(digest, 0)
        x, y = self.chip.pubkey(0)
        return p256.verify(x, y, digest, r, s)

    def c5(self):
        import webauthn
        before = self.chip.counter(0)
        plain = self._sign_ok(hashlib.sha256(b"picowallet").digest())
        ad, fields, digest = webauthn.assertion(bytes(32))
        wa = self._sign_ok(digest)
        after = self.chip.counter(0)
        try:
            self.chip.sign(bytes(32), 1)
            refused = False
        except atecc.AteccError:
            refused = True
        checks = [("plain digest verifies", plain), ("WebAuthn digest verifies", wa),
                  ("counter %d -> %d" % (before, after), after == before + 2), ("Sign on slot 1 refused", refused)]
        self.tested = all(k for _, k in checks)
        return self.tested, checks, "LimitedUse counts every signature" if self.tested else "the key is not sealed: fix this first"

    def c6(self):
        if not self.tested or not self._sign_ok(hashlib.sha256(b"before the seal").digest()):
            return False, [("the key signs and verifies", False)], "not sealed: run C5 again"
        before = self.chip.pubkey(0)
        msg = self.sig.lock_slot(0)
        cfg = self.chip.read_config_all()
        checks = [("slot 0 locked (FE FF)", cfg[88] == 0xFE and cfg[89] == 0xFF),
                  ("same public key", self.chip.pubkey(0) == before),
                  ("signs + verifies", self._sign_ok(hashlib.sha256(b"sealed").digest()))]
        return all(k for _, k in checks), checks, msg

    def c7(self):
        self.owner_seen = True
        return True, [("key %s" % self.fingerprint(), True)], "owner %s. Compare it on the laptop before enrolling." % self.owner()

    def c8(self):
        import image
        try:
            if time.gmtime()[0] < 2026:
                import ntptime      # the record's date; boot.py joined the WiFi
                ntptime.settime()
        except Exception:
            pass
        x, y = self.key
        rec = chipcfg.record_encode(self.chip.serial(), 0, x, y, self.owner(), time.time(), image.BUILD, self.chip.counter(0))
        self.summary = write_record_and_fill(self.sig, rec, TABLE)
        self.record = rec
        return True, [("slots 1-15 zeroed", True), ("record in OTP", True), ("data CRC %04x" % self.summary, True)], \
            "nothing can be read back before the lock: the CRC lock is the check"

    def c9(self):
        msg = lock_data_crc(self.sig, self.summary)
        cfg = self.chip.read_config_all()
        otp = self.chip.read_otp(0) + self.chip.read_otp(1)
        try:
            self.chip.read_data(1, 0)
            secret = False
        except atecc.AteccError:
            secret = True
        try:
            self.chip.write_otp(0, bytes(32))
            frozen = False
        except atecc.AteccError:
            frozen = True
        checks = [("data locked (86 = 00)", cfg[86] == 0x00), ("OTP holds the record", otp == self.record),
                  ("slot 1 unreadable", secret), ("OTP frozen", frozen),
                  ("signs + verifies, sealed", self._sign_ok(hashlib.sha256(b"locked").digest()))]
        return all(k for _, k in checks), checks, msg

    def cother(self):
        return False, [("table: %s" % self.profile, False)], WHAT["other"]

    def c10(self):
        otp = self.chip.read_otp(0) + self.chip.read_otp(1)
        rec = chipcfg.record_decode(otp)
        x, y = self.key
        import chips
        chips.seen(self.serial, "quorum-v1", owner=self.owner(), sealed=rec["date"] if rec else None)
        checks = [("quorum v1, locked 00/00", self.profile == "quorum-v1" and self.config_locked and self.data_locked),
                  ("slot 0 sealed", self.slot0["locked"]),
                  ("record matches this key", chipcfg.record_matches(rec, x, y)),
                  ("counter %s" % self.counter, True),
                  ("ALLOW_* back to False", not (S.flag("ALLOW_LOCK") or S.flag("ALLOW_GENKEY")))]
        return all(k for _, k in checks[:3]), checks, "owner %s" % self.owner()


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
        self.c = ceremony or Ceremony(sig)
        self.result = None      # (step, ok, checks, message) after a run
        self.hold = None
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
                S.arm()
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
            if self.keys.held("A") and self.released:
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
        if S.armed() and time.ticks_ms() % 1000 < 60:
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
                self.hold = time.ticks_ms()
            if time.ticks_diff(time.ticks_ms(), self.hold) >= HOLD_MS:
                self.hold, self.released = None, False
                if not S.armed():
                    S.arm()                 # the first hold arms; let go, then hold again
                else:
                    self.busy(st)
                    self.result = (st,) + self.c.run(st)
            self.dirty = True
        elif self.hold is not None:
            self.hold, self.dirty = None, True
        if S.armed() and time.ticks_ms() % 1000 < 60:
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
            left = S.armed()
            d.text("armed %ds" % left if left else "", 4, 196, self.p["ok"])
            if self.hold is not None:
                frac = min(1, time.ticks_diff(time.ticks_ms(), self.hold) / HOLD_MS)
                d.fill_rect(4, 208, int(232 * frac), 6, self.p["bad"])
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
            left = S.armed()
            if why and not why.startswith("not armed"):
                self.lines(why, 186, self.p["bad"])
            else:
                d.text("armed %ds: hold 3 s to do it" % left if left else "not armed: hold 3 s to arm", 4, 190,
                       self.p["ok"] if left else self.p["accent"])
                if self.hold is not None:
                    frac = min(1, time.ticks_diff(time.ticks_ms(), self.hold) / HOLD_MS)
                    d.fill_rect(4, 202, 232, 6, self.p["dim"])
                    d.fill_rect(4, 202, int(232 * frac), 6, self.p["bad"] if left else self.p["accent"])
        pick = self.p["accent"]
        d.text(("> " if self.choice == 0 else "  ") + ("check" if st in c.FINAL else "do it"), 4, 214,
               pick if self.choice == 0 else self.p["fg"])
        d.text(("> " if self.choice == 1 else "  ") + "back", 120, 214, pick if self.choice == 1 else self.p["fg"])
        d.text("turn: choose   press: go", 4, 228, self.p["muted"])
