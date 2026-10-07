#!/usr/bin/env python3
"""PicoQuorum console, proposal A (console-a): one board that holds everything Build 1 wires by hand,
and runs today's console image unchanged. Writes the KiCad 10 project in console-a/ from scratch.

    tools/keypcb gen-console      (runs this with the Python that has KiCad's pcbnew module)

On the board (README.md says why):
- a Raspberry Pi Pico 2 W, soldered flat by its castellations; JLCPCB places it
- the 2.8" 320x240 ST7789 module Build 1 uses, on its own 8-pin header
- a Bourns PEC11R knob with push: 24 detents and 24 pulses, the 4 steps a click knob.py counts
- Sign, Back, Device and Reject buttons
- a vertical USB-C plug that key-c (hardware/key-pcb/key-c-usbc) slides onto, with the console end
  hardware/key-pcb/PROPOSALS.md asks for: a current-limited, reverse-blocking switch on VBUS, CC1
  and CC2 read separately, 2.2k pull-ups to the switched VBUS, and ESD on every line
- a status LED

The pins are Build 1's ("build1" in firmware/board.py), so BOARD = "build1" and SCREEN = "2.8" in
secrets.py run the console image as it is: no new release. main() reads firmware/board.py and
firmware/atecc.py and stops if GPIO below disagrees with them.

The tracks come from the small grid router at the end of this file, so a moved part or a measured
screen only needs a rerun. As with the key boards, once you edit the board in KiCad, the KiCad files
are the source of truth: don't run this again. Frame: x to the right and y down from the board's
top-left corner, in mm.
"""
import heapq, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "hardware", "key-pcb"))
import gen      # noqa: E402  the key boards' helpers: symbols, schematic sheet, board drawing
import gen_cd   # noqa: E402  (also points gen at KiCad's libraries on macOS)

NAME, REV, DATE = "console-a", "P1", "2026-10-07"
TITLE = "PicoQuorum console, proposal A: Pico 2 W carrier"
LIB = os.path.join(HERE, "lib")
KEYLIB = os.path.join(REPO, "hardware", "key-pcb", "lib")

# =================================================================================================
# The pin map: the one table. firmware/board.py ("build1") and firmware/atecc.py must agree with the
# first block; the second block is new, and today's console image never touches those pins.
# =================================================================================================
GPIO = {
    "LCD_DC": 8, "LCD_CS": 9, "LCD_SCK": 10, "LCD_MOSI": 11, "LCD_RST": 12, "LCD_BL": 13,
    "BTN_SIGN": 15, "BTN_BACK": 17, "BTN_DEVICE": 19, "BTN_REJECT": 21,     # A, B, X, Y
    "KNOB_SW": 1, "KNOB_GP2": 2, "KNOB_GP3": 3,
    "KEY_SDA": 4, "KEY_SCL": 5,
}
NEW_GPIO = {
    "KEY_EN": 6,        # the key's power switch: pulled up, so the key is on unless firmware says not
    "KEY_FAULT": 14,    # the switch's open-drain fault flag (overload, reverse voltage)
    "CC1_SENSE": 26,    # ADC0: about 1.1 V with a key on, 3.3 V with nothing
    "CC2_SENSE": 27,    # ADC1: the same for CC2. On this plug a key shows on both, not one
    "LED": 22,
}

# The Pico 2 W's 40 pins (the same as the Pico W's)
PICO = {1: "GP0", 2: "GP1", 3: "GND", 4: "GP2", 5: "GP3", 6: "GP4", 7: "GP5", 8: "GND", 9: "GP6", 10: "GP7",
        11: "GP8", 12: "GP9", 13: "GND", 14: "GP10", 15: "GP11", 16: "GP12", 17: "GP13", 18: "GND", 19: "GP14",
        20: "GP15", 21: "GP16", 22: "GP17", 23: "GND", 24: "GP18", 25: "GP19", 26: "GP20", 27: "GP21", 28: "GND",
        29: "GP22", 30: "RUN", 31: "GP26", 32: "GP27", 33: "AGND", 34: "GP28", 35: "ADC_VREF", 36: "3V3",
        37: "3V3_EN", 38: "GND", 39: "VSYS", 40: "VBUS"}


def check_firmware():
    """GPIO against the console image's own pin tables. Read only: this never edits firmware/."""
    b = open(os.path.join(REPO, "firmware", "board.py")).read()
    a = open(os.path.join(REPO, "firmware", "atecc.py")).read()
    want = {}
    m = re.search(r"^DC, CS, SCK, MOSI, RST, BL = (\d+), (\d+), (\d+), (\d+), (\d+), (\d+)$", b, re.M)
    want.update(zip(("LCD_DC", "LCD_CS", "LCD_SCK", "LCD_MOSI", "LCD_RST", "LCD_BL"), map(int, m.groups())))
    m = re.search(r'^BUTTONS = \{"A": (\d+), "B": (\d+), "X": (\d+), "Y": (\d+)\}$', b, re.M)
    want.update(zip(("BTN_SIGN", "BTN_BACK", "BTN_DEVICE", "BTN_REJECT"), map(int, m.groups())))
    m = re.search(r"^\s+ENC_A, ENC_B, ENC_SW = (\d+), (\d+), (\d+)$", b, re.M)
    enc_a, enc_b, enc_sw = map(int, m.groups())
    m = re.search(r'"ATECC_SDA", (\d+)\)\), int\(getattr\(_s, "ATECC_SCL", (\d+)\)', a)
    want.update(KEY_SDA=int(m.group(1)), KEY_SCL=int(m.group(2)))
    bad = [f"{k}: GP{GPIO[k]} here, GP{v} in firmware" for k, v in want.items() if GPIO[k] != v]
    if {GPIO["KNOB_GP2"], GPIO["KNOB_GP3"]} != {enc_a, enc_b} or GPIO["KNOB_SW"] != enc_sw:
        bad.append(f"knob: GP{GPIO['KNOB_GP2']}/GP{GPIO['KNOB_GP3']}/GP{GPIO['KNOB_SW']} here, "
                   f"ENC_A/ENC_B/ENC_SW = {enc_a}/{enc_b}/{enc_sw} in firmware")
    used = set(GPIO.values())
    bad += [f"{k}: GP{v} is already {n}" for k, v in NEW_GPIO.items() for n, u in GPIO.items() if u == v]
    if len(used | set(NEW_GPIO.values())) != len(GPIO) + len(NEW_GPIO):
        bad.append("two nets share a GPIO")
    if bad:
        sys.exit("the pin map disagrees with the firmware:\n  " + "\n  ".join(bad))


# =================================================================================================
# Parts. LCSC numbers drive JLCPCB's BOM (tools/keypcb fab); parts without one are soldered by hand.
# =================================================================================================
P = dict(
    pico=dict(mpn="Raspberry Pi Pico 2 W (SC1633)", lcsc="C42394205", fp="pqconsole:RaspberryPi_Pico_2_W_SMD_PQ",
              ds="https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf"),
    plug=dict(mpn="918-118A2021Y40002", lcsc="C399939",
              fp="Connector_USB:USB_C_Plug_ShenzhenJingTuoJin_918-118A2021Y40002_Vertical",
              ds="https://datasheet.lcsc.com/lcsc/1912111437_Jing-Extension-of-the-Electronic-Co--918-118A2021Y40002_C399939.pdf"),
    switch=dict(mpn="AP22653W6-7", lcsc="C2158037", fp="Package_TO_SOT_SMD:SOT-23-6",
                ds="https://www.diodes.com/assets/Datasheets/AP22652_53_52A_53A.pdf"),
    esd=dict(mpn="USBLC6-2SC6", lcsc="C7519", fp="Package_TO_SOT_SMD:SOT-23-6", ds=gen.USBLC6_DS),
    tvs=dict(mpn="ESD5Z5V0", lcsc="C502546", fp="Diode_SMD:D_SOD-523"),
    led=dict(mpn="KT-0603R", lcsc="C2286", fp="LED_SMD:LED_0603_1608Metric"),
    knob=dict(mpn="PEC11R-4215F-S0024",
              fp="pqconsole:RotaryEncoder_Bourns_PEC11R-S_Vertical",
              ds="https://www.bourns.com/docs/Product-Datasheets/PEC11R.pdf"),
    button=dict(mpn="K2-1102SP-K4SC-04", lcsc="C129461", fp="pqconsole:SW_HRO_K2-1102SP_6x6mm"),
    screen=dict(mpn="2.8in 240x320 ST7789 SPI module, 8-pin", fp="pqconsole:Screen_ST7789_2.8in_8P_PLACEHOLDER"),
)
R0402, C0402, C0603 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric"
LCSC_R = {"10k": "C25744", "2.2k": "C25879", "1k": "C11702", "0R": "C17168"}
LCSC_C = {"100n": "C1525", "10u": "C19702"}

# The screen module, as a placeholder until one is measured: an 86 x 50 mm board with the 8-pin
# header on its left edge and an M3 hole in each corner. PINS runs top to bottom with the header on
# the left (the way Build 1's case holds it, MADCTL 0x60): Build 1's bench screen prints BL, RST,
# DC, SCL, MOSI, CS, 3V3, GND from top to bottom with its header on the right, so on the left it is
# the reverse. Check every number here against the module you buy (README.md, "Before ordering").
SCREEN = dict(w=86.0, h=50.0, header_dx=2.54, hole_inset=3.0, hole_d=3.2,
              pins=["GND", "3V3", "CS", "MOSI", "SCL", "DC", "RST", "BL"])
SCREEN_NET = {"GND": "GND", "3V3": "+3V3", "CS": "LCD_CS", "MOSI": "LCD_MOSI", "SCL": "LCD_SCK",
              "DC": "LCD_DC", "RST": "LCD_RST", "BL": "LCD_BL"}

# =================================================================================================
# Symbols
# =================================================================================================

def pico_symbol():
    kind = lambda n: ("power_in" if n in ("GND", "AGND") else "power_out" if n in ("3V3", "VSYS", "VBUS")
                      else "input" if n in ("RUN", "3V3_EN") else "passive" if n == "ADC_VREF" else "bidirectional")
    pins = [(str(n), PICO[n], kind(PICO[n]), "L", 24.13 - (n - 1) * 2.54) for n in range(1, 21)]
    pins += [(str(n), PICO[n], kind(PICO[n]), "R", 24.13 - (40 - n) * 2.54) for n in range(21, 41)]
    return gen.box_symbol("Pico_2_W", "U", "Pico_2_W", P["pico"]["fp"], P["pico"]["ds"],
                          "Raspberry Pi Pico 2 W module (RP2350 + CYW43439), castellated, 40 pins", 10.16, 26.67, pins)


def plug_symbol():
    """The 16-pin plug as the console sees it. On a plug, B5 is VCONN; plugged straight into key-c it
    lands on the key's other CC. key-c joins A6 to B6 and A7 to B7, so either way up the key's SDA and
    SCL meet A6 and A7: B6 and B7 stay unconnected here."""
    w, h = 7.62, 10.16
    Pn = gen._pin
    right = lambda num, name, off, hide=False: Pn("passive", num, name, w + 2.54, off, 180, hide=hide)
    pins = [right("A4", "VBUS", 7.62), right("A9", "VBUS", 7.62, True), right("B4", "VBUS", 7.62, True),
            right("B9", "VBUS", 7.62, True), right("A5", "CC", 5.08), right("B5", "VCONN", 2.54),
            right("A6", "D+", 0), right("A7", "D-", -2.54), right("A8", "SBU1", -5.08), right("B8", "SBU2", -7.62)]
    left = lambda num, name, off: Pn("passive", num, name, -w - 2.54, off, 0)
    pins += [left("B6", "D+", 0), left("B7", "D-", -2.54)]
    for i, num in enumerate(("A1", "A12", "B1", "B12", "SH")):
        pins.append(Pn("passive", num, "GND" if num != "SH" else "SHIELD", 0, -h - 2.54, 90, hide=i > 0))
    props = [("Reference", "J", 0, h + 1.27, False), ("Value", "USB_C_Plug_16P", 0, -h - 1.27, False),
             ("Footprint", P["plug"]["fp"], 0, 0, True), ("Datasheet", P["plug"]["ds"], 0, 0, True),
             ("Description", "USB-C plug, 16 pins, used as plain wires: VBUS, GND, D+, D-, CC, VCONN", 0, 0, True)]
    pr = "\n".join(f'(property "{k}" "{v}" (at {x} {y} 0) {gen._font(hide)})' for k, v, x, y, hide in props)
    return f"""(symbol "USB_C_Plug_16P" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
{pr}
(symbol "USB_C_Plug_16P_0_1" (rectangle (start {-w} {h}) (end {w} {-h}) (stroke (width 0.254) (type default)) (fill (type background))))
(symbol "USB_C_Plug_16P_1_1"
{chr(10).join(pins)})
(embedded_fonts no))"""


def switch_symbol():
    pins = [("1", "IN", "power_in", "L", 2.54), ("3", "EN", "input", "L", -2.54),
            ("6", "OUT", "power_out", "R", 2.54), ("4", "~{FAULT}", "open_collector", "R", -2.54),
            ("2", "GND", "power_in", "B", -2.54), ("5", "ILIM", "passive", "B", 2.54)]
    return gen.box_symbol("AP22653", "U", "AP22653", P["switch"]["fp"], P["switch"]["ds"],
                          "Diodes AP22653: current-limited high-side switch, reverse blocking, output discharge, active-high EN, SOT-26",
                          7.62, 5.08, pins)


def write_symbol_lib():
    syms = [pico_symbol(), plug_symbol(), switch_symbol(), gen.usblc6_symbol()]
    with open(os.path.join(LIB, "pqconsole.kicad_sym"), "w") as f:
        f.write('(kicad_symbol_lib (version 20241209) (generator "picoquorum_gen") (generator_version "9.0")\n')
        f.write("\n".join(syms))
        f.write("\n)\n")
    return {re.match(r'\(symbol "([^"]+)"', s).group(1): s for s in syms}


# =================================================================================================
# Footprints
# =================================================================================================

def _items(text):
    """The top-level items of a footprint file, as text."""
    body = text[text.index("\n") + 1:text.rindex(")")]
    out, d, start = [], 0, None
    for i, ch in enumerate(body):
        if ch == "(":
            if d == 0:
                start = i
            d += 1
        elif ch == ")":
            d -= 1
            if d == 0:
                out.append(body[start:i + 1])
    return text[:text.index("\n") + 1], out


def write_pico_footprint():
    """KiCad's Pico W SMD footprint (which also fits the Pico 2 W), with these changes:
    - its suggested board edge, drawn as a zone on Edge.Cuts, goes: the outline here has the cut-out
    - the test-point and debug pads go: nothing on this board meets the Pico's bottom test points
    - in their place, rule areas keep copper off the top layer under those exposed points
    - the keep-out past the antenna end starts at 25.3 mm, not 25: the corner pads' paste reaches 25.23
    - no silkscreen outline: on this board the module's ends are the board's edges"""
    src = os.path.join(gen.KIFP, "Module.pretty", "RaspberryPi_Pico_W_SMD.kicad_mod")
    head, items = _items(open(src).read())
    keep = []
    template = None
    for it in items:
        if it.startswith("(zone") and '"Edge.Cuts"' in it:
            continue
        if re.match(r'\(pad "(TP\d|D\d)"', it):
            continue
        if re.match(r"\(fp_(line|arc|circle|poly|rect)", it) and '"F.SilkS"' in it:
            continue
        if it.startswith("(zone") and "(xy -21 25)" in it:
            it = it.replace("(xy -21 25)", "(xy -21 25.3)").replace("(xy 21 25)", "(xy 21 25.3)")
        if it.startswith("(zone") and template is None:
            template = it
        keep.append(it)
    for x0, y0, x1, y1 in ((-3.6, -25.4, 2.1, -9.9), (-0.6, 4.6, 6.8, 6.8)):
        z = re.sub(r"\(layers [^)]*\)", '(layers "F.Cu")', template, count=1, flags=re.S)
        z = re.sub(r"\(keepout.*?\)\s*\)", "(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) "
                   "(copperpour not_allowed) (footprints allowed))", z, count=1, flags=re.S)
        z = re.sub(r"\(pts.*?\)\s*\)", f"(pts (xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1}))", z,
                   count=1, flags=re.S)
        keep.append(z)
    head = head.replace('(footprint "RaspberryPi_Pico_W_SMD"', '(footprint "RaspberryPi_Pico_2_W_SMD_PQ"', 1)
    text = head + "\t" + "\n\t".join(keep) + "\n)\n"
    text = re.sub(r'\(descr "', '(descr "PicoQuorum copy (gen_console.py): no Edge.Cuts zone, no test-point or '
                  'debug pads, copper kept off the top layer under them. ', text, count=1)
    with open(os.path.join(LIB, "pqconsole.pretty", "RaspberryPi_Pico_2_W_SMD_PQ.kicad_mod"), "w") as f:
        f.write(text)


def _fp(name, descr, tags, attr, body, ref_at=(0, -2), value_at=(0, 2)):
    uid = gen.uid
    return f"""(footprint "{name}" (version 20241229) (generator "picoquorum_gen") (generator_version "9.0") (layer "F.Cu")
(descr "{descr}")
(tags "{tags}")
(property "Reference" "REF**" (at {ref_at[0]} {ref_at[1]} 0) (layer "F.SilkS") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(property "Value" "{name}" (at {value_at[0]} {value_at[1]} 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))
(attr {attr})
{body}
(embedded_fonts no))
"""


def _rect(x0, y0, x1, y1, layer, w=0.1):
    return (f'(fp_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width {w}) (type default)) (fill no) '
            f'(layer "{layer}") (uuid "{gen.uid()}"))')


def _line(x0, y0, x1, y1, layer, w=0.12):
    return (f'(fp_line (start {x0} {y0}) (end {x1} {y1}) (stroke (width {w}) (type default)) '
            f'(layer "{layer}") (uuid "{gen.uid()}"))')


def write_knob_footprint():
    """Bourns PEC11R-xxxxF-Sxxxx, from its datasheet's PCB layout: A, C, B at 2.5 mm, the switch 5 mm
    apart and 14.5 mm across, holes 1.0 +0.1 mm. KiCad's Alps EC11E footprint has the same pins, but
    its mounting tabs sit 11.2 mm apart; the PEC11R's are 13.2 mm apart in 2.6 x 1.8 mm slots."""
    uid = gen.uid
    pads = []
    for n, x, y, shape in (("A", 0, 0, "rect"), ("C", 0, 2.5, "circle"), ("B", 0, 5, "circle"),
                           ("S1", 14.5, 0, "circle"), ("S2", 14.5, 5, "circle")):
        pads.append(f'(pad "{n}" thru_hole {shape} (at {x} {y}) (size 1.8 1.8) (drill 1.1) (layers "*.Cu" "*.Mask") '
                    f'(remove_unused_layers no) (uuid "{uid()}"))')
    for y in (2.5 - 6.6, 2.5 + 6.6):
        pads.append(f'(pad "MP" thru_hole rect (at 7.5 {y:.1f}) (size 3.4 2.6) (drill oval 2.8 2.0) '
                    f'(layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{uid()}"))')
    cx, cy = 7.5, 2.5
    body = [_rect(cx - 6.25, cy - 6.7, cx + 6.25, cy + 6.7, "F.Fab"),
            f'(fp_circle (center {cx} {cy}) (end {cx + 3} {cy}) (stroke (width 0.1) (type default)) (fill no) (layer "F.Fab") (uuid "{uid()}"))',
            _line(cx - 6.36, cy - 4.6, cx - 6.36, cy + 4.6, "F.SilkS"),   # the switch pads mark the other side
            _rect(-1.25, cy - 8.4, 15.75, cy + 8.4, "F.CrtYd", 0.05)] + pads
    text = _fp("RotaryEncoder_Bourns_PEC11R-S_Vertical",
               "Bourns PEC11R incremental encoder with push switch, vertical, through-hole: pins A C B at 2.5 mm, switch at 14.5 mm, tabs 13.2 mm apart (datasheet PCB layout). https://www.bourns.com/docs/Product-Datasheets/PEC11R.pdf",
               "rotary encoder PEC11R", "through_hole", "\n".join(body), ref_at=(7.5, -7.5), value_at=(7.5, 12.5))
    with open(os.path.join(LIB, "pqconsole.pretty", "RotaryEncoder_Bourns_PEC11R-S_Vertical.kicad_mod"), "w") as f:
        f.write(text)


def write_button_footprint():
    """HRO K2-1102SP, a 6 x 6 mm SMD tact switch, from its datasheet: four 1.9 x 1.0 mm pads, 7.2 mm
    apart inside and 4.5 mm between rows. The two pads of a row are joined inside the switch."""
    uid = gen.uid
    pads = [f'(pad "{"1" if y < 0 else "2"}" smd rect (at {x} {y}) (size 1.9 1.0) (layers "F.Cu" "F.Mask" "F.Paste") (uuid "{uid()}"))'
            for x in (-4.55, 4.55) for y in (-2.25, 2.25)]
    body = [_rect(-3, -3, 3, 3, "F.Fab"),
            f'(fp_circle (center 0 0) (end 1.7 0) (stroke (width 0.1) (type default)) (fill no) (layer "F.Fab") (uuid "{uid()}"))',
            _line(-3.1, -1.5, -3.1, 1.5, "F.SilkS"), _line(3.1, -1.5, 3.1, 1.5, "F.SilkS"),
            _line(-2.9, -3.1, 2.9, -3.1, "F.SilkS"), _line(-2.9, 3.1, 2.9, 3.1, "F.SilkS"),
            _rect(-5.75, -3.35, 5.75, 3.35, "F.CrtYd", 0.05)] + pads
    text = _fp("SW_HRO_K2-1102SP_6x6mm", "HRO K2-1102SP 6x6 mm SMD tactile switch (the K4SC part is 9 mm tall). https://datasheet.lcsc.com/lcsc/1912111437_Korean-Hroparts-Elec-K2-1102SP-K4SC-04_C129461.pdf",
               "switch tactile SMD 6x6", "smd", "\n".join(body), ref_at=(0, -4.2), value_at=(0, 4.2))
    with open(os.path.join(LIB, "pqconsole.pretty", "SW_HRO_K2-1102SP_6x6mm.kicad_mod"), "w") as f:
        f.write(text)


def write_screen_footprint():
    """The screen module in one footprint: its header, its corner holes and its outline, so they
    can't drift apart. Origin at the module's centre. A placeholder until measured: see SCREEN."""
    uid = gen.uid
    w, h = SCREEN["w"] / 2, SCREEN["h"] / 2
    x = -w + SCREEN["header_dx"]
    pads = []
    n = len(SCREEN["pins"])
    for i, sig in enumerate(SCREEN["pins"]):
        y = (i - (n - 1) / 2) * 2.54
        pads.append(f'(pad "{i + 1}" thru_hole {"rect" if i == 0 else "circle"} (at {x:.2f} {y:.2f}) (size 1.7 1.7) '
                    f'(drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{uid()}"))')
        pads.append(f'(fp_text user "{sig}" (at {x + 1.6:.2f} {y:.2f} 0) (layer "F.Fab") (uuid "{uid()}") '
                    f'(effects (font (size 0.8 0.8) (thickness 0.12)) (justify left)))')
    d, k = SCREEN["hole_d"], SCREEN["hole_inset"]
    for hx in (-w + k, w - k):
        for hy in (-h + k, h - k):
            pads.append(f'(pad "" np_thru_hole circle (at {hx} {hy}) (size {d} {d}) (drill {d}) (layers "*.Cu" "*.Mask") (uuid "{uid()}"))')
    body = [_rect(-w, -h, w, h, "F.Fab"), _rect(-w - 0.1, -h - 0.1, w + 0.1, h + 0.1, "F.SilkS", 0.15),
            _rect(-w - 0.25, -h - 0.25, w + 0.25, h + 0.25, "F.CrtYd", 0.05),
            f'(fp_text user "PLACEHOLDER: measure your module" (at 0 0 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1.5 1.5) (thickness 0.2))))'] + pads
    text = _fp("Screen_ST7789_2.8in_8P_PLACEHOLDER",
               f"2.8in 240x320 ST7789 SPI module, 8-pin header on the left, {SCREEN['w']} x {SCREEN['h']} mm, M3 corner holes. PLACEHOLDER numbers until a module is measured (gen_console.py SCREEN)",
               "display ST7789 module", "through_hole", "\n".join(body), ref_at=(0, -h - 1.5), value_at=(0, h + 1.5))
    with open(os.path.join(LIB, "pqconsole.pretty", "Screen_ST7789_2.8in_8P_PLACEHOLDER.kicad_mod"), "w") as f:
        f.write(text)


# =================================================================================================
# Schematic: every pin gets a short stub and a net label (or a power symbol), so the sheet reads as
# blocks and the connections are by name.
# =================================================================================================

def _pins(sym):
    """(number, x, y, angle) of each pin's connection point, in symbol coordinates (y up)."""
    return [(n, float(x), float(y), int(a)) for x, y, a, n in
            re.findall(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(number "([^"]+)"', sym, re.S)]


OUT = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}    # a pin's outward direction on the sheet
GND_ROT = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}
VCC_ROT = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}


class Schematic:
    def __init__(self):
        self.sh = gen.Sheet(NAME)
        self.syms = {}

    def lib(self, lib_id, text):
        name = lib_id.split(":")[1]
        self.sh.lib(lib_id, text.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
                    if not text.startswith(f'(symbol "{lib_id}"') else text)
        self.syms[lib_id] = text

    def part(self, lib_id, ref, value, x, y, nets, fp="", fields=(), dnp=False, in_bom=True, on_board=None, box_h=None):
        pins = _pins(self.syms[lib_id])
        self.sh.symbol(lib_id, ref, value, x, y, [p[0] for p in pins], fp=fp, fields=fields, dnp=dnp,
                       in_bom=in_bom, on_board=on_board, box_h=box_h)
        done = {}
        for num, px, py, ang in pins:
            cx, cy = round(x + px, 2), round(y - py, 2)
            net = nets.get(num)
            if (cx, cy) in done:
                assert done[(cx, cy)] == net, (ref, num)
                continue
            done[(cx, cy)] = net
            if net is None:
                self.sh.nc(cx, cy)
                continue
            ox, oy = OUT[ang]
            ex, ey = round(cx + 2.54 * ox, 2), round(cy + 2.54 * oy, 2)
            self.sh.wire(cx, cy, ex, ey)
            if net == "GND":
                self.sh.power("GND", ex, ey, rot=GND_ROT[(ox, oy)])
            elif net == "+3V3":
                self.sh.power("+3V3", ex, ey, rot=VCC_ROT[(ox, oy)])
            else:
                self.sh.label(net, ex, ey, left=ox < 0)


def write_schematic(syms):
    s = Schematic()
    for name in ("Pico_2_W", "USB_C_Plug_16P", "AP22653", "USBLC6-2SC6"):
        s.lib(f"pqconsole:{name}", syms[name])
    for lib, name in (("Device", "R"), ("Device", "C"), ("Device", "LED"), ("Device", "D_Zener"),
                      ("Device", "RotaryEncoder_Switch"), ("Switch", "SW_Push"), ("Connector_Generic", "Conn_01x08"),
                      ("Connector", "TestPoint"), ("power", "GND"), ("power", "+3V3"), ("power", "PWR_FLAG")):
        s.lib(f"{lib}:{name}", gen.stock_symbol(lib, name))
    F = lambda p, desc, **kw: ([("Datasheet", P[p]["ds"])] if P[p].get("ds") else []) + [("MPN", P[p]["mpn"])] + \
        ([("LCSC", P[p]["lcsc"])] if P[p].get("lcsc") else []) + [("Description", desc)]
    R = lambda v, desc: [("LCSC", LCSC_R[v]), ("Description", desc)]
    C = lambda v, desc: [("LCSC", LCSC_C[v]), ("Description", desc)]
    gp = {f"GP{v}": k for k, v in {**GPIO, **NEW_GPIO}.items()}

    # U1, the Pico 2 W
    nets = {}
    for n, sig in PICO.items():
        nets[str(n)] = ("GND" if sig in ("GND", "AGND") else "+3V3" if sig == "3V3" else gp.get(sig))
    s.part("pqconsole:Pico_2_W", "U1", "Pico 2 W", 76.2, 101.6, nets, fp=P["pico"]["fp"], box_h=26.67,
           fields=F("pico", "The console's computer and its Wi-Fi. JLCPCB solders it flat by its castellations"))
    s.sh.text("Build 1's pins (firmware/board.py \"build1\"):\n"
              "secrets.py BOARD = \"build1\", SCREEN = \"2.8\".\n"
              "GP6, GP14, GP22, GP26, GP27 are new here:\n"
              "today's console image doesn't touch them.\n"
              "Micro-USB on the Pico: power and updates.", 50.8, 139.7)
    s.sh.power("GND", 50.8, 160.02, rot=0)
    s.sh.wire(50.8, 160.02, 50.8, 157.48)
    s.sh.power("PWR_FLAG", 50.8, 157.48, rot=0)

    # The key port: J1, the switch U2, ESD U3 (I2C) and U4 (CC), the TVS D1
    s.part("pqconsole:USB_C_Plug_16P", "J1", "USB-C plug", 152.4, 63.5,
           {"A4": "VKEY", "A9": "VKEY", "B4": "VKEY", "B9": "VKEY", "A5": "CC1", "B5": "CC2",
            "A6": "KEY_SDA", "B6": None, "A7": "KEY_SCL", "B7": None, "A8": None, "B8": None,
            "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND"}, fp=P["plug"]["fp"], box_h=10.16,
           fields=F("plug", "The key port: key-c slides onto this vertical plug. I2C on the USB 2.0 pairs, no USB"))
    s.part("pqconsole:AP22653", "U2", "AP22653W6-7", 203.2, 50.8,
           {"1": "+3V3", "3": "KEY_EN", "6": "VKEY", "4": "KEY_FAULT", "2": "GND", "5": "GND"}, fp=P["switch"]["fp"],
           box_h=5.08, fields=F("switch", "Key power: 80 mA limit (ILIM to GND), reverse blocking, output discharge"))
    s.part("Device:R", "R7", "10k", 182.88, 50.8, {"1": "+3V3", "2": "KEY_EN"}, fp=R0402,
           fields=R("10k", "KEY_EN pull-up: the key is powered unless firmware drives GP6 low"))
    s.part("Device:R", "R8", "10k", 228.6, 50.8, {"1": "+3V3", "2": "KEY_FAULT"}, fp=R0402,
           fields=R("10k", "Pull-up for the switch's open-drain FAULT flag"))
    s.part("Device:C", "C1", "100n", 193.04, 71.12, {"1": "+3V3", "2": "GND"}, fp=C0402,
           fields=C("100n", "At U2's IN, as the datasheet asks"))
    s.part("Device:C", "C2", "10u", 213.36, 71.12, {"1": "VKEY", "2": "GND"}, fp=C0603,
           fields=C("10u", "At U2's OUT: the key's supply"))
    s.part("Device:D_Zener", "D1", "ESD5Z5V0", 223.52, 71.12 + 3.81, {"1": "VKEY", "2": "GND"}, fp=P["tvs"]["fp"],
           fields=F("tvs", "TVS on the key's VBUS: the plug's one line with no array on it"))
    s.part("pqconsole:USBLC6-2SC6", "U3", "USBLC6-2SC6", 203.2, 101.6,
           {"1": "KEY_SDA", "6": "KEY_SDA", "3": "KEY_SCL", "4": "KEY_SCL", "5": "+3V3", "2": "GND"},
           fp=P["esd"]["fp"], box_h=10.16, fields=F("esd", "ESD on SDA and SCL at the plug. Rail on 3V3, never on VKEY"))
    s.part("pqconsole:USBLC6-2SC6", "U4", "USBLC6-2SC6", 203.2, 147.32,
           {"1": "CC1", "6": "CC1", "3": "CC2", "4": "CC2", "5": "+3V3", "2": "GND"},
           fp=P["esd"]["fp"], box_h=10.16, fields=F("esd", "ESD on CC1 and CC2 at the plug. Rail on 3V3"))
    for i, (ref, net) in enumerate((("R1", "KEY_SDA"), ("R2", "KEY_SCL"))):
        s.part("Device:R", ref, "2.2k", 238.76 + 10.16 * i, 101.6, {"1": "VKEY", "2": net}, fp=R0402,
               fields=R("2.2k", f"{net} pull-up to the switched VKEY (the key has none): 2.2k for a 300 ns rise"))
    for i, (cc, sense) in enumerate((("CC1", "CC1_SENSE"), ("CC2", "CC2_SENSE"))):
        x = 238.76 + 10.16 * i
        s.part("Device:R", f"R{3 + i}", "10k", x, 139.7, {"1": "+3V3", "2": cc}, fp=R0402,
               fields=R("10k", f"Pull-up on {cc}: with the key's 5.1k Rd it reads about 1.1 V"))
        s.part("Device:R", f"R{5 + i}", "1k", x, 157.48, {"1": cc, "2": sense}, fp=R0402,
               fields=R("1k", f"{cc} into the ADC, current-limited"))
    s.sh.text("The console end of key-c (hardware/key-pcb/PROPOSALS.md):\n"
              "- VKEY comes through U2: 80 mA limit, reverse blocking,\n"
              "  discharged when off. Never straight from a GPIO.\n"
              "- CC1 and CC2 read on their own ADC pins. Plugged\n"
              "  straight in, a key shows 5.1k on both.\n"
              "- 2.2k pull-ups to VKEY, so a key that's off isn't\n"
              "  powered through SDA/SCL.\n"
              "- U3/U4 rails on 3V3: the CC pull-ups can't feed VKEY.", 139.7, 167.64)

    # The screen, the knob (with its A/B swap resistors) and the buttons
    s.part("Connector_Generic:Conn_01x08", "J2", "Screen 2.8in", 76.2, 198.12,
           {str(i + 1): SCREEN_NET[sig] for i, sig in enumerate(SCREEN["pins"])}, fp=P["screen"]["fp"],
           fields=F("screen", "The screen module's 8-pin header (soldered by hand). Pin order: check your module"))
    s.part("Device:RotaryEncoder_Switch", "SW1", "PEC11R-4215F-S0024", 152.4, 203.2,
           {"A": "ENC_A", "B": "ENC_B", "C": "GND", "S1": "KNOB_SW", "S2": "GND"}, fp=P["knob"]["fp"],
           fields=F("knob", "The knob: turn to move, press to choose. 24 detents, 24 pulses. "
                            "Through-hole, soldered by hand (LCSC C143790)"))
    for i, (ref, a, b, fit) in enumerate((("R10", "ENC_A", "KNOB_GP2", True), ("R11", "ENC_B", "KNOB_GP3", True),
                                          ("R12", "ENC_A", "KNOB_GP3", False), ("R13", "ENC_B", "KNOB_GP2", False))):
        s.part("Device:R", ref, "0R", 182.88 + 10.16 * i, 203.2, {"1": a, "2": b}, fp=R0402, dnp=not fit,
               fields=R("0R", "Knob direction: R10/R11 fitted wires it as Build 1's bench. "
                              "If clockwise goes backwards, move them to R12/R13"))
    for i, (ref, net, label) in enumerate((("SW2", "BTN_SIGN", "Sign (A)"), ("SW3", "BTN_BACK", "Back (B)"),
                                           ("SW4", "BTN_DEVICE", "Device (X)"), ("SW5", "BTN_REJECT", "Reject (Y)"))):
        s.part("Switch:SW_Push", ref, label, 256.54 + 22.86 * (i % 2), 195.58 + 15.24 * (i // 2), {"1": net, "2": "GND"},
               fp=P["button"]["fp"], fields=F("button", f"{label}: to GND, the firmware's pull-up"))
    s.sh.text("Hold at power-up: Y = Wi-Fi setup, knob = maintenance.\n"
              "Sign is held 2 s (3 s on a red page).", 243.84, 233.68)

    # The LED and the test pads
    s.part("Device:R", "R9", "1k", 279.4, 63.5, {"1": "LED", "2": "LED_A"}, fp=R0402,
           fields=R("1k", "LED current, about 1 mA"))
    s.part("Device:LED", "D2", "red", 289.56, 71.12, {"2": "LED_A", "1": "GND"}, fp=P["led"]["fp"],
           fields=F("led", "Status LED on GP22: for a later firmware"))
    for i, net in enumerate(("GND", "+3V3", "VKEY", "KEY_SDA", "KEY_SCL", "CC1", "CC2")):
        s.part("Connector:TestPoint", f"TP{i + 1}", net.lstrip("+"), 279.4 + 7.62 * i, 101.6, {"1": net},
               fp="TestPoint:TestPoint_Pad_D1.5mm", in_bom=False, on_board=True,
               fields=[("Description", f"Test pad on the back: {net}")])

    path = os.path.join(HERE, NAME, NAME + ".kicad_sch")
    s.sh.write(path, TITLE)
    t = open(path).read()
    t = t.replace('(paper "A4")', '(paper "A3")', 1).replace(f'(date "{gen.DATE}")', f'(date "{DATE}")', 1)
    t = t.replace('(rev "A")', f'(rev "{REV}")', 1)
    t = t.replace('(comment 1 "The PCB is the plug: see hardware/key-pcb/README.md")',
                  '(comment 1 "Console carrier: see hardware/console-pcb/README.md")', 1)
    open(path, "w").write(t)


def write_lib_tables(d):
    with open(os.path.join(d, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "pqconsole")(type "KiCad")'
                '(uri "${KIPRJMOD}/../lib/pqconsole.kicad_sym")(options "")(descr "PicoQuorum console parts"))\n)\n')
    with open(os.path.join(d, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n'
                '  (lib (name "pqconsole")(type "KiCad")(uri "${KIPRJMOD}/../lib/pqconsole.pretty")(options "")(descr "PicoQuorum console footprints"))\n'
                '  (lib (name "picoquorum")(type "KiCad")(uri "${KIPRJMOD}/../../key-pcb/lib/picoquorum.pretty")(options "")(descr "PicoQuorum key footprints: the mark"))\n)\n')


# =================================================================================================
# The board
# =================================================================================================
W, H = 160.0, 51.0          # the outline, before the antenna cut-out
CORNER_R = 1.5
PICO_AT = (13.0, 25.5)      # the module fills the board's height: antenna at the top, micro-USB at the bottom
NOTCH = (PICO_AT[0] - 7.1, PICO_AT[0] + 7.1, 8.5)   # x0, x1, depth: no board under the antenna (datasheet 2.2.1)
SCREEN_AT = (41.0 + SCREEN["w"] / 2, H / 2)
KNOB_A = (136.0, 11.0)      # the knob's pin A; its shaft is 7.5 mm right of it and 2.5 mm down

# ref -> (x, y, rotation, side). Side B parts are flipped onto the bottom.
PARTS = {
    "U1": (*PICO_AT, 180, "F"), "J2": (*SCREEN_AT, 0, "F"), "SW1": (*KNOB_A, 0, "F"),
    "SW2": (151.5, 29.0, 0, "F"), "SW3": (135.5, 29.0, 0, "F"), "SW4": (135.5, 40.0, 0, "F"), "SW5": (151.5, 40.0, 0, "F"),
    "R10": (131.0, 9.5, 0, "F"), "R11": (131.0, 11.0, 0, "F"), "R12": (131.0, 12.5, 0, "F"), "R13": (131.0, 14.0, 0, "F"),
    "D2": (130.0, 3.5, 0, "F"), "R9": (133.0, 3.5, 0, "F"),
    # the key port, in the gap between the Pico and the screen: the plug, its ESD arrays either side
    # of the signal rows (U3 for SDA/SCL, U4 for CC), the switch U2 above it
    "J1": (34.0, 40.5, 0, "F"),
    "U3": (28.5, 40.5, 0, "F"), "U4": (34.0, 47.6, 0, "F"),
    "U2": (34.0, 31.0, 0, "F"), "C1": (30.5, 29.0, 90, "F"), "C2": (37.5, 29.5, 90, "F"), "D1": (37.5, 33.5, 90, "F"),
    "R7": (30.5, 33.0, 90, "F"), "R8": (37.5, 26.0, 0, "F"),
    "R1": (27.0, 36.5, 0, "F"), "R2": (27.0, 38.0, 0, "F"),
    "R3": (29.5, 45.5, 90, "F"), "R5": (29.5, 48.5, 90, "F"), "R4": (38.5, 45.5, 90, "F"), "R6": (38.5, 48.5, 90, "F"),
    # test pads on the back, under the screen
    **{f"TP{i + 1}": (49.0 + 3.0 * i, 47.5, 0, "B") for i in range(7)},
}
# Pads too boxed in for the router to find a via beside: a short track straight out of the pad and a
# via at its end, laid before anything else. (ref, pad, dx, dy): the ESD arrays' rail and ground pins
# sit between the two lines they protect, as do the switch's GND and ILIM.
ESCAPES = [("U3", "2", -1.2, 0), ("U3", "5", 1.2, 0), ("U4", "2", -1.2, 0), ("U4", "5", 1.2, 0),
           ("U2", "2", -1.2, 0), ("U2", "5", 1.2, 0)]
# Nets routed first, in this order: the key port's, then power. The rest go shortest first.
FIRST = ["/KEY_SDA", "/KEY_SCL", "/CC1", "/CC2", "/VKEY", "+3V3", "/KEY_EN", "/KEY_FAULT"]
# The top layer around the key port is for the key port's own nets: everything else passes under it
# on the bottom layer. (layer, x0, y0, x1, y1, nets allowed)
KEYPORT = {"/KEY_SDA", "/KEY_SCL", "/CC1", "/CC2", "/VKEY", "+3V3", "/KEY_EN", "/KEY_FAULT",
           "/CC1_SENSE", "/CC2_SENSE", "GND"}
RESERVED = [(0, 25.5, 25.5, 40.5, H, KEYPORT)]
# The screen's four corner holes hold the board too; these two take the right-hand end.
HOLES = [("H2", 156.5, 3.5), ("H3", 156.5, 47.5)]


def outline_points():
    x0, x1, d = NOTCH
    return [(0, 0), (x0, 0), (x0, d), (x1, d), (x1, 0), (W, 0), (W, H), (0, H)]


def _outline(board):
    """Rounded outer corners, and the square cut-out under the Pico's antenna."""
    import pcbnew
    E, r = pcbnew.Edge_Cuts, CORNER_R
    x0, x1, d = NOTCH
    gen._seg(board, (r, 0), (x0, 0), E)
    gen._seg(board, (x0, 0), (x0, d), E)
    gen._seg(board, (x0, d), (x1, d), E)
    gen._seg(board, (x1, d), (x1, 0), E)
    gen._seg(board, (x1, 0), (W - r, 0), E)
    gen._seg(board, (W, r), (W, H - r), E)
    gen._seg(board, (W - r, H), (r, H), E)
    gen._seg(board, (0, H - r), (0, r), E)
    gen._arc(board, (W - r, r), (W - r, 0), 90)
    gen._arc(board, (W - r, H - r), (W, H - r), 90)
    gen._arc(board, (r, H - r), (r, H), 90)
    gen._arc(board, (r, r), (0, r), 90)


def _zones(board, gnd):
    import pcbnew
    whole = [(-1, -1), (W + 1, -1), (W + 1, H + 1), (-1, H + 1)]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        gen._zone_poly(z, whole)
        z.SetLocalClearance(pcbnew.FromMM(0.25))
        z.SetMinThickness(pcbnew.FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)   # SMD pads solid, through-hole on spokes
        z.SetZoneName("GND " + ("top" if layer == pcbnew.F_Cu else "bottom"))
        board.Add(z)


def _silk(board):
    import pcbnew
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    for ref, label in (("SW2", "SIGN"), ("SW3", "BACK"), ("SW4", "DEVICE"), ("SW5", "REJECT")):
        x, y, _, _ = PARTS[ref]
        gen._text(board, label, x, y + 4.6, F, 1.0)
    gen._text(board, "KEY", PARTS["J1"][0], 35.4, F, 1.0)
    gen._text(board, "PICOQUORUM", 144.0, 49.4, F, 1.0)
    for i, s in enumerate((f"PicoQuorum console-a {REV} {DATE[:7]}",
                           "BOARD=build1 SCREEN=2.8 (firmware/board.py)",
                           "hold Y at power-up: Wi-Fi setup; hold the knob: maintenance",
                           "github.com/jmcpheron/pico-quorum  CERN-OHL-W")):
        gen._text(board, s, SCREEN_AT[0], 6.0 + 2.0 * i, B, 1.0 if i == 0 else 0.8, mirror=True)
    for i in range(7):
        x, y, _, _ = PARTS[f"TP{i + 1}"]
        net = ("GND", "3V3", "VKEY", "SDA", "SCL", "CC1", "CC2")[i]
        gen._text(board, net, x, y - 2.0, B, 0.8, mirror=True)


def _mark(board):
    import pcbnew
    fp = pcbnew.FootprintLoad(os.path.join(KEYLIB, "picoquorum.pretty"), "PicoQuorum_Mark")
    fp.SetFPID(pcbnew.LIB_ID("picoquorum", "PicoQuorum_Mark"))
    fp.SetReference("LOGO1"); fp.Reference().SetVisible(False)
    fp.SetBoardOnly(True)
    board.Add(fp)
    fp.SetPosition(gen._mm(SCREEN_AT[0], 24.0))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def read_netlist():
    """gen_cd's reader, pointed at this directory."""
    keep = gen_cd.HERE
    gen_cd.HERE = HERE
    try:
        return gen_cd.read_netlist(NAME)
    finally:
        gen_cd.HERE = keep


def write_board(netlist):
    import pcbnew
    gen.OX, gen.OY = 100.0, 100.0
    path = os.path.join(HERE, NAME, NAME + ".kicad_pcb")
    if os.path.exists(path):
        os.remove(path)
    board = pcbnew.NewBoard(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
    ds.SetAuxOrigin(gen._mm(0, H))      # Gerbers, drill and CPL measure from the bottom-left corner
    tb = board.GetTitleBlock()
    tb.SetTitle(TITLE); tb.SetDate(DATE); tb.SetRevision(REV); tb.SetCompany("PicoQuorum")

    nets = {}
    for n in sorted({net for comp in netlist.values() for net in comp["pads"].values()}):
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    fps = {}
    for ref, comp in netlist.items():
        lib, fpname = comp["footprint"].split(":")
        libdir = os.path.join(LIB, "pqconsole.pretty") if lib == "pqconsole" else os.path.join(gen.KIFP, lib + ".pretty")
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
        fp.SetDNP(comp["dnp"])
        board.Add(fp)
        x, y, rot, side = PARTS[ref]
        fp.SetPosition(gen._mm(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for pad in fp.Pads():
            net = comp["pads"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        # references go on the fab layer: the labels that matter are the board's own text
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fps[ref] = fp
    for ref, x, y in HOLES:
        gen_cd._hole(board, ref, "MountingHole_3.2mm_M3", x, y, "M3")

    _outline(board)
    Router(board, nets).run()
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
    gen_cd._stackup(path, "HASL(with lead-free)")
    gen._rules(os.path.join(HERE, NAME, NAME + ".kicad_pro"))


# =================================================================================================
# The router: a plain grid router, enough for a two-layer board this sparse.
# - A 0.25 mm grid on both layers. Every track is 0.25 mm with 0.2 mm clearance; vias 0.6/0.3 mm.
# - A cell is free for a net when no other net's copper, no board edge and no keep-out is within
#   reach of a track (or a via) centred there. Pad shapes come from KiCad itself.
# - Each net grows as a tree: every pad in turn is joined to the nearest copper the net already has,
#   by A*. Top-layer runs prefer x, bottom-layer runs prefer y, and a via costs six steps.
# - Then every SMD ground pad gets a via to the bottom pour, and a sparse grid of stitching vias
#   ties the two pours together.
# DRC (tools/keypcb check) is the judge; this only has to give it nothing to complain about.
# =================================================================================================
GRID, TRACK, CLEAR, VIA_D, VIA_DRILL = 0.25, 0.25, 0.2, 0.6, 0.3
# A track centre this close to foreign copper would break clearance. The extra 0.035 covers the
# middle of a 0.25 mm step, which can pass nearer a corner than either end does.
REACH_T = TRACK / 2 + CLEAR + 0.035
REACH_V = VIA_D / 2 + CLEAR + 0.01
EDGE_T, EDGE_V = TRACK / 2 + 0.3 + 0.05, VIA_D / 2 + 0.3 + 0.05   # 0.3 mm copper to edge
VIA_COST, WRONG_WAY, BEND = 6.0, 0.4, 0.4


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


class Router:
    def __init__(self, board, nets):
        import pcbnew
        self.pcbnew, self.board, self.nets = pcbnew, board, nets
        self.nx, self.ny = int(round(W / GRID)) + 1, int(round(H / GRID)) + 1
        self.near = [dict(), dict()]    # cell -> nets within REACH_T (or "*": nothing may go here)
        self.vnear = [dict(), dict()]   # cell -> nets within REACH_V
        self.novia = set()              # cells where a via would sit in a pad or too close to a hole
        self.own = {}                   # net -> nodes (layer, cell) that are already its copper
        self.pads = {}                  # net -> [(pad, nodes)]
        self.added = []                 # the tracks and vias laid so far
        self.failed = []
        self.res = [dict(), dict()]     # cell -> the only nets allowed there (RESERVED)
        for layer, x0, y0, x1, y1, allowed in RESERVED:
            for c, _, _ in self._cells(x0, y0, x1, y1):
                self.res[layer][c] = allowed
        self._edges()
        self._footprints()
        self.base = ([{c: set(s) for c, s in m.items()} for m in self.near],
                     [{c: set(s) for c, s in m.items()} for m in self.vnear], set(self.novia))

    def reset(self):
        """Take up every track and via, back to the parts alone."""
        for item in self.added:
            self.board.Remove(item)
        self.added, self.own, self.failed = [], {}, []
        near, vnear, novia = self.base
        self.near = [{c: set(s) for c, s in m.items()} for m in near]
        self.vnear = [{c: set(s) for c, s in m.items()} for m in vnear]
        self.novia = set(novia)

    # --- the grid ---------------------------------------------------------------------------------
    def cell(self, i, j):
        return j * self.nx + i

    def xy(self, c):
        return (c % self.nx) * GRID, (c // self.nx) * GRID

    def _cells(self, x0, y0, x1, y1):
        i0, i1 = max(0, int(math.floor(x0 / GRID))), min(self.nx - 1, int(math.ceil(x1 / GRID)))
        j0, j1 = max(0, int(math.floor(y0 / GRID))), min(self.ny - 1, int(math.ceil(y1 / GRID)))
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                yield self.cell(i, j), i * GRID, j * GRID

    def _mark(self, layer, net, dist, bbox):
        x0, y0, x1, y1 = bbox
        for c, x, y in self._cells(x0 - REACH_V, y0 - REACH_V, x1 + REACH_V, y1 + REACH_V):
            d = dist(x, y)
            if d < REACH_V:
                self.vnear[layer].setdefault(c, set()).add(net)
                if d < REACH_T:
                    self.near[layer].setdefault(c, set()).add(net)

    def free(self, layer, c, net):
        r = self.res[layer].get(c)
        if r is not None and net not in r:
            return False
        s = self.near[layer].get(c)
        return s is None or (len(s) == 1 and net in s)

    def via_ok(self, c, net):
        if c in self.novia:
            return False
        for layer in (0, 1):
            r = self.res[layer].get(c)
            if r is not None and net not in r:
                return False
            s = self.vnear[layer].get(c)
            if s is not None and not (len(s) == 1 and net in s):
                return False
        return True

    # --- what's already on the board ---------------------------------------------------------------
    def _edges(self):
        pts = outline_points()
        segs = list(zip(pts, pts[1:] + pts[:1]))

        def inside(x, y):
            n = False
            for (ax, ay), (bx, by) in segs:
                if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                    n = not n
            return n
        for c, x, y in self._cells(0, 0, W, H):
            d = min(_seg_dist(x, y, *a, *b) for a, b in segs)
            # the rounded corners stay inside the square ones; CORNER_R of margin covers them
            corner = min(math.hypot(x - cx, y - cy) for cx, cy in ((0, 0), (W, 0), (0, H), (W, H)))
            if not inside(x, y) or d < EDGE_V or corner < CORNER_R + EDGE_V:
                for layer in (0, 1):
                    self.vnear[layer].setdefault(c, set()).add("*")
                    if not inside(x, y) or d < EDGE_T or corner < CORNER_R + EDGE_T:
                        self.near[layer].setdefault(c, set()).add("*")

    def _poly_dist(self, poly):
        pcbnew = self.pcbnew

        def dist(x, y):
            p = pcbnew.VECTOR2I(pcbnew.FromMM(gen.OX + x), pcbnew.FromMM(gen.OY + y))
            if poly.Collide(p, 0):
                return 0.0
            if poly.Collide(p, pcbnew.FromMM(REACH_T)):
                return REACH_T - 0.001
            if poly.Collide(p, pcbnew.FromMM(REACH_V)):
                return REACH_V - 0.001
            return 99.0
        return dist

    def _bbox(self, box):
        pcbnew = self.pcbnew
        return (pcbnew.ToMM(box.GetLeft()) - gen.OX, pcbnew.ToMM(box.GetTop()) - gen.OY,
                pcbnew.ToMM(box.GetRight()) - gen.OX, pcbnew.ToMM(box.GetBottom()) - gen.OY)

    def _footprints(self):
        pcbnew = self.pcbnew
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                net = pad.GetNetname() or "*"
                layers = [l for l, L in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if pad.IsOnLayer(L)]
                bbox = self._bbox(pad.GetBoundingBox())
                nodes = set()
                for layer, L in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
                    if layer not in layers and not pad.HasHole():
                        continue
                    poly = pad.GetEffectivePolygon(L) if layer in layers else None
                    if poly is None:      # a hole through a layer the pad's copper isn't on
                        hx, hy = gen._key(pad.GetPosition())
                        r = pcbnew.ToMM(pad.GetDrillSize().x) / 2
                        self._mark(layer, "*", lambda x, y: math.hypot(x - hx, y - hy) - r, bbox)
                        continue
                    dist = self._poly_dist(poly)
                    self._mark(layer, net, dist, bbox)
                    if net != "*":
                        for c, x, y in self._cells(*bbox):
                            if dist(x, y) == 0.0:
                                nodes.add((layer, c))
                for c, x, y in self._cells(bbox[0] - 0.4, bbox[1] - 0.4, bbox[2] + 0.4, bbox[3] + 0.4):
                    self.novia.add(c)
                if pad.HasHole():
                    hx, hy = gen._key(pad.GetPosition())
                    r = max(pcbnew.ToMM(pad.GetDrillSize().x), pcbnew.ToMM(pad.GetDrillSize().y)) / 2
                    for c, x, y in self._cells(hx - r - 1, hy - r - 1, hx + r + 1, hy + r + 1):
                        if math.hypot(x - hx, y - hy) < r + VIA_DRILL / 2 + 0.55:
                            self.novia.add(c)
                if net != "*" and nodes:
                    self.pads.setdefault(net, []).append((pad, nodes))
            for z in fp.Zones():
                if not z.GetIsRuleArea():
                    continue
                poly = z.Outline()
                bbox = self._bbox(poly.BBox())
                dist = self._poly_dist(poly)
                for layer, L in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
                    if z.GetLayerSet().Contains(L) and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                        self._mark(layer, "*", dist, bbox)

    # --- laying copper ------------------------------------------------------------------------------
    def _add_track(self, net, layer, a, b):
        pcbnew = self.pcbnew
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(gen._mm(*a)); t.SetEnd(gen._mm(*b))
        t.SetWidth(pcbnew.FromMM(TRACK))
        t.SetLayer(pcbnew.F_Cu if layer == 0 else pcbnew.B_Cu)
        t.SetNet(self.nets[net])
        self.board.Add(t)
        self.added.append(t)
        (ax, ay), (bx, by) = a, b
        self._mark(layer, net, lambda x, y: _seg_dist(x, y, ax, ay, bx, by) - TRACK / 2,
                   (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))
        for c, x, y in self._cells(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)):
            if _seg_dist(x, y, ax, ay, bx, by) < 0.01:
                self.own.setdefault(net, set()).add((layer, c))

    def _add_via(self, net, c):
        pcbnew = self.pcbnew
        x, y = self.xy(c)
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(gen._mm(x, y))
        v.SetWidth(pcbnew.FromMM(VIA_D)); v.SetDrill(pcbnew.FromMM(VIA_DRILL))
        v.SetNet(self.nets[net])
        self.board.Add(v)
        self.added.append(v)
        for layer in (0, 1):
            self._mark(layer, net, lambda px, py: math.hypot(px - x, py - y) - VIA_D / 2, (x, y, x, y))
            self.own.setdefault(net, set()).add((layer, c))
        for cc, px, py in self._cells(x - 1, y - 1, x + 1, y + 1):
            if math.hypot(px - x, py - y) < VIA_D / 2 + 0.5 + VIA_D / 2:   # hole to hole, any net
                self.novia.add(cc)

    def commit(self, net, path):
        """path: nodes (layer, cell) from start to goal. Straight runs become one track each, and a
        change of layer becomes a via."""
        runs, cur = [], [path[0]]
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                runs.append(cur)
                self._add_via(net, a[1])
                cur = [b]
            else:
                cur.append(b)
        runs.append(cur)
        for run in runs:
            layer = run[0][0]
            pts = [self.xy(c) for _, c in run]
            corners = [pts[0]]
            for p, q, r in zip(pts, pts[1:], pts[2:]):
                if (q[0] - p[0]) * (r[1] - q[1]) != (q[1] - p[1]) * (r[0] - q[0]):
                    corners.append(q)
            corners.append(pts[-1])
            for a, b in zip(corners, corners[1:]):
                if a != b:
                    self._add_track(net, layer, a, b)

    # --- A* -------------------------------------------------------------------------------------------
    def astar(self, net, starts, goal, targets=(), limit=600000):
        """starts: nodes; goal(node) -> True where the path may end; targets: nodes to aim at (for the
        heuristic only). Returns the path as a list of nodes, or None."""
        nx = self.nx
        pts = [self.xy(c) for _, c in targets]
        if pts:
            bx0, by0 = min(p[0] for p in pts), min(p[1] for p in pts)
            bx1, by1 = max(p[0] for p in pts), max(p[1] for p in pts)

            def h(c):
                x, y = (c % nx) * GRID, (c // nx) * GRID
                return (max(bx0 - x, 0, x - bx1) + max(by0 - y, 0, y - by1)) / GRID
        else:
            def h(c):
                return 0.0
        best, came, heap = {}, {}, []
        for n in starts:
            best[n] = 0.0
            came[n] = None
            heapq.heappush(heap, (h(n[1]), 0.0, n))
        steps = 0
        while heap:
            _, g, n = heapq.heappop(heap)
            if g > best.get(n, 1e18):
                continue
            if goal(n):
                path = [n]
                while came[path[-1]] is not None:
                    path.append(came[path[-1]])
                return path[::-1]
            steps += 1
            if steps > limit:
                return None
            layer, c = n
            i, j = c % nx, c // nx
            prev = came[n]
            pdir = None if prev is None or prev[0] != layer else c - prev[1]
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ii, jj = i + di, j + dj
                if not (0 <= ii < nx and 0 <= jj < self.ny):
                    continue
                cc = jj * nx + ii
                if not self.free(layer, cc, net):
                    continue
                cost = 1.0 + (WRONG_WAY if (dj != 0) == (layer == 0) else 0.0)
                if pdir is not None and pdir != cc - c:
                    cost += BEND
                m = (layer, cc)
                ng = g + cost
                if ng < best.get(m, 1e18):
                    best[m] = ng
                    came[m] = n
                    heapq.heappush(heap, (ng + h(cc), ng, m))
            if self.via_ok(c, net):
                m = (1 - layer, c)
                if self.free(1 - layer, c, net):
                    ng = g + VIA_COST
                    if ng < best.get(m, 1e18):
                        best[m] = ng
                        came[m] = n
                        heapq.heappush(heap, (ng + h(c), ng, m))
        return None

    # --- the order of work ------------------------------------------------------------------------
    def route_net(self, net):
        key = lambda pad: (pad.GetParentFootprint().GetReference(), pad.GetNumber())
        pads = [(pad, nodes | self.extra.get(key(pad), set())) for pad, nodes in self.pads[net]]
        cx = sum(gen._key(p.GetPosition())[0] for p, _ in pads) / len(pads)
        cy = sum(gen._key(p.GetPosition())[1] for p, _ in pads) / len(pads)
        pads.sort(key=lambda pn: math.hypot(gen._key(pn[0].GetPosition())[0] - cx, gen._key(pn[0].GetPosition())[1] - cy))
        own = self.own.setdefault(net, set())
        own |= pads[0][1]
        todo = pads[1:]
        while todo:
            # the pad nearest the tree so far goes next
            tree = [self.xy(c) for _, c in own]
            def gap(pn):
                px, py = gen._key(pn[0].GetPosition())
                return min(abs(px - x) + abs(py - y) for x, y in tree)
            todo.sort(key=gap)
            pad, nodes = todo.pop(0)
            if nodes & own:
                own |= nodes
                continue
            starts = [n for n in nodes if self.free(n[0], n[1], net)] or list(nodes)
            path = self.astar(net, starts, own.__contains__, targets=own)
            if path is None:
                self.failed.append((net, pad.GetParentFootprint().GetReference(), pad.GetNumber()))
                continue
            self.commit(net, path)
            own |= nodes

    def fanout(self, net="GND"):
        """A via beside every surface-mount ground pad, down to the bottom pour."""
        for pad, nodes in self.pads.get(net, []):
            if pad.HasHole():
                continue
            starts = [n for n in nodes if n[0] == 0]
            if not starts:
                continue
            ok = lambda n: n[0] == 0 and self.via_ok(n[1], net) and n not in nodes
            path = self.astar(net, starts, ok, limit=4000)
            if path is None:
                continue
            self.commit(net, path)
            self._add_via(net, path[-1][1])

    def stitch(self, net="GND", pitch=6.0):
        y = pitch / 2
        while y < H:
            x = pitch / 2
            while x < W:
                c = self.cell(int(round(x / GRID)), int(round(y / GRID)))
                if self.via_ok(c, net) and all(self.vnear[l].get(cc) is None
                                               for l in (0, 1) for cc, _, _ in self._cells(x - 0.75, y - 0.75, x + 0.75, y + 0.75)):
                    self._add_via(net, c)
                x += pitch
            y += pitch

    def escapes(self):
        """The ESCAPES stubs. Their copper counts as part of the pad, not yet part of the net's tree."""
        self.extra = {}
        for ref, num, dx, dy in ESCAPES:
            pad = self.board.FindFootprintByReference(ref).FindPadByNumber(num)
            net = pad.GetNetname()
            px, py = gen._key(pad.GetPosition())
            i, j = int(round((px + dx) / GRID)), int(round((py + dy) / GRID))
            before = set(self.own.get(net, ()))
            self._add_track(net, 0, (px, py), (i * GRID, j * GRID))
            self._add_via(net, self.cell(i, j))
            self.extra[(ref, num)] = self.own[net] - before
            self.own[net] = before

    def route_all(self, order):
        self.reset()
        self.escapes()
        for net in order:
            self.route_net(net)
        return [n for n, _, _ in self.failed]

    def run(self, tries=6):
        nets = [n for n in self.pads if n != "GND" and len(self.pads[n]) > 1]
        order = [n for n in FIRST if n in nets] + sorted((n for n in nets if n not in FIRST), key=self._span)
        best = None
        for _ in range(tries):
            failed = self.route_all(order)
            if best is None or len(failed) < len(best[1]):
                best = (list(order), failed)
            if not failed:
                break
            # what failed goes first next time, in the order it had
            order = [n for n in order if n in failed] + [n for n in order if n not in failed]
        if best[1] and best[0] != order:
            self.route_all(best[0])
        self.fanout()
        self.stitch()
        if self.failed:
            print("router: could not finish", ", ".join(f"{n} at {r}.{p}" for n, r, p in self.failed))

    def _span(self, net):
        xs = [gen._key(p.GetPosition()) for p, _ in self.pads[net]]
        return (max(x for x, _ in xs) - min(x for x, _ in xs)) + (max(y for _, y in xs) - min(y for _, y in xs))


# =================================================================================================

def main():
    check_firmware()
    os.makedirs(os.path.join(LIB, "pqconsole.pretty"), exist_ok=True)
    d = os.path.join(HERE, NAME)
    os.makedirs(d, exist_ok=True)
    syms = write_symbol_lib()
    write_pico_footprint()
    write_knob_footprint()
    write_button_footprint()
    write_screen_footprint()
    write_lib_tables(d)
    write_schematic(syms)
    write_board(read_netlist())


if __name__ == "__main__":
    main()
