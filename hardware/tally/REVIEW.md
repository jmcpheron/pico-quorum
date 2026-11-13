# Tally: the review of 2026-11-13

Ten agents read the design the day it was drawn. Five reviewed one area each: the RP2350 and what
it needs, pin by pin against its datasheet; the USB, power, bridge, key, screen and buttons against
theirs; the layout, measured from the board file; the fab files, read back from the zip; and the
board against the rest of this repository. Then five more each took one reviewer's findings and
tried to refute them, measuring again.

This is a review by language models with the datasheets' text, KiCad 7 and the files. Nobody
held a board. It is not an audit.

- **42 findings, 42 reproduced, none refuted.** By the second reader's rating: 2 major, 18 minor,
  22 notes. No blocker: every pin of every part was found on the right net.
- Both majors were about assembly, not the circuit: two chips had no pin-1 mark, and the placement
  file would have laid the bridge a quarter turn off, where it still fits its pads.
- What was changed is below. What was not is in the README's [Open](README.md#open), or here.

## Checked and found right

- All 61 pins of the RP2350A against the datasheet's figure 2 and pin tables; the outside 1.1 V
  supply against figure 24, pin by pin; decoupling at Raspberry Pi's places.
- The flash, pin by pin. The crystal's wiring and land pattern.
- The USB-C against HRO's drawing; one 5.1 kΩ on each CC. The USBLC6 in line. All 17 pins of the
  CH343P against WCH's table, and its supply scheme (5 V in, 3.3 V I/O from an outside regulator).
- TXD to GPIO21 (UART1 RX) and RXD from GPIO20 (UART1 TX). The two regulators' pinouts.
- The backlight's two FETs, its state at reset, and its current. The ZIF's pin order against the
  panel's drawing. The key's pins. The switches' pad pairs. The LED. J3's pin order.
- By geometry alone, nets ignored: 0 shorts and 0 opens; the bridge's modem pads, the chip's USB
  pads, VREG_LX and every unused pin touch no copper. From the USB-C there is no path to RUN, SWD,
  the flash's chip select, a button or the key's bus.
- The Gerbers and drill files read back twice, once by an unmodified copy of this repository's
  `tools/jlc/gerb_check.py`: 11 files, the outline, every hole, every pad on its net, copper
  0.3 mm or more from the edge. `tools/jlc/netlist_check.py`, unmodified, on the BOM,
  CPL and an IPC-D-356 netlist. `tools/jlc/pcb_checks.py` does not run on KiCad 7.
- A fresh run of `gen_tally.py` gives the committed files byte for byte.

## Changed because of it

| | finding | what was done |
|---|---|---|
| major | U5 (the bridge) and U7 (the flash) had no pin-1 mark on the silkscreen | KiCad 10's filled triangles are kept on both footprints |
| major | `cpl.csv` carried KiCad's rotations. Against JLCPCB's own footprints, eight parts would be turned, and U5 a quarter turn where a QFN-16 still fits its pads | see [The placement file](#the-placement-file) |
| minor | J1's placement point was 1.4 mm from where JLCPCB's footprint has its origin | the same section |
| minor | The bridge's VDD5 sat on VBUS behind 5.7 µF. WCH asks for a 5.5 V protector or 10 µF there; its limit is 6.0 V and the ESD part clamps only above that | C1 is 10 µF in 0805, so 11 µF with C5, as console-rp has. Not measured: see Open |
| minor | LINK_TX had no level while the chip is in reset, blank or booting: the chip's pull-down fights the bridge's pull-up | R13, 4.7 kΩ to 3.3 V |
| minor | D−'s via under the USB-C ended 0.02 mm from where the metal shell begins | moved 0.35 mm toward the pads |
| note | No series resistor in SWCLK or SWDIO; Raspberry Pi's debug connector specification asks for 100 Ω at the target | R14 and R15, 100 Ω. The buttons are left bare |
| minor | Four capacitors' ground pads were 4 to 15 mm of pour from a via; the key's was the worst | a via beside each, and a second at the key's ground pin |
| minor | The LED was under where Mono's case has its mark | D1 and R12 moved to 66.5 mm from the top, 10.5 mm from that mark |
| note | Three test pads had their via at the centre, where a pogo pin lands; VBUS's pad was 0.57 mm from the USB-C's grounded leg | each via is now 1 mm or more off its pad's centre; TP11 moved 1 mm |
| note | The 5 V track into U5 pin 3 was 0.05 mm off the pad's centre | drawn on the centre |
| minor | The check of the screen's and key's pins against `firmware/board.py` never ran: it looked for a name that file does not have | it reads the two real lines now, and fails if they are gone |
| minor | A symbol pin with no pad on its footprint passed | checked both ways |
| minor | The link's rules missed TXD and RXD swapped, and had none for the buttons, the flash, CC or the bridge's supply pins | every bridge pin is held by its name; exact part lists for 23 nets |
| minor | `check` trusted the Gerber zip, the project file and PINS.md as found | each is written again and compared |
| minor | `bom.csv` and `cpl.csv` were in another row order than `tools/keypcb fab` writes, so each tool failed the other's files | written in its order; compared as sets of rows |
| minor | Two KiCad calls that changed names since KiCad 7 had no fallback | five are handled now. Still not run on KiCad 10 |
| minor | Wrong or stale words in the script and README | corrected |

After the changes six broken copies were tried (TXD and RXD swapped; DC and CS swapped; PINS.md
edited; every DRC severity set to ignore; the zip replaced; a pad cut from a footprint).
`gen_tally.py` stops on each.

## The placement file

JLCPCB lays its own footprint for each part on the CPL's point, turned by the CPL's angle. Its
footprint can have pin 1 somewhere else than KiCad's. The second reader fetched JLCPCB's footprint
for each of the fifteen polarised parts (the JLCEDA/EasyEDA library, easyeda.com) and found the turn
that lays its pads on KiCad's.

| part | JLCPCB's footprint: its package name, and where pin 1 is | KiCad's angle on the board | the CPL reads | would a wrong turn show on the pads? |
|---|---|---|---|---|
| U5 CH343P | `TQFN-16...-BL`: bottom row, left end | 0 | **270** | **no** |
| U2 USBLC6-2SC6, U4 TLV74311P | `SOT-23-6...-BL`, `SOT-23-5...-BL` | 90 | 0 | yes |
| U6 ATECC608C, U7 W25Q128 | `SOP-8...-BL`, `SOIC-8...-BL` | 90 | 0 | a quarter turn, yes |
| U3 LDL1117 | `SOT-223-4...-BR`: right column, bottom | 0 | 180 | yes |
| Q1, Q2 | `SOT-23...-BR` | 180 | 0 | yes |
| U1 RP2350A | `QFN-60...-TL`: as KiCad's | 270 | 270 | no |
| Y1, J3, the switches, J2 | as KiCad's (J2's pads are numbered from the other end; the shape is the same) | | as KiCad's | |
| D1 | JLCPCB's pad 2 is the cathode, on the side KiCad's pad 1 is | 180 | 180 | no |
| J1 | the same way up; its origin 1.394 mm nearer the pads, by its two pegs | 0 | 0, moved | yes |

As first written, U5's VIO would have been laid on LINK_TX and its VDD5 on D+.

How far to trust it:
- The same table came out three times: from the second reader, and from two scripts written
  afterwards without its code, one matching pads by number and one by shape alone.
- The method gives −90° for the USBLC6, which this repository had already recorded from the same
  library (`hardware/archive/console-pcb/gen_console.py`), and it gives the quarter turn that
  key-c's order showed in JLCPCB's preview for a SOIC-8 and a SOT-23-6.
- It rests on JLCPCB's machine following its library's drawing. That was seen on two parts of one
  order. console-rp had this CH343P at KiCad's angle with no offset, and its link works, so somebody
  turned it; the record does not say who.
- So: the offsets are in `cpl.csv`, the two chips have their marks back, and the preview is still
  the check.

## Left as it is, and why

| | finding | |
|---|---|---|
| minor | The crystal is a 20 pF, 80 Ω part where Raspberry Pi's network was tuned for 10 pF and 50 Ω: 50 to 100 ppm fast, and 1.6 times less start-up margin on paper. The chip's oscillator gain is not published, so the margin is unknown, not known bad | Open. Test before more than five boards, or fit a 10 pF part |
| minor | "One profile serves all three" clashed with telling the firmware to switch the chip's regulator off: on Mono or console-rp that write resets the chip | the README no longer asks for the write in a shared image |
| note | Nothing holds the chip in reset until 3.3 V is in range. A VBUS gap of about 0.5 to 1.2 ms can leave the core running with the flash below its range: a hang that a replug cures | Open. A bring-up test; no part added |
| note | Plug-in charge was about 100 µC by the capacitors' printed values, against USB-IF's 50 µC mark; with C1 at 10 µF it is about 125 | Open |
| note | The RP2350's low-power default is the mode the datasheet forbids with an outside supply, and HIZ does not survive a reset | README, "The core's supply" |
| note | VBUS draw about 80 mA typical, 150 mA at peaks; nothing drops in USB suspend; the bridge's declared current was not read | read `bMaxPower` on the first board |
| note | J1 sits 0.4 mm further in than HRO's drawing, its mouth level with the edge | as Mono and console-rp, whose cable seats |
| note | J1's front slots are 1.2 mm long where HRO's drawing asks 1.4 | KiCad's footprint; console-rp's is the same and was fitted |
| note | The via in U5's pad can take most of that pad's solder paste | pin 2 has its own joint |
| note | U1's pins get full-size paste, as Raspberry Pi's own board and console-rp | consider ENIG for the 0.4 mm QFN |
| note | Footprint silkscreen lines are 0.12 mm, under JLCPCB's stated 0.15 | as the sibling boards, which were printed |
| note | J3 is 1.6 mm from the left edge, so JLCPCB will add rails; and it decides where its tooling holes go | pay for "Confirm Production file" to see them |
| note | Four of the screen's lines run under the ZIF's housing | as console-rp, whose screen works |
| note | D0's back-side track cuts the ground under the screen's lines; three of the flash's lines are 17 to 26 mm long | if the screen shows noise, lower the SPI clock first |
| note | Stitching vias sit under some silkscreen text | cosmetic |
| note | Mono's case script stops on Tally: it has no size for J3's package, and names Mono's generator | the case is not drawn |
| note | The folder has no golden pictures, 3D shapes or panel footprint, and its pictures' script is not in the repo | for a KiCad 10 machine |
| note | Firmware: an unknown board name falls back to a profile that reads GPIO20 and 21 as keys; the link code talks to the chip's own USB; a maintenance REPL has no port | Open |

Their notes, scripts and pictures were in the session's scratch folder and are not kept.
