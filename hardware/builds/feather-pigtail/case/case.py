"""Case for the Feather pigtail (hardware/builds/feather-pigtail/README.md): a tray that holds an
Adafruit Feather ESP32-S3 Reverse TFT screen up, and a bezel that clicks onto it. A key-c cable comes
in through the tray's side wall, below the board, and a cable tie through the floor holds it.

Run: uv run --python 3.11 --with cadquery python hardware/builds/feather-pigtail/case/case.py

The tray is cad/key/tray.py's, grown to the Feather: the board sits on four bosses, with a peg on
each up through a mounting hole, and the bezel's skirt clicks over four bumps on the long walls. The
bezel's opening leaves the screen and the four front buttons (D0, D1, D2, Reset) bare. Rings under
the bezel stop 0.2 mm above the board around each peg, so it can't lift off them.

The board's numbers are from Adafruit's "Adafruit ESP32-S3 Reverse TFT Feather.brd"
(https://github.com/adafruit/Adafruit-ESP32-S3-Reverse-TFT-Feather-PCB), not calipers. The part
heights are from their usual datasheets, not measured. Board frame: the .brd's, origin at the corner
at the USB end of the 16-pin row, seen from its top layer (the module's side, the back here). Case
frame: board centre at x = y = 0, the board turned over so the screen faces +z, which puts the
16-pin row at +y; z 0 at the tray's underside. All dimensions mm.
"""
import os
import cadquery as cq

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# --- the Feather (from the .brd) ---------------------------------------------------------------
BOARD_X, BOARD_Y = 50.8, 22.86   # 2.0 x 0.9 in
BOARD_R = 2.54
PCB_T = 1.6
# mounting holes: (x, y, drill) in the board frame. 2.5 plated at the USB end, 2.2 plain at the other
HOLES = [(2.54, 2.54, 2.5), (2.54, 20.32, 2.5), (48.26, 1.8415, 2.2), (48.26, 20.955, 2.2)]
# what stands off the back (the .brd's top layer): (name, x0, x1, y0, y1, height)
BACK = [("USB-C", -1.14, 6.49, 6.81, 16.05, 3.3), ("battery JST PH", 5.70, 15.89, 13.30, 22.30, 6.0),
        ("module", 28.37, 48.36, 3.73, 19.13, 2.4), ("STEMMA QT", 21.37, 24.85, 7.73, 15.13, 3.0),
        ("reset (back)", 8.32, 13.27, 3.91, 6.76, 1.9)]
# and off the front, the screen's side: the three buttons, Reset and the 1.14" panel
FRONT = [("D0", 5.15, 10.09, 3.02, 5.87, 1.9), ("D1", 5.15, 10.09, 10.00, 12.86, 1.9),
         ("D2", 5.15, 10.09, 16.99, 19.84, 1.9), ("Reset", 43.03, 45.88, 8.96, 13.90, 1.9),
         ("screen", 11.29, 42.29, 2.50, 20.10, 1.8)]
# the pins the cable's wires go to: 3V, GND on the 16-pin row; SCL, SDA on the 12-pin row
PINS = {"3V": (8.89, 1.27), "GND": (13.97, 1.27), "SCL": (41.91, 21.59), "SDA": (44.45, 21.59)}
PAD_D = 1.8            # a header pad and its fillet, wire trimmed flush
FILLET_H = 0.6         # how far the fillet stands on the front

# --- the cable ---------------------------------------------------------------------------------
CABLE_D = 4.0          # the jacket: measure the cable you cut and change this before printing
CABLE_CLEAR = 0.3      # on the diameter
CABLE_BX = 20.0        # where it comes in, along the 16-pin side, in the board frame: clear of the
                       # back's parts, between the 3V/GND and the SDA/SCL ends
TIE_W, TIE_T = 2.8, 1.6  # each tie slot through the floor: for a tie up to 2.5 mm wide
TIE_IN = 3.5           # slots' centre line, in from the inside of the wall
TIE_GROOVE = 0.8       # under the floor, between the slots, so the tie's band lies below the bottom

# --- tray --------------------------------------------------------------------------------------
CLEAR = 0.5            # board edge to wall
WALL = 1.8
FLOOR = 1.6
STANDOFF = 7.0         # floor top to board underside: the battery socket, the module, the wires
WALL_ABOVE = 1.0       # wall top, and the bezel's underside, above the board top
BOSS_D = {2.5: 4.0, 2.2: 3.4}    # the far end's bosses stay off the module's outline
PEG_D = {2.5: 2.40, 2.2: 2.10}   # 2.40 in 2.5 won cad/key's fit check; 2.10 in 2.2 is the same fit
PEG_ABOVE = 0.8
PEG_CHAMFER = 0.4
USB_W = 13.0           # the end wall's opening for a cable's overmold on the Feather's USB-C
USB_BELOW = 5.1        # how far the opening reaches below the board's underside

# --- snap and bezel (cad/key/tray.py's) --------------------------------------------------------
SNAP_R = 0.5
SNAP_PROUD = 0.35
SNAP_LEN = 6.0
SNAP_BELOW_TOP = 1.4
SNAP_XS = (-15.0, 15.0)  # bump centres along each long wall
GROOVE_EXTRA = 0.05
LID_CLEAR = 0.15
SKIRT_T = 1.2
SKIRT_H = 3.0
LEAD_IN = 0.5
PLATE_T = 1.2          # the bezel's top
OPEN = (4.6, 46.4, 2.3, 20.56)   # its opening, board frame: x0, x1, y0, y1; covers the pin rows' pads
OPEN_R = 1.0
RING_GAP = 0.2         # the rings under the bezel, above the board top
RING_IN = 0.6          # ring bore over the peg, on the diameter

INNER_X, INNER_Y, INNER_R = BOARD_X + 2 * CLEAR, BOARD_Y + 2 * CLEAR, BOARD_R + CLEAR
OUTER_X, OUTER_Y, OUTER_R = INNER_X + 2 * WALL, INNER_Y + 2 * WALL, INNER_R + WALL
BOARD_BOT = FLOOR + STANDOFF
BOARD_TOP = BOARD_BOT + PCB_T
HEIGHT = BOARD_TOP + WALL_ABOVE
SNAP_Z = HEIGHT - SNAP_BELOW_TOP
SNAP_AXIS_Y = OUTER_Y / 2 + SNAP_PROUD - SNAP_R
SKIRT_IN_X, SKIRT_IN_Y, SKIRT_IN_R = OUTER_X + 2 * LID_CLEAR, OUTER_Y + 2 * LID_CLEAR, OUTER_R + LID_CLEAR
TOP = HEIGHT + PLATE_T
CABLE_Z = FLOOR + CABLE_D / 2


def c(x, y):
    """Board frame to case frame: the board turned over about its long axis."""
    return x - BOARD_X / 2, BOARD_Y / 2 - y


def rect(x0, x1, y0, y1):
    """A board-frame rectangle as (case-frame centre, size)."""
    (ax, ay), (bx, by) = c(x0, y0), c(x1, y1)
    return ((ax + bx) / 2, (ay + by) / 2), (abs(bx - ax), abs(by - ay))


CABLE_X = c(CABLE_BX, 0)[0]
TIE_Y = INNER_Y / 2 - TIE_IN

assert STANDOFF >= max(h for *_r, h in BACK) + 0.5, "the board's back parts reach the floor"
assert WALL_ABOVE >= FILLET_H + 0.3, "the bezel sits on the pin rows' solder"
assert CABLE_Z + CABLE_D / 2 < BOARD_BOT - 1.0, "the cable reaches the board"
assert HEIGHT - SKIRT_H < SNAP_Z - SNAP_R - LEAD_IN, "skirt too short to reach past the bump"
assert all(abs(x) + SNAP_LEN / 2 < OUTER_X / 2 - OUTER_R for x in SNAP_XS), "bump runs off the flat wall"
assert abs(CABLE_X) + CABLE_D < OUTER_X / 2 - OUTER_R, "the cable hole is in the corner"


def rounded_box(x, y, h, r):
    return cq.Workplane("XY").rect(x, y).extrude(h).edges("|Z").fillet(r)


def rounded_rect_wire(x, y, r, z):
    w = cq.Workplane("XY").rect(x, y).val()
    return w.fillet2D(r, w.Vertices()).translate((0, 0, z))


def x_rod(r, length, y, z, x=0.0):
    return cq.Workplane("YZ").circle(r).extrude(length).translate((x - length / 2, y, z))


def box(cx, cy, sx, sy, z0, h):
    return cq.Workplane("XY").box(sx, sy, h, centered=(True, True, False)).translate((cx, cy, z0))


def usb_cut(extra=0.0):
    """The opening in the USB end: from above everything down to USB_BELOW under the board."""
    z0 = BOARD_BOT - USB_BELOW
    (_x, y), _s = rect(0, 1, 6.81, 16.05)
    x0, x1 = -OUTER_X / 2 - 6, -INNER_X / 2 + 0.01    # through the whole wall
    return box((x0 + x1) / 2, y, x1 - x0, USB_W + 2 * extra, z0, TOP - z0 + 5)


def tray():
    """Floor down, open top. Prints as is, no supports (the cable hole's top is a short bridge)."""
    part = rounded_box(OUTER_X, OUTER_Y, HEIGHT, OUTER_R)
    part = part.cut(rounded_box(INNER_X, INNER_Y, HEIGHT, INNER_R).translate((0, 0, FLOOR)))
    for bx, by, drill in HOLES:
        x, y = c(bx, by)
        boss = cq.Workplane("XY").circle(BOSS_D[drill] / 2).extrude(STANDOFF).translate((x, y, FLOOR))
        peg = (cq.Workplane("XY").circle(PEG_D[drill] / 2).extrude(PCB_T + PEG_ABOVE)
               .faces(">Z").edges().chamfer(PEG_CHAMFER).translate((x, y, BOARD_BOT)))
        part = part.union(boss).union(peg)
    for x in SNAP_XS:
        for sy in (-1, 1):
            part = part.union(x_rod(SNAP_R, SNAP_LEN, sy * SNAP_AXIS_Y, SNAP_Z, x))
    part = part.cut(usb_cut())
    # the cable's hole through the 16-pin side wall: thread the cut end in from outside, then solder
    hole = cq.Workplane("XZ").circle((CABLE_D + CABLE_CLEAR) / 2).extrude(-WALL * 3).translate((CABLE_X, INNER_Y / 2 - WALL, CABLE_Z))
    part = part.cut(hole)
    # the tie: two slots through the floor beside the cable, a groove between them underneath
    off = CABLE_D / 2 + CABLE_CLEAR + TIE_T / 2 + 0.6
    for sx in (-1, 1):
        part = part.cut(box(CABLE_X + sx * off, TIE_Y, TIE_T, TIE_W, -1, FLOOR + 2))
    part = part.cut(box(CABLE_X, TIE_Y, 2 * off + TIE_T, TIE_W, -1, 1 + TIE_GROOVE))
    # underneath, mirrored so it reads with the tray turned over: the name and the Source Location
    for text, y, size in (("PicoQuorum feather-pigtail", -1.5, 2.6), ("github.com/jmcpheron/pico-quorum", -6.0, 2.2),
                          ("cable %.1f" % CABLE_D, -10.0, 2.2)):
        t = (cq.Workplane("XY").text(text, size, 0.4, kind="bold", halign="center", valign="center")
             .mirror("YZ").translate((0, y, -0.01)))
        part = part.cut(t)
    return part


def bezel():
    """In the tray's frame, seated on the wall top. bezel_for_print() turns it over."""
    skirt_bot = HEIGHT - SKIRT_H
    out_x, out_y, out_r = SKIRT_IN_X + 2 * SKIRT_T, SKIRT_IN_Y + 2 * SKIRT_T, SKIRT_IN_R + SKIRT_T
    part = rounded_box(out_x, out_y, TOP - skirt_bot, out_r).translate((0, 0, skirt_bot))
    part = part.cut(rounded_box(SKIRT_IN_X, SKIRT_IN_Y, HEIGHT - skirt_bot + 1, SKIRT_IN_R).translate((0, 0, skirt_bot - 1)))
    flare = cq.Solid.makeLoft([
        rounded_rect_wire(SKIRT_IN_X + 2 * LEAD_IN, SKIRT_IN_Y + 2 * LEAD_IN, SKIRT_IN_R + LEAD_IN, skirt_bot - 0.01),
        rounded_rect_wire(SKIRT_IN_X, SKIRT_IN_Y, SKIRT_IN_R, skirt_bot + LEAD_IN)], True)
    part = part.cut(cq.Workplane("XY").add(flare))
    for sy in (-1, 1):
        part = part.cut(x_rod(SNAP_R + GROOVE_EXTRA, OUTER_X - 2 * OUTER_R, sy * SNAP_AXIS_Y, SNAP_Z))
    (cx, cy), (sx, sy) = rect(*OPEN)
    part = part.cut(rounded_box(sx, sy, PLATE_T + 2, OPEN_R).translate((cx, cy, HEIGHT - 1)))
    part = part.cut(usb_cut(LID_CLEAR))
    # rings around the pegs, down to just above the board
    for bx, by, drill in HOLES:
        x, y = c(bx, by)
        ring = (cq.Workplane("XY").circle(BOSS_D[drill] / 2).circle((PEG_D[drill] + RING_IN) / 2)
                .extrude(HEIGHT - BOARD_TOP - RING_GAP + 0.01).translate((x, y, BOARD_TOP + RING_GAP)))
        part = part.union(ring)
    return part


def bezel_for_print():
    """Top face down on the plate, skirt up. No supports."""
    return bezel().rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, TOP))


def board():
    """The Feather as solids: the board with its holes, its parts front and back, the wires' pads."""
    b = rounded_box(BOARD_X, BOARD_Y, PCB_T, BOARD_R).translate((0, 0, BOARD_BOT))
    for bx, by, drill in HOLES:
        x, y = c(bx, by)
        b = b.cut(cq.Workplane("XY").circle(drill / 2).extrude(PCB_T).translate((x, y, BOARD_BOT)))
    parts = {}
    for name, x0, x1, y0, y1, h in BACK:
        (x, y), (sx, sy) = rect(x0, x1, y0, y1)
        parts[name] = box(x, y, sx, sy, BOARD_BOT - h, h)
    for name, x0, x1, y0, y1, h in FRONT:
        (x, y), (sx, sy) = rect(x0, x1, y0, y1)
        parts[name] = box(x, y, sx, sy, BOARD_TOP, h)
    for name, (bx, by) in PINS.items():
        x, y = c(bx, by)
        parts[name + " solder"] = cq.Workplane("XY").circle(PAD_D / 2).extrude(FILLET_H).translate((x, y, BOARD_TOP))
    return b, parts


def cable():
    """The jacket from outside the wall to past the tie."""
    length = WALL + 2 + TIE_IN + 3
    return cq.Workplane("XZ").circle(CABLE_D / 2).extrude(-length).translate((CABLE_X, OUTER_Y / 2 + 2 - length, CABLE_Z))


def export(shape, name):
    cq.exporters.export(shape, os.path.join(OUT, name + ".stl"), tolerance=0.05, angularTolerance=0.3)
    bb = shape.val().BoundingBox()
    print(f"{name}.stl  {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm")


def preview(views, path):
    """Each view a list of (shape, colour), drawn from its triangles with flat shading."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgb
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    light = (0.3, -0.5, 0.8)
    fig = plt.figure(figsize=(12, 4.4), dpi=110)
    for i, (title, elev, azim, shapes) in enumerate(views):
        ax = fig.add_subplot(1, len(views), i + 1, projection="3d")
        pts, cols = [], []
        for shape, color in shapes:
            verts, tris = shape.val().tessellate(0.05, 0.3)
            for t in tris:
                p0, p1, p2 = (verts[k] for k in t)
                n = (p1 - p0).cross(p2 - p0)
                ln = n.Length or 1
                k = 0.35 + 0.65 * abs(n.x * light[0] + n.y * light[1] + n.z * light[2]) / ln
                pts.append([(q.x, q.y, q.z) for q in (p0, p1, p2)])
                cols.append(tuple(min(1, ch * k) for ch in to_rgb(color)))
        ax.add_collection3d(Poly3DCollection(pts, facecolors=cols, edgecolor="none"))
        ax.set_xlim(-29, 29), ax.set_ylim(-29, 29), ax.set_zlim(-14, 22)
        ax.set_box_aspect((58, 58, 36))
        ax.view_init(elev, azim)
        ax.set_axis_off()
        ax.set_title(title)
    fig.subplots_adjust(0, 0, 1, 0.92, 0, 0)
    fig.savefig(path)
    print("preview", os.path.relpath(path))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("tray %.2f x %.2f x %.2f, board underside at z %.2f, top at %.2f; closed case %.2f tall; cable %.1f mm" % (
        OUTER_X, OUTER_Y, HEIGHT, BOARD_BOT, BOARD_TOP, TOP, CABLE_D))
    t, bz = tray(), bezel()
    export(t, "pigtail_tray_v1")
    export(bezel_for_print(), "pigtail_bezel_v1")
    export(t.union(bezel_for_print().translate((0, OUTER_Y + 8, 0))), "pigtail_case_v1")
    # the closed case: tray, bezel, board, its parts and the cable must not overlap
    b, parts = board()
    checks = [("tray/bezel", t, bz), ("tray/board", t, b), ("bezel/board", bz, b), ("tray/cable", t, cable()),
              ("board/cable", b, cable())]
    checks += [("tray/" + n, t, p) for n, p in parts.items()] + [("bezel/" + n, bz, p) for n, p in parts.items()]
    checks += [("cable/" + n, cable(), p) for n, p in parts.items()]
    bad = []
    for name, a, s in checks:
        v = a.intersect(s).val().Volume()
        if v >= 1e-3:
            bad.append(name)
            print("overlap %-24s %.4f mm3" % (name, v))
    print("overlap checks: %d, %s" % (len(checks), "all clear" if not bad else "FAILED: " + ", ".join(bad)))
    # the bezel's opening must leave every front part bare from above
    (cx, cy), (sx, sy) = rect(*OPEN)
    for name, x0, x1, y0, y1, _h in FRONT:
        (x, y), (px, py) = rect(x0, x1, y0, y1)
        inside = abs(x - cx) + px / 2 <= sx / 2 and abs(y - cy) + py / 2 <= sy / 2
        print("open   %-8s %s" % (name, "bare" if inside else "COVERED"))
        bad += [] if inside else [name]
    try:
        inside = [(b, "#1f6f43"), (cable(), "#333333")] + [(p, "#c9c9c9") for p in parts.values()]
        preview([("the tray: bosses, cable hole, tie slots", 40, -125, [(t, "#9aa4b1"), (cable(), "#333333")]),
                 ("the Feather in it", 40, -125, [(t, "#9aa4b1")] + inside),
                 ("closed", 40, -125, [(t, "#9aa4b1"), (bz, "#4a5363")] + inside)],
                os.path.join(OUT, "pigtail_case_v1_preview.png"))
    except ImportError:
        print("preview: no matplotlib (add --with matplotlib)")
    assert not bad, bad
