"""The slate, industrial: rp.py's case made thicker, with cut corners. Everything inside is rp.py's: the same board,
posts, screws, caps, window and back panel. What changes is the front shell, and the dock that follows it:
- the walls 3.5 mm, not 2.0, and the lanyard's lug 7.5 mm, not 6: 87.1 x 43.6 mm closed (rp.py's: 82.6 x 40.6), the
  same 10.9 thick. The bar outside the lanyard's slot is 2.45 mm, not 1.7
- the corners cut off at 45 degrees, not rounded: 4.5 mm along each edge at the USB end, 8 mm at the other, across
  the lug, which tapers that end
- a notch either side of every corner, eight in all: 2.5 mm wide, 1.2 deep, 1.5 mm from the cut's end, from the back
  to the face. The face's rounded edge is 1.5 mm, so each notch runs out in it and the face's outline stays whole
- nine V-grooves, 0.8 mm deep, across the top and bottom edges over D0-D2, where the hand holds it
- the mark printed with the shell, not a badge glued in, as Mono's industrial case has it (mono_ind.decor): a pocket
  0.4 mm deep, the five dots open, thin lines of the face's plastic across the triangle, the colour behind. Its two
  lower dots are still over RESET and BOOTSEL: each has a 1.4 mm pinhole through its floor, stepped for two layers
  so the colour bridges it
- the name over it, cut to show the same colour (rp.name), at rp.py's size

Two ways to print the colours, as Mono's: rp_ind_shell.stl, one body, the first two layers black and then green;
or rp_ind_shell_black.stl, _green.stl and _orange.stl, the same shell as three bodies in the same place.

(cad/consoles/README.md, "The slate, industrial")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/rp_ind.py [screen.png]
(or tools/case build rp-industrial)

Writes out/rp_ind/, the same files as rp.py with rp_ind_ in place of rp_, but no badge; the shell's three bodies; and
rp_ind_mark.png: the mark and the name from the front, in the three colours. Not sliced, not printed.
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
HATCH = dict(pitches=5)     # the lines across the triangle: 1.48 mm apart at this mark's size (mono_ind.HATCH: 6)
NAME_FIT = RP.NAME[1:]      # the name at rp.py's size: the top-right screw's counterbore is 0.8 mm over it


def board():
    b = RP.board()
    x, pitch, n, depth = GROOVES
    b.update(name="rp_ind", title="The slate, industrial", wall=WALL, lug=("left", LUG), decor=MI.decor,
             corner_cut=CORNER_CUT, corner_notch=NOTCH, grooves_x=([x + pitch * k for k in range(n)], depth),
             hatch=HATCH, name_fit=NAME_FIT)
    b["views"] = dict(b["views"], front=b["views"]["front"] + [("the USB end: the cut corners, a notch either side", 22, -28)])
    return b


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else RP.SCREEN)
    MI.mark_picture(c, OUT)
    print("rp_ind: the wall at the cut corners %.2f mm at the least, behind a notch %.2f" % (c.corner_wall, WALL - NOTCH[2]))
    print("rp_ind: the mark's lines: %d across the triangle, %.2f mm apart, %.2f mm between them" % c.hatch)
    print("rp_ind: the shell's bodies: " + ", ".join("%s %.1f mm3" % b for b in MI.bodies(c, OUT)))
    return bad


if __name__ == "__main__":
    sys.exit(main())
