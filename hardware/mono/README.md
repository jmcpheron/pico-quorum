# Mono: a slender console on an RP2350, with no radio

*Design, 2026-11-06. Written by a script, [gen_mono.py](gen_mono.py), and read back by KiCad 10: the
schematic (netlist and ERC) and the board, routed (DRC, with schematic parity). The fab files for
JLCPCB are in [mono/fab/](mono/fab/) and pass `tools/keypcb jlc mono`. Not ordered, nothing built,
and no panel folded against it yet.*

![Mono from above: the 1.14-inch screen across the top, D0, D1 and D2 in a row under it, an M2 hole either side; below them the second key's site on the left and the key that signs on the right, the RP2350 in the middle, and the USB-C on the bottom end, left of centre](renders/mono-top.jpg)

*KiCad's 3D render. The panel is drawn as a box. More views are in [renders/](renders/).*

Mono is a newer, slender sibling of [console-rp](../console-rp/README.md): a 40 × 89.5 mm bar,
2.24 : 1. The screen sits near the top, the three buttons are evenly spaced under it, and the rest
of the face is a plain field. Power and data come in at the bottom end, through a USB-C left of
centre. Like console-rp it has no radio at all, and the USB-C's data lines reach a USB serial bridge
and nothing else:

```
   computer (the relay) ── USB-C ── CH343P ── UART1 ── RP2350A ── I2C0 ── ATECC608C (the key that signs)
   no key, no say in                                  │   │
   what gets signed                                   │   └─ I2C1 ── KEY 2: a second key's site, its own
                                                      │              switched supply, nothing fitted
                                                      └─ SPI1 ── 1.14" panel;  D0 D1 D2
   the jig, on the back: SWD, RUN, BOOT, the RP2350's own USB, 3V3, GND
```

The computer can't reach the RP2350's REPL, reset it or hold BOOTSEL: the CH343P's DTR and RTS go
nowhere, on purpose (console-rp's README, "Why a serial bridge"). The console rebuilds every hash
itself, and the key signs only that.

## What it keeps, and what is new

Kept from console-rp, whose first board came up on 2026-11-04
([bench/BRINGUP.md](../console-rp/bench/BRINGUP.md)):
- **The RP2350A, its flash and Raspberry Pi's minimal circuit**, with their copper round the chip
  (`rpi_minimal.json`, MIT, [lib/RPI-MINIMAL-LICENSE.txt](lib/RPI-MINIMAL-LICENSE.txt)), turned a
  quarter turn with the chip.
- **The link:** the CH343P on UART1, DTR and RTS unconnected.
- **The key:** an ATECC608C (SOIC-8) on I2C0, 4.7k pull-ups to 3.3 V.
- **The screen:** the same ZIF and pin order, MADCTL 0x60.
- **Every GPIO**, so console-rp's image runs on Mono unchanged ([PINS.md](PINS.md)). The generator
  checks the screen's and key's pins against `firmware/board.py`.

New:
- **The shape.** 40 × 89.5 mm, every part on the front, the jig's pads and the text on the back.
- **An LDL1117S33R** (ST, 1.2 A, SOT-223) in place of console-rp's XC6206 (200 mA in a SOT-23, which
  its README flags at about 82 °C over the air at 0.12 A). By ST's 120 °C/W, 0.15 A from 5 V is about
  30 °C over the air. It is stable on ceramics: 4.7 µF in, 10 µF out.
- **The backlight from 5 V.** A P-FET (Q1), switched by an NPN (Q2) on GPIO13, feeds the LED
  through 150 Ω: 11 to 17 mA across USB's 4.75 to 5.5 V and the LED's 2.9 to 3.1 V. console-rp
  feeds it from 3.3 V through 22 Ω, 12 to 22 mA. It also keeps the backlight off the regulator.
- **No RESET or BOOTSEL buttons, and no header.** Nine pads on the back for a pogo jig
  ([The jig's pads](#the-jigs-pads)). Raspberry Pi says neither button is needed.
- **KEY 2**, a second key's site under D0 ([KEY 2](#key-2)).
- **5.7 µF on VBUS** (C18 4.7 µF, C20 1 µF), under USB's 10 µF. console-rp's outside review found 11.
  USB also counts what charges through the regulator at plug-in, about 17 µF on 3.3 V. By estimate
  that is about 60 µC, a little over USB-IF's 50 µC inrush test. Not measured.
- **The ZIF 19.5 mm in from the panel's ribbon end**, as console-s3 and PicoquorumKey, for the
  drawing's tight fold. console-rp's 17.2 came from an older guess.
- **The picture centred on the board.** The active area sits 1.445 mm off the glass's centre, away
  from the ribbon (the ER-TFT1.14-2 drawing), so the glass sits 1.445 mm right of centre.

## The front

- The glass is 1 mm from the top edge. Its picture is centred across the board.
- D0, D1 and D2 are 10 mm apart, 5.4 mm under the glass. D1 is on the board's middle, and D0 and
  D2 sit about 1.8 mm further out than the middles of the footer's slots, still inside them (each
  slot is about 8 mm wide). An M2 hole sits either side of the row, and one at each bottom corner.
- Under D0 is KEY 2's site, with its five holes. Under D2 is the key that signs. The backlight's
  switch runs down the right edge under the hole.
- The RP2350 is in the middle. Its pins 1–15, the screen's, the buttons' and the key's, face up.
  The flash is up and to the right, the crystal is on the left, and the regulator's corner is at
  the bottom right of the chip.
- The bottom end: the USB-C left of centre, its ESD diodes and the CH343P above it, and the LDL1117
  on the right.
- The silkscreen on the front is the buttons' names, KEY 2's labels and two drawings. The
  key-forge, a hammer over a key on an anvil, is the owner's drawing traced into keyforge.json. It
  sits between D2's name and U5, the key that signs. Some ground vias are under it; they're tented,
  so it prints over them. The dragon from Atari's Adventure, 4 × 10 mm, is under the glass's left
  end, where the panel hides it; it prints over tented ground vias too. On the back: EXPERIMENTAL
  HARDWARE COSIGNER, "nothing is fitted on this side", "no radio: USB serial only", the revision,
  picoquorum.dev (the Source Location), the licence, the census of the parts, the current to expect,
  and the jig's pads' names.

Every part JLCPCB fits is on the front, because Economic assembly does one side. So the field below
the buttons holds the electronics. A case's face would cover them.

## The jig's pads

Nine 1.5 mm pads in one row on the back, under the RP2350, at 2.54 mm. Nothing reaches them through
the USB-C.

| pad | net | what |
|---|---|---|
| TP1 | SWCLK | through 100 Ω (R15), so a jig's long leads can't ring into the chip |
| TP2 | GND | |
| TP3 | SWDIO | through 100 Ω (R16) |
| TP4 | RUN | low resets the RP2350 |
| TP5 | 3V3 | to measure only. Power the board through the USB-C: 3.3 V here with no 5 V puts the LDL1117's output above its input, past ST's absolute maximum (VIN + 0.3 V) |
| TP6 | BOOT | QSPI_SS through 1 kΩ (R3): to GND at reset for the RP2350's USB boot |
| TP7 | D+ | the RP2350's own USB, through 27 Ω (R14) |
| TP8 | D− | through 27 Ω (R13) |
| TP9 | GND | |

The four M2 holes can locate the jig. console-rp's board 1 was loaded over SWD. Its USB on J3,
the same circuit as TP7 and TP8, has not enumerated yet; the cause isn't known.

## KEY 2

A second key's site, below the screen and buttons, under D0. Nothing in it is fitted, and console-rp's
image leaves it switched off.
- **Its own bus:** I2C1 on GPIO14 and GPIO15 (pins 18 and 19). Two ATECC608s can't share a bus,
  since both answer at 0x60, and a fault at the holes can't take the signing key's bus down.
  `firmware/atecc.py`'s `make_i2c` puts this pair on I2C1; the generator checks that.
- **Its own supply, VKEY:** U9, an AP22653W6-7, from 3.3 V. Its EN is GPIO7, held low by R20 (4.7k,
  under the 8.2k RP2350-E9 asks for), so the site is off at reset. The switch limits the current,
  40 mA at least and 120 mA at most with ILIM to ground (Diodes' datasheet, at 5 V in). When off, it
  discharges its output through 600 Ω and blocks current back into 3.3 V. FAULT is not connected.
  C28 sits beside IN and ground, C29 beside OUT and ground, and one ground line joins the switch's
  two ground pins, both capacitors, R20 and U10 to a via.
- **Pull-ups to VKEY,** R17 and R18 4.7k, never to 3.3 V: a key that is off isn't fed through its
  pins. R19 10k holds the Trust M's reset off.
- **Footprints, not fitted:** U7 for an OPTIGA Trust M (SLS32AIA, USON-10, at 0x30) on KiCad's
  3 × 3 mm USON-10, and U8 for an ATECC608C (SOIC-8, at 0x60). Their 100 nF (C26, C27) are fitted.
- **Five holes,** J4, not fitted: VKEY, GND, SCL, SDA, RST, Adafruit's breakouts' order (the Trust M
  breakout uses all five, the ATECC608 breakout the first four). Both faces are labelled. A breakout
  put on the wrong way round lands its VCC and GND on signal holes, so meter it before power.
- **ESD at the holes:** U10, a USBLC6-2SC6 on SCL and SDA, its rail on the always-on 3.3 V. A
  footprint for an ESD5Z5V0 on VKEY (D2), not fitted, for a key plugged in and out there. RST has
  no clamp: it runs from hole 5 straight to U7 and R19.
- **C29, 1 µF on VKEY,** not 10: the Trust M wants VCC to rise from 0.4 V to 90% in 1 ms at most
  (Infineon's datasheet, Table 12). That isn't guaranteed here. The switch's own rise is 0.3 ms
  typical and 1 ms at most (Diodes, 3 V in, 1 µF). A breakout's 10 µF on top adds about 0.7 ms at
  the switch's 40 mA least, by estimate. Measure it before relying on a breakout. RST reaches no
  GPIO, so the firmware can reset a Trust M only by command, or by turning VKEY off, waiting about
  25 ms for it to drain through the switch, and on again.

Using KEY 2 needs a board profile and a second bus in `signer.detect()`: a firmware change, so a
new release fingerprint, and making a second chip sign is the owner's decision (AGENTS.md, rules 1
and 2). The board adds no way to sign and no way to read a key out.

## Parts at JLCPCB

console-rp's parts ([its README](../console-rp/README.md#parts-at-jlcpcb), read 2026-10-28), less its
XC6206, buttons SW4 and SW5 and J3, plus these, read from LCSC on 2026-11-06:

| part | LCSC | stock | tier |
|---|---|---|---|
| LDL1117S33R | C435835 | 58,511 | not checked |
| AP22653W6-7 | C2158037 | 11,045 | Extended (console-pcb's README, 2026-10-07) |
| 100 Ω 0402 | C25076 | 7.27 M | not checked |

67 parts fitted (the census on the back counts them), the screen fitted by hand. U7, U8, D2 and J4
are not fitted, and the jig's pads are copper only.

**L1 is still the risk.** console-rp's order took JLCPCB's last 6 of Raspberry Pi's inductor on
2026-10-29. Check its stock before ordering.

**Placement.** console-pcb and feather-wing found that JLCPCB draws the AP22653 turned 180° and the
USBLC6 turned 90° from KiCad, and carry a "JLCPCB Rotation Offset" for each. console-rp carried
none for its USBLC6 and its boards came back working. Mono carries none yet. Check every part in
JLCPCB's placement preview against `fab/check/cpl-overlay.png`, and above all U9, U2, U10 and D1
(the LED, turned 180° here and 0° on console-rp).

## The panel

The ER-TFT1.14-2 drawing (rev 1.0, 2022-02-22), the panel console-rp's README describes:
- the module 31.0 × 17.6 × 1.6 mm, on four 2 mm foam pads at its corners;
- the active area 24.91 × 14.86 mm, its centre 1.445 mm off the module's, away from the ribbon.
  PicoquorumKey's notes read the same drawing as 2.0 mm;
- the ribbon 4.5 mm wide, folded under the glass. Its end reaches 21.0 ± 0.5 mm in from the glass's
  ribbon end, and the fold stands at most 0.5 mm past that end. The glass ends 3.055 mm from the
  board's right edge.

J2's origin is 19.5 mm in from the glass's ribbon end. Under the glass are only J2 and its two
capacitors (C24, C25); the generator checks their heights and keeps them off the foam pads and out of
the ribbon's path.

Before ordering, fold a real panel over a 1:1 print of the board: the reach, how wide the fold is,
how far it stands out, and 1.445 against 2.0 for the active area. Also measure how deep the ribbon
goes into a real ZIF (2.6 mm assumed).

## Round the RP2350

Raspberry Pi says to copy its minimal design's layout, so the board does, as console-rp did: their
parts at their places round U1, their power copper and their crystal's corner, locked, all turned
with the chip. Where Mono differs from console-rp:
- **The chip is turned −90°**, so its first fifteen pins face the buttons and the screen, and the
  flash sits up and to the right, clear of the glass.
- **The escapes.** Raspberry Pi's 100 nF row (C5, C10, C4) stands 2.3 mm above the top edge's pads,
  and C8 under the LED's pin. The first route left SDA, SDA2, D0 and D2 open there and necked
  LCD_DC to 0.12 mm. So the lines out of the top, left and bottom edges are drawn and locked
  (`ESCAPE`), and the router or the drawn lines ([Routing](#routing)) take each on from its end:
  the screen's five in one column past C5 and straight up to y 43, RESET out of it to a via;
  pins 7–10 straight up between C5 and C10, KEY2_EN to a via; D1 and D0 between C10 and C4, D0 to
  a via; KEY 2's bus off the left edge at 45°; the backlight up beside the screen's column to a
  via; and the LED down past C8.
- **A ground via over each of C5, C10 and C4,** since the escapes wall their ground pads in.
  console-rp's one via between C10 and C4 is gone: D0's escape would cut C4 off from it.
- **SWCLK and SWDIO run on into their 100 Ω** and RUN to its via, which takes it to its pad.

## Routing

`tools/keypcb route mono` routed the board with Freerouting 2.5, which gives the same route for the
same board. So wherever a route left a net open, walled a pad in or took a poor way, the line was
drawn in `gen_mono.py`, locked, and the board routed again: six routes in all. The drawn lines, each
with why in the generator's comments:
- the escapes round U1 ([Round the RP2350](#round-the-rp2350));
- 3V3: the regulator's output to the rest; from C6 past KEY 2's corner and on the back to C23,
  then up beside the screen's lines to J2, C24 and C25; from C7 to the CH343P and C22;
- the screen's five from the column to J2. RESET and CS run on the back beside the front's three,
  not under them, and MOSI crosses under SCK just below J2. The backlight's line goes under the
  lines out of U1's top;
- KEY 2's switch's ground, and its bus into U10;
- D0 to SW1, D2 between SW2's pads and over it to SW3, and KEY2_EN and D0 under the screen's column;
- ground vias where the pour can't reach a pad: C5's, C10's, C4's, C22's and the panel's ground
  pin's, and console-rp's round U1, the flash, the CH343P and U2 (`HAND_VIAS`).

For the route only, rule areas kept lines from necking down or starving a spoke: under U8, past
J2's pad ends, 1.65 mm round J4's ground hole and round U1 and the flash on the back, from U2's
ground via to the edge, the crystal's corner, and 0.6 mm in from the edge. `tools/keypcb gen-mono
tidy` takes them off after the route.

Ground is left to the pours and 250 ground vias. `tools/keypcb route` put 225 of them in as it read
the route back: on a 2.5 mm grid, and one in each island of the front's pour the grid missed. The
route is told to skip the Ground class (`-inc Ground`), but it still drew 107 mm of short ground
lines, inside the pours; console-rp's route drew 139. Tracks are 0.2 mm, and 0.25 for power and
ground. The escapes and the screen's lines are 0.15, the least, and Raspberry Pi's DVDD and the
regulator's output are wider.

After the last route the board was put right in place, not routed again. The generator draws the
same for the next route:
- **TP5,** which the route left open, has a via off 3V3's line to U4.
- **SCL** leaves U1 left of SDA, but its pads are below SDA's, so the route took it 61 mm up round
  SW2 and back. It now crosses under SDA through two vias: 24 mm from U1's pin to U5's.
- **Two ground vias** sat 1 nm off the ends the route drew to them, because KiCad's millimetre
  conversion truncates. JLCPCB's DRC flags that (`track_not_centered_on_via`). The generator now
  rounds.
- **96 mm became 89.5.** The top edge came down 2 mm, so the glass is 1 mm from it. Everything
  below y 73.85 rose 4.5 mm into the empty field under the LED: the USB-C, U2, the CH343P, the
  regulator, their capacitors and resistors, the bottom holes, a fiducial and their copper. Lines
  running straight down through the field got shorter. Four crossed it at a slant: the regulator's
  3V3 line, which the generator draws, is now its column and one 45° run, and VBUS, LINK_TX and
  LINK_RX, the route's, keep their upper part and take a 4.5 mm level jog in the field. On the back,
  the warning came down with the edge, and the current lines and the logo rose only 1.3 mm, clear
  of the jig's names. The route's top row of ground vias, now off the board, came out, and 15 more
  where the two halves met, too near each other or other copper: 29 in all. The pours were filled
  again.
- **The silkscreen's drawings and address** (2026-11-08). The key-forge and the dragon were drawn
  onto the board by the generator's own `art()`, and the back's address became picoquorum.dev. Only
  the two silkscreen layers changed.

## What is checked, and how

`tools/keypcb gen-mono` (add `render` for the pictures) writes everything from the one table in
`gen_mono.py`, then checks it. It won't overwrite a routed board: `tools/keypcb gen-mono check`
checks the routed one as it is. Both run:
- **KiCad reads the schematic back.** Its netlist must match the table, net by net.
- **ERC:** 0 errors, 0 warnings.
- **The link's wiring:** the USB-C's D+ and D− reach only J1, U2 and U4; the CH343P's DTR and RTS
  nothing; no net but power joins the USB-C to the RP2350; SWD, RUN, BOOT and the RP2350's own USB
  reach only their jig pads.
- **KEY 2's wiring:** its bus, supply and reset reach only its own parts, and there is no 3.3 V on
  its holes.
- **Every symbol pin has a pad** in its footprint, and every pad a pin.
- **Each GPIO's function** (UART1, I2C0, I2C1, SPI1) against the RP2350's table; the screen's and
  key's pins against `firmware/board.py`; KEY 2's pair against `make_i2c`.
- **DRC** on the placed board, and on the routed one with schematic parity. The five findings left
  are expected, each a footprint that differs from its library's copy. J1's silkscreen past the edge
  is left out. FID1–3 and U4 differ from KiCad 10.0.8's library, which came after the route: it
  tags the fiducials' pads as fiducials, a Gerber attribute, and moves the CH343P's pin-1 mark to
  its corner. Their copper, mask and paste are the same.
- **Raspberry Pi's areas:** no other net's copper in their regulator's or crystal's corner, or under
  the chip or the crystal on the back.
- **Under the glass:** each part's height and place.

`tools/keypcb fab mono` writes the files to upload: `mono-gerbers.zip`, `bom.csv` and `cpl.csv` in
[mono/fab/](mono/fab/). `tools/keypcb jlc mono` ([tools/jlc](../../tools/jlc/README.md)) passed
every check: DRC at JLCPCB's limits, the Gerbers and drills read back, the netlist, the BOM and
CPL against LCSC's parts, mask and paste, holes, pours and the 3D fit. It passed on 2026-11-06,
before the board was made shorter and after, and on 2026-11-08 after the drawings, with KiCad
10.0.8, each time with `--strict` against the golden pictures (written again for the shorter
board, then the silkscreen's for the drawings). Its self-test caught 10 of 10 broken copies. For
the fit, its broken copy makes J2's ZIF 3 mm tall, since no SOT-23 sits under Mono's glass
(`selftest_tall` in the spec; other boards' copies still raise their SOT-23s). What its spec
(`jlc_spec()`) lets through, each with why:
- 30 DRC findings: Raspberry Pi's footprints and the ZIF don't match the stock symbols' footprint
  filters (23), U1 is an SMD part with holes in its pad, J1's silkscreen past the edge is left out,
  FID1–3 and U4 differ from KiCad 10.0.8's library (above), and the panel has no courtyard (the
  fit's glass stands in).
- U1's nine thermal-via holes are held to the vias' ring (0.15 mm), not a component hole's 0.2.
- The one via in the CH343P's exposed pad, the only via not tented.

Its first run failed three DRC checks: the two ground vias above, and KEY 2's label closer to
R18's silkscreen than JLCPCB's 0.15 mm. The label is now 0.2 mm lower, midway between R18's
silkscreen and J4's outline. It also warned that U7's exposed pad joined the pours solid, as KiCad's
footprint has it, so slow to heat when the Trust M goes on by hand. It now takes spokes (`SPOKED`).
No warnings are left. Worth reading in its output:
- U3 runs about 31 °C over the air at 0.15 A, by ST's 120 °C/W;
- the least paste area ratio is 0.72 (U1's pins, for a 0.12 mm stencil), and the narrowest mask web
  between nets is 0.17 mm (U1's pins too);
- the least ground on the other layer is under USB_D− (52% of 16.3 mm) and SDA2 (53% of 45.1 mm).

Not checked:
- the Trust M's land pattern (KiCad's Microchip USON-10) against Infineon's package drawing;
- the SOT-223's height (1.8 mm assumed) and the 3D fit's other guessed sizes;
- anything on a real board.

## Steps to a board

1. Fold a real panel against a 1:1 print ([The panel](#the-panel)).
2. Check L1's stock, and the new parts' tiers.
3. `tools/keypcb jlc mono`, then upload `mono/fab/mono-gerbers.zip`, `bom.csv` and `cpl.csv`:
   Economic, one side. Check the placement preview, U9, U2, U10 and D1 above all.
4. Bring one up over SWD, as console-rp's board 1 ([BRINGUP.md](../console-rp/bench/BRINGUP.md)),
   with console-rp's image.

## Open

- [ ] The panel's fold and the ZIF's depth, measured.
- [ ] L1's stock.
- [ ] The jig: a pogo fixture for the nine pads, located on the M2 holes. It powers the board
  through the USB-C; TP5 only measures.
- [ ] The RP2350's own USB on TP7 and TP8, unproven, as on console-rp.
- [ ] Secure boot. The RP2350 can boot only images signed with a key in its OTP. It is one-way,
  and console-rp's plan tries it on a spare board first. Raspberry Pi's RP2350-E24 erratum is about
  glitch attacks on the A2 stepping; check which stepping JLCPCB supplies.
- [ ] KEY 2's firmware, and whether to fit a key there. VKEY's rise with a breakout on it,
  measured; and whether RST wants a GPIO (spares: 0, 1, 16–19, 22–24, 26–29).
- [ ] A case.
- [ ] picoquorum.dev, printed on the back as the Source Location, must lead to the source before
  boards ship. Its forwarding is still to do (docs/STATUS.md). It expires 2027-10-06, and the
  licence wants a Source Location that lasts three years.
