# Tally's library

Every symbol and footprint the project uses, so it opens with no other library installed.
`gen_tally.py import` wrote the footprints; `gen_tally.py` writes the symbols on each run.

| what | from | licence |
|---|---|---|
| `tally.pretty/RPi_*`, and the copper in `../rpi_minimal.json` | Raspberry Pi's minimal RP2350 design, by way of `hardware/mono/lib/` | MIT: [RPI-MINIMAL-LICENSE.txt](RPI-MINIMAL-LICENSE.txt) |
| `tally.pretty/FPC_ZIF_8P_P0.5mm_HDGC_0.5K-HX-8PWB` | this repository (`hardware/mono/lib/mono.pretty`, first drawn for console-s3) | the repository's |
| `tally.pretty/WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm`, `SOIC-8_5.3x5.3mm_P1.27mm` | KiCad's footprint library, tag 10.0.0, rewritten in KiCad 7's format | CC-BY-SA 4.0, with KiCad's exception for use in a design |
| the other 16 footprints | KiCad 7.0.11's footprint library. The USB-C's shell pads and the JST's tabs are renamed `SH`; the USB-C's silkscreen past the board's edge is left out | the same |
| `tally.kicad_sym`: R, C, LED, the crystal, the two FETs, the switch, test point, hole, fiducial and the power symbols | KiCad 7.0.11's symbol library | the same |
| `tally.kicad_sym`: the rest, drawn as plain boxes | `gen_tally.py` | the repository's |
