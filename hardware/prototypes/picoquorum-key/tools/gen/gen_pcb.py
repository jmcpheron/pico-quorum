"""Build hardware/picoquorum-key/picoquorum-key.kicad_pcb from the schematic's netlist and the placement below.

  kicad-cli sch export netlist --format kicadsexpr -o <net> hardware/picoquorum-key/picoquorum-key.kicad_sch
  <KiCad python> tools/gen/gen_pcb.py <net> [--force]

Places every footprint (front unless noted), assigns nets, draws the outline, the antenna keep-out,
the ground pours and the mechanical reference drawings (glass, active area, ribbon path). It does
not route. Refuses to overwrite a board that has tracks unless --force is given, because routing
is done after this script and must not be thrown away.

Coordinates are board millimetres from the top-left corner, X right, Y down (docs/DESIGN.md).
Rev B grew the board 6 mm on the left for the key port: every rev A X is X + 6 here.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
from sexp import dumps, parse, find, find_all  # noqa: E402
from silk_art import draw_silk, pad_label  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PCB = os.path.join(ROOT, "hardware/picoquorum-key/picoquorum-key.kicad_pcb")
KICAD_FP = os.environ.get("KICAD_FOOTPRINT_DIR",
                          "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
LIBS = {"console": os.path.join(ROOT, "hardware/lib/console.pretty"),
        "jlc": os.path.join(ROOT, "hardware/lib/jlc.pretty")}

# ---- geometry (docs/DESIGN.md) -----------------------------------------------------------------
OX, OY = 100.0, 60.0                 # where the board's top-left corner sits on the KiCad page
W, H, CORNER = 50.0, 53.0, 1.5
THICKNESS = 0.8                      # the straddle plug's drawing: T = 0.80 +- 0.05
ANT_BAND = 7.0                       # Y 0..7: no pour on either face, anywhere along the top edge
ANT_X = (29.5, 51.0)                 # the antenna rule area: the module's 18 mm (X 30-48) + 0.5, to the edge
HOLE_KEEPOUT = 2.5                   # radius: an M2 pan head is 3.8-4.0 mm across, plus margin
GLASS = (15.0, 8.5, 46.0, 26.1)      # x0 y0 x1 y1; 31.0 x 17.6 landscape, ribbon exits at x1
AA = (17.0, 9.87, 41.9, 24.73)       # active area 24.9 x 14.86, offset away from the ribbon end
ROW_MM = (AA[3] - AA[1]) / 135.0
RAIL_Y = [round(AA[1] + (r + 0.5) * ROW_MM, 2) for r in (7, 67, 127)]   # 10.70, 17.30, 23.90
RIBBON_Y = (GLASS[1] + GLASS[3]) / 2                                    # ribbon centred on the short side
ZIF_X = 26.5                         # ER-TFT1.14-2: folded tail ends 21.0 +/- 0.5 in from the glass edge
# The key port's plug straddles a paddle at the top-left corner: SHOU HAN TYPE-C 24P-GTJB 040's
# "cable side PCB layout" is a 7.90 mm paddle for at least 3.5 mm from the tip (wing-b's tab). Here
# the tip is on the top edge (Y 0), the board cut away either side of it to NOTCH_D, and the
# notch's inside corners drawn at the mill's radius, so the paddle is straight for 4.0 mm.
PLUG_X = 8.0                         # a key-c (16 mm wide) on the plug lies over X 0-16
PADDLE = (PLUG_X - 3.95, PLUG_X + 3.95)                                 # X 4.05 .. 11.95
SLOT_X1 = 14.0                       # the cut right of the paddle: 2.05 mm wide, room for the plug's body (8.4)
NOTCH_D, MILL_R = 4.5, 0.5
GND_POUR = [(0, 0), (SLOT_X1, 0), (SLOT_X1, 4.6), (16.2, 4.6), (16.2, ANT_BAND + 0.5),
            (W, ANT_BAND + 0.5), (W, H), (0, H)]                       # both faces (main, below)
# ER-TFT1.14-2 ribbon, folded, seen from the front (datasheet p.6): end, narrow tail 4.5 wide,
# taper, then 9.1 wide across the fold. The fold stands up to 0.5 proud of the glass edge.
TAIL_END = GLASS[2] - 21.0
TAPER = (GLASS[2] - 21.0 + 9.8, GLASS[2] - 21.0 + 15.6)
FOLD_Y = (GLASS[1] + 5.4, GLASS[1] + 14.5)                              # Y 13.9 .. 23.0

# ref: (x, y, rotation, side)  side "F" or "B"
PLACE = {
    # module on the back, antenna end at the top edge
    "U1": (39.0, 12.75, 0, "B"),
    # rail buttons, level with screen rows 7, 67, 127
    "SW1": (10.5, RAIL_Y[0], 0, "F"), "SW2": (10.5, RAIL_Y[1], 0, "F"), "SW3": (10.5, RAIL_Y[2], 0, "F"),
    "SW6": (42.0, 39.0, 0, "F"), "SW7": (42.0, 46.0, 0, "F"),          # BOOT, RESET
    "R4": (37.0, 39.0, 90, "F"),                                          # BOOT pull-up
    # panel connector under the glass, opening toward the fold at the glass's right edge
    "J2": (ZIF_X, RIBBON_Y, 90, "F"),      # MP/insertion side faces +X, toward the fold
    "C6": (23.85, 20.2, 0, "F"), "R5": (29.5, 23.0, 0, "F"),
    # right strip beside the glass: decoupling, EN, I2C pull-ups, next to the module's right pads
    "C3": (46.85, 9.6, 90, "F"), "C5": (48.85, 9.6, 90, "F"),
    "R3": (48.85, 12.8, 90, "F"), "C4": (47.0, 12.8, 90, "F"),       # above the fold band; C4 clear of the fold (X > 46.5)
    "R6": (46.85, 24.6, 90, "F"), "R7": (48.85, 24.6, 90, "F"),   # below the fold band (FOLD_Y)
    # below the glass
    "Q1": (21.0, 30.0, 0, "F"), "R10": (17.5, 30.0, 90, "F"), "R11": (24.5, 30.0, 90, "F"),
    "Q2": (21.0, 34.0, 0, "F"), "R9": (24.5, 34.0, 90, "F"), "R14": (17.5, 34.0, 90, "F"),
    "D1": (31.5, 29.0, 0, "F"), "R8": (31.5, 31.0, 0, "F"),
    "U2": (38.0, 31.5, 0, "F"), "C7": (42.6, 29.2, 90, "F"),
    # power: LDO left, USB-C bottom centre, ESD and links above it
    "U3": (16.0, 39.5, 0, "F"),
    "C1": (11.0, 46.0, 90, "F"), "C8": (13.2, 46.0, 90, "F"), "C2": (19.267, 44.2, 0, "F"),
    "J1": (28.0, H - 3.65, 0, "F"),
    "U4": (28.0, 39.5, 0, "F"),
    "R12": (26.1, 35.5, 90, "F"), "R13": (31.0, 35.5, 90, "F"),    # R12 at X 26.1 clears R9 above it
    "R1": (22.0, 41.0, 90, "F"), "R2": (34.0, 41.0, 90, "F"),
    # mounting holes, none near the antenna; the left two stay 3 mm in from the (new) left edge
    "H1": (3.0, 29.5, 0, "F"), "H2": (47.0, 29.5, 0, "F"), "H3": (3.0, H - 3.0, 0, "F"), "H4": (47.0, H - 3.0, 0, "F"),
    # the key port (rev B): the plug on the paddle at the top-left corner. What sits on its lines (ESD,
    # series resistors, pull-ups) is in the band right of the slot, between the plug and the module
    # the lines go to, in the order they arrive; the power switch by the regulator that feeds it,
    # between H1 and H3. Two earlier layouts put all of it in the strip left of D0-D2, where the
    # lines doubled back past each other, and the router never finished.
    "J3": (PLUG_X, 0.0, 0, "F"),           # footprint origin at the tip; the plug points up, out of the top edge
    "D3": (2.2, 5.6, 0, "F"),              # VKEY's TVS, beside the plug's left VBUS pins
    "R21": (2.2, 7.4, 0, "F"),             # VKEY to SBU, 100R: a key-c P3's LED
    "R22": (2.2, 9.2, 0, "F"), "D4": (2.2, 11.0, 0, "F"),               # the port's LED, on VKEY, beside the plug
    "U6": (16.6, 4.6, 0, "F"),             # ESD on SDA, SCL
    "U7": (20.8, 4.6, 0, "F"),             # ESD on CC, SBU
    "R18": (23.6, 3.4, 90, "F"),                                          # CC 1k
    "R17": (25.4, 3.4, 90, "F"),                                          # CC's pull-up, on every board;
                                                                          # the band's last copper, X 25.9: 3.6 mm from the keep-out
    "R19": (6.4, 43.4, 0, "F"), "R20": (6.4, 45.2, 0, "F"),             # the bus's pull-ups, by U5 (VKEY) and TP13/TP14
    "C9": (4.0, 35.4, 0, "F"), "U5": (4.0, 38.0, 0, "F"), "C10": (4.0, 40.8, 0, "F"),
    "D5": (4.0, 19.5, -90, "F"), "R23": (2.2, 19.5, -90, "F"),         # in VKEY's run up the strip, cathode up; R23 drains VKEY
    "R15": (7.6, 37.0, 90, "F"),                                          # EN pull-down
}
# debug pads on the back, two rows below the module; the port's bus below them, where rev A's
# routing (carried over by tools/gen/seed_route.py) leaves room
for i in range(12):
    PLACE["TP%d" % (i + 1)] = (15.0 + (i % 6) * 5.2, 35.0 + (i // 6) * 4.0, 0, "B")
PLACE["TP13"], PLACE["TP14"] = (8.4, 43.0, 0, "B"), (15.0, 43.0, 0, "B")



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
            if name in ("LCSC", "MPN", "Description", "Fit"):
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
    if len(board.GetTracks()) and not force:
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
    # outline with rounded corners, and the key port's notch at the top-left: the board cut away
    # left of the paddle (X 0..PADDLE[0]) and in a slot right of it, both NOTCH_D deep. The inside
    # corners are drawn at the mill's radius, as the board will come; the corner below the notch,
    # at (0, NOTCH_D), is rounded at 1 mm.
    E = pcbnew.Edge_Cuts
    c, r, d = CORNER, MILL_R, NOTCH_D
    (px0, px1), s1 = PADDLE, SLOT_X1
    seg(board, E, px0, 0, px1, 0)                                         # the paddle's tip
    seg(board, E, px1, 0, px1, d - r); arc(board, E, px1 + r, d - r, px1 + r, d, 90)
    seg(board, E, px1 + r, d, s1 - r, d); arc(board, E, s1 - r, d - r, s1, d - r, 90)
    seg(board, E, s1, d - r, s1, 0)
    seg(board, E, s1, 0, W - c, 0); arc(board, E, W - c, c, W - c, 0, 90)
    seg(board, E, W, c, W, H - c); arc(board, E, W - c, H - c, W, H - c, 90)
    seg(board, E, W - c, H, c, H); arc(board, E, c, H - c, c, H, 90)
    seg(board, E, 0, H - c, 0, d + 1.0); arc(board, E, 1.0, d + 1.0, 0, d + 1.0, 90)
    seg(board, E, 1.0, d, px0 - r, d); arc(board, E, px0 - r, d - r, px0, d - r, 90)
    seg(board, E, px0, d - r, px0, 0)

    # antenna keep-out: the module's antenna end (X 30-48) plus 0.5 mm, out past the right edge,
    # both faces. The rest of the top band has no pour (below), but tracks may cross it to the plug.
    zone(board, [pcbnew.F_Cu, pcbnew.B_Cu], [(ANT_X[0], -1), (ANT_X[1], -1), (ANT_X[1], ANT_BAND), (ANT_X[0], ANT_BAND)],
         rule_area=True, name="antenna keep-out")
    # screw-head keep-out round each M2 hole: no tracks or vias under a head or washer (a screw
    # that bites through the mask lands on GND, which the pour may keep)
    for ref in ("H1", "H2", "H3", "H4"):
        hx, hy = PLACE[ref][:2]
        ring = [(hx + HOLE_KEEPOUT * math.cos(a * math.pi / 12), hy + HOLE_KEEPOUT * math.sin(a * math.pi / 12))
                for a in range(24)]
        zone(board, [pcbnew.F_Cu, pcbnew.B_Cu], ring, rule_area=True, fills=True, name=ref + " screw keep-out")
    # ground pours below the band, and in the key port's corner (X < SLOT_X1, 17 mm and more from
    # the antenna keep-out) up to the plug's tip: the plug's ground pads and shell join it there.
    # Below the slot it steps 2.2 mm into the band, to take in U6's ground pin (13 mm from the keep-out)
    gnd = netinfo["GND"]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(board, [layer], GND_POUR, gnd, name="GND")

    # mechanical references
    U1L, U2L = pcbnew.User_1, pcbnew.User_2
    rect(board, U1L, *GLASS)
    rect(board, U1L, *AA, width=0.05)
    text(board, U1L, "glass 31.0 x 17.6; active area dashed", 30.5, GLASS[1] - 0.8, 0.6)
    for yy in RAIL_Y:
        seg(board, U1L, AA[0] - 1.0, yy, AA[0] + 2.0, yy, 0.05)
    outline = [(TAIL_END, RIBBON_Y - 2.25), (TAPER[0], RIBBON_Y - 2.25), (TAPER[1], FOLD_Y[0]),
               (GLASS[2] + 0.5, FOLD_Y[0]), (GLASS[2] + 0.5, FOLD_Y[1]), (TAPER[1], FOLD_Y[1]),
               (TAPER[0], RIBBON_Y + 2.25), (TAIL_END, RIBBON_Y + 2.25)]
    for (xa, ya), (xb, yb) in zip(outline, outline[1:] + outline[:1]):
        seg(board, U2L, xa, ya, xb, yb, 0.05)
    text(board, U2L, "ribbon, folded under the glass", 36.0, FOLD_Y[1] + 0.9, 0.6)
    rect(board, U2L, 30.0, 0.0, 48.0, 25.5, 0.05)
    text(board, U2L, "module on the back", 39.0, 26.5, 0.6)

    tps = []                             # (label, x, y) of the back test pads
    for ref in sorted((r for r in PLACE if r.startswith("TP")), key=lambda r: int(r[2:])):
        x, y, _, _ = PLACE[ref]
        tps.append((pad_label(pin_net[(ref, "1")].GetNetname()), x, y))
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
    # the stackup's thickness and the title block, in the file for the same reason
    t = re.sub(r"\(general\s*\(thickness [\d.]+\)", "(general\n\t\t(thickness %g)" % THICKNESS, t, count=1)
    t = re.sub(r"\(title \"[^\"]*\"\)", '(title "picoquorum-key rev B")', t, count=1)
    t = re.sub(r"\(date \"[^\"]*\"\)", '(date "2026-10-25")', t, count=1)
    t = re.sub(r"\(rev \"[^\"]*\"\)", '(rev "B")', t, count=1)
    open(PCB, "w").write(t)
    print(f"wrote {PCB}: {len(board.GetFootprints())} footprints, {len(netinfo)} nets")


if __name__ == "__main__":
    main()
