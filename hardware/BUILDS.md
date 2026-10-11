# Console builds: shopping lists

> **A survey, 2026-10-11.** Prices and stock come from each store's page on that date. Nothing
> here is bought or tested. Where a fact came from a reseller or a search result instead of the
> maker, it says "unverified".

How to build a console without designing a whole board. They run from "buy one board and print a
case" to "a dev board on a carrier PCB of our own". In every one, the only part we make ourselves
is the key.

The firmware decides a lot here:
- **Screens.** It drives ST7789 and ST7735 screens over SPI, at 240 × 240, 320 × 240 and
  160 × 128. Another size needs a new layout. Another controller (ILI9341, ST7796, GC9A01, QSPI
  AMOLED, or an 8-bit parallel bus) needs a new driver.
- **Memory.** An ESP32 needs PSRAM ([wiring/ESP32.md](wiring/ESP32.md#will-the-whole-console-fit)).
- **The chip.** It's an ATECC608 on I2C at 3.3 V. On a Pico the firmware uses GP4 (SDA) and GP5
  (SCL).
- **A new board means a new pin table** in `firmware/board.py`, and so a new release
  fingerprint (AGENTS.md rule 2).

## The builds at a glance

| | build | you buy | about | custom | firmware |
|---|---|---|---|---|---|
| 1 | **Pico + Display Pack 2.8″** | Pico 2 WH, Pimoroni Display Pack 2.8″, the chip on a Qwiic cable | **$32**, $42 with a knob | a printed case | a board profile, and an I2C knob or a 4-button layout |
| 2 | **The upstream build, tidied** | Pico 2 WH, Pico Omnibus, Waveshare Pico-LCD-1.3, the chip on a cable | **$31** | a printed case | **none** |
| 3 | **An ESP32 board with a screen** | Adafruit Reverse TFT Feather, LilyGO T-Embed or LilyGO T-Deck | $31–54 | a printed case | a board profile, a layout, inputs |
| 4 | **A dev board on our own carrier PCB** | Pico 2 W or Waveshare ESP32-S3-Pico, a screen, a knob | ~$12 carrier + board + screen | the carrier (JLCPCB assembles it) | none on a Pico, a profile on the S3 |
| 5 | **Fully our own board** | nothing but the key | ~$16 at 5, ~$7 at 100 | everything | an S3 profile ([devkit-s3](devkit-s3/PLAN.md)) |

Each total includes Adafruit's ATECC608 breakout (4314, $4.95) and a cable. None includes
shipping, tax or a case.

## 1. Pico + Pimoroni Display Pack 2.8″

The closest thing to the upstream build that has a proper port for the chip. Pimoroni's
[schematic](https://cdn.shopify.com/s/files/1/0174/1800/files/pico_display_2_8_schematic.pdf?v=1728314048)
puts its Qw/ST (Qwiic) socket on **GP4 and GP5, the pins `atecc.py` already uses**.

| part | price | store |
|---|---|---|
| Raspberry Pi Pico 2 WH (with headers) | $9 | Pimoroni US, in stock |
| Pico Display Pack 2.8″ (PIM715): 320 × 240 ST7789V, buttons A/B/X/Y, RGB LED, Qw/ST | $17 on sale, $22 list | Pimoroni US (stock unclear: check) |
| ATECC608 breakout, STEMMA QT (4314) | $4.95 | Adafruit |
| STEMMA QT cable, 100 mm (4210) | $0.95 | Adafruit |
| *optional:* I2C rotary encoder with the encoder fitted (5880) + a second cable | $8.90 | Adafruit |
| *optional:* 35 mm "scrubber" knob (2055), snaps onto Adafruit's encoders | $0.95 | Adafruit |

**Pins**, from the schematic:
- screen DC, CS, SCK, MOSI and backlight on GP16–20
- buttons A, B, X and Y on GP12–15
- LED on GP26–28

**Firmware:** a new board profile with the pins above. Then the console needs a way to move:
- **With the I2C knob:** the knob and the pack's A, B and Y are exactly knob mode: turn and push,
  with Sign, Back and Reject. `knob.py` would read the knob over I2C instead of from pins.
- **Without it:** a layout for four buttons alone. Four buttons for next, back, select, Sign and
  Reject takes some design.

**Catches:**
- The Qw/ST power is always on, so the firmware can't switch the key off.
- The knob would share the key's bus. Keep **Sign and Reject on the pack's own buttons**, never on
  anything that sits on that bus, so a key can't fake a press (AGENTS.md rule 1).
- The pack doesn't fit a Pico Decker.

A snap-on case for the pack is on Printables (model 1136102; not opened).

## 2. The upstream build, tidied

The upstream's problem was that the Waveshare screen covers the Pico's pins. A Pico Omnibus puts
the Pico and the screen side by side. The second slot then leaves the Pico's pins free as male
headers.

| part | price | store |
|---|---|---|
| Pico 2 WH | $9 | Pimoroni US |
| Pico Omnibus (two slots) | $8 on sale, $10 list | Pimoroni US |
| Waveshare Pico-LCD-1.3: 240 × 240, joystick and A/B/X/Y | $7.99 | Waveshare |
| ATECC608 breakout (4314) | $4.95 | Adafruit |
| STEMMA QT to female sockets (4397), onto GP4, GP5, 3V3 and GND | $0.95 | Adafruit |

- **Firmware: none.** It's today's default board, `BOARD = "waveshare"`.
- **Catch:** the chip still arrives on four loose sockets, though onto labelled pins now instead
  of into the screen's headers.
- Check how the Omnibus takes the screen before buying (unverified).

## 3. An ESP32 board with a screen

Most of these fail on the screen, the memory, the buttons or the port. These three pass, each
with a catch:

| board | why | catch | price |
|---|---|---|---|
| **Adafruit ESP32-S3 Reverse TFT Feather** (5691) | ST7789 over SPI, 3 buttons, 2 MB PSRAM. Its STEMMA QT port is 3.3 V **and its power can be switched**: key power for free | 1.14″ 240 × 135, a new layout. 3 buttons. PSRAM right at 2 MB. No case | $24.95, Adafruit, in stock |
| **LilyGO T-Embed** | ST7789 over SPI, a knob with push, 8 MB PSRAM, a shell (+$4) | 1.9″ 320 × 170, a new layout. No buttons for Sign and Reject. Grove or Qwiic and its voltage: sources disagree. Ships from China | $28–33, lilygo.cc |
| **LilyGO T-Deck** | 2.8″ 320 × 240 ST7789 over SPI, the layout we have. A trackball (a joystick) and a keyboard. 8 MB PSRAM | The keyboard is its own ESP32-C3 on I2C. Grove port, voltage unverified. No battery or case. Ships from China | $46.52, lilygo.cc |

**Ruled out:**
- **No PSRAM:** M5Stack Core Basic, Cardputer, Dial.
- **Touch only:** M5Stack Core2, CoreS3.
- **A new screen driver:**
  - parallel bus: LilyGO T-Display-S3
  - ST7796: T-Display-S3 Pro, T-LoRa Pager
  - QSPI: T-Encoder-Pro, Waveshare's knob displays
  - ILI9342C: M5Stack Fire
- **Wi-Fi the firmware can't use:** Seeed Wio Terminal, whose MCU is an ATSAMD51 with its radio on
  a second chip.

**M5Stack's Grove ports supply 5 V.** A chip breakout with pull-ups to its supply would pull the
ESP32's 3.3 V pins to 5 V. M5Stack's StickS3 ($21.50, 8 MB PSRAM, case and battery) is otherwise
tempting, but it has 2 buttons and that port.

## 4. A dev board on our own carrier PCB

The dev board brings the chip, its power and USB. The carrier brings the screen connector, the
knob, the buttons and the key port. JLCPCB assembles the carrier, and you solder or socket the dev
board. There's no radio, power or USB design to do.

**On a Pico 2 W, already drawn:**
- [console-pcb/console-a](console-pcb/README.md): Build 1's pins, the 2.8″ module, a knob, four
  buttons and key-c's plug
- [console-a](console-a/README.md): the Waveshare pins
- [console-pocket](console-pocket/README.md): the Waveshare pins in a pocket size

None is ordered. All run today's firmware. console-a estimates about $24 a console at 5 and $18 at
20, and $11.68 of that is the Pico. So the carrier is about $12 at 5 and $6 at 20.

**On an ESP32-S3:** the **Waveshare ESP32-S3-Pico** is the base to use.
- **Price:** $9–10, from Waveshare.
- **Footprint:** a Pico's, castellated, so it solders flat like the Pico on console-a.
  There's also a version with headers.
- **Memory and pins:** 16 MB flash, 2 MB PSRAM, 27 GPIO.
- **USB:** native, plus a USB-serial chip.
- **MicroPython** has its own build for it (`WAVESHARE_ESP32_S3_PICO`, from 1.29).

Waveshare says it fits Pico add-ons. If its power pins sit where a Pico's do (unverified), one
carrier could take either a Pico 2 W or this board, with a pin table for each. Waveshare's own
docs disagree about its PSRAM type, so check the schematic.

Other bases:
- **Espressif ESP32-S3-DevKitC-1-N8R8:** 8 MB PSRAM, headers only, €12.85 at Digi-Key, but out of
  stock there and at Adafruit.
- **Unexpected Maker NanoS3:** castellated, 8 MB PSRAM, $20. Out of stock, and the carrier would
  need its own USB-C.
- **Seeed XIAO ESP32S3:** too few pins (11).

**Connecting the screen.** Pick one per carrier:

| connector | screens | price |
|---|---|---|
| 1×8 header, 2.54 mm | modules like the bench's 2.8″ and Waveshare's 2″ (ST7789VW, comes with an 8-wire cable) | Waveshare 2″: $10.99 |
| FPC socket | bare panels, the cheapest and thinnest: 2.8″ 320 × 240 ST7789 (LCSC C5329584, 401 in stock); 2.0″ (C5329586) | $4.93; $5.10 |
| EYESPI (18-pin 0.5 mm FPC) | Adafruit's displays: one flat cable, no soldering. 2.0″ 320 × 240 ST7789 (4311) | cable $0.75–0.95; 4311 $19.95 |

Read each bare panel's datasheet for its pin count. Avoid ILI9341 screens: Waveshare's 2.4″, and
Adafruit's 2.2″, 2.4″ and 2.8″. The firmware has no init for them yet.

## 5. Fully our own board

[devkit-s3/PLAN.md](devkit-s3/PLAN.md): an ESP32-S3 module, USB-C, a regulator, buttons, a knob
header and the key port, all assembled by JLCPCB. It costs about $16 a board at 5 and about $7 at
100. It's the cheapest at volume and the most work.

## Parts for any build

**A chunky knob:**

| part | | price |
|---|---|---|
| Adafruit I2C rotary encoder, encoder fitted (5880) | Qwiic, takes no pins, one RGB LED (red on a red page) | $7.95 |
| Adafruit rotary encoder + knob (377) | 24 detents, push, on pins | $4.50 |
| Bourns PEC11R-4215F-S0024 | console-a's knob, on pins; get a knurled-shaft PEC11R for metal knobs | $2.95 Digi-Key, $2.35 LCSC |
| 35 mm scrubber knob (2055) | snaps onto Adafruit's encoders | $0.95 |
| 20 mm aluminum knob (5527) | 6 mm bore, set screw | $2.95 |

**A guarded Sign button:**
- A 30 mm arcade button (Adafruit 3489, $2.50), sunk in a printed collar a few millimetres
  proud of the cap. It's hard to press by accident and easy to hold. Its red and yellow LEDs need
  5 V.
- 12 mm tactile switches with caps (1010, 15 for $5.95) for Reject and Back.
- Missile-switch covers fit toggles only.

**Qwiic plumbing:** cables 50–400 mm, $0.95–1.50 (Adafruit); a 5-port hub (5625, $2.50);
Qwiic-to-Grove (SparkFun PRT-15109, $1.95). There's no panel-mount Qwiic part: run a short cable to
a printed bracket at the case wall.

**Cases** (search results, not opened):
- Display Pack 2.8: Printables 1136102
- ESP32-S3-DevKitC-1: Printables 565403, MakerWorld 1763319

## What this suggests

1. **To show people now: build 1.** About $32 to $42, with a Qwiic port on the pins the firmware
   already uses. Write its profile and the I2C knob, and print a case. Or build 2 today, with no
   firmware change at all.
2. **To give people a kit: build 4.** The Pico carriers are drawn. The same carrier could take a
   Waveshare ESP32-S3-Pico if the footprints really match.
3. **At volume: build 5.**

In all of them, what we make is the key, and on 4 and 5 the carrier.
