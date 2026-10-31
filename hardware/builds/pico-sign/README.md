# pico-sign: a knob and a hold-to-sign switch

| | |
|---|---|
| board | a Pico 2 W (castellated), wires or headers soldered on |
| key | a key-c in a printed cartridge that slides into a bay ([case/CONCEPTS.md](case/CONCEPTS.md)) |
| runs | the console image as `BOARD = "build1"`, `SCREEN = "2.8"`, unchanged; `firmware/bench1.py` first |
| case | [the prism](#the-case-the-prism): a one-piece body and a front plate, M3 into heat-set inserts |
| status | written up 2026-10-30 for a demo; not wired, not printed, not run |

Build 1 again, made into a box. A rotary knob does everything on the screen, and one metal push
switch is Sign: hold to sign. A key-c plugs in on top, so keys swap in and out. It is a hobby build: bought
parts, hand wiring, a printed case.

![the wiring](wiring.svg)

`python3 hardware/builds/pico-sign/wiring.py` redraws the diagram. With `--check` it only loads
`firmware/board.py` as build1 and stops if the pins below differ.

## Parts

- a Pico 2 W
- the 2.8″ IPS 240 × 320 SPI screen (ST7789) from the earlier build, the one Build 1 proved on the
  bench (2026-09-27). Same 8 pins as the 2.4″ this build started with
- an EC11 knob with push, the one from Build 1: 20 detents, a 6 mm D-shaft, an M7 bushing
- the sign switch: a 12 mm metal push switch, **momentary** and normally open. See [the sign switch](#the-sign-switch)
- a key-c, and a USB-C plug for it: a C-to-C cable cut short behind one plug, as the
  [Feather pigtail](../feather-pigtail/README.md) uses, or a USB-C plug breakout
- two 4.7 kΩ resistors, the key's pull-ups
- for the case: four M3 × 8 countersunk screws, four M3 heat-set inserts, four M2 × 5 screws for the
  Pico, four small rubber feet

## The wiring

Every signal is on Build 1's pin ([BUILD1.md](../../wiring/BUILD1.md)), so the console image runs
with no change. Physical pins count from the USB end: 1–20 along one side, 40–21 back along the other.

### The screen

| screen pin | Pico pin | GPIO |
|---|---|---|
| VCC (or 3V3) | **36**, 3V3 OUT | |
| GND | **13** | |
| SCL (or CLK, SCK): the SPI clock | **14** | GP10 |
| SDA (or MOSI, DIN): SPI data | **15** | GP11 |
| CS | **12** | GP9 |
| DC (or RS) | **11** | GP8 |
| RST | **16** | GP12 |
| BLK (or BL, LED) | **17** | GP13 |

- Go by the names printed on your board. The order of the pins varies between makers.
- The screen's SCL and SDA are its SPI lines. They are not the key's I2C.
- 3.3 V only. Nothing goes to VBUS (40) or VSYS (39).

### The knob

| knob pin | Pico pin | GPIO |
|---|---|---|
| A | **4** | GP2 |
| C, the middle of the three | **3**, GND | |
| B | **5** | GP3 |
| SW1, the push | **2** | GP1 |
| SW2, the push's other leg | **3**, GND | |

- Join C and SW2 at the knob and run one ground wire to pin 3.
- The Pico's own pull-ups. No resistors.
- If clockwise moves backwards, swap A and B.

### The sign switch

| switch lug | Pico pin | GPIO |
|---|---|---|
| either | **20** | GP15 |
| the other | **18**, GND | |

GP15 is the Waveshare's A, which the console reads as Sign. Build 1 kept it for a Sign button.

### The key

key-c: D+ carries SDA, D− carries SCL, VBUS is the key's power
([key-c](../../key-pcb/key-c-usbc/README.md)).

| plug wire (the usual colour) | Pico pin | GPIO |
|---|---|---|
| VBUS (red) | **36**, 3V3 OUT. Never 40 (VBUS) | |
| GND (black) | **8** | |
| D+ (green) | **6** | GP4, SDA |
| D− (white) | **7** | GP5, SCL |
| CC, SBU, the rest | trimmed and insulated, each on its own | |

- **Pull-ups.** key-c has none. Solder a 4.7 kΩ from VBUS to D+ and another from VBUS to D−, at the
  plug. The Pico's internal pull-ups are about 50 kΩ: maybe enough at 100 kHz on short wires, not
  checked.
- **Three wires on 3V3.** Pin 36 feeds the screen, the key and the pull-ups. Splice them on a scrap of
  perfboard or with a short Y-lead.
- **The colours are only a convention.** Meter each wire from its pin on the plug. Before the first
  key goes in, meter VBUS to GND: not a short.
- **No protection.** As on the Feather pigtail: no current limit, no ESD diodes, no switch. The key is
  powered whenever the Pico is. Build 1's switched power on GP6 isn't in the console image yet
  ([BUILD1.md](../../wiring/BUILD1.md#firmware-to-do)), so this build doesn't wire it.
- **No key LED.** key-c P2 has none. P3's LED takes SBU from wing-a; nothing here drives it.

### Headers or wires

For tonight, header pins and female Dupont leads are quickest, and they come apart. For a box that
stays together, solder the wires straight to the castellated pads. The case leaves 22 mm above the
Pico's board for headers and Dupont housings.

## The sign switch

**It must be momentary.** Music shops sell 12 mm metal push switches for effects pedals, and most of
them are latching 3PDT (true bypass): press once and they stay closed. The console starts a Sign when the switch goes down and signs once it has been
held 2 s. A latching switch stays down by itself, so one tap would sign 2 s later with nobody
holding it. That breaks the rule that Sign is held. Use a momentary SPST, normally open (often sold
as "soft touch" or "momentary"). Meter it: it beeps only while pressed.

If yours is latching, don't use it for this build.

## What the controls do

The console's build1 rules, from `firmware/quorum.py`. Nothing here is new.

| | on a review | anywhere else |
|---|---|---|
| turn clockwise | the next page; past the last, the action rows | the next row or choice |
| turn back | the page before | the one before |
| push the knob | jumps to the rows; on Sign, held, signs; on Back, leaves it unsigned | open |
| **sign switch** | **Sign: every page seen first, then held 2 s (3 s when a page is red)** | says "Sign button: only for signing" |

- **There is no Reject button.** A cosigner can't reject a Safe transaction: not signing it is all
  it can do. A transaction is only cancelled when the owners execute another one at the same nonce.
  Today's console still has a Reject row on a review, but it only hides the transaction on this
  console. The v3 plan (`docs/quorum-ui/v3/`) drops it.

- **The sign switch is not the only way to sign.** The knob's push on the Sign row, held, signs too.
  Making the sign switch the only one is a firmware change and a new release fingerprint (AGENTS.md).
  Not done; ask first.
- Let go early and nothing is signed. A red page needs 3 s.
- **Maintenance:** the knob held down at power-up. **Wi-Fi setup:** by itself when no network is
  saved, or Device → Wi-Fi. (GP21 held at power-up starts it too, but nothing is wired to GP21 here.)

## First: the bench check

In the board's `secrets.py`, beside the rest:

```python
BOARD = "build1"
SCREEN = "2.8"
```

Then `tools/usb push`, `tools/usb`, `import wallet; wallet.stop()`, `import bench1`, as in
[BREADBOARD.md](../../wiring/BREADBOARD.md#try-it). `bench1.py` only reads the chip. Leave its
`JACKS = False`: the key is on 3V3, not on GP6.

What to look for:
- **the screen:** TL top left, the bars red, green, blue, white. If it's dark, check the wiring by
  the printed names first. Then `SPI_BAUD = 10_000_000` at the top of `bench1.py`. If it's upside
  down, `MADCTL`; if the colours are a negative, `INVERT = False`
- **the knob:** one click is one count, clockwise up, PUSH reads DOWN while pressed
- **the key:** BUS 60 and the chip's serial when a key-c is in

`bench1` doesn't show GP15 or GP21. Check them on the console: the sign switch on home says "Sign
button: only for signing".

**The 2.8″ is proven on build1** (2026-09-27): `MADCTL = 0x60`, inversion on, 24 MHz. If it comes up
upside down, the header is on the other side from Build 1's case: that is `MADCTL`. (The 2.4″ this
build started with was never seen working; if you go back to it, it may be an ILI9341, which needs
inversion off: a firmware change.)

## Then: the console

Push the image as usual (`tools/fw push`, [docs/guide](../../../docs/guide/)). The key needs to be one
that is provisioned already. This build doesn't run a ceremony, and nothing in it writes or locks a
chip.

## The case: the prism

[`case/prism.py`](case/prism.py), CadQuery. A first draft to print and try.

```sh
uv run --python 3.11 --with cadquery --with matplotlib --with pillow \
    python hardware/builds/pico-sign/case/prism.py [screen.png]
```

![the prism](case/out/prism/prism_front.png)

A triangle seen from the side, 180 mm wide: the front plate slopes at 60°, a flat band 34 mm deep runs
along the top, and the back falls at 70°. 78 mm tall, 107 mm front to back.

**Two printed parts:**
- **The body**, one piece, open at the front. Printed front-down, every face leans at 40° or less
  from upright, so it needs no supports. Its outside edges are chamfered 2.5 mm. A channel 3 mm tall
  and 1.5 mm deep runs round the base, plate included, for a strip of another colour.
- **The plate**, 3 mm, printed face down. Four M3 countersunk screws hold it, into heat-set inserts
  in blocks at the corners of the body's opening.

**On the plate:**
- the screen on the left, in a bevelled window, on four posts (M2.5 self-tapping into the plate)
- the controls on the right:
  - the sign switch on top, a 12 mm metal push switch, on a ring 2 mm thicker behind the plate
    because it's pressed hard, with HOLD TO SIGN under it
  - the knob under that, with TURN / PUSH
- PICOQUORUM and SEALED HARDWARE COSIGNER cut under the screen

![the plate, front and back](case/out/prism/prism_plate.png)

**The key** lies flat in a tray sunk into the top band, in its cartridge
([CONCEPTS.md](case/CONCEPTS.md#the-key-cartridge)), its chip window up, 2.4 mm below the surface. A
finger scoop at the grip end lifts it out. The console's USB-C plug sits in a cradle under the
band at the tray's other end, its face flush with the tray's end. So the cartridge slides along the
tray onto it, and a pull comes off the cradle, never the joints. "KEY" is cut beside the tray.

**Inside:**
- the Pico on four posts on the floor, at the left, its USB out of the left side
- the plug's cable out through the cradle's back stop
- 27 mm between the sign switch's lugs and the floor

![the body, open](case/out/prism/prism_body.png)

| file in `case/out/prism/` | what |
|---|---|
| `prism_body.stl` | the body, front down, as it prints (180 × 104 × 88 mm) |
| `prism_plate.stl` | the plate, face down |
| `prism_assembly.step` | closed, with a box for each part |
| `prism_front.png`, `prism_plate.png`, `prism_body.png` | the pictures here |

**What the script checks:** that the boxes standing in for the screen board, the switch, the knob,
the plug, the cartridge and the Pico with its wires don't overlap the body, the plate or each
other (50 pairs). Also that the plug clears the top band (0.38 mm). It is not a fit check.

**Before printing:**
- **Measure the screen.** `SCREEN_*` are a placeholder: an 86 × 50 mm board with M3 holes 3 mm in,
  a 69.2 × 50 mm glass and a 57.6 × 43.2 mm active area. The glass and active area are the usual 2.8″
  IPS panel's; the board and its holes vary by maker.
- **The plug:** the cut cable's overmold, as the Feather pigtail measured it. A different cable, or
  a USB-C plug breakout, needs the cradle (`PLUG_*`) changed.
- **The sign switch:** a 12 mm bushing and 28 mm of body under the plate, momentary.
- Print the plate first: every part's hole is in it.

Not printed yet. The pictures are matplotlib's, and its shading is rough.

**Earlier:** [CONCEPTS.md](case/CONCEPTS.md) has the four first concepts for the 2.8″ and the key
cartridge. [`case.py`](case/case.py) is the first wedge, for the 2.4″, with the key standing up.

## The demo

[DEMO.md](DEMO.md): the story, the setup with the laptop's simulated Safe, the shots, and the key swap.
