#!/usr/bin/env python3
"""console-rp: the console on one board with no radio at all. An RP2350A and its flash, the 1.14"
screen with three buttons under it, the ATECC608C soldered on, and a USB-C whose only data path is
a CH343P serial bridge to the RP2350's UART1. See README.md.

    tools/keypcb gen-console-rp [render]         writes the project, the board placed, not routed
    tools/keypcb route console-rp                routes it (Freerouting)
    tools/keypcb gen-console-rp check [render]   checks the routed board, writing nothing but renders
        (KiCad 10: kicad-cli, its Python with pcbnew, its stock libraries and, to render, its 3D
        models; on Linux the system Python's pcbnew)

Writes, from the one table below:
  console-rp/console-rp.kicad_sch   the schematic, every part a stock KiCad symbol
  console-rp/console-rp.kicad_pcb   the board, every part placed, the copper round the RP2350 copied
                                    from Raspberry Pi's minimal board (rpi_minimal.json), the rest
                                    left to the router
  console-rp/console-rp.kicad_pro   the project, with JLCPCB's limits as its rules
  lib/                              J2's footprint (console-s3's), the panel's, and 3D boxes for both
                                    (Raspberry Pi's footprints, lib/pqrp.pretty/RPi_*, come from
                                    rpi_minimal.py)
  fab/bom.csv                       JLCPCB's BOM format: Comment, Designator, Footprint, LCSC Part #
  PINS.md                           the RP2350's pins, as the firmware sees them
  renders/                          with "render": KiCad's 3D view of the board, the panel on it

Then has KiCad read the schematic back (kicad-cli netlist and ERC) and checks every connection
against the table, every symbol pin against its footprint's pads, the screen's and key's pins
against firmware/board.py's Pico pins, each GPIO against the RP2350's function table, and the link's
wiring rules; and runs KiCad's DRC on the placed board, and checks what sits under the panel's glass.
It stops on any difference.

It won't rewrite a routed board: the schematic's new uuids would no longer match it. Once the
schematic or the board is edited in KiCad, KiCad's files are the source and this script only checks.
"""
import csv, json, math, os, re, shutil, subprocess, sys, tempfile, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
NAME = "console-rp"
OUT = os.path.join(HERE, NAME)
APP = "/Applications/KiCad/KiCad.app/Contents"       # macOS keeps KiCad's libraries in the app
SHARE = os.path.join(APP, "SharedSupport") if os.path.isdir(APP) else "/usr/share/kicad"
KISYM, KIFP, KI3D, KITPL = (os.path.join(SHARE, d) for d in ("symbols", "footprints", "3dmodels", "template"))
CLI = shutil.which("kicad-cli") or os.path.join(APP, "MacOS", "kicad-cli")
DATE = "2026-10-28"
sys.path.insert(0, os.path.join(REPO, "hardware", "key-pcb"))
import gen        # noqa: E402  JLC_RULES

GND, V33, VBUS = "GND", "+3V3", "VBUS"
POWER = (GND, V33, VBUS)

# =================================================================================================
# The one table: every part, its LCSC number and what each of its pins connects to. A pin not listed
# is not connected, on purpose, and gets a no-connect flag. Nets other than the three power nets are
# local labels, which KiCad names "/<net>".
# LCSC numbers, tiers and stock from JLCPCB's parts search on 2026-10-28 (README.md has the table).
# The RP2350's circuit is Raspberry Pi's minimal design ("Hardware design with RP2350"): its
# regulator parts, its crystal and 1k, its 27 R on USB, and a 100n at each power pin.
# =================================================================================================
R0402, C0402, C0805 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0805_2012Metric"
C100N = dict(value="100n", fp=C0402, lcsc="C1525")
C1U = dict(value="1u", fp=C0402, lcsc="C52923")
C4U7 = dict(value="4.7u", fp=C0402, lcsc="C23733")
C10U = dict(value="10u", fp=C0805, lcsc="C15850")
R10K = dict(value="10k", fp=R0402, lcsc="C25744")
R1K = dict(value="1k", fp=R0402, lcsc="C11702")
R27 = dict(value="27R", fp=R0402, lcsc="C25100")
SW = dict(sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", lcsc="C318884", mpn="TS-1187A-B-A-B")


def cap(ref, top, spec, why=""):
    return dict(ref=ref, sym="Device:C", nets={"1": top, "2": GND}, why=why, **spec)


def res(ref, a, b, spec, why=""):
    return dict(ref=ref, sym="Device:R", nets={"1": a, "2": b}, why=why, **spec)


# The RP2350's GPIOs on this board, by net. The screen and the key are on the Pico's pins
# (board.py's defaults, the Waveshare Pico-LCD-1.3's); the buttons and the link are new.
GPIO = {"BTN_D0": 2, "BTN_D1": 3, "SDA": 4, "SCL": 5, "BTN_D2": 6, "LCD_DC": 8, "LCD_CS": 9, "LCD_SCK": 10,
        "LCD_MOSI": 11, "LCD_RST": 12, "LCD_BL": 13, "LINK_TX": 20, "LINK_RX": 21, "LED": 25}
# RP2350A (QFN-60) package pin -> GPIO, from its datasheet's pin table (checked against the symbol's
# pin names)
PIN_GPIO = {"4": 2, "5": 3, "7": 4, "8": 5, "9": 6, "12": 8, "13": 9, "14": 10, "15": 11, "16": 12, "17": 13,
            "32": 20, "33": 21, "37": 25}
U1_NETS = {pin: next(n for n, g in GPIO.items() if g == gp) for pin, gp in PIN_GPIO.items()}

PARTS = [
    # --- the RP2350A. IOVDD (six pins), ADC_AVDD, USB_OTP_VDD, QSPI_IOVDD and VREG_VIN from 3.3 V;
    # DVDD (1.1 V) from its own switching regulator: VREG_LX through L1, VREG_FB reading DVDD.
    dict(ref="U1", sym="MCU_RaspberryPi:RP2350A", value="RP2350A", lcsc="C42411118", mpn="RP2350A",
         fp="pqrp:RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias",          # Raspberry Pi's: nine vias in its pad
         nets={**{p: V33 for p in ("1", "11", "20", "30", "38", "45")}, **{p: "DVDD" for p in ("6", "23", "39")},
               "44": V33, "46": "VREG_AVDD", "47": GND, "48": "VREG_LX", "49": V33, "50": "DVDD",
               "53": V33, "54": V33, "61": GND, "21": "XIN", "22": "XOUT",
               "24": "SWCLK", "25": "SWDIO", "26": "RUN", "51": "RP_DM", "52": "RP_DP",
               "55": "QSPI_SD3", "56": "QSPI_SCLK", "57": "QSPI_SD0", "58": "QSPI_SD2", "59": "QSPI_SD1",
               "60": "QSPI_SS", **U1_NETS}),
    # the regulator, as the minimal design (its C6, C7, C9, L1, R3). L1 is the polarity-marked
    # Abracon part Raspberry Pi asks for; its layout is theirs, copied (rpi_minimal.json).
    cap("C1", V33, C4U7, "VREG_VIN, pin 49"),
    cap("C2", "DVDD", C4U7, "the regulator's output"),
    res("R1", V33, "VREG_AVDD", dict(value="33R", fp=R0402, lcsc="C25105"), "VREG_AVDD's RC filter"),
    cap("C3", "VREG_AVDD", C4U7),
    dict(ref="L1", sym="Device:L", value="3.3uH", fp="pqrp:RPi_L_Abracon_AOTA-B201610", lcsc="C42411119",
         mpn="AOTA-B201610S3R3-101-T", nets={"1": "DVDD", "2": "VREG_LX"},
         why="Raspberry Pi's footprint, its pad 1 (the dot) on DVDD as theirs"),
    # a 100n at each power pin; USB_OTP_VDD and QSPI_IOVDD share one, as the minimal design
    *[cap(f"C{4 + i}", V33, C100N, f"IOVDD, pin {p}") for i, p in enumerate(("1", "11", "20", "30", "38", "45"))],
    *[cap(f"C{10 + i}", "DVDD", C100N, f"DVDD, pin {p}") for i, p in enumerate(("6", "23", "39"))],
    cap("C13", V33, C100N, "ADC_AVDD, pin 44"),
    cap("C14", V33, C100N, "USB_OTP_VDD and QSPI_IOVDD, pins 53-54"),
    # the 12 MHz crystal: Raspberry Pi's ABM8-272-T3 (10 pF), 15 pF each side, 1k into XOUT
    dict(ref="Y1", sym="Device:Crystal_GND24", value="12MHz", fp="pqrp:RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm",
         lcsc="C20625731", mpn="ABM8-272-T3", nets={"1": "XIN", "3": "XTAL_OUT", "2": GND, "4": GND}),
    res("R2", "XOUT", "XTAL_OUT", R1K, "keeps the crystal from being over-driven"),
    cap("C15", "XIN", dict(value="15p", fp=C0402, lcsc="C1548")),
    cap("C16", "XTAL_OUT", dict(value="15p", fp=C0402, lcsc="C1548")),
    # the flash: 16 MB, the minimal design's. The stock Pico 2 MicroPython uses the first 4 MB.
    dict(ref="U6", sym="Memory_Flash:W25Q128JVS", value="W25Q128JVSIQ", fp="Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
         lcsc="C97521", mpn="W25Q128JVSIQ",
         nets={"1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": GND, "5": "QSPI_SD0", "6": "QSPI_SCLK",
               "7": "QSPI_SD3", "8": V33}),
    cap("C17", V33, C100N, "the flash's VCC"),
    # BOOTSEL: QSPI_SS low at reset starts the RP2350's USB boot. Through 1k, as the minimal design,
    # so the RP2350 can still drive it once booted
    res("R3", "QSPI_SS", "BOOT_SW", R1K),
    dict(ref="SW5", value="BOOTSEL", nets={"1": "BOOT_SW", "2": GND}, **SW),
    # RESET: RUN has its own pull-up inside
    dict(ref="SW4", value="RESET", nets={"1": "RUN", "2": GND}, **SW),

    # --- power: USB-C in, 5 V to 3.3 V. CC1 and CC2 at 5.1k: a sink, so a C-to-C cable gives 5 V.
    dict(ref="J1", sym="Connector:USB_C_Receptacle_USB2.0_16P", value="USB-C",
         fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948", mpn="TYPE-C-31-M-12",
         nets={"A1": GND, "A12": GND, "B1": GND, "B12": GND, "SH": GND,
               "A4": VBUS, "A9": VBUS, "B4": VBUS, "B9": VBUS, "A5": "CC1", "B5": "CC2",
               "A6": "USB_D+", "B6": "USB_D+", "A7": "USB_D-", "B7": "USB_D-"}),
    res("R4", "CC1", GND, dict(value="5.1k", fp=R0402, lcsc="C25905")),
    res("R5", "CC2", GND, dict(value="5.1k", fp=R0402, lcsc="C25905")),
    dict(ref="U2", sym="Power_Protection:USBLC6-2SC6", value="USBLC6-2SC6", fp="Package_TO_SOT_SMD:SOT-23-6",
         lcsc="C7519", nets={"1": "USB_D+", "6": "USB_D+", "3": "USB_D-", "4": "USB_D-", "5": VBUS, "2": GND},
         why="ESD on D+, D- and VBUS at the connector"),
    dict(ref="U3", sym="Regulator_Linear:XC6206PxxxMR", value="XC6206P332MR", fp="Package_TO_SOT_SMD:SOT-23-3",
         lcsc="C5446", mpn="XC6206P332MR-G", nets={"3": VBUS, "2": V33, "1": GND},
         why="200 mA: the RP2350, the backlight and the key draw well under it"),
    cap("C18", VBUS, C10U, "XC6206 in; USB allows 10u on VBUS"),
    cap("C19", V33, C10U, "XC6206 out, and the board's bulk"),

    # --- the link: the USB-C's D+/D- reach the CH343P and nothing else. It is a standard USB serial
    # device (CDC-ACM): no driver anywhere. VDD5 from VBUS, its own 3.3 V on V3 for its USB side, its
    # serial pins at VIO = the board's 3.3 V (WCH's datasheet, 5.2). TXD and RXD go to UART1 on
    # GPIO20/21. DTR and RTS go nowhere, on purpose: the computer can't reset the RP2350 or hold
    # BOOTSEL. DTR is also a strap at power-up (a pull-down there changes its mode): it floats.
    dict(ref="U4", sym="Interface_USB:CH343P", value="CH343P", fp="Package_DFN_QFN:WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm",
         lcsc="C2846043", mpn="CH343P",
         nets={"3": VBUS, "9": VBUS, "6": "CH_V3", "1": V33, "2": GND, "17": GND, "7": "USB_D+", "8": "USB_D-",
               "4": "LINK_RX", "5": "LINK_TX"}),
    cap("C20", VBUS, C1U, "CH343P VDD5"), cap("C21", "CH_V3", C100N, "CH343P V3: about 0.1u, WCH says"),
    cap("C22", V33, C100N, "CH343P VIO"),

    # --- the key: the ATECC608C in SOIC-8 on I2C0 (GPIO4/5, the Pico's), 4.7k pull-ups to 3.3 V
    dict(ref="U5", sym="Security:ATECC608A-SSHDA", value="ATECC608C-SSHDA-T", fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
         lcsc="C28975195", mpn="ATECC608C-SSHDA-T", nets={"8": V33, "4": GND, "5": "SDA", "6": "SCL"},
         why="same pins as the 608A symbol"),
    cap("C23", V33, C100N, "ATECC608C VCC"),
    res("R6", V33, "SDA", dict(value="4.7k", fp=R0402, lcsc="C25900")),
    res("R7", V33, "SCL", dict(value="4.7k", fp=R0402, lcsc="C25900")),

    # --- the screen: console-usb's. The 1.14" 240x135 ST7789 on an 8-pin 0.5 mm FPC, pin order from
    # the seller's listing (1 LEDA, 2 GND, 3 RESET, 4 RS, 5 SDA, 6 SCL, 7 VDD, 8 CS); check it on the
    # panel bought before the layout. The backlight's cathode is on GND inside, so it's switched
    # high: Q1 (P-FET) from 3.3 V, turned on by Q2 when GPIO13 is high.
    dict(ref="J2", sym="Connector_Generic:Conn_01x08", value="PANEL",
         fp="pqrp:FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB", lcsc="C2919492",
         mpn="0.5K-HX-8PWB", nets={"1": "LCD_LEDA", "2": GND, "3": "LCD_RST", "4": "LCD_DC",
                                   "5": "LCD_MOSI", "6": "LCD_SCK", "7": V33, "8": "LCD_CS"}),
    cap("C24", V33, C1U, "the panel's VDD"), cap("C25", V33, C100N),
    dict(ref="Q1", sym="Transistor_FET:AO3401A", value="AO3401A", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C15127",
         nets={"2": V33, "3": "BL_SW", "1": "BL_GATE"}),
    res("R8", "BL_SW", "LCD_LEDA", dict(value="22R", fp=R0402, lcsc="C25092"), "backlight current, about 10 mA: tune at bring-up"),
    res("R9", V33, "BL_GATE", R10K, "Q1 off by default"),
    dict(ref="Q2", sym="Transistor_BJT:SS8050", value="S8050", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C2150",
         mpn="SS8050", nets={"1": "BL_BASE", "2": GND, "3": "BL_GATE"}),
    res("R10", "LCD_BL", "BL_BASE", R1K),
    res("R11", "LCD_BL", GND, dict(value="4.7k", fp=R0402, lcsc="C25900"),
        "the backlight stays off until the firmware turns it on; under the 8.2k RP2350-E9 asks of a pull-down"),

    # --- the buttons, in a row under the screen, each to GND: pulled up inside the RP2350 and
    # pressed low: no pull-downs inside (RP2350-E9)
    dict(ref="SW1", value="D0", nets={"1": "BTN_D0", "2": GND}, **SW),
    dict(ref="SW2", value="D1", nets={"1": "BTN_D1", "2": GND}, **SW),
    dict(ref="SW3", value="D2", nets={"1": "BTN_D2", "2": GND}, **SW),

    # --- the LED on GPIO25, the Pico 2's
    res("R12", "LED", "LED_A", R1K),
    dict(ref="D1", sym="Device:LED", value="RED", fp="LED_SMD:LED_0603_1608Metric", lcsc="C2286", mpn="KT-0603R",
         nets={"2": "LED_A", "1": GND}),

    # --- the bench header, not fitted: SWD, the RP2350's own USB (its REPL, and BOOTSEL's USB
    # boot), and the key's bus for a key on wires. Holes only; a header goes in for bring-up.
    dict(ref="J3", sym="Connector_Generic:Conn_01x08", value="BENCH", fp="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
         nets={"1": GND, "2": V33, "3": "SWCLK", "4": "SWDIO", "5": "DEV_D-", "6": "DEV_D+", "7": "SDA", "8": "SCL"},
         dnp=True, bom=False),
    res("R13", "RP_DM", "DEV_D-", R27, "USB's 27 R, close to the chip"),
    res("R14", "RP_DP", "DEV_D+", R27),
] + [dict(ref=f"H{i}", sym="Mechanical:MountingHole", value="M2.5", fp="MountingHole:MountingHole_2.7mm_M2.5",
          nets={}, bom=False) for i in range(1, 5)]

# Nets KiCad would call undriven: VBUS comes in on a passive pin, DVDD through L1, VREG_AVDD through
# R1. Each gets a PWR_FLAG.
FLAGS = [GND, VBUS, "DVDD", "VREG_AVDD"]

# The RP2350's function table (its datasheet, GPIO functions F1-F3): which GPIOs can carry each.
FUNC = {"UART1 TX": {4, 8, 20, 24}, "UART1 RX": {5, 9, 21, 25}, "I2C0 SDA": {0, 4, 8, 12, 16, 20, 24, 28},
        "I2C0 SCL": {1, 5, 9, 13, 17, 21, 25, 29}, "SPI1 SCK": {10, 14, 26}, "SPI1 TX": {11, 15, 27}}
NEEDS = {"LINK_TX": "UART1 TX", "LINK_RX": "UART1 RX", "SDA": "I2C0 SDA", "SCL": "I2C0 SCL",
         "LCD_SCK": "SPI1 SCK", "LCD_MOSI": "SPI1 TX"}

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
    "U1": (g(80), g(64)),
    # power in
    "J1": (g(14), g(22)), "R4": (g(26), g(14)), "R5": (g(30), g(14)), "U2": (g(14), g(42)),
    "U3": (g(28), g(32)), "C18": (g(22), g(40)), "C19": (g(34), g(40)),
    # the link
    "U4": (g(16), g(68)), "C20": (g(28), g(62)), "C21": (g(32), g(62)), "C22": (g(36), g(62)),
    # the RP2350's supplies, in a row above it
    "R1": (g(46), g(14)), "C3": (g(50), g(16)), "L1": (g(54), g(14)), "C1": (g(58), g(16)), "C2": (g(62), g(16)),
    **{f"C{4 + i}": (g(66 + 4 * i), g(16)) for i in range(11)},
    # the crystal, RESET, the flash and BOOTSEL, left of it
    "Y1": (g(50), g(98)), "R2": (g(50), g(90)), "C15": (g(44), g(104)), "C16": (g(56), g(104)),
    "SW4": (g(48), g(52)),
    "U6": (g(46), g(72)), "C17": (g(56), g(66)), "R3": (g(54), g(80)), "SW5": (g(58), g(84)),
    "R13": (g(48), g(30)), "R14": (g(54), g(30)),
    # the key
    "U5": (g(116), g(14)), "C23": (g(126), g(12)), "R6": (g(108), g(28)), "R7": (g(112), g(28)),
    # the screen and its backlight
    "J2": (g(116), g(46)), "C24": (g(128), g(42)), "C25": (g(132), g(42)),
    "Q1": (g(142), g(54)), "R8": (g(148), g(48)), "R9": (g(136), g(54)), "Q2": (g(140), g(64)),
    "R10": (g(134), g(66)), "R11": (g(128), g(70)),
    # the buttons and the LED
    "SW1": (g(110), g(84)), "SW2": (g(122), g(84)), "SW3": (g(134), g(84)),
    "R12": (g(148), g(80)), "D1": (g(148), g(88)),
    "J3": (g(156), g(16)),
    "H1": (g(146), g(100)), "H2": (g(150), g(100)), "H3": (g(154), g(100)), "H4": (g(158), g(100)),
}
FLAG_AT = {GND: (g(6), g(100)), VBUS: (g(10), g(100)), "DVDD": (g(14), g(100)), "VREG_AVDD": (g(18), g(100))}
NOTES = [
    (g(4), g(106), "console-rp: the console with no radio. See hardware/console-rp/README.md.\n"
                   "Every connection is a name: a net label or a power symbol at the end of each pin's stub."),
    (g(2), g(80), "The link. The USB-C's D+ and D- reach the CH343P and nothing else.\n"
                  "TXD/RXD go to UART1 (GPIO21/20). DTR and RTS are NOT connected,\n"
                  "on purpose: the computer can't reset the RP2350 or hold BOOTSEL.\n"
                  "Don't add auto-reset."),
    (g(62), g(106), "The RP2350's regulator (L1, C1, C2, R1, C3) is Raspberry Pi's minimal design.\n"
                    "Copy its layout and L1's orientation exactly (Hardware design with RP2350, 2.1)."),
    (g(104), g(36), "J2: pin order from the seller's listing. Check it on the panel before the layout."),
    (g(140), g(36), "J3 is not fitted: holes for a header at the bench.\n"
                    "SWD, and the RP2350's own USB: its REPL, and USB boot\n"
                    "(hold BOOTSEL, press RESET). Nothing reaches them through the USB-C."),
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
        self.uuids = {}
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
        u = self.uuids[ref] = uid()      # the board's footprint points back to it
        self.items.append(
            f'(symbol (lib_id {q(lib_id)}) (at {x} {y} {rot}) (unit 1) (exclude_from_sim no) (in_bom {yn(in_bom)}) '
            f'(on_board yes) (dnp {yn(dnp)}) (uuid "{u}")\n' + "\n".join(props) + "\n"
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
(title_block (title "PicoQuorum console-rp: an RP2350, no radio, USB serial to the host") (date "{DATE}") (rev "A")
  (company "PicoQuorum") (comment 1 "Written by hardware/console-rp/gen_console_rp.py. CERN-OHL-W v2")
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
    d["board"]["design_settings"]["rules"]["min_hole_to_hole"] = 0.25     # Raspberry Pi's, for their via pairs: JLCPCB's is 0.2
    d["board"]["design_settings"]["rules"]["min_clearance"] = 0.125       # Raspberry Pi's wide 0402 (C1, C2) sets its pads' own 0.125
    # 0.15 mm between copper, as Raspberry Pi's board: its QFN's pads are 0.17 apart. Signals at
    # 0.2 mm (at 0.15 the router necked down to 0.11 mm in far more places). Power at
    # 0.25 mm, the widest a track can meet a 0.4 mm-pitch pad at and keep 0.15 from the next.
    # Ground the same, in a class of its own that `tools/keypcb route` leaves to the pours: the
    # router's ground tracks blocked the flash's and the chip's lines
    cls = d["net_settings"]["classes"]
    cls[0].update(clearance=CLEAR, track_width=0.2, via_diameter=0.6, via_drill=0.3)
    cls.append(dict(cls[0], name="Power", priority=0, track_width=0.25))
    cls.append(dict(cls[0], name="Ground", priority=1, track_width=0.25))
    d["net_settings"]["netclass_patterns"] = ([{"netclass": "Power", "pattern": n} for n in (V33, VBUS)]
                                              + [{"netclass": "Ground", "pattern": GND}])
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
    lines = ["# console-rp: the RP2350's pins", "",
             "*Written by `gen_console_rp.py`; don't edit by hand.*", "",
             "| GPIO | RP2350A pin | net | what | board.py's Pico default |", "|---|---|---|---|---|"]
    what = {"BTN_D0": "D0, to GND: pull-up inside, pressed low", "BTN_D1": "D1, to GND: pull-up inside, pressed low",
            "BTN_D2": "D2, to GND: pull-up inside, pressed low", "SDA": "I2C0 SDA, the key's bus, 4.7k to 3.3 V",
            "SCL": "I2C0 SCL, the key's bus, 4.7k to 3.3 V", "LED": "red LED, high is on",
            "LINK_TX": "UART1 TX to the CH343P's RXD", "LINK_RX": "UART1 RX from the CH343P's TXD",
            "LCD_MOSI": "SPI1 TX, the screen's SDA", "LCD_SCK": "SPI1 SCK, the screen's SCL", "LCD_DC": "the screen's RS",
            "LCD_RST": "the screen's RESET", "LCD_CS": "the screen's CS", "LCD_BL": "backlight, high is on; 4.7k down"}
    pico = pico_pins()
    for net, gp in sorted(GPIO.items(), key=lambda kv: kv[1]):
        lines.append(f"| {gp} | {pin_of[gp]} | `{net}` | {what[net]} | {pico.get(gp, '')} |")
    lines += ["", "Also: QSPI to the flash (pins 55–60), XIN/XOUT to the crystal, RUN to RESET, SWCLK/SWDIO and",
              "USB_DP/DM (through 27 R) to J3 only. Not connected: GPIO 0, 1, 7, 14–19, 22–24 and 26–29.", ""]
    with open(os.path.join(HERE, "PINS.md"), "w") as f:
        f.write("\n".join(lines))


# =================================================================================================
# The checks
# =================================================================================================
def pico_pins():
    """firmware/board.py's Pico pins (its defaults, before any profile), GPIO -> role. Read only."""
    b = open(os.path.join(REPO, "firmware", "board.py")).read()
    dc, cs, sck, mosi, rst, bl = map(int, re.search(r"^DC, CS, SCK, MOSI, RST, BL = ([\d, ]+)\n", b, re.M).group(1).split(","))
    spi, sda, scl = map(int, re.search(r"^SPI_ID, SDA, SCL, LED = (\d+), (\d+), (\d+),", b, re.M).groups())
    return {dc: "DC", cs: "CS", sck: f"SCK (SPI{spi})", mosi: f"MOSI (SPI{spi})", rst: "RST", bl: "BL", sda: "SDA", scl: "SCL"}


def check_firmware(bad):
    want = {"LCD_DC": "DC", "LCD_CS": "CS", "LCD_SCK": "SCK (SPI1)", "LCD_MOSI": "MOSI (SPI1)", "LCD_RST": "RST",
            "LCD_BL": "BL", "SDA": "SDA", "SCL": "SCL"}
    pico = pico_pins()
    for net, role in want.items():
        if pico.get(GPIO[net]) != role:
            bad.append(f"{net} is GPIO{GPIO[net]}, but board.py's Pico pins have {pico.get(GPIO[net])!r} there (wants {role})")
    for net, fn in NEEDS.items():
        if GPIO[net] not in FUNC[fn]:
            bad.append(f"{net} is GPIO{GPIO[net]}, which can't be {fn}")
    names = {n: name for n, name, *_ in stock("MCU_RaspberryPi:RP2350A")[1]}
    u1 = next(p for p in PARTS if p["ref"] == "U1")["nets"]
    for pin, gp in PIN_GPIO.items():
        if not re.match(rf"GPIO{gp}(/|$)", names.get(pin, "")):
            bad.append(f"U1 pin {pin} is {names.get(pin)!r} in KiCad's symbol, not GPIO{gp}")
        if GPIO.get(u1.get(pin)) != gp:
            bad.append(f"U1 pin {pin} is GPIO{gp} but carries {u1.get(pin)}")


def check_link(bad, nets):
    """What the computer can reach, from the netlist: the USB-C's data lines only the CH343P, the
    CH343P's DTR and RTS nothing, the RP2350's own USB and SWD only J3, BOOTSEL and RUN only their
    buttons."""
    def on(net):
        return {r for r, _ in nets.get("/" + net, ())}
    for n, s in nets.items():
        if any(r == "U4" and pin in ("12", "13") for r, pin in s) and not n.startswith("unconnected-"):
            bad.append(f"the CH343P's DTR or RTS is connected ({n}): the computer could reset the RP2350 or hold BOOTSEL")
        if any(r == "J1" for r, _ in s) and any(r == "U1" for r, _ in s) and n not in POWER:
            bad.append(f"the USB-C reaches the RP2350 directly on {n}")
    for net in ("USB_D+", "USB_D-"):
        if on(net) != {"J1", "U2", "U4"}:
            bad.append(f"{net} reaches {sorted(on(net))}; it should be the USB-C, its ESD diodes and the CH343P only")
    for net, want in (("RP_DP", {"U1", "R14"}), ("RP_DM", {"U1", "R13"}), ("DEV_D+", {"R14", "J3"}), ("DEV_D-", {"R13", "J3"}),
                      ("SWCLK", {"U1", "J3"}), ("SWDIO", {"U1", "J3"}), ("RUN", {"U1", "SW4"}),
                      ("QSPI_SS", {"U1", "U6", "R3"}), ("BOOT_SW", {"R3", "SW5"}), ("LINK_TX", {"U1", "U4"}),
                      ("LINK_RX", {"U1", "U4"})):
        if on(net) != want:
            bad.append(f"{net} reaches {sorted(on(net))}, not {sorted(want)}")


def netlist():
    """KiCad's own reading of the schematic: net name -> {(ref, pin)}."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "n.net")
        subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out,
                        os.path.join(OUT, NAME + ".kicad_sch")], check=True, capture_output=True, env=kicad_env(tmp))
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
        out = os.path.join(tmp, "erc.json")
        subprocess.run([CLI, "sch", "erc", "--format", "json", "--severity-all", "-o", out,
                        os.path.join(OUT, NAME + ".kicad_sch")], capture_output=True, env=kicad_env(tmp))
        rep = json.load(open(out))
    found = []
    for sheet in rep.get("sheets", []):
        for v in sheet.get("violations", []):
            items = "; ".join(i.get("description", "") for i in v.get("items", []))
            found.append((v["severity"], v["type"], items))
    for f in found:
        print(f"  ERC {f[0]} {f[1]}: {f[2]}  <- not expected")
        bad.append(f"ERC {f[0]} {f[1]}: {f[2]}")
    return found


def check_footprints(bad):
    """Every symbol pin has a pad of the same number in its footprint, and every copper pad a pin."""
    import pcbnew
    for p in PARTS:
        lib, name = p["fp"].split(":")
        fp = pcbnew.FootprintLoad(fp_lib(lib), name)
        if fp is None:
            bad.append(f"{p['ref']}: no footprint {p['fp']}")
            continue
        pads = {pd.GetNumber() for pd in fp.Pads() if pd.GetNumber() and pd.IsOnCopperLayer()}
        pins = {n for n, *_ in stock(p["sym"])[1]}
        if pins - pads:
            bad.append(f"{p['ref']}: pins {sorted(pins - pads)} have no pad in {p['fp']}")
        if pads - pins:
            bad.append(f"{p['ref']}: pads {sorted(pads - pins)} of {p['fp']} have no pin")


def kicad_env(tmp):
    """kicad-cli with a fresh config: KiCad's default library tables, pointed at its stock libraries."""
    ver = "10.0"
    cfg = os.path.join(tmp, ver)
    os.makedirs(cfg, exist_ok=True)
    for t in ("sym-lib-table", "fp-lib-table"):
        shutil.copy(os.path.join(KITPL, t), cfg)
    return dict(os.environ, KICAD_CONFIG_HOME=tmp, KICAD10_SYMBOL_DIR=KISYM, KICAD10_FOOTPRINT_DIR=KIFP,
                KICAD10_3DMODEL_DIR=KI3D)


# =================================================================================================
# The board: every part placed, not routed. Board coordinates in mm from the top-left corner, y
# down; the page puts that corner at (OX, OY).
# =================================================================================================
W, H = 72.0, 36.0
OX, OY = 100.0, 100.0
CORNER = 2.0
LIB = os.path.join(HERE, "lib")
CLEAR = 0.15                             # the Default and Power classes' clearance (write_project)
SHAPES = os.path.join(LIB, "pqrp.3dshapes")
MARK = os.path.join(LIB, "picoquorum.pretty")     # a copy of console-pocket's, so a copy of the project finds it

# The panel, console-usb's (and console-s3's) numbers: glass 31 x 17 mm and a 23 mm tail from one
# seller's listing, the active area from Waveshare's 1.14" module, 1.6 mm thick. The glass lies on
# 2 mm foam pads at its corners; the tail leaves its right end, folds under it and comes back into
# J2, using about 5.7 mm in the fold. Measure a panel before ordering.
PANEL = dict(glass=(31.0, 17.0), active=(24.912, 14.864), rows=135, cols=240, thick=1.6, foam=2.0,
             pad=2.0, tail=23.0, fold=5.7, ribbon=4.5)
GX0, GY0 = 5.0, 4.5                      # the glass's top-left corner on the board
GX1, GY1 = GX0 + PANEL["glass"][0], GY0 + PANEL["glass"][1]
XC, YC = (GX0 + GX1) / 2, (GY0 + GY1) / 2
ZIF_IN = GX1 + 1.0 - (PANEL["tail"] - PANEL["fold"]) + 1.0   # where the ribbon's end reaches, as console-s3

# Heights (mm) of what sits under the glass, which has PANEL["foam"] of room
UNDER = {"_0402_": 0.5, "_0603_": 0.8, "SOT-23": 1.15, "HDGC": 1.0}


def slot(i):
    """x of button i: under the middle of footer slot i, as quorum_ui_s.bar draws three slots of
    (W - 8) // 3 pixels, 2 apart, from x = 2 (the QT Py's footer, 240 wide here)."""
    sw = (PANEL["cols"] - 8) // 3
    px = 2 + i * (sw + 2) + sw / 2
    return round(XC - PANEL["active"][0] / 2 + px * PANEL["active"][0] / PANEL["cols"], 3)


BY = 28.5                                # the buttons' row, under the glass
# ref -> (x, y, rotation in degrees). Under the glass: only parts lower than the tape, none in the
# foam pads' corners, none in the ribbon's path (y 10.75-15.25 right of J2).
AT = {
    "SW1": (slot(0), BY, 0), "SW2": (slot(1), BY, 0), "SW3": (slot(2), BY, 0),
    "H1": (3.0, 3.0, 0), "H2": (3.0, H - 3.0, 0), "H3": (W - 3.0, 9.0, 0), "H4": (W - 3.0, H - 3.0, 0),
    # under the glass: the screen's connector, its decoupling and the backlight switch
    "J2": (round(ZIF_IN - 1.9, 3), YC, 90), "C24": (23.0, 8.0, 0), "C25": (23.0, 18.0, 0),
    "R9": (8.0, 7.5, 90), "Q1": (10.5, 7.5, 0), "R8": (13.0, 7.5, 90),
    "Q2": (10.5, 18.5, 0), "R10": (8.0, 18.5, 90), "R11": (13.0, 18.5, 90),
    # right of the glass: the RP2350 with Raspberry Pi's parts round it (RPI, below: the regulator
    # above-right, where VREG is, a 100n at each power pin, the USB resistors above, the crystal
    # below), the flash above-left of it (QSPI is its top-left side)
    "U1": (46.5, 15.0, 0),
    "U6": (39.4, 4.2, 0), "C17": (45.55, 5.6, -90), "R3": (37.8, 8.4, -90),
    "C9": (52.985, 13.2, 0),                     # pin 45's: Raspberry Pi's C17 serves pins 44 and 45 together
    # the link and power in
    "U4": (57.0, 18.0, 0), "C20": (57.0, 14.6, 0), "C21": (57.0, 21.6, 0), "C22": (54.5, 21.6, 90),
    "J1": (W - 3.6, 21.0, 90), "U2": (60.6, 22.0, 0), "R4": (61.0, 18.2, 0), "R5": (61.0, 25.6, 0),
    "U3": (63.5, 9.0, 0), "C19": (59.5, 9.0, 90), "C18": (63.5, 12.8, 0),
    # the key (below the crystal's corner, its 100n up-left of pin 8), RESET, BOOTSEL and the LED
    # along the bottom; the bench header along the top
    "U5": (42.0, 32.0, 0), "C23": (42.2, 28.7, 180), "R6": (47.0, 31.2, -90), "R7": (48.4, 31.2, -90),
    "SW4": (54.0, 30.0, 0), "SW5": (61.5, 30.0, 0), "D1": (53.5, 25.5, 0), "R12": (51.0, 25.5, 0),
    "J3": (64.98, 2.8, -90),                      # pin 1 at the right: SDA and SCL nearest U1, D+ and D- in their order
}
# Raspberry Pi's minimal board round the chip (rpi_minimal.py wrote it from their MIT KiCad files):
# their footprints and where each part sits from U1's centre, and their power copper, which
# write_board copies as it is. Their U1 and ours have the same pads in the same places.
RPI = json.load(open(os.path.join(HERE, "rpi_minimal.json")))
for _ref, _q in RPI["parts"].items():
    AT[_ref] = (round(AT["U1"][0] + _q["at"][0], 4), round(AT["U1"][1] + _q["at"][1], 4), _q["rot"])
    next(p for p in PARTS if p["ref"] == _ref)["fp"] = _q["fp"]
# The one place ours differs: their C12 (our C14, pins 53-54's) sits up-left, where our flash's
# lines run (it is 1.9 mm nearer the chip than theirs). Its track (DROP) is left out; ours from pin
# 54 runs up beside the flash's lines to C14 and C17 above the USB resistors, and on to the flash.
AT["C14"] = (45.55, 3.6, 90)
DROP = {((0.0, -3.4375), (0.0, -3.9)), ((0.0, -3.9), (-0.4, -4.3)), ((-0.4, -3.4375), (-0.4, -4.3)),
        ((-0.4, -4.3), (-2.1, -6.0)), ((-2.1, -6.0), (-2.1, -6.92))}
# And their two ground vias beside C1's and C2's ground pads, 0.05 mm from the pads' mask openings,
# where solder would run down them: one goes 0.15 mm out (0.2 mm from C2's), and the other, which
# has no room to (VREG_AVDD's track is 0.8 mm from C1), is left out; C1's pad has the track to the first.
VIA_MOVE = {(3.1, -5.5): (3.25, -5.5), (3.1, -4.9): None}

# Raspberry Pi's pours join pads that their tracks don't: a router reading only tracks would join them
# again with its own. These tracks, inside the pours and on the same nets, join them for it (U1's
# centre is 0, 0): (net, [points]). VREG_LX from pin 48 down the channel between C1's and C2's pads
# to L1; PGND from pin 47 by C1 and C2 to their via (VIA_MOVE); VREG_VIN from pin 49 to C1, and on into the
# 3V3 ring under the chip, which meets the stubs of pins 11, 20, 30, 38 and 53-54, and pins 44 and
# 45, which their pour joined; the DVDD ring
# inside it, through its four vias; and DVDD from L1 by C2 to the vias that take it under the chip.
LINKS = [
    ("/VREG_LX", [(2.0, -3.45), (2.0, -5.95), (2.7, -6.65), (2.7, -7.2)]),
    (GND, [(2.4, -3.45), (2.4, -4.61), (2.9, -4.9), (3.1, -4.9), (3.1, -5.5)]),
    (GND, [(2.515, -5.55), (3.05, -5.55), (3.1, -5.5), (3.25, -5.5)]),
    (V33, [(1.6, -2.7), (1.6, -4.05), (1.485, -4.3), (1.485, -4.61)]),
    (V33, [(3.45, -2.4), (3.45, -2.8), (2.75, -2.75)]),
    (V33, [(-2.75, -2.75), (2.75, -2.75), (2.75, 0.0), (2.75, 2.75), (2.574, 2.75), (-1.2, 2.75), (-2.75, 2.75),
           (-2.75, 1.2), (-2.75, -2.75)]),
    ("/DVDD", [(-2.15, -2.15), (0.488, -2.15), (2.15, -2.15), (2.15, -0.4), (2.15, 2.15), (0.2, 2.15), (-2.15, 2.15),
               (-2.15, -0.8), (-2.15, -2.15)]),
    ("/DVDD", [(1.3, -7.2), (1.3, -6.4), (1.485, -6.0), (1.485, -5.55), (0.85, -5.55), (0.5, -5.2)]),
    ("/DVDD", [(0.925, -5.125), (0.5, -5.2)]),
]
# The flash's six lines, drawn here and locked (board mm, F.Cu, 0.15 mm): the router left some open
# every time. Raspberry Pi's fan-out from pins 55-60, then as theirs: SD0 into pin 5 from below,
# SCLK and SD3 past the right ends of pins 5-6 into 6 and 7, SD2 under the flash into pin 3, SD1 and
# SS round its left into 2 and 1, SS by R3. Then 3V3 from pin 54, between SD3 and RP_DP as theirs
# to C12, up to C17 and C14 and into the flash's pin 8; and the flash's ground pin to a via.
FLASH = [
    ("/QSPI_SD3", [(45.7, 11.55), (45.7, 10.8), (44.4, 9.5), (44.4, 3.565), (42.988, 3.565)]),
    ("/QSPI_SCLK", [(45.3, 11.55), (45.3, 10.9), (44.05, 9.65), (44.05, 4.835), (42.988, 4.835)]),
    ("/QSPI_SD0", [(44.9, 11.55), (44.9, 11.0), (43.5, 9.6), (43.5, 6.105)]),
    ("/QSPI_SD2", [(44.5, 11.55), (44.5, 11.1), (38.235, 4.835), (35.812, 4.835)]),
    ("/QSPI_SD1", [(44.1, 11.55), (44.1, 11.136), (39.864, 6.9), (34.85, 6.9), (34.5, 6.55), (34.5, 3.565), (35.812, 3.565)]),
    ("/QSPI_SS", [(43.7, 11.55), (43.7, 11.3), (39.65, 7.25), (37.8, 7.25), (34.5, 7.25), (34.15, 6.9), (34.15, 2.295), (35.812, 2.295)]),
    ("/QSPI_SS", [(37.8, 7.25), (37.8, 7.89)]),
    (GND, [(35.812, 6.105), (37.2, 6.105)]),
]
SPINE = [(V33, [(46.1, 11.55), (46.1, 10.7), (44.775, 9.375), (44.775, 5.12), (44.775, 4.08), (44.775, 2.295), (42.988, 2.295)]),
         (V33, [(44.775, 5.12), (45.55, 5.12)]), (V33, [(44.775, 4.08), (45.55, 4.08)])]
# The bench USB, from between R14, C17, R13 and C14 to J3: D+ between C17 and R13, up right of C17,
# far enough out for C17's ground via, and along under J3's SCL and SDA; D- under C14 and along above L1.
BENCH = [
    ("/DEV_D+", [(45.4, 7.125), (45.4, 6.6), (46.85, 6.6), (46.85, 4.3), (51.98, 4.3), (52.28, 4.0), (52.28, 2.8)]),
    ("/DEV_D-", [(46.4, 7.125), (46.9, 7.125), (47.2, 6.615), (48.2, 6.615), (48.5, 6.3), (54.52, 6.3), (54.82, 6.0),
                 (54.82, 2.8)]),
]
# The key's bus, from pins 7 and 8 past Raspberry Pi's C10 and C5 to a via each, one above the other:
# the router left pin 8 shut in between its SDA and D2 every time. It takes them on to J3 and U5.
BUS = [("/SDA", [(43.05, 14.6), (39.0, 14.6), (38.7, 14.75)]), ("/SCL", [(43.05, 15.0), (39.3, 15.0), (38.7, 15.6)])]
# Three more: the backlight switch's collector straight up to a via, which the router took round R10
# at 0.1 mm; C9's 3V3 to C13's, beside it, which the router left off; and C14's ground, shut in by
# the 3V3 track and D+, up to a via.
TIES = [("/BL_GATE", [(11.438, 18.5), (11.438, 17.3)]), (V33, [(52.505, 13.2), (52.51, 12.0)]), (GND, [(45.55, 3.12), (45.55, 2.2)])]
# SWCLK, SWDIO and RUN out from pins 24-26 past the DVDD copper, as Raspberry Pi's: three 45-degree
# lines down and right. RUN then drops to a via for the back, to RESET; the router takes SWD on to J3.
SWD = [("/RUN", [(47.7, 18.45), (47.7, 19.5), (49.6, 21.4), (50.1, 21.4)]),
       ("/SWDIO", [(47.3, 18.45), (47.3, 19.7), (49.6, 22.0), (50.5, 22.0)]),
       ("/SWCLK", [(46.9, 18.45), (46.9, 19.9), (49.6, 22.6), (50.5, 22.6)])]
# (net, where, locked): BL_GATE's via unlocked, so the route's tidy-up drops it if the router stays on the front.
# Two ground vias for pads the pour can't reach otherwise: C17's, shut in by the 3V3 spine and D+, beside
# it; and the CH343P's, its exposed pad and pin 2 shut in by its pins, in the exposed pad (jlc_spec says so)
HAND_VIAS = [(GND, (37.2, 6.105), True), ("/SDA", (38.7, 14.75), True), ("/SCL", (38.7, 15.6), True),
             ("/BL_GATE", (11.438, 17.3), False), (GND, (45.55, 2.2), True), ("/RUN", (50.1, 21.4), True),
             (GND, (46.3, 5.6), True), (GND, (57.0, 18.55), True)]

# Pads joined to the ground pours solid, not by thermal spokes: C1's and C2's, inside Raspberry Pi's
# pours as theirs are, and J1's and C17's, between other copper, where spokes don't fit
SOLID = {("C1", "2"), ("C2", "2"), ("C17", "2"), ("J1", "A1"), ("J1", "A12"), ("J1", "B1"), ("J1", "B12")}

# Raspberry Pi's areas round U1 (from its centre), where only their nets' copper belongs: the
# regulator's corner on the front (VREG_LX, DVDD, VREG_AVDD, 3V3, ground), under the chip on the
# back (ground and DVDD), the crystal's corner on the front (its pour's outline) and, as theirs, only
# ground on the back under the crystal and its capacitors (UNDER_Y1). Not rule areas: Freerouting routed far worse round fixed copper inside
# them (82 "violations" it couldn't clear, 50 connections left). check_rpi reads the routed board.
RPI_AREAS = [
    ("the regulator's corner", "F.Cu", {"/VREG_LX", "/DVDD", "/VREG_AVDD", V33, GND},
     [(1.0, -3.0), (3.2, -3.0), (4.65, -4.45), (4.65, -6.95), (3.3, -6.95), (3.3, -8.15), (0.85, -8.15), (0.85, -6.3),
      (0.25, -6.3), (0.25, -4.85), (1.0, -4.85)]),
    ("under U1", "B.Cu", {"/DVDD", GND}, [(-2.95, -2.95), (2.95, -2.95), (2.95, 2.95), (-2.95, 2.95)]),
    ("the crystal's corner", "F.Cu", {"/XIN", "/XOUT", "/XTAL_OUT", GND},
     [(-2.8, 8.0), (2.8, 8.0), (3.2, 8.4), (3.2, 14.7), (-3.2, 14.7), (-3.2, 8.4)]),
    ("under the crystal", "B.Cu", {GND}, [(-2.2, 7.9), (2.2, 7.9), (2.2, 14.6), (-2.2, 14.6)]),
]

# The router keeps off the back under U1, except where Raspberry Pi's four DVDD tracks run out
# from their vias (a notch 1 mm wide round each, from U1's centre): a rule area round them works
# where one over them didn't, and without it the router ran SWD and buttons between the ground vias.
UNDER_U1 = [(-2.95, -2.95), (0.0, -2.95), (0.0, -1.65), (1.0, -1.65), (1.0, -2.95), (2.95, -2.95),
            (2.95, -0.9), (1.65, -0.9), (1.65, 0.1), (2.95, 0.1), (2.95, 2.95), (0.7, 2.95), (0.7, 1.65),
            (-0.3, 1.65), (-0.3, 2.95), (-2.95, 2.95), (-2.95, -0.3), (-1.65, -0.3), (-1.65, -1.3), (-2.95, -1.3)]

# The router keeps off the back under the crystal and its capacitors, inside Raspberry Pi's ground
# vias round them
UNDER_Y1 = RPI_AREAS[3][3]

HOLE_RING = 2.6           # no track and no via this close to a hole's centre: an M2.5 screw's washer is 5 mm across

# Stock footprints whose 3D model KiCad's library doesn't ship: a part of the same size and pads
# stands in, in the board and so in the renders
STANDIN = {
    "SW_Push_1P1T_XKB_TS-1187A": "${KICAD10_3DMODEL_DIR}/Button_Switch_SMD.3dshapes/SW_SPST_TL3342.step",
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12":
        "${KICAD10_3DMODEL_DIR}/Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step",
}
ROUTE_NOTE = "Routed by tools/keypcb route; the copper round U1 is Raspberry Pi's (README.md)."

# The warning in the top strip: the triangle's centre and side (mm), then WARN_TEXT beside it
WARN = (8.4, 2.4, 2.4)
WARN_TEXT = "EXPERIMENTAL HARDWARE COSIGNER"

# console-s3's nod to Adventure (Atari 2600, 1980): the 8-bit key and the dragon guarding it, drawn
# in the game's manner, not copied from it. The key is out in the open beside U5, the key that
# signs, its shaft pointing at it. The dragon is the Easter egg: under the glass, below the ribbon's
# path, turned to face the key. Rows top first; pixels of 0.4 and 0.3 mm keep every gap at least
# twice JLCPCB's 0.15 mm.
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
ART = [(KEY, 33.9, 31.2, 0.4),                       # board (x, y) of each one's top left, and its pixel
       (tuple(r[::-1] for r in DRAGON), 27.0, 15.45, 0.3)]     # mirrored, to face the key


def silk_pixels():
    """The art as filled rectangles (board x0, y0, x1, y1): each run of pixels in a row, carried
    down while the row below has the same run."""
    out = []
    for rows, ax, ay, px in ART:
        running = {}
        for r, row in enumerate(rows + ("",)):
            now = {m.span() for m in re.finditer(r"#+", row)}
            for c0, c1 in [k for k in running if k not in now]:
                r0 = running.pop((c0, c1))
                out.append((ax + c0 * px, ay + r0 * px, ax + c1 * px, ay + r * px))
            for span in now - running.keys():
                running[span] = r
    return out


def fp_lib(lib):
    return os.path.join(LIB, "pqrp.pretty") if lib == "pqrp" else MARK if lib == "picoquorum" else os.path.join(KIFP, lib + ".pretty")


# --- 3D boxes for what KiCad has no model of: the panel, its ZIF ---------------------------------
def _wrl_shape(quads, rgb):
    """One VRML shape: quads are 4 (x, y, z) mm points each. VRML units in KiCad are 0.1 inch."""
    pts, idx = [], []
    for qd in quads:
        idx.append(" ".join(str(len(pts) + i) for i in range(4)) + " -1")
        pts += [" ".join(f"{v / 2.54:.4f}" for v in p) for p in qd]
    return (f"Shape {{ appearance Appearance {{ material Material {{ diffuseColor {' '.join(f'{c:.3f}' for c in rgb)} "
            f"specularColor 0.1 0.1 0.1 shininess 0.3 }} }}\n"
            f"geometry IndexedFaceSet {{ solid FALSE coord Coordinate {{ point [ {', '.join(pts)} ] }}\n"
            f"coordIndex [ {', '.join(idx)} ] }} }}\n")


def _box(x0, y0, z0, x1, y1, z1):
    """A box's six faces, in VRML's axes (y north)."""
    return [[(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
            [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
            [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]]


def write_models():
    """The panel as it sits: foam pads, the backlight frame, the glass and its dark active area, and
    the ribbon folding under into J2. Its origin is the glass's centre (LCD1's footprint)."""
    os.makedirs(SHAPES, exist_ok=True)
    gw, gh = PANEL["glass"]
    f, t, p = PANEL["foam"], PANEL["thick"], PANEL["pad"]
    hw, hh, rw = gw / 2, gh / 2, PANEL["ribbon"] / 2
    pads = [_box(sx * hw - (p if sx > 0 else 0), sy * hh - (p if sy > 0 else 0), 0, sx * hw + (0 if sx > 0 else p), sy * hh + (0 if sy > 0 else p), f)
            for sx in (-1, 1) for sy in (-1, 1)]
    aw, ah = PANEL["active"]
    zin = ZIF_IN - XC                            # the ribbon's end, from the glass's centre
    rib = _box(hw, -rw, f, hw + 1.2, rw, f + 0.1) + _box(hw + 1.1, -rw, 0.45, hw + 1.2, rw, f + 0.1) \
        + _box(zin - 1.4, -rw, 0.45, hw + 1.2, rw, 0.55)
    shapes = [_wrl_shape(sum(pads, []), (0.92, 0.92, 0.88)),
              _wrl_shape(_box(-hw, -hh, f, hw, hh, f + t - 0.3), (0.75, 0.76, 0.78)),
              _wrl_shape(_box(-hw, -hh, f + t - 0.3, hw, hh, f + t), (0.02, 0.02, 0.03)),
              _wrl_shape(_box(-aw / 2, -ah / 2, f + t, aw / 2, ah / 2, f + t + 0.01), (0.10, 0.12, 0.16)),
              _wrl_shape(rib, (0.85, 0.45, 0.08))]
    with open(os.path.join(SHAPES, "LCD_1.14in_240x135_on_tape.wrl"), "w") as fh:
        fh.write("#VRML V2.0 utf8\n# The 1.14in panel on its tape. Written by gen_console_rp.py\n")
        fh.writelines(shapes)
    zif = [_wrl_shape(_box(-3.0, -1.6, 0, 3.0, 1.65, 0.75), (0.93, 0.88, 0.75)),
           _wrl_shape(_box(-3.0, 0.9, 0.75, 3.0, 1.65, 1.0), (0.08, 0.08, 0.08))]
    with open(os.path.join(SHAPES, "FPC_ZIF_8P_HDGC_0.5K-HX-8PWB.wrl"), "w") as fh:
        fh.write("#VRML V2.0 utf8\n# HDGC 0.5K-HX-8PWB, a box from its drawing's outline. Written by gen_console_rp.py\n")
        fh.writelines(zif)


def write_footprints():
    """pqrp.pretty: console-s3's ZIF footprint with a 3D body, and the panel as a board-only part; and
    picoquorum.pretty, the mark."""
    os.makedirs(os.path.join(LIB, "pqrp.pretty"), exist_ok=True)
    os.makedirs(MARK, exist_ok=True)
    shutil.copy(os.path.join(REPO, "hardware", "console-pocket", "lib", "picoquorum.pretty", "PicoQuorum_Mark.kicad_mod"), MARK)
    src = os.path.join(REPO, "hardware", "console-s3", "lib", "pqs3.pretty", "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB.kicad_mod")
    zif = open(src).read().replace(
        "\t(embedded_fonts no)",
        '\t(model "${KIPRJMOD}/../lib/pqrp.3dshapes/FPC_ZIF_8P_HDGC_0.5K-HX-8PWB.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n'
        "\t(embedded_fonts no)")
    with open(os.path.join(LIB, "pqrp.pretty", "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB.kicad_mod"), "w") as fh:
        fh.write(zif)
    gw, gh = PANEL["glass"]
    hw, hh, p = gw / 2, gh / 2, PANEL["pad"]
    lines = []
    for sx in (-1, 1):                         # silkscreen corners just outside the glass
        for sy in (-1, 1):
            x, y = sx * (hw + 0.3), sy * (hh + 0.3)
            lines.append(f'\t(fp_line (start {x} {y}) (end {x - sx * 2} {y}) (stroke (width 0.15) (type solid)) (layer "F.SilkS") (uuid "{uid()}"))')
            lines.append(f'\t(fp_line (start {x} {y}) (end {x} {y - sy * 2}) (stroke (width 0.15) (type solid)) (layer "F.SilkS") (uuid "{uid()}"))')
            fx, fy = sx * hw - (p if sx > 0 else 0), sy * hh - (p if sy > 0 else 0)
            lines.append(f'\t(fp_rect (start {fx} {fy}) (end {fx + p} {fy + p}) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab") (uuid "{uid()}"))')
    lines.append(f'\t(fp_rect (start {-hw} {-hh}) (end {hw} {hh}) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab") (uuid "{uid()}"))')
    with open(os.path.join(LIB, "pqrp.pretty", "LCD_1.14in_240x135_on_tape.kicad_mod"), "w") as fh:
        fh.write(f"""(footprint "LCD_1.14in_240x135_on_tape" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")
\t(descr "The 1.14in 240x135 ST7789 panel's glass ({gw} x {gh} mm) on {PANEL['foam']} mm foam pads at its corners (F.Fab). No pads: the ribbon goes to J2. Board only")
\t(property "Reference" "LCD1" (at 0 {-hh - 1.2} 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 0.8 0.8) (thickness 0.12))))
\t(property "Value" "1.14in 240x135" (at 0 0 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
\t(attr board_only exclude_from_pos_files exclude_from_bom)
{chr(10).join(lines)}
\t(model "${{KIPRJMOD}}/../lib/pqrp.3dshapes/LCD_1.14in_240x135_on_tape.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
\t(embedded_fonts no)
)
""")
    with open(os.path.join(OUT, "fp-lib-table"), "w") as fh:
        fh.write('(fp_lib_table\n  (version 7)\n'
                 '  (lib (name "pqrp")(type "KiCad")(uri "${KIPRJMOD}/../lib/pqrp.pretty")(options "")(descr "console-rp\'s own footprints"))\n'
                 '  (lib (name "picoquorum")(type "KiCad")(uri "${KIPRJMOD}/../lib/picoquorum.pretty")(options "")(descr "the mark"))\n)\n')


def write_board(sh, nets):
    import pcbnew
    mm = lambda x, y: pcbnew.VECTOR2I_MM(OX + x, OY + y)
    b = pcbnew.BOARD()
    pad_net = {}
    for name, nodes in nets.items():         # unconnected pins too, on KiCad's unconnected-(...) nets, as the schematic
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        for node in nodes:
            pad_net[node] = name

    def place(fp, ref, x, y, rot):
        fp.SetReference(ref)
        if fp.Reference().GetLayer() == pcbnew.F_SilkS:
            fp.Reference().SetLayer(pcbnew.F_Fab)     # 0402s too close for names: the silkscreen keeps labels only
        fp.SetPosition(mm(x, y))
        fp.SetOrientationDegrees(rot)
        b.Add(fp)
        return fp

    for p in PARTS:
        lib, name = p["fp"].split(":")
        fp = pcbnew.FootprintLoad(fp_lib(lib), name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetValue(p["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + sh.uuids[p["ref"]]))
        fp.SetSheetname("/")
        fp.SetSheetfile(NAME + ".kicad_sch")
        for k in ("LCSC", "MPN"):
            if p.get(k.lower()):
                fp.SetField(k, p[k.lower()])
                fp.GetField(k).SetVisible(False)
        models = list(fp.Models())           # copies: change them, then put them back
        for m in models:
            if name in STANDIN and not os.path.exists(re.sub(r"\$\{KICAD\d+_3DMODEL_DIR\}", KI3D, m.m_Filename)):
                m.m_Filename = STANDIN[name]
        fp.Models().clear()
        for m in models:
            fp.Models().append(m)
        if p.get("dnp"):
            fp.SetDNP(True)
            fp.SetExcludedFromBOM(not p.get("bom", True))      # as its symbol, else KiCad's parity check flags it
            fp.Models().clear()            # J3: holes only, no header in the picture, no outline, no courtyard
            for it in [i for i in fp.GraphicalItems() if i.GetLayer() in (pcbnew.F_SilkS, pcbnew.F_CrtYd)]:
                fp.Remove(it)
        x, y, rot = AT[p["ref"]]
        place(fp, p["ref"], x, y, rot)
        if p["ref"] == "J1":           # the plug's face, past the board's edge: no silkscreen off the board
            for it in [i for i in fp.GraphicalItems() if i.GetLayer() == pcbnew.F_SilkS
                       and pcbnew.ToMM(i.GetBoundingBox().GetRight()) > OX + W]:
                fp.Remove(it)
        for pad in fp.Pads():
            n = pad_net.get((p["ref"], pad.GetNumber()))
            if n:
                pad.SetNet(b.FindNet(n))
            if (p["ref"], pad.GetNumber()) in SOLID:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    place(pcbnew.FootprintLoad(fp_lib("pqrp"), "LCD_1.14in_240x135_on_tape"), "LCD1", XC, YC, 0)
    logo = pcbnew.FootprintLoad(MARK, "PicoQuorum_Mark")
    logo.SetFPID(pcbnew.LIB_ID("picoquorum", "PicoQuorum_Mark"))
    place(logo, "LOGO1", 24.0, 13.0, 0)
    logo.Flip(logo.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

    def seg(a, c):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(*a)); s.SetEnd(mm(*c)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.05))
        b.Add(s)

    def arc(a, m, c):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(mm(*a), mm(*m), mm(*c)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.05))
        b.Add(s)
    r, k = CORNER, CORNER * (1 - 0.5 ** 0.5)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))

    # --- copper: ground pours on both sides; round U1, Raspberry Pi's copper as it is, locked, with LINKS
    u0, v0 = AT["U1"][0], AT["U1"][1]
    at = lambda q: mm(u0 + q[0], v0 + q[1])

    def track(net, layer, a, c, w):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(at(a)); t.SetEnd(at(c)); t.SetLayer(b.GetLayerID(layer)); t.SetWidth(pcbnew.FromMM(w))
        t.SetNet(b.FindNet(net)); t.SetLocked(True)
        b.Add(t)

    def zone(pts, layers, net=None, prio=0, clear=0.2, min_w=0.2, solid=False, thermal=(0.3, 0.3), rule=None):
        z = pcbnew.ZONE(b)
        ls = pcbnew.LSET()
        for name in layers:
            ls.AddLayer(b.GetLayerID(name))
        z.SetLayerSet(ls)
        if rule:
            z.SetIsRuleArea(True); z.SetZoneName(rule)
            z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
            z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False); z.SetDoNotAllowZoneFills(False)
        else:
            z.SetNet(b.FindNet(net)); z.SetAssignedPriority(prio)
            z.SetLocalClearance(pcbnew.FromMM(clear)); z.SetMinThickness(pcbnew.FromMM(min_w))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else pcbnew.ZONE_CONNECTION_THERMAL)
            z.SetThermalReliefGap(pcbnew.FromMM(thermal[0])); z.SetThermalReliefSpokeWidth(pcbnew.FromMM(thermal[1]))
        o = z.Outline()
        o.NewOutline()
        for q in pts:
            o.Append(at(q))
        b.Add(z)
        return z

    edge = [(-u0, -v0), (W - u0, -v0), (W - u0, H - v0), (-u0, H - v0)]
    for layer in ("F.Cu", "B.Cu"):
        z = zone(edge, (layer,), GND)
        if layer == "F.Cu":         # not in the regulator's corner, where it left scraps between their pours
            corner = pcbnew.SHAPE_POLY_SET()
            corner.NewOutline()
            for q in RPI_AREAS[0][3]:
                corner.Append(at(q))
            z.Outline().BooleanSubtract(corner)
    # their track ends and LINKS' 0.001 mm off their vias' centres (as rpi_minimal.json rounds them) go on the centres
    centres = [q for q in (VIA_MOVE.get(tuple(v["at"]), v["at"]) for v in RPI["vias"]) if q]
    snap = lambda e: next((c for c in centres if math.dist(c, e) < 0.005), e)
    for t in RPI["tracks"]:
        if (tuple(t["a"]), tuple(t["b"])) not in DROP:
            track(t["net"], t["layer"], snap(t["a"]), snap(t["b"]), t["w"])
    for v in RPI["vias"]:
        q = VIA_MOVE.get(tuple(v["at"]), v["at"])
        if q is None:
            continue
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(at(q)); via.SetWidth(pcbnew.FromMM(v["dia"])); via.SetDrill(pcbnew.FromMM(v["drill"]))
        via.SetNet(b.FindNet(v["net"])); via.SetLocked(True)
        b.Add(via)
    for z in RPI["zones"]:
        zone(z["pts"], (z["layer"],), z["net"], z["priority"], z["clearance"], z["min_width"], z["solid"], z["thermal"])
    for net, pts in LINKS:
        for a, c in zip(pts, pts[1:]):
            track(net, "F.Cu", snap(a), snap(c), 0.15)
    for net, pts in FLASH + BENCH + BUS + TIES + SWD:
        for a, c in zip(pts, pts[1:]):
            track(net, "F.Cu", (a[0] - u0, a[1] - v0), (c[0] - u0, c[1] - v0), 0.15)
    for net, pts in SPINE:
        for a, c in zip(pts, pts[1:]):
            track(net, "F.Cu", (a[0] - u0, a[1] - v0), (c[0] - u0, c[1] - v0), 0.2)
    for net, q, locked in HAND_VIAS:
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(at((q[0] - u0, q[1] - v0))); via.SetWidth(pcbnew.FromMM(0.6)); via.SetDrill(pcbnew.FromMM(0.3))
        via.SetNet(b.FindNet(net)); via.SetLocked(locked)
        b.Add(via)
    zone(UNDER_U1, ("B.Cu",), rule="U1: no tracks under it")
    zone(UNDER_Y1, ("B.Cu",), rule="Y1: no tracks under it")
    for h in ("H1", "H2", "H3", "H4"):              # the screws' washers: the pours may run under, behind the mask
        x, y, _ = AT[h]
        zone([(x - u0 + HOLE_RING * math.cos(k * math.pi / 16), y - v0 + HOLE_RING * math.sin(k * math.pi / 16)) for k in range(32)],
             ("F.Cu", "B.Cu"), rule=f"{h}: no tracks")
    b.GetDesignSettings().SetAuxOrigin(mm(0, H))     # the fab files' origin: the bottom-left corner
    b.GetDesignSettings().SetGridOrigin(mm(0, H))
    arc((W - r, 0), (W - k, k), (W, r)); arc((W, H - r), (W - k, H - k), (W - r, H))
    arc((r, H), (k, H - k), (0, H - r)); arc((0, r), (k, k), (r, 0))

    def text(s, x, y, size, layer=pcbnew.F_SilkS, back=False, rot=0, align=0, wide=None):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s); t.SetPosition(mm(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I_MM(wide or size, size)); t.SetTextThickness(pcbnew.FromMM(max(0.15, size * 0.15)))
        t.SetTextAngleDegrees(rot)
        if align:
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if align < 0 else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
        if back:
            t.SetMirrored(True)
        b.Add(t)

    def silk_line(a, c, width=0.2):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(*a)); s.SetEnd(mm(*c)); s.SetLayer(pcbnew.F_SilkS); s.SetWidth(pcbnew.FromMM(width))
        b.Add(s)

    def silk_box(x0, y0, x1, y1):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_RECTANGLE)
        s.SetStart(mm(x0, y0)); s.SetEnd(mm(x1, y1)); s.SetLayer(pcbnew.F_SilkS); s.SetWidth(0); s.SetFilled(True)
        b.Add(s)
    # silkscreen text 1.0 mm high at least, JLCPCB's least
    for i, lab in enumerate(("D0", "D1", "D2")):
        text(lab, AT[f"SW{i + 1}"][0], H - 1.8, 1.0)
    text("RESET", AT["SW4"][0], H - 1.8, 1.0)
    text("BOOTSEL", AT["SW5"][0], H - 1.8, 1.0)
    # the top strip: a warning triangle and WARN_TEXT; the name goes between the glass and the buttons
    tx, ty, side = WARN
    tri = [(tx, ty - side * 0.866 / 2), (tx + side / 2, ty + side * 0.866 / 2), (tx - side / 2, ty + side * 0.866 / 2)]
    for a, c in zip(tri, tri[1:] + tri[:1]):
        silk_line(a, c)
    silk_line((tx, ty - side * 0.866 / 2 + 0.55), (tx, ty + side * 0.866 / 2 - 0.75))
    silk_box(tx - 0.12, ty + side * 0.866 / 2 - 0.5, tx + 0.12, ty + side * 0.866 / 2 - 0.26)
    text(WARN_TEXT, tx + side / 2 + 0.6, ty, 1.0, align=-1, wide=0.85)      # narrow, to end before U6's pads
    text("PicoQuorum console-rp", XC, (GY1 + BY - 3.3) / 2, 1.0)
    for x0, y0, x1, y1 in silk_pixels():
        silk_box(x0, y0, x1, y1)
    x3, y3, _ = AT["J3"]
    for i, lab in enumerate(("GND", "3V3", "CLK", "DIO", "D-", "D+", "SDA", "SCL")):     # J3's pins, as the schematic, upright to fit
        text(lab, x3 - 2.54 * i, y3 + 2.6, 1.0, rot=90)
    text("no radio: USB serial only", XC, 20.0, 1.0, pcbnew.B_SilkS, back=True)
    text("console-rp rev A " + DATE, 50.0, 22.0, 1.0, pcbnew.B_SilkS, back=True)
    text("picoquorum.dev", 50.0, 24.6, 1.4, pcbnew.B_SilkS, back=True)           # also the Source Location
    text("CERN-OHL-W v2, Source Location as 4.1", 50.0, 26.8, 1.0, pcbnew.B_SilkS, back=True)
    text("ribbon folds under the glass into J2", (ZIF_IN + GX1) / 2 + 1.0, YC + 3.0, 0.8, pcbnew.F_Fab)
    text(ROUTE_NOTE, W / 2, H + 2.0, 1.0, pcbnew.Cmts_User)
    pcbnew.SaveBoard(os.path.join(OUT, NAME + ".kicad_pcb"), b)


def is_routed():
    """Whether the board on disk has tracks the router put there: every track this script draws is locked."""
    path = os.path.join(OUT, NAME + ".kicad_pcb")
    return os.path.exists(path) and re.search(r"\(segment\s*\n\s*\(start", open(path).read()) is not None


def check_placement(bad, routed=False):
    """KiCad's DRC. On the placed board (its pours filled for the check, not saved) unrouted nets
    and the copied copper inside the router's rule areas are expected; on the routed board, with
    schematic parity, neither is. Anything else is a problem (overlapping courtyards, copper on
    copper, parts at the edge or on a hole). Then what sits under the panel's glass."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "drc.json")
        subprocess.run([CLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", out,
                        *(["--schematic-parity"] if routed else ["--refill-zones"]),
                        os.path.join(OUT, NAME + ".kicad_pcb")], capture_output=True, env=kicad_env(tmp))
        rep = json.load(open(out))
    seen = {}
    ok = ("lib_footprint_issues", "lib_footprint_mismatch", "silk_over_copper", "silk_overlap",
          "silk_edge_clearance", "text_height", "text_thickness") + (() if routed else ("unconnected_items", "via_dangling", "track_dangling"))
    for v in rep.get("violations", []) + rep.get("unconnected_items", []) + rep.get("schematic_parity", []):
        seen[v["type"]] = seen.get(v["type"], 0) + 1
        if v["type"] not in ok:
            bad.append(f"DRC {v['type']}: " + "; ".join(i.get("description", "") for i in v.get("items", [])))
    # the glass: everything under it lower than the tape, nothing in the foam's corners
    for p in PARTS:
        x, y, _ = AT[p["ref"]]
        if GX0 <= x <= GX1 and GY0 <= y <= GY1:
            h = next((v for k, v in UNDER.items() if k in p["fp"]), None)
            if h is None or h > PANEL["foam"] - 0.3:
                bad.append(f"{p['ref']} ({p['fp']}) is under the glass, and isn't known to be under {PANEL['foam'] - 0.3} mm")
            gx, gy = x - GX0, y - GY0
            if (gx < PANEL["pad"] or gx > PANEL["glass"][0] - PANEL["pad"]) and (gy < PANEL["pad"] or gy > PANEL["glass"][1] - PANEL["pad"]):
                bad.append(f"{p['ref']} is under a foam pad")
    return seen


def check_rpi(bad):
    """On the routed board: no other net's track or via in Raspberry Pi's areas (RPI_AREAS)."""
    import pcbnew
    b = pcbnew.LoadBoard(os.path.join(OUT, NAME + ".kicad_pcb"))
    u = b.FindFootprintByReference("U1").GetPosition()
    for name, layer, nets, pts in RPI_AREAS:
        poly = pcbnew.SHAPE_POLY_SET()
        poly.NewOutline()
        for x, y in pts:
            poly.Append(u.x + pcbnew.FromMM(x), u.y + pcbnew.FromMM(y))
        lid = b.GetLayerID(layer)
        for t in b.GetTracks():
            if t.GetNetname() not in nets and t.IsOnLayer(lid) and poly.Collide(t.GetEffectiveShape(lid)):
                bad.append(f"{t.GetNetname()} {'via' if t.Type() == pcbnew.PCB_VIA_T else 'track'} in Raspberry Pi's area {name} ({layer})")


RENDERS = [  # name, kicad-cli pcb render options
    ("top", ["--side", "top", "--zoom", "1.6", "--width", "1600", "--height", "820"]),
    ("3q", ["--side", "top", "--rotate", "-38,0,-24", "--perspective", "--zoom", "1.45", "--width", "1600", "--height", "900"]),
    ("bottom", ["--side", "bottom", "--zoom", "1.6", "--width", "1600", "--height", "820"]),
    ("under-glass", ["--side", "top", "--zoom", "1.6", "--width", "1600", "--height", "820"]),
]


def render():
    """KiCad's own 3D view (raytraced) into renders/, as JPEGs (macOS's sips)."""
    import pcbnew
    os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        bare = os.path.join(OUT, f"_{NAME}-under-glass.kicad_pcb")      # the panel lifted off: the dragon
        brd = pcbnew.LoadBoard(os.path.join(OUT, NAME + ".kicad_pcb"))
        brd.Remove(brd.FindFootprintByReference("LCD1"))
        pcbnew.SaveBoard(bare, brd)
        for name, opts in RENDERS:
            png = os.path.join(tmp, name + ".png")
            src = bare if name == "under-glass" else os.path.join(OUT, NAME + ".kicad_pcb")
            subprocess.run([CLI, "pcb", "render", "--quality", "high", "--background", "opaque", "--floor",
                            *opts, "-o", png, src], check=True, capture_output=True, env=kicad_env(tmp))
            jpg = os.path.join(HERE, "renders", f"{NAME}-{name}.jpg")
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", png, "--out", jpg], check=True, capture_output=True)
            print(f"  {os.path.relpath(jpg, REPO)}")
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_prl"):
            if os.path.exists(bare[:-10] + ext):
                os.remove(bare[:-10] + ext)


# What `tools/keypcb jlc console-rp` needs to know that the board file doesn't say, in its frame: mm
# from the bottom-left corner, y up. Heights (mm) are datasheets' or the usual for the package.
HEIGHT = {"C_0402_1005Metric": 0.55, "R_0402_1005Metric": 0.4, "RPi_C_0402": 0.55, "RPi_C_0402_wide": 0.55, "RPi_R_0402": 0.4,
          "C_0805_2012Metric": 1.25, "LED_0603_1608Metric": 0.8, "SOT-23": 1.15, "SOT-23-3": 1.15, "SOT-23-6": 1.45,
          "RPi_L_Abracon_AOTA-B201610": 1.0, "RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias": 0.85,
          "WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm": 0.75, "SOIC-8_3.9x4.9mm_P1.27mm": 1.75, "SOIC-8_5.3x5.3mm_P1.27mm": 2.16,
          "RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm": 0.8, "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB": 1.0,
          "SW_Push_1P1T_XKB_TS-1187A": 1.5, "USB_C_Receptacle_HRO_TYPE-C-31-M-12": 3.2}


def jlc_spec():
    """The board's numbers for tools/jlc: the holes' rings, the regulator's heat, the nets whose
    return path to report, and the 3D fit of the panel."""
    up = lambda y: round(H - y, 4)
    rib = PANEL["ribbon"] / 2
    fx, fy = AT["U6"][:2]            # the flash, under the glass's edge: its body and leads, not its courtyard
    return {
        "edge": 0.3,
        "hole_ring": HOLE_RING,
        "via_in_pad": [{"pad": "U4.17", "why": "the CH343P's exposed pad and pin 2, shut in by its other pins, have no other way to ground: one via in the exposed pad"}],
        "thermal_vias": [{"pad": "U1.61", "why": "Raspberry Pi's nine 0.3 mm holes in the RP2350's exposed pad, 0.6 mm across like our vias"}],
        "jlc_allow": [{"type": "footprint_filters_mismatch", "ref": p["ref"], "why": "Raspberry Pi's footprint, or console-s3's ZIF: not a name the stock symbol's filters list"}
                      for p in PARTS if p["fp"].startswith("pqrp:")]
                     + [{"type": "footprint_type_mismatch", "ref": "U1", "why": "Raspberry Pi's footprint: an SMD part with plated holes in its exposed pad"},
                        {"type": "lib_footprint_mismatch", "ref": "J1", "why": "its silkscreen past the board's edge left out"},
                        {"type": "lib_footprint_mismatch", "ref": "J3", "why": "not fitted: its outline and courtyard left out, the holes only"},
                        {"type": "missing_courtyard", "ref": "J3", "why": "not fitted: the holes only"},
                        {"type": "missing_courtyard", "ref": "LCD1", "why": "the panel on tape over the parts: the fit check's glass stands in"},
                        {"type": "silk_over_copper", "ref": "LCD1", "why": "the glass's outline crosses U6's pads, and KiCad cuts it at their openings"}],
        "regulator": {"ref": "U3", "part": "XC6206P332MR", "vin": 5.0, "vout": 3.3, "amps": [0.05, 0.12], "theta_ja": 400,
                      "theta_note": "250 mW at 25 C in its datasheet's SOT-23 rating, so about 400 C/W"},
        "return_nets": ["/USB_D+", "/USB_D-", "/RP_DP", "/RP_DM", "/LCD_SCK", "/LCD_MOSI", "/QSPI_SCLK", "/XIN"],
        "fit": {
            "heights": HEIGHT, "default_height": 1.0,
            "solids": [{"name": "glass", "box": [GX0, up(GY1), GX1, up(GY0)], "z": [PANEL["foam"], PANEL["foam"] + PANEL["thick"]],
                        "note": f"on {PANEL['foam']} mm foam, {PANEL['thick']} thick: one seller's numbers, not measured"},
                       {"name": "U6 body", "box": [fx - 2.69, up(fy + 2.665), fx + 2.69, up(fy - 2.665)], "z": [0.0, 2.16],
                        "note": "Winbond's 208-mil SOIC-8: 5.38 x 5.33 at most, 2.16 tall (datasheet)"},
                       *({"name": f"U6 leads {side}", "box": box, "z": [0.0, 1.3], "guess": True,
                          "note": "8.10 across the leads at most (datasheet); how high they leave the body is a guess"}
                         for side, box in (("left", [fx - 4.05, up(fy + 2.665), fx - 2.69, up(fy - 2.665)]),
                                           ("right", [fx + 2.69, up(fy + 2.665), fx + 4.05, up(fy - 2.665)])))],
            "ribbon_run": [AT["J2"][0], up(YC + rib), GX1, up(YC - rib)],
        },
    }


def main():
    bad = []
    check_firmware(bad)
    checking = "check" in sys.argv[1:]
    if not checking:
        if is_routed():
            sys.exit(f"{NAME}: {NAME}.kicad_pcb is routed, and a new schematic wouldn't match it. "
                     f"`tools/keypcb gen-console-rp check` checks it; delete it to place the board again")
        sh = write_schematic()
        write_project(sh.root)
        write_footprints()
        write_models()
        write_bom()
        write_pins()
        print(f"wrote {os.path.relpath(OUT, REPO)}/{NAME}.kicad_sch, .kicad_pro, fab/bom.csv, PINS.md")
    nets = netlist()
    check_netlist(bad, nets)
    check_link(bad, nets)
    found = check_erc(bad)
    check_footprints(bad)
    if not checking:
        write_board(sh, nets)
        write_project(sh.root)       # after SaveBoard, so the project is ours
    drc = check_placement(bad, routed=checking)
    if checking:
        check_rpi(bad)
    print(f"  the board: {NAME}.kicad_pcb, {W:g} x {H:g} mm, {'routed' if checking else 'placed, not routed'}; DRC: "
          + (", ".join(f"{k} {v}" for k, v in sorted(drc.items())) or "nothing"))
    if "render" in sys.argv[1:] and not bad:
        render()
    n_parts = sum(1 for p in PARTS if p.get("bom", True))
    if bad:
        sys.exit(NAME + ": " + str(len(bad)) + " problems\n  " + "\n  ".join(bad))
    print(f"  {len(PARTS)} parts ({n_parts} placed by JLCPCB), {len([n for n in nets if not n.startswith('unconnected-')])} nets, "
          f"ERC: {len(found)} findings")
    print("  KiCad's netlist matches the table; the link's wiring, the footprints, the GPIO functions and the Pico pins check out")


if __name__ == "__main__":
    main()
