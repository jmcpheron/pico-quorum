# The bench half of a branded key (docs/BRANDED-KEYS.md), first build: a SPARE chip, branded with a
# public test key, to settle on silicon what the proposal can't settle on paper. The brand image's
# ceremony, on provision.py's screen (A/B/X/Y or the knob) and gates. The step comes from the chip's
# own state, so a reboot resumes where the chip is.
#
#   B1  pre-flight, as C1: read-only, the factory config saved as snapshot-<serial>.bin
#   B2  write quorum v2 and read it back (reversible: the config zone is still open)
#   B3  lock the config zone, the chip checking a CRC of the reviewed table   PERMANENT
#   B4  zeros into slots 1-15, the brand record into OTP; no key is made (rewritable until B6)
#   B5  the brand signature into slot 8 (rewritable until B6)
#   B6  lock the data and OTP zones, the chip checking their CRC               PERMANENT
#   B7  read it all back: record, signature, slot 0 empty, counter 0 = 0
#   S1  GenKey in slot 0 after the data lock (the claim's U2, on silicon)
#   S2  two test signatures, verified here (U3)
#   S3  lock slot 0 (U4)                                                       PERMANENT
#
# THE TEST KEY. Key 0000 doesn't exist yet, so B5 signs with a key whose private half is printed
# below, and the record says bench 0xFF (chipcfg.TEST_BENCH). Anyone can make that signature: it
# proves slot 8 holds and reads back what was written, nothing else. brand_check refuses it as a brand.
# Nothing here signs anything but the brand digest and S2's test digests.
import time
import hashlib
import board
import atecc
import chipcfg
import p256
import signer as S
import provision as P

TABLE = chipcfg.QUORUM_V2
SIG_SLOT = 8
# Public on purpose: SHA-256 of this text, mod n. Never a brand key.
TEST_KEY_TEXT = b"PicoQuorum test bench: a public key, never a brand"
_test = None


def test_key():
    """(d, qx, qy) of the public test key."""
    global _test
    if _test is None:
        d = int.from_bytes(hashlib.sha256(TEST_KEY_TEXT).digest(), "big") % p256.N
        _test = (d,) + tuple(p256.pubkey(d))
    return _test


def key_id(qx, qy):
    return hashlib.sha256(int(qx).to_bytes(32, "big") + int(qy).to_bytes(32, "big")).digest()[:16]


def slot8_bytes(sig64):
    """Slot 8 as the bench writes it: (r, s) in 0-63, the bench certificate's room (64-223) and the rest zeros."""
    return bytes(sig64) + bytes(atecc.SLOT_BYTES[SIG_SLOT] - 64)


def brand_check(rec, slot8, serial, revision, cfg, keys):
    """[(check, ok)] for a chip's brand, as a console would check it, with no network. keys:
    {key id hex: (qx, qy)}, the pinned brand keys. Refuses a test bench, a bench certificate, and
    any bench but 0, rather than guess."""
    if rec is None:
        return [("a v2 brand record in OTP", False)]
    r = int.from_bytes(slot8[0:32], "big")
    s = int.from_bytes(slot8[32:64], "big")
    k = keys.get(rec["keyId"])
    good = k is not None and s <= p256.N // 2 and p256.verify(k[0], k[1], chipcfg.brand_digest(rec["_raw"]), r, s)
    return [("signed by a pinned brand key", good),
            ("serial matches the chip", rec["serial"] == serial),
            ("revision matches", rec["revision"] == revision),
            ("config CRC matches", rec["configCrc"] == chipcfg.locked_summary(cfg, TABLE)),
            ("locked 00/00", cfg[86] == 0x00 and cfg[87] == 0x00),
            ("bench 0, no certificate", rec["bench"] == 0 and slot8[64:224] == bytes(160)),
            ("the rest of slot 8 zeros", slot8[224:] == bytes(len(slot8) - 224))]


LOG = "brand-log.txt"


def log(step, out):
    """Every step's full result into brand-log.txt on the board (the screen shows only a few lines):
    the record of what this silicon did, read back over USB."""
    ok, checks, msg = out
    try:
        with open(LOG, "a") as f:
            f.write("%d %s %s: %s\n" % (board.unix(), step, "ok" if ok else "STOPPED", msg))
            for label, k in checks:
                f.write("  %s %s\n" % ("ok" if k else "NO", label))
    except OSError:
        pass


TITLES = {"B1": "Pre-flight", "B2": "Write quorum v2", "B3": "Lock the config", "B4": "Write the brand",
          "B5": "Sign the brand", "B6": "Lock the data zone", "B7": "Check it", "S1": "Make a key",
          "S2": "Test signatures", "S3": "Seal slot 0", "S4": "Done", "other": "Not for this bench"}
WHAT = {
    "B1": "Reads the chip and saves its factory config. Changes nothing.",
    "B2": "Writes the quorum v2 table and reads it back. Reversible: the config zone is still open.",
    "B3": "Locks the config zone forever. The chip checks a CRC of the reviewed table and refuses if one bit differs.",
    "B4": "Zeros into slots 1-15, the brand record into OTP. No key is made. Rewritable until B6.",
    "B5": "The TEST key signs the record; the signature goes into slot 8. A spare, never a brand.",
    "B6": "Locks the data and OTP zones forever: then only the chip's own GenKey can fill slot 0.",
    "B7": "Reads back the record and slot 8, checks the signature, slot 0 empty, counter 0.",
    "S1": "Silicon: GenKey in slot 0 after the data lock. Until S3 it can be made again.",
    "S2": "Signs two test digests with the new key and checks both here.",
    "S3": "Locks slot 0 forever: this key can never be replaced.",
    "S4": "The spare is done: branded with the test key, its key made after the lock and sealed.",
    "other": "This chip's config is locked and is not quorum v2. This bench is for fresh chips.",
}


class Ceremony(P.Ceremony):
    HEADER = "BRAND quorum v2 (spare)"
    NSTEPS = 10
    PERMANENT = ("B3", "B6", "S3")
    GENKEY = ("S1",)
    FINAL = ("B7", "S4", "other")
    TITLES = TITLES
    WHAT = WHAT

    def __init__(self, sig):
        self.branded = None         # B4's record, this session (OTP can't be read before the data lock)
        self.signed = None          # B5's slot 8 bytes, this session
        self.checked = False        # B7 passed this session: only then the S steps
        self.timing = None
        P.Ceremony.__init__(self, sig)

    def read(self):
        P.Ceremony.read(self)
        if self.data_locked and self.branded is None:
            try:            # frozen and readable now: the screen shows the chip's own number
                self.branded = bytes(self.chip.read_otp(0)) + bytes(self.chip.read_otp(1))
            except atecc.AteccError:
                pass
        return self

    def index(self, st):
        if st[0] == "B":
            return int(st[1:])
        return 7 + int(st[1:]) if st[0] == "S" and st != "S4" else 0

    def step(self):
        if not self.config_locked:
            if self.profile == "quorum-v2":
                return "B3"
            return "B1" if self.sig.snapshot() is None else "B2"
        if self.profile != "quorum-v2":
            return "other"
        if not self.data_locked:
            if self.key is not None:
                return "other"          # a key before the data lock: not this bench's chip
            if self.branded is None:
                return "B4"
            return "B5" if self.signed is None else "B6"
        if not self.checked and self.key is None:
            return "B7"
        if self.key is None:
            return "S1"
        if not self.slot0["locked"]:
            return "S3" if self.tested else "S2"
        return "S4"

    def run(self, step):
        fn = {"B1": self.c1, "B2": self.b2, "B3": self.b3, "B4": self.b4, "B5": self.b5, "B6": self.b6, "B7": self.b7,
              "S1": self.s1, "S2": self.s2, "S3": self.s3, "S4": self.s4}.get(step, self.cother)
        try:
            out = fn()
        except Exception as e:
            out = (False, [], "%s" % e)
        self.read()
        log(step, out)
        return out

    def cother(self):
        return False, [("table: %s" % self.profile, False)], WHAT["other"]

    def b2(self):
        n = P.write_table(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        crc = chipcfg.config_summary(cfg, TABLE)
        checks = [("written, %d bytes changed" % n, True), ("reads back as quorum v2", chipcfg.identify(cfg) == "quorum-v2"),
                  ("config CRC %04x" % crc, True)]
        return all(k for _, k in checks), checks, "compare the CRC on the laptop: tools/check_config --summary <snapshot> --v2"

    def b3(self):
        msg = P.lock_config_crc(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        live = self.chip.random() != bytes([0xFF, 0xFF, 0, 0]) * 8
        s8 = atecc.decode_slot(cfg, SIG_SLOT)
        checks = [("config locked (87 = 00)", cfg[87] == 0x00), ("still quorum v2", chipcfg.identify(cfg) == "quorum-v2"),
                  ("Random is live", live), ("slot 8 readable, never written", not s8["isSecret"] and s8["clearWrite"] == "never")]
        return all(k for _, k in checks), checks, msg

    def b4(self):
        import image
        try:
            if time.gmtime()[0] < 2026:
                import ntptime
                ntptime.settime()
        except Exception:
            pass
        _, qx, qy = test_key()
        rec = chipcfg.brand_encode(self.chip.serial(), self.chip.revision(), chipcfg.locked_summary(self.cfg, TABLE),
                                   int(S.setting("BRAND_BATCH", 0)), chipcfg.TEST_BENCH, int(S.setting("BRAND_SEQ", 1)),
                                   board.unix(), image.BUILD, key_id(qx, qy))
        P.write_record_and_fill(self.sig, rec, TABLE)
        self.branded, self.signed = rec, None
        r = chipcfg.brand_decode(rec)
        return True, [("slots 1-15 zeroed", True), ("record in OTP", True), ("no key made", self.key is None),
                      ("test bench, number %s" % chipcfg.brand_number(r), True)], \
            "nothing can be read back before the lock: B7 reads it"

    def b5(self):
        d, qx, qy = test_key()
        r, s = p256.sign(d, chipcfg.brand_digest(self.branded))
        b = slot8_bytes(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        self.chip.write_data(SIG_SLOT, 0, b[0:32])
        self.chip.write_data(SIG_SLOT, 1, b[32:64])
        self.signed = b
        slots = chipcfg.zero_slots(TABLE)
        slots[SIG_SLOT] = b
        self.summary = chipcfg.data_summary(TABLE, slots, self.branded)
        return True, [("test key signs", p256.verify(qx, qy, chipcfg.brand_digest(self.branded), r, s)),
                      ("into slot 8", True), ("data CRC %04x" % self.summary, True)], "the CRC lock at B6 is the check"

    def b6(self):
        msg = P.lock_data_crc(self.sig, self.summary)
        cfg = self.chip.read_config_all()
        try:
            self.chip.write_otp(0, bytes(32))
            frozen = False
        except atecc.AteccError:
            frozen = True
        checks = [("data locked (86 = 00)", cfg[86] == 0x00), ("OTP frozen", frozen)]
        return all(k for _, k in checks), checks, msg

    def b7(self):
        c = self.chip
        otp = bytes(c.read_otp(0)) + bytes(c.read_otp(1))
        slot8 = b"".join(bytes(c.read_data(SIG_SLOT, b)) for b in range(atecc.SLOT_BYTES[SIG_SLOT] // 32))
        rec = chipcfg.brand_decode(otp)
        if rec:
            rec["_raw"] = otp
        try:
            c.read_data(1, 0)
            secret = False
        except atecc.AteccError:
            secret = True
        try:
            c.pubkey(0)
            empty = False
        except atecc.AteccError:
            empty = True
        _, qx, qy = test_key()
        t = time.ticks_ms()
        test = brand_check(rec, slot8, self.serial, self.revision, self.cfg, {key_id(qx, qy).hex(): (qx, qy)})
        self.timing = time.ticks_diff(time.ticks_ms(), t)
        real = brand_check(rec, slot8, self.serial, self.revision, self.cfg, {})
        checks = [("v2 record in OTP", rec is not None), ("slot 8 reads in the clear", True)]
        checks += [(l, k) for l, k in test if l != "bench 0, no certificate"]
        checks += [("refused as a brand (test bench)", not all(k for _, k in real)),
                   ("slot 0 empty", empty), ("slot 1 unreadable", secret),
                   ("counter 0 = %s (finding)" % self.counter, True), ("verify %d ms" % self.timing, True)]
        self.checked = all(k for _, k in checks)
        if self.checked:
            import chips
            chips.seen(self.serial, "quorum-v2")
        return self.checked, checks, "number %s, test bench. The S steps make a key." % chipcfg.brand_number(rec) if rec else "no record"

    def s1(self):
        x, y = self.sig.genkey(0)
        checks = [("new key %08x after the data lock" % (x >> 224), True), ("KeyValid", self.chip.info(1, 0)[0] == 1),
                  ("public key reads back", self.chip.pubkey(0) == (x, y))]
        return all(k for _, k in checks), checks, "GenKey after the data lock: works on this silicon"

    def s2(self):
        """C5 after the data lock, where a public-key read counts as a use too (chip 2, silicon): the
        key is read once, before the count, so the counter must rise by the two signatures alone."""
        import webauthn
        x, y = self.chip.pubkey(0)
        before = self.chip.counter(0)
        digest = hashlib.sha256(b"picowallet").digest()
        plain = p256.verify(x, y, digest, *self.sig.sign(digest, 0))
        ad, fields, digest = webauthn.assertion(bytes(32))
        wa = p256.verify(x, y, digest, *self.sig.sign(digest, 0))
        after = self.chip.counter(0)
        try:
            self.chip.sign(bytes(32), 1)
            refused = False
        except atecc.AteccError:
            refused = True
        checks = [("plain digest verifies", plain), ("WebAuthn digest verifies", wa),
                  ("counter %d -> %d" % (before, after), after == before + 2), ("Sign on slot 1 refused", refused)]
        self.tested = all(k for _, k in checks)
        return self.tested, checks, "LimitedUse counts every signature" if self.tested else "not sealed: fix this first"

    def s3(self):
        return self.c6()

    def s4(self):
        x, y = self.key
        checks = [("quorum v2, locked 00/00", self.profile == "quorum-v2" and self.config_locked and self.data_locked),
                  ("slot 0 sealed", self.slot0["locked"]), ("counter %s" % self.counter, True),
                  ("ALLOW_* back to False", not (S.flag("ALLOW_LOCK") or S.flag("ALLOW_GENKEY")))]
        return all(k for _, k in checks[:2]), checks, "owner %s" % self.owner()
