"""The stompbox's wiring: a Pico 2 W seen from the top, USB on the left, with the 2.4" ST7789 screen,
an EC11 knob, a footswitch for Sign, and a USB-C plug for a key-c.
Writes wiring.svg next to this file. --check writes nothing: it loads firmware/board.py as the
"build1" profile and stops if its pins differ from the ones here.
    python3 hardware/builds/pico-stomp/wiring.py [--check]

Physical pin numbers as in hardware/wiring/BUILD1.md: USB to the left, chips up, pins 1-20 along
the bottom from the USB end, 40-21 along the top. Every signal is on Build 1's pin."""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

# Pico 2 W header: physical pin -> name
PICO = {1: "GP0", 2: "GP1", 3: "GND", 4: "GP2", 5: "GP3", 6: "GP4", 7: "GP5", 8: "GND", 9: "GP6", 10: "GP7",
        11: "GP8", 12: "GP9", 13: "GND", 14: "GP10", 15: "GP11", 16: "GP12", 17: "GP13", 18: "GND", 19: "GP14",
        20: "GP15", 21: "GP16", 22: "GP17", 23: "GND", 24: "GP18", 25: "GP19", 26: "GP20", 27: "GP21", 28: "GND",
        29: "GP22", 30: "RUN", 31: "GP26", 32: "GP27", 33: "AGND", 34: "GP28", 35: "VREF", 36: "3V3", 37: "3V3_EN",
        38: "GND", 39: "VSYS", 40: "VBUS"}

# What goes where: part -> [(its pin, Pico pin or "3V3 bus", colour)], left to right as drawn
KNOB = [("SW1", 2, "#e07b00"), ("SW2", "C", "#222222"), ("C", 3, "#222222"), ("A", 4, "#2e7dd7"), ("B", 5, "#1f9e8f")]
KEY = [("VBUS", "bus", "#d0312d"), ("D+", 6, "#2a9d3a"), ("D-", 7, "#7a5cc7"), ("GND", 8, "#222222")]
SCREEN = [("VCC", "bus", "#d0312d"), ("DC", 11, "#c2410c"), ("CS", 12, "#a16207"), ("GND", 13, "#222222"),
          ("SCL", 14, "#0e7490"), ("SDA", 15, "#1d4ed8"), ("RST", 16, "#6d28d9"), ("BLK", 17, "#be185d")]
FOOT = [("lug", 18, "#222222"), ("lug", 20, "#d4a000")]
POWER = 36

# The pins board.py's build1 profile must read for them (the knob's A and B either way round:
# board.py reads them swapped for the bench knob, and swapping the wires does the same)
WANT = {"ENC_SW": 1, "DC": 8, "CS": 9, "SCK": 10, "MOSI": 11, "RST": 12, "BL": 13, "SDA": 4, "SCL": 5}
WANT_KEYS = {"A": 15}               # A is Sign (the footswitch)


def gp(pin):
    return int(PICO[pin][2:])


def build1():
    """firmware/board.py, run on CPython with secrets.BOARD = "build1"."""
    sys.modules["secrets"] = types.SimpleNamespace(BOARD="build1", SCREEN="2.4")
    ns = {"__name__": "board"}
    exec(compile(open(os.path.join(REPO, "firmware", "board.py")).read(), "board.py", "exec"), ns)
    del sys.modules["secrets"]
    return ns


def check():
    b = build1()
    bad = []
    if b["BOARD"] != "build1" or not b["KNOB"] or (b["W"], b["H"]) != (320, 240):
        bad.append("board.py did not pick build1 with the knob and a 320x240 screen")
    for k, want in WANT.items():
        if b[k] != want:
            bad.append("%s: board.py GPIO%s, the wiring GPIO%d" % (k, b[k], want))
    if {b["ENC_A"], b["ENC_B"]} != {gp(4), gp(5)}:
        bad.append("knob A/B: board.py GPIO%s/%s, the wiring GP2/GP3" % (b["ENC_A"], b["ENC_B"]))
    for k, want in WANT_KEYS.items():
        if b["KEYS"].get(k) != want:
            bad.append("button %s: board.py GPIO%s, the wiring GPIO%d" % (k, b["KEYS"].get(k), want))
    if gp(FOOT[1][1]) != WANT_KEYS["A"]:
        bad.append("the footswitch is drawn on the wrong pin")
    if gp(KNOB[0][1]) != WANT["ENC_SW"] or gp(KEY[1][1]) != WANT["SDA"] or gp(KEY[2][1]) != WANT["SCL"]:
        bad.append("the knob's push or the key's bus is drawn on the wrong pin")
    if bad:
        sys.exit("the wiring and board.py's build1 profile disagree:\n  " + "\n  ".join(bad))
    print("pico-stomp wiring: agrees with board.py build1 (Sign GP15, knob GP1-3, key GP4/5, screen GP8-13)")


# --- drawing -------------------------------------------------------------------------------------
S = 8.0                                 # px per mm
PX, PY = 330, 210                       # the Pico's top-left corner
PW, PH = 51 * S, 21 * S
PIN0 = 1.37                             # mm from the board's end to pin 1's centre; 2.54 mm pitch
ROW = 1.61                              # mm from the long edge to a row's centres
BUS_Y = 440                             # the 3V3 bus, under the Pico
LANE0, LANE_DY = 462, 10                # the wires' lanes under it, from the highest down
PART_Y = 560                            # the top of the parts under the Pico


def pin_xy(n):
    if n <= 20:
        return PX + (PIN0 + 2.54 * (n - 1)) * S, PY + PH - ROW * S
    return PX + (PIN0 + 2.54 * (40 - n)) * S, PY + ROW * S


def svg():
    W, H = 1020, 860
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
         'font-family="Helvetica, Arial, sans-serif" font-size="12">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<text x="24" y="34" font-size="19" font-weight="bold">PicoQuorum stompbox: Pico 2 W, 2.4" screen, '
         'EC11 knob, footswitch Sign, key-c</text>',
         '<text x="24" y="56" fill="#555">Pico seen from the top, USB on the left. Firmware: the console image, '
         'BOARD = "build1", SCREEN = "2.4". Go by the names printed on each part.</text>']

    def line(pts, col, w=2.6, dash=None):
        o.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round"%s/>'
                 % (" ".join("%.1f,%.1f" % p for p in pts), col, w,
                    ' stroke-dasharray="%s"' % dash if dash else ""))

    def dot(x, y, col):
        o.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s"/>' % (x, y, col))

    def text(x, y, s, size=12, anchor="middle", col="#111", bold=False, rot=None):
        o.append('<text x="%.1f" y="%.1f" font-size="%s" text-anchor="%s" fill="%s"%s%s>%s</text>'
                 % (x, y, size, anchor, col, ' font-weight="bold"' if bold else "",
                    ' transform="rotate(%d %.1f %.1f)"' % (rot, x, y) if rot else "", s))

    # the Pico
    o.append('<rect x="%d" y="%d" width="%.1f" height="%.1f" rx="6" fill="#1f6f3f"/>' % (PX, PY, PW, PH))
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="#bfc4c9"/>'
             % (PX - 1.3 * S, PY + PH / 2 - 4 * S, 5.5 * S, 8 * S))
    text(PX + 3 * S, PY + PH / 2 + 4, "USB", 10, col="#333", rot=-90)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#2b2b2b"/>' % (PX + 19 * S, PY + 6.5 * S, 8 * S, 8 * S))
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#c9cfd4"/>' % (PX + 33 * S, PY + 5 * S, 11 * S, 11 * S))
    text(PX + PW / 2 + 40, PY + PH / 2 + 5, "Pico 2 W", 15, col="#ffffff", bold=True)
    used = {POWER} | {p for part in (KNOB, KEY, SCREEN, FOOT) for _, p, _ in part if isinstance(p, int)}
    for n in range(1, 41):
        x, y = pin_xy(n)
        u = n in used
        o.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="#e8c15a" stroke-width="1.5"/>'
                 % (x, y, 4.2 if u else 3.4, "#f4d77a" if u else "#1f6f3f"))
        top = n > 20
        text(x, y + (-10 if top else 17), str(n), 9, col="#ffffff" if u else "#a7c8b2")
        if u:
            text(x + 4, y + (-36 if top else 42), PICO[n], 10, anchor="start" if top else "end",
                 col="#333", bold=True, rot=-60)

    # a part: a box with its pins along the top edge, one per entry, in the order given
    def part(x, y, w, h, name, pins, fill, sub=None, dash=None, pitch=None, bottom=False):
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="8" fill="%s" stroke="#333" '
                 'stroke-width="1.5"%s/>' % (x, y, w, h, fill, ' stroke-dasharray="6 4"' if dash else ""))
        text(x + w / 2, y + h / 2 + 2, name, 14, bold=True)
        if sub:
            for i, s in enumerate(sub.split("\n")):
                text(x + w / 2, y + h / 2 + 20 + 15 * i, s, 11, col="#444")
        p = pitch or w / (len(pins) + 1)
        x0 = x + (w - p * (len(pins) - 1)) / 2
        out = []
        for i, (label, _, col) in enumerate(pins):
            px = x0 + p * i
            ey = y + h if bottom else y - 10
            o.append('<rect x="%.1f" y="%.1f" width="8" height="12" fill="#c9a227"/>' % (px - 4, ey - (2 if bottom else 0)))
            text(px, y + h - 8 if bottom else y + 18, label, 10, col="#222", bold=True)
            out.append((px, y + h + 10 if bottom else y - 10))
        return out

    # the 3V3 bus: pin 36, up and round the USB end, along under the Pico
    bx, by = pin_xy(POWER)
    line([(bx, by), (bx, PY - 54), (PX - 46, PY - 54), (PX - 46, BUS_Y), (540, BUS_Y)], "#d0312d", 3.4)
    text(PX - 54, BUS_Y - 4, "3V3 bus: pin 36 only. Never VBUS (40) or VSYS (39)", 11, anchor="start",
         col="#d0312d", bold=True, rot=-90)

    k = part(40, PART_Y, 190, 150, "EC11 knob", KNOB, "#e6eef8", "turn: move   push: open\nA C B one side, SW the other")
    ke = part(262, PART_Y, 190, 150, "USB-C plug", KEY, "#fff3e0",
              "key-c plugs on here\n4.7k VBUS to D+, 4.7k VBUS to D-\n(key-c has no pull-ups)")
    se = part(478, PART_Y, 330, 190, "2.4\" ST7789 240x320", SCREEN, "#e8f4ea",
              "your header's order differs: go by the names\nSCL = SPI clock, SDA = SPI data (MOSI)\nnot the key's I2C")
    fe = part(836, PART_Y, 150, 150, "Footswitch", FOOT, "#fdf2c4", "SIGN, held 2 s\nMOMENTARY, normally\nopen. Not latching", pitch=60)

    # Every wire from a part up to the Pico's bottom row: up to its lane, along, up to the pin. The
    # parts' pins and the Pico's run in the same order, so no two wires cross when, of the wires going
    # right, the leftmost runs highest, and of those going left, the rightmost.
    wires = []
    for pins, ends in ((KNOB, k), (KEY, ke), (SCREEN, se), (FOOT, fe)):
        at = {label: xy for (label, _, _), xy in zip(pins, ends)}
        for (label, p, col), (x, y) in zip(pins, ends):
            if p == "bus":
                line([(x, y), (x, BUS_Y)], col)
                dot(x, BUS_Y, col)
            elif p == "C":              # joined to C at the knob
                line([(x, y), (x, y - 12), (at["C"][0], y - 12)], col)
                dot(at["C"][0], y - 12, col)
            else:
                wires.append((x, y, p, col))
    right = sorted((w for w in wires if w[0] <= pin_xy(w[2])[0]), key=lambda w: w[0])
    left = sorted((w for w in wires if w[0] > pin_xy(w[2])[0]), key=lambda w: -w[0])
    lane = {w: LANE0 + LANE_DY * i for g in (right, left) for i, w in enumerate(g)}
    for w in wires:
        x, y, p, col = w
        px, py = pin_xy(p)
        line([(x, y), (x, lane[w]), (px, lane[w]), (px, py)], col)

    # notes
    notes = ["One press of the knob opens; a turn moves. On a review the footswitch is Sign: held 2 s (3 s when a page is red).",
             "The knob's push on the Sign row signs too (build1's rules). No Reject button: not signing is all a cosigner can do.",
             "Pull-ups: key-c has none of its own. 4.7k from D+ and from D- to VBUS (which is 3V3), at the plug.",
             "The key is powered whenever the Pico is: no switch, no current limit, as on the Feather pigtail."]
    for i, s in enumerate(notes):
        text(24, 790 + 17 * i, s, 11.5, anchor="start", col="#333")
    o.append("</svg>")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    check()
    if "--check" not in sys.argv:
        with open(os.path.join(HERE, "wiring.svg"), "w") as f:
            f.write(svg())
        print("wrote", os.path.relpath(os.path.join(HERE, "wiring.svg"), REPO))
