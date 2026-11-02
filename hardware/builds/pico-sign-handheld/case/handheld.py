"""pico-sign-handheld's case: flat, portrait, held in two hands or laid on the desk. A tub, printed in
one piece on its back, open at the face, and a front plate that holds everything you touch or read:
the 2.4" screen across the top half; under it the knob on the left and the sign button on the right,
each sunk in a well, with a frame for a label. The sign button is a printed cap whose plunger presses a
tactile switch: a 12 x 12 mm one in a mini breadboard on the tub's floor, or a 6 x 6 mm one in a printed
holder behind the plate (SIGN_MOUNT). Its well holds a guard: a flip cover on a filament pin, flush with
the face when shut. The plate fixes with four M3 socket head screws, in counterbores, into heat-set inserts in
posts at the tub's corners. The key's USB-C plug stands in a holder at the top edge, built up from the
back, its face flush with the edge: the key, in its clamshell (cartridge.py), plugs straight down onto it
and stands up out of the top. The screen mount and the carrier are the prism's (pico-sign's prism.py):
posts and pins on the plate's back, spacers, a carrier screwed to four bosses, the Pico screwed to the
carrier's back, its USB out through the right side. Everything you wire is on the plate but the key's plug.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign-handheld/case/handheld.py [screen.png]
(or tools/case build handheld)

Writes out/: handheld_body.stl (on its back, as it prints), handheld_plate.stl (face down),
handheld_carrier.stl, handheld_spacers.stl, handheld_plug_lock.stl, handheld_guard_base.stl,
handheld_guard_cover.stl, handheld_sign_cap.stl, handheld_tact_holder.stl (with SIGN_MOUNT = "holder"), handheld_assembly.step, handheld_*.png (the screen PNG warped onto the panel
if one is given), and the clamshell's cartridge_*.stl and cartridge.png.

A first draft to print and try. The 2.4" screen's numbers are placeholders (SCREEN_*): measure yours.
The tactile switch (TACT) and the breadboard's height (BREADBOARD) are not measured: the cap's plunger follows them. The knob, the plugs and the Pico are the prism's numbers. The script checks only that the
parts' stand-ins don't overlap the tub, the plate or each other. All dimensions mm.

Frame: the handheld face up on the desk. x across, left to right; y from the bottom edge (your thumbs)
up to the top edge (the key); z up from the desk, the face at z = T.
"""
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "pico-sign", "case"))
import concepts as K        # the pictures
import cartridge as C       # the key's clamshell

OUT = os.path.join(HERE, "out")

# --- the outline: a rounded oblong, seen from the front --------------------------------------------
W, H, T = 86.0, 118.0, 30.0         # across, bottom to top, thick
R, R_BR = 6.0, 20.0                 # the corners; the bottom right one rounder, under the sign switch
WALL, PLATE = 2.4, 3.0
BACK_R, FRONT_C = 3.0, 1.5          # the back's edge rounded, the face's edge chamfered
FOOT = (6.0, 35.0)                  # the rubber feet: strips with round ends (calipers), bottom to top
FOOT_CLEAR, FOOT_DEPTH = 0.3, 1.0
FOOT_X, FOOT_END = 15.0, 8.0        # their centres in from the sides; their ends in from the bottom and top
ZP = T - PLATE                      # the plate's back: the tub's rim

# --- the plate's parts (x, y) ----------------------------------------------------------------------
# The 2.4" 240x320 SPI module (ST7789, or ILI9341: README), 8 pins. Placeholders, the earlier wedge's
# guesses (pico-sign/case/case.py), but the active area, which is the panel's datasheet. Measure yours.
SCREEN_PCB = (72.0, 44.0)           # the board, the 8-pin header at one end (HEADER_SIDE), its pins out of the back
SCREEN_PCB_T = 1.6
SCREEN_HOLES = (66.0, 38.0)         # its four holes' centres: placeholder, 3 mm in from each corner
SCREEN_HOLE = 3.2                   # their diameter: placeholder
SCREEN_GLASS = (60.3, 42.7, 3.5)    # the panel: outline and thickness from the board's front to the glass's, placeholders
SCREEN_ACTIVE = (48.96, 36.72)      # the active area, landscape: a 2.4" 240x320's, 0.153 mm pixels
# The header on the left (-1), away from the controls; build1 draws the 2.8" the right way up that way
# (MADCTL 0x60). The 2.4" isn't seen working yet (README).
HEADER_SIDE = -1
SCREEN_DX = 0.0                     # the glass this far right of the board's centre: measure
SCREEN_XY = (W / 2, 79.0)           # the board's centre
HEADER_X = SCREEN_XY[0] + HEADER_SIDE * (SCREEN_PCB[0] / 2 - 1.5)
HEADER = (3.0, 21.0, 11.5)          # its 8 pins out of the back, with wires soldered to them: wide, tall, deep
KNOB_XY, SIGN_XY = (22.0, 30.0), (64.0, 30.0)    # under the screen: the knob left, the sign button right
KNOB_HOLE = 7.2                     # EC11, M7 bushing
EC11 = (12.0, 12.0, 7.0)            # its body behind the plate
# Both sit in wells in the plate, the plate thickened behind each so the well's floor stays thick.
KNOB_WELL, KNOB_FLOOR = (25.0, 3.0), 2.0        # round: across, deep; the floor under it, for the EC11's nut
# The sign button: a printed cap in the well, its plunger down through the floor onto a tactile switch. A flange
# under the cap seats in a cone under the guard's base, so the cap can't fall out; pressed, it travels TRAVEL,
# then the flange stops on the floor. The switch is held one of two ways (SIGN_MOUNT):
#   "breadboard": a 12 x 12 mm switch in a mini breadboard stuck to the tub's floor, between four corner stops
#                 that put the switch's column under the button. The cap's plunger reaches down to it.
#   "holder":     a 6 x 6 mm switch in a printed holder screwed behind the plate, two bosses for it.
SIGN_MOUNT = "breadboard"
if SIGN_MOUNT == "breadboard":
    TACT = (12.0, 12.0, 3.6, 7.3, 12.5)     # body across, along, tall; tall to its stem's top, from the board's top;
    TACT_TRAVEL = 0.3                       # across its legs. A usual 12 x 12 x 7.3: not measured
else:
    TACT = (6.0, 6.0, 3.5, 5.0, 9.0)        # a usual 6 x 6 mm one, SMD or through-hole with its legs bent flat.
    TACT_TRAVEL = 0.25                      # Not measured
# The mini breadboard (calipers: 46 x 34.2; its height with its tape not measured), long across the case, its
# channel along it, the switch across the channel. 17 holes along it at 2.54 mm, so the first is 2.68 mm in
# from each end. The switch's centre goes on column BB_COL from its right-hand end, its legs in the columns
# either side; the corner stops put that column under the button.
BREADBOARD = (46.0, 34.2, 8.5)
BB_END, BB_PITCH, BB_COL = 2.68, 2.54, 3
BB_X1 = SIGN_XY[0] + BB_END + (BB_COL - 1) * BB_PITCH       # its right-hand end
BB_CLEAR, BB_STOP = 0.3, (6.0, 1.2, 1.5)    # round it in its stops; each stop's arms: long, thick, tall
CAP_D, CAP_UP = 12.0, 2.0           # the cap's head: across, how far it stands over the guard's base
FLANGE_D, FLANGE_T = 15.0, 0.5      # its flange: across, and its flat edge, under a 45 degree cone up to the head
PLUNGER_D = 5.0
STEM_GAP = 0.2                      # the plunger over the switch's stem at rest
TRAVEL = STEM_GAP + TACT_TRAVEL + 0.05      # the cap's travel to the stop: to the stem, then the switch's travel
HOLDER = (24.0, 9.0, 1.2)           # the switch's holder: across, along, its floor under the switch
HOLDER_BOSS = 4.0                   # the bosses it screws to, down from the floor's back
M2_HOLE, M2_CLEAR, M2_SCREW, M2_HEAD = 1.8, 2.4, 8.0, (3.8, 2.0)   # self-tapping M2 x 8 socket heads
# The well holds a guard: a base (two M2 screws through it into the plate), two knuckles on it, and a cover
# hinged between them on a 1.75 mm filament pin. Shut, the cover is flush with the face; it flips up toward
# the screen. The well is the base's outline, so the base can't turn.
GUARD = (20.0, 24.0, 3.0)           # the base: across, tall, its corners' radius
GUARD_DY = -10.0                    # its bottom edge from the button's centre: the hinge is at the top
BASE_T, COVER_T = 3.0, 1.6
HEAD_CLEAR = 0.4                    # over the cap's head and the screws' heads, under the cover
BASE_SCREWS = [(SIGN_XY[0] + sx * 7.5, SIGN_XY[1] - 7.5) for sx in (-1, 1)]
HOLDER_SCREWS = [(SIGN_XY[0] + sx * 9.5, SIGN_XY[1]) for sx in (-1, 1)]
KNUCKLE_R, KNUCKLE_W = 1.8, 4.0     # the hinge's knuckles: radius; the base's two, each this wide
PIN_D, PIN_HOLE_BASE, PIN_HOLE_COVER = 1.75, 1.8, 2.0   # filament; tight in the base, free in the cover
GUARD_CLEAR = 0.3                   # round the base in its well, round the cover's sides
SIGN_WELL = COVER_T + HEAD_CLEAR + CAP_UP + BASE_T    # 7.0
SIGN_FLOOR = 1.5
Z_FLOOR_TOP = T - SIGN_WELL         # the sign well's floor, and its back
Z_FLOOR_BOT = Z_FLOOR_TOP - SIGN_FLOOR
Z_BASE_TOP = Z_FLOOR_TOP + BASE_T
Z_HOLDER = Z_FLOOR_BOT - HOLDER_BOSS  # the holder's top, against its bosses
if SIGN_MOUNT == "breadboard":
    Z_TACT = WALL + BREADBOARD[2]       # the switch's underside, on the breadboard
    Z_TIP = Z_TACT + TACT[3] + STEM_GAP  # the plunger's tip, at rest
    assert Z_TIP < Z_FLOOR_BOT - 0.5, "the switch stands too tall for the space under the button: TACT, BREADBOARD"
else:
    Z_TIP = Z_FLOOR_BOT - 1.0
    Z_TACT = Z_TIP - STEM_GAP - TACT[3]
    assert Z_TACT < Z_HOLDER, "the switch is too short for its holder: TACT"
assert M2_HEAD[1] <= CAP_UP, "the base's screw heads stand higher than the cap: they'd hit the cover"
WELL_RIB = 3.0                      # the thickening behind a well, this much past it
# Colours by layer change. The plate prints face down, so its face is its first layers, and whatever is cut into
# the face shows the colour printing at the depth of its floor. Four filaments, changed at these depths from
# the face: the face itself in the first; the name and the labels' frames, cut to the first depth, in the
# second; the labels' words in the third; the deepest stripe in the fourth. The wells' chamfers, the window's
# bevel and the plate's edge show them as rings.
COLOURS = [("light grey", (0.86, 0.86, 0.84)), ("charcoal", (0.22, 0.22, 0.25)), ("red", (0.78, 0.16, 0.14)),
           ("blue", (0.20, 0.36, 0.72))]
LAYER_CHANGES = (0.6, 1.2, 1.8)     # mm from the face: three layers each, at 0.2 mm layers
NAME = "PICOQUORUM"                 # between the controls and the screen, as big as fits
CUT = LAYER_CHANGES[0]              # the name and the frames' lines: the second colour
LABEL_LINE, LABEL_DEPTH = 0.6, LAYER_CHANGES[1]     # the frames' line; their words: the third colour
LABELS = [(KNOB_XY[0], 12.0, (23.0, 7.0), "TURN"), (SIGN_XY[0] - 3.0, 12.0, (23.0, 7.0), "SIGN")]   # bold: thin strokes won't print
# three stripes over the screen, each cut to one of the depths: the three colours under the face, side by side
STRIPES = dict(x0=14.0, x1=W - 15.6, y=108.6, h=1.6, gap=1.0)
KNOB_CHAMFER, SIGN_CHAMFER = LAYER_CHANGES[1], LAYER_CHANGES[2]   # round the wells' tops, 45 degrees: rings of colour
M3_INSERT = (4.2, 6.0)              # M3*6*5, as the prism: the hole, the insert's length
SCREW_D = 3.4                       # M3 clearance
# The plate's four screws are M3 x 8 socket heads (5.5 across, 3 tall), sunk in counterbores. The plate is
# thickened PLATE_BOSS under each, and the tub's corner posts are that much shorter, so 1.8 mm stays under
# the head and the screw goes 6.2 mm into its insert.
CBORE = (6.0, 3.2)                  # across, deep: the head 0.2 under the face
PLATE_BOSS = 2.0
UNDER_HEAD = PLATE + PLATE_BOSS - CBORE[1]
assert UNDER_HEAD >= 1.5, "too little plate under the plate screws' heads"
assert 8.0 - UNDER_HEAD <= M3_INSERT[1] + 1 - 0.3, "the plate's M3 x 8 screws bottom out in their posts"
POST_D = 8.0                        # the tub's corner posts, for the plate's screws


def br_screw():
    """The bottom right screw, on the round corner's diagonal, its post into the wall."""
    d = R_BR - WALL - POST_D / 2 + 0.5
    return (W - R_BR + d * math.cos(math.radians(45)), R_BR - d * math.sin(math.radians(45)))


SCREWS = [(7.0, 7.0), br_screw(), (7.0, H - 7.0), (W - 7.0, H - 7.0)]

# --- behind the screen: the prism's posts and pins, spacers and carrier ---------------------------------
GLASS_GAP = 0.2                     # the glass this far behind the plate: the posts carry the board, not the glass
SEAT_D = 6.0                        # the posts' tops, round the board's holes; cut flat where the glass is
GLASS_CLEAR = 0.3
PIN_D, PIN_HOLE = SCREEN_HOLE - 0.4, SCREEN_HOLE
SPACER, SPACER_D = 4.0, 6.0         # room for the parts on the board's back
CARRIER_MARGIN, CARRIER_T, CARRIER_R = 1.0, 2.5, 2.0
BOSS_D = 9.0
CARRIER_SCREWS = [(sx * 26.0, sy * (SCREEN_PCB[1] / 2 + BOSS_D / 2 + 2.25)) for sx in (-1, 1) for sy in (-1, 1)]
EAR_W = 10.0
HEADER_NOTCH = (9.0, 26.0)
Z_BOARD = ZP - GLASS_GAP - SCREEN_GLASS[2]                  # the screen board's front: the posts' tops
Z_CARRIER = Z_BOARD - SCREEN_PCB_T - SPACER                 # the carrier's front: the bosses' tops
Z_CARRIER_BACK = Z_CARRIER - CARRIER_T
assert ZP - Z_CARRIER >= M3_INSERT[1] + 1.5, "the bosses are too short for their inserts"

# --- the Pico on the carrier's back, as on the prism, its USB out through the right side --------------------
# Its parts and its USB socket face the carrier (with headers, the usual way; here, wires on its pads, the
# same way up). It lies across, behind the screen, under the key's plug holder, its USB end to the right.
PICO = (51.0, 21.0, 1.0)            # long, across, thick
PICO_X1, PICO_Y = 72.0, 72.0        # its USB end; its centre line
PICO_UP = 6.5                       # its posts on the carrier's back, the prism's: the plug clears the carrier
PICO_POST_D, PICO_POST_D_USB = 4.5, 3.6         # the prism's: slimmer at the USB end, clear of the plug and socket
PICO_SCREW_HOLE, PICO_SCREW = 1.8, 8.0          # M2 x 8, cutting its own thread
PICO_HOLES = [(2.0, -5.7), (2.0, 5.7), (49.0, -5.7), (49.0, 5.7)]   # in from its USB end, across
PICO_POSTS = [(dx, dy, PICO_POST_D_USB if dx < PICO[0] / 2 else PICO_POST_D) for dx, dy in PICO_HOLES]
PICO_PARTS = 3.0                    # its parts, toward the carrier
PICO_WIRES = 4.0                    # wires soldered to its pads, on the side away from the carrier
USB_PLUG = (24.0, 11.0, 8.0, 1.5)   # micro-USB: the overmold's length out of the case, width, thickness, axis off the face
USB_SOCKET = (7.5, 5.6, 2.6)        # on the board's face, between the USB end's posts: wide, in from its end, tall. Not measured
CABLE = 14.0                        # the square hole in the right side, round the plug
Z_PICO = Z_CARRIER_BACK - PICO_UP   # the Pico's face, toward the carrier
PLUG_Z = Z_PICO + USB_PLUG[3]       # the plug's axis
assert CARRIER_T + PICO_UP >= PICO_SCREW - PICO[2] + 0.5, "the Pico's posts are too short for their screws"

# --- the key's plug in the top edge: the prism's holder and lock, laid on the floor ------------------------
PLUG_W, PLUG_H, PLUG_L = 12.4, 5.5, 17.1        # a cut USB-C cable's overmold (calipers)
SHELL_W, SHELL_H, SHELL_L = 8.25, 2.4, 6.5
PLUG_CLEAR = 0.2
HOLDER_WALL, STOP, CABLE_SLOT = 1.6, 2.0, 5.0
LIFT = SHELL_L + WALL + 0.5         # the plug goes in this far down, its shell inside the top wall, then up into the hole
LOCK_CLEAR, LOCK_TAB = 0.15, 2.5    # the lock: its clearance, the lip out of its face to pull it by
DETENT = (0.8, 0.3)
KEY_X = W / 2
PW, PH = PLUG_W / 2 + PLUG_CLEAR, PLUG_H / 2 + PLUG_CLEAR
KEY_Z = WALL + HOLDER_WALL + PH     # the plug's axis: the holder stands on the floor
HOLDER_TOP = KEY_Z + PH + HOLDER_WALL
Y_STOP = H - PLUG_L - LIFT          # the stop's top: the lock fills from here to the plug


def zp(z):
    return cq.Workplane(cq.Plane(origin=(0, 0, z), xDir=(1, 0, 0), normal=(0, 0, 1)))


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def oblong(inset, z0, z1):
    """The outline, or (inset > 0) the same that much smaller all round, from z0 to z1."""
    b = box(inset, W - inset, inset, H - inset, z0, z1)
    b = b.edges("|Z and >X and <Y").fillet(R_BR - inset)
    return b.edges("|Z").fillet(R - inset)


def slab(z0, z1):
    return box(-50, W + 50, -50, H + 50, z0, z1)


def tub_and_plate():
    full = oblong(0, 0, T).faces("<Z").edges().fillet(BACK_R).faces(">Z").edges().chamfer(FRONT_C)
    plate = full.intersect(slab(ZP, T + 1))
    body = full.intersect(slab(-1, ZP)).cut(oblong(WALL, WALL, T + 1))

    # the corner posts, an insert in each; the plate's bosses over them, its screws' counterbores
    inner = oblong(WALL + 0.3, 0, T)          # the plate's bosses stay 0.3 off the tub's walls
    for x, y in SCREWS:
        zt = ZP - PLATE_BOSS                    # the post's top
        body = body.union(zp(WALL - 0.1).center(x, y).circle(POST_D / 2).extrude(zt - WALL + 0.1).intersect(full))
        body = body.cut(zp(zt + 0.01).center(x, y).circle(M3_INSERT[0] / 2).extrude(-M3_INSERT[1] - 1))
        plate = plate.union(zp(ZP + 0.01).center(x, y).circle(POST_D / 2).extrude(-PLATE_BOSS - 0.01).intersect(inner))
        plate = plate.cut(zp(T + 1).center(x, y).circle(SCREW_D / 2).extrude(-(PLATE + PLATE_BOSS + 2)))
        plate = plate.cut(zp(T + 0.01).center(x, y).circle(CBORE[0] / 2).extrude(-CBORE[1] - 0.01))

    # the screen's window, its posts and pins, the carrier's bosses
    sx, sy = SCREEN_XY
    gx = sx + SCREEN_DX
    aw, ah = SCREEN_ACTIVE
    plate = plate.cut(zp(T).center(gx, sy).rect(aw + 6, ah + 6).workplane(offset=-2).rect(aw + 2, ah + 2).loft())
    plate = plate.cut(zp(T + 1).center(gx, sy).rect(aw + 2, ah + 2).extrude(-(PLATE + 2)))
    tip = Z_CARRIER_BACK + 0.3
    for c in screen_holes():
        plate = plate.union(zp(ZP).center(*c).circle(SEAT_D / 2).extrude(Z_BOARD - ZP))
        plate = plate.union(zp(Z_BOARD).center(*c).circle(PIN_D / 2).extrude(tip + 0.5 - Z_BOARD))
        plate = plate.union(zp(tip + 0.5).center(*c).circle(PIN_D / 2).workplane(offset=-0.5).circle(PIN_D / 2 - 0.4).loft())
    gw, gh, _ = SCREEN_GLASS
    plate = plate.cut(zp(ZP - 0.01).center(gx, sy).rect(gw + 2 * GLASS_CLEAR, gh + 2 * GLASS_CLEAR)
                      .extrude(Z_BOARD - ZP + 0.01))
    for c in carrier_screws():
        plate = plate.union(zp(ZP).center(*c).circle(BOSS_D / 2).extrude(Z_CARRIER - ZP))
        plate = plate.cut(zp(Z_CARRIER - 0.01).center(*c).circle(M3_INSERT[0] / 2).extrude(M3_INSERT[1] + 0.5))

    # the controls
    # the controls' wells, the plate thickened behind each; the holes through their floors
    kd, kdepth = KNOB_WELL
    plate = plate.union(zp(ZP).center(*KNOB_XY).circle(kd / 2 + WELL_RIB).extrude(-(kdepth + KNOB_FLOOR - PLATE)))
    plate = plate.cut(zp(T + 1).center(*KNOB_XY).circle(kd / 2).extrude(-(kdepth + 1)))
    kc = KNOB_CHAMFER
    plate = plate.cut(zp(T + 0.01).center(*KNOB_XY).circle(kd / 2 + kc + 0.01).workplane(offset=-(kc + 0.01))
                      .circle(kd / 2).loft())
    plate = plate.union(guard_outline(WELL_RIB, ZP, ZP - (SIGN_WELL + SIGN_FLOOR - PLATE)))
    plate = plate.cut(guard_outline(GUARD_CLEAR, T - SIGN_WELL, T + 1))
    sc = SIGN_CHAMFER
    rim = lambda grow, z: guard_outline(grow, z - 0.01, z).faces(">Z").val().outerWire()
    plate = plate.cut(cq.Workplane().add(cq.Solid.makeLoft([rim(GUARD_CLEAR + sc + 0.01, T + 0.01), rim(GUARD_CLEAR, T - sc)], True)))
    gx0, gx1, gy0, gy1 = guard_box()
    plate = plate.cut(zp(T + 1).center(SIGN_XY[0], gy0).circle(5.0).extrude(-3.5))     # under the cover's edge, to lift it
    for xy, d, deep in ((SIGN_XY, PLUNGER_D + 0.6, SIGN_WELL + SIGN_FLOOR), (KNOB_XY, KNOB_HOLE, kdepth + KNOB_FLOOR)):
        plate = plate.cut(zp(T + 1).center(*xy).circle(d / 2).extrude(-(deep + 2)))
    # bosses behind the sign well's floor: two for the guard's base (screws from the front), two for the
    # switch's holder (screws from behind); a hole each for an M2 to cut its thread
    for x, y in BASE_SCREWS + (HOLDER_SCREWS if SIGN_MOUNT == "holder" else []):
        plate = plate.union(zp(Z_FLOOR_BOT + 0.01).center(x, y).circle(2.5).extrude(-HOLDER_BOSS - 0.01))
    for x, y in BASE_SCREWS:            # from the base's top, an M2 x 8's length, 0.5 short of the boss's end
        plate = plate.cut(zp(Z_FLOOR_TOP + 0.01).center(x, y).circle(M2_HOLE / 2).extrude(-(M2_SCREW - BASE_T + 0.01)))
    for x, y in (HOLDER_SCREWS if SIGN_MOUNT == "holder" else []):     # from the holder's side, stopping 0.5 under the well's floor
        plate = plate.cut(zp(Z_HOLDER - 0.01).center(x, y).circle(M2_HOLE / 2).extrude(Z_FLOOR_TOP - 0.5 - Z_HOLDER))

    # the name, between the controls' tops and the window's bevel, clear of the edge's chamfer
    y0 = max(KNOB_XY[1] + kd / 2 + KNOB_CHAMFER, gy1 + GUARD_CLEAR + SIGN_CHAMFER) + 1.5   # over the wells' chamfers
    y1 = sy - (ah + 6) / 2 - 1.5
    half = min(gx, W - gx) - FRONT_C - 9.0
    probe = cq.Workplane("XY").text(NAME, 10, 1, combine=False).val().BoundingBox()
    size = 10 * min(2 * half / probe.xlen, (y1 - y0) / probe.ylen)
    print("the name: %.1f mm letters, %.0f mm long" % (probe.ylen * size / 10, probe.xlen * size / 10))
    plate = plate.cut(zp(T).center(gx, (y0 + y1) / 2).text(NAME, size, -CUT, combine=False, halign="center", valign="center"))
    for x, y, (lw, lh), words in LABELS:
        frame = zp(T).center(x, y).rect(lw, lh).extrude(-CUT).cut(
            zp(T).center(x, y).rect(lw - 2 * LABEL_LINE, lh - 2 * LABEL_LINE).extrude(-CUT))
        plate = plate.cut(frame)
        probe = cq.Workplane("XY").text(words, 10, 1, combine=False, kind="bold").val().BoundingBox()
        size = 10 * min((lw - 2 * LABEL_LINE - 2.4) / probe.xlen, (lh - 2 * LABEL_LINE - 1.6) / probe.ylen)
        plate = plate.cut(zp(T).center(x, y).text(words, size, -LABEL_DEPTH, combine=False, kind="bold",
                                                  halign="center", valign="center"))
        print("the label %r: %.1f mm letters" % (words, probe.ylen * size / 10))
    # the stripes, each a parallelogram with 45 degree ends, the nearest the screen cut shallowest
    st = STRIPES
    for i, depth in enumerate(LAYER_CHANGES):
        yc = st["y"] + (i - 1) * (st["h"] + st["gap"])
        y0_, y1_ = yc - st["h"] / 2, yc + st["h"] / 2
        bar = zp(T + 0.01).polyline([(st["x0"], y0_), (st["x1"], y0_), (st["x1"] + st["h"], y1_), (st["x0"] + st["h"], y1_)]) \
            .close().extrude(-(depth + 0.01))
        plate = plate.cut(bar)

    # the key's plug: a holder on the floor at the top edge, a channel along it open toward the face. The
    # plug drops in low, its shell inside the top wall, slides up into the top's hole, flush, and the lock
    # drops in under it. The cable goes down through a slot in the stop, open toward the face too.
    y0 = Y_STOP - STOP
    body = body.union(box(KEY_X - PW - HOLDER_WALL, KEY_X + PW + HOLDER_WALL, y0, H - 1, WALL - 0.1, HOLDER_TOP).intersect(full))
    body = body.cut(box(KEY_X - PW, KEY_X + PW, Y_STOP, H - WALL, KEY_Z - PH, HOLDER_TOP + 1))
    body = body.cut(box(KEY_X - PW, KEY_X + PW, H - WALL - 0.01, H + 1, KEY_Z - PH, KEY_Z + PH))
    body = body.cut(cable_slot(KEY_Z, HOLDER_TOP + 1, y0 - 1, STOP + 2))
    dr, dout = DETENT
    for s in (-1, 1):      # round holes for the lock's bumps: dimples cut as spheres break OCC's later booleans here
        x, y, z = detent_at(s, PW)
        body = body.cut(cq.Workplane("YZ").center(y, z).circle(dr).extrude(0.6, both=True).translate((x, 0, 0)))

    # the Pico's cable in through the right side: a square hole with round corners, round the plug. The plug
    # goes in from outside once the plate is on
    hole = box(W - WALL - 1, W + 1, PICO_Y - CABLE / 2, PICO_Y + CABLE / 2, PLUG_Z - CABLE / 2, PLUG_Z + CABLE / 2)
    body = body.cut(hole.edges("|X").fillet(1.5))
    # the breadboard's four corner stops, L-shaped, clear of the tabs on its sides
    if SIGN_MOUNT == "breadboard":
        x0, x1, y0, y1 = bb_box(BB_CLEAR)
        sl, st, sh = BB_STOP
        for cx, sx in ((x0, -1), (x1, 1)):
            for cy, sy in ((y0, -1), (y1, 1)):
                arm_x = box(min(cx, cx - sx * sl), max(cx, cx - sx * sl), min(cy, cy + sy * st), max(cy, cy + sy * st), WALL - 0.1, WALL + sh)
                arm_y = box(min(cx, cx + sx * st), max(cx, cx + sx * st), min(cy + sy * st, cy - sy * sl), max(cy + sy * st, cy - sy * sl),
                            WALL - 0.1, WALL + sh)
                body = body.union(arm_x.union(arm_y).intersect(full))
    # the rubber feet
    fw, fl = FOOT[0] + 2 * FOOT_CLEAR, FOOT[1] + 2 * FOOT_CLEAR
    for x in (FOOT_X, W - FOOT_X):
        for y in (FOOT_END + fl / 2, H - FOOT_END - fl / 2):
            body = body.cut(cq.Workplane("XY").slot2D(fl, fw, 90).extrude(FOOT_DEPTH).translate((x, y, -0.01)))
    return body, plate


def bb_box(grow=0.0):
    """The breadboard's outline on the floor, grown by grow: x0, x1, y0, y1."""
    bl, bw, _ = BREADBOARD
    return BB_X1 - bl - grow, BB_X1 + grow, SIGN_XY[1] - bw / 2 - grow, SIGN_XY[1] + bw / 2 + grow


def colour_bands(plate):
    """The plate cut at the layer changes: (shape, colour, name), the face's band first."""
    cuts = [T + 1] + [T - z for z in LAYER_CHANGES] + [-1]
    return [(plate.intersect(box(-1, W + 1, -1, H + 1, lo, hi)), c, name)
            for (name, c), hi, lo in zip(COLOURS, cuts[:-1], cuts[1:])]


def guard_box():
    """The guard's base: x0, x1, y0, y1."""
    gw, gh, _ = GUARD
    y0 = SIGN_XY[1] + GUARD_DY
    return SIGN_XY[0] - gw / 2, SIGN_XY[0] + gw / 2, y0, y0 + gh


def guard_outline(grow, z0, z1):
    """The base's outline, grown by grow, from z0 to z1 (either way round)."""
    x0, x1, y0, y1 = guard_box()
    lo, hi = sorted((z0, z1))
    return box(x0 - grow, x1 + grow, y0 - grow, y1 + grow, lo, hi).edges("|Z").fillet(GUARD[2] + grow)


def hinge():
    """The hinge's axis, along x: its y and z. The knuckles' tops are flush with the face."""
    return guard_box()[3] - KNUCKLE_R - 0.4, T - KNUCKLE_R


def guard_base():
    """A plate on the well's floor, under the switch's head, a knuckle at each end of the hinge. Prints as
    it sits."""
    x0, x1, y0, y1 = guard_box()
    yh, zh = hinge()
    z0 = T - SIGN_WELL
    b = guard_outline(0, z0, z0 + BASE_T)
    b = b.cut(zp(T).center(*SIGN_XY).circle(CAP_D / 2 + 0.2).extrude(-SIGN_WELL - 1))
    b = b.cut(cap_seat(0.2))
    for x, y in BASE_SCREWS:
        b = b.cut(zp(T).center(x, y).circle(M2_CLEAR / 2).extrude(-SIGN_WELL - 1))
    for k0 in (x0, x1 - KNUCKLE_W):
        tab = cq.Workplane("YZ").polyline([(yh - KNUCKLE_R, z0 + BASE_T - 0.1), (yh + KNUCKLE_R, z0 + BASE_T - 0.1),
                                           (yh + KNUCKLE_R, zh), (yh - KNUCKLE_R, zh)]).close().extrude(KNUCKLE_W)
        tab = tab.union(cq.Workplane("YZ").center(yh, zh).circle(KNUCKLE_R).extrude(KNUCKLE_W))
        b = b.union(tab.translate((k0, 0, 0)).intersect(guard_outline(0, z0, T + 1)))     # inside the round corners
    return b.cut(cq.Workplane("YZ").center(yh, zh).circle(PIN_HOLE_BASE / 2).extrude(GUARD[0] + 2).translate((x0 - 1, 0, 0)))


def cap_seat(grow):
    """The space under the base the cap's flange moves in: its flat edge, TRAVEL and a 45 degree cone up to
    the head, grown by grow."""
    r0, r1 = FLANGE_D / 2 + grow, CAP_D / 2 + grow
    z = Z_FLOOR_TOP - 0.01
    return zp(z).center(*SIGN_XY).circle(r0).extrude(FLANGE_T + TRAVEL + 0.01).faces(">Z").workplane() \
        .circle(r0).workplane(offset=r0 - r1).circle(r1).loft()


def sign_cap(pressed=0.0):
    """The button: a head in the base's hole, a flange under the base, a plunger through the floor. At rest
    the flange is TRAVEL over the floor; pressed, it comes down that far. Prints head down."""
    zf = Z_FLOOR_TOP + TRAVEL - pressed           # the flange's underside
    r0, r1 = FLANGE_D / 2, CAP_D / 2
    c = zp(zf).center(*SIGN_XY).circle(r0).extrude(FLANGE_T).faces(">Z").workplane() \
        .circle(r0).workplane(offset=r0 - r1).circle(r1).loft()
    top = Z_BASE_TOP + CAP_UP - pressed
    c = c.union(zp(zf + FLANGE_T + r0 - r1 - 0.01).center(*SIGN_XY).circle(r1).extrude(top - (zf + FLANGE_T + r0 - r1) + 0.01)
                .faces(">Z").edges().fillet(0.8))
    return c.union(zp(zf + 0.01).center(*SIGN_XY).circle(PLUNGER_D / 2).extrude(-(zf - (Z_TIP - pressed)) - 0.01))


def tact_holder():
    """A plate screwed to two bosses behind the sign well, a pocket in it for the tactile switch, its stem
    toward the plunger, its legs in the pocket's ends; two slots for the wires. Prints as it sits."""
    hw, hl, hf = HOLDER
    x, y = SIGN_XY
    z0 = Z_TACT - hf
    h = box(x - hw / 2, x + hw / 2, y - hl / 2, y + hl / 2, z0, Z_HOLDER).edges("|Z").fillet(1.5)
    h = h.cut(box(x - TACT[4] / 2 - 0.3, x + TACT[4] / 2 + 0.3, y - TACT[1] / 2 - 0.15, y + TACT[1] / 2 + 0.15, Z_TACT, Z_HOLDER + 1))
    for s in (-1, 1):
        h = h.cut(box(x + s * 3.5 - 0.75, x + s * 3.5 + 0.75, y - hl, y + hl, Z_HOLDER - 1.5, Z_HOLDER + 1))
    seat = Z_FLOOR_TOP - 0.5 - M2_SCREW               # the screws' heads: their tips 0.5 under the well's floor
    assert seat < Z_HOLDER - 1.0, "the holder's screws are too long"
    for sx, sy in HOLDER_SCREWS:
        h = h.cut(zp(z0 - 1).center(sx, sy).circle(M2_CLEAR / 2).extrude(Z_HOLDER - z0 + 2))
        if seat > z0:
            h = h.cut(zp(z0 - 1).center(sx, sy).circle(M2_HEAD[0] / 2 + 0.3).extrude(seat - z0 + 1))
    return h


def guard_cover(angle=0.0):
    """Flush with the face when shut, its knuckle between the base's; open, turned angle degrees about the
    hinge, its free edge up. Prints face down."""
    x0, x1, y0, y1 = guard_box()
    yh, zh = hinge()
    g = GUARD_CLEAR
    c = box(x0 + 0.0, x1 - 0.0, y0 + g, yh, T - COVER_T, T).edges("|Z").edges("<Y").fillet(GUARD[2])
    kx0, kx1 = x0 + KNUCKLE_W + g, x1 - KNUCKLE_W - g
    c = c.cut(box(x0 - 1, kx0, yh - KNUCKLE_R - g, yh + 1, T - 5, T + 1)).cut(box(kx1, x1 + 1, yh - KNUCKLE_R - g, yh + 1, T - 5, T + 1))
    c = c.union(cq.Workplane("YZ").center(yh, zh).circle(KNUCKLE_R).extrude(kx1 - kx0).translate((kx0, 0, 0)))
    c = c.cut(cq.Workplane("YZ").center(yh, zh).circle(PIN_HOLE_COVER / 2).extrude(GUARD[0] + 2).translate((x0 - 1, 0, 0)))
    if angle:
        c = c.rotate((0, yh, zh), (1, yh, zh), -angle)      # the free edge up
    return c


def cable_slot(z_round, z_open, y, h):
    """A slot for the key's cable along y, round at the cable, open toward z_open."""
    lo, hi = sorted((z_round, z_open))
    return cq.Workplane("XZ").center(KEY_X, z_round).circle(CABLE_SLOT / 2).extrude(-h).union(
        box(KEY_X - CABLE_SLOT / 2, KEY_X + CABLE_SLOT / 2, 0, h, lo, hi)).translate((0, y, 0))


def detent_at(s, dx):
    """Where a detent's sphere sits: on the channel's side s, dx out from its middle, near the floor."""
    return (KEY_X + s * dx, Y_STOP + LIFT / 2, KEY_Z - PH + 2.5)


def plug_lock():
    """Drops into the holder's channel under the plug once the plug is up, the cable into its slot, which
    is open at its underside (its leading end). Two bumps click into dimples in the channel's walls; the
    lip is to pull it out by. Prints on its side, the lip on the bed."""
    w = 2 * (PW - LOCK_CLEAR)
    z0, h = KEY_Z - PH + LOCK_CLEAR, LIFT - 0.1
    lock = box(KEY_X - w / 2, KEY_X + w / 2, Y_STOP, Y_STOP + h, z0, HOLDER_TOP + LOCK_TAB)
    lock = lock.cut(box(KEY_X - w, KEY_X + w, Y_STOP + 2, Y_STOP + h + 1, HOLDER_TOP, HOLDER_TOP + LOCK_TAB + 1))  # lip: 2 mm
    lock = lock.cut(cable_slot(KEY_Z, z0 - 1, Y_STOP - 1, h + 2))
    dr, dout = DETENT
    for s in (-1, 1):
        lock = lock.union(cq.Workplane("XY").sphere(dr).translate(detent_at(s, w / 2 + dout - dr)))
    return lock


def screen_holes():
    sx, sy = SCREEN_XY
    hx, hy = SCREEN_HOLES
    return [(sx + a * hx / 2, sy + b * hy / 2) for a in (-1, 1) for b in (-1, 1)]


def carrier_screws():
    return [(SCREEN_XY[0] + dx, SCREEN_XY[1] + dy) for dx, dy in CARRIER_SCREWS]


def carrier_and_spacers():
    """The prism's carrier, without the Pico: the screen board's size and 1 mm more, an ear out to each
    boss, cut round the header. It goes over the pins, rests on the bosses and screws into their inserts,
    so the spacers press the board onto its posts. The spacers are four tubes, slipped on the pins."""
    sx, sy = SCREEN_XY
    bw, bh = SCREEN_PCB
    car = zp(Z_CARRIER).center(sx, sy).rect(bw + 2 * CARRIER_MARGIN, bh + 2 * CARRIER_MARGIN).extrude(-CARRIER_T)
    for x, y in carrier_screws():
        edge = sy + math.copysign(bh / 2 - 2, y - sy)
        far = y + math.copysign(EAR_W / 2, y - sy)
        car = car.union(zp(Z_CARRIER).center(x, (edge + far) / 2).rect(EAR_W, abs(far - edge)).extrude(-CARRIER_T))
    nw, nh = HEADER_NOTCH
    n0, n1 = sx - bw / 2 - CARRIER_MARGIN - 1, sx - bw / 2 + nw
    if HEADER_SIDE > 0:
        n0, n1 = 2 * sx - n1, 2 * sx - n0
    car = car.cut(zp(Z_CARRIER + 1).center((n0 + n1) / 2, sy).rect(n1 - n0, nh).extrude(-CARRIER_T - 2))
    car = car.edges("|Z").fillet(CARRIER_R)
    for c in carrier_screws():
        car = car.cut(zp(Z_CARRIER + 1).center(*c).circle(SCREW_D / 2).extrude(-CARRIER_T - 2))
    spacers = None
    for c in screen_holes():
        car = car.cut(zp(Z_CARRIER + 1).center(*c).circle(PIN_HOLE / 2).extrude(-CARRIER_T - 2))
        t = zp(Z_BOARD - SCREEN_PCB_T).center(*c).circle(SPACER_D / 2).circle(PIN_HOLE / 2).extrude(-SPACER)
        spacers = t if spacers is None else spacers.union(t)
    for c in pico_posts():              # the Pico's posts, the prism's: blind holes, 1.5 mm short of the front
        car = car.union(zp(Z_CARRIER_BACK + 0.01).center(*c[:2]).circle(c[2] / 2).extrude(-PICO_UP - 0.01))
        car = car.cut(zp(Z_PICO - 0.01).center(*c[:2]).circle(PICO_SCREW_HOLE / 2).extrude(PICO_SCREW - PICO[2] + 0.5))
    return car, spacers


def pico_posts():
    """Each of the Pico's posts: x, y, diameter. Its USB end is at PICO_X1, the board running left."""
    return [(PICO_X1 - dx, PICO_Y + dy, d) for dx, dy, d in PICO_POSTS]


# --- stand-ins, for the pictures, the STEP and the checks --------------------------------------------------
def stand_ins():
    s = []
    sx, sy = SCREEN_XY
    gw, gh, gt = SCREEN_GLASS
    s.append((zp(ZP - GLASS_GAP).center(sx + SCREEN_DX, sy).rect(gw, gh).extrude(-gt), (0.05, 0.05, 0.06), "screen glass"))
    brd = zp(Z_BOARD).center(sx, sy).rect(*SCREEN_PCB).extrude(-SCREEN_PCB_T)
    for c in screen_holes():
        brd = brd.cut(zp(Z_BOARD + 1).center(*c).circle(PIN_HOLE / 2).extrude(-4))
    s.append((brd, (0.10, 0.30, 0.55), "screen board"))
    s.append((zp(Z_BOARD - SCREEN_PCB_T).center(sx - HEADER_SIDE * 8, sy).rect(50, 26).extrude(-SPACER + 0.5),
              (0.3, 0.3, 0.32), "screen board back parts"))
    s.append((zp(Z_BOARD - SCREEN_PCB_T).center(HEADER_X, sy).rect(*HEADER[:2]).extrude(-HEADER[2]), (0.1, 0.1, 0.1),
              "screen header and wires"))
    heads = None                    # the carrier's M3 x 8 socket heads on M3 washers
    for c in carrier_screws():
        h = zp(Z_CARRIER_BACK).center(*c).circle(3.5).extrude(-0.5).union(
            zp(Z_CARRIER_BACK - 0.5).center(*c).circle(2.75).extrude(-3.0))
        heads = h if heads is None else heads.union(h)
    s.append((heads, (0.08, 0.08, 0.09), "carrier screws"))
    tw, tl, th, tall, legs = TACT
    sw = box(SIGN_XY[0] - tw / 2, SIGN_XY[0] + tw / 2, SIGN_XY[1] - tl / 2, SIGN_XY[1] + tl / 2, Z_TACT, Z_TACT + th)
    sw = sw.union(zp(Z_TACT + th - 0.01).center(*SIGN_XY).circle(1.75).extrude(tall - th + 0.01))
    sw = sw.union(box(SIGN_XY[0] - legs / 2, SIGN_XY[0] + legs / 2, SIGN_XY[1] - tl / 2 + 0.5, SIGN_XY[1] + tl / 2 - 0.5,
                      Z_TACT, Z_TACT + 0.6))
    s.append((sw, (0.25, 0.25, 0.28), "tact switch"))
    if SIGN_MOUNT == "breadboard":
        x0, x1, y0, y1 = bb_box()
        s.append((box(x0, x1, y0, y1, WALL, Z_TACT), (0.95, 0.95, 0.97), "breadboard"))
    heads = None                    # the guard's base's two M2 socket heads
    for x, y in BASE_SCREWS:
        h = zp(Z_BASE_TOP).center(x, y).circle(M2_HEAD[0] / 2).extrude(M2_HEAD[1])
        heads = h if heads is None else heads.union(h)
    s.append((heads, (0.08, 0.08, 0.09), "base screws"))
    kfloor = T - KNOB_WELL[1]
    s.append((zp(kfloor + 2.5).center(*KNOB_XY).circle(9).extrude(13).faces(">Z").edges().fillet(1.5), (0.1, 0.1, 0.11), "knob"))
    s.append((zp(kfloor + 15.5).center(KNOB_XY[0], KNOB_XY[1] + 5).rect(0.8, 6).extrude(0.4), (0.9, 0.9, 0.9), "knob mark"))
    s.append((zp(kfloor - KNOB_FLOOR).center(*KNOB_XY).rect(*EC11[:2]).extrude(-EC11[2]), (0.25, 0.25, 0.28), "EC11 body"))
    s.append((box(KEY_X - PLUG_W / 2, KEY_X + PLUG_W / 2, H - PLUG_L, H, KEY_Z - PLUG_H / 2, KEY_Z + PLUG_H / 2),
              (0.15, 0.15, 0.15), "plug overmold"))
    s.append((cq.Workplane("XZ").center(KEY_X, KEY_Z).slot2D(SHELL_W, SHELL_H).extrude(-SHELL_L).translate((0, H, 0)),
              (0.8, 0.8, 0.82), "plug shell"))
    # the cartridge plugged on: its length up out of the top edge, its chip's window toward the face
    o = (KEY_X, H, KEY_Z - (K.KEYC[2] + K.REC[1] / 2))
    loc = cq.Location(cq.Plane(origin=o, xDir=(1, 0, 0), normal=(0, 0, 1)))
    top, bottom, board, chip = C.clamshell()
    s.append((cq.Workplane().add(top.val().moved(loc)), K.AMBER, "cartridge cover"))
    s.append((cq.Workplane().add(bottom.val().moved(loc)), K.AMBER_D, "cartridge tray"))
    s.append((cq.Workplane().add(board.val().moved(loc)), (0.10, 0.25, 0.60), "key-c"))
    s.append((cq.Workplane().add(chip.val().moved(loc)), (0.08, 0.08, 0.09), "ATECC608"))
    pc = PICO_X1 - PICO[0] / 2
    s.append((zp(Z_PICO).center(pc, PICO_Y).rect(PICO[0], PICO[1]).extrude(-PICO[2]), (0.10, 0.42, 0.22), "Pico 2 W"))
    near = zp(Z_PICO).center(pc, PICO_Y).rect(PICO[0], PICO[1]).extrude(PICO_PARTS)
    for x, y, d in pico_posts():
        near = near.cut(zp(Z_PICO - 1).center(x, y).circle(d / 2 + 0.2).extrude(PICO_PARTS + 2))
    s.append((near, (0.55, 0.55, 0.58), "Pico's parts, toward the carrier (space)"))
    s.append((zp(Z_PICO - PICO[2]).center(pc, PICO_Y).rect(PICO[0], PICO[1]).extrude(-PICO_WIRES),
              (0.55, 0.55, 0.58), "Pico's wires (space)"))
    pl, pw_, pt = USB_PLUG[:3]
    s.append((box(PICO_X1, PICO_X1 + pl, PICO_Y - pw_ / 2, PICO_Y + pw_ / 2, PLUG_Z - pt / 2, PLUG_Z + pt / 2),
              (0.15, 0.15, 0.15), "USB plug (space)"))
    return s


def checks(body, plate, parts, carrier, spacers, lock, base, cover, cap, holder):
    """Only that nothing obvious collides: the parts are boxes. Not a fit check."""
    n = {name: sh for sh, _, name in parts}
    n["guard base"], n["guard cover"], n["sign cap"], n["tact holder"] = base, cover, cap, holder
    inside = ["screen glass", "screen board", "screen board back parts", "screen header and wires", "carrier screws",
              "tact switch", "EC11 body", "plug overmold", "key-c", "cartridge cover", "cartridge tray",
              "Pico 2 W", "Pico's parts, toward the carrier (space)", "Pico's wires (space)", "USB plug (space)"]
    inside += ["breadboard"] if SIGN_MOUNT == "breadboard" else []
    pairs = [(a, "body", body) for a in inside] + [(a, "plate", plate) for a in inside]
    pairs += [(a, "carrier", carrier) for a in inside if a != "Pico's parts, toward the carrier (space)"]
    pairs += [(a, "spacers", spacers) for a in inside]
    pairs += [("carrier", b, x) for b, x in (("body", body), ("plate", plate), ("spacers", spacers))]
    n["plate"] = plate
    pairs += [("plate", "body", body)]
    pairs += [("spacers", b, x) for b, x in (("body", body), ("plate", plate))]
    pairs += [(a, "plug lock", lock) for a in inside] + [("plug lock", "body", body), ("plug lock", "carrier", carrier)]
    n["carrier"], n["spacers"], n["plug lock"] = carrier, spacers, lock
    together = ({"key-c", "cartridge cover"}, {"key-c", "cartridge tray"}, {"cartridge cover", "cartridge tray"},
                {"Pico 2 W", "Pico's parts, toward the carrier (space)"}, {"Pico 2 W", "Pico's wires (space)"},
                {"Pico's parts, toward the carrier (space)", "USB plug (space)"}, {"tact switch", "breadboard"})
    pairs += [(a, b, n[b]) for i, a in enumerate(inside) for b in inside[i + 1:] if {a, b} not in together]
    # the guard, shut and opening: its cover clears the plate, the base, the switch's head and the knob
    pairs += [("guard base", "plate", plate), ("guard cover", "plate", plate), ("guard cover", "guard base", base)]
    pairs += [(g, h, n[h]) for g in ("guard base", "guard cover") for h in ("sign cap", "base screws", "knob")]
    pairs += [("sign cap", h, x) for h, x in (("plate", plate), ("tact switch", n["tact switch"]))]
    if holder is not None:
        pairs += [("tact holder", h, x) for h, x in (("plate", plate), ("tact switch", n["tact switch"]), ("carrier", carrier),
                                                     ("body", body), ("EC11 body", n["EC11 body"]))]
    for a in (30, 60, 90):
        n["guard cover open %d" % a] = guard_cover(a)
        pairs += [("guard cover open %d" % a, b, x) for b, x in (("plate", plate), ("guard base", base), ("sign cap", cap),
                                                                ("base screws", n["base screws"]))]
    bad = 0
    for a, bname, b in pairs:
        v = n[a].intersect(b).val().Volume()
        if v > 0.05:
            bad += 1
            print("  OVERLAP %-36s %-24s %.2f mm3" % (a, bname, v))
    print("checked %d pairs: %s" % (len(pairs), "clear" if not bad else "%d overlap" % bad))

    def d(a, b):
        return (n[a] if isinstance(a, str) else a).val().distance((n[b] if isinstance(b, str) else b).val())
    print("closest: the carrier to the body %.1f mm; the plug lock to the carrier %.1f mm; the Pico's wires to the "
          "screen's header %.1f mm" % (d(carrier, body), d(lock, carrier), d("Pico's wires (space)", "screen header and wires")))
    if SIGN_MOUNT == "breadboard":
        x0, x1, y0, y1 = bb_box()
        posts = body.intersect(box(0, W, 0, H, WALL + BB_STOP[2] + 0.01, ZP))       # the tub above the stops
        print("the breadboard, %.1f x %.1f, %.1f tall, at x %.1f to %.1f, y %.1f to %.1f: to the tub's posts %.1f mm, the "
              "carrier's screws %.1f mm, the EC11 %.1f mm, the Pico's wires %.1f mm, the plate %.1f mm over it" % (
                  BREADBOARD[0], BREADBOARD[1], BREADBOARD[2], x0, x1, y0, y1, d("breadboard", posts),
                  d("breadboard", "carrier screws"), d("breadboard", "EC11 body"), d("breadboard", "Pico's wires (space)"),
                  d("breadboard", plate)))
    print("the Pico's wires to the tub %.1f mm (the floor, the key's plug holder); its plug to the carrier %.1f mm" % (
        d("Pico's wires (space)", body), d("USB plug (space)", carrier)))
    pressed = sign_cap(TRAVEL)
    print("the sign button: its plunger %.1f mm over the switch's stem, %.1f mm below the well's floor; pressed %.2f mm "
          "to the stop, it pushes the stem %.2f mm (the switch's travel, about %.2f)" % (
              STEM_GAP, Z_FLOOR_BOT - Z_TIP, TRAVEL, TRAVEL - STEM_GAP, TACT_TRAVEL))
    if holder is not None:
        print("the switch %.1f mm in its holder's pocket, %.1f mm off the floor" % (Z_HOLDER - Z_TACT, Z_TACT - HOLDER[2] - WALL))
    assert pressed.intersect(plate).val().Volume() < 0.05, "the cap, pressed, goes into the plate"
    stop = 90
    while stop < 180 and guard_cover(stop + 5).intersect(plate).val().Volume() < 0.05:
        stop += 5
    print("the guard's cover opens to %d degrees, where it rests on the well's edge" % stop)
    print("the guard: the cover %.1f mm over the cap's head; the wells %.1f mm (the knob) and %.1f mm (the switch) "
          "deep, their floors %.1f and %.1f mm" % (d("guard cover", "sign cap"), KNOB_WELL[1], SIGN_WELL,
                                                  KNOB_FLOOR, SIGN_FLOOR))
    gx0, gx1 = SCREEN_XY[0] + SCREEN_DX - SCREEN_GLASS[0] / 2, SCREEN_XY[0] + SCREEN_DX + SCREEN_GLASS[0] / 2
    gy0, gy1 = SCREEN_XY[1] - SCREEN_GLASS[1] / 2, SCREEN_XY[1] + SCREEN_GLASS[1] / 2
    bx0, bx1 = SCREEN_XY[0] - SCREEN_PCB[0] / 2, SCREEN_XY[0] + SCREEN_PCB[0] / 2
    by0, by1 = SCREEN_XY[1] - SCREEN_PCB[1] / 2, SCREEN_XY[1] + SCREEN_PCB[1] / 2

    def gap(c, r, x0, x1, y0, y1):
        return math.hypot(max(x0 - c[0], 0, c[0] - x1), max(y0 - c[1], 0, c[1] - y1)) - r
    print("the glass's edge to the nearest hole's centre: %.2f mm (a seat closer than %.1f is cut flat); "
          "the bosses to the screen's board: %.2f mm" % (
              min(gap(c, 0, gx0, gx1, gy0, gy1) for c in screen_holes()), SEAT_D / 2 + GLASS_CLEAR,
              min(gap(c, BOSS_D / 2, bx0, bx1, by0, by1) for c in carrier_screws())))
    print("the Pico's posts to the nearest pin's pad: %.2f mm; the USB end's posts to the socket between them: %.2f mm; "
          "the plug to its posts %.1f mm, to the hole in the side %.1f mm" % (
              min(math.hypot(dx - (1.61 + 2.54 * i), dy - s * 8.89) - dd / 2 - 0.85
                  for dx, dy, dd in PICO_POSTS for i in range(20) for s in (-1, 1)),
              min(math.hypot(max(abs(dy) - USB_SOCKET[0] / 2, 0), max(dx - USB_SOCKET[1], 0)) - dd / 2
                  for dx, dy, dd in PICO_POSTS if dx < PICO[0] / 2),
              min(math.hypot(dx, max(abs(dy) - USB_PLUG[1] / 2, 0)) - dd / 2 for dx, dy, dd in PICO_POSTS if dx < PICO[0] / 2),
              n["USB plug (space)"].val().distance(body.val())))
    # the tub as it prints, on its back: flat faces that face down and aren't on the bed
    over = []
    for f in body.val().Faces():
        if f.geomType() == "PLANE" and f.Area() >= 2 and f.normalAt().z < -math.cos(math.radians(45)) - 0.01 \
                and f.Center().z > 0.5:
            over.append((f.Area(), f.Center()))
    print("overhangs past 45 degrees as the tub prints: %d" % len(over))
    for a, c in sorted(over, key=lambda t: -t[0]):
        print("  %6.1f mm2 at x %.0f y %.0f z %.0f" % (a, c.x, c.y, c.z))
    # the plate as it prints, face down: flat faces that face up from the bed (down in this frame) and overhang
    over = []
    for f in plate.val().Faces():
        if f.geomType() == "PLANE" and f.Area() >= 2 and f.normalAt().z > math.cos(math.radians(45)) + 0.01 \
                and f.Center().z < T - 0.5:
            over.append((f.Area(), f.Center()))
    print("overhangs past 45 degrees as the plate prints, face down: %d" % len(over))
    for a, c in sorted(over, key=lambda t: -t[0])[:12]:
        print("  %6.1f mm2 at x %.0f y %.0f, %.1f mm off the bed" % (a, c.x, c.y, T - c.z))
    return bad


def main():
    os.makedirs(OUT, exist_ok=True)
    screen_png = sys.argv[1] if len(sys.argv) > 1 else None
    body, plate = tub_and_plate()
    carrier, spacers = carrier_and_spacers()
    lock = plug_lock()
    parts = stand_ins()
    base, cover, cap = guard_base(), guard_cover(), sign_cap()
    holder = tact_holder() if SIGN_MOUNT == "holder" else None
    stale = os.path.join(OUT, "handheld_tact_holder.stl")
    if holder is None and os.path.exists(stale):        # only the mount in use has its part
        os.remove(stale)
    bad = checks(body, plate, parts, carrier, spacers, lock, base, cover, cap, holder) + C.checks()

    def stl(shape, name, tol=0.05):
        cq.exporters.export(shape.translate((0, 0, -shape.val().BoundingBox().zmin)), os.path.join(OUT, name),
                            tolerance=tol, angularTolerance=0.2)
    stl(body, "handheld_body.stl")                                              # on its back, as it is
    flip = lambda s: s.rotate((0, 0, 0), (1, 0, 0), 180)                        # face down
    stl(flip(plate), "handheld_plate.stl")
    stl(flip(carrier), "handheld_carrier.stl")
    stl(spacers, "handheld_spacers.stl")
    stl(lock.rotate((0, 0, 0), (0, 1, 0), 90), "handheld_plug_lock.stl", 0.02)  # on its side
    stl(base, "handheld_guard_base.stl", 0.02)                                  # as it sits
    stl(flip(cover), "handheld_guard_cover.stl", 0.02)                          # face down
    stl(flip(cap), "handheld_sign_cap.stl", 0.02)                               # head down
    if holder is not None:
        stl(holder, "handheld_tact_holder.stl", 0.02)                           # as it sits
    C.write(OUT)
    bb = body.val().BoundingBox()
    print("the case closed: %.0f x %.0f x %.0f mm; with a key in, %.0f mm tall" % (
        bb.xlen, bb.ylen, bb.zlen, H + K.CART[1]))
    asm = cq.Assembly(name="pico_sign_handheld")
    asm.add(body, name="body", color=cq.Color(0.20, 0.21, 0.23))
    asm.add(plate, name="plate", color=cq.Color(0.74, 0.73, 0.70))
    asm.add(carrier, name="carrier", color=cq.Color(0.35, 0.36, 0.40))
    asm.add(spacers, name="spacers", color=cq.Color(0.90, 0.60, 0.20))
    asm.add(lock, name="plug_lock", color=cq.Color(0.90, 0.60, 0.20))
    asm.add(base, name="guard_base", color=cq.Color(0.35, 0.36, 0.40))
    asm.add(cover, name="guard_cover", color=cq.Color(0.80, 0.12, 0.10))
    asm.add(cap, name="sign_cap", color=cq.Color(0.90, 0.60, 0.20))
    if holder is not None:
        asm.add(holder, name="tact_holder", color=cq.Color(0.90, 0.60, 0.20))
    for sh, c, nm in parts:
        asm.add(sh, name=nm.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "").replace("'", ""),
                color=cq.Color(*c))
    asm.save(os.path.join(OUT, "handheld_assembly.step"))

    aw, ah = SCREEN_ACTIVE
    gx, sy = SCREEN_XY[0] + SCREEN_DX, SCREEN_XY[1]
    corners = [(gx + a * aw / 2, sy + b * ah / 2, ZP - GLASS_GAP + 0.01) for a, b in ((-1, 1), (1, 1), (1, -1), (-1, -1))]
    PLATE_C, LOCK_C, RED = (0.74, 0.73, 0.70), (0.90, 0.60, 0.20), (0.80, 0.12, 0.10)
    keep = ("screen glass", "knob", "knob mark", "cartridge cover", "cartridge tray", "ATECC608")
    shown = [p for p in parts if p[2] in keep] + [(base, (0.35, 0.36, 0.40), "guard base"), (cover, COLOURS[2][1], "guard cover")]
    K.render(dict(title="The handheld", parts=[(body, K.DARK, "body"), (plate, PLATE_C, "plate")] + shown, corners=corners,
                  views=[("in the hand", 62, -90), ("the top edge: the key on its plug", 28, 125)]),
             os.path.join(OUT, "handheld_front.png"), screen_png)
    inside = [(body, K.DARK, "body"), (lock, LOCK_C, "plug lock")] + \
        [p for p in parts if p[2] in ("plug overmold", "plug shell", "cartridge cover", "cartridge tray", "key-c", "ATECC608")
         or (SIGN_MOUNT == "breadboard" and p[2] in ("breadboard", "tact switch"))]
    K.render(dict(title="The tub, open", parts=inside, corners=[],
                  views=[("the key's plug and its lock" + (", the breadboard" if SIGN_MOUNT == "breadboard" else ""), 55, -70),
                         ("the right side: the Pico's cable", 20, -30)]),
             os.path.join(OUT, "handheld_tub.png"))
    GREY = (0.35, 0.36, 0.40)
    opt = lambda sh, c, nm: [(sh, c, nm)] if sh is not None else []
    on_plate = ("screen board", "screen header and wires", "carrier screws", "EC11 body", "Pico 2 W") + \
        (("tact switch",) if holder is not None else ())
    back = [(flip(plate), PLATE_C, "plate"), (flip(carrier), GREY, "carrier"), (flip(spacers), LOCK_C, "spacers"),
            (flip(base), GREY, "guard base")] + opt(holder and flip(holder), LOCK_C, "tact holder") + \
        [(flip(sh), c, nm) for sh, c, nm in parts if nm in on_plate]
    K.render(dict(title="Behind the plate", parts=back, corners=[],
                  views=[("the carrier, the Pico on it" + (", the sign button's holder" if holder is not None else ""), 55, -90),
                         ("from the right", 20, -10)]),
             os.path.join(OUT, "handheld_carrier.png"))
    K.render(dict(title="The plate", parts=[(plate, PLATE_C, "plate")], corners=corners,
                  views=[("front: the wells", 70, -90), ("back: posts and pins, bosses, the wells' backs", 45, 90)]),
             os.path.join(OUT, "handheld_plate.png"), screen_png)
    # the colours are drawn by assembly.py (out/assembly/00-colours.png): its renderer sorts the bands right
    near = box(SIGN_XY[0] - 22, W + 1, SIGN_XY[1] - 22, SIGN_XY[1] + 26, ZP - 6, T + 1)
    sw = [p for p in parts if p[2] in ("tact switch", "base screws", "breadboard")]
    where = "in its holder" if holder is not None else "on the breadboard"
    cut = box(SIGN_XY[0], W + 1, -1, H, 0, T + 2)                 # the side view cut through the button's middle
    K.render(dict(title="The sign button's guard", corners=[],
                  parts=[(plate.intersect(near), PLATE_C, "plate"), (base, GREY, "guard base"), (cap, LOCK_C, "sign cap"),
                         (guard_cover(100), RED, "guard cover")] + opt(holder, LOCK_C, "tact holder") + sw,
                  views=[("open: the cap in its well", 50, -70)]),
             os.path.join(OUT, "handheld_guard.a.png"))
    K.render(dict(title="The sign button's guard", corners=[],
                  parts=[(sh.cut(cut), c, nm) for sh, c, nm in [(plate.intersect(near), PLATE_C, "plate"), (base, GREY, "base"),
                                                               (cap, LOCK_C, "cap"), (guard_cover(), RED, "cover")]
                         + opt(holder, LOCK_C, "holder") + sw],
                  views=[("cut through the middle: the cover, the cap, the switch " + where, 0, 0)]),
             os.path.join(OUT, "handheld_guard.b.png"))
    from PIL import Image
    a, b = Image.open(os.path.join(OUT, "handheld_guard.a.png")), Image.open(os.path.join(OUT, "handheld_guard.b.png"))
    sheet = Image.new("RGB", (a.width + b.width, a.height), (240, 239, 242))
    sheet.paste(a, (0, 0)); sheet.paste(b, (a.width, 0)); sheet.save(os.path.join(OUT, "handheld_guard.png"))
    os.remove(os.path.join(OUT, "handheld_guard.a.png")); os.remove(os.path.join(OUT, "handheld_guard.b.png"))
    for f in sorted(os.listdir(OUT)):
        print("wrote", os.path.join("hardware/builds/pico-sign-handheld/case/out", f))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
