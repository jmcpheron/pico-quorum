# console-rp: the console's boot animation (firmware/bootmark.py, the default "mark") on this board,
# timed frame by frame. Bench only. The console's own lcd.py, fonts.py, splash.py and bootmark.py run
# unchanged; board_rp.py stands in for board.py. Nothing here touches the key.
#   1. alone: the mark played three times, nothing else running
#   2. as the console boots: splash.run()'s soft timer draws while the main code does what a start
#      does with no Wi-Fi: compiles a big module, hashes the owner address (two Keccaks), collects
# Each frame's cost and the gaps between frames go over the link.
#   put.py PORT board_rp.py(as board.py) firmware/{lcd,fonts,theme,icons,splash,bootmark,taglines}.py
#          firmware/qf_{bold18,sans14,sans12}.bin firmware/keccak.py, then rawrepl.py PORT bootanim.py
import gc
import time
import lcd as L                         # the frame buffer first, as main.py does
import splash
import bootmark

us, dt = time.ticks_us, time.ticks_diff
log = []                                # (start us, cost us) of each frame that sent something
_render = bootmark.render


def timed_render(*a, **k):
    m = bootmark._mark
    before = m.sent if m else -1
    t = us()
    _render(*a, **k)
    if bootmark._mark.sent != before:   # a frame where nothing changed sends nothing: not counted
        log.append((t, dt(us(), t)))


bootmark.render = timed_render          # splash looks it up on each frame


def report(name, t_from, t_to):
    """Frames whose start is in [t_from, t_to): how many, what they cost, the longest gap."""
    gc.collect()
    fs = [f for f in log if dt(f[0], t_from) >= 0 and dt(t_to, f[0]) > 0]
    if len(fs) < 2:
        print("%s: %d frames" % (name, len(fs)))
        return
    costs = sorted(c for _, c in fs)
    gaps = [dt(fs[i + 1][0], fs[i][0]) for i in range(len(fs) - 1)]
    span = dt(fs[-1][0], fs[0][0]) / 1e6
    print("%s: %d frames in %.2f s = %.1f fps; frame cost median %.1f ms, max %.1f ms; longest gap %.0f ms; gaps over 100 ms: %d"
          % (name, len(fs), span, (len(fs) - 1) / span, costs[len(costs) // 2] / 1000, costs[-1] / 1000,
             max(gaps) / 1000, sum(1 for g in gaps if g > 100_000)))


def big_source(n):
    return "".join("def f%d(a, b):\n    x = a + b * %d\n    if x > 3:\n        return [x, a, b, 'f%d']\n"
                   "    return {'k': x, 'n': %d}\n" % (i, i, i, i) for i in range(n))


def alone():
    d = splash.begin()
    for run in range(3):
        bootmark._mark = None
        d.fill(L.BLACK); d.show()
        t0 = time.ticks_ms()
        start = us()
        while time.ticks_diff(time.ticks_ms(), t0) < bootmark.DURATION_MS + 300:
            bootmark.render(d, time.ticks_diff(time.ticks_ms(), t0), "console-rp: alone, run %d" % (run + 1), (152, 160, 172))
            time.sleep_ms(10)                       # as splash.finish paces it
        report("alone run %d" % (run + 1), start, us())
        log.clear()
        time.sleep_ms(1500)


def as_boot():
    global log
    # A fresh splash, as at power-up.
    import sys
    sys.modules.pop("splash", None)
    import splash as s
    log = []
    gc.collect()
    s.begin()
    s.run(30)
    start = us()
    s.step("chip", "reading")
    src = big_source(220)                           # about 25 KB, near quorum_ui.py's 20 KB
    time.sleep_ms(600)                              # the lead-in and the first pops, nothing else
    t = us()
    exec(compile(src, "big", "exec"), {})           # compiling is C: the timer can't run meanwhile
    c_ms = dt(us(), t) / 1000
    del src
    s.step("chip", "hashing the owner")
    t = us()
    try:
        from keccak import keccak256
        h = keccak256(keccak256(b"\x04" + b"\x11" * 64))  # the owner address: two Keccaks, in Python
    except ImportError:
        h = b""
    k_ms = dt(us(), t) / 1000
    t = us()
    gc.collect()
    g_ms = dt(us(), t) / 1000
    s.step("app", "starting")
    s.finish(wait=True)                             # what the console does: the mark to its end
    report("as the console boots", start, us())
    print("  compiling 25 KB took %.0f ms, the two Keccaks %.0f ms, gc %.1f ms" % (c_ms, k_ms, g_ms))


alone()
as_boot()
gc.collect()
print("heap free after: %d KB" % (gc.mem_free() // 1024))
