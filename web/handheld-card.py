# The handheld page's share card (web/src/handheld-card.png, 1200 x 630, the size X and others show
# for a large link preview): the four-colour plate, and the cartridge going into the bay in the back, both
# from the case's own pictures (assembly.py draws card-key-in.png for this). build.mjs copies it to
# docs/handheld/card.png. Run it again when those pictures change, and commit the card:
#   uv run --no-project --with pillow==12.3.0 python3 web/handheld-card.py
from pathlib import Path
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
PICS = ROOT / "hardware/builds/pico-sign-handheld/case/out/assembly"
W, H, PAD = 1200, 630, 40
WHITE = (255, 255, 255)


def trim(im):
    """Crop to what's drawn: everything not white, and a few pixels round it."""
    box = ImageChops.difference(im, Image.new("RGB", im.size, WHITE)).getbbox()
    return im.crop((max(box[0] - 4, 0), max(box[1] - 4, 0), min(box[2] + 4, im.width), min(box[3] + 4, im.height)))


def fit(im, h):
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


plate = trim(Image.open(PICS / "00-colours.png").convert("RGB").crop((20, 170, 690, 1080)))  # the plate, face on
key_in = trim(Image.open(PICS / "card-key-in.png").convert("RGB"))                            # from the back
plate, key_in = fit(plate, H - 2 * PAD), fit(key_in, H - 2 * PAD)
if plate.width + key_in.width > W - 3 * PAD:                   # too wide: shrink the back view to fit
    key_in = key_in.resize((W - 3 * PAD - plate.width, round(key_in.height * (W - 3 * PAD - plate.width) / key_in.width)), Image.LANCZOS)
card = Image.new("RGB", (W, H), WHITE)
gap = (W - plate.width - key_in.width) // 3
card.paste(plate, (gap, (H - plate.height) // 2))
card.paste(key_in, (2 * gap + plate.width, (H - key_in.height) // 2))
card.save(ROOT / "web/src/handheld-card.png", optimize=True)
print(f"web/src/handheld-card.png: {W} x {H}")
