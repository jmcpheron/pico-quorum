# devkit-s3: a bare-bones ESP32-S3 console board

> **Status: a plan, 2026-10-11.** Nothing is drawn or ordered. The prices are JLCPCB's on this
> date, read from its parts search. The firmware it needs is not written yet.

The console on one small board, built around an ESP32-S3 module instead of a Pico. It's a dev kit
first:
- the key plugs in, and there are three ways for it to arrive
- cheap surface-mount buttons are enough to run the console
- a knob plugs into a header
- every spare pin comes out on two rows of 2.54 mm pads

JLCPCB assembles the whole top side. Nothing needs hand soldering except headers you choose to fit.

The ESP32 bench test ([wiring/ESP32.md](../wiring/ESP32.md)) ran the console on a classic ESP32
with PSRAM. This board moves to the ESP32-S3. The firmware changes for that are listed
[below](#firmware-changes); nothing has been released yet, so a new pin map is fine.

## The choices, and why

| | choice | why |
|---|---|---|
| Module | **ESP32-S3-WROOM-1-N16R8** (C2913202): 16 MB flash, 8 MB octal PSRAM | The console needs PSRAM ([ESP32.md](../wiring/ESP32.md#will-the-whole-console-fit)). The S3 has USB built in, so there's no USB-serial chip and no auto-reset transistors. JLCPCB had 34,398 in stock. The N8R8 is $0.13 cheaper but had 2,891 |
| USB | a USB-C socket (C2894897, the one key-c uses) wired straight to the S3's own USB | power, firmware and the REPL on one cable. 5.1 kΩ on each CC pin, so USB-C chargers give 5 V. A USBLC6 on D+ and D− |
| 3.3 V | **AMS1117-3.3** (C6186) | 1 A, and a JLCPCB *basic* part, so it adds no feeder fee. Wi-Fi's bursts, the screen's backlight and the key together stay well under 1 A |
| Buttons | **8 × TS-1187A-B-A-B** (C318884), 5.1 mm, $0.02 each, basic | Up, Down, Select, Sign, Back, Reject, plus BOOT and RESET |
| Knob | a 1×5 header in a KY-040's order (CLK, DT, SW, +, GND) | A KY-040 plugs in with five straight wires, or wire an EC11's legs. Select and the knob's push share a pin, so the board works the same with or without a knob |
| Screen | a 1×8 header in the bench module's order (BL, RST, DC, SCL, MOSI, CS, 3V3, GND) | any panel from the pack plugs in with eight straight wires ([SCREENS.md](../../docs/quorum-ui/SCREENS.md)) |
| Key | **one key bus, three ways in** ([below](#the-key-bus)) | key-c's USB-C plug, a STEMMA QT socket for the Adafruit breakout, and a 1×8 header for whatever comes next |
| Breakout | two rows of 2.54 mm pads, every usable GPIO plus 3V3, 5V, EN and GND | like Espressif's DevKitC-1. Pads only: fit headers where you want them |
| Board | 2 layers, under 100 × 100 mm, lead-free HASL | the module carries the radio, flash, PSRAM and crystal, so there's no RF or memory layout to do. Under 100 × 100 is JLCPCB's cheapest size |

**Why not the classic ESP32 (WROVER-E) that was tested.** It costs the same at 5 boards:
- its module is cheaper ($3.81, C2973667)
- it needs a CH340C ($0.61, plus a $3.07 feeder fee) and two transistors

The S3 has fewer parts, USB of its own, more of everything, and about 8 times the stock. The cost
is a new board profile, and a bench test on an S3 before ordering.

## The key bus

Every kind of key meets the same five things:
- a switched 3.3 V, VKEY
- ground
- SDA and SCL, with 2.2 kΩ pull-ups to VKEY
- ESD protection

Only the connector differs. **One key at a time:** they all share the bus.

1. **key-c's plug** (J2): the vertical USB-C plug console-a uses (C399939).
   - SDA on A6, SCL on A7.
   - CC (A5) and VCONN (B5) are each read on their own ADC pin, through 1 kΩ, with a 10 kΩ pull-up.
     A key shows its 5.1 kΩ on both.
   - The circuit is console-a's ([README](../console-pcb/README.md#the-key-port)), as
     [PROPOSALS.md](../key-pcb/PROPOSALS.md#the-console-end-of-key-c) asks.
2. **A STEMMA QT socket** (J3, JST SH 4-pin): Adafruit's ATECC608 breakout (4209), the chip the
   bench test used, plugs in with its cable.
3. **A 1×8 key header** in rev A's finger order: GND, SDA, SCL, VKEY, ID, (none), RST, DETECT.
   - It serves a card-edge socket for key-a or key-b, key-d's pogo block, or a cartridge not yet
     designed, on a small board or on wires.
   - DETECT has a 10 kΩ pull-up. ID has a 10 kΩ pull-up into an ADC, for the KEY ID resistor.

**VKEY** comes from an AP22653W6-7 load switch fed from 3.3 V, as on console-a:
- current-limited to about 80 mA, reverse-blocking, and it discharges its output when off
- its enable has a 10 kΩ pull-up, so the key is powered unless the firmware turns it off. Today's
  console expects exactly that
- its fault flag goes to a GPIO

**ESD:**
- a USBLC6 on SDA and SCL
- a USBLC6 on the two CC lines
- an ESD5Z5V0 on VKEY

The USBLC6 rails go to 3.3 V, never VKEY, so the pull-ups can't feed a key that's switched off.

## Pins (draft)

Checked against the WROOM-1 datasheet's pin table (v1.3).
- **Never used:** GPIO35–37, the octal PSRAM; and GPIO19/20, USB.
- **ADC2 is avoided** for analog: Wi-Fi can block it. CC1, CC2 and ID are on ADC1 (GPIO1–10).
- **GPIO45 must be low at power-up** or the flash gets the wrong voltage, as IO12 on the classic
  ESP32. Nothing on the board pulls it.

| signal | GPIO | notes |
|---|---|---|
| USB D−, D+ | 19, 20 | the S3's own USB |
| BOOT | 0 | to GND; held at reset, the S3 waits for new firmware |
| RESET | EN | to GND; 10 kΩ pull-up and 1 µF, as Espressif draws it |
| screen CS, MOSI, SCK | 10, 11, 12 | FSPI's own pins, so the SPI runs without the GPIO matrix |
| screen DC, RST, BL | 13, 14, 21 | |
| key SDA, SCL | 8, 9 | |
| key CC1, CC2 | 1, 2 | ADC1 |
| key ID | 4 | ADC1 |
| key DETECT | 5 | |
| key power on, fault | 6, 7 | |
| key RST | 15 | Trust M only |
| Sign (A), Back (B), Reject (Y) | 16, 17, 18 | the roles in `firmware/quorum.py` |
| Up, Down | 38, 39 | a turn of the knob, as buttons |
| Select, and the knob's push | 40 | |
| knob A, B | 41, 42 | the pulse counter |
| status LED | 48 | |
| UART0 TX, RX | 43, 44 | breakout only, for a serial adapter |
| free | 3, 45, 46, 47 | breakout. 3, 45 and 46 are boot pins: nothing may drive them at power-up |

Every pin above except 19, 20 and 35–37 is on the breakout too. An add-on on a pin the board uses
shares it: the silkscreen says which.

A board generator, like console-a's `gen_console.py`, should read these from `firmware/board.py`
and stop if they disagree.

## Parts and prices

From JLCPCB's parts search, 2026-10-11. "Ext" parts cost a $3.07 feeder fee each per order.
Basic parts cost nothing extra.

| ref | part | LCSC | type | stock | each, 1–9 | 10–29 | 100+ |
|---|---|---|---|---|---|---|---|
| U1 | ESP32-S3-WROOM-1-N16R8 | C2913202 | ext | 34,398 | $5.15 | $4.52 | $3.61 |
| J1 | USB-C socket, HCTL HC-TYPE-C-16P-01A | C2894897 | ext | 42,422 | $0.10 + $0.03 handling | | $0.08 |
| U2 | AMS1117-3.3, SOT-223 | C6186 | basic | 1.2 M | $0.21 | $0.21 | $0.16 |
| U3–U5 | USBLC6-2SC6 (ST) | C7519 | ext | 48,756 | $0.18 | $0.18 | $0.14 |
| U6 | AP22653W6-7 | C2158037 | ext | 13,739 | $0.26 | $0.26 | $0.21 |
| D1 | ESD5Z5V0 | C502546 | ext | 125,980 | $0.02 | | |
| J2 | key-c plug, 918-118A2021Y40002 | C399939 | ext | **201** | $0.60 | $0.48 | $0.36 |
| J3 | STEMMA QT, JST SM04B-SRSS-TB | C160404 | ext | 24,508 | $0.21 | $0.21 | $0.17 |
| SW1–SW8 | tact, TS-1187A-B-A-B | C318884 | basic | 379,890 | $0.02 | | |
| D2, D3 | red 0603 (status), green 0805 (power) | C2286, C2297 | basic | | $0.01, $0.02 | | |
| R | 17 × 0402: 5.1k, 10k, 1k, 2.2k | C25905, C25744, C11702, C25879 | basic | | under $0.01 | | |
| C | 6 × 100 nF, 1 µF, 3 × 10 µF, 22 µF | C1525, C52923, C19702, C45783 | basic | | $0.31 together | | |

- **J2's stock is low.** It was 850 on 2026-10-07 and 201 today. Enough for a first batch. The
  HX "TYPE C-M 16P V-SMT" (C55200592, 866 in stock, $0.67) may be a second source. Check its
  drawing first.
- 7 extended types: $21.49 in feeder fees per order.

## What a batch costs

| | 5 boards | 20 | 100 |
|---|---|---|---|
| parts, each | $7.70 | $6.95 | $5.64 |
| parts, all | $38.50 | $139 | $564 |
| setup $8.18, stencil $1.53, feeders $21.49 | $31.20 | $31.20 | $31.20 |
| placement, about 209 joints a board at $0.0016 | $1.67 | $6.69 | $33.44 |
| bare boards (estimate, below) | $5–10 | $15–25 | $40–60 |
| **before shipping** | **$76–81** | **$192–202** | **$669–689** |
| **each** | **about $16** | **about $10** | **about $7** |

How these were found:
- **Parts:** JLCPCB's parts search on 2026-10-11.
- **Fees:** JLCPCB's assembly price page, updated 2026-09-09. key-c's order on 2026-10-02 paid
  nearly the same: $8.24, $1.55 and $3.09
  ([buildlog](../../buildlog/2026-10-02-key-c-order.md)).
- **The module** is two-thirds of the parts cost.

**Not looked up exactly:**
- **The bare boards.** JLCPCB advertises "from $2.00 / 5 pcs". key-c's five 16 × 36 mm boards
  came to $6.22 with lead-free HASL and options. The real figure comes from uploading the Gerbers.
- **Shipping and US duty.** key-c paid $7.51 shipping and $2.28 sales tax by Global Standard.
  Above $59 the buildlog says to use express with DDP. JLCPCB says the US tariff it prepays
  changed in March 2026. Expect tens of dollars more. The checkout shows the number.

**Options:**
- **JLCPCB fits the through-hole headers too:** about $15 more for 5 boards. That's manual
  assembly at $0.0164 a joint, $3.58 labor, and the headers with their feeder fee. Or solder them
  yourself.
- **A polyfuse on USB 5 V** (C20978, $0.07): one more feeder fee.

**To try the firmware first:** an ESP32-S3-DevKitC-1-N8R8 (or N16R8). Digi-Key lists it at
€12.85; clones cost less. It's the same chip and PSRAM as U1, with 8 MB of flash instead of 16.

## Firmware changes

None of this is written yet. Each is small.

1. **`board.py`: an `"s3"` profile.**
   - `sys.platform` is `"esp32"` on both chips. Today an S3 would get the classic profile, whose
     IO22, IO23 and IO25 don't exist on it. So tell them apart by `os.uname().machine`, which
     names the S3. Check that on the DevKit.
   - The profile holds the pins above. `KNOB` is on, so the console uses its knob screens.
   - `KEYS` adds `"up"` and `"down"` on GPIO38/39. In knob mode `quorum.py` treats those exactly as
     a turn (`turned()`), and Select is the knob's own push pin.
   - The classic `"esp32"` profile stays, for the DevKit already wired.
2. **The key's detect and power.** VKEY is on by default, so today's console works as it is.
   Later, the detect, power, scan order in [BUILD1.md](../wiring/BUILD1.md#how-the-key-is-detected-and-powered)
   (from `bench1.py`), on CC for key-c and DETECT for the header.
3. **`tools/usb` and `tools/fw`:** find the board by Espressif's USB ID (303a). Until then,
   `PICO_PORT=/dev/ttyACM0` works.
4. **MicroPython:** the `ESP32_GENERIC_S3` build, variant `SPIRAM_OCT` for octal PSRAM. Flash it
   at address 0. The repository's ESP32 work reads against 1.26; the latest release is 1.29.0.
5. **Tests:** `test-vectors/esp32_test.py` runs the S3 profile too.
6. **A new release fingerprint** (AGENTS.md rule 2): `node tools/releases/badge.mjs`, and
   rebuild the console page.

## Before drawing

- [ ] Run the console on an S3 DevKit with the new profile: screen, buttons, a knob on the header
      pins, Wi-Fi, HTTPS, signing.
- [ ] Read the bench screen module's header order and the KY-040's off the real parts.
- [ ] Decide the board's shape: where key-c stands, and whether the screen module sits on the
      board or on wires.

## Before ordering

- [ ] ERC, DRC and parity clean, as `tools/keypcb check` does for the other boards.
- [ ] J2's stock, and every rotation in JLCPCB's placement preview (the lessons in key-c's
      [buildlog](../../buildlog/2026-10-02-key-c-order.md#lessons-from-the-first-order)).
- [ ] The module's antenna past the board edge, or over a cut-out, with no copper under it (the
      module datasheet's layout section).

## Open

- [ ] Fit the breakout headers at JLCPCB, or solder them?
- [ ] A polyfuse on USB 5 V?
- [ ] A battery later? Not in this plan.
