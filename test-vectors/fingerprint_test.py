"""The release fingerprint, computed here with hashlib from firmware/manifest.json and compared
with tools/release/fingerprint.mjs (which tools/fw build, the emulator and the web builds use).
Two implementations of one definition: sha256 over "name\\0sha256hex\\n" lines, sorted by name.
    python3 test-vectors/fingerprint_test.py"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "firmware"
failed = 0


def check(ok, what):
    global failed
    print(("pass  " if ok else "FAIL  ") + what)
    failed += not ok


def fingerprint(names, read):
    lines = "".join("%s\0%s\n" % (n, hashlib.sha256(read(n)).hexdigest()) for n in sorted(set(names)))
    return hashlib.sha256(lines.encode()).hexdigest()


m = json.loads((FW / "manifest.json").read_text())
mine = {img: fingerprint(spec["files"], lambda n: (FW / n).read_bytes()) for img, spec in m["images"].items()}
out = subprocess.run(["node", str(ROOT / "tools/release/fingerprint.mjs")], capture_output=True, text=True, check=True).stdout
theirs = {l.split()[0]: l.split()[1] for l in out.splitlines() if l.strip()}
for img, fp in mine.items():
    check(theirs.get(img) == fp, "%s: %s" % (img, fp))

# The definition, pinned on a tiny made-up image, both sides, so a change to either one shows.
files = {"b.py": b"print(2)\n", "a.bin": b"\x00\x01", "main_x.py": b""}
PINNED = "7173a8d9700f74ceff3678b90232b2fa8b1d8efe1d5c88df9078bbad9b184cd6"
check(fingerprint(files, files.get) == PINNED, "made-up image, here")
js = ("import {fingerprint} from %s; const f = {'b.py': 'print(2)\\n', 'a.bin': Buffer.from([0, 1]), 'main_x.py': ''};"
      "console.log(fingerprint(Object.keys(f), (n) => f[n]))") % json.dumps((ROOT / "tools/release/fingerprint.mjs").as_uri())
out = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True).stdout.strip()
check(out == PINNED, "made-up image, tools/release/fingerprint.mjs")
# Order and duplicates do not matter; content and names do.
check(fingerprint(["b.py", "a.bin", "b.py"], files.get) == fingerprint(["a.bin", "b.py"], files.get), "order and duplicates ignored")
check(fingerprint(["a.bin"], files.get) != fingerprint(["a.bin"], {"a.bin": b"\x00\x02"}.get), "content changes it")
sys.exit(1 if failed else 0)
