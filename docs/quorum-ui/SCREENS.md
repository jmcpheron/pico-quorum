# Plan: one approval flow, six screen sizes

The Lonely Binary 6-pack is on its way. This plan covers:
- what each screen can be in PicoQuorum;
- how the approval flow should reflow for each;
- what has to change in the firmware and emulator;
- the order to do it in.

It also feeds the kickoff's open decision on the console's
[screen size](../KICKOFF.md#screen-candidates).

Status: **a plan for review**. Nothing here is built yet. Answer the [questions](#questions) inline
or in a PR comment.

## The screens

From the vendor's table ([lonelybinary/TFT-LCD](https://github.com/lonelybinary/TFT-LCD/blob/main/tft-lcd/README.md)).
None has touch, and all use the same 15-pin FPC and 8 wires.

| Size | Pixels | Driver | Density | Text at our 14 px body size | Role in PicoQuorum |
|---|---|---|---|---|---|
| 0.96″ | 80 × 160 | ST7735S | ~186 ppi | small | **Status strip**, never an approval screen |
| 1.3″ (today) | 240 × 240 | ST7789 | ~261 ppi | smallest | the dev console |
| 1.8″ | 128 × 160 | ST7735S | ~114 ppi | large, coarse | **Pocket signer**: one fact per screen |
| 2.0″ | 240 × 320 | ST7789 | ~200 ppi | crisp | **Console** candidate |
| 2.4″ | 240 × 320 | ST7789 | ~167 ppi | comfortable | **Console** candidate |
| 2.8″ | 240 × 320 | ST7789 | ~143 ppi | big | **Console** candidate (readable at arm's length) |
| 3.5″ | 320 × 480 | ST7796 | ~165 ppi | big, and room | **Console, everything on one screen** |

What the numbers mean:
- **The 2.0″, 2.4″ and 2.8″ are the same 240 × 320 pixels.** One layout serves all three, and
  choosing between them is purely about physical size and readability. We decide by holding them.
- **Today's screen is 240 wide.** Those three are 80 px taller, so today's screens mostly just
  gain room.
- **The 3.5″ is the only one where the whole transaction fits on one screen.** Its ST7796 takes
  the same 16-bit colour over SPI as our ST7789, which is easy. Some 3.5″ panels use an ILI9488,
  which needs 18-bit colour; this one doesn't.

## The flow, the same everywhere

Every size runs the same flow. The content model is the same everywhere; only how many pages it
takes changes.

```
Queue ─▶ Summary ─▶ What it does (1 per action) ─▶ Red pages ─▶ Calldata ─▶ Verify ─▶ Hold ─▶ Result
 glance      understand                                                  check    decide
```

**Rules that never change with the size.** These are the safety model, not layout choices:

1. The hash is computed on the device from the fields shown, and a lie is refused.
2. Every page must be seen before SIGN arms, and signing is a hold: longer when anything is red.
3. Every address that matters is shown **in full** somewhere before signing, in 4-character
   chunks. A name or logo is only a hint next to it.
4. The contract being called is in the header: logo and "known", or ⚠ unknown.
5. The verify page (last 8 of the hash, the full hash, a blockie) is always there.
6. Reject is always one press, with no hold.

**The idea that makes it work on every size:** stop placing things at fixed pixel positions, and
build pages out of **blocks** that the screen packs in order. The blocks are headline, recipient,
address, approvals, warning, calldata and verify code. A small screen gets more pages and a big
one fewer. The pages still come out in the same order, and the "see every page" rule still counts
them.

How many pages a transaction takes (targets, not measurements):

| Transaction | 1.8″ 128×160 | 1.3″ 240×240 (today) | 2.x″ 240×320 | 3.5″ 320×480 |
|---|---|---|---|---|
| Send ETH to a known name | 6 | 3 | 2 | **1** |
| Batch of 2 (MultiSend) | 10 | 4 | 3 | **1–2** |
| Add owner (red) | 7 | 3 | 2 | **1** |
| Unknown call | 8 | 4 | 3 | **2** |

## Per size

### 3.5″, 320 × 480: the console with everything on one screen

**Portrait**, with the green Sign button beside the top and the red Reject beside the bottom
(where the kickoff puts them):

```
┌──────────────────────────────┐
│ SIGN · hold 2 s          (●)─┼─ guarded green button
│ #0 → transfer · Local · v1.4 │
│ Send 0.05 ETH                │  headline, 32 px
│ to Carol                     │
│ 0x90f7 9bf6 eb2c 4f87 0365   │  full address, 16 px mono
│   e785 982e 1f10 1e93 b906   │
├──────────────────────────────┤
│ 1 of 2  ● Alice ○ Bob ○ You  │
│ Yours makes it 2 of 2 · ready│
├──────────────────────────────┤
│ CHECK WITH THE PROPOSER      │
│ 7f99 f59f         ▓▓ blockie │  36 px mono
│ 0x2051 5d50 e59b 09a9 …      │
├──────────────────────────────┤
│ REJECT                   (●)─┼─ red button
└──────────────────────────────┘
```

- **A simple transaction** is one screen. Nothing to page through: seen means signable.
- **A batch** lists its calls in the middle. More than about 4 calls, or any red call, adds pages.
- **A red page** turns the whole middle red, as today.
- **The verify page's QR code of the hash** fits here, for a phone to scan and compare.
- **Landscape (480 × 320)** is the alternative: two columns. The left one says what it does; the
  right one, next to the buttons, holds approvals, the verify code and the button labels.
  Question 2.
- **Memory:** a full 320 × 480 frame is 300 KB, too much for the Pico's heap. It gets drawn in
  bands: a 320 × 96 strip (60 KB) is drawn 5 times, each shifted up, and framebuf clips the rest.
  - Same drawing code, about 5× the drawing time: still under a quarter of a second for a
    screen that changes when you press something.
  - The hold bar only redraws its own band.

### 2.0″, 2.4″, 2.8″, 240 × 320: the console as today's screens, taller

Today's screens, 80 px taller:
- **Summary:** it gains the recipient's full address. For a simple send, summary + verify is 2
  pages instead of 3.
- **Verify:** it gains the QR code of the hash under the code.
- **Queue:** it shows 6 rows instead of 4.
- **Owners:** it shows all owners with no scrolling.
- **Framebuffer:** 150 KB, about 35 KB more than today. It should fit the Pico 2 W's heap; I'll
  measure it on the board. If it doesn't, the same band drawing as the 3.5″ works here too.

The 2.8″ has the same pixels in a bigger body, so the same 14 px text is about 1.8× larger
physically than on today's 1.3″. That's the argument for it: an address you can compare from
arm's length.

### 1.8″, 128 × 160: a pocket signer, one fact per screen

Think Ledger Nano: small, with a big word per screen.

```
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│#0 Local   1/6 │  │#0         2/6 │  │#0         3/6 │  │#0         6/6 │
│ SEND          │  │ TO  Carol     │  │ 1 of 2        │  │ ends in       │
│ 0.05          │  │ 0x90f7 9bf6   │  │ ● Alice       │  │  7f99         │
│ ETH           │  │   eb2c 4f87   │  │ ○ Bob         │  │  f59f         │
│               │  │   0365 e785   │  │ ○ You         │  │ hold SIGN 2 s │
│ ▸ next        │  │   … b906      │  │ ▸ next        │  │               │
└───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘
```

- Two 4-character chunks a line, so a full address takes 5 lines.
- It needs its own type sizes (12/18/24 px). At ~114 ppi they're big on the glass.
- A red page is one screen that says what's lost, plus a "you must scroll through" gate.

### 0.96″, 80 × 160: the status strip, never the approval

Too small to show a transaction honestly, so it never shows one to sign. It could be:
- **A second display on the console, facing the other person on the call:** the verify code big,
  "#0 · 1 of 2", and the hold progress.
- **A status light that says more than an LED:** "2 waiting · Local".

```
┌────────────────────┐
│ ● 2 waiting  Local │
│   7f99 f59f        │
└────────────────────┘
```

## What changes in the code

| Piece | Now | Planned |
|---|---|---|
| **Display driver** | `lcd.py`: ST7789 240×240, Waveshare pins | `display.py`: one interface (`W`, `H`, `show()`, `show_band()`) with **ST7789** (240×240, 240×320), **ST7735S** (80×160 with its column offset, 128×160) and **ST7796** (320×480, banded). The panel and pins come from `secrets.py` / a board profile. |
| **Layout** | absolute y positions per 240×240 screen | `layout.py`: blocks with measured heights (`fonts.width` / `wrap`), packed into pages for the screen's height, and a profile per size (margins, type sizes, rows per queue page) |
| **Fonts** | 7 sizes for 240×240 | a type scale per profile. The 3.5″ adds 16/22/32/36 px, and the 1.8″ reuses the small ones. About 5–15 KB each, loaded only for the screen in use. |
| **Input** | A/B/X/Y + joystick | roles already exist (`SIGN`, `REJECT`, `BACK`, `NEXT`, `PREV`). Add a console profile: rotary encoder (turn = page, push = back to summary), guarded Sign (hold), Reject. Labels are drawn beside wherever the physical control sits. |
| **Emulator** | 240×240 ST7789, the Waveshare 3D case | `--screen 320x480` etc. ST7735, ST7789 and ST7796 share the column, row and write commands the emulator already captures. A flat preview for sizes without a 3D model. |
| **Walkthrough** | one size | `tools/quorum shots --screen …` writes `docs/quorum-ui/sizes/<WxH>/`, with the same stories side by side per size |

## Order of work

1. **Before the screens arrive** (emulator only; nothing to wire):
   1. Layout blocks and pagination, and today's 240×240 moved onto them. The screens must come
      out the same or better, and the shots show it.
   2. The emulator at any size. Shots at 240×320, 320×480 (portrait and landscape) and 128×160.
   3. The per-size stories in the walkthrough for you to compare on your phone.
2. **When they arrive:**
   1. **Wiring and first light.** FPC breakout to the Pico 2 W's SPI0 (e.g. GP18 SCK, GP19 MOSI,
      GP17 CS and three GPIOs for DC, RST and backlight), then the drivers, the font check
      screen, and a colour test.
   2. **Measurements.** Heap and redraw time per size.
   3. **Photos in the buildlog,** all six side by side showing the same transaction.
3. **Decide the console screen** (the kickoff's open item). Criteria:
   - comparing a full address at arm's length;
   - QR scan from a phone;
   - power draw on the 18650;
   - whether it fits the case with a guarded Sign button beside it.
4. **Console input.** An encoder and two buttons on the perfboard, and the console profile.

## Questions

1. **Which screen is the console aiming at?** My guess:
   - the **2.8″** for the console, if a two-page flow is fine;
   - the **3.5″**, if one screen per transaction matters more than size;
   - the **1.8″** kept as a pocket variant.
2. **3.5″ portrait or landscape?** Portrait puts Sign and Reject top and bottom, as today.
   Landscape gives two columns with the buttons down the right.
3. **A second Pico 2 W?** The Waveshare board on today's console uses most of the pins these
   screens would need (keys on GP2–3 and GP15–21). Bringing up the new screens on a second Pico
   keeps the dev console and its ATECC608 as they are.
4. **Controls on the new console:** wire the encoder and two buttons now, or keep testing with
   the Waveshare's A/B/X/Y until the case is designed?
5. **The 0.96″ as a second, outward-facing verify display:** worth it, or a distraction?
