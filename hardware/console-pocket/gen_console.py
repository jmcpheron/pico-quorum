#!/usr/bin/env python3
"""PicoQuorum console PCB, console-pocket: the Pico 2 W, a 1.54" ST7789 panel, seven buttons and pads
for the key, on one 51 x 85 mm board. Writes the whole KiCad 9 project as text:

    python3 hardware/console-pocket/gen_console.py          write lib/, console-pocket/, then self-check
    python3 hardware/console-pocket/gen_console.py --check  self-check console-pocket/console-pocket.kicad_pcb only

No KiCad is needed here: symbols, footprints, the schematic, the board, its routing and the
project file are all written by this script, and a geometric self-check stands in for DRC until
`tools/keypcb check console-pocket` runs on a machine with KiCad (README.md). The zones are written
unfilled: `tools/keypcb fill console-pocket` fills them with KiCad's Python before check and fab.

As with hardware/key-pcb/gen.py: once a board is edited in KiCad, the KiCad files are the source
of truth; don't run this again or the edits are lost. Frames: the board frame has its origin at
the board's bottom-left corner, x right and y up, in mm; page coordinates (KiCad's, y down) are
OX + x, OY - y. Footprints are drawn in KiCad's library frame (origin at the part's centre, y
down). Schematic y grows downward, symbol-library y upward (gen.py's conventions).
"""
import heapq, json, math, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "key-pcb")))
import gen        # noqa: E402  the text helpers of the key boards: uid, _pin, box_symbol, Sheet
import gen_cd     # noqa: E402  _sexpr, STACKUP, write_mark_footprint

NAME = "console-pocket"
L = "picoquorum-pocket"                        # the library name, in sym-lib-table and fp-lib-table
LIB = os.path.join(HERE, "lib")
OUT = os.path.join(HERE, NAME)
DATE = "2026-10-07"
TITLE = "PicoQuorum console-pocket, rev A: Pico 2 W on the back, 1.54in ST7789, 7 buttons, key pads"
NOTE = "The pocket console on one board: see hardware/console-pocket/README.md"
PICO_DS = "https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf"
SRC = "github.com/jmcpheron/pico-quorum"        # the Source Location, CERN-OHL-W 4.1

# --- the board ---------------------------------------------------------------------------------
W, H = 51.0, 85.0        # the Pico is 51 mm long: antenna flush with the left edge, USB with the right
OX, OY = 100.0, 190.0    # page coordinates of the board's bottom-left corner
CORNER = 2.0
EDGE = 0.3               # copper to edge (JLCPCB: 0.3 on a 2-layer board)
CLEAR = 0.2              # the Default netclass clearance; the router keeps a little more
TRACK, PWR_TRACK = 0.25, 0.25     # one width: 0.25 mm carries the console's 150 mA many times over
VIA, DRILL = 0.6, 0.3
PICO_AT = (25.5, 12.0)   # module centre: it lies along the bottom edge on the back, USB at +x
ANTENNA = (0.0, 5.0, 9.0, 19.0)   # x0, y0, x1, y1: the 14 x 9 mm keep-out at the module's antenna end
HOLES = [(3.5, 40.5), (47.5, 40.5), (3.5, 81.5), (47.5, 81.5)]   # 3.2 mm, clear of the module

# The 1.54" panel's FPC: 12 pins at 0.7 mm, soldered flat to pads just below the glass. No public
# drawing was found for this panel, so these are parameters: measure a panel before ordering.
PANEL = dict(pins=12, pitch=0.7, pad=(0.4, 2.5), glass=(31.52, 33.72), active=27.72,
             gap=3.8,          # pad row centre to the glass's bottom edge
             pin1_left=True)   # pin 1 nearest the board's left edge, looking at the front

# --- the Pico 2 W's pins: number -> (name, ERC pin type, net) ----------------------------------
# Physical numbering from the datasheet's Figure 4: 1-20 down the left with USB up, 21-40 up the
# right. Nets are firmware/board.py's GPIOs and BUILD1.md's key pins; None is a no-connect.
_B = "bidirectional"
PICO = {
    1: ("GP0", _B, None), 2: ("GP1", _B, None), 3: ("GND", "power_in", "GND"),
    4: ("GP2", _B, "/BTN_UP"), 5: ("GP3", _B, "/PRESS"), 6: ("GP4", _B, "/SDA"), 7: ("GP5", _B, "/SCL"),
    8: ("GND", "power_in", "GND"), 9: ("GP6", _B, "/KEY_PWR"), 10: ("GP7", _B, "/KEY_DET"),
    11: ("GP8", _B, "/LCD_DC"), 12: ("GP9", _B, "/LCD_CS"), 13: ("GND", "power_in", "GND"),
    14: ("GP10", _B, "/LCD_SCK"), 15: ("GP11", _B, "/LCD_MOSI"), 16: ("GP12", _B, "/LCD_RST"),
    17: ("GP13", _B, "/LCD_BL"), 18: ("GND", "power_in", "GND"), 19: ("GP14", _B, None), 20: ("GP15", _B, "/BTN_A"),
    21: ("GP16", _B, "/BTN_LEFT"), 22: ("GP17", _B, "/BTN_B"), 23: ("GND", "power_in", "GND"),
    24: ("GP18", _B, "/BTN_DOWN"), 25: ("GP19", _B, "/GP19_X"), 26: ("GP20", _B, "/BTN_RIGHT"),
    27: ("GP21", _B, "/BTN_Y"), 28: ("GND", "power_in", "GND"), 29: ("GP22", _B, None), 30: ("RUN", "input", None),
    31: ("GP26", _B, "/KEY_RST"), 32: ("GP27", _B, "/KEY_ID"), 33: ("AGND", "power_in", "GND"),
    34: ("GP28", _B, None), 35: ("ADC_VREF", "passive", None), 36: ("3V3", "power_out", "+3V3"),
    37: ("3V3_EN", "input", None), 38: ("GND", "power_in", "GND"), 39: ("VSYS", "power_out", "VSYS"),
    40: ("VBUS", "power_out", None),
    41: ("SWCLK", _B, None), 42: ("DBG_GND", "passive", None), 43: ("SWDIO", _B, None), 44: ("BOOTSEL", _B, None),
}

LCD_PINS = [("GND", "power_in", "GND"), ("LEDK", "passive", "/LCD_LEDK"), ("LEDA", "passive", "+3V3"),
            ("VDD", "power_in", "+3V3"), ("GND", "power_in", "GND"), ("GND", "power_in", "GND"),
            ("DC", "input", "/LCD_DC"), ("CS", "input", "/LCD_CS"), ("SCL", "input", "/LCD_SCK"),
            ("SDA", "input", "/LCD_MOSI"), ("RESET", "input", "/LCD_RST"), ("GND", "power_in", "GND")]
SWITCHES = [("SW1", "UP", "/BTN_UP"), ("SW2", "DOWN", "/BTN_DOWN"), ("SW3", "LEFT", "/BTN_LEFT"),
            ("SW4", "RIGHT", "/BTN_RIGHT"), ("SW5", "SELECT", "/BTN_A"), ("SW6", "BACK", "/BTN_B"),
            ("SW7", "REJECT", "/BTN_Y")]
J2_PINS = [("GND", "GND"), ("3V3", "+3V3"), ("SDA", "/SDA"), ("SCL", "/SCL"), ("KEY_PWR", "/KEY_PWR"),
           ("KEY_DET", "/KEY_DET"), ("KEY_RST", "/KEY_RST"), ("KEY_ID", "/KEY_ID")]
J3_PINS = [("VSYS", "VSYS"), ("GND", "GND")]
J4_PINS = [("GP19", "/GP19_X"), ("GP3", "/PRESS"), ("GND", "GND")]

# The one net table: (ref, pad) -> net, exactly as KiCad names them from the schematic
NETS = {}
for n, (pname, _t, net) in PICO.items():
    NETS["U1", str(n)] = net or f"unconnected-(U1-{pname}-Pad{n})"
for i, (_n, _t, net) in enumerate(LCD_PINS, 1):
    NETS["LCD1", str(i)] = net
for ref, _label, net in SWITCHES:
    NETS[ref, "1"], NETS[ref, "2"] = net, "GND"
NETS.update({("R1", "1"): "/LCD_LEDK", ("R1", "2"): "/BL_C", ("Q1", "1"): "/BL_B", ("Q1", "2"): "GND",
             ("Q1", "3"): "/BL_C", ("R2", "1"): "/LCD_BL", ("R2", "2"): "/BL_B", ("R3", "1"): "/BL_B",
             ("R3", "2"): "GND", ("C1", "1"): "+3V3", ("C1", "2"): "GND",
             ("R4", "1"): "/SDA", ("R4", "2"): "/KEY_PWR", ("R5", "1"): "/SCL", ("R5", "2"): "/KEY_PWR"})
for j, pins in (("J2", J2_PINS), ("J3", J3_PINS), ("J4", J4_PINS)):
    for i, (_n, net) in enumerate(pins, 1):
        NETS[j, str(i)] = net

# --- parts: ref -> footprint, value, fields, board position (board frame), rotation, side --------
# LCSC numbers: JLCPCB basic parts except the switch (extended). Check stock when uploading.
SW_LCSC, SW_MPN = "C720496", "TS-1097A-05026"
PARTS = {
    "U1": dict(fp="Pico2W_SMD", value="Pico 2 W", at=PICO_AT, rot=-90, side="B",
               fields=[("Datasheet", PICO_DS), ("MPN", "SC1633"),
                       ("Description", "Raspberry Pi Pico 2 W soldered as a module, on the back; JLCPCB C42394205, not in the BOM: hand-soldered")]),
    "LCD1": dict(fp="LCD_1.54in_240x240_FPC12_P0.7mm", value="1.54in ST7789 240x240", at=(25.5, 44.5), rot=0,
                 fields=[("Description", "Bare IPS panel, 12-pin 0.7 mm FPC soldered to the pads; glass taped above them")]),
    "C1": dict(fp="C_0603", value="100n", at=(19.0, 38.5), rot=0, fields=[("LCSC", "C14663"), ("Description", "Panel VDD decoupling")]),
    "R1": dict(fp="R_0603", value="10R", at=(32.0, 38.1), rot=0, ref_at=(-3.0, 0), fields=[("LCSC", "C22859"), ("Description", "Backlight LEDK series; pad 2 runs straight into Q1's collector")]),
    "Q1": dict(fp="SOT-23", value="S8050", at=(35.5, 37.0), rot=0, ref_at=(0, -2.6), fields=[("LCSC", "C2150"), ("MPN", "S8050 J3Y"),
               ("Description", "NPN low-side backlight switch, as the Waveshare Pico-LCD-1.3 does it")]),
    "R2": dict(fp="R_0603", value="1k", at=(32.0, 35.9), rot=0, ref_at=(-3.0, 0), fields=[("LCSC", "C21190"), ("Description", "GP13 to Q1 base; pad 2 runs straight into the base")]),
    "R3": dict(fp="R_0603", value="10k", at=(33.5, 33.5), rot=0, ref_at=(-3.0, 0), fields=[("LCSC", "C25804"), ("Description", "Base pulldown: backlight off while the Pico boots")]),
    "R4": dict(fp="R_0603", value="2.2k", at=(44.5, 50.0), rot=90, dnp=True, fields=[("LCSC", "C4190"), ("Description", "SDA pull-up to key power, not fitted: the key is wired to the pads first")]),
    "R5": dict(fp="R_0603", value="2.2k", at=(44.5, 54.0), rot=90, dnp=True, fields=[("LCSC", "C4190"), ("Description", "SCL pull-up to key power, not fitted")]),
    "J2": dict(fp="Pads_1x8_P2.54mm", value="KEY", at=(48.0, 54.89), rot=0, in_bom=False,
               fields=[("Description", "The key's wiring pads: GND, 3V3, SDA, SCL, KEY_PWR (GP6), KEY_DET (GP7), KEY_RST (GP26), KEY_ID (GP27)")]),
    "J3": dict(fp="Pads_1x2_P2.54mm", value="BATT", at=(3.0, 51.27), rot=0, in_bom=False,
               fields=[("Description", "VSYS and GND for a battery later (hardware/wiring/SOLDERING.md)")]),
    "J4": dict(fp="Pads_1x3_P2.54mm", value="XTRA", at=(3.0, 60.0), rot=0, in_bom=False,
               fields=[("Description", "GP19 (X), GP3 (joystick press) and GND: solder pads only")]),
}
# The D-pad and the Select/Back/Reject column, both at an 8.5 mm pitch. Left, Right and Back sit
# at y 22.5: their pads clear the antenna keep-out below (y 19) and leave room above (y 26 to 27)
# for the vias of the Pico's top pad row, which leaves the module through exit lanes there. Reject
# sits 3 mm further out than Back, so the track down to it passes between Back's pads.
_SW_AT = {"SW1": (14.0, 31.0), "SW2": (14.0, 14.0), "SW3": (5.5, 22.5), "SW4": (22.5, 22.5),
          "SW5": (42.0, 31.0), "SW6": (42.0, 22.5), "SW7": (45.0, 14.0)}
for ref, label, _net in SWITCHES:
    PARTS[ref] = dict(fp="SW_SMD_6x6x5_TS1097A", value=label, at=_SW_AT[ref], rot=0,
                      fields=[("LCSC", SW_LCSC), ("MPN", SW_MPN), ("Description", f"{label}: 6x6x5 mm tact switch, GPIO on the top-left pad, GND on the bottom-right")])
for p in PARTS.values():
    p.setdefault("side", "F"); p.setdefault("dnp", False); p.setdefault("in_bom", True)
BOARD_ONLY = [("H1", "MountingHole_3.2mm", HOLES[0]), ("H2", "MountingHole_3.2mm", HOLES[1]),
              ("H3", "MountingHole_3.2mm", HOLES[2]), ("H4", "MountingHole_3.2mm", HOLES[3])]

uid = gen.uid


def page(x, y):
    return OX + x, OY - y


def f(v):
    """A number for a KiCad file: no trailing zeros, no -0."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# =================================================================================================
# Symbols
# =================================================================================================

def power_symbol(name, kind, shape):
    """A power symbol like KiCad's own: the (power) flag and one hidden pin of length 0 at the
    origin, so the net takes the symbol's value."""
    pts = " ".join(f"(xy {f(x)} {f(y)})" for x, y in shape)
    vy = -3.81 if name == "GND" else 3.556
    return f"""(symbol "{name}" (power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "#PWR" (at 0 {f(vy - 2.54 if name == "GND" else vy + 2.54)} 0) {gen._font(True)})
(property "Value" "{name}" (at 0 {f(vy)} 0) {gen._font()})
(property "Footprint" "" (at 0 0 0) {gen._font(True)})
(property "Datasheet" "" (at 0 0 0) {gen._font(True)})
(property "Description" "Power symbol: a global label named {name}" (at 0 0 0) {gen._font(True)})
(symbol "{name}_0_1" (polyline (pts {pts}) (stroke (width 0) (type default)) (fill (type none))))
(symbol "{name}_1_1" (pin {kind} line (at 0 0 {270 if name == "GND" else 90}) (length 0) (hide yes) (name "{name}" {gen._font()}) (number "1" {gen._font()})))
(embedded_fonts no))"""


def two_pin_symbol(name, ref, desc, fp):
    """R and C: a slim box with pin 1 on top and pin 2 below, 10.16 mm pin to pin."""
    return gen.box_symbol(name, ref, name, f"{L}:{fp}", "", desc, 1.27, 2.54,
                          [("1", "1", "passive", "T", 0), ("2", "2", "passive", "B", 0)])


def pico_symbol():
    pins = []
    for n in range(1, 21):
        pins.append((str(n), PICO[n][0], PICO[n][1], "L", 24.13 - 2.54 * (n - 1)))
    for n in range(21, 41):
        pins.append((str(n), PICO[n][0], PICO[n][1], "R", -24.13 + 2.54 * (n - 21)))
    for k, n in enumerate((41, 42, 43, 44)):
        pins.append((str(n), PICO[n][0], PICO[n][1], "B", -3.81 + 2.54 * k))
    return gen.box_symbol("Pico2W_SMD", "U", "Pico2W_SMD", f"{L}:Pico2W_SMD", PICO_DS,
                          "Raspberry Pi Pico 2 W as a surface-mount module: 40 castellations, the SWD pads and BOOTSEL",
                          15.24, 27.94, pins, mpn="SC1633")


def lcd_symbol():
    pins = [(str(i), n, t, "L", 13.97 - 2.54 * (i - 1)) for i, (n, t, _net) in enumerate(LCD_PINS, 1)]
    return gen.box_symbol("LCD_1.54in_ST7789", "LCD", "LCD_1.54in_ST7789", f"{L}:LCD_1.54in_240x240_FPC12_P0.7mm", "",
                          "1.54in 240x240 IPS panel, ST7789, 12-pin 0.7 mm FPC soldered to the board", 10.16, 15.24, pins)


def switch_symbol():
    return gen.box_symbol("SW_Push_4", "SW", "SW_Push_4", f"{L}:SW_SMD_6x6x5_TS1097A", "",
                          "6x6 mm tact switch; pins 1 and 2 are two diagonal pads, the other two pads carry no net",
                          2.54, 2.54, [("1", "1", "passive", "T", 0), ("2", "2", "passive", "B", 0)], lcsc=SW_LCSC, mpn=SW_MPN)


def npn_symbol():
    return gen.box_symbol("Q_NPN_S8050", "Q", "Q_NPN_S8050", f"{L}:SOT-23", "", "NPN transistor, SOT-23: 1 B, 2 E, 3 C",
                          5.08, 5.08, [("1", "B", "passive", "L", 0), ("2", "E", "passive", "B", 0), ("3", "C", "passive", "T", 0)],
                          lcsc="C2150", mpn="S8050 J3Y")


def pads_symbol(n, pins, fp):
    h = 1.27 * n
    ps = [(str(i), name, "passive", "R", h - 1.27 - 2.54 * (i - 1)) for i, (name, _net) in enumerate(pins, 1)]
    return gen.box_symbol(f"Pads_1x{n}", "J", f"Pads_1x{n}", f"{L}:{fp}", "", f"{n} solder pads at 2.54 mm, a header fits", 5.08, h, ps)


def write_symbols():
    syms = [pico_symbol(), lcd_symbol(), switch_symbol(), npn_symbol(),
            two_pin_symbol("R", "R", "Resistor", "R_0603"), two_pin_symbol("C", "C", "Capacitor", "C_0603"),
            pads_symbol(8, J2_PINS, "Pads_1x8_P2.54mm"), pads_symbol(2, J3_PINS, "Pads_1x2_P2.54mm"),
            pads_symbol(3, J4_PINS, "Pads_1x3_P2.54mm"),
            power_symbol("GND", "power_in", [(0, 0), (0, -1.27), (1.27, -1.27), (0, -2.54), (-1.27, -1.27), (0, -1.27)]),
            power_symbol("+3V3", "power_in", [(0, 0), (0, 2.54), (-0.762, 1.27), (0, 2.54), (0.762, 1.27)]),
            power_symbol("VSYS", "power_in", [(0, 0), (0, 2.54), (-0.762, 1.27), (0, 2.54), (0.762, 1.27)]),
            power_symbol("PWR_FLAG", "power_out", [(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)])]
    os.makedirs(LIB, exist_ok=True)
    with open(os.path.join(LIB, f"{L}.kicad_sym"), "w") as fh:
        fh.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        fh.write("\n".join(syms))
        fh.write("\n)\n")
    return {re.match(r'\(symbol "([^"]+)"', s).group(1): s for s in syms}


# =================================================================================================
# Schematic
# =================================================================================================

class ConsoleSheet(gen.Sheet):
    def power(self, name, x, y, rot=0):
        """gen.Sheet.power points at KiCad's stock power library; this project carries its own."""
        self.npwr += 1
        ref = f"#FLG0{self.npwr:02d}" if name == "PWR_FLAG" else f"#PWR0{self.npwr:02d}"
        self.symbol(f"{L}:{name}", ref, name, x, y, ["1"], rot=rot)

    def write(self, path, title):
        super().write(path, title)
        s = open(path).read()
        s = s.replace('(comment 1 "The PCB is the plug: see hardware/key-pcb/README.md")', f'(comment 1 "{NOTE}")', 1)
        s = s.replace(f'(date "{gen.DATE}")', f'(date "{DATE}")', 1)
        open(path, "w").write(s)


def pin_end(x, y, side, off, w, h):
    """Where a box_symbol pin connects, in schematic coordinates."""
    return {"L": (x - w - 2.54, y - off), "R": (x + w + 2.54, y - off), "T": (x + off, y - h - 2.54), "B": (x + off, y + h + 2.54)}[side]


def write_schematic(syms):
    sh = ConsoleSheet(NAME)
    for name, text in syms.items():
        sh.lib(f"{L}:{name}", text.replace(f'(symbol "{name}"', f'(symbol "{L}:{name}"', 1))
    uids = {}

    def part(ref, lib_id, x, y, pin_nums, box_h, extra=()):
        p = PARTS[ref]
        fields = list(p["fields"]) + list(extra)
        uids[ref] = sh.symbol(f"{L}:{lib_id}", ref, p["value"], x, y, pin_nums, fp=f"{L}:{p['fp']}", fields=fields,
                              dnp=p["dnp"], in_bom=p["in_bom"], on_board=True, box_h=box_h)

    def end(x, y, side, off, w, h, net, dx=7.62):
        """Wire a pin out by dx and put a label or power symbol there; None marks it no-connect."""
        px, py = pin_end(x, y, side, off, w, h)
        if net is None:
            sh.nc(px, py)
            return
        if side == "L":
            ex, ey = px - dx, py
        elif side == "R":
            ex, ey = px + dx, py
        elif side == "T":
            ex, ey = px, py - 2.54
        else:
            ex, ey = px, py + 2.54
        sh.wire(px, py, ex, ey)
        if net == "GND":
            sh.power("GND", ex, ey, rot={"L": 270, "R": 90, "T": 0, "B": 0}[side])
        elif net in ("+3V3", "VSYS"):
            sh.power(net, ex, ey, rot={"L": 90, "R": 270, "T": 0, "B": 180}[side])
        else:
            sh.label(net.lstrip("/"), ex, ey, left=(side == "L"))

    # U1, the Pico, in the middle
    ux, uy, uw, uh = 139.7, 88.9, 15.24, 27.94
    part("U1", "Pico2W_SMD", ux, uy, [str(n) for n in PICO], uh)
    for n, (_name, _t, net) in PICO.items():
        if n <= 20:
            end(ux, uy, "L", 24.13 - 2.54 * (n - 1), uw, uh, net)
        elif n <= 40:
            end(ux, uy, "R", -24.13 + 2.54 * (n - 21), uw, uh, net)
        else:
            end(ux, uy, "B", -3.81 + 2.54 * (n - 41), uw, uh, net)
    sh.text("Pico 2 W as an SMD module, on the back of the board.\n"
            "Physical pins 1-40, as the datasheet numbers them.\n"
            "Nets are firmware/board.py's GPIOs for the Waveshare build\n"
            "and BUILD1.md's key pins, so the firmware does not change.", ux - 20.32, uy + 36.83)
    # PWR_FLAG on GND (the only net with no power_out pin driving it)
    sh.power("GND", 50.8, 55.88)
    sh.wire(50.8, 55.88, 58.42, 55.88)
    sh.power("PWR_FLAG", 58.42, 55.88, rot=180)

    # the switches in a row along the bottom
    for k, (ref, label, net) in enumerate(SWITCHES):
        x, y = 35.56 + 20.32 * k, 171.45
        part(ref, "SW_Push_4", x, y, ["1", "2"], 2.54)
        end(x, y, "T", 0, 2.54, 2.54, net)
        end(x, y, "B", 0, 2.54, 2.54, "GND")
    sh.text("Buttons to GND, the Pico's internal pull-ups. Up/down/left/right, A (Select,\n"
            "held to sign), B (Back), Y (Reject): the Waveshare board's keys, same GPIOs.\n"
            "Each switch is wired on a diagonal (pads 1 and 2), so it works whichever\n"
            "pair of legs the maker joins inside; the other two pads carry no net.", 35.56, 182.88)

    # the key pads and spares on the left
    for ref, lib_id, pins, x, y in (("J2", "Pads_1x8", J2_PINS, 30.48, 93.98), ("J3", "Pads_1x2", J3_PINS, 30.48, 123.19),
                                    ("J4", "Pads_1x3", J4_PINS, 30.48, 138.43)):
        n = len(pins)
        part(ref, lib_id, x, y, [str(i) for i in range(1, n + 1)], 1.27 * n)
        for i, (_name, net) in enumerate(pins, 1):
            end(x, y, "R", 1.27 * n - 1.27 - 2.54 * (i - 1), 5.08, 1.27 * n, net)
    sh.text("J2: the key's wires, straight from the GPIOs (BUILD1.md).\n"
            "GP6 powers the key for the bench only; a load switch, CC\n"
            "sensing and ESD come later (key-pcb/PROPOSALS.md).\n"
            "J3: a battery later. J4: X and the stick's press, spare.", 20.32, 68.58)
    for ref, x in (("R4", 83.82), ("R5", 96.52)):
        part(ref, "R", x, 128.27, ["1", "2"], 2.54)
        end(x, 128.27, "T", 0, 1.27, 2.54, NETS[ref, "1"])
        end(x, 128.27, "B", 0, 1.27, 2.54, NETS[ref, "2"])
    sh.text("I2C pull-ups to key power, not fitted", 78.74, 143.51)

    # the panel and its backlight on the right
    lx, ly = 220.98, 86.36
    part("LCD1", "LCD_1.54in_ST7789", lx, ly, [str(i) for i in range(1, 13)], 15.24)
    for i, (_name, _t, net) in enumerate(LCD_PINS, 1):
        end(lx, ly, "L", 13.97 - 2.54 * (i - 1), 10.16, 15.24, net)
    sh.text("12-pin 0.7 mm FPC, the Waveshare Pico-LCD-1.3's\n"
            "pin order. Confirm against the panel's drawing.", lx - 25.4, ly + 21.59)
    part("C1", "C", 193.04, 129.54, ["1", "2"], 2.54)
    end(193.04, 129.54, "T", 0, 1.27, 2.54, "+3V3")
    end(193.04, 129.54, "B", 0, 1.27, 2.54, "GND")
    part("R1", "R", 236.22, 129.54, ["1", "2"], 2.54)
    end(236.22, 129.54, "T", 0, 1.27, 2.54, "/LCD_LEDK")
    end(236.22, 129.54, "B", 0, 1.27, 2.54, "/BL_C")
    part("Q1", "Q_NPN_S8050", 236.22, 157.48, ["1", "2", "3"], 5.08)
    end(236.22, 157.48, "L", 0, 5.08, 5.08, "/BL_B")
    end(236.22, 157.48, "B", 0, 5.08, 5.08, "GND")
    end(236.22, 157.48, "T", 0, 5.08, 5.08, "/BL_C")
    part("R2", "R", 208.28, 157.48, ["1", "2"], 2.54)
    end(208.28, 157.48, "T", 0, 1.27, 2.54, "/LCD_BL")
    end(208.28, 157.48, "B", 0, 1.27, 2.54, "/BL_B")
    part("R3", "R", 220.98, 170.18, ["1", "2"], 2.54)
    end(220.98, 170.18, "T", 0, 1.27, 2.54, "/BL_B")
    end(220.98, 170.18, "B", 0, 1.27, 2.54, "GND")
    sh.text("Backlight: LEDA on 3V3, LEDK through R1 and Q1 to GND,\n"
            "GP13 drives the base through R2 (PWM, lcd.py); R3 keeps it off at boot.", 190.5, 185.42)

    os.makedirs(OUT, exist_ok=True)
    sh.write(os.path.join(OUT, NAME + ".kicad_sch"), TITLE)
    return sh.root, uids


# =================================================================================================
# Footprints
# =================================================================================================
# Each footprint is a list of items in the library frame (origin at the part centre, y down):
#   ("pad", num, kind, shape, x, y, w, h, drill, layers)          kind: smd | thru_hole | np_thru_hole
#   ("line", x1, y1, x2, y2, layer, width) ("rect", x1, y1, x2, y2, layer, width, fill)
#   ("circle", cx, cy, r, layer, width, fill) ("text", s, x, y, rot, layer, size)
# The same list writes the library file and the board copy (flipped for the back).

def _pad(num, kind, shape, x, y, w, h=None, drill=None, layers=None):
    h = w if h is None else h
    if layers is None:
        layers = ["F.Cu", "F.Mask", "F.Paste"] if kind == "smd" else ["*.Cu", "*.Mask"]
    return ("pad", num, kind, shape, x, y, w, h, drill, layers)


def _outline(hw, hh, layer="F.Fab", width=0.1, grow=0.0):
    return ("rect", -hw - grow, -hh - grow, hw + grow, hh + grow, layer, width, False)


def fp_pico():
    """The datasheet's SMT footprint (Figure 5): pads 3.2 x 1.6 whose centres sit 0.81 mm inside
    each long edge, the SWD pads E/F/G, the test points and the USB shell pads. Module frame
    (origin bottom-left, USB at the top) to library frame: x - 10.5, 25.5 - y."""
    items = []
    for n in range(1, 21):
        items.append(_pad(str(n), "smd", "rect", -9.69, -24.13 + 2.54 * (n - 1), 3.2, 1.6))
    for n in range(21, 41):
        items.append(_pad(str(n), "smd", "rect", 9.69, 24.13 - 2.54 * (n - 21), 3.2, 1.6))
    for num, mx, my in (("41", 11.0841, 19.8), ("42", 13.6241, 19.8), ("43", 16.1641, 19.8)):
        items.append(_pad(num, "smd", "circle" if num != "41" else "rect", mx - 10.5, 25.5 - my, 1.5748, layers=["F.Cu", "F.Mask"]))
    items.append(_pad("44", "smd", "roundrect", 8 - 10.5, 25.5 - 36.5, 1.5, 1.5, layers=["F.Cu", "F.Mask"]))
    for mx, my in ((8, 39), (8, 41.5), (10.5, 46.5)):      # TP5, TP4, TP1; TP2/TP3 sit 0.075 mm from the USB pads, left out
        items.append(_pad("", "smd", "roundrect", mx - 10.5, 25.5 - my, 1.5, 1.5, layers=["F.Cu", "F.Mask"]))
    for mx, my, w, h in ((7.775, 49.5, 1.8, 1.1), (13.225, 49.5, 1.8, 1.1), (8.075, 46.47, 1.45, 1.05), (12.925, 46.47, 1.45, 1.05)):
        items.append(_pad("", "smd", "roundrect", mx - 10.5, 25.5 - my, w, h, layers=["F.Cu", "F.Mask"]))
    items.append(_outline(10.5, 25.5))                                     # the module
    items.append(("rect", -10.5 - 0.25, -25.5 - 1.3 - 0.25, 10.5 + 0.25, 25.5 + 0.25, "F.CrtYd", 0.05, False))
    items.append(("rect", -3.95, -26.8, 3.95, -22.0, "F.Fab", 0.1, False))   # the micro-USB, 1.3 mm over the edge
    items.append(("rect", -7.0, 16.5, 7.0, 25.5, "F.Fab", 0.1, False))      # the antenna: 14 x 9, keep copper away
    items.append(("text", "antenna", 0, 21.0, 0, "F.Fab", 0.8))
    items.append(("text", "USB", 0, -24.4, 0, "F.Fab", 0.8))
    for x in (-10.5, 10.5):                                                  # silk along the long edges, between the pads
        items.append(("line", x, -25.5, x, 25.5, "F.SilkS", 0.12))
    items.append(("line", -10.5, 25.5, 10.5, 25.5, "F.SilkS", 0.12))
    items.append(("circle", -12.0, -25.4, 0.3, "F.SilkS", 0.12, True))     # pin 1
    items.append(("text", "1", -8.0, -24.13, 0, "F.Fab", 0.6))
    items.append(("text", "20", -8.0, 24.13, 0, "F.Fab", 0.6))
    items.append(("text", "21", 8.0, 24.13, 0, "F.Fab", 0.6))
    items.append(("text", "40", 8.0, -24.13, 0, "F.Fab", 0.6))
    return dict(items=items, attr="smd exclude_from_pos_files",
                descr="Raspberry Pi Pico 2 W as an SMD module: the datasheet's footprint (Figure 5), pads 3.2x1.6 at 2.54 mm, "
                      "SWD pads 41-43, BOOTSEL 44, test points and USB shell pads as plain copper. Keep the 14x9 mm antenna end copper-free.",
                tags="pico rp2350 module")


def fp_switch():
    """XUNPU TS-1097A land pattern: 2.0 x 2.0 pads, 6.0 mm apart in x (4.0 gap, 8.0 overall), on
    the 3.5 mm terminal pitch in y. Only the diagonal pads carry numbers."""
    items = [_pad("1", "smd", "rect", -3.0, -1.75, 2.0, 2.0), _pad("2", "smd", "rect", 3.0, 1.75, 2.0, 2.0),
             _pad("", "smd", "rect", 3.0, -1.75, 2.0, 2.0), _pad("", "smd", "rect", -3.0, 1.75, 2.0, 2.0),
             _outline(3.0, 3.0), ("circle", 0, 0, 2.3, "F.Fab", 0.1, False),
             ("rect", -4.25, -3.25, 4.25, 3.25, "F.CrtYd", 0.05, False)]
    for sx in (-1, 1):
        items.append(("line", sx * 3.2, -0.5, sx * 3.2, 0.5, "F.SilkS", 0.12))
    for sy in (-1, 1):
        items.append(("line", -1.6, sy * 3.2, 1.6, sy * 3.2, "F.SilkS", 0.12))
    return dict(items=items, attr="smd",
                descr="6x6x5 mm SMD tact switch (XUNPU TS-1097A, LCSC C720496): pads 2x2 at (+-3.0, +-1.75). Pads 1 and 2 are a diagonal "
                      "pair, so the switch works whichever legs are joined inside; the other two are copper only.",
                tags="tact switch 6x6")


def fp_lcd():
    n, pitch, (pw, ph) = PANEL["pins"], PANEL["pitch"], PANEL["pad"]
    gw, gh = PANEL["glass"]
    items = []
    for i in range(1, n + 1):
        k = (i - 1) if PANEL["pin1_left"] else (n - i)
        items.append(_pad(str(i), "smd", "rect", pitch * (k - (n - 1) / 2), 0, pw, ph))
    top = -PANEL["gap"] - gh
    items.append(("rect", -gw / 2, top, gw / 2, -PANEL["gap"], "F.Fab", 0.1, False))        # the glass
    a = PANEL["active"] / 2
    cy = top + 2.0 + a                                                                    # the active area sits high in the glass
    items.append(("rect", -a, cy - a, a, cy + a, "F.Fab", 0.1, False))
    items.append(("rect", -gw / 2 - 0.25, top - 0.25, gw / 2 + 0.25, ph / 2 + 0.75, "F.CrtYd", 0.05, False))
    for sx in (-1, 1):                                                                    # silk corners to place the glass by
        items.append(("line", sx * gw / 2, top, sx * gw / 2, top + 3, "F.SilkS", 0.12))
        items.append(("line", sx * gw / 2, top, sx * (gw / 2 - 3), top, "F.SilkS", 0.12))
        items.append(("line", sx * gw / 2, -PANEL["gap"], sx * gw / 2, -PANEL["gap"] - 3, "F.SilkS", 0.12))
    x1 = pitch * (-(n - 1) / 2) if PANEL["pin1_left"] else pitch * ((n - 1) / 2)
    items.append(("circle", x1, ph / 2 + 0.6, 0.2, "F.SilkS", 0.12, True))              # pin 1
    items.append(("text", "FPC pads, pin 1 at the dot", 0, ph / 2 + 1.6, 0, "F.Fab", 0.6))
    return dict(items=items, attr="smd exclude_from_pos_files",
                descr=f"1.54in 240x240 ST7789 IPS panel: {n} FPC pads {pw}x{ph} at {pitch} mm, soldered flat; the glass is drawn above them on F.Fab. Measure a panel before ordering.",
                tags="lcd st7789 fpc")


def fp_chip(name, descr):
    return dict(items=[_pad("1", "smd", "roundrect", -0.775, 0, 0.9, 0.95), _pad("2", "smd", "roundrect", 0.775, 0, 0.9, 0.95),
                       _outline(0.8, 0.4), ("rect", -1.5, -0.75, 1.5, 0.75, "F.CrtYd", 0.05, False),
                       ("line", -0.4, -0.75, 0.4, -0.75, "F.SilkS", 0.12), ("line", -0.4, 0.75, 0.4, 0.75, "F.SilkS", 0.12)],
                attr="smd", descr=descr, tags="0603")


def fp_sot23():
    return dict(items=[_pad("1", "smd", "roundrect", -0.95, 1.1, 0.9, 0.8), _pad("2", "smd", "roundrect", 0.95, 1.1, 0.9, 0.8),
                       _pad("3", "smd", "roundrect", 0, -1.1, 0.9, 0.8), _outline(0.7, 1.45),
                       ("rect", -1.7, -1.75, 1.7, 1.75, "F.CrtYd", 0.05, False),
                       ("line", -0.7, -1.6, 0.7, -1.6, "F.SilkS", 0.12), ("line", -0.7, 1.6, 0.7, 1.6, "F.SilkS", 0.12),
                       ("circle", -1.7, 1.9, 0.15, "F.SilkS", 0.12, True)],
                attr="smd", descr="SOT-23, KiCad's land pattern: pads 0.9x0.8 at (+-0.95, 1.1) and (0, -1.1)", tags="sot-23")


def fp_pads(n, labels):
    items = [_pad(str(i), "thru_hole", "circle" if i > 1 else "rect", 0, 2.54 * (i - 1 - (n - 1) / 2), 1.7, 1.7, 1.0) for i in range(1, n + 1)]
    for i, lab in enumerate(labels, 1):
        items.append(("text", lab, 1.6, 2.54 * (i - 1 - (n - 1) / 2), 0, "F.Fab", 0.6))
    hh = 1.27 * n
    items.append(("rect", -1.27, -hh, 1.27, hh, "F.CrtYd", 0.05, False))
    return dict(items=items, attr="through_hole exclude_from_pos_files exclude_from_bom",
                descr=f"{n} solder pads at 2.54 mm, 1.7 mm with a 1.0 mm hole: a wire or a header. Pin 1 is square.", tags="pads header")


def fp_hole():
    return dict(items=[_pad("", "np_thru_hole", "circle", 0, 0, 3.2, 3.2, 3.2), ("circle", 0, 0, 1.85, "F.CrtYd", 0.05, False)],
                attr="through_hole board_only exclude_from_pos_files exclude_from_bom",
                descr="3.2 mm mounting hole, not plated, for an M3 screw", tags="mounting hole")


FOOTPRINTS = {
    "Pico2W_SMD": fp_pico, "SW_SMD_6x6x5_TS1097A": fp_switch, "LCD_1.54in_240x240_FPC12_P0.7mm": fp_lcd,
    "R_0603": lambda: fp_chip("R_0603", "0603 resistor: pads 0.9x0.95 at +-0.775"),
    "C_0603": lambda: fp_chip("C_0603", "0603 capacitor: pads 0.9x0.95 at +-0.775"),
    "SOT-23": fp_sot23,
    "Pads_1x8_P2.54mm": lambda: fp_pads(8, [n for n, _ in J2_PINS]),
    "Pads_1x2_P2.54mm": lambda: fp_pads(2, [n for n, _ in J3_PINS]),
    "Pads_1x3_P2.54mm": lambda: fp_pads(3, [n for n, _ in J4_PINS]),
    "MountingHole_3.2mm": fp_hole,
}


def _flip_layer(layer, back):
    if not back:
        return layer
    return {"F": "B", "B": "F"}.get(layer[0], layer[0]) + layer[1:] if layer[1:2] == "." else layer


def item_text(it, back=False, rot=0.0, indent="\t"):
    """One footprint item as KiCad text. On the back, y is negated and the layers swap, which is
    how KiCad stores a flipped footprint (checked against key-c's test pads and mark)."""
    s = -1 if back else 1
    kind = it[0]
    if kind == "pad":
        _, num, pk, shape, x, y, w, h, drill, layers = it
        layers = " ".join(f'"{_flip_layer(l, back)}"' for l in layers)
        d = f" (drill {f(drill)})" if drill else ""
        rr = " (roundrect_rratio 0.25)" if shape == "roundrect" else ""
        ang = f" {f(rot)}" if rot else ""
        return f'{indent}(pad "{num}" {pk} {shape} (at {f(x)} {f(s * y)}{ang}) (size {f(w)} {f(h)}){d} (layers {layers}){rr}'
    if kind == "line":
        _, x1, y1, x2, y2, layer, width = it
        return (f'{indent}(fp_line (start {f(x1)} {f(s * y1)}) (end {f(x2)} {f(s * y2)}) (stroke (width {f(width)}) (type default)) '
                f'(layer "{_flip_layer(layer, back)}") (uuid "{uid()}"))')
    if kind == "rect":
        _, x1, y1, x2, y2, layer, width, fill = it
        return (f'{indent}(fp_rect (start {f(x1)} {f(s * y1)}) (end {f(x2)} {f(s * y2)}) (stroke (width {f(width)}) (type default)) '
                f'(fill {"yes" if fill else "no"}) (layer "{_flip_layer(layer, back)}") (uuid "{uid()}"))')
    if kind == "circle":
        _, cx, cy, r, layer, width, fill = it
        return (f'{indent}(fp_circle (center {f(cx)} {f(s * cy)}) (end {f(cx + r)} {f(s * cy)}) (stroke (width {f(width)}) (type default)) '
                f'(fill {"yes" if fill else "no"}) (layer "{_flip_layer(layer, back)}") (uuid "{uid()}"))')
    if kind == "text":
        _, text, x, y, trot, layer, size = it
        j = " (justify mirror)" if back else ""
        return (f'{indent}(fp_text user "{text}" (at {f(x)} {f(s * y)} {f(trot)}) (layer "{_flip_layer(layer, back)}") (uuid "{uid()}") '
                f'(effects (font (size {f(size)} {f(size)}) (thickness {f(max(0.1, size * 0.15))})){j}))')
    raise ValueError(kind)


def _prop(name, value, x, y, layer, hide=False, size=1.0, back=False):
    h = " (hide yes)" if hide else ""
    j = " (justify mirror)" if back else ""
    return (f'\t(property "{name}" "{value}" (at {f(x)} {f(y)} 0) (layer "{layer}"){h} (uuid "{uid()}") '
            f'(effects (font (size {f(size)} {f(size)}) (thickness {f(0.15 if size >= 1 else 0.12)})){j}))')


def write_footprints():
    d = os.path.join(LIB, f"{L}.pretty")
    os.makedirs(d, exist_ok=True)
    for name, make in FOOTPRINTS.items():
        fp = make()
        items = [item_text(it) + (f' (uuid "{uid()}"))' if it[0] == "pad" else "") for it in fp["items"]]
        with open(os.path.join(d, name + ".kicad_mod"), "w") as fh:
            fh.write(f'(footprint "{name}" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")\n'
                     f'\t(descr "{fp["descr"]}")\n\t(tags "{fp["tags"]}")\n'
                     + _prop("Reference", "REF**", 0, -ref_y(fp), "F.SilkS", size=0.8) + "\n"
                     + _prop("Value", name, 0, ref_y(fp), "F.Fab") + "\n"
                     + _prop("Datasheet", "", 0, 0, "F.Fab", hide=True) + "\n"
                     + _prop("Description", "", 0, 0, "F.Fab", hide=True) + "\n"
                     + f'\t(attr {fp["attr"]})\n' + "\n".join(items) + "\n\t(embedded_fonts no)\n)\n")
    # the mark, as the key boards carry it: one copy of the key library's file
    md = os.path.join(LIB, "picoquorum.pretty")
    os.makedirs(md, exist_ok=True)
    shutil.copy(os.path.join(HERE, "..", "key-pcb", "lib", "picoquorum.pretty", "PicoQuorum_Mark.kicad_mod"), md)


def ref_y(fp):
    """Just above the courtyard, for the reference text."""
    ys = [it[2] for it in fp["items"] if it[0] == "rect" and it[5] == "F.CrtYd"]
    ys += [it[2] - it[3] for it in fp["items"] if it[0] == "circle" and it[4] == "F.CrtYd"]
    return (min(ys) if ys else -1.0) - 0.7


# =================================================================================================
# Geometry shared by the board writer, the router and the self-check
# =================================================================================================

def rotate(x, y, rot):
    """KiCad's rotation of a footprint's local point, in page coordinates (y down). Verified
    against key-c: a footprint at -90 puts local (-2.475, -1.905) at (-1.905, +2.475)."""
    r = math.radians(rot)
    return x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)


def world(px, py, rot, back, lx, ly):
    """Page position of a footprint's local point. Back-side footprints store y negated."""
    dx, dy = rotate(lx, -ly if back else ly, rot)
    return px + dx, py + dy


def pad_rects():
    """Every numbered copper pad on the board: (ref, num, net, layers, (x0, y0, x1, y1) in page mm,
    is_tht). Also the unnumbered copper (net None). Rotations are multiples of 90, so pads stay
    axis-aligned: w and h swap at 90 and 270."""
    out = []
    parts = dict(PARTS)
    for ref, fpname, at in BOARD_ONLY:
        parts[ref] = dict(fp=fpname, at=at, rot=0, side="F")
    for ref, p in parts.items():
        fp = FOOTPRINTS[p["fp"]]()
        px, py = page(*p["at"])
        back = p["side"] == "B"
        for it in fp["items"]:
            if it[0] != "pad":
                continue
            _, num, kind, _shape, lx, ly, w, h, drill, layers = it
            cx, cy = world(px, py, p["rot"], back, lx, ly)
            if round(p["rot"]) % 180 != 0:
                w, h = h, w
            if kind == "smd":
                lays = {_flip_layer(l, back) for l in layers if l.endswith(".Cu")}
            else:
                lays = {"F.Cu", "B.Cu"}
            net = NETS.get((ref, num)) if num else None
            out.append(dict(ref=ref, num=num, net=net, layers=lays, rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                            centre=(cx, cy), tht=kind != "smd", drill=drill))
    return out


def _gap(a, b):
    """Distance between two axis-aligned rects (0 if they touch or overlap)."""
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


def ant_rect():
    x0, y0, x1, y1 = ANTENNA
    return (OX + x0, OY - y1, OX + x1, OY - y0)


def board_rect():
    return (OX, OY - H, OX + W, OY)


# =================================================================================================
# Routing: a grid router. Cells are 0.25 mm; B.Cu runs vertically, F.Cu sideways (no_sideways).
# =================================================================================================
STEP = 0.25
LAYERS = ("F.Cu", "B.Cu")
VIA_COST, TURN_COST = 12, 2


class Router:
    def __init__(self, pads):
        self.nx = int(round(W / STEP)) + 1
        self.ny = int(round(H / STEP)) + 1
        # owner[layer][cell] = net that copper (or its clearance band) belongs to, "*" = nobody may pass
        self.owner = {l: {} for l in LAYERS}
        self.lane = {l: {} for l in LAYERS}     # exit lanes: cells no other net may use or crowd
        self.segments = []      # (net, layer, width, (x0, y0), (x1, y1)) in page mm
        self.vias = []          # (net, x, y)
        self.pads = pads
        self.pad_cells = {}     # (ref, num) -> set of cells inside the pad (where a track may end)
        # Rows where a layer allows no sideways step. The back is vertical-only above the Pico's
        # bottom corridor: columns there never cross a sideways run, so a net routed late still
        # finds its way up (sideways runs on the back above the module walled in every later
        # net). The front carries the sideways runs, except in the module and lane zone, up to
        # y 27.5, and in the strip under the FPC pads, where they fan out downward. A bottom-row
        # net steps out of its pad at pad height, climbs the column between two top-row pads and
        # changes layer where it wants to turn; a top-row net rises in its lane (see lanes()).
        # Board y ranges.
        self.no_sideways = {"B.Cu": self.rows((4.6, H)),
                            "F.Cu": self.rows((5.0, 27.5)) | self.rows((39.5, 43.3))}
        # The one row between the bottom pads and the keep-out is the corridor out of the antenna
        # end: sideways steps there cost enough that a track turns up as soon as it is clear.
        self.slow_rows = {"B.Cu": self.rows((4.4, 4.6)), "F.Cu": set()}
        m = EDGE + VIA / 2
        for i in range(self.nx):
            for j in range(self.ny):
                x, y = self.xy(i, j)
                if x - OX < m or OX + W - x < m or y - (OY - H) < m or OY - y < m:
                    self.block(None, (i, j), "*")
        # the rule area forbids copper inside it: a track centre this far out keeps its edge outside
        self.block_rect(ant_rect(), "*", band=PWR_TRACK / 2 + 0.02)
        self.novia = set()      # no via in or next to any pad, whatever its net, nor in the keep-out
        ax0, ay0, ax1, ay1 = ant_rect()
        b = VIA / 2 + 0.05
        self.novia |= set(self.cells_in((ax0 - b, ay0 - b, ax1 + b, ay1 + b)))
        for pad in pads:
            net = pad["net"] if pad["net"] else "*"
            for layer in pad["layers"]:
                # a track centre this close to another net's pad: 0.345 leaves the 0.2 mm clearance
                # for a 0.25 track, lets a track leave a 0.4 mm FPC pad at 0.7 mm pitch, and leaves
                # one passable column in every 0.94 mm gap between two of the Pico's pads
                self.block_rect(pad["rect"], net, band=CLEAR + TRACK / 2 + 0.02, layer=layer)
            x0, y0, x1, y1 = pad["rect"]
            b = VIA / 2 + CLEAR + 0.05
            self.novia |= set(self.cells_in((x0 - b, y0 - b, x1 + b, y1 + b)))
        for pad in pads:        # the pad's own cells win over a neighbour's clearance band
            if not pad["net"] or pad["net"].startswith("unconnected"):
                continue
            cells = set()
            x0, y0, x1, y1 = pad["rect"]
            sh = TRACK / 2 - 0.03
            for (i, j) in self.cells_in((x0 + sh, y0 + sh, x1 - sh, y1 - sh)):
                cells.add((i, j))
                for layer in pad["layers"]:
                    self.owner[layer][i, j] = pad["net"]
            if not cells:
                cx, cy = pad["centre"]
                cells.add(self.cell(cx, cy))
            self.pad_cells[pad["ref"], pad["num"]] = cells

    def lanes(self, pads):
        """Reserve each Pico and FPC pad's way out before the other nets are routed; without this,
        the first track to run along a pad row walls in every pad behind it.

        The two Pico rows share their x positions, 2.54 mm apart, with 0.94 mm between pads. A
        top-row net climbs straight up on the right side of its pad for 3.5 mm, a strip where a via
        fits. A bottom-row net can't climb straight: the top-row pad at the same x is in the way.
        It steps right at pad height onto the column 1.27 mm over, halfway between two top-row
        pads, and climbs that column as far as it needs: the column is reserved to the top of the
        board, since a via of another net next to it would cut it, and it costs nothing when unused.
        An FPC pad's lane runs straight down for 3.5 mm. Lanes are cut short where another net
        already is (Select, routed first, crosses the first columns at the antenna end)."""
        for pad in pads:
            net = pad["net"]
            if not net or net == "GND" or net.startswith("unconnected") or pad["ref"] not in ("U1", "LCD1"):
                continue
            x0, y0, x1, y1 = pad["rect"]
            cols = sorted({i for i, _j in self.pad_cells[pad["ref"], pad["num"]]})
            cells = []
            if pad["ref"] == "U1" and pad["centre"][1] > page(*PICO_AT)[1]:      # bottom row
                gap_i = self.cell(pad["centre"][0] + 1.27, 0)[0]
                row_j = self.cell(0, page(0, 3.75)[1])[1]
                cells += [(i, row_j) for i in range(cols[-1], gap_i + 1)]
                top_j = self.cell(0, page(0, H - 1.0)[1])[1]     # the whole way up: nothing may via onto it
                cells += [(gap_i, j) for j in range(top_j, row_j)]
            elif pad["ref"] == "U1":                                           # top row
                edge_j = self.cell(x0, y0)[1]
                cells += [(i, edge_j - k) for i in cols[-2:] for k in range(1, int(3.5 / STEP) + 2)]
            else:                                                              # FPC: down
                edge_j = self.cell(x0, y1)[1]
                cells += [(i, edge_j + k) for i in cols for k in range(1, int(3.5 / STEP) + 2)]
            for cell in cells:
                for layer in pad["layers"]:
                    if self.owner[layer].get(cell) in (None, net) and self.lane[layer].get(cell) in (None, net):
                        self.lane[layer][cell] = net

    def rows(self, yrange):
        y0, y1 = yrange
        return {j for j in range(self.ny) if y0 - 1e-6 <= OY - self.xy(0, j)[1] <= y1 + 1e-6}

    def xy(self, i, j):
        return OX + i * STEP, OY - H + j * STEP

    def cell(self, x, y):
        return int(round((x - OX) / STEP)), int(round((y - (OY - H)) / STEP))

    def cells_in(self, rect):
        x0, y0, x1, y1 = rect
        i0, j0 = self.cell(x0, y0)
        i1, j1 = self.cell(x1, y1)
        for i in range(max(0, i0 - 1), min(self.nx, i1 + 2)):
            for j in range(max(0, j0 - 1), min(self.ny, j1 + 2)):
                x, y = self.xy(i, j)
                if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
                    yield i, j

    def block(self, layer, cell, net):
        for l in ([layer] if layer else LAYERS):
            cur = self.owner[l].get(cell)
            self.owner[l][cell] = net if cur in (None, net) else "*"

    def block_rect(self, rect, net, band, layer=None):
        x0, y0, x1, y1 = rect
        for cell in self.cells_in((x0 - band, y0 - band, x1 + band, y1 + band)):
            self.block(layer, cell, net)

    def free(self, layer, cell, net):
        return self.owner[layer].get(cell) in (None, net) and self.lane[layer].get(cell) in (None, net)

    def crowds_lane(self, layer, cell, net):
        """True if a track here would sit next to another net's exit lane."""
        i, j = cell
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if self.lane[layer].get((i + di, j + dj)) not in (None, net):
                    return True
        return False

    def via_ok(self, cell, net):
        if cell in self.novia:
            return False
        # a track reserves one cell around itself and a via two, so a free ring of one cell here
        # puts the nearest track 0.75 mm away (0.325 mm gap) and the nearest via 1.0 mm (0.4 mm)
        i, j = cell
        for l in LAYERS:
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if not self.free(l, (i + di, j + dj), net):
                        return False
            for di in range(-2, 3):          # its reservation reaches two cells: never onto a lane
                for dj in range(-2, 3):
                    if self.lane[l].get((i + di, j + dj)) not in (None, net):
                        return False
        return True

    def route_net(self, net, pads, width):
        """Connect the pads of one net: shortest path from everything connected so far to the
        nearest pad not yet reached, repeated. Returns the pads it could not reach."""
        todo = [p for p in pads]
        first = todo.pop(0)
        sources = {(l, c) for c in self.pad_cells[first["ref"], first["num"]] for l in first["layers"]}
        reached_cells = {}
        for p in todo:
            for c in self.pad_cells[p["ref"], p["num"]]:
                for l in p["layers"]:
                    reached_cells[l, c] = (p["ref"], p["num"])
        failed = []
        while todo:
            path = self.search(net, sources, reached_cells)
            if path is None:
                failed.append(todo.pop(0))
                continue
            end = path[-1]
            hit = reached_cells[end]
            todo = [p for p in todo if (p["ref"], p["num"]) != hit]
            for key in [k for k, v in reached_cells.items() if v == hit]:
                del reached_cells[key]
            self.commit(net, path, width)
            sources |= set(path)
            hit_pad = next(p for p in pads if (p["ref"], p["num"]) == hit)
            sources |= {(l, c) for c in self.pad_cells[hit] for l in hit_pad["layers"]}
        return failed

    def search(self, net, sources, targets):
        """Dijkstra over (layer, cell) with a preferred direction per layer and a via cost."""
        dist, prev = {}, {}
        heap = []
        for s in sources:
            dist[s] = 0
            heapq.heappush(heap, (0, s, None))
        while heap:
            d, node, _ = heapq.heappop(heap)
            if d > dist.get(node, 1e18):
                continue
            if node in targets:
                path = [node]
                while prev.get(path[-1]) is not None:
                    path.append(prev[path[-1]])
                return path[::-1]
            l, (i, j) = node
            came = prev.get(node)
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = i + di, j + dj
                if not (0 <= ni < self.nx and 0 <= nj < self.ny):
                    continue
                if not self.free(l, (ni, nj), net) or self.crowds_lane(l, (ni, nj), net):
                    continue
                horizontal = di != 0
                if horizontal and (nj in self.no_sideways[l] or j in self.no_sideways[l]):
                    continue
                c = 1 if (horizontal == (l == "F.Cu")) else 1.6     # the front runs sideways, the back up
                if horizontal and nj in self.slow_rows[l]:
                    c += 6
                if came is not None and came[0] == l:
                    pdi, pdj = i - came[1][0], j - came[1][1]
                    if (pdi, pdj) != (di, dj):
                        c += TURN_COST
                nn = (l, (ni, nj))
                if d + c < dist.get(nn, 1e18):
                    dist[nn] = d + c
                    prev[nn] = node
                    heapq.heappush(heap, (d + c, nn, node))
            other = "B.Cu" if l == "F.Cu" else "F.Cu"
            if self.via_ok((i, j), net) and (other, (i, j)) not in sources:
                nn = (other, (i, j))
                if d + VIA_COST < dist.get(nn, 1e18):
                    dist[nn] = d + VIA_COST
                    prev[nn] = node
                    heapq.heappush(heap, (d + VIA_COST, nn, node))
        return None

    def commit(self, net, path, width):
        """Turn a cell path into straight segments and vias, and reserve its cells."""
        run = [path[0]]
        for node in path[1:]:
            if node[0] != run[-1][0]:                        # a via
                self.flush(net, run, width)
                x, y = self.xy(*node[1])
                self.reserve_via(net, node[1])
                run = [node]
            else:
                run.append(node)
        self.flush(net, run, width)

    def flush(self, net, run, width):
        if len(run) < 2:
            return
        layer = run[0][0]
        pts = [self.xy(*n[1]) for n in run]
        # merge collinear steps
        merged = [pts[0]]
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            if not ((a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1])):
                merged.append(b)
        merged.append(pts[-1])
        for a, b in zip(merged, merged[1:]):
            self.segments.append((net, layer, width, a, b))
        # the cells a track and its clearance cover: the next track of another net is one cell past
        r = 1 if width <= PWR_TRACK else 2
        for n in run:
            i, j = n[1]
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    self.block(layer, (i + di, j + dj), net)

    def reserve_via(self, net, cell):
        """Two cells around a via: the next track of another net is 0.75 mm from its centre."""
        x, y = self.xy(*cell)
        self.vias.append((net, x, y))
        i, j = cell
        for di in range(-2, 3):
            for dj in range(-2, 3):
                self.block(None, (i + di, j + dj), net)

    def stitch(self, net="GND", pitch=7.0):
        """Ground stitching vias wherever a via fits on a coarse grid, plus one beside each
        front-side GND pad so the pour on either layer reaches it."""
        n = 0
        xs = [OX + 2.5 + pitch * k for k in range(int((W - 5) / pitch) + 1)]
        ys = [OY - H + 2.5 + pitch * k for k in range(int((H - 5) / pitch) + 1)]
        for x in xs:
            for y in ys:
                c = self.cell(x, y)
                if self.via_ok(c, net) and self.owner["F.Cu"].get(c) is None and self.owner["B.Cu"].get(c) is None:
                    self.add_via(net, c)
                    n += 1
        return n

    def add_via(self, net, cell):
        self.reserve_via(net, cell)

    def gnd_pad_vias(self, pads):
        """A via next to every GND pad that is not on the Pico, with a short track to it, so each
        is tied to both pours even if the fill around it is narrow."""
        n = 0
        for pad in pads:
            if pad["net"] != "GND" or pad["ref"] == "U1" or pad["tht"]:
                continue
            cx, cy = pad["centre"]
            layer = next(iter(pad["layers"]))
            best = None
            for r in (0.9, 1.1, 1.3, 1.5, 1.8, 2.1, 2.5):
                for ang in range(0, 360, 45):
                    x, y = cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))
                    c = self.cell(x, y)
                    vx, vy = self.xy(*c)
                    if not (abs(vx - cx) < 1e-6 or abs(vy - cy) < 1e-6):
                        continue            # keep the stub straight
                    if not self.via_ok(c, "GND"):
                        continue
                    path = self.stub_cells(pad, c)
                    if path is not None and all(self.free(layer, k, "GND") and not self.crowds_lane(layer, k, "GND") for k in path):
                        best, stub = c, path
                        break
                if best:
                    break
            if not best:
                continue
            vx, vy = self.xy(*best)
            self.add_via("GND", best)
            self.segments.append(("GND", layer, TRACK, (cx, cy), (vx, vy)))
            for k in stub:
                i, j = k
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        self.block(layer, (i + di, j + dj), "GND")
            n += 1
        return n

    def stub_cells(self, pad, via_cell):
        """The grid cells a straight stub from the pad's centre to the via crosses, outside the pad."""
        cx, cy = pad["centre"]
        ci, cj = self.cell(cx, cy)
        vi, vj = via_cell
        if ci != vi and cj != vj:
            return None
        cells = []
        i, j = ci, cj
        while (i, j) != (vi, vj):
            i += (vi > i) - (vi < i)
            j += (vj > j) - (vj < j)
            x, y = self.xy(i, j)
            if _gap(pad["rect"], (x, y, x, y)) > 0:
                cells.append((i, j))
        return cells


def route(pads):
    r = Router(pads)
    by_net = {}
    for p in pads:
        if p["net"] and not p["net"].startswith("unconnected") and p["net"] != "GND":
            by_net.setdefault(p["net"], []).append(p)

    def span(ps):
        xs = [p["centre"][0] for p in ps]
        ys = [p["centre"][1] for p in ps]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    # Order: the Pico's nets from the antenna end outward, so each takes the free columns nearest
    # its pad and never the ones a pad further in still needs (Select, GP15, goes first: its only
    # way out is the 1 mm corridor between the pad row and the keep-out). After it, exit lanes are
    # reserved for every other pad. The nets with no Pico pad come last, longest first: a short
    # local net routed early tends to wall in the pads around it.
    def pico_key(n):
        """The Pico pad's x from the antenna end; at the same x the top-row net goes first, since a
        bottom-row net has more ways out (its lane, or the gap between two top-row pads). The nets
        with no Pico pad (the backlight's) come first of all, longest first: they are short and
        local, and the long sideways runs that come later would otherwise box their pads in."""
        ps = [p for p in by_net[n] if p["ref"] == "U1"]
        if not ps:
            return (-1, 0)
        p = min(ps, key=lambda p: p["centre"][0])
        return (round(p["centre"][0] - OX, 2), p["centre"][1])

    order = sorted(by_net, key=lambda n: (n != "/BTN_A", pico_key(n), -span(by_net[n])))
    failed = []
    for net in order:
        ps = sorted(by_net[net], key=lambda p: (p["ref"] != "U1", p["centre"]))
        width = PWR_TRACK if net in ("+3V3", "VSYS") else TRACK
        for p in r.route_net(net, ps, width):
            failed.append((net, p["ref"], p["num"]))
        if net == "/BTN_A":
            r.lanes(pads)
    r.gnd_pad_vias(pads)
    r.stitch()
    return r, failed


# =================================================================================================
# The board file
# =================================================================================================

def _template_blocks():
    """The (layers) and (setup) blocks as KiCad 9 wrote them for key-b, with this board's stackup
    and drill/place origin."""
    src = open(os.path.join(HERE, "..", "key-pcb", "key-b-udfn", "key-b-udfn.kicad_pcb")).read()

    def balanced(text, start):
        """The end of the S-expression whose opening parenthesis is at or after start."""
        k = text.index("(", start)
        d = 0
        while True:
            d += {"(": 1, ")": -1}.get(text[k], 0)
            k += 1
            if d == 0:
                return k

    def block(key):
        i = src.index(f"\n\t({key}") + 1
        return src[i:balanced(src, i)]
    layers = block("layers")
    setup = block("setup")
    i = setup.index("\t\t(stackup")
    setup = setup[:i] + gen_cd.STACKUP.format(finish="HASL(with lead-free)").rstrip("\n") + setup[balanced(setup, i):]
    setup = re.sub(r"\(aux_axis_origin [^)]*\)", f"(aux_axis_origin {f(OX)} {f(OY)})", setup)
    return layers, setup


def footprint_text(ref, p, fpname, fp, nets, path_uuid):
    px, py = page(*p["at"])
    back = p["side"] == "B"
    rot = p["rot"]
    side_silk, side_fab = ("B.SilkS", "B.Fab") if back else ("F.SilkS", "F.Fab")
    ry = ref_y(fp)
    lines = [f'\t(footprint "{L}:{fpname}" (layer "{"B.Cu" if back else "F.Cu"}") (uuid "{uid()}") (at {f(px)} {f(py)}{" " + f(rot) if rot else ""})',
             f'\t\t(descr "{fp["descr"]}")', f'\t\t(tags "{fp["tags"]}")']
    s = -1 if back else 1
    # the switches are named by their silk labels, the big parts and the holes need no reference
    hide_ref = ref in ("U1", "LCD1") or ref[:2] in ("H1", "H2", "H3", "H4", "SW") or ref == "LOGO1"
    rx, ry2 = p.get("ref_at", (0, -ry))         # the silk reference: above the courtyard unless placed
    lines.append(_prop("Reference", ref, rx, s * ry2, side_silk, hide=hide_ref, size=0.8, back=back).replace("\t(", "\t\t(", 1))
    lines.append(_prop("Value", p["value"], 0, s * ry, side_fab, back=back).replace("\t(", "\t\t(", 1))
    fields = dict(p.get("fields", []))
    lines.append(_prop("Datasheet", fields.pop("Datasheet", ""), 0, 0, side_fab, hide=True, back=back).replace("\t(", "\t\t(", 1))
    lines.append(_prop("Description", fields.pop("Description", ""), 0, 0, side_fab, hide=True, back=back).replace("\t(", "\t\t(", 1))
    for k, v in fields.items():
        lines.append(_prop(k, v, 0, 0, side_fab, hide=True, back=back).replace("\t(", "\t\t(", 1))
    if path_uuid:
        lines.append(f'\t\t(path "/{path_uuid}")')
        lines.append('\t\t(sheetname "/")')
        lines.append(f'\t\t(sheetfile "{NAME}.kicad_sch")')
    attr = fp["attr"] + (" dnp" if p.get("dnp") else "")
    lines.append(f"\t\t(attr {attr})")
    for it in fp["items"]:
        t = item_text(it, back=back, rot=rot, indent="\t\t")
        if it[0] == "pad":
            num = it[1]
            net = NETS.get((ref, num)) if num else None
            if net:
                t += f' (net {nets[net]} "{net}")'
                if ref == "LCD1" and net == "GND":
                    t += " (zone_connect 2)"          # solid to the pour: 0.4 mm pads starve a thermal
            t += f' (uuid "{uid()}"))'
        lines.append(t)
    lines.append("\t\t(embedded_fonts no)")
    lines.append("\t)")
    return "\n".join(lines)


def mark_text(x, y):
    """The PicoQuorum mark on the back, as a board-only footprint from gen_cd's library file."""
    src = open(os.path.join(LIB, "picoquorum.pretty", "PicoQuorum_Mark.kicad_mod")).read()
    body = src[src.index("\n(fp_poly"):src.rindex("\n(embedded_fonts")]
    # flip to the back: negate every y and swap the silk layer
    def neg(m):
        return f"(xy {m.group(1)} {f(-float(m.group(2)))})"
    body = re.sub(r"\(xy ([\-\d.]+) ([\-\d.]+)\)", neg, body)
    body = re.sub(r"\(center ([\-\d.]+) ([\-\d.]+)\) \(end ([\-\d.]+) ([\-\d.]+)\)",
                  lambda m: f"(center {m.group(1)} {f(-float(m.group(2)))}) (end {m.group(3)} {f(-float(m.group(4)))})", body)
    body = body.replace('"F.SilkS"', '"B.SilkS"')
    px, py = page(x, y)
    return (f'\t(footprint "picoquorum:PicoQuorum_Mark" (layer "B.Cu") (uuid "{uid()}") (at {f(px)} {f(py)})\n'
            f'\t\t(descr "The PicoQuorum mark, one colour, for silkscreen: docs/BRAND.md")\n\t\t(tags "logo")\n'
            + _prop("Reference", "LOGO1", 0, -4, "B.SilkS", hide=True, back=True).replace("\t(", "\t\t(", 1) + "\n"
            + _prop("Value", "PicoQuorum_Mark", 0, 4, "B.Fab", hide=True, back=True).replace("\t(", "\t\t(", 1) + "\n"
            + "\t\t(attr board_only exclude_from_pos_files exclude_from_bom allow_missing_courtyard)\n"
            + body.strip("\n").replace("\n(", "\n\t\t(").replace("(fp_", "\t\t(fp_", 1) + "\n\t\t(embedded_fonts no)\n\t)")


def gr_text(s, x, y, layer, size=1.0, back=False, rot=0):
    px, py = page(x, y)
    j = " (justify mirror)" if back else ""
    return (f'\t(gr_text "{s}" (at {f(px)} {f(py)}{" " + f(rot) if rot else ""}) (layer "{layer}") (uuid "{uid()}") '
            f'(effects (font (size {f(size)} {f(size)}) (thickness {f(0.15 if size >= 1 else 0.12)})){j}))')


def gr_rect(x0, y0, x1, y1, layer, width=0.15):
    a, b = page(x0, y0), page(x1, y1)
    return (f'\t(gr_rect (start {f(a[0])} {f(a[1])}) (end {f(b[0])} {f(b[1])}) (stroke (width {f(width)}) (type default)) '
            f'(fill no) (layer "{layer}") (uuid "{uid()}"))')


def outline_text():
    x0, y0, x1, y1 = board_rect()
    r, c = CORNER, CORNER * (1 - math.sqrt(0.5))
    E = '(stroke (width 0.1) (type default)) (layer "Edge.Cuts")'
    out = [f"\t(gr_line (start {f(x0 + r)} {f(y0)}) (end {f(x1 - r)} {f(y0)}) {E} (uuid \"{uid()}\"))",
           f"\t(gr_line (start {f(x1)} {f(y0 + r)}) (end {f(x1)} {f(y1 - r)}) {E} (uuid \"{uid()}\"))",
           f"\t(gr_line (start {f(x1 - r)} {f(y1)}) (end {f(x0 + r)} {f(y1)}) {E} (uuid \"{uid()}\"))",
           f"\t(gr_line (start {f(x0)} {f(y1 - r)}) (end {f(x0)} {f(y0 + r)}) {E} (uuid \"{uid()}\"))",
           f"\t(gr_arc (start {f(x0)} {f(y0 + r)}) (mid {f(x0 + c)} {f(y0 + c)}) (end {f(x0 + r)} {f(y0)}) {E} (uuid \"{uid()}\"))",
           f"\t(gr_arc (start {f(x1 - r)} {f(y0)}) (mid {f(x1 - c)} {f(y0 + c)}) (end {f(x1)} {f(y0 + r)}) {E} (uuid \"{uid()}\"))",
           f"\t(gr_arc (start {f(x1)} {f(y1 - r)}) (mid {f(x1 - c)} {f(y1 - c)}) (end {f(x1 - r)} {f(y1)}) {E} (uuid \"{uid()}\"))",
           f"\t(gr_arc (start {f(x0 + r)} {f(y1)}) (mid {f(x0 + c)} {f(y1 - c)}) (end {f(x0)} {f(y1 - r)}) {E} (uuid \"{uid()}\"))"]
    return "\n".join(out)


def zone_text(net_num, net, layer, name, pts):
    p = " ".join(f"(xy {f(x)} {f(y)})" for x, y in pts)
    return (f'\t(zone (net {net_num}) (net_name "{net}") (layer "{layer}") (uuid "{uid()}") (name "{name}") (hatch edge 0.5)\n'
            f'\t\t(connect_pads (clearance 0.25)) (min_thickness 0.2) (filled_areas_thickness no)\n'
            f'\t\t(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
            f'\t\t(polygon (pts {p}))\n\t)')


def keepout_text(pts):
    p = " ".join(f"(xy {f(x)} {f(y)})" for x, y in pts)
    return (f'\t(zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (uuid "{uid()}") (name "Antenna: no copper") (hatch edge 0.5)\n'
            f'\t\t(connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no)\n'
            f'\t\t(keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed))\n'
            f'\t\t(placement (enabled no) (sheetname ""))\n'
            f'\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
            f'\t\t(polygon (pts {p}))\n\t)')


def write_board(uids, router):
    names = sorted(set(NETS.values()))
    nets = {n: i + 1 for i, n in enumerate(names)}
    layers, setup = _template_blocks()
    out = ["(kicad_pcb", "\t(version 20241229)", '\t(generator "picoquorum_gen")', '\t(generator_version "9.0")',
           "\t(general (thickness 1.6) (legacy_teardrops no))", '\t(paper "A4")',
           f'\t(title_block (title "{TITLE}") (date "{DATE}") (rev "A") (company "PicoQuorum") (comment 1 "{NOTE}"))',
           layers, setup, '\t(net 0 "")']
    out += [f'\t(net {i} "{n}")' for n, i in nets.items()]
    for ref, p in PARTS.items():
        out.append(footprint_text(ref, p, p["fp"], FOOTPRINTS[p["fp"]](), nets, uids[ref]))
    for ref, fpname, at in BOARD_ONLY:
        out.append(footprint_text(ref, dict(fp=fpname, value="M3", at=at, rot=0, side="F", fields=[]), fpname, FOOTPRINTS[fpname](), nets, None)
                   .replace("(attr through_hole board_only", "(attr through_hole board_only"))
    out.append(mark_text(25.5, 38.0))
    out.append(outline_text())
    # silkscreen: the buttons' names, the key pads' names (on the back, where the wires go), the board's name
    for ref, label, _net in SWITCHES:
        x, y = _SW_AT[ref]
        if label == "UP":
            out.append(gr_text(label, x, y + 4.8, "F.SilkS"))
        elif label == "DOWN":
            out.append(gr_text(label, x, y - 4.8, "F.SilkS"))
        elif label in ("LEFT", "RIGHT"):
            out.append(gr_text(label, x, y + 4.8, "F.SilkS"))
        else:
            out.append(gr_text(label, x, y - 4.6, "F.SilkS"))
    x, y = _SW_AT["SW7"]
    out.append(gr_rect(x - 4.7, y - 4.7, x + 4.7, y + 4.7, "F.SilkS", 0.2))     # the ring around Reject
    for i, (name, _net) in enumerate(J2_PINS, 1):
        out.append(gr_text(name, 45.6, 54.89 + 8.89 - 2.54 * (i - 1), "B.SilkS", 0.8, back=True))
    for i, (name, _net) in enumerate(J3_PINS, 1):
        out.append(gr_text(name, 5.5, 51.27 + 1.27 - 2.54 * (i - 1), "B.SilkS", 0.8, back=True))
    for i, (name, _net) in enumerate(J4_PINS, 1):
        out.append(gr_text(name, 5.5, 60.0 + 2.54 - 2.54 * (i - 1), "B.SilkS", 0.8, back=True))
    out.append(gr_text("PICOQUORUM", 25.5, 83.6, "F.SilkS", 1.0))
    out.append(gr_text(f"PicoQuorum console-pocket {DATE[:7]}", 25.5, 33.2, "B.SilkS", 1.0, back=True))
    out.append(gr_text(SRC, 25.5, 31.2, "B.SilkS", 0.8, back=True))
    out.append(gr_text("Pico 2 W on this side, USB at the right edge", 25.5, 29.2, "B.SilkS", 0.8, back=True))
    out.append(gr_text("key wires", 45.6, 65.5, "B.SilkS", 0.8, back=True))
    # tracks and vias
    for net, layer, width, (ax, ay), (bx, by) in router.segments:
        out.append(f'\t(segment (start {f(ax)} {f(ay)}) (end {f(bx)} {f(by)}) (width {f(width)}) (layer "{layer}") (net {nets[net]}) (uuid "{uid()}"))')
    for net, x, y in router.vias:
        out.append(f'\t(via (at {f(x)} {f(y)}) (size {f(VIA)}) (drill {f(DRILL)}) (layers "F.Cu" "B.Cu") (net {nets[net]}) (uuid "{uid()}"))')
    # pours and the antenna rule area
    x0, y0, x1, y1 = board_rect()
    whole = [(x0 - 1, y0 - 1), (x1 + 1, y0 - 1), (x1 + 1, y1 + 1), (x0 - 1, y1 + 1)]
    out.append(zone_text(nets["GND"], "GND", "F.Cu", "GND top", whole))
    out.append(zone_text(nets["GND"], "GND", "B.Cu", "GND bottom", whole))
    ax0, ay0, ax1, ay1 = ant_rect()
    out.append(keepout_text([(ax0 - 1, ay0), (ax1, ay0), (ax1, ay1), (ax0 - 1, ay1)]))
    out.append("\t(embedded_fonts no)")
    out.append(")")
    with open(os.path.join(OUT, NAME + ".kicad_pcb"), "w") as fh:
        fh.write("\n".join(out) + "\n")
    return nets


def write_project(sheet_uuid):
    d = json.load(open(os.path.join(HERE, "..", "key-pcb", "key-b-udfn", "key-b-udfn.kicad_pro")))
    d["meta"]["filename"] = NAME + ".kicad_pro"
    d["board"]["design_settings"]["rules"].update(gen.JLC_RULES)
    for c in d["net_settings"]["classes"]:
        if c["name"] == "Default":
            c.update(clearance=CLEAR, track_width=TRACK, via_diameter=VIA, via_drill=DRILL)
    d["sheets"] = [[sheet_uuid, "Root"]]
    with open(os.path.join(OUT, NAME + ".kicad_pro"), "w") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)
        fh.write("\n")


def write_lib_tables():
    with open(os.path.join(OUT, "sym-lib-table"), "w") as fh:
        fh.write(f'(sym_lib_table\n  (version 7)\n  (lib (name "{L}")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/{L}.kicad_sym")'
                 f'(options "")(descr "PicoQuorum console parts"))\n)\n')
    with open(os.path.join(OUT, "fp-lib-table"), "w") as fh:
        fh.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{L}")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/{L}.pretty")'
                 f'(options "")(descr "PicoQuorum console footprints"))\n'
                 f'  (lib (name "picoquorum")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/picoquorum.pretty")'
                 f'(options "")(descr "The PicoQuorum mark"))\n)\n')


# =================================================================================================
# Self-check: reads the written board back, as KiCad will
# =================================================================================================

def check(path):
    tree = gen_cd._sexpr(open(path).read())
    kids = gen_cd._kids

    def node(n, key):
        k = kids(n, key)
        return k[0] if k else None
    nets = {int(n[1]): n[2] for n in kids(tree, "net")}
    pads, segs, vias = [], [], []
    for fp in kids(tree, "footprint"):
        ref = next(p[2] for p in kids(fp, "property") if p[1] == "Reference")
        at = node(fp, "at")
        px, py, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        back = node(fp, "layer")[1] == "B.Cu"
        for pad in kids(fp, "pad"):
            num, kind = pad[1], pad[2]
            pat = node(pad, "at")
            lx, ly = float(pat[1]), float(pat[2])
            size = node(pad, "size")
            w, h = float(size[1]), float(size[2])
            if round(rot) % 180 != 0:
                w, h = h, w
            dx, dy = rotate(lx, ly, rot)             # the file already holds the flipped y
            cx, cy = px + dx, py + dy
            lays = {l for l in node(pad, "layers")[1:] if l.endswith(".Cu")}
            if "*.Cu" in lays:
                lays = {"F.Cu", "B.Cu"}
            netv = node(pad, "net")
            pads.append(dict(ref=ref, num=num, net=netv[2] if netv else None, layers=lays,
                             rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), centre=(cx, cy), kind=kind))
    for s in kids(tree, "segment"):
        a, b = node(s, "start"), node(s, "end")
        w = float(node(s, "width")[1])
        ax, ay, bx, by = float(a[1]), float(a[2]), float(b[1]), float(b[2])
        segs.append(dict(net=nets[int(node(s, "net")[1])], layer=node(s, "layer")[1], w=w, a=(ax, ay), b=(bx, by),
                         rect=(min(ax, bx) - w / 2, min(ay, by) - w / 2, max(ax, bx) + w / 2, max(ay, by) + w / 2)))
    for v in kids(tree, "via"):
        at = node(v, "at")
        x, y = float(at[1]), float(at[2])
        d = float(node(v, "size")[1])
        vias.append(dict(net=nets[int(node(v, "net")[1])], at=(x, y), rect=(x - d / 2, y - d / 2, x + d / 2, y + d / 2)))
    problems = []

    def inside_rect(pt, rect):
        return rect[0] - 1e-6 <= pt[0] <= rect[2] + 1e-6 and rect[1] - 1e-6 <= pt[1] <= rect[3] + 1e-6

    # 1. clearance between copper of different nets on a shared layer
    items = [("pad", p["net"], p["layers"], p["rect"], f'{p["ref"]}.{p["num"] or "-"}') for p in pads]
    items += [("seg", s["net"], {s["layer"]}, s["rect"], f'track {s["net"]}') for s in segs]
    items += [("via", v["net"], {"F.Cu", "B.Cu"}, v["rect"], f'via {v["net"]}') for v in vias]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if not (a[2] & b[2]):
                continue
            if a[1] is not None and a[1] == b[1]:
                continue
            g = _gap(a[3], b[3])
            if g < CLEAR - 1e-6:
                problems.append(f"clearance {g:.3f} mm between {a[4]} and {b[4]}")
    # 2. copper to the edge, and nothing in the antenna area but the module's own pads
    bx0, by0, bx1, by1 = board_rect()
    ar = ant_rect()
    for kind, net, _l, rect, name in items:
        if rect[0] < bx0 + EDGE - 1e-6 or rect[1] < by0 + EDGE - 1e-6 or rect[2] > bx1 - EDGE + 1e-6 or rect[3] > by1 - EDGE + 1e-6:
            problems.append(f"{name} within {EDGE} mm of the edge")
        if _gap(rect, ar) < 1e-6 and not name.startswith("U1."):
            problems.append(f"{name} inside the antenna keep-out")
    # 3. a track end or a via inside a pad of another net is a short
    for s in segs:
        for p in pads:
            if s["layer"] in p["layers"] and p["net"] != s["net"]:
                for pt in (s["a"], s["b"]):
                    if p["rect"][0] <= pt[0] <= p["rect"][2] and p["rect"][1] <= pt[1] <= p["rect"][3]:
                        problems.append(f'track {s["net"]} ends inside {p["ref"]}.{p["num"]}')
    for v in vias:
        for p in pads:
            if inside_rect(v["at"], p["rect"]):
                problems.append(f'via {v["net"]} inside pad {p["ref"]}.{p["num"] or "-"}')
    # 4. connectivity, by union-find over pads, tracks and vias
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    def inside(pt, rect):
        return rect[0] - 1e-6 <= pt[0] <= rect[2] + 1e-6 and rect[1] - 1e-6 <= pt[1] <= rect[3] + 1e-6

    for i, s in enumerate(segs):
        for j, p in enumerate(pads):
            if s["layer"] in p["layers"] and p["net"] == s["net"] and (inside(s["a"], p["rect"]) or inside(s["b"], p["rect"])):
                union(("s", i), ("p", j))
        for k, t in enumerate(segs):
            if k <= i or t["layer"] != s["layer"] or t["net"] != s["net"]:
                continue
            if any(inside(pt, t["rect"]) for pt in (s["a"], s["b"])) or any(inside(pt, s["rect"]) for pt in (t["a"], t["b"])):
                union(("s", i), ("s", k))
        for m, v in enumerate(vias):
            if v["net"] == s["net"] and (inside(v["at"], s["rect"]) or any(math.hypot(v["at"][0] - pt[0], v["at"][1] - pt[1]) < 1e-6 for pt in (s["a"], s["b"]))):
                union(("s", i), ("v", m))
    for m, v in enumerate(vias):
        if v["net"] == "GND":
            union(("v", m), "POUR")
    by_net = {}
    for j, p in enumerate(pads):
        if p["net"] and not p["net"].startswith("unconnected"):
            by_net.setdefault(p["net"], []).append(j)
    for net, idx in sorted(by_net.items()):
        if net == "GND":
            for j in idx:
                p = pads[j]
                if find(("p", j)) == find("POUR"):
                    continue
                if _gap(p["rect"], ar) < 1e-6:
                    problems.append(f'GND pad {p["ref"]}.{p["num"]} sits in the keep-out, the pour cannot reach it')
            continue
        roots = {find(("p", j)) for j in idx}
        if len(roots) > 1:
            groups = {}
            for j in idx:
                groups.setdefault(find(("p", j)), []).append(f'{pads[j]["ref"]}.{pads[j]["num"]}')
            problems.append(f"net {net} is in {len(roots)} pieces: " + " | ".join(", ".join(g) for g in groups.values()))
    # 5. the net table on the board is the schematic's
    on_board = {(p["ref"], p["num"]): p["net"] for p in pads if p["num"]}
    for key, net in NETS.items():
        if on_board.get(key) != net:
            problems.append(f"pad {key} carries {on_board.get(key)} on the board, {net} in NETS")
    # 6. the Pico: pins 1 and 40 at the USB (right) end, 20 and 21 at the antenna (left) end, rows at the module's edges
    pico = {p["num"]: p["centre"] for p in pads if p["ref"] == "U1"}
    rows = {}
    for n in ("1", "20", "21", "40"):
        x, y = pico[n]
        rows[n] = (round(x - OX, 2), round(OY - y, 2))
    want = {"1": (49.63, 2.31), "20": (1.37, 2.31), "21": (1.37, 21.69), "40": (49.63, 21.69)}
    for n, w in want.items():
        if any(abs(a - b) > 0.02 for a, b in zip(rows[n], w)):
            problems.append(f"Pico pin {n} at {rows[n]} (board mm), expected {w}")
    gnd_vias = sum(1 for v in vias if v["net"] == "GND")
    print(f"{NAME}: {len(pads)} pads, {len(segs)} tracks, {len(vias)} vias ({gnd_vias} GND), {len(nets) - 1} nets")
    print("  Pico pins 1/20/21/40 (board mm):", ", ".join(f"{n} at {rows[n]}" for n in ("1", "20", "21", "40")))
    if problems:
        print(f"  {len(problems)} problem(s):")
        for p in problems[:60]:
            print("   -", p)
        return False
    print("  self-check clean: clearance, edge, antenna, shorts, connectivity, net table, Pico orientation")
    return True


# =================================================================================================

def main():
    path = os.path.join(OUT, NAME + ".kicad_pcb")
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        sys.exit(0 if check(path) else 1)
    syms = write_symbols()
    write_footprints()
    os.makedirs(OUT, exist_ok=True)
    write_lib_tables()
    sheet_uuid, uids = write_schematic(syms)
    pads = pad_rects()
    router, failed = route(pads)
    for net, ref, num in failed:
        print(f"  unrouted: {net} to {ref}.{num}")
    write_board(uids, router)
    write_project(sheet_uuid)
    ok = check(path) and not failed
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
