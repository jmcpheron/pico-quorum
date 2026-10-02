# The refusals a sealed and frozen Trust M must give, tried for real: ONLY on a sacrificial chip.
# A refusal that failed would replace the key or rewrite what it tested, so the script runs only
# when the chip on the bus has the serial named here. First run on TM2 (0a091b5c000b00620076,
# 2026-10-01): every write refused, 07, and lowering a lifecycle 05 (docs/TRUSTM.md).
#   1. Set SACRIFICIAL below to the chip's serial (tools/fw verify shows it). Never a chip that owns anything.
#   2. With the board on the ceremony image after T10:
#      mpremote connect PORT resume exec "$(cat tools/board/tm_refusals.py)"
# The ceremony app is paused while it runs and started again after. It prints one RESULT: line.
SACRIFICIAL = ""
import sys, json, hashlib, p256, tmcfg, trustm_q
ca = sys.modules.get("chipapp")
if ca and getattr(ca, "timer", None):
    ca.stop()
t = trustm_q.TrustM()
out = {"serial": t.serial()}
def mh(oid):
    return "".join("%02x" % b for b in t.metadata(oid))
def trial(name, fn, oid):
    m0, s0 = mh(oid), t.sec()
    try:
        r = fn()
        res = "ACCEPTED " + repr(r)[:60]
    except trustm_q.Refused as e:
        res = "refused: " + str(e)[-70:]
    except Exception as e:
        res = "error: %r" % (e,)
    out[name] = {"result": res, "metaBefore": m0, "metaAfter": mh(oid), "sec": [s0, t.sec()]}
if not SACRIFICIAL or out["serial"] != SACRIFICIAL:
    print("NOT THE SACRIFICIAL CHIP, nothing tried:" + json.dumps(out))
else:
    recb = bytes(t.get(0xF1D0))
    rec = tmcfg.record_decode(recb)
    trial("genkey_E0F1_sealed", lambda: t.gen_keypair(0xE0F1), 0xE0F1)
    trial("write_F1D0_sealed_same_bytes", lambda: t.set_data(0xF1D0, recb), 0xF1D0)
    trial("write_F1D2_frozen", lambda: t.set_data(0xF1D2, b"PicoQuorum refusal test"), 0xF1D2)
    trial("genkey_E0F2_frozen", lambda: t.gen_keypair(0xE0F2), 0xE0F2)
    trial("lower_lifecycle_F1D3", lambda: t.set_lifecycle(0xF1D3, 0x03), 0xF1D3)
    trial("meta_change_F1D4_to_ALW", lambda: t.command(0x02, 0x01, (0xF1D4).to_bytes(2, "big") + b"\x00\x00" + bytes([0x20, 3, 0xD0, 1, 0x00]), retry=False), 0xF1D4)
    d = hashlib.sha256(b"after the refusal tests").digest()
    r, s = t.sign(0xE0F1, d)
    out["key_still_the_records"] = p256.verify(rec["qx"], rec["qy"], d, r, s)
    out["F1D0_unchanged"] = bytes(t.get(0xF1D0)) == recb
    out["F1D2_first_bytes"] = "".join("%02x" % b for b in t.get(0xF1D2))[:32]
    out["sec_end"] = t.sec()
    print("RESULT:" + json.dumps(out))
if ca:
    ca.start_timer()
