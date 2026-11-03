"""PicoQuorumKey rev A's case: the badge. Portrait, 49 x 64 x 12 mm, worn on a lanyard or laid on the desk
like a small handheld. A tub, and a front plate set into it flush, the board clamped between them by four M2
screws from the back through its four holes. The plate's rib holds the antenna end down onto two ribs in
the tub under the module's shield. On the plate: the window, caps on D0, D1 and D2 down its left side
(Reject red, white, Sign green), a hole over the LED, pinholes for BOOT and RESET, the mark and the name,
and the key window: an opening over the ATECC608C, the chip that is the key, with the board's 8-bit key
and its dragon beside it. The USB-C is open at the bottom edge; the lanyard's lug is at the top. A dock
holds it leaning back on the desk, the plug in a slot in its lip. (cad/consoles/README.md)

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/badge.py [screen.png]
(or tools/case build badge)

Writes out/badge/: badge_tub.stl (on its back, as it prints), badge_plate.stl (face down), badge_cap_D0/D1/D2.stl
(flange down), badge_dock.stl, badge_assembly.step, badge_front.png, badge_apart.png, badge_dock.png.

Rev A, the board ordered: 44 x 53 mm, 1.6 mm thick. Its parts are the placement file JLCPCB built it from
(hardware/out/rev-a/cpl.csv), its holes the drill file; the glass, the active area, the tape and the
module are its DESIGN.md's (rev B's, less 6 mm in x, which is how rev B was made from rev A). Rev B is
50 mm wide and 0.8 mm thick, with a key port at its top-left corner: this case doesn't fit it. Not
measured: the panel, the switches' height, the module. A first draft to print and try.
"""
import os
import re
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402

REV_A = os.path.join(S.REPO, "hardware", "picoquorum-key", "hardware", "out", "rev-a")
OUT = os.path.join(HERE, "out", "badge")
SCREEN = os.path.join(S.REPO, "docs", "quorum-ui", "feather", "03-review-head.png")
W, H = 44.0, 53.0
up = lambda y: H - y        # DESIGN.md's y runs down from the top edge; the placement file's, up from the bottom


def holes():
    """The 2.2 mm holes in the drill file JLCPCB drilled (NPTH, tool T2)."""
    src = open(os.path.join(REV_A, "gerbers", "picoquorum-key-NPTH.drl")).read()
    tool, out = None, []
    for line in src.splitlines():
        m = re.match(r"T(\d+)C([\d.]+)", line)
        if m:
            continue
        m = re.match(r"T(\d+)$", line)
        if m:
            tool = m.group(1)
            continue
        m = re.match(r"X([\d.-]+)Y([\d.-]+)", line)
        if m and tool == "2":
            out.append((float(m.group(1)), float(m.group(2))))
    assert len(out) == 4, out
    return sorted(out)


def key_window(z0, z1):
    """Over U2 (32, 21.5), the 8-bit key right of it and the dragon right of that (silk_art.py at rev A: the key's
    top left at (36.0, 33.0) and the dragon's at (40.7, 32.1), down from the top edge). It stops above BOOT, and
    the post round H2 bites its top right corner: the dragon's head is under it."""
    w = S.box(29.6, 43.2, 16.8, 23.6, z0, z1)
    return w.cut(S.cyl(41.0, 23.5, S.POST_R + 0.7, z0 - 1, z1 + 1)).edges("|Z").fillet(0.4)


def board():
    P = S.parts(os.path.join(REV_A, "cpl.csv"), os.path.join(REV_A, "bom.csv"))
    glass = (9.0, up(26.1), 40.0, up(8.5))
    active = (11.0, up(24.73), 35.9, up(9.87))
    for ref, y in (("SW1", 10.70), ("SW2", 17.30), ("SW3", 23.90)):      # the rail rows (DESIGN.md) are where JLCPCB put them
        assert abs(P[ref]["y"] - up(y)) < 0.01 and abs(P[ref]["x"] - 4.5) < 0.01, ref
    return dict(
        name="badge", title="The badge (PicoQuorumKey rev A)",
        W=W, H=H, R=1.5, T=1.6, holes=holes(), hole_d=2.2, parts=P,
        glass=glass, glass_z=(1.5, 3.1), active=active,     # 1.5 mm tape (DESIGN.md), 1.6 mm glass
        fold=(40.0, 40.5, up(23.0), up(13.9)),
        module=(24.0, 42.0, up(25.5), H), module_h=S.WROOM[2],
        buttons=[("SW1", "D0"), ("SW2", "D1"), ("SW3", "D2")], pins=[("SW6", "BOOT"), ("SW7", "RESET")],
        led="D1", usb="J1", usb_edge="bottom", dock_depth=50.0, dock_plug=20.0,
        lug=("top", 6.0),
        # ribs under the module's shield; the plate's rib on the front of the antenna band, which has silk and no parts
        rest=[(25.5, 40.5, 31.0, 31.0 + S.REST_W), (25.5, 40.5, 43.0, 43.0 + S.REST_W)],
        press=[(6.0, 38.0, 46.0, 51.0)],
        key_window=key_window,
        face=[("mark", (15.5, 15.0, 4.2)), ("text", ("PicoQuorum", (15.2, 6.2), (22.0, 3.6)))],
        flip="y",                   # turned over about its height to read the back
        back_text=[("PicoQuorum", (22.0, 38.0), (30.0, 6.0), "bold"), ("PicoQuorum.app", (22.0, 31.0), (24.0, 3.0), "regular")],
        seen=("D1", "U2"),
        views=dict(front=[("in the hand", 58, -78), ("the back: the name, the Source Location, four screws", -55, 110)],
                   apart=[("apart: tub, screws, board, plate, caps", 30, -60)],
                   dock=[("on its dock, the plug in the lip", 20, -68)]),
    )


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else SCREEN)
    return bad


if __name__ == "__main__":
    sys.exit(main())
