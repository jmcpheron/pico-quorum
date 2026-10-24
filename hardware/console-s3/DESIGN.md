# console-s3, rev A: the technical design

*Drawn 2026-10-24. Written by a script, placed, checked. Not routed, not checked in KiCad, not
ordered. The idea and the costs are in [CONCEPT.md](CONCEPT.md); this page is the board.*

One board for the console: an ESP32-S3-WROOM-1 on the back, the Feather's 1.14″ 240 × 135 panel in
a ZIF on the front, five buttons, the ATECC608C soldered on, and USB-C for power and the serial port.
64 × 22.86 mm, 2 layers, 1.6 mm, lead-free HASL.

```
  front                                                          the antenna end: no copper
  ┌──────────────────────────────────────────────────────────────┬──────┐
  │ H2  U4   [ D0 ]   ┌──── the panel's glass, on tape ────┐ [PREV] │      │
  │         │        │  U2  R12 R13                C6     │  C3 D1 │      │
  │ J1 ◄    [ D1 ]   │              J2 (ZIF)              │  C4 R9 │      │
  │ USB-C   │        │  U3  C2          R2 R4             │  R8 C7 │      │
  │ H1 R10  [ D2 ]   │  C1             Q1 Q2              │ [BACK] │      │
  │    R11           └──────────────────── ribbon folds ──┘        │      │
  └──────────────────────────────────────────────────────────────┴──────┘
  back: the module from x 38.5 to the right edge, antenna flush with it; test pads at x 20-32
```

It runs today's console image unchanged: the screen, D0, D1, D2, the key's bus and the LED are on
the Feather ESP32-S3 Reverse TFT's GPIOs, so `firmware/board.py` picks `"feather-s3"` and nothing in
`firmware/` changes (AGENTS.md rule 2). PREV and BACK are on new GPIOs that today's image never
reads; a `"console-s3"` profile that uses them is a later firmware change and a new release.

## What changed from the concept

- **The module is on the back.** The workshop solders it either way, so it needn't share the side
  JLCPCB assembles. The panel, the buttons and the module stop competing for the same 51 mm.
- **Five buttons, not three.** D0, D1 and D2 keep the Feather's pins, polarity and place (level with
  the screen's rails); PREV and BACK sit right of the panel.
- **The board is 64 mm long**, not the Feather's 50.8. The USB-C, the D column, the 31 mm glass, the
  PREV/BACK column and the 6.5 mm antenna keep-out end to end. It keeps the Feather's 22.86 mm width.
- **The backlight is switched on the high side.** The 8-pin panel brings out LEDA only, so the
  concept's low-side S8050 can't switch it ([below](#the-backlight)).
- **The regulator is an ME6211 (SOT-23-5), not an AMS1117.** A SOT-223 doesn't fit beside the USB-C
  at this width; the ME6211 fits under the glass ([power](#power)).
- **No reset button.** EN comes out to a test pad on the back. Holding D0 while plugging in starts
  the ROM bootloader, and esptool resets the S3 over its own USB.

## Pins

The module's pin numbers are Espressif's ([datasheet v1.8][wroom], Table 3-1). "Feather" is
`firmware/board.py`'s `"feather-s3"` profile; the generator reads it and stops if the two disagree.

| GPIO | module pin | net | goes to | firmware |
|---|---|---|---|---|
| 40, 42, 36, 35, 41 | 33, 35, 29, 28, 34 | LCD_DC, LCD_CS, LCD_SCK, LCD_MOSI, LCD_RST | the ZIF | Feather `DC, CS, SCK, MOSI, RST` |
| 45 | 26 | LCD_BL | R2 to Q1's base | Feather `BL`, high is on |
| 0 | 27 | BTN_D0 | SW1 to GND, R5 10k up | Feather D0: Reject; BOOT at reset |
| 1 | 39 | BTN_D1 | SW2 to 3V3, R6 10k down | Feather D1, `HIGH` |
| 2 | 38 | BTN_D2 | SW3 to 3V3, R7 10k down | Feather D2, `HIGH` |
| 5 | 5 | BTN_PREV | SW4 to GND | new: not read today |
| 6 | 6 | BTN_BACK | SW5 to GND | new: not read today |
| 3, 4 | 15, 4 | SDA, SCL | U2, R12/R13 4.7k up, TP8/TP9 | Feather `SDA, SCL` |
| 13 | 21 | LED | R9, D1 | Feather `LED` |
| 19, 20 | 13, 14 | USB_DN, USB_DP | U4, J1 | the S3's USB-Serial-JTAG |
| 43, 44 | 37, 36 | TXD0, RXD0 | TP4, TP5 | UART0, test pads only |
| — | 3 | EN | R8 10k up, C7 1 µF, TP3 | |
| — | 2; 1, 40, 41 | +3V3; GND | | |

Every other GPIO has no connection. Three of them matter:
- **GPIO7** is `board.POWER`, which the image drives high as `board.py` is imported. Here it drives
  nothing; the screen and the chip are on 3.3 V always. The generator checks it stays unconnected.
- **GPIO35–37** are free only on a quad-PSRAM module. An R8 module (octal PSRAM) takes them
  (datasheet Table 3-1, note b), and the screen's MOSI and SCK are 35 and 36. So it is
  WROOM-1-**N4R2**, or N8R2, never R8; the generator stops on an R8 part number.
- **The straps** (Table 4-1): GPIO0 is D0 with its pull-up. GPIO45 must read low at reset (VDD_SPI at
  3.3 V); R3 holds Q1's base, and so GPIO45 through R2, at ground. GPIO3 has the I2C pull-up, which
  only matters to an eFuse this board never burns. GPIO46 is left to its internal pull-down.

PREV and BACK were picked from the GPIOs that are not taken, not a strap, not USB or UART0, and not
GPIO26–37; the generator checks that too.

## The circuit

### Power

USB-C VBUS → U3 (ME6211C33, 500 mA LDO, CE tied to VIN) → +3V3. C1 10 µF at its input, C2 10 µF at
its output, C3 10 µF and C4 100 nF at the module's 3V3, C5 at the chip, C6 at the ZIF.

What it has to carry, from Espressif's datasheet unless marked:
- the S3: up to 355 mA in 802.11b bursts at 20.5 dBm (Table 6-4), about 95 mA receiving
- the backlight: about 30 mA with R1 at 10 Ω (estimated, below)
- the chip and the LED: allow 20 mA together (not measured)

That is about 405 mA at the worst moment, against the ME6211's 500 mA and Espressif's "0.5 A or
more" from the supply (Table 6-2). It meets the minimum with little margin. What heats U3 is the
average: at an assumed 120 mA it drops 1.7 V × 0.12 A ≈ 0.2 W, which a SOT-23-5 on a ground pour
carries. Measure U3's temperature on the first board; a 1 A part in the same footprint is the
answer if it runs hot.

No battery, no charger: as the concept says, a battery is a later revision.

### USB

J1 is key-c's receptacle (HC-TYPE-C-16P-01A). CC1 and CC2 each have a 5.1k Rd to ground (R10, R11),
so a USB-C charger gives 5 V. D+ and D− go through U4 (USBLC6-2SC6) to GPIO20 and GPIO19, the S3's
USB-Serial-JTAG port, which is what esptool and `tools/fw` used on the Feather. No bridge chip. U4's
rail is on VBUS, so it clamps VBUS as well. The shell is on ground.

Under MicroPython's `ESP32_GENERIC_S3` build the port shows Espressif's USB IDs, not Adafruit's.
`tools/fw` takes the port by name, so that doesn't matter to it.

### EN and the bootloader

R8 10k and C7 1 µF: Espressif's RC delay on EN (datasheet section 9: "usually R = 10 kΩ and C =
1 µF"). EN is on TP3 for a reset by hand. To reach the ROM bootloader: hold D0, plug in USB.

### The buttons

TS-1187A-B-A-B, 5.1 × 5.1 × 1.5 mm, the part console-a uses. Its top pair of pads is pad 1, its
bottom pair pad 2.
- **D0**: pad 1 on GPIO0, pad 2 on ground, R5 10k to 3.3 V. Pressed reads low.
- **D1, D2**: pad 1 on GPIO1 and GPIO2, pad 2 on 3.3 V, R6 and R7 10k to ground. Pressed reads high,
  as `board.HIGH = (1, 2)` expects. The image also turns on the S3's internal pull-downs; the
  resistors keep the level right before it does.
- **PREV, BACK**: pad 1 on GPIO5 and GPIO6, pad 2 on ground. No resistors: a profile that reads them
  turns on the internal pull-ups, as console-a's buttons do.

### The key

U2 is the ATECC608C in UDFN-8 (ATECC608C-MAHDA-S), the part key-b uses, at 0x60 on GPIO3/4 with
R12/R13 4.7k pull-ups to 3.3 V. Its exposed pad is on ground. TP6–TP9 (GND, 3V3, SDA, SCL) on the
back are the same bus, for a key-c on wires if a swappable key is ever wanted; nothing is fitted
there.

The chip arrives fresh. The ceremony runs on the board's own buttons, as it did for chip 3 on the
Feather ([FEATHER-S3.md](../wiring/FEATHER-S3.md#the-ceremony-on-the-feather)). Locking is permanent
([LOCKING.md](../../docs/LOCKING.md)), so one board is one key for life.

### The backlight

The 8-pin panel's ribbon has LEDA and no LEDK: the LED's cathode is ground inside the panel. So it
is switched on the high side:
- Q2 (AO3401A, P-MOSFET) from 3.3 V through R1 10 Ω to LEDA. R4 10k holds its gate up: off.
- Q1 (S8050) pulls Q2's gate down when GPIO45 drives its base through R2 1k. R3 10k holds the base,
  and GPIO45, low at reset.
- GPIO45 high is on, as on the Feather, and the image's PWM works the same way.

R1 sets the current against the panel's own LED: about (3.3 − 3.0) V / 10 Ω ≈ 30 mA for a white
LED at 3.0 V. Change it when the panel's LED is measured.

### Test pads

On the back, bare 1.5 mm copper: TP1 3V3, TP2 GND, TP3 EN, TP4 TX, TP5 RX; TP6–TP9 the spare bus.

## The panel

**No drawing of this panel was found.** Every number below is a parameter in `PANEL` (or
`PANEL_PINS`) in the generator, with its source. Buy one panel and measure it before the boards go
in, as the concept's step 1 says.

| | value | source |
|---|---|---|
| glass | 31 × 17 mm | one seller's listing (probots.co.in, "1.14 inch SPI IPS LCD display module ST7789 FPC") |
| ribbon | 8 pins at 0.5 mm; 54 mm with the glass, so a 23 mm tail | the same listing |
| pins | 1 LEDA, 2 GND, 3 RESET, 4 RS (DC), 5 SDA, 6 SCL, 7 VDD, 8 CS | the same listing; it numbers only pins 1 and 4 |
| active area | 24.912 × 14.864 mm, 135 rows | Waveshare's 1.14″ module |
| controller | ST7789, 135 × 240 at column 40, row 53 of its RAM | the Feather's panel, as `board.py` drives it |

How it sits:
- **The glass lies on foam tape over the ZIF**, inside silkscreen corners, its right end at x 48. The
  tape is taken as 2.0 mm thick. Everything under the glass is lower than 1.7 mm: the ZIF (1.0 mm),
  the SOT-23s (1.25 mm at most) and 0603 parts. The generator checks every part under the glass
  against a height table.
- **The ribbon leaves the glass's right end, folds under it and comes back into J2** from the right.
  J2's position comes from the tail: 23 mm, less about 5.7 mm for the fold. If the measured tail
  differs, change `PANEL["tail"]` and run the generator again.
- **The fold turns the ribbon over**, so which end of J2 pin 1 lands on depends on which way its
  contacts face. J2 has contacts on both sides, so either face works; `PANEL["reversed"]` swaps the
  pin order if the measured panel needs it.
- **Which end the ribbon leaves matters to the picture.** The image draws with the Feather's
  `MADCTL = 0x60` and offsets. Mount the panel the way the Feather holds the same panel, relative to
  its buttons, or the picture comes out rotated, and fixing that is a firmware change. Check on a
  Feather which end its ribbon leaves before ordering.
- **The rails.** D0, D1 and D2 sit level with rows 7, 67 and 127 (`board.RAIL_Y`), at 0.1101 mm a
  row: y 18.036, 11.430 and 4.824. That assumes the active area is centred on the glass;
  `PANEL["active_dy"]` moves it if it isn't, and the buttons follow.

J2 is HDGC's 0.5K-HX-8PWB: front entry, rear flip actuator, contacts top and bottom. Its footprint is
the drawing's recommended pattern for 8 contacts (pads 0.30 × 0.80 at 0.5 mm, pegs 0.40 × 0.80 with
E = 5.10, F = 5.90, 3.30 mm across). The actuator flips up at the back, so lift the glass to open it.

## Parts

LCSC numbers and tiers from JLCPCB's part pages on 2026-10-24. The stock figures there didn't read
reliably, so check stock when you upload.

| ref | part | LCSC | JLCPCB tier | who fits it |
|---|---|---|---|---|
| U1 | ESP32-S3-WROOM-1-N4R2 (4 MB flash, 2 MB quad PSRAM) | C2913203 | Extended, Standard assembly only | the workshop, on the back |
| U2 | ATECC608C-MAHDA-S, UDFN-8 | C23291019 | Extended | JLCPCB |
| U3 | ME6211C33M5G-N, 3.3 V 500 mA LDO, SOT-23-5 | C82942 | Extended | JLCPCB |
| U4 | USBLC6-2SC6, SOT-23-6 | C7519 | Extended | JLCPCB |
| Q1 | SS8050, SOT-23 | C2150 | Basic | JLCPCB |
| Q2 | AO3401A, SOT-23 | C15127 | Basic | JLCPCB |
| J1 | HC-TYPE-C-16P-01A USB-C receptacle (key-c's) | C2894897 | Extended | JLCPCB |
| J2 | HDGC 0.5K-HX-8PWB, 8-pin 0.5 mm ZIF | C2919492 | Extended | JLCPCB |
| SW1–SW5 | TS-1187A-B-A-B tact | C318884 | Basic | JLCPCB |
| R1 | 10 Ω | C22859 | Basic | JLCPCB |
| R2, R9 | 1k | C21190 | Basic | JLCPCB |
| R3–R8 | 10k | C25804 | Basic | JLCPCB |
| R10, R11 | 5.1k | C23186 | Basic | JLCPCB |
| R12, R13 | 4.7k | C23162 | Basic | JLCPCB |
| C1–C3 | 10 µF | C19702 | Basic | JLCPCB |
| C4–C6 | 100 nF | C14663 | Basic | JLCPCB |
| C7 | 1 µF | C15849 | Basic | JLCPCB |
| D1 | red LED | C2286 | Basic | JLCPCB |
| — | the 1.14″ panel | not stocked; about $2.50 | | the workshop: clips in |

The resistors, capacitors and the LED are 0603. Five Extended types go on in JLCPCB's assembly (U2,
U3, U4, J1, J2; the module isn't in the BOM): at the concept's $3.07 a feeder that is about $15
once, so the fees stay near the concept's $25.

## How the board is laid out

The board frame has its origin at the bottom-left corner looking at the front, x along the board,
y up, in mm.

- **Front, left to right:** J1 at the left edge, its mouth flush with it (the receptacle's origin
  3.675 mm in, as on key-c), with U4 above it and R10/R11 below; H1 and H2 (2.2 mm, M2) in the left
  corners. The D column at x 12.6. The glass from x 17 to 48. PREV and BACK at x 53.5, level with
  D0 and D2, with the module's decoupling, EN's RC and the LED between them. Then the keep-out.
- **Under the glass:** U2 with C5 and R12/R13 at the top left, U3 with C1/C2 at the bottom left, J2
  in the middle at x 32.7, the backlight's Q1, Q2 and R1–R4 at the bottom right, C6 by J2, and
  R5–R7 down the glass's left edge.
- **Back:** U1, its centre at (51.25, 11.43), turned so the antenna end is flush with the right edge
  and pins 1–14 run along the bottom edge. Pin 1 is at (56.51, 2.68), pin 14 at (40.0, 2.68), the
  bottom row at x 38.75 and pins 27–40 along the top edge. The test pads, the mark, the name and
  the Source Location are at x 9–37.
- **The antenna keep-out** is x 57.5 to 64, the whole height, on both layers: a rule area that
  allows no copper, track, via or pour. That is the module's 18 × 6 mm antenna area (Figure 11-1)
  and 0.5 mm, with the board edge free beyond it, as the concept asks. Nothing on the front is
  there either. The holes are at the USB end only: a screw at the far end would be metal next to
  the antenna.
- **The module's exposed pad** is one 3.7 mm pad, bare, with no paste. Espressif says soldering it
  "is not a must" and helps only with heat (section 9). It can't be reached with an iron under a
  module on the back; hot air can do it if a board runs warm.
- **J1's locating holes** are 0.165 mm from its VBUS pads, closer than JLCPCB's 0.25 mm hole rule.
  That is the maker's pattern as key-c's board has it; the check lets a part's own holes be.
- **Ground** is a pour on both layers up to the keep-out, written unfilled. Tracks are to be 0.25 mm,
  vias 0.6/0.3, clearance 0.2: JLCPCB's 2-layer limits with margin, set in the project's netclass.
- **Silkscreen:** D0, D2, PREV and BACK by their buttons (D1 sits between D0 and D2 and needs none:
  the screen's rail names every button); the glass's corners. On the back: the mark, the name,
  `github.com/jmcpheron/pico-quorum` and the licence (CERN-OHL-W 4.1), the test pads' names.
  References are on the fab layer only.

## The firmware

Nothing changes for rev A. On this board today's console image:
- picks `"feather-s3"`, because it picks that on any ESP32-S3
- drives the screen, reads D0/D1/D2 and the chip at 0x60, and blinks GPIO13, all on the same pins
- drives GPIO7 high, which reaches nothing
- finds no battery gauge at 0x36; `NOT_KEYS` already keeps that address off the key list, and with
  nothing there the scan finds only the chip

A later `"console-s3"` profile for five buttons would add PREV (GPIO5) and BACK (GPIO6) to `KEYS`,
pulled up, and say how they map onto the console's moves; the three-button rail would then be a
choice, not a necessity. It needs a way to tell this board from the Feather, since both are an
ESP32-S3: a `secrets.BOARD` setting, or a strap read at boot. That is a firmware change and so a
new release fingerprint (AGENTS.md rule 2), and it is not part of this board.

Nothing on the board signs anything new: the same `quorum.sign_it`, the same hash, the same held
Sign (AGENTS.md rule 1).

## Files

| path | what |
|---|---|
| `gen_console_s3.py` | writes everything below from Python, no KiCad needed, then checks it |
| `lib/pqs3.kicad_sym`, `lib/pqs3.pretty/` | the symbols and footprints, all written by the script. The UDFN, SOT-23s, 0603s, USB-C and switch are KiCad's own or key-c's and console-a's, as their boards hold them; the module's and the ZIF's are from their makers' drawings |
| `lib/picoquorum.pretty/PicoQuorum_Mark.kicad_mod` | the mark, a copy of the key library's |
| `console-s3/` | the KiCad 9 project: open `console-s3.kicad_pro`. Placed, not routed |

`gen_console_s3.py` reuses console-pocket's footprint and board-text helpers and the key boards'
schematic helpers, as the wing does. Once the board is edited in KiCad, the KiCad files are the
source of truth: don't run the generator again, or the edits are lost (`tools/keypcb
gen-console-s3` reruns it).

## Checking it

Here, with no KiCad: `python3 hardware/console-s3/gen_console_s3.py` writes the project and checks
it; `--check` checks what is there and writes nothing. Both report clean. What they check:
- **The firmware:** the pin table against `firmware/board.py`'s `"feather-s3"` profile (the screen,
  the three buttons and their polarity, the bus, the LED), GPIO7 unconnected, PREV and BACK on safe
  free pins, and no R8 module. It stops before writing anything if these disagree.
- **The schematic, read back:** every symbol pin's net, worked out from its wires, labels, power
  symbols and no-connect flags, is the net in the script's one table (gen_wing.py's check).
- **The board, read back:**
  - 0.2 mm between pads of different nets, 0.25 mm from pads to plain holes
  - 0.3 mm from copper to the edge, corners included
  - no pad, and no courtyard but the module's, in the antenna keep-out
  - every pad on the net the schematic gives it
  - no two courtyards on the same side overlap
  - everything in the BOM on the front, the module on the back
  - nothing under the glass taller than the tape allows
  - silkscreen text off the pads and on the board
  - D0, D1 and D2 level with their rails, within 0.05 mm
  - module pins 1, 14, 15, 26, 27 and 40 where Espressif's drawing puts them, the antenna end on the
    board's edge

It also counts what's left to route: 99 connections on 29 nets.

The checks were tried against broken boards (a scratch script, not in the repository), and each
caught its fault: D1 0.3 mm off its rail, the LED in the keep-out, BACK on GPIO7, an N8R8 module, a
resistor on Q1's pad, the chip on the back, D1 wired to ground, and 1.0 mm tape under the
SOT-23s. These stand in for ERC and DRC; they are not ERC or DRC.

On a machine with KiCad, once it is routed: `tools/keypcb fill console-s3`, `check`, `render`, `fab`,
as for console-pocket.

## Open

- [ ] **Measure a panel**: glass, the tail's length, the pin order, which face its contacts are on
      after the fold, where the active area sits on the glass, the LED's forward voltage. Then set
      `PANEL` and `PANEL_PINS` and run the generator again.
- [ ] **Look at a Feather**: which end its panel's ribbon leaves, relative to its buttons. Mount
      this one the same way.
- [ ] **Measure a module** against Figure 11-1, and read the exposed pad's position off a real one:
      the drawing's 7.5 and 10.29 mm are read here as distances to the block's near sides.
- [ ] **Route it**: a router in the style of console-pocket's or the wing's, or by hand in KiCad. USB
      D+/D− as a pair from U4 to module pins 13 and 14; the module's 3V3 short and wide to C3/C4;
      ground vias next to every ground pad.
- [ ] KiCad: fill, ERC, DRC with parity, the 3D view from both sides, then the fab files.
- [ ] U3's temperature on the first board; a 1 A regulator in the same footprint if it runs hot.
- [ ] A case: the two holes at the USB end, the glass about 3.6 mm proud of the board (tape and
      glass) against 1.5 mm buttons, and a guard over Sign (the kickoff's open decisions).
- [ ] The `"console-s3"` firmware profile for PREV and BACK, and how the console tells this board
      from the Feather.
- [ ] Wi-Fi with the module on the back and the antenna at the edge, measured on the first board.

[wroom]: https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
