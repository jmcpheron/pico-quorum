"""Mutation testing of the checks themselves.

Inject one fault at a time into a scratch copy of the board (or its netlist) and require the
existing tooling to notice. A mutant that survives is a hole in the checks, not in the board.
A clean, round-tripped copy runs first as the negative control: if that fails, no kill means anything.
"""
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

import common
import mutation as m
from sexp import dumps, find, find_all

# name -> (mutator, DRC violation types of which at least one must appear)
BOARD_MUTANTS = {
    "open: all LED_A copper deleted": (m.delete_net_copper("LED_A"), {"unconnected_items"}),
    "open: BOOT via deleted": (m.delete_one_via("BOOT"), {"unconnected_items"}),
    "short: track bridges BTN_SIGN and BTN_NEXT": (m.bridge_tracks("BTN_SIGN", "BTN_NEXT"),
                                                  {"clearance", "shorting_items", "tracks_crossing"}),
    "swap: R6 pads exchanged": (m.swap_pad_nets("R6", "1", "2"), {"net_conflict", "shorting_items"}),
    "parity: R5 removed": (m.remove_footprint("R5"), {"missing_footprint"}),
    "width: LCD_CS track thinned to 0.1 mm": (m.thin_segment("LCD_CS", 0.1), {"track_width"}),
    "overlap: C8 stacked on C1": (m.move_footprint_onto("C8", "C1"), {"courtyards_overlap", "clearance"}),
    "antenna: LCD_SCK track in the band": (m.track_into_antenna_band("LCD_SCK"), {"items_not_allowed"}),
    "antenna: BOOT via in the band": (m.via_into_antenna_band("BOOT"), {"items_not_allowed"}),
    "edge: mounting hole H1 on the board edge": (m.move_hole_to_edge("H1"),
                                                 {"hole_clearance", "copper_edge_clearance"}),
    "silk: RESET label dragged onto SW7's pad": (m.move_silk_text_onto_pad("RESET", "SW7", "1"),
                                                {"silk_over_copper", "silk_overlap"}),
}

MATRIX = []


def run_board_mutant(item):
    name, (mutate, _expected) = item
    tag = "m%02d" % list(BOARD_MUTANTS).index(name)
    prj = m.fresh_project(tag)
    tree = m.load_pcb(prj)
    mutate(tree)
    m.save_pcb(prj, tree)
    return name, m.drc(prj, tag)


def check_netlist(net_file):
    return subprocess.run([sys.executable, os.path.join(common.ROOT, "tools", "gen", "check_netlist.py"), net_file],
                          capture_output=True, text=True)


class Mutation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prj = m.fresh_project("control")
        m.save_pcb(prj, m.load_pcb(prj))          # parse -> write, no change
        cls.control = m.drc(prj, "control")
        with ThreadPoolExecutor(max_workers=4) as pool:
            cls.results = dict(pool.map(run_board_mutant, BOARD_MUTANTS.items()))

    @classmethod
    def tearDownClass(cls):
        lines = ["%-46s %-9s %s" % ("mutant", "result", "violations found")]
        for name, (code, types, n) in cls.results.items():
            expected = BOARD_MUTANTS[name][1]
            lines.append("%-46s %-9s %s" % (name, "killed" if types & expected else "SURVIVED", sorted(types)))
        lines += ["", "\n".join("%-46s %-9s %s" % row for row in MATRIX)]
        text = "\n".join(lines)
        with open(common.scratch("kill_matrix.txt"), "w") as f:
            f.write(text + "\n")
        print("\n" + text)

    def test_negative_control_round_trip_is_clean(self):
        code, types, n = self.control
        self.assertEqual((code, types, n), (0, set(), 0))

    def test_every_board_mutant_is_caught_by_drc(self):
        for name, (_mutate, expected) in BOARD_MUTANTS.items():
            with self.subTest(mutant=name):
                code, types, n = self.results[name]
                self.assertNotEqual(code, 0, "DRC exited 0: the fault went unnoticed")
                self.assertTrue(types & expected, "expected one of %s, DRC reported %s" % (sorted(expected), sorted(types)))

    # --- the schematic-vs-circuit.py check ---------------------------------------------------
    def test_check_netlist_catches_netlist_faults(self):
        common.sch_pad_nets()                                      # writes scratch/test/sch.net
        good = common.scratch("sch.net")
        base = check_netlist(good)
        self.assertEqual(base.returncode, 0, base.stdout)
        MATRIX.append(("check_netlist: unmodified netlist", "clean" if base.returncode == 0 else "FAILED", ""))

        def swap_names(tree):
            nets = find(tree, "nets")
            by = {str(find(n, "name")[1]).lstrip("/"): n for n in find_all(nets, "net")}
            a, b = by["I2C_SDA"], by["I2C_SCL"]
            find(a, "name")[1], find(b, "name")[1] = find(b, "name")[1], find(a, "name")[1]

        def drop_component(tree):
            comps = find(tree, "components")
            comps.remove(next(c for c in find_all(comps, "comp") if str(find(c, "ref")[1]) == "R5"))

        def move_pin(tree):
            nets = find(tree, "nets")
            by = {str(find(n, "name")[1]).lstrip("/"): n for n in find_all(nets, "net")}
            node = next(x for x in find_all(by["LCD_CS"], "node") if str(find(x, "ref")[1]) == "U1")
            by["LCD_CS"].remove(node)
            by["LCD_DC"].append(node)

        for label, fn in (("SDA/SCL net names swapped", swap_names), ("R5 missing", drop_component),
                          ("U1 LCD_CS pin moved to LCD_DC", move_pin)):
            with self.subTest(mutant=label):
                tree = common.tree_of(good)
                fn(tree)
                path = common.scratch("sch-mut.net")
                with open(path, "w") as f:
                    f.write(dumps(tree))
                r = check_netlist(path)
                MATRIX.append(("check_netlist: " + label, "killed" if r.returncode else "SURVIVED", ""))
                self.assertNotEqual(r.returncode, 0, "check_netlist.py accepted: " + label)


if __name__ == "__main__":
    unittest.main()
