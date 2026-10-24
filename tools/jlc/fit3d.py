"""The board in 3D, as boxes: each part's courtyard to its height, the module on the back, the
glass on its tape, the ribbon's fold, the screws. Every pair is intersected; what touches is a
clash. Sizes are datasheet figures and guesses (the board's jlc_spec says which), so this catches
gross trouble, not tenths. Run by `tools/keypcb jlc` in FreeCAD's own Python, not by hand:

    JLC_FIT="facts.json:spec.json:outdir" freecadcmd fit3d.py

(freecadcmd opens each argument as a document, so the paths come in the environment.)

z is up from the front face; the board is z -t to 0. Every line it prints starts "ok", "warn",
"FAIL" or "info".
"""
import json, os, sys

import FreeCAD
import Part

V = FreeCAD.Vector


def say(kind, text):
    print(f"  {kind:<4} {text}", flush=True)
    return kind == "FAIL"


def box(x0, y0, x1, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def main(argv):
    factsp, specp, out = argv[:3]
    f, spec = json.load(open(factsp)), json.load(open(specp)).get("fit")
    print("8. the fit in 3D", flush=True)
    if not spec:
        say("info", "the board's generator gives no fit (no jlc_spec()['fit']): skipped")
        return 0
    t = f["thickness"]
    (bx0, by0), (bx1, by1) = f["outline"]
    solids, guessed = [], []
    extra = spec.get("back", []) + spec.get("solids", [])
    stand_in = {s["name"].split()[0] for s in extra}       # "U1 module" stands in for U1's courtyard
    for fp in f["footprints"]:
        c = fp["courtyard"].get(fp["side"])
        if not c or fp["dnp"] or fp["ref"].startswith(("TP", "H")) or fp["ref"] in stand_in:
            continue
        h = spec["heights"].get(fp["fp"])
        if h is None:
            h = spec["default_height"]
            guessed.append(fp["ref"])
        (x0, y0), (x1, y1) = c
        z = (0.0, h) if fp["side"] == "F" else (-t - h, -t)
        solids.append((fp["ref"], box(x0, y0, x1, y1, *z), "part"))
    guess = set()
    for s in extra:
        if "cyl" in s:
            x, y, r = s["cyl"]
            shape = Part.makeCylinder(r, s["z"][1] - s["z"][0], V(x, y, s["z"][0]))
        else:
            shape = box(*s["box"], *s["z"])
        solids.append((s["name"], shape, "extra"))
        if s.get("guess"):
            guess.add(s["name"])
    if guessed:
        say("warn", f"no height for {', '.join(guessed)}: taken as {spec['default_height']} mm")

    clashes, maybe, pairs = [], [], []
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            (a, sa, ka), (b, sb, kb) = solids[i], solids[j]
            if ka == kb == "part":
                continue        # courtyards: the generator and KiCad's DRC hold them apart
            if not sa.BoundBox.intersect(sb.BoundBox):
                continue
            v = sa.common(sb).Volume
            if v > 1e-6:
                (maybe if a in guess or b in guess else clashes).append(f"{a} and {b} ({v:.2f} mm³)")
                c = sa.common(sb).BoundBox
                pairs.append({"a": a, "b": b, "box": [c.XMin, c.YMin, c.ZMin, c.XMax, c.YMax, c.ZMax], "guess": a in guess or b in guess})
    bad = say("FAIL" if clashes else "ok", f"{len(solids)} solids, no two in the same space" + (" but for guessed ones, below" if maybe else "")
              if not clashes else f"clashes: {clashes}")
    if maybe:
        say("warn", f"clashes with a guessed solid (measure it): {maybe}")

    def nearest(name):
        """The nearest part on the same face of the board."""
        s = next(sh for n, sh, _ in solids if n == name)
        front = s.BoundBox.ZMin >= -1e-6
        best = min(((s.distToShape(sh)[0], n) for n, sh, k in solids if k == "part" and (sh.BoundBox.ZMin >= -1e-6) == front),
                   default=(None, None))
        return best
    for name in [n for n, _, k in solids if k == "extra"]:
        d, n = nearest(name)
        if d is not None:
            say("info", f"{name}: the nearest part is {n}, {d:.2f} mm away")
    run = spec.get("ribbon_run")
    if run:
        x0, y0, x1, y1 = min(run[0], run[2]), run[1], max(run[0], run[2]), run[3]
        under = sorted(f"{fp['ref']} {spec['heights'].get(fp['fp'], spec['default_height'])}" for fp in f["footprints"]
                       if fp["side"] == "F" and fp["courtyard"].get("F") and not fp["dnp"]
                       and fp["courtyard"]["F"][0][0] < x1 and fp["courtyard"]["F"][1][0] > x0
                       and fp["courtyard"]["F"][0][1] < y1 and fp["courtyard"]["F"][1][1] > y0)
        say("info", "the ribbon runs back to J2 over: " + (", ".join(under) or "nothing") + " (mm tall): it lies on what is tallest")
    for s in spec.get("solids", []) + spec.get("back", []):
        if s.get("note"):
            say("info", f"{s['name']}: {s['note']}")
    # for the pictures (gerb_check.py draws them): every solid's box, and where any two meet
    json.dump({"board": [bx0, by0, -t, bx1, by1, 0.0],
               "solids": [{"name": n, "kind": ("guess" if n in guess else "glass" if n == "glass" else k),
                           "box": [sh.BoundBox.XMin, sh.BoundBox.YMin, sh.BoundBox.ZMin, sh.BoundBox.XMax, sh.BoundBox.YMax, sh.BoundBox.ZMax],
                           "cyl": next((s["cyl"] for s in extra if s["name"] == n and "cyl" in s), None)} for n, sh, k in solids],
               "clashes": pairs, "ribbon_run": spec.get("ribbon_run")},
              open(os.path.join(out, "fit.json"), "w"), indent=1)
    comp = Part.makeCompound([box(bx0, by0, bx1, by1, -t, 0)] + [sh for _, sh, _ in solids])
    comp.exportStep(os.path.join(out, "fit.step"))
    say("info", f"fit.step: the board and {len(solids)} solids, to look at in FreeCAD")
    return 1 if bad else 0


args = os.environ["JLC_FIT"].split(":")
code = main(args)
if code:
    open(os.path.join(args[2], "fit3d.failed"), "w").write("1")
