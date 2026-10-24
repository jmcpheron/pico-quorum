# From KiCad to a JLCPCB order

*2026-10-23. KiCad 10.0.x on macOS, `kicad-cli` on the path (`brew install --cask kicad` puts it
there). No plugins are required; everything is `kicad-cli` plus one Python script.*

## Before exporting

- [ ] Board routed. ERC clean, DRC clean with no unconnected items (the export script refuses
      otherwise).
- [ ] Every placed symbol has an `LCSC` field with its C-number ([BOM.md](BOM.md)).
- [ ] U1 (module) is marked **DNP** so it leaves the assembly BOM but stays on the board. Test points and mounting holes are **excluded from BOM**.
- [ ] One real ER-TFT1.14-2 checked on a 1:1 print: folded tail reaches J2, pin 1 at the bottom.
      See [DESIGN.md](DESIGN.md), "The panel and its ribbon".
- [ ] `hardware/out/rev-a/fit-check-front-1to1.pdf` printed at 100% ("actual size") and checked
      against the real panel and your thumb.
- [ ] Board rev text updated on the silkscreen; git tag `rev-a`.
- [ ] `tools/test.sh` green after the final export. `test_visual` compares the fab layers and
      renders with the approved copies in `tests/golden/`; after a deliberate change, look at the
      `*-diff.png` sheets it writes, then approve them with `CONSOLE_BLESS=1 tools/test.sh test_visual`.

## Export

```sh
tools/export.sh rev-a
```

writes `hardware/out/rev-a/`:

```
gerbers/              F.Cu B.Cu F.Paste F.SilkS B.SilkS F.Mask B.Mask Edge.Cuts, Protel extensions, no X2
                      (no B.Paste: nothing on the back is machine-placed, so one stencil only)
gerbers/*.drl         Excellon, PTH and NPTH separate
picoquorum-key-gerbers.zip
picoquorum-key-pos.csv    KiCad position file, front side, mm
picoquorum-key-kicad-bom.csv
bom.csv               JLCPCB BOM:  Comment, Designator, Footprint, LCSC Part #
cpl.csv               JLCPCB CPL:  Designator, Mid X, Mid Y, Layer, Rotation
erc.txt drc.txt
```

`tools/jlc_bom_cpl.py` merges rows that share a C-number (the five switches become one line), uses
the `MPN` field as the comment where one is set, drops DNP and parts without an LCSC
number (listing them on stderr so you can see that only U1 is missing), and applies
per-footprint rotation offsets from `tools/rotations.json`. JLCPCB's rotation convention differs
from KiCad's for some packages (SOT-23, SOT-223, SOIC, USB-C often need ±90° or 180°). The table
starts empty: check every part in JLCPCB's placement preview the first time, write the offsets you
had to apply into the JSON, and they apply from then on.

## Upload

1. **PCB**: upload `picoquorum-key-gerbers.zip`. Options: 2 layers, 44 × 53 mm (read from the Gerbers),
   5 pcs, 1.6 mm, any colour (black hides the module's solder joints less; green is cheapest), HASL
   lead-free or ENIG, 1 oz, min via 0.3 mm, "Specify a location" for the order number: no, tented
   vias: yes. Remove-order-number: optional.
2. **Assembly**: Economic, **top** side (the face the Gerbers call F.Cu), 5 pcs, tooling holes added
   by JLCPCB, confirm parts placement: yes. Stencil: JLCPCB picks the thickness unless told. Any of
   0.10, 0.12 or 0.15 mm prints every aperture (`test_paste_mask` finds U2's 0.25 mm pad apertures limit it
   to 0.150 mm); 0.12 is the usual and a good choice. 0.18 and 0.20 are too thick for U2 and J2.
3. Upload `bom.csv` and `cpl.csv`. On the parts page every line should match its C-number; anything
   "not found" is a stock or tier change: fix the C-number in the schematic, re-export.
4. **Placement preview**: check each part's rotation and polarity — U3's tab, U4 pin 1, Q1/Q2
   orientation, D1 polarity, U2's pin 1 (a UDFN's dot is small: hold it against `cpl.csv`'s rotation), J1 and J2 orientation. J2's hold-down tabs and entry slot face the
   board's right edge; its contact tails face left. Fix offsets in `tools/rotations.json`,
   re-export, re-upload if anything is off.
5. DFM check, then pay. Record the final options and cost below.
6. **Modules**: add 7 × C2913204 to the LCSC cart from the same account; JLCPCB can ship them with
   the order, or they come separately.
7. **Panels** from BuyDisplay or MikroElektronika ([BOM.md](BOM.md)).

## Record of orders

| date | rev | PCB | assembly | parts | shipping | total | notes |
|---|---|---|---|---|---|---|---|
| | rev-a | | | | | | |
