# hardware

Console and key electronics. The goals are in [`../docs/KICKOFF.md`](../docs/KICKOFF.md).

- [`HANDOFF.md`](HANDOFF.md): Build 1 on the bench: parts, build order, rules, what's next
- [`DEV-CONSOLE.md`](DEV-CONSOLE.md): the no-solder dev console (Pico 2 W, Waveshare Pico-LCD-1.3,
  an ATECC608 breakout), from picowallet
- [`wiring/`](wiring/): the key connector pinout and console schematics; Build 1 in
  [`wiring/BUILD1.md`](wiring/BUILD1.md), and on a breadboard in [`wiring/BREADBOARD.md`](wiring/BREADBOARD.md)
- [`bom/`](bom/): the parts list and sourcing notes
- [`key-pcb/`](key-pcb/): the key's board. Rev A makes the board itself the plug (gold fingers into
  a card-edge socket). It has two KiCad projects, the fab files, and how to order them
  ([ORDERING.md](key-pcb/ORDERING.md))

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
