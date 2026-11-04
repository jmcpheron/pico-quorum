# console-rp, to print

A print of [console-rp](../README.md) as JLCPCB is building it (the
[2026-10-29 order](../../../buildlog/2026-10-29-console-rp-order.md)), with its 1.14″ panel in place. It
is one solid: the board, every part and the panel are fused, so it prints in one piece with no
supports. Hold it to see the board's shape and size, where each part sits, and what a case must clear.

![the print from above and from the USB-C's corner: the panel at the top left, D0 D1 D2 under it, the flash, the RP2350 and the key chip with their names engraved, RESET and BOOT at the bottom right, the USB-C on the right edge and J3's eight holes along the top](out/console-rp-mockup.png)

| file | size | what |
|---|---|---|
| [`console-rp-mockup.stl`](out/console-rp-mockup.stl) | 72.05 × 36.0 × 5.2 mm | 1:1, plain. For the size, and for trying a case on |
| [`console-rp-mockup-2x.stl`](out/console-rp-mockup-2x.stl) | 144.1 × 72.0 × 10.4 mm | twice the size, so the 0402s print. RP2350, FLASH and KEY are engraved on their chips; D0, D1, D2, RESET, BOOT and LED on the board |

## Printing

- Flat on the bed as written: the board's back is the base. No supports, no brim needed.
- PLA or PETG, 0.2 mm layers; 0.12 mm shows the small parts better on the 1:1 print.
- On the 1:1 print the 0402s are 1.0 × 0.5 mm, about one line wide. Some may come out as blobs or not at
  all. The 2x print has them all.
- The holes are the board's: four M2.5 holes, 2.7 mm, and J3's eight, 1.0 mm. A case's screws can be tried
  in the 1:1 one's holes.

## What is in it

**Every part in `fab/cpl.csv`, the file JLCPCB placed the parts from, where the routed board has it.** The
script reads each part's place and turn from `console-rp.kicad_pcb`, and stops if any part in `cpl.csv`
isn't on the board at the same place, or if any part on the board isn't in `cpl.csv`.

Each part is a box at its datasheet's body size, with a 0.3 mm slab under it for its leads; heights are
`gen_console_rp.py`'s `HEIGHT`, the ones the fit check in `tools/jlc` uses. They are not the makers' models. The
buttons have a round plunger whose size is a guess.

The panel is as the [README](../README.md#the-panel) gives it: 31.0 × 17.6 × 1.6 mm glass on 2 mm foam, so its
top is 3.6 mm above the board and 5.2 mm above the board's back. The active area is sunk 0.4 mm into the glass,
1.4 mm left of the glass's centre, away from the ribbon. The ribbon's loop stands 1.8 mm past the glass's right
end; that is the drawing's figure, not measured.

**What isn't as on the board, so it prints:**
- The 2 mm under the glass is filled, 0.5 mm in from the glass's edge. J2, the backlight switch and their
  0402s are inside the fill. They can't be seen on a real board either.
- The USB-C is its outside, 8.94 × 3.2 mm, with a 1 mm socket in its face to show where the plug goes. A
  plug doesn't go in. Its face is at the board's edge, as the footprint's outline has it.
- J3 isn't fitted on these boards: its holes only.

**Nothing here is measured.** When the boards arrive, compare one with the print; heights first.

## Run

```sh
tools/case build console-rp-mockup
```

`tools/case check console-rp-mockup` builds it and lists any output that changed. The script also checks
that the result is one valid solid with its base at z 0.
