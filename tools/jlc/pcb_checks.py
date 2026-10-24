"""The checks that read the board itself, in KiCad's own Python (pcbnew): the vias and holes, the mask
and paste, the regulator's copper and the ground pour. It also writes facts.json, what the other
checks need from the board, so they need no KiCad. Run by `tools/keypcb jlc`, not by hand:

    <KiCad's python3> pcb_checks.py board.kicad_pcb outdir [spec.json]
    <KiCad's python3> pcb_checks.py --mutate kind board.kicad_pcb     (the self-test's broken boards)

Every line it prints starts "ok", "warn", "FAIL" or "info". Board frame: the drill/place origin
(the files' origin), x right, y up, mm.
"""
import csv, json, math, os, sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from limits import mm as jlc   # noqa: E402

F, B = pcbnew.F_Cu, pcbnew.B_Cu
MAXERR = pcbnew.FromMM(0.005)
STENCIL = 0.12          # mm, JLCPCB's usual stencil
AREA_RATIO = 0.66       # IPC-7525's least area ratio for a clean release


TIGHT = []              # the tightest spots measured, for the zoomed pictures (tight.json)


def say(kind, text):
    print(f"  {kind:<4} {text}")
    return kind == "FAIL"


def tight(what, side, at, value, limit):
    TIGHT.append({"what": what, "side": side, "at": list(at), "value": round(value, 3), "limit": limit})


class Board:
    def __init__(self, path):
        self.b = pcbnew.LoadBoard(path)
        o = self.b.GetDesignSettings().GetAuxOrigin()
        self.ox, self.oy = o.x, o.y

    def xy(self, v):
        return (round(pcbnew.ToMM(v.x - self.ox), 4), round(pcbnew.ToMM(self.oy - v.y), 4))

    def V(self, p):
        return pcbnew.VECTOR2I(int(self.ox + pcbnew.FromMM(p[0])), int(self.oy - pcbnew.FromMM(p[1])))

    def polys(self, ps):
        """A SHAPE_POLY_SET as [[outline, hole, ...], ...] in board mm."""
        out = []
        for i in range(ps.OutlineCount()):
            rings = [ps.Outline(i)] + [ps.Hole(i, k) for k in range(ps.HoleCount(i))]
            out.append([[self.xy(r.CPoint(j)) for j in range(r.PointCount())] for r in rings])
        return out


def dist_point(ps, pt):
    """mm from a point (VECTOR2I) to a SHAPE_POLY_SET's copper; 0 inside."""
    if ps.OutlineCount() == 0:
        return 1e9
    if ps.Contains(pt):
        return 0.0
    return pcbnew.ToMM(math.sqrt(ps.SquaredDistance(pt)))


def item_poly(item, layer, grow=0):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, layer, int(grow), MAXERR, pcbnew.ERROR_INSIDE)
    return ps


def copper_by_net(bd, pours=True):
    """{(layer, netcode): SHAPE_POLY_SET} of the tracks, vias, pads and (with pours) zone fills on
    F.Cu and B.Cu."""
    out = {}

    def add(layer, net, ps):
        out.setdefault((layer, net), pcbnew.SHAPE_POLY_SET()).Append(ps)
    for t in bd.b.GetTracks():
        for l in (F, B):
            if t.IsOnLayer(l):
                add(l, t.GetNetCode(), item_poly(t, l))
    for fp in bd.b.GetFootprints():
        for p in fp.Pads():
            for l in (F, B):
                if p.IsOnLayer(l) and p.IsOnCopperLayer():
                    add(l, p.GetNetCode(), item_poly(p, l))
    for z in bd.b.Zones() if pours else []:
        if z.GetIsRuleArea():
            continue
        for l in (F, B):
            if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
                add(l, z.GetNetCode(), z.GetFilledPolysList(l))
    for ps in out.values():
        ps.Simplify()
    return out


def others(cu, layer, net):
    ps = pcbnew.SHAPE_POLY_SET()
    for (l, n), p in cu.items():
        if l == layer and n != net:
            ps.Append(p)
    return ps


def mask_openings(bd):
    """Each SMD/PTH pad's mask opening on each side it opens: [(pad, side, poly)]."""
    out = []
    for fp in bd.b.GetFootprints():
        for p in fp.Pads():
            for side, ml in ((F, pcbnew.F_Mask), (B, pcbnew.B_Mask)):
                if p.IsOnLayer(ml):
                    out.append((p, side, item_poly(p, ml)))
    return out


def outline_poly(bd):
    ps = pcbnew.SHAPE_POLY_SET()
    bd.b.GetBoardPolygonOutlines(ps, True)
    return ps


def edge_dist(edge, pt):
    """mm from a point inside the board to its outline."""
    d = 1e9
    for i in range(edge.OutlineCount()):
        o = edge.Outline(i)
        for k in range(o.SegmentCount()):
            d = min(d, pcbnew.ToMM(o.CSegment(k).Distance(pt)))
    return d


# ------------------------------------------------------------------------------------------------
# facts.json: what the Gerber, BOM/CPL and fit checks need from the board
# ------------------------------------------------------------------------------------------------

LAYERS = {"F.Cu": F, "B.Cu": B, "F.Mask": pcbnew.F_Mask, "B.Mask": pcbnew.B_Mask, "F.Paste": pcbnew.F_Paste,
          "B.Paste": pcbnew.B_Paste, "F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS}


def facts(bd):
    b = bd.b
    edge = outline_poly(bd)
    bb = edge.BBox()
    f = {"outline": [bd.xy(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetBottom())), bd.xy(pcbnew.VECTOR2I(bb.GetRight(), bb.GetTop()))],
         "thickness": pcbnew.ToMM(b.GetDesignSettings().GetBoardThickness()),
         "vias": [], "pads": [], "footprints": [], "layers": {}}
    f["outline_polys"] = bd.polys(edge)
    for v in b.GetTracks():
        if v.GetClass() == "PCB_VIA":
            f["vias"].append({"at": bd.xy(v.GetPosition()), "drill": pcbnew.ToMM(v.GetDrillValue()),
                              "dia": pcbnew.ToMM(v.GetWidth(F)), "net": v.GetNetname()})
    attr = {pcbnew.PAD_ATTRIB_PTH: "pth", pcbnew.PAD_ATTRIB_NPTH: "npth", pcbnew.PAD_ATTRIB_SMD: "smd",
            pcbnew.PAD_ATTRIB_CONN: "conn"}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        crt = {}
        for side, l in (("F", pcbnew.F_CrtYd), ("B", pcbnew.B_CrtYd)):
            c = fp.GetCourtyard(l)
            if c.OutlineCount():
                cb = c.BBox()
                crt[side] = [bd.xy(pcbnew.VECTOR2I(cb.GetLeft(), cb.GetBottom())), bd.xy(pcbnew.VECTOR2I(cb.GetRight(), cb.GetTop()))]
        a = fp.GetAttributes()
        f["footprints"].append({
            "ref": ref, "fp": fp.GetFPIDAsString().split(":")[-1], "value": fp.GetValue(),
            "side": "B" if fp.GetLayer() == B else "F", "at": bd.xy(fp.GetPosition()),
            "rot": fp.GetOrientationDegrees(), "courtyard": crt, "dnp": bool(fp.IsDNP()),
            "no_bom": bool(a & pcbnew.FP_EXCLUDE_FROM_BOM), "no_pos": bool(a & pcbnew.FP_EXCLUDE_FROM_POS_FILES)})
        for p in fp.Pads():
            d = p.GetDrillSize()
            f["pads"].append({"ref": ref, "num": p.GetNumber(), "net": p.GetNetname(), "kind": attr.get(p.GetAttribute(), "?"),
                              "at": bd.xy(p.GetPosition()), "drill": [pcbnew.ToMM(d.x), pcbnew.ToMM(d.y)],
                              "slot": p.GetDrillShape() == pcbnew.PAD_DRILL_SHAPE_OBLONG and d.x != d.y,
                              "front": p.IsOnLayer(F), "back": p.IsOnLayer(B)})
    for name, l in LAYERS.items():
        ps = pcbnew.SHAPE_POLY_SET()
        b.ConvertBrdLayerToPolygonalContours(l, ps)
        ps.Simplify()
        f["layers"][name] = bd.polys(ps)
    return f


# ------------------------------------------------------------------------------------------------
# 6. vias and holes
# ------------------------------------------------------------------------------------------------

def holes(bd, cu, spec, out):
    b, bad = bd.b, False
    edge = outline_poly(bd)
    allcu = {l: pcbnew.SHAPE_POLY_SET() for l in (F, B)}
    for (l, n), p in cu.items():
        allcu[l].Append(p)
    mask = {}
    for side, ml in ((F, pcbnew.F_Mask), (B, pcbnew.B_Mask)):
        mask[side] = pcbnew.SHAPE_POLY_SET()
        b.ConvertBrdLayerToPolygonalContours(ml, mask[side])
    rows, low_ring, low_pref, near, untented = [], [], [], [], []
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]:
        at, drill, dia = v.GetPosition(), pcbnew.ToMM(v.GetDrillValue()), pcbnew.ToMM(v.GetWidth(F))
        ring = (dia - drill) / 2
        gap = min(dist_point(others(cu, l, v.GetNetCode()), at) for l in (F, B)) - dia / 2
        tented = not any(mask[s].Contains(at) for s in (F, B))
        rows.append(["via", v.GetNetname(), *bd.xy(at), f"{drill:.3f}", f"{dia:.3f}", f"{ring:.3f}", f"{gap:.3f}",
                     f"{edge_dist(edge, at):.3f}", "yes" if tented else "no"])
        if ring < jlc("via_ring") - 1e-6 or drill < jlc("via_drill") - 1e-6:
            low_ring.append(bd.xy(at))
            tight(f"via ring on {v.GetNetname().lstrip('/')}", "F", bd.xy(at), ring, jlc("via_ring"))
        elif ring < jlc("via_ring_preferred") - 1e-6:
            low_pref.append(bd.xy(at))
        if gap < jlc("gap") - 1e-6:
            near.append(bd.xy(at))
        if not tented:
            untented.append(bd.xy(at))
    for r in sorted(rows, key=lambda r: float(r[7]))[:3]:
        tight(f"via on {r[1].lstrip('/')} to other-net copper", "F", (r[2], r[3]), float(r[7]), jlc("gap"))
    tr = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    if tr:
        t = min(tr, key=lambda t: t.GetWidth())
        m = pcbnew.VECTOR2I((t.GetStart().x + t.GetEnd().x) // 2, (t.GetStart().y + t.GetEnd().y) // 2)
        tight(f"narrowest track, {t.GetNetname().lstrip('/')}", "F" if t.GetLayer() == F else "B", bd.xy(m),
              pcbnew.ToMM(t.GetWidth()), jlc("track"))
    sizes = sorted({(r[4], r[5]) for r in rows})
    bad |= say("FAIL" if low_ring else "ok", f"vias: {len(rows)}, drill/diameter {', '.join(f'{d}/{w}' for d, w in sizes)} mm; "
               + (f"{len(low_ring)} under JLCPCB's {jlc('via_drill')} mm drill or {jlc('via_ring')} mm ring, at {low_ring[:4]}"
                  if low_ring else f"each ring at least {jlc('via_ring')} mm a side"))
    if low_pref:
        say("warn", f"{len(low_pref)} vias under JLCPCB's preferred {jlc('via_ring_preferred')} mm ring, at {low_pref[:4]}")
    bad |= say("FAIL" if near else "ok", f"vias: other-net copper at least {jlc('gap')} mm away" if not near else
               f"{len(near)} vias closer than {jlc('gap')} mm to other-net copper, at {near[:4]}")
    say("info", f"vias: {len(rows) - len(untented)} tented, {len(untented)} open" + (f" at {untented[:4]}" if untented else ""))

    plated, npth, small, slots = [], [], [], []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            at, d = p.GetPosition(), p.GetDrillSize()
            dx, dy = pcbnew.ToMM(d.x), pcbnew.ToMM(d.y)
            name = f"{fp.GetReference()}.{p.GetNumber() or '-'}"
            ed = edge_dist(edge, at) - max(dx, dy) / 2
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                cg = min(dist_point(allcu[l], at) for l in (F, B)) - max(dx, dy) / 2
                npth.append((name, fp, at, dx))
                rows.append(["npth", "", *bd.xy(at), f"{dx:.3f}", "", "", f"{cg:.3f}", f"{ed:.3f}", ""])
                if dx < jlc("npth") - 1e-6:
                    small.append(name)
            else:
                s = p.GetSize(F)
                ring = min(pcbnew.ToMM(s.x) - dx, pcbnew.ToMM(s.y) - dy) / 2
                cg = min(dist_point(others(cu, l, p.GetNetCode()), at) for l in (F, B))
                plated.append(name)
                rows.append(["pth", p.GetNetname(), *bd.xy(at), f"{dx:.3f}x{dy:.3f}", f"{pcbnew.ToMM(s.x):.3f}x{pcbnew.ToMM(s.y):.3f}",
                             f"{ring:.3f}", "", f"{ed:.3f}", ""])
                if ring < jlc("pth_ring") - 1e-6:
                    small.append(f"{name} ring {ring:.3f}")
                if not any(t["what"].startswith("plated hole") for t in TIGHT):
                    tight(f"plated hole {name}: ring", "F", bd.xy(at), ring, jlc("pth_ring"))
                if dx != dy and min(dx, dy) < jlc("slot") - 1e-6:
                    small.append(f"{name} slot {min(dx, dy):.3f}")
                if dx != dy:
                    slots.append(name)
    bad |= say("FAIL" if small else "ok", f"plated holes: {len(plated)} ({len(slots)} slots), plain holes: {len(npth)}; "
               + (f"under JLCPCB's limits: {small}" if small else
                  f"rings at least {jlc('pth_ring')}, slots at least {jlc('slot')}, plain holes at least {jlc('npth')} mm"))

    # mounting holes: no track, via or pad under a screw head or washer, on either side; a pour may
    # run under one, behind the mask
    ring = spec.get("hole_ring")
    drawn = {l: pcbnew.SHAPE_POLY_SET() for l in (F, B)}
    for (l, n), p in copper_by_net(bd, pours=False).items():
        if n > 0:
            drawn[l].Append(p)
    for name, fp, at, d in npth:
        if not fp.GetFPIDAsString().split(":")[-1].startswith("MountingHole"):
            continue
        r = ring if ring else d / 2 + 1.0
        cg = min(dist_point(drawn[l], at) for l in (F, B))
        pour = min(dist_point(allcu[l], at) for l in (F, B))
        e = edge_dist(edge, at)
        tight(f"{name.split('.')[0]}: copper from its centre", "F", bd.xy(at), cg, r)
        bad |= say("FAIL" if cg < r - 1e-6 else "ok",
                   f"{name.split('.')[0]}: {d} mm hole; the nearest track, via or pad {cg:.2f} mm from its centre "
                   f"(needs {r}), the pour {pour:.2f}; the edge {e:.2f} mm away")

    # hand-soldered parts (not in the CPL): how their pads join a pour. Solid copper soaks up an iron's heat.
    full = []
    for fp in b.GetFootprints():
        if not (fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES or fp.IsDNP()) or fp.GetFPIDAsString().split(":")[-1].startswith(("MountingHole", "TestPad")):
            continue
        for p in fp.Pads():
            zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == p.GetNetCode() and p.GetNetCode() > 0
                     and any(z.IsOnLayer(l) and p.IsOnLayer(l) for l in (F, B))]
            if not zones:
                continue
            mode = p.GetLocalZoneConnection()
            if mode == pcbnew.ZONE_CONNECTION_INHERITED:
                mode = fp.GetLocalZoneConnection()
            if mode == pcbnew.ZONE_CONNECTION_INHERITED:
                mode = zones[0].GetPadConnection()
            if mode == pcbnew.ZONE_CONNECTION_FULL:
                full.append(f"{fp.GetReference()}.{p.GetNumber()}")
    if full:
        say("warn", f"hand-soldered pads joined to a pour by solid copper (slow to heat with an iron): {', '.join(full)}")
    else:
        say("ok", "hand-soldered pads join their pours by thermal spokes")

    # vias under parts JLCPCB places: tented, so fine, but listed for the look-over
    under = {}
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]:
        for fp in b.GetFootprints():
            if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES or fp.IsDNP():
                continue
            c = fp.GetCourtyard(pcbnew.F_CrtYd if fp.GetLayer() == F else pcbnew.B_CrtYd)
            if c.OutlineCount() and c.Contains(v.GetPosition()):
                under.setdefault(fp.GetReference(), 0)
                under[fp.GetReference()] += 1
    say("info", "vias inside the courtyard of a placed part: " + (", ".join(f"{r} {n}" for r, n in sorted(under.items())) or "none"))

    with open(os.path.join(out, "holes.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "net", "x", "y", "drill", "diameter/pad", "ring", "nearest other-net copper", "to edge", "tented"])
        w.writerows(rows)
    return bad


# ------------------------------------------------------------------------------------------------
# 5. mask and paste
# ------------------------------------------------------------------------------------------------

def mask_paste(bd, cu, spec):
    b, bad = bd.b, False
    ops = mask_openings(bd)
    allowed = set(spec.get("mask_ganged", []))
    thin, thin_same, gangs, webs = [], [], [], []
    for side in (F, B):
        mine = [(p, ps) for p, s, ps in ops if s == side]
        boxes = [ps.BBox() for _, ps in mine]
        for i in range(len(mine)):
            for j in range(i + 1, len(mine)):
                bi, bj = boxes[i], boxes[j]
                pad = pcbnew.FromMM(0.3)
                if bi.GetRight() + pad < bj.GetLeft() or bj.GetRight() + pad < bi.GetLeft() or \
                   bi.GetBottom() + pad < bj.GetTop() or bj.GetBottom() + pad < bi.GetTop():
                    continue
                (p, a), (q, c) = mine[i], mine[j]
                web = mask_gap(a, c)
                name = f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}-{q.GetParentFootprint().GetReference()}.{q.GetNumber()}"
                if p.GetNetCode() != q.GetNetCode():
                    pa, pb = bd.xy(p.GetPosition()), bd.xy(q.GetPosition())
                    webs.append((web, name, "F" if side == F else "B", ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)))
                if web >= jlc("mask_dam") - 1e-6:
                    continue
                if p.GetNetCode() == q.GetNetCode() and p.GetNetCode() > 0:
                    thin_same.append(name)
                elif p.GetParentFootprint().GetReference() in allowed:
                    gangs.append(f"{name} {web:.3f}")
                else:
                    thin.append(f"{name} {web:.3f}")
    bad |= say("FAIL" if thin else "ok", f"mask: every web between different nets' pads at least {jlc('mask_dam')} mm" if not thin else
               f"mask webs under {jlc('mask_dam')} mm between different nets (JLCPCB opens them as one: a bridge risk): {thin[:6]}")
    if gangs:
        say("warn", f"mask webs under {jlc('mask_dam')} mm on parts listed as ganged: {gangs[:6]}")
    if thin_same:
        say("info", f"mask webs under {jlc('mask_dam')} mm within one net (harmless): {len(thin_same)}")
    webs.sort()
    if webs:
        say("info", "the narrowest mask webs between different nets: " + ", ".join(f"{n} {w:.3f}" for w, n, _, _ in webs[:4]))
    for w, n, sd, at in webs[:3]:
        tight(f"mask web {n}", sd, at, w, jlc("mask_dam"))

    # vias in or by an SMD pad's opening: solder runs down them
    wick = []
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]:
        r = pcbnew.ToMM(v.GetWidth(F)) / 2
        for p, s, ps in ops:
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            dd = dist_point(ps, v.GetPosition())
            if dd < r + 0.1:
                wick.append(f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()} at {bd.xy(v.GetPosition())}")
                tight(f"via by {p.GetParentFootprint().GetReference()}.{p.GetNumber()}'s opening", "F" if s == F else "B",
                      bd.xy(v.GetPosition()), max(0.0, dd - r), 0.1)
    bad |= say("FAIL" if wick else "ok", "no via in or within 0.1 mm of an SMD pad's mask opening" if not wick else
               f"vias in or within 0.1 mm of an SMD pad's opening: {wick[:6]}")

    # mask-defined pads (opening smaller than the copper) and paste release
    defined = [f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}" for p, s, ps in ops
               if p.GetSolderMaskExpansion(pcbnew.F_Mask if s == F else pcbnew.B_Mask) < 0]
    say("info", f"mask openings: {len(ops)}, {len(defined)} mask-defined" + (f" ({', '.join(defined[:8])})" if defined else ", the rest copper-defined"))
    ratios = []
    for fp in b.GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES or fp.IsDNP():
            continue
        for p in fp.Pads():
            for pl in (pcbnew.F_Paste, pcbnew.B_Paste):
                if not p.IsOnLayer(pl):
                    continue
                ps = item_poly(p, pl)
                ps.Simplify()
                for i in range(ps.OutlineCount()):
                    o = ps.Outline(i)
                    area = abs(o.Area()) / 1e12
                    per = pcbnew.ToMM(o.Length())
                    if per > 0:
                        ratios.append((area / (per * STENCIL), f"{fp.GetReference()}.{p.GetNumber()}"))
    ratios.sort()
    if ratios:
        ref, num = ratios[0][1].split(".", 1)
        p = next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
        tight(f"paste aperture {ratios[0][1]}: area ratio", "F" if p.IsOnLayer(pcbnew.F_Paste) else "B", bd.xy(p.GetPosition()),
              ratios[0][0], AREA_RATIO)
    low = [f"{n} {r:.2f}" for r, n in ratios if r < AREA_RATIO]
    bad |= say("FAIL" if low else "ok", f"paste: {len(ratios)} apertures, the least area ratio {ratios[0][0]:.2f} ({ratios[0][1]}) "
               f"for a {STENCIL} mm stencil, at least {AREA_RATIO}" if not low and ratios else
               f"paste apertures under area ratio {AREA_RATIO} for a {STENCIL} mm stencil: {low[:6]}")
    return bad


def mask_gap(a, c):
    """The least distance in mm between two small polygon sets' outlines (0 if they overlap)."""
    a2, c2 = pcbnew.SHAPE_POLY_SET(a), pcbnew.SHAPE_POLY_SET(c)
    a2.BooleanIntersection(c2)
    if a2.OutlineCount():
        return 0.0
    best = 1e18
    for s, t in ((a, c), (c, a)):
        for i in range(s.OutlineCount()):
            o = s.Outline(i)
            for k in range(o.PointCount()):
                best = min(best, t.SquaredDistance(o.CPoint(k)))
    return pcbnew.ToMM(math.sqrt(best))


# ------------------------------------------------------------------------------------------------
# 7. the regulator's heat, the ground pour's islands, the signals' return path
# ------------------------------------------------------------------------------------------------

def thermal(bd, cu, spec):
    b, bad = bd.b, False
    reg = spec.get("regulator")
    if reg:
        fp = b.FindFootprintByReference(reg["ref"])
        at = fp.GetPosition()
        area = 0.0
        nets = {p.GetNetCode() for p in fp.Pads()}
        circ = pcbnew.SHAPE_POLY_SET()
        circ.NewOutline()
        for k in range(64):
            a = 2 * math.pi * k / 64
            circ.Append(int(at.x + pcbnew.FromMM(10) * math.cos(a)), int(at.y + pcbnew.FromMM(10) * math.sin(a)))
        for (l, n), p in cu.items():
            if n in nets:
                q = pcbnew.SHAPE_POLY_SET(p)
                q.BooleanIntersection(circ)
                area += q.Area() / 1e12
        vin, vout = reg["vin"], reg["vout"]
        lines = []
        for amps in reg["amps"]:
            w = (vin - vout) * amps
            lines.append(f"{amps:.2f} A: {w:.2f} W, about {w * reg['theta_ja']:.0f} °C over the air")
        say("warn" if max((vin - vout) * a * reg["theta_ja"] for a in reg["amps"]) > 60 else "info",
            f"{reg['ref']} ({reg['part']}): {area:.0f} mm² of its nets' copper within 10 mm; at the datasheet's "
            f"{reg['theta_ja']} °C/W (its least pad, so high): " + "; ".join(lines))

    # islands: pour pieces with no pad or via of their net in them
    isl = []
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() <= 0:
            continue
        net = z.GetNetCode()
        for l in (F, B):
            if not (z.IsOnLayer(l) and z.HasFilledPolysForLayer(l)):
                continue
            ps = z.GetFilledPolysList(l)
            pts = [v.GetPosition() for v in b.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetCode() == net]
            pts += [t.GetStart() for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net and t.IsOnLayer(l)]
            pts += [p.GetPosition() for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetCode() == net and p.IsOnLayer(l)]
            for i in range(ps.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET()
                one.AddOutline(ps.Outline(i))
                if not any(one.Contains(pt) for pt in pts):
                    isl.append(f"{b.GetLayerName(l)} at {bd.xy(ps.Outline(i).CPoint(0))}, {one.Area() / 1e12:.2f} mm²")
                    c = one.BBox().Centre()
                    tight(f"pour island, {one.Area() / 1e12:.2f} mm²", "F" if l == F else "B", bd.xy(c), 0.0, 0.0)
    bad |= say("FAIL" if isl else "ok", "pours: every piece holds a pad, via or track of its net" if not isl else
               f"pour islands (no pad, via or track of their net): {isl[:6]}")

    # return path: how much of each listed signal runs over ground on the other layer
    gnd = b.FindNet("GND")
    if gnd and spec.get("return_nets"):
        fill = {l: pcbnew.SHAPE_POLY_SET() for l in (F, B)}
        for z in b.Zones():
            if not z.GetIsRuleArea() and z.GetNetCode() == gnd.GetNetCode():
                for l in (F, B):
                    if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
                        fill[l].Append(z.GetFilledPolysList(l))
        parts = []
        for name in spec["return_nets"]:
            n = b.FindNet(name)
            if not n:
                continue
            total = over = crossings = 0.0
            for t in b.GetTracks():
                if t.GetClass() != "PCB_TRACK" or t.GetNetCode() != n.GetNetCode():
                    continue
                other = B if t.GetLayer() == F else F
                a, z_ = t.GetStart(), t.GetEnd()
                L = pcbnew.ToMM(t.GetLength())
                k = max(1, int(L / 0.25))
                prev = None
                for i in range(k + 1):
                    pt = pcbnew.VECTOR2I(int(a.x + (z_.x - a.x) * i / k), int(a.y + (z_.y - a.y) * i / k))
                    on = fill[other].Contains(pt)
                    if i:
                        total += L / k
                        over += L / k if on else 0
                    if prev is not None and prev and not on:
                        crossings += 1
                    prev = on
            if total:
                parts.append(f"{name.lstrip('/')} {100 * over / total:.0f}% of {total:.1f} mm, off it {int(crossings)}x")
        say("info", "over ground on the other layer: " + "; ".join(parts))
    return bad


# ------------------------------------------------------------------------------------------------
# the self-test's broken boards
# ------------------------------------------------------------------------------------------------

def mutate(kind, path):
    bd = Board(path)
    b = bd.b
    vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
    tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    if kind == "track":            # one track at 0.08 mm, under JLCPCB's 0.10
        t = max(tracks, key=lambda t: t.GetLength())
        t.SetWidth(pcbnew.FromMM(0.08))
    elif kind == "ring":           # one via with a 0.025 mm ring
        vias[0].SetWidth(vias[0].GetDrillValue() + pcbnew.FromMM(0.05))
    elif kind == "wick":           # a ground via against a ground SMD pad
        p = next(p for fp in b.GetFootprints() for p in fp.Pads()
                 if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and not fp.IsDNP()
                 and not fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(p.GetPosition())
        v.SetWidth(vias[0].GetWidth(F))
        v.SetDrill(vias[0].GetDrillValue())
        v.SetNet(p.GetNet())
        b.Add(v)
    elif kind == "island":         # a scrap of ground pour joined to nothing
        gnd = b.FindNet("GND")
        z = pcbnew.ZONE(b)
        z.SetLayer(B)
        z.SetNet(gnd)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        x, y = b.GetDesignSettings().GetAuxOrigin().x, b.GetDesignSettings().GetAuxOrigin().y
        o = z.Outline()
        o.NewOutline()
        for dx, dy in ((0.6, -0.6), (1.4, -0.6), (1.4, -1.4), (0.6, -1.4)):
            o.Append(int(x + pcbnew.FromMM(dx)), int(y + pcbnew.FromMM(dy)))
        b.Add(z)
        pcbnew.ZONE_FILLER(b).Fill([z])
    elif kind == "net":            # one pad on the wrong net
        fp = next(fp for fp in b.GetFootprints() if fp.GetReference().startswith("R") and len(fp.Pads()) == 2)
        fp.Pads()[0].SetNet(b.FindNet("GND"))
    else:
        sys.exit(f"no mutation {kind!r}")
    pcbnew.SaveBoard(path, b)


def main():
    if sys.argv[1] == "--mutate":
        mutate(sys.argv[2], sys.argv[3])
        return
    pcb, out = sys.argv[1], sys.argv[2]
    spec = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
    bd = Board(pcb)
    os.makedirs(out, exist_ok=True)
    json.dump(facts(bd), open(os.path.join(out, "facts.json"), "w"))
    cu = copper_by_net(bd)
    which = os.environ.get("JLC_ONLY", "holes,mask,thermal").split(",")
    bad = False
    if "holes" in which:
        print("6. vias and holes")
        bad |= holes(bd, cu, spec, out)
    if "mask" in which:
        print("5. mask and paste")
        bad |= mask_paste(bd, cu, spec)
    if "thermal" in which:
        print("7. heat, pours, return path")
        bad |= thermal(bd, cu, spec)
    if TIGHT:
        json.dump(TIGHT, open(os.path.join(out, "tight.json"), "w"), indent=1)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
