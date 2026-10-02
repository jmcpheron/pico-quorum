#!/usr/bin/env python3
"""PicoQuorum key PCB proposals C and D: the same circuit as rev A, on an off-the-shelf connector
instead of gold fingers. Writes two KiCad 10 projects next to rev A, and never touches rev A's.

    tools/keypcb gen-cd          (runs this with KiCad's own Python, which has the pcbnew module)

key-c-usbc  a USB-C receptacle wired as plain pins, no USB chip: any USB-C cable, or a console
            dock with an upright plug. JLCPCB assembles it.
key-d-pogo  five flat ENIG pads on the bottom for spring (pogo) pins on the console, and two
            holes for 3 mm magnets that pull the key onto them. Bare boards, hand-soldered.

Both use the hand-solderable SOIC-8 ATECC608C, the USBLC6-2SC6 ESD array and a 100 nF cap, as
key-a does. The helpers come from gen.py; this file adds only what's new. As with gen.py, once
you edit one of these boards in KiCad, the KiCad files are the source of truth: don't run this
again, or your edits are overwritten. Frame: x from the centre line, y from the connector end
(negative into the board), all in mm.
"""
import os, re, sys

import gen

# macOS paths for KiCad's stock libraries (gen.py has the Linux ones)
_SS = "/Applications/KiCad/KiCad.app/Contents/SharedSupport"
if os.path.isdir(_SS):
    gen.KISYM, gen.KIFP = _SS + "/symbols", _SS + "/footprints"

HERE, LIB = gen.HERE, gen.LIB
DATE = "2026-10-02"
REVS = {"key-c-usbc": "P2", "key-d-pogo": "P1"}   # proposals, not releases

CHIP = dict(chip="ATECC608C-SSHDA", chip_fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", chip_lcsc="C28975195",
            chip_mpn="ATECC608C-SSHDA-B")
USBC = dict(mpn="HC-TYPE-C-16P-01A", fp="picoquorum:USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A_PQ", lcsc="C2894897",
            ds="https://datasheet.lcsc.com/lcsc/2211161000_HCTL-HC-TYPE-C-16P-01A_C2894897.pdf")
BOARDS = {
    "key-c-usbc": dict(title="PicoQuorum key, proposal C: USB-C receptacle", W=16.0, L=36.0, R=2.0,
                       finish="HASL(with lead-free)", cap_fp="Capacitor_SMD:C_0402_1005Metric", cap_lcsc="C1525",
                       res_fp="Resistor_SMD:R_0402_1005Metric", res_lcsc="C25905", **CHIP),
    "key-d-pogo": dict(title="PicoQuorum key, proposal D: pogo pads and magnets", W=18.0, L=32.0, R=3.0,
                       finish="ENIG", cap_fp="Capacitor_SMD:C_0805_2012Metric", cap_lcsc="C49678",
                       res_fp="Resistor_SMD:R_0805_2012Metric", res_lcsc="", **CHIP),
}

# key-d's contact pads, numbered left to right as seen from the pad side. VCC sits in the middle
# and both ends are ground, so a key put on backwards still sees GND and VCC in the right places,
# and only SDA and SCL swap: harmless. DETECT is tied to GND on the key, read by the console's GP7
# pull-up. (Seen from the top, through the board, the order reverses: SDA comes out on the left,
# on the same side as the chip's SDA pin, so the traces don't cross.)
PADS = [(1, "GND", "GND"), (2, "SCL", "/SCL"), (3, "VCC", "VCC"), (4, "SDA", "/SDA"), (5, "DETECT", "GND")]
PAD_PITCH, PAD_D = 2.54, 1.8
TPS = [("TP1", "GND"), ("TP2", "VCC"), ("TP3", "SDA"), ("TP4", "SCL")]   # key-c's test pads
PAD_Y = -3.5                      # the pad row's distance from the key's end
MAGNET_X, MAGNET_Y, MAGNET_HOLE = 6.0, -9.0, 3.2   # for 3 mm neodymium discs, glued in


# =================================================================================================
# Symbols and footprint
# =================================================================================================

def usbc_symbol():
    """The 16-pin receptacle as a key sees it. Pins that are joined on the board are stacked,
    with all but one hidden, the way KiCad's own USB-C symbols do it."""
    w, h = 7.62, 10.16
    P = gen._pin
    right = lambda num, name, off, hide=False: P("passive", num, name, w + 2.54, off, 180, hide=hide)
    pins = [right("A4", "VBUS", 7.62), right("A9", "VBUS", 7.62, True), right("B4", "VBUS", 7.62, True),
            right("B9", "VBUS", 7.62, True),
            right("A5", "CC1", 5.08), right("B5", "CC2", 2.54),
            right("A6", "D+", 0), right("B6", "D+", 0, True),
            right("A7", "D-", -2.54), right("B7", "D-", -2.54, True),
            right("A8", "SBU1", -5.08), right("B8", "SBU2", -7.62)]
    for i, num in enumerate(("A1", "A12", "B1", "B12", "SH")):
        pins.append(P("passive", num, "GND" if num != "SH" else "SHIELD", 0, -h - 2.54, 90, hide=i > 0))
    props = [("Reference", "J", 0, h + 1.27, False), ("Value", "USB_C_16P", 0, -h - 1.27, False),
             ("Footprint", USBC["fp"], 0, 0, True), ("Datasheet", USBC["ds"], 0, 0, True),
             ("Description", "USB-C receptacle, 16 pins, used as plain wires: VBUS, GND, D+, D-, CC1, CC2", 0, 0, True)]
    pr = "\n".join(f'(property "{k}" "{v}" (at {x} {y} 0) {gen._font(hide)})' for k, v, x, y, hide in props)
    return f"""(symbol "USB_C_16P" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
{pr}
(symbol "USB_C_16P_0_1" (rectangle (start {-w} {h}) (end {w} {-h}) (stroke (width 0.254) (type default)) (fill (type background))))
(symbol "USB_C_16P_1_1"
{chr(10).join(pins)})
(embedded_fonts no))"""


def pads_symbol():
    pins = [(str(n), s, "passive", "R", 5.08 - 2.54 * i) for i, (n, s, _) in enumerate(PADS)]
    return gen.box_symbol("KeyPads_5P", "J", "KeyPads_5P", "picoquorum:KeyPads_5P_P2.54mm", "",
                          "The key's contact pads for spring (pogo) pins: 5 at 2.54 mm, on the bottom, no paste",
                          2.54, 7.62, pins)


def write_symbol_lib():
    """gen.py's four symbols, unchanged, then this file's two."""
    syms = [gen.atecc_symbol("ATECC608C-SSHDA", gen.BOARDS["key-a-soic"]["chip_fp"], False),
            gen.atecc_symbol("ATECC608C-MAHDA", gen.BOARDS["key-b-udfn"]["chip_fp"], True),
            gen.usblc6_symbol(), gen.blade_symbol(), usbc_symbol(), pads_symbol()]
    with open(os.path.join(LIB, "picoquorum.kicad_sym"), "w") as f:
        f.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        f.write("\n".join(syms))
        f.write("\n)\n")
    return {re.match(r'\(symbol "([^"]+)"', s).group(1): s for s in syms}


def write_pads_footprint():
    """Drawn on the front and flipped onto the bottom by the board, so pad 1 reads left to right
    when you look at the pad side."""
    uid = gen.uid
    pads = []
    for n, sig, _ in PADS:
        x = (n - 3) * PAD_PITCH
        pads.append(f'(pad "{n}" smd circle (at {x:.2f} 0) (size {PAD_D} {PAD_D}) (layers "F.Cu" "F.Mask") (uuid "{uid()}"))')
        pads.append(f'(fp_text user "{sig}" (at {x:.2f} 1.8 90) (layer "F.Fab") (uuid "{uid()}") '
                    f'(effects (font (size 0.6 0.6) (thickness 0.1)) (justify right)))')
    half = 2 * PAD_PITCH + PAD_D / 2
    with open(os.path.join(LIB, "picoquorum.pretty", "KeyPads_5P_P2.54mm.kicad_mod"), "w") as f:
        f.write(f"""(footprint "KeyPads_5P_P2.54mm" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")
(descr "PicoQuorum key contact pads: 5 round pads at 2.54 mm for spring (pogo) pins. Place it on the bottom. ENIG, no paste: nothing is soldered here.")
(tags "pogo contact pads")
(property "Reference" "J1" (at 0 -2 0) (layer "F.SilkS") (hide yes) (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(property "Value" "KeyPads_5P" (at 0 2.5 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(attr smd exclude_from_pos_files exclude_from_bom)
(fp_rect (start {-half - 0.5} -1.5) (end {half + 0.5} 1.5) (stroke (width 0.05) (type default)) (fill no) (layer "F.CrtYd") (uuid "{uid()}"))
(fp_rect (start {-half} -1.2) (end {half} 1.2) (stroke (width 0.1) (type default)) (fill no) (layer "F.Fab") (uuid "{uid()}"))
{chr(10).join(pads)}
(embedded_fonts no))
""")


def write_receptacle_footprint():
    """KiCad's HCTL HC-TYPE-C-16P-01A footprint, with one change. Its four outer ground pads
    (A1/B12, A12/B1) reach to 0.18 mm from the part's own plastic peg holes, under JLCPCB's
    published 0.20 mm hole-to-copper limit. Here they are 0.1 mm shorter at the end nearest the pegs,
    which gives about 0.26 mm. Their back end, where the leads solder, doesn't move, and neither do
    the peg holes, so the part fits the same way."""
    src = os.path.join(gen.KIFP, "Connector_USB.pretty", "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A.kicad_mod")
    t = open(src).read()
    t = t.replace('(footprint "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A"', '(footprint "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A_PQ"', 1)
    for x in ("3.2", "-3.2"):
        a = f"(at {x} -3.745)\n\t\t(size 0.6 1.3)"
        assert t.count(a) == 2, x
        t = t.replace(a, f"(at {x} -3.795)\n\t\t(size 0.6 1.2)")
    t = t.replace('(descr "', '(descr "PicoQuorum copy: outer ground pads 0.1 mm shorter at the peg end, for JLCPCB hole clearance (gen_cd.py). ', 1)
    with open(os.path.join(LIB, "picoquorum.pretty", "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A_PQ.kicad_mod"), "w") as f:
        f.write(t)


MARK_H = 5.0     # the mark's height on the board, mm (docs/BRAND.md: below ~16 px, use the triangle alone)


def write_mark_footprint():
    """The PicoQuorum mark (docs/BRAND.md) in one colour, for silkscreen. Same geometry as
    docs/brand/mark-*.svg: five points at -90 + 72k degrees on a circle of radius r, signed dots
    r/4 (top, lower left, lower right), waiting dots r/6, the triangle joining the signed three.
    Silkscreen has no second colour, so the waiting dots are hollow rings instead of amber, and the
    filled triangle stops short of each signed dot, leaving a thin gap so the dots read as dots."""
    import math
    uid = gen.uid
    r = MARK_H / 2.309                       # top of the top dot to the bottom of the lower dots is 2.309 r
    cy = (1.25 - 1.059) * r / 2              # centre the drawing on the footprint origin
    pt = lambda k: (r * math.cos(math.radians(-90 + 72 * k)), r * math.sin(math.radians(-90 + 72 * k)) + cy)
    signed, waiting = [pt(0), pt(2), pt(3)], [pt(1), pt(4)]
    rs, rw, gap = r / 4, r / 6, 0.22
    items = []
    # the triangle, its corners cut back to a circle of radius rs + gap around each signed dot
    R = rs + gap
    poly = []
    for i, v in enumerate(signed):
        prev, nxt = signed[i - 1], signed[(i + 1) % 3]
        a_in = math.atan2(prev[1] - v[1], prev[0] - v[0])
        a_out = math.atan2(nxt[1] - v[1], nxt[0] - v[0])
        d = (a_out - a_in + math.pi) % (2 * math.pi) - math.pi      # the short way round, through the inside
        for j in range(9):
            t = a_in + d * j / 8
            poly.append((v[0] + R * math.cos(t), v[1] + R * math.sin(t)))
    pts = " ".join(f"(xy {x:.4f} {y:.4f})" for x, y in poly)
    items.append(f'(fp_poly (pts {pts}) (stroke (width 0) (type solid)) (fill yes) (layer "F.SilkS") (uuid "{uid()}"))')
    for x, y in signed:
        items.append(f'(fp_circle (center {x:.4f} {y:.4f}) (end {x + rs:.4f} {y:.4f}) (stroke (width 0) (type solid)) '
                     f'(fill yes) (layer "F.SilkS") (uuid "{uid()}"))')
    ring = 0.15                               # JLCPCB's thinnest silkscreen line
    for x, y in waiting:
        items.append(f'(fp_circle (center {x:.4f} {y:.4f}) (end {x + rw - ring / 2:.4f} {y:.4f}) '
                     f'(stroke (width {ring}) (type solid)) (fill no) (layer "F.SilkS") (uuid "{uid()}"))')
    w = 1.118 * r
    with open(os.path.join(LIB, "picoquorum.pretty", "PicoQuorum_Mark.kicad_mod"), "w") as f:
        f.write(f"""(footprint "PicoQuorum_Mark" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")
(descr "The PicoQuorum mark, {MARK_H} mm tall, in one colour for silkscreen: three signed dots solid, two waiting dots as rings. docs/BRAND.md")
(tags "logo PicoQuorum")
(property "Reference" "LOGO1" (at 0 {-MARK_H / 2 - 1:.2f} 0) (layer "F.SilkS") (hide yes) (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(property "Value" "PicoQuorum_Mark" (at 0 {MARK_H / 2 + 1:.2f} 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(attr board_only exclude_from_pos_files exclude_from_bom allow_missing_courtyard)
{chr(10).join(items)}
(embedded_fonts no))
""")
    return w


# =================================================================================================
# Schematics
# =================================================================================================

def _common(sh, b, syms):
    """U2 (ESD), U1 (the chip), C1 and the power flags: the same on every key, placed as gen.py does."""
    sh.lib(f"picoquorum:{b['chip']}", syms[b["chip"]].replace(f'(symbol "{b["chip"]}"', f'(symbol "picoquorum:{b["chip"]}"', 1))
    sh.lib("picoquorum:USBLC6-2SC6", syms["USBLC6-2SC6"].replace('(symbol "USBLC6-2SC6"', '(symbol "picoquorum:USBLC6-2SC6"', 1))
    for lib, s in (("Device", "C"), ("Device", "R"), ("power", "GND"), ("power", "VCC"), ("power", "PWR_FLAG")):
        sh.lib(f"{lib}:{s}", gen.stock_symbol(lib, s))

    fx, fy = 60.96, 68.58
    sh.power("VCC", fx, fy)
    sh.wire(fx, fy, fx + 7.62, fy)
    sh.power("PWR_FLAG", fx + 7.62, fy)
    sh.power("GND", fx + 22.86, fy)
    sh.wire(fx + 22.86, fy, fx + 30.48, fy)
    sh.power("PWR_FLAG", fx + 30.48, fy, rot=180)

    ux, uy = 109.22, 88.9
    sh.symbol("picoquorum:USBLC6-2SC6", "U2", "USBLC6-2SC6", ux, uy, ["1", "2", "3", "4", "5", "6"],
              fp=gen.ESD["fp"], box_h=10.16, fields=[("Datasheet", gen.USBLC6_DS), ("MPN", gen.ESD["mpn"]),
              ("LCSC", gen.ESD["lcsc"]), ("Description", "ESD array on SDA, SCL and VCC: the key is handled and hot-plugged")])
    for side, off, net in (("L", 2.54, "SDA"), ("L", -2.54, "SCL"), ("R", 2.54, "SDA"), ("R", -2.54, "SCL")):
        x = ux - 10.16 if side == "L" else ux + 10.16
        ex = x - 2.54 if side == "L" else x + 2.54
        sh.wire(x, uy - off, ex, uy - off)
        sh.label(net, ex, uy - off, left=(side == "L"))
    sh.wire(ux, uy - 12.7, ux, uy - 15.24)
    sh.power("VCC", ux, uy - 15.24)
    sh.wire(ux, uy + 12.7, ux, uy + 15.24)
    sh.power("GND", ux, uy + 15.24)

    cx, cy = 147.32, 88.9
    sh.symbol(f"picoquorum:{b['chip']}", "U1", b["chip"], cx, cy, [str(i) for i in range(1, 9)], fp=b["chip_fp"],
              box_h=7.62, fields=[("Datasheet", gen.ATECC_DS), ("MPN", b["chip_mpn"]), ("LCSC", b["chip_lcsc"]),
                                  ("Description", "Secure element: the key's P-256 signing key lives here")])
    for off, net in ((2.54, "SDA"), (-2.54, "SCL")):
        sh.wire(cx - 10.16, cy - off, cx - 12.7, cy - off)
        sh.label(net, cx - 12.7, cy - off, left=True)
    sh.wire(cx, cy - 10.16, cx, cy - 12.7)
    sh.power("VCC", cx, cy - 12.7)
    sh.wire(cx, cy + 10.16, cx, cy + 12.7)
    sh.power("GND", cx, cy + 12.7)
    sh.text("I2C address 0x60 as shipped (7-bit).\nP-256 only: the Safe signs through its\npasskey (WebAuthn) signer.",
            cx - 7.62, cy + 22.86)

    kx, ky = 177.8, 88.9
    sh.symbol("Device:C", "C1", "100n", kx, ky, ["1", "2"], fp=b["cap_fp"],
              fields=[("LCSC", b["cap_lcsc"]), ("Description", "Decoupling, as close to U1 pin 8 as it goes")])
    sh.wire(kx, ky - 3.81, kx, ky - 6.35)
    sh.power("VCC", kx, ky - 6.35)
    sh.wire(kx, ky + 3.81, kx, ky + 6.35)
    sh.power("GND", kx, ky + 6.35)


def _finish(sh, name, b, note):
    path = os.path.join(HERE, name, name + ".kicad_sch")
    sh.write(path, b["title"])
    s = open(path).read()
    s = s.replace('(rev "A")', f'(rev "{REVS[name]}")', 1)
    s = s.replace('(comment 1 "The PCB is the plug: see hardware/key-pcb/README.md")', f'(comment 1 "{note}")', 1)
    open(path, "w").write(s)


def write_usbc_schematic(name, b, syms):
    sh = gen.Sheet(name)
    _common(sh, b, syms)
    sh.lib("picoquorum:USB_C_16P", syms["USB_C_16P"].replace('(symbol "USB_C_16P"', '(symbol "picoquorum:USB_C_16P"', 1))
    jx, jy = 63.5, 88.9
    pins = ["A1", "A4", "A5", "A6", "A7", "A8", "A9", "A12", "B1", "B4", "B5", "B6", "B7", "B8", "B9", "B12", "SH"]
    sh.symbol("picoquorum:USB_C_16P", "J1", USBC["mpn"], jx, jy, pins, fp=USBC["fp"], box_h=10.16,
              fields=[("Datasheet", USBC["ds"]), ("MPN", USBC["mpn"]), ("LCSC", USBC["lcsc"]),
                      ("Description", "USB-C receptacle used as plain wires, no USB: see hardware/key-pcb/PROPOSALS.md")])
    px = jx + 10.16
    for off, what in ((7.62, "VCC"), (5.08, "CC1"), (2.54, "CC2"), (0, "SDA"), (-2.54, "SCL"), (-5.08, None), (-7.62, None)):
        py = jy - off
        if what is None:
            sh.nc(px, py)
            continue
        sh.wire(px, py, px + 7.62, py)
        if what == "VCC":
            sh.power("VCC", px + 7.62, py, rot=270)
        else:
            sh.label(what, px + 7.62, py)
    sh.wire(jx, jy + 12.7, jx, jy + 15.24)
    sh.power("GND", jx, jy + 15.24)

    # the CC pull-downs (Rd): how a USB-C source, here the console, sees that something is plugged in
    for ref, net, rx in (("R1", "CC1", 86.36), ("R2", "CC2", 93.98)):
        ry = 109.22
        sh.symbol("Device:R", ref, "5.1k", rx, ry, ["1", "2"], fp=b["res_fp"],
                  fields=[("LCSC", b["res_lcsc"]), ("Description", f"Rd on {net}: tells the console a key is attached (DETECT)")])
        sh.wire(rx, ry - 3.81, rx, ry - 6.35)
        sh.label(net, rx, ry - 6.35)
        sh.wire(rx, ry + 3.81, rx, ry + 6.35)
        sh.power("GND", rx, ry + 6.35)
    # C2: ST's layout bypasses the USBLC6's VBUS pin right at the part
    c2x, c2y = 124.46, 71.12
    sh.symbol("Device:C", "C2", "100n", c2x, c2y, ["1", "2"], fp=b["cap_fp"],
              fields=[("LCSC", b["cap_lcsc"]), ("Description", "Bypass at U2's VBUS pin, as ST's layout shows")])
    sh.wire(c2x, c2y - 3.81, c2x, c2y - 6.35)
    sh.power("VCC", c2x, c2y - 6.35)
    sh.wire(c2x, c2y + 3.81, c2x, c2y + 6.35)
    sh.power("GND", c2x, c2y + 6.35)
    # test pads on the back, for a probe or a scope on the bench
    sh.lib("Connector:TestPoint", gen.stock_symbol("Connector", "TestPoint"))
    for i, (ref, net) in enumerate(TPS):
        tx, ty = 147.32 + 7.62 * i, 127.0
        sh.symbol("Connector:TestPoint", ref, net, tx, ty, ["1"], fp="TestPoint:TestPoint_Pad_D1.5mm",
                  in_bom=False, on_board=True, fields=[("Description", f"Test pad on the back: {net}")])
        sh.wire(tx, ty, tx, ty + 2.54)
        if net == "GND":
            sh.power("GND", tx, ty + 2.54)
        elif net == "VCC":
            sh.power("VCC", tx, ty + 2.54, rot=180)
        else:
            sh.label(net, tx, ty + 2.54)
    sh.text("USB-C used as plain wires, no USB:\n"
            "VBUS = key VCC (console GP6, switched)\n"
            "D+ = SDA (GP4), D- = SCL (GP5)\n"
            "A6/B6 and A7/B7 are joined on the board,\n"
            "so a cable works either way up.\n"
            "CC1/CC2: 5.1k each to GND (USB-C's Rd).\n"
            "The console's GP7 pull-up on CC reads low\n"
            "when a key is attached: that is DETECT.\n"
            "SBU1/SBU2 unused.", jx - 7.62, jy + 30.48)
    _finish(sh, name, b, "USB-C as plain wires: see hardware/key-pcb/PROPOSALS.md")


def write_pogo_schematic(name, b, syms):
    sh = gen.Sheet(name)
    _common(sh, b, syms)
    sh.lib("picoquorum:KeyPads_5P", syms["KeyPads_5P"].replace('(symbol "KeyPads_5P"', '(symbol "picoquorum:KeyPads_5P"', 1))
    jx, jy = 63.5, 88.9
    sh.symbol("picoquorum:KeyPads_5P", "J1", "KeyPads_5P", jx, jy, [str(n) for n, *_ in PADS],
              fp="picoquorum:KeyPads_5P_P2.54mm", in_bom=False, on_board=True, box_h=7.62,
              fields=[("Description", "Contact pads on the bottom, not a part")])
    px = jx + 5.08
    for i, (n, sig, net) in enumerate(PADS):
        py = jy - 5.08 + 2.54 * i
        ex = px + 7.62
        sh.wire(px, py, ex, py)
        if net == "GND":
            sh.power("GND", ex, py, rot=90)
        elif net == "VCC":
            sh.power("VCC", ex, py, rot=270)
        else:
            sh.label(net.strip("/"), ex, py)
    sh.text("Pads on the bottom, for pogo pins, 2.54 mm.\n"
            "VCC in the middle, ground at both ends:\n"
            "put on backwards, only SDA and SCL swap.\n"
            "5 DETECT is tied to GND here: the console's\n"
            "GP7 pull-up reads low once the key is on.\n"
            "Two 3 mm magnets in the board pull it down\n"
            "onto the pins and line it up.", jx - 7.62, jy + 22.86)
    _finish(sh, name, b, "Pogo pads and magnets: see hardware/key-pcb/PROPOSALS.md")


# =================================================================================================
# Boards
# =================================================================================================
# Parts: ref -> (x, y, rotation, side). Routes and vias as in gen.py: a point is (x, y),
# ("pad", ref, number), and a route is (net, layer, width, points).

T, P, G = gen.TRACK, gen.PWR_TRACK, 0.4
LAYOUT = {
    "key-c-usbc": dict(parts={"J1": (0, -3.675, 0, "F"), "R1": (-2.4, -10.4, 90, "F"), "R2": (2.15, -10.0, 90, "F"),
                              "U2": (0, -12.5, 90, "F"), "C2": (0, -15.5, 90, "F"), "U1": (0, -20.675, 270, "F"),
                              "C1": (3.75, -18.2, 0, "F"), "TP1": (3.81, -18.6, 0, "B"), "TP2": (-3.81, -18.6, 0, "B"),
                              "TP3": (-1.27, -18.6, 0, "B"), "TP4": (1.27, -18.6, 0, "B")},
                       # The receptacle's middle pads run B7 A6 A7 B6: SCL SDA SCL SDA. SCL joins on the top
                       # just under the pads; SDA takes two vias and joins on the bottom, then comes up
                       # beside U2, which sits as close to the pads as the join allows (about 4 mm).
                       routes=[
                           ("/SDA", "F.Cu", T, [("pad", "J1", "A6"), (-0.25, -8.6), (-0.05, -8.8), (-0.05, -9.0)]),
                           ("/SDA", "F.Cu", T, [("pad", "J1", "B6"), (0.75, -8.2), (1.2, -8.65), (1.35, -8.8), (1.35, -8.95)]),
                           ("/SDA", "B.Cu", T, [(1.35, -8.95), (-0.05, -9.0), (-0.75, -9.7), (-0.75, -11.6), (-1.25, -12.1),
                                                (-1.25, -12.5)]),
                           ("/SDA", "F.Cu", T, [(-1.25, -12.5), (-0.95, -12.5)]),
                           ("/SCL", "F.Cu", T, [("pad", "J1", "B7"), (-0.75, -9.7), (0.6, -9.7)]),
                           ("/SCL", "F.Cu", T, [("pad", "J1", "A7"), (0.25, -8.35), (0.6, -8.7), (0.6, -9.7), (0.95, -10.05),
                                                ("pad", "U2", "3")]),
                           # flow-through: pins 1/6 and 3/4 are one line each inside the USBLC6
                           ("/SDA", "F.Cu", T, [("pad", "U2", "1"), ("pad", "U2", "6")]),
                           ("/SCL", "F.Cu", T, [("pad", "U2", "3"), ("pad", "U2", "4")]),
                           ("/CC1", "F.Cu", T, [("pad", "J1", "A5"), (-1.25, -8.3), (-2.0, -9.05), (-2.4, -9.45), ("pad", "R1", "1")]),
                           ("/CC2", "F.Cu", T, [("pad", "J1", "B5"), (1.75, -8.3), (2.15, -8.7), ("pad", "R2", "1")]),
                           # grounds: short and wide, each straight to its own via
                           ("GND", "F.Cu", G, [("pad", "R1", "2"), (-1.85, -11.5)]),
                           ("GND", "F.Cu", G, [("pad", "R2", "2"), (2.15, -11.2)]),
                           ("GND", "F.Cu", G, [("pad", "U2", "2"), (0, -10.35)]),
                           ("GND", "F.Cu", G, [("pad", "C2", "2"), (-0.85, -16.4)]),
                           # VBUS: the left pad drops straight to the bottom, which leaves the top-left free for
                           # R1; the right one is a rail to C1 and U1. They meet on the bottom, where U2 and C2 join
                           ("VCC", "F.Cu", P, [("pad", "J1", "A4"), (-2.4, -8.3), (-2.9, -8.8), (-2.9, -8.9)]),
                           ("VCC", "B.Cu", P, [(-2.9, -8.9), (-2.9, -15.3)]),
                           ("VCC", "F.Cu", P, [("pad", "J1", "A9"), (2.4, -8.2), (2.9, -8.7), (2.9, -18.2), ("pad", "C1", "1")]),
                           ("VCC", "F.Cu", P, [("pad", "C1", "1"), ("pad", "U1", "8")]),
                           ("VCC", "F.Cu", P, [("pad", "U2", "5"), ("pad", "C2", "1"), (0.85, -15.3)]),
                           ("VCC", "B.Cu", P, [(-2.9, -15.3), (2.9, -15.3)]),
                           ("/SDA", "F.Cu", T, [("pad", "U2", "6"), (-0.95, -14.3), (-1.6, -14.95), (-1.6, -16.9), (-1.905, -17.2),
                                                ("pad", "U1", "5")]),
                           ("/SCL", "F.Cu", T, [("pad", "U2", "4"), (0.95, -14.3), (1.6, -14.95), (1.6, -16.75), (-0.2, -16.75),
                                                (-0.635, -17.1), ("pad", "U1", "6")]),
                           # the test pads, on the back
                           ("VCC", "B.Cu", P, [(-2.9, -15.3), (-2.9, -17.7), ("pad", "TP2", "1")]),
                           ("/SDA", "B.Cu", T, [(-1.6, -16.9), (-1.27, -17.23), ("pad", "TP3", "1")]),
                           ("/SCL", "B.Cu", T, [(1.6, -16.0), (1.27, -16.33), ("pad", "TP4", "1")]),
                       ],
                       vias=[("/SDA", -0.05, -9.0), ("/SDA", 1.35, -8.95), ("/SDA", -1.25, -12.5), ("/SDA", -1.6, -16.9),
                             ("/SCL", 1.6, -16.0),
                             ("GND", -1.85, -11.5), ("GND", 2.15, -11.2), ("GND", 0, -10.35), ("GND", -0.85, -16.4),
                             ("VCC", -2.9, -8.9), ("VCC", 0.85, -15.3), ("VCC", 2.9, -15.3),
                             ("GND", -6.3, -6.0), ("GND", 6.3, -6.0), ("GND", -6.5, -11.0), ("GND", 6.5, -11.0),
                             ("GND", -6.5, -19.0), ("GND", 6.5, -19.0), ("GND", -6.5, -27.0), ("GND", 6.5, -27.0),
                             ("GND", -5.0, -33.3), ("GND", 5.0, -33.3)]),
    "key-d-pogo": dict(parts={"J1": (0, PAD_Y, 0, "B"), "U2": (0, -10.0, 90, "F"), "U1": (0, -17.6, 270, "F"),
                              "C1": (4.6, -15.1, 0, "F")},
                       # The pads are on the bottom: each signal runs there to a via beside U2. VCC goes on
                       # under U2 to its far-row pin and on to C1, so it never crosses SDA or SCL.
                       routes=[
                           ("/SDA", "B.Cu", T, [("pad", "J1", "4"), (-2.54, -6.66), (-1.6, -7.6)]),
                           ("/SDA", "F.Cu", T, [(-1.6, -7.6), (-0.95, -8.25), ("pad", "U2", "1")]),
                           ("/SCL", "B.Cu", T, [("pad", "J1", "2"), (2.54, -6.66), (1.6, -7.6)]),
                           ("/SCL", "F.Cu", T, [(1.6, -7.6), (0.95, -8.25), ("pad", "U2", "3")]),
                           ("VCC", "B.Cu", P, [("pad", "J1", "3"), (0, -12.2), (3.65, -13.3)]),
                           ("VCC", "F.Cu", P, [("pad", "U2", "5"), (0, -12.2)]),
                           ("VCC", "F.Cu", P, [(3.65, -13.3), ("pad", "C1", "1"), ("pad", "U1", "8")]),
                           ("/SDA", "F.Cu", T, [("pad", "U2", "1"), ("pad", "U2", "6")]),
                           ("/SCL", "F.Cu", T, [("pad", "U2", "3"), ("pad", "U2", "4")]),
                           ("GND", "B.Cu", P, [("pad", "J1", "1"), (5.08, -6.3)]),
                           ("GND", "B.Cu", P, [("pad", "J1", "5"), (-5.08, -6.3)]),
                           ("/SDA", "F.Cu", T, [("pad", "U2", "6"), (-0.95, -12.5), (-1.905, -13.455), ("pad", "U1", "5")]),
                           ("/SCL", "F.Cu", T, [("pad", "U2", "4"), (0.95, -12.9), (-0.635, -13.9), ("pad", "U1", "6")]),
                       ],
                       vias=[("/SDA", -1.6, -7.6), ("/SCL", 1.6, -7.6), ("VCC", 0, -12.2), ("VCC", 3.65, -13.3),
                             ("GND", 5.08, -6.3), ("GND", -5.08, -6.3), ("GND", -4.5, -13.0), ("GND", 4.5, -12.6),
                             ("GND", -4.5, -21.0), ("GND", 4.5, -21.0), ("GND", -5.0, -25.0), ("GND", 5.0, -25.0)]),
}


def write_board(name, b, netlist, dump=False):
    import pcbnew
    W, L = b["W"], b["L"]
    gen.OX, gen.OY = 100 + W / 2, 100 + L
    path = os.path.join(HERE, name, name + ".kicad_pcb")
    if os.path.exists(path):
        os.remove(path)
    board = pcbnew.NewBoard(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
    ds.SetAuxOrigin(gen._mm(-W / 2, 0))
    tb = board.GetTitleBlock()
    tb.SetTitle(b["title"]); tb.SetDate(DATE); tb.SetRevision(REVS[name]); tb.SetCompany("PicoQuorum")

    nets = {}
    for n in sorted({net for comp in netlist.values() for net in comp["pads"].values()}):
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    lay = LAYOUT[name]
    fps = {}
    for ref, comp in netlist.items():
        lib, fpname = comp["footprint"].split(":")
        libdir = os.path.join(LIB, "picoquorum.pretty") if lib == "picoquorum" else os.path.join(gen.KIFP, lib + ".pretty")
        fp = pcbnew.FootprintLoad(libdir, fpname)
        fp.SetFPID(pcbnew.LIB_ID(lib, fpname))
        fp.SetReference(ref)
        fp.SetValue(comp["value"])
        fp.SetPath(pcbnew.KIID_PATH(comp["path"]))
        fp.SetSheetname("/"); fp.SetSheetfile(name + ".kicad_sch")
        for k, v in comp["fields"].items():
            fp.SetField(k, v)
            f = fp.GetField(k)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab)
        fp.SetDNP(comp["dnp"])
        board.Add(fp)
        x, y, rot, side = lay["parts"][ref]
        fp.SetPosition(gen._mm(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for pad in fp.Pads():
            net = comp["pads"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        fps[ref] = fp
    for ref, fp in fps.items():
        fp.Reference().SetVisible(ref != "J1" and not ref.startswith("TP"))
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.12))
    gen._place_refs(fps, {"U2": (1, 0), "R1": (-1, 0), "R2": (1, 0), "C1": (0, 0), "C2": (1, 0)} if name == "key-c-usbc"
                    else {"U2": (1, 0), "C1": (0, 0), "U1": (-1, 0)})
    if name == "key-c-usbc":
        # the receptacle's ground pads are small and boxed in by VBUS: join them to the pour solid,
        # not through thermal spokes that can't all reach
        for pad in fps["J1"].Pads():
            if pad.GetNetname() == "GND":
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        # U2's ground pin sits between SDA and SCL, where the pour can't reach it with two spokes; it
        # has its own short, wide trace to a via, and joins the pour solid as well
        fps["U2"].FindPadByNumber("2").SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    if dump:
        for ref, fp in sorted(fps.items()):
            for pad in sorted(fp.Pads(), key=lambda p: p.GetNumber()):
                x, y = gen._key(pad.GetPosition())
                print(f"{ref:>3} {pad.GetNumber():>4} {pad.GetNetname():<8} ({x:7.3f}, {y:7.3f})"
                      f" {'B' if pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu) else 'F'}")
        return

    def point(p):
        if p[0] == "pad":
            return gen._key(fps[p[1]].FindPadByNumber(p[2]).GetPosition())
        return p

    for net, layer, width, pts in lay["routes"]:
        pts = [point(p) for p in pts]
        for a, c in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(gen._mm(*a)); t.SetEnd(gen._mm(*c))
            t.SetWidth(pcbnew.FromMM(width))
            t.SetLayer(pcbnew.F_Cu if layer == "F.Cu" else pcbnew.B_Cu)
            t.SetNet(nets[net])
            board.Add(t)
    for net, x, y in lay["vias"]:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(gen._mm(x, y))
        v.SetWidth(pcbnew.FromMM(gen.VIA[0])); v.SetDrill(pcbnew.FromMM(gen.VIA[1]))
        v.SetNet(nets[net])
        board.Add(v)

    _outline(board, W, L, b["R"])
    _hole(board, "H1", "MountingHole_3mm", 0, -L + 4.0, "Lanyard")
    if name == "key-d-pogo":
        _hole(board, "H2", "MountingHole_3.2mm_M3", -MAGNET_X, MAGNET_Y, "Magnet")
        _hole(board, "H3", "MountingHole_3.2mm_M3", MAGNET_X, MAGNET_Y, "Magnet")
    _zones(board, nets["GND"], W, L, name)
    _silk(board, name, W, L)
    _mark(board, L)

    pcbnew.SaveBoard(path, board)
    err = os.dup(2)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    try:
        board = pcbnew.LoadBoard(path)
    finally:
        os.dup2(err, 2)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    _stackup(path, b["finish"])
    gen._rules(os.path.join(HERE, name, name + ".kicad_pro"))
    dru = os.path.join(HERE, name, name + ".kicad_dru")
    if os.path.exists(dru):
        os.remove(dru)   # P1's J1 clearance exception: the project footprint makes it unnecessary


def _outline(board, W, L, r):
    import pcbnew
    E, h = pcbnew.Edge_Cuts, W / 2
    gen._seg(board, (-h + r, 0), (h - r, 0), E)
    gen._seg(board, (h, -r), (h, -L + r), E)
    gen._seg(board, (h - r, -L), (-h + r, -L), E)
    gen._seg(board, (-h, -L + r), (-h, -r), E)
    gen._arc(board, (h - r, -r), (h - r, 0), -90)
    gen._arc(board, (h - r, -L + r), (h, -L + r), -90)
    gen._arc(board, (-h + r, -L + r), (-h + r, -L), -90)
    gen._arc(board, (-h + r, -r), (-h, -r), -90)


def _hole(board, ref, fpname, x, y, value):
    import pcbnew
    fp = pcbnew.FootprintLoad(os.path.join(gen.KIFP, "MountingHole.pretty"), fpname)
    fp.SetFPID(pcbnew.LIB_ID("MountingHole", fpname))
    fp.SetReference(ref); fp.Reference().SetVisible(False)
    fp.SetValue(value); fp.Value().SetVisible(False)
    fp.SetBoardOnly(True)
    board.Add(fp)
    fp.SetPosition(gen._mm(x, y))


def _mark(board, L):
    """The mark on the back, under the lanyard hole: upright when you turn the key over (it's
    symmetric left to right, so the mirror the back side needs changes nothing)."""
    import pcbnew
    fp = pcbnew.FootprintLoad(os.path.join(LIB, "picoquorum.pretty"), "PicoQuorum_Mark")
    fp.SetFPID(pcbnew.LIB_ID("picoquorum", "PicoQuorum_Mark"))
    fp.SetReference("LOGO1"); fp.Reference().SetVisible(False)
    fp.SetBoardOnly(True)
    board.Add(fp)
    hole_edge = -L + 4.0 + 1.5               # the lanyard hole's edge nearest the parts
    fp.SetPosition(gen._mm(0, hole_edge + 0.6 + MARK_H / 2))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def _zones(board, gnd, W, L, name):
    """GND on both layers. On key-d the bottom pour stays clear of the pads, so a pogo pin that
    lands off-centre meets bare board, never ground under thin solder mask."""
    import pcbnew
    h = W / 2 + 1
    whole = [(-h, 1), (h, 1), (h, -L - 1), (-h, -L - 1)]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        gen._zone_poly(z, whole)
        z.SetLocalClearance(pcbnew.FromMM(0.25))
        z.SetMinThickness(pcbnew.FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetZoneName("GND " + ("top" if layer == pcbnew.F_Cu else "bottom"))
        board.Add(z)
    if name == "key-d-pogo":
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.B_Cu)
        k.SetLayerSet(ls)
        k.SetDoNotAllowZoneFills(True)   # KiCad 9 called it SetDoNotAllowCopperPour
        k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False); k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        k.SetZoneName("Pads: no pour")
        x = 2 * PAD_PITCH + PAD_D / 2 + 1.0
        gen._zone_poly(k, [(-x, PAD_Y + 2.0), (x, PAD_Y + 2.0), (x, PAD_Y - 2.0), (-x, PAD_Y - 2.0)])
        board.Add(k)


def _silk(board, name, W, L):
    import pcbnew
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    if name == "key-c-usbc":
        gen._text(board, "PICOQUORUM", 0, -26.8, F, 1.0)
        gen._text(board, "PicoQuorum key", 0, -23.9, B, 1.0, mirror=True)
        gen._text(board, f"key-c {REVS[name]} {DATE[:7]}", 0, -22.5, B, 0.8, mirror=True)
        gen._text(board, "I2C on USB-C", 0, -21.3, B, 0.8, mirror=True)
        for ref, net in TPS:
            x, y, _, _ = LAYOUT[name]["parts"][ref]
            gen._text(board, net, x, y - 1.5, B, 0.8, mirror=True)
    else:
        gen._text(board, "PICOQUORUM", 0, -L + 8.5, F, 1.2)
        gen._text(board, "PicoQuorum key", 0, -19.8, B, 1.2, mirror=True)
        gen._text(board, f"key-d pogo {REVS[name]} {DATE[:7]}", 0, -18.2, B, 0.8, mirror=True)
        for n, sig, _ in PADS:
            # pads are numbered as seen from the bottom, so pad n sits at x = (3 - n) * pitch from the top
            gen._text(board, "D" if sig == "DETECT" else sig[:3] if sig != "GND" else "G",
                      (3 - n) * PAD_PITCH, PAD_Y - 1.9, B, 0.8, mirror=True)


STACKUP = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "{finish}")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def _stackup(path, finish):
    s = open(path).read()
    assert "(stackup" not in s
    assert "\t(setup\n" in s, "the board file's (setup) section moved: update _stackup"
    s = s.replace("\t(setup\n", "\t(setup\n" + STACKUP.replace("{finish}", finish), 1)
    open(path, "w").write(s)


def _sexpr(text):
    """A KiCad S-expression as nested lists of strings."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t[1:-1].replace('\\"', '"') if t.startswith('"') else t)
    return stack[0][0]


def _kids(node, key):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == key]


def _val(node, key, default=None):
    k = _kids(node, key)
    return k[0][1] if k and len(k[0]) > 1 else default


def read_netlist(name):
    """gen.read_netlist, for KiCad 10's netlist layout (one item per line, which gen.py's regexes
    don't expect). Same result: ref -> value, footprint, symbol path, fields and pad nets."""
    import subprocess
    sch = os.path.join(HERE, name, name + ".kicad_sch")
    out = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", "/dev/stdout", sch],
                         capture_output=True, text=True, check=True).stdout
    root = _sexpr(out[out.index("(export"):])
    comps = {}
    for c in _kids(_kids(root, "components")[0], "comp"):
        fields = {}
        for f in _kids(_kids(c, "fields")[0], "field") if _kids(c, "fields") else []:
            nm = _val(f, "name")
            if nm in ("LCSC", "MPN", "Datasheet", "Description") and len(f) > 2:
                fields[nm] = f[2]
        props = {_val(p, "name"): _val(p, "value") for p in _kids(c, "property")}
        comps[_val(c, "ref")] = dict(value=_val(c, "value"), footprint=_val(c, "footprint"),
                                     path="/" + _val(c, "tstamps"), pads={}, dnp="dnp" in props, fields=fields)
    for n in _kids(_kids(root, "nets")[0], "net"):
        for node in _kids(n, "node"):
            comps[_val(node, "ref")]["pads"][_val(node, "pin")] = _val(n, "name")
    return comps


# =================================================================================================

def main():
    dump = "--dump" in sys.argv
    syms = write_symbol_lib()
    write_pads_footprint()
    write_mark_footprint()
    write_receptacle_footprint()
    for name, b in BOARDS.items():
        d = os.path.join(HERE, name)
        os.makedirs(d, exist_ok=True)
        gen.write_lib_tables(d)
        (write_usbc_schematic if name == "key-c-usbc" else write_pogo_schematic)(name, b, syms)
    for name, b in BOARDS.items():
        if dump:
            print(f"== {name}")
        write_board(name, b, read_netlist(name), dump=dump)


if __name__ == "__main__":
    main()
