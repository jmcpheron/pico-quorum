#!/usr/bin/env python3
"""The PicoQuorum name as a silkscreen footprint, in the brand's face (docs/BRAND.md: Atkinson
Hyperlegible Next, bold): lib/picoquorum.pretty/PicoQuorum_Name.kicad_mod.

    uv run --no-project --with numpy==2.5.3 --with pillow==12.3.0 python3 hardware/console-s3/wordmark.py

The face is the one tools/fonts/gen.py fetches into tools/fonts/src/ (git ignores it), checked
against gen.py's sha256. Pillow draws the name about 300 px to the mm of cap height; the outline is
traced where the ink is half on (marching squares) and simplified to 3 µm. A footprint polygon has
one outline, so each counter (the holes in P, o, Q) is joined to its letter's outside by a
zero-width cut, as KiCad itself does. The footprint is 1 mm to the cap height, centred on the name's
advance and cap height; the generator scales it. The letters are spaced a little wider than the
face's own spacing, so they stay apart at small sizes. Nothing is random: a rerun writes the same
file.
"""
import hashlib, math, os, re, sys, uuid

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FONT = os.path.join(REPO, "tools", "fonts", "src", "next.ttf")
OUT = os.path.join(HERE, "lib", "picoquorum.pretty", "PicoQuorum_Name.kicad_mod")
NAME, WEIGHT, SIZE = "PicoQuorum", 700, 420     # bold, as the panel's lockup; SIZE in px a em
TRACK = 0.04                                    # em added between letters: c and o close to 0.08 mm at 1.3 mm without it
TOL = 0.003                                     # mm, at 1 mm cap height


def font():
    sha = re.search(r'"next": \("[^"]+",\s*"([0-9a-f]{64})"\)', open(os.path.join(REPO, "tools", "fonts", "gen.py")).read()).group(1)
    if not os.path.exists(FONT) or hashlib.sha256(open(FONT, "rb").read()).hexdigest() != sha:
        sys.exit(f"{FONT}: missing or not gen.py's pinned file; `uv run --with pillow python tools/fonts/gen.py` fetches it")
    f = ImageFont.truetype(FONT, SIZE)
    f.set_variation_by_axes([WEIGHT if a["name"] == b"Weight" else a["default"] for a in f.get_variation_axes()])
    return f


def trace(a):
    """Closed outlines of a > 0.5 in a (rows down, columns across), as lists of (x, y) in pixels."""
    a = np.pad(a, 1)
    b = a > 0.5
    tl, tr, br, bl = b[:-1, :-1], b[:-1, 1:], b[1:, 1:], b[1:, :-1]
    busy = np.argwhere((tl != tr) | (tr != br) | (br != bl) | (bl != tl))

    def cut(e):      # where the half-ink level crosses an edge: ("h", i, j) joins (i, j)-(i, j+1)
        k, i, j = e
        p, q = (a[i, j], a[i, j + 1]) if k == "h" else (a[i, j], a[i + 1, j])
        t = (0.5 - p) / (q - p)
        return (j + t, i) if k == "h" else (j, i + t)
    link = {}

    def join(e1, e2):
        link.setdefault(e1, []).append(e2)
        link.setdefault(e2, []).append(e1)
    for i, j in busy:
        c = [b[i, j], b[i, j + 1], b[i + 1, j + 1], b[i + 1, j]]
        top, right, bottom, left = ("h", i, j), ("v", i, j + 1), ("h", i + 1, j), ("v", i, j)
        crossed = [e for e, (p, q) in zip((top, right, bottom, left), ((0, 1), (1, 2), (3, 2), (0, 3))) if c[p] != c[q]]
        if len(crossed) == 2:
            join(*crossed)
            continue
        centre = (a[i, j] + a[i, j + 1] + a[i + 1, j + 1] + a[i + 1, j]) / 4 > 0.5
        if c[0] == centre:          # the corners that differ from the centre are cut off
            join(top, right)
            join(left, bottom)
        else:
            join(top, left)
            join(right, bottom)
    loops, seen = [], set()
    for start in link:
        if start in seen:
            continue
        loop, prev, e = [], None, start
        while e not in seen:
            seen.add(e)
            loop.append(cut(e))
            nxt = [n for n in link[e] if n != prev and n not in seen]
            prev, e = e, (nxt[0] if nxt else start)
        loops.append(loop)
    return loops


def simplify(pts, tol):
    """Douglas-Peucker on a closed outline, split at its two farthest points."""
    def dp(seg):
        if len(seg) < 3:
            return seg
        (x0, y0), (x1, y1) = seg[0], seg[-1]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1e-12
        d = [abs(dy * (x - x0) - dx * (y - y0)) / L for x, y in seg[1:-1]]
        k = max(range(len(d)), key=d.__getitem__)
        if d[k] <= tol:
            return [seg[0], seg[-1]]
        return dp(seg[:k + 2])[:-1] + dp(seg[k + 1:])
    far = max(range(len(pts)), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)
    return dp(pts[:far + 1])[:-1] + dp(pts[far:] + [pts[0]])[:-1]


def area(p):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(p, p[1:] + p[:1])) / 2


def inside(pt, poly):
    x, y, n = pt[0], pt[1], False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            n = not n
    return n


def outlines():
    f = font()
    # each letter where the face's own advance and kerning put it, TRACK further on per letter
    at = [f.getlength(NAME[:k + 1]) - f.getlength(NAME[k]) + k * TRACK * SIZE for k in range(len(NAME))]
    boxes = [f.getbbox(c, anchor="ls") for c in NAME]
    x0, y0 = min(a + b[0] for a, b in zip(at, boxes)), min(b[1] for b in boxes)
    x1, y1 = max(a + b[2] for a, b in zip(at, boxes)), max(b[3] for b in boxes)
    cap = -f.getbbox("H", anchor="ls")[1]              # px from the baseline to the top of H
    adv = at[-1] + f.getlength(NAME[-1])
    pad = 8
    img = Image.new("L", (math.ceil(x1 - x0) + 2 * pad, y1 - y0 + 2 * pad), 0)
    for a, c in zip(at, NAME):
        ImageDraw.Draw(img).text((pad - x0 + a, pad - y0), c, fill=255, font=f, anchor="ls")
    ox, oy = pad - x0 + adv / 2, pad - y0 - cap / 2      # the name's centre: half its advance, half its cap height
    loops = [[((x + 0.5 - 1 - ox) / cap, (y + 0.5 - 1 - oy) / cap) for x, y in l]   # +0.5: pixel centres; -1: the pad trace() adds
             for l in trace(np.asarray(img, dtype=float) / 255)]
    loops = [simplify(l, TOL) for l in loops if abs(area(l)) > 1e-4]
    depth = [sum(inside(l[0], m) for m in loops if m is not l) for l in loops]
    outer = [l if area(l) > 0 else l[::-1] for l, d in zip(loops, depth) if d % 2 == 0]
    for hole, d in zip(loops, depth):
        if d % 2 == 0:
            continue
        hole = hole if area(hole) < 0 else hole[::-1]
        k = min((o for o in range(len(outer)) if inside(hole[0], outer[o])), key=lambda o: abs(area(outer[o])))
        o = outer[k]
        i, j = min(((i, j) for i in range(len(o)) for j in range(len(hole))),
                   key=lambda ij: (o[ij[0]][0] - hole[ij[1]][0]) ** 2 + (o[ij[0]][1] - hole[ij[1]][1]) ** 2)
        outer[k] = o[:i + 1] + hole[j:] + hole[:j + 1] + o[i:]
    return outer, adv / cap


def gap(polys):
    """The narrowest gap between two outlines, mm at 1 mm cap height."""
    def d(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ((dx * dx + dy * dy) or 1e-12)))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
    return min(d(p, a, b) for i, P in enumerate(polys) for j, Q in enumerate(polys) if i != j
               for p in P for a, b in zip(Q, Q[1:] + Q[:1]))


def write():
    polys, width = outlines()
    ids = (str(uuid.uuid5(uuid.NAMESPACE_URL, f"picoquorum:PicoQuorum_Name:{k}")) for k in range(len(polys) + 2))
    items = [f'(fp_poly (pts {" ".join(f"(xy {x:.4f} {y:.4f})" for x, y in p)}) (stroke (width 0) (type solid)) (fill yes) '
             f'(layer "F.SilkS") (uuid "{next(ids)}"))' for p in polys]
    with open(OUT, "w") as fh:
        fh.write(f"""(footprint "PicoQuorum_Name" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")
(descr "The name PicoQuorum in Atkinson Hyperlegible Next Bold, 1 mm to the cap height, {width:.4f} mm of advance, centred; for silkscreen, scaled by the board's generator. docs/BRAND.md")
(tags "logo PicoQuorum")
(property "Reference" "LOGO2" (at 0 -1.5 0) (layer "F.SilkS") (hide yes) (uuid "{next(ids)}") (effects (font (size 1 1) (thickness 0.15))))
(property "Value" "PicoQuorum_Name" (at 0 1.5 0) (layer "F.Fab") (hide yes) (uuid "{next(ids)}") (effects (font (size 1 1) (thickness 0.15))))
(attr board_only exclude_from_pos_files exclude_from_bom allow_missing_courtyard)
{chr(10).join(items)}
(embedded_fonts no))
""")
    print(f"wrote {os.path.relpath(OUT, REPO)}: {len(polys)} outlines, {sum(map(len, polys))} points; a mm of cap height is "
          f"{width:.3f} mm wide, its letters {gap(polys):.3f} mm apart at the closest")


if __name__ == "__main__":
    write()
