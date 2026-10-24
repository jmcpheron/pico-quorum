# tools/jlc: the checks before a JLCPCB order

`tools/keypcb jlc <board>` runs these on any board `tools/keypcb` knows. It reads the board, its
schematic and the files in `<board>/fab/`, the ones you upload, and writes tables and pictures to
`<board>/fab/check/`. That folder is git-ignored and cleared each run. Each line it prints starts
"ok", "warn", "FAIL" or "info". It exits 1 on any FAIL.

The limits are JLCPCB's for a standard 2-layer board, 1 oz copper, green mask, in `limits.py`, each
with the page's own words. They were read from <https://jlcpcb.com/capabilities/pcb-capabilities> on
2026-10-23. Read the page again before an order: JLCPCB changes it.

| | check | how | where |
|---|---|---|---|
| 0 | the zip, BOM and CPL in `fab/` are the board's | `tools/keypcb fab` again into a temp folder, compared with dates stripped | `tools/keypcb` |
| 1 | DRC at JLCPCB's limits | a copy of the project with `limits.py`'s rules as its `.kicad_dru`, every check's severity raised to error, schematic parity on. A board's `jlc_spec()["jlc_allow"]` names what it lets pass, and why | `tools/keypcb` |
| 2 | the Gerbers and drills, read back | gerbonara, not KiCad, reads the zip: the layers, the outline, copper from the edge, each drill hit against the board's holes, each pad's `.P`/`.N` attribute against the board's pad and net, and each layer drawn again and laid over the board's own shapes to 0.05 mm | `gerb_check.py` |
| 3 | the electrical-test netlist | `kicad-cli pcb export ipcd356` (what a flying probe tests) against the schematic's netlist: the same pads in each net, the names as far as IPC-D-356's 14 characters | `netlist_check.py` |
| 4 | the BOM and CPL | each part in both or neither; not-fitted parts in neither; each CPL row at its part's place and side; each footprint's pad count, pitch and value against the LCSC part in `parts.json`; the CPL overlay picture | `netlist_check.py`, `gerb_check.py` |
| 5 | mask and paste | the mask web between different nets' pads; no via in or near an SMD pad's opening; mask- or copper-defined pads; paste area ratio for a 0.12 mm stencil | `pcb_checks.py` |
| 6 | vias and holes | each via's ring, gap and tenting; plated and plain holes, slots; copper round mounting holes; hand-soldered pads joined by spokes; `holes.csv` | `pcb_checks.py` |
| 7 | heat, pours, return path | the regulator's copper and a rough temperature, pour islands, how much of each fast net runs over ground | `pcb_checks.py` |
| 8 | the fit in 3D | each part's courtyard as a box to its height, plus the board's own solids (module, glass, ribbon, screws), every pair intersected; `fit.step` | `fit3d.py`, in FreeCAD |
| 9 | golden pictures | each layer against `<board>/fab/golden/`; a change is a warning and a picture, a FAIL only with `--strict` | `gerb_check.py` |

Check 10 is by hand, in [ORDERING.md](../../hardware/key-pcb/ORDERING.md).

The board's generator says what is particular to it in `jlc_spec()`: the regulator, the fast nets,
the allow-list and the 3D solids. A board without one gets the checks that need nothing from it
(console-s3's is in `hardware/console-s3/gen_console_s3.py`).

## Pictures

- `tight-spots.png`: the tightest places found (via gaps, the narrowest track, rings, mask webs,
  paste ratio, and anything that failed), each 3.2 mm across, drawn from the Gerbers, with the
  value against its limit.
- `cpl-overlay.png`: each CPL row's rotation as an arrow, and pin 1, on the board. Hold it beside
  JLCPCB's placement preview.
- `fit-iso.png`, `fit-fold.png`, `fit-side.png`, `fit-end.png`: the 3D fit. Clashes are red.
- `diff-<layer>.png`, `changed-<layer>.png`, `drill-mismatch.png`: only when something disagrees.

## Self-test

`tools/keypcb jlc --selftest <board>` breaks a copy of the board once per check (a thin track, a
thin via ring, a via in a pad, an island, a pad on the wrong net, a hole out of the drill file, a
row out of the CPL, parts too tall, a stale zip, a thinned track against the golden pictures) and wants
each one caught. Their pictures go to `fab/check/selftest/`. On console-s3, 2026-10-23: 10 of 10.

## What it needs

- KiCad 10's `kicad-cli` and its Python, as the rest of `tools/keypcb`.
- uv. `gerb_check.py` names its packages in its header (gerbonara 1.6.3, numpy 2.5.3, Pillow
  12.3.0) and `gerb_check.py.lock` pins every package by hash; it runs with
  `uv run --locked --script`. The lock also pins packages gerbonara names but these checks don't
  use (its web viewer's).
- FreeCAD 1.1's `freecadcmd` for check 8 (`FREECADCMD`, or `/Applications/FreeCAD.app`). Without it,
  check 8 is skipped with a warning.

None of it makes a network call but uv's first download of the locked packages.

## What it doesn't do

It checks the files against the board and the board against JLCPCB's printed limits. It doesn't
replace JLCPCB's own DFM check or a look at their placement preview. The 3D sizes are datasheet
figures and guesses (the board's `jlc_spec` says which), and the temperature is a rough figure
from a datasheet's θJA, not a measurement.
