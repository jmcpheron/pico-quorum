#!/usr/bin/env python3
"""Sketches of ways to lock key-c into a dock: top views of the key and its dock, as SVG.

    python3 hardware/key-pcb/key-c-usbc/lock/gen_lock.py

Writes lock-*.svg next to this file. These are concept sketches to compare ideas, not
drawings to build from. Nothing here changes the board as ordered (key-c-usbc.kicad_pcb).

Units are mm. The key is drawn parts side up, H1 at the top (y = 0) and the USB-C end at the
bottom (y = 36), the way it slides down into a dock. Part positions are the ordered board's,
from 3d/print_mockup.py, moved into this frame.
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

L, R = 36.0, 2.0          # board length and corner radius, as ordered
CLEAR = 0.3               # dock clearance round the key

PCB, PCB_EDGE = "#1d4f91", "#0e2d57"
SILK = "#ffffff"
CHIP, PIN = "#1b1b1b", "#b8bcc2"
SHELL, SHELL_EDGE = "#c8ccd2", "#7d828a"
DOCK, DOCK_EDGE, FLOOR = "#c3c6cc", "#6b6f76", "#8f939a"
LOCK, LOCK_EDGE = "#e8772e", "#9c4613"
PLUG, INK, PAPER = "#2b2b2b", "#222222", "#ffffff"

# chip and small-part bodies (x from the centre line, y from the H1 end, size x, size y)
BODIES = [(0.00, 18 - 2.675, 4.90, 3.90),    # U1 ATECC608C, SOIC-8
          (0.00, 18 + 5.500, 2.90, 1.60),    # U2 USBLC6, SOT-23-6
          (3.75, 18 - 0.200, 1.00, 0.50),    # C1
          (0.00, 18 + 2.500, 0.50, 1.00),    # C2
          (-2.40, 18 + 7.600, 0.50, 1.00),   # R1
          (2.15, 18 + 8.000, 0.50, 1.00)]    # R2
SHELL_W, SHELL_L = 8.94, 7.8                 # J1's shell, flush with the USB-C edge


# ---- notch profiles: (depth into the board, y) pairs in order of increasing y ----

def arc(cx, cy, r, a0, a1, n=12):
    return [(cx + r * math.cos(a), cy + r * math.sin(a))
            for a in (a0 + (a1 - a0) * i / n for i in range(n + 1))]


def round_notch(c, r):
    """A half-round detent of radius r centred at y = c."""
    return [(math.sqrt(max(r * r - (y - c) ** 2, 0)), y)
            for y in (c - r + 2 * r * i / 16 for i in range(17))]


def square_notch(c, w, d, rc=1.0):
    """A w-wide, d-deep notch. Its inside corners keep the router's radius rc
    (1.0 mm with JLCPCB's standard 2 mm bit)."""
    y0, y1 = c - w / 2, c + w / 2
    pts = [(0, y0)]
    pts += [(d - rc + rc * math.sin(a), y0 + rc - rc * math.cos(a))
            for a in (math.pi / 2 * i / 6 for i in range(7))]
    pts += [(d - rc + rc * math.cos(a), y1 - rc + rc * math.sin(a))
            for a in (math.pi / 2 * i / 6 for i in range(7))]
    return pts + [(0, y1)]


def barb_notch(c, w, d, rc=0.4):
    """A ramp on the H1 side and a square catch face on the USB-C side.
    rc 0.4 needs a 0.8 mm bit, asked for in the order notes."""
    y0, y1 = c - w / 2, c + w / 2
    pts = [(0, y0), (d, y1 - rc - 0.6)]
    pts += [(d - rc + rc * math.cos(a), y1 - rc + rc * math.sin(a))
            for a in (math.pi / 2 * i / 6 for i in range(7))]
    return pts + [(0, y1)]


# ---- the key ----

def key_outline(w, left=None, right=None, step=None):
    """Board outline as points. left/right are notch profiles; step = (sw, sl) cuts a corner
    out of the USB-C end on the left, for keying."""
    pts = arc(R, R, R, math.pi, 1.5 * math.pi)                       # top-left corner
    pts += arc(w - R, R, R, 1.5 * math.pi, 2 * math.pi)              # top-right corner
    for d, y in right or []:
        pts.append((w - d, y))
    pts += arc(w - R, L - R, R, 0, 0.5 * math.pi)                    # bottom-right corner
    if step:
        sw, sl = step
        pts += [(sw + 0.5, L), (sw, L - 0.5), (sw, L - sl + 1.0)]
        pts += arc(sw - 1.0, L - sl + 1.0, 1.0, 0, -0.5 * math.pi)   # inside corner, R1.0
        pts += [(0, L - sl)]
    else:
        pts += arc(R, L - R, R, 0.5 * math.pi, math.pi)              # bottom-left corner
    for d, y in reversed(left or []):
        pts.append((d, y))
    return pts


def poly(pts, fill, stroke, sw=0.15, extra=""):
    p = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
    return f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def rect(x, y, w, h, fill, stroke="none", sw=0.15, rx=0, extra=""):
    return (f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')


def text(x, y, s, size=2.2, anchor="middle", weight="normal", fill=INK):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}" fill="{fill}" font-family="Helvetica, Arial, sans-serif">'
            f'{s}</text>')


def key(ox, oy, w, **notches):
    """The key at (ox, oy): board, H1, chips, small parts and J1's shell."""
    cx = w / 2
    g = [f'<g transform="translate({ox},{oy})">',
         poly(key_outline(w, **notches), PCB, PCB_EDGE, 0.2),
         f'<circle cx="{cx}" cy="4" r="1.5" fill="{PAPER}" stroke="{PCB_EDGE}" stroke-width="0.15"/>']
    ux, uy, uw, uh = BODIES[0]
    for i in range(4):                                               # U1's pins, top and bottom
        px = cx + ux - 1.905 + 1.27 * i - 0.2
        g.append(rect(px, uy - uh / 2 - 0.9, 0.4, 0.9, PIN))
        g.append(rect(px, uy + uh / 2, 0.4, 0.9, PIN))
    for x, y, sx, sy in BODIES:
        g.append(rect(cx + x - sx / 2, y - sy / 2, sx, sy,
                      CHIP if sx > 1.5 else "#a0703c", rx=0.1))
    g.append(text(cx, uy + 0.7, "U1", 1.6, fill="#bbbbbb"))
    g.append(rect(cx - SHELL_W / 2, L - SHELL_L, SHELL_W, SHELL_L, SHELL, SHELL_EDGE, rx=0.5))
    g.append(rect(cx - 3.6, L - 0.9, 7.2, 0.5, "#555a61", rx=0.25))  # the socket mouth
    g.append(text(cx, L - SHELL_L / 2 + 0.8, "J1", 1.8, fill="#5a5f66"))
    g.append(text(cx, 9.4, "key-c", 1.8, fill=SILK))
    g.append("</g>")
    return "\n".join(g)


def dock(ox, oy, w, top=14.0, wall=4.5):
    """The dock round the key's USB-C end: two side walls, a floor and a back wall holding the
    console's USB-C plug. (ox, oy) is the key's origin."""
    x0, x1 = ox - CLEAR - wall, ox + w + CLEAR + wall
    back = oy + L + CLEAR
    cx = ox + w / 2
    return "\n".join([
        rect(x0, oy + top, x1 - x0, back + 9 - oy - top, DOCK, DOCK_EDGE, 0.2, rx=1.2),
        rect(ox - CLEAR, oy + top, w + 2 * CLEAR, L + CLEAR - top, FLOOR),
        rect(cx - 6.2, back, 12.4, 5.2, PLUG, rx=1.0),                 # the plug's overmould
        rect(cx - 2.2, back + 5.2, 4.4, 4.0 + 3.5, "#3a3a3a", rx=0.8),  # its cable
        text(cx, back + 3.1, "USB-C plug", 1.6, fill="#dddddd"),
    ])


def label(x, y, s, tx, ty, anchor="start"):
    """A leader line from (x, y) to a note at (tx, ty)."""
    return (f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{tx:.2f}" y2="{ty - 0.7:.2f}" '
            f'stroke="{INK}" stroke-width="0.15"/>' + text(tx, ty, s, 1.9, anchor))


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w * 8:.0f}" height="{h * 8:.0f}">\n'
            f'<title>{title}</title>\n'
            f'{rect(0, 0, w, h, PAPER)}\n{body}\n</svg>\n')


def write(name, content):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(content)
    print("wrote", name)


# ---- the options ----

W = 20.0                                   # the wider board
NC = 24.0                                  # notch centre: 12 mm back from the USB-C edge

OPTIONS = {
    "A": dict(title="A · two round detents", w=W,
              left=round_notch(NC, 1.5), right=round_notch(NC, 1.5)),
    "B": dict(title="B · keyed corner + one detent", w=W,
              step=(3.0, 6.0), right=round_notch(NC, 1.5)),
    "C": dict(title="C · square notches + lid with prongs", w=W,
              left=square_notch(NC, 4.0, 2.0), right=square_notch(NC, 4.0, 2.0)),
    "D": dict(title="D · barbs + release tabs", w=W,
              left=barb_notch(NC, 4.0, 2.0), right=barb_notch(NC, 4.0, 2.0)),
    "E": dict(title="E · pin through H1 (P2 as ordered)", w=16.0),
}


def notches(o):
    return {k: o[k] for k in ("left", "right", "step") if k in o}


def finger(ox, oy, w, side, tooth, y0=16.6, y1=31.0):
    """A cantilever cut into a side wall: fixed at the USB-C end (y1), free at y0, with a
    tooth on its inner face at the notch. side is -1 for left, +1 for right."""
    fw, slot = 1.3, 0.8
    if side > 0:
        inner = ox + w + CLEAR
        fx, sx = inner, inner + fw
    else:
        inner = ox - CLEAR
        fx, sx = inner - fw, inner - fw - slot
    g = [rect(sx, oy + y0 - slot, slot, y1 - y0 + slot, FLOOR),     # the slot behind it
         rect(min(fx, inner), oy + y0 - slot, fw, slot, FLOOR),      # and across its free end
         rect(fx, oy + y0, fw, y1 - y0, LOCK, LOCK_EDGE, 0.12)]
    g.append(poly([(inner + side * -x, oy + y) for x, y in tooth], LOCK, LOCK_EDGE, 0.12))
    return "\n".join(g)


def figure(k):
    o = OPTIONS[k]
    w = o["w"]
    kx, ky = 8.0, 9.0                         # the key on its own, left
    dx, dy = 60.0, 9.0                        # the key in its dock, right
    nx = dx + w + 9                           # notes beside the dock
    below = ky + L + 6                        # notes under the lone key
    body = [text(4, 4.6, o["title"], 2.8, "start", "bold"),
            text(kx + w / 2, 7.4, "the key", 1.9),
            text(dx + w / 2, 7.4, "in the dock, locked", 1.9),
            key(kx, ky, w, **notches(o))]
    if k != "E":
        body.append(dock(dx, dy, w))
    body.append(key(dx, dy, w, **notches(o)))
    notes = []
    if k == "A":
        bump = [(math.sqrt(max(1.25 ** 2 - (y - NC) ** 2, 0)), y)
                for y in (NC - 1.25 + 2.5 * i / 12 for i in range(13))]
        body += [finger(dx, dy, w, +1, bump), finger(dx, dy, w, -1, bump)]
        notes += [label(kx + w - 0.5, ky + NC + 1, "R1.5 half-round notch, both sides", kx, below),
                  label(dx + w + 1, dy + 20, "printed flex finger, in each wall", nx, dy + 16),
                  label(dx + w + 0.6, dy + NC, "its bump clicks into the notch", nx, dy + NC + 4)]
    elif k == "B":
        bump = [(math.sqrt(max(1.25 ** 2 - (y - NC) ** 2, 0)), y)
                for y in (NC - 1.25 + 2.5 * i / 12 for i in range(13))]
        body.append(finger(dx, dy, w, +1, bump))
        body.append(rect(dx - CLEAR, dy + L - 6.0 + CLEAR, 3.0, 6.0, LOCK, LOCK_EDGE, 0.12))
        notes += [label(kx + 1.5, ky + L - 2, "3 x 6 mm corner step", kx, below),
                  label(kx + w - 0.5, ky + NC + 1, "one detent, on the other side", kx, below + 3.5),
                  label(dx + 1.5, dy + L - 2.5, "a block fills the step,", nx, dy + 30),
                  text(nx, dy + 32.6, "so upside down it won't seat", 1.9, "start"),
                  label(dx + w + 0.6, dy + NC, "one flex finger clicks in", nx, dy + 20)]
    elif k == "C":
        # the lid, hinged at the dock's back wall, swung closed over the key
        body.append(rect(dx - 5.5, dy + 19.0, w + 11, 10.0, LOCK, LOCK_EDGE, 0.15, rx=1.0,
                         extra='fill-opacity="0.35" stroke-dasharray="0.8 0.5"'))
        for x in (dx + 0.15, dx + w - 1.65):
            body.append(rect(x - (CLEAR if x < dx + 1 else -CLEAR), dy + NC - 1.25, 1.5, 2.5,
                             LOCK, LOCK_EDGE, 0.12, rx=0.3))
        body.append(rect(dx + w + 4.3, dy + 19.0, 1.2, 10.0, "#7a3a12", rx=0.4))  # hinge
        notes += [label(kx + w - 1, ky + NC + 1, "4 x 2 mm notches, R1.0 inside corners", kx, below),
                  label(dx + w + 4, dy + 20, "lid swings over the key", nx, dy + 14),
                  label(dx + w - 0.5, dy + NC, "its prongs drop into the notches", nx, dy + NC + 1),
                  label(dx + w + 4, dy + 28.8, "hinge", nx, dy + 33)]
        body.append(section_c(nx + 15, dy + 50))
    elif k == "D":
        tooth = [(0, NC - 1.6), (1.8, NC + 1.4), (1.8, NC + 1.8), (0, NC + 1.8)]
        body += [finger(dx, dy, w, +1, tooth), finger(dx, dy, w, -1, tooth)]
        for side in (-1, +1):
            x = dx + w + CLEAR + 1.3 if side > 0 else dx - CLEAR - 1.3 - 4.0
            body.append(rect(x, dy + 15.8, 4.0, 1.6, LOCK, LOCK_EDGE, 0.12, rx=0.5))
        notes += [label(kx + w - 1, ky + NC + 1.5, "ramp to the H1 side, square face to J1", kx, below),
                  label(dx + w + 5, dy + 16.6, "pull both tabs out to release", nx, dy + 12),
                  label(dx + w + 1, dy + NC + 1.5, "the tooth catches the square face", nx, dy + NC + 4)]
    elif k == "E":
        cx = dx + w / 2
        body.insert(3, rect(dx - 4, dy - 3, w + 8, L + 12, DOCK, DOCK_EDGE, 0.2, rx=1.2))
        body.insert(4, rect(dx - CLEAR, dy - CLEAR, w + 2 * CLEAR, L + 2 * CLEAR, FLOOR))
        body.append(rect(cx - 6.2, dy + L + CLEAR, 12.4, 5.2, PLUG, rx=1.0))
        body.append(text(cx, dy + L + 3.4, "USB-C plug", 1.6, fill="#dddddd"))
        body.append(rect(dx - 3.5, dy - 2.5, w + 7, 10.0, LOCK, LOCK_EDGE, 0.15, rx=1.0,
                         extra='fill-opacity="0.35" stroke-dasharray="0.8 0.5"'))
        body.append(f'<circle cx="{cx}" cy="{dy + 4}" r="1.3" fill="{LOCK}" '
                    f'stroke="{LOCK_EDGE}" stroke-width="0.15"/>')
        notes += [label(kx + w / 2 + 1.5, ky + 4, "H1, 3 mm, already on P2", kx + w + 3, ky + 3),
                  text(kx, below, "no notches: 16 mm wide, as ordered", 1.9, "start"),
                  label(cx + 1.3, dy + 4, "spring pin through H1", nx, dy + 10),
                  label(dx + w + 3.5, dy + 0, "hinged flap over the key's end", nx, dy + 3)]
    body += notes
    return svg(132, 64, "\n".join(body), o["title"])


def section_c(x, y):
    """C, cut across the key at the notches: the lid's prongs go down past the board."""
    t, w = 1.6, 16.0                       # board thickness; its width at the notches
    g = [text(x, y - 7.0, "section at the notches", 1.7),
         rect(x - 14, y - 5.8, 28, 1.4, LOCK, LOCK_EDGE, 0.12, rx=0.4),          # the lid
         rect(x - w / 2, y - 2.0, w, t, PCB, PCB_EDGE, 0.15),                    # the board
         rect(x - 14, y - 0.4, 28, 2.0, DOCK, DOCK_EDGE, 0.15)]                  # dock floor
    for px in (x - w / 2 - 1.8, x + w / 2 + 0.3):
        g.append(rect(px, y - 4.4, 1.5, 5.4, LOCK, LOCK_EDGE, 0.12))             # the prongs
    return "\n".join(g)


def overview():
    body = [text(4, 5, "Ways to lock key-c into a dock (top view, parts side, USB-C end down)",
                 2.6, "start", "bold")]
    for i, k in enumerate("ABCDE"):
        o = OPTIONS[k]
        x = 6 + i * 29 + (2 if k == "E" else 0)
        body.append(key(x, 12, o["w"], **notches(o)))
        body.append(text(x + o["w"] / 2, 53, k, 3.2, weight="bold"))
        body.append(text(x + o["w"] / 2, 56.5, o["title"].split("· ")[1], 1.55))
    return svg(152, 60, "\n".join(body), "key-c lock options")


if __name__ == "__main__":
    write("lock-overview.svg", overview())
    for k in OPTIONS:
        write(f"lock-{k}.svg", figure(k))
