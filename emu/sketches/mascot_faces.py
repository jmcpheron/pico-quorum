# Quo's faces, one card each: the face at 8 px an art pixel, its name, and what puts it on the screen.
# For docs/quorum-ui/v3/mascot/: the cards, then a contact sheet and a GIF of them (tools/mascotsheet).
# A design study: nothing here reads a chip or a service, and nothing signs.
#   tools/emu run mascot_faces     then turn or press A for the next face
#   node emu/render-cosigner-ui.mjs mascot_faces docs/quorum-ui/v3/mascot/faces waveshare
import lcd as L
import mascot as M

W, H = L.W, L.H
lcd = None
BG, PANEL, RULE, MUTED = (24, 20, 37), (38, 32, 60), (66, 58, 100), (150, 142, 180)
BANDS = {"red": ((96, 26, 46), M.RED), "amber": ((92, 60, 24), M.AMBER),
         "green": ((24, 72, 50), M.GREEN), "blue": ((30, 40, 96), M.BLUE), "none": (PANEL, M.AMBER)}

# face, the band it goes with, its name on the card, what puts it there
CARDS = [
    ("idle", "none", "IDLE", "Home. Nothing to review."),
    ("blink", "none", "BLINK", "Home, one step in 24."),
    ("money", "green", "MONEY", "Green: a payment."),
    ("scared", "amber", "SCARED", "Amber: owners or threshold change."),
    ("panic", "red", "PANIC", "Red: takes control."),
    ("nolook", "red", "NO LOOK", "Red: unknown module, guard, handler, delegatecall, 7702."),
    ("peek", "amber", "PEEK", "Amber: the same, known code, on purpose."),
    ("refuse", "red", "REFUSE", "A rule won't sign it."),
    ("suspect", "red", "SUSPECT", "The service's hash doesn't match."),
    ("focus", "blue", "FOCUS", "Sign held."),
    ("happy", "green", "HAPPY", "Signed."),
]
SCREENS = [(c[0], None) for c in CARDS]
cur = 0


def col(rgb):
    return L.color(*rgb)


def card(d, i):
    face, band, name, what = CARDS[i]
    bg, fg = BANDS[band]
    d.fill(col(BG))
    d.fill_rect(0, 0, W, 6, col(fg))
    px = 8 if H >= 200 else 4
    s = 16 * px
    d.fill_rect((W - s) // 2 - 8, 14, s + 16, s + 12, col(bg))
    M.draw(d, face, (W - s) // 2, 20, px, light=fg)
    y = 30 + s
    n = len(name) * 16
    _big(d, name, (W - n) // 2, y, fg)
    y += 24
    line = ""
    for w in what.split(" "):
        if len(line) + len(w) + 1 > (W - 16) // 8:
            d.text(line, (W - 8 * len(line)) // 2, y, col(MUTED))
            y, line = y + 11, w
        else:
            line = (line + " " + w) if line else w
    d.text(line, (W - 8 * len(line)) // 2, y, col(MUTED))


def _big(d, s, x, y, rgb):
    import framebuf
    fb = framebuf.FrameBuffer(bytearray(len(s) * 8), len(s) * 8, 8, framebuf.MONO_HLSB)
    fb.text(s, 0, 0, 1)
    c = col(rgb)
    for j in range(8):
        for i in range(len(s) * 8):
            if fb.pixel(i, j):
                d.fill_rect(x + 2 * i, y + 2 * j, 2, 2, c)


def draw(i):
    global lcd, cur
    if lcd is None:
        lcd = L.LCD()
    cur = i % len(CARDS)

    def frame():
        card(lcd, cur)
        lcd.show()
    lcd.frames(frame)


def start():
    draw(0)
    try:
        from machine import Timer
        keys = L.Keys()

        def tick(_t):
            for k in keys.pressed():
                if k in ("down", "right", "A", "press", "D1"):
                    draw(cur + 1)
                elif k in ("up", "left", "B", "D1L"):
                    draw(cur - 1)
        Timer(period=60, mode=Timer.PERIODIC, callback=tick)
    except Exception as e:
        print("mascot_faces: no keys:", e)


start()
