#!/usr/bin/env python3
"""console-rp, assembled with its panel, as one solid to print: its shape and size, and where each part sits.

    tools/case build console-rp-mockup

or on its own (from anywhere):

    uv run --python 3.11 --with cadquery --with matplotlib --with pillow python hardware/console-rp/mockup/mockup.py

Writes into out/ next to this file:
- console-rp-mockup.stl      1:1, plain
- console-rp-mockup-2x.stl   twice the size, the main parts' names engraved, so the small parts read
- console-rp-mockup.png      the 2x one, from above and from the USB-C's corner

Where the numbers come from:
- every part's place and turn: the routed board, console-rp.kicad_pcb. The script stops unless each part
  in fab/cpl.csv, the file JLCPCB placed the order's parts from, is where the board has it.
- the outline, its corners and the four M2.5 holes: the same board. J3 isn't fitted: its eight holes only.
- each part's body: a box at the datasheet's size (BODIES), and its leads a thin slab under it. These
  are not the makers' models. Heights are gen_console_rp.py's HEIGHT, the ones tools/jlc's fit check uses.
- the panel: the README's (YIYANG's datasheet for the Y114): glass 31.0 x 17.6 x 1.6 mm on 2 mm foam,
  the active area 1.4 mm off the glass's centre, away from the ribbon, the ribbon's loop about 1.8 mm
  past the glass's right end.

What makes it one solid, and print without supports:
- every part is on the front, so the board's back is the print's flat base.
- the 2 mm under the glass is filled. The parts under it (J2, the backlight switch, their 0402s) can't
  be seen on a real board either. The fill stands 0.5 mm in from the glass's edge, so the glass reads
  as a plate on its tape; that is a 0.5 mm overhang.
- the USB-C is its outside, with a 1 mm socket in its face to show where the plug goes. A real plug
  doesn't fit: the metal's 0.3 mm walls don't print.

Frame: mm, as fab/cpl.csv: origin at the board's bottom-left corner seen from the front, x along it,
y up; z up from the board's back, so the board is z 0..1.6.
"""
import csv
import math
import os
import re
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
RP = os.path.normpath(os.path.join(HERE, ".."))
REPO = os.path.normpath(os.path.join(RP, "..", ".."))
PCB = os.path.join(RP, "console-rp", "console-rp.kicad_pcb")
CPL = os.path.join(RP, "console-rp", "fab", "cpl.csv")
OUT = os.path.join(HERE, "out")
W, H, T, CORNER = 72.0, 36.0, 1.6, 2.0      # gen_console_rp.py's board, 1.6 mm as ordered
PAGE = (100.0, 100.0)                        # where the board's top-left corner is on KiCad's page

# The panel (README, "The panel"): glass, its tape, the active area, the ribbon
GLASS = (31.0, 17.6, 1.6)
FOAM = 2.0
ACTIVE = (24.912, 14.864)                    # gen_console_rp.py's PANEL["active"], Waveshare's 1.14" module
ACTIVE_DX = -1.4                             # off the glass's centre, away from the ribbon (it leaves the right end)
ACTIVE_DEPTH = 0.4                           # the active area sunk into the glass's top, so it shows
FILL_IN = 0.5                                # the fill under the glass, in from its edge
RIBBON = (4.5, 1.8)                          # the ribbon's width, and how far its loop stands past the glass

# Footprint -> body (along x at rotation 0, along y, height), its leads' span (x, y) or None, and what it is.
# Sizes are the datasheets' bodies; heights are gen_console_rp.py's HEIGHT. The leads are a 0.3 mm slab.
BODIES = {
    "C_0402_1005Metric": ((1.0, 0.5, 0.55), None, "0402"),
    "R_0402_1005Metric": ((1.0, 0.5, 0.4), None, "0402"),
    "RPi_C_0402": ((1.0, 0.5, 0.55), None, "0402"),
    "RPi_C_0402_wide": ((1.0, 0.5, 0.55), None, "0402"),
    "RPi_R_0402": ((1.0, 0.5, 0.4), None, "0402"),
    "C_0805_2012Metric": ((2.0, 1.25, 1.25), None, "0805"),
    "LED_0603_1608Metric": ((1.6, 0.8, 0.8), None, "0603"),
    "SOT-23": ((1.3, 2.9, 1.15), (2.4, 2.0), "SOT-23"),
    "SOT-23-3": ((1.3, 2.9, 1.15), (2.4, 2.0), "SOT-23"),
    "SOT-23-6": ((1.6, 2.9, 1.45), (2.8, 2.4), "SOT-23-6"),
    "RPi_L_Abracon_AOTA-B201610": ((2.0, 1.6, 1.0), None, "2016"),
    "RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias": ((7.0, 7.0, 0.85), None, "QFN-60"),
    "WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm": ((3.0, 3.0, 0.75), None, "QFN-16"),
    "SOIC-8_3.9x4.9mm_P1.27mm": ((3.9, 4.9, 1.75), (6.0, 4.3), "SOIC-8"),
    "SOIC-8_5.3x5.3mm_P1.27mm": ((5.3, 5.3, 2.16), (8.0, 4.3), "SOIC-8 wide"),
    "RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm": ((3.2, 2.5, 0.8), None, "3225"),
    "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB": ((6.0, 3.25, 1.0), None, "ZIF"),
    "SW_Push_1P1T_XKB_TS-1187A": ((5.1, 5.1, 1.5), (6.2, 4.2), "TS-1187A"),
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": ((8.94, 7.3, 3.2), None, "USB-C"),
}
SW_BASE, SW_PLUNGER = 0.9, 3.0               # a TS-1187A's base, and its round plunger's size: a guess
USB_SOCKET = (7.9, 2.2, 1.0)                 # the socket in J1's face: across, tall, deep
NOT_PARTS = {"LCD1", "J3", "LOGO1"} | {f"H{i}" for i in range(1, 5)}   # the panel, drawn below; J3 isn't fitted; the mark is silkscreen

# Engraved on the 2x print, at 1:1 sizes: (text, x, y, height, on what). "board" is the board's top.
LABELS = [("RP2350", "U1", 1.2), ("FLASH", "U6", 1.0), ("KEY", "U5", 1.0)]
BOARD_LABELS = [("D0", 12.248, 2.9, 1.4), ("D1", 20.448, 2.9, 1.4), ("D2", 28.648, 2.9, 1.4),
                ("RESET", 54.0, 1.7, 1.0), ("BOOT", 61.5, 1.7, 1.0), ("LED", 53.5, 12.0, 0.9)]
ENGRAVE = 0.3


def board_parts():
    """Every footprint on the routed board: ref -> (footprint, x, y, rotation), in this frame."""
    s = open(PCB).read()
    out = {}
    for m in re.finditer(r'\n\t\(footprint "(?:[^":]+:)?([^"]+)"(.*?)\n\t\)', s, re.S):
        fp, body = m.groups()
        ref = re.search(r'\(property "Reference" "([^"]+)"', body).group(1)
        at = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', body).groups()
        out[ref] = (fp, float(at[0]) - PAGE[0], H - (float(at[1]) - PAGE[1]), float(at[2] or 0))
    return out


def check_against_order(parts):
    """Each part in the order's placement file is where the board has it, and nothing else is on the board."""
    bad = []
    placed = set()
    for row in csv.DictReader(open(CPL)):
        ref = row["Designator"]
        placed.add(ref)
        x, y = float(row["Mid X"].rstrip("m")), float(row["Mid Y"].rstrip("m"))
        if ref not in parts:
            bad.append(f"{ref} is in cpl.csv and not on the board")
        elif abs(parts[ref][1] - x) > 0.01 or abs(parts[ref][2] - y) > 0.01:
            bad.append(f"{ref}: cpl.csv has it at {x}, {y}, the board at {parts[ref][1]:.3f}, {parts[ref][2]:.3f}")
        if row["Layer"] != "Top":
            bad.append(f"{ref} is on the {row['Layer']}: the print's base is the board's back, flat")
    for ref in parts:
        if ref not in placed and ref not in NOT_PARTS:
            bad.append(f"{ref} is on the board and not in cpl.csv")
    if bad:
        sys.exit("the board and the order's cpl.csv disagree:\n  " + "\n  ".join(bad))
    return placed


def holes():
    """The board's drilled holes: (x, y, diameter), from its footprints' through-hole pads."""
    s = open(PCB).read()
    out = []
    for m in re.finditer(r'\n\t\(footprint "[^"]+"(.*?)\n\t\)', s, re.S):
        body = m.group(1)
        fx, fy, rot = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', body).groups()
        th = math.radians(float(rot or 0))
        for p in re.finditer(r'\(pad "[^"]*" (?:np_thru_hole|thru_hole) (?:circle|rect)\s*\(at ([-\d.]+) ([-\d.]+)[^)]*\)'
                             r'.*?\(drill ([-\d.]+)\)', body, re.S):
            lx, ly, d = float(p.group(1)), float(p.group(2)), float(p.group(3))
            if d < 0.9:
                continue                     # U1's thermal vias, J1's pegs: under parts, nothing to see
            # KiCad: y down, a turn counter-clockwise on the screen
            x = float(fx) + lx * math.cos(th) + ly * math.sin(th)
            y = float(fy) - lx * math.sin(th) + ly * math.cos(th)
            out.append((x - PAGE[0], H - (y - PAGE[1]), d))
    return out


def box(cx, cy, sx, sy, z0, z1):
    return cq.Workplane("XY").box(sx, sy, z1 - z0, centered=(True, True, False)).translate((cx, cy, z0))


def turned(w, cx, cy, rot):
    return w.rotate((cx, cy, 0), (cx, cy, 1), rot) if rot % 360 else w


def part(fp, x, y, rot):
    (bx, by, h), leads, kind = BODIES[fp]
    if kind == "USB-C":
        return usb_c(x, y, rot)
    if kind == "TS-1187A":
        w = box(x, y, bx, by, T, T + SW_BASE).edges("|Z").chamfer(0.6)
        w = w.union(cq.Workplane("XY").workplane(offset=T + SW_BASE).center(x, y).circle(SW_PLUNGER / 2).extrude(h - SW_BASE))
    else:
        w = box(x, y, bx, by, T, T + h)
    if leads:
        w = w.union(box(x, y, leads[0], leads[1], T, T + 0.3))
    return turned(w, x, y, rot)


def usb_c(x, y, rot):
    """The receptacle's outside, its round ends flat on the board, and a shallow socket in its face."""
    bx, by, h = BODIES["USB_C_Receptacle_HRO_TYPE-C-31-M-12"][0]
    assert rot % 360 == 90 and abs(x + by / 2 - W) < 0.1, "J1 should face out of the board's right edge"
    face = x + by / 2
    yz = cq.Workplane("YZ", origin=(face, 0, 0))     # normal +x: extrude negative to go into the board
    shell = yz.center(y, T + h / 2).slot2D(bx, h).extrude(-by)
    foot = yz.center(y, T + h / 4).rect(bx, h / 2).extrude(-by)
    sw, sh, sd = USB_SOCKET
    sock = yz.center(y, T + h / 2).slot2D(sw, sh).extrude(-sd)
    return shell.union(foot).cut(sock)


def panel():
    """The glass on its tape, the active area sunk in its top, and the ribbon's loop off its right end."""
    gx, gy = 5.0 + GLASS[0] / 2, H - 13.0               # LCD1's centre on the board: gen_console_rp.py's XC, YC
    z0, z1 = T + FOAM, T + FOAM + GLASS[2]
    w = box(gx, gy, GLASS[0], GLASS[1], z0, z1)
    w = w.union(box(gx, gy, GLASS[0] - 2 * FILL_IN, GLASS[1] - 2 * FILL_IN, T, z0))
    w = w.cut(box(gx + ACTIVE_DX, gy, ACTIVE[0], ACTIVE[1], z1 - ACTIVE_DEPTH, z1))
    rw, past = RIBBON
    x0 = gx + GLASS[0] / 2
    loop = (cq.Workplane("XZ", origin=(0, gy + rw / 2, 0)).center(x0 - 1.0, T)
            .rect(1.0 + past, z0 + 0.6 - T, centered=False).extrude(rw))
    loop = loop.edges("|Y").edges(">X").edges(">Z").fillet(min(past, z0 + 0.6 - T) - 0.1)
    return w.union(loop), (gx, gy, z1)


def text(s, x, y, size, ztop):
    return (cq.Workplane("XY").workplane(offset=ztop - ENGRAVE).center(x, y)
            .text(s, size, ENGRAVE + 0.01, kind="bold", halign="center", valign="center"))


def build():
    parts = board_parts()
    placed = check_against_order(parts)
    outline = cq.Workplane("XY").rect(W, H, centered=False).extrude(T).edges("|Z").fillet(CORNER)
    m = outline
    for x, y, d in holes():
        m = m.cut(cq.Workplane("XY").center(x, y).circle(d / 2).extrude(T))
    for ref in sorted(placed):
        fp, x, y, rot = parts[ref]
        if fp not in BODIES:
            sys.exit(f"no body for {ref} ({fp}): add it to BODIES")
        m = m.union(part(fp, x, y, rot))
    glass, (gx, gy, gz) = panel()
    m = m.union(glass)
    solids = m.solids().vals()
    assert len(solids) == 1 and solids[0].isValid(), f"expected one valid solid, got {len(solids)}"
    bb = solids[0].BoundingBox()
    assert abs(bb.zmin) < 1e-6, "the base isn't at z 0"

    marked = m
    for s, ref, size in LABELS:
        fp, x, y, _ = parts[ref]
        marked = marked.cut(text(s, x, y, size, T + BODIES[fp][0][2]))
    for s, x, y, size in BOARD_LABELS:
        marked = marked.cut(text(s, x, y, size, T))
    assert len(marked.solids().vals()) == 1
    return m, marked, len(placed)


def render(shape, path, views, px=14.0):
    """The print in one colour, each view drawn with a depth buffer (matplotlib's painter sorts the board's big
    faces wrongly), outlines where the depth jumps, cropped and set side by side with its title."""
    import numpy as np
    from PIL import Image, ImageDraw
    vs, ts = shape.tessellate(0.02, 0.2)
    p = np.array([v.toTuple() for v in vs])
    tris = p[np.array(ts)]
    light = np.array([-0.35, -0.45, 0.82]); light /= np.linalg.norm(light)
    tiles = []
    for title, elev, azim in views:
        e, a = math.radians(elev), math.radians(azim)
        fwd = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])   # toward the eye
        right = np.array([-math.sin(a), math.cos(a), 0.0])
        up = np.cross(fwd, right)
        q = tris @ np.stack([right, up, fwd], 1)
        lo, hi = q.reshape(-1, 3).min(0), q.reshape(-1, 3).max(0)
        wpx, hpx = int((hi[0] - lo[0]) * px) + 40, int((hi[1] - lo[1]) * px) + 40
        X = (q[..., 0] - lo[0]) * px + 20
        Y = (hi[1] - q[..., 1]) * px + 20
        Z = q[..., 2]
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
        shade = 0.30 + 0.70 * np.clip(n @ light, 0, 1)
        depth = np.full((hpx, wpx), -np.inf)
        img = np.full((hpx, wpx), np.nan)
        for i in np.nonzero(n @ fwd > 0)[0]:
            x, y, z = X[i], Y[i], Z[i]
            x0, x1 = max(int(x.min()), 0), min(int(x.max()) + 1, wpx - 1)
            y0, y1 = max(int(y.min()), 0), min(int(y.max()) + 1, hpx - 1)
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
            if abs(d) < 1e-12:
                continue
            l0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
            l1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            zz = l0 * z[0] + l1 * z[1] + l2 * z[2]
            win = inside & (zz > depth[y0:y1 + 1, x0:x1 + 1])
            depth[y0:y1 + 1, x0:x1 + 1][win] = zz[win]
            img[y0:y1 + 1, x0:x1 + 1][win] = shade[i]
        bg = np.isnan(img)
        rgb = np.where(bg[..., None], np.array([240, 239, 242]), np.nan_to_num(img)[..., None] * np.array([214, 212, 206]))
        dz = np.zeros_like(depth)
        fin = np.where(bg, depth[~bg].min() - 5 if (~bg).any() else 0, depth)
        dz[1:-1, 1:-1] = np.maximum.reduce([abs(fin[1:-1, 1:-1] - fin[:-2, 1:-1]), abs(fin[1:-1, 1:-1] - fin[2:, 1:-1]),
                                            abs(fin[1:-1, 1:-1] - fin[1:-1, :-2]), abs(fin[1:-1, 1:-1] - fin[1:-1, 2:])])
        rgb[dz > 0.25] = (60, 60, 64)
        tiles.append((title, Image.fromarray(rgb.astype(np.uint8))))
    w = sum(t.width for _, t in tiles) + 20 * (len(tiles) + 1)
    h = max(t.height for _, t in tiles) + 60
    sheet = Image.new("RGB", (w, h), (240, 239, 242))
    dr = ImageDraw.Draw(sheet)
    x = 20
    for title, t in tiles:
        sheet.paste(t, (x, 50 + (h - 60 - t.height) // 2))
        dr.text((x + 10, 16), title, fill=(20, 20, 24))
        x += t.width + 20
    sheet.save(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    m, marked, n = build()
    one = os.path.join(OUT, "console-rp-mockup.stl")
    two = os.path.join(OUT, "console-rp-mockup-2x.stl")
    cq.exporters.export(m, one, tolerance=0.01, angularTolerance=0.1)
    cq.exporters.export(cq.Workplane("XY").add(marked.val().scale(2.0)), two, tolerance=0.02, angularTolerance=0.1)
    bb = m.val().BoundingBox()
    print(f"{os.path.relpath(one, REPO)}: {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm, {m.val().Volume():.0f} mm^3, "
          f"1 solid, {n} parts from cpl.csv")
    print(f"{os.path.relpath(two, REPO)}: twice that, {2 * bb.xlen:.1f} x {2 * bb.ylen:.1f} x {2 * bb.zlen:.1f} mm, names engraved")
    png = os.path.join(OUT, "console-rp-mockup.png")
    render(marked.val(), png, [("from above", 90, -90), ("from the USB-C's corner", 35, -60)])
    print(os.path.relpath(png, REPO))

if __name__ == "__main__":
    main()
