# M1 carrier: prototype quote instructions

2026-10-07. **Quote for the main console carrier only.** This is an unbuilt prototype,
not a tested console. The display, cable, key adapter, enclosure and firmware work
are separate. No order has been placed.

Quote 5 prototypes, with separate estimates for 20 and 100 units. Do not buy a
production batch before the prototype is checked on the bench.

## PCB and assembly

- Two layers, 70 x 95 mm bounding size, 1.6 mm FR-4, 1 oz copper, ENIG.
- Green mask, white silkscreen; lead-free solder. Other mask colours are optional.
- All 30 fitted components are on the top. J2 and TP1-TP4 are bare pads, not parts.
- Four 2.7 mm non-plated mounting holes. Preserve the antenna cutout and RF void.
- Obtain fabrication review of the milled inside corners and board neck before ordering.
- Gerbers and drills share the bottom-left placement origin. CPL uses mm, +X right,
  +Y up from that origin. Check rotations against pad 1 in the assembler's preview.
- BOM gives manufacturer part numbers, not pre-verified JLCPCB stock codes. Quote
  sourcing and any consigned parts separately. No substitutes without checking the drawing.

U1 is **Raspberry Pi Pico 2 W SC1633, without headers**. Solder its castellations to
the carrier. Do not substitute a non-wireless Pico, Pico W, or headered board.
The footprint is based on KiCad's Pico W SMD pattern, which supports Pico 2 W.
It retains the oversized castellated paste openings described by Raspberry Pi.
Agree the stencil and module placement process with the assembler. Inspect every
castellation and check for bridging or a module lifted by excess underside solder.

Unused underside test-point copper and paste lands are removed, with front-copper
voids around them. USB shell ground lands and SWD lands remain. The radio keepout
applies to both copper layers. The stock rule's paste-layer false positives were
removed; the castellated paste pattern itself was retained.

SW1-SW8 are **E-Switch TL3305AF160QG**, 160 gf, A actuator (3.8 mm overall height).
The KiCad two-terminal footprint groups each internally common row of the maker's
four-terminal switch. Lands are 1.6 x 1.4 mm, centres at X +/-3.6, Y +/-1.5 mm.
This gives the maker's 8.8 mm outside width, 5.6 mm inside gap, 4.4 mm outside
row span and 1.6 mm inner row gap. Use case plungers with travel stops; do not
side-load the actuators. The enclosure must recess Sign and leave Reject accessible.

J1 is **JST S8B-PH-SM4-TB**, eight-way, 2 mm pitch, SMT side entry. Use the
manufacturer's lead-free tin version. Its two retention lands are mechanical pads.
The 3D preview has no connector-body model; it is not a completed fit check.

## Separate LCD and cable

Use **Waveshare 1.3inch LCD Module, SKU 15867**, not Pico-LCD-1.3 or an LCD HAT.
It is 240 x 240 IPS ST7789 with an eight-wire interface. Its documented board
outline is 45 x 31 mm; the drawing reserves a rotated 31 x 45 mm envelope.
The case supports the module separately. Do not send the display through reflow.
Its own PCB includes decoupling and a transistor for the backlight. Operate VCC
and the carrier logic at 3.3 V. Do not feed the panel through a GPIO.

Keep the cable short, initially 50-100 mm if the stack permits. Quote a crimped,
keyed harness separately. Carrier J1 mating housing is JST PHR-8; choose the proper
PH contacts for the wire gauge and use the specified crimp process. The supplied
Waveshare breakout cable may have loose ends; it is not automatically our harness.

| Carrier J1 pin | signal | LCD connection by its printed label |
|---|---|---|
| 1 | 3V3 | VCC |
| 2 | GND | GND |
| 3 | GP11 through 33R | DIN |
| 4 | GP10 through 33R | CLK / SCK |
| 5 | GP9 through 33R | CS |
| 6 | GP8 through 33R | DC |
| 7 | GP12 through 33R | RST |
| 8 | GP13 through 33R | BL |

The maker's schematic numbers the LCD's J2 opposite to its J1: LCD J2 pin 8 is
VCC and pin 1 is BL. Do not assume a straight-through numbered cable. Confirm
the actual module revision, physical pin 1, mating view and every conductor with
a meter before power. Cable colours are not a pinout.

## Internal key-adapter pads

These pads are **host-side signals**, not a finished USB-C key interface. Solder
only the internal protected adapter here; provide strain relief through the case.
The future adapter must handle key power switching, current limiting, reverse
blocking, isolation, ESD, protected attachment sensing and removal behaviour.

| J2 pad, left to right | label | adapter requirement |
|---|---|---|
| 1 | GND | shared host ground |
| 2 | 3V3 | host supply; never connect directly to dock VBUS |
| 3 | SDA | GP4; host side of isolatable I2C interface |
| 4 | SCL | GP5; host side of isolatable I2C interface |
| 5 | EN | GP6 request; 100k pull-down; adapter hardware defaults off |
| 6 | FLT | GP7; 10k pull-up; adapter open-drain fault/status output |
| 7 | A | GP26; protected 0-3V3 attachment output from adapter |
| 8 | B | GP27; protected 0-3V3 attachment output from adapter |

Host I2C has 2.2k pull-ups to host 3V3. The adapter must provide the appropriate
key-side pull-ups and preserve ATECC wake timing. A/B must not back-power the ADC
pins when the host is off. Raw CC, VBUS or key-side bus lines must not be soldered
to these host pads. No adapter circuit or harness protection is supplied by this package.

## Prototype acceptance, before use as a signer

Inspect soldering. Meter 3V3/GND and connector wiring before power. Check unloaded
power first, then LCD/adapter loads; measure 3V3 during Wi-Fi activity. The actual
load budget is not measured yet. Check all eight buttons, SWD/RUN access and USB
connector access. Test the screen's rotation, colour, offsets and readable text.
Start cable SPI at a low rate (for example 8 MHz); the present Waveshare firmware's
62.5 MHz is not validated on this harness.

Firmware still needs Select/Device navigation, actual button names, and a dedicated
Sign role outside review. Test all-page review, red pages, hold/release behaviour,
Reject during a hold, boot shortcuts and key removal with a test key. Keep the existing
signing site and hash reconstruction. No firmware is changed or flashed by this package.

Then test the protected adapter in powered/unpowered, removal, short and foreign-power
cases before connecting the arriving USB-C key. Provisioning and locks are separate
tasks. A clean CAD check does not verify hardware behaviour or authorise production.

## Files and checks

`m1-gerbers.zip` contains nine Gerber layers and separate plated/non-plated drill
files. `bom.csv` and `cpl.csv` contain the same 30 fitted references. `assembly.svg`
and `schematic.pdf` describe the circuit and placement. `board-only.step` is the
carrier without components or case. `SHA256SUMS` identifies the exported files.

`export.py` refuses to export unless ERC, all-severity DRC, missing-connection and
schematic-parity checks are all zero. Saved reports are `erc.rpt` and `drc.rpt`.
Supplier stock, assembler process, physical fit, Wi-Fi performance, power budget,
adapter behaviour and firmware navigation remain unverified.

Sources: [Pico 2 W drawing](https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf),
[TL3305 drawing](https://www.e-switch.com/wp-content/uploads/2023/01/TL3305.pdf),
[JST PH drawing](https://www.jst-mfg.com/product/pdf/eng/ePH.pdf),
[LCD manual](https://files.waveshare.com/upload/7/70/1.3inch_LCD_Module_user_manual_en.pdf),
[LCD circuit](https://files.waveshare.com/upload/0/0c/1.3inch_LCD_Module_Schematic.pdf).

Source Location: https://github.com/jmcpheron/pico-quorum
Hardware licence: CERN-OHL-W-2.0, as in the repository's LICENSE-HARDWARE.
