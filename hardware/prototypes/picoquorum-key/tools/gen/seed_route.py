"""Carry a routed board's tracks and vias onto the freshly generated one, moved and locked.

  <KiCad python> tools/gen/seed_route.py <routed.kicad_pcb> [dx] [dy]

Rev B is rev A with every part moved 6 mm right (gen_pcb.py) and the key port added. Rev A's
routing (reviewed, DRC clean, tested) is still right for every part it connects, so it is copied
over, moved by (dx, dy) (default 6, 0), and locked; tools/autoroute.sh then routes only what is left,
the key port's connections, around it. Nets are matched by name. Two of rev A's nets are left
behind: IO1 and IO2, its spare module pins' runs to TP9 and TP10. In rev B those pins are the key
port's KEY_CC and KEY_EN, and rev A's runs lay along the top band's lower edge on both faces, walling
in the port's parts; they are routed again. GND vias no track ends on (post_route.py's stitching)
are left behind too: post_route.py adds them again for the new board.

Rev A's routed board is in git: git show 143276a:hardware/picoquorum-key/hardware/picoquorum-key/picoquorum-key.kicad_pcb
"""
import sys

import pcbnew

PCB = "hardware/picoquorum-key/picoquorum-key.kicad_pcb"
LEFT_BEHIND = {"IO1", "IO2"}         # rev A's spare pins, the key port's KEY_CC and KEY_EN in rev B


def main():
    src_path = sys.argv[1]
    dx = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
    dy = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    src = pcbnew.LoadBoard(src_path)
    # read everything out of the source first: KiCad 10's SWIG binding hands back unwrapped
    # objects once a second board has been loaded
    tracks = [t for t in src.GetTracks()]
    ends = {}
    for t in tracks:
        if t.GetClass() != "PCB_VIA":
            for p in (t.GetStart(), t.GetEnd()):
                ends[(p.x, p.y)] = True
    items = []
    for t in tracks:
        net = t.GetNetname()
        if net in LEFT_BEHIND:
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            if net == "GND" and (p.x, p.y) not in ends:
                continue                                  # a stitching via: post_route.py redoes these
            items.append(("via", net, (p.x, p.y), None, t.GetWidth(pcbnew.F_Cu), t.GetDrillValue(), None))
        else:
            a, b = t.GetStart(), t.GetEnd()
            items.append(("track", net, (a.x, a.y), (b.x, b.y), t.GetWidth(), None, t.GetLayer()))

    board = pcbnew.LoadBoard(PCB)
    if len(board.GetTracks()):
        sys.exit("the board already has tracks: build it fresh first (tools/build_board.sh --force)")
    off = pcbnew.VECTOR2I(pcbnew.FromMM(dx), pcbnew.FromMM(dy))
    missing = set()
    n = 0
    for kind, net, a, b, width, drill, layer in items:
        ni = board.FindNet(net)
        if ni is None:
            missing.add(net)
            continue
        if kind == "via":
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(a[0], a[1]) + off)
            v.SetWidth(width); v.SetDrill(drill)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(ni); v.SetLocked(True)
            board.Add(v)
        else:
            s = pcbnew.PCB_TRACK(board)
            s.SetStart(pcbnew.VECTOR2I(a[0], a[1]) + off); s.SetEnd(pcbnew.VECTOR2I(b[0], b[1]) + off)
            s.SetWidth(width); s.SetLayer(layer)
            s.SetNet(ni); s.SetLocked(True)
            board.Add(s)
        n += 1
    if missing:
        sys.exit("nets in the routed board that this one lacks: " + ", ".join(sorted(missing)))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB)
    print(f"seed_route: {n} tracks and vias from {src_path}, moved ({dx}, {dy}) mm and locked; saved {PCB}")


if __name__ == "__main__":
    main()
