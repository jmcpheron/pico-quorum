"""console-s3's case: the stick. A bar the board's own size and shape, 75 x 27 x 12 mm, in the "shell" layout:
the face and the walls are one front shell, and a flat panel closes the back. Two M2 screws go in from the
front, through the shell's posts and the board's holes at the USB end, into bosses on the back panel. At
the other end the panel's tab hooks into a slot in the end wall, and a rib under the face holds the
board's antenna end down onto two ribs on the panel under the module's shield: no metal near the antenna.
The face has the window, caps on D0, D1 and D2 (Reject red, white, Sign green), a pinhole for BOOT, a
hole over the LED, and the mark, big, at the antenna end: its lower-left dot is RESET's hole. The USB-C
is open at the left end; a lanyard lug at the right. A dock holds it leaning back on the desk, its cable
out of the left side. (cad/consoles/README.md)

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/stick.py [screen.png]
(or tools/case build stick)

Writes out/stick/: stick_shell.stl (face down, as it prints), stick_back.stl (outside down), stick_cap_D0/D1/D2.stl
(flange down), stick_dock.stl, stick_assembly.step, stick_front.png, stick_apart.png, stick_dock.png.

The board's numbers are its generator's (hardware/prototypes/console-s3/gen_console_s3.py) and the placement file JLCPCB
built it from (console-s3/fab/cpl.csv), checked against each other. Not measured: the panel (glass, tape,
where its active area sits), the switches' height, the module. A first draft to print and try.
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402

S3 = os.path.join(S.REPO, "hardware", "prototypes", "console-s3")
_spec = importlib.util.spec_from_file_location("s3", os.path.join(S3, "gen_console_s3.py"))
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)        # the board's generator; it writes nothing on import
G.place_switches()
FAB = os.path.join(S3, "console-s3", "fab")
OUT = os.path.join(HERE, "out", "stick")
SCREEN = os.path.join(S.REPO, "docs", "quorum-ui", "feather", "06-review-head.png")
MARK_R = 7.5                # the mark's circle: as big as clears the window, BOOT's pinhole and the lanyard's slot


def board():
    P = S.parts(os.path.join(FAB, "cpl.csv"), os.path.join(FAB, "bom.csv"))
    for ref in ("SW1", "SW2", "SW3", "SW4", "SW5", "J1", "D1"):     # the fab file and the generator agree
        gx, gy = G.PARTS[ref]["at"]
        assert abs(P[ref]["x"] - gx) < 0.01 and abs(P[ref]["y"] - gy) < 0.01, ref
    W, H, yc = G.W, G.H, G.YC
    gx0, gy0, gx1, gy1 = G.GLASS
    aw, ah = G.PANEL["active"]
    # The active area: centred on the glass, as the board's own render draws it; ER-TFT1.14-2's drawing (as
    # PicoquorumKey reads it) has it 2.0 mm from the end away from the ribbon. The window shows either.
    cx = (gx0 + gx1) / 2
    active = (cx - aw / 2, yc - ah / 2, cx + aw / 2, yc + ah / 2)
    over = (min(cx - aw / 2, gx0 + 2.0), yc - ah / 2, max(cx + aw / 2, gx0 + 2.0 + aw), yc + ah / 2)
    mx, my = G.MOD_AT
    module = (mx - G.MOD_L / 2, mx + G.MOD_L / 2, my - G.MOD_W / 2, my + G.MOD_W / 2)
    return dict(
        name="stick", title="The stick (console-s3)", layout="shell",
        W=W, H=H, R=G.CORNER, T=1.6, holes=[xy for _, xy in G.HOLES], hole_d=2.2, parts=P,
        glass=G.GLASS, glass_z=(G.PANEL["foam"], G.PANEL["foam"] + G.GLASS_T), active=active, window_over=over,
        fold=(gx1, gx1 + G.FOLD_R, G.FOLD_Y[0], G.FOLD_Y[1]),
        module=module, module_h=S.WROOM[2],
        buttons=[("SW1", "D0"), ("SW2", "D1"), ("SW3", "D2")], pins=[("SW4", "BOOT")],
        led="D1", usb="J1", usb_edge="left", dock_depth=38.0, dock_plug=0.0,
        lug=("right", 6.0),
        # two ribs under the module's shield (its first 19 mm from the pin end), the plate's rib on the antenna end's
        # front, where the board has no copper and no parts (the keep-out, x 57.5 to the edge)
        rest=[(41.5, 41.5 + S.REST_W, 4.0, H - 4.0), (54.0, 54.0 + S.REST_W, 4.0, H - 4.0)],
        press=[(59.0, 63.0, 4.0, H - 4.0)],
        # the mark, big, at the antenna end: its lower-left dot over RESET (SW5) is RESET's hole
        face=[("mark", (P["SW5"]["x"] + MARK_R * math.cos(math.radians(54)), P["SW5"]["y"] + MARK_R * math.sin(math.radians(54)),
                        MARK_R, "SW5"))],
        flip="x",                   # turned over about its length to read the back
        back_text=[("Picoquorum", (33.0, yc), (40.0, 6.0), "bold")],
        seen=("D1",),
        views=dict(front=[("in the hand: two screws in the face", 55, -72), ("the back panel: the name, the Source Location", -50, -120)],
                   apart=[("apart: screws, front shell, caps, board, back panel", 28, -62)],
                   dock=[("on its dock, the cable out of the left", 18, -62)]),
    )


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else SCREEN)
    return bad


if __name__ == "__main__":
    sys.exit(main())
