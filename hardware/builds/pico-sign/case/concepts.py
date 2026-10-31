"""Four case concepts for pico-sign with the 2.8" screen, and the key cartridge they share
(hardware/builds/pico-sign/case/CONCEPTS.md). Massing models to choose from, not designs to print:
the bodies are solid, nothing inside is placed, nothing is checked for fit. The cartridge is the
exception: it is drawn to the key-c's own numbers and is meant to be printed and tried.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign/case/concepts.py [screen.png]

Writes out/concepts/: <concept>.png (two views each, the screen PNG warped onto the panel if one is
given), cartridge.png (exploded), cartridge_top.stl and cartridge_bottom.stl (to print), and
concepts.step (every concept, for CAD).

The 2.8" module is console-pcb's placeholder (gen_console.py SCREEN): an 86 x 50 mm board, M3 holes
3 mm in from each corner, the header on the left. Its active area, 57.6 x 43.2 mm, is the panel's
(240 x 320 at 0.18 mm). Measure yours, or take the numbers from the earlier case, and change SCREEN_*.
All dimensions mm.
"""
import math
import os
import sys

import cadquery as cq

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "concepts")

# --- parts -----------------------------------------------------------------------------------------
SCREEN_PCB = (86.0, 50.0)           # placeholder until measured
SCREEN_HOLES = (80.0, 44.0)         # M3, 3 mm in
SCREEN_ACTIVE = (57.6, 43.2)        # 320 x 240 landscape
SCREEN_DX = 3.0                     # the active area's centre right of the board's: the header side is left
KNOB_CAP, SIGN_CAP = 9.0, 7.0       # radii of the knob and the sign switch's cap, for the pictures

# key-c (key-c-usbc/3d/print_mockup.py): 16 x 36 x 1.6, the receptacle on the parts side at the -y end
KEYC = (16.0, 36.0, 1.6)
REC = (8.94, 3.26, 7.8)             # the receptacle: across, tall, deep from the board's edge
U1_Y = 2.675                        # the ATECC608 from the board's centre, toward +y
# the cartridge: x across, y from its plug end (0) to its grip end, z through, 0 at the board's back
CART = (22.0, 46.0)                 # outside, across and long
WALL_B, WALL_T = 1.2, 1.2           # under the board and over the receptacle
CART_T = WALL_B + KEYC[2] + REC[1] + 0.3 + WALL_T   # 7.56
BOARD_Y0 = 0.0                      # the receptacle's face flush with the cartridge's end, so a plug mates fully
CLEAR = 0.2                         # round the board in its pocket


def cartridge():
    """The key cartridge: a top and a bottom half, split at the board's back face, that close round a
    key-c for good (glued, or two M2 screws). Its plug end is open to the receptacle; a window over
    the ATECC608 shows the chip; a recess takes a label; one rear corner is cut so it goes in one way
    up; a lanyard hole goes through the grip. Returns (top, bottom, board, chip) in its own frame."""
    w, l = CART
    zb = -WALL_B
    body = cq.Workplane("XY").box(w, l, CART_T, centered=(True, False, False)).translate((0, 0, zb)) \
        .edges("|Z").fillet(2.5)
    body = body.cut(cq.Workplane("XY").box(8, 8, 20).rotate((0, 0, 0), (0, 0, 1), 45).translate((w / 2, l, 0)))  # the key corner
    # the board's pocket and the receptacle's, and the opening at the plug end
    by0 = BOARD_Y0
    body = body.cut(cq.Workplane("XY").box(KEYC[0] + 2 * CLEAR, KEYC[1] + CLEAR, KEYC[2] + 0.1, centered=(True, False, False))
                    .translate((0, by0 - CLEAR, 0)))
    body = body.cut(cq.Workplane("XY").box(KEYC[0] - 1, KEYC[1] - 2, REC[1] + 0.3, centered=(True, False, False))
                    .translate((0, by0 + 1, KEYC[2])))                       # room for the parts on the board
    body = body.cut(cq.Workplane("XZ").center(0, KEYC[2] + REC[1] / 2).slot2D(REC[0] + 1.4, REC[1] + 1.2)
                    .extrude(-(by0 + REC[2])))                               # the plug goes in here
    body = body.cut(cq.Workplane("XY").center(0, by0 + KEYC[1] / 2 + U1_Y).rect(7, 6).extrude(20))   # the chip's window
    body = body.cut(cq.Workplane("XY").workplane(offset=CART_T + zb - 0.6).center(0, by0 + 29.5)
                    .rect(16, 9).extrude(1))                                 # the label
    body = body.cut(cq.Workplane("XY").center(-4, l - 4.5).circle(1.8).extrude(20, both=True))      # lanyard
    for sx in (-1, 1):                                                       # grip ridges
        for i in range(3):
            body = body.cut(cq.Workplane("XZ").center(sx * w / 2, CART_T / 2 + zb).rect(1.2, CART_T + 1)
                            .extrude(-1).translate((0, l - 13 + 3 * i, 0)))
    top = body.intersect(cq.Workplane("XY").box(100, 100, 50, centered=(True, True, False)))
    bottom = body.intersect(cq.Workplane("XY").box(100, 100, 50, centered=(True, True, False)).translate((0, 0, -50)))
    board = cq.Workplane("XY").box(KEYC[0], KEYC[1], KEYC[2], centered=(True, False, False)).translate((0, by0, 0)) \
        .union(cq.Workplane("XY").box(REC[0], REC[2], REC[1], centered=(True, False, False)).translate((0, by0, KEYC[2])))
    chip = cq.Workplane("XY").box(4.9, 3.9, 1.75, centered=(True, True, False)).translate((0, by0 + KEYC[1] / 2 + U1_Y, KEYC[2]))
    return top, bottom, board, chip


def cart_parts(loc, out=0.0):
    """The cartridge in a bay: loc is (origin, xDir, normal) of its frame; out pulls it back along its y."""
    o, xd, n = loc
    pl = cq.Plane(origin=o, xDir=xd, normal=n)
    move = cq.Location(pl) * cq.Location(cq.Vector(0, -out, 0))
    top, bottom, board, chip = CARTRIDGE
    return [(cq.Workplane().add(top.val().moved(move)), AMBER, "cartridge top"),
            (cq.Workplane().add(bottom.val().moved(move)), AMBER_D, "cartridge bottom"),
            (cq.Workplane().add(chip.val().moved(move)), (0.08, 0.08, 0.09), "the chip, through its window")]


# --- the screen on a panel --------------------------------------------------------------------------
def screen(pl, u, v):
    """The panel's glass in a window at (u, v) on plane pl (the face's top), and the active area's
    corners in the world, top left first, for the picture."""
    aw, ah = SCREEN_ACTIVE
    glass = cq.Workplane(pl).center(u, v).rect(aw + 2, ah + 2).extrude(-1.5)
    corners = [pl.toWorldCoords((u + sx * aw / 2, v + sy * ah / 2, -0.01)) for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1))]
    return glass, [c.toTuple() for c in corners]


def window_cut(pl, u, v):
    aw, ah = SCREEN_ACTIVE
    return cq.Workplane(pl).center(u, v).rect(aw + 6, ah + 6).workplane(offset=-2).rect(aw + 2, ah + 2).loft() \
        .union(cq.Workplane(pl).center(u, v).rect(aw + 2, ah + 2).extrude(-1.4))


def knob(pl, u, v):
    return cq.Workplane(pl).center(u, v).circle(KNOB_CAP).extrude(15).faces(">Z").edges().fillet(1.5)


def sign_switch(pl, u, v):
    return cq.Workplane(pl).center(u, v).polygon(6, 16).extrude(2.5).union(
        cq.Workplane(pl).center(u, v).workplane(offset=2.5).circle(SIGN_CAP).extrude(9))


DARK, MID, LIGHT = (0.20, 0.21, 0.23), (0.32, 0.33, 0.36), (0.86, 0.85, 0.82)
AMBER, AMBER_D = (0.95, 0.63, 0.15), (0.80, 0.50, 0.10)
BLACK, STEEL = (0.05, 0.05, 0.06), (0.78, 0.78, 0.80)
CARTRIDGE = None


def tilted(origin, from_vertical):
    """A plane through origin, its x across, facing forward (-y), leaned back from_vertical degrees
    (0: an upright face, 90: flat, facing up)."""
    a = math.radians(from_vertical)
    return cq.Plane(origin=origin, xDir=(1, 0, 0), normal=(0, -math.cos(a), math.sin(a)))


# --- the four ------------------------------------------------------------------------------------------
def wedge():
    """A: the wedge. A sloped desk box; the screen across the top half of the lid, the knob and the
    sign switch below it; the cartridge slides into the right-hand wall, flat, and sits flush."""
    W, L, HF, HB = 130.0, 150.0, 36.0, 60.0
    a = math.degrees(math.atan2(HB - HF, L))
    body = cq.Workplane("YZ").polyline([(0, 0), (L, 0), (L, HB), (0, HF)]).close().extrude(W).edges("|Z").fillet(7)
    top = tilted((0, 0, HF), 90 - a)
    lt = L / math.cos(math.radians(a))
    shell = body          # one piece in the pictures: a lid split off here draws badly in matplotlib
    su, sv = W / 2, lt - 46
    shell = shell.cut(window_cut(top, su, sv))
    glass, corners = screen(top, su, sv)
    shell = shell.cut(cq.Workplane("XY").box(60, CART[0] + 0.8, CART_T + 0.8, centered=(False, True, False))
                      .translate((W - 50, 62, 13 - WALL_B - 0.4)))
    shell = shell.cut(cq.Workplane("XZ").center(W, 13 + CART_T / 2).circle(6).extrude(30, both=True)
                      .intersect(cq.Workplane("XY").box(8, 60, 60).translate((W, 62, 13))))   # the finger notch
    parts = [(shell, DARK, "body"), (glass, BLACK, "screen"),
             (knob(top, W / 2 + 32, 46), BLACK, "knob"), (sign_switch(top, W / 2 - 26, 40), STEEL, "sign switch")]
    parts += cart_parts(((W - 43.0, 62.0, 13.0), (0, -1, 0), (0, 0, 1)))   # its grip 3 mm out of the wall
    return dict(name="A-wedge", title="A: the wedge", parts=parts, corners=corners,
                views=[("front", 30, -60), ("the key bay, right side", 18, -5)])


def terminal():
    """B: the terminal. A small upright body with the screen in its face, tilted back, over a deck
    with the knob and the sign switch; the cartridge slides into the deck's front, under the knob."""
    W, DD, DH, MD, MH, t = 140.0, 78.0, 38.0, 70.0, 112.0, 14.0
    deck = cq.Workplane("XY").box(W, DD + 10, DH, centered=False).edges("|Y").fillet(6)
    mon = cq.Workplane("XY").box(W, MD, MH, centered=False).translate((0, DD, 0)).edges("|Y").fillet(8)
    face = tilted((0, DD, DH + 4), t)
    mon = mon.cut(cq.Workplane(face).rect(1000, 1000).extrude(200))
    hood = cq.Workplane(face).center(W / 2, 40).rect(W - 10, 66).extrude(-4)
    mon = mon.cut(hood)
    su, sv = W / 2, 40
    inner = cq.Plane(origin=face.toWorldCoords((0, 0, -4)).toTuple(), xDir=(1, 0, 0), normal=face.zDir.toTuple())
    mon = mon.cut(window_cut(inner, su, sv))
    glass, corners = screen(inner, su, sv)
    deck_top = cq.Plane(origin=(0, 0, DH), xDir=(1, 0, 0), normal=(0, 0, 1))
    ky = 30.0
    deck = deck.cut(cq.Workplane("XY").box(CART[0] + 0.8, 60, CART_T + 0.8, centered=(True, False, False))
                    .translate((W - 36, -1, 9 - WALL_B - 0.4)))
    deck = deck.cut(cq.Workplane("XY").box(30, 3, 14, centered=(True, False, True)).translate((W - 36, -1, 9 + CART_T / 2)))
    parts = [(deck, MID, "deck"), (mon, DARK, "body"), (glass, BLACK, "screen"),
             (knob(deck_top, W - 36, ky + 8), BLACK, "knob"), (sign_switch(deck_top, 42, ky), STEEL, "sign switch")]
    parts += cart_parts(((W - 36, 46.0, 9.0), (-1, 0, 0), (0, 0, 1)), out=0)
    return dict(name="B-terminal", title="B: the terminal", parts=parts, corners=corners,
                views=[("front", 22, -62), ("the key slot, in the deck's front", 8, -20)])


def slab():
    """C: the slab. A leaning panel on a foot: the screen at the top, the knob and the sign switch
    under it. The cartridge lies in a compartment in its back, behind a sliding door."""
    W, L, T, a = 104.0, 156.0, 24.0, 26.0     # a: the panel's lean back from upright
    base = tilted((0, 18, 6), a)
    body = cq.Workplane(base).center(W / 2, L / 2).rect(W, L).extrude(T)
    body = body.edges(cq.selectors.ParallelDirSelector(base.zDir)).fillet(8)
    top = cq.Plane(origin=base.toWorldCoords((0, 0, T)).toTuple(), xDir=(1, 0, 0), normal=base.zDir.toTuple())
    su, sv = W / 2, L - 40
    body = body.cut(window_cut(top, su, sv))
    glass, corners = screen(top, su, sv)
    # the compartment, in the back face (the base plane, its normal into the panel)
    cu, cv = W / 2, 52.0
    body = body.cut(cq.Workplane(base).center(cu, cv).rect(CART[0] + 6, CART[1] + 14).extrude(CART_T + 2))
    door = cq.Workplane(base).center(cu + 18, cv).rect(CART[0] + 10, CART[1] + 18).extrude(-1.6)
    foot = cq.Workplane("XY").box(W - 20, 70, 8, centered=(True, False, False)).translate((W / 2, 0, 0)).edges("|Z").fillet(4)
    loc = (base.toWorldCoords((cu, cv - CART[1] / 2, WALL_B + 0.8)).toTuple(), (1, 0, 0), base.zDir.toTuple())
    parts = [(body, DARK, "panel"), (foot, MID, "foot"), (door, MID, "door, slid open"), (glass, BLACK, "screen"),
             (knob(top, W / 2 + 24, 44), BLACK, "knob"), (sign_switch(top, W / 2 - 24, 44), STEEL, "sign switch")]
    parts += cart_parts(loc)
    return dict(name="C-slab", title="C: the slab", parts=parts, corners=corners,
                views=[("front", 18, -58), ("from behind: the key door, open", 12, 140)])


def vault():
    """D: the vault. A heavy box: the screen in its sloped front, the sign switch on top under a
    flip-up guard, the knob beside it. The cartridge lies in a bay in the top under a hinged lid
    with a hole for a padlock or a numbered seal, so anyone can see if it has been opened."""
    W, D, H, t = 150.0, 120.0, 84.0, 24.0
    body = cq.Workplane("XY").box(W, D, H, centered=False).edges("|Y or |X").fillet(5)
    face = tilted((0, 0, 4), t)
    body = body.cut(cq.Workplane(face).rect(1000, 1000).extrude(300))
    su, sv = 56.0, 44.0
    body = body.cut(window_cut(face, su, sv))
    glass, corners = screen(face, su, sv)
    topp = cq.Plane(origin=(0, 0, H), xDir=(1, 0, 0), normal=(0, 0, 1))
    bx, by = 118.0, 70.0                        # the bay's centre
    body = body.cut(cq.Workplane("XY").box(CART[0] + 10, CART[1] + 10, CART_T + 3, centered=(True, True, False))
                    .translate((bx, by, H - CART_T - 3)))
    hinge_y = by + (CART[1] + 10) / 2
    lid = cq.Workplane("XY").box(CART[0] + 14, CART[1] + 14, 3, centered=(True, False, False)) \
        .translate((bx, hinge_y - CART[1] - 14, H)).rotate((0, hinge_y, H), (1, hinge_y, H), -70)
    hasp = cq.Workplane("XZ").center(bx, H - 6).rect(10, 12).extrude(3).faces(">Y").workplane() \
        .center(0, 0).hole(4).translate((0, by - (CART[1] + 10) / 2 - 3 - 1, 0))
    gx, gy = 40.0, 84.0
    guard = cq.Workplane("XY").box(30, 34, 16, centered=(True, False, False)).faces("<Z").shell(-2) \
        .translate((gx, gy - 17, H)).rotate((0, gy + 17, H), (1, gy + 17, H), -60)
    loc = ((bx, by - CART[1] / 2, H - CART_T - 3 + WALL_B + 0.6), (1, 0, 0), (0, 0, 1))
    parts = [(body, DARK, "body"), (glass, BLACK, "screen"), (lid, MID, "bay lid, open"), (hasp, STEEL, "hasp"),
             (guard, (0.75, 0.16, 0.14), "guard, flipped up"), (sign_switch(topp, gx, gy), STEEL, "sign switch"),
             (knob(topp, 82, 96), BLACK, "knob")]
    parts += cart_parts(loc)
    return dict(name="D-vault", title="D: the vault", parts=parts, corners=corners,
                views=[("front", 26, -52), ("the top: guard up, key bay open", 62, -110)])


# --- pictures --------------------------------------------------------------------------------------
def render(c, path, screen_png=None):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import proj3d
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from PIL import Image

    light = np.array([0.35, -0.55, 0.75]); light /= np.linalg.norm(light)
    tris = []
    for shape, color, _ in c["parts"]:
        for sol in shape.vals():
            vs, ts = sol.tessellate(0.2, 0.3)
            p = np.array([v.toTuple() for v in vs])
            for t in ts:
                tri = p[list(t)]
                n = np.cross(tri[1] - tri[0], tri[2] - tri[0]); nn = np.linalg.norm(n)
                if nn > 1e-9:
                    tris.append((tri, tuple(min(1, x * (0.35 + 0.65 * abs(np.dot(n / nn, light)))) for x in color)))
    allp = np.concatenate([t for t, _ in tris])
    lo, hi = allp.min(0), allp.max(0)
    ctr, r = (lo + hi) / 2, (hi - lo).max() / 2 * 0.9
    tiles = []
    for i, (title, elev, azim) in enumerate(c["views"]):
        fig = plt.figure(figsize=(7, 6), dpi=130)
        ax = fig.add_axes([0, 0, 1, 1], projection="3d")
        ax.add_collection3d(Poly3DCollection([t for t, _ in tris], facecolors=[k for _, k in tris], linewidths=0))
        ax.set_xlim(ctr[0] - r, ctr[0] + r); ax.set_ylim(ctr[1] - r, ctr[1] + r); ax.set_zlim(ctr[2] - r, ctr[2] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
        fig.patch.set_facecolor((0.94, 0.93, 0.95)); ax.set_facecolor((0.94, 0.93, 0.95))
        fig.canvas.draw()
        tmp = path + ".%d.png" % i
        fig.savefig(tmp, dpi=130)
        im = Image.open(tmp).convert("RGBA")
        if screen_png and i == 0:
            quad = []
            for p in c["corners"]:
                x2, y2, _ = proj3d.proj_transform(*p, ax.get_proj())
                dx, dy = ax.transData.transform((x2, y2))
                quad.append((dx, fig.bbox.height - dy))
            shot = Image.open(screen_png).convert("RGBA")
            shot = shot.resize((shot.width * 4, shot.height * 4), Image.NEAREST)
            src = [(0, 0), (shot.width, 0), (shot.width, shot.height), (0, shot.height)]
            a = []
            for (x, y), (u, v) in zip(quad, src):
                a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
            k = np.linalg.solve(np.array(a, float), np.array(src, float).reshape(8)).tolist()
            im.paste(shot.transform(im.size, Image.PERSPECTIVE, k, Image.BILINEAR), (0, 0),
                     Image.new("L", shot.size, 255).transform(im.size, Image.PERSPECTIVE, k, Image.BILINEAR))
        plt.close(fig)
        os.remove(tmp)
        tiles.append((title, im))
    w = sum(t.width for _, t in tiles)
    sheet = Image.new("RGB", (w, tiles[0][1].height + 40), (240, 239, 242))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    x = 0
    for title, t in tiles:
        sheet.paste(t, (x, 40))
        dr.text((x + 16, 12), (c["title"] + ": " + title) if x == 0 else title, fill=(20, 20, 24))
        x += t.width
    sheet.save(path)


def render_cartridge(path):
    top, bottom, board, chip = CARTRIDGE
    lift = cq.Location(cq.Vector(0, 0, 12))
    c = dict(title="The key cartridge", corners=[], views=[("exploded: top, the key-c, bottom", 34, -58), ("closed, the plug end", 14, -150)],
             parts=[(cq.Workplane().add(top.val().moved(cq.Location(cq.Vector(0, 0, 22)))), AMBER, "top"),
                    (cq.Workplane().add(board.val().moved(lift)), (0.10, 0.25, 0.60), "key-c"),
                    (cq.Workplane().add(chip.val().moved(lift)), BLACK, "ATECC608"),
                    (bottom, AMBER_D, "bottom")])
    render(c, path + ".a.png")
    c2 = dict(title="", corners=[], views=[("closed, the plug end", 14, -150)],
              parts=[(top, AMBER, "top"), (bottom, AMBER_D, "bottom"), (chip, BLACK, "chip")])
    render(c2, path + ".b.png")
    from PIL import Image
    a, b = Image.open(path + ".a.png"), Image.open(path + ".b.png")
    a = a.crop((0, 0, a.width // 2, a.height))
    s = Image.new("RGB", (a.width + b.width, a.height), (240, 239, 242))
    s.paste(a, (0, 0)); s.paste(b, (a.width, 0)); s.save(path)
    os.remove(path + ".a.png"); os.remove(path + ".b.png")


def main():
    global CARTRIDGE
    os.makedirs(OUT, exist_ok=True)
    screen_png = sys.argv[1] if len(sys.argv) > 1 else None
    CARTRIDGE = cartridge()
    top, bottom, _, _ = CARTRIDGE
    print("cartridge: %.1f x %.1f x %.2f mm" % (CART[0], CART[1], CART_T))
    # each half as it prints: flat face down
    cq.exporters.export(top.translate((0, 0, 0)), os.path.join(OUT, "cartridge_top.stl"), tolerance=0.02, angularTolerance=0.1)
    cq.exporters.export(bottom.rotate((0, 0, 0), (0, 1, 0), 180), os.path.join(OUT, "cartridge_bottom.stl"),
                        tolerance=0.02, angularTolerance=0.1)
    render_cartridge(os.path.join(OUT, "cartridge.png"))
    asm = cq.Assembly(name="pico_sign_concepts")
    for i, make in enumerate((wedge, terminal, slab, vault)):
        c = make()
        render(c, os.path.join(OUT, c["name"] + ".png"), screen_png)
        sub = cq.Assembly(name=c["name"], loc=cq.Location(cq.Vector(i * 220, 0, 0)))
        for shape, color, n in c["parts"]:
            sub.add(shape, name=n.replace(" ", "_").replace(",", "").replace(":", ""), color=cq.Color(*color))
        asm.add(sub)
        print("drew", c["name"])
    asm.save(os.path.join(OUT, "concepts.step"))
    for f in sorted(os.listdir(OUT)):
        print("wrote", os.path.join("hardware/builds/pico-sign/case/out/concepts", f))


if __name__ == "__main__":
    main()
