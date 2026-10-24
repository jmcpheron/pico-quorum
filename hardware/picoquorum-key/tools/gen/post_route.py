"""Tidy a routed picoquorum-key board (run after tools/autoroute.sh, or after routing by hand).

  <KiCad python> tools/gen/post_route.py [hardware/picoquorum-key/picoquorum-key.kicad_pcb]

1. Vias whose copper ring is thinner than the board's minimum get the net class's drill (0.3 mm).
2. Tracks thinner than the board's 0.2 mm minimum (the router's neck-downs between fine-pitch
   pads) are widened to 0.2 mm. DRC afterwards shows whether each one still fits.
3. GND stitching vias go on a grid wherever both ground pours are solid around the via, outside
   the antenna band and clear of every pad (a via in a pad wicks solder away from the joint). They tie the front and back pours together and rescue pour islands.
Then the pours are refilled and the board saved. Run DRC after; tools/gen/drc_prune.py removes any
stitching via that DRC objects to.
"""
import sys

import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else "hardware/picoquorum-key/picoquorum-key.kicad_pcb"
OX, OY, W, H = 100.0, 60.0, 44.0, 53.0
MIN_TRACK, MIN_RING = 0.2, 0.13
VIA_D, VIA_DRILL = 0.6, 0.3
GRID, Y_MIN, EDGE = 3.0, 9.0, 1.5
STITCH_TAG = "stitch"            # recorded nowhere; stitching vias are plain GND vias

mm, to_mm = pcbnew.FromMM, pcbnew.ToMM
board = pcbnew.LoadBoard(PCB)
gnd = board.FindNet("GND")

fixed_vias = widened = 0
for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        ring = (to_mm(t.GetWidth(pcbnew.F_Cu)) - to_mm(t.GetDrillValue())) / 2
        if ring < MIN_RING - 1e-6:
            t.SetDrill(mm(VIA_DRILL)); fixed_vias += 1
    elif to_mm(t.GetWidth()) < MIN_TRACK - 1e-6:
        t.SetWidth(mm(MIN_TRACK)); widened += 1

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
gnd_zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"]


def solid(layer, x, y, r):
    """True if the GND fill on layer covers a circle of radius r around (x, y)."""
    pts = [(x, y)] + [(x + r * c, y + r * s) for c, s in
                      ((1, 0), (-1, 0), (0, 1), (0, -1), (.7, .7), (-.7, .7), (.7, -.7), (-.7, -.7))]
    for px, py in pts:
        p = pcbnew.VECTOR2I(mm(OX + px), mm(OY + py))
        if not any(z.IsOnLayer(layer) and z.HitTestFilledArea(layer, p) for z in gnd_zones):
            return False
    return True


# No stitching via in or beside any pad, of any net: a via in an SMD pad wicks solder out of the
# joint, and module pad 41 is left unsoldered with no vias under it (DESIGN.md). The boxes are read
# before any via is created: pcbnew objects fetched after board.Add() come back unwrapped.
keep_clear = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        bb.Inflate(mm(VIA_D / 2 + 0.25))
        keep_clear.append((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))


def near_pad(x, y):
    px, py = mm(OX + x), mm(OY + y)
    return any(l <= px <= r and t <= py <= b for l, t, r, b in keep_clear)


added = 0
y = Y_MIN
while y <= H - EDGE:
    x = EDGE
    while x <= W - EDGE:
        r = VIA_D / 2 + 0.25
        if not near_pad(x, y) and solid(pcbnew.F_Cu, x, y, r) and solid(pcbnew.B_Cu, x, y, r):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(OX + x), mm(OY + y)))
            v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(gnd)
            board.Add(v); added += 1
        x += GRID
    y += GRID

filler.Fill(board.Zones())
board.Save(PCB)
print(f"post_route: {fixed_vias} vias re-drilled, {widened} tracks widened to {MIN_TRACK} mm, "
      f"{added} GND stitching vias added; pours refilled; saved {PCB}")
