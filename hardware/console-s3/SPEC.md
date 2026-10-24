# The S3 console: what it has

*Spec, 2026-10-24. What any S3 console board must have and do, whatever its shape or size. One
layout that meets it is [DESIGN.md](DESIGN.md) (rev A); the idea and costs are in
[CONCEPT.md](CONCEPT.md).*

This page names no board size and no part positions. It says what each part is for, what the
firmware expects of it, and the rules a layout must keep. "Must" is something the console image or
the project's security rules depend on. "Should" is good practice. Each number says where it comes
from.

## What it is

One owner of a Safe multisig. It fetches a pending transaction over its own Wi-Fi, shows what it
does, rebuilds the Safe transaction hash from the fields on its screen, and has its secure element
sign that hash and nothing else, after every page is seen and Sign is held (AGENTS.md rule 1).

```
   USB-C 5 V ── 3.3 V regulator ──┬── ESP32-S3 module ── Wi-Fi, TLS ── Safe's transaction service
   (and the S3's own USB)         │      │ SPI ─────── 240 × 135 ST7789 screen, backlight switch
                                  │      │ GPIO ────── 3 buttons (5 with PREV and BACK)
                                  │      │ I2C ─────── ATECC608C: the key
                                  │      └ GPIO ────── status LED
                                  └── everything above is on 3.3 V
```

## The parts

| part | what it must be | why |
|---|---|---|
| processor | ESP32-S3 with **at least 2 MB PSRAM** and **4 MB flash** | the console image doesn't fit an ESP32-WROOM-32's 520 KB ([ESP32.md](../wiring/ESP32.md)); it runs in the Feather's 2 MB ([FEATHER-S3.md](../wiring/FEATHER-S3.md)) |
| its PSRAM | **quad**, not octal | an octal-PSRAM module (R8) takes GPIO35–37 ([WROOM-1 datasheet v1.8][wroom], Table 3-1, note b), and the screen's MOSI and SCK are on 35 and 36 |
| its radio | a certified Espressif module | a module keeps its radio certification; a bare chip with our own antenna doesn't |
| the key | **ATECC608C**, UDFN-8 or SOIC-8 | the chip the firmware's driver (`firmware/atecc.py`) and the ceremony are written for |
| screen | **ST7789, 240 × 135 (1.14″), SPI** | the size the console's three-button screens are drawn for (`quorum_ui_s.py`) |
| buttons | **three**, or five with PREV and BACK | three is what today's image reads |
| power in | **USB-C**, 5 V | power and the serial port on one cable |
| 3.3 V | a regulator good for **500 mA or more** | Espressif's minimum for the supply (Table 6-2); Wi-Fi bursts reach 355 mA (Table 6-4) |
| status LED | one LED | the firmware blinks it |

Known-good modules: **ESP32-S3-WROOM-1-N4R2** (rev A's), **WROOM-1-N8R2**, and
**ESP32-S3-MINI-1-N4R2** (the Feather's). MicroPython **1.26.1**, the `ESP32_GENERIC_S3` build,
finds the flash and the PSRAM itself ([FEATHER-S3.md](../wiring/FEATHER-S3.md#try-it)).

## The pins

To run today's console image with no firmware change, a board must use the GPIOs of
`firmware/board.py`'s `"feather-s3"` profile. The image picks that profile on any ESP32-S3.

| what | GPIO | electrical |
|---|---|---|
| screen SCK, MOSI | 36, 35 | SPI(1), up to 40 MHz (`SPI_BAUD`) |
| screen CS, DC, RST | 42, 40, 41 | |
| backlight | 45 | high is on; PWM |
| D0: Reject | 0 | to ground when pressed, pulled up. GPIO0 is also BOOT |
| D1: Next | 1 | to 3.3 V when pressed, pulled down (`board.HIGH`) |
| D2: Sign, Open | 2 | to 3.3 V when pressed, pulled down (`board.HIGH`) |
| the key's I2C SDA, SCL | 3, 4 | pulled up to 3.3 V |
| status LED | 13 | high is on |
| USB D−, D+ | 19, 20 | the S3's own USB-Serial-JTAG |
| `board.POWER` | 7 | the image drives it high at start; it may power the screen and the bus, or nothing |

Rules for every other pin:
- **Moving any pin above is a new profile and a new release fingerprint** (AGENTS.md rule 2). Do
  it only when a layout can't avoid it, and say so in the board's design.
- **Never use for anything new:** GPIO26–37 (flash and PSRAM inside the module), 19 and 20 (USB),
  43 and 44 (UART0, the boot log), and the straps 0, 3, 45 and 46 beyond what the table gives them.
- **PREV and BACK**, if fitted, go on free pins outside that list, to ground when pressed, with the
  S3's internal pull-ups. Rev A uses GPIO5 and GPIO6. Today's image doesn't read them; a profile
  that does is a firmware change and a new release.

## The key

- ATECC608C at I2C address **0x60**, on 3.3 V, with 100 nF at its VCC.
- **Pull-ups** of 2.2k to 4.7k on SDA and SCL, unless something else on the bus provides them.
- **Nothing else on the bus at an address the firmware tries as a key**: 0x60, 0x35, 0x6A, 0x58,
  0x36 or 0x59 (`atecc.KNOWN_ADDRS`). A part that must sit at one of them goes in the profile's
  `NOT_KEYS`, as the Feather's battery gauge at 0x36 does.
- **Soldered on, or on a port.** Soldered on, one board is one key for life: the chip's locks can't
  be undone ([LOCKING.md](../../docs/LOCKING.md)), and a lost board is a lost owner the Safe's other
  owners replace. On a port, the port is key-c's, with its protection
  ([PROPOSALS.md](../key-pcb/PROPOSALS.md#the-console-end-of-key-c)).
- **The key's bus should also come out to pads**, so a key-c on wires can stand in for a soldered
  chip.
- The ceremony runs on the board's own buttons, as it did on the Feather. Nothing on the board may
  read a private key out or sign a digest it was handed (AGENTS.md rule 3).

## The screen

- **ST7789, 240 × 135, landscape**, with the panel at column 40, row 53 of the controller's RAM,
  `MADCTL = 0x60`, inversion on: how the image drives the Feather's panel. A panel that needs other
  values is a new profile.
- **Mounted the way the Feather holds it relative to the buttons**, so the picture is upright with
  D0, D1 and D2 on its left. Turned the other way, the picture is upside down until the firmware
  changes.
- **Backlight off at reset, high is on.** If the panel's LED cathode is tied to ground inside (an
  8-pin ribbon with LEDA only), switch it on the high side: a P-MOSFET from 3.3 V, its gate pulled
  up, pulled down by an NPN that GPIO45 drives. Choose the series resistor against the panel's own
  LED.
- **Its pins** come from the panel's own drawing, measured on a real panel before a board is made.

## The buttons

- **D0, D1 and D2 sit level with the screen's three rail rows**, rows 7, 67 and 127 of the 135
  (`board.RAIL_Y`). The image labels each button on the screen beside it, so the labels must line up
  with the buttons.
- **D0 is Reject: one easy press**, on any page, even while Sign is held. **D2 is Sign: held** for
  2 s, 3 s on a red page. The firmware enforces the holds; the layout must not make Sign easier to
  press by accident than Reject.
- **D0 is also GPIO0, the BOOT strap.** Held at reset, it starts the ROM bootloader. The image never
  asks for it at power-up: D1 held is maintenance, D2 held is Wi-Fi setup.
- PREV and BACK, if fitted, should sit apart from D0–D2, so the three the image reads today are
  still the three by the screen.

## Power

- **USB-C, 5 V, as a sink**: a 5.1k resistor from each CC pin to ground, so a USB-C charger turns
  its 5 V on.
- **3.3 V at 500 mA or more.** The S3 draws up to 355 mA in 802.11b bursts at 20.5 dBm and about
  95 mA receiving (Table 6-4); allow about 30 mA for the backlight and 20 mA for the chip and the
  LED. A low-dropout regulator in SOT-23-5 (rev A: ME6211, 500 mA) meets the minimum with little
  margin; a SOT-223 part has more room for heat.
- **Decoupling:** about 22 µF and 100 nF at the module's 3V3 (Espressif's application circuit,
  section 9), 100 nF at the chip and at the screen.
- **EN:** 10 kΩ to 3.3 V and 1 µF to ground, the RC delay Espressif asks for (section 9).
- **The straps at reset** (Table 4-1): GPIO0 high (D0's pull-up), GPIO45 low (the backlight
  driver's base pull-down holds it), GPIO46 low (its internal pull-down; leave it unconnected).
  GPIO3 has the I2C pull-up, which only matters to an eFuse this console never burns.
- **No battery** in this version. A battery means a charger, a low-dropout regulator that works from
  3.7 V, and a battery gauge the profile's `NOT_KEYS` keeps off the key list.

## USB

- **The S3's own USB-Serial-JTAG** on GPIO19 and GPIO20, straight to the USB-C's D+ and D−, with an
  ESD array (USBLC6-2SC6 or alike) at the connector. esptool and `tools/fw` use this port; there's no
  bridge chip and no auto-reset circuit.
- **What comes with it:** MicroPython's USB REPL is on this port, by a decision recorded in
  [SECURITY.md](../../docs/SECURITY.md). Anyone with the board and a USB cable can have the chip sign
  any digest. That is one owner's signature, and it shows in the chip's counter. A board that
  plugs into a computer and stays there should close this with wiring instead:
  [console-usb](../console-usb/README.md) puts a serial bridge in front of the S3 for that reason.
- To reach the ROM bootloader: hold D0 and plug in, or hold D0 and pulse EN.

## The radio

The module's PCB antenna needs room ([WROOM-1 datasheet v1.8][wroom], Figure 11-1):
- **The antenna end at a board edge**, or past it.
- **No copper, track, via or pour under the antenna area** on any layer, and none beside it.
- **No screw, standoff, metal part or button** near it. Mounting holes go at the other end.
- **No part over it** on the other face, and no screen glass.

## Debug access

Bare pads, not fitted with anything:
- **3V3 and GND**, to meter the supply
- **EN**, to reset by hand
- **TX and RX** (UART0, GPIO43 and GPIO44), to read the boot log
- **SDA, SCL, 3V3, GND**, the key's bus, for a key-c on wires

## Making it

- **One side for JLCPCB's Economic assembly.** Everything JLCPCB places goes on one face.
- **The module is hand-soldered.** Every Espressif ESP32-S3 module is "Standard only" at JLCPCB,
  which adds about $55 an order (checked 2026-10-23). The module's castellations solder with an
  iron, so it can go on either face. Its exposed pad needn't be soldered (datasheet section 9).
- **The panel clips into a ZIF** or is soldered to pads; JLCPCB doesn't stock the 1.14″ panel.
- **Check stock and tiers at upload.** Rev A's parts and their tiers are in
  [DESIGN.md](DESIGN.md#parts).

## What any layout must keep: a checklist

- [ ] An ESP32-S3 module with at least 2 MB of quad PSRAM and 4 MB flash; never an R8.
- [ ] The pin table above, or a new firmware profile and release named in the board's design.
- [ ] D0 pulled up and low when pressed; D1 and D2 pulled down and high when pressed.
- [ ] D0, D1 and D2 level with rows 7, 67 and 127 of the screen.
- [ ] The screen upright with the buttons on its left; backlight off at reset.
- [ ] The ATECC608C alone at 0x60, with pull-ups, and nothing at the other key addresses unless
      `NOT_KEYS` lists it.
- [ ] GPIO45 low and GPIO0 high at reset; GPIO46 unconnected.
- [ ] 3.3 V good for 500 mA; EN's 10k and 1 µF.
- [ ] USB-C with 5.1k on each CC, ESD on D+ and D−.
- [ ] The antenna at an edge with nothing near it.
- [ ] Pads for 3V3, GND, EN, TX, RX and the key's bus.
- [ ] Nothing that can read a key out or sign a handed-in digest; no new way to sign (AGENTS.md
      rules 1 and 3).

## Boards that meet it

- [console-s3 rev A](DESIGN.md): the module on the back, five buttons, the chip soldered on,
  64 × 22.86 mm. Placed and checked, not routed.
- [console-usb](../console-usb/README.md): the same idea with the radio out of use. It keeps the
  pin table, the key, the screen, the three buttons and the power rules. It departs on purpose in
  three places: the bare ESP32-S3FH4R2 chip instead of a module (no radio to certify), no antenna,
  and a serial bridge in front of the S3 instead of its own USB.

[wroom]: https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
