#!/usr/bin/env python3
"""console-usb: the console on one board with no radio in use. An ESP32-S3FH4R2 chip (no module, no
antenna), the Feather's 1.14" screen and three buttons, the ATECC608C soldered on, and a USB-C whose
only data path is a CH340C serial bridge to the S3's UART1. See README.md.

    python3 hardware/console-usb/gen_console_usb.py      (needs KiCad 9: kicad-cli and its stock libraries)

Writes, from the one table below:
  console-usb/console-usb.kicad_sch   the schematic, every part a stock KiCad symbol
  console-usb/console-usb.kicad_pro   the project, with JLCPCB's limits as its rules
  fab/bom.csv                         JLCPCB's BOM format: Comment, Designator, Footprint, LCSC Part #
  PINS.md                             the S3's pins, as the firmware sees them

Then has KiCad read the schematic back (kicad-cli netlist and ERC) and checks every connection
against the table, every symbol pin against its footprint's pads, and the S3's pins against
firmware/board.py's "feather-s3" profile and the S3's strapping rules. It stops on any difference.

The schematic only, so far: no board. The layout is the next step (README.md). Once the schematic
is edited in KiCad, KiCad's file is the source and this script is not run again.
"""
import csv, json, os, re, shutil, subprocess, sys, tempfile, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
NAME = "console-usb"
OUT = os.path.join(HERE, NAME)
KISYM = "/usr/share/kicad/symbols"
KIFP = "/usr/share/kicad/footprints"
DATE = "2026-10-24"
sys.path.insert(0, os.path.join(REPO, "hardware", "key-pcb"))
import gen        # noqa: E402  JLC_RULES

GND, V33, VBUS = "GND", "+3V3", "VBUS"
POWER = (GND, V33, VBUS)

# =================================================================================================
# The one table: every part, its LCSC number and what each of its pins connects to. A pin not listed
# is not connected, on purpose, and gets a no-connect flag. Nets other than the three power nets are
# local labels, which KiCad names "/<net>".
# LCSC numbers and tiers checked on jlcpcb.com on 2026-10-24 (README.md says which).
# =================================================================================================
R0402, C0402, C0805 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0805_2012Metric"
C100N = dict(value="100n", fp=C0402, lcsc="C1525")
C1U = dict(value="1u", fp=C0402, lcsc="C52923")
C10U = dict(value="10u", fp=C0805, lcsc="C15850")
R10K = dict(value="10k", fp=R0402, lcsc="C25744")
R1K = dict(value="1k", fp=R0402, lcsc="C11702")
SW = dict(sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", lcsc="C318884", mpn="TS-1187A-B-A-B")


def cap(ref, top, spec, why=""):
    return dict(ref=ref, sym="Device:C", nets={"1": top, "2": GND}, why=why, **spec)


def res(ref, a, b, spec, why=""):
    return dict(ref=ref, sym="Device:R", nets={"1": a, "2": b}, why=why, **spec)


PARTS = [
    # --- the S3. Pins as Espressif's MINI-1 schematic (its datasheet v1.7, Figure 8-1), which is the
    # same ESP32-S3FH4R2 the Feather's module carries. LNA_IN floats: Espressif's checklist allows it
    # when the firmware never starts the radio. The flash and PSRAM are in the package: SPI* and
    # GPIO26 (SPICS1, the PSRAM's select) stay unconnected.
    dict(ref="U1", sym="MCU_Espressif:ESP32-S3", value="ESP32-S3FH4R2", lcsc="C3013940", mpn="ESP32-S3FH4R2",
         fp="Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP4x4mm_ThermalVias",
         nets={"2": "VDD3P3", "3": "VDD3P3", "4": "CHIP_PU", "20": V33, "29": "VDD_SPI", "46": V33,
               "55": V33, "56": V33, "57": GND, "53": "XTAL_N", "54": "XTAL_P",
               "5": "BTN_D0", "6": "BTN_D1", "7": "BTN_D2", "8": "SDA", "9": "SCL", "18": "LED",
               "23": "LINK_TX", "24": "LINK_RX", "25": "DEV_D-", "26": "DEV_D+",
               "40": "LCD_MOSI", "41": "LCD_SCK", "45": "LCD_DC", "47": "LCD_RST", "48": "LCD_CS",
               "49": "U0TXD", "50": "U0RXD", "51": "LCD_BL"}),
    # its supplies, as Figure 8-1 (the module's own values)
    cap("C1", V33, C10U, "3V3 into VDD3P3"), cap("C2", V33, C1U), cap("C3", V33, C100N),
    dict(ref="L1", sym="Device:R", value="0R", fp=R0402, lcsc="C17168", nets={"1": V33, "2": "VDD3P3"},
         why="Espressif's 2.0 nH RF filter; 0 R while the radio stays off"),
    cap("C4", "VDD3P3", C100N, "at VDD3P3, pins 2-3"),
    cap("C5", V33, C100N, "VDD3P3_RTC, pin 20"), cap("C6", V33, C100N, "VDD3P3_CPU, pin 46"),
    cap("C7", "VDD_SPI", C100N, "VDD_SPI, pin 29: the in-package flash"), cap("C8", "VDD_SPI", C1U),
    cap("C9", V33, C1U, "VDDA, pins 55-56"), cap("C10", V33, dict(value="10n", fp=C0402, lcsc="C15195")),
    # reset: 10k and 1u, the checklist's RC; RESET pulls it low
    res("R1", V33, "CHIP_PU", R10K), cap("C11", "CHIP_PU", C1U),
    dict(ref="SW4", value="RESET", nets={"1": "CHIP_PU", "2": GND}, **SW),
    # the 40 MHz crystal, +-10 ppm as Espressif asks. CL 15 pF: 22 pF each side to start, tuned at
    # bring-up. R2 is the module's 0 R on XTAL_P (the checklist's 24 nH spot).
    dict(ref="Y1", sym="Device:Crystal_GND24", value="40MHz", fp="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
         lcsc="C9010", mpn="X322540MPB4SI", nets={"1": "XTAL_IN", "3": "XTAL_N", "2": GND, "4": GND}),
    res("R2", "XTAL_P", "XTAL_IN", dict(value="0R", fp=R0402, lcsc="C17168")),
    cap("C12", "XTAL_IN", dict(value="22p", fp=C0402, lcsc="C1555")),
    cap("C13", "XTAL_N", dict(value="22p", fp=C0402, lcsc="C1555")),

    # --- power: USB-C in, 5 V to 3.3 V. CC1 and CC2 at 5.1k: a sink, so a C-to-C cable gives 5 V.
    dict(ref="J1", sym="Connector:USB_C_Receptacle_USB2.0_16P", value="USB-C",
         fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948", mpn="TYPE-C-31-M-12",
         nets={"A1": GND, "A12": GND, "B1": GND, "B12": GND, "S1": GND,
               "A4": VBUS, "A9": VBUS, "B4": VBUS, "B9": VBUS, "A5": "CC1", "B5": "CC2",
               "A6": "USB_D+", "B6": "USB_D+", "A7": "USB_D-", "B7": "USB_D-"}),
    res("R3", "CC1", GND, dict(value="5.1k", fp=R0402, lcsc="C25905")),
    res("R4", "CC2", GND, dict(value="5.1k", fp=R0402, lcsc="C25905")),
    dict(ref="U2", sym="Power_Protection:USBLC6-2SC6", value="USBLC6-2SC6", fp="Package_TO_SOT_SMD:SOT-23-6",
         lcsc="C7519", nets={"1": "USB_D+", "6": "USB_D+", "3": "USB_D-", "4": "USB_D-", "5": VBUS, "2": GND},
         why="ESD on D+, D- and VBUS at the connector"),
    dict(ref="U3", sym="Regulator_Linear:AMS1117-3.3", value="AMS1117-3.3", fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2",
         lcsc="C6186", nets={"3": VBUS, "2": V33, "1": GND}),
    cap("C14", VBUS, C10U, "AMS1117 in"),
    cap("C15", V33, dict(value="22u", fp=C0805, lcsc="C45783"), "AMS1117 out, and the board's bulk"),

    # --- the link: the USB-C's D+/D- reach the CH340C and nothing else. It runs at 3.3 V (V3 tied to
    # VCC, as WCH's datasheet says for 3.3 V). TXD and RXD go to UART1 on GPIO18/17, where
    # MicroPython never puts its REPL. DTR and RTS go nowhere, on purpose: the computer can't reset
    # the S3 or start its bootloader.
    dict(ref="U4", sym="Interface_USB:CH340C", value="CH340C", fp="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm",
         lcsc="C84681", nets={"16": V33, "4": V33, "1": GND, "15": GND, "5": "USB_D+", "6": "USB_D-",
                              "2": "LINK_RX", "3": "LINK_TX"}),
    cap("C16", V33, C100N, "CH340C VCC"),

    # --- the key: the ATECC608C on the S3's I2C (GPIO3/4, the Feather's), 4.7k pull-ups to 3.3 V
    dict(ref="U5", sym="Security:ATECC608A-MAHDA", value="ATECC608C-MAHDA-S", fp="Package_DFN_QFN:DFN-8-1EP_3x2mm_P0.5mm_EP1.3x1.5mm",
         lcsc="C23291019", mpn="ATECC608C-MAHDA-S", nets={"8": V33, "4": GND, "9": GND, "5": "SDA", "6": "SCL"},
         why="same pins as the 608A symbol"),
    cap("C17", V33, C100N, "ATECC608C VCC"),
    res("R5", V33, "SDA", dict(value="4.7k", fp=R0402, lcsc="C25900")),
    res("R6", V33, "SCL", dict(value="4.7k", fp=R0402, lcsc="C25900")),

    # --- the screen: the 1.14" 240x135 ST7789 on an 8-pin 0.5 mm FPC. Pin order from the seller's
    # listing (1 LEDA, 2 GND, 3 RESET, 4 RS, 5 SDA, 6 SCL, 7 VDD, 8 CS); check it on the panel
    # bought before the layout. The backlight's cathode is on GND inside, so it's switched high:
    # Q1 (P-FET) from 3.3 V, turned on by Q2 when GPIO45 is high, as the Feather's is.
    dict(ref="J2", sym="Connector_Generic_MountingPin:Conn_01x08_MountingPin", value="LCD 1.14in FPC",
         fp="Connector_FFC-FPC:Hirose_FH12-8S-0.5SH_1x08-1MP_P0.50mm_Horizontal", lcsc="C597995",
         mpn="FH12-8S-0.5SH(55)", nets={"1": "LCD_LEDA", "2": GND, "3": "LCD_RST", "4": "LCD_DC",
                                        "5": "LCD_MOSI", "6": "LCD_SCK", "7": V33, "8": "LCD_CS", "MP": GND}),
    cap("C18", V33, C1U, "the panel's VDD"), cap("C19", V33, C100N),
    dict(ref="Q1", sym="Transistor_FET:AO3401A", value="AO3401A", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C15127",
         nets={"2": V33, "3": "BL_SW", "1": "BL_GATE"}),
    res("R7", "BL_SW", "LCD_LEDA", dict(value="22R", fp=R0402, lcsc="C25092"), "backlight current, about 10 mA: tune at bring-up"),
    res("R8", V33, "BL_GATE", R10K, "Q1 off by default"),
    dict(ref="Q2", sym="Transistor_BJT:SS8050", value="SS8050", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C2150",
         mpn="SS8050", nets={"1": "BL_BASE", "2": GND, "3": "BL_GATE"}),
    res("R9", "LCD_BL", "BL_BASE", R1K),
    res("R10", "LCD_BL", GND, R10K, "GPIO45 is a strap: low at reset picks 3.3 V for the flash"),

    # --- the buttons, as the Feather's: D0 to GND with a pull-up (it is also BOOT), D1 and D2 to
    # 3.3 V with pull-downs (board.HIGH)
    dict(ref="SW1", value="D0", nets={"1": "BTN_D0", "2": GND}, **SW),
    dict(ref="SW2", value="D1", nets={"1": V33, "2": "BTN_D1"}, **SW),
    dict(ref="SW3", value="D2", nets={"1": V33, "2": "BTN_D2"}, **SW),
    res("R11", V33, "BTN_D0", R10K, "GPIO0 is the BOOT strap: high at reset"),
    res("R12", "BTN_D1", GND, R10K), res("R13", "BTN_D2", GND, R10K),

    # --- the LED on GPIO13, as the Feather's
    res("R14", "LED", "LED_A", R1K),
    dict(ref="D1", sym="Device:LED", value="red", fp="LED_SMD:LED_0603_1608Metric", lcsc="C2286", mpn="KT-0603R",
         nets={"2": "LED_A", "1": GND}),

    # --- the bench header, not fitted: UART0 (the REPL and the ROM's flasher, D0 held at RESET), the
    # S3's own USB, and the key's bus for a key-c on wires. Holes only; a header goes in for bring-up.
    dict(ref="J3", sym="Connector_Generic:Conn_01x08", value="BENCH", fp="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
         nets={"1": GND, "2": V33, "3": "U0TXD_R", "4": "U0RXD", "5": "DEV_D-", "6": "DEV_D+", "7": "SDA", "8": "SCL"},
         dnp=True, bom=False),
    res("R15", "U0TXD", "U0TXD_R", dict(value="510R", fp=R0402, lcsc="C25123"), "Espressif's 499 R on U0TXD"),
] + [dict(ref=f"H{i}", sym="Mechanical:MountingHole", value="M2.5", fp="MountingHole:MountingHole_2.7mm_M2.5",
          nets={}, bom=False) for i in range(1, 5)]

# Nets KiCad would call undriven: VBUS comes in on a passive pin, VDD3P3 through a resistor-shaped
# 0 R, VDD_SPI from inside the S3. Each gets a PWR_FLAG.
FLAGS = [GND, VBUS, "VDD3P3", "VDD_SPI"]

# The S3's GPIOs on this board, by net. The firmware's "feather-s3" profile must name the same ones.
GPIO = {"BTN_D0": 0, "BTN_D1": 1, "BTN_D2": 2, "SDA": 3, "SCL": 4, "LED": 13, "LINK_TX": 17, "LINK_RX": 18,
        "DEV_D-": 19, "DEV_D+": 20, "LCD_MOSI": 35, "LCD_SCK": 36, "LCD_DC": 40, "LCD_RST": 41, "LCD_CS": 42,
        "LCD_BL": 45, "U0TXD": 43, "U0RXD": 44}
# ESP32-S3 package pin -> GPIO (the datasheet's pin table; MTCK..MTMS are GPIO39..42)
PIN_GPIO = {"5": 0, "6": 1, "7": 2, "8": 3, "9": 4, "18": 13, "23": 17, "24": 18, "25": 19, "26": 20,
            "40": 35, "41": 36, "45": 40, "47": 41, "48": 42, "49": 43, "50": 44, "51": 45}

# =================================================================================================
# S-expressions: just enough to lift a stock symbol out of KiCad's library
# =================================================================================================
TOK = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)')


def parse(s):
    stack, cur = [], []
    for m in TOK.finditer(s):
        t = m.group(1)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t)
    return cur


def dump(x):
    return "(" + " ".join(dump(i) if isinstance(i, list) else i for i in x) + ")" if isinstance(x, list) else x


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def uq(t):
    return t[1:-1] if t.startswith('"') else t


_libs = {}


def lib_symbols(lib):
    if lib not in _libs:
        root = parse(open(os.path.join(KISYM, lib + ".kicad_sym")).read())[0]
        _libs[lib] = {uq(x[1]): x for x in root if isinstance(x, list) and x[0] == "symbol"}
    return _libs[lib]


def stock(lib_id):
    """The stock symbol, flattened if it extends another, named lib_id for the schematic's cache.
    Returns (s-expression, pins): pins are (number, name, type, x, y, angle), y up."""
    lib, name = lib_id.split(":")
    syms = lib_symbols(lib)
    sym = syms[name]
    ext = next((x for x in sym if isinstance(x, list) and x[0] == "extends"), None)
    if ext:
        parent = syms[uq(ext[1])]
        pname = uq(parent[1])
        props = {uq(x[1]): x for x in sym if isinstance(x, list) and x[0] == "property"}
        body = []
        for x in parent[2:]:
            if isinstance(x, list) and x[0] == "property" and uq(x[1]) in props:
                body.append(props.pop(uq(x[1])))
            elif isinstance(x, list) and x[0] == "symbol":
                body.append(["symbol", q(uq(x[1]).replace(pname, name, 1))] + x[2:])
            else:
                body.append(x)
        body[1:1] = list(props.values())
        sym = ["symbol", q(name)] + body
    out = ["symbol", q(lib_id)] + sym[2:]
    pins = []
    for unit in (x for x in sym if isinstance(x, list) and x[0] == "symbol"):
        for p in (x for x in unit if isinstance(x, list) and x[0] == "pin"):
            at = next(x for x in p if isinstance(x, list) and x[0] == "at")
            nm = next(x for x in p if isinstance(x, list) and x[0] == "name")
            nu = next(x for x in p if isinstance(x, list) and x[0] == "number")
            pins.append((uq(nu[1]), uq(nm[1]), p[1], float(at[1]), float(at[2]), int(float(at[3]))))
    return out, pins


# =================================================================================================
# The schematic: each part placed, a short wire from each pin, and the net's label or power symbol
# at its end. Nothing is drawn wire to wire, so a connection is exactly a name.
# =================================================================================================
def uid():
    return str(uuid.uuid4())


def font(hide=False, justify=None):
    return "(effects (font (size 1.27 1.27))" + (f" (justify {justify})" if justify else "") + (" (hide yes)" if hide else "") + ")"


# Where each part goes on the A3 sheet (mm, on the 2.54 grid), block by block.
def g(n):
    return round(n * 2.54, 2)


PLACE = {
    "U1": (g(70), g(55)),
    "J1": (g(14), g(22)), "R3": (g(26), g(14)), "R4": (g(30), g(14)), "U2": (g(14), g(42)),
    "U3": (g(26), g(32)), "C14": (g(22), g(40)), "C15": (g(32), g(40)),
    "U4": (g(14), g(66)), "C16": (g(26), g(66)),
    "C1": (g(46), g(10)), "C2": (g(50), g(10)), "C3": (g(54), g(10)), "L1": (g(58), g(10)), "C4": (g(62), g(10)),
    "C5": (g(66), g(10)), "C6": (g(70), g(10)), "C7": (g(74), g(10)), "C8": (g(78), g(10)), "C9": (g(82), g(10)),
    "C10": (g(86), g(10)),
    "R1": (g(44), g(26)), "C11": (g(44), g(34)), "SW4": (g(48), g(34)),
    "Y1": (g(46), g(84)), "R2": (g(46), g(76)), "C12": (g(40), g(90)), "C13": (g(52), g(90)),
    "U5": (g(110), g(14)), "C17": (g(122), g(12)), "R5": (g(102), g(28)), "R6": (g(106), g(28)),
    "J2": (g(110), g(46)), "C18": (g(122), g(42)), "C19": (g(126), g(42)),
    "Q1": (g(134), g(54)), "R7": (g(140), g(48)), "R8": (g(128), g(54)), "Q2": (g(132), g(64)),
    "R9": (g(126), g(66)), "R10": (g(120), g(70)),
    "SW1": (g(98), g(80)), "SW2": (g(110), g(80)), "SW3": (g(122), g(80)),
    "R11": (g(98), g(90)), "R12": (g(110), g(90)), "R13": (g(122), g(90)),
    "R14": (g(134), g(80)), "D1": (g(134), g(88)),
    "J3": (g(150), g(16)), "R15": (g(150), g(30)),
    "H1": (g(146), g(96)), "H2": (g(150), g(96)), "H3": (g(154), g(96)), "H4": (g(158), g(96)),
}
FLAG_AT = {GND: (g(6), g(96)), VBUS: (g(10), g(96)), "VDD3P3": (g(14), g(96)), "VDD_SPI": (g(18), g(96))}
NOTES = [
    (g(6), g(104), "console-usb: the console with no radio in use. See hardware/console-usb/README.md.\n"
                 "Every connection is a name: a net label or a power symbol at the end of each pin's stub."),
    (g(2), g(76), "The link. The USB-C's D+ and D- reach the CH340C and nothing else.\n"
                  "TXD/RXD go to UART1 (GPIO18/17); MicroPython's REPL is never there.\n"
                  "DTR and RTS are NOT connected, on purpose: the computer can't reset\n"
                  "the S3 or start its bootloader. Don't add auto-reset."),
    (g(38), g(98), "LNA_IN floats and there is no antenna: the firmware never starts the radio\n"
                   "(Espressif's checklist: an antenna is needed only if RF is enabled).\n"
                   "Flash and PSRAM are in the package: SPI* and GPIO26 stay unconnected."),
    (g(100), g(36), "J2: pin order from the seller's listing. Check it on the panel before the layout."),
    (g(138), g(40), "J3 is not fitted: holes for a header at the bench. UART0 is the REPL\n"
                    "and the ROM's flasher (hold D0, press RESET). Nothing reaches it\n"
                    "through the USB-C."),
]


def outward(angle):
    """The way a pin points out of its symbol, in schematic coordinates (y down)."""
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[angle]


# rotation of a power symbol so it points away from the pin: GND's graphic hangs down at 0,
# +3V3's and VBUS's stands up at 0; a schematic rotation turns them anticlockwise
GND_ROT = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}
SUP_ROT = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}
LABEL_ROT = {(-1, 0): (180, "right bottom"), (1, 0): (0, "left bottom"), (0, -1): (90, "left bottom"), (0, 1): (270, "right bottom")}


class Sheet:
    def __init__(self):
        self.root = uid()
        self.items = []
        self.cache = {}
        self.npwr = 0

    def lib(self, lib_id):
        if lib_id not in self.cache:
            self.cache[lib_id] = stock(lib_id)
        return self.cache[lib_id][1]

    def symbol(self, lib_id, ref, value, x, y, rot=0, fp="", fields=(), pins=(), dnp=False, in_bom=True, ref_at=None, val_at=None):
        hide = ref.startswith("#")
        ra = ref_at or (x + 2.54, y - 2.54)
        va = val_at or (x + 2.54, y + 2.54)
        props = [f'(property "Reference" {q(ref)} (at {ra[0]} {ra[1]} 0) {font(hide, None if hide else "left")})',
                 f'(property "Value" {q(value)} (at {va[0]} {va[1]} 0) {font(False, None if hide else "left")})',
                 f'(property "Footprint" {q(fp)} (at {x} {y} 0) {font(True)})']
        props += [f'(property {q(k)} {q(v)} (at {x} {y} 0) {font(True)})' for k, v in fields if v]
        yn = lambda b: "yes" if b else "no"
        self.items.append(
            f'(symbol (lib_id {q(lib_id)}) (at {x} {y} {rot}) (unit 1) (exclude_from_sim no) (in_bom {yn(in_bom)}) '
            f'(on_board yes) (dnp {yn(dnp)}) (uuid "{uid()}")\n' + "\n".join(props) + "\n"
            + " ".join(f'(pin {q(n)} (uuid "{uid()}"))' for n in pins)
            + f'\n(instances (project "{NAME}" (path "/{self.root}" (reference {q(ref)}) (unit 1)))))')

    def power(self, net, x, y, d):
        self.npwr += 1
        lib_id = "power:" + net
        self.lib(lib_id)
        rot = (GND_ROT if net == GND else SUP_ROT)[d]
        self.symbol(lib_id, f"#PWR{self.npwr:03d}", net, x, y, rot, pins=["1"],
                    ref_at=(x, y), val_at=(x + 3.81 * d[0], y + 3.81 * d[1] if d[1] else y))

    def flag(self, x, y):
        self.npwr += 1
        self.lib("power:PWR_FLAG")
        self.symbol("power:PWR_FLAG", f"#FLG{self.npwr:03d}", "PWR_FLAG", x, y, 0, pins=["1"], ref_at=(x, y), val_at=(x, y - 3.81))

    def wire(self, x1, y1, x2, y2):
        self.items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid "{uid()}"))')

    def label(self, net, x, y, d):
        a, j = LABEL_ROT[d]
        self.items.append(f'(label {q(net)} (at {x} {y} {a}) (fields_autoplaced yes) {font(False, j)} (uuid "{uid()}"))')

    def nc(self, x, y):
        self.items.append(f'(no_connect (at {x} {y}) (uuid "{uid()}"))')

    def text(self, s, x, y):
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) {font(False, "left top")} (uuid "{uid()}"))')

    def stub(self, net, x, y, d, n=1):
        """A pin's wire out to its net's name, n grid steps long."""
        ex, ey = round(x + 2.54 * n * d[0], 2), round(y + 2.54 * n * d[1], 2)
        self.wire(x, y, ex, ey)
        if net in POWER:
            self.power(net, ex, ey, d)
        else:
            self.label(net, ex, ey, d)

    def write(self, path):
        cache = "\n".join(dump(s) for s, _ in self.cache.values())
        with open(path, "w") as f:
            f.write(f"""(kicad_sch (version 20250114) (generator "picoquorum_gen") (generator_version "9.0")
(uuid "{self.root}")
(paper "A3")
(title_block (title "PicoQuorum console-usb: no radio, USB serial to the host") (date "{DATE}") (rev "A")
  (company "PicoQuorum") (comment 1 "Written by hardware/console-usb/gen_console_usb.py. CERN-OHL-W v2")
  (comment 2 "Source Location: https://github.com/jmcpheron/pico-quorum"))
(lib_symbols
{cache})
{chr(10).join(self.items)}
(sheet_instances (path "/" (page "1")))
(embedded_fonts no))
""")


def write_schematic():
    sh = Sheet()
    for p in PARTS:
        pins = sh.lib(p["sym"])
        x, y = PLACE[p["ref"]]
        ys = [py for *_, py, _a in pins] or [0]
        fields = [("Datasheet", ""), ("LCSC", p.get("lcsc", "")), ("MPN", p.get("mpn", ""))]
        sh.symbol(p["sym"], p["ref"], p["value"], x, y, fp=p["fp"], fields=fields,
                  pins=sorted({n for n, *_ in pins}), dnp=p.get("dnp", False), in_bom=p.get("bom", True),
                  ref_at=(x + 2.54, round(y - max(ys) - 2.54, 2)), val_at=(x + 2.54, round(y - min(ys) + 2.54, 2)))
        done = {}
        top = 0             # pins side by side on a symbol's top edge: stubs of 1, 3 and 5 steps
        for num, _name, _kind, px, py, angle in sorted(pins, key=lambda t: t[3]):
            at = (round(x + px, 2), round(y - py, 2))
            net = p["nets"].get(num)
            if at in done:          # stacked pins: one stub, and they must agree
                if done[at] != net:
                    sys.exit(f"{p['ref']} pins stacked at {at} disagree: {done[at]} and {net}")
                continue
            done[at] = net
            if net is None:
                sh.nc(*at)
            elif angle == 270 and p["ref"] == "U1":
                sh.stub(net, *at, outward(angle), 1 + 2 * (top % 3))
                top += 1
            else:
                sh.stub(net, *at, outward(angle))
    for net, (x, y) in FLAG_AT.items():
        sh.flag(x, y)
        sh.stub(net, x, y, (0, 1))
    for x, y, s in NOTES:
        sh.text(s, x, y)
    os.makedirs(OUT, exist_ok=True)
    sh.write(os.path.join(OUT, NAME + ".kicad_sch"))
    return sh


def write_project(sheet_uuid):
    d = json.load(open(os.path.join(REPO, "hardware", "key-pcb", "key-b-udfn", "key-b-udfn.kicad_pro")))
    d["meta"]["filename"] = NAME + ".kicad_pro"
    d["board"]["design_settings"]["rules"].update(gen.JLC_RULES)
    d["sheets"] = [[sheet_uuid, "Root"]]
    with open(os.path.join(OUT, NAME + ".kicad_pro"), "w") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)
        fh.write("\n")


def write_bom():
    rows = {}
    for p in PARTS:
        if not p.get("bom", True):
            continue
        key = (p["value"], p["fp"].split(":")[1], p["lcsc"])
        rows.setdefault(key, []).append(p["ref"])
    nat = lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r)))
    os.makedirs(os.path.join(HERE, "fab"), exist_ok=True)
    with open(os.path.join(HERE, "fab", "bom.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (value, fp, lcsc), refs in sorted(rows.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
            w.writerow([value, ",".join(sorted(refs, key=nat)), fp, lcsc])


def write_pins():
    pin_of = {gp: pin for pin, gp in PIN_GPIO.items()}
    lines = ["# console-usb: the S3's pins", "",
             "*Written by `gen_console_usb.py`; don't edit by hand.*", "",
             "| GPIO | S3 pin | net | what | the Feather's |", "|---|---|---|---|---|"]
    what = {"BTN_D0": "D0, pulled up, low when pressed; the BOOT strap", "BTN_D1": "D1, pulled down, high when pressed",
            "BTN_D2": "D2, pulled down, high when pressed", "SDA": "the key's I2C, 4.7k to 3.3 V", "SCL": "the key's I2C, 4.7k to 3.3 V",
            "LED": "red LED, high is on", "LINK_TX": "UART1 TX to the CH340C's RXD", "LINK_RX": "UART1 RX from the CH340C's TXD",
            "DEV_D-": "the S3's own USB, to J3 only", "DEV_D+": "the S3's own USB, to J3 only",
            "LCD_MOSI": "the screen's SDA", "LCD_SCK": "the screen's SCL", "LCD_DC": "the screen's RS", "LCD_RST": "the screen's RESET",
            "LCD_CS": "the screen's CS", "LCD_BL": "backlight, high is on; a strap: 10k down", "U0TXD": "UART0 TX, through 510 R to J3",
            "U0RXD": "UART0 RX, to J3"}
    feather = feather_profile()
    for net, gp in sorted(GPIO.items(), key=lambda kv: kv[1]):
        lines.append(f"| {gp} | {pin_of[gp]} | `{net}` | {what[net]} | {feather.get(gp, '')} |")
    lines += ["", "Not connected: GPIO 5–12, 14, 21, 33, 34, 37–39, 46–48, LNA_IN, XTAL_32K_P/N (GPIO15/16), and",
              "the in-package flash's and PSRAM's pins (SPICS1/GPIO26, SPIHD, SPIWP, SPICS0, SPICLK, SPIQ, SPID).",
              "GPIO7, which the firmware drives high for the Feather's screen power, drives nothing here.", ""]
    with open(os.path.join(HERE, "PINS.md"), "w") as f:
        f.write("\n".join(lines))


# =================================================================================================
# The checks
# =================================================================================================
def feather_profile():
    """firmware/board.py's "feather-s3" pins, GPIO -> role. Read only."""
    b = open(os.path.join(REPO, "firmware", "board.py")).read()
    prof = re.search(r"^if THREE:(.*?)\nelif ", b, re.S | re.M).group(1)
    dc, cs, sck, mosi, rst, bl = map(int, re.search(r"DC, CS, SCK, MOSI, RST, BL = ([\d, ]+)\n", prof).group(1).split(","))
    btn = {k: int(v) for k, v in re.findall(r'"(D\d)": (\d+)', re.search(r"BUTTONS = \{[^}]*\}", prof).group(0))}
    _spi, sda, scl, led = map(int, re.search(r"SPI_ID, SDA, SCL, LED = ([\d, ]+)\n", prof).group(1).split(","))
    high = {int(v) for v in re.search(r"HIGH = \(([\d, ]+)\)", prof).group(1).split(",") if v.strip()}
    out = {dc: "DC", cs: "CS", sck: "SCK", mosi: "MOSI", rst: "RST", bl: "BL", sda: "SDA", scl: "SCL", led: "LED"}
    out.update({v: k + (" (high)" if v in high else " (low)") for k, v in btn.items()})
    return out


def check_firmware(bad):
    want = {"LCD_DC": "DC", "LCD_CS": "CS", "LCD_SCK": "SCK", "LCD_MOSI": "MOSI", "LCD_RST": "RST", "LCD_BL": "BL",
            "SDA": "SDA", "SCL": "SCL", "LED": "LED", "BTN_D0": "D0 (low)", "BTN_D1": "D1 (high)", "BTN_D2": "D2 (high)"}
    prof = feather_profile()
    for net, role in want.items():
        if prof.get(GPIO[net]) != role:
            bad.append(f"{net} is GPIO{GPIO[net]}, but board.py's feather-s3 has {prof.get(GPIO[net])!r} there (wants {role})")
    for gp, role in prof.items():
        if gp not in GPIO.values():
            bad.append(f"board.py's feather-s3 uses GPIO{gp} ({role}), which this board leaves unconnected")
    for net in ("LINK_TX", "LINK_RX"):
        if GPIO[net] in prof:
            bad.append(f"{net} is on GPIO{GPIO[net]}, which feather-s3 already uses")
    u1 = next(p for p in PARTS if p["ref"] == "U1")["nets"]
    for pin, gp in PIN_GPIO.items():
        net = u1.get(pin)
        if net is not None and GPIO.get(net) != gp:
            bad.append(f"U1 pin {pin} is GPIO{gp} but carries {net}")


def check_straps(bad, nets):
    """The S3's strapping pins at reset, from the netlist: GPIO0 high (SPI boot), GPIO45 low (3.3 V
    flash), GPIO46 left to its pull-down, GPIO3 free to be high (JTAG strap only counts with an eFuse)."""
    def ends(ref):
        return sorted(n for n, s in nets.items() if (ref, "1") in s or (ref, "2") in s)
    if ends("R11") != sorted([V33, "/BTN_D0"]):
        bad.append("GPIO0 (BOOT) has no pull-up to 3.3 V")
    if ends("R10") != sorted(["/LCD_BL", GND]):
        bad.append("GPIO45 isn't pulled down: at reset it would pick 1.8 V for a 3.3 V flash")
    if "/LCD_BL" in nets and any(r.startswith("U") and r != "U1" for r, _ in nets["/LCD_BL"]):
        bad.append("GPIO45 drives a chip input directly: it must see only R9 and R10")
    for n, s in nets.items():
        if n.startswith("unconnected-"):    # one pin alone: check_netlist stops on any with more
            continue
        if ("U1", "52") in s:
            bad.append(f"GPIO46 is connected ({n}); it should be left to its pull-down")
        if any(r == "U4" and pin in ("13", "14") for r, pin in s):
            bad.append(f"the CH340C's DTR or RTS is connected ({n}): the computer could reset the S3 or start its bootloader")
        if any(r == "J1" for r, _ in s) and any(r == "U1" for r, _ in s) and n not in POWER:
            bad.append(f"the USB-C reaches the S3 directly on {n}")


def netlist():
    """KiCad's own reading of the schematic: net name -> {(ref, pin)}."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "n.net")
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out,
                        os.path.join(OUT, NAME + ".kicad_sch")], check=True, capture_output=True)
        tree = parse(open(out).read())[0]
    nets = {}
    for n in next(x for x in tree if isinstance(x, list) and x[0] == "nets")[1:]:
        name = uq(next(x for x in n if isinstance(x, list) and x[0] == "name")[1])
        nodes = {(uq(nd[1][1]), uq(nd[2][1])) for nd in n if isinstance(nd, list) and nd[0] == "node"}
        nets[name] = nodes
    return nets


def check_netlist(bad, nets):
    want = {}
    for p in PARTS:
        for pin, net in p["nets"].items():
            want.setdefault(net if net in POWER else "/" + net, set()).add((p["ref"], pin))
    for net, nodes in want.items():
        got = nets.get(net, set())
        if got != nodes:
            bad.append(f"net {net}: KiCad reads {sorted(got)}, the table says {sorted(nodes)}")
    for net, nodes in nets.items():
        if net not in want and not net.startswith("unconnected-"):
            bad.append(f"KiCad has a net the table doesn't: {net} {sorted(nodes)}")
        if net.startswith("unconnected-") and len(nodes) > 1:
            bad.append(f"{net} joins {sorted(nodes)}")


def check_erc(bad):
    """KiCad's ERC, with KiCad's default library tables (a fresh config), so each cached symbol is
    compared with the stock library it came from."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = os.path.join(tmp, "9.0")
        os.makedirs(cfg)
        for t in ("sym-lib-table", "fp-lib-table"):
            shutil.copy(os.path.join("/usr/share/kicad/template", t), cfg)
        out = os.path.join(tmp, "erc.json")
        subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", out,
                        os.path.join(OUT, NAME + ".kicad_sch")], capture_output=True,
                       env=dict(os.environ, KICAD_CONFIG_HOME=tmp, KICAD9_SYMBOL_DIR=KISYM, KICAD9_FOOTPRINT_DIR=KIFP))
        rep = json.load(open(out))
    found = []
    for sheet in rep.get("sheets", []):
        for v in sheet.get("violations", []):
            items = "; ".join(i.get("description", "") for i in v.get("items", []))
            found.append((v["severity"], v["type"], items))
    # Expected, and why: the CH340C's V3 pin is a power output that WCH's datasheet ties to VCC at
    # 3.3 V, so +3V3 has two power outputs (it and the AMS1117).
    def expected(f):
        return f[1] == "pin_to_pin" and "U4 Pin 4 [V3" in f[2] and "U3 Pin 2 [VO" in f[2]
    for f in found:
        print(f"  ERC {f[0]} {f[1]}: {f[2]}" + ("" if expected(f) else "  <- not expected"))
        if not expected(f):
            bad.append(f"ERC {f[0]} {f[1]}: {f[2]}")
    return found


def check_footprints(bad):
    """Every symbol pin has a pad of the same number in its footprint, and every copper pad a pin."""
    try:
        import pcbnew
    except ImportError:
        print("  (no pcbnew module: footprint pads not checked)")
        return
    for p in PARTS:
        lib, name = p["fp"].split(":")
        fp = pcbnew.FootprintLoad(os.path.join(KIFP, lib + ".pretty"), name)
        if fp is None:
            bad.append(f"{p['ref']}: no footprint {p['fp']}")
            continue
        pads = {pd.GetNumber() for pd in fp.Pads() if pd.GetNumber() and pd.IsOnCopperLayer()}
        pins = {n for n, *_ in stock(p["sym"])[1]}
        if pins - pads:
            bad.append(f"{p['ref']}: pins {sorted(pins - pads)} have no pad in {p['fp']}")
        if pads - pins:
            bad.append(f"{p['ref']}: pads {sorted(pads - pins)} of {p['fp']} have no pin")


def main():
    bad = []
    check_firmware(bad)
    sh = write_schematic()
    write_project(sh.root)
    write_bom()
    write_pins()
    print(f"wrote {os.path.relpath(OUT, REPO)}/{NAME}.kicad_sch, .kicad_pro, fab/bom.csv, PINS.md")
    nets = netlist()
    check_netlist(bad, nets)
    check_straps(bad, nets)
    found = check_erc(bad)
    check_footprints(bad)
    n_parts = sum(1 for p in PARTS if p.get("bom", True))
    print(f"  {len(PARTS)} parts ({n_parts} placed by JLCPCB), {len([n for n in nets if not n.startswith('unconnected-')])} nets, "
          f"ERC: {len(found)} findings, all expected" if not bad else "")
    if bad:
        sys.exit("console-usb: " + str(len(bad)) + " problems\n  " + "\n  ".join(bad))
    print("  KiCad's netlist matches the table; straps, footprints and the feather-s3 pins check out")


if __name__ == "__main__":
    main()
