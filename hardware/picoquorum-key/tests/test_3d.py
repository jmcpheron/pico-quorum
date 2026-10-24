"""3D fit: the board's STEP (every part's real model) against the things that sit on it.

kicad-cli exports the STEP; FreeCAD (tests/freecad/fit.py) intersects each part's solid with:
- the panel glass, on 1.5 mm foam tape (DESIGN.md "The panel and its ribbon");
- the ribbon's folded tail, lying under the glass from the fold back to J2;
- the fold itself, standing up to 0.5 mm proud of the glass's right edge;
- the foam tape at the glass's two ends (the right-hand piece split round the fold);
- an M2 pan head on the front and an M2 nut on the back at each hole;
- the board itself (a model sunk into the board is a model in the wrong place) and every other part.
It also holds the part heights DESIGN.md quotes to the models. Pictures, in
hardware/out/scratch/test/3d/: a top view and three side sections, clashes in red.

Needs FreeCAD 1.x (FREECADCMD, default the macOS app's freecadcmd). Skipped if it isn't there.
"""
import hashlib
import json
import os
import unittest

import common
from test_geometry import read_consts

FREECADCMD = os.environ.get("FREECADCMD", "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
GEN = os.path.join(common.ROOT, "tools", "gen", "gen_pcb.py")
FIT = os.path.join(common.ROOT, "tests", "freecad", "fit.py")

# mechanical numbers, with where they come from
TAPE = 1.5             # foam tape under the glass (DESIGN.md)
PANEL_T = 1.6          # ER-TFT1.14-2 outline thickness "with FPC folded" (datasheet p. 5)
RIBBON_T = 0.30        # ribbon with stiffener (datasheet)
RIBBON_W = 4.5         # tail width (datasheet)
FOLD_PROUD = 0.5       # the fold stands up to 0.5 mm proud of the glass edge (datasheet)
TAPE_W = 2.0           # each foam strip, measured in from the glass's short edge
BOARD_T = 1.6
M2_HEAD = (2.0, 1.6)   # ISO 7045 M2 pan head: radius (dk 4.0 / 2), height k
M2_NUT = (2.2, 1.6)    # ISO 4032 M2 nut: across corners 4.32 / 2, height m
HEIGHTS = {            # DESIGN.md "Height on the front", and the module's datasheet (3.1 mm)
    "SW": (3.8, 0.15), "J2": (1.0, 0.1), "J1": (3.2, 0.2), "U1": (3.1, 0.15)}
NOTES = []
_RESULT = {}


def job_and_result():
    if _RESULT:
        return _RESULT["job"], _RESULT["res"]
    c = read_consts(GEN, {"W", "H", "GLASS", "ZIF_X"})
    W, H, (gx0, gy0, gx1, gy1) = c["W"], c["H"], c["GLASS"]
    ribbon_y = (gy0 + gy1) / 2
    fold_y = (gy0 + 5.4, gy0 + 14.5)                         # gen_pcb.FOLD_Y, from the datasheet
    tail_end = gx1 - 21.0
    f = common.board_facts()
    models = {}                                              # ref -> model file stem (the STEP's label)
    for fp in common.find_all(common.tree_of(common.PCB), "footprint"):
        ref = next(str(p[2]) for p in common.find_all(fp, "property") if p[1] == "Reference")
        m = common.find(fp, "model")
        models[ref] = os.path.splitext(os.path.basename(str(m[1])))[0] if m else None
    fps = [{"ref": r, "x": fp["pos"][0], "y": fp["pos"][1], "side": fp["layer"], "model": models.get(r)}
           for r, fp in f["footprints"].items()]
    holes = [(r, fp["pos"]) for r, fp in f["footprints"].items() if r.startswith("H")]
    envs = [
        {"name": "glass", "kind": "box", "box": [gx0, gy0, TAPE, gx1, gy1, TAPE + PANEL_T]},
        {"name": "ribbon", "kind": "box", "box": [tail_end, ribbon_y - RIBBON_W / 2, TAPE - RIBBON_T,
                                                  gx1, ribbon_y + RIBBON_W / 2, TAPE]},
        {"name": "fold", "kind": "box", "box": [gx1, fold_y[0], 0, gx1 + FOLD_PROUD, fold_y[1], TAPE + PANEL_T]},
        {"name": "tape", "kind": "box", "box": [gx0, gy0, 0, gx0 + TAPE_W, gy1, TAPE]},
        {"name": "tape", "kind": "box", "box": [gx1 - TAPE_W, gy0, 0, gx1, fold_y[0], TAPE]},
        {"name": "tape", "kind": "box", "box": [gx1 - TAPE_W, fold_y[1], 0, gx1, gy1, TAPE]},
    ]
    for ref, (x, y) in holes:
        envs.append({"name": "screw head", "kind": "cyl", "x": x, "y": y, "r": M2_HEAD[0], "z0": 0, "z1": M2_HEAD[1]})
        envs.append({"name": "nut", "kind": "cyl", "x": x, "y": y, "r": M2_NUT[0], "face": "back",
                     "z0": -M2_NUT[1], "z1": 0})
    # the real board's pictures go to scratch/test/3d; another board (CONSOLE_PCB) gets its own folder
    tag = "" if common.PCB == os.path.join(common.PRJ, "picoquorum-key.kicad_pcb") else \
        "-" + hashlib.md5(common.PCB.encode()).hexdigest()[:8]
    out_dir = common.scratch("3d" + tag)
    views = [
        {"axis": "plan", "title": "top view: front parts solid (height in mm), back dashed (depth); clashes red",
         "png": os.path.join(out_dir, "plan.png")},
        {"axis": "y", "at": ribbon_y, "u": [-1, W + 1], "z": [-5.5, 4.5], "w": 13, "h": 4.2,
         "title": "section at y = %.1f: buttons, ZIF, ribbon, glass on tape; the module below" % ribbon_y,
         "png": os.path.join(out_dir, "section-ribbon.png")},
        {"axis": "y", "at": 29.5, "u": [-1, W + 1], "z": [-4, 4.5], "w": 13, "h": 3.6,
         "title": "section at y = 29.5: the upper M2 holes (head above, nut below)",
         "png": os.path.join(out_dir, "section-holes.png")},
        {"axis": "x", "at": 21.5, "u": [-1, H + 1], "z": [-5.5, 4.5], "w": 14, "h": 4.0,
         "title": "section at x = 21.5: J2 under the glass, U4, USB-C at the bottom edge",
         "png": os.path.join(out_dir, "section-usb.png")},
    ]
    step = os.path.join(out_dir, "board.step")
    if not os.path.exists(step) or os.path.getmtime(step) < os.path.getmtime(common.PCB):
        r = common.run(["kicad-cli", "pcb", "export", "step", "--force", "--subst-models",
                        "--user-origin", "%gx%gmm" % (100.0, 60.0), "-o", step, common.PCB])
        if r.returncode:
            raise RuntimeError(r.stdout + r.stderr)
    job = {"step": step, "footprints": fps, "envelopes": envs, "views": views, "W": W, "H": H,
           "out": os.path.join(out_dir, "fit.json")}
    job_path = os.path.join(out_dir, "job.json")
    with open(job_path, "w") as fh:
        json.dump(job, fh, indent=1)
    # freecadcmd swallows a script's exceptions: run it through exec() so a traceback reaches stderr
    wrapper = "import traceback\ntry:\n    exec(open(%r).read())\nexcept BaseException:\n    traceback.print_exc()\n" % FIT
    r = common.run([FREECADCMD, "-c", wrapper], env=dict(os.environ, FIT_JSON=job_path))
    if not os.path.exists(job["out"]) or os.path.getmtime(job["out"]) < os.path.getmtime(job_path):
        raise RuntimeError("fit.py failed:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    with open(job["out"]) as fh:
        res = json.load(fh)
    _RESULT.update(job=job, res=res, glass=(gx0, gy0, gx1, gy1), W=W, H=H)
    return job, res


@unittest.skipUnless(os.path.exists(FREECADCMD), "FreeCAD not installed")
class Fit3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job, cls.r = job_and_result()
        cls.parts = cls.r["parts"]

    @classmethod
    def tearDownClass(cls):
        if NOTES:
            print("\n3d fit notes (pictures in %s):\n  " % os.path.dirname(cls.job["out"]) + "\n  ".join(NOTES))

    def bbox(self, ref):
        return self.parts[ref]["bbox"]

    def test_every_part_has_a_model(self):
        """A footprint with no model would sail through every clash check below."""
        missing = [r for r in self.r["no_model"] if not r.startswith(("TP", "H"))]
        self.assertEqual(missing, [], "placed parts with no 3D model in the STEP")
        self.assertEqual(self.r["unmatched_solids"], [], "solids in the STEP away from any footprint origin")
        # KiCad seats models on the pad copper: the two faces sit about 0.04 mm outside the 1.6 mm board
        self.assertAlmostEqual(self.r["thickness"], BOARD_T, delta=0.1)

    def test_no_model_sinks_into_the_board(self):
        self.assertEqual(self.r["board"], {}, "part solids inside the board body (mm^3)")

    def test_part_heights_match_the_design(self):
        for ref, (x0, y0, z0, x1, y1, z1) in sorted((r, p["bbox"]) for r, p in self.parts.items()):
            key = next((k for k in HEIGHTS if ref == k or (k == "SW" and ref.startswith("SW"))), None)
            if key is None:
                continue
            want, tol = HEIGHTS[key]
            got = -(z0 + self.r["thickness"]) if z1 <= 0.01 else z1
            with self.subTest(part=ref):
                self.assertAlmostEqual(got, want, delta=tol)

    def test_nothing_under_the_glass_touches_it(self):
        self.assertEqual(self.r["envelopes"]["glass"], [])
        gx0, gy0, gx1, gy1 = _RESULT["glass"]
        under = [(r, p["bbox"][5]) for r, p in self.parts.items()
                 if p["bbox"][5] > 0 and p["bbox"][0] < gx1 and p["bbox"][3] > gx0 and p["bbox"][1] < gy1 and p["bbox"][4] > gy0]
        if under:
            ref, top = max(under, key=lambda t: t[1])
            NOTES.append("under the glass: tallest is %s at %.2f mm, %.2f mm below the glass on %.1f mm tape (%s)"
                         % (ref, top, TAPE - top, TAPE, ", ".join("%s %.2f" % u for u in sorted(under))))

    def test_ribbon_path_is_clear(self):
        """The folded tail lies under the glass from the fold back to J2; J2 is where it goes in."""
        self.assertEqual([h for h in self.r["envelopes"]["ribbon"] if h[0] != "J2"], [])

    def test_fold_is_clear(self):
        self.assertEqual(self.r["envelopes"]["fold"], [])

    def test_foam_tape_lands_on_bare_board(self):
        self.assertEqual(self.r["envelopes"]["tape"], [])
        NOTES.append("foam tape: %.1f mm strips at each end of the glass; the right-hand one in two pieces, "
                     "either side of the ribbon's fold (Y %.1f-%.1f)" % (TAPE_W, *self.job["envelopes"][2]["box"][1:5:3]))

    def test_screw_heads_and_nuts_are_clear(self):
        self.assertEqual(self.r["envelopes"]["screw head"], [], "parts under an M2 pan head (front)")
        self.assertEqual(self.r["envelopes"]["nut"], [], "parts under an M2 nut (back)")
        for name in ("screw head", "nut"):
            if self.r["clearance"][name]:
                ref, d = self.r["clearance"][name][0]
                NOTES.append("closest part to an M2 %s: %s, %.2f mm" % (name, ref, d))

    def test_no_two_parts_collide(self):
        self.assertEqual(self.r["collisions"], [])

    def test_parts_stay_inside_the_outline(self):
        W, H = _RESULT["W"], _RESULT["H"]
        for ref, p in sorted(self.parts.items()):
            x0, y0, _, x1, y1, _ = p["bbox"]
            with self.subTest(part=ref):
                self.assertGreaterEqual(x0, -0.05)
                self.assertLessEqual(x1, W + 0.05)
                self.assertGreaterEqual(y0, -0.05)
                self.assertLessEqual(y1, H + (0.8 if ref == "J1" else 0.05))   # the receptacle's lip
        NOTES.append("J1 face %+.2f mm past the bottom edge; U1's antenna end %+.2f mm from the top edge"
                     % (self.bbox("J1")[4] - H, self.bbox("U1")[1]))

    def test_stack_height(self):
        """Reported: what an enclosure has to hold."""
        top = max(p["bbox"][5] for p in self.parts.values())
        bottom = min(p["bbox"][2] for p in self.parts.values())
        sw = max(p["bbox"][5] for r, p in self.parts.items() if r.startswith("SW"))
        NOTES.append("stack: %.2f mm above the board's top face, %.2f mm below its back face, %.2f mm overall; "
                     "the button tops stand %.2f mm above the glass's top"
                     % (top, -(bottom + self.r["thickness"]), top - bottom, sw - (TAPE + PANEL_T)))


if __name__ == "__main__":
    unittest.main()
