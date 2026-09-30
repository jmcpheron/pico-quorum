# A virtual ATECC608 on the emulator's I2C bus at 0x60. Speaks the chip's packet protocol
# (wake token, 0x03 command packets with CRC-16, count+payload+CRC responses) so firmware/atecc.py
# runs here unchanged. Models what a wallet touches: the config zone and its locks, the slot table
# (SlotConfig / KeyConfig), GenKey, Nonce pass-through + Sign, Random, Info, per-slot locks.
# Also answered: Info KeyValid/State, SelfTest (all pass), SHA-256, Counter reads, clear data
# and OTP writes (32 or 4 bytes; any slot but a private key before the data lock, only WriteConfig
# Always after it), reads of the OTP and data zones only once the DATA zone is locked, and the
# CRC-checked locks: the config zone's summary is the CRC of its 128 bytes, the data zone's of every
# slot that is not a private key followed by the OTP zone; a slot lock ignores it. LimitedUse stops
# a slot at counter 0's cap. Not modeled: MAC/encrypted anything, the watchdog.
#
# A fresh emulator answers like a real fresh part: the factory config of an Adafruit 4314 breakout
# (docs/UPSTREAM.md section 3: slots 0-2 already typed P-256, GenKey allowed), config zone unlocked, and
# Random returning the datasheet's fixed pattern until the lock. The state persists across reboots
# through the host (server: emu/chip.json). wipe() / provision() reset it.
import json
import _emu

ADDR = 0x60
WAKE = b"\x04\x11\x33\x43"
STATUS_OK, STATUS_PARSE, STATUS_EXEC, STATUS_CRC = 0x00, 0x03, 0x0F, 0xFF
OP_READ, OP_NONCE, OP_GENKEY, OP_SIGN, OP_RANDOM, OP_INFO, OP_WRITE, OP_LOCK = 0x02, 0x16, 0x40, 0x41, 0x1B, 0x30, 0x12, 0x17
OP_COUNTER, OP_SHA, OP_SELFTEST = 0x24, 0x47, 0x77
SLOT_BYTES = (36,) * 8 + (416,) + (72,) * 7

# what a fresh part answers: the serial (bytes 0-3, 8-12) and revision 00006002 (608A) of the
# virtual chip, then byte for byte the factory table read off a real Adafruit breakout on
# 2026-09-16: I2C address 0xC0, SlotConfig 2083 2087 208f for slots 0-2, lock bytes 86/87 = 0x55,
# SlotLocked = 0xFFFF, KeyConfig 0033 for slots 0-2 (P-256 private, GenKey allowed).
FRESH = bytearray(bytes([
    0x01, 0x23, 0xE1, 0x00, 0x00, 0x00, 0x60, 0x02, 0xE1, 0xE1, 0xE1, 0xE1, 0xEE, 0xC1, 0x55, 0x00,
    0xC0, 0x00, 0x00, 0x00, 0x83, 0x20, 0x87, 0x20, 0x8F, 0x20, 0xC4, 0x8F, 0x8F, 0x8F, 0x8F, 0x8F,
    0x9F, 0x8F, 0xAF, 0x8F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0xAF, 0x8F, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x55, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x33, 0x00, 0x33, 0x00, 0x33, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00,
    0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x1C, 0x00,
]))
FIXED_RANDOM = bytes([0xFF, 0xFF, 0x00, 0x00]) * 8     # what an unlocked chip answers to Random
COUNTER_MAX = 2097151       # counter 0's cap; a LimitedUse slot signs no more once it is there


def crc16(data):
    crc = 0
    for b in data:
        for shift in range(8):
            data_bit = (b >> shift) & 1
            crc_bit = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if data_bit != crc_bit:
                crc ^= 0x8005
    return bytes([crc & 0xFF, crc >> 8])


class Chip:
    def __init__(self):
        self.cfg = bytearray(FRESH)
        self.keys = {}          # slot -> private scalar
        self.counters = [0, 0]
        self.otp = bytearray(b"\xff" * 64)   # "All OTP bits have a value of one upon shipment"
        self.data = {}          # slot -> bytearray, on first use (factory contents: all ones here)
        self.sha = None
        self.awake = False
        self.tempkey = None
        self.resp = b""
        self.load()

    # --- persistence through the host ----------------------------------------------------
    def load(self):
        try:
            raw = _emu.chip_load()
        except Exception:
            raw = None
        if not raw:
            return
        try:
            st = json.loads(raw)
            if "config" not in st:
                return          # only the Trust M's state (or the bus) is stored so far
            self.cfg = bytearray(bytes.fromhex(st["config"]))
            self.keys = {int(k): int(v, 16) for k, v in st.get("keys", {}).items()}
            self.counters = list(st.get("counters", [0, 0]))
            self.data = {int(k): bytearray(bytes.fromhex(v)) for k, v in st.get("data", {}).items()}
            if "otp" in st:
                self.otp = bytearray(bytes.fromhex(st["otp"]))
        except Exception as e:
            print("atecc_sim: bad saved state (%s), starting blank" % e)

    def save(self):
        st = {"config": "".join("%02x" % b for b in self.cfg), "keys": {str(k): "%064x" % v for k, v in self.keys.items()},
              "counters": self.counters, "data": {str(k): "".join("%02x" % b for b in v) for k, v in self.data.items()},
              "otp": "".join("%02x" % b for b in self.otp)}
        try:
            old = json.loads(_emu.chip_load() or "{}")     # keep what else is stored (the Trust M's)
        except Exception:
            old = {}
        old.update(st)
        try:
            _emu.chip_save(json.dumps(old))
        except Exception as e:
            print("atecc_sim: could not save state: %s" % e)

    # --- config zone helpers ---------------------------------------------------------------
    def config_locked(self):
        return self.cfg[87] == 0x00

    def data_locked(self):
        return self.cfg[86] == 0x00

    def slot_cfg(self, slot):
        return self.cfg[20 + 2 * slot] | self.cfg[21 + 2 * slot] << 8

    def key_cfg(self, slot):
        return self.cfg[96 + 2 * slot] | self.cfg[97 + 2 * slot] << 8

    def slot_locked(self, slot):
        return not (self.cfg[88 + (slot >> 3)] >> (slot & 7)) & 1

    def is_p256_private(self, slot):
        kc = self.key_cfg(slot)
        return bool(kc & 1) and (kc >> 2) & 7 == 4

    def slot_data(self, slot):
        return self.data.setdefault(slot, bytearray(b"\xff" * SLOT_BYTES[slot]))

    def data_summary_bytes(self):
        out = b""
        for n in range(16):
            if self.key_cfg(n) & 1:
                continue            # private keys are never part of the data zone's CRC
            out += bytes(self.slot_data(n))
        return out + bytes(self.otp)

    # --- bus ---------------------------------------------------------------------------------
    def write(self, buf):
        """One I2C write to 0x60. Word address byte first: 0x01 sleep, 0x02 idle, 0x03 command."""
        if not self.awake:
            raise OSError(5, "EIO: chip is asleep")
        wa = buf[0]
        if wa == 0x01 or wa == 0x02:
            self.awake = False
            self.tempkey = None
            self.resp = b""
            return
        if wa != 0x03:
            raise OSError(5, "EIO: unknown word address 0x%02x" % wa)
        pkt = bytes(buf[1:])
        if len(pkt) < 7 or pkt[0] != len(pkt) or crc16(pkt[:-2]) != pkt[-2:]:
            self.resp = self._status(STATUS_CRC)
            return
        opcode, p1, p2 = pkt[1], pkt[2], pkt[3] | pkt[4] << 8
        data = pkt[5:-2]
        try:
            out = self.execute(opcode, p1, p2, data)
        except _Fail as f:
            out = self._status(f.code)
        self.resp = out

    def read(self, n):
        if not self.awake:
            raise OSError(5, "EIO: chip is asleep")
        if not self.resp:
            raise OSError(5, "EIO: busy")   # the driver retries until the wait time has passed
        out = self.resp[:n]
        return out + bytes(n - len(out))

    def wake_token(self):
        self.awake = True
        self.tempkey = None
        self.resp = WAKE

    def _status(self, code):
        body = bytes([4, code])
        return body + crc16(body)

    def _data(self, payload):
        body = bytes([len(payload) + 3]) + payload
        return body + crc16(body)

    # --- commands ----------------------------------------------------------------------------
    def execute(self, opcode, p1, p2, data):
        if opcode == OP_INFO:
            mode = p1 & 0x0F
            if mode == 0:
                return self._data(bytes(self.cfg[4:8]))
            if mode == 1:       # KeyValid: byte 0 is 1 when the slot holds a usable key
                return self._data(bytes([1 if (p2 & 0xF) in self.keys and self.config_locked() else 0, 0, 0, 0]))
            if mode == 2:       # State: bit 7 of byte 0 = TempKey valid (the rest is not modeled)
                return self._data(bytes([0x80 if self.tempkey else 0x00, 0, 0, 0]))
            if mode == 3:       # GPIO
                return self._data(bytes(4))
            raise _Fail(STATUS_PARSE)
        if opcode == OP_RANDOM:
            if not self.config_locked():
                return self._data(FIXED_RANDOM)    # datasheet: a fixed pattern until the config lock
            return self._data(bytes(_emu.random(32)))
        if opcode == OP_SELFTEST:
            return self._data(b"\x00")             # every test passes
        if opcode == OP_SHA:
            return self.sha_cmd(p1 & 0x07, p2, data)
        if opcode == OP_COUNTER:
            if p2 > 1:
                raise _Fail(STATUS_PARSE)
            if p1 & 1:
                self.counters[p2] += 1
                self.save()
            return self._data(self.counters[p2].to_bytes(4, "little"))
        if opcode == OP_READ:
            zone = p1 & 3
            if zone == 3:
                raise _Fail(STATUS_PARSE)
            if zone != 0 and not self.data_locked():
                raise _Fail(STATUS_EXEC)      # data and OTP cannot be read until the DATA zone is locked (seen on silicon)
            if zone == 1:
                block = p2 >> 3
                if block > 1 or not p1 & 0x80:
                    raise _Fail(STATUS_PARSE)
                return self._data(bytes(self.otp[block * 32:block * 32 + 32]))
            if zone == 2:
                slot, block = (p2 >> 3) & 0xF, p2 >> 8
                if block * 32 + 32 > SLOT_BYTES[slot] or not p1 & 0x80:
                    raise _Fail(STATUS_PARSE)
                if self.slot_cfg(slot) & 0x80:
                    raise _Fail(STATUS_EXEC)  # IsSecret: never readable in clear
                buf = self.slot_data(slot)
                return self._data(bytes(buf[block * 32:block * 32 + 32]))
            if p1 & 0x80:
                block = p2 >> 3
                if block > 3:
                    raise _Fail(STATUS_PARSE)
                return self._data(bytes(self.cfg[block * 32:block * 32 + 32]))
            if p2 > 31:
                raise _Fail(STATUS_PARSE)
            return self._data(bytes(self.cfg[p2 * 4:p2 * 4 + 4]))
        if opcode == OP_WRITE:
            n = 32 if p1 & 0x80 else 4
            if p1 & 3 in (1, 2) and len(data) != n:
                raise _Fail(STATUS_PARSE)
            if p1 & 3 == 2:
                # a data slot in clear, 32 bytes at a block or 4 at a word, only after the config lock.
                # Before the data lock any slot but a private key (those take PrivWrite); after it,
                # only where WriteConfig says Always, and never a locked slot.
                slot, block, word = (p2 >> 3) & 0xF, p2 >> 8, p2 & 7 if n == 4 else 0
                off = block * 32 + word * 4
                if off >= SLOT_BYTES[slot] or (n == 4 and off + n > SLOT_BYTES[slot]):
                    raise _Fail(STATUS_PARSE)
                if not self.config_locked() or self.key_cfg(slot) & 1 or self.slot_locked(slot):
                    raise _Fail(STATUS_EXEC)
                if self.data_locked() and self.slot_cfg(slot) >> 12:
                    raise _Fail(STATUS_EXEC)
                if n == 4 and not self.data_locked() and self.slot_cfg(slot) >> 12:
                    raise _Fail(STATUS_EXEC)      # seen on silicon: no 4-byte writes into these slots before the data lock
                n = min(n, SLOT_BYTES[slot] - off)  # a 32-byte write at the last, partial block keeps what fits
                self.slot_data(slot)[off:off + n] = data[:n]
                self.save()
                return self._status(STATUS_OK)
            if p1 & 3 == 1:
                # the OTP zone: writable in clear only while the data zone is open
                block, word = (p2 >> 3) & 1, p2 & 7 if n == 4 else 0
                if not self.config_locked() or self.data_locked():
                    raise _Fail(STATUS_EXEC)
                self.otp[block * 32 + word * 4:block * 32 + word * 4 + n] = data
                self.save()
                return self._status(STATUS_OK)
            if p1 & 3 != 0 or p1 & 0x80 or len(data) != 4:
                raise _Fail(STATUS_PARSE)
            if self.config_locked() or p2 < 4 or p2 == 21 or p2 > 31:
                raise _Fail(STATUS_EXEC)     # locked zone, or the read-only words
            self.cfg[p2 * 4:p2 * 4 + 4] = data
            self.save()
            return self._status(STATUS_OK)
        if opcode == OP_LOCK:
            return self.lock(p1, p2)
        if opcode == OP_GENKEY:
            return self.genkey(p1, p2)
        if opcode == OP_NONCE:
            if p1 & 3 != 3 or len(data) != 32:
                raise _Fail(STATUS_PARSE)     # only pass-through mode is modeled
            self.tempkey = bytes(data)
            return self._status(STATUS_OK)
        if opcode == OP_SIGN:
            return self.sign(p1, p2)
        raise _Fail(STATUS_PARSE)

    def sha_cmd(self, mode, length, data):
        try:
            import hashlib
        except ImportError:
            raise _Fail(STATUS_PARSE)
        if mode == 0:
            self.sha = hashlib.sha256()
            return self._status(STATUS_OK)
        if self.sha is None:
            raise _Fail(STATUS_EXEC)
        if mode == 1:
            if len(data) != 64:
                raise _Fail(STATUS_PARSE)
            self.sha.update(data)
            return self._status(STATUS_OK)
        if mode == 2:
            if len(data) != length or length > 63:
                raise _Fail(STATUS_PARSE)
            self.sha.update(data)
            out, self.sha = self.sha.digest(), None
            return self._data(out)
        raise _Fail(STATUS_PARSE)

    def _crc_ok(self, mode, summary, data):
        """Bit 7 of the mode: ignore the summary. Otherwise the zone must match it exactly."""
        if mode & 0x80:
            return True
        c = crc16(data)
        return summary == (c[0] | c[1] << 8)

    def lock(self, mode, summary=0):
        what = mode & 3
        if what == 0:
            if self.config_locked():
                raise _Fail(STATUS_EXEC)
            if not self._crc_ok(mode, summary, bytes(self.cfg)):
                raise _Fail(STATUS_EXEC)      # the zone is not what the summary says: nothing is locked
            self.cfg[87] = 0x00
        elif what == 1:
            if not self.config_locked() or self.data_locked():
                raise _Fail(STATUS_EXEC)
            if not self._crc_ok(mode, summary, self.data_summary_bytes()):
                raise _Fail(STATUS_EXEC)
            self.cfg[86] = 0x00
        elif what == 2:
            slot = (mode >> 2) & 0xF
            if not self.config_locked() or not self.key_cfg(slot) & 0x20 or self.slot_locked(slot):
                raise _Fail(STATUS_EXEC)      # KeyConfig.Lockable clear, or already locked
            self.cfg[88 + (slot >> 3)] &= ~(1 << (slot & 7)) & 0xFF
        else:
            raise _Fail(STATUS_PARSE)
        self.save()
        return self._status(STATUS_OK)

    def genkey(self, mode, slot):
        import p256
        if slot > 15:
            raise _Fail(STATUS_PARSE)
        if not self.config_locked() or not self.is_p256_private(slot):
            raise _Fail(STATUS_EXEC)          # a blank chip, or the slot is not a private key
        if mode & 0x04:
            # create: SlotConfig.WriteConfig bit 13 (GenKey allowed) and the slot not locked
            if not self.slot_cfg(slot) >> 13 & 1 or self.slot_locked(slot):
                raise _Fail(STATUS_EXEC)
            self.keys[slot] = p256.rand_scalar()
            self.save()
        elif mode & 0x0F:
            raise _Fail(STATUS_PARSE)
        else:
            # public key of the stored key: needs a key and KeyConfig.PubInfo
            if slot not in self.keys or not self.key_cfg(slot) & 2:
                raise _Fail(STATUS_EXEC)
            if self.data_locked() and self.slot_cfg(slot) & 0x20:
                # seen on silicon (chip 2, quorum v1): once the data zone is locked, a public-key
                # read counts as a use of a LimitedUse key; chip 1 (data zone open) never counted it
                if self.counters[0] >= COUNTER_MAX:
                    raise _Fail(STATUS_EXEC)
                self.counters[0] += 1
                self.save()
        x, y = p256.pubkey(self.keys[slot])
        return self._data(x.to_bytes(32, "big") + y.to_bytes(32, "big"))

    def sign(self, mode, slot):
        import p256
        if not mode & 0x80:
            raise _Fail(STATUS_PARSE)         # only external (TempKey) signing is modeled
        if slot > 15 or self.tempkey is None:
            raise _Fail(STATUS_EXEC)
        if not self.config_locked() or not self.is_p256_private(slot) or slot not in self.keys:
            raise _Fail(STATUS_EXEC)
        if not self.slot_cfg(slot) & 1 or not self.slot_cfg(slot) & 0x80:
            raise _Fail(STATUS_EXEC)          # ReadKey bit 0: external signatures not permitted; IsSecret required
        digest, self.tempkey = self.tempkey, None
        if self.slot_cfg(slot) & 0x20:          # LimitedUse: every signature spends one on counter 0, first
            if self.counters[0] >= COUNTER_MAX:
                raise _Fail(STATUS_EXEC)
            self.counters[0] += 1
            self.save()
        r, s = p256.sign(self.keys[slot], digest)
        return self._data(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


class _Fail(Exception):
    def __init__(self, code):
        self.code = code


def _on_bus():
    try:
        return json.loads(_emu.chip_load() or "{}").get("bus", {}).get("atecc608", True)
    except Exception:
        return True


_chip = None
present = _on_bus()     # False: nothing answers at 0x60, as with the chip unplugged (tests, tools/emu chip trustm)


def chip():
    global _chip
    if _chip is None:
        _chip = Chip()
    return _chip


# --- knobs for tools/emu chip ... and sketches -------------------------------------------
def wipe(revision="608a"):
    """Back to a fresh part: the factory table, config unlocked, no keys, factory data and OTP.
    revision "608b" answers Info with 00006003 (and has it at config bytes 4-7), as a 608B does."""
    c = chip()
    c.cfg = bytearray(FRESH)
    c.cfg[7] = 0x03 if revision == "608b" else 0x02
    c.keys = {}
    c.counters = [0, 0]
    c.data = {}
    c.otp = bytearray(b"\xff" * 64)
    c.save()
    return "chip wiped: fresh %s, config zone unlocked" % revision.upper()


def provision(slot=0):
    """A chip as the wallet ships it: reference config written and locked, a fresh key in `slot`."""
    import p256
    from atecc import CONFIG
    c = chip()
    cfg = bytearray(CONFIG)
    cfg[0:16] = FRESH[0:16]
    cfg[84:88] = bytes([0x00, 0x00, 0x00, 0x00])   # data zone stays unlocked, config locked
    cfg[86] = 0x55
    c.cfg = cfg
    c.keys = {slot: p256.rand_scalar()}
    c.save()
    return "chip provisioned: config locked, key in slot %d" % slot


def provision_v1(slot=0):
    """A chip after the whole quorum v1 ceremony (docs/PROVISIONING.md): the table locked, a key in
    slot 0 and the slot locked, slots 1-15 zeroed, the data zone locked. No OTP record."""
    import p256
    from chipcfg import QUORUM_V1
    c = chip()
    cfg = bytearray(QUORUM_V1)
    cfg[0:16] = c.cfg[0:16]
    cfg[84:88] = bytes([0x00, 0x00, 0x00, 0x00])
    cfg[88] = 0xFE
    c.cfg = cfg
    c.keys = {slot: p256.rand_scalar()}
    c.counters = [0, 0]
    c.data = {n: bytearray(SLOT_BYTES[n]) for n in range(1, 16)}
    c.otp = bytearray(64)
    c.save()
    return "chip provisioned as quorum v1: sealed key in slot 0, data zone locked"


def state():
    c = chip()
    return {"configLocked": c.config_locked(), "dataLocked": c.data_locked(), "keys": sorted(c.keys),
            "slotLocked": [n for n in range(16) if c.slot_locked(n)]}
