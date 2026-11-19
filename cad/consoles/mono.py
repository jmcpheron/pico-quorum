"""Mono's case. A slender bar round the 40 x 89.5 mm board, in the slate's "shell" layout: the face and the walls are
one front shell, and a flat panel closes the back. Four M2 screws go in from the front, through the shell's posts
and the board's four M2 holes, into bosses on the back panel.

No screw holds the top end, behind the screen: the two beside the buttons are 24 mm from the top edge. So the board
lies between rests there. In the shell, a block in each top corner, beside the glass, on the board's front. On the
back panel, ribs across the board's back: one behind each row of the glass's foam pads, the one under the buttons,
and one midway between the screws' rows. Two tabs hold the panel's top end in slots in the top wall, either side of
the lanyard's slot, so its ribs can bear.

The face has the window at the top, caps on D0, D1 and D2 in a row under it, and in the plain field below them the
mark alone, with no name: a badge, its pieces printed in colour and glued into a pocket (rp.decor), 9 mm in radius,
in the middle of the field. Mono has no RESET or BOOTSEL buttons, so the mark's dots are whole, with no pinholes.
A hole over the LED. The USB-C is open at the bottom end, left of centre; a lanyard lug at the top.
The back has picoquorum.app along its length, which is the name and the Source Location both, since the case covers
the board's own: cut 0.6 mm in mono_back.stl, and in mono_back.3mf filled flush in two colours, picoquorum in one
and .app in another. A dock holds it leaning back, its plug down into a slot in the lip. (cad/consoles/README.md)

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/mono.py [screen.png]
(or tools/case build mono)

Writes out/mono/: mono_shell.stl (face down, as it prints), mono_back.stl (outside down), mono_back.3mf (the back
as three bodies: black, and its words in green and orange), mono_cap_D0/D1/D2.stl (flange down), mono_badge_*.stl
(the badge's six pieces, face down), mono_dock.stl, mono_assembly.step, mono_front.png, mono_face.png,
mono_apart.png, mono_dock.png.

The board's numbers are its generator's (hardware/mono/gen_mono.py) and the placement file made for JLCPCB
(mono/fab/cpl.csv), checked against each other. The glass and the active area are the generator's, from the
panel's datasheet. Nothing is built: the board, the foam, the switches' height and the USB-C's legs under the
board are all unmeasured. A first draft to print and try.
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import rp as RP         # noqa: E402  the slate's badge and name (decor)

MONO = os.path.join(S.REPO, "hardware", "mono")
_spec = importlib.util.spec_from_file_location("gen_mono", os.path.join(MONO, "gen_mono.py"))
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)        # the board's generator; it writes nothing on import
FAB = os.path.join(MONO, "mono", "fab")
OUT = os.path.join(HERE, "out", "mono")
SCREEN = os.path.join(S.REPO, "docs", "quorum-ui", "feather", "06-review-head.png")
BACK_ROOM = 1.6             # under the board: the USB-C's shell legs, and the bosses' height for the M2 thread
# The mark in the field under the buttons, alone: its centre and radius. The centre puts the mark midway between
# the caps' holes and the LED's hole, for any radius (the mark's own middle is 0.0955 r over its centre). The radius
# is 1.5 times the slate's, near enough (r 6.4 there, from RESET and BOOTSEL; here nothing fixes it).
# Given in the generator's frame (y down), so it keeps its place to the parts when the board changes.
MARK = (20.0, 52.0, 9.0)
# The back's words: picoquorum.app along the length, its room (long, tall), and which way it reads: -1 is from the
# top end down, so it reads level with the case on its side, top end to the left
BACK_WORDS = ((76.0, 10.0), -1)
FOLD = 1.5                  # the ribbon's fold past the glass's right end: the README reads the drawing as 0.5 at
                            # most; the slate allows 2.0. 1.5 leaves the wall 1.8 mm clear
# The top end, where no screw is. The shell's rests on the board's front, one in each top corner: this far down from
# the top edge, and this far off the glass's ends (where the glass lies on its foam isn't measured)
REST_TOP, REST_OFF = 4.0, 0.5
REST_MISS = 1.5             # a rest in the shell from FID1's centre and the ribbon's fold, a tab from the lanyard's slot: at the least
RIB_MISS = 2.0              # a rib on the back from KEY 2's holes (a header's pins would stand out) and the jig's pads
TABS = [(4.0, 14.0), (26.0, 36.0)]      # the back panel's tabs into the top wall: x, either side of the lanyard's slot


def board():
    P = S.parts(os.path.join(FAB, "cpl.csv"), os.path.join(FAB, "bom.csv"))
    # the generator's y runs down from the first outline's top-left corner, the board from TOP to H; the fab files'
    # runs up from the bottom edge
    W, H = G.W, G.H
    up = lambda xy: (xy[0], H - xy[1])
    for ref in ("SW1", "SW2", "SW3", "J1", "J2", "D1", "U1"):     # the fab file and the generator agree
        gx, gy = up(G.AT[ref][:2])
        assert abs(P[ref]["x"] - gx) < 0.01 and abs(P[ref]["y"] - gy) < 0.01, ref
    glass = (G.GX0, H - G.GY1, G.GX1, H - G.GY0)
    yc = H - G.YC
    aw, ah = G.PANEL["active"]
    # the active area is centred on the board (XA), 1.445 mm off the glass's centre by the datasheet. PicoquorumKey's
    # notes read 2.0: then it sits 0.555 further from the ribbon, left. The window shows it either way.
    active = (G.XA - aw / 2, yc - ah / 2, G.XA + aw / 2, yc + ah / 2)
    over = (active[0] - (2.0 - G.PANEL["active_off"]), active[1], active[2], active[3])
    rw = G.PANEL["ribbon"]
    holes = [up(G.AT[h][:2]) for h in ("H1", "H2", "H3", "H4")]
    cx, cy, r = MARK[0], H - MARK[1], MARK[2]
    led = P["D1"]
    assert math.hypot(led["x"] - cx, led["y"] - cy) > r + r / 4 + S.LED_HOLE, "the mark runs into the LED's hole"
    hb = H - G.TOP                  # the board's top edge
    far = lambda box, at: math.hypot(max(box[0] - at[0], at[0] - box[1], 0), max(box[2] - at[1], at[1] - box[3], 0))
    # the shell's rests: from 0.5 mm into the walls to REST_OFF off the glass's ends
    press = [(-0.5, glass[0] - REST_OFF, hb - REST_TOP, hb + 0.5), (glass[2] + REST_OFF, W + 0.5, hb - REST_TOP, hb + 0.5)]
    for q in press:
        assert far(q, up(G.AT["FID1"][:2])) >= REST_MISS, "a rest in the shell is on FID1"
        assert q[2] - (yc + rw / 2) >= REST_MISS, "a rest in the shell is on the ribbon's fold"
    # the back panel's ribs: under the buttons, where the board is pressed; behind the glass's foam pads, its lower
    # row and its top row, the top one on to the corners, behind the shell's rests; and one midway between the
    # screws' rows, so the panel doesn't give when the case is held
    pad, hw = G.PANEL["pad"] / 2, S.REST_W / 2
    bar = lambda x0, x1, y: (x0, x1, y - hw, y + hw)
    support = [bar(P["SW1"]["x"] - 3.0, P["SW3"]["x"] + 3.0, P["SW1"]["y"]),
               bar(glass[0], glass[2], glass[1] + pad), bar(1.0, W - 1.0, glass[3] - pad),
               bar(P["SW1"]["x"] - 3.0, P["SW3"]["x"] + 3.0, (holes[0][1] + holes[2][1]) / 2)]
    miss = [up((x, G.TPY)) for x in G.TP_X.values()] + [up((G.AT["J4"][0] + 2.54 * i, G.AT["J4"][1])) for i in range(5)]
    for q in support:
        assert min(far(q, at) for at in miss) >= RIB_MISS, "a rib on the back is on the jig's pads or KEY 2's holes"
    lug = (W / 2 - S.LUG_HOLE[0] / 2, W / 2 + S.LUG_HOLE[0] / 2)
    assert all(x1 <= lug[0] - REST_MISS or x0 >= lug[1] + REST_MISS for x0, x1 in TABS), "a tab's slot is by the lanyard's"
    return dict(
        name="mono", title="Mono's case", layout="shell",
        W=W, H=H - G.TOP, R=G.CORNER, T=1.6, holes=holes, hole_d=2.2, parts=P,
        glass=glass, glass_z=(G.PANEL["foam"], G.PANEL["foam"] + G.PANEL["thick"]), active=active, window_over=over,
        fold=(glass[2], glass[2] + FOLD, yc - rw / 2, yc + rw / 2),
        module=None, module_h=BACK_ROOM,
        buttons=[("SW1", "D0"), ("SW2", "D1"), ("SW3", "D2")], pins=[],
        # as the slate's: D0 out (Reject, No, Back), a square; D1 on (Next), a circle; D2 do (Sign, OK, Open), a triangle
        cap_shapes={"D0": "square", "D1": "circle", "D2": "triangle"},
        # the caps' holes 1.2 times the slate's across, for faces as much larger, and their flanges
        # 7.4 mm, wider to hold them: 0.3 mm off the posts beside D0 and D2. Each flange still sits on its switch,
        # with the slate's play and clearance, and reaches 0.35 mm past its hole at the least (the slate's: 0.25)
        cap_scale=1.2, flange_over=2.3,
        # printed, the caps were a bit too big for their holes at the slate's 0.2 mm a side: the holes are in the
        # shell's first layers, which spread on the bed. 0.4 mm a side now, by smaller stems (circle 4.6 mm,
        # square 4.2, triangle 6.5); the holes are as they were, so a printed shell takes the new caps
        cap_clear=0.4,
        led="D1", usb="J1", usb_edge="bottom", dock_depth=55.0, dock_plug=20.0,
        lug=("top", 6.0), tab=("top", TABS),
        post_r=G.HOLE_RING,         # the board's own keep-out round each hole
        rest=[], support=support, press=press, decor=RP.decor, face_name=False,
        face=[],                    # the mark is decor's: a badge in a pocket, and the name over it
        engrave=RP.ENGRAVE_DEEP,
        mark=(cx, cy, r),           # no switch under its dots
        flip="y",                   # turned over about its length to read the back, as the badge
        # one line, in two pieces to print in two colours (the 3MF); an address, so lower case (docs/BRAND.md)
        back_text=[("picoquorum.app", (W / 2, hb / 2), BACK_WORDS[0], "bold",
                    dict(along=BACK_WORDS[1], parts=[("picoquorum", "green", S.GREEN), (".app", "orange", RP.ORANGE)]))],
        seen=("D1",),
        views=dict(front=[("in the hand: four screws in the face", 58, -78), ("the back: picoquorum.app, in two colours", -55, 110)],
                   apart=[("apart: screws, front shell, caps, board, back panel", 30, -60)],
                   dock=[("on its dock, the plug in the lip", 20, -68)]),
    )


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else SCREEN)
    return bad


if __name__ == "__main__":
    sys.exit(main())
