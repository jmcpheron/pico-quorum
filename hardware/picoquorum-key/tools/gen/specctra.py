"""Specctra round trip for an autorouter (Freerouting or any DSN/SES router).

  <KiCad python> tools/gen/specctra.py export <board.kicad_pcb> <out.dsn>
  <KiCad python> tools/gen/specctra.py import <board.kicad_pcb> <in.ses>

export: removes the copper pours from a copy of the board in memory (the router should route GND
        as tracks), and writes the DSN with every copper clearance raised by ROUTER_MARGIN: Freerouting
        rounds its geometry and lands a few microns inside the exact rule, which DRC then rejects.
        The board file is not changed.
import: applies the router's tracks and vias, refills the pours, saves the board.
"""
import re
import sys

import pcbnew

ROUTER_MARGIN = 0.01             # mm added to each clearance the router is given (not to smd_smd)


def main():
    cmd, pcb, path = sys.argv[1], sys.argv[2], sys.argv[3]
    board = pcbnew.LoadBoard(pcb)
    if cmd == "export":
        for z in list(board.Zones()):
            if not z.GetIsRuleArea():
                board.Remove(z)
        ok = pcbnew.ExportSpecctraDSN(board, path)
        if ok:
            dsn = open(path).read()
            unit = 1000.0 if re.search(r"\(resolution um", dsn) else None
            if unit is None:
                sys.exit("unexpected DSN resolution in " + path)
            dsn = re.sub(r"\(clearance ([\d.]+)\)",
                         lambda m: "(clearance %g)" % (float(m.group(1)) + ROUTER_MARGIN * unit), dsn)
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
