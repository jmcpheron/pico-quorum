# Cases for the console boards

Two cases for the two S3 boards from JLCPCB, and a dock for each:
- **the stick**, for [console-s3](../../hardware/console-s3/DESIGN.md)
- **the badge**, for [PicoQuorumKey rev A](../../hardware/picoquorum-key/README.md)

**Status, 2026-11-03:** a first draft of each, drawn the day the boards arrived. Not printed, not
fitted to a board.

| | the stick | the badge |
|---|---|---|
| board | console-s3 rev A, 64 × 22.86 × 1.6 mm | PicoQuorumKey rev A, 44 × 53 × 1.6 mm |
| closed | 74.6 × 27.5 × 12.2 mm | 48.6 × 63.6 × 12.2 mm |
| screws | 2 × M2 × 8, at the USB end | 4 × M2 × 8 |
| USB-C | the left end | the bottom edge |
| lanyard | a lug at the antenna end | a lug at the top |
| dock | 81 × 38 × 15 mm, the cable out of the left | 55 × 50 × 48 mm, the plug in a slot in its lip |

![the stick](out/stick/stick_front.png)

![the badge](out/badge/badge_front.png)

## How they go together

Both are the same kind of case, made by one script, [`shell.py`](shell.py):

- **A tub and a front plate.** The plate sits in the tub's opening, flush with its rim. The board
  lies between them, face up.
- **The board's own holes hold it.** M2 screws go in from the back:
  - through bosses in the tub
  - through the board's holes
  - into posts on the plate's underside

  The bosses and posts clamp the board, and stay inside the 2.5 mm keep-out ring round each hole. There
  is nothing to see on the front.
- **The antenna end is held without metal.** A rib on the plate presses on the board's front where it
  has no copper. Two ribs in the tub come up under the module's shield. The nearest screw is 23 mm
  from the antenna on the badge, 55 mm on the stick.
- **The window** shows the active area and 0.5 mm round it. The plate keeps at least 0.8 mm over the
  glass's edge, and sits 0.15 mm above the glass, so it keeps the glass on its tape.
- **Caps on D0, D1 and D2.** Each cap has a round stem through the plate, and a square flange under the
  plate that keeps it in. The caps are in the brand's colours ([BRAND.md](../../docs/BRAND.md)):
  - D0 is Reject red
  - D1 is white
  - D2 is Sign green

  All three take the same light press. A case mustn't make Reject harder to reach than Sign.
- **BOOT and RESET are pinholes,** 1.8 mm across. A paperclip reaches them, and a thumb doesn't press
  them by mistake.
- **A hole over the LED.**
- **The Source Location is on the back** (CERN-OHL-W v2, section 4.1). The case covers the board's
  own, so the back carries `PicoQuorum.app` under the name.

![the stick, apart](out/stick/stick_apart.png)

## The stick (console-s3)

[`stick.py`](stick.py). The board is a bar, and the case follows it.
- **The screws are at the USB end only.** The board's only holes are there, by design: a screw at the
  far end would be metal by the antenna.
- **The mark is at the antenna end,** engraved, over the board's own mark.
- **The window is 1 mm wider than the active area needs.** The board's render centres the active area
  on the glass. ER-TFT1.14-2's drawing puts it 2.0 mm from the end away from the ribbon. The window
  shows the active area wherever it is, until a panel is measured.
- **The dock** holds it leaning back 25°. The cable comes out of a slot in the dock's left side.

![the stick on its dock](out/stick/stick_dock.png)

## The badge (PicoQuorumKey rev A)

[`badge.py`](badge.py). Portrait, like a small handheld, with a lug for a lanyard.
- **The key window** is an opening over U2, the ATECC608C: the chip that is the key. The board's 8-bit
  key and its dragon are beside the chip, so you can see them too. The post round H2 hides the
  dragon's head. The window stops above BOOT, so BOOT stays behind its pinhole.
- **The mark and the name** are engraved under the screen, left of the key window.
- **The caps sit in pockets in the plate's underside,** because these switches stand 3.8 mm, higher
  than the glass. So the plate is 2.3 mm thick over the glass, not 1.8.
- **The dock** holds it leaning back 25°. The plug goes down into a slot in the lip, and the cable
  leaves at the front.

**Rev A only.** Rev B is 50 mm wide and 0.8 mm thick, with a key port at its top-left corner. This case
doesn't fit it.

![the badge on its dock](out/badge/badge_dock.png)

![the badge, apart](out/badge/badge_apart.png)

## Where the numbers come from

| | the stick | the badge |
|---|---|---|
| outline, holes | the generator (`gen_console_s3.py`) | the outline from DESIGN.md; the holes from the NPTH drill file JLCPCB drilled |
| every part on the front | `console-s3/fab/cpl.csv` and `bom.csv`, the files JLCPCB built from. The script stops if they disagree with the generator | `hardware/out/rev-a/cpl.csv` and `bom.csv` |
| glass, tape, ribbon fold | the generator: 31 × 17 mm glass, 1.6 mm thick on 2.0 mm tape | DESIGN.md: 31 × 17.6 mm glass, 1.6 mm thick on 1.5 mm tape |
| module | the generator: the WROOM-1 on the back, 3.1 mm | DESIGN.md, less 6 mm in x (rev B was made from rev A that way) |

Each part is a box, at its footprint's usual size and height (`PACKAGES` in `shell.py`). These are not
the makers' models.

## What the script checks, and what it doesn't

When a case builds, the script checks that none of these overlap each other:
- the tub, the plate and the caps
- the board, each part's box, the glass and its ribbon fold, the module
- a USB-C plug pushed fully home: 12.4 × 5.5 mm overmold, the handheld's measured cable
- the screws
- the dock, with the case in it

It prints a line for each overlap and exits 1 if there is one; both cases build with none. It also
chooses the screw: the longest in the bench's kit (4, 8, 12, 16 mm) that leaves at least 3 mm of
thread in the post.

**It doesn't check fit against a real board.** Nothing here is measured. Before printing the tub, measure
these and change the numbers in the scripts:
- **the panel:** the glass's thickness and the tape's (`glass_z`). The plate's height follows them.
- **the switches:** the stick's TS-1187A is taken as 1.5 mm tall, the badge's 4.5 × 4.5 tacts as
  3.8 mm (`PACKAGES`). The caps sit on them. If a height is wrong, reprint the caps; on the badge,
  the plate too.
- **the module, as soldered:** 3.1 mm (`WROOM`). The tub's ribs follow it.
- **your cable's overmold**, against the 13.2 × 6.2 mm opening (`USB_OPEN`).

## Printing

Every part prints without supports, judging by the shapes. They haven't been sliced.
- **tub:** on its back, as written. The opening over the USB-C is a short bridge.
- **plate:** face down, as written. The posts, ribs and pockets point up.
- **caps:** flange down, one STL each, so each can be its own colour.
- **dock:** on its base, as written.
- PLA or PETG, 0.2 mm layers. The engraving is 0.5 mm deep.

**Print the plate first** and lay it on the board. It's the fit check:
- the posts land round the holes
- the window frames the screen
- the caps' holes sit over D0, D1 and D2

## Putting it together

1. Drop the caps into the plate from behind, flange inside: red D0 at the top, white D1, green D2.
2. Lay the board in the tub face up, its USB-C to the opening.
3. Lay the plate on it, caps onto the switches.
4. Hold the two together, turn them over, and put in the M2 × 8 screws.
5. Turn each screw until it is snug, no tighter: it cuts its own thread in the post.
6. Press each cap. It should click and come back.

## Run

```sh
tools/case build stick badge
```

Each script runs on its own too:

```sh
uv run --python 3.11 --with cadquery --with matplotlib --with pillow python cad/consoles/stick.py [screen.png]
```

They write `out/stick/` and `out/badge/`:
- the STLs to print
- `<name>_assembly.step`, with the board's stand-ins
- the pictures, with the Feather's review screen (`docs/quorum-ui/feather/03-review-head.png`) on the
  panel, or the PNG given
