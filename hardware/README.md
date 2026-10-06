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
