# console-rp: the console on an RP2350, no radio at all

*Sketch, 2026-10-29. A plan to take into KiCad: the circuit, the pins and the parts. No schematic,
no board and no fab files yet. Not ordered. The firmware it needs is not written.*

[console-usb](../console-usb/README.md) took the radio out of use: a bare ESP32-S3 with no antenna,
a USB-C whose only data path is a CH340C serial bridge, and the ATECC608C soldered on. This is the
same console on the chip the Pico 2 W is built around, the RP2350. The Pico 2 W's Wi-Fi is a
separate chip beside it; the RP2350 itself has no radio. So here "no radio" is a fact of the parts
list, not a rule the firmware has to keep.

```
   Safe's service ── HTTPS ── phone or laptop (the relay) ── USB-C ── CH340C ── UART1 ── RP2350 ── I2C ── ATECC608C
                              no key, no say in                                          screen, 3 buttons
                              what gets signed
```

What the RP2350 buys over console-usb's S3:
- **No radio to keep off.** Nothing to check in the image, no antenna rules to break, nothing to
  certify as a radio.
- **The console already runs on it.** The Pico 2 W is an RP2350 with 520 KB of RAM, and the console
  fits there with Wi-Fi and TLS. Without them it has more room, not less.
- **MicroPython's Pico 2 build has no network code.** The `RPI_PICO2` build (not `RPI_PICO2_W`) has
  no `network` module and no Wi-Fi driver, so the image can't start a radio even by mistake.
- **Secure boot, for later.** The RP2350 can refuse to run an image that isn't signed with a key
  fused into its OTP (RP2350 datasheet, section 10.1.1), and it has a glitch detector (10.9). Like
  an ATECC608's locks, OTP fuses can't be undone. Nothing here burns them.

What it costs: a core regulator that Raspberry Pi says must be laid out their way
([below](#the-core-regulator-copy-it-exactly)), an external flash chip (or the RP2354A, which has
it inside), and a 12 MHz crystal. That is about the same part count as the S3's supplies.

The link, what the relay can and can't do, and why the USB-C reaches only the CH340C are all as in
console-usb ([the link](../console-usb/README.md#the-link-what-the-computer-can-and-cant-do)). This
board changes the chip, not that design.

## The quickest way into KiCad

console-usb is already drawn and placed in KiCad (`hardware/console-usb/console-usb/`). Most of this
board is the same:

| block | from console-usb | change |
|---|---|---|
| USB-C, CC resistors, USBLC6 ESD | J1, R3, R4, U2 | none |
| 5 V to 3.3 V | U3 AMS1117-3.3, C14, C15 | none |
| the link | U4 CH340C, C16 | its TXD and RXD go to GPIO21 and GPIO20 |
| the key | U5 ATECC608C, C17, R5, R6 | its bus goes to GPIO4 and GPIO5 |
| the screen and its ZIF | J2, C18, C19 | its pins go to GPIO8–13 |
| the backlight switch | Q1, Q2, R7–R10 | its gate drive comes from GPIO13. R10, there for the S3's GPIO45 strap, can stay as a pull-down so the backlight is off at reset |
| buttons | SW1–SW3, R11–R13 | **all three pressed low**, with 10k pull-ups. console-usb's D1 and D2 are pressed high with pull-downs, as on the Feather |
| LED | D1, R14 | from GPIO25 |
| RESET | SW4, R1, C11 | to RUN. The RP2350 has its own pull-up on RUN; keep R1 and C11 as console-usb has them, or drop them |
| holes, the panel's foam pads, the silkscreen | as placed | none |

So in KiCad:
1. Copy `hardware/console-usb/console-usb/` to `hardware/console-rp/console-rp/` and rename the
   project files.
2. Delete the S3 block: U1, its supplies C1–C10, L1 (its 0 Ω), the 40 MHz crystal Y1, R2, C12, C13,
   and R15. The new L1, Y1 and the rest come from the tables below.
3. Add the RP2350 block from the tables below.
4. Rewire the moved blocks to their new GPIOs.
5. Change D1 and D2 to pressed-low: pull-ups in place of the pull-downs, the switches to GND.
6. Update PCB from schematic. The RP2350 goes where the S3 was, under the glass. Under the glass
   only parts lower than 1.7 mm may go (console-usb's rule). A 7 × 7 mm QFN is usually about 0.9 mm,
   as the S3's is; check the RP2350's package drawing (datasheet, section 14.1), and the flash's
   SOIC-8, which is taller and may have to sit outside the glass.

KiCad 9's library may have an RP2350A symbol. Either way, Raspberry Pi publishes its RP2350A
Minimal board as a KiCad project (a ZIP linked from section 1.1 of the hardware design guide
below): take the symbol, the footprint and the regulator's layout from there. Check the symbol's
pin numbers against the table here, which is from the datasheet.

## The RP2350 block

Values from Raspberry Pi's *Hardware design with RP2350* (RP-008280-DS-2) and its Minimal board.
Pin numbers from the *RP2350 Datasheet*, Figure 2 (QFN-60).

### Power pins

| pin | name | connects to | parts |
|---|---|---|---|
| 1, 11, 20, 30, 38, 45 | IOVDD | 3V3 | 100 nF at each pin |
| 44 | ADC_AVDD | 3V3 | 100 nF |
| 53 | USB_OTP_VDD | 3V3 | shares one 100 nF with pin 54, as on the Minimal board |
| 54 | QSPI_IOVDD | 3V3 | (the 100 nF above) |
| 6, 23, 39 | DVDD | the 1.1 V core, from the regulator below | 100 nF at each pin |
| 49 | VREG_VIN | 3V3 | 4.7 µF, 0402, close (the guide's C6) |
| 48 | VREG_LX | L1 to DVDD | L1: 3.3 µH, Abracon AOTA-B201610S3R3-101-T, 0806 |
| 50 | VREG_FB | DVDD | 4.7 µF, 0402, on DVDD (the guide's C7) |
| 47 | VREG_PGND | GND, by its own short path | |
| 46 | VREG_AVDD | 3V3 through 33 Ω | 33 Ω, 0402, then 4.7 µF, 0402, to GND (the guide's R3 and C9) |
| 61 | the centre pad | GND | vias to the GND pour, 0.3 mm or more for JLCPCB |

Plus 10 µF bulk on 3V3, which console-usb's C15 (22 µF) already gives.

### The core regulator: copy it exactly

The RP2350's 1.1 V core comes from its own switching regulator: VREG_VIN, VREG_LX, VREG_FB,
VREG_PGND and VREG_AVDD. The guide is blunt about it:
- **Use their layout.** Raspberry Pi say that if you don't use the Minimal board's layout for L1, C6,
  C7, C9 and R3, you do so at your own risk. Copy the placement and the tracks from their KiCad
  files.
- **L1 has a polarity.** A small inductor's magnetic field leaks one way. The wrong way round upsets
  C7 and the regulator. The Abracon part has a dot and comes on a reel all facing the same way. Put
  the dot where the Minimal board puts it, and check JLCPCB's placement preview for it.
- **PGND's return.** The switching current must return straight to VREG_PGND without crossing the
  rest of the ground.
- **VREG_AVDD is noise-sensitive.** That is what the 33 Ω and 4.7 µF are for.

### Flash, QSPI and boot

| pin | name | connects to |
|---|---|---|
| 60 | QSPI_SS | the flash's /CS (pin 1); 10k to 3V3, not fitted; 1k to SW5 BOOT, to GND |
| 56 | QSPI_SCLK | CLK (pin 6) |
| 57 | QSPI_SD0 | DI, IO0 (pin 5) |
| 59 | QSPI_SD1 | DO, IO1 (pin 2) |
| 58 | QSPI_SD2 | /WP, IO2 (pin 3) |
| 55 | QSPI_SD3 | /HOLD, IO3 (pin 7) |

- **The flash:** Winbond W25Q32JVSSIQ, 4 MB, SOIC-8 208 mil. 4 MB is what the Pico 2 has and what
  MicroPython's `RPI_PICO2` build expects. Its pin 8 to 3V3 with 100 nF, pin 4 to GND. Short tracks,
  straight to the chip.
- **The 10k on QSPI_SS** is the guide's R1, not fitted. Their Winbond part didn't need it; the
  footprint is there in case another part does.
- **SW5 BOOT** pulls QSPI_SS low through 1k. Held while RUN is pressed, the RP2350 starts its USB
  bootloader. The USB is only on J3 (below), so this does nothing unless a person has a cable on J3.
- **Or the RP2354A,** the same QFN-60 with 2 MB of flash inside. Then the W25Q32 isn't fitted, and
  SW5 stays on QSPI_SS. 2 MB means a MicroPython build for 2 MB. Its LCSC stock wasn't found on
  2026-10-29.

### Crystal

- **Y1:** Abracon ABM8-272-T3, 12 MHz, 10 pF, ±30 ppm, 3225. Raspberry Pi recommend this exact part:
  the Pico 2 is tuned for it.
- **C, 15 pF** from each side to GND (the guide's C3 and C4).
- **1 kΩ** in series from XOUT (pin 22) to the crystal. XIN (pin 21) goes straight to it.
- Short tracks, GND under it, nothing else routed under it.

### USB, debug and RUN

| pin | name | connects to |
|---|---|---|
| 52 | USB_DP | 27 Ω, close to the chip, then J3 only |
| 51 | USB_DM | 27 Ω, close to the chip, then J3 only |
| 24 | SWCLK | J3 |
| 25 | SWDIO | J3 |
| 26 | RUN | SW4 RESET to GND, and J3. It has its own pull-up (datasheet, pin table) |

The RP2350's own USB never reaches the USB-C. On it are MicroPython's REPL and the USB bootloader,
so a computer on the other end could run anything and write a new image. That is console-usb's
reason for the CH340C, and it holds here too.

## The pins

| GPIO | QFN pin | net | what |
|---|---|---|---|
| 1 | 3 | `BTN_D0` | D0: Reject and Back. 10k up, pressed low |
| 2 | 4 | `BTN_D1` | D1: Next. 10k up, pressed low |
| 3 | 5 | `BTN_D2` | D2: Sign, held. 10k up, pressed low |
| 4 | 7 | `SDA` | the key's I2C, I2C0 SDA, 4.7k to 3.3 V |
| 5 | 8 | `SCL` | the key's I2C, I2C0 SCL, 4.7k to 3.3 V |
| 8 | 12 | `LCD_DC` | the screen's RS |
| 9 | 13 | `LCD_CS` | the screen's CS |
| 10 | 14 | `LCD_SCK` | the screen's SCL, SPI1 SCK |
| 11 | 15 | `LCD_MOSI` | the screen's SDA, SPI1 TX |
| 12 | 16 | `LCD_RST` | the screen's RESET |
| 13 | 17 | `LCD_BL` | backlight, high is on |
| 20 | 32 | `LINK_TX` | UART1 TX to the CH340C's RXD |
| 21 | 33 | `LINK_RX` | UART1 RX from the CH340C's TXD |
| 25 | 37 | `LED` | red LED, high is on |

Why these:
- **The screen is on the Waveshare Pico-LCD-1.3's pins** (8–13, `firmware/board.py`'s defaults), so
  `lcd.py` drives SPI(1) on them as it does on the dev console. Only the panel's size and offsets
  change: they are the Feather's 240 × 135, as in `"feather-s3"`.
- **The key is on GPIO4 and 5,** the default `SDA` and `SCL` there too.
- **UART1 on GPIO20 and 21.** The datasheet's function table puts UART1 TX and RX on them, and
  MicroPython's REPL on the RP2350 is on USB, never UART1.
- **All three buttons pressed low with 10k pull-ups.** The RP2350's A2 stepping has a fault in its
  pull-downs (erratum RP2350-E9, fixed in A3); pull-ups always worked. Pressed low also means no
  pin needs `HIGH` in the profile.
- **GPIO0 is left free.** It is the second QSPI chip select (QMI CS1n), if a later board wants PSRAM.
- **The LED on GPIO25,** where the original Pico has its own.

Free: GPIO 0, 6, 7, 14–19, 22–24 and 26–29. GPIO26–29 are the ADC inputs, if a later board wants to
measure VBUS.

## J3, the bench header (not fitted)

Eight holes, each named on the silkscreen: GND, 3V3, SWCLK, SWDIO, USB D+, USB D−, RUN, and BOOT
(QSPI_SS's side of SW5, after the 1k, so a wire from BOOT to GND does what SW5 does). With a cable on its USB pins, BOOT held and RESET pressed, the RP2350 shows up as a
USB drive and takes a MicroPython `.uf2`. With a Raspberry Pi Debug Probe on SWCLK and SWDIO, it can
be flashed and debugged. Either way it is a person with the board in hand, as on console-usb.

Anyone with the board and a probe can also read and rewrite its flash. That is today's position for
every console ([docs/SECURITY.md](../../docs/SECURITY.md)). Secure boot and the OTP debug-disable
bits would close it, permanently; that is a decision for later, not this board.

## The parts

LCSC numbers. Those marked *new* were looked up on 2026-10-29 by web search, not by reading
JLCPCB's quote page; check each there the day you order. The rest are console-usb's, checked
2026-10-24.

| ref | part | LCSC | tier | note |
|---|---|---|---|---|
| U1 | RP2350A, QFN-60 7 × 7 mm | C42411118 | Extended | *new*. A search snapshot hinted the stock may be low |
| U6 | W25Q32JVSSIQ, 4 MB, SOIC-8 208 mil | C82344 | Extended | *new*. Not fitted with an RP2354A |
| L1 | Abracon AOTA-B201610S3R3-101-T, 3.3 µH, 0806 | C42411119 | Extended | *new*. Raspberry Pi's recommended part, with its polarity dot |
| Y1 | Abracon ABM8-272-T3, 12 MHz, 3225 | C20625731 | | *new*. Tier not read |
| C | 4.7 µF 0402 × 3 | | | for VREG_VIN, DVDD and VREG_AVDD: pick a Basic part on the day |
| C | 100 nF 0402 × 11 | C1525 | Basic | six IOVDD, three DVDD, ADC_AVDD, USB_OTP_VDD/QSPI_IOVDD, plus one at the flash |
| C | 15 pF 0402 × 2 | | | crystal load: pick a Basic part on the day |
| R | 33 Ω 0402 | | | VREG_AVDD filter |
| R | 1 kΩ 0402 × 2 | C11702 | Basic | XOUT series, and BOOT |
| R | 27 Ω 0402 × 2 | | | USB series |
| R | 10k 0402, not fitted | C25744 | Basic | QSPI_SS pull-up |
| SW5 | BOOT, TS-1187A | C318884 | | as SW1–SW4 |
| U4 | CH340C | C84681 | Extended | console-usb's |
| U5 | ATECC608C-MAHDA-S, UDFN-8 | C23291019 | Extended | console-usb's. **Thin stock** on 2026-10-24; the SOIC-8 608C (C28975195) is the fallback, with another footprint |
| J1, U2, U3, J2, Q1, Q2 and the rest | | | | console-usb's `fab/bom.csv` |

**Extended feeder fees,** $3.07 each an order: the RP2350A, the flash, L1, probably Y1, the CH340C,
the 608C, the ZIF, the USB-C and the USBLC6. Nine, about $28, against console-usb's seven.

**A rough cost,** not a quote, and these prices are guesses until JLCPCB's quote page shows them:
the RP2350A about $1, the flash about $0.40, L1 about $0.25 (Findchips), Y1 about $0.70
(element14), against the S3's $3.04 at LCSC. So the parts
cost about the same, and the two extra feeders add about $6 an order. Expect about console-usb's
figures: around $21 a console for five, around $12 for twenty-five. Upload the files for the real
number.

## The firmware it needs (not written)

Each is a firmware change, so a new release fingerprint ([AGENTS.md](../../AGENTS.md), rule 2).

1. **A `console-rp` profile** in `firmware/board.py`: `THREE`, the screen on 8–13 with the
   Feather's panel size, offsets and `MADCTL`, the buttons on 1, 2, 3 pressed low (`HIGH` empty),
   the key on 4 and 5, the LED on 25, no `POWER`. The RP2350 picks `"waveshare"` today, so the
   profile comes from `secrets.BOARD`, or from looking at the board as `picoquorum-key` does.
2. **The link,** shared with console-usb: `link.py` on UART1 in place of `vhttp`, the line protocol
   in console-usb's README, a link shim in the emulator, and a hostile-relay test in
   `run-console.mjs`.
3. **A `console-link` image** with no Wi-Fi files (`net.py`, `wifisetup.py`, `wificfg.py`,
   `vhttp.py`, `ca_*.bin`), built for MicroPython's `RPI_PICO2`.
4. **The relay** on the phone or laptop: a new network path and a new part of the app, so it needs a
   yes before it's built (AGENTS.md).

## Steps to a board

1. **Into KiCad** as above: copy console-usb, swap the chip, rewire. ERC.
2. **Lay out the regulator from Raspberry Pi's files,** then the crystal and the flash, then the
   rest. DRC against JLCPCB's limits (`hardware/key-pcb/gen.py`'s `JLC_RULES`).
3. **Quote it:** Economic, one side, qty 5. Check the RP2350A's and the 608C's stock, and the
   crystal's tier. Write the real numbers here.
4. **Bring one up:** 3.3 V and 1.1 V before anything; MicroPython over J3; the screen, the buttons
   and the key with a bench script. Log it in the build log.
5. **The firmware and the relay,** above.

## Open

- [ ] RP2350A and a W25Q32, or the RP2354A if JLCPCB stocks it?
- [ ] KiCad 9's RP2350A symbol, or Raspberry Pi's? Check the pins either way.
- [ ] Keep J3's USB pins, or flash over SWD only?
- [ ] Secure boot: when, and who holds the signing key? OTP can't be undone.
- [ ] The relay: a Web Serial page in the app, a command-line tool, or both?
- [ ] An iPhone has no Web Serial or WebUSB, as far as we know. Android and laptops first.

## What was checked, and how

- The RP2350A's pin numbers: the *RP2350 Datasheet*, Figure 2 (QFN-60), read 2026-10-29.
- The UART1, SPI1 and I2C0 pins: the datasheet's GPIO function table.
- The regulator, decoupling, flash, crystal and USB values: *Hardware design with RP2350*
  (RP-008280-DS-2), sections 2 to 5, read 2026-10-29.
- RP2350-E9: the datasheet's errata, D.5.1, and the A3 stepping's fixes, C.2.1.
- The *new* LCSC numbers: web search on 2026-10-29, not JLCPCB's own pages.

Not checked: anything in KiCad. There is no schematic or board yet, no ERC or DRC, and nothing on a
bench. Nothing here has been reviewed by anyone but its author.

## License

Hardware: CERN-OHL-W-2.0, as everything in `hardware/` ([hardware/README.md](../README.md#license)).
