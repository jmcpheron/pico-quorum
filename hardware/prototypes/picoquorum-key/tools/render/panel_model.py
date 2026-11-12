"""A 3D model of the EastRising ER-TFT1.14-2 panel with a mock console screen, for renders only.

  uv run --no-project --with pillow==12.3.0 python3 tools/render/panel_model.py <out_dir>

Writes <out_dir>/screen.png (the 240 x 135 mock UI, pixel for pixel) and <out_dir>/panel.wrl
(VRML in KiCad's 0.1-inch units). The model's origin is the glass centre, its z = 0 the panel's
back face; tools/render/render_with_panel.sh lifts it by the foam tape's thickness.

Dimensions from the ER-TFT1.14-2 datasheet (rev 1.0, p. 5-6): outline 31.0 x 17.6 x 1.6, LCD glass
30.11 x 17.26, polariser 27.10 x 16.80, active area 24.91 x 14.86 starting 1.60 from the edge away
from the ribbon. The ribbon fold at the right edge is drawn as a strip of polyimide.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "hardware/out/scratch/render"
os.makedirs(OUT, exist_ok=True)

W, H = 240, 135
AA_W, AA_H = 24.91, 14.86
AA_X0, AA_Y0 = -15.5 + 1.60, -AA_H / 2           # panel-relative mm, y down
PW, PH = AA_W / W, AA_H / H
RAIL = (7, 67, 127)

# ---- the mock screen --------------------------------------------------------------------------
MENLO = "/System/Library/Fonts/Menlo.ttc"
f10 = ImageFont.truetype(MENLO, 10, index=0)
f10b = ImageFont.truetype(MENLO, 10, index=1)
f18b = ImageFont.truetype(MENLO, 18, index=1)

RED, GREEN, WHITE, GREY, DIM = (255, 72, 72), (64, 220, 120), (235, 235, 235), (140, 140, 150), (85, 85, 95)
CYAN, AMBER = (70, 200, 255), (255, 180, 40)

img = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(img)
d.fontmode = "1"                                  # no anti-aliasing: exact colours, like a bitmap font


def text_mid(x, row, s, font, fill):
    top, bottom = d.textbbox((0, 0), s, font=font)[1::2]
    d.text((x, row - (top + bottom) // 2), s, font=font, fill=fill)


for row, label, col in zip(RAIL, ("REJECT", "NEXT", "SIGN"), (RED, WHITE, GREEN)):
    d.polygon([(1, row), (5, row - 4), (5, row + 4)], fill=col)          # points at the button
    text_mid(8, row, label, f10b, col)
d.line([(50, 0), (50, H - 1)], fill=DIM)

x = 56
d.text((x, 2), "SAFE TX", font=f10b, fill=CYAN)
d.text((W - 2 - d.textlength("1/3", font=f10), 2), "1/3", font=f10, fill=GREY)
d.line([(x, 16), (W - 3, 16)], fill=DIM)
d.text((x, 20), "Transfer", font=f10, fill=GREY)
d.text((x, 32), "1.50 ETH", font=f18b, fill=WHITE)
d.text((x, 56), "to   0x7a25…c3F1", font=f10, fill=WHITE)
d.text((x, 70), "from 0x9fC2…41aB", font=f10, fill=GREY)
d.text((x, 84), "nonce 42  chain 1", font=f10, fill=GREY)
d.line([(x, 100), (W - 3, 100)], fill=DIM)
d.text((x, 104), "hash 5e1d…a07c", font=f10, fill=DIM)
d.text((x, 119), "hold SIGN 2 s", font=f10, fill=AMBER)
img.save(os.path.join(OUT, "screen.png"))

# ---- VRML -------------------------------------------------------------------------------------
U = 1 / 2.54                                      # KiCad VRML unit is 0.1 inch


def v(x, y, z):
    return f"{x * U:.4f} {-y * U:.4f} {z * U:.4f}"


def material(rgb, shine=0.2, emissive=0.0):
    r, g, b = rgb
    e = f"{r * emissive:.3f} {g * emissive:.3f} {b * emissive:.3f}"
    return (f"appearance Appearance {{ material Material {{ diffuseColor {r:.3f} {g:.3f} {b:.3f} "
            f"emissiveColor {e} specularColor 0.3 0.3 0.3 shininess {shine} }} }}")


def shape(points, faces, mat):
    pts = ", ".join(points)
    idx = ", ".join(" ".join(str(i) for i in f) + " -1" for f in faces)
    return (f"Shape {{ {mat}\n geometry IndexedFaceSet {{ solid FALSE coord Coordinate {{ point [ {pts} ] }}"
            f" coordIndex [ {idx} ] }} }}\n")


def box(x0, y0, z0, x1, y1, z1, rgb, shine=0.2):
    p = [v(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    faces = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
    faces += [tuple(reversed(f)) for f in faces]    # both windings: KiCad culls back faces
    return shape(p, faces, material(rgb, shine))


parts = [
    box(-15.5, -8.8, 0.0, 15.5, 8.8, 1.15, (0.86, 0.86, 0.84)),                 # backlight frame
    box(-15.3, -8.63, 1.15, 14.81, 8.63, 1.45, (0.10, 0.11, 0.12), 0.8),       # LCD glass
    box(-15.1, -8.40, 1.45, 12.0, 8.40, 1.60, (0.015, 0.015, 0.02), 0.9),      # polariser
    box(12.7, -5.5, 1.45, 13.4, 5.5, 1.70, (0.30, 0.30, 0.33), 0.5),           # driver IC on the ledge
    box(15.5, -3.4, -1.2, 16.0, 5.7, 1.30, (0.80, 0.50, 0.12), 0.4),           # ribbon fold
    box(-15.3, -8.5, -1.5, -12.8, 8.5, 0.0, (0.06, 0.06, 0.06)),               # foam tape, left end
    box(12.0, -8.5, -1.5, 15.2, -3.8, 0.0, (0.06, 0.06, 0.06)),                # foam, right corners
    box(12.0, 6.1, -1.5, 15.2, 8.5, 0.0, (0.06, 0.06, 0.06)),
]

# pixels: one IndexedFaceSet per colour, horizontal runs merged into single quads
Z = 1.603
runs = {}
px = img.load()
for y in range(H):
    xx = 0
    while xx < W:
        c = px[xx, y]
        x0 = xx
        while xx < W and px[xx, y] == c:
            xx += 1
        if c != (0, 0, 0):
            runs.setdefault(c, []).append((x0, xx, y))
for c, rr in runs.items():
    pts, faces = [], []
    for x0, x1, y in rr:
        a, b = AA_X0 + x0 * PW, AA_X0 + x1 * PW
        t, u = AA_Y0 + y * PH, AA_Y0 + (y + 1) * PH
        n = len(pts)
        pts += [v(a, u, Z), v(b, u, Z), v(b, t, Z), v(a, t, Z)]      # counter-clockwise from above
        faces.append((n, n + 1, n + 2, n + 3))
    rgb = tuple(ch / 255 for ch in c)
    parts.append(shape(pts, faces, material(rgb, 0.1, emissive=0.9)))

with open(os.path.join(OUT, "panel.wrl"), "w") as fh:
    fh.write("#VRML V2.0 utf8\n# ER-TFT1.14-2 panel with a mock picoquorum-key screen (render only)\n")
    fh.writelines(parts)
print(f"panel_model: {sum(len(r) for r in runs.values())} pixel runs in {len(runs)} colours; "
      f"wrote {OUT}/panel.wrl and {OUT}/screen.png")
