# Adafruit's Feather ESP32-S3 Reverse TFT

A ready-made board: an ESP32-S3 with a 240 × 135 screen, three buttons, a battery charger and a
STEMMA QT socket, all on one Feather ([Adafruit 5691](https://www.adafruit.com/product/5691)). No
breadboard: a key plugs into the I2C pins and that's the whole build.

**The console doesn't run on it yet.** What runs is a bench test in [`feather-s3/`](feather-s3/):
the screen, the buttons and the key's ATECC608, read-only. It is not part of the console image.

On hardware, 2026-10-20: the screen showed the test, and the spare 608C on a key-c
(`0123e063db3354d7ee`) answered at 0x60 through USB-C adapters. See
[the build log](../../buildlog/BUILDLOG.md).

## The board

What esptool and MicroPython read from this one:

| | |
|---|---|
| USB | `239A:8123`, "Feather ESP32_S3 Reverse TFT", as `/dev/cu.usbmodem…` on macOS |
| chip | ESP32-S3 |
| flash | 4 MB, quad |
| PSRAM | 2 MB: MicroPython's heap starts with about 2 MB free |
| on the I2C bus | a MAX17048 battery gauge at **0x36** |

## Pins

From Adafruit's pinout. The screen and I2C rows were checked on this board, the buttons were not.

| what | GPIO | notes |
|---|---|---|
| I2C SDA | 3 | the SDA header pin and the STEMMA QT socket: one bus |
| I2C SCL | 4 | |
| TFT and I2C power | 7 | drive high, or the screen and the STEMMA QT's V+ stay off |
| TFT SCK, MOSI | 36, 35 | SPI(1); also on the header as SCK and MO |
| TFT CS, DC, RST | 42, 40, 41 | |
| TFT backlight | 45 | high is on |
| button D0 | 0 | pull-up, **low** when pressed; also BOOT |
| buttons D1, D2 | 1, 2 | pull-down, **high** when pressed |

The screen is an ST7789 with a 135 × 240 window in its 240 × 320 RAM. Landscape with the buttons on
the left is `MADCTL = 0x60` with offsets x 40, y 53. It needs inversion on (`0x21`). The column and
row addresses go past 255, so they are two bytes each.

## The key

A key-c's D+ is SDA and D− is SCL ([ESP32.md](ESP32.md#the-chip)). The Feather has pull-ups on
SDA and SCL, so the key needs none, but they are powered from IO7.

What it took on 2026-10-20: through the USB-C adapters the chip first never answered, with D+ and
D− either way round, at 20, 100 or 400 kHz, or after a 1 ms wake pulse. A scan of every pair of the
20 header pins found only the gauge. The key was then unplugged, and once it was back in, 0x60
answered. What changed in the adapters wasn't recorded. So when 0x36 answers and 0x60 doesn't, the
bus is fine: look at the key's wiring and power.

`firmware/atecc.py`'s `KNOWN_ADDRS` includes 0x36. If 0x60 doesn't answer, `ATECC608()` with no
address would talk to the battery gauge. The bench scripts pass `addr=0x60`.

## Try it

**1. MicroPython 1.26.1**, the `ESP32_GENERIC_S3` build from
[micropython.org](https://micropython.org/download/ESP32_GENERIC_S3/). That build finds the flash
size and the PSRAM itself. `ESP32_GENERIC_S3-20250911-v1.26.1.bin` had SHA-256
`d6c48687f684cc7c002a0a4acd258f881c4b391f3ef121726a3b7cd285dcdbbc`.

```sh
export PICO_PORT=/dev/cu.usbmodem3101
esptool --chip esp32s3 --port $PICO_PORT --baud 460800 write-flash -z 0 ESP32_GENERIC_S3-20250911-v1.26.1.bin
```

From Adafruit's factory demo, esptool put the board into its bootloader on its own; no buttons.
The port goes away and comes back as "USB JTAG/serial debug unit" (same name here). An
`erase-flash` straight after another esptool command failed because the port was still coming
back; the write without it worked. If esptool can't connect, hold D0 and press Reset.

**2. The bench test.** From the repository root:

```sh
F=hardware/wiring/feather-s3
mpremote connect $PICO_PORT fs mkdir :bench + \
  fs cp $F/board.py :bench/board.py + fs cp $F/tft.py :bench/tft.py + \
  fs cp firmware/atecc.py :bench/atecc.py + fs cp firmware/chipcfg.py :bench/chipcfg.py + \
  fs cp $F/scantest.py :bench/scantest.py + fs cp $F/main.py :main.py + reset
```

`board.py` here is a stand-in with just the bus pins, so `atecc.py` imports without the console's.
It goes in `/bench`, never at the top, where the real one would go.

The screen's top lines show the chip, its slot table and its locks. Then:

| button | what the chip does |
|---|---|
| D0 | 32 random bytes, as hex and a grid of colours. `ffff0000…` means the config is open |
| D1 | SHA-256 of `PicoQuorum 1`, `2`, …; MATCH when MicroPython's `hashlib` agrees |
| D2 | its self-test: RNG, ECDSA verify and sign, ECDH, AES, SHA |

None of it makes, reads or uses a key, or writes or locks anything. Random updates the chip's own
seed, as the console's Random does. A key that doesn't answer should show CHIP ERROR; plug it in
and press again. That screen and the buttons haven't been seen on the board yet; each command was
run once from a script (the build log).

`scantest.py` is the first test: the battery voltage, the buttons, and every I2C address that
answers, three times a second. Run it with `mpremote connect $PICO_PORT run $F/scantest.py`.

## What the console would need

`firmware/board.py` picks its `"esp32"` profile on anything where `sys.platform == "esp32"`, and
an S3 is one. Its pins don't fit:

- SCL is GPIO22 and the knob's press GPIO25. The S3 has no GPIO 22 to 25.
- The screen's DC is GPIO19. On the S3, 19 and 20 are the USB port.

So the console image would stop at startup. Running it here means:

- a `"feather-s3"` profile in `board.py`, picked by the chip (`os.uname().machine` names the S3)
- 0x36 out of `atecc.py`'s fallback addresses on this board
- the console's screens laid out for 240 × 135, the smallest yet
- the three buttons for Sign, Reject and Back, with D0 the other way round from D1 and D2

That is a firmware change and a new release. Not started.
