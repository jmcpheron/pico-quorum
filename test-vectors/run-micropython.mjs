// The same vectors under real MicroPython 1.26 (WebAssembly, from emu/), so safe_tx.py,
// decode.py and webauthn.py are known to run on the Pico and not only on CPython.
//   (cd emu && npm install) && node test-vectors/run-micropython.mjs
import { readFileSync } from "node:fs";
import { loadMicroPython } from "../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";

const root = new URL("..", import.meta.url);
const mp = await loadMicroPython({ stdout: (l) => console.log(l) });
for (const f of ["keccak.py", "safe_tx.py", "decode.py", "quorum_cfg.py", "webauthn.py", "release.py"]) mp.FS.writeFile("/" + f, readFileSync(new URL("firmware/" + f, root)));
for (const f of ["safe_tx.json", "webauthn.json", "passkey.json", "release.json", "webauthn_check.py", "release_check.py"]) mp.FS.writeFile("/" + f, readFileSync(new URL("test-vectors/" + f, root)));
mp.runPython(`
import sys, json, safe_tx
vs = json.load(open("/safe_tx.json"))["vectors"]
bad = 0
for v in vs:
    t = v["tx"]
    h = safe_tx.safe_tx_hash(v["chainId"], v["safe"], t["to"], t["value"], t["data"], t["operation"],
                             t["safeTxGas"], t["baseGas"], t["gasPrice"], t["gasToken"], t["refundReceiver"], t["nonce"])
    ok = ("0x" + "".join("%02x" % b for b in h)) == v["safeTxHash"].lower()
    bad += not ok
    print("pass" if ok else "FAIL", v["name"])
print("%s: %d/%d vectors pass" % (sys.version, len(vs) - bad, len(vs)))

import decode, quorum_cfg
from keccak import keccak256
for sel, sig in decode.SIGS.items():
    if "".join("%02x" % b for b in keccak256(sig.encode())[:4]) != sel:
        bad += 1
        print("FAIL selector", sel, sig)
n = 0
for v in vs:
    got = decode.review(v["tx"], decode.context(quorum_cfg.CFG, v["safe"]))
    if "expect" not in v:
        continue
    n += 1
    ok = got["summary"] == v["expect"]["summary"] and [[i["title"], i["level"]] for i in got["items"]] == v["expect"]["items"]
    bad += not ok
    print("pass" if ok else "FAIL", "decode", v["name"], got["summary"][:40])
print("decode: %d expectations, %d selectors" % (n, len(decode.SIGS)))

import webauthn_check
bad += webauthn_check.check("/webauthn.json")
bad += webauthn_check.check_passkey("/passkey.json")
import release_check
bad += release_check.check("/release.json")
_failed = bad
`);
process.exit(mp.globals.get("_failed") ? 1 : 0);
