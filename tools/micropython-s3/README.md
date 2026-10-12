# MicroPython for the Cardputer console

The Cardputer v1.1's ESP32-S3 has no PSRAM, so stock MicroPython loads every module's bytecode into
about 205 KB of heap. The console needs more than that, and it stopped with a MemoryError while
`quorum.py` loaded. This build runs the modules from flash instead (ROMFS), so their bytecode takes no
RAM.

What it changes from `ESP32_GENERIC_S3` (`PICOQUORUM_CARDPUTER/`):
- **ROMFS** (`MICROPY_VFS_ROM`): a 1 MiB `romfs` partition at 0x200000, mounted at `/rom`.
  `tools/fw push` puts the image's compiled modules there as one ROMFS image and checks each one's
  hash where it landed. `boot.py`, `main.py`, the fonts and certificates, and the board's own files
  (`secrets.py`, logs, `wifi.json`) stay on the filesystem in `/`.
- **No Bluetooth**: the firmware uses none. The app is about 270 KB smaller.
- **The REPL on the S3's USB-Serial-JTAG port**, not TinyUSB. TinyUSB's port jumps to the bootloader
  on a DTR/RTS pattern, and macOS made that pattern as mpremote closed and reopened the port: the
  board dropped off USB between `tools/fw`'s sessions.
- **No UART REPL**: GPIO43 and 44 are not a UART on the Stamp-S3A.
- The board name is `PicoQuorum Cardputer`. `board.py` picks its `cardputer` profile from the
  `ESP32S3` in `os.uname().machine`.

Measured on a Cardputer v1.1 (2026-10-12):
- At boot, 242 KB of heap is free, against 209 KB on stock MicroPython.
- With the console's modules in ROMFS, the console's whole import chain left 107 KB free. Stock
  MicroPython ran out with `quorum.py` not yet loaded.
- Running, with Wi-Fi joined: 139 KB free, up in 5.3 s, no `error.log`.
- `tools/fw push` and `tools/fw verify` ran with the modules in ROMFS, including a push that rewrote it.

## Build it

Pinned in `build`: MicroPython v1.26.1 (`647c8b96`) and ESP-IDF v5.4.2 (`f5c3654a`). The script
refuses other commits.

```sh
mkdir -p ~/esp && cd ~/esp
git clone --depth 1 --branch v1.26.1 https://github.com/micropython/micropython.git
git clone --depth 1 --branch v5.4.2 --recursive --shallow-submodules https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3 && python3 tools/idf_tools.py install cmake ninja
cd ~/path/to/pico-quorum && tools/micropython-s3/build
```

It writes `tools/micropython-s3/out/firmware.bin` (gitignored) and prints its SHA-256.

Not checked yet: whether two machines build the same bytes. So for now, the hash only names the file
you built.

On macOS with Command Line Tools whose default SDK the linker can't read (here, MacOSX27.0's
`arm64e.x1`), nothing links, mpy-cross included. Point the build at an older SDK:
`SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk tools/micropython-s3/build`.

## Flash it

**This erases the board**: its files, Wi-Fi and `secrets.py`. Back the board up first
(`tools/fw backup`), and keep a full flash image of a stock board (`esptool.py read_flash 0 ALL ...`)
if you want to go back to M5's firmware.

```sh
esptool.py --port /dev/cu.usbmodem* erase_flash
esptool.py --port /dev/cu.usbmodem* -b 921600 write_flash 0 tools/micropython-s3/out/firmware.bin
tools/fw push console
```

- From stock MicroPython (TinyUSB), esptool's reset just restarts it. Run
  `mpremote exec "import machine; machine.bootloader()"`, then add `--before no_reset` to esptool.
- From this build, esptool resets the board by itself.
- After a flash, run one more esptool command (`chip_id`) if the REPL doesn't answer. The board can
  stay in the bootloader until a full reset.
- A new MicroPython over this one doesn't need `erase_flash`: it covers only the first 2 MiB, so ROMFS
  and the files survive.
