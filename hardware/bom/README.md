# Parts

## The dev console (today)

The build picowallet started from. It runs everything in test ladder rung 1. Build guide:
[DEV-CONSOLE.md](../DEV-CONSOLE.md).

| part | ~price | source |
|---|---|---|
| Raspberry Pi Pico 2 W, **pre-soldered header** | $12 | Amazon `B0DRJXPPWL` (Freenove) or any Pico 2 W with headers |
| Waveshare Pico-LCD-1.3 (240×240 IPS, joystick, A/B/X/Y) | $15 | Amazon `B092VVCBQP` |
| Adafruit ATECC608 breakout, STEMMA QT | $6 | Adafruit 4314 |
| STEMMA QT / JST-SH 4-pin cable, any ends | $1 to $8 | Amazon `B08HQ1VSVL`, or Adafruit 4209 (snip the pins off and strip) |
| micro-USB cable, data not charge-only | | |

About $35, no soldering. A printed case that fits: [DEV-CONSOLE.md](../DEV-CONSOLE.md#wiring).

For the soldered perfboard version with an 18650 cell (a protected cell or a DW01 board, a holder,
an SPST switch, a 1N5817 Schottky, and an optional 2 × 100 kΩ + 100 nF battery gauge), see
[hardware/wiring/SOLDERING.md](../wiring/SOLDERING.md#parts).

## Build 1

The first console with the real parts ([BUILD1.md](../wiring/BUILD1.md)): a Pico 2 W, a 2.0″ ST7789
240×320 SPI screen (8-pin), an EC11 rotary encoder with push, a 3.5 mm and a 2.5 mm TRRS jack and
plug, and an ATECC608 STEMMA QT breakout as the stand-in key.

Still to buy for the full version (from the Build 1 bench, 2026-09-27):

| part | unblocks |
|---|---|
| TP4056 module **with** DW01 protection, 1N5817, SPST slide switch | the battery build ([SOLDERING.md](../wiring/SOLDERING.md#2-battery-switch-diode)) |
| resistors: 100k ×2 | the battery gauge on GP28 |
| resistors: 10k | console-side I2C pull-ups once a key is a bare chip without a breakout |
| resistors: 1k, and a 2N3906 or S8550 PNP | a key power switch, if GP6 alone can't carry signing (open decision) |
| resistors: 33k, 10k | ID resistor codes on GP27, if the ID line gets used |
| resistors: 100 Ω | series on SDA and SCL at J1, to limit current while a plug wipes across the contacts |
| caps: 100 nF | key decoupling, the battery gauge |
| tact switches | Sign (A, GP15) and Reject (Y, GP21), then B and X |

## Key PCB, rev A

The order itself is in [key-pcb/ORDERING.md](../key-pcb/ORDERING.md).

| part | qty | source | notes |
|---|---|---|---|
| key-a bare boards, ENIG, 1.6 mm | 5–10 | JLCPCB, `key-a-soic/fab/key-a-soic-gerbers.zip` | gold-finger option off |
| ATECC608C-SSHDA-B (SOIC-8) | 10 | Digi-Key 150-ATECC608C-SSHDA-B-ND | out of stock until Jan 2027 on 2026-10-02; see ORDERING.md |
| USBLC6-2SC6 | 10 | Digi-Key 497-5235-1-ND | |
| 100 nF 0805 X7R | 10 | any | |
| key-b boards, assembled | 5 | JLCPCB Economic PCBA, `key-b-udfn/fab/` | ATECC608C-MAHDA-S is C23291019, pre-order if short |
| Card-edge socket, 0.100″, 0.062″ card, 8/16 positions | 1–2 | Sullins EBC08DRXN (the 5/10 size is Digi-Key S9641-ND) | the console side; hand-solder, never reflow |
| Sullins PLA-K1 polarizing key | 2 | Digi-Key PLA-K1-ND | optional; check which way it sits |

## The cartridge bay

For [hardware/case/](../case/README.md). Nothing ordered yet.

| part | qty | notes |
|---|---|---|
| 2 mm steel dowel pins, 12 mm (P3) and 16 mm (P2) | a few of each | the lock pins, pressed into the carriage |
| microswitch, D2F size (12.8 × 5.8 × 6.5 mm body, pin plunger) | 2 | cuts the console's 5 V until the key is locked; check its operating point and overtravel against `cartridge.py` |
| USB-C male plug breakout | 2 | the console's plug at the back of the bay; measure it against the pocket |
| M2 × 8 screws for plastic | 8 | the bottom plate |

## First order for the PicoQuorum console and keys

From the [kickoff](../../docs/KICKOFF.md#first-parts-order). Nothing ordered yet.

| part | qty | notes |
|---|---|---|
| Raspberry Pi Pico 2 W | 2 | |
| Adafruit ATECC608 breakout, STEMMA QT | 2–3 | what the current firmware drives |
| Adafruit Trust M breakout | 2–3 | evaluation for `firmware/trustm.py` (from upstream, not yet run on a chip here) |
| Momentary push buttons, thumb-sized, green and red | a few of each | compare feel |
| Flip-up switch cover or guard hardware | | Sign button guard |
| ¼″ stereo plugs (solder type), ¼″ stereo switched jacks | extras | key connector: SDA, SCL, GND |
| 3.5 mm plugs (solder type), 3.5 mm switched jacks | extras | key connector: VCC, spare, GND |
| Rotary encoder with push switch | 1–2 | paging |
| 2.0″ and 2.8″ 320×240 SPI screens | 1 each | compare |
| Load switch and ESD/TVS parts, or breakouts | | key VCC current limit; SDA, SCL, VCC protection |
| Status LEDs, assorted resistors and capacitors | | |
