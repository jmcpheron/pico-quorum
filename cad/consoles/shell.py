"""The shared half of the console boards' cases (cad/consoles/README.md): a tub and a front plate round one
board, the board clamped between them by M2 screws through its own holes, printed caps on its three
buttons, pinholes for BOOT and RESET, and a dock that holds the closed case on the desk. stick.py
(console-s3) and badge.py (PicoquorumKey rev A) each describe their board and call build().

The board's parts come from the files JLCPCB built it from: the placement file (cpl.csv) and the BOM's
footprints, read by parts(). Each part is a box: its footprint's usual size and height (PACKAGES), not
the maker's model. The script checks only that the printed parts don't overlap those boxes, the board,
the glass, the module, a USB-C plug or each other. All dimensions mm.

Frame: the board's front up, x along it and y across it as its own files have them (origin at its
bottom-left corner seen from the front, y up), z up from the board's front face: the board is
z -T..0, its back parts below, the glass and the front parts above.
"""
import csv
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "hardware", "archive", "builds", "pico-sign", "case"))
import concepts as K        # the renderer the other cases use

# --- the case --------------------------------------------------------------------------------------
WALL, FLOOR = 2.0, 1.4
CLEAR = 0.3                 # round the board in the tub
PLATE = 1.8                 # the plate over the glass, at the least
PLATE_CLEAR = 0.2           # round the plate in the tub's opening
GLASS_GAP = 0.15            # the plate's underside over the glass: it keeps the glass on its tape
MOD_GAP = 0.5               # the floor under the module; two ribs come up to REST_GAP under its shield
REST_GAP, REST_W = 0.1, 1.6     # the same gap for ribs under the board's back where it's pressed (b["support"])
POCKET = (0.4, 0.3)         # round and over a part that stands higher than the plate's underside
BACK_R, FRONT_C = 2.0, 0.8  # the back's edge rounded, the face's edge chamfered
WINDOW_MARGIN = 0.5         # the window round the active area
GLASS_LIP = 0.8             # the plate over the glass's edge, at the least
WINDOW_C = 0.8              # the window's top edge chamfered
ENGRAVE = 0.5
# The screws: M2 socket heads, self-tapping into a 1.8 mm hole in the plate's posts, as the handheld's are.
# The bench's kit has 4, 8, 12 and 16 mm; the longest that fits is taken.
M2_PILOT, M2_CLEAR, M2_HEAD = 1.8, 2.4, (3.8, 2.0)
M2_KIT = (4.0, 8.0, 12.0, 16.0)
# A counterbore printed from the bed up ends in a ceiling with the screw's hole in it, an annulus with nothing to
# bridge to. Two layers of steps fix it in any slicer: in the first, the hole is a strip across the counterbore, so the
# layer is two bridges from wall to wall, along the strip; in the second, a square, bridged across the strip the
# other way; above it, the round hole. One layer each at the slicer's layer height (b["bridge_layer"]; 0 for none).
# The counterbore's depth must be a whole number of layers, so the steps fall on layer lines.
BRIDGE_LAYER = 0.2
ENGAGE = 3.0                # the least thread in the post
POST_R = 2.2                # on the board's front: inside the 2.5 mm keep-out round each hole
BOSS_R, BOSS_BASE = 2.3, (3.4, 1.2)     # under the board; a wider foot on the floor round the counterbore
# The caps on D0, D1, D2: a round stem through the plate and a square flange under it that keeps it in.
CAP_D, CAP_HOLE = 4.2, 4.6
# Shaped caps (b["cap_shapes"]: name -> shape), each about a round cap's area (14 mm2), so none is harder to hit:
# a square of 3.8 mm, corners rounded 0.6; an equilateral triangle of 6.0 mm, point up, corners rounded 0.8,
# centred on its height. A shaped stem in its own shaped hole can't turn.
CAP_SQUARE, CAP_TRI = (3.8, 0.6), (6.0, 0.8)
CAP_PROUD = 1.0             # over the plate
CAP_FLANGE_T = 0.8
CAP_LIP = 0.2               # the flange past the edge of its hole in the face, at the least (Case.lip)
CAP_GAP = 0.2               # the flange under the plate (or its pocket) at rest: the cap's free play
PIN_HOLE, LED_HOLE = 1.8, 1.6   # BOOT and RESET with a paperclip; the status LED
# The USB-C plug: a cut cable's overmold, as the handheld measured one, and its shell
PLUG = (12.4, 5.5, 17.1)
PLUG_SHELL = (8.25, 2.4, 6.5)
USB_OPEN = (13.2, 6.2, 1.5)     # the opening in the wall: across, tall, corner radius
LUG_HOLE = (8.0, 3.2)       # the lanyard's slot through the lug, an oval
# The other layout, "shell" (the stick): the face, walls and all are one front shell, a flat panel closes the
# back, and the screws go in from the front, through the shell's posts and the board into bosses on the panel.
PANEL_T = 1.6               # the back panel
SHELL_EDGE = (1.5, 0.8)     # the face's edge rounded, the back's
SHELL_POST_R = 3.0          # the face's posts, wider than POST_R so a counterbore fits in them
TAB = (2.0, 1.2, 0.2)       # the back panel's tab into the end wall: long, thick, clearance round it
CORNER_WALL = 1.5           # the wall where a cut corner (b["corner_cut"]) comes nearest the inside, at the least

# Footprint -> (along x at rotation 0, along y, height), by the first prefix that matches. Datasheet sizes
# with the leads, not measured. The receptacles' face is at the board's edge.
PACKAGES = [
    ("USB_C_Receptacle_HCTL", (8.94, 7.35, 3.3)),       # HC-TYPE-C-16P-01A (console-s3's generator: 3.3)
    ("USB_C_Receptacle_HRO", (8.94, 7.35, 3.2)),        # TYPE-C-31-M-12 (PicoquorumKey's DESIGN.md: 3.2)
    ("FPC", (3.6, 8.0, 1.0)), ("SW_TS-1187A", (5.1, 5.1, 1.5)), ("SW_Push_1P1T_XKB_TS-1187A", (5.1, 5.1, 1.5)),
    ("SW_Tact_4.5x4.5", (4.5, 4.5, 3.8)),
    ("SOT-223", (6.5, 7.0, 1.8)), ("SOT-23-6", (2.9, 2.8, 1.45)), ("SOT-23-5", (2.9, 2.8, 1.25)),
    ("SOT-23", (2.9, 2.4, 1.2)), ("DFN-8", (3.0, 3.0, 0.6)),
    ("C_0805", (2.0, 1.25, 1.25)), ("C_0603", (1.6, 0.8, 0.9)), ("R_0603", (1.6, 0.8, 0.55)),
    ("LED_0603", (1.6, 0.8, 0.8)), ("D_SOD-523", (1.6, 0.8, 0.7)), ("D_SOD-323", (2.5, 1.3, 1.1)),
    # console-rp's: Raspberry Pi's footprints (hardware/console-rp/lib/pqrp.pretty) and the stock ones
    ("C_0402", (1.0, 0.5, 0.55)), ("R_0402", (1.0, 0.5, 0.4)), ("RPi_C_0402", (1.0, 0.5, 0.55)),
    ("RPi_R_0402", (1.0, 0.5, 0.4)), ("RPi_Crystal_SMD_3225", (3.2, 2.5, 0.8)), ("RPi_L_Abracon_AOTA-B201610", (2.0, 1.6, 1.0)),
    ("RPi_RP2350A_QFN-60", (7.0, 7.0, 0.9)), ("WCH_QFN-16", (3.0, 3.0, 0.75)),
    ("SOIC-8_3.9x4.9", (4.9, 6.0, 1.75)), ("SOIC-8_5.3x5.3", (5.3, 8.0, 2.16)),
]
WROOM = (25.5, 18.0, 3.1)   # ESP32-S3-WROOM-1: long, across, thick (Espressif's datasheet)

# Colours for the pictures: the brand's Reject red and Sign green on their caps (docs/BRAND.md)
TUB_C, PLATE_C = K.DARK, (0.74, 0.73, 0.70)
RED, GREEN, PAPER = (1.0, 0.36, 0.33), (0.20, 0.78, 0.35), (0.90, 0.90, 0.88)
CAP_C = {"D0": RED, "D1": PAPER, "D2": GREEN}
BOARD_C, PART_C, GLASS_C, MOD_C = (0.10, 0.36, 0.20), (0.15, 0.15, 0.17), (0.05, 0.05, 0.07), (0.70, 0.70, 0.72)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl(x, y, r, z0, z1):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def rrect(x0, x1, y0, y1, r, z0, z1):
    w = cq.Workplane("XY").workplane(offset=z0).center((x0 + x1) / 2, (y0 + y1) / 2).rect(x1 - x0, y1 - y0).extrude(z1 - z0)
    return w.edges("|Z").fillet(r) if r > 0.01 else w


def slot(x, y, length, width, z0, z1, along_x=True):
    w = cq.Workplane("XY").workplane(offset=z0).center(x, y)
    return (w.slot2D(length, width, 0 if along_x else 90)).extrude(z1 - z0)


def parts(cpl, bom):
    """The board's parts from its placement file and BOM: ref -> dict(fp, x, y, rot, side, box=(x0, x1, y0, y1), h)."""
    fp = {}
    for row in csv.DictReader(open(bom)):
        for ref in row["Designator"].split(","):
            fp[ref.strip()] = row["Footprint"]
    out = {}
    for row in csv.DictReader(open(cpl)):
        ref = row["Designator"]
        f = fp.get(ref, "")
        size = next((s for p, s in PACKAGES if f.startswith(p)), None)
        assert size, "no package size for %s (%s): add it to PACKAGES" % (ref, f)
        x, y = float(row["Mid X"].rstrip("m")), float(row["Mid Y"].rstrip("m"))
        rot = float(row["Rotation"]) % 180
        lx, ly = (size[1], size[0]) if abs(rot - 90) < 1 else (size[0], size[1])
        out[ref] = dict(fp=f, x=x, y=y, rot=rot, side=row["Layer"], box=(x - lx / 2, x + lx / 2, y - ly / 2, y + ly / 2),
                        h=size[2])
    return out


def cap_shape(x, y, kind, grow, z0, z1, scale=1.0):
    """A cap's stem (grow 0) or its hole in the face (grow the clearance), as a solid from z0 to z1. scale makes
    the stem's face larger (b["cap_scale"]); the clearance stays the same."""
    if kind == "square":
        s, r = (v * scale for v in CAP_SQUARE)
        return box(x - s / 2 - grow, x + s / 2 + grow, y - s / 2 - grow, y + s / 2 + grow, z0, z1).edges("|Z").fillet(r + grow)
    if kind == "triangle":
        s, r = (v * scale for v in CAP_TRI)
        h = s * math.sqrt(3) / 2
        cy = y - h / 6                      # the centroid, so the triangle's height is centred on the switch
        s += 2 * math.sqrt(3) * grow        # the same triangle moved out by grow, about its centroid
        ri = s * math.sqrt(3) / 6
        pts = [(x - s / 2, cy - ri), (x + s / 2, cy - ri), (x, cy + 2 * ri)]
        w = cq.Workplane("XY").workplane(offset=z0).polyline(pts).close().extrude(z1 - z0)
        return w.edges("|Z").fillet(r + grow)
    return cyl(x, y, CAP_D * scale / 2 + grow, z0, z1)


def mark(cx, cy, r, z0, z1):
    """The Picoquorum mark (docs/BRAND.md): five owners on a circle of radius r, the top and the two at the bottom
    signed (dots r/4) and joined by their triangle, the other two waiting (dots r/6)."""
    pts = [(cx + r * math.cos(math.radians(90 - 72 * k)), cy + r * math.sin(math.radians(90 - 72 * k))) for k in range(5)]
    tri = [pts[0], pts[2], pts[3]]
    m = cq.Workplane("XY").workplane(offset=z0).polyline(tri).close().extrude(z1 - z0)
    for k, (x, y) in enumerate(pts):
        m = m.union(cyl(x, y, r / 4 if k in (0, 2, 3) else r / 6, z0, z1))
    return m


def fit_text(words, width, height, kind="bold"):
    """The text size that fits words in width x height."""
    bb = cq.Workplane("XY").text(words, 10, 1, combine=False, kind=kind).val().BoundingBox()
    return min(10 * width / bb.xlen, 10 * height / bb.ylen)


def engrave_text(plane, words, size, depth, kind="bold"):
    return cq.Workplane(plane).text(words, size, -depth, combine=False, kind=kind, halign="center", valign="center")


class Case:
    """One board's case. b describes the board (stick.py, badge.py)."""

    def __init__(self, b):
        self.b = b
        P = b["parts"]
        T = b["T"]
        self.zb = -T
        self.zmod = self.zb - b["module_h"]
        self.zf = self.zmod - MOD_GAP
        self.layout = b.get("layout", "plate")
        self.z0 = self.zf - (FLOOR if self.layout == "plate" else PANEL_T)
        self.zu = b["glass_z"][1] + GLASS_GAP
        # the caps: a flange on each switch, under the plate or in a pocket in its underside
        tops = [P[r]["h"] for r, _ in b["buttons"]]
        assert len(set(tops)) == 1, "the buttons stand at different heights"
        self.zcap = tops[0]                                     # the flange's bottom, on the switch
        self.zft = max(self.zcap + CAP_FLANGE_T, self.zu - CAP_GAP)   # its top
        need = [self.zu + PLATE, self.zft + CAP_GAP + 0.8]
        usb = P[b["usb"]]
        self.usb_z = usb["h"] / 2
        need.append(self.usb_z + USB_OPEN[1] / 2 + 0.8)          # a bridge over the USB opening
        self.zt = max(need)
        self.plate_t = self.zt - self.zu
        # the outline: the board's, CLEAR round it inside, WALL more outside, and the lug at one end
        W, H = b["W"], b["H"]
        wall = self.wall = b.get("wall", WALL)
        self.inner = (-CLEAR, W + CLEAR, -CLEAR, H + CLEAR)
        x0, x1, y0, y1 = -CLEAR - wall, W + CLEAR + wall, -CLEAR - wall, H + CLEAR + wall
        side, self.lug = b["lug"]
        if side == "right":
            x1 += self.lug
        elif side == "left":
            x0 -= self.lug
        elif side == "top":
            y1 += self.lug
        self.outer = (x0, x1, y0, y1)
        self.r_in = b["R"] + CLEAR
        self.r_out = self.r_in + wall
        # the screw: the longest in the kit that stops short of the pilot hole's end with ENGAGE in the post or boss.
        # "plate": from the back, into the plate's posts. "shell": from the front, into the back panel's bosses.
        cb = M2_HEAD[1] + 0.2
        self.cb = cb
        if self.layout == "plate":
            seat = self.z0 + cb
            fit = [s for s in M2_KIT if seat + s <= self.zt - 0.8 and seat + s >= ENGAGE]
        else:
            seat = self.zt - cb
            fit = [s for s in M2_KIT if seat - s >= self.z0 + 0.6 and self.zb - (seat - s) >= ENGAGE]
        assert fit, "no screw in the kit fits"
        self.screw = max(fit)
        self.seat = seat

    # --- what's on the board: stand-ins for the pictures and the checks -----------------------------------
    def standins(self):
        b, P = self.b, self.b["parts"]
        W, H, T = b["W"], b["H"], b["T"]
        out = []
        board = rrect(0, W, 0, H, b["R"], -T, 0)
        for x, y in b["holes"]:
            board = board.cut(cyl(x, y, b["hole_d"] / 2, -T - 1, 1))
        for cx0, cx1, cy0, cy1 in b.get("board_cut", []):
            board = board.cut(box(cx0, cx1, cy0, cy1, -T - 1, 1))
        out.append((board, BOARD_C, "board"))
        for (ex0, ex1, ey0, ey1, ez0, ez1), col, n in b.get("extras", []):
            out.append((box(ex0, ex1, ey0, ey1, ez0, ez1), col, n))
        for ref, p in sorted(P.items()):
            if p["side"] != "Top":
                continue
            x0, x1, y0, y1 = p["box"]
            out.append((box(x0, x1, y0, y1, 0, p["h"]), PART_C, ref))
        g0, g1 = b["glass_z"]
        gx0, gy0, gx1, gy1 = b["glass"]
        out.append((box(gx0, gx1, gy0, gy1, g0, g1), GLASS_C, "glass"))
        fx0, fx1, fy0, fy1 = b["fold"]
        out.append((box(fx0, fx1, fy0, fy1, 0.0, g1), GLASS_C, "ribbon fold"))
        if b["module"]:
            mx0, mx1, my0, my1 = b["module"]
            out.append((box(mx0, mx1, my0, my1, self.zmod, -T), MOD_C, "module"))
        return out

    def plug(self):
        """A USB-C plug pushed fully home: its shell in the receptacle, its overmold against the receptacle's face."""
        b, p = self.b, self.b["parts"][self.b["usb"]]
        z = self.usb_z
        sw, sh, sl = PLUG_SHELL
        ow, oh, ol = PLUG
        if b["usb_edge"] == "left":
            yc = (p["box"][2] + p["box"][3]) / 2
            shell = box(-0.01, sl - 0.5, yc - sw / 2 + 0.3, yc + sw / 2 - 0.3, z - sh / 2 + 0.2, z + sh / 2 - 0.2)
            over = box(-ol, -0.01, yc - ow / 2, yc + ow / 2, z - oh / 2, z + oh / 2).edges("|X").fillet(1.0)
        elif b["usb_edge"] == "right":
            yc, W = (p["box"][2] + p["box"][3]) / 2, b["W"]
            shell = box(W - sl + 0.5, W + 0.01, yc - sw / 2 + 0.3, yc + sw / 2 - 0.3, z - sh / 2 + 0.2, z + sh / 2 - 0.2)
            over = box(W + 0.01, W + ol, yc - ow / 2, yc + ow / 2, z - oh / 2, z + oh / 2).edges("|X").fillet(1.0)
        else:
            xc = (p["box"][0] + p["box"][1]) / 2
            shell = box(xc - sw / 2 + 0.3, xc + sw / 2 - 0.3, -0.01, sl - 0.5, z - sh / 2 + 0.2, z + sh / 2 - 0.2)
            over = box(xc - ow / 2, xc + ow / 2, -ol, -0.01, z - oh / 2, z + oh / 2).edges("|Y").fillet(1.0)
        return over, shell

    # --- the tub --------------------------------------------------------------------------------------
    def tub(self):
        b = self.b
        x0, x1, y0, y1 = self.outer
        t = rrect(x0, x1, y0, y1, self.r_out, self.z0, self.zt)
        t = t.faces("<Z").edges().fillet(BACK_R).faces(">Z").edges().chamfer(FRONT_C)
        ix0, ix1, iy0, iy1 = self.inner
        cavity = rrect(ix0, ix1, iy0, iy1, self.r_in, self.zf, self.zt + 1)
        t = t.cut(cavity)
        inside = rrect(ix0, ix1, iy0, iy1, self.r_in, self.zf - 0.01, self.zt)
        add = None
        for x, y in b["holes"]:
            s = cyl(x, y, BOSS_R, self.zf - 0.01, self.zb).union(cyl(x, y, BOSS_BASE[0], self.zf - 0.01, self.zf + BOSS_BASE[1]))
            add = s if add is None else add.union(s)
        for rx0, rx1, ry0, ry1 in b["rest"]:
            add = add.union(box(rx0, rx1, ry0, ry1, self.zf - 0.01, self.zmod - REST_GAP))
        for rx0, rx1, ry0, ry1 in b.get("support", []):
            add = add.union(box(rx0, rx1, ry0, ry1, self.zf - 0.01, self.zb - REST_GAP))
        t = t.union(add.intersect(inside))
        for x, y in b["holes"]:
            t = t.cut(cyl(x, y, M2_CLEAR / 2, self.z0 - 1, self.zb + 0.1))
            t = t.cut(cyl(x, y, M2_HEAD[0] / 2 + 0.2, self.z0 - 1, self.z0 + self.cb))
            t = self.bridge_steps(t, x, y, self.z0 + self.cb, up=True)       # the tub prints on its back
        t = t.cut(self.usb_hole())
        t = self.notch(self.lug_slot(t))
        # the back: the name, and the Source Location (CERN-OHL-W v2, section 4.1: the board's own is under the case)
        t = t.cut(self.back_text())
        return t

    def lug_slot(self, t):
        b = self.b
        side, lug = b["lug"]
        if side == "right":
            return t.cut(slot(b["W"] + CLEAR + self.wall + lug / 2 - 0.3, b.get("lug_at", b["H"] / 2), LUG_HOLE[0], LUG_HOLE[1],
                              self.z0 - 1, self.zt + 1, along_x=False))
        if side == "left":
            return t.cut(slot(-CLEAR - self.wall - lug / 2 + 0.3, b.get("lug_at", b["H"] / 2), LUG_HOLE[0], LUG_HOLE[1],
                              self.z0 - 1, self.zt + 1, along_x=False))
        return t.cut(slot(b.get("lug_at", b["W"] / 2), b["H"] + CLEAR + self.wall + lug / 2 - 0.3, LUG_HOLE[0], LUG_HOLE[1],
                          self.z0 - 1, self.zt + 1))

    def notch(self, t):
        """t with an opening through the case at one edge, all the way through, for something that stands out of
        the board's edge (b["notch"]: x0, x1, from y0 to past the top edge): the badge's key port."""
        if not self.b.get("notch"):
            return t
        nx0, nx1, ny0 = self.b["notch"]
        x0, x1, y0, y1 = self.outer
        n = box(max(nx0, x0 - 1), nx1, ny0, y1 + 1, self.z0 - 1, self.zt + 1)
        return t.cut(n.edges("|Z").fillet(0.8))

    def tab(self, grow=0.0):
        """The back panel's tab at the antenna end (the lug's side), into a slot in the end wall; grow makes the slot."""
        b = self.b
        L, t, _ = TAB
        ix1 = self.inner[1]
        y0, y1 = 4.0 - grow, b["H"] - 4.0 + grow
        # from the board's edge on: the module's antenna end is flush with it, and the tab stands above the panel
        return box(b["W"] - grow, ix1 + L + grow, y0, y1, self.zf - t / 2 - grow, self.zf + t / 2 + grow)

    def front(self):
        """The "shell" layout's front: the face and the walls in one piece, open at the back."""
        b = self.b
        t = self.outline(self.z0, self.zt)
        kind, size = b.get("face_edge", ("fillet", SHELL_EDGE[0]))     # the face's edge: rounded, or a chamfer
        t = t.faces(">Z").edges()
        t = t.chamfer(size) if kind == "chamfer" else t.fillet(size)
        kind, size = b.get("back_edge", ("fillet", SHELL_EDGE[1]))     # the back's edge, the same choice
        t = t.faces("<Z").edges()
        t = t.chamfer(size) if kind == "chamfer" else t.fillet(size)
        ix0, ix1, iy0, iy1 = self.inner
        t = t.cut(rrect(ix0, ix1, iy0, iy1, self.r_in, self.z0 - 1, self.zu))
        # posts on the board round its holes (they run into the walls at the corners), ribs on its antenna end
        gx0, gy0, gx1, gy1 = b["glass"]
        pr = b.get("post_r", SHELL_POST_R)
        for x, y in b["holes"]:
            c = cyl(x, y, pr, 0.0, self.zu + 0.01)
            if gx0 - pr - 0.3 < x < gx1 + pr + 0.3 and gy0 - pr - 0.3 < y < gy1 + pr + 0.3:
                c = c.cut(box(gx0 - 0.3, gx1 + 0.3, gy0 - 0.3, gy1 + 0.3, -1, self.zu))   # by the glass: 0.3 mm off it
            t = t.union(c)
        for rx0, rx1, ry0, ry1 in b["press"]:
            t = t.union(box(rx0, rx1, ry0, ry1, 0.0, self.zu + 0.01))
        for x, y in b["holes"]:
            t = t.cut(cyl(x, y, M2_CLEAR / 2, -1, self.zt + 1))
            t = t.cut(cyl(x, y, M2_HEAD[0] / 2 + 0.2, self.seat, self.zt + 1))
            t = self.bridge_steps(t, x, y, self.seat, up=False)              # the shell prints face down
            ch = b.get("cb_chamfer", 0.0)       # the counterbore's top edge chamfered
            if ch:
                t = t.cut(cq.Workplane("XY").workplane(offset=self.zt - ch).center(x, y).circle(M2_HEAD[0] / 2 + 0.2)
                          .workplane(offset=ch + 0.01).circle(M2_HEAD[0] / 2 + 0.2 + ch + 0.01).loft())
        t = t.cut(self.usb_hole())
        t = self.notch(self.lug_slot(t))
        t = self.corner_notches(self.grooves(t))
        if b.get("tab", True):
            t = t.cut(self.tab(TAB[2]))
        return self.face(t)

    def bridge_steps(self, t, x, y, seat, up):
        """t with the two bridging steps over a counterbore whose floor (the screw head's seat) is at seat, the
        layers after it going up (up) or down from it (BRIDGE_LAYER)."""
        L = self.b.get("bridge_layer", BRIDGE_LAYER)
        if not L:
            return t
        n = self.cb / L
        assert abs(n - round(n)) < 1e-6, "the counterbore isn't a whole number of %.2f mm layers" % L
        rc, d, s = M2_HEAD[0] / 2 + 0.2, M2_CLEAR, 1 if up else -1
        z1, z2 = seat + s * L, seat + 2 * s * L
        strip = box(x - rc - 1, x + rc + 1, y - d / 2, y + d / 2, min(seat, z1) - 0.01, max(seat, z1))
        strip = strip.intersect(cyl(x, y, rc, min(seat, z1) - 0.01, max(seat, z1)))
        square = box(x - d / 2, x + d / 2, y - d / 2, y + d / 2, min(z1, z2) - 0.01, max(z1, z2) + 0.01)
        return t.cut(strip).cut(square)

    def outline(self, z0, z1):
        """The case's outside from z0 to z1: the outline rounded at its corners, or with them cut off at 45 degrees
        (b["corner_cut"]: the cut along each edge at the corners, and at the two at the lug's end). Checks that the
        wall keeps CORNER_WALL where a cut comes nearest the board's corner inside."""
        x0, x1, y0, y1 = self.outer
        cut = self.b.get("corner_cut")
        if not cut:
            return rrect(x0, x1, y0, y1, self.r_out, z0, z1)
        lo, hi = cut
        side = self.b["lug"][0]
        ix0, ix1, iy0, iy1 = self.inner
        r = self.r_in
        # bottom left, bottom right, top right, top left: each one's cut, and how far its arc's centre is in from it
        bl, br = (hi if side == "left" else lo), (hi if side == "right" else lo)
        tr, tl = (hi if side in ("right", "top") else lo), (hi if side in ("left", "top") else lo)
        self.cuts = (bl, br, tr, tl)
        ax0, ax1, ay0, ay1 = (ix0 + r) - x0, x1 - (ix1 - r), (iy0 + r) - y0, y1 - (iy1 - r)
        # each corner of the inside is an arc of r_in; the cut's line is its cut from the outside's corner
        self.corner_wall = min((a - c) / math.sqrt(2) - r
                               for a, c in ((ax0 + ay0, bl), (ax1 + ay0, br), (ax1 + ay1, tr), (ax0 + ay1, tl)))
        assert self.corner_wall >= CORNER_WALL, "a cut corner leaves the wall %.2f mm" % self.corner_wall
        pts = [(x0 + bl, y0), (x1 - br, y0), (x1, y0 + br), (x1, y1 - tr), (x1 - tr, y1), (x0 + tl, y1), (x0, y1 - tl),
               (x0, y0 + bl)]
        return cq.Workplane("XY").workplane(offset=z0).polyline(pts).close().extrude(z1 - z0)

    def corner_notches(self, t):
        """A notch either side of each cut corner, from the back to the face (b["corner_notch"]: how far from the
        cut's end, wide, deep). The wall behind each keeps CORNER_WALL."""
        n = self.b.get("corner_notch")
        if not n:
            return t
        gap, w, d = n
        assert self.wall - d >= CORNER_WALL, "a notch leaves the wall %.2f mm" % (self.wall - d)
        x0, x1, y0, y1 = self.outer
        bl, br, tr, tl = self.cuts
        za, zb = self.z0 - 1, self.zt + 1
        span = lambda a, c, s: sorted((a + s * (c + gap), a + s * (c + gap + w)))     # along an edge, from its corner at a
        for (ya, yb), cl, cr in (((y0 - 1, y0 + d), bl, br), ((y1 - d, y1 + 1), tl, tr)):       # the bottom edge, the top
            for xa, xb in (span(x0, cl, 1), span(x1, cr, -1)):
                t = t.cut(box(xa, xb, ya, yb, za, zb))
        for (xa, xb), cb, ct in (((x0 - 1, x0 + d), bl, tl), ((x1 - d, x1 + 1), br, tr)):       # the left end, the right
            for ya, yb in (span(y0, cb, 1), span(y1, ct, -1)):
                t = t.cut(box(xa, xb, ya, yb, za, zb))
        return t

    def grooves(self, t):
        """90-degree V-grooves across both long sides, for grip (b["grooves"]: their y, and their depth; each is twice
        as wide as it is deep), stopping short of the face's and the back's edges. b["grooves_x"]: the same across
        the top and bottom edges, at their x."""
        for key in ("grooves", "grooves_x"):
            g = self.b.get(key)
            if not g:
                continue
            at, d = g
            assert d <= self.wall - 1.0, "a groove too deep for the wall"
            x0, x1, y0, y1 = self.outer
            a = d * math.sqrt(2)                    # a square turned 45 degrees, its corner d into the wall
            za = self.z0 + self.b.get("back_edge", ("", SHELL_EDGE[1]))[1] + 0.8
            zb = self.zt - self.b.get("face_edge", ("", SHELL_EDGE[0]))[1] - 0.8
            for u in at:
                for x, y in ([(x0, u), (x1, u)] if key == "grooves" else [(u, y0), (u, y1)]):
                    v = cq.Workplane("XY").box(a, a, zb - za).rotate((0, 0, 0), (0, 0, 1), 45).translate((x, y, (za + zb) / 2))
                    t = t.cut(v)
        return t

    def back(self):
        """The "shell" layout's back panel: flush in the shell's back, its tab in the end wall, two screws at the
        other end into its bosses. Ribs under the module's shield; the name and the Source Location outside."""
        b = self.b
        ix0, ix1, iy0, iy1 = self.inner
        c = PLATE_CLEAR
        outline = lambda z0, z1: rrect(ix0 + c, ix1 - c, iy0 + c, iy1 - c, self.r_in - c, z0, z1)
        p = outline(self.z0, self.zf).faces("<Z").edges().chamfer(0.5)
        add = None
        for x, y in b["holes"]:
            s = cyl(x, y, BOSS_R, self.zf - 0.01, self.zb).union(cyl(x, y, BOSS_BASE[0], self.zf - 0.01, self.zf + BOSS_BASE[1]))
            add = s if add is None else add.union(s)
        for rx0, rx1, ry0, ry1 in b["rest"]:
            add = add.union(box(rx0, rx1, ry0, ry1, self.zf - 0.01, self.zmod - REST_GAP))
        for rx0, rx1, ry0, ry1 in b.get("support", []):
            add = add.union(box(rx0, rx1, ry0, ry1, self.zf - 0.01, self.zb - REST_GAP))
        p = p.union(add.intersect(outline(self.zf - 0.01, self.zb + 0.01)))
        if b.get("tab", True):
            p = p.union(self.tab())
        for x, y in b["holes"]:
            p = p.cut(cyl(x, y, M2_PILOT / 2, self.z0 + 0.6, self.zb + 0.1))
        return p.cut(self.back_text())

    def printed(self):
        """The printed parts as they sit: (name, shape, colour), and how each lies on the bed."""
        caps = [(n, s, col) for s, col, n in self.caps()]
        if self.layout == "plate":
            return [("tub", self.tub(), TUB_C, lambda s: s), ("plate", self.plate(), PLATE_C, flip)] + \
                [(n, s, col, lambda s: s) for n, s, col in caps]
        front, back, extra = self.front(), self.back(), []
        if self.b.get("decor"):     # the board's own touches: (shell, back) -> (shell, back, [(name, shape, colour, lie)])
            front, back, extra = self.b["decor"](self, front, back)
        return [("shell", front, TUB_C, flip), ("back", back, PLATE_C, lambda s: s)] + \
            [(n, s, col, lambda s: s) for n, s, col in caps] + extra

    def usb_hole(self):
        """The USB opening: through the wall, and on to the receptacle's face at the board's edge."""
        b = self.b
        p = b["parts"][b["usb"]]
        x0, _, y0, _ = self.outer
        w, h, r = USB_OPEN
        z = self.usb_z
        if b["usb_edge"] == "left":
            yc = (p["box"][2] + p["box"][3]) / 2
            return box(x0 - 1, 0.0, yc - w / 2, yc + w / 2, z - h / 2, z + h / 2).edges("|X").fillet(r)
        if b["usb_edge"] == "right":
            yc = (p["box"][2] + p["box"][3]) / 2
            return box(b["W"], self.outer[1] + 1, yc - w / 2, yc + w / 2, z - h / 2, z + h / 2).edges("|X").fillet(r)
        xc = (p["box"][0] + p["box"][1]) / 2
        return box(xc - w / 2, xc + w / 2, y0 - 1, 0.0, z - h / 2, z + h / 2).edges("|Y").fillet(r)

    def back_text(self):
        b = self.b
        flip = b["flip"]                      # how the case is turned over to read its back: about "x" or "y"
        xdir = (1, 0, 0) if flip == "x" else (-1, 0, 0)
        cut = None
        for words, (cx, cy), (w, h), kind in b["back_text"]:
            size = fit_text(words, w, h, kind)
            pl = cq.Plane(origin=(cx, cy, self.z0), xDir=xdir, normal=(0, 0, -1))
            c = engrave_text(pl, words, size, b.get("engrave", ENGRAVE), kind)
            cut = c if cut is None else cut.union(c)
        return cut

    # --- the plate -----------------------------------------------------------------------------------
    def plate(self):
        b, P = self.b, self.b["parts"]
        ix0, ix1, iy0, iy1 = self.inner
        c = PLATE_CLEAR
        zu, zt = self.zu, self.zt
        p = rrect(ix0 + c, ix1 - c, iy0 + c, iy1 - c, self.r_in - c, zu, zt)
        p = p.faces(">Z").edges().chamfer(0.5).cut(self.usb_hole())
        p = self.notch(p)
        # posts on the board round its holes, ribs that hold its far end down
        for x, y in b["holes"]:
            p = p.union(cyl(x, y, POST_R, 0.0, zu + 0.01))
        for rx0, rx1, ry0, ry1 in b["press"]:
            p = p.union(box(rx0, rx1, ry0, ry1, 0.0, zu + 0.01))
        for x, y in b["holes"]:
            p = p.cut(cyl(x, y, M2_PILOT / 2, -0.1, zt - 0.8))
        return self.face(p)

    def face(self, p):
        """The face's openings and engraving, cut into p (the plate, or the front shell) between zu and zt."""
        b, P = self.b, self.b["parts"]
        zu, zt = self.zu, self.zt
        # pockets in the underside over any part that stands higher than it, but the capped buttons
        capped = {r for r, _ in b["buttons"]}
        for ref, q in P.items():
            if q["side"] != "Top" or ref in capped or q["h"] < zu - 0.2:
                continue
            x0, x1, y0, y1 = q["box"]
            a, up = POCKET
            p = p.cut(box(x0 - a, x1 + a, y0 - a, y1 + a, zu - 0.5, q["h"] + up))
        # the window: the active area and a margin, never closer than GLASS_LIP to the glass's edge; chamfered
        ax0, ay0, ax1, ay1 = b.get("window_over", b["active"])
        gx0, gy0, gx1, gy1 = b["glass"]
        m = WINDOW_MARGIN
        wx0, wx1 = max(ax0 - m, gx0 + GLASS_LIP), min(ax1 + m, gx1 - GLASS_LIP)
        wy0, wy1 = max(ay0 - m, gy0 + GLASS_LIP), min(ay1 + m, gy1 - GLASS_LIP)
        self.window = (wx0, wx1, wy0, wy1)
        p = p.cut(box(wx0, wx1, wy0, wy1, zu - 1, zt + 1))
        ch = WINDOW_C
        bev = (cq.Workplane("XY").workplane(offset=zt - ch).center((wx0 + wx1) / 2, (wy0 + wy1) / 2).rect(wx1 - wx0, wy1 - wy0)
               .workplane(offset=ch + 0.01).rect(wx1 - wx0 + 2 * ch + 0.02, wy1 - wy0 + 2 * ch + 0.02).loft())
        p = p.cut(bev)
        # the caps' holes, and a pocket for each flange where it stands higher than the underside
        for ref, name in b["buttons"]:
            q = P[ref]
            kind = b.get("cap_shapes", {}).get(name, "circle")
            p = p.cut(cap_shape(q["x"], q["y"], kind, (CAP_HOLE - CAP_D) / 2, zu - 1, zt + 1, b.get("cap_scale", 1.0)))
            if self.zft + CAP_GAP > zu:
                f = self.flange_w() / 2 + 0.3
                p = p.cut(box(q["x"] - f, q["x"] + f, q["y"] - f, q["y"] + f, zu - 0.5, self.zft + CAP_GAP))
        for ref, _ in b["pins"]:
            q = P[ref]
            p = p.cut(cyl(q["x"], q["y"], PIN_HOLE / 2, zu - 1, zt + 1))
            p = p.cut(cq.Workplane("XY").workplane(offset=zt - 0.5).center(q["x"], q["y"]).circle(PIN_HOLE / 2)
                      .workplane(offset=0.51).circle(PIN_HOLE / 2 + 0.5).loft())
        for ref in ([b["led"]] if isinstance(b["led"], str) else b["led"]):
            q = P[ref]
            p = p.cut(cyl(q["x"], q["y"], LED_HOLE / 2, zu - 1, zt + 1))
        for kind, args in b["face"]:
            if kind == "mark":
                cx, cy, r = args[:3]
                p = p.cut(mark(cx, cy, r, zt - ENGRAVE, zt + 1))
                # a switch under the mark's lower-left dot (and its lower-right): the dot is its hole, through
                for ref, ang in zip(args[3:], (-126, -54)):
                    q = P[ref]
                    dx, dy = cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))
                    assert abs(dx - q["x"]) < 0.01 and abs(dy - q["y"]) < 0.01, "the mark's dot isn't over " + ref
                    p = p.cut(cyl(dx, dy, r / 4, zu - 1, zt + 1))
            else:
                words, (cx, cy), (w, h) = args
                size = fit_text(words, w, h)
                p = p.cut(engrave_text(cq.Plane(origin=(cx, cy, zt), xDir=(1, 0, 0), normal=(0, 0, 1)), words, size, ENGRAVE))
        return p

    def flange_w(self):
        b, P = self.b, self.b["parts"]
        at = [(P[r]["x"], P[r]["y"]) for r, _ in b["buttons"]]
        pitch = min(max(abs(a[0] - c[0]), abs(a[1] - c[1])) for i, a in enumerate(at) for c in at[i + 1:])
        sw = P[b["buttons"][0][0]]["box"]
        return min(pitch - 0.6, (sw[1] - sw[0]) + b.get("flange_over", 1.0))

    def lip(self, ref, name):
        """How far the flange reaches past the edge of its cap's hole at the least, in 0.05 mm steps: what keeps the
        cap in the face. 0 means the hole is wider than the flange somewhere."""
        b, q = self.b, self.b["parts"][ref]
        f = self.flange_w() / 2
        flange = box(q["x"] - f, q["x"] + f, q["y"] - f, q["y"] + f, 0, 1).edges("|Z").fillet(0.6)
        kind = b.get("cap_shapes", {}).get(name, "circle")
        m = 0.0
        while m < 3.0:
            hole = cap_shape(q["x"], q["y"], kind, (CAP_HOLE - CAP_D) / 2 + m + 0.05, 0.2, 0.8, b.get("cap_scale", 1.0))
            if hole.cut(flange).val().Volume() > 1e-6:
                return m
            m += 0.05
        return m

    def caps(self):
        """Each button's cap, as it sits: flange on the switch, stem through the plate."""
        out = []
        f = self.flange_w() / 2
        for ref, name in self.b["buttons"]:
            q = self.b["parts"][ref]
            c = box(q["x"] - f, q["x"] + f, q["y"] - f, q["y"] + f, self.zcap, self.zft).edges("|Z").fillet(0.6)
            kind = self.b.get("cap_shapes", {}).get(name, "circle")
            stem = cap_shape(q["x"], q["y"], kind, 0.0, self.zft - 0.01, self.zt + CAP_PROUD, self.b.get("cap_scale", 1.0))
            stem = stem.faces(">Z").edges().fillet(0.6 if kind == "circle" else 0.4)
            out.append((c.union(stem), CAP_C.get(name, PAPER), "cap " + name))
        return out

    def screws(self):
        out = None
        for x, y in self.b["holes"]:
            seat = self.seat
            if self.layout == "plate":
                s = cyl(x, y, M2_HEAD[0] / 2, seat - M2_HEAD[1], seat).union(cyl(x, y, 0.95, seat, seat + self.screw))
            else:
                s = cyl(x, y, M2_HEAD[0] / 2, seat, seat + M2_HEAD[1]).union(cyl(x, y, 0.95, seat - self.screw, seat))
            out = s if out is None else out.union(s)
        return out

    # --- the dock: the closed case leaning back on the desk ----------------------------------------------
    def dock(self, tilt=65.0, back=3.0, side=3.0, under=3.0, lip=0.55):
        """A wedge with a pocket that holds the case's back, its bottom edge and the lower part of its sides,
        leaning back so the face looks up at 90 - tilt degrees. Built in the case's frame and turned:
        rotate() maps a case-frame point to the desk's."""
        b = self.b
        x0, x1, y0, y1 = self.outer
        hc = y1 - y0
        tc = self.zt - self.z0
        a = math.radians(tilt)
        ya = y0 - under - (b["dock_plug"] if b["usb_edge"] == "bottom" else 0.0)
        yb = y0 + 0.45 * hc
        za, zc = self.z0 - back, self.z0 + lip * tc
        rot = lambda y, z: (y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))
        pts = [rot(ya, za), rot(ya, zc), rot(yb, za), rot(yb, self.z0)]
        zmin = min(z for _, z in pts)
        pts += [(pts[1][0], zmin), (pts[2][0], zmin)]
        # a press on a button pushes back along the face's normal: a tail back along the desk, a slope like the prism's
        front = min(y for y, _ in pts)
        pts.append((max(front + b["dock_depth"], max(y for y, _ in pts)), zmin))
        hull = convex_hull(pts)
        prof = cq.Workplane("YZ").workplane(offset=x0 - side).polyline(hull).close().extrude(x1 - x0 + 2 * side)
        env = rrect(x0 - 0.4, x1 + 0.4, y0 - 0.4, y1 + 0.4, self.r_out + 0.4, self.z0 - 0.4, self.zt + 20)
        p = b["parts"][b["usb"]]
        z = self.usb_z
        if b["usb_edge"] == "left":
            yc = (p["box"][2] + p["box"][3]) / 2
            chan = box(x0 - 60, x0 + 1, yc - 7.5, yc + 7.5, z - 3.8, self.zt + 20)
        elif b["usb_edge"] == "right":
            yc = (p["box"][2] + p["box"][3]) / 2
            chan = box(x1 - 1, x1 + 60, yc - 7.5, yc + 7.5, z - 3.8, self.zt + 20)
        else:
            xc = (p["box"][0] + p["box"][1]) / 2
            chan = box(xc - 7.5, xc + 7.5, ya - 60, y0 + 1, z - 3.8, self.zt + 20)
        cut = env.union(chan).rotate((0, 0, 0), (1, 0, 0), tilt)
        d = prof.cut(cut)
        self.dock_move = (0, 0, -zmin)
        return d.translate(self.dock_move), tilt

    def on_dock(self, shape, tilt):
        return shape.rotate((0, 0, 0), (1, 0, 0), tilt).translate(self.dock_move)


def convex_hull(pts):
    pts = sorted(set(pts))
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def overlap(a, b):
    try:
        return a.intersect(b).val().Volume()
    except Exception:
        return 0.0


def check(pairs):
    """Every pair (name, shape, name, shape) that overlaps by more than a speck: a list of lines."""
    bad = []
    for na, a, nb, b in pairs:
        v = overlap(a, b)
        if v > 1e-3:
            bad.append("%s overlaps %s: %.3f mm3" % (na, nb, v))
    return bad


def stl(shape, path, tol=0.05):
    cq.exporters.export(shape, path, tolerance=tol, angularTolerance=0.2)


def flip(shape):
    """Face down, as the plate prints."""
    return shape.rotate((0, 0, 0), (1, 0, 0), 180)


def build(b, out, screen_png=None):
    """Make the case's parts, check them, write the STLs, the STEP and the pictures to out. Returns 1 if a check fails."""
    os.makedirs(out, exist_ok=True)
    c = Case(b)
    name = b["name"]
    shown = c.printed()                                 # (name, shape as it sits, colour, how it lies on the bed)
    parts = [p for p in shown if p[3]]                  # one that lies no way is only for the pictures (decor)
    printed = [(n, s) for n, s, _, _ in parts]
    dock, tilt = c.dock()
    screws = c.screws()
    over, shell = c.plug()
    things = c.standins()
    own = {"cap " + n: ref for ref, n in b["buttons"]}  # a cap sits on its own switch
    pairs = []
    for pn, ps in printed:
        for sn, sh in [(n, s) for s, _, n in things] + [("plug overmold", over), ("plug shell", shell)]:
            if own.get(pn) != sn:
                pairs.append((pn, ps, sn, sh))
    for i, (pn, ps) in enumerate(printed):
        for qn, qs in printed[i + 1:]:
            pairs.append((pn, ps, qn, qs))
    pairs += [("screws", screws, sn, sh) for sh, _, sn in things]
    pairs += [("dock", dock, n, c.on_dock(s, tilt)) for n, s in printed + [("plug overmold", over)]]
    bad = check(pairs)
    for ref, n in b["buttons"]:                         # the flange must reach past the hole, or the cap falls out
        lip = c.lip(ref, n)
        if lip < CAP_LIP:
            bad.append("cap %s: its flange reaches %.2f mm past its hole, under %.2f" % (n, lip, CAP_LIP))
    for line in bad:
        print("CHECK:", line)
    for n, s, _, lie in parts:
        if n.startswith("cap"):
            s = s.translate((0, 0, -c.zcap))
        stl(lie(s), os.path.join(out, "%s_%s.stl" % (name, n.replace(" ", "_"))))
    stl(dock, os.path.join(out, name + "_dock.stl"))
    asm = cq.Assembly(name=name)
    for n, s, col, _ in parts:
        asm.add(s, name=n.replace(" ", "_"), color=cq.Color(*col))
    asm.add(screws, name="screws", color=cq.Color(*K.STEEL))
    for s, col, n in things:
        asm.add(s, name="pcb_" + n.replace(" ", "_"), color=cq.Color(*col))
    asm.save(os.path.join(out, name + "_assembly.step"))
    pictures(c, out, shown, dock, tilt, screws, things, over, screen_png)
    for n, sh in printed + [("dock", dock)]:
        bb = sh.val().BoundingBox()
        print("  %-7s %5.1f x %5.1f x %4.1f mm, %5.2f cm3" % (n, bb.xlen, bb.ylen, bb.zlen, sh.val().Volume() / 1000))
    print("%s: closed %.1f x %.1f x %.1f mm; %.1f mm over the glass; screws M2 x %g from the %s; caps %.1f mm proud"
          % (name, c.outer[1] - c.outer[0], c.outer[3] - c.outer[2], c.zt - c.z0, c.plate_t, c.screw,
             "back" if c.layout == "plate" else "front", CAP_PROUD))
    for f in sorted(os.listdir(out)):
        print("wrote", os.path.relpath(os.path.join(out, f), REPO))
    return 1 if bad else 0, c


def render(c, path, screen_png=None):
    """K.render's pictures, with a depth for every pixel. K.render has matplotlib paint whole triangles, the far
    ones first by their middles, so a long thin triangle of a flat face shows through whatever is in front of it.
    Here the nearest triangle wins at each pixel. The views, the light and the colours are K.render's; each pixel
    is the mean of SS x SS samples."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import proj3d
    from PIL import Image, ImageDraw

    SS, BG = 3, (0.94, 0.93, 0.95)
    light = np.array([0.35, -0.55, 0.75]); light /= np.linalg.norm(light)
    pts, cols = [], []
    for shape, color, _ in c["parts"]:
        for sol in shape.vals():
            vs, ts = sol.tessellate(0.2, 0.3)
            if not ts:
                continue
            tri = np.array([v.toTuple() for v in vs])[np.array(ts)]
            n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nn = np.linalg.norm(n, axis=1)
            ok = nn > 1e-9
            lit = 0.35 + 0.65 * np.abs(n[ok] @ light) / nn[ok]
            pts.append(tri[ok]); cols.append(np.minimum(1, lit[:, None] * np.array(color)[None, :]))
    pts, cols = np.concatenate(pts), np.concatenate(cols)
    allp = pts.reshape(-1, 3)
    lo, hi = allp.min(0), allp.max(0)
    ctr, r = (lo + hi) / 2, (hi - lo).max() / 2 * 0.9
    tiles = []
    for i, (title, elev, azim) in enumerate(c["views"]):
        fig = plt.figure(figsize=(7, 6), dpi=130)
        ax = fig.add_axes([0, 0, 1, 1], projection="3d")
        ax.set_xlim(ctr[0] - r, ctr[0] + r); ax.set_ylim(ctr[1] - r, ctr[1] + r); ax.set_zlim(ctr[2] - r, ctr[2] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
        fig.canvas.draw()
        proj = ax.get_proj()
        w, h = int(round(fig.bbox.width)), int(round(fig.bbox.height))

        def place(p):
            """Points to pixels from the picture's top left, and a depth: more is further."""
            p = np.asarray(p, float)
            x2, y2, z2 = proj3d.proj_transform(p[:, 0], p[:, 1], p[:, 2], proj)
            d = ax.transData.transform(np.column_stack([x2, y2]))
            return np.column_stack([d[:, 0], fig.bbox.height - d[:, 1], z2])

        s = place(allp).reshape(-1, 3, 3)
        s[:, :, :2] *= SS
        W, H = w * SS, h * SS
        img = np.empty((H, W, 3)); img[:] = BG
        depth = np.full((H, W), np.inf)
        for (a, b_, c_), col in zip(s, cols):
            x0 = max(int(math.ceil(min(a[0], b_[0], c_[0]) - 0.5)), 0); x1 = min(int(math.floor(max(a[0], b_[0], c_[0]) - 0.5)), W - 1)
            y0 = max(int(math.ceil(min(a[1], b_[1], c_[1]) - 0.5)), 0); y1 = min(int(math.floor(max(a[1], b_[1], c_[1]) - 0.5)), H - 1)
            if x1 < x0 or y1 < y0:
                continue
            area = (b_[0] - a[0]) * (c_[1] - a[1]) - (b_[1] - a[1]) * (c_[0] - a[0])
            if abs(area) < 1e-12:
                continue
            px = np.arange(x0, x1 + 1)[None, :] + 0.5; py = np.arange(y0, y1 + 1)[:, None] + 0.5
            u = ((b_[0] - px) * (c_[1] - py) - (b_[1] - py) * (c_[0] - px)) / area      # a's weight, then b's
            v = ((c_[0] - px) * (a[1] - py) - (c_[1] - py) * (a[0] - px)) / area
            z = u * a[2] + v * b_[2] + (1 - u - v) * c_[2]
            d = depth[y0:y1 + 1, x0:x1 + 1]
            hit = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (z < d)
            d[hit] = z[hit]
            img[y0:y1 + 1, x0:x1 + 1][hit] = col
        plt.close(fig)
        img = img.reshape(h, SS, w, SS, 3).mean(axis=(1, 3))
        im = Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGB").convert("RGBA")
        if screen_png and i == 0:
            quad = [tuple(q[:2]) for q in place(c["corners"])]
            shot = Image.open(screen_png).convert("RGBA")
            shot = shot.resize((shot.width * 4, shot.height * 4), Image.NEAREST)
            src = [(0, 0), (shot.width, 0), (shot.width, shot.height), (0, shot.height)]
            m = []
            for (x, y), (u, v) in zip(quad, src):
                m += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
            k = np.linalg.solve(np.array(m, float), np.array(src, float).reshape(8)).tolist()
            im.paste(shot.transform(im.size, Image.PERSPECTIVE, k, Image.BILINEAR), (0, 0),
                     Image.new("L", shot.size, 255).transform(im.size, Image.PERSPECTIVE, k, Image.BILINEAR))
        tiles.append((title, im))
    sheet = Image.new("RGB", (sum(t.width for _, t in tiles), tiles[0][1].height + 40), (240, 239, 242))
    dr = ImageDraw.Draw(sheet)
    x = 0
    for title, t in tiles:
        sheet.paste(t, (x, 40))
        dr.text((x + 16, 12), (c["title"] + ": " + title) if x == 0 else title, fill=(20, 20, 24))
        x += t.width
    sheet.save(path)


def pictures(c, out, parts, dock, tilt, screws, things, over, screen_png):
    b, name = c.b, c.b["name"]
    ax0, ay0, ax1, ay1 = b["active"]
    z = b["glass_z"][1] + 0.01
    corners = [(ax0, ay1, z), (ax1, ay1, z), (ax1, ay0, z), (ax0, ay0, z)]
    seen = [p for p in things if p[2] in ("glass",) or p[2] in b.get("seen", ())]
    case = [(s, col, n) for n, s, col, _ in parts]
    v = b["views"]
    render(dict(title=b["title"], parts=case + seen + [(screws, K.STEEL, "screws")], corners=corners, views=v["front"]),
             os.path.join(out, name + "_front.png"), screen_png)
    # the face from above, sliced just under its top: every opening and the engraving, which a picture of the
    # dark plastic doesn't show
    x0, x1, y0, y1 = c.outer
    face = case[0][0] if c.layout == "shell" else case[1][0]
    cut = face.intersect(box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, c.zt - 0.3, c.zt - 0.2))
    render(dict(title=b["title"] + ": the face, sliced 0.25 mm under its top", parts=[(cut, (0.80, 0.80, 0.78), "face")],
                  corners=[], views=[("", 89.9, -90)]), os.path.join(out, name + "_face.png"))
    # apart: each part moved off the board the way it goes on
    if c.layout == "plate":
        move = {"tub": 0, "plate": 22, "screws": -14}
    else:
        move = {"shell": 22, "back": -12, "screws": 40}
    ex = [(s.translate((0, 0, move.get(n.split()[0], 12))), col, n) for s, col, n in case] + \
        [(screws.translate((0, 0, move["screws"])), K.STEEL, "screws")] + [(s, col, n) for s, col, n in things]
    render(dict(title=b["title"] + ", apart", parts=ex, corners=[], views=v["apart"]), os.path.join(out, name + "_apart.png"))
    rot = lambda s: c.on_dock(s, tilt)
    docked = [(dock, K.MID, "dock")] + [(rot(s), col, n) for s, col, n in case + seen] + \
        [(rot(screws), K.STEEL, "screws"), (rot(over), K.BLACK, "plug")]
    dc = [rot_pt(c, p, tilt) for p in corners]
    render(dict(title=b["title"] + " on its dock", parts=docked, corners=dc, views=v["dock"]),
             os.path.join(out, name + "_dock.png"), screen_png)


def rot_pt(c, p, tilt):
    a = math.radians(tilt)
    x, y, z = p
    return (x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a) + c.dock_move[2])
