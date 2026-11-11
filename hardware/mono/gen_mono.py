#!/usr/bin/env python3
"""Mono: a slender console on one board with no radio at all. A 40 x 89.5 mm bar (2.24:1): the 1.14"
screen near the top, three buttons under it, and a plain field below. An RP2350A and its flash, the
ATECC608C soldered on, a second key site under D0 on a bus of its own, and a USB-C on the bottom end,
left of centre, whose only data path is a CH343P serial bridge to the RP2350's UART1. The jig's pads
are on the back. See README.md.

    tools/keypcb gen-mono [render]         writes the project, the board placed, not routed
    tools/keypcb route mono                routes it (Freerouting)
    tools/keypcb gen-mono tidy [render]    after the route: the route-only keep-outs off, then checks it
    tools/keypcb gen-mono check [render]   checks the routed board, writing nothing but renders
        (KiCad 10: kicad-cli, its Python with pcbnew, its stock libraries and, to render, its 3D
        models; on Linux the system Python's pcbnew)

Writes, from the one table below:
  mono/mono.kicad_sch   the schematic, every part a stock KiCad symbol but two (lib/mono.kicad_sym)
  mono/mono.kicad_pcb   the board, every part placed, the copper round the RP2350 copied from
                        Raspberry Pi's minimal board (rpi_minimal.json), turned with the chip; the rest
                        left to the router
  mono/mono.kicad_pro   the project, with JLCPCB's limits as its rules
  lib/                  the symbols for the second key site's switch and Trust M; Raspberry Pi's
                        footprints (console-rp's copy), console-s3's ZIF, the panel's footprint, 3D
                        boxes for both, and the mark
  fab/bom.csv           JLCPCB's BOM format: Comment, Designator, Footprint, LCSC Part #
  PINS.md               the RP2350's pins, as the firmware sees them
  renders/              with "render": KiCad's 3D view of the board, the panel on it

Then has KiCad read the schematic back (kicad-cli netlist and ERC) and checks every connection
against the table, every symbol pin against its footprint's pads, the screen's and key's pins
against firmware/board.py's Pico pins, each GPIO against the RP2350's function table, and the link's
and the key site's wiring rules; and runs KiCad's DRC on the placed board, and checks what sits
under the panel's glass. It stops on any difference.

It won't rewrite a routed board: the schematic's new uuids would no longer match it. Once the
schematic or the board is edited in KiCad, KiCad's files are the source and this script only checks.
"""
import csv, json, math, os, re, shutil, subprocess, sys, tempfile, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
NAME = "mono"
OUT = os.path.join(HERE, NAME)
APP = "/Applications/KiCad/KiCad.app/Contents"       # macOS keeps KiCad's libraries in the app
SHARE = os.path.join(APP, "SharedSupport") if os.path.isdir(APP) else "/usr/share/kicad"
KISYM, KIFP, KI3D, KITPL = (os.path.join(SHARE, d) for d in ("symbols", "footprints", "3dmodels", "template"))
CLI = shutil.which("kicad-cli") or os.path.join(APP, "MacOS", "kicad-cli")
DATE, REV = "2026-11-06", "A"
CONSOLE_RP = os.path.join(REPO, "hardware", "console-rp")    # Raspberry Pi's footprints, as console-rp copied them
sys.path.insert(0, os.path.join(REPO, "hardware", "key-pcb"))
import gen        # noqa: E402  JLC_RULES, box_symbol

GND, V33, VBUS = "GND", "+3V3", "VBUS"
POWER = (GND, V33, VBUS)

# =================================================================================================
# The one table: every part, its LCSC number and what each of its pins connects to. A pin not listed
# is not connected, on purpose, and gets a no-connect flag. Nets other than the three power nets are
# local labels, which KiCad names "/<net>".
# The RP2350's circuit is console-rp's, which is Raspberry Pi's minimal design ("Hardware design with
# RP2350"), with the one change its datasheet asks for: 4.7u, not 100n, at DVDD pin 23 (C11).
# LCSC numbers: console-rp's, read 2026-10-28; R8's (C22808) 2026-10-24; the new ones (U3, U9, R15,
# R16) 2026-11-06; U7's and D2's, not fitted, checked against their datasheets 2026-11-06.
# =================================================================================================
R0402, C0402, C0805 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0805_2012Metric"
R0603 = "Resistor_SMD:R_0603_1608Metric"
SOT23, SOT236 = "Package_TO_SOT_SMD:SOT-23", "Package_TO_SOT_SMD:SOT-23-6"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
C100N = dict(value="100n", fp=C0402, lcsc="C1525")
C1U = dict(value="1u", fp=C0402, lcsc="C52923")
C4U7 = dict(value="4.7u", fp=C0402, lcsc="C23733")
C10U = dict(value="10u", fp=C0805, lcsc="C15850")
R10K = dict(value="10k", fp=R0402, lcsc="C25744")
R4K7 = dict(value="4.7k", fp=R0402, lcsc="C25900")
R1K = dict(value="1k", fp=R0402, lcsc="C11702")
R27 = dict(value="27R", fp=R0402, lcsc="C25100")
R100 = dict(value="100R", fp=R0402, lcsc="C25076")
SW = dict(sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", lcsc="C318884", mpn="TS-1187A-B-A-B")


def cap(ref, top, spec, why=""):
    return dict(ref=ref, sym="Device:C", nets={"1": top, "2": GND}, why=why, **spec)


def res(ref, a, b, spec, why=""):
    return dict(ref=ref, sym="Device:R", nets={"1": a, "2": b}, why=why, **spec)


def tp(ref, net, label):
    """A jig pad on the back: copper only, nothing fitted."""
    return dict(ref=ref, sym="Connector:TestPoint", value=label, fp="TestPoint:TestPoint_Pad_D1.5mm",
                nets={"1": net}, bom=False)


# The RP2350's GPIOs, by net. console-rp's, so its image runs here unchanged: the screen and the key
# on the Pico's pins (board.py's defaults), the buttons on 2, 3 and 6, the link on UART1. New: the
# second key site's bus on I2C1 (GPIO14/15, pins 18 and 19, beside the screen's) and its power on 7.
GPIO = {"BTN_D0": 2, "BTN_D1": 3, "SDA": 4, "SCL": 5, "BTN_D2": 6, "KEY2_EN": 7, "LCD_DC": 8, "LCD_CS": 9,
        "LCD_SCK": 10, "LCD_MOSI": 11, "LCD_RST": 12, "LCD_BL": 13, "SDA2": 14, "SCL2": 15, "LINK_TX": 20,
        "LINK_RX": 21, "LED": 25}
# RP2350A (QFN-60) package pin -> GPIO, from its datasheet's pin table (checked against the symbol's
# pin names)
PIN_GPIO = {"4": 2, "5": 3, "7": 4, "8": 5, "9": 6, "10": 7, "12": 8, "13": 9, "14": 10, "15": 11, "16": 12,
            "17": 13, "18": 14, "19": 15, "32": 20, "33": 21, "37": 25}
U1_NETS = {pin: next(n for n, g in GPIO.items() if g == gp) for pin, gp in PIN_GPIO.items()}

PARTS = [
    # --- the RP2350A, as console-rp's. IOVDD (six pins), ADC_AVDD, USB_OTP_VDD, QSPI_IOVDD and
    # VREG_VIN from 3.3 V; DVDD (1.1 V) from its own switching regulator: VREG_LX through L1, VREG_FB
    # reading DVDD.
    dict(ref="U1", sym="MCU_RaspberryPi:RP2350A", value="RP2350A", lcsc="C42411118", mpn="RP2350A",
         fp="mono:RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias",          # Raspberry Pi's: nine vias in its pad
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
    dict(ref="L1", sym="Device:L", value="3.3uH", fp="mono:RPi_L_Abracon_AOTA-B201610", lcsc="C42411119",
         mpn="AOTA-B201610S3R3-101-T", nets={"1": "DVDD", "2": "VREG_LX"},
         why="Raspberry Pi's footprint, its pad 1 (the dot) on DVDD as theirs"),
    # a 100n at each power pin; USB_OTP_VDD and QSPI_IOVDD share one, as the minimal design. DVDD pin
    # 23's is 4.7u: the RP2350 datasheet wants 4.7u there, away from L1 (6.1.3), as the Pico 2 has
    *[cap(f"C{4 + i}", V33, C100N, f"IOVDD, pin {p}") for i, p in enumerate(("1", "11", "20", "30", "38", "45"))],
    *[cap(f"C{10 + i}", "DVDD", C4U7 if p == "23" else C100N, f"DVDD, pin {p}") for i, p in enumerate(("6", "23", "39"))],
    cap("C13", V33, C100N, "ADC_AVDD, pin 44"),
    cap("C14", V33, C100N, "USB_OTP_VDD and QSPI_IOVDD, pins 53-54"),
    # the 12 MHz crystal: Raspberry Pi's ABM8-272-T3 (10 pF), 15 pF each side, 1k into XOUT
    dict(ref="Y1", sym="Device:Crystal_GND24", value="12MHz", fp="mono:RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm",
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
    # to a jig pad on the back (TP6): no button. Raspberry Pi says neither BOOTSEL nor RESET is needed
    res("R3", "QSPI_SS", "BOOT_SW", R1K),

    # --- power: USB-C in on the bottom end, 5 V to 3.3 V. CC1 and CC2 at 5.1k: a sink, so a C-to-C
    # cable gives 5 V.
    dict(ref="J1", sym="Connector:USB_C_Receptacle_USB2.0_16P", value="USB-C",
         fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948", mpn="TYPE-C-31-M-12",
         nets={"A1": GND, "A12": GND, "B1": GND, "B12": GND, "SH": GND,
               "A4": VBUS, "A9": VBUS, "B4": VBUS, "B9": VBUS, "A5": "CC1", "B5": "CC2",
               "A6": "USB_D+", "B6": "USB_D+", "A7": "USB_D-", "B7": "USB_D-"}),
    res("R4", "CC1", GND, dict(value="5.1k", fp=R0402, lcsc="C25905")),
    res("R5", "CC2", GND, dict(value="5.1k", fp=R0402, lcsc="C25905")),
    dict(ref="U2", sym="Power_Protection:USBLC6-2SC6", value="USBLC6-2SC6", fp=SOT236,
         lcsc="C7519", nets={"1": "USB_D+", "6": "USB_D+", "3": "USB_D-", "4": "USB_D-", "5": VBUS, "2": GND},
         why="ESD on D+, D- and VBUS at the connector"),
    # ST's LDL1117 in SOT-223, not console-rp's XC6206 (200 mA in a SOT-23, flagged for heat): 1.2 A,
    # stable on ceramics (1u in at least, 4.7u out suggested), about 120 C/W on its tab's copper
    dict(ref="U3", sym="Regulator_Linear:LD1117S33TR_SOT223", value="LDL1117S33R", fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2",
         lcsc="C435835", mpn="LDL1117S33R", nets={"3": VBUS, "2": V33, "1": GND},
         why="the LD1117's symbol: the same pins (1 GND, 2 VOUT and the tab, 3 VIN)"),
    cap("C18", VBUS, C4U7, "LDL1117 in; USB allows 10u on VBUS, this and C20 make 5.7u"),
    cap("C19", V33, C10U, "LDL1117 out, and the board's bulk"),

    # --- the link, console-rp's: the USB-C's D+/D- reach the CH343P and nothing else. It is a
    # standard USB serial device (CDC-ACM): no driver anywhere. VDD5 from VBUS, its own 3.3 V on V3 for
    # its USB side, its serial pins at VIO = the board's 3.3 V (WCH's datasheet, 5.2). TXD and RXD go
    # to UART1 on GPIO20/21. DTR and RTS go nowhere, on purpose: the computer can't reset the RP2350 or
    # hold BOOTSEL. DTR is also a strap at power-up (a pull-down there changes its mode): it floats.
    dict(ref="U4", sym="Interface_USB:CH343P", value="CH343P", fp="Package_DFN_QFN:WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm",
         lcsc="C2846043", mpn="CH343P",
         nets={"3": VBUS, "9": VBUS, "6": "CH_V3", "1": V33, "2": GND, "17": GND, "7": "USB_D+", "8": "USB_D-",
               "4": "LINK_RX", "5": "LINK_TX"}),
    cap("C20", VBUS, C1U, "CH343P VDD5"), cap("C21", "CH_V3", C100N, "CH343P V3: about 0.1u, WCH says"),
    cap("C22", V33, C100N, "CH343P VIO"),

    # --- the key: the ATECC608C in SOIC-8 on I2C0 (GPIO4/5, the Pico's), 4.7k pull-ups to 3.3 V
    dict(ref="U5", sym="Security:ATECC608A-SSHDA", value="ATECC608C-SSHDA-T", fp=SOIC8,
         lcsc="C28975195", mpn="ATECC608C-SSHDA-T", nets={"8": V33, "4": GND, "5": "SDA", "6": "SCL"},
         why="same pins as the 608A symbol"),
    cap("C23", V33, C100N, "ATECC608C VCC"),
    res("R6", V33, "SDA", R4K7), res("R7", V33, "SCL", R4K7),

    # --- the screen: the 1.14" 240x135 ST7789 on an 8-pin 0.5 mm FPC, console-rp's pin order (1 LEDA,
    # 2 GND, 3 RESET, 4 RS, 5 SDA, 6 SCL, 7 VDD, 8 CS), which its board 1 shows a picture with. The
    # backlight's cathode is on GND inside, so it's switched high: Q1 (P-FET) from 5 V through 150R, a
    # current set by the resistor and not by the panel's LED, turned on by Q2 when GPIO13 is high.
    dict(ref="J2", sym="Connector_Generic:Conn_01x08", value="PANEL",
         fp="mono:FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB", lcsc="C2919492",
         mpn="0.5K-HX-8PWB", nets={"1": "LCD_LEDA", "2": GND, "3": "LCD_RST", "4": "LCD_DC",
                                   "5": "LCD_MOSI", "6": "LCD_SCK", "7": V33, "8": "LCD_CS"}),
    cap("C24", V33, C1U, "the panel's VDD"), cap("C25", V33, C100N),
    dict(ref="Q1", sym="Transistor_FET:AO3401A", value="AO3401A", fp=SOT23, lcsc="C15127",
         nets={"2": VBUS, "3": "BL_SW", "1": "BL_GATE"}),
    res("R8", "BL_SW", "LCD_LEDA", dict(value="150R", fp=R0603, lcsc="C22808"),
        "from 5 V: about 13 mA at the LED's 3.0 V (15 typical, 20 most); 27 mW"),
    res("R9", VBUS, "BL_GATE", R10K, "Q1 off by default"),
    dict(ref="Q2", sym="Transistor_BJT:SS8050", value="S8050", fp=SOT23, lcsc="C2150",
         mpn="SS8050", nets={"1": "BL_BASE", "2": GND, "3": "BL_GATE"}),
    res("R10", "LCD_BL", "BL_BASE", R1K),
    res("R11", "LCD_BL", GND, R4K7,
        "the backlight stays off until the firmware turns it on; under the 8.2k RP2350-E9 asks of a pull-down"),

    # --- the buttons, in a row under the screen, each to GND: pulled up inside the RP2350 and pressed
    # low (no pull-downs inside: RP2350-E9). Each one's GPIO on the side its line comes from.
    dict(ref="SW1", value="D0", nets={"1": GND, "2": "BTN_D0"}, **SW),
    dict(ref="SW2", value="D1", nets={"1": GND, "2": "BTN_D1"}, **SW),
    dict(ref="SW3", value="D2", nets={"1": "BTN_D2", "2": GND}, **SW),

    # --- the LED on GPIO25, the Pico 2's
    res("R12", "LED", "LED_A", R1K),
    dict(ref="D1", sym="Device:LED", value="RED", fp="LED_SMD:LED_0603_1608Metric", lcsc="C2286", mpn="KT-0603R",
         nets={"2": "LED_A", "1": GND}),

    # --- the jig: nine pads on the back, in one row under U1, for pogo pins: SWD (through 100R, so
    # a jig's long leads can't ring into the chip), RUN, 3.3 V, BOOTSEL (TP6 to GND at reset), the
    # RP2350's own USB (its REPL and USB boot, through 27R) and ground at each end. Nothing reaches
    # them through the USB-C.
    res("R13", "RP_DM", "DEV_D-", R27, "USB's 27 R, close to the chip"),
    res("R14", "RP_DP", "DEV_D+", R27),
    res("R15", "SWCLK", "JIG_SWCLK", R100), res("R16", "SWDIO", "JIG_SWDIO", R100),
    tp("TP1", "JIG_SWCLK", "SWCLK"), tp("TP2", GND, "GND"), tp("TP3", "JIG_SWDIO", "SWDIO"), tp("TP4", "RUN", "RUN"),
    tp("TP5", V33, "3V3"), tp("TP6", "BOOT_SW", "BOOT"), tp("TP7", "DEV_D+", "D+"), tp("TP8", "DEV_D-", "D-"),
    tp("TP9", GND, "GND"),

    # --- KEY 2: a second key's site under D0, on I2C1 (GPIO14/15) and a supply of its own, off until
    # the firmware turns it on. Footprints for a Trust M (USON-10, at 0x30) and a 608C (SOIC-8, at
    # 0x60), both not fitted, and five holes in Adafruit's breakouts' order (VCC GND SCL SDA RST) for a
    # breakout or a key on wires. The AP22653 limits the site to 40-120 mA (ILIM to GND), discharges it
    # when off and blocks current back into 3.3 V; the pull-ups go to the switched supply, so a chip that's
    # off isn't fed through its pins. U10 clamps SDA2 and SCL2 at the holes.
    dict(ref="U9", sym="mono:AP22653", value="AP22653W6-7", fp=SOT236, lcsc="C2158037", mpn="AP22653W6-7",
         nets={"1": V33, "2": GND, "3": "KEY2_EN", "5": GND, "6": "VKEY"},
         why="FAULT (pin 4) not connected: the firmware sees a short as a chip that doesn't answer"),
    cap("C28", V33, C100N, "U9 in"),
    cap("C29", "VKEY", C1U, "U9 out: 1u, not 10u, for the Trust M's 1 ms rise (with a breakout's 10u, an estimate)"),
    res("R20", "KEY2_EN", GND, R4K7, "KEY 2 off at reset and under any image that doesn't know it (RP2350-E9: under 8.2k)"),
    dict(ref="U7", sym="mono:OPTIGA_TRUST_M", value="SLS32AIA010MH", fp="Package_SON:Microchip_USON-10-1EP_3x3mm_P0.5mm_EP1.8x2.5mm",
         lcsc="C539250", mpn="SLS32AIA010MH", nets={"1": GND, "3": "SDA2", "8": "SCL2", "9": "KEY2_RST", "10": "VKEY", "11": GND},
         dnp=True, why="Infineon's PG-USON-10-2 on KiCad's 3 x 3 mm USON-10; its exposed pad isn't connected inside, ground for heat"),
    cap("C26", "VKEY", C100N, "U7 VCC"),
    dict(ref="U8", sym="Security:ATECC608A-SSHDA", value="ATECC608C-SSHDA-T", fp=SOIC8,
         lcsc="C28975195", mpn="ATECC608C-SSHDA-T", nets={"8": "VKEY", "4": GND, "5": "SDA2", "6": "SCL2"}, dnp=True),
    cap("C27", "VKEY", C100N, "U8 VCC"),
    res("R17", "VKEY", "SDA2", R4K7), res("R18", "VKEY", "SCL2", R4K7),
    res("R19", "VKEY", "KEY2_RST", R10K, "the Trust M's reset held off; the holes can pull it low"),
    dict(ref="U10", sym="Power_Protection:USBLC6-2SC6", value="USBLC6-2SC6", fp=SOT236, lcsc="C7519",
         nets={"1": "SDA2", "6": "SDA2", "3": "SCL2", "4": "SCL2", "5": V33, "2": GND},
         why="ESD at the holes, to always-on 3.3 V, never to VKEY"),
    dict(ref="D2", sym="Diode:ESD5Zxx", value="ESD5Z5V0", fp="Diode_SMD:D_SOD-523", lcsc="C502546", mpn="ESD5Z5V0",
         nets={"1": "VKEY", "2": GND}, dnp=True, why="for a key that's plugged in and out at the holes"),
    dict(ref="J4", sym="Connector_Generic:Conn_01x05", value="KEY2", fp="Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
         nets={"1": "VKEY", "2": GND, "3": "SCL2", "4": "SDA2", "5": "KEY2_RST"}, dnp=True, bom=False),
] + [dict(ref=f"H{i}", sym="Mechanical:MountingHole", value="M2", fp="MountingHole:MountingHole_2.2mm_M2",
          nets={}, bom=False) for i in range(1, 5)] \
  + [dict(ref=f"FID{i}", sym="Mechanical:Fiducial", value="Fiducial", fp="Fiducial:Fiducial_1mm_Mask2mm",
          nets={}, bom=False) for i in range(1, 4)]     # for JLCPCB's Standard assembly and its panel

# Nets KiCad would call undriven: VBUS comes in on a passive pin, DVDD through L1, VREG_AVDD through
# R1. Each gets a PWR_FLAG.
FLAGS = [GND, VBUS, "DVDD", "VREG_AVDD"]

# The RP2350's function table (its datasheet, GPIO functions F1-F3): which GPIOs can carry each.
FUNC = {"UART1 TX": {4, 8, 20, 24}, "UART1 RX": {5, 9, 21, 25}, "I2C0 SDA": {0, 4, 8, 12, 16, 20, 24, 28},
        "I2C0 SCL": {1, 5, 9, 13, 17, 21, 25, 29}, "I2C1 SDA": {2, 6, 10, 14, 18, 22, 26},
        "I2C1 SCL": {3, 7, 11, 15, 19, 23, 27}, "SPI1 SCK": {10, 14, 26}, "SPI1 TX": {11, 15, 27}}
NEEDS = {"LINK_TX": "UART1 TX", "LINK_RX": "UART1 RX", "SDA": "I2C0 SDA", "SCL": "I2C0 SCL",
         "SDA2": "I2C1 SDA", "SCL2": "I2C1 SCL", "LCD_SCK": "SPI1 SCK", "LCD_MOSI": "SPI1 TX"}

# =================================================================================================
# S-expressions: just enough to lift a stock symbol out of KiCad's library
# =================================================================================================
TOK = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)')
LIB = os.path.join(HERE, "lib")
SYMLIB = os.path.join(LIB, "mono.kicad_sym")


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
        path = SYMLIB if lib == "mono" else os.path.join(KISYM, lib + ".kicad_sym")
        root = parse(open(path).read())[0]
        _libs[lib] = {uq(x[1]): x for x in root if isinstance(x, list) and x[0] == "symbol"}
    return _libs[lib]


def stock(lib_id):
    """The library symbol, flattened if it extends another, named lib_id for the schematic's cache.
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


AP22653_DS = "https://www.diodes.com/assets/Datasheets/AP22652_53_52A_53A.pdf"
TRUSTM_DS = "https://www.infineon.com/assets/row/public/documents/30/49/infineon-optiga-trust-m-sls32aia-datasheet-en.pdf"


def write_symbols():
    """lib/mono.kicad_sym: the two parts KiCad has no symbol for, as plain boxes. AP22653's pins are
    console-pcb's (Diodes DS41186); the Trust M's are Infineon's datasheet's, table 6."""
    ap = gen.box_symbol("AP22653", "U", "AP22653", SOT236, AP22653_DS,
                        "Diodes AP22653: current-limited high-side switch, reverse blocking, output discharge, active-high EN, SOT-26",
                        7.62, 5.08, [("1", "IN", "power_in", "L", 2.54), ("3", "EN", "input", "L", -2.54),
                                     ("6", "OUT", "power_out", "R", 2.54), ("4", "~{FAULT}", "open_collector", "R", -2.54),
                                     ("2", "GND", "power_in", "B", -2.54), ("5", "ILIM", "passive", "B", 2.54)])
    tm = gen.box_symbol("OPTIGA_TRUST_M", "U", "OPTIGA_TRUST_M", "Package_SON:Microchip_USON-10-1EP_3x3mm_P0.5mm_EP1.8x2.5mm",
                        TRUSTM_DS, "Infineon OPTIGA Trust M (SLS32AIA): secure element, ECC and RSA, I2C at 0x30, PG-USON-10-2",
                        7.62, 7.62, [("10", "VCC", "power_in", "T", 0), ("1", "GND", "power_in", "B", -2.54),
                                     ("11", "EP", "passive", "B", 2.54), ("3", "SDA", "bidirectional", "L", 2.54),
                                     ("8", "SCL", "input", "L", 0), ("9", "~{RST}", "input", "L", -2.54),
                                     *[(n, "NC", "no_connect", "R", off) for n, off in
                                       (("2", 5.08), ("4", 2.54), ("5", 0), ("6", -2.54), ("7", -5.08))]])
    os.makedirs(LIB, exist_ok=True)
    with open(SYMLIB, "w") as f:
        f.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        f.write("\n".join((ap, tm)))
        f.write("\n)\n")
    _libs.pop("mono", None)
    with open(os.path.join(OUT, "sym-lib-table"), "w") as fh:
        fh.write('(sym_lib_table\n  (version 7)\n'
                 '  (lib (name "mono")(type "KiCad")(uri "${KIPRJMOD}/../lib/mono.kicad_sym")(options "")(descr "Mono\'s own symbols"))\n)\n')


# =================================================================================================
# The schematic: each part placed, a short wire from each pin, and the net's label or power symbol
# at its end. Nothing is drawn wire to wire, so a connection is exactly a name.
# =================================================================================================
def uid():
    return str(uuid.uuid4())


def font(hide=False, justify=None):
    return "(effects (font (size 1.27 1.27))" + (f" (justify {justify})" if justify else "") + (" (hide yes)" if hide else "") + ")"


# Where each part goes on the A2 sheet (mm, on the 2.54 grid), block by block: console-rp's blocks
# where it had them, the second key site and the jig at the right.
def g(n):
    return round(n * 2.54, 2)


PLACE = {
    "U1": (g(80), g(64)),
    # power in
    "J1": (g(14), g(22)), "R4": (g(26), g(14)), "R5": (g(30), g(14)), "U2": (g(14), g(42)),
    "U3": (g(32), g(28)), "C18": (g(22), g(40)), "C19": (g(42), g(40)),
    # the link
    "U4": (g(16), g(68)), "C20": (g(28), g(62)), "C21": (g(32), g(62)), "C22": (g(36), g(62)),
    # the RP2350's supplies, in a row above it
    "R1": (g(46), g(14)), "C3": (g(50), g(16)), "L1": (g(54), g(14)), "C1": (g(58), g(16)), "C2": (g(62), g(16)),
    **{f"C{4 + i}": (g(66 + 4 * i), g(16)) for i in range(11)},
    # the crystal, the flash and BOOTSEL's resistor, left of it
    "Y1": (g(50), g(98)), "R2": (g(50), g(90)), "C15": (g(44), g(104)), "C16": (g(56), g(104)),
    "U6": (g(46), g(72)), "C17": (g(56), g(66)), "R3": (g(54), g(80)),
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
    "H1": (g(146), g(100)), "H2": (g(150), g(100)), "H3": (g(154), g(100)), "H4": (g(158), g(100)),
    **{f"FID{i + 1}": (g(146 + 4 * i), g(106)) for i in range(3)},
    # KEY 2: the switch, the two chips, the pull-ups, the clamp and the holes
    "U9": (g(182), g(18)), "C28": (g(168), g(20)), "C29": (g(196), g(20)), "R20": (g(170), g(28)),
    "U7": (g(182), g(46)), "C26": (g(196), g(40)),
    "U8": (g(212), g(46)), "C27": (g(224), g(40)),
    "R17": (g(200), g(60)), "R18": (g(204), g(60)), "R19": (g(208), g(60)),
    "U10": (g(184), g(70)), "D2": (g(200), g(72)), "J4": (g(218), g(72)),
    # the jig
    "R15": (g(170), g(90)), "R16": (g(176), g(90)),
    **{f"TP{i + 1}": (g(168 + 6 * i), g(102)) for i in range(9)},
}
FLAG_AT = {GND: (g(6), g(100)), VBUS: (g(10), g(100)), "DVDD": (g(14), g(100)), "VREG_AVDD": (g(18), g(100))}
NOTES = [
    (g(4), g(106), "Mono: a slender console with no radio. See hardware/mono/README.md.\n"
                   "Every connection is a name: a net label or a power symbol at the end of each pin's stub."),
    (g(2), g(80), "The link. The USB-C's D+ and D- reach the CH343P and nothing else.\n"
                  "TXD/RXD go to UART1 (GPIO21/20). DTR and RTS are NOT connected,\n"
                  "on purpose: the computer can't reset the RP2350 or hold BOOTSEL.\n"
                  "Don't add auto-reset."),
    (g(62), g(106), "The RP2350's regulator (L1, C1, C2, R1, C3) is Raspberry Pi's minimal design.\n"
                    "Copy its layout and L1's orientation exactly (Hardware design with RP2350, 2.1)."),
    (g(104), g(36), "J2: console-rp's pin order, which its board 1 shows a picture with."),
    (g(162), g(8), "KEY 2: a second key's site, on I2C1 and VKEY, a supply of its own that is off at reset.\n"
                   "U7 (Trust M, 0x30), U8 (608C, 0x60) and J4 are not fitted. Pull-ups to VKEY, never to 3V3.\n"
                   "J4: VKEY GND SCL SDA RST, Adafruit's breakouts' order. Meter before power."),
    (g(162), g(84), "The jig's pads, on the back: SWD through 100R, RUN, 3V3, BOOT (to GND at reset for\n"
                    "USB boot), the RP2350's own USB through 27R, and ground. Nothing reaches them through the USB-C."),
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
(paper "A2")
(title_block (title "Picoquorum Mono: a slender console, an RP2350, no radio, USB serial to the host") (date "{DATE}") (rev "{REV}")
  (company "Picoquorum") (comment 1 "Written by hardware/mono/gen_mono.py. CERN-OHL-W v2")
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
    # console-rp's classes: 0.15 mm between copper, as Raspberry Pi's board (its QFN's pads are 0.17
    # apart); signals at 0.2 mm, power at 0.25 mm, the widest a track can meet a 0.4 mm-pitch pad at
    # and keep 0.15 from the next; ground the same, in a class of its own that `tools/keypcb route`
    # leaves to the pours
    cls = d["net_settings"]["classes"]
    cls[0].update(clearance=CLEAR, track_width=0.2, via_diameter=0.6, via_drill=0.3)
    cls.append(dict(cls[0], name="Power", priority=0, track_width=0.25))
    cls.append(dict(cls[0], name="Ground", priority=1, track_width=0.25))
    d["net_settings"]["netclass_patterns"] = ([{"netclass": "Power", "pattern": n} for n in (V33, VBUS, "/VKEY")]
                                              + [{"netclass": "Ground", "pattern": GND}])
    d["sheets"] = [[sheet_uuid, "Root"]]
    with open(os.path.join(OUT, NAME + ".kicad_pro"), "w") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)
        fh.write("\n")


def write_bom():
    rows = {}
    for p in PARTS:
        if not p.get("bom", True) or p.get("dnp"):
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
    lines = ["# Mono: the RP2350's pins", "",
             "*Written by `gen_mono.py`; don't edit by hand.*", "",
             "console-rp's pins, so console-rp's image runs on Mono unchanged; KEY 2's three are new and",
             "unused by that image (its supply stays off).", "",
             "| GPIO | RP2350A pin | net | what | board.py's Pico default |", "|---|---|---|---|---|"]
    what = {"BTN_D0": "D0, to GND: pull-up inside, pressed low", "BTN_D1": "D1, to GND: pull-up inside, pressed low",
            "BTN_D2": "D2, to GND: pull-up inside, pressed low", "SDA": "I2C0 SDA, the key's bus, 4.7k to 3.3 V",
            "SCL": "I2C0 SCL, the key's bus, 4.7k to 3.3 V", "LED": "red LED, high is on",
            "KEY2_EN": "KEY 2's supply (VKEY), high is on; 4.7k down", "SDA2": "I2C1 SDA, KEY 2's bus, 4.7k to VKEY",
            "SCL2": "I2C1 SCL, KEY 2's bus, 4.7k to VKEY",
            "LINK_TX": "UART1 TX to the CH343P's RXD", "LINK_RX": "UART1 RX from the CH343P's TXD",
            "LCD_MOSI": "SPI1 TX, the screen's SDA", "LCD_SCK": "SPI1 SCK, the screen's SCL", "LCD_DC": "the screen's RS",
            "LCD_RST": "the screen's RESET", "LCD_CS": "the screen's CS", "LCD_BL": "backlight, high is on; 4.7k down"}
    pico = pico_pins()
    for net, gp in sorted(GPIO.items(), key=lambda kv: kv[1]):
        lines.append(f"| {gp} | {pin_of[gp]} | `{net}` | {what[net]} | {pico.get(gp, '')} |")
    lines += ["", "Also: QSPI to the flash (pins 55–60), XIN/XOUT to the crystal, and to the jig's pads on the",
              "back only: RUN, SWCLK/SWDIO (through 100 R) and USB_DP/DM (through 27 R). Not connected:",
              "GPIO 0, 1, 16–19, 22–24 and 26–29.", ""]
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


def make_i2c_pairs():
    """Whether firmware/atecc.py's make_i2c still puts a pair with SCL = SDA + 1 and SDA % 4 == 2 on
    I2C1 (anything it doesn't is a SoftI2C). Read only."""
    a = open(os.path.join(REPO, "firmware", "atecc.py")).read()
    return bool(re.search(r"if scl == sda \+ 1 and sda % 4 in \(0, 2\):\n\s+return I2C\(0 if sda % 4 == 0 else 1,", a))


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
    sda2, scl2 = GPIO["SDA2"], GPIO["SCL2"]
    if not (scl2 == sda2 + 1 and sda2 % 4 == 2):
        bad.append(f"KEY 2's bus (GPIO{sda2}/{scl2}) isn't a pair firmware/atecc.py's make_i2c puts on I2C1")
    if not make_i2c_pairs():
        bad.append("firmware/atecc.py's make_i2c no longer reads as the pair rule this board's KEY 2 bus relies on")
    names = {n: name for n, name, *_ in stock("MCU_RaspberryPi:RP2350A")[1]}
    u1 = next(p for p in PARTS if p["ref"] == "U1")["nets"]
    for pin, gp in PIN_GPIO.items():
        if not re.match(rf"GPIO{gp}(/|$)", names.get(pin, "")):
            bad.append(f"U1 pin {pin} is {names.get(pin)!r} in KiCad's symbol, not GPIO{gp}")
        if GPIO.get(u1.get(pin)) != gp:
            bad.append(f"U1 pin {pin} is GPIO{gp} but carries {u1.get(pin)}")


def check_link(bad, nets):
    """What the computer can reach, from the netlist: the USB-C's data lines only the CH343P, the
    CH343P's DTR and RTS nothing, the RP2350's own USB, SWD, RUN and BOOTSEL only the jig's pads.
    And KEY 2: its bus and supply apart from the signing key's, and no 3V3 at its holes."""
    def on(net):
        return {r for r, _ in nets.get(net if net in POWER else "/" + net, ())}
    for n, s in nets.items():
        if any(r == "U4" and pin in ("12", "13") for r, pin in s) and not n.startswith("unconnected-"):
            bad.append(f"the CH343P's DTR or RTS is connected ({n}): the computer could reset the RP2350 or hold BOOTSEL")
        if any(r == "J1" for r, _ in s) and any(r == "U1" for r, _ in s) and n not in POWER:
            bad.append(f"the USB-C reaches the RP2350 directly on {n}")
        if any(r == "J4" for r, _ in s) and n == V33:
            bad.append("KEY 2's holes have 3.3 V on them: a breakout's pull-ups would stay powered with the site off")
    for net in ("USB_D+", "USB_D-"):
        if on(net) != {"J1", "U2", "U4"}:
            bad.append(f"{net} reaches {sorted(on(net))}; it should be the USB-C, its ESD diodes and the CH343P only")
    for net, want in (("RP_DP", {"U1", "R14"}), ("RP_DM", {"U1", "R13"}), ("DEV_D+", {"R14", "TP7"}),
                      ("DEV_D-", {"R13", "TP8"}), ("SWCLK", {"U1", "R15"}), ("JIG_SWCLK", {"R15", "TP1"}),
                      ("SWDIO", {"U1", "R16"}), ("JIG_SWDIO", {"R16", "TP3"}), ("RUN", {"U1", "TP4"}),
                      ("QSPI_SS", {"U1", "U6", "R3"}), ("BOOT_SW", {"R3", "TP6"}), ("LINK_TX", {"U1", "U4"}),
                      ("LINK_RX", {"U1", "U4"}), ("SDA", {"U1", "U5", "R6"}), ("SCL", {"U1", "U5", "R7"}),
                      ("SDA2", {"U1", "U7", "U8", "U10", "R17", "J4"}), ("SCL2", {"U1", "U7", "U8", "U10", "R18", "J4"}),
                      ("KEY2_EN", {"U1", "U9", "R20"}), ("KEY2_RST", {"U7", "R19", "J4"}),
                      ("VKEY", {"U9", "U7", "U8", "C26", "C27", "C29", "R17", "R18", "R19", "J4", "D2"})):
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
    """KiCad's ERC, with KiCad's default library tables (a fresh config) and the project's own, so
    each cached symbol is compared with the library it came from."""
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
# The board: every part placed, not routed. Board coordinates in mm, y down, from the top-left
# corner of Mono's first outline, 40 x 96; the page puts that point at (OX, OY). The board was made
# shorter after its route without routing it again: the top edge came down 2 mm, to TOP, and
# everything below y 73.85 (the USB-C, the CH343P, the regulator, the bottom holes) rose 4.5 mm
# into the empty field under the LED (README.md, "Routing"); the back's current lines and logo
# rose 1.3. Every other part kept its place.
# Mono: a 40 x 89.5 bar, 2.24:1. The glass across the top 1 mm from the edge, its picture centred
# across; the three buttons under it 10 mm apart, an M2 hole either side; under D0 the second key's
# site, under D2 the backlight's switch and the key; the RP2350 in the middle turned a quarter turn so
# its screen and button pins face up and its flash sits up-right, clear of the glass; the jig's pads
# on the back under it; and the USB-C on the bottom end, left of centre, with its ESD diodes, the
# CH343P and the regulator above it. Every part on the front, as every board before it.
# =================================================================================================
W = 40.0
TOP, H = 2.0, 91.5                       # the top and bottom edges: 89.5 mm
OX, OY = 100.0, 100.0
CORNER = 2.0
CLEAR = 0.15                             # the Default and Power classes' clearance (write_project)
SHAPES = os.path.join(LIB, "mono.3dshapes")
MONO_FP = os.path.join(LIB, "mono.pretty")
MARK = os.path.join(LIB, "picoquorum.pretty")     # a copy of console-pocket's, so a copy of the project finds it

# The panel: ER-TFT1.14-2 (EastRising's drawing, rev 1.0, 2022-02-22): the module 31.0 x 17.6, 1.6
# thick; the active area 24.91 x 14.86, 1.445 mm off the module's centre away from the ribbon; the
# ribbon 4.5 wide, folded under it reaching 21.0 +-0.5 mm in from the module's ribbon end, the fold
# at most 0.5 past that end. The glass lies on 2 mm foam pads at its corners. Measure a panel before
# ordering (README.md, "The panel").
PANEL = dict(glass=(31.0, 17.6), active=(24.91, 14.86), active_off=1.445, rows=135, cols=240, thick=1.6,
             foam=2.0, pad=2.0, reach=21.0, ribbon=4.5)
XA = W / 2                               # the picture's centre across: the board's middle
GX0 = round(XA + PANEL["active_off"] - PANEL["glass"][0] / 2, 4)     # the glass's left end; the ribbon leaves its right end
GY0 = 3.0
GX1, GY1 = GX0 + PANEL["glass"][0], GY0 + PANEL["glass"][1]
XC, YC = (GX0 + GX1) / 2, (GY0 + GY1) / 2
ZIF_X = round(GX1 - 19.5, 3)             # J2's origin 19.5 mm in from the glass's ribbon end, as console-s3's and PicoquorumKey's


def gl(x, y):
    """A point given from the glass's top-left corner."""
    return round(GX0 + x, 4), round(GY0 + y, 4)


# Heights (mm) of what sits under the glass, which has PANEL["foam"] of room
UNDER = {"_0402_": 0.5, "_0603_": 0.8, "SOT-23": 1.15, "HDGC": 1.0}


def slot(i):
    """x of the middle of footer slot i, as quorum_ui_s.bar draws three slots of (W - 8) // 3
    pixels, 2 apart, from x = 2 (240 wide here): about 8.0 mm wide, 8.2 apart."""
    sw = (PANEL["cols"] - 8) // 3
    px = 2 + i * (sw + 2) + sw / 2
    return round(XA - PANEL["active"][0] / 2 + px * PANEL["active"][0] / PANEL["cols"], 3)


PITCH = 10.0        # the buttons apart: D1 on the board's middle, D0 and D2 about 1.8 mm further out than their
                    # slots' middles, still inside the slots
BY = 26.0           # the buttons' row: 5.4 mm under the glass, their tops 1.6 under it


def button(i):
    """x of button i (D0, D1, D2)."""
    return round(XA + (i - 1) * PITCH, 3)


U1 = (20.0, 61.0)                        # the RP2350's centre, turned -90: pins 1-15 face up
J1 = (12.0, 87.9)                        # the USB-C, its opening down: its face 3.6 mm from its origin, on the bottom edge


def u1(x, y):
    """A point given from U1's centre in Raspberry Pi's frame (the chip not turned, pin 1 top-left), on
    the board: U1 turned -90 (KiCad's angles run anticlockwise), so their x runs down the board and
    their y runs left. Raspberry Pi's block, console-rp's flash and the copper drawn round U1 keep
    their places to the chip through it."""
    return round(U1[0] - y, 4), round(U1[1] + x, 4)


def pin(n):
    """U1's pad n on the board: the QFN-60's 15 pads a side at 0.4 mm, their centres 3.45 mm out, pin 1
    at the top of its left side in Raspberry Pi's frame (which is the board's top, U1 turned)."""
    side, k = divmod(n - 1, 15)
    o = -2.8 + 0.4 * k
    return u1(*((-3.45, o), (o, 3.45), (3.45, -o), (-o, -3.45))[side])


def jm(x, y):
    """A point given from J1 (its opening down, as the square console-rp rev B had it and console-rp's
    j1() measures from): the ESD diodes, the CH343P and their copper keep their places to it."""
    return round(J1[0] + x, 4), round(J1[1] + y, 4)


def jd(x, y):
    """A console-rp board point taken off its short bar's route, J1 at (3.6, 51.0) facing left: turned
    back to J1 facing down, from Mono's J1."""
    return jm(round(y - 51.0, 4), round(3.6 - x, 4))


def rot(r):
    """An angle in (-180, 180]."""
    r = (r + 180) % 360 - 180
    return 180 if r == -180 else r


TPY = 70.0                               # the jig's pads' row, on the back, under U1's block
TP_X = {"TP1": 3.0, "TP2": 5.54, "TP3": 8.08, "TP4": 10.62, "TP5": 13.16,
        "TP6": 28.0, "TP7": 30.54, "TP8": 33.08, "TP9": 35.62}

# ref -> (x, y, rotation in degrees). Under the glass: only parts lower than the tape, none in the
# foam pads' corners, none in the ribbon's path (right of J2, across YC).
AT = {
    "SW1": (button(0), BY, 90), "SW2": (button(1), BY, 90), "SW3": (button(2), BY, 90),
    # an M2 hole either side of the buttons, and either side of the USB-C's end
    "H1": (3.5, BY, 0), "H2": (W - 3.5, BY, 0), "H3": (3.5, H - 3.5, 0), "H4": (W - 3.5, H - 3.5, 0),
    # under the glass: the screen's connector and its decoupling, above it to the left
    "J2": (ZIF_X, YC, 90), "C24": (15.0, 7.4, 0), "C25": (15.0, 6.3, 0),
    # the backlight's switch down the right edge under H2, from VBUS
    "R9": (37.4, 29.9, 0), "Q1": (37.4, 32.5, 0), "R8": (37.4, 35.3, 0),
    "Q2": (37.4, 38.5, 0), "R10": (37.4, 41.3, 0), "R11": (37.4, 42.5, 0),
    # the key under D2, its bus pins facing U1; its pull-ups and 100n beside them
    "U5": (30.0, 44.6, 180), "R6": (25.0, 42.7, 0), "R7": (25.0, 43.9, 0), "C23": (25.0, 46.5, 0),
    # the RP2350 with Raspberry Pi's parts round it (RPI, below), turned with it: the regulator right
    # of it, low; the crystal left; the USB resistors and the flash up-right
    "U1": (*U1, -90),
    "U6": (*u1(-7.1, -10.8), -90), "C17": (*u1(-0.95, -9.4), 180), "R3": (*u1(-8.7, -6.6), 180),
    "C9": (*u1(6.485, -1.8), -90),                # pin 45's: Raspberry Pi's C17 serves pins 44 and 45 together
    # the LED under U1, in the field
    "R12": (19.46, 73.0, 0), "D1": (22.0, 73.0, 180),      # D1's anode toward R12
    # the jig's series resistors at the end of SWD's fan-out, pin 1 (the chip's side) up
    "R15": (11.9, 67.5, -90), "R16": (13.0, 67.5, -90),
    # power in and the link: the USB-C on the bottom edge, its ESD diodes, the CH343P above it, the
    # square console-rp rev B's block as it was; the regulator right of it
    "J1": (*J1, 0), "U2": (*jm(0.0, -7.5), 90), "R4": (*jm(-4.0, -6.2), 0), "R5": (*jm(4.0, -6.2), 0),
    "U4": (*jm(-0.5, -11.8), 0), "C20": (*jm(3.0, -11.1), 90), "C21": (*jm(-3.5, -9.0), 180), "C22": (*jm(-3.4, -14.4), 90),
    "U3": (27.0, 82.0, 0), "C18": (21.6, 84.3, 0), "C19": (32.9, 82.0, 90),
    # KEY 2 under D0: the two chips side by side, their 100n above them, the pull-ups under them, the
    # holes across, and the switch and the clamp under the holes: C28 beside the switch's IN and
    # ground, C29 beside its OUT and ground, R20 under C28
    "U8": (4.8, 35.2, 0), "U7": (10.8, 35.2, 0), "C27": (7.3, 31.5, 0), "C26": (11.3, 32.1, 0),
    "R17": (6.4, 39.4, 0), "R18": (6.4, 40.6, 0), "R19": (11.0, 39.4, 0),
    "J4": (1.9, 44.2, 90),
    "U9": (4.4, 49.6, 0), "C28": (1.75, 49.12, -90), "C29": (7.0, 49.12, -90), "R20": (1.75, 51.0, 90),
    "U10": (9.6, 49.6, 0), "D2": (9.6, 52.6, 0),
    # fiducials, each 3.85 mm or more from the edge (JLCPCB's process-edge page)
    "FID1": (3.85, 8.0, 0), "FID2": (W - 3.85, 52.0, 0), "FID3": (20.0, H - 3.85, 0),
    **{t: (x, TPY, 0) for t, x in TP_X.items()},
}
BACK = set(TP_X)                         # placed on the back
# Raspberry Pi's minimal board round the chip (console-rp's rpi_minimal.py wrote it from their MIT
# KiCad files): their footprints and where each part sits from U1's centre, and their power copper,
# which write_board copies as it is, turned with U1. Their U1 and ours have the same pads in the same places.
RPI = json.load(open(os.path.join(HERE, "rpi_minimal.json")))
for _ref, _q in RPI["parts"].items():
    AT[_ref] = (*u1(*_q["at"]), rot(_q["rot"] - 90))
    next(p for p in PARTS if p["ref"] == _ref)["fp"] = _q["fp"].replace("pqrp:", "mono:")
# console-rp's one change to their block: their C12 (our C14, pins 53-54's) up beside the flash's lines
AT["C14"] = (*u1(-0.95, -11.4), 0)
DROP = {((0.0, -3.4375), (0.0, -3.9)), ((0.0, -3.9), (-0.4, -4.3)), ((-0.4, -3.4375), (-0.4, -4.3)),
        ((-0.4, -4.3), (-2.1, -6.0)), ((-2.1, -6.0), (-2.1, -6.92))}
# And their two ground vias beside C1's and C2's ground pads: one 0.15 mm out, one left out (console-rp's)
VIA_MOVE = {(3.1, -5.5): (3.25, -5.5), (3.1, -4.9): None}

# console-rp's tracks inside Raspberry Pi's pours, which join the pads their pours do, for the router
# (U1's centre is 0, 0, their frame): VREG_LX to L1, PGND to its via, VREG_VIN to C1 and the 3V3 ring
# under the chip, the DVDD ring inside it, and DVDD from L1 by C2 to the vias under the chip.
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
# The flash's six lines, console-rp's, drawn and locked (F.Cu, 0.15 mm): Raspberry Pi's fan-out from
# pins 55-60, SD0 into pin 5 from below, SCLK and SD3 past the ends of pins 5-6 into 6 and 7, SD2 under
# the flash into pin 3, SD1 and SS round its far side into 2 and 1, SS by R3. Then 3V3 from pin 54 to
# C17, C14 and the flash's pin 8 (SPINE, 0.2 mm); and the flash's ground pin to a via.
FLASH = [
    ("/QSPI_SD3", [u1(-0.8, -3.45), u1(-0.8, -4.2), u1(-2.1, -5.5), u1(-2.1, -11.435), u1(-3.512, -11.435)]),
    ("/QSPI_SCLK", [u1(-1.2, -3.45), u1(-1.2, -4.1), u1(-2.45, -5.35), u1(-2.45, -10.165), u1(-3.512, -10.165)]),
    ("/QSPI_SD0", [u1(-1.6, -3.45), u1(-1.6, -4.0), u1(-3.0, -5.4), u1(-3.0, -8.895)]),
    ("/QSPI_SD2", [u1(-2.0, -3.45), u1(-2.0, -3.9), u1(-8.265, -10.165), u1(-10.688, -10.165)]),
    ("/QSPI_SD1", [u1(-2.4, -3.45), u1(-2.4, -3.864), u1(-6.636, -8.1), u1(-11.65, -8.1), u1(-12.0, -8.45), u1(-12.0, -11.435),
                   u1(-10.688, -11.435)]),
    ("/QSPI_SS", [u1(-2.8, -3.45), u1(-2.8, -3.7), u1(-6.85, -7.75), u1(-8.7, -7.75), u1(-12.0, -7.75), u1(-12.35, -8.1),
                  u1(-12.35, -12.705), u1(-10.688, -12.705)]),
    ("/QSPI_SS", [u1(-8.7, -7.75), u1(-8.7, -7.11)]),
    (GND, [u1(-10.688, -8.895), u1(-9.3, -8.895)]),
]
SPINE = [(V33, [u1(-0.4, -3.45), u1(-0.4, -4.3), u1(-1.725, -5.625), u1(-1.725, -9.88), u1(-1.725, -10.92), u1(-1.725, -12.705),
                u1(-3.512, -12.705)]),
         (V33, [u1(-1.725, -9.88), u1(-0.95, -9.88)]), (V33, [u1(-1.725, -10.92), u1(-0.95, -10.92)])]
# console-rp's ties round U1's block, which keep their places to it: pin 1's 3V3 into the ring's
# corner; C9's 3V3 to C13's; C14's ground up to a via; C12's and C8's ground past C9's to Raspberry
# Pi's ground via; R1's 3V3 on to C9's and C13's; C3's ground to a via. And the USB-C's: D- from U2's
# pin 4 to the CH343P's pin 8, U2's ground to a via in its middle, VBUS from its pin 5 to a via.
TIES = [(V33, [u1(-3.45, -2.8), u1(-2.75, -2.75)]),
        (V33, [u1(6.005, -1.8), u1(6.01, -3.0)]), (GND, [u1(-0.95, -11.88), u1(-0.95, -12.8)]),
        (GND, [u1(7.56, -0.6), u1(7.56, -3.1), u1(7.6, -3.5)]), (GND, [u1(6.965, -1.8), u1(7.56, -1.8)]),
        (V33, [u1(4.2, -7.375), u1(4.75, -7.375), u1(5.55, -8.175)]), (GND, [u1(4.2, -4.575), u1(4.75, -4.575), u1(5.3, -5.125)]),
        (V33, [u1(5.55, -8.175), u1(6.01, -7.715), u1(6.01, -3.0)]),
        ("/USB_D-", [jm(0.95, -8.6375), jm(0.95, -9.613), jm(0.25, -10.312)]),
        (GND, [jm(0, -6.3625), jm(0, -7.0), jm(-0.5, -7.5)]), (VBUS, [jm(0, -8.6375), jm(0.2, -8.4375), jm(0.2, -7.5), jm(1.9, -7.5)]),
        # the 100n row's ground pads, each walled in by the escapes, to a via above it; and C4's 3V3 to pin 1
        (GND, [(18.6, 54.04), (18.6, 53.15)]), (GND, [(21.0, 54.045), (21.0, 53.15)]), (GND, [(23.4, 54.04), (23.4, 53.15)]),
        (V33, [(23.4, 54.99), (23.4, 55.6), (22.8, 56.2), pin(1)])]
# SWCLK, SWDIO and RUN out from pins 24-26 past the DVDD copper, as Raspberry Pi's: three 45-degree
# lines away from the chip, here down and left; SWCLK and SWDIO on into pin 1 of their 100R, RUN to
# its via, which takes it to its pad on the back
SWD = [("/RUN", [u1(1.2, 3.45), u1(1.2, 4.5), u1(3.1, 6.4), u1(3.6, 6.4)]),
       ("/SWDIO", [u1(0.8, 3.45), u1(0.8, 4.7), u1(3.1, 7.0), u1(4.0, 7.0), (13.0, 66.99)]),
       ("/SWCLK", [u1(0.4, 3.45), u1(0.4, 4.9), u1(3.1, 7.6), u1(4.0, 7.6), (11.9, 65.5), (11.9, 66.99)])]
# Out of U1's top, left and bottom edges, where the first routes left SDA, SDA2, D0, D2 and the LED
# open, or necked LCD_DC to 0.12 mm: Raspberry Pi's 100n row (C5, C10, C4) stands 2.3 mm above the
# top edge's pads, and C8 under pin 37. The screen's four from the top edge and RESET from the left
# go up and left past C5 into one column, 0.35 mm apart, and straight up it to y 43, RESET out of it
# at y 44.7 to its via (RAILS takes all five on to J2); pins 7-10 rise straight through the 1.8 mm
# between C5 and C10, KEY2_EN on to its via, D2 on up (RAILS); D1 steps right past C10's DVDD via, D0
# past D1, between C10 and C4, to its via (RAILS takes both on); KEY 2's bus leaves the left edge at
# 45 degrees, the two staggered so each keeps 0.2 mm from the next, clear of C6 and its 3V3 line, and
# the backlight with them, then up 0.7 mm left of the screen's column to its via (RAILS takes it on);
# the LED goes down past C8's left into R12. 0.15 mm, as Raspberry Pi's; the router takes the rest on
# from their ends.
ESCAPE = [("/LCD_MOSI", [pin(15), (17.2, 57.0), (15.8, 55.6), (15.8, 43.0)]),
          ("/LCD_SCK", [pin(14), (17.6, 56.9), (16.15, 55.45), (16.15, 43.0)]),
          ("/LCD_CS", [pin(13), (18.0, 56.8), (16.5, 55.3), (16.5, 43.0)]),
          ("/LCD_DC", [pin(12), (18.4, 56.7), (16.85, 55.15), (16.85, 43.0)]),
          ("/LCD_RST", [pin(16), (16.05, 58.2), (15.45, 57.6), (15.45, 44.7), (14.95, 44.2)]),
          ("/KEY2_EN", [pin(10), (19.2, 52.45), (18.75, 52.0)]), ("/BTN_D2", [pin(9), (19.6, 53.3)]),
          ("/SCL", [pin(8), (20.0, 53.3)]), ("/SDA", [pin(7), (20.4, 53.3)]),
          ("/BTN_D1", [pin(5), (21.2, 56.95), (21.65, 56.5), (21.65, 53.3)]),
          ("/BTN_D0", [pin(4), (21.6, 57.05), (22.1, 56.55), (22.1, 51.75), (21.85, 51.5)]),
          ("/LCD_BL", [pin(17), (15.95, 58.6), (14.75, 57.4), (14.75, 50.4)]),
          ("/SDA2", [pin(18), (15.85, 59.0), (13.35, 56.5)]), ("/SCL2", [pin(19), (15.75, 59.4), (12.85, 56.5)]),
          ("/LED", [pin(37), (19.6, 65.6), (18.95, 66.25), (18.95, 73.0)])]
def j2(x, y):
    """A point given from J2's centre, as it's placed (turned 90, the pads to the left, pin 1 lowest)."""
    return round(AT["J2"][0] + x, 4), round(AT["J2"][1] + y, 4)


# Drawn where three routes in a row left a net open or a pad cut off (net, layer, width, [points]):
# - the regulator's output, which no route joined to the rest of 3V3: U3's pin 2 to its tab, the tab
#   to C19, and 0.4 mm up from the tab to console-rp's 3V3 tie from R1 to C13;
# - KEY 2's switch, whose ground pads the routes walled in: one ground line from R20 through C28,
#   U9's pins 2 and 5 (ILIM), C29 and on to U10's pin 2, with a via under C29; IN to C28, OUT to C29
#   and EN to R20, each beside its pin;
# - the backlight's line, which no route took across the screen's lines from the left edge: from its
#   escape's via, under all the lines that leave U1's top on the back at y 50.4, up to y 48, along it
#   over the flash's lines and under U5, and into R11 and R10;
# - KEY 2's bus, where a route took SCL2 round U10's right side to the holes and walled SDA2 off from
#   U10: both straight up from their escapes into U10's right pins, SDA2 above, and U10's 3V3 pin out
#   between them to a via;
# - C22's ground pad, which the link's two lines walled in on the left and above: up to a via;
# - KEY2_EN and D0, which cross under the screen's column on the back, below the backlight's line:
#   a route that ran D0 on the back along y 51.5 and up beside the column left KEY2_EN, SCK and the
#   key's 3V3 open. KEY2_EN on the back at y 52 to a via by R20; D0 at y 51.1 to a via left of the
#   backlight's, then up the front at x 13.6 and into SW1; and U10's 3V3 via on east on the back at
#   y 47.2 to C23, so the key's corner has 3V3 under the column;
# - 3V3 to the north and to the CH343P, which routes left in islands: from C6 up beside SCL2 to a
#   via and on the back into U10's 3V3 via; from C7 down to U4's pin 1 and C22, over TP5, which a
#   via off it joins (the route that drew the rest left TP5 open);
# - the screen's five from the column to J2, where a route left MOSI no way in: the pads take them
#   from the left in the order CS, 3V3, SCK, MOSI, DC, RESET, and the column has them RESET, MOSI,
#   SCK, CS, DC. RESET goes under the rest on the back to a via below its stub; CS on the back too,
#   right of RESET, to a via above pin 7's line, so the two slow lines run beside the front's three
#   and not under them; MOSI crosses under SCK just below J2. 3V3 runs up the front beside them from
#   a via on the back's 3V3 at y 47.2, to pin 7, C24 and C25; LEDA goes into a via under the housing;
# - D2, which the column, I2C0 and D1 walled in: straight up between SW2's pads and over SW2 to SW3;
# - SCL, which leaves the column left of SDA and has its pads below SDA's, so a route took it 61 mm up
#   round SW2 and back: up the column past where SDA turns off, to a via, on the back north of D1's
#   via and under R6 and R7 to a via between R7 and C23, and into R7 (drawn in place after the route).
RAILS = [(V33, "F.Cu", 0.4, [(23.85, 82.0), (30.15, 82.0)]), (V33, "F.Cu", 0.4, [(30.15, 82.95), (32.9, 82.95)]),
         (V33, "F.Cu", 0.4, [(30.15, 82.0), (30.15, 71.66), (25.5, 67.01)]),
         (GND, "F.Cu", 0.3, [(1.75, 50.49), (1.75, 49.6), (3.2625, 49.6), (5.5375, 49.6), (7.0, 49.6), (8.4625, 49.6)]),
         (GND, "F.Cu", 0.3, [(7.0, 49.6), (7.0, 50.65)]),
         (V33, "F.Cu", 0.25, [(1.75, 48.64), (3.2625, 48.65)]), ("/VKEY", "F.Cu", 0.25, [(5.5375, 48.65), (7.0, 48.64)]),
         ("/KEY2_EN", "F.Cu", 0.15, [(1.75, 51.51), (2.75, 51.51), (3.2625, 51.0), (3.2625, 50.55)]),
         ("/LCD_BL", "B.Cu", 0.2, [(14.75, 50.4), (23.6, 50.4)]),
         ("/LCD_BL", "F.Cu", 0.2, [(23.6, 50.4), (23.6, 48.0), (35.3, 48.0), (36.89, 46.41), (36.89, 41.3)]),
         ("/SCL2", "F.Cu", 0.2, [(12.85, 56.5), (12.85, 51.25), (12.15, 50.55), (10.7375, 50.55)]),
         ("/SDA2", "F.Cu", 0.2, [(13.35, 56.5), (13.35, 50.0), (12.0, 48.65), (10.7375, 48.65)]),
         (V33, "F.Cu", 0.25, [(10.7375, 49.6), (11.9, 49.6)]),
         (GND, "F.Cu", 0.25, [jm(-3.4, -14.88), jm(-3.4, -15.8)]),
         ("/KEY2_EN", "B.Cu", 0.2, [(18.75, 52.0), (3.0, 52.0), (2.75, 52.25)]),
         ("/KEY2_EN", "F.Cu", 0.2, [(2.75, 52.25), (2.75, 51.51)]),
         ("/BTN_D0", "B.Cu", 0.2, [(21.85, 51.5), (21.45, 51.1), (14.05, 51.1)]),
         ("/BTN_D0", "F.Cu", 0.2, [(14.05, 51.1), (14.05, 49.5), (13.6, 49.05), (13.6, 30.0), (12.6, 29.0), (11.875, 29.0)]),
         (V33, "B.Cu", 0.25, [(11.9, 49.6), (14.3, 47.2), (23.82, 47.2)]),
         (V33, "F.Cu", 0.25, [(23.82, 47.2), (24.52, 46.5)]),
         (V33, "F.Cu", 0.25, [(14.395, 59.2), (14.395, 58.611), (12.45, 56.666), (12.45, 51.9), (11.9, 51.35)]),
         (V33, "B.Cu", 0.25, [(11.9, 51.35), (11.9, 49.6)]),
         (V33, "F.Cu", 0.25, [(16.0, 66.21), (15.5, 66.21), (14.723, 66.987), (14.723, 68.364), (10.013, 73.074),
                              (10.013, 75.35)]),
         (V33, "F.Cu", 0.25, [(10.013, 73.98), (8.6, 73.98)]),
         (V33, "B.Cu", 0.25, [(14.0, 69.087), (13.16, 70.0)]),
         ("/LCD_MOSI", "F.Cu", 0.15, [(15.8, 43.0), (14.395, 41.595), (14.395, 21.2), (13.425, 20.23), (13.425, 13.42)]),
         ("/LCD_MOSI", "B.Cu", 0.15, [(13.425, 13.42), (14.545, 12.3)]),
         ("/LCD_MOSI", "F.Cu", 0.15, [(14.545, 12.3), (14.545, 11.9), (14.895, 11.55), j2(-1.25, -0.25)]),
         ("/LCD_SCK", "F.Cu", 0.15, [(16.15, 43.0), (16.15, 42.855), (14.745, 41.45), (14.745, 21.0), (14.0, 20.255),
                                     (14.0, 11.4), (14.35, 11.05), j2(-1.25, -0.75)]),
         ("/LCD_CS", "F.Cu", 0.15, [(16.5, 43.0), (16.5, 42.2), (16.3, 42.0)]),
         ("/LCD_CS", "B.Cu", 0.15, [(16.3, 42.0), (16.3, 14.5), (15.3, 13.5), (15.3, 9.95)]),
         ("/LCD_CS", "F.Cu", 0.15, [(15.3, 9.95), (15.4, 10.05), j2(-1.25, -1.75)]),
         ("/LCD_DC", "F.Cu", 0.15, [(16.85, 43.0), (16.85, 41.3), (15.095, 39.545), (15.095, 12.4), (15.445, 12.05),
                                    j2(-1.25, 0.25)]),
         ("/LCD_RST", "B.Cu", 0.15, [(14.95, 44.2), (15.6, 43.55), (15.6, 15.455), (15.75, 15.305)]),
         ("/LCD_RST", "F.Cu", 0.15, [(15.75, 15.305), j2(-2.0, 3.2)]),
         (V33, "F.Cu", 0.25, [(14.3, 47.2), (14.3, 44.0), (14.0, 43.7), (14.0, 21.4), (12.8, 20.2), (12.8, 8.0), (13.4, 7.4),
                              (14.52, 7.4), (14.52, 6.3)]),
         (V33, "F.Cu", 0.25, [(12.8, 10.55), j2(-1.25, -1.25)]),
         ("/LCD_LEDA", "F.Cu", 0.2, [j2(-1.25, 1.75), (16.75, 13.55), (17.3, 14.1)]),
         ("/BTN_D2", "F.Cu", 0.2, [(19.6, 53.3), (19.6, 22.0), (20.2, 21.4), (27.5, 21.4), (28.125, 22.025), (28.125, 23.0)]),
         ("/SCL", "F.Cu", 0.2, [(20.0, 53.3), (20.0, 45.2), (20.5, 44.7)]),
         ("/SCL", "B.Cu", 0.2, [(20.5, 44.7), (20.5, 43.4), (21.0, 42.9), (24.8, 42.9), (25.5, 43.6), (25.5, 45.0)]),
         ("/SCL", "F.Cu", 0.2, [(25.5, 45.0), (25.51, 43.9)])]
# The USB-C's D+ and D- into U2 and on to the CH343P, and VBUS out of U2's middle, console-rp's drawn
# block (from its short bar's first route, net, layer, width, [points]), turned back to J1 facing down
USB = [("/USB_D+", "F.Cu", 0.2, [jd(7.645, 50.75), jd(8.412, 50.75), jd(8.667, 51.005), jd(8.667, 51.65)]),
       ("/USB_D+", "F.Cu", 0.15, [jd(8.667, 51.65), jd(7.745, 51.65), jd(7.645, 51.75)]),
       ("/USB_D+", "F.Cu", 0.2, [jd(8.667, 51.005), jd(9.622, 50.05), jd(9.963, 50.05)]),
       ("/USB_D+", "F.Cu", 0.2, [jd(9.963, 50.05), jd(10.158, 49.854), jd(12.042, 49.854), jd(12.237, 50.05), jd(12.493, 50.05),
                                 jd(12.844, 50.4)]),
       ("/USB_D+", "F.Cu", 0.15, [jd(12.844, 50.4), jd(13.024, 50.581), jd(13.222, 50.581), jd(13.222, 50.65), jd(13.813, 50.65),
                                  jd(13.912, 50.75)]),
       ("/USB_D-", "F.Cu", 0.2, [jd(7.645, 51.25), jd(6.9, 51.25), jd(6.791, 51.141), jd(6.63, 50.979), jd(6.63, 50.35)]),
       ("/USB_D-", "F.Cu", 0.15, [jd(6.63, 50.35), jd(7.546, 50.35), jd(7.645, 50.25)]),
       ("/USB_D-", "F.Cu", 0.2, [jd(6.791, 51.141), jd(6.447, 51.485)]),
       ("/USB_D-", "B.Cu", 0.2, [jd(6.447, 51.485), jd(5.931, 51.485), jd(5.364, 52.052), jd(5.364, 52.523), jd(5.715, 52.874),
                                 jd(9.963, 52.874)]),
       ("/USB_D-", "F.Cu", 0.2, [jd(9.963, 52.874), jd(9.963, 51.95)]),
       ("/USB_D-", "F.Cu", 0.2, [jd(9.963, 52.874), jd(10.22, 52.874), jd(10.825, 53.478), jd(11.347, 53.478), jd(12.237, 52.588),
                                 jd(12.237, 51.95)]),
       (VBUS, "B.Cu", 0.25, [jd(11.1, 52.9), jd(10.477, 52.277), jd(5.946, 52.277)]),
       (VBUS, "B.Cu", 0.25, [jd(10.477, 52.277), jd(12.093, 50.661), jd(12.093, 49.899), jd(14.466, 47.526), jd(15.093, 47.526),
                             jd(15.225, 47.658)]),
       (VBUS, "F.Cu", 0.25, [jd(15.225, 47.658), jd(15.225, 48.405), jd(15.15, 48.48), jd(15.15, 49.012)]),
       (VBUS, "F.Cu", 0.25, [jd(5.946, 52.277), jd(7.119, 53.45), jd(7.645, 53.45)]),
       (VBUS, "F.Cu", 0.25, [jd(5.946, 52.277), jd(5.946, 52.019), jd(5.65, 51.724), jd(5.65, 51.246), jd(5.946, 50.951),
                             jd(5.946, 49.723), jd(7.119, 48.55), jd(7.645, 48.55)])]
USB_VIAS = [("/USB_D-", jd(6.447, 51.485)), ("/USB_D-", jd(9.963, 52.874)), (VBUS, jd(5.946, 52.277)), (VBUS, jd(15.225, 47.658))]
# For the route only: the back from U2's ground via to the board's edge, beside VBUS's line, stays ground
AROUND_U2 = [jd(0.0, 44.6), jd(13.6, 44.6), jd(13.6, 46.9), jd(11.7, 48.8), jd(11.7, 50.4), jd(10.3, 51.8), jd(0.0, 51.8)]


# J2's pin 2, the panel's only ground, to a via under the housing (console-rp's is beside the pads,
# where it and a route's via boxed RESET in); and RESET out of the row and down, 0.35 mm off the
# pads' ends, for the router to take on
PANEL_PINS = [(GND, 0.2, [j2(-1.25, 1.25), j2(-0.2, 1.25)]),
              ("/LCD_RST", 0.15, [j2(-1.25, 0.75), j2(-2.0, 0.75), j2(-2.0, 3.2)])]

# (net, where, locked): console-rp's ground vias for pads the pour can't reach otherwise, which keep
# their places to U1 and J1: the flash's ground pin's; three ground ties beside C14,
# from the back's ground under U1 and the flash to the front's pour; C14's, C17's and C3's; the
# CH343P's, in its exposed pad (jlc_spec says so); U2's, and VBUS out of U2; J2's pin 2's; and the
# end of RUN's fan-out, which goes on on the back to its pad.
HAND_VIAS = [(GND, u1(-9.3, -8.895), True),
             (GND, u1(-2.6, -13.7), True), (GND, u1(-1.4, -13.7), True), (GND, u1(-0.2, -13.7), True),
             (GND, u1(-0.95, -12.8), True), ("/RUN", u1(3.6, 6.4), True), (GND, u1(-0.2, -9.4), True),
             (GND, (AT["U4"][0], AT["U4"][1] + 0.55), True), (GND, u1(5.3, -5.125), True),
             (GND, jm(-0.5, -7.5), True), (VBUS, jm(1.9, -7.5), True), (GND, j2(-0.2, 1.25), True), (GND, (7.0, 50.65), True),
             (GND, (18.6, 53.15), True), (GND, (21.0, 53.15), True), (GND, (23.4, 53.15), True),   # KEY 2's switch's; C5's, C10's, C4's
             ("/LCD_BL", (14.75, 50.4), True), ("/LCD_BL", (23.6, 50.4), True),                     # the backlight's way under
             (V33, (11.9, 49.6), True), (GND, jm(-3.4, -15.8), True),                                # U10's 3V3 pin's, C22's
             ("/KEY2_EN", (18.75, 52.0), True), ("/KEY2_EN", (2.75, 52.25), True),                   # under the column
             ("/BTN_D0", (21.85, 51.5), True), ("/BTN_D0", (14.05, 51.1), True), (V33, (23.82, 47.2), True),
             (V33, (11.9, 51.35), True), (V33, (14.3, 47.2), True),                                  # 3V3 from C6; up the column
             (V33, (14.0, 69.087), True),                                                            # TP5's, off the line to U4
             ("/LCD_RST", (14.95, 44.2), True), ("/LCD_RST", (15.75, 15.305), True),                 # the screen's on the back
             ("/LCD_CS", (16.3, 42.0), True), ("/LCD_CS", (15.3, 9.95), True),
             ("/LCD_MOSI", (13.425, 13.42), True), ("/LCD_MOSI", (14.545, 12.3), True), ("/LCD_LEDA", (17.3, 14.1), True),
             ("/SCL", (20.5, 44.7), True), ("/SCL", (25.5, 45.0), True)]                              # SCL under SDA

# Pads joined to the ground pours solid, not by thermal spokes: C1's and C2's, inside Raspberry Pi's
# pours as theirs are, and J1's, C17's, U9's and C28's, between other copper, where spokes don't fit
SOLID = {("C1", "2"), ("C2", "2"), ("C17", "2"), ("J1", "A1"), ("J1", "A12"), ("J1", "B1"), ("J1", "B12"),
         ("U9", "2"), ("U9", "5"), ("C28", "2")}
# and by spokes: U7's exposed pad, which KiCad's footprint joins solid as a heatsink; the Trust M goes
# on by hand, with hot air, and a solid pad in both pours soaks up the heat
SPOKED = {("U7", "11")}

# Raspberry Pi's areas round U1 (their frame), where only their nets' copper belongs: the regulator's
# corner on the front, under the chip on the back, the crystal's corner on the front and only ground
# on the back under the crystal (UNDER_Y1). check_rpi reads the routed board.
RPI_AREAS = [
    ("the regulator's corner", "F.Cu", {"/VREG_LX", "/DVDD", "/VREG_AVDD", V33, GND},
     [(1.0, -3.0), (3.2, -3.0), (4.65, -4.45), (4.65, -6.95), (3.3, -6.95), (3.3, -8.15), (0.85, -8.15), (0.85, -6.3),
      (0.25, -6.3), (0.25, -4.85), (1.0, -4.85)]),
    ("under U1", "B.Cu", {"/DVDD", GND}, [(-2.95, -2.95), (2.95, -2.95), (2.95, 2.95), (-2.95, 2.95)]),
    ("the crystal's corner", "F.Cu", {"/XIN", "/XOUT", "/XTAL_OUT", GND},
     [(-2.8, 8.0), (2.8, 8.0), (3.2, 8.4), (3.2, 14.7), (-3.2, 14.7), (-3.2, 8.4)]),
    ("under the crystal", "B.Cu", {GND}, [(-2.2, 7.9), (2.2, 7.9), (2.2, 14.6), (-2.2, 14.6)]),
]
# The router keeps off the back under U1, but for a notch round each of Raspberry Pi's four DVDD
# tracks out from their vias (console-rp's)
UNDER_U1 = [(-2.95, -2.95), (0.0, -2.95), (0.0, -1.65), (1.0, -1.65), (1.0, -2.95), (2.95, -2.95),
            (2.95, -0.9), (1.65, -0.9), (1.65, 0.1), (2.95, 0.1), (2.95, 2.95), (0.7, 2.95), (0.7, 1.65),
            (-0.3, 1.65), (-0.3, 2.95), (-2.95, 2.95), (-2.95, -0.3), (-1.65, -0.3), (-1.65, -1.3), (-2.95, -1.3)]
UNDER_Y1 = RPI_AREAS[3][3]
# For the route only (console-rp's): the router keeps off the back round U1 and under the flash's
# lines, so the back there stays one ground: under U1's exposed pad, out to Raspberry Pi's ground vias
# by the regulator, and under the QSPI lines to the flash.
AROUND_U1 = [(-12.8, -13.8), (-2.0, -13.8), (-2.0, -12.2), (6.0, -12.2), (6.0, -6.0), (4.4, -6.0), (4.4, 4.0),
             (-4.0, 4.0), (-4.0, -2.3), (-12.8, -2.3)]
# For the route only: no track under U8's body, where every route necked SCL2 to 0.1 mm between VKEY
# and pin 5; and none between the ends of J2's pads and its housing, where every route necked
# LCD_MOSI past the next pads' ends. The router leaves U8's pins from their outer ends, J2's from theirs.
UNDER_U8 = [(3.45, 32.9), (6.15, 32.9), (6.15, 37.5), (3.45, 37.5)]
PAST_J2 = [j2(-0.7, -2.1), j2(0.7, -2.1), j2(0.7, 2.1), j2(-0.7, 2.1)]
# And none on the back within 1.65 mm of J4's ground hole, where every route starved its spokes: the
# pad's 0.85, the relief's 0.3 gap, the pour's least 0.2 and its 0.2 clearance, half a track
SPOKE_RING = 1.65
FID_RING = 1.3            # no track and no via this close to a fiducial: its 2 mm mask opening and 0.6 mm clearance
EDGE_KEEP = 0.6           # for the route only: no track this close to the board's edge (JLCPCB's V-cut wants 0.4 at least)
ROUTE_ONLY = "route only: "      # rule areas the router obeys that the routed board drops (tidy)
HOLE_RING = 2.5           # no track and no via this close to a hole's centre: an M2 screw's head and washer, 5 mm across

# Stock footprints whose 3D model KiCad's library doesn't ship: a part of the same size and pads
# stands in, in the board and so in the renders
STANDIN = {
    "SW_Push_1P1T_XKB_TS-1187A": "${KICAD10_3DMODEL_DIR}/Button_Switch_SMD.3dshapes/SW_SPST_TL3342.step",
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12":
        "${KICAD10_3DMODEL_DIR}/Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step",
}
ROUTE_NOTE = "Routed by tools/keypcb route; the copper round U1 is Raspberry Pi's, turned with it (README.md)."
WARN_TEXT = "EXPERIMENTAL HARDWARE COSIGNER"


def fp_lib(lib):
    return MONO_FP if lib == "mono" else MARK if lib == "picoquorum" else os.path.join(KIFP, lib + ".pretty")


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
    """The panel as it sits: foam pads, the backlight frame, the glass and its dark active area, set
    1.445 mm away from the ribbon, and the ribbon folding under into J2. Its origin is the glass's
    centre (LCD1's footprint)."""
    os.makedirs(SHAPES, exist_ok=True)
    gw, gh = PANEL["glass"]
    f, t, p = PANEL["foam"], PANEL["thick"], PANEL["pad"]
    hw, hh, rw = gw / 2, gh / 2, PANEL["ribbon"] / 2
    pads = [_box(sx * hw - (p if sx > 0 else 0), sy * hh - (p if sy > 0 else 0), 0, sx * hw + (0 if sx > 0 else p), sy * hh + (0 if sy > 0 else p), f)
            for sx in (-1, 1) for sy in (-1, 1)]
    aw, ah = PANEL["active"]
    ax = -PANEL["active_off"]
    zin = hw - PANEL["reach"]                     # the ribbon's end, from the glass's centre
    rib = _box(hw, -rw, f, hw + 0.6, rw, f + 0.1) + _box(hw + 0.5, -rw, 0.45, hw + 0.6, rw, f + 0.1) \
        + _box(zin, -rw, 0.45, hw + 0.6, rw, 0.55)
    shapes = [_wrl_shape(sum(pads, []), (0.92, 0.92, 0.88)),
              _wrl_shape(_box(-hw, -hh, f, hw, hh, f + t - 0.3), (0.75, 0.76, 0.78)),
              _wrl_shape(_box(-hw, -hh, f + t - 0.3, hw, hh, f + t), (0.02, 0.02, 0.03)),
              _wrl_shape(_box(ax - aw / 2, -ah / 2, f + t, ax + aw / 2, ah / 2, f + t + 0.01), (0.10, 0.12, 0.16)),
              _wrl_shape(rib, (0.85, 0.45, 0.08))]
    with open(os.path.join(SHAPES, "LCD_1.14in_240x135_on_tape.wrl"), "w") as fh:
        fh.write("#VRML V2.0 utf8\n# The 1.14in panel on its tape. Written by gen_mono.py\n")
        fh.writelines(shapes)
    zif = [_wrl_shape(_box(-3.0, -1.6, 0, 3.0, 1.65, 0.75), (0.93, 0.88, 0.75)),
           _wrl_shape(_box(-3.0, 0.9, 0.75, 3.0, 1.65, 1.0), (0.08, 0.08, 0.08))]
    with open(os.path.join(SHAPES, "FPC_ZIF_8P_HDGC_0.5K-HX-8PWB.wrl"), "w") as fh:
        fh.write("#VRML V2.0 utf8\n# HDGC 0.5K-HX-8PWB, a box from its drawing's outline. Written by gen_mono.py\n")
        fh.writelines(zif)


def write_footprints():
    """mono.pretty: Raspberry Pi's footprints (console-rp's copy, MIT, lib/RPI-MINIMAL-LICENSE.txt),
    console-s3's ZIF footprint with a 3D body, and the panel as a board-only part; and
    picoquorum.pretty, the mark."""
    os.makedirs(MONO_FP, exist_ok=True)
    os.makedirs(MARK, exist_ok=True)
    src = os.path.join(CONSOLE_RP, "lib", "pqrp.pretty")
    for fn in sorted(os.listdir(src)):
        if fn.startswith("RPi_"):
            shutil.copy(os.path.join(src, fn), MONO_FP)
    shutil.copy(os.path.join(CONSOLE_RP, "lib", "RPI-MINIMAL-LICENSE.txt"), LIB)
    shutil.copy(os.path.join(REPO, "hardware", "archive", "console-pocket", "lib", "picoquorum.pretty", "PicoQuorum_Mark.kicad_mod"), MARK)
    zsrc = os.path.join(REPO, "hardware", "prototypes", "console-s3", "lib", "pqs3.pretty", "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB.kicad_mod")
    zif = open(zsrc).read().replace(
        "\t(embedded_fonts no)",
        '\t(model "${KIPRJMOD}/../lib/mono.3dshapes/FPC_ZIF_8P_HDGC_0.5K-HX-8PWB.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n'
        "\t(embedded_fonts no)")
    with open(os.path.join(MONO_FP, "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB.kicad_mod"), "w") as fh:
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
    with open(os.path.join(MONO_FP, "LCD_1.14in_240x135_on_tape.kicad_mod"), "w") as fh:
        fh.write(f"""(footprint "LCD_1.14in_240x135_on_tape" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")
\t(descr "The 1.14in 240x135 ST7789 panel's glass ({gw} x {gh} mm) on {PANEL['foam']} mm foam pads at its corners (F.Fab). No pads: the ribbon goes to J2. Board only")
\t(property "Reference" "LCD1" (at 0 {-hh - 1.2} 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 0.8 0.8) (thickness 0.12))))
\t(property "Value" "1.14in 240x135" (at 0 0 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
\t(attr board_only exclude_from_pos_files exclude_from_bom)
{chr(10).join(lines)}
\t(model "${{KIPRJMOD}}/../lib/mono.3dshapes/LCD_1.14in_240x135_on_tape.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
\t(embedded_fonts no)
)
""")
    with open(os.path.join(OUT, "fp-lib-table"), "w") as fh:
        fh.write('(fp_lib_table\n  (version 7)\n'
                 '  (lib (name "mono")(type "KiCad")(uri "${KIPRJMOD}/../lib/mono.pretty")(options "")(descr "Mono\'s own footprints"))\n'
                 '  (lib (name "picoquorum")(type "KiCad")(uri "${KIPRJMOD}/../lib/picoquorum.pretty")(options "")(descr "the mark"))\n)\n')


# What an owner can count on the board: each fitted part's group, from its footprint's name, the
# first group whose key is in it
CENSUS = [("QFN", "QFN"), ("SOIC-8", "SOIC-8"), ("SOT-223", "SOT-223"), ("SOT-23-6", "SOT-23-6"), ("SOT-23", "SOT-23"), ("crystal", "Crystal"),
          ("inductor", "_L_"), ("USB-C", "USB_C"), ("ZIF", "FPC_ZIF"), ("buttons", "SW_Push"), ("LED", "LED_"),
          ("0805", "_0805"), ("0603", "_0603"), ("0402", "0402")]


def census():
    """The parts JLCPCB fits (not the holes, the pads, the panel, the mark or what isn't fitted), grouped: [(group, count)]."""
    n = {}
    for p in PARTS:
        if p.get("dnp") or not p.get("bom", True):
            continue
        fp = p["fp"].split(":")[1]
        group = next((g for g, key in CENSUS if key in fp), None)
        if group is None:
            sys.exit(f"{NAME}: the census has no group for {p['ref']} ({fp})")
        n[group] = n.get(group, 0) + 1
    return [(g, n[g]) for g, _ in CENSUS if g in n]


def census_lines(width=30):
    """The census as silkscreen lines, about width characters each."""
    groups = census()
    lines, line = [f"{sum(c for _, c in groups)} parts, every one on the front:"], ""
    for i, (g, c) in enumerate(groups):
        item = f"{c} {g}" + ("," if i < len(groups) - 1 else "")
        if line and len(line) + 1 + len(item) > width:
            lines.append(line)
            line = item
        else:
            line = f"{line} {item}" if line else item
    lines.append(line)
    return lines + ["and the screen, fitted by hand"]


def current_lines():
    """The current to expect, by the USB-C: a USB meter is the radio detector. All the USB-C feeds:
    U3's load at most (jlc_spec), the backlight's 17 mA (R8 at 5.5 V, the LED's 2.9 V least) and the
    CH343P's own supply, 20 mA allowed (not measured), rounded up to 0.05 A."""
    amps = math.ceil((max(jlc_spec()["regulator"]["amps"]) + 0.017 + 0.020) / 0.05 - 1e-9) * 0.05
    return [f"under {amps:g} A at 5 V with KEY 2 empty:", "more, or bursts, is a part that isn't ours"]


def write_board(sh, nets):
    import pcbnew
    # rounded to the nanometre: VECTOR2I_MM truncates, and a via 1 nm off the end a route drew to it
    # fails JLCPCB's DRC (track_not_centered_on_via)
    mm = lambda x, y: pcbnew.VECTOR2I(round((OX + x) * 1e6), round((OY + y) * 1e6))
    b = pcbnew.BOARD()
    pad_net = {}
    for name, nodes in nets.items():         # unconnected pins too, on KiCad's unconnected-(...) nets, as the schematic
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        for node in nodes:
            pad_net[node] = name

    def place(fp, ref, x, y, r):
        fp.SetReference(ref)
        if fp.Reference().GetLayer() == pcbnew.F_SilkS:
            fp.Reference().SetLayer(pcbnew.F_Fab)     # 0402s too close for names: the silkscreen keeps labels only
        fp.SetPosition(mm(x, y))
        fp.SetOrientationDegrees(r)
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
            fp.Models().clear()            # not fitted: the site shows empty, its outline and pin 1 kept
        x, y, r = AT[p["ref"]]
        place(fp, p["ref"], x, y, r)
        if p["ref"] in BACK:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if p["ref"] == "J1":           # the plug's face, past the board's bottom edge: no silkscreen off the board
            for it in [i for i in fp.GraphicalItems() if i.GetLayer() == pcbnew.F_SilkS
                       and pcbnew.ToMM(i.GetBoundingBox().GetBottom()) > OY + H]:
                fp.Remove(it)
        for pad in fp.Pads():
            n = pad_net.get((p["ref"], pad.GetNumber()))
            if n:
                pad.SetNet(b.FindNet(n))
            if (p["ref"], pad.GetNumber()) in SOLID:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            elif (p["ref"], pad.GetNumber()) in SPOKED:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    place(pcbnew.FootprintLoad(MONO_FP, "LCD_1.14in_240x135_on_tape"), "LCD1", XC, YC, 0)
    logo = pcbnew.FootprintLoad(MARK, "PicoQuorum_Mark")
    logo.SetFPID(pcbnew.LIB_ID("picoquorum", "PicoQuorum_Mark"))
    place(logo, "LOGO1", XA, 81.2, 0)
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
    seg((r, TOP), (W - r, TOP)); seg((W, TOP + r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, TOP + r))

    # --- copper: ground pours on both sides; round U1, Raspberry Pi's copper as it is, turned, locked
    def track(net, layer, a, c, w):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(mm(*a)); t.SetEnd(mm(*c)); t.SetLayer(b.GetLayerID(layer)); t.SetWidth(pcbnew.FromMM(w))
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
        for x, y in pts:
            o.Append(mm(x, y))
        b.Add(z)
        return z

    edge = [(0, TOP), (W, TOP), (W, H), (0, H)]
    for layer in ("F.Cu", "B.Cu"):
        z = zone(edge, (layer,), GND)
        if layer == "F.Cu":         # not in the regulator's corner, where it left scraps between their pours
            corner = pcbnew.SHAPE_POLY_SET()
            corner.NewOutline()
            for qq in RPI_AREAS[0][3]:
                corner.Append(mm(*u1(*qq)))
            z.Outline().BooleanSubtract(corner)
    # their track ends and LINKS' 0.001 mm off their vias' centres (as rpi_minimal.json rounds them) go on the centres
    centres = [qq for qq in (VIA_MOVE.get(tuple(v["at"]), v["at"]) for v in RPI["vias"]) if qq]
    snap = lambda e: next((c for c in centres if math.dist(c, e) < 0.005), e)
    for t in RPI["tracks"]:
        if (tuple(t["a"]), tuple(t["b"])) not in DROP:
            track(t["net"], t["layer"], u1(*snap(t["a"])), u1(*snap(t["b"])), t["w"])
    for v in RPI["vias"]:
        qq = VIA_MOVE.get(tuple(v["at"]), v["at"])
        if qq is None:
            continue
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(mm(*u1(*qq))); via.SetWidth(pcbnew.FromMM(v["dia"])); via.SetDrill(pcbnew.FromMM(v["drill"]))
        via.SetNet(b.FindNet(v["net"])); via.SetLocked(True)
        b.Add(via)
    for z in RPI["zones"]:
        zone([u1(*qq) for qq in z["pts"]], (z["layer"],), z["net"], z["priority"], z["clearance"], z["min_width"], z["solid"], z["thermal"])
    for net, pts in LINKS:
        for a, c in zip(pts, pts[1:]):
            track(net, "F.Cu", u1(*snap(a)), u1(*snap(c)), 0.15)
    for net, pts in FLASH + TIES + SWD + ESCAPE:
        for a, c in zip(pts, pts[1:]):
            track(net, "F.Cu", a, c, 0.15)
    for net, pts in SPINE:
        for a, c in zip(pts, pts[1:]):
            track(net, "F.Cu", a, c, 0.2)
    for net, layer, w, pts in USB + RAILS:
        for a, c in zip(pts, pts[1:]):
            track(net, layer, a, c, w)
    for net, w, pts in PANEL_PINS:
        for a, c in zip(pts, pts[1:]):
            track(net, "F.Cu", a, c, w)
    for net, qq, locked in HAND_VIAS + [(n, qq, True) for n, qq in USB_VIAS]:
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(mm(*qq)); via.SetWidth(pcbnew.FromMM(0.6)); via.SetDrill(pcbnew.FromMM(0.3))
        via.SetNet(b.FindNet(net)); via.SetLocked(locked)
        b.Add(via)
    zone([u1(*qq) for qq in UNDER_U1], ("B.Cu",), rule="U1: no tracks under it")
    zone([u1(*qq) for qq in UNDER_Y1], ("B.Cu",), rule="Y1: no tracks under it")
    # for the route only, as console-rp's: the router keeps out of the crystal's corner on the front
    # and off the back round U1. `gen-mono tidy` takes them off the routed board.
    zone([u1(*qq) for qq in RPI_AREAS[2][3]], ("F.Cu",), rule=ROUTE_ONLY + "the crystal's corner")
    zone([u1(*qq) for qq in AROUND_U1], ("B.Cu",), rule=ROUTE_ONLY + "round U1 and the flash, one ground on the back")
    zone(AROUND_U2, ("B.Cu",), rule=ROUTE_ONLY + "U2's ground via to the edge")
    zone(UNDER_U8, ("F.Cu",), rule=ROUTE_ONLY + "under U8's body")
    zone(PAST_J2, ("F.Cu",), rule=ROUTE_ONLY + "past the ends of J2's pads")
    x, y = AT["J4"][0] + 2.54, AT["J4"][1]       # J4's ground hole: no track on the back where its spokes go
    zone([(x + SPOKE_RING * math.cos(kk * math.pi / 8), y + SPOKE_RING * math.sin(kk * math.pi / 8)) for kk in range(16)],
         ("B.Cu",), rule=ROUTE_ONLY + "round J4's ground hole")
    e = EDGE_KEEP
    for i, (x0, y0, x1, y1) in enumerate(((0, TOP, W, TOP + e), (0, H - e, W, H), (0, TOP, e, H), (W - e, TOP, W, H))):
        zone([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], ("F.Cu", "B.Cu"),
             rule=ROUTE_ONLY + f"the edge {'top bottom left right'.split()[i]}")
    for h in ("H1", "H2", "H3", "H4"):              # the screws' heads: the pours may run under, behind the mask
        x, y, _ = AT[h]
        zone([(x + HOLE_RING * math.cos(kk * math.pi / 16), y + HOLE_RING * math.sin(kk * math.pi / 16)) for kk in range(32)],
             ("F.Cu", "B.Cu"), rule=f"{h}: no tracks")
    for f in ("FID1", "FID2", "FID3"):              # the router doesn't see a fiducial's clearance or mask opening
        x, y, _ = AT[f]
        zone([(x + FID_RING * math.cos(kk * math.pi / 8), y + FID_RING * math.sin(kk * math.pi / 8)) for kk in range(16)],
             ("F.Cu",), rule=f"{f}: no tracks")
    b.GetDesignSettings().SetAuxOrigin(mm(0, H))     # the fab files' origin: the bottom-left corner
    b.GetDesignSettings().SetGridOrigin(mm(0, H))
    arc((W, H - r), (W - k, H - k), (W - r, H)); arc((r, H), (k, H - k), (0, H - r)); arc((0, TOP + r), (k, TOP + k), (r, TOP))
    arc((W - r, TOP), (W - k, TOP + k), (W, TOP + r))

    def text(s, x, y, size, layer=pcbnew.F_SilkS, back=False, rot_=0, align=0, wide=None):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s); t.SetPosition(mm(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I_MM(wide or size, size)); t.SetTextThickness(pcbnew.FromMM(max(0.15, size * 0.15)))
        t.SetTextAngleDegrees(rot_)
        if align:
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if align < 0 else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
        if back:
            t.SetMirrored(True)
        b.Add(t)

    # silkscreen text 1.0 mm high at least, JLCPCB's least. The front keeps to the buttons' names and
    # the second key's site; the rest is on the back.
    for i, lab in enumerate(("D0", "D1", "D2")):
        text(lab, AT[f"SW{i + 1}"][0], BY + 4.8, 1.0)
    x4, y4, _ = AT["J4"]
    for i, lab in enumerate(("VK", "GND", "SCL", "SDA", "RST")):      # J4's holes, as the schematic, under them
        text(lab, x4 + 2.54 * i, y4 + 2.4, 1.0, wide=0.75)
        text(lab, x4 + 2.54 * i, y4 + 2.4, 1.0, pcbnew.B_SilkS, back=True, wide=0.75)
    text("KEY 2  I2C1  3.3 V", (x4 + x4 + 4 * 2.54) / 2, y4 - 2.3, 1.0, wide=0.8)    # midway, R18's silk to J4's
    # the back: the warning along the top; under the glass what isn't on this side, the name, the
    # revision, the Source Location; the jig's pads' names; the census and the current to expect
    text(WARN_TEXT, XA, TOP + 1.6, 1.0, pcbnew.B_SilkS, back=True, wide=0.85)
    for i, line in enumerate(("nothing is fitted on this side", "no radio: USB serial only")):
        text(line, XA, GY0 + 3.0 + 2.0 * i, 1.0, pcbnew.B_SilkS, back=True, wide=0.85)
    text(f"Picoquorum mono rev {REV} {DATE}", XA, GY0 + 9.4, 1.0, pcbnew.B_SilkS, back=True, wide=0.85)
    text("picoquorum.app", XA, GY0 + 11.8, 1.4, pcbnew.B_SilkS, back=True)           # also the Source Location
    text("CERN-OHL-W v2, Source Location as 4.1", XA, GY0 + 14.0, 1.0, pcbnew.B_SilkS, back=True, wide=0.8)
    for t_, x in TP_X.items():
        lab = next(p["value"] for p in PARTS if p["ref"] == t_)
        text(lab, x, TPY + (-1.9 if int(t_[2:]) % 2 else 1.9), 1.0, pcbnew.B_SilkS, back=True, wide=0.7)
    for i, line in enumerate(census_lines()):
        text(line, XA, 21.0 + 2.0 * i, 1.0, pcbnew.B_SilkS, back=True, wide=0.8)       # between H1 and H2
    for i, line in enumerate(current_lines()):                                       # under the jig's names, the mark under them
        text(line, XA, 74.2 + 2.0 * i, 1.0, pcbnew.B_SilkS, back=True, wide=0.8)
    text("ribbon folds under the glass into J2", (ZIF_X + GX1) / 2 + 1.0, YC + 3.0, 0.8, pcbnew.F_Fab)
    text(ROUTE_NOTE, W / 2, H + 2.0, 1.0, pcbnew.Cmts_User)
    pcbnew.SaveBoard(os.path.join(OUT, NAME + ".kicad_pcb"), b)


def tidy():
    """After `tools/keypcb route mono`: the route-only rule areas off the routed board.
    Nothing else is touched: they let the pours fill, so the fill stands."""
    import pcbnew
    path = os.path.join(OUT, NAME + ".kicad_pcb")
    b = pcbnew.LoadBoard(path)
    gone = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith(ROUTE_ONLY)]
    for z in gone:
        b.Delete(z)
    pcbnew.SaveBoard(path, b)
    print(f"  took {len(gone)} route-only rule area(s) off {os.path.relpath(path, REPO)}")


def is_routed():
    """Whether the board on disk has tracks the router put there: every track this script draws is locked.
    KiCad 10 writes (locked yes) inside a segment, after its width."""
    path = os.path.join(OUT, NAME + ".kicad_pcb")
    return os.path.exists(path) and any("(locked yes)" not in s for s in re.findall(r"\(segment\b.*?\n\t\)", open(path).read(), re.S))


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
          "silk_edge_clearance", "text_height", "text_thickness") + (() if routed else (
              "unconnected_items", "via_dangling", "track_dangling",
              "items_not_allowed",      # Raspberry Pi's crystal copper inside the route-only keep-out, till tidy
              "starved_thermal"))       # the placed board's pours, before the route's ground vias
    for v in rep.get("violations", []) + rep.get("unconnected_items", []) + rep.get("schematic_parity", []):
        seen[v["type"]] = seen.get(v["type"], 0) + 1
        if v["type"] not in ok:
            bad.append(f"DRC {v['type']}: " + "; ".join(i.get("description", "") for i in v.get("items", [])))
    # the glass: everything under it lower than the tape, nothing in the foam's corners
    for p in PARTS:
        x, y, _ = AT[p["ref"]]
        if GX0 <= x <= GX1 and GY0 <= y <= GY1 and p["ref"] not in BACK:
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
    for name, layer, nets, pts in RPI_AREAS:
        poly = pcbnew.SHAPE_POLY_SET()
        poly.NewOutline()
        for x, y in (u1(*qq) for qq in pts):
            poly.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
        lid = b.GetLayerID(layer)
        for t in b.GetTracks():
            if t.GetNetname() not in nets and t.IsOnLayer(lid) and poly.Collide(t.GetEffectiveShape(lid)):
                bad.append(f"{t.GetNetname()} {'via' if t.Type() == pcbnew.PCB_VIA_T else 'track'} in Raspberry Pi's area {name} ({layer})")


RENDERS = [  # name, kicad-cli pcb render options
    ("top", ["--side", "top", "--zoom", "1.0", "--width", "800", "--height", "1600"]),
    ("3q", ["--side", "top", "--rotate", "-38,0,-24", "--perspective", "--zoom", "0.8", "--width", "1400", "--height", "1400"]),
    ("bottom", ["--side", "bottom", "--zoom", "1.0", "--width", "800", "--height", "1600"]),
    ("under-glass", ["--side", "top", "--zoom", "1.0", "--width", "800", "--height", "1600"]),
]


def render():
    """KiCad's own 3D view (raytraced) into renders/, as JPEGs (macOS's sips)."""
    import pcbnew
    os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        bare = os.path.join(OUT, f"_{NAME}-under-glass.kicad_pcb")      # the panel lifted off
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


# What `tools/keypcb jlc mono` needs to know that the board file doesn't say, in its frame: mm from
# the bottom-left corner, y up. Heights (mm) are datasheets' or the usual for the package.
HEIGHT = {"C_0402_1005Metric": 0.55, "R_0402_1005Metric": 0.4, "RPi_C_0402": 0.55, "RPi_C_0402_wide": 0.55, "RPi_R_0402": 0.4,
          "C_0805_2012Metric": 1.25, "R_0603_1608Metric": 0.55, "LED_0603_1608Metric": 0.8, "SOT-23": 1.15, "SOT-23-6": 1.45,
          "SOT-223-3_TabPin2": 1.8, "RPi_L_Abracon_AOTA-B201610": 1.0, "RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias": 0.85,
          "WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm": 0.75, "SOIC-8_3.9x4.9mm_P1.27mm": 1.75, "SOIC-8_5.3x5.3mm_P1.27mm": 2.16,
          "Microchip_USON-10-1EP_3x3mm_P0.5mm_EP1.8x2.5mm": 0.6, "D_SOD-523": 0.7,
          "RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm": 0.8, "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB": 1.0,
          "SW_Push_1P1T_XKB_TS-1187A": 1.5, "USB_C_Receptacle_HRO_TYPE-C-31-M-12": 3.2,
          "Fiducial_1mm_Mask2mm": 0.05, "TestPoint_Pad_D1.5mm": 0.05}       # copper only


def jlc_spec():
    """The board's numbers for tools/jlc: the holes' rings, the regulator's heat, the nets whose
    return path to report, and the 3D fit of the panel."""
    up = lambda y: round(H - y, 4)
    rib = PANEL["ribbon"] / 2
    return {
        "edge": 0.3,
        "hole_ring": HOLE_RING,
        "via_in_pad": [{"pad": "U4.17", "why": "the CH343P's exposed pad and pin 2, shut in by its other pins, have no other way to ground: one via in the exposed pad"}],
        "thermal_vias": [{"pad": "U1.61", "why": "Raspberry Pi's nine 0.3 mm holes in the RP2350's exposed pad, 0.6 mm across like our vias"}],
        "jlc_allow": [{"type": "footprint_filters_mismatch", "ref": p["ref"], "why": "Raspberry Pi's footprint, or console-s3's ZIF: not a name the stock symbol's filters list"}
                      for p in PARTS if p["fp"].startswith("mono:")]
                     + [{"type": "footprint_type_mismatch", "ref": "U1", "why": "Raspberry Pi's footprint: an SMD part with plated holes in its exposed pad"},
                        {"type": "lib_footprint_mismatch", "ref": "J1", "why": "its silkscreen past the board's edge left out"},
                        *({"type": "lib_footprint_mismatch", "ref": r, "why": "not fitted: its 3D model left out, so the site shows empty"}
                          for r in ("U7", "U8", "D2", "J4")),
                        {"type": "missing_courtyard", "ref": "LCD1", "why": "the panel on tape over the parts: the fit check's glass stands in"}],
        "regulator": {"ref": "U3", "part": "LDL1117S33R", "vin": 5.0, "vout": 3.3, "amps": [0.06, 0.15], "theta_ja": 120,
                      "theta_note": "ST's datasheet (DocID030319): 120 C/W in SOT-223 on its test board's copper"},
        "return_nets": ["/USB_D+", "/USB_D-", "/RP_DP", "/RP_DM", "/DEV_D+", "/DEV_D-", "/LCD_SCK", "/LCD_MOSI", "/LCD_CS",
                        "/LCD_DC", "/XIN", "/XOUT", "/SWCLK", "/SWDIO", "/LINK_TX", "/LINK_RX", "/QSPI_SCLK", "/QSPI_SD0",
                        "/QSPI_SD1", "/QSPI_SD2", "/QSPI_SD3", "/QSPI_SS", "/SDA2", "/SCL2"],
        "fit": {
            "heights": HEIGHT, "default_height": 1.0,
            "solids": [{"name": "glass", "box": [GX0, up(GY1), GX1, up(GY0)], "z": [PANEL["foam"], PANEL["foam"] + PANEL["thick"]],
                        "note": f"on {PANEL['foam']} mm foam, {PANEL['thick']} thick: EastRising's drawing, not measured"}],
            "ribbon_run": [AT["J2"][0], up(YC + rib), GX1, up(YC - rib)],
            "selftest_tall": "FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB",    # J2: no SOT-23 is under the glass here
        },
    }


def main():
    bad = []
    check_firmware(bad)
    checking = "check" in sys.argv[1:] or "tidy" in sys.argv[1:]
    if "tidy" in sys.argv[1:]:
        tidy()
    if not checking:
        if is_routed():
            sys.exit(f"{NAME}: {NAME}.kicad_pcb is routed, and a new schematic wouldn't match it. "
                     f"`tools/keypcb gen-mono check` checks it; delete it to place the board again")
        os.makedirs(OUT, exist_ok=True)
        write_symbols()
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
    print(f"  the board: {NAME}.kicad_pcb, {W:g} x {H - TOP:g} mm ({(H - TOP) / W:.2f}:1), {'routed' if checking else 'placed, not routed'}; DRC: "
          + (", ".join(f"{k} {v}" for k, v in sorted(drc.items())) or "nothing"))
    if "render" in sys.argv[1:] and not bad:
        render()
    n_parts = sum(1 for p in PARTS if p.get("bom", True) and not p.get("dnp"))
    if bad:
        sys.exit(NAME + ": " + str(len(bad)) + " problems\n  " + "\n  ".join(bad))
    print(f"  {len(PARTS)} parts ({n_parts} placed by JLCPCB), {len([n for n in nets if not n.startswith('unconnected-')])} nets, "
          f"ERC: {len(found)} findings")
    print("  KiCad's netlist matches the table; the link's and KEY 2's wiring, the footprints, the GPIO functions and the Pico pins check out")


if __name__ == "__main__":
    main()
