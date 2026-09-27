# ATECC608 configs by name, and what the provisioning ceremony (provision.py) needs to know about
# them: which one a chip has, the CRC the chip checks when a zone is locked, and the record that
# goes into the OTP zone. Pure: no bus, so tools/check_config and the tests use it too.
#
# "quorum-v1" is PicoQuorum's own config, written for one job: a P-256 key that is one owner of a
# Safe (docs/PROVISIONING.md has the reasoning, byte by byte). In short:
#   slot 0      P-256 private key, made on the chip by GenKey, external Sign only (no internal sign,
#               no ECDH), never written or imported (no PrivWrite), LimitedUse: every signature
#               raises counter 0, which the console shows. Sealed by a slot lock after GenKey.
#   slots 1-15  dead: data, secret (never readable), never writable once the data zone is locked.
#   header      I2C 0x60, CountMatch off (no slot-10 trap), no IO protection, KDF, SecureBoot,
#               UseLock or VolatileKey: nothing the console does not use.
# Bytes 0-15 (serial, revision) and 84-87 (UserExtra, lock bytes) are the chip's own; the Write
# command skips them and the CRC takes them from the chip.
#
# "legacy-test" is Microchip's test table (atecc.CONFIG), which chip #1 runs. "factory" is what an
# Adafruit 4314 breakout answers before anyone writes it (read off a real part, 2026-09-16).
import hashlib
from binascii import hexlify
from atecc import CONFIG as LEGACY, crc16, decode_slot, SLOT_BYTES

QUORUM_V1 = bytes([
    0x01, 0x23, 0x00, 0x00, 0x00, 0x00, 0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEE, 0x00, 0x00, 0x00,
    0xC0, 0x00, 0x00, 0x00, 0xA1, 0x2F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F,
    0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F, 0x9F, 0x8F,
    0x9F, 0x8F, 0x9F, 0x8F, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x55, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x33, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00,
    0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00,
])
# Never edit these bytes by hand: the import refuses a table whose fingerprint or shape changed.
# To change it on purpose, update docs/PROVISIONING.md, this hash and tools/check_config together.
QUORUM_V1_SHA256 = "aadcf1ea51b86a8f71c19823c5eea2adbd683221180496622db2c54b66e8abef"
assert hexlify(hashlib.sha256(QUORUM_V1).digest()).decode() == QUORUM_V1_SHA256, "QUORUM_V1 changed: see tools/check_config"
assert len(QUORUM_V1) == 128
assert QUORUM_V1[88:90] == b"\xff\xff", "SlotLocked must be FF FF at the config lock, or slot 0 can never get a key"
assert QUORUM_V1[18] == 0 and QUORUM_V1[19] == 0, "CountMatch and ChipMode must be 0"
assert QUORUM_V1[68:84] == bytes(16) and QUORUM_V1[90:96] == bytes(6), "UseLock, VolatileKey, SecureBoot, KdfIv, ChipOptions, X509 must be 0"
_s0 = decode_slot(QUORUM_V1, 0)
assert (_s0["kind"], _s0["extSign"], _s0["intSign"], _s0["genKey"], _s0["privWrite"], _s0["pubInfo"], _s0["lockable"],
        _s0["isSecret"], _s0["limitedUse"], _s0["reqAuth"], _s0["locked"]) == \
       ("P256", True, False, True, False, True, True, True, True, False, False), "slot 0 must be the sealed-key row"
assert QUORUM_V1[20] & 0x0E == 0, "slot 0: no internal sign, no ECDH"
for _n in range(1, 16):
    _r = decode_slot(QUORUM_V1, _n)
    assert (_r["kind"], _r["private"], _r["isSecret"], _r["clearWrite"], _r["lockable"]) == ("DATA", False, True, "never", False), \
        "slot %d must be dead" % _n
del _s0, _r, _n

# The Adafruit 4314's factory table, bytes 16-127 (bytes 0-15 are the chip's own).
FACTORY = bytes(16) + bytes([
    0xC0, 0x00, 0x00, 0x00, 0x83, 0x20, 0x87, 0x20, 0x8F, 0x20, 0xC4, 0x8F, 0x8F, 0x8F, 0x8F, 0x8F,
    0x9F, 0x8F, 0xAF, 0x8F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0xAF, 0x8F, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x55, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x33, 0x00, 0x33, 0x00, 0x33, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00, 0x1C, 0x00,
    0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x1C, 0x00,
])
assert len(FACTORY) == 128

PROFILES = (("quorum-v1", QUORUM_V1), ("legacy-test", LEGACY), ("factory", FACTORY))
PROFILE_ID = {"quorum-v1": 1}
REVISIONS = {"00006002": "ATECC608A", "00006003": "ATECC608B"}

# The bytes that say what a chip IS: the slot table and header. Not the counters (52-67, they move),
# not the chip's own bytes (0-15, 84-87) and not SlotLocked (88-89, a slot lock clears a bit).
_SAME = [i for i in range(16, 128) if not (52 <= i < 68 or 84 <= i < 90)]


def identify(cfg):
    """The profile name a chip's 128 config bytes match, else "unknown"."""
    for name, t in PROFILES:
        if all(cfg[i] == t[i] for i in _SAME):
            return name
    return "unknown"


def expected_image(chip_cfg, table=QUORUM_V1):
    """The 128 bytes the config zone must hold at the lock: the table, with the chip's own bytes
    0-15 and 84-85, and the two lock bytes still 0x55. Built from the reviewed table, never from a
    readback: that is what makes the CRC lock refuse a table that is not the reviewed one."""
    if chip_cfg[86] != 0x55 or chip_cfg[87] != 0x55:
        raise ValueError("a zone is already locked")
    return bytes(chip_cfg[0:16]) + table[16:84] + bytes(chip_cfg[84:86]) + b"\x55\x55" + table[88:128]


def summary(data):
    """The Lock command's Param2: the chip's CRC-16 over the bytes, in the order it goes on the wire."""
    c = crc16(data)
    return c[0] | c[1] << 8


def config_summary(chip_cfg, table=QUORUM_V1):
    return summary(expected_image(chip_cfg, table))


def data_image(table, slots, otp):
    """What the data lock's CRC covers: every slot that is not a private key, in order, then the OTP
    zone (datasheet, Lock: "Slots that are configured to contain an ECC private key are never included
    in the summary CRC"). slots: {slot: bytes of its full size}."""
    out = b""
    for n in range(16):
        if decode_slot(table, n)["private"]:
            continue
        b = slots[n]
        if len(b) != SLOT_BYTES[n]:
            raise ValueError("slot %d: %d bytes, not %d" % (n, len(b), SLOT_BYTES[n]))
        out += bytes(b)
    if len(otp) != 64:
        raise ValueError("the OTP zone is 64 bytes")
    return out + bytes(otp)


def data_summary(table, slots, otp):
    return summary(data_image(table, slots, otp))


def zero_slots(table=QUORUM_V1):
    """The contents the ceremony writes into every slot that is not a private key: zeros."""
    return {n: bytes(SLOT_BYTES[n]) for n in range(16) if not decode_slot(table, n)["private"]}


# ----------------------------------------------------------------------------- the OTP record
MAGIC = b"PQ"


def record_encode(serial, slot, qx, qy, owner, date, build, counter, profile="quorum-v1", flags=0):
    """64 bytes for the OTP zone, integers big-endian:
      0 "PQ" | 2 version 1 | 3 profile | 4 serial (9) | 13 key slot | 14 flags (2) |
      16 SHA-256(qx || qy)[:16] | 32 owner address (20) | 52 date (unix, 4) | 56 build (4) |
      60 counter 0 when written (4)
    Advisory: the console always checks the live key, never the record."""
    pub = int(qx).to_bytes(32, "big") + int(qy).to_bytes(32, "big")
    ow = bytes.fromhex(owner[2:] if owner.startswith("0x") else owner)
    b = (build or "")[:8]
    bid = bytes.fromhex(b + "0" * (8 - len(b))) if all(c in "0123456789abcdef" for c in b) else bytes(4)
    r = (MAGIC + bytes([1, PROFILE_ID.get(profile, 0)]) + bytes(serial) + bytes([slot]) + flags.to_bytes(2, "big")
         + hashlib.sha256(pub).digest()[:16] + ow + int(date).to_bytes(4, "big") + bid + int(counter).to_bytes(4, "big"))
    assert len(r) == 64
    return r


def record_decode(b):
    """The OTP zone as a record, or None when it is not one (a factory chip, or chip #1)."""
    b = bytes(b)
    if len(b) != 64 or b[:2] != MAGIC or b[2] != 1:
        return None
    return {"profile": {v: k for k, v in PROFILE_ID.items()}.get(b[3], "?"), "serial": hexlify(b[4:13]).decode(),
            "slot": b[13], "flags": int.from_bytes(b[14:16], "big"), "pubHash": hexlify(b[16:32]).decode(),
            "owner": "0x" + hexlify(b[32:52]).decode(), "date": int.from_bytes(b[52:56], "big"),
            "build": hexlify(b[56:60]).decode(), "counter": int.from_bytes(b[60:64], "big")}


def record_matches(rec, qx, qy):
    """Does the record describe this public key?"""
    pub = int(qx).to_bytes(32, "big") + int(qy).to_bytes(32, "big")
    return rec is not None and rec["pubHash"] == hexlify(hashlib.sha256(pub).digest()[:16]).decode()
