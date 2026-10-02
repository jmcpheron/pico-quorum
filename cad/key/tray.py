"""Snap-lid case for the Adafruit ATECC608 STEMMA QT breakout (Adafruit 4314), parametric.

Run: uv run --python 3.11 --with cadquery python cad/key/tray.py

The tray is open on top. The board sits on four bosses, and a peg on each boss goes up through
one of the board's mounting holes. Notches in both short walls let a STEMMA QT plug into either
port. Notches in both long walls let you get a fingernail under the board edge to lift it out.

v2 adds a lid. Its skirt slides down over the tray's walls, and a groove inside the skirt clicks
over four small bumps on the outside of the long walls. Two ribs under the lid stop 0.2 mm above
the board, so it can't lift off its pegs. The port openings run up into the lid, so a plugged-in
cable still fits with the lid on.

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
# silkscreen only (no parts) along the top edge, y +6.5 to the edge, and below the header pads,
# y -7.2 to the edge, |x| < 5: the lid ribs land there

# --- tray -------------------------------------------------------------------------------------
CLEAR = 0.5            # board edge to wall, each side
WALL = 1.8
FLOOR = 1.6
STANDOFF = 3.0         # floor top to board underside: room for header solder tails and wires
WALL_ABOVE = 2.0       # wall top above the board top
BOSS_D = KEEPOUT_D     # boss the board rests on
PEG_D = 2.4            # v1 fit check 2026-10-02: 2.40 won over 2.20 and 2.30
PEG_ABOVE = 0.8        # peg tip above the board top
PEG_CHAMFER = 0.4      # lead-in on the peg tip
PORT_NOTCH_W = 9.0     # short walls: room for the plug and fingers on its latch
GRIP_NOTCH_W = 8.0     # long walls: fingernail notch down to the board underside
GRIP = True

# --- snap and lid -----------------------------------------------------------------------------
SNAP_R = 0.5           # bumps: half-round ridges on the long outer walls, 4 of them
SNAP_PROUD = 0.35      # how far a bump stands off the wall; minus LID_CLEAR = the click (0.2)
SNAP_LEN = 5.0         # each bump, along x, on the flat wall between the grip notch and the corner
SNAP_BELOW_TOP = 1.4   # bump centre below the wall top
GROOVE_EXTRA = 0.05    # groove radius over the bump radius
LID_CLEAR = 0.15       # skirt inner face to tray outer wall, each side
SKIRT_T = 1.2
SKIRT_H = 3.0          # how far the skirt reaches down the tray wall
LEAD_IN = 0.5          # 45 degree chamfer inside the skirt mouth
HEADROOM = 1.5         # lid ceiling above the wall top: 3.5 mm over the board for the ports and a plug
LID_T = 1.2            # lid top plate
RIB_W = 0.9
RIB_GAP = 0.2          # rib tip above the board top
RIBS = [(0, 7.6, 12.0), (0, -8.1, 9.0)]   # (x, y, length along x), board frame

INNER_X = BOARD_X + 2 * CLEAR
INNER_Y = BOARD_Y + 2 * CLEAR
INNER_R = BOARD_R + CLEAR
OUTER_X = INNER_X + 2 * WALL
OUTER_Y = INNER_Y + 2 * WALL
OUTER_R = INNER_R + WALL
FLAT_X = OUTER_X / 2 - OUTER_R      # long walls are flat for |x| below this
BOARD_BOT = FLOOR + STANDOFF
BOARD_TOP = BOARD_BOT + PCB_T
HEIGHT = BOARD_TOP + WALL_ABOVE
SNAP_Z = HEIGHT - SNAP_BELOW_TOP
SNAP_X = (GRIP_NOTCH_W / 2 + FLAT_X) / 2
SNAP_AXIS_Y = OUTER_Y / 2 + SNAP_PROUD - SNAP_R   # bump/groove axis, |y|
CEILING = HEIGHT + HEADROOM
SKIRT_IN_X = OUTER_X + 2 * LID_CLEAR
SKIRT_IN_Y = OUTER_Y + 2 * LID_CLEAR
SKIRT_IN_R = OUTER_R + LID_CLEAR

assert SNAP_LEN <= FLAT_X - GRIP_NOTCH_W / 2, "bump runs off the flat wall"
assert SNAP_Z - SNAP_R > BOARD_TOP, "bump below the port notch floor"
assert HEIGHT - SKIRT_H < SNAP_Z - SNAP_R - LEAD_IN, "skirt too short to reach past the bump"


def rounded_box(x, y, h, r):
    return cq.Workplane("XY").rect(x, y).extrude(h).edges("|Z").fillet(r)


def rounded_rect_wire(x, y, r, z):
    w = cq.Workplane("XY").rect(x, y).val()
    return w.fillet2D(r, w.Vertices()).translate((0, 0, z))


def x_rod(r, length, y, z, x=0.0):
    """Cylinder along x."""
    return cq.Workplane("YZ").circle(r).extrude(length).translate((x - length / 2, y, z))


def tray(peg_d=PEG_D, grip=GRIP, snap=True, label=True):
    """Floor down, open top. Prints as is, no supports."""
    part = rounded_box(OUTER_X, OUTER_Y, HEIGHT, OUTER_R)
    part = part.cut(rounded_box(INNER_X, INNER_Y, HEIGHT, INNER_R).translate((0, 0, FLOOR)))

    holes = [(sx * HOLE_DX / 2, sy * HOLE_DY / 2) for sx in (-1, 1) for sy in (-1, 1)]
    bosses = cq.Workplane("XY").pushPoints(holes).circle(BOSS_D / 2).extrude(STANDOFF).translate((0, 0, FLOOR))
    peg_h = PCB_T + PEG_ABOVE
    pegs = (cq.Workplane("XY").pushPoints(holes).circle(peg_d / 2).extrude(peg_h)
            .faces(">Z").edges().chamfer(PEG_CHAMFER).translate((0, 0, BOARD_BOT)))
    part = part.union(bosses).union(pegs)

    if snap:
        for sx in (-1, 1):
            for sy in (-1, 1):
                part = part.union(x_rod(SNAP_R, SNAP_LEN, sy * SNAP_AXIS_Y, SNAP_Z, sx * SNAP_X))

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


def lid():
    """In the tray's frame, seated: its ring rests on the wall top. lid_for_print() flips it."""
    skirt_bot = HEIGHT - SKIRT_H
    top = CEILING + LID_T
    out_x, out_y, out_r = SKIRT_IN_X + 2 * SKIRT_T, SKIRT_IN_Y + 2 * SKIRT_T, SKIRT_IN_R + SKIRT_T
    part = rounded_box(out_x, out_y, top - skirt_bot, out_r).translate((0, 0, skirt_bot))
    # the tray's walls, plus clearance, up to the wall top
    part = part.cut(rounded_box(SKIRT_IN_X, SKIRT_IN_Y, HEIGHT - skirt_bot + 1, SKIRT_IN_R).translate((0, 0, skirt_bot - 1)))
    # lead-in: the skirt mouth flares by LEAD_IN
    flare = cq.Solid.makeLoft([
        rounded_rect_wire(SKIRT_IN_X + 2 * LEAD_IN, SKIRT_IN_Y + 2 * LEAD_IN, SKIRT_IN_R + LEAD_IN, skirt_bot - 0.01),
        rounded_rect_wire(SKIRT_IN_X, SKIRT_IN_Y, SKIRT_IN_R, skirt_bot + LEAD_IN)], True)
    part = part.cut(cq.Workplane("XY").add(flare))
    # headroom over the board, inside the walls
    part = part.cut(rounded_box(INNER_X, INNER_Y, CEILING - HEIGHT + 1, INNER_R).translate((0, 0, HEIGHT - 1)))
    # snap grooves along the flat of each long side
    for sy in (-1, 1):
        part = part.cut(x_rod(SNAP_R + GROOVE_EXTRA, 2 * FLAT_X, sy * SNAP_AXIS_Y, SNAP_Z))
    # port openings run on up to the ceiling, through ring and skirt
    w = PORT_NOTCH_W + 2 * LID_CLEAR
    for sx in (-1, 1):
        cut = cq.Workplane("XY").box(out_x, w, CEILING - skirt_bot + 1, centered=(False, True, False))
        part = part.cut(cut.translate((INNER_X / 2 if sx > 0 else -INNER_X / 2 - out_x, 0, skirt_bot - 1)))
    # ribs that keep the board on its pegs
    for x, y, length in RIBS:
        rib = cq.Workplane("XY").box(length, RIB_W, CEILING - BOARD_TOP - RIB_GAP + 0.01, centered=(True, True, False))
        part = part.union(rib.translate((x, y, BOARD_TOP + RIB_GAP)))
    return part


def lid_for_print():
    """Top face down on the plate, skirt up. No supports."""
    top = CEILING + LID_T
    return lid().rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, top))


def export(shape, name):
    cq.exporters.export(shape, f"cad/key/out/{name}.stl")
    bb = shape.val().BoundingBox()
    print(f"{name}.stl  {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm")


if __name__ == "__main__":
    import os
    os.makedirs("cad/key/out", exist_ok=True)
    print("tray outer %.2f x %.2f x %.2f, board underside at z %.2f, top at %.2f; closed case %.2f tall" % (
        OUTER_X, OUTER_Y, HEIGHT, BOARD_BOT, BOARD_TOP, CEILING + LID_T))
    t, l = tray(), lid_for_print()
    export(t, "key_tray_v2")
    export(l, "key_lid_v2")
    export(t.union(l.translate((0, OUTER_Y + 8, 0))), "key_case_v2")
    # closed-case checks: lid and tray must not overlap, and nothing may touch the board
    board = rounded_box(BOARD_X, BOARD_Y, PCB_T, BOARD_R).translate((0, 0, BOARD_BOT))
    board = board.cut(cq.Workplane("XY").pushPoints([(sx * HOLE_DX / 2, sy * HOLE_DY / 2) for sx in (-1, 1) for sy in (-1, 1)])
                      .circle(HOLE_D / 2).extrude(PCB_T).translate((0, 0, BOARD_BOT)))
    for name, a, b in (("tray/lid", tray(), lid()), ("lid/board", lid(), board), ("tray/board", tray(), board)):
        v = a.intersect(b).val().Volume()
        print("overlap %-10s %.4f mm3" % (name, v))
        assert v < 1e-3, name
