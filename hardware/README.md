# hardware

Console and key electronics. The goals are in [`../docs/KICKOFF.md`](../docs/KICKOFF.md).

- [`HANDOFF.md`](HANDOFF.md): Build 1 on the bench: parts, build order, rules, what's next
- [`wiring/`](wiring/): the key connector pinout and console schematics; Build 1 in
  [`wiring/BUILD1.md`](wiring/BUILD1.md), and on a breadboard in [`wiring/BREADBOARD.md`](wiring/BREADBOARD.md)
- [`bom/`](bom/): the parts list and sourcing notes
- [`key-pcb/`](key-pcb/): the key's board. Rev A makes the board itself the plug (gold fingers into
  a card-edge socket). It has two KiCad projects, the fab files, and how to order them
  ([ORDERING.md](key-pcb/ORDERING.md))
- [`key-interface/`](key-interface/SPEC.md): the key interface, version 0 (draft). This is the blade,
  the pins, the power sequence and the ID codes that any key and any console agree on
- [`console-v2/`](console-v2/README.md): the console as one PCB a fab can assemble, with a better
  knob, a Sign button lit from underneath, a load-switched key socket and a LiPo. This is an
  exploration, so nothing is laid out yet

The inherited picowallet wiring (Pico + Waveshare LCD + ATECC608 + 18650) is in
[`wiring/SOLDERING.md`](wiring/SOLDERING.md) and `tools/wiring`.
