"""Remove GND copper that DRC reports and the pours make unneeded, then refill and save.

  <KiCad python> tools/gen/drc_prune.py <board.kicad_pcb> <drc.json>

Removed, and only on GND:
- free-standing vias (no track ends on them) that DRC flags: post_route.py's stitching vias;
- unlocked tracks and vias DRC flags as too near the board edge or dangling. The router can't see
  the pours, so it routes GND as tracks too; near the key port's paddle it ran some along the edge,
  where the corner pour already joins the plug's ground pads (rev B).
Anything else DRC reports is left for a person to look at. Run DRC again after: the pours must still
connect everything (tools/autoroute.sh does, twice).
"""
import json
import sys

import pcbnew

pcb, report = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(pcb)
flagged, near_edge = set(), set()
for v in json.load(open(report)).get("violations", []):
    for item in v.get("items", []):
        flagged.add(item.get("uuid"))
        if v.get("type") in ("copper_edge_clearance", "track_dangling", "via_dangling"):
            near_edge.add(item.get("uuid"))

# decide everything first, then remove: KiCad 10's SWIG binding hands back unwrapped objects once
# anything has been removed
everything = list(board.GetTracks())
tracks = [t for t in everything if t.GetClass() != "PCB_VIA"]
ends = {(t.GetStart().x, t.GetStart().y) for t in tracks} | {(t.GetEnd().x, t.GetEnd().y) for t in tracks}
stitching, strays = [], []
for t in everything:
    if t.GetNetname() != "GND" or t.IsLocked():
        continue
    uid = t.m_Uuid.AsString()
    if t.GetClass() == "PCB_VIA" and uid in flagged and (t.GetPosition().x, t.GetPosition().y) not in ends:
        stitching.append(t)
    elif uid in near_edge:
        strays.append(t)
zones = list(board.Zones())
for t in stitching + strays:
    board.Remove(t)
removed, stray = len(stitching), len(strays)
pcbnew.ZONE_FILLER(board).Fill(zones)
board.Save(pcb)
print(f"drc_prune: removed {removed} stitching vias and {stray} GND tracks or vias at the edge or dangling; refilled; saved {pcb}")
