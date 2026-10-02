"""2.8-inch console case: Jason's Onshape draft plus mounting posts for the LCD board.

Run: uv run --python 3.11 --with cadquery python cad/console/lcd28/gen.py

The shell comes straight from `dial-and-button.step`, the Onshape export. It is 90 x 120 x 30 mm
and open at the bottom, with 2.5 mm walls and a 2.5 mm face plate. The face plate holds a
68 x 48 screen window, a 12 mm dial hole, a 7 mm button hole and a 30 x 40 chip slot (open for
now). Keep editing the shell in Onshape, export it over the STEP, and run this again.

This script adds four posts under the face plate for the Lonely Binary 2.8-inch LCD board
(ASIN B0GR4HRVV2). It works the same way as the key tray (cad/key/tray.py): a boss the board
rests on, and a chamfered peg through each mounting hole. The case prints face down, so the posts
print standing up, with no supports.

No drawing of that board exists (see LCD-REFERENCE.md). Every name ending in _GUESS is a
placeholder until it is measured with calipers. The posts move when those numbers change.

Frame: the STEP's own. x across the face, y along it (+ toward the screen), z up, with the face
plate's outer surface at z = 30 and its underside at z = 27.5. The screen is landscape. All
dimensions mm.
"""
import os
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
STEP_IN = os.path.join(HERE, "dial-and-button.step")
OUT = os.path.join(HERE, "out")

# --- the shell (read off the STEP; checked below) ---------------------------------------------
PLATE_UNDER_Z = 27.5   # face plate underside
PLATE_TOP_Z = 30.0
INNER_X = 85.0         # inside the walls
INNER_Y = 115.0
WINDOW_C = (0.0, 28.0)  # screen window centre
WINDOW_X = 68.0
WINDOW_Y = 48.0

# --- the LCD board: placeholders until measured (LCD-REFERENCE.md, section 8) -----------------
PCB_X_GUESS = 80.0          # board width, landscape
PCB_Y_GUESS = 54.0          # board height
PCB_T_GUESS = 1.6           # board thickness
HOLE_D_GUESS = 3.0          # mounting hole diameter
HOLE_INSET_GUESS = 3.0      # hole centre to the nearest two edges, assumed the same at all four corners
FRONT_Z_GUESS = 4.0         # glass/frame front surface above the board's front face
LAND_D_GUESS = 5.5          # flat ring around each hole the boss can press on
BOARD_OFFSET_GUESS = (0.0, 0.0)  # board centre minus window centre

# --- design choices ---------------------------------------------------------------------------
GLASS_GAP = 0.3        # the plate never presses on the glass
PEG_CLEAR = 0.1        # peg = hole - this (the key tray's fit check picked 2.40 in a 2.5 hole)
PEG_ABOVE = 0.8        # peg tip past the board's back face
PEG_CHAMFER = 0.4

BOARD_C = (WINDOW_C[0] + BOARD_OFFSET_GUESS[0], WINDOW_C[1] + BOARD_OFFSET_GUESS[1])
HOLES = [(BOARD_C[0] + sx * (PCB_X_GUESS / 2 - HOLE_INSET_GUESS),
          BOARD_C[1] + sy * (PCB_Y_GUESS / 2 - HOLE_INSET_GUESS)) for sx in (-1, 1) for sy in (-1, 1)]
BOARD_FRONT_Z = PLATE_UNDER_Z - FRONT_Z_GUESS - GLASS_GAP   # board front face, facing the plate
BOARD_BACK_Z = BOARD_FRONT_Z - PCB_T_GUESS
PEG_D = HOLE_D_GUESS - PEG_CLEAR


def shell():
    s = cq.importers.importStep(STEP_IN)
    bb = s.val().BoundingBox()
    assert (round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zmax, 2)) == (90.0, 120.0, PLATE_TOP_Z), \
        "the STEP changed size: update the shell numbers at the top of gen.py"
    return s


def posts():
    boss_h = PLATE_UNDER_Z - BOARD_FRONT_Z
    bosses = cq.Workplane("XY").pushPoints(HOLES).circle(LAND_D_GUESS / 2).extrude(boss_h + 0.01).translate((0, 0, BOARD_FRONT_Z))
    peg_h = PCB_T_GUESS + PEG_ABOVE
    pegs = (cq.Workplane("XY").pushPoints(HOLES).circle(PEG_D / 2).extrude(peg_h)
            .faces("<Z").edges().chamfer(PEG_CHAMFER).translate((0, 0, BOARD_FRONT_Z - peg_h)))
    return bosses.union(pegs)


def board():
    """Stand-in for the LCD board, for the checks and the preview."""
    b = cq.Workplane("XY").rect(PCB_X_GUESS, PCB_Y_GUESS).extrude(PCB_T_GUESS).translate((BOARD_C[0], BOARD_C[1], BOARD_BACK_Z))
    return b.cut(cq.Workplane("XY").pushPoints(HOLES).circle(HOLE_D_GUESS / 2).extrude(PCB_T_GUESS).translate((0, 0, BOARD_BACK_Z)))


def check(case, p):
    # the posts hang from solid plate, clear of the screen window
    window = cq.Workplane("XY").rect(WINDOW_X, WINDOW_Y).extrude(PLATE_TOP_Z).translate((WINDOW_C[0], WINDOW_C[1], 0))
    assert p.intersect(window).val().Volume() < 1e-6, "a post lands in the screen window: check the hole guesses"
    # the board fits inside the walls with room to spare
    assert PCB_X_GUESS / 2 + abs(BOARD_C[0]) < INNER_X / 2 - 0.5 and abs(BOARD_C[1]) + PCB_Y_GUESS / 2 < INNER_Y / 2 - 0.5, \
        "the board doesn't fit inside the walls"
    # nothing of the case occupies the board's volume
    v = case.intersect(board()).val().Volume()
    assert v < 1e-3, "the case overlaps the board by %.3f mm3" % v
    # and the posts don't stray outside the walls
    inner = cq.Workplane("XY").rect(INNER_X, INNER_Y).extrude(PLATE_UNDER_Z + 0.02)
    assert abs(p.cut(inner).val().Volume()) < 1e-3, "a post pokes into a wall"


def coupon(case, p):
    """The face plate around the screen, with the posts: a quick print to try the real board on."""
    margin = 4.0
    # clipped to the inside of the walls, and only the plate's own thickness: flat plate and posts
    x0, x1 = max(BOARD_C[0] - PCB_X_GUESS / 2 - margin, -INNER_X / 2), min(BOARD_C[0] + PCB_X_GUESS / 2 + margin, INNER_X / 2)
    y0, y1 = max(BOARD_C[1] - PCB_Y_GUESS / 2 - margin, -INNER_Y / 2), min(BOARD_C[1] + PCB_Y_GUESS / 2 + margin, INNER_Y / 2)
    box = cq.Workplane("XY").box(x1 - x0, y1 - y0, PLATE_TOP_Z - PLATE_UNDER_Z, centered=False).translate((x0, y0, PLATE_UNDER_Z))
    return case.intersect(box).union(p)


def face_down(shape):
    """Flip for printing: face plate on the bed, posts up."""
    return shape.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, PLATE_TOP_Z))


def export(shape, name, ext="stl"):
    cq.exporters.export(shape, os.path.join(OUT, f"{name}.{ext}"))
    bb = shape.val().BoundingBox()
    print(f"{name}.{ext}  {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    p = posts()
    case = shell().union(p)
    check(case, p)
    print("posts at %s; boss %.2f long, board front at z %.2f, peg %.2f across" % (
        ", ".join("(%.1f, %.1f)" % h for h in HOLES), PLATE_UNDER_Z - BOARD_FRONT_Z, BOARD_FRONT_Z, PEG_D))
    export(face_down(case), "console28_v1")
    export(case, "console28_v1", "step")   # in the draft's own frame, for importing back into Onshape
    export(face_down(coupon(case, p)), "console28_v1_coupon")
