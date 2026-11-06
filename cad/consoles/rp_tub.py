"""console-rp's second case, the tub: rev B's short bar (48 x 64.5 mm) in the badge's "plate" layout. A tub holds the board
face up, and a front plate sits in its opening, flush with the rim. Four M2 screws go in from the back, through bosses in the
tub and the board's four M2.5 holes, into posts on the plate's underside, so the front shows no screw. Beside the bar
(rp.py, screws from the front): same board, same caps, same window, same lug and dock.

The face is the plate alone: the window, caps on D0, D1 and D2 under it, two pinholes at the left for RESET and BOOTSEL with
their names engraved under them, a hole over the LED, and at the right the mark engraved 0.5 mm, its name under it. The
USB-C is open in the left wall, a lanyard lug along the top. The back has the name and the Source Location.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/rp_tub.py [screen.png]

Writes out/rp_tub/: rp_tub_tub.stl (on its back, as it prints), rp_tub_plate.stl (face down), rp_tub_cap_D0/D1/D2.stl,
rp_tub_dock.stl, rp_tub_assembly.step and the pictures. The board's numbers are rp.py's: its generator's and the placement
file JLCPCB built it from. Not measured, not printed: the foam, the switches' height, the USB-C's legs.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rp as R          # noqa: E402
import shell as S       # noqa: E402

OUT = os.path.join(HERE, "out", "rp_tub")


def board():
    b = R.board()
    P = b["parts"]
    rs, bs = P["SW4"], P["SW5"]
    cx, cy, r = R.MARK
    b.update(
        name="rp_tub", title="The tub (console-rp rev B)", layout="plate", decor=None,
        # the plate's face: the pinholes' names and the mark with its name, all engraved (the bar's mark is a glued badge)
        face=[("text", ("RESET", (rs["x"], rs["y"] - 3.6), (7.0, 2.0))), ("text", ("BOOTSEL", (bs["x"], bs["y"] - 3.6), (9.0, 2.0))),
              ("mark", (cx, cy, r)), ("text", ("PicoQuorum", (cx, cy - r - 4.0), (22.0, 4.0)))],
        engrave=S.ENGRAVE,
        plate=2.2,      # over the glass: 0.4 mm over the least, so the kit's M2 x 8 reaches the plate's posts from the back
        views=dict(front=[("in the hand: nothing on the front but the face", 58, -78), ("the tub's back: the name, the Source Location", -55, 110)],
                   apart=[("apart: tub, board, caps, plate, screws from the back", 30, -60)],
                   dock=[("on its dock, the cable out of the left", 20, -68)]),
    )
    return b


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else R.SCREEN)
    return bad


if __name__ == "__main__":
    sys.exit(main())
