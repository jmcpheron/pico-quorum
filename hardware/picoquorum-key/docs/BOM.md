# Bill of materials, rev B

*Checked 2026-10-23 against JLCPCB and LCSC pages and distributor searches. Tiers and stock move;
re-check every line at upload and update the date here. "Basic" and "Preferred extended" cost no
feeder fee under Economic assembly; "Extended" costs a per-line feeder fee ($3 by JLCPCB's FAQ;
reported lower since 2025-12).*

Rev B is rev A's parts plus the key port. Every board is the same copper; the port's parts are
assembled only on the boards ordered with `bom-port.csv` (below). LCSC numbers of the new parts were
read back from LCSC's part data on 2026-10-25; their JLCPCB tiers were not, and are marked.

## Placed by JLCPCB (front face), every board

This is what `tools/export.sh` writes into the JLCPCB `bom.csv`: rev A's 20 lines and 37
placements, plus R17.

| ref | qty | part | package | LCSC | tier | note |
|---|---|---|---|---|---|---|
| J1 | 1 | USB-C receptacle, HRO TYPE-C-31-M-12, 16-pin | SMD + THT shell pegs | C165948 | extended (page says Extended, 2026-10-23) | confirm at upload |
| J2 | 1 | FPC/FFC connector 0.5 mm 8-pin, front insert, back flip, double-sided contacts, HDGC 0.5K-HX-8PWB | SMD, 1.0 mm tall | C2919492 | extended | pin count follows the panel; swap if the panel has 12 pins |
| U3 | 1 | AMS1117-3.3, 1 A LDO | SOT-223 | C6186 | basic (not re-checked: LCSC rate-limited) | alt: XC6220B331MR-G (SOT-25, 1 A) |
| U4 | 1 | USBLC6-2SC6 ESD array | SOT-23-6 | C7519 | **extended** (2026-10-23) | |
| U2 | 1 | ATECC608C-MAHDA-S, the key chip | UDFN-8 2 x 3 mm | C23291019 | extended | console-s3's part. Stock was thin on 2026-10-24 (62 at JLCPCB, 0 at LCSC): check, or pre-order it; check pin 1 in the placement preview |
| Q1 | 1 | AO3401A P-MOSFET | SOT-23 | C15127 | basic (not re-checked) | backlight high-side switch |
| Q2 | 1 | MMBT3904 NPN | SOT-23 | C20526 | basic | level shift for Q1 |
| SW1–SW3, SW6, SW7 | 5 | tactile switch 4.5 × 4.5 × 3.8 mm, BOOMELE | SMD-4 | C2897501 | extended | D0 D1 D2 BOOT RESET (SW4, SW5 retired with PREV and BACK); alt C2923720 (5 mm tall, round plunger) |
| D1 | 1 | LED 0603, red | 0603 | C2286 | basic | |
| R1, R2 | 2 | 5.1 kΩ 1% | 0603 | C23186 | basic | USB-C CC pull-downs |
| R3, R4, R5 | 3 | 10 kΩ 1% | 0603 | C25804 | basic | EN, BOOT, panel RST pull-ups |
| R6, R7, R14 | 3 | 4.7 kΩ 1% | 0603 | C23162 | basic | I2C pull-ups; Q2 base pull-down |
| R8, R9 | 2 | 1 kΩ 1% | 0603 | C21190 | basic | LED series, Q2 base |
| R10 | 1 | 100 kΩ 1% | 0603 | C25803 | basic | Q1 gate pull-up |
| R17 | 1 | 47 kΩ 1% | 0603 | C25819 | basic (expected; confirm at upload) | the key port's CC pull-up: on every board, so GPIO1 reads "no key" without the port |
| R11 | 1 | 150 Ω 1% | 0603 | C22808 | basic (expected; confirm at upload) | backlight series, ≈ 13 mA (panel max 20 mA) |
| R12, R13 | 2 | 0 Ω | 0603 | C21189 | basic | USB D+/D− links |
| C1, C2 | 2 | 10 µF X5R | 0805 | C15850 | basic | LDO in/out |
| C3 | 1 | 22 µF 25 V X5R | 0805 | C45783 | basic | module 3V3 |
| C4 | 1 | 1 µF X5R | 0603 | C15849 | basic (not re-checked) | EN delay |
| C5–C8 | 4 | 100 nF 50 V X7R | 0603 | C14663 | basic | module, panel VDD, ATECC, LDO input |
| TP1–TP14 | 14 | test pad 1.5 × 1.5 mm, back face | pad | – | – | no part |
| H1–H4 | 4 | M2 mounting hole | 2.2 mm | – | – | no part |

Extended lines: J1, J2, the five switches (one line), U2 and U4. Five feeder fees. Everything else basic. There
is no polyfuse: JLCPCB has no Basic-tier PPTC, and a USB port limits current itself.

## Placed by JLCPCB, the key port's boards only

`bom-port.csv` and `cpl-port.csv` are `bom.csv` and `cpl.csv` plus these. The Gerbers are the same.

| ref | qty | part | package | LCSC | tier | note |
|---|---|---|---|---|---|---|
| U5 | 1 | AP22653W6-7, current-limited power switch, 80 mA with ILIM to GND, reverse blocking, output discharge | SOT-23-6 | C2158037 | extended (wing-a's note) | the key's power, VKEY |
| U6, U7 | 2 | USBLC6-2SC6 ESD array | SOT-23-6 | C7519 | extended | the same line as U4: no extra feeder fee |
| D3 | 1 | ESD5Z5V0 TVS | SOD-523 | C502546 | not checked | VKEY, at the plug |
| D4 | 1 | LED 0603, green, KT-0603G | 0603 | C12624 | not checked | the port's LED, on while the key is powered (the plan's green C72043 was out of stock on 2026-10-26) |
| R15 | 1 | 100 kΩ 1% | 0603 | C25803 | basic | KEY_EN pull-down: the key off at reset |
| R18 | 1 | 1 kΩ 1% | 0603 | C21190 | basic | CC series |
| R22 | 1 | 470 Ω 1% | 0603 | C23179 | basic (expected; confirm) | D4's resistor |
| R19, R20 | 2 | 2.2 kΩ 1% | 0603 | C4190 | basic (expected; confirm) | the port bus's pull-ups to VKEY |
| R21 | 1 | 100 Ω 1% | 0603 | C22775 | basic (expected; confirm) | VKEY to a key-c P3's LED on SBU |
| C9 | 1 | 100 nF 50 V X7R | 0603 | C14663 | basic | at U5's input |
| C10 | 1 | 10 µF X5R | 0805 | C15850 | basic | at U5's output; no bigger, U5 discharges it |

New extended lines: U5, and D3 if it isn't basic. One or two more feeder fees on these boards only.

## Fitted by hand

| ref | qty per board | part | source | price (2026-10-23) | note |
|---|---|---|---|---|---|
| J3 | 1, port boards only | SHOU HAN TYPE-C 24P-GTJB 040, a USB-C plug that straddles a 0.8 mm board's edge | LCSC C3151751, about 44,000 in stock on 2026-10-23 (wing-b's note) | ≈ $0.14 | its pads are on both faces, so front-only assembly can't fit it: solder by hand, front row first, or ask JLCPCB. Check A1's side against a real plug first (DESIGN.md) |
| U1 | 1 | ESP32-S3-WROOM-1-N8R2 | LCSC C2913204 (3.8k in stock), order with the JLCPCB job or separately | ≈ $5.12 | back face; 41 castellations, pad 41 left unsoldered. Buy 7 |
| panel | 1 | EastRising **ER-TFT1.14-2**: 1.14″ IPS 135 × 240, ST7789V, 8-pin 0.5 mm FPC, no touch | BuyDisplay (buydisplay.com); also sold as MikroElektronika MIKROE-6077 (RS 029-6118). Datasheet: download.mikroe.com/documents/datasheets/ER-TFT1.14-2_datasheet.pdf | ≈ $3–6 | the layout follows its drawing (DESIGN.md, "The panel and its ribbon"). Buy 7 |
| panel (alt) | – | Walfront "ST7789V 1.14 Inch … Inline Type 2Pcs": the same generic panel, ribbon marked **NFP114H-03AF**, 8-pin 0.5 mm plug-in, pin 1 LEDA, pin 4 RS, 31 × 17 × 1.6 mm, 54 mm long with the ribbon | Amazon ASIN B0BNLLZQNK (checked 2026-10-23 from the listing photos; no datasheet) | ≈ $7.50 each (2-pack) | fits J2 with no change. Fast to get, so useful for the 1:1 fit check before ordering. On arrival check the "1"/"8" marks on the ribbon |
| tape | – | 1.5 mm double-sided foam tape | any | | panel to board, at the glass ends; clears the 1.0 mm ZIF under the glass |

## Cost, five boards (estimate, confirm at quote)

| item | est. |
|---|---|
| PCB 50 × 53, 2 layers, 0.8 mm, 5 pcs | $4–8 (0.8 mm may cost a little more; confirm at quote) |
| Economic assembly setup + stencil | $9.50 |
| feeder fees, 5 extended lines | $7.50–15 |
| placed parts, 5 boards (key chips included) | $22–28 |
| modules ×7 | $36 |
| panels ×7 | $15–35 |
| shipping (JLCPCB + one distributor) | $25–40 |
| **total** | **≈ $125–175** |

## How to re-check a line

JLCPCB part page: `https://jlcpcb.com/partdetail/<C-number>` shows the tier badge and stock. LCSC:
`https://www.lcsc.com/product-detail/<C-number>.html`. `tools/check_parts.py` is a placeholder for
scripting this; JLCPCB's pages are JavaScript-rendered, so a browser is the reliable way.
