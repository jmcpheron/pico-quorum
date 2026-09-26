# Run on the board by `tools/fw measure tls`, which puts _CA (the pinned roots, DER) and _VHTTP
# (firmware/vhttp.py's source) in front of this file: nothing is written to flash. It answers:
#   1. does plain `requests` accept a certificate nobody vouches for? (the hazard vhttp fixes)
#   2. before NTP, does a verified call fail on the clock?
#   3. after NTP, do 10 verified calls to api.safe.global fit in the heap the console leaves, and
#      how long does each take?
#   4. does the verified context refuse badssl.com's expired, wrong-host, self-signed and
#      untrusted-root certificates?
#   5. how big is a 10-transaction queue from the real service?
import gc, time, sys

ns = {}
exec(_VHTTP, ns)
URL = "https://api.safe.global/tx-service/basesep/api/v1/about/"
QUEUE = "https://api.safe.global/tx-service/basesep/api/v2/safes/0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43/multisig-transactions/?executed=false&limit=10"


def ctx():
    import tls
    c = tls.SSLContext(tls.PROTOCOL_TLS_CLIENT)
    c.verify_mode = tls.CERT_REQUIRED
    for b in _CA:
        c.load_verify_locations(b)
    return c


def largest():
    """The biggest single block the heap can give right now (binary search)."""
    gc.collect()
    lo, hi = 0, gc.mem_free()
    while hi - lo > 256:
        mid = (lo + hi) // 2
        try:
            b = bytearray(mid)
            del b
            lo = mid
        except MemoryError:
            hi = mid
    gc.collect()
    return lo


def get(url, c):
    t0 = time.ticks_ms()
    r = ns["request"]("GET", url, c, timeout=15)
    return r.status_code, len(r.content), time.ticks_diff(time.ticks_ms(), t0)


print("1. plain requests against self-signed.badssl.com:")
try:
    import requests
    r = requests.get("https://self-signed.badssl.com/", timeout=15)
    print("   ACCEPTED (status %d): requests does not check certificates" % r.status_code)
    r.close()
except Exception as e:
    print("   refused: %r" % e)

C = ctx()
print("2. verified, clock at %s:" % (time.gmtime()[:3],))
try:
    print("   ", get(URL, C))
except Exception as e:
    print("   failed as expected: %r" % e)

import ntptime
ntptime.settime()
print("   NTP: clock now %04d-%02d-%02d %02d:%02d" % time.gmtime()[:5])

print("3. the console's heap: its modules, fonts and the 32 KB reserve")
for m in ("quorum_ui", "decode", "fonts", "safe_tx", "webauthn"):
    try:
        __import__(m)
    except Exception as e:
        print("   (%s not loaded: %r)" % (m, e))
try:
    import fonts
    for f in fonts.FILES:
        fonts.get(f)
except Exception:
    pass
gc.collect()
room = bytearray(32 * 1024)
print("   free %d, largest block %d, with the reserve held" % (gc.mem_free(), largest()))
ok, times, worst_block = 0, [], 10 ** 9
for i in range(10):
    room = None
    gc.collect()
    try:
        st, n, ms = get(URL, C)
        ok += st == 200
        times.append(ms)
        print("   call %d: HTTP %d, %d bytes, %d ms" % (i + 1, st, n, ms))
    except Exception as e:
        print("   call %d FAILED: %r" % (i + 1, e))
    gc.collect()
    worst_block = min(worst_block, largest())
    room = bytearray(32 * 1024)
times.sort()
print("   %d/10 ok, median %s ms, worst %s ms, smallest largest-block after a call %d" % (
    ok, times[len(times) // 2] if times else "-", times[-1] if times else "-", worst_block))

print("4. the verified context must refuse these:")
room = None
gc.collect()
bad = 0
for host in ("expired", "wrong.host", "self-signed", "untrusted-root"):
    try:
        st, n, ms = get("https://%s.badssl.com/" % host, C)
        print("   %s: ACCEPTED (HTTP %d)" % (host, st))
        bad += 1
    except Exception as e:
        print("   %s: refused, %r" % (host, e))

print("5. a real queue:")
try:
    print("   HTTP %d, %d bytes, %d ms" % get(QUEUE, C))
except Exception as e:
    print("   failed: %r" % e)
print("RESULT ok=%d/10 refused=%d/4 median_ms=%s" % (ok, 4 - bad, times[len(times) // 2] if times else "-"))
