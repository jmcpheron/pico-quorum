# The pocket console PCB, console-pocket

*Rev A, drawn 2026-10-07. Not yet ordered.*

> **Don't order the board in this folder as it is.** KiCad 10.0.6's DRC, run on 2026-10-23, finds
> 138 violations, 32 of them shorts. `gen_console.py`'s `rotate()` turned parts the other way from
> KiCad, so every part at 90° or 270° has its pads swapped against its tracks. The self-check used
> the same `rotate()`, so it couldn't see it. `rotate()` is fixed now. Before this board is
> regenerated, swap its 90s and 270s (as `feather-wing/gen_wing.py`'s `ROT` was) so each pad
> lands where the placement expects it; then rerun it and `tools/keypcb check`.

One board for the console, the small one: a Pico 2 W soldered on the back as a module, a bare
1.54″ ST7789 240×240 panel on the front, seven buttons, and pads for the key's wires. It runs the
same console image as the dev console, on the same GPIOs, so the firmware does not change.

It is the third one-board console in this repository, drawn in parallel with the other two:
[`console-pcb/console-a`](../console-pcb/README.md) is Build 1 on one board (2.8″ screen, knob,
USB-C plug) and [`console-a/console-a`](../console-a/README.md) is the Waveshare build with a 1.3″
panel and nine buttons, Pico on the front. This one is the pocket size: the Pico goes on the back.

| front | back |
|---|---|
| the panel at the top, the FPC pads under it, the D-pad left and Select, Back, Reject right | the Pico along the bottom edge, USB at the right, antenna at the left; the key pads' names |

51 × 85 mm, 2 layers, 1.6 mm, lead-free HASL. The width is the Pico's length: its micro-USB is
flush with the right edge and its antenna end with the left, as the datasheet asks.

## What is on it

| ref | part | LCSC | note |
|---|---|---|---|
| U1 | Raspberry Pi Pico 2 W, soldered as an SMD module | C42394205, not in the BOM | on the back; you solder it (40 castellations) |
| LCD1 | 1.54″ ST7789 240×240 IPS, 12-pin 0.7 mm FPC, soldering type | not at JLCPCB; ~$2 ("1.54 inch 12PIN 0.7mm soldered", MKTechnic, AliExpress) | pads only; you solder the FPC |
| SW1–SW7 | XUNPU TS-1097A-05026, 6×6×5 mm tact, 2.6 N | C720496, extended | Up, Down, Left, Right, Select (A), Back (B), Reject (Y) |
| Q1 | S8050, SOT-23 | C2150 | backlight low-side switch, as the Waveshare board does it |
| R1 | 10 Ω 0603 | C22859 | LEDK series |
| R2 | 1 kΩ 0603 | C21190 | GP13 to Q1's base |
| R3 | 10 kΩ 0603 | C25804 | base pulldown: backlight off while the Pico boots |
| C1 | 100 nF 0603 | C14663 | panel VDD |
| R4, R5 | 2.2 kΩ 0603, **not fitted** | C4190 | SDA and SCL pull-ups to key power, for later |
| J2 | 8 pads, 2.54 mm, 1.0 mm holes | copper | the key's wires (below) |
| J3 | 2 pads | copper | VSYS, GND: a battery later ([SOLDERING.md](../wiring/SOLDERING.md)) |
| J4 | 3 pads | copper | GP19 (X), GP3 (the stick's press), GND: spare |
| H1–H4 | 3.2 mm holes | | M3, at (3.5, 40.5), (47.5, 40.5), (3.5, 81.5), (47.5, 81.5) from the bottom-left corner |

The LCSC numbers were looked up on 2026-10-07. Check stock when you upload.

## Pins

Every GPIO is the one `firmware/board.py` uses for the Waveshare build, and the key pins are
Build 1's ([BUILD1.md](../wiring/BUILD1.md)).

| GPIO | Pico pin | goes to |
|---|---|---|
| GP2, GP18, GP16, GP20 | 4, 24, 21, 26 | Up, Down, Left, Right |
| GP15 (A) | 20 | Select: opens, and held to sign |
| GP17 (B) | 22 | Back; held at power-up: maintenance |
| GP21 (Y) | 27 | Reject; held at power-up: Wi-Fi setup |
| GP19 (X), GP3 (press) | 25, 5 | J4 pads only |
| GP8 DC, GP9 CS, GP10 SCK, GP11 MOSI, GP12 RST, GP13 BL | 11, 12, 14, 15, 16, 17 | the panel |
| GP4 SDA, GP5 SCL, GP6, GP7, GP26, GP27 | 6, 7, 9, 10, 31, 32 | J2 pads 3 to 8 |
| 3V3 (OUT), VSYS | 36, 39 | the panel, J2 pad 2; J3 pad 1 |

J2, top to bottom (pad 1 is square): GND, 3V3, SDA, SCL, KEY_PWR (GP6), KEY_DET (GP7), KEY_RST
(GP26), KEY_ID (GP27). The names are on the back silkscreen beside the pads, where the wires go.

**The key is wired straight to the GPIOs here.** That is the bench setup
[PROPOSALS.md](../key-pcb/PROPOSALS.md#the-console-end-of-key-c) allows for one key on the
bench: GP6 powers the key directly. The load switch, the CC sensing and the ESD array come on a
later revision or a small adapter. R4 and R5 are the pull-up spots for then.

### The panel

12 pins at 0.7 mm, the Waveshare Pico-LCD-1.3's order, soldered flat to the pads just below the
glass: 1 GND, 2 LEDK, 3 LEDA (3V3), 4 VDD (3V3), 5 GND, 6 GND, 7 DC, 8 CS, 9 SCL, 10 SDA,
11 RESET, 12 GND. Pin 1 is at the dot, nearest the board's left edge. The backlight: LEDA on 3V3,
LEDK through R1 to Q1, GP13 drives the base through R2, R3 holds it off at boot.

**No public drawing of this panel was found.** `PANEL` in `gen_console.py` holds the pad size
(0.4 × 2.5 mm), the pitch, the glass size (31.52 × 33.72 mm), its distance above the pad row
(3.8 mm) and which end pin 1 is. Measure a panel against them before ordering boards. The glass
sits on the board above the pads, held with double-sided tape; the silkscreen corners show where.

The firmware's Waveshare init sequence should drive this panel as is (same controller, same
240×240). If the picture is mirrored or inverted, `board.py` gets a `"console-pocket"` entry.

### The buttons

Active low to GND, the Pico's internal pull-ups, as `lcd.py` reads them. Each switch is wired on
a **diagonal**: the GPIO on the top-left pad, GND on the bottom-right, the other two pads copper
only. A four-leg tact switch joins one pair of legs inside, and makers differ on which; a
diagonal works either way, so a wrong guess can't short a GPIO to ground.

Positions, from the bottom-left corner: Up (14, 31), Left (5.5, 22.5), Right (22.5, 22.5),
Down (14, 14); Select (42, 31), Back (42, 22.5), Reject (45, 14) with a square ring around it.
Left, Right and Back sit at y 22.5 so their pads clear the antenna keep-out below and leave the
strip above the Pico's top pad row to the vias.

## How the board is laid out

- **The Pico** lies along the bottom edge on the back, module frame x 0..51, y 1.5..22.5, USB
  at the right. Its castellations are the datasheet's SMT footprint: pads 3.2 × 1.6 mm, centres
  0.81 mm inside each long edge, pin 1 at the USB end of the row nearest the bottom edge. The
  three SWD pads and BOOTSEL are pads 41 to 44, unconnected; the test points and the USB shell
  pads are plain copper.
- **The antenna keep-out**, 14 × 9 mm at the module's left end (x 0..9, y 5..19), is a rule area
  on both layers: no copper pour, no track, no via.
- **Routing.** The back is vertical-only above the Pico's bottom corridor: every one of the
  Pico's nets climbs straight out of its pad, a bottom-row net through the gap between two
  top-row pads, and changes layer where it turns. The front carries the sideways runs. Tracks
  are 0.25 mm, vias 0.6/0.3 mm, clearance 0.2 mm, JLCPCB's 2-layer limits with margin.
- **Ground** is a pour on both layers, stitched with vias, with a via next to every ground pad
  on the front. The FPC's ground pins connect solid (a 0.4 mm pad starves a thermal relief).
- **Silkscreen.** The buttons' names on the front; the mark, the Source Location
  (`github.com/jmcpheron/pico-quorum`, CERN-OHL-W 4.1) and the key pads' names on the back.

## Files

| path | what |
|---|---|
| `gen_console.py` | writes everything below from Python, no KiCad needed; its self-check stands in for DRC here |
| `lib/picoquorum-pocket.kicad_sym`, `lib/picoquorum-pocket.pretty/` | the symbols and footprints, all written by the script (no stock library is read) |
| `lib/picoquorum.pretty/PicoQuorum_Mark.kicad_mod` | the mark, a copy of the key library's |
| `console-pocket/` | the KiCad 9 project: open `console-pocket.kicad_pro` |
| `console-pocket/fab/` | what you upload, written on a machine with KiCad by `tools/keypcb fab console-pocket` |

Once a board is edited in KiCad, the KiCad files are the source of truth: don't run the
generator again, or the edits are lost (`tools/keypcb gen-console-pocket` reruns it).

## Checking it

Here, with no KiCad, `python3 hardware/console-pocket/gen_console.py` writes the project and checks
the board it wrote: every pad of a net connected, 0.2 mm between copper of different nets, 0.3 mm
to the edge, nothing in the antenna keep-out, no via in a pad, the board's nets equal to the
schematic's, and the Pico's pins 1, 20, 21 and 40 where the datasheet puts them. It reports
clean. That is a stand-in for DRC, not DRC.

On a machine with KiCad 9 or 10:

1. `tools/keypcb fill console-pocket`: fills the copper pours and saves the board. The generator
   writes the zones unfilled, and `kicad-cli` doesn't fill them.
2. `tools/keypcb check console-pocket`: ERC, then DRC with schematic parity. Expect 0 errors, 0
   violations, 0 unconnected, parity clean. The likely first-run complaints are
   `lib_footprint_mismatch` on U1 if KiCad flips a footprint differently from the script, and a
   silkscreen text too near a pad; fix those in the GUI and note it here.
3. Open the project and look at the 3D view from the back: the Pico's USB at the right edge,
   pin 1 at the bottom-right corner of its footprint, the antenna end at the left edge.
4. `tools/keypcb fab console-pocket` writes `fab/console-pocket-gerbers.zip`, `bom.csv` and `cpl.csv`;
   `tools/keypcb render console-pocket` draws both sides.

## Ordering

1. **Panels and Picos first.** Buy a 1.54″ panel and measure its FPC against `PANEL` before the
   boards go in. Pico 2 W without headers.
2. **Upload** `fab/console-pocket-gerbers.zip` at https://jlcpcb.com. It should read 2 layers,
   51 × 85 mm.
3. **Board:** 1.6 mm, LeadFree HASL, any colour, "Remove Mark" if offered.
4. **PCB Assembly:** Economic, top side, qty 5, Confirm Parts Placement. Upload `fab/bom.csv` and
   `fab/cpl.csv`. The switch is the one extended part (a feeder fee once); the rest are basic.
   U1, LCD1, J2–J4 and the unfitted R4/R5 aren't in the BOM.
5. **In the placement preview** check Q1's pin 1 at its silkscreen dot, and that the switches sit
   on their four pads (they're symmetric).
6. **When the boards arrive:** solder the Pico 2 W on the back (tack two corner castellations,
   check the USB is flush with the edge, then the rest), then the panel's FPC on the front, pin 1
   at the dot. Tape the glass down inside the silkscreen corners. Power it over the Pico's USB;
   `tools/emu flash --wifi`, then `tools/fw push console` as for any board.

Rough cost for 5 boards: boards about $5, assembly setup, stencil and one feeder about $13,
placed parts about $1 a board, plus shipping; then about $7 for a Pico 2 W and $2 for a panel per
console. Trust the quote over these.

## Open

- [ ] Measure a panel: pad length, pitch, pin-1 side, how far the FPC reaches below the glass.
- [ ] `tools/keypcb fill`, `check`, `fab`, `render` on a machine with KiCad; record the result here.
- [ ] Button feel: the TS-1097A is 2.6 N. The 1.6 N version (TS-1097A-05016) is the same footprint
      if JLCPCB stocks it.
- [ ] The key's console-side circuit (load switch, CC sensing, ESD) on rev B or an adapter.
- [ ] A case: the holes are M3 at the corners of the screen area; the Pico's BOOTSEL is on the back.
- [ ] The buttons sit above the antenna's end on the front. The datasheet prefers nothing nearby;
      rev B can move the D-pad right if the Wi-Fi suffers.
