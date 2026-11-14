# console-s3 rev A: the second board

Jason soldered a WROOM-1 onto a second console-s3 board on 2026-11-13, with its panel in the ZIF.
What was run on it from the Mac, in order, and what came back. The first board's day is
[2026-11-02-console-s3-first-board.md](2026-11-02-console-s3-first-board.md).

## 1. The empty module

- Espressif's `USB JTAG_serial debug unit` (303A:1001), serial `A4:CB:8F:B1:18:BC`, on
  `/dev/cu.usbmodem3101`.
- esptool 5.6.0, read only: ESP32-S3 (QFN56) revision v0.2, 2 MB embedded PSRAM, flash `c8`/`4017`,
  8 MB, quad: an N8R2, as the design asks. The first 4 KB of flash read all `0xFF`.
- `tools/board/newboard.py`: the ROM printed `invalid header: 0xffffffff` hundreds of times between
  restarts, `rst:0x7 (TG0WDT_SYS_RST)`, `boot:0x28`, so GPIO0 read high at reset. Unlike the first
  board, it stayed on USB for the 20 s it was watched.

## 2. MicroPython 1.26.1

`ESP32_GENERIC_S3-20250911-v1.26.1.bin` from micropython.org, 1,735,456 bytes, SHA-256
`d6c48687…dcdbbc`, the hash `newboard.py` pins: `newboard.py --flash` erased the flash, wrote it,
and esptool verified it. It came up with `Performing initial setup`, then the prompt.

## 3. The parts check, and D0 bridged to the screen's MOSI again

`newboard.py`'s check from RAM picked console-s3's pins (no pull-ups on GPIO16/17), and passed the
flash (8 MB), the PSRAM (2001 kB free), the key bus (only `0x60`) and 20 s with no restart. The
ATECC608C answered with serial `0123182000ec297dee`, config and data unlocked: factory fresh, and
nothing on it was written then or since.

| run | buttons at rest | then |
|---|---|---|
| 1 | none pressed | "D0 pressed" at 3739 ms, never released; D1 and D2 never seen |
| 2 | D0 pressed | "D0 pressed" at 3733 ms, never released; D1 and D2 never seen |

3.7 s is when the check has set the screen up and starts watching the buttons. Run 2 began with D0
low because run 1's SPI was still holding MOSI low. The first board's follow test, from RAM: each
pin driven low, then high, then let go, with GPIO0 (D0 and BOOT), GPIO1 (D1) and GPIO2 (D2) read
after each.

| driven | G0 D1 D2: low / high / released |
|---|---|
| GPIO35, MOSI | **000** / 100 / 100 |
| GPIO45, BL | 100 / 100 / 100 |
| GPIO36, SCK | 100 / 100 / 100 |
| GPIO40, DC | 100 / 100 / 100 |
| GPIO42, CS | 100 / 100 / 100 |
| GPIO41, RST | 100 / 100 / 100 |

GPIO0 followed GPIO35 and nothing else: the first board's fault, a bridge between the module's pads
27 (`/BTN_D0`) and 28 (`/LCD_MOSI`), 0.37 mm apart.

## 4. The console image

The console image of main 9f0d93df (`tools/fw build console` in a clean worktree): 2026.11.3, 55
files, release 1eeb·bf43, the README's fingerprint. `tools/fw push` goes through mpremote, which
wedges on these boards, so `tools/board/rawcopy.py` copied it: raw-paste in 64-byte pieces over
plain serial, each file's SHA-256 checked on the board before it took its name, `boot.py` and
`main.py` last. 55 files, 272,411 bytes, in 71 s, none sent twice.

After the restart the link's `hello` answered `console`, `2026.11.3`, `9f0d93df`, the release, board
`feather-s3`, mode `setup`: Wi-Fi setup, its hotspot `Picoquorum-18BC`, no `secrets.py`, not pinned.
In the first minute after the restart the port went away three times while `hello` was being
asked. Not explained. It then stayed on USB 40 s with the port closed and answered every time.

## 5. Reflowed

Jason reflowed the module's pads. In Wi-Fi setup the buttons moved round its pages. To reach the
REPL: D1 held at power-up (`boot.py`'s maintenance key; setup mode's link takes only a Wi-Fi ask).
Then `newboard.py` again, in maintenance:

```
buttons-at-rest  ok    none reads pressed
key-chip         ok    serial 0123182000ec297dee
  press D1 7431 / release 7682,  press D2 8560 / release 8883,  press D0 9822 / release 9964
buttons          ok    D0 x1 D1 x1 D2 x1, each alone
soak             ok    20 s more on USB without a restart
PASS: 15 checks, 0 failed
```

D0 now pressed and let go with the screen's SPI running, and three more D0 presses, a D1 and a D2
came in the soak. The follow test again: GPIO0 read 1 with GPIO35 low, high and let go, and with
the other five. Then a restart, and the console answered `hello` as before.

## What this says

Both boards with a module soldered by hand had the same bridge at pads 27 and 28, and on both it
showed the same way: D0 reads pressed from the moment the screen's SPI starts. When `newboard.py`
says D0 was pressed at that moment and never let go, run the follow test before anything else.
