# The cartridge bay

*Designed 2026-10-06. Not printed yet.*

A printed bay that a key-c key plugs into, like a USB stick: the connector half goes in, the lanyard
half stays out. One lever does two jobs:
- **Lever up:** the key is locked in, then the console turns on.
- **Lever down:** the console turns off, then the key is free.

It is a lock against pulling the key out by mistake while the console is on. It is not tamper
resistance: anyone can move the lever.

## How it works

**The lock moves through the board, not along it.**
- The key lies flat in a channel, its back face on the floor.
- Under the floor, a carriage holds two 2 mm steel dowel pins, one under each of key-c P3's edge
  notches.
- Lever up lifts the pins up through the notches and on into pockets in the channel's roof. Each
  notch is half a hole round a pin, so the key can't slide.
- Lever down drops the pin tops 0.3 mm below the floor, and the key slides out.

```
         across the key, at the notches (y = -3.5), lever up

     roof    ┌──────────┐  ┌────────────┐  ┌──────────┐
     pocket  │          │▓▓│   tunnel   │▓▓│          │
             │      ═══▓▓══════key══════▓▓═══       │    ═ key-c, notches at the pins
     floor   └──────────┴▓▓┴────────────┴▓▓┴──────────┘
             │     ┌─────▓▓──────────────▓▓─────┐    │    ▓ 2 mm dowel pins
             │     │          carriage          │────┤ knob (lever)
             │     └────────────────────────────┘    │
             └──────────────────plate─────────────────┘
```

**Both notches are filled**, so a key put in the other way up still locks (USB-C is reversible).

**Power comes on after the lock, and goes off before it.**
- A D2F-size microswitch sits plunger down over a tab on the carriage.
- The tab reaches the plunger only in the last 0.4 mm of travel, when the pin tops are 3.3 mm past
  the board's top face.
- On the way down the switch opens in that first 0.4 mm (plus its own differential travel), while
  the pins still cross the board.
- Wire it in the console's USB 5 V feed. This is rev A's DETECT rule again: mates last, breaks
  first.

**A key that isn't fully in can't be locked.**
- The key's end seats against a 1 mm lip, at the stop.
- A key short of the stop puts board, not notch, over a pin. The pin meets the board and the lever
  won't go up.

**A detent** holds the lever up or down: a thin beam across the carriage's back has a bump that
clicks into one of two grooves.

**The console's USB-C plug** sits in a pocket behind the stop. The channel guides the key, so the
plug carries no side load. The lip's window (9.4 × 4.0 mm) passes the plug's metal shell (8.25 ×
2.40).

> [!WARNING]
> Don't wire the plug to the Pico until the console end of key-c exists
> ([PROPOSALS.md](../key-pcb/PROPOSALS.md#the-console-end-of-key-c)): a current-limited,
> reverse-blocking VBUS switch, CC1 and CC2 sensed separately, and 2.2 kΩ pull-ups. The cartridge's
> power switch cuts the console's own power; it is not that VBUS switch.

## Two modes

| | `P3` (default) | `P2` |
|---|---|---|
| for | key-c P3, with the edge notches | the key-c P2 boards in production now, which have none |
| key | half in (19 mm), lanyard end out | all in, flush, with finger cut-outs at the mouth to pinch it out |
| pins | 2 × 2 × 12 mm, one in each notch | 1 × 2 × 16 mm, through the lanyard hole H1 |
| travel | 5.6 mm | 7.7 mm (the pin rises through the taller tunnel over the receptacle) |
| size, with the plate (the knob adds 7 mm to the width) | 31.5 × 31 × 23 mm | 31.5 × 48 × 28 mm |

P2 is a bench cradle for trying the lock and switch with real boards before P3 exists.

## Files

| path | what |
|---|---|
| `cartridge.py` | writes everything below, after its fit checks pass |
| `p3/`, `p2/` | `body`, `carriage`, `plate` and `coupon`, as `.stl` (to print) and `.step` (for CAD); `assembly.step` has the body, carriage, pins and dummy key in place, locked |

```sh
pip install cadquery
python3 hardware/case/cartridge.py        # P3
python3 hardware/case/cartridge.py P2
```

The key's numbers come from `../key-pcb/gen_cd.py` (board size, `NOTCH_Y`, `NOTCH_R`, the licence
text). The dummy key used in the checks is `../key-pcb/key-c-usbc/3d/print_mockup.py`. So the bay
can't drift from the board. The frame is the key's own STEP frame: origin at the board centre,
Z = 0 the key's back face, USB-C end at −Y, mm, with the key seated.

**What `check()` proves before anything is written:**
- Each part is one valid solid.
- With the carriage up and down:
  - The carriage clears the body and the plate.
  - The pins clear the body and the seated key.
- The seated dummy key clears the body.
- A key pulled 2 mm towards the mouth hits the pins when they're up, and clears them when down.
- The switch operates within its rated overtravel, before the tab could touch its body, and only
  with the pin tops at least 1 mm over the board.
- The plate's text stays on the plate and clear of the screw heads.

It checks the geometry against the dummy key, not a real board. Printing is the real test.

## Parts

| part | qty | notes |
|---|---|---|
| 2 mm steel dowel pin, 12 mm (P3) or 16 mm (P2) | 2 (P3), 1 (P2) | hardened, h6 |
| microswitch, D2F size (12.8 × 5.8 × 6.5 mm body, pin plunger) | 1 | set `SW_AT_OP` and `SW_OT` from your switch's datasheet |
| USB-C male plug breakout | 1 | measure it, and set `PLUG_W` and `PLUG_H` (its pocket, 12.4 × 8.0 now) |
| M2 × 8 screws for plastic | 4 | the plate |

## Printing and putting it together

1. **Print the coupon first.** It's a small slice of the bay round the pins.
   - Slide a key (or the P3 dummy, `../key-pcb/key-c-usbc/3d/print_mockup.py P3`) in.
   - Push a dowel up through each bore by hand.
   - The key should slide with light friction, and the pins should pass through both notches.
   - If not, change `CLR` (0.2 mm a side now) and print it again.
2. **Body:** top face down on the bed. The chamber, the lever slot and the switch pocket then open
   upwards, and the channel's ceiling is a 16 mm bridge. No supports.
3. **Carriage:** underside down. The tab, arm and knob all start there.
4. **Plate:** text side up, so the text prints clean.
5. PLA or PETG. PETG for the detent beam if PLA cracks.
6. **Assemble:**
   1. Press the dowels into the carriage, flush with its underside. If they're loose, use a drop of
      CA glue.
   2. Drop the microswitch into its pocket from the top, plunger down. It rests on two ledges.
      Wire COM and NO in series with the console's 5 V.
   3. Put the carriage in from below, its arm in the lever slot. Screw on the plate.
   4. Seat a key at the stop, then glue the plug breakout in its pocket so the plug is fully home.
7. **Check:**
   - With a meter on the switch, the lever closes it only at the very top.
   - Moving down, it opens before the key can be pulled.
   - With the key short of the stop, the lever won't go up.

## Open

- [ ] Print it, and tune `CLR`, the detent and the switch's height on the bench
- [ ] The switch numbers (`SW_AT_OP` 0.7, `SW_OT` 0.5) are typical of a D2F, not measured
- [ ] A turning knob with a cam on the same carriage, instead of the straight lever
- [ ] The rest of the console's case round it (the kickoff's [open decisions](../../docs/KICKOFF.md#open-decisions))

## License

Copyright Jason McPheron 2026. CERN-OHL-W v2, like the rest of `hardware/`: see
[hardware/README.md](../README.md#license) for the notice and the Source Location. The plate
carries both on its underside:
- `PicoQuorum`
- `github.com/jmcpheron/pico-quorum`
- `CERN-OHL-W-2.0`

The name and the mark are not part of the licence ([TRADEMARK.md](../../TRADEMARK.md)): a
cartridge you change carries your name, with the Source Location.
