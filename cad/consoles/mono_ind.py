"""Mono's case, industrial: mono.py's case with harder edges, and the mark printed in the face. Everything inside is
mono.py's: the same board, posts, screws, caps, window, back panel and dock. What changes is the front shell:
- the corners cut off at 45 degrees, not rounded: 3 mm along each edge at the bottom, where the board's corner is
  near the wall, and 8 mm at the top, across the lanyard's lug, which tapers the top end
- the face's edge chamfered 1.6 mm, and the back's 0.8, in place of mono.py's rounds
- the screws' counterbores chamfered 0.4 mm
- nine V-grooves, 0.5 mm deep, across each long side, where the thumb and fingers hold it
- the mark, 8 mm in radius (mono.py's: 6), printed with the shell, not a badge glued in. Its pocket is 0.4 mm deep:
  the shell's first two layers. The three signed dots are open. Thin lines of the face's plastic cross the
  triangle, a ring of it goes round each signed dot inside the triangle, and one line crosses each waiting dot.
  Print the first two layers black and the third in green: the green lies on the lines, so it bridges 1 mm at
  a time, and 4 mm across each dot. From the front the signed dots are green, and the triangle and the waiting
  dots green behind black lines. The name over it shows the same green (rp.name)

(cad/consoles/README.md, "Mono, industrial")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/mono_ind.py [screen.png]
(or tools/case build mono-industrial)

Writes out/mono_ind/, the same files as mono.py with mono_ind_ in place of mono_, but no badge, and mono_ind_mark.png:
the mark and the name from the front, in the two colours. Not printed.
"""
import functools
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import rp as RP         # noqa: E402  the name over the mark
import mono as M        # noqa: E402

OUT = os.path.join(HERE, "out", "mono_ind")
CORNER_CUT = (3.0, 8.0)     # along each edge: the bottom corners, the top's (shell.Case.outline checks the wall)
GROOVES = (14.0, 2.5, 9, 0.5)   # the lowest groove's y up from the board's bottom edge, the pitch, how many, depth
MARK_R = 8.0                # the mark's radius, at mono.py's centre
# The mark's pocket: its depth, two 0.2 mm layers; the lines' width, one pass of a 0.4 mm nozzle; and how many
# pitches of them from the waiting dots' centres down to the triangle's base. That sets the pitch (1.53 mm here), so
# a line crosses each waiting dot through its centre and the last gap, at the base, is as wide as the others
HATCH = dict(depth=0.4, line=0.5, pitches=6)
HATCH_GAP = 0.8             # between two lines at the least: narrower, and the first layer closes it
BLACK, GREEN = (0.10, 0.10, 0.11), (0.20, 0.78, 0.35)     # the pictures': the first two layers, the third (Sign green)


def decor(c, shell, back):
    """The mark printed in the face: a pocket HATCH's depth deep, the signed dots open, lines left across the
    triangle and the waiting dots. And the name over it (rp.name). No badge: nothing more to print or glue."""
    b = c.b
    cx, cy, r = b["mark"]
    pts = [(cx + r * math.cos(math.radians(90 - 72 * k)), cy + r * math.sin(math.radians(90 - 72 * k))) for k in range(5)]
    signed, waiting = (0, 2, 3), (1, 4)
    rs, rw = r / 4, r / 6
    d, w, n = HATCH["depth"], HATCH["line"], HATCH["pitches"]
    z0, z1 = c.zt - d, c.zt + 1
    union = lambda shapes: functools.reduce(lambda a, s: a.union(s), shapes)
    tri = lambda a, e: cq.Workplane("XY").workplane(offset=a).polyline([pts[k] for k in signed]).close().extrude(e - a)
    dots = lambda ks, rad, a, e: union([S.cyl(*pts[k], rad, a, e) for k in ks])
    pocket = tri(z0, z1).union(dots(signed, rs, z0, z1)).union(dots(waiting, rw, z0, z1))
    # the lines: one through the waiting dots' centres, the rest a pitch apart, down to a gap over the base and up
    # to the top dot
    base, yw, top = pts[2][1], pts[1][1], pts[0][1] - rs
    pitch = (yw - base + w / 2) / n
    assert pitch - w >= HATCH_GAP, "the lines are %.2f mm apart" % (pitch - w)
    ys = [yw + pitch * k for k in range(1 - n, n) if yw + pitch * k - w / 2 < top]
    strip = lambda y: S.box(cx - 2 * r, cx + 2 * r, y - w / 2, y + w / 2, z0 - 1, z1 + 1)
    inside = tri(z0 - 1, z1 + 1)
    left = union([strip(y) for y in ys]).intersect(inside).cut(dots(signed, rs, z0 - 2, z1 + 2))
    left = left.union(dots(signed, rs + w, z0 - 1, z1 + 1).cut(dots(signed, rs, z0 - 2, z1 + 2)).intersect(inside))
    left = left.union(strip(yw).intersect(dots(waiting, rw, z0 - 1, z1 + 1)))
    open_ = pocket.cut(left)
    cut = RP.name(c, cx, pts[0][1] + rs)
    shell = shell.cut(open_).cut(cut)
    c.hatch = (len(ys), pitch, pitch - w)
    # for the pictures: the third layer where it shows, on the pocket's floor and the letters'
    skin = lambda shape, z: shape.intersect(S.box(cx - 30, cx + 30, cy - 30, cy + 30, z, z + 0.05)).solids().vals()
    spots = skin(open_, z0) + skin(cut, c.zt - RP.ENGRAVE_DEEP)
    # in a set order, so the pictures come out the same each run
    c.shell, c.green = shell, cq.Workplane("XY").newObject(sorted(spots, key=lambda s: [round(v, 3) for v in s.Center().toTuple()]))
    return shell, back, [("shell green", c.green, GREEN, None)]


def board():
    b = M.board()
    y, pitch, n, depth = GROOVES
    cx, cy, _ = b["mark"]
    led = b["parts"][b["led"]]
    assert math.hypot(led["x"] - cx, led["y"] - cy) > MARK_R + MARK_R / 4 + S.LED_HOLE, "the mark runs into the LED's hole"
    b.update(name="mono_ind", title="Mono's case, industrial", mark=(cx, cy, MARK_R), decor=decor,
             corner_cut=CORNER_CUT, face_edge=("chamfer", 1.6), back_edge=("chamfer", 0.8), cb_chamfer=0.4,
             grooves=([y + pitch * k for k in range(n)], depth))
    b["views"] = dict(b["views"], front=b["views"]["front"] + [("the left side: the grooves, the cut corners", 15, 180)])
    return b


def mark_picture(c, shell):
    """The mark and the name from the front, as the two colours print: the face's top 0.7 mm round them."""
    cx, cy, r = c.b["mark"]
    near = S.box(cx - 2 * r, cx + 2 * r, cy - 1.6 * r, cy + 2.4 * r, c.zt - 0.7, c.zt)
    S.K.render(dict(title="Mono's case, industrial: the mark, black with the third layer green", corners=[], views=[("", 89.9, -90)],
                    parts=[(shell.intersect(near), BLACK, "face"), (c.green, GREEN, "green")]),
               os.path.join(OUT, "mono_ind_mark.png"))


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else M.SCREEN)
    mark_picture(c, c.shell)
    print("mono_ind: the wall at the cut corners %.2f mm at the least" % c.corner_wall)
    print("mono_ind: the mark's lines: %d across the triangle, %.2f mm apart, %.2f mm between them" % c.hatch)
    return bad


if __name__ == "__main__":
    sys.exit(main())
