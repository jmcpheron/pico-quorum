"""A small reader for the files that go to the fab: RS-274X Gerber and Excellon drill. Stdlib only.

It is deliberately not KiCad: the point of test_fab_files is to read back what was written with
code that shares nothing with the code that wrote it. It covers what KiCad 10 emits (FS/MO,
standard and RoundRect apertures, G01/G02/G03 with G75, D01/D02/D03, G36/G37 regions, Excellon
tools, hits and G85 slots), not the whole of either format.

Coordinates come back in millimetres in the file's own frame (for this project: the drill/place
origin at the board's bottom-left, Y up).
"""
import math
import re
import zipfile


class Aperture:
    def __init__(self, code, kind, params, function=None):
        self.code, self.kind, self.params, self.function = code, kind, params, function
        if kind == "C":
            self.half = (params[0] / 2, params[0] / 2)
        elif kind in ("R", "O"):
            self.half = (params[0] / 2, params[1] / 2)
        elif kind == "RoundRect":              # radius, 4 corner centres, rotation
            r, xs, ys = params[0], params[1:9:2], params[2:9:2]
            self.half = (max(abs(v) for v in xs) + r, max(abs(v) for v in ys) + r)
        else:
            self.half = None                   # other macros: extent unknown

    @property
    def size(self):
        return None if self.half is None else (2 * self.half[0], 2 * self.half[1])

    def __repr__(self):
        return "Aperture(D%d %s %s %s)" % (self.code, self.kind, self.params, self.function)


class Gerber:
    """flashes: [(x, y, Aperture)]; strokes: [(x0, y0, x1, y1, Aperture, kind)] with kind 'line'
    or 'arc' (arcs carry their end points only); regions: [[(x, y), ...]]; attrs: file attributes.
    Only dark-polarity (%LPD%) objects land there; clear-polarity flashes go to `clears` (KiCad uses
    them to cut silk away from pads)."""

    def __init__(self, text):
        self.apertures, self.flashes, self.strokes, self.regions = {}, [], [], []
        self.attrs, self.macros, self.clears = {}, set(), []
        self.dark = True
        self.scale = None
        self._parse(text)

    def _num(self, s):
        return int(s) * self.scale

    def _parse(self, text):
        x = y = 0.0
        cur, interp, in_region, region = None, "G01", False, []
        pending_function = None
        # split into %...% extended blocks and *-terminated words
        for block in re.findall(r"%[^%]*%|[^%*]+\*", text, re.S):
            block = block.strip()
            if block.startswith("%"):
                body = block.strip("%").strip()
                if body.startswith("FS"):
                    m = re.match(r"FSLAX(\d)(\d)Y(\d)(\d)", body)
                    self.scale = 10.0 ** -int(m.group(2))
                elif body.startswith("MO") and "MOMM" not in body:
                    raise ValueError("only millimetre Gerbers are handled")
                elif body.startswith("AM"):
                    self.macros.add(re.match(r"AM([\w.$]+)\*", body).group(1))
                elif body.startswith("AD"):
                    m = re.match(r"ADD(\d+)([\w.$]+?)(?:,([^*]*))?\*?$", body.rstrip("*"))
                    code, kind = int(m.group(1)), m.group(2)
                    params = [float(v) for v in m.group(3).split("X")] if m.group(3) else []
                    self.apertures[code] = Aperture(code, kind, params, pending_function)
                elif body.startswith("LP"):
                    self.dark = body[2] == "D"
                elif body.startswith("TF"):
                    name, _, value = body[3:].rstrip("*").partition(",")
                    self.attrs[name] = value
                continue
            w = block.rstrip("*")
            if w.startswith("G04"):
                m = re.match(r"G04 #@! (TF|TA|TD)\.?(\w*),?(.*)", w)
                if m and m.group(1) == "TF":
                    self.attrs[m.group(2)] = m.group(3)
                elif m and m.group(1) == "TA" and m.group(2) == "AperFunction":
                    pending_function = m.group(3)
                elif m and m.group(1) == "TD":
                    pending_function = None
                continue
            if w in ("G01", "G02", "G03"):
                interp = w
                continue
            if w in ("G75", "G74", "%LPD", "M02"):
                continue
            if w == "G36":
                in_region, region = True, []
                continue
            if w == "G37":
                if region:
                    self.regions.append(region)
                in_region = False
                continue
            m = re.fullmatch(r"(G0[123])?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?(D0[123])?", w)
            if m and (m.group(2) or m.group(3) or m.group(6)):
                if m.group(1):
                    interp = m.group(1)
                nx = self._num(m.group(2)) if m.group(2) else x
                ny = self._num(m.group(3)) if m.group(3) else y
                op = m.group(6) or "D01"
                if op == "D03":
                    (self.flashes if self.dark else self.clears).append((nx, ny, self.apertures[cur]))
                elif op == "D01":
                    if in_region:
                        if not region:
                            region.append((x, y))
                        region.append((nx, ny))
                    elif self.dark:
                        self.strokes.append((x, y, nx, ny, self.apertures[cur], "line" if interp == "G01" else "arc"))
                elif op == "D02" and in_region:
                    if region:
                        self.regions.append(region)
                    region = [(nx, ny)]
                x, y = nx, ny
                continue
            m = re.fullmatch(r"D(\d+)", w)
            if m and int(m.group(1)) >= 10:
                cur = int(m.group(1))
                continue

    def extent(self):
        """(x0, y0, x1, y1) of everything drawn, apertures included."""
        xs, ys = [], []
        for x, y, ap in self.flashes:
            hx, hy = ap.half or (0, 0)
            xs += [x - hx, x + hx]; ys += [y - hy, y + hy]
        for x0, y0, x1, y1, ap, _ in self.strokes:
            r = (ap.half or (0, 0))[0]
            xs += [x0 - r, x0 + r, x1 - r, x1 + r]; ys += [y0 - r, y0 + r, y1 - r, y1 + r]
        for reg in self.regions:
            xs += [p[0] for p in reg]; ys += [p[1] for p in reg]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None


class Drill:
    """tools: {T: diameter}; hits: [(diameter, x, y)]; slots: [(diameter, x0, y0, x1, y1)]; plated: bool."""

    def __init__(self, text):
        self.tools, self.hits, self.slots, self.functions = {}, [], [], {}
        self.plated = None
        cur, pending = None, None
        for line in text.splitlines():
            line = line.strip()
            if "TF.FileFunction" in line:
                self.plated = "NonPlated" not in line
            m = re.match(r"; #@! TA.AperFunction,(.*)", line)
            if m:
                pending = m.group(1)
                continue
            m = re.fullmatch(r"T(\d+)C([\d.]+)", line)
            if m:
                self.tools[int(m.group(1))] = float(m.group(2))
                self.functions[int(m.group(1))] = pending
                continue
            m = re.fullmatch(r"T(\d+)", line)
            if m:
                cur = int(m.group(1))
                continue
            m = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)G85X(-?[\d.]+)Y(-?[\d.]+)", line)
            if m:
                self.slots.append((self.tools[cur],) + tuple(float(v) for v in m.groups()))
                continue
            m = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
            if m:
                self.hits.append((self.tools[cur], float(m.group(1)), float(m.group(2))))


def read_zip(path):
    """{filename: text} for every file in the fab zip."""
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n).decode("ascii", "replace") for n in z.namelist()}


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)
