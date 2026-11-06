# console-rp rev B: a review before the order (2026-11-06)

A read of the short-bar board (commit `8949cce`: `hardware/console-rp/`, 48 × 64.5 mm) before its
fab files go to JLCPCB, and a view of the follow-up work on the ground check. It finds no wiring
mistake. It finds two things JLCPCB's own rules reject, three measurements rev A still owes, and a
list of smaller points. None of it needs a reroute: every fix here is a hand edit on the routed
board of the kind the README already describes, followed by writing the fab files once.

The circuit is rev A's, and rev A is up on the bench ([bench/BRINGUP.md](hardware/console-rp/bench/BRINGUP.md)):
the chip, crystal, flash, screen, buttons, LED, key and link all work. So the risk in rev B is in
what moved, not in the netlist.

## What was checked, and how

No KiCad here. So the DRC, `gen-console-rp check` and `tools/keypcb jlc` were not run again; the
README's record of them (2026-11-05, all passing) is taken as read. What was done instead:

- `gen_console_rp.py` read whole: the parts table, every net, the hand-drawn copper, the checks.
- Each part's pins against its datasheet pinout: the RP2350A (pins 51 and 52 are USB_DM and USB_DP,
  pin 50 is VREG_FB on DVDD, as the KiCad symbol names them), the CH343P, USBLC6-2SC6, XC6206,
  AO3401A, SS8050, ATECC608C, W25Q128, the USB-C and the ZIF.
- `console-rp.kicad_pcb` parsed with a script: every footprint's place, every track, via and
  zone, copper to the edge, copper near the holes and fiducials, vias near pads, each decoupling
  capacitor's distance to its pin, and which back-layer tracks cross the board.
- The Gerber golden pictures and the renders, by eye.
- The BOM and CPL against the rev A order's, which was built and works.
- JLCPCB's current help pages for fiducials, edge rails and V-cut panels (sources at the end).

What this review assumes: the README's numbers for the route (ground under each fast line, the
back pour in one piece) are right as of the correction below, and the 3D fit check ran on the Mac.

## Fix before the order

### 1. All three fiducials are closer to the edge than JLCPCB allows

JLCPCB's page on edge rails and fiducials says a fiducial must keep at least 3.35 mm from the board
edge, counting its clearance area; its page on process edges puts the mark's centre 3.85 mm in.
The board's three, centre to the nearest edge:

| fiducial | at (mm) | to the edge |
|---|---|---|
| FID1 | (39.0, 3.3) | 3.3 mm, top |
| FID2 | (9.0, 62.8) | 1.7 mm, bottom |
| FID3 | (3.0, 14.0) | 3.0 mm, left |

FID2 is the bad one: its 2 mm mask opening ends 0.7 mm from the edge, under any rail clamp. A
fiducial the camera half-sees is worse than none. Move all three in to 4 mm or more from the edge
(`AT["FID1"]`, `AT["FID2"]`, `AT["FID3"]` in the generator, and the same move on the routed
board), keeping each 1.3 mm clear of tracks as `FID_RING` asks and 2.6 mm from a hole's centre.
Or drop them for an Economic order: JLCPCB adds its own on the rails.

### 2. Copper within 0.4 mm of the right edge

Two tracks run along the right edge:

| net | x (mm) | y (mm) | copper to the edge |
|---|---|---|---|
| LED | 47.42 to 47.52 | 15.1 to 31.5 | 0.38 to 0.49 mm, between J3's pads and the edge |
| SWCLK | 47.49 | 36.8 to 51.8 | 0.41 to 0.43 mm, below J3 |

The board's own rule is 0.3 mm and JLCPCB's routed-edge minimum is 0.2, so DRC is clean. But
JLCPCB panelises assembled boards, and its V-cut page wants copper at least 0.4 mm from the cut
line and recommends 1.0 mm. These two tracks would sit on the line. The 2 mm corner radii also mean
a V-cut panel leaves a nub at each corner. Pull both tracks in to 0.6 mm or more from the edge
(there is room: J3's pad edges are at x 46.35), or write "tab-routed, no V-cut" in the order's
notes, or both.

### 3. Rev A's 1.4 V on DVDD is unexplained, and rev B copies that layout exactly

The core rail should be 1.1 V. BRINGUP.md records 1.4 V on the via beside L1 and calls it "not
yet measured again". If the reading is real, the chip is above its maximum and every rev B board
inherits it, since the regulator corner is Raspberry Pi's copper moved as one piece. If it is a
meter on a switching node, a scope on C2's pad settles it in minutes. The rev B plan lists this
under step 0; this review calls it a blocker for the order.

### 4. J3's USB has never enumerated

Rev B keeps the same path (pins 51 and 52, R13 and R14 at 27 Ω, J3) and draws the two lines
shorter and on the front, which is an improvement. But the rev A failure was never found. The
bench notes used jumper wires in bare holes, which is a plausible cause for full-speed USB on its
own. Test rev A again with a soldered header and a short cable before relying on it. If it still
fails, the fault is on the board and rev B would carry it. SWD loading doesn't depend on it; the
jig's BOOTSEL option and `picotool` do.

### 5. The XC6206 runs hot

At 0.12 A and the datasheet's 400 °C/W it is about 82 °C over the air, inside a closed case. The
CH343P runs from VBUS, not 3V3, so the real draw is nearer 70 to 90 mA: about 50 °C over, within
rating and uncomfortable. Measure it on rev A at full backlight, as the README's open item says.
An AP2112K-3.3 in SOT-23-5 is the swap if one is needed, and the only swap in the plan that
touches copper.

## Smaller things

- **C14 is still 11.4 mm from pins 53 and 54.** The rev B plan said to move it nearer and it was
  not done. Those pins have C1 at 1.9 to 2.2 mm through the 3V3 ring, so the chip is decoupled,
  and rev A runs. Not a blocker; a line for rev C.
- **The back ground is nearly cut in two.** RUN runs 27.6 mm straight across the back at y 33.2,
  from J3 to x 17.9, and LCD_BL runs 22.8 mm across the bottom at y 60.3. The halves meet through
  a few mm at the left and through the front pour's 199 ground vias. The README's return-path
  numbers are fine, and it is the layout's weakest ground region, where the screen's SPI lines
  cross. No check sees this; the README now says someone must look at the back.
- **A 3V3 via touches C19's pad edge** (at 15.4, 57.1), and Raspberry Pi's four DVDD vias sit
  0.15 mm from U1's exposed pad. Both are fine because the board tents its vias front and back.
  Keep "tented" selected at order time.
- **J3's 3V3 pin can back-feed the board** through the XC6206 if a jig drives it while the USB-C
  is unplugged. The bench notes already say each board gets its own cable. Make that a rule for
  the jig: J3's 3V3 is for measuring, not for powering.
- **CPL rotations.** J1 and U4 turned a quarter turn, and L1 is polarised. The README's step of
  holding `fab/check/cpl-overlay.png` beside JLCPCB's placement preview is the one that catches a
  dead link or a wrong-way inductor. Rev A proves the tooling for the parts that didn't turn.
- **Stale `jlc_spec()` entries.** It still describes U6 as "under the glass's edge" and allows the
  glass's silk over U6's pads. U6 is at (31.3, 38.2), 14 mm below the glass. Harmless, but the
  allow-list should shrink with the board, since each entry is a finding nobody will see.
- **Value swaps still undecided.** C18 at 4.7 µF, R8 at 27 Ω and the Basic 22 Ω pair are open in
  the plan. None affects copper; decide them with the order.

## The ground check, and what carries over

A second session (2026-11-05 to 06, on the Mac) turned the ground review into a check in
`tools/keypcb jlc`, moved two hand fixes into the generator, and corrected one number. The
direction is right: each item turns a one-off fix or a scratch script into something the next board
gets for free, which is the proper answer to "don't reroute". Points on it:

- **Make the via count a cut, not a tally.** The island under U1 holds nine thermal vias and
  more, so counting vias on it reads well even on the first route, which had one effective path.
  The right measure is the smallest set of vias whose removal separates U1's pad from the main
  ground, which is what the by-hand check did (remove three, the ground splits). The code should
  do the same.
- **Keep both thresholds in the board's `jlc_spec()`, not in the shared tool.** The 90 % ground
  floor under the flash's lines is for a board with a QSPI flash. Rev A measured 85 to 90 % and
  would fail it. That is fine for rev B and shows the number is this board's.
- **The correction from six vias to three matters.** This review's first draft repeated the
  README's six. Three vias carry the current easily; the problem is the loop. Every signal leaving
  U1 returns through the island under the chip, and the island reaches the rest of the ground
  through those three. So add ground vias, and set the floor to the count after adding them.
  A floor equal to the board's current value passes by construction: it guards against a worse
  route, not against this one being marginal.
- **Put the new vias in the generator**, not only on the routed board. They are ground vias at
  fixed offsets from U1, which is what `HAND_VIAS` holds. Then the generator's copper stays a
  subset of the routed board's, and the next revision starts with them.
- **Make that subset check permanent.** "All 312 drawn tracks and vias are on the routed board"
  was checked once by hand. It belongs in `gen-console-rp check`, so the routed board can't drift
  from the generator's locked copper without a message.
- **The unlocked LCD_CS via** is harmless: the route it would affect isn't going to be run.
- **Long back tracks** have no check. If one is ever wanted, the simplest is a warning when a
  single back-layer track spans more than half the board's width, which RUN and LCD_BL do today.
- **Pushing it runs CI in full**, because `.github/workflows/ci.yml` ignores only `hardware/`,
  `cad/` and `buildlog/`. None of CI's jobs runs KiCad or `jlc`, so the run can only fail on
  something unrelated to these edits.

## What looks right

- **The link's isolation is real and checked.** The USB-C reaches only the ESD clamp and the
  CH343P. DTR and RTS float. The RP2350's own USB and SWD go only to an unfitted header. The
  generator reads this back from KiCad's netlist and stops if it changes.
- **Raspberry Pi's copper, not a reinterpretation.** The regulator corner, the crystal corner and
  the thermal vias are copied from their files and locked, with each deviation listed and said
  why. That is the part people most often get wrong on an RP2350 board.
- **The QSPI lines are hand-drawn with 100 % ground under them,** and the review that found U1's
  pad on one via led to a keep-out, not a workaround. Measure, then constrain the router.
- **The USB front end is textbook.** D+ and D− flow through the USBLC6's pad pairs between the
  connector and the bridge, CC1 and CC2 each have 5.1 kΩ, VBUS has its clamp.
- **RP2350-E9 is handled**: a 4.7 kΩ external pull-down on the backlight line, no internal
  pull-downs anywhere.
- **The checks are strong for a one-person project:** netlist against the table, ERC, pin-to-pad
  parity, the GPIO function table, DRC at JLCPCB's limits, Gerber read-back, the IPC-356 netlist,
  the 3D fit, golden pictures, and a self-test that breaks the board a dozen ways.
- **The BOM is the proven one.** Every LCSC number matches the rev A order that came back working.
- **Ground:** 254 vias, 199 of them ground; the back is 2,690 mm² of ground out of 3,100.

## Suggested order of work

1. On rev A: DVDD on a scope at C2; U3's temperature at full backlight; J3's USB with a soldered
   header and a short cable.
2. Commit the ground-check work as one commit, with the README's "six vias" line corrected.
3. On the routed board, in one sitting: the ground vias by U1 (in `HAND_VIAS` too), the three
   fiducials moved in, the LED and SWCLK tracks pulled off the right edge. Then raise the via
   floor to the new count, and trim the stale `jlc_spec()` entries.
4. `gen-console-rp check`, `tools/keypcb fab`, `tools/keypcb jlc` once, the golden pictures and
   renders rewritten once.
5. Decide the value swaps, select tented vias and tab-routing in the order, hold the CPL overlay
   beside JLCPCB's preview for J1, U4, U1 and L1's dot.

## Sources

- JLCPCB, [How to add edge rails and fiducials for a PCB assembly order](https://jlcpcb.com/help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order):
  1 mm marks, mask-free, three or four along the edges, at least 3.35 mm from the edge including
  the clearance area; rails at least 5 mm.
- JLCPCB, [Specifications for adding process edges and positioning holes](https://jlcpcb.com/help/article/specifications-for-adding-process-edges-and-positioning-holes):
  fiducial centres 3.85 mm from the edge.
- JLCPCB, [V-cut panelization standards](https://jlcpcb.com/blog/technical-guidance-v-cut-panelization-standards):
  copper at least 0.4 mm from the V-cut line, 1.0 mm recommended; cuts run edge to edge.
- JLCPCB, [PCB panelization](https://jlcpcb.com/help/article/pcb-panelization).
- Rev A's bring-up: [hardware/console-rp/bench/BRINGUP.md](hardware/console-rp/bench/BRINGUP.md).
- The board and its checks: [hardware/console-rp/README.md](hardware/console-rp/README.md),
  [tools/jlc/README.md](tools/jlc/README.md).
