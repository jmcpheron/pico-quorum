"""Route the connections the autorouter left open, one at a time, on a grid.

  <KiCad python> tools/gen/finish_route.py <board.kicad_pcb> <drc.json>

Freerouting routed rev B's key port onto rev A's locked routing but for a few long runs it gave up
on (it stops when its score stops improving). This takes each pair of items DRC reports as
unconnected, GND aside (the pours join those), and looks for a path on a 0.1 mm grid on both copper
layers: A*, 45-degree moves, a via costing as much as 2 mm of track. The path keeps every other
net's copper at the board's clearance, the board edge at its edge clearance, and stays out of every
rule area; a via also keeps out of every SMD pad. It is drawn at the net's width (KEY_*, VKEY: 0.25
mm, the Signal class; +3V3: 0.3 mm, as the router draws it), and the pours are refilled. Run DRC
after, as always: this script checks nothing a DRC doesn't.
"""
import heapq
import json
import math
import sys

import pcbnew

GRID = 0.1                      # mm
CLEAR = 0.2 + 0.08              # the board's clearance, and a margin for the grid's diagonal steps
EDGE = 0.3 + 0.08               # copper to the board edge
HOLE_TO_HOLE = 0.25 + 0.05      # the board's least, and a margin
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 20                   # in grid steps: 2 mm of track
WIDTH = {"+3V3": 0.3, "+5V": 0.3}
DEFAULT_WIDTH = 0.25

mm, to_mm = pcbnew.FromMM, pcbnew.ToMM
pcb = sys.argv[1]
report = sys.argv[2] if len(sys.argv) > 2 else None
board = pcbnew.LoadBoard(pcb)

# --- read the board once (KiCad 10's SWIG binding goes stale after a Remove or a second load) ---
outline = pcbnew.SHAPE_POLY_SET()
board.GetBoardPolygonOutlines(outline, False)
bb = outline.BBox()
X0, Y0 = to_mm(bb.GetX()), to_mm(bb.GetY())
NX, NY = int(to_mm(bb.GetWidth()) / GRID) + 2, int(to_mm(bb.GetHeight()) / GRID) + 2
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)

pads, segs, vias, rules = [], [], [], []
for fp in board.GetFootprints():
    for p in fp.Pads():
        on = [l for l in LAYERS if p.IsOnLayer(l)]
        pads.append((p, p.GetNetname(), on, p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD))
for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        vias.append((t.GetNetname(), to_mm(t.GetPosition().x), to_mm(t.GetPosition().y), to_mm(t.GetWidth(pcbnew.F_Cu)) / 2))
    else:
        segs.append((t.GetNetname(), t.GetLayer(), to_mm(t.GetStart().x), to_mm(t.GetStart().y),
                     to_mm(t.GetEnd().x), to_mm(t.GetEnd().y), to_mm(t.GetWidth()) / 2))
for z in board.Zones():
    if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
        rules.append((z, [l for l in LAYERS if z.IsOnLayer(l)], z.GetDoNotAllowVias()))
by_uuid = {}
for p, *_ in pads:
    by_uuid[p.m_Uuid.AsString()] = p
for t in board.GetTracks():
    by_uuid[t.m_Uuid.AsString()] = t


def cell(x, y):
    return int(round((x - X0) / GRID)), int(round((y - Y0) / GRID))


def centre(i, j):
    return X0 + i * GRID, Y0 + j * GRID


def disc(r):
    n = int(math.ceil(r / GRID))
    return [(a, b) for a in range(-n, n + 1) for b in range(-n, n + 1) if (a * GRID) ** 2 + (b * GRID) ** 2 <= r * r]


def mark_poly(grid, poly):
    b = poly.BBox()
    i0, j0 = cell(to_mm(b.GetX()), to_mm(b.GetY()))
    i1, j1 = cell(to_mm(b.GetRight()), to_mm(b.GetBottom()))
    for i in range(max(i0, 0), min(i1 + 1, NX)):
        for j in range(max(j0, 0), min(j1 + 1, NY)):
            x, y = centre(i, j)
            if poly.Contains(pcbnew.VECTOR2I(mm(x), mm(y))):
                grid[j * NX + i] = 1


def mark_disc(grid, x, y, r):
    ci, cj = cell(x, y)
    for a, b in disc(r):
        i, j = ci + a, cj + b
        if 0 <= i < NX and 0 <= j < NY:
            grid[j * NX + i] = 1


def mark_seg(grid, x0, y0, x1, y1, r):
    n = max(1, int(math.hypot(x1 - x0, y1 - y0) / (GRID / 2)))
    for k in range(n + 1):
        mark_disc(grid, x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n, r)


def obstacles(net, w):
    """Per layer: 1 where a track centre of `net` (half width w/2) may not go; and where a via may not."""
    grids = {l: bytearray(NX * NY) for l in LAYERS}
    via = bytearray(NX * NY)
    # outside the board, or too near its edge
    inner = pcbnew.SHAPE_POLY_SET(outline)
    inner.Deflate(mm(EDGE + w / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
    inner_via = pcbnew.SHAPE_POLY_SET(outline)
    inner_via.Deflate(mm(EDGE + VIA_D / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
    for j in range(NY):
        for i in range(NX):
            x, y = centre(i, j)
            v = pcbnew.VECTOR2I(mm(x), mm(y))
            if not inner.Contains(v):
                grids[LAYERS[0]][j * NX + i] = grids[LAYERS[1]][j * NX + i] = 1
            if not inner_via.Contains(v):
                via[j * NX + i] = 1
    for p, pnet, on, smd in pads:
        for l in on:
            if pnet != net or not pnet:
                for g, r in ((grids[l], CLEAR + w / 2), (via, CLEAR + VIA_D / 2)):
                    poly = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(poly, l, mm(r), mm(0.005), pcbnew.ERROR_OUTSIDE)
                    mark_poly(g, poly)
            elif smd:                                   # no via in or beside a pad, even its own net's
                poly = pcbnew.SHAPE_POLY_SET()
                p.TransformShapeToPolygon(poly, l, mm(VIA_D / 2 + 0.05), mm(0.005), pcbnew.ERROR_OUTSIDE)
                mark_poly(via, poly)
        if p.GetDrillSizeX():                           # any hole: a via's hole keeps its distance
            mark_disc(via, to_mm(p.GetPosition().x), to_mm(p.GetPosition().y),
                      to_mm(max(p.GetDrillSizeX(), p.GetDrillSizeY())) / 2 + HOLE_TO_HOLE + VIA_DRILL / 2)
        if not on and p.GetDrillSizeX():                # a bare hole (NPTH)
            r = to_mm(p.GetDrillSizeX()) / 2
            for g in (grids[LAYERS[0]], grids[LAYERS[1]]):
                mark_disc(g, to_mm(p.GetPosition().x), to_mm(p.GetPosition().y), r + CLEAR + w / 2)
            mark_disc(via, to_mm(p.GetPosition().x), to_mm(p.GetPosition().y), r + CLEAR + VIA_D / 2)
    for snet, layer, x0, y0, x1, y1, hw in segs:
        if snet != net and layer in grids:
            mark_seg(grids[layer], x0, y0, x1, y1, hw + CLEAR + w / 2)
            mark_seg(via, x0, y0, x1, y1, hw + CLEAR + VIA_D / 2)
    for vnet, x, y, r in vias:
        if vnet != net:
            for l in LAYERS:
                mark_disc(grids[l], x, y, r + CLEAR + w / 2)
            mark_disc(via, x, y, r + CLEAR + VIA_D / 2)
        else:
            mark_disc(via, x, y, r + VIA_D / 2 + 0.05)  # no via on top of another
    for z, on, no_vias in rules:
        for l in on:
            poly = pcbnew.SHAPE_POLY_SET(z.Outline())
            poly.Inflate(mm(w / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
            mark_poly(grids[l], poly)
        if no_vias:
            poly = pcbnew.SHAPE_POLY_SET(z.Outline())
            poly.Inflate(mm(VIA_D / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
            mark_poly(via, poly)
    return grids, via


def cells_of(item):
    """(layer, i, j) cells inside an item: where a path may start or end."""
    out = set()
    if isinstance(item, pcbnew.PAD):
        for l in LAYERS:
            if item.IsOnLayer(l):
                poly = pcbnew.SHAPE_POLY_SET()
                item.TransformShapeToPolygon(poly, l, 0, mm(0.005), pcbnew.ERROR_INSIDE)
                g = bytearray(NX * NY)
                mark_poly(g, poly)
                out |= {(l, k % NX, k // NX) for k in range(NX * NY) if g[k]}
    elif item.GetClass() == "PCB_VIA":
        i, j = cell(to_mm(item.GetPosition().x), to_mm(item.GetPosition().y))
        out |= {(l, i, j) for l in LAYERS}
    else:
        g = bytearray(NX * NY)
        mark_seg(g, to_mm(item.GetStart().x), to_mm(item.GetStart().y), to_mm(item.GetEnd().x), to_mm(item.GetEnd().y),
                 max(to_mm(item.GetWidth()) / 2 - GRID, 0.0))
        out |= {(item.GetLayer(), k % NX, k // NX) for k in range(NX * NY) if g[k]}
    return out


MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def astar(grids, via, starts, goals):
    other = {LAYERS[0]: LAYERS[1], LAYERS[1]: LAYERS[0]}
    gx = sum(i for _, i, _ in goals) / len(goals)
    gy = sum(j for _, _, j in goals) / len(goals)

    def h(i, j):
        dx, dy = abs(i - gx), abs(j - gy)
        return max(dx, dy) + 0.4142 * min(dx, dy) - 3          # a little under: the goal is an area
    best, came, heap = {}, {}, []
    for s in starts:
        best[s] = 0.0
        heapq.heappush(heap, (h(s[1], s[2]), 0.0, s))
    while heap:
        _, g, s = heapq.heappop(heap)
        if g > best.get(s, 1e18):
            continue
        if s in goals:
            path = [s]
            while path[-1] in came:
                path.append(came[path[-1]])
            return path[::-1]
        l, i, j = s
        steps = [((l, i + di, j + dj), c) for di, dj, c in MOVES]
        if not via[j * NX + i]:
            steps.append(((other[l], i, j), VIA_COST))
        for (nl, ni, nj), c in steps:
            if not (0 <= ni < NX and 0 <= nj < NY):
                continue
            n = (nl, ni, nj)
            if grids[nl][nj * NX + ni] and n not in goals:
                continue
            ng = g + c
            if ng < best.get(n, 1e18):
                best[n], came[n] = ng, s
                heapq.heappush(heap, (ng + h(ni, nj), ng, n))
    return None


def draw(path, net, w):
    """Straight runs as tracks, layer changes as vias. Returns the new copper, to keep clear of next."""
    ni = board.FindNet(net)
    pts = [(l,) + centre(i, j) for l, i, j in path]
    added = []
    run = [pts[0]]

    def flush(run):
        if len(run) < 2:
            return
        # keep only the corners: where the grid step changes direction
        def step(a, b):
            return round((b[1] - a[1]) / GRID), round((b[2] - a[2]) / GRID)
        keep = [run[0]]
        for a, b, c in zip(run, run[1:], run[2:]):
            if step(a, b) != step(b, c):
                keep.append(b)
        keep.append(run[-1])
        for a, b in zip(keep, keep[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(mm(a[1]), mm(a[2]))); t.SetEnd(pcbnew.VECTOR2I(mm(b[1]), mm(b[2])))
            t.SetWidth(mm(w)); t.SetLayer(a[0]); t.SetNet(ni)
            board.Add(t)
            added.append(("seg", net, a[0], a[1], a[2], b[1], b[2], w / 2))
    for p in pts[1:]:
        if p[0] != run[-1][0]:
            flush(run)
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(p[1]), mm(p[2]))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(ni)
            board.Add(v)
            added.append(("via", net, p[1], p[2], VIA_D / 2))
            run = [p]
        else:
            run.append(p)
    flush(run)
    return added


def main():
    pairs = []
    for v in json.load(open(report)).get("unconnected_items", []):
        items = [by_uuid.get(it.get("uuid")) for it in v.get("items", [])]
        if len(items) == 2 and all(items) and items[0].GetNetname() != "GND":
            pairs.append(items)
    print(f"finish_route: {len(pairs)} open connections to route")
    done = 0
    for a, b in pairs:
        net = a.GetNetname()
        w = WIDTH.get(net, DEFAULT_WIDTH)
        grids, via = obstacles(net, w)
        path = astar(grids, via, cells_of(a), cells_of(b))
        if not path:
            print(f"  {net}: no path from {a.GetFriendlyName()} to {b.GetFriendlyName()}")
            continue
        for kind, *rest in draw(path, net, w):
            if kind == "seg":
                segs.append(tuple(rest))
            else:
                vias.append(tuple(rest))
        done += 1
        print(f"  {net}: {len(path)} steps")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(pcb)
    print(f"finish_route: routed {done} of {len(pairs)}; refilled; saved {pcb}")


if __name__ == "__main__":
    main()
