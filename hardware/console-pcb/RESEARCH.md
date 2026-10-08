# Component research and first CAD files

2026-10-07. Draft D0. **Not ready for a fabrication or assembly order.**

## What is drawn

- `controls.kicad_sch` and `controls.kicad_pro`: an editable KiCad controls subcircuit.
  It contains the encoder, four switches and seven 10k pull-ups. Named nets describe
  the Pico interface; the Pico, power supply, display and key port are not on this sheet.
- `console.kicad_sym` and `sym-lib-table`: the encoder symbol, with the manufacturer's
  terminal letters. Its physical footprint is deliberately unassigned.
- `placement-study.kicad_pcb` and `placement-study.kicad_pro`: a 120 x 100 x 1.6 mm
  placement study. It has the stock Pico W SMD footprint (which supports Pico 2 W),
  four stock switch footprints, six proposed M2.5 holes, and component envelopes.
  There are no nets or tracks. It is not the PCB counterpart of the controls sheet.
- `review/controls.svg` and `review/placement.svg`: exports from those native files.
  They are review drawings, not manufacturing artwork.

The design does not yet have a complete BOM, CPL, Gerber archive or schematic/PCB parity.
Do not feed these drafts to the existing key-board fabrication tool.

`start_design.py` bootstraps the two drawings using the existing repository's KiCad
helpers. It adds no Python dependency. Run it with KiCad's Python. It refuses to overwrite
the CAD unless `--force` is supplied. Once editing the CAD in KiCad, stop regenerating it.
The stock KiCad symbols/footprints are embedded in the native files; the installed
KiCad libraries were not changed.

## Buttons: keep all four for prototype 1

Back and Device each add one switch and one pull-up, with two more case plungers.
Their area fits. Keeping them avoids changing navigation while testing the new board.
Reject remains dedicated and one press, as required by the repository instructions.
Sign remains separate from the encoder push.

The working choice is **E-Switch TL3305AF160QG**, quantity four. The manufacturer's
TL3305 sheet lists a 4.5 x 4.5 mm SMT body, 3.8 mm actuator for the A version, 160 gf
actuation, 0.20 mm travel, and 500,000 electrical cycles at that force. The case must
limit plunger travel and prevent sideways load. These are not finished capped buttons.
Check the library land pattern against the final supplier drawing before routing.

Source: [E-Switch TL3305](https://www.e-switch.com/wp-content/uploads/2023/01/TL3305.pdf).
No stock or price claim is made here.

## Encoder: exact candidate and firmware consequence

**Bourns PEC11J-9215F-S0015**: surface mount, 30 detents, 15 pulses/revolution,
15 mm shaft-length code, flatted shaft, standard push switch. The drawing specifies
a 6 mm shaft diameter. Select the cap only after checking its bore depth and retention.

The 30:15 detent/pulse ratio implies two quadrature transitions per click. The current
`firmware/knob.py` uses four. Verify actual direction and every detent with a sample;
do not claim this part will feel right with unchanged firmware. No firmware was edited.

The sheet uses 10k pull-ups and the existing software debounce approach. Bourns also
shows a filter circuit. Decide whether to add its RC network after measuring bounce
and checking GPIO edge behaviour; do not pick capacitors merely to make a schematic
look finished. Seven grounded inputs draw about 2.31 mA through the external 10k
pull-ups at 3.3 V, excluding the Pico's internal pull-ups.

The encoder needs five signal lands plus its retention features. The drawing includes
a 2.05 mm locating hole and a 2.2 x 1.55 mm slot. Those are not mounting screw holes.
The placement study reserves a 19 x 19 mm area but has no encoder copper footprint;
all pad coordinates and top/bottom orientation need a separate check before assigning it.

One reflow pass, no aqueous wash, no hand-soldering assumption. Its push switch is rated
for 20,000 cycles; its rotation rating is 100,000 cycles. These are different ratings.

Source: [Bourns drawing, revision 06/26](https://www.bourns.com/docs/product-datasheets/pec11j.pdf),
pages 1-3 inspected. Manufacturer PDFs were downloaded to temporary storage, not added
to the repository.

## USB-C: a board-thickness constraint

**GCT USB4151-GF-C** is the current plug candidate. The manufacturer drawing B3,
2023-05-08, specifies **0.8 +/- 0.10 mm PCB thickness**. Its through-hole shell stakes
extend 1.25 mm below the mounting face. Do not put its published land pattern on our
1.6 mm board and assume assembly will work.

The proposed solution is a small **0.8 mm dock PCB**, fastened to the case close to the
connector, above the 1.6 mm main board. It adds a board and an internal connection but
keeps the main board stiff and allows replacement of the worn connector. The internal
connector, harness, support heights and cost are still open. This is a proposal, not
a frozen two-board architecture; a suitable 1.6 mm plug could remove the extra board.

Useful drawing dimensions:

| item | manufacturer value |
|---|---|
| Plug height above PCB | 11.10 mm |
| Plug mating shell | 8.25 x 2.40 mm nominal |
| Main signal pads | 24, 0.28 mm width, 0.50 mm pitch |
| Peg-hole pitch | 7.62 mm |
| Peg holes | two, 0.75 mm diameter |
| Shell end-slot pitch | 8.02 mm |
| Published mating force | 5-20 N |
| Published durability | 10,000 cycles |

These dimensions describe USB4151, not the HCTL receptacle on our key. GCT's mating
section uses its own USB4070 receptacle. Its 15.45 mm board spacing cannot be copied
to our right-angle HCTL key. Draw that specific pair in section and check a real sample.
The dock rim, connector seating depth and key-case stop depend on that result.

Source: [USB4151 product page](https://gct.co/connector/usb4151) and
[manufacturer drawing](https://gct.co/files/drawings/usb4151.pdf), pages 1-2 inspected.
The web page and drawing differ in some specification details; use a supplier-confirmed
current drawing at procurement. The draft includes no unverified substitute footprint.

### Direct-plug pin mapping to review

The selected 24-contact plug drawing exposes both A5 and B5, labelled CC1 and CC2.
The existing P2 key has separate 5.1k resistors on both receptacle contacts. With this
direct pair, both contacts should meet an Rd; flipping the key swaps the two.
That is different from the earlier cable design's single active CC conductor.
Confirm continuity physically before implementing attachment thresholds.

| plug pads | intended dock net | P2 key connection |
|---|---|---|
| A1, A12, B1, B12, shell | GND | GND |
| A4, A9, B4, B9 | protected KEY_VCC | key VCC |
| A6, B6 | protected KEY_SDA | D+, SDA |
| A7, B7 | protected KEY_SCL | D-, SCL |
| A5 | SENSE_A, independent | one 5.1k Rd |
| B5 | SENSE_B, independent | other 5.1k Rd |
| A2, A3, A8, A10, A11, B2, B3, B8, B10, B11 | unconnected | no required key function |

This maps function, not a finished electrical circuit. Neither sense input connects
straight to an ADC. Both need foreign-voltage protection, and attachment alone does
not authenticate a key or establish full mechanical insertion.

## Screen comparison remains open

| option | useful evidence | reason not frozen |
|---|---|---|
| EastRising ER-TFT028A3-4 bare panel | supplier lists 50.20 x 69.30 x 2.8 mm, plug-in FPC, ST7789 and SPI | directional viewing; complete manual could not be retrieved (HTTP 403); supply limits, FPC and backlight wiring not verified |
| Waveshare 2.8inch Capacitive Touch LCD module | published ST7789T3 module and circuit; onboard regulator, backlight transistor and level translation | extra touch hardware; exact outline and assembly interface need checking; not a proven drop-in for current driver |
| A bare IPS SPI panel | would give wide viewing angles and fewer assembled boards | no exact orderable part with verified drawing selected yet |

The Waveshare circuit was retrieved. It has a TXS0108E with one supply on external
VCC. Do not assume a 5 V-powered module accepts a direct Pico connection simply because
the display itself is 3.3 V. Check the complete module's external logic voltages and
regulator headroom. Its extra board does not automatically make the electrical design
simpler. Touch would remain unused.

Sources: [EastRising panel](https://www.buydisplay.com/2-8-inch-tft-lcd-display-capacitive-touch-screen-st7789v-spi-240x320),
[Waveshare module](https://www.waveshare.com/product/displays/lcd-oled/2.8inch-capacitive-touch-lcd.htm),
[Waveshare circuit](https://files.waveshare.com/wiki/2.8inch-Capacitive-Touch-LCD/2.8inch_Capacitive_Touch_LCD_Sch.pdf).
The 70 x 51 mm envelope is still an allowance, not a screen selection.

## Key protection: not ready to route

TPS2553 is still a power-switch candidate. TCA9517A is a bus-buffer candidate because
TI specifies 5.5 V-tolerant I2C pins and powered-off high impedance. That does not make
either part a complete foreign-power solution. Check supply relationships, buffer low
levels, ATECC wake pulses, disable behaviour and every path through pull-ups and clamps.

Sources: [TPS2553](https://www.ti.com/product/TPS2553),
[TCA9517A](https://www.ti.com/product/TCA9517A).

Before a circuit is marked ready, resolve these cases on a pin-by-pin schematic:

| case | required outcome |
|---|---|
| Console unpowered, charger attached to dock through an adapter | no console supply or GPIO back-powering |
| Console powered, foreign VBUS present | key drive disabled; power, bus and sense inputs within ratings |
| Key power off, external bus high | bus isolation; no parasitic key or MCU supply path |
| Dock VBUS shorted | hardware current limit; no thermal damage |
| Key pulled during review or hold | power/bus off and review discarded |
| Reset with key inserted | power off until stable detection and key checks complete |
| Normal key wake and reply | correct SDA-low wake pulse and response levels through the buffer |

Set the fault-voltage envelope explicitly. A 5.5 V-tolerant buffer is not protection
against a short to arbitrary USB-PD voltage. No voltage or cycle test has been run.

## Quote readiness

The controls circuit can be reviewed now. The complete console cannot yet be quoted
accurately as an assembled PCB. Missing items are the exact screen and connector,
backlight/power budget, protected key circuit, encoder footprint, dock stack/harness,
routing and assembly process. Supplier sourcing and a sample fit remain unverified.

When those are settled, request separate prices for 5, 20 and 100 units. Include the
Pico module mounting, shell-stake soldering, display insertion, case assembly, test
fixture, programming and functional testing. Identify any supplied-by-us parts. Do not
present the controls subcircuit's clean ERC as a check of the complete console.
