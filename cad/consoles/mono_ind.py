"""Mono's case, industrial: mono.py's case with harder edges. Everything inside is mono.py's: the same board, posts,
screws, caps, window, badge, back panel and dock. What changes is the outside of the front shell:
- the corners cut off at 45 degrees, not rounded: 3 mm along each edge at the bottom, where the board's corner is
  near the wall, and 8 mm at the top, across the lanyard's lug, which tapers the top end
- the face's edge chamfered 1.6 mm, and the back's 0.8, in place of mono.py's rounds
- the screws' counterbores chamfered 0.4 mm
- nine V-grooves, 0.5 mm deep, across each long side, where the thumb and fingers hold it

(cad/consoles/README.md, "Mono, industrial")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/mono_ind.py [screen.png]
(or tools/case build mono-industrial)

Writes out/mono_ind/, the same files as mono.py with mono_ind_ in place of mono_. Not printed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import mono as M        # noqa: E402

OUT = os.path.join(HERE, "out", "mono_ind")
CORNER_CUT = (3.0, 8.0)     # along each edge: the bottom corners, the top's (shell.Case.outline checks the wall)
GROOVES = (14.0, 2.5, 9, 0.5)   # the lowest groove's y up from the board's bottom edge, the pitch, how many, depth


def board():
    b = M.board()
    y, pitch, n, depth = GROOVES
    b.update(name="mono_ind", title="Mono's case, industrial",
             corner_cut=CORNER_CUT, face_edge=("chamfer", 1.6), back_edge=("chamfer", 0.8), cb_chamfer=0.4,
             grooves=([y + pitch * k for k in range(n)], depth))
    b["views"] = dict(b["views"], front=b["views"]["front"] + [("the left side: the grooves, the cut corners", 15, 180)])
    return b


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else M.SCREEN)
    print("mono_ind: the wall at the cut corners %.2f mm at the least" % c.corner_wall)
    return bad


if __name__ == "__main__":
    sys.exit(main())
