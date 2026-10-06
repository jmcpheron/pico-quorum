# The dev console

The quickest PicoQuorum console to build: three off-the-shelf parts, about $35, no soldering, an
evening. It runs the same console image as every other build. Its key is an ATECC608 breakout (or
an Infineon OPTIGA Trust M, [TRUSTM.md](../docs/TRUSTM.md)) until the [plug-in key](key-pcb/) is
ready.

This build comes from Austin Griffith's [picowallet](https://github.com/austintgriffith/picowallet),
which first put a Pico, this screen and an ATECC608 together; its README is the original guide.

## Parts

| part | ~price | notes |
|---|---|---|
| Raspberry Pi Pico 2 W, with headers | $12 | any Pico 2 W with a pre-soldered header |
| Waveshare Pico-LCD-1.3 | $15 | 240 × 240 IPS, a joystick and A/B/X/Y |
| Adafruit ATECC608 breakout, STEMMA QT (4314) | $6 | or a Trust M breakout |
| STEMMA QT / JST-SH 4-pin cable, one end bare | $1-8 | Adafruit 4209, snipped and stripped, works |
| micro-USB cable that carries data | | |

The full list, with the parts for the other builds, is in [bom/](bom/README.md).

## Wiring

1. Plug the Pico into the LCD board's header: components toward the screen, USB at the joystick
   end.
2. Plug the cable into the breakout.
3. Push the cable's four bare ends into the LCD board's header sockets **beside** the Pico's pins;
   the spring contacts hold both. Counting from the USB end:

   | wire | pin | signal |
   |---|---|---|
   | red | 36 | 3V3 |
   | black | 38 | GND |
   | blue | 6 | GP4 (SDA) |
   | yellow | 7 | GP5 (SCL) |

4. Tuck the breakout into the gap between the boards, wires flat.

If GP4/GP5 are taken on your board, any two free GPIOs work: set `ATECC_SDA` and `ATECC_SCL` in the
board's `secrets.py`. A soldered version, with an 18650 cell behind a switch and a diode, is in
[wiring/SOLDERING.md](wiring/SOLDERING.md).

A printed case: Tomáš Plass's
[Waveshare Pico 1.3 LCD case](https://www.printables.com/model/1322102-waveshare-pico-13-lcd-case)
(CC BY-NC 4.0) fits this stack.

## Software

1. **MicroPython.** Hold BOOTSEL while plugging the Pico in, then `tools/emu flash --wifi` (or drag
   [the Pico 2 W build](https://micropython.org/download/RPI_PICO2_W/) onto the `RP2350` drive).
2. **The chip.** A fresh chip goes through the ceremony once. Some steps are permanent: read
   [PROVISIONING.md](../docs/PROVISIONING.md) first, and run `python3 tools/check_config` before
   anything locks.
3. **The console.** [The owner's guide](../docs/guide/SETUP.md) takes it from there: `tools/fw push
   console`, the board's `secrets.py`, and your Safes.

No hardware yet? `tools/emu` runs the same firmware in a browser on your laptop, with a virtual
chip.
