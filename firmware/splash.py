# Boot display: a short black lead-in, then the PicoQuorum mark with the real boot status on its
# last line. secrets.BOOT_ART picks the art: "mark" (the default, bootmark.py: flat vectors, only
# what changed is sent to the panel, runs on every panel), "still" (the finished mark at once) or
# "orbit" (bootart.py: the full orbit, the whole panel every frame, ~8-10 fps on the Pico; strip-
# buffered 240-row panels only, others get the mark) or "checklist" (the chip and a row per step,
# no art). The console calls finish before starting its
# timer/watchdog, releasing the art's code before normal transaction-service polling.
import time
import lcd as L
import theme as T
import icons as I

lcd = None
TITLE = "picowallet"   # the app that boots sets its own name (quorum.py: "picoquorum")
rows = []           # [key, text, color], drawn in ORDER
ORDER = ("screen", "wifi", "chip", "app")
ICON = {"screen": "screen", "wifi": "wifi", "chip": "chip", "app": "app"}
BLACK_LEAD_MS = 4000    # the orbit's; the mark sets its own (begin)
ANIMATION_MS = 9600
_t0 = 0
_frame = 0
_last = 0
_art = None
_still = False
_gap = 120          # spin redraws at most this often (ms): the orbit is a whole frame, the mark is not
_finished = False
_status = "Starting up"
_status_color = (152, 160, 172)
_waiting = None     # the row that is spinning, if any


def _choice():
    try:
        import secrets
        return getattr(secrets, "BOOT_ART", "mark")
    except ImportError:
        return "mark"


def begin():
    """The LCD, created once. Safe to call again: returns the same one."""
    global lcd, _t0, _art, _still, _gap, BLACK_LEAD_MS, ANIMATION_MS
    if lcd is None:
        lcd = L.LCD()
        # Clear every strip once; leave it black while the rest of startup proceeds.
        lcd.frames(_black)
        art = _choice()
        if art == "orbit" and L.H >= 200 and L.BANDS > 1:
            # The orbit needs the strip buffer: on a single 115 KB frame it ran the heap out
            # (MemoryError in bootart.render, 2026-09-29).
            import bootart
            _art = bootart
        elif art != "checklist":
            import bootmark
            _art, _gap = bootmark, 30
            _still = art == "still"
            BLACK_LEAD_MS = bootmark.LEAD_MS
            ANIMATION_MS = 0 if _still else bootmark.DURATION_MS
        _t0 = time.ticks_ms()
        step("screen", "ok", L.GREEN)
    return lcd


def step(key, text, color=L.WHITE):
    """Set a row (rows appear in ORDER as they are first set) and redraw."""
    global _waiting, _status, _status_color
    _status = key + ": " + text
    _status_color = (255, 92, 84) if color == L.RED else (152, 160, 172)
    for r in rows:
        if r[0] == key:
            r[1], r[2] = text, color
            break
    else:
        rows.append([key, text, color])
        rows.sort(key=lambda r: ORDER.index(r[0]) if r[0] in ORDER else 9)
    if _waiting == key and color != L.GREY:
        _waiting = None
    draw()


def spin(key, text):
    """A row that is waiting: call it as often as you like, it redraws at most ~8 times a second."""
    global _last, _waiting
    now = time.ticks_ms()
    if time.ticks_diff(now, _last) < _gap:
        return
    _last = now
    _waiting = key
    step(key, text, L.GREY)


def wifi_row(wlan, ssid):
    if wlan.isconnected():
        step("wifi", wlan.ifconfig()[0], L.GREEN)
    else:
        step("wifi", "not found, retrying" if ssid else "no secrets.py", L.RED)


def draw():
    """One frame. Each call advances the leg chase, so a periodic redraw animates it."""
    global _frame
    if lcd is None:
        return
    _frame += 1
    if _finished:
        return
    if _art is not None:
        elapsed = time.ticks_diff(time.ticks_ms(), _t0) - BLACK_LEAD_MS
        if elapsed < 0:
            return
        try:
            if getattr(_art, "IN_MS", False):          # the mark: time in ms
                _art.render(lcd, elapsed, _status, _status_color, _still)
            else:                                       # the orbit: its frame, 30 ms each
                _art.render(lcd, elapsed // 30, _status, _status_color)
        except MemoryError:
            # A frame of the animation is not worth the console: the Trust M's certificate checks leave
            # the heap in pieces (MemoryError in bootart.render on the 240x240 board, 2026-09-30). Skip it.
            # The mark keeps what it last sent until a frame completes, so the next one repaints the rest.
            _skipped()
    else:
        try:
            lcd.frames(_draw)
        except MemoryError:
            _skipped()


def _skipped():
    import gc
    lcd.y0 = 0
    gc.collect()


def _black():
    lcd.fill(L.BLACK)
    lcd.show()


def _draw():
    d = lcd
    T.gradient(d, 0, L.H, T.RGB["navy"], T.RGB["bg"])
    # the die: 48 px body, 8 legs a side, one colour of the rainbow per leg walking round
    small = L.H < 200       # the 1.8": the die, the name and four short rows in 128 px
    cx, cy = L.W // 2, 26 if small else 42
    if _waiting:
        r = 34 + (_frame % 3) * 2
        d.ellipse(cx, cy, r, r, T.shade("config", 0.5))
    d.fill_rect(cx - 24, cy - 24, 48, 48, T.C["ink"])
    d.rect(cx - 24, cy - 24, 48, 48, T.C["chip"])
    d.fill_rect(cx - 18, cy - 18, 5, 5, T.C["learn"])
    I.draw(d, "chip", cx - 8, cy - 8, T.shade("chip", 0.6))
    for i in range(8):
        y = cy - 21 + i * 6
        left = T.C[T.RAINBOW[(_frame + i) % 7]] if _waiting or _frame < 40 else T.C["dim"]
        right = T.C[T.RAINBOW[(_frame + 15 - i) % 7]] if _waiting or _frame < 40 else T.C["dim"]
        d.fill_rect(cx - 33, y, 9, 3, left)
        d.fill_rect(cx + 24, y, 9, 3, right)
    d.center_text(TITLE, 56 if small else 76, L.WHITE, 2)
    done = sum(1 for r in rows if r[2] == L.GREEN)
    x0, yb = L.W // 2 - 80, 74 if small else 96
    d.fill_rect(x0, yb, 160, 3, T.C["ink"])
    d.fill_rect(x0, yb, 40 * done, 3, T.C["learn"])
    if small:
        y = 82
        for key, text, color in rows:
            d.fill_rect(4, y + 2, 4, 4, color if color != L.GREY else T.C["config"])
            d.text((key + " " + text)[:(L.W - 14) // 8], 12, y, color)
            y += 11
        d.show()
        return
    y, ox = 110, (L.W - 240) // 2
    for key, text, color in rows:
        I.draw(d, ICON.get(key, "chip"), ox + 20, y - 4, color if color != L.GREY else T.C["config"])
        d.text(text[:24], ox + 44, y, color)
        y += 20
    d.text("%.1fs" % (time.ticks_diff(time.ticks_ms(), _t0) / 1000), 4, L.H - 12, T.C["dim"])
    d.show()


def finish(keys=None, wait=True):
    """Let the branding reach the name (the mark: 0.3 s black + 3.8 s; the orbit: 4 s + 9.6 s); any key skips.
    Called before the console starts its timer/watchdog. Release animation code before TLS.
    Errors bypass this hold and go straight to the console's error screen.
    """
    global _art, _finished
    if _art is None:
        return
    import gc
    import sys
    try:
        while wait and time.ticks_diff(time.ticks_ms(), _t0) < BLACK_LEAD_MS + ANIMATION_MS:
            if keys is not None and keys.pressed():
                break
            draw()
            time.sleep_ms(10)
    finally:
        _finished = True
        _art = None
        sys.modules.pop("bootart", None)
        sys.modules.pop("bootmark", None)
        sys.modules.pop("taglines", None)
        gc.collect()
