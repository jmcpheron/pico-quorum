"""Geometry and placement: the numbers in docs/DESIGN.md, asserted against the routed board.

pcb_facts.py (run under KiCad's Python) dumps the board to JSON in millimetres relative to the
board's top-left corner, the same frame as DESIGN.md's placement table.
"""
import ast
import json
import math
import os
import unittest

import common

TOL = 0.1            # mm; the placement table is exact, this only absorbs float rounding
ANT = 7.0            # antenna band, Y 0..7: no pour anywhere, no copper over the module (ANT_X in gen_pcb)
POUR_START = 7.5
GLASS_X1, FOLD_X1 = 46.0, 46.5      # glass right edge, and how far the fold stands proud of it
FOLD_Y0, FOLD_Y1 = 13.9, 23.0
DECOUPLING_MAX = 5.0  # mm, capacitor pad to the supply pad it decouples
USB_SKEW_MAX = 10.0   # mm; USB full speed (12 Mbit/s) tolerates far more, this is a sanity bound

# DESIGN.md "placement" table: ref -> (x, y)
PLACEMENT = {
    "U1": (39, 12.75), "J2": (26.5, 17.3), "SW1": (10.5, 10.7), "SW2": (10.5, 17.3), "SW3": (10.5, 23.9),
    "SW6": (42, 39), "SW7": (42, 46), "R4": (37, 39),
    "Q1": (21, 30), "Q2": (21, 34), "D1": (31.5, 29), "U2": (38, 31.5), "U3": (16, 39.5),
    "U4": (28, 39.5), "C6": (23.85, 20.2), "C2": (19.27, 44.2), "R5": (29.5, 23),
    "H1": (3, 29.5), "H2": (47, 29.5), "H3": (3, 50), "H4": (47, 50),
    "C3": (46.85, 9.6), "C5": (48.85, 9.6),
    # rev B's key port
    "J3": (8, 0), "U6": (16.6, 4.6), "U7": (20.8, 4.6), "U5": (4, 38), "D3": (2.2, 5.6), "D4": (2.2, 11.0),
}
POUR_STEP_X = 16.2      # gen_pcb.GND_POUR: the step under U6
# panel pin n -> net, from DESIGN.md: LEDA GND RESET RS SDA SCL VDD CS
PANEL = ["BL_A", "GND", "LCD_RST", "LCD_DC", "LCD_MOSI", "LCD_SCK", "+3V3", "LCD_CS"]
# (capacitor, supply pad it decouples)
DECOUPLING = [("C3", "U1", "2"), ("C5", "U1", "2"), ("C7", "U2", "8"),
              ("C2", "U3", "2"), ("C6", "J2", "2")]                              # held to DECOUPLING_MAX
DECOUPLING_INFO = [("C1", "U3", "3"), ("C8", "U3", "3")]                         # LDO input: reported only
NOTES = []


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def ipc2221_amps(width_mm, temp_rise=10.0, oz=1.0):
    """External-layer current capacity (IPC-2221): I = 0.048 * dT^0.44 * A^0.725, A in mil^2."""
    area = (width_mm / 0.0254) * (oz * 1.378)
    return 0.048 * temp_rise ** 0.44 * area ** 0.725


def read_consts(path, names):
    with open(path) as f:
        tree = ast.parse(f.read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            tgt = node.targets[0]
            targets = tgt.elts if isinstance(tgt, ast.Tuple) else [tgt]
            try:
                vals = ast.literal_eval(node.value)
            except ValueError:
                continue
            vals = vals if isinstance(tgt, ast.Tuple) else [vals]
            for t, v in zip(targets, vals):
                if getattr(t, "id", None) in names:
                    out[t.id] = v
    return out


class Geometry(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if NOTES:
            print("\nnotes:\n  " + "\n  ".join(NOTES))

    @classmethod
    def setUpClass(cls):
        cls.f = common.board_facts()
        cls.fp = cls.f["footprints"]

    def pad(self, ref, number):
        return next(p for p in self.fp[ref]["pads"] if p["number"] == str(number))

    # --- outline and placement ----------------------------------------------------------------
    def test_board_is_50_by_53(self):
        self.assertAlmostEqual(self.f["board"]["w"], 50, delta=TOL)
        self.assertAlmostEqual(self.f["board"]["h"], 53, delta=TOL)

    def test_placement_table(self):
        for ref, (x, y) in PLACEMENT.items():
            with self.subTest(ref=ref):
                px, py = self.fp[ref]["pos"]
                self.assertAlmostEqual(px, x, delta=TOL)
                self.assertAlmostEqual(py, y, delta=TOL)

    def test_sides(self):
        self.assertEqual(self.fp["U1"]["layer"], "B.Cu", "the module is hand-soldered on the back")
        for i in range(1, 15):
            self.assertEqual(self.fp["TP%d" % i]["layer"], "B.Cu")
        for ref in ("J1", "J2", "J3", "U2", "U3", "SW1", "D1"):
            self.assertEqual(self.fp[ref]["layer"], "F.Cu", ref)

    def test_test_pads_grid(self):
        for i in range(12):
            with self.subTest(tp=i + 1):
                x, y = self.fp["TP%d" % (i + 1)]["pos"]
                self.assertAlmostEqual(x, 15 + 5.2 * (i % 6), delta=TOL)
                self.assertAlmostEqual(y, 35 + 4 * (i // 6), delta=TOL)
                self.assertEqual(self.fp["TP%d" % (i + 1)]["pads"][0]["size"], [1.5, 1.5])
        for ref, (x, y) in (("TP13", (8.4, 43)), ("TP14", (15, 43))):      # the key port's bus (rev B)
            with self.subTest(tp=ref):
                self.assertEqual(self.fp[ref]["pos"], [x, y])
                self.assertEqual(self.fp[ref]["pads"][0]["size"], [1.5, 1.5])

    def test_usb_connector_centred_and_inside_outline(self):
        self.assertAlmostEqual(self.fp["J1"]["pos"][0], 28, delta=TOL)
        for p in self.fp["J1"]["pads"]:
            self.assertLessEqual(p["bbox"][3], 53 + TOL)

    def test_no_mounting_hole_in_top_29mm(self):
        for h in ("H1", "H2", "H3", "H4"):
            self.assertGreaterEqual(self.fp[h]["pos"][1], 29 - TOL)

    # --- buttons level with the screen rows (links firmware profile to layout) -----------------
    def test_rail_buttons_sit_on_the_screen_rows(self):
        prof = read_consts(os.path.join(common.ROOT, "firmware", "profile", "picoquorum_key.py"), {"RAIL_Y", "LCD_H"})
        gen = read_consts(os.path.join(common.ROOT, "tools", "gen", "gen_pcb.py"), {"AA"})
        x0, y0, x1, y1 = gen["AA"]
        pitch = (y1 - y0) / prof["LCD_H"]
        for ref, row in zip(("SW1", "SW2", "SW3"), prof["RAIL_Y"]):
            with self.subTest(ref=ref, row=row):
                self.assertAlmostEqual(self.fp[ref]["pos"][1], y0 + (row + 0.5) * pitch, delta=0.06)

    # --- antenna band --------------------------------------------------------------------------
    def test_antenna_band_has_no_copper_over_the_module(self):
        """Rev B: the band's copper-free part is the module's antenna end plus 0.5 mm (X 29.5 on); the
        key port's plug and its tracks use the band's other end (test_key_port checks the rule area)."""
        x_ant = read_consts(os.path.join(common.ROOT, "tools", "gen", "gen_pcb.py"), {"ANT_X"})["ANT_X"][0]
        bad = []
        for t in self.f["tracks"]:
            pts = [[t["a"][k] + (t["b"][k] - t["a"][k]) * i / 100 for k in (0, 1)] for i in range(101)]
            if any(y - t["w"] / 2 < ANT - 1e-6 and x + t["w"] / 2 > x_ant for x, y in pts):
                bad.append("track %s at %s" % (t["net"], t["a"]))
        for v in self.f["vias"]:
            if v["pos"][1] - v["size"] / 2 < ANT - 1e-6 and v["pos"][0] + v["size"] / 2 > x_ant:
                bad.append("via %s at %s" % (v["net"], v["pos"]))
        for ref, fp in self.fp.items():
            for p in fp["pads"]:
                if p["copper"] and p["bbox"][1] < ANT - 1e-6 and p["bbox"][2] > x_ant:
                    bad.append("pad %s.%s" % (ref, p["number"]))
        self.assertEqual(bad, [], "copper over the module's antenna")

    def test_antenna_keepout_covers_both_layers_and_the_module(self):
        areas = [z for z in self.f["zones"] if z["rule_area"] and z["name"] == "antenna keep-out"]
        self.assertEqual({z["layer"] for z in areas}, {"F.Cu", "B.Cu"})
        for z in areas:
            (x0, y0), (x1, y1) = z["outline"]
            self.assertLessEqual(x0, self.fp["U1"]["pos"][0] - 9.0 - 0.5 + 1e-3)
            self.assertGreaterEqual(x1, 50)
            self.assertGreaterEqual(y1, ANT)

    def test_each_m2_hole_has_a_screw_keepout_on_both_layers(self):
        """A 2.5 mm keep-out round each hole: no track or via under an M2 head (3.8-4.0 mm) or washer."""
        for ref in ("H1", "H2", "H3", "H4"):
            with self.subTest(hole=ref):
                areas = [z for z in self.f["zones"] if z["rule_area"] and z["name"] == ref + " screw keep-out"]
                self.assertEqual({z["layer"] for z in areas}, {"F.Cu", "B.Cu"})
                hx, hy = self.fp[ref]["pos"]
                for z in areas:
                    (x0, y0), (x1, y1) = z["outline"]
                    self.assertAlmostEqual((x0 + x1) / 2, hx, delta=0.05)
                    self.assertAlmostEqual((y0 + y1) / 2, hy, delta=0.05)
                    self.assertGreaterEqual(min(x1 - x0, y1 - y0) / 2, 2.4)

    def test_ground_pours_start_at_7_5_but_in_the_plugs_corner(self):
        """Rev B: no pour above Y 7.5 except left of the slot (X < 14), the key port's corner, and a
        step to X 16.2 below Y 4.6 that reaches U6's ground pin; 13 mm and more from the antenna keep-out."""
        slot_x1 = read_consts(os.path.join(common.ROOT, "tools", "gen", "gen_pcb.py"), {"SLOT_X1"})["SLOT_X1"]
        pours = [z for z in self.f["zones"] if not z["rule_area"]]
        self.assertEqual({z["layer"] for z in pours}, {"F.Cu", "B.Cu"})
        for z in pours:
            with self.subTest(layer=z["layer"]):
                self.assertEqual(z["net"], "GND")
                high = [p for p in z["points"] if p[1] < POUR_START - 1e-3]
                self.assertTrue(high, "the corner pour is missing")
                self.assertTrue(all(p[0] <= slot_x1 + 1e-3 or (p[0] <= POUR_STEP_X + 1e-3 and p[1] >= 4.6 - 1e-3)
                                    for p in high), "pour above Y 7.5 right of the slot: %s" % high)

    def test_module_antenna_end_is_flush_with_the_top_edge(self):
        self.assertAlmostEqual(self.fp["U1"]["pos"][1] - 25.5 / 2, 0, delta=TOL)

    def test_no_via_or_hole_under_module_pad_41(self):
        # DESIGN.md: the footprint has none, and pad 41 is left unsoldered. The router's GND
        # stitching must not put one there either (post_route.py skips it).
        x0, y0, x1, y1 = self.pad("U1", 41)["bbox"]
        under = [v["pos"] for v in self.f["vias"]
                 if x0 - v["size"] / 2 < v["pos"][0] < x1 + v["size"] / 2 and y0 - v["size"] / 2 < v["pos"][1] < y1 + v["size"] / 2]
        self.assertEqual(under, [])
        self.assertEqual([p["number"] for p in self.fp["U1"]["pads"] if p["number"] != "41" and p["drill"] > 0
                          and x0 < p["pos"][0] < x1 and y0 < p["pos"][1] < y1], [])

    # --- panel connector -------------------------------------------------------------------
    def test_j2_pad_n_carries_panel_pin_9_minus_n(self):
        for n in range(1, 9):
            with self.subTest(pad=n):
                self.assertEqual(self.pad("J2", n)["net"], PANEL[9 - n - 1])

    def test_j2_pad_1_is_at_the_antenna_end(self):
        self.assertLess(self.pad("J2", 1)["pos"][1], self.pad("J2", 8)["pos"][1])

    def test_ribbon_fold_strip_is_free_of_front_parts(self):
        # The ribbon folds round the glass edge (X 46.0) and stands up to 0.5 mm proud of it, over
        # Y 13.9..23.0 (DESIGN.md). Nothing on the front may sit in that box.
        hits = []
        for ref, fp in self.fp.items():
            if fp["layer"] != "F.Cu":
                continue
            for p in fp["pads"]:
                x0, y0, x1, y1 = p["bbox"]
                if x0 < FOLD_X1 and x1 > GLASS_X1 and y1 > FOLD_Y0 and y0 < FOLD_Y1:
                    hits.append("%s.%s" % (ref, p["number"]))
        self.assertEqual(hits, [])

    # --- copper widths and current ---------------------------------------------------------------
    def test_no_track_below_minimum_width(self):
        thin = [t for t in self.f["tracks"] if t["w"] < 0.2 - 1e-6]
        self.assertEqual(thin, [])

    def test_supply_tracks_carry_500mA(self):
        for net in ("+5V", "+3V3"):
            with self.subTest(net=net):
                widths = [t["w"] for t in self.f["tracks"] if t["net"] == net]
                self.assertTrue(widths)
                self.assertGreaterEqual(ipc2221_amps(min(widths)), 0.5,
                                        "%s has a %.2f mm segment (%.2f A at +10 C)" % (net, min(widths), ipc2221_amps(min(widths))))

    # --- decoupling and USB ---------------------------------------------------------------------
    def decoupling_distance(self, cap, ic, pin):
        """Capacitor pad on the rail to the nearest pad numbered `pin` (a SOT-223 has a tab pad too)."""
        targets = [p for p in self.fp[ic]["pads"] if p["number"] == str(pin)]
        rail = targets[0]["net"]
        cap_pad = next(p for p in self.fp[cap]["pads"] if p["net"] == rail)
        return min(dist(cap_pad["pos"], t["pos"]) for t in targets)

    def test_decoupling_capacitors_are_close(self):
        for cap, ic, pin in DECOUPLING:
            with self.subTest(cap=cap, ic=ic, pin=pin):
                self.assertLessEqual(self.decoupling_distance(cap, ic, pin), DECOUPLING_MAX)

    def test_report_other_decoupling_distances(self):
        for cap, ic, pin in DECOUPLING_INFO:
            d = self.decoupling_distance(cap, ic, pin)
            NOTES.append("%s is %.1f mm from %s pin %s" % (cap, d, ic, pin))
            self.assertLess(d, 15, "%s is nowhere near %s" % (cap, ic))

    def net_length(self, *nets):
        return sum(t["len"] for t in self.f["tracks"] if t["net"] in nets)

    def test_usb_pair_skew(self):
        dp = self.net_length("USB_DP", "USB_DP_MCU")
        dn = self.net_length("USB_DN", "USB_DN_MCU")
        self.assertGreater(dp, 0)
        self.assertGreater(dn, 0)
        self.assertLessEqual(abs(dp - dn), USB_SKEW_MAX, "D+ %.1f mm, D- %.1f mm" % (dp, dn))


if __name__ == "__main__":
    unittest.main()
