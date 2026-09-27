# A log that survives power cycles: one line per event in log.txt, the older half in log.1.txt.
# Each line is appended and the file closed straight away: MicroPython's LittleFS keeps nothing
# that was not closed (a backup made with one open().write() came out 0 bytes, BUILDLOG 2026-09-25).
# `tools/fw logs` pulls both files. Never raises: a full flash must not stop a signature.
import time

FILE, OLD = "log.txt", "log.1.txt"
MAX = 16 * 1024
_size = None
_last = {}          # message -> (ticks of first sighting, repeats since): see once()


def _stamp():
    t = time.gmtime()
    if t[0] >= 2025:
        return "%04d-%02d-%02d %02d:%02d:%02d" % t[:6]
    return "+%ds" % (time.ticks_ms() // 1000)     # clock not set yet (NTP): seconds since boot


def write(msg):
    global _size
    try:
        import os
        if _size is None:
            try:
                _size = os.stat(FILE)[6]
            except OSError:
                _size = 0
        if _size > MAX:
            try:
                os.remove(OLD)
            except OSError:
                pass
            os.rename(FILE, OLD)
            _size = 0
        line = "%s %s\n" % (_stamp(), msg)
        with open(FILE, "a") as f:
            f.write(line)
        _size += len(line)
    except Exception as e:
        print("qlog:", e)


def once(msg, every_ms=600000):
    """For errors that repeat on every poll: the first one is written, then a count every 10 min."""
    now = time.ticks_ms()
    seen = _last.get(msg)
    if seen is None:
        _last[msg] = (now, 0)
        if len(_last) > 20:
            _last.pop(next(iter(_last)))
        write(msg)
    elif time.ticks_diff(now, seen[0]) > every_ms:
        write("%s (x%d)" % (msg, seen[1] + 1))
        _last[msg] = (now, 0)
    else:
        _last[msg] = (seen[0], seen[1] + 1)
