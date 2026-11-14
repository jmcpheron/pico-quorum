# console-rp bench: how the link on UART1 holds up at 460800, before link.py is written. Bench only,
# like main_repl.py; it never opens the key's bus.
#   1. json: a 40 KB Safe queue answer wrapped as the relay sends it ({"t":"res",...,"body":"<json>"}),
#      parsed twice (the envelope, then its body): the time and the heap it takes. Printed over the REPL.
#   2. uart: the REPL leaves UART1 (os.dupterm(None)) and UART1 runs at 460800 with no flow control (the
#      CH343P's RTS/CTS go nowhere). linkhost.py on the computer sends lines of 1, 16 and 40 KB, each with
#      its CRC, for three rxbuf sizes, while this side is idle, hashing (safe_tx_hash, 564 ms) or writing
#      flash (littlefs; the RP2350 stops interrupts while it erases and programs, and the UART's FIFO is
#      32 bytes). Then lines the other way. Each result goes back to linkhost.py as a line.
#   rawrepl.py PORT linkbench.py --follow 3, then linkhost.py PORT at once; probe-rs reset after.
import gc
import os
import sys
import time
import json
import binascii
import machine
from machine import UART, Pin

BAUD = 460800
RXBUFS = (4096, 16384, 32768)
SIZES = (1024, 16384, 40960)
CONDS = ("idle", "hash", "flash")
REPS = 3


def largest():
    gc.collect()
    for kb in range(480, 0, -4):
        try:
            b = bytearray(kb * 1024)
            del b
            gc.collect()
            return kb
        except MemoryError:
            pass
    return 0


# ----------------------------------------------------------------------------- 1. the double parse
def queue_body(want):
    """A v2 multisig-transactions answer of about `want` bytes, shaped like Safe's."""
    one = {"safe": "0x" + "ab" * 20, "to": "0x" + "cd" * 20, "value": "0", "data": "0xa9059cbb" + "00" * 64,
           "operation": 0, "gasToken": "0x" + "00" * 20, "safeTxGas": "0", "baseGas": "0", "gasPrice": "0",
           "refundReceiver": "0x" + "00" * 20, "nonce": 7, "submissionDate": "2026-11-05T00:00:00.000000Z",
           "safeTxHash": "0x" + "ef" * 32, "proposer": "0x" + "12" * 20, "isExecuted": False,
           "confirmationsRequired": 2, "trusted": True, "signatures": None,
           "confirmations": [{"owner": "0x" + "34" * 20, "submissionDate": "2026-11-05T00:00:00.000000Z",
                              "signature": "0x" + "56" * 65, "signatureType": "EOA"}],
           "dataDecoded": {"method": "transfer", "parameters": [{"name": "to", "type": "address", "value": "0x" + "78" * 20},
                                                               {"name": "value", "type": "uint256", "value": "1000000"}]}}
    s = json.dumps(one)
    n = max(1, want // (len(s) + 1))
    return '{"count": %d, "next": null, "previous": null, "results": [%s]}' % (n, ",".join([s] * n))


def part_json():
    body = queue_body(40 * 1024)
    env = json.dumps({"t": "res", "id": 7, "status": 200, "body": body}).encode()
    del body
    line = bytearray(env)                   # as link.py will hold it: one preallocated line buffer
    del env
    gc.collect()
    f0, big0 = gc.mem_free(), largest()
    a0 = gc.mem_alloc()
    t0 = time.ticks_us()
    m = json.loads(line)
    t1 = time.ticks_us()
    q = json.loads(m["body"])
    t2 = time.ticks_us()
    a1 = gc.mem_alloc()
    n = len(q["results"])
    out = {"line": len(line), "body": len(m["body"]), "txs": n, "env_ms": time.ticks_diff(t1, t0) // 1000,
           "body_ms": time.ticks_diff(t2, t1) // 1000, "alloc_kb": (a1 - a0) // 1024, "free_kb_before": f0 // 1024,
           "largest_kb_before": big0}
    del m
    gc.collect()
    out["body_only_kb"] = (gc.mem_alloc() - a0) // 1024     # what stays once the string is gone: the parsed queue
    del q, line
    gc.collect()
    out["free_kb_after"] = gc.mem_free() // 1024
    print("JSON", json.dumps(out))


# ----------------------------------------------------------------------------- 2. the UART
def busy(cond, ms):
    """Keep the CPU on `cond` for about ms, as the console would be while a line arrives."""
    t0 = time.ticks_ms()
    if cond == "hash":
        import safe_tx
        while time.ticks_diff(time.ticks_ms(), t0) < ms:
            safe_tx._domain_cache.clear()
            safe_tx.safe_tx_hash(8453, "0x" + "ab" * 20, "0x" + "cd" * 20, 0, b"\xa9\x05\x9c\xbb" + bytes(64), 0, nonce=7)
    elif cond == "flash":
        chunk = bytes(4096)
        with open("lb.tmp", "wb") as f:
            while time.ticks_diff(time.ticks_ms(), t0) < ms:
                f.write(chunk)
                f.flush()
        os.remove("lb.tmp")


def read_line(u, buf, quiet_ms):
    """Bytes until a newline, or until quiet_ms with nothing new. -> (length without the newline, done)."""
    mv = memoryview(buf)
    pos, last = 0, time.ticks_ms()
    while True:
        if u.any():
            n = u.readinto(mv[pos:]) or 0
            if n:
                last = time.ticks_ms()
                i = bytes(mv[pos:pos + n]).find(b"\n")
                pos += n
                if i >= 0:
                    return pos - n + i, True
                if pos >= len(buf):
                    return pos, False
        elif time.ticks_diff(time.ticks_ms(), last) > quiet_ms:
            return pos, False


def say(u, s):
    u.write(s + "\n")


def part_uart():
    print("LINKBENCH: UART1 goes to %d now; run linkhost.py" % BAUD)
    time.sleep_ms(300)
    os.dupterm(None)
    u = UART(1, BAUD, tx=Pin(20), rx=Pin(21), rxbuf=4096, txbuf=4096, timeout=0)
    buf = bytearray(max(SIZES) + 64)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 60000:       # the host has a minute to say GO
        say(u, "READY")
        n, done = read_line(u, buf, 500)
        if done and bytes(buf[:n]).strip() == b"GO":
            break
    else:
        return
    for rxbuf in RXBUFS:
        u.deinit()
        gc.collect()
        u = UART(1, BAUD, tx=Pin(20), rx=Pin(21), rxbuf=rxbuf, txbuf=4096, timeout=0)
        time.sleep_ms(50)
        while u.any():
            u.read()
        for size in SIZES:
            for cond in CONDS:
                for r in range(REPS):
                    say(u, "CASE %d %s %d %d" % (rxbuf, cond, size, r))
                    ms = size * 10 * 1000 // BAUD + 200           # as long as the line takes to arrive, and more
                    busy(cond, ms if cond != "idle" else 0)
                    n, done = read_line(u, buf, 1500)
                    got = bytes(buf[:n])
                    ok = done and len(got) > 9 and got[8:9] == b" " and \
                        "%08x" % (binascii.crc32(got[9:]) & 0xFFFFFFFF) == got[:8].decode("ascii", "replace")
                    say(u, "RES %d %s %d %d %s %d %d" % (rxbuf, cond, size, r, "ok" if ok else "BAD", n, 1 if done else 0))
                    while u.any():                          # whatever was left of a broken line
                        u.read()
                        time.sleep_ms(20)
        say(u, "FREE %d %d" % (rxbuf, gc.mem_free()))
    for size in SIZES:                                       # the other way: this side writes a line
        for r in range(REPS):
            payload = binascii.hexlify(os.urandom(size // 2))
            t0 = time.ticks_us()
            u.write(b"%08x " % (binascii.crc32(payload) & 0xFFFFFFFF))
            u.write(payload)
            u.write(b"\n")
            say(u, "SENT %d %d %d" % (size, r, time.ticks_diff(time.ticks_us(), t0) // 1000))
    say(u, "DONE")


gc.collect()
print("linkbench: heap %d KB free, largest block %d KB" % (gc.mem_free() // 1024, largest()))
part_json()
try:
    part_uart()
except Exception as e:                      # the REPL is off UART1 by now: keep the reason on the board
    with open("lb.err", "w") as f:
        sys.print_exception(e, f)
