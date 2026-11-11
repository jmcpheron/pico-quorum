# console-rp rev B: the square (2026-11-05)

A plan for the next console-rp board: the same circuit as rev A, moved onto a square-ish board with
the USB-C at the bottom, room for a key port at the top, the flash clear of the glass, and the hooks
a run of 100 to 250 needs. Rev B is a proof of it, 5 to 20 boards. Rev C is the run. Like the
console-rp plan, it's a plan to argue with. Decisions are marked **Decide**.

## The brief, in one paragraph

Keep what works: the RP2350A with no radio, the CH343P as the only thing the USB-C reaches, the
ATECC608C on I2C0, the 1.14″ panel in its ZIF, D0 D1 D2 in a row under the screen, every GPIO as
tonight. Change the shape: a square, not a stick, so it reads as its own thing and sits in a dock
like a badge. Fix the one crowding on rev A: the flash's pads under the glass's top-right corner.
Put in now what a run needs and a board of five doesn't: test pads for a jig, fiducials, a board
that goes into the jig and the case one way only, a part census on the silkscreen, and the name on
its face.

## What doesn't change: the wiring

Rev A's netlist is rev B's netlist. Every net, every GPIO, every part number, with a few
value-only swaps listed below. The generator makes this checkable: `tools/keypcb gen-console-rp`
reads KiCad's netlist back against its table, net by net, and writes `PINS.md`. **The test is that
`PINS.md` doesn't change**, and the firmware's `console-rp` profile runs on rev B without an edit.

What that means for the layout:

| moves freely | why |
|---|---|
| D0, D1, D2, RESET, BOOTSEL, the LED | three nets each, no timing |
| the key chip and its two pull-ups | I2C at 400 kHz; 40 mm of track is nothing |
| the USB block: J1, U2 (ESD), U3 (LDO), U4 (CH343P) and their caps | it's a cluster already; the UART is two lines to U1's right side |
| J2 and the backlight switch | they follow the glass |
| J3 | pads now, holes if wanted |
| the outline, the holes, the silkscreen | |

| moves as one piece, not rotated | why |
|---|---|
| U1 and Raspberry Pi's parts round it: the regulator corner (L1, C1–C3, R1), the crystal corner (Y1, C15, C16, R2), the 100n at each power pin, R13/R14 | their copper is copied from Raspberry Pi's design and placed from U1's centre (`rpi_minimal.json`). Moving `AT["U1"]` moves all of it. Rotating it means rotating that copy, which the generator doesn't do today |
| the flash U6, C17, R3 and the six hand-drawn QSPI lines | drawn from U1 in board mm (`gen_console_rp.py`, "The flash's six lines"); they move with U1 if they're made relative to it, a small edit |

So the block round U1 keeps its orientation: screen side (GPIO 2–13, pins 4–17) on its left, the
link (GPIO 20/21, pins 32/33) on its right, the flash above-left, the crystal below. The whole board
is laid out round that fact. The block is about 18 × 28 mm (x from U1 − 10 to U1 + 8, y from
U1 − 13.5 to U1 + 14.7, the crystal's corner included).

## The shape

**58 × 54 mm.** Not a perfect square: the chip block beside the screen needs the width, and 1.07:1
reads as square in the hand. Two-layer, every part on the front, as rev A.

```
      0        10        20        30        40        50   58
    0 +---------+---------+---------+---------+---------+--\
      |  [key port zone, empty on rev B]  EXPERIMENTAL ...   \   <- top-right corner cut 6 mm
      |  +-------------------------------+   U6 flash       |
    7 |  |                               |~  C14 R13 R14    |
      |  |      glass 31 x 17.6          |~    +--------+   |
      |  |      active 240 x 135         |~    |  U1    | L1|   <- Raspberry Pi's block, as rev A
      |  |                               |~    | RP2350 |   |
   24 |  +-------------------------------+     +--------+   |
      |        Picoquorum console-rp              Y1        |
   31 |     (D0)      (D1)      (D2)         . . crystal    |
      |                                                     |
      |       o   mark  o          U5 key   U4 CH343P  U3   |
   44 |      (RESET) (BOOTSEL)   8-bit key   C20-22    LDO  |
      |   J3 pads (back)  LED      U2 ESD  [ USB-C J1 ]     |
   54 +-----------------------------------------------------+
                                            cable out of the bottom
```

| zone | where (mm, from the top-left, y down) | what |
|---|---|---|
| the top band | y 0–7 | the warning text; at the left, x 0–16, nothing: the key port's zone (below) |
| the glass | x 3.5–34.5, y 7–24.6 | the panel as rev A: 2 mm foam, the tail looping out of its right end to about x 37, J2 under it |
| the chip block | U1 at about (48, 19.5) | the flash's nearest lead at x 37.9: **3.4 mm from the glass**, against about 0.4 on rev A. The ribbon's loop (y 13.5–18) passes under the flash's row, not through it |
| the buttons | y 31; x 9.35, 17.55, 25.75 | `slot()` as rev A: under the footer's three slots, 1.4 mm right of the glass's centre line, so the firmware's footer lands on them |
| the name | y 27.5 | between the glass and the buttons, as rev A |
| the mark | x 20–36, y 36–50 | RESET and BOOTSEL are its two lower dots, 7.5 mm apart, as the slate case draws them (`cad/consoles/rp.py` stops if they aren't). The mark is then 6.4 mm in radius with its top dot 11.5 mm above them |
| the key | U5 at about (38, 40) | below U1's left side, a 25 mm bus to pins 7 and 8; the 8-bit key on the silkscreen points at it. Or at the bottom-left, on show, under the mark. **Decide**; it's placement only |
| the USB block | J1 on the bottom edge at about x 46; U4 at (46, 41); U2, U3 beside | the cable leaves the bottom. The UART runs 20 mm up to pins 32 and 33 |
| J3 | the bottom-left, on the back | pads for pogo pins (below). The bench's 1×8 holes can stay on the front edge for the 5 to 20; drop them at rev C |
| the holes | four M2.5, one near each corner, the top-right one tucked in under the cut | the slate's shell layout: screws from the front into bosses on the back panel |
| fiducials | three 1 mm copper dots, in three corners, none in the cut one | Standard assembly wants them; Economic doesn't mind them |

**The USB-C at the bottom, not the top or a side.** The top is the key port's (next section). A side
puts the cable under the hand that holds the board. The bottom puts it where a phone's is: in a dock
it drops straight into the dock's slot, as the badge's dock already does, and on a desk the cable
runs away from the thumb that's on Sign.

**One corner cut.** The top-right corner is chamfered 6 mm. That's the asymmetry: the board goes into
the test jig and the case one way only, a person tells top from bottom across the room, and with the
holes already not mirror-symmetric (rev A has H3 at y 9 and H4 at y 33) two holes make locating pins
for a fixture. In the SMT line itself the panel's fiducials set orientation, not the outline; the
cut is for the jig, the case, and the eye. It's also the brand's shape, so the case follows it.

**The key port's zone.** The PicoquorumKey rev B has a key port: a USB-C plug standing out of the
board's top-left, on I2C1, with a load switch, a CC sense and an enable, its power off until the
firmware turns it on (`hardware/picoquorum-key/docs/DESIGN.md`, "The key port"). The console-rp can
carry the same one later: an interchangeable key is a key-c on that plug, like a cartridge. Rev B
doesn't fit it, but reserves for it:
- the top-left 16 × 7 mm, empty, where the plug straddles the edge (8.4 mm wide, 9.6 out);
- GPIO 18 and 19 for I2C1, GPIO 22 for the enable, GPIO 26 (ADC0) for the CC sense: four of the
  pins rev A leaves unconnected. Nothing is wired to them on rev B;
- the case's notch, as the badge's, open from the top edge.

That's why the glass starts at y 7, not 4.5, and the board is 54 tall, not 52. The port variant is
then the same board with eight parts added, not a new layout. **Decide:** reserve it (this plan), or
make rev B 52 tall and give the port its own board later.

## Branding, on the board and on the case

- **The mark on the face,** in the silkscreen for the five: `lib/picoquorum.pretty` already has
  `PicoQuorum_Mark.kicad_mod`. For the run, the mark in exposed ENIG copper under the mask: gold on
  green, two colours from one process, and a tamper-visible one (a sticker over it shows).
- **The name under the screen** as rev A, written Picoquorum and on one line (`docs/BRAND.md`), and
  the warning line above it until the terms say otherwise. On the back: the revision, the part
  census (below), the expected current, picoquorum.app as the Source Location. The back's
  `picoquorum.dev` is rev A's open item; print the name that resolves.
- **The 8-bit key and the dragon** stay: the key by U5, pointing at it; the dragon under the glass.
- **Mask colour. Decide.** Matte black is the brand's Night and hides traces; green is the clearest
  over copper, the tamper-visible concept's choice, and JLCPCB's cheapest. For the 5 to 20: green,
  and let the case carry the colour. Reopen at rev C.
- **The case** does the colour work: the slate's badge (the triangle green, the signed dots blue, the
  waiting dots orange, glued into a pocket), the caps in Reject red, white and Sign green, the name
  on one line, cut through to a second colour. All drawn in `rp.py` already; it moves to the new outline.

## What a run of 100 to 250 needs, designed in now

| hook | on rev B | why now |
|---|---|---|
| **test pads on the back** for a pogo jig: GND, 3V3, SWCLK, SWDIO, RUN, D+, D− | yes | loading is through SWD (`bench/BRINGUP.md`, "Loading boards in numbers"); RUN lets the jig reset a board without SWD. 1.5 mm pads at 2.54, in a row, no part within 2 mm. The jig's locating pins go through two of the M2.5 holes |
| **fiducials** | yes | Standard assembly's panel needs them; they cost nothing |
| **a panelisable outline** | yes | 58 × 54 goes 2 × 2 in a 70 × 70-plus panel with mouse bites; the cut corner rules out V-cuts on that edge, mouse bites don't care. JLCPCB panelises on request |
| **the census and outlines** from the rev B concept (`claude/console-rp-concept`, round 1) | yes | written by the generator from `PARTS`, so it can't go stale. Cheap, and it's the owner's check |
| **"nothing is fitted on this side"** on the back | yes | one line |
| **the current label** by the USB-C | yes | the USB meter is the radio detector |
| **the slate on the new outline** | yes | print its face first and lay it on rev A's parts list, before the board is ordered: the 1:1 check the console-rp plan asked for |
| the factory-soldered panel | no | the concept's big move. The 100 ER-TFT1.14-2 panels on order are hand-fit panels; check one in J2 on rev A first. **Decide** at rev C |
| secure boot and the SWD lock | no | try on rev A board #2 first; both are one-way |
| the key port fitted | no | the zone is reserved |

**Value-only swaps,** no copper change, each a line in `PARTS`. **Decide** each:
- C18 10 µF → 4.7 µF: VBUS then carries under USB's 10 µF (the outside review).
- R8 22 Ω → 27 Ω if the backlight runs bright on rev A.
- R13, R14 27 Ω → a Basic 22 Ω: $3 an order off, a little off Raspberry Pi's value. Only J3's USB
  uses them, and J3's USB hasn't worked yet.
- U3, the XC6206: measure it on rev A at full brightness first. If it runs hot, an AP2112K-3.3
  (SOT-23-5) is a footprint change and a new line, the one swap here that touches wiring.

**Layout fixes while the board is open,** from the review of rev A:
- USB D+ and D− with ground under their whole length, no layer change: the block moves anyway.
- C14 nearer pins 53–54.
- L1's way round on the silkscreen, as JLCPCB's RP2350 guide asks.

**Supply, the real risk for 250.** JLCPCB had 6 of Raspberry Pi's inductor (AOTA-B201610S3R3-101-T)
and the order took them. Before rev C: a reel pre-ordered or consigned, or a substitute tested on a
rev B board with the core supply measured (rev A's 1.4 V reading, understood first). Pre-order the
ATECC608C (3,972 in stock, 1 a board) and the RP2350A at the same time.

## The steps

**0. On rev A, this week.** Nothing here needs rev B.
- Measure: the core supply (the 1.4 V), U3's temperature, the backlight's current, the switch
  height, a cable's overmold. The case scripts take these as numbers.
- Clip an ER-TFT1.14-2 into J2 and compare it with the Walfront panel: tail length, pin 1, glass.
- The `console-rp` firmware profile and the link on UART1, from the console-rp plan. Rev B's
  footer is the same screen on the same pins.

**1. The generator.** Edit `gen_console_rp.py` in place; it writes the schematic, the board, the
pictures and `PINS.md`, and checks them.
- `W, H`, the cut corner in the outline writer, the holes, the fiducials, the back pads.
- `GX0, GY0` for the glass, `BY` for the buttons; `slot()` as it is.
- `AT["U1"]`, and the flash's lines made relative to U1.
- The USB block, the key, RESET, BOOTSEL, the LED, J3, the mark.
- The silkscreen: the census and outlines brought over from the concept branch's round 1.
- Then: `tools/keypcb gen-console-rp` (the netlist against the table, ERC, the link's wiring rules,
  each GPIO's function), diff `PINS.md` against rev A's: empty. `tools/keypcb route console-rp`,
  put right by hand as rev A was, `gen-console-rp check`, `tools/keypcb jlc console-rp`.

**2. The case.** `rp.py` on the new outline: the USB opening in the bottom wall, the notch for the
port's zone left closed on rev B (a line in the script), the dock's slot at the bottom as the
badge's. Build it, print the face, lay it on a rev A board's parts and on a 1:1 print of the new
board. Fix the numbers that were guesses.

**3. Quote and order.** Five on Economic as rev A was (about $33 a board), or twenty on Standard
(about $45 an order over Economic, the panel and its fiducials needed). **Decide** when rev A has
signed a testnet transaction end to end, as the console-rp plan says. Check L1's stock the day of
the order.

**4. Bring-up on the jig,** not on jumper wires. The jig is rev B's second deliverable: pogo pins on
the back pads, the USB-C in it, `swdload.py` and `stage0.py` as `BRINGUP.md` describes. Every rev B
board goes through it, and that's the rehearsal for 250.

**5. Rev C is rev B with the answers:** the panel decision, the inductor's source, the LDO, the
Basic-part swaps, the locks, the port variant if wanted, and the back silkscreen's final text. If
rev B's layout holds, rev C is a parts list and a silkscreen, not a layout.

## What this plan doesn't settle

- **The chip block isn't rotated.** A true portrait board, screen above the chip and the link
  straight down to the USB-C, wants the block turned 90°. That's a generator change (rotate the copy
  of Raspberry Pi's copper and the checks that read it) and a route nobody has looked at. The
  58 × 54 layout above gets the square without it. If the look isn't square enough, that's the
  next lever, and the first thing to try on a branch.
- **Switch choice.** Rev A's tacts are fine for five. For 250, pick the switch the case's caps are
  drawn for and its height measured, once, before rev B's order: the caps and the plate follow it.
- **Nothing here is secure or audited.** It's the same circuit on a different outline, with the
  same open items: the Sign button's guard, the relay's rules, the panel in someone else's hands.
