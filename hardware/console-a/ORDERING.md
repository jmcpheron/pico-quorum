# Ordering console-a

How to get a quote for the [console board](README.md) and then order it. The PCB basics (what
Gerbers, a BOM and a CPL are, and how to open a board in KiCad) are in the key's
[ORDERING.md](../key-pcb/ORDERING.md). This page only adds what's different here.

Prices and stock were looked up on JLCPCB's parts search on 2026-10-07. Check them again, and trust
the quote JLCPCB shows over the numbers here.

## 1. The files

All in `console-a/fab/`, written by `tools/keypcb fab console-a`:

| file | what |
|---|---|
| `console-a-gerbers.zip` | Gerbers and drill files: 2 layers, 92 × 52 mm |
| `bom.csv` | 30 parts on 13 lines, by LCSC number |
| `cpl.csv` | where each of the 30 goes, all on the top side |
| `factory-pico/bom.csv`, `factory-pico/cpl.csv` | the same 30, plus U1, the Pico 2 W, on the bottom: for [a factory-soldered Pico](#2b-factory-soldered-pico) |

The panel and the key pads are never in the BOM or the CPL: you fit those yourself. The Pico is
in the `factory-pico` pair only.

Before you upload anything, run `tools/keypcb check console-a` (ERC, DRC, parity and the pin map)
and `tools/keypcb fab console-a`, then `git status`: the fab files should match the board.

## 2. At jlcpcb.com

1. Upload `console-a-gerbers.zip`. It should read 92 × 52 mm, 2 layers.

| setting | choose | why |
|---|---|---|
| Layers | 2 | |
| PCB qty | 5 | the minimum; enough for a first look |
| Thickness | 1.6 mm | |
| Surface finish | HASL lead-free | Economic PCBA takes it, and nothing here needs gold |
| Mask colour | any | |
| Mark on PCB | "Remove mark" if offered | |
| PCB Assembly | **on**, Economic, **top side** | everything JLCPCB places is on the front. The back's paste layer is for the Pico, which you solder |
| Assembly qty | 2 to 5 | fewer than the boards is fine |

2. Upload `bom.csv` and `cpl.csv`. Every line should match an LCSC part:

| part | LCSC | class | ~each |
|---|---|---|---|
| TS-1187A-B-A-B tact switch ×9 | C318884 | Basic | $0.02 |
| AFC07-S24FCA-00, 24-pin 0.5 mm FPC (J2) | C262567 | Extended | $0.13 |
| TPS22945DCKR load switch (U2) | C47507 | Extended | $0.52 |
| USBLC6-2SC6 ESD (U3, U4) | C7519 | Extended | $0.18 |
| SS8050 NPN (Q1) | C2150 | Basic | $0.02 |
| B5819W Schottky (D1) | C8598 | Basic | $0.03 |
| 0603 resistors and capacitors (R1–R11, C1–C4) | C22859, C21190, C4190, C25804, C25803, C14663, C15849 | Basic | under $0.02 |

3. **Check the placement preview, part by part.** Look at every pin 1, especially J2, U2, U3, U4,
   Q1 and D1. On key-c, a SOIC-8 and a SOT-23-6 came up 90° off. If one is turned, rotate it in the
   preview, and write down the correction in README.md's log.
4. Read the quote, then decide. The quote is free; ordering is a separate step.

## 2b. Factory-soldered Pico

The same order with `fab/factory-pico/bom.csv` and `fab/factory-pico/cpl.csv` in place of the two
in `fab/`. The Gerbers are the same zip. What changes:

| setting | choose | why |
|---|---|---|
| PCB Assembly | **on**, **both sides** | U1, the Pico, is on the back; everything else is on the front. Take Economic if JLCPCB offers it for two sides, otherwise Standard |
| X-ray | accept it | JLCPCB marks C42394205 "X-ray inspection required": the castellations are under the module |

- **U1 is LCSC C42394205**: "Raspberry Pi Pico 2W", Raspberry Pi SC1633, the Pico 2 W without
  headers. On 2026-10-07 it was Extended, $11.68, with 82 in stock and 67 more on pre-order.
- **For more boards than JLCPCB holds,** pre-order the Picos into your parts library first
  (JLCPCB → Parts Manager). Library parts can only be used in assembly; JLCPCB won't ship them to
  you.
- **In the placement preview, look hardest at U1:**
  - It's on the bottom, with its USB end at the board's bottom edge and its antenna end over the
    notch.
  - Its two USB-connector pegs sit over their holes.
  - Bottom-side rotations are where a CPL most often goes wrong, so fix any turn in the preview
    and note it in README.md's log.
- **What it adds, roughly:** the dearer Pico ($11.68 against about $7 retail), a second side's
  setup, X-ray, and one more Extended-part fee. In return, nobody hand-solders 40 joints per
  console. Only the quote says how much it adds.

### What the quote should look like

These are estimates from the part prices above and from key-c's order. They are not a quote.

- **5 boards, 2–5 assembled:**
  - Bare boards: a few dollars.
  - JLCPCB's assembly setup and stencil: about $10.
  - About $3 for each of the 3 Extended parts: $9.
  - Parts: about $1.40 a board, plus each part's minimum quantity.
  - Shipping comes on top.
  - key-c, a smaller assembled order, came to $38.96.
- **At 20 to 100 boards:** the setup and Extended-part fees are once per order, so a board's own
  share drops to a few dollars. Add per board:
  - a Pico 2 W: about $7 if you solder it, $11.68 if JLCPCB does
  - a panel: $7.50–12.50 ([README.md](README.md#getting-the-right-panel))
  - foam tape
  - wire for the key

## 3. Parts you buy yourself

| part | qty | where | notes |
|---|---|---|---|
| Raspberry Pi Pico 2 W, **no headers** (SC1633) | 1 a board | any Raspberry Pi reseller | only if you solder it yourself; with `factory-pico`, JLCPCB supplies it |
| 1.3″ 240×240 ST7789 panel, **24-pin plug-in** (ZJY133T-IF05) | 1 a board, and ~10% spare | [Adafruit 4520](https://www.adafruit.com/product/4520), or [Smart Prototyping 102108](https://www.smart-prototyping.com/1_3-inch-TFT-IPS-Bare-Display-ST7789-SPI-240-240) "Plug-in type 24pin" | how to tell the right one, and to check a batch: [README.md](README.md#getting-the-right-panel) |
| Double-sided foam tape, 2–2.5 mm | a strip | any | under the panel |
| Thin wire, or a USB-C receptacle breakout | | | for the key, on J3 |

## 4. When the boards come

1. Look at J2 under a loupe for bridges between its 0.5 mm pins.
2. Meter it before the Pico goes on (with `factory-pico`, before first power):
   - 3V3 to GND isn't a short.
   - Each button reads closed only while pressed.
   - The 3V3 pin of the Pico's footprint reaches J2's pins 1, 4, 5, 6 and 11 (panel numbering).
3. Solder the Pico 2 W flat on the back:
   - USB at the bottom edge, antenna over the notch.
   - Tack two opposite corner pins, check it's straight, then do the rest.
   - With `factory-pico` it's already on: check it sits flat and square, and look along both
     rows for bridges.
4. Plug in the panel's tail (slide lock out, tail in, lock in), fold the panel over onto the foam
   tape, and flash the console image as for the dev console ([DEV-CONSOLE.md](../DEV-CONSOLE.md)).
   It's the same image, `BOARD = "waveshare"`.
5. Only after the screen and buttons work, wire a key to J3. For the console image as it is,
   close JP1 (README.md, "The key port"). Lock nothing until the key reads back right (0x60 on the
   bus, its serial and its config). Practise on a spare (docs/LOCKING.md).
