"""Mono's case, industrial, in colours: mono_ind.py's case with its mark and name printed flush in the face, for a
printer that changes filament itself. The case is mono_ind.py's: the same cut corners, edges, grooves, window, caps,
screws, back panel and dock, and the same mark and name, at the same size and place. What changes is how they are
made, in the front shell:
- nothing is cut into the face. Green fills the triangle, the three signed dots and the name, orange the two
  waiting dots, each 0.6 mm deep from the face, three layers, the first on the bed (mono_ind.decor's inlay). The
  face is flat
- the lines across the triangle, and the ring round each signed dot, are black through that depth (mono_ind.py's:
  0.4 mm, over the colour)

The colours, two ways: mono_ind_inlay_shell_colours.3mf, one object of three parts, black, green and orange; or
mono_ind_inlay_shell_black.stl, _green.stl and _orange.stl, the same three, each in the shell's own place.
mono_ind_inlay_shell.stl is the three as one body: its face is plain. For one filament change, print mono_ind.py's.

(cad/consoles/README.md, "Mono, industrial, in colours")

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python cad/consoles/mono_ind_inlay.py [screen.png]
(or tools/case build mono-industrial-inlay)

Writes out/mono_ind_inlay/, the same files as mono_ind.py with mono_ind_inlay_ in place of mono_ind_, and the
shell's 3MF. Not sliced, not printed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell as S       # noqa: E402
import rp as RP         # noqa: E402
import mono as M        # noqa: E402
import mono_ind as MI   # noqa: E402

OUT = os.path.join(HERE, "out", "mono_ind_inlay")
HATCH = dict(depth=RP.ENGRAVE_DEEP)     # the colours' depth from the face, three 0.2 mm layers; the name's is the same


def board():
    b = MI.board()
    b.update(name="mono_ind_inlay", title="Mono's case, industrial, in colours", hatch=HATCH, inlay=True)
    return b


def main():
    bad, c = S.build(board(), OUT, sys.argv[1] if len(sys.argv) > 1 else M.SCREEN)
    MI.mark_picture(c, OUT)
    print("mono_ind_inlay: the mark's lines: %d across the triangle, %.2f mm apart, %.2f mm between them" % c.hatch)
    print("mono_ind_inlay: the shell's bodies: " + ", ".join("%s %.1f mm3" % b for b in MI.bodies(c, OUT)))
    MI.threemf(c, OUT)
    return bad


if __name__ == "__main__":
    sys.exit(main())
