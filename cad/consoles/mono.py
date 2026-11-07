"""Mono's case. A slender bar round the 40 x 96 mm board, in the slate's "shell" layout: the face and the walls are
one front shell, and a flat panel closes the back. Four M2 screws go in from the front, through the shell's posts
and the board's four M2 holes, into bosses on the back panel. The board has no radio, so no end is kept free of
metal, and no tab.

The face has the window at the top, caps on D0, D1 and D2 in a row under it, and in the plain field below them the
name and the mark, as on the slate: the mark a badge, its pieces printed in colour and glued into a pocket, the name
over it cut to show a second colour (rp.decor). Mono has no RESET or BOOTSEL buttons, so the mark's dots are whole,
with no pinholes. A hole over the LED. The USB-C is open at the bottom end, left of centre; a lanyard lug at the top.
The back has the name and the Source Location, since the case covers the board's own. A dock holds it leaning back,
its plug down into a slot in the lip. (cad/consoles/README.md)

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/mono.py [screen.png]
(or tools/case build mono)

Writes out/mono/: mono_shell.stl (face down, as it prints), mono_back.stl (outside down), mono_cap_D0/D1/D2.stl
(flange down), mono_badge_*.stl (the badge's six pieces, face down), mono_dock.stl, mono_assembly.step,
mono_front.png, mono_face.png, mono_apart.png, mono_dock.png.

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
# The mark in the field under the buttons, over the RP2350: its centre and radius, the slate's size near enough
# (r 6.4 there, from RESET and BOOTSEL; here nothing fixes it). The name goes over it (rp.NAME).
MARK = (20.0, 38.0, 6.0)
FOLD = 1.5                  # the ribbon's fold past the glass's right end: the README reads the drawing as 0.5 at
                            # most; the slate allows 2.0. 1.5 leaves the wall 1.8 mm clear


def board():
    P = S.parts(os.path.join(FAB, "cpl.csv"), os.path.join(FAB, "bom.csv"))
    W, H = G.W, G.H
    up = lambda xy: (xy[0], H - xy[1])     # the generator's y runs down from the top edge; the fab files' up
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
    cx, cy, r = MARK
    led = P["D1"]
    assert math.hypot(led["x"] - cx, led["y"] - cy) > r + r / 4 + S.LED_HOLE, "the mark runs into the LED's hole"
    return dict(
        name="mono", title="Mono's case", layout="shell",
        W=W, H=H, R=G.CORNER, T=1.6, holes=holes, hole_d=2.2, parts=P,
        glass=glass, glass_z=(G.PANEL["foam"], G.PANEL["foam"] + G.PANEL["thick"]), active=active, window_over=over,
        fold=(glass[2], glass[2] + FOLD, yc - rw / 2, yc + rw / 2),
        module=None, module_h=BACK_ROOM,
        buttons=[("SW1", "D0"), ("SW2", "D1"), ("SW3", "D2")], pins=[],
        # as the slate's: D0 out (Reject, No, Back), a square; D1 on (Next), a circle; D2 do (Sign, OK, Open), a triangle
        cap_shapes={"D0": "square", "D1": "circle", "D2": "triangle"},
        led="D1", usb="J1", usb_edge="bottom", dock_depth=55.0, dock_plug=20.0,
        lug=("top", 6.0), tab=False,
        post_r=G.HOLE_RING,         # the board's own keep-out round each hole
        rest=[],
        # a rib under the back where it's pressed: the three buttons. The jig's pads are lower down, under U1
        support=[(P["SW1"]["x"] - 3.0, P["SW3"]["x"] + 3.0, P["SW1"]["y"] - S.REST_W / 2, P["SW1"]["y"] + S.REST_W / 2)],
        press=[], decor=RP.decor,
        face=[],                    # the mark is decor's: a badge in a pocket, and the name over it
        engrave=RP.ENGRAVE_DEEP,
        mark=(cx, cy, r),           # no switch under its dots
        flip="y",                   # turned over about its length to read the back, as the badge
        back_text=[("Picoquorum", (W / 2, 54.0), (30.0, 6.0), "bold"),
                   ("picoquorum.app", (W / 2, 46.0), (24.0, 3.0), "regular")],
        seen=("D1",),
        views=dict(front=[("in the hand: four screws in the face", 58, -78), ("the back: the name, the Source Location", -55, 110)],
                   apart=[("apart: screws, front shell, caps, board, back panel", 30, -60)],
                   dock=[("on its dock, the plug in the lip", 20, -68)]),
    )


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else SCREEN)
    return bad


if __name__ == "__main__":
    sys.exit(main())
