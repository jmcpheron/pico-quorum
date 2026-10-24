# Testing the board

`tools/test.sh` runs everything in `tests/` in about 60 s on a laptop with KiCad 10, `ngspice`,
FreeCAD 1.x (for `test_3d`, skipped without it) and system Python 3. No extra packages. It never writes to `hardware/picoquorum-key` or `hardware/out/rev-*`
(it checks file hashes before and after) and puts scratch files in `hardware/out/scratch/test/`.

```
tools/test.sh                    # all of it
tools/test.sh test_geometry      # one module
CONSOLE_PCB=/path/x.kicad_pcb tools/test.sh   # another copy of the board (a mutant, a later rev)
```

| module | what it checks | why it is worth having |
|---|---|---|
| `test_pin_contract` | module pin, GPIO and net agree across KiCad's ESP32-S3 symbol, `PINS.md`, `circuit.py`, the routed board, `picoquorum_key.py` and `smoke.py`; straps; PCB pad nets equal the schematic's | the pin table is hand-copied in five places; the symbol is the independent truth |
| `test_mutation` | injects 11 board faults and 3 netlist faults into scratch copies and requires DRC / `check_netlist.py` to fail; a clean round trip is the control | shows the existing checks would notice an open, a short, a swap, a missing part, the antenna band, an edge hole |
| `test_geometry` | the placement table in `DESIGN.md`, antenna band empty, pours from Y 7.5, a screw keep-out at each hole, buttons level with the screen rows, J2 pad order, track widths and current, decoupling distance, USB skew | the layout claims were prose only |
| `test_silk` | silk lines >= 0.15 mm, text >= 1.0 mm high with a 0.15 mm stroke, back text mirrored, nothing within 0.5 mm of the edge; each button label sits under its switch; each test-pad label is its net's name; the R12/R13 and flash legends match the netlist | silk is the one place a human reads the board, so a wrong label is a bug; DRC covers silk over pads and silk on silk |
| `test_fab_files` | reads the Gerber zip back with a small stdlib reader (`tests/gerber.py`, no KiCad code): exactly the promised layers, job file agrees, outline closed and 44 × 53, every drill hit, slot, copper, mask and paste flash is a hole or pad on the board and vice versa, rings measured from the files, vias tented | the zip is what JLCPCB builds; this catches a stale export, a shifted drill origin, a missing or mislabelled layer |
| `test_assembly_files` | `bom.csv` and `cpl.csv` against the board and `circuit.py`: same parts, DNP and test pads absent, LCSC numbers, positions in the CPL frame, rotations; JLCPCB's own footprint (where the repo has one) placed with the CPL's numbers must land on the board's pads with matching pin numbers | wrong rotation and polarity are the usual first-order assembly faults, and DRC can't see them |
| `test_holes` | the project's rules against JLCPCB's limits (`tests/jlc_limits.py`, with its source and date), then every via and hole: drill, ring, hole to hole, hole to other-net track, vias in or beside SMD pads, the M2 screw-head keep-out, finished size after drill tolerance, thermal spokes on the hand-soldered module and on every two-pad part's GND end | the fab's numbers, applied hole by hole, with a full table in `scratch/test/holes/holes.csv` |
| `test_jlc_rules` | `picoquorum-key.kicad_dru` (JLCPCB rules KiCad's DRC applies while you edit) against `jlc_limits.py`: every JLC limit is enforced by a project minimum, the rule file or a named test; the routed board passes; each rule, pushed past the board's values, fires under its own name on the items it's meant for; a 0.15 mm ring on J1 and a 0.45 mm NPTH pass the project's minimums and are caught by the file alone | moves the fab's limits from a test you run into DRC, where a later edit meets them; a rule with a typo in its condition would otherwise pass silently |
| `test_3d` | kicad-cli's STEP with every model, intersected in FreeCAD (`tests/freecad/fit.py`) with the glass on its tape, the ribbon's path and fold, the tape strips, M2 heads and nuts, the board and each other; part heights against `DESIGN.md`; every part has a model. Draws a top view and three side sections (`scratch/test/3d/*.png`), clashes in red | the one check of height: courtyards and DRC are flat. It found the switch model sunk 2.9 mm into the board and the ZIF drawn with its actuator open |
| `test_paste_mask` | the stencil and mask as the Gerbers have them: IPC-7525 area ratio (≥ 0.66) and aspect ratio (≥ 1.5) of every aperture at 0.12 mm, and the thickest stencil the board takes; paste coverage per pad, both ends of each two-pad part equal, stencil webs, paste only on parts the CPL places; every mask opening at least its copper, and other nets' tracks at least 0.09 mm from a pad's opening. Draws `scratch/test/paste/closeups.svg` and `front-paste.svg` | paste problems are invisible to DRC and show up as tombstones, opens or bridges after reflow; this picks the stencil thickness to order |
| `test_visual` | every fab layer and the drill file, drawn from the zip by `tests/raster.py`, and KiCad's top and bottom renders, compared pixel for pixel with the approved copies in `tests/golden/`; each change is reported in board mm with the parts under it, and drawn in `scratch/test/visual/<name>-diff.png` (approved, now, changes in red). `sheet.png` shows every current picture | nothing changes without someone looking at it: a re-route, a nudged part, a silk edit all fail until approved with `CONSOLE_BLESS=1 tools/test.sh test_visual`. Renders are skipped under a different KiCad version |
| `test_spice` | backlight dark when GPIO21 floats, current under the panel limit over 64 corners, EN delay vs the 3V3 ramp, I2C rise time with the routed trace length | decks are rebuilt from the schematic netlist, so rewiring changes what is simulated; models are generic, read results as bias and timing |
| `test_twin` | runs `firmware/smoke/smoke.py` unmodified against a fake `machine` wired through the PCB's pad nets, with scripted button presses; six miswired variants must fail | the only test that connects the firmware to the layout |

Each module was also checked the other way: a sabotaged board or component value turns the matching
test red (`CONSOLE_PCB` for the board tests, patched values for SPICE).

## Open findings the suite reports

Nothing fails today. Reported, not failed:

- J1's footprint origin is 1.46 mm from its pad centre: check its position in JLCPCB's placement preview.
- 18 of 20 BOM lines have no JLCPCB footprint in the repo, so their CPL rotation is checked only against
  KiCad's; `tools/fetch_parts.sh <C-number>` adds one.
- **C1 and C8 (LDO input) are 5.5 and 5.0 mm from U3's input pin.** Reported, not asserted.
- **Backlight at reset:** with R14 at 4.7k the backlight stays dark for any GPIO21 pull-up of about 23 kOhm
  or more, about 2x margin against the S3's typical ~45 kOhm internal pull-up. Confirm GPIO21's reset
  state in the ESP32-S3 datasheet if you want the exact figure.

Fixed after the first run: C4 moved 0.15 mm right (its pad overlapped the ribbon fold); the GND
stitching via under module pad 41 removed (`post_route.py` now skips that area); C2 moved under the
LDO tab and C6 next to the panel VDD pad (both now asserted within 5 mm); R14 changed from 100k to
4.7k; and `smoke.py` wakes the ATECC before its I2C scan.

Fixed after the fab-file and hole checks (all now asserted):
- Two GND stitching vias sat inside solder pads (SW1 pad 2, C8 pad 2). `post_route.py` now keeps
  stitching vias clear of every pad, whatever its net.
- EN and USB D+ ran about 2.0 mm from H2's centre, under the screw head. Each M2 hole now has a
  2.5 mm track-and-via keep-out on both faces (`test_geometry` checks the areas, `test_holes` the copper).
- Nine 0603 parts (C4–C8, D1, R1, R2, R14) had one end solid in the front GND pour, a tombstoning
  risk. The front pour now uses thermal spokes like the back. J1's four edge GND contacts are solid
  locally: at the edge a relief only had room for one spoke.
- The project's silk rules were below JLCPCB's. They are now 1.0 mm text, 0.15 mm stroke and 0.15 mm
  silk to pad, so DRC (and `tools/export.sh`) stop a later edit that breaks them.
- To get a clean route, the DSN now gives Freerouting 0.01 mm extra clearance.

Found by the 3D check, fixed: the tact switch's `.step` (a generic 6.5 mm part) sat 2.9 mm into the
board, and the ZIF's model had its actuator standing open, 1.75 mm tall, which would have put it
through the glass at 1.5 mm. `tools/gen/fix_models.py` makes corrected copies (see DESIGN.md).
`test_3d` was sabotage-checked with six boards: ZIF open, switch sunk, R5 without a model, C6
on the tape, SW7 under a screw head, C7 on U2. Each failed its own test. `test_fab_files` also measures
the solder-mask web between different nets' openings: 0.20 mm at J2's 0.5 mm pitch, against JLCPCB's 0.10.

From the paste and mask check (passing, for the record):
- Lowest area ratio at 0.12 mm is 0.83, on U2's 0.82 × 0.25 mm pad apertures (it was 0.91 on J2 with
  the SOIC). The thickest stencil every aperture takes is 0.150 mm, so order 0.10, 0.12 or 0.15 (ORDERING.md).
- U3's tab (7.4 mm²) gets a full aperture. If the regulator floats or skews in reflow, a window-pane
  aperture at 50–80 % is the fix.
- The thinnest stencil web is 0.20 mm (J1's contacts), and the closest other-net track to a pad's opening
  is 0.21 mm (+5V past U3 pin 1).
- Sabotage-checked: J2's paste shrunk, C6's paste uneven, U4's mask openings shrunk and widened, R5
  missing from the CPL. Each failed its own test.

The golden-image check was sabotage-checked with C6 moved 0.25 mm (caught on F.Cu, F.Mask, F.Paste,
F.Silk and the top render, each placed at C6) and one silk letter changed (caught on F.Silk and the
render, near SW7). The approved copies are from this board as of 2026-10-24.

## What stays a bench check

3V3 under Wi-Fi load and the AMS1117 with ceramic output capacitors (not modelled), antenna
performance, USB enumeration, and the panel fit.
