# The Trust M's security event counter under a burst of signatures, and how it fades after: the
# chip's own brake on key use, measured. ONLY on a sacrificial chip (it signs many times in a row
# and drives the counter up): it runs only when the chip on the bus has the serial named here.
# Also times the console's spares read (signer.TrustMSigner.spares, the Chip page) on silicon.
#   1. Set SACRIFICIAL below to the chip's serial (tools/fw verify shows it). Never a chip that owns anything.
#   2. On the console image with that chip in (not pinned, so the console signs nothing):
#      mpremote connect PORT resume exec "$(cat tools/board/tm_burst.py)"
# About two minutes. The console or ceremony app is paused while it runs and started again after.
# Prints one RESULT: line: the burst as [n, ms, counter, error] and the fade as [seconds, counter].
# TM2 (2026-10-01): +1 per signature from 0 with no slowdown to 78; from about 127 each count adds
# about 40 ms to a signature (1.0 s at 149, 2.5 s at 187), 5 s near 249; it fades 1 every 5 s.
# Past about 150 a signature outlasts upstream's 1 s wait (trustm.wait_response), so this run
# waits up to 15 s, in RAM only.
SACRIFICIAL = ""
BURST = 200             # signatures in a row, at most
SLOW_MS = 5000          # stop the burst once one signature takes this long
import sys, time, json, hashlib, trustm, trustm_q, tmcfg
_wait = trustm.wait_response
trustm.wait_response = lambda timeout_ms=15000: _wait(15000)
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
        try:
            t.sign(tmcfg.KEY, d)
            err = ""
        except Exception as e:
            err = str(e)[-40:]
            t.s = None
        ms = time.ticks_diff(time.ticks_ms(), t0)
        burst.append([i + 1, ms, t.sec(), err])
        if ms > SLOW_MS or err:
            break
    out["burst"] = burst
    fade = []
    for k in range(12):
        time.sleep(5)
        fade.append([(k + 1) * 5, t.sec()])
    out["fade"] = fade
    print("RESULT:" + json.dumps(out))
trustm.wait_response = _wait
for _m in _apps:
    _m.start_timer()
try:
    import watch
    watch.hold(5000)
except (ImportError, AttributeError):
    pass
