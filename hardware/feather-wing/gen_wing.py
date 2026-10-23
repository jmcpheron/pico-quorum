#!/usr/bin/env python3
"""PicoQuorum key wing, wing-a: a board the size of a Feather that sits behind Adafruit's ESP32-S3
Reverse TFT on its header pins and carries the key's port. Writes the whole KiCad 9 project as text:

    python3 hardware/feather-wing/gen_wing.py          write lib/, wing-a/, then self-check
    python3 hardware/feather-wing/gen_wing.py --check  self-check wing-a/wing-a.kicad_pcb only

On the board (README.md says why):
- the Feather's two header rows, 16 and 12 pins, where Adafruit's own board file puts them
- a vertical USB-C plug that key-c (hardware/key-pcb/key-c-usbc) slides onto, with console-a's key
  port behind it: a current-limited, reverse-blocking switch for the key's power, CC1 and CC2 read
  on their own ADC pins, 2.2k pull-ups to the switched power, ESD on every line
- four 0 ohm links that choose the key's bus: the Feather's own SDA/SCL (fitted, today's console
  image) or D11/D12 (a bus of its own, for a later image)
- test pads for VKEY and GND, and no copper behind the ESP32 module's antenna

Everything that is soldered by a machine is on the front, the side away from the Feather. Nothing
but the header pins is on the back, which faces the Feather's own parts.

No KiCad is needed here, as with hardware/console-pocket/gen_console.py, whose text helpers this
reuses: symbols, footprints, the schematic, the board, its routing and the project file are all
written here, and a geometric self-check stands in for DRC until `tools/keypcb check wing-a` runs on
a machine with KiCad. The zones are written unfilled: `tools/keypcb fill wing-a` fills them.

Once the board is edited in KiCad, the KiCad files are the source of truth: don't run this again.
Frames: the board frame is the Feather's own, as Adafruit's EagleCAD file draws it seen from its
parts side: origin at the bottom-left corner, the Feather's USB-C at the left, x right and y up, in
mm. Looking at the wing's front is looking the same way, so the two frames are one. Page
coordinates (KiCad's, y down) are OX + x, OY - y. Footprints are drawn in KiCad's library frame
(origin at the part's centre, y down).
"""
import heapq, importlib.util, json, math, os, random, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "hardware", "key-pcb"))
import gen        # noqa: E402  the key boards' text helpers: uid, box_symbol, Sheet, JLC_RULES
import gen_cd     # noqa: E402  _sexpr, _kids, STACKUP

_spec = importlib.util.spec_from_file_location("pocket", os.path.join(REPO, "hardware", "console-pocket", "gen_console.py"))
pocket = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pocket)   # console-pocket's footprint and board-text helpers; it writes nothing on import
f, item_text, _prop, _pad, rotate, _gap = pocket.f, pocket.item_text, pocket._prop, pocket._pad, pocket.rotate, pocket._gap

NAME = "wing-a"
L = "pqwing"                                   # the library name, in sym-lib-table and fp-lib-table
LIB = os.path.join(HERE, "lib")
OUT = os.path.join(HERE, NAME)
DATE = "2026-10-23"
TITLE = "PicoQuorum key wing, wing-a: key-c's USB-C port behind a Feather ESP32-S3 Reverse TFT (FeatherWing-compatible)"
NOTE = "A FeatherWing-compatible key port: see hardware/feather-wing/README.md"
SRC = "github.com/jmcpheron/pico-quorum"

# --- the Feather, from Adafruit's "Adafruit ESP32-S3 Reverse TFT Feather.brd" (2026-10-23) -------
W, H = 50.8, 22.86       # 2.0 x 0.9 in
CORNER = 2.54            # its corners are 0.1 in arcs
OX, OY = 100.0, 140.0    # page coordinates of the board's bottom-left corner
# Its holes: 2.5 mm plated at the USB end, 2.2 mm plain at the far end, off the 0.1 in grid there.
# The wing's holes are clearances for an M2.5 and an M2 screw at the same centres.
HOLES = [("H1", (2.54, 2.54), 2.7), ("H2", (2.54, 20.32), 2.7), ("H3", (48.26, 1.8415), 2.4), ("H4", (48.26, 20.955), 2.4)]
# The two header rows, Feather order from the USB end; the 16-pin row along the bottom edge.
# Adafruit's names, and what the console calls the ESP32-S3 GPIO behind each (module pin - 4).
ROW16 = [("RST", None), ("3V3", None), ("AREF", None), ("GND", None), ("A0", 18), ("A1", 17), ("A2", 16), ("A3", 15),
         ("A4", 14), ("A5", 8), ("SCK", 36), ("MO", 35), ("MI", 37), ("RX", 38), ("TX", 39), ("DB", 43)]
ROW12 = [("BAT", None), ("EN", None), ("USB", None), ("D13", 13), ("D12", 12), ("D11", 11), ("D10", 10), ("D9", 9),
         ("D6", 6), ("D5", 5), ("SCL", 4), ("SDA", 3)]
ROW16_AT = (6.35, 1.27)          # pin 1 (RST); the rest at +2.54 mm in x
ROW12_AT = (16.51, 21.59)        # pin 1 (BAT)
# The ESP32-S3-MINI-1 lies along the board, its antenna at the far end: the module's outline runs
# to x 48.36 and its pads stop at x 45.35. No copper on the wing from x KEEPOUT_X, and no pour from
# POUR_X, so the wing's ground isn't a reflector a few mm behind the antenna.
KEEPOUT_X, POUR_X = 45.6, 41.0
ANTENNA_SIDE_X = 42.6     # and no track or via from here to the keep-out, below the bus links

EDGE = 0.3               # copper to edge (JLCPCB: 0.3 on a 2-layer board)
CLEAR = 0.2              # the Default netclass clearance
HOLE_CLEAR = 0.3         # copper to a plain hole (JLCPCB's 0.25, with margin)
TRACK = 0.25
VIA, DRILL = 0.6, 0.3

# --- what the wing uses on the Feather: header pin -> net. None is a no-connect. --------------------
FEATHER16 = {"3V3": "+3V3", "GND": "GND"}
FEATHER12 = {"D12": "/ALT_SCL", "D11": "/ALT_SDA", "D10": "/KEY_FAULT", "D9": "/KEY_EN", "D6": "/CC2_SENSE",
             "D5": "/CC1_SENSE", "SCL": "/FTHR_SCL", "SDA": "/FTHR_SDA"}
# The same, as the firmware will see it (README.md, "Pins"). D5 and D6 are on ADC1, which works with
# Wi-Fi on; the console image uses none of these pins today.
GPIO = {"/CC1_SENSE": 5, "/CC2_SENSE": 6, "/KEY_EN": 9, "/KEY_FAULT": 10, "/ALT_SDA": 11, "/ALT_SCL": 12,
        "/FTHR_SDA": 3, "/FTHR_SCL": 4}


def check_firmware():
    """The wing's pins against firmware/board.py's "feather-s3" profile. Read only."""
    b = open(os.path.join(REPO, "firmware", "board.py")).read()
    m = re.search(r"^if THREE:(.*?)\nelif ", b, re.S | re.M)
    prof = m.group(1)
    sda, scl = map(int, re.search(r"SPI_ID, SDA, SCL, LED = \d+, (\d+), (\d+), (\d+)", prof).groups()[:2])
    bad = []
    if (sda, scl) != (GPIO["/FTHR_SDA"], GPIO["/FTHR_SCL"]):
        bad.append(f"board.py's feather-s3 key bus is GPIO{sda}/{scl}, the wing's default link is GPIO{GPIO['/FTHR_SDA']}/{GPIO['/FTHR_SCL']}")
    used = {int(n) for n in re.findall(r"\b(\d+)\b", " ".join(re.findall(r"^\s+(?:DC|BUTTONS|SPI_ID|NOT_KEYS|MAINT)[^\n]*", prof, re.M)))}
    for net, g in GPIO.items():
        if net.startswith("/FTHR"):
            continue
        if g in used:
            bad.append(f"{net} is GPIO{g}, which board.py's feather-s3 profile already uses")
    if bad:
        sys.exit("the wing's pins disagree with the firmware:\n  " + "\n  ".join(bad))


# --- the one net table: (ref, pad) -> net, exactly as KiCad names them from the schematic ----------
NETS = {}
for i, (name, _g) in enumerate(ROW16, 1):
    NETS["J2", str(i)] = FEATHER16.get(name) or f"unconnected-(J2-{name}-Pad{i})"
for i, (name, _g) in enumerate(ROW12, 1):
    NETS["J3", str(i)] = FEATHER12.get(name) or f"unconnected-(J3-{name}-Pad{i})"
# J1, the plug, as console-a wires it: key-c joins A6 to B6 and A7 to B7 itself, so B6 and B7 stay open
PLUG = {"A1": "GND", "A4": "/VKEY", "A5": "/CC1", "A6": "/KEY_SDA", "A7": "/KEY_SCL", "A8": None, "A9": "/VKEY",
        "A12": "GND", "B1": "GND", "B4": "/VKEY", "B5": "/CC2", "B6": None, "B7": None, "B8": None, "B9": "/VKEY",
        "B12": "GND", "SH": "GND"}
PLUG_NAMES = {"A1": "GND", "A4": "VBUS", "A5": "CC", "A6": "D+", "A7": "D-", "A8": "SBU1", "A9": "VBUS", "A12": "GND",
              "B1": "GND", "B4": "VBUS", "B5": "VCONN", "B6": "D+", "B7": "D-", "B8": "SBU2", "B9": "VBUS", "B12": "GND",
              "SH": "SHIELD"}
for num, net in PLUG.items():
    NETS["J1", num] = net or f"unconnected-(J1-{PLUG_NAMES[num]}-Pad{num})"
NETS.update({
    # U2, the key's power switch: 80 mA limit (ILIM to GND), reverse blocking, output discharge
    ("U2", "1"): "+3V3", ("U2", "2"): "GND", ("U2", "3"): "/KEY_EN", ("U2", "4"): "/KEY_FAULT", ("U2", "5"): "GND",
    ("U2", "6"): "/VKEY",
    ("R7", "1"): "+3V3", ("R7", "2"): "/KEY_EN", ("R8", "1"): "+3V3", ("R8", "2"): "/KEY_FAULT",
    ("C1", "1"): "+3V3", ("C1", "2"): "GND", ("C3", "1"): "+3V3", ("C3", "2"): "GND",
    ("C2", "1"): "/VKEY", ("C2", "2"): "GND", ("D1", "1"): "/VKEY", ("D1", "2"): "GND",
    # U3: ESD on SDA and SCL, flow-through pairs 1/6 and 3/4, rail on 3V3 (never VKEY)
    ("U3", "1"): "/KEY_SCL", ("U3", "6"): "/KEY_SCL", ("U3", "3"): "/KEY_SDA", ("U3", "4"): "/KEY_SDA",
    ("U3", "5"): "+3V3", ("U3", "2"): "GND",
    # U4: ESD on CC1 and CC2
    ("U4", "1"): "/CC1", ("U4", "6"): "/CC1", ("U4", "3"): "/CC2", ("U4", "4"): "/CC2", ("U4", "5"): "+3V3", ("U4", "2"): "GND",
    ("R1", "1"): "/VKEY", ("R1", "2"): "/KEY_SDA", ("R2", "1"): "/VKEY", ("R2", "2"): "/KEY_SCL",
    ("R3", "1"): "+3V3", ("R3", "2"): "/CC1", ("R4", "1"): "+3V3", ("R4", "2"): "/CC2",
    ("R5", "1"): "/CC1", ("R5", "2"): "/CC1_SENSE", ("R6", "1"): "/CC2", ("R6", "2"): "/CC2_SENSE",
    # the bus links: R9/R10 fitted (the Feather's SDA/SCL), R11/R12 not (D11/D12)
    ("R9", "1"): "/KEY_SDA", ("R9", "2"): "/FTHR_SDA", ("R10", "1"): "/KEY_SCL", ("R10", "2"): "/FTHR_SCL",
    ("R11", "1"): "/KEY_SDA", ("R11", "2"): "/ALT_SDA", ("R12", "1"): "/KEY_SCL", ("R12", "2"): "/ALT_SCL",
    ("TP1", "1"): "/VKEY", ("TP2", "1"): "GND",
})

# --- parts: footprint, value, fields, board position, rotation (all on the front) -----------------
R0402, C0402, C0603 = "R_0402", "C_0402", "C_0603"
LCSC_R = {"10k": "C25744", "2.2k": "C25879", "1k": "C11702", "0R": "C17168"}
DS = dict(plug="https://datasheet.lcsc.com/lcsc/1912111437_Jing-Extension-of-the-Electronic-Co--918-118A2021Y40002_C399939.pdf",
          switch="https://www.diodes.com/assets/Datasheets/AP22652_53_52A_53A.pdf")
# JLCPCB's footprint turns, from console-a (hardware/console-pcb/gen_console.py JLC_ROT): tools/keypcb
# adds them to cpl.csv. The 0402s, 0603s and the SOD-523 need none.
JLC_ROT = {"C399939": -90, "C2158037": 180, "C7519": -90}


def R(value, desc, dnp=False):
    return dict(fp=R0402, value=value, dnp=dnp, fields=[("LCSC", LCSC_R[value]), ("Description", desc)])


PARTS = {
    "J1": dict(fp="USB_C_Plug_918-118A2021Y40002_Vertical", value="USB-C plug", rot=90,
               fields=[("LCSC", "C399939"), ("MPN", "918-118A2021Y40002"), ("Datasheet", DS["plug"]),
                       ("Description", "The key port: key-c slides onto this vertical plug. I2C on the USB 2.0 pair, no USB")]),
    "U2": dict(fp="SOT-23-6", value="AP22653W6-7", rot=0,
               fields=[("LCSC", "C2158037"), ("MPN", "AP22653W6-7"), ("Datasheet", DS["switch"]),
                       ("Description", "Key power: 80 mA limit (ILIM to GND), reverse blocking, output discharge, EN active high")]),
    "U3": dict(fp="SOT-23-6", value="USBLC6-2SC6", rot=0,
               fields=[("LCSC", "C7519"), ("MPN", "USBLC6-2SC6"), ("Datasheet", gen.USBLC6_DS),
                       ("Description", "ESD on the key's SDA and SCL, at the plug. Rail on 3V3, never on VKEY")]),
    "U4": dict(fp="SOT-23-6", value="USBLC6-2SC6", rot=0,
               fields=[("LCSC", "C7519"), ("MPN", "USBLC6-2SC6"), ("Datasheet", gen.USBLC6_DS),
                       ("Description", "ESD on CC1 and CC2, at the plug. Rail on 3V3")]),
    "D1": dict(fp="D_SOD-523", value="ESD5Z5V0", rot=0,
               fields=[("LCSC", "C502546"), ("MPN", "ESD5Z5V0"), ("Description", "TVS on VKEY, the plug's one line with no array on it: beside the plug")]),
    "C1": dict(fp=C0402, value="100n", rot=0, fields=[("LCSC", "C1525"), ("Description", "At U2's IN, as the datasheet asks")]),
    "C3": dict(fp=C0603, value="10u", rot=0, fields=[("LCSC", "C19702"), ("Description", "Bulk on the Feather's 3V3 at the wing: a key plugged in dips it less")]),
    "C2": dict(fp=C0603, value="10u", rot=0, fields=[("LCSC", "C19702"), ("Description", "At U2's OUT: the key's supply. Nothing bigger: U2 discharges it at power-off")]),
    "R1": R("2.2k", "KEY_SDA pull-up to the switched VKEY (the key has none): 2.2k for a 300 ns rise"),
    "R2": R("2.2k", "KEY_SCL pull-up to the switched VKEY"),
    "R3": R("10k", "Pull-up on CC1: with the key's 5.1k Rd it reads about 1.1 V"),
    "R4": R("10k", "Pull-up on CC2: the same"),
    "R5": R("1k", "CC1 into D5 (GPIO5, ADC1), current-limited"),
    "R6": R("1k", "CC2 into D6 (GPIO6, ADC1), current-limited"),
    "R7": R("10k", "KEY_EN pull-up: the key is powered unless firmware drives D9 low"),
    "R8": R("10k", "Pull-up for U2's open-drain FAULT flag, read on D10"),
    "R9": R("0R", "The key's SDA to the Feather's SDA (GPIO3): fitted, today's console image"),
    "R10": R("0R", "The key's SCL to the Feather's SCL (GPIO4): fitted"),
    "R11": R("0R", "The key's SDA to D11 (GPIO11), a bus of its own: not fitted. Fit R11/R12 or R9/R10, never both", dnp=True),
    "R12": R("0R", "The key's SCL to D12 (GPIO12): not fitted", dnp=True),
    "J2": dict(fp="Feather_Header_1x16", value="Feather 16-pin", rot=0, in_bom=False,
               fields=[("Description", "The Feather's 16-pin row, through-hole: a socket or a pin header, hand-soldered from the back")]),
    "J3": dict(fp="Feather_Header_1x12", value="Feather 12-pin", rot=0, in_bom=False,
               fields=[("Description", "The Feather's 12-pin row, through-hole: a socket or a pin header, hand-soldered from the back")]),
}
for ref, label in (("TP1", "VKEY"), ("TP2", "GND")):
    PARTS[ref] = dict(fp="TestPad_1.5mm", value=label, rot=0, in_bom=False,
                      fields=[("Description", f"Test pad, {label}: bare copper for a probe")])
for ref, p in PARTS.items():
    p.setdefault("dnp", False)
    p.setdefault("in_bom", True)
    p["fields"] = list(p["fields"]) + ([("JLCPCB Rotation Offset", str(JLC_ROT[dict(p["fields"]).get("LCSC")]))]
                                       if dict(p["fields"]).get("LCSC") in JLC_ROT else [])

# Where each part sits (board frame). The plug is left of centre, clear of the antenna end. Right of
# it, the two ESD arrays take its lines as they leave it: I2C above, CC below. The switch sits at
# the bottom right, by the 3V3 and GND it takes from the 16-pin row and under the D9/D10 pins it
# answers to; the bus links sit right under the 12-pin row's SDA, SCL, D11 and D12.
PLACE = {
    "J1": (14.0, 11.4),
    "U3": (20.0, 14.6), "R1": (23.4, 12.6), "R2": (23.4, 16.6),
    "U4": (20.0, 8.2), "R3": (22.8, 9.3), "R4": (22.8, 7.1), "R5": (25.2, 9.81), "R6": (25.2, 6.59),
    "U2": (34.0, 7.0), "C1": (37.0, 5.0), "C3": (37.2, 3.4), "R7": (36.9, 9.0), "R8": (31.6, 9.0),
    "C2": (31.0, 5.0), "D1": (7.8, 11.4),
    "R9": (44.45, 18.4), "R10": (41.91, 18.4), "R11": (29.21, 18.4), "R12": (26.67, 18.4),
    "J2": (ROW16_AT[0] + 2.54 * 7.5, ROW16_AT[1]), "J3": (ROW12_AT[0] + 2.54 * 5.5, ROW12_AT[1]),
    "TP1": (5.0, 13.4), "TP2": (5.0, 9.4),
}
ROT = {"R1": 270, "R2": 90, "R3": 270, "R4": 90, "R7": 180, "U2": 180, "D1": 90,
       "R9": 270, "R10": 270, "R11": 270, "R12": 270}
for ref, p in PARTS.items():
    p["at"] = PLACE[ref]
    p["rot"] = ROT.get(ref, p.get("rot", 0))
    p["side"] = "F"

uid = gen.uid


def page(x, y):
    return OX + x, OY - y


# =================================================================================================
# Symbols
# =================================================================================================

def header_symbol(name, row):
    n = len(row)
    h = 1.27 * n
    pins = [(str(i), pname, "passive", "R", h - 1.27 - 2.54 * (i - 1)) for i, (pname, _g) in enumerate(row, 1)]
    return gen.box_symbol(name, "J", name, f"{L}:{name.replace('Feather_', 'Feather_Header_')}", "",
                          f"Feather header row, {n} pins at 2.54 mm, Adafruit's order from the USB end", 5.08, h, pins)


def plug_symbol():
    order = ["A4", "A9", "B4", "B9", "A5", "B5", "A6", "A7", "B6", "B7", "A8", "B8", "A1", "A12", "B1", "B12", "SH"]
    pins = [(num, PLUG_NAMES[num], "passive", "R" if k < 12 else "L", 10.16 - 2.54 * k if k < 12 else 10.16 - 2.54 * (k - 12))
            for k, num in enumerate(order)]
    return gen.box_symbol("USB_C_Plug_16P", "J", "USB_C_Plug_16P", f"{L}:USB_C_Plug_918-118A2021Y40002_Vertical", DS["plug"],
                          "USB-C plug, 16 pins, used as plain wires: VBUS, GND, D+, D-, CC, VCONN", 7.62, 12.7, pins)


def switch_symbol():
    pins = [("1", "IN", "power_in", "L", 2.54), ("3", "EN", "input", "L", -2.54),
            ("6", "OUT", "power_out", "R", 2.54), ("4", "~{FAULT}", "open_collector", "R", -2.54),
            ("2", "GND", "power_in", "B", -2.54), ("5", "ILIM", "passive", "B", 2.54)]
    return gen.box_symbol("AP22653", "U", "AP22653", f"{L}:SOT-23-6", DS["switch"],
                          "Diodes AP22653: current-limited high-side switch, reverse blocking, output discharge, active-high EN, SOT-26",
                          7.62, 5.08, pins)


def esd_symbol():
    pins = [("1", "IO1", "passive", "L", 2.54), ("3", "IO2", "passive", "L", -2.54),
            ("6", "IO1", "passive", "R", 2.54), ("4", "IO2", "passive", "R", -2.54),
            ("5", "VBUS", "passive", "T", 0), ("2", "GND", "passive", "B", 0)]
    return gen.box_symbol("USBLC6-2SC6", "U", "USBLC6-2SC6", f"{L}:SOT-23-6", gen.USBLC6_DS,
                          "ST 2-line ESD array with a rail clamp, SOT-23-6. Pins 1/6 and 3/4 are flow-through pairs.",
                          7.62, 5.08, pins)


def two_pin_symbol(name, ref, desc, fp, names=("1", "2")):
    return gen.box_symbol(name, ref, name, f"{L}:{fp}", "", desc, 1.27, 2.54,
                          [("1", names[0], "passive", "T", 0), ("2", names[1], "passive", "B", 0)])


def write_symbols():
    syms = [header_symbol("Feather_1x16", ROW16), header_symbol("Feather_1x12", ROW12), plug_symbol(), switch_symbol(),
            esd_symbol(), two_pin_symbol("R", "R", "Resistor", R0402), two_pin_symbol("C", "C", "Capacitor", C0402),
            two_pin_symbol("D_TVS", "D", "TVS diode: pin 1 cathode", "D_SOD-523", ("K", "A")),
            gen.box_symbol("TestPad", "TP", "TestPad", f"{L}:TestPad_1.5mm", "", "A bare copper pad for a probe",
                           1.27, 1.27, [("1", "1", "passive", "B", 0)]),
            pocket.power_symbol("GND", "power_in", [(0, 0), (0, -1.27), (1.27, -1.27), (0, -2.54), (-1.27, -1.27), (0, -1.27)]),
            pocket.power_symbol("+3V3", "power_in", [(0, 0), (0, 2.54), (-0.762, 1.27), (0, 2.54), (0.762, 1.27)]),
            pocket.power_symbol("PWR_FLAG", "power_out", [(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)])]
    os.makedirs(LIB, exist_ok=True)
    with open(os.path.join(LIB, f"{L}.kicad_sym"), "w") as fh:
        fh.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        fh.write("\n".join(syms))
        fh.write("\n)\n")
    return {re.match(r'\(symbol "([^"]+)"', s).group(1): s for s in syms}


# =================================================================================================
# Schematic: every pin gets a short wire and a net label or a power symbol, as console-pocket's does
# =================================================================================================

class WingSheet(gen.Sheet):
    def power(self, name, x, y, rot=0):
        self.npwr += 1
        ref = f"#FLG0{self.npwr:02d}" if name == "PWR_FLAG" else f"#PWR0{self.npwr:02d}"
        self.symbol(f"{L}:{name}", ref, name, x, y, ["1"], rot=rot)

    def write(self, path, title):
        super().write(path, title)
        s = open(path).read()
        s = s.replace('(comment 1 "The PCB is the plug: see hardware/key-pcb/README.md")', f'(comment 1 "{NOTE}")', 1)
        s = s.replace(f'(date "{gen.DATE}")', f'(date "{DATE}")', 1)
        open(path, "w").write(s)


def write_schematic(syms):
    sh = WingSheet(NAME)
    for name, text in syms.items():
        sh.lib(f"{L}:{name}", text.replace(f'(symbol "{name}"', f'(symbol "{L}:{name}"', 1))
    uids = {}

    def end(px, py, side, net, dx=5.08):
        if net is None or net.startswith("unconnected"):
            sh.nc(px, py)
            return
        ex, ey = {"L": (px - dx, py), "R": (px + dx, py), "T": (px, py - 2.54), "B": (px, py + 2.54)}[side]
        sh.wire(px, py, ex, ey)
        if net == "GND":
            sh.power("GND", ex, ey, rot={"L": 270, "R": 90, "T": 180, "B": 0}[side])
        elif net == "+3V3":
            sh.power("+3V3", ex, ey, rot={"L": 90, "R": 270, "T": 0, "B": 180}[side])
        else:
            sh.label(net.lstrip("/"), ex, ey, left=(side == "L"))

    def part(ref, sym, x, y, w, h, pins):
        """pins: (number, side, offset) as in gen.box_symbol."""
        p = PARTS[ref]
        uids[ref] = sh.symbol(f"{L}:{sym}", ref, p["value"], x, y, [n for n, _s, _o in pins], fp=f"{L}:{p['fp']}",
                              fields=p["fields"], dnp=p["dnp"], in_bom=p["in_bom"], on_board=True, box_h=h)
        for num, side, off in pins:
            end(*pocket.pin_end(x, y, side, off, w, h), side, NETS[ref, num])

    hdr = lambda row: [(str(i), "R", 1.27 * len(row) - 1.27 - 2.54 * (i - 1)) for i in range(1, len(row) + 1)]
    part("J2", "Feather_1x16", 38.1, 76.2, 5.08, 1.27 * 16, hdr(ROW16))
    part("J3", "Feather_1x12", 38.1, 144.78, 5.08, 1.27 * 12, hdr(ROW12))
    sh.text("The Feather's two header rows, Adafruit's order from the USB end.\n"
            "3V3 and GND power the wing; D5, D6, D9, D10 are new pins for the key port;\n"
            "SDA/SCL (GPIO3/4) or D11/D12 carry the key's bus, chosen by R9-R12.", 25.4, 172.72)
    sh.power("GND", 30.48, 30.48)
    sh.wire(30.48, 30.48, 38.1, 30.48)
    sh.power("PWR_FLAG", 38.1, 30.48, rot=180)
    sh.power("+3V3", 30.48, 40.64)
    sh.wire(30.48, 40.64, 38.1, 40.64)
    sh.power("PWR_FLAG", 38.1, 40.64, rot=180)

    order = ["A4", "A9", "B4", "B9", "A5", "B5", "A6", "A7", "B6", "B7", "A8", "B8", "A1", "A12", "B1", "B12", "SH"]
    part("J1", "USB_C_Plug_16P", 109.22, 76.2, 7.62, 12.7,
         [(num, "R" if k < 12 else "L", 10.16 - 2.54 * k if k < 12 else 10.16 - 2.54 * (k - 12)) for k, num in enumerate(order)])
    sh.text("key-c's USB-C socket carries I2C, not USB (hardware/key-pcb/PROPOSALS.md):\n"
            "SDA on D+ (A6), SCL on D- (A7), power on VBUS, a 5.1k Rd on each CC.\n"
            "key-c joins A6/B6 and A7/B7 itself, so B6 and B7 stay open here.", 88.9, 99.06)
    part("U2", "AP22653", 175.26, 50.8, 7.62, 5.08,
         [("1", "L", 2.54), ("3", "L", -2.54), ("6", "R", 2.54), ("4", "R", -2.54), ("2", "B", -2.54), ("5", "B", 2.54)])
    for ref, sym, x, y in (("R7", "R", 152.4, 40.64), ("R8", "R", 203.2, 40.64), ("C1", "C", 152.4, 66.04),
                           ("C3", "C", 160.02, 66.04), ("C2", "C", 200.66, 66.04), ("D1", "D_TVS", 210.82, 66.04),
                           ("R1", "R", 241.3, 50.8), ("R2", "R", 251.46, 50.8), ("R3", "R", 241.3, 76.2),
                           ("R4", "R", 251.46, 76.2), ("R5", "R", 241.3, 96.52), ("R6", "R", 251.46, 96.52),
                           ("R9", "R", 160.02, 152.4), ("R10", "R", 172.72, 152.4), ("R11", "R", 195.58, 152.4),
                           ("R12", "R", 208.28, 152.4)):
        part(ref, sym, x, y, 1.27, 2.54, [("1", "T", 0), ("2", "B", 0)])
    sh.text("The console end of key-c, as console-a has it:\n"
            "- VKEY comes through U2: 80 mA limit, reverse blocking, discharged\n"
            "  when off. Never straight from a GPIO. EN pulled up: on by default.\n"
            "- CC1 and CC2 read on their own ADC1 pins (D5, D6). Plugged straight\n"
            "  in, a key shows 5.1k on both.\n"
            "- 2.2k pull-ups to VKEY, so a key that's off isn't powered through SDA/SCL.\n"
            "- U3/U4 rails on 3V3: the CC pull-ups can't feed VKEY.", 147.32, 106.68)
    for ref, x in (("U3", 175.26), ("U4", 226.06)):
        part(ref, "USBLC6-2SC6", x, 129.54, 7.62, 5.08,
             [("1", "L", 2.54), ("3", "L", -2.54), ("6", "R", 2.54), ("4", "R", -2.54), ("5", "T", 0), ("2", "B", 0)])
    sh.text("Bus links: R9/R10 fitted put the key on the Feather's SDA/SCL, the bus\n"
            "today's console image reads. R11/R12 instead give it a bus of its own on\n"
            "D11/D12, for a later image. Never fit both pairs.", 152.4, 167.64)
    for k, ref in enumerate(("TP1", "TP2")):
        part(ref, "TestPad", 101.6 + 12.7 * k, 152.4, 1.27, 1.27, [("1", "B", 0)])
    os.makedirs(OUT, exist_ok=True)
    sh.write(os.path.join(OUT, NAME + ".kicad_sch"), TITLE)
    return sh.root, uids


# =================================================================================================
# Footprints, in pocket's item format: ("pad", num, kind, shape, x, y, w, h, drill, layers), lines...
# =================================================================================================

def _crtyd(hw, hh):
    return ("rect", -hw, -hh, hw, hh, "F.CrtYd", 0.05, False)


def fp_plug():
    """KiCad's USB_C_Plug_ShenzhenJingTuoJin_918-118A2021Y40002_Vertical, as console-a's board holds
    it: two rows of eight 0.79 x 0.4 pads 2.54 mm apart at a 0.8 mm pitch, and two shell pads."""
    items = []
    for k, num in enumerate(("A1", "A4", "A5", "A6", "A7", "A8", "A9", "A12")):
        items.append(_pad(num, "smd", "roundrect", -1.27, -2.8 + 0.8 * k, 0.79, 0.4))
    for k, num in enumerate(("B12", "B9", "B8", "B7", "B6", "B5", "B4", "B1")):
        items.append(_pad(num, "smd", "roundrect", 1.27, -2.8 + 0.8 * k, 0.79, 0.4))
    items += [_pad("SH", "smd", "roundrect", 0, -3.95, 1.6, 0.65), _pad("SH", "smd", "roundrect", 0, 3.95, 1.6, 0.65)]
    items += [("rect", -1.44, -2.88, 1.44, 2.88, "F.Fab", 0.1, False), _crtyd(2.17, 4.78),
              ("line", -1.74, -3.125, -1.4, -3.125, "F.SilkS", 0.12), ("circle", -2.1, -2.8, 0.15, "F.SilkS", 0.12, True)]
    return dict(items=items, attr="smd", tags="usb c plug vertical",
                descr="Vertical USB-C plug, Shenzhen Jing Tuo Jin 918-118A2021Y40002 (LCSC C399939): KiCad's footprint, pads as console-a's board holds them")


def fp_sot23_6():
    items = [_pad(str(n), "smd", "roundrect", x, y, 1.325, 0.6)
             for n, x, y in ((1, -1.1375, -0.95), (2, -1.1375, 0), (3, -1.1375, 0.95), (4, 1.1375, 0.95), (5, 1.1375, 0), (6, 1.1375, -0.95))]
    items += [("rect", -0.8, -1.45, 0.8, 1.45, "F.Fab", 0.1, False), _crtyd(2.05, 1.75),
              ("line", -0.8, -1.56, 0.8, -1.56, "F.SilkS", 0.12), ("line", -0.8, 1.56, 0.8, 1.56, "F.SilkS", 0.12),
              ("circle", -1.9, -1.6, 0.15, "F.SilkS", 0.12, True)]
    return dict(items=items, attr="smd", tags="sot-23-6", descr="SOT-23-6, KiCad's land pattern: pads 1.325x0.6 at (+-1.1375, -0.95/0/0.95)")


def fp_two(pw, ph, dx, hw, hh, cw, ch, descr, tags, mark=False):
    items = [_pad("1", "smd", "roundrect", -dx, 0, pw, ph), _pad("2", "smd", "roundrect", dx, 0, pw, ph),
             ("rect", -hw, -hh, hw, hh, "F.Fab", 0.1, False), _crtyd(cw, ch)]
    if mark:
        items.append(("line", -cw + 0.1, -ch + 0.1, -cw + 0.1, ch - 0.1, "F.SilkS", 0.12))   # the cathode end
    return dict(items=items, attr="smd", descr=descr, tags=tags)


def fp_header(n):
    items = [_pad(str(i), "thru_hole", "rect" if i == 1 else "circle", 2.54 * (i - 1 - (n - 1) / 2), 0, 1.7, 1.7, 1.0)
             for i in range(1, n + 1)]
    items.append(("rect", -1.27 * n, -1.27, 1.27 * n, 1.27, "F.CrtYd", 0.05, False))
    return dict(items=items, attr="through_hole exclude_from_pos_files",
                descr=f"Feather header row, {n} pins at 2.54 mm, 1.7 mm pads with 1.0 mm holes; pin 1 (square) at the USB end",
                tags="feather header")


def fp_testpad():
    return dict(items=[_pad("1", "smd", "circle", 0, 0, 1.5, 1.5, layers=["F.Cu", "F.Mask"]), ("circle", 0, 0, 1.0, "F.CrtYd", 0.05, False)],
                attr="smd exclude_from_pos_files exclude_from_bom", descr="Test pad: 1.5 mm bare copper, no paste", tags="test pad")


def fp_hole(d):
    return dict(items=[_pad("", "np_thru_hole", "circle", 0, 0, d, d, d), ("circle", 0, 0, d / 2 + 0.25, "F.CrtYd", 0.05, False)],
                attr="through_hole board_only exclude_from_pos_files exclude_from_bom",
                descr=f"{d} mm mounting hole, not plated", tags="mounting hole")


FOOTPRINTS = {
    "USB_C_Plug_918-118A2021Y40002_Vertical": fp_plug, "SOT-23-6": fp_sot23_6,
    "D_SOD-523": lambda: fp_two(0.6, 0.7, 0.7, 0.6, 0.4, 1.25, 0.6, "SOD-523, KiCad's land pattern: pads 0.6x0.7 at +-0.7, pin 1 the cathode", "sod-523", mark=True),
    R0402: lambda: fp_two(0.54, 0.64, 0.51, 0.5, 0.25, 0.93, 0.47, "0402 resistor, KiCad's land pattern: pads 0.54x0.64 at +-0.51", "0402"),
    C0402: lambda: fp_two(0.54, 0.64, 0.51, 0.5, 0.25, 0.93, 0.47, "0402 capacitor, KiCad's land pattern: pads 0.54x0.64 at +-0.51", "0402"),
    C0603: lambda: fp_two(0.9, 0.95, 0.775, 0.8, 0.4, 1.48, 0.73, "0603 capacitor, KiCad's land pattern: pads 0.9x0.95 at +-0.775", "0603"),
    "Feather_Header_1x16": lambda: fp_header(16), "Feather_Header_1x12": lambda: fp_header(12),
    "TestPad_1.5mm": fp_testpad, "MountingHole_2.7mm": lambda: fp_hole(2.7), "MountingHole_2.4mm": lambda: fp_hole(2.4),
}


def ref_y(fp):
    ys = [it[2] for it in fp["items"] if it[0] == "rect" and it[5] == "F.CrtYd"]
    ys += [it[2] - it[3] for it in fp["items"] if it[0] == "circle" and it[4] == "F.CrtYd"]
    return (min(ys) if ys else -1.0) - 0.7


def write_footprints():
    d = os.path.join(LIB, f"{L}.pretty")
    os.makedirs(d, exist_ok=True)
    for name, make in FOOTPRINTS.items():
        fp = make()
        items = [item_text(it) + (f' (uuid "{uid()}"))' if it[0] == "pad" else "") for it in fp["items"]]
        with open(os.path.join(d, name + ".kicad_mod"), "w") as fh:
            fh.write(f'(footprint "{name}" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")\n'
                     f'\t(descr "{fp["descr"]}")\n\t(tags "{fp["tags"]}")\n'
                     + _prop("Reference", "REF**", 0, ref_y(fp), "F.SilkS", size=0.8) + "\n"
                     + _prop("Value", name, 0, -ref_y(fp), "F.Fab") + "\n"
                     + _prop("Datasheet", "", 0, 0, "F.Fab", hide=True) + "\n"
                     + _prop("Description", "", 0, 0, "F.Fab", hide=True) + "\n"
                     + f'\t(attr {fp["attr"]})\n' + "\n".join(items) + "\n\t(embedded_fonts no)\n)\n")
    md = os.path.join(LIB, "picoquorum.pretty")
    os.makedirs(md, exist_ok=True)
    shutil.copy(os.path.join(REPO, "hardware", "key-pcb", "lib", "picoquorum.pretty", "PicoQuorum_Mark.kicad_mod"), md)


# =================================================================================================
# Geometry shared by the router, the board writer and the self-check (page coordinates)
# =================================================================================================

def all_parts():
    parts = dict(PARTS)
    for ref, at, d in HOLES:
        parts[ref] = dict(fp=f"MountingHole_{d}mm", at=at, rot=0, side="F", value=f"M{2.5 if d > 2.5 else 2}", fields=[])
    return parts


def pad_rects():
    """Every pad: ref, num, net, copper layers, rect (page mm), centre, kind. Rotations are multiples
    of 90, so pads stay axis-aligned."""
    out = []
    for ref, p in all_parts().items():
        fp = FOOTPRINTS[p["fp"]]()
        px, py = page(*p["at"])
        for it in fp["items"]:
            if it[0] != "pad":
                continue
            _, num, kind, _shape, lx, ly, w, h, drill, layers = it
            dx, dy = rotate(lx, ly, p["rot"])
            cx, cy = px + dx, py + dy
            if round(p["rot"]) % 180:
                w, h = h, w
            lays = {"F.Cu", "B.Cu"} if kind != "smd" else {l for l in layers if l.endswith(".Cu")}
            out.append(dict(ref=ref, num=num, net=NETS.get((ref, num)) if num else None, layers=lays, kind=kind,
                            rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), centre=(cx, cy), key=(ref, num, len(out))))
    return out


def plug_rect():
    """The plug's courtyard, page mm: its footprint's +-2.17 x +-4.78, turned with it."""
    px, py = page(*PARTS["J1"]["at"])
    hw, hh = (4.78, 2.17) if round(PARTS["J1"]["rot"]) % 180 else (2.17, 4.78)
    return (px - hw, py - hh, px + hw, py + hh)


def plug_body():
    """The board between the plug's two pad rows, page mm."""
    px, py = page(*PARTS["J1"]["at"])
    a, b = 1.27 - 0.395 - 0.25, 3.2      # the rows' inner edges, less a track's clearance; the rows' length
    return (px - b, py - a, px + b, py + a) if round(PARTS["J1"]["rot"]) % 180 else (px - a, py - b, px + a, py + b)


def antenna_side():
    """Beside the antenna, below the bus links: the router keeps out of it (page mm)."""
    return (OX + ANTENNA_SIDE_X, OY - 17.0, OX + KEEPOUT_X, OY)


def board_rect():
    return (OX, OY - H, OX + W, OY)


def keepout_rect():
    return (OX + KEEPOUT_X, OY - H, OX + W, OY)


def edge_ok(rect, margin):
    """The rect stays margin inside the outline, rounded corners included."""
    x0, y0, x1, y1 = rect
    bx0, by0, bx1, by1 = board_rect()
    if x0 < bx0 + margin or y0 < by0 + margin or x1 > bx1 - margin or y1 > by1 - margin:
        return False
    for cx, cy in ((bx0 + CORNER, by0 + CORNER), (bx1 - CORNER, by0 + CORNER), (bx0 + CORNER, by1 - CORNER), (bx1 - CORNER, by1 - CORNER)):
        for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            if (px - cx) * (cx - (bx0 + bx1) / 2) > 0 and (py - cy) * (cy - (by0 + by1) / 2) > 0:
                if math.hypot(px - cx, py - cy) > CORNER - margin:
                    return False
    return True


# =================================================================================================
# Routing: a grid router that checks every step against the copper already there, by geometry
# =================================================================================================
STEP = 0.2
LAYERS = ("F.Cu", "B.Cu")
VIA_COST, TURN_COST = 12, 1.5
F_COST = 1.3          # the front carries the parts and its pour: long runs go on the back


class Router:
    def __init__(self, pads):
        self.nx, self.ny = int(round(W / STEP)) + 1, int(round(H / STEP)) + 1
        self.obs = []                   # dict(net, layers, rect, hole)
        self.buckets = {}               # (bx, by) -> obstacle indices, 1 mm buckets
        self.segments, self.vias = [], []
        self.cells = {}                 # net -> {(layer, i, j)} already copper of that net, joined
        self.island = {}                # pad key -> its fan-out's cells, not yet joined to the rest
        self.cache = {}
        self.pads = pads
        for p in pads:
            hole = p["kind"] == "np_thru_hole"
            self.add(p["net"] if p["net"] and not p["net"].startswith("unconnected") else ("*" if hole else f"pad:{p['ref']}.{p['num']}"),
                     p["layers"], p["rect"], hole=hole)
        self.smd = [p["rect"] for p in pads if p["kind"] == "smd"]
        # Under the plug: no via anywhere in its courtyard, and no front copper between its pad rows,
        # where its shell sits on the board. Its pads leave outward.
        x0, y0, x1, y1 = plug_rect()
        self.smd.append((x0 + 0.15, y0 + 0.15, x1 - 0.15, y1 - 0.15))
        self.add("*", {"F.Cu"}, plug_body())
        self.pad_cells = {}
        for p in pads:
            if p["kind"] == "np_thru_hole" or not p["net"] or p["net"].startswith("unconnected"):
                continue
            x0, y0, x1, y1 = p["rect"]
            cells = set()
            for layer in p["layers"]:
                for i, j in self.cells_in((x0 + 0.01, y0 + 0.01, x1 - 0.01, y1 - 0.01)):
                    if self.node_ok(layer, i, j, p["net"]):
                        cells.add((layer, i, j))
            self.pad_cells[p["key"]] = cells

    def add(self, net, layers, rect, hole=False):
        k = len(self.obs)
        self.obs.append(dict(net=net, layers=set(layers), rect=rect, hole=hole))
        x0, y0, x1, y1 = rect
        for bx in range(int(math.floor(x0 - 1)), int(math.floor(x1 + 1)) + 1):
            for by in range(int(math.floor(y0 - 1)), int(math.floor(y1 + 1)) + 1):
                self.buckets.setdefault((bx, by), []).append(k)
        self.cache.clear()

    def xy(self, i, j):
        return OX + i * STEP, OY - H + j * STEP

    def cells_in(self, rect):
        x0, y0, x1, y1 = rect
        for i in range(max(0, int(math.ceil((x0 - OX) / STEP - 1e-9))), min(self.nx, int(math.floor((x1 - OX) / STEP + 1e-9)) + 1)):
            for j in range(max(0, int(math.ceil((y0 - OY + H) / STEP - 1e-9))), min(self.ny, int(math.floor((y1 - OY + H) / STEP + 1e-9)) + 1)):
                yield i, j

    def rect_ok(self, rect, layers, net, via=False):
        x0, y0, x1, y1 = rect
        if not edge_ok(rect, EDGE):
            return False
        if _gap(rect, keepout_rect()) < 0.05 or _gap(rect, antenna_side()) < 0.05:
            return False
        seen = set()
        for bx in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
            for by in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
                for k in self.buckets.get((bx, by), ()):
                    if k in seen:
                        continue
                    seen.add(k)
                    o = self.obs[k]
                    if not (o["layers"] & layers):
                        continue
                    if o["net"] == net and not o["hole"]:
                        continue
                    need = (0.5 if via else HOLE_CLEAR) if o["hole"] else CLEAR + 0.02
                    if _gap(rect, o["rect"]) < need:
                        return False
        if via:
            for r in self.smd:        # no via in or against any SMD pad, whatever its net
                if _gap(rect, r) < 0.15:
                    return False
        return True

    def node_ok(self, layer, i, j, net):
        key = ("n", layer, i, j, net)
        if key not in self.cache:
            x, y = self.xy(i, j)
            t = TRACK / 2
            self.cache[key] = self.rect_ok((x - t, y - t, x + t, y + t), {layer}, net)
        return self.cache[key]

    def step_ok(self, layer, a, b, net):
        key = ("s", layer, min(a, b), max(a, b), net)
        if key not in self.cache:
            (xa, ya), (xb, yb) = self.xy(*a), self.xy(*b)
            t = TRACK / 2
            self.cache[key] = self.rect_ok((min(xa, xb) - t, min(ya, yb) - t, max(xa, xb) + t, max(ya, yb) + t), {layer}, net)
        return self.cache[key]

    def via_ok(self, i, j, net):
        key = ("v", i, j, net)
        if key not in self.cache:
            x, y = self.xy(i, j)
            v = VIA / 2
            self.cache[key] = self.rect_ok((x - v, y - v, x + v, y + v), set(LAYERS), net, via=True)
        return self.cache[key]

    def search(self, net, sources, targets, single_layer=False, limit=None):
        """Dijkstra over (layer, cell). targets: a dict of cells, or a function of a node."""
        hit = targets if callable(targets) else targets.__contains__
        dist, prev, heap = {}, {}, []
        for s in sources:
            dist[s] = 0
            heapq.heappush(heap, (0, s))
        while heap:
            d, node = heapq.heappop(heap)
            if d > dist.get(node, 1e18):
                continue
            if limit is not None and d > limit:
                return None
            if hit(node):
                path = [node]
                while path[-1] in prev:
                    path.append(prev[path[-1]])
                return path[::-1]
            l, i, j = node
            came = prev.get(node)
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = i + di, j + dj
                if not (0 <= ni < self.nx and 0 <= nj < self.ny):
                    continue
                if not self.node_ok(l, ni, nj, net) or not self.step_ok(l, (i, j), (ni, nj), net):
                    continue
                c = 1.0 if l == "B.Cu" else F_COST
                if came is not None and came[0] == l and (i - came[1], j - came[2]) != (di, dj):
                    c += TURN_COST
                nn = (l, ni, nj)
                if d + c < dist.get(nn, 1e18):
                    dist[nn], prev[nn] = d + c, node
                    heapq.heappush(heap, (d + c, nn))
            other = "B.Cu" if l == "F.Cu" else "F.Cu"
            nn = (other, i, j)
            if not single_layer and nn not in dist and self.node_ok(other, i, j, net) and self.via_ok(i, j, net):
                if d + VIA_COST < dist.get(nn, 1e18):
                    dist[nn], prev[nn] = d + VIA_COST, node
                    heapq.heappush(heap, (d + VIA_COST, nn))
        return None

    def fanout(self, pads):
        """Each of the plug's signal pins straight out to a via of its own, just past the plug's
        courtyard: the 0.8 mm pitch leaves no room to do it later, between other nets' tracks."""
        cx = sum(p["centre"][0] for p in pads) / len(pads)
        for p in sorted(pads, key=lambda p: abs(p["centre"][0] - cx)):
            net = p["net"]
            path = self.search(net, self.pad_cells[p["key"]], lambda n: self.node_ok("B.Cu", n[1], n[2], net) and self.via_ok(n[1], n[2], net),
                               single_layer=True, limit=3.0 / STEP)
            if path is None:
                continue
            self.commit(net, path)
            l, i, j = path[-1]
            self.add_via(net, i, j)
            self.island[p["key"]] = set(path) | self.pad_cells[p["key"]] | {("F.Cu", i, j), ("B.Cu", i, j)}

    def route_net(self, net, pads):
        """Join the pads of one net: from what is joined so far to the nearest pad (or its fan-out)
        not yet reached, until none is left. Returns the pads it couldn't reach."""
        reach = lambda p: self.island.get(p["key"], self.pad_cells[p["key"]])
        todo = list(pads)
        sources = set(reach(todo.pop(0)))
        failed = []
        while todo:
            targets = {c: p["key"] for p in todo for c in reach(p)}
            path = self.search(net, sources, targets) if targets else None
            if path is None:
                failed += [(net, p["ref"], p["num"]) for p in todo]
                break
            hit = targets[path[-1]]
            todo = [p for p in todo if p["key"] != hit]
            self.commit(net, path)
            sources |= set(path) | reach(next(p for p in pads if p["key"] == hit))
        self.cells.setdefault(net, set()).update(sources)
        return failed

    def commit(self, net, path):
        run = [path[0]]
        for node in path[1:]:
            if node[0] != run[-1][0]:
                self.flush(net, run)
                self.add_via(net, node[1], node[2])
                run = [node]
            else:
                run.append(node)
        self.flush(net, run)

    def flush(self, net, run):
        if len(run) < 2:
            return
        layer = run[0][0]
        pts = [self.xy(n[1], n[2]) for n in run]
        merged = [pts[0]]
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            if not ((abs(a[0] - b[0]) < 1e-9 and abs(b[0] - c[0]) < 1e-9) or (abs(a[1] - b[1]) < 1e-9 and abs(b[1] - c[1]) < 1e-9)):
                merged.append(b)
        merged.append(pts[-1])
        t = TRACK / 2
        for (ax, ay), (bx, by) in zip(merged, merged[1:]):
            self.segments.append((net, layer, TRACK, (ax, ay), (bx, by)))
            self.add(net, {layer}, (min(ax, bx) - t, min(ay, by) - t, max(ax, bx) + t, max(ay, by) + t))

    def add_via(self, net, i, j):
        x, y = self.xy(i, j)
        self.vias.append((net, x, y))
        v = VIA / 2
        self.add(net, set(LAYERS), (x - v, y - v, x + v, y + v))
        self.cells.setdefault(net, set()).update({("F.Cu", i, j), ("B.Cu", i, j)})

    def gnd_vias(self):
        """A via for every front GND pad, reached by the shortest front track that finds room for
        one, so each pad meets the back pour even where the front fill around it is thin. The plug's
        four ground pins join its shell pads instead, outward, which leaves the room above and below
        its rows to the pins between them; the shell pads get the vias."""
        n = 0
        shell = [p for p in self.pads if p["ref"] == "J1" and p["num"] == "SH"]
        rest = [p for p in self.pads if p["net"] == "GND" and p["kind"] == "smd" and p not in shell]
        for p in shell + rest:
            cells = self.pad_cells[p["key"]]
            cx, cy = p["centre"]
            gnd = self.cells.get("GND", set())
            if p["ref"] == "J1" and p["num"] != "SH":
                near = min(shell, key=lambda q: abs(q["centre"][0] - cx))
                path = self.search("GND", cells, set(self.pad_cells[near["key"]]), single_layer=True, limit=4.0 / STEP)
                if path is not None:
                    self.commit("GND", path)
                    self.cells.setdefault("GND", set()).update(path)
                    continue

            def goal(node):
                l, i, j = node
                x, y = self.xy(i, j)
                if ("B.Cu", i, j) in gnd:           # a ground via already there
                    return True
                return (math.hypot(x - cx, y - cy) > 0.5 and self.node_ok("B.Cu", i, j, "GND") and self.via_ok(i, j, "GND"))
            path = self.search("GND", cells, goal, single_layer=True, limit=4.0 / STEP)
            if path is None:
                continue
            self.commit("GND", path)
            l, i, j = path[-1]
            if ("B.Cu", i, j) not in gnd:
                self.add_via("GND", i, j)
                n += 1
            self.cells.setdefault("GND", set()).update(path)
        return n

    def stitch(self):
        """Stitching vias on a 4 mm grid, wherever no other net's copper is within 1 mm."""
        n = 0
        for x in range(2, int(POUR_X), 4):
            for y in (4.0, 8.0, 12.0, 16.0, 19.0):
                i, j = int(round(x / STEP)), int(round((H - y) / STEP))
                if self.via_ok(i, j, "GND") and self.node_ok("F.Cu", i, j, "GND") and self.node_ok("B.Cu", i, j, "GND"):
                    # only where both pours are free around it: no other net's copper within 1 mm
                    vx, vy = self.xy(i, j)
                    if self.rect_ok((vx - 1.0, vy - 1.0, vx + 1.0, vy + 1.0), set(LAYERS), "GND"):
                        self.add_via("GND", i, j)
                        n += 1
        return n


# Nets in the order they are routed: the plug's fine-pitch pads first, then the power, and the long,
# roomy ones last.
ORDER = ["/KEY_SDA", "/KEY_SCL", "/CC1", "/CC2", "/VKEY", "+3V3", "/CC1_SENSE", "/CC2_SENSE", "/KEY_EN", "/KEY_FAULT",
         "/FTHR_SDA", "/FTHR_SCL", "/ALT_SDA", "/ALT_SCL"]


def route(pads):
    """Route the nets in several orders and keep the complete result with the least copper: ORDER
    first, then each failure's nets moved to the front, then a few fixed shuffles. The same orders
    every run, so the same board."""
    by_net = {}
    for p in pads:
        if p["net"] and not p["net"].startswith("unconnected") and p["net"] != "GND":
            by_net.setdefault(p["net"], []).append(p)
    assert set(by_net) == set(ORDER), sorted(set(by_net) ^ set(ORDER))
    rng = random.Random(608)
    queue, best = [list(ORDER)], None
    for attempt in range(16):
        order = queue.pop(0) if queue else rng.sample(ORDER, len(ORDER))
        r = Router(pads)
        r.gnd_vias()        # first, so every ground pad keeps its way down to the back pour
        r.fanout([p for p in pads if p["ref"] == "J1" and p["net"] in by_net])
        failed = []
        for net in order:
            ps = sorted(by_net[net], key=lambda p: (p["ref"] != "J1", p["ref"], p["num"]))
            failed += r.route_net(net, ps)
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for _n, _l, _w, a, b in r.segments)
        cost = length + 2.0 * len(r.vias)
        bad = list(dict.fromkeys(n for n, _r, _p in failed))
        print(f"  attempt {attempt + 1}: " + (f"{', '.join(bad)} unfinished" if bad else f"{length:.0f} mm of track, {len(r.vias)} vias"))
        if bad and attempt < 3:
            queue.append(bad + [n for n in order if n not in bad])
        if best is None or (len(failed), cost) < (len(best[1]), best[2]):
            best = (r, failed, cost, order)
    r, failed, _cost, order = best
    r.stitch()
    print(f"  kept the order {', '.join(n.lstrip('/') for n in order)}")
    return r, failed


# =================================================================================================
# The board file
# =================================================================================================

def _template_blocks():
    """The (layers) and (setup) blocks as KiCad 9 wrote them for key-b, with this board's stackup and
    drill/place origin: pocket's, pointed at this board's origin."""
    src = open(os.path.join(REPO, "hardware", "key-pcb", "key-b-udfn", "key-b-udfn.kicad_pcb")).read()

    def balanced(text, start):
        k, d = text.index("(", start), 0
        while True:
            d += {"(": 1, ")": -1}.get(text[k], 0)
            k += 1
            if d == 0:
                return k

    def block(key):
        i = src.index(f"\n\t({key}") + 1
        return src[i:balanced(src, i)]
    layers, setup = block("layers"), block("setup")
    i = setup.index("\t\t(stackup")
    setup = setup[:i] + gen_cd.STACKUP.format(finish="HASL(with lead-free)").rstrip("\n") + setup[balanced(setup, i):]
    setup = re.sub(r"\(aux_axis_origin [^)]*\)", f"(aux_axis_origin {f(OX)} {f(OY)})", setup)
    return layers, setup


def footprint_text(ref, p, nets, path_uuid):
    fp = FOOTPRINTS[p["fp"]]()
    px, py = page(*p["at"])
    rot = p["rot"]
    ry = ref_y(fp)
    lines = [f'\t(footprint "{L}:{p["fp"]}" (layer "F.Cu") (uuid "{uid()}") (at {f(px)} {f(py)}{" " + f(rot) if rot else ""})',
             f'\t\t(descr "{fp["descr"]}")', f'\t\t(tags "{fp["tags"]}")']
    hide_ref = ref[0] == "H" or ref.startswith("J") or ref.startswith("TP")
    lines.append(_prop("Reference", ref, 0, ry, "F.Fab", hide=hide_ref, size=0.8).replace("\t(", "\t\t(", 1))
    lines.append(_prop("Value", p["value"], 0, -ry, "F.Fab").replace("\t(", "\t\t(", 1))
    fields = dict(p.get("fields", []))
    lines.append(_prop("Datasheet", fields.pop("Datasheet", ""), 0, 0, "F.Fab", hide=True).replace("\t(", "\t\t(", 1))
    lines.append(_prop("Description", fields.pop("Description", ""), 0, 0, "F.Fab", hide=True).replace("\t(", "\t\t(", 1))
    for k, v in fields.items():
        lines.append(_prop(k, v, 0, 0, "F.Fab", hide=True).replace("\t(", "\t\t(", 1))
    if path_uuid:
        lines += [f'\t\t(path "/{path_uuid}")', '\t\t(sheetname "/")', f'\t\t(sheetfile "{NAME}.kicad_sch")']
    lines.append(f'\t\t(attr {fp["attr"]}{" dnp" if p.get("dnp") else ""})')
    for it in fp["items"]:
        t = item_text(it, rot=rot, indent="\t\t")
        if it[0] == "pad":
            net = NETS.get((ref, it[1])) if it[1] else None
            if net:
                t += f' (net {nets[net]} "{net}")'
            t += f' (uuid "{uid()}"))'
        lines.append(t)
    lines += ["\t\t(embedded_fonts no)", "\t)"]
    return "\n".join(lines)


def mark_text(x, y):
    src = open(os.path.join(LIB, "picoquorum.pretty", "PicoQuorum_Mark.kicad_mod")).read()
    body = src[src.index("\n(fp_poly"):src.rindex("\n(embedded_fonts")]
    px, py = page(x, y)
    return (f'\t(footprint "picoquorum:PicoQuorum_Mark" (layer "F.Cu") (uuid "{uid()}") (at {f(px)} {f(py)})\n'
            f'\t\t(descr "The PicoQuorum mark, one colour, for silkscreen: docs/BRAND.md")\n\t\t(tags "logo")\n'
            + _prop("Reference", "LOGO1", 0, -4, "F.SilkS", hide=True).replace("\t(", "\t\t(", 1) + "\n"
            + _prop("Value", "PicoQuorum_Mark", 0, 4, "F.Fab", hide=True).replace("\t(", "\t\t(", 1) + "\n"
            + "\t\t(attr board_only exclude_from_pos_files exclude_from_bom allow_missing_courtyard)\n"
            + body.strip("\n").replace("\n(", "\n\t\t(").replace("(fp_", "\t\t(fp_", 1) + "\n\t\t(embedded_fonts no)\n\t)")


def gr_text(s, x, y, layer, size=1.0, rot=0):
    px, py = page(x, y)
    j = " (justify mirror)" if layer.startswith("B.") else ""
    return (f'\t(gr_text "{s}" (at {f(px)} {f(py)}{" " + f(rot) if rot else ""}) (layer "{layer}") (uuid "{uid()}") '
            f'(effects (font (size {f(size)} {f(size)}) (thickness {f(0.15 if size >= 1 else 0.12)})){j}))')


def outline_text():
    x0, y0, x1, y1 = board_rect()
    r, c = CORNER, CORNER * (1 - math.sqrt(0.5))
    E = '(stroke (width 0.1) (type default)) (layer "Edge.Cuts")'
    return "\n".join([
        f'\t(gr_line (start {f(x0 + r)} {f(y0)}) (end {f(x1 - r)} {f(y0)}) {E} (uuid "{uid()}"))',
        f'\t(gr_line (start {f(x1)} {f(y0 + r)}) (end {f(x1)} {f(y1 - r)}) {E} (uuid "{uid()}"))',
        f'\t(gr_line (start {f(x1 - r)} {f(y1)}) (end {f(x0 + r)} {f(y1)}) {E} (uuid "{uid()}"))',
        f'\t(gr_line (start {f(x0)} {f(y1 - r)}) (end {f(x0)} {f(y0 + r)}) {E} (uuid "{uid()}"))',
        f'\t(gr_arc (start {f(x0)} {f(y0 + r)}) (mid {f(x0 + c)} {f(y0 + c)}) (end {f(x0 + r)} {f(y0)}) {E} (uuid "{uid()}"))',
        f'\t(gr_arc (start {f(x1 - r)} {f(y0)}) (mid {f(x1 - c)} {f(y0 + c)}) (end {f(x1)} {f(y0 + r)}) {E} (uuid "{uid()}"))',
        f'\t(gr_arc (start {f(x1)} {f(y1 - r)}) (mid {f(x1 - c)} {f(y1 - c)}) (end {f(x1 - r)} {f(y1)}) {E} (uuid "{uid()}"))',
        f'\t(gr_arc (start {f(x0 + r)} {f(y1)}) (mid {f(x0 + c)} {f(y1 - c)}) (end {f(x0)} {f(y1 - r)}) {E} (uuid "{uid()}"))'])


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
            f'\t\t(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed))\n'
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
        out.append(footprint_text(ref, p, nets, uids[ref]))
    for ref, p in all_parts().items():
        if ref not in PARTS:
            out.append(footprint_text(ref, p, nets, None))
    out.append(mark_text(48.2, 11.43))
    out.append(outline_text())
    # silkscreen, front: the key port, the header pins the wing uses, the links, the test pads
    out.append(gr_text("KEY", PLACE["J1"][0], PLACE["J1"][1] + 4.8, "F.SilkS", 1.0))
    for name, label in (("D10", "FLT"), ("D9", "EN"), ("D6", "CC2"), ("D5", "CC1")):
        i = [n for n, _g in ROW12].index(name)
        out.append(gr_text(label, ROW12_AT[0] + 2.54 * i, 19.0, "F.SilkS", 0.8, rot=90))
    out.append(gr_text("3V3", ROW16_AT[0] + 2.54, 4.0, "F.SilkS", 0.8, rot=90))
    out.append(gr_text("GND", ROW16_AT[0] + 2.54 * 3, 4.0, "F.SilkS", 0.8, rot=90))
    for ref in ("TP1", "TP2"):
        x, y = PLACE[ref]
        out.append(gr_text(PARTS[ref]["value"], x, y + 1.6, "F.SilkS", 0.8))
    out.append(gr_text("USB", 1.2, 11.43, "F.SilkS", 0.8, rot=90))
    out.append(gr_text(f"wing-a {DATE[:7]}", 20.0, 3.4, "F.SilkS", 0.8))
    # back: what this side is, and the source
    out.append(gr_text("PicoQuorum key wing", 25.0, 15.4, "B.SilkS", 1.0))
    out.append(gr_text("FeatherWing-compatible", 25.0, 13.6, "B.SilkS", 0.8))
    out.append(gr_text("this side faces the Feather", 25.0, 11.8, "B.SilkS", 0.8))
    out.append(gr_text(SRC, 25.0, 9.6, "B.SilkS", 0.8))
    out.append(gr_text("CERN-OHL-W-2.0", 25.0, 7.8, "B.SilkS", 0.8))
    for net, layer, width, (ax, ay), (bx, by) in router.segments:
        out.append(f'\t(segment (start {f(ax)} {f(ay)}) (end {f(bx)} {f(by)}) (width {f(width)}) (layer "{layer}") (net {nets[net]}) (uuid "{uid()}"))')
    for net, x, y in router.vias:
        out.append(f'\t(via (at {f(x)} {f(y)}) (size {f(VIA)}) (drill {f(DRILL)}) (layers "F.Cu" "B.Cu") (net {nets[net]}) (uuid "{uid()}"))')
    x0, y0, x1, y1 = board_rect()
    pour = [(x0 - 1, y0 - 1), (OX + POUR_X, y0 - 1), (OX + POUR_X, y1 + 1), (x0 - 1, y1 + 1)]
    out.append(zone_text(nets["GND"], "GND", "F.Cu", "GND front", pour))
    out.append(zone_text(nets["GND"], "GND", "B.Cu", "GND back", pour))
    kx0, ky0, kx1, ky1 = keepout_rect()
    out.append(keepout_text([(kx0, ky0 - 1), (kx1 + 1, ky0 - 1), (kx1 + 1, ky1 + 1), (kx0, ky1 + 1)]))
    out += ["\t(embedded_fonts no)", ")"]
    with open(os.path.join(OUT, NAME + ".kicad_pcb"), "w") as fh:
        fh.write("\n".join(out) + "\n")


def write_project(sheet_uuid):
    d = json.load(open(os.path.join(REPO, "hardware", "key-pcb", "key-b-udfn", "key-b-udfn.kicad_pro")))
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
                 f'(options "")(descr "PicoQuorum key wing parts"))\n)\n')
    with open(os.path.join(OUT, "fp-lib-table"), "w") as fh:
        fh.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{L}")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/{L}.pretty")'
                 f'(options "")(descr "PicoQuorum key wing footprints"))\n'
                 f'  (lib (name "picoquorum")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/picoquorum.pretty")'
                 f'(options "")(descr "The PicoQuorum mark"))\n)\n')


# =================================================================================================
# Self-checks: read the written schematic and board back, as KiCad will
# =================================================================================================

def check_schematic(path):
    """Every symbol pin's net, worked out from the schematic's wires, labels, power symbols and
    no-connect flags, against NETS. A stand-in for ERC and schematic parity, not either."""
    tree = gen_cd._sexpr(open(path).read())
    kids = gen_cd._kids
    lib = {}
    for sym in kids(kids(tree, "lib_symbols")[0], "symbol"):
        pins = {}
        for unit in kids(sym, "symbol"):
            for pin in kids(unit, "pin"):
                at = gen_cd._kids(pin, "at")[0]
                pins[gen_cd._kids(pin, "number")[0][1]] = (float(at[1]), float(at[2]))
        lib[sym[1]] = pins
    key = lambda x, y: (round(x, 2), round(y, 2))
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for w in kids(tree, "wire"):
        a, b = kids(kids(w, "pts")[0], "xy")
        parent[find(key(float(a[1]), float(a[2])))] = find(key(float(b[1]), float(b[2])))
    names = {}
    for lab in kids(tree, "label"):
        at = kids(lab, "at")[0]
        names[find(key(float(at[1]), float(at[2])))] = "/" + lab[1]
    ncs = {key(float(kids(n, "at")[0][1]), float(kids(n, "at")[0][2])) for n in kids(tree, "no_connect")}
    pins = []
    for sym in kids(tree, "symbol"):
        lib_id = kids(sym, "lib_id")[0][1]
        at = kids(sym, "at")[0]
        x, y = float(at[1]), float(at[2])
        ref = next(p[2] for p in kids(sym, "property") if p[1] == "Reference")
        if ref.startswith("#"):
            if not ref.startswith("#FLG"):
                names[find(key(x, y))] = lib_id.split(":")[1]
            continue
        for num, (px, py) in lib[lib_id].items():
            pins.append((ref, num, key(x + px, y - py)))
    problems = []
    for ref, num, pt in pins:
        want = NETS.get((ref, num))
        if pt in ncs:
            got = want if want and want.startswith("unconnected") else "a no-connect flag"
        else:
            got = names.get(find(pt))
        if got != want:
            problems.append(f"schematic: {ref}.{num} is on {got}, NETS says {want}")
    missing = set(NETS) - {(r, n) for r, n, _p in pins}
    problems += [f"schematic: no pin {r}.{n}" for r, n in sorted(missing)]
    print(f"{NAME}: schematic {len(pins)} pins, " + (f"{len(problems)} problem(s)" if problems else "every pin on its net in NETS"))
    for p in problems[:30]:
        print("   -", p)
    return not problems


# =================================================================================================
# The board, read back
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
        for pad in kids(fp, "pad"):
            pat, size = node(pad, "at"), node(pad, "size")
            w, h = float(size[1]), float(size[2])
            if round(rot) % 180:
                w, h = h, w
            dx, dy = rotate(float(pat[1]), float(pat[2]), rot)
            cx, cy = px + dx, py + dy
            lays = {l for l in node(pad, "layers")[1:] if l.endswith(".Cu")}
            if "*.Cu" in lays:
                lays = {"F.Cu", "B.Cu"}
            netv = node(pad, "net")
            pads.append(dict(ref=ref, num=pad[1], kind=pad[2], net=netv[2] if netv else None, layers=lays,
                             rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), centre=(cx, cy)))
    for s in kids(tree, "segment"):
        a, b, w = node(s, "start"), node(s, "end"), float(node(s, "width")[1])
        ax, ay, bx, by = float(a[1]), float(a[2]), float(b[1]), float(b[2])
        segs.append(dict(net=nets[int(node(s, "net")[1])], layer=node(s, "layer")[1], a=(ax, ay), b=(bx, by),
                         rect=(min(ax, bx) - w / 2, min(ay, by) - w / 2, max(ax, bx) + w / 2, max(ay, by) + w / 2)))
    for v in kids(tree, "via"):
        at = node(v, "at")
        x, y, d = float(at[1]), float(at[2]), float(node(v, "size")[1])
        vias.append(dict(net=nets[int(node(v, "net")[1])], at=(x, y), rect=(x - d / 2, y - d / 2, x + d / 2, y + d / 2)))
    problems = []
    # 1. clearance between copper of different nets, and copper to the plain holes
    items = [(p["kind"], p["net"], p["layers"], p["rect"], f'{p["ref"]}.{p["num"] or "-"}') for p in pads]
    items += [("seg", s["net"], {s["layer"]}, s["rect"], f'track {s["net"]}') for s in segs]
    items += [("via", v["net"], {"F.Cu", "B.Cu"}, v["rect"], f'via {v["net"]}') for v in vias]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if not (a[2] & b[2]):
                continue
            hole = "np_thru_hole" in (a[0], b[0])
            if not hole and a[1] is not None and a[1] == b[1]:
                continue
            need = (0.5 if "via" in (a[0], b[0]) else 0.25) if hole else CLEAR
            if hole and "np_thru_hole" == a[0] == b[0]:
                continue
            g = _gap(a[3], b[3])
            if g < need - 1e-6:
                problems.append(f"clearance {g:.3f} mm between {a[4]} and {b[4]} (needs {need})")
    # 2. copper to the edge, and no copper behind the antenna but the header pads
    for kind, net, _l, rect, name in items:
        if kind != "np_thru_hole" and not edge_ok(rect, EDGE - 1e-6):
            problems.append(f"{name} within {EDGE} mm of the edge")
        if _gap(rect, keepout_rect()) < 1e-6 and not (name.startswith("J2.") or name.startswith("J3.") or kind == "np_thru_hole"):
            problems.append(f"{name} in the antenna keep-out")
    # 3. a track end or a via inside a pad of another net is a short
    for s in segs:
        for p in pads:
            if s["layer"] in p["layers"] and p["net"] != s["net"] and p["kind"] != "np_thru_hole":
                for pt in (s["a"], s["b"]):
                    if p["rect"][0] <= pt[0] <= p["rect"][2] and p["rect"][1] <= pt[1] <= p["rect"][3]:
                        problems.append(f'track {s["net"]} ends inside {p["ref"]}.{p["num"]}')
    for v in vias:
        for p in pads:
            if p["kind"] == "smd" and _gap(v["rect"], p["rect"]) < 1e-6:
                problems.append(f'via {v["net"]} in pad {p["ref"]}.{p["num"]}')
    # 4. connectivity, by union-find over pads, tracks and vias (GND also joins through the pours)
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def inside(pt, rect):
        return rect[0] - 1e-6 <= pt[0] <= rect[2] + 1e-6 and rect[1] - 1e-6 <= pt[1] <= rect[3] + 1e-6

    for i, s in enumerate(segs):
        for j, p in enumerate(pads):
            if s["layer"] in p["layers"] and p["net"] == s["net"] and (inside(s["a"], p["rect"]) or inside(s["b"], p["rect"])):
                parent[find(("s", i))] = find(("p", j))
        for k, t in enumerate(segs):
            if k > i and t["layer"] == s["layer"] and t["net"] == s["net"] and (
                    any(inside(pt, t["rect"]) for pt in (s["a"], s["b"])) or any(inside(pt, s["rect"]) for pt in (t["a"], t["b"]))):
                parent[find(("s", i))] = find(("s", k))
        for m, v in enumerate(vias):
            if v["net"] == s["net"] and inside(v["at"], s["rect"]):
                parent[find(("s", i))] = find(("v", m))
    for m, v in enumerate(vias):
        for j, p in enumerate(pads):
            if p["kind"] == "thru_hole" and p["net"] == v["net"] and inside(v["at"], p["rect"]):
                parent[find(("v", m))] = find(("p", j))
    by_net = {}
    for j, p in enumerate(pads):
        if p["net"] and not p["net"].startswith("unconnected"):
            by_net.setdefault(p["net"], []).append(j)
    for net, idx in sorted(by_net.items()):
        if net == "GND":
            for j in idx:     # every GND pad but the header's has its own via, so it meets both pours
                p = pads[j]
                if p["kind"] == "smd" and not any(find(("v", m)) == find(("p", j)) for m, v in enumerate(vias) if v["net"] == "GND"):
                    problems.append(f'GND pad {p["ref"]}.{p["num"]} has no via of its own')
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
    # 6. silkscreen text off the pads, by a rough box: KiCad's stroke font is about 0.85 of the size
    #    per character
    for t in kids(tree, "gr_text"):
        at, layer = node(t, "at"), node(t, "layer")[1]
        size = float(node(node(node(t, "effects"), "font"), "size")[1])
        x, y, trot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        hw, hh = len(t[1]) * size * 0.85 / 2, size / 2
        if round(trot) % 180:
            hw, hh = hh, hw
        box = (x - hw, y - hh, x + hw, y + hh)
        side = "F.Cu" if layer.startswith("F.") else "B.Cu"
        for p in pads:
            if side in p["layers"] and p["kind"] != "np_thru_hole" and _gap(box, p["rect"]) < 0.15:
                problems.append(f'silkscreen "{t[1]}" over pad {p["ref"]}.{p["num"]}')
        if not edge_ok(box, 0.2):
            problems.append(f'silkscreen "{t[1]}" off the board')
    # 7. the Feather's fit: every header pin and hole where Adafruit's file has it
    want = {("J2", str(i)): (ROW16_AT[0] + 2.54 * (i - 1), ROW16_AT[1]) for i in range(1, 17)}
    want.update({("J3", str(i)): (ROW12_AT[0] + 2.54 * (i - 1), ROW12_AT[1]) for i in range(1, 13)})
    got = {(p["ref"], p["num"]): (round(p["centre"][0] - OX, 3), round(OY - p["centre"][1], 3)) for p in pads}
    for key, (x, y) in want.items():
        gx, gy = got[key]
        if abs(gx - x) > 0.005 or abs(gy - y) > 0.005:
            problems.append(f"header pin {key} at ({gx}, {gy}), Adafruit's at ({x}, {y})")
    holes = sorted((round(p["centre"][0] - OX, 3), round(OY - p["centre"][1], 3)) for p in pads if p["kind"] == "np_thru_hole")
    if holes != sorted((round(x, 3), round(y, 3)) for _r, (x, y), _d in HOLES):
        problems.append(f"holes at {holes}")
    gnd_vias = sum(1 for v in vias if v["net"] == "GND")
    print(f"{NAME}: {len(pads)} pads, {len(segs)} tracks, {len(vias)} vias ({gnd_vias} GND), {len(nets) - 1} nets")
    if problems:
        print(f"  {len(problems)} problem(s):")
        for p in problems[:60]:
            print("   -", p)
        return False
    print("  self-check clean: clearance, holes, edge, antenna keep-out, shorts, connectivity, net table, silkscreen, the Feather's pins and holes")
    return True


# =================================================================================================

def main():
    path = os.path.join(OUT, NAME + ".kicad_pcb")
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        ok = check_schematic(os.path.join(OUT, NAME + ".kicad_sch"))
        sys.exit(0 if check(path) and ok else 1)
    check_firmware()
    syms = write_symbols()
    write_footprints()
    os.makedirs(OUT, exist_ok=True)
    write_lib_tables()
    sheet_uuid, uids = write_schematic(syms)
    router, failed = route(pad_rects())
    for net, ref, num in failed:
        print(f"  unrouted: {net} to {ref}.{num}")
    write_board(uids, router)
    write_project(sheet_uuid)
    ok = check_schematic(os.path.join(OUT, NAME + ".kicad_sch"))
    sys.exit(0 if check(path) and ok and not failed else 1)


if __name__ == "__main__":
    main()
