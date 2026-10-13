# The console on an M5Stack Cardputer v1.1

A Cardputer v1.1 (Stamp-S3A: ESP32-S3, 8 MB flash, **no PSRAM**, 240x135 ST7789V2, a 56-key
keyboard) as a PicoQuorum console, with an ATECC608 on its Grove port. Branch
`claude/cardputer-console`, three commits: `0cb6c06`, `36ddf80`, `61f8b85`. It ended with both Base
Sepolia Safes `ok, owner` and a queued transaction found. Signing on the device is not tried yet.

## 1. The board profile (`0cb6c06`)

`board.py` gets a `cardputer` profile, picked whenever the chip is an ESP32-S3. The pins are the
Stamp-S3A's own, checked on the bench:
- Screen: MOSI 35, SCK 36, DC 34, RST 33, CS 37, BL 38. MADCTL `0x60`, and the 240x135 glass sits at
  x=40, y=52 in the controller's RAM. Drawn in 5 bands of 27 rows.
- Keyboard: a 74HC138 on G8/G9/G11 picks a line, G13, G15 and G3–G7 read it (`lcd.Keys`). `;` `.`
  are up and down, `,` `/` left and right, Enter presses, Del is back. Enter held at power-up is
  maintenance, S is Wi-Fi setup. Not G0: held at reset, it starts the ROM bootloader.
- The key: Grove G2 SDA, G1 SCL. Grove gives 5 V and the key needs 3.3 V, so it goes through an
  adapter (`hardware/bom/README.md`).
- The 240x135 screen uses the small-screen pages (`quorum_ui_s.py`).

## 2. Stock MicroPython doesn't fit (`36ddf80`)

On stock `ESP32_GENERIC_S3` MicroPython the heap is about 205 KB, and every imported module's
bytecode lives in it. The console stopped with a `MemoryError` before `quorum.py` had loaded.

So `tools/micropython-s3` builds MicroPython v1.26.1 (ESP-IDF v5.4.2, both pinned by commit) for a
`PICOQUORUM_CARDPUTER` board:
- **ROMFS**: a 1 MiB partition mounted at `/rom`. `tools/fw push` puts the image's compiled modules
  there and checks each one's hash where it landed. Their bytecode runs from flash and takes no RAM.
  242 KB free at boot, about 139 KB after importing the console.
- **No Bluetooth**: nothing uses it, and its RAM goes to the heap.
- **The REPL on the S3's USB-Serial-JTAG port, not TinyUSB.** TinyUSB jumps to the bootloader on a
  DTR/RTS pattern that macOS made as mpremote closed and reopened the port, so the board fell off
  USB between `tools/fw`'s sessions. On the hardware port, sessions are stable.

## 3. "It finds the chip but not the Safe"

The key answered at `0x60`, but the console showed no Safe. The board had no `secrets.py`: the
`erase_flash` before the new MicroPython took it. It got a new one, made from the Pico console's
backup (the Safes, `QUORUM_EXPECT`, the API key; Wi-Fi stays in `wifi.json`). It is on the board
only, never in the repository. The chip's pin then passed.

## 4. Then every request failed: `OSError 12` (`61f8b85`)

With the Safes known, every HTTPS request failed with `OSError 12` (out of memory), and later Wi-Fi
stopped starting.

**Why:** stock MicroPython grows its Python heap into the IDF heap whenever an allocation fails
after a collection, by its own size or by the largest block left. The console's ~150 KB live and its
fragmentation grew the heap to 239 KB. That left the IDF heap no block over 8 KB, and Wi-Fi and TLS
allocate from there.

**What didn't work:**
- A 192 KB starting heap: it still grew.
- Fonts read in place from ROMFS: saved 34 KB, but it still grew.
- A fixed 208 KB heap that never grows: now the IDF heap starved instead (Wi-Fi "Internal Error",
  `-116` timeouts), and on some boots `quorum.py` didn't import.

**Measured** with the heap fixed at 208 KB: the system left 35 KB of the IDF heap's main region,
Wi-Fi took about 30 KB of that, and one TLS session needs about 31 KB. So the main region can't hold
both a 208 KB Python heap and the network.

**What worked:** the ESP32-S3's IDF heap has four DATA regions: 289 KB (main), 32 KB, 22 KB and 8 KB
(RTC). Wi-Fi and TLS take theirs from the main region and never touched the 32 KB one. So:
- The Python heap never grows (`MICROPY_GC_SPLIT_HEAP_AUTO 0`), and starts at 160 KB from the main
  region.
- `heap.c` adds the largest blocks of the two other regions to it (32 KB and 22 KB), after every
  `gc_init`, soft resets included. 212 KB in all.
- Two small patches to MicroPython (`patches/`): one lets the board turn auto-growth off, one adds
  the hook `heap.c` runs from. `build` applies them for the build and takes them out after.
- Fewer Wi-Fi buffers (`sdkconfig.board`: 4 static RX, 16 dynamic RX and TX, no AMPDU TX) and no
  mDNS, for more IDF heap. `build` now deletes the build's old `sdkconfig`: ESP-IDF ignores the
  sdkconfig files while one exists.
- Fonts stay in ROMFS (`fonts.py`): `framebuf.blit` takes a read-only `(buffer, w, h, format)`, so a
  glyph is drawn straight from flash. `tools/fw` puts the `qf_*.bin` fonts in ROMFS with the modules.

## 5. A reset every 14 seconds

Once requests got through, the board reset about every 14 s (reset cause 3, the watchdog). A soft
timer feeds the console's watchdog, and on the ESP32 soft timers don't run during a blocking C call:
0 runs during a 6.7 s TLS read. The watchdog was 8 s. On the ESP32 it is now 30 s (`watch.py`); the
Pico keeps 8 s. `test-vectors/esp32_test.py` expects the new value.

## 6. The boot mark broke the import

With the heap fixed in size, the console sometimes failed to import: a `MemoryError` for 1,280 bytes
with 107 KB free. The animated boot mark draws while the console loads, and left the heap in holes
too small. The Cardputer now boots with the checklist (`splash.py`); `BOOT_ART` in `secrets.py`
still picks either. Other boards keep the mark.

## Numbers (2026-10-12)

- Importing the whole console takes 109 KB of Python heap.
- IDF main region free: 84 KB in maintenance, 53 KB with Wi-Fi joined, 17 KB with one HTTPS session
  open.
- The console running: 27–69 KB of Python heap free, both Safes `ok, owner`, `queue: 1`, TLS
  verified, no network errors and no resets over several minutes of polling.
- `tools/fw push console` and `tools/fw verify` with the modules and fonts in ROMFS: verify shows
  build `61f8b85`, release `e76e·9308`.

## How to get at a board in a watchdog loop

Reset it with `esptool.py chip_id`, then within about 1.5 s write a `maint` file with mpremote. The
next boot stays in maintenance. `mpremote resume exec` reads the running state without a soft reset.

## What ran

- `test-vectors/run.py`, `fingerprint_test.py`, `esp32_test.py`, `run-micropython.mjs`,
  `manifest.mjs`, `run-console.mjs`: pass.
- `emu/build.mjs`, `emu/e2e-static.mjs`, `tools/releases/site-test.mjs`: pass. The badges and the
  console page were rebuilt.
- Not run: the app's tests. The app didn't change.

## Not done yet

- **Reviewing and signing on the device.** A large transaction's pages take the most memory of
  anything the console does, and 27 KB free is a thin margin. If it runs out, the next step is
  asking Safe's service for less at once.
- The boot checklist on the 240x135 screen hasn't been checked by eye.
- Whether two machines build the same `firmware.bin`.
- This board's `QUORUM_EXPECT` pins chips `01230e6b…` (chip 2) and `0123f3ac…`, and a Trust M. Any
  other key, chip 5 (`0123a431…`, the test-key spare) included, stops at the pin screen.
