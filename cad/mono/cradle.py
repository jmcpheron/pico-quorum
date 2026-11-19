"""A stopgap for the days before the spring probes come: a shallow cradle for the bottom end of Mono's
board, with a hole under each of the three SWD pads (TP1 SWCLK, TP2 GND, TP3 SWDIO) for a jumper wire.

Run: uv run --python 3.11 --with cadquery --with matplotlib python cad/mono/cradle.py

Writes out/: mono_cradle.stl, as it prints, no support; mono_cradle.png and mono_cradle_under.png. The
latches are jig.py's (mono_jig_latch.stl, print two).

How it works:
- It is jig.py's pocket, cut off above the pads' row: the same deck, the same opening for the USB-C's
  plug, the same two latches. The rest of the board stands out past its top end.
- Each wire comes up its hole from underneath, its stripped end spread over the hole's mouth. The board
  pressed to the deck squashes the strands onto the pad: soft copper in place of a stiff pin.
- The wires leave along a channel in the bottom, out of the top end, under the board.
- The latches' screws cut their own thread in a printed hole: no inserts. A rubber band round the cradle
  and the board, lying in the latches' landings, does the same job.

It takes the pads' places, the checks and the latches from jig.py, and so from the routed board.
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("jig", os.path.join(HERE, "jig.py"))
J = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(J)
B, G, OUT = J.B, J.G, J.OUT
box, rod = J.box, J.rod

PADS = ("TP1", "TP2", "TP3")         # SWCLK, GND, SWDIO, from the left edge in
HOLE = 1.9                           # a jumper wire in its insulation is 1.2 to 1.5 mm; a printed hole comes out small
SLAB = 6.0                           # the plastic under the deck
CHANNEL = 3.0                        # the wires' channel, cut up into the bottom
PILOT = dict(d=2.8, depth=6.5)       # an M3 screw cuts its thread in this
TOP = J.SWING + 5.0                  # the cradle ends this far above the pads' row

ZD = J.ZD
Z_BOT = ZD - SLAB


def cradle(xs, yp, j1):
    y_top = yp + TOP
    body = box(-J.RIM, G.W + J.RIM, -J.END, y_top, Z_BOT, J.LIP).edges("|Z").fillet(3.0)
    # the board's pocket, open at the top end where the board runs on
    pocket = box(-J.FIT, G.W + J.FIT, -J.FIT, y_top + 10, ZD, J.LIP + 1).edges("|Z").fillet(G.CORNER + J.FIT)
    body = body.cut(pocket)
    # the USB-C, as the jig has it: the rim open for the plug, a relief under the shell's legs
    jx0, jx1, jy1 = j1
    body = body.cut(box(jx0 - 3.0, jx1 + 3.0, -J.END - 1, 0.5, ZD - 3.5, J.LIP + 1))
    body = body.cut(box(jx0 - 1.0, jx1 + 1.0, -J.FIT, jy1 + 2.0, ZD - 1.5, ZD + 1))
    # the three holes, and the channel from under them out of the top end
    for p in PADS:
        body = body.cut(rod(xs[p], yp, HOLE, Z_BOT - 1, ZD + 1))
    body = body.cut(box(xs[PADS[0]] - 1.5, xs[PADS[-1]] + 1.5, yp - 1.5, y_top + 1, Z_BOT - 1, Z_BOT + CHANNEL))
    # the latches' landings and their screws' holes
    for x0, x1, x in ((-J.RIM - 1, -J.FIT, J.XL), (G.W + J.FIT, G.W + J.RIM + 1, J.XR)):
        body = body.cut(box(x0, x1, yp - J.SWING, yp + J.SWING, J.LAND, J.LIP + 1))
        body = body.cut(rod(x, yp, PILOT["d"], J.LAND - PILOT["depth"], J.LAND + 1))
    return body


def main():
    os.makedirs(OUT, exist_ok=True)
    fps = B.footprints()
    xs, yp = J.pads(fps)
    J.checks(fps, xs, yp)
    assert J.POGO["pitch"] - HOLE >= 0.6, "the wall between two holes is under 0.6 mm"
    assert J.LAND - PILOT["depth"] > Z_BOT + 0.8, "a screw's hole comes through the bottom"
    assert Z_BOT + CHANNEL < ZD - 2.5, "the channel's roof is under 2.5 mm thick"
    assert xs[PADS[0]] - 1.5 > J.XL + PILOT["d"] / 2 + 2, "the channel is under a screw"
    body = cradle(xs, yp, J.usbc(fps))
    assert len(body.val().Solids()) == 1, "the cradle is not one solid"
    pcb, bits, glass = B.board(fps), B.parts(fps), B.panel()
    for name, s in (("the board", pcb), ("its parts", bits), ("the glass", glass)):
        assert body.intersect(s).val().Volume() < 1e-6, f"the cradle cuts into {name}"
    shut = J.latch(J.XL, yp).union(J.latch(J.XR, yp, 180))
    for name, s in (("the cradle", body), ("the board's parts", bits)):
        assert shut.intersect(s).val().Volume() < 1e-6, f"a shut latch cuts into {name}"

    import cadquery as cq
    cq.exporters.export(body.translate((0, 0, -Z_BOT)), os.path.join(OUT, "mono_cradle.stl"), tolerance=0.01, angularTolerance=0.1)
    orange, dark = (0.95, 0.55, 0.15), (0.1, 0.1, 0.1)
    B.picture([(body, orange), (shut, dark), (pcb, (0.18, 0.42, 0.25)), (bits, (0.75, 0.75, 0.72)), (glass, (0.12, 0.13, 0.16))],
              os.path.join(OUT, "mono_cradle.png"), size=1100)
    turn = lambda s: s.rotate((G.W / 2, 0, 0), (G.W / 2, 1, 0), 180)          # the bottom toward the eye
    B.picture([(turn(body), orange)], os.path.join(OUT, "mono_cradle_under.png"), size=1100)

    bb = body.val().BoundingBox()
    print(f"wrote {os.path.relpath(OUT, B.REPO)}/: mono_cradle.stl, mono_cradle.png, mono_cradle_under.png; "
          f"{bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm")
    print(f"  three holes, {HOLE} mm as drawn, {yp:g} mm up from the bottom edge: "
          + ", ".join(f"{p} {xs[p]:g}" for p in PADS) + " mm from the left edge")
    print(f"  the board stands {J.L - (yp + TOP):.1f} mm out past the top end")


if __name__ == "__main__":
    main()
