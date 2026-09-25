# Checks firmware/webauthn.py against test-vectors/webauthn.json. Shared by run.py (CPython) and
# run-micropython.mjs (MicroPython), so it sticks to what both have. Returns the failure count.
import json
import quorum_cfg
import webauthn


def hx(b):
    return "0x" + "".join("%02x" % x for x in b)


def check(path):
    with open(path) as f:
        doc = json.load(f)
    signer = quorum_cfg.CFG["signer"]
    bad = 0
    for k in ("factory", "singleton", "verifiers"):
        if doc["signer"][k].lower() != signer[k].lower():
            print("FAIL  webauthn.json was made for signer %s %s, quorum_cfg.py has %s" % (k, doc["signer"][k], signer[k]))
            bad += 1
    for v in doc["vectors"]:
        r, s = int(v["r"], 16), int(v["s"], 16)
        ad, fields, digest = webauthn.assertion(v["safeTxHash"])
        got = {
            "authenticatorData": hx(ad),
            "clientDataFields": fields,
            "clientDataJSON": webauthn.client_json(bytes.fromhex(v["safeTxHash"][2:])),
            "digest": hx(digest),
            "signature": hx(webauthn.encode(ad, fields, r, s)),
            "contractSignature": hx(webauthn.contract_signature(v["owner"], ad, fields, r, s)),
            "owner": webauthn.owner_address(v["qx"], v["qy"], signer),
        }
        wrong = [k for k in got if got[k] != v[k]]
        print("%s  webauthn %-24s owner %s" % ("FAIL" if wrong else "pass", v["name"], got["owner"]))
        for k in wrong:
            print("      %s\n        got  %s\n        want %s" % (k, got[k], v[k]))
        bad += 1 if wrong else 0
    print("%d/%d webauthn vectors pass" % (len(doc["vectors"]) - bad, len(doc["vectors"])))
    return bad
