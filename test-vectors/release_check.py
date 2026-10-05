# Checks firmware/release.py and decode.py against test-vectors/release.json (tools/vectors/release.mjs,
# made by viem and checked against a real Safe on Ethereum). Shared by run.py (CPython) and
# run-micropython.mjs (MicroPython). Returns the failure count.
import json
import decode
import quorum_cfg
import release


def check(path):
    with open(path) as f:
        doc = json.load(f)
    bad = 0

    def ok(cond, what):
        nonlocal bad
        print(("pass  " if cond else "FAIL  ") + what)
        bad += 0 if cond else 1

    for v in doc["vectors"]:
        d = decode.hx(release.digest(v["version"], v["firmware"], v["manifest"]))
        ok(d == v["digest"], "release %-14s digest %s" % (v["name"], d[:14]))
        safe = v["safeMessageHash"]["safe"]
        ctx = decode.context(quorum_cfg.CFG, safe, chain=1)
        tx = {"to": v["to"], "value": "0", "data": v["data"], "operation": v["operation"], "origin": v["origin"]}
        r = decode.review(tx, ctx)
        it = r["items"][0]
        ok(not r["refuse"] and it["title"] == "RELEASE" and it["release"]["digest"] == v["digest"] and r["summary"] == "Approve release " + v["version"],
           "release %-14s the console reads the approval and would sign it" % v["name"])
        o = json.loads(v["origin"])
        for why, t in (
            ("another version in the note", dict(tx, origin=json.dumps({"pq": dict(o["pq"], v="2026.10.99")}))),
            ("another fingerprint in the note", dict(tx, origin=json.dumps({"pq": dict(o["pq"], f="ab" * 32)}))),
            ("no note", dict(tx, origin=None)),
            ("a note naming no release", dict(tx, origin='{"url": "https://app.safe.global", "name": "Safe{Wallet}"}')),
            ("another digest in the calldata", dict(tx, data=v["data"][:-2] + ("00" if v["data"][-2:] != "00" else "01"))),
            ("a byte more of calldata", dict(tx, data=v["data"] + "00")),
            ("ETH sent with it", dict(tx, value="1")),
            ("a version that isn't year.month.n", dict(tx, origin=json.dumps({"pq": dict(o["pq"], v="latest")}))),
        ):
            ok(bool(decode.review(t, ctx)["refuse"]), "release %-14s refused: %s" % (v["name"], why))
        other = dict(tx, to="0x" + "12" * 20)
        ok(bool(decode.review(other, ctx)["refuse"]), "release %-14s refused: the same delegatecall to an unpinned library" % v["name"])
    return bad
