# The watchdog, on a deadline. RP2350's watchdog can wait 8.3 s at most and cannot be stopped once
# started, while one HTTPS call can take 15 s. So the watchdog is fed every second by a hard timer,
# but only until a deadline the console sets; code that is about to block pushes the deadline out
# first (extend). A console that stops calling extend (a hang, a loop that never returns) stops
# being fed and the board resets itself 8 s later. Started only by the production image, and only
# once the chip is the pinned one: a watchdog on a board that is being repaired over USB would
# reset it in the middle of a copy.
import time
import machine
import micropython

TIMEOUT_MS = 8000
_wdt = None
_timer = None
_deadline = 0


def _feed(t):
    if _wdt is not None and time.ticks_diff(_deadline, time.ticks_ms()) > 0:
        _wdt.feed()


def start():
    global _wdt, _timer
    if _wdt is not None:
        return
    if hasattr(micropython, "alloc_emergency_exception_buf"):      # a traceback from the hard timer, if it ever raises
        micropython.alloc_emergency_exception_buf(100)
    extend(TIMEOUT_MS)
    # The feeder before the watchdog: if the timer could not be made, nothing is armed that would
    # then reset the board every 8 s, boot after boot. (hard=True: checked on the board, 1.26.1.)
    _timer = machine.Timer(period=1000, mode=machine.Timer.PERIODIC, callback=_feed, hard=True)
    _wdt = machine.WDT(timeout=TIMEOUT_MS)


def extend(ms):
    """The console is alive and expects to be back within ms."""
    global _deadline
    d = time.ticks_add(time.ticks_ms(), ms)
    if _wdt is None or time.ticks_diff(d, _deadline) > 0:
        _deadline = d


def hold(ms):
    """Set the deadline to exactly ms from now, shorter too: tools/fw pauses the console for a
    backup with hold(600000) and puts it back to a normal tick's 5 s with hold(5000)."""
    global _deadline
    _deadline = time.ticks_add(time.ticks_ms(), ms)


def running():
    return _wdt is not None
