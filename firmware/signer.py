# The thing that holds the keys. Two backends with one shape:
#   slot                       the active slot; sign() and pubkey() use it unless told otherwise
#   slots() -> [dict]          the slot table: kind, hasKey, qx/qy, locked, genKey, ... (see atecc.decode_slot)
#   pubkey(slot=None) -> (x, y)
#   sign(digest, slot=None) -> (r, s) low-s
#   genkey(slot=None) -> (x, y)      NEW random key in the slot, replacing the old one
#   use(slot)                        make a slot the active signer (persisted in slot.txt)
#   lock_config() / lock_data() / lock_slot(slot)      permanent, gated by secrets.ALLOW_LOCK
#   status() -> dict                 what the app sees on announce
#   allowed(what) -> bool            "genkey" or "lock": may it happen right now (secrets.py flag AND the wallet is armed)
#   gate(what) -> str                "" when allowed, else why not ("not armed", "ALLOW_LOCK is False")
#   write_config() / restore_snapshot()   REVERSIBLE while the config zone is open; snapshot() the original bytes
#   provision()                      write the wallet config and lock it (the app's lock-config command)
#   config() -> bytes                the 128 config bytes (the software signer fakes them)
#   random() -> bytes                32 bytes from the chip's RNG, a harmless "is it alive" test
#   name
# The console's view of a chip, the same on both kinds (quorum.py):
#   serial(fresh=False) -> str       cached; fresh reads it off the chip again
#   key_row() -> dict                the key's slot row: kind, extSign, locked, limitedUse (atecc.decode_slot's shape)
#   profile() -> str                 quorum-v1, factory, ... / quorum-tm1, ...
#   use_counter() -> int | None      a count the chip raises on every use of the key, if it keeps one
#   needs_ceremony() -> bool         a fresh chip, or one half way through its ceremony
#   info() -> [str]                  short facts from the chip for the screens
# SoftSigner: P-256 keys in files on the Pico's flash, one per slot. Only until the ATECC608 is wired.
# ChipSigner: the ATECC608 over I2C. TrustMSigner: the OPTIGA Trust M. The keys never leave the chip.
# detect() says which of them answer on I2C0; load() picks one.
import os
import time
import p256

KEY_FILE = "key.bin"        # slot 0 of the software signer, the file older firmware used
SLOT_FILE = "slot.txt"      # the active slot, both backends
SOFT_SLOTS = 8              # the software signer pretends to be a chip with 8 P-256 slots


def _read_slot():
    try:
        return int(open(SLOT_FILE).read().strip())
    except Exception:
        return 0


def _write_slot(n):
    with open(SLOT_FILE, "w") as f:
        f.write(str(n))


# ARM: permanent actions also need someone at the device. Hold B and Y together for 3 s on the
# wallet (chipmap.py) and it is armed for a minute; every red action, including the ones the app
# can request over WiFi, is refused until then. This lives here, not on the chip: it is the wallet's
# own safety catch, the chip knows nothing about it.
ARM_SECONDS = 60
_armed_until = None


def arm(seconds=ARM_SECONDS):
    global _armed_until
    _armed_until = time.ticks_add(time.ticks_ms(), seconds * 1000)


def disarm():
    global _armed_until
    _armed_until = None


def armed():
    """Seconds left on the arm, 0 when not armed."""
    if _armed_until is None:
        return 0
    left = time.ticks_diff(_armed_until, time.ticks_ms())
    return (left + 999) // 1000 if left > 0 else 0


def flag(name):
    """A secrets.py flag; False when secrets.py is missing, and always False on the production
    console image, so an ALLOW_* left in a pushed secrets.py can never arm anything there."""
    import image
    if image.PRODUCTION:
        return False
    try:
        import secrets
    except ImportError:
        return False        # no secrets.py on the board: every permanent action is off
    return bool(getattr(secrets, name, False))


def gate(what):
    """Why a permanent action may not run now: "" when it may."""
    name = "ALLOW_GENKEY" if what == "genkey" else "ALLOW_LOCK"
    if not flag(name):
        return "%s is False on the board" % name
    if not armed():
        return "not armed: hold B+Y 3 s"
    return ""


def _allowed(name):
    return flag(name) and armed() > 0


def _refused(what):
    return "%s refused: %s" % (what, gate(what))


def _fp(x):
    """8 hex chars of qx: enough to tell keys apart on a 240 px screen."""
    return "%08x" % (x >> 224)


class SoftSigner:
    name = "pico-soft"

    def __init__(self):
        self.slot = _read_slot()
        self._pub = {}

    def _file(self, slot):
        return KEY_FILE if slot == 0 else "key%d.bin" % slot

    def _scalar(self, slot):
        f = self._file(slot)
        if f in os.listdir():
            return int.from_bytes(open(f, "rb").read(), "big")
        if slot == 0:
            # the first boot of a bare Pico makes a slot-0 key on its own, as before
            d = p256.rand_scalar()
            open(f, "wb").write(d.to_bytes(32, "big"))
            return d
        return None

    def pubkey(self, slot=None):
        slot = self.slot if slot is None else slot
        if slot not in self._pub:
            d = self._scalar(slot)
            if d is None:
                raise Exception("slot %d is empty" % slot)
            self._pub[slot] = p256.pubkey(d)
        return self._pub[slot]

    def sign(self, digest, slot=None):
        slot = self.slot if slot is None else slot
        d = self._scalar(slot)
        if d is None:
            raise Exception("slot %d is empty" % slot)
        return p256.sign(d, digest)

    def genkey(self, slot=None):
        slot = self.slot if slot is None else slot
        if slot >= SOFT_SLOTS:
            raise Exception("slot %d is not a key slot" % slot)
        d = p256.rand_scalar()
        open(self._file(slot), "wb").write(d.to_bytes(32, "big"))
        self._pub[slot] = p256.pubkey(d)
        return self._pub[slot]

    def use(self, slot):
        self.pubkey(slot)   # must hold a key
        self.slot = slot
        _write_slot(slot)

    def slots(self):
        out = []
        for n in range(16):
            s = {"slot": n, "kind": "P256" if n < SOFT_SLOTS else "DATA", "locked": False, "lockable": False,
                 "genKey": n < SOFT_SLOTS, "extSign": n < SOFT_SLOTS, "pubInfo": n < SOFT_SLOTS,
                 "privWrite": False, "limitedUse": False, "hasKey": False}
            if n < SOFT_SLOTS:
                try:
                    s["qx"], s["qy"] = self.pubkey(n)
                    s["hasKey"] = True
                except Exception:
                    pass
            out.append(s)
        return out

    def lock_config(self):
        return "software key: nothing to lock"

    def lock_data(self):
        return "software key: nothing to lock"

    def lock_slot(self, slot):
        return "software key: nothing to lock"

    def allowed(self, what):
        return True

    def gate(self, what):
        return ""

    def config(self):
        from atecc import CONFIG
        return CONFIG

    def snapshot(self):
        return None

    def write_config(self):
        return 0

    def restore_snapshot(self):
        return 0

    def provision(self):
        return "software key: nothing to lock"

    def sign_test(self, slot=None):
        import hashlib
        slot = self.slot if slot is None else slot
        digest = hashlib.sha256(b"picowallet").digest()
        r, s = self.sign(digest, slot)
        qx, qy = self.pubkey(slot)
        return p256.verify(qx, qy, digest, r, s), r, s

    def write_note(self, text, slot=12):
        raise Exception("software key: no data slots")

    def read_note(self, slot=12):
        raise Exception("software key: no data slots")

    def random(self):
        return os.urandom(32)

    def status(self):
        st = {"configLocked": True, "dataLocked": False, "slot": self.slot, "activeSlot": self.slot,
              "note": "software keys on the Pico (no chip yet)"}
        try:
            x, _ = self.pubkey()
            st["hasKey"] = True
            st["fingerprint"] = _fp(x)
        except Exception:
            st["hasKey"] = False
        st["slots"] = summary(self.slots())
        return st


class ChipSigner:
    name = "atecc608"

    def __init__(self, addr=None):
        from atecc import ATECC608
        self.chip = ATECC608(addr=addr)
        self.slot = _read_slot()
        self._pub = {}
        self._slots = None      # cached table; every key op invalidates it
        self._serial = None

    def serial(self, fresh=False):
        if fresh:
            return "".join("%02x" % b for b in self.chip.serial())
        if self._serial is None:
            self._serial = self.serial(True)
        return self._serial

    # --- the console's view (the same methods on TrustMSigner) --------------------
    def key_row(self):
        import atecc
        return atecc.decode_slot(self.config(), self.slot)

    def profile(self):
        import chipcfg
        return chipcfg.identify(self.config())

    def fresh_pubkey(self):
        """The slot's public key read off the chip now, not the cached one."""
        return self.chip.pubkey(self.slot)

    def use_counter(self):
        """Counter 0: every use of a LimitedUse slot raises it (quorum v1's slot 0, chip 1's)."""
        return self.chip.counter(0)

    def needs_ceremony(self):
        """A fresh chip, or quorum v1 with its data zone still open: main_dual.py's rule."""
        import chipcfg
        cfg = self.config()
        p = chipcfg.identify(cfg)
        return p == "factory" or (p == "quorum-v1" and cfg[86] != 0x00)

    def info(self, row=None, counter=None):
        """Short facts for the Signing and Device screens, from the chip itself."""
        rev = "".join("%02x" % b for b in self.chip.revision())
        out = ["Microchip ATECC608%s" % {"00006002": "A", "00006003": "B"}.get(rev, " rev " + rev)]
        if row:
            out.append("Slot %d: P-256, %s" % (self.slot, "sealed (slot lock)" if row.get("locked") else "not sealed"))
            if row.get("limitedUse"):
                out.append("LimitedUse: counter 0 counts every use")
        if counter is not None:
            out.append("Key uses so far: %d" % counter)
        return out

    def pubkey(self, slot=None):
        slot = self.slot if slot is None else slot
        if slot not in self._pub:
            self._pub[slot] = self.chip.pubkey(slot)
        return self._pub[slot]

    def sign(self, digest, slot=None):
        slot = self.slot if slot is None else slot
        r, s = self.chip.sign(digest, slot)
        if s > p256.N // 2:
            s = p256.N - s
        return r, s

    def genkey(self, slot=None):
        """Only when secrets.ALLOW_GENKEY is True: this REPLACES the key in the slot. A vault paired
        to the old key can never be spent again."""
        slot = self.slot if slot is None else slot
        if not _allowed("ALLOW_GENKEY"):
            raise Exception(_refused("genkey"))
        self._slots = None
        self._pub.pop(slot, None)
        self._pub[slot] = self.chip.genkey_new(slot)
        return self._pub[slot]

    def use(self, slot):
        self.pubkey(slot)   # must hold a readable key
        self.slot = slot
        _write_slot(slot)

    def slots(self):
        if self._slots is None:
            self._slots = self.chip.slots()
        return self._slots

    # --- the config zone: reversible while open, then sealed ---------------
    def snapshot_path(self):
        return "snapshot-%s.bin" % self.serial()

    def snapshot(self):
        """This chip's config bytes as this wallet first saw them, or None before the first write."""
        p = self.snapshot_path()
        return open(p, "rb").read() if p in os.listdir() else None

    def save_snapshot(self):
        """Keep the original 128 bytes once, before anything is written. Never overwritten."""
        p = self.snapshot_path()
        if p in os.listdir():
            return False
        with open(p, "wb") as f:
            f.write(self.chip.read_config_all())
        return True

    def write_config(self):
        """REVERSIBLE while the config zone is open: write the wallet's slot table (atecc.CONFIG) and
        read it back, without locking. The chip's original bytes are snapshotted first."""
        self.save_snapshot()
        self._slots = None
        return self.chip.write_config()

    def restore_snapshot(self):
        """REVERSIBLE: put the snapshot's bytes back on the chip (the config zone must still be open)."""
        snap = self.snapshot()
        if snap is None:
            raise Exception("no snapshot saved for this chip yet")
        self._slots = None
        return self.chip.write_config(snap)

    def lock_config(self):
        """PERMANENT. Locks whatever table is on the chip now. Needs ALLOW_LOCK and the wallet armed."""
        if not _allowed("ALLOW_LOCK"):
            raise Exception(_refused("lock"))
        self._slots = None
        self.chip.lock_config()
        return "config zone locked"

    def provision(self):
        """The legacy app's lock-config command. Retired: a fresh chip gets quorum v1 through the
        ceremony (provision.py), zone by zone, each lock checked by the chip against a CRC."""
        raise Exception("provisioning is the ceremony now: the PROVISION screen (docs/PROVISIONING.md)")

    def lock_data(self):
        if not _allowed("ALLOW_LOCK"):
            raise Exception(_refused("lock"))
        self._slots = None
        self.chip.lock_data()
        return "data zone locked"

    def lock_slot(self, slot):
        if not _allowed("ALLOW_LOCK"):
            raise Exception(_refused("lock"))
        self._slots = None
        self.chip.lock_slot(slot)
        return "slot %d locked" % slot

    def sign_test(self, slot=None):
        """Sign SHA-256 of b"picowallet" with the slot and verify it on the Pico. Returns
        (verified, r, s). A signature spends one count on counter 0 if the slot has LimitedUse."""
        import hashlib
        slot = self.slot if slot is None else slot
        digest = hashlib.sha256(b"picowallet").digest()
        r, s = self.sign(digest, slot)
        qx, qy = self.pubkey(slot)
        return p256.verify(qx, qy, digest, r, s), r, s

    def write_note(self, text, slot=12):
        """REVERSIBLE while the data zone is open: put a short line into a clear data slot (with
        the wallet config, slots 12 and 13 are the clear ones: 72 bytes, read and written in clear)."""
        b = text.encode()[:32]
        b = b + bytes(32 - len(b))
        self.chip.write_data(slot, 0, b)
        return len(text)

    def read_note(self, slot=12):
        b = self.chip.read_data(slot, 0)
        return bytes(b).rstrip(b"\x00").decode()

    def allowed(self, what):
        return _allowed("ALLOW_GENKEY" if what == "genkey" else "ALLOW_LOCK")

    def gate(self, what):
        return gate(what)

    def config(self):
        return self.chip.read_config_all()

    def random(self):
        return self.chip.random()

    def status(self):
        st = self.chip.status(self.slot)
        st["allowLock"], st["allowGenkey"] = flag("ALLOW_LOCK"), flag("ALLOW_GENKEY")
        st["armed"] = armed()
        st["activeSlot"] = self.slot
        if st.get("hasKey"):
            st["fingerprint"] = _fp(self.pubkey()[0])
        try:
            st["slots"] = summary(self.slots())
        except Exception as e:
            st["note"] = "slot table: %s" % e
        return st


def summary(slots):
    """The slot table without the big numbers, small enough to send on every announce."""
    out = []
    for s in slots:
        if s["kind"] == "P256":
            row = {"slot": s["slot"], "kind": s["kind"], "hasKey": s.get("hasKey", False), "locked": s["locked"],
                   "genKey": s["genKey"], "lockable": s["lockable"]}
            if s.get("hasKey"):
                row["fingerprint"] = _fp(s["qx"])
            out.append(row)
    return out


class TrustMSigner:
    """The OPTIGA Trust M (trustm_q.py). One key, E0F1 (tmcfg.KEY), made on the chip by the
    Trust M ceremony (provision_tm.py). Its public key comes from the record in F1D0: a Trust M
    never gives a private-key object's public key back. The console checks that record against
    the board's pin (secrets.QUORUM_EXPECT's owner), so a record that lied would fail the pin."""
    name = "trustm"

    def __init__(self):
        import tmcfg
        import trustm_q
        self.chip = trustm_q.TrustM()
        self.slot = tmcfg.KEY
        self._uid = None
        self._meta = None
        self._rec = None
        self._cert = None
        self.bound = None           # binding_ok(): None until checked (a P-256 verify, not free)

    def uid(self, fresh=False):
        if fresh or self._uid is None:
            self._uid = self.chip.uid()
        return self._uid

    def serial(self, fresh=False):
        import tmcfg
        return tmcfg.serial(self.uid(fresh))

    def forget(self):
        """After anything that changes the chip: read it again next time."""
        self._meta = self._rec = None
        self.bound = None

    def key_meta(self):
        if self._meta is None:
            self._meta = self.chip.meta(self.slot)
        return self._meta

    def record(self):
        import tmcfg
        if self._rec is None:
            self._rec = tmcfg.record_decode(self.chip.get(tmcfg.RECORD)) or False
        return self._rec or None

    def cert(self):
        """The factory certificate (E0E0): (der, parsed)."""
        import tmcfg
        if self._cert is None:
            der = tmcfg.cert_der(self.chip.get_all(tmcfg.CERT))
            self._cert = (der, tmcfg.cert_parse(der))
        return self._cert

    def binding_ok(self):
        """F1D1 holds E0F0's signature over this key, under the factory certificate. One verify."""
        import tmcfg
        if self.bound is None:
            try:
                rec = self.record()
                der, c = self.cert()
                b = tmcfg.binding_decode(self.chip.get(tmcfg.BINDING))
                self.bound = bool(rec) and tmcfg.binding_check(b, der, c, self.uid(), self.slot, rec["qx"], rec["qy"])
            except Exception as e:
                print("binding:", e)
                self.bound = False
        return self.bound

    def pubkey(self, slot=None):
        rec = self.record()
        if rec is None or rec["oid"] != (self.slot if slot is None else slot):
            raise Exception("no key record in F1D0: run the Trust M ceremony")
        return rec["qx"], rec["qy"]

    def fresh_pubkey(self):
        """The key from F1D0 read again (the record is sealed with the key)."""
        self._rec = None
        return self.pubkey()

    def sign(self, digest, slot=None):
        r, s = self.chip.sign(self.slot if slot is None else slot, digest)
        if s > p256.N // 2:
            s = p256.N - s
        return r, s

    def genkey(self, slot=None):
        """Only when secrets.ALLOW_GENKEY is True: a NEW key in E0F1, replacing any key there."""
        if not _allowed("ALLOW_GENKEY"):
            raise Exception(_refused("genkey"))
        self.forget()
        return self.chip.gen_keypair(self.slot if slot is None else slot)

    def key_row(self):
        import tmcfg
        return tmcfg.key_row(self.key_meta())

    def profile(self):
        import tmcfg
        return tmcfg.identify(self.key_meta(), self.record())

    def use_counter(self):
        return None         # quorum-tm1 puts no use limit on the key (no Luc counter)

    def needs_ceremony(self):
        return self.profile() in ("factory", "quorum-tm1-open")

    def sec(self):
        return self.chip.sec()

    def info(self, row=None, counter=None, sec=None):
        import tmcfg
        issuer = None
        try:
            issuer = self.cert()[1]["issuer"]
        except Exception:
            pass
        return tmcfg.info_lines(self.uid(), issuer, row or self.key_row(), self.bound, sec)

    def slots(self):
        return [self.key_row()]

    def allowed(self, what):
        return _allowed("ALLOW_GENKEY" if what == "genkey" else "ALLOW_LOCK")

    def gate(self, what):
        return gate(what)

    def random(self):
        return self.chip.random(32)

    def status(self):
        st = {"chip": "trustm", "serial": self.serial(), "activeSlot": self.slot, "profile": self.profile()}
        st["allowLock"], st["allowGenkey"] = flag("ALLOW_LOCK"), flag("ALLOW_GENKEY")
        st["armed"] = armed()
        try:
            st["fingerprint"] = _fp(self.pubkey()[0])
            st["hasKey"] = True
        except Exception:
            st["hasKey"] = False
        return st


def _trustm_here(i2c, tries=40):
    """A Trust M at 0x30? Asleep it NACKs its address, so i2c.scan() alone can miss it: poll its
    state register a few times (trustm_q.present, without importing the driver)."""
    for _ in range(tries):
        try:
            i2c.writeto(0x30, b"\x82")
            time.sleep_us(100)
            return len(i2c.readfrom(0x30, 4)) == 4
        except OSError:
            time.sleep_ms(1)
    return False


def detect():
    """The secure elements on I2C0: [("atecc608", addr), ("trustm", 0x30)], either, both or none.
    One wake token for a sleeping ATECC, one scan, then a short poll at 0x30."""
    try:
        import atecc
        found = atecc.scan()
        out = [("atecc608", a) for a in atecc.KNOWN_ADDRS if a in found][:1]
        if 0x30 in found or _trustm_here(atecc.make_i2c(atecc.SDA, atecc.SCL, 100_000)):
            out.append(("trustm", 0x30))
        return out
    except Exception as e:
        print("detect:", e)
        return []


def is_chip(sig):
    """A secure element, not the software key or nothing."""
    return sig is not None and sig.name in ("atecc608", "trustm")


def _open(kind, addr):
    if kind == "trustm":
        s = TrustMSigner()
        s.uid()                 # answers, or raises
    else:
        s = ChipSigner(addr)
        s.chip.wake()
        s.chip.sleep()
    return s


class NoSigner:
    """What load(soft=False) returns when no chip answers: it has no key and can sign nothing."""
    name = "none"
    slot = 0

    def pubkey(self, slot=None):
        raise Exception("no chip")

    def sign(self, digest, slot=None):
        raise Exception("no chip")


def load(soft=True, pins=None):
    """The chip on the bus as a signer: an ATECC608 (ChipSigner) or an OPTIGA Trust M
    (TrustMSigner). With both on the bus, the one whose serial is pinned (pins: policy.pins of
    secrets.QUORUM_EXPECT); unpinned, the ATECC first, as before the Trust M. No chip: the software
    key (soft=True), else NoSigner. The production console passes soft=False: SoftSigner's first
    pubkey() writes a key to flash."""
    err = "nothing answers on I2C0"
    found = []
    for kind, addr in detect():
        try:
            found.append(_open(kind, addr))
        except Exception as e:
            err = "%s at 0x%02x: %s" % (kind, addr, e)
    if found:
        if len(found) > 1:
            want = [str(p.get("serial", "")).lower() for p in (pins or [])]
            for s in found:
                try:
                    if s.serial() in want:
                        return s
                except Exception:
                    pass
            print("two chips on the bus, none pinned: using the %s" % found[0].name)
        return found[0]
    if not soft:
        print("no chip (%s)" % err)
        return NoSigner()
    print("no chip (%s), using software key" % err)
    return SoftSigner()
