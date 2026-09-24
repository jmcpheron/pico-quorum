#!/usr/bin/env python3
# Check firmware/safe_tx.py against every vector in test-vectors/. Exit 1 on any mismatch.
#   python3 test-vectors/run.py
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "firmware"))
import safe_tx  # noqa: E402


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
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
