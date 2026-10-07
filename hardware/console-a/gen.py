#!/usr/bin/env python3
"""PicoQuorum console PCB, rev A ("console-a"): a Pico 2 W, a 1.3" 240x240 ST7789 panel and nine
buttons on one board, wired exactly as the Waveshare Pico-LCD-1.3, so the console image runs on it
unchanged. Writes the KiCad 10 project from scratch.

    tools/keypcb gen-console      (KiCad's own Python, which has the pcbnew module)
    python3 hardware/console-a/gen.py check     (the pin check alone; needs no KiCad)

One table, PINS, says which GPIO each signal is on, and `check` compares it with firmware/board.py
and the emulator's emu/core/runtime.mjs. Every part is in PARTS: its symbol, footprint, LCSC
number, nets and place on the board. The schematic is drawn from that table (each pin gets a short
wire and a net label), and router.py lays the tracks. As with the key boards, once you edit the
board in KiCad, the KiCad files are the source of truth: don't run this again, or your edits are
overwritten. Board frame: x to the right, y down, (0, 0) at the top-left corner, looking at the
front (the screen side). All dimensions are mm.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "key-pcb"))
import gen as kgen          # the key boards' helpers: symbols, the schematic writer, text
import router

# macOS paths for KiCad's stock libraries (gen.py has the Linux ones)
_SS = "/Applications/KiCad/KiCad.app/Contents/SharedSupport"
if os.path.isdir(_SS):
    kgen.KISYM, kgen.KIFP = _SS + "/symbols", _SS + "/footprints"

NAME = "console-a"
TITLE = "PicoQuorum console, rev A: Pico 2 W, 1.3in panel, nine buttons"
DATE = "2026-10-07"
LIB = os.path.join(HERE, "lib")
KEYLIB = os.path.join(HERE, "..", "key-pcb", "lib")

# =================================================================================================
# The pin table: the one place this board says which GPIO does what. It must match
# firmware/board.py (BOARD "waveshare") and the emulator; `check` makes sure it does.
# =================================================================================================
PINS = {
    # signal: (GPIO, net)
    "LCD_DC": (8, "/LCD_DC"), "LCD_CS": (9, "/LCD_CS"), "LCD_SCK": (10, "/LCD_SCK"), "LCD_MOSI": (11, "/LCD_MOSI"),
    "LCD_RST": (12, "/LCD_RST"), "LCD_BL": (13, "/LCD_BL"),
    "A": (15, "/BTN_A"), "B": (17, "/BTN_B"), "X": (19, "/BTN_X"), "Y": (21, "/BTN_Y"),
    "up": (2, "/BTN_UP"), "down": (18, "/BTN_DOWN"), "left": (16, "/BTN_LEFT"), "right": (20, "/BTN_RIGHT"),
    "press": (3, "/BTN_PRESS"),
    "KEY_SDA": (4, "/KEY_SDA"), "KEY_SCL": (5, "/KEY_SCL"), "KEY_EN": (6, "/KEY_EN"), "KEY_DET": (7, "/KEY_DET"),
    "KEY_GP26": (26, "/KEY_GP26"), "KEY_CC1": (27, "/KEY_CC1"), "KEY_CC2": (28, "/KEY_CC2"),
}

# The Pico 2 W's 40 castellated pins, as on its pinout card. Pins left out of PINS are not used.
PICO = {1: "GP0", 2: "GP1", 3: "GND", 4: "GP2", 5: "GP3", 6: "GP4", 7: "GP5", 8: "GND", 9: "GP6", 10: "GP7",
        11: "GP8", 12: "GP9", 13: "GND", 14: "GP10", 15: "GP11", 16: "GP12", 17: "GP13", 18: "GND", 19: "GP14",
        20: "GP15", 21: "GP16", 22: "GP17", 23: "GND", 24: "GP18", 25: "GP19", 26: "GP20", 27: "GP21", 28: "GND",
        29: "GP22", 30: "RUN", 31: "GP26", 32: "GP27", 33: "AGND", 34: "GP28", 35: "ADC_VREF", 36: "3V3",
        37: "3V3_EN", 38: "GND", 39: "VSYS", 40: "VBUS"}


def pico_nets():
    by_gpio = {g: net for g, net in PINS.values()}
    out = {}
    for n, name in PICO.items():
        if name in ("GND", "AGND"):
            out[n] = "GND"
        elif name == "3V3":
            out[n] = "+3V3"
        elif name.startswith("GP"):
            out[n] = by_gpio.get(int(name[2:]))
        else:
            out[n] = None
    return out


def check():
    """PINS against firmware/board.py and emu/core/runtime.mjs. Returns a list of problems."""
    bad = []
    src = open(os.path.join(ROOT, "firmware", "board.py")).read()
    m = re.search(r"^DC, CS, SCK, MOSI, RST, BL = ([\d, ]+)$", src, re.M)
    fw = dict(zip(("LCD_DC", "LCD_CS", "LCD_SCK", "LCD_MOSI", "LCD_RST", "LCD_BL"), map(int, m.group(1).split(","))))
    fw.update({k: int(v) for k, v in re.findall(r'"([ABXY])": (\d+)', re.search(r"^BUTTONS = \{.*\}$", src, re.M).group(0))})
    keys = re.search(r"KEYS = dict\(BUTTONS, (.*)\)$", src, re.M).group(1)
    fw.update({k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", keys)})
    at = open(os.path.join(ROOT, "firmware", "atecc.py")).read()
    sda = re.search(r'ATECC_SDA["\']?\s*,\s*(\d+)', at)
    scl = re.search(r'ATECC_SCL["\']?\s*,\s*(\d+)', at)
    if sda and scl:
        fw["KEY_SDA"], fw["KEY_SCL"] = int(sda.group(1)), int(scl.group(1))
    else:
        bad.append("firmware/atecc.py: can't find the default ATECC_SDA / ATECC_SCL pins")
    for sig, g in fw.items():
        if PINS.get(sig, (None,))[0] != g:
            bad.append(f"{sig}: firmware/board.py says GP{g}, PINS says {PINS.get(sig)}")
    rt = open(os.path.join(ROOT, "emu", "core", "runtime.mjs")).read()
    emu = {k: int(g) for g, k in re.findall(r'(\d+): "(\w+)"', re.search(r"KEY_PINS = \{(.*?)\}", rt).group(1))}
    for sig, g in emu.items():
        if PINS[sig][0] != g:
            bad.append(f"{sig}: the emulator says GP{g}, PINS says GP{PINS[sig][0]}")
    for sig in ("A", "B", "X", "Y", "up", "down", "left", "right", "press"):
        if sig not in emu:
            bad.append(f"{sig}: not in the emulator's KEY_PINS")
    # nothing on the radio's pins (GP23, 24, 25, 29), and no GPIO used twice
    used = [g for g, _ in PINS.values()]
    bad += [f"GP{g} is the radio's" for g in used if g in (23, 24, 25, 29)]
    bad += [f"GP{g} is used twice" for g in set(used) if used.count(g) > 1]
    # and the board as saved (it may have been edited in KiCad since): U1's pads carry those nets
    pcb = os.path.join(HERE, NAME, NAME + ".kicad_pcb")
    if os.path.exists(pcb):
        text = open(pcb).read()
        i = text.find('(property "Reference" "U1"')
        start = text.rfind("\n\t(footprint ", 0, i)
        end = text.find("\n\t(footprint ", i)
        pads = dict(re.findall(r'\(pad "(\d+)" .*?\(net "([^"]*)"\)', text[start:end], re.S))
        for n, net in pico_nets().items():
            got = pads.get(str(n))
            got = None if got is None or got.startswith("unconnected-") else got
            if got != net:
                bad.append(f"{NAME}.kicad_pcb: U1 pin {n} ({PICO[n]}) is on {got}, PINS says {net}")
    return bad


# =================================================================================================
# Parts
# =================================================================================================
W, H = 92.0, 52.0          # the board
CORNER_R = 2.0
PICO_XY = (46.0, 26.0)     # centre of the module, on the back, antenna up
NOTCH = (46.0 - 7.1, 46.0 + 7.1, 9.0)   # under the antenna: no board (Pico W footprint's RF keep-out)
PANEL = (31.78, 10.0, 61.0, 36.16)      # the bare panel's outline on the front: 29.22 x 26.16
FPC_XY = (47.7, 20.25)     # J2: under the panel, opening toward the panel's flex (its right edge)
HOLES = [(3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]
KEYPADS_XY = (88.5, 13.0)  # J3 pin 1; the rest follow at 2.54 mm downward

R0603, C0603 = "Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric"
LCSC_R = {"10": "C22859", "1k": "C21190", "2.2k": "C4190", "10k": "C25804", "100k": "C25803"}
LCSC_C = {"100n": "C14663", "1u": "C15849"}
SW_FP, SW_LCSC = "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "C318884"
FPC_FP = "Connector_FFC-FPC:Jushuo_AFC07-S24FCA-00_1x24-1MP_P0.50_Horizontal"
PICO_FP = "console:RaspberryPi_Pico_W_SMD_HandSolder_PQ"

# The panel: ZJY130T-IF05 (ZJY133T-IF05 on its drawing), 1.3" 240x240 ST7789VW, 24-pin 0.5 mm FPC
# that folds behind the panel. Its pin n lands on J2's contact 25 - n: J2 sits turned so its pin
# 1 is at the bottom, and the panel's pin 1 is at the top (README.md, "The panel").
PANEL_PINS = {1: "+3V3", 2: "/LEDK", 3: "GND", 4: "+3V3", 5: "+3V3", 6: "+3V3", 7: "/LCD_RST", 8: "/LCD_CS",
              9: "/LCD_SCK", 10: "/LCD_DC", 11: "+3V3", 12: "/LCD_MOSI", 21: None, 22: None, 23: "GND", 24: "GND"}
PANEL_PINS.update({n: "GND" for n in range(13, 21)})   # DB0-DB7: unused in SPI mode, tied low
PANEL_NAMES = {1: "LEDA", 2: "LEDK", 3: "GND", 4: "VDD", 5: "IOVCC", 6: "IM1/2", 7: "RESET", 8: "CS",
               9: "SCL", 10: "D/C", 11: "RD", 12: "SDA", 21: "TE", 22: "NC", 23: "GND", 24: "GND"}
PANEL_NAMES.update({n: f"DB{n - 13}" for n in range(13, 21)})


def R(ref, value, a, b, xy, desc, rot=0):
    return dict(ref=ref, sym="Device:R", value=value, fp=R0603, lcsc=LCSC_R[value], nets={"1": a, "2": b},
                at=xy + (rot,), desc=desc)


def C(ref, value, a, b, xy, desc, rot=0):
    return dict(ref=ref, sym="Device:C", value=value, fp=C0603, lcsc=LCSC_C[value], nets={"1": a, "2": b},
                at=xy + (rot,), desc=desc)


def SW(ref, label, net, xy):
    return dict(ref=ref, sym="Switch:SW_Push", value="TS-1187A-B-A-B", fp=SW_FP, lcsc=SW_LCSC, nets={"1": net, "2": "GND"},
                at=xy + (0,), desc=f"Button {label}: pulls its GPIO low (internal pull-up, firmware/lcd.py)")


PARTS = [
    dict(ref="U1", sym="console:Pico2W", value="Pico 2 W", fp=PICO_FP, lcsc="", nets={str(k): v for k, v in pico_nets().items()},
         at=PICO_XY + (180,), back=True, mpn="SC1634",
         desc="Raspberry Pi Pico 2 W, castellated module soldered flat on the back by hand, antenna over the notch"),
    # the screen
    dict(ref="J2", sym="Connector_Generic_MountingPin:Conn_01x24_MountingPin", value="AFC07-S24FCA-00", fp=FPC_FP,
         lcsc="C262567", mpn="AFC07-S24FCA-00",
         nets=dict({str(25 - n): v for n, v in PANEL_PINS.items()}, MP="GND"), at=FPC_XY + (90,),
         desc="0.5 mm FPC, 24 pins, bottom contact: the panel's flex folds behind it and plugs in here. Contact k is panel pin 25-k"),
    C("C1", "100n", "+3V3", "GND", (42.6, 13.6), "Panel VDD/IOVCC decoupling", 90),
    C("C2", "1u", "+3V3", "GND", (40.6, 13.6), "Panel supply", 90),
    dict(ref="Q1", sym="Transistor_BJT:Q_NPN_BEC", value="SS8050", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C2150",
         nets={"1": "/BL_B", "2": "GND", "3": "/BL_SW"}, at=(42.4, 31.6, 0), mpn="SS8050",
         desc="Backlight switch, low side, as on the Waveshare board: GP13 high (or PWM) lights it"),
    R("R1", "10", "/LEDK", "/BL_SW", (46.0, 31.6), "Backlight current: (3.3 V - 2.9 V LEDs - Vce) / 10 R, about 30 mA", 90),
    R("R2", "1k", "/LCD_BL", "/BL_B", (38.8, 31.6), "Backlight base resistor", 90),
    R("R3", "10k", "/BL_B", "GND", (39.4, 34.6), "Keeps the backlight off while GP13 floats at reset", 0),
    # the buttons: a d-pad with a centre press on the left, A/B/X/Y in a column on the right, as the
    # emulator draws them (emu/console)
    SW("SW1", "UP", "/BTN_UP", (16.0, 18.0)),
    SW("SW2", "DOWN", "/BTN_DOWN", (16.0, 34.0)),
    SW("SW3", "LEFT", "/BTN_LEFT", (8.0, 26.0)),
    SW("SW4", "RIGHT", "/BTN_RIGHT", (24.0, 26.0)),
    SW("SW5", "PRESS", "/BTN_PRESS", (16.0, 26.0)),
    SW("SW6", "A", "/BTN_A", (70.0, 12.5)),
    SW("SW7", "B", "/BTN_B", (70.0, 21.0)),
    SW("SW8", "X", "/BTN_X", (70.0, 29.5)),
    SW("SW9", "Y", "/BTN_Y", (70.0, 38.0)),
    # the key port: PROPOSALS.md, "The console end of key-c"
    dict(ref="U2", sym="console:TPS22945", value="TPS22945DCKR", fp="Package_TO_SOT_SMD:SOT-353_SC-70-5", lcsc="C47507",
         nets={"1": "/KEY_PWR", "2": "GND", "3": None, "4": "/KEY_EN", "5": "+3V3"}, at=(79.5, 42.0, 0), mpn="TPS22945DCKR",
         desc="Key power: 100 mA current limit, enabled by GP6. It doesn't block reverse current: D1 does"),
    C("C3", "1u", "+3V3", "GND", (76.0, 45.0), "U2 input: larger than its output cap (TPS22945 datasheet 9.1.4)", 0),
    C("C4", "100n", "/KEY_PWR", "GND", (83.0, 45.0), "U2 output", 0),
    R("R4", "100k", "/KEY_EN", "GND", (76.0, 39.0), "Key power stays off until the firmware drives GP6 high", 0),
    R("R5", "100k", "/KEY_PWR", "GND", (83.0, 39.0), "Bleeds KEY_PWR (and the pull-ups) down when U2 turns off", 0),
    # today's console image doesn't drive GP6 (only firmware/bench1.py does): closing JP1 turns key
    # power on whenever the console is on. Through R11, so firmware that later drives GP6 low still wins
    R("R11", "10k", "+3V3", "/KEY_ON", (76.0, 36.0), "Key power always on, once JP1 is closed", 0),
    dict(ref="JP1", sym="Jumper:SolderJumper_2_Open", value="KEY ON", fp="Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
         lcsc="", nets={"1": "/KEY_ON", "2": "/KEY_EN"}, at=(79.5, 39.0, 0),
         desc="Open as made. Close it with solder to power the key from boot, for firmware that doesn't switch GP6"),
    dict(ref="D1", sym="Device:D_Schottky", value="B5819W", fp="Diode_SMD:D_SOD-123", lcsc="C8598",
         nets={"1": "/KEY_VBUS", "2": "/KEY_PWR"}, at=(83.5, 35.5, 0), mpn="B5819W SL",
         desc="Blocks 5 V that a charger puts on VBUS from reaching KEY_PWR, the pull-ups and 3V3. Key gets about 3.0 V"),
    R("R6", "10k", "/KEY_VBUS", "GND", (79.0, 35.5), "Bleeds VBUS down so the key really loses power", 0),
    R("R7", "2.2k", "/KEY_SDA", "/KEY_PWR", (78.5, 31.0), "SDA pull-up to switched key power, never 3V3 (BUILD1.md)", 90),
    R("R8", "2.2k", "/KEY_SCL", "/KEY_PWR", (80.5, 31.0), "SCL pull-up to switched key power", 90),
    R("R9", "10k", "+3V3", "/KEY_CC1", (78.5, 24.5), "CC1 Rp: a key's 5.1k Rd reads about 1.1 V on GP27", 90),
    R("R10", "10k", "+3V3", "/KEY_CC2", (80.5, 24.5), "CC2 Rp: read on GP28; exactly one CC may show Rd", 90),
    dict(ref="U3", sym="picoquorum:USBLC6-2SC6", value="USBLC6-2SC6", fp="Package_TO_SOT_SMD:SOT-23-6", lcsc="C7519",
         nets={"1": "/KEY_SDA", "6": "/KEY_SDA", "3": "/KEY_SCL", "4": "/KEY_SCL", "5": "+3V3", "2": "GND"},
         at=(84.0, 17.5, 90), mpn="USBLC6-2SC6", desc="ESD on SDA and SCL at the port"),
    dict(ref="U4", sym="picoquorum:USBLC6-2SC6", value="USBLC6-2SC6", fp="Package_TO_SOT_SMD:SOT-23-6", lcsc="C7519",
         nets={"1": "/KEY_CC1", "6": "/KEY_CC1", "3": "/KEY_CC2", "4": "/KEY_CC2", "5": "+3V3", "2": "GND"},
         at=(84.0, 27.0, 90), mpn="USBLC6-2SC6", desc="ESD on CC1 and CC2 at the port"),
    dict(ref="J3", sym="Connector_Generic:Conn_01x08", value="KEY PORT", fp="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
         lcsc="", nets={"1": "GND", "2": "/KEY_VBUS", "3": "/KEY_SDA", "4": "/KEY_SCL", "5": "/KEY_CC1", "6": "/KEY_CC2",
                        "7": "/KEY_DET", "8": "/KEY_GP26"},
         at=KEYPADS_XY + (0,), desc="Pads for the key's wires, in key-c's order: GND, VBUS, SDA (D+), SCL (D-), CC1, CC2, then GP7 and GP26 spare"),
]

# =================================================================================================
# Symbols and footprints
# =================================================================================================

def pico_symbol():
    pins = []
    for n, name in PICO.items():
        side, off = ("L", 24.13 - 2.54 * (n - 1)) if n <= 20 else ("R", 24.13 - 2.54 * (40 - n))
        pins.append((str(n), name, "passive", side, off))
    return kgen.box_symbol("Pico2W", "U", "Pico 2 W", PICO_FP, "https://datasheets.raspberrypi.com/pico/pico-2-w-datasheet.pdf",
                           "Raspberry Pi Pico 2 W module: RP2350, CYW43439 Wi-Fi. Pins as on its pinout card",
                           10.16, 26.67, pins)


def tps_symbol():
    pins = [("5", "VIN", "power_in", "L", 2.54), ("4", "ON", "input", "L", -2.54), ("1", "VOUT", "power_out", "R", 2.54),
            ("3", "OC", "open_collector", "R", -2.54), ("2", "GND", "power_in", "B", 0)]
    return kgen.box_symbol("TPS22945", "U", "TPS22945DCKR", "Package_TO_SOT_SMD:SOT-353_SC-70-5",
                           "https://www.ti.com/lit/ds/symlink/tps22945.pdf",
                           "TI current-limited load switch, 100 mA, active-high ON, auto-restart, SC-70-5", 7.62, 5.08, pins)


def write_libs():
    os.makedirs(os.path.join(LIB, "console.pretty"), exist_ok=True)
    syms = [pico_symbol(), tps_symbol()]
    with open(os.path.join(LIB, "console.kicad_sym"), "w") as f:
        f.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        f.write("\n".join(syms))
        f.write("\n)\n")
    write_pico_footprint()
    return {re.match(r'\(symbol "([^"]+)"', s).group(1): s for s in syms}


def write_pico_footprint():
    """KiCad's RaspberryPi_Pico_W_SMD_HandSolder, with two changes:
    - its three SWD through-holes (D1-D3) are gone: on this board they would land under the panel
      connector, and the console is flashed over USB;
    - its "RF Copper Keep Out" (the 10 mm past the antenna end) is gone, because it also covers the
      module's own end pads and DRC flags them. This board ends at the antenna end anyway, and
      _zones keeps the pour out of the strip along that edge.
    The antenna keep-out and the keep-outs over the module's test pads stay."""
    src = os.path.join(kgen.KIFP, "Module.pretty", "RaspberryPi_Pico_W_SMD_HandSolder.kicad_mod")
    t = open(src).read()
    t = t.replace('(footprint "RaspberryPi_Pico_W_SMD_HandSolder"', '(footprint "RaspberryPi_Pico_W_SMD_HandSolder_PQ"', 1)
    for d in ("D1", "D2", "D3"):
        i = t.index(f'\t(pad "{d}"')
        depth, k = 0, i + 1
        while True:
            depth += {"(": 1, ")": -1}.get(t[k], 0)
            if depth == 0 and t[k] == ")":
                break
            k += 1
        t = t[:i] + t[k + 2:]
    i = t.index('(name "RF Copper Keep Out")')
    i = t.rindex("\t(zone", 0, i)
    depth, k = 0, i + 1
    while True:
        depth += {"(": 1, ")": -1}.get(t[k], 0)
        if depth == 0 and t[k] == ")":
            break
        k += 1
    t = t[:i] + t[k + 2:]
    t = t.replace('(descr "Raspberry Pi Pico W surface-mount footprint with debug pads for hand soldering',
                  '(descr "PicoQuorum copy, SWD through-holes removed: Raspberry Pi Pico W surface-mount footprint for hand soldering', 1)
    with open(os.path.join(LIB, "console.pretty", "RaspberryPi_Pico_W_SMD_HandSolder_PQ.kicad_mod"), "w") as f:
        f.write(t)


def write_lib_tables(d):
    with open(os.path.join(d, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n'
                '  (lib (name "console")(type "KiCad")(uri "${KIPRJMOD}/../lib/console.kicad_sym")(options "")(descr "PicoQuorum console parts"))\n'
                '  (lib (name "picoquorum")(type "KiCad")(uri "${KIPRJMOD}/../../key-pcb/lib/picoquorum.kicad_sym")(options "")(descr "PicoQuorum key parts"))\n)\n')
    with open(os.path.join(d, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n'
                '  (lib (name "console")(type "KiCad")(uri "${KIPRJMOD}/../lib/console.pretty")(options "")(descr "PicoQuorum console footprints"))\n'
                '  (lib (name "picoquorum")(type "KiCad")(uri "${KIPRJMOD}/../../key-pcb/lib/picoquorum.pretty")(options "")(descr "PicoQuorum key footprints"))\n)\n')


# =================================================================================================
# Schematic: every pin gets a short wire and its net's label (or a power symbol, or a no-connect)
# =================================================================================================

def _lib_symbol(lib_id, own):
    lib, name = lib_id.split(":")
    if lib in ("console", "picoquorum"):
        text = own[name] if lib == "console" else _picoquorum_symbol(name)
        return text.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    return kgen.stock_symbol(lib, name)


def _picoquorum_symbol(name):
    s = open(os.path.join(KEYLIB, "picoquorum.kicad_sym")).read()
    i = s.index(f'(symbol "{name}"')
    d = 0
    for k in range(i, len(s)):
        d += {"(": 1, ")": -1}.get(s[k], 0)
        if d == 0:
            return s[i:k + 1]


def _pins(text):
    """(number, x, y, angle) of each pin in a symbol's text, in symbol coordinates (y up)."""
    out = []
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)(.*?)\(number "([^"]*)"', text, re.S):
        out.append((m.group(5), float(m.group(1)), float(m.group(2)), int(m.group(3))))
    return out


def _label(sh, name, x, y, angle):
    j = {0: "left bottom", 90: "left bottom", 180: "right bottom", 270: "right bottom"}[angle]
    sh.items.append(f'(label "{name}" (at {x:.2f} {y:.2f} {angle}) (fields_autoplaced yes) {kgen._font(False, j)} (uuid "{kgen.uid()}"))')


# where each part's symbol sits on the A3 sheet
SHEET_AT = {
    "U1": (60.96, 101.6), "J2": (198.12, 88.9), "C1": (167.64, 175.26), "C2": (182.88, 175.26),
    "Q1": (223.52, 175.26), "R1": (241.3, 160.02), "R2": (205.74, 175.26), "R3": (215.9, 190.5),
    "U2": (299.72, 50.8), "C3": (276.86, 71.12), "C4": (327.66, 71.12), "R4": (284.48, 71.12),
    "R5": (317.5, 71.12), "D1": (345.44, 50.8), "R6": (360.68, 71.12), "R7": (284.48, 104.14),
    "R8": (299.72, 104.14), "R9": (284.48, 139.7), "R10": (299.72, 139.7), "U3": (337.82, 109.22),
    "U4": (337.82, 144.78), "J3": (391.16, 104.14), "R11": (269.24, 50.8), "JP1": (269.24, 33.02),
}
for i, ref in enumerate(("SW1", "SW2", "SW3", "SW4", "SW5", "SW6", "SW7", "SW8", "SW9")):
    SHEET_AT[ref] = (40.64 + 40.64 * (i % 3), 213.36 + 22.86 * (i // 3))


def write_schematic(own):
    sh = kgen.Sheet(NAME)
    sh.lib("power:GND", kgen.stock_symbol("power", "GND"))
    sh.lib("power:+3V3", kgen.stock_symbol("power", "+3V3"))
    sh.lib("power:PWR_FLAG", kgen.stock_symbol("power", "PWR_FLAG"))
    for p in PARTS:
        text = _lib_symbol(p["sym"], own)
        sh.lib(p["sym"], text)
        x, y = SHEET_AT[p["ref"]]
        pins = _pins(text)
        fields = [("Description", p["desc"])]
        if p.get("mpn"):
            fields.append(("MPN", p["mpn"]))
        if p["lcsc"]:
            fields.append(("LCSC", p["lcsc"]))
        box = "box" if p["sym"].startswith(("console:", "picoquorum:", "Connector")) else None
        bh = max(abs(py) for _, _, py, _ in pins) if box else None
        sh.symbol(p["sym"], p["ref"], p["value"], x, y, [n for n, *_ in pins], fp=p["fp"], fields=fields,
                  in_bom=bool(p["lcsc"]) or p["ref"] in ("U1",), on_board=True,
                  box_h=bh)
        for num, px, py, ang in pins:
            ex, ey = x + px, y - py
            net = p["nets"].get(num)
            if net is None:
                sh.nc(ex, ey)
                continue
            dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[ang]
            L = 2.54
            wx, wy = ex + dx * L, ey + dy * L
            sh.wire(ex, ey, wx, wy)
            if net in ("GND", "+3V3"):
                rot = {(0, 1): 0, (0, -1): 180, (-1, 0): 270, (1, 0): 90}[(dx, dy)] if net == "GND" else \
                      {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}[(dx, dy)]
                sh.power(net, wx, wy, rot=rot)
            else:
                _label(sh, net.strip("/"), wx, wy, {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[(dx, dy)])
    # power comes in through the Pico (its 3V3 regulator), which the schematic can't see: flags
    for i, net in enumerate(("+3V3", "GND")):
        fx, fy = 20.32 + 15.24 * i, 25.4
        sh.power("PWR_FLAG", fx, fy)
        sh.wire(fx, fy, fx, fy + 5.08)
        sh.power(net, fx, fy + 5.08, rot=0 if net == "GND" else 180)
    sh.text("Console rev A. Every connection is by net label.\n"
            "Pin map = firmware/board.py (BOARD waveshare): gen.py check.\n"
            "Panel: ZJY130T-IF05, 1.3in 240x240 ST7789VW, 4-wire SPI (IM1/2 high).\n"
            "J2 contact k = panel pin 25-k (see README.md).", 101.6, 20.32)
    sh.text("Key port (key-c, PROPOSALS.md): U2 limits current and is\n"
            "switched by GP6; D1 keeps a charger's 5 V off KEY_PWR;\n"
            "pull-ups go to KEY_PWR, never 3V3; CC1/CC2 are read\n"
            "separately on GP27/GP28 through 10k Rp each.", 276.86, 20.32)
    path = os.path.join(HERE, NAME, NAME + ".kicad_sch")
    sh.write(path, TITLE)
    # A3, and our own comment in place of the key boards'
    s = open(path).read().replace('(paper "A4")', '(paper "A3")', 1)
    s = s.replace("The PCB is the plug: see hardware/key-pcb/README.md", "See hardware/console-a/README.md", 1)
    open(path, "w").write(s)


def read_netlist():
    import gen_cd
    sch = os.path.join(HERE, NAME, NAME + ".kicad_sch")
    out = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", "/dev/stdout", sch],
                         capture_output=True, text=True, check=True).stdout
    root = gen_cd._sexpr(out[out.index("(export"):])
    K, V = gen_cd._kids, gen_cd._val
    comps = {}
    for c in K(K(root, "components")[0], "comp"):
        fields = {}
        for f in K(K(c, "fields")[0], "field") if K(c, "fields") else []:
            if V(f, "name") in ("LCSC", "MPN", "Description", "Datasheet") and len(f) > 2:
                fields[V(f, "name")] = f[2]
        comps[V(c, "ref")] = dict(value=V(c, "value"), footprint=V(c, "footprint"), path="/" + V(c, "tstamps"),
                                  pads={}, fields=fields)
    for n in K(K(root, "nets")[0], "net"):
        for node in K(n, "node"):
            comps[V(node, "ref")]["pads"][V(node, "pin")] = V(n, "name")
    return comps


# =================================================================================================
# Board
# =================================================================================================

def _mm(x, y):
    import pcbnew
    return pcbnew.VECTOR2I(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 + y))


def _xy(v):
    import pcbnew
    return pcbnew.ToMM(v.x) - 100, pcbnew.ToMM(v.y) - 100


def outline_pts():
    """The board outline as a polygon (corners not rounded; _outline rounds the outer four)."""
    n0, n1, nd = NOTCH
    return [(0, 0), (n0, 0), (n0, nd), (n1, nd), (n1, 0), (W, 0), (W, H), (0, H)]


def _outline(board):
    import pcbnew
    E, r = pcbnew.Edge_Cuts, CORNER_R
    n0, n1, nd = NOTCH
    segs = [((r, 0), (n0, 0)), ((n0, 0), (n0, nd)), ((n0, nd), (n1, nd)), ((n1, nd), (n1, 0)), ((n1, 0), (W - r, 0)),
            ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(_mm(*a)); s.SetEnd(_mm(*b))
        s.SetLayer(E); s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)
    for c, st in (((W - r, r), (W - r, 0)), ((W - r, H - r), (W, H - r)), ((r, H - r), (r, H)), ((r, r), (0, r))):
        a = pcbnew.PCB_SHAPE(board)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetCenter(_mm(*c)); a.SetStart(_mm(*st))
        a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        a.SetLayer(E); a.SetWidth(pcbnew.FromMM(0.1))
        board.Add(a)


def _inside(x, y):
    n0, n1, nd = NOTCH
    if not (0 <= x <= W and 0 <= y <= H):
        return False
    return not (n0 < x < n1 and y < nd)


def _edge_dist(x, y):
    pts = outline_pts()
    d = min(router._d_seg(x, y, *a, *b) for a, b in zip(pts, pts[1:] + pts[:1]))
    r = CORNER_R
    for cx, cy in ((r, r), (W - r, r), (r, H - r), (W - r, H - r)):
        if abs(x - cx) <= r and abs(y - cy) <= r and (x - cx) * (cx - W / 2) > 0 and (y - cy) * (cy - H / 2) > 0:
            d = min(d, r - min(r, ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5))
    return d


def _text(board, s, x, y, layer, size=1.0, mirror=False, angle=0):
    import pcbnew
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(_mm(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(0.15 if size >= 1 else 0.12))
    t.SetMirrored(mirror)
    if angle:
        t.SetTextAngleDegrees(angle)
    board.Add(t)


def _line(board, a, b, layer, w=0.15):
    import pcbnew
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(_mm(*a)); s.SetEnd(_mm(*b))
    s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(w))
    board.Add(s)


def _rect(board, x0, y0, x1, y1, layer, w=0.15):
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        _line(board, a, b, layer, w)


def _silk(board):
    import pcbnew
    F, B, FF = pcbnew.F_SilkS, pcbnew.B_SilkS, pcbnew.F_Fab
    x0, y0, x1, y1 = PANEL
    _rect(board, x0, y0, x1, y1, FF, 0.1)
    _text(board, "1.3in panel, flex to the right, folded under", (x0 + x1) / 2, y1 - 1.5, FF, 0.8)
    for ref, label in (("SW6", "A"), ("SW7", "B"), ("SW8", "X"), ("SW9", "Y")):
        x, y, _ = next(p["at"] for p in PARTS if p["ref"] == ref)
        _text(board, label, x - 5.2, y, F, 1.2)
    _text(board, "KEY ON", 79.5, 37.4, F, 0.8)
    _text(board, "PICOQUORUM", 16.0, 44.0, F, 1.2)
    _text(board, "console-a rev A " + DATE[:7], 16.0, 46.3, F, 0.8)
    # the back: what goes where
    _text(board, "PicoQuorum console rev A", 72.0, 47.0, B, 1.0, mirror=True)
    _text(board, "Pico 2 W: chips out,", 46.0, 28.0, B, 0.8, mirror=True)
    _text(board, "USB to the bottom edge", 46.0, 29.4, B, 0.8, mirror=True)
    names = ("GND", "VBUS", "SDA D+", "SCL D-", "CC1", "CC2", "DET GP7", "GP26")
    kx, ky = KEYPADS_XY
    for i, n in enumerate(names):
        _text(board, n, kx - 4.6, ky + 2.54 * i, B, 0.8, mirror=True)
    _text(board, "KEY", kx, ky - 2.4, B, 1.0, mirror=True)


def _zones(board, gnd):
    import pcbnew
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        o = z.Outline()
        o.NewOutline()
        for x, y in outline_pts():
            o.Append(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 + y))
        z.SetLocalClearance(pcbnew.FromMM(0.25))
        z.SetMinThickness(pcbnew.FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetZoneName("GND " + ("top" if layer == pcbnew.F_Cu else "bottom"))
        board.Add(z)
    # no pour along the top edge beside the antenna (the module's RF keep-out, inside the board)
    k = pcbnew.ZONE(board)
    k.SetIsRuleArea(True)
    k.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    k.SetDoNotAllowZoneFills(True)
    k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False); k.SetDoNotAllowPads(False)
    k.SetDoNotAllowFootprints(False)
    k.SetZoneName("Antenna edge: no pour")
    o = k.Outline()
    o.NewOutline()
    for x, y in ((PICO_XY[0] - 21, 0), (PICO_XY[0] + 21, 0), (PICO_XY[0] + 21, 1.0), (PICO_XY[0] - 21, 1.0)):
        o.Append(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 + y))
    board.Add(k)


def _hole(board, ref, x, y):
    import pcbnew
    fp = pcbnew.FootprintLoad(os.path.join(kgen.KIFP, "MountingHole.pretty"), "MountingHole_2.7mm_M2.5")
    fp.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_2.7mm_M2.5"))
    fp.SetReference(ref); fp.Reference().SetVisible(False)
    fp.SetValue("M2.5"); fp.Value().SetVisible(False)
    fp.SetBoardOnly(True)
    board.Add(fp)
    fp.SetPosition(_mm(x, y))
    return fp


def _mark(board):
    import pcbnew
    fp = pcbnew.FootprintLoad(os.path.join(KEYLIB, "picoquorum.pretty"), "PicoQuorum_Mark")
    fp.SetFPID(pcbnew.LIB_ID("picoquorum", "PicoQuorum_Mark"))
    fp.SetReference("LOGO1"); fp.Reference().SetVisible(False)
    fp.SetBoardOnly(True)
    board.Add(fp)
    fp.SetPosition(_mm(16.0, 40.4))


# The order nets are routed in: the tight ones first (the panel's 0.5 mm connector), then power,
# then the buttons and the key port.
ORDER = ["/LCD_RST", "/LCD_CS", "/LCD_SCK", "/LCD_DC", "/LCD_MOSI", "/LEDK", "/BL_SW", "/BL_B", "/LCD_BL",
         "/BTN_UP", "/BTN_PRESS", "/BTN_LEFT", "/BTN_DOWN", "/BTN_RIGHT", "/BTN_A", "/BTN_B", "/BTN_X", "/BTN_Y",
         "/KEY_SDA", "/KEY_SCL", "/KEY_CC1", "/KEY_CC2", "/KEY_EN", "/KEY_DET", "/KEY_GP26", "/KEY_PWR", "/KEY_VBUS",
         "+3V3"]

# Pads joined by a straight track before routing: runs of same-net contacts on J2 (as contact
# numbers), which a track through their middles joins without touching anything else.
TIES = [("J2", ["5", "12"]), ("J2", ["1", "2"]), ("J2", ["19", "21"])]
# J2's ground contacts reach ground under the connector's body, where nothing else is routed: a short
# track out of the contact's back end to a via (contact, via x, via y). Contact 1 runs to the bottom
# mounting pad instead, and each mounting pad gets a via of its own.
J2_BODY = (46.95, 13.3, 52.2, 27.2)       # under the plastic: no other tracks here
J2_GND = [("22", 48.6, 15.5), ("8", 48.6, 22.5), ("12", 48.6, 20.5)]
# RD (panel pin 11, contact 14) is +3V3 boxed in between D/C and MOSI: it leaves the same way
J2_3V3 = [("14", 48.5, 19.25)]
# small parts whose ground pin is hemmed in by their other pins: a short track to a via (pin, dx, dy)
GND_STUBS = [("U2", "2", -1.5, 0.0)]
J2_MP_VIAS = [(50.6, 12.85), (50.6, 27.65)]


def _pad_rect(pad):
    import pcbnew
    bb = pad.GetBoundingBox()
    return (pcbnew.ToMM(bb.GetLeft()) - 100, pcbnew.ToMM(bb.GetTop()) - 100,
            pcbnew.ToMM(bb.GetRight()) - 100, pcbnew.ToMM(bb.GetBottom()) - 100)


def _layers(pad):
    import pcbnew
    return tuple(l for l, cu in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if pad.IsOnLayer(cu))


def write_board(netlist):
    import pcbnew
    path = os.path.join(HERE, NAME, NAME + ".kicad_pcb")
    if os.path.exists(path):
        os.remove(path)
    board = pcbnew.NewBoard(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    ds.m_CopperEdgeClearance = pcbnew.FromMM(router.EDGE)
    ds.SetAuxOrigin(_mm(0, H))          # Gerbers, drill and CPL measure from the bottom-left corner
    ds.m_TentViasFront = True
    ds.m_TentViasBack = True
    tb = board.GetTitleBlock()
    tb.SetTitle(TITLE); tb.SetDate(DATE); tb.SetRevision("A"); tb.SetCompany("PicoQuorum")

    nets = {}
    for n in sorted({net for comp in netlist.values() for net in comp["pads"].values()}):
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    parts = {p["ref"]: p for p in PARTS}
    fps = {}
    for ref, comp in netlist.items():
        lib, fpname = comp["footprint"].split(":")
        libdir = {"console": os.path.join(LIB, "console.pretty"),
                  "picoquorum": os.path.join(KEYLIB, "picoquorum.pretty")}.get(lib, os.path.join(kgen.KIFP, lib + ".pretty"))
        fp = pcbnew.FootprintLoad(libdir, fpname)
        fp.SetFPID(pcbnew.LIB_ID(lib, fpname))
        fp.SetReference(ref)
        fp.SetValue(comp["value"])
        fp.SetPath(pcbnew.KIID_PATH(comp["path"]))
        fp.SetSheetname("/"); fp.SetSheetfile(NAME + ".kicad_sch")
        for k, v in comp["fields"].items():
            fp.SetField(k, v)
            f = fp.GetField(k)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab)
        if not parts[ref]["lcsc"]:
            # hand-soldered (the Pico) or not a part at all (the key pads): off the CPL, and J3 off the BOM
            fp.SetExcludedFromPosFiles(True)
            fp.SetExcludedFromBOM(ref != "U1")
            # (JP1 is a solder jumper: copper only)
            if ref == "J3":
                fp.Models().clear()     # nothing is fitted there: the renders shouldn't show a header
        board.Add(fp)
        x, y, rot = parts[ref]["at"]
        fp.SetPosition(_mm(x, y))
        fp.SetOrientationDegrees(rot)
        if parts[ref].get("back"):
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for pad in fp.Pads():
            net = comp["pads"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
        r.SetTextThickness(pcbnew.FromMM(0.12))
        # references sit on the Fab layer: the silkscreen keeps only labels a person needs
        r.SetLayer(pcbnew.B_Fab if parts[ref].get("back") else pcbnew.F_Fab)
        fps[ref] = fp
    holes = [_hole(board, f"H{i + 1}", x, y) for i, (x, y) in enumerate(HOLES)]
    _check_orientation(fps)

    # ---- the router's picture of the board
    g = router.Grid(W, H)
    g.block_outside(_inside, _edge_dist)
    for x, y in HOLES:
        g.add_hole(x, y, 2.7)
    pads_by_net = {}
    for ref, fp in fps.items():
        for pad in fp.Pads():
            layers = _layers(pad)
            net = pad.GetNetname()
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                x, y = _xy(pad.GetPosition())
                g.add_hole(x, y, pcbnew.ToMM(pad.GetDrillSize().x))
                continue
            rect = _pad_rect(pad)
            inside = lambda x, y, pad=pad: pad.HitTest(_mm(x, y), 0)
            g.add_pad(layers, net or None, *rect, inside=inside)
            if net:
                pads_by_net.setdefault(net, []).append((ref, pad.GetNumber(), layers, rect))
        for z in fp.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
                bb = z.GetBoundingBox()
                ls = [l for l, cu in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if z.IsOnLayer(cu)]
                g.block(ls, pcbnew.ToMM(bb.GetLeft()) - 100, pcbnew.ToMM(bb.GetTop()) - 100,
                        pcbnew.ToMM(bb.GetRight()) - 100, pcbnew.ToMM(bb.GetBottom()) - 100)

    def centre(ref, num):
        return _xy(fps[ref].FindPadByNumber(num).GetPosition())

    def join_pad(net, entry):
        _, _, layers, rect = entry
        for l in layers:
            g.join(net, l, g.pad_cells(l, net, *rect))

    for ref, (a, b) in TIES:
        net = netlist[ref]["pads"][a]
        pa, pb = centre(ref, a), centre(ref, b)
        g.add_seg(0, net, pa, pb, joined=False)
    g.block((0,), *J2_BODY)
    for num, vx, vy in J2_GND:
        g.add_seg(0, "GND", centre("J2", num), (vx, vy), joined=False)
        g.add_via("GND", vx, vy, joined=False)
    for num, vx, vy in J2_3V3:
        a = centre("J2", num)
        g.add_seg(0, "+3V3", a, (vx - 0.25, a[1]), joined=False)
        g.add_seg(0, "+3V3", (vx - 0.25, a[1]), (vx, vy), joined=False)
        g.add_via("+3V3", vx, vy, joined=False)
        # the router picks this contact up from its via, on the back
        lst = pads_by_net["+3V3"]
        i = next(k for k, e in enumerate(lst) if e[:2] == ("J2", num))
        lst[i] = ("J2", num, (1,), (vx, vy, vx, vy))
    for ref, num, dx, dy in GND_STUBS:
        a = centre(ref, num)
        g.add_seg(0, "GND", a, (a[0] + dx, a[1] + dy), joined=False)
        g.add_via("GND", a[0] + dx, a[1] + dy, joined=False)
    p1 = centre("J2", "1")
    g.add_seg(0, "GND", p1, (p1[0] + 1.4, p1[1] + 1.4), joined=False)
    for vx, vy in J2_MP_VIAS:
        g.add_via("GND", vx, vy, joined=False)
    # the pads those tracks reach are on ground already: no stitching via for them below
    stitched = {("J2", str(k)) for k in list(range(1, 3)) + list(range(5, 13)) + [22]} | {("J2", "MP")}
    stitched |= {(ref, num) for ref, num, *_ in GND_STUBS}

    # ---- signals
    failed = []
    for net in ORDER + sorted(n for n in pads_by_net if n not in ORDER and n != "GND"):
        entries = pads_by_net.get(net, [])
        if len(entries) < 2:
            continue
        # start the tree at the first pad; join the rest one at a time, nearest first
        join_pad(net, entries[0])
        todo = entries[1:]
        while todo:
            tx = [g.xy(c) for l in (0, 1) for c in range(len(g.cu[l])) if g.cu[l][c] == g.nid(net) and g.joined[l][c]]
            def dist(e):
                cx, cy = (e[3][0] + e[3][2]) / 2, (e[3][1] + e[3][3]) / 2
                return min(abs(cx - x) + abs(cy - y) for x, y in tx)
            todo.sort(key=dist)
            e = todo.pop(0)
            starts = [(l, c) for l in e[2] for c in g.pad_cells(l, net, *e[3])]
            try:
                way = g.route(net, starts)
            except router.NoRoute as ex:
                failed.append(str(ex) + f" from {e[0]}.{e[1]}")
                continue
            g.commit(net, way)
            join_pad(net, e)

    # ---- ground: every front ground pad gets a via to the back pour
    for ref, num, layers, rect in pads_by_net["GND"]:
        if layers != (0,) or (ref, num) in stitched:
            continue
        starts = [(0, c) for c in g.pad_cells(0, "GND", *rect)]
        try:
            way = g.route("GND", starts, to_via=True, limit=200_000)
        except router.NoRoute as ex:
            failed.append(str(ex) + f" (via for {ref}.{num})")
            continue
        g.commit("GND", way, end_via=True)

    if failed:
        print("console-a: could not route:\n  " + "\n  ".join(failed))

    for l, net, a, b, width in g.segs:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(_mm(*a)); t.SetEnd(_mm(*b))
        t.SetWidth(pcbnew.FromMM(width))
        t.SetLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
    for net, x, y in g.vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(_mm(x, y))
        v.SetWidth(pcbnew.FromMM(router.VIA_D)); v.SetDrill(pcbnew.FromMM(router.VIA_DRILL))
        v.SetNet(nets[net])
        board.Add(v)

    _outline(board)
    _zones(board, nets["GND"])
    _silk(board)
    _mark(board)

    pcbnew.SaveBoard(path, board)
    err = os.dup(2)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    try:
        board = pcbnew.LoadBoard(path)
    finally:
        os.dup2(err, 2)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    _stackup(path)
    _project(os.path.join(HERE, NAME, NAME + ".kicad_pro"))
    return failed


def _check_orientation(fps):
    """The two things the layout leans on: the Pico's antenna end at the top edge, and the panel's
    pin 1 (J2 contact 24) at the top of J2."""
    _, y40 = _xy(fps["U1"].FindPadByNumber("40").GetPosition())
    _, y20 = _xy(fps["U1"].FindPadByNumber("20").GetPosition())
    assert y20 < 5 and y40 > 45, "the Pico should have its antenna end (pins 20/21) at the top, USB at the bottom"
    _, j1 = _xy(fps["J2"].FindPadByNumber("1").GetPosition())
    _, j24 = _xy(fps["J2"].FindPadByNumber("24").GetPosition())
    assert j24 < j1, "J2 contact 24 (panel pin 1) should be at the top"


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
\t\t\t(copper_finish "HAL lead-free")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def _stackup(path):
    s = open(path).read()
    assert "(stackup" not in s
    assert "\t(setup\n" in s, "the board file's (setup) section moved: update _stackup"
    s = s.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1)
    open(path, "w").write(s)


def _project(pro):
    """JLCPCB's limits (gen.py's JLC_RULES), and a netclass that matches what the router lays."""
    d = json.load(open(pro))
    d["board"]["design_settings"]["rules"].update(kgen.JLC_RULES)
    # one spoke is enough where a pad sits against the board edge (the Pico's pins by the notch)
    d["board"]["design_settings"]["rules"]["min_resolved_spokes"] = 1
    for c in d["net_settings"]["classes"]:
        if c["name"] == "Default":
            c.update(clearance=router.CLEAR, track_width=router.TRACK, via_diameter=router.VIA_D, via_drill=router.VIA_DRILL)
    with open(pro, "w") as f:
        json.dump(d, f, indent=2, sort_keys=True)
        f.write("\n")


def main():
    bad = check()
    if bad:
        sys.exit("pin check failed:\n  " + "\n  ".join(bad))
    if sys.argv[1:] == ["check"]:
        print(f"console-a: pin map matches firmware/board.py, the emulator and the board ({len(PINS)} signals)")
        return
    d = os.path.join(HERE, NAME)
    os.makedirs(d, exist_ok=True)
    write_lib_tables(d)
    own = write_libs()
    write_schematic(own)
    failed = write_board(read_netlist())
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
