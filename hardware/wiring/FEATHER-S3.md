# Adafruit's Feather ESP32-S3 Reverse TFT

A ready-made board: an ESP32-S3 with a 240 × 135 screen, three buttons, a battery charger and a
STEMMA QT socket, all on one Feather ([Adafruit 5691](https://www.adafruit.com/product/5691)). No
breadboard: a key plugs into the I2C pins and that's the whole build.

**The console runs on it in the emulator, not yet on the board.** `firmware/board.py` has its
`"feather-s3"` profile and the review and Sign work on three buttons ([below](#the-console-on-the-feather),
screenshots in [docs/quorum-ui/feather](../../docs/quorum-ui/feather/README.md)). The status home,
the key screens and setup on three buttons are still to come. What runs on the board itself is a
bench test in [`feather-s3/`](feather-s3/): the screen, the buttons and the key's ATECC608,
read-only. It is not part of the console image.

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
| on the I2C bus | a MAX17048 battery gauge at **0x36**, version `0012` |
| HTTPS | the console's own check passes (below) |

## Pins

From Adafruit's pinout. The screen, I2C and button rows were checked on this board
(`feather-s3/stage0.py`, 2026-10-21): at rest D0 reads 1 and D1, D2 read 0, with or without
MicroPython's pulls, and each reads the other way while pressed. No bounce showed at a 20 ms poll.

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
| LED | 13 | red; `stage0.py` blinked it (seen 2026-10-21) |

The screen is an ST7789 with a 135 × 240 window in its 240 × 320 RAM. Landscape with the buttons on
the left is `MADCTL = 0x60` with offsets x 40, y 53. It needs inversion on (`0x21`). The column and
row addresses go past 255, so they are two bytes each.

In landscape with USB on the left, D0 is level with rows 0–14 of the screen, D1 with rows 60–74
and D2 with rows 120–134 (`board.RAIL_Y`, read off the board with `stage0.py`'s numbered bands).

Held at reset, D0 starts the ROM bootloader, so the console never asks for it at power-up:
maintenance is D1 held, Wi-Fi setup D2 held (`board.MAINT`, `board.SETUP`).

## HTTPS

`tools/board/measure_tls.py`, the check `tools/fw measure tls` runs, with a Wi-Fi join in front, on
2026-10-21 from RAM: 10 of 10 calls to `api.safe.global` checked against the console's pinned roots
(median 561 ms, worst 811 ms), and `expired`, `wrong.host`, `self-signed` and `untrusted-root` at
badssl.com refused, each on its certificate. A real 10-transaction queue came back. About 1.3 MB of
heap stayed free throughout.

## The key

A key-c's D+ is SDA and D− is SCL ([ESP32.md](ESP32.md#the-chip)). The Feather has pull-ups on
SDA and SCL, so the key needs none, but they are powered from IO7.

What it took on 2026-10-20: through the USB-C adapters the chip first never answered, with D+ and
D− either way round, at 20, 100 or 400 kHz, or after a 1 ms wake pulse. A scan of every pair of the
20 header pins found only the gauge. The key was then unplugged, and once it was back in, 0x60
answered. What changed in the adapters wasn't recorded. So when 0x36 answers and 0x60 doesn't, the
bus is fine: look at the key's wiring and power.

`firmware/atecc.py`'s `KNOWN_ADDRS` includes 0x36. On the Feather, `board.NOT_KEYS` takes it out
(`atecc.KEY_ADDRS`), so neither `ATECC608()` nor `signer.detect()` takes the battery gauge for a key.
The bench scripts, which use their own stand-in `board.py`, pass `addr=0x60`.

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

**3. The checks before the console** (`stage0.py`, needs `/bench/tft.py`): the screen in numbered
bands of 15 rows, each button's level as it is pressed, the LED blinked, and the gauge every 30 s,
for three minutes. Reads only.

## The console on the Feather

The classic ESP32's `"esp32"` profile can't run here: its SCL is GPIO22 and its knob's press GPIO25,
which the S3 doesn't have, and its screen's DC is GPIO19, one of the S3's USB pins. So
`firmware/board.py` now picks `"feather-s3"` on any ESP32-S3 (`os.uname().machine` names it; the
emulator picks it with `secrets.BOARD`):

- the screen as in the table, drawn whole (`BANDS = 1`, 64.8 KB in PSRAM), at (40, 53) in the
  panel's RAM (`RAM_X`, `RAM_Y`, added in `lcd._window`)
- the buttons by their own pulls: `board.HIGH` lists the pulled-down ones, which `lcd.Keys` and
  `board.key_down` read the other way round. D1 held 1 s is a key of its own, `"D1L"`, then again
  every 500 ms
- GPIO7 driven high as `board.py` is imported, before the screen or the key is touched
- `THREE = True`: the three buttons, below

`python3 test-vectors/feather_s3_test.py` runs these paths on CPython against a stand-in of the
S3's MicroPython, and CI runs it.

The buttons (`quorum.three()`), each turned into what a button or the knob already does there, so
the rules stay where they are:

| | on a review | anywhere else |
|---|---|---|
| D0 | Reject: one press, on any page, even while Sign is held | Back |
| D1 | the next page (round to the first after the last); held 1 s, the one before; held on the first page, out without rejecting | the next row or choice; held, the one before |
| D2 | the next page not yet seen; once every page is seen, Sign, held 2 s (3 s when a page is red) | Open; Check again on the no-chip and not-pinned screens |

The screens are `quorum_ui_s.py`'s small ones, moved right of a 36 px rail that names what each
button does, level with it; while Sign is held the rail fills from the bottom, green or red.
`node test-vectors/run-console.mjs` runs `console_test.case_three` in a device of its own with
`BOARD = "feather-s3"`: refusals, the unseen pages, the holds to the millisecond, Reject from every
page and during the hold, the moves, and that every page of a review fits 240 × 135.

Still to come: the status home and the key screens (what a key plugged in is, and where it goes),
the battery, noticing a key plugged in or pulled out, then the ceremony and the claim on three
buttons. The Feather will run the dual image, so a blank key can be set up on it, behind the same
flags and holds as on the Pico.
