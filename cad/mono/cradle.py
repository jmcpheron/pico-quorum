"""A stopgap for the days before the spring probes come: a shallow cradle for the bottom end of Mono's
board, with a 3-pin strip of right-angle 2.54 mm header under the three SWD pads (TP1 SWCLK, TP2 GND,
TP3 SWDIO).

Run: uv run --python 3.11 --with cadquery --with matplotlib python cad/mono/cradle.py

Writes out/: mono_cradle.stl, as it prints, no support; mono_cradle.png, mono_cradle_empty.png and
mono_cradle_under.png. The latches are jig.py's (mono_jig_latch.stl, print two).

How it works:
- It is jig.py's pocket, cut off above the pads' row: the same deck, the same opening for the USB-C's
  plug, the same two latches. The rest of the board stands out past its top end.
- The header drops into the deck from above, its bent legs first, each down its own slot, pointing up
  the board. Its plastic sits in a square pocket on the ribs between the slots; the straight pins stand
  PROUD of the deck, where the pads come down on them. The board pushes the strip onto the ribs, so
  nothing has to hold it.
- Under the deck a channel, open at the bottom, runs from the legs out of the top end: the jumpers'
  sockets slide in there, under the board, onto the legs. Past the legs' tips the deck over it is cut
  away, so the wires can leave upward too.
- A tray on the left holds the probe, a Pico 2 W, its USB at the same end as the board's USB-C. It lies
  flat, its header's pins up: GND, GP2 and GP3 (pins 3, 4 and 5) are in the row nearest the cradle.
  Grooves in the floor take the header's soldered ends, and four holes take M2 screws.
- The latches' screws cut their own thread in a printed hole: no inserts. A rubber band round the cradle
  and the board, lying in the latches' landings, does the same job.

Three stiff pins in a row touch on the tallest two; a first try with wires in holes didn't work either
(README.md). Paper under the plastic raises the strip; a bit of rubber band under it lets it give.

It takes the pads' places, the checks and the latches from jig.py, and so from the routed board. The
header's sizes (HEADER) are the usual right-angle strip's, not measured: measure yours.
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
# A right-angle strip: plastic 2.54 square, 3.0 mm of straight pin one side; the other side leaves the
# plastic, bends, and runs level, its middle `drop` from the plastic, its tip `reach` from the pin's line.
HEADER = dict(pitch=2.54, body=2.54, short=3.0, pin=0.64, drop=1.5, reach=8.5)
HFIT = 0.15                          # room round the header's plastic, each side
PROUD = 0.3                          # the straight pins' tips, over the deck
SLOT = 1.1                           # each leg's slot through the deck
UNDER = 10.0                         # the plastic under the ledge: a socket on a leg, and its wire's bend under it
ROOF = 2.0                           # the deck over the sockets' channel
SOCKET = 2.6                         # a jumper's socket, square
START = 2.0                          # the channel starts this far up from the pins' line: the ribs under the plastic end there
PILOT = dict(d=2.8, depth=6.5)       # an M3 screw cuts its thread in this
TOP = J.SWING + 5.0                  # the cradle ends this far above the pads' row
SIDE = 1.0                           # the channel, wider than the header's pocket by this each side
OPEN = 2.0                           # the deck is cut away over the channel from this far past the legs' tips
# The probe: a Pico 2 W, 51 x 21 x 1 mm, its two rows of holes 17.78 mm apart, its four M2 holes 11.4 x 47 mm
# apart (Raspberry Pi's drawing). `tail` is how far a header's soldered ends stand out of the far face.
PICO = dict(w=21.0, l=51.0, t=1.0, rows=17.78, holes=(11.4, 47.0), pin1=1.37, tail=2.0)
PFIT = 0.2                           # room round the Pico, each side
WALL = 2.5                           # the tray's walls
SUNK = 1.2                           # the tray's floor, under the rim's top
GROOVE = dict(w=2.8, d=2.4)          # under each row, for the soldered ends
M2 = dict(d=1.7, depth=5.0)          # an M2 screw cuts its thread in this
PX1 = J.XL - J.LATCH["tail"] - J.LATCH["r"] - 3.0    # the tray's pocket's right side: 3 mm clear of a turned latch
PX0 = PX1 - PICO["w"] - 2 * PFIT
PY0 = -J.END                         # the Pico's USB end, level with the cradle's bottom end
PY1 = PY0 + PICO["l"] + PFIT
Z_TRAY = J.LIP - SUNK

ZD = J.ZD
Z_LEDGE = ZD + PROUD - HEADER["short"] - HEADER["body"]     # where the plastic sits
Z_BOT = Z_LEDGE - UNDER


def span(xs):
    """The pocket: its two ends, and its half-width."""
    half = len(PADS) * HEADER["pitch"] / 2 + HFIT
    xc = (xs[PADS[0]] + xs[PADS[-1]]) / 2
    return xc - half, xc + half, HEADER["body"] / 2 + HFIT


def header(xs, yp):
    """The strip on its ribs, its legs up the board: for the pictures."""
    h, p = HEADER["body"] / 2, HEADER["pin"] / 2
    zl = Z_LEDGE - HEADER["drop"]
    s = box(xs[PADS[0]] - HEADER["pitch"] / 2, xs[PADS[-1]] + HEADER["pitch"] / 2, yp - h, yp + h, Z_LEDGE, Z_LEDGE + HEADER["body"])
    for q in PADS:
        s = s.union(box(xs[q] - p, xs[q] + p, yp - p, yp + p, zl - p, ZD + PROUD))
        s = s.union(box(xs[q] - p, xs[q] + p, yp - p, yp + HEADER["reach"], zl - p, zl + p))
    return s


def rows():
    """The two rows' x, the far one first."""
    xc = (PX0 + PX1) / 2
    return xc - PICO["rows"] / 2, xc + PICO["rows"] / 2


def pico():
    """The Pico in its tray, a 3-pin strip on pins 3 to 5, pins up: for the pictures and the checks."""
    x0, x1, y0 = PX0 + PFIT, PX1 - PFIT, PY0
    s = box(x0, x1, y0, y0 + PICO["l"], Z_TRAY, Z_TRAY + PICO["t"])
    s = s.union(box((x0 + x1) / 2 - 4, (x0 + x1) / 2 + 4, y0 - 1.3, y0 + 4.5, Z_TRAY + PICO["t"], Z_TRAY + PICO["t"] + 2.8))   # the USB
    xr, p = rows()[1], HEADER["pin"] / 2
    ya = y0 + PICO["pin1"] + 2 * HEADER["pitch"]             # pin 3
    strip = box(xr - 1.27, xr + 1.27, ya - 1.27, ya + 2 * HEADER["pitch"] + 1.27, Z_TRAY + PICO["t"], Z_TRAY + PICO["t"] + HEADER["body"])
    for i in range(3):
        y = ya + i * HEADER["pitch"]
        strip = strip.union(box(xr - p, xr + p, y - p, y + p, Z_TRAY - PICO["tail"], Z_TRAY + PICO["t"] + HEADER["body"] + 6.0))
    return s, strip


def cradle(xs, yp, j1):
    y_top = yp + TOP
    body = box(-J.RIM, G.W + J.RIM, -J.END, y_top, Z_BOT, J.LIP).edges("|Z").fillet(3.0)
    # the probe's tray, on the left: a pocket open at the USB's end, a groove under each row, four screw holes
    body = body.union(box(PX0 - WALL, -J.RIM + 3.5, -J.END, PY1 + WALL, Z_BOT, J.LIP).edges("|Z").fillet(3.0))
    body = body.cut(box(PX0, PX1, PY0 - 1, PY1, Z_TRAY, J.LIP + 1))
    for xr in rows():
        body = body.cut(box(xr - GROOVE["w"] / 2, xr + GROOVE["w"] / 2, PY0 - 1, PY1, Z_TRAY - GROOVE["d"], Z_TRAY + 1))
    xc, (hx, hy) = (PX0 + PX1) / 2, PICO["holes"]
    for x in (xc - hx / 2, xc + hx / 2):
        for y in (PY0 + (PICO["l"] - hy) / 2, PY0 + (PICO["l"] + hy) / 2):
            body = body.cut(rod(x, y, M2["d"], Z_TRAY - M2["depth"], Z_TRAY + 1))
    body = body.cut(box(xc - 5, xc + 5, PY1 - 1, PY1 + WALL + 1, Z_TRAY - 2.0, J.LIP + 1))      # a notch at the far end, for a nail under the Pico
    # the board's pocket, open at the top end where the board runs on
    pocket = box(-J.FIT, G.W + J.FIT, -J.FIT, y_top + 10, ZD, J.LIP + 1).edges("|Z").fillet(G.CORNER + J.FIT)
    body = body.cut(pocket)
    # the USB-C, as the jig has it: the rim open for the plug, a relief under the shell's legs
    jx0, jx1, jy1 = j1
    body = body.cut(box(jx0 - 3.0, jx1 + 3.0, -J.END - 1, 0.5, ZD - 3.5, J.LIP + 1))
    body = body.cut(box(jx0 - 1.0, jx1 + 1.0, -J.FIT, jy1 + 2.0, ZD - 1.5, ZD + 1))
    # the header: its plastic's pocket down to the ribs, a slot for each leg, and the sockets' channel
    x0, x1, b = span(xs)
    body = body.cut(box(x0, x1, yp - b, yp + b, Z_LEDGE, ZD + 1))
    for p in PADS:
        body = body.cut(box(xs[p] - SLOT / 2, xs[p] + SLOT / 2, yp - SLOT / 2, yp + HEADER["reach"] + 1.0, Z_BOT - 1, ZD + 1))
    body = body.cut(box(x0 - SIDE, x1 + SIDE, yp + START, y_top + 1, Z_BOT - 1, ZD - ROOF))
    body = body.cut(box(x0 - SIDE, x1 + SIDE, yp + HEADER["reach"] + OPEN, y_top + 1, Z_BOT - 1, ZD + 1))
    # the latches' landings and their screws' holes
    for x0, x1, x in ((PX1 + 2.0, -J.FIT, J.XL), (G.W + J.FIT, G.W + J.RIM + 1, J.XR)):
        body = body.cut(box(x0, x1, yp - J.SWING, yp + J.SWING, J.LAND, J.LIP + 1))
        body = body.cut(rod(x, yp, PILOT["d"], J.LAND - PILOT["depth"], J.LAND + 1))
    return body


def main():
    os.makedirs(OUT, exist_ok=True)
    fps = B.footprints()
    xs, yp = J.pads(fps)
    J.checks(fps, xs, yp)
    assert all(abs(xs[b] - xs[a] - HEADER["pitch"]) < 1e-6 for a, b in zip(PADS, PADS[1:])), "the three pads are not 2.54 mm apart"
    assert J.LAND - PILOT["depth"] > Z_BOT + 0.8, "a screw's hole comes through the bottom"
    assert span(xs)[0] > J.FIT + 0.8, "the pocket breaks the board's pocket's wall"
    assert HEADER["pitch"] - SLOT >= 1.2, "a rib between two slots is under 1.2 mm"
    assert START > HEADER["body"] / 2 + HFIT + 0.4, "the channel is under the plastic: nothing holds the strip up"
    zl = Z_LEDGE - HEADER["drop"]
    assert zl + SOCKET / 2 + 0.3 <= ZD - ROOF and zl - SOCKET / 2 - 0.3 >= Z_BOT, "a socket on a leg doesn't fit the channel"
    assert OPEN >= 1.8, "the strip of deck past the slots' ends is under 0.8 mm"
    assert span(xs)[0] - SIDE > J.XL + PILOT["d"] / 2 + 2, "the channel is under a latch's screw"
    assert GROOVE["d"] > PICO["tail"] and Z_TRAY - max(GROOVE["d"], M2["depth"]) > Z_BOT + 2, "the tray's floor"
    body = cradle(xs, yp, J.usbc(fps))
    assert len(body.val().Solids()) == 1, "the cradle is not one solid"
    pcb, bits, glass = B.board(fps), B.parts(fps), B.panel()
    for name, s in (("the board", pcb), ("its parts", bits), ("the glass", glass)):
        assert body.intersect(s).val().Volume() < 1e-6, f"the cradle cuts into {name}"
    shut = J.latch(J.XL, yp).union(J.latch(J.XR, yp, 180))
    wide = J.latch(J.XL, yp, 90).union(J.latch(J.XR, yp, 90))
    probe, strip = pico()
    for name, s in (("the cradle", body), ("the board's parts", bits), ("the Pico", probe.union(strip))):
        assert shut.intersect(s).val().Volume() < 1e-6, f"a shut latch cuts into {name}"
        assert name == "the board's parts" or wide.intersect(s).val().Volume() < 1e-6, f"an open latch cuts into {name}"
    assert body.intersect(probe.union(strip)).val().Volume() < 1e-6, "the Pico doesn't fit its tray"
    assert body.intersect(probe.union(strip).translate((0, 0, 6))).val().Volume() < 1e-6, "something is in the Pico's way in"
    assert probe.union(strip).intersect(pcb).val().Volume() < 1e-6, "the Pico is under the board"
    pins = header(xs, yp)
    assert body.intersect(pins).val().Volume() < 1e-6, "the header doesn't fit its pocket"
    assert body.intersect(pins.translate((0, 0, 8))).val().Volume() < 1e-6, "something is in the header's way in"
    sockets = box(xs[PADS[0]] - 1.27, xs[PADS[-1]] + 1.27, yp + START + 0.2, yp + TOP + 5, zl - SOCKET / 2, zl + SOCKET / 2)
    assert body.intersect(sockets).val().Volume() < 1e-6, "something is in the sockets' way in"

    import cadquery as cq
    cq.exporters.export(body.translate((0, 0, -Z_BOT)), os.path.join(OUT, "mono_cradle.stl"), tolerance=0.01, angularTolerance=0.1)
    orange, dark = (0.95, 0.55, 0.15), (0.1, 0.1, 0.1)
    B.picture([(body, orange), (wide, dark), (pins, dark)], os.path.join(OUT, "mono_cradle_empty.png"), size=1100)
    B.picture([(body, orange), (shut, dark), (probe, (0.1, 0.45, 0.3)), (strip, dark), (pcb, (0.18, 0.42, 0.25)), (bits, (0.75, 0.75, 0.72)), (glass, (0.12, 0.13, 0.16))],
              os.path.join(OUT, "mono_cradle.png"), size=1100)
    turn = lambda s: s.rotate((G.W / 2, 0, 0), (G.W / 2, 1, 0), 180)          # the bottom toward the eye
    B.picture([(turn(body), orange), (turn(pins), dark)], os.path.join(OUT, "mono_cradle_under.png"), size=1100)

    bb = body.val().BoundingBox()
    print(f"wrote {os.path.relpath(OUT, B.REPO)}/: mono_cradle.stl, mono_cradle.png, mono_cradle_empty.png, mono_cradle_under.png; "
          f"{bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm")
    print(f"  the Pico's tray {PX1 - PX0:.1f} x {PY1 - PY0:.1f} mm, its floor {Z_TRAY - Z_BOT:.1f} mm up; "
          f"pins 3 to 5 in the row {J.XL - rows()[1]:.1f} mm left of the left latch's screw")
    x0, x1, b = span(xs)
    print(f"  the pocket {x1 - x0:.2f} x {2 * b:.2f} mm, {ZD - Z_LEDGE:.2f} mm deep, {yp:g} mm up from the bottom edge; pins on "
          + ", ".join(f"{p} {xs[p]:g}" for p in PADS) + " mm from the left edge")
    print(f"  the tips {PROUD} mm over the deck, the latches {J.LAND} mm over the front; the legs' middles "
          f"{zl - Z_BOT:.1f} mm over the table, the channel {ZD - ROOF - Z_BOT:.1f} mm high")
    print(f"  the board stands {J.L - (yp + TOP):.1f} mm out past the top end")


if __name__ == "__main__":
    main()
