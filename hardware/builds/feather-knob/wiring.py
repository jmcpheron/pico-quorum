"""The knob Feather's pin diagram: Adafruit's ESP32-S3 TFT Feather (5483) seen from its screen side,
USB-C on the left, with an EC11 knob and a USB-C adapter for a key-c on its header pins. Writes
wiring.svg next to this file. --check writes nothing: it compares the pins here with
firmware/board.py's "feather-knob" profile and stops if they differ.
    python3 hardware/builds/feather-knob/wiring.py [--check]

The header order and each pin's GPIO are from Adafruit's board files
(https://github.com/adafruit/Adafruit-ESP32-S3-TFT-Feather-PCB, 2026-10-25): the schematic's nets,
mapped to the ESP32-S3-MINI-1's pins. Go by the silkscreen labels on the board when wiring."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

# The two rows from the USB end, as the silkscreen names them, and the GPIO behind each.
ROW16 = [("RST", None), ("3V", None), ("NC", None), ("GND", None), ("A0", 18), ("A1", 17), ("A2", 16), ("A3", 15),
         ("A4", 14), ("A5", 8), ("SCK", 36), ("MO", 35), ("MI", 37), ("RX", 2), ("TX", 1), ("DB", None)]
ROW12 = [("BAT", None), ("EN", None), ("USB", None), ("13", 13), ("12", 12), ("11", 11), ("10", 10), ("9", 9),
         ("6", 6), ("5", 5), ("SCL", 41), ("SDA", 42)]
ROW16_X, ROW12_X = 6.35, 16.51        # mm from the USB end to each row's first pin; 2.54 mm pitch

# What goes where: (part, its pin, the Feather's pin, colour)
KNOB = [("A", "A1", "#2e7dd7"), ("C", "GND", "#222222"), ("B", "A2", "#1f9e6f"),
        ("D", "A3", "#d7832e"), ("E", "GND", "#222222")]
KEY = [("VBUS", "3V", "#d0312d"), ("GND", "GND", "#222222"), ("D+", "SDA", "#2a9d3a"), ("D-", "SCL", "#7a5cc7")]
# The pins board.py must read for them
WANT = {"ENC_A": "A1", "ENC_B": "A2", "ENC_SW": "A3", "SDA": "SDA", "SCL": "SCL"}

S = 9.0                               # px per mm
BX, BY = 70, 250                      # the board's top-left corner on the page
BW, BH = 50.8 * S, 22.86 * S


def gpio(name):
    return dict(ROW16 + ROW12)[name]


def pin_xy(name):
    """The centre of a header pin on the page. The 12-pin row is along the top edge, the 16-pin row
    along the bottom, seen from the screen side with USB-C on the left."""
    for row, x0, y in ((ROW16, ROW16_X, BH - 1.27 * S), (ROW12, ROW12_X, 1.27 * S)):
        for i, (n, _g) in enumerate(row):
            if n == name and (n != "GND" or row is ROW16):
                return BX + (x0 + 2.54 * i) * S, BY + y
    raise KeyError(name)


def check():
    b = open(os.path.join(REPO, "firmware", "board.py")).read()
    m = re.search(r"^if DIAL:\n(.*?)(?:\n\S|\Z)", b, re.S | re.M)
    if not m:
        sys.exit("board.py has no `if DIAL:` block")
    prof = m.group(1)
    got = {}
    for names, values in re.findall(r"^\s+([A-Z_, ]+?) = ([\d, ]+)$", prof, re.M):
        for k, v in zip(names.split(","), values.split(",")):
            got[k.strip()] = int(v)
    bad = ["%s: board.py says GPIO%s, the wiring %s is GPIO%d" % (k, got.get(k), pin, gpio(pin))
           for k, pin in WANT.items() if got.get(k) != gpio(pin)]
    if bad:
        sys.exit("the wiring and board.py's feather-knob profile disagree:\n  " + "\n  ".join(bad))
    print("feather-knob wiring: agrees with board.py (%s)" % ", ".join("%s GPIO%d" % (k, got[k]) for k in WANT))


def svg():
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="660" height="740" viewBox="0 0 660 740" '
           'font-family="Helvetica, Arial, sans-serif" font-size="11">',
           '<rect width="660" height="740" fill="#ffffff"/>',
           '<text x="20" y="28" font-size="16" font-weight="bold">The knob Feather: ESP32-S3 TFT Feather (5483), EC11 knob, key-c</text>',
           '<text x="20" y="46" fill="#555">Seen from the screen side, USB-C on the left. Go by the silkscreen labels.</text>']

    def wire(x0, y0, x1, y1, col, via_y):
        out.append('<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" '
                   'stroke-width="2.5" stroke-linejoin="round"/>' % (x0, y0, x0, via_y, x1, via_y, x1, y1, col))

    # the board
    out.append('<rect x="%d" y="%d" width="%.1f" height="%.1f" rx="%.1f" fill="#1d1d1d"/>' % (BX, BY, BW, BH, 2.54 * S))
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#3a6ea5"/>' % (BX + 13 * S, BY + 3.5 * S, 25 * S, 15.5 * S))
    out.append('<text x="%.1f" y="%.1f" fill="#ffffff" text-anchor="middle">1.14" screen</text>' % (BX + 25.5 * S, BY + 11.8 * S))
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#9a9a9a"/>' % (BX - 1.2 * S, BY + 7.4 * S, 7.5 * S, 8 * S))
    out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#000" font-size="9">USB-C</text>' % (BX + 2.6 * S, BY + 11.8 * S))
    out.append('<text x="%.1f" y="%.1f" fill="#bbb" font-size="9">Boot  Reset</text>' % (BX + 40.5 * S, BY + 11.8 * S))
    used = {p for _a, p, _c in KNOB + KEY}
    for row in (ROW16, ROW12):
        for n, g in row:
            x, y = pin_xy(n) if not (n == "GND" and row is ROW12) else (0, 0)
            hot = n in used
            out.append('<circle cx="%.1f" cy="%.1f" r="7" fill="%s" stroke="#d4a017" stroke-width="2"/>' % (x, y, "#d4a017" if hot else "#000"))
            ty = y - 13 if row is ROW12 else y + 20
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-weight="%s" font-size="%s">%s</text>' % (
                x, ty, "#000" if hot else "#777", "bold" if hot else "normal", 9 if len(n) > 2 else 11, n))
            if g is not None:
                out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#999" font-size="8">%d</text>' % (
                    x, ty + (-11 if row is ROW12 else 11), g))

    # the key-c's USB-C adapter, above the board: its wires go to the 12-pin row and round to 3V/GND
    kx, ky = 430, 64
    out.append('<rect x="%d" y="%d" width="190" height="64" rx="6" fill="#f2f2f2" stroke="#888"/>' % (kx, ky))
    out.append('<text x="%d" y="%d" font-weight="bold">USB-C adapter for key-c</text>' % (kx + 8, ky + 16))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">key-c: D+ is SDA, D- is SCL</text>' % (kx + 8, ky + 29))
    for i, (a, p, col) in enumerate(KEY):
        x = kx + 22 + i * 46
        out.append('<circle cx="%d" cy="%d" r="5" fill="%s"/>' % (x, ky + 64, col))
        out.append('<text x="%d" y="%d" text-anchor="middle">%s</text>' % (x, ky + 52, a))
        px, py = pin_xy(p)
        if p in ("SDA", "SCL"):
            wire(x, ky + 64, px, py - 7, col, ky + 90 + i * 8)
        else:                         # 3V and GND are on the far row: round the board's right end
            ex = BX + BW + 22 + i * 10
            low = 575 + i * 9
            out.append('<polyline points="%d,%d %d,%d %.1f,%d %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" '
                       'stroke-width="2.5" stroke-linejoin="round"/>' % (
                           x, ky + 64, x, ky + 90 + i * 8, ex, ky + 90 + i * 8, ex, low, px, low, px, py + 7, col))

    # the knob, below the board: A C B on one side, D E on the other
    nx, ny = 150, 610
    out.append('<rect x="%d" y="%d" width="150" height="90" rx="8" fill="#f2f2f2" stroke="#888"/>' % (nx, ny))
    out.append('<circle cx="%d" cy="%d" r="22" fill="#cfcfcf" stroke="#888"/>' % (nx + 75, ny + 45))
    out.append('<text x="%d" y="%d" font-weight="bold">EC11 knob, 20 detents</text>' % (nx + 190, ny + 40))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">A C B on one side (C in the middle),</text>' % (nx + 190, ny + 54))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">the push D E on the other</text>' % (nx + 190, ny + 66))
    xs = {"A": nx + 50, "C": nx + 75, "B": nx + 100, "D": nx + 62, "E": nx + 88}
    for i, (a, p, col) in enumerate(KNOB):
        x = xs[a]
        y = ny if a in "ACB" else ny + 90
        out.append('<circle cx="%d" cy="%d" r="5" fill="%s"/>' % (x, y, col))
        out.append('<text x="%d" y="%d" text-anchor="middle">%s</text>' % (x, y + (16 if a in "ACB" else -8), a))
        px, py = pin_xy(p)
        if a in "ACB":
            wire(x, y, px, py + 7, col, 520 + i * 10)
        else:                         # the push: round the knob's side, below the board's labels
            side = nx + 170 if a == "D" else nx - 20
            via = 552 if a == "D" else 562
            out.append('<polyline points="%d,%d %d,%d %d,%d %d,%d %.1f,%d %.1f,%.1f" fill="none" stroke="%s" '
                       'stroke-width="2.5" stroke-linejoin="round"/>' % (
                           x, y, x, y + 16, side, y + 16, side, via, px, via, px, py + 7, col))

    notes = ["Knob: A to A1 (GPIO17), B to A2 (GPIO16),", "the push's D to A3 (GPIO15); C and E to GND.",
             "Key adapter: VBUS to 3V, never USB or BAT;", "GND to GND, D+ to SDA (42), D- to SCL (41).",
             "One GND pin for three wires: join C and E", "at the knob, then splice in the adapter's GND."]
    for i, n in enumerate(notes):
        out.append('<text x="20" y="%d" fill="#333" font-size="10.5">%s</text>' % (78 + i * 15, n))
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    check()
    if "--check" not in sys.argv:
        path = os.path.join(HERE, "wiring.svg")
        with open(path, "w") as f:
            f.write(svg() + "\n")
        print("wrote", os.path.relpath(path, REPO))
