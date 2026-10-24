"""Silkscreen for picoquorum-key, front and back, drawn from one spec.

gen_pcb.py calls draw_silk() when it builds the board. To redraw the silkscreen on a board that
is already routed (without regenerating it):

  <KiCad python> tools/gen/silk_art.py [hardware/picoquorum-key/picoquorum-key.kicad_pcb]

That deletes every board-level (not part of a footprint) shape and text on F.SilkS and B.SilkS,
draws everything again and saves. Silkscreen only: no copper changes.

Fab limits kept everywhere: strokes >= 0.15 mm, text >= 1.0 mm high with a 0.15 mm stroke
(JLCPCB's legibility minimums). Back-side text is mirrored, so it reads correctly with the board
turned over left to right. The front panel hides silk under the glass (X 9-40, Y 8.5-26.1), so the
front art lives in the antenna band above it and in the strips around the glass. Filled shapes (the
logos, the 8-bit art) have no line: their narrowest part is what JLCPCB's 0.15 mm applies to.
"""
import math
import os
import re
import sys

import pcbnew

OX, OY = 100.0, 60.0
W, H = 44.0, 53.0
LINE = 0.2                      # default art stroke
MIN_LINE, MIN_TEXT = 0.15, 1.0  # JLCPCB legibility minimums (tests/test_silk.py checks these)

F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "lib", "picoquorum.pretty")


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def _shape(board, layer, kind, width=LINE, filled=False):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(kind)
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    s.SetFilled(filled)
    return s


def seg(board, layer, x0, y0, x1, y1, width=LINE):
    s = _shape(board, layer, pcbnew.SHAPE_T_SEGMENT, width)
    s.SetStart(pt(x0, y0)); s.SetEnd(pt(x1, y1))
    board.Add(s)


def poly(board, layer, points, width=LINE, close=False):
    pts = list(points) + ([points[0]] if close else [])
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        seg(board, layer, xa, ya, xb, yb, width)


def circle(board, layer, cx, cy, r, width=LINE, filled=False):
    s = _shape(board, layer, pcbnew.SHAPE_T_CIRCLE, width, filled)
    s.SetCenter(pt(cx, cy)); s.SetEnd(pt(cx + r, cy))
    board.Add(s)


def arc3(board, layer, p0, pm, p1, width=LINE):
    s = _shape(board, layer, pcbnew.SHAPE_T_ARC, width)
    s.SetArcGeometry(pt(*p0), pt(*pm), pt(*p1))
    board.Add(s)


def triangle(board, layer, cx, cy, h, direction="right", width=0.2):
    """Filled-look triangle (outline plus a centre stroke so it prints solid), h mm tall."""
    a = h / 2
    pts = {"right": [(cx - a * 0.8, cy - a), (cx - a * 0.8, cy + a), (cx + a * 0.8, cy)],
           "left": [(cx + a * 0.8, cy - a), (cx + a * 0.8, cy + a), (cx - a * 0.8, cy)]}[direction]
    s = _shape(board, layer, pcbnew.SHAPE_T_POLY, width, filled=True)
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        chain.Append(pt(x, y))
    chain.SetClosed(True)
    s.SetPolyShape(pcbnew.SHAPE_POLY_SET(chain))
    board.Add(s)


# Advance widths of KiCad's stroke font at size 1.0 (measured with pcbnew; objects SWIG creates
# after LoadBoard return unwrapped bounding boxes, so the layout uses this table instead).
_ADV = {'A': 0.857, 'B': 1.0, 'C': 1.0, 'D': 1.0, 'E': 0.905, 'F': 0.857, 'G': 1.0, 'H': 1.048, 'I': 0.476,
        'J': 0.762, 'K': 1.0, 'L': 0.81, 'M': 1.143, 'N': 1.048, 'O': 1.048, 'P': 1.0, 'Q': 1.048, 'R': 1.0,
        'S': 0.952, 'T': 0.762, 'U': 1.048, 'V': 0.857, 'W': 1.143, 'X': 0.952, 'Y': 0.857, 'Z': 0.952,
        'a': 0.905, 'b': 0.905, 'c': 0.857, 'd': 0.905, 'e': 0.857, 'f': 0.571, 'g': 0.905, 'h': 0.905,
        'i': 0.476, 'j': 0.476, 'k': 0.81, 'l': 0.524, 'm': 1.333, 'n': 0.905, 'o': 0.905, 'p': 0.905,
        'q': 0.905, 'r': 0.619, 's': 0.81, 't': 0.571, 'u': 0.905, 'v': 0.762, 'w': 1.048, 'x': 0.81,
        'y': 0.762, 'z': 0.81, '+': 1.238, '-': 1.238, '=': 1.238, '/': 1.048, '.': 0.476, ',': 0.476,
        ':': 0.476, '(': 0.667, ')': 0.667, ' ': 0.762}
_ADV.update({d: 0.952 for d in "0123456789"})


def text_width(s, size):
    """Inked width in mm: the advances minus the side bearing after the last letter."""
    return (sum(_ADV[c] for c in s) - 0.2) * size


def text(board, layer, s, x, y, size=1.0, thick=0.15, align="center"):
    """Stroke-font text at (x, y); align 'center' / 'left' / 'right' says which part of the ink sits
    at x. Back-layer text is mirrored (so 'left' is the left edge as seen from the back, which is
    the +X end on the board). Returns the board-mm box (x0, y0, x1, y1) the ink covers."""
    w = text_width(s, size)
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thick))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    if layer == B:
        t.SetMirrored(True)
    # ink spans [cx - w/2, cx + w/2] in board X for either side
    left_end_is_low_x = layer == F
    if align == "center":
        cx = x
    elif (align == "left") == left_end_is_low_x:
        cx = x + w / 2
    else:
        cx = x - w / 2
    t.SetPosition(pt(cx, y))
    board.Add(t)
    return (cx - w / 2, y - 0.55 * size, cx + w / 2, y + 0.55 * size)


# --- the brand (PicoQuorum's docs/BRAND.md) ---------------------------------------------------
# The mark and the name are the polygons in hardware/lib/picoquorum.pretty, copied from the
# PicoQuorum repository's hardware/console-s3/lib: the mark 5.0 mm tall, the name traced from
# Atkinson Hyperlegible Next Bold at 1 mm to the cap height. They go on as plain board shapes,
# scaled here, not as footprints.
CAP_EM = 0.669          # Atkinson Hyperlegible Next: its cap height in em
SITE = "PicoQuorum.app"


def _logo(name):
    return open(os.path.join(LIB, name + ".kicad_mod")).read()


def mark_ring():
    """The mark's ring of five dots: its radius, and how far its centre is below the mark's middle."""
    dots = [(float(y), float(e) - float(x)) for x, y, e in re.findall(
        r"\(fp_circle \(center ([\-\d.]+) ([\-\d.]+)\) \(end ([\-\d.]+) [\-\d.]+\) \(stroke \(width 0\)", _logo("PicoQuorum_Mark"))]
    top, low = min(y for y, _ in dots), max(y for y, _ in dots)       # the signed dots: -90 deg, 54 and 126
    r = (low - top) / (1 + math.sin(math.radians(54)))
    return r, top + r


def name_advance():
    """The name's width in mm at 1 mm to the cap height."""
    return float(re.search(r"([\d.]+) mm of advance", _logo("PicoQuorum_Name")).group(1))


def logo(board, layer, name, x, y, k):
    """A logo's shapes, its origin at (x, y), k times its size. On the back it is mirrored left to
    right, so it reads the right way round from the back; a ring keeps its 0.15 mm line."""
    sx = -1 if layer == B else 1
    src = _logo(name)
    for pts in re.findall(r"\(fp_poly \(pts (.*?)\) \(stroke", src):
        s = _shape(board, layer, pcbnew.SHAPE_T_POLY, 0, filled=True)
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for a, b in re.findall(r"\(xy ([\-\d.]+) ([\-\d.]+)\)", pts):
            chain.Append(pt(x + sx * float(a) * k, y + float(b) * k))
        chain.SetClosed(True)
        s.SetPolyShape(pcbnew.SHAPE_POLY_SET(chain))
        board.Add(s)
    for cx, cy, ex, w in re.findall(r"\(fp_circle \(center ([\-\d.]+) ([\-\d.]+)\) \(end ([\-\d.]+) [\-\d.]+\) \(stroke \(width ([\d.]+)\)", src):
        r, w = abs(float(ex) - float(cx)), float(w)
        r = r * k if w == 0 else (r + w / 2) * k - w / 2
        circle(board, layer, x + sx * float(cx) * k, y + float(cy) * k, r, w, filled=w == 0)


def lockup(board, layer, cx, cy, cap):
    """The mark left of the name, as on the panel: at a 26 px name the ring's radius is 12 px, its
    centre 13 px in from the left, the name 34 px in. Centred on (cx, cy), the name's middle."""
    r, dy = mark_ring()
    em = cap / CAP_EM
    k = 12 / 26 * em / r
    adv = name_advance() * cap
    width = 34 / 26 * em + adv
    sx = -1 if layer == B else 1           # seen from the back, its left is the board's +x
    left = cx - sx * width / 2
    logo(board, layer, "PicoQuorum_Mark", left + sx * 13 / 26 * em, cy - dy * k, k)
    logo(board, layer, "PicoQuorum_Name", left + sx * (34 / 26 * em + adv / 2), cy, cap)


# A nod to Adventure (Atari 2600, 1980), as on PicoQuorum's console-s3: an 8-bit key beside U2, the
# key chip, and a dragon facing it, guarding it; drawn in the game's manner, not copied from it.
# Rows top to bottom, '#' a 0.3 mm square of silk.
DRAGON = ("....###.", "#####.#.", "....###.", ".....#..", ".....#..", "....##..", "...###..", "..####..",
          ".#####..", ".#####..", ".#####..", "..####..", "...###..", "....##..", ".....#..", ".....#..",
          ".....#..", ".....#..", ".....#.#", ".....###")
KEY = (".##......", "#..######", "#..#..#.#", ".##......")
PIXEL = 0.3
ART = [(KEY, 36.0, 33.0), (DRAGON, 40.7, 32.1)]   # each one's top left corner


def pixels(board, rows, x0, y0):
    """Each run of '#' in a row as one filled rectangle."""
    for j, row in enumerate(rows):
        for m in re.finditer(r"#+", row):
            s = _shape(board, F, pcbnew.SHAPE_T_RECT, 0, filled=True)
            s.SetStart(pt(x0 + m.start() * PIXEL, y0 + j * PIXEL))
            s.SetEnd(pt(x0 + m.end() * PIXEL, y0 + (j + 1) * PIXEL))
            board.Add(s)


# --- front art ------------------------------------------------------------------------------
def wordmark(board):
    """The mark and the name in the antenna band, over a rule that carries PicoQuorum.app."""
    lockup(board, F, 22.0, 2.9, 2.4)
    y = 6.1
    box = text(board, F, SITE, 22.0, y, size=1.0)
    seg(board, F, 3.0, y, box[0] - 0.9, y)
    seg(board, F, box[2] + 0.9, y, 41.0, y)
    for x in (3.0, 41.0):
        circle(board, F, x, y, 0.45, 0.15, filled=True)


def panel_marks(board):
    """Corner ticks 0.4 mm outside the glass (X 9-40, Y 8.5-26.1): where to set the panel."""
    x0, y0, x1, y1 = 9.0, 8.5, 40.0, 26.1
    g = 0.4
    for (cx, cy, sx, sy) in ((x0 - g, y0 - g, 1, 1), (x0 - g, y1 + g, 1, -1)):
        poly(board, F, [(cx + sx * 2.0, cy), (cx, cy), (cx, cy + sy * 2.0)], 0.15)
    for cy in (y0 - g, y1 + g):                  # right side: C3's pad sits just past the glass corner
        seg(board, F, x1 - 2.0, cy, x1, cy, 0.15)


def button_labels(board):
    """BOOT and RESET, each under its switch (SW6 at Y 39, SW7 at Y 46) and with a small glyph."""
    # BOOT: a lightning bolt (download mode)
    box = text(board, F, "BOOT", 38.1, 42.5, align="right")
    bx, by = box[0] - 0.9, 42.5
    poly(board, F, [(bx + 0.25, by - 0.5), (bx - 0.2, by + 0.05), (bx + 0.2, by + 0.05), (bx - 0.25, by + 0.5)], 0.18)
    # RESET: a circular arrow
    box = text(board, F, "RESET", 38.1, 49.7, align="right")
    rx, ry, r = box[0] - 1.15, 49.7, 0.42
    arc3(board, F, (rx + r * math.cos(math.radians(-60)), ry + r * math.sin(math.radians(-60))),
         (rx - r, ry), (rx + r * math.cos(math.radians(60)), ry + r * math.sin(math.radians(60))), 0.16)
    poly(board, F, [(rx + 0.5, ry - 0.62), (rx + 0.21, ry - 0.36), (rx + 0.55, ry - 0.2)], 0.15)


def usb_label(board):
    """'USB-C 5V' with an arrow pointing at the connector."""
    text(board, F, "USB-C 5V", 14.4, H - 2.0, align="right")
    triangle(board, F, 15.3, H - 2.0, 0.7, "right")


def hole_rings(board):
    """A silk ring round each M2 hole marks the screw-head keep-out."""
    for x, y in ((3.0, 29.5), (41.0, 29.5), (3.0, H - 3.0), (41.0, H - 3.0)):
        circle(board, F, x, y, 2.0, 0.2)


def key_and_dragon(board):
    """The 8-bit key right of U2, and the dragon right of it, above BOOT."""
    for rows, x, y in ART:
        pixels(board, rows, x, y)


# --- back art -------------------------------------------------------------------------------
def title_block(board):
    """The mark, the name, the revision and a short legend on the empty left half of the back
    (mirrored)."""
    x0, x1 = 6.0, 20.5          # clear of the module (X >= 22) and of the left mounting hole ring.
                                # Seen from the back, x1 is the left edge: text is anchored there.
    cx = (x0 + x1) / 2
    r, dy = mark_ring()
    logo(board, B, "PicoQuorum_Mark", cx, 4.6 - dy * 0.9, 0.9)
    logo(board, B, "PicoQuorum_Name", cx, 9.6, 1.45)
    seg(board, B, x0, 12.0, x1, 12.0, 0.2)
    text(board, B, "KEY, REV A", x1, 14.0, align="left")
    text(board, B, SITE, x1, 16.0, align="left")
    seg(board, B, x0, 18.0, x1, 18.0, 0.15)
    text(board, B, "R12+R13 = USB DATA", x1, 20.0, align="left")
    text(board, B, "remove: power-only", x1, 21.8, align="left")
    text(board, B, "BOOT+RESET = FLASH", x1, 24.0, align="left")


def back_key(board):
    """A big key outline under the module, with its caption beside the tip (seen from the back)."""
    kx, ky = 36.5, 29.3                       # bow centre (the bow is on the left when the board is turned over)
    for r in (1.9, 0.9):
        circle(board, B, kx, ky, r, 0.25)
    seg(board, B, kx - 1.9, ky, kx - 13.0, ky, 0.25)           # shaft
    for tx, tl in ((kx - 10.5, 1.7), (kx - 12.5, 2.4)):         # teeth
        seg(board, B, tx, ky, tx, ky + tl, 0.25)
    text(board, B, "ONE OWNER", 14.5, ky - 0.6)
    text(board, B, "ONE KEY", 14.5, ky + 1.2)


def test_pads(board):
    """[(name, x, y)] for the back test pads. Read before any item is created: after that, KiCad 10.0.6's
    Python binding hands back unwrapped footprint objects."""
    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith("TP") and ref[2:].isdigit():
            name = list(fp.Pads())[0].GetNetname().lstrip("/").replace("UART_", "").replace("I2C_", "")
            pos = fp.GetPosition()
            out.append((name, pcbnew.ToMM(pos.x) - OX, pcbnew.ToMM(pos.y) - OY))
    return out


def test_pad_labels(board, tps):
    """Net names under the twelve back test pads, mirrored."""
    for name, x, y in tps:
        text(board, B, name, x, y + 1.9)
    text(board, B, "TEST PADS", 22.0, 43.0, align="center")


# --- entry points ---------------------------------------------------------------------------
def clear_silk(board):
    """Delete the board-level shapes and text on F.SilkS / B.SilkS (footprint silk stays)."""
    old = [d for d in board.GetDrawings()
           if d.GetLayer() in (F, B) and d.GetClass() in ("PCB_SHAPE", "PCB_TEXT")]
    for d in old:
        board.Remove(d)
    return len(old)


def draw_silk(board, tps=None):
    """Draw everything. tps: test_pads(board), read by the caller before it created anything."""
    if tps is None:
        tps = test_pads(board)
    wordmark(board)
    panel_marks(board)
    button_labels(board)
    usb_label(board)
    hole_rings(board)
    key_and_dragon(board)
    title_block(board)
    back_key(board)
    test_pad_labels(board, tps)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "hardware/picoquorum-key/picoquorum-key.kicad_pcb"
    board = pcbnew.LoadBoard(path)
    tps = test_pads(board)
    n = clear_silk(board)
    draw_silk(board, tps)
    board.Save(path)
    print(f"silk_art: removed {n} old items, drew the silkscreen; saved {path}")
