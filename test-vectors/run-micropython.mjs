// The same vectors under real MicroPython 1.26 (WebAssembly, from emu/), so safe_tx.py is known to
// run on the Pico and not only on CPython.
//   (cd emu && npm install) && node test-vectors/run-micropython.mjs
import { readFileSync } from "node:fs";
import { loadMicroPython } from "../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";

const root = new URL("..", import.meta.url);
const mp = await loadMicroPython({ stdout: (l) => console.log(l) });
for (const f of ["keccak.py", "safe_tx.py"]) mp.FS.writeFile("/" + f, readFileSync(new URL("firmware/" + f, root)));
mp.FS.writeFile("/safe_tx.json", readFileSync(new URL("test-vectors/safe_tx.json", root)));
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
_failed = bad
`);
process.exit(mp.globals.get("_failed") ? 1 : 0);
