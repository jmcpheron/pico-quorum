#!/usr/bin/env python3
"""key-c P2 print mock-up: one plain solid of the key's shape and size, for a 3D printer.

    pip install cadquery
    python3 hardware/key-pcb/key-c-usbc/3d/print_mockup.py

Writes key-c-P2-print.step next to this file. Unlike key-c-P2.step it has no real parts: the
board, the chips' bodies, the small parts and the USB-C shell are blocks fused into one solid.
The USB-C shell is only its outside, with an open socket a real USB-C plug slides into (no
tongue, no contacts). Its walls are thicker than metal so they print, so it is a little bigger
than the real receptacle; the socket has a print clearance round the plug.

Frame as the other STEP files: origin at the board centre, Z = 0 the back face, USB-C end at -Y,
mm. Part positions are the board's (key-c-usbc.kicad_pcb), moved into this frame.
"""
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "key-c-P2-print.step")

# board: 16 x 36 mm, 2 mm corners, 1.6 mm thick as ordered
BOARD_W, BOARD_L, BOARD_T, BOARD_R = 16.0, 36.0, 1.6, 2.0
HOLE_XY, HOLE_D = (0.0, 14.0), 3.0                 # H1, the lanyard hole

# USB-C socket. A real plug is 8.25 x 2.40 mm, 6.65 mm long; these add print clearance.
PLUG_W, PLUG_H = 8.70, 2.90                        # socket opening (stadium)
SOCKET_DEPTH = 7.0                                 # from the board edge
WALL = 0.8                                         # two 0.4 mm perimeters
FLOOR = 0.2                                        # under the socket, above the board
SHELL_L = SOCKET_DEPTH + WALL                      # 7.8, as the real shell

# chip and small-part bodies: (name, x centre, y centre, size x, size y, height above board)
BODIES = [
    ("U1 ATECC608C SOIC-8",  0.00,  2.675, 4.90, 3.90, 1.75),
    ("U2 USBLC6 SOT-23-6",   0.00, -5.500, 2.90, 1.60, 1.45),
    ("C1 0402",              3.75,  0.200, 1.00, 0.50, 0.50),
    ("C2 0402",              0.00, -2.500, 0.50, 1.00, 0.50),
    ("R1 0402",             -2.40, -7.600, 0.50, 1.00, 0.35),
    ("R2 0402",              2.15, -8.000, 0.50, 1.00, 0.35),
]


def board():
    b = (cq.Workplane("XY").rect(BOARD_W, BOARD_L).extrude(BOARD_T)
         .edges("|Z").fillet(BOARD_R))
    return b.faces(">Z").workplane().center(*HOLE_XY).hole(HOLE_D)


def usb_shell():
    """The receptacle's outside, flat on the board, with the plug socket open at the edge."""
    edge = -BOARD_L / 2
    zc = BOARD_T + FLOOR + PLUG_H / 2                # socket centre line
    out_w, out_h = PLUG_W + 2 * WALL, PLUG_H + 2 * WALL
    # XZ workplane's normal is -Y, so extrude negative to grow into the board (+Y)
    xz = cq.Workplane("XZ", origin=(0, edge, 0))
    rounded = xz.center(0, zc).slot2D(out_w, out_h).extrude(-SHELL_L)
    footing = (xz.center(0, (BOARD_T + zc) / 2)
               .rect(out_w, zc - BOARD_T).extrude(-SHELL_L))
    socket = xz.center(0, zc).slot2D(PLUG_W, PLUG_H).extrude(-SOCKET_DEPTH)
    return rounded.union(footing).cut(socket)


def mockup():
    m = board()
    for _, x, y, sx, sy, h in BODIES:
        m = m.union(cq.Workplane("XY").box(sx, sy, h, centered=(True, True, False))
                    .translate((x, y, BOARD_T)))
    m = m.union(usb_shell())
    solids = m.solids().vals()
    assert len(solids) == 1, f"expected one fused solid, got {len(solids)}"
    assert solids[0].isValid()
    return m


if __name__ == "__main__":
    m = mockup()
    cq.exporters.export(m, OUT, opt={"write_pcurves": False})
    bb = m.val().BoundingBox()
    print(f"{OUT}\n  {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm, "
          f"{m.val().Volume():.0f} mm^3, 1 solid")
