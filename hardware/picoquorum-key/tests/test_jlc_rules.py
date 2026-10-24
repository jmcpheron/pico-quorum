"""JLCPCB's limits as DRC rules: hardware/picoquorum-key/picoquorum-key.kicad_dru, held to tests/jlc_limits.py.

KiCad reads picoquorum-key.kicad_dru beside the board on every DRC, in the editor as you route and in
tools/export.sh, which refuses to export with a violation. The rule file only carries what the
project's own minimums (Board Setup > Constraints) don't already cover. This module checks:
- every number in jlc_limits.py is enforced somewhere: a project minimum at least as strict, a rule
  in the file with the same number, or a named test (some limits aren't DRC rules: drill tolerance);
- the routed board passes the rule file;
- each rule fires: with its number pushed past the board, DRC flags it under the rule's own name,
  on the kind of item it is meant for (a rule with a typo in its condition matches nothing and
  would otherwise pass silently);
- two faults the project's minimums let through are caught by the file alone.
"""
import json
import os
import re
import unittest

import common
import jlc_limits as jlc
import mutation as m

DRU = os.path.join(common.PRJ, "picoquorum-key.kicad_dru")
PRO = os.path.join(common.PRJ, "picoquorum-key.kicad_pro")

# rule name -> (constraint, "min"/"max", limit name, item kind the rule must flag)
RULES = {
    "JLC: plated hole annular ring": ("annular_width", "min", "PTH_RING_MIN", "PTH pad"),
    "JLC: plated hole to other copper": ("hole_clearance", "min", "PTH_TO_TRACK_MIN", "PTH pad"),
    "JLC: non-plated hole size": ("hole_size", "min", "NPTH_DRILL_MIN", "NPTH pad"),
    "JLC: largest drill": ("hole_size", "max", "DRILL_MAX", "Via"),
}
# every limit in jlc_limits.py -> where it is enforced
COVERAGE = {
    "TRACK_MIN": ("project", "min_track_width"),
    "SPACE_MIN": ("project", "min_clearance"),
    "PAD_TO_PAD_MIN": ("project", "min_clearance"),
    "COPPER_TO_OUTLINE_MIN": ("project", "min_copper_edge_clearance"),
    "VIA_DRILL_MIN": ("project", "min_through_hole_diameter"),
    "VIA_DIAMETER_MIN": ("project", "min_via_diameter"),
    "VIA_RING_MIN": ("project", "min_via_annular_width"),
    "VIA_RING_PREFERRED": ("project", "min_via_annular_width"),
    "VIA_TO_VIA_MIN": ("project", "min_hole_to_hole"),
    "VIA_HOLE_TO_TRACK_MIN": ("project", "min_hole_clearance"),
    "PTH_DRILL_MIN": ("project", "min_through_hole_diameter"),
    "PAD_HOLE_TO_HOLE_MIN": ("project", "min_hole_to_hole"),
    "NPTH_TO_TRACK_MIN": ("project", "min_hole_clearance"),
    "SILK_TEXT_MIN": ("project", "min_text_height"),
    "SILK_TO_PAD_MIN": ("project", "min_silk_clearance"),
    "PTH_RING_MIN": ("rule", "JLC: plated hole annular ring"),
    "PTH_TO_TRACK_MIN": ("rule", "JLC: plated hole to other copper"),
    "NPTH_DRILL_MIN": ("rule", "JLC: non-plated hole size"),
    "DRILL_MAX": ("rule", "JLC: largest drill"),
    # not expressible as a KiCad rule (KiCad can't tell a slot from a round hole in a condition,
    # and nothing checks a tolerance): checked from the fab files or the board by these tests
    "MASK_DAM_MIN": ("test", "test_fab_files"),   # KiCad's solder_mask_min_width would do it in DRC,
                                                   # but then plots merged mask regions, not pad openings
    "PTH_RING_PREFERRED": ("test", "test_fab_files"),
    "PLATED_SLOT_WIDTH_MIN": ("test", "test_fab_files"),
    "NPTH_SLOT_WIDTH_MIN": ("test", "test_fab_files"),
    "DRILL_TOL_PLUS": ("test", "test_holes"),
    "DRILL_TOL_MINUS": ("test", "test_holes"),
    "MASK_TO_TRACE_MIN": ("test", "test_holes"),
    "SILK_LINE_MIN": ("test", "test_holes"),
    "HOLE_POSITION_TOL": ("info", "JLCPCB's own placement tolerance; nothing on this board is closer to a hole than it"),
}
NOTES = []


def read_rules(path=DRU):
    """{rule name: {constraint: {"min": mm, "max": mm}}, "_condition": str} from a .kicad_dru."""
    text = "\n".join(l for l in open(path).read().splitlines() if not l.lstrip().startswith("#"))
    tree = common.parse("(dru " + text + ")")
    out = {}
    for r in common.find_all(tree, "rule"):
        name = str(r[1])
        entry = {"_condition": str(common.find(r, "condition")[1])}
        for c in common.find_all(r, "constraint"):
            entry[str(c[1])] = {str(b[0]): float(str(b[1]).replace("mm", "")) for b in c[2:] if isinstance(b, list)}
        out[name] = entry
    return out


def drc_json(pcb, tag):
    out = common.scratch("jlc_rules", tag + "-drc.json")
    common.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "-o", out, pcb])
    with open(out) as f:
        return json.load(f)["violations"]


def jlc_hits(violations):
    """[(rule name, first item's description)] for violations raised by a JLC rule."""
    hits = []
    for v in violations:
        mm = re.search(r"rule '(JLC:[^']*)'", v["description"])
        if mm:
            hits.append((mm.group(1), v["items"][0]["description"]))
    return hits


class JlcRules(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if NOTES:
            print("\njlc rule notes:\n  " + "\n  ".join(NOTES))

    @classmethod
    def setUpClass(cls):
        cls.rules = read_rules()
        with open(PRO) as f:
            cls.pro = json.load(f)["board"]["design_settings"]["rules"]

    def test_rule_numbers_are_jlcs(self):
        self.assertEqual(set(self.rules), set(RULES), "rules in the file vs the rules this test knows")
        for name, (constraint, bound, limit, _) in RULES.items():
            with self.subTest(rule=name):
                self.assertAlmostEqual(self.rules[name][constraint][bound], getattr(jlc, limit), places=4)

    def test_every_jlc_limit_is_enforced_somewhere(self):
        limits = {k for k in vars(jlc) if k.isupper() and k != "SOURCE"}
        self.assertEqual(limits - set(COVERAGE), set(), "limits in jlc_limits.py with nowhere enforcing them")
        self.assertEqual(set(COVERAGE) - limits, set(), "coverage entries for limits that no longer exist")
        for limit, (where, what) in sorted(COVERAGE.items()):
            value = getattr(jlc, limit)
            with self.subTest(limit=limit):
                if where == "project":
                    self.assertGreaterEqual(self.pro[what] + 1e-9, value, "%s %.3f is below JLC's %.3f" % (what, self.pro[what], value))
                elif where == "rule":
                    self.assertIn(what, self.rules)
                elif where == "test":
                    src = open(os.path.join(common.ROOT, "tests", what + ".py")).read()
                    self.assertIn("jlc." + limit, src, "%s doesn't use jlc.%s" % (what, limit))
        NOTES.append("JLC limits: %d by project minimums, %d by the rule file, %d by other tests, %d informational"
                     % tuple(sum(1 for w, _ in COVERAGE.values() if w in ks)
                             for ks in (("project",), ("rule",), ("test",), ("info",))))

    def test_routed_board_passes_the_rules(self):
        self.assertEqual(jlc_hits(drc_json(common.PCB, "board")), [])

    def test_each_rule_fires_on_its_own_items(self):
        """Push every number past the board's real values: each rule must flag, under its own name,
        an item of the kind it is for."""
        prj = m.fresh_project("jlc-rules-tight")
        path = os.path.join(prj, "picoquorum-key.kicad_dru")
        text = open(path).read()
        tight = {"annular_width (min 0.18mm)": "annular_width (min 0.5mm)",
                 "hole_clearance (min 0.28mm)": "hole_clearance (min 2.0mm)",
                 "hole_size (min 0.5mm) (max 6.3mm)": "hole_size (min 3.0mm) (max 6.3mm)",
                 "hole_size (max 6.3mm))": "hole_size (max 0.35mm))"}
        for a, b in tight.items():
            self.assertIn(a, text)
            text = text.replace(a, b)
        open(path, "w").write(text)
        hits = jlc_hits(drc_json(os.path.join(prj, "picoquorum-key.kicad_pcb"), "tight"))
        for name, (_, _, _, kind) in RULES.items():
            with self.subTest(rule=name):
                items = [d for r, d in hits if r == name]
                self.assertTrue(items, "rule never fired")
                self.assertTrue(any(d.startswith(kind) for d in items), "%s flagged only %s" % (kind, sorted(set(items))[:3]))

    def run_mutant(self, name, mutate):
        """DRC on a mutant with the rule file and without it: (JLC hits, other violations without it)."""
        prj = m.fresh_project(name)
        tree = m.load_pcb(prj)
        mutate(tree)
        m.save_pcb(prj, tree)
        pcb = os.path.join(prj, "picoquorum-key.kicad_pcb")
        with_rules = jlc_hits(drc_json(pcb, name))
        os.remove(os.path.join(prj, "picoquorum-key.kicad_dru"))
        without = drc_json(pcb, name + "-norules")
        return with_rules, without

    def test_thin_ring_on_the_usb_shell_is_caught_only_by_the_rule_file(self):
        """J1's shell tabs with a 0.15 mm ring: above the project's 0.13 mm, below JLC's 0.18."""
        def mutate(tree):
            for p in m.find_all(m.footprint(tree, "J1"), "pad"):
                if str(p[2]) == "thru_hole":
                    drill, size = m.find(p, "drill"), m.find(p, "size")
                    d = [float(v) for v in drill[1:] if not isinstance(v, list) and v != "oval"]
                    size[1], size[2] = "%g" % (d[0] + 0.30), "%g" % (d[-1] + 0.30)
        hits, without = self.run_mutant("jlc-thin-ring", mutate)
        self.assertIn("JLC: plated hole annular ring", {r for r, _ in hits})
        self.assertNotIn("annular_width", {v["type"] for v in without}, "the project's own minimum caught it too")

    def test_small_mounting_hole_is_caught_only_by_the_rule_file(self):
        """H1 drilled 0.45 mm: the project allows 0.3 mm holes, JLC won't drill an NPTH under 0.5."""
        def mutate(tree):
            p = m.find(m.footprint(tree, "H1"), "pad")
            m.find(p, "drill")[1] = "0.45"
            s = m.find(p, "size")
            s[1] = s[2] = "0.45"
        hits, without = self.run_mutant("jlc-small-hole", mutate)
        self.assertIn("JLC: non-plated hole size", {r for r, _ in hits})
        self.assertNotIn("drill_out_of_range", {v["type"] for v in without})


if __name__ == "__main__":
    unittest.main()
