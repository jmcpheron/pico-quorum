#!/usr/bin/env python3
# tools/relay/relay.py without a board or a network: what it forwards and refuses, what each fault
# sends, and that the API key never reaches a log or the console.
#   python3 tools/relay/relay_test.py
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import relay as R

failed = [0]
KEY = "test-key-0123456789"
SAFE = "0x5a5A5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a"
H = "0x" + "ab" * 32
BASES = list(R.services().values())
BASE = R.services()[84532]
MOCK = "http://127.0.0.1:8787"


def check(ok, what):
    print(("pass  " if ok else "FAIL  ") + what)
    if not ok:
        failed[0] += 1


def req(url, m="GET", body=None, i=7):
    d = {"t": "req", "id": i, "m": m, "url": url}
    if body is not None:
        d["body"] = body
    return d


def refused(d, allowed=()):
    try:
        R.check(d, BASES, allowed)
    except R.Refused as e:
        return str(e)
    return None


INFO = BASE + "/api/v1/safes/%s/" % SAFE
QUEUE = BASE + "/api/v2/safes/%s/multisig-transactions/?executed=false&nonce__gte=4&ordering=nonce&limit=3" % SAFE
CONFIRM = BASE + "/api/v1/multisig-transactions/%s/confirmations/" % H
SIG = json.dumps({"signature": "0x" + "00" * 200})


def case_check():
    check(not refused(req(INFO)) and not refused(req(QUEUE)) and not refused(req(CONFIRM, "POST", SIG)),
          "the three calls txservice makes pass: the Safe, its queue, a confirmation")
    check(not refused(req(R.services()[1] + "/api/v1/safes/%s/" % SAFE)) and not refused(req(R.services()[8453] + "/api/v1/safes/%s/" % SAFE)),
          "on every pinned service (eth, base, basesep)")
    bad = {"off the pin": "https://evil.example/api/v1/safes/%s/" % SAFE,
           "a longer name (basesepolia)": BASE + "olia/api/v1/safes/%s/" % SAFE,
           "user@host": "https://api.safe.global/tx-service/basesep@evil.example/api/v1/safes/%s/" % SAFE,
           "..": BASE + "/../eth/api/v1/safes/%s/" % SAFE, "#": INFO + "#x", "a space": INFO + " x", "\\": BASE + "/api\\v1",
           "non-ASCII": INFO + "é", "too long": INFO + "a" * R.MAX_URL, "plain http": INFO.replace("https", "http"),
           "the base alone": BASE, "another path": BASE + "/api/v1/safes/%s/balances/" % SAFE,
           "another query": QUEUE.replace("limit=3", "limit=3&x=1"), "the owners endpoint": BASE + "/api/v1/owners/%s/safes/" % SAFE,
           "a sim path on Safe's service": BASE + "/sim/device", "not a string": 5}
    out = {k: refused(req(u)) for k, u in bad.items()}
    check(all(out.values()), "refused, nothing fetched: " + ", ".join(k for k, v in out.items() if v)
          + ("; NOT refused: %s" % [k for k, v in out.items() if not v] if not all(out.values()) else ""))
    check(refused(req(INFO, "DELETE")) and refused(req(INFO, "PUT")) and refused({"t": "res", "id": 1}) and refused(req(INFO, i="7")),
          "DELETE, PUT, an answer, a string id: refused")
    check(refused(req(INFO, body="{}")) and refused(req(CONFIRM, "POST")) and refused(req(CONFIRM, "POST", "x" * 5000)),
          "a GET with a body, a POST without one, a POST body over 4 KB: refused")
    check(all(refused(req(CONFIRM, "POST", b)) for b in ("not json", json.dumps({"signature": "0x00", "extra": 1}),
                                                          json.dumps({"signature": "zz"}), json.dumps(["0x00"]))),
          "a confirmation is {\"signature\": \"0x...\"} and nothing else")
    check(refused(req(MOCK + "/api/v1/safes/%s/" % SAFE)) and not refused(req(MOCK + "/api/v1/safes/%s/" % SAFE), (MOCK,))
          and not refused(req(MOCK + "/sim/device", "POST", "{}"), (MOCK,)),
          "--allow-base: the mock's paths and its /sim endpoints, only when allowed")
    h = R.headers_for(INFO, KEY)
    check(h.get("Authorization") == "Bearer " + KEY and "Authorization" not in R.headers_for(MOCK + "/api/v1/safes/x/", KEY)
          and "Authorization" not in R.headers_for(INFO, ""), "the API key goes to api.safe.global only")
    check(R.parse_safes("basesep:%s:Test,base:%s" % (SAFE, SAFE), R.services()) ==
          [{"chainId": 84532, "address": SAFE, "name": "Test"}, {"chainId": 8453, "address": SAFE, "name": "Safe"}],
          "--safes basesep:0x..:Test,base:0x..: the safes ask's list")


class FakePort:
    def __init__(self):
        self.out = []

    def write(self, data):
        for line in data.split(b"\n")[:-1]:
            self.out.append(line)

    def lines(self):
        out = []
        for b in self.out:
            try:
                out.append(json.loads(b))
            except ValueError:
                out.append(b)
        return out


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


QUEUE_BODY = json.dumps({"count": 1, "results": [{"safe": SAFE, "to": SAFE, "value": "0", "nonce": 4, "safeTxHash": H}]})


def relay(**kw):
    d = tempfile.mkdtemp()
    calls = []

    def fetcher(method, url, body, key):
        calls.append((method, url, body, key))
        if "/multisig-transactions/?" in url:
            return 200, QUEUE_BODY
        return (201, "") if method == "POST" else (200, json.dumps({"address": SAFE, "nonce": 4}))
    p, clk = FakePort(), Clock()
    r = R.Relay(p, d, BASES, kw.pop("allowed", ()), KEY, fetcher=fetcher, clock=clk, quiet=True, **kw)
    r.hello = {"link": {"max": 49152}}
    r.max = 49152
    return r, p, calls, clk, d


def logs(d):
    return "".join(open(os.path.join(d, f)).read() for f in os.listdir(d))


def case_relay():
    r, p, calls, clk, d = relay()
    r.feed(json.dumps(req(INFO, i=3)).encode() + b"\n")
    got = p.lines()
    check(len(calls) == 1 and calls[0][:2] == ("GET", INFO) and calls[0][3] == KEY and got[-1]["id"] == 3 and got[-1]["status"] == 200
          and json.loads(got[-1]["body"])["nonce"] == 4, "a GET goes out with the key and comes back under its id")
    r.feed(json.dumps(req("https://evil.example/x", i=4)).encode() + b"\n")
    check(len(calls) == 1 and p.lines()[-1] == {"t": "res", "id": 4, "status": 0, "err": "not a pinned service"},
          "an off-pin request: status 0, nothing fetched")
    r.feed(json.dumps(req(CONFIRM, "POST", SIG, i=5)).encode() + b"\n")
    check(calls[-1][:3] == ("POST", CONFIRM, SIG) and p.lines()[-1]["status"] == 201, "a confirmation: POSTed as sent, 201 back")
    r.feed(b'{"t":"log","m":"+9s signed #4"}\n\x00garbage\n')
    rel = [json.loads(l) for l in open(os.path.join(d, "relay.jsonl"))]
    con = [json.loads(l) for l in open(os.path.join(d, "console.jsonl"))]
    check(con[-1]["m"] == "+9s signed #4" and r.counts["noise"] == 1 and any(x.get("kind") == "noise" for x in rel),
          "the console's log lines in console.jsonl; noise counted and logged")
    check(all("sha256" in x and "ms" in x for x in rel if x.get("kind") == "req") and any(x.get("kind") == "refused" for x in rel),
          "relay.jsonl: each request with its status, bytes, ms and the body's SHA-256; each refusal with why")
    every = logs(d) + "\n".join(str(x) for x in p.out)
    check(KEY not in every and "Bearer" not in every, "the API key in no log and in no line to the console")

    r.max = 200
    r.feed(json.dumps(req(QUEUE, i=6)).encode() + b"\n")
    check(p.lines()[-1]["status"] == 0 and "too big" in p.lines()[-1]["err"], "an answer longer than hello's max: status 0, too big")
    shutil.rmtree(d)

    # hello, then status every status_s; an ask with no answer is asked again
    r, p, calls, clk, d = relay(status_s=60)
    r.hello = None
    r.tick()
    hello = [x for x in p.lines() if isinstance(x, dict) and x.get("op") == "hello"]
    check(len(hello) == 1 and {"t": "hi"} in p.lines(), "at start: hi, and hello")
    clk.t += 4
    r.tick()
    hello2 = [x for x in p.lines() if isinstance(x, dict) and x.get("op") == "hello"]
    check(len(hello2) == 2 and hello2[1]["id"] != hello2[0]["id"], "no answer in 3 s: hello again, under a new id")
    r.feed(json.dumps({"pq": 1, "id": hello2[1]["id"], "ok": True, "image": "console-rp", "link": {"max": 30000}}).encode() + b"\n")
    r.tick()
    st = [x for x in p.lines() if isinstance(x, dict) and x.get("op") == "status"]
    check(r.max == 30000 and len(st) == 1, "hello's answer: answers up to its link.max; then status")
    r.feed(json.dumps({"pq": 1, "id": st[0]["id"], "ok": True, "serial": "01234ed5a949900dee", "state": "home"}).encode() + b"\n")
    check(r.serial == "01234ed5a949900dee" and json.loads(open(os.path.join(d, "status.jsonl")).readline())["status"]["state"] == "home",
          "status's answer in status.jsonl")
    shutil.rmtree(d)
    base = tempfile.mkdtemp()
    d = os.path.join(base, "20261104-120000-relay")
    rr = R.Relay(FakePort(), d, BASES, (), KEY, fetcher=lambda *a: (200, "{}"), clock=Clock(), quiet=True, rename=True)
    rr.asks[5] = ("status", 1000.0, {})
    rr.feed(json.dumps({"pq": 1, "id": 5, "serial": "01234ed5a949900dee"}).encode() + b"\n")
    rr.log("relay", kind="after")
    check(rr.run_dir.endswith("-01234ed5a949900dee") and os.path.exists(os.path.join(rr.run_dir, "relay.jsonl"))
          and "after" in open(os.path.join(rr.run_dir, "relay.jsonl")).read(), "the run's folder takes the serial, the open logs with it")
    shutil.rmtree(base)

    # each fault, and what reaches the console
    def faulted(fault, url=QUEUE, i=20):
        r, p, calls, clk, d = relay(hostile=[fault], rate=1.0, seed=1)
        r.feed(json.dumps(req(url, i=i)).encode() + b"\n")
        out = p.lines()
        rec = [json.loads(l) for l in open(os.path.join(d, "relay.jsonl"))]
        shutil.rmtree(d)
        return r, out, rec
    r, out, rec = faulted("garbage")
    check(len(out) == 5 and out[-1]["id"] == 20 and rec[-1]["fault"] == "garbage" and "garbage" in rec[-1]["expect"],
          "garbage: four junk lines, then the answer; logged with what should happen")
    r, out, rec = faulted("overlong")
    check(len(out) == 2 and isinstance(out[0], dict) and len(json.dumps(out[0])) > 49152 and out[-1]["id"] == 20,
          "overlong: one line past max, then the answer")
    r, out, rec = faulted("wrong-id")
    check([x["id"] for x in out] == [27, 20], "wrong-id: the answer under id+7, then under its own")
    r, out, rec = faulted("dup")
    check(len(out) == 2 and out[0] == out[1], "dup: the same answer twice")
    r, out, rec = faulted("stall")
    check(out == [] and rec[-1]["fault"] == "stall", "stall: nothing sent")
    r, out, rec = faulted("truncate")
    check(len(out) == 1 and len(out[0]["body"]) == len(QUEUE_BODY) // 2, "truncate: half the body")
    r, out, rec = faulted("nested")
    check(out[0]["body"] == "[" * 5000, "nested: a body 5000 deep")
    r, out, rec = faulted("forge-queue")
    q = json.loads(out[0]["body"])["results"][0]
    check(q["value"] == str(10 ** 18) and q["safeTxHash"] == H, "forge-queue: the value changed, the hash kept")
    r, p, calls, clk, d = relay(hostile=["late"], rate=1.0, seed=1)
    r.feed(json.dumps(req(QUEUE, i=30)).encode() + b"\n")
    held = list(p.lines())
    r.hostile = []
    r.feed(json.dumps(req(QUEUE, i=31)).encode() + b"\n")
    out = p.lines()
    check(held == [] and [x["id"] for x in out] == [30, 31], "late: nothing now, then the held answer before the next one")
    shutil.rmtree(d)
    r, p, calls, clk, d = relay(hostile=["stall", "truncate"], rate=1.0, seed=1)
    r.feed(json.dumps(req(CONFIRM, "POST", SIG, i=40)).encode() + b"\n")
    check(p.lines()[-1]["id"] == 40 and p.lines()[-1]["status"] == 201, "stall and truncate are GET faults: a POST goes through")
    shutil.rmtree(d)


def main():
    for case in (case_check, case_relay):
        print("--", case.__name__[5:])
        case()
    print("relay: all pass" if not failed[0] else "relay: %d FAILED" % failed[0])
    return 1 if failed[0] else 0


if __name__ == "__main__":
    sys.exit(main())
