#!/usr/bin/env python3
"""The cartridge bay: a printed bay that a key-c key plugs into, and that locks it in while the
console is on. hardware/case/README.md says how it works and how to print it.

    pip install cadquery
    python3 hardware/case/cartridge.py        # P3: key half in, pins through the two edge notches
    python3 hardware/case/cartridge.py P2     # bench cradle for P2 (no notches): one pin through H1

Writes <mode>/ next to this file: body, carriage, plate and fit coupon as STL (to print) and STEP
(for CAD), and assembly.step (the body, carriage, pins and dummy key, locked). Before it writes
anything, check() makes sure the parts fit.

Frame: the key's own (key-c-usbc/3d/*.step): origin at the board centre, Z = 0 the key's back face,
USB-C end at -Y, mm, with the key fully seated. The key lies flat; its back face is on the bay's
floor. The lock pins rise up through the board (+Z); switch up is locked and on.
"""
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
KEYPCB = os.path.join(HERE, "..", "key-pcb")
sys.path[:0] = [KEYPCB, os.path.join(KEYPCB, "key-c-usbc", "3d")]
import gen_cd          # noqa: E402  the board's numbers, so the bay can't drift from the key
import print_mockup    # noqa: E402  the printed dummy key, used for the fit checks

MODE = sys.argv[1] if len(sys.argv) > 1 else "P3"
assert MODE in ("P2", "P3"), MODE

# ---- the key (gen_cd.py) -------------------------------------------------------------------------
KEY = gen_cd.BOARDS["key-c-usbc"]
KEY_W, KEY_L, KEY_T = KEY["W"], KEY["L"], 1.6
EDGE_Y = -KEY_L / 2                          # the connector edge, seated
NOTCH_Y = EDGE_Y - gen_cd.NOTCH_Y            # gen_cd's frame runs from the connector edge, into -y
NOTCH_R = gen_cd.NOTCH_R
H1_Y, H1_D = KEY_L / 2 - 4.0, 3.0            # the lanyard hole
SOURCE = gen_cd.SOURCE

# ---- fit ---------------------------------------------------------------------------------------
CLR = 0.2            # per side, between the key and the bay, and a sliding part and its guide
PIN_D = 2.0          # steel dowel pins, 2 mm: 12 mm long for P3, 16 for P2 (whose pin rises higher)
PIN_L = 12.0 if MODE == "P3" else 16.0
PIN_BORE = 2.4       # the pin slides in this
PIN_PRESS = 1.95     # and is pressed into the carriage through this (a printed hole comes out small)

# ---- the bay -----------------------------------------------------------------------------------
LOW_ROOF = KEY_T + 1.75 + 0.45               # over the tallest part beside the receptacle (U1, 1.75)
TUNNEL_W = 11.0                              # over the receptacle: the dummy key's shell is 10.3 wide
TUNNEL_TOP = 5.9                             # the dummy key's shell top is 5.5; the real one 4.9
FLOOR = 2.0                                  # under the key, over the carriage
LEAD_IN = 0.8                                # chamfer at the mouth
PLUG_W, PLUG_ZC, PLUG_H = 12.4, 3.25, 8.0    # the console's USB-C plug breakout, in a pocket behind
BACK_Y = EDGE_Y - 12.0                       # the bay's back face; the pocket runs out through it
STOP_T = 1.0                                 # a lip the key's end edge seats against: 0 leaves only the corners
STOP_WIN = (9.4, 4.0)                        # its window, for the plug's metal shell (8.25 x 2.40)

if MODE == "P3":
    PINS = [(-KEY_W / 2, NOTCH_Y), (KEY_W / 2, NOTCH_Y)]   # one pin in each notch
    LOCK_Y = NOTCH_Y
    MOUTH_Y = 1.0                            # 19 mm of the key in, the lanyard half out
else:
    PINS = [(0.0, H1_Y)]                     # one pin through the lanyard hole
    LOCK_Y = H1_Y
    MOUTH_Y = KEY_L / 2                      # all of it in, flush; finger cut-outs at the mouth


def roof_over(x):
    return TUNNEL_TOP if abs(x) <= TUNNEL_W / 2 else LOW_ROOF


ROOF_AT_PIN = max(roof_over(x) for x, _ in PINS)
PIN_TOP_UP = ROOF_AT_PIN + 1.5               # up: the pin runs on into the roof, held at both ends
PIN_TOP_DOWN = -0.3                          # down: below the floor, so the key slides out
TRAVEL = PIN_TOP_UP - PIN_TOP_DOWN
TOP = max(8.4, PIN_TOP_UP + 0.3 + 1.2)       # the body's top face

# ---- the carriage, under the floor -------------------------------------------------------------
CAR_T = PIN_L - (PIN_TOP_UP + FLOOR)         # pins pressed flush with its underside
assert CAR_T >= 4.0, f"the carriage would be {CAR_T:.1f} mm thick: use longer pins"
CAR_TOP_UP = -FLOOR                          # up: stops against the floor's underside
CAR_C = LOCK_Y - 3.25                        # its centre in y: the pins sit near its front
CAR_X = (-10.5, 10.5)
CAR_Y = (CAR_C - 5.5, CAR_C + 5.5)
CH_X = (CAR_X[0] - CLR, CAR_X[1] + CLR)      # its chamber
CH_Y = (CAR_Y[0] - CLR, CAR_Y[1] + CLR)
CH_BOT = CAR_TOP_UP - TRAVEL - CAR_T         # the plate's top face: the carriage rests on it, down
PLATE_T = 2.5

# ---- the detent: a beam across the carriage's back face, its bump clicks into two grooves -------
BEAM_T, BEAM_L, BEAM_SLOT = 0.8, 16.0, 1.0
BUMP_R, BUMP_L = 0.45, 3.0                   # proud of the beam by BUMP_R: CLR clearance, the rest flexes

# ---- the power switch: a D2F-size microswitch, plunger down, over a tab on the carriage ---------
SW_L, SW_W, SW_H = 12.8, 5.8, 6.5            # body, without the plunger
SW_AT_OP = 0.7                               # plunger below the body face at its operating point
SW_OT = 0.5                                  # its rated overtravel past that
SW_LAST = 0.4                                # it operates this far before the carriage is fully up
SW_X = (-17.2, -11.4)
SW_Y = CAR_C - 1.0
SW_FACE = CAR_TOP_UP - SW_LAST + SW_AT_OP    # where the switch's plunger face sits
TAB_W = 6.0                                  # the tab runs the carriage's full height

# ---- the lever, out through the +X wall ---------------------------------------------------------
# The tab, arm and knob all start at the carriage's underside, so it prints flat with no supports.
ARM_W, ARM_T = 5.0, 3.0
KNOB = (6.0, 7.0, 8.0)                       # x, y, z

BODY_X = (SW_X[0] - 1.8, CH_X[1] + 1.75)
BODY_Y = (BACK_Y, MOUTH_Y)
SCREWS = [(-16.5, BACK_Y + 3.0), (10.0, BACK_Y + 3.0), (-16.5, CH_Y[0] - 3.0), (10.0, CH_Y[0] - 3.0)]

TEXT_H, TEXT_DEPTH = 2.8, 0.6
TEXT = ["PicoQuorum"] + SOURCE[1:] + SOURCE[:1]   # name, source location, licence


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl(x, y, z0, z1, d):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(d / 2).extrude(z1 - z0)


def channel():
    """The space the key slides in, from the mouth to the stop at its connector edge."""
    h = KEY_W / 2 + CLR
    c = box(-h, h, EDGE_Y, MOUTH_Y + 1, 0, LOW_ROOF)
    c = c.union(box(-TUNNEL_W / 2, TUNNEL_W / 2, EDGE_Y, MOUTH_Y + 1, 0, TUNNEL_TOP))
    lead = (cq.Workplane("XZ", origin=(0, MOUTH_Y, 0)).center(0, TUNNEL_TOP / 2)
            .rect(2 * (h + LEAD_IN), TUNNEL_TOP + 2 * LEAD_IN)
            .workplane(offset=LEAD_IN).rect(2 * h, TUNNEL_TOP).loft())
    return c.union(lead)


def body():
    b = box(*BODY_X, *BODY_Y, CH_BOT, TOP)
    b = b.cut(channel())
    b = b.cut(box(-PLUG_W / 2, PLUG_W / 2, BACK_Y - 1, EDGE_Y - STOP_T + 0.01, PLUG_ZC - PLUG_H / 2, PLUG_ZC + PLUG_H / 2))
    b = b.cut(box(-STOP_WIN[0] / 2, STOP_WIN[0] / 2, EDGE_Y - STOP_T - 0.01, EDGE_Y + 0.01,
                  PLUG_ZC - STOP_WIN[1] / 2, PLUG_ZC + STOP_WIN[1] / 2))
    b = b.cut(box(*CH_X, *CH_Y, CH_BOT - 1, CAR_TOP_UP))                              # the chamber
    for x, y in PINS:                                                                   # pin bores
        b = b.cut(cyl(x, y, CAR_TOP_UP - 0.1, PIN_TOP_UP + 0.3, PIN_BORE))
    # the switch tab's slot, and the switch pocket over it, open at the top for the switch and wires
    b = b.cut(box(SW_X[0] + 0.2, CH_X[0] + 0.1, SW_Y - TAB_W / 2 - CLR, SW_Y + TAB_W / 2 + CLR, CH_BOT - 1, SW_FACE))
    b = b.cut(box(SW_X[0] - CLR, SW_X[1] + CLR, SW_Y - SW_L / 2 - CLR, SW_Y + SW_L / 2 + CLR, SW_FACE, TOP + 1))
    # the lever's slot, open at the bottom so the carriage goes in from below
    ac = CAR_C
    b = b.cut(box(CH_X[1] - 0.1, BODY_X[1] + 1, ac - ARM_W / 2 - 0.3, ac + ARM_W / 2 + 0.3, CH_BOT - 1,
                  CAR_TOP_UP - CAR_T + ARM_T + 0.3))
    # detent grooves in the chamber's back wall, at the bump's height up and down
    for up in (True, False):
        b = b.cut(cq.Workplane("YZ").workplane(offset=-BUMP_L / 2 - 0.5).center(CH_Y[0], car_mid(up))
                  .circle(BUMP_R + 0.1).extrude(BUMP_L + 1))
    for x, y in SCREWS:
        b = b.cut(cyl(x, y, CH_BOT - 1, CH_BOT + 6, 1.7))
    if MODE == "P2":   # finger cut-outs at the mouth, to pinch the key's edges
        x0, x1 = TUNNEL_W / 2 + 0.6, KEY_W / 2 + CLR + 3.0
        for s in (-1, 1):
            b = b.cut(box(min(s * x0, s * x1), max(s * x0, s * x1), MOUTH_Y - 6, MOUTH_Y + 1, 0, TOP + 1))
    return b


def car_mid(up):
    top = CAR_TOP_UP if up else CAR_TOP_UP - TRAVEL
    return top - CAR_T / 2


def carriage(up=True):
    dz = 0 if up else -TRAVEL
    top = CAR_TOP_UP
    c = box(*CAR_X, *CAR_Y, top - CAR_T, top)
    mid = top - CAR_T / 2
    bot = top - CAR_T
    c = c.union(box(SW_X[0] + 0.2 + CLR, CAR_X[0] + 0.01, SW_Y - TAB_W / 2, SW_Y + TAB_W / 2, bot, top))
    ac = CAR_C
    c = c.union(box(CAR_X[1] - 0.01, BODY_X[1] + 1.0, ac - ARM_W / 2, ac + ARM_W / 2, bot, bot + ARM_T))
    kx = BODY_X[1] + 1.0
    c = c.union(box(kx, kx + KNOB[0], ac - KNOB[1] / 2, ac + KNOB[1] / 2, bot, bot + KNOB[2]))
    for x, y in PINS:
        c = c.cut(cyl(x, y, top - CAR_T - 1, top + 1, PIN_PRESS))
    # the detent beam: a slot through the carriage leaves a thin beam on its back face, with a bump
    y0 = CAR_Y[0]
    c = c.cut(box(-BEAM_L / 2, BEAM_L / 2, y0 + BEAM_T, y0 + BEAM_T + BEAM_SLOT, top - CAR_T - 1, top + 1))
    c = c.union(cq.Workplane("YZ").workplane(offset=-BUMP_L / 2).center(y0 + 0.01, mid)
                .circle(BUMP_R).extrude(BUMP_L).cut(box(-5, 5, y0, y0 + 2, mid - 2, mid + 2)))
    return c.translate((0, 0, dz))


def pins(up=True):
    top = PIN_TOP_UP if up else PIN_TOP_DOWN
    out = None
    for x, y in PINS:
        p = cyl(x, y, top - PIN_L, top, PIN_D)
        out = p if out is None else out.union(p)
    return out


def plate():
    p = box(*BODY_X, *BODY_Y, CH_BOT - PLATE_T, CH_BOT)
    for x, y in SCREWS:
        p = p.cut(cyl(x, y, CH_BOT - PLATE_T - 1, CH_BOT + 1, 2.3))
    # the licence notice, pressed into the underside (hardware/README.md#license)
    cx = (BODY_X[0] + BODY_X[1]) / 2
    cy = (SCREWS[0][1] + SCREWS[2][1]) / 2   # the longest line goes here, midway between the screws
    wide = TEXT.index(max(TEXT, key=len))
    for i, line in enumerate(TEXT):
        y = cy - (i - wide) * TEXT_H * 1.45     # first line nearest the mouth
        # facing down, and upright to someone holding the bay upside down with its mouth away from them
        t = (cq.Workplane("XY", origin=(0, 0, CH_BOT - PLATE_T)).transformed(rotate=(0, 180, 0))
             .center(-cx, y).text(line, TEXT_H, -TEXT_DEPTH, combine=False, kind="bold",
                                       halign="center", valign="center"))
        bb = t.val().BoundingBox()
        assert (bb.xmin > BODY_X[0] + 1 and bb.xmax < BODY_X[1] - 1 and
                bb.ymin > BODY_Y[0] + 1 and bb.ymax < BODY_Y[1] - 1), f"{line!r} runs off the plate"
        for sx, sy in SCREWS:   # clear of the screw heads (about 4 mm across)
            assert (bb.xmax < sx - 2.5 or bb.xmin > sx + 2.5 or bb.ymax < sy - 2.5 or bb.ymin > sy + 2.5), \
                f"{line!r} runs into the screw at {sx, sy}"
        p = p.cut(t)
    return p


def coupon():
    """A slice of the bay round the pins, to try the clearances before the whole body."""
    h = KEY_W / 2 + CLR + 2.3
    return body().intersect(box(-h, h, LOCK_Y - 4.5, MOUTH_Y if MODE == "P3" else LOCK_Y + 3.5,
                                -FLOOR, TOP))


def key():
    return print_mockup.mockup(MODE)


def vol(a, b):
    try:
        return a.intersect(b).val().Volume()
    except Exception:
        return 0.0


def one_solid(name, w):
    s = w.solids().vals()
    assert len(s) == 1 and s[0].isValid(), f"{name}: {len(s)} solids"


def check(parts):
    """The fit, in numbers. Each assertion says what it guards."""
    eps = 1e-3
    for name, w in parts.items():
        one_solid(name, w)
    b, k = parts["body"], key()
    pull = k.translate((0, 2.0, 0))           # the key, pulled 2 mm towards the mouth
    for up in (True, False):
        c, p = carriage(up), pins(up)
        st = "up" if up else "down"
        assert vol(b, c) < eps, f"carriage {st} hits the body"
        assert vol(b, p) < eps, f"pins {st} hit the body"
        assert vol(k, p) < eps, f"pins {st} hit the seated key"
        assert vol(parts["plate"], c) < eps, f"carriage {st} hits the plate"
    assert vol(b, k) < eps, "the seated key hits the body"
    assert vol(pull, pins(True)) > 0.1, "up, the pins don't stop the key"
    assert vol(pull, pins(False)) < eps, "down, the pins still catch the key"
    assert PIN_TOP_DOWN < 0, "down, the pins must be under the floor"
    # power: the switch operates SW_LAST before the top, with the pins well through the board
    assert SW_LAST < SW_OT, "the carriage would push the plunger past its rated overtravel"
    assert SW_LAST < SW_AT_OP, "the tab would hit the switch body"
    pin_top_at_op = PIN_TOP_UP - SW_LAST
    assert pin_top_at_op > KEY_T + 1.0, "power would come on before the pins cross the board"
    print(f"  checks pass: pins lock up and clear down; the switch operates with the pin tops at "
          f"{pin_top_at_op:.1f} mm, {pin_top_at_op - KEY_T:.1f} above the board's top face")


def main():
    out = os.path.join(HERE, MODE.lower())
    os.makedirs(out, exist_ok=True)
    parts = {"body": body(), "carriage": carriage(True), "plate": plate(), "coupon": coupon()}
    check(parts)
    for name, w in parts.items():   # in the bay's frame: the slicer lays each one flat
        cq.exporters.export(w, os.path.join(out, f"{name}.step"), opt={"write_pcurves": False})
        # STL to 0.02 mm, finer than a printer resolves
        cq.exporters.export(w, os.path.join(out, f"{name}.stl"), tolerance=0.02, angularTolerance=0.2)
        bb = w.val().BoundingBox()
        print(f"  {name:<9} {bb.xlen:5.1f} x {bb.ylen:5.1f} x {bb.zlen:5.1f} mm")
    asm = cq.Assembly(name=f"cartridge-{MODE}")
    asm.add(parts["body"], name="body", color=cq.Color(0.85, 0.85, 0.85, 0.5))
    asm.add(parts["carriage"], name="carriage-up", color=cq.Color(0.2, 0.5, 0.9))
    asm.add(pins(True), name="pins-up", color=cq.Color(0.5, 0.5, 0.55))
    asm.add(key(), name=f"key-c-{MODE}", color=cq.Color(0.1, 0.3, 0.8))
    asm.export(os.path.join(out, "assembly.step"))
    print(f"  travel {TRAVEL:.1f} mm, {out}")


if __name__ == "__main__":
    main()
