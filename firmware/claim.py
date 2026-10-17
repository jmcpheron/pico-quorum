# The user's half of a branded key (docs/BRANDED-KEYS.md): a chip the bench branded and locked,
# with no key in it, gets its key from this console. On the dual image, which routes a quorum v2
# chip locked 00/00 with slot 0 unsealed here; on provision.py's screen and gates, in brand_ui.py's
# pictures. It can make slot 0's key and seal it, nothing else: the config, OTP and slot 8 are
# frozen by the bench's locks, and it locks no zone.
#
#   U1  check the brand with no network: key 0000's signature, this serial, revision and config,
#       both zones locked, counter 0 = 0 while there is no key
#   U2  GenKey in slot 0, made again in every session until U4 (a key found at plug-in was not made
#       here, so it is replaced)
#   U3  two test signatures, verified here, the counter up by exactly 2
#   U4  lock slot 0                                                            PERMANENT
#   U5  the owner address. tools/fw ceremony finish pins it and puts the console back.
#
# The brand bench's spare runs U2-U4 as its S1-S3 (brand.py), so both use make_key, test_sigs and
# provision's c6. GenKey needs ALLOW_GENKEY, the lock ALLOW_LOCK, as in the ceremony, with the arm
# and a 3 s hold. Nothing here signs anything but U3's test digests and c6's.
import hashlib
import board
import atecc
import chipcfg
import p256
import signer as S
import provision as P

SIG_SLOT = 8
LOG = "claim-log.txt"


def log(path, step, out):
    """A step's full result into `path` on the board, one line and then a line a check: the screen
    shows only a few. brand.py logs through it too."""
    ok, checks, msg = out
    try:
        with open(path, "a") as f:
            f.write("%d %s %s: %s\n" % (board.unix(), step, "ok" if ok else "STOPPED", msg))
            for label, k in checks:
                f.write("  %s %s\n" % ("ok" if k else "NO", label))
    except OSError:
        pass


def read_key(c):
    """Slot 0's public key, or None. Once the data zone is locked a public-key read counts as a use
    (chip 2, silicon), so an empty slot is told by Info KeyValid, which counts nothing, and is never
    read: the bench's reads made chip 5's counter 1 before it had a key."""
    if c.data_locked:
        try:
            if c.chip.info(1, 0)[0] != 1:
                return None
        except atecc.AteccError:
            return None
    return P.Ceremony.read_key(c)


def read_brand(chip):
    """(record with "_raw", slot 8's bytes) of a data-locked chip; the record is None when OTP holds none."""
    otp = bytes(chip.read_otp(0)) + bytes(chip.read_otp(1))
    slot8 = b"".join(bytes(chip.read_data(SIG_SLOT, b)) for b in range(atecc.SLOT_BYTES[SIG_SLOT] // 32))
    rec = chipcfg.brand_decode(otp)
    if rec:
        rec["_raw"] = otp
    return rec, slot8


def make_key(c):
    """U2 (the spare's S1): GenKey in slot 0 after the data lock."""
    x, y = c.sig.genkey(0)
    c.made = True
    checks = [("new key %08x" % (x >> 224), True), ("KeyValid", c.chip.info(1, 0)[0] == 1),
              ("public key reads back", c.chip.pubkey(0) == (x, y))]
    return all(k for _, k in checks), checks, "made inside the chip: it can't be read out"


def test_sigs(c):
    """U3 (the spare's S2): C5 after the data lock, where a public-key read counts as a use too: the
    key is read once, before the count, so the counter must rise by the two signatures alone."""
    import webauthn
    x, y = c.chip.pubkey(0)
    before = c.chip.counter(0)
    digest = hashlib.sha256(b"picowallet").digest()
    plain = p256.verify(x, y, digest, *c.sig.sign(digest, 0))
    ad, fields, digest = webauthn.assertion(bytes(32))
    wa = p256.verify(x, y, digest, *c.sig.sign(digest, 0))
    after = c.chip.counter(0)
    try:
        c.chip.sign(bytes(32), 1)
        refused = False
    except atecc.AteccError:
        refused = True
    checks = [("plain digest verifies", plain), ("WebAuthn digest verifies", wa),
              ("counter %d -> %d" % (before, after), after == before + 2), ("Sign on slot 1 refused", refused)]
    c.tested = all(k for _, k in checks)
    return c.tested, checks, "LimitedUse counts every signature" if c.tested else "not sealed: fix this first"


TITLES = {"U1": "Check the brand", "U2": "Make your key", "U3": "Test signatures", "U4": "Seal your key",
          "U5": "Your key is ready", "other": "Not a key to claim"}
WHAT = {
    "U1": "Checks the brand here, with no network: PicoQuorum key 0000's signature, this chip, its locks.",
    "U2": "Your key is made inside the chip. It signs your Safe's approvals, holds no funds, can't be read out.",
    "U3": "Signs two test digests with your key and checks both here. Nothing leaves this console.",
    "U4": "Locks slot 0 forever: your key can never be changed or replaced.",
    "U5": "The Safe owner address of your key. tools/fw ceremony finish pins it.",
    "other": "This chip isn't a branded key waiting for its owner. Nothing was written to it.",
}


class Ceremony(P.Ceremony):
    HEADER = "CLAIM your key"
    NSTEPS = 5
    PERMANENT = ("U4",)
    GENKEY = ("U2",)
    FINAL = ("U5", "other")
    TITLES = TITLES
    WHAT = WHAT
    LOG = LOG

    def __init__(self, sig):
        self.branded = None         # the OTP record, read once the chip is data-locked (the screen's number)
        self.signed = None          # slot 8
        self.checked = False        # U1 passed this session: only then U2
        self.made = False           # U2 ran this session: only a key made here is tested and sealed
        self.sealed_here = False
        self.why = WHAT["other"]
        P.Ceremony.__init__(self, sig)

    def read(self):
        P.Ceremony.read(self)
        if self.data_locked and self.branded is None and self.profile == "quorum-v2":
            try:
                rec, self.signed = read_brand(self.chip)
                self.branded = rec["_raw"] if rec else None
            except atecc.AteccError:
                pass
        return self

    def read_key(self):
        return read_key(self)

    def index(self, st):
        return int(st[1:]) if st[0] == "U" else 0

    def step(self):
        if self.profile != "quorum-v2" or not (self.config_locked and self.data_locked):
            self.why = "Not a branded chip, or its zones aren't both locked. Nothing was written to it."
            return "other"
        if self.slot0["locked"]:
            if self.sealed_here:
                return "U5"
            self.why = "This key was claimed before: slot 0 is sealed. Nothing was written to it."
            return "other"
        if not self.checked:
            return "U1"
        if self.key is None or not self.made:
            return "U2"
        return "U4" if self.tested else "U3"

    def run(self, step):
        fn = {"U1": self.u1, "U2": self.u2, "U3": self.u3, "U4": self.u4, "U5": self.u5}.get(step, self.uother)
        try:
            out = fn()
        except Exception as e:
            out = (False, [], "%s" % e)
        self.read()
        log(LOG, step, out)
        return out

    def uother(self):
        return False, [("table: %s" % self.profile, self.profile == "quorum-v2"),
                       ("locked 00/00", self.config_locked and self.data_locked), ("slot 0 not sealed", not self.slot0["locked"])], self.why

    def u1(self):
        rec = chipcfg.brand_decode(self.branded) if self.branded else None
        if rec:
            rec["_raw"] = self.branded
        checks = chipcfg.brand_check(rec, self.signed or b"", self.serial, self.revision, self.cfg, chipcfg.brand_keys())
        if self.key is None:
            checks.append(("never used: counter 0 = %s" % self.counter, self.counter == 0))
        else:
            checks.append(("a key from an unfinished claim, replaced at U2 (counter %s)" % self.counter, True))
        self.checked = all(k for _, k in checks)
        if not self.checked:
            return False, checks, "Not a PicoQuorum key: its brand doesn't verify. Nothing was written. Don't use it."
        return True, checks, "PicoQuorum key %s, batch %d. Check the number on its label." % (chipcfg.brand_number(rec), rec["batch"])

    def u2(self):
        return make_key(self)

    def u3(self):
        return test_sigs(self)

    def u4(self):
        out = self.c6()
        self.sealed_here = out[0]
        return out

    def u5(self):
        x, y = self.key
        checks = [("quorum v2, locked 00/00", self.profile == "quorum-v2" and self.config_locked and self.data_locked),
                  ("slot 0 sealed", self.slot0["locked"]), ("counter %s" % self.counter, True)]
        return all(k for _, k in checks), checks, "owner %s. A signer, not a wallet: funds go to your Safe." % self.owner()

    def picture(self, st, result=False):
        """U5 draws the owner address's blockie."""
        return self.owner() if st == "U5" and self.key else None
