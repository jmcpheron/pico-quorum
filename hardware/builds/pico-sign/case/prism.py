"""pico-sign's case: the prism. A triangular body, printed in one piece, open at the front, and a
front plate that holds everything you touch or read: the 2.8" screen on the left; on the right the
sign switch on top and the knob under it, each with a frame for a label. The plate fixes with four M3
screws into heat-set inserts in blocks on the side walls. The key's USB-C plug stands in a holder under
the top, on the screen's side, its face flush with the top: the key, in its cartridge (concepts.py),
plugs straight down onto it. On the plate's back the screen rests on four posts, their pins through its
holes; spacers and a carrier plate follow on the pins, and the carrier screws to four bosses with M3
inserts. The Pico screws to the carrier, its cable out through the left wall.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign/case/prism.py [screen.png]

Writes out/prism/: prism_body.stl (on its back, as it prints), prism_plate.stl (face down),
prism_carrier.stl, prism_spacers.stl, prism_assembly.step, and prism_*.png (the screen PNG warped onto the panel if one is given).

A first draft to print and try. The screen's numbers are a placeholder (SCREEN_*): measure yours.
The switch, the knob and the plug are the usual sizes. The script checks only that the parts'
stand-ins don't overlap the body, the plate or each other. All dimensions mm.

Frame: x across, left to right from the front; y from the front edge back; z up. Plate frame:
u = x, v up the plate from its bottom edge, w out of its face.
"""
import math
import os
import sys

import cadquery as cq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import concepts as K        # the key cartridge

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "prism")

# --- the body: a triangle with a flat top band, seen from the side -------------------------------
W = 180.0                   # across
LP = 90.0                   # the front plate's length up its slope
A_F, A_B = 60.0, 70.0       # the front's and the back's angle from the desk
BAND = 34.0                 # the flat top, front to back: the key's plug stands in it
WALL, PLATE = 2.4, 3.0
EDGE = 2.5                  # the chamfer on every outside edge
CF, SF = math.cos(math.radians(A_F)), math.sin(math.radians(A_F))
H = LP * SF                                         # 77.9
P1 = (LP * CF, H)                                   # the front's top edge
P2 = (P1[0] + BAND, H)                              # the band's back edge
P3 = (P2[0] + H / math.tan(math.radians(A_B)), 0.0)  # the back's foot
PROFILE = [(0.0, 0.0), P1, P2, P3]
ACCENT_Z, ACCENT_H, ACCENT_D = 6.0, 3.0, 1.5        # the channel round the base, for a strip of colour

# --- the plate's parts (u, v) -----------------------------------------------------------------------
# Calipers on the bench's 2.8": the board, its holes (4.6 mm) and the panel's thickness. The holes' centres
# from their edges: 35.1 inside and 44.6 outside top to bottom; 76.1 and 76.5 outside across, so about 71.7.
SCREEN_PCB = (80.0, 48.5)           # the board, the 8-pin header on its left, its pins out of the back
SCREEN_PCB_T = 1.5
SCREEN_HOLES = (71.7, 39.85)        # its four holes' centres
SCREEN_GLASS = (66.5, 48.5, 4.0)    # the panel: its outline a placeholder, between the holes; 4.0 thick, the board's front to the glass's
SCREEN_ACTIVE = (57.6, 43.2)        # its active area, landscape: a 2.8" 240x320's, 0.18 mm pixels
SCREEN_DX = 0.0                     # the glass right of the board's centre: a placeholder
SCREEN_UV = (57.0, 50.0)            # the board's centre on the plate
CTRL_U = 140.0                      # the controls' column
SIGN_V, KNOB_V = 62.0, 30.0         # the sign switch on top, the knob under it
SIGN_HOLE, SIGN_RING, SIGN_RING_T = 12.2, 26.0, 2.0     # a 12 mm metal push switch; a thicker ring: it's pressed hard
SIGN_BODY, SIGN_DEPTH = 17.5, 28.0                      # its body and lugs behind the plate
KNOB_HOLE = 7.2                                         # EC11, M7 bushing
NAME = "PICOQUORUM"                 # across the bottom of the screen, as big as fits between the window and the channel
LABELS = [(SIGN_V - 16.5, (30.0, 8.0)), (KNOB_V - 15.0, (30.0, 8.0))]   # frames for a sticker or a printed label: v, size
LABEL_LINE, CUT = 0.6, 0.6          # the frames' line; how deep the name and the frames are cut
SCREWS = [(11.0, 15.0), (W - 11.0, 15.0), (11.0, LP - 9.0), (W - 11.0, LP - 9.0)]   # the bottom two above the channel
# The bench's kits: brass heat-set inserts named thread x length x outside diameter, socket head screws
# M2 x 4/8/12/16 and M3 x 6/8/12/16, nuts and washers. Holes for the inserts are about 0.84 of the outside
# diameter: print one boss and try an insert before the rest.
M3_INSERT = (4.2, 6.0)              # M3*6*5: the hole, the insert's length
M2_INSERT = (2.7, 4.0)              # M2*4*3.2
INSERT_D, INSERT_L, BOSS_L = M3_INSERT[0], M3_INSERT[1], 12.0
SCREW_D, CSK_D = 3.4, 6.6           # M3 countersunk: not in the kit

# --- printing the body: on its back, the front's opening up, the desk's side a wall -------------------
UP = cq.Vector(0, -math.sin(math.radians(A_B)), -math.cos(math.radians(A_B)))   # up from the bed, in the body's frame

# --- the key's plug, standing in the top: the key plugs straight down onto it ----------------------------
# a cut USB-C cable's plug (calipers, twice: the Feather pigtail's and the bench's): overmold, metal shell
PLUG_W, PLUG_H, PLUG_L = 12.4, 5.5, 17.1
SHELL_W, SHELL_H, SHELL_L = 8.25, 2.4, 6.5
PLUG_CLEAR = 0.2                    # round the overmold in its channel and the top's hole
HOLDER_WALL, STOP, CABLE_SLOT = 1.6, 2.0, 5.0       # the channel's walls; the stop at its foot, the cable's slot in it
LIFT = SHELL_L + WALL + 0.5         # the plug goes in this far down, its shell under the top, then up into the hole
LOCK_CLEAR, LOCK_TAB = 0.15, 4.0    # the lock: its clearance in the channel, the lip out of the front to pull it by
DETENT = (0.8, 0.3)                 # the lock's bumps: their radius, how far they stand out (into dimples in the walls)
KEY_X = 24.0                        # on the screen's side, left of the Pico and its wires
Y_BACK_IN = P3[0] - H / math.tan(math.radians(A_B)) - WALL / math.sin(math.radians(A_B))   # the back wall's inside, at the top
KEY_Y = Y_BACK_IN - (PLUG_H / 2 + PLUG_CLEAR + HOLDER_WALL)                                 # the holder against it

# --- behind the screen: posts and pins, spacers, the carrier on its bosses, the Pico on the carrier -----
GLASS_GAP = 0.2                     # the glass this far behind the plate: the posts carry the board, not the glass
SEAT_D = 7.0                        # the posts' tops, the board rests on them round its holes; cut flat where the glass is
GLASS_CLEAR = 0.3                   # the posts' flats this far from the glass's edge
PIN_D, PIN_HOLE = 4.2, 4.6          # pins on the posts, through the board's 4.6 mm holes; the carrier's and spacers' holes
SPACER, SPACER_D = 4.0, 7.0         # tubes on the pins between the board and the carrier: room for the board's back parts
CARRIER_MARGIN = 1.0                # the carrier this much bigger than the board all round: wall round its pin holes
CARRIER_T = 2.5
CARRIER_SCREWS = [(-28.0, -31.0), (-28.0, 31.0), (28.0, -31.0), (28.0, 31.0)]   # from the board's centre: above and below it
EAR_W = 12.0                        # the carrier's ears out to its screws
BOSS_D = 9.0                        # the bosses on the plate's back: the carrier rests on them; an M3 insert in each
HEADER_NOTCH = (9.0, 26.0)          # the carrier is cut round the screen's header and its wires: from the board's edge in, tall
PICO = (51.0, 21.0, 1.0)
PICO_U0 = 30.0                      # its USB end, pointing left: room for the plug and the cable's bend
PICO_V = 67.0                       # its centre line, above the screen's: the plug and cable pass over the screen's header
# The Pico's pins point away from the carrier, its USB to the left. With its headers soldered the usual way
# its parts and USB face the carrier; soldered the other way, they face away. The posts and the cable hole
# take either: the micro-USB plug's overmold, 11 x 8 mm, centred 1.5 mm off whichever face has the socket.
PICO_UP, PICO_POST_D = 6.5, 6.0     # its posts on the carrier's back, an M2 insert in each: the plug clears the carrier
PICO_TOP = 22.0                     # headers and Dupont housings off the board, on the side away from the carrier
USB_PLUG = (24.0, 11.0, 8.0, 1.5)   # the overmold and the cable's bend to the wall, its width, its thickness, its axis off the face
PICO_HOLES = [(2.0, -5.7), (2.0, 5.7), (49.0, -5.7), (49.0, 5.7)]
CABLE = 13.0                        # the square hole in the left wall: the plug passes it, its socket on either face
W_BOARD = -PLATE - GLASS_GAP - SCREEN_GLASS[2]      # the screen board's front: the posts' tops
W_CARRIER = W_BOARD - SCREEN_PCB_T - SPACER                  # the carrier's front: the bosses' tops
W_PICO = W_CARRIER - CARRIER_T - PICO_UP            # the Pico's face on its posts
PLUG_NEAR = W_PICO + USB_PLUG[3] + USB_PLUG[2] / 2               # the plug's reach toward the carrier, socket that side
PLUG_FAR = W_PICO - PICO[2] - USB_PLUG[3] - USB_PLUG[2] / 2      # and away from it, socket the other side
assert -PLATE - W_CARRIER >= M3_INSERT[1] + 1.5, "the bosses are too short for their inserts"
assert CARRIER_T + PICO_UP >= M2_INSERT[1] + 1.0, "the Pico's posts are too short for their inserts"


def plate_plane(w=0.0):
    o = cq.Vector(0, 0, 0) + cq.Vector(0, -SF, CF) * w
    return cq.Plane(origin=o.toTuple(), xDir=(1, 0, 0), normal=(0, -SF, CF))


def pw(w=0.0):
    return cq.Workplane(plate_plane(w))


def world(u, v, w=0.0):
    return plate_plane(w).toWorldCoords((u, v, 0)).toTuple()


def prism(inset=0.0):
    """The whole outside, or (inset > 0) the same shape that much smaller all round."""
    sk = cq.Workplane("YZ").polyline(PROFILE).close()
    if inset:
        sk = sk.offset2D(-inset)
    return sk.extrude(W - 2 * inset).translate((inset, 0, 0))


def slab_z(z0, z1):
    return cq.Workplane("XY").box(1000, 1000, z1 - z0, centered=(True, True, False)).translate((W / 2, 0, z0))


def body_and_plate():
    full = prism().edges().chamfer(EDGE)
    plate_slab = pw(-PLATE).rect(4000, 4000).extrude(PLATE + 0.01)
    plate = full.intersect(plate_slab)
    body = full.cut(plate_slab).cut(prism(WALL))

    # the plate's corner blocks, from the side walls, each with a heat-set insert. Under each, as it prints,
    # a 45 degree chamfer down to its side wall: the block swept toward the wall and down at once
    for u, v in SCREWS:
        left = u < W / 2
        u0, u1 = (WALL - 0.5, u + 4.5) if left else (u - 4.5, W - WALL + 0.5)
        blk = pw(-PLATE).center((u0 + u1) / 2, v).rect(u1 - u0, 9).extrude(-BOSS_L).intersect(prism())
        reach = u1 - WALL if left else W - WALL - u0
        chamfer = swept(blk.val(), (cq.Vector(-1 if left else 1, 0, 0) - UP) * reach)
        body = body.union(blk).union(cq.Workplane().add(chamfer).intersect(full))
        body = body.cut(pw(-PLATE + 0.01).center(u, v).circle(INSERT_D / 2).extrude(-INSERT_L - 1))
    # the accent channel, round all four faces, plate included
    band = full.intersect(slab_z(ACCENT_Z, ACCENT_Z + ACCENT_H)).cut(prism(ACCENT_D))
    body, plate = body.cut(band), plate.cut(band)
    for u, v in SCREWS:
        plate = plate.cut(pw(1).center(u, v).circle(SCREW_D / 2).extrude(-(PLATE + 2)))
        plate = plate.cut(pw(0).center(u, v).circle(CSK_D / 2).workplane(offset=-(CSK_D - SCREW_D) / 2)
                          .circle(SCREW_D / 2).loft())

    # the plate: the screen's window and posts, the switch, the knob, the words
    su, sv = SCREEN_UV
    gu = su + SCREEN_DX
    aw, ah = SCREEN_ACTIVE
    plate = plate.cut(pw(0).center(gu, sv).rect(aw + 6, ah + 6).workplane(offset=-2).rect(aw + 2, ah + 2).loft())
    plate = plate.cut(pw(1).center(gu, sv).rect(aw + 2, ah + 2).extrude(-(PLATE + 2)))
    # the screen's posts, the board rests on them; their pins go on through the board, a spacer and the carrier,
    # 0.3 short of its back, the last 0.5 tapered to lead them in
    tip = W_CARRIER - CARRIER_T + 0.3
    for c in screen_holes():
        post = pw(-PLATE).center(*c).circle(SEAT_D / 2).extrude(W_BOARD + PLATE)
        pin = pw(W_BOARD).center(*c).circle(PIN_D / 2).extrude(tip + 0.5 - W_BOARD)
        lead = pw(tip + 0.5).center(*c).circle(PIN_D / 2).workplane(offset=-0.5).circle(PIN_D / 2 - 0.4).loft()
        plate = plate.union(post).union(pin).union(lead)
    # the glass's outline out of the posts, so a seat by the glass is flat on that side
    gw, gh, _ = SCREEN_GLASS
    plate = plate.cut(pw(-PLATE - 0.01).center(su + SCREEN_DX, sv).rect(gw + 2 * GLASS_CLEAR, gh + 2 * GLASS_CLEAR)
                      .extrude(W_BOARD + PLATE + 0.01))
    # the carrier's bosses, an M3 insert in each
    for c in carrier_screws():
        plate = plate.union(pw(-PLATE).center(*c).circle(BOSS_D / 2).extrude(W_CARRIER + PLATE))
        plate = plate.cut(pw(W_CARRIER - 0.01).center(*c).circle(M3_INSERT[0] / 2).extrude(M3_INSERT[1] + 0.5))
    plate = plate.union(pw(-PLATE).center(CTRL_U, SIGN_V).circle(SIGN_RING / 2).extrude(-SIGN_RING_T))
    for v, d in ((SIGN_V, SIGN_HOLE), (KNOB_V, KNOB_HOLE)):
        plate = plate.cut(pw(1).center(CTRL_U, v).circle(d / 2).extrude(-(PLATE + SIGN_RING_T + 2)))
    # the name: between the bottom screws' countersinks, from above the channel to under the window's bevel
    v0 = (ACCENT_Z + ACCENT_H) / SF + 1.5
    v1 = sv - (ah + 6) / 2 - 1.5
    half = min(gu - (SCREWS[0][0] + CSK_D / 2 + 2.0), SCREWS[1][0] - CSK_D / 2 - 2.0 - gu, CTRL_U - 15 - 2.0 - gu)
    probe = cq.Workplane("XY").text(NAME, 10, 1, combine=False).val().BoundingBox()   # in the text's own frame
    size = 10 * min(2 * half / probe.xlen, (v1 - v0) / probe.ylen)
    print("the name: %.1f mm letters, %.0f mm long" % (probe.ylen * size / 10, probe.xlen * size / 10))
    plate = plate.cut(pw(0).center(gu, (v0 + v1) / 2).text(NAME, size, -CUT, combine=False, halign="center", valign="center"))
    # a frame under each control, for its label
    for v, (lw, lh) in LABELS:
        frame = pw(0).center(CTRL_U, v).rect(lw, lh).extrude(-CUT).cut(
            pw(0).center(CTRL_U, v).rect(lw - 2 * LABEL_LINE, lh - 2 * LABEL_LINE).extrude(-CUT))
        plate = plate.cut(frame)

    # the key's plug: a holder under the top, built back to the back wall, a channel down it open at the front.
    # The plug slides in low, its shell under the top, is pushed up into the top's hole, flush, and the lock
    # slides in under it. The cable goes down through a slot in the stop, open at the front too.
    pw_, ph_ = PLUG_W / 2 + PLUG_CLEAR, PLUG_H / 2 + PLUG_CLEAR
    z_stop = H - PLUG_L - LIFT
    z0, front = z_stop - STOP, KEY_Y - ph_ - HOLDER_WALL
    holder = cq.Workplane("XY").box(2 * (pw_ + HOLDER_WALL), 30, H - z0, centered=(True, False, False)) \
        .translate((KEY_X, front, z0))
    body = body.union(holder.intersect(full))
    body = body.cut(cq.Workplane("XY").box(2 * pw_, KEY_Y + ph_ - front + 1, H - WALL - z_stop, centered=(True, False, False))
                    .translate((KEY_X, front - 1, z_stop)))
    body = body.cut(cq.Workplane("XY").box(2 * pw_, 2 * ph_, WALL + 1, centered=(True, True, False))
                    .translate((KEY_X, KEY_Y, H - WALL - 0.01)))
    body = body.cut(cable_slot(KEY_Y, front - 1, z0 - 1, STOP + 2))
    dr, dout = DETENT
    for sx in (-1, 1):
        body = body.cut(cq.Workplane("XY").sphere(dr + 0.1).translate(detent_at(sx, pw_ - LOCK_CLEAR + dout - dr)))   # the bump's own centre

    # the cable out through the left wall, level with the Pico's USB; rubber feet
    hole = pw(PLUG_NEAR + (CABLE - (PLUG_NEAR - PLUG_FAR)) / 2).center(-1, PICO_V).rect(2 * (WALL + 3), CABLE).extrude(-CABLE)
    body = body.cut(hole.edges("|X").fillet(2.5))
    for x in (14, W - 14):
        for y in (12, P3[0] - 14):
            body = body.cut(cq.Workplane("XY").circle(5.2).extrude(1.0).translate((x, y, 0)))
    return body, plate


def swept(solid, vec):
    """A convex solid swept straight along vec: each face extruded along it, and the solid."""
    out = solid
    for f in solid.Faces():
        if abs(f.normalAt().dot(vec)) > 1e-6:
            out = out.fuse(cq.Solid.extrudeLinear(f, vec))
    return out.clean()


def cable_slot(y_round, y_open, z, h):
    """A slot for the key's cable, round at the cable, open toward y_open."""
    return cq.Workplane("XY").circle(CABLE_SLOT / 2).extrude(h).union(
        cq.Workplane("XY").center(0, (y_open - y_round) / 2).rect(CABLE_SLOT, abs(y_open - y_round)).extrude(h)) \
        .translate((KEY_X, y_round, z))


def detent_at(sx, dx):
    """Where a detent's sphere sits: on the channel's side sx, dx out from its middle, by the back."""
    return (KEY_X + sx * dx, KEY_Y + PLUG_H / 2 + PLUG_CLEAR - 2.5, H - PLUG_L - LIFT / 2)


def plug_lock():
    """The second piece: slides into the holder's channel under the plug once the plug is up, the cable
    into its slot, which is open at the back (its leading end). Its front and a lip join its two sides.
    Two bumps click into dimples in the channel's walls; the lip is to pull it out by. Prints as it sits."""
    pw_, ph_ = PLUG_W / 2 + PLUG_CLEAR, PLUG_H / 2 + PLUG_CLEAR
    front = KEY_Y - ph_ - HOLDER_WALL
    w, back, h = 2 * (pw_ - LOCK_CLEAR), KEY_Y + ph_ - LOCK_CLEAR, LIFT - 0.1
    z = H - PLUG_L - LIFT
    lock = cq.Workplane("XY").box(w, back - front + LOCK_TAB, h, centered=(True, False, False)) \
        .translate((KEY_X, front - LOCK_TAB, z))
    lock = lock.cut(cq.Workplane("XY").box(w + 2, LOCK_TAB + 0.01, h - 2, centered=(True, False, False))
                    .translate((KEY_X, front - LOCK_TAB, z + 2)))           # the lip: only its bottom 2 mm stand out
    lock = lock.cut(cable_slot(KEY_Y, back + 1, z - 1, h + 2))
    dr, dout = DETENT
    for sx in (-1, 1):
        lock = lock.union(cq.Workplane("XY").sphere(dr).translate(detent_at(sx, w / 2 + dout - dr)))
    return lock


def screen_holes():
    su, sv = SCREEN_UV
    hu, hv = SCREEN_HOLES
    return [(su + sx * hu / 2, sv + sy * hv / 2) for sx in (-1, 1) for sy in (-1, 1)]


def carrier_screws():
    return [(SCREEN_UV[0] + du, SCREEN_UV[1] + dv) for du, dv in CARRIER_SCREWS]


def carrier_and_spacers():
    """The plate behind the screen: the size of the screen's board, with an ear out to each of its four
    screws. It goes over the pins, rests on the plate's bosses and screws into their inserts, so the
    spacers press the screen onto its posts. The Pico screws to posts on its back. Prints face down,
    the Pico's posts up. The spacers are four tubes, slipped on the pins."""
    su, sv = SCREEN_UV
    bw, bh = SCREEN_PCB
    car = pw(W_CARRIER).center(su, sv).rect(bw + 2 * CARRIER_MARGIN, bh + 2 * CARRIER_MARGIN).extrude(-CARRIER_T)
    car = car.union(pw(W_CARRIER).center(PICO_U0 + PICO[0] / 2, PICO_V).rect(PICO[0], PICO[1] + 2).extrude(-CARRIER_T))
    for u, v in carrier_screws():
        edge = sv + math.copysign(bh / 2 - 2, v - sv)            # 2 mm into the board's outline
        far = v + math.copysign(EAR_W / 2, v - sv)
        car = car.union(pw(W_CARRIER).center(u, (edge + far) / 2).rect(EAR_W, abs(far - edge)).extrude(-CARRIER_T))
        car = car.cut(pw(W_CARRIER + 1).center(u, v).circle(SCREW_D / 2).extrude(-CARRIER_T - 2))
    nw, nh = HEADER_NOTCH
    n0, n1 = su - bw / 2 - CARRIER_MARGIN - 1, su - bw / 2 + nw          # open past the carrier's edge
    car = car.cut(pw(W_CARRIER + 1).center((n0 + n1) / 2, sv).rect(n1 - n0, nh).extrude(-CARRIER_T - 2))
    spacers = None
    for c in screen_holes():
        car = car.cut(pw(W_CARRIER + 1).center(*c).circle(PIN_HOLE / 2).extrude(-CARRIER_T - 2))
        t = pw(W_BOARD - SCREEN_PCB_T).center(*c).circle(SPACER_D / 2).circle(PIN_HOLE / 2).extrude(-SPACER)
        spacers = t if spacers is None else spacers.union(t)
    for dx, dy in PICO_HOLES:
        c = (PICO_U0 + dx, PICO_V + dy)
        car = car.union(pw(W_CARRIER - CARRIER_T).center(*c).circle(PICO_POST_D / 2).extrude(-PICO_UP))
        car = car.cut(pw(W_PICO + 0.01).center(*c).circle(M2_INSERT[0] / 2).extrude(M2_INSERT[1] + 0.5))
    return car, spacers


# --- stand-ins, for the pictures, the STEP and the checks --------------------------------------------------
def stand_ins():
    s = []
    su, sv = SCREEN_UV
    gw, gh, gt = SCREEN_GLASS
    s.append((pw(-PLATE - GLASS_GAP).center(su + SCREEN_DX, sv).rect(gw, gh).extrude(-gt), (0.05, 0.05, 0.06), "screen glass"))
    brd = pw(W_BOARD).center(su, sv).rect(*SCREEN_PCB).extrude(-SCREEN_PCB_T)
    for sx in (-1, 1):
        for sy in (-1, 1):
            brd = brd.cut(pw(W_BOARD + 1).center(su + sx * SCREEN_HOLES[0] / 2, sv + sy * SCREEN_HOLES[1] / 2)
                          .circle(PIN_HOLE / 2).extrude(-4))
    s.append((brd, (0.10, 0.30, 0.55), "screen board"))
    s.append((pw(W_BOARD - SCREEN_PCB_T).center(su + 10, sv).rect(60, 30).extrude(-SPACER + 0.5), (0.3, 0.3, 0.32),
              "screen board back parts"))
    s.append((pw(W_BOARD - SCREEN_PCB_T).center(su - SCREEN_PCB[0] / 2 + 1.5, sv).rect(3, 21).extrude(-16), (0.1, 0.1, 0.1),
              "screen header and wires"))       # pins 1.5 mm in from the edge (the photo), Dupont housings on them
    heads = None                    # the carrier's M3 x 8 socket heads on M3 washers
    for c in carrier_screws():
        h = pw(W_CARRIER - CARRIER_T).center(*c).circle(3.5).extrude(-0.5).union(
            pw(W_CARRIER - CARRIER_T - 0.5).center(*c).circle(2.75).extrude(-3.0))
        heads = h if heads is None else heads.union(h)
    s.append((heads, (0.08, 0.08, 0.09), "carrier screws"))
    s.append((pw(0).center(CTRL_U, SIGN_V).polygon(6, 16).extrude(2.5).union(
        pw(2.5).center(CTRL_U, SIGN_V).circle(6).extrude(9)).union(pw(11.5).center(CTRL_U, SIGN_V).circle(6.3).extrude(1.5)),
        (0.78, 0.78, 0.80), "sign switch"))
    s.append((pw(-PLATE - SIGN_RING_T).center(CTRL_U, SIGN_V).rect(SIGN_BODY, SIGN_BODY).extrude(-SIGN_DEPTH),
              (0.25, 0.25, 0.28), "sign switch body"))
    s.append((pw(0).center(CTRL_U, KNOB_V).circle(9).extrude(15).faces(">Z").edges().fillet(1.5), (0.1, 0.1, 0.11), "knob"))
    s.append((pw(15).center(CTRL_U, KNOB_V).rect(0.8, 7).extrude(0.4), (0.9, 0.9, 0.9), "knob mark"))
    s.append((pw(-PLATE).center(CTRL_U, KNOB_V).rect(12, 12).extrude(-7), (0.25, 0.25, 0.28), "EC11 body"))
    s.append((cq.Workplane("XY").box(PLUG_W, PLUG_H, PLUG_L, centered=(True, True, False)).translate((KEY_X, KEY_Y, H - PLUG_L)),
              (0.15, 0.15, 0.15), "plug overmold"))
    s.append((cq.Workplane("XY").slot2D(SHELL_W, SHELL_H).extrude(SHELL_L).translate((KEY_X, KEY_Y, H)),
              (0.8, 0.8, 0.82), "plug shell"))
    # the cartridge plugged on: its length up, its receptacle on the plug, its top (the chip's window) to the front
    o = (KEY_X, KEY_Y + K.KEYC[2] + K.REC[1] / 2, H)
    loc = cq.Location(cq.Plane(origin=o, xDir=(1, 0, 0), normal=(0, -1, 0)))
    top, bottom, board, chip = K.cartridge()
    s.append((cq.Workplane().add(top.val().moved(loc)), K.AMBER, "cartridge top"))
    s.append((cq.Workplane().add(bottom.val().moved(loc)), K.AMBER_D, "cartridge bottom"))
    s.append((cq.Workplane().add(board.val().moved(loc)), (0.10, 0.25, 0.60), "key-c"))
    s.append((cq.Workplane().add(chip.val().moved(loc)), (0.08, 0.08, 0.09), "ATECC608"))
    pc = PICO_U0 + PICO[0] / 2
    s.append((pw(W_PICO).center(pc, PICO_V).rect(PICO[0], PICO[1]).extrude(-PICO[2]), (0.10, 0.42, 0.22), "Pico 2 W"))
    s.append((pw(W_PICO - PICO[2]).center(pc + 2, PICO_V).rect(PICO[0] - 4, PICO[1]).extrude(-(PICO_TOP - PICO[2])),
              (0.55, 0.55, 0.58), "headers and wires (space)"))
    pl = USB_PLUG[0]
    s.append((pw(PLUG_NEAR).center(PICO_U0 - 1.3 - pl / 2, PICO_V).rect(pl, USB_PLUG[1]).extrude(PLUG_FAR - PLUG_NEAR),
              (0.15, 0.15, 0.15), "USB plug and bend (space)"))   # the socket on either face: both plugs' room
    near = pw(W_PICO).center(pc, PICO_V).rect(PICO[0], PICO[1]).extrude(3.0)
    for dx, dy in PICO_HOLES:
        near = near.cut(pw(W_PICO - 1).center(PICO_U0 + dx, PICO_V + dy).circle(PICO_POST_D / 2 + 0.2).extrude(5))
    s.append((near, (0.55, 0.55, 0.58), "Pico's parts toward the carrier (space)"))
    return s


def checks(body, plate, parts, carrier, spacers, lock):
    """Only that nothing obvious collides: the parts are boxes. Not a fit check."""
    n = {name: sh for sh, _, name in parts}
    inside = ["screen board", "screen header and wires", "sign switch body", "EC11 body", "plug overmold",
              "headers and wires (space)", "key-c", "cartridge top", "cartridge bottom", "Pico 2 W",
              "screen board back parts", "USB plug and bend (space)", "screen glass", "carrier screws",
              "Pico's parts toward the carrier (space)"]
    pairs = [(a, "body", body) for a in inside] + [(a, "plate", plate) for a in inside if a not in ("plug overmold",)]
    pairs += [(a, "carrier", carrier) for a in inside if a != "Pico 2 W"] + [(a, "spacers", spacers) for a in inside]
    pairs += [("carrier", b, x) for b, x in (("body", body), ("plate", plate), ("spacers", spacers))]
    pairs += [("spacers", b, x) for b, x in (("body", body), ("plate", plate))]
    pairs += [(a, "plug lock", lock) for a in inside] + [("plug lock", "body", body)]
    n["carrier"], n["spacers"], n["plug lock"] = carrier, spacers, lock
    pairs += [(a, b, n[b]) for i, a in enumerate(inside) for b in inside[i + 1:]
              if {a, b} not in ({"key-c", "cartridge top"}, {"key-c", "cartridge bottom"}, {"cartridge top", "cartridge bottom"})]
    bad = 0
    for a, bname, b in pairs:
        v = n[a].intersect(b).val().Volume()
        if v > 0.05:
            bad += 1
            print("  OVERLAP %-28s %-28s %.2f mm3" % (a, bname, v))
    print("checked %d pairs: %s" % (len(pairs), "clear" if not bad else "%d overlap" % bad))
    print("the Pico's wires and plug to the body: %.1f mm; the carrier to the body: %.1f mm" % (min(
        n[k].val().distance(body.val()) for k in ("headers and wires (space)", "USB plug and bend (space)", "carrier screws")),
        carrier.val().distance(body.val())))
    gu0, gu1 = SCREEN_UV[0] + SCREEN_DX - SCREEN_GLASS[0] / 2, SCREEN_UV[0] + SCREEN_DX + SCREEN_GLASS[0] / 2
    gv0, gv1 = SCREEN_UV[1] - SCREEN_GLASS[1] / 2, SCREEN_UV[1] + SCREEN_GLASS[1] / 2
    bu0, bu1 = SCREEN_UV[0] - SCREEN_PCB[0] / 2, SCREEN_UV[0] + SCREEN_PCB[0] / 2
    bv0, bv1 = SCREEN_UV[1] - SCREEN_PCB[1] / 2, SCREEN_UV[1] + SCREEN_PCB[1] / 2
    def gap(c, r, u0, u1, v0, v1):              # a circle outside a rectangle, to its nearest edge
        return math.hypot(max(u0 - c[0], 0, c[0] - u1), max(v0 - c[1], 0, c[1] - v1)) - r
    print("the glass's edge to the nearest hole's centre: %.2f mm (a seat closer than %.1f is cut flat); "
          "the bosses to the screen's board: %.2f mm" % (
        min(gap(c, 0, gu0, gu1, gv0, gv1) for c in screen_holes()), SEAT_D / 2 + GLASS_CLEAR,
        min(gap(c, BOSS_D / 2, bu0, bu1, bv0, bv1) for c in carrier_screws())))
    sw = n["sign switch body"].val().BoundingBox()
    print("sign switch's lugs to the floor: %.1f mm" % (sw.zmin - WALL))
    # the body as it prints, on its back: flat faces that lean more than 45 degrees past upright and aren't
    # on the bed need support
    bed = min(p.dot(UP) for p in (v.Center() for v in body.val().Vertices()))
    over = []
    for f in body.val().Faces():
        if f.geomType() != "PLANE" or f.Area() < 2:
            continue
        lean = f.normalAt().dot(UP)
        if lean < -math.cos(math.radians(45)) - 0.01 and f.Center().dot(UP) - bed > 0.5:
            over.append((f.Area(), math.degrees(math.acos(-lean)), f.Center()))
    print("overhangs past 45 degrees as the body prints: %d" % len(over))
    for a, ang, c in sorted(over, key=lambda t: -t[0]):
        print("  %6.1f mm2, %2.0f degrees from flat-down, at x %.0f y %.0f z %.0f" % (a, ang, c.x, c.y, c.z))
    return bad


def main():
    os.makedirs(OUT, exist_ok=True)
    screen_png = sys.argv[1] if len(sys.argv) > 1 else None
    body, plate = body_and_plate()
    carrier, spacers = carrier_and_spacers()
    lock = plug_lock()
    parts = stand_ins()
    checks(body, plate, parts, carrier, spacers, lock)
    # the body as it prints: on its back. Turn the back onto the bed.
    turned = body.rotate((0, 0, 0), (1, 0, 0), -(180 - A_B))
    bb = turned.val().BoundingBox()
    turned = turned.translate((0, 0, -bb.zmin))
    cq.exporters.export(turned, os.path.join(OUT, "prism_body.stl"), tolerance=0.05, angularTolerance=0.2)
    flat = plate.rotate((0, 0, 0), (1, 0, 0), 180 - A_F)      # face down
    flat = flat.translate((0, 0, -flat.val().BoundingBox().zmin))
    cq.exporters.export(flat, os.path.join(OUT, "prism_plate.stl"), tolerance=0.05, angularTolerance=0.2)
    t = lock.translate((0, 0, -lock.val().BoundingBox().zmin))   # the lock prints as it sits
    cq.exporters.export(t, os.path.join(OUT, "prism_plug_lock.stl"), tolerance=0.02, angularTolerance=0.1)
    for part, name in ((carrier, "prism_carrier.stl"), (spacers, "prism_spacers.stl")):
        t = part.rotate((0, 0, 0), (1, 0, 0), 180 - A_F)    # as the plate: its front down, the Pico's posts up
        t = t.translate((0, 0, -t.val().BoundingBox().zmin))
        cq.exporters.export(t, os.path.join(OUT, name), tolerance=0.05, angularTolerance=0.2)
    print("body prints %.0f x %.0f x %.0f mm; plate %.0f x %.0f x %.1f mm" % (bb.xlen, bb.ylen, bb.zlen,
          flat.val().BoundingBox().xlen, flat.val().BoundingBox().ylen, flat.val().BoundingBox().zlen))
    asm = cq.Assembly(name="pico_sign_prism")
    asm.add(body, name="body", color=cq.Color(0.20, 0.21, 0.23))
    asm.add(plate, name="plate", color=cq.Color(0.74, 0.73, 0.70))
    asm.add(carrier, name="carrier", color=cq.Color(0.35, 0.36, 0.40))
    asm.add(spacers, name="spacers", color=cq.Color(0.90, 0.60, 0.20))
    asm.add(lock, name="plug_lock", color=cq.Color(0.90, 0.60, 0.20))
    for sh, c, n in parts:
        asm.add(sh, name=n.replace(" ", "_").replace("(", "").replace(")", ""), color=cq.Color(*c))
    asm.save(os.path.join(OUT, "prism_assembly.step"))

    corners = [world(SCREEN_UV[0] + SCREEN_DX + sx * SCREEN_ACTIVE[0] / 2, SCREEN_UV[1] + sy * SCREEN_ACTIVE[1] / 2, -PLATE - GLASS_GAP - 0.01)
               for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1))]
    keep = ("screen glass", "sign switch", "knob", "knob mark", "cartridge top", "cartridge bottom", "ATECC608")
    shown = [(sh, c, n) for sh, c, n in parts if n in keep]
    closed = [(body, K.DARK, "body"), (plate, (0.74, 0.73, 0.70), "plate")] + shown
    K.render(dict(title="The prism", parts=closed, corners=corners,
                  views=[("front", 22, -58), ("from the right: the key on its plug", 30, 20)]),
             os.path.join(OUT, "prism_front.png"), screen_png)
    on_plate = ("screen", "sign", "knob", "EC11")
    inside = [(body, K.DARK, "body")] + [(sh, c, n) for sh, c, n in parts if not n.startswith(on_plate)]
    K.render(dict(title="The body, open", parts=inside, corners=[],
                  views=[("inserts, the Pico, the key's plug", 42, -78), ("the chamfered blocks, from inside", 10, -30)]),
             os.path.join(OUT, "prism_body.png"))
    near = cq.Workplane("XY").box(40, 40, 40).translate((KEY_X, KEY_Y - 8, H - 14))
    plug = [(sh, c, n) for sh, c, n in parts if n in ("plug overmold", "plug shell")]
    K.render(dict(title="The key's plug: in from the front, up into the top, the lock under it", corners=[],
                  parts=[(body.intersect(near), K.DARK, "body"), (lock, (0.90, 0.60, 0.20), "plug lock")] + plug,
                  views=[("from the front, below", -15, -70), ("from the front, right", -15, -110)]),
             os.path.join(OUT, "prism_plug.png"))
    K.render(dict(title="The body as it prints: on its back, the front's opening up", parts=[(turned, K.DARK, "body")],
                  corners=[], views=[("from the left", 15, -150), ("from above", 60, -120)]),
             os.path.join(OUT, "prism_print.png"))
    front = [(plate, (0.74, 0.73, 0.70), "plate")] + [(sh, c, n) for sh, c, n in parts if n.startswith(on_plate)
                                                       and n not in ("screen board", "screen header and wires")]   # they draw through the glass
    K.render(dict(title="The plate", parts=front, corners=corners,
                  views=[("front", 12, -75), ("back: the screen's posts, the switch's ring", 10, 105)]),
             os.path.join(OUT, "prism_plate.png"), screen_png)
    back = [(plate, (0.74, 0.73, 0.70), "plate"), (carrier, (0.35, 0.36, 0.40), "carrier"),
            (spacers, (0.90, 0.60, 0.20), "spacers")] + \
        [(sh, c, n) for sh, c, n in parts if n in ("screen board", "Pico 2 W", "carrier screws")]
    K.render(dict(title="Behind the plate: the screen, the carrier, the Pico", parts=back, corners=[],
                  views=[("from behind", 15, 110), ("from the side", 5, 175)]),
             os.path.join(OUT, "prism_carrier.png"))
    bare = [(plate, (0.74, 0.73, 0.70), "plate")]
    K.render(dict(title="The plate's back: posts and pins, the carrier's bosses", parts=bare, corners=[],
                  views=[("from behind", 25, 110), ("close, from below", 8, 150)]),
             os.path.join(OUT, "prism_plate_back.png"))
    for f in sorted(os.listdir(OUT)):
        print("wrote", os.path.join("hardware/builds/pico-sign/case/out/prism", f))


if __name__ == "__main__":
    main()
