"""What a mockup needs from a board, read by KiCad's own Python (pcbnew): the outline, the holes,
and each part's side, place and courtyard. Run by tools/mockup/mockup.py, not by hand:

    <KiCad's python3> facts.py board.kicad_pcb out.json

Board mm from the aux origin (the board's bottom-left corner on both S3 boards), y up, as
tools/jlc/pcb_checks.py reads them.
"""
import json
import os
import sys

import pcbnew

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jlc"))
from pcb_checks import Board, outline_poly   # noqa: E402


def box(bd, bb):
    return [bd.xy(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetBottom())), bd.xy(pcbnew.VECTOR2I(bb.GetRight(), bb.GetTop()))]


def main(pcb, out):
    bd = Board(pcb)
    b = bd.b
    f = {"thickness": pcbnew.ToMM(b.GetDesignSettings().GetBoardThickness()),
         "outline": bd.polys(outline_poly(bd)), "holes": [], "parts": []}
    for fp in b.GetFootprints():
        side = "B" if fp.GetLayer() == pcbnew.B_Cu else "F"
        crt = fp.GetCourtyard(pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd)
        for p in fp.Pads():
            d = p.GetDrillSize()
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_NPTH, pcbnew.PAD_ATTRIB_PTH) and min(d.x, d.y) >= pcbnew.FromMM(1.5):
                f["holes"].append({"ref": fp.GetReference(), "at": bd.xy(p.GetPosition()), "d": pcbnew.ToMM(min(d.x, d.y))})
        f["parts"].append({
            "ref": fp.GetReference(), "fp": fp.GetFPIDAsString().split(":")[-1], "side": side,
            "at": bd.xy(fp.GetPosition()), "rot": fp.GetOrientationDegrees(),
            "courtyard": box(bd, crt.BBox()) if crt.OutlineCount() else None, "dnp": bool(fp.IsDNP())})
    json.dump(f, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
