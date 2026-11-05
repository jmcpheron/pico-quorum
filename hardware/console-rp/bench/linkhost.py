# The computer's half of linkbench.py: at 460800 on the console-rp's USB-C port, it answers each CASE
# with one line of the size asked for (8 hex digits of CRC-32, a space, then printable bytes, then a
# newline), checks the lines the board sends back, and prints a table. Every line each way goes into
# hardware/console-rp/bench/runs/<time>-linkbench/link.jsonl (gitignored).
#
#   uv run --no-project --with pyserial==3.5 python hardware/console-rp/bench/linkhost.py PORT
import json
import os
import random
import string
import sys
import time
import zlib
import serial

HERE = os.path.dirname(os.path.abspath(__file__))
ABC = (string.ascii_letters + string.digits + "+/").encode()


def main(port):
    run = os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-linkbench")
    os.makedirs(run, exist_ok=True)
    log = open(os.path.join(run, "link.jsonl"), "w")
    t0 = time.time()

    def note(d, **kv):
        log.write(json.dumps(dict(t=round(time.time() - t0, 3), d=d, **kv)) + "\n")

    s = serial.Serial(port, 460800, timeout=0.05)
    s.reset_input_buffer()
    buf = b""

    def line(wait=90):
        nonlocal buf
        end = time.time() + wait
        while time.time() < end:
            i = buf.find(b"\n")
            if i >= 0:
                ln, buf = buf[:i], buf[i + 1:]
                return ln.rstrip(b"\r")
            buf += s.read(65536)
        return None

    while True:                         # the board says READY every half second until GO
        ln = line(60)
        if ln is None:
            sys.exit("no READY from the board in 60 s")
        if ln == b"READY":
            break
    s.write(b"GO\n")
    note("out", m="GO")
    res, sent, free, rng = {}, [], [], random.Random(1)
    while True:
        ln = line()
        if ln is None:
            sys.exit("the board went quiet")
        if len(ln) > 64 and ln[8:9] == b" ":        # a line the board wrote
            ok = "%08x" % (zlib.crc32(ln[9:]) & 0xFFFFFFFF) == ln[:8].decode("ascii", "replace")
            sent.append({"len": len(ln), "ok": ok})
            note("in", kind="payload", len=len(ln), ok=ok)
            continue
        txt = ln.decode("ascii", "replace")
        note("in", m=txt[:200])
        w = txt.split()
        if not w:
            continue
        if w[0] == "CASE":
            size = int(w[3])
            body = bytes(rng.choice(ABC) for _ in range(size - 9))
            s.write(b"%08x " % (zlib.crc32(body) & 0xFFFFFFFF) + body + b"\n")
            note("out", kind="payload", case=txt, len=size)
        elif w[0] == "RES":
            k = (int(w[1]), w[2], int(w[3]))
            res.setdefault(k, []).append((w[5] == "ok", int(w[6])))
        elif w[0] == "SENT":
            sent[-1]["ms"] = int(w[3]) if sent else None
        elif w[0] == "FREE":
            free.append((int(w[1]), int(w[2]) // 1024))
        elif w[0] == "DONE":
            break
    print("lines to the board at 460800 (ok of %d; bytes the board had when it stopped)" % len(next(iter(res.values()))))
    print("%7s %6s %7s  %s" % ("rxbuf", "while", "line", "result"))
    for (rx, cond, size), v in sorted(res.items()):
        oks = sum(1 for o, _ in v if o)
        print("%7d %6s %7d  %d ok  %s" % (rx, cond, size, oks, " ".join(str(n) for _, n in v)))
    print("lines from the board:", ", ".join("%d B %s %s ms" % (x["len"], "ok" if x["ok"] else "BAD", x.get("ms")) for x in sent))
    print("heap after each rxbuf:", ", ".join("%d: %d KB" % f for f in free))
    json.dump({"res": {"%d %s %d" % k: v for k, v in res.items()}, "sent": sent, "free": free}, open(os.path.join(run, "summary.json"), "w"), indent=1)
    print("log:", run)


if __name__ == "__main__":
    main(sys.argv[1])
