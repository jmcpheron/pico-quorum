"""The slate, industrial: rp.py's case made thicker, with cut corners. Everything inside is rp.py's: the same board,
posts, screws, caps, window and back panel. What changes is the front shell, and the dock that follows it:
- the walls 3.5 mm, not 2.0, and the lanyard's lug 7.5 mm, not 6: 87.1 x 43.6 mm closed (rp.py's: 82.6 x 40.6), the
  same 10.9 thick. The bar outside the lanyard's slot is 2.45 mm, not 1.7
- the corners cut off at 45 degrees, not rounded: 4.5 mm along each edge at the USB end, 8 mm at the other, across
  the lug, which tapers that end
- a notch either side of every corner, eight in all: 2.5 mm wide, 1.2 deep, 1.5 mm from the cut's end, from the back
  to the face. The face's rounded edge is 1.5 mm, so each notch runs out in it and the face's outline stays whole
- nine V-grooves, 0.8 mm deep, across the top and bottom edges over D0-D2, where the hand holds it
- the mark and the name big, in the plain field right of the screen, their colours flush with the face, for a
  printer that changes filament itself (mono_ind.decor's inlay): nothing cut, nothing glued. Each colour is 0.6 mm
  deep from the face, three layers, the first on the bed. The mark is 9.5 mm in radius (rp.py's: 6.4), the name
  up to 33 x 5.5 mm (rp.py's: 24 x 3.6), in a line over it, their left edges level
- no holes for RESET and BOOTSEL: the face covers both switches, 2.2 mm over them. The mark is no longer drawn
  from them; it is placed to miss the LED's hole, which is right of the triangle

The colours, two ways: rp_ind_shell_colours.3mf, one object of three parts, black, green and orange; or
rp_ind_shell_black.stl, _green.stl and _orange.stl, the same three, each in the shell's own place.
rp_ind_shell.stl is the three as one body: its face is plain.

(cad/consoles/README.md, "The slate, industrial")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/rp_ind.py [screen.png]
(or tools/case build rp-industrial)

Writes out/rp_ind/, the same files as rp.py with rp_ind_ in place of rp_, but no badge; the shell's three bodies
and their 3MF; and rp_ind_mark.png: the mark and the name from the front, in the three colours. Not sliced, not
printed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import rp as RP         # noqa: E402
import mono_ind as MI   # noqa: E402  the mark printed in the face (decor), its picture, the shell's three bodies

OUT = os.path.join(HERE, "out", "rp_ind")
WALL = 3.5                  # rp.py's: shell.WALL, 2.0
LUG = 7.5                   # rp.py's: 6.0
CORNER_CUT = (4.5, 8.0)     # along each edge: the USB end's corners, the lug end's (shell.Case.outline checks the wall)
NOTCH = (1.5, 2.5, 1.2)     # either side of each corner: from the cut's end, wide, deep
GROOVES = (10.448, 2.5, 9, 0.8)     # the first groove's x, the pitch, how many, depth: centred on D1, 20 mm over D0-D2
# The mark, in the plain field right of the screen: its centre and radius on the board, x from its left edge and
# y up from its bottom. The LED (D1) is in the middle of that field, so the mark is left of the middle: the LED's
# hole is in the face right of the triangle, 1.2 mm from its edge and 2.0 mm from the lower right dot
MARK = (47.5, 13.0, 9.5)
# The colours come to the face (mono_ind.decor's inlay): three 0.2 mm layers deep, the first on the bed. The lines
# across the triangle are black through that depth, 1.55 mm apart at this size (mono_ind.HATCH: 6 pitches, 0.4 deep)
HATCH = dict(pitches=7, depth=RP.ENGRAVE_DEEP)
# The name: the room for its line, its middle's x, and its bottom edge's y. Its left end is level with the mark's left
# waiting dot. The top-right screw is under its right end: 30.0 is 0.9 mm over that counterbore
NAME = ((33.0, 5.5), 53.4, 30.0)
WHOLE = 1.0                 # the face black this close to the LED's hole, at the least


def board():
    b = RP.board()
    x, pitch, n, depth = GROOVES
    cx, cy, r = MARK
    fit, nx, ny = NAME
    b.update(name="rp_ind", title="The slate, industrial", wall=WALL, lug=("left", LUG), decor=MI.decor,
             corner_cut=CORNER_CUT, corner_notch=NOTCH, grooves_x=([x + pitch * k for k in range(n)], depth),
             mark=MARK, hatch=HATCH, inlay=True, name_x=nx, name_fit=(fit, ny - (cy + r + r / 4)))
    b["views"] = dict(b["views"], front=b["views"]["front"] + [("the USB end: the cut corners, a notch either side", 22, -28)])
    return b


def whole(c):
    """Checks no colour comes within WHOLE of the LED's hole."""
    led = c.b["parts"][c.b["led"]]
    r = S.LED_HOLE / 2
    ring = S.cyl(led["x"], led["y"], r + WHOLE, c.zt - 0.3, c.zt - 0.1).cut(S.cyl(led["x"], led["y"], r + 0.05, c.zt - 1, c.zt))
    gone = ring.val().Volume() - ring.intersect(dict(c.bodies)["black"]).val().Volume()
    assert gone < 1e-3, "the mark or the name comes within %.1f mm of the LED's hole" % WHOLE


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else RP.SCREEN)
    whole(c)
    MI.mark_picture(c, OUT)
    print("rp_ind: the wall at the cut corners %.2f mm at the least, behind a notch %.2f" % (c.corner_wall, WALL - NOTCH[2]))
    print("rp_ind: the mark's lines: %d across the triangle, %.2f mm apart, %.2f mm between them" % c.hatch)
    print("rp_ind: the shell's bodies: " + ", ".join("%s %.1f mm3" % b for b in MI.bodies(c, OUT)))
    S.threemf([(n, os.path.join(OUT, "rp_ind_shell_%s.stl" % n), col)
               for n, col in (("black", MI.BLACK), ("green", MI.GREEN), ("orange", MI.ORANGE))],
              os.path.join(OUT, "rp_ind_shell_colours.3mf"), "rp_ind_shell")
    print("wrote", os.path.relpath(os.path.join(OUT, "rp_ind_shell_colours.3mf"), S.REPO))
    return bad


if __name__ == "__main__":
    sys.exit(main())
