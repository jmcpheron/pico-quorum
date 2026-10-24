# picoquorum-key rev A: the design

*2026-10-23. How rev A meets [SPEC.md](SPEC.md). The schematic and board are generated from
`tools/gen/` (see "How the files are made"), so the numbers here are the generator's numbers. If
this file and the board disagree, the board is right and this file is stale.*

![front, 3D](img/rev-a-iso.png)

## In one paragraph

A 44 × 53 mm two-layer board. The ESP32-S3-WROOM-1-N8R2 is hand-soldered on the **back**, its
antenna at the top edge. Everything else JLCPCB places on the **front**: the 1.14″ panel's ZIF
connector (under the glass), five tactile switches, the 3.3 V regulator, USB-C at the bottom edge
with ESD, the backlight switch, the ATECC608C key chip, a status LED and the passives. The panel sits landscape on foam tape. Its ribbon folds under the
glass into the ZIF. Reject, Next and Sign sit in a column on its left, level with the three rail
rows. Debug pads are on the back.

## Decisions and departures from the spec

| topic | rev A does | because |
|---|---|---|
| module | WROOM-1-**N8R2**, hand-soldered, back face | plain N4R2 isn't stocked at LCSC, DigiKey or Mouser (2026-10-23); N8R2 is on the known-good list |
| pins | new profile `picoquorum-key` ([PINS.md](PINS.md)) | no button on a strap, one button polarity, IO_MUX SPI, R8-tolerant, short button tracks |
| key | ATECC608C-MAHDA-S (UDFN-8, 2 x 3 mm), placed by JLCPCB | LCSC C23291019, an extended part; the same chip and package as PicoQuorum's console-s3 (it was SOIC-8, C28975195, until 2026-10-24) |
| backlight | high-side P-FET from **5 V**, NPN level shift from GPIO21, 150 Ω series | the current is (5 − Vf)/R, independent of the LDO; keeps ~13 mA off the 3.3 V rail |
| USB data | 0 Ω links R12, R13 in D+ and D− | removable: the board becomes power-only, closing the REPL path the spec records |
| polyfuse | **none** | JLCPCB has no Basic-tier PPTC; a USB port limits current itself; one fewer extended line |
| PREV, BACK | not fitted | the image reads three buttons; dropping the other two freed the band they sat in and took 5 mm off the board's height. GPIO39 and 38 are left unconnected |
| BOOT, RESET | 4.5 mm tacts on the front, right of centre | placed by JLCPCB; recovery without a tweezer short |
| panel ribbon | folds under the glass into a ZIF under the panel | keeps the board 44 mm wide; the ZIF is 1.0 mm tall and fits under the glass on foam tape |
| debug pads | 12 pads on the back | keeps the front for the screen and buttons; a pogo jig can reach them |
| regulator | AMS1117-3.3 in SOT-223, 1 A | the margin the spec asks for; a JLCPCB basic part |

Nothing here adds a way to sign or to read a key (rule 3). The 0 Ω links only close an existing path.

## Geometry

Origin top-left of the board, X right, Y down (KiCad's convention). All mm. The KiCad page has the
board's top-left at (100, 60); the drill/place origin is the bottom-left, (100, 118).

```
 X:  0    4.5   9                          40  44
 Y 0 ╭──────────────────────────────────────────╮
     │░░░░░░░ antenna band: no copper either face ░░░░░░│  0–7
   7 ├──────────────────────────────────────────┤
     │ [D0]  ┌──────────────────────────┐ C3 C5 │ ← rows 7 / 67 / 127 at Y 10.70 / 17.30 / 23.90
     │       │ glass 31.0 × 17.6     ┌──┐╮ R3 C4 │
     │ [D1]  │                      │J2│ )fold  │   ribbon exits at X 40, folds back to J2
     │       │                      └──┘╯       │
     │ [D2]  └──────────────────────────┘ R6 R7 │
  26 ├──────────────────────────────────────────┤
     │(o)   Q1 Q2 cluster   LED   U2 UDFN   (o) │  H1, H2 at Y 29.5
     │  U3 LDO      R12 U4 R13      R4 [BOOT]   │  Y 35–41
     │  C1 C8 C2    R1     R2         [RESET]   │  Y 41–46
     │(o)              ┌──USB-C──┐          (o) │  H3, H4 at Y 50
  53 ╰─────────────────┴─────────┴──────────────╯
 back: WROOM-1 at X 24–42, Y 0–25.5, antenna end on the top edge; test pads X 9–35, Y 35 and 39
```

| item | position / size | note |
|---|---|---|
| board | 44 × 53, corners R1.5, 2 layers, 1.6 mm | |
| antenna band | Y 0–7, full width | rule area: no tracks, vias, pads or pours on either copper layer. Ground pours start at Y 7.5 |
| module U1 (back) | 18 × 25.5, centre (33, 12.75) | antenna end flush with the top edge; castellation pads 1.0 mm longer than stock for the iron |
| glass | (9.0, 8.5) to (40.0, 26.1), 31.0 × 17.6 | drawn on `User.1` |
| active area | (11.0, 9.87) to (35.9, 24.73), 24.9 × 14.86 | offset away from the ribbon end; 0.110 mm per row |
| rail rows | Y 10.70, 17.30, 23.90 | centre of rows 7, 67 and 127 |
| D0, D1, D2 | SW1–SW3 at X 4.5, on the rail rows | 6.6 mm pitch; 4.5 mm switches leave 2.1 mm between caps |
| J2 ZIF | centre (20.5, 17.3), rotation 90 | under the glass; entry side faces +X, toward the fold |
| under-glass parts | J2, C6 (17.85, 20.2), R5 (23.5, 23) | all ≤ 1.0 mm tall; C6 sits on the 3V3 and GND runs 4.7 mm from the panel VDD pad |
| right strip | C3, C5 at Y 9.6; R3, C4 at Y 12.8; R6, R7 at Y 24.6; X 40.85 and 42.85 (C4 at X 41.0 so its pad clears the fold, which stands up to X 40.5) | beside the module's pins 2, 3, 9 and 10. Y 13.9–23.0 is left clear for the ribbon fold |
| backlight switch | Q1 (15, 30), Q2 (15, 34) and R9–R11, R14 around them | |
| LED | D1 (25.5, 29), R8 below it | visible below the screen's lower edge |
| key U2 | UDFN-8 at (32, 31.5), C7 up and right of pin 8 | about 15 mm in a straight line to module pins 9 and 10; 3V3 comes over the chip's top and down its west side, ground through the exposed pad's via (below) |
| BOOT, RESET | SW6 (36, 39), SW7 (36, 46) | R4 pull-up at (31, 39) |
| regulator | U3 SOT-223 at (10, 39.5); C1, C8 at (5–7.2, 46); C2 at (13.27, 44.2), 4.8 mm from the tab | |
| USB | J1 centred X 22, mouth flush with Y 53; U4 at (22, 39.5); R12 (20.1, 35.5), R13 (25, 35.5), R12 nudged right to clear R9; R1, R2 at Y 41 | ESD array between the connector and the links |
| M2 holes | (3, 29.5), (41, 29.5), (3, 50), (41, 50) | none in the top 29 mm |
| test pads (back) | TP1–TP12, 1.5 mm square, X 9 + 5.2·i, Y 35 and 39 | +3V3, GND, EN, TX, RX, SDA / SCL, BOOT, IO1, IO2, +5V, GND |

Height on the front: tacts 3.8 mm, ZIF 1.0 mm (actuator closed), USB-C 3.2 mm, glass 1.6 mm.
Reference designators are on `F.Fab` only; the silkscreen carries what a person needs, all drawn by
`tools/gen/silk_art.py` (text at least 1.0 mm high with a 0.15 mm stroke, lines at least 0.15 mm,
JLCPCB's legibility minimums):

| side | what is printed |
|---|---|
| front, antenna band | the PicoQuorum mark and name (filled shapes from `hardware/lib/picoquorum.pretty`, the name 2.4 mm to the cap), and `PicoQuorum.app` on a rule |
| front, around the glass | corner ticks 0.4 mm outside the glass (X 9–40, Y 8.5–26.1) for placing the panel; the glass hides anything under it, and the screen labels the rail three |
| front, buttons | BOOT and RESET, each under its switch with a small glyph (bolt, circular arrow) |
| front, elsewhere | an 8-bit key right of U2 and a dragon guarding it, above BOOT (a nod to Atari's Adventure, as on console-s3; 0.3 mm squares of silk); `USB-C 5V` and an arrow beside J1; a ring round each M2 hole for the screw head |
| back | title block (the mark, the name, `KEY, REV A`, `PicoQuorum.app`), the legend `R12+R13 = USB DATA / remove: power-only` and `BOOT+RESET = FLASH`, a key outline with `ONE OWNER / ONE KEY` beside its tip, the twelve test pads each named for its net, `TEST PADS` under them |

Back text is mirrored so it reads with the board turned over. `tests/test_silk.py` checks the size
limits, that each button label sits under its own switch, and that every test-pad label, and the R12/R13
and flash legends, match the nets on the board.

## The panel and its ribbon

The 1.14″ bare panel's ribbon leaves the glass at its right-hand short edge. It folds 180° around
that edge and runs back under the glass into J2. J2 is an HDGC 0.5K-HX-8PWB (C2919492): front
insert, back flip. Its hold-down tabs and entry slot face +X (the fold), and its actuator and
contact tails face −X. Its contacts are double-sided, so the ribbon's face can't be wrong.

Rev A is drawn for the **EastRising ER-TFT1.14-2** (BuyDisplay), using its datasheet (rev 1.0,
2022-02-22, pages 5–8). Its English drawing gives every number the layout needs:

| item | datasheet | on the board |
|---|---|---|
| outline | 31.0 × 17.6 × 1.6 mm "with FPC folded" | glass rectangle (9.0, 8.5)–(40.0, 26.1) |
| active area | 24.91 × 14.86 mm, 135 × 240 | (11.0, 9.87)–(35.9, 24.73) |
| ribbon | 8 pins, 0.5 mm pitch, 0.30 mm thick with stiffener, tail 4.5 mm wide, centred on the short edge | tail centred on Y 17.3 |
| folded tail end | 21.0 ± 0.5 mm in from the glass edge; the fold stands ≤ 0.5 mm proud | tail end at X 19.0; J2 at `ZIF_X = 20.5` |
| fold width | ribbon 9.1 mm wide where it bends, 5.4–14.5 mm from the panel's top | Y 13.9–23.0 kept free of parts beside the glass edge |
| pins, from 1 | LEDA, GND, RESET, RS (DC), SDA (MOSI), SCL, VDD, CS | see below |
| VDD | 2.5–3.3 V, typical 2.8 V, 8 mA | +3V3 (the top of its range, well inside its 4.6 V maximum) |
| backlight | one LED, Vf 2.9–3.1 V at 15 mA, 20 mA maximum | R11 150 Ω: about 13 mA |

**Pin 1 lands on J2 pad 8.** Seen from the front with the ribbon leaving to the right, the
ribbon's pin 1 is at the bottom. The fold keeps that order along Y. J2's pad 1 is at the top
(Y 15.55, the antenna end), so J2 pad n carries panel pin 9 − n: pad 8 is LEDA and pad 1 is CS.
`tools/gen/circuit.py` is wired that way.

**The tail's reach.** J2's entry face is at about X 22.3, and the ribbon goes in about 1.5–2 mm.
The tail needs about 19.5 mm from the glass edge and has 20.5–21.5 mm, so it lies with a slight
bow. Check it with the first real panel before ordering: fold the ribbon, lay the panel on a 1:1
print, and see where the tail's end falls against J2's outline.

Another panel will do if it has the same 8-pin order, but its drawing has to be read the same way.
The other common 8-pin order is GND, VCC, SCL, SDA, RES, DC, CS, BLK, and it would need J2
re-wired.

Under the glass is J2's 1.0 mm plus the folded ribbon (~0.15 mm). Use **1.5 mm** foam tape at the
glass's left and right ends, so the glass clears the connector. The right-hand strip goes in two
pieces, above and below the ribbon's fold (Y 13.9–23.0), since the ribbon runs under the glass there.
`tests/test_3d.py` checks this in 3D: the glass on the tape, the ribbon's path, the fold, the
tape strips (2 mm each) and the M2 heads and nuts against every part's model. J2 is the tallest
part under the glass, 0.5 mm below it. The tact switches stand 0.70 mm above the glass's top, and
the board with parts is 8.6 mm thick (3.8 above, the module's 3.1 below).

## Circuits

### Power

```
USB-C VBUS ─────────────┬─ U3 AMS1117-3.3 ─┬─ +3V3
  CC1 ─ R1 5.1k ─ GND   C1 10 µF, C8 100 nF   C2 10 µF at U3; C3 22 µF + C5 100 nF at module pin 2
  CC2 ─ R2 5.1k ─ GND   │                     C7 100 nF at the key, C6 100 nF at the panel
  shell ─ GND           └─ +5V: U4's VBUS pin and the backlight switch only
```

- The AMS1117 wants ≥ 10 µF on its output for stability: C2 at U3, plus C3 at the module.
- Dropout 1.1 V: a sagged 4.5 V USB rail still gives 3.3 V with margin.
- EN: R3 10k to 3V3, C4 1 µF to GND, RESET tact to GND, pad TP3.

### Backlight (high side, 5 V)

```
+5V ──┬────────────── Q1 AO3401A source
      R10 100k        gate = BL_GATE
      │               drain ── R11 150 Ω ── J2 pad 8 (panel pin 1, LEDA)
 BL_GATE ── Q2 MMBT3904 collector; emitter GND
 GPIO21 ── R9 1k ── Q2 base ── R14 4.7k ── GND
```

- At reset GPIO21 floats. R14 (4.7k) holds Q2 off even if the pin has a pull-up of 20k or more (a ~45k internal one included), R10 holds Q1's gate at 5 V, and the backlight is off.
- GPIO21 high: Q2 saturates, Q1's gate falls to ~0 V, and the backlight is on. PWM at 1 kHz dims.
- R11 sets the current: (5 − 3.0 V) / 150 Ω ≈ 13 mA. Worst case, 5.25 V and Vf 2.9 V, is 16 mA,
  under the panel's 20 mA maximum. 120 Ω gives the datasheet's typical 15–17 mA if it looks dim.

### Screen

ZIF pins per "The panel and its ribbon" above. R5 10k pulls LCD_RST up, so the panel stays out of
reset while the S3 itself resets. C6 100 nF decouples the panel's VDD at the connector.

### Buttons

Five identical 4.5 × 4.5 × 3.8 mm tacts. The footprint uses the two diagonal pads as the switch's
terminals, which is correct whichever way the part pairs its pins inside. Three are UI buttons, each
from its GPIO to GND, with the S3's internal pull-ups (~45 kΩ) enabled in firmware. Sign (D2) is
the bottom of the rail column, farthest from Reject. BOOT pulls GPIO0 low against R4. RESET pulls
EN low.

### Key

ATECC608C-MAHDA-S, UDFN-8 2 x 3 mm: pin 4 GND, 5 SDA, 6 SCL, 8 VCC, 1–3 and 7 NC, the exposed pad
(9) to GND. The exposed pad joins pin 4 on the front and drops to both ground pours through one via
just below the chip. C7 100 nF at pin 8. R6
and R7 4.7k pull SDA and SCL to 3V3. SDA, SCL, 3V3 and GND are on test pads TP6, TP7, TP1 and TP2,
so a key on wires can stand in for the soldered chip.

### USB

Connector D+ and D− → U4 USBLC6-2SC6 (its VBUS pin on +5V) → R12, R13 0 Ω → module pins 14 (IO20,
D+) and 13 (IO19, D−). Keep the pair short and together. At this length a controlled 90 Ω pair is
not needed.

## Routing

Rev A was autorouted with Freerouting 2.5.0 (2026-10-23) and tidied by script. Every connection is
routed, and DRC with schematic parity reports nothing at any severity.

| item | count |
|---|---|
| track segments | ~610 |
| vias placed by the router | 81 |
| GND stitching vias | 51, on a 3 mm grid wherever both pours are solid and no pad is near |

Rules in the project (Board Setup, plus `hardware/picoquorum-key/picoquorum-key.kicad_dru` for the JLCPCB limits
the board minimums don't already cover: plated-hole ring 0.18 mm, plated hole to other copper 0.28 mm,
NPTH at least 0.5 mm, no drill over 6.3 mm; DRC, in the editor and in `tools/export.sh`, reads it):

- Net classes: Power (+5V, +3V3, GND) 0.5 mm, Signal (USB, I2C, LCD) 0.25 mm, everything else
  0.3 mm. Clearance 0.2 mm. Minimum track 0.2 mm. Vias 0.6 / 0.3 mm, tented on both faces.
- Nothing in the antenna band: the rule area keeps tracks, vias and pours out, and the router
  respects it.
- A 2.5 mm keep-out round each M2 hole on both faces: no track or via under a screw head or
  washer. The GND pour may run under it, so a head that bites through the mask lands on ground.
- Ground pours on both faces from Y 7.5 down, pads joined by thermal spokes (0.4 mm spokes,
  0.3 mm gap). On the front the spokes keep 0603 parts with one end on GND from tombstoning in
  reflow. On the back they let the hand-soldered module's pads heat up. Two exceptions are solid:
  module pad 41 (not soldered), and J1's four GND contacts at the board edge, where a relief only
  had room for one spoke.
- Silk rules at JLCPCB's numbers: text at least 1.0 mm high and 0.15 mm thick, 0.15 mm from pads.
- No stitching via in or beside any pad: a via in an SMD pad wicks solder out of the joint.

How to redo it, for example after moving a part:

```sh
tools/build_board.sh --force          # regenerates the unrouted board (throws the routing away)
FREEROUTING_JAR=~/.local/share/freerouting/freerouting-2.5.0.jar tools/autoroute.sh
```

`tools/autoroute.sh` exports a Specctra DSN with the pours removed and runs Freerouting headless.
The DSN asks for 0.01 mm more clearance than the board's rule (`ROUTER_MARGIN` in
`tools/gen/specctra.py`): without it Freerouting's rounding left tracks a few microns inside the
0.2 mm rule. With 0.02 mm the board would not route completely. Freerouting doesn't always give
the same route: one run put D+ 13 mm longer than D−, which `test_geometry`'s USB skew check failed.
So run `tools/test.sh` after every route, and keep the last good route if a new one fails.
It needs Java 25+ (`brew install openjdk`) and the jar from Freerouting's GitHub releases. It then
imports the tracks and runs the tidy steps:

1. `tools/gen/post_route.py` re-drills vias with a thin copper ring, widens the router's
   neck-downs to 0.2 mm, adds the stitching vias and refills the pours.
2. `tools/gen/drc_prune.py` removes any stitching via that DRC objects to.

The router's result is a starting point, not a final word. Worth a look in KiCad's PCB editor:
the USB pair from J1 through U4 and the links to module pins 13 and 14, and the 3.3 V feed into
module pin 2 and C3/C5. `tools/build_board.sh` refuses to overwrite a routed board unless given
`--force`.

## How the files are made

```
tools/gen/circuit.py        every part: symbol, footprint, value, LCSC, MPN, nets  (the source)
tools/gen/make_footprints.py  project footprint copies → hardware/lib/console.pretty
tools/gen/gen_sch.py        circuit.py → picoquorum-key.kicad_sch (global labels, no wires)
tools/gen/check_netlist.py  exported netlist == circuit.py
tools/gen/gen_pcb.py        netlist + placement table → picoquorum-key.kicad_pcb (outline, keep-out, pours)
tools/autoroute.sh          Freerouting round trip, then post_route.py and drc_prune.py
tools/build_board.sh        all of the above, then ERC and DRC
tools/export.sh <rev>       Gerbers, drill, position, BOM → JLCPCB bom.csv / cpl.csv
tools/gen/silk_art.py       the silkscreen: wordmark, labels, glyphs, lock and key, back title block
tools/render/render_with_panel.sh  device renders: ER-TFT1.14-2 model + mock screen, module fitted
```

`tools/build_board.sh --force` rebuilds everything. ERC must be clean, the netlist must match, and
DRC must show no violations apart from unrouted connections and no schematic-parity issues. The
generators refuse to overwrite a hand-edited schematic or a routed board unless `--force` is given.

## Library mapping

| part | symbol | footprint |
|---|---|---|
| U1 module | `RF_Module:ESP32-S3-WROOM-1` | `console:ESP32-S3-WROOM-1_HandSolder` (KiCad's, pads +1.0 mm, no vias under pad 41) |
| U2 key | `Security:ATECC608B-MAHDA` (value ATECC608C-MAHDA) | `Package_DFN_QFN:DFN-8-1EP_3x2mm_P0.5mm_EP1.3x1.5mm` (its exposed pad pasted as four window panes) |
| U3 LDO | `Regulator_Linear:AMS1117-3.3` | `Package_TO_SOT_SMD:SOT-223-3_TabPin2` |
| U4 ESD | `Power_Protection:USBLC6-2SC6` | `Package_TO_SOT_SMD:SOT-23-6` |
| J1 USB-C | `Connector:USB_C_Receptacle_USB2.0_16P` | `console:USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge` (silk kept off the edge) |
| J2 ZIF | `Connector_Generic_MountingPin:Conn_01x08_MountingPin` | `console:FPC_0.5mm_8P_C2919492` (LCSC footprint, hold-downs as MP) |
| SW1–7 | `Switch:SW_Push` | `console:SW_Tact_4.5x4.5_C2897501` (LCSC footprint, diagonal pads numbered) |
| Q1 | `Transistor_FET:AO3401A` | `Package_TO_SOT_SMD:SOT-23` |
| Q2 | `Transistor_BJT:MMBT3904` | `Package_TO_SOT_SMD:SOT-23` |
| D1 | `Device:LED` | `LED_SMD:LED_0603_1608Metric` |
| R, C | `Device:R`, `Device:C` | `R_0603_1608Metric`, `C_0603_1608Metric` / `C_0805_2012Metric` |
| TP | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_1.5x1.5mm` |
| H1–4 | `Mechanical:MountingHole` | `MountingHole:MountingHole_2.2mm_M2` |

Every symbol carries `LCSC`, `MPN` and `Description` fields. U1, the module, is DNP: off the
assembly BOM and CPL, still on the board. Test pads and holes are excluded from the BOM and position file.
LCSC footprints and 3D models are fetched by `tools/fetch_parts.sh` into `hardware/lib/jlc.*`.
Two of those models aren't fit for a mechanical check, so `tools/gen/fix_models.py` (run once with
FreeCAD's `freecadcmd`) writes corrected copies to `hardware/lib/console.3dshapes`, and the footprints
use those:
- the tact switch is a generic 6.5 mm part whose `.step` sits 2.9 mm into the board; it is cut to the
  real 3.8 mm and put on z = 0;
- the ZIF's actuator is drawn standing open (1.75 mm); it is cut to the closed 1.0 mm.

## The spec's checklist, walked

| item | rev A |
|---|---|
| S3 module, ≥ 2 MB PSRAM, ≥ 4 MB flash | N8R2: 2 MB quad PSRAM, 8 MB flash. Kept |
| one profile's pin table named | `picoquorum-key`. Departed from `feather-s3` on purpose, see PINS.md |
| buttons to ground with pull-ups, none on a strap | all three on GPIO42–40. Kept |
| D0–D2 level with rows 7, 67, 127 | by construction from the active area; check on paper. Kept |
| screen upright, buttons left; backlight off at reset | landscape, column on the left; Q1 off until GPIO21 drives. Kept |
| ATECC608C alone at 0x60, pull-ups | nothing else on the bus. Kept |
| GPIO45 low, GPIO0 high, GPIO46 unconnected | 45 and 46 floating on internal pull-downs; 0 pulled up. Kept |
| 3.3 V ≥ 500 mA; EN 10k + 1 µF | AMS1117 1 A. Kept |
| USB-C 5.1k CCs, ESD on data | Kept, plus 0 Ω links |
| antenna at an edge, nothing near | top edge, 7 mm band, holes 29 mm and more away. Kept |
| pads for 3V3 GND EN TX RX and the key bus | back-face test pads. Kept |
| no new way to sign or read a key | Kept |

## Phases from here

1. **Check one real ER-TFT1.14-2** against a 1:1 print: the folded tail's reach into J2, pin 1
   at the bottom, and the rail rows against the buttons. The layout already follows its datasheet.
2. **Review the routing** in KiCad (see Routing) and print the front 1:1 for a thumb check.
3. **Order:** `tools/export.sh rev-a`, then [ORDERING.md](ORDERING.md).
4. **Bring up:** [BRINGUP.md](BRINGUP.md).
5. **Later:** an enclosure on the four M2 holes.
