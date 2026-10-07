"""A small two-layer grid router for console-a: A* on a 0.25 mm grid, eight directions, vias between
F.Cu and B.Cu. Pure Python, no KiCad and no numpy, so gen.py can run it inside KiCad's own Python.

It routes one connection at a time, from an unconnected pad to the copper its net already has. Every
cell carries the net that owns the space around it, so a track of another net can't come closer
than the clearance. The result is plain segments and vias for gen.py to put on the board, and
KiCad's DRC checks it all again afterwards. All lengths are mm, in the board's frame: x to the
right, y down, (0, 0) at the board's top-left corner.
"""
import heapq, math
from array import array

STEP = 0.25
TRACK = 0.25          # every routed track
CLEAR = 0.15          # copper to copper; the netclass asks for this too
VIA_D, VIA_DRILL = 0.6, 0.3
HOLE_GAP = 0.5        # JLCPCB: drill edge to drill edge
EDGE = 0.3            # copper to board edge
VIA_COST = 6.0        # in mm of track: a via is worth this much detour
TURN_COST = 0.3
BACK_COST = 1.15      # B.Cu costs a little more than F.Cu per mm, so the front is tried first

FREE, BLOCKED = 0, -1
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


class NoRoute(Exception):
    pass


def _d_rect(px, py, x0, y0, x1, y1):
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return math.hypot(dx, dy)


def _d_seg(px, py, x0, y0, x1, y1):
    vx, vy = x1 - x0, y1 - y0
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / L))
    return math.hypot(px - x0 - t * vx, py - y0 - t * vy)


class Grid:
    def __init__(self, W, H):
        self.nx, self.ny = int(round(W / STEP)) + 1, int(round(H / STEP)) + 1
        n = self.nx * self.ny
        # trk[l]: who owns the space a track centreline may use; via[l]: the same for a via centre;
        # cu[l]: the copper itself (the net's tree, or a pad not yet joined: see joined)
        self.trk = [array("i", [FREE]) * n for _ in range(2)]
        self.via = [array("i", [FREE]) * n for _ in range(2)]
        self.cu = [array("i", [FREE]) * n for _ in range(2)]
        self.joined = [array("b", [0]) * n for _ in range(2)]   # copper that is part of its net's tree
        self.pad = [array("b", [0]) * n for _ in range(2)]      # inside a pad: no via here
        self.ids, self.names = {}, {}
        self.segs, self.vias = [], []

    def nid(self, net):
        if net not in self.ids:
            self.ids[net] = len(self.ids) + 1
            self.names[self.ids[net]] = net
        return self.ids[net]

    def xy(self, c):
        return (c % self.nx) * STEP, (c // self.nx) * STEP

    def cell(self, x, y):
        return int(round(y / STEP)) * self.nx + int(round(x / STEP))

    def _cells(self, bbox, r, dist):
        x0, y0, x1, y1 = bbox
        i0, i1 = max(0, int((x0 - r) / STEP)), min(self.nx - 1, int(math.ceil((x1 + r) / STEP)))
        j0, j1 = max(0, int((y0 - r) / STEP)), min(self.ny - 1, int(math.ceil((y1 + r) / STEP)))
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                if dist(i * STEP, j * STEP) <= r:
                    yield j * self.nx + i

    @staticmethod
    def _own(arr, c, v):
        o = arr[c]
        if o == FREE:
            arr[c] = v
        elif o != v:
            arr[c] = BLOCKED

    def claim(self, layers, net, bbox, dist, trk_r, via_r, cu_r=None, joined=False, pad=False):
        """Mark the space around a piece of copper (dist: distance from a point to its edge)."""
        v = self.nid(net) if net else BLOCKED
        for l in layers:
            for c in self._cells(bbox, trk_r, dist):
                self._own(self.trk[l], c, v)
            for c in self._cells(bbox, via_r, dist):
                self._own(self.via[l], c, v)
            if cu_r is not None and net:
                for c in self._cells(bbox, cu_r, dist):
                    self.cu[l][c] = v
                    if joined:
                        self.joined[l][c] = 1
                    if pad:
                        self.pad[l][c] = 1

    def add_pad(self, layers, net, x0, y0, x1, y1, inside=None):
        """A pad, as its bounding box (which is what other nets keep clear of). inside(x, y) is the
        pad's real shape: only there may a track of its own net end."""
        bb = (x0, y0, x1, y1)
        self.claim(layers, net, bb, lambda px, py: _d_rect(px, py, *bb), CLEAR + TRACK / 2, CLEAR + VIA_D / 2)
        if net:
            v = self.nid(net)
            for l in layers:
                for c in self._cells(bb, 0.0, lambda px, py: _d_rect(px, py, *bb)):
                    self.pad[l][c] = 1
                    if inside is None or inside(*self.xy(c)):
                        self.cu[l][c] = v

    def add_hole(self, x, y, d):
        """A plain drilled hole, no copper."""
        dist = lambda px, py: math.hypot(px - x, py - y) - d / 2
        self.claim((0, 1), None, (x, y, x, y), dist, 0.25 + TRACK / 2, HOLE_GAP + VIA_DRILL / 2)

    def block(self, layers, x0, y0, x1, y1, trk=True):
        bb = (x0, y0, x1, y1)
        dist = lambda px, py: _d_rect(px, py, *bb)
        for l in layers:
            for c in self._cells(bb, TRACK / 2, dist):
                if trk:
                    self.trk[l][c] = BLOCKED
            for c in self._cells(bb, VIA_D / 2, dist):
                self.via[l][c] = BLOCKED

    def block_outside(self, inside, edge_dist):
        """inside(x, y) is the board outline; edge_dist(x, y) the distance to it."""
        for c in range(self.nx * self.ny):
            x, y = self.xy(c)
            if not inside(x, y):
                d = 0.0
            else:
                d = edge_dist(x, y)
            for l in (0, 1):
                if d < EDGE + TRACK / 2:
                    self.trk[l][c] = BLOCKED
                if d < EDGE + VIA_D / 2:
                    self.via[l][c] = BLOCKED

    def add_seg(self, l, net, a, b, width=TRACK, joined=True):
        bb = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        dist = lambda px, py: _d_seg(px, py, a[0], a[1], b[0], b[1]) - width / 2
        self.claim((l,), net, bb, dist, CLEAR + TRACK / 2, CLEAR + VIA_D / 2, cu_r=-width / 2 + 0.01, joined=joined)
        self.segs.append((l, net, a, b, width))

    def add_via(self, net, x, y, joined=True):
        dist = lambda px, py: math.hypot(px - x, py - y) - VIA_D / 2
        self.claim((0, 1), net, (x, y, x, y), dist, CLEAR + TRACK / 2, max(CLEAR + VIA_D / 2, HOLE_GAP + VIA_DRILL - VIA_D / 2),
                   cu_r=0.0, joined=joined)
        self.vias.append((net, x, y))

    def join(self, net, l, cells):
        for c in cells:
            self.joined[l][c] = 1

    def pad_cells(self, l, net, x0, y0, x1, y1):
        v = self.nid(net)
        return [c for c in self._cells((x0, y0, x1, y1), 0.0, lambda px, py: _d_rect(px, py, x0, y0, x1, y1))
                if self.cu[l][c] == v]

    # ---------------------------------------------------------------------------------------------
    def route(self, net, starts, to_via=False, limit=3_000_000):
        """A* from starts [(layer, cell)] to the net's joined copper (or, with to_via, to the
        nearest place a via of this net fits). Returns the path as [(layer, cell)]."""
        v = self.nid(net)
        nx = self.nx
        trk, via, cu, joined, pad = self.trk, self.via, self.cu, self.joined, self.pad
        if to_via:
            goal = lambda l, c: (via[0][c] in (FREE, v) and via[1][c] in (FREE, v) and not pad[0][c] and not pad[1][c])
            h = lambda l, c: 0.0
        else:
            tx, ty = [], []
            for l in (0, 1):
                for c in range(len(cu[l])):
                    if cu[l][c] == v and joined[l][c]:
                        tx.append(c % nx); ty.append(c // nx)
            if not tx:
                raise NoRoute(f"{net}: nothing to connect to")
            bx0, bx1, by0, by1 = min(tx), max(tx), min(ty), max(ty)
            goal = lambda l, c: cu[l][c] == v and joined[l][c]

            def h(l, c):
                i, j = c % nx, c // nx
                dx = max(bx0 - i, 0, i - bx1)
                dy = max(by0 - j, 0, j - by1)
                return STEP * (max(dx, dy) + 0.4142 * min(dx, dy))
        best, prev = {}, {}
        heap = []
        for l, c in starts:
            if goal(l, c):
                return [(l, c)]
            s = (l * len(cu[0]) + c) * 9 + 8
            best[s] = 0.0
            heapq.heappush(heap, (h(l, c), 0.0, s))
        n = len(cu[0])
        steps = 0
        while heap:
            f, g, s = heapq.heappop(heap)
            if g > best.get(s, 1e18):
                continue
            steps += 1
            if steps > limit:
                break
            d = s % 9
            lc = s // 9
            l, c = lc // n, lc % n
            if goal(l, c) and g > 0:
                path = [(l, c)]
                while s in prev:
                    s = prev[s]
                    lc = s // 9
                    path.append((lc // n, lc % n))
                return path[::-1]
            i, j = c % nx, c // nx
            k = BACK_COST if l == 1 else 1.0
            for nd, (di, dj) in enumerate(DIRS):
                if d != 8:
                    turn = min((nd - d) % 8, (d - nd) % 8)
                    if turn > 2:
                        continue
                else:
                    turn = 0
                ii, jj = i + di, j + dj
                if not (0 <= ii < nx and 0 <= jj < self.ny):
                    continue
                cc = jj * nx + ii
                o = trk[l][cc]
                if o != FREE and o != v:
                    continue
                if di and dj:
                    o1, o2 = trk[l][j * nx + ii], trk[l][jj * nx + i]
                    if (o1 != FREE and o1 != v) or (o2 != FREE and o2 != v):
                        continue
                cost = STEP * (1.4142 if di and dj else 1.0) * k + TURN_COST * turn
                ns = ((l * n + cc) * 9) + nd
                ng = g + cost
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    prev[ns] = s
                    heapq.heappush(heap, (ng + h(l, cc), ng, ns))
            # a via here, to the other layer
            o0, o1 = via[0][c], via[1][c]
            if (o0 == FREE or o0 == v) and (o1 == FREE or o1 == v) and not pad[0][c] and not pad[1][c] \
                    and trk[1 - l][c] in (FREE, v):
                ns = (((1 - l) * n + c) * 9) + 8
                ng = g + VIA_COST
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    prev[ns] = s
                    heapq.heappush(heap, (ng + h(1 - l, c), ng, ns))
        raise NoRoute(f"{net}: no path ({steps} steps)")

    def commit(self, net, path, end_via=False):
        """Turn a path into straight segments and vias, and claim their space."""
        pts = [(l, self.xy(c)) for l, c in path]
        runs, cur = [], [pts[0]]
        for p in pts[1:]:
            if p[0] != cur[-1][0]:
                runs.append(cur)
                self.add_via(net, *p[1])
                cur = [p]
            else:
                cur.append(p)
        runs.append(cur)
        for run in runs:
            l = run[0][0]
            xy = [p[1] for p in run]
            # keep only the corners
            keep = [xy[0]]
            for a, b, c in zip(xy, xy[1:], xy[2:]):
                if (round((b[0] - a[0]) / STEP), round((b[1] - a[1]) / STEP)) != \
                        (round((c[0] - b[0]) / STEP), round((c[1] - b[1]) / STEP)):
                    keep.append(b)
            keep.append(xy[-1])
            for a, b in zip(keep, keep[1:]):
                if a != b:
                    self.add_seg(l, net, a, b)
        if end_via:
            self.add_via(net, *pts[-1][1])
        for l, c in path:
            self.joined[l][c] = 1
