"""The fab files, read back: what JLCPCB receives must be the board as designed.

Reads hardware/out/rev-a/picoquorum-key-gerbers.zip (tools/export.sh writes it) with tests/gerber.py,
which shares no code with KiCad's plotter, and compares it with the board (pcb_facts.py):

- the zip has exactly the layers export.sh promises, each one labelled as what it is;
- the outline is closed and 44 x 53; every file is in one coordinate frame;
- every drill hit and slot is a via, a pad hole or a mounting hole on the board, and the other way
  round, at the same position and size;
- every copper, mask and paste flash is a pad (or via) on the board, and the other way round;
- annular rings measured from the Gerber pads around the Excellon holes meet JLCPCB's minimums;
- no via has a mask opening (they're tented); no paste lands anywhere but a front SMD pad.

A failure here after a board edit usually means the zip is stale: run tools/export.sh rev-a.
It also writes gerbers-top.svg / gerbers-bottom.svg to hardware/out/scratch/test/fab/, a picture
drawn from the Gerbers alone, for a look with your own eyes.
"""
import math
import os
import unittest
from collections import Counter

import common
import gerber
import jlc_limits as jlc

ZIP = os.environ.get("CONSOLE_FAB_ZIP", os.path.join(common.ROOT, "hardware", "out", "rev-a", "picoquorum-key-gerbers.zip"))
POS_TOL = 0.01          # mm; plotter rounding is far below this
EXPECTED = {            # Gerber file function -> what export.sh asks for
    "Copper,L1,Top": "F.Cu", "Copper,L2,Bot": "B.Cu", "Paste,Top": "F.Paste",
    "Legend,Top": "F.SilkS", "Legend,Bot": "B.SilkS", "Soldermask,Top": "F.Mask",
    "Soldermask,Bot": "B.Mask", "Profile,NP": "Edge.Cuts",
}
NOTES = []


def norm(function):
    """The job file and the Gerbers spell the same function differently (SolderMask / Soldermask,
    SolderPaste / Paste, Profile / Profile,NP)."""
    f = function.lower().replace("solderpaste", "paste")
    return f.split(",")[0] if f.startswith("profile") else f


def match(expected, found, tol=POS_TOL):
    """Pair points (x, y, tag) one to one by nearest position; return (unmatched expected, unmatched found)."""
    left = list(found)
    missing = []
    for e in expected:
        best = min(range(len(left)), key=lambda i: gerber.dist(e[0], e[1], left[i][0], left[i][1]), default=None)
        if best is not None and gerber.dist(e[0], e[1], left[best][0], left[best][1]) <= tol:
            left.pop(best)
        else:
            missing.append(e)
    return missing, left


@unittest.skipUnless(os.path.exists(ZIP), "no fab zip: run tools/export.sh rev-a")
class FabFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = common.board_facts()
        cls.W, cls.H = cls.f["board"]["w"], cls.f["board"]["h"]
        cls.files = gerber.read_zip(ZIP)
        cls.layers, cls.drills = {}, {}
        for name, text in cls.files.items():
            if name.endswith(".drl"):
                d = gerber.Drill(text)
                cls.drills["PTH" if d.plated else "NPTH"] = d
            elif not name.endswith(".gbrjob"):
                g = gerber.Gerber(text)
                cls.layers[g.attrs.get("FileFunction", name)] = g
        cls.pads = [(ref, fp, p) for ref, fp in cls.f["footprints"].items() for p in fp["pads"]]
        cls.vias = cls.f["vias"]
        out = os.path.dirname(common.scratch("fab", "gerbers-top.svg"))
        write_svgs(cls, out)

    @classmethod
    def tearDownClass(cls):
        if NOTES:
            print("\nfab file notes:\n  " + "\n  ".join(NOTES))

    def board(self, x, y):
        """Gerber frame (origin bottom-left, Y up) -> board frame (origin top-left, Y down)."""
        return x, self.H - y

    # --- what is in the zip ------------------------------------------------------------------
    def test_zip_has_exactly_the_promised_layers(self):
        self.assertEqual(set(self.layers), set(EXPECTED))
        self.assertEqual(set(self.drills), {"PTH", "NPTH"})
        NOTES.append("no B.Paste in the zip: the back (the module) is hand-soldered, no stencil needed")

    def test_job_file_agrees_with_the_layers_and_the_board(self):
        import json
        job = json.loads(next(t for n, t in self.files.items() if n.endswith(".gbrjob")))
        spec = job["GeneralSpecs"]
        self.assertEqual(spec["LayerNumber"], 2)
        self.assertAlmostEqual(spec["BoardThickness"], 1.6)
        # KiCad's job size includes the outline's stroke
        self.assertAlmostEqual(spec["Size"]["X"], self.W, delta=0.2)
        self.assertAlmostEqual(spec["Size"]["Y"], self.H, delta=0.2)
        for fa in job["FilesAttributes"]:
            with self.subTest(file=fa["Path"]):
                self.assertIn(fa["Path"], self.files)
                if fa["Path"].endswith(".drl"):
                    continue
                own = gerber.Gerber(self.files[fa["Path"]]).attrs.get("FileFunction")
                self.assertEqual(norm(fa["FileFunction"]), norm(own), "job file and Gerber disagree on what this layer is")

    def test_every_gerber_shares_one_coordinate_frame(self):
        frames = {g.attrs.get("SameCoordinates") for g in self.layers.values()}
        self.assertEqual(len(frames), 1, frames)

    # --- outline -----------------------------------------------------------------------------
    def test_outline_is_closed_and_the_board_size(self):
        edge = self.layers["Profile,NP"]
        ends = Counter()
        for x0, y0, x1, y1, _, _ in edge.strokes:
            ends[(round(x0, 3), round(y0, 3))] += 1
            ends[(round(x1, 3), round(y1, 3))] += 1
        self.assertTrue(all(n == 2 for n in ends.values()), "outline has loose ends: %s"
                        % [p for p, n in ends.items() if n != 2])
        xs = [p[0] for p in ends]; ys = [p[1] for p in ends]
        self.assertAlmostEqual(min(xs), 0, delta=POS_TOL); self.assertAlmostEqual(min(ys), 0, delta=POS_TOL)
        self.assertAlmostEqual(max(xs), self.W, delta=POS_TOL); self.assertAlmostEqual(max(ys), self.H, delta=POS_TOL)

    def test_copper_keeps_off_the_outline(self):
        for fn in ("Copper,L1,Top", "Copper,L2,Bot"):
            with self.subTest(layer=fn):
                x0, y0, x1, y1 = self.layers[fn].extent()
                gap = min(x0, y0, self.W - x1, self.H - y1)
                NOTES.append("%s: copper comes within %.2f mm of the edge (JLCPCB minimum %.2f)"
                             % (EXPECTED[fn], gap, jlc.COPPER_TO_OUTLINE_MIN))
                self.assertGreaterEqual(gap, jlc.COPPER_TO_OUTLINE_MIN - 1e-6)

    # --- drills ------------------------------------------------------------------------------
    def expected_holes(self, plated):
        out = []
        if plated:
            out += [(v["pos"][0], v["pos"][1], ("via", v["drill"])) for v in self.vias]
        for ref, fp, p in self.pads:
            if p["attr"] == ("PTH" if plated else "NPTH") and not p["drill_oblong"]:
                out.append((p["pos"][0], p["pos"][1], (ref, p["drill"])))
        return out

    def test_every_drill_hit_is_a_hole_on_the_board_and_back(self):
        for kind in ("PTH", "NPTH"):
            with self.subTest(file=kind):
                d = self.drills[kind]
                found = [self.board(x, y) + (dia,) for dia, x, y in d.hits]
                missing, extra = match(self.expected_holes(kind == "PTH"), found)
                self.assertEqual(missing, [], "on the board, not in %s.drl" % kind)
                self.assertEqual(extra, [], "in %s.drl, not on the board" % kind)

    def test_drill_sizes_match_hole_by_hole(self):
        for kind in ("PTH", "NPTH"):
            d = self.drills[kind]
            for e in self.expected_holes(kind == "PTH"):
                hit = min(d.hits, key=lambda h: gerber.dist(e[0], e[1], *self.board(h[1], h[2])))
                with self.subTest(hole=e[2]):
                    self.assertAlmostEqual(hit[0], e[2][1], delta=0.001)

    def test_every_slot_is_an_oblong_pad_hole(self):
        oblong = [(ref, p) for ref, fp, p in self.pads if p["drill_oblong"]]
        slots = self.drills["PTH"].slots + self.drills["NPTH"].slots
        self.assertEqual(len(slots), len(oblong))
        for ref, p in oblong:
            with self.subTest(pad="%s %s" % (ref, p["number"])):
                s = min(slots, key=lambda s: gerber.dist(p["pos"][0], p["pos"][1],
                                                          *self.board((s[1] + s[3]) / 2, (s[2] + s[4]) / 2)))
                w, length = min(p["drill_xy"]), max(p["drill_xy"])
                self.assertAlmostEqual(s[0], w, delta=0.001)
                self.assertAlmostEqual(gerber.dist(s[1], s[2], s[3], s[4]) + s[0], length, delta=0.01)
                self.assertGreaterEqual(w, jlc.PLATED_SLOT_WIDTH_MIN if p["attr"] == "PTH" else jlc.NPTH_SLOT_WIDTH_MIN)
                self.assertGreaterEqual(length, 2 * w - 1e-6, "JLCPCB wants a slot at least twice as long as wide")

    def test_drill_list_is_short(self):
        sizes = sorted({t for d in self.drills.values() for t in d.tools.values()})
        NOTES.append("drill sizes: %s mm (%d tools)" % (sizes, len(sizes)))
        self.assertLessEqual(len(sizes), 8)

    # --- copper, mask, paste -----------------------------------------------------------------
    def check_flashes(self, fn, want):
        g = self.layers[fn]
        found = [self.board(x, y) + (ap,) for x, y, ap in g.flashes]
        missing, extra = match(want, found)
        self.assertEqual(missing, [], "%s: on the board, not flashed" % fn)
        self.assertEqual([(round(x, 3), round(y, 3), a.code) for x, y, a in extra], [],
                         "%s: flashed, not a pad on the board" % fn)

    def test_copper_flashes_are_the_pads_and_vias(self):
        for fn, cu in (("Copper,L1,Top", "F.Cu"), ("Copper,L2,Bot", "B.Cu")):
            with self.subTest(layer=cu):
                want = [(p["pos"][0], p["pos"][1], (ref, p["number"])) for ref, fp, p in self.pads
                        if cu in p["copper"] and p["attr"] != "NPTH"]
                want += [(v["pos"][0], v["pos"][1], "via") for v in self.vias]
                self.check_flashes(fn, want)

    def test_mask_openings_are_the_pads_only_vias_are_tented(self):
        for fn, layer in (("Soldermask,Top", "F.Mask"), ("Soldermask,Bot", "B.Mask")):
            with self.subTest(layer=layer):
                want = [(p["pos"][0], p["pos"][1], (ref, p["number"])) for ref, fp, p in self.pads if layer in p["mask"]]
                self.check_flashes(fn, want)
                g = self.layers[fn]
                open_vias = []
                for v in self.vias:
                    for x, y, ap in g.flashes:
                        bx, by = self.board(x, y)
                        hx, hy = ap.half or (0, 0)
                        if abs(v["pos"][0] - bx) < hx + v["size"] / 2 and abs(v["pos"][1] - by) < hy + v["size"] / 2:
                            open_vias.append((v["net"], tuple(v["pos"])))
                self.assertEqual(open_vias, [], "via inside a mask opening: solder can wick into it")

    def test_mask_webs_between_nets(self):
        """The strip of mask between two openings must be at least JLCPCB's minimum web, or the fab
        drops it and the two pads share one opening: an easy solder bridge if their nets differ.
        Measured between the flashed openings, each tied to its pad's net (an unconnected pad
        counts as a net of its own)."""
        for fn, layer in (("Soldermask,Top", "F.Mask"), ("Soldermask,Bot", "B.Mask")):
            pads = [(p["pos"], p["net"] if not common.is_nc(p["net"]) else "%s.%s" % (ref, p["number"]))
                    for ref, fp, p in self.pads if layer in p["mask"]]
            opens = []
            for x, y, ap in self.layers[fn].flashes:
                bx, by = self.board(x, y)
                if ap.half is None:
                    continue
                net = min(pads, key=lambda q: gerber.dist(bx, by, q[0][0], q[0][1]))[1]
                opens.append((bx, by, ap.half, net))
            webs = []
            for i, (ax, ay, (ahx, ahy), an) in enumerate(opens):
                for bx, by, (bhx, bhy), bn in opens[i + 1:]:
                    if an == bn:
                        continue
                    gx = abs(ax - bx) - ahx - bhx
                    gy = abs(ay - by) - ahy - bhy
                    webs.append((math.hypot(max(gx, 0), max(gy, 0)), (round(ax, 2), round(ay, 2)), (round(bx, 2), round(by, 2))))
            with self.subTest(layer=layer):
                thin = sorted(w for w in webs if w[0] < jlc.MASK_DAM_MIN - 1e-6)
                self.assertEqual(thin, [], "mask webs under %.2f mm between different nets" % jlc.MASK_DAM_MIN)
                if webs:
                    w = min(webs)
                    NOTES.append("%s: thinnest mask web between two nets %.3f mm, at %s / %s (JLCPCB minimum %.2f)"
                                 % (layer, w[0], w[1], w[2], jlc.MASK_DAM_MIN))

    def test_paste_only_on_front_smd_pads(self):
        want = [(p["pos"][0], p["pos"][1], (ref, p["number"])) for ref, fp, p in self.pads
                if "F.Paste" in p["paste"] and p["attr"] == "SMD" and ("F.Cu" in p["copper"] or common.pane_of(fp, p))]
        self.check_flashes("Paste,Top", want)
        stray = [(ref, p["number"]) for ref, fp, p in self.pads if "F.Paste" in p["paste"] and p["attr"] != "SMD"]
        self.assertEqual(stray, [])

    def test_paste_never_bigger_than_its_pad(self):
        cu = self.layers["Copper,L1,Top"]
        for x, y, ap in self.layers["Paste,Top"].flashes:
            pad = min(cu.flashes, key=lambda f: gerber.dist(x, y, f[0], f[1]))
            with self.subTest(at=(round(x, 2), round(y, 2))):
                self.assertTrue(ap.half and pad[2].half)
                self.assertLessEqual(sorted(ap.size), [v + 1e-6 for v in sorted(pad[2].size)])

    # --- annular rings, measured from the files ----------------------------------------------
    def test_annular_rings_from_the_gerbers(self):
        worst = {}
        for kind in ("PTH",):
            d = self.drills[kind]
            for layer in ("Copper,L1,Top", "Copper,L2,Bot"):
                cu = self.layers[layer]
                for dia, x, y in d.hits:
                    pad = min(cu.flashes, key=lambda f: gerber.dist(x, y, f[0], f[1]))
                    self.assertLess(gerber.dist(x, y, pad[0], pad[1]), POS_TOL, "hole without copper at %s" % ((x, y),))
                    ring = (min(pad[2].size) - dia) / 2
                    is_via = pad[2].function and "ViaPad" in pad[2].function
                    key = "via %.2f" % dia if is_via else "pad hole %.2f" % dia
                    worst[key] = min(ring, worst.get(key, 9))
                for dia, x0, y0, x1, y1 in d.slots:
                    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                    pad = min(cu.flashes, key=lambda f: gerber.dist(cx, cy, f[0], f[1]))
                    length = gerber.dist(x0, y0, x1, y1) + dia
                    w, h = sorted(pad[2].size)
                    ring = min((w - dia) / 2, (h - length) / 2)
                    worst["slot %.2f" % dia] = min(ring, worst.get("slot %.2f" % dia, 9))
        for key, ring in sorted(worst.items()):
            limit, pref = ((jlc.VIA_RING_MIN, jlc.VIA_RING_PREFERRED) if key.startswith("via")
                           else (jlc.PTH_RING_MIN, jlc.PTH_RING_PREFERRED))
            NOTES.append("annular ring, %s: %.3f mm (JLCPCB min %.2f, preferred %.2f)%s"
                         % (key, ring, limit, pref, "  <- below preferred" if ring < pref else ""))
            with self.subTest(hole=key):
                self.assertGreaterEqual(ring, limit - 1e-6)


# --- a picture from the Gerbers alone ---------------------------------------------------------
def _svg_items(g, color, opacity=1.0, mirror=False, W=0.0, H=0.0):
    def X(x):
        return W - x if mirror else x

    out = []
    for x0, y0, x1, y1, ap, kind in g.strokes:
        r = (ap.half or (0.05, 0.05))[0] * 2
        out.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="%s" stroke-width="%.3f" '
                   'stroke-linecap="round" opacity="%s"/>' % (X(x0), H - y0, X(x1), H - y1, color, r, opacity))
    for x, y, ap in g.flashes:
        if not ap.half:
            continue
        hx, hy = ap.half
        if ap.kind == "C":
            out.append('<circle cx="%.3f" cy="%.3f" r="%.3f" fill="%s" opacity="%s"/>' % (X(x), H - y, hx, color, opacity))
        else:
            rr = min(hx, hy) if ap.kind == "O" else (ap.params[0] if ap.kind == "RoundRect" else 0)
            out.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" rx="%.3f" fill="%s" opacity="%s"/>'
                       % (X(x) - hx, H - y - hy, 2 * hx, 2 * hy, rr, color, opacity))
    for reg in g.regions:
        pts = " ".join("%.3f,%.3f" % (X(x), H - y) for x, y in reg)
        out.append('<polygon points="%s" fill="%s" opacity="%s"/>' % (pts, color, opacity))
    return out


def write_svgs(cls, out_dir):
    W, H = cls.W, cls.H
    for side, cu, mask, silk, mirror in (("top", "Copper,L1,Top", "Soldermask,Top", "Legend,Top", False),
                                         ("bottom", "Copper,L2,Bot", "Soldermask,Bot", "Legend,Bot", True)):
        body = ['<rect x="0" y="0" width="%s" height="%s" fill="#1d3b2a"/>' % (W, H)]
        body += _svg_items(cls.layers[cu], "#c9a227", 0.9, mirror, W, H)
        body += _svg_items(cls.layers[mask], "#f2d16b", 1.0, mirror, W, H)       # exposed copper
        body += _svg_items(cls.layers[silk], "#ffffff", 1.0, mirror, W, H)
        body += _svg_items(cls.layers["Profile,NP"], "#ff4fa0", 1.0, mirror, W, H)
        for kind in ("PTH", "NPTH"):
            d = cls.drills[kind]
            for dia, x, y in d.hits:
                xx = W - x if mirror else x
                body.append('<circle cx="%.3f" cy="%.3f" r="%.3f" fill="#000"/>' % (xx, H - y, dia / 2))
            for dia, x0, y0, x1, y1 in d.slots:
                body.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#000" stroke-width="%.3f" '
                            'stroke-linecap="round"/>' % (W - x0 if mirror else x0, H - y0, W - x1 if mirror else x1, H - y1, dia))
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -1 %s %s" width="%smm" height="%smm">\n%s\n</svg>\n'
               % (W + 2, H + 2, (W + 2) * 4, (H + 2) * 4, "\n".join(body)))
        with open(os.path.join(out_dir, "gerbers-%s.svg" % side), "w") as f:
            f.write(svg)


if __name__ == "__main__":
    unittest.main()
