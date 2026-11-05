"""console-rp's case: the slate. A flat bar round the 72 x 36 mm board, 79 x 41 x 11 mm, in the stick's "shell"
layout: the face and the walls are one front shell, and a flat panel closes the back. Four M2 screws go in from
the front, through the shell's posts and the board's four M2.5 holes, into bosses on the back panel. The board
has no radio, so no end is kept free of metal, and no tab.

The face has the window, caps on D0, D1 and D2 in a row under it, a hole over the LED, and the mark, at the
right: its two lower dots are the holes for RESET and BOOTSEL, 7.5 mm apart on the board, so the mark is drawn
from them. The USB-C is open at the right end; a lanyard lug at the left. The back has the name and the Source
Location, since the case covers the board's own. A dock holds it leaning back, its cable out of the right side.
(cad/consoles/README.md)

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/rp.py [screen.png]
(or tools/case build rp)

Writes out/rp/: rp_shell.stl (face down, as it prints), rp_back.stl (outside down), rp_cap_D0/D1/D2.stl (flange
down), rp_dock.stl, rp_assembly.step, rp_front.png, rp_face.png, rp_apart.png, rp_dock.png.

The board's numbers are its generator's (hardware/console-rp/gen_console_rp.py) and the placement file JLCPCB
built it from (console-rp/fab/cpl.csv), checked against each other. The glass is the panel's datasheet's,
31.0 x 17.6 mm (the README's "The panel"); the generator still has 17.0. Not measured: the foam, the
switches' height, how far the USB-C's legs stand out of the back. A first draft to print and try.
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402

RP = os.path.join(S.REPO, "hardware", "console-rp")
_spec = importlib.util.spec_from_file_location("rp", os.path.join(RP, "gen_console_rp.py"))
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)        # the board's generator; it writes nothing on import
FAB = os.path.join(RP, "console-rp", "fab")
OUT = os.path.join(HERE, "out", "rp")
SCREEN = os.path.join(S.REPO, "docs", "quorum-ui", "feather", "06-review-head.png")
GLASS_H = 17.6              # the datasheet's glass, 0.3 mm more each side than the generator's 17.0
OFF = 1.4                   # the active area's centre from the glass's, away from the ribbon (the datasheet's)
BACK_ROOM = 1.6             # under the board: the USB-C's shell legs, and the bosses' height for the M2 x 8's thread


def board():
    P = S.parts(os.path.join(FAB, "cpl.csv"), os.path.join(FAB, "bom.csv"))
    W, H = G.W, G.H
    up = lambda xy: (xy[0], H - xy[1])     # the generator's y runs down from the top edge; the fab files' up
    for ref in ("SW1", "SW2", "SW3", "SW4", "SW5", "J1", "J2", "D1", "U1"):     # the fab file and the generator agree
        gx, gy = up(G.AT[ref][:2])
        assert abs(P[ref]["x"] - gx) < 0.01 and abs(P[ref]["y"] - gy) < 0.01, ref
    xc, yc = G.XC, H - G.YC
    gw = G.PANEL["glass"][0]
    glass = (xc - gw / 2, yc - GLASS_H / 2, xc + gw / 2, yc + GLASS_H / 2)
    aw, ah = G.PANEL["active"]
    # the active area: off-centre away from the ribbon (it leaves the glass's right end), as the datasheet has
    # it; the window shows it there or centred, until a panel is measured
    active = (xc - OFF - aw / 2, yc - ah / 2, xc - OFF + aw / 2, yc + ah / 2)
    over = (active[0], active[1], xc + aw / 2, active[3])
    rw = G.PANEL["ribbon"]
    # the mark: its lower dots over RESET (SW4) and BOOTSEL (SW5), 2 r sin 36 apart
    rs, bs = P["SW4"], P["SW5"]
    assert abs(rs["y"] - bs["y"]) < 0.01
    r = (bs["x"] - rs["x"]) / (2 * math.cos(math.radians(54)))
    return dict(
        name="rp", title="The slate (console-rp)", layout="shell",
        W=W, H=H, R=G.CORNER, T=1.6, holes=[up(G.AT[h][:2]) for h in ("H1", "H2", "H3", "H4")], hole_d=2.7, parts=P,
        glass=glass, glass_z=(G.PANEL["foam"], G.PANEL["foam"] + G.PANEL["thick"]), active=active, window_over=over,
        # the ribbon's loop past the glass's right end, about 1.5 to 2 mm by the datasheet's drawing (not measured)
        fold=(glass[2], glass[2] + 2.0, yc - rw / 2, yc + rw / 2),
        module=None, module_h=BACK_ROOM,
        buttons=[("SW1", "D0"), ("SW2", "D1"), ("SW3", "D2")], pins=[],
        led="D1", usb="J1", usb_edge="right", dock_depth=40.0, dock_plug=0.0,
        lug=("left", 6.0), tab=False,
        post_r=2.6,                 # the board's own keep-out round each hole (HOLE_RING in the generator)
        rest=[],
        # ribs under the back where it's pressed: the three buttons, and RESET and BOOTSEL
        support=[(P["SW1"]["x"] - 3.0, P["SW3"]["x"] + 3.0, P["SW1"]["y"] - S.REST_W / 2, P["SW1"]["y"] + S.REST_W / 2),
                 (rs["x"] - 3.0, bs["x"] + 3.0, rs["y"] - S.REST_W / 2, rs["y"] + S.REST_W / 2)],
        press=[],
        face=[("mark", (rs["x"] + r * math.cos(math.radians(54)), rs["y"] + r * math.sin(math.radians(54)), r, "SW4", "SW5"))],
        flip="x",
        # turned over about x, the back's lower y is its top: the name, and the Source Location under it
        back_text=[("PicoQuorum", (W / 2, H / 2 - 3.0), (44.0, 8.0), "bold"),
                   ("PicoQuorum.app", (W / 2, H / 2 + 7.0), (30.0, 3.2), "regular")],
        seen=("D1",),
        views=dict(front=[("in the hand: four screws in the face", 55, -72), ("the back panel: the name, the Source Location", -50, -120)],
                   apart=[("apart: screws, front shell, caps, board, back panel", 28, -62)],
                   dock=[("on its dock, the cable out of the right", 18, -62)]),
    )


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else SCREEN)
    return bad


if __name__ == "__main__":
    sys.exit(main())
