"""pico-sign-handheld's case: flat, portrait, held in two hands or laid on the desk. A tub, printed in
one piece on its back, open at the face, and a front plate that holds everything you touch or read:
the 2.4" screen across the top half; under it the knob on the left and the sign switch on the right,
each with a frame for a label. The plate fixes with four M3 countersunk screws into heat-set inserts in
posts at the tub's corners. The key's USB-C plug stands in a holder at the top edge, built up from the
back, its face flush with the edge: the key, in its cartridge (pico-sign's concepts.py), plugs straight
down onto it and stands up out of the top. The screen mount is the prism's (pico-sign's prism.py): posts
and pins on the plate's back, spacers, a carrier screwed to four bosses. The Pico lies on four posts on
the tub's floor between the knob and the switch, its USB out through the bottom edge.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign-handheld/case/handheld.py [screen.png]
(or tools/case build handheld)

Writes out/: handheld_body.stl (on its back, as it prints), handheld_plate.stl (face down),
handheld_carrier.stl, handheld_spacers.stl, handheld_plug_lock.stl, handheld_assembly.step, and
handheld_*.png (the screen PNG warped onto the panel if one is given).

A first draft to print and try. The 2.4" screen's numbers are placeholders (SCREEN_*): measure yours.
The sign switch is a short-bodied 12 mm one (SIGN_DEPTH), not measured; the script prints how deep a
switch fits. The knob, the plugs and the Pico are the prism's numbers. The script checks only that the
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
import concepts as K        # the key cartridge and the pictures

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
KNOB_XY, SIGN_XY = (22.0, 30.0), (64.0, 30.0)    # under the screen: the knob left, the sign switch right
SIGN_HOLE, SIGN_RING, SIGN_RING_T = 12.2, 26.0, 2.0     # a 12 mm metal push switch; a thicker ring: it's pressed hard
SIGN_BODY, SIGN_DEPTH = 16.0, 20.0  # its body and lugs behind the ring: a short one, not measured (README)
KNOB_HOLE = 7.2                     # EC11, M7 bushing
EC11 = (12.0, 12.0, 7.0)            # its body behind the plate
NAME = "PICOQUORUM"                 # between the controls and the screen, as big as fits
LABELS = [(KNOB_XY[0], 13.0, (20.0, 6.0)), (SIGN_XY[0] - 3.0, 13.0, (20.0, 6.0))]   # frames for a label: x, y, size
LABEL_LINE, CUT = 0.6, 0.6
M3_INSERT = (4.2, 6.0)              # M3*6*5, as the prism: the hole, the insert's length
SCREW_D, CSK_D = 3.4, 6.6           # M3 countersunk: not in the kit
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

# --- the Pico on the tub's floor, its USB down through the bottom edge ----------------------------------
PICO = (21.0, 51.0, 1.0)
PICO_X = 42.0                       # its centre line, between the knob and the switch
PICO_Y0 = 10.0                      # its USB end
PICO_UP = 6.0                       # its posts, from the floor
PICO_POST_D, PICO_POST_D_USB = 4.5, 3.6         # the prism's: slimmer at the USB end, clear of the plug and socket
PICO_SCREW_HOLE, PICO_SCREW = 1.8, 8.0          # M2 x 8, cutting its own thread
PICO_HOLES = [(-5.7, 2.0), (5.7, 2.0), (-5.7, 49.0), (5.7, 49.0)]   # from its USB end
PICO_POSTS = [(dx, dy, PICO_POST_D_USB if dy < PICO[1] / 2 else PICO_POST_D) for dx, dy in PICO_HOLES]
PICO_WIRES = 4.0                    # wires soldered to its pads, on the side away from the floor
USB_PLUG = (24.0, 11.0, 8.0, 1.5)   # micro-USB: the overmold's length out of the case, width, thickness, axis off the face
USB_SOCKET = (7.5, 5.6, 2.6)        # under the board when it lies parts down: wide, in from its end, tall. Not measured
CABLE = 14.0                        # the square hole in the bottom edge: the plug passes, its socket on either face
Z_PICO = WALL + PICO_UP             # the Pico's underside
PLUG_LO = Z_PICO - USB_PLUG[3] - USB_PLUG[2] / 2                # the plug's reach down, socket under the board
PLUG_HI = Z_PICO + PICO[2] + USB_PLUG[3] + USB_PLUG[2] / 2      # and up, socket on top
assert WALL + PICO_UP >= PICO_SCREW - PICO[2] + 1.0, "the Pico's posts are too short for their screws"

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

    # the corner posts, an insert in each; the plate's countersunk screws
    for x, y in SCREWS:
        body = body.union(zp(WALL - 0.1).center(x, y).circle(POST_D / 2).extrude(ZP - WALL + 0.1).intersect(full))
        body = body.cut(zp(ZP + 0.01).center(x, y).circle(M3_INSERT[0] / 2).extrude(-M3_INSERT[1] - 1))
        plate = plate.cut(zp(T + 1).center(x, y).circle(SCREW_D / 2).extrude(-(PLATE + 2)))
        plate = plate.cut(zp(T).center(x, y).circle(CSK_D / 2).workplane(offset=-(CSK_D - SCREW_D) / 2)
                          .circle(SCREW_D / 2).loft())

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
    plate = plate.union(zp(ZP).center(*SIGN_XY).circle(SIGN_RING / 2).extrude(-SIGN_RING_T))
    for xy, d in ((SIGN_XY, SIGN_HOLE), (KNOB_XY, KNOB_HOLE)):
        plate = plate.cut(zp(T + 1).center(*xy).circle(d / 2).extrude(-(PLATE + SIGN_RING_T + 2)))

    # the name, between the controls' tops and the window's bevel, clear of the edge's chamfer
    y0 = max(KNOB_XY[1] + 9.0, SIGN_XY[1] + 8.0) + 3.0      # the knob's cap, the switch's nut
    y1 = sy - (ah + 6) / 2 - 1.5
    half = min(gx, W - gx) - FRONT_C - 9.0
    probe = cq.Workplane("XY").text(NAME, 10, 1, combine=False).val().BoundingBox()
    size = 10 * min(2 * half / probe.xlen, (y1 - y0) / probe.ylen)
    print("the name: %.1f mm letters, %.0f mm long" % (probe.ylen * size / 10, probe.xlen * size / 10))
    plate = plate.cut(zp(T).center(gx, (y0 + y1) / 2).text(NAME, size, -CUT, combine=False, halign="center", valign="center"))
    for x, y, (lw, lh) in LABELS:
        frame = zp(T).center(x, y).rect(lw, lh).extrude(-CUT).cut(
            zp(T).center(x, y).rect(lw - 2 * LABEL_LINE, lh - 2 * LABEL_LINE).extrude(-CUT))
        plate = plate.cut(frame)

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

    # the Pico's posts on the floor, a hole each for an M2 screw that cuts its own thread
    posts = holes = None
    for dx, dy, d in PICO_POSTS:
        c = (PICO_X + dx, PICO_Y0 + dy)
        p = zp(1.0).center(*c).circle(d / 2).extrude(Z_PICO - 1.0)
        h = zp(Z_PICO + 0.01).center(*c).circle(PICO_SCREW_HOLE / 2).extrude(-(PICO_SCREW - PICO[2] + 0.5))
        posts, holes = (p, h) if posts is None else (posts.union(p), holes.union(h))
    body = body.union(posts).cut(holes)
    # its cable out through the bottom edge: a square hole with round corners, the plug passes either way up
    zc = max((PLUG_LO + PLUG_HI) / 2, WALL + 0.3 + CABLE / 2)      # not flush with the floor: OCC chokes on it
    hole = box(PICO_X - CABLE / 2, PICO_X + CABLE / 2, -1, WALL + 1, zc - CABLE / 2, zc + CABLE / 2)
    body = body.cut(hole.edges("|Y").fillet(1.5))
    # the rubber feet
    fw, fl = FOOT[0] + 2 * FOOT_CLEAR, FOOT[1] + 2 * FOOT_CLEAR
    for x in (FOOT_X, W - FOOT_X):
        for y in (FOOT_END + fl / 2, H - FOOT_END - fl / 2):
            body = body.cut(cq.Workplane("XY").slot2D(fl, fw, 90).extrude(FOOT_DEPTH).translate((x, y, -0.01)))
    return body, plate


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
    return car, spacers


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
    s.append((zp(T).center(*SIGN_XY).polygon(6, 16).extrude(2.5).union(
        zp(T + 2.5).center(*SIGN_XY).circle(6).extrude(5)).union(zp(T + 7.5).center(*SIGN_XY).circle(6.3).extrude(1.5)),
        (0.78, 0.78, 0.80), "sign switch"))
    s.append((zp(ZP - SIGN_RING_T).center(*SIGN_XY).circle(SIGN_BODY / 2).extrude(-SIGN_DEPTH), (0.25, 0.25, 0.28),
              "sign switch body"))
    s.append((zp(T).center(*KNOB_XY).circle(9).extrude(13).faces(">Z").edges().fillet(1.5), (0.1, 0.1, 0.11), "knob"))
    s.append((zp(T + 13).center(KNOB_XY[0], KNOB_XY[1] + 5).rect(0.8, 6).extrude(0.4), (0.9, 0.9, 0.9), "knob mark"))
    s.append((zp(ZP).center(*KNOB_XY).rect(*EC11[:2]).extrude(-EC11[2]), (0.25, 0.25, 0.28), "EC11 body"))
    s.append((box(KEY_X - PLUG_W / 2, KEY_X + PLUG_W / 2, H - PLUG_L, H, KEY_Z - PLUG_H / 2, KEY_Z + PLUG_H / 2),
              (0.15, 0.15, 0.15), "plug overmold"))
    s.append((cq.Workplane("XZ").center(KEY_X, KEY_Z).slot2D(SHELL_W, SHELL_H).extrude(-SHELL_L).translate((0, H, 0)),
              (0.8, 0.8, 0.82), "plug shell"))
    # the cartridge plugged on: its length up out of the top edge, its chip's window toward the face
    o = (KEY_X, H, KEY_Z - (K.KEYC[2] + K.REC[1] / 2))
    loc = cq.Location(cq.Plane(origin=o, xDir=(1, 0, 0), normal=(0, 0, 1)))
    top, bottom, board, chip = K.cartridge()
    s.append((cq.Workplane().add(top.val().moved(loc)), K.AMBER, "cartridge top"))
    s.append((cq.Workplane().add(bottom.val().moved(loc)), K.AMBER_D, "cartridge bottom"))
    s.append((cq.Workplane().add(board.val().moved(loc)), (0.10, 0.25, 0.60), "key-c"))
    s.append((cq.Workplane().add(chip.val().moved(loc)), (0.08, 0.08, 0.09), "ATECC608"))
    pc = PICO_Y0 + PICO[1] / 2
    s.append((zp(Z_PICO).center(PICO_X, pc).rect(PICO[0], PICO[1]).extrude(PICO[2]), (0.10, 0.42, 0.22), "Pico 2 W"))
    s.append((zp(Z_PICO + PICO[2]).center(PICO_X, pc).rect(PICO[0], PICO[1]).extrude(PICO_WIRES),
              (0.55, 0.55, 0.58), "Pico's parts and wires, face up (space)"))
    under = zp(Z_PICO).center(PICO_X, pc).rect(PICO[0], PICO[1]).extrude(-USB_SOCKET[2])
    for dx, dy, d in PICO_POSTS:
        under = under.cut(zp(Z_PICO + 1).center(PICO_X + dx, PICO_Y0 + dy).circle(d / 2 + 0.2).extrude(-5))
    s.append((under, (0.55, 0.55, 0.58), "Pico's parts, face down (space)"))
    s.append((box(PICO_X - USB_PLUG[1] / 2, PICO_X + USB_PLUG[1] / 2, PICO_Y0 - USB_PLUG[0], PICO_Y0, PLUG_LO, PLUG_HI),
              (0.15, 0.15, 0.15), "USB plug (space)"))   # the socket on either face: both plugs' room
    return s


def checks(body, plate, parts, carrier, spacers, lock):
    """Only that nothing obvious collides: the parts are boxes. Not a fit check."""
    n = {name: sh for sh, _, name in parts}
    inside = ["screen glass", "screen board", "screen board back parts", "screen header and wires", "carrier screws",
              "sign switch body", "EC11 body", "plug overmold", "key-c", "cartridge top", "cartridge bottom",
              "Pico 2 W", "Pico's parts and wires, face up (space)", "Pico's parts, face down (space)", "USB plug (space)"]
    pairs = [(a, "body", body) for a in inside] + [(a, "plate", plate) for a in inside]
    pairs += [(a, "carrier", carrier) for a in inside] + [(a, "spacers", spacers) for a in inside]
    pairs += [("carrier", b, x) for b, x in (("body", body), ("plate", plate), ("spacers", spacers))]
    pairs += [("spacers", b, x) for b, x in (("body", body), ("plate", plate))]
    pairs += [(a, "plug lock", lock) for a in inside] + [("plug lock", "body", body), ("plug lock", "carrier", carrier)]
    n["carrier"], n["spacers"], n["plug lock"] = carrier, spacers, lock
    together = ({"key-c", "cartridge top"}, {"key-c", "cartridge bottom"}, {"cartridge top", "cartridge bottom"},
                {"Pico 2 W", "Pico's parts and wires, face up (space)"}, {"Pico 2 W", "Pico's parts, face down (space)"},
                {"Pico's parts and wires, face up (space)", "USB plug (space)"},
                {"Pico's parts, face down (space)", "USB plug (space)"})
    pairs += [(a, b, n[b]) for i, a in enumerate(inside) for b in inside[i + 1:] if {a, b} not in together]
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
          "carrier %.1f mm; the Pico's wires to the screen's header %.1f mm" % (
              d(carrier, body), d(lock, carrier), d("Pico's parts and wires, face up (space)", carrier),
              d("Pico's parts and wires, face up (space)", "screen header and wires")))
    print("the Pico to the sign switch's body %.1f mm, to the knob's %.1f mm" % (
        d("Pico 2 W", "sign switch body"), d("Pico 2 W", "EC11 body")))
    sw = n["sign switch body"].val().BoundingBox()
    room = sw.zmin - WALL
    print("the sign switch: %.1f mm behind its ring, %.1f mm off the floor: a switch up to %.1f mm deep fits" % (
        SIGN_DEPTH, room, SIGN_DEPTH + room - 0.5))
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
          "the plug to the tub (the posts, the hole): %.1f mm" % (
              min(math.hypot(dy - (1.61 + 2.54 * i), dx - s * 8.89) - dd / 2 - 0.85
                  for dx, dy, dd in PICO_POSTS for i in range(20) for s in (-1, 1)),
              min(math.hypot(max(abs(dx) - USB_SOCKET[0] / 2, 0), max(dy - USB_SOCKET[1], 0)) - dd / 2
                  for dx, dy, dd in PICO_POSTS if dy < PICO[1] / 2),
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
    return bad


def main():
    os.makedirs(OUT, exist_ok=True)
    screen_png = sys.argv[1] if len(sys.argv) > 1 else None
    body, plate = tub_and_plate()
    carrier, spacers = carrier_and_spacers()
    lock = plug_lock()
    parts = stand_ins()
    bad = checks(body, plate, parts, carrier, spacers, lock)

    def stl(shape, name, tol=0.05):
        cq.exporters.export(shape.translate((0, 0, -shape.val().BoundingBox().zmin)), os.path.join(OUT, name),
                            tolerance=tol, angularTolerance=0.2)
    stl(body, "handheld_body.stl")                                              # on its back, as it is
    flip = lambda s: s.rotate((0, 0, 0), (1, 0, 0), 180)                        # face down
    stl(flip(plate), "handheld_plate.stl")
    stl(flip(carrier), "handheld_carrier.stl")
    stl(spacers, "handheld_spacers.stl")
    stl(lock.rotate((0, 0, 0), (0, 1, 0), 90), "handheld_plug_lock.stl", 0.02)  # on its side
    bb = body.val().BoundingBox()
    print("the case closed: %.0f x %.0f x %.0f mm; with a key in, %.0f mm tall" % (
        bb.xlen, bb.ylen, bb.zlen, H + K.CART[1]))
    asm = cq.Assembly(name="pico_sign_handheld")
    asm.add(body, name="body", color=cq.Color(0.20, 0.21, 0.23))
    asm.add(plate, name="plate", color=cq.Color(0.74, 0.73, 0.70))
    asm.add(carrier, name="carrier", color=cq.Color(0.35, 0.36, 0.40))
    asm.add(spacers, name="spacers", color=cq.Color(0.90, 0.60, 0.20))
    asm.add(lock, name="plug_lock", color=cq.Color(0.90, 0.60, 0.20))
    for sh, c, nm in parts:
        asm.add(sh, name=nm.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "").replace("'", ""),
                color=cq.Color(*c))
    asm.save(os.path.join(OUT, "handheld_assembly.step"))

    aw, ah = SCREEN_ACTIVE
    gx, sy = SCREEN_XY[0] + SCREEN_DX, SCREEN_XY[1]
    corners = [(gx + a * aw / 2, sy + b * ah / 2, ZP - GLASS_GAP + 0.01) for a, b in ((-1, 1), (1, 1), (1, -1), (-1, -1))]
    PLATE_C, LOCK_C = (0.74, 0.73, 0.70), (0.90, 0.60, 0.20)
    keep = ("screen glass", "sign switch", "knob", "knob mark", "cartridge top", "cartridge bottom", "ATECC608")
    shown = [p for p in parts if p[2] in keep]
    K.render(dict(title="The handheld", parts=[(body, K.DARK, "body"), (plate, PLATE_C, "plate")] + shown, corners=corners,
                  views=[("in the hand", 62, -90), ("the top edge: the key on its plug", 28, 125)]),
             os.path.join(OUT, "handheld_front.png"), screen_png)
    on_plate = ("screen", "sign", "knob", "EC11", "carrier")
    inside = [(body, K.DARK, "body"), (lock, LOCK_C, "plug lock")] + \
        [p for p in parts if not p[2].startswith(on_plate) and not p[2].endswith("(space)")]
    K.render(dict(title="The tub, open", parts=inside, corners=[],
                  views=[("the Pico, the key's plug and its lock", 55, -70), ("the bottom edge: the Pico's cable", 20, -120)]),
             os.path.join(OUT, "handheld_tub.png"))
    back = [(flip(plate), PLATE_C, "plate"), (flip(carrier), (0.35, 0.36, 0.40), "carrier"), (flip(spacers), LOCK_C, "spacers")] + \
        [(flip(sh), c, nm) for sh, c, nm in parts if nm in ("screen board", "screen header and wires", "carrier screws",
                                                            "sign switch body", "EC11 body")]
    K.render(dict(title="Behind the plate", parts=back, corners=[],
                  views=[("the screen on its carrier, the switch, the knob", 55, -90), ("from the side", 20, -10)]),
             os.path.join(OUT, "handheld_carrier.png"))
    K.render(dict(title="The plate", parts=[(plate, PLATE_C, "plate")], corners=corners,
                  views=[("front", 70, -90), ("back: posts and pins, bosses, the switch's ring", 45, 90)]),
             os.path.join(OUT, "handheld_plate.png"), screen_png)
    for f in sorted(os.listdir(OUT)):
        print("wrote", os.path.join("hardware/builds/pico-sign-handheld/case/out", f))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
