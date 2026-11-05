# Load a console-rp over SWD: MicroPython from its UF2, and files into MicroPython's own filesystem.
# The board's USB-C can't do it (it reaches only the CH343P), and J3's USB pins are only holes, so the
# debug probe is the way in. BRINGUP.md has the whole story.
#
#   uv run --no-project --with littlefs-python==0.19.0 python hardware/console-rp/bench/swdload.py \
#       RPI_PICO2-20250911-v1.26.1.uf2 main.py=hardware/console-rp/bench/stage0.py [--no-micropython] [--dry-run]
#   ... swdload.py --no-micropython --image build/console-rp-<sha> [--dirty-ok] [--dev] [--secrets PATH]
#
# Each NAME=PATH goes into the filesystem as /NAME. --image DIR puts in a `tools/fw build console-rp`
# directory, each file first checked against its build.py's FILES. It refuses a build of uncommitted
# firmware unless --dirty-ok. --dev leaves build.py out (a development board: PRODUCTION off, and
# the board named by secrets.BOARD); --secrets PATH adds a bench secrets.py, which stays out of the
# repository. Needs probe-rs on the PATH (brew install probe-rs-tools) and a CMSIS-DAP probe on J3's
# CLK, DIO and GND. It writes the RP2350's flash only: nothing here talks to the key. The whole
# filesystem is new each time: what was on the board before is gone.
import hashlib
import os
import struct
import subprocess
import sys
import tempfile

# The MicroPython the first board was loaded with (micropython.org/download/RPI_PICO2, 2026-11-04).
UF2_SHA256 = {"0616a3a4298a3c32c9092b71a431867dafcb4250f467245bcf2b6fe9704e4548": "RPI_PICO2 v1.26.1"}
FAMILY_ARM = 0xE48BFF59         # RP2350, Arm, secure: MicroPython's own blocks
XIP = 0x10000000
# MicroPython's rp2 filesystem on a Pico 2 (ports/rp2: PICO_FLASH_SIZE_BYTES 4 MB, storage = all but the
# first 1 MB): littlefs v2, 4 KB blocks, 256-byte programming (_boot.py), readsize and lookahead 32.
FS_BASE, FS_BLOCKS, BLOCK = XIP + 0x100000, 768, 4096
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
    """A littlefs with these (name, path) files. -> [(address, bytes)]: blocks 0 and 1 (the superblock
    pair, always, so an older filesystem's pair can't win) and every block that holds data."""
    from littlefs import LittleFS
    fs = LittleFS(block_size=BLOCK, block_count=FS_BLOCKS, prog_size=256, read_size=32, lookahead_size=32,
                  disk_version=0x00020000)
    for name, path in files:
        with fs.open(name, "wb") as f:
            f.write(open(path, "rb").read())
        print("  /%s  %d bytes  sha256 %s" % (name, os.path.getsize(path), hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]))
    data = bytes(fs.context.buffer)
    keep = [i for i in range(FS_BLOCKS) if i < 2 or data[i * BLOCK:(i + 1) * BLOCK] != b"\xff" * BLOCK]
    runs = []
    for i in keep:
        if runs and runs[-1][1] == i:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1])
    return [(FS_BASE + a * BLOCK, data[a * BLOCK:b * BLOCK]) for a, b in runs]


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


def download(addr, blob, dry):
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(blob)
    cmd = PROBE + ["download"] + CHIP + ["--binary-format", "bin", "--base-address", hex(addr), "--verify", f.name]
    print("  %#x  %d bytes" % (addr, len(blob)))
    try:
        if not dry:
            subprocess.run(cmd, check=True)
    finally:
        os.unlink(f.name)


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
    image, secrets = option(argv, "--image"), option(argv, "--secrets")
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
