# Adafruit's Feather ESP32-S3 Reverse TFT

A ready-made board: an ESP32-S3 with a 240 × 135 screen, three buttons, a battery charger and a
STEMMA QT socket, all on one Feather ([Adafruit 5691](https://www.adafruit.com/product/5691)). No
breadboard: a key plugs into the I2C pins and that's the whole build.

**The console runs on it.** On 2026-10-22 the dual image booted it for chip 3: pinned, on Wi-Fi,
watching a Base Sepolia Safe. `firmware/board.py` has its `"feather-s3"` profile. The review,
Sign and the key's QR code work on three buttons in the emulator, not yet on the board
([below](#the-console-on-the-feather), screenshots in
[docs/quorum-ui/feather](../../docs/quorum-ui/feather/README.md)).
[The ceremony](#the-ceremony-on-the-feather) works on them too, and chip 3 went through it on the board. The status
home and the claim on three buttons are still to come. [`feather-s3/`](feather-s3/) holds the
first bench test (the screen, the buttons and the key's ATECC608, read-only), which is not part of
any image.

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

A board that gives key-c a port of its own behind the Feather, on the header pins, is drawn in
[hardware/feather-wing](../feather-wing/README.md) (wing-a, not ordered).

The same Feather with a USB-C cable soldered straight to SDA, SCL, 3V and GND, no adapters, a
screen that reads whichever key is plugged in, and a case:
[builds/feather-pigtail](../builds/feather-pigtail/README.md).

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

Every address page of a review (to, from, the owner replaced and the new one, a spender, a contract,
and each of these in every call of a batch) draws the address's blockie, 40 px, beside its short last line: the picture
Safe{Wallet} and Etherscan draw for it. A token's amount page has the token contract's, and
approvals and Owners one for each owner. `case_three` checks each is drawn, on the screen and clear
of the text, for a send, a token send, a swapOwner and a MultiSend batch.

**Key**, past Owners and Device on home, shows the key's owner address as a QR code, then in full
(D1 switches, D0 back). A console with no Safe yet says "Your key is ready" and D2 opens the same
screen; a Safe that doesn't list the key says "Not an owner yet" ([ONBOARDING.md](../../docs/ONBOARDING.md)).

Still to come: the status home, the battery, noticing a key plugged in or pulled out, and the claim
on three buttons. On the Feather the banner offers nothing for a branded chip until then.

## The ceremony on the Feather

The dual image sends a fresh chip to the ceremony, C1–C10 ([PROVISIONING.md](../../docs/PROVISIONING.md)).
`setup_s.py` draws it on 240 × 135 and reads the three buttons as the Pico's: D0 is Y, D1 is B, D2
is A. So the steps, checks and gates are `provision.UI`'s own:

| | |
|---|---|
| D2 on the banner | opens PROVISION |
| D0 | back; on a result, OK |
| D0 + D1 held 3 s | the arm, for 60 s (the Pico's B+Y). D2 is never part of it |
| D2 | a step; on a permanent or GenKey step (C3, C4, C6, C9), held 3 s once armed, started with 10 s or more of the arm left. On a result, OK |

`ALLOW_LOCK` and `ALLOW_GENKEY` in the board's `secrets.py` still gate every permanent step
(`tools/fw allow on`). `node test-vectors/run-ceremony.mjs` walks C1–C10 on a virtual 608C through
the buttons alone, in a device of its own with `BOARD = "feather-s3"`. It also checks that D2 held
without the arm does nothing, D1 + D2 is no arm, an arm let go at 2 s is none, ALLOW_LOCK off
stops C3 even when armed, C6 with 9 s of the arm left says arm again and seals nothing, a refusal
names D0+D1, and every screen fits 240 × 135. Screenshots:
[docs/quorum-ui/feather-setup](../../docs/quorum-ui/feather-setup/README.md).

On hardware, 2026-10-22: chip `0123147ac8c5b889ee`, a key-c's ATECC608C, went from factory-fresh to
sealed on the board's buttons, build `2cd9354c`. Owner `0x031B2c6038aB0d15e62eC2D2D21D84878e13250e`,
checked on the laptop afterwards ([the build log](../../buildlog/BUILDLOG.md)). One C6 attempt was
refused: its hold started with about 4 s of the arm left and the arm ran out before the lock. The
10 s rule above came from that.

## Writing to it

`tools/fw` drives the board with mpremote. On this board, mpremote 1.29's sessions sometimes reset
it (a watchdog reset), as they close or partway through, about one session in three after a
restart, so `tools/fw push` fails partway. The files it had copied were whole. On 2026-10-22 the
push of the dual image was finished over plain serial instead ([the build log](../../buildlog/BUILDLOG.md)).
When mpremote's only error is the port gone, `tools/fw` now waits for the board to come back and
judges the step by what the board printed, so a step cut short still stops it. Not fixed yet.
