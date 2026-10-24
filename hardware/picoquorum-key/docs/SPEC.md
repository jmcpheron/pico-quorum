# The console: what it has

*Spec, 2026-10-23. What any console board must have and do, whatever its shape or size. The
layout that meets it is [DESIGN.md](DESIGN.md) (rev A).*

This page names no board size and no part positions. It says what each part is for, what the
firmware expects of it, and the rules a layout must keep. "Must" is something the console image or
the project's security rules depend on. "Should" is good practice. Each number says where it comes
from.

The three security rules this page leans on, stated once:

1. **Rule 1.** The key signs the Safe transaction hash the device rebuilt from the fields on its own
   screen, and nothing else, after every page is seen and Sign is held.
2. **Rule 2.** Moving any pin the firmware reads is a new board profile and a new release
   fingerprint. Rev A does this once, on purpose: its profile is `picoquorum-key` ([PINS.md](PINS.md)).
3. **Rule 3.** Nothing on the board may read a private key out or sign a digest it was handed. A
   layout adds no new way to sign.

## What it is

One owner of a Safe multisig. It fetches a pending transaction over its own Wi-Fi, shows what it
does, rebuilds the Safe transaction hash from the fields on its screen, and has its secure element
sign that hash and nothing else, after every page is seen and Sign is held (rule 1).

```
   USB-C 5 V ── 3.3 V regulator ──┬── ESP32-S3 module ── Wi-Fi, TLS ── Safe's transaction service
   (and the S3's own USB)         │      │ SPI ─────── screen; backlight switch
                                  │      │ GPIO ────── 3 buttons (5 with PREV and BACK)
                                  │      │ I2C ─────── ATECC608C: the key
                                  │      └ GPIO ────── status LED
                                  └── everything above is on 3.3 V (rev A: backlight LEDs on 5 V)
```

## The parts

| part | what it must be | why |
|---|---|---|
| processor | ESP32-S3 with **at least 2 MB PSRAM** and **4 MB flash** | the console image needs the PSRAM; it runs in 2 MB |
| its PSRAM | **quad** on the firmware's original profile; **any** on `picoquorum-key` | the original profile drives the screen on GPIO35/36, which an octal-PSRAM (R8) module takes ([WROOM-1 datasheet][wroom] Table 3-1, note b); `picoquorum-key` leaves GPIO35–37 unconnected, so the rule relaxes |
| its radio | a certified Espressif module | a module keeps its radio certification; a bare chip with our own antenna doesn't |
| the key | **ATECC608C**, SOIC-8 or UDFN-8, I2C | the chip the firmware's driver and the ceremony are written for |
| screen | **ST7789, 240 × 135 (1.14″), SPI** | the size the console's three-button screens are drawn for |
| buttons | **three**, or five with PREV and BACK | three is what today's image reads |
| power in | **USB-C**, 5 V | power and the serial port on one cable |
| 3.3 V | a regulator good for **500 mA or more** | Espressif's minimum for the supply (datasheet Table 6-2); Wi-Fi bursts reach 355 mA (Table 6-4) |
| status LED | one LED | the firmware blinks it |

Known-good modules: **ESP32-S3-WROOM-1-N4R2**, **WROOM-1-N8R2** (rev A's), and
**ESP32-S3-MINI-1-N4R2**. MicroPython **1.26.1**, the `ESP32_GENERIC_S3` build, finds the flash
and the PSRAM itself; 1.28.0 (2026-04-06) is current upstream and should be checked against the
console image before it is adopted.

## The pins

A board uses one of the firmware's profiles. Rev A uses `picoquorum-key`, defined in
[PINS.md](PINS.md) and summarised here. (The firmware's original `feather-s3` profile is a
different table; a board that uses it needs no firmware change.)

| what | GPIO | electrical |
|---|---|---|
| screen SCK, MOSI | 12, 11 | SPI(1), IO_MUX pins, up to 40 MHz |
| screen CS, DC, RST | 10, 9, 14 | |
| backlight | 21 | high is on; PWM |
| D0: Reject | 42 | to ground when pressed, internal pull-up |
| D1: Next | 41 | to ground when pressed, internal pull-up |
| D2: Sign, Open | 40 | to ground when pressed, internal pull-up |
| PREV, BACK | 39, 38 | to ground when pressed, internal pull-up; today's image doesn't read them |
| the key's I2C SDA, SCL | 16, 17 | 4.7k pull-ups to 3.3 V |
| status LED | 48 | high is on |
| USB D−, D+ | 19, 20 | the S3's own USB-Serial-JTAG |
| BOOT | 0 | tact to ground, 10k pull-up; recovery only, never a UI button |

Rules for every other pin:
- **Moving any pin above is a new profile and a new release fingerprint** (rule 2).
- **Never use for anything new:** GPIO26–37 (flash and PSRAM inside the module), 19 and 20 (USB),
  43 and 44 (UART0, the boot log), and the straps 0, 3, 45 and 46 beyond what the table gives them.
- **No UI button on a strap pin.** On `picoquorum-key` GPIO0 is BOOT only, so holding any button at
  plug-in cannot start the ROM bootloader.

## The key

- ATECC608C at I2C address **0x60**, on 3.3 V, with 100 nF at its VCC.
- **Pull-ups** of 2.2k to 4.7k on SDA and SCL, unless something else on the bus provides them.
- **Nothing else on the bus at an address the firmware tries as a key**: 0x60, 0x35, 0x6A, 0x58,
  0x36 or 0x59. A part that must sit at one of them goes in the profile's `NOT_KEYS`.
- **Soldered on, or on a port.** Soldered on, one board is one key for life: the chip's locks can't
  be undone, and a lost board is a lost owner the Safe's other owners replace. **The bus should also
  come out to pads**, so a key on wires can stand in for a soldered chip.
- The ceremony runs on the board's own buttons. Nothing on the board may read a private key out or
  sign a digest it was handed (rule 3).

## The screen

- **ST7789, 240 × 135, landscape**, with the panel at column 40, row 53 of the controller's RAM,
  `MADCTL = 0x60`, inversion on. A panel that needs other values is a new profile.
- **Mounted so the picture is upright with D0, D1 and D2 on its left.** Turned the other way, the
  picture is upside down until the firmware changes.
- **Backlight off at reset, high is on.** If the panel's LED cathode is tied to ground inside (an
  8-pin ribbon with LEDA only), switch it on the high side: a P-MOSFET, its gate pulled up, pulled
  down by an NPN the backlight GPIO drives. Choose the series resistor against the panel's own LED.
- **Its pins** come from the panel's own drawing, measured on a real panel before a board is made.

## The buttons

- **D0, D1 and D2 sit level with the screen's three rail rows**, rows 7, 67 and 127 of the 135. The
  image labels each button on the screen beside it, so the labels must line up with the buttons.
- **D0 is Reject: one easy press**, on any page, even while Sign is held. **D2 is Sign: held** for
  2 s, 3 s on a red page. The firmware enforces the holds; the layout must not make Sign easier to
  press by accident than Reject.
- At power-up the image never asks for BOOT: D1 held is maintenance, D2 held is Wi-Fi setup.
- PREV and BACK, if fitted, should sit apart from D0–D2, so the three the image reads today are
  still the three by the screen.

## Power

- **USB-C, 5 V, as a sink**: a 5.1k resistor from each CC pin to ground, so a USB-C charger turns
  its 5 V on.
- **3.3 V at 500 mA or more.** The S3 draws up to 355 mA in 802.11b bursts at 20.5 dBm and about
  95 mA receiving (Table 6-4); allow 20 mA for the chip and the LED, and 30 mA for the backlight if
  it is on 3.3 V. A low-dropout regulator in SOT-23-5 (500 mA) meets the minimum with little
  margin; a SOT-223 part has more room for heat.
- **Decoupling:** about 22 µF and 100 nF at the module's 3V3 (Espressif's application circuit,
  section 9), 100 nF at the chip and at the screen.
- **EN:** 10 kΩ to 3.3 V and 1 µF to ground, the RC delay Espressif asks for (section 9).
- **The straps at reset** (Table 4-1): GPIO0 high, GPIO45 low, GPIO46 low, GPIO3 don't-care without
  the JTAG eFuse this console never burns. Nothing on the board may drive 45 or 46.
- **No battery** in this version. A battery means a charger, a low-dropout regulator that works from
  3.7 V, and a battery gauge the profile's `NOT_KEYS` keeps off the key list.

## USB

- **The S3's own USB-Serial-JTAG** on GPIO19 and GPIO20, straight to the USB-C's D+ and D−, with an
  ESD array (USBLC6-2SC6 or alike) at the connector. esptool uses this port; there's no bridge chip
  and no auto-reset circuit.
- **What comes with it:** MicroPython's USB REPL is on this port. Anyone with the board and a USB
  cable can have the chip sign any digest. That is one owner's signature, and it shows in the chip's
  counter. A board that plugs into a computer and stays there should close this with wiring. Rev A
  puts two 0 Ω links in D+ and D−: removed, the port is power only.
- To reach the ROM bootloader: hold BOOT and plug in, or hold BOOT and pulse EN. esptool can also
  enter it over USB without touching either.

## The radio

The module's PCB antenna needs room ([WROOM-1 datasheet][wroom], Figure 11-1):
- **The antenna end at a board edge**, or past it.
- **No copper, track, via or pour under the antenna area** on any layer, and none beside it.
- **No standoff, metal part or button** near it. Mounting holes go at the other end.
- **No part over it** on the other face, and no screen glass.

## Debug access

Bare pads, not fitted with anything:
- **3V3 and GND**, to meter the supply
- **EN**, to reset by hand
- **TX and RX** (UART0, GPIO43 and GPIO44), to read the boot log
- **SDA, SCL, 3V3, GND**, the key's bus, for a key on wires

## Making it

- **One side for JLCPCB's Economic assembly.** Everything JLCPCB places goes on one face.
- **The module is hand-soldered.** Every Espressif ESP32-S3 module is "Standard only" at JLCPCB
  (checked 2026-10-23). The module's castellations solder with an iron, so it can go on either face.
  Its exposed pad needn't be soldered (datasheet section 9).
- **The panel clips into a ZIF**; JLCPCB doesn't stock the 1.14″ panel.
- **Check stock and tiers at upload.** Rev A's parts and their tiers are in [BOM.md](BOM.md).

## What any layout must keep: a checklist

- [ ] An ESP32-S3 module with at least 2 MB PSRAM and 4 MB flash; quad PSRAM unless the profile
      leaves GPIO35–37 unconnected.
- [ ] One firmware profile's pin table, named in the board's design.
- [ ] Every button to ground when pressed with a pull-up (on `picoquorum-key`); no UI button on a strap.
- [ ] D0, D1 and D2 level with rows 7, 67 and 127 of the screen.
- [ ] The screen upright with the buttons on its left; backlight off at reset.
- [ ] The ATECC608C alone at 0x60, with pull-ups, and nothing at the other key addresses unless
      `NOT_KEYS` lists it.
- [ ] GPIO45 low and GPIO0 high at reset; GPIO46 unconnected.
- [ ] 3.3 V good for 500 mA; EN's 10k and 1 µF.
- [ ] USB-C with 5.1k on each CC, ESD on D+ and D−.
- [ ] The antenna at an edge with nothing near it.
- [ ] Pads for 3V3, GND, EN, TX, RX and the key's bus.
- [ ] Nothing that can read a key out or sign a handed-in digest; no new way to sign (rules 1 and 3).

[wroom]: https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
