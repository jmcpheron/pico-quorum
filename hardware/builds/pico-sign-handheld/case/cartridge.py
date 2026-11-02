"""The key's cartridge: a key-c in two printed halves that snap together, each printed flat on its
outside face. It slides down into a bay in the back of the handheld (handheld.py), as a game cartridge
does, its plug end first, onto a USB-C plug standing at the bay's foot.

The tray (the back half, its outside the label side) holds the board in a pocket, a peg up through its
lanyard hole (H1), so it can't slide either way. The cover (the front half, toward the screen when it's
in) comes down on it: a boss round the peg and a rim round the board press the board flat, and four
clips on the tray, two each side, snap into windows in the cover's sides. Push the clips in through the
windows to open it.

It is wider than the board, 48 x 54 x 7.56 mm, so it reads as a cartridge and has room for a label:
- a tongue down each side of the tray, which runs in a groove in the bay's side wall. The grooves guide
  it and hold it in the bay, so the USB-C plug is never the guide
- a notch in one bottom corner, round a rib in the bay. In the wrong way round, it stops on the rib
  (upside down) or can't start down the grooves (back to front), well before it reaches the plug
- a dimple in each side of the cover, where a bump in the bay clicks when it's all the way in
- the top 8 mm stand out of the case: grip grooves across both faces, a cut corner, a lanyard hole
- a frame on the back for a label

Run by handheld.py, which writes out/cartridge_tray.stl, out/cartridge_cover.stl and
out/cartridge.png. Alone: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign-handheld/case/cartridge.py

key-c's numbers are its board's (key-c-usbc.kicad_pcb, key-c-usbc/3d/print_mockup.py): 16 x 36 x 1.6,
2 mm corners, H1 3 mm at 14 mm from the centre; J1's shell tabs through the board at x +-4.32, 2.6 and
6.8 mm in from the USB edge. The receptacle's front is taken to be flush with the board's edge: not
measured. The clips' numbers are not tried: print one pair first. All dimensions mm.

Frame: x across, y from the plug end (0) to the grip end, z through, 0 at the board's back. Seen from
the front (the cover), the notch is at the bottom left and the cut corner at the top right.
"""
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "pico-sign", "case"))
import concepts as K        # the wall thicknesses and the pictures

CART = (48.0, 54.0)                 # outside: across, long. About a game cartridge's shape, at key-c's thickness
PROUD = 8.0                         # how far its top stands out of the case's top edge when it's in
WALL_B, WALL_T = K.WALL_B, K.WALL_T  # 1.2 under the board and over the receptacle
CART_T = K.CART_T                   # 7.56
CORNER_R = 2.5
KEY_CORNER = 8.0                    # the cut corner at the top right: a square this size turned 45 degrees
NOTCH = (3.0, 12.0)                 # the bottom left corner cut away: across, up. Longer than the plug's shell stands up
TONGUE = (1.2, -0.2)                # the tongues: how far out of the side, where they start (to the tray's top, Z0)
DETENT = (40.0, 0.6, 0.9)           # the dimples: up from the plug end; their centre out from the side; radius
GRIP = (3, 1.2, 0.6, 2.2)           # grip grooves across both faces near the top: how many, wide, deep, apart
LABEL = (38.0, 28.0, 13.0, 0.6, 0.4)  # the label's frame on the back: across, tall, its bottom from the plug end; line, deep
# key-c, in this frame (its own: origin the board's centre, the USB end at -y; here y + 18)
BOARD = (16.0, 36.0, 1.6)
BOARD_R = 2.0
H1 = (0.0, 32.0, 3.0)               # the lanyard hole: x, y, diameter
REC = (8.94, 7.8, 3.26)             # the receptacle: across, deep from the board's edge, tall
TABS = (4.32, 2.6, 6.8, 1.0)        # J1's shell tabs through the board: x +-, from y to y, how far they stand out the back
BODIES = [("U1 ATECC608", 0.00, 20.675, 4.90, 3.90, 1.75), ("U2 USBLC6", 0.00, 12.5, 2.90, 1.60, 1.45),
          ("C1", 3.75, 18.2, 1.00, 0.50, 0.50), ("C2", 0.00, 15.5, 0.50, 1.00, 0.50),
          ("R1", -2.40, 10.4, 0.50, 1.00, 0.35), ("R2", 2.15, 10.0, 0.50, 1.00, 0.35)]
Z0 = BOARD[2]                       # the parting plane: the board's front face

# the tray
POCKET_CLEAR = 0.15                 # round the board in its pocket
PEG_D, PEG_UP = 2.7, 1.0            # through H1 (3.0), and this far on into the cover's boss
TAB_RELIEF = (11.0, 9.0, 1.0)       # under the receptacle, for its tabs: across, from the edge, deep
# the clips: arms standing up from the tray near its sides, a hook on each, into a window in the cover's side
CLIP_Y = (16.0, 32.0)               # their centres: clear of the notch and the dimples
CLIP_W, CLIP_T = 5.0, 0.8           # each arm: along y, thick
HOOK = 0.35                         # how far the hook stands out
CLIP_GAP = 0.2                      # round the arm in its slot (y), and its relief
CLIP_X = CART[0] / 2 - 1.0 - CLIP_GAP - HOOK - CLIP_T     # the arm's inner face: 1 mm of tray outside its relief
CLIP_TOP = Z0 + 4.0                 # 5.6
CLIP_ROOT = -0.8                    # the arm is free from here up: a relief round it in the tray
CATCH = Z0 + 2.6                    # the hook's flat underside, on the cover's ledge
# the cover
RIM = 1.0                           # the cover presses the board's edge this wide
BOSS_D = 5.0                        # round the peg, presses the board round H1
CAVITY_H = 2.2                      # over the board's parts (U1 1.75)
REC_CLEAR = 0.25
REC_POCKET_W = 2 * 5.2              # over the receptacle and its tabs
WINDOW = 7.0, 6.0                   # over U1, to see the chip
LANYARD = (-(CART[0] / 2 - 4.5), CART[1] - 4.5, 3.6)


def outline(z0, z1):
    """The cartridge's outline from z0 to z1: rounded corners, the cut corner at the top right, the notch
    at the bottom left."""
    w, l = CART
    b = cq.Workplane("XY").box(w, l, z1 - z0, centered=(True, False, False)).translate((0, 0, z0)).edges("|Z").fillet(CORNER_R)
    b = b.cut(cq.Workplane("XY").box(KEY_CORNER, KEY_CORNER, 40).rotate((0, 0, 0), (0, 0, 1), 45).translate((w / 2, l, 0)))
    return b.cut(notch())


def notch():
    w = CART[0]
    nw, nl = NOTCH
    return cq.Workplane("XY").box(nw + 5, nl + 1, 40, centered=False).translate((-w / 2 - 5, -1, -20))


def board_shape(clear=0.0, z0=0.0, z1=BOARD[2]):
    w, l, _ = BOARD
    return cq.Workplane("XY").box(w + 2 * clear, l + 2 * clear, z1 - z0, centered=(True, False, False)) \
        .translate((0, -clear, z0)).edges("|Z").fillet(BOARD_R + clear)


def hook_profile(s):
    """The arm and its hook seen end on, on side s (+1 right): a polygon in (x, z)."""
    xi, xo = CLIP_X, CLIP_X + CLIP_T
    pts = [(xi, CLIP_ROOT), (xo, CLIP_ROOT), (xo, CATCH), (xo + HOOK, CATCH), (xo + HOOK, CATCH + 0.4),
           (xo, CLIP_TOP), (xi, CLIP_TOP)]
    return [(s * x, z) for x, z in pts]


def grip(z_face, into):
    """The grip grooves across a face at z_face, cut into (+1 up, -1 down) it, in the part that stands out."""
    n, gw, gd, gap = GRIP
    w, l = CART
    g = None
    for i in range(n):
        y = l - 2.0 - i * gap - gw
        b = cq.Workplane("XY").box(w - 14, gw, gd + 0.01, centered=(True, False, False)) \
            .translate((0, y, z_face - 0.01 if into > 0 else z_face - gd))
        g = b if g is None else g.union(b)
    return g


def dimples(z0, z1):
    """The detent's dimples in the cartridge's sides, from z0 to z1."""
    y, dx, r = DETENT
    w = CART[0]
    return cq.Workplane("XY").pushPoints([(-(w / 2 + dx), y), (w / 2 + dx, y)]).circle(r).extrude(z1 - z0).translate((0, 0, z0))


def tray():
    w, l = CART
    t = outline(-WALL_B, Z0)
    # the tongues, down each side, stopping at the case's top edge
    tw, tz = TONGUE
    for s in (-1, 1):
        t = t.union(cq.Workplane("XY").box(tw + 1, l - PROUD, Z0 - tz, centered=False)
                    .translate((w / 2 - 1 if s > 0 else -w / 2 - tw, 0, tz)))
    t = t.cut(notch())
    t = t.cut(board_shape(POCKET_CLEAR, 0.0, Z0 + 1).translate((0, -1, 0)).union(board_shape(POCKET_CLEAR, 0.0, Z0 + 1)))
    rw, rl, rd = TAB_RELIEF
    t = t.cut(cq.Workplane("XY").box(rw, rl + 1, rd + 0.01, centered=(True, False, False)).translate((0, -1, -rd)))
    t = t.union(cq.Workplane("XY").center(H1[0], H1[1]).circle(PEG_D / 2).extrude(Z0 + PEG_UP - 0.4)
                .faces(">Z").workplane().circle(PEG_D / 2).workplane(offset=0.4).circle(PEG_D / 2 - 0.4).loft())
    for y in CLIP_Y:
        for s in (-1, 1):
            # free the arm: a relief round it, down to CLIP_ROOT
            x0 = CLIP_X - 0.4 if s > 0 else -(CLIP_X + CLIP_T + HOOK + CLIP_GAP)
            x1 = CLIP_X + CLIP_T + HOOK + CLIP_GAP if s > 0 else -(CLIP_X - 0.4)
            t = t.cut(cq.Workplane("XY").box(x1 - x0, CLIP_W + 2 * CLIP_GAP, Z0 - CLIP_ROOT + 1, centered=False)
                      .translate((x0, y - CLIP_W / 2 - CLIP_GAP, CLIP_ROOT)))
            arm = cq.Workplane("XZ").polyline(hook_profile(s)).close().extrude(-CLIP_W).translate((0, y - CLIP_W / 2, 0))
            t = t.union(arm.union(cq.Workplane("XY").box(CLIP_T, CLIP_W, CLIP_ROOT + WALL_B, centered=False)
                                  .translate((CLIP_X if s > 0 else -CLIP_X - CLIP_T, y - CLIP_W / 2, -WALL_B))))
    # the back: the label's frame, a groove line round it; the grip grooves
    lw, lh, ly, line, deep = LABEL
    frame = cq.Workplane("XY").center(0, ly + lh / 2).rect(lw, lh).extrude(deep + 0.01).cut(
        cq.Workplane("XY").center(0, ly + lh / 2).rect(lw - 2 * line, lh - 2 * line).extrude(deep + 0.01))
    t = t.cut(frame.translate((0, 0, -WALL_B - 0.01)))
    t = t.cut(grip(-WALL_B, 1))
    return t.cut(lanyard())


def cover():
    c = outline(Z0, CART_T - WALL_B)
    w, l, _ = BOARD
    # over the parts, inside the rim; over the receptacle, open at the plug end
    c = c.cut(cq.Workplane("XY").box(w - 2 * RIM, l - REC[1] - 0.3 - RIM, CAVITY_H, centered=(True, False, False))
              .translate((0, REC[1] + 0.3, Z0 - 0.01)))
    c = c.cut(cq.Workplane("XY").box(REC_POCKET_W, REC[1] + 0.3 + 1, REC[2] + REC_CLEAR + 0.01, centered=(True, False, False))
              .translate((0, -1, Z0 - 0.01)))
    c = c.union(cq.Workplane("XY").center(H1[0], H1[1]).circle(BOSS_D / 2).extrude(CAVITY_H).translate((0, 0, Z0)))
    c = c.cut(cq.Workplane("XY").center(H1[0], H1[1]).circle(H1[2] / 2).extrude(PEG_UP + 0.3).translate((0, 0, Z0 - 0.01)))
    u1 = BODIES[0]
    c = c.cut(cq.Workplane("XY").center(u1[1], u1[2]).rect(*WINDOW).extrude(20))
    for y in CLIP_Y:
        for s in (-1, 1):
            # the arm's slot, room for it to flex in; the window above the ledge, through the side
            xi, xo = CLIP_X - 0.5, CLIP_X + CLIP_T + 0.1
            x0, x1 = (xi, xo) if s > 0 else (-xo, -xi)
            c = c.cut(cq.Workplane("XY").box(x1 - x0, CLIP_W + 2 * CLIP_GAP, CLIP_TOP + 0.3 - Z0 + 0.01, centered=False)
                      .translate((x0, y - CLIP_W / 2 - CLIP_GAP, Z0 - 0.01)))
            x0, x1 = (xi, CART[0]) if s > 0 else (-CART[0], -xi)
            c = c.cut(cq.Workplane("XY").box(x1 - x0, CLIP_W + 2 * CLIP_GAP, CLIP_TOP + 0.3 - CATCH, centered=False)
                      .translate((x0, y - CLIP_W / 2 - CLIP_GAP, CATCH)))
    c = c.cut(dimples(Z0 - 0.01, CART_T - WALL_B + 0.01))
    c = c.cut(grip(CART_T - WALL_B, -1))
    return c.cut(lanyard())


def lanyard():
    x, y, d = LANYARD
    return cq.Workplane("XY").center(x, y).circle(d / 2).extrude(40, both=True)


def key_c():
    """key-c as blocks, in this frame: the board with H1, the receptacle, its tabs, the parts."""
    b = board_shape().cut(cq.Workplane("XY").center(H1[0], H1[1]).circle(H1[2] / 2).extrude(5, both=True))
    b = b.union(cq.Workplane("XY").box(REC[0], REC[1], REC[2], centered=(True, False, False)).translate((0, 0, Z0)))
    tx, ty0, ty1, tz = TABS
    for s in (-1, 1):
        b = b.union(cq.Workplane("XY").box(1.0, ty1 - ty0, tz, centered=(True, False, False)).translate((s * tx, ty0, -tz)))
    for _, x, y, sx, sy, h in BODIES[1:]:
        b = b.union(cq.Workplane("XY").box(sx, sy, h, centered=(True, True, False)).translate((x, y, Z0)))
    u1 = BODIES[0]
    chip = cq.Workplane("XY").box(u1[3], u1[4], u1[5], centered=(True, True, False)).translate((u1[1], u1[2], Z0))
    return b, chip


def clamshell():
    """(cover, tray, key-c, chip), closed, in the cartridge's frame: what handheld.py puts in its bay."""
    board, chip = key_c()
    return cover(), tray(), board, chip


def checks():
    top, bottom, board, chip = clamshell()
    bad = 0
    for a, an in ((board, "key-c"), (chip, "U1")):
        for b, bn in ((top, "cover"), (bottom, "tray")):
            v = a.intersect(b).val().Volume()
            if v > 0.01:
                bad += 1
                print("  OVERLAP %s %s %.2f mm3" % (an, bn, v))
    v = top.intersect(bottom).val().Volume()
    if v > 0.01:
        bad += 1
        print("  OVERLAP cover tray %.2f mm3" % v)
    print("the key's cartridge: %.0f x %.0f x %.2f mm, %d overlaps; U1 to the cover %.2f mm. The board's %.1f mm fills its "
          "pocket, so the cover's rim and boss press it flat; the peg is %.1f mm in its %.1f mm hole" % (
              CART[0], CART[1], CART_T, bad, chip.val().distance(top.val()), BOARD[2], PEG_D, H1[2]))
    t = CLIP_T
    L = CATCH - CLIP_ROOT
    print("the clips: hooks %.2f mm onto a %.1f mm ledge; arms %.1f thick, %.1f long to the hook: %.1f%% strain "
          "to snap in (about 1.5 t d / L^2; PLA takes about 2%%); %.1f mm of tray outside each relief" % (
              HOOK - 0.1, CATCH - Z0, t, L, 100 * 1.5 * t * HOOK / L ** 2, CART[0] / 2 - (CLIP_X + CLIP_T + HOOK + CLIP_GAP)))
    # what's left where things are cut into the faces
    print("under the label's frame %.1f mm of tray, under its grip grooves %.1f mm" % (WALL_B - LABEL[4], WALL_B - GRIP[2]))
    return bad


def picture(path):
    top, bottom, board, chip = clamshell()
    up = lambda s, dz: cq.Workplane().add(s.val().moved(cq.Location(cq.Vector(0, 0, dz))))
    blue, black = (0.10, 0.25, 0.60), (0.08, 0.08, 0.09)
    K.render(dict(title="The key's cartridge", corners=[],
                  views=[("apart: the cover, key-c, the tray with its clips and tongues", 32, -58)],
                  parts=[(up(top, 16), K.AMBER, "cover"), (up(board, 7), blue, "key-c"), (up(chip, 7), black, "U1"),
                         (bottom, K.AMBER_D, "tray")]), path + ".a.png")
    K.render(dict(title="The key's cartridge", corners=[],
                  views=[("shut, the front: the chip's window", 40, -120), ("the back: the label's frame, the grip", -40, -60)],
                  parts=[(top, K.AMBER, "cover"), (bottom, K.AMBER_D, "tray"), (board, blue, "key-c"), (chip, black, "U1")]),
             path + ".b.png")
    from PIL import Image
    a, b = Image.open(path + ".a.png"), Image.open(path + ".b.png")
    s = Image.new("RGB", (a.width + b.width, a.height), (240, 239, 242))
    s.paste(a, (0, 0)); s.paste(b, (a.width, 0)); s.save(path)
    os.remove(path + ".a.png"); os.remove(path + ".b.png")


def write(out):
    """The two halves to print, each on its outside face, and the picture."""
    top, bottom, _, _ = clamshell()
    flip = top.rotate((0, 0, 0), (1, 0, 0), 180)
    for s, name in ((flip, "cartridge_cover.stl"), (bottom, "cartridge_tray.stl")):
        if not s.val().isValid():  # an invalid solid meshes with holes
            raise SystemExit("cartridge: %s is not a valid solid" % name)
        cq.exporters.export(s.translate((0, 0, -s.val().BoundingBox().zmin)), os.path.join(out, name),
                            tolerance=0.02, angularTolerance=0.1)
    picture(os.path.join(out, "cartridge.png"))


if __name__ == "__main__":
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    bad = checks()
    write(out)
    sys.exit(1 if bad else 0)
