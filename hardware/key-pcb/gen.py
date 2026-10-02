#!/usr/bin/env python3
"""PicoQuorum key PCB, rev A: the PCB is the plug. Writes both KiCad 9 projects from scratch.

    python3 hardware/key-pcb/gen.py          (needs KiCad 9: its pcbnew Python module and kicad-cli)

key-a-soic  ATECC608C in SOIC-8, bare boards, chip hand-soldered
key-b-udfn  ATECC608C in UDFN-8 (2x3 mm), fully assembled by JLCPCB

Both are the same blade: seven gold fingers on the top side at 2.54 mm, GND longest so it mates
first, DETECT shortest so it mates last, and a keying slot. See README.md.

This script is how rev A was bootstrapped: a second run gives the same design (with fresh UUIDs). Once you start
editing a board in the KiCad GUI, the KiCad files are the source of truth: stop running this, or
your edits are overwritten. All dimensions are mm. Schematic y grows downward, symbol-library y
grows upward, and the board origin is the top-left corner of the key (y grows toward the fingers).
"""
import json, os, re, subprocess, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "lib")
KISYM = "/usr/share/kicad/symbols"
KIFP = "/usr/share/kicad/footprints"
DATE = "2026-10-02"

ATECC_DS = "https://ww1.microchip.com/downloads/aemDocuments/documents/SCBU/ProductDocuments/DataSheets/ATECC608C-CryptoAuthentication-Summary-Data-Sheet-DS40002513.pdf"
USBLC6_DS = "https://www.st.com/resource/en/datasheet/usblc6-2.pdf"

# --- the two boards -----------------------------------------------------------------------------
# LCSC numbers drive the JLCPCB BOM (tools/keypcb fab). key-a is meant to be ordered bare and
# soldered by hand, but its BOM is there too in case you'd rather have JLCPCB place the parts.
# The UDFN footprint is the 3x2 one: Microchip's land pattern (C04-23355) has its two pad rows
# 2.90 mm apart and a 1.5 x 1.3 mm centre pad, which is what KiCad's 3x2 DFN draws.
BOARDS = {
    "key-a-soic": dict(
        title="PicoQuorum key, rev A: SOIC-8, hand-soldered",
        chip="ATECC608C-SSHDA", chip_fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        chip_lcsc="C28975195", chip_mpn="ATECC608C-SSHDA-B",
        cap_fp="Capacitor_SMD:C_0805_2012Metric", cap_lcsc="C49678",
        res_fp="Resistor_SMD:R_0805_2012Metric",
    ),
    "key-b-udfn": dict(
        title="PicoQuorum key, rev A: UDFN-8, assembled",
        chip="ATECC608C-MAHDA", chip_fp="Package_DFN_QFN:DFN-8-1EP_3x2mm_P0.5mm_EP1.3x1.5mm",
        chip_lcsc="C23291019", chip_mpn="ATECC608C-MAHDA-S",
        cap_fp="Capacitor_SMD:C_0402_1005Metric", cap_lcsc="C1525",
        res_fp="Resistor_SMD:R_0402_1005Metric",
    ),
}
ESD = dict(mpn="USBLC6-2SC6", fp="Package_TO_SOT_SMD:SOT-23-6", lcsc="C7519")

# --- the finger map: the one table. README.md and the console wiring follow it. -----------------
# (connector position, signal, net on the key, length class, console GPIO). Position 6 has no
# finger: it is the keying slot, and the connector's key insert goes there.
FINGERS = [
    (1, "GND", "GND", "long", "GND"),
    (2, "SDA", "/SDA", "mid", "GP4"),
    (3, "SCL", "/SCL", "mid", "GP5"),
    (4, "VCC", "VCC", "mid", "GP6 (switched key power)"),
    (5, "ID", "/ID", "mid", "GP27 / ADC1"),
    (7, "RST", None, "mid", "GP26 (Trust M only)"),
    (8, "DETECT", "GND", "short", "GP7 (pull-up)"),
]
POSITIONS = 8
KEY_POS = 6


def uid():
    return str(uuid.uuid4())


# =================================================================================================
# Symbols
# =================================================================================================

def _font(hide=False, justify=None):
    j = f" (justify {justify})" if justify else ""
    h = " (hide yes)" if hide else ""
    return f"(effects (font (size 1.27 1.27)){j}{h})"


def _pin(kind, num, name, x, y, angle, length=2.54, hide=False):
    h = " hide" if hide else ""
    return (f'(pin {kind} line (at {x} {y} {angle}) (length {length}){h} '
            f'(name "{name}" {_font()}) (number "{num}" {_font()}))')


def box_symbol(name, ref, value, fp, ds, desc, w, h, pins, lcsc="", mpn=""):
    """A plain box symbol. pins: (number, name, type, side, offset); side is L/R/T/B, offset runs
    along the side (y for L/R, x for T/B)."""
    ps = []
    for num, pname, kind, side, off in pins:
        if side == "L":
            ps.append(_pin(kind, num, pname, -w - 2.54, off, 0))
        elif side == "R":
            ps.append(_pin(kind, num, pname, w + 2.54, off, 180))
        elif side == "T":
            ps.append(_pin(kind, num, pname, off, h + 2.54, 270))
        else:
            ps.append(_pin(kind, num, pname, off, -h - 2.54, 90))
    props = [("Reference", ref, 0, h + 1.27, False), ("Value", value, 0, -h - 1.27, False),
             ("Footprint", fp, 0, 0, True), ("Datasheet", ds, 0, 0, True),
             ("Description", desc, 0, 0, True)]
    if mpn:
        props.append(("MPN", mpn, 0, 0, True))
    if lcsc:
        props.append(("LCSC", lcsc, 0, 0, True))
    pr = "\n".join(f'(property "{k}" "{v}" (at {x} {y} 0) {_font(hide)})' for k, v, x, y, hide in props)
    return f"""(symbol "{name}" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
{pr}
(symbol "{name}_0_1" (rectangle (start {-w} {h}) (end {w} {-h}) (stroke (width 0.254) (type default)) (fill (type background))))
(symbol "{name}_1_1"
{chr(10).join(ps)})
(embedded_fonts no))"""


def atecc_symbol(name, fp, udfn):
    pins = [("8", "VCC", "power_in", "T", 0), ("4", "GND", "power_in", "B", 0),
            ("5", "SDA", "bidirectional", "L", 2.54), ("6", "SCL", "input", "L", -2.54),
            ("1", "NC", "no_connect", "R", 3.81), ("2", "NC", "no_connect", "R", 1.27),
            ("3", "NC", "no_connect", "R", -1.27), ("7", "NC", "no_connect", "R", -3.81)]
    if udfn:
        pins.append(("9", "EP", "passive", "B", 2.54))
    pkg = "UDFN-8 2x3 mm" if udfn else "SOIC-8"
    return box_symbol(name, "U", name, fp, ATECC_DS,
                      f"Microchip CryptoAuthentication secure element, ECC P-256, I2C, {pkg}",
                      7.62, 7.62, pins)


def usblc6_symbol():
    pins = [("1", "IO1", "passive", "L", 2.54), ("3", "IO2", "passive", "L", -2.54),
            ("6", "IO1", "passive", "R", 2.54), ("4", "IO2", "passive", "R", -2.54),
            ("5", "VBUS", "passive", "T", 0), ("2", "GND", "passive", "B", 0)]
    return box_symbol("USBLC6-2SC6", "U", "USBLC6-2SC6", ESD["fp"], USBLC6_DS,
                      "ST 2-line ESD array with a rail clamp, SOT-23-6. Pins 1/6 and 3/4 are flow-through pairs.",
                      7.62, 10.16, pins)


def blade_symbol():
    pins = [(str(n), s, "passive", "R", 7.62 - 2.54 * i) for i, (n, s, *_) in enumerate(FINGERS)]
    return box_symbol("KeyBlade_7P", "J", "KeyBlade_7P", "picoquorum:KeyBlade_7P_P2.54mm", "",
                      "The key's fingers: card-edge plug, 8 positions at 2.54 mm (6 is the keying slot), staggered lengths",
                      2.54, 10.16, pins)


def stock_symbol(lib, name):
    """A symbol's text from the stock KiCad library, renamed lib:name for a schematic's cache."""
    s = open(os.path.join(KISYM, lib + ".kicad_sym")).read()
    i = s.index(f'\n\t(symbol "{name}"') + 2
    d = 0
    for k in range(i, len(s)):
        d += {"(": 1, ")": -1}.get(s[k], 0)
        if d == 0:
            return s[i:k + 1].replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
    raise ValueError(name)


def write_symbol_lib():
    syms = [atecc_symbol("ATECC608C-SSHDA", BOARDS["key-a-soic"]["chip_fp"], False),
            atecc_symbol("ATECC608C-MAHDA", BOARDS["key-b-udfn"]["chip_fp"], True),
            usblc6_symbol(), blade_symbol()]
    with open(os.path.join(LIB, "picoquorum.kicad_sym"), "w") as f:
        f.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        f.write("\n".join(syms))
        f.write("\n)\n")
    return {re.match(r'\(symbol "([^"]+)"', s).group(1): s for s in syms}


# =================================================================================================
# Schematic
# =================================================================================================

class Sheet:
    def __init__(self, project):
        self.project = project
        self.root = uid()
        self.items = []
        self.libs = {}
        self.npwr = 0

    def lib(self, lib_id, text):
        self.libs[lib_id] = text

    def symbol(self, lib_id, ref, value, x, y, pin_nums, fp="", fields=(), dnp=False, rot=0, in_bom=True,
               box_h=None, on_board=None):
        """box_h: half-height of a box symbol, to put its reference above it and its value below."""
        u = uid()
        hide_ref = ref.startswith("#")
        if box_h is not None:
            rat, vat, j = (x + 3.81, y - box_h - 1.27), (x + 3.81, y + box_h + 2.54), "left"
        elif ref.startswith("#"):
            # power symbols: the value goes past the end the symbol points to
            dx, dy = {0: (0, -3.81), 90: (6.35, 0), 180: (0, 3.81), 270: (6.35, 0)}[rot]
            if "GND" in lib_id and rot == 0:
                dy = 3.81
            rat, vat, j = (x, y), (x + dx, y + dy), None
        else:
            rat, vat, j = (x + 2.54, y - 1.27), (x + 2.54, y + 1.27), "left"
        props = [f'(property "Reference" "{ref}" (at {rat[0]} {rat[1]} 0) {_font(hide_ref, j)})',
                 f'(property "Value" "{value}" (at {vat[0]} {vat[1]} {rot if rot in (90, 270) else 0}) {_font(False, j)})',
                 f'(property "Footprint" "{fp}" (at {x} {y} 0) {_font(True)})']
        props += [f'(property "{k}" "{v}" (at {x} {y} 0) {_font(True)})' for k, v in fields]
        pins = " ".join(f'(pin "{n}" (uuid "{uid()}"))' for n in pin_nums)
        yn = lambda b: "yes" if b else "no"
        self.items.append(
            f'(symbol (lib_id "{lib_id}") (at {x} {y} {rot}) (unit 1) (exclude_from_sim no) '
            f'(in_bom {yn(in_bom)}) (on_board {yn(in_bom if on_board is None else on_board)}) (dnp {yn(dnp)}) (uuid "{u}")\n'
            + "\n".join(props) + f"\n{pins}\n"
            f'(instances (project "{self.project}" (path "/{self.root}" (reference "{ref}") (unit 1)))))')
        return u

    def power(self, name, x, y, rot=0):
        self.npwr += 1
        if name == "PWR_FLAG":
            ref = f"#FLG0{self.npwr:02d}"
        else:
            ref = f"#PWR0{self.npwr:02d}"
        self.symbol(f"power:{name}", ref, name, x, y, ["1"], rot=rot)

    def wire(self, x1, y1, x2, y2):
        self.items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid "{uid()}"))')

    def label(self, name, x, y, left=False):
        a, j = (180, "right bottom") if left else (0, "left bottom")
        self.items.append(f'(label "{name}" (at {x} {y} {a}) (fields_autoplaced yes) {_font(False, j)} (uuid "{uid()}"))')

    def nc(self, x, y):
        self.items.append(f'(no_connect (at {x} {y}) (uuid "{uid()}"))')

    def text(self, s, x, y):
        s = s.replace('"', '\\"').replace("\n", "\\n")
        self.items.append(f'(text "{s}" (exclude_from_sim no) (at {x} {y} 0) {_font(False, "left top")} (uuid "{uid()}"))')

    def write(self, path, title):
        cache = "\n".join(self.libs.values())
        body = "\n".join(self.items)
        with open(path, "w") as f:
            f.write(f"""(kicad_sch (version 20250114) (generator "picoquorum_gen") (generator_version "9.0")
(uuid "{self.root}")
(paper "A4")
(title_block (title "{title}") (date "{DATE}") (rev "A") (company "PicoQuorum")
  (comment 1 "The PCB is the plug: see hardware/key-pcb/README.md"))
(lib_symbols
{cache})
{body}
(sheet_instances (path "/" (page "1")))
(embedded_fonts no))
""")


def write_schematic(name, b, syms):
    sh = Sheet(name)
    udfn = name == "key-b-udfn"
    sh.lib(f"picoquorum:{b['chip']}", syms[b["chip"]].replace(f'(symbol "{b["chip"]}"', f'(symbol "picoquorum:{b["chip"]}"', 1))
    for s in ("USBLC6-2SC6", "KeyBlade_7P"):
        sh.lib(f"picoquorum:{s}", syms[s].replace(f'(symbol "{s}"', f'(symbol "picoquorum:{s}"', 1))
    for lib, s in (("Device", "C"), ("Device", "R"), ("power", "GND"), ("power", "VCC"), ("power", "PWR_FLAG")):
        sh.lib(f"{lib}:{s}", stock_symbol(lib, s))

    # J1, the fingers. Pin ends at x = jx + 5.08, y = jy - 7.62 + 2.54 * row.
    jx, jy = 63.5, 88.9
    sh.symbol("picoquorum:KeyBlade_7P", "J1", "KeyBlade_7P", jx, jy, [str(n) for n, *_ in FINGERS],
              fp="picoquorum:KeyBlade_7P_P2.54mm", in_bom=False, on_board=True, box_h=10.16,
              fields=[("Description", "Gold fingers on the board edge, not a part")])
    px = jx + 5.08
    for i, (n, sig, net, *_) in enumerate(FINGERS):
        py = jy - 7.62 + 2.54 * i
        ex = px + 7.62
        if sig == "RST":
            sh.nc(px, py)
            continue
        sh.wire(px, py, ex, py)
        if net == "GND":
            sh.power("GND", ex, py, rot=90)
        elif net == "VCC":
            sh.power("VCC", ex, py, rot=270)
        else:
            sh.label(net.strip("/"), ex, py)
    # The fingers are where power comes in, so the PWR_FLAGs (which tell ERC that) sit here.
    fx, fy = jx - 2.54, jy - 20.32
    sh.power("VCC", fx, fy)
    sh.wire(fx, fy, fx + 7.62, fy)
    sh.power("PWR_FLAG", fx + 7.62, fy)
    sh.power("GND", fx + 22.86, fy)
    sh.wire(fx + 22.86, fy, fx + 30.48, fy)
    sh.power("PWR_FLAG", fx + 30.48, fy, rot=180)
    sh.text("Fingers, top side, 2.54 mm pitch.\n"
            "1 GND is longest: mates first, breaks last.\n"
            "8 DETECT is shortest and tied to GND here:\n"
            "the console's GP7 pull-up reads low only at\n"
            "full depth, and only then does it switch\n"
            "VCC on (GP6). 6 is the keying slot.\n"
            "7 RST is for a Trust M key.\n"
            "No I2C pull-ups on the key: they are on the\n"
            "console, to switched VCC.", jx - 7.62, jy + 27.94)

    # R1: the KEY ID resistor, not fitted on rev A
    rx, ry = 93.98, 106.68
    sh.symbol("Device:R", "R1", "DNP", rx, ry, ["1", "2"], fp=b["res_fp"], dnp=True,
              fields=[("Description", "KEY ID code to GND, read by the console on GP27 (ADC1). Not fitted on rev A")])
    sh.wire(rx, ry - 3.81, rx, ry - 6.35)
    sh.label("ID", rx, ry - 6.35)
    sh.wire(rx, ry + 3.81, rx, ry + 6.35)
    sh.power("GND", rx, ry + 6.35)

    # U2: ESD on SDA, SCL and VCC, between the fingers and the chip
    ux, uy = 109.22, 88.9
    sh.symbol("picoquorum:USBLC6-2SC6", "U2", "USBLC6-2SC6", ux, uy, ["1", "2", "3", "4", "5", "6"],
              fp=ESD["fp"], box_h=10.16, fields=[("Datasheet", USBLC6_DS), ("MPN", ESD["mpn"]), ("LCSC", ESD["lcsc"]),
                      ("Description", "ESD array on SDA, SCL and VCC: the key is handled and hot-plugged")])
    for side, off, net in (("L", 2.54, "SDA"), ("L", -2.54, "SCL"), ("R", 2.54, "SDA"), ("R", -2.54, "SCL")):
        x = ux - 10.16 if side == "L" else ux + 10.16
        ex = x - 2.54 if side == "L" else x + 2.54
        sh.wire(x, uy - off, ex, uy - off)
        sh.label(net, ex, uy - off, left=(side == "L"))
    sh.wire(ux, uy - 12.7, ux, uy - 15.24)
    sh.power("VCC", ux, uy - 15.24)
    sh.wire(ux, uy + 12.7, ux, uy + 15.24)
    sh.power("GND", ux, uy + 15.24)

    # U1: the secure element
    cx, cy = 147.32, 88.9
    pins = ["1", "2", "3", "4", "5", "6", "7", "8"] + (["9"] if udfn else [])
    fields = [("Datasheet", ATECC_DS), ("MPN", b["chip_mpn"]),
              ("Description", "Secure element: the key's P-256 signing key lives here")]
    if b["chip_lcsc"]:
        fields.append(("LCSC", b["chip_lcsc"]))
    sh.symbol(f"picoquorum:{b['chip']}", "U1", b["chip"], cx, cy, pins, fp=b["chip_fp"], fields=fields, box_h=7.62)
    for off, net in ((2.54, "SDA"), (-2.54, "SCL")):
        sh.wire(cx - 10.16, cy - off, cx - 12.7, cy - off)
        sh.label(net, cx - 12.7, cy - off, left=True)
    sh.wire(cx, cy - 10.16, cx, cy - 12.7)
    sh.power("VCC", cx, cy - 12.7)
    sh.wire(cx, cy + 10.16, cx, cy + 12.7)
    sh.power("GND", cx, cy + 12.7)
    if udfn:
        sh.wire(cx + 2.54, cy + 10.16, cx + 2.54, cy + 12.7)
        sh.wire(cx + 2.54, cy + 12.7, cx, cy + 12.7)
    sh.text("I2C address 0x60 as shipped (7-bit).\nP-256 only: the Safe signs through its\npasskey (WebAuthn) signer.",
            cx - 7.62, cy + 22.86)

    # C1: decoupling, next to pin 8
    kx, ky = 177.8, 88.9
    sh.symbol("Device:C", "C1", "100n", kx, ky, ["1", "2"], fp=b["cap_fp"],
              fields=[("LCSC", b["cap_lcsc"]), ("Description", "Decoupling, as close to U1 pin 8 as it goes")])
    sh.wire(kx, ky - 3.81, kx, ky - 6.35)
    sh.power("VCC", kx, ky - 6.35)
    sh.wire(kx, ky + 3.81, kx, ky + 6.35)
    sh.power("GND", kx, ky + 6.35)

    sh.write(os.path.join(HERE, name, name + ".kicad_sch"), b["title"])


# =================================================================================================
# The blade footprint
# =================================================================================================
# Footprint origin: the leading edge of the board, on the centre line. Footprint y is negative
# into the board. A finger is plated from its start (its distance from the edge) to FINGER_END.
# Once the key is fully in, the connector's contact rests at CONTACT_DEPTH from the edge, so every
# finger must cover that line. A finger that starts closer to the edge gets touched sooner.
#
# The numbers come from EDAC's 345/395 card-edge drawing, the one 0.100"-pitch maker that
# publishes the card side: fingers 0.055" (1.40 mm) wide, the contact point 0.160" below the
# insulator face in a 0.330" slot (so about 4.3 mm from a seated card's edge), a 0.080" (2.03 mm)
# cut-out for an in-contact key, and card width = slot length - 0.012". Sullins' EBC (the
# in-stock part, Digi-Key S9641-ND family) takes the same 0.062" card; it doesn't publish its
# contact point, so the short fingers start at 2.0 mm to leave room if it sits shallower.

PITCH = 2.54
FINGER_W = 1.40
FINGER_END = 8.5          # where every finger stops, measured from the leading edge
FINGER_START = {"long": 0.5, "mid": 1.25, "short": 2.0}   # 0.75 mm of stagger between classes
CONTACT_DEPTH = 4.3       # EDAC: the contact point on a fully seated card
BLADE_W = 22.35           # 8 positions: card 0.888" +0/-0.015" (22.17-22.55 mm); JLCPCB holds +-0.2 mm
KEY_SLOT_W = 2.03         # EDAC's in-contact key cut-out, at position KEY_POS
KEY_SLOT_D = 8.9          # as deep as the finger zone


def finger_x(n):
    """Centre of connector position n (1..POSITIONS), from the key's centre line."""
    return (n - (POSITIONS + 1) / 2) * PITCH


def write_blade_footprint():
    d = os.path.join(LIB, "picoquorum.pretty")
    os.makedirs(d, exist_ok=True)
    pads = []
    for n, sig, net, cls, gpio in FINGERS:
        y0, y1 = -FINGER_END, -FINGER_START[cls]
        pads.append(f'(pad "{n}" smd rect (at {finger_x(n):.3f} {(y0 + y1) / 2:.3f}) (size {FINGER_W} {y1 - y0:.3f}) '
                    f'(layers "F.Cu" "F.Mask") (uuid "{uid()}"))')
        pads.append(f'(fp_text user "{sig}" (at {finger_x(n):.3f} {-FINGER_END - 1.0:.3f} 90) (layer "F.Fab") (uuid "{uid()}") '
                    f'(effects (font (size 0.6 0.6) (thickness 0.1)) (justify right)))')
    half = BLADE_W / 2
    fab = [f'(fp_line (start {-half} 0) (end {half} 0) (stroke (width 0.1) (type default)) (layer "F.Fab") (uuid "{uid()}"))',
           f'(fp_line (start {-half} {-CONTACT_DEPTH}) (end {half} {-CONTACT_DEPTH}) (stroke (width 0.05) (type dash)) (layer "F.Fab") (uuid "{uid()}"))',
           f'(fp_text user "contact line at full insertion" (at 0 {-CONTACT_DEPTH - 0.4}) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))',
           f'(fp_rect (start {-half - 0.25} 0.25) (end {half + 0.25} {-FINGER_END - 0.25}) (stroke (width 0.05) (type default)) (fill no) (layer "F.CrtYd") (uuid "{uid()}"))']
    with open(os.path.join(d, "KeyBlade_7P_P2.54mm.kicad_mod"), "w") as f:
        f.write(f"""(footprint "KeyBlade_7P_P2.54mm" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")
(descr "PicoQuorum key blade: 7 fingers at 2.54 mm on the top side of an 8-position 0.062in card edge, staggered so GND mates first and DETECT last; position 6 is the keying slot (cut in Edge.Cuts by the board). The board edge is the plug.")
(tags "card edge gold fingers staggered")
(property "Reference" "J1" (at 0 {-FINGER_END - 4} 0) (layer "F.SilkS") (hide yes) (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(property "Value" "KeyBlade_7P" (at 0 1.5 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(attr smd exclude_from_pos_files exclude_from_bom allow_missing_courtyard)
{chr(10).join(fab)}
{chr(10).join(pads)}
(embedded_fonts no))
""")


# =================================================================================================
# The board
# =================================================================================================
# Key frame: x from the centre line, y from the leading edge (negative into the board). The
# board's top-left corner sits at (100, 100) in KiCad's page coordinates.

KEY_L = 32.0              # leading edge to the lanyard end
CORNER_R = 3.0            # lanyard-end corners
LEAD_CHAMFER = 0.8        # leading corners, to find the slot
HOLE = (0.0, -KEY_L + 4.0, 3.0)   # lanyard hole: x, y, diameter (NPTH)
TRACK = 0.2
PWR_TRACK = 0.3
VIA = (0.6, 0.3)          # diameter, drill: JLCPCB's standard via, no extra cost
OX, OY = 100 + BLADE_W / 2, 100 + KEY_L
NO_POUR = FINGER_END + 0.6   # the rule area keeps the ground pour this far from the edge

# Placement and routing, per board. Parts: ref -> (x, y, rotation). Routes: (net, layer, width,
# points); a point is (x, y), ("pad", ref, number), or ("fin", position) for the top of a finger.
# Vias: (net, x, y). The ESD array U2 sits between SDA and SCL, turned so each line runs straight
# through it (pins 1 to 6 and 3 to 4), and the chip U1 sits above it.
G, SDA, SCL, VCC, ID, DET = (finger_x(n) for n in (1, 2, 3, 4, 5, 8))
U2X, U2Y = (SDA + SCL) / 2, -12.5
_COMMON_ROUTES = [
    ("GND", "F.Cu", PWR_TRACK, [("fin", 1), (G, -10.0)]),
    ("GND", "F.Cu", PWR_TRACK, [("fin", 8), (DET, -10.0)]),
    ("/SDA", "F.Cu", TRACK, [("fin", 2), (SDA, -9.9), ("pad", "U2", "1")]),
    ("/SCL", "F.Cu", TRACK, [("fin", 3), (SCL, -9.9), ("pad", "U2", "3")]),
    ("/ID", "F.Cu", TRACK, [("fin", 5), ("pad", "R1", "1")]),
    ("GND", "F.Cu", TRACK, [("pad", "U2", "2"), (U2X, -10.0)]),
    # flow-through: pins 1/6 and 3/4 are one line each inside the USBLC6, and the trace runs
    # under the package between them, as ST's layout does
    ("/SDA", "F.Cu", TRACK, [("pad", "U2", "1"), ("pad", "U2", "6")]),
    ("/SCL", "F.Cu", TRACK, [("pad", "U2", "3"), ("pad", "U2", "4")]),
    # VCC reaches the ESD array's rail pin, between the two lines, through the bottom layer
    ("VCC", "F.Cu", PWR_TRACK, [("pad", "U2", "5"), (U2X, -14.8)]),
    ("VCC", "B.Cu", PWR_TRACK, [(U2X, -14.8), (VCC, -14.8)]),
]
_COMMON_VIAS = [("GND", G, -10.0), ("GND", DET, -10.0), ("GND", U2X, -10.0),
                ("VCC", U2X, -14.8), ("VCC", VCC, -14.8)]

LAYOUT = {
    # UDFN turned 270: the bottom row is SDA, SCL, NC, VCC (pins 5 to 8) from left to right
    "key-b-udfn": dict(
        parts={"J1": (0, 0, 0), "U2": (U2X, U2Y, 90), "U1": (-3.5, -18.5, 270), "C1": (VCC, -18.0, 90),
               "R1": (ID, -11.5, 90)},
        routes=_COMMON_ROUTES + [
            ("VCC", "F.Cu", PWR_TRACK, [("fin", 4), (VCC, -16.3), ("pad", "C1", "1")]),
            ("VCC", "F.Cu", TRACK, [(VCC, -16.3), (-2.75, -16.3), ("pad", "U1", "8")]),
            ("/SDA", "F.Cu", TRACK, [("pad", "U2", "6"), (-6.03, -15.6), (-4.25, -16.4), ("pad", "U1", "5")]),
            ("/SCL", "F.Cu", TRACK, [("pad", "U2", "4"), (-4.13, -15.4), (-3.75, -16.0), ("pad", "U1", "6")]),
            ("GND", "F.Cu", TRACK, [(-4.25, -18.8), ("pad", "U1", "4"), (-4.25, -21.0)]),
            ("GND", "F.Cu", TRACK, [("pad", "C1", "2"), (VCC, -19.4)]),
            ("GND", "F.Cu", TRACK, [("pad", "R1", "2"), (ID, -12.9)]),
        ],
        vias=_COMMON_VIAS + [("GND", -4.25, -21.0), ("GND", VCC, -19.4), ("GND", ID, -12.9)],
    ),
    # SOIC turned 270 at x = -3.175: its bottom-row pins land at x = -5.08, -3.81 (SCL, straight
    # above the SCL finger), -2.54 and -1.27 (VCC, straight above the VCC finger)
    "key-a-soic": dict(
        parts={"J1": (0, 0, 0), "U2": (U2X, U2Y, 90), "U1": (-3.175, -19.5, 270), "C1": (1.0, -17.0, 90),
               "R1": (ID, -11.5, 90)},
        routes=_COMMON_ROUTES + [
            ("VCC", "F.Cu", PWR_TRACK, [("fin", 4), ("pad", "U1", "8")]),
            ("VCC", "F.Cu", PWR_TRACK, [(VCC, -15.6), (1.0, -15.6), ("pad", "C1", "1")]),
            ("/SDA", "F.Cu", TRACK, [("pad", "U2", "6"), (-6.03, -15.2), (-5.08, -15.8), ("pad", "U1", "5")]),
            ("/SCL", "F.Cu", TRACK, [("pad", "U2", "4"), (-4.13, -15.2), (-3.81, -15.6), ("pad", "U1", "6")]),
            ("GND", "F.Cu", PWR_TRACK, [("pad", "U1", "4"), (-6.6, -21.975)]),
            ("GND", "F.Cu", PWR_TRACK, [("pad", "C1", "2"), (1.0, -19.0)]),
            ("GND", "F.Cu", PWR_TRACK, [("pad", "R1", "2"), (ID, -13.6)]),
        ],
        vias=_COMMON_VIAS + [("GND", -6.6, -21.975), ("GND", 1.0, -19.0), ("GND", ID, -13.6)],
    ),
}


def _mm(x, y):
    import pcbnew
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def _key(v):
    import pcbnew
    return (pcbnew.ToMM(v.x) - OX, pcbnew.ToMM(v.y) - OY)


def write_board(name, b, netlist):
    import pcbnew
    path = os.path.join(HERE, name, name + ".kicad_pcb")
    if os.path.exists(path):
        os.remove(path)
    board = pcbnew.NewBoard(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
    # The drill/place origin: the leading edge's left end, so Gerbers, drill and CPL all
    # measure from the board's bottom-left corner (tools/keypcb fab uses it)
    ds.SetAuxOrigin(_mm(-BLADE_W / 2, 0))
    ds.m_TentViasFront = True
    ds.m_TentViasBack = True
    tb = board.GetTitleBlock()
    tb.SetTitle(b["title"]); tb.SetDate(DATE); tb.SetRevision("A"); tb.SetCompany("PicoQuorum")

    nets = {}
    for n in sorted({net for comp in netlist.values() for net in comp["pads"].values()}):
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    lay = LAYOUT[name]
    fps = {}
    for ref, comp in netlist.items():
        lib, fpname = comp["footprint"].split(":")
        libdir = os.path.join(LIB, "picoquorum.pretty") if lib == "picoquorum" else os.path.join(KIFP, lib + ".pretty")
        fp = pcbnew.FootprintLoad(libdir, fpname)
        fp.SetFPID(pcbnew.LIB_ID(lib, fpname))
        fp.SetReference(ref)
        fp.SetValue(comp["value"])
        fp.SetPath(pcbnew.KIID_PATH(comp["path"]))
        fp.SetSheetname("/"); fp.SetSheetfile(name + ".kicad_sch")
        for k, v in comp["fields"].items():
            fp.SetField(k, v)
            f = fp.GetFieldByName(k)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab)
        fp.SetDNP(comp["dnp"])
        board.Add(fp)
        x, y, rot = lay["parts"][ref]
        fp.SetPosition(_mm(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            net = comp["pads"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        fps[ref] = fp
    # the silkscreen reference of each part sits clear of the others; KiCad's GUI can move them
    for ref, fp in fps.items():
        fp.Reference().SetVisible(ref != "J1")
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.12))
    _place_refs(fps, {"U1": (-1, 0)} if name == "key-b-udfn" else {})

    def point(p):
        if p[0] == "pad":
            return _key(fps[p[1]].FindPadByNumber(p[2]).GetPosition())
        if p[0] == "fin":
            return (finger_x(p[1]), -FINGER_END + 0.4)
        return p

    for net, layer, width, pts in lay["routes"]:
        pts = [point(p) for p in pts]
        for a, c in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(_mm(*a)); t.SetEnd(_mm(*c))
            t.SetWidth(pcbnew.FromMM(width))
            t.SetLayer(pcbnew.F_Cu if layer == "F.Cu" else pcbnew.B_Cu)
            t.SetNet(nets[net])
            board.Add(t)
    for net, x, y in lay["vias"]:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(_mm(x, y))
        v.SetWidth(pcbnew.FromMM(VIA[0])); v.SetDrill(pcbnew.FromMM(VIA[1]))
        v.SetNet(nets[net])
        board.Add(v)

    _outline(board)
    _hole(board)
    _zones(board, nets["GND"])
    _silk(board, name)

    pcbnew.SaveBoard(path, board)
    # Fill the pours on a fresh load: filling the board as built here misses the lanyard hole.
    # (LoadBoard prints wxWidgets debug lines on stderr, so they are muted for the call.)
    err = os.dup(2)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    try:
        board = pcbnew.LoadBoard(path)
    finally:
        os.dup2(err, 2)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    _stackup(path)
    _rules(os.path.join(HERE, name, name + ".kicad_pro"))


# The stackup records how the board is to be made: 1.6 mm FR4, ENIG (gold on every pad, which is
# what makes the fingers gold), and an edge connector without a bevel. pcbnew's Python API doesn't
# reach the stackup, so it goes into the file's (setup) as text.
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
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t\t(edge_connector yes)
\t\t)
"""


def _stackup(path):
    s = open(path).read()
    assert "(stackup" not in s
    s = s.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1)
    open(path, "w").write(s)


# JLCPCB's 2-layer limits, with a little margin: https://jlcpcb.com/capabilities/pcb-capabilities
# The netclass asks for more (0.2 mm track and clearance, 0.6/0.3 mm vias), so these only catch
# a hand edit that goes below what the fab can make.
JLC_RULES = {
    "min_clearance": 0.15, "min_track_width": 0.15, "min_copper_edge_clearance": 0.3,
    "min_hole_clearance": 0.25, "min_hole_to_hole": 0.5, "min_via_diameter": 0.45,
    "min_through_hole_diameter": 0.3, "min_via_annular_width": 0.13, "min_text_height": 0.8,
    "min_text_thickness": 0.12, "min_silk_clearance": 0.0,
}


def _rules(pro):
    d = json.load(open(pro))
    d["board"]["design_settings"]["rules"].update(JLC_RULES)
    with open(pro, "w") as f:
        json.dump(d, f, indent=2, sort_keys=True)
        f.write("\n")


def _place_refs(fps, override):
    import pcbnew
    where = {"U1": (1, 0), "U2": (-1, 0), "C1": (1, 0), "R1": (1, 0)} | override
    for ref, fp in fps.items():
        if ref not in where:
            continue
        bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        dx, dy = where[ref]
        c = bb.Centre()
        if dx > 0:
            pos = pcbnew.VECTOR2I(bb.GetRight() + pcbnew.FromMM(0.9), c.y)
        elif dx < 0:
            pos = pcbnew.VECTOR2I(bb.GetLeft() - pcbnew.FromMM(0.9), c.y)
        else:
            pos = pcbnew.VECTOR2I(c.x, bb.GetTop() - pcbnew.FromMM(0.6))
        fp.Reference().SetPosition(pos)
        fp.Reference().SetTextAngleDegrees(0)


def _seg(board, a, c, layer):
    import pcbnew
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(_mm(*a)); s.SetEnd(_mm(*c))
    s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(0.1 if layer == pcbnew.Edge_Cuts else 0.15))
    board.Add(s)


def _arc(board, centre, start, degrees):
    import pcbnew
    a = pcbnew.PCB_SHAPE(board)
    a.SetShape(pcbnew.SHAPE_T_ARC)
    a.SetCenter(_mm(*centre))
    a.SetStart(_mm(*start))
    a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(degrees, pcbnew.DEGREES_T), True)
    a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(pcbnew.FromMM(0.1))
    board.Add(a)


def _outline(board):
    """The key's outline: chamfered at the leading edge, a round-ended keying slot at KEY_POS, and
    rounded corners at the lanyard end."""
    import pcbnew
    h, L, r, c = BLADE_W / 2, KEY_L, CORNER_R, LEAD_CHAMFER
    k, kw = finger_x(KEY_POS), KEY_SLOT_W / 2
    E = pcbnew.Edge_Cuts
    _seg(board, (-h + c, 0), (k - kw, 0), E)             # leading edge, left of the slot
    _seg(board, (k - kw, 0), (k - kw, -KEY_SLOT_D + kw), E)
    _arc(board, (k, -KEY_SLOT_D + kw), (k - kw, -KEY_SLOT_D + kw), 180)
    _seg(board, (k + kw, -KEY_SLOT_D + kw), (k + kw, 0), E)
    _seg(board, (k + kw, 0), (h - c, 0), E)              # leading edge, right of the slot
    _seg(board, (h - c, 0), (h, -c), E)
    _seg(board, (h, -c), (h, -L + r), E)
    _seg(board, (-h, -L + r), (-h, -c), E)
    _seg(board, (-h, -c), (-h + c, 0), E)
    _seg(board, (-h + r, -L), (h - r, -L), E)
    _arc(board, (h - r, -L + r), (h, -L + r), -90)
    _arc(board, (-h + r, -L + r), (-h, -L + r), 90)


def _hole(board):
    import pcbnew
    x, y, d = HOLE
    fp = pcbnew.FootprintLoad(os.path.join(KIFP, "MountingHole.pretty"), "MountingHole_3mm")
    fp.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_3mm"))
    fp.SetReference("H1"); fp.Reference().SetVisible(False)
    fp.SetValue("Lanyard"); fp.Value().SetVisible(False)
    fp.SetBoardOnly(True)  # not in the schematic
    board.Add(fp)
    fp.SetPosition(_mm(x, y))


def _zone_poly(z, pts):
    import pcbnew
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def _zones(board, gnd):
    """A ground pour on both layers, and a rule area that keeps the pour off the fingers."""
    import pcbnew
    h = BLADE_W / 2 + 1
    whole = [(-h, 1), (h, 1), (h, -KEY_L - 1), (-h, -KEY_L - 1)]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        _zone_poly(z, whole)
        z.SetLocalClearance(pcbnew.FromMM(0.25))
        z.SetMinThickness(pcbnew.FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetZoneName("GND " + ("top" if layer == pcbnew.F_Cu else "bottom"))
        board.Add(z)
    k = pcbnew.ZONE(board)
    k.SetIsRuleArea(True)
    k.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    k.SetDoNotAllowCopperPour(True)
    k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False); k.SetDoNotAllowPads(False)
    k.SetDoNotAllowFootprints(False)
    k.SetZoneName("Fingers: no pour")
    _zone_poly(k, [(-h, 1), (h, 1), (h, -NO_POUR), (-h, -NO_POUR)])
    board.Add(k)


def _text(board, s, x, y, layer, size=1.0, mirror=False):
    import pcbnew
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(_mm(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(0.15 if size >= 1 else 0.12))
    t.SetMirrored(mirror)
    board.Add(t)


def _silk(board, name):
    import pcbnew
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    _text(board, "PICOQUORUM", 0, -24.8, F, 1.2)
    _text(board, "PicoQuorum key", 0, -24.8, B, 1.2, mirror=True)
    _text(board, f"{name} rev A {DATE[:7]}", 0, -22.8, B, 0.8, mirror=True)
    _text(board, "fingers face up", 0, -12.2, B, 0.8, mirror=True)
    _text(board, "GND mates first, DETECT last", 0, -11.0, B, 0.8, mirror=True)


def read_netlist(name):
    """Every footprint's ref, value, footprint, symbol path, fields and pad nets, from kicad-cli."""
    sch = os.path.join(HERE, name, name + ".kicad_sch")
    out = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", "/dev/stdout", sch],
                         capture_output=True, text=True, check=True).stdout
    comps = {}
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)(.*?)\(tstamps "([^"]+)"\)\)', out, re.S):
        ref, body, ts = m.groups()
        fields = dict(re.findall(r'\(field \(name "([^"]+)"\) "([^"]*)"\)', body))
        comps[ref] = dict(value=re.search(r'\(value "([^"]*)"\)', body).group(1),
                          footprint=re.search(r'\(footprint "([^"]*)"\)', body).group(1),
                          path="/" + ts, pads={}, dnp='(property (name "dnp"))' in body,
                          fields={k: v for k, v in fields.items() if k in ("LCSC", "MPN")})
    for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]+)"\)[^\n]*\n(.*?)\)\)\n?(?=\s*\(net |\s*\)\))', out, re.S):
        net, body = m.groups()
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body):
            comps[ref]["pads"][pin] = net
    return comps


# =================================================================================================

def write_lib_tables(d):
    with open(os.path.join(d, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "picoquorum")(type "KiCad")'
                '(uri "${KIPRJMOD}/../lib/picoquorum.kicad_sym")(options "")(descr "PicoQuorum key parts"))\n)\n')
    with open(os.path.join(d, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n  (lib (name "picoquorum")(type "KiCad")'
                '(uri "${KIPRJMOD}/../lib/picoquorum.pretty")(options "")(descr "PicoQuorum key footprints"))\n)\n')


def main():
    os.makedirs(LIB, exist_ok=True)
    syms = write_symbol_lib()
    for name, b in BOARDS.items():
        d = os.path.join(HERE, name)
        os.makedirs(d, exist_ok=True)
        write_lib_tables(d)
        write_schematic(name, b, syms)
    write_blade_footprint()
    for name, b in BOARDS.items():
        write_board(name, b, read_netlist(name))


if __name__ == "__main__":
    main()
