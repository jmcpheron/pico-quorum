"""Open-top tray for the Adafruit ATECC608 STEMMA QT breakout (Adafruit 4314), parametric.

Run: uv run --python 3.11 --with cadquery python cad/key/tray.py

v1: a box open on top. The board sits on four bosses, and a peg on each boss goes up through
one of the board's mounting holes. Notches in both short walls let a STEMMA QT plug into either
port. Notches in both long walls let you get a fingernail under the board edge to lift it out.
Nothing holds the board down yet. A lid, snap ridges or screws come later.

Board numbers come from Adafruit's Eagle file (Adafruit_ATECC608.brd,
https://github.com/adafruit/Adafruit-ATECC608-PCB), not from calipers. Frame: x along the long
side, toward the CONN3 port is +; y across, toward the silkscreen title is +; z up, 0 at the
tray's underside. Board centre = tray centre. All dimensions mm.
"""
import cadquery as cq

# --- the board (from the .brd) ----------------------------------------------------------------
BOARD_X = 25.4         # 1.0 in
BOARD_Y = 17.78        # 0.7 in
BOARD_R = 2.54         # corner radius
PCB_T = 1.6            # standard; measure if the pegs feel off
HOLE_D = 2.5           # plated mounting holes, drill size (plating makes the finished hole a bit smaller)
HOLE_DX = 20.32        # hole centres, x pitch (0.8 in)
HOLE_DY = 12.7         # hole centres, y pitch (0.5 in)
KEEPOUT_D = 4.0        # silkscreen ring around each hole: the boss may touch the board inside this
PORT_W = 6.1           # JST SH 4-pin body incl. mounting tabs, across (y); both ports centred on y = 0
PORT_H = 2.9           # JST SH body height above the board
# nothing is on the underside; the 4-pin header row (unused, wired keys solder there) is at y = -6.35

# --- design choices ---------------------------------------------------------------------------
CLEAR = 0.5            # board edge to wall, each side
WALL = 1.8
FLOOR = 1.6
STANDOFF = 3.0         # floor top to board underside: room for header solder tails and wires
WALL_ABOVE = 2.0       # wall top above the board top
BOSS_D = KEEPOUT_D     # boss the board rests on
PEG_D = 2.3            # 0.1 mm per side clearance in a 2.5 hole
PEG_ABOVE = 0.8        # peg tip above the board top
PEG_CHAMFER = 0.4      # lead-in on the peg tip
PORT_NOTCH_W = 9.0     # short walls: room for the plug and fingers on its latch
GRIP_NOTCH_W = 8.0     # long walls: fingernail notch down to the board underside
GRIP = True

INNER_X = BOARD_X + 2 * CLEAR
INNER_Y = BOARD_Y + 2 * CLEAR
OUTER_X = INNER_X + 2 * WALL
OUTER_Y = INNER_Y + 2 * WALL
BOARD_BOT = FLOOR + STANDOFF
BOARD_TOP = BOARD_BOT + PCB_T
HEIGHT = BOARD_TOP + WALL_ABOVE


def rounded_box(x, y, h, r):
    return cq.Workplane("XY").rect(x, y).extrude(h).edges("|Z").fillet(r)


def tray(peg_d=PEG_D, grip=GRIP, label=True):
    """Floor down, open top. Prints as is, no supports."""
    part = rounded_box(OUTER_X, OUTER_Y, HEIGHT, BOARD_R + CLEAR + WALL)
    part = part.cut(rounded_box(INNER_X, INNER_Y, HEIGHT, BOARD_R + CLEAR).translate((0, 0, FLOOR)))

    holes = [(sx * HOLE_DX / 2, sy * HOLE_DY / 2) for sx in (-1, 1) for sy in (-1, 1)]
    bosses = cq.Workplane("XY").pushPoints(holes).circle(BOSS_D / 2).extrude(STANDOFF).translate((0, 0, FLOOR))
    peg_h = PCB_T + PEG_ABOVE
    pegs = (cq.Workplane("XY").pushPoints(holes).circle(peg_d / 2).extrude(peg_h)
            .faces(">Z").edges().chamfer(PEG_CHAMFER).translate((0, 0, BOARD_BOT)))
    part = part.union(bosses).union(pegs)

    # STEMMA QT ports, both ends: notch from the top down to the board top, so the wall still
    # covers the board edge and the plug drops in from above.
    port_depth = HEIGHT - BOARD_TOP
    for sx in (-1, 1):
        notch = cq.Workplane("XY").box(WALL * 3, PORT_NOTCH_W, port_depth + 1, centered=(True, True, False))
        part = part.cut(notch.translate((sx * (INNER_X / 2 + WALL / 2), 0, BOARD_TOP)))

    if grip:
        grip_depth = HEIGHT - BOARD_BOT
        for sy in (-1, 1):
            notch = cq.Workplane("XY").box(GRIP_NOTCH_W, WALL * 3, grip_depth + 1, centered=(True, True, False))
            part = part.cut(notch.translate((0, sy * (INNER_Y / 2 + WALL / 2), BOARD_BOT)))

    if label:
        # peg size, engraved in the underside, mirrored so it reads right with the tray flipped over
        text = (cq.Workplane("XY").text("%.2f" % peg_d, 4.0, 0.4, kind="bold", halign="center", valign="center")
                .mirror("YZ").translate((0, 0, -0.01)))
        part = part.cut(text)
    return part


def export(shape, name):
    cq.exporters.export(shape, f"cad/key/out/{name}.stl")
    bb = shape.val().BoundingBox()
    print(f"{name}.stl  {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm")


if __name__ == "__main__":
    import os
    os.makedirs("cad/key/out", exist_ok=True)
    print("tray outer %.2f x %.2f x %.2f, board underside at z %.2f, top at %.2f" % (
        OUTER_X, OUTER_Y, HEIGHT, BOARD_BOT, BOARD_TOP))
    export(tray(), "key_tray_v1")
    # fit check: three trays, pegs 2.20 / 2.30 / 2.40, size engraved underneath
    plate = None
    for i, d in enumerate((2.20, 2.30, 2.40)):
        t = tray(peg_d=d).translate((0, i * (OUTER_Y + 5), 0))
        plate = t if plate is None else plate.union(t)
    export(plate, "key_tray_v1_pegfit_x3")
