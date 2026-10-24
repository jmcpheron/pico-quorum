# Order plan, 2026-10-24

Two boards to order from JLCPCB, five of each: console-s3, and PicoQuorumKey, designed apart to compare. Prices
below are from JLCPCB's pages read on 2026-10-23 and 24 ([sources](#sources)). They are estimates, not
quotes: the quote page fills its prices in by script, so get the real figures by uploading the files.

## 1. console-s3 rev A, five boards

The board: [hardware/console-s3](hardware/console-s3/DESIGN.md). Routed, and `tools/keypcb check`
and `tools/keypcb jlc` pass on it as of 2026-10-24. Its files are in `hardware/console-s3/console-s3/fab/`:
`console-s3-gerbers.zip`, `bom.csv`, `cpl.csv`.

### Before ordering

- [ ] **Measure a panel** (CONCEPT step 1): glass, the tail's length, the pin order, which face its
      contacts are on after the fold, the LED's forward voltage. Check its ribbon has 8 pins at
      0.5 mm, for J2 (HDGC 0.5K-HX-8PWB, C2919492). If anything moves, run the generator and
      `route` again.
- [ ] **Measure a module** against Espressif's Figure 11-1.
- [ ] **Look the routing over in KiCad** by eye, the tracks under the module most.
- [ ] `tools/keypcb fab console-s3`, then `tools/keypcb jlc console-s3`: every check passes.
- [ ] Check stock (below) the same day you order.

### The one decision: who fits the module

JLCPCB marks every ESP32-S3-WROOM-1 "Standard only". Economic assembly can't place it, and it
assembles one side only, and the module is on the back. So it is one of these:

| | **A. Economic, front only** (recommended for these five) | **B. Standard, both sides** |
|---|---|---|
| JLCPCB fits | every part in `bom.csv`: all on the front | those, and the module on the back |
| You fit | the module: 40 castellations with an iron, about 15 minutes a board (CONCEPT.md) | nothing |
| Setup and stencil | $8.18 + $1.53 | $51.12 + $16.42 (two sides) |
| Feeder fees | $3.07 for each Extended part type: U2, U3, U4, J1, J2, about $15 | $1.53 for every part type, about $34 |
| Board size | 10 x 10 mm or more: fine | 70 x 70 mm or more: the board needs a panel or rails (ask support, or "Panel by JLCPCB") |
| Build time | 1–3 days | 4 days or more |
| Assembly, before parts | about $25 | about $100, plus the panel |

**A saves about $75 and needs no panel.** The module goes on by hand as the design always meant
(the workshop's steps in [CONCEPT.md](hardware/console-s3/CONCEPT.md#what-jlcpcb-does-what-the-workshop-does)).
B is for when soldering forty pads per board is the bottleneck; CONCEPT puts that past about 20 boards.

For option A, buy the five modules from LCSC in the same order or separately:
- The design's part: **ESP32-S3-WROOM-1-N4R2, C2913203**. Stock wasn't confirmed.
- If it's short, **N8R2, C2913204**: about $4.60, with 6,428 in stock on 2026-10-24. Quad PSRAM, so
  firmware-compatible. **Never an R8 part** (octal PSRAM takes GPIO35–37), and the generator
  refuses one.

### Flashing the firmware

JLCPCB's "PCBA Programming Service" exists only with Standard assembly. It needs an engineer's review
for each chip, with ESP32 not on any published list. It costs about $8 plus $8 an hour, and works
from a HEX or BIN file you upload.

**Recommendation: flash them yourself.** The console image must hash to its release fingerprint, and
`tools/fw push console` puts it on and checks it. Over USB-C that is a minute a board, and you would
re-flash and verify a factory-flashed board anyway. Paying for it only buys MicroPython on the chip,
which `esptool` does in a minute. If you choose B anyway, the option is under Advanced Options →
Function test.

### The PCB order: what to select

| option | choose | why |
|---|---|---|
| Base material | FR-4 | |
| Layers | 2 | |
| Dimensions | 64 x 22.86 mm (read from the zip) | |
| PCB qty | 5 | the least |
| Delivery format | Single PCB for A; Panel by JLCPCB for B | B needs 70 x 70 mm |
| Thickness | 1.6 mm | the design's stackup, and Economic's range is 0.8–1.6 |
| Colour | **Green** | the only colour without two extra days, and the mask limits checked are green's |
| Surface finish | **LeadFree HASL** | lead-free, cheap. ENIG is flatter for the 0.5 mm ZIF and UDFN but costs more; HASL is what the design says |
| Outer copper | 1 oz | |
| Via covering | Tented | the default, and all 74 vias are 0.3 mm, tented in the Gerbers |
| Mark on PCB | **Remove Mark** (or the free 2D barcode) | JLCPCB now adds no order number by default; check the option shows "no mark" |
| Electrical test | flying probe (free) | |
| Gold fingers, castellated holes | No | |
| Confirm Production File | Yes | a person looks at the files before production (its fee, if any, wasn't read) |
| Impedance control | none | full-speed USB doesn't need it |

**Watch for the small-board fee:** one side at 30 mm or less on a "Single PCB" order costs extra,
and 22.86 mm qualifies. The fee wasn't readable. If it's large, "Panel by JLCPCB" may cost less.

### The assembly order: what to select

- **PCBA type:** Economic (A) or Standard (B).
- **Assembly side:** Top (A), or Both (B).
- **PCBA qty:** 5, or 2 to try first. It may be less than the PCB qty; then "Accept Shortages"
  appears.
- **Tooling holes:** added by JLCPCB. **Fiducials:** not needed for Economic.
- **Confirm Parts Placement: Yes.** Then hold JLCPCB's preview against
  `fab/check/cpl-overlay.png`, pin 1 by pin 1: U2 (UDFN-8), U3, U4, Q1, Q2, D1, J1, J2.
- Upload `bom.csv` and `cpl.csv`. The module isn't in them (A). For B, add U1's row first.

### Parts to check on the day

| part | LCSC | stock read 2026-10-24 |
|---|---|---|
| ATECC608C-MAHDA-S, U2 | C23291019 | **62 at JLCPCB, 0 at LCSC: thin.** If it's under 5, pre-order it into your JLCPCB parts library before the order |
| ESP32-S3-WROOM-1-N4R2 (A: LCSC; B: JLCPCB) | C2913203 | not confirmed: N8R2 C2913204 instead |
| the 1.14″ panel | not stocked | about $2.50 each elsewhere; buy 6 or 7 |
| everything else | `bom.csv` | check the BOM page shows no shortages |

### Rough total for A, five boards

PCB about $2–10 (plus the small-board fee, unknown), assembly about $25, U2 5 x $2.64, the other
parts a few dollars, modules 5 x about $4.60, panels 5 x about $2.50, plus shipping. **About $75–90
before shipping.** Upload the files for the real figure.

### When they arrive

The workshop's steps, per board (CONCEPT.md):
1. Solder the module.
2. Meter 3.3 V to GND for a short.
3. Plug in USB: the LED lights and the S3's USB port appears.
4. Clip in the panel.
5. Flash MicroPython, run `tools/fw push console`, then the bench scan.

Write down in DESIGN.md:
- U3's temperature with the radio busy;
- whether R8 is clear of the real ribbon fold.

## 2. PicoQuorumKey rev A, five boards

The board: [hardware/picoquorum-key](hardware/picoquorum-key/README.md), designed apart from console-s3
to the same spec, ordered beside it to compare. 44 x 53 mm, the module on the back, the panel in a
ZIF on the front, five buttons, U2 the same UDFN ATECC608C as console-s3. Its files are in
`hardware/picoquorum-key/hardware/out/rev-a/`: `picoquorum-key-gerbers.zip`, `bom.csv`, `cpl.csv`,
and `fit-check-front-1to1.pdf`. Its own step-by-step is
[its ORDERING.md](hardware/picoquorum-key/docs/ORDERING.md).

### Before ordering

- [ ] Its `tools/test.sh` passes (125 tests; it did on 2026-10-24), after `tools/export.sh rev-a`.
- [ ] Print `fit-check-front-1to1.pdf` at 100 % and lay a real panel on it: the folded tail reaches J2.
- [ ] **Know it won't run the console image yet.** Its buttons are on GPIO40–42, which today's ESP32-S3
      profile drives as outputs. Flash only its `firmware/smoke/smoke.py` until a `picoquorum-key`
      profile and a new release exist ([its README](hardware/picoquorum-key/README.md#in-picoquorum)).
- [ ] Check stock the same day (below).

### What to select

The same as console-s3's option A, with three differences:

| | PicoQuorumKey | why |
|---|---|---|
| Dimensions | 44 x 53 mm | no side at 30 mm or less: **no small-board fee** |
| Assembly | Economic, top side | the module goes on by hand, as on console-s3 |
| Extended part types | J1, J2, the switches, U2, U4: five | about $15 in feeder fees |
| Stencil | 0.10, 0.12 or 0.15 mm (0.12 is fine) | U2's pads limit it to 0.150 mm |
| Placement preview | U2's pin 1 (a small dot), U3's tab, U4, Q1, Q2, D1, J1, J2 | there is no `cpl-overlay.png` for this board: hold `cpl.csv`'s rotations |

PCB options otherwise as console-s3's table: FR-4, 2 layers, 1.6 mm, green, LeadFree HASL, 1 oz,
tented vias, Remove Mark, flying probe.

### Shared with console-s3

- **U2, ATECC608C-MAHDA-S, C23291019:** both boards use it, so ten for two orders of five. On
  2026-10-24 JLCPCB had 62 and LCSC none: if fewer than 10 show on the day, pre-order them into the
  JLCPCB parts library first.
- **The module:** N8R2, C2913204, the design's own part. Seven per its BOM (two spare).
- **The panel and J2:** the same kind of panel (1.14″ ST7789, 8-pin 0.5 mm ribbon; NFP114H-03AF is
  printed on the Walfront one both designs name) in the same ZIF, C2919492. Check each board's pin
  order on its own 1:1 print: they were laid out apart.
- Order both boards in one JLCPCB cart to share shipping.

### Rough total, five boards

Its BOM.md puts it at about $125–175 with seven modules, seven panels and shipping. With console-s3
in the same cart, the shipping is paid once.

## Sources

Read 2026-10-23 and 24:
- https://jlcpcb.com/help/article/pcb-assembly-price (updated 2026-10-22): setup, stencil, feeder fees, Economic and Standard quantities and sizes
- https://jlcpcb.com/capabilities/pcb-assembly-capabilities: Economic single-sided; Standard both sides, 70 x 70 mm
- https://jlcpcb.com/help/article/pcba-programming-service (2026-09-09)
- https://jlcpcb.com/help/article/pcb-assembly-faqs and https://jlcpcb.com/help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order (2026-09-09): rails, fiducials, tooling holes
- https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra (2026-09-09): the small-board fee
- https://jlcpcb.com/help/article/shortage-preference-guide; https://jlcpcb.com/help/article/pre-ordering-parts-terms-conditions
- https://jlcpcb.com/help/article/pcb-via-covering
- https://cart.jlcpcb.com/quote: the option names, "No mark will be added by default", green's turnaround
- JLCPCB part pages, e.g. https://jlcpcb.com/partdetail/EspressifSystems-ESP32_S3_WROOM_1_N8R2/C2913204, and C23291019: "Standard Only", stock, tiers
- https://www.lcsc.com/product-detail/C2913203.html, C2913204.html, C23291019.html
