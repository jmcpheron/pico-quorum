# console-rp: bringing a board up, and loading boards in numbers

How the first board was brought up and loaded on 2026-11-04, what went wrong and why, and the ways to
load these boards if we make more than a handful. The scripts are in this folder.

## What the first board showed

| part | result | how it was checked |
|---|---|---|
| RP2350A | answers on SWD: DPv3, two Cortex-M33; `CHIP_ID` 0x30004927 | `probe-rs info`, `probe-rs read` |
| crystal | `XOSC_STATUS` 0x81001000: enabled and stable | `probe-rs read b32 0x40048004` |
| flash | MicroPython and a filesystem written and read back | `probe-rs download --verify` |
| screen | fills white, red, green, blue; the frame's four edges show; R G B in order; right way up | by eye, `stage0.py` |
| D0 D1 D2 | each press reaches the RP2350 | `stage0.py`'s lines over the link |
| LED, backlight | both switch | by eye |
| the key | ATECC608 at 0x60, revision 00006005, both zones open | `stage0.py`: Info and two config reads, nothing written |
| the link | the CH343P carries UART1 both ways at 115200 | `stage0.py`'s lines, and its echo of what was sent |
| J3's USB | **not seen by the Mac**, either way round | see below |

The screen's settings are the Feather's: MADCTL 0x60, its window at column 40, row 53 of the
ST7789's memory, inversion on.

## How it was loaded

The USB-C reaches only the CH343P (README.md, "the link"). It can't reset the RP2350, hold BOOTSEL,
or reach the REPL. That is on purpose, and it means a new board can only be loaded from J3.

J3's USB pins were tried first, with a USB cable's GND, D− and D+ on jumper wires. The Mac never saw
the RP2350, whichever way round D+ and D− went. The chip was waiting on USB the whole time: its
clocks ran from the crystal's PLLs, which is what the boot ROM sets up for its USB boot. So the fault
is in the wires or in that part of the board. It is still open.

What worked is SWD, through J3's CLK, DIO and GND:

1. **A probe.** A Pico 2 W with Raspberry Pi's `debugprobe_on_pico2.uf2` (debugprobe v2.3.1, sha256
   `98cbb993872e4bb7bf7ac064cef8986cda171b9e783ef6ce1544873d7b704621`). Copy it to the Pico's boot drive
   (hold its BOOTSEL as it is plugged in). It uses GP2 for SWCLK and GP3 for SWDIO; the W's LED does
   nothing, its radio is not used. Raspberry Pi's own Debug Probe does the same job.
2. **Wires.** Pico GP2 (pin 4) to CLK, GP3 (pin 5) to DIO, GND (pin 3) to J3's square GND pad. No
   power between the boards: each has its own USB cable, the console-rp on its USB-C.
3. **probe-rs** on the Mac: `brew install probe-rs-tools` (0.32.0). Homebrew's OpenOCD 0.12 doesn't
   know the RP2350.
4. **MicroPython** for the Pico 2 (not the 2 W), v1.26.1, `RPI_PICO2-20250911-v1.26.1.uf2` from
   micropython.org (sha256 `0616a3a4298a3c32c9092b71a431867dafcb4250f467245bcf2b6fe9704e4548`).
5. **Load:**
   ```sh
   uv run --no-project --with littlefs-python==0.19.0 python hardware/console-rp/bench/swdload.py \
       RPI_PICO2-20250911-v1.26.1.uf2 main.py=hardware/console-rp/bench/stage0.py
   ```
   `swdload.py` checks the UF2's hash, takes its Arm blocks as one image for 0x10000000, builds a
   littlefs the way MicroPython's rp2 port makes its own (4 KB blocks, 768 of them, from 0x10100000,
   256-byte writes), writes both with `probe-rs download --verify`, and resets the chip. It writes
   only the filesystem's blocks that hold data, and always the superblock pair.

   The UF2 also has one block for 0x10ffff00 of another family (0xe48bff57). It is for a UF2 copied to
   the boot drive, not part of MicroPython, and SWD doesn't need it.

### On the bench: the REPL on the USB-C

For the bring-up, `main_repl.py` was loaded as `/main.py`: it puts MicroPython's REPL on UART1, so the
Mac drives the board over the USB-C's serial port while the probe stays for loading.

```sh
uv run --no-project --with littlefs-python==0.19.0 python hardware/console-rp/bench/swdload.py \
    RPI_PICO2-20250911-v1.26.1.uf2 main.py=hardware/console-rp/bench/main_repl.py \
    stage0.py=hardware/console-rp/bench/stage0.py --no-micropython
uv run --no-project --with pyserial==3.5 python hardware/console-rp/bench/rawrepl.py \
    /dev/cu.usbmodem… hardware/console-rp/bench/stage0.py --follow 5
```

**This is for a bench board only.** On a console the USB-C must never reach the REPL. Anything on the
computer could then talk to the RP2350, and through it to the key. Load the console's own main.py
before a board leaves the bench.

`mpremote` doesn't work here: it soft-resets the board, and a soft reset drops the REPL off UART1
until a hard reset (RESET, or `probe-rs reset`). `rawrepl.py` uses the raw REPL with no soft reset.

### How long it took

| what | bytes | time, with verify |
|---|---|---|
| MicroPython | 324,864 | 18 s |
| a filesystem written whole | 2 MB | 117 s |
| a filesystem's used blocks only | 8 KB + 16 KB | about 1 s each |

At probe-rs's default SWD clock. A board is about 20 s of loading.

## What went wrong, and what we learnt

- **The screen stayed black: our bug.** MicroPython's `SPI(1, sck=…, mosi=…)` on the rp2 port takes
  SPI1's default MISO, GPIO8, which is this board's (and the Pico's) LCD DC. DC then never moved.
  `miso=None` fixes it. `firmware/lcd.py` already passes it; `stage0.py` didn't at first.
- **Jumper wires in bare holes.** They lost contact three times: once with the probe mid-write, which
  left the chip halted until they were reseated and the load run again. Solder a 1×8 header into J3
  for any board that will be loaded more than once.
- **J3's USB never enumerated.** Not yet known why. Check the wires to D+ and D− with a meter, then
  the board (R13, R14 and the tracks to J3) before relying on it.
- **A 1.4 V reading** on the via beside L1 (DVDD). The RP2350 should set 1.1 V at power-up. The chip
  runs, so this may be the meter on a switching rail. Not yet measured again, nor 3V3 beside it.

## Loading boards in numbers

The USB-C won't load a board, by design, so every way in is through J3 or before the flash is
placed. In order of how soon we could use it:

**1. SWD through a fixture on J3 (what we did, made repeatable).** Pogo pins on J3's CLK, DIO and
GND, a probe per station, and `swdload.py`. About 20 s of loading a board, plus handling. More
stations, more probes: probe-rs picks one by serial (`--probe`). The fixture can also hold the USB-C,
so one station loads, runs the test and logs the result:
- `stage0.py` as the test. When it owns the link it sends each fact line over the USB-C
  (`fact: 01234ed5a949900dee`), so a script on the station logs the key's serial against the board,
  and checks the button counts as a person presses them.
- Then load the console's own image and leave it. The station never needs the REPL.

**2. The flash programmed before assembly.** Some assemblers program memory chips before placing them.
We'd send one flash image (MicroPython and the filesystem, made by `swdload.py`'s code into one file)
and every board starts with it. It's fastest for big runs. But the image has to be final when the
order goes in, a mistake costs the run, and we'd still test each board on a fixture. We haven't asked
JLCPCB whether they do this for the W25Q128.

**3. USB through J3 (BOOTSEL), with `picotool load --verify`.** Raspberry Pi's usual way, and no probe.
It needs J3's USB proven first (it isn't), the fixture on D+ and D−, and BOOTSEL held at reset. SWD
needs neither.

**Whichever way:**
- **One image per release.** MicroPython and the console's files made into one flash image from a
  tagged release, its hash in the release's manifest, written with `--verify`. The console then shows
  the release fingerprint on its Device screen, as every board does (`docs/RELEASES.md`).
- **Freezing the console's files into MicroPython** would make one smaller image and boot faster, but
  it means building MicroPython ourselves, and that build then has to be pinned like everything else.
- **Loading is not the key ceremony.** The ATECC608 arrives open, and nothing above writes to it.
  Making its key is a separate step, run with its own image (`docs/LOCKING.md`).
- **Decide early on the RP2350's own locks.** Its OTP can turn on secure boot (only images signed by
  our key run) and turn off or lock SWD. Like the key's locks, these can't be undone. They change
  every option above: a locked SWD rules out option 1 for updates, and secure boot means every
  image must be signed. Try them on a spare board before deciding.
- **For a rev C board:** J3 as pads for a pogo fixture (or a Tag-Connect footprint), with RUN on it
  too, so a fixture can reset the board without SWD.
