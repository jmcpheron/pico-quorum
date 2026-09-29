# OPTIGA Trust M profiles, and what the console and the Trust M ceremony (provision_tm.py) need to
# know about them: the chip's metadata decoded, its factory certificate checked, the record that
# goes into a data object, the key-binding statement, and the lines the screens show. Pure: no
# bus, so the tests and the host tools use it too. The chipcfg.py of the Trust M.
#
# "quorum-tm1" is PicoQuorum's Trust M profile (docs/TRUSTM.md):
#   E0F1   P-256 private key, made on the chip by GenKeyPair (key usage Sign), Execute ALW (no use
#          limit, no PIN: the Safe's threshold and rotation cover theft, as on quorum v1).
#   F1D0   the record: serial, key OID, the public key (a Trust M never hands a private-key OID's
#          public key back), owner address, date, build.
#   F1D1   the binding: the factory key E0F0, whose Infineon certificate is in E0E0, signs
#          "this UID holds this E0F1 key". Anyone with the certificate can check it.
#   seal   LcsO of E0F1, F1D0 and F1D1 raised to operational. Their factory Change condition is
#          "LcsO < operational", so from then on nothing can regenerate the key or rewrite either
#          object, and a lifecycle state never goes down.
#
# Read off a real Adafruit 4351 on 2026-09-28 (chips/trustm-*-probe.txt): LcsA operational,
# E0F1-E0F3 empty with Change "LcsO < op", F1D0-F1DB 140 bytes each with the same Change, E0F0 the
# factory key (Change NEV, Execute ALW, key usage Auth), its certificate from "Infineon OPTIGA(TM)
# Trust M CA 101".
import hashlib
from binascii import hexlify

KEY = 0xE0F1            # the Safe key
FACTORY_KEY = 0xE0F0    # Infineon's, certified in E0E0
CERT = 0xE0E0
RECORD = 0xF1D0
BINDING = 0xF1D1
UID = 0xE0C2
LCSA = 0xE0C0
SEC = 0xE0C5            # the security event counter: rises on suspect events, the chip slows down
SEALED = (KEY, RECORD, BINDING)

_LCS_SHORT = {0x01: "cre", 0x03: "init", 0x07: "op", 0x0F: "term"}
LCS = {0x01: "creation", 0x03: "initialization", 0x07: "operational", 0x0F: "termination"}
OPERATIONAL = 0x07
ALGO = {0x03: "P256", 0x04: "P384", 0x01: "RSA1024", 0x02: "RSA2048"}
USAGE_AUTH, USAGE_ENC, USAGE_SIGN, USAGE_KEYAGREE = 0x01, 0x02, 0x10, 0x20

# Access-condition bytes (Solution Reference Manual, "Access Conditions")
_AC = {0x00: "ALW", 0xFF: "NEV", 0x20: "Conf", 0x21: "Int", 0x23: "Auto", 0x40: "Luc", 0x70: "LcsG",
       0xE0: "LcsA", 0xE1: "LcsO", 0xFA: "==", 0xFB: ">", 0xFC: "<", 0xFD: "&&", 0xFE: "||"}

# The Infineon CA keys a factory certificate may chain to, by the issuer's common name. From
# TrustMAttest's test (a real chip's certificate, 2026-09-17), and matched by this board's chip.
CAS = {
    "Infineon OPTIGA(TM) Trust M CA 101": (
        0x97337734AD7423A14BF40FD4EE1D27AF8ED05AE87970C74DFE29889B499AD2D0,
        0x1EA249AE7910F052C59D85514A8215E2D63E4730CDFB5CC153BBCC00A7E6408B),
}
# The emulator's virtual Trust M (emu/core/shims/trustm_sim.py) signs its certificate with a test
# CA. Accepted only off the Pico: on rp2 this name means nothing.
EMU_CA = "PicoQuorum emulator CA (not Infineon)"


def _emu_ca():
    import sys
    if sys.platform == "rp2":
        return None
    try:
        import trustm_sim
        return trustm_sim._ca_pub()
    except ImportError:
        return None


# ----------------------------------------------------------------------------- the UID
def uid_fields(uid):
    """The 27-byte coprocessor UID (datasheet: CIM, platform, model, ROM mask, chip type, batch,
    wafer X, wafer Y, firmware id, ESW build)."""
    u = bytes(uid)
    if len(u) != 27:
        raise ValueError("a Trust M UID is 27 bytes, not %d" % len(u))
    return {"cim": u[0], "platform": u[1], "model": u[2], "rom": u[3:5], "type": u[5:11], "batch": u[11:17],
            "x": int.from_bytes(u[17:19], "big"), "y": int.from_bytes(u[19:21], "big"),
            "fw": hexlify(u[21:25]).decode(), "build": hexlify(u[25:27]).decode()}


def serial(uid):
    """This chip among all others: batch number and wafer X/Y (UID bytes 11-20), 20 hex chars. The
    UID's tail is the firmware id and build, the same for the whole batch, so screens showing the
    last 8 characters show the wafer position."""
    return hexlify(bytes(uid)[11:21]).decode()


# ----------------------------------------------------------------------------- metadata
def parse_meta(b):
    """A metadata TLV (0x20 len, then tag len value) as a dict. Access conditions stay bytes;
    ac_text() says them."""
    b = bytes(b)
    if not b or b[0] != 0x20:
        raise ValueError("not metadata: %s" % hexlify(b).decode())
    out = {"lcso": None, "change": None, "read": None, "exec": None, "algo": None, "usage": None,
           "max": None, "used": None, "type": None}
    names = {0xC0: "lcso", 0xD0: "change", 0xD1: "read", 0xD3: "exec", 0xE0: "algo", 0xE1: "usage", 0xC4: "max",
             0xC5: "used", 0xE8: "type"}
    i, end = 2, 2 + b[1]
    while i < end:
        tag, n = b[i], b[i + 1]
        v = b[i + 2:i + 2 + n]
        k = names.get(tag)
        if k in ("lcso", "algo", "usage", "type"):
            out[k] = v[0] if n == 1 else v
        elif k in ("max", "used"):
            out[k] = int.from_bytes(v, "big")
        elif k:
            out[k] = v
        i += 2 + n
    return out


def meta_tlv(lcso=None):
    """The metadata a SetDataObject(metadata) writes: only what changes. Here, only LcsO."""
    body = b""
    if lcso is not None:
        body += bytes([0xC0, 1, lcso])
    return bytes([0x20, len(body)]) + body


def ac_text(ac):
    """An access condition in words: "ALW", "NEV", "LcsO<op", "Luc(E120)"."""
    if ac is None:
        return "-"
    ac = bytes(ac)
    out = []
    i = 0
    while i < len(ac):
        x = ac[i]
        if x in (0xE0, 0xE1, 0x70) and i + 2 < len(ac) and ac[i + 1] in (0xFA, 0xFB, 0xFC):
            out.append(_AC[x] + _AC[ac[i + 1]] + _LCS_SHORT.get(ac[i + 2], "%02x" % ac[i + 2]))
            i += 3
        elif x in (0x20, 0x21, 0x23, 0x40) and i + 2 < len(ac):
            out.append("%s(%02X%02X)" % (_AC[x], ac[i + 1], ac[i + 2]))
            i += 3
        else:
            out.append(_AC.get(x, "%02x" % x))
            i += 1
    return " ".join(out)


def lcs_name(v):
    return LCS.get(v, "?") if v is not None else "-"


def key_row(meta):
    """The Safe key's metadata in the shape atecc.decode_slot gives the console, so
    policy.expect_check reads a Trust M key the same way. locked: LcsO operational while Change
    needs LcsO below it (or never), so the key can never be made again."""
    ch = bytes(meta.get("change") or b"")
    frozen = meta.get("lcso") == OPERATIONAL and ch in (b"\xff", b"\xe1\xfc\x07")
    usage = meta.get("usage") or 0
    return {"slot": KEY, "kind": ALGO.get(meta.get("algo"), "?" if meta.get("algo") else "EMPTY"),
            "extSign": bool(usage & USAGE_SIGN) if isinstance(usage, int) else False, "locked": frozen,
            "limitedUse": False, "hasKey": meta.get("algo") is not None, "lcso": meta.get("lcso"),
            "change": ac_text(meta.get("change")), "exec": ac_text(meta.get("exec"))}


def identify(key_meta, record):
    """factory: E0F1 never made and no record. quorum-tm1: E0F1 sealed and our record in F1D0.
    quorum-tm1-open: on the way (a key or a record, nothing sealed). unknown: sealed by someone else."""
    sealed = key_meta.get("lcso") == OPERATIONAL
    if sealed:
        return "quorum-tm1" if record else "unknown"
    if key_meta.get("algo") is None and not record:
        return "factory"
    return "quorum-tm1-open"


# ----------------------------------------------------------------------------- the certificate
SPKI_P256 = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d03010703420004")


def _tlv(b, i):
    """(tag, value start, value end) of the DER element at i."""
    tag, n = b[i], b[i + 1]
    i += 2
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(b[i:i + k], "big")
        i += k
    return tag, i, i + n


def cert_der(e0e0):
    """The X.509 certificate out of E0E0. Infineon stores it in a TLS-style wrapper: C0, a 2-byte
    length, the chain's 3-byte length, the certificate's 3-byte length, then the DER."""
    b = bytes(e0e0)
    if b[:1] == b"\xc0":
        n = int.from_bytes(b[6:9], "big")
        return b[9:9 + n]
    if b[:1] == b"\x30":
        return b
    raise ValueError("E0E0 holds no certificate")


def _cn(tbs, start):
    """The next common name (OID 2.5.4.3) at or after start: (name, end)."""
    i = tbs.find(b"\x06\x03\x55\x04\x03", start)
    if i < 0:
        return None, start
    _, s, e = _tlv(tbs, i + 5)
    return tbs[s:e].decode(), e


def cert_parse(der):
    """{tbs, r, s, qx, qy, serial, issuer, subject} of a P-256 certificate signed with ECDSA-SHA256."""
    der = bytes(der)
    _, s0, _ = _tlv(der, 0)
    _, ts, te = _tlv(der, s0)
    tbs = der[s0:te]
    _, _, ae = _tlv(der, te)                # signatureAlgorithm
    tag, bs, be = _tlv(der, ae)
    if tag != 0x03:
        raise ValueError("no signature")
    sig = der[bs + 1:be]
    _, i, _ = _tlv(sig, 0)
    _, rs, re_ = _tlv(sig, i)
    _, ss, se = _tlv(sig, re_)
    k = tbs.find(SPKI_P256)
    if k < 0:
        raise ValueError("not a P-256 key")
    k += len(SPKI_P256)
    # serial: after the TBS header and the optional [0] version
    _, j, _ = _tlv(tbs, 0)
    if tbs[j] == 0xA0:
        _, _, j = _tlv(tbs, j)
    _, ns, ne = _tlv(tbs, j)
    issuer, at = _cn(tbs, ne)
    subject, _ = _cn(tbs, at)
    return {"tbs": tbs, "r": int.from_bytes(sig[rs:re_], "big"), "s": int.from_bytes(sig[ss:se], "big"),
            "qx": int.from_bytes(tbs[k:k + 32], "big"), "qy": int.from_bytes(tbs[k + 32:k + 64], "big"),
            "serial": hexlify(tbs[ns:ne]).decode(), "issuer": issuer, "subject": subject}


def ca_key(issuer):
    if issuer in CAS:
        return CAS[issuer]
    if issuer == EMU_CA:
        return _emu_ca()
    return None


def cert_check(cert):
    """Is the factory certificate signed by the Infineon CA its issuer names? -> (ok, why)."""
    import p256
    ca = ca_key(cert["issuer"])
    if ca is None:
        return False, "unknown issuer %r" % cert["issuer"]
    ok = p256.verify(ca[0], ca[1], hashlib.sha256(cert["tbs"]).digest(), cert["r"], cert["s"])
    return ok, "" if ok else "the CA's signature does not verify"


# ----------------------------------------------------------------------------- record + binding
MAGIC = b"PQ"
BIND_MAGIC = b"PB"
PROFILE_ID = {"quorum-tm1": 3}
BIND_DOMAIN = b"PicoQuorum Trust M key binding v1"


def _b32(v):
    return int(v).to_bytes(32, "big")


def binding_digest(uid, oid, qx, qy):
    """What the factory key E0F0 signs: SHA-256 of the domain, this chip's UID, the key's OID and
    its public key. With E0E0's certificate it says "a genuine Trust M holds this key"."""
    return hashlib.sha256(BIND_DOMAIN + bytes(uid) + oid.to_bytes(2, "big") + _b32(qx) + _b32(qy)).digest()


def record_encode(ser, oid, qx, qy, owner, date, build, profile="quorum-tm1", flags=0):
    """110 bytes for F1D0, integers big-endian:
      0 "PQ" | 2 version 2 | 3 profile | 4 serial (10) | 14 key OID | 16 flags (2) | 18 qx | 50 qy |
      82 owner (20) | 102 date (unix, 4) | 106 build (4)
    Unlike the ATECC's OTP record this one carries the public key: the console reads the key here."""
    ow = bytes.fromhex(owner[2:] if owner.startswith("0x") else owner)
    b = (build or "")[:8]
    bid = bytes.fromhex(b + "0" * (8 - len(b))) if all(c in "0123456789abcdef" for c in b) else bytes(4)
    s = bytes.fromhex(ser) if isinstance(ser, str) else bytes(ser)
    r = (MAGIC + bytes([2, PROFILE_ID.get(profile, 0)]) + s + oid.to_bytes(2, "big") + flags.to_bytes(2, "big")
         + _b32(qx) + _b32(qy) + ow + int(date).to_bytes(4, "big") + bid)
    assert len(r) == 110
    return r


def record_decode(b):
    """F1D0 as a record, or None (a factory chip reads back zeros)."""
    b = bytes(b)
    if len(b) < 110 or b[:2] != MAGIC or b[2] != 2:
        return None
    return {"profile": {v: k for k, v in PROFILE_ID.items()}.get(b[3], "?"), "serial": hexlify(b[4:14]).decode(),
            "oid": int.from_bytes(b[14:16], "big"), "flags": int.from_bytes(b[16:18], "big"),
            "qx": int.from_bytes(b[18:50], "big"), "qy": int.from_bytes(b[50:82], "big"),
            "owner": "0x" + hexlify(b[82:102]).decode(), "date": int.from_bytes(b[102:106], "big"),
            "build": hexlify(b[106:110]).decode()}


def binding_encode(r, s, cert):
    """83 bytes for F1D1: "PB" | version 1 | r | s | SHA-256(certificate DER)[:16]."""
    return BIND_MAGIC + b"\x01" + _b32(r) + _b32(s) + hashlib.sha256(bytes(cert)).digest()[:16]


def binding_decode(b):
    b = bytes(b)
    if len(b) < 83 or b[:2] != BIND_MAGIC or b[2] != 1:
        return None
    return {"r": int.from_bytes(b[3:35], "big"), "s": int.from_bytes(b[35:67], "big"),
            "cert": hexlify(b[67:83]).decode()}


def binding_check(bind, cert_der_bytes, cert, uid, oid, qx, qy):
    """Does F1D1 hold E0F0's signature over this key, made under this certificate? -> bool."""
    import p256
    if not bind or bind["cert"] != hexlify(hashlib.sha256(bytes(cert_der_bytes)).digest()[:16]).decode():
        return False
    return p256.verify(cert["qx"], cert["qy"], binding_digest(uid, oid, qx, qy), bind["r"], bind["s"])


# ----------------------------------------------------------------------------- what the screens say
def short_ca(issuer):
    """ "Infineon OPTIGA(TM) Trust M CA 101" -> "CA 101"."""
    if not issuer:
        return "?"
    if issuer == EMU_CA:
        return "emulator CA"
    i = issuer.find("CA ")
    return issuer[i:] if i >= 0 else issuer[-16:]


def info_lines(uid, issuer=None, key=None, bound=None, sec=None):
    """Short facts, each from the chip itself, for the Signing and Device screens and the ceremony,
    most telling first (the Signing screen shows four): which silicon, where the key came from and
    what seals it, the factory binding, and the chip's own brake on bursts of key use."""
    f = uid_fields(uid) if uid else None
    out = ["Infineon OPTIGA Trust M, CC EAL6+"]
    if key:
        if key.get("hasKey"):
            out.append("Key %04X made on-chip, %s" % (KEY, "sealed (LcsO op)" if key.get("locked") else "not sealed"))
        else:
            out.append("Key %04X: empty" % KEY)
    if bound is not None:
        out.append(("Bound to Infineon cert, %s" % short_ca(issuer)) if bound else "No factory binding")
    elif issuer:
        out.append("Factory cert from %s" % short_ca(issuer))
    if sec is not None:
        out.append("Security event counter: %d" % sec)
    if f:
        out.append("fw %s build %s, wafer %d,%d" % (f["fw"], f["build"], f["x"], f["y"]))
    return out
