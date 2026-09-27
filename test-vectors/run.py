#!/usr/bin/env python3
# Check firmware/safe_tx.py against every vector in test-vectors/, firmware/decode.py against
# each vector's "expect" (what the screen must say about it), and firmware/webauthn.py against
# webauthn.json (the chip signature packed for the Safe). Exit 1 on any mismatch.
#   python3 test-vectors/run.py
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "firmware"))
import safe_tx  # noqa: E402
import decode  # noqa: E402
import quorum_cfg  # noqa: E402
from keccak import keccak256  # noqa: E402
import webauthn_check  # noqa: E402


def hx(b):
    return "0x" + b.hex()


def main():
    with open(os.path.join(HERE, "safe_tx.json")) as f:
        vectors = json.load(f)["vectors"]
    failed = 0
    for v in vectors:
        t = v["tx"]
        dom = hx(safe_tx.domain_separator(v["chainId"], v["safe"]))
        h = safe_tx.safe_tx_hash(v["chainId"], v["safe"], t["to"], t["value"], t["data"], t["operation"],
                                 t["safeTxGas"], t["baseGas"], t["gasPrice"], t["gasToken"],
                                 t["refundReceiver"], t["nonce"])
        ok = dom == v["domainSeparator"].lower() and hx(h) == v["safeTxHash"].lower()
        if ok and safe_tx.verify_code(h) != v["safeTxHash"].lower()[-8:]:
            ok = False
        print("%s  %-24s %s" % ("pass" if ok else "FAIL", v["name"], safe_tx.verify_code(h)))
        if not ok:
            failed += 1
            print("      domain   got %s\n               want %s" % (dom, v["domainSeparator"]))
            print("      hash     got %s\n               want %s" % (hx(h), v["safeTxHash"]))
    print("%d/%d vectors pass" % (len(vectors) - failed, len(vectors)))
    failed += check_decode(vectors)
    failed += webauthn_check.check(os.path.join(HERE, "webauthn.json"))
    return 1 if failed else 0


def check_decode(vectors):
    failed = 0
    for sel, sig in decode.SIGS.items():
        if keccak256(sig.encode())[:4].hex() != sel:
            print("FAIL  selector %s is not %s" % (sel, sig))
            failed += 1
    for a, (name, logo, calls) in decode.for_chain(quorum_cfg.CFG, "contracts", None).items():
        for sel, (sig, what) in calls.items():
            if keccak256(sig.encode())[:4].hex() != sel:
                print("FAIL  %s selector %s is not %s" % (name, sel, sig))
                failed += 1
    n = 0
    for v in vectors:
        got = decode.review(v["tx"], decode.context(quorum_cfg.CFG, v["safe"]))
        if "expect" not in v:
            print("----  %-24s %s (%s, no expectation)" % (v["name"], got["summary"][:40], got["level"]))
            continue
        n += 1
        items = [[i["title"], i["level"]] for i in got["items"]]
        ok = got["summary"] == v["expect"]["summary"] and items == v["expect"]["items"]
        print("%s  %-24s %s (%s)" % ("pass" if ok else "FAIL", v["name"], got["summary"][:40], got["level"]))
        if not ok:
            failed += 1
            print("      got  %r %r\n      want %r %r" % (got["summary"], items, v["expect"]["summary"], v["expect"]["items"]))
    print("%d/%d decode expectations pass, %d selectors checked" % (n - failed, n, len(decode.SIGS)))
    return failed


if __name__ == "__main__":
    sys.exit(main())
