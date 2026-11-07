"""Mono's board as a print: the 40 x 89.5 mm bar, its holes, and a block for each part JLCPCB fits, to its
height, with the panel on top. A rough model to hold in the hand and lay a case or a thumb against, not a
fit check (tools/jlc's fit3d.py is that).

Run: uv run --python 3.11 --with cadquery --with matplotlib python cad/mono/board.py

Writes out/: mono_board.stl (everything as one solid, the back down, as it prints), and the same split in
three for a print in colours: mono_board_pcb.stl, mono_board_parts.stl, mono_board_panel.stl. Also
mono_board.png, a picture of it.

Read from the routed board (hardware/mono/mono/mono.kicad_pcb): the outline, the holes, each fitted part's
place and turn, and its body from the footprint's F.Fab outline (its courtyard where it has none). The
heights, the glass and its foam are the generator's (gen_mono.py: HEIGHT, PANEL, GX0, GY0), which are
datasheet figures and guesses. Drawn here, not taken from the board:
- the glass's foam stands under all of it, 1 mm in from its edges, not on four pads, so the glass prints
  without support. The ribbon's fold is a 0.5 mm strip at the glass's right end.
- the picture's area is cut 0.2 mm into the glass.
- each switch is its body to 0.9 mm and a 3 mm round plunger to its 1.5 mm.
Not fitted, so not drawn: U7, U8, D2 and J4 (J4's five holes are). The jig's pads, the fiducials and the
mark are copper only.
"""
import importlib.util
import math
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
MONO = os.path.join(REPO, "hardware", "mono")
PCB = os.path.join(MONO, "mono", "mono.kicad_pcb")
OUT = os.path.join(HERE, "out")

_spec = importlib.util.spec_from_file_location("gen_mono", os.path.join(MONO, "gen_mono.py"))
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

T = 1.6                              # the board's thickness (JLCPCB's default; the generator's stackup)
SKIP = ("TP", "H", "FID", "LOGO", "LCD")     # copper only, holes, or the panel, drawn apart


# --- the board file ----------------------------------------------------------------------------------
def sexp(text):
    """KiCad's S-expressions as nested lists of strings."""
    out, stack, i, n = [], [], 0, len(text)
    cur = out
    while i < n:
        c = text[i]
        if c == "(":
            stack.append(cur)
            cur.append([])
            cur = cur[-1]
            i += 1
        elif c == ")":
            cur = stack.pop()
            i += 1
        elif c == '"':
            j = i + 1
            while text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            cur.append(text[i + 1:j])
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            cur.append(text[i:j])
            i = j
    return out[0]


def kids(node, key):
    return [k for k in node if isinstance(k, list) and k and k[0] == key]


def kid(node, key):
    k = kids(node, key)
    return k[0] if k else None


def footprints():
    """Each footprint: its reference, name, side, place (x, y, turn), attributes, body box, holes."""
    board = sexp(open(PCB).read())
    fps = []
    for f in kids(board, "footprint"):
        at = kid(f, "at")
        x, y, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        ref = next(p[2] for p in kids(f, "property") if p[1] == "Reference")
        attr = kid(f, "attr") or []
        body = {}
        for layer in ("F.Fab", "F.CrtYd"):
            pts = []
            for g in f:
                if not (isinstance(g, list) and g and g[0] in ("fp_line", "fp_rect", "fp_circle", "fp_poly", "fp_arc")):
                    continue
                if kid(g, "layer")[1] != layer:
                    continue
                if g[0] == "fp_circle":
                    cx, cy = map(float, kid(g, "center")[1:3])
                    ex, ey = map(float, kid(g, "end")[1:3])
                    r = math.hypot(ex - cx, ey - cy)
                    pts += [(cx - r, cy - r), (cx + r, cy + r)]
                elif g[0] == "fp_poly":
                    pts += [(float(p[1]), float(p[2])) for p in kids(kid(g, "pts"), "xy")]
                else:
                    pts += [tuple(map(float, kid(g, k)[1:3])) for k in ("start", "mid", "end") if kid(g, k)]
            if pts:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                body[layer] = (min(xs), min(ys), max(xs), max(ys))
        holes = []
        for p in kids(f, "pad"):
            if p[2] in ("thru_hole", "np_thru_hole") and kid(p, "drill"):
                d = kid(p, "drill")
                if "oval" in d:
                    continue        # J1's legs: under the part
                px, py = map(float, kid(p, "at")[1:3])
                holes.append((px, py, float(d[1])))
        fps.append(dict(ref=ref, name=f[1].split(":")[-1], side=kid(f, "layer")[1][0], x=x, y=y, rot=rot,
                        dnp="dnp" in attr, body=body.get("F.Fab") or body.get("F.CrtYd"), holes=holes))
    return fps


def place(fp, lx, ly):
    """A point in the footprint, as the model has it: millimetres from the board's bottom-left, y up."""
    a = math.radians(fp["rot"])
    x = fp["x"] + lx * math.cos(a) + ly * math.sin(a)
    y = fp["y"] - lx * math.sin(a) + ly * math.cos(a)
    return x - G.OX, G.OY + G.H - y


def up(y):
    """A y from the generator (from the board's top edge, down) as the model's."""
    return G.H - y


# --- the solids --------------------------------------------------------------------------------------
def block(fp, z0, z1, inset=0.0):
    x0, y0, x1, y1 = fp["body"]
    corners = [place(fp, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    w, h = max(xs) - min(xs) - 2 * inset, max(ys) - min(ys) - 2 * inset
    return (cq.Workplane("XY").box(w, h, z1 - z0, centered=False)
            .translate((min(xs) + inset, min(ys) + inset, z0)))


def board(fps):
    pcb = (cq.Workplane("XY").box(G.W, G.H - G.TOP, T, centered=False).translate((0, 0, -T))
           .edges("|Z").fillet(G.CORNER))
    for fp in fps:
        for hx, hy, d in fp["holes"]:
            if fp["ref"] == "J1":
                continue
            x, y = place(fp, hx, hy)
            pcb = pcb.cut(cq.Workplane("XY").circle(d / 2).extrude(T + 2).translate((x, y, -T - 1)))
    return pcb


def parts(fps):
    out, guessed = None, []
    for fp in fps:
        if fp["side"] != "F" or fp["dnp"] or fp["ref"].startswith(SKIP) or not fp["body"]:
            continue
        h = G.HEIGHT.get(fp["name"])
        if h is None:
            h = 1.0
            guessed.append(fp["ref"])
        if fp["name"].startswith("SW_Push"):
            s = block(fp, 0, 0.9)
            x, y = place(fp, 0, 0)
            s = s.union(cq.Workplane("XY").circle(1.5).extrude(h).translate((x, y, 0)))
        else:
            s = block(fp, 0, h)
        out = s if out is None else out.union(s)
    if guessed:
        print(f"  no height for {', '.join(guessed)}: taken as 1.0 mm")
    return out


def panel():
    P = G.PANEL
    x0, x1, y0, y1 = G.GX0, G.GX1, up(G.GY1), up(G.GY0)
    z0, z1 = P["foam"], P["foam"] + P["thick"]
    glass = cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))
    aw, ah = P["active"]
    ax, ay = G.XA, (y0 + y1) / 2
    glass = glass.cut(cq.Workplane("XY").box(aw, ah, 0.2 + 1, centered=False).translate((ax - aw / 2, ay - ah / 2, z1 - 0.2)))
    foam = cq.Workplane("XY").box(x1 - x0 - 2, y1 - y0 - 2, z0, centered=False).translate((x0 + 1, y0 + 1, 0))
    rib = P["ribbon"] / 2
    fold = cq.Workplane("XY").box(0.5, 2 * rib, z1, centered=False).translate((x1, up(G.YC) - rib, 0))
    return glass.union(foam).union(fold)


def picture(solids, path, size=1400):
    """The model from above, front and left, its faces shaded: a small z-buffer, for a look before printing."""
    import numpy as np
    import matplotlib.pyplot as plt

    az, el = math.radians(-30), math.radians(50)
    ca, sa, ce, se = math.cos(az), math.sin(az), math.cos(el), math.sin(el)
    light = np.array([-0.4, 0.5, 0.75])
    light /= np.linalg.norm(light)
    tris, cols = [], []
    for shape, rgb in solids:
        verts, idx = shape.val().tessellate(0.01, 0.2)
        v = np.array([(p.x, p.y, p.z) for p in verts])
        for t in idx:
            tris.append(v[list(t)])
            cols.append(rgb)
    tris, cols = np.array(tris), np.array(cols)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    shade = cols * (0.4 + 0.6 * np.clip(nrm @ light, 0, 1))[:, None]
    x, y, z = tris[..., 0], tris[..., 1], tris[..., 2]
    x1, y1 = ca * x - sa * y, sa * x + ca * y              # turn about z, then tip toward the eye
    sx, sy, depth = x1, ce * y1 + se * z, -se * y1 + ce * z
    lo, hi = np.array([sx.min(), sy.min()]), np.array([sx.max(), sy.max()])
    k = (size - 40) / (hi - lo).max()
    W, H = int((hi[0] - lo[0]) * k) + 40, int((hi[1] - lo[1]) * k) + 40
    px, py = (sx - lo[0]) * k + 20, H - ((sy - lo[1]) * k + 20)
    img, zb = np.ones((H, W, 3)), np.full((H, W), -np.inf)
    for i in range(len(tris)):
        (ax_, bx, cx), (ay, by, cy) = px[i], py[i]
        x0, x1_ = int(max(min(ax_, bx, cx), 0)), int(min(max(ax_, bx, cx), W - 1)) + 1
        y0, y1_ = int(max(min(ay, by, cy), 0)), int(min(max(ay, by, cy), H - 1)) + 1
        d = (by - cy) * (ax_ - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9 or x0 >= x1_ or y0 >= y1_:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1_) + 0.5, np.arange(y0, y1_) + 0.5)
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
        w1 = ((cy - ay) * (gx - cx) + (ax_ - cx) * (gy - cy)) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        zz = w0 * depth[i, 0] + w1 * depth[i, 1] + w2 * depth[i, 2]
        win = inside & (zz > zb[y0:y1_, x0:x1_])
        zb[y0:y1_, x0:x1_][win] = zz[win]
        img[y0:y1_, x0:x1_][win] = shade[i]
    plt.imsave(path, img)


def main():
    os.makedirs(OUT, exist_ok=True)
    fps = footprints()
    pcb, bits, glass = board(fps), parts(fps), panel()
    bits = bits.cut(glass)                     # J2 and its capacitors sit under the glass's foam
    whole = pcb.union(bits).union(glass)
    lift = (0, 0, T)                           # the back on the bed
    for name, s in (("mono_board", whole), ("mono_board_pcb", pcb), ("mono_board_parts", bits), ("mono_board_panel", glass)):
        cq.exporters.export(s.translate(lift), os.path.join(OUT, name + ".stl"), tolerance=0.01, angularTolerance=0.1)
    picture([(pcb, (0.18, 0.42, 0.25)), (bits, (0.75, 0.75, 0.72)), (glass, (0.12, 0.13, 0.16))],
            os.path.join(OUT, "mono_board.png"))
    bb = whole.val().BoundingBox()
    n = sum(1 for fp in fps if fp["side"] == "F" and not fp["dnp"] and not fp["ref"].startswith(SKIP) and fp["body"])
    print(f"wrote {os.path.relpath(OUT, REPO)}/: mono_board.stl, _pcb, _parts, _panel, .png; {n} parts; "
          f"{bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.2f} mm; one solid: {len(whole.val().Solids()) == 1}")


if __name__ == "__main__":
    main()
