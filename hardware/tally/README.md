# Tally: a second take on Mono's idea, with no inductor

*Design, 2026-11-13. Written by a script, [gen_tally.py](gen_tally.py), with KiCad 7.0.11: KiCad
reads the schematic back (netlist) and runs its DRC on the routed board, and both come out clean.
The repo's own checks (`tools/keypcb check` and `jlc`) want KiCad 10 and were **not run**: see
[What is checked, and how](#what-is-checked-and-how). Not ordered, nothing built, no panel folded
against it, and no firmware profile for it yet. Tally is a working name.*

![Tally's front copper: the screen's connector at the top, three buttons under it, the key, the RP2350 with the flash beside it, the core's regulator, the serial bridge and the USB-C at the bottom](renders/tally-front.png)

*The board file's front copper, drawn by a plotting script (KiCad 7 has no 3D render). Blue is
signal, red 3.3 V, orange 1.1 V, purple 5 V, grey ground. Pale lines are on the back.
[The back](renders/tally-back.png) is in the same folder.*

Tally is an independent design of the same console as [Mono](../mono/README.md): a 40 × 89.5 mm
bar with no radio, the key soldered on, a small screen for clear signing and three buttons. It
starts from Mono's outline and pins and makes its own choices where Mono's parts are hard to buy or
its first relative, console-rp, misbehaved.

```
   computer (the relay) ── USB-C ── CH343P ── UART1 ── RP2350A ── I2C0 ── ATECC608C (the key that signs)
   no key, no say in                                  │
   what gets signed                                   └─ SPI1 ── 1.14" panel;  D0 D1 D2
   firmware goes in over SWD only: J3 on the front, pads on the back
```

The computer can't reach the RP2350's REPL, reset it or hold BOOTSEL: the CH343P's modem pins go
nowhere, and the RP2350's own USB pins go nowhere either. The generator checks both
([The link](#the-link)).

## What is different from Mono, and why

| | Mono | Tally | why |
|---|---|---|---|
| the core's 1.1 V | the RP2350's switching regulator: Abracon inductor, 33 Ω, three capacitors | a fixed 1.1 V LDO, **TLV74311PDBVR**, from 3.3 V; one capacitor at the chip's regulator pins | the inductor is the hardest part to buy (JLCPCB 756, LCSC 0, one maker, polarity matters). console-rp's board 1 read 1.4 V on DVDD where 1.1 V is expected, and nobody knows why. An LDO has nothing to lay out wrong. It costs about 0.14 W more from USB at 45 mA of core current |
| the crystal | Abracon ABM8-272-T3, the one Raspberry Pi names | YXC **X322512MSB4SI** (C9002) on Raspberry Pi's 15 pF and 1 kΩ | JLCPCB has 1 of the Abracon, LCSC 0. The YXC is a Basic part with 494,234 in stock. Not Raspberry Pi's tested part: see [Open](#open) |
| the chip's own USB, BOOT | on pads, through 27 Ω and 1 kΩ | **not connected** | console-rp's own USB never enumerated; SWD is how its board 1 was loaded. Three parts and three pads fewer, and one less way in. It has a cost: see [Open](#open) |
| the debug way in | pads for a pogo jig | the same pads at Mono's places, and **J3**, Raspberry Pi's 3-pin JST-SH debug socket | a Debug Probe's cable plugs in. No jig is needed for the first boards |
| the second key's site | KEY 2: a footprint, a switched supply, a header | none | not needed for a first product |
| the USB-C | left of centre | centred | the bridge and the ESD diodes sit in line above it. Mono's case needs its opening moved |
| the backlight's driver | an NPN and a base resistor | an N-FET, AO3400A | one part fewer |
| parts | 67 | 67 on the drawing, **50 fitted** of 24 kinds (Mono's count includes its unfitted sites) | |

Kept: the outline, the four M2 holes, the glass and the three buttons where Mono has them; the
RP2350A with Raspberry Pi's copper round it (`rpi_minimal.json`, MIT,
[lib/RPI-MINIMAL-LICENSE.txt](lib/RPI-MINIMAL-LICENSE.txt)); the CH343P link; the ATECC608C in
SOIC-8; the ZIF and the panel; the LDL1117S33R; the backlight fed from 5 V; and **every GPIO**
([PINS.md](PINS.md)), so one board profile can serve console-rp, Mono and Tally.

**An ESP32 instead?** No. Every ESP32 that JLCPCB can solder has a radio on the chip except the
ESP32-P4, which needs Standard assembly, costs $5.41, and had 111 in stock. The RP2350A has no radio
on the chip, costs $1.23, and the firmware already runs on it.

## The core's supply

The RP2350 datasheet (section 6.3.7, figure 24) allows it: "If the digital core supply (DVDD) is
powered from an external 1.1 V supply, the on-chip regulator can be disabled and the application
circuit simplified. Power must still be provided on the regulator's analogue supply (VREG_AVDD)
and input supply (VREG_VIN) ... But the inductor can be omitted and only a single input capacitor
is required. Connect VREG_FB directly to ground."

So on Tally:
- VREG_VIN (pin 49) and VREG_AVDD (pin 46) are on 3.3 V with C20, 4.7 µF.
- VREG_FB (pin 50) and VREG_PGND (pin 47) are on ground. VREG_LX (pin 48) is open.
- U4 feeds the three DVDD pins: 4.7 µF at its output, 100 nF at pins 6 and 39, 4.7 µF at pin 23.
- TP10 on the back is DVDD, to put a meter on.

**The firmware has two duties** it does not have on Mono:
1. Write 1 to `VREG.HIZ` early. The datasheet: "The on-chip regulator will still power on ... This
   is a safe mode of operation, though the regulator will consume approximately 400 µA until it's
   shut down."
2. Never put the regulator in low-power mode (the P1.x power states): "Don't put the regulator into
   low-power mode if DVDD is being powered from an external supply."

The TLV74311P is ±1.4 % over temperature by its datasheet, so 1.085 to 1.115 V, inside the chip's
1.05 to 1.16 V. It gives 300 mA. Its heat is (3.3 − 1.1) V × the core's current: about 0.1 W at
45 mA. How it holds up under the core's load steps was not measured or simulated.

## The link

The same as Mono's. The USB-C's D+ and D− go through the USBLC6-2SC6 to the CH343P and stop. The
CH343P's TXD and RXD go to GPIO21 and GPIO20 (UART1) and to two pads on the back, to watch the
link. `gen_tally.py` holds each of these nets to an exact list of parts and stops if:
- D+ or D− reaches anything but J1, U2 and U5;
- any of the CH343P's DTR, RTS, ACT, DCD, DSR, CTS or RI pins is connected at all;
- the RP2350's USB_DP or USB_DM is connected at all;
- the USB-C and the RP2350 share any net but power;
- SWCLK, SWDIO or RUN reaches anything but the chip, J3 and its pad.

## The front, top to bottom

- **The panel**, a 1.14-inch 240 × 135 ST7789 (ER-TFT1.14-2) on tape, where Mono has it. Its ribbon
  folds under into J2. Only J2 and two capacitors are under the glass. Four silkscreen corners
  show where the glass goes.
- **D0, D1, D2**, 10 mm apart, 24 mm from the top, as Mono.
- **The backlight's switch** on the left: Q2 (GPIO13, 4.7 kΩ to ground) pulls Q1's gate; Q1 feeds
  the LED from 5 V through 150 Ω, about 13 mA. High is on.
- **The key**, U6, under D1, with its pull-ups and capacitor.
- **The RP2350A**, turned a quarter turn, and **the flash** beside it.
- **U4**, the 1.1 V regulator, under the chip, and the red LED (GPIO25).
- **J3**, the debug socket, on the left edge.
- **The bridge, the ESD diodes and the USB-C** in line at the bottom; the 3.3 V regulator beside them.

Nothing is fitted on the back. It has the pads and the text.

## The pads on the back

| pad | net | |
|---|---|---|
| TP1, TP2, TP3 | SWCLK, GND, SWDIO | at Mono's places, 2.54 mm apart |
| TP4 | RUN | low resets the chip |
| TP5, TP9 | 3V3, GND | to measure |
| TP10 | 1V1 | the core's supply |
| TP11 | VBUS | |
| TP12, TP13 | TX, RX | the link, to watch with a logic probe |

Mono's BOOT, D+ and D− pads have no twin here.

## Parts at JLCPCB

Read from JLCPCB's and LCSC's listings on 2026-11-13. Stock and prices move daily.

| | part | LCSC | tier | JLCPCB stock | each |
|---|---|---|---|---|---|
| U1 | RP2350A | C42411118 | Extended | 5,813 | $1.29 |
| U7 | W25Q128JVSIQ, 16 MB | C97521 | Basic | 70,193 | $2.26 |
| U6 | ATECC608C-SSHDA-T | C28975195 | Extended | 3,664 | $1.75 |
| U5 | CH343P | C2846043 | Extended | 18,478 | $1.00 |
| U3 | LDL1117S33R | C435835 | Extended | 53,806 | $0.49 |
| U4 | TLV74311PDBVR | C485147 | Extended | 10,900 | $0.07 |
| U2 | USBLC6-2SC6 (ST) | C7519 | Extended | 43,645 | $0.16 |
| J1 | TYPE-C-31-M-12 | C165948 | Extended | 539,075 | $0.19 |
| J2 | 0.5K-HX-8PWB | C2919492 | Extended | 13,441 | $0.10 |
| J3 | SM03B-SRSS-TB | C160403 | Extended | 26,795 | $0.19 |
| Y1 | X322512MSB4SI, 12 MHz | C9002 | Basic | 494,234 | $0.10 |
| Q1, Q2 | AO3401A, AO3400A | C15127, C20917 | Basic | over 1,000,000 each | $0.08 |
| SW1 to SW3 | TS-1187A-B-A-B | C318884 | Basic | 826,275 | $0.02 |
| the rest | 24 capacitors, 9 resistors, 1 LED, all 0402 but three | | Basic | | $0.15 together |

- **About $8.00 of parts a board**, at JLCPCB's price for one.
- **Nine Extended kinds.** On Economic assembly that is 9 × $3.07, with $8.18 setup, $1.53 stencil
  and $0.45: about $38 an order before boards, parts and joints.
- **Two fees could go.** J3 can be left off the BOM (the pads on the back do the same job with a
  jig). JLCPCB lists an SRV05-4 (C7420376) as a Preferred part with no fee, in the USBLC6's package;
  its maker is not ST and its pinout was not checked here, so Tally keeps the ST part.
- **With the flash inside the chip.** `BUILD = "RP2354A"` in the generator fits an RP2354A
  (C41378174, 1,418 in stock, $1.24 at ten) and leaves U7 and its capacitor off: about $2.30 less a board.
  It has 2 MB, so it needs a MicroPython build told so; the stock Pico 2 image assumes 4 MB. The
  default stays the RP2350A with the 16 MB flash, which is what console-rp's board 1 ran.
- The panel is not JLCPCB's: 100 ER-TFT1.14-2 were bought at $3.71.
- JLCPCB's part rotations can differ from KiCad's. No offsets are applied in `cpl.csv`. Look at each
  part in their placement preview before paying, the ICs and the USB-C first.

## Routing

Two layers, 0.15 mm least track and gap, 0.6 mm vias with 0.3 mm holes. Every track is drawn by
the script, by coordinates: nothing was autorouted.
- **Round the chip** the copper is Raspberry Pi's, turned with it: the 3.3 V and 1.1 V rings under
  the chip, each supply pin's track to its capacitor, the crystal's corner. Their switching
  regulator's corner is left out.
- **The back is ground**, with these tracks on it: the 1.1 V tracks under the chip (Raspberry Pi's);
  D0, 18 mm from the chip to the left button; the key's 3.3 V, 8 mm; the screen's DC, 5 mm under the
  glass; 5 V across the bridge; D− for 4 mm under the USB-C; and stubs to five pads. Three of them
  exist because GPIO2, 3 and 6 leave the chip in the opposite order to D0, D1, D2, and Tally keeps
  Mono's pins rather than untangle them.
- **93 ground vias** join the two pours on a 4 mm grid.
- **5 V runs up the left edge** to the backlight's switch, about 55 mm of 0.25 mm track at 13 mA. It
  passes under R11 between its pads.
- The screen's six lines run 25 mm side by side. SCK has 0.5 mm to its neighbours.

## What is checked, and how

Run here, with KiCad 7.0.11 on Linux, on 2026-11-13:
- `python3 gen_tally.py`: writes everything, then checks it. `python3 gen_tally.py check` checks
  the files as they are.
- **The table against itself:** every symbol pin has a pad on its footprint; each GPIO can do the
  job it is given (SPI1, I2C0, UART1); the screen's and key's pins are `firmware/board.py`'s Pico
  defaults; the link's rules above.
- **KiCad's netlist of the schematic against the table:** every net has exactly the pins the table
  lists, every part its value, footprint and LCSC number.
- **The board against the netlist:** every pad on its net, every part at its place and side.
- **KiCad's DRC on the routed board**, with the project's rules: 0 violations, 0 unconnected.
- **fab/:** the BOM is the table's; each CPL row is its part's place, side and rotation.

Not run, and why:
- **`tools/keypcb check tally` and `tools/keypcb jlc tally`** (KiCad 10's ERC, DRC with schematic
  parity, JLCPCB's limits, the Gerbers read back, the 3D fit). They need KiCad 10. This session
  could not install it: adding KiCad's package source and running its Docker image were both
  refused by the session's permissions. `tools/keypcb` knows the board, and `gen_tally.py` has a
  `jlc_spec()` for it, written by Mono's keys and never executed.
- **KiCad's ERC.** KiCad 7's command line has none.
- **`gen_tally.py` under KiCad 10's Python.** It was written and run on KiCad 7's. Two calls that
  changed names are handled; others may not be.
- **A 3D render or the case.** `cad/consoles/mono.py` was not run against Tally.
- **Anything electrical.** No simulation, no board.

A review by other agents, each finding checked by a second one, is summarised in
[REVIEW.md](REVIEW.md).

## Steps to a board

1. On a machine with KiCad 10: `tools/keypcb check tally`, then `tools/keypcb fab tally` and
   `tools/keypcb jlc tally`. Fix what they find. `tools/keypcb fab` rewrites `tally/fab/`.
2. Measure a real panel's ribbon in a real J2 (Mono's README, "The panel"). Tally's J2 is where
   Mono's is, 19.5 mm in from the glass's ribbon end. By the connector's drawing the ribbon may want
   it about 1.2 mm further in; console-rp's sits further out and works with a loop.
3. Decide the two things under [Open](#open).
4. Order five on Economic assembly: 2 layers, 1.6 mm, lead-free HASL. Let JLCPCB add its tooling
   holes; there is bare ground pour to put them in.
5. Bring-up, in this order: 5 V and 3.3 V with nothing else; **1.1 V on TP10 before anything
   else**; SWD on J3 with a Debug Probe; then console-rp's bench scripts.

## Open

- **The chip's own USB is not brought out.** `picotool`'s OTP commands work only over that USB, so
  turning on secure boot later would need a program loaded over SWD instead. And once SWD is closed
  in OTP, a board with no USB and no BOOT pad cannot be loaded again at all. If secure boot is on
  the road, put Mono's three pads back: two 27 Ω resistors, 1 kΩ, three pads, and three thin tracks
  past C19. Ask and it is a small change.
- **The crystal is not Raspberry Pi's.** They ask for the ABM8-272-T3 by name and say other
  crystals may need other values. The YXC part wants 20 pF where the Abracon wants 10 pF, so on
  15 pF capacitors it will run a little fast (tens of ppm by arithmetic; USB is not on this clock's
  budget here, the UART link tolerates percent). Start-up at cold was not tested. The footprint is
  the same 3.2 × 2.5 mm, so the Abracon can be fitted instead when there is stock.
- **The firmware.** No profile exists for this board or for Mono: the pins, the UART link, the
  240 × 135 screen at MADCTL 0x60, and for Tally the two regulator duties above. That is a firmware
  change and so a new release fingerprint.
- **Inrush.** 5.7 µF on VBUS, under USB's 10 µF. What charges through the regulators at plug-in
  (about 18 µF on 3.3 V and 10 µF on 1.1 V) was not measured. Mono's README estimates the same
  case at a little over USB-IF's 50 µC.
- **No fuse and no TVS on VBUS** beyond the USBLC6's clamp, as Mono.
- **The 3.3 V regulator's tab** is its output and has no large pour. At 0.15 A it makes 0.26 W.
- **The name.**
