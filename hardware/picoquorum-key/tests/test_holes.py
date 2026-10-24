"""Via and hole audit: every via, pad hole and mounting hole against JLCPCB's limits.

DRC checks the project's own rules. This checks the rules themselves against JLCPCB's numbers
(tests/jlc_limits.py), and then each hole one by one, with the distances a fab cares about:
drill, ring, hole to hole, hole to other copper, vias at or in SMD pads, the screw-head keep-out
round the M2 holes, finished-size bands after drill tolerance, and how the hand-soldered module's
ground pads meet the pour.

Writes the full table to hardware/out/scratch/test/holes/holes.csv.
"""
import csv
import json
import math
import os
import unittest

import common
import jlc_limits as jlc

SCREW_KEEPOUT_R = 2.2       # mm from an M2 hole's centre: a pan head is ~3.8 mm across, plus margin
M2_CLEAR = (2.1, 2.4)       # a finished hole in this band takes an M2 screw without binding or slop
NOTES = []


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def box_dist(px, py, b):
    """Distance from a point to a box (0 inside)."""
    dx = max(b[0] - px, 0, px - b[2])
    dy = max(b[1] - py, 0, py - b[3])
    return math.hypot(dx, dy)


class Holes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = common.board_facts()
        cls.W, cls.H = cls.f["board"]["w"], cls.f["board"]["h"]
        cls.vias = cls.f["vias"]
        cls.tracks = cls.f["tracks"]
        cls.pads = [(ref, fp, p) for ref, fp in cls.f["footprints"].items() for p in fp["pads"]]
        # every drilled hole: (kind, ref, x, y, drill, net)
        cls.holes = [("via", "via", v["pos"][0], v["pos"][1], v["drill"], v["net"]) for v in cls.vias]
        cls.holes += [(p["attr"], "%s.%s" % (ref, p["number"]), p["pos"][0], p["pos"][1], min(p["drill_xy"]), p["net"])
                      for ref, fp, p in cls.pads if p["attr"] in ("PTH", "NPTH")]
        with open(os.path.join(common.PRJ, "picoquorum-key.kicad_pro")) as f:
            cls.rules = json.load(f)["board"]["design_settings"]["rules"]
        write_table(cls)

    @classmethod
    def tearDownClass(cls):
        if NOTES:
            print("\nhole audit notes:\n  " + "\n  ".join(NOTES))

    # --- the project's rules against JLCPCB's ---------------------------------------------
    def test_project_copper_and_drill_rules_are_within_jlc_limits(self):
        pairs = {"min_track_width": jlc.TRACK_MIN, "min_clearance": jlc.SPACE_MIN,
                 "min_via_diameter": jlc.VIA_DIAMETER_MIN, "min_through_hole_diameter": jlc.VIA_DRILL_MIN,
                 "min_via_annular_width": jlc.VIA_RING_MIN, "min_copper_edge_clearance": jlc.COPPER_TO_OUTLINE_MIN,
                 "min_hole_to_hole": jlc.VIA_TO_VIA_MIN, "min_hole_clearance": jlc.VIA_HOLE_TO_TRACK_MIN}
        for rule, floor in pairs.items():
            with self.subTest(rule=rule):
                self.assertGreaterEqual(self.rules[rule], floor - 1e-9,
                                        "project rule %s = %s is below JLCPCB's %s" % (rule, self.rules[rule], floor))

    def test_project_silk_rules_against_jlc(self):
        """Reported, not asserted: the board-level silk already meets these (test_silk), but DRC would
        let a footprint's own text or a later edit go below them."""
        for rule, floor in (("min_text_height", jlc.SILK_TEXT_MIN), ("min_text_thickness", jlc.SILK_LINE_MIN),
                            ("min_silk_clearance", jlc.SILK_TO_PAD_MIN)):
            if self.rules[rule] < floor:
                NOTES.append("finding: project rule %s = %s is below JLCPCB's %s; DRC won't flag silk that "
                             "JLCPCB may not print legibly" % (rule, self.rules[rule], floor))

    # --- each via ----------------------------------------------------------------------------
    def test_every_via_drill_and_ring(self):
        for v in self.vias:
            ring = (v["size"] - v["drill"]) / 2
            with self.subTest(via=tuple(v["pos"])):
                self.assertGreaterEqual(v["drill"], jlc.VIA_DRILL_MIN)
                self.assertGreaterEqual(v["size"], jlc.VIA_DIAMETER_MIN)
                self.assertGreaterEqual(ring, jlc.VIA_RING_MIN - 1e-6)
        sizes = sorted({(v["size"], v["drill"]) for v in self.vias})
        NOTES.append("%d vias in %d sizes (diameter/drill mm): %s" % (len(self.vias), len(sizes), sizes))

    def test_hole_to_hole(self):
        worst = []
        for i, a in enumerate(self.holes):
            for b in self.holes[i + 1:]:
                edge = math.hypot(a[2] - b[2], a[3] - b[3]) - a[4] / 2 - b[4] / 2
                if a[1].split(".")[0] == b[1].split(".")[0] != "via":
                    continue                     # two holes of one part: the footprint's own design
                limit = jlc.VIA_TO_VIA_MIN if a[0] == b[0] == "via" else jlc.PAD_HOLE_TO_HOLE_MIN
                worst.append((edge, limit, a[1], b[1], (round(a[2], 2), round(a[3], 2))))
        worst.sort()
        NOTES.append("closest holes: %.2f mm edge to edge (%s and %s at %s)" % (worst[0][0], worst[0][2], worst[0][3], worst[0][4]))
        bad = [w for w in worst if w[0] < w[1] - 1e-6]
        self.assertEqual(bad, [])

    def test_hole_to_other_net_copper(self):
        """Drilling wanders (+/- 0.075 mm position): a hole too near another net's track can nick it."""
        bad, worst = [], (9, None)
        for kind, ref, x, y, drill, net in self.holes:
            limit = {"via": jlc.VIA_HOLE_TO_TRACK_MIN, "PTH": jlc.PTH_TO_TRACK_MIN, "NPTH": jlc.NPTH_TO_TRACK_MIN}[kind]
            for t in self.tracks:
                if t["net"] == net and kind != "NPTH":
                    continue
                d = seg_dist(x, y, t["a"][0], t["a"][1], t["b"][0], t["b"][1]) - drill / 2 - t["w"] / 2
                worst = min(worst, (d, (ref, t["net"])))
                if d < limit - 1e-6:
                    bad.append((ref, t["net"], round(d, 3), limit))
        NOTES.append("closest hole to another net's track: %.2f mm (%s)" % worst)
        self.assertEqual(bad, [])

    def test_vias_beside_smd_pads(self):
        """A via inside a pad wicks solder away; one beside a pad's mask opening can be exposed by mask
        misregistration. JLCPCB wants mask openings at least 0.09 mm from neighbouring copper."""
        in_pad, close = [], []
        for v in self.vias:
            r = v["size"] / 2
            for ref, fp, p in self.pads:
                if p["attr"] != "SMD" or not p["copper"]:
                    continue
                d = box_dist(v["pos"][0], v["pos"][1], p["bbox"]) - r
                if d < 0:
                    in_pad.append((ref, p["number"], tuple(v["pos"])))
                elif d < jlc.MASK_TO_TRACE_MIN and p["net"] != v["net"]:
                    close.append((ref, p["number"], round(d, 3)))
        self.assertEqual(in_pad, [], "via in pad")
        self.assertEqual(close, [], "via copper within %.2f mm of another net's mask opening" % jlc.MASK_TO_TRACE_MIN)

    def test_vias_under_parts(self):
        """Reported: vias under a part are fine when tented (test_fab_files checks that), but worth knowing
        for the hand-soldered module and anything with a metal body."""
        under = {}
        for ref, fp in self.f["footprints"].items():
            c = fp.get("courtyard")
            if not c:
                continue
            n = sum(1 for v in self.vias if box_dist(v["pos"][0], v["pos"][1], c) == 0)
            if n:
                under[ref] = n
        NOTES.append("vias inside courtyards: %s" % under)

    # --- mounting holes ----------------------------------------------------------------------
    def mounting_holes(self):
        return [(ref, fp["pos"], fp["pads"][0]) for ref, fp in self.f["footprints"].items() if ref.startswith("H")]

    def test_mounting_holes_take_an_m2_screw(self):
        for ref, pos, p in self.mounting_holes():
            with self.subTest(hole=ref):
                self.assertEqual(p["attr"], "NPTH")
                lo, hi = p["drill"] - jlc.DRILL_TOL_MINUS, p["drill"] + jlc.DRILL_TOL_PLUS
                self.assertGreaterEqual(lo, M2_CLEAR[0], "can come out too tight for M2")
                self.assertLessEqual(hi, M2_CLEAR[1], "can come out too loose")
        p = self.mounting_holes()[0][2]
        NOTES.append("M2 holes drilled %.2f, finished %.2f-%.2f mm after JLCPCB's tolerance"
                     % (p["drill"], p["drill"] - jlc.DRILL_TOL_MINUS, p["drill"] + jlc.DRILL_TOL_PLUS))

    def test_screw_head_keepout_is_clear_on_both_faces(self):
        """Nothing but ground under an M2 head: a metal head on worn mask must not touch a signal.
        Ground copper there is reported, not failed."""
        for ref, pos, p in self.mounting_holes():
            x, y = pos
            copper = [("track", t["net"], seg_dist(x, y, t["a"][0], t["a"][1], t["b"][0], t["b"][1]) - t["w"] / 2)
                      for t in self.tracks]
            copper += [("via", v["net"], math.hypot(v["pos"][0] - x, v["pos"][1] - y) - v["size"] / 2) for v in self.vias]
            copper += [("pad %s.%s" % (r, q["number"]), q["net"], box_dist(x, y, q["bbox"]))
                       for r, fp, q in self.pads if r != ref and q["copper"] and q["attr"] != "NPTH"]
            inside = [(k, n, round(d, 2)) for k, n, d in copper if d < SCREW_KEEPOUT_R]
            gnd = [c for c in inside if c[1] == "GND"]
            if gnd:
                NOTES.append("%s: ground copper under the screw head: %s" % (ref, gnd))
            parts = [r for r, fp in self.f["footprints"].items()
                     if r != ref and fp.get("courtyard") and box_dist(x, y, fp["courtyard"]) < SCREW_KEEPOUT_R - 0.5]
            with self.subTest(hole=ref):
                self.assertEqual([c for c in inside if c[1] != "GND"], [], "signal copper under the screw head")
                self.assertEqual(parts, [], "a part under the screw head")

    def test_holes_clear_the_board_edge(self):
        for kind, ref, x, y, drill, net in self.holes:
            edge = min(x, y, self.W - x, self.H - y) - drill / 2
            with self.subTest(hole=ref):
                self.assertGreaterEqual(edge, 1.0 if kind == "NPTH" else jlc.COPPER_TO_OUTLINE_MIN)

    def test_component_holes_after_drill_tolerance(self):
        """Reported: the finished size band of each part's holes, to hold against its datasheet's pin."""
        seen = {}
        for ref, fp, p in self.pads:
            if p["attr"] in ("PTH", "NPTH") and not ref.startswith("H"):
                key = (ref, p["attr"], tuple(p["drill_xy"]))
                seen[key] = seen.get(key, 0) + 1
        for (ref, attr, (dx, dy)), n in sorted(seen.items()):
            w = min(dx, dy)
            NOTES.append("%s: %d x %s %s, finished width %.2f-%.2f mm%s"
                         % (ref, n, attr, ("slot %.2f x %.2f" % (dx, dy)) if dx != dy else "%.2f" % dx,
                            w - jlc.DRILL_TOL_MINUS, w + jlc.DRILL_TOL_PLUS,
                            "" if attr == "NPTH" else "; check the pin/tab against the low end"))

    # --- copper connections for soldering ----------------------------------------------------
    def test_module_ground_pads_use_thermal_spokes(self):
        """U1 is soldered by hand: a castellation pad sunk straight into the back pour won't take solder."""
        back = next(z for z in self.f["zones"] if z["name"] == "GND" and z["layer"] == "B.Cu")
        for p in self.f["footprints"]["U1"]["pads"]:
            if p["net"] != "GND" or p["number"] == "41":      # 41: the exposed pad, needn't be soldered
                continue
            mode = p["zone_connection"] if p["zone_connection"] != "inherited" else back["pad_connection"]
            with self.subTest(pad=p["number"]):
                self.assertEqual(mode, "thermal")

    def test_small_passives_meet_the_front_pour_through_spokes(self):
        """A two-pad part with one end sunk solid in the front GND pour and the other on a thin track
        heats unevenly in reflow: the classic cause of tombstoning. Every such GND pad must be thermal."""
        front = next(z for z in self.f["zones"] if z["name"] == "GND" and z["layer"] == "F.Cu")
        for ref, fp in self.f["footprints"].items():
            pads = [p for p in fp["pads"] if p["attr"] == "SMD" and "F.Cu" in p["copper"]]
            if len(pads) != 2:
                continue
            for p in pads:
                if p["net"] != "GND":
                    continue
                mode = p["zone_connection"] if p["zone_connection"] != "inherited" else front["pad_connection"]
                with self.subTest(pad="%s.%s" % (ref, p["number"])):
                    self.assertEqual(mode, "thermal")

def write_table(cls):
    path = common.scratch("holes", "holes.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "ref", "x", "y", "drill", "diameter", "ring", "net", "nearest hole (edge)", "nearest other-net track (edge)"])
        for kind, ref, x, y, drill, net in cls.holes:
            dia = next((v["size"] for v in cls.vias if v["pos"] == [x, y]), None) if kind == "via" else None
            if dia is None and kind != "via":
                pad = next(p for r, fp, p in cls.pads if "%s.%s" % (r, p["number"]) == ref and p["pos"] == [x, y])
                dia = min(pad["size"]) if kind == "PTH" else None
            nh = min((math.hypot(x - h[2], y - h[3]) - drill / 2 - h[4] / 2 for h in cls.holes if (h[2], h[3]) != (x, y)), default=None)
            nt = min((seg_dist(x, y, t["a"][0], t["a"][1], t["b"][0], t["b"][1]) - drill / 2 - t["w"] / 2
                      for t in cls.tracks if t["net"] != net or kind == "NPTH"), default=None)
            w.writerow([kind, ref, x, y, drill, dia or "", "%.3f" % ((dia - drill) / 2) if dia else "", net,
                        "%.3f" % nh if nh is not None else "", "%.3f" % nt if nt is not None else ""])


if __name__ == "__main__":
    unittest.main()
