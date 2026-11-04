"""PicoQuorumKey rev B's case: the badge, for the board with its key port fitted. Portrait, 55 x 64 x 12.5 mm,
worn on a lanyard or laid on the desk like a small handheld. The "shell" layout, as the stick's: the face and the
walls are one front shell, and a flat panel closes the back. Four M2 screws go in from the front, through the
shell's posts and the board's holes, into bosses on the back panel. At the antenna end, the top, the panel's
tab hooks into a slot in the top wall. On the face: the window, caps on D0, D1 and D2 down its left side
(Reject red, white, Sign green, 1.5 mm proud), holes over the LED and the key port's LED, pinholes for BOOT and
RESET, and the mark, big. The back panel carries the name.

The board is taken as 1.6 mm thick, not rev B's 0.8. Drawn for 0.8, the printed case came out with its back
panel about 1 mm proud and its caps flush, and calipers on a fitted board read 5.5 mm from the board's back to
the top of a switch (5.1-5.2 pressed): on a 1.6 mm board that is 3.9 mm over its front, the switch's datasheet
3.8. The board's own thickness hasn't been measured. A straddle plug for the key port needs 0.8.

The top-left corner is open for the key port: its plug stands out of the board's top edge, and a key-c
plugs onto it from outside, the case cut away round it. A rib under the face holds the board's antenna end
down on the antenna's keep-out band, which has no parts, not across U6, U7, R17 and R18 to the left of it;
two ribs on the panel come up under the module's shield. Ribs on the panel back the board under D0-D2 and under BOOT and RESET, clear of the test pads. The USB-C is open at the bottom edge;
the lanyard's lug is at the top right. A dock holds it leaning back on the desk, the plug in a slot in its
lip. (cad/consoles/README.md)

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/badge.py [screen.png]
(or tools/case build badge)

Writes out/badge/: badge_shell.stl (face down, as it prints), badge_back.stl (outside down), badge_cap_D0/D1/D2.stl
(flange down), badge_dock.stl, badge_assembly.step, badge_front.png, badge_face.png, badge_apart.png,
badge_dock.png.

Rev B with the port: 50 x 53 mm. Its parts are the placement file and BOM JLCPCB builds the port's
boards from (hardware/out/rev-b/cpl-port.csv, bom-port.csv), its holes the drill file; the outline, the glass,
the active area, the tape, the module, the plug and the back's test pads are its DESIGN.md's and
tools/gen/gen_pcb.py's. The plug (fitted by hand) and a key-c on it are boxes: the plug's drawing gives its
width and length, not its height; the key-c is its design's 16 x 36 mm. Not measured: the panel, the
module, the plug. A first draft to print and try.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402

REV_B = os.path.join(S.REPO, "hardware", "picoquorum-key", "hardware", "out", "rev-b")
OUT = os.path.join(HERE, "out", "badge")
SCREEN = os.path.join(S.REPO, "docs", "quorum-ui", "feather", "03-review-head.png")
# 1.6 mm, not rev B's 0.8: the case drawn for 0.8 came out with its back 0.8-1 mm proud and its caps flush, not
# 1 mm proud, and with 1.6 the measured switches are 3.9 mm over the front, their datasheet's 3.8. Not measured yet.
W, H, T = 50.0, 53.0, 1.6
up = lambda y: H - y        # DESIGN.md's y runs down from the top edge; the placement file's, up from the bottom
# The key port (DESIGN.md): the plug straddles a 7.90 mm paddle at X 4.05-11.95, its tip on the top edge, the board
# cut away left of it and in a slot right of it (X 11.95-14.0), both 4.5 mm down. The plug is 8.4 mm wide and stands
# 9.6 mm past the tip (its footprint's drawing). A key-c on it lies over X 0-16, its own edge about 3 mm past the tip
# (9.6 mm of plug less the 6.5 mm its receptacle takes).
PADDLE, SLOT_X1, NOTCH_D = (4.05, 11.95), 14.0, 4.5
PLUG = (8.4, 9.6, 3.4)      # across, past the tip, thick (not given: a USB-C plug's usual, straddling the board)
KEYC = (16.0, 36.0, 7.4)    # across, long, thick with its receptacle and its parts (key-c's design)
KEYC_GAP = 3.0
# The panel as fitted on the first board, from a photo of the printed badge (2026-11-04): the picture sits 0.8 mm left
# of DESIGN.md's place for it. The window's right edge showed 1.3 mm of black, not its 0.5 mm margin, and the rail's
# divider, 22.3% across the picture, put its left edge 0.3 mm under the window's. Whether that is how this panel lies on
# its tape, or where the active area sits on the glass, one board doesn't say: the glass and the ribbon move with it.
PANEL_DX = -0.8
SWITCH_TOP = 5.5            # the switches' tops from the board's back: calipers, 2026-11-03 (5.1-5.2 pressed)
SWITCHES = ("SW1", "SW2", "SW3", "SW6", "SW7")


def holes():
    """The 2.2 mm holes in the drill file (NPTH, tool T2)."""
    tool, out = None, []
    for line in open(os.path.join(REV_B, "gerbers", "picoquorum-key-NPTH.drl")).read().splitlines():
        m = re.match(r"T(\d+)$", line)
        if m:
            tool = m.group(1)
            continue
        m = re.match(r"X([\d.-]+)Y([\d.-]+)", line)
        if m and tool == "2":
            out.append((float(m.group(1)), float(m.group(2))))
    assert len(out) == 4, out
    return sorted(out)


def board():
    P = S.parts(os.path.join(REV_B, "cpl-port.csv"), os.path.join(REV_B, "bom-port.csv"))
    for ref, y in (("SW1", 10.70), ("SW2", 17.30), ("SW3", 23.90)):      # the rail rows (DESIGN.md) are where the files put them
        assert abs(P[ref]["y"] - up(y)) < 0.01 and abs(P[ref]["x"] - 10.5) < 0.01, ref
    for ref in ("U6", "U7", "R17", "R18", "D4"):                         # the port's parts, which this case is for
        assert ref in P, ref
    for ref in SWITCHES:                                                 # as measured, not the datasheet's 3.8
        P[ref]["h"] = SWITCH_TOP - T
    pz = -T / 2                                                          # the plug's and the key's axis: the board's middle
    px = sum(PADDLE) / 2
    return dict(
        name="badge", title="The badge (PicoQuorumKey rev B, key port)", layout="shell", window_c=1.5, cap_proud=1.5,
        W=W, H=H, R=1.5, T=T, holes=holes(), hole_d=2.2, parts=P,
        board_cut=[(-1.0, PADDLE[0], up(NOTCH_D), H + 1), (PADDLE[1], SLOT_X1, up(NOTCH_D), H + 1)],
        extras=[((px - PLUG[0] / 2, px + PLUG[0] / 2, H - 2.7, H + PLUG[1], pz - PLUG[2] / 2, pz + PLUG[2] / 2), S.K.STEEL, "key port plug"),
                ((px - KEYC[0] / 2, px + KEYC[0] / 2, H + KEYC_GAP, H + KEYC_GAP + KEYC[1], pz - KEYC[2] / 2, pz + KEYC[2] / 2),
                 (0.10, 0.25, 0.60), "key-c")],
        glass=(15.0 + PANEL_DX, up(26.1), 46.0 + PANEL_DX, up(8.5)), glass_z=(1.5, 3.1),     # 1.5 mm tape (DESIGN.md), 1.6 mm glass
        active=(17.0 + PANEL_DX, up(24.73), 41.9 + PANEL_DX, up(9.87)),
        fold=(46.0 + PANEL_DX, 46.5 + PANEL_DX, up(23.0), up(13.9)),
        module=(30.0, 48.0, up(25.5), H), module_h=S.WROOM[2],
        buttons=[("SW1", "D0"), ("SW2", "D1"), ("SW3", "D2")], pins=[("SW6", "BOOT"), ("SW7", "RESET")],
        led=["D1", "D4"], usb="J1", usb_edge="bottom", dock_depth=50.0, dock_plug=20.0,
        lug=("top", 6.0), lug_at=34.0,                                  # right of the key port's opening
        tab=("top", 20.0, 46.0),                                        # the back panel's tab into the top wall, by the antenna
        notch=(-10.0, px + KEYC[0] / 2 + 0.5, H + 0.2),                 # the key port: open from the board's top edge
        # ribs under the module's shield; the face's rib on the front of the antenna's keep-out band (X 29.5 on, the
        # top 7 mm), which has no parts. Left of it, the band holds U6, U7, R18 and R17.
        rest=[(31.5, 46.5, 31.0, 31.0 + S.REST_W), (31.5, 46.5, 43.0, 43.0 + S.REST_W)],
        press=[(30.5, 46.0, 46.0, 52.0)],
        # ribs on the panel under the board where it's pressed: D0-D2, and BOOT and RESET. The back's test pads are at
        # X 15-41 (y 14 and 18) and (8.4, 10), (15, 10): the ribs miss them.
        support=[(9.5, 11.5, 27.0, 45.0), (42.6, 44.6, 4.5, 16.5)],
        face=[("mark", (20.0, 14.0, 8.0))],                             # the mark alone, big, under the screen
        flip="y",                   # turned over about its height to read the back
        back_text=[("PicoQuorum", (25.0, 26.5), (42.0, 10.0), "bold")],
        seen=("D1", "D4", "key port plug", "key-c"),
        views=dict(front=[("in the hand: four screws in the face, a key-c in its port", 58, -78), ("the back panel: the name, the Source Location", -55, 110)],
                   apart=[("apart: screws, front shell, caps, board, back panel", 30, -60)],
                   dock=[("on its dock, the plug in the lip", 20, -68)]),
    )


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else SCREEN)
    return bad


if __name__ == "__main__":
    sys.exit(main())
