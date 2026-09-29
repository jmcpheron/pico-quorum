# A virtual OPTIGA Trust M on the emulator's I2C bus at 0x30, so firmware/trustm.py, trustm_q.py
# and signer.TrustMSigner run here unchanged. Speaks the chip's registers (0x80 DATA, 0x82
# I2C_STATE, 0x88 SOFT_RESET), the IFX data-link frames (frame and ack numbers, CRC-16 0x8408) and
# the APDUs PicoQuorum sends: OpenApplication, GetDataObject (data and metadata), SetDataObject
# (data, erase-and-write, metadata), GenKeyPair (P-256), CalcSign (DER r,s, high s half the time
# as a real chip may give it), GetRandom.
#
# The factory state is what a real Adafruit 4351 answered on 2026-09-28 (chips/trustm-*-probe.txt):
# LcsA operational; E0F0 a factory key (Change NEV, Execute ALW, P-256, usage Auth) certified in
# E0E0; E0F1-E0F3 empty with Change "LcsO < op"; F1D0-F1DB 140 bytes, 100 used, zeros, Change
# "LcsO < op", Read ALW; the security event counter E0C5 at 0. The certificate is signed by a test
# CA (CA_PUB), which tmcfg.py accepts only off the Pico.
#
# The security event counter as the real chip showed it (2026-09-28): every CalcSign, with E0F0
# or E0F1, raises it by one; refused commands do not; it falls back by one about every 5 s.
# GenKeyPair's effect on it is not measured yet.
#
# Modeled as the chip documents them, NOT yet confirmed on silicon (a sacrificial chip will): that
# GenKeyPair checks the key object's Change condition; that metadata can be written only while
# LcsO is below operational, and LcsO only goes up; the error codes in F1C2.
# Not modeled: shielded connection, Luc/Conf/Int/Auto conditions (refused), sleep timing.
#
# Asleep, a real Trust M NACKs its address, so i2c.scan() does not list it; here too. present
# says whether it is on the bus at all; the state persists with the ATECC's (key "trustm").
import json
import hashlib
import time
import _emu

SEC_DECAY_MS = 5000     # one count back about every 5 s (measured on the real chip)

ADDR = 0x30
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
LCS_OP = 0x07

# The emulator's certificate authority: a fixed test key, never Infineon's.
CA_NAME = "PicoQuorum emulator CA (not Infineon)"
CA_D = int.from_bytes(hashlib.sha256(b"PicoQuorum emulator Trust M CA").digest(), "big") % N
CA_PUB = None           # (x, y), computed on first use


def _ca_pub():
    global CA_PUB
    if CA_PUB is None:
        import p256
        CA_PUB = p256.pubkey(CA_D)
    return CA_PUB


# Real UID prefix (CIM .. chip type) and suffix (firmware id, build) from the probed chip; the
# batch and wafer X/Y are made up per virtual chip.
UID_HEAD = bytes.fromhex("cd16338401001c00010000")
UID_TAIL = bytes.fromhex("801010710809")

# Error codes (F1C2). Seen on the real chip: 0x01 an OID it does not have, 0x07 reading a key
# object's data, 0x0B CalcSign with an empty key. The others are the manual's.
ERR_OID, ERR_PARAM, ERR_LEN, ERR_AC, ERR_BOUNDS, ERR_CMD, ERR_KEY = 0x01, 0x03, 0x04, 0x07, 0x09, 0x0B, 0x0B


def _crc(data):
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0x8408 if c & 1 else c >> 1
    return c


def _hx(b):
    return "".join("%02x" % x for x in b)


# ----------------------------------------------------------------------------- DER, for the cert
def _len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes(2 if n > 0xFF else 1, "big")
    return bytes([0x80 | len(b)]) + b


def _el(tag, body):
    return bytes([tag]) + _len(len(body)) + body


def _int(v):
    b = v.to_bytes(33, "big")          # MicroPython ints have no bit_length()
    i = 0
    while i < 32 and b[i] == 0:
        i += 1
    b = b[i:]
    if b[0] & 0x80:
        b = b"\x00" + b
    return _el(0x02, b)


def _name(cn):
    return _el(0x30, _el(0x31, _el(0x30, bytes.fromhex("0603550403") + _el(0x0C, cn.encode()))))


ECDSA_SHA256 = _el(0x30, bytes.fromhex("06082a8648ce3d040302"))
SPKI_HEAD = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d03010703420004")


def make_cert(serial, qx, qy):
    """A certificate shaped like Infineon's (issuer, validity, subject "Infineon IoT Node", P-256
    key), signed by the emulator CA."""
    import p256
    tbs = _el(0x30, bytes.fromhex("a003020102") + _int(serial) + ECDSA_SHA256 + _name(CA_NAME)
              + _el(0x30, _el(0x17, b"190701150414Z") + _el(0x17, b"390701150414Z"))
              + _name("Infineon IoT Node (emulated)") + SPKI_HEAD + qx.to_bytes(32, "big") + qy.to_bytes(32, "big"))
    r, s = p256.sign(CA_D, hashlib.sha256(tbs).digest())
    return _el(0x30, tbs + ECDSA_SHA256 + _el(0x03, b"\x00" + _el(0x30, _int(r) + _int(s))))


def wrap_cert(der):
    """E0E0's TLS-style wrapper: C0, length, chain length, certificate length, certificate."""
    n = len(der)
    return b"\xc0" + (n + 6).to_bytes(2, "big") + (n + 3).to_bytes(3, "big") + n.to_bytes(3, "big") + der


# ----------------------------------------------------------------------------- objects
def _key_meta(change):
    return {"lcso": 0x01, "change": change, "exec": b"\x00"}


def factory():
    """The objects of a factory-fresh chip: {oid: {"data": bytes, "meta": {...}, "key": scalar}}."""
    import p256
    objs = {}
    d0 = p256.rand_scalar()
    x, y = p256.pubkey(d0)
    ser = int.from_bytes(bytes(_rand(4)), "big") | 0x01000000
    cert = wrap_cert(make_cert(ser, x, y))
    objs[0xE0F0] = {"meta": {"lcso": 0x01, "change": b"\xff", "exec": b"\x00", "algo": 0x03, "usage": 0x01}, "key": d0}
    for oid in (0xE0F1, 0xE0F2, 0xE0F3):
        objs[oid] = {"meta": _key_meta(b"\xe1\xfc\x07")}
    objs[0xE0E0] = {"data": cert, "meta": {"lcso": 0x01, "max": 1728, "change": b"\xff", "read": b"\x00", "exec": b"\x00", "type": 0x12}}
    for oid in list(range(0xF1D0, 0xF1DC)):
        objs[oid] = {"data": bytes(100), "meta": {"lcso": 0x01, "max": 140, "change": b"\xe1\xfc\x07", "read": b"\x00"}}
    return objs


def _rand(n):
    try:
        return bytes(_emu.random(n))
    except Exception:
        import os
        return os.urandom(n)


ORDER = (("lcso", 0xC0), ("max", 0xC4), ("used", 0xC5), ("change", 0xD0), ("read", 0xD1), ("exec", 0xD3),
         ("algo", 0xE0), ("usage", 0xE1), ("type", 0xE8))


def meta_bytes(o):
    m = dict(o["meta"])
    if "data" in o:
        m["used"] = len(o["data"])
    body = b""
    for k, tag in ORDER:
        v = m.get(k)
        if v is None:
            continue
        if k == "max" or k == "used":
            v = v.to_bytes(2 if v > 0xFF else 1, "big")
        elif isinstance(v, int):
            v = bytes([v])
        body += bytes([tag, len(v)]) + bytes(v)
    return bytes([0x20, len(body)]) + body


class Chip:
    def __init__(self):
        self.objs = None
        self.uid = None
        self.sec = 0
        self.sec_t = time.ticks_ms()
        self.err = 0
        self.ptr = 0x82
        self.pending = b""
        self.frnr = 0
        self.load()
        if self.objs is None:
            self.fresh()

    def fresh(self):
        self.objs = factory()
        self.uid = UID_HEAD + _rand(6) + bytes([0, _rand(1)[0] % 120, 0, _rand(1)[0] % 120]) + UID_TAIL
        self.sec = 0
        self.save()

    # --- persistence, next to the ATECC's state ------------------------------------------
    def load(self):
        try:
            st = json.loads(_emu.chip_load() or "{}").get("trustm")
        except Exception:
            st = None
        if not st:
            return
        try:
            self.uid = bytes.fromhex(st["uid"])
            self.sec = st.get("sec", 0)
            self.objs = {}
            for k, o in st["objs"].items():
                m = {}
                for mk, mv in o["meta"].items():
                    m[mk] = bytes.fromhex(mv) if isinstance(mv, str) else mv
                e = {"meta": m}
                if "data" in o:
                    e["data"] = bytes.fromhex(o["data"])
                if "key" in o:
                    e["key"] = int(o["key"], 16)
                self.objs[int(k)] = e
        except Exception as ex:
            print("trustm_sim: bad saved state (%s), starting fresh" % ex)
            self.objs = None

    def save(self):
        objs = {}
        for k, o in self.objs.items():
            e = {"meta": {mk: (_hx(mv) if isinstance(mv, (bytes, bytearray)) else mv) for mk, mv in o["meta"].items()}}
            if "data" in o:
                e["data"] = _hx(o["data"])
            if "key" in o:
                e["key"] = "%064x" % o["key"]
            objs[str(k)] = e
        _store("trustm", {"uid": _hx(self.uid), "sec": self.sec, "objs": objs})

    # --- the I2C registers -----------------------------------------------------------------
    def write(self, buf):
        buf = bytes(buf)
        if len(buf) == 1:
            self.ptr = buf[0]
            return
        reg, payload = buf[0], buf[1:]
        if reg == 0x88:                     # soft reset
            self.pending = b""
            self.frnr = 0
            self.ptr = 0x82
            return
        if reg == 0x80:
            self.frame(payload)
            self.ptr = 0x82

    def read(self, n):
        if self.ptr == 0x82:
            if self.pending:
                return bytes([0x48, 0x80, len(self.pending) >> 8, len(self.pending) & 0xFF])[:n]
            return b"\x08\x80\x00\x00"[:n]
        if self.ptr == 0x80:
            out, self.pending = self.pending[:n], self.pending[n:]
            return out
        return bytes(n)

    # --- data link --------------------------------------------------------------------------
    def frame(self, f):
        if len(f) < 5 or _crc(f[:-2]) != int.from_bytes(f[-2:], "big"):
            return                          # a bad frame: the host times out, as on a noisy bus
        fctr = f[0]
        if fctr & 0x80:
            return                          # a control frame (the host's ack): nothing to answer
        host_nr = (fctr >> 2) & 3
        n = int.from_bytes(f[1:3], "big")
        apdu = f[4:3 + n]                   # after PCTR
        resp = self.apdu(apdu)
        body = bytes([(self.frnr << 2) | host_nr]) + (len(resp) + 1).to_bytes(2, "big") + b"\x00" + resp
        self.frnr = (self.frnr + 1) & 3
        self.pending = body + _crc(body).to_bytes(2, "big")

    # --- APDUs ------------------------------------------------------------------------------
    def apdu(self, a):
        cmd, param = a[0] & 0x7F, a[1]
        data = a[4:4 + int.from_bytes(a[2:4], "big")]
        try:
            out = {0x70: self.open_app, 0x01: self.get, 0x02: self.set, 0x31: self.calc_sign, 0x38: self.gen_keypair,
                   0x0C: self.get_random}[cmd](param, data)
        except KeyError:
            return self.fail(ERR_CMD)
        except _Fail as e:
            return self.fail(e.code)
        self.err = 0
        return b"\x00\x00" + len(out).to_bytes(2, "big") + out

    def fail(self, code):
        self.err = code
        return b"\xff\x00\x00\x00"

    def obj(self, oid):
        if oid == 0xE0C2:
            return {"data": self.uid, "meta": {"change": b"\xff", "read": b"\x00"}}
        if oid == 0xE0C0:
            return {"data": bytes([LCS_OP]), "meta": {"change": b"\x00", "read": b"\x00"}}
        if oid == 0xE0C5:
            return {"data": bytes([self.sec_now()]), "meta": {"change": b"\xff", "read": b"\x00"}}
        if oid == 0xF1C2:
            return {"data": bytes([self.err]), "meta": {"change": b"\xff", "read": b"\x00"}}
        o = self.objs.get(oid)
        if o is None:
            raise _Fail(ERR_OID)
        return o

    def sec_now(self):
        """The counter after its decay since it was last touched."""
        steps = time.ticks_diff(time.ticks_ms(), self.sec_t) // SEC_DECAY_MS
        if steps > 0:
            self.sec = max(0, self.sec - steps)
            self.sec_t = time.ticks_add(self.sec_t, steps * SEC_DECAY_MS)
        if self.sec == 0:
            self.sec_t = time.ticks_ms()
        return self.sec

    def sec_event(self):
        self.sec = min(255, self.sec_now() + 1)

    def ac(self, o, which):
        """Is the object's access condition met? ALW, NEV and LcsO/LcsA comparisons; anything else
        (Conf, Int, Auto, Luc) is not modeled and refused."""
        ac = o["meta"].get(which)
        if ac is None:
            return which != "change"
        ac = bytes(ac)
        result, op, i = None, None, 0
        while i < len(ac):
            x = ac[i]
            if x == 0x00:
                v, i = True, i + 1
            elif x == 0xFF:
                v, i = False, i + 1
            elif x in (0xE0, 0xE1) and i + 2 < len(ac):
                have = LCS_OP if x == 0xE0 else o["meta"].get("lcso", 0x01)
                want, cmp_ = ac[i + 2], ac[i + 1]
                v = {0xFA: have == want, 0xFB: have > want, 0xFC: have < want}.get(cmp_, False)
                i += 3
            elif x in (0xFD, 0xFE):
                op, i = x, i + 1
                continue
            else:
                return False
            result = v if result is None else (result and v if op == 0xFD else result or v)
        return bool(result)

    def open_app(self, param, data):
        return b""

    def get(self, param, data):
        oid = int.from_bytes(data[:2], "big")
        o = self.obj(oid)
        if param == 0x01:
            return meta_bytes(o)
        if "data" not in o:
            raise _Fail(ERR_AC)             # a key object's data is never readable (0x07 on the real chip)
        if not self.ac(o, "read"):
            raise _Fail(ERR_AC)
        d = o["data"]
        if len(data) >= 6:
            off, n = int.from_bytes(data[2:4], "big"), int.from_bytes(data[4:6], "big")
            return d[off:off + n]
        return d

    def set(self, param, data):
        oid = int.from_bytes(data[:2], "big")
        off = int.from_bytes(data[2:4], "big")
        body = bytes(data[4:])
        o = self.obj(oid)
        if oid not in self.objs:
            raise _Fail(ERR_AC)
        if param == 0x01:
            return self.set_meta(o, body)
        if "data" not in o or param not in (0x00, 0x40):
            raise _Fail(ERR_PARAM)
        if not self.ac(o, "change"):
            raise _Fail(ERR_AC)
        cur = b"" if param == 0x40 else o["data"]
        if off + len(body) > o["meta"].get("max", 0):
            raise _Fail(ERR_BOUNDS)
        cur = cur + bytes(max(0, off - len(cur)))
        o["data"] = cur[:off] + body + cur[off + len(body):]
        self.save()
        return b""

    def set_meta(self, o, tlv):
        """Only while LcsO is below operational; LcsO only goes up; only LcsO and the access
        conditions can be written (as modeled: confirm on silicon)."""
        if o["meta"].get("lcso", 0x01) >= LCS_OP or not tlv or tlv[0] != 0x20:
            raise _Fail(ERR_AC)
        i, end = 2, 2 + tlv[1]
        upd = {}
        while i < end:
            tag, n = tlv[i], tlv[i + 1]
            v = tlv[i + 2:i + 2 + n]
            k = {0xC0: "lcso", 0xD0: "change", 0xD1: "read", 0xD3: "exec"}.get(tag)
            if k is None:
                raise _Fail(ERR_PARAM)
            upd[k] = v[0] if k == "lcso" else bytes(v)
            i += 2 + n
        if "lcso" in upd and upd["lcso"] < o["meta"].get("lcso", 0x01):
            raise _Fail(ERR_PARAM)
        o["meta"].update(upd)
        self.save()
        return b""

    def gen_keypair(self, param, data):
        import p256
        if param != 0x03:
            raise _Fail(ERR_PARAM)
        oid = usage = None
        i = 0
        while i < len(data):
            tag, n = data[i], int.from_bytes(data[i + 1:i + 3], "big")
            v = data[i + 3:i + 3 + n]
            if tag == 0x01:
                oid = int.from_bytes(v, "big")
            elif tag == 0x02:
                usage = v[0]
            i += 3 + n
        if oid not in (0xE0F1, 0xE0F2, 0xE0F3):
            raise _Fail(ERR_OID)
        o = self.objs[oid]
        if not self.ac(o, "change"):
            raise _Fail(ERR_AC)
        d = p256.rand_scalar()
        x, y = p256.pubkey(d)
        o["key"] = d
        o["meta"]["algo"] = 0x03
        o["meta"]["usage"] = usage or 0x10
        self.save()
        pub = b"\x03\x42\x00\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")
        return b"\x02" + len(pub).to_bytes(2, "big") + pub

    def calc_sign(self, param, data):
        import p256
        if param != 0x11:
            raise _Fail(ERR_PARAM)
        digest = oid = None
        i = 0
        while i < len(data):
            tag, n = data[i], int.from_bytes(data[i + 1:i + 3], "big")
            v = data[i + 3:i + 3 + n]
            if tag == 0x01:
                digest = bytes(v)
            elif tag == 0x03:
                oid = int.from_bytes(v, "big")
            i += 3 + n
        o = self.objs.get(oid)
        if o is None or "key" not in o:
            raise _Fail(ERR_KEY if o is not None else ERR_OID)
        if not self.ac(o, "exec"):
            raise _Fail(ERR_AC)
        r, s = p256.sign(o["key"], digest)
        self.sec_event()                    # a private-key use counts as a security event
        if _rand(1)[0] & 1:
            s = N - s                       # a chip does not promise low s
        return _int(r) + _int(s)

    def get_random(self, param, data):
        n = int.from_bytes(data[:2], "big")
        if not 8 <= n <= 256:
            raise _Fail(ERR_LEN)
        return _rand(n)


class _Fail(Exception):
    def __init__(self, code):
        self.code = code


def _store(key, value):
    try:
        st = json.loads(_emu.chip_load() or "{}")
    except Exception:
        st = {}
    st[key] = value
    try:
        _emu.chip_save(json.dumps(st))
    except Exception as e:
        print("trustm_sim: could not save state: %s" % e)


def _bus():
    try:
        return json.loads(_emu.chip_load() or "{}").get("bus") or {}
    except Exception:
        return {}


_chip = None
present = bool(_bus().get("trustm", False))     # off by default: the ATECC is the emulator's chip


def chip():
    global _chip
    if _chip is None:
        _chip = Chip()
    return _chip


# --- knobs for tools/emu chip ..., sketches and tests --------------------------------------------
def bus(trustm=None, atecc=None):
    """Which chips are on the virtual bus, kept across reboots."""
    global present
    import atecc_sim
    if trustm is not None:
        present = bool(trustm)
    if atecc is not None:
        atecc_sim.present = bool(atecc)
    _store("bus", {"trustm": present, "atecc608": atecc_sim.present})
    return {"trustm": present, "atecc608": atecc_sim.present}


def wipe():
    """Back to a factory-fresh part (a new UID and factory key)."""
    chip().fresh()
    return "Trust M wiped: factory-fresh, E0F1 empty"


def seal_as_quorum(owner_signer=None):
    """A chip after the whole quorum-tm1 ceremony: a key in E0F1, the record and binding written,
    all three sealed (LcsO operational). For console tests; the ceremony itself is provision_tm."""
    import p256
    import tmcfg
    c = chip()
    d = p256.rand_scalar()
    x, y = p256.pubkey(d)
    k = c.objs[0xE0F1]
    k["key"] = d
    k["meta"].update({"algo": 0x03, "usage": 0x10})
    import webauthn
    import quorum_cfg
    owner = webauthn.owner_address("0x%064x" % x, "0x%064x" % y, owner_signer or quorum_cfg.CFG["signer"])
    c.objs[0xF1D0]["data"] = tmcfg.record_encode(tmcfg.serial(c.uid), 0xE0F1, x, y, owner, 1790000000, "00000000")
    cert = tmcfg.cert_der(c.objs[0xE0E0]["data"])
    r, s = p256.sign(c.objs[0xE0F0]["key"], tmcfg.binding_digest(c.uid, 0xE0F1, x, y))
    c.objs[0xF1D1]["data"] = tmcfg.binding_encode(r, s, cert)
    for oid in (0xE0F1, 0xF1D0, 0xF1D1):
        c.objs[oid]["meta"]["lcso"] = LCS_OP
    c.save()
    return "Trust M sealed as quorum-tm1: owner %s" % owner


def state():
    c = chip()
    return {"present": present, "serial": _hx(c.uid[11:21]), "sec": c.sec,
            "E0F1": {"key": "key" in c.objs[0xE0F1], "lcso": c.objs[0xE0F1]["meta"].get("lcso")},
            "F1D0": c.objs[0xF1D0]["meta"].get("lcso"), "F1D1": c.objs[0xF1D1]["meta"].get("lcso")}
