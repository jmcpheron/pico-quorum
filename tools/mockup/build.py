"""The mockup's solids, in FreeCAD's own Python. Run by tools/mockup/mockup.py, not by hand:

    MOCKUP="facts.json:spec.json:outdir:name" freecadcmd build.py

(freecadcmd opens each argument as a document, so the paths come in the environment.)

Writes two STLs, each laid out to print flat with no support:
- <name>-board.stl: the board, every front part as a block to its height, and the panel as one block
  from the board up to the glass's top, fused into one solid, back face down. The M2 holes go
  through. A 0.4 mm groove on the back outlines where the module goes, with a line where its
  shield ends and its antenna begins.
- <name>-module.stl: the ESP32-S3-WROOM-1, its soldered face down, its antenna end at +y.

Blocks are courtyards less their 0.25 mm margin, to datasheet or typical heights: a mockup to hold
and fit, not a model to measure.
"""
import json
import os

import FreeCAD
import Mesh
import MeshPart
import Part

V = FreeCAD.Vector
SINK = 0.2          # every block starts this far inside the board, so the fuse is one solid
GROOVE = 0.4        # the module's outline on the back: width and depth


def box(x0, y0, x1, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def height(spec, fp):
    for prefix, h in spec["heights"]:
        if fp.startswith(prefix):
            return h
    return spec["default_height"]


def module_body(f, spec):
    """(x0, y0, x1, y1, antenna side) of U1's body on the back: centred on its footprint, its long
    side along y at 0 or 180 degrees, along x at +-90, its antenna at the end nearest the edge."""
    u1 = next(p for p in f["parts"] if p["ref"] == "U1")
    m = spec["module"]
    (cx, cy), along_y = u1["at"], round(u1["rot"]) % 180 == 0
    w, l = (m["w"], m["l"]) if along_y else (m["l"], m["w"])
    x0, y0, x1, y1 = cx - w / 2, cy - l / 2, cx + w / 2, cy + l / 2
    xs = [x for ring in f["outline"] for pt in ring[0] for x in [pt[0]]]
    ys = [y for ring in f["outline"] for pt in ring[0] for y in [pt[1]]]
    if along_y:
        side = "+y" if max(ys) - y1 < y0 - min(ys) else "-y"
    else:
        side = "+x" if max(xs) - x1 < x0 - min(xs) else "-x"
    return x0, y0, x1, y1, side


def board_solid(f, spec):
    t = f["thickness"]
    outer = f["outline"][0][0]
    wire = Part.makePolygon([V(x, y, -t) for x, y in outer] + [V(*outer[0], -t)])
    board = Part.Face(wire).extrude(V(0, 0, t))
    xs, ys = [p[0] for p in outer], [p[1] for p in outer]
    blocks = []
    for p in f["parts"]:
        if p["side"] != "F" or p["dnp"] or not p["courtyard"] or p["ref"].startswith(("H", "TP")):
            continue
        (x0, y0), (x1, y1) = p["courtyard"]
        x0, y0, x1, y1 = x0 + 0.25, y0 + 0.25, x1 - 0.25, y1 - 0.25
        h = height(spec, p["fp"])
        # A part past the edge (a USB-C's mouth) comes down to the board's back, so nothing overhangs.
        z0 = -t if x0 < min(xs) or y0 < min(ys) or x1 > max(xs) or y1 > max(ys) else -SINK
        if p["ref"].startswith("SW"):
            # a tact switch: its body, and a round plunger to the full height
            hb = round(h * spec["switch_body"], 2)
            blocks.append(box(x0, y0, x1, y1, z0, hb))
            r = min(x1 - x0, y1 - y0) / 4
            blocks.append(Part.makeCylinder(r, h - hb + SINK, V((x0 + x1) / 2, (y0 + y1) / 2, hb - SINK)))
        else:
            blocks.append(box(x0, y0, x1, y1, z0, h))
    for b in spec["panel"]:
        blocks.append(box(*b, -SINK, spec["panel_top"]))
    shape = board.fuse(blocks).removeSplitter()
    for hole in f["holes"]:
        x, y = hole["at"]
        shape = shape.cut(Part.makeCylinder(hole["d"] / 2, t + 20, V(x, y, -t - 1)))
    x0, y0, x1, y1, side = module_body(f, spec)
    g, ant = GROOVE, spec["module"]["ant"]
    ring = box(x0, y0, x1, y1, -t - 1, -t + g).cut(box(x0 + g, y0 + g, x1 - g, y1 - g, -t - 2, -t + 2))
    line = {"+y": box(x0, y1 - ant - g / 2, x1, y1 - ant + g / 2, -t - 1, -t + g),
            "-y": box(x0, y0 + ant - g / 2, x1, y0 + ant + g / 2, -t - 1, -t + g),
            "+x": box(x1 - ant - g / 2, y0, x1 - ant + g / 2, y1, -t - 1, -t + g),
            "-x": box(x0 + ant - g / 2, y0, x0 + ant + g / 2, y1, -t - 1, -t + g)}[side]
    shape = shape.cut(ring.fuse(line))
    shape.translate(V(0, 0, t))          # back face on z = 0, the print bed
    return shape


def module_solid(spec):
    """Soldered face on z = 0, pins along x = 0 and x = w, antenna end at +y."""
    m = spec["module"]
    w, l, pcb, top, ant, inset = m["w"], m["l"], m["pcb"], m["t"], m["ant"], m["shield_inset"]
    plate = box(0, 0, w, l, 0, pcb)
    shield = box(inset, inset, w - inset, l - ant - inset, pcb - SINK, top)
    return plate.fuse(shield).removeSplitter()


def write(shape, path):
    assert shape.isValid(), path
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2)
    mesh.write(path)
    bb = shape.BoundBox
    print(f"  {os.path.basename(path)}: {len(shape.Solids)} solid, {bb.XLength:.2f} x {bb.YLength:.2f} x "
          f"{bb.ZLength:.2f} mm, {shape.Volume:.0f} mm3, {mesh.CountFacets} facets", flush=True)
    return len(shape.Solids) == 1


def main():
    factsp, specp, out, name = os.environ["MOCKUP"].split(":")
    f, spec = json.load(open(factsp)), json.load(open(specp))
    ok = write(board_solid(f, spec), os.path.join(out, f"{name}-board.stl"))
    ok &= write(module_solid(spec), os.path.join(out, f"{name}-module.stl"))
    if not ok:
        raise SystemExit("mockup: a shape isn't one solid")


main()
