#!/usr/bin/env python3
"""Tally: a second take on Mono's idea, drawn from scratch. A 40 x 89.5 mm bar with no radio: the
1.14" screen at the top, three buttons under it, an RP2350A and its flash, the ATECC608C soldered
on, and a USB-C on the bottom end whose only data path is a CH343P serial bridge to the RP2350's
UART1. The chip's core runs from a plain 1.1 V regulator, so the board has no inductor. Tally is a
working name. See README.md.

    python3 gen_tally.py            writes everything below, then checks it
    python3 gen_tally.py check      checks the files as they are, writing nothing
    python3 gen_tally.py import D   once: writes lib/ afresh (D holds the two KiCad 10 footprint files)
        (written and run on KiCad 7.0.11: kicad-cli and its Python's pcbnew, nothing else)

Writes, from the one table below:
  lib/tally.kicad_sym    every symbol the schematic uses, so the project needs no stock library
  lib/tally.pretty/      every footprint the board uses, the same way
  tally/tally.kicad_sch  the schematic: each pin a stub and a name, nothing drawn wire to wire
  tally/tally.kicad_pcb  the board, placed and routed: Raspberry Pi's copper round the chip
                         (rpi_minimal.json), and every other track drawn here, in wire()
  tally/tally.kicad_pro  the project, with the rules the other boards here use
  tally/fab/             the Gerber and drill zip, bom.csv and cpl.csv in JLCPCB's format
  PINS.md                the RP2350's pins, as the firmware sees them

Then it has KiCad read the schematic back and checks every connection against the table, every
symbol pin against its footprint's pads, each GPIO against the RP2350's function table, the screen's
and key's pins against firmware/board.py, and the link's wiring rules; checks the board against that netlist; and runs KiCad's DRC on the board. It
prints each difference and exits 1.
"""
import csv, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
NAME = "tally"
OUT = os.path.join(HERE, NAME)
LIB = os.path.join(HERE, "lib")
PRETTY = os.path.join(LIB, NAME + ".pretty")
SHARE = "/Applications/KiCad/KiCad.app/Contents/SharedSupport" if os.path.isdir("/Applications/KiCad/KiCad.app") else "/usr/share/kicad"
KISYM, KIFP = os.path.join(SHARE, "symbols"), os.path.join(SHARE, "footprints")
CLI = shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
DATE, REV = "2026-11-13", "A"

GND, V33, V11, VBUS = "GND", "+3V3", "+1V1", "VBUS"
POWER = (GND, V33, V11, VBUS)

# Which chip sits at U1. One board takes either; an RP2354A and a flash at U7 must never both be fitted.
#   "RP2350A": the RP2350A and a W25Q128 at U7. Runs the stock MicroPython image for the Pico 2, as console-rp does.
#   "RP2354A": the RP2354A, its 2 MB flash inside, U7 and C23 left off. Needs a MicroPython built for 2 MB.
BUILD = "RP2350A"
CHIP = {"RP2350A": dict(value="RP2350A", lcsc="C42411118", mpn="RP2350A"),
        "RP2354A": dict(value="RP2354A", lcsc="C41378174", mpn="RP2354A")}[BUILD]
FLASH = dict(lcsc="C97521", mpn="W25Q128JVSIQ") if BUILD == "RP2350A" else dict(bom=False)

# =================================================================================================
# The one table: every part, its LCSC number and what each of its pins connects to. A pin not listed
# is not connected, on purpose, and gets a no-connect flag. Nets other than the four power nets are
# local labels, which KiCad names "/<net>".
# =================================================================================================
C0402, R0402 = "C_0402_1005Metric", "R_0402_1005Metric"
RC0402, RR0402 = "RPi_C_0402", "RPi_R_0402"        # Raspberry Pi's own, for the parts round the chip at their places
C100N = dict(value="100n", fp=C0402, lcsc="C1525", mpn="CL05B104KO5NNNC")
C1U = dict(value="1u", fp=C0402, lcsc="C52923", mpn="CL05A105KA5NQNC")
C4U7 = dict(value="4.7u", fp=C0402, lcsc="C23733", mpn="CL05A475MP5NRNC")
C10U = dict(value="10u", fp="C_0805_2012Metric", lcsc="C15850", mpn="CL21A106KAYNNNE")
C15P = dict(value="15p", fp=C0402, lcsc="C1548", mpn="0402CG150J500NT")
R1K = dict(value="1k", fp=R0402, lcsc="C11702", mpn="0402WGF1001TCE")
R4K7 = dict(value="4.7k", fp=R0402, lcsc="C25900", mpn="0402WGF4701TCE")
R5K1 = dict(value="5.1k", fp=R0402, lcsc="C25905", mpn="0402WGF5101TCE")
R150 = dict(value="150R", fp="R_0603_1608Metric", lcsc="C22808", mpn="0603WAF1500T5E")


def cap(ref, a, b, spec, why="", **kw):
    return dict(ref=ref, sym="C", nets={"1": a, "2": b}, why=why, **{**spec, **kw})


def res(ref, a, b, spec, why="", **kw):
    return dict(ref=ref, sym="R", nets={"1": a, "2": b}, why=why, **{**spec, **kw})


def tp(ref, net, why):
    return dict(ref=ref, sym="TestPoint", value=net, fp="TestPoint_Pad_D1.5mm", nets={"1": net}, why=why, bom=False)


# net -> the RP2350's GPIO. console-rp's and Mono's numbers, so one firmware profile serves all three.
GPIO = {"BTN_D0": 2, "BTN_D1": 3, "SDA": 4, "SCL": 5, "BTN_D2": 6,
        "LCD_DC": 8, "LCD_CS": 9, "LCD_SCK": 10, "LCD_MOSI": 11, "LCD_RST": 12, "LCD_BL": 13,
        "LINK_TX": 20, "LINK_RX": 21, "LED": 25}
# the QFN-60's pin for each GPIO (RP2350 datasheet, figure 2)
PIN_GPIO = {**{2 + g: g for g in range(4)}, **{7 + (g - 4): g for g in range(4, 8)}, **{12 + (g - 8): g for g in range(8, 12)},
            **{16 + (g - 12): g for g in range(12, 16)}, **{27 + (g - 16): g for g in range(16, 19)},
            **{31 + (g - 19): g for g in range(19, 26)}, **{40 + (g - 26): g for g in range(26, 30)}}
GPIO_PIN = {g: p for p, g in PIN_GPIO.items()}
U1_NETS = {**{str(p): V33 for p in (1, 11, 20, 30, 38, 45)},          # IOVDD
           **{str(p): V11 for p in (6, 23, 39)},                      # DVDD, from U4
           "44": V33, "53": V33, "54": V33,                           # ADC_AVDD, USB_OTP_VDD, QSPI_IOVDD
           # the core regulator, not used (datasheet 6.3.7, figure 24): its two supplies still on 3.3 V
           # for the power-on reset and brown-out blocks, FB to ground, LX open
           "46": V33, "49": V33, "47": GND, "50": GND,
           "21": "XIN", "22": "XOUT", "24": "SWCLK", "25": "SWDIO", "26": "RUN",
           "55": "QSPI_SD3", "56": "QSPI_SCLK", "57": "QSPI_SD0", "58": "QSPI_SD2", "59": "QSPI_SD1", "60": "QSPI_SS",
           "61": GND,
           **{str(GPIO_PIN[g]): n for n, g in GPIO.items()}}

PARTS = [
    # --- power in: the USB-C, its ESD diodes, 5 V to 3.3 V, 3.3 V to the core's 1.1 V -------------
    dict(ref="J1", sym="USB_C_16P", value="USB-C", fp="USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948", mpn="TYPE-C-31-M-12",
         nets={**{p: GND for p in ("A1", "A12", "B1", "B12", "SH")}, **{p: VBUS for p in ("A4", "A9", "B4", "B9")},
               "A5": "CC1", "B5": "CC2", "A6": "USB_D+", "B6": "USB_D+", "A7": "USB_D-", "B7": "USB_D-"},
         why="power, and the link to the computer. SBU open. The shell to ground"),
    res("R1", "CC1", GND, R5K1, "a sink: 5.1k on each CC, so a C-to-C cable gives 5 V"),
    res("R2", "CC2", GND, R5K1),
    dict(ref="U2", sym="USBLC6-2SC6", value="USBLC6-2SC6", fp="SOT-23-6", lcsc="C7519", mpn="USBLC6-2SC6",
         nets={"1": "USB_D+", "6": "USB_D+", "3": "USB_D-", "4": "USB_D-", "5": VBUS, "2": GND},
         why="ESD on D+, D- and VBUS at the connector"),
    dict(ref="U3", sym="LDL1117S33R", value="LDL1117S33R", fp="SOT-223-3_TabPin2", lcsc="C435835", mpn="LDL1117S33R",
         nets={"3": VBUS, "2": V33, "1": GND},
         why="5 V to 3.3 V. SOT-223: about 0.1 W here. Stable on ceramics; takes 18 V in"),
    cap("C1", VBUS, GND, C4U7, "U3's input. With C5, 5.7u on VBUS, under USB's 10u"),
    cap("C2", V33, GND, C10U, "U3's output, the board's bulk"),
    dict(ref="U4", sym="TLV74311P", value="TLV74311PDBVR", fp="SOT-23-5", lcsc="C485147", mpn="TLV74311PDBVR",
         nets={"1": V33, "3": V33, "2": GND, "5": V11},
         why="3.3 V to the RP2350's core, 1.1 V. In place of the chip's own switching regulator: no inductor"),
    cap("C3", V33, GND, C1U, "U4's input"),
    cap("C4", V11, GND, C4U7, "U4's output"),
    # --- the link: USB to UART1 and nothing else --------------------------------------------------
    dict(ref="U5", sym="CH343P", value="CH343P", fp="WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm", lcsc="C2846043", mpn="CH343P",
         nets={"1": V33, "2": GND, "17": GND, "3": VBUS, "9": VBUS, "6": "CH_V3", "7": "USB_D+", "8": "USB_D-",
               "4": "LINK_RX", "5": "LINK_TX"},
         why="USB to serial, a CDC-ACM device. DTR, RTS and the modem pins open: the computer can't reset the RP2350 or hold BOOT"),
    cap("C5", VBUS, GND, C1U, "CH343P VDD5"),
    cap("C6", "CH_V3", GND, C100N, "CH343P V3, its own 3.3 V"),
    cap("C7", V33, GND, C100N, "CH343P VIO: its UART pins at the RP2350's 3.3 V"),
    # --- the RP2350A and what it needs ------------------------------------------------------------
    dict(ref="U1", sym="RP2350A", fp="RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias", **CHIP,
         nets=U1_NETS, why="no radio on the chip. The RP2354A is the same chip with 2 MB of flash in the package (BUILD)"),
    cap("C10", V33, GND, C100N, "IOVDD pin 1", fp=RC0402),
    cap("C11", V33, GND, C100N, "IOVDD pin 11", fp=RC0402),
    cap("C12", V33, GND, C100N, "IOVDD pin 20", fp=RC0402),
    cap("C13", V33, GND, C100N, "IOVDD pin 30", fp=RC0402),
    cap("C14", V33, GND, C100N, "IOVDD pin 38", fp=RC0402),
    cap("C15", V33, GND, C100N, "ADC_AVDD pin 44 and IOVDD pin 45", fp=RC0402),
    cap("C16", V11, GND, C100N, "DVDD pin 6", fp=RC0402),
    cap("C17", V11, GND, C100N, "DVDD pin 39", fp=RC0402),
    cap("C18", V11, GND, C4U7, "DVDD pin 23, the one furthest from U4", fp=RC0402),
    cap("C19", V33, GND, C100N, "USB_OTP_VDD pin 53 and QSPI_IOVDD pin 54", fp=RC0402),
    cap("C20", V33, GND, C4U7, "VREG_VIN pin 49 and VREG_AVDD pin 46: the one capacitor figure 24 asks for", fp="RPi_C_0402_wide"),
    dict(ref="Y1", sym="Crystal_GND24", value="12MHz", fp="RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm", lcsc="C9002", mpn="X322512MSB4SI",
         nets={"1": "XIN", "3": "XTAL_OUT", "2": GND, "4": GND}, why="12 MHz, 3.2 x 2.5 mm"),
    cap("C21", "XIN", GND, C15P, "the crystal's load, Raspberry Pi's value", fp=RC0402),
    cap("C22", "XTAL_OUT", GND, C15P, fp=RC0402),
    res("R3", "XOUT", "XTAL_OUT", R1K, "keeps the crystal from being over-driven", fp=RR0402),
    dict(ref="U7", sym="W25Q", value="W25Q128JVSIQ", fp="SOIC-8_5.3x5.3mm_P1.27mm", **FLASH,
         nets={"1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": GND, "5": "QSPI_SD0", "6": "QSPI_SCLK", "7": "QSPI_SD3", "8": V33},
         why="the flash, for the RP2350A build: 16 MB, Basic at JLCPCB. Not fitted beside an RP2354A"),
    cap("C23", V33, GND, C100N if BUILD == "RP2350A" else dict(value="100n", fp=C0402), "the flash's", **({} if BUILD == "RP2350A" else dict(bom=False))),
    # --- the key that signs -----------------------------------------------------------------------
    dict(ref="U6", sym="ATECC608", value="ATECC608C-SSHDA-T", fp="SOIC-8_3.9x4.9mm_P1.27mm", lcsc="C28975195", mpn="ATECC608C-SSHDA-T",
         nets={"8": V33, "4": GND, "5": "SDA", "6": "SCL"}, why="the key: I2C0, address 0x60"),
    cap("C24", V33, GND, C100N, "the key's"),
    res("R7", "SDA", V33, R4K7, "I2C pull-ups"),
    res("R8", "SCL", V33, R4K7),
    # --- the screen -------------------------------------------------------------------------------
    dict(ref="J2", sym="PANEL_ZIF8", value="PANEL", fp="FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB", lcsc="C2919492", mpn="0.5K-HX-8PWB",
         nets={"1": "LCD_LEDA", "2": GND, "3": "LCD_RST", "4": "LCD_DC", "5": "LCD_MOSI", "6": "LCD_SCK", "7": V33, "8": "LCD_CS"},
         why="the 1.14\" 240 x 135 ST7789 panel's ribbon. console-rp's pin order, which its board 1 shows a picture with"),
    cap("C25", V33, GND, C1U, "the panel's VDD"),
    cap("C26", V33, GND, C100N),
    dict(ref="Q1", sym="Q_PMOS_GSD", value="AO3401A", fp="SOT-23", lcsc="C15127", mpn="AO3401A",
         nets={"1": "BL_GATE", "2": VBUS, "3": "BL_SW"}, why="the backlight's switch, from 5 V: the panel's LED cathode is grounded inside"),
    dict(ref="Q2", sym="Q_NMOS_GSD", value="AO3400A", fp="SOT-23", lcsc="C20917", mpn="AO3400A",
         nets={"1": "LCD_BL", "2": GND, "3": "BL_GATE"}, why="GPIO13 high pulls Q1's gate low: the backlight on"),
    res("R9", "BL_GATE", VBUS, R4K7, "Q1 off unless Q2 pulls"),
    res("R10", "LCD_BL", GND, R4K7, "off until the firmware turns it on; under the 8.2k RP2350-E9 asks for on an A2 chip"),
    res("R11", "BL_SW", "LCD_LEDA", R150, "about 13 mA from 5 V; the panel's limit is 20"),
    # --- buttons and the LED ----------------------------------------------------------------------
    # each switch's pad pair on the side its line arrives from carries the signal, the other pair is ground
    *[dict(ref=f"SW{i + 1}", sym="SW_Push", value=f"D{i}", fp="SW_Push_1P1T_XKB_TS-1187A", lcsc="C318884", mpn="TS-1187A-B-A-B",
           nets={sig: f"BTN_D{i}", gnd: GND}, why="to ground; pulled up inside the chip") for i, (sig, gnd) in enumerate((("2", "1"), ("2", "1"), ("1", "2")))],
    dict(ref="D1", sym="LED", value="RED", fp="LED_0603_1608Metric", lcsc="C2286", mpn="KT-0603R",
         nets={"2": "LED", "1": "LED_K"}, why="GPIO25 high lights it"),
    res("R12", "LED_K", GND, R1K),
    # --- the way in for firmware: nothing here is reached through the USB-C ------------------------
    dict(ref="J3", sym="DEBUG_3P", value="SWD", fp="JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal", lcsc="C160403", mpn="SM03B-SRSS-TB(LF)(SN)",
         nets={"1": "SWCLK", "2": GND, "3": "SWDIO", "SH": GND}, why="Raspberry Pi's 3-pin debug connector: a Debug Probe's cable plugs in"),
    tp("TP1", "SWCLK", "the jig's pads, on the back, at Mono's places"), tp("TP2", GND, ""), tp("TP3", "SWDIO", ""),
    tp("TP4", "RUN", "low resets the chip"), tp("TP5", V33, "to measure"), tp("TP9", GND, ""),
    tp("TP10", V11, "the core's supply, to measure"), tp("TP11", VBUS, "to measure"),
    tp("TP12", "LINK_TX", "the link, to watch"), tp("TP13", "LINK_RX", ""),
    # --- mechanical -------------------------------------------------------------------------------
    *[dict(ref=f"H{i}", sym="MountingHole", value="M2", fp="MountingHole_2.2mm_M2", nets={}, why="", bom=False) for i in range(1, 5)],
    *[dict(ref=f"FID{i}", sym="Fiducial", value="Fiducial", fp="Fiducial_1mm_Mask2mm", nets={}, why="", bom=False) for i in range(1, 4)],
]
BY_REF = {p["ref"]: p for p in PARTS}
FLAGS = (VBUS, GND)                       # nets no symbol drives: each gets a PWR_FLAG

# What each GPIO's function must be able to be (RP2350 datasheet, table 3: UART1 TX on 4, 8, 12, 20,
# 24, 28 and RX one up; I2C0 SDA on 0, 4, 8, ... and SCL one up; SPI1 SCK on 10, 14, 26 and TX one up)
NEEDS = {"SDA": lambda g: g % 4 == 0, "SCL": lambda g: g % 4 == 1,
         "LCD_SCK": lambda g: g in (10, 14, 26), "LCD_MOSI": lambda g: g in (11, 15, 27),
         "LINK_TX": lambda g: g in (4, 8, 12, 20, 24, 28), "LINK_RX": lambda g: g in (5, 9, 13, 21, 25, 29)}

# =================================================================================================
# S-expressions, KiCad's file format: a small reader and writer
# =================================================================================================
class Sym(str):
    """A bare word, not a quoted string."""


_NUM = re.compile(r"^-?\d+(\.\d+)?([eE]-?\d+)?$")
_TOK = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


def parse(text):
    stack, cur, pos, root = [], None, 0, None
    while pos < len(text):
        m = _TOK.match(text, pos)
        if not m:
            if not text[pos:].strip():
                break
            raise ValueError("bad s-expression at %d: %r" % (pos, text[pos:pos + 40]))
        pos = m.end()
        if m.group(1):
            new = []
            if cur is not None:
                cur.append(new)
                stack.append(cur)
            cur = new
        elif m.group(2):
            if stack:
                cur = stack.pop()
            else:
                root, cur = cur, None
        elif m.group(3) is not None:
            cur.append(m.group(3).replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\"))
        else:
            w = m.group(4)
            cur.append((float(w) if re.search(r"[.eE]", w) else int(w)) if _NUM.match(w) else Sym(w))
    return root


def dump(node, indent=0, width=118):
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, str):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(node, float):
        s = ("%.6f" % node).rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    if isinstance(node, int):
        return str(node)
    flat = "(" + " ".join(dump(c, 0, 10 ** 9) for c in node) + ")"
    if len(flat) + indent <= width or not any(isinstance(c, list) for c in node):
        return flat
    k = next(i for i, c in enumerate(node) if isinstance(c, list))      # the head stays on the first line; order is kept
    out = "(" + " ".join(dump(c) for c in node[:k])
    for c in node[k:]:
        out += "\n" + " " * (indent + 2) + dump(c, indent + 2, width)
    return out + "\n" + " " * indent + ")"


def find(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def first(node, name):
    for c in node:
        if isinstance(c, list) and c and c[0] == name:
            return c
    return None


def S(*words):
    """S("at", 1, 2) -> [Sym("at"), 1, 2]: the head a bare word, strings stay strings."""
    return [Sym(words[0]), *words[1:]]


def uid(*key):
    """The same uuid for the same key every run, so the files don't change when nothing has."""
    return str(uuid.UUID(hashlib.sha256(("tally/" + "/".join(map(str, key))).encode()).hexdigest()[:32]))


# =================================================================================================
# Symbols: stock ones copied out of KiCad's libraries, and plain boxes for the rest. All of them go
# into lib/tally.kicad_sym, so the project names no library but its own.
# =================================================================================================
_stock = {}


def stock(lib, name):
    """A stock symbol with "extends" resolved, as a list ready to rename."""
    if lib not in _stock:
        _stock[lib] = {s[1]: s for s in find(parse(open(os.path.join(KISYM, lib + ".kicad_sym")).read()), "symbol")}
    s = _stock[lib][name]
    ext = first(s, "extends")
    if not ext:
        return s
    base = _stock[lib][ext[1]]
    props = {p[1]: p for p in find(base, "property")}
    props.update({p[1]: p for p in find(s, "property")})
    out = [Sym("symbol"), name] + [c for c in base[2:] if not (isinstance(c, list) and c[0] in ("property", "symbol"))]
    out += list(props.values())
    return out + [[Sym("symbol"), name + sub[1][len(ext[1]):]] + sub[2:] for sub in find(base, "symbol")]


def renamed(symdef, name):
    """The symbol under a new name, without its footprint filters (ours are our own footprints)."""
    old = symdef[1]
    out = [Sym("symbol"), name]
    for c in symdef[2:]:
        if isinstance(c, list) and c[0] == "property" and c[1] == "ki_fp_filters":
            continue
        if isinstance(c, list) and c[0] == "symbol":
            c = [Sym("symbol"), name + c[1][len(old):]] + c[2:]
        out.append(c)
    return out


def font(hide=False, just=None, size=1.27):
    e = S("effects", S("font", S("size", size, size)))
    if just:
        e.append([Sym("justify")] + [Sym(j) for j in just.split()])
    if hide:
        e.append(Sym("hide"))
    return e


def box(name, ref, left=(), right=(), top=(), bottom=(), descr=""):
    """A plain box. Each side lists (number, name, type), or None for a gap, in order."""
    n = max(len(left), len(right), 1)
    w = math.ceil(max(20.32, 2.54 * (max(len(top), len(bottom)) + 3)) / 5.08) * 5.08
    h = 2.54 * (n + 1)
    x0, y0 = -w / 2, h / 2
    pins = []

    def pin(p, x, y, ang):
        pins.append(S("pin", Sym(p[2]), Sym("line"), S("at", round(x, 3), round(y, 3), ang), S("length", 2.54),
                      S("name", p[1], font()), S("number", str(p[0]), font())))
    for i, p in enumerate(left):
        p and pin(p, x0 - 2.54, y0 - 2.54 * (i + 1), 0)
    for i, p in enumerate(right):
        p and pin(p, -x0 + 2.54, y0 - 2.54 * (i + 1), 180)
    for i, p in enumerate(top):
        p and pin(p, x0 + 2.54 * (i + 2), y0 + 2.54, 270)
    for i, p in enumerate(bottom):
        p and pin(p, x0 + 2.54 * (i + 2), -y0 - 2.54, 90)
    return [Sym("symbol"), name, S("pin_names", S("offset", 1.016)), S("in_bom", Sym("yes")), S("on_board", Sym("yes")),
            S("property", "Reference", ref, S("at", round(x0, 3), round(y0 + 1.27, 3), 0), font(just="left bottom")),
            S("property", "Value", name, S("at", round(x0, 3), round(-y0 - 1.27, 3), 0), font(just="left top")),
            S("property", "Footprint", "", S("at", 0, 0, 0), font(hide=True)),
            S("property", "Datasheet", "", S("at", 0, 0, 0), font(hide=True)),
            S("property", "ki_description", descr, S("at", 0, 0, 0), font(hide=True)),
            [Sym("symbol"), name + "_0_1", S("rectangle", S("start", round(x0, 3), round(y0, 3)), S("end", round(-x0, 3), round(-y0, 3)),
                                             S("stroke", S("width", 0.254), S("type", Sym("default"))), S("fill", S("type", Sym("background"))))],
            [Sym("symbol"), name + "_1_1"] + pins]


def _u1_symbol():
    g = lambda n: (GPIO_PIN[n], "GPIO%d" % n, "bidirectional")
    left = [g(n) for n in range(0, 16)] + [None, (21, "XIN", "input"), (22, "XOUT", "passive"), None,
                                           (24, "SWCLK", "input"), (25, "SWDIO", "bidirectional"), (26, "RUN", "input")]
    right = [g(n) for n in range(16, 30)] + [None, (52, "USB_DP", "bidirectional"), (51, "USB_DM", "bidirectional"), None,
                                             (60, "~{QSPI_SS}", "bidirectional"), (56, "QSPI_SCLK", "bidirectional"), (57, "QSPI_SD0", "bidirectional"),
                                             (59, "QSPI_SD1", "bidirectional"), (58, "QSPI_SD2", "bidirectional"), (55, "QSPI_SD3", "bidirectional")]
    top = [(p, "IOVDD", "power_in") for p in (1, 11, 20, 30, 38, 45)] + [(54, "QSPI_IOVDD", "power_in"), (53, "USB_OTP_VDD", "power_in"),
                                                                        (44, "ADC_AVDD", "power_in"), None, (49, "VREG_VIN", "power_in"),
                                                                        (46, "VREG_AVDD", "power_in"), None, (6, "DVDD", "power_in"),
                                                                        (23, "DVDD", "power_in"), (39, "DVDD", "power_in")]
    bottom = [(61, "GND", "power_in"), (47, "VREG_PGND", "power_in"), None, (50, "VREG_FB", "passive"), (48, "VREG_LX", "passive")]
    return box("RP2350A", "U", left, right, top, bottom,
               "Raspberry Pi RP2350A, QFN-60: two Cortex-M33 or Hazard3 cores, 520 KB RAM. The RP2354A is the same with 2 MB of flash inside")


STOCK_SYMBOLS = {"R": "Device", "C": "Device", "LED": "Device", "Crystal_GND24": "Device", "Q_PMOS_GSD": "Device", "Q_NMOS_GSD": "Device",
                 "SW_Push": "Switch", "TestPoint": "Connector", "MountingHole": "Mechanical", "Fiducial": "Mechanical",
                 "GND": "power", "+3V3": "power", "+1V1": "power", "VBUS": "power", "PWR_FLAG": "power"}


def symbols(fresh=False):
    """name -> the symbol, for every symbol the table and the sheet use. The stock ones were copied out
    of KiCad's libraries once ("import") and are read back from lib/tally.kicad_sym, so a run doesn't
    depend on which KiCad's libraries this machine has."""
    P, pw, bi, inp, out, nc = "passive", "power_in", "bidirectional", "input", "output", "no_connect"
    path = os.path.join(LIB, NAME + ".kicad_sym")
    if fresh:
        s = {n: renamed(stock(lib, n), n) for n, lib in STOCK_SYMBOLS.items()}
    else:
        have = {x[1]: x for x in find(parse(open(path).read()), "symbol")}
        s = {n: have[n] for n in STOCK_SYMBOLS}
    s["RP2350A"] = _u1_symbol()
    s["USB_C_16P"] = box("USB_C_16P", "J",
                         [("A4", "VBUS", P), ("A9", "VBUS", P), ("B4", "VBUS", P), ("B9", "VBUS", P), None,
                          ("A5", "CC1", P), ("B5", "CC2", P), None, ("A6", "D+", P), ("B6", "D+", P), ("A7", "D-", P), ("B7", "D-", P), None,
                          ("A8", "SBU1", P), ("B8", "SBU2", P)],
                         [("A1", "GND", P), ("A12", "GND", P), ("B1", "GND", P), ("B12", "GND", P), None, ("SH", "SHIELD", P)],
                         descr="USB Type-C receptacle, USB 2.0, 16 pins")
    s["USBLC6-2SC6"] = box("USBLC6-2SC6", "U", [(1, "I/O1", P), (3, "I/O2", P), None, (2, "GND", P)], [(6, "I/O1", P), (4, "I/O2", P), None, (5, "VBUS", P)],
                           descr="ST USBLC6-2SC6: ESD protection for two data lines and VBUS, SOT-23-6")
    s["LDL1117S33R"] = box("LDL1117S33R", "U", [(3, "VIN", pw), None, (1, "GND", pw)], [(2, "VOUT", "power_out")],
                           descr="ST LDL1117S33R: 3.3 V, 1.2 A low-drop regulator, SOT-223, the tab is VOUT")
    s["TLV74311P"] = box("TLV74311P", "U", [(1, "IN", pw), (3, "EN", inp), None, (2, "GND", pw)], [(5, "OUT", "power_out"), None, (4, "NC", nc)],
                         descr="TI TLV74311PDBVR: 1.1 V, 300 mA low-drop regulator, SOT-23-5")
    s["CH343P"] = box("CH343P", "U",
                      [(3, "VDD5", pw), (9, "VBUS", inp), (1, "VIO", pw), (6, "V3", "power_out"), None, (7, "UD+", bi), (8, "UD-", bi), None,
                       (2, "GND", pw), (17, "EP", pw)],
                      [(4, "TXD", out), (5, "RXD", inp), None, (10, "~{ACT}", out), (11, "~{DCD}", inp), (12, "~{DTR}", out), (13, "~{RTS}", out),
                       (14, "~{DSR}", inp), (15, "~{CTS}", inp), (16, "~{RI}", inp)],
                      descr="WCH CH343P: USB to UART, CDC-ACM, QFN-16 3 x 3 mm")
    s["ATECC608"] = box("ATECC608", "U", [(8, "VCC", pw), None, (4, "GND", pw)], [(5, "SDA", bi), (6, "SCL", inp), None, (1, "NC", nc), (2, "NC", nc), (3, "NC", nc), (7, "NC", nc)],
                        descr="Microchip ATECC608C-SSHDA: P-256 secure element, I2C, SOIC-8")
    s["W25Q"] = box("W25Q", "U", [(8, "VCC", pw), None, (4, "GND", pw)],
                    [(1, "~{CS}", inp), (6, "CLK", inp), (5, "DI/IO0", bi), (2, "DO/IO1", bi), (3, "~{WP}/IO2", bi), (7, "~{HOLD}/IO3", bi)],
                    descr="Winbond W25QxxJV quad-SPI flash, SOIC-8 208 mil")
    s["PANEL_ZIF8"] = box("PANEL_ZIF8", "J", [(1, "LEDA", P), (2, "GND", P), (3, "RESET", P), (4, "RS", P), (5, "SDA", P), (6, "SCL", P), (7, "VDD", P), (8, "CS", P)],
                          descr="8-pin 0.5 mm ZIF for the 1.14 inch ST7789 panel's ribbon, the panel's pin names")
    s["DEBUG_3P"] = box("DEBUG_3P", "J", [(1, "SWCLK", P), (2, "GND", P), (3, "SWDIO", P)], [("SH", "TABS", P)],
                        descr="Raspberry Pi 3-pin debug connector, JST SH 1 mm")
    return s


SYMBOLS = None


def sym_pins(symdef):
    """number -> (x, y, angle, type, name)."""
    out = {}
    for sub in find(symdef, "symbol"):
        for p in find(sub, "pin"):
            at = first(p, "at")
            out[str(first(p, "number")[1])] = (at[1], at[2], at[3] if len(at) > 3 else 0, str(p[1]), first(p, "name")[1])
    return out


def write_symbols():
    lib = [Sym("kicad_symbol_lib"), S("version", 20220914), S("generator", Sym("tally_gen"))] + [SYMBOLS[n] for n in sorted(SYMBOLS)]
    os.makedirs(LIB, exist_ok=True)
    open(os.path.join(LIB, NAME + ".kicad_sym"), "w").write(dump(lib) + "\n")


# =================================================================================================
# Footprints: lib/tally.pretty holds every one the board uses, written once by "import" and kept in
# the repository. Three sources: KiCad's stock library; Raspberry Pi's own for the parts round the
# chip and the ZIF's from its maker's drawing, both as Mono's library has them; and two from KiCad
# 10's library that KiCad 7's lacks (FROM_KICAD10, fetched by hand). The ones not in KiCad 7's
# format are rewritten in it, which every later KiCad reads.
# =================================================================================================
STOCK_FP = {
    "C_0402_1005Metric": "Capacitor_SMD", "C_0805_2012Metric": "Capacitor_SMD", "R_0402_1005Metric": "Resistor_SMD",
    "R_0603_1608Metric": "Resistor_SMD", "LED_0603_1608Metric": "LED_SMD",
    "SOT-23": "Package_TO_SOT_SMD", "SOT-23-5": "Package_TO_SOT_SMD", "SOT-23-6": "Package_TO_SOT_SMD", "SOT-223-3_TabPin2": "Package_TO_SOT_SMD",
    "SOIC-8_3.9x4.9mm_P1.27mm": "Package_SO",
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": "Connector_USB", "SW_Push_1P1T_XKB_TS-1187A": "Button_Switch_SMD",
    "JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal": "Connector_JST",
    "TestPoint_Pad_D1.5mm": "TestPoint", "MountingHole_2.2mm_M2": "MountingHole", "Fiducial_1mm_Mask2mm": "Fiducial",
}
MONO_FP = os.path.join(REPO, "hardware", "mono", "lib", "mono.pretty")
PORTED_FP = ["RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias", "RPi_C_0402", "RPi_C_0402_wide", "RPi_R_0402", "RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm",
             "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB"]
FROM_KICAD10 = ["WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm", "SOIC-8_5.3x5.3mm_P1.27mm"]      # kicad-footprints, tag 10.0.0
KEEP_PAD = {"at", "size", "drill", "layers", "roundrect_rratio", "chamfer_ratio", "chamfer", "solder_mask_margin", "solder_paste_margin",
            "solder_paste_margin_ratio", "clearance", "zone_connect", "thermal_bridge_width", "thermal_gap", "property", "options", "primitives"}


def fp_to_v7(text, name=None):
    """A footprint file from KiCad 8, 9 or 10, rewritten as KiCad 7 writes one."""
    t = parse(text)
    name = name or t[1]
    out = [Sym("footprint"), name, S("version", 20221018), S("generator", Sym("tally_gen")), S("layer", "F.Cu")]

    def effects(e):
        f = first(e, "font")
        font_ = [Sym("font")] + [c for c in f[1:] if isinstance(c, list) and c[0] in ("size", "thickness")]
        font_ += [Sym(c[0]) for c in f[1:] if isinstance(c, list) and c[0] in ("bold", "italic") and str(c[1]) == "yes"]
        return [Sym("effects"), font_] + [c for c in e[1:] if isinstance(c, list) and c[0] == "justify"]

    def text_(kind, value, c):
        at = first(c, "at")
        hidden = any(isinstance(x, list) and x[0] == "hide" and str(x[1]) == "yes" for x in c) or (
            first(c, "effects") and any(isinstance(x, list) and x[0] == "hide" and str(x[1]) == "yes" for x in first(c, "effects")))
        o = [Sym("fp_text"), Sym(kind), value, at, first(c, "layer")]
        if hidden:
            o.append(Sym("hide"))
        return o + [effects(first(c, "effects"))]

    def shape(c):
        o = [c[0]]
        for x in c[1:]:
            if not isinstance(x, list):
                continue
            if x[0] == "fill":
                v = str(x[1])
                o.append(S("fill", Sym("solid" if v in ("yes", "solid") else "none")))
            elif x[0] in ("start", "end", "center", "mid", "pts", "stroke", "layer"):
                o.append(x)
        if c[0] in ("fp_line", "fp_arc"):
            o = [x for x in o if not (isinstance(x, list) and x[0] == "fill")]
        return o

    for c in t[2:]:
        if not isinstance(c, list):
            continue
        k = c[0]
        if k in ("descr", "tags", "attr"):
            out.append(c)
        elif k == "property" and c[1] in ("Reference", "Value"):
            out.append(text_(c[1].lower(), c[2], c))
        elif k == "fp_text":
            out.append(text_(str(c[1]), c[2], c))
        elif k in ("fp_line", "fp_rect", "fp_circle", "fp_poly", "fp_arc"):
            if k == "fp_poly" and first(c, "layer")[1] == "F.SilkS":
                continue                 # KiCad 10's filled pin-1 triangle: it sits on the pads' mask openings
            out.append(shape(c))
        elif k == "pad":
            out.append(c[:4] + [x for x in c[4:] if isinstance(x, list) and x[0] in KEEP_PAD])
        elif k == "model":
            out.append(c)
    return dump(out) + "\n"


def import_footprints(kicad10_dir):
    """Writes lib/tally.pretty afresh. Run once, with KiCad 7's stock library here and the two KiCad 10 files in kicad10_dir."""
    import pcbnew
    tmp = os.path.join(tempfile.mkdtemp(prefix="tally-fp-"), NAME + ".pretty")
    os.makedirs(tmp)                    # pcbnew's FootprintSave wants the folder there
    for name, lib in sorted(STOCK_FP.items()):
        fp = pcbnew.FootprintLoad(os.path.join(KIFP, lib + ".pretty"), name)
        if name.startswith("USB_C"):
            for pad in fp.Pads():       # the shell: SH, as KiCad 10's library and tools/jlc name it
                if pad.GetNumber() == "S1":
                    pad.SetNumber("SH")
        if name.startswith("JST_SH"):
            for pad in fp.Pads():       # its two solder tabs, the same way: not counted as pins
                if pad.GetNumber() == "MP":
                    pad.SetNumber("SH")
        pcbnew.FootprintSave(tmp, fp)
    for name in PORTED_FP:
        open(os.path.join(tmp, name + ".kicad_mod"), "w").write(fp_to_v7(open(os.path.join(MONO_FP, name + ".kicad_mod")).read()))
    for name in FROM_KICAD10:
        open(os.path.join(tmp, name + ".kicad_mod"), "w").write(fp_to_v7(open(os.path.join(kicad10_dir, name + ".kicad_mod")).read()))
    for f in sorted(os.listdir(tmp)):          # 3D models by KiCad 10's names, as the repo's other boards
        p = os.path.join(tmp, f)
        txt = open(p).read()
        if f.startswith("USB_C"):       # its silkscreen sides run past the board's edge, where the connector overhangs
            t = parse(txt)
            def past(c):
                return (isinstance(c, list) and c[0] == "fp_line" and first(c, "layer")[1] == "F.SilkS"
                        and max(first(c, "start")[2], first(c, "end")[2]) > 3.0)
            txt = dump([c for c in t if not past(c)]) + "\n"
        txt = re.sub(r"\$\{KICAD\d+_3DMODEL_DIR\}", "${KICAD10_3DMODEL_DIR}", txt).replace('.wrl"', '.step"')
        open(p, "w").write(txt)
    shutil.rmtree(PRETTY, ignore_errors=True)
    shutil.copytree(tmp, PRETTY)
    for f in sorted(os.listdir(PRETTY)):
        if pcbnew.FootprintLoad(PRETTY, f[:-len(".kicad_mod")]) is None:        # each must read back
            raise SystemExit(f"{f} does not read back")


# =================================================================================================
# The schematic: each part placed, a stub from each pin, and at its end a power symbol or a label.
# Nothing is drawn wire to wire, so a connection is exactly a name.
# =================================================================================================
G = 1.27


class Sheet:
    def __init__(self):
        self.root = uid("sheet")
        self.used, self.items, self.at, self.n_pwr, self.points = {}, [], {}, 0, {}

    def lib(self, name):
        if name not in self.used:      # in the sheet the symbol is "tally:R", its units still "R_0_1"
            self.used[name] = [Sym("symbol"), NAME + ":" + name] + SYMBOLS[name][2:]
        return SYMBOLS[name]

    @staticmethod
    def xf(px, py, ang, x, y, rot):
        """Symbol space (y up) to sheet space (y down), turned rot degrees anticlockwise."""
        c, s = round(math.cos(math.radians(rot))), round(math.sin(math.radians(rot)))
        return round(x + px * c - py * s, 4), round(y - (px * s + py * c), 4), (ang + rot) % 360

    def _instance(self, name, ref, x, y, rot, props, flags):
        d = self.lib(name)
        s = S("symbol", S("lib_id", NAME + ":" + name), S("at", x, y, rot), S("unit", 1), *flags, S("uuid", uid("sym", ref)))
        dp = {p[1]: p for p in find(d, "property")}
        for k, v, hide in props:
            a = first(dp[k], "at") if k in dp else S("at", 0, 0, 0)
            ax, ay, _ = self.xf(a[1], a[2], 0, x, y, rot)
            j = first(first(dp[k], "effects"), "justify") if k in dp else None
            s.append(S("property", k, v, S("at", ax, ay, (a[3] if len(a) > 3 else 0)), font(hide=hide, just=" ".join(map(str, j[1:])) if j else None)))
        for num in sym_pins(d):
            s.append(S("pin", num, S("uuid", uid("pin", ref, num))))
        s.append(S("instances", S("project", NAME, S("path", "/" + self.root, S("reference", ref), S("unit", 1)))))
        self.items.append(s)

    def place(self, p, x, y, rot=0):
        x, y = round(round(x / G) * G, 4), round(round(y / G) * G, 4)
        self.at[p["ref"]] = (p["sym"], x, y, rot)
        fitted = not p.get("dnp")
        props = [("Reference", p["ref"], False), ("Value", p["value"], False), ("Footprint", NAME + ":" + p["fp"], True), ("Datasheet", "~", True)]
        if p.get("lcsc"):
            props += [("LCSC", p["lcsc"], True), ("MPN", p["mpn"], True)]
        if p.get("rot_offset") is not None:
            props.append(("JLCPCB Rotation Offset", str(p["rot_offset"]), True))
        yn = lambda b: Sym("yes" if b else "no")
        self._instance(p["sym"], p["ref"], x, y, rot, props,
                       [S("in_bom", yn(p.get("bom", True))), S("on_board", Sym("yes")), S("dnp", yn(not fitted))])
        pins = sym_pins(SYMBOLS[p["sym"]])
        for num in sorted(set(p["nets"]) - set(pins)):
            raise SystemExit(f"{p['ref']}: the table names pin {num}, which {p['sym']} doesn't have")
        for num, (px, py, ang, typ, _n) in pins.items():
            ex, ey, ea = self.xf(px, py, ang, x, y, rot)
            net = p["nets"].get(num)
            if net is None:
                if typ != "no_connect":
                    self.items.append(S("no_connect", S("at", ex, ey), S("uuid", uid("nc", p["ref"], num))))
                continue
            dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[ea]      # away from the body
            self.net_at(net, ex, ey, dx, dy, (p["ref"], num))

    def net_at(self, net, x, y, dx, dy, key):
        """From (x, y), a stub going (dx, dy) and the net's name at its end: a power symbol where it
        can stand upright, else a label."""
        x2, y2 = round(x + dx * 2.54, 4), round(y + dy * 2.54, 4)
        self.items.append(S("wire", S("pts", S("xy", x, y), S("xy", x2, y2)), S("stroke", S("width", 0), S("type", Sym("default"))), S("uuid", uid("wire", *key))))
        for pt in ((x, y), (round(x + dx * 1.27, 4), round(y + dy * 1.27, 4)), (x2, y2)):     # two stubs on one spot would join their nets
            other = self.points.setdefault(pt, (net, key))
            if other[0] != net:
                raise SystemExit(f"the sheet: {key} ({net}) and {other[1]} ({other[0]}) meet at {pt}")
        if net in POWER and (dy == 0 or (dy < 0) == (net != GND)):
            self.power(net, x2, y2, key)
            return
        ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[(dx, dy)]
        just = "left bottom" if ang in (0, 90) else "right bottom"
        self.items.append(S("label", net, S("at", x2, y2, ang), font(just=just), S("uuid", uid("label", *key))))

    def power(self, net, x, y, key):
        self.lib(net)
        self.n_pwr += 1
        ref = "#PWR%03d" % self.n_pwr if net != "PWR_FLAG" else "#FLG%03d" % self.n_pwr
        dy = 3.81 if net == GND else -3.81
        self.items.append(S("symbol", S("lib_id", NAME + ":" + net), S("at", x, y, 0), S("unit", 1), S("in_bom", Sym("yes")), S("on_board", Sym("yes")),
                            S("dnp", Sym("no")), S("uuid", uid("pwr", *key)),
                            S("property", "Reference", ref, S("at", x, y, 0), font(hide=True)),
                            S("property", "Value", net, S("at", x, round(y + dy, 4), 0), font()),
                            S("property", "Footprint", "", S("at", x, y, 0), font(hide=True)),
                            S("property", "Datasheet", "", S("at", x, y, 0), font(hide=True)),
                            S("pin", "1", S("uuid", uid("pwrpin", *key))),
                            S("instances", S("project", NAME, S("path", "/" + self.root, S("reference", ref), S("unit", 1))))))

    def flag(self, net, x, y):
        """A PWR_FLAG on a net no symbol drives: the flag, a stub down, and the net."""
        x, y = round(round(x / G) * G, 4), round(round(y / G) * G, 4)
        self.power("PWR_FLAG", x, y, ("flag", net))
        self.items.append(S("wire", S("pts", S("xy", x, y), S("xy", x, round(y + 2.54, 4))), S("stroke", S("width", 0), S("type", Sym("default"))), S("uuid", uid("flagwire", net))))
        if net == GND:
            self.power(GND, x, round(y + 2.54, 4), ("flagnet", net))
        else:
            self.items.append(S("label", net, S("at", x, round(y + 2.54, 4), 270), font(just="right bottom"), S("uuid", uid("flaglabel", net))))
            # a label alone doesn't name a power net: the power symbol beside it does
            self.items.append(S("wire", S("pts", S("xy", x, y), S("xy", round(x + 5.08, 4), y)), S("stroke", S("width", 0), S("type", Sym("default"))), S("uuid", uid("flagwire2", net))))
            self.power(net, round(x + 5.08, 4), y, ("flagnet", net))

    def text(self, s, x, y, size=1.8):
        self.items.append(S("text", s, S("at", x, y, 0), S("effects", S("font", S("size", size, size)), S("justify", Sym("left"), Sym("bottom"))), S("uuid", uid("text", s))))

    def write(self, path):
        tb = S("title_block", S("title", "Picoquorum Tally: a slender console, an RP2350A, no radio, USB serial to the host"), S("date", DATE), S("rev", REV),
               S("company", "Picoquorum"), S("comment", 1, "Written by hardware/tally/gen_tally.py. CERN-OHL-W v2"),
               S("comment", 2, "Source Location: https://github.com/jmcpheron/pico-quorum"))
        doc = [Sym("kicad_sch"), S("version", 20230121), S("generator", Sym("eeschema")), S("uuid", self.root), S("paper", "A2"), tb,
               [Sym("lib_symbols")] + [self.used[n] for n in sorted(self.used)]] + self.items
        doc.append(S("sheet_instances", S("path", "/", S("page", "1"))))
        open(path, "w").write(dump(doc) + "\n")


def g(n):
    return round(n * 2.54, 4)


def row(x, y, refs, dx=7):
    return {r: (g(x + i * dx), g(y)) for i, r in enumerate(refs)}


# where each part sits on the sheet (in 2.54 mm steps), block by block
PLACE = {
    "J1": (g(16), g(18)), **row(30, 12, ["R1", "R2"], 5), "U2": (g(34), g(24)),
    "U3": (g(58), g(12)), "C1": (g(46), g(12)), "C2": (g(70), g(12)),
    "U4": (g(58), g(24)), "C3": (g(46), g(24)), "C4": (g(70), g(24)),
    "U5": (g(28), g(44)), **row(6, 42, ["C5", "C6", "C7"], 5),
    "U1": (g(104), g(52)),
    **row(82, 12, ["C10", "C11", "C12", "C13", "C14", "C15", "C19", "C20"], 5), **row(124, 12, ["C16", "C17", "C18"], 5),
    "Y1": (g(74), g(62)), "C21": (g(68), g(70)), "C22": (g(80), g(70)), "R3": (g(84), g(60)),
    "U7": (g(156), g(70)), "C23": (g(170), g(68)),
    "U6": (g(158), g(14)), "C24": (g(144), g(12)), "R7": (g(174), g(12)), "R8": (g(179), g(12)),
    "J2": (g(158), g(38)), "C25": (g(144), g(34)), "C26": (g(149), g(34)),
    "Q1": (g(190), g(38)), "Q2": (g(182), g(50)), "R9": (g(178), g(34)), "R10": (g(172), g(52)), "R11": (g(200), g(38)),
    **{f"SW{i + 1}": (g(14 + 14 * i), g(68)) for i in range(3)}, "D1": (g(24), g(78)), "R12": (g(12), g(80)),
    "J3": (g(16), g(94)), **row(36, 94, [f"TP{i}" for i in (1, 2, 3, 4, 5, 9, 10, 11, 12, 13)], 7),
    **row(140, 94, ["H1", "H2", "H3", "H4"], 6), **row(170, 94, ["FID1", "FID2", "FID3"], 6),
}
ROT = {}
NOTES = [
    (g(4), g(5), "Power in. 5.1k on each CC. 5.7u on VBUS. U3: 5 V to 3.3 V. U4: 3.3 V to the core's 1.1 V."),
    (g(4), g(34), "The link: USB to UART1 and nothing else. DTR and RTS reach nothing."),
    (g(80), g(5), "The RP2350A. Its own core regulator is not used: FB to ground, LX open, its supplies on 3.3 V (datasheet, figure 24)."),
    (g(142), g(5), "The key that signs: I2C0, 4.7k pull-ups."),
    (g(142), g(27), "The screen's ribbon, and its backlight from 5 V: GPIO13 high is on."),
    (g(146), g(60), "Not fitted: a flash, only for a build with an RP2350A at U1."),
    (g(4), g(62), "D0, D1, D2 to ground; the LED."),
    (g(4), g(88), "The way in for firmware: SWD on J3 and the pads on the back. Nothing here is reached through the USB-C."),
]


def write_schematic():
    sh = Sheet()
    for p in PARTS:
        if p["ref"] not in PLACE:
            raise SystemExit(f"{p['ref']} has no place on the sheet")
        sh.place(p, *PLACE[p["ref"]], ROT.get(p["ref"], 0))
    for i, net in enumerate(FLAGS):
        sh.flag(net, g(196 + 10 * i), g(12))
    for x, y, s in NOTES:
        sh.text(s, x, y)
    os.makedirs(OUT, exist_ok=True)
    sh.write(os.path.join(OUT, NAME + ".kicad_sch"))
    open(os.path.join(OUT, "sym-lib-table"), "w").write(
        f'(sym_lib_table\n  (version 7)\n  (lib (name "{NAME}")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/{NAME}.kicad_sym")(options "")(descr "Tally\'s own symbols"))\n)\n')


# =================================================================================================
# Checks on the schematic: KiCad's own netlist of it against the table
# =================================================================================================
def kicad_env():
    """A fresh KiCad configuration, so nothing on this machine changes what KiCad reads."""
    cfg = tempfile.mkdtemp(prefix="tally-kicad-")
    return dict(os.environ, KICAD_CONFIG_HOME=cfg, HOME=cfg)


def netlist():
    """{net: {(ref, pin)}} and {ref: (value, footprint, {field: value})}, as KiCad reads the schematic."""
    with tempfile.TemporaryDirectory() as t:
        out = os.path.join(t, "n.net")
        r = subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, os.path.join(OUT, NAME + ".kicad_sch")],
                           capture_output=True, text=True, env=kicad_env())
        if r.returncode or not os.path.exists(out):
            raise SystemExit(f"kicad-cli netlist failed:\n{r.stdout}{r.stderr}")
        n = parse(open(out).read())
    nets = {first(x, "name")[1]: {(first(nd, "ref")[1], str(first(nd, "pin")[1])) for nd in find(x, "node")} for x in find(first(n, "nets"), "net")}
    comps = {}
    for c in find(first(n, "components"), "comp"):
        fields = {(f[1][1] if isinstance(f[1], list) else f[1]): (f[-1] if not isinstance(f[-1], list) else "") for f in find(first(c, "fields") or [], "field")}
        comps[first(c, "ref")[1]] = (str(first(c, "value")[1]), first(c, "footprint")[1] if first(c, "footprint") else "", fields)
    return nets, comps


def table_nets():
    want = {}
    for p in PARTS:
        for pin, net in p["nets"].items():
            want.setdefault(net if net in POWER else "/" + net, set()).add((p["ref"], pin))
    return want


def check_netlist(nets, comps):
    bad = []
    want = table_nets()
    for net, pins in sorted(want.items()):
        got = {x for x in nets.get(net, set()) if not x[0].startswith("#")}
        if got != pins:
            bad.append(f"net {net}: the table has {sorted(pins - got)} that KiCad lacks, KiCad has {sorted(got - pins)} that the table lacks")
    for net, pins in sorted(nets.items()):
        real = {x for x in pins if not x[0].startswith("#")}
        if net not in want and len(real) > 1:
            bad.append(f"net {net} joins {sorted(real)} and is not in the table")
        if net not in want and not net.startswith("unconnected-") and real:
            bad.append(f"net {net} is not in the table")
    for p in PARTS:
        c = comps.get(p["ref"])
        if c is None:
            bad.append(f"{p['ref']} is not in KiCad's netlist")
        elif c[0] != p["value"] or c[1] != NAME + ":" + p["fp"] or c[2].get("LCSC", "") != p.get("lcsc", ""):
            bad.append(f"{p['ref']}: KiCad reads {c}, the table says {p['value']}, {p['fp']}, {p.get('lcsc')}")
    extra = sorted(set(comps) - set(BY_REF))
    if extra:
        bad.append(f"KiCad's netlist has parts the table lacks: {extra}")
    return bad


def check_table():
    """The table against itself, the chip's function table and the firmware's pins."""
    bad = []
    refs = [p["ref"] for p in PARTS]
    bad += [f"{r} is in the table twice" for r in sorted({r for r in refs if refs.count(r) > 1})]
    for net, g_ in GPIO.items():
        if net in NEEDS and not NEEDS[net](g_):
            bad.append(f"{net} is on GPIO{g_}, which can't be that function")
        if U1_NETS.get(str(GPIO_PIN[g_])) != net:
            bad.append(f"{net}: pin {GPIO_PIN[g_]} is not GPIO{g_} in the table")
    pins = sym_pins(SYMBOLS["RP2350A"])
    for p_, g_ in PIN_GPIO.items():
        if pins[str(p_)][4] != "GPIO%d" % g_:
            bad.append(f"U1 pin {p_} is {pins[str(p_)][4]} in the symbol, GPIO{g_} in the table")
    if len(pins) != 61:
        bad.append(f"U1's symbol has {len(pins)} pins, not 61")
    # one-pin nets are mistakes, but for a test pad's own
    count = {}
    for p in PARTS:
        for net in p["nets"].values():
            count[net] = count.get(net, 0) + 1
    bad += [f"net {n} has one pin" for n, c in sorted(count.items()) if c < 2]
    # firmware/board.py's Pico defaults for the screen and the key bus, which console-rp and Mono keep
    try:
        src = open(os.path.join(REPO, "firmware", "board.py")).read()
        m = re.search(r"LCD_PINS\s*=\s*dict\(([^)]*)\)", src)
        if m:
            fw = dict((k.strip(), int(v)) for k, v in (kv.split("=") for kv in m.group(1).split(",")) if v.strip().isdigit())
            for k, net in (("dc", "LCD_DC"), ("cs", "LCD_CS"), ("sck", "LCD_SCK"), ("mosi", "LCD_MOSI"), ("rst", "LCD_RST"), ("bl", "LCD_BL")):
                if k in fw and fw[k] != GPIO[net]:
                    bad.append(f"{net} is GPIO{GPIO[net]}, firmware/board.py's Pico default is {fw[k]}")
    except OSError:
        pass
    return bad


# =================================================================================================
# The board: a 40 x 89.5 mm bar, Mono's outline, holes, glass and buttons, so Mono's case drafts
# fit it but for the USB-C's opening, which follows J1 to the middle. y runs down from the top edge.
# cad/consoles/mono.py reads W, H, TOP, CORNER, AT, the glass and PANEL from a generator by these names.
# =================================================================================================
W, TOP, H = 40.0, 0.0, 89.5
OX, OY = 100.0, 100.0                    # where the board's top-left corner sits on KiCad's page
CORNER = 2.0
HOLE_RING = 2.5                          # no track or via this close to an M2 hole's centre: a screw head and a post land there
CLEAR = 0.15

# The panel: ER-TFT1.14-2 (EastRising's drawing, rev 1.0, 2022-02-22), as Mono's generator reads it:
# the module 31.0 x 17.6, 1.6 thick; the active area 24.91 x 14.86, 1.445 mm off the module's centre
# away from the ribbon; the ribbon 4.5 wide, folded under reaching 21.0 +-0.5 mm in from the ribbon end.
PANEL = dict(glass=(31.0, 17.6), active=(24.91, 14.86), active_off=1.445, rows=135, cols=240, thick=1.6,
             foam=2.0, pad=2.0, reach=21.0, ribbon=4.5)
XA = W / 2                               # the picture's centre across: the board's middle
GX0 = round(XA + PANEL["active_off"] - PANEL["glass"][0] / 2, 4)     # the glass's left end; the ribbon leaves its right end
GY0 = 1.0
GX1, GY1 = GX0 + PANEL["glass"][0], GY0 + PANEL["glass"][1]
XC, YC = (GX0 + GX1) / 2, (GY0 + GY1) / 2
ZIF_X = round(GX1 - 19.5, 3)             # J2's origin 19.5 mm in from the glass's ribbon end, as console-s3's, PicoquorumKey's and Mono's
PITCH, BY = 10.0, 24.0                   # the buttons: 10 mm apart, their row 24 mm below the top edge
U1 = (20.0, 47.0)                        # the RP2350's centre, turned -90: pins 1-15 (screen, buttons, key) face up
J1 = (20.0, H - 3.6)                     # the USB-C, its opening down, its face on the bottom edge
TPY = 68.0                               # the jig's pads' row, on the back: Mono's places


def u1(x, y):
    """A point given from U1's centre in Raspberry Pi's frame (the chip not turned, pin 1 top-left), on
    the board: U1 turned -90 (KiCad's angles run anticlockwise), so their x runs down the board and
    their y runs left."""
    return round(U1[0] - y, 4), round(U1[1] + x, 4)


def pin(n):
    """U1's pad n on the board: 15 pads a side at 0.4 mm, their centres 3.45 mm out."""
    side, k = divmod(n - 1, 15)
    o = -2.8 + 0.4 * k
    return u1(*((-3.45, o), (o, 3.45), (3.45, -o), (-o, -3.45))[side])


def jm(x, y):
    """A point given from J1's origin."""
    return round(J1[0] + x, 4), round(J1[1] + y, 4)


# Raspberry Pi's minimal board round the chip (rpi_minimal.json, which console-rp's rpi_minimal.py
# wrote from their MIT KiCad files): where each part sits from U1's centre, and their copper. Their
# switching regulator's parts and copper are left out; the rest keeps its place, turned with U1.
RPI = json.load(open(os.path.join(HERE, "rpi_minimal.json")))
RPI_REF = {"C4": "C10", "C5": "C11", "C6": "C12", "C7": "C13", "C8": "C14", "C13": "C15", "C10": "C16", "C12": "C17", "C11": "C18",
           "C1": "C20", "R2": "R3", "Y1": "Y1", "C15": "C21", "C16": "C22"}
RPI_NET = {"+3V3": V33, "/DVDD": V11, "GND": GND, "/XIN": "/XIN", "/XOUT": "/XOUT", "/XTAL_OUT": "/XTAL_OUT"}


def rot(r):
    r = (r + 180) % 360 - 180
    return 180 if r == -180 else r


TP_X = {"TP1": 3.0, "TP2": 5.54, "TP3": 8.08, "TP4": 10.62, "TP5": 13.16, "TP9": 35.62}      # Mono's BOOT, D+ and D- pads (28.0, 30.54, 33.08) have no twin here
# ref -> (x, y, rotation in degrees)
AT = {
    "SW1": (XA - PITCH, BY, 90), "SW2": (XA, BY, 90), "SW3": (XA + PITCH, BY, 90),
    "H1": (3.5, BY, 0), "H2": (W - 3.5, BY, 0), "H3": (3.5, H - 3.5, 0), "H4": (W - 3.5, H - 3.5, 0),
    # under the glass: only the screen's connector and its two capacitors
    "J2": (ZIF_X, YC, 90), "C25": (13.9, 7.45, 180), "C26": (13.9, 8.55, 180),
    # the key under D2, its bus pins facing the chip
    "U6": (19.6, 33.6, 90), "R7": (20.5, 28.3, 180), "R8": (19.1, 29.4, 180), "C24": (17.2, 29.4, 180),
    # the RP2350 with Raspberry Pi's parts round it
    "U1": (*U1, -90),
    **{RPI_REF[r]: (*u1(*p["at"]), rot(p["rot"] - 90)) for r, p in RPI["parts"].items() if r in RPI_REF},
    # the flash up and to the right, its chip-select, IO1 and IO2 pads over the chip's pins for them; its capacitor
    "U7": (26.9, 39.0, 90), "C23": (23.15, 35.4, 90),
    # pins 53 and 54's capacitor right at the pins (Raspberry Pi's sits 3.5 mm off, where the flash's lines run here)
    "C19": (24.9, 46.8, 0),
    # the core's regulator under the chip, by DVDD's pin 39
    "U4": (22.6, 57.2, 90), "C3": (19.8, 58.3, 180), "C4": (19.8, 56.1, 180),
    "D1": (20.2, 62.4, 180), "R12": (22.9, 62.4, 0),
    "J3": (4.2, 57.5, 270),
    # the bottom end: the USB-C, the ESD diodes in line, the bridge, the 3.3 V regulator, the backlight's switch
    "J1": (*J1, 0), "U2": (*jm(0.0, -8.3), 90), "R1": (*jm(-2.3, -6.25), 90), "R2": (*jm(2.2, -6.25), 90),
    "U5": (*jm(-0.5, -14.2), 0), "C5": (15.6, 72.0, 180), "C6": (17.8, 75.1, -90), "C7": (16.6, 70.0, 180),
    "U3": (31.2, 77.6, 0), "C1": (25.0, 79.3, 90), "C2": (25.6, 76.4, 90),
    # the backlight's switch left of the screen's lines, between the chip and D0: 5 V comes up the left edge
    "R11": (4.9, 36.5, 180), "Q1": (8.4, 36.5, 180), "R9": (8.4, 39.3, 180), "Q2": (11.3, 40.0, 180), "R10": (11.2, 42.2, 180),
    # fiducials, each 3.85 mm or more from the edge
    "FID1": (3.85, 6.0, 0), "FID2": (W - 3.85, 54.0, 0), "FID3": (9.5, H - 3.85, 0),
    **{t: (x, TPY, 0) for t, x in TP_X.items()},
    "TP10": (22.2, 55.4, 0), "TP11": (25.6, 84.6, 0), "TP12": (12.6, 64.2, 0), "TP13": (15.8, 64.2, 0),
}
BACK = {r for r in AT if r.startswith("TP")}
# pads joined to the ground pours solidly: thermal spokes can't reach these from two sides
SOLID = {("J1", "A1"), ("J1", "B12"), ("J1", "A12"), ("J1", "B1"), ("C20", "2")}


def mm(v):
    return int(round(v * 1e6))


def P(x, y):
    """A board point (mm from its top-left corner) as KiCad's, to the nanometre: VECTOR2I_MM truncates."""
    import pcbnew
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


RULES = dict(min_clearance=0.125, min_track_width=0.15, min_copper_edge_clearance=0.3, min_hole_clearance=0.25, min_hole_to_hole=0.25,
             min_via_diameter=0.45, min_through_hole_diameter=0.3, min_via_annular_width=0.13, min_text_height=0.8, min_text_thickness=0.12,
             min_silk_clearance=0.0, min_resolved_spokes=2, min_connection=0.0, min_microvia_diameter=0.2, min_microvia_drill=0.1,
             max_error=0.005, solder_mask_to_copper_clearance=0.0)
SEVERITIES = dict(annular_width="error", clearance="error", connection_width="warning", copper_edge_clearance="error", copper_sliver="warning",
                  courtyards_overlap="error", diff_pair_gap_out_of_range="error", diff_pair_uncoupled_length_too_long="error",
                  drill_out_of_range="error", duplicate_footprints="warning", extra_footprint="warning", footprint="error",
                  footprint_type_mismatch="ignore", hole_clearance="error", hole_near_hole="warning", invalid_outline="error",
                  isolated_copper="warning", item_on_disabled_layer="error", items_not_allowed="error", length_out_of_range="error",
                  lib_footprint_issues="warning", lib_footprint_mismatch="warning", malformed_courtyard="error", microvia_drill_out_of_range="error",
                  missing_courtyard="ignore", missing_footprint="warning", net_conflict="warning", npth_inside_courtyard="ignore", padstack="warning",
                  pth_inside_courtyard="ignore", shorting_items="error", silk_edge_clearance="warning", silk_over_copper="warning",
                  silk_overlap="warning", skew_out_of_range="error", solder_mask_bridge="error", starved_thermal="error", text_height="warning",
                  text_thickness="warning", through_hole_pad_without_hole="error", too_many_vias="error", track_dangling="warning",
                  track_width="error", tracks_crossing="error", unconnected_items="error", unresolved_variable="error", via_dangling="warning",
                  zones_intersect="error")
CLASSES = [("Default", 0.2, []), ("Power", 0.3, [V33, V11, VBUS]), ("Ground", 0.3, [GND])]


def write_project():
    cls = [dict(name=n, clearance=CLEAR, track_width=w, via_diameter=0.6, via_drill=0.3, microvia_diameter=0.3, microvia_drill=0.1,
                diff_pair_width=0.2, diff_pair_gap=0.25, diff_pair_via_gap=0.25, bus_width=12, wire_width=6, line_style=0,
                pcb_color="rgba(0, 0, 0, 0.000)", schematic_color="rgba(0, 0, 0, 0.000)") for n, w, _nets in CLASSES]
    pro = {"board": {"design_settings": {"defaults": {}, "diff_pair_dimensions": [], "drc_exclusions": [], "rule_severities": SEVERITIES,
                                         "rules": RULES, "track_widths": [], "via_dimensions": []}},
           "boards": [], "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
           "meta": {"filename": NAME + ".kicad_pro", "version": 1},
           "net_settings": {"classes": cls, "meta": {"version": 3}, "net_colors": None, "netclass_assignments": None,
                            "netclass_patterns": [{"netclass": n, "pattern": net} for n, _w, nets in CLASSES for net in nets]},
           "pcbnew": {"page_layout_descr_file": ""}, "sheets": [], "text_variables": {}}
    open(os.path.join(OUT, NAME + ".kicad_pro"), "w").write(json.dumps(pro, indent=2, sort_keys=True) + "\n")
    open(os.path.join(OUT, "fp-lib-table"), "w").write(
        f'(fp_lib_table\n  (version 7)\n  (lib (name "{NAME}")(type "KiCad")(uri "${{KIPRJMOD}}/../lib/{NAME}.pretty")(options "")(descr "Tally\'s own footprints"))\n)\n')


def place_board(nets):
    """The board with every part placed and its pads on their nets, as KiCad's netlist of the schematic names them."""
    import pcbnew
    b = pcbnew.BOARD()
    pad_net = {}
    for name, pins in sorted(nets.items()):
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        for ref, pin_ in pins:
            pad_net[ref, pin_] = ni
    for p in PARTS:
        fp = pcbnew.FootprintLoad(PRETTY, p["fp"])
        fp.SetFPID(pcbnew.LIB_ID(NAME, p["fp"]))
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + uid("sym", p["ref"])))
        fp.Reference().SetLayer(pcbnew.F_Fab)           # 0402s are too close for names on the silkscreen
        fp.Value().SetLayer(pcbnew.F_Fab)
        fp.Value().SetVisible(False)
        x, y, r = AT[p["ref"]]
        fp.SetPosition(P(x, y))
        b.Add(fp)
        if p["ref"] in BACK:
            fp.Flip(P(x, y), getattr(pcbnew, "FLIP_DIRECTION_LEFT_RIGHT", False))
        fp.SetOrientationDegrees(r)
        attr = fp.GetAttributes()
        if not p.get("lcsc"):            # in no BOM and no placement file: holes, fiducials, pads, the flash's place
            attr |= pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES
        fp.SetAttributes(attr)
        for pad in fp.Pads():
            n = pad.GetNumber()
            if n and (p["ref"], n) in pad_net:
                pad.SetNet(pad_net[p["ref"], n])
            elif n:
                raise SystemExit(f"{p['ref']}: pad {n} of {p['fp']} has no pin in the schematic")
            if (p["ref"], n) in SOLID:
                (getattr(pad, "SetLocalZoneConnection", None) or pad.SetZoneConnection)(pcbnew.ZONE_CONNECTION_FULL)   # KiCad 9's name, or 7's
    return b


def outline(b):
    import pcbnew
    r = CORNER
    def line(a, z):
        s_ = pcbnew.PCB_SHAPE(b)
        s_.SetShape(pcbnew.SHAPE_T_SEGMENT); s_.SetStart(P(*a)); s_.SetEnd(P(*z)); s_.SetLayer(pcbnew.Edge_Cuts); s_.SetWidth(mm(0.05))
        b.Add(s_)
    def arc(c, a0):
        s_ = pcbnew.PCB_SHAPE(b)
        s_.SetShape(pcbnew.SHAPE_T_ARC); s_.SetLayer(pcbnew.Edge_Cuts); s_.SetWidth(mm(0.05))
        cx, cy = c
        a = math.radians(a0)
        st = (cx + r * math.cos(a), cy + r * math.sin(a))
        md = (cx + r * math.cos(a + math.pi / 4), cy + r * math.sin(a + math.pi / 4))
        en = (cx + r * math.cos(a + math.pi / 2), cy + r * math.sin(a + math.pi / 2))
        s_.SetArcGeometry(P(*st), P(*md), P(*en))
        b.Add(s_)
    line((r, 0), (W - r, 0)); line((W, r), (W, H - r)); line((W - r, H), (r, H)); line((0, H - r), (0, r))
    arc((r, r), 180); arc((W - r, r), 270); arc((W - r, H - r), 0); arc((r, H - r), 90)
    ds = b.GetDesignSettings()
    ds.SetAuxOrigin(P(0, H))             # the fab files' origin: the bottom-left corner
    ds.SetGridOrigin(P(0, H))
    ds.SetBoardThickness(mm(1.6))


# --- copper ------------------------------------------------------------------------------------
VIA = (0.6, 0.3)                         # every via: 0.6 mm pad, 0.3 mm hole, JLCPCB's base price


def netname(n):
    return n if n in POWER else ("/" + n.lstrip("/"))


class Copper:
    """Tracks, vias and zones go onto the board and into the router's picture of it together."""

    def __init__(self, b):
        import pcbnew
        self.b, self.k = b, pcbnew
        self.layer = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
        self.tracks, self.vias = [], []      # (net, layer, [pts], width), (net, x, y)

    def net(self, name):
        n = self.b.FindNet(netname(name))
        if n is None:
            raise SystemExit(f"no net {name}")
        return n

    def track(self, net, layer, pts, w=0.2, locked=True):
        k = self.k
        for a, z in zip(pts, pts[1:]):
            if a == z:
                continue
            t = k.PCB_TRACK(self.b)
            t.SetStart(P(*a)); t.SetEnd(P(*z)); t.SetWidth(mm(w)); t.SetLayer(self.layer[layer]); t.SetNet(self.net(net)); t.SetLocked(locked)
            self.b.Add(t)
        self.tracks.append((netname(net), layer, list(pts), w))

    def via(self, net, x, y, locked=True):
        k = self.k
        v = k.PCB_VIA(self.b)
        v.SetPosition(P(x, y)); v.SetWidth(mm(VIA[0])); v.SetDrill(mm(VIA[1])); v.SetViaType(k.VIATYPE_THROUGH)
        v.SetLayerPair(k.F_Cu, k.B_Cu); v.SetNet(self.net(net)); v.SetLocked(locked)
        self.b.Add(v)
        self.vias.append((netname(net), x, y))

    def zone(self, net, layers, pts, prio=0, clearance=0.2, min_w=0.2, solid=False, gap=0.3, spoke=0.3, rule=None):
        k = self.k
        z = k.ZONE(self.b)
        ls = k.LSET()
        for l in layers:
            ls.AddLayer(self.layer[l])
        z.SetLayerSet(ls)
        o = z.Outline()
        o.NewOutline()
        for x, y in pts:
            o.Append(mm(OX + x), mm(OY + y))
        if rule:                         # a keep-out: no tracks or vias; pads, footprints and pours may
            z.SetIsRuleArea(True); z.SetZoneName(rule)
            z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
            z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False); z.SetDoNotAllowCopperPour(False)
        else:
            z.SetNet(self.net(net)); z.SetAssignedPriority(prio)
            z.SetLocalClearance(mm(clearance)); z.SetMinThickness(mm(min_w))
            z.SetPadConnection(k.ZONE_CONNECTION_FULL if solid else k.ZONE_CONNECTION_THERMAL)
            z.SetThermalReliefGap(mm(gap)); z.SetThermalReliefSpokeWidth(mm(spoke))
            z.SetIslandRemovalMode(k.ISLAND_REMOVAL_MODE_ALWAYS)
        self.b.Add(z)
        return z


def rpi_copper(c):
    """Raspberry Pi's copper round the chip, turned with it, less their switching regulator's: the
    rings under the chip (3.3 V outside, the core's 1.1 V inside it), each supply pin's track to its
    capacitor, the core supply's four tracks on the back, the crystal's corner."""
    def lx(t):                           # their regulator's corner, in their frame: above the chip's top edge, right of centre
        xs = [p[0] for p in t]; ys = [p[1] for p in t]
        return min(ys) < -2.0 and 0.3 < min(xs) and max(xs) < 4.5
    for t in RPI["tracks"]:
        if t["net"] not in RPI_NET or (t["net"] in ("/DVDD", "GND") and lx([t["a"], t["b"]])):
            continue
        if t["net"] == "+3V3" and min(t["a"][1], t["b"][1]) < -4.35 and -2.6 < min(t["a"][0], t["b"][0]) and max(t["a"][0], t["b"][0]) < 0.1:
            continue                     # their track from pins 53 and 54 out to their capacitor: C19 sits at the pins here
        c.track(RPI_NET[t["net"]], t["layer"][0], [u1(*t["a"]), u1(*t["b"])], t["w"])
    for v in RPI["vias"]:
        if v["net"] not in RPI_NET or (v["net"] == "/DVDD" and lx([v["at"]])) or tuple(v["at"]) == (3.85, -3.85):
            continue
        c.via(RPI_NET[v["net"]], *u1(*v["at"]))
    for z in RPI["zones"]:
        if z["net"] not in RPI_NET or (z["net"] == "/DVDD" and z["priority"] == 6):
            continue
        c.zone(RPI_NET[z["net"]], [z["layer"][0]], [u1(*p) for p in z["pts"]], prio=z["priority"], clearance=z["clearance"],
               min_w=z["min_width"], solid=z["solid"], gap=z["thermal"][0], spoke=z["thermal"][1])
    # What their board gets from its 3.3 V front pour, drawn here, where the front pour is ground:
    R = lambda *pts: [u1(*p) for p in pts]
    c.track(V33, "F", R((-3.45, -2.8), (-2.7, -2.8)), 0.2)                              # pin 1 into the ring
    c.track(V33, "F", R((-3.45, -2.8), (-5.2, -2.8), (-5.8, -3.4), (-6.01, -3.4)), 0.2)   # and out to its capacitor, C10
    c.track(V33, "F", R((3.45, -2.8), (2.7, -2.8)), 0.2)                                # pin 45 into the ring
    c.track(V33, "F", R((2.8, -3.45), (2.8, -2.7)), 0.2)                                # pin 46, VREG_AVDD, into the ring
    c.track(V33, "F", [u1(-0.4, -4.3), (AT["C19"][0] - 0.475, AT["C19"][1])], 0.2)             # pins 53 and 54 to C19
    # VREG_FB to ground (figure 24), by the way their track took it to the regulator's output
    c.track(GND, "F", R((1.2, -3.4375), (1.175, -3.4625), (1.175, -4.125), (0.925, -4.375), (0.925, -5.45)), 0.15)
    c.via(GND, *u1(0.925, -5.45))


class Wiring:
    """Lines drawn by name: a pad as 'U1.12' (its centre), a bend as (x, y)."""

    def __init__(self, b, c):
        import pcbnew
        self.c, self.pads = c, {}
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNumber():
                    self.pads.setdefault((fp.GetReference(), pad.GetNumber()),
                                         (round(pcbnew.ToMM(pad.GetPosition().x) - OX, 4), round(pcbnew.ToMM(pad.GetPosition().y) - OY, 4)))

    def at(self, spec):
        if isinstance(spec, str):
            ref, num = spec.split(".")
            return self.pads[ref, num]
        return spec

    def line(self, net, layer, pts, w=0.2):
        self.c.track(net, layer, [self.at(p) for p in pts], w)

    def via(self, net, x, y):
        self.c.via(net, x, y)


def wire(w):
    """Every track and via outside Raspberry Pi's block, drawn by hand: a pad by its name ('U1.12'),
    a bend by its place. KiCad's DRC is the check that none of it touches what it shouldn't.
    Three nets change sides once, each under lines they could not cross on top: D0 (GPIO2 is on the
    wrong side of the chip for the left button), the key's 3.3 V, and the screen's DC."""
    # --- the USB corner, by hand -------------------------------------------------------------------
    w.line("USB_D+", "F", ["J1.A6", jm(-0.25, -5.35), jm(0.75, -5.35), "J1.B6"], 0.2)
    w.line("USB_D+", "F", [jm(-0.25, -5.35), jm(-0.25, -5.6), jm(-0.95, -6.3), "U2.1"], 0.2)
    w.line("USB_D+", "F", ["U2.1", "U2.6"], 0.2)
    w.line("USB_D+", "F", ["U2.6", jm(-0.95, -11.0), jm(-0.25, -11.7), "U5.7"], 0.2)
    w.line("USB_D-", "F", ["J1.B7", jm(-0.75, -3.0), jm(-0.25, -2.5), jm(0.25, -3.0), "J1.A7"], 0.2)
    w.via("USB_D-", *jm(-0.25, -2.5))
    w.line("USB_D-", "B", [jm(-0.25, -2.5), jm(-0.25, -4.4), jm(0.95, -5.6), jm(0.95, -5.95)], 0.2)
    w.via("USB_D-", *jm(0.95, -5.95))
    w.line("USB_D-", "F", [jm(0.95, -5.95), "U2.3"], 0.2)
    w.line("USB_D-", "F", ["U2.3", "U2.4"], 0.2)
    w.line("USB_D-", "F", ["U2.4", jm(0.95, -11.0), jm(0.25, -11.7), "U5.8"], 0.2)
    w.line("GND", "F", ["U2.2", jm(0.0, -6.15)], 0.3)
    w.via("GND", *jm(0.0, -6.15))
    w.line("VBUS", "F", ["U2.5", jm(0.0, -10.6)], 0.3)
    w.via("VBUS", *jm(0.0, -10.6))
    w.line("CC1", "F", ["J1.A5", jm(-1.25, -5.0), jm(-1.99, -5.74), "R1.1"], 0.2)
    w.line("CC2", "F", ["J1.B5", jm(1.75, -5.0), jm(1.99, -5.74), "R2.1"], 0.2)
    w.line("VBUS", "F", ["J1.A4", jm(-2.45, -4.8), jm(-3.1, -5.45), jm(-3.1, -10.6)], 0.3)
    w.via("VBUS", *jm(-3.1, -10.6))
    w.line("VBUS", "F", ["J1.A9", jm(2.45, -4.8), jm(2.9, -5.25), jm(2.9, -10.6)], 0.3)
    w.via("VBUS", *jm(2.9, -10.6))
    w.line("VBUS", "B", [jm(-3.1, -10.6), jm(2.9, -10.6)], 0.3)
    w.line("VBUS", "F", [jm(2.9, -10.6), jm(2.9, -13.45), "U5.9"], 0.25)
    # the bridge
    w.line("CH_V3", "F", ["U5.6", (19.25, 73.75), (18.5, 74.5), "C6.1"], 0.2)
    w.line("GND", "F", ["U5.2", (18.8, 71.45)], 0.25)
    w.via("GND", 19.5, 71.7)
    w.via("VBUS", 16.85, 72.0)                                        # 5 V up from the bar on the back, to the bridge's VDD5
    w.line("VBUS", "B", [jm(-3.1, -10.6), (16.9, 72.05), (16.85, 72.0)], 0.3)
    w.line("VBUS", "F", ["C5.1", (16.85, 72.0), (17.6, 72.0), "U5.3"], 0.3)
    w.line("+3V3", "F", ["C7.1", (17.2, 70.52), (17.63, 70.95), "U5.1"], 0.25)
    # --- 3.3 V: the regulator, the trunk up the right of the bridge, the chip's VREG_VIN ---------------
    w.line("+3V3", "F", [(28.05, 77.6), (34.35, 77.6)], 0.6)
    w.line("+3V3", "F", [(28.05, 77.6), (25.6, 77.6)], 0.6)
    w.line("+3V3", "F", [(25.6, 77.35), (24.3, 77.35), (24.3, 53.0), (24.3, 52.5), (26.4, 50.4), (26.4, 48.6), (24.61, 48.6)], 0.4)
    w.line("+3V3", "F", [(24.3, 53.0), "C15.1"], 0.3)
    w.line("+3V3", "F", [(24.3, 59.6), (21.65, 59.6), "U4.1"], 0.3)
    w.line("+3V3", "F", [(23.55, 59.6), "U4.3"], 0.3)
    w.line("+3V3", "F", ["U4.1", "C3.1"], 0.3)
    w.line("+3V3", "F", [(24.3, 69.3), (17.08, 69.3), "C7.1"], 0.3)
    w.line("+3V3", "F", [(17.08, 69.3), (16.3, 69.3), (16.1, 69.1)], 0.3)
    w.via("+3V3", 16.1, 69.1)
    w.line("+3V3", "B", [(16.1, 69.1), (14.26, 69.1), "TP5.1"], 0.3)
    # --- 1.1 V ---------------------------------------------------------------------------------------
    w.line("+1V1", "F", ["U4.5", (21.65, 54.2), (21.05, 53.6), "C17.1"], 0.4)
    w.line("+1V1", "F", ["U4.5", "C4.1"], 0.4)
    w.via("+1V1", 21.65, 54.75)
    w.line("+1V1", "B", [(21.65, 54.75), "TP10.1"], 0.4)
    w.line("GND", "F", ["U4.2", (22.6, 57.0)], 0.3)
    w.via("GND", 22.6, 57.0)
    # --- VBUS: to the regulator, its test pad, and up the left edge to the backlight's switch ---------
    w.line("VBUS", "F", [jm(2.9, -6.05), (28.05, 79.85)], 0.4)
    w.line("VBUS", "F", [(26.2, 79.85), (26.2, 81.0)], 0.3)
    w.via("VBUS", 26.2, 81.0)
    w.line("VBUS", "B", [(26.2, 81.0), (26.2, 84.0), "TP11.1"], 0.3)
    w.line("VBUS", "F", [(16.9, 76.5), (4.0, 76.5), (4.0, 40.2), (4.9, 39.3), (4.9, 35.55), "Q1.2"], 0.25)   # under R11, between its pads
    w.line("VBUS", "F", [(4.9, 39.3), "R9.2"], 0.25)
    # the backlight's switch
    w.line("BL_GATE", "F", ["Q1.1", (9.3375, 38.87), "R9.1"], 0.2)
    w.line("BL_GATE", "F", ["R9.1", (9.61, 40.0), "Q2.3"], 0.2)
    w.line("BL_SW", "F", ["Q1.3", "R11.1"], 0.25)
    w.line("LCD_BL", "F", ["U1.17", (15.83, 44.6), (12.38, 41.15), "Q2.1"], 0.2)
    w.line("LCD_BL", "F", ["Q2.1", (12.2375, 41.67), "R10.1"], 0.2)
    w.line("GND", "F", ["Q2.2", (12.2375, 38.0)], 0.25)
    w.via("GND", 12.2375, 38.0)
    w.line("LCD_LEDA", "F", ["R11.2", (4.075, 29.8), (6.8, 27.075), (6.8, 19.6), (14.1, 12.3), (14.3, 12.3), (15.05, 11.55), "J2.1"], 0.25)
    w.line("GND", "F", ["J2.2", (14.6, 11.05)], 0.2)
    w.via("GND", 14.6, 11.05)
    # --- the chip's top side: buttons, the key's bus, the screen's lines ------------------------------
    w.line("BTN_D0", "F", ["U1.4", (21.6, 43.0), (22.2, 42.4)], 0.2)
    w.via("BTN_D0", 22.2, 42.4)
    w.line("BTN_D0", "B", [(22.2, 42.4), (22.2, 40.8), (12.3, 30.9), (12.3, 28.3)], 0.2)
    w.via("BTN_D0", 12.3, 28.3)
    w.line("BTN_D0", "F", [(12.3, 28.3), (11.875, 27.875), (11.875, 21.0)], 0.2)
    w.line("BTN_D1", "F", ["U1.5", (21.2, 42.4), (21.6, 42.0), (21.6, 40.0), (22.3, 39.3), (22.3, 28.3), (21.875, 27.875), (21.875, 21.0)], 0.2)
    w.line("SDA", "F", ["U1.7", (20.4, 37.9), (20.87, 37.43), (20.87, 32.6), (21.505, 31.965), "U6.5"], 0.2)
    w.line("SDA", "F", ["U6.5", (21.505, 28.795), "R7.1"], 0.2)
    w.line("SCL", "F", ["U1.8", (20.0, 37.5), (19.6, 37.1), (19.6, 32.6), (20.235, 31.965), "U6.6"], 0.2)
    w.line("SCL", "F", ["U6.6", (20.235, 30.02), "R8.1"], 0.2)
    w.line("BTN_D2", "F", ["U1.9", (19.6, 38.2), (19.4, 38.0), (17.55, 38.0), (16.15, 36.6), (16.15, 20.0), (16.55, 19.6), (27.7, 19.6), (28.125, 20.025), (28.125, 27.0)], 0.2)
    w.line("+3V3", "F", ["C11.1", (19.0, 40.99), (19.2, 40.79), (19.2, 38.65), (19.0, 38.45), (17.4, 38.45), (15.7, 36.75), (15.7, 17.8), (19.6, 13.9), (19.6, 6.3), (15.2, 6.3), (14.38, 7.12), "C25.1"], 0.25)
    w.line("+3V3", "F", ["C25.1", "C26.1"], 0.25)
    w.line("+3V3", "F", ["C26.1", "J2.7"], 0.2)
    w.via("GND", 18.6, 39.15)
    w.line("GND", "F", ["C11.2", (18.6, 39.15)], 0.25)
    w.via("GND", 21.5, 38.0)
    w.line("LCD_DC", "F", ["U1.12", (18.4, 42.4), (15.25, 39.25), (15.25, 17.4), (18.6, 14.05)], 0.2)
    w.via("LCD_DC", 18.6, 14.05)
    w.line("LCD_DC", "B", [(18.6, 14.05), (14.9, 10.35), (14.9, 10.05)], 0.2)
    w.via("LCD_DC", 14.9, 10.05)
    w.line("LCD_DC", "F", [(14.9, 10.05), "J2.4"], 0.2)
    w.line("LCD_CS", "F", ["U1.13", (18.0, 42.57), (14.8, 39.37), (14.8, 17.3)], 0.2)
    w.line("LCD_CS", "F", [(14.8, 17.3), (18.0, 14.1), (18.0, 8.05), "J2.8"], 0.15)
    w.line("LCD_SCK", "F", ["U1.14", (17.6, 42.73), (14.3, 39.43), (14.3, 17.3)], 0.2)
    w.line("LCD_SCK", "F", [(14.3, 17.3), (17.65, 13.95), (17.65, 9.05), "J2.6"], 0.15)
    w.line("LCD_MOSI", "F", ["U1.15", (17.2, 42.9), (13.8, 39.5), (13.8, 17.3)], 0.2)
    w.line("LCD_MOSI", "F", [(13.8, 17.3), (17.3, 13.8), (17.3, 9.55), "J2.5"], 0.15)
    w.line("LCD_RST", "F", ["U1.16", (16.0, 44.2), (13.4, 41.6), (13.4, 17.2)], 0.2)
    w.line("LCD_RST", "F", [(13.4, 17.2), (16.95, 13.65), (16.95, 10.55), "J2.3"], 0.15)
    # the key's supply: from the flash's, under D1 on the back
    w.line("+3V3", "F", ["C10.1", (24.05, 40.99), (24.05, 36.4), (24.6, 35.85), (24.995, 35.85)], 0.3)
    w.line("+3V3", "F", ["C23.1", (23.67, 36.4), (24.05, 36.4)], 0.3)
    w.line("+3V3", "F", ["U7.8", (24.995, 33.7)], 0.3)
    w.via("+3V3", 24.995, 33.7)
    w.line("+3V3", "B", [(24.995, 33.7), (24.3, 33.7), (18.9, 28.3)], 0.3)
    w.via("+3V3", 18.9, 28.3)
    w.line("+3V3", "F", [(18.9, 28.3), "R7.2"], 0.25)
    w.line("+3V3", "F", [(18.9, 28.3), (18.59, 28.61), "R8.2"], 0.25)
    w.line("+3V3", "F", ["R8.2", "C24.1"], 0.25)
    w.line("+3V3", "F", ["C24.1", "U6.8"], 0.25)
    # --- the flash -----------------------------------------------------------------------------------
    w.line("QSPI_SS", "F", ["U1.60", (24.4, 44.2), (24.995, 43.605), "U7.1"], 0.2)
    w.line("QSPI_SD1", "F", ["U1.59", (25.8, 44.6), (26.265, 44.135), "U7.2"], 0.2)
    w.line("QSPI_SD2", "F", ["U1.58", (27.1, 45.0), (27.535, 44.565), "U7.3"], 0.2)
    w.line("QSPI_SD0", "F", ["U1.57", (29.4, 45.4), (29.8, 45.0), (29.8, 35.812), (29.4, 35.412), "U7.5"], 0.2)
    w.line("QSPI_SCLK", "F", ["U1.56", (29.9, 45.8), (30.3, 45.4), (30.3, 34.4), (29.9, 34.0), (27.935, 34.0), (27.535, 34.4), "U7.6"], 0.2)
    w.line("QSPI_SD3", "F", ["U1.55", (30.4, 46.2), (30.8, 45.8), (30.8, 33.9), (30.4, 33.5), (26.665, 33.5), (26.265, 33.9), "U7.7"], 0.2)
    w.line("GND", "F", ["U7.4", (28.805, 44.2)], 0.3)
    w.via("GND", 28.805, 44.2)
    # --- the chip's left and bottom: debug, reset, the link, the LED ----------------------------------
    w.line("SWCLK", "F", ["U1.24", (15.4, 47.4), (14.75, 48.05), (14.75, 55.6), (13.85, 56.5), "J3.1"], 0.15)
    w.via("SWCLK", 9.5, 56.5)
    w.line("SWCLK", "B", [(9.5, 56.5), (3.0, 63.0), "TP1.1"], 0.2)
    w.line("SWDIO", "F", ["U1.25", (15.5, 47.8), (15.1, 48.2), (15.1, 57.6), (14.2, 58.5), "J3.3"], 0.15)
    w.via("SWDIO", 10.3, 58.5)
    w.line("SWDIO", "B", [(10.3, 58.5), (8.08, 60.72), "TP3.1"], 0.2)
    w.line("RUN", "F", ["U1.26", (15.6, 48.2), (15.45, 48.35), (15.45, 59.2), (10.62, 64.03), "TP4.1"], 0.15)
    w.via("RUN", 10.62, 68.0)
    w.via("GND", 7.5, 57.5)
    w.line("GND", "F", ["J3.2", (7.5, 57.5)], 0.25)
    w.line("LINK_TX", "F", ["U1.32", (17.6, 51.4), (16.9, 52.1), (16.9, 59.9), "TP12.1", (14.15, 65.75), (14.15, 73.6), (14.55, 74.0), (18.45, 74.0), (18.75, 73.7), "U5.5"], 0.2)
    w.via("LINK_TX", 12.6, 64.2)
    w.line("LINK_RX", "F", ["U1.33", (18.0, 51.8), (17.3, 52.5), (17.3, 62.7), "TP13.1", (14.55, 65.45), (14.55, 72.6), (14.95, 73.0), (17.2, 73.0), (17.75, 72.45), "U5.4"], 0.2)
    w.via("LINK_RX", 15.8, 64.2)
    w.line("LED", "F", ["U1.37", (19.6, 51.5), (18.6, 52.5), (18.6, 61.59), "D1.2"], 0.2)
    w.line("LED_K", "F", ["D1.1", "R12.1"], 0.2)
    # ground where the front pour can't reach a pad from two sides
    w.line("GND", "F", ["C16.2", (21.0, 39.0), (21.5, 38.5), (21.5, 38.0)], 0.25)
    w.line("GND", "F", ["C14.2", "C17.2"], 0.25)
    w.line("GND", "F", ["C14.2", (19.9, 54.86), (19.9, 55.3)], 0.25)
    w.via("GND", 19.9, 55.3)
    w.line("GND", "F", ["R1.2", (17.8, 77.8), "C6.2"], 0.25)
    w.via("GND", 17.8, 77.8)
    w.line("GND", "F", ["C5.2", (15.12, 70.9)], 0.25)
    w.via("GND", 15.12, 70.9)
    w.line("GND", "F", ["R2.2", (22.2, 77.8)], 0.25)
    w.via("GND", 22.2, 77.8)
    w.line("GND", "F", ["C10.2", (23.4, 38.6)], 0.25)
    w.via("GND", 23.4, 38.6)


# The link's rules, as exact sets: what each of these nets may reach, and nothing else.
LINK_RULES = [
    ("USB_D+", {"J1", "U2", "U5"}), ("USB_D-", {"J1", "U2", "U5"}),
    ("LINK_TX", {"U1", "U5", "TP12"}), ("LINK_RX", {"U1", "U5", "TP13"}),
    ("SWCLK", {"U1", "J3", "TP1"}), ("SWDIO", {"U1", "J3", "TP3"}), ("RUN", {"U1", "TP4"}),
    ("SDA", {"U1", "U6", "R7"}), ("SCL", {"U1", "U6", "R8"}),
    ("QSPI_SS", {"U1", "U7"}),
]


def check_link():
    bad = []
    want = table_nets()
    for net, refs in LINK_RULES:
        got = {r for r, _p in want.get("/" + net, set())}
        if got != refs:
            bad.append(f"{net} reaches {sorted(got)}, the rule says {sorted(refs)}")
    u5 = BY_REF["U5"]["nets"]
    for pin, what in (("12", "DTR"), ("13", "RTS"), ("10", "ACT"), ("11", "DCD"), ("14", "DSR"), ("15", "CTS"), ("16", "RI")):
        if pin in u5:
            bad.append(f"the CH343P's {what} (pin {pin}) is connected to {u5[pin]}; it must reach nothing")
    for pin, what in (("51", "USB_DM"), ("52", "USB_DP")):       # the chip's own USB reaches nothing at all
        if pin in BY_REF["U1"]["nets"]:
            bad.append(f"U1's {what} (pin {pin}) is connected to {BY_REF['U1']['nets'][pin]}; it must reach nothing")
    # nothing but power joins the USB-C to the chip
    j1 = {n for n in BY_REF["J1"]["nets"].values()} - set(POWER)
    u1 = {n for n in BY_REF["U1"]["nets"].values()} - set(POWER)
    if j1 & u1:
        bad.append(f"the USB-C and the RP2350 share {sorted(j1 & u1)}")
    return bad


def stitch(b, c):
    """Ground vias joining the two pours: on a 4 mm grid, the rows staggered, wherever one fits 0.5 mm
    clear of every other net's copper, and clear of every pad, courtyard, other via, hole and the edge."""
    import pcbnew
    r = VIA[0] / 2

    def box(bb, grow):
        return (pcbnew.ToMM(bb.GetLeft()) - OX - grow, pcbnew.ToMM(bb.GetTop()) - OY - grow,
                pcbnew.ToMM(bb.GetRight()) - OX + grow, pcbnew.ToMM(bb.GetBottom()) - OY + grow)
    boxes = []                                                  # nothing of the via's centre in any of these
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            boxes.append(box(pad.GetBoundingBox(), r + 0.3))
        for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            if fp.GetCourtyard(lay).OutlineCount():
                boxes.append(box(fp.GetCourtyard(lay).BBox(), r + 0.2))
    for z in RPI["zones"]:                                      # Raspberry Pi's rings and corners
        xs, ys = zip(*[u1(*p) for p in z["pts"]])
        boxes.append((min(xs) - r - 0.5, min(ys) - r - 0.5, max(xs) + r + 0.5, max(ys) + r + 0.5))
    rounds = [(x, y, HOLE_RING + r + 0.2) for ref, (x, y, _r) in AT.items() if ref.startswith("H")]
    rounds += [(x, y, 1.5) for _n, x, y in c.vias]
    segs = [(a, z, w / 2 + r + 0.5) for net, _l, pts, w in c.tracks if net != GND for a, z in zip(pts, pts[1:])]

    def seg_d2(p, a, z):
        (px, py), (ax, ay), (zx, zy) = p, a, z
        dx, dy = zx - ax, zy - ay
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2

    def fits(x, y):
        return (not any(x0 < x < x1 and y0 < y < y1 for x0, y0, x1, y1 in boxes)
                and not any((x - cx) ** 2 + (y - cy) ** 2 < d * d for cx, cy, d in rounds)
                and not any(seg_d2((x, y), a, z) < d * d for a, z, d in segs))
    n = 0
    for j_ in range(int((H - 5.0) / 4.0) + 1):
        for i_ in range(int((W - 5.0) / 4.0) + 1):
            x, y = 3.0 + 4.0 * i_ + (2.0 if j_ % 2 else 0.0), 3.0 + 4.0 * j_
            if x <= W - 2.5 and fits(x, y):
                c.via(GND, x, y)
                rounds.append((x, y, 1.5))
                n += 1
    return n


def keepouts(c):
    """Where nobody should draw a track or a via later: round each M2 hole, under a screw's head."""
    for ref, (x, y, _r) in AT.items():
        if ref.startswith("H"):
            c.zone(None, ["F", "B"], [(x + HOLE_RING * math.cos(a * math.pi / 16), y + HOLE_RING * math.sin(a * math.pi / 16)) for a in range(32)],
                   rule=f"{ref}: a screw's head and a post")


WARN_TEXT = "EXPERIMENTAL HARDWARE COSIGNER"
TP_LABEL = {"TP1": "SWCLK", "TP2": "GND", "TP3": "SWDIO", "TP4": "RUN", "TP5": "3V3", "TP9": "GND",
            "TP10": "1V1", "TP11": "VBUS", "TP12": "TX", "TP13": "RX"}


def texts(b):
    """The silkscreen, 1.0 mm high at least (JLCPCB's least), and the panel's place on the drawing layers."""
    import pcbnew

    def text(s_, x, y, size=1.0, layer=pcbnew.F_SilkS, wide=None, rot_=0):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s_); t.SetPosition(P(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(wide or size), mm(size))); t.SetTextThickness(mm(max(0.15, size * 0.15)))
        t.SetTextAngleDegrees(rot_)
        if layer in (pcbnew.B_SilkS, pcbnew.B_Fab):
            t.SetMirrored(True)
        b.Add(t)

    def line(a, z, layer, wd=0.15):
        s_ = pcbnew.PCB_SHAPE(b)
        s_.SetShape(pcbnew.SHAPE_T_SEGMENT); s_.SetStart(P(*a)); s_.SetEnd(P(*z)); s_.SetLayer(layer); s_.SetWidth(mm(wd))
        b.Add(s_)

    def rect(x0, y0, x1, y1, layer, wd=0.1):
        for a, z in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            line(a, z, layer, wd)
    # the front: the buttons' names above them, the debug socket's, and four corners to lay the glass to
    for i in range(3):
        text(f"D{i}", AT[f"SW{i + 1}"][0], BY - 4.6, 1.0)
    text("SWD", 4.2, 52.9, 1.0)
    for cx, sx in ((GX0, 1), (GX1, -1)):
        for cy, sy in ((GY0, 1), (GY1, -1)):
            line((cx, cy), (cx + 2.0 * sx, cy), pcbnew.F_SilkS)
            line((cx, cy), (cx, cy + 2.0 * sy), pcbnew.F_SilkS)
    rect(GX0, GY0, GX1, GY1, pcbnew.F_Fab)                                  # the glass
    ax0 = XA - PANEL["active"][0] / 2
    rect(ax0, YC - PANEL["active"][1] / 2, ax0 + PANEL["active"][0], YC + PANEL["active"][1] / 2, pcbnew.Cmts_User)   # the picture
    text("the panel on tape; its ribbon folds under into J2", XC, GY1 - 1.2, 0.8, pcbnew.F_Fab)
    # the back: what the board is, what is not on it, and each pad's name
    B = pcbnew.B_SilkS
    text(WARN_TEXT, XA, 2.2, 1.0, B, wide=0.85)
    for i, s_ in enumerate(("nothing is fitted on this side", "no radio: USB serial only",
                            f"Picoquorum tally rev {REV} {DATE}")):
        text(s_, XA, 5.0 + 2.0 * i, 1.0, B, wide=0.85)
    text("picoquorum.app", XA, 12.4, 1.4, B)                                 # also the Source Location
    text("CERN-OHL-W v2, Source Location as 4.1", XA, 14.8, 1.0, B, wide=0.8)
    for ref, lab in TP_LABEL.items():
        x, y, _r = AT[ref]
        if ref in TP_X:
            text(lab, x, y + (-1.9 if list(TP_X).index(ref) % 2 == 0 else 1.9), 1.0, B, wide=0.7)
        else:
            text(lab, x + (2.6 if ref in ("TP10", "TP11", "TP13") else -2.4), y, 1.0, B, wide=0.7)
    text("pads: SWD, reset, the rails, the link", XA, 71.6, 1.0, B, wide=0.8)


def build_board(nets, path):
    """The whole board: placed, wired, stitched, poured, saved, read back, filled and checked.
    Returns KiCad's DRC counts: (violations by kind, unconnected, ground vias)."""
    import pcbnew
    pcbnew.KIID.SeedGenerator(20261113)       # the same file from the same script
    b = place_board(nets)
    outline(b)
    c = Copper(b)
    rpi_copper(c)
    wire(Wiring(b, c))
    n_st = stitch(b, c)
    keepouts(c)
    for l in ("F", "B"):
        c.zone(GND, [l], [(0, 0), (W, 0), (W, H), (0, H)])
    texts(b)
    tb = b.GetTitleBlock()
    tb.SetTitle("Picoquorum tally"); tb.SetRevision(REV); tb.SetDate(DATE); tb.SetCompany("picoquorum.app")
    pcbnew.SaveBoard(path, b, True)
    b = pcbnew.LoadBoard(path)                # a board built in memory can't be filled (KiCad 7): read it back
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b, True)
    return (*drc(path), n_st)


def drc(path):
    """KiCad's own DRC on the board file, with the project's rules: ({kind: count}, unconnected)."""
    import pcbnew
    b = pcbnew.LoadBoard(path)
    with tempfile.TemporaryDirectory() as t:
        rpt = os.path.join(t, "drc.rpt")
        pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
        txt = open(rpt).read()
    kinds = {}
    head = txt.split("** Found", 2)
    body = txt[txt.index("** Found"):]
    viol, rest = body.split("** Found", 2)[1], body.split("** Found", 2)[2] if body.count("** Found") > 1 else ""
    for k in re.findall(r"^\[(\w+)\]", viol, re.M):
        kinds[k] = kinds.get(k, 0) + 1
    unconnected = len(re.findall(r"^\[unconnected_items\]", rest, re.M))
    return kinds, unconnected


def check_board(path, nets):
    """The board file against the table: each pad on its net, each part at its place, nothing else there."""
    import pcbnew
    bad = []
    b = pcbnew.LoadBoard(path)
    want = {(r_, p_): n for n, pins in nets.items() for r_, p_ in pins}
    seen = set()
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        seen.add(ref)
        if ref not in BY_REF:
            bad.append(f"the board has {ref}, the table doesn't")
            continue
        x, y, r = AT[ref]
        px, py = pcbnew.ToMM(fp.GetPosition().x) - OX, pcbnew.ToMM(fp.GetPosition().y) - OY
        if abs(px - x) > 1e-4 or abs(py - y) > 1e-4 or abs((fp.GetOrientationDegrees() - r + 180) % 360 - 180) > 1e-6:
            bad.append(f"{ref} is at ({px:.3f}, {py:.3f}, {fp.GetOrientationDegrees():g}), the script says ({x}, {y}, {r})")
        if (fp.GetLayer() == pcbnew.B_Cu) != (ref in BACK):
            bad.append(f"{ref} is on the wrong side")
        for pad in fp.Pads():
            if pad.GetNumber() and pad.GetNetname() != want.get((ref, pad.GetNumber())):
                bad.append(f"{ref}.{pad.GetNumber()} is on {pad.GetNetname()!r}, the schematic says {want.get((ref, pad.GetNumber()))!r}")
    bad += [f"{r_} is not on the board" for r_ in sorted(set(BY_REF) - seen)]
    front = [fp.GetReference() for fp in b.GetFootprints() if fp.GetLayer() == pcbnew.B_Cu and BY_REF.get(fp.GetReference(), {}).get("lcsc")]
    if front:
        bad.append(f"parts for JLCPCB on the back: {front}; Economic assembly fits one side")
    return bad


# --- what goes to JLCPCB ------------------------------------------------------------------------
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"      # tools/keypcb's, by KiCad 7's names
FAB = os.path.join(OUT, "fab")              # where `tools/keypcb fab tally` writes too


def fitted():
    return [p for p in PARTS if p.get("lcsc") and not p.get("dnp")]


def write_bom(path):
    """JLCPCB's BOM, as tools/keypcb writes it: Comment, Designator, Footprint, LCSC Part #."""
    rows = {}
    for p in fitted():
        rows.setdefault((p["value"], p["fp"], p["lcsc"]), []).append(p["ref"])
    nat = lambda r_: (re.sub(r"\d", "", r_), int(re.sub(r"\D", "", r_)))
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (value, fp, lcsc), refs in sorted(rows.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
            wr.writerow([value, ",".join(sorted(refs, key=nat)), fp, lcsc])


def write_fab(pcb):
    """The Gerbers and drill files zipped, the BOM and the CPL, every one measured from the board's
    bottom-left corner, with tools/keypcb's own options. JLCPCB's rotation for a part can differ from
    KiCad's: no offsets are applied here, and their placement preview is where that is looked at."""
    os.makedirs(FAB, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        g = os.path.join(t, "g")
        os.makedirs(g)
        run = lambda *a: subprocess.run([CLI, *a], check=True, capture_output=True, text=True, env=kicad_env())
        run("pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "--use-drill-file-origin", "-o", g + "/", pcb)
        run("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--drill-origin", "plot", "-o", g + "/", pcb)
        z = os.path.join(FAB, NAME + "-gerbers.zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(os.listdir(g)):
                if p.endswith(".gbrjob"):
                    continue
                data = open(os.path.join(g, p), "rb").read()
                data = re.sub(rb"(%TF\.CreationDate,|G04 Created by KiCad[^\n]*date |; DRILL file \{[^}]*\} date )[^*\n]*", rb"\g<1>" + DATE.encode(), data)
                info = zipfile.ZipInfo(p, date_time=(2026, 1, 1, 0, 0, 0))      # the same bytes on every run
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
        pos = os.path.join(t, "pos.csv")
        run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--use-drill-file-origin", "-o", pos, pcb)
        rows = {r_["Ref"]: r_ for r_ in csv.DictReader(open(pos))}
    write_bom(os.path.join(FAB, "bom.csv"))
    with open(os.path.join(FAB, "cpl.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in fitted():
            r_ = rows[p["ref"]]
            wr.writerow([p["ref"], f'{float(r_["PosX"]):.4f}mm', f'{float(r_["PosY"]):.4f}mm', "Top" if r_["Side"] == "top" else "Bottom",
                         f'{float(r_["Rot"]) % 360:.0f}'])
    return len(zipfile.ZipFile(z).namelist())


def check_fab(pcb):
    """fab/ is this board's: the BOM is the table's, and each CPL row is its part's place."""
    bad = []
    with tempfile.TemporaryDirectory() as t:
        write_bom(os.path.join(t, "bom.csv"))
        if not os.path.exists(os.path.join(FAB, "bom.csv")) or open(os.path.join(FAB, "bom.csv")).read() != open(os.path.join(t, "bom.csv")).read():
            bad.append("fab/bom.csv is not the table's")
    try:
        rows = {r_["Designator"]: r_ for r_ in csv.DictReader(open(os.path.join(FAB, "cpl.csv")))}
    except FileNotFoundError:
        return bad + ["fab/cpl.csv is missing"]
    if set(rows) != {p["ref"] for p in fitted()}:
        bad.append(f"fab/cpl.csv has other parts than the BOM: {sorted(set(rows) ^ {p['ref'] for p in fitted()})}")
    for ref, r_ in rows.items():
        x, y, rot_ = AT[ref]
        if abs(float(r_["Mid X"][:-2]) - x) > 1e-3 or abs(float(r_["Mid Y"][:-2]) - (H - y)) > 1e-3 or r_["Layer"] != "Top":
            bad.append(f"fab/cpl.csv: {ref} at {r_['Mid X']}, {r_['Mid Y']}, {r_['Layer']}; the board has it at {x}, {H - y:g} from the bottom-left, on top")
        if abs((float(r_["Rotation"]) - rot_ + 180) % 360 - 180) > 0.5:
            bad.append(f"fab/cpl.csv: {ref} turned {r_['Rotation']}, the board has {rot_}")
    if not os.path.exists(os.path.join(FAB, NAME + "-gerbers.zip")):
        bad.append("fab/tally-gerbers.zip is missing")
    return bad


WHAT = {"BTN_D0": "D0, to GND: pull-up inside, pressed low", "BTN_D1": "D1, to GND: pull-up inside, pressed low",
        "BTN_D2": "D2, to GND: pull-up inside, pressed low", "SDA": "I2C0 SDA, the key's bus, 4.7k to 3.3 V",
        "SCL": "I2C0 SCL, the key's bus, 4.7k to 3.3 V", "LED": "red LED, high is on",
        "LINK_TX": "UART1 TX to the CH343P's RXD", "LINK_RX": "UART1 RX from the CH343P's TXD",
        "LCD_MOSI": "SPI1 TX, the screen's SDA", "LCD_SCK": "SPI1 SCK, the screen's SCL", "LCD_DC": "the screen's RS",
        "LCD_RST": "the screen's RESET", "LCD_CS": "the screen's CS", "LCD_BL": "backlight, high is on; 4.7k down"}


def write_pins():
    lines = ["# Tally: the RP2350's pins", "", "*Written by `gen_tally.py`; don't edit by hand.*", "",
             "console-rp's and Mono's pins, so one board profile can serve all three.", "",
             "| GPIO | RP2350A pin | net | what |", "|---|---|---|---|"]
    for net, gp in sorted(GPIO.items(), key=lambda kv: kv[1]):
        lines.append(f"| {gp} | {GPIO_PIN[gp]} | `{net}` | {WHAT[net]} |")
    used = set(GPIO.values())
    free = [g_ for g_ in range(30) if g_ not in used]
    lines += ["", "Also: QSPI to the flash (pins 55 to 60), XIN and XOUT to the crystal, and on the back's pads and J3:",
              "SWCLK, SWDIO and RUN. The chip's own USB (pins 51 and 52) reaches nothing.",
              f"Not connected: GPIO {', '.join(str(g_) for g_ in free)}.", ""]
    open(os.path.join(HERE, "PINS.md"), "w").write("\n".join(lines))


HEIGHT = {"C_0402_1005Metric": 0.55, "R_0402_1005Metric": 0.4, "RPi_C_0402": 0.55, "RPi_C_0402_wide": 0.55, "RPi_R_0402": 0.4,
          "C_0805_2012Metric": 1.25, "R_0603_1608Metric": 0.55, "LED_0603_1608Metric": 0.8, "SOT-23": 1.15, "SOT-23-5": 1.45, "SOT-23-6": 1.45,
          "SOT-223-3_TabPin2": 1.8, "RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias": 0.85,
          "WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm": 0.75, "SOIC-8_3.9x4.9mm_P1.27mm": 1.75, "SOIC-8_5.3x5.3mm_P1.27mm": 2.16,
          "RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm": 0.8, "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB": 1.0,
          "SW_Push_1P1T_XKB_TS-1187A": 1.5, "USB_C_Receptacle_HRO_TYPE-C-31-M-12": 3.2,
          "JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal": 2.95}


def jlc_spec():
    """The board's numbers for tools/jlc (`tools/keypcb jlc tally`), by Mono's keys: the holes' rings,
    the vias that sit in pads, the regulator's heat, the nets whose return path to report, and the
    3D fit of the panel. Not run here: tools/keypcb wants KiCad 10."""
    up = lambda y: round(H - y, 4)
    rib = PANEL["ribbon"] / 2
    return {
        "edge": 0.3,
        "hole_ring": HOLE_RING,
        "via_in_pad": [{"pad": "U5.17", "why": "the CH343P's exposed pad and pin 2, shut in by its other pins, have no other way to ground: one via in the exposed pad"}],
        "thermal_vias": [{"pad": "U1.61", "why": "Raspberry Pi's nine 0.3 mm holes in the RP2350's exposed pad, 0.6 mm across like our vias"}],
        "jlc_allow": [{"type": "footprint_type_mismatch", "ref": "U1", "why": "Raspberry Pi's footprint: an SMD part with plated holes in its exposed pad"}],
        "regulator": {"ref": "U3", "part": "LDL1117S33R", "vin": 5.0, "vout": 3.3, "amps": [0.06, 0.15], "theta_ja": 120,
                      "theta_note": "ST's datasheet (DocID030319): 120 C/W in SOT-223 on its test board's copper"},
        "return_nets": ["/USB_D+", "/USB_D-", "/LCD_SCK", "/LCD_MOSI", "/LCD_CS", "/LCD_DC", "/XIN", "/XOUT", "/SWCLK", "/SWDIO",
                        "/LINK_TX", "/LINK_RX", "/QSPI_SCLK", "/QSPI_SD0", "/QSPI_SD1", "/QSPI_SD2", "/QSPI_SD3", "/QSPI_SS"],
        "fit": {
            "heights": HEIGHT, "default_height": 1.0,
            "solids": [{"name": "glass", "box": [GX0, up(GY1), GX1, up(GY0)], "z": [PANEL["foam"], PANEL["foam"] + PANEL["thick"]],
                        "note": f"on {PANEL['foam']} mm foam, {PANEL['thick']} thick: EastRising's drawing, not measured"}],
            "ribbon_run": [AT["J2"][0], up(YC + rib), GX1, up(YC - rib)],
            "selftest_tall": "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB",
        },
    }


def main(argv):
    global SYMBOLS
    if argv[:1] == ["import"]:          # once: the stock symbols and every footprint into lib/
        SYMBOLS = symbols(fresh=True)
        write_symbols()
        import_footprints(argv[1])
        print(f"{NAME}: lib/ written: {len(SYMBOLS)} symbols, {len(os.listdir(PRETTY))} footprints")
        return 0
    SYMBOLS = symbols()
    check_only = "check" in argv
    pcb = os.path.join(OUT, NAME + ".kicad_pcb")
    problems = check_table() + check_link()
    if not check_only:
        write_symbols()
        write_schematic()
    nets, comps = netlist()
    problems += check_netlist(nets, comps)
    if not check_only:
        write_project()
        kinds, loose, n_st = build_board(nets, pcb)
        n_files = write_fab(pcb)
        write_pins()
    else:
        kinds, loose = drc(pcb)
    problems += check_board(pcb, nets) + check_fab(pcb)
    problems += [f"DRC: {n} {k}" for k, n in sorted(kinds.items())] + ([f"DRC: {loose} unconnected"] if loose else [])
    n_fit = len(fitted())
    print(f"{NAME}: {len(PARTS)} parts, {n_fit} fitted by JLCPCB ({len({p['lcsc'] for p in fitted()})} kinds), {len(table_nets())} nets; "
          f"{W:g} x {H:g} mm, 2 layers")
    if not check_only:
        print(f"  wrote the schematic, the board ({n_st} ground vias stitched), fab/ ({n_files} files zipped, bom.csv, cpl.csv) and PINS.md")
    print(f"  KiCad's netlist of the schematic {'matches' if not problems else 'or the board DIFFERS from'} the table; "
          f"KiCad's DRC: {sum(kinds.values())} violations, {loose} unconnected")
    for p in problems:
        print("  PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
