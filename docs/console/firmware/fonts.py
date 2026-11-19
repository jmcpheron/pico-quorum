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
import lcd as L

# Named literally, so tools/emu ship copies them to the board with any module that imports this.
FILES = {"sans12": "qf_sans12.bin", "sans14": "qf_sans14.bin", "bold14": "qf_bold14.bin",
         "bold18": "qf_bold18.bin", "bold26": "qf_bold26.bin", "mono13": "qf_mono13.bin",
         "monob28": "qf_monob28.bin"}

EXTRA = {"\u2026": 127, "\u00b7": 128, "\u2014": 129}   # … · —, after "~" (tools/fonts/gen.py)

_fonts = {}
_set = None                 # a candidate font set from tools/fonts/gen.py --try, or None


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

    def at(self, c):
        """Where character c's metrics are in buf: 8 bytes, "<HBBbbB" (bitmap offset, width,
        height, x and y offsets, advance). Read there each time, nothing kept: a FrameBuffer, a
        view and a tuple a glyph, built as each was first drawn, were 172 small objects spread
        through the heap by the end of a review (board #2, 2026-11-10)."""
        i = EXTRA.get(c, ord(c)) - self.first
        if not 0 <= i < self.count:
            i = ord("?") - self.first
        return 8 + 8 * i


def get(name):
    f = _fonts.get(name)
    if f is None:
        f = _fonts[name] = Font(FILES[name] if _set is None else "qf_%s_%s.bin" % (_set, name))
    return f


def use(fontset=None):
    """Draw every size in a candidate set (qf_SET_NAME.bin, emulator only); None: our own."""
    global _set
    _set = fontset
    _fonts.clear()
    for i in range(_WN):
        _wk[i] = None


PALS = 32
_pals = [framebuf.FrameBuffer(bytearray(32), 16, 1, framebuf.RGB565) for _ in range(PALS)]
_pkey = [None] * PALS
_pal = {}                   # (fg, bg) -> its index in _pals
_pnext = 0


def palette(fg, bg):
    """16 colours from bg (coverage 0) to fg (15), as the panel wants them. PALS of them, made
    together at import and reused oldest first: made as they were first wanted, 48 were spread
    through the heap by the end of a review, and all made again when the 49th came."""
    global _pnext
    k = (fg, bg)
    i = _pal.get(k)
    if i is None:
        i = _pnext
        _pnext = (i + 1) % PALS
        if _pkey[i] is not None:
            del _pal[_pkey[i]]
        _pkey[i], _pal[k] = k, i
        p = _pals[i]
        for j in range(16):
            p.pixel(j, 0, L.color(bg[0] + (fg[0] - bg[0]) * j // 15, bg[1] + (fg[1] - bg[1]) * j // 15,
                                  bg[2] + (fg[2] - bg[2]) * j // 15))
    return _pals[i]


def text(d, s, x, y, font, fg, bg):
    """Draw s with the top of its line box at y. fg and bg are (r, g, b). Returns x after it."""
    f = get(font)
    if L.BANDS > 1 and (y + f.height + 4 <= d.y0 or y - 4 >= d.y0 + d.band_h):
        return x + width(s, font)       # not in the band being drawn (lcd.LCD.frames)
    p = palette(fg, bg)
    key = L.color(*bg)      # coverage 0 is the background itself: leave those pixels alone
    b, data, src = f.buf, f.data, _src
    for c in s:
        o = f.at(c)
        w, h = b[o + 2], b[o + 3]
        if w:
            off, xo, yo = b[o] | b[o + 1] << 8, b[o + 4], b[o + 5]
            src[0], src[1], src[2] = data[off:off + h * ((w + 1) // 2)], w, h
            d.blit(src, x + xo - (256 if xo > 127 else 0), y + yo - (256 if yo > 127 else 0), key, p)
        x += b[o + 6]
    return x


_src = [None, 0, 0, framebuf.GS4_HMSB]     # blit's source as (buffer, w, h, format), one list for every glyph


_WN = 128
_wk, _wf, _wv = [None] * _WN, [None] * _WN, [0] * _WN    # the widths remembered: string, font, width


def width(s, font):
    """Remembered: a banded screen (lcd.py) measures every string once per band, and fit() and the
    right-aligned text measure the same ones over and over (~0.5 s a frame on Build 1, uncached).
    In a fixed table, one slot per string's hash, set aside at import: a dict here grew to a
    1336-byte table, emptied and grew again every 160 strings, and a heap in pieces had no such
    block for a screen, nor for the Sending screen after a signature (board #2, 2026-11-11)."""
    i = hash(s) % _WN
    if _wk[i] == s and _wf[i] == font:
        return _wv[i]
    f = get(font)
    b, n = f.buf, 0
    for c in s:
        n += b[f.at(c) + 6]
    _wk[i], _wf[i], _wv[i] = s, font, n
    return n


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
