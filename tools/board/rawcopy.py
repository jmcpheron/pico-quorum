# A tools/fw build directory onto an ESP32-S3 at bare MicroPython's REPL (a new board after
# newboard.py --flash, or one in maintenance), over plain serial with DTR and RTS low. tools/fw push
# goes through mpremote, which wedges on these boards: their USB drops the front of a long write.
# This writes in newboard.py's 64-byte raw-paste pieces instead. Each file goes to NAME.tmp, its
# SHA-256 is computed on the board and compared with this one's, and only then renamed to NAME.
# boot.py and main.py go last, so a restart mid-copy lands at the REPL, not in half a console.
#
#   uv run --no-project --with pyserial==3.5 python tools/board/rawcopy.py build/console-<sha> [--reset]
#
# A dropout: it waits for the port, reopens it, and goes on from the file that failed. --reset
# restarts the board at the end. It deletes nothing on the board, and never touches the chip.
import binascii, hashlib, os, sys, time

import serial

import newboard

src = sys.argv[1]
names = sorted(n for n in os.listdir(src) if os.path.isfile(os.path.join(src, n)))
names = [n for n in names if n not in ("boot.py", "main.py")] + [n for n in ("boot.py", "main.py") if n in names]


def run(s, code, wait=20):
    """Code from RAM; its stdout and stderr."""
    newboard.raw_paste(s, code)
    out, end = b"", time.time() + wait
    while time.time() < end and out.count(b"\x04") < 2:
        out += s.read(4096)
    if out.count(b"\x04") < 2:
        raise OSError("no end from the board: %r" % out[-120:])
    so, se = out.split(b"\x04")[:2]
    return so.decode(errors="replace").strip(), se.decode(errors="replace").strip()


def one(s, n):
    data = open(os.path.join(src, n), "rb").read()
    want = hashlib.sha256(data).hexdigest()
    name = n.encode()
    code = (b"import binascii, hashlib, os\n"
            b"d = binascii.a2b_base64(b'" + binascii.b2a_base64(data, newline=False) + b"')\n"
            b"f = open('" + name + b".tmp', 'wb'); f.write(d); f.close(); del d\n"
            b"h = hashlib.sha256(); f = open('" + name + b".tmp', 'rb')\n"
            b"while True:\n"
            b"    c = f.read(2048)\n"
            b"    if not c: break\n"
            b"    h.update(c)\n"
            b"f.close(); x = binascii.hexlify(h.digest()).decode()\n"
            b"if x == '" + want.encode() + b"':\n"
            b"    os.rename('" + name + b".tmp', '" + name + b"')\n"
            b"print('H', x)\n")
    so, se = run(s, code)
    if se or ("H " + want) not in so:
        raise ValueError("%s: the board said %r %r" % (n, so[-80:], se[-200:]))
    return len(data)


def main():
    dev, _ = newboard.find(None, 15)
    if not dev:
        raise SystemExit("no ESP32-S3 on USB")
    s, i, tries, t0, total = newboard.opened(dev), 0, 0, time.time(), 0
    while i < len(names):
        n = names[i]
        try:
            total += one(s, n)
            print("  %2d/%d  %-20s ok" % (i + 1, len(names), n))
            i, tries = i + 1, 0
        except (OSError, serial.SerialException, ValueError) as e:
            tries += 1
            print("  %2d/%d  %-20s again (%d): %s" % (i + 1, len(names), n, tries, str(e)[:120]))
            if tries > 4:
                raise SystemExit("gave up on %s" % n)
            try:
                s.close()
            except (OSError, serial.SerialException):
                pass
            time.sleep(2)
            dev, _ = newboard.find(None, 30)
            if not dev:
                raise SystemExit("the board is off USB: press RESET, and run this again")
            s = newboard.opened(dev)
    # one name a line: a long print loses its front on this USB, as a long write does
    so, _ = run(s, b"import os\nfor n in os.listdir():\n    print(n)\n")
    have = set(l.strip() for l in so.splitlines() if l.strip())
    print("copied %d files, %d bytes, in %.0f s; each hash checked on the board" % (len(names), total, time.time() - t0))
    print("missing on the board:", ", ".join(sorted(set(names) - have)) or "none")
    print("on the board, not in the build:", ", ".join(sorted(have - set(names))) or "none")
    if "--reset" in sys.argv:
        newboard.raw_paste(s, b"import machine; machine.reset()\n")
        print("restarted")
    try:
        s.write(b"\x02")
        s.close()
    except (OSError, serial.SerialException):
        pass


if __name__ == "__main__":
    main()
