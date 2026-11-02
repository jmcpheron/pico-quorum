"""pico-sign-handheld: the pictures for ASSEMBLY.md, drawn the way flat-pack instructions are. Each step's new
printed parts in amber, what's already done in white, the hardware in its own colours, black outlines, arrows
for where things go, and what the step needs along the bottom.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign-handheld/case/assembly.py
(or tools/case build handheld)

Writes out/assembly/*.png. The parts come from handheld.py and cartridge.py, so the pictures follow their
numbers. The drawing (the z-buffer, the outlines, the labels, the hardware's shapes) is pico-sign's
case/assembly.py, loaded from there.
"""
import importlib.util
import math
import os
import sys

import numpy as np
import cadquery as cq
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handheld as H
import cartridge as C

_spec = importlib.util.spec_from_file_location(
    "prism_assembly", os.path.join(HERE, "..", "..", "pico-sign", "case", "assembly.py"))
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
A.BENCH = np.diag([1.0, -1.0, -1.0])        # bench=True: the plate face down, turned over its x axis

OUT = os.path.join(H.OUT, "assembly")
WHITE, NEW, BRASS, STEEL, DARK, BLACK = A.WHITE, A.NEW, A.BRASS, A.STEEL, A.DARK, A.BLACK
GLASS, BLUE, GREEN, RED, INK = A.GLASS, A.BLUE, A.GREEN, (0.80, 0.18, 0.15), A.INK
Shot, font, wp = A.Shot, A.font, A.wp
M3I, M3S, M2S, CSK, WASHER, IRON3 = A.M3I, A.M3S, A.M2S, A.CSK, A.WASHER, A.IRON3
FOOT = cq.Workplane("XY").slot2D(H.FOOT[1], H.FOOT[0], 90).extrude(2.5).edges(">Z").fillet(1.0)
UP = np.array([0, 0, 1.0])
ZPOST = H.ZP - H.PLATE_BOSS                 # the tub's corner posts' tops, under the plate's bosses
BB = H.SIGN_MOUNT == "breadboard"           # the sign button's switch in a mini breadboard in the tub, or a holder


def at(shape, x, y, z, flip=False):
    """A part made along +z put at (x, y, z), its +z up (flip: down)."""
    n = (0, 0, -1) if flip else (0, 0, 1)
    pl = cq.Plane(origin=(x, y, z), xDir=(1, 0, 0), normal=n)
    return wp(*[s.moved(cq.Location(pl)) for s in shape.vals()])


def pressed(x, y, entry, down, lift, tool=False):
    """An M3 insert lift mm out of its hole, which opens at z = entry and runs down (down) or up; the iron on it."""
    if down:
        base = entry - 6 + lift
        out = [(at(M3I, x, y, base), BRASS)]
        if tool:
            out += [(at(IRON3[0], x, y, base + 6), STEEL), (at(IRON3[1], x, y, base + 6), RED)]
    else:
        base = entry + 6 - lift
        out = [(at(M3I, x, y, base, True), BRASS)]
        if tool:
            out += [(at(IRON3[0], x, y, base - 6, True), STEEL), (at(IRON3[1], x, y, base - 6, True), RED)]
    return out


def items(parts, move=(0, 0, 0)):
    return [(s, c, np.array(move, float)) for s, c in parts]


def icon(parts, az=-55, el=30, size=170):
    return Shot(items(parts), az, el, (size, size), pad=0.14).img


def ctr(shape):
    return np.array(shape.val().Center().toTuple())


def page(name, n, title, panels, need=(), note=None):
    """A step: its number and title over its pictures side by side, what it needs under them."""
    rows = panels if isinstance(panels[0], list) else [panels]
    w = max(sum(p.width for p in r) for r in rows)
    head, foot = 120, (250 if need else 0) + (70 * len(note.split("\n")) if note else 0)
    h = sum(max(p.height for p in r) for r in rows)
    im = Image.new("RGB", (max(w, 1650), head + h + foot), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.text((40, 18), str(n) if n is not None else "", font=font(80), fill=INK)
    d.text((160 if n is not None else 40, 44), title, font=font(40), fill=INK)
    y = head
    for r in rows:
        x, rh = 0, max(p.height for p in r)
        for i, p in enumerate(r):
            im.paste(p, (x, y))
            if i:
                d.line([(x, y + 20), (x, y + rh - 20)], fill=(200, 200, 205), width=2)
            x += p.width
        y += rh
    if note:
        for line in note.split("\n"):
            d.text((40, y + 16), line, font=font(30), fill=INK)
            y += 50
        y += 20
    if need:
        d.line([(30, y + 6), (im.width - 30, y + 6)], fill=(200, 200, 205), width=2)
        x = 40
        for ic, count, text in need:
            im.paste(ic, (x, y + 22))
            d.text((x + ic.width + 8, y + 70), A.txt(count), font=font(46), fill=INK)
            d.text((x + 4, y + 22 + ic.height), A.txt(text), font=font(22), fill=INK)
            x += ic.width + 150
    name = "%02d-%s" % (n or 0, name)
    im.save(os.path.join(OUT, name + ".png"), optimize=True)
    print("wrote", os.path.join("hardware/builds/pico-sign-handheld/case/out/assembly", name + ".png"))


# --- the parts, placed where they go ---------------------------------------------------------------------------
def build():
    g = {}
    g["body"], g["plate"] = H.tub_and_plate()
    g["carrier"], _ = H.carrier_and_spacers()
    g["lock"] = H.plug_lock()
    g["base"], g["cover"], g["cap"] = H.guard_base(), H.guard_cover(), H.sign_cap()
    g["holder"] = None if BB else H.tact_holder()
    si = {n: sh for sh, _, n in H.stand_ins()}
    g["spacers"] = [H.zp(H.Z_BOARD - H.SCREEN_PCB_T).center(*c).circle(H.SPACER_D / 2).circle(H.PIN_HOLE / 2)
                    .extrude(-H.SPACER) for c in H.screen_holes()]
    sx, sy = H.SCREEN_XY
    zb = H.Z_BOARD - H.SCREEN_PCB_T
    hdr = cq.Workplane("XY").box(2.5, 20.3, 2.5, centered=(True, True, False))
    pins = wp(*[cq.Workplane("XY").box(0.64, 0.64, 6, centered=(True, True, False)).translate((0, (i - 3.5) * 2.54, 2.5))
                for i in range(8)])
    g["screen"] = [(si["screen glass"], GLASS), (si["screen board"], BLUE),
                   (at(hdr, H.HEADER_X, sy, zb, True), BLACK), (at(pins, H.HEADER_X, sy, zb, True), BRASS)]
    # the knob: the EC11 from behind, its nut on the well's floor, its cap
    kx, ky = H.KNOB_XY
    kfloor = H.T - H.KNOB_WELL[1]
    kback = kfloor - H.KNOB_FLOOR
    g["ec11"] = [(H.zp(kback).center(kx, ky).rect(12, 12).extrude(-6.5), DARK),
                 (H.zp(kback).center(kx, ky).circle(3.5).extrude(H.KNOB_FLOOR + 5), STEEL),
                 (H.zp(kfloor + 5).center(kx, ky).circle(3).extrude(10), STEEL)]
    g["ec11 nut"] = [(H.zp(kfloor).center(kx, ky).polygon(6, 11).circle(3.6).extrude(2), STEEL)]
    g["knob"] = [(si["knob"], BLACK), (si["knob mark"], WHITE)]
    # the sign button: the guard, its pin, the cap; the tactile switch and its two wires
    x0, x1, _, _ = H.guard_box()
    yh, zh = H.hinge()
    g["pin"] = [(cq.Workplane("YZ").center(yh, zh).circle(H.PIN_D / 2).extrude(x1 - x0).translate((x0, 0, 0)), WHITE)]
    g["tact"] = [(si["tact switch"], DARK)]
    tx, ty = H.SIGN_XY
    if BB:      # two flat jumpers on the board, from the rows of two diagonal legs, out to the left
        lx = tx - 2 * H.BB_PITCH
        g["breadboard"] = [(si["breadboard"], (0.95, 0.95, 0.97))]
        g["tact wires"] = [(cq.Workplane("YZ").center(ty + s * 3.5 * H.BB_PITCH, H.Z_TACT + 0.5).circle(0.6).extrude(-30)
                            .translate((lx + (2 * H.BB_PITCH if s > 0 else 0), 0, 0)), (0.82, 0.20, 0.18) if s > 0 else BLACK)
                           for s in (-1, 1)]
    else:
        g["breadboard"] = []
        g["tact wires"] = [(cq.Workplane("YZ").center(ty + s * 2.25, H.Z_TACT + 0.3).circle(0.6).extrude(30 * s)
                            .translate((tx + s * H.TACT[4] / 2, 0, 0)), (0.82, 0.20, 0.18) if s > 0 else BLACK)
                           for s in (-1, 1)]       # on two diagonal legs, out of the pocket's ends
    seat = max(H.Z_FLOOR_TOP - 0.5 - H.M2_SCREW, H.Z_TACT - H.HOLDER[2])
    g["base screws"] = [(at(M2S, x, y, H.Z_BASE_TOP), DARK) for x, y in H.BASE_SCREWS]
    g["holder screws"] = [] if BB else [(at(M2S, x, y, seat, True), DARK) for x, y in H.HOLDER_SCREWS]
    # the Pico, its parts and USB socket up toward the carrier, its USB end to the right
    zt = H.Z_PICO
    px0 = H.PICO_X1 - H.PICO[0]
    pb = H.box(px0, H.PICO_X1, H.PICO_Y - H.PICO[1] / 2, H.PICO_Y + H.PICO[1] / 2, zt - H.PICO[2], zt)
    for x, y, _ in H.pico_posts():
        pb = pb.cut(H.zp(zt - 2).center(x, y).circle(1.05).extrude(4))
    sw, sl, sh = H.USB_SOCKET
    g["pico"] = [(pb, GREEN), (H.box(H.PICO_X1 - sl, H.PICO_X1, H.PICO_Y - sw / 2, H.PICO_Y + sw / 2, zt, zt + sh), STEEL),
                 (H.box(px0 + 22, px0 + 29, H.PICO_Y - 3.5, H.PICO_Y + 3.5, zt, zt + 0.9), BLACK),
                 (H.box(px0 + 4, px0 + 14, H.PICO_Y - 5, H.PICO_Y + 5, zt, zt + 1.6), STEEL)]
    g["pico screws"] = [(at(M2S, x, y, zt - H.PICO[2], True), DARK) for x, y, _ in H.pico_posts()]
    pl, pw_, pt = H.USB_PLUG[:3]
    g["usb cable"] = [(H.box(H.PICO_X1, H.PICO_X1 + 18, H.PICO_Y - pw_ / 2, H.PICO_Y + pw_ / 2, H.PLUG_Z - pt / 2, H.PLUG_Z + pt / 2), BLACK),
                      (cq.Workplane("YZ").center(H.PICO_Y, H.PLUG_Z).circle(1.75).extrude(40).translate((H.PICO_X1 + 18, 0, 0)), BLACK)]
    # the key's plug and its cable; the key in its clamshell
    g["plug"] = [(si["plug overmold"], BLACK), (si["plug shell"], STEEL),
                 (cq.Workplane("XZ").center(H.KEY_X, H.KEY_Z).circle(2).extrude(30).translate((0, H.H - H.PLUG_L, 0)), BLACK)]
    g["key"] = [(si["cartridge cover"], NEW), (si["cartridge tray"], (0.86, 0.60, 0.25)), (si["ATECC608"], BLACK)]
    # the hardware in place
    g["body inserts"] = [it for x, y in H.SCREWS for it in pressed(x, y, ZPOST, True, 0)]
    g["boss inserts"] = [it for c in H.carrier_screws() for it in pressed(*c, H.Z_CARRIER, False, 0)]
    wc = H.Z_CARRIER_BACK
    g["carrier screws"] = [it for c in H.carrier_screws() for it in
                           ((at(WASHER, *c, wc, True), STEEL), (at(M3S, *c, wc - 0.5, True), DARK))]
    g["plate screws"] = [(at(M3S, x, y, H.T - H.CBORE[1]), DARK) for x, y in H.SCREWS]     # heads in their counterbores
    fl = H.FOOT[1] + 2 * H.FOOT_CLEAR
    g["feet"] = [(FOOT.translate((x, y, -1.5)), BLACK) for x in (H.FOOT_X, H.W - H.FOOT_X)
                 for y in (H.FOOT_END + fl / 2, H.H - H.FOOT_END - fl / 2)]
    return g


# --- the steps ------------------------------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):           # a step taken out leaves no picture behind
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    g = build()
    body, plate, carrier, lock = g["body"], g["plate"], g["carrier"], g["lock"]
    base, cover, cap, holder = g["base"], g["cover"], g["cap"], g["holder"]
    ic = dict(m3i=icon([(M3I, BRASS)]), m3s=icon([(M3S, DARK)], el=15), m2s=icon([(M2S, DARK)], el=15),
              washer=icon([(WASHER, STEEL)], el=45), foot=icon([(FOOT, BLACK)], el=40),
              iron=icon([(IRON3[0], STEEL), (IRON3[1], RED)], el=10), pin=icon(g["pin"], el=30))
    sx, sy = H.SCREEN_XY
    tx, ty = H.SIGN_XY
    kx, ky = H.KNOB_XY
    p = lambda x, y, z: np.array((x, y, z), float)
    N = iter(range(1, 100))             # the steps' numbers, in the order they're drawn

    # 0. the parts
    ct, cb, _, _ = C.clamshell()
    tiles = [("1 tub: handheld_body.stl", [(body, NEW)], -60, 35), ("1 plate: handheld_plate.stl", [(plate, NEW)], -80, 50),
             ("1 carrier:\nhandheld_carrier.stl", [(carrier, NEW)], 120, -40),
             ("4 spacers: handheld_spacers.stl", [(g["spacers"][0], NEW)], -55, 35),
             ("1 plug lock:\nhandheld_plug_lock.stl", [(lock, NEW)], -60, 35),
             ("1 guard base:\nhandheld_guard_base.stl", [(base, NEW)], -60, 40),
             ("1 guard cover:\nhandheld_guard_cover.stl", [(cover, NEW)], -60, 40),
             ("1 button cap:\nhandheld_sign_cap.stl", [(cap, NEW)], -60, 20),
] + ([] if BB else [("1 switch holder:\nhandheld_tact_holder.stl", [(holder, NEW)], -60, 45)]) + [
             ("1 key tray + 1 key cover:\ncartridge_tray.stl, cartridge_cover.stl",
              [(cb, NEW), (wp(*[s.moved(cq.Location(cq.Vector(30, 0, 0))) for s in ct.vals()]), NEW)], -60, 45)]
    shots = []
    for name, parts, az, el in tiles:
        s = Shot(items(parts), az, el, (825, 560) if len(shots) < 2 else (412, 400), pad=0.16)
        s.d.multiline_text((20, 14), name, font=font(24 if len(shots) < 2 else 19), fill=INK, spacing=5)
        shots.append(s.img)
    page("printed-parts", None, "The printed parts", [shots[:2], shots[2:6], shots[6:]])
    hw = [(ic["m3i"], "8×", "M3 insert, M3*6*5"), (ic["m3s"], "8×", "M3 × 8 socket head"), (ic["washer"], "4×", "M3 washer"),
          (ic["m2s"], "%d×" % (4 + 2 + len(g["holder screws"])), "M2 × 8 socket head"), (ic["foot"], "4×", "rubber strip"), (ic["pin"], "20 mm", "1.75 mm filament")]
    page("hardware", None, "The hardware", [Image.new("RGB", (1650, 10), (255, 255, 255))], need=hw)

    # the exploded view: the tub at the bottom, the plate high over it, its stack spread down from it
    G = 150.0
    done_plate = [(plate, WHITE)] + g["boss inserts"]
    ex = items([(body, WHITE)] + g["body inserts"] + g["plug"] + [(lock, WHITE)]) + items(g["feet"], move=(0, 0, -20))
    ex += items(g["key"], move=(0, 40, 0))
    ex += items(done_plate + [(base, WHITE), (cover, WHITE), (cap, WHITE)] + g["ec11"] + g["ec11 nut"] + g["base screws"],
                move=(0, 0, G))
    ex += items(g["knob"], move=(0, 0, G + 25)) + items(g["plate screws"], move=(0, 0, G + 18))
    B = dict(screen=-18, spacers=-34, carrier=-50, screws=-64, pico=-80, pico_screws=-96, holder=-40)
    ex += items(g["screen"], move=(0, 0, G + B["screen"])) + items([(x, NEW) for x in g["spacers"]], move=(0, 0, G + B["spacers"]))
    ex += items([(carrier, NEW)], move=(0, 0, G + B["carrier"])) + items(g["carrier screws"], move=(0, 0, G + B["screws"]))
    ex += items(g["pico"], move=(0, 0, G + B["pico"])) + items(g["pico screws"], move=(0, 0, G + B["pico_screws"]))
    if BB:
        ex += items(g["breadboard"] + g["tact"])
    else:
        ex += items(g["tact"] + [(holder, NEW)] + g["holder screws"], move=(0, 0, G + B["holder"]))
    s = Shot(ex, -55, 20, (1650, 1500), pad=0.04)
    for q, t, dx, dy in [(p(70, 20, 15), "tub", 220, -30), (p(10, 60, H.T + G), "plate", -90, -40),
                         (p(sx + 25, sy + 20, H.Z_BOARD + G + B["screen"]), "screen", 190, -40),
                         (p(*H.screen_holes()[3], H.Z_BOARD - 3 + G + B["spacers"]), "spacers", 200, 0),
                         (p(sx - 25, sy - 20, H.Z_CARRIER + G + B["carrier"]), "carrier", -200, 30),
                         (p(H.PICO_X1 - 30, H.PICO_Y, H.Z_PICO + G + B["pico"]), "Pico 2 W", 200, 60),
                         ((p(H.bb_box()[0] + 6, ty - 10, H.Z_TACT) if BB else p(tx + 10, ty, H.Z_HOLDER + G + B["holder"])),
                          "breadboard\nand switch" if BB else "switch\nin its holder", -230 if BB else 230, 30),
                         (p(tx, ty, H.T + G), "button\nand cover", 160, -120),
                         (ctr(g["key"][0][0]) + (0, 40, 0), "key", 120, -30), (ctr(g["feet"][0][0]) + (0, 0, -20), "feet", -160, 40)]:
        s.label(q, t, dx, dy)
    page("exploded", None, "Everything, pulled apart", [s.img])

    # 1. the tub's inserts
    ov = Shot(items([(body, WHITE)]) + items([it for x, y in H.SCREWS for it in pressed(x, y, ZPOST, True, 20)]),
              -60, 40, (900, 900), pad=0.06)
    for x, y in H.SCREWS:
        ov.arrow(p(x, y, ZPOST + 18), p(x, y, ZPOST + 2))
    x, y = H.SCREWS[2]
    blk = body.intersect(H.box(x - 14, x + 18, y - 18, y + 14, 0, ZPOST + 1))
    fit = [p(x + dx, y + dy, z) for dx in (-12, 14) for dy in (-14, 12) for z in (ZPOST - 16, ZPOST + 28)]
    a = Shot(items([(blk, WHITE)] + pressed(x, y, ZPOST, True, 5, True)), -50, 25, (750, 900), fit=fit)
    a.arrow(p(x + 10, y, ZPOST + 24), p(x + 10, y, ZPOST + 8))
    a.label(p(x, y, ZPOST + 18), "hot iron:\npress straight,\nno twisting", 190, -100, 24)
    page("tub-inserts", next(N), "The tub: an insert in each corner post", [ov.img, a.img],
         need=[(ic["m3i"], "4×", "M3 insert"), (ic["iron"], "", "soldering iron, insert tip")],
         note="Stop when each insert is flush with its post's top. The holes are 4.2 mm, not tried yet: try one first.")

    # 2. the feet
    s = Shot(items([(body, WHITE)] + g["body inserts"]) + items(g["feet"], move=(0, 0, -22)), -60, -45, (1650, 950))
    for sh, _ in g["feet"]:
        c = ctr(sh)
        s.arrow(c + (0, 0, -19), c + (0, 0, -3))
    page("feet", next(N), "The tub: the rubber strips into their pockets", [s.img], need=[(ic["foot"], "4×", "rubber strip, 6 × 35")],
         note="Peel each strip and press it into its pocket, round ends to the round ends.")

    # 3. the key's plug and its lock
    hold = body.intersect(H.box(H.KEY_X - 18, H.KEY_X + 18, H.Y_STOP - 14, H.H + 8, 0, 24))
    fit = [p(H.KEY_X + dx, H.H + dy, dz) for dx in (-18, 18) for dy in (-34, 8) for dz in (0, 32)]
    low, up = np.array((0, -H.LIFT, 0)), np.array((0, 0, 16))
    mid = p(H.KEY_X, H.H - H.PLUG_L / 2, H.KEY_Z)
    panels = []
    for plug_mv, lock_mv, arr, text in [
            (low + up, None, (mid + low + up + (0, 0, 4), mid + low + (0, 0, 6)), "1  drop it in low,\n   its cable down the slot"),
            (low, None, (mid + low + (0, 0, 8), mid + (0, 0, 8)), "2  push it up, the shell\n   through the top, flush"),
            (np.zeros(3), up, (mid + (0, -H.PLUG_L / 2 - 4, 26), mid + (0, -H.PLUG_L / 2 - 4, 12)),
             "3  press the lock in under it\n   until it clicks")]:
        its = items([(hold, WHITE)]) + items(g["plug"], move=plug_mv)
        if lock_mv is not None:
            its += items([(lock, NEW)], move=lock_mv)
        s = Shot(its, -40, 45, (550, 820), fit=fit)
        s.arrow(*arr)
        s.d.multiline_text((24, 18), text, font=font(26), fill=INK, spacing=6)
        panels.append(s.img)
    page("key-plug", next(N), "The tub: the key's USB-C plug, in the top edge", panels,
         need=[(icon(g["plug"][:2], el=20), "1×", "USB-C plug on its cable"), (icon([(lock, NEW)]), "1×", "the plug lock")],
         note="Solder the plug's four wires and its two 4.7k pull-ups first. Leave the wires about 12 cm long.")

    # (breadboard) the breadboard on the tub's floor, the switch in it
    if BB:
        inb = [(body, WHITE)] + g["body inserts"] + g["feet"] + g["plug"] + [(lock, WHITE)]
        bx0, bx1, by0, by1 = H.bb_box()
        a = Shot(items(inb) + items([(g["breadboard"][0][0], NEW)], move=(0, 0, 25)) + items(g["tact"], move=(0, 0, 45)),
                 -60, 40, (900, 950), pad=0.05)
        a.arrow(p(bx0 - 4, H.SIGN_XY[1], H.Z_TACT + 20), p(bx0 - 4, H.SIGN_XY[1], H.Z_TACT + 3))
        a.label(p(bx0, by1, H.WALL), "between the four\ncorner stops", -120, -200, 24)
        fit = [p(x, y, z) for x in (bx0 - 2, bx1 + 2) for y in (by0 - 2, by1 + 2) for z in (H.WALL, H.Z_TACT + 8)]
        b = Shot(items([(body.intersect(H.box(bx0 - 4, bx1 + 4, by0 - 4, by1 + 4, -1, 12)), WHITE)] + g["breadboard"] + g["tact"]
                       + g["tact wires"]), -90, 65, (750, 950), fit=fit, pad=0.12)
        b.label(p(tx, ty, H.Z_TACT + H.TACT[3]), "across the channel, its centre\non the %s column from the\nright-hand end"
                % {1: "1st", 2: "2nd", 3: "3rd"}.get(H.BB_COL, "%dth" % H.BB_COL), -230, -250, 24)
        b.label(p(tx - 30, ty + 3.5 * H.BB_PITCH, H.Z_TACT + 0.5), "flat jumpers from two\ndiagonal legs' rows", -60, 230, 24)
        page("breadboard", next(N), "The tub: the breadboard, the sign button's switch in it", [a.img, b.img],
             need=[(icon(g["breadboard"]), "1×", "mini breadboard"), (icon(g["tact"]), "1×", "12 × 12 tactile switch"),
                   (icon(g["tact wires"]), "2×", "flat jumper wire")],
             note="Stick it down with its own tape. Over the board, under the button, there's only about 6 mm: use flat\n"
                  "jumpers, not Dupont leads. Meter the two legs: they beep only while pressed. They go to pins 20 and 18.")

    # the plate's inserts, face down
    cs = H.carrier_screws()
    ov = Shot(items([(plate, WHITE)]) + items([it for c in cs for it in pressed(*c, H.Z_CARRIER, False, 20)]),
              -72, 48, (1100, 950), bench=True, pad=0.05)
    for c in cs:
        ov.arrow(p(*c, H.Z_CARRIER - 18), p(*c, H.Z_CARRIER - 2))
    ov.label(p(sx, sy, H.T), "face down on a towel", 0, 0, 24)
    c = cs[1]
    near = H.box(c[0] - 14, c[0] + 14, c[1] - 14, c[1] + 14, H.Z_CARRIER - 1, H.T + 1)
    fit = [p(c[0] + dx, c[1] + dy, z) for dx in (-12, 12) for dy in (-12, 12) for z in (H.T, H.Z_CARRIER - 30)]
    a = Shot(items([(plate.intersect(near), WHITE)] + pressed(*c, H.Z_CARRIER, False, 5, True)), -55, 28,
             (550, 950), bench=True, fit=fit)
    a.label(p(*c, H.Z_CARRIER - 18), "straight down,\nstop flush", -150, -60, 24)
    page("plate-inserts", next(N), "The plate: an insert in each of the carrier's bosses", [ov.img, a.img],
         need=[(ic["m3i"], "4×", "M3 insert"), (ic["iron"], "", "soldering iron")])

    # 5. the guard: cover on the base, the pin, the cap up through it
    x0, x1, y0, y1 = H.guard_box()
    yh, zh = H.hinge()
    gfit = [p(x, y, z) for x in (x0 - 24, x1 + 6) for y in (y0 - 4, y1 + 4) for z in (H.Z_FLOOR_TOP - 12, H.T + 10)]
    a = Shot(items([(base, NEW)]) + items([(cover, NEW)], move=(0, 0, 10)) + items(g["pin"], move=(-24, 0, 0)),
             -60, 30, (550, 800), fit=gfit)
    a.arrow(p(x0 - 22, yh, zh), p(x0 - 4, yh, zh))
    a.d.multiline_text((24, 18), "1  the cover between the\n   base's knuckles, the pin\n   through all three", font=font(24), fill=INK, spacing=6)
    b = Shot(items([(base, NEW), (cover, NEW)] + g["pin"]) + items([(cap, NEW)], move=(0, 0, -12)), -60, -30, (550, 800), fit=gfit)
    b.arrow(p(tx, ty, H.Z_FLOOR_TOP - 16), p(tx, ty, H.Z_FLOOR_TOP - 6))
    b.d.multiline_text((24, 18), "2  the cap up through the\n   base from underneath", font=font(24), fill=INK, spacing=6)
    c2 = Shot(items([(base, NEW), (cap, NEW)] + g["pin"]) + items([(H.guard_cover(100), NEW)]), -60, 30, (550, 800), fit=gfit)
    c2.d.multiline_text((24, 18), "3  trim the pin flush;\n   the cover swings up", font=font(24), fill=INK, spacing=6)
    page("guard", next(N), "The sign button's guard, on the bench", [a.img, b.img, c2.img],
         need=[(icon([(base, NEW)]), "1×", "guard base"), (icon([(cover, NEW)]), "1×", "guard cover"),
               (icon([(cap, NEW)], el=20), "1×", "button cap"), (ic["pin"], "20 mm", "1.75 mm filament")])

    # 6. the guard into its well
    near = H.box(tx - 24, H.W + 1, ty - 22, ty + 28, H.Z_FLOOR_BOT - 6, H.T + 1)
    gpl = plate.intersect(near)
    guard = [(base, NEW), (cap, NEW)] + g["pin"] + [(H.guard_cover(100), NEW)]
    fit = [p(x, y, z) for x in (tx - 24, H.W) for y in (ty - 22, ty + 28) for z in (H.Z_FLOOR_BOT - 6, H.T + 40)]
    s = Shot(items([(gpl, WHITE)]) + items(guard, move=(0, 0, 22)) + items(g["base screws"], move=(0, 0, 40)),
             -60, 38, (1000, 950), fit=fit)
    s.arrow(p(x1 + 4, ty, H.T + 18), p(x1 + 4, ty, H.T + 2))
    for x, y in H.BASE_SCREWS:
        s.arrow(p(x, y, H.Z_BASE_TOP + 52), p(x, y, H.Z_BASE_TOP + 44))
    s.label(p(x1 - 2, yh, zh + 22), "the knuckles toward\nthe screen", 250, -60, 24)
    page("guard-in", next(N), "The plate, face up: the guard into its well, two screws", [s.img],
         need=[(ic["m2s"], "2×", "M2 × 8 socket head")],
         note="The screws cut their own thread in the plate: firm, then stop.")

    # (holder) the tactile switch in its holder, behind the well
    if not BB:
        fit = [p(x, y, z) for x in (tx - 22, tx + 22) for y in (ty - 16, ty + 18) for z in (H.Z_TACT - 36, H.T)]
        a = Shot(items([(gpl, WHITE)] + guard[:3]) + items(g["tact"] + g["tact wires"], move=(0, 0, -10))
                 + items([(holder, NEW)], move=(0, 0, -20)) + items(g["holder screws"], move=(0, 0, -30)),
                 -60, 40, (900, 950), bench=True, fit=fit)
        a.arrow(p(tx + 14, ty, H.Z_TACT - 26), p(tx + 14, ty, H.Z_TACT - 12))
        a.label(p(tx, ty, H.Z_TACT - 6), "the switch in the pocket,\nits stem toward the plate", 230, -170, 24)
        a.label(p(tx + H.TACT[4] / 2 + 10, ty, H.Z_TACT - 10), "two wires on two\ndiagonal legs", 200, 160, 24)
        cut = H.box(-1, H.W + 1, ty, H.H, -1, H.T + 30)
        cfit = [p(x, y, z) for x in (tx - 15, tx + 15) for y in (ty,) for z in (H.Z_TACT - H.HOLDER[2] - 1, H.T + 1)]
        b = Shot(items([(sh.cut(cut), c) for sh, c in [(gpl, WHITE), (base, WHITE), (cap, WHITE)] + g["tact"] + [(holder, NEW)]]),
                 -90, 0, (750, 950), fit=cfit, pad=0.18)
        b.d.multiline_text((24, 18), "cut through, from the side:\nthe cap's plunger 0.2 mm\nover the switch's stem", font=font(24), fill=INK, spacing=6)
        page("switch", next(N), "The plate, face down: the sign button's switch", [a.img, b.img],
             need=[(icon(g["tact"]), "1×", "6 × 6 tactile switch"), (icon([(holder, NEW)]), "1×", "switch holder"),
                   (ic["m2s"], "2×", "M2 × 8 socket head")],
             note="Meter the two legs first: they beep only while the switch is pressed. The wires go to pins 20 and 18.")

    # 8. the knob
    done8 = [(plate, WHITE)] + g["boss inserts"] + guard[:3] + ([] if BB else g["tact"] + [(holder, WHITE)] + g["holder screws"])
    kfl = H.T - H.KNOB_WELL[1] - H.KNOB_FLOOR - 30
    fit = [p(x, y, z) for x in (kx - 18, kx + 18) for y in (ky - 18, ky + 18) for z in (kfl, H.T + 8)]
    a = Shot(items(done8) + items(g["ec11"], move=(0, 0, -20)), -60, 40, (800, 900), bench=True, fit=fit)
    a.arrow(p(kx + 12, ky, kfl + 6), p(kx + 12, ky, kfl + 20))
    a.d.multiline_text((24, 18), "1  from behind: the EC11\n   into the knob's hole", font=font(24), fill=INK, spacing=6)
    fit2 = [p(x, y, z) for x in (kx - 18, kx + 18) for y in (ky - 18, ky + 18) for z in (H.T - 16, H.T + 22)]
    b = Shot(items(done8 + g["ec11"]) + items(g["ec11 nut"], move=(0, 0, 16)), -60, 40, (850, 900), fit=fit2)
    b.arrow(p(kx, ky - 9, H.T + 20), p(kx, ky - 9, H.T + 4))
    b.d.multiline_text((24, 18), "2  face up: its nut in the well,\n   snug, not tight", font=font(24), fill=INK, spacing=6)
    page("knob", next(N), "The plate: the knob", [a.img, b.img], need=[(icon(g["ec11"] + g["ec11 nut"]), "1×", "EC11 knob, its nut")])

    # 9. the screen
    done9 = done8 + g["ec11"] + g["ec11 nut"]
    s = Shot(items(done9) + items(g["screen"], move=(0, 0, -30)), -72, 46, (1650, 950), bench=True, pad=0.09)
    for hc in H.screen_holes():
        s.arrow(p(*hc, H.Z_BOARD - 30), p(*hc, H.Z_BOARD - 6))
    s.label(p(H.HEADER_X, sy, H.Z_BOARD - 38), "header on the " + ("LEFT\n(the firmware's way up)" if H.HEADER_SIDE < 0 else "RIGHT"),
            220 * H.HEADER_SIDE, 60, 26)
    s.label(p(sx, sy - 10, H.Z_BOARD - 32), "glass down,\ninto the window", 260, 140, 26)
    page("screen", next(N), "The plate, face down: the screen onto its four pins", [s.img],
         need=[(icon(g["screen"]), "1×", '2.4" screen')],
         note="Peel the screen's film first. It drops on: the pins find its holes, and the board rests on the seats.")

    # 10. the spacers
    done10 = done9 + g["screen"]
    sp = [(x, NEW) for x in g["spacers"]]
    s = Shot(items(done10) + items(sp, move=(0, 0, -22)), -72, 46, (1650, 950), bench=True, pad=0.06)
    for hc in H.screen_holes():
        s.arrow(p(*hc, H.Z_CARRIER - 20), p(*hc, H.Z_CARRIER - 4))
    page("spacers", next(N), "The plate: a spacer on each pin", [s.img], need=[(icon([sp[0]]), "4×", "spacer (printed)")])

    # 11. the carrier
    done11 = done10 + [(x, WHITE) for x in g["spacers"]]
    s = Shot(items(done11) + items([(carrier, NEW)], move=(0, 0, -26)) + items(g["carrier screws"], move=(0, 0, -50)),
             -72, 46, (1650, 1000), bench=True, pad=0.05)
    for c in H.carrier_screws():
        s.arrow(p(*c, H.Z_CARRIER_BACK - 48), p(*c, H.Z_CARRIER_BACK - 32))
    s.label(p(H.HEADER_X + 2, sy, H.Z_CARRIER - 26), "the notch goes round\nthe screen's header", 170 * H.HEADER_SIDE, -170, 24)
    s.label(p(H.PICO_X1 - 10, H.PICO_Y + 6, H.Z_CARRIER_BACK - 32), "the Pico's posts\nface you", 180, -150, 24)
    page("carrier", next(N), "The plate: the carrier over the pins, four screws into the bosses", [s.img],
         need=[(icon([(carrier, NEW)], az=115, el=-40), "1×", "the carrier"), (ic["m3s"], "4×", "M3 × 8 socket head"),
               (ic["washer"], "4×", "M3 washer")],
         note="The pins come up through the carrier. Tighten the screws evenly, a little at a time; they hold the screen down.")

    # 12. the Pico
    done12 = done11 + [(carrier, WHITE)] + g["carrier screws"]
    s = Shot(items(done12) + items(g["pico"], move=(0, 0, -22)) + items(g["pico screws"], move=(0, 0, -40)),
             -72, 46, (1650, 1000), bench=True, pad=0.09)
    for x, y, _ in H.pico_posts():
        s.arrow(p(x, y, H.Z_PICO - 40), p(x, y, H.Z_PICO - 28))
    s.label(p(H.PICO_X1, H.PICO_Y, H.Z_PICO - 22), "USB to the plate's\nRIGHT edge", 260, 120, 26)
    s.label(p(H.PICO_X1 - 30, H.PICO_Y - 8, H.Z_PICO - 22), "its parts and USB socket\ndown, toward the carrier", -330, 230, 26)
    s.label(p(H.PICO_X1 - 2, H.PICO_Y + 5.7, H.Z_CARRIER_BACK - H.PICO_UP), "slimmer posts at the USB end:\n%.1f mm, for its plug"
            % H.PICO_POST_D_USB, 200, -230, 24)
    page("pico", next(N), "The plate: the Pico on the carrier's posts", [s.img],
         need=[(icon(g["pico"]), "1×", "Pico 2 W, no headers"), (ic["m2s"], "4×", "M2 × 8 socket head")],
         note="Solder its wires to its pads before it goes on: it's easier with the board in your hand.")

    # 13. the wires
    done13 = done12 + g["pico"] + g["pico screws"]
    s = Shot(items(done13), -60, 40, (1650, 1000), bench=True, pad=0.06)
    for q, t, dx, dy in [((H.HEADER_X, sy, H.Z_BOARD - 9), "screen header: 8 wires\nto pins 11-17 and 36", -60, 230),
                         ] + ([] if BB else [((tx, ty, H.Z_TACT - 2), "sign button: pins 20, 18", 170, 150)]) + [
                         ((kx, ky, H.T - H.KNOB_WELL[1] - H.KNOB_FLOOR - 6.5), "knob: pins 2, 3, 4, 5", -330, -60),
                         ((H.PICO_X1 - 20, H.PICO_Y, H.Z_PICO - 1), "key's plug: pins 6, 7, 8, 36" + (
                             "\nsign button: pins 20, 18\n(their wires come from the tub)" if BB else "\n(its wires come from the tub)"), 330, 230)]:
        s.label(p(*q), t, dx, dy, 24)
    page("wires", next(N), "The wires: as pico-sign's tables", [s.img],
         note=("Wire the plate, push the console image and try it on the bench before closing: the key and the sign\n"
               "button are in the tub, so lay the plate beside it to wire them." if BB else
               "Everything here is on the plate: wire it, push the console image and try it on the bench before closing."))

    # 14. onto the tub
    stack = done13 + [(cap, WHITE), (H.guard_cover(), WHITE)] + g["base screws"]
    inbody = [(body, WHITE)] + g["body inserts"] + g["feet"] + g["plug"] + [(lock, WHITE)] + g["breadboard"] + \
        (g["tact"] + g["tact wires"] if BB else [])
    a = Shot(items(inbody) + items(stack, move=(0, 0, 60)) + items(g["plate screws"], move=(0, 0, 85)), -55, 25, (900, 1000), pad=0.05)
    for x, y in H.SCREWS:
        a.arrow(p(x, y, H.T + 82), p(x, y, H.T + 64))
    a.arrow(p(H.W + 12, 20, H.T + 50), p(H.W + 12, 20, H.T + 12))
    a.label(p(H.KEY_X, H.H - 20, H.ZP), "the key's%s wires\nto the Pico first" % (" and the button's" if BB else ""), -200, -80, 24)
    fit = [p(x, y, z) for x in (H.W - 20, H.W + 60) for y in (H.PICO_Y - 22, H.PICO_Y + 22) for z in (0, H.T + 4)]
    b = Shot(items(inbody + stack + g["plate screws"]) + items(g["usb cable"], move=(30, 0, 0)), -20, 20, (750, 1000), fit=fit)
    b.arrow(p(H.W + 46, H.PICO_Y, H.PLUG_Z + 12), p(H.W + 24, H.PICO_Y, H.PLUG_Z + 12))
    b.label(p(H.W, H.PICO_Y, H.PLUG_Z), "the micro-USB cable\nin through the side", 60, 200, 24)
    page("close", next(N), "The plate onto the tub, four screws; the Pico's cable", [a.img, b.img],
         need=[(ic["m3s"], "4×", "M3 × 8 socket head"), (icon(g["usb cable"][:1], el=20), "1×", "micro-USB cable")],
         note="The heads sink into the plate's counterbores. Snug: they go into brass, but the plate is plastic.")

    # 15. the key in its clamshell
    ct, cb, kb, kc = C.clamshell()
    up_ = lambda parts, dz: items(parts, move=(0, 0, dz))
    kfit = [p(x, y, z) for x in (-14, 14) for y in (-4, 50) for z in (-3, 30)]
    a = Shot(up_([(cb, NEW)], 0) + up_([(kb, BLUE), (kc, BLACK)], 10) + up_([(ct, NEW)], 22), -55, 32, (800, 900), fit=kfit)
    a.arrow(p(0, 32, 9), p(0, 32, 2))
    a.label(p(0, 32, 2), "the peg through the\nkey's round hole", -200, 120, 24)
    a.arrow(p(0, 22, 27), p(0, 22, 15))
    b = Shot(up_([(cb, NEW), (kb, BLUE), (kc, BLACK), (ct, NEW)], 0), -55, 32, (850, 900), fit=kfit)
    b.label(p(C.CART[0] / 2, C.CLIP_Y[1], C.CATCH), "press until all four\nclips click", 150, 160, 24)
    b.label(p(0, 18 + 2.7, C.CART_T - C.WALL_B), "the chip shows\nthrough the window", -60, -160, 24)
    page("key", next(N), "The key into its clamshell", [a.img, b.img],
         need=[(icon([(kb, BLUE), (kc, BLACK)]), "1×", "a key-c"), (icon([(cb, NEW)]), "1×", "key tray"),
               (icon([(ct, NEW)]), "1×", "key cover")],
         note="To open it, push the four hooks in through the windows in the sides with a small screwdriver.")

    # 16. the knob's cap, the key on top
    whole = inbody + stack + g["plate screws"]
    a = Shot(items(whole) + items(g["knob"], move=(0, 0, 25)) + items(g["key"], move=(0, 30, 0)), -60, 30, (900, 1000), pad=0.05)
    a.arrow(p(kx + 14, ky, H.T + 34), p(kx + 14, ky, H.T + 16))
    k = ctr(g["key"][0][0])
    a.arrow(k + (0, 58, 0), k + (0, 34, 0))
    a.label(k + (0, 30, 0), "the key, straight down\nonto its plug", -260, -90, 24)
    b = Shot(items(whole + g["knob"] + g["key"]), -50, 35, (750, 1000), pad=0.06)
    page("done", next(N), "The knob's cap, then a key in the top", [a.img, b.img],
         need=[(icon(g["knob"]), "1×", "knob cap"), (icon(g["key"], el=20), "1×", "the key in its clamshell")])


if __name__ == "__main__":
    main()
