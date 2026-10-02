# The Trust M's security event counter under a burst of signatures, and how it fades after: the
# chip's own brake on key use, measured. ONLY on a sacrificial chip (it signs many times in a row
# and drives the counter up): it runs only when the chip on the bus has the serial named here.
# Also times the console's spares read (signer.TrustMSigner.spares, the Chip page) on silicon.
#   1. Set SACRIFICIAL below to the chip's serial (tools/fw verify shows it). Never a chip that owns anything.
#   2. On the console image with that chip in (not pinned, so the console signs nothing):
#      mpremote connect PORT resume exec "$(cat tools/board/tm_burst.py)"
# About two minutes. The console or ceremony app is paused while it runs and started again after.
# Prints one RESULT: line: the burst as [n, ms, counter] and the fade as [seconds, counter].
SACRIFICIAL = ""
BURST = 80              # signatures in a row, at most
SLOW_MS = 3000          # stop the burst once one signature takes this long
import sys, time, json, hashlib, trustm_q, tmcfg
_apps = [m for m in (sys.modules.get(n) for n in ("quorum", "chipapp")) if m and getattr(m, "timer", None)]
for _m in _apps:
    _m.stop()
try:
    import watch
    watch.hold(600000)
except (ImportError, AttributeError):
    pass
t = trustm_q.TrustM()
out = {"serial": t.serial()}
if not SACRIFICIAL or out["serial"] != SACRIFICIAL:
    print("NOT THE SACRIFICIAL CHIP, nothing tried:" + json.dumps(out))
else:
    import signer
    s = signer.TrustMSigner()
    t0 = time.ticks_ms()
    sp = s.spares()
    out["sparesMs"] = time.ticks_diff(time.ticks_ms(), t0)
    out["spares"] = tmcfg.spares_text(sp)
    out["secStart"] = t.sec()
    burst = []
    for i in range(BURST):
        d = hashlib.sha256(b"burst %d" % i).digest()
        t0 = time.ticks_ms()
        t.sign(tmcfg.KEY, d)
        ms = time.ticks_diff(time.ticks_ms(), t0)
        burst.append([i + 1, ms, t.sec()])
        if ms > SLOW_MS:
            break
    out["burst"] = burst
    fade = []
    for k in range(12):
        time.sleep(5)
        fade.append([(k + 1) * 5, t.sec()])
    out["fade"] = fade
    print("RESULT:" + json.dumps(out))
for _m in _apps:
    _m.start_timer()
try:
    import watch
    watch.hold(5000)
except (ImportError, AttributeError):
    pass
