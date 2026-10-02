"""2.8-inch console case: Jason's Onshape draft plus mounting posts for the LCD board.

Run: uv run --python 3.11 --with cadquery python cad/console/lcd28/gen.py

The shell comes straight from `dial-and-button.step`, the Onshape export. It is 90 x 120 x 30 mm
and open at the bottom, with 2.5 mm walls and a 2.5 mm face plate. The face plate holds a
68 x 48 screen window, a 12 mm dial hole, a 7 mm button hole and a 30 x 40 chip slot (open for
now). Keep editing the shell in Onshape, export it over the STEP, and run this again.

This script changes two things:
- It fills the draft's screen window and cuts a smaller one. The 64.3 x 47.5 glass would not
  cover a 68 x 48 window, and the mounting holes sit inside the old window's width.
- It adds four posts under the face plate for the Lonely Binary 2.8-inch LCD board
  (ASIN B0GR4HRVV2). They work like the key tray's (cad/key/tray.py): a boss the board's front
  face rests on, and a chamfered peg in each mounting hole. Each post has a pilot hole, so a
  self-tapping screw from behind can clamp the board; the pegs only locate it.

The case prints face down, so the posts print standing up, with no supports.

Board numbers: Jason's calipers, 2026-10-02. The board has no published drawing; see
LCD-REFERENCE.md. The estimated active image is calculated from the 2.8-inch diagonal, not
measured.

Frame: the STEP's own. x across the face, y along it (+ toward the screen), z up, with the face
plate's outer surface at z = 30 and its underside at z = 27.5. The screen is landscape. All
dimensions mm.
"""
import os
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
STEP_IN = os.path.join(HERE, "dial-and-button.step")
OUT = os.path.join(HERE, "out")
VERSION = "v2"

# --- the shell (read off the STEP; checked below) ---------------------------------------------
PLATE_UNDER_Z = 27.5   # face plate underside
PLATE_TOP_Z = 30.0
INNER_X = 85.0         # inside the walls
INNER_Y = 115.0
SCREEN_C = (0.0, 28.0)  # the draft's screen window centre; the board and the new window centre here
DRAFT_WINDOW = (68.0, 48.0)

# --- the LCD board (calipers, 2026-10-02) -----------------------------------------------------
PCB_X = 80.0           # landscape
PCB_Y = 48.6
PCB_T = 1.6            # the bare board
HOLE_D = 4.5           # if that was the gold ring, not the drilled hole, the pegs are too big
HOLE_INSET = 4.0       # hole centre to the two nearest edges ("maybe 4"); assumed at all four corners
STACK_T = 3.8          # board back face to glass front
GLASS_X = 64.3
GLASS_Y = 47.5
GLASS_OFFSET = (0.0, 0.0)   # glass centre minus board centre ("looks about centred")
GLASS_Z = STACK_T - PCB_T   # 2.2: glass front above the board's front face

# --- estimated, not measured (LCD-REFERENCE.md, section 1) -------------------------------------
ACTIVE_EST = (56.9, 42.7)   # active image, landscape, from the diagonal; assumed centred on the glass

# --- design choices ---------------------------------------------------------------------------
WINDOW = (60.0, 45.0)  # covers the estimated image with 1.5 / 1.15 mm to spare; hides the glass edge
WINDOW_R = 1.0         # corner radius, as in the draft
GLASS_GAP = 0.3        # the plate never presses on the glass
BOSS_D = 7.0           # land on the board's front face around each hole
BOSS_GLASS_GAP = 0.3   # boss edge to glass edge, at least
PEG_CLEAR = 0.1        # peg = hole - this (the key tray's fit check picked 2.40 in a 2.5 hole)
PEG_SHORT = 0.3        # peg tip stops this far inside the board, so a screw head clamps the board
PEG_CHAMFER = 0.4
PILOT_D = 2.5          # for an M3 self-tapping screw; 0 for solid pegs
PLATE_KEEP = 1.0       # the pilot hole stops this far short of the face

BOARD_C = SCREEN_C
GLASS_C = (BOARD_C[0] + GLASS_OFFSET[0], BOARD_C[1] + GLASS_OFFSET[1])
HOLES = [(BOARD_C[0] + sx * (PCB_X / 2 - HOLE_INSET), BOARD_C[1] + sy * (PCB_Y / 2 - HOLE_INSET))
         for sx in (-1, 1) for sy in (-1, 1)]
BOARD_FRONT_Z = PLATE_UNDER_Z - GLASS_Z - GLASS_GAP   # board front face, facing the plate
BOARD_BACK_Z = BOARD_FRONT_Z - PCB_T
PEG_D = HOLE_D - PEG_CLEAR
PEG_H = PCB_T - PEG_SHORT


def rect_prism(c, size, z0, h, r=0.0):
    w = cq.Workplane("XY").rect(*size).extrude(h)
    if r:
        w = w.edges("|Z").fillet(r)
    return w.translate((c[0], c[1], z0))


def shell():
    s = cq.importers.importStep(STEP_IN)
    bb = s.val().BoundingBox()
    assert (round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zmax, 2)) == (90.0, 120.0, PLATE_TOP_Z), \
        "the STEP changed size: update the shell numbers at the top of gen.py"
    plate_t = PLATE_TOP_Z - PLATE_UNDER_Z
    s = s.union(rect_prism(SCREEN_C, DRAFT_WINDOW, PLATE_UNDER_Z, plate_t))      # fill the draft window
    return s.cut(rect_prism(SCREEN_C, WINDOW, PLATE_UNDER_Z - 1, plate_t + 2, WINDOW_R))


def posts():
    boss_h = PLATE_UNDER_Z - BOARD_FRONT_Z
    bosses = cq.Workplane("XY").pushPoints(HOLES).circle(BOSS_D / 2).extrude(boss_h + 0.01).translate((0, 0, BOARD_FRONT_Z))
    pegs = (cq.Workplane("XY").pushPoints(HOLES).circle(PEG_D / 2).extrude(PEG_H)
            .faces("<Z").edges().chamfer(PEG_CHAMFER).translate((0, 0, BOARD_FRONT_Z - PEG_H)))
    return bosses.union(pegs)


def pilots():
    top = PLATE_TOP_Z - PLATE_KEEP
    low = BOARD_FRONT_Z - PEG_H - 0.01
    return cq.Workplane("XY").pushPoints(HOLES).circle(PILOT_D / 2).extrude(top - low).translate((0, 0, low))


def board():
    """Stand-in for the LCD: the board with its holes, and the glass on its front face."""
    b = rect_prism(BOARD_C, (PCB_X, PCB_Y), BOARD_BACK_Z, PCB_T)
    b = b.cut(cq.Workplane("XY").pushPoints(HOLES).circle(HOLE_D / 2).extrude(PCB_T).translate((0, 0, BOARD_BACK_Z)))
    return b.union(rect_prism(GLASS_C, (GLASS_X, GLASS_Y), BOARD_FRONT_Z, GLASS_Z))


def check(case, p):
    plate_t = PLATE_TOP_Z - PLATE_UNDER_Z
    # the window shows the whole estimated image and stays inside the glass
    assert all(w >= a for w, a in zip(WINDOW, ACTIVE_EST)), "the window crops the estimated image"
    assert all(w <= g - 1.0 for w, g in zip(WINDOW, (GLASS_X, GLASS_Y))), "the window shows the glass edge"
    # the posts hang from solid plate, clear of the window, and stay off the glass
    assert p.intersect(rect_prism(SCREEN_C, WINDOW, PLATE_UNDER_Z, plate_t)).val().Volume() < 1e-6, \
        "a post lands in the screen window"
    for hx, hy in HOLES:
        gx = abs(hx - GLASS_C[0]) - GLASS_X / 2
        gy = abs(hy - GLASS_C[1]) - GLASS_Y / 2
        assert max(gx, gy) >= BOSS_D / 2 + BOSS_GLASS_GAP, "a boss would press on the glass at (%.1f, %.1f)" % (hx, hy)
    # the bosses stay on the board
    assert BOSS_D / 2 <= HOLE_INSET, "a boss hangs off the board edge"
    # the board fits inside the walls with room to spare
    assert PCB_X / 2 + abs(BOARD_C[0]) < INNER_X / 2 - 0.5 and abs(BOARD_C[1]) + PCB_Y / 2 < INNER_Y / 2 - 0.5, \
        "the board doesn't fit inside the walls"
    # nothing of the case occupies the board or the glass
    v = case.intersect(board()).val().Volume()
    assert v < 1e-3, "the case overlaps the LCD by %.3f mm3" % v
    # and the posts don't stray outside the walls
    assert abs(p.cut(rect_prism((0, 0), (INNER_X, INNER_Y), 0, PLATE_UNDER_Z + 0.02)).val().Volume()) < 1e-3, \
        "a post pokes into a wall"


def coupon(case):
    """The face plate around the screen, with the posts: a quick print to try the real board on."""
    margin = 4.0
    # clipped to the inside of the walls, and only the plate's own thickness, plus the posts
    x0, x1 = max(BOARD_C[0] - PCB_X / 2 - margin, -INNER_X / 2), min(BOARD_C[0] + PCB_X / 2 + margin, INNER_X / 2)
    y0, y1 = max(BOARD_C[1] - PCB_Y / 2 - margin, -INNER_Y / 2), min(BOARD_C[1] + PCB_Y / 2 + margin, INNER_Y / 2)
    keep = cq.Workplane("XY").box(x1 - x0, y1 - y0, PLATE_TOP_Z - PLATE_UNDER_Z, centered=False).translate((x0, y0, PLATE_UNDER_Z))
    keep = keep.union(cq.Workplane("XY").pushPoints(HOLES).circle(BOSS_D / 2 + 0.01).extrude(PLATE_UNDER_Z - BOARD_BACK_Z)
                      .translate((0, 0, BOARD_BACK_Z)))
    return case.intersect(keep)


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
    if PILOT_D:
        case = case.cut(pilots())
    check(case, p)
    print("window %.1f x %.1f; posts at %s; boss %.2f long, board front at z %.2f; peg %.2f across, %.2f long" % (
        WINDOW + (", ".join("(%.1f, %.1f)" % h for h in HOLES), PLATE_UNDER_Z - BOARD_FRONT_Z, BOARD_FRONT_Z, PEG_D, PEG_H)))
    name = "console28_" + VERSION
    export(face_down(case), name)
    export(case, name, "step")   # in the draft's own frame, for importing back into Onshape
    export(face_down(coupon(case)), name + "_coupon")
