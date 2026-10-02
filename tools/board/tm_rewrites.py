# Every way to rewrite a sealed and frozen Trust M we could think of, tried for real: data writes
# (plain, at an offset, past the end, empty, erase-and-write), a counter increment, the certificate
# and trust-anchor slots, the UID, metadata (the same value again, Read or Execute to NEV, two tags,
# an empty TLV), the factory objects still at LcsO creation (E0F0, E0E0, E140), and lowering the
# chip's own lifecycle (LcsA). Never termination. ONLY on a sacrificial chip: any write that is
# accepted is permanent, so it runs only when the chip on the bus has the serial named here.
#   1. Set SACRIFICIAL below to the chip's serial. Never a chip that owns anything.
#   2. mpremote connect PORT resume exec "$(cat tools/board/tm_rewrites.py)"
# Prints one RESULT: line: each trial's answer (ok, or the chip's error code), the security counter
# around it, the object's metadata and data before and after; then whether the factory key still
# signs under its certificate and E0F1 still signs as its record says.
SACRIFICIAL = ""
import sys, json, hashlib, p256, tmcfg, trustm_q
_apps = [m for m in (sys.modules.get(n) for n in ("quorum", "chipapp")) if m and getattr(m, "timer", None)]
for _m in _apps:
    _m.stop()
t = trustm_q.TrustM()
out = {"serial": t.serial(), "trials": []}
SET, W, EW, META, COUNT = 0x02, 0x00, 0x40, 0x01, 0x02


def hx(b):
    return "".join("%02x" % x for x in b)


def sec():
    """The counter, or None when the chip's answer was empty (seen once after an odd write: the
    session is reopened and the next read is fine)."""
    try:
        return t.sec()
    except Exception:
        t.s = None
        return None


def peek(oid):
    try:
        m = hx(t.metadata(oid))
    except Exception as e:
        m = "error %s" % str(e)[-20:]
        t.s = None
    try:
        d = hx(t.get(oid))[:64]
    except Exception as e:
        d = "error %s" % str(e)[-20:]
        t.s = None
    return m, d


def trial(name, oid, param, off, body):
    m0, d0 = peek(oid)
    s0 = sec()
    try:
        t.command(SET, param, oid.to_bytes(2, "big") + off.to_bytes(2, "big") + bytes(body), retry=False)
        res = "ACCEPTED"
    except trustm_q.Refused as e:
        msg = str(e)
        res = "refused " + (msg[msg.find("error code") + 11:msg.find("error code") + 13] if "error code" in msg else msg[-30:])
    except Exception as e:
        res = "error " + str(e)[-40:]
        t.s = None
    s1 = sec()
    m1, d1 = peek(oid)
    e = {"name": name, "oid": "%04X" % oid, "result": res, "sec": [s0, s1],
         "metaChanged": m0 != m1, "dataChanged": d0 != d1, "metaBefore": m0, "metaAfter": m1}
    out["trials"].append(e)
    print("TRIAL:" + json.dumps(e))       # each as it finishes: a crash later loses nothing


def meta(*tags):
    body = b"".join(bytes([tag, len(v)]) + v for tag, v in tags)
    return bytes([0x20, len(body)]) + body


if not SACRIFICIAL or out["serial"] != SACRIFICIAL:
    print("NOT THE SACRIFICIAL CHIP, nothing tried:" + json.dumps(out))
else:
    recb = bytes(t.get(tmcfg.RECORD))
    der = tmcfg.cert_der(t.get_all(tmcfg.CERT))
    cert = tmcfg.cert_parse(der)
    # data: every way in
    trial("F1D2 write at 0", 0xF1D2, W, 0, b"A")
    trial("F1D2 write at 100", 0xF1D2, W, 100, b"B")
    trial("F1D2 write past the end (140)", 0xF1D2, W, 140, b"C")
    trial("F1D2 write of nothing", 0xF1D2, W, 0, b"")
    trial("F1D2 erase-and-write", 0xF1D2, EW, 0, b"D")
    trial("F1D0 (sealed record) one byte at 109", 0xF1D0, W, 109, b"\x00")
    trial("F1E0 200 bytes", 0xF1E0, W, 0, bytes(range(200)))
    trial("E0E1 (spare cert slot)", 0xE0E1, W, 0, b"\xc0\x00\x01\x00")
    trial("E0E8 (trust anchor)", 0xE0E8, W, 0, b"\x30\x00")
    trial("E120 count +1", 0xE120, COUNT, 0, b"\x01")
    trial("E120 write 8 bytes", 0xE120, W, 0, bytes(8))
    trial("E0C2 (UID)", 0xE0C2, W, 0, b"\x00")
    # metadata on frozen objects
    trial("F1D2 meta: LcsO op again", 0xF1D2, META, 0, meta((0xC0, b"\x07")))
    trial("F1D2 meta: Read NEV", 0xF1D2, META, 0, meta((0xD1, b"\xff")))
    trial("E0F1 meta: Execute NEV", 0xE0F1, META, 0, meta((0xD3, b"\xff")))
    trial("F1D2 meta: LcsO op + Change ALW", 0xF1D2, META, 0, meta((0xC0, b"\x07"), (0xD0, b"\x00")))
    trial("F1D2 meta: empty", 0xF1D2, META, 0, meta())
    # the factory objects, still at LcsO creation: their rules first, then their lifecycle
    trial("E0F0 meta: Change ALW", 0xE0F0, META, 0, meta((0xD0, b"\x00")))
    trial("E0F0 meta: LcsO op", 0xE0F0, META, 0, meta((0xC0, b"\x07")))
    trial("E0E0 meta: LcsO op", 0xE0E0, META, 0, meta((0xC0, b"\x07")))
    trial("E140 meta: LcsO op", 0xE140, META, 0, meta((0xC0, b"\x07")))
    # the chip's own lifecycle, down (never up to termination)
    trial("E0C0 (LcsA) down to initialization", 0xE0C0, W, 0, b"\x03")
    # still working?
    d = hashlib.sha256(b"after the rewrites").digest()
    r, s = t.sign(tmcfg.FACTORY_KEY, d)
    out["factoryKeyStillMatchesCert"] = p256.verify(cert["qx"], cert["qy"], d, r, s)
    rec = tmcfg.record_decode(recb)
    r, s = t.sign(tmcfg.KEY, d)
    out["keyStillTheRecords"] = p256.verify(rec["qx"], rec["qy"], d, r, s)
    out["recordUnchanged"] = bytes(t.get(tmcfg.RECORD)) == recb
    out["lcsa"] = t.lcsa()
    print("RESULT:" + json.dumps(out))
for _m in _apps:
    _m.start_timer()
