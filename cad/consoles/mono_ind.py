"""Mono's case, industrial: mono.py's case with cut corners, and the mark printed in the face. Everything inside is
mono.py's: the same board, posts, screws, caps, window, back panel and dock. What changes is the front shell:
- the corners cut off at 45 degrees, not rounded: 3 mm along each edge at the bottom, where the board's corner is
  near the wall, and 8 mm at the top, across the lanyard's lug, which tapers the top end
- the face's and the back's edges rounded as mono.py's (1.5 mm, 0.8), and the counterbores plain. An earlier draft
  chamfered them, the face's edge 1.6 mm and the counterbores 0.4: that left 1.2 mm of plastic between a
  counterbore and the edge's slope. Now 2.2 mm of flat face
- nine V-grooves, 0.5 mm deep, across each long side, where the thumb and fingers hold it
- the mark, 8 mm in radius (mono.py's: 6), printed with the shell, not a badge glued in. Its pocket is 0.4 mm deep:
  the shell's first two layers. All five dots are open. Thin lines of the face's plastic cross the triangle, and
  a ring of it goes round each signed dot inside the triangle. The colour lies behind, on the lines, so it bridges
  1 mm at a time, 4 mm across a signed dot and 2.7 across a waiting one. From the front the dots are the colour,
  and the triangle the colour behind black lines
- the name over it, 36 mm wide (mono.py's: 22.5), cut to show the same colour (rp.name)

Two ways to print the colours:
- from mono_ind_shell.stl, one body: the first two layers black, then green. All five dots come out green, which
  docs/BRAND.md says not to do
- from mono_ind_shell_black.stl, _green.stl and _orange.stl, the same shell as three bodies, in the same place:
  load them as one object, a filament each. Green behind the triangle, the signed dots and the name, orange behind
  the waiting dots, each COLOUR's thickness and no wider than it shows, but for a rim

(cad/consoles/README.md, "Mono, industrial")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/mono_ind.py [screen.png]
(or tools/case build mono-industrial)

Writes out/mono_ind/, the same files as mono.py with mono_ind_ in place of mono_, but no badge; the shell's three
bodies; and mono_ind_mark.png: the mark and the name from the front, in the three colours. Not printed.
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
# pitches of them from the waiting dots' height down to the triangle's base. That sets the pitch (1.53 mm here), so
# the last gap, at the base, is as wide as the others
HATCH = dict(depth=0.4, line=0.5, pitches=6)
HATCH_GAP = 0.8             # between two lines at the least: narrower, and the first layer closes it
# The name: the room for its line, and how far over the mark's top dot (rp.NAME's: 24 x 3.6, 1.4 over). 36 mm is
# the screws' counterbores, outside to outside, near enough (37.2); the face is flat for 2.8 mm past each end
NAME_FIT = ((36.0, 5.8), 2.2)
# The shell as three bodies: the colour behind each opening, three 0.2 mm layers thick, and its rim under the face
# round the opening, so its edge lies on the black
COLOUR = dict(thick=0.6, rim=0.6)
BLACK, GREEN, ORANGE = (0.10, 0.10, 0.11), S.GREEN, RP.ORANGE   # the pictures': the face, Sign green, the waiting dots


def decor(c, shell, back):
    """The mark printed in the face: a pocket HATCH's depth deep, the five dots open, lines left across the
    triangle. And the name over it (rp.name). No badge: nothing more to print or glue. Leaves the shell's three
    bodies in c.bodies (COLOUR)."""
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
    # the lines: one at the waiting dots' height, the rest a pitch apart, down to a gap over the base and up to the
    # top dot
    base, yw, top = pts[2][1], pts[1][1], pts[0][1] - rs
    pitch = (yw - base + w / 2) / n
    assert pitch - w >= HATCH_GAP, "the lines are %.2f mm apart" % (pitch - w)
    ys = [yw + pitch * k for k in range(1 - n, n) if yw + pitch * k - w / 2 < top]
    strip = lambda y: S.box(cx - 2 * r, cx + 2 * r, y - w / 2, y + w / 2, z0 - 1, z1 + 1)
    inside = tri(z0 - 1, z1 + 1)
    left = union([strip(y) for y in ys]).intersect(inside).cut(dots(signed, rs, z0 - 2, z1 + 2))
    left = left.union(dots(signed, rs + w, z0 - 1, z1 + 1).cut(dots(signed, rs, z0 - 2, z1 + 2)).intersect(inside))
    open_ = pocket.cut(left)
    cut = RP.name(c, cx, pts[0][1] + rs, NAME_FIT)
    shell = shell.cut(open_).cut(cut)
    c.hatch = (len(ys), pitch, pitch - w)
    # the three bodies: a slab of colour behind the pocket's floor and the letters', the rest black
    t, m = COLOUR["thick"], COLOUR["rim"]
    zn = c.zt - RP.ENGRAVE_DEEP
    assert zn - t - c.zu >= 0.4, "the colour behind the name leaves %.2f mm of the face" % (zn - t - c.zu)
    nb = cut.val().BoundingBox()
    green = (cq.Workplane("XY").workplane(offset=z0 - t).polyline([pts[k] for k in signed]).close().offset2D(m).extrude(t)
             .union(dots(signed, rs + m, z0 - t, z0))
             .union(S.box(nb.xmin - m, nb.xmax + m, nb.ymin - m, nb.ymax + m, zn - t, zn))).intersect(shell)
    orange = dots(waiting, rw + m, z0 - t, z0).intersect(shell)
    c.shell, c.bodies = shell, [("black", shell.cut(green).cut(orange)), ("green", green), ("orange", orange)]
    # for the pictures: each colour where it shows, on the pocket's floor and the letters'
    skin = lambda shape, z: shape.intersect(S.box(cx - 30, cx + 30, cy - 30, cy + 30, z, z + 0.05)).solids().vals()
    # in a set order, so the pictures come out the same each run
    seen = lambda spots: cq.Workplane("XY").newObject(sorted(spots, key=lambda s: [round(v, 3) for v in s.Center().toTuple()]))
    amber = dots(waiting, rw, z0 - 1, z1)
    c.shown = [("shell green", seen(skin(open_.cut(amber), z0) + skin(cut, zn)), GREEN),
               ("shell orange", seen(skin(open_.intersect(amber), z0)), ORANGE)]
    return shell, back, [(n, s, col, None) for n, s, col in c.shown]


def board():
    b = M.board()
    y, pitch, n, depth = GROOVES
    cx, cy, _ = b["mark"]
    led = b["parts"][b["led"]]
    assert math.hypot(led["x"] - cx, led["y"] - cy) > MARK_R + MARK_R / 4 + S.LED_HOLE, "the mark runs into the LED's hole"
    b.update(name="mono_ind", title="Mono's case, industrial", mark=(cx, cy, MARK_R), decor=decor,
             corner_cut=CORNER_CUT, grooves=([y + pitch * k for k in range(n)], depth))
    b["views"] = dict(b["views"], front=b["views"]["front"] + [("the left side: the grooves, the cut corners", 15, 180)])
    return b


def mark_picture(c, shell):
    """The mark and the name from the front, as the three bodies print: the face's top 0.7 mm round them."""
    cx, cy, r = c.b["mark"]
    near = S.box(cx - 2.6 * r, cx + 2.6 * r, cy - 1.6 * r, cy + 2.6 * r, c.zt - 0.7, c.zt)
    S.render(dict(title="Mono's case, industrial: the mark and the name, as its three bodies print", corners=[], views=[("", 89.9, -90)],
                    parts=[(shell.intersect(near), BLACK, "face")] + [(s, col, n) for n, s, col in c.shown]),
               os.path.join(OUT, "mono_ind_mark.png"))


def bodies(c):
    """The shell's three bodies, each face down in the shell's own place, so a slicer puts them together. Checks
    that they add up to the shell."""
    whole = c.shell.val().Volume()
    parts = sum(s.val().Volume() for _, s in c.bodies)
    assert abs(whole - parts) < 0.01, "the shell's bodies add up to %.2f mm3, the shell %.2f" % (parts, whole)
    for n, s in c.bodies:
        S.stl(S.flip(s), os.path.join(OUT, "mono_ind_shell_%s.stl" % n))
    return [(n, s.val().Volume()) for n, s in c.bodies]


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else M.SCREEN)
    mark_picture(c, c.shell)
    print("mono_ind: the wall at the cut corners %.2f mm at the least" % c.corner_wall)
    print("mono_ind: the mark's lines: %d across the triangle, %.2f mm apart, %.2f mm between them" % c.hatch)
    print("mono_ind: the shell's bodies: " + ", ".join("%s %.1f mm3" % b for b in bodies(c)))
    return bad


if __name__ == "__main__":
    sys.exit(main())
