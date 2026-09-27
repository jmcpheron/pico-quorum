# The pictures in docs/quorum-ui/v2/FONTS.md: each candidate font set next to today's fonts.
#
#   GF_DIR=... uv run --with pillow python tools/fonts/gen.py --try     the candidates' glyphs
#   tools/quorum shots --fonts inter,interd,grotesk,plex,manrope        the real screens in each
#   uv run --with pillow python tools/fonts/compare.py                  specimens, then the grids
#
# Specimens: emu/sketches/fontspec.py's card in each set, from the emulator. Grids: one per
# screen, today's shot (docs/quorum-ui/shots/) and each set's, labelled, 3 across.
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DOCS = os.path.join(ROOT, "docs", "quorum-ui", "v2", "fonts")
SETS = [(None, "Today: Atkinson Hyperlegible"), ("inter", "Inter + Atkinson Mono"),
        ("interd", "Inter, disambiguated (ss02)"), ("grotesk", "Space Grotesk + JetBrains Mono"),
        ("plex", "IBM Plex Sans + Plex Mono"), ("manrope", "Manrope + Atkinson Mono")]
SCREENS = ["01-home", "02-approve-summary", "03-approve-send", "11-batch-verify", "13-owner-red-page",
           "16-lie-refused"]
CELL, LABEL, GAP = 360, 30, 12


def specimens():
    args = ["node", "headless.mjs", "fontspec", "--quiet", "--exec", "fontspec.stop()"]
    for key, _ in SETS:
        args += ["--exec", "fontspec.card(%r)" % key, "--shot", os.path.join(DOCS, "spec-%s.png" % (key or "atkinson"))]
    subprocess.run(args, cwd=os.path.join(ROOT, "emu"), check=True, stdout=subprocess.DEVNULL)


def grid(paths, dst):
    font = ImageFont.load_default(18)
    cols = 3
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * CELL + (cols - 1) * GAP, rows * (CELL + LABEL) + (rows - 1) * GAP), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for k, (path, label) in enumerate(paths):
        x, y = (k % cols) * (CELL + GAP), (k // cols) * (CELL + LABEL + GAP)
        draw.text((x + 2, y + 5), label, fill=(20, 20, 20), font=font)
        sheet.paste(Image.open(path).convert("RGB").resize((CELL, CELL), Image.LANCZOS), (x, y + LABEL))
    sheet.save(dst, optimize=True)
    print(os.path.relpath(dst, ROOT))


if __name__ == "__main__":
    specimens()
    grid([(os.path.join(DOCS, "spec-%s.png" % (k or "atkinson")), label) for k, label in SETS],
         os.path.join(DOCS, "compare-specimen.png"))
    for s in SCREENS:
        paths = [(os.path.join(ROOT, "docs", "quorum-ui", "shots", s + ".png") if k is None
                  else os.path.join(DOCS, k, s + ".png"), label) for k, label in SETS]
        missing = [p for p, _ in paths if not os.path.exists(p)]
        if missing:
            sys.exit("missing %s: run tools/quorum shots --fonts first" % missing[0])
        grid(paths, os.path.join(DOCS, "compare-%s.png" % s))
