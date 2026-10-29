"""The QT Py cosigner's wiring diagrams: an Adafruit QT Py ESP32 seen from its top, USB-C up, with an
SPI screen, an ATECC608 breakout on the STEMMA QT port and three buttons (wiring.svg), and the USB
serial bridge that later carries the link instead of the QT Py's own USB (link.svg). Writes both
next to this file. --check writes nothing: it stops if either file differs from what this draws, or
if the README's pin table disagrees with the pins here.
    python3 hardware/builds/qtpy-cosigner/wiring.py [--check]

The pads and each pad's GPIO are from CircuitPython's board files (ports/espressif/boards/
adafruit_qtpy_esp32s3_nopsram, adafruit_qtpy_esp32s3_4mbflash_2mbpsram and adafruit_qtpy_esp32_pico,
pins.c, 2026-10-29). The two S3 boards have the same map. Go by the silkscreen labels when wiring."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

# Each column from the USB end, as the silkscreen names it, and the GPIO behind it: (S3, ESP32 Pico)
LEFT = [("A0", 18, 26), ("A1", 17, 25), ("A2", 9, 27), ("A3", 8, 15), ("SDA", 7, 4), ("SCL", 6, 33),
        ("TX", 5, 32)]
RIGHT = [("5V", None, None), ("GND", None, None), ("3V", None, None), ("MO", 35, 13), ("MI", 37, 12),
         ("SCK", 36, 14), ("RX", 16, 7)]
STEMMA = {"SDA1": (41, 22), "SCL1": (40, 19)}     # the STEMMA QT port's own bus, not the SDA/SCL pads
BOOT = (0, 0)

# The screen: (its pin, the QT Py's pad, colour). Top to bottom as drawn; modules differ, so go by
# the labels printed on yours.
SCREEN = [("GND", "GND", "#222222"), ("3V3", "3V", "#d0312d"), ("MOSI", "MO", "#2e7dd7"),
          ("SCL", "SCK", "#d7832e"), ("BL", "A3", "#c2185b"), ("RST", "A2", "#8a6d3b"),
          ("DC", "A1", "#1f9e6f"), ("CS", "A0", "#7a5cc7")]
BUTTONS = [("D0", "Reject", "SDA", "#c62828"), ("D2", "Sign", "SCL", "#0a7d8c"), ("D1", "Next", "TX", "#6b8e23")]
# The link, later: a 3.3 V USB serial bridge on UART1. (its pin, the QT Py's pad or None, colour)
BRIDGE = [("5V", "5V", "#d0312d"), ("GND", "GND", "#222222"), ("RXD", "SDA", "#2e7dd7"),
          ("TXD", "RX", "#1f9e6f"), ("3V3", None, "#999999"), ("DTR", None, "#999999"), ("RTS", None, "#999999")]

# What each pad is for, in the README's table
USE = {"A0": "screen CS", "A1": "screen DC", "A2": "screen RST", "A3": "screen BL", "SCK": "screen SCL (the clock)",
       "MO": "screen MOSI", "TX": "D1, Next: a button to GND", "SCL": "D2, Sign: a button to GND",
       "SDA": "D0, Reject: a button to GND. Later the link's UART1 TX, and D0 moves to A3",
       "RX": "the link, later: UART1 RX from the bridge's TXD"}

S = 12.0                              # px per mm
BX, BY = 250, 170                     # the board's top-left corner on the page
BW, BH = 17.8 * S, 21.6 * S           # 0.7 x 0.85 inch, USB-C on the top edge; the columns 0.6 inch apart


def gpio(pad):
    return {n: (s3, pico) for n, s3, pico in LEFT + RIGHT}[pad]


def pad_xy(name):
    for col, x in ((LEFT, BX + BW / 2 - 15.24 * S / 2), (RIGHT, BX + BW / 2 + 15.24 * S / 2)):
        for i, (n, _s3, _p) in enumerate(col):
            if n == name:
                return x, BY + (3.18 + 2.54 * i) * S
    raise KeyError(name)


def head(out, w, h, title, sub):
    out += ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
            'font-family="Helvetica, Arial, sans-serif" font-size="11">' % (w, h, w, h),
            '<rect width="%d" height="%d" fill="#ffffff"/>' % (w, h),
            '<text x="20" y="28" font-size="16" font-weight="bold">%s</text>' % title,
            '<text x="20" y="46" fill="#555">%s</text>' % sub]


def line(out, pts, col, dash=False):
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.5" stroke-linejoin="round"%s/>' % (
        " ".join("%.1f,%.1f" % p for p in pts), col, ' stroke-dasharray="6 4"' if dash else ""))


def ground(out, x, y, down=True):
    """A ground symbol hanging from (x, y). Every one is the QT Py's GND pad."""
    d = 1 if down else -1
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#222" stroke-width="2.5"/>' % (x, y, x, y + 10 * d))
    for i, w in enumerate((9, 6, 3)):
        yy = y + (10 + 4 * i) * d
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#222" stroke-width="2"/>' % (x - w, yy, x + w, yy))


def board(out, used, own_usb):
    """The QT Py, top side up, USB-C on the top edge. The STEMMA QT port is on the back, at the far end."""
    out.append('<rect x="%d" y="%d" width="%.1f" height="%.1f" rx="%.1f" fill="#1d1d1d"/>' % (BX, BY, BW, BH, 1.5 * S))
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#9a9a9a" rx="3"/>' % (
        BX + BW / 2 - 4.5 * S, BY - 1.5 * S, 9 * S, 4.2 * S))
    out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="10">USB-C</text>' % (BX + BW / 2, BY + 0.1 * S))
    out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#333" font-size="9">%s</text>' % (
        BX + BW / 2, BY + 1.6 * S, own_usb))
    cx = BX + BW / 2
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#3a3a3a" stroke="#666"/>' % (cx - 3.6 * S, BY + 8.8 * S, 7.2 * S, 5.6 * S))
    out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#eee" font-size="9">ESP32-S3</text>' % (cx, BY + 11.3 * S))
    out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#aaa" font-size="8">or ESP32 Pico</text>' % (cx, BY + 12.5 * S))
    for i, (lab, col) in enumerate((("Boot", "#888"), ("Reset", "#888"))):
        bx = cx - 3.2 * S + i * 3.6 * S
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="#bbb" stroke="%s" stroke-width="2"/>' % (
            bx, BY + 14.8 * S, 2.8 * S, 2.0 * S, col))
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-size="9">%s</text>' % (
            bx + 1.4 * S, BY + 17.9 * S, "#bbb", lab))
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#f0c040" stroke-dasharray="4 3"/>' % (
        cx - 3.2 * S, BY + BH - 2.2 * S, 6.4 * S, 2.6 * S))
    for col, left in ((LEFT, True), (RIGHT, False)):
        for n, s3, pico in col:
            x, y = pad_xy(n)
            hot = n in used
            out.append('<circle cx="%.1f" cy="%.1f" r="7" fill="%s" stroke="#d4a017" stroke-width="2"/>' % (
                x, y, "#d4a017" if hot else "#000"))
            tx = x + 12 if left else x - 12
            anchor = "start" if left else "end"
            out.append('<text x="%.1f" y="%.1f" text-anchor="%s" fill="%s" font-weight="%s">%s</text>' % (
                tx, y + (0 if s3 is not None else 4), anchor, "#fff" if hot else "#888", "bold" if hot else "normal", n))
            if s3 is not None:
                out.append('<text x="%.1f" y="%.1f" text-anchor="%s" fill="#999" font-size="8">%d/%d</text>' % (
                    tx, y + 10, anchor, s3, pico))


def wiring_svg():
    out = []
    head(out, 800, 800, "The QT Py cosigner: QT Py ESP32, SPI screen, ATECC608 breakout, three buttons",
         "Seen from the top, USB-C up. Small numbers: GPIO on the S3 / on the ESP32 Pico. Go by the silkscreen labels.")
    used = {p for _a, p, _c in SCREEN} | {p for _d, _l, p, _c in BUTTONS}
    board(out, used, "to the phone")

    # the phone, above, on the QT Py's own USB-C: the bench stage
    out.append('<rect x="290" y="62" width="134" height="44" rx="8" fill="#f2f2f2" stroke="#888"/>')
    out.append('<text x="357" y="81" text-anchor="middle" font-weight="bold">phone (the relay)</text>')
    out.append('<text x="357" y="96" text-anchor="middle" fill="#555" font-size="9">USB-C, OTG</text>')
    line(out, [(BX + BW / 2, 106), (BX + BW / 2, BY - 1.5 * S)], "#777")

    # the screen, on the right
    lx, ly0 = 600, 110
    out.append('<rect x="%d" y="%d" width="170" height="410" rx="6" fill="#f2f2f2" stroke="#888"/>' % (lx, ly0))
    out.append('<rect x="%d" y="%d" width="96" height="150" fill="#3a6ea5"/>' % (lx + 58, ly0 + 150))
    out.append('<text x="%d" y="%d" font-weight="bold">SPI screen</text>' % (lx + 8, ly0 + 18))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">ST7789 or ST7735, 3.3 V</text>' % (lx + 8, ly0 + 32))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">pin order varies: go by</text>' % (lx + 8, ly0 + 46))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">the labels on yours</text>' % (lx + 8, ly0 + 58))
    loop_y = {"BL": 420, "RST": 445, "DC": 470, "CS": 495}
    for i, (pin, pad, col) in enumerate(SCREEN):
        px, py = pad_xy(pad)
        y = loop_y.get(pin, py)
        out.append('<circle cx="%d" cy="%.1f" r="5" fill="%s"/>' % (lx, y, col))
        out.append('<text x="%d" y="%.1f" font-size="10">%s</text>' % (lx + 9, y + 4, pin))
        if pin not in loop_y:                   # the right column: straight across
            line(out, [(px + 7, py), (lx, y)], col)
        else:                                   # A0-A3: out to the left, under the board, up to the screen
            k = ["CS", "DC", "RST", "BL"].index(pin)
            xl, yb, xe = 100 + 12 * k, 676 - 12 * k, 540 - 12 * k
            line(out, [(px - 7, py), (xl, py), (xl, yb), (xe, yb), (xe, y), (lx, y)], col)
    gx, gy = pad_xy("GND")
    out.append('<circle cx="%.1f" cy="%.1f" r="3.5" fill="#222"/>' % (gx + 50, gy))
    ground(out, gx + 50, gy, down=False)

    # the key, under the board on its STEMMA QT cable
    kx, ky = 285, 485
    out.append('<rect x="%d" y="%d" width="145" height="110" rx="6" fill="#f2f2f2" stroke="#888"/>' % (kx, ky))
    out.append('<rect x="%d" y="%d" width="22" height="22" fill="#333"/>' % (kx + 61, ky + 46))
    out.append('<text x="%d" y="%d" font-weight="bold">ATECC608 breakout</text>' % (kx + 8, ky + 18))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">I2C 0x60, the key</text>' % (kx + 8, ky + 32))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">SDA1 41/22, SCL1 40/19</text>' % (kx + 8, ky + 100))
    for i, col in enumerate(("#222222", "#d0312d", "#2e7dd7", "#f0c020")):   # STEMMA QT: GND, V+, SDA, SCL
        x = BX + BW / 2 - 6 + i * 4
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%d" stroke="%s" stroke-width="2.5"/>' % (
            x, BY + BH - 0.9 * S, x, ky, col))
    out.append('<text x="%.1f" y="%d" fill="#555" font-size="9">STEMMA QT cable, from the port on the back</text>' % (BX + BW / 2 + 14, ky - 22))

    # the buttons, on the left: each to its pad and to GND
    for i, (d, lab, pad, col) in enumerate(BUTTONS):
        px, py = pad_xy(pad)
        by = py - 14                    # the pads are 30 px apart: each button just above its own
        sx = 172
        out.append('<rect x="%d" y="%.1f" width="34" height="20" rx="3" fill="#eee" stroke="%s" stroke-width="2"/>' % (sx, by - 10, col))
        out.append('<circle cx="%d" cy="%.1f" r="5" fill="%s"/>' % (sx + 17, by, col))
        out.append('<text x="%d" y="%.1f" text-anchor="end" font-weight="bold">%s</text>' % (sx - 42, by + 4, d))
        out.append('<text x="%d" y="%.1f" text-anchor="end" fill="#555" font-size="9">%s</text>' % (sx - 42, by + 15, lab))
        line(out, [(px - 7, py), (230, py), (230, by), (sx + 34, by)], col)
        line(out, [(sx, by), (sx - 16, by)], "#222")
        ground(out, sx - 16, by)

    notes = ["Screen: CS A0, DC A1, RST A2, BL A3; its SCL to SCK and its MOSI (or SDA) to MO.",
             "Its SCL is the SPI clock: never the QT Py's SCL pad. 3V3 to 3V, never 5V.",
             "Buttons to GND, read with the chip's own pull-ups: D0 (Reject) on SDA, D1 (Next) on TX, D2 (Sign) on SCL.",
             "Boot is not read. The QT Py has one GND pad: every ground symbol is that pad.",
             "The key is on the STEMMA QT port, a bus of its own; the SDA and SCL pads are not it."]
    for i, n in enumerate(notes):
        out.append('<text x="20" y="%d" fill="#333" font-size="10.5">%s</text>' % (712 + i * 16, n))
    out.append("</svg>")
    return "\n".join(out)


def link_svg():
    out = []
    head(out, 800, 650, "The QT Py cosigner, later: the link on a USB serial bridge",
         "The phone reaches only UART1. The QT Py's own USB-C stays empty. Screen, key and buttons as in wiring.svg.")
    used = {p for _a, p, _c in BRIDGE if p}
    board(out, used, "leave empty")
    ux, uy = BX + BW / 2 + 4.5 * S + 12, BY - 1.5 * S + 8
    out.append('<text x="%.1f" y="%.1f" fill="#d0312d" font-weight="bold" font-size="16">&#215;</text>' % (ux, uy + 6))

    # the phone and the bridge, on the left
    out.append('<rect x="30" y="66" width="140" height="44" rx="8" fill="#f2f2f2" stroke="#888"/>')
    out.append('<text x="100" y="85" text-anchor="middle" font-weight="bold">phone (the relay)</text>')
    out.append('<text x="100" y="100" text-anchor="middle" fill="#555" font-size="9">USB-C, OTG</text>')
    line(out, [(100, 110), (100, 200)], "#777")
    bx, by0 = 30, 200
    out.append('<rect x="%d" y="%d" width="140" height="295" rx="6" fill="#f2f2f2" stroke="#888"/>' % (bx, by0))
    out.append('<text x="%d" y="%d" font-weight="bold">USB serial bridge</text>' % (bx + 8, by0 + 18))
    out.append('<text x="%d" y="%d" fill="#555" font-size="9">CP2102N or CH340, 3.3 V logic</text>' % (bx + 8, by0 + 32))
    out.append('<text x="%d" y="%d" fill="#d0312d" font-size="9">&#215; not connected</text>' % (bx + 8, by0 + 280))
    ys = {"5V": 245, "GND": 285, "RXD": pad_xy("SDA")[1], "TXD": 365, "3V3": 400, "DTR": 430, "RTS": 460}
    ex = bx + 140
    for pin, pad, col in BRIDGE:
        y = ys[pin]
        out.append('<circle cx="%d" cy="%.1f" r="5" fill="%s"/>' % (ex, y, col))
        out.append('<text x="%d" y="%.1f" text-anchor="end" font-size="10">%s</text>' % (ex - 9, y + 4, pin))
        if pad is None:
            out.append('<text x="%d" y="%.1f" fill="#d0312d" font-weight="bold" font-size="13">&#215;</text>' % (ex + 8, y + 5))
            continue
        px, py = pad_xy(pad)
        if pin == "RXD":                        # straight across to SDA, UART1's TX
            line(out, [(ex, y), (px - 7, py)], col)
        elif pin == "TXD":                      # under the board to RX, UART1's RX
            line(out, [(ex, y), (215, y), (215, 505), (500, 505), (500, py), (px + 7, py)], col)
        elif pin == "5V":                       # over the top, through a Schottky, to the 5V pad
            line(out, [(ex, y), (200, y), (200, 140), (500, 140), (500, py), (px + 7, py)], col)
            dx = 350
            out.append('<rect x="%d" y="130" width="40" height="20" fill="#fff"/>' % (dx - 20))
            out.append('<polygon points="%d,131 %d,149 %d,140" fill="#222"/>' % (dx - 9, dx - 9, dx + 7))
            out.append('<line x1="%d" y1="130" x2="%d" y2="150" stroke="#222" stroke-width="3"/>' % (dx + 8, dx + 8))
            out.append('<text x="%d" y="124" text-anchor="middle" fill="#555" font-size="9">Schottky, e.g. 1N5817: bar to the QT Py</text>' % dx)
        elif pin == "GND":
            line(out, [(ex, y), (ex + 22, y)], col)
            ground(out, ex + 22, y)
    gx, gy = pad_xy("GND")
    line(out, [(gx + 7, gy), (gx + 40, gy)], "#222")
    ground(out, gx + 40, gy)

    notes = ["The bridge's TXD to RX (UART1 RX), its RXD to SDA (UART1 TX): D0 moves to A3, BL to 3V.",
             "Its 5V through a Schottky to the 5V pad: the QT Py runs from the phone's cable.",
             "DTR and RTS go nowhere, so the phone can't reset the QT Py or start its ROM flasher.",
             "MicroPython never puts its REPL on UART1. Flashing stays a person with the board,",
             "a cable in the QT Py's own USB-C and Boot held. Every ground symbol is the GND pad."]
    for i, n in enumerate(notes):
        out.append('<text x="20" y="%d" fill="#333" font-size="10.5">%s</text>' % (560 + i * 16, n))
    out.append("</svg>")
    return "\n".join(out)


def check_readme():
    """The README's pin table: one row per pad used, `| **pad** | S3 | Pico | what |`."""
    text = open(os.path.join(HERE, "README.md")).read()
    rows = re.findall(r"^\| \*\*([A-Z0-9]+)\*\* \| (\d+) \| (\d+) \| ([^|]+) \|$", text, re.M)
    got = {pad: (int(s3), int(pico), what.strip()) for pad, s3, pico, what in rows}
    want = {pad: gpio(pad) + (USE[pad],) for pad in USE}
    if got != want:
        bad = sorted(set(got) ^ set(want)) + sorted(p for p in set(got) & set(want) if got[p] != want[p])
        sys.exit("README.md's pin table disagrees with wiring.py: " + ", ".join(bad))


if __name__ == "__main__":
    check_readme()
    files = {"wiring.svg": wiring_svg() + "\n", "link.svg": link_svg() + "\n"}
    if "--check" in sys.argv:
        stale = [f for f, s in files.items()
                 if not os.path.exists(os.path.join(HERE, f)) or open(os.path.join(HERE, f)).read() != s]
        if stale:
            sys.exit("out of date, run wiring.py: " + ", ".join(stale))
        print("qtpy-cosigner wiring: the diagrams and the README's pin table agree with wiring.py")
    else:
        for f, s in files.items():
            with open(os.path.join(HERE, f), "w") as fh:
                fh.write(s)
            print("wrote", os.path.relpath(os.path.join(HERE, f), REPO))
