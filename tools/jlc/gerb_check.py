# /// script
# requires-python = ">=3.12"
# dependencies = ["gerbonara==1.6.3", "numpy==2.5.3", "pillow==12.3.0"]
# [tool.uv]
# exclude-newer = "2026-10-09T00:00:00Z"
# ///
"""The files you upload, read back by code that isn't KiCad: gerbonara reads the Gerber and drill
zip, and each layer is drawn again here and laid over the board's own copper, mask, paste and silk
from facts.json (pcb_checks.py). Also the CPL overlay and the golden pictures. Run by
`tools/keypcb jlc`, through uv and this file's lock (gerb_check.py.lock), not by hand:

    uv run --locked --script gerb_check.py zip facts.json spec.json cpl.csv outdir golden_dir [--write-golden]

Every line it prints starts "ok", "warn", "FAIL" or "info".
"""
import csv, json, math, os, sys, warnings

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from gerbonara import LayerStack
from gerbonara.graphic_primitives import Arc, ArcPoly, Circle, Line, Rectangle, approximate_arc
from gerbonara.utils import MM

PX = 20                 # pixels a mm: 0.05 mm, a third of JLCPCB's 0.15 mm silk line
LAYERS = [("F.Cu", ("top", "copper")), ("B.Cu", ("bottom", "copper")), ("F.Mask", ("top", "mask")),
          ("B.Mask", ("bottom", "mask")), ("F.Paste", ("top", "paste")), ("B.Paste", ("bottom", "paste")),
          ("F.SilkS", ("top", "silk")), ("B.SilkS", ("bottom", "silk"))]
TOL = 0.01              # mm, where a drill hit may sit from the board's hole


def say(kind, text):
    print(f"  {kind:<4} {text}")
    return kind == "FAIL"


class Canvas:
    """A 1-bit picture of the board's box and a margin, board mm to pixels, y up."""

    def __init__(self, box, px=PX, margin=1.0):
        (self.x0, self.y0), (x1, y1) = box[0], box[1]
        self.x0, self.y0, self.px = self.x0 - margin, self.y0 - margin, px
        self.w, self.h = int((x1 + margin - self.x0) * px) + 1, int((y1 + margin - self.y0) * px) + 1

    def new(self):
        return np.zeros((self.h, self.w), bool)

    def p(self, x, y):
        return ((x - self.x0) * self.px, (self.h - 1) - (y - self.y0) * self.px)

    def fill(self, a, rings, dark=True):
        """Fill rings (lists of (x, y) mm) into a, even-odd, at pixel centres. Even-odd, so a hole
        joined to its outline by a zero-width cut (KiCad's pours in a Gerber) stays a hole."""
        e = []
        for ring in rings:
            q = np.array([self.p(*pt) for pt in ring], float)
            if len(q) > 2:
                e.append(np.hstack([q, np.roll(q, -1, axis=0)]))
        if not e:
            return
        e = np.vstack(e)
        e = e[e[:, 1] != e[:, 3]]
        if not len(e):
            return
        r0 = max(0, int(np.floor(min(e[:, 1].min(), e[:, 3].min()))))
        r1 = min(self.h - 1, int(np.ceil(max(e[:, 1].max(), e[:, 3].max()))))
        for r in range(r0, r1 + 1):
            yc = r + 0.5
            m = (np.minimum(e[:, 1], e[:, 3]) <= yc) & (np.maximum(e[:, 1], e[:, 3]) > yc)
            if not m.any():
                continue
            k = e[m]
            xs = np.sort(k[:, 0] + (yc - k[:, 1]) * (k[:, 2] - k[:, 0]) / (k[:, 3] - k[:, 1]))
            row = np.zeros(self.w + 1, int)
            for xa, xb in zip(xs[0::2], xs[1::2]):
                c0, c1 = max(0, int(np.ceil(xa - 0.5))), min(self.w, int(np.floor(xb - 0.5)) + 1)
                if c1 > c0:
                    row[c0] ^= 1
                    row[c1] ^= 1
            inside = np.cumsum(row[:-1]) % 2 == 1
            if dark:
                a[r] |= inside
            else:
                a[r] &= ~inside


def capsule(x1, y1, x2, y2, w, n=12):
    """A stroked line's outline: a round-ended rectangle, as a polygon."""
    a, r = math.atan2(y2 - y1, x2 - x1), w / 2
    pts = [(x2 + r * math.cos(a + math.pi / 2 - math.pi * k / n), y2 + r * math.sin(a + math.pi / 2 - math.pi * k / n)) for k in range(n + 1)]
    pts += [(x1 + r * math.cos(a - math.pi / 2 - math.pi * k / n), y1 + r * math.sin(a - math.pi / 2 - math.pi * k / n)) for k in range(n + 1)]
    return pts


def prim_polys(prim):
    """A gerbonara primitive as polygons (lists of (x, y) mm), with its polarity."""
    if isinstance(prim, Circle):
        return [[(prim.x + prim.r * math.cos(2 * math.pi * k / 48), prim.y + prim.r * math.sin(2 * math.pi * k / 48)) for k in range(48)]]
    if isinstance(prim, Line):
        return [capsule(prim.x1, prim.y1, prim.x2, prim.y2, prim.width)]
    if isinstance(prim, Arc):
        pts = list(approximate_arc(prim.cx, prim.cy, prim.x1, prim.y1, prim.x2, prim.y2, prim.clockwise, max_error=0.002))
        return [capsule(*a, *b, prim.width) for a, b in zip(pts, pts[1:])]
    if isinstance(prim, Rectangle):
        c, s = math.cos(prim.rotation), math.sin(prim.rotation)
        return [[(prim.x + c * dx - s * dy, prim.y + s * dx + c * dy) for dx, dy in
                 ((-prim.w / 2, -prim.h / 2), (prim.w / 2, -prim.h / 2), (prim.w / 2, prim.h / 2), (-prim.w / 2, prim.h / 2))]]
    if isinstance(prim, ArcPoly):
        return [prim.approximate_arcs(max_error=0.002).outline]
    raise TypeError(type(prim).__name__)


def draw_gerber(cv, layer):
    a = cv.new()
    for obj in layer.objects:
        for prim in obj.to_primitives(MM):
            if isinstance(prim, (Line, Arc)):      # a stroke: its pieces overlap, so each fills alone
                for poly in prim_polys(prim):
                    cv.fill(a, [poly], prim.polarity_dark)
            else:
                cv.fill(a, prim_polys(prim), prim.polarity_dark)
    return a


def draw_facts(cv, polys):
    a = cv.new()
    for rings in polys:
        cv.fill(a, rings)
    return a


def grow(a, n=1):
    for _ in range(n):
        b = a.copy()
        b[1:] |= a[:-1]; b[:-1] |= a[1:]; b[:, 1:] |= a[:, :-1]; b[:, :-1] |= a[:, 1:]
        a = b
    return a


def shrink(a, n=1):
    return ~grow(~a, n)


def differ(a, b):
    """Pixels well inside one picture and well clear of the other: a 0.05 mm edge either way is the
    two drawings' rounding, not a difference."""
    return (shrink(a) & ~grow(b)) | (shrink(b) & ~grow(a))


def where(cv, m):
    ys, xs = np.nonzero(m)
    return f"({cv.x0 + xs.min() / PX:.2f}, {cv.y0 + (cv.h - 1 - ys.max()) / PX:.2f})-({cv.x0 + xs.max() / PX:.2f}, {cv.y0 + (cv.h - 1 - ys.min()) / PX:.2f})"


# ------------------------------------------------------------------------------------------------
# pictures: the tightest spots, zoomed; the 3D fit from three sides
# ------------------------------------------------------------------------------------------------

MASK_GREEN, CU_UNDER, CU_BARE, FR4, SILK, HOLE = (25, 85, 45), (55, 125, 65), (214, 172, 72), (170, 160, 115), (240, 240, 240), (10, 10, 10)


def crop(st, side, at, half=1.6, px=90):
    """The board round a point drawn from the Gerbers: mask, copper, openings, silk, holes."""
    cv = Canvas(((at[0] - half, at[1] - half), (at[0] + half, at[1] + half)), px=px, margin=0)
    g = {k: draw_gerber(cv, st.graphic_layers[(side, k)]) for k in ("copper", "mask", "silk")}
    holes = cv.new()
    for d in (st.drill_pth, st.drill_npth):
        for o in d.objects:
            r = o.aperture.diameter / 2
            if type(o).__name__ == "Line":
                cv.fill(holes, [capsule(o.x1, o.y1, o.x2, o.y2, 2 * r)])
            else:
                cv.fill(holes, [[(o.x + r * math.cos(2 * math.pi * k / 40), o.y + r * math.sin(2 * math.pi * k / 40)) for k in range(40)]])
    rgb = np.empty(g["copper"].shape + (3,), np.uint8)
    rgb[:] = MASK_GREEN
    rgb[g["copper"]] = CU_UNDER
    rgb[g["mask"] & ~g["copper"]] = FR4
    rgb[g["mask"] & g["copper"]] = CU_BARE
    rgb[g["silk"]] = SILK
    rgb[holes] = HOLE
    img = Image.fromarray(rgb)
    if side == "bottom":
        img = img.transpose(Image.FLIP_LEFT_RIGHT)     # seen from the back, as it reads there
    return img, cv


def tight_sheet(st, tight, out):
    font, small = ImageFont.load_default(size=17), ImageFont.load_default(size=14)
    tiles = []
    for t in tight:
        side = "top" if t["side"] == "F" else "bottom"
        img, cv = crop(st, side, t["at"])
        d = ImageDraw.Draw(img)
        cx, cy = img.width / 2, img.height / 2
        d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], outline=(255, 40, 200), width=3)
        bar = ImageDraw.Draw(img)
        bar.line([(10, img.height - 14), (10 + cv.px, img.height - 14)], fill=(255, 255, 255), width=3)
        bar.text((14 + cv.px, img.height - 24), "1 mm", fill=(255, 255, 255), font=small)
        tile = Image.new("RGB", (img.width, img.height + 64), (245, 245, 240))
        tile.paste(img, (0, 64))
        td = ImageDraw.Draw(tile)
        lo = t["value"] < t["limit"] or not t["limit"]      # a limit of 0: a thing that shouldn't be there at all
        margin = (t["value"] / t["limit"]) if t["limit"] else 0
        td.text((6, 4), t["what"].replace("²", "2")[:38], fill=(20, 20, 20), font=font)
        td.text((6, 24), f"{t['value']:.3f} (limit {t['limit']}) at ({t['at'][0]:.2f}, {t['at'][1]:.2f})", fill=(20, 20, 20), font=small)
        td.text((6, 42), (("UNDER the limit" if t["limit"] else "FOUND") if lo else f"{margin:.1f}x the limit") + f", {side}", fill=(200, 30, 30) if lo else (30, 120, 50), font=small)
        tiles.append(tile)
    if not tiles:
        return
    cols = 4
    w, h = tiles[0].width, max(t.height for t in tiles)
    sheet = Image.new("RGB", (cols * (w + 10) + 10, ((len(tiles) + cols - 1) // cols) * (h + 10) + 10), (200, 200, 195))
    for k, t in enumerate(tiles):
        sheet.paste(t, (10 + (k % cols) * (w + 10), 10 + (k // cols) * (h + 10)))
    sheet.save(os.path.join(out, "tight-spots.png"))
    say("info", f"tight-spots.png: the {len(tiles)} tightest spots measured, each 3.2 mm across, drawn from the Gerbers")


def drill_picture(st, f, bad, out):
    """The board's front with each drill hit the file and the board disagree on ringed red."""
    cv = Canvas(f["outline"], px=30)
    cu, mk = draw_gerber(cv, st.graphic_layers[("top", "copper")]), draw_gerber(cv, st.graphic_layers[("top", "mask")])
    rgb = np.empty(cu.shape + (3,), np.uint8)
    rgb[:] = MASK_GREEN
    rgb[cu] = CU_UNDER
    rgb[cu & mk] = CU_BARE
    img = Image.fromarray(rgb)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=20)
    for what, (x, y, dia, _l) in bad:
        px, py = cv.p(x, y)
        d.ellipse([px - 18, py - 18, px + 18, py + 18], outline=(255, 30, 30), width=4)
        d.text((px + 22, py - 12), f"{what}: {dia} mm at ({x:.2f}, {y:.2f})", fill=(255, 60, 60), font=font)
    img.save(os.path.join(out, "drill-mismatch.png"))
    say("info", f"drill-mismatch.png: the {len(bad)} hits the drill file and the board disagree on")


KIND = {"part": (150, 150, 160), "extra": (175, 180, 190), "glass": (120, 190, 235), "guess": (240, 150, 60)}


def project(x, y, z, az, el):
    ca, sa, ce, se = math.cos(az), math.sin(az), math.cos(el), math.sin(el)
    u = x * ca - y * sa
    w = x * sa + y * ca
    return u, z * ce + w * se, w * ce - z * se          # screen x, screen up, depth (bigger is nearer the back)


def iso(fit, path, title, window=None, az=math.radians(-28), el=math.radians(38), size=1800):
    """Boxes drawn back to front: the board, each solid, the glass see-through, clashes red."""
    items = [("board", "board", fit["board"])] + [(s["name"], s["kind"], s["box"]) for s in fit["solids"]]
    if window:
        x0, y0, x1, y1 = window
        items = [(n, k, b) for n, k, b in items if b[3] > x0 and b[0] < x1 and b[4] > y0 and b[1] < y1]
        items = [(n, k, [max(b[0], x0), max(b[1], y0), b[2], min(b[3], x1), min(b[4], y1), b[5]]) for n, k, b in items]
    items = [it for it in items if it[2][5] > -0.01 or it[0] == "board"]      # the front face up
    pts = [project(x, y, z, az, el) for _, _, b in items for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]
    us, vs = [p[0] for p in pts], [p[1] for p in pts]
    k = (size - 120) / max(max(us) - min(us), (max(vs) - min(vs)) * 2.2)
    W, H = size, int((max(vs) - min(vs)) * k + 160)
    def S(x, y, z):
        u, v, _ = project(x, y, z, az, el)
        return (60 + (u - min(us)) * k, H - 70 - (v - min(vs)) * k)
    img = Image.new("RGBA", (W, H), (250, 250, 247, 255))
    faces = []
    for name, kind, b in items:
        x0, y0, z0, x1, y1, z1 = b
        col = (35, 110, 60) if kind == "board" else KIND.get(kind, (150, 150, 160))
        for quad, shade in (([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], 1.0),
                            ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], 0.72),
                            ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], 0.85),
                            ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], 0.6),
                            ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], 0.5)):
            depth = sum(project(*q, az, el)[2] for q in quad) / 4
            faces.append((depth, kind, [S(*q) for q in quad], tuple(int(c * shade) for c in col)))
    faces.sort(key=lambda f: -f[0])
    base = ImageDraw.Draw(img)
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glass)
    for depth, kind, poly, col in faces:
        if kind == "glass":
            gd.polygon(poly, fill=col + (70,), outline=(40, 90, 140, 200))
        else:
            base.polygon(poly, fill=col + (255,), outline=(60, 60, 60, 255))
    img = Image.alpha_composite(img, glass)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=22)
    for c in fit["clashes"]:
        x0, y0, z0, x1, y1, z1 = c["box"]
        for quad in ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]):
            d.polygon([S(*q) for q in quad], fill=(230, 30, 30, 255))
        sx, sy = S(x1, y0, z1)
        d.text((sx + 8, sy - 30), f"{c['a']} / {c['b']}" + (" (guessed)" if c["guess"] else ""), fill=(200, 0, 0, 255), font=font)
    for name, kind, b in items:
        if kind not in ("part", "board") and b[5] > 0:
            sx, sy = S((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[5])
            d.text((sx - 30, sy - 26), name, fill=(20, 20, 20, 255), font=font)
    d.text((20, 16), title, fill=(20, 20, 20, 255), font=ImageFont.load_default(size=28))
    img.convert("RGB").save(path)


def elevation(fit, path, title, axis, band, span, zx=4.0):
    """A section seen side on: axis "x" looks along y at the solids within band (y0, y1), over span
    (x0, x1); axis "y" looks along x. z is stretched zx times, so tenths of a mm show."""
    a, c = (0, 3) if axis == "x" else (1, 4)          # the horizontal axis's min and max in a box
    o, p = (1, 4) if axis == "x" else (0, 3)          # the axis looked along
    sol = [(s["name"], s["kind"], s["box"]) for s in fit["solids"] if s["box"][p] > band[0] and s["box"][o] < band[1]
           and s["box"][c] > span[0] and s["box"][a] < span[1]]
    zmin = min([fit["board"][2]] + [b[2] for _, _, b in sol]) - 0.3
    zmax = max([0] + [b[5] for _, _, b in sol]) + 0.6
    k = 1700 / (span[1] - span[0])
    W, H = 1800, int((zmax - zmin) * k * zx) + 150
    X = lambda h: 50 + (h - span[0]) * k
    Z = lambda z: H - 60 - (z - zmin) * k * zx
    img = Image.new("RGB", (W, H), (250, 250, 247))
    d = ImageDraw.Draw(img, "RGBA")
    font, small = ImageFont.load_default(size=20), ImageFont.load_default(size=16)
    bd = fit["board"]
    d.rectangle([X(max(bd[a], span[0])), Z(0), X(min(bd[c], span[1])), Z(bd[2])], fill=(35, 110, 60))
    for name, kind, b in sorted(sol, key=lambda s: s[1] == "glass"):
        col = KIND.get(kind, (150, 150, 160))
        fill = col + ((110,) if kind == "glass" else (230,))
        d.rectangle([X(max(b[a], span[0])), Z(b[5]), X(min(b[c], span[1])), Z(b[2])], fill=fill, outline=(50, 50, 50))
        if X(b[c]) - X(b[a]) > 28:
            d.text((X(max(b[a], span[0])) + 3, Z(b[5]) - 19), name, fill=(20, 20, 20), font=small)
    for cl in fit["clashes"]:
        b = cl["box"]
        if b[p] > band[0] and b[o] < band[1] and b[c] > span[0] and b[a] < span[1]:
            d.rectangle([X(b[a]), Z(b[5]), X(b[c]), Z(b[2])], fill=(230, 30, 30, 220))
            d.text((X(b[c]) + 6, Z(b[5]) + 2), f"{cl['a']} / {cl['b']}", fill=(200, 0, 0), font=font)
    # the gap under the glass, where it is least
    gl = next((b for n, kd, b in sol if kd == "glass"), None)
    if gl:
        under = [(b[5], n, b) for n, kd, b in sol if kd == "part" and b[a] < gl[c] and b[c] > gl[a] and b[5] > 0]
        if under:
            top, n, b = max(under)
            xm = X((max(b[a], gl[a]) + min(b[c], gl[c])) / 2)
            d.line([(xm, Z(top)), (xm, Z(gl[2]))], fill=(200, 0, 120), width=3)
            d.text((xm + 6, (Z(top) + Z(gl[2])) / 2 - 10), f"{gl[2] - top:.2f} mm, glass to {n}", fill=(200, 0, 120), font=font)
    for zz in (0, 1, 2, 3):
        if zmin < zz < zmax:
            d.line([(30, Z(zz)), (44, Z(zz))], fill=(80, 80, 80), width=2)
            d.text((4, Z(zz) - 8), f"{zz}", fill=(80, 80, 80), font=small)
    d.text((20, 12), f"{title} (z drawn {zx:g}x)", fill=(20, 20, 20), font=ImageFont.load_default(size=26))
    img.save(path)


def fit_views(fit, out):
    (bx0, by0, _, bx1, by1, _) = fit["board"]
    yc = (by0 + by1) / 2
    iso(fit, os.path.join(out, "fit-iso.png"), "console in 3D: courtyard boxes to their heights, the glass see-through")
    glass = next((s["box"] for s in fit["solids"] if s["kind"] == "glass"), None)
    if glass:
        iso(fit, os.path.join(out, "fit-fold.png"), "the glass's right end: the ribbon's fold (guessed) and what is near it",
            window=(glass[3] - 8, by0, min(bx1, glass[3] + 8), by1), az=math.radians(-55), el=math.radians(30))
        elevation(fit, os.path.join(out, "fit-side.png"), "side on, through the ribbon's path", "x", (yc - 2.5, yc + 2.5), (bx0, bx1))
    elevation(fit, os.path.join(out, "fit-end.png"), "the USB end, looking along the board", "y", (bx0, 9.0), (by0, by1), zx=2.0)
    say("info", "fit-iso.png, fit-fold.png, fit-side.png, fit-end.png: the 3D fit drawn from fit.json")


def main():
    zp, factsp, specp, cplp, out, golden = sys.argv[1:7]
    write_golden = "--write-golden" in sys.argv
    f, spec = json.load(open(factsp)), json.load(open(specp))
    os.makedirs(out, exist_ok=True)
    bad = False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)    # KiCad's drill files put G90 after the header; gerbonara says so
        st = LayerStack.open(zp)

    print("2. the Gerbers and drill files, read back")
    missing = [n for n, k in LAYERS if k not in st.graphic_layers] + [n for n, d in (("PTH", st.drill_pth), ("NPTH", st.drill_npth)) if d is None] \
        + (["outline"] if st.outline is None else [])
    bad |= say("FAIL" if missing else "ok", f"layers: {len(LAYERS)} graphic, the outline, PTH and NPTH drills" if not missing else f"missing: {missing}")
    if missing:
        sys.exit(1)

    (bx0, by0), (bx1, by1) = f["outline"]
    pts = [(o.x1, o.y1) for o in st.outline.objects] + [(o.x2, o.y2) for o in st.outline.objects]
    gx0, gy0 = min(p[0] for p in pts), min(p[1] for p in pts)
    gx1, gy1 = max(p[0] for p in pts), max(p[1] for p in pts)
    off = max(abs(gx0 - bx0), abs(gy0 - by0), abs(gx1 - bx1), abs(gy1 - by1))
    bad |= say("FAIL" if off > 0.001 else "ok", f"outline: {gx1 - gx0:.3f} x {gy1 - gy0:.3f} mm from ({gx0:.3f}, {gy0:.3f}), "
               + ("the board's" if off <= 0.001 else f"the board is {bx1 - bx0:.3f} x {by1 - by0:.3f}"))

    edge = min(spec.get("edge", 0.3), 0.3)
    for side in ("top", "bottom"):
        (cx0, cy0), (cx1, cy1) = st.graphic_layers[(side, "copper")].bounding_box(MM)
        m = min(cx0 - bx0, cy0 - by0, bx1 - cx1, by1 - cy1)
        bad |= say("FAIL" if m < edge - 0.005 else "ok", f"{side} copper: ({cx0:.2f}, {cy0:.2f})-({cx1:.2f}, {cy1:.2f}), {m:.3f} mm from the edge at the least (at least {edge})")
        for k in ("silk", "mask", "paste"):
            bb = st.graphic_layers[(side, k)].bounding_box(MM)
            if not bb:
                continue        # nothing on that layer
            (sx0, sy0), (sx1, sy1) = bb
            if sx0 < bx0 - 1e-3 or sy0 < by0 - 1e-3 or sx1 > bx1 + 1e-3 or sy1 > by1 + 1e-3:
                bad |= say("FAIL", f"{side} {k} runs off the board: ({sx0:.2f}, {sy0:.2f})-({sx1:.2f}, {sy1:.2f})")

    # holes: every hit is a hole in the board, every hole is a hit, in the right file
    def hits(d):
        out = []
        for o in d.objects:
            dia = o.aperture.diameter
            if type(o).__name__ == "Line":
                out.append(((o.x1 + o.x2) / 2, (o.y1 + o.y2) / 2, dia, math.hypot(o.x2 - o.x1, o.y2 - o.y1) + dia))
            else:
                out.append((o.x, o.y, dia, dia))
        return out
    want_pth = [(v["at"][0], v["at"][1], v["drill"], v["drill"]) for v in f["vias"]] + \
               [(p["at"][0], p["at"][1], min(p["drill"]), max(p["drill"])) for p in f["pads"] if p["kind"] == "pth"]
    want_npth = [(p["at"][0], p["at"][1], min(p["drill"]), max(p["drill"])) for p in f["pads"] if p["kind"] == "npth"]
    drill_bad = []
    for name, got, want in (("PTH", hits(st.drill_pth), want_pth), ("NPTH", hits(st.drill_npth), want_npth)):
        left = list(want)
        extra = []
        for g in got:
            m = next((w for w in left if abs(w[0] - g[0]) < TOL and abs(w[1] - g[1]) < TOL and abs(w[2] - g[2]) < 0.001 and abs(w[3] - g[3]) < 0.01), None)
            if m:
                left.remove(m)
            else:
                extra.append(g)
        drill_bad += [("extra", g) for g in extra] + [("missing", w) for w in left]
        sizes = sorted({g[2] for g in got})
        slots = sum(1 for g in got if g[3] > g[2] + 1e-6)
        bad |= say("FAIL" if extra or left else "ok", f"{name}: {len(got)} hits ({slots} slots), {len(sizes)} drill sizes {sizes} mm" +
                   ("; each the board's" if not (extra or left) else f"; in the file, not the board: {extra[:4]}; the board's, not in the file: {left[:4]}"))
    dsizes = sorted({g[2] for g in hits(st.drill_pth) + hits(st.drill_npth)})
    say("info", f"{len(dsizes)} drill sizes in all: {dsizes} mm")

    # pads: the copper layers' pad flashes carry KiCad's .P (ref, pad) and .N (net) attributes
    for side, key in (("top", "front"), ("bottom", "back")):
        got = {}
        for o in st.graphic_layers[(side, "copper")].objects:
            a = getattr(o, "attrs", None)
            if isinstance(a, dict) and ".P" in a:
                got[(a[".P"][0], a[".P"][1])] = (a.get(".N") or ("",))[0]
        want = {(p["ref"], p["num"]): p["net"] for p in f["pads"] if p[key] and p["kind"] in ("smd", "pth", "conn") and p["num"]}
        wrong = [f"{r}.{n} {got.get((r, n))!r} not {want[(r, n)]!r}" for r, n in want if (r, n) in got and got[(r, n)] != want[(r, n)]]
        lost = [f"{r}.{n}" for r, n in want if (r, n) not in got]
        bad |= say("FAIL" if wrong or lost else "ok", f"{side} pads: {len(got)} in the Gerber, each the board's pad on the board's net" if not (wrong or lost)
                   else f"{side} pads: missing {lost[:6]}, on another net {wrong[:6]}")

    # each layer drawn from the Gerber against the board's own shapes
    cv = Canvas(f["outline"])
    pics = {}
    for name, key in LAYERS:
        pics[name] = (draw_gerber(cv, st.graphic_layers[key]), draw_facts(cv, f["layers"][name]))
    for side in ("F", "B"):     # KiCad takes the mask openings out of the silk it plots
        g, b = pics[f"{side}.SilkS"]
        pics[f"{side}.SilkS"] = (g, b & ~pics[f"{side}.Mask"][1])
    worst = []
    for name, (g, b) in pics.items():
        m = differ(g, b)
        n = int(m.sum())
        if n:
            worst.append(f"{name} {n / PX / PX:.3f} mm² at {where(cv, m)}")
            Image.fromarray((np.dstack([g, b, np.zeros_like(g)]) * 255).astype(np.uint8)).save(os.path.join(out, f"diff-{name}.png"))
    bad |= say("FAIL" if worst else "ok", f"each layer drawn from the Gerber matches the board's shapes to {1 / PX:.2f} mm" if not worst
               else f"the Gerber and the board differ: {worst} (pictures: diff-<layer>.png, red the Gerber, green the board)")

    # 9. the golden pictures: what moved since they were written
    print("9. against the golden pictures")
    os.makedirs(golden, exist_ok=True)
    changed = []
    for name, (g, _b) in pics.items():
        gp = os.path.join(golden, f"{name}.png")
        if write_golden:
            Image.fromarray(g).save(gp, optimize=True)
            continue
        if not os.path.exists(gp):
            changed.append(f"{name} (no golden picture)")
            continue
        old = np.array(Image.open(gp), dtype=bool)
        if old.shape != g.shape:
            changed.append(f"{name} (size {old.shape[::-1]} -> {g.shape[::-1]})")
            continue
        m = old ^ g
        if m.any():
            changed.append(f"{name} {m.sum() / PX / PX:.3f} mm² at {where(cv, m)}")
            rgb = np.full(g.shape + (3,), 40, np.uint8)
            rgb[old & g] = (110, 110, 110)
            rgb[old & ~g] = (230, 60, 60)
            rgb[g & ~old] = (60, 200, 90)
            Image.fromarray(rgb).save(os.path.join(out, f"changed-{name}.png"))
    if write_golden:
        say("ok", f"golden pictures written: {os.path.relpath(golden)}")
    else:
        say("warn" if changed else "ok", "every layer as the golden pictures" if not changed else
            f"changed since the golden pictures: {changed} (changed-<layer>.png: red gone, green new)")
        if changed and "--strict" in sys.argv:
            bad = True

    # 4. the CPL drawn on the front: an arrow for each part's rotation, a dot on its pin 1
    rows = list(csv.DictReader(open(cplp)))
    S = 3
    big = Image.new("RGB", (cv.w * S, cv.h * S), (20, 60, 35))
    for name, colour in (("F.Cu", (60, 110, 60)), ("F.Mask", (200, 170, 70)), ("F.SilkS", (235, 235, 235))):
        m = Image.fromarray(pics[name][0]).resize((cv.w * S, cv.h * S))
        big.paste(colour, mask=m)
    d = ImageDraw.Draw(big)
    font = ImageFont.load_default(size=26)
    pads = {}
    for p in f["pads"]:
        pads.setdefault(p["ref"], {})[p["num"]] = p["at"]
    for r in rows:
        x, y = float(r["Mid X"].rstrip("m")), float(r["Mid Y"].rstrip("m"))
        a = math.radians(float(r["Rotation"]))
        px, py = cv.p(x, y)
        ex, ey = cv.p(x + 1.5 * math.cos(a), y + 1.5 * math.sin(a))
        d.line([(px * S, py * S), (ex * S, ey * S)], fill=(230, 40, 200), width=4)
        d.ellipse([ex * S - 6, ey * S - 6, ex * S + 6, ey * S + 6], fill=(230, 40, 200))
        one = pads.get(r["Designator"], {})
        pin1 = one.get("1") or one.get("A1")
        if pin1 and len(one) > 2:
            qx, qy = cv.p(*pin1)
            d.ellipse([qx * S - 8, qy * S - 8, qx * S + 8, qy * S + 8], outline=(40, 200, 255), width=4)
        d.text((px * S + 10, py * S + 6), r["Designator"], fill=(255, 255, 0), font=font)
    big.save(os.path.join(out, "cpl-overlay.png"))
    tp = os.path.join(out, "tight.json")
    if drill_bad and not os.path.exists(tp):
        drill_picture(st, f, drill_bad, out)
    if os.path.exists(tp):
        print("pictures")
        tight_sheet(st, json.load(open(tp)), out)
        if drill_bad:
            drill_picture(st, f, drill_bad, out)
        fp = os.path.join(out, "fit.json")
        if os.path.exists(fp):
            fit_views(json.load(open(fp)), out)
    say("info", f"cpl-overlay.png: {len(rows)} CPL rows; the magenta arrow is each part's rotation (0 points right), "
        "the blue ring pin 1. Hold it beside JLCPCB's placement preview")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
