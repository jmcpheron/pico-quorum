# Run a MicroPython file on a bench console-rp through the raw REPL that main_repl.py puts on the
# USB-C's serial port. No soft reset (mpremote's): a soft reset drops the REPL off UART1 and only a
# hard reset (RESET, or probe-rs reset) brings it back.
#
#   uv run --no-project --with pyserial==3.5 python hardware/console-rp/bench/rawrepl.py PORT FILE [--follow S]
#
# Without --follow it waits for FILE to finish (at most 60 s) and prints what it printed. With
# --follow S it starts FILE, prints S seconds of its output and leaves it running.
import sys
import time
import serial


def main(argv):
    follow = None
    if "--follow" in argv:
        i = argv.index("--follow")
        follow = float(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    port, path = argv
    s = serial.Serial(port, 115200, timeout=0.2)
    s.write(b"\r\x03\x03")
    time.sleep(0.3)
    s.read(4096)
    s.write(b"\x01")                    # raw REPL
    time.sleep(0.3)
    got = s.read(4096)
    if b"raw REPL" not in got:
        sys.exit("no raw REPL on %s: %r (is main_repl.py the board's main.py?)" % (port, got[-80:]))
    code = open(path, "rb").read()
    for i in range(0, len(code), 64):
        s.write(code[i:i + 64])
        time.sleep(0.01)
    s.write(b"\x04")                    # run it
    out, t = b"", time.time()
    while time.time() - t < (follow if follow is not None else 60):
        out += s.read(4096)
        if follow is None and out.count(b"\x04") >= 2:
            break
    if follow is None:
        s.write(b"\x02")                # back to the friendly REPL
    body = out.partition(b"OK")[2]
    res, _, err = body.partition(b"\x04")
    sys.stdout.write(res.decode("latin1"))
    err = err.strip(b"\x04>")
    if err:
        sys.exit("error: " + err.decode("latin1"))


if __name__ == "__main__":
    main(sys.argv[1:])
