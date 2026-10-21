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

# "quorum-v2" is quorum v1 with one change, for a branded chip (docs/BRANDED-KEYS.md): slot 8 (416
# bytes) is the dead row with IsSecret cleared (SlotConfig 0x8F1F), so it reads in the clear once the
# data zone is locked. It holds the brand signature, written before that lock and never after.
QUORUM_V2 = QUORUM_V1[:36] + b"\x1f\x8f" + QUORUM_V1[38:]
QUORUM_V2_SHA256 = "36da855657a3ee7e098f27cd17b2a636c9e51adec02d252ee0adbe905b8113e1"
assert hexlify(hashlib.sha256(QUORUM_V2).digest()).decode() == QUORUM_V2_SHA256, "QUORUM_V2 changed: see tools/check_config"
assert [i for i in range(128) if QUORUM_V1[i] != QUORUM_V2[i]] == [36], "quorum v2 differs from v1 in slot 8's IsSecret only"
_r = decode_slot(QUORUM_V2, 8)
assert (_r["kind"], _r["private"], _r["isSecret"], _r["clearWrite"], _r["lockable"], _r["encRead"]) == \
       ("DATA", False, False, "never", False, False), "slot 8 must be readable in the clear and never writable"
del _r

# "quorum-v3" is quorum v2 with one more change (docs/ATTESTED-KEYS.md): slot 1 is the attestation
# key, made by GenKey and slot-locked at the bench, before the data lock. SlotConfig 0x2F82: internal
# Sign only (ReadKey 0010): it signs only messages the chip builds from its own state, never a digest a
# host hands it. No ECDH, no PrivWrite, no LimitedUse. KeyConfig 0x0033, slot 0's: PubInfo, Lockable.
QUORUM_V3 = QUORUM_V2[:22] + b"\x82\x2f" + QUORUM_V2[24:98] + b"\x33\x00" + QUORUM_V2[100:]
QUORUM_V3_SHA256 = "5997c7e21d9a746d697a9adadd128ade84a5bef11628c106bd9182d3ca40905e"
assert hexlify(hashlib.sha256(QUORUM_V3).digest()).decode() == QUORUM_V3_SHA256, "QUORUM_V3 changed: see tools/check_config"
assert [i for i in range(128) if QUORUM_V2[i] != QUORUM_V3[i]] == [22, 23, 98], "quorum v3 differs from v2 in slot 1's rows only"
_r = decode_slot(QUORUM_V3, 1)
assert (_r["kind"], _r["extSign"], _r["intSign"], _r["genKey"], _r["privWrite"], _r["pubInfo"], _r["lockable"],
        _r["isSecret"], _r["limitedUse"], _r["reqAuth"], _r["locked"]) == \
       ("P256", False, True, True, False, True, True, True, False, False, False), "slot 1 must be the attestation-key row"
assert QUORUM_V3[22] & 0x0D == 0, "slot 1: no external sign, no ECDH"
assert QUORUM_V3[20:22] == QUORUM_V1[20:22] and QUORUM_V3[96:98] == QUORUM_V1[96:98], "slot 0 stays quorum v1's"
del _r

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

PROFILES = (("quorum-v1", QUORUM_V1), ("quorum-v2", QUORUM_V2), ("quorum-v3", QUORUM_V3), ("legacy-test", LEGACY), ("factory", FACTORY))
PROFILE_ID = {"quorum-v1": 1, "quorum-v2": 2, "quorum-v3": 3}
TABLES = {"quorum-v1": QUORUM_V1, "quorum-v2": QUORUM_V2, "quorum-v3": QUORUM_V3}
REVISIONS = {"00006002": "ATECC608A", "00006003": "ATECC608B", "00006005": "ATECC608C"}

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


def locked_summary(chip_cfg, table):
    """The CRC a chip's config lock was checked against, worked out again after the lock: the
    table with the chip's own bytes, and the lock bytes as they were (55 55)."""
    return summary(bytes(chip_cfg[0:16]) + table[16:84] + bytes(chip_cfg[84:86]) + b"\x55\x55" + table[88:128])


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


# ----------------------------------------------------------------------------- the brand record (v2, v3)
# A branded chip's OTP zone (docs/BRANDED-KEYS.md). No key fields: the bench makes no key. Version 3
# (docs/ATTESTED-KEYS.md) is the same record on a quorum v3 chip; its attestation key's public half is
# in slot 8 at 224-287, and the brand signature covers it.
BRAND_PREFIX = b"PicoQuorum brand v1"       # a version 2 record
BRAND_PREFIX_V3 = b"PicoQuorum brand v2"    # a version 3 record and the attestation key: never verifies as v2
TEST_BENCH = 0xFF       # a spare branded with the public test key (brand.py): never a brand
ATT_AT = 224            # slot 8: the attestation key's qx || qy, 224-287
ATT_SLOT = 1


def brand_encode(serial, revision, config_crc, batch, bench, seq, date, build, key_id, version=3):
    """64 bytes, integers big-endian:
      0 "PQ" | 2 version (2, or 3) | 3 profile (2, or 3: quorum v3) | 4 serial (9) | 13 revision (4) |
      17 config CRC (2) | 19 batch (2) | 21 bench id | 22 sequence on that bench (3) | 25 date (4) |
      29 bench build (4) | 33 brand key id: SHA-256(qx || qy)[:16] | 49 zeros (15)"""
    b = (build or "")[:8]
    bid = bytes.fromhex(b + "0" * (8 - len(b))) if all(c in "0123456789abcdef" for c in b) else bytes(4)
    r = (MAGIC + bytes([version, PROFILE_ID["quorum-v%d" % version]]) + bytes(serial) + bytes(revision) + int(config_crc).to_bytes(2, "big")
         + int(batch).to_bytes(2, "big") + bytes([bench]) + int(seq).to_bytes(3, "big") + int(date).to_bytes(4, "big")
         + bid + bytes(key_id) + bytes(15))
    assert len(r) == 64
    return r


def brand_decode(b):
    """The OTP zone as a brand record, or None when it is not one."""
    b = bytes(b)
    if len(b) != 64 or b[:2] != MAGIC or b[2] not in (2, 3):
        return None
    return {"version": b[2], "profile": {v: k for k, v in PROFILE_ID.items()}.get(b[3], "?"), "serial": hexlify(b[4:13]).decode(),
            "revision": hexlify(b[13:17]).decode(), "configCrc": int.from_bytes(b[17:19], "big"),
            "batch": int.from_bytes(b[19:21], "big"), "bench": b[21], "seq": int.from_bytes(b[22:25], "big"),
            "date": int.from_bytes(b[25:29], "big"), "build": hexlify(b[29:33]).decode(), "keyId": hexlify(b[33:49]).decode(),
            "zeros": b[49:64] == bytes(15)}


def brand_digest(record, att=None):
    """What the brand key signs: SHA-256("PicoQuorum brand v1" || the 64-byte record) for version 2;
    SHA-256("PicoQuorum brand v2" || the record || the attestation key, qx || qy) for version 3."""
    if bytes(record)[2] == 3:
        if att is None or len(att) != 64:
            raise ValueError("a version 3 brand covers the attestation key")
        return hashlib.sha256(BRAND_PREFIX_V3 + bytes(record) + bytes(att)).digest()
    return hashlib.sha256(BRAND_PREFIX + bytes(record)).digest()


def on_curve(pub):
    """Is qx || qy (64 bytes) a point on P-256?"""
    import p256
    x, y = int.from_bytes(pub[:32], "big"), int.from_bytes(pub[32:64], "big")
    return 0 < x < p256.P and 0 < y < p256.P and (y * y - x * x * x - p256.A * x - p256.B) % p256.P == 0


def brand_number(rec):
    """The label's number: 0042 on bench 0, B2-0042 on any other, T0042 on the test bench."""
    if rec["bench"] == TEST_BENCH:
        return "T%04d" % rec["seq"]
    return "%04d" % rec["seq"] if rec["bench"] == 0 else "B%d-%04d" % (rec["bench"], rec["seq"])


def key_id(qx, qy):
    """A brand key's id: SHA-256(qx || qy)[:16]."""
    return hashlib.sha256(int(qx).to_bytes(32, "big") + int(qy).to_bytes(32, "big")).digest()[:16]


def brand_keys():
    """The pinned brand keys, {key id hex: (qx, qy)}, from quorum_cfg's "brandKeys" (key 0000 and
    any later ones). Empty until key 0000 exists: then no chip passes as branded."""
    import quorum_cfg
    return {kid: (int(k["qx"], 16), int(k["qy"], 16)) for kid, k in quorum_cfg.CFG.get("brandKeys", {}).items()}


def brand_check(rec, slot8, serial, revision, cfg, keys, att_live=None):
    """[(check, ok)] for a chip's brand, as a console checks it, with no network. rec: brand_decode
    of the OTP with "_raw" set; keys: {key id hex: (qx, qy)}, the pinned brand keys; att_live: a
    version 3 chip's slot 1 public key as it reads (qx || qy), which must be the one in slot 8.
    Refuses a test bench, a bench certificate, and any bench but 0, rather than guess."""
    import p256
    if rec is None:
        return [("a brand record in OTP", False)]
    v3 = rec["version"] == 3
    table = QUORUM_V3 if v3 else QUORUM_V2
    att = bytes(slot8[ATT_AT:ATT_AT + 64]) if v3 else None
    r = int.from_bytes(slot8[0:32], "big")
    s = int.from_bytes(slot8[32:64], "big")
    k = keys.get(rec["keyId"])
    good = k is not None and s <= p256.N // 2 and p256.verify(k[0], k[1], brand_digest(rec["_raw"], att), r, s)
    out = [("signed by a pinned brand key", good),
           ("serial matches the chip", rec["serial"] == serial),
           ("revision matches", rec["revision"] == revision),
           ("%s, config CRC matches" % ("quorum v3" if v3 else "quorum v2"),
            rec["profile"] == ("quorum-v3" if v3 else "quorum-v2") and rec["configCrc"] == locked_summary(cfg, table)),
           ("locked 00/00", cfg[86] == 0x00 and cfg[87] == 0x00),
           ("bench 0, no certificate", rec["bench"] == 0 and slot8[64:224] == bytes(160))]
    if v3:
        out += [("attestation key in slot 8", on_curve(att)),
                ("slot 1 sealed, its key the one in slot 8", not (cfg[88] >> ATT_SLOT) & 1 and att_live is not None and bytes(att_live) == att),
                ("the rest of slot 8 zeros", slot8[ATT_AT + 64:] == bytes(len(slot8) - ATT_AT - 64))]
    else:
        out.append(("the rest of slot 8 zeros", slot8[224:] == bytes(len(slot8) - 224)))
    return out


# ----------------------------------------------------------------------------- the attestation (v3)
# docs/ATTESTED-KEYS.md, U4a: the chip attests slot 0's key with slot 1, and anyone can check it from
# public bytes. Three commands with no sleep between (TempKey dies with a sleep), none changing a key:
#   Nonce    the challenge into TempKey: passed through (32 bytes), or random mode (RandOut, NumIn)
#   GenKey   digest mode (0x08) on slot 0: the public key worked out again, no new key; TempKey becomes
#            SHA-256(TempKey | 40 08 slot(2) | SN[8] SN[0:2] | 25 zeros | qx qy)
#   Sign     internal (0x40: the full serial in the message) with slot 1, over SHA-256 of the 55 bytes
#            internal_message builds: TempKey, the Sign command, slot 0's SlotConfig and KeyConfig,
#            TempKey's flags (GenKey made it, from slot 0), the serial, and slot 0's SlotLocked bit.
# The layout is the datasheet's as remembered (cryptoauthlib's atcah_gen_key_msg and
# atcah_sign_internal_msg). A real chip's signature settles it: tools/check_attest searches the
# nearby layouts when the strict one fails, and says which one the chip used.
GENKEY_DIGEST = 0x08
SIGN_INTERNAL_SN = 0x40
NONCE_PASS, NONCE_RANDOM = 0x03, 0x00


def nonce_tempkey(nonce):
    """TempKey after the Nonce: {"mode": "input", "value": 32 bytes} passed through, or
    {"mode": "random", "randOut": 32, "numIn": 20}. -> (TempKey, its SourceFlag: 1 input, 0 random)."""
    if nonce["mode"] == "input":
        return bytes(nonce["value"]), 1
    return hashlib.sha256(bytes(nonce["randOut"]) + bytes(nonce["numIn"]) + bytes([0x16, NONCE_RANDOM, 0x00])).digest(), 0


def genkey_tempkey(tempkey, slot, sn, pub):
    """TempKey after GenKey's digest mode on `slot`. sn: the 9-byte serial; pub: qx || qy."""
    msg = bytes(tempkey) + bytes([0x40, GENKEY_DIGEST, slot & 0xFF, slot >> 8, sn[8], sn[0], sn[1]]) + bytes(25) + bytes(pub)
    assert len(msg) == 128
    return hashlib.sha256(msg).digest()


def internal_message(tempkey, sn, flags, sealed, table=None, key_slot=0, att_slot=ATT_SLOT, last=0x01):
    """The 55 bytes an internal Sign with SIGN_INTERNAL_SN signs the SHA-256 of. flags: TempKey's
    (keyId 0-3, SourceFlag 4, GenDigData 5, GenKeyData 6, NoMacFlag 7); sealed: SlotLocked of keyId."""
    t = QUORUM_V3 if table is None else table
    msg = (bytes(tempkey) + bytes([0x41, SIGN_INTERNAL_SN, att_slot & 0xFF, att_slot >> 8]) + bytes(t[20 + 2 * key_slot:22 + 2 * key_slot])
           + bytes(t[96 + 2 * key_slot:98 + 2 * key_slot]) + bytes([flags, 0, 0, sn[8]]) + bytes(sn[4:8]) + bytes(sn[0:2])
           + bytes(sn[2:4]) + bytes([0x00 if sealed else 0x01, last, 0x00]))
    assert len(msg) == 55
    return msg


def attest_digest(bundle, sealed=True):
    """What slot 1 signed, rebuilt from the bundle's public bytes alone, for a sealed slot 0 made by
    GenKey (GenKeyData 1, keyId 0, NoMac 0)."""
    sn = bytes.fromhex(bundle["serial"])
    tk, source = nonce_tempkey(bundle["nonce"])
    tk = genkey_tempkey(tk, 0, sn, bundle["pub"])
    return hashlib.sha256(internal_message(tk, sn, 0x40 | source << 4, sealed)).digest()


def attest_check(bundle, keys):
    """[(check, ok)] for an attestation bundle (docs/ATTESTED-KEYS.md): serial, otp (64), slot8
    (0-287), pub (slot 0's qx || qy), nonce (nonce_tempkey's), sig (64, slot 1's). keys: {key id hex:
    (qx, qy)}, the brand keys to take (the test key on a spare). The chain key -> brand -> attestation
    key -> slot 0's key; the owner address is the signer factory's from there."""
    import p256
    rec = brand_decode(bundle["otp"])
    slot8 = bytes(bundle["slot8"])
    att = slot8[ATT_AT:ATT_AT + 64]
    v3 = rec is not None and rec["version"] == 3 and rec["profile"] == "quorum-v3"
    k = keys.get(rec["keyId"]) if rec else None
    r, s = int.from_bytes(slot8[0:32], "big"), int.from_bytes(slot8[32:64], "big")
    branded = v3 and k is not None and p256.verify(k[0], k[1], brand_digest(bundle["otp"], att), r, s)
    ar, as_ = int.from_bytes(bundle["sig"][:32], "big"), int.from_bytes(bundle["sig"][32:], "big")
    ax, ay = int.from_bytes(att[:32], "big"), int.from_bytes(att[32:], "big")
    attested = v3 and on_curve(att) and p256.verify(ax, ay, attest_digest(bundle), ar, as_)
    return [("a v3 brand record, quorum v3", v3), ("the serial is the record's", v3 and rec["serial"] == bundle["serial"]),
            ("the brand signs the attestation key", branded), ("slot 0's key attested, sealed, by slot 1", attested)]
