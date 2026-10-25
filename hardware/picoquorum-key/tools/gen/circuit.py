"""picoquorum-key rev B: every part, its fields, its schematic position and the net on each pin.

This file is the single source for the generated schematic (gen_sch.py). The board generator
(gen_pcb.py) reads the schematic's own netlist, not this file, so the schematic stays the truth.

Every part is on every board. `fit` says which boards get it assembled: "base" on all of them,
"port" only on those ordered with the key port (section 7). The schematic carries it as each
symbol's Fit field, and tools/jlc_bom_cpl.py writes one BOM and CPL per fit from it.

Pin profile: docs/PINS.md. Circuits: docs/DESIGN.md.
"""

G = 2.54


def g(v):
    """Snap to the 2.54 mm schematic grid."""
    return round(v / G) * G


class Part:
    def __init__(self, ref, lib_id, value, footprint, lcsc="", pos=(0, 0), nets=None,
                 dnp=False, in_bom=True, on_board=True, mpn="", note="", fit="base"):
        self.ref, self.lib_id, self.value, self.footprint = ref, lib_id, value, footprint
        self.lcsc, self.pos, self.nets = lcsc, (g(pos[0]), g(pos[1])), nets or {}
        self.dnp, self.in_bom, self.on_board, self.mpn, self.note = dnp, in_bom, on_board, mpn, note
        self.fit = fit


R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
NC = None
FITS = ("base", "port")

PARTS = []


def P(*a, **k):
    PARTS.append(Part(*a, **k))


def R(ref, value, lcsc, pos, n1, n2, note="", fit="base"):
    P(ref, "Device:R", value, R0603, lcsc, pos, {"1": n1, "2": n2}, note=note, fit=fit)


def C(ref, value, lcsc, pos, n1, n2, fp=C0603, note="", fit="base"):
    P(ref, "Device:C", value, fp, lcsc, pos, {"1": n1, "2": n2}, note=note, fit=fit)


def SW(ref, value, pos, net):
    P(ref, "Switch:SW_Push", value, "console:SW_Tact_4.5x4.5_C2897501", "C2897501", pos,
      {"1": net, "2": "GND"}, mpn="BOOMELE 4.5x4.5x3.8 SMD tact")


def TP(ref, pos, net):
    P(ref, "Connector:TestPoint", net, "TestPoint:TestPoint_Pad_1.5x1.5mm", "", pos, {"1": net},
      in_bom=False)


# ---------------------------------------------------------------------------------------------
# 1. Power: USB-C sink, ESD, removable data links, 3.3 V regulator
# ---------------------------------------------------------------------------------------------
P("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", "console:USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge",
  "C165948", (38.1, 81.28), {
      "A4": "+5V", "A9": "+5V", "B4": "+5V", "B9": "+5V",
      "A5": "CC1", "B5": "CC2",
      "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN",
      "A8": NC, "B8": NC,
      "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND"},
  mpn="HRO TYPE-C-31-M-12")
R("R1", "5.1k", "C23186", (78.74, 106.68), "CC1", "GND", note="USB-C sink: CC1 pull-down")
R("R2", "5.1k", "C23186", (88.9, 106.68), "CC2", "GND", note="USB-C sink: CC2 pull-down")
P("U4", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "C7519",
  (111.76, 68.58), {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN", "5": "+5V", "2": "GND"})
R("R12", "0", "C21189", (139.7, 66.04), "USB_DP", "USB_DP_MCU", note="remove for power-only USB")
R("R13", "0", "C21189", (149.86, 66.04), "USB_DN", "USB_DN_MCU", note="remove for power-only USB")
P("U3", "Regulator_Linear:AMS1117-3.3", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "C6186",
  (114.3, 119.38), {"3": "+5V", "2": "+3V3", "1": "GND"})
C("C1", "10u", "C15850", (91.44, 132.08), "+5V", "GND", C0805, note="LDO input")
C("C8", "100n", "C14663", (81.28, 132.08), "+5V", "GND", note="LDO input")
C("C2", "10u", "C15850", (137.16, 132.08), "+3V3", "GND", C0805, note="LDO output, >= 10u for stability")
P("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", "", (60.96, 132.08), {"1": "+5V"}, in_bom=False, on_board=False)
P("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", "", (60.96, 147.32), {"1": "GND"}, in_bom=False, on_board=False)

# ---------------------------------------------------------------------------------------------
# 2. MCU: ESP32-S3-WROOM-1-N8R2, hand-soldered on the back
# ---------------------------------------------------------------------------------------------
P("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N8R2", "console:ESP32-S3-WROOM-1_HandSolder",
  "C2913204", (233.68, 104.14), {
      "1": "GND", "40": "GND", "41": "GND", "2": "+3V3", "3": "EN",
      "27": "BOOT",                      # IO0, strap: BOOT button only
      "39": "KEY_CC", "38": "KEY_EN",    # IO1, IO2: the key port (section 7), on pads TP9, TP10
      "15": NC,                          # IO3 strap (JTAG source), unconnected
      "4": NC, "5": NC, "6": NC, "7": NC, "12": NC, "8": NC, "11": NC, "21": NC, "24": NC,
      "17": "LCD_DC", "18": "LCD_CS", "19": "LCD_MOSI", "20": "LCD_SCK", "22": "LCD_RST",
      "23": "LCD_BL",
      "9": "I2C_SDA", "10": "I2C_SCL",
      "37": "UART_TX", "36": "UART_RX",
      "13": "USB_DN_MCU", "14": "USB_DP_MCU",
      "28": NC, "29": NC, "30": NC,      # IO35-37: octal PSRAM on R8 modules
      "35": "BTN_REJECT", "34": "BTN_NEXT", "33": "BTN_SIGN",
      "31": "KEY2_SDA", "32": "KEY2_SCL",  # IO38, IO39: the key port's own bus, I2C(1)
      "26": NC, "16": NC,                # IO45, IO46 straps, unconnected
      "25": "LED"},
  dnp=True, mpn="ESP32-S3-WROOM-1-N8R2", note="hand-soldered on the back")
C("C3", "22u", "C45783", (266.7, 63.5), "+3V3", "GND", C0805, note="at module pin 2")
C("C5", "100n", "C14663", (276.86, 63.5), "+3V3", "GND", note="at module pin 2")
R("R3", "10k", "C25804", (180.34, 76.2), "+3V3", "EN", note="EN RC delay")
C("C4", "1u", "C15849", (190.5, 76.2), "EN", "GND", note="EN RC delay")
SW("SW7", "RESET", (180.34, 58.42), "EN")
R("R4", "10k", "C25804", (180.34, 106.68), "+3V3", "BOOT", note="GPIO0 strap high: normal boot")
SW("SW6", "BOOT", (180.34, 124.46), "BOOT")

# ---------------------------------------------------------------------------------------------
# 3. Display: 8-pin 0.5 mm ZIF for the 1.14" ST7789 panel, high-side backlight switch from 5 V
# Panel: EastRising ER-TFT1.14-2. Its FPC, from panel pin 1: LEDA GND RESET RS SDA SCL VDD CS.
# Folded under the glass, panel pin 1 lands on J2 pad 8 (J2 pad 1 is at the antenna end, panel
# pin 1 at the other), so J2 pad n carries panel pin 9 - n.
# ---------------------------------------------------------------------------------------------
P("J2", "Connector_Generic_MountingPin:Conn_01x08_MountingPin", "ST7789 1.14in panel",
  "console:FPC_0.5mm_8P_C2919492", "C2919492", (383.54, 83.82), {
      "8": "BL_A", "7": "GND", "6": "LCD_RST", "5": "LCD_DC", "4": "LCD_MOSI",
      "3": "LCD_SCK", "2": "+3V3", "1": "LCD_CS", "MP": "GND"},
  mpn="HDGC 0.5K-HX-8PWB")
C("C6", "100n", "C14663", (398.78, 109.22), "+3V3", "GND", note="panel VDD")
R("R5", "10k", "C25804", (360.68, 114.3), "+3V3", "LCD_RST", note="panel held out of reset while the S3 resets")
R("R10", "100k", "C25803", (317.5, 55.88), "+5V", "BL_GATE", note="Q1 off at reset")
P("Q1", "Transistor_FET:AO3401A", "AO3401A", "Package_TO_SOT_SMD:SOT-23", "C15127", (330.2, 71.12),
  {"1": "BL_GATE", "2": "+5V", "3": "BL_D"})
R("R11", "150", "C22808", (345.44, 88.9), "BL_D", "BL_A", note="backlight (5 - 3.0 V)/150 = 13 mA; panel max 20 mA")
P("Q2", "Transistor_BJT:MMBT3904", "MMBT3904", "Package_TO_SOT_SMD:SOT-23", "C20526", (317.5, 93.98),
  {"1": "BL_B", "2": "GND", "3": "BL_GATE"})
R("R9", "1k", "C21190", (297.18, 88.9), "LCD_BL", "BL_B")
R("R14", "4.7k", "C23162", (307.34, 111.76), "BL_B", "GND", note="keeps Q2 off while GPIO21 floats or has a weak pull-up (>= ~20k)")

# ---------------------------------------------------------------------------------------------
# 4. Inputs and LED: every button to GND, the S3's internal pull-ups
# ---------------------------------------------------------------------------------------------
SW("SW1", "D0 Reject", (50.8, 185.42), "BTN_REJECT")
SW("SW2", "D1 Next", (50.8, 203.2), "BTN_NEXT")
SW("SW3", "D2 Sign", (50.8, 220.98), "BTN_SIGN")
R("R8", "1k", "C21190", (111.76, 190.5), "LED", "LED_A")
P("D1", "Device:LED", "red", "LED_SMD:LED_0603_1608Metric", "C2286", (127.0, 203.2),
  {"2": "LED_A", "1": "GND"}, mpn="KT-0603R")

# ---------------------------------------------------------------------------------------------
# 5. The key: ATECC608C at 0x60, alone on the bus
# ---------------------------------------------------------------------------------------------
P("U2", "Security:ATECC608B-MAHDA", "ATECC608C-MAHDA", "Package_DFN_QFN:DFN-8-1EP_3x2mm_P0.5mm_EP1.3x1.5mm", "C23291019",
  (215.9, 215.9), {"8": "+3V3", "4": "GND", "5": "I2C_SDA", "6": "I2C_SCL", "9": "GND",
                   "1": NC, "2": NC, "3": NC, "7": NC},
  mpn="ATECC608C-MAHDA-S", note="UDFN-8 2x3 mm, as PicoQuorum's console-s3; placed by JLCPCB (extended part)")
C("C7", "100n", "C14663", (195.58, 198.12), "+3V3", "GND", note="at ATECC VCC")
R("R6", "4.7k", "C23162", (241.3, 198.12), "+3V3", "I2C_SDA")
R("R7", "4.7k", "C23162", (251.46, 198.12), "+3V3", "I2C_SCL")

# ---------------------------------------------------------------------------------------------
# 6. Debug pads (back face) and mounting holes
# ---------------------------------------------------------------------------------------------
for i, net in enumerate(["+3V3", "GND", "EN", "UART_TX", "UART_RX", "I2C_SDA",
                         "I2C_SCL", "BOOT", "KEY_CC", "KEY_EN", "+5V", "GND",
                         "KEY2_SDA", "KEY2_SCL"]):
    TP("TP%d" % (i + 1), (309.88 + (i % 6) * 15.24, 190.5 + (i // 6) * 20.32), net)
for i in range(4):
    P("H%d" % (i + 1), "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", "",
      (317.5 + i * 15.24, 248.92), {}, in_bom=False)

# ---------------------------------------------------------------------------------------------
# 7. The key port (rev B): a USB-C plug at the top-left corner for a key-c, on a bus of its own.
# key-c's socket carries I2C, not USB: SDA on D+ (A6), SCL on D- (A7), power on VBUS, a 5.1k Rd
# on each CC. Fitted only on boards ordered with the port, but for R17: on every board it makes
# KEY_CC read "no key" rather than float. U5 is off until firmware drives KEY_EN high. Its LEDs (D4,
# and a key-c P3's on SBU) run from VKEY: lit while the key is powered. U5's FAULT is left unused.
# ---------------------------------------------------------------------------------------------
P("J3", "console:USB_C_Plug_Straddle", "USB-C plug, straddle", "console:USB_C_Plug_ShouHan_24P-GTJB_Straddle",
  "C3151751", (63.5, 330.2), {
      "A4": "VKEY", "A9": "VKEY", "B4": "VKEY", "B9": "VKEY",
      "A5": "KEY_CC_PLUG", "B5": NC,                 # one CC line: key-c's Rd is on both of its CC pins
      "A6": "KEY2_SDA", "A7": "KEY2_SCL", "B6": NC, "B7": NC,   # key-c joins A6/B6 and A7/B7 itself
      "A8": "KEY_SBU", "B8": "KEY_SBU",              # joined, so the key's LED meets one either way up
      "A2": NC, "A3": NC, "A10": NC, "A11": NC, "B2": NC, "B3": NC, "B10": NC, "B11": NC,
      "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND"},
  dnp=True, mpn="TYPE-C 24P-GTJB 040", fit="port",
  note="the key port; pads on both faces, so fitted by hand like U1. Needs the 0.8 mm board")
P("U5", "console:AP22653", "AP22653W6-7", "Package_TO_SOT_SMD:SOT-23-6", "C2158037", (190.5, 307.34),
  {"1": "+3V3", "2": "GND", "3": "KEY_EN", "4": NC, "5": "GND", "6": "VKEY"},     # FAULT unused: DESIGN.md
  mpn="AP22653W6-7", fit="port", note="the key's power: 80 mA limit (ILIM to GND), reverse blocking, output discharge")
C("C9", "100n", "C14663", (167.64, 330.2), "+3V3", "GND", note="at U5's IN", fit="port")
C("C10", "10u", "C15850", (213.36, 330.2), "VKEY", "GND", C0805, note="at U5's OUT; no bigger: U5 discharges it", fit="port")
R("R15", "100k", "C25803", (177.8, 330.2), "KEY_EN", "GND", note="U5 off until firmware drives KEY_EN", fit="port")
P("D3", "Diode:ESD5Zxx", "ESD5Z5V0", "Diode_SMD:D_SOD-523", "C502546", (228.6, 330.2),
  {"1": "VKEY", "2": "GND"}, mpn="ESD5Z5V0", fit="port", note="TVS on VKEY, at the plug")
R("R17", "47k", "C25819", (101.6, 297.18), "+3V3", "KEY_CC",
  note="on every board: a key-c's 5.1k reads 0.32 V, none reads 3.3 V")
R("R18", "1k", "C21190", (111.76, 297.18), "KEY_CC", "KEY_CC_PLUG", note="limits what a wrong plug pushes into GPIO1", fit="port")
R("R19", "2.2k", "C4190", (127.0, 297.18), "VKEY", "KEY2_SDA", note="to VKEY: a key that is off isn't fed through its bus", fit="port")
R("R20", "2.2k", "C4190", (137.16, 297.18), "VKEY", "KEY2_SCL", fit="port")
R("R21", "100", "C22775", (152.4, 297.18), "VKEY", "KEY_SBU", note="lights a key-c P3's LED (its own 470R) while the key is powered", fit="port")
R("R22", "1k", "C21190", (162.56, 297.18), "VKEY", "KEY_LED_A", fit="port")
P("D4", "Device:LED", "green", "LED_SMD:LED_0603_1608Metric", "C72043", (177.8, 297.18),
  {"2": "KEY_LED_A", "1": "GND"}, mpn="19-217/GHC-YR1S2/3T", fit="port", note="the port's LED, beside the plug: on while the key is powered")
P("U6", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "C7519",
  (111.76, 345.44), {"1": "KEY2_SDA", "6": "KEY2_SDA", "3": "KEY2_SCL", "4": "KEY2_SCL", "5": "+3V3", "2": "GND"},
  fit="port", note="ESD on the key's SDA and SCL, at the plug; its rail on 3V3, never VKEY")
P("U7", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "C7519",
  (152.4, 345.44), {"1": "KEY_CC_PLUG", "6": "KEY_CC_PLUG", "3": "KEY_SBU", "4": "KEY_SBU", "5": "+3V3", "2": "GND"},
  fit="port", note="ESD on CC and the LED line (SBU), at the plug; its rail on 3V3")

# ---------------------------------------------------------------------------------------------
# Section notes drawn on the sheet
# ---------------------------------------------------------------------------------------------
NOTES = [
    ((25.4, 30.48), "1  POWER\nUSB-C sink (5.1k on each CC), ESD on D+/D-.\n0 ohm links R12/R13: remove for power-only USB.\nAMS1117-3.3 (1 A). No battery."),
    ((165.1, 30.48), "2  MCU: ESP32-S3-WROOM-1-N8R2 (back face, by hand)\n"
                     "Profile picoquorum-key (docs/PINS.md). IO0 pulled up, BOOT only.\n"
                     "IO3, IO45, IO46 (straps) and IO35-37 unconnected. EN: 10k + 1u."),
    ((292.1, 30.48), "3  DISPLAY: ST7789 240x135, 8-pin 0.5 mm ZIF\n"
                     "Panel ER-TFT1.14-2, pins from 1: LEDA GND RESET RS SDA SCL VDD CS.\nRibbon folds under the glass: panel pin n on J2 pad 9-n.\n"
                     "Backlight from 5 V: off at reset, on when IO21 is high."),
    ((25.4, 165.1), "4  BUTTONS AND LED\nAll buttons to GND; firmware enables the S3's pull-ups. Pressed reads 0.\n"
                    "D0/D1/D2 sit level with screen rows 7/67/127."),
    ((165.1, 165.1), "5  THE KEY: ATECC608C-MAHDA at 0x60\nNothing else on the bus. Placed by JLCPCB.\n"
                     "Bus also on pads TP6/TP7 for a key on wires."),
    ((292.1, 165.1), "6  DEBUG PADS (back face) AND MOUNTING HOLES\n"
                     "TP: 3V3 GND EN TX RX SDA SCL BOOT KCC KEN 5V GND KSDA KSCL"),
    ((25.4, 266.7), "7  THE KEY PORT (rev B): a key-c on its own bus, I2C(1)\n"
                    "Fit 'port' only, but R17 (every board). Power off at reset: R15 holds U5's EN low.\n"
                    "SDA on D+ (A6), SCL on D- (A7), VKEY on VBUS, one CC line (A5), SBU (A8+B8) from VKEY.\n"
                    "ESD rails on 3V3, never VKEY. J3 hand-fitted; 0.8 mm board."),
]
