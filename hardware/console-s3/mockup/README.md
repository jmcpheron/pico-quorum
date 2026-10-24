# console-s3 mockup

Two STLs to print and stack, made by [tools/mockup](../../../tools/mockup/README.md) from the routed board.
Rough blocks at about the right sizes: for holding and trying in a case, not for measuring.

| file | what | print it |
|---|---|---|
| `console-s3-board.stl` | the board, the front parts and the panel, one solid, 5.2 mm tall: the board 1.6, the glass's top 3.6 over it | as it is, back face down, no supports |
| `console-s3-module.stl` | the ESP32-S3-WROOM-1 on the back, 18 x 25.5 x 3.1 mm | as it is, soldered face down, no supports |

To stack them: turn the module over, its flat face against the board's back, inside the groove that
outlines it. Its bare antenna end goes to the end past the groove's cross line, at the board's edge.
Glue or tape it.

A layer of 0.1 to 0.12 mm keeps the smallest parts (0.55 mm resistors) more than a smear. Run
`tools/mockup/mockup.py console-s3` again after the board changes.
