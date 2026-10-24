#!/usr/bin/env python3
"""PicoQuorum console-s3, rev A: an ESP32-S3-WROOM-1 on the back, the Feather's 1.14" 240x135
panel in a ZIF on the front, five buttons, the ATECC608C soldered on and USB-C for power and the
serial port. Writes the KiCad 9 project as text, placed but not routed:

    python3 hardware/console-s3/gen_console_s3.py          write lib/ and console-s3/, then check them
    python3 hardware/console-s3/gen_console_s3.py --check  check what is there, write nothing

The design and every number's source are in DESIGN.md. No KiCad is needed here; the checks below
stand in for ERC and DRC on a placed board and are neither. Routing is the next step.

Frames, as in console-pocket's gen_console.py: the board frame has its origin at the board's
bottom-left corner looking at the front, x right and y up, in mm. Page coordinates (KiCad's, y
down) are OX + x, OY - y. Footprints are drawn in KiCad's library frame (origin at the part's
centre, y down). Once the board is edited in KiCad, the KiCad files are the source of truth: don't
run this again, or the edits are lost.
"""
import importlib.util, json, math, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "hardware", "key-pcb"))
import gen        # noqa: E402  the key boards' text helpers: uid, box_symbol, Sheet, JLC_RULES, _font
import gen_cd     # noqa: E402  _sexpr, _kids, STACKUP

_spec = importlib.util.spec_from_file_location("pocket", os.path.join(REPO, "hardware", "console-pocket", "gen_console.py"))
pocket = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pocket)   # console-pocket's footprint and board-text helpers; it writes nothing on import
f, item_text, _prop, _pad, rotate, _gap = pocket.f, pocket.item_text, pocket._prop, pocket._pad, pocket.rotate, pocket._gap
uid = gen.uid

NAME = "console-s3"
L = "pqs3"                                     # the library name, in sym-lib-table and fp-lib-table
LIB = os.path.join(HERE, "lib")
OUT = os.path.join(HERE, NAME)
DATE = "2026-10-24"
TITLE = "PicoQuorum console-s3, rev A: ESP32-S3-WROOM-1 on the back, 1.14in ST7789 in a ZIF, 5 buttons, ATECC608C on board"
NOTE = "The S3 console on one board: see hardware/console-s3/DESIGN.md"
SRC = "PicoQuorum.app"        # the Source Location (CERN-OHL-W v2, section 4.1): the site links to the source
WROOM_DS = "https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf"
ATECC_DS = gen.ATECC_DS

# --- the board -------------------------------------------------------------------------------------
W, H = 64.0, 22.86       # the Feather's width; long enough for five buttons, the panel and the antenna
YC = H / 2
OX, OY = 100.0, 140.0    # page coordinates of the board's bottom-left corner
CORNER = 2.0
EDGE = 0.3               # copper to edge (JLCPCB: 0.3 on a 2-layer board)
CLEAR = 0.2              # the Default netclass clearance
HOLE_CLEAR = 0.25        # copper to a plain hole (JLCPCB's minimum)
TRACK, VIA, DRILL = 0.25, 0.6, 0.3
MIN_TRACK = 0.127        # JLCPCB's narrowest track on 2 layers: Freerouting necks some below TRACK
HOLE_GAP = 0.5           # drilled hole to drilled hole, wall to wall (KiCad's board setup; JLCPCB's)
HOLES = [("H1", (2.2, 2.2)), ("H2", (2.2, H - 2.2))]   # 2.2 mm for M2, at the USB end only: the far end is the antenna's
HOLE_RING = 2.5          # no track and no via this close to a hole's centre, on either side: an M2 washer is 5 mm across
SILK_H, SILK_W = 1.0, 0.8   # silkscreen text, height and width: JLCPCB reads nothing under 1.0 mm tall or 0.15 mm a stroke

# The module: ESP32-S3-WROOM-1-N8R2, Espressif's datasheet v1.8 (Figure 11-1, the land pattern).
# On the back, its antenna end flush with the right edge. N8R2 is quad PSRAM: an R8 (octal) takes
# GPIO35-37, and the screen's MOSI and SCK are 35 and 36 (datasheet Table 3-1, note b).
MODULE_MPN, MODULE_LCSC = "ESP32-S3-WROOM-1-N8R2", "C2913204"
MOD_W, MOD_L, MOD_ANT = 18.0, 25.5, 6.0
MOD_AT = (W - MOD_L / 2, YC)
KEEPOUT = (W - MOD_ANT - 0.5, 0.0, W, H)   # x0, y0, x1, y1: the antenna area and 0.5 mm, full height, both layers

# The panel: a bare 1.14" 240x135 ST7789, 8-pin 0.5 mm FPC, the size Adafruit's Feather ESP32-S3
# Reverse TFT carries. glass is one seller's listing (31 x 17 mm), active is Waveshare's 1.14"
# figure (24.912 x 14.864 mm). The glass lies on foam tape over the ZIF; the tail leaves the glass's
# right end, folds under it and comes back into the ZIF. How far it comes back is EastRising's
# ER-TFT1.14-2 drawing (datasheet rev 1.0, as PicoQuorumKey reads it): the folded tail ends 21.0 +-
# 0.5 mm in from the glass's edge. Until 2026-10-24 this was one seller's 23 mm tail less a guessed
# 5.7 mm fold, which put the end 4.7 mm short of the drawing's. Measure a panel before ordering:
# DESIGN.md, "The panel".
PANEL = dict(glass=(31.0, 17.0), active=(24.912, 14.864), active_dy=0.0, rows=135,
             reach=21.0,         # the glass's right edge to the folded ribbon's end
             reach_tol=0.5,
             home=1.0,           # a ribbon pushed fully into J2 ends this far past J2's centre
             reversed=False,     # True if the fold puts the ribbon's pin 1 at the ZIF's pin 8
             foam=2.0)           # tape thickness: everything under the glass is lower than this
GLASS_X = 18.5            # the glass's left end: room beside J1's pads for the D column and a channel of tracks
GLASS = (GLASS_X, YC - PANEL["glass"][1] / 2, GLASS_X + PANEL["glass"][0], YC + PANEL["glass"][1] / 2)
ROW = PANEL["active"][1] / PANEL["rows"]
# The ribbon's pins, one seller's order: LEDA, GND, RESET, RS (DC), SDA, SCL, VDD, CS. LEDK is
# joined to GND inside, so the backlight is switched on the high side.
PANEL_PINS = [("LEDA", "/LCD_LEDA"), ("GND", "GND"), ("RESET", "/LCD_RST"), ("DC", "/LCD_DC"),
              ("SDA", "/LCD_MOSI"), ("SCL", "/LCD_SCK"), ("VDD", "+3V3"), ("CS", "/LCD_CS")]

# --- the module's pins: number -> (name, ERC type, net). None is a no-connect. ----------------------
_B = "bidirectional"
MODULE = {1: ("GND", "power_in", "GND"), 2: ("3V3", "power_in", "+3V3"), 3: ("EN", "input", "/EN")}
_NAMES = {4: "IO4", 5: "IO5", 6: "IO6", 7: "IO7", 8: "IO15", 9: "IO16", 10: "IO17", 11: "IO18", 12: "IO8", 13: "IO19",
          14: "IO20", 15: "IO3", 16: "IO46", 17: "IO9", 18: "IO10", 19: "IO11", 20: "IO12", 21: "IO13", 22: "IO14",
          23: "IO21", 24: "IO47", 25: "IO48", 26: "IO45", 27: "IO0", 28: "IO35", 29: "IO36", 30: "IO37", 31: "IO38",
          32: "IO39", 33: "IO40", 34: "IO41", 35: "IO42", 36: "RXD0", 37: "TXD0", 38: "IO2", 39: "IO1"}
GPIO_OF = {n: (44 if s == "RXD0" else 43 if s == "TXD0" else int(s[2:])) for n, s in _NAMES.items()}
# The nets by GPIO: the Feather's (firmware/board.py, "feather-s3") and USB
BY_GPIO = {40: "/LCD_DC", 42: "/LCD_CS", 36: "/LCD_SCK", 35: "/LCD_MOSI", 41: "/LCD_RST", 45: "/LCD_BL",
           0: "/BTN_D0", 1: "/BTN_D1", 2: "/BTN_D2", 3: "/SDA", 4: "/SCL", 13: "/LED",
           19: "/S3_DN", 20: "/S3_DP", 43: "/TXD0", 44: "/RXD0"}
for n, s in _NAMES.items():
    MODULE[n] = (s, _B, BY_GPIO.get(GPIO_OF[n]))
MODULE[40] = ("GND", "power_in", "GND")
MODULE[41] = ("EPAD", "power_in", "GND")

ZIF = {k: PANEL_PINS[(8 - k) if PANEL["reversed"] else (k - 1)] for k in range(1, 9)}
USBC = {"A1": "GND", "A4": "VBUS", "A5": "/CC1", "A6": "/USB_DP", "A7": "/USB_DN", "A8": None, "A9": "VBUS", "A12": "GND",
        "B1": "GND", "B4": "VBUS", "B5": "/CC2", "B6": "/USB_DP", "B7": "/USB_DN", "B8": None, "B9": "VBUS", "B12": "GND",
        "SH": "GND"}
# The buttons: (ref, label, net, the other side). D0 is the S3's BOOT strap: low when pressed, with
# a pull-up. D1 and D2 are high when pressed, pulled down, as on the Feather (board.HIGH). BOOT is
# D0 again, on the far side; RESET pulls EN low, as on Espressif's boards.
SWITCHES = [("SW1", "D0", "/BTN_D0", "GND"), ("SW2", "D1", "/BTN_D1", "+3V3"), ("SW3", "D2", "/BTN_D2", "+3V3"),
            ("SW4", "BOOT", "/BTN_D0", "GND"), ("SW5", "RESET", "/EN", "GND")]
TESTPADS = [("TP1", "3V3", "+3V3"), ("TP2", "GND", "GND"), ("TP3", "EN", "/EN"), ("TP4", "TX", "/TXD0"), ("TP5", "RX", "/RXD0"),
            ("TP6", "GND", "GND"), ("TP7", "3V3", "+3V3"), ("TP8", "SDA", "/SDA"), ("TP9", "SCL", "/SCL")]

# The two-pin parts: ref -> (value, footprint, net 1, net 2, LCSC, what it is for)
TWO = {
    "R1": ("150R", "R_0603", "/BL_D", "/LCD_LEDA", "C22808", "Backlight series resistor, from VBUS: (5 - 3.0) V / 150 R = 13 mA, the panel's maximum 20 mA"),
    "R2": ("1k", "R_0603", "/LCD_BL", "/BL_B", "C21190", "GPIO45 to Q1's base"),
    "R3": ("10k", "R_0603", "/BL_B", "GND", "C25804", "Q1 base pull-down: holds GPIO45, a strap, low at reset (VDD_SPI 3.3 V)"),
    "R4": ("10k", "R_0603", "VBUS", "/BL_G", "C25804", "Q2 gate pull-up, to its source: backlight off until GPIO45 drives Q1"),
    "R5": ("10k", "R_0603", "+3V3", "/BTN_D0", "C25804", "D0 pull-up: GPIO0 is BOOT, high for a normal start"),
    "R6": ("10k", "R_0603", "/BTN_D1", "GND", "C25804", "D1 pull-down: pressed reads high (board.HIGH)"),
    "R7": ("10k", "R_0603", "/BTN_D2", "GND", "C25804", "D2 pull-down: pressed reads high (board.HIGH)"),
    "R8": ("10k", "R_0603", "+3V3", "/EN", "C25804", "EN pull-up, with C7 the RC delay Espressif asks for"),
    "R9": ("1k", "R_0603", "/LED", "/LED_A", "C21190", "Status LED series resistor"),
    "R10": ("5.1k", "R_0603", "/CC1", "GND", "C23186", "CC1 Rd: a USB-C source gives 5 V to a sink"),
    "R11": ("5.1k", "R_0603", "/CC2", "GND", "C23186", "CC2 Rd"),
    "R12": ("4.7k", "R_0603", "/SDA", "+3V3", "C23162", "I2C pull-up: the Feather's are on its board, not here"),
    "R13": ("4.7k", "R_0603", "/SCL", "+3V3", "C23162", "I2C pull-up"),
    "C1": ("10u", "C_0603", "VBUS", "GND", "C19702", "U3 input"),
    "C2": ("10u", "C_0603", "+3V3", "GND", "C19702", "U3 output"),
    "C3": ("10u", "C_0603", "+3V3", "GND", "C19702", "Module 3V3 bulk (Espressif shows 22 uF with C2)"),
    "C4": ("100n", "C_0603", "+3V3", "GND", "C14663", "Module 3V3"),
    "C5": ("100n", "C_0603", "+3V3", "GND", "C14663", "ATECC608C VCC"),
    "C6": ("100n", "C_0603", "+3V3", "GND", "C14663", "Panel VDD, at the ZIF"),
    "C7": ("1u", "C_0603", "/EN", "GND", "C15849", "EN delay: R = 10k, C = 1 uF (datasheet v1.8, section 9)"),
    "D1": ("RED", "LED_0603", "GND", "/LED_A", "C2286", "Status LED on GPIO13, the Feather's; pad 1 the cathode"),
}

# --- the one net table: (ref, pad) -> net, exactly as KiCad names them from the schematic ------------
NETS = {}
for n, (pname, _t, net) in MODULE.items():
    NETS["U1", str(n)] = net or f"unconnected-(U1-{pname}-Pad{n})"
for k, (_name, net) in ZIF.items():
    NETS["J2", str(k)] = net
for num, net in USBC.items():
    NETS["J1", num] = net or f"unconnected-(J1-{'SBU1' if num == 'A8' else 'SBU2'}-Pad{num})"
for ref, _label, net, other in SWITCHES:
    NETS[ref, "1"], NETS[ref, "2"] = net, other
for ref, (_v, _fp, n1, n2, _l, _d) in TWO.items():
    NETS[ref, "1"], NETS[ref, "2"] = n1, n2
NETS.update({("U2", "1"): "unconnected-(U2-NC-Pad1)", ("U2", "2"): "unconnected-(U2-NC-Pad2)",
             ("U2", "3"): "unconnected-(U2-NC-Pad3)", ("U2", "4"): "GND", ("U2", "5"): "/SDA", ("U2", "6"): "/SCL",
             ("U2", "7"): "unconnected-(U2-NC-Pad7)", ("U2", "8"): "+3V3", ("U2", "9"): "GND",
             ("U3", "1"): "VBUS", ("U3", "2"): "GND", ("U3", "3"): "VBUS", ("U3", "4"): "unconnected-(U3-NC-Pad4)",
             ("U3", "5"): "+3V3",
             # USB runs through U4: J1's side in on pins 6 and 4, the S3's out on 1 and 3. Pins 1 and 6, and 3
             # and 4, are joined inside it (ST's datasheet, Figures 16 and 18), so no stub can hang off a line
             ("U4", "1"): "/S3_DP", ("U4", "2"): "GND", ("U4", "3"): "/S3_DN", ("U4", "4"): "/USB_DN",
             ("U4", "5"): "VBUS", ("U4", "6"): "/USB_DP",
             ("Q1", "1"): "/BL_B", ("Q1", "2"): "GND", ("Q1", "3"): "/BL_G",
             ("Q2", "1"): "/BL_G", ("Q2", "2"): "VBUS", ("Q2", "3"): "/BL_D"})
for ref, _label, net in TESTPADS:
    NETS[ref, "1"] = net

# --- parts: footprint, value, fields, board position, rotation, side --------------------------------
# Rotations are KiCad's (counter-clockwise on the page). Until 2026-10-23 console-pocket's rotate()
# turned the other way, so every 90 here was meant as -90: these are the old values swapped, which
# puts each pad where the placement was worked out for (KiCad read the old board with the module's
# antenna mid-board and J1's pads off the edge).
# LCSC numbers and tiers from JLCPCB's part pages, 2026-10-24 (DESIGN.md). Check stock when uploading.
PARTS = {
    "U1": dict(fp="ESP32-S3-WROOM-1", value=MODULE_MPN, at=MOD_AT, rot=90, side="B", in_bom=False,
               fields=[("Datasheet", WROOM_DS), ("MPN", MODULE_MPN),
                       ("Description", f"ESP32-S3 module, 8 MB flash, 2 MB quad PSRAM, on the back; JLCPCB {MODULE_LCSC} is Standard-only: hand-soldered")]),
    "U2": dict(fp="DFN-8-1EP_3x2mm_P0.5mm", value="ATECC608C", at=(23.5, 16.5), rot=0,
               fields=[("Datasheet", ATECC_DS), ("LCSC", "C23291019"), ("MPN", "ATECC608C-MAHDA-S"),
                       ("Description", "The console's key: ECC P-256 secure element, I2C 0x60, UDFN-8 2x3 mm, the part key-b uses")]),
    "U3": dict(fp="SOT-23-5", value="ME6211C33", at=(23.5, 6.5), rot=0,
               fields=[("LCSC", "C82942"), ("MPN", "ME6211C33M5G-N"), ("Description", "3.3 V LDO, 500 mA, from USB's 5 V; CE tied to VIN")]),
    "U4": dict(fp="SOT-23-6", value="USBLC6-2SC6", at=(7.5, 2.85), rot=0,     # below J1, clear of H1's ring
               fields=[("LCSC", "C7519"), ("MPN", "USBLC6-2SC6"), ("Description", "ESD on D+ and D-, and its rail clamps VBUS")]),
    "Q1": dict(fp="SOT-23", value="S8050", at=(38.5, 6.0), rot=0,
               fields=[("LCSC", "C2150"), ("MPN", "SS8050"), ("Description", "NPN: GPIO45 high pulls Q2's gate low. 1 B, 2 E, 3 C")]),
    "Q2": dict(fp="SOT-23", value="AO3401A", at=(43.0, 6.0), rot=0,
               fields=[("LCSC", "C15127"), ("MPN", "AO3401A"), ("Description", "P-MOSFET high-side backlight switch, from VBUS. 1 G, 2 S, 3 D")]),
    "J1": dict(fp="USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A", value="USB-C", at=(3.675, YC), rot=-90,
               fields=[("LCSC", "C2894897"), ("MPN", "HC-TYPE-C-16P-01A"),
                       ("Description", "USB-C receptacle, key-c's part: power and the S3's own USB (serial, esptool)")]),
    "J2": dict(fp="FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB", value="PANEL", rot=90,
               at=(GLASS[2] - (PANEL["reach"] - PANEL["reach_tol"]) + PANEL["home"], YC),   # the shortest ribbon home; the longest bows 1 mm
               fields=[("LCSC", "C2919492"), ("MPN", "0.5K-HX-8PWB"),
                       ("Description", "8-pin 0.5 mm FPC ZIF, rear flip, contacts both sides: the panel's ribbon clips in")]),
}
# C3 and C4 under RESET, against the bottom edge: over the module's 3V3 and ground pins (2 and 1)
_TWO_AT = {"R1": ((43.0, 2.8), 0), "R2": ((38.5, 9.2), 0), "R3": ((38.5, 2.8), 0), "R4": ((43.0, 9.2), 0),
           "R5": ((19.9, 17.5), -90), "R6": ((19.9, YC), -90), "R7": ((19.9, 5.4), -90), "R8": ((52.2, 10.4), -90),
           "R9": ((55.0, 11.4), 0), "R10": ((6.0, 17.6), 180), "R11": ((6.0, 5.35), 180), "R12": ((28.0, 17.5), -90),
           "R13": ((30.0, 17.5), -90), "C1": ((23.5, 3.8), 0), "C2": ((27.5, 6.5), -90), "C3": ((52.4, 1.1), 0),
           "C4": ((55.4, 1.1), 0), "C5": ((23.5, 19.0), 180), "C6": ((32.4, 16.2), 0), "C7": ((55.0, 9.65), 0),
           "D1": ((55.0, 13.4), 0)}
for ref, (value, fp, _n1, _n2, lcsc, desc) in TWO.items():
    at, rot = _TWO_AT[ref]
    PARTS[ref] = dict(fp=fp, value=value, at=at, rot=rot, fields=[("LCSC", lcsc), ("Description", desc)])


def rail_y():
    """The buttons' heights: each level with its row of firmware/board.py's RAIL_Y on the panel's
    active area, which is centred on the glass unless PANEL["active_dy"] says otherwise."""
    rows = firmware_profile()["RAIL_Y"]
    mid = (PANEL["rows"] - 1) / 2
    return [YC + PANEL["active_dy"] + (mid - r) * ROW for r in rows]


SW_X = (14.7, 53.5)      # the D column left of the glass, BOOT and RESET right of it; 14.7 leaves a 3 mm channel beside J1's pads
SW_LCSC, SW_MPN = "C318884", "TS-1187A-B-A-B"
for p in PARTS.values():
    p.setdefault("side", "F"); p.setdefault("dnp", False); p.setdefault("in_bom", True)


def place_switches():
    y0, y1, y2 = rail_y()
    at = {"SW1": (SW_X[0], y0), "SW2": (SW_X[0], y1), "SW3": (SW_X[0], y2), "SW4": (SW_X[1], y0), "SW5": (SW_X[1], y2)}
    for ref, label, net, other in SWITCHES:
        what = {"D0": "Reject (today's image); BOOT when held at reset", "D1": "Next", "D2": "Sign, held; Open",
                "BOOT": "GPIO0, as D0: held through RESET, the S3 starts its ROM loader",
                "RESET": "EN to ground: the S3 restarts"}[label]
        PARTS[ref] = dict(fp="SW_TS-1187A", value=label, at=(round(at[ref][0], 3), round(at[ref][1], 3)), rot=0, side="F",
                          dnp=False, in_bom=True,
                          fields=[("LCSC", SW_LCSC), ("MPN", SW_MPN), ("Description", f"{label}: {what}. 5.1x5.1x1.5 mm tact, {net.lstrip('/')} to {other}")])
    for k, (ref, label, net) in enumerate(TESTPADS):
        x, y = (20.0 + 3.0 * k, 19.6) if k < 5 else (20.0 + 3.0 * (k - 5), 3.0)
        PARTS[ref] = dict(fp="TestPad_1.5mm_Back", value=label, at=(x, y), rot=0, side="B", dnp=False, in_bom=False,
                          fields=[("Description", f"{label}: bare copper on the back" + (", a spare for a key-c on wires" if k >= 5 else ""))])


# Heights above the board, mm, for what may sit under the glass on its tape (DESIGN.md, "The panel")
HEIGHT = {"R_0603": 0.55, "C_0603": 0.9, "LED_0603": 0.8, "SOT-23": 1.2, "SOT-23-5": 1.25, "SOT-23-6": 1.45,
          "DFN-8-1EP_3x2mm_P0.5mm": 0.6, "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB": 1.0, "SW_TS-1187A": 1.5,
          "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A": 3.3}


def page(x, y):
    return OX + x, OY - y


# =================================================================================================
# What the firmware expects, read from firmware/board.py. Read only.
# =================================================================================================

def firmware_profile():
    b = open(os.path.join(REPO, "firmware", "board.py")).read()
    prof = re.search(r"^if THREE:(.*?)\nelif ", b, re.S | re.M).group(1)

    def nums(pattern):
        return tuple(int(v) for v in re.search(pattern, prof).group(1).replace(" ", "").split(",") if v)
    dc, cs, sck, mosi, rst, bl = nums(r"DC, CS, SCK, MOSI, RST, BL = ([\d, ]+)")
    spi, sda, scl, led = nums(r"SPI_ID, SDA, SCL, LED = ([\d, ]+)")
    return dict(DC=dc, CS=cs, SCK=sck, MOSI=mosi, RST=rst, BL=bl, SDA=sda, SCL=scl, LED=led,
                BUTTONS={k: int(v) for k, v in re.findall(r'"(D\d)": (\d+)', re.search(r"BUTTONS = \{([^}]*)\}", prof).group(1))},
                HIGH=nums(r"HIGH = \(([\d, ]+)\)"), POWER=int(re.search(r"NOT_KEYS, POWER = \([^)]*\), (\d+)", prof).group(1)),
                RAIL_Y=nums(r"RAIL_Y = \(([\d, ]+)\)"))


def check_firmware():
    """The board's pin table against the "feather-s3" profile, so today's console image runs on it
    with no change (AGENTS.md rule 2)."""
    p = firmware_profile()
    net_of = {GPIO_OF[n]: MODULE[n][2] for n in _NAMES}
    want = {p["DC"]: "/LCD_DC", p["CS"]: "/LCD_CS", p["SCK"]: "/LCD_SCK", p["MOSI"]: "/LCD_MOSI", p["RST"]: "/LCD_RST",
            p["BL"]: "/LCD_BL", p["SDA"]: "/SDA", p["SCL"]: "/SCL", p["LED"]: "/LED"}
    want.update({g: f"/BTN_{k}" for k, g in p["BUTTONS"].items()})
    bad = [f"GPIO{g} is {net_of.get(g)} on the board, {net} in board.py's feather-s3 profile" for g, net in want.items() if net_of.get(g) != net]
    for ref, label, net, other in SWITCHES:
        if label in p["BUTTONS"]:
            high = p["BUTTONS"][label] in p["HIGH"]
            if other != ("+3V3" if high else "GND"):
                bad.append(f"{label} switches to {other}, board.py reads it {'high' if high else 'low'} when pressed")
    if net_of.get(p["POWER"]) is not None:
        bad.append(f"GPIO{p['POWER']} (board.POWER, driven high at import) carries {net_of[p['POWER']]}; it must drive nothing here")
    if "R8" in MODULE_MPN.split("-")[-1]:
        bad.append(f"{MODULE_MPN} has octal PSRAM, which takes GPIO35-37")
    if bad:
        sys.exit("the board's pins disagree with the firmware:\n  " + "\n  ".join(bad))
    return p


# =================================================================================================
# Symbols
# =================================================================================================

def two_pin_symbol(name, ref, desc, fp, names=("1", "2")):
    return gen.box_symbol(name, ref, name, f"{L}:{fp}", "", desc, 1.27, 2.54,
                          [("1", names[0], "passive", "T", 0), ("2", names[1], "passive", "B", 0)])


def module_symbol():
    pins = [(str(n), MODULE[n][0], MODULE[n][1], "L", 24.13 - 2.54 * (n - 1)) for n in range(1, 21)]
    pins += [(str(n), MODULE[n][0], MODULE[n][1], "R", -24.13 + 2.54 * (n - 21)) for n in range(21, 41)]
    pins.append(("41", "EPAD", "power_in", "B", 0))
    return gen.box_symbol("ESP32-S3-WROOM-1", "U", "ESP32-S3-WROOM-1", f"{L}:ESP32-S3-WROOM-1", WROOM_DS,
                          "ESP32-S3-WROOM-1 module: 40 castellations and the exposed pad, numbered as datasheet v1.8 Table 3-1",
                          15.24, 27.94, pins, mpn=MODULE_MPN)


SYM = {   # name -> (width, half-height, pins as (number, name, type, side, offset))
    "ATECC608C_UDFN": (7.62, 7.62, [("8", "VCC", "power_in", "T", 0), ("4", "GND", "power_in", "B", -2.54),
                                    ("9", "EP", "passive", "B", 2.54), ("5", "SDA", "bidirectional", "L", 2.54),
                                    ("6", "SCL", "input", "L", -2.54), ("1", "NC", "no_connect", "R", 3.81),
                                    ("2", "NC", "no_connect", "R", 1.27), ("3", "NC", "no_connect", "R", -1.27),
                                    ("7", "NC", "no_connect", "R", -3.81)]),
    "ME6211C33": (7.62, 5.08, [("1", "VIN", "power_in", "L", 2.54), ("3", "CE", "input", "L", -2.54),
                               ("5", "VOUT", "power_out", "R", 2.54), ("4", "NC", "no_connect", "R", -2.54),
                               ("2", "GND", "power_in", "B", 0)]),
    "USBLC6-2SC6": (7.62, 5.08, [("1", "IO1", "passive", "L", 2.54), ("3", "IO2", "passive", "L", -2.54),
                                 ("6", "IO1", "passive", "R", 2.54), ("4", "IO2", "passive", "R", -2.54),
                                 ("5", "VBUS", "passive", "T", 0), ("2", "GND", "passive", "B", 0)]),
    "Q_NPN": (5.08, 5.08, [("1", "B", "passive", "L", 0), ("2", "E", "passive", "B", 0), ("3", "C", "passive", "T", 0)]),
    "Q_PMOS": (5.08, 5.08, [("1", "G", "passive", "L", 0), ("2", "S", "passive", "T", 0), ("3", "D", "passive", "B", 0)]),
    "USB_C_16P": (7.62, 22.86, [(n, nm, "passive", "R", 21.59 - 2.54 * k) for k, (n, nm) in enumerate(
        [("A4", "VBUS"), ("A9", "VBUS"), ("B4", "VBUS"), ("B9", "VBUS"), ("A5", "CC1"), ("B5", "CC2"), ("A6", "D+"),
         ("B6", "D+"), ("A7", "D-"), ("B7", "D-"), ("A8", "SBU1"), ("B8", "SBU2"), ("A1", "GND"), ("A12", "GND"),
         ("B1", "GND"), ("B12", "GND"), ("SH", "SHIELD")])]),
    "FPC_8P": (7.62, 10.16, [(str(k), ZIF[k][0], "passive", "R", 8.89 - 2.54 * (k - 1)) for k in range(1, 9)]),
    "SW_Push": (2.54, 2.54, [("1", "1", "passive", "T", 0), ("2", "2", "passive", "B", 0)]),
    "TestPad": (1.27, 1.27, [("1", "1", "passive", "B", 0)]),
}
SYM_FP = {"ATECC608C_UDFN": ("DFN-8-1EP_3x2mm_P0.5mm", "ATECC608C secure element, ECC P-256, I2C, UDFN-8 2x3 mm", ATECC_DS),
          "ME6211C33": ("SOT-23-5", "ME6211 3.3 V LDO, 500 mA, SOT-23-5", ""),
          "USBLC6-2SC6": ("SOT-23-6", "USBLC6-2SC6 ESD protection, two lines and a VBUS rail", gen.USBLC6_DS),
          "Q_NPN": ("SOT-23", "NPN transistor, SOT-23: 1 B, 2 E, 3 C", ""),
          "Q_PMOS": ("SOT-23", "P-channel MOSFET, SOT-23: 1 G, 2 S, 3 D", ""),
          "USB_C_16P": ("USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A", "USB-C 16-pin receptacle, USB 2.0", ""),
          "FPC_8P": ("FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB", "8-pin 0.5 mm FPC connector; pin names are the panel's", ""),
          "SW_Push": ("SW_TS-1187A", "Tact switch; pads 1 (one pair) and 2 (the other) close when pressed", ""),
          "TestPad": ("TestPad_1.5mm_Back", "Test pad, bare copper on the back", "")}


def write_symbols():
    syms = [module_symbol()]
    for name, (w, h, pins) in SYM.items():
        fp, desc, ds = SYM_FP[name]
        syms.append(gen.box_symbol(name, {"Q_NPN": "Q", "Q_PMOS": "Q", "USB_C_16P": "J", "FPC_8P": "J", "SW_Push": "SW",
                                          "TestPad": "TP"}.get(name, "U"), name, f"{L}:{fp}", ds, desc, w, h, pins))
    syms += [two_pin_symbol("R", "R", "Resistor", "R_0603"), two_pin_symbol("C", "C", "Capacitor", "C_0603"),
             two_pin_symbol("LED", "D", "LED, pad 1 the cathode", "LED_0603", names=("K", "A"))]
    up = [(0, 0), (0, 2.54), (-0.762, 1.27), (0, 2.54), (0.762, 1.27)]
    syms += [pocket.power_symbol("GND", "power_in", [(0, 0), (0, -1.27), (1.27, -1.27), (0, -2.54), (-1.27, -1.27), (0, -1.27)]),
             pocket.power_symbol("+3V3", "power_in", up), pocket.power_symbol("VBUS", "power_in", up),
             pocket.power_symbol("PWR_FLAG", "power_out", [(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)])]
    os.makedirs(LIB, exist_ok=True)
    with open(os.path.join(LIB, f"{L}.kicad_sym"), "w") as fh:
        fh.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        fh.write("\n".join(syms))
        fh.write("\n)\n")
    return {re.match(r'\(symbol "([^"]+)"', s).group(1): s for s in syms}


# =================================================================================================
# Schematic
# =================================================================================================

class S3Sheet(gen.Sheet):
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


def write_schematic(syms):
    sh = S3Sheet(NAME)
    for name, text in syms.items():
        sh.lib(f"{L}:{name}", text.replace(f'(symbol "{name}"', f'(symbol "{L}:{name}"', 1))
    uids = {}

    def end(px, py, side, net, dx=7.62):
        """Wire a pin out and end it in a label or a power symbol; a no-connect flag if it has no net."""
        if net is None or net.startswith("unconnected"):
            sh.nc(px, py)
            return
        ex, ey = {"L": (px - dx, py), "R": (px + dx, py), "T": (px, py - 2.54), "B": (px, py + 2.54)}[side]
        sh.wire(px, py, ex, ey)
        if net == "GND":
            sh.power("GND", ex, ey, rot={"L": 270, "R": 90, "T": 180, "B": 0}[side])
        elif net in ("+3V3", "VBUS"):
            sh.power(net, ex, ey, rot={"L": 90, "R": 270, "T": 0, "B": 180}[side])
        else:
            sh.label(net.lstrip("/"), ex, ey, left=(side == "L"))

    def part(ref, sym, x, y, w, h, pins):
        p = PARTS[ref]
        uids[ref] = sh.symbol(f"{L}:{sym}", ref, p["value"], x, y, [n for n, *_ in pins], fp=f"{L}:{p['fp']}",
                              fields=p["fields"], dnp=p["dnp"], in_bom=p["in_bom"], on_board=True, box_h=h)
        for num, _name, _t, side, off in pins:
            end(*pocket.pin_end(x, y, side, off, w, h), side, NETS[ref, num])

    def boxed(ref, sym, x, y):
        w, h, pins = SYM[sym]
        part(ref, sym, x, y, w, h, pins)

    def two(ref, x, y):
        sym = {"R": "R", "C": "C", "D": "LED"}[ref[0]]
        part(ref, sym, x, y, 1.27, 2.54, [("1", "", "", "T", 0), ("2", "", "", "B", 0)])

    # the module in the middle
    mx, my = 147.32, 85.09
    part("U1", "ESP32-S3-WROOM-1", mx, my, 15.24, 27.94,
         [(str(n), "", "", "L", 24.13 - 2.54 * (n - 1)) for n in range(1, 21)]
         + [(str(n), "", "", "R", -24.13 + 2.54 * (n - 21)) for n in range(21, 41)] + [("41", "", "", "B", 0)])
    sh.text("ESP32-S3-WROOM-1-N8R2 on the back, hand-soldered.\n"
            "The Feather ESP32-S3 Reverse TFT's GPIOs (firmware/board.py,\n"
            "\"feather-s3\"), so today's console image runs unchanged.\n"
            "Never an R8 module: octal PSRAM takes GPIO35-37.", mx - 20.32, my + 38.1)
    for k, (net, x) in enumerate((("GND", 22.86), ("VBUS", 40.64))):
        sh.power(net, x, 20.32)
        sh.wire(x, 20.32, x + 7.62, 20.32)
        sh.power("PWR_FLAG", x + 7.62, 20.32, rot=180)

    # power: USB-C, its ESD array, the regulator
    part("J1", "USB_C_16P", 30.48, 81.28, 7.62, 22.86, SYM["USB_C_16P"][2])
    boxed("U4", "USBLC6-2SC6", 76.2, 40.64)
    boxed("U3", "ME6211C33", 76.2, 66.04)
    for ref, x, y in (("R10", 58.42, 101.6), ("R11", 68.58, 101.6), ("C1", 58.42, 127.0), ("C2", 99.06, 81.28)):
        two(ref, x, y)
    sh.text("USB-C: 5 V in and the S3's own USB-Serial-JTAG on D+/D-\n"
            "(GPIO20/19): esptool and tools/fw, no bridge chip. 5.1k Rd\n"
            "on each CC. U4's rail on VBUS clamps it too.", 20.32, 114.3)

    # the panel and its backlight
    boxed("J2", "FPC_8P", 233.68, 50.8)
    for ref, x, y in (("C6", 254.0, 76.2), ("R1", 213.36, 93.98), ("R2", 187.96, 119.38), ("R3", 195.58, 129.54),
                      ("R4", 236.22, 101.6)):
        two(ref, x, y)
    boxed("Q2", "Q_PMOS", 213.36, 114.3)
    boxed("Q1", "Q_NPN", 213.36, 139.7)
    sh.text("The panel: 1.14in 240x135 ST7789 on an 8-pin 0.5 mm ribbon, one\n"
            "seller's pin order (DESIGN.md). Its LEDK is GND inside, so Q2\n"
            "switches LEDA from VBUS on the high side, R1 setting 13 mA;\n"
            "GPIO45 high is on, as on the\n"
            "Feather. R3 holds GPIO45 (a strap: VDD_SPI) low at reset.", 185.42, 157.48)

    # the key, the buttons, the LED, EN
    boxed("U2", "ATECC608C_UDFN", 233.68, 177.8 - 12.7)
    for ref, x, y in (("C5", 259.08, 152.4 + 2.54), ("R12", 203.2, 167.64), ("R13", 210.82, 167.64)):
        two(ref, x, y)
    for k, (ref, _label, _net, _other) in enumerate(SWITCHES):
        part(ref, "SW_Push", 22.86 + 15.24 * k, 172.72, 2.54, 2.54, SYM["SW_Push"][2])
    for k, ref in enumerate(("R5", "R6", "R7")):
        two(ref, 22.86 + 15.24 * k, 144.78)
    sh.text("D0, D1, D2: the Feather's buttons on its GPIOs. D0 is BOOT: low\n"
            "when pressed, R5 up. D1, D2 high when pressed, R6 and R7 down.\n"
            "BOOT is D0 again; RESET pulls EN low.", 20.32, 185.42)
    for ref, x, y in (("R8", 106.68, 147.32), ("C7", 116.84, 147.32), ("C3", 129.54, 147.32), ("C4", 139.7, 147.32),
                      ("R9", 160.02, 147.32), ("D1", 160.02, 167.64)):
        two(ref, x, y)
    sh.text("EN: R8 and C7, Espressif's RC delay. C3, C4 at the module's 3V3.\n"
            "D1: the status LED on GPIO13, the Feather's.", 106.68, 182.88)
    for k, (ref, _label, _net) in enumerate(TESTPADS):
        part(ref, "TestPad", 182.88 + 7.62 * k, 22.86, 1.27, 1.27, SYM["TestPad"][2])
    sh.text("Bare pads on the back: 3V3, GND, EN, TX, RX; then GND, 3V3,\n"
            "SDA, SCL for a key-c on wires.", 182.88, 35.56)
    os.makedirs(OUT, exist_ok=True)
    sh.write(os.path.join(OUT, NAME + ".kicad_sch"), TITLE)
    return sh.root, uids


# =================================================================================================
# Footprints, in pocket's item format: ("pad", num, kind, shape, x, y, w, h, drill, layers), lines...
# =================================================================================================

def _crtyd(x0, y0, x1, y1):
    return ("rect", x0, y0, x1, y1, "F.CrtYd", 0.05, False)


PAD_IRON = 1.0           # the module's pads reach this much further out than Espressif's pattern, for an iron


def fp_module():
    """Espressif's land pattern (datasheet v1.8, Figure 11-1), antenna up (-y): pads 1.5 x 0.9 at
    1.27 mm, reaching 0.5 mm past the module's edge, each made PAD_IRON longer outward so an iron's
    tip has copper beside every castellation (as PicoQuorumKey's are); pin 1 7.49 mm below the antenna end, the
    bottom row from 2.015 mm in. The exposed pad is the 3.7 mm block of nine, its centre 7.5 mm from
    the pin-1 side and 10.29 mm from the bottom edge, where KiCad's own RF_Module footprint has it
    (until 2026-10-23 these were read as distances to its near sides, 1.85 mm off); one pad here,
    bare, no paste (soldering it is optional: section 9). The silkscreen stops short of the antenna
    end, which is the board's edge. The pin-1 dot sits just past pin 1 toward the antenna, clear of its longer pad."""
    hw, hl = MOD_W / 2, MOD_L / 2
    y1 = -hl + 7.49
    items = []
    e, L = PAD_IRON / 2, 1.5 + PAD_IRON
    for n in range(1, 15):
        items.append(_pad(str(n), "smd", "rect", -hw + 0.25 - e, y1 + 1.27 * (n - 1), L, 0.9))
    for n in range(15, 27):
        items.append(_pad(str(n), "smd", "rect", -hw + 2.015 + 1.27 * (n - 15), hl - 0.25 + e, 0.9, L))
    for n in range(27, 41):
        items.append(_pad(str(n), "smd", "rect", hw - 0.25 + e, hl - 1.5 - 1.27 * (n - 27), L, 0.9))
    items.append(_pad("41", "smd", "rect", -hw + 7.5, hl - 10.29, 3.7, 3.7, layers=["F.Cu", "F.Mask"]))
    items += [("rect", -hw, -hl, hw, hl, "F.Fab", 0.1, False), ("rect", -hw, -hl, hw, -hl + MOD_ANT, "F.Fab", 0.1, False),
              ("text", "antenna: no copper", 0, -hl + 3.0, 0, "F.Fab", 0.8), _crtyd(-hw - 0.75 - PAD_IRON, -hl - 0.25, hw + 0.75 + PAD_IRON, hl + 0.75 + PAD_IRON),
              ("line", -hw, -hl + 0.5, -hw, y1 - 1.0, "F.SilkS", 0.12),
              ("line", hw, -hl + 0.5, hw, y1 - 1.0, "F.SilkS", 0.12), ("circle", -hw - 1.0, y1 - 1.1, 0.3, "F.SilkS", 0.12, True)]
    return dict(items=items, attr="smd exclude_from_pos_files exclude_from_bom",
                descr="ESP32-S3-WROOM-1, Espressif's recommended land pattern (datasheet v1.8, Figure 11-1), its 40 pads 1.0 mm longer outward "
                      "for hand soldering (2.5x0.9 at 1.27 mm), "
                      "the exposed pad as one 3.7 mm pad without paste. Keep the 18x6 mm antenna end free of copper on every layer",
                tags="esp32-s3 wroom module")


def fp_udfn():
    """key-b's DFN-8-1EP_3x2mm_P0.5mm_EP1.3x1.5mm, as its board holds it (KiCad's own footprint)."""
    items = [_pad(str(n), "smd", "rect", x, y, 0.75, 0.3) for n, x, y in
             ((1, -1.45, -0.75), (2, -1.45, -0.25), (3, -1.45, 0.25), (4, -1.45, 0.75),
              (5, 1.45, 0.75), (6, 1.45, 0.25), (7, 1.45, -0.25), (8, 1.45, -0.75))]
    items += [_pad("9", "smd", "rect", 0, 0, 1.3, 1.5, layers=["F.Cu", "F.Mask"])]
    items += [_pad("", "smd", "rect", x, y, 0.5, 0.6, layers=["F.Paste"]) for x in (-0.325, 0.325) for y in (-0.375, 0.375)]
    items += [("rect", -1.5, -1.0, 1.5, 1.0, "F.Fab", 0.1, False), _crtyd(-2.1, -1.3, 2.1, 1.3),
              ("circle", -2.2, -1.2, 0.15, "F.SilkS", 0.12, True)]
    return dict(items=items, attr="smd", tags="dfn udfn 3x2", descr="UDFN-8 2x3 mm with a 1.3x1.5 mm exposed pad: KiCad's footprint, as key-b's board holds it")


def fp_sot23_5():
    items = [_pad(str(n), "smd", "roundrect", x, y, 1.325, 0.6)
             for n, x, y in ((1, -1.1375, -0.95), (2, -1.1375, 0), (3, -1.1375, 0.95), (4, 1.1375, 0.95), (5, 1.1375, -0.95))]
    items += [("rect", -0.8, -1.45, 0.8, 1.45, "F.Fab", 0.1, False), _crtyd(-2.05, -1.75, 2.05, 1.75),
              ("line", -0.8, -1.56, 0.8, -1.56, "F.SilkS", 0.12), ("line", -0.8, 1.56, 0.8, 1.56, "F.SilkS", 0.12),
              ("circle", -1.9, -1.6, 0.15, "F.SilkS", 0.12, True)]
    return dict(items=items, attr="smd", tags="sot-23-5", descr="SOT-23-5, KiCad's land pattern: pads 1.325x0.6 at (+-1.1375, -0.95/0/0.95)")


def fp_sot23_6():
    items = [_pad(str(n), "smd", "roundrect", x, y, 1.325, 0.6)
             for n, x, y in ((1, -1.1375, -0.95), (2, -1.1375, 0), (3, -1.1375, 0.95), (4, 1.1375, 0.95), (5, 1.1375, 0), (6, 1.1375, -0.95))]
    items += [("rect", -0.8, -1.45, 0.8, 1.45, "F.Fab", 0.1, False), _crtyd(-2.05, -1.75, 2.05, 1.75),
              ("line", -0.8, -1.56, 0.8, -1.56, "F.SilkS", 0.12), ("line", -0.8, 1.56, 0.8, 1.56, "F.SilkS", 0.12),
              ("circle", -1.9, -1.6, 0.15, "F.SilkS", 0.12, True)]
    return dict(items=items, attr="smd", tags="sot-23-6", descr="SOT-23-6, KiCad's land pattern: pads 1.325x0.6 at (+-1.1375, -0.95/0/0.95)")


def fp_two(descr, tags, mark=False):
    items = [_pad("1", "smd", "roundrect", -0.775, 0, 0.9, 0.95), _pad("2", "smd", "roundrect", 0.775, 0, 0.9, 0.95),
             ("rect", -0.8, -0.4, 0.8, 0.4, "F.Fab", 0.1, False), _crtyd(-1.48, -0.73, 1.48, 0.73)]
    if mark:
        items.append(("line", -1.6, -0.6, -1.6, 0.6, "F.SilkS", 0.12))     # the cathode end
    return dict(items=items, attr="smd", descr=descr, tags=tags)


def pad_item_text(it, **kw):
    """item_text, and a plated slot's oval drill, which pocket's writer doesn't know (gen_wing.py's)."""
    if it[0] == "pad" and isinstance(it[8], tuple):
        _oval, dw, dh = it[8]
        return item_text(it[:8] + (dw,) + it[9:], **kw).replace(f"(drill {f(dw)})", f"(drill oval {f(dw)} {f(dh)})")
    return item_text(it, **kw)


def fp_usbc():
    """key-c's HC-TYPE-C-16P-01A footprint, as its board holds it: the mouth at +y, 3.675 mm from
    the origin, flush with the board edge. A1/B12 and A12/B1 share pads, as do A4/B9 and A9/B4."""
    pads = [("A1", -3.2, -3.795, 0.6, 1.2), ("A4", -2.4, -3.745, 0.6, 1.3), ("A5", -1.25, -3.745, 0.3, 1.3),
            ("A6", -0.25, -3.745, 0.3, 1.3), ("A7", 0.25, -3.745, 0.3, 1.3), ("A8", 1.25, -3.745, 0.3, 1.3),
            ("A9", 2.4, -3.745, 0.6, 1.3), ("A12", 3.2, -3.795, 0.6, 1.2), ("B1", 3.2, -3.795, 0.6, 1.2),
            ("B4", 2.4, -3.745, 0.6, 1.3), ("B5", 1.75, -3.745, 0.3, 1.3), ("B6", 0.75, -3.745, 0.3, 1.3),
            ("B7", -0.75, -3.745, 0.3, 1.3), ("B8", -1.75, -3.745, 0.3, 1.3), ("B9", -2.4, -3.745, 0.6, 1.3),
            ("B12", -3.2, -3.795, 0.6, 1.2)]
    items = [_pad(n, "smd", "roundrect", x, y, w, h) for n, x, y, w, h in pads]
    items += [_pad("", "np_thru_hole", "circle", x, -2.605, 0.65, 0.65, 0.65, layers=["*.Mask"]) for x in (-2.89, 2.89)]
    # the shell's slots as key-c's, their pads 0.1 mm bigger than key-c's: a 0.25 mm ring, not JLCPCB's bare 0.2
    items += [_pad("SH", "thru_hole", "oval", x, y, 1.1, h + 0.1, ("oval", 0.6, h - 0.4)) for x in (-4.32, 4.32)
              for y, h in ((-3.105, 2.1), (1.075, 1.6))]
    items += [("rect", -4.47, -3.675, 4.47, 3.675, "F.Fab", 0.1, False), _crtyd(-5.32, -4.9, 5.32, 4.18),
              ("text", "board edge", 0, 3.4, 0, "F.Fab", 0.6)]
    return dict(items=items, attr="smd", tags="usb c receptacle",
                descr="USB-C receptacle HCTL HC-TYPE-C-16P-01A (LCSC C2894897): key-c's footprint, the mouth at +y on the board edge")


def fp_zif():
    """HDGC 0.5K-HX-8PWB, its drawing's recommended pattern for 8 contacts: pads 0.30 x 0.80 at
    0.5 mm (B = 3.50), pegs 0.40 x 0.80 with E = 5.10 and F = 5.90 between their inner and outer
    sides, 3.30 mm from the contact pads' far edge to the pegs' far edge. The ribbon goes in from +y
    (the peg side); the actuator flips up at -y."""
    items = [_pad(str(k), "smd", "rect", -1.75 + 0.5 * (k - 1), -1.25, 0.3, 0.8) for k in range(1, 9)]
    items += [_pad("", "smd", "rect", x, 1.25, 0.4, 0.8) for x in (-2.75, 2.75)]
    items += [("rect", -3.0, -1.65, 3.0, 1.6, "F.Fab", 0.1, False), _crtyd(-3.3, -2.3, 3.3, 1.9),
              ("circle", -1.75, -2.05, 0.12, "F.SilkS", 0.12, True), ("text", "ribbon in", 0, 2.5, 0, "F.Fab", 0.5)]
    return dict(items=items, attr="smd", tags="fpc zif 0.5mm",
                descr="8-pin 0.5 mm FPC ZIF, HDGC 0.5K-HX-8PWB (LCSC C2919492): the drawing's recommended pattern. Ribbon in at +y")


def fp_switch():
    """KiCad's SW_Push_1P1T_XKB_TS-1187A, as console-a's board holds it: pads 1 x 0.75 at (+-3,
    +-1.875); the top pair is pad 1, the bottom pair pad 2."""
    items = [_pad("1", "smd", "rect", x, -1.875, 1.0, 0.75) for x in (-3.0, 3.0)]
    items += [_pad("2", "smd", "rect", x, 1.875, 1.0, 0.75) for x in (-3.0, 3.0)]
    items += [("rect", -2.55, -2.55, 2.55, 2.55, "F.Fab", 0.1, False), ("circle", 0, 0, 1.5, "F.Fab", 0.1, False),
              _crtyd(-3.75, -2.8, 3.75, 2.8)]
    for sy in (-1, 1):
        items.append(("line", -1.8, sy * 2.65, 1.8, sy * 2.65, "F.SilkS", 0.12))
    return dict(items=items, attr="smd", tags="tact switch 5.1x5.1",
                descr="5.1x5.1x1.5 mm SMD tact switch, XKB TS-1187A-B-A-B (LCSC C318884): KiCad's footprint")


def fp_testpad():
    return dict(items=[_pad("1", "smd", "circle", 0, 0, 1.5, 1.5, layers=["F.Cu", "F.Mask"]), ("circle", 0, 0, 1.0, "F.CrtYd", 0.05, False)],
                attr="smd exclude_from_pos_files exclude_from_bom", descr="Test pad: 1.5 mm bare copper, no paste (placed on the back)",
                tags="test pad")


def fp_hole():
    return dict(items=[_pad("", "np_thru_hole", "circle", 0, 0, 2.2, 2.2, 2.2), ("circle", 0, 0, 1.35, "F.CrtYd", 0.05, False)],
                attr="through_hole board_only exclude_from_pos_files exclude_from_bom", descr="2.2 mm mounting hole, not plated, for an M2 screw",
                tags="mounting hole")


FOOTPRINTS = {
    "ESP32-S3-WROOM-1": fp_module, "DFN-8-1EP_3x2mm_P0.5mm": fp_udfn, "SOT-23-5": fp_sot23_5, "SOT-23-6": fp_sot23_6,
    "SOT-23": pocket.fp_sot23, "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A": fp_usbc, "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB": fp_zif,
    "SW_TS-1187A": fp_switch, "TestPad_1.5mm_Back": fp_testpad, "MountingHole_2.2mm": fp_hole,
    "R_0603": lambda: fp_two("0603 resistor, KiCad's land pattern: pads 0.9x0.95 at +-0.775", "0603"),
    "C_0603": lambda: fp_two("0603 capacitor, KiCad's land pattern: pads 0.9x0.95 at +-0.775", "0603"),
    "LED_0603": lambda: fp_two("0603 LED: pads 0.9x0.95 at +-0.775, pad 1 the cathode (the silk bar)", "0603 led", mark=True),
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
        items = [pad_item_text(it) + (f' (uuid "{uid()}"))' if it[0] == "pad" else "") for it in fp["items"]]
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
# Geometry shared by the board writer and the checks (page coordinates)
# =================================================================================================

def all_parts():
    parts = dict(PARTS)
    for ref, at in HOLES:
        parts[ref] = dict(fp="MountingHole_2.2mm", at=at, rot=0, side="F", value="M2", fields=[], in_bom=False, dnp=False)
    return parts


def world(p, lx, ly):
    """Page position of a footprint's local point. Back-side footprints store y negated."""
    px, py = page(*p["at"])
    dx, dy = rotate(lx, -ly if p["side"] == "B" else ly, p["rot"])
    return px + dx, py + dy


def to_board(pt):
    return round(pt[0] - OX, 3), round(OY - pt[1], 3)


def courtyards():
    """(ref, side, rect in page mm) for every part's courtyard."""
    out = []
    for ref, p in all_parts().items():
        fp = FOOTPRINTS[p["fp"]]()
        for it in fp["items"]:
            if it[0] == "rect" and it[5] == "F.CrtYd":
                a, b = world(p, it[1], it[2]), world(p, it[3], it[4])
            elif it[0] == "circle" and it[4] == "F.CrtYd":
                a, b = world(p, it[1] - it[3], it[2] - it[3]), world(p, it[1] + it[3], it[2] + it[3])
            else:
                continue
            out.append((ref, p["side"], (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))))
    return out


def rect_page(x0, y0, x1, y1):
    a, b = page(x0, y0), page(x1, y1)
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def edge_ok(rect, margin):
    """rect (page mm) at least margin inside the board outline, rounded corners included."""
    bx0, by0, bx1, by1 = rect_page(0, 0, W, H)
    if rect[0] < bx0 + margin or rect[1] < by0 + margin or rect[2] > bx1 - margin or rect[3] > by1 - margin:
        return False
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx = bx0 + CORNER if sx < 0 else bx1 - CORNER          # the corner arc's centre
            cy = by0 + CORNER if sy < 0 else by1 - CORNER
            px = rect[0] if sx < 0 else rect[2]                    # the rect's point furthest into that corner
            py = rect[1] if sy < 0 else rect[3]
            if (px - cx) * sx > 0 and (py - cy) * sy > 0 and math.hypot(px - cx, py - cy) > CORNER - margin:
                return False
    return True


def _pt_seg(p, a, b):
    """Distance from point p to the segment a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _seg_seg(a, b, c, d):
    """Distance between the segments a-b and c-d, 0 where they cross."""
    side = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0:
        return 0.0
    return min(_pt_seg(a, c, d), _pt_seg(b, c, d), _pt_seg(c, a, b), _pt_seg(d, a, b))


def capsule(cx, cy, w, h):
    """A round or oval pad or hole, w x h at (cx, cy), as ("cap", a, b, r): every point within r of
    the segment a-b. A track is one too, and a via."""
    r = min(w, h) / 2
    if w >= h:
        return ("cap", (cx - w / 2 + r, cy), (cx + w / 2 - r, cy), r)
    return ("cap", (cx, cy - h / 2 + r), (cx, cy + h / 2 - r), r)


def copper_gap(p, q):
    """Distance between two shapes, each a capsule or ("rect", x0, y0, x1, y1, r): the rect grown by
    r, a rounded pad's shape (r 0 for a square-cornered one). At most 0 where they meet."""
    if p[0] == "rect" and q[0] == "rect":
        return _gap(p[1:5], q[1:5]) - p[5] - q[5]
    if p[0] == "rect":
        p, q = q, p
    _c, a, b, r = p
    if q[0] == "cap":
        return _seg_seg(a, b, q[1], q[2]) - r - q[3]
    x0, y0, x1, y1, rr = q[1:]
    if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in (a, b)):
        return -r - rr
    sides = (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)))
    return min(_seg_seg(a, b, c, d) for c, d in sides) - r - rr


def j1_body():
    """J1's shell where it sits on the front, from its mouth at the edge to just short of its pads
    (page mm): no front track and no via goes under its metal."""
    return rect_page(0.0, YC - 4.47, 6.5, YC + 4.47)


# J1's pads and the chip's bus, routed by hand and locked, so the router (tools/keypcb route) goes on from them: (net,
# layer, path) in board mm. The ten live pads run GND, VBUS, CC1, D-, D+, D-, D+, CC2, VBUS, GND
# down a 6.4 mm column, and the two pairs interleave, so a router taking the shortest way closes D+
# round D-'s middle pad (Freerouting left A6 unrouted). Here each pair is joined beside J1: the D-
# pads on the front in a loop round A6, which drops to the back inside it and meets B6 there. CC1
# climbs to R10 and CC2 drops to R11; VBUS's pads drop to the back and join there. D+ goes on down
# the back and up to U4's pin 6 (Freerouting found no way between CC2, VBUS and D-). The router takes
# D- and VBUS on from any of this copper. And the chip's SDA and SCL, at 0.5 mm pitch between
# 3V3 and the pull-ups, each go straight to a via of its own: left to itself, Freerouting walled
# pin 6 in. C5 joins the chip directly: its 3V3 pad to pin 8, its ground pad to the exposed pad
# (Freerouting had joined C5 to pin 8 through 35 mm of the 3V3 net).
ESCAPE = [
    ("/CC1", "F.Cu", [(7.5, 12.68), (8.5, 12.68), (8.5, 13.18), (9.5, 13.18), (9.5, 17.43), (7.0, 17.43)]),
    ("/USB_DN", "F.Cu", [(7.5, 12.18), (9.0, 12.18), (9.0, 12.68), (10.75, 12.68), (10.75, 10.93)]),
    ("/USB_DN", "F.Cu", [(7.5, 11.18), (9.0, 11.18), (9.0, 10.93), (10.75, 10.93)]),
    ("/USB_DP", "F.Cu", [(7.5, 11.68), (9.75, 11.68)]),
    ("/USB_DP", "F.Cu", [(7.5, 10.68), (8.5, 10.68), (8.5, 10.18), (10.1, 10.18)]),
    ("/USB_DP", "B.Cu", [(9.75, 11.68), (10.1, 11.68), (10.1, 10.18), (10.1, 4.6)]),
    ("/USB_DP", "F.Cu", [(10.1, 4.6), (9.3, 3.8), (8.6375, 3.8)]),
    ("/CC2", "F.Cu", [(7.5, 9.68), (9.5, 9.68), (9.5, 5.43), (7.0, 5.43)]),
    ("VBUS", "F.Cu", [(7.5, 13.93), (8.75, 13.93)]),
    ("VBUS", "F.Cu", [(7.5, 8.93), (8.75, 8.93)]),
    ("VBUS", "B.Cu", [(8.75, 13.93), (8.75, 8.93)]),
    ("/SDA", "F.Cu", [(24.95, 15.75), (25.75, 15.75), (25.75, 15.0)]),
    ("/SCL", "F.Cu", [(24.95, 16.25), (26.5, 16.25)]),
    ("+3V3", "F.Cu", [(24.275, 19.0), (24.275, 18.2), (24.95, 17.525), (24.95, 17.25)]),
    ("GND", "F.Cu", [(22.725, 19.0), (22.725, 18.3), (23.5, 17.525), (23.5, 16.5)]),
    ("GND", "F.Cu", [(22.363, 6.5), (23.5, 6.5)]),       # U3's ground pin, its heat path, to a via under its body
]
ESCAPE_VIAS = [("/USB_DP", 9.75, 11.68), ("/USB_DP", 10.1, 10.18), ("/USB_DP", 10.1, 4.6),
               ("VBUS", 8.75, 13.93), ("VBUS", 8.75, 8.93), ("/SDA", 25.75, 15.0), ("/SCL", 26.5, 16.25),
               ("GND", 23.5, 6.5)]


# =================================================================================================
# The board file
# =================================================================================================

def _template_blocks():
    """The (layers) and (setup) blocks as KiCad 9 wrote them for key-b, with this board's stackup and
    drill/place origin (as gen_wing.py does it)."""
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
    back = p["side"] == "B"
    rot = p["rot"]
    side_silk, side_fab = ("B.SilkS", "B.Fab") if back else ("F.SilkS", "F.Fab")
    ry = ref_y(fp)
    s = -1 if back else 1
    lines = [f'\t(footprint "{L}:{p["fp"]}" (layer "{"B.Cu" if back else "F.Cu"}") (uuid "{uid()}") (at {f(px)} {f(py)}{" " + f(rot) if rot else ""})',
             f'\t\t(descr "{fp["descr"]}")', f'\t\t(tags "{fp["tags"]}")']
    # references on the fab layer only, as on the wing: the board is too dense for them on the silk
    lines.append(_prop("Reference", ref, 0, s * ry, side_fab, size=0.8, back=back).replace("\t(", "\t\t(", 1))
    lines.append(_prop("Value", p["value"], 0, -s * ry, side_fab, hide=True, back=back).replace("\t(", "\t\t(", 1))
    fields = dict(p.get("fields", []))
    lines.append(_prop("Datasheet", fields.pop("Datasheet", ""), 0, 0, side_fab, hide=True, back=back).replace("\t(", "\t\t(", 1))
    lines.append(_prop("Description", fields.pop("Description", ""), 0, 0, side_fab, hide=True, back=back).replace("\t(", "\t\t(", 1))
    for k, v in fields.items():
        lines.append(_prop(k, v, 0, 0, side_fab, hide=True, back=back).replace("\t(", "\t\t(", 1))
    if path_uuid:
        lines += [f'\t\t(path "/{path_uuid}")', '\t\t(sheetname "/")', f'\t\t(sheetfile "{NAME}.kicad_sch")']
    lines.append(f'\t\t(attr {fp["attr"]}{" dnp" if p.get("dnp") else ""})')
    for it in fp["items"]:
        t = pad_item_text(it, back=back, rot=rot, indent="\t\t")
        if it[0] == "pad":
            net = NETS.get((ref, it[1])) if it[1] else None
            if net:
                t += f' (net {nets[net]} "{net}")'
                if ref == "J1" and net == "GND" and it[2] == "smd":
                    t += " (zone_connect 2)"      # solid to the pour: hemmed in by VBUS and the shell, a thermal gets one spoke
                if (ref, it[1]) == ("U3", "2"):
                    t += " (zone_connect 2)"      # solid to the pour: U3's heat leaves by its ground pin
            t += f' (uuid "{uid()}"))'
        lines.append(t)
    lines += ["\t\t(embedded_fonts no)", "\t)"]
    return "\n".join(lines)


def _logo(name):
    """A logo's shapes from lib/picoquorum.pretty, as its file holds them"""
    src = open(os.path.join(LIB, "picoquorum.pretty", name + ".kicad_mod")).read()
    return src, src[re.search(r"\n\(fp_", src).start():src.rindex("\n(embedded_fonts")]


def logo_items(name, x, y, k, side):
    """A logo's shapes as board silkscreen, its origin at board (x, y), k times its size: plain shapes,
    so nothing ties them to the library copy they were scaled from. On the back they are mirrored left
    to right, so the logo reads the right way up from the back; a ring keeps its 0.15 mm line."""
    sx, layer = (-1, "B.SilkS") if side == "B" else (1, "F.SilkS")
    ox, oy = page(x, y)

    def at(lx, ly):
        return ox + sx * float(lx) * k, oy + float(ly) * k
    body, out = _logo(name)[1], []
    for pts in re.findall(r"\(fp_poly \(pts (.*?)\) \(stroke", body):
        xy = " ".join("(xy {} {})".format(*map(f, at(a, b))) for a, b in re.findall(r"\(xy ([\-\d.]+) ([\-\d.]+)\)", pts))
        out.append(f'\t(gr_poly (pts {xy}) (stroke (width 0) (type solid)) (fill yes) (layer "{layer}") (uuid "{uid()}"))')
    for cx, cy, ex, w in re.findall(r"\(fp_circle \(center ([\-\d.]+) ([\-\d.]+)\) \(end ([\-\d.]+) [\-\d.]+\) \(stroke \(width ([\d.]+)\)", body):
        r, w = abs(float(ex) - float(cx)), float(w)
        r = r * k if w == 0 else (r + w / 2) * k - w / 2
        x0, y0 = at(cx, cy)
        out.append(f'\t(gr_circle (center {f(x0)} {f(y0)}) (end {f(x0 + r)} {f(y0)}) (stroke (width {f(w)}) (type solid)) '
                   f'(fill {"yes" if w == 0 else "no"}) (layer "{layer}") (uuid "{uid()}"))')
    return out


def gr_text(s, x, y, layer, size=1.0, rot=0, width=None):
    """size is the height; width, if given, the characters' width (KiCad writes size as height, width)"""
    px, py = page(x, y)
    j = " (justify mirror)" if layer.startswith("B.") else ""
    return (f'\t(gr_text "{s}" (at {f(px)} {f(py)}{" " + f(rot) if rot else ""}) (layer "{layer}") (uuid "{uid()}") '
            f'(effects (font (size {f(size)} {f(width or size)}) (thickness {f(0.15 if size >= 1 else 0.12)})){j}))')


def gr_rect(x0, y0, x1, y1, layer, width=0.12, fill=False):
    a, b = page(x0, y0), page(x1, y1)
    return (f'\t(gr_rect (start {f(a[0])} {f(a[1])}) (end {f(b[0])} {f(b[1])}) (stroke (width {f(width)}) (type default)) '
            f'(fill {"yes" if fill else "no"}) (layer "{layer}") (uuid "{uid()}"))')


def gr_line(x0, y0, x1, y1, layer, width=0.12):
    a, b = page(x0, y0), page(x1, y1)
    return (f'\t(gr_line (start {f(a[0])} {f(a[1])}) (end {f(b[0])} {f(b[1])}) (stroke (width {f(width)}) (type default)) '
            f'(layer "{layer}") (uuid "{uid()}"))')


def outline_text():
    x0, y0, x1, y1 = rect_page(0, 0, W, H)
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


def shell_keepout_text(pts):
    """A rule area under J1's shell on the front: no track and no via there, so a router can't put
    one under its metal; the ground pour and J1's own pads may be."""
    p = " ".join(f"(xy {f(x)} {f(y)})" for x, y in pts)
    return (f'\t(zone (net 0) (net_name "") (layers "F.Cu") (uuid "{uid()}") (name "J1 shell: no tracks") (hatch edge 0.5)\n'
            f'\t\t(connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no)\n'
            f'\t\t(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour allowed) (footprints allowed))\n'
            f'\t\t(placement (enabled no) (sheetname ""))\n'
            f'\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
            f'\t\t(polygon (pts {p}))\n\t)')


def hole_keepout_text(ref, c, n=24):
    """A ring round a mounting hole on both layers: no track and no via under a screw head or washer
    (HOLE_RING); the ground pour may. The polygon is drawn outside the circle."""
    r = HOLE_RING / math.cos(math.pi / n)
    p = " ".join(f"(xy {f(x)} {f(y)})" for x, y in (page(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n))
                                                   for k in range(n)))
    return (f'\t(zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (uuid "{uid()}") (name "{ref}: no tracks") (hatch edge 0.5)\n'
            f'\t\t(connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no)\n'
            f'\t\t(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour allowed) (footprints allowed))\n'
            f'\t\t(placement (enabled no) (sheetname ""))\n'
            f'\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
            f'\t\t(polygon (pts {p}))\n\t)')


def art_keepout_text():
    """No via under the art, on either layer (tracks may: they're under the mask), 0.2 mm round each
    sprite: one rule area each, so the stitching keeps the vias between them."""
    out = []
    for rows, ax, ay in ART:
        x0, y0 = ax - 0.2, ay - len(rows) * PIXEL - 0.2
        x1, y1 = ax + len(rows[0]) * PIXEL + 0.2, ay + 0.2
        p = " ".join(f"(xy {f(x)} {f(y)})" for x, y in (page(x0, y0), page(x1, y0), page(x1, y1), page(x0, y1)))
        out.append(f'\t(zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (uuid "{uid()}") (name "Art: no vias") (hatch edge 0.5)\n'
                   f'\t\t(connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no)\n'
                   f'\t\t(keepout (tracks allowed) (vias not_allowed) (pads allowed) (copperpour allowed) (footprints allowed))\n'
                   f'\t\t(placement (enabled no) (sheetname ""))\n'
                   f'\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
                   f'\t\t(polygon (pts {p}))\n\t)')
    return out


def keepout_text(pts):
    p = " ".join(f"(xy {f(x)} {f(y)})" for x, y in pts)
    return (f'\t(zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (uuid "{uid()}") (name "Antenna: no copper") (hatch edge 0.5)\n'
            f'\t\t(connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no)\n'
            f'\t\t(keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed))\n'
            f'\t\t(placement (enabled no) (sheetname ""))\n'
            f'\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
            f'\t\t(polygon (pts {p}))\n\t)')


LABELS = {"SW1": "D0", "SW3": "D2", "SW4": "BOOT", "SW5": "RESET"}   # D1 sits between D0 and D2


def label_y(ref):
    """A button's label goes outside it, but RESET's above it, between its outline and R8, C7: C3 and
    C4 are below. render.py draws them here too."""
    y = PARTS[ref]["at"][1]
    return y + 3.48 if ref == "SW5" else y + 3.55 if y > YC else y - 3.55


# The brand on the silkscreen (docs/BRAND.md). The mark, the right way up, on the front of the antenna
# end, where nothing else is; the name above the glass, on the button labels' line. On the back the
# lockup, the mark left of the name in the panel's proportions (at a 26 px name, the ring's radius is
# 12 px, its centre 13 px in from the left, the name 34 px in), and under it a tagline, the board and
# its licence, and the Source Location.
MARK, NAME_FP = "PicoQuorum_Mark", "PicoQuorum_Name"   # the key library's mark, 5.0 mm tall; wordmark.py's name
CAP_EM = 0.669           # Atkinson Hyperlegible Next: its cap height in em
FRONT_CAP = 1.3          # the name's cap height, mm: its letters are 0.16 mm apart at the closest (JLCPCB: 0.15)
BACK_CAP = 2.3
LOCKUP = (34.5, 14.4)    # the back's mark: its ring's centre, board mm; the lockup reads leftward in board x
TAGLINE = "Nothing signs unseen"                      # one of docs/BRAND.md's draft taglines


def mark_ring():
    """The mark's ring: its radius and how far its centre is below the middle of the mark, at 5.0 mm"""
    dots = [(float(y), float(e) - float(x)) for x, y, e in re.findall(
        r"\(fp_circle \(center ([\-\d.]+) ([\-\d.]+)\) \(end ([\-\d.]+) [\-\d.]+\) \(stroke \(width 0\)", _logo(MARK)[1])]
    top, low = min(y for y, _ in dots), max(y for y, _ in dots)       # the signed dots: -90 deg, 54 and 126
    r = (low - top) / (1 + math.sin(math.radians(54)))
    return r, top + r


def silk_logos():
    """(footprint, board x, y of its origin, scale, side): the origin is the middle of each."""
    r, dy = mark_ring()
    em = BACK_CAP / CAP_EM
    k = 12 / 26 * em / r
    adv = float(re.search(r"([\d.]+) mm of advance", _logo(NAME_FP)[0]).group(1)) * BACK_CAP
    mx, my = LOCKUP
    return [(MARK, (KEEPOUT[0] + W) / 2, YC, 1.0, "F"),
            (NAME_FP, (GLASS[0] + GLASS[2]) / 2, label_y("SW1"), FRONT_CAP, "F"),
            (MARK, mx, my + dy * k, k, "B"),
            (NAME_FP, mx - (34 - 13) / 26 * em - adv / 2, my, BACK_CAP, "B")]


def silk_texts():
    """(text, board x, y, side): the buttons' labels; the lines under the lockup, centred on it; the
    test pads' names."""
    em = BACK_CAP / CAP_EM
    adv = float(re.search(r"([\d.]+) mm of advance", _logo(NAME_FP)[0]).group(1)) * BACK_CAP
    mx, my = LOCKUP
    cx = (mx + 13 / 26 * em + mx - (34 - 13) / 26 * em - adv) / 2
    out = [(label, PARTS[ref]["at"][0], label_y(ref), "F") for ref, label in LABELS.items()]
    out += [(TAGLINE, cx, my - 3.0, "B"), ("console-s3 rev A · CERN-OHL-W 2.0", cx, my - 4.8, "B"), (SRC, cx, my - 6.6, "B")]
    for ref, label, _net in TESTPADS:
        x, y = PARTS[ref]["at"]
        out.append((label, x, y - 1.75 if y > YC else y + 1.75, "B"))
    return out


# A nod to Adventure (Atari 2600, 1980), hidden under the glass: an 8-bit key just below U2, the key
# that signs, and a dragon guarding it, drawn here in the game's manner, not copied from it. Rows as
# they read from the front, top first; a pixel is 0.3 mm, so every gap is twice JLCPCB's 0.15 mm.
# No via goes under it (art_keepout_text): the ground stitching would put holes through the dragon.
DRAGON = ("....###.",
          "#####.#.",
          "....###.",
          ".....#..",
          ".....#..",
          "....##..",
          "...###..",
          "..####..",
          ".#####..",
          ".#####..",
          ".#####..",
          "..####..",
          "...###..",
          "....##..",
          ".....#..",
          ".....#..",
          ".....#..",
          ".....#..",
          ".....#.#",
          ".....###")
KEY = (".##......",
       "#..######",
       "#..#..#.#",
       ".##......")
PIXEL = 0.3
ART = [(KEY, 21.65, 14.6), (DRAGON, 25.15, 14.3)]    # board (x, y) of each one's top left: the key under U2's
                                                    # pads, the dragon between it and J2, below the via at (25.75, 15.0)


def silk_pixels():
    """The art as filled rectangles (board x0, y0, x1, y1, side): each run of pixels in a row, carried
    down while the row below has the same run."""
    out = []
    for rows, ax, ay in ART:
        running = {}
        for r, row in enumerate(rows + ("",)):
            now = {m.span() for m in re.finditer(r"#+", row)}
            for c0, c1 in [k for k in running if k not in now]:
                r0 = running.pop((c0, c1))
                out.append((ax + c0 * PIXEL, ay - r * PIXEL, ax + c1 * PIXEL, ay - r0 * PIXEL, "F"))
            for span in now - running.keys():
                running[span] = r
    return out


def write_board(uids):
    names = sorted(set(NETS.values()))
    nets = {n: i + 1 for i, n in enumerate(names)}
    layers, setup = _template_blocks()
    out = ["(kicad_pcb", "\t(version 20241229)", '\t(generator "picoquorum_gen")', '\t(generator_version "9.0")',
           "\t(general (thickness 1.6) (legacy_teardrops no))", '\t(paper "A4")',
           f'\t(title_block (title "{TITLE}") (date "{DATE}") (rev "A") (company "PicoQuorum") (comment 1 "{NOTE}"))',
           layers, setup, '\t(net 0 "")']
    out += [f'\t(net {i} "{n}")' for n, i in nets.items()]
    for ref, p in all_parts().items():
        out.append(footprint_text(ref, p, nets, uids.get(ref)))
    for name, x, y, k, side in silk_logos():
        out += logo_items(name, x, y, k, side)
    out.append(outline_text())
    # the glass, on the front silk by its corners, and its ribbon's fold on the fab layer
    gx0, gy0, gx1, gy1 = GLASS
    for x, dx in ((gx0, 2.5), (gx1, -2.5)):
        for y, dy in ((gy0, 2.0), (gy1, -2.0)):
            out.append(gr_line(x, y, x + dx, y, "F.SilkS", 0.15))
            out.append(gr_line(x, y, x, y + dy, "F.SilkS", 0.15))
    out.append(gr_rect(gx0, gy0, gx1, gy1, "F.Fab", 0.1))
    out.append(gr_text("panel glass on tape: the ribbon folds under at the right end", (gx0 + gx1) / 2, gy1 - 1.0, "F.Fab", 0.6))
    for text, x, y, side in silk_texts():
        out.append(gr_text(text, x, y, f"{side}.SilkS", SILK_H, width=SILK_W))
    for x0, y0, x1, y1, side in silk_pixels():
        out.append(gr_rect(x0, y0, x1, y1, f"{side}.SilkS", 0, fill=True))
    out.append(gr_text("ESP32-S3 here, antenna at the edge", W - MOD_L / 2, YC, "B.Fab", 0.8))
    # the hand-drawn escapes, locked
    for net, layer, pts in ESCAPE:
        for a, b in zip(pts, pts[1:]):
            (ax, ay), (bx, by) = page(*a), page(*b)
            out.append(f'\t(segment (start {f(ax)} {f(ay)}) (end {f(bx)} {f(by)}) (width {f(TRACK)}) (layer "{layer}") (locked yes) '
                       f'(net {nets[net]}) (uuid "{uid()}"))')
    for net, x, y in ESCAPE_VIAS:
        px, py = page(x, y)
        out.append(f'\t(via (at {f(px)} {f(py)}) (size {f(VIA)}) (drill {f(DRILL)}) (layers "F.Cu" "B.Cu") (locked yes) '
                   f'(net {nets[net]}) (uuid "{uid()}"))')
    # pours, and the antenna's rule area on both layers
    x0, y0, x1, y1 = rect_page(0, 0, KEEPOUT[0], H)
    whole = [(x0 - 1, y0 - 1), (x1, y0 - 1), (x1, y1 + 1), (x0 - 1, y1 + 1)]
    out.append(zone_text(nets["GND"], "GND", "F.Cu", "GND top", whole))
    out.append(zone_text(nets["GND"], "GND", "B.Cu", "GND bottom", whole))
    kx0, ky0, kx1, ky1 = rect_page(*KEEPOUT)
    out.append(keepout_text([(kx0, ky0 - 1), (kx1 + 1, ky0 - 1), (kx1 + 1, ky1 + 1), (kx0, ky1 + 1)]))
    sx0, sy0, sx1, sy1 = j1_body()
    out.append(shell_keepout_text([(sx0 - 1, sy0), (sx1, sy0), (sx1, sy1), (sx0 - 1, sy1)]))
    for ref, c in HOLES:
        out.append(hole_keepout_text(ref, c))
    out += art_keepout_text()
    out += ["\t(embedded_fonts no)", ")"]
    with open(os.path.join(OUT, NAME + ".kicad_pcb"), "w") as fh:
        fh.write("\n".join(out) + "\n")


def write_project(sheet_uuid):
    d = json.load(open(os.path.join(REPO, "hardware", "key-pcb", "key-b-udfn", "key-b-udfn.kicad_pro")))
    d["meta"]["filename"] = NAME + ".kicad_pro"
    d["board"]["design_settings"]["rules"].update(gen.JLC_RULES)
    # the router joins every ground pad with tracks (the check says so), so where the routing leaves
    # a ground pad's thermal room for one spoke, one will do
    d["board"]["design_settings"]["rules"]["min_resolved_spokes"] = 1
    # JLCPCB's silkscreen limits (tools/jlc/limits.py), which the board already meets: KiCad's own DRC
    # holds it to them too
    d["board"]["design_settings"]["rules"].update(min_text_height=1.0, min_text_thickness=0.15, min_silk_clearance=0.15)
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
                 f'(options "")(descr "PicoQuorum console-s3 parts"))\n)\n')
    with open(os.path.join(OUT, "fp-lib-table"), "w") as fh:
        fh.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{L}")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/{L}.pretty")'
                 f'(options "")(descr "PicoQuorum console-s3 footprints"))\n'
                 f'  (lib (name "picoquorum")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/picoquorum.pretty")'
                 f'(options "")(descr "The PicoQuorum mark"))\n)\n')


# =================================================================================================
# Checks: read the written schematic and board back, as KiCad will
# =================================================================================================

def check_schematic(path):
    """Every symbol pin's net, worked out from the schematic's wires, labels, power symbols and
    no-connect flags, against NETS (gen_wing.py's check). A stand-in for ERC and parity, not either."""
    tree = gen_cd._sexpr(open(path).read())
    kids = gen_cd._kids
    lib = {}
    for sym in kids(kids(tree, "lib_symbols")[0], "symbol"):
        pins = {}
        for unit in kids(sym, "symbol"):
            for pin in kids(unit, "pin"):
                at = kids(pin, "at")[0]
                pins[kids(pin, "number")[0][1]] = (float(at[1]), float(at[2]))
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
        got = (want if want and want.startswith("unconnected") else "a no-connect flag") if pt in ncs else names.get(find(pt))
        if got != want:
            problems.append(f"schematic: {ref}.{num} is on {got}, NETS says {want}")
    missing = {(r, n) for r, n in NETS} - {(r, n) for r, n, _p in pins}
    problems += [f"schematic: no pin {r}.{n}" for r, n in sorted(missing)]
    print(f"{NAME}: schematic {len(pins)} pins, " + (f"{len(problems)} problem(s)" if problems else "every pin on its net in NETS"))
    for p in problems[:30]:
        print("   -", p)
    return not problems


def check(path, prof):
    tree = gen_cd._sexpr(open(path).read())
    kids = gen_cd._kids

    def node(n, k):
        v = kids(n, k)
        return v[0] if v else None
    # the generator writes (net 3 "GND"); KiCad 10, saving the board, writes (net "GND")
    nets = {int(n[1]): n[2] for n in kids(tree, "net") if len(n) > 2}
    netof = lambda n: n[-1] if len(n) == 2 and not n[1].lstrip("-").isdigit() else nets[int(n[1])] if len(n) == 2 else n[2]
    pads, sides, segs, vias = [], {}, [], []
    for fp in kids(tree, "footprint"):
        ref = next(p[2] for p in kids(fp, "property") if p[1] == "Reference")
        at = node(fp, "at")
        px, py, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        sides[ref] = "B" if node(fp, "layer")[1] == "B.Cu" else "F"
        for pad in kids(fp, "pad"):
            pat, size = node(pad, "at"), node(pad, "size")
            w, h = float(size[1]), float(size[2])
            if round(rot) % 180:
                w, h = h, w
            dx, dy = rotate(float(pat[1]), float(pat[2]), rot)      # the file already holds a back part's flipped y
            cx, cy = px + dx, py + dy
            lays = {l for l in node(pad, "layers")[1:] if l.endswith(".Cu")}
            if "*.Cu" in lays:
                lays = {"F.Cu", "B.Cu"}
            netv = node(pad, "net")
            k = 0.5 / math.sqrt(2) if pad[3] == "circle" else 0.5
            dr = node(pad, "drill")
            dw, dh = (float(dr[2]), float(dr[3])) if dr and dr[1] == "oval" else (float(dr[1]), float(dr[1])) if dr else (0, 0)
            if round(rot) % 180:
                dw, dh = dh, dw
            if lays or pad[2] == "np_thru_hole":
                rect = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                rr = float(node(pad, "roundrect_rratio")[1]) * min(w, h) if pad[3] == "roundrect" else 0.0
                pads.append(dict(ref=ref, num=pad[1], kind=pad[2], net=netof(netv) if netv else None, layers=lays or {"F.Cu", "B.Cu"},
                                 rect=rect, centre=(cx, cy), hit=(cx - k * w, cy - k * h, cx + k * w, cy + k * h),
                                 shape=capsule(cx, cy, w, h) if pad[3] in ("circle", "oval")
                                 else ("rect", rect[0] + rr, rect[1] + rr, rect[2] - rr, rect[3] - rr, rr),
                                 hole=capsule(cx, cy, dw, dh) if pad[2] == "thru_hole" else None))
    for sg in kids(tree, "segment"):
        a, b, w = node(sg, "start"), node(sg, "end"), float(node(sg, "width")[1])
        ax, ay, bx, by = float(a[1]), float(a[2]), float(b[1]), float(b[2])
        locked = "locked" in sg or (node(sg, "locked") or [0, "no"])[1] == "yes"
        segs.append(dict(net=netof(node(sg, "net")), layer=node(sg, "layer")[1], a=(ax, ay), b=(bx, by), r=w / 2, locked=locked,
                         rect=(min(ax, bx) - w / 2, min(ay, by) - w / 2, max(ax, bx) + w / 2, max(ay, by) + w / 2),
                         shape=("cap", (ax, ay), (bx, by), w / 2)))
    for v in kids(tree, "via"):
        at = node(v, "at")
        x, y, d, dd = float(at[1]), float(at[2]), float(node(v, "size")[1]), float(node(v, "drill")[1])
        vias.append(dict(net=netof(node(v, "net")), at=(x, y), r=d / 2, rect=(x - d / 2, y - d / 2, x + d / 2, y + d / 2),
                         shape=("cap", (x, y), (x, y), d / 2), hole=("cap", (x, y), (x, y), dd / 2)))
    problems = []
    # 1. copper of different nets apart, and copper clear of the plain holes
    items = [(p["kind"], p["net"], p["layers"], p["rect"], f'{p["ref"]}.{p["num"] or "-"}', p["ref"], p["shape"]) for p in pads]
    items += [("seg", s["net"], {s["layer"]}, s["rect"], f'track {s["net"]} at {s["a"]}', None, s["shape"]) for s in segs]
    items += [("via", v["net"], {"F.Cu", "B.Cu"}, v["rect"], f'via {v["net"]} at {v["at"]}', None, v["shape"]) for v in vias]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if not (a[2] & b[2]):
                continue
            hole = "np_thru_hole" in (a[0], b[0])
            if hole and (a[0] == b[0] or a[5] is not None and a[5] == b[5]):
                continue        # a part's own locating holes: the maker's pattern (J1's, as key-c's board has it)
            if not hole and (a[1] is not None and a[1] == b[1] or a[4] == b[4] and a[5] is not None):
                continue
            need = (0.5 if "via" in (a[0], b[0]) else HOLE_CLEAR) if hole else CLEAR
            if _gap(a[3], b[3]) >= need:
                continue
            g = max(0.0, copper_gap(a[6], b[6]))
            if g < need - 1e-6:
                problems.append(f"clearance {g:.3f} mm between {a[4]} and {b[4]} (needs {need})")
    # 2. copper to the edge; nothing in the antenna keep-out on either side; no front track or via
    #    of another net under J1's shell
    keep = rect_page(*KEEPOUT)
    for kind, net, lays, rect, name, _ref, _shape in items:
        if kind != "np_thru_hole" and not edge_ok(rect, EDGE - 1e-6):
            problems.append(f"{name} within {EDGE} mm of the edge")
        if _gap(rect, keep) < 1e-6:
            problems.append(f"{name} in the antenna keep-out")
        if kind in ("seg", "via") and net != "GND" and "F.Cu" in lays and _gap(rect, j1_body()) < 1e-6:
            problems.append(f"{name} under J1's shell")
        for ref, c in HOLES:
            pc = page(*c)
            if kind in ("seg", "via") and copper_gap(_shape, ("cap", pc, pc, HOLE_RING)) < -1e-6:
                problems.append(f"{name} inside {ref}'s ring ({HOLE_RING} mm)")
    # 2b. no track narrower than JLCPCB makes
    for s_ in segs:
        if 2 * s_["r"] < MIN_TRACK - 1e-6:
            problems.append(f'track {s_["net"]} on {s_["layer"]} {2 * s_["r"]:.3f} mm wide (JLCPCB: {MIN_TRACK})')
    # 3. a track end or a via inside a pad of another net is a short
    for s_ in segs:
        for p in pads:
            if s_["layer"] in p["layers"] and p["net"] != s_["net"] and p["kind"] != "np_thru_hole":
                for pt in (s_["a"], s_["b"]):
                    if p["rect"][0] <= pt[0] <= p["rect"][2] and p["rect"][1] <= pt[1] <= p["rect"][3]:
                        problems.append(f'track {s_["net"]} ends inside {p["ref"]}.{p["num"]}')
    for v in vias:
        for p in pads:
            if p["kind"] == "smd" and copper_gap(v["shape"], p["shape"]) < 1e-6:
                problems.append(f'via {v["net"]} in pad {p["ref"]}.{p["num"]}')
    # 3b. a via's hole HOLE_GAP from every other drilled hole, whatever its net
    holes = [(f'via {v["net"]} at {v["at"]}', v["hole"]) for v in vias]
    for k, (name, hole) in enumerate(holes):
        for other, h2 in holes[k + 1:] + [(f'{p["ref"]}.{p["num"]}', p["hole"]) for p in pads if p["hole"]]:
            if copper_gap(hole, h2) < HOLE_GAP - 1e-6:
                problems.append(f"{name}'s hole {copper_gap(hole, h2):.3f} mm from {other}'s (needs {HOLE_GAP})")
    # 4. connectivity, by union-find over pads, tracks and vias, as KiCad joins them: a track at its
    #    ends, to a pad they lie in or a track or via they touch. Ground too: the pours aren't counted.
    #    A board not yet routed, whose only tracks are the locked escapes, says how much is left.
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def inside(pt, rect):
        return rect[0] - 1e-6 <= pt[0] <= rect[2] + 1e-6 and rect[1] - 1e-6 <= pt[1] <= rect[3] + 1e-6
    for i, s_ in enumerate(segs):
        for j, p in enumerate(pads):
            if s_["layer"] in p["layers"] and p["net"] == s_["net"] and (inside(s_["a"], p["hit"]) or inside(s_["b"], p["hit"])):
                parent[find(("s", i))] = find(("p", j))
        for k, t in enumerate(segs):
            if k > i and t["layer"] == s_["layer"] and t["net"] == s_["net"] and (
                    any(_pt_seg(pt, t["a"], t["b"]) <= t["r"] + 1e-6 for pt in (s_["a"], s_["b"]))
                    or any(_pt_seg(pt, s_["a"], s_["b"]) <= s_["r"] + 1e-6 for pt in (t["a"], t["b"]))):
                parent[find(("s", i))] = find(("s", k))
        for m, v in enumerate(vias):
            if v["net"] == s_["net"] and _pt_seg(v["at"], s_["a"], s_["b"]) <= s_["r"] + v["r"] + 1e-6 and (
                    _pt_seg(v["at"], s_["a"], s_["b"]) <= s_["r"] + 1e-6 or min(math.dist(v["at"], s_["a"]), math.dist(v["at"], s_["b"])) <= v["r"] + 1e-6):
                parent[find(("s", i))] = find(("v", m))
    for m, v in enumerate(vias):
        for j, p in enumerate(pads):
            if p["kind"] == "thru_hole" and p["net"] == v["net"] and inside(v["at"], p["hit"]):
                parent[find(("v", m))] = find(("p", j))
    for j, p in enumerate(pads):        # pads of one net that overlap, as J1's paired ground pins do
        for k in range(j + 1, len(pads)):
            q = pads[k]
            if p["net"] and p["net"] == q["net"] and p["layers"] & q["layers"] and copper_gap(p["shape"], q["shape"]) < -1e-6:
                parent[find(("p", j))] = find(("p", k))
    by_net = {}
    for j, p in enumerate(pads):
        if p["net"] and not p["net"].startswith("unconnected"):
            by_net.setdefault(p["net"], []).append(j)
    routed = any(not s_["locked"] for s_ in segs)
    left = 0
    for net, idx in sorted(by_net.items()):
        roots = {find(("p", j)) for j in idx}
        left += len(roots) - 1
        if routed and len(roots) > 1:
            groups = {}
            for j in idx:
                groups.setdefault(find(("p", j)), []).append(f'{pads[j]["ref"]}.{pads[j]["num"]}')
            problems.append(f"net {net} is in {len(roots)} pieces: " + " | ".join(", ".join(g) for g in groups.values()))
    yards = courtyards()
    for ref, side, r in yards:
        if ref != "U1" and min(r[2], keep[2]) - max(r[0], keep[0]) > 1e-6 and min(r[3], keep[3]) - max(r[1], keep[1]) > 1e-6:
            problems.append(f"{ref}'s courtyard reaches into the antenna keep-out")
    # 5. the net table on the board is the schematic's
    on_board = {(p["ref"], p["num"]): p["net"] for p in pads if p["num"]}
    for k, net in NETS.items():
        if on_board.get(k) != net:
            problems.append(f"pad {k} carries {on_board.get(k)} on the board, {net} in NETS")
    # 6. courtyards on the same side don't overlap
    for i in range(len(yards)):
        for j in range(i + 1, len(yards)):
            (ra, sa, a), (rb, sb, b) = yards[i], yards[j]
            both = sa == sb or "H" in (ra[0], rb[0])
            if ra != rb and both and min(a[2], b[2]) - max(a[0], b[0]) > 1e-6 and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6:
                problems.append(f"courtyards of {ra} and {rb} overlap")
    # 7. one-sided assembly: everything JLCPCB places on the front; the module on the back
    for ref, p in PARTS.items():
        if p["in_bom"] and sides.get(ref) != "F":
            problems.append(f"{ref} is in the BOM but on the back: JLCPCB's Economic assembly is one side")
    if sides.get("U1") != "B":
        problems.append("the module isn't on the back")
    # 8. under the glass, only parts lower than the tape
    glass = rect_page(*GLASS)
    for ref, side, r in yards:
        p = all_parts()[ref]
        if side == "F" and min(r[2], glass[2]) - max(r[0], glass[0]) > 1e-6 and min(r[3], glass[3]) - max(r[1], glass[1]) > 1e-6:
            h = HEIGHT.get(p["fp"], 99)
            if h > PANEL["foam"] - 0.3:
                problems.append(f"{ref} ({h} mm) is under the glass, whose tape is {PANEL['foam']} mm")
    # 9. silkscreen text and the logos off the pads and on the board, by a rough box (gen_wing.py's)
    for t in kids(tree, "gr_text"):
        at, layer = node(t, "at"), node(t, "layer")[1]
        if not layer.endswith("SilkS"):
            continue
        font = node(node(t, "effects"), "font")
        hgt, wid = float(node(font, "size")[1]), float(node(font, "size")[2])
        if hgt < 1.0 - 1e-6 or float(node(font, "thickness")[1]) < 0.15 - 1e-6:
            problems.append(f'silkscreen "{t[1]}" under JLCPCB\'s 1.0 mm tall, 0.15 mm stroke')
        x, y = float(at[1]), float(at[2])
        hw, hh = len(t[1]) * wid * 0.85 / 2, hgt / 2
        box = (x - hw, y - hh, x + hw, y + hh)
        side = "F.Cu" if layer.startswith("F.") else "B.Cu"
        for p in pads:
            if side in p["layers"] and p["kind"] != "np_thru_hole" and _gap(box, p["rect"]) < 0.15:
                problems.append(f'silkscreen "{t[1]}" over pad {p["ref"]}.{p["num"]}')
        if not edge_ok(box, 0.2):
            problems.append(f'silkscreen "{t[1]}" off the board')
    for g in kids(tree, "gr_poly") + kids(tree, "gr_circle") + kids(tree, "gr_rect"):   # the logos and the art, by their boxes
        layer = node(g, "layer")[1]
        if not layer.endswith("SilkS"):
            continue
        if g[0] == "gr_poly":
            pts = [(float(q[1]), float(q[2])) for q in kids(node(g, "pts"), "xy")]
        elif g[0] == "gr_rect":
            pts = [(float(node(g, k)[1]), float(node(g, k)[2])) for k in ("start", "end")]
        else:
            (cx, cy), e = (float(v) for v in node(g, "center")[1:3]), node(g, "end")
            r = math.dist((cx, cy), (float(e[1]), float(e[2]))) + float(node(node(g, "stroke"), "width")[1]) / 2
            pts = [(cx - r, cy - r), (cx + r, cy + r)]
        box = (min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts), max(y for _, y in pts))
        name = f"silkscreen {g[0][3:]} at board ({box[0] - OX:.1f}, {OY - box[3]:.1f})"
        side = "F.Cu" if layer.startswith("F.") else "B.Cu"
        for p in pads:
            if side in p["layers"] and p["kind"] != "np_thru_hole" and _gap(box, p["rect"]) < 0.15:
                problems.append(f'{name} over pad {p["ref"]}.{p["num"]}')
        if not edge_ok(box, 0.2):
            problems.append(f"{name} off the board")
    # 10. the buttons level with the rails the firmware draws (board.RAIL_Y), D0 at the top
    for ref, want in zip(("SW1", "SW2", "SW3"), rail_y()):
        got = next(to_board(p["centre"]) for p in pads if p["ref"] == ref and p["num"] == "1")
        centre_y = round(got[1] - 1.875, 3)
        if abs(centre_y - want) > 0.05:
            problems.append(f"{ref} sits at y {centre_y}, its rail at {want:.3f}")
    # 11. the module: pins where Espressif's drawing puts them, its antenna end at the board's edge
    mod = {p["num"]: to_board(p["centre"]) for p in pads if p["ref"] == "U1"}
    end = W                     # the antenna end, flush with the right edge; pins 1-14 along the bottom edge
    e = PAD_IRON / 2      # each pad's centre moves out by half what it gained for the iron
    want = {"1": (end - 7.49, YC - 8.75 - e), "14": (end - 7.49 - 16.51, YC - 8.75 - e),
            "15": (end - MOD_L + 0.25 - e, YC - MOD_W / 2 + 2.015), "26": (end - MOD_L + 0.25 - e, YC + MOD_W / 2 - 2.015),
            "27": (end - 7.49 - 16.51, YC + 8.75 + e), "40": (end - 7.49, YC + 8.75 + e)}
    for n, (x, y) in want.items():
        gx, gy = mod[n]
        if abs(gx - x) > 0.005 or abs(gy - y) > 0.005:
            problems.append(f"module pin {n} at ({gx}, {gy}), Espressif's drawing puts it at ({x:.3f}, {y:.3f})")
    if routed:
        length = sum(math.dist(s_["a"], s_["b"]) for s_ in segs)
        print(f"{NAME}: {len(pads)} pads, {len(by_net)} nets, {len(segs)} tracks ({length:.0f} mm), {len(vias)} vias")
    else:
        print(f"{NAME}: {len(pads)} pads, {len(by_net)} nets, {left} connections to route (the escapes drawn, the rest unrouted)")
    print("  module pins 1/14/15/26/27/40 (board mm):", ", ".join(f"{n} at {mod[n]}" for n in ("1", "14", "15", "26", "27", "40")))
    print("  buttons D0/D1/D2 at y", ", ".join(f"{v:.3f}" for v in rail_y()), f"(rails {prof['RAIL_Y']}, {ROW:.4f} mm a row)")
    if problems:
        print(f"  {len(problems)} problem(s):")
        for p in problems[:60]:
            print("   -", p)
        return False
    print("  checks clean: clearance, track widths, holes, edge, antenna keep-out, J1's shell, the holes' rings, shorts, " + ("connectivity, " if routed else "")
          + "net table, courtyards, one-sided assembly, under the glass, silkscreen, the rails, the module's pins")
    return True


# =================================================================================================
# What `tools/keypcb jlc` needs to know about this board that the board file doesn't say
# =================================================================================================

GLASS_T = 1.6             # the panel's glass, mm: a 1.14" module's usual, not measured (DESIGN.md: 3.6 mm proud with the tape)
RIBBON_W = 4.5            # the ribbon's tail, back to J2 (ER-TFT1.14-2's drawing)
FOLD_W = 9.1              # the ribbon where it bends round the glass's end (the same drawing)
FOLD_R = 0.5              # the fold stands at most this far past the glass's right end (the same drawing)
FOLD_Y = (YC + 8.8 - 14.5, YC + 8.8 - 5.4)   # it is 5.4 to 14.5 mm from the top of the drawing's 17.6 mm glass


def jlc_spec():
    """The board's numbers for tools/jlc: the mounting holes' rings, the regulator's heat, the nets
    whose return path to report, and the 3D fit (datasheet and guessed sizes, z up from the front)."""
    t = 1.6
    screw = [{"name": f"{ref} screw head", "cyl": [x, y, 1.9], "z": [0.0, 2.0]} for ref, (x, y) in HOLES]   # DIN 912 M2: 3.8 x 2.0
    screw += [{"name": f"{ref} nut", "cyl": [x, y, 2.2], "z": [-t - 1.6, -t]} for ref, (x, y) in HOLES]  # M2 nut, 4.4 across corners
    return {
        "edge": EDGE,
        "hole_ring": HOLE_RING,
        "regulator": {"ref": "U3", "part": "ME6211C33", "vin": 5.0, "vout": 3.3, "amps": [0.15, 0.45], "theta_ja": 250,
                      "theta_note": "a usual SOT-23-5 figure on its least pad, not the ME6211's own"},
        "return_nets": ["/S3_DP", "/S3_DN", "/USB_DP", "/USB_DN", "/LCD_SCK", "/LCD_MOSI"],
        "jlc_allow": [{"type": "footprint_type_mismatch", "ref": "J1",
                       "why": "marked SMD, as key-c's is, though its shell's tabs go through plated slots: the Gerbers and CPL are right either way"}],
        "fit": {
            "heights": HEIGHT, "default_height": 1.0,
            "back": [{"name": "U1 module", "box": [MOD_AT[0] - MOD_L / 2, MOD_AT[1] - MOD_W / 2, MOD_AT[0] + MOD_L / 2, MOD_AT[1] + MOD_W / 2],
                      "z": [-t - 3.1, -t], "note": "WROOM-1, 18 x 25.5 x 3.1 (datasheet)"}],
            "solids": [{"name": "glass", "box": list(GLASS), "z": [PANEL["foam"], PANEL["foam"] + GLASS_T], "note": "on 2.0 mm tape, 1.6 thick: not measured"},
                       {"name": "ribbon fold", "box": [GLASS[2], FOLD_Y[0], GLASS[2] + FOLD_R, FOLD_Y[1]],
                        "z": [PANEL["foam"], PANEL["foam"] + GLASS_T], "guess": True,
                        "note": "the fold past the glass's end, from ER-TFT1.14-2's drawing (inside the panel's 1.6 mm \"with FPC folded\"): not measured"}] + screw,
            "ribbon_run": [GLASS[2], YC - RIBBON_W / 2, PARTS["J2"]["at"][0], YC + RIBBON_W / 2],
        },
    }


# =================================================================================================

def main():
    path = os.path.join(OUT, NAME + ".kicad_pcb")
    prof = check_firmware()
    place_switches()
    if "--check" in sys.argv[1:]:
        ok = check_schematic(os.path.join(OUT, NAME + ".kicad_sch"))
        sys.exit(0 if check(path, prof) and ok else 1)
    syms = write_symbols()
    write_footprints()
    os.makedirs(OUT, exist_ok=True)
    write_lib_tables()
    sheet_uuid, uids = write_schematic(syms)
    write_board(uids)
    write_project(sheet_uuid)
    ok = check_schematic(os.path.join(OUT, NAME + ".kicad_sch"))
    sys.exit(0 if check(path, prof) and ok else 1)


if __name__ == "__main__":
    main()
