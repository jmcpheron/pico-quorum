# pico-sign-handheld: pico-sign, flat, with the 2.4″ screen

| | |
|---|---|
| board | a Pico 2 W (castellated), wires soldered to its pads: no headers |
| key | a key-c in [a clamshell](#the-keys-clamshell): two halves that snap shut, plugged straight down onto a USB-C plug in the top edge |
| runs | the console image as `BOARD = "build1"`, `SCREEN = "2.4"`, unchanged; `firmware/bench1.py` first |
| case | [the handheld](#the-case-the-handheld): a tub and a front plate, 86 × 118 × 30 mm, M3 into heat-set inserts |
| status | written up 2026-11-02; not printed, not wired, not run. The 2.4″ has not been seen working |

[pico-sign](../pico-sign/README.md) again, smaller. The same knob, the same hold-to-sign switch and the
same pins, with the 2.4″ screen in place of the 2.8″, in a flat case you hold in two hands like a
handheld game, or lay on the desk. The screen is across the top half. Under it the knob is on the left
and the sign switch on the right, each sunk in a well; the sign switch has a flip cover. The key, in a
snap-shut clamshell, stands up out of the top edge.

![the handheld](case/out/handheld_front.png)

## What is different from pico-sign

- **The screen** is the 2.4″ 240 × 320 SPI module with 8 pins, the one pico-sign started with:
  `SCREEN = "2.4"`.
- **The case** is the handheld, not the prism: 86 × 118 × 30 mm against the prism's 180 × 107 × 78.
- **The Pico lies on the tub's floor**, between the knob and the switch, its USB out of the bottom edge.
  On the prism it hangs behind the screen.
- **No headers.** The case leaves 4 mm over the Pico's board, so the wires are soldered to its pads.
- **A short sign switch.** 20 mm under its head, not the 28 mm the prism allows. See
  [the sign switch](#the-sign-switch).
- **The controls are sunk in wells**, and the sign switch has a [flip cover](#the-sign-switchs-cover).
- **The key's case is a clamshell** that snaps shut, not pico-sign's cartridge, which is glued or
  screwed. Same outside, so either fits either build.

Everything else is pico-sign's.

## Parts

- a Pico 2 W
- the 2.4″ IPS 240 × 320 SPI screen, 8 pins (VCC, GND, SCL, SDA, RST, DC, CS, BLK)
- an EC11 knob with push, 20 detents, a 6 mm D-shaft, an M7 bushing, and a cap about 18 mm across
- the sign switch: a 12 mm metal push switch, **momentary**, normally open, short-bodied
- a key-c, and a USB-C plug on a short cable for it, as on [pico-sign](../pico-sign/README.md#the-key)
- two 4.7 kΩ resistors, the key's pull-ups
- thin stranded wire, about 12 cm a lead
- for the case: [the hardware](#the-hardware)

## The wiring

**The same pins as pico-sign.** Every table is in [pico-sign's README](../pico-sign/README.md#the-wiring):
the screen, the knob, the sign switch, the key and its pull-ups. Every signal is on Build 1's pin, so
the console image runs unchanged. `python3 hardware/builds/pico-sign/wiring.py --check` checks those pins
against `firmware/board.py`; it is not a different build there.

What changes is how the wires go:

- **Solder them to the Pico's pads.** There is no room for headers or Dupont housings.
- **Make each lead about 12 cm.** The screen, the knob and the switch are on the plate; the Pico and the
  key's plug are in the tub. Long leads let the plate lie face down beside the tub while you wire it.
- **The Pico's far end is under the carrier's edge**, 1.8 mm over the 4 mm the script leaves for wires.
  That is pins 19 to 22. Pin 20 (GP15, the sign switch) is wired there: lead its wire off the board's
  side, not straight up.
- **The screen's header.** Solder the leads to its pins at the back. The case leaves 11.5 mm behind the
  board for pins and wire.

## The screen

`SCREEN = "2.4"`, with `BOARD = "build1"`, in the board's `secrets.py`. `firmware/board.py` drives the
2.4″ the same way as the 2.8″: an ST7789, 240 × 320, run landscape as 320 × 240.

**Not seen working.** pico-sign started with this screen and never got a picture from it. It may be an
ILI9341, not an ST7789. That needs inversion off, which is a firmware change. Try `bench1.py` first
(below).

**The header is on the left** (seen from the front), at the screen's left end. That is how build1 draws
the 2.8″ the right way up (`MADCTL = 0x60`). If the 2.4″ comes up upside down this way, the fix is
`MADCTL`. That is a firmware change and a new release fingerprint (AGENTS.md); it isn't made. The other
fix is in the case: `HEADER_SIDE = 1` in `handheld.py` moves the carrier's notch to the right. The
screen's posts don't change.

## The sign switch

**It must be momentary.** A latching switch would sign 2 s after one tap, with nobody holding it.
[pico-sign's README](../pico-sign/README.md#the-sign-switch) says why, and how to meter one.

**It must be short.** The case is 30 mm thick, and the switch hangs behind the plate. The script
takes a switch 20 mm long from under its head to its lugs' tips, and prints how long one fits: up to
23.1 mm. The pedal switches the prism allows for (28 mm) don't fit. 12 mm "anti-vandal" metal momentary
switches are often about 20 mm long under the head. That is not measured.

**Its head must be low.** It sits in a well under the cover. The script takes a head 15 mm across and
2.0 mm tall over its flange's underside, with 0.4 mm between it and the cover. Measure yours, set
`SIGN_HEAD` and `SIGN_DEPTH`, and run the script again: the well's depth follows the head.

## What the controls do

The same as pico-sign: [the table](../pico-sign/README.md#what-the-controls-do). Turn for pages and
rows, push to open, hold the sign switch to sign (every page seen first, 2 s, 3 s on a red page). The
knob's push on the Sign row, held, signs too.

## First: the bench check

As on [pico-sign](../pico-sign/README.md#first-the-bench-check), with `SCREEN = "2.4"`.
`bench1.py` only reads the chip. Leave its `JACKS = False`.

Look for TL at the top left and the bars red, green, blue, white. If the colours are a negative,
`INVERT = False` at the top of `bench1.py`; if that fixes it, the panel is likely an ILI9341 and the
console image needs that change too (not made).

Then the console as usual. The key must be provisioned already. Nothing in this build writes or locks a
chip.

## The case: the handheld

[`case/handheld.py`](case/handheld.py), CadQuery. A first draft to print and try.

```sh
tools/case build handheld     # handheld.py; `tools/case check handheld` says what changed
```

Flat and portrait, 86 mm wide, 118 tall and 30 thick, corners rounded 6 mm. The bottom right corner,
under the sign switch, is rounded 20 mm. The back's edge is rounded 3 mm and the face's chamfered 1.5 mm.
With a key in, it is 164 mm tall.

**Seven printed parts, and the key's two:**
- **The tub**, one piece, open at the face. It prints on its back. In it:
  - four posts at the corners, an M3 insert in each, for the plate's screws
  - four posts for the Pico, M2 screws cutting their own thread
  - the key's plug holder at the top edge
  - a 14 mm square hole in the bottom edge for the Pico's cable
  - four pockets 1 mm deep in the back for rubber feet
- **The plate**, 3 mm, printed face down. Four M3 countersunk screws hold it to the tub's posts.
- **The carrier**, 2.5 mm, behind the screen. It is the prism's, without the Pico.
- **Four spacers**, 4 mm tubes that slip onto the screen's pins.
- **The plug lock**, which holds the key's plug up. It prints on its side.
- **The guard's base and cover**, for the sign switch. The base prints as it sits, the cover face down.
- **The key's tray and cover**: [the clamshell](#the-keys-clamshell).

**On the plate:**
- the screen's window across the top, bevelled, 2 mm bigger than the active area
- on the back, the prism's screen mount. A post at each of the screen board's holes is a seat for the
  board, with a pin through it, the spacer and the carrier. Where the glass comes close, the seat is cut
  flat. Four 9 mm bosses above and below the screen, each with an M3 insert, take the carrier.
- the knob on the left and the sign switch on the right, 30 mm up from the bottom edge, each sunk in a
  well. The plate is thickened behind each well, 3 mm past its edge, so its floor stays thick:
  - **the knob's well:** round, 25 mm across and 3 mm deep, a 2 mm floor for the EC11's nut. The knob's
    cap stands about 12 mm out of the face, with 3.5 mm round it for your fingers.
  - **the sign switch's well:** the guard's outline, 20.6 × 24.6 mm, 6 mm deep, a 1.5 mm floor. A
    notch under its bottom edge is for a thumbnail, to lift the cover.
- a 20 × 6 mm frame under each, a 0.6 mm line cut 0.6 mm deep, for a label
- PICOQUORUM cut between the controls and the window: 7.7 mm letters, 65 mm long (the script works it out)

![the plate, front and back](case/out/handheld_plate.png)

### The sign switch's cover

![the guard, open](case/out/handheld_guard.png)

A flip cover over the sign switch, so it isn't pressed by accident. Shut, it is flush with the face. It
flips up toward the screen, and stops at 100°, where it rests on the well's edge.

- **The base** is a 2 mm plate, the well's shape, so it can't turn in it. It has a hole for the switch and
  a knuckle at each end of the hinge. The switch goes through the base and the floor. Its head clamps
  the base down, and its nut is behind the plate. No screws.
- **The cover** is 1.6 mm, with a knuckle between the base's two.
- **The pin** is a piece of 1.75 mm filament, 20 mm long, pushed through the three knuckles. It is tight
  in the base's (1.8 mm holes) and free in the cover's (2.0 mm). Trim it flush.
- Put the cover on the base before the switch goes in. The pin goes in from the side.

The cover stays shut by its own weight with the handheld flat, and by the pin's friction in your hands.
There is no latch.

### The key

The key plugs straight down onto a USB-C plug in the top edge, in the middle, near the back. As on the
prism, the plug is a cut cable's: its overmold, 12.4 × 5.5 × 17.1 mm (calipers), ends flush with the
edge in a hole with 0.2 mm round it, so only the metal shell stands out. The key's clamshell stands up
out of the top, its chip's window toward the face.

The plug's holder is the prism's, laid on the floor. Its channel is open toward the face, and so is the
slot for the cable in the stop at its foot. Putting the plug in:
1. Drop it into the channel low, the cable down through the stop's slot. The channel has 9.4 mm below
   the plug's final place, so its shell clears the top wall.
2. Push it up into the top's hole until the overmold is flush.
3. Drop **the lock** into the 9.4 mm under it, the cable in the lock's slot. Two bumps on the lock click
   into holes in the channel's walls. Its lip is to pull it out by.

### The key's clamshell

[`case/cartridge.py`](case/cartridge.py). Two halves that snap shut round a key-c. Each prints flat on its
outside face, with no supports. Same outside as pico-sign's cartridge: 22 × 46 × 7.56 mm, a keyed corner
and a lanyard hole.

![the key's clamshell](case/out/cartridge.png)

- **The tray** (the back) holds the board in a pocket 1.6 mm deep, the board's thickness. A 2.7 mm peg
  stands up through key-c's 3 mm lanyard hole, H1, so the board can't slide either way: plugging the key
  in pushes the board toward the grip, and pulling it off pulls the board toward the plug. A relief under the receptacle takes its shell tabs, which come
  through the board.
- **The cover** (the front) comes down on it. A rim 1 mm wide round the board's edge and a boss round the
  peg press the board flat. Inside, 2.2 mm over the parts and a pocket over the receptacle, open at the
  plug end. A window shows the ATECC608.
- **Four clips** stand up from the tray, two each side, beside the board. Each hooks 0.25 mm over a ledge
  in a window in the cover's side. Press the halves together and they click. To open it, push the four
  hooks in through the windows with a small screwdriver.
- The receptacle's face is flush with the plug end, so the plug goes all the way in.

**Not tried.** The clips are 0.8 mm thick and 5 mm long to the hook: about 1.7% strain to snap in, by the
usual cantilever sum. PLA takes about 2%, so PETG is the safer plastic. Print a pair and try it before the
key goes in. If the clips are loose, glue the halves.

key-c's numbers come from its board file: 16 × 36 × 1.6 mm, H1 3 mm at 14 mm from the centre, J1's
tabs at ±4.32 mm. The receptacle's front is taken to be flush with the board's edge: not measured.

### Inside

![the tub, open](case/out/handheld_tub.png)

**The Pico** lies on four posts on the floor, its USB end down, 6 mm up. Its posts are the prism's:
4.5 mm across at the far end, 3.6 mm at the USB end, so they keep clear of the pads beside each hole, of
the micro-USB plug and of the socket. It goes either way up. The cable comes in through the hole in the
bottom edge, which takes the plug whichever face its socket is on.

**Behind the plate**, the stack is the prism's: the screen board on its seats, a spacer on each pin, the
carrier, four M3 screws through the carrier into the bosses. The carrier is cut round the screen's header.

![behind the plate](case/out/handheld_carrier.png)

### The hardware

From the bench's kits (inserts are named thread × length × outside diameter):

| where | inserts | screws |
|---|---|---|
| the tub's corner posts, for the plate | 4 × M3\*6\*5, in 4.2 mm holes | 4 × M3 × 8 **countersunk**: not in the kit |
| the plate's bosses, for the carrier | 4 × M3\*6\*5, in 4.2 mm holes | 4 × M3 × 8 socket head, with M3 washers |
| the tub's posts, for the Pico | none: 1.8 mm holes, self-tapping | 4 × M2 × 8 socket head |
| the screen | none: four pins and four spacers | none |
| the feet | | 4 rubber strips, 6 × 35 mm |
| the guard's hinge | none | 20 mm of 1.75 mm filament |
| the key's clamshell | none: it snaps shut | none |

The insert holes and the 1.8 mm self-tapping holes are the prism's numbers, and neither has been tried.
Print one post and set an insert first.

### Putting it together

1. **The tub:** the four corner inserts. The key's plug and its lock, as above. The Pico on its posts,
   four M2 × 8. The micro-USB cable in through the bottom edge.
2. **The plate:** the four boss inserts. The guard: its cover on its base, the pin through, then the
   base into its well and the sign switch through both, its nut behind. The knob with its nut. The screen face
   down onto its seats, the pins through its holes. A spacer on each pin, the carrier on, four M3 × 8 with
   washers.
3. **The wires:** the plate face down beside the tub. The screen, the knob and the switch to the Pico;
   the key's plug to the Pico, its pull-ups at the plug ([pico-sign's tables](../pico-sign/README.md#the-wiring)).
4. **Close it:** the plate onto the tub, four M3 × 8 countersunk. The feet in their pockets.
5. **The key:** into its tray, the peg through H1; the cover on, pressed until the four clips click.
   Then straight down onto the plug in the top edge.

### What the script checks

That the boxes standing in for the screen's glass, board, back parts and header, the carrier's screw
heads, the switch, the knob, the key's plug, the clamshell, the Pico, the room for its parts and wires
on either face, and its USB plug don't overlap the tub, the plate, the carrier, the spacers, the plug
lock or each other. That the guard's base and cover clear the plate, the switch and the knob, with the
cover shut and opened 30°, 60° and 90°. 198 pairs, all clear. The closest:

| | mm |
|---|---|
| the Pico's USB plug to its posts and its cable hole | 0.2 |
| the Pico's posts to the nearest pin's pad, from the Pico's drawing | 0.21 |
| the USB end's posts to the micro-USB socket between them (a usual micro-B's, not measured) | 0.15 |
| the carrier to the tub | 1.0 |
| the plug lock to the carrier | 1.2 |
| the Pico's wires to the carrier | 1.8 |
| the guard's cover to the switch's head | 0.4 |
| the sign switch to the floor | 3.6 |
| the Pico to the sign switch | 3.5 |

It also checks that the bosses are deep enough for their inserts and the Pico's posts for their screws.
In the clamshell, that key-c, its parts and its tabs don't overlap either half, nor the halves each other
(U1 is 1.14 mm under the cover). It is not a fit check: the parts are boxes, and the screen's and the
switch's are placeholders.

**Overhangs**, with the tub on its back: six flat faces face down off the bed. They are all bridges:
- the four feet's pockets: 6.6 mm across, 1 mm up
- the top of the key's plug hole in the top edge: 12.8 mm across
- the top of the Pico's cable hole in the bottom edge: 14 mm across, its corners rounded 1.5 mm

With the plate face down, the wells' floors are bridges: the knob's 25 mm across, 3 mm up; the sign
switch's 20.6 mm, 6 mm up, its hole in the middle. The thumbnail notch's top is one too, 2.5 mm up. The
rest are the tops of the cuts for the name and the label frames, 0.6 mm up. Bridges of 20 to 25 mm print
on most printers; if yours sags, put supports in the two wells only.

### Before printing

- **Measure the screen.** None of its numbers is measured. The board (72 × 44 × 1.6 mm), the glass
  (60.3 × 42.7 mm, 3.5 mm from the board's front to the glass's front) and the hole spacing
  (66 × 38 mm, 3.2 mm holes) are placeholders. The board and the glass come from pico-sign's first
  wedge ([`case.py`](../pico-sign/case/case.py)), which guessed them. The active area, 48.96 × 36.72 mm,
  is a 2.4″ 240 × 320 panel's. If the glass sits off the board's centre, set `SCREEN_DX`, as the prism
  did. All of it is `SCREEN_*` at the top of `handheld.py`. The script prints how close the glass comes
  to the holes.
- **Measure the sign switch** (`SIGN_HEAD`, `SIGN_DEPTH`, above).
- **The key's plug** is the prism's: the cut cable's overmold, 12.4 × 5.5 × 17.1 mm. A different cable
  needs `PLUG_*` changed.
- **The Pico's plug:** a micro-USB overmold 11 × 8 mm is assumed (`USB_PLUG`).
- Print the plate first: every part's hole is in it.

| file in `case/out/` | what |
|---|---|
| `handheld_body.stl` | the tub, on its back, as it prints |
| `handheld_plate.stl` | the plate, face down |
| `handheld_carrier.stl`, `handheld_spacers.stl` | the carrier, face down; the four spacers |
| `handheld_plug_lock.stl` | the lock for the key's plug, on its side |
| `handheld_guard_base.stl`, `handheld_guard_cover.stl` | the sign switch's guard: the base as it sits, the cover face down |
| `cartridge_tray.stl`, `cartridge_cover.stl` | the key's clamshell, each half on its outside face |
| `handheld_assembly.step` | closed, with a box for each part |
| `handheld_*.png`, `cartridge.png` | the pictures here |

Not printed yet. The pictures are matplotlib's, and its shading is rough: it draws some faces from behind
through the plate.
