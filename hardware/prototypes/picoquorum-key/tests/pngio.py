"""Read and write PNG with the standard library only (zlib), for test_visual.

Handles what kicad-cli and this suite write: 8-bit RGB or RGBA, not interlaced, filters 0-4.
An Image is (width, height, channels, rows), rows a list of bytearrays of width * channels.
"""
import struct
import zlib


class Image:
    def __init__(self, width, height, channels, rows):
        self.width, self.height, self.channels, self.rows = width, height, channels, rows

    def rgb(self, x, y):
        r = self.rows[y]
        i = x * self.channels
        return r[i], r[i + 1], r[i + 2]


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def read(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: " + path)
    pos, idat, ihdr = 8, [], None
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
        pos += 12 + n
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or ctype not in (2, 6) or interlace:
        raise ValueError("unsupported PNG (depth %d, colour type %d, interlace %d): %s" % (depth, ctype, interlace, path))
    ch = 3 if ctype == 2 else 4
    raw = zlib.decompress(b"".join(idat))
    stride = w * ch
    rows, prev = [], bytearray(stride)
    for y in range(h):
        ft = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                up_left = prev[i - ch] if i >= ch else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 255
        rows.append(line)
        prev = line
    return Image(w, h, ch, rows)


def write(path, img):
    """RGB or RGBA, filter 0 for every row (small enough for the suite's images)."""
    ctype = 2 if img.channels == 3 else 6
    raw = b"".join(b"\x00" + bytes(r) for r in img.rows)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", img.width, img.height, 8, ctype, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))


def blank(width, height, rgb=(255, 255, 255)):
    return Image(width, height, 3, [bytearray(bytes(rgb) * width) for _ in range(height)])
