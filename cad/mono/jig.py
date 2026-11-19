"""A jig for Mono's nine pads: a block the board drops into, face up, onto nine spring probes (pogo pins)
that stand up out of it, with two turn latches that hold it down and two strips of 2.54 mm header in its
rim for the debug probe and the rest. One jig is one station; print one for each board loaded at a time.

Run: uv run --python 3.11 --with cadquery --with matplotlib python cad/mono/jig.py

Writes out/: mono_jig_base.stl, mono_jig_latch.stl (print two) and mono_jig_gauge.stl, each as it prints,
no support; and mono_jig.png, mono_jig_empty.png and mono_jig_under.png.

How it works:
- The board lies on a flat deck, its back down, in a pocket its own size. Nothing is fitted on the back;
  the USB-C's legs get a relief, and the bottom rim is open for the plug, since the board is powered
  through its own USB-C. The screen and the buttons stay in reach.
- Each probe sits in a receptacle in a bore under its pad, its tip TRAVEL above the deck when free. The
  board pressed to the deck pushes each probe in by that much, whatever the probe's length: the gauge,
  a bar with a groove that deep, sets the receptacles' height before they are glued.
- The latches turn on M3 screws over the board's edges, either end of the pads' row, where the springs
  push. Their landings are LAND over the front, so the board lifts at most that.
- Under the row is a room, open at the bottom, for the receptacles' tails and their wires. It runs up
  under each rim to a header: the plastic sits on a ledge at the rim's top, the long pins up, the wires
  soldered to the short pins and let down a slot. The left header is TP1 to TP5 (SWCLK, GND, SWDIO,
  RUN, 3V3), the right one TP9 to TP6 (GND, D-, D+, BOOT), each from the USB-C's end up.

Read from the routed board: the pads' places, the USB-C's body, and the parts near the latches and on
the back, which the script checks. The probes' and receptacles' sizes are the P75 and R75's as sellers
give them (POGO), not measured: measure yours, and drill the bores to fit.

The model's frame is board.py's: x from the left edge, y up from the bottom edge, the front at z = 0,
the back at z = -T.
"""
import importlib.util
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("board", os.path.join(HERE, "board.py"))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
G, T, OUT = B.G, B.T, B.OUT

LEFT = ("TP1", "TP2", "TP3", "TP4", "TP5")       # SWCLK, GND, SWDIO, RUN, 3V3: the left header, from the USB-C's end up
RIGHT = ("TP9", "TP8", "TP7", "TP6")             # GND, D-, D+, BOOT: the right header, the same way
# A P75 probe in an R75 receptacle: the receptacle 1.32 mm across, sellers' hole for it 1.30 to 1.35. A
# printed hole comes out small, so the bore is drawn 1.5 and drilled to fit. TRAVEL is two thirds of the
# probe's 2.65 mm stroke.
POGO = dict(bore=1.5, travel=1.7, pitch=2.54)
HEADER = dict(pitch=2.54, body=2.54, short=3.0, long=6.0, pin=0.64)     # a breakaway strip, as clip.py's
INSERT = dict(d=4.0, depth=6.5)      # an M3 heat-set insert, 5 mm long: the hole its maker asks for; measure yours
FIT = 0.25                           # room round the board in its pocket, each side
HFIT = 0.15                          # room round a header's plastic, each side
RIM, END = 10.0, 4.0                 # the rim along the long sides, and at the two ends
LIP = 1.0                            # the rim's top, over the board's front
LAND = 0.2                           # the latches' landings, over the front: how far the board can lift
SLAB, ROOM = 10.0, 12.0              # the plastic the bores go through, and the room under it
REACH = 6.0                          # the room, either side of the pads' row
LATCH = dict(r=3.5, arm=4.0, tail=4.5, t=2.4, hole=3.3, over=2.5)       # over: how far it reaches onto the board
SWING = 9.5                          # a landing's half-length: the latch turned a quarter lies inside it
HEADER_Y = 42.0                      # the headers' middle, up from the bottom edge
SLOT = 2.0                           # the slot under a header, for its short pins and the wires

L = G.H - G.TOP                      # the board's length
ZD = -T                              # the deck
Z_ROOF = ZD - SLAB
Z_BOT = Z_ROOF - ROOM
XL, XR = -RIM / 2, G.W + RIM / 2     # the rims' middles: the latches' screws and the headers


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def rod(x, y, d, z0, z1):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def pads(fps):
    """Each pad's x, and the row's y: one row, each group at the probes' pitch."""
    at = {fp["ref"]: B.place(fp, 0, 0) for fp in fps if fp["ref"] in LEFT + RIGHT}
    assert len(at) == 9, "not nine pads"
    ys = [p[1] for p in at.values()]
    assert max(ys) - min(ys) < 1e-6, "the pads are not in one row"
    for group in (LEFT, RIGHT):
        xs = sorted(at[p][0] for p in group)
        assert all(abs(b - a - POGO["pitch"]) < 1e-6 for a, b in zip(xs, xs[1:])), "a group is not 2.54 mm apart"
    return {p: at[p][0] for p in at}, ys[0]


def usbc(fps):
    """The USB-C's body: x0, x1, and how far up the board it reaches."""
    fp = next(f for f in fps if f["ref"] == "J1")
    x0, y0, x1, y1 = fp["body"]
    cs = [B.place(fp, x, y) for x, y in ((x0, y0), (x1, y1))]
    return min(c[0] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs)


def header_span(n):
    return n * HEADER["pitch"] / 2 + HFIT


def base(xs, yp, j1):
    body = box(-RIM, G.W + RIM, -END, L + END, Z_BOT, LIP).edges("|Z").fillet(3.0)
    pocket = box(-FIT, G.W + FIT, -FIT, L + FIT, ZD, LIP + 1).edges("|Z").fillet(G.CORNER + FIT)
    body = body.cut(pocket)
    # the USB-C: the bottom rim open for the plug's moulding, and a relief under the shell's legs
    jx0, jx1, jy1 = j1
    body = body.cut(box(jx0 - 3.0, jx1 + 3.0, -END - 1, 0.5, ZD - 3.5, LIP + 1))
    body = body.cut(box(jx0 - 1.0, jx1 + 1.0, -FIT, jy1 + 2.0, ZD - 1.5, ZD + 1))
    # a notch in the top rim, to get a nail under the board's top edge
    body = body.cut(box(G.W / 2 - 8, G.W / 2 + 8, L - 1.5, L + END + 1, ZD - 6, LIP + 1))
    # the room under the row, and its two arms up under the rims to the headers
    y_arm = HEADER_Y + header_span(len(LEFT)) + 1.0
    body = body.cut(box(XL - 2.5, XR + 2.5, yp - REACH, yp + REACH, Z_BOT - 1, Z_ROOF))
    for x in (XL, XR):
        body = body.cut(box(x - 2.5, x + 2.5, yp - REACH, y_arm, Z_BOT - 1, Z_ROOF))
    for x in xs.values():
        body = body.cut(rod(x, yp, POGO["bore"], Z_ROOF - 1, ZD + 1))
    # the latches' landings and their inserts
    for x0, x1, x in ((-RIM - 1, -FIT, XL), (G.W + FIT, G.W + RIM + 1, XR)):
        body = body.cut(box(x0, x1, yp - SWING, yp + SWING, LAND, LIP + 1))
        body = body.cut(rod(x, yp, INSERT["d"], LAND - INSERT["depth"], LAND + 1))
    # the headers: the plastic's pocket down to a ledge, then the slot to the room
    b = HEADER["body"] / 2 + HFIT
    for x, n in ((XL, len(LEFT)), (XR, len(RIGHT))):
        h = header_span(n)
        body = body.cut(box(x - b, x + b, HEADER_Y - h, HEADER_Y + h, LIP - HEADER["body"], LIP + 1))
        body = body.cut(box(x - SLOT / 2, x + SLOT / 2, HEADER_Y - h, HEADER_Y + h, Z_ROOF - 1, LIP - HEADER["body"] + 1))
    # a dot in the rim beside each header's first pin, the one nearest the USB-C
    for x, n, side in ((XL, len(LEFT), -1), (XR, len(RIGHT), 1)):
        y1 = HEADER_Y - (n - 1) * HEADER["pitch"] / 2
        body = body.cut(rod(x + side * 3.2, y1, 1.6, LIP - 0.6, LIP + 1))
    return body


def latch(x, y, turn=0.0):
    """A latch on its landing at (x, y), its arm toward +x; turn in degrees about its screw."""
    a = LATCH
    s = (cq.Workplane("XY").slot2D(a["arm"] + a["tail"] + 2 * a["r"], 2 * a["r"]).extrude(a["t"])
         .translate(((a["arm"] - a["tail"]) / 2, 0, 0)))
    s = s.cut(rod(0, 0, a["hole"], -1, a["t"] + 1))
    return s.rotate((0, 0, 0), (0, 0, 1), turn).translate((x, y, LAND))


def gauge():
    """A bar that lies on the deck across the row, a groove TRAVEL deep over the probes' tips. Drawn in
    place, on the deck; it prints the groove up."""
    return (box(0.5, G.W - 0.5, -6, 6, 0, 5.0).cut(box(-1, G.W + 1, -2, 2, -1, POGO["travel"])))


def headers(yp):
    """The two strips, seated: for the pictures."""
    out, p = None, HEADER["pin"] / 2
    for x, n in ((XL, len(LEFT)), (XR, len(RIGHT))):
        h = n * HEADER["pitch"] / 2
        s = box(x - 1.27, x + 1.27, HEADER_Y - h, HEADER_Y + h, LIP - HEADER["body"], LIP)
        for i in range(n):
            y = HEADER_Y - h + (i + 0.5) * HEADER["pitch"]
            s = s.union(box(x - p, x + p, y - p, y + p, LIP - HEADER["body"] - HEADER["short"], LIP + HEADER["long"]))
        out = s if out is None else out.union(s)
    return out


def probes(xs, yp, pressed):
    """The probes' tips over the deck, free or with the board on them: for the pictures."""
    top = ZD + (0 if pressed else POGO["travel"])
    out = None
    for x in xs.values():
        s = rod(x, yp, 1.0, ZD - 3, top)
        out = s if out is None else out.union(s)
    return out


def checks(fps, xs, yp):
    """What the drawing takes from the board, checked. -> the parts nearest each latch's tip."""
    # nothing fitted on the back, so the deck can be flat
    back = [fp["ref"] for fp in fps if fp["side"] == "B" and not fp["dnp"] and not fp["ref"].startswith(B.SKIP)]
    assert not back, f"fitted on the back: {back}"
    assert POGO["pitch"] - POGO["bore"] >= 0.9, "the wall between two bores is under 0.9 mm"
    assert all(XL + 2.5 < x < XR - 2.5 for x in xs.values()) and REACH > 2, "a bore misses the room"
    assert LATCH["tail"] + LATCH["r"] <= SWING and LATCH["arm"] + LATCH["r"] <= SWING, "a turned latch leaves its landing"
    assert abs(XL + LATCH["arm"] + LATCH["r"] - LATCH["over"]) < 1e-6, "the latch's reach onto the board"
    assert HEADER_Y - header_span(len(LEFT)) > yp + SWING + 1, "a header is in a landing"
    assert LAND - INSERT["depth"] > Z_ROOF + 2, "an insert's hole comes too near the room"
    # no fitted part on the front under a latch's tip
    near = []
    for fp in fps:
        if fp["side"] != "F" or fp["dnp"] or fp["ref"].startswith(B.SKIP) or not fp["body"]:
            continue
        x0, y0, x1, y1 = fp["body"]
        cs = [B.place(fp, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        ax0, ax1, ay0, ay1 = min(c[0] for c in cs), max(c[0] for c in cs), min(c[1] for c in cs), max(c[1] for c in cs)
        if ay0 < yp + LATCH["r"] and ay1 > yp - LATCH["r"]:
            gap = min(ax0 - LATCH["over"], G.W - LATCH["over"] - ax1)
            near.append((gap, fp["ref"]))
            assert gap > 0.3, f"{fp['ref']} is under a latch"
    return sorted(near)[:3]


def main():
    os.makedirs(OUT, exist_ok=True)
    fps = B.footprints()
    xs, yp = pads(fps)
    near = checks(fps, xs, yp)
    body = base(xs, yp, usbc(fps))
    assert len(body.val().Solids()) == 1, "the base is not one solid"
    pcb, bits, glass = B.board(fps), B.parts(fps), B.panel()
    for name, s in (("the board", pcb), ("its parts", bits), ("the glass", glass)):
        assert body.intersect(s).val().Volume() < 1e-6, f"the base cuts into {name}"
    shut = latch(XL, yp).union(latch(XR, yp, 180))
    wide = latch(XL, yp, 90).union(latch(XR, yp, 90))
    for name, s in (("the base", body), ("the board's parts", bits)):
        assert shut.intersect(s).val().Volume() < 1e-6, f"a shut latch cuts into {name}"
    assert wide.intersect(body).val().Volume() < 1e-6, "an open latch cuts into the base"
    assert wide.intersect(pcb).val().Volume() < 1e-6, "an open latch is still over the board"
    g = gauge().translate((0, yp, ZD))
    assert g.intersect(body).val().Volume() < 1e-6, "the gauge doesn't lie on the deck"

    ex = lambda s, name: cq.exporters.export(s, os.path.join(OUT, name), tolerance=0.01, angularTolerance=0.1)
    ex(body.translate((0, 0, -Z_BOT)), "mono_jig_base.stl")
    ex(latch(0, 0).translate((0, 0, -LAND)), "mono_jig_latch.stl")
    ex(gauge().rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, 5.0)), "mono_jig_gauge.stl")

    orange, dark, steel = (0.95, 0.55, 0.15), (0.1, 0.1, 0.1), (0.8, 0.8, 0.82)
    hd = headers(yp)
    B.picture([(body, orange), (shut, dark), (hd, dark), (pcb, (0.18, 0.42, 0.25)), (bits, (0.75, 0.75, 0.72)),
               (glass, (0.12, 0.13, 0.16))], os.path.join(OUT, "mono_jig.png"), size=1100)
    B.picture([(body, orange), (wide, dark), (hd, dark), (probes(xs, yp, False), steel)],
              os.path.join(OUT, "mono_jig_empty.png"), size=1100)
    turn = lambda s: s.rotate((G.W / 2, 0, 0), (G.W / 2, 1, 0), 180)          # the bottom toward the eye
    B.picture([(turn(body), orange)], os.path.join(OUT, "mono_jig_under.png"), size=1100)

    bb = body.val().BoundingBox()
    print(f"wrote {os.path.relpath(OUT, B.REPO)}/: mono_jig_base.stl, mono_jig_latch.stl, mono_jig_gauge.stl, "
          f"mono_jig.png, mono_jig_empty.png, mono_jig_under.png")
    print(f"  the base {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm; the deck {-Z_BOT + ZD:.1f} mm up, the room under it {ROOM:g} mm")
    print(f"  nine bores, {POGO['bore']} mm as drawn, {yp:g} mm up from the bottom edge: "
          + ", ".join(f"{p} {xs[p]:g}" for p in sorted(xs, key=xs.get)))
    print(f"  the tips {POGO['travel']} mm over the deck when free; the latches {LATCH['over']} mm onto the board, "
          f"{LAND} mm over its front")
    print("  nearest a latch's tip: " + (", ".join(f"{r} {g_:.1f} mm" for g_, r in near) or "nothing in its row"))


if __name__ == "__main__":
    main()
