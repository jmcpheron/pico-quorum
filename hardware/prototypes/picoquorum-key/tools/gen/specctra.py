"""Specctra round trip for an autorouter (Freerouting or any DSN/SES router).

  <KiCad python> tools/gen/specctra.py export <board.kicad_pcb> <out.dsn>
  <KiCad python> tools/gen/specctra.py import <board.kicad_pcb> <in.ses>

export: removes the copper pours and the GND stitching vias from a copy of the board in memory (the
        router should route GND as tracks), and writes the DSN with every copper clearance raised by
        ROUTER_MARGIN and the Power class's width set to ROUTER_POWER_WIDTH: Freerouting
        rounds its geometry and lands a few microns inside the exact rule, which DRC then rejects.
        The board file is not changed.
import: applies the router's tracks and vias, refills the pours, saves the board.
"""
import re
import sys

import pcbnew

ROUTER_MARGIN = 0.01             # mm added to each clearance the router is given (not to smd_smd)
# The width the router gives new Power-class tracks (the netclass says 0.5 mm). Rev B routes only the
# key port onto rev A's locked routing, and the port's 3V3 loads are small (ESD rails, pull-ups, U5's
# input, which its 80 mA limit caps): 0.5 mm couldn't reach U7's rail pin between its neighbours.
# 0.3 mm carries about 1 A by IPC-2221 (test_geometry holds the supply tracks to 0.5 A).
ROUTER_POWER_WIDTH = 0.3


def main():
    cmd, pcb, path = sys.argv[1], sys.argv[2], sys.argv[3]
    board = pcbnew.LoadBoard(pcb)
    if cmd == "export":
        # read everything before removing anything: KiCad 10's SWIG binding hands back unwrapped
        # objects after a Remove()
        tracks, zones = list(board.GetTracks()), list(board.Zones())
        ends = {(p.x, p.y) for t in tracks if t.GetClass() != "PCB_VIA" for p in (t.GetStart(), t.GetEnd())}
        # the GND stitching vias (no track ends on them): without the pours the router would try to
        # wire each one to ground. post_route.py adds them again after a route.
        stitching = [t for t in tracks if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
                     and (t.GetPosition().x, t.GetPosition().y) not in ends]
        for item in [z for z in zones if not z.GetIsRuleArea()] + stitching:
            board.Remove(item)
        ok = pcbnew.ExportSpecctraDSN(board, path)
        if ok:
            dsn = open(path).read()
            unit = 1000.0 if re.search(r"\(resolution um", dsn) else None
            if unit is None:
                sys.exit("unexpected DSN resolution in " + path)
            dsn = re.sub(r"\(clearance ([\d.]+)\)",
                         lambda m: "(clearance %g)" % (float(m.group(1)) + ROUTER_MARGIN * unit), dsn)
            dsn, n = re.subn(r"(\(class Power [^(]*\(circuit.*?\)\s*\)\s*\(rule\s*)\(width [\d.]+\)",
                             lambda m: m.group(1) + "(width %g)" % (ROUTER_POWER_WIDTH * unit), dsn, count=1, flags=re.S)
            if n != 1:
                sys.exit("no Power class in " + path)
            open(path, "w").write(dsn)
        print("wrote" if ok else "FAILED to write", path)
    elif cmd == "import":
        ok = pcbnew.ImportSpecctraSES(board, path)
        if not ok:
            sys.exit("could not import " + path)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.Save(pcb)
        print(f"imported {path}: {len(board.GetTracks())} tracks and vias; pours refilled; saved {pcb}")
    else:
        sys.exit(__doc__)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
