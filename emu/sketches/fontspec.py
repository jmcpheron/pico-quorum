# Font specimens for v2: the same card in each candidate font set. A = next set, X stops.
#   GF_DIR=... uv run --with pillow python tools/fonts/gen.py --try    render the candidates first
#   tools/emu run fontspec                                            then flip through them
# The card holds what the console's screens are made of: a headline, body text, a title, an
# address in 4-character chunks, the pairs people mix up, the verify code and a button line.
# card(None) is today's fonts (firmware/qf_*.bin); card("inter") etc. a set from gen.py --try.
import fonts as F
import lcd as L
import quorum_ui as U

d = L.LCD()
keys = L.Keys()
SETS = (None, "inter", "interd", "grotesk", "plex", "manrope")
NAMES = {None: "ATKINSON HYPERLEGIBLE · TODAY", "inter": "INTER + ATKINSON MONO",
         "interd": "INTER (SS02) + ATKINSON MONO",
         "grotesk": "SPACE GROTESK + JETBRAINS MONO", "plex": "IBM PLEX SANS + PLEX MONO",
         "manrope": "MANROPE + ATKINSON MONO"}
T = U.THEMES["dark"]
BG, INK, MUTED, OK, STAKE = T["bg"], T["text"], T["muted"], T["ok"], T["stake"]
cur = 0


def card(fontset):
    F.use(fontset)
    d.fill(L.color(*BG))
    x = 10
    F.text(d, NAMES[fontset], x, 6, "sans12", MUTED, BG)
    F.text(d, "Send 0.05 ETH", x, 24, "bold26", INK, BG)
    F.text(d, "to Carol · from Family Safe", x, 60, "sans14", MUTED, BG)
    F.text(d, "Add a new owner?", x, 82, "bold18", INK, BG)
    F.text(d, "0x5afe 0c3E 91b8 4d27", x, 110, "mono13", STAKE, BG)
    F.text(d, "a11e 7F60 b3c9 8e05", x, 128, "mono13", STAKE, BG)
    F.text(d, "Il1| O0o rn m 5S 8B 6b", x, 150, "sans14", INK, BG)
    F.text(d, "3fa9 c071", x, 172, "monob28", INK, BG)
    x2 = F.text(d, "Hold A to sign", x, 214, "bold14", OK, BG)
    F.text(d, "  2 of 3 · ready", x2, 214, "sans12", MUTED, BG)
    d.show()
    F.use(None)


def tick(_):
    global cur
    for k in keys.pressed():
        if k == "A":
            cur = (cur + 1) % len(SETS)
            card(SETS[cur])
        elif k == "X":
            stop()


timer = None


def start():
    global timer
    from machine import Timer
    card(SETS[cur])
    timer = Timer(period=50, mode=Timer.PERIODIC, callback=tick)


def stop():
    if timer:
        timer.deinit()


start()
