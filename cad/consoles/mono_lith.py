"""Mono's case, monolith: mono_ind.py's case with no lanyard slot, and a face made to print in two colours by one
filament change. Everything inside is mono.py's: the same board, posts, screws, caps, window, back panel and dock.
The outline is mono_ind.py's: the corners cut off at 45 degrees, 8 mm at the top, the grooves on the sides.
What changes in the front shell:
- no slot through the top end: it is solid, 8.3 mm of plastic past the board's top edge
- the face's edge is a chamfer, SKIN wide, not a 1.5 mm round. The shell prints face down, and a round starts
  nearly flat on the bed
- the face is a skin, SKIN thick: its first three 0.2 mm layers. Cut through it, to its back and no further:
  - the mark, 12 mm in radius, as mono_ind.py's: the triangle between lines of the skin, the three signed dots
    open. The two waiting dots are rings, each round a disc of the skin, so they stay unlike the signed ones in
    two colours (docs/BRAND.md: never five dots alike)
  - a line round the window, FRAME wide

Printed in one colour, those are cut in, 0.6 mm deep. Printed in two, the first three layers in one and the rest in
another, the second colour shows through them, and in the screws' and the caps' holes, and it is the walls. The back
is mono.py's, its words cut 0.6 mm in: the same change, at the same height, does the same there.

(cad/consoles/README.md, "Mono, monolith")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/mono_lith.py [screen.png]
(or tools/case build mono-monolith)

Writes out/mono_lith/, the same files as mono.py with mono_lith_ in place of mono_, but no badge;
mono_lith_shell_plain.stl, the same shell with nothing cut in its face; mono_lith_shell.3mf, the shell as two
bodies, the skin and the rest, for a printer that changes filament itself; and mono_lith_mark.png. Not printed.
"""
import functools
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import mono as M        # noqa: E402
import mono_ind as MI   # noqa: E402

OUT = os.path.join(HERE, "out", "mono_lith")
SKIN = 0.6                  # the face's first colour: three 0.2 mm layers, and the depth of the back's words
# The line round the window: this far outside the window's chamfer (the strip of skin between them, on the bed), and
# this wide. And what it keeps, at the least,
# from the face's chamfer and from the caps' holes
FRAME = dict(off=0.9, wide=0.8, miss=1.0)
RING = 0.8                  # a waiting dot's ring: its width. The disc inside is the skin
BEHIND = 0.8                # the face left whole behind every cut, at the least: four layers
ISLAND = 1.5                # a piece of the skin alone on the bed: across, at the least
FACE, BODY = S.BLACK, S.GREEN       # the pictures': the first three layers, and the rest


def decor(c, shell, back):
    """The cuts through the face's skin: the mark and the window's line. Leaves the shell with a plain face in
    c.plain, and the shell's two bodies in c.bodies."""
    b = c.b
    cx, cy, r = b["mark"]
    pts = [(cx + r * math.cos(math.radians(90 - 72 * k)), cy + r * math.sin(math.radians(90 - 72 * k))) for k in range(5)]
    signed, waiting = (0, 2, 3), (1, 4)
    rs, rw = r / 4, r / 6
    assert SKIN <= c.plate_t - 1.0, "the skin leaves %.2f mm of the face behind it" % (c.plate_t - SKIN)
    z0, z1 = c.zt - SKIN, c.zt + 1
    union = lambda shapes: functools.reduce(lambda a, s: a.union(s), shapes)
    tri = lambda a, e: cq.Workplane("XY").workplane(offset=a).polyline([pts[k] for k in signed]).close().extrude(e - a)
    dots = lambda ks, rad, a, e: union([S.cyl(*pts[k], rad, a, e) for k in ks])
    mark = tri(z0, z1).union(dots(signed, rs, z0, z1)).cut(MI.kept(c, pts, signed, rs, z0, z1, union, tri, dots))
    # a waiting dot: a ring as far out as the dot's own edge, the skin left inside it
    assert 2 * (rw - RING) >= ISLAND, "a waiting dot's disc is %.2f mm across" % (2 * (rw - RING))
    rings = dots(waiting, rw, z0, z1).cut(dots(waiting, rw - RING, z0 - 1, z1 + 1))
    # the window's line, round its chamfer
    wx0, wx1, wy0, wy1 = c.window
    a = S.WINDOW_C + FRAME["off"]
    e = a + FRAME["wide"]
    fx0, fx1, fy0, fy1 = wx0 - e, wx1 + e, wy0 - e, wy1 + e
    x0, x1, _, y1 = c.outer
    edge = b["face_edge"][1]
    grow = (S.CAP_HOLE - S.CAP_D) / 2
    caps = max(S.cap_shape(b["parts"][ref]["x"], b["parts"][ref]["y"], b["cap_shapes"][n], grow, z0, z1, b["cap_scale"])
               .val().BoundingBox().ymax for ref, n in b["buttons"])
    corner = (min(fx0 - x0, x1 - fx1) + y1 - fy1 - b["corner_cut"][1]) / math.sqrt(2)     # from a top corner's cut
    c.frame = (min(fx0 - x0, x1 - fx1, y1 - fy1, corner) - edge, fy0 - caps)
    assert min(c.frame) >= FRAME["miss"], "the window's line is %.2f mm from the face's edge, %.2f from the caps' holes" % c.frame
    frame = S.box(fx0, fx1, fy0, fy1, z0, z1).cut(S.box(wx0 - a, wx1 + a, wy0 - a, wy1 + a, z0 - 1, z1 + 1))
    cuts = mark.union(rings).union(frame)
    # behind every cut the face is whole, BEHIND thick at the least: no pocket or hole comes up under one
    floor = cuts.intersect(S.box(x0, x1, c.outer[2], y1, z0, z0 + 0.1)).translate((0, 0, -0.1))
    floor = union([floor.translate((0, 0, -0.1 * k)) for k in range(round(BEHIND / 0.1))])
    assert abs(floor.intersect(shell).val().Volume() - floor.val().Volume()) < 0.01, "the face is open behind a cut"
    c.plain = shell
    shell = shell.cut(cuts)
    # the two bodies: the skin, and the rest behind it
    x0, x1, y0, y1 = c.outer
    slab = S.box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, z0, z1)
    c.bodies = [("face", shell.intersect(slab)), ("body", shell.cut(slab))]
    # for the pictures: the skin in its colour, a hair over the shell, which is the rest's colour
    return shell, back, [("shell face", c.bodies[0][1].translate((0, 0, 0.02)), FACE, None)]


def board():
    b = MI.board()
    W, hb = b["W"], b["H"]
    b.update(name="mono_lith", title="Mono's case, monolith", decor=decor, lug_hole=False,
             face_edge=("chamfer", SKIN), shell_colour=BODY, back_colour=FACE,
             # the back's words in one piece: one colour behind the skin
             back_text=[("picoquorum.app", (W / 2, hb / 2), M.BACK_WORDS[0], "bold",
                         dict(along=M.BACK_WORDS[1], parts=[("picoquorum.app", "green", BODY)]))])
    b["views"] = dict(b["views"], front=[("in the hand: the face in one colour, the rest in another", 58, -78),
                                         ("the back: picoquorum.app", -55, 110),
                                         ("the left side: the grooves, the cut corners", 15, 180)])
    return b


def mark_picture(c):
    """The face from the front, as the two colours print: the skin, and the rest 0.7 mm behind the face."""
    x0, x1, y0, y1 = c.outer
    behind = S.box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, c.zt - SKIN - 0.1, c.zt - SKIN)
    S.render(dict(title="Mono's case, monolith: the face, as its two colours print", corners=[], views=[("", 89.9, -90)],
                  parts=[(c.bodies[1][1].intersect(behind), BODY, "body"), (c.bodies[0][1], FACE, "face")]),
             os.path.join(OUT, "mono_lith_mark.png"))


def bodies(c):
    """The shell with a plain face, one STL; and the shell's two bodies in one 3MF, face down in the shell's own
    place. Checks that the two add up to the shell, that the cuts go no deeper than the skin, and that no piece of
    the skin is too small to hold on the bed."""
    S.stl(S.flip(c.plain), os.path.join(OUT, "mono_lith_shell_plain.stl"))
    whole = sum(s.val().Volume() for _, s in c.bodies)
    assert abs(whole - c.shell.val().Volume()) < 0.01, "the shell's bodies add up to %.2f mm3" % whole
    x0, x1, y0, y1 = c.outer
    under = S.box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, c.z0 - 1, c.zt - SKIN)
    assert abs(c.plain.intersect(under).val().Volume() - c.shell.intersect(under).val().Volume()) < 0.01, "a cut goes behind the skin"
    pieces = c.bodies[0][1].solids().vals()
    for s in pieces:
        bb = s.BoundingBox()
        assert min(bb.xlen, bb.ylen) >= ISLAND, "a piece of the skin is %.2f mm across" % min(bb.xlen, bb.ylen)
    S.threemf(os.path.join(OUT, "mono_lith_shell.3mf"), "Mono's case, monolith: the shell",
              [(n, col, S.flip(s)) for (n, s), col in zip(c.bodies, (FACE, BODY))])
    return len(pieces), [(n, s.val().Volume()) for n, s in c.bodies]


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else M.SCREEN)
    c.shell = c.bodies[0][1].union(c.bodies[1][1])
    mark_picture(c)
    n, vols = bodies(c)
    print("mono_lith: the wall at the cut corners %.2f mm at the least" % c.corner_wall)
    print("mono_lith: the mark's lines: %d across the triangle, %.2f mm apart, %.2f mm between them" % c.hatch)
    print("mono_lith: the window's line: %.2f mm from the face's chamfer, %.2f mm from the caps' holes" % c.frame)
    print("mono_lith: the shell's bodies: " + ", ".join("%s %.1f mm3" % v for v in vols) + "; the skin in %d pieces" % n)
    return bad


if __name__ == "__main__":
    sys.exit(main())
