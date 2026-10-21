# The bench half of a branded key (docs/BRANDED-KEYS.md), with an attestation key (docs/ATTESTED-KEYS.md):
# PicoQuorum's config, an attestation key made and sealed in slot 1, a brand record and that key signed
# by key 0000, both zone locks, and no key in slot 0. With no brand key pinned it brands a SPARE with a
# public test key, to settle on silicon what the proposals can't settle on paper, and then runs the
# claim's key steps on it (S1-S3) and the attestation (S4). The brand image's ceremony, on
# provision.py's screen (A/B/X/Y or the knob) and gates. The step comes from the chip's own state, so a
# reboot resumes where the chip is.
#
#   B1   pre-flight, as C1: read-only, the factory config saved as snapshot-<serial>.bin
#   B2   write quorum v3 and read it back (reversible: the config zone is still open)
#   B3   lock the config zone, the chip checking a CRC of the reviewed table   PERMANENT
#   B4   zeros into slots 2-15, the brand record into OTP; no key in slot 0 (rewritable until B6)
#   B4a  GenKey in slot 1: the attestation key (made again until B4b)
#   B4b  lock slot 1: the attestation key can never be replaced               PERMANENT
#   B5   the brand signature, and slot 1's public half, into slot 8 (rewritable until B6)
#   B6   lock the data and OTP zones, the chip checking their CRC               PERMANENT
#   B7   read it all back: record, signature, slot 1 sealed and in slot 8, slot 0 empty, counter 0 = 0
#   S1   GenKey in slot 0 after the data lock (the claim's U2, on silicon)      spare only
#   S2   two test signatures, verified here (U3)                                spare only
#   S3   lock slot 0 (U4)                                                       PERMANENT, spare only
#   S4   slot 1 attests slot 0's key, checked here; writes nothing (U4a)        spare only
#
# KEY 0000 (quorum_cfg "brandKeys") signs at B5, one chip on the bus at a time: the bench asks for
# this chip out and key 0000 in, waits until key 0000's serial reads twice, has it sign the brand
# digest it worked out from B4's record and B4a's key, checks the signature under the pinned key, then
# asks for this chip back and checks its serial before writing slot 8. The record, the attestation key
# and the signature are kept in brand-pending-<serial>.bin, so a restart before B6 neither makes a new
# record nor signs again.
#
# THE TEST KEY, while no brand key is pinned: its private half is printed below, and the record says
# bench 0xFF (chipcfg.TEST_BENCH). Anyone can make that signature: it proves slot 8 holds and reads
# back what was written, nothing else. brand_check refuses it as a brand.
# Nothing here signs anything but the brand digest, S2's test digests and S4's chip-built message.
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

TABLE = chipcfg.QUORUM_V3
PROFILE = "quorum-v3"
SIG_SLOT = 8
ATT = chipcfg.ATT_SLOT
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


def pub64(xy):
    return xy[0].to_bytes(32, "big") + xy[1].to_bytes(32, "big")


def slot8_bytes(sig64, att):
    """Slot 8 as the bench writes it: (r, s) in 0-63, the bench certificate's room (64-223), the
    attestation key's qx || qy (224-287) and the rest zeros."""
    return bytes(sig64) + bytes(chipcfg.ATT_AT - 64) + bytes(att) + bytes(atecc.SLOT_BYTES[SIG_SLOT] - chipcfg.ATT_AT - 64)


LOG = "brand-log.txt"
SWAP_S = 180            # how long B5 waits for each plug, key 0000 in and this chip back


def pending_path(serial):
    return "brand-pending-%s.bin" % serial


def save_pending(serial, rec, att=b"", sig64=b""):
    """B4's record, then B4a's attestation key, then B5's signature. Public, like the chip will be."""
    with open(pending_path(serial), "wb") as f:
        f.write(bytes(rec) + bytes(att) + (bytes(sig64) if att else b""))


def load_pending(serial):
    """(record, attestation key or None, signature or None) kept for this serial, or (None, None, None)."""
    try:
        with open(pending_path(serial), "rb") as f:
            b = f.read()
    except OSError:
        return None, None, None
    rec = chipcfg.brand_decode(b[:64]) if len(b) in (64, 128, 192) else None
    if rec is None or rec["serial"] != serial or rec["version"] != 3:
        return None, None, None
    return b[:64], (b[64:128] or None), (b[128:] or None)


def log(step, out):
    """Every step's full result into brand-log.txt on the board (the screen shows only a few lines):
    the record of what this silicon did, read back over USB."""
    claim.log(LOG, step, out)


ORDER = ("B1", "B2", "B3", "B4", "B4a", "B4b", "B5", "B6", "B7", "S1", "S2", "S3", "S4")
TITLES = {"B1": "Pre-flight", "B2": "Write quorum v3", "B3": "Lock the config", "B4": "Write the brand",
          "B4a": "Attestation key", "B4b": "Seal it", "B5": "Sign the brand", "B6": "Lock the data zone",
          "B7": "Check it", "S1": "Make a key", "S2": "Test signatures", "S3": "Seal slot 0", "S4": "Attest",
          "S5": "Done", "other": "Not for this bench"}
WHAT = {
    "B1": "Reads the chip and saves its factory config. Changes nothing.",
    "B2": "Writes the quorum v3 table and reads it back. Reversible: the config zone is still open.",
    "B3": "Locks the config zone forever. The chip checks a CRC of the reviewed table and refuses if one bit differs.",
    "B4": "Zeros into slots 2-15, the brand record into OTP. No key is made. Rewritable until B6.",
    "B4a": "GenKey in slot 1: the chip's attestation key. It signs only messages the chip builds. Made again until B4b.",
    "B4b": "Locks slot 1 forever: the attestation key can never be replaced. B5 signs its public half.",
    "B5": "The TEST key signs the record and the attestation key; both go into slot 8. A spare, never a brand.",
    "B6": "Locks the data and OTP zones forever: then only the chip's own GenKey can fill slot 0.",
    "B7": "Reads back the record and slot 8, checks the signature, slot 1 sealed, slot 0 empty, counter 0.",
    "S1": "Silicon: GenKey in slot 0 after the data lock. Until S3 it can be made again.",
    "S2": "Signs two test digests with the new key and checks both here.",
    "S3": "Locks slot 0 forever: this key can never be replaced.",
    "S4": "Slot 1 attests slot 0's key: the chip builds the message and signs it. Writes nothing.",
    "S5": "The spare is done: branded with the test key, its key made after the lock, sealed and attested.",
    "other": "This chip's config is locked and is not quorum v3. This bench is for fresh chips.",
}


class Ceremony(P.Ceremony):
    HEADER = "BRAND quorum v3 (spare)"
    NSTEPS = len(ORDER)
    PERMANENT = ("B3", "B4b", "B6", "S3")
    GENKEY = ("B4a", "S1")
    FINAL = ("B7", "S5", "other")
    TITLES = TITLES
    WHAT = WHAT

    def __init__(self, sig):
        self.branded = None         # B4's record (OTP can't be read before the data lock): this session or brand-pending
        self.att = None             # slot 1's public key (qx || qy): made this session, from brand-pending, or sealed
        self.att_live = None        # slot 1's public key as it reads now
        self.signed = None          # B5's slot 8 bytes, this session
        self.kept = None            # a signature over self.branded from brand-pending, written again at B5
        self.checked = False        # B7 passed this session: only then the S steps
        self.attested = False       # S4 passed this session
        self.timing = None
        self.say = lambda what, serial=None: None      # the screen sets it: what B5 asks to be plugged in
        self.brand = bench_key()
        if self.brand:
            self.HEADER = "BRAND quorum v3"
            self.NSTEPS = ORDER.index("B7") + 1
            self.WHAT = dict(WHAT, B5="Key 0000 signs the record and the attestation key: unplug this chip, plug in "
                                      "key 0000, then this chip again. The signature goes into slot 8.",
                             B7="Reads back the record and slot 8, checks the brand as a console will, slot 1 sealed, "
                                "slot 0 empty, counter 0. Then it ships.")
        P.Ceremony.__init__(self, sig)
        if self.config_locked and not self.data_locked and self.profile == PROFILE:
            self.branded, att, self.kept = load_pending(self.serial)
            if self.att is None and att is not None and att == self.att_live:
                self.att = att

    def read_key(self):
        return claim.read_key(self)

    def read(self):
        P.Ceremony.read(self)
        self.slot1 = atecc.decode_slot(self.cfg, ATT)
        self.att_live = None
        if self.config_locked and self.profile == PROFILE:
            try:            # slot 1 is not LimitedUse: a public-key read counts nothing
                self.att_live = pub64(self.chip.pubkey(ATT))
            except atecc.AteccError:
                pass
            if self.slot1["locked"]:
                self.att = self.att_live
        if self.data_locked and self.branded is None:
            try:            # frozen and readable now: the screen shows the chip's own number
                self.branded = bytes(self.chip.read_otp(0)) + bytes(self.chip.read_otp(1))
            except atecc.AteccError:
                pass
        return self

    def index(self, st):
        return ORDER.index(st) + 1 if st in ORDER else 0

    def step(self):
        if not self.config_locked:
            if self.profile == PROFILE:
                return "B3"
            return "B1" if self.sig.snapshot() is None else "B2"
        if self.profile != PROFILE:
            return "other"
        if not self.data_locked:
            if self.key is not None:
                return "other"          # a key before the data lock: not this bench's chip
            if self.branded is None:
                return "B4"
            if not self.slot1["locked"]:
                return "B4b" if self.att is not None and self.att == self.att_live else "B4a"
            return "B5" if self.signed is None else "B6"
        if not self.checked and self.key is None:
            return "B7"
        if self.key is None:
            return "S1" if self.spare() else "B7"      # a branded chip ships with no key: the claim makes it
        if not self.slot0["locked"]:
            return "S3" if self.tested else "S2"
        return "S5" if self.attested else "S4"

    def run(self, step):
        fn = {"B1": self.c1, "B2": self.b2, "B3": self.b3, "B4": self.b4, "B4a": self.b4a, "B4b": self.b4b, "B5": self.b5,
              "B6": self.b6, "B7": self.b7, "S1": self.s1, "S2": self.s2, "S3": self.s3, "S4": self.s4,
              "S5": self.s5}.get(step, self.cother)
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

    def keys(self):
        """The brand keys B7 and S4 check against: the pinned one, or the test key on a spare."""
        if self.brand:
            return chipcfg.brand_keys()
        _, qx, qy = test_key()
        return {chipcfg.key_id(qx, qy).hex(): (qx, qy)}

    def cother(self):
        return False, [("table: %s" % self.profile, False)], WHAT["other"]

    def b2(self):
        n = P.write_table(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        crc = chipcfg.config_summary(cfg, TABLE)
        checks = [("written, %d bytes changed" % n, True), ("reads back as quorum v3", chipcfg.identify(cfg) == PROFILE),
                  ("config CRC %04x" % crc, True)]
        return all(k for _, k in checks), checks, "compare the CRC on the laptop: tools/check_config --summary <snapshot> --v3"

    def b3(self):
        msg = P.lock_config_crc(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        live = self.chip.random() != bytes([0xFF, 0xFF, 0, 0]) * 8
        s1, s8 = atecc.decode_slot(cfg, ATT), atecc.decode_slot(cfg, SIG_SLOT)
        checks = [("config locked (87 = 00)", cfg[87] == 0x00), ("still quorum v3", chipcfg.identify(cfg) == PROFILE),
                  ("Random is live", live), ("slot 1: P-256, internal sign only", s1["kind"] == "P256" and s1["intSign"] and not s1["extSign"]),
                  ("slot 8 readable, never written", not s8["isSecret"] and s8["clearWrite"] == "never")]
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
        save_pending(self.serial, rec, (self.att or b"") if self.slot1["locked"] else b"")
        r = chipcfg.brand_decode(rec)
        return True, [("slots 2-15 zeroed", True), ("record in OTP", True), ("no key made", self.key is None),
                      ("%s, number %s" % ("bench 0" if self.brand else "test bench", chipcfg.brand_number(r)), True)], \
            "nothing can be read back before the lock: B7 reads it"

    def b4a(self):
        xy = self.sig.genkey(ATT)
        att = pub64(xy)
        self.att, self.signed, self.kept = att, None, None
        save_pending(self.serial, self.branded, att)
        checks = [("attestation key %08x" % (xy[0] >> 224), True), ("on the curve", chipcfg.on_curve(att)),
                  ("public key reads back", self.chip.pubkey(ATT) == tuple(xy)), ("no key in slot 0", self.key is None)]
        return all(k for _, k in checks), checks, "made inside the chip: it can't be read out"

    def b4b(self):
        before = self.chip.pubkey(ATT)
        if self.att is None or pub64(before) != self.att:
            return False, [("slot 1 holds B4a's key", False)], "not sealed: make it again at B4a"
        msg = self.sig.lock_slot(ATT)
        cfg = self.chip.read_config_all()
        try:
            self.chip.genkey_new(ATT)
            again = True
        except atecc.AteccError:
            again = False
        try:
            self.chip.sign(bytes(32), ATT)
            ext = True
        except atecc.AteccError:
            ext = False
        checks = [("slot 1 locked", not (cfg[88] >> ATT) & 1), ("slot 0 still open", bool(cfg[88] & 1)),
                  ("same public key", self.chip.pubkey(ATT) == before), ("GenKey on slot 1 refused", not again),
                  ("external Sign on slot 1 refused", not ext)]
        return all(k for _, k in checks), checks, msg

    def b5(self):
        if self.att is None or self.att != self.att_live:
            return False, [("slot 1's key is B4a's", False)], "nothing signed"
        digest = chipcfg.brand_digest(self.branded, self.att)
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
        save_pending(self.serial, self.branded, self.att, sig64)
        self.kept = sig64
        b = slot8_bytes(sig64, self.att)
        for blk in (0, 1, chipcfg.ATT_AT // 32, chipcfg.ATT_AT // 32 + 1):
            self.chip.write_data(SIG_SLOT, blk, b[blk * 32:blk * 32 + 32])
        self.signed = b
        slots = chipcfg.zero_slots(TABLE)
        slots[SIG_SLOT] = b
        self.summary = chipcfg.data_summary(TABLE, slots, self.branded)
        return True, checks + [("signature and slot 1's key into slot 8", True), ("data CRC %04x" % self.summary, True)], \
            "the CRC lock at B6 is the check"

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
        checks). Key 0000 signs only the digest worked out here from B4's record and B4a's key."""
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
            save_pending(mine, self.branded, self.att, sig64)
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
            c.read_data(ATT, 0)
            secret = False
        except atecc.AteccError:
            secret = True
        empty = c.info(1, 0)[0] == 0        # KeyValid: a public-key read would count as a use
        t = time.ticks_ms()
        brand = chipcfg.brand_check(rec, slot8, self.serial, self.revision, self.cfg, self.keys(), self.att_live)
        self.timing = time.ticks_diff(time.ticks_ms(), t)
        checks = [("v3 record in OTP", rec is not None and rec["version"] == 3), ("slot 8 reads in the clear", True)]
        if self.brand:
            checks += brand
        else:
            real = chipcfg.brand_check(rec, slot8, self.serial, self.revision, self.cfg, {}, self.att_live)
            checks += [(l, k) for l, k in brand if l != "bench 0, no certificate"]
            checks.append(("refused as a brand (test bench)", not all(k for _, k in real)))
        checks += [("slot 0 empty (KeyValid 0)", empty), ("slot 1 unreadable", secret),
                   # a finding on a spare (chip 5 read 1); what the claim's "never used" stands on for a brand
                   ("never used: counter 0 = %s" % self.counter, self.counter == 0 or not self.brand), ("verify %d ms" % self.timing, True)]
        self.checked = all(k for _, k in checks)
        if self.checked:
            import chips
            chips.seen(self.serial, PROFILE)
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
        out = claim.attest(self, self.keys(), LOG)
        # docs/ATTESTED-KEYS.md: a host must not steer an internal Sign. A TempKey the host passed
        # through, with no GenKey after it, must be refused.
        c = self.chip
        c.wake()
        try:
            c.command(atecc.OP_NONCE, 0x03, 0x0000, hashlib.sha256(b"a digest the host chose").digest(), resp_len=1, wait_ms=8)
            c.command(atecc.OP_SIGN, chipcfg.SIGN_INTERNAL_SN, ATT, resp_len=64, wait_ms=120)
            steered = True
        except atecc.AteccError:
            steered = False
        finally:
            c.sleep()
        out[1].append(("internal Sign over a host's TempKey refused", not steered))
        self.attested = out[0] and not steered
        return self.attested, out[1], out[2]

    def s5(self):
        x, y = self.key
        checks = [("quorum v3, locked 00/00", self.profile == PROFILE and self.config_locked and self.data_locked),
                  ("slots 0 and 1 sealed", self.slot0["locked"] and self.slot1["locked"]), ("counter %s" % self.counter, True),
                  ("ALLOW_* back to False", not (S.flag("ALLOW_LOCK") or S.flag("ALLOW_GENKEY")))]
        return all(k for _, k in checks[:2]), checks, "owner %s" % self.owner()
