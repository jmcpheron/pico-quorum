#!/usr/bin/env python3
"""console-s3's renders, drawn from the generator's own geometry: no KiCad, no 3D models.

    python3 hardware/console-s3/render.py          writes renders/*.jpg
    (or: uv run --with numpy --with pillow python3 hardware/console-s3/render.py)

Every position, turn, side and pad comes from gen_console_s3.py, so a render can't drift from the
board. The parts are plain blocks at their datasheet sizes, coloured by kind; the board's faces are
textures (mask, pads, silkscreen); the panel shows a real screen from the Feather
(docs/quorum-ui/feather). A small z-buffered rasterizer in numpy draws them at twice the size and
Pillow shrinks the picture, so the edges are smooth. Nothing is random: a rerun writes the same file.

World frame: the board frame (mm, origin at the bottom-left corner looking at the front, x along
the board, y up the page), and z out of the front. The front face is z = 0, the back z = -1.6.
"""
import importlib.util, math, os, re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
_spec = importlib.util.spec_from_file_location("s3", os.path.join(HERE, "gen_console_s3.py"))
s3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s3)       # the generator; it writes nothing on import
s3.place_switches()
OUT = os.path.join(HERE, "renders")
SCREEN = os.path.join(REPO, "docs", "quorum-ui", "feather", "05-review-to.png")

W, H, YC, T = s3.W, s3.H, s3.YC, 1.6
PX = 40                              # texture pixels a mm
MASK, SILK, HASL, FR4 = (28, 112, 58), (238, 240, 236), (196, 198, 196), (176, 172, 120)
BLACK, METAL, GOLD = (32, 32, 34), (192, 194, 198), (206, 168, 82)
SPEC = {"metal": 0.4, "glass": 0.35, "plain": 0.06}   # none on a textured face: it would show its triangles


def board_xy(pt):
    """A page point from the generator, in the board frame."""
    return pt[0] - s3.OX, s3.OY - pt[1]


# =================================================================================================
# The board's faces, as textures
# =================================================================================================

def _pads(side):
    """(kind, shape, x0, y0, x1, y1) in the board frame for every copper pad and plain hole on a side."""
    out = []
    for ref, p in s3.all_parts().items():
        fp = s3.FOOTPRINTS[p["fp"]]()
        for it in fp["items"]:
            if it[0] != "pad":
                continue
            _, num, kind, shape, lx, ly, w, h, _drill, layers = it
            copper = [l for l in layers if l.endswith(".Cu")]
            if kind == "smd":
                if not copper or (p["side"] == "B") != (side == "B"):
                    continue
            if round(p["rot"]) % 180:
                w, h = h, w
            x, y = board_xy(s3.world(p, lx, ly))
            out.append((kind, shape, x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    return out


def _logo(draw, name, x, y, k):
    """A logo from lib/picoquorum.pretty, white, its origin at (x, y) in texture px, k texture px a mm
    of the footprint, as it reads from its own side (the back is mirrored afterwards)."""
    src = s3._logo(name)[1]
    for pts in re.findall(r"\(fp_poly \(pts (.*?)\) \(stroke", src):
        draw.polygon([(x + float(a) * k, y + float(b) * k) for a, b in re.findall(r"\(xy ([\-\d.]+) ([\-\d.]+)\)", pts)], fill=SILK)
    for cx, cy, ex, w in re.findall(r"\(fp_circle \(center ([\-\d.]+) ([\-\d.]+)\) \(end ([\-\d.]+) [\-\d.]+\) \(stroke \(width ([\d.]+)\)", src):
        r, w = abs(float(ex) - float(cx)), float(w)
        cx, cy = x + float(cx) * k, y + float(cy) * k
        if w == 0:
            draw.ellipse([cx - r * k, cy - r * k, cx + r * k, cy + r * k], fill=SILK)
        else:            # a ring keeps its 0.15 mm line at any scale, as on the board
            out = (r + w / 2) * k
            draw.ellipse([cx - out, cy - out, cx + out, cy + out], outline=SILK, width=max(1, round(w * PX)))


def face_texture(side):
    """The front (side "F") or the back ("B") as an image in the board frame: column 0 at x = 0,
    row 0 at y = H. The back is drawn as seen from the back and then mirrored, so its text reads."""
    w, h = int(W * PX), int(H * PX)
    img = Image.new("RGB", (w, h), MASK)
    d = ImageDraw.Draw(img)
    back = side == "B"

    def X(x):
        return (W - x if back else x) * PX

    def Y(y):
        return (H - y) * PX

    font = lambda mm: ImageFont.load_default(size=int(mm * PX * 1.25))

    def text(s, x, y, mm=0.8):
        d.text((X(x), Y(y)), s, fill=SILK, font=font(mm), anchor="mm")

    for kind, shape, x0, y0, x1, y1 in _pads(side):
        box = [min(X(x0), X(x1)), Y(y1), max(X(x0), X(x1)), Y(y0)]
        if kind == "np_thru_hole":
            d.ellipse(box, fill=(18, 20, 18))
        elif shape in ("circle", "oval"):
            d.rounded_rectangle(box, radius=min(box[2] - box[0], box[3] - box[1]) / 2, fill=HASL)
        else:
            d.rounded_rectangle(box, radius=0.08 * PX if shape == "roundrect" else 0, fill=HASL)
    if not back:
        gx0, gy0, gx1, gy1 = s3.GLASS
        for x, dx in ((gx0, 2.5), (gx1, -2.5)):
            for y, dy in ((gy0, 2.0), (gy1, -2.0)):
                d.line([X(x), Y(y), X(x + dx), Y(y)], fill=SILK, width=int(0.15 * PX))
                d.line([X(x), Y(y), X(x), Y(y + dy)], fill=SILK, width=int(0.15 * PX))
    for name, x, y, k, on in s3.silk_logos():
        if (on == "B") == back:
            _logo(d, name, X(x), Y(y), k * PX)
    for t, x, y, on in s3.silk_texts():
        if (on == "B") == back:
            text(t, x, y, s3.SILK_H)
    for x0, y0, x1, y1, on in s3.silk_pixels():
        if (on == "B") == back:
            d.rectangle([min(X(x0), X(x1)), Y(y1), max(X(x0), X(x1)), Y(y0)], fill=SILK)
    return np.asarray(img.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if back else img)


def screen_texture():
    """The glass from above: a black border round the active area, which shows the Feather's
    240 x 135 screen (the emulator's shot, less its strip of button dots on the left)."""
    gw, gh = s3.PANEL["glass"]
    aw, ah = s3.PANEL["active"]
    k = 30
    img = Image.new("RGB", (int(gw * k), int(gh * k)), (14, 14, 16))
    shot = Image.open(SCREEN).convert("RGB")
    sw, sh = shot.size
    shot = shot.crop((sw - sh * 240 // 135, 0, sw, sh)).resize((int(aw * k), int(ah * k)), Image.Resampling.LANCZOS)
    img.paste(shot, (int((gw - aw) / 2 * k), int((gh - ah) / 2 * k - s3.PANEL["active_dy"] * k)))
    return np.asarray(img)


# =================================================================================================
# The scene: triangles with a colour or a texture
# =================================================================================================

class Scene:
    def __init__(self):
        self.tris = []      # (3x3 vertices, colour or None, material, texture index or None, 3x2 uv or None)
        self.tex = []

    def tri(self, a, b, c, colour=None, mat="plain", tex=None, uv=None):
        self.tris.append((np.array([a, b, c], float), colour, mat, tex, None if uv is None else np.array(uv, float)))

    def quad(self, a, b, c, d, colour=None, mat="plain", tex=None, uv=None):
        self.tri(a, b, c, colour, mat, tex, None if uv is None else uv[:3])
        self.tri(a, c, d, colour, mat, tex, None if uv is None else [uv[0], uv[2], uv[3]])

    def box(self, x0, y0, z0, x1, y1, z1, colour, mat="plain"):
        x0, x1, y0, y1, z0, z1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for a, b, c, d in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.quad(v[a], v[b], v[c], v[d], colour, mat)

    def cylinder(self, cx, cy, z0, z1, r, colour, mat="plain", n=28):
        ring = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        for k in range(n):
            (ax, ay), (bx, by) = ring[k], ring[(k + 1) % n]
            self.quad((ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1), colour, mat)
            self.tri((cx, cy, z1), (ax, ay, z1), (bx, by, z1), colour, mat)
            self.tri((cx, cy, z0), (ax, ay, z0), (bx, by, z0), colour, mat)


def outline(n=8):
    """The board's outline, anticlockwise, with the generator's rounded corners."""
    r, pts = s3.CORNER, []
    for cx, cy, a0 in ((W - r, r, -90), (W - r, H - r, 0), (r, H - r, 90), (r, r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def add_board(sc):
    front, back = face_texture("F"), face_texture("B")
    sc.tex += [front, back]
    tf, tb = len(sc.tex) - 2, len(sc.tex) - 1
    pts = outline()
    # each face as a fan from the centre: the outline is convex
    c = (W / 2, H / 2)
    uv = lambda x, y: (x / W, 1 - y / H)
    for k in range(len(pts)):
        a, b = pts[k], pts[(k + 1) % len(pts)]
        sc.tri((*c, 0), (*a, 0), (*b, 0), tex=tf, uv=[uv(*c), uv(*a), uv(*b)])
        sc.tri((*c, -T), (*a, -T), (*b, -T), tex=tb, uv=[uv(*c), uv(*a), uv(*b)])
        sc.quad((*a, 0), (*b, 0), (*b, -T), (*a, -T), FR4)


def part_box(sc, p, lx0, ly0, lx1, ly1, z0, z1, colour, mat="plain"):
    """A block in a part's own frame (footprint coordinates, z up from its side of the board),
    turned and flipped as the part is."""
    (ax, ay), (bx, by) = board_xy(s3.world(p, lx0, ly0)), board_xy(s3.world(p, lx1, ly1))
    if p["side"] == "B":
        z0, z1 = -T - z0, -T - z1
    sc.box(ax, ay, z0, bx, by, z1, colour, mat)


def two_terminal(sc, p, l, w, h, body, ends):
    part_box(sc, p, -l / 2 + 0.3, -w / 2, l / 2 - 0.3, w / 2, 0, h, body)
    for s in (-1, 1):
        part_box(sc, p, s * l / 2, -w / 2, s * (l / 2 - 0.3), w / 2, 0, h, ends, "metal")


def add_parts(sc, panel=True):
    for ref, p in s3.PARTS.items():
        fp = p["fp"]
        if fp == "R_0603":
            two_terminal(sc, p, 1.6, 0.8, 0.45, BLACK, METAL)
        elif fp == "C_0603":
            two_terminal(sc, p, 1.6, 0.8, 0.8, (170, 138, 96), METAL)
        elif fp == "LED_0603":
            two_terminal(sc, p, 1.6, 0.8, 0.6, (232, 70, 60), METAL)
        elif fp == "SOT-23":
            part_box(sc, p, -1.45, -0.65, 1.45, 0.65, 0.1, 1.0, BLACK)
            for lx, ly in ((-0.95, 1.1), (0.95, 1.1), (0, -1.1)):
                part_box(sc, p, lx - 0.2, ly - 0.45, lx + 0.2, ly + 0.45, 0, 0.12, METAL, "metal")
        elif fp in ("SOT-23-5", "SOT-23-6"):
            part_box(sc, p, -0.8, -1.45, 0.8, 1.45, 0.1, 1.1, BLACK)
            for it in s3.FOOTPRINTS[fp]()["items"]:
                if it[0] == "pad":
                    part_box(sc, p, it[4] - 0.5, it[5] - 0.2, it[4] + 0.5, it[5] + 0.2, 0, 0.12, METAL, "metal")
        elif fp == "DFN-8-1EP_3x2mm_P0.5mm":
            part_box(sc, p, -1.5, -1.0, 1.5, 1.0, 0, 0.55, BLACK)
        elif fp == "SW_TS-1187A":
            part_box(sc, p, -2.55, -2.55, 2.55, 2.55, 0, 0.7, (46, 46, 48))
            part_box(sc, p, -2.4, -2.4, 2.4, 2.4, 0.7, 0.95, METAL, "metal")
            for lx in (-3.0, 3.0):
                for ly in (-1.875, 1.875):
                    part_box(sc, p, lx - 0.45, ly - 0.3, lx + 0.45, ly + 0.3, 0, 0.15, METAL, "metal")
            x, y = p["at"]
            sc.cylinder(x, y, 0.95, 1.5, 1.5, (28, 28, 30))
        elif fp.startswith("USB_C"):
            part_box(sc, p, -4.47, -3.675, 4.47, 3.675, 0, 3.26, METAL, "metal")
            part_box(sc, p, -4.0, 3.675, 4.0, 3.70, 0.4, 2.86, (12, 12, 14))     # the mouth
            part_box(sc, p, -2.9, 3.0, 2.9, 3.71, 1.45, 2.05, (226, 226, 226))     # its tongue
        elif fp.startswith("FPC_ZIF"):
            part_box(sc, p, -3.0, -1.0, 3.0, 1.6, 0, 1.0, (222, 206, 170))
            part_box(sc, p, -3.0, -1.65, 3.0, -1.0, 0, 1.05, (40, 40, 42))     # the actuator
        elif fp == "ESP32-S3-WROOM-1":
            add_module(sc, p)
    if panel:
        add_panel(sc)


def add_module(sc, p):
    """The module: its 0.8 mm board, the 15.8 x 17.6 mm can (datasheet v1.8, Figure 10-1: 3.1 mm in
    all), gold castellations, and the antenna end bare with a meander on it."""
    hw, hl = s3.MOD_W / 2, s3.MOD_L / 2
    part_box(sc, p, -hw, -hl, hw, hl, 0, 0.8, (34, 38, 52))
    part_box(sc, p, -7.9, hl - 1.05 - 17.6, 7.9, hl - 1.05, 0.8, 3.1, METAL, "metal")
    for it in s3.FOOTPRINTS["ESP32-S3-WROOM-1"]()["items"]:
        if it[0] == "pad" and it[1] != "41":
            lx, ly, w, h = it[4], it[5], it[6], it[7]
            if abs(lx) > hw - 1:
                lx0, lx1 = (hw - 0.4, hw + 0.01) if lx > 0 else (-hw - 0.01, -hw + 0.4)
                part_box(sc, p, lx0, ly - 0.3, lx1, ly + 0.3, 0, 0.81, GOLD, "metal")
            else:
                part_box(sc, p, lx - 0.3, hl - 0.4, lx + 0.3, hl + 0.01, 0, 0.81, GOLD, "metal")
    ya = -hl + 1.0
    xs = [-7.5 + 1.5 * k for k in range(11)]
    for k, x in enumerate(xs[:-1]):                      # the meander: up, across, down, across
        part_box(sc, p, x - 0.25, ya, x + 0.25, ya + 3.8, 0.8, 0.83, GOLD, "metal")
        y = ya + 3.8 if k % 2 == 0 else ya
        part_box(sc, p, x - 0.25, y - 0.25, xs[k + 1] + 0.25, y + 0.25, 0.8, 0.83, GOLD, "metal")


def add_panel(sc):
    """The foam tape, the glass with the screen on it, and the ribbon folding under its right end."""
    gx0, gy0, gx1, gy1 = s3.GLASS
    foam, gt = s3.PANEL["foam"], 1.6
    for x0, y0, x1, y1 in ((gx0 + 0.5, gy0 + 0.5, gx1 - 0.5, gy0 + 2.5), (gx0 + 0.5, gy1 - 2.5, gx1 - 0.5, gy1 - 0.5)):
        sc.box(x0, y0, 0, x1, y1, foam, (52, 52, 54))
    z0, z1 = foam, foam + gt
    sc.tex.append(screen_texture())
    t = len(sc.tex) - 1
    sc.quad((gx0, gy0, z1), (gx1, gy0, z1), (gx1, gy1, z1), (gx0, gy1, z1), tex=t, mat="glass", uv=[(0, 1), (1, 1), (1, 0), (0, 0)])
    rim = (24, 24, 26)
    sc.quad((gx0, gy0, z0), (gx1, gy0, z0), (gx1, gy1, z0), (gx0, gy1, z0), rim)
    for a, b in (((gx0, gy0), (gx1, gy0)), ((gx1, gy0), (gx1, gy1)), ((gx1, gy1), (gx0, gy1)), ((gx0, gy1), (gx0, gy0))):
        sc.quad((*a, z0), (*b, z0), (*b, z1), (*a, z1), (70, 72, 76), "glass")
    # the ribbon: out of the glass's right end, round a 1 mm bend, back under the glass into J2
    amber, rw, r = (196, 128, 36), 4.5 / 2, (z0 + 0.1 - 0.1) / 2
    cx, cz = gx1 + 0.8, 0.1 + r
    path = [(gx1 - 0.5, z0 + 0.1), (gx1 + 0.8, z0 + 0.1)]
    path += [(cx + r * math.sin(math.pi * k / 12), cz + r * math.cos(math.pi * k / 12)) for k in range(1, 12)]
    j2 = s3.PARTS["J2"]["at"][0]
    path += [(gx1 + 0.8, 0.1), (j2 + 1.0, 0.1)]
    for (ax, az), (bx, bz) in zip(path, path[1:]):
        sc.quad((ax, YC - rw, az), (bx, YC - rw, bz), (bx, YC + rw, bz), (ax, YC + rw, az), amber)


# =================================================================================================
# The renderer
# =================================================================================================

def look_at(eye, target, up):
    eye, target, up = (np.array(v, float) for v in (eye, target, up))
    fwd = target - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    right /= np.linalg.norm(right)
    return eye, right, np.cross(right, fwd), fwd


def render(sc, eye, target, up, light, width=1600, fov=24.0, ss=2):
    """The scene from eye, cropped to the board with a margin, width pixels wide."""
    w, h = 1600 * ss, 1000 * ss
    eye, right, upv, fwd = look_at(eye, target, up)
    f = (h / 2) / math.tan(math.radians(fov) / 2)
    light = np.array(light, float) / np.linalg.norm(light)
    view = -fwd                                              # one view direction: a flat face has one highlight
    half = (light + view) / np.linalg.norm(light + view)
    zbuf = np.full((h, w), np.inf, np.float32)
    top, bottom = np.array([248, 248, 246], float), np.array([222, 224, 226], float)
    img = (top + (bottom - top) * np.linspace(0, 1, h)[:, None, None] * np.ones((1, w, 1))).astype(np.float32)
    for v, colour, mat, tex, uv in sc.tris:
        rel = v - eye
        cz = rel @ fwd
        if np.any(cz <= 1e-3):
            continue
        sx = w / 2 + f * (rel @ right) / cz
        sy = h / 2 - f * (rel @ upv) / cz
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(area) < 1e-9:
            continue
        x0, x1 = max(int(math.floor(sx.min())), 0), min(int(math.ceil(sx.max())), w - 1)
        y0, y1 = max(int(math.floor(sy.min())), 0), min(int(math.ceil(sy.max())), h - 1)
        if x0 > x1 or y0 > y1:
            continue
        px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        b0 = ((sx[1] - px) * (sy[2] - py) - (sx[2] - px) * (sy[1] - py)) / area
        b1 = ((sx[2] - px) * (sy[0] - py) - (sx[0] - px) * (sy[2] - py)) / area
        b2 = 1 - b0 - b1
        inside = (b0 >= -1e-6) & (b1 >= -1e-6) & (b2 >= -1e-6)
        if not inside.any():
            continue
        iz = b0 / cz[0] + b1 / cz[1] + b2 / cz[2]          # 1/depth, which is linear on the screen
        depth = 1 / np.where(inside, iz, 1e-9)
        region = zbuf[y0:y1 + 1, x0:x1 + 1]
        hit = inside & (depth < region)
        if not hit.any():
            continue
        region[hit] = depth[hit]
        n = np.cross(v[1] - v[0], v[2] - v[0])
        n /= np.linalg.norm(n)
        if n @ (eye - v[0]) < 0:
            n = -n                                           # light the side that faces the camera
        shade = 0.42 + 0.58 * max(0.0, n @ light)
        spec = 0.0 if tex is not None else SPEC[mat] * max(0.0, n @ half) ** 48 * 255
        if tex is not None:
            t = sc.tex[tex]
            u = (b0 * uv[0, 0] / cz[0] + b1 * uv[1, 0] / cz[1] + b2 * uv[2, 0] / cz[2]) / iz
            vv = (b0 * uv[0, 1] / cz[0] + b1 * uv[1, 1] / cz[1] + b2 * uv[2, 1] / cz[2]) / iz
            tx = np.clip((u[hit] * t.shape[1]).astype(int), 0, t.shape[1] - 1)
            ty = np.clip((vv[hit] * t.shape[0]).astype(int), 0, t.shape[0] - 1)
            col = t[ty, tx].astype(np.float32) * (shade if mat != "glass" else 0.92 + 0.08 * shade)
        else:
            col = np.array(colour, np.float32) * shade
        img[y0:y1 + 1, x0:x1 + 1][hit] = np.clip(col + spec, 0, 255)
    ys, xs = np.nonzero(np.isfinite(zbuf))
    m = int(0.06 * max(xs.max() - xs.min(), ys.max() - ys.min()))
    box = (max(xs.min() - m, 0), max(ys.min() - m, 0), min(xs.max() + m, w), min(ys.max() + m, h))
    out = Image.fromarray(img.astype(np.uint8)).crop(box)
    return out.resize((width, round(width * out.height / out.width)), Image.Resampling.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    c = (W / 2, YC, 0)
    views = [
        ("console-s3-3q-top.jpg", True, dict(eye=(W / 2 - 48, YC - 92, 78), target=c, up=(0, 0, 1), light=(-0.35, -0.55, 1.0))),
        ("console-s3-3q-top-bare.jpg", False, dict(eye=(W / 2 - 48, YC - 92, 78), target=c, up=(0, 0, 1), light=(-0.35, -0.55, 1.0))),
        ("console-s3-3q-bottom.jpg", True, dict(eye=(W / 2 + 48, YC - 92, -80), target=(W / 2, YC, -T), up=(0, 0, -1), light=(0.35, -0.55, -1.0))),
        ("console-s3-top.jpg", True, dict(eye=(W / 2, YC, 260), target=c, up=(0, 1, 0), light=(-0.3, 0.4, 1.0), fov=17.5)),
    ]
    for name, panel, view in views:
        sc = Scene()
        add_board(sc)
        add_parts(sc, panel=panel)
        render(sc, **view).save(os.path.join(OUT, name), quality=90, optimize=True)
        print(f"wrote {os.path.relpath(os.path.join(OUT, name), REPO)}: {len(sc.tris)} triangles")


if __name__ == "__main__":
    main()
