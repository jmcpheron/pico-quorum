# hardware

Console and key electronics. The goals are in [`../docs/KICKOFF.md`](../docs/KICKOFF.md).

## Every configuration

Two kinds: **builds**, put together from bought boards, and **boards** we design. The firmware
column is the console image's `BOARD` profile (`firmware/board.py`); a build's own test and demo
screens are bench scripts, never part of the image ([builds/](builds/README.md#firmware)).

| name | kind | the key | firmware | where it stands |
|---|---|---|---|---|
| [dev console](DEV-CONSOLE.md) | build | ATECC608 breakout, STEMMA QT | `waveshare` | the no-solder build |
| [Build 1](wiring/BUILD1.md), [on a breadboard](wiring/BREADBOARD.md) | build | ATECC608 on TRRS jacks | `build1` | — |
| [ESP32 DevKit](wiring/ESP32.md) | build | ATECC608 breakout | `esp32` | the console ran on a WROVER |
| [Feather + adapters](wiring/FEATHER-S3.md) | build | key-c, STEMMA QT to USB-C adapters | `feather-s3`; bench in [wiring/feather-s3/](wiring/feather-s3/) | runs; chip 3 through the ceremony, 2026-10-22 |
| [Feather pigtail](builds/feather-pigtail/README.md) | build | key-c, a USB-C cable soldered to the pins | `feather-s3`; bench `swap.py`; a case | written up, not wired |
| [Feather knob](builds/feather-knob/README.md) | build | key-c, a USB-C adapter on the header pins | `feather-knob` (knob and Boot); bench `dial.py` | written up, not wired |
| [pico-sign](builds/pico-sign/README.md) | build | key-c in a cartridge, in a bay | `build1` (knob, hold-to-sign switch); case concepts | written up, not wired |
| [key-c and the other keys](key-pcb/README.md) | board | — | — | key-c P2 built and working; P3 drawn |
| [console-a (console-pcb)](console-pcb/README.md) | board | key-c, USB-C | `build1` | designed |
| [console-a](console-a/README.md) | board | pads | `waveshare` | designed, not ordered |
| [console-pocket](console-pocket/README.md) | board | pads | `waveshare` | not checked in KiCad, not ordered |
| [feather-wing a, b](feather-wing/README.md) | board | key-c, USB-C | `feather-s3` | not ordered |
| [console-s3](console-s3/DESIGN.md) | board | ATECC608C on the board | `feather-s3` | to order ([plan](../ORDER-PLAN-2026-10-24.md)) |
| [console-usb](console-usb/README.md) | board | ATECC608C on the board | `feather-s3`, plus firmware not written | not routed |
| [console-rp](console-rp/README.md) | board | ATECC608C (SOIC-8) on the board | a `console-rp` profile, not written | routed, fab files pass `tools/keypcb jlc`; not ordered |
| [picoquorum-key](picoquorum-key/README.md) | board | UDFN ATECC608C on the board; rev B adds a key port for key-c | `picoquorum-key`, picked by its key bus's pull-ups; the port needs a later image | rev A to order ([plan](../ORDER-PLAN-2026-10-24.md)); rev B designed, not ordered |

The parts of each are below.

- [`DEV-CONSOLE.md`](DEV-CONSOLE.md): the no-solder dev console (Pico 2 W, Waveshare Pico-LCD-1.3,
  an ATECC608 breakout), from picowallet
- [`builds/`](builds/README.md): rigs put together from bought boards, one folder each (README,
  `bench/`, `case/`); the first is the [Feather pigtail](builds/feather-pigtail/README.md)
- [`wiring/`](wiring/): the key connector pinout and console schematics; Build 1 in
  [`wiring/BUILD1.md`](wiring/BUILD1.md) (its build order, rules and firmware to do), and on a breadboard in [`wiring/BREADBOARD.md`](wiring/BREADBOARD.md);
  the same parts on an ESP32 DevKit instead of a Pico in [`wiring/ESP32.md`](wiring/ESP32.md)
- [`bom/`](bom/): the parts list and sourcing notes
- [`key-pcb/`](key-pcb/): the key's board. Rev A makes the board itself the plug (gold fingers into
  a card-edge socket). It has two KiCad projects, the fab files, and how to order them
  ([ORDERING.md](key-pcb/ORDERING.md))
- [`console-pcb/`](console-pcb/): the console on one board. console-a holds a Pico 2 W, Build 1's
  screen, knob and buttons, and a USB-C plug for key-c. The options weighed are in
  [OPTIONS.md](console-pcb/OPTIONS.md)
- [`console-a/`](console-a/): a second one-board console, on the Waveshare Pico-LCD-1.3's pins
  (a bare 1.3″ panel, a d-pad and A/B/X/Y, pads for the key), so the console image runs with the
  default `BOARD`. JLCPCB can solder its Pico too. Designed and checked, not ordered
  ([ORDERING.md](console-a/ORDERING.md))
- [`console-pocket/`](console-pocket/README.md): a third, the pocket size, also on the Waveshare
  pins: the Pico 2 W soldered on the back as a module, a bare 1.54″ panel, seven buttons and pads
  for the key's wires, 51 × 85 mm. Written by a script, routed, self-checked; not yet checked in
  KiCad, not ordered
- [`feather-wing/`](feather-wing/README.md): not a console but a board for one: a FeatherWing-sized
  board behind Adafruit's Feather ESP32-S3 Reverse TFT, on its header pins, with console-a's
  protected USB-C port for key-c. wing-a has an upright plug; wing-b a right-angle plug at the
  edge of a tab. Written by a script, routed, self-checked; not yet checked in KiCad, not ordered
- [`console-s3/`](console-s3/DESIGN.md): a fourth, the S3 console: an ESP32-S3-WROOM-1 on the back,
  the Feather's 1.14″ screen in a ZIF, five buttons, the ATECC608C soldered on and a USB-C for power
  and serial, 64 × 22.86 mm. Economic assembly for everything but the module and the panel, which
  the workshop fits. Three of its buttons, the screen and the key are on the Feather's pins, so
  today's image runs on it. Written by a script, placed, routed and self-checked; ERC, DRC and
  parity clean in KiCad; not ordered. The idea and costs: [CONCEPT.md](console-s3/CONCEPT.md);
  what any S3 console must have, in any shape: [SPEC.md](console-s3/SPEC.md)
- [`console-usb/`](console-usb/README.md): the console-s3 idea with no radio in use: the bare
  ESP32-S3 chip, no antenna, three buttons on the Feather's pins, and a USB-C whose only data path
  is a CH340C serial bridge to the S3's UART1, so the computer that relays the queue gets no REPL
  and can't reset it. JLCPCB places everything but the screen. Written by a script and checked by
  KiCad 9: the schematic, and a 70 × 28 mm board with every part placed and 3D renders; not routed,
  not ordered
- [`console-rp/`](console-rp/README.md): console-usb on an RP2350A, which has no radio at all:
  Raspberry Pi's minimal circuit and 16 MB flash, the 1.14″ screen with D0 D1 D2 in a row under
  it, the SOIC-8 ATECC608C, and a USB-C whose only data path is a CH343P (CDC-ACM) serial bridge
  to UART1. JLCPCB places everything but the screen. Written by a script and checked by KiCad 10:
  the schematic, and a 72 × 36 mm board routed round Raspberry Pi's own layout, with 3D renders and
  fab files that pass `tools/keypcb jlc`; not ordered
- [`picoquorum-key/`](picoquorum-key/README.md): PicoQuorumKey, a second S3 console designed apart
  from console-s3, to order beside it and compare: the module on the back, the 1.14″ panel in a
  ZIF, five buttons, the UDFN ATECC608C, 44 × 53 mm. Its own generators, tests and fab files in
  `hardware/out/rev-a/`. Rev B (`hardware/out/rev-b/`) adds a key port at the top-left corner: a
  straddle USB-C plug for key-c on an I2C bus of its own, power switched and off by default, its
  parts fitted only on the boards that want it; 50 × 53 mm, 0.8 mm thick. Its buttons aren't on the Feather's pins, so it has its own firmware
  profile, `picoquorum-key`, which the image picks by looking at the board; in a release from
  after 2026.10.12

The inherited picowallet wiring (Pico + Waveshare LCD + ATECC608 + 18650) is in
[`wiring/SOLDERING.md`](wiring/SOLDERING.md) and `tools/wiring`.

**The enclosure** isn't designed yet. Its open questions (button layout, a flip cover or a guard
over Sign, printed or aluminum, the faceplate name) are in the kickoff's
[open decisions](../docs/KICKOFF.md#open-decisions).

## License

Copyright Jason McPheron 2026.

This source describes Open Hardware and is licensed under the CERN-OHL-W v2
([LICENSE-HARDWARE](../LICENSE-HARDWARE), https://ohwr.org/cern_ohl_w_v2.txt). You may redistribute
and modify this source and make products using it under the terms of the CERN-OHL-W v2. This source
is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY, INCLUDING OF MERCHANTABILITY, SATISFACTORY
QUALITY AND FITNESS FOR A PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable
conditions.

**Source Location:** https://github.com/jmcpheron/pico-quorum

As per CERN-OHL-W v2 section 4.1, should you make hardware based on these sources, you must keep
the Source Location visible on the product itself (its silkscreen, case or label) or, where it
doesn't fit, on its packaging or documentation.

The name and the mark on the boards are not part of this license ([TRADEMARK.md](../TRADEMARK.md)):
a board you change carries your name, with the Source Location.

- [ ] Put the Source Location on the silkscreen at the next key revision (key-c P3).
