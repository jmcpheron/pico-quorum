# The STEMMA QT breakout footprint: ATECC608 (4314) and Trust M (4351)

Both chip boards use the same Adafruit footprint: 1.0" × 0.7", four corner holes, and a STEMMA QT
socket on each short edge. A case, cradle or standoff pattern built for one fits the other. The
same outline is used by dozens of other Adafruit STEMMA QT sensor boards, but not by every one.

The numbers come from Adafruit's EagleCAD files (`.brd`, read 2026-10-01). Both boards gave the
same values to 0.01 mm:

- ATECC608: [adafruit/Adafruit-ATECC608-PCB](https://github.com/adafruit/Adafruit-ATECC608-PCB)
- Trust M: [adafruit/Adafruit-Infineon-Trust-M-PCB](https://github.com/adafruit/Adafruit-Infineon-Trust-M-PCB)

Adafruit's Fritzing parts are also usable for layout:
[Fritzing-Library](https://github.com/adafruit/Fritzing-Library). Neither repo has a STEP model
or a dimensioned drawing, so this page is the drawing.

## Coordinates

The origin is the bottom-left corner, with the board flat, components up, and the 0.1" header row at
the bottom. Units are mm.

| Feature | Position | Size |
|---|---|---|
| Board outline | 0,0 to 25.40, 17.78 | 1.6 mm FR4 (standard; not stated in the file) |
| Corner radius | all four | R 2.54 |
| Mounting holes, plated | (2.54, 2.54) (22.86, 2.54) (2.54, 15.24) (22.86, 15.24) | 2.5 mm drill, 3.2 mm pad. Takes M2 or M2.5 screws |
| Hole pitch | 20.32 × 12.70 | 0.8" × 0.5" |
| STEMMA QT socket, left | centred at y 8.89, facing −x | JST SH 4-pin horizontal; pads span x 1.15–5.05, y 6.09–11.69 |
| STEMMA QT socket, right | centred at y 8.89, facing +x | pads span x 20.35–24.25, y 6.09–11.69 |
| Header row | y 2.54, on the line between the two bottom holes | 1.0 mm drill, 0.1" pitch |
| ATECC608 header | 4 pins at x 8.89, 11.43, 13.97, 16.51 | VIN GND SCL SDA |
| Trust M header | 5 pins at x 7.62, 10.16, 12.70, 15.24, 17.78 | one more pin than the ATECC |
| Chip | centred at (12.70, ~8.7) | the middle of the board |
| Overall height | 4.7 mm per Adafruit | PCB plus the JST sockets, the tallest parts |

The header pin count is the one difference that matters for a case. A slot for the header row
should be wide enough for 5 pins: x 6.4 to 19.0 clears both boards.

## Designing around it

- **Cable clearance.** A STEMMA QT plug sticks out about 8–10 mm from each short edge before the
  cable bends. Leave a cable channel on the side you use, or both sides if the board is in a chain.
- **Hold-down.** Four M2 or M2.5 standoffs on the 20.32 × 12.70 grid. A drop-in pocket of
  25.6 × 18.0 mm works too, with a lip or a printed clip. The plated holes aren't connected to any net, so metal screws are fine.
- **Underside.** The back is flat except for solder joints, if header pins are soldered on.
- **Revisions.** Adafruit updated the ATECC608 board in December 2023, but only the silkscreen
  changed (per the product page). Older boards have the same footprint.

## Not the same as Qwiic

SparkFun Qwiic boards use the same JST SH cable and pinout, so they work electrically. Their board
sizes and hole patterns are SparkFun's own, so check a Qwiic board against this page before
reusing a case.
