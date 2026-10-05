# The PicoQuorum lockup (the mark left of the name) as SVG, for the README and anywhere else that
# shows an <img>: docs/brand/lockup-dark.svg and lockup-light.svg. The name is outlined from
# Atkinson Hyperlegible Next Bold (the app's own copy, docs/app/fonts/next-700.woff2), so it looks
# the same without the font installed. Proportions are docs/BRAND.md's: name 26 px, ring radius
# 12 px, the mark's centre 13 px in, the word at 34 px.
#
#   uv run --with fonttools --with brotli python tools/brand/lockup.py
import math
import os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
FONT = os.path.join(ROOT, "docs", "app", "fonts", "next-700.woff2")
OUT = os.path.join(ROOT, "docs", "brand")

NAME, SIZE, R, CX, X0, PAD = "PicoQuorum", 26, 12, 13, 34, 2

# docs/BRAND.md: text, signed green, waiting amber, and the triangle as face green mixed 55% into
# the ground. The mark's own files (mark-dark.svg, mark-light.svg) use the same values.
THEMES = {
    "dark": {"text": "#F2F4F7", "ok": "#34C759", "warn": "#CE9529", "tri": "#397F4C"},
    "light": {"text": "#101318", "ok": "#16963E", "warn": "#B78231", "tri": "#7AC191"},
}


def word():
    """The name as one path at SIZE px, baseline at y=0, and its advance width."""
    font = TTFont(FONT)
    gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    s = SIZE / font["head"].unitsPerEm
    pen, x = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip(".")), 0
    for ch in NAME:
        g = cmap[ord(ch)]
        gs[g].draw(TransformPen(pen, (s, 0, 0, -s, x, 0)))
        x += hmtx[g][0] * s
    cap = font["OS/2"].sCapHeight * s
    return pen.getCommands(), x, cap


def svg(theme, d, adv, cap):
    c = THEMES[theme]
    # the word sits on a baseline; the mark is centred on the capitals
    h = 2 * R + 2 * (R / 4) + 2 * PAD
    cy = h / 2
    base = cy + cap / 2
    pts = [(PAD + CX + R * math.cos(math.radians(-90 + 72 * k)), cy + R * math.sin(math.radians(-90 + 72 * k))) for k in range(5)]
    signed = (0, 2, 3)
    tri = " ".join(f"{pts[k][0]:.2f},{pts[k][1]:.2f}" for k in signed)
    dots = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{R / 4 if k in signed else R / 6:.2f}" fill="{c["ok"] if k in signed else c["warn"]}"/>'
        for k, (x, y) in enumerate(pts))
    w = PAD + X0 + adv + PAD
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" width="{w * 4:.0f}" height="{h * 4:.0f}">\n'
            f'<title>PicoQuorum</title>\n'
            f'<polygon points="{tri}" fill="{c["tri"]}"/>\n{dots}\n'
            f'<path transform="translate({PAD + X0} {base:.2f})" fill="{c["text"]}" d="{d}"/>\n</svg>\n')


if __name__ == "__main__":
    d, adv, cap = word()
    for theme in THEMES:
        p = os.path.join(OUT, f"lockup-{theme}.svg")
        with open(p, "w") as f:
            f.write(svg(theme, d, adv, cap))
        print(os.path.relpath(p, ROOT))
