# wiring

Console and key schematics and pinouts. Draft only.

Build 1 (Pico 2 W, 2.0″ screen, EC11 knob, 3.5 mm + 2.5 mm TRRS jacks, ATECC608 stand-in key):
[BUILD1.md](BUILD1.md), drawn by `tools/wiring-build1`.

## Key connector: draft pinout

| Plug | Contact | Signal |
|---|---|---|
| ¼″ TRS | Tip | SDA |
| ¼″ TRS | Ring | SCL |
| ¼″ TRS | Sleeve | GND |
| 3.5 mm | Tip | VCC (3.3 V, console-switched) |
| 3.5 mm | Ring | Spare |
| 3.5 mm | Sleeve | GND |

## Design rules

- The shorter 3.5 mm plug mates last and breaks first, which sequences power mechanically.
- The console enables key power **only** after the switched jack's detect contact confirms full
  insertion, and cuts it immediately on removal.
- Key VCC gets a current-limited load switch, so a stray headphone or guitar cable can't do damage.
- SDA, SCL, and VCC get ESD/TVS protection at the jacks.
- I2C pull-ups live on the console side.
- Both jacks mount on one rigid bracket or PCB. One plug on the key gets slight float so it
  self-aligns.

## Open

- [ ] Pico GPIO assignment: key I2C (upstream uses GP4/GP5), jack detect, load-switch enable,
      encoder, Sign, Reject, status LED, screen SPI
- [ ] Load switch and TVS part numbers
- [ ] Does the ATECC608 or the Trust M need anything beyond a decoupling cap on the key side?
