# tools/mockup

Printable mockups of the two S3 boards, console-s3 and PicoQuorumKey: something to hold, put in a
hand and try in a case before the boards come. Not a model to measure.

    tools/mockup/mockup.py                    # both boards
    tools/mockup/mockup.py picoquorum-key     # one

It needs KiCad (its Python reads the routed board) and FreeCAD's `freecadcmd` (`FREECADCMD`), as
`tools/keypcb jlc` does. Run it again after a board changes and commit what it writes.

What it writes, in `<board dir>/mockup/`:
- `<board>-board.stl`: the board's own outline and M2 holes; each part on the front as a block (its
  courtyard less the 0.25 mm margin, to a datasheet or typical height); the panel as one block from
  the board to the glass's top, its ribbon's fold beside it. Fused into one solid, back face down.
  On the back, a 0.4 mm groove outlines the module, with a line where its shield ends and its
  antenna begins.
- `<board>-module.stl`: the ESP32-S3-WROOM-1, 18 x 25.5 x 3.1 mm, its soldered face down, the
  antenna end bare. The same file for both boards.

Where the numbers come from:
- The outline, the holes and every part's place and courtyard: the routed `.kicad_pcb` (`facts.py`).
- The panel and fold: console-s3's generator (`jlc_spec()["fit"]`), PicoQuorumKey's `GLASS` and
  `FOLD_Y` in `tools/gen/gen_pcb.py`, with its 1.5 mm tape and 1.6 mm panel.
- Heights: console-s3's generator, then the table in `mockup.py`.
- The module's split between its board and its shield, and the shield's inset, are rough.

Files: `mockup.py` runs the rest; `facts.py` reads the board (KiCad's Python); `build.py` makes the
solids and the STLs (FreeCAD).
