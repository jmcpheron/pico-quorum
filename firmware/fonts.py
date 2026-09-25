# Anti-aliased text for the 240x240 panel. The glyphs are Atkinson Hyperlegible Next and Mono,
# rendered on the laptop by tools/fonts/gen.py into qf_*.bin (SIL OFL 1.1, tools/fonts/OFL.txt).
# Each glyph is a 4-bit coverage bitmap; framebuf.blit draws it in C through a 16-colour palette
# that runs from the background to the ink, so edges are smooth and nothing is drawn per pixel
# in Python. The one rule: say what the text sits on (bg), because the edges are mixed with it.
#
#   fonts.text(d, "Send 0.05 ETH", x, y, "bold26", (255, 255, 255), (11, 13, 17)) -> x after it
#   fonts.width("0.05 ETH", "bold26"); fonts.wrap(s, 220, "sans14"); fonts.height("sans14")
import framebuf
import os
import struct
import lcd as L

# Named literally, so tools/emu ship copies them to the board with any module that imports this.
FILES = {"sans12": "qf_sans12.bin", "sans14": "qf_sans14.bin", "bold14": "qf_bold14.bin",
         "bold18": "qf_bold18.bin", "bold26": "qf_bold26.bin", "mono13": "qf_mono13.bin",
         "monob28": "qf_monob28.bin"}

EXTRA = {"\u2026": 127, "\u00b7": 128, "\u2014": 129}   # … · —, after "~" (tools/fonts/gen.py)

_fonts = {}
_pal = {}


class Font:
    def __init__(self, path):
        b = bytearray(os.stat(path)[6])         # framebuf wants a writable buffer
        with open(path, "rb") as f:
            f.readinto(b)
        if b[:3] != b"QF\x01":
            raise ValueError(path + " is not a font")
        self.height, self.ascent, self.first, self.count = b[3], b[4], b[5], b[6]
        self.buf = b
        self.data = memoryview(b)[8 + 8 * self.count:]
        self.glyphs = {}

    def glyph(self, c):
        """(framebuffer or None, xoff, yoff, advance) for one character, built once."""
        g = self.glyphs.get(c)
        if g is None:
            i = EXTRA.get(c, ord(c)) - self.first
            if not 0 <= i < self.count:
                i = ord("?") - self.first
            off, w, h, xo, yo, adv = struct.unpack_from("<HBBbbB", self.buf, 8 + 8 * i)
            fb = framebuf.FrameBuffer(self.data[off:off + h * ((w + 1) // 2)], w, h, framebuf.GS4_HMSB) if w else None
            g = self.glyphs[c] = (fb, xo, yo, adv)
        return g


def get(name):
    f = _fonts.get(name)
    if f is None:
        f = _fonts[name] = Font(FILES[name])
    return f


def palette(fg, bg):
    """16 colours from bg (coverage 0) to fg (15), as the panel wants them."""
    k = (fg, bg)
    p = _pal.get(k)
    if p is None:
        if len(_pal) > 48:
            _pal.clear()
        p = framebuf.FrameBuffer(bytearray(32), 16, 1, framebuf.RGB565)
        for i in range(16):
            p.pixel(i, 0, L.color(bg[0] + (fg[0] - bg[0]) * i // 15, bg[1] + (fg[1] - bg[1]) * i // 15,
                                  bg[2] + (fg[2] - bg[2]) * i // 15))
        _pal[k] = p
    return p


def text(d, s, x, y, font, fg, bg):
    """Draw s with the top of its line box at y. fg and bg are (r, g, b). Returns x after it."""
    f = get(font)
    p = palette(fg, bg)
    key = L.color(*bg)      # coverage 0 is the background itself: leave those pixels alone
    for c in s:
        fb, xo, yo, adv = f.glyph(c)
        if fb:
            d.blit(fb, x + xo, y + yo, key, p)
        x += adv
    return x


def width(s, font):
    f = get(font)
    return sum(f.glyph(c)[3] for c in s)


def height(font):
    return get(font).height


def wrap(s, w, font):
    """Words into lines no wider than w pixels. A word wider than a line is cut."""
    out, line = [], ""
    for word in s.split(" "):
        while width(word, font) > w:
            if line:
                out.append(line)
                line = ""
            n = len(word)
            while n > 1 and width(word[:n], font) > w:
                n -= 1
            out.append(word[:n])
            word = word[n:]
        cand = line + " " + word if line else word
        if width(cand, font) > w and line:
            out.append(line)
            line = word
        else:
            line = cand
    if line:
        out.append(line)
    return out
