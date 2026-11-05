# The provisioning ceremony for a fresh ATECC608: Picoquorum's own config, quorum v1
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
# held 3 s, started with ARM_LEFT of the arm's 60 s to go. Nothing here signs anything but its own
# test digests. Logic (Ceremony, here) and screen (ceremony_ui.py, which the console's practice uses
# too) are apart so test-vectors/run-ceremony.mjs can walk the whole thing on the virtual chip.
import time
import hashlib
import board
import atecc
import chipcfg
import signer as S
import p256
import ceremony_ui
from ceremony_ui import HOLD_MS, ARM_MS, ARM_LEFT, PERMANENT, TITLES, WHAT, palette  # noqa: F401 (brand, claim, chipapp)

TABLE = chipcfg.QUORUM_V1

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
            self.key = self.read_key()
            try:
                self.counter = c.counter(0)
            except atecc.AteccError:
                pass
        return self

    def read_key(self):
        try:
            return self.chip.pubkey(0)
        except atecc.AteccError:
            return None

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
        self.tested = False         # a new key: C5 again before any seal
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
        before, was = self.chip.pubkey(0), self.cfg[88]
        msg = self.sig.lock_slot(0)
        cfg = self.chip.read_config_all()
        # only slot 0's bit clears: FF FF -> FE FF (quorum v3's sealed slot 1: FD FF -> FC FF)
        checks = [("slot 0 locked (%02X FF)" % (was & 0xFE), cfg[88] == was & 0xFE and cfg[89] == 0xFF),
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
        rec = chipcfg.record_encode(self.chip.serial(), 0, x, y, self.owner(), board.unix(), image.BUILD, self.chip.counter(0))
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
class UI(ceremony_ui.UI):
    """ceremony_ui.UI on this module's Ceremony unless another is given (provision_tm's, brand's)."""

    def __init__(self, d, keys, sig, theme="dark", ceremony=None):
        super().__init__(d, keys, sig, theme, ceremony or Ceremony(sig))
