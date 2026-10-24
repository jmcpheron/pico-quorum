"""Draw a Gerber or drill layer (tests/gerber.py objects) into a bitmap. Standard library only.

Not a full Gerber renderer: flashes (circle, rectangle, obround, rounded rectangle), strokes with
round ends (arcs drawn as their chord), filled regions (even-odd), and clear-polarity flashes drawn
last, which is what KiCad 10 writes for this board. The point is a picture that changes when the
fab output changes, drawn by code that shares nothing with KiCad's plotter.
"""
import math

import pngio


class Raster:
    """A one-byte-per-pixel bitmap over a board-sized window. Coordinates in mm in the Gerber frame
    (origin bottom-left, y up); (x0, y0, x1, y1) is the window, scale in pixels per mm."""

    def __init__(self, window, scale):
        self.x0, self.y0, self.x1, self.y1 = window
        self.s = scale
        self.w = int(math.ceil((self.x1 - self.x0) * scale))
        self.h = int(math.ceil((self.y1 - self.y0) * scale))
        self.px = bytearray(self.w * self.h)

    def to_px(self, x, y):
        return (x - self.x0) * self.s, (self.y1 - y) * self.s

    def _span(self, row, a, b, v):
        if 0 <= row < self.h:
            a, b = max(0, a), min(self.w, b)
            if b > a:
                self.px[row * self.w + a:row * self.w + b] = bytes([v]) * (b - a)

    def disc(self, x, y, r, v=1):
        cx, cy = self.to_px(x, y)
        rp = r * self.s
        for row in range(int(cy - rp), int(cy + rp) + 2):
            dy = row + 0.5 - cy
            if abs(dy) <= rp:
                dx = math.sqrt(rp * rp - dy * dy)
                self._span(row, int(round(cx - dx)), int(round(cx + dx)), v)

    def rect(self, x, y, hx, hy, r=0.0, v=1):
        """Axis-aligned rectangle centred on (x, y), half extents hx, hy, corner radius r."""
        cx, cy = self.to_px(x, y)
        hxp, hyp, rp = hx * self.s, hy * self.s, r * self.s
        for row in range(int(cy - hyp), int(cy + hyp) + 2):
            dy = abs(row + 0.5 - cy)
            if dy > hyp:
                continue
            inset = 0.0
            if rp > 0 and dy > hyp - rp:
                t = dy - (hyp - rp)
                inset = rp - math.sqrt(max(rp * rp - t * t, 0.0))
            self._span(row, int(round(cx - hxp + inset)), int(round(cx + hxp - inset)), v)

    def capsule(self, xa, ya, xb, yb, r, v=1):
        """A stroke from a to b with round ends, radius r."""
        ax, ay = self.to_px(xa, ya)
        bx, by = self.to_px(xb, yb)
        rp = max(r * self.s, 0.5)
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        for row in range(int(min(ay, by) - rp), int(max(ay, by) + rp) + 2):
            if not 0 <= row < self.h:
                continue
            py = row + 0.5
            lo, hi = None, None
            for col in range(max(0, int(min(ax, bx) - rp)), min(self.w, int(max(ax, bx) + rp) + 2)):
                pxx = col + 0.5
                t = 0.0 if ll == 0 else max(0.0, min(1.0, ((pxx - ax) * dx + (py - ay) * dy) / ll))
                if (pxx - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2 <= rp * rp:
                    lo = col if lo is None else lo
                    hi = col
            if lo is not None:
                self._span(row, lo, hi + 1, v)

    def polygon(self, pts, v=1):
        """Even-odd fill; pts in mm."""
        P = [self.to_px(x, y) for x, y in pts]
        ys = [p[1] for p in P]
        for row in range(max(0, int(min(ys))), min(self.h, int(max(ys)) + 2)):
            py = row + 0.5
            xs = []
            for (xa, ya), (xb, yb) in zip(P, P[1:] + P[:1]):
                if (ya <= py < yb) or (yb <= py < ya):
                    xs.append(xa + (py - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for a, b in zip(xs[0::2], xs[1::2]):
                self._span(row, int(round(a)), int(round(b)), v)

    def flash(self, x, y, ap, v=1):
        if ap.half is None:
            return False
        hx, hy = ap.half
        if ap.kind == "C":
            self.disc(x, y, hx, v)
        elif ap.kind == "O":
            self.rect(x, y, hx, hy, min(hx, hy), v)
        elif ap.kind == "RoundRect":
            self.rect(x, y, hx, hy, ap.params[0], v)
        else:
            self.rect(x, y, hx, hy, 0.0, v)
        return True

    def to_image(self, fg, bg=(20, 24, 28)):
        rows = []
        on, off = bytes(fg), bytes(bg)
        for y in range(self.h):
            line = self.px[y * self.w:(y + 1) * self.w]
            rows.append(bytearray(b"".join(on if c else off for c in line)))
        return pngio.Image(self.w, self.h, 3, rows)


def draw_gerber(g, window, scale):
    r = Raster(window, scale)
    skipped = 0
    for reg in g.regions:
        r.polygon(reg)
    for x0, y0, x1, y1, ap, kind in g.strokes:
        r.capsule(x0, y0, x1, y1, (ap.half or (0.05, 0.05))[0])
    for x, y, ap in g.flashes:
        skipped += not r.flash(x, y, ap)
    for x, y, ap in g.clears:
        r.flash(x, y, ap, 0)
    return r, skipped


def draw_drill(drills, window, scale):
    r = Raster(window, scale)
    for d in drills:
        for dia, x, y in d.hits:
            r.disc(x, y, dia / 2)
        for dia, xa, ya, xb, yb in d.slots:
            r.capsule(xa, ya, xb, yb, dia / 2)
    return r
