# A small QR code encoder for the Pico: versions 1 to 6 (21 to 41 modules), error correction L or M,
# alphanumeric or byte mode, Reed-Solomon over GF(256), all eight masks scored as the spec asks.
# Pure Python so the same file runs on the laptop for tests. encode(text) returns (n, rows) in the
# form wallet.draw_qr and slots draw: n modules a side, rows[r] an int whose bit c is the dark module
# at column c. A 130-character uppercase hex key fits version 5 (37 modules) at level L.
ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
# per version: total codewords, then per level: (ec codewords per block, number of blocks)
TOTAL = (0, 26, 44, 70, 100, 134, 172)
BLOCKS = {"L": (None, (7, 1), (10, 1), (15, 1), (20, 1), (26, 1), (18, 2)),
          "M": (None, (10, 1), (16, 1), (26, 1), (18, 2), (24, 2), (16, 4))}
LEVEL_BITS = {"L": 1, "M": 0}

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs(data, nec):
    """Reed-Solomon error-correction codewords for one block."""
    gen = [1]                       # coefficients, highest degree first; times (x + a^i) each round
    for i in range(nec):
        gen = [g ^ (_mul(gen[j - 1], _EXP[i]) if j else 0) for j, g in enumerate(gen + [0])]
    rem = [0] * nec
    for d in data:
        f = d ^ rem[0]
        rem = rem[1:] + [0]
        if f:
            for j in range(nec):
                rem[j] ^= _mul(gen[j + 1], f)
    return rem


def _bits(text, version, level):
    """Mode, count, data, terminator, padding: the data codewords, or None if it does not fit."""
    nec, nb = BLOCKS[level][version]
    cap = TOTAL[version] - nec * nb
    out = []
    alnum = all(c in ALNUM for c in text)
    if alnum:
        out.append((2, 4)); out.append((len(text), 9))
        for i in range(0, len(text) - 1, 2):
            out.append((ALNUM.index(text[i]) * 45 + ALNUM.index(text[i + 1]), 11))
        if len(text) % 2:
            out.append((ALNUM.index(text[-1]), 6))
    else:
        b = text.encode()
        out.append((4, 4)); out.append((len(b), 8))
        for c in b:
            out.append((c, 8))
    n = sum(w for _, w in out)
    if n > cap * 8:
        return None
    out.append((0, min(4, cap * 8 - n)))
    acc, nacc, cw = 0, 0, []
    for v, w in out:
        acc = (acc << w) | v
        nacc += w
        while nacc >= 8:
            cw.append((acc >> (nacc - 8)) & 0xFF)
            nacc -= 8
    if nacc:
        cw.append((acc << (8 - nacc)) & 0xFF)
    pad = (0xEC, 0x11)
    while len(cw) < cap:
        cw.append(pad[len(cw) % 2])
    return cw


def _codewords(data, version, level):
    """Split into blocks, add EC, interleave."""
    nec, nb = BLOCKS[level][version]
    short = len(data) // nb
    blocks, k = [], 0
    for i in range(nb):
        size = short + (1 if i >= nb - len(data) % nb else 0) if len(data) % nb else short
        blocks.append(data[k:k + size]); k += size
    ecs = [_rs(b, nec) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(nec):
        for e in ecs:
            out.append(e[i])
    return out


def _matrix(version):
    """Function patterns and a mask of reserved modules, a byte per module row by row (module (row,
    col) at row * n + col). Returns (grid, reserved)."""
    n = 17 + 4 * version
    g = bytearray(n * n)
    r = bytearray(n * n)

    def finder(x, y):
        for i in range(-1, 8):
            for j in range(-1, 8):
                if 0 <= x + i < n and 0 <= y + j < n:
                    v = 1 if (0 <= i <= 6 and 0 <= j <= 6 and (i in (0, 6) or j in (0, 6) or (2 <= i <= 4 and 2 <= j <= 4))) else 0
                    g[(y + j) * n + x + i] = v
                    r[(y + j) * n + x + i] = 1
    finder(0, 0); finder(n - 7, 0); finder(0, n - 7)
    for i in range(8, n - 8):
        g[6 * n + i] = g[i * n + 6] = 1 - i % 2
        r[6 * n + i] = r[i * n + 6] = 1
    if version >= 2:
        c = 4 * version + 10
        for i in range(-2, 3):
            for j in range(-2, 3):
                g[(c + j) * n + c + i] = 1 if (abs(i) == 2 or abs(j) == 2 or (i == 0 and j == 0)) else 0
                r[(c + j) * n + c + i] = 1
    g[(4 * version + 9) * n + 8] = 1
    r[(4 * version + 9) * n + 8] = 1
    for i in range(9):          # format info around the top-left finder
        if i != 6:
            r[8 * n + i] = r[i * n + 8] = 1
    for i in range(8):          # its second copy: row 8 on the right, column 8 at the bottom
        r[8 * n + n - 1 - i] = 1
        r[(n - 1 - i) * n + 8] = 1
    return g, r


def _place(g, r, n, cw):
    """The codewords into the modules not reserved, most significant bit first. Each bit is read
    from cw where it goes: a list of the 1072 bits (version 5) grew to an 8 KB block, more than a
    console-rp's heap had in one piece after a while (board #2, 2026-11-07)."""
    nbits = 8 * len(cw)
    i, up, col = 0, True, n - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if up else range(n)
        for row in rows:
            for dx in (0, 1):
                x = col - dx
                if not r[row * n + x]:
                    g[row * n + x] = cw[i >> 3] >> (7 - (i & 7)) & 1 if i < nbits else 0
                    i += 1
        up = not up
        col -= 2


def _mask(out, g, r, n, m):
    """g with mask m over the modules not reserved, written into out: no grid is copied."""
    k = 0
    for i in range(n):
        for j in range(n):
            v = g[k]
            if not r[k]:
                if m == 0: f = (i + j) % 2 == 0
                elif m == 1: f = i % 2 == 0
                elif m == 2: f = j % 3 == 0
                elif m == 3: f = (i + j) % 3 == 0
                elif m == 4: f = (i // 2 + j // 3) % 2 == 0
                elif m == 5: f = (i * j) % 2 + (i * j) % 3 == 0
                elif m == 6: f = ((i * j) % 2 + (i * j) % 3) % 2 == 0
                else: f = ((i + j) % 2 + (i * j) % 3) % 2 == 0
                if f:
                    v ^= 1
            out[k] = v
            k += 1


def _format(g, n, level, m):
    v = (LEVEL_BITS[level] << 3) | m
    f = v << 10
    for i in range(14, 9, -1):
        if f >> i & 1:
            f ^= 0x537 << (i - 10)
    f = ((v << 10) | f) ^ 0x5412
    bits = [(f >> i) & 1 for i in range(14, -1, -1)]
    # around the top-left finder
    pos = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8), (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    for (row, col), b in zip(pos, bits):
        g[row * n + col] = b
    # split copy: bottom-left column 8 and top-right row 8
    for k in range(7):
        g[(n - 1 - k) * n + 8] = bits[k]
    for k in range(7, 15):
        g[8 * n + n - 15 + k] = bits[k]


_FINDER = (bytes((1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0)), bytes((0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1)))


def _penalty(g, n):
    """The four scores, read in place, one line of n bytes at a time. Lists of the grid's rows, the
    columns copied out too, ran a console-rp out of memory after a day (board #2, 2026-11-10)."""
    p = 0
    line = bytearray(n)
    for across in (True, False):
        for a in range(n):
            for i in range(n):
                line[i] = g[a * n + i] if across else g[i * n + a]
            run, prev = 0, -1
            for v in line:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        p += run - 2
                    run, prev = 1, v
            if run >= 5:
                p += run - 2
            s = bytes(line)
            p += 40 * (s.count(_FINDER[0]) + s.count(_FINDER[1]))
    for i in range(n - 1):
        k = i * n
        for j in range(k, k + n - 1):
            if g[j] == g[j + 1] == g[j + n] == g[j + n + 1]:
                p += 3
    dark = sum(g)
    k = abs(dark * 100 // (n * n) - 50) // 5
    return p + 10 * k


def encode_map(text, level="L", max_version=6, mask=None):
    """(n, m) for the smallest version that fits, best mask by penalty (or `mask`, for tests): m a
    bytearray of n * n, 1 for a dark module, row by row. Three grids of n * n bytes and one line of
    n, whatever the mask: the grid for each mask is written over the last."""
    for version in range(1, max_version + 1):
        data = _bits(text, version, level)
        if data is not None:
            break
    else:
        raise ValueError("too long for version %d" % max_version)
    n = 17 + 4 * version
    cw = _codewords(data, version, level)
    base, reserved = _matrix(version)
    _place(base, reserved, n, cw)
    g = bytearray(n * n)
    best, best_p = None, None
    for m in (range(8) if mask is None else (mask,)):
        _mask(g, base, reserved, n, m)
        _format(g, n, level, m)
        p = _penalty(g, n)
        if best_p is None or p < best_p:
            best, best_p = m, p
    if best != m:                   # g holds the last mask tried: make the best one again
        _mask(g, base, reserved, n, best)
        _format(g, n, level, best)
    return n, g


def encode(text, level="L", max_version=6, mask=None):
    """(n, rows): rows[r] an int whose bit c is the dark module at column c."""
    n, g = encode_map(text, level, max_version, mask)
    rows = []
    for r in range(n):
        bits = 0
        for c in range(n):
            if g[r * n + c]:
                bits |= 1 << c
        rows.append(bits)
    return n, rows
