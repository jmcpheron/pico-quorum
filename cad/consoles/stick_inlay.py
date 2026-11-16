"""The stick, in colours: stick.py's case with its mark printed flush in the face, for a printer that changes
filament itself. The case is stick.py's: the same outline, edges, window, caps, screws, back panel and dock. What
changes is the mark at the antenna end, in the front shell:
- it is not engraved. Green fills the triangle and the three signed dots, orange the two waiting dots, each 0.6 mm
  deep from the face, three layers, the first on the bed (mono_ind.decor's inlay). The face is flat
- black lines 0.5 mm wide cross the green triangle, and a black ring goes round each signed dot inside it, as on
  the slate's industrial case, so the dots show as dots
- RESET is a 1.8 mm pinhole through the lower-left dot, as BOOT's is, not the whole dot (stick.py's: 3.75 mm): the
  dot is a green ring 1 mm wide round it
- the green stands 0.8 mm back from the LED's hole, which is 0.4 mm from the triangle's left edge: a bite 0.4 mm
  deep in that edge

The colours, two ways: stick_inlay_shell_colours.3mf, one object of three parts, black, green and orange; or
stick_inlay_shell_black.stl, _green.stl and _orange.stl, the same three, each in the shell's own place.
stick_inlay_shell.stl is the three as one body: its face is plain. For one filament, print stick.py's.

(cad/consoles/README.md, "The stick, in colours")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow --with fonttools --with brotli \\
         python cad/consoles/stick_inlay.py [screen.png]
(or tools/case build stick-inlay)

Writes out/stick_inlay/, the same files as stick.py with stick_inlay_ in place of stick_; the shell's three bodies
and their 3MF; and stick_inlay_mark.png: the mark from the front, in the three colours. Not sliced, not printed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import stick as ST      # noqa: E402
import rp as RP         # noqa: E402
import mono_ind as MI   # noqa: E402  the mark printed in the face (decor), its picture, the shell's three bodies

OUT = os.path.join(HERE, "out", "stick_inlay")
# The colours' depth from the face, three 0.2 mm layers, and the lines across the triangle: 1.44 mm apart at this
# mark's size
HATCH = dict(pitches=6, depth=RP.ENGRAVE_DEEP)
LED_CLEAR = 0.8             # black round the LED's hole, at the least


def decor(c, shell, back):
    """RESET's pinhole, through the mark's lower-left dot, and then the mark (mono_ind.decor)."""
    q = c.b["parts"][c.b["reset"]]
    return MI.decor(c, shell.cut(S.cyl(q["x"], q["y"], S.PIN_HOLE / 2, c.zu - 1, c.zt + 1)), back)


def board():
    b = ST.board()
    (_, (cx, cy, r, reset)), = b["face"]        # stick.py's mark: drawn from RESET, its lower-left dot over it
    led = b["parts"][b["led"]]
    b.update(name="stick_inlay", title="The stick, in colours", face=[], decor=decor, reset=reset,
             mark=(cx, cy, r), hatch=HATCH, inlay=True, name_fit=None,
             keep=[(led["x"], led["y"], S.LED_HOLE / 2 + LED_CLEAR)])
    return b


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else ST.SCREEN)
    MI.mark_picture(c, OUT)
    print("stick_inlay: the mark's lines: %d across the triangle, %.2f mm apart, %.2f mm between them" % c.hatch)
    print("stick_inlay: the shell's bodies: " + ", ".join("%s %.1f mm3" % b for b in MI.bodies(c, OUT)))
    MI.threemf(c, OUT)
    return bad


if __name__ == "__main__":
    sys.exit(main())
