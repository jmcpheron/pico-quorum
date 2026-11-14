"""console-rp's case: the slate. A flat bar round the 72 x 36 mm board, 79 x 41 x 11 mm, in the stick's "shell"
layout: the face and the walls are one front shell, and a flat panel closes the back. Four M2 screws go in from
the front, through the shell's posts and the board's four M2.5 holes, into bosses on the back panel. The board
has no radio, so no end is kept free of metal, and no tab.

The face has the window, caps on D0, D1 and D2 in a row under it, a hole over the LED, and the mark, at the
right: its two lower dots are the holes for RESET and BOOTSEL, 7.5 mm apart on the board, so the mark is drawn
from them. The mark is a badge, its pieces printed in colour and glued into a pocket 1.0 mm deep, standing
0.6 mm proud: the triangle green, the three signed dots blue, the two waiting dots orange. The lower two blue
dots are rings round 1.4 mm pinholes for RESET and BOOTSEL. Over it, the name on one line, cut 0.6 mm: print
the first two layers black and the rest in a colour, and the letters show the colour. The USB-C is open at the
right end; a lanyard lug at the left. The back has the name and the Source Location, since the case covers the
board's own. A dock holds it leaning back, its cable out of the right side. (cad/consoles/README.md)

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/rp.py [screen.png]
(or tools/case build rp)

Writes out/rp/: rp_shell.stl (face down, as it prints), rp_back.stl (outside down), rp_cap_D0/D1/D2.stl (flange
down), rp_badge_*.stl (the badge's six pieces, face down), rp_dock.stl, rp_assembly.step,
rp_front.png, rp_face.png, rp_apart.png, rp_dock.png.

The board's numbers are its generator's (hardware/console-rp/gen_console_rp.py) and the placement file JLCPCB
built it from (console-rp/fab/cpl.csv), checked against each other. The glass is the panel's datasheet's,
31.0 x 17.6 mm (the README's "The panel"); the generator still has 17.0. Not measured: the foam, the
switches' height, how far the USB-C's legs stand out of the back. A first draft to print and try.
"""
import importlib.util
import math
import os
import sys

import cadquery as cq

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
GREEN, BLUE, ORANGE = (0.18, 0.75, 0.33), (0.17, 0.42, 0.85), (1.0, 0.42, 0.07)     # PLA: the triangle, its dots, the others
BADGE = dict(depth=1.0, proud=0.6, gap=0.1, short=0.05, edge=0.2)
# the mark's pocket deep, the badge's pieces proud of the face; each piece 0.1 mm in from its neighbours and the
# pocket's walls, 0.05 mm off the pocket's floor for the glue; their top edges chamfered
# The name over the mark, on one line (docs/BRAND.md), centred on it: up to 24 x 3.6 mm, 1.4 mm over the mark's top
# dot, which keeps it under the top-right screw's counterbore. Cut 0.6 mm, three 0.2 mm layers: printed face down with its first two layers in black
# and the rest in a colour, the letters' floor shows that colour. The back's text is cut as deep.
NAME = ("Picoquorum", (24.0, 3.6), 1.4)
ENGRAVE_DEEP = 0.6
PIN = 0.7                   # RESET's and BOOTSEL's pinholes, inside the blue rings: a paperclip, not a thumb


def name(c, cx, top, fit=NAME[1:]):
    """The name's cut in the face, its line centred on cx, over top: the top edge of the mark's top dot. fit is
    NAME's: the room for the line, and how far over top."""
    word, ((w, h), over) = NAME[0], fit
    size = S.fit_text(word, w, h)
    y = top + over + h / 2                          # the line's middle
    tw = size * cq.Workplane("XY").text(word, 10, 1, combine=False, kind="bold").val().BoundingBox().xlen / 10
    for hx, hy in c.b["holes"]:                     # clear of each screw's counterbore by 0.5 mm
        gap = math.hypot(max(abs(hx - cx) - tw / 2, 0), max(abs(hy - y) - h / 2, 0))
        assert gap > S.M2_HEAD[0] / 2 + 0.2 + 0.5, "the name runs into the counterbore at %s" % ((hx, hy),)
    return S.engrave_text(cq.Plane(origin=(cx, y, c.zt), xDir=(1, 0, 0), normal=(0, 0, 1)), word, size, ENGRAVE_DEEP)


def decor(c, shell, back):
    """The mark as a badge glued into a pocket in the face, its pieces standing proud: the triangle in green, the
    three signed dots in blue, the two waiting dots in orange. The lower two signed dots are rings round the
    pinholes for RESET and BOOTSEL. Each piece its own STL, face down."""
    b, P = c.b, c.b["parts"]
    cx, cy, r, *under = b["mark"]
    pinned = dict(zip((3, 2), under))           # the dots with a pinhole: the slate's two, none on Mono (mono.py)
    pts = [(cx + r * math.cos(math.radians(90 - 72 * k)), cy + r * math.sin(math.radians(90 - 72 * k))) for k in range(5)]
    for k, ref in zip((3, 2), under):           # the lower dots, left and right: over RESET and BOOTSEL
        assert abs(pts[k][0] - P[ref]["x"]) < 0.01 and abs(pts[k][1] - P[ref]["y"]) < 0.01, "the mark's dot isn't over " + ref
    d, g = BADGE["depth"], BADGE["gap"]
    z0, z1 = c.zt - d + BADGE["short"], c.zt + BADGE["proud"]
    rad = {0: r / 4, 1: r / 6, 2: r / 4, 3: r / 4, 4: r / 6}
    tri = lambda grow, a, e: (cq.Workplane("XY").workplane(offset=a).polyline([pts[0], pts[2], pts[3]]).close()
                              .offset2D(grow).extrude(e - a))
    pocket = tri(0, c.zt - d, c.zt + 1)
    for k in range(5):
        pocket = pocket.union(S.cyl(*pts[k], rad[k], c.zt - d, c.zt + 1))
    shell = shell.cut(pocket)
    for k, ref in zip((3, 2), under):
        shell = shell.cut(S.cyl(P[ref]["x"], P[ref]["y"], PIN, c.zt - 5, c.zt + 1))
    top = lambda w: w.faces(">Z").edges().chamfer(BADGE["edge"])
    triangle = tri(-g, z0, z1)
    for k in (0, 2, 3):
        triangle = triangle.cut(S.cyl(*pts[k], rad[k] + g, z0 - 1, z1 + 1))
    shell = shell.cut(name(c, cx, pts[0][1] + rad[0]))
    out = [("badge triangle", top(triangle), GREEN, S.flip)]
    for k in (0, 2, 3):
        dot = S.cyl(*pts[k], rad[k] - g, z0, z1)
        if k in pinned:
            dot = dot.cut(S.cyl(*pts[k], PIN + g, z0 - 1, z1 + 1))
        out.append(("badge signed %d" % k, top(dot), BLUE, S.flip))
    for k in (1, 4):
        out.append(("badge waiting %d" % k, top(S.cyl(*pts[k], rad[k] - g, z0, z1)), ORANGE, S.flip))
    return shell, back, out


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
        # each button's job on every screen, as its shape: D0 out (Reject, No, Back), a square, stop; D1 on (Next),
        # a circle; D2 do (Sign, OK, Open), the mark's triangle
        cap_shapes={"D0": "square", "D1": "circle", "D2": "triangle"},
        led="D1", usb="J1", usb_edge="right", dock_depth=40.0, dock_plug=0.0,
        lug=("left", 6.0), tab=False,
        post_r=2.6,                 # the board's own keep-out round each hole (HOLE_RING in the generator)
        rest=[],
        # ribs under the back where it's pressed: the three buttons, and RESET and BOOTSEL
        support=[(P["SW1"]["x"] - 3.0, P["SW3"]["x"] + 3.0, P["SW1"]["y"] - S.REST_W / 2, P["SW1"]["y"] + S.REST_W / 2),
                 (rs["x"] - 3.0, bs["x"] + 3.0, rs["y"] - S.REST_W / 2, rs["y"] + S.REST_W / 2)],
        press=[], decor=decor,
        face=[],                    # the mark is decor's: a badge in a pocket, and the name over it
        engrave=ENGRAVE_DEEP,
        mark=(rs["x"] + r * math.cos(math.radians(54)), rs["y"] + r * math.sin(math.radians(54)), r, "SW4", "SW5"),
        flip="x",
        # turned over about x, the back's lower y is its top: the name, and the Source Location under it
        back_text=[("Picoquorum", (W / 2, H / 2 - 3.0), (44.0, 8.0), "bold"),
                   ("picoquorum.app", (W / 2, H / 2 + 7.0), (30.0, 3.2), "regular")],
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
