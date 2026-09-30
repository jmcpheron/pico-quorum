# Hardware handoff: Build 1

*2026-09-26, updated 2026-09-27.* This file is for the next person or AI session to pick up from: what's on the bench,
how it's wired, what to do next and what's still open.

It links to the wiring rather than repeating it:

- [wiring/BREADBOARD.md](wiring/BREADBOARD.md): **where the bench is now.** The chip, the screen and
  the knob on a breadboard with jumper wires, the chip wired straight to 3.3 V, no jacks. It has 19
  numbered wires, a picture of the knob's legs, and troubleshooting
- [wiring/BUILD1.md](wiring/BUILD1.md): the pin map, the detect and power logic, and the key
- [wiring/build1-wiring.svg](wiring/build1-wiring.svg): the diagram

## 1. Goal

The key is a printed handle holding a 3.5 mm and a 2.5 mm TRRS plug, rigidly joined, with the
signing chip inside. The console has the screen, the knob, the Sign and Reject buttons, and the two
jacks. It can't sign without a key plugged in, and a key on its own is inert.

Build 1 is the first console with the real parts:

- a 2.0″ 240×320 screen
- a knob
- the two jacks
- an ATECC608 breakout wired to two plugs as a stand-in key

It runs on USB, and it only reads the chip.

## 2. Parts

**On the bench**

| part | unblocks |
|---|---|
| Pico 2 W | everything |
| 2.0″ ST7789 240×320 SPI screen, 8-pin | step 2 (screen), firmware 1 |
| EC11 rotary encoder with push, one | step 3 (knob), firmware 2 |
| 3.5 mm and 2.5 mm TRRS jacks and plugs | steps 4–8 (jacks and key) |
| ATECC608 STEMMA QT breakouts, a pack, unconfigured; STEMMA QT cables | step 1 (today) and step 6. One is the sacrificial chip for firmware 4 |
| 18650 cell and clips | nothing yet: waits for the protected TP4056 |

**Arriving:** 5–10 Adafruit OPTIGA Trust M STEMMA boards, expected Tuesday 2026-09-29. They unblock
firmware 5 and a Trust M key (its RST pad goes to P2 ring 1).

**Not bought, needed for the full v2**

| part | unblocks |
|---|---|
| TP4056 module **with** DW01 protection, 1N5817, SPST slide switch | the battery build ([SOLDERING.md](wiring/SOLDERING.md#2-battery-switch-diode)) |
| resistors: 100k ×2 | the battery gauge on GP28 |
| resistors: 10k | console-side I2C pull-ups once a key is a bare chip without a breakout |
| resistors: 1k, and a 2N3906 or S8550 PNP | a key power switch, if GP6 alone can't carry signing (open decision) |
| resistors: 33k, 10k | ID resistor codes on GP27, if the ID line gets used |
| resistors: 100 Ω | series on SDA and SCL at J1, to limit current while a plug wipes across the contacts |
| caps: 100 nF | key decoupling, the battery gauge |
| tact switches | Sign (A, GP15) and Reject (Y, GP21), then B and X |

## 3. Wiring summary

The full tables with notes are in [BUILD1.md](wiring/BUILD1.md#pin-map). This is the same table
on one screen. `tools/wiring-build1 --check` confirms it still matches.

<!-- pins: summary -->
| part, contact | signal | GPIO | Pico pin |
|---|---|---|---|
| screen 3V3 | 3.3 V | 3V3 | 36 |
| screen GND | ground | GND | 13 |
| screen MOSI | SPI1 MOSI | GP11 | 15 |
| screen SCL | SPI1 SCK | GP10 | 14 |
| screen CS | chip select | GP9 | 12 |
| screen DC | data/command | GP8 | 11 |
| screen RST | reset | GP12 | 16 |
| screen BL | backlight PWM | GP13 | 17 |
| knob A | encoder A | GP2 | 4 |
| knob B | encoder B | GP3 | 5 |
| knob C | encoder common | GND | 3 |
| knob SW1 | push | GP1 | 2 |
| knob SW2 | push, other side | GND | 3 |
| J1 T | SDA | GP4 | 6 |
| J1 R1 | SCL | GP5 | 7 |
| J1 R2 | DETECT | GP7 | 10 |
| J1 S | ground | GND | 8 |
| J2 T | KEY VCC | GP6 | 9 |
| J2 R1 | KEY RST | GP26 | 31 |
| J2 R2 | KEY ID | GP27 | 32 |
| J2 S | ground | GND | 8 |

J1 is the 3.5 mm jack and J2 is the 2.5 mm jack. The key's RST and ID lines are already wired to
J2, even though nothing uses them yet.

These pins are reserved and nothing else goes on them:

- GP15, GP17, GP19 and GP21 (pins 20, 22, 25 and 27): the A, B, X and Y buttons
- GP28 (pin 34): battery sense

Free pins: GP0, GP14, GP16, GP18, GP20 and GP22.

Never use GP23, GP24, GP25 or GP29 in firmware. They belong to the radio.

## 4. Build order

Each step has a pass test. `bench1` means `firmware/bench1.py`; see
[BREADBOARD.md](wiring/BREADBOARD.md#try-it) for how to run it.

**Now: the breadboard, no jacks** ([BREADBOARD.md](wiring/BREADBOARD.md), `JACKS = False` in `bench1.py`).

- [ ] **1. ATECC608 alone.** Wires 1–6: the power rails and the chip.
      *Passes when* `import bench1` prints `key bus scan: ['0x60']`, a serial number, and
      `config open, data open`.
- [ ] **2. Screen.** Wires 7–14.
      *Passes when* `bench1` shows the TL mark top left, the bars read red, green, blue and white in
      that order, and the text isn't mirrored. If not, fix it with `MADCTL` and `INVERT`.
- [ ] **3. Knob.** Wires 15–19.
      *Passes when* one click moves the count by exactly 1, clockwise goes up, PUSH shows DOWN while
      the knob is pressed, and a 2 s hold prints the chip report.

**Later: the jacks and the key** ([BUILD1.md](wiring/BUILD1.md), `JACKS = True`). The chip comes off
the red rail and into the key.

- [ ] **4. Mark the jack lugs.** Put the matching plug in each jack. Beep each plug contact (tip,
      ring 1, ring 2, sleeve) to the lugs, and label them. Note any switch lugs; Build 1 doesn't use
      them.
      *Passes when* every lug of both jacks has a label.
- [ ] **5. Jacks to the console.** Before power, check continuity from each lug to its Pico pin, and
      check that J2's tip (GP6) doesn't beep to ground. Then put a test plug in J1 with ring 2
      shorted to its sleeve.
      *Passes when* DETECT shows "key in" and POWER shows "ON" then drops to "off" with "not a key",
      since that plug has no chip.
- [ ] **6. Solder the key.** Solder the breakout to P1 and P2 as in
      [BUILD1.md](wiring/BUILD1.md#the-key-build-1), then run the meter checks listed there.
      *Passes when* every check in that list beeps as it should.
- [ ] **7. Key scan.** Plug the key in.
      *Passes when* the screen shows DETECT "key in", POWER "ON GP6", and BUS "60". Unplugging it shows
      "key out: power cut".
- [ ] **8. Chip status.**
      *Passes when* the CHIP line shows 608A or 608B, the serial matches step 1's, and the locks
      read `config open, data open`. Nothing has been written.

## 5. Rules that prevent damage

- **The screen runs on 3.3 V** from pin 36. Never connect it to VBUS or 5 V.
- **GP6 is low before a key goes in or comes out.** Every plug tip wipes past every jack contact,
  so a live J2 tip shorts to ground on the way in. The firmware handles this: DETECT has to settle
  before power comes on, and power drops as soon as DETECT lifts. Any firmware that drives GP6 has
  to keep that behavior.
- **Never plug a key into a phone, laptop or audio jack.** Those drive the tip and put mic bias on
  a ring.
- **No 18650 without a protected TP4056** (the DW01 kind). Build 1 runs on USB.
- **Config lock and data lock are permanent.** Build 1 only reads. `ALLOW_LOCK` and `ALLOW_GENKEY`
  stay `False` in `secrets.py` until the slot plan is decided, and even then only on one chip marked
  as sacrificial.

## 6. Firmware to do, in order

1. **`lcd.py`: a size option.** Add width, height, offset and MADCTL so `LCD()` can drive the
   240×320 panel in landscape. `bench1.py`'s `Screen` class is the working reference. The
   framebuffer grows from 115 KB to 150 KB; that's fine on the RP2350 but check the emulator's heap.
   `quorum_ui.py` then has to reflow; [SCREENS.md](../docs/quorum-ui/SCREENS.md) has the plan.
2. **Encoder input.** Add a `firmware/knob.py` with the same `pressed()` and `held()` shape as
   `lcd.Keys`, so `wallet.py` and `quorum_ui.py` don't change: a turn reads as up or down, a press
   reads as press, and a 2 s hold is its own event. The quadrature table and IRQs are in `bench1.py`.
3. **Key presence and power in `wallet.py`.** DETECT, then GP6 on, then scan, then the ATECC. Key
   out means power off and the bus released, and the wallet shows "insert key" instead of failing
   on a missing chip. `bench1.tick()` has the logic.
4. **ATECC config and lock on the Pico**, with `atecc.py`'s `write_config`, `lock_config` and
   `genkey_new`, from the chip page behind the hold-A red screens that already exist. Run it on the
   sacrificial chip first, and only after the slot plan is decided (see
   [CHIPMAP.md](../docs/CHIPMAP.md) and [LOCKING.md](../docs/LOCKING.md)).
5. **`trustm.py` when the boards arrive.** Done on 2026-09-28, on the Build 1 bench. The console, the
   dual image and the ceremony image detect a Trust M (`signer.detect`). The quorum-tm1 ceremony
   ran T1–T6 on the first chip; the seal (T7) is not done yet. See [docs/TRUSTM.md](../docs/TRUSTM.md).
   Still to do: `bench1.probe()` stops at 0x30, and the Trust M's current draw on GP6.
6. **Emulator.** Add a 320×240 screen, a knob, and a virtual key jack (DETECT plus GP6) to
   `emu/core/shims/machine.py` and the page, so steps 1–3 can be rehearsed without the board.

## 7. Open decisions

- [ ] **Trust M or ATECC608 for the production key.** Trust M has attempt throttling; the ATECC608
      needs a counter-based limit. See [KICKOFF](../docs/KICKOFF.md#secure-element).
- [ ] **The slot plan**, before locking any ATECC: which slot signs, what's lockable, and whether
      there's a CheckMac or PIN gate. The config lock freezes all of it.
- [ ] **The connector.** The kickoff drafts ¼″ plus 3.5 mm TRS; Build 1 uses 3.5 mm plus 2.5 mm
      TRRS. Measure the jack spacing on the bench for the key body and the case.
- [ ] **The 18650 holder or clips** that go in the case.
- [ ] **Key power**: GP6 directly, or a PNP high-side switch. Measure whether an ATECC Sign or a
      Trust M holds up on GP6.
- [ ] **KEY ID on GP27**: resistor codes per key type, or leave it unused.
- [ ] **Secure boot on the RP2350.** Try it on a spare board only, and later. Enabling it burns OTP.

## 8. Pin change log

Earlier notes from the planning chat had different pins. The tables here replace them:

| signal | old | now |
|---|---|---|
| key VCC | GP14 | GP6 |
| key RST | GP6 | GP26 |
| knob push | GP16 | GP1 |

Compared with the Waveshare dev console, the joystick is gone:

- GP2 and GP3 are now knob A and B.
- GP16, GP18 and GP20 are free.
- A, B, X and Y keep GP15, GP17, GP19 and GP21.
- The screen keeps its SPI pins.

## 9. Where the notes are

- [wiring/BREADBOARD.md](wiring/BREADBOARD.md), [build1-breadboard.svg](wiring/build1-breadboard.svg),
  [knob-ec11.svg](wiring/knob-ec11.svg), and `tools/wiring-breadboard`, which draws them
- [wiring/BUILD1.md](wiring/BUILD1.md), [wiring/build1-wiring.svg](wiring/build1-wiring.svg), and
  `tools/wiring-build1`, which redraws the diagram; `--check` compares the tables
- `firmware/bench1.py`: the bench test
- [wiring/SOLDERING.md](wiring/SOLDERING.md): mapping STEMMA wires by pad, the battery, and exploring a
  fresh chip without changing it
- [app/SOLDERING.md](../app/SOLDERING.md): the upstream soldering notes, including the ATECC wake
  pulse
- [docs/KICKOFF.md](../docs/KICKOFF.md): the design, the connector draft, controls and open decisions
- [docs/LOCKING.md](../docs/LOCKING.md), [docs/CHIPMAP.md](../docs/CHIPMAP.md),
  [docs/TESTPLAN.md](../docs/TESTPLAN.md): the chip's locks and slot table
- [reference/pi/README.md](../reference/pi/README.md): the Pi signer, including how it provisions and
  locks
- [docs/quorum-ui/SCREENS.md](../docs/quorum-ui/SCREENS.md): how the UI reflows on each screen size
