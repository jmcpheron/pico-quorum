"""Case for pico-sign (hardware/builds/pico-sign/README.md), concept A: a wedge.
A tray (the base) with sloped walls, and a flat lid on the slope that holds every part: the
sign switch at the front, the knob above it, the 2.4" screen
landscape behind them, and the key dock at the back, where a key-c stands up out of the lid. The
Pico lies on the floor with its USB out of the back wall.

Run: uv run --python 3.11 --with cadquery --with matplotlib python hardware/builds/pico-sign/case/case.py

A mock-up to print and try, not a checked design. The sign switch, knob and plug sizes are the
usual ones, and the plug's are the Feather pigtail's calipers. The screen module's are a guess:
measure yours and change SCREEN_* first. All dimensions mm.

Case frame: x across (left to right, seen from the front), y from the front edge to the back, z up
from the underside. Lid frame: u = x, v up the slope from the front edge, w out of the lid's top.
"""
import math
import os

import cadquery as cq

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# --- the box -------------------------------------------------------------------------------------
W, L = 100.0, 150.0         # outside, across and front to back
HF, HB = 36.0, 56.0         # height at the front and at the back, the lid's top
R = 6.0                     # the corners, seen from above
WALL, FLOOR, LID = 2.4, 2.4, 3.0
A = math.atan2(HB - HF, L)  # the lid's slope, about 7.6 degrees
CA, SA = math.cos(A), math.sin(A)
LT = L / CA                 # the lid's length up the slope
RIM_T, RIM_D = 1.2, 3.0     # the lid's locating rim under it, inside the walls
RIM_GAP = 0.3               # between the rim and the walls (twice that at the front and back)
BOSS_D, BOSS_HOLE = 8.0, 4.0        # corner posts: M3 heat-set inserts, 4.0 holes
BOSS_IN = WALL + 3.5        # a post's centre from the outside walls
SCREW, CSK = 3.4, 6.6       # the lid's M3 countersunk screws

# --- the parts on the lid (u across, v up the slope) ----------------------------------------------
SIGN_UV, SIGN_HOLE = (W / 2, 30.0), 12.2        # the sign switch: a 12 mm bushing
SIGN_RING, SIGN_RING_T = 26.0, 2.0              # a thicker ring under it: it is pressed hard
SIGN_BODY, SIGN_DEPTH = 17.5, 28.0              # its body and lugs below the panel, a soft-touch momentary
KNOB_UV, KNOB_HOLE = (W / 2, 68.0), 7.2         # EC11, M7 bushing: one knob, one switch
SCREEN_UV = (W / 2, 112.0)                      # the active area's centre
SCREEN_ACTIVE = (48.96, 36.72)                  # 2.4" 240x320, landscape: from the panel's datasheet
SCREEN_GLASS = (60.3, 42.7, 2.4)                # the panel, a guess: measure yours
SCREEN_PCB = (72.0, 44.0, 1.6)                  # the module's board, a guess: measure yours
SCREEN_POCKET = 1.0         # the panel sits this far up into the lid
DOCK_UV = (W / 2, 142.0)    # where the key stands
# the plug of a cut USB-C cable (Feather pigtail, calipers) and the key-c on it
PLUG_W, PLUG_H, PLUG_L = 12.4, 5.5, 17.1        # the overmold: across, thick, long
SHELL_W, SHELL_H, SHELL_L = 8.25, 2.4, 6.5      # its metal shell, standing out of the overmold
KEEPER = 1.2                # the overmold's face sits this far under the lid's top: the lid keeps it
REC_W, REC_H = 9.4, 3.8     # the opening for key-c's receptacle (8.94 x 3.26)
KEYC = (16.0, 36.0, 1.6)    # key-c's board
SLEEVE_T = 1.6              # the walls round the overmold under the lid

# --- the Pico on the floor -----------------------------------------------------------------------
PICO = (21.0, 51.0, 1.0)
PICO_X = 24.0               # its centre line
PICO_UP = 5.0               # standoffs
PICO_HOLES = [(-5.7, 2.0), (5.7, 2.0), (-5.7, 49.0), (5.7, 49.0)]   # from its USB end, along y
PICO_TOP = 22.0             # headers and Dupont housings above its board
USB_HOLE = (12.0, 8.0)      # in the back wall, for a micro-USB plug's overmold


def lid_plane(w=0.0):
    """The plane of the lid's top (w = 0), or w above it, as a CadQuery plane in lid coordinates."""
    o = cq.Vector(0, 0, HF) + cq.Vector(0, -SA, CA) * w
    return cq.Plane(origin=o.toTuple(), xDir=(1, 0, 0), normal=(0, -SA, CA))


def lid_wp(w=0.0):
    return cq.Workplane(lid_plane(w))


def world(u, v, w=0.0):
    return (u, v * CA - w * SA, HF + v * SA + w * CA)


def outer():
    side = cq.Workplane("YZ").polyline([(0, 0), (L, 0), (L, HB), (0, HF)]).close().extrude(W)
    return side.edges("|Z").fillet(R)


def base():
    b = outer()
    cav = cq.Workplane("XY").box(W - 2 * WALL, L - 2 * WALL, 200, centered=(True, True, False)) \
        .edges("|Z").fillet(R - WALL).translate((W / 2, L / 2, FLOOR))
    b = b.cut(cav)
    posts = [(x, y) for x in (BOSS_IN, W - BOSS_IN) for y in (BOSS_IN, L - BOSS_IN)]
    for x, y in posts:
        b = b.union(cq.Workplane("XY").circle(BOSS_D / 2).extrude(200).translate((x, y, 0)))
    py0 = L - WALL - 1.5 - PICO[1]      # the Pico's USB end 1.5 from the back wall
    for dx, dy in PICO_HOLES:
        b = b.union(cq.Workplane("XY").circle(2.5).extrude(PICO_UP).translate((PICO_X + dx, py0 + dy, FLOOR)))
    b = b.cut(lid_wp(-LID).rect(1000, 1000).extrude(300))       # everything above the lid's underside
    for x, y in posts:
        b = b.cut(cq.Workplane("XY").circle(BOSS_HOLE / 2).extrude(200).translate((x, y, FLOOR + 2)))
    for dx, dy in PICO_HOLES:
        b = b.cut(cq.Workplane("XY").circle(0.9).extrude(PICO_UP).translate((PICO_X + dx, py0 + dy, FLOOR)))
    uz = FLOOR + PICO_UP + PICO[2] + 1.6
    b = b.cut(cq.Workplane("XZ").rect(*USB_HOLE).extrude(-10).translate((PICO_X, L - WALL - 2, uz)))
    for x in (12, W - 12):                                      # rubber feet
        for y in (12, L - 12):
            b = b.cut(cq.Workplane("XY").circle(5.2).extrude(1.0).translate((x, y, 0)))
    return b


def lid():
    t = outer().intersect(lid_wp(-LID).rect(1000, 1000).extrude(LID))
    # the rim, inside the walls
    iw, il = W - 2 * (WALL + RIM_GAP), LT - 2 * (WALL / CA + 2 * RIM_GAP)
    rim = lid_wp(-LID).center(W / 2, LT / 2).rect(iw, il).extrude(-RIM_D) \
        .cut(lid_wp(-LID).center(W / 2, LT / 2).rect(iw - 2 * RIM_T, il - 2 * RIM_T).extrude(-RIM_D))
    posts = [(x, y / CA) for x in (BOSS_IN, W - BOSS_IN) for y in (BOSS_IN, L - BOSS_IN)]
    for u, v in posts:
        rim = rim.cut(lid_wp(-LID).center(u, v).circle(BOSS_D / 2 + 0.6).extrude(-RIM_D))
    t = t.union(rim)
    # under the sign switch, a thicker ring
    t = t.union(lid_wp(-LID).center(*SIGN_UV).circle(SIGN_RING / 2).extrude(-SIGN_RING_T))
    # round the plug's overmold, a sleeve
    sw, sh = PLUG_W + 2 * SLEEVE_T, PLUG_H + 2 * SLEEVE_T
    t = t.union(lid_wp(-LID).center(*DOCK_UV).rect(sw, sh).extrude(-(PLUG_L + KEEPER - LID)))
    # holes
    for (u, v), d in [(SIGN_UV, SIGN_HOLE), (KNOB_UV, KNOB_HOLE)]:
        t = t.cut(lid_wp(1).center(u, v).circle(d / 2).extrude(-(LID + SIGN_RING_T + 2)))
    for u, v in posts:
        t = t.cut(lid_wp(1).center(u, v).circle(SCREW / 2).extrude(-(LID + 2)))
        t = t.cut(lid_wp(0).center(u, v).circle(CSK / 2).workplane(offset=-(CSK - SCREW) / 2)
                  .circle(SCREW / 2).loft())
    # the screen: a bevelled window and a pocket for the panel
    aw, ah = SCREEN_ACTIVE
    t = t.cut(lid_wp(0).center(*SCREEN_UV).rect(aw + 6, ah + 6).workplane(offset=-2).rect(aw + 2, ah + 2).loft())
    t = t.cut(lid_wp(1).center(*SCREEN_UV).rect(aw + 2, ah + 2).extrude(-(LID + 2)))
    gw, gh, _ = SCREEN_GLASS
    t = t.cut(lid_wp(-LID).center(*SCREEN_UV).rect(gw + 0.6, gh + 0.6).extrude(SCREEN_POCKET))
    # the key dock: the receptacle's and key-c's board's opening, then the overmold's pocket
    t = t.cut(lid_wp(1).center(*DOCK_UV).slot2D(REC_W, REC_H).extrude(-(1 + KEEPER)))
    t = t.cut(lid_wp(1).center(*DOCK_UV).rect(KEYC[0] + 0.6, KEYC[2] + 0.6).extrude(-(1 + KEEPER)))
    t = t.cut(lid_wp(-KEEPER).center(*DOCK_UV).rect(PLUG_W + 0.3, PLUG_H + 0.3).extrude(-(PLUG_L + 1)))
    # words, cut 0.6 into the top
    for txt, (u, v), size in [("HOLD TO SIGN", (W / 2, 10.0), 6.0), ("KEY", (DOCK_UV[0] + 16, DOCK_UV[1]), 4.5)] + \
            [("MOVE / OPEN", (KNOB_UV[0], KNOB_UV[1] - 15), 4.0)]:
        t = t.cut(lid_wp(0).center(u, v).text(txt, size, -0.6, combine=False, halign="center", valign="center"))
    return t


# --- stand-ins for the parts, for the pictures and the STEP -------------------------------------
def stand_ins():
    s = []

    def on_lid(shape, color, name):
        s.append((shape, color, name))

    fu, fv = SIGN_UV
    on_lid(lid_wp(0).center(fu, fv).circle(7).extrude(2).union(
        lid_wp(2).center(fu, fv).polygon(6, 16).extrude(2.5)).union(
        lid_wp(4.5).center(fu, fv).circle(6).extrude(9)).union(
        lid_wp(13.5).center(fu, fv).circle(6.2).extrude(1.5)), (0.78, 0.78, 0.80), "sign switch")
    on_lid(lid_wp(-LID - SIGN_RING_T).center(fu, fv).rect(SIGN_BODY, SIGN_BODY).extrude(-SIGN_DEPTH),
           (0.25, 0.25, 0.28), "sign switch body")
    ku, kv = KNOB_UV
    on_lid(lid_wp(0).center(ku, kv).circle(9).extrude(15).faces(">Z").edges().fillet(1.5), (0.12, 0.12, 0.13), "knob")
    on_lid(lid_wp(15).center(ku, kv).rect(0.8, 7).extrude(0.4), (0.9, 0.9, 0.9), "knob mark")
    on_lid(lid_wp(-LID).center(ku, kv).rect(12, 12).extrude(-7), (0.25, 0.25, 0.28), "EC11 body")
    gw, gh, gt = SCREEN_GLASS
    pw, ph, pt = SCREEN_PCB
    gw0 = -LID + SCREEN_POCKET
    on_lid(lid_wp(gw0).center(*SCREEN_UV).rect(gw, gh).extrude(-gt), (0.05, 0.05, 0.07), "screen panel")
    on_lid(lid_wp(gw0).center(*SCREEN_UV).rect(*SCREEN_ACTIVE).extrude(0.3),
           (0.16, 0.42, 0.62), "screen picture")
    on_lid(lid_wp(gw0 - gt).center(SCREEN_UV[0] + (pw - gw) / 2 - 2, SCREEN_UV[1]).rect(pw, ph).extrude(-pt),
           (0.10, 0.30, 0.55), "screen board")
    du, dv = DOCK_UV
    on_lid(lid_wp(-KEEPER).center(du, dv).rect(PLUG_W, PLUG_H).extrude(-PLUG_L), (0.15, 0.15, 0.15), "plug overmold")
    on_lid(lid_wp(-KEEPER).center(du, dv).slot2D(SHELL_W, SHELL_H).extrude(SHELL_L), (0.8, 0.8, 0.82), "plug shell")
    on_lid(lid_wp(-KEEPER).center(du, dv).rect(*KEYC[::2]).extrude(KEYC[1]), (0.10, 0.25, 0.60), "key-c board")
    on_lid(lid_wp(-KEEPER).center(du, dv).slot2D(8.94, 3.26).extrude(7.8), (0.75, 0.75, 0.78), "key-c receptacle")
    on_lid(lid_wp(16).center(du, dv - KEYC[2] / 2 - 0.9).rect(4.9, 1.75).extrude(3.9).rotate(
        world(du, dv - 1.7, 16), world(du + 1, dv - 1.7, 16), 0), (0.1, 0.1, 0.1), "ATECC608")
    py0 = L - WALL - 1.5 - PICO[1]
    pico = cq.Workplane("XY").box(PICO[0], PICO[1], PICO[2], centered=(True, False, False)) \
        .translate((PICO_X, py0, FLOOR + PICO_UP))
    s.append((pico, (0.10, 0.42, 0.22), "Pico 2 W"))
    s.append((cq.Workplane("XY").box(8, 5.5, 2.8, centered=(True, False, False))
              .translate((PICO_X, py0 + PICO[1] - 4.2, FLOOR + PICO_UP + PICO[2])), (0.8, 0.8, 0.82), "micro-USB"))
    s.append((cq.Workplane("XY").box(PICO[0], PICO[1] - 4, PICO_TOP - PICO[2], centered=(True, False, False))
              .translate((PICO_X, py0 + 1, FLOOR + PICO_UP + PICO[2])), (0.55, 0.55, 0.58), "headers and wires (space)"))
    return s


def checks(b, l, parts):
    """Only that nothing obvious collides. Not a fit check: the parts are boxes."""
    lid_body = l
    names = {n: sh for sh, _, n in parts}
    out = []
    for n in ("sign switch body", "EC11 body", "screen board", "plug overmold", "headers and wires (space)"):
        v = names[n].intersect(b).val().Volume()
        out.append(("%s vs base" % n, v))
    for n in ("headers and wires (space)",):
        for m in ("screen board", "plug overmold", "sign switch body", "EC11 body"):
            out.append(("%s vs %s" % (n, m), names[n].intersect(names[m]).val().Volume()))
    for n in ("sign switch body", "EC11 body", "screen panel", "plug overmold"):
        out.append(("%s vs lid" % n, names[n].intersect(lid_body).val().Volume()))
    gap = names["sign switch body"].val().BoundingBox().zmin - FLOOR
    print("sign switch lugs to the floor: %.1f mm" % gap)
    print("screen board to the wires' space: %.1f mm" % (names["screen board"].val().BoundingBox().zmin
                                                        - names["headers and wires (space)"].val().BoundingBox().zmax))
    bad = [(n, v) for n, v in out if v > 0.01]
    for n, v in out:
        print("  %-48s %s" % (n, "clear" if v <= 0.01 else "OVERLAP %.2f mm3" % v))
    assert gap > 1.0, "the sign switch reaches the floor: raise HF"
    return bad


def render(items, path, views):
    """A rough picture with matplotlib: each solid tessellated, shaded by its faces' angle to a light."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np

    fig = plt.figure(figsize=(6 * len(views), 6.4), dpi=130)
    light = np.array([0.35, -0.55, 0.75])
    light /= np.linalg.norm(light)
    tris_all = []
    for shape, color, offset in items:
        for sol in shape.vals():
            vs, ts = sol.tessellate(0.15, 0.3)
            p = np.array([v.toTuple() for v in vs]) + np.array(offset)
            for t in ts:
                tri = p[list(t)]
                n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
                nn = np.linalg.norm(n)
                if nn < 1e-9:
                    continue
                k = 0.35 + 0.65 * abs(np.dot(n / nn, light))
                tris_all.append((tri, tuple(min(1, c * k) for c in color)))
    for i, (title, elev, azim) in enumerate(views):
        ax = fig.add_subplot(1, len(views), i + 1, projection="3d")
        pc = Poly3DCollection([t for t, _ in tris_all], facecolors=[c for _, c in tris_all], linewidths=0)
        ax.add_collection3d(pc)
        allp = np.concatenate([t for t, _ in tris_all])
        lo, hi = allp.min(0), allp.max(0)
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(title, fontsize=12)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    b, l = base(), lid()
    parts = stand_ins()
    bad = checks(b, l, parts)
    if bad:
        print("WARNING: overlaps above")
    cq.exporters.export(b, os.path.join(OUT, "pico_sign_base.stl"), tolerance=0.05, angularTolerance=0.2)
    # the lid as it prints: top face down
    flat = l.translate((0, 0, -HF)).rotate((0, 0, 0), (1, 0, 0), -math.degrees(A)).rotate((0, 0, 0), (1, 0, 0), 180)
    flat = flat.translate((0, 0, -flat.val().BoundingBox().zmin))
    cq.exporters.export(flat, os.path.join(OUT, "pico_sign_lid.stl"), tolerance=0.05, angularTolerance=0.2)
    asm = cq.Assembly(name="pico_sign")
    asm.add(b, name="base", color=cq.Color(0.20, 0.20, 0.22))
    asm.add(l, name="lid", color=cq.Color(0.93, 0.62, 0.15))
    for sh, col, n in parts:
        asm.add(sh, name=n.replace(" ", "_").replace("(", "").replace(")", ""), color=cq.Color(*col))
    asm.save(os.path.join(OUT, "pico_sign_assembly.step"))

    shell, top = (0.22, 0.22, 0.24), (0.95, 0.63, 0.15)
    closed = [(b, shell, (0, 0, 0)), (l, top, (0, 0, 0))] + [(sh, c, (0, 0, 0)) for sh, c, n in parts]
    render(closed, os.path.join(OUT, "pico_sign_preview.png"),
           [("front, three-quarter", 24, -62), ("from the side", 4, -2), ("from above", 88, -90)])
    lift = (0, -18 * SA * 3, 34)
    opened = [(b, shell, (0, 0, 0))] + [(l, top, lift)] + \
             [(sh, c, lift if n not in ("Pico 2 W", "micro-USB", "headers and wires (space)") else (0, 0, 0))
              for sh, c, n in parts]
    render(opened, os.path.join(OUT, "pico_sign_exploded.png"),
           [("lid lifted", 28, -55), ("lid lifted, from behind", 30, 128)])
    for f in sorted(os.listdir(OUT)):
        print("wrote", os.path.join("hardware/builds/pico-sign/case/out", f))


if __name__ == "__main__":
    main()
