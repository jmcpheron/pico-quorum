"""Dump the geometry of a .kicad_pcb as JSON. Run with KiCad's own Python (it imports pcbnew):

    $KICAD_PYTHON tests/pcb_facts.py hardware/picoquorum-key/picoquorum-key.kicad_pcb out.json

Coordinates are millimetres, relative to the board's top-left corner (the Edge.Cuts bounding box),
so they read the same as the placement table in docs/DESIGN.md.
"""
import json
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
# Outline extent from the Edge.Cuts line endpoints, so the stroke width doesn't shift the origin.
_ends = [p for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts and d.GetClass() == "PCB_SHAPE"
         and d.GetShape() == pcbnew.SHAPE_T_SEGMENT for p in (d.GetStart(), d.GetEnd())]
OX, OY = pcbnew.ToMM(min(p[0] for p in _ends)), pcbnew.ToMM(min(p[1] for p in _ends))
W, H = pcbnew.ToMM(max(p[0] for p in _ends)) - OX, pcbnew.ToMM(max(p[1] for p in _ends)) - OY


def mm(v):
    return round(pcbnew.ToMM(v), 4)


def pt(p):
    return [round(pcbnew.ToMM(p[0]) - OX, 4), round(pcbnew.ToMM(p[1]) - OY, 4)]


def layer_name(i):
    return board.GetLayerName(i)


facts = {"board": {"w": round(W, 4), "h": round(H, 4)}, "footprints": {}, "tracks": [],
         "vias": [], "zones": [], "silk": []}

def courtyard(fp):
    """Courtyard box on the footprint's own side, or None."""
    c = fp.GetCourtyard(pcbnew.B_CrtYd if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_CrtYd)
    if not c.OutlineCount():
        return None
    bb = c.BBox()
    return pt((bb.GetX(), bb.GetY())) + pt((bb.GetRight(), bb.GetBottom()))


ZONE_CONNECTION = {int(pcbnew.ZONE_CONNECTION_INHERITED): "inherited", int(pcbnew.ZONE_CONNECTION_NONE): "none",
                   int(pcbnew.ZONE_CONNECTION_THERMAL): "thermal", int(pcbnew.ZONE_CONNECTION_FULL): "full",
                   int(pcbnew.ZONE_CONNECTION_THT_THERMAL): "tht_thermal"}

for fp in board.GetFootprints():
    pads = []
    for p in fp.Pads():
        sz = p.GetSize()
        pb = p.GetBoundingBox()
        ds = p.GetDrillSize()
        layers = [layer_name(l) for l in p.GetLayerSet().Seq()]
        pads.append({"number": p.GetNumber(), "pos": pt(p.GetPosition()), "net": p.GetNetname(),
                     "bbox": pt((pb.GetX(), pb.GetY())) + pt((pb.GetRight(), pb.GetBottom())),
                     "size": [mm(sz[0]), mm(sz[1])], "layer": layer_name(p.GetLayer()),
                     "copper": [l for l in layers if l.endswith(".Cu")],
                     "mask": [l for l in layers if l.endswith(".Mask")],
                     "paste": [l for l in layers if l.endswith(".Paste")],
                     "attr": {pcbnew.PAD_ATTRIB_PTH: "PTH", pcbnew.PAD_ATTRIB_NPTH: "NPTH",
                              pcbnew.PAD_ATTRIB_SMD: "SMD", pcbnew.PAD_ATTRIB_CONN: "CONN"}[p.GetAttribute()],
                     "drill": mm(ds[0]), "drill_xy": [mm(ds[0]), mm(ds[1])],
                     "drill_oblong": p.GetDrillShape() == pcbnew.PAD_DRILL_SHAPE_OBLONG,
                     "orient": p.GetOrientationDegrees(),
                     "zone_connection": ZONE_CONNECTION.get(int(p.GetLocalZoneConnection()), "?"),
                     "shape": p.ShapeName() if hasattr(p, "ShapeName") else str(p.GetShape())})
    facts["footprints"][fp.GetReference()] = {
        "pos": pt(fp.GetPosition()), "rot": fp.GetOrientationDegrees(), "layer": layer_name(fp.GetLayer()),
        "lib": str(fp.GetFPID().GetLibItemName()), "pads": pads, "dnp": bool(fp.IsDNP()),
        "exclude_pos": bool(fp.IsExcludedFromPosFiles()), "exclude_bom": bool(fp.IsExcludedFromBOM()),
        "courtyard": courtyard(fp)}

for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        facts["vias"].append({"pos": pt(t.GetPosition()), "net": t.GetNetname(), "size": mm(t.GetWidth(t.GetLayer())),
                              "drill": mm(t.GetDrillValue())})
    else:
        facts["tracks"].append({"a": pt(t.GetStart()), "b": pt(t.GetEnd()), "w": mm(t.GetWidth()),
                                "layer": layer_name(t.GetLayer()), "net": t.GetNetname(),
                                "len": mm(t.GetLength())})

for z in board.Zones():
    for lid in z.GetLayerSet().Seq():
        entry = {"name": z.GetZoneName(), "net": z.GetNetname(), "layer": layer_name(lid),
                 "rule_area": z.GetIsRuleArea(),
                 "pad_connection": ZONE_CONNECTION.get(int(z.GetPadConnection()), "?"),
                 "spoke_width": mm(z.GetThermalReliefSpokeWidth()), "thermal_gap": mm(z.GetThermalReliefGap())}
        zb = z.GetBoundingBox()
        entry["outline"] = [pt((zb.GetX(), zb.GetY())), pt((zb.GetRight(), zb.GetBottom()))]
        if not z.GetIsRuleArea() and z.HasFilledPolysForLayer(lid):
            fb = z.GetFilledPolysList(lid).BBox()
            entry["filled"] = [pt((fb.GetX(), fb.GetY())), pt((fb.GetRight(), fb.GetBottom()))]
        facts["zones"].append(entry)

# board-level silkscreen (footprint silk is the library's business)
for d in board.GetDrawings():
    if d.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        continue
    bb = d.GetBoundingBox()
    item = {"layer": layer_name(d.GetLayer()), "class": d.GetClass(),
            "bbox": pt((bb.GetX(), bb.GetY())) + pt((bb.GetRight(), bb.GetBottom()))}
    if d.GetClass() == "PCB_TEXT":
        item.update({"text": d.GetText(), "height": mm(d.GetTextHeight()), "thickness": mm(d.GetTextThickness()),
                     "mirrored": bool(d.IsMirrored())})
    else:
        item.update({"width": mm(d.GetWidth()), "shape": d.GetShape(), "filled": bool(d.IsSolidFill())})
    facts["silk"].append(item)

json.dump(facts, open(sys.argv[2], "w"), indent=1)
