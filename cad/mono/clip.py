"""A clip that holds a 3-pin strip of 2.54 mm header on Mono's SWD pads (TP1 SWCLK, TP2 GND, TP3 SWDIO),
in place of pogo pins. It slides onto the board's left edge (the front facing you), 21.5 mm up from the
USB-C's end, and stops on that edge and on the bottom-left corner, which puts the pins on the pads.

Run: uv run --python 3.11 --with cadquery --with matplotlib python cad/mono/clip.py

Writes out/: mono_clip.stl, as it prints (its side on the bed, no support), and mono_clip.png and
mono_clip_back.png, the clip on board.py's model with a header in it.

How it works:
- The header goes in through the window in the front arm, long pins first, into a pocket in the back jaw.
  Its plastic sits on a ledge there; the long pins stand out of the back for jumper wires, the short ones
  point at the board. The pins are the only thing that touches the board's back.
- The front arm is the spring: two bumps, one either side of the pads' row, press the front 0.6 mm
  further than a 1.6 mm board leaves room for.
- A wall takes the board's left edge, and a 45-degree face at the end of the long leg takes the
  bottom-left corner's round.

Read from the routed board: the pads' places, and the parts on the front under the arm, which the script
checks the arm clears. The header's sizes are the usual strip's (HEADER); measure yours.

The model's frame is board.py's: x from the left edge, y up from the bottom edge, the front at z = 0,
the back at z = -T.
"""
import importlib.util
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("board", os.path.join(HERE, "board.py"))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
G, T, OUT = B.G, B.T, B.OUT

PADS = ("TP1", "TP2", "TP3")         # SWCLK, GND, SWDIO, from the edge in
HEADER = dict(pitch=2.54, body=2.54, short=3.0, long=6.0, pin=0.64)     # a breakaway strip: plastic 2.54 square
FIT = 0.15                           # room round the header's plastic, each side
PRESS = 0.6                          # how far the board lifts the bumps
HALF = 6.0                           # the jaws reach this far either side of the pads' row
WINDOW = 1.8                         # the window's half-height: the header's plastic and room to push it

# The profile, across the board's edge (x, z). The back jaw, from the back's side:
ZB = -T
Z_IN = ZB - 1.0                      # its face: the pins stand 1 mm proud of it
Z_LEDGE = ZB - HEADER["short"] - HEADER["body"]     # the ledge the plastic sits on, the pins' tips on the back
Z_OUT = Z_LEDGE - 1.0                # the jaw's outside: 5 mm of the long pins stand out of it
X_END = 12.0
# the spine and the wall the board's edge stops on
X_SPINE, X_ROOT, Z_WALL = -8.0, -5.0, 0.3
# the front arm: 1.2 thick, its bumps 1.7 under it
Z_ARM, Z_TOP, Z_BUMP = 1.1, 2.3, -PRESS
X_TIP = 11.8


def prism(points, y0, y1):
    """An (x, z) outline, from y0 to y1."""
    return (cq.Workplane("XY").polyline(points).close().extrude(y1 - y0)
            .rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y1, 0)))


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def pads(fps):
    """The pads' (x, y), and that they are one row at the header's pitch."""
    at = {fp["ref"]: B.place(fp, 0, 0) for fp in fps if fp["ref"] in PADS}
    xs, ys = [at[p][0] for p in PADS], [at[p][1] for p in PADS]
    assert all(abs(y - ys[0]) < 1e-6 for y in ys), "the pads are not in one row"
    assert all(abs(b - a - HEADER["pitch"]) < 1e-6 for a, b in zip(xs, xs[1:])), "the pads are not 2.54 mm apart"
    return xs, ys[0]


def clip(xs, yp):
    xc, half = (xs[0] + xs[-1]) / 2, len(xs) * HEADER["pitch"] / 2 + FIT
    xb = xc                              # the bumps, over the middle pin
    jaws = prism([
        (X_SPINE, Z_OUT), (X_END, Z_OUT), (X_END, Z_IN),
        (X_END - 1.0, ZB - 0.2), (X_END - 1.8, ZB - 0.2), (X_END - 1.8, Z_IN),      # a ramp that lifts the board's edge to the pins' tips
        (0, Z_IN), (0, Z_WALL),                                                     # the wall the edge stops on
        (X_ROOT + 0.5, Z_WALL), (X_ROOT, Z_WALL + 0.25), (X_ROOT, Z_ARM - 0.25), (X_ROOT + 0.5, Z_ARM),
        (xb - 1.3, Z_ARM), (xb - 0.5, Z_BUMP), (xb + 0.5, Z_BUMP), (xb + 2.6, Z_ARM),   # the bump, its long slope toward the board coming in
        (X_TIP - 1.3, Z_ARM), (X_TIP, Z_ARM + 0.9), (X_TIP, Z_TOP + 0.9), (X_TIP - 1.6, Z_TOP),   # the tip turned up, for the board and a nail
        (X_SPINE, Z_TOP),
    ], yp - HALF, yp + HALF)
    b = HEADER["body"] / 2 + FIT
    jaws = jaws.cut(box(xc - half, xc + half, yp - b, yp + b, Z_LEDGE, Z_IN + 1))               # the plastic's pocket
    jaws = jaws.cut(box(xc - half, xc + half, yp - 0.6, yp + 0.6, Z_OUT - 1, Z_LEDGE + 1))      # the long pins' slot
    jaws = jaws.cut(box(xc - half - 0.3, xc + half + 0.3, yp - WINDOW, yp + WINDOW, Z_BUMP - 0.5, Z_TOP + 2))   # the window, through the arm and the bump under it

    # the leg down the edge to the corner, and the face that takes the corner's round at its middle
    y_end, x_cap = -4.0, 4.5
    leg = box(X_SPINE, 0, y_end, yp - HALF, ZB - 1.5, Z_WALL)
    r = G.CORNER
    k = (2 - 2 ** 0.5) * r                   # the face is x + y = k
    cap = (cq.Workplane("XY").polyline([(0, k), (x_cap, k - x_cap), (x_cap, y_end), (0, y_end)]).close()
           .extrude(Z_WALL - (ZB - 1.5)).translate((0, 0, ZB - 1.5)))
    return jaws.union(leg).union(cap), (xc, half)


def header(xs, yp):
    """The strip, seated: for the pictures."""
    h, p = HEADER["body"] / 2, HEADER["pin"] / 2
    s = box(xs[0] - HEADER["pitch"] / 2, xs[-1] + HEADER["pitch"] / 2, yp - h, yp + h, Z_LEDGE, Z_LEDGE + HEADER["body"])
    for x in xs:
        s = s.union(box(x - p, x + p, yp - p, yp + p, Z_LEDGE - HEADER["long"], ZB))
    return s


def under_arm(fps, yp, xb):
    """The fitted parts on the front under the arm: (ref, height, under a bump)."""
    out = []
    for fp in fps:
        if fp["side"] != "F" or fp["dnp"] or fp["ref"].startswith(B.SKIP) or not fp["body"]:
            continue
        x0, y0, x1, y1 = fp["body"]
        cs = [B.place(fp, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        ax0, ax1, ay0, ay1 = min(c[0] for c in cs), max(c[0] for c in cs), min(c[1] for c in cs), max(c[1] for c in cs)
        if ax0 < X_TIP and ay0 < yp + HALF and ay1 > yp - HALF:
            out.append((fp["ref"], G.HEIGHT.get(fp["name"], 1.0), ax0 < xb + 2.6 and ax1 > xb - 1.3))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    fps = B.footprints()
    xs, yp = pads(fps)
    body, (xc, half) = clip(xs, yp)
    assert len(body.val().Solids()) == 1, "the clip is not one solid"
    way = box(xs[0] - HEADER["pitch"] / 2, xs[-1] + HEADER["pitch"] / 2, yp - HEADER["body"] / 2, yp + HEADER["body"] / 2, Z_LEDGE, Z_TOP + 3)
    assert body.intersect(way).val().Volume() < 1e-6, "something is in the header's way in"
    near = under_arm(fps, yp, xc)
    for ref, h, bump in near:
        assert not bump, f"{ref} is under a bump"
        assert h < Z_ARM - 0.3, f"{ref}, {h} mm, is too tall for the arm"
    # as it prints: the jaws' end on the bed, the leg up, the corner's face a 45-degree overhang
    flat = body.rotate((0, 0, 0), (1, 0, 0), -90).translate((0, 0, yp + HALF))
    cq.exporters.export(flat, os.path.join(OUT, "mono_clip.stl"), tolerance=0.01, angularTolerance=0.1)

    pcb, bits, pins = B.board(fps), B.parts(fps), header(xs, yp)
    scene = [(pcb, (0.18, 0.42, 0.25)), (bits, (0.75, 0.75, 0.72)), (body, (0.95, 0.55, 0.15)), (pins, (0.1, 0.1, 0.1))]
    # the bottom third of the board is enough to see it by
    crop = box(-20, G.W + 20, -20, 40, -30, 30)
    scene = [(s.intersect(crop), c) for s, c in scene]
    B.picture(scene, os.path.join(OUT, "mono_clip.png"), size=1100)
    turn = lambda s: s.rotate((G.W / 2, 0, 0), (G.W / 2, 1, 0), 180)          # the back toward the eye
    B.picture([(turn(s), c) for s, c in scene], os.path.join(OUT, "mono_clip_back.png"), size=1100)

    bb = flat.val().BoundingBox()
    print(f"wrote {os.path.relpath(OUT, B.REPO)}/: mono_clip.stl, mono_clip.png, mono_clip_back.png; "
          f"{bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm as it prints")
    print(f"  pins on {', '.join(PADS)}: x {', '.join(f'{x:g}' for x in xs)} mm from the left edge, {yp:g} mm up from the bottom")
    print(f"  pocket {2 * half:.2f} x {HEADER['body'] + 2 * FIT:.2f} mm; the pins' tips {ZB - Z_IN:.1f} mm proud of the jaw, the bumps {PRESS} mm into a {T} mm board")
    print(f"  under the arm, {Z_ARM:.1f} mm over the front: " + (", ".join(f"{r} {h}" for r, h, _ in near) or "nothing"))


if __name__ == "__main__":
    main()
