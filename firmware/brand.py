# The bench half of a branded key (docs/BRANDED-KEYS.md): PicoQuorum's config, a brand record signed
# by key 0000, both zone locks, and no key. With no brand key pinned it brands a SPARE with a public
# test key, to settle on silicon what the proposal can't settle on paper, and then runs the claim's
# key steps on it (S1-S3). The brand image's ceremony, on provision.py's screen (A/B/X/Y or the knob)
# and gates. The step comes from the chip's own state, so a reboot resumes where the chip is.
#
#   B1  pre-flight, as C1: read-only, the factory config saved as snapshot-<serial>.bin
#   B2  write quorum v2 and read it back (reversible: the config zone is still open)
#   B3  lock the config zone, the chip checking a CRC of the reviewed table   PERMANENT
#   B4  zeros into slots 1-15, the brand record into OTP; no key is made (rewritable until B6)
#   B5  the brand signature into slot 8 (rewritable until B6)
#   B6  lock the data and OTP zones, the chip checking their CRC               PERMANENT
#   B7  read it all back: record, signature, slot 0 empty, counter 0 = 0
#   S1  GenKey in slot 0 after the data lock (the claim's U2, on silicon)      spare only
#   S2  two test signatures, verified here (U3)                                spare only
#   S3  lock slot 0 (U4)                                                       PERMANENT, spare only
#
# KEY 0000 (quorum_cfg "brandKeys") signs at B5, one chip on the bus at a time: the bench asks for
# this chip out and key 0000 in, waits until key 0000's serial reads twice, has it sign the brand
# digest it worked out from B4's record, checks the signature under the pinned key, then asks for this
# chip back and checks its serial before writing slot 8. The record and the signature are kept in
# brand-pending-<serial>.bin, so a restart before B6 neither makes a new record nor signs again.
#
# THE TEST KEY, while no brand key is pinned: its private half is printed below, and the record says
# bench 0xFF (chipcfg.TEST_BENCH). Anyone can make that signature: it proves slot 8 holds and reads
# back what was written, nothing else. brand_check refuses it as a brand.
# Nothing here signs anything but the brand digest and S2's test digests.
import time
import hashlib
import board
import atecc
import chipcfg
import p256
import quorum_cfg
import signer as S
import provision as P
import claim

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


def bench_key():
    """(qx, qy, serial) of the pinned brand key, which signs at B5, or None: then the public test
    key, on the test bench. The bench doesn't choose between brand keys."""
    keys = quorum_cfg.CFG.get("brandKeys", {})
    if len(keys) > 1:
        raise Exception("more than one brand key pinned: the bench doesn't choose")
    for kid, k in keys.items():
        qx, qy = int(k["qx"], 16), int(k["qy"], 16)
        if chipcfg.key_id(qx, qy).hex() != kid:
            raise Exception("brandKeys: id %s isn't its key's" % kid)
        return qx, qy, k["serial"]
    return None


def slot8_bytes(sig64):
    """Slot 8 as the bench writes it: (r, s) in 0-63, the bench certificate's room (64-223) and the rest zeros."""
    return bytes(sig64) + bytes(atecc.SLOT_BYTES[SIG_SLOT] - 64)


LOG = "brand-log.txt"
SWAP_S = 180            # how long B5 waits for each plug, key 0000 in and this chip back


def pending_path(serial):
    return "brand-pending-%s.bin" % serial


def save_pending(serial, rec, sig64=b""):
    """B4's record, then B5's signature once there is one. Public, like the chip will be."""
    with open(pending_path(serial), "wb") as f:
        f.write(bytes(rec) + bytes(sig64))


def load_pending(serial):
    """(record, signature or None) kept for this serial, or (None, None)."""
    try:
        with open(pending_path(serial), "rb") as f:
            b = f.read()
    except OSError:
        return None, None
    rec = chipcfg.brand_decode(b[:64]) if len(b) in (64, 128) else None
    if rec is None or rec["serial"] != serial:
        return None, None
    return b[:64], (b[64:] or None)


def log(step, out):
    """Every step's full result into brand-log.txt on the board (the screen shows only a few lines):
    the record of what this silicon did, read back over USB."""
    claim.log(LOG, step, out)


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
        self.branded = None         # B4's record (OTP can't be read before the data lock): this session or brand-pending
        self.signed = None          # B5's slot 8 bytes, this session
        self.kept = None            # a signature over self.branded from brand-pending, written again at B5
        self.checked = False        # B7 passed this session: only then the S steps
        self.timing = None
        self.say = lambda what, serial=None: None      # the screen sets it: what B5 asks to be plugged in
        self.brand = bench_key()
        if self.brand:
            self.HEADER = "BRAND quorum v2"
            self.WHAT = dict(WHAT, B5="Key 0000 signs the record: unplug this chip, plug in key 0000, then this chip "
                                      "again. The signature goes into slot 8.",
                             B7="Reads back the record and slot 8, checks the brand as a console will, slot 0 empty, "
                                "counter 0. Then it ships.")
        P.Ceremony.__init__(self, sig)
        if self.config_locked and not self.data_locked and self.profile == "quorum-v2":
            self.branded, self.kept = load_pending(self.serial)

    def read_key(self):
        return claim.read_key(self)

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
            return "S1" if self.spare() else "B7"      # a branded chip ships with no key: the claim makes it
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

    def spare(self):
        """A test-bench record: the S steps may make and seal a key on it."""
        rec = chipcfg.brand_decode(self.branded) if self.branded else None
        return rec is not None and rec["bench"] == chipcfg.TEST_BENCH

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
        qx, qy = self.brand[:2] if self.brand else test_key()[1:]
        bench = 0 if self.brand else chipcfg.TEST_BENCH
        rec = chipcfg.brand_encode(self.chip.serial(), self.chip.revision(), chipcfg.locked_summary(self.cfg, TABLE),
                                   int(S.setting("BRAND_BATCH", 0)), bench, int(S.setting("BRAND_SEQ", 1)),
                                   board.unix(), image.BUILD, chipcfg.key_id(qx, qy))
        P.write_record_and_fill(self.sig, rec, TABLE)
        self.branded, self.signed, self.kept = rec, None, None
        save_pending(self.serial, rec)
        r = chipcfg.brand_decode(rec)
        return True, [("slots 1-15 zeroed", True), ("record in OTP", True), ("no key made", self.key is None),
                      ("%s, number %s" % ("bench 0" if self.brand else "test bench", chipcfg.brand_number(r)), True)], \
            "nothing can be read back before the lock: B7 reads it"

    def b5(self):
        digest = chipcfg.brand_digest(self.branded)
        qx, qy = self.brand[:2] if self.brand else test_key()[1:]
        checks = []
        if self.kept and p256.verify(qx, qy, digest, int.from_bytes(self.kept[:32], "big"), int.from_bytes(self.kept[32:], "big")):
            sig64 = self.kept           # signed before a restart: written again, not signed again
            checks.append(("the signature kept in %s" % pending_path(self.serial), True))
        elif self.brand:
            sig64, more = self.sign_by_key0000(qx, qy, self.brand[2], digest)
            checks += more
        else:
            r, s = p256.sign(test_key()[0], digest)
            sig64 = r.to_bytes(32, "big") + s.to_bytes(32, "big")
            checks.append(("test key signs", p256.verify(qx, qy, digest, r, s)))
        save_pending(self.serial, self.branded, sig64)
        self.kept = sig64
        b = slot8_bytes(sig64)
        self.chip.write_data(SIG_SLOT, 0, b[0:32])
        self.chip.write_data(SIG_SLOT, 1, b[32:64])
        self.signed = b
        slots = chipcfg.zero_slots(TABLE)
        slots[SIG_SLOT] = b
        self.summary = chipcfg.data_summary(TABLE, slots, self.branded)
        return True, checks + [("into slot 8", True), ("data CRC %04x" % self.summary, True)], "the CRC lock at B6 is the check"

    def wait_chip(self, want, other):
        """Poll the bus until the chip at 0x60 reads `want`'s serial twice running. A chip that is
        neither `want` nor `other` (the one just asked to be unplugged) is shown as the wrong one.
        False after SWAP_S."""
        t, last, told = time.ticks_ms(), None, None
        while time.ticks_diff(time.ticks_ms(), t) < SWAP_S * 1000:
            try:
                now = "".join("%02x" % b for b in self.chip.serial())
            except Exception:
                now = None
            if now is not None and now == last:
                if now == want:
                    return True
                if now != other and now != told:
                    self.say("wrong", now)
                    told = now
            last = now
            time.sleep_ms(300)
        return False

    def sign_by_key0000(self, qx, qy, serial0, digest):
        """B5 on a real bench: this chip out, key 0000 in, the signature, this chip back. -> (r||s,
        checks). Key 0000 signs only the digest worked out here from B4's record."""
        mine = self.serial
        self.say("key0000")
        if not self.wait_chip(serial0, mine):
            raise Exception("key 0000 (%s) didn't come in %d s: nothing signed" % (serial0, SWAP_S))
        self.sig._slots = None
        before = self.chip.counter(0)
        r, s = self.sig.sign(digest, 0)
        after = self.chip.counter(0)
        good = p256.verify(qx, qy, digest, r, s)
        sig64 = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        if good:
            save_pending(mine, self.branded, sig64)
        self.say("back")
        if not self.wait_chip(mine, serial0):
            raise Exception("chip %s didn't come back in %d s: plug it in, then B5 again (the signature is kept)" % (mine, SWAP_S))
        self.sig._slots = None
        if not good:
            raise Exception("the chip with key 0000's serial doesn't sign as key 0000: nothing written")
        return sig64, [("key 0000 (%s) signs" % serial0[-8:], good), ("key 0000 counter %d -> %d" % (before, after), after == before + 1),
                       ("chip %s back" % mine[-8:], True)]

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
        rec, slot8 = claim.read_brand(c)
        try:
            c.read_data(1, 0)
            secret = False
        except atecc.AteccError:
            secret = True
        empty = c.info(1, 0)[0] == 0        # KeyValid: a public-key read would count as a use
        t = time.ticks_ms()
        if self.brand:
            brand = chipcfg.brand_check(rec, slot8, self.serial, self.revision, self.cfg, chipcfg.brand_keys())
        else:
            _, qx, qy = test_key()
            brand = chipcfg.brand_check(rec, slot8, self.serial, self.revision, self.cfg, {chipcfg.key_id(qx, qy).hex(): (qx, qy)})
        self.timing = time.ticks_diff(time.ticks_ms(), t)
        checks = [("v2 record in OTP", rec is not None), ("slot 8 reads in the clear", True)]
        if self.brand:
            checks += brand
        else:
            real = chipcfg.brand_check(rec, slot8, self.serial, self.revision, self.cfg, {})
            checks += [(l, k) for l, k in brand if l != "bench 0, no certificate"]
            checks.append(("refused as a brand (test bench)", not all(k for _, k in real)))
        checks += [("slot 0 empty (KeyValid 0)", empty), ("slot 1 unreadable", secret),
                   # a finding on a spare (chip 5 read 1); what the claim's "never used" stands on for a brand
                   ("never used: counter 0 = %s" % self.counter, self.counter == 0 or not self.brand), ("verify %d ms" % self.timing, True)]
        self.checked = all(k for _, k in checks)
        if self.checked:
            import chips
            chips.seen(self.serial, "quorum-v2")
        if not rec:
            return self.checked, checks, "no record"
        if self.brand:
            return self.checked, checks, "PicoQuorum key %s, batch %d: ready to ship, no key inside." % (chipcfg.brand_number(rec), rec["batch"])
        return self.checked, checks, "number %s, test bench. The S steps make a key." % chipcfg.brand_number(rec)

    def s1(self):
        return claim.make_key(self)

    def s2(self):
        return claim.test_sigs(self)

    def s3(self):
        return self.c6()

    def s4(self):
        x, y = self.key
        checks = [("quorum v2, locked 00/00", self.profile == "quorum-v2" and self.config_locked and self.data_locked),
                  ("slot 0 sealed", self.slot0["locked"]), ("counter %s" % self.counter, True),
                  ("ALLOW_* back to False", not (S.flag("ALLOW_LOCK") or S.flag("ALLOW_GENKEY")))]
        return all(k for _, k in checks[:2]), checks, "owner %s" % self.owner()
