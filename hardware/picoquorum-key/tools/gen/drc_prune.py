"""Remove GND vias that DRC reports, then refill and save.

  <KiCad python> tools/gen/drc_prune.py <board.kicad_pcb> <drc.json>

Only free-standing GND vias (no track ends on them) are removed: those are the stitching vias
post_route.py adds. Anything else DRC reports is left for a person to look at.
"""
import json
import sys

import pcbnew

pcb, report = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(pcb)
flagged = set()
for v in json.load(open(report)).get("violations", []):
    for item in v.get("items", []):
        flagged.add(item.get("uuid"))

tracks = [t for t in board.GetTracks() if t.GetClass() != "PCB_VIA"]
ends = {(t.GetStart().x, t.GetStart().y) for t in tracks} | {(t.GetEnd().x, t.GetEnd().y) for t in tracks}
removed = 0
for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
    p = v.GetPosition()
    if v.m_Uuid.AsString() in flagged and v.GetNetname() == "GND" and (p.x, p.y) not in ends:
        board.Remove(v); removed += 1
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(pcb)
print(f"drc_prune: removed {removed} stitching vias; refilled; saved {pcb}")
