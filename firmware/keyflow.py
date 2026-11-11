# The owner's key on a chip whose config is already locked as quorum v1: the ceremony's steps from
# GenKey to the data lock (docs/PROVISIONING.md), with nothing that writes or locks a config zone.
# provision.py adds C1-C3 for a fresh chip (the ceremony and dual images). console-rp's image carries
# this file and not provision.py: its chips come from the bench prepared (C1-C3 done, no key).
#
#   C4  GenKey in slot 0 (a new key; replaceable until C6)
#   C5  test signatures (a plain digest and a WebAuthn assertion), verified here
#   C6  lock slot 0: the key can never be replaced                            PERMANENT
#   C7  the owner address this key gets on the Safe
#   C8  zeros into slots 1-15 and the record into the OTP zone (rewritable until C9)
#   C9  lock the data and OTP zones, the chip checking their CRC               PERMANENT
#   C10 final checks and the summary
#
# OwnKey is console-rp's route: the customer makes the key on the device (keypick_rp.py), and the holds
# on that screen are the permission (signer.own_key_step). Its steps:
#   unprepared  the config zone is open. Nothing here goes on: only the bench prepares a chip
#   other       a config locked as something other than quorum v1
#   K0          read only, at each start: is there a key in slot 0 (KeyValid), what counter 0 says
#   C4          first at each start, whatever K0 found: a key in slot 0 from before (made at an earlier
#               start, or written in while the data zone was open) is replaced by one GenKey makes now
#   C5, C6      as above. Before the seal, keyflow.json names the key being sealed
#   C7-C9       only when keyflow.json names this chip and this key, else "elsewhere": a chip sealed
#               by something other than this flow is never locked or pinned by it
#   C10         the checks, then pin.json: the console's pin (quorum.py), written here and nowhere else
#   done
# Nothing here signs anything but its own fixed test digests (C5, C6, C9).
import time
import hashlib
import board
import atecc
import chipcfg
import signer as S
import p256
from ceremony_ui import PERMANENT, TITLES, WHAT

TABLE = chipcfg.QUORUM_V1
STATE_FILE = "keyflow.json"     # OwnKey: {"serial", "key"}, the key sealed here (sha256 of its public key)


# ----------------------------------------------------------------------------- chip writes
# Here, not in signer.py, so the console image (which carries signer.py) holds none of them.
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
    """PERMANENT. Lock the data and OTP zones; the chip refuses unless they match `summary`. Needs
    ALLOW_LOCK and the arm, or on console-rp the arm on a prepared chip (signer.own_key_step)."""
    if not S._may("ALLOW_LOCK", "lock_data", sig.chip):
        raise Exception(S._refused("lock"))
    sig._slots = None
    sig.chip.lock_data(summary=summary)
    return "data zone locked (CRC %04x)" % summary


def key_id(x, y):
    """A public key as keyflow.json names it: the SHA-256 of its 64 bytes, in hex."""
    from binascii import hexlify, unhexlify
    return hexlify(hashlib.sha256(unhexlify("%064x%064x" % (x, y))).digest()).decode()


def write_json(path, obj):
    """The whole file or the old one, never half: a .tmp first, then a rename over it."""
    import json
    import os
    with open(path + ".tmp", "w") as f:
        json.dump(obj, f)
    os.rename(path + ".tmp", path)


def read_json(path):
    try:
        import json
        with open(path) as f:
            v = json.load(f)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


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
        self._own = (None, "")      # (key, its owner address): two Keccaks, worked out once a key
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
            return self.step_open()
        if self.profile != "quorum-v1":
            return "other"
        return self.step_key()

    def step_open(self):
        """The config zone is still open: nothing here writes it (provision.Ceremony does)."""
        return "unprepared"

    def step_key(self):
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
        if self._own[0] != self.key:
            import webauthn
            import quorum_cfg
            x, y = self.key
            self._own = (self.key, webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"]))
        return self._own[1]

    def fingerprint(self):
        return "%08x" % (self.key[0] >> 224) if self.key else "none"

    def date(self):
        """The record's date: this board's clock, or the image's build date if the clock is behind it
        (no RTC and no network: an RP2350 starts in 2021)."""
        import image
        return max(board.unix(), image.DATE)

    # --- the steps: each returns (ok, [(check, ok), ...], message) -------------------
    def run(self, step):
        fn = getattr(self, step.lower(), None) if step[:1] in ("C", "K") else None
        try:
            out = (fn or self.cother)()
        except Exception as e:
            out = (False, [], "%s" % e)
        self.read()
        return out

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
        x, y = self.key
        rec = chipcfg.record_encode(self.chip.serial(), 0, x, y, self.owner(), self.date(), image.BUILD, self.chip.counter(0))
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


class OwnKey(Ceremony):
    """console-rp's route (the steps at the top of this file). The screen is keypick_rp.UI."""
    HEADER = "YOUR KEY"

    def __init__(self, sig):
        self.made = False           # a key made at this start: until then C4 comes first
        self.checked = None         # K0's checks at this start
        self.had_key = False        # K0 found a key in slot 0
        super().__init__(sig)

    def read(self):
        super().read()
        self._known = {}            # mine() and pinned(), worked out once a read: step() runs each tick
        return self

    def step_key(self):
        if not self.slot0["locked"]:
            if self.checked is None:
                return "K0"
            if not self.made:
                return "C4"
            return super().step_key()
        if self.data_locked and self.pinned():
            return "done"
        if not self.mine():
            return "elsewhere"          # never locked, or pinned, from here
        return super().step_key()

    def mine(self):
        """keyflow.json names this chip and the key in its slot 0: this flow sealed it."""
        if "mine" not in self._known:
            st = read_json(STATE_FILE)
            self._known["mine"] = bool(st and self.key and st.get("serial") == self.serial and st.get("key") == key_id(*self.key))
        return self._known["mine"]

    def pinned(self):
        """pin.json names this chip and its key's owner."""
        if "pinned" not in self._known:
            import policy
            p = policy.pick(policy.pins(policy.pin_file()), self.serial)
            self._known["pinned"] = bool(p and self.key) and str(p.get("owner", "")).lower() == self.owner().lower()
        return self._known["pinned"]

    def k0(self):
        """Read only. Before anything is made: the chip as the bench left it, and whether slot 0 holds a
        key already. A key there, or a count on counter 0, is said, not refused: C4 replaces the key."""
        cfg = self.cfg
        self.had_key = self.chip.info(1, 0)[0] == 1
        checks = [("quorum v1, config locked", self.profile == "quorum-v1" and self.config_locked),
                  ("data zone open (86 = 55)", cfg[86] == 0x55),
                  ("slot 0 not sealed", bool(cfg[88] & 1)),
                  ("no key in slot 0 yet" if not self.had_key else "a key from before: Make replaces it", not self.had_key),
                  ("counter 0 at %s" % self.counter, self.counter == 0)]
        self.checked = checks
        return True, checks, "no key yet" if all(k for _, k in checks) else "Make replaces what is there"

    def c4(self):
        out = super().c4()
        self.made = self.made or out[0]
        return out

    def c6(self):
        if self.key and self.tested:
            write_json(STATE_FILE, {"serial": self.serial, "key": key_id(*self.key)})     # before the seal
        return super().c6()

    def c10(self):
        ok, checks, msg = super().c10()
        if ok:
            import policy
            pin = {"serial": self.serial, "slot": 0, "owner": self.owner(), "locked": True}
            write_json(policy.PIN_FILE, pin)
            got = policy.pick(policy.pins(policy.pin_file()), self.serial)
            ok = bool(got) and policy.expect_check(got, self.serial, 0, self.slot0, self.owner())[0]
            checks.append(("pinned: pin.json", ok))
        return ok, checks, msg
