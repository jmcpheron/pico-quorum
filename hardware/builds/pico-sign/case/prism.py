"""pico-sign's case: the prism. A triangular body, printed in one piece, open at the front, and a
front plate that holds everything you touch or read: the 2.8" screen on the left; on the right the
sign switch on top (HOLD TO SIGN) and the knob under it. The plate fixes with four M3 screws into
heat-set inserts. The key, in its cartridge (concepts.py), lies flat in a tray sunk into the top,
its chip window up, 2.4 mm below the surface; the console's USB-C plug is held in a cradle under the
top, at the tray's end. The Pico lies on posts on the floor, its USB out of the left side.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign/case/prism.py [screen.png]

Writes out/prism/: prism_body.stl (front down, as it prints), prism_plate.stl (face down),
prism_assembly.step, and prism_*.png (the screen PNG warped onto the panel if one is given).

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
BAND = 34.0                 # the flat top, front to back: the key's tray is in it
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
SCREEN_PCB = (86.0, 50.0)           # placeholder: an 86 x 50 board, the 8-pin header on its left
SCREEN_HOLES = (80.0, 44.0)         # M3 holes, 3 mm in from each corner
SCREEN_GLASS = (69.2, 50.0, 2.3)    # a 2.8" 240x320 IPS panel's outline
SCREEN_ACTIVE = (57.6, 43.2)        # its active area, landscape
SCREEN_DX = 6.0                     # the glass right of the board's centre: the header is on the left
SCREEN_UV = (57.0, 50.0)            # the board's centre on the plate
CTRL_U = 140.0                      # the controls' column
SIGN_V, KNOB_V = 62.0, 30.0         # the sign switch on top, the knob under it
SIGN_HOLE, SIGN_RING, SIGN_RING_T = 12.2, 26.0, 2.0     # a 12 mm metal push switch; a thicker ring: it's pressed hard
SIGN_BODY, SIGN_DEPTH = 17.5, 28.0                      # its body and lugs behind the plate
KNOB_HOLE = 7.2                                         # EC11, M7 bushing
LABEL = "HOLD TO SIGN"
SCREWS = [(11.0, 15.0), (W - 11.0, 15.0), (11.0, LP - 9.0), (W - 11.0, LP - 9.0)]   # the bottom two above the channel
INSERT_D, INSERT_L, BOSS_L = 4.0, 6.0, 12.0             # M3 heat-set inserts: 4.0 mm holes
SCREW_D, CSK_D = 3.4, 6.6

# --- the key tray, in the top band --------------------------------------------------------------------
TRAY_SINK = 2.4                     # the cartridge's top this far under the band: the plug then clears the band
TRAY_CLEAR = 0.3                    # round the cartridge
TRAY_Y = (P1[0] + P2[0]) / 2        # the tray's centre line, front to back
TRAY_X1 = W - 12.0                  # its grip end
TRAY_LEN = K.CART[1] + TRAY_CLEAR
TRAY_X0 = TRAY_X1 - TRAY_LEN        # its plug end
TRAY_DEPTH = K.CART_T + 0.15 + TRAY_SINK
# the plug of a cut USB-C cable (the Feather pigtail's calipers), its face at the tray's end
PLUG_W, PLUG_H, PLUG_L = 12.4, 5.5, 17.1
SHELL_W, SHELL_H, SHELL_L = 8.25, 2.4, 6.5
PLUG_Z = H - TRAY_DEPTH + 0.15 + K.WALL_B + K.KEYC[2] + K.REC[1] / 2   # the plug's axis = the receptacle's

# --- the Pico on the floor ----------------------------------------------------------------------------
PICO = (51.0, 21.0, 1.0)
PICO_X0 = WALL + 1.5                # its USB end, at the left wall
PICO_Y = 75.0
PICO_UP, PICO_TOP = 5.0, 22.0       # standoffs; headers and Dupont housings above the board
PICO_HOLES = [(2.0, -5.7), (2.0, 5.7), (49.0, -5.7), (49.0, 5.7)]


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
    # the accent channel, round all four faces, plate included
    band = full.intersect(slab_z(ACCENT_Z, ACCENT_Z + ACCENT_H)).cut(prism(ACCENT_D))
    body, plate = body.cut(band), plate.cut(band)

    # the plate's corner blocks, from the side walls, each with a heat-set insert
    for u, v in SCREWS:
        u0, u1 = (WALL - 0.5, u + 4.5) if u < W / 2 else (u - 4.5, W - WALL + 0.5)
        blk = pw(-PLATE).center((u0 + u1) / 2, v).rect(u1 - u0, 9).extrude(-BOSS_L)
        body = body.union(blk.intersect(prism()))
        body = body.cut(pw(-PLATE + 0.01).center(u, v).circle(INSERT_D / 2).extrude(-INSERT_L - 1))
        plate = plate.cut(pw(1).center(u, v).circle(SCREW_D / 2).extrude(-(PLATE + 2)))
        plate = plate.cut(pw(0).center(u, v).circle(CSK_D / 2).workplane(offset=-(CSK_D - SCREW_D) / 2)
                          .circle(SCREW_D / 2).loft())

    # the plate: the screen's window and posts, the switch, the knob, the words
    su, sv = SCREEN_UV
    gu = su + SCREEN_DX
    aw, ah = SCREEN_ACTIVE
    plate = plate.cut(pw(0).center(gu, sv).rect(aw + 6, ah + 6).workplane(offset=-2).rect(aw + 2, ah + 2).loft())
    plate = plate.cut(pw(1).center(gu, sv).rect(aw + 2, ah + 2).extrude(-(PLATE + 2)))
    hu, hv = SCREEN_HOLES
    gt = SCREEN_GLASS[2]
    for sx in (-1, 1):
        for sy in (-1, 1):
            post = pw(-PLATE).center(su + sx * hu / 2, sv + sy * hv / 2).circle(3.0).extrude(-gt)
            plate = plate.union(post).cut(pw(-PLATE + 0.5).center(su + sx * hu / 2, sv + sy * hv / 2)
                                          .circle(1.1).extrude(-gt - 1))           # M2.5 self-tapping
    plate = plate.union(pw(-PLATE).center(CTRL_U, SIGN_V).circle(SIGN_RING / 2).extrude(-SIGN_RING_T))
    for v, d in ((SIGN_V, SIGN_HOLE), (KNOB_V, KNOB_HOLE)):
        plate = plate.cut(pw(1).center(CTRL_U, v).circle(d / 2).extrude(-(PLATE + SIGN_RING_T + 2)))
    for txt, (u, v), size in [("PICOQUORUM", (su - 8, 19.5), 6.5), ("SEALED HARDWARE COSIGNER", (su - 8, 13.5), 3.2),
                              (LABEL, (CTRL_U, SIGN_V - 17), 4.0), ("TURN / PUSH", (CTRL_U, KNOB_V - 15), 3.2)]:
        plate = plate.cut(pw(0).center(u, v).text(txt, size, -0.6, combine=False, halign="center", valign="center"))

    # the key's tray, sunk into the band, and the plug's cradle under the band at its plug end
    zt = H - TRAY_DEPTH
    tw = K.CART[0] + 2 * TRAY_CLEAR
    body = body.union(cq.Workplane("XY").box(TRAY_LEN + 4, tw + 2 * WALL, TRAY_DEPTH + WALL, centered=False)
                      .translate((TRAY_X0 - 2, TRAY_Y - tw / 2 - WALL, zt - WALL)))
    cw = PLUG_W + 0.3 + 2 * 1.6
    cz0 = PLUG_Z - PLUG_H / 2 - 0.15 - 1.6
    body = body.union(cq.Workplane("XY").box(PLUG_L + 1.6, cw, H - cz0, centered=False)
                      .translate((TRAY_X0 - PLUG_L - 1.6, TRAY_Y - cw / 2, cz0)))
    body = body.cut(cq.Workplane("XY").box(TRAY_LEN, tw, TRAY_DEPTH + 1, centered=False)
                    .translate((TRAY_X0, TRAY_Y - tw / 2, zt)).edges("|Z").fillet(2.0))
    body = body.cut(cq.Workplane("XZ").center(TRAY_X1 - 6, H).circle(9).extrude(tw / 2 + 4, both=True)
                    .translate((0, TRAY_Y, 0)).intersect(cq.Workplane("XY").box(30, tw, 40).translate((TRAY_X1 - 6, TRAY_Y, H))))
    body = body.cut(cq.Workplane("XY").box(PLUG_L, PLUG_W + 0.3, PLUG_H + 0.3, centered=(False, True, True))
                    .translate((TRAY_X0 - PLUG_L, TRAY_Y, PLUG_Z)))           # the overmold's pocket, open at the tray
    body = body.cut(cq.Workplane("XY").box(3, 7, 4, centered=(False, True, True))
                    .translate((TRAY_X0 - PLUG_L - 2, TRAY_Y, PLUG_Z)))       # the cable out through the back stop
    body = body.cut(cq.Workplane("XY").workplane(offset=H - 0.6).center(TRAY_X0 - 10, TRAY_Y)
                    .text("KEY", 4.5, 1, combine=False, halign="center", valign="center"))

    # the Pico's posts, its USB through the left wall; rubber feet
    for dx, dy in PICO_HOLES:
        x, y = PICO_X0 + dx, PICO_Y + dy
        body = body.union(cq.Workplane("XY").circle(2.5).extrude(PICO_UP + WALL).translate((x, y, 0)))
        body = body.cut(cq.Workplane("XY").circle(0.9).extrude(PICO_UP).translate((x, y, WALL)))
    uz = WALL + PICO_UP + PICO[2] + 1.6
    body = body.cut(cq.Workplane("YZ").center(PICO_Y, uz).rect(12, 8).extrude(10).translate((-2, 0, 0)))
    for x in (14, W - 14):
        for y in (12, P3[0] - 14):
            body = body.cut(cq.Workplane("XY").circle(5.2).extrude(1.0).translate((x, y, 0)))
    return body, plate


# --- stand-ins, for the pictures, the STEP and the checks --------------------------------------------------
def stand_ins():
    s = []
    su, sv = SCREEN_UV
    gw, gh, gt = SCREEN_GLASS
    s.append((pw(-PLATE).center(su + SCREEN_DX, sv).rect(gw, gh).extrude(-gt), (0.05, 0.05, 0.06), "screen glass"))
    s.append((pw(-PLATE - gt).center(su, sv).rect(*SCREEN_PCB).extrude(-1.6), (0.10, 0.30, 0.55), "screen board"))
    s.append((pw(-PLATE - gt - 1.6).center(su - SCREEN_PCB[0] / 2 + 4, sv).rect(5, 21).extrude(-9), (0.1, 0.1, 0.1), "screen header and wires"))
    s.append((pw(0).center(CTRL_U, SIGN_V).polygon(6, 16).extrude(2.5).union(
        pw(2.5).center(CTRL_U, SIGN_V).circle(6).extrude(9)).union(pw(11.5).center(CTRL_U, SIGN_V).circle(6.3).extrude(1.5)),
        (0.78, 0.78, 0.80), "sign switch"))
    s.append((pw(-PLATE - SIGN_RING_T).center(CTRL_U, SIGN_V).rect(SIGN_BODY, SIGN_BODY).extrude(-SIGN_DEPTH),
              (0.25, 0.25, 0.28), "sign switch body"))
    s.append((pw(0).center(CTRL_U, KNOB_V).circle(9).extrude(15).faces(">Z").edges().fillet(1.5), (0.1, 0.1, 0.11), "knob"))
    s.append((pw(15).center(CTRL_U, KNOB_V).rect(0.8, 7).extrude(0.4), (0.9, 0.9, 0.9), "knob mark"))
    s.append((pw(-PLATE).center(CTRL_U, KNOB_V).rect(12, 12).extrude(-7), (0.25, 0.25, 0.28), "EC11 body"))
    s.append((cq.Workplane("XY").box(PLUG_L, PLUG_W, PLUG_H, centered=(False, True, True)).translate((TRAY_X0 - PLUG_L, TRAY_Y, PLUG_Z)),
              (0.15, 0.15, 0.15), "plug overmold"))
    s.append((cq.Workplane("YZ").slot2D(SHELL_W, SHELL_H).extrude(SHELL_L).translate((TRAY_X0, TRAY_Y, PLUG_Z)),
              (0.8, 0.8, 0.82), "plug shell"))
    # the cartridge in its tray: its y along -x into the plug, its top up
    o = (TRAY_X0 + TRAY_CLEAR / 2, TRAY_Y, H - TRAY_DEPTH + 0.15 + K.WALL_B)
    loc = cq.Location(cq.Plane(origin=o, xDir=(0, -1, 0), normal=(0, 0, 1)))
    top, bottom, board, chip = K.cartridge()
    s.append((cq.Workplane().add(top.val().moved(loc)), K.AMBER, "cartridge top"))
    s.append((cq.Workplane().add(bottom.val().moved(loc)), K.AMBER_D, "cartridge bottom"))
    s.append((cq.Workplane().add(board.val().moved(loc)), (0.10, 0.25, 0.60), "key-c"))
    s.append((cq.Workplane().add(chip.val().moved(loc)), (0.08, 0.08, 0.09), "ATECC608"))
    s.append((cq.Workplane("XY").box(PICO[0], PICO[1], PICO[2], centered=(False, True, False))
              .translate((PICO_X0, PICO_Y, WALL + PICO_UP)), (0.10, 0.42, 0.22), "Pico 2 W"))
    s.append((cq.Workplane("XY").box(PICO[0] - 4, PICO[1], PICO_TOP - PICO[2], centered=(False, True, False))
              .translate((PICO_X0 + 2, PICO_Y, WALL + PICO_UP + PICO[2])), (0.55, 0.55, 0.58), "headers and wires (space)"))
    return s


def checks(body, plate, parts):
    """Only that nothing obvious collides: the parts are boxes. Not a fit check."""
    n = {name: sh for sh, _, name in parts}
    inside = ["screen board", "screen header and wires", "sign switch body", "EC11 body", "plug overmold",
              "headers and wires (space)", "key-c", "cartridge top", "cartridge bottom"]
    pairs = [(a, "body", body) for a in inside] + [(a, "plate", plate) for a in inside if a not in ("plug overmold",)]
    pairs += [(a, b, n[b]) for i, a in enumerate(inside) for b in inside[i + 1:]
              if {a, b} not in ({"key-c", "cartridge top"}, {"key-c", "cartridge bottom"}, {"cartridge top", "cartridge bottom"})]
    bad = 0
    for a, bname, b in pairs:
        v = n[a].intersect(b).val().Volume()
        if v > 0.05:
            bad += 1
            print("  OVERLAP %-28s %-28s %.2f mm3" % (a, bname, v))
    print("checked %d pairs: %s" % (len(pairs), "clear" if not bad else "%d overlap" % bad))
    sw = n["sign switch body"].val().BoundingBox()
    print("sign switch's lugs to the floor: %.1f mm; plug's top under the band: %.2f mm" %
          (sw.zmin - WALL, (H - WALL) - (PLUG_Z + PLUG_H / 2)))
    return bad


def main():
    os.makedirs(OUT, exist_ok=True)
    screen_png = sys.argv[1] if len(sys.argv) > 1 else None
    body, plate = body_and_plate()
    parts = stand_ins()
    checks(body, plate, parts)
    # the body as it prints: front down. Turn the plate's plane onto the desk.
    turned = body.rotate((0, 0, 0), (1, 0, 0), 180 - A_F)
    bb = turned.val().BoundingBox()
    turned = turned.translate((0, 0, -bb.zmin))
    cq.exporters.export(turned, os.path.join(OUT, "prism_body.stl"), tolerance=0.05, angularTolerance=0.2)
    flat = plate.rotate((0, 0, 0), (1, 0, 0), 180 - A_F)      # face down
    flat = flat.translate((0, 0, -flat.val().BoundingBox().zmin))
    cq.exporters.export(flat, os.path.join(OUT, "prism_plate.stl"), tolerance=0.05, angularTolerance=0.2)
    print("body prints %.0f x %.0f x %.0f mm; plate %.0f x %.0f x %.1f mm" % (bb.xlen, bb.ylen, bb.zlen,
          flat.val().BoundingBox().xlen, flat.val().BoundingBox().ylen, flat.val().BoundingBox().zlen))
    asm = cq.Assembly(name="pico_sign_prism")
    asm.add(body, name="body", color=cq.Color(0.20, 0.21, 0.23))
    asm.add(plate, name="plate", color=cq.Color(0.74, 0.73, 0.70))
    for sh, c, n in parts:
        asm.add(sh, name=n.replace(" ", "_").replace("(", "").replace(")", ""), color=cq.Color(*c))
    asm.save(os.path.join(OUT, "prism_assembly.step"))

    corners = [world(SCREEN_UV[0] + SCREEN_DX + sx * SCREEN_ACTIVE[0] / 2, SCREEN_UV[1] + sy * SCREEN_ACTIVE[1] / 2, -PLATE - 0.01)
               for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1))]
    keep = ("screen glass", "sign switch", "knob", "knob mark", "cartridge top", "cartridge bottom", "ATECC608")
    shown = [(sh, c, n) for sh, c, n in parts if n in keep]
    closed = [(body, K.DARK, "body"), (plate, (0.74, 0.73, 0.70), "plate")] + shown
    K.render(dict(title="The prism", parts=closed, corners=corners,
                  views=[("front", 22, -58), ("from the right: the key's tray", 48, 20)]),
             os.path.join(OUT, "prism_front.png"), screen_png)
    on_plate = ("screen", "sign", "knob", "EC11")
    inside = [(body, K.DARK, "body")] + [(sh, c, n) for sh, c, n in parts if not n.startswith(on_plate)]
    K.render(dict(title="The body, open", parts=inside, corners=[],
                  views=[("inserts, the Pico, the plug's cradle", 42, -78), ("the tray and the cradle, from behind", 40, 130)]),
             os.path.join(OUT, "prism_body.png"))
    front = [(plate, (0.74, 0.73, 0.70), "plate")] + [(sh, c, n) for sh, c, n in parts if n.startswith(on_plate)
                                                       and n not in ("screen board", "screen header and wires")]   # they draw through the glass
    K.render(dict(title="The plate", parts=front, corners=corners,
                  views=[("front", 12, -75), ("back: the screen's posts, the switch's ring", 10, 105)]),
             os.path.join(OUT, "prism_plate.png"), screen_png)
    for f in sorted(os.listdir(OUT)):
        print("wrote", os.path.join("hardware/builds/pico-sign/case/out/prism", f))


if __name__ == "__main__":
    main()
