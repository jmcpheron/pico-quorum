# Render the console's fonts into firmware/qf_*.bin: anti-aliased glyph bitmaps the Pico draws
# with framebuf.blit and a 16-colour palette (firmware/fonts.py). MicroPython's framebuf only has
# an 8x8 font; scaling it up is what made the old screens blocky.
#
#   uv run --with pillow python tools/fonts/gen.py
#
# The typefaces are Atkinson Hyperlegible Next and Mono (Braille Institute; SIL OFL 1.1, see
# OFL.txt here): made to keep 0/O, 1/l/I and similar pairs apart, which matters on a device
# whose job is to make people compare addresses. They are downloaded (pinned by sha256) into
# tools/fonts/src/, which git ignores; the .bin files are committed.
#
# .bin layout (little-endian):
#   header  "QF" version(1) height ascent first count 0      8 bytes
#   table   count x (offset:u16 w:u8 h:u8 xoff:i8 yoff:i8 advance:u8 0)
#   data    per glyph h rows of ceil(w/2) bytes, 4 bits a pixel, left pixel in the high nibble
#           (framebuf.GS4_HMSB); 0 = background, 15 = ink
import hashlib
import os
import struct
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(HERE, "..", "..", "firmware")
GF = "https://github.com/google/fonts/raw/main/ofl/"
TTF = {
    "next": (GF + "atkinsonhyperlegiblenext/AtkinsonHyperlegibleNext%5Bwght%5D.ttf",
             "5a455d1cfa099b601ab70751bb9673e8fe1854dc4500c80e1a220d0d75e31745"),
    "mono": (GF + "atkinsonhyperlegiblemono/AtkinsonHyperlegibleMono%5Bwght%5D.ttf",
             "5ce8b1698d1ded7dff2178c1a3ad159470085a58ea239e8b2cb88f4fb4a6f646"),
}
ASCII = "".join(chr(c) for c in range(32, 127))
EXTRA = "\u2026\u00b7\u2014"                # … · —, stored after "~" in this order (fonts.EXTRA)
TEXT = ASCII + EXTRA
HEX = " .:0123456789abcdefx"

# name: (typeface, weight, pixel size, characters). firmware/fonts.py lists the same names.
FONTS = {
    "sans12": ("next", 400, 12, TEXT),      # captions
    "sans14": ("next", 400, 14, TEXT),      # body text
    "bold14": ("next", 700, 14, TEXT),      # labels, emphasis
    "bold18": ("next", 700, 18, TEXT),      # titles
    "bold26": ("next", 700, 26, TEXT),      # headlines: amounts, what a transaction does
    "mono13": ("mono", 500, 13, TEXT),      # addresses and hashes
    "monob28": ("mono", 700, 28, HEX),      # the verify code
}


def ttf(key):
    url, sha = TTF[key]
    path = os.path.join(SRC, key + ".ttf")
    if not os.path.exists(path):
        os.makedirs(SRC, exist_ok=True)
        print("downloading", url)
        urllib.request.urlretrieve(url, path)
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if got != sha:
        sys.exit("%s: sha256 %s, expected %s" % (path, got, sha))
    return path


def render(name, face, weight, size, chars):
    f = ImageFont.truetype(ttf(face), size)
    f.set_variation_by_axes([weight])
    ascent, descent = f.getmetrics()
    height = ascent + descent
    first, last = 32, 126 + len(EXTRA)
    table, data = [], bytearray()
    for code in range(first, last + 1):
        ch = chr(code) if code < 127 else EXTRA[code - 127]
        if ch not in chars:
            table.append((0, 0, 0, 0, 0, 0))
            continue
        adv = round(f.getlength(ch))
        pad = size
        img = Image.new("L", (adv + 2 * pad, height + 2 * pad), 0)
        ImageDraw.Draw(img).text((pad, pad + ascent), ch, font=f, fill=255, anchor="ls")
        box = img.getbbox()
        if box is None:                     # space
            table.append((len(data), 0, 0, 0, 0, adv))
            continue
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        px = img.crop(box).load()
        off = len(data)
        for y in range(h):
            row = [(px[x, y] * 15 + 127) // 255 for x in range(w)] + [0]
            for x in range(0, w, 2):
                data.append(row[x] << 4 | row[x + 1])
        table.append((off, w, h, x0 - pad, y0 - pad, adv))
    if len(data) > 0xFFFF:
        sys.exit("%s: %d bytes of glyphs, more than a u16 offset reaches" % (name, len(data)))
    out = bytearray(b"QF" + bytes([1, height, ascent, first, last - first + 1, 0]))
    for off, w, h, xo, yo, adv in table:
        out += struct.pack("<HBBbbBx", off, w, h, xo, yo, adv)
    out += data
    path = os.path.join(OUT, "qf_%s.bin" % name)
    with open(path, "wb") as fh:
        fh.write(out)
    print("%-8s %2d px  line %2d  %5d bytes  %s" % (name, size, height, len(out), os.path.relpath(path)))


if __name__ == "__main__":
    for name, spec in FONTS.items():
        render(name, *spec)
