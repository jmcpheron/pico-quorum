"""console-rp rev B as one printable solid: the board (48 x 64.5 x 1.6 mm, its four holes), every part on its front as
a box, the glass on its foam, and the ribbon's loop. For a test fit in the case (rp.py) and to hold in the hand.

The numbers are rp.py's board(): the generator's outline and holes, the parts from the fab files JLCPCB built from,
each a box at its package's usual size and height (shell.py's PACKAGES), not measured. The foam under the glass is
printed solid. The switches' plungers are their boxes' tops, so the caps sit where the case expects them.

Run: uv run --python 3.11 --with cadquery python cad/consoles/rp_mockup.py
Writes out/rp/rp_board_mockup.stl: board side down, prints without supports.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import rp               # noqa: E402


def main():
    b = rp.board()
    c = S.Case(b)
    solid = None
    for shape, _, name in c.standins():
        if name == "glass":         # the glass stands on 2 mm of foam: print the foam with it
            gx0, gy0, gx1, gy1 = b["glass"]
            shape = S.box(gx0, gx1, gy0, gy1, 0.0, b["glass_z"][1])
        solid = shape if solid is None else solid.union(shape)
    solid = solid.translate((0, 0, b["T"]))     # the board's back on the bed
    bb = solid.val().BoundingBox()
    out = os.path.join(rp.OUT, "rp_board_mockup.stl")
    S.stl(solid, out)
    print("%s: %.1f x %.1f x %.1f mm" % (os.path.relpath(out, S.REPO), bb.xlen, bb.ylen, bb.zlen))


if __name__ == "__main__":
    main()
