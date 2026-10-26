# picoquorum-key mockup

Two STLs to print and stack, made by [tools/mockup](../../../tools/mockup/README.md) from the routed board.
Rough blocks at about the right sizes: for holding and trying in a case, not for measuring.

| file | what | print it |
|---|---|---|
| `picoquorum-key-board.stl` | the board, the front parts and the panel, one solid, 5.4 mm tall: the board 1.6, the switches 3.8 over it | as it is, back face down, no supports |
| `picoquorum-key-module.stl` | the ESP32-S3-WROOM-1 on the back, 18 x 25.5 x 3.1 mm | as it is, soldered face down, no supports |

To stack them: turn the module over, its flat face against the board's back, inside the groove that
outlines it. Its bare antenna end goes to the end past the groove's cross line, at the board's edge.
Glue or tape it.

A layer of 0.1 to 0.12 mm keeps the smallest parts (0.55 mm resistors) more than a smear. Run
`tools/mockup/mockup.py picoquorum-key` again after the board changes.

**These STLs are rev A's** (44 × 53 mm, 1.6 mm). Rev B is 50 × 53 mm and 0.8 mm thick, with the key
port's notch and plug at the top-left corner, so a case made from them doesn't fit it. They haven't
been made again: `mockup.py` needs FreeCAD, which the machine that drew rev B didn't have. A rev B
mockup also wants a key-c on the plug, standing 36 mm out of the top edge, to try the case's slot
for it.
