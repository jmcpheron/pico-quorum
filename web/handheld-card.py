# The handheld page's share card (web/src/handheld-card.png, 1200 x 630, the size X and others show
# for a large link preview): the four-colour plate and the finished handheld, cropped from the case's
# own assembly pictures. build.mjs copies it to docs/handheld/card.png. Run it again when those
# pictures change, and commit the card:
#   uv run --no-project --with pillow==12.3.0 python3 web/handheld-card.py
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PICS = ROOT / "hardware/builds/pico-sign-handheld/case/out/assembly"
W, H, PAD = 1200, 630, 40

plate = Image.open(PICS / "00-colours.png").convert("RGB").crop((30, 180, 672, 1060))  # the plate, face on
done = Image.open(PICS / "16-done.png").convert("RGB").crop((930, 370, 1620, 870))     # step 16's right panel

def fit(im, h):
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)

plate, done = fit(plate, H - 2 * PAD), fit(done, 470)
card = Image.new("RGB", (W, H), (255, 255, 255))
gap = (W - plate.width - done.width) // 3
card.paste(plate, (gap, PAD))
card.paste(done, (2 * gap + plate.width, (H - done.height) // 2))
card.save(ROOT / "web/src/handheld-card.png", optimize=True)
print(f"web/src/handheld-card.png: {W} x {H}")
