# Render the console's fonts into firmware/qf_*.bin: anti-aliased glyph bitmaps the Pico draws
# with framebuf.blit and a 16-colour palette (firmware/fonts.py). MicroPython's framebuf only has
# an 8x8 font; scaling it up is what made the old screens blocky.
#
#   uv run --with pillow python tools/fonts/gen.py
#   uv run --with pillow python tools/fonts/gen.py --try [set ...]
#
# --try renders candidate font sets (SETS below) for comparing on the screen: the same seven names
# and sizes, into emu/sketches/qf_SET_NAME.bin, where the emulator finds them and fonts.use(SET)
# swaps them in (emu/sketches/fontspec.py, tools/quorum shots --fonts). They never go to the
# board. GF_DIR=/path/to/a/google/fonts/checkout copies the typefaces from there instead of
# downloading them; either way they're checked against the pinned sha256.
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
    "next": ("atkinsonhyperlegiblenext/AtkinsonHyperlegibleNext[wght].ttf",
             "5a455d1cfa099b601ab70751bb9673e8fe1854dc4500c80e1a220d0d75e31745"),
    "mono": ("atkinsonhyperlegiblemono/AtkinsonHyperlegibleMono[wght].ttf",
             "5ce8b1698d1ded7dff2178c1a3ad159470085a58ea239e8b2cb88f4fb4a6f646"),
    # candidates (--try), all SIL OFL 1.1 from Google Fonts
    "inter": ("inter/Inter[opsz,wght].ttf",
              "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"),
    "grotesk": ("spacegrotesk/SpaceGrotesk[wght].ttf",
                "acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72"),
    "jetbrains": ("jetbrainsmono/JetBrainsMono[wght].ttf",
                  "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda"),
    "plex": ("ibmplexsans/IBMPlexSans[wdth,wght].ttf",
             "3b031aa4216174205bd8471f88a49b91f093169e9e87bd5262242bc5967fe2e3"),
    "plexmono500": ("ibmplexmono/IBMPlexMono-Medium.ttf",
                    "a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755"),
    "plexmono700": ("ibmplexmono/IBMPlexMono-Bold.ttf",
                    "ac27abd6450a64dd94467580a02fe6235156d5b92f2926ebbc8e7489df64e0be"),
    "manrope": ("manrope/Manrope[wght].ttf",
                "3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6"),
}
ASCII = "".join(chr(c) for c in range(32, 127))
EXTRA = "\u2026\u00b7\u2014"                # … · —, stored after "~" in this order (fonts.EXTRA)
TEXT = ASCII + EXTRA
HEX = " .:0123456789abcdefx"

# name: (typeface, weight, pixel size, characters). firmware/fonts.py lists the same names.
# weight None: a static file (its weight is in the file).
FONTS = {
    "sans12": ("next", 400, 12, TEXT),      # captions
    "sans14": ("next", 400, 14, TEXT),      # body text
    "bold14": ("next", 700, 14, TEXT),      # labels, emphasis
    "bold18": ("next", 700, 18, TEXT),      # titles
    "bold26": ("next", 700, 26, TEXT),      # headlines: amounts, what a transaction does
    "mono13": ("mono", 500, 13, TEXT),      # addresses and hashes
    "monob28": ("mono", 700, 28, HEX),      # the verify code
}


def candidate(sans, sans_w, bold_w, mono, mono_w, monob_w, features=None):
    """A font set with FONTS' names and sizes: a sans at two weights and a mono at two.
    features: OpenType features for the sans (e.g. Inter's ss02, which tells I from l)."""
    f = lambda face, w: (face + str(w), None) if face == "plexmono" else (face, w)
    return {
        "sans12": f(sans, sans_w) + (12, TEXT, features), "sans14": f(sans, sans_w) + (14, TEXT, features),
        "bold14": f(sans, bold_w) + (14, TEXT, features), "bold18": f(sans, bold_w) + (18, TEXT, features),
        "bold26": f(sans, bold_w) + (26, TEXT, features),
        "mono13": f(mono, mono_w) + (13, TEXT), "monob28": f(mono, monob_w) + (28, HEX),
    }


# The candidates for v2 (docs/quorum-ui/v2/FONTS.md). Today's fonts are FONTS, in firmware/.
SETS = {
    "inter": candidate("inter", 400, 700, "mono", 500, 700),
    "interd": candidate("inter", 400, 700, "mono", 500, 700, ["ss02"]),     # Inter, disambiguated
    "grotesk": candidate("grotesk", 400, 700, "jetbrains", 500, 700),
    "plex": candidate("plex", 400, 700, "plexmono", 500, 700),
    "manrope": candidate("manrope", 500, 750, "mono", 500, 700),
}


def ttf(key):
    rel, sha = TTF[key]
    path = os.path.join(SRC, key + ".ttf")
    if not os.path.exists(path):
        os.makedirs(SRC, exist_ok=True)
        if os.environ.get("GF_DIR"):
            print("copying", rel)
            with open(os.path.join(os.environ["GF_DIR"], "ofl", rel), "rb") as src, open(path, "wb") as dst:
                dst.write(src.read())
        else:
            url = GF + rel.replace("[", "%5B").replace("]", "%5D").replace(",", "%2C")
            print("downloading", url)
            urllib.request.urlretrieve(url, path)
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if got != sha:
        sys.exit("%s: sha256 %s, expected %s" % (path, got, sha))
    return path


def render(name, face, weight, size, chars, features=None, dest=None):
    f = ImageFont.truetype(ttf(face), size)
    if weight is not None:
        # by axis name: weight as given, optical size (Inter's) to match the pixel size, width normal
        want = {b"Weight": weight, b"Optical size": size, b"Width": 100}
        f.set_variation_by_axes([max(a["minimum"], min(a["maximum"], want.get(a["name"], a["default"])))
                                 for a in f.get_variation_axes()])
    ascent, descent = f.getmetrics()
    height = ascent + descent
    first, last = 32, 126 + len(EXTRA)
    table, data = [], bytearray()
    for code in range(first, last + 1):
        ch = chr(code) if code < 127 else EXTRA[code - 127]
        if ch not in chars:
            table.append((0, 0, 0, 0, 0, 0))
            continue
        adv = round(f.getlength(ch, features=features))
        pad = size
        img = Image.new("L", (adv + 2 * pad, height + 2 * pad), 0)
        ImageDraw.Draw(img).text((pad, pad + ascent), ch, font=f, fill=255, anchor="ls", features=features)
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
    path = dest or os.path.join(OUT, "qf_%s.bin" % name)
    with open(path, "wb") as fh:
        fh.write(out)
    print("%-8s %2d px  line %2d  %5d bytes  %s" % (name, size, height, len(out), os.path.relpath(path)))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--try"]:
        sketches = os.path.join(HERE, "..", "..", "emu", "sketches")
        for s in sys.argv[2:] or list(SETS):
            for name, spec in SETS[s].items():
                render(name, *spec, dest=os.path.join(sketches, "qf_%s_%s.bin" % (s, name)))
    else:
        for name, spec in FONTS.items():
            render(name, *spec)
