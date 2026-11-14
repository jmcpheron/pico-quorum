# Load a console-rp over SWD: MicroPython from its UF2, and files into MicroPython's own filesystem.
# The board's USB-C can't do it (it reaches only the CH343P), and J3's USB pins are only holes, so the
# debug probe is the way in. BRINGUP.md has the whole story.
#
#   uv run --no-project --with littlefs-python==0.19.0 python hardware/console-rp/bench/swdload.py \
#       RPI_PICO2-20250911-v1.26.1.uf2 main.py=hardware/console-rp/bench/stage0.py [--no-micropython] [--dry-run]
#   ... swdload.py --no-micropython --image build/console-rp-<sha> [--dirty-ok] [--dev] [--secrets PATH]
#   ... swdload.py --dump DIR       read only: the files a push keeps (the manifest's preserve), secrets left out
#   ... swdload.py --no-micropython --image DIR --keep DUMP   a new image, the dumped files carried back
#
# Each NAME=PATH goes into the filesystem as /NAME. --image DIR puts in a `tools/fw build console-rp`
# directory, each file first checked against its build.py's FILES. It refuses a build of uncommitted
# firmware unless --dirty-ok. --dev leaves build.py out (a development board: PRODUCTION off, and
# the board named by secrets.BOARD); --secrets PATH adds a bench secrets.py, which stays out of the
# repository. Needs probe-rs on the PATH (brew install probe-rs-tools) and a CMSIS-DAP probe on J3's
# CLK, DIO and GND. It writes the RP2350's flash only: nothing here talks to the key. The whole
# filesystem is new each time: what was on the board before is gone. --keep DUMP puts back each file
# a --dump wrote (a pinned board's pin.json, keyflow.json, safes.json, counter and logs): without it a
# pinned board loses its pin.
import fnmatch
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import time

# The MicroPython the first board was loaded with (micropython.org/download/RPI_PICO2, 2026-11-04).
UF2_SHA256 = {"0616a3a4298a3c32c9092b71a431867dafcb4250f467245bcf2b6fe9704e4548": "RPI_PICO2 v1.26.1"}
FAMILY_ARM = 0xE48BFF59         # RP2350, Arm, secure: MicroPython's own blocks
XIP = 0x10000000
# MicroPython's rp2 filesystem on a Pico 2 (ports/rp2: PICO_FLASH_SIZE_BYTES 4 MB, storage = all but the
# first 1 MB): littlefs v2, 4 KB blocks, 256-byte programming (_boot.py), readsize and lookahead 32.
FS_BASE, FS_BLOCKS, BLOCK = XIP + 0x100000, 768, 4096
CHUNK = 32                      # blocks per read in --dump, and per write: 128 KB
PROBE = ["probe-rs"]
CHIP = ["--chip", "RP235x", "--protocol", "swd"]


def micropython_bin(path):
    """The UF2's Arm blocks as one image from 0x10000000. -> bytes. Other families are left out: the
    file also carries one block for 0x10ffff00 (family 0xe48bff57), which is for a UF2 copied to the
    boot drive, not part of MicroPython."""
    b = open(path, "rb").read()
    h = hashlib.sha256(b).hexdigest()
    if h not in UF2_SHA256:
        sys.exit("%s: sha256 %s is not a UF2 this script knows (UF2_SHA256)" % (path, h))
    img = {}
    for i in range(0, len(b), 512):
        m0, m1, flags, addr, size, n, total, fam = struct.unpack("<8I", b[i:i + 32])
        if m0 != 0x0A324655 or m1 != 0x9E5D5157:
            sys.exit("%s: block %d is not UF2" % (path, i // 512))
        if fam == FAMILY_ARM:
            img[addr] = b[i + 32:i + 32 + size]
    lo, hi = min(img), max(a + len(d) for a, d in img.items())
    if lo != XIP:
        sys.exit("the image starts at %#x, not %#x" % (lo, XIP))
    out = bytearray(b"\xff" * (hi - lo))
    for a, d in img.items():
        out[a - lo:a - lo + len(d)] = d
    print("%s (%s): %d bytes for %#x" % (os.path.basename(path), UF2_SHA256[h], len(out), lo))
    return bytes(out)


def filesystem(files):
    """A littlefs with these (name, path) files. -> [(address, bytes)]: every block of it, the unused
    ones erased, in CHUNK pieces. Each directory is a pair of blocks, and littlefs reads the pair's
    newer half: a block this image leaves blank would keep what the old filesystem had there, and an
    old directory block won (board #2, 2026-11-08: block 602 brought back the empty safes.json.tmp of
    an earlier write, and safes.json was gone). Writing only the blocks with data was 400 KB, not 3 MB."""
    from littlefs import LittleFS
    fs = LittleFS(block_size=BLOCK, block_count=FS_BLOCKS, prog_size=256, read_size=32, lookahead_size=32,
                  disk_version=0x00020000)
    for name, path in files:
        with fs.open(name, "wb") as f:
            f.write(open(path, "rb").read())
        print("  /%s  %d bytes  sha256 %s" % (name, os.path.getsize(path), hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]))
    data = bytes(fs.context.buffer)
    return [(FS_BASE + a * BLOCK, data[a * BLOCK:(a + CHUNK) * BLOCK]) for a in range(0, FS_BLOCKS, CHUNK)]


def image_files(d, dirty_ok=False, dev=False, secrets=None):
    """A tools/fw build directory as (name, path) pairs, every file checked against build.py's FILES
    (each one's SHA-256, first 12 hex digits) and none missing or extra."""
    import ast
    vals = {}
    for line in open(os.path.join(d, "build.py")).read().splitlines():
        k, sep, v = line.partition(" = ")
        if sep and k.isupper():
            vals[k] = ast.literal_eval(v)
    want = vals.get("FILES") or sys.exit("%s/build.py has no FILES" % d)
    if vals.get("BUILD", "").endswith("+dirty") and not dirty_ok:
        sys.exit("%s is a build of uncommitted firmware (%s): commit, build again, or pass --dirty-ok" % (d, vals["BUILD"]))
    names = sorted(n for n in os.listdir(d) if n != "build.py")
    if set(names) != set(want):
        sys.exit("%s differs from its build.py: extra %s, missing %s" % (d, sorted(set(names) - set(want)), sorted(set(want) - set(names))))
    for n in names:
        if hashlib.sha256(open(os.path.join(d, n), "rb").read()).hexdigest()[:12] != want[n]:
            sys.exit("%s/%s no longer matches build.py" % (d, n))
    print("image %s %s, build %s, release %s, %d files%s" % (vals.get("IMAGE"), vals.get("VERSION"), vals.get("BUILD"),
                                                             vals.get("RELEASE", "")[:8], len(names), ", dev: no build.py" if dev else ""))
    out = [(n, os.path.join(d, n)) for n in names]
    if not dev:
        out.append(("build.py", os.path.join(d, "build.py")))
    if secrets:
        out.append(("secrets.py", secrets))
    return out


PAUSES = (2, 5, 10, 20)     # between tries of one piece: a dropped pogo pin came back within a minute (2026-11-10)


def download(addr, blob, dry):
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(blob)
    cmd = PROBE + ["download"] + CHIP + ["--binary-format", "bin", "--base-address", hex(addr), "--verify", f.name]
    print("  %#x  %d bytes" % (addr, len(blob)))
    try:
        for tries in range(len(PAUSES) + 1 if not dry else 0):     # pogo pins drop out mid-write too; --verify says so
            if subprocess.run(cmd).returncode == 0:
                break
            if tries < len(PAUSES):
                print("  %#x: download failed; again in %d s (press J3's pins down)" % (addr, PAUSES[tries]))
                time.sleep(PAUSES[tries])
        else:
            if not dry:
                sys.exit("the write over SWD keeps failing: check J3's pins, then load again (the whole filesystem)")
    finally:
        os.unlink(f.name)


MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "firmware", "manifest.json")
NEVER_OUT = ("secrets*", "wifi.json*")      # a development board's secrets and a Wi-Fi password stay on it


def kept():
    """The files a dump copies out and --keep puts back: the manifest's preserve list (what tools/fw push
    keeps on a board) and the ceremony's key-log.txt, less NEVER_OUT."""
    return json.load(open(MANIFEST))["preserve"] + ["key-log.txt"]


def keeps(name):
    return any(fnmatch.fnmatchcase(name, p) for p in kept()) and not any(fnmatch.fnmatchcase(name, p) for p in NEVER_OUT)


def keep_files(d):
    """A --dump directory's files as (name, path) pairs: each one the board kept, files.txt left out."""
    out = []
    for n in sorted(os.listdir(d)):
        if n == "files.txt":
            continue
        if not keeps(n):
            sys.exit("%s/%s is not a file a board keeps (or never leaves it): not carried" % (d, n))
        out.append((n, os.path.join(d, n)))
    if not out:
        sys.exit("%s holds no dumped files" % d)
    return out


def dump(out):
    """Read only. The filesystem over SWD, then from it only the files a board keeps (keeps) into out,
    and a list of every file with its size. The raw image is read into a temporary file and deleted: on
    a development board the filesystem holds a secrets.py, and nothing NEVER_OUT names is copied out."""
    from littlefs import LittleFS
    os.makedirs(out, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        raw = f.name
    try:
        data = bytearray()
        for i in range(0, FS_BLOCKS, CHUNK):     # in pieces, each tried again: pogo pins drop out mid-read
            n = min(CHUNK, FS_BLOCKS - i) * BLOCK
            for tries in range(5):
                r = subprocess.run(PROBE + ["read"] + CHIP + ["b8", hex(FS_BASE + i * BLOCK), str(n), "--output", raw,
                                                               "--format", "binary"], capture_output=True, text=True)
                if r.returncode == 0 and os.path.getsize(raw) == n:
                    break
                print("  blocks %d-%d: read failed, again (%s)" % (i, i + n // BLOCK - 1, r.stderr.strip().splitlines()[-1:]))
            else:
                sys.exit("the read over SWD keeps failing: check J3's pins")
            data += open(raw, "rb").read()
    finally:
        os.unlink(raw)
    fs = LittleFS(block_size=BLOCK, block_count=FS_BLOCKS, prog_size=256, read_size=32, lookahead_size=32, mount=False)
    fs.context.buffer = bytearray(data)
    fs.mount()
    names = sorted(fs.listdir("/"))
    with open(os.path.join(out, "files.txt"), "w") as f:
        for n in names:
            f.write("%8d  %s\n" % (fs.stat(n).size, n))
    for n in names:
        if keeps(n):
            with fs.open(n, "rb") as src, open(os.path.join(out, n), "wb") as dst:
                dst.write(src.read())
            print("  %s  %d bytes" % (n, fs.stat(n).size))
    print("%d files on the board; listed in %s/files.txt" % (len(names), out))


def option(argv, name):
    """The value after --name, taken out of argv; None when it isn't there."""
    if name not in argv:
        return None
    i = argv.index(name)
    if i + 1 >= len(argv):
        sys.exit("%s needs a value" % name)
    v = argv[i + 1]
    del argv[i:i + 2]
    return v


def main(argv):
    argv = list(argv)
    out = option(argv, "--dump")
    if out:
        return dump(out)
    image, secrets, keep = option(argv, "--image"), option(argv, "--secrets"), option(argv, "--keep")
    dry = "--dry-run" in argv
    skip_mp = "--no-micropython" in argv
    args = [a for a in argv if not a.startswith("--")]
    if skip_mp and args and "=" not in args[0]:
        args = args[1:]                 # a UF2 named but not loaded
    if not skip_mp and not args:
        sys.exit("usage: swdload.py UF2 NAME=PATH ... (or --no-micropython --image DIR)")
    uf2 = None if skip_mp else args[0]
    files = [tuple(a.split("=", 1)) for a in (args if skip_mp else args[1:])]
    if any(len(f) != 2 for f in files):
        sys.exit("files are NAME=PATH")
    if image:
        files = image_files(image, "--dirty-ok" in argv, "--dev" in argv, secrets) + files
    elif secrets:
        files.append(("secrets.py", secrets))
    if keep:
        files += keep_files(keep)
    if len(set(n for n, _ in files)) != len(files):
        sys.exit("a name twice: %s" % [n for n, _ in files])
    if not dry:
        subprocess.run(PROBE + ["info", "--protocol", "swd"], check=False, capture_output=True)
    if not skip_mp:
        download(XIP, micropython_bin(uf2), dry)
    if files:
        print("filesystem:")
        for addr, blob in filesystem(files):
            download(addr, blob, dry)
    if not dry:
        subprocess.run(PROBE + ["reset"] + CHIP, check=True)
        print("reset: the board starts MicroPython, then /main.py")


if __name__ == "__main__":
    main(sys.argv[1:])
