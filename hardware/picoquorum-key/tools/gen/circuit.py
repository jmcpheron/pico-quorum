"""picoquorum-key rev A: every part, its fields, its schematic position and the net on each pin.

This file is the single source for the generated schematic (gen_sch.py). The board generator
(gen_pcb.py) reads the schematic's own netlist, not this file, so the schematic stays the truth.

Pin profile: docs/PINS.md. Circuits: docs/DESIGN.md.
"""

G = 2.54


def g(v):
    """Snap to the 2.54 mm schematic grid."""
    return round(v / G) * G


class Part:
    def __init__(self, ref, lib_id, value, footprint, lcsc="", pos=(0, 0), nets=None,
                 dnp=False, in_bom=True, on_board=True, mpn="", note=""):
        self.ref, self.lib_id, self.value, self.footprint = ref, lib_id, value, footprint
        self.lcsc, self.pos, self.nets = lcsc, (g(pos[0]), g(pos[1])), nets or {}
        self.dnp, self.in_bom, self.on_board, self.mpn, self.note = dnp, in_bom, on_board, mpn, note


R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
NC = None

PARTS = []


def P(*a, **k):
    PARTS.append(Part(*a, **k))


def R(ref, value, lcsc, pos, n1, n2, note="", dnp=False):
    P(ref, "Device:R", value, R0603, lcsc, pos, {"1": n1, "2": n2}, note=note, dnp=dnp)


def C(ref, value, lcsc, pos, n1, n2, fp=C0603, note="", dnp=False):
    P(ref, "Device:C", value, fp, lcsc, pos, {"1": n1, "2": n2}, note=note, dnp=dnp)


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
      "39": "IO1", "38": "IO2",          # to pads; the key port's detect and power enable (section 7)
      "15": NC,                          # IO3 strap (JTAG source), unconnected
      "4": NC, "5": NC, "6": NC, "7": NC, "12": NC, "8": NC, "11": NC, "21": NC, "24": NC,
      "17": "LCD_DC", "18": "LCD_CS", "19": "LCD_MOSI", "20": "LCD_SCK", "22": "LCD_RST",
      "23": "LCD_BL",
      "9": "I2C_SDA", "10": "I2C_SCL",
      "37": "UART_TX", "36": "UART_RX",
      "13": "USB_DN_MCU", "14": "USB_DP_MCU",
      "28": NC, "29": NC, "30": NC,      # IO35-37: octal PSRAM on R8 modules
      "35": "BTN_REJECT", "34": "BTN_NEXT", "33": "BTN_SIGN",
      "32": "KEY_SDA", "31": "KEY_SCL",  # IO39, IO38: the key port's own bus (section 7); PREV/BACK were dropped
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
                         "I2C_SCL", "BOOT", "IO1", "IO2", "+5V", "GND"]):
    TP("TP%d" % (i + 1), (309.88 + (i % 6) * 15.24, 190.5 + (i // 6) * 20.32), net)
for i in range(4):
    P("H%d" % (i + 1), "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", "",
      (317.5 + i * 15.24, 248.92), {}, in_bom=False)

# ---------------------------------------------------------------------------------------------
# 7. The key port: a USB-C plug at the left edge, on the back, for key-c. Optional: every part is
# DNP, off JLCPCB's BOM and CPL, and fitted by hand. Unfitted, the board is rev A as it was: U2
# keeps its bus, and IO1, IO2, IO38 and IO39 lead only to empty pads. Fitted, the plugged key is on
# a bus of its own (IO39/IO38), since it and U2 both answer at 0x60.
# ---------------------------------------------------------------------------------------------
P("J3", "console:USB_C_Plug_12P", "USB-C plug", "console:USB_C_Plug_HRO_TYPE-C-31-G-03_Edge", "C840338",
  (40.64, 264.16), {
      "A1": "GND", "A12": "GND", "B12": "GND", "SH": "GND",
      "A4": "VKEY", "B9": "VKEY", "A5": "KEY_CC", "A6": "KEY_SDA", "A7": "KEY_SCL",
      "A2": NC, "A3": NC, "B10": NC, "B11": NC},
  dnp=True, mpn="HRO TYPE-C-31-G-03", note="key-c plugs on: SDA on D+, SCL on D-, power on VBUS, a 5.1k Rd on each CC")
P("U5", "console:AP22653", "AP22653W6-7", "Package_TO_SOT_SMD:SOT-23-6", "C2158037", (111.76, 259.08),
  {"1": "+3V3", "2": "GND", "3": "IO2", "4": NC, "5": "GND", "6": "VKEY"},
  dnp=True, mpn="AP22653W6-7", note="key power: 80 mA limit (ILIM to GND), reverse blocking, output discharge")
R("R19", "10k", "C25804", (88.9, 271.78), "+3V3", "IO2", note="U5 on unless IO2 drives low", dnp=True)
C("C9", "100n", "C14663", (139.7, 271.78), "+3V3", "GND", note="U5 input", dnp=True)
C("C10", "10u", "C15850", (149.86, 271.78), "VKEY", "GND", C0805, note="U5 output; no bigger, U5 discharges it", dnp=True)
P("D2", "Diode:ESD5Zxx", "ESD5Z5V0", "Diode_SMD:D_SOD-523", "C502546", (170.18, 271.78),
  {"1": "VKEY", "2": "GND"}, dnp=True, mpn="ESD5Z5V0", note="TVS on VKEY: a 5 V source on the plug stops at U5")
P("U6", "Power_Protection:SRV05-4", "SRV05-4", "Package_TO_SOT_SMD:SOT-23-6", "C13612", (200.66, 264.16),
  {"6": "KEY_SDA", "4": "KEY_SCL", "1": "KEY_CC", "3": NC, "5": "+3V3", "2": "GND"},   # its four lines are alike: SDA, SCL on the plug's side
  dnp=True, mpn="SRV05-4.TCT", note="ESD on the plug's SDA, SCL and CC; rail on 3V3, never VKEY")
R("R15", "2.2k", "C4190", (233.68, 254.0), "VKEY", "KEY_SDA", note="pull-up to VKEY: a key that is off isn't fed through SDA", dnp=True)
R("R16", "2.2k", "C4190", (243.84, 254.0), "VKEY", "KEY_SCL", note="pull-up to VKEY", dnp=True)
R("R17", "22k", "C31850", (259.08, 254.0), "+3V3", "KEY_CC", note="CC pull-up: 0.62 V with a key's 5.1k Rd (a logic low), 3.3 V empty", dnp=True)
R("R18", "1k", "C21190", (269.24, 254.0), "KEY_CC", "IO1", note="CC into IO1 (ADC1_CH0), limits what the plug can push in", dnp=True)

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
    ((292.1, 165.1), "6  DEBUG PADS (back face) AND MOUNTING HOLES\nTP: 3V3 GND EN TX RX SDA SCL BOOT IO1 IO2 5V GND"),
    ((25.4, 233.68), "7  KEY PORT (optional: back face, every part DNP, fitted by hand)\n"
                     "USB-C plug for key-c at the left edge. Its own bus, IO39/IO38: U2 is at 0x60 too.\n"
                     "IO1 reads CC: low = key in, high = none. IO2 high (R19) = key powered."),
]
