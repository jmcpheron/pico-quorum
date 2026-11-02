# pico-sign-handheld: putting it together

Sixteen steps, from printed parts to a key in the top. Each picture shows the step's new printed parts
in amber, what's already done in white, and what the step needs along the bottom. The pictures are
drawn from the case's own model ([`case/assembly.py`](case/assembly.py)), so they follow
[`case/handheld.py`](case/handheld.py)'s numbers. Nothing here has been put together yet: this is the
plan for the first build.

The wiring is in [pico-sign's README](../pico-sign/README.md#the-wiring), and what differs is in this
build's [README](README.md#the-wiring). This page only says where the wires go.

![everything, pulled apart](case/out/assembly/00-exploded.png)

## What you need

### Printed

All in `case/out/`, each the way up it prints.

| part | file | how many |
|---|---|---|
| the tub | `handheld_body.stl` | 1 |
| the plate | `handheld_plate.stl` | 1 |
| the carrier | `handheld_carrier.stl` | 1 |
| the spacers | `handheld_spacers.stl` (all four in one file) | 4 |
| the plug lock | `handheld_plug_lock.stl` | 1 |
| the guard's base and cover | `handheld_guard_base.stl`, `handheld_guard_cover.stl` | 1 each |
| the button cap | `handheld_sign_cap.stl` | 1 |
| the key's tray and cover | `cartridge_tray.stl`, `cartridge_cover.stl` | 1 each |

![the printed parts](case/out/assembly/00-printed-parts.png)

### Hardware

| what | how many | where |
|---|---|---|
| M3 heat-set insert, M3\*6\*5 | 8 | 4 in the tub's corner posts, 4 in the plate's bosses |
| M3 × 8 socket head screw | 8 | 4 for the plate into the tub, their heads in counterbores; 4 for the carrier onto the plate's bosses |
| M3 washer | 4 | under the carrier's screws |
| M2 × 8 socket head screw | 6 | 4 for the Pico, 2 for the guard's base. They cut their own thread |
| rubber strip, 6 × 35 mm | 4 | the tub's feet |
| 1.75 mm filament | 20 mm | the guard's hinge pin |

![the hardware](case/out/assembly/00-hardware.png)

### Bought

- the 2.4″ screen
- a Pico 2 W, no headers
- a 12 × 12 mm tactile switch, a mini breadboard (46 × 34.2 mm) and two flat jumper wires
- an EC11 knob, its nut, and a cap for its 6 mm D-shaft
- a USB-C plug on a short cable, for the key, and two 4.7 kΩ resistors
- a micro-USB cable for the Pico
- thin stranded wire
- a key-c

### Tools

- a soldering iron, with an M3 heat-set insert tip as well as its usual one
- hex keys: 2.5 mm (M3 socket heads), 1.5 mm (M2)
- a spanner or pliers for the knob's nut
- flush cutters, for the hinge pin
- a meter, for the switch's legs
- a towel to lay the plate on

## 1. The tub: an insert in each corner post

![step 1](case/out/assembly/01-tub-inserts.png)

The plate screws into these four. Set the iron to the temperature your inserts' maker gives for your
plastic. Sit an insert on the tip, square to the hole, and let it sink in under its own weight with a
light push. Don't twist. Stop when it is flush with the post's top, take the iron straight out, and let
it cool before you touch it.

The insert holes are 4.2 mm, not tried yet. If the first one goes in loose or won't go, stop: the hole
(`M3_INSERT` in `handheld.py`) needs changing.

## 2. The tub: the feet

![step 2](case/out/assembly/02-feet.png)

Peel each strip and press it into its pocket, round ends into the round ends.

## 3. The tub: the key's USB-C plug

![step 3](case/out/assembly/03-key-plug.png)

Solder the plug's four wires and its two pull-ups first ([the key](../pico-sign/README.md#the-key)), and
leave the wires about 12 cm long. Then, in the holder at the tub's top edge:
1. Drop the plug into the channel low, its cable down through the slot in the holder's foot.
2. Push it up. The metal shell goes through the hole in the top edge, and the black overmold stops
   flush with it.
3. Press the lock in under it, the cable in the lock's slot, until its two bumps click. Its lip is to
   pull it out by.

## 4. The tub: the breadboard and the sign button's switch

![step 4](case/out/assembly/04-breadboard.png)

The breadboard goes on the floor under where the button will be, between the four L-shaped stops, long
across the case. Stick it down with its own tape. The 12 × 12 switch goes across the centre channel, its
centre on the **3rd column from the right-hand end**, its legs in the 2nd and 4th. That column is under the
button.

Meter the switch first: find two legs, diagonally opposite, that beep only while it is pressed. Run a flat
jumper from each of their rows; they go to pins 20 and 18. Under the button there's only about 6.6 mm over
the board, so Dupont leads standing up won't fit.

## 5. The plate: an insert in each of the carrier's bosses

![step 5](case/out/assembly/05-plate-inserts.png)

Lay the plate face down on a towel. An insert in each of the four round bosses round the window, as in
step 1.

## 6. The sign button's guard, on the bench

![step 6](case/out/assembly/06-guard.png)

1. Put the cover's knuckle between the base's two and push the filament through all three. It is tight
   in the base and free in the cover.
2. Push the button cap up through the base from underneath. Its flange seats in the cone under the base.
3. Trim the pin flush on both sides. The cover should swing up and down, and the cap move a little.

## 7. The guard into its well

![step 7](case/out/assembly/07-guard-in.png)

Plate face up. The base, the cap and the cover go into the sign button's well together, the knuckles
toward the screen. Two M2 × 8 through the base's holes into the plate. They cut their own thread: turn
until firm, then stop.

## 8. The plate: the knob

![step 8](case/out/assembly/08-knob.png)

From behind, the EC11 into the knob's hole. Turn the plate over and put its nut on in the well. Snug,
not tight.

## 9. The plate: the screen onto its pins

![step 9](case/out/assembly/09-screen.png)

Face down again. Peel the screen's film. It goes glass down, its 8-pin header on the **left**. Lower it
onto the four pins: they go through its corner holes, and the board rests on the posts' seats.

## 10. The plate: the spacers

![step 10](case/out/assembly/10-spacers.png)

A printed spacer on each pin.

## 11. The plate: the carrier

![step 11](case/out/assembly/11-carrier.png)

The carrier over the pins, the Pico's posts facing you, its notch round the screen's header. Four
M3 × 8 with washers into the bosses. Tighten them evenly, a little at a time: they hold the screen down.

## 12. The plate: the Pico

![step 12](case/out/assembly/12-pico.png)

Solder its wires to its pads first, with the board in your hand. Then onto the carrier's four posts:
its parts and USB socket down toward the carrier, its USB end to the plate's **right** edge. The
slimmer posts are at the USB end. Four M2 × 8.

## 13. The wires

![step 13](case/out/assembly/13-wires.png)

The screen's header and the knob to the Pico, as pico-sign's tables say. Push the console image and try
it on the bench ([the bench check](README.md#first-the-bench-check)) before it goes in the tub. The key's
plug and the sign button's switch are in the tub: their wires come in the next step.

## 14. Onto the tub

![step 14](case/out/assembly/14-close.png)

Lay the plate face down beside the tub and solder the key's plug wires and the sign button's two jumpers
to the Pico. Press the cap: the switch should click. Then the plate onto
the tub, and four M3 × 8 socket heads through its corners, into the counterbores. Snug: they go into brass, but the plate is plastic. The micro-USB cable goes in through the hole in the right side, straight into
the Pico's socket.

## 15. The key into its clamshell

![step 15](case/out/assembly/15-key.png)

The key-c into the tray, parts up, the tray's peg through its round lanyard hole. The cover on, and
press until all four clips click. The chip shows through the window. To open it, push the four hooks in
through the windows in the sides with a small screwdriver.

The clips are not tried. Print the two halves and try them before the key goes in; if they're loose,
glue them.

## 16. The knob's cap, then the key

![step 16](case/out/assembly/16-done.png)

The cap onto the knob's shaft. The key, in its clamshell, straight down onto the plug in the top edge,
its chip's window toward the face.
