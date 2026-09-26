# Run on the board by `tools/fw measure tls`, which puts _CA (the pinned roots, DER) and _VHTTP
# (firmware/vhttp.py's source) in front of this file: nothing is written to flash. It follows the
# console's own order at start (its modules, every font, then the TLS context and the 32 KB
# reserve while the heap is still whole) and then answers:
#   1. does plain `requests` accept a certificate nobody vouches for? (the hazard vhttp fixes)
#   2. do 10 verified calls to api.safe.global fit, the reserve lent to each, and how long do they take?
#   3. does the verified context refuse badssl.com's expired, wrong-host, self-signed and
#      untrusted-root certificates (for the right reason, not for lack of memory)?
#   4. how big is a 10-transaction queue from the real service?
import gc, time, sys

URL = "https://api.safe.global/tx-service/basesep/api/v1/about/"
QUEUE = "https://api.safe.global/tx-service/basesep/api/v2/safes/0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43/multisig-transactions/?executed=false&limit=10"


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


print("0. the console's start: its modules, every font, then the TLS context and the reserve")
for m in ("quorum_ui", "decode", "safe_tx", "webauthn", "quorum_cfg", "signer", "txservice"):
    try:
        __import__(m)
    except Exception as e:
        print("   (%s not loaded: %r)" % (m, e))
try:
    import fonts
    for f in fonts.FILES:
        fonts.get(f)
except Exception as e:
    print("   (fonts: %r)" % e)
gc.collect()
ns = {}
exec(_VHTTP, ns)
import tls
C = tls.SSLContext(tls.PROTOCOL_TLS_CLIENT)
C.verify_mode = tls.CERT_REQUIRED
for b in _CA:
    C.load_verify_locations(b)
del _CA, _VHTTP
gc.collect()
KB = 32
try:
    room = bytearray(KB * 1024)
except MemoryError:
    room, KB = None, 0
print("   free %d, largest block %d, reserve %d KB held" % (gc.mem_free(), largest(), KB))


def call(url):
    """One verified GET with the reserve lent for its length, as txservice does."""
    global room
    room = None
    gc.collect()
    t0 = time.ticks_ms()
    try:
        r = ns["request"]("GET", url, C, timeout=15)
        return r.status_code, len(r.content), time.ticks_diff(time.ticks_ms(), t0)
    finally:
        gc.collect()
        try:
            room = bytearray(KB * 1024)
        except MemoryError:
            room = None
            print("   (the reserve no longer fits)")


print("1. plain requests against self-signed.badssl.com:")
room = None
gc.collect()
try:
    import requests
    r = requests.get("https://self-signed.badssl.com/", timeout=15)
    print("   ACCEPTED (status %d): requests does not check certificates" % r.status_code)
    r.close()
    r = None
except Exception as e:
    print("   refused: %r" % e)
gc.collect()
room = bytearray(KB * 1024) if KB else None

if time.gmtime()[0] < 2026:
    import ntptime
    for _ in range(3):
        try:
            ntptime.settime()
            break
        except OSError as e:
            print("   NTP: %r, again" % e)
print("   clock %04d-%02d-%02d %02d:%02d" % time.gmtime()[:5])

print("2. 10 verified calls, the reserve lent to each:")
ok, times, worst = 0, [], 10 ** 9
for i in range(10):
    try:
        st, n, ms = call(URL)
        ok += st == 200
        times.append(ms)
        print("   call %d: HTTP %d, %d bytes, %d ms" % (i + 1, st, n, ms))
    except Exception as e:
        print("   call %d FAILED: %r" % (i + 1, e))
    worst = min(worst, largest())
times.sort()
med = times[len(times) // 2] if times else -1
print("   %d/10 ok, median %d ms, worst %d ms; smallest largest-block between calls %d" % (ok, med, times[-1] if times else -1, worst))

print("3. the verified context must refuse these, on the certificate:")
cert_refusals = 0
for host in ("expired", "wrong.host", "self-signed", "untrusted-root"):
    try:
        st, n, ms = call("https://%s.badssl.com/" % host)
        print("   %s: ACCEPTED (HTTP %d)" % (host, st))
    except Exception as e:
        why = repr(e)
        mem = isinstance(e, OSError) and e.args and e.args[0] == 12
        cert_refusals += not mem
        print("   %s: %s %s" % (host, "refused (MEMORY, not the certificate)" if mem else "refused", why[:70]))

print("4. a real queue:")
try:
    print("   HTTP %d, %d bytes, %d ms" % call(QUEUE))
except Exception as e:
    print("   failed: %r" % e)
print("RESULT ok=%d/10 refused=%d/4 median_ms=%d reserve_kb=%d" % (ok, cert_refusals, med, KB))
