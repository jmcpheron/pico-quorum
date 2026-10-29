# console-rp: the console on an RP2350, with no radio

*Design, 2026-10-29. Written by a script and read back by KiCad 10: the schematic (netlist and ERC)
and the board, routed (DRC). The fab files for JLCPCB are in [console-rp/fab/](console-rp/fab/) and
pass `tools/keypcb jlc console-rp`. Ready to order: two real panels were checked against J2
([The panel](#the-panel)). Not built yet, and the firmware it needs is not written.*

![console-rp from above: a warning triangle and EXPERIMENTAL HARDWARE COSIGNER over the 1.14-inch screen at the top left, PicoQuorum console-rp under it, and D0, D1 and D2 in a row below that; the flash, the RP2350, the crystal, the CH343P, and the key chip with an 8-bit key pointing at it, to its right; the USB-C on the right edge, RESET and BOOTSEL at the bottom right, and the bench header's holes along the top](renders/console-rp-top.jpg)

*KiCad's 3D render of the routed board. The panel is drawn as a box. More views are in
[renders/](renders/).*

[console-usb](../console-usb/README.md) took the radio out of use on an ESP32-S3. This board takes
it out of the chip: an **RP2350A** has none. The console talks to the world only through the USB-C
cable it is powered by. A program on the computer fetches the Safe's queue for it and posts its
signatures. The console still rebuilds every hash itself, and the key still signs only that.

```
   Safe's service ── HTTPS ── computer (the relay) ── USB-C ── CH343P ── UART1 ── RP2350A ── I2C0 ── ATECC608C
                              no key, no say in                              screen, D0 D1 D2
                              what gets signed
```

## Why an RP2350

The parts cost about the same as console-usb's: the RP2350A ($1.13 at 100) and its flash ($1.78)
against the S3's $2.52. What it buys is simpler:
- **No radio on the chip at all**, so nothing to keep switched off and no antenna rules.
- **The stock MicroPython image for the Pico 2** (not the W) runs on it, and the console already
  runs on an RP2350 (the Pico 2 W).
- **KiCad 10 ships the RP2350A's symbol and footprint**, and Raspberry Pi publishes the minimal
  circuit around it ("Hardware design with RP2350"). The circuit here is that one.

## Why a serial bridge, not the RP2350's own USB

The RP2350's own USB carries MicroPython's REPL. On this console the cable goes to a computer and
stays there, so any program on that computer could reach the REPL. From there it could make the chip
sign any digest, or call `machine.bootloader()` and write a new image. The bridge closes this with
wiring, as on console-usb:
- The USB-C's D+ and D− go to a **CH343P** (C2846043) and nothing else. It is a standard USB serial
  device (CDC-ACM), so no computer needs a driver.
- Its TXD and RXD go to **UART1** (GPIO21 and GPIO20). MicroPython never puts its REPL there.
- Its **DTR and RTS go nowhere.** The computer can't reset the RP2350 or hold BOOTSEL. DTR is also a
  strap at power-up, so it floats.
- The RP2350's own USB (through Raspberry Pi's 27 Ω) and SWD go to **J3**, a header that isn't
  fitted. Flashing needs J3 and a cable, or SWD and a debug probe: a person with the board in hand.

The generator checks this from KiCad's netlist and stops if it isn't so: the USB-C's data lines,
DTR and RTS, the RP2350's USB and SWD, RUN and BOOTSEL.

## The circuit

| block | parts | notes |
|---|---|---|
| the chip | U1 RP2350A (QFN-60), a 100n at each power pin | USB_OTP_VDD and QSPI_IOVDD share one, as the minimal design |
| its 1.1 V | L1 3.3 µH, C1 and C2 4.7 µF, R1 33 Ω and C3 4.7 µF on VREG_AVDD | the minimal design's. Raspberry Pi says to copy its layout and L1's orientation exactly |
| the clock | Y1 ABM8-272-T3 12 MHz, C15 and C16 15 pF, R2 1 kΩ into XOUT | the crystal and values Raspberry Pi asks for |
| the flash | U6 W25Q128JVSIQ, 16 MB, R3 1 kΩ and SW5 BOOTSEL on QSPI_SS | Basic at JLCPCB, so no fee. The Pico 2 image uses 4 MB of it |
| power | J1 USB-C (5.1k on CC1 and CC2), U2 USBLC6-2SC6, U3 XC6206P332MR | 200 mA is well over what the board draws |
| the link | U4 CH343P | VDD5 and VBUS from the USB-C, V3 on its own 100n, VIO at 3.3 V (WCH's datasheet, 5.2) |
| the key | U5 ATECC608C-SSHDA-T (SOIC-8), R6 and R7 4.7k on I2C0 | SOIC because JLCPCB has 3,972; the UDFN had 27 |
| the screen | J2 ZIF for the 1.14″ 240 × 135 ST7789, Q1, Q2 backlight switch | console-usb's: the same ZIF, panel and pin order |
| buttons | SW1–SW3 D0 D1 D2 in a row under the screen, each to GND | pulled up inside the RP2350, pressed low. Each sits under one of the three footer slots the QT Py console draws |
| reset | SW4 RESET on RUN | |
| bench | J3, 8 holes: GND, 3V3, SWCLK, SWDIO, D−, D+, SDA, SCL | not fitted |

[PINS.md](PINS.md) has the GPIOs. The screen (GPIO 8–13 on SPI1) and the key (GPIO 4 and 5 on I2C0)
are on the Pico's pins, the ones `firmware/board.py` uses by default. The generator checks that, and
checks each GPIO against the RP2350's function table.

**RP2350-E9.** A GPIO with only a weak pull-down can float at about 2 V. Nothing here uses an
internal pull-down. The backlight line's pull-down, R11, is 4.7 kΩ, under the 8.2 kΩ the erratum
asks for.

## Parts at JLCPCB

From JLCPCB's parts search on 2026-10-28. Prices are for one piece and for 100.

| part | LCSC | tier | stock | 1 | 100 |
|---|---|---|---|---|---|
| RP2350A | C42411118 | Extended | 5,521 | $1.30 | $1.13 |
| W25Q128JVSIQ | C97521 | Basic | 66,073 | $2.58 | $1.78 |
| ABM8-272-T3 | C20625731 | Extended | 2,147 | $0.66 | $0.43 |
| AOTA-B201610S3R3-101-T | C42411119 | Extended | **6** | $0.36 | |
| CH343P | C2846043 | Extended | 12,867 | $0.98 | $0.68 |
| ATECC608C-SSHDA-T | C28975195 | Extended | 3,972 | $1.75 | $1.15 |
| XC6206P332MR | C5446 | Basic | 533,724 | $0.15 | |
| USB-C TYPE-C-31-M-12 | C165948 | Extended | 292,653 | $0.19 | |
| USBLC6-2SC6 | C7519 | Extended | 40,704 | $0.18 | |
| ZIF 0.5K-HX-8PWB | C2919492 | Extended | 15,695 | $0.10 | |
| 27 Ω 0402 | C25100 | Extended | 43,619 | $0.001 | |
| AO3401A, SS8050, LED, buttons, the other passives | | Basic | | | |

**About $8.70 of parts a board** at one-piece prices, and about $6.60 at 100. The panel is bought
separately (about $2.50) and clipped into J2 by hand.

**Nine Extended parts, each about $3 a JLCPCB order.** The 27 Ω pair serves only the bench USB on
J3. A Basic 22 Ω would save $3 an order, a little off Raspberry Pi's value.

**L1 is the risk.** JLCPCB has 6 of Raspberry Pi's polarity-marked inductor. Raspberry Pi says its
regulator needs this part, the right way round, in their layout. Before ordering, check the stock,
and plan to pre-order or send our own if it's still short. Its footprint is Raspberry Pi's, from
their minimal design, turned as theirs is.

## The board

72 × 36 mm, two layers, every part on top, ground poured on both sides.
- The panel's glass lies on four 2 mm foam pads at the top left. Under it are only J2, the
  backlight switch and 0402s. The generator checks their heights and keeps them off the pads and
  out of the ribbon's path.
- D0, D1 and D2 sit in a row under the glass, each under the middle of its footer slot.
- The RP2350 is right of the glass. The flash is above-left of it, where its QSPI pins are; the
  regulator is above-right, where VREG is; the crystal is below.
- The CH343P sits between the RP2350 and the USB-C on the right edge.
- The key, RESET, BOOTSEL and the LED are along the bottom; J3 is along the top.
- The silkscreen: a warning triangle and EXPERIMENTAL HARDWARE COSIGNER over the glass, and the
  name under it. On the back: the revision, **picoquorum.dev** and the licence, which names it as
  the Source Location.
  console-s3's 8-bit key (a nod to Adventure) sits beside U5, the key that signs, pointing at it.
  Its dragon is the Easter egg: under the glass, below the ribbon's path, turned to face the key.
  Pixels are 0.4 mm for the key and 0.3 mm for the dragon, so every gap is at least twice JLCPCB's
  0.15 mm.

### The panel

The panel is the common 8-pin 1.14″ ST7789V with a plug-in ribbon. Sellers call it NFP114H-03AF
(printed on the ribbon), NFP114H-03D, N114-2413THBIG09-C08 or Y114-2413THBIG09-C08. YIYANG's
datasheet for the Y114 (rev A, 2020) gives:
- pins 1 LEDA, 2 GND, 3 RESET, 4 RS, 5 SDA, 6 SCL, 7 VDD, 8 CS, at 0.5 mm, the same as J2;
- glass 31.0 × 17.6 × 1.6 mm, with a 23 ± 0.3 mm tail;
- one white LED, its cathode grounded inside, 2.9 to 3.1 V at 20 mA; VDD 2.4 to 3.3 V.

On 2026-10-29 two panels (Walfront's "ST7789V LCD Display Module 1.14 Inch ... Inline Type 2Pcs")
were checked by hand:
- the tail is 23 mm;
- pin 1 is on the side the board expects. With the glass face up and the ribbon leaving its right
  end, pin 1 is nearer the bottom edge, as on the datasheet's drawing. The fold under the glass
  keeps it there, and that is where J2's pad 1 (LEDA) is.

What follows from the datasheet, none of it a change to the board:
- **The ribbon loops, it isn't creased.** The datasheet's tight fold ends 21.0 ± 0.5 mm in from
  the glass's edge, but J2 is about 18.2 mm in. The spare ribbon makes a looser loop, about
  1.5 to 2 mm past the glass's right end by the drawing (not measured). Nothing on the board is
  there; a case needs room for it. console-s3 put its J2 for the tight fold; this board and
  console-usb didn't.
- **The top-right foam pad goes 2.5 mm in from the corner.** At the corner it would sit on U6's
  pins 3 and 4.
- The glass is 0.6 mm wider than the generator's 17.0, which is still the probots listing's figure.
  The extra 0.3 mm each side meets the silkscreen corners and covers nothing new.
- The active area is 1.4 mm off-centre, away from the ribbon. So each button sits 1.4 mm right of
  the middle of its footer slot, well inside the slot's 8 mm.
- R8's 22 Ω gives about 12 to 22 mA, by the datasheet's Vf and a 3.3 V rail within 2%. The high
  end is just past 20 mA. Dim it with PWM, or fit 27 Ω (parts list only) if it runs bright.

Other 1.14″ panels to avoid: the 13-pin N114-2413THBIG01-H13 (another pinout), the solder-type
ribbon, and modules on a small board with a 2.54 mm header (GND on pin 1).

### Round the RP2350: Raspberry Pi's layout

Raspberry Pi says to copy its minimal design's layout, so the board does. `rpi_minimal.py` reads
their KiCad files (MIT, [lib/RPI-MINIMAL-LICENSE.txt](lib/RPI-MINIMAL-LICENSE.txt)) and writes
their footprints for the chip, L1, the crystal and the 0402s into `lib/pqrp.pretty`, and
`rpi_minimal.json`: where each of their parts sits from the chip's centre, their power copper (the
regulator's pours, the rings under the chip, the DVDD and 3V3 tracks and vias), and their crystal's
corner (its lines, ground vias and pour). The generator puts the same
parts at the same places round our U1 and copies their copper, locked. Where ours differs:
- **0.3 mm holes**, not their 0.25: JLCPCB's base price, and our vias'.
- **Their C12 (our C14) moved.** It sat where our flash's lines run; ours is above the USB
  resistors, beside C17.
- **The flash is 1.9 mm nearer the chip,** so its six lines are drawn by hand, as theirs run.
- **Their 27 Ω pair (our R13, R14) is turned round,** as our symbols have the chip on pin 1.
- **Their two ground vias by C1 and C2** were 0.05 mm from those pads' mask openings, where solder
  runs down. The one by C2 moved 0.15 mm out; the one by C1 had no room to move and is left out. C1's
  ground pad reaches the other by a track, and the pour.
- **Our front pour is ground, theirs 3V3,** and it stays out of the regulator's corner, where it
  left scraps between their pours.
- **The back under the chip** is a keep-out for the router, but for their four DVDD tracks, and so
  is the back under the crystal and its capacitors, which on theirs is only ground.

The generator checks the routed board for any other net's copper in their regulator corner or
their crystal's corner, or under the chip or the crystal on the back.

### Routing

Some lines are drawn by hand in `gen_console_rp.py` and locked, because the router left them open
or necked them down: the flash's six, its 3V3 from pin 54, the bench USB to J3, the key's bus out
from pins 7 and 8, SWD and RUN out from pins 24–26, and a few short ties and vias. C17's ground and
the CH343P's exposed pad each get a via the pour can't give them: C17's beside its pad, the
CH343P's in its exposed pad, since its pins shut it in.

`tools/keypcb route console-rp` routed the rest with Freerouting 2.5. The Ground class isn't
routed: the pours and 163 ground vias join it. Tracks are 0.2 mm, 0.25 for power and ground, the
least 0.15. The route isn't the same each run, so after it the board was put right in place, not
routed again: the ground vias the route's tidy-up had put inside C17's and the CH343P's pads went
(it now keeps 0.45 mm from pads), D+ moved out for C17's via, and a few track ends went onto their
vias' centres. The generator draws all of it the same way for the next route.

Then Raspberry Pi's crystal corner was copied (2026-10-29), which moved U5 2 mm down, C23 up-left of
its pin 8, and R6 and R7 round so their 3V3 pads face pin 8. The board was placed again, the old
route carried over locked wherever the move left it whole, and the rest routed: the crystal's
lines are theirs, and SDA, SCL, the LED and BOOT_SW were routed again whole. For that route only,
a keep-out over the crystal's corner kept the router out of it.

![The board with the panel lifted off: under the glass, the ZIF, the backlight switch and, below the ribbon's path, the 8-bit dragon facing the key by U5](renders/console-rp-under-glass.jpg)

## What is checked, and how

`tools/keypcb gen-console-rp` (add `render` for the pictures) writes everything from the one table
in `gen_console_rp.py`, then checks it. It won't overwrite a routed board: `tools/keypcb
gen-console-rp check` checks the routed one as it is. Both run:
- **KiCad reads the schematic back.** Its netlist must match the table, net by net.
- **ERC:** 0 errors, 0 warnings.
- **The link's wiring rules** (above), from the netlist.
- **Every symbol pin has a pad** in its footprint, and every pad a pin.
- **Each GPIO's function** (UART1, I2C0, SPI1) against the RP2350's table, and the screen's and
  key's pins against `firmware/board.py`.
- **DRC on the routed board.** Allowed: J1's and J3's footprints differ from the library (J1's
  silkscreen past the edge left out; J3, not fitted, has holes only), and the glass's outline over
  U6's pads.
- **Raspberry Pi's areas:** no other net's copper in their regulator corner or crystal corner, or
  under the chip or the crystal on the back.
- **Under the glass:** each part's height and place.

`tools/keypcb fab console-rp` writes the files to upload: `console-rp-gerbers.zip`, `bom.csv` and
`cpl.csv` in [console-rp/fab/](console-rp/fab/). `tools/keypcb jlc console-rp`
([tools/jlc](../../tools/jlc/README.md)) passed every check on 2026-10-29: DRC at JLCPCB's limits,
the Gerbers and drills read back, the netlist, the BOM and CPL against LCSC's parts, mask and paste,
holes, pours and the 3D fit. Its self-test caught 10 of 10 broken copies. What its spec
(`jlc_spec()`) lets through, each with why:
- 30 DRC and parity findings: Raspberry Pi's footprints and the ZIF don't match the stock symbols'
  footprint filters, U1 is an SMD part with holes in its pad, J1's and J3's footprints as above,
  J3 and the panel have no courtyard, and the glass's outline over U6.
- U1's nine thermal-via holes are held to the vias' ring (0.15 mm), not a component hole's 0.2.
- The one via in the CH343P's exposed pad.

Its warnings: J3's 3V3 hole is joined to the pour solid, so slow to solder by hand;
U3 runs about 82 °C over the air at 0.12 A on the datasheet's SOT-23 figure (34 °C at 0.05 A).

Not checked:
- L1's footprint (Raspberry Pi's) against Abracon's land pattern;
- the 3D fit's guessed sizes: the foam, the ribbon's loop, and how high U6's leads rise;
- anything on a real board.

An outside review on 2026-10-29 found these, all left as they are for the first boards:
- USB D+ and D- between J1, U2 and U4 have ground under 75% and 48% of their tracks. D- crosses
  to the back on three vias. At full speed (12 Mb/s) 20 mm of track is electrically short.
- VBUS has 11 µF on it, C18's 10 µF and C20's 1 µF. USB asks for at most 10 µF; C18's comment
  counts only itself. A 4.7 µF C18 would fix it with no copper change.
- C14 (pins 53-54) is about 8 mm of track from them, against Raspberry Pi's 4.5 mm. Those pins
  also meet the 3V3 ring under the chip and its six 100n capacitors.
- U3's heat (below, under Open) needs a measurement.

## Steps to a board

1. **Panels:** two bought and checked by hand on 2026-10-29 ([The panel](#the-panel)).
2. **Order it:** upload the zip, BOM and CPL; Economic, one side, qty 5. Check L1's stock. Hold
   `fab/check/cpl-overlay.png` beside JLCPCB's placement preview, L1's dot above all.
   JLCPCB's RP2350 design guide asks for Raspberry Pi's layout, the AOTA inductor with a silkscreen
   mark for its way round, and the ABM8-272-T3: the board has all three. Its offer of a review
   with Raspberry Pi means sending them the files; we don't.
3. **Bring one up:** 3.3 V first. Hold BOOTSEL, press RESET, and copy the Pico 2 MicroPython image
   over J3's USB (or use SWD). Then bench scripts for the screen, buttons and key.
4. **The firmware and the relay.** A `console-rp` profile: the QT Py's footer screens at 240 × 135
   (`claude/qtpy-cosigner`, PR #91), these pins, and the link on UART1. The relay is a new network
   path and part of the app, so it needs a yes before it's built.

## Open

- [ ] L1: Abracon's part in stock, or a tested substitute.
- [ ] U3, the XC6206: about 82 °C over the air at 0.12 A by the datasheet's figure. The board
  draws less, but a measurement would say.
- [ ] The relay: a Web Serial page in the app, a command-line tool, or both?
- [ ] The 27 Ω pair: keep, or a Basic 22 Ω?
- [ ] A case, and the Sign button's guard.
- [ ] picoquorum.dev, printed on the back, must lead to the site and the source before boards ship.
  Today the site is at picoquorum.app (`docs/CNAME`), and .dev doesn't reach it.
