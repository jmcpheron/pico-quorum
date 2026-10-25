"""Build hardware/picoquorum-key/picoquorum-key.kicad_pcb from the schematic's netlist and the placement below.

  kicad-cli sch export netlist --format kicadsexpr -o <net> hardware/picoquorum-key/picoquorum-key.kicad_sch
  <KiCad python> tools/gen/gen_pcb.py <net> [--force]

Places every footprint (front unless noted), assigns nets, draws the outline, the antenna keep-out,
the ground pours and the mechanical reference drawings (glass, active area, ribbon path). It routes
only the key port plug's escape (ESCAPE, locked). Refuses to overwrite a board that has other tracks
unless --force is given, because routing is done after this script and must not be thrown away.

Coordinates are board millimetres from the top-left corner, X right, Y down (docs/DESIGN.md).
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
from sexp import dumps, parse, find, find_all  # noqa: E402
from silk_art import draw_silk  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PCB = os.path.join(ROOT, "hardware/picoquorum-key/picoquorum-key.kicad_pcb")
KICAD_FP = os.environ.get("KICAD_FOOTPRINT_DIR",
                          "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
LIBS = {"console": os.path.join(ROOT, "hardware/lib/console.pretty"),
        "jlc": os.path.join(ROOT, "hardware/lib/jlc.pretty")}

# ---- geometry (docs/DESIGN.md) -----------------------------------------------------------------
OX, OY = 100.0, 60.0                 # where the board's top-left corner sits on the KiCad page
W, H, CORNER = 44.0, 53.0, 1.5
ANT_BAND = 7.0                       # Y 0..7: no copper on either face
HOLE_KEEPOUT = 2.5                   # radius: an M2 pan head is 3.8-4.0 mm across, plus margin
GLASS = (9.0, 8.5, 40.0, 26.1)       # x0 y0 x1 y1; 31.0 x 17.6 landscape, ribbon exits at x1
AA = (11.0, 9.87, 35.9, 24.73)       # active area 24.9 x 14.86, offset away from the ribbon end
ROW_MM = (AA[3] - AA[1]) / 135.0
RAIL_Y = [round(AA[1] + (r + 0.5) * ROW_MM, 2) for r in (7, 67, 127)]   # 10.70, 17.30, 23.90
RIBBON_Y = (GLASS[1] + GLASS[3]) / 2                                    # ribbon centred on the short side
ZIF_X = 20.5                         # ER-TFT1.14-2: folded tail ends 21.0 +/- 0.5 in from the glass edge
# ER-TFT1.14-2 ribbon, folded, seen from the front (datasheet p.6): end, narrow tail 4.5 wide,
# taper, then 9.1 wide across the fold. The fold stands up to 0.5 proud of the glass edge.
TAIL_END = GLASS[2] - 21.0
TAPER = (GLASS[2] - 21.0 + 9.8, GLASS[2] - 21.0 + 15.6)
FOLD_Y = (GLASS[1] + 5.4, GLASS[1] + 14.5)                              # Y 13.9 .. 23.0

# ref: (x, y, rotation, side)  side "F" or "B"
PLACE = {
    # module on the back, antenna end at the top edge
    "U1": (33.0, 12.75, 0, "B"),
    # rail buttons, level with screen rows 7, 67, 127
    "SW1": (4.5, RAIL_Y[0], 0, "F"), "SW2": (4.5, RAIL_Y[1], 0, "F"), "SW3": (4.5, RAIL_Y[2], 0, "F"),
    "SW6": (36.0, 39.0, 0, "F"), "SW7": (36.0, 46.0, 0, "F"),          # BOOT, RESET
    "R4": (31.0, 39.0, 90, "F"),                                          # BOOT pull-up
    # panel connector under the glass, opening toward the fold at the glass's right edge
    "J2": (ZIF_X, RIBBON_Y, 90, "F"),      # MP/insertion side faces +X, toward the fold
    "C6": (17.85, 20.2, 0, "F"), "R5": (23.5, 23.0, 0, "F"),
    # right strip beside the glass: decoupling, EN, I2C pull-ups, next to the module's right pads
    "C3": (40.85, 9.6, 90, "F"), "C5": (42.85, 9.6, 90, "F"),
    "R3": (42.85, 12.8, 90, "F"), "C4": (41.0, 12.8, 90, "F"),       # above the fold band; C4 clear of the fold (X > 40.5)
    "R6": (40.85, 24.6, 90, "F"), "R7": (42.85, 24.6, 90, "F"),   # below the fold band (FOLD_Y)
    # below the glass
    "Q1": (15.0, 30.0, 0, "F"), "R10": (11.5, 30.0, 90, "F"), "R11": (18.5, 30.0, 90, "F"),
    "Q2": (15.0, 34.0, 0, "F"), "R9": (18.5, 34.0, 90, "F"), "R14": (11.5, 34.0, 90, "F"),
    "D1": (25.5, 29.0, 0, "F"), "R8": (25.5, 31.0, 0, "F"),
    "U2": (32.0, 31.5, 0, "F"), "C7": (36.6, 29.2, 90, "F"),
    # power: LDO left, USB-C bottom centre, ESD and links above it
    "U3": (10.0, 39.5, 0, "F"),
    "C1": (5.0, 46.0, 90, "F"), "C8": (7.2, 46.0, 90, "F"), "C2": (13.267, 44.2, 0, "F"),
    "J1": (22.0, H - 3.65, 0, "F"),
    "U4": (22.0, 39.5, 0, "F"),
    "R12": (20.1, 35.5, 90, "F"), "R13": (25.0, 35.5, 90, "F"),    # R12 at X 20.1 clears R9 above it
    "R1": (16.0, 41.0, 90, "F"), "R2": (28.0, 41.0, 90, "F"),
    # the key port, on the back, all DNP (fitted by hand): the plug at the left edge, its body past
    # the edge, beside the module; its parts between it and the module
    "J3": (0.0, 20.0, 270, "B"),
    "U6": (7.8, 22.75, 0, "B"), "D2": (6.0, 16.6, 90, "B"),
    "R15": (12.5, 21.0, 0, "B"), "R16": (12.5, 22.6, 0, "B"), "R17": (12.5, 24.2, 0, "B"), "R18": (15.5, 24.2, 0, "B"),
    "C10": (10.3, 12.0, 90, "B"), "U5": (13.5, 12.0, 0, "B"), "C9": (16.7, 12.0, 90, "B"), "R19": (18.5, 12.0, 90, "B"),
    # mounting holes, none near the antenna
    "H1": (3.0, 29.5, 0, "F"), "H2": (41.0, 29.5, 0, "F"), "H3": (3.0, H - 3.0, 0, "F"), "H4": (41.0, H - 3.0, 0, "F"),
}
# The key port plug's escape, drawn here because its pads are 0.5 mm apart and the router can't
# leave them: (net, width, points) on the back, and (net, x, y) vias. Locked, so the router keeps
# them. A1 and A12 go to the shell's GND pads, B12 to a GND via, A4 and B9 (VBUS) join, SDA and SCL
# fan out into U6's near corners, and CC goes over U6 to its far corner.
ESCAPE = [
    ("GND", 0.2, [(1.8, 17.25), (0.9, 16.42)]),
    ("GND", 0.2, [(1.8, 22.75), (0.9, 23.58)]),
    ("GND", 0.2, [(1.8, 19.25), (3.4, 19.25), (3.4, 19.6)]),
    ("VKEY", 0.25, [(1.8, 18.75), (4.2, 18.75), (4.2, 20.75), (1.8, 20.75)]),
    ("KEY_CC", 0.2, [(1.8, 21.25), (4.6, 21.25), (5.3, 20.55), (8.4, 20.55), (8.94, 21.09), (8.94, 21.8)]),
    ("KEY_SDA", 0.2, [(1.8, 21.75), (4.2, 21.75), (4.7, 22.25), (5.2, 22.25), (5.65, 21.8), (6.66, 21.8)]),
    ("KEY_SCL", 0.2, [(1.8, 22.25), (3.6, 22.25), (4.6, 23.25), (5.2, 23.25), (5.65, 23.7), (6.66, 23.7)]),
]
ESCAPE_VIAS = [("GND", 3.4, 19.6)]

# debug pads on the back, two rows below the module
for i in range(12):
    PLACE["TP%d" % (i + 1)] = (9.0 + (i % 6) * 5.2, 35.0 + (i // 6) * 4.0, 0, "B")



def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def load_fp(lib_id):
    nick, name = lib_id.split(":", 1)
    path = LIBS.get(nick, os.path.join(KICAD_FP, nick + ".pretty"))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        sys.exit(f"footprint {lib_id} not found in {path}")
    fp.SetFPID(pcbnew.LIB_ID(nick, name))
    return fp


def seg(board, layer, x0, y0, x1, y1, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pt(x0, y0)); s.SetEnd(pt(x1, y1))
    s.SetLayer(layer); s.SetWidth(mm(width))
    board.Add(s)


def rect(board, layer, x0, y0, x1, y1, width=0.1):
    for a, b, c, d in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        seg(board, layer, a, b, c, d, width)


def arc(board, layer, cx, cy, sx, sy, angle_deg, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(pt(cx, cy)); s.SetStart(pt(sx, sy))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle_deg, pcbnew.DEGREES_T), True)
    s.SetLayer(layer); s.SetWidth(mm(width))
    board.Add(s)


def text(board, layer, s, x, y, size=1.0, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s); t.SetPosition(pt(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(size * 0.15))
    if mirror:
        t.SetMirrored(True)
    board.Add(t)


def zone(board, layers, pts, net=None, rule_area=False, name="", fills=False):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(mm(OX + x), mm(OY + y))
    if rule_area:
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(not fills)
        z.SetDoNotAllowZoneFills(not fills); z.SetDoNotAllowFootprints(False)
    else:
        z.SetNet(net)
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.4))
        # thermal spokes on both faces: on the front they keep small passives from tombstoning in
        # reflow, on the back they let the hand-soldered module heat up (pad 41 is set solid locally)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    board.Add(z)
    return z


def configure(fp, c):
    """Fields, flags and text, set before LoadBoard (see main)."""
    ref = str(find(c, "ref")[1])
    fp.SetReference(ref)
    fp.SetValue(str(find(c, "value")[1]))
    fields = find(c, "fields")
    if fields:
        for f in find_all(fields, "field"):
            name = str(find(f, "name")[1])
            val = str(f[2]) if len(f) > 2 else ""
            if name in ("LCSC", "MPN", "Description"):
                fp.SetField(name, val)
                fp.GetField(name).SetVisible(False)
    props = {str(find(p, "name")[1]) for p in find_all(c, "property")}
    fp.SetDNP("dnp" in props)
    if "exclude_from_bom" in props or ref.startswith(("TP", "H")):
        fp.SetExcludedFromBOM(True)
    if ref.startswith(("TP", "H")):
        fp.SetExcludedFromPosFiles(True)
    tstamp = str(find(c, "tstamps")[1])
    fp.SetPath(pcbnew.KIID_PATH("/" + tstamp))
    fp.SetSheetname("/"); fp.SetSheetfile("picoquorum-key.kicad_sch")

    # references on the fab layer (assembly drawing); the silkscreen carries only labels people need
    r = fp.Reference()
    r.SetLayer(pcbnew.F_Fab)
    r.SetPosition(fp.GetPosition())          # footprint still at the origin here: centre of the part
    r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); r.SetTextThickness(mm(0.12))
    fp.Value().SetVisible(False)


def main():
    netfile = sys.argv[1]
    force = "--force" in sys.argv
    tree = parse(open(netfile).read())
    comps = [c for c in find_all(find(tree, "components"), "comp")
             if find(c, "footprint") and str(find(c, "footprint")[1])]
    missing = [str(find(c, "ref")[1]) for c in comps if str(find(c, "ref")[1]) not in PLACE]
    if missing:
        sys.exit("no placement for: " + ", ".join(missing))
    # Load every footprint BEFORE LoadBoard: in KiCad 10.0.6, objects SWIG creates after LoadBoard
    # come back unwrapped.
    loaded, pads_of = {}, {}
    for c in comps:
        fp = load_fp(str(find(c, "footprint")[1]))
        configure(fp, c)
        loaded[str(find(c, "ref")[1])] = fp
        pads_of[str(find(c, "ref")[1])] = list(fp.Pads())     # same quirk: list the pads now

    if force:
        # Keep only the settings (layers, design rules) and load that: removing a routed board's
        # items in Python leaves KiCad 10.0.6's SWIG binding handing back unwrapped objects later.
        tree0 = parse(open(PCB).read())
        keep = {"version", "generator", "generator_version", "general", "paper", "title_block", "layers", "setup"}
        tree0[:] = [tree0[0]] + [x for x in tree0[1:] if isinstance(x, list) and x and x[0] in keep]
        open(PCB, "w").write(dumps(tree0) + "\n")
    board = pcbnew.LoadBoard(PCB)
    if any(not t.IsLocked() for t in board.GetTracks()) and not force:
        sys.exit("the board has tracks; pass --force to rebuild it from scratch (routing will be lost)")
    for item in list(board.GetDrawings()) + list(board.GetFootprints()) + list(board.Zones()) + list(board.GetTracks()):
        board.Remove(item)
    board.SetCopperLayerCount(2)

    # nets
    netinfo = {}
    for n in find_all(find(tree, "nets"), "net"):
        name = str(find(n, "name")[1])
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    pin_net = {}
    for n in find_all(find(tree, "nets"), "net"):
        name = str(find(n, "name")[1])
        for node in find_all(n, "node"):
            pin_net[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = netinfo[name]

    # footprints
    for c in comps:
        ref = str(find(c, "ref")[1])
        fp = loaded[ref]
        x, y, rot, side = PLACE[ref]
        board.Add(fp)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for pad in pads_of[ref]:
            ni = pin_net.get((ref, pad.GetNumber()))
            if ni is not None:
                pad.SetNet(ni)
    # the key port's escape (ESCAPE above), locked
    for name, width, pts in ESCAPE:
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(pt(xa, ya)); tr.SetEnd(pt(xb, yb))
            tr.SetWidth(mm(width)); tr.SetLayer(pcbnew.B_Cu); tr.SetNet(netinfo[name]); tr.SetLocked(True)
            board.Add(tr)
    for name, x, y in ESCAPE_VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(x, y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
        v.SetNet(netinfo[name]); v.SetLocked(True)
        board.Add(v)

    # outline with rounded corners
    E = pcbnew.Edge_Cuts
    c = CORNER
    seg(board, E, c, 0, W - c, 0); seg(board, E, W, c, W, H - c)
    seg(board, E, W - c, H, c, H); seg(board, E, 0, H - c, 0, c)
    arc(board, E, W - c, c, W - c, 0, 90); arc(board, E, W - c, H - c, W, H - c, 90)
    arc(board, E, c, H - c, c, H, 90); arc(board, E, c, c, 0, c, 90)

    # antenna keep-out band, both faces
    zone(board, [pcbnew.F_Cu, pcbnew.B_Cu], [(-1, -1), (W + 1, -1), (W + 1, ANT_BAND), (-1, ANT_BAND)],
         rule_area=True, name="antenna keep-out")
    # screw-head keep-out round each M2 hole: no tracks or vias under a head or washer (a screw
    # that bites through the mask lands on GND, which the pour may keep)
    for ref in ("H1", "H2", "H3", "H4"):
        hx, hy = PLACE[ref][:2]
        ring = [(hx + HOLE_KEEPOUT * math.cos(a * math.pi / 12), hy + HOLE_KEEPOUT * math.sin(a * math.pi / 12))
                for a in range(24)]
        zone(board, [pcbnew.F_Cu, pcbnew.B_Cu], ring, rule_area=True, fills=True, name=ref + " screw keep-out")
    # ground pours below the band
    gnd = netinfo["GND"]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(board, [layer], [(0, ANT_BAND + 0.5), (W, ANT_BAND + 0.5), (W, H), (0, H)], gnd, name="GND")

    # mechanical references
    U1L, U2L = pcbnew.User_1, pcbnew.User_2
    rect(board, U1L, *GLASS)
    rect(board, U1L, *AA, width=0.05)
    text(board, U1L, "glass 31.0 x 17.6; active area dashed", 24.5, GLASS[1] - 0.8, 0.6)
    for yy in RAIL_Y:
        seg(board, U1L, AA[0] - 1.0, yy, AA[0] + 2.0, yy, 0.05)
    outline = [(TAIL_END, RIBBON_Y - 2.25), (TAPER[0], RIBBON_Y - 2.25), (TAPER[1], FOLD_Y[0]),
               (GLASS[2] + 0.5, FOLD_Y[0]), (GLASS[2] + 0.5, FOLD_Y[1]), (TAPER[1], FOLD_Y[1]),
               (TAPER[0], RIBBON_Y + 2.25), (TAIL_END, RIBBON_Y + 2.25)]
    for (xa, ya), (xb, yb) in zip(outline, outline[1:] + outline[:1]):
        seg(board, U2L, xa, ya, xb, yb, 0.05)
    text(board, U2L, "ribbon, folded under the glass", 30.0, FOLD_Y[1] + 0.9, 0.6)
    rect(board, U2L, 24.0, 0.0, 42.0, 25.5, 0.05)
    text(board, U2L, "module on the back", 33.0, 26.5, 0.6)

    tps = []                             # (net name, x, y) of the back test pads, for their labels
    for i in range(12):
        x, y, _, _ = PLACE["TP%d" % (i + 1)]
        tps.append((pin_net[("TP%d" % (i + 1), "1")].GetNetname().replace("UART_", "").replace("I2C_", ""), x, y))
    draw_silk(board, tps)                # wordmark, labels, glyphs, lock and key, back title block

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.Save(PCB)
    # drill/place origin at the board's bottom-left (JLCPCB's CPL and the Gerbers share it).
    # Set in the file: GetDesignSettings() comes back unwrapped from SWIG in this KiCad build.
    import re
    t = open(PCB).read()
    origin = "%g %g" % (OX, OY + H)
    t = re.sub(r"\(aux_axis_origin [^)]*\)", "(aux_axis_origin %s)" % origin, t)
    t = re.sub(r"\(grid_origin [^)]*\)", "(grid_origin %s)" % origin, t)
    if "(aux_axis_origin" not in t:
        t = t.replace("(setup", "(setup\n\t\t(aux_axis_origin %s)\n\t\t(grid_origin %s)" % (origin, origin), 1)
    open(PCB, "w").write(t)
    print(f"wrote {PCB}: {len(board.GetFootprints())} footprints, {len(netinfo)} nets")


if __name__ == "__main__":
    main()
