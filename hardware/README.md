# hardware

Console and key electronics. The goals are in [`../docs/KICKOFF.md`](../docs/KICKOFF.md).

- [`DEV-CONSOLE.md`](DEV-CONSOLE.md): the no-solder dev console (Pico 2 W, Waveshare Pico-LCD-1.3,
  an ATECC608 breakout), from picowallet
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
- [`picoquorum-key/`](picoquorum-key/README.md): PicoQuorumKey, a second S3 console designed apart
  from console-s3, to order beside it and compare: the module on the back, the 1.14″ panel in a
  ZIF, five buttons, the UDFN ATECC608C, 44 × 53 mm. Its own generators, 125 tests and fab files in
  `hardware/out/rev-a/`. Its buttons aren't on the Feather's pins, so it has its own firmware
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
