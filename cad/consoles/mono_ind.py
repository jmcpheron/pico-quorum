"""Mono's case, industrial: mono.py's case with harder edges. Everything inside is mono.py's: the same board, posts,
screws, caps, window, badge, back panel and dock. What changes is the outside of the front shell:
- the corners cut off at 45 degrees, not rounded: 3 mm along each edge at the bottom, where the board's corner is
  near the wall, and 8 mm at the top, across the lanyard's lug, which tapers the top end
- the face's edge chamfered 1.6 mm, and the back's 0.8, in place of mono.py's rounds
- the screws' counterbores chamfered 0.4 mm
- nine V-grooves, 0.5 mm deep, across each long side, where the thumb and fingers hold it

And two things to try:
- the caps as one print, a cap tree: a bar under the buttons, a long thin link to each cap's flange, all 0.4 mm thick,
  held by two pins under the face (shell.Case.cap_tree). The caps one by one are written too
- the board's top end held: pads under the face press on its front round the glass, and ribs on the back panel come
  up under it, so the end away from the screws can't rock

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
    P, W, H = b["parts"], b["W"], b["H"]
    gx0, gy0, gx1, gy1 = b["glass"]
    fx0, fx1, fy0, fy1 = b["fold"]
    g = 0.3                                     # off the glass and the fold
    by = P["SW1"]["y"] - 13.5                   # the bar's foot: 13.5 under the buttons, so each link is 7.8 mm long
    y, pitch, n, depth = GROOVES
    b.update(name="mono_ind", title="Mono's case, industrial",
             corner_cut=CORNER_CUT, face_edge=("chamfer", 1.6), back_edge=("chamfer", 0.8), cb_chamfer=0.4,
             grooves=([y + pitch * k for k in range(n)], depth),
             # the bar from D0's link to D2's, 2 mm wide; the pins between the caps. Nothing on the board under it
             # stands higher than 0.4 mm, and the bar is 1.5 mm up
             cap_tree=dict(bar=(P["SW1"]["x"] - 0.5, P["SW3"]["x"] + 0.5, by, by + 2.0),
                           pins=[((P["SW1"]["x"] + P["SW2"]["x"]) / 2, by + 1.0), ((P["SW2"]["x"] + P["SW3"]["x"]) / 2, by + 1.0)]),
             # the top end, 24 mm past the screws: pads on its front beside the glass, past the ribbon's fold, and along
             # the top edge over the glass, into the walls; nothing is fitted there
             press=[(-S.CLEAR, gx0 - g, gy0, H + S.CLEAR), (gx1 + g, W + S.CLEAR, fy1 + g, H + S.CLEAR),
                    (gx0 - g, gx1 + g, gy1 + g, H + S.CLEAR)],
             # and ribs on the back panel under it: along the top edge and down both sides, to the glass's foot
             support=b["support"] + [(1.0, W - 1.0, H - 2.5, H - 1.0), (1.0, 2.5, gy0, H - 1.0), (W - 2.5, W - 1.0, gy0, H - 1.0)])
    b["views"] = dict(b["views"], front=b["views"]["front"] + [("the left side: the grooves, the cut corners", 15, 180)])
    return b


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else M.SCREEN)
    print("mono_ind: the wall at the cut corners %.2f mm at the least" % c.corner_wall)
    return bad


if __name__ == "__main__":
    sys.exit(main())
