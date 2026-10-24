"""The FreeCAD half of test_3d: load the board's STEP, intersect it with the mechanical envelopes,
write the numbers as JSON and the section views as PNG. Run by test_3d.py, not by hand:

  FIT_JSON=<job.json> freecadcmd tests/freecad/fit.py

The job (written by test_3d.py) gives the STEP path, each footprint's position and side, the
envelopes (boxes and cylinders in board millimetres: x right, y down from the top-left corner,
z up from the board's top face) and the sections to draw. Every solid in the STEP is matched to the
footprint at its origin; the result says which footprints had no model and which solids had no
footprint, so a missing model can't pass for a clear fit.
"""
import itertools
import json
import os
import re

import FreeCAD as App
import Import
import Part

job = json.load(open(os.environ["FIT_JSON"]))
doc = App.newDocument("fit")
Import.insert(job["step"], doc.Name)

# --- the board body and the parts, in board coordinates ----------------------------------------
# STEP frame (export with --user-origin at the board's top-left): X = x, Y = -y, Z = 0 at the
# board's bottom face. Everything is mirrored to y down and moved to z = 0 at the board's top face.
roots = [o for o in doc.Objects if o.TypeId == "App::Part" and not o.InList]
if len(roots) != 1:
    raise RuntimeError("expected one root assembly, found %s" % [o.Label for o in roots])
solids = []
for o in doc.Objects:                                        # one App::Part per footprint, directly
    if o.TypeId != "App::Part" or roots[0] not in o.InList:  # under the root (multi-solid models nest
        continue                                             # more App::Parts inside theirs)
    sh = o.Shape
    if sh.isNull() or not sh.Solids:
        continue
    solids.append((o.Label, o.getGlobalPlacement().Base, sh))
pcb = [o for o in doc.Objects if o.TypeId == "Part::Feature" and o.Label.endswith("_PCB")]
if len(pcb) != 1:
    raise RuntimeError("expected one *_PCB body in the STEP, found %s" % [o.Label for o in pcb])
# KiCad's board body is the core only (1.51 of 1.6 mm), and it seats each model on its pads' copper,
# so the faces used here are where the front and back parts' origins sit (1.6 mm + about 0.04 a side).
zs = sorted(round(b.z, 4) for _, b, _ in solids)
TOP, BOTTOM = zs[-1], zs[0]
THICK = TOP - BOTTOM


def to_b(shape):
    s = shape.copy()
    s.translate(App.Vector(0, 0, -TOP))
    return s.mirror(App.Vector(0, 0, 0), App.Vector(0, 1, 0))


board = to_b(pcb[0].Shape)
def stem(name):
    return re.sub(r"[\d.]+$", "", name)


parts = {}
unmatched = []
fps = job["footprints"]
for label, base, sh in solids:
    x, y = base.x, -base.y
    # STEP labels are the model's file stem, but FreeCAD treats trailing digits as its own uniqueness
    # suffix (SOT-23 arrives as SOT-001), so names are compared with trailing digits and dots dropped,
    # and position picks among the parts that share a name
    same = [f for f in fps if f["model"] and f["ref"] not in parts and stem(f["model"]) == stem(label)]
    if not same:
        unmatched.append({"label": label, "x": round(x, 2), "y": round(y, 2)})
        continue
    best = min(same, key=lambda f: (f["x"] - x) ** 2 + (f["y"] - y) ** 2)
    if (best["x"] - x) ** 2 + (best["y"] - y) ** 2 > 0.1 ** 2 or best["ref"] in parts:
        unmatched.append({"label": label, "x": round(x, 2), "y": round(y, 2)})
        continue
    parts[best["ref"]] = to_b(sh)


def bbox(s):
    b = s.BoundBox
    return [round(v, 3) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]


# --- envelopes ----------------------------------------------------------------------------------
def solid_of(e):
    """Back-side envelopes (face "back") give z from the back face, negative going away from it."""
    if e.get("face") == "back":
        e = dict(e, z0=e["z0"] - THICK, z1=e["z1"] - THICK)
    if e["kind"] == "box":
        x0, y0, z0, x1, y1, z1 = e["box"]
        return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))
    if e["kind"] == "cyl":
        return Part.makeCylinder(e["r"], e["z1"] - e["z0"], App.Vector(e["x"], e["y"], e["z0"]))
    raise ValueError(e["kind"])


env = {}
for e in job["envelopes"]:
    env.setdefault(e["name"], []).append(solid_of(e))
env = {k: (v[0] if len(v) == 1 else v[0].fuse(v[1:])) for k, v in env.items()}

MIN_VOL = 1e-4                                               # mm^3: below this, a touch, not a clash
res = {"thickness": round(THICK, 3), "parts": {}, "unmatched_solids": unmatched,
       "no_model": sorted(f["ref"] for f in fps if f["ref"] not in parts),
       "board": {}, "envelopes": {}, "clearance": {}, "collisions": []}
for ref, s in parts.items():
    res["parts"][ref] = {"bbox": bbox(s), "volume": round(s.Volume, 3)}
    v = s.common(board).Volume
    if v > MIN_VOL:
        res["board"][ref] = round(v, 4)
for name, es in env.items():
    hits, near = [], []
    for ref, s in parts.items():
        if (s.BoundBox.ZMax <= 0.01) != (es.BoundBox.ZMax <= 0.01):
            continue                                         # the other side of the board
        bb = App.BoundBox(es.BoundBox)
        bb.enlarge(2.0)
        if not s.BoundBox.intersect(bb):
            continue
        v = s.common(es).Volume
        if v > MIN_VOL:
            hits.append([ref, round(v, 4)])
        else:
            d = s.distToShape(es)[0]
            if d < 2.0:
                near.append([ref, round(d, 3)])
    res["envelopes"][name] = sorted(hits)
    res["clearance"][name] = sorted(near, key=lambda r: r[1])
refs = sorted(parts)
for a, b in itertools.combinations(refs, 2):
    if not parts[a].BoundBox.intersect(parts[b].BoundBox):
        continue
    v = parts[a].common(parts[b]).Volume
    if v > MIN_VOL:
        res["collisions"].append([a, b, round(v, 4)])

json.dump(res, open(job["out"], "w"), indent=1)

# --- pictures -----------------------------------------------------------------------------------
import matplotlib                                            # noqa: E402  (FreeCAD bundles it)
matplotlib.use("Agg")
import matplotlib.pyplot as plt                               # noqa: E402
from matplotlib.patches import Polygon                        # noqa: E402

COLOURS = {"board": "#2f6b3a", "part": "#4a5a70", "hit": "#d1342f", "env": "#d39b2a"}
hit_refs = {r for hs in res["envelopes"].values() for r, _ in hs} | {r for c in res["collisions"] for r in c[:2]} \
    | set(res["board"])


def section(shape, axis, at):
    """Closed outlines of shape cut by the plane axis = at, as lists of (u, z) points."""
    normal = App.Vector(1, 0, 0) if axis == "x" else App.Vector(0, 1, 0)
    out = []
    try:
        wires = shape.slice(normal, at)
    except Exception:
        return out
    for w in wires:
        pts = w.discretize(Distance=0.05)
        out.append([((p.y if axis == "x" else p.x), p.z) for p in pts])
    return out


def draw(view):
    axis, at = view["axis"], view["at"]
    fig, ax = plt.subplots(figsize=(view.get("w", 12), view.get("h", 4.5)), dpi=150)
    for poly in section(board, axis, at):
        ax.add_patch(Polygon(poly, closed=True, fc=COLOURS["board"], ec="none", alpha=0.9))
    for name, es in env.items():
        for poly in section(es, axis, at):
            ax.add_patch(Polygon(poly, closed=True, fc=COLOURS["env"], ec=COLOURS["env"], alpha=0.18, lw=0.8, ls="--"))
            u = sum(p[0] for p in poly) / len(poly)
            z = max(p[1] for p in poly)
            ax.text(u, z + 0.08, name, fontsize=6.5, ha="center", va="bottom", color="#7a5a10")
    for ref, s in sorted(parts.items()):
        polys = section(s, axis, at)
        c = COLOURS["hit"] if ref in hit_refs else COLOURS["part"]
        for poly in polys:
            ax.add_patch(Polygon(poly, closed=True, fc=c, ec="black", lw=0.3, alpha=0.85))
        if polys:
            u = sum(p[0] for p in polys[0]) / len(polys[0])
            zt = max(p[1] for poly in polys for p in poly)
            zb = min(p[1] for poly in polys for p in poly)
            ax.text(u, (zt + 0.1) if zb >= -0.01 else (zb - 0.1), ref, fontsize=7, ha="center",
                    va="bottom" if zb >= -0.01 else "top", color=c, weight="bold")
    ax.set_aspect("equal")
    ax.set_xlim(*view["u"])
    ax.set_ylim(*view["z"])
    ax.set_xlabel(("y" if axis == "x" else "x") + " (mm, board frame)")
    ax.set_ylabel("z (mm, 0 = board top)")
    ax.grid(True, lw=0.3, alpha=0.5)
    ax.set_title(view["title"], fontsize=10)
    fig.tight_layout()
    fig.savefig(view["png"])
    plt.close(fig)


def plan(view):
    """Top view: part outlines (front solid, back dashed) and the envelopes, clashes in red."""
    fig, ax = plt.subplots(figsize=(7, 8.4), dpi=150)
    ax.add_patch(Polygon([(0, 0), (job["W"], 0), (job["W"], job["H"]), (0, job["H"])], closed=True,
                         fc="#e9f0ea", ec=COLOURS["board"], lw=1))
    for e in job["envelopes"]:
        if e["kind"] == "box":
            x0, y0, _, x1, y1, _ = e["box"]
            ax.add_patch(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True, fc=COLOURS["env"],
                                 ec=COLOURS["env"], alpha=0.15, ls="--"))
        else:
            ax.add_patch(plt.Circle((e["x"], e["y"]), e["r"], fc=COLOURS["env"], ec=COLOURS["env"], alpha=0.15, ls="--"))
    for ref, s in sorted(parts.items()):
        x0, y0, z0, x1, y1, z1 = bbox(s)
        back = z1 <= 0.01
        c = COLOURS["hit"] if ref in hit_refs else COLOURS["part"]
        ax.add_patch(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True, fill=not back,
                             fc=c, alpha=0.12 if back else 0.55, ec=c, ls="--" if back else "-", lw=0.6))
        h = (-z0 - THICK) if back else z1
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, "%s\n%.1f" % (ref, h), fontsize=5, ha="center", va="center",
                color=c if not back else "#777")
    ax.set_xlim(-2, job["W"] + 2)
    ax.set_ylim(job["H"] + 2, -2)
    ax.set_aspect("equal")
    ax.set_title(view["title"], fontsize=10)
    fig.tight_layout()
    fig.savefig(view["png"])
    plt.close(fig)


for v in job["views"]:
    (plan if v["axis"] == "plan" else draw)(v)
print("fit: %d parts, %d envelopes, %d collisions" % (len(parts), len(env), len(res["collisions"])))
