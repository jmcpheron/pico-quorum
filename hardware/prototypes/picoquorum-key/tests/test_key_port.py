"""The key port (rev B): its circuit, which boards get it, and where it sits.

The circuit is read from the schematic's own netlist and circuit.py, the geometry from the routed
board (pcb_facts.py). What it holds the board to is docs/DESIGN.md, "The key port".
"""
import os
import re
import unittest

import common
import circuit
from test_geometry import read_consts

PORT_PARTS = {"J3", "U5", "U6", "U7", "D3", "D4", "D5", "C9", "C10", "R15", "R18", "R19", "R20", "R21", "R22", "R23"}
PLUG_TO_ANTENNA_MIN = 15.0      # mm, the plug's body to the antenna rule area: Espressif's ~15 mm from metal
TOL = 0.05


def members(nets, net):
    return {ref for (ref, _), n in nets.items() if n == net}


class Circuit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nets = common.sch_pad_nets()
        cls.parts = {p.ref: p for p in circuit.PARTS}

    def net(self, ref, pin):
        return self.nets[(ref, str(pin))]

    def test_fit_groups(self):
        """Every port part is fit 'port' and nothing else is, but R17: it stays on every board."""
        self.assertEqual({p.ref for p in circuit.PARTS if p.fit == "port"}, PORT_PARTS)
        self.assertEqual(self.parts["R17"].fit, "base")
        self.assertEqual({p.fit for p in circuit.PARTS}, set(circuit.FITS))

    def test_plug_wiring(self):
        """key-c's socket: SDA on D+ (A6), SCL on D- (A7), power on VBUS, one CC line, its LED's power on SBU."""
        want = {"A6": "KEY2_SDA", "A7": "KEY2_SCL", "A4": "VKEY", "A9": "VKEY", "B4": "VKEY", "B9": "VKEY",
                "A5": "KEY_CC_PLUG", "A8": "KEY_SBU", "B8": "KEY_SBU",
                "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND"}
        for pin, net in want.items():
            with self.subTest(pin=pin):
                self.assertEqual(self.net("J3", pin), net)
        for pin in ("B5", "B6", "B7", "A2", "A3", "A10", "A11", "B2", "B3", "B10", "B11"):
            with self.subTest(pin=pin):
                self.assertTrue(common.is_nc(self.net("J3", pin)), "J3.%s should be open" % pin)

    def test_the_key_is_off_until_firmware_powers_it(self):
        """U5's EN is pulled down (R15) and nothing pulls it up: an image that doesn't know the port, or
        a board at reset, leaves the key unpowered."""
        self.assertEqual(self.net("U5", 3), "KEY_EN")
        self.assertEqual({self.net("R15", 1), self.net("R15", 2)}, {"KEY_EN", "GND"})
        self.assertEqual(members(self.nets, "KEY_EN"), {"U1", "U5", "R15", "TP10"})
        self.assertEqual((self.net("U5", 1), self.net("U5", 6)), ("+3V3", "VKEY_SW"))
        self.assertEqual((self.net("D5", 2), self.net("D5", 1)), ("VKEY_SW", "VKEY"), "D5: anode on U5, cathode on the plug")
        self.assertEqual(self.net("U5", 5), "GND", "ILIM to GND: the 80 mA limit")

    def test_pull_ups_on_the_switched_rail_and_esd_rails_on_3v3(self):
        """The bus pull-ups go to U5's output, so a key that is off isn't fed through its bus; the ESD
        arrays' rails go to 3V3, never VKEY, so nothing feeds VKEY through them."""
        for ref, net in (("R19", "KEY2_SDA"), ("R20", "KEY2_SCL")):
            with self.subTest(ref=ref):
                self.assertEqual({self.net(ref, 1), self.net(ref, 2)}, {"VKEY_SW", net})
        for ref in ("U6", "U7"):
            with self.subTest(ref=ref):
                self.assertEqual(self.net(ref, 5), "+3V3")
        self.assertEqual(members(self.nets, "VKEY") - {"J3"}, {"D5", "D3", "R21", "R22", "R23"})
        self.assertEqual(members(self.nets, "VKEY_SW"), {"U5", "D5", "C10", "R19", "R20"})

    def test_esd_on_every_plug_line(self):
        """SBU has no array of its own: it is R21 from VKEY, so D3 clamps it through 100 ohms."""
        protected = {self.net(r, p) for r in ("U6", "U7") for p in (1, 3)} | {self.net("D3", 1)}
        protected -= {n for n in protected if common.is_nc(n)}
        self.assertEqual(protected, {"KEY2_SDA", "KEY2_SCL", "KEY_CC_PLUG", "VKEY"})
        self.assertEqual(members(self.nets, "KEY_SBU"), {"J3", "R21"})

    def test_5v_on_vbus_has_no_way_to_3v3(self):
        """5 V put on the plug's VBUS (VKEY) meets D5 reverse-biased, whether U5 is on or off (U5
        itself blocks only while off). Nothing else on VKEY leads to 3V3: no resistor from VKEY into a
        line with a diode to 3V3 (an ESD array's I/O, or a GPIO's clamp), and no part on VKEY but D5
        touches 3V3's side. Until 2026-10-26 R21 fed U7's diode (100 ohms), then R19/R20 (2.2k)."""
        esd_io = {self.net(r, p) for r in ("U4", "U6", "U7") for p in (1, 3, 4, 6)}
        gpio = {n for (r, _), n in self.nets.items() if r == "U1"}
        clamped = {n for n in esd_io | gpio if not common.is_nc(n)} - {"GND", "+3V3"}
        for ref in sorted(members(self.nets, "VKEY") - {"J3", "D5"}):
            on = {n for (r, _), n in self.nets.items() if r == ref}
            with self.subTest(ref=ref):
                self.assertFalse(on & (clamped | {"+3V3", "VKEY_SW"}), "%s joins VKEY to %s" % (ref, on))
        self.assertEqual(self.parts["D5"].lib_id, "Device:D_Schottky")

    def test_the_two_buses_are_apart(self):
        """The soldered chip and a key-c both answer at 0x60: no part touches both buses."""
        bus0, bus1 = {"I2C_SDA", "I2C_SCL"}, {"KEY2_SDA", "KEY2_SCL"}
        refs = {ref for (ref, _), n in self.nets.items()}
        for ref in sorted(refs - {"U1"}):
            on = {n for (r, _), n in self.nets.items() if r == ref}
            with self.subTest(ref=ref):
                self.assertFalse(on & bus0 and on & bus1, "%s is on both buses" % ref)
        self.assertEqual(members(self.nets, "I2C_SDA"), {"U1", "U2", "R6", "TP6"})

    def test_cc_reaches_the_plug_through_a_resistor(self):
        self.assertEqual({self.net("R17", 1), self.net("R17", 2)}, {"+3V3", "KEY_CC"})
        self.assertEqual({self.net("R18", 1), self.net("R18", 2)}, {"KEY_CC", "KEY_CC_PLUG"})

    def test_the_leds_run_off_the_keys_power(self):
        """No GPIO for them: the port's LED (D4) and a key-c P3's own (on SBU) light while VKEY is on."""
        self.assertEqual({self.net("R21", 1), self.net("R21", 2)}, {"VKEY", "KEY_SBU"})
        self.assertEqual({self.net("R22", 1), self.net("R22", 2)}, {"VKEY", "KEY_LED_A"})
        self.assertEqual((self.net("D4", 2), self.net("D4", 1)), ("KEY_LED_A", "GND"))
        self.assertTrue(common.is_nc(self.net("U5", 4)), "U5's FAULT is left open")

    def test_no_new_way_to_sign(self):
        """Rule 3: the port adds wires, a switch and protection, and no second key chip on the board."""
        keys = [p.ref for p in circuit.PARTS if "ATECC" in p.value]
        self.assertEqual(keys, ["U2"])


class Placement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = common.board_facts()
        cls.fp = cls.f["footprints"]
        cls.gen = read_consts(os.path.join(common.ROOT, "tools", "gen", "gen_pcb.py"),
                              {"PLUG_X", "ANT_X", "ANT_BAND", "GLASS", "THICKNESS", "NOTCH_D"})

    def test_board_is_0_8_mm(self):
        """The straddle plug grips a 0.80 +- 0.05 mm board."""
        self.assertEqual(self.gen["THICKNESS"], 0.8)
        with open(common.PCB) as f:
            m = re.search(r"\(general\s*\(thickness ([\d.]+)\)", f.read())
        self.assertAlmostEqual(float(m.group(1)), 0.8)

    def test_plug_sits_on_the_paddle_and_points_out_of_the_top_edge(self):
        j3 = self.fp["J3"]
        self.assertEqual(j3["layer"], "F.Cu")
        self.assertTrue(j3["dnp"], "J3 is fitted by hand: its pads are on both faces")
        self.assertAlmostEqual(j3["pos"][0], self.gen["PLUG_X"], delta=TOL)
        self.assertAlmostEqual(j3["pos"][1], 0.0, delta=TOL)
        x0, x1 = self.gen["PLUG_X"] - 3.95, self.gen["PLUG_X"] + 3.95
        for p in j3["pads"]:
            with self.subTest(pad=p["number"]):
                bx0, by0, bx1, by1 = p["bbox"]
                self.assertGreaterEqual(bx0, x0 + 0.2 - 1e-3, "inside the paddle, 0.2 mm from its side")
                self.assertLessEqual(bx1, x1 - 0.2 + 1e-3)
                self.assertGreater(by0, 1.0, "pads start 1.2 mm in from the tip")
                self.assertLess(by1, self.gen["NOTCH_D"])

    def test_a_row_on_the_front_b_row_on_the_back(self):
        for p in self.fp["J3"]["pads"]:
            with self.subTest(pad=p["number"]):
                if p["number"].startswith("A"):
                    self.assertEqual(p["copper"], ["F.Cu"])
                elif p["number"].startswith("B"):
                    self.assertEqual(p["copper"], ["B.Cu"])

    def test_plug_is_far_from_the_antenna(self):
        """The plug's body (8.4 mm wide) to the antenna rule area; a key-c on it is a ground pour
        beside the antenna too, which only a measurement settles (BRINGUP.md)."""
        body_x1 = self.gen["PLUG_X"] + 4.2
        self.assertGreaterEqual(self.gen["ANT_X"][0] - body_x1, PLUG_TO_ANTENNA_MIN)

    def test_antenna_rule_area_covers_the_module_antenna_both_faces(self):
        areas = [z for z in self.f["zones"] if z["rule_area"] and z["name"] == "antenna keep-out"]
        self.assertEqual({z["layer"] for z in areas}, {"F.Cu", "B.Cu"})
        u1x = self.fp["U1"]["pos"][0]
        for z in areas:
            (x0, y0), (x1, y1) = z["outline"]
            self.assertLessEqual(x0, u1x - 9.0 - 0.5 + TOL)
            self.assertGreaterEqual(x1, self.f["board"]["w"])
            self.assertLessEqual(y0, 0)
            self.assertGreaterEqual(y1, self.gen["ANT_BAND"])

    def test_line_parts_in_the_band_between_the_plug_and_the_module(self):
        """ESD and the CC resistors right of the slot, above the glass, clear of the antenna."""
        gx0, gy0, gx1, gy1 = self.gen["GLASS"]
        for ref in ("U6", "U7", "R18", "R17"):
            with self.subTest(ref=ref):
                pads = self.fp[ref]["pads"]
                self.assertGreater(min(p["bbox"][0] for p in pads), 14.0, "right of the slot")
                self.assertLess(max(p["bbox"][2] for p in pads), self.gen["ANT_X"][0], "clear of the antenna keep-out")
                self.assertLess(max(p["bbox"][3] for p in pads), gy0, "above the glass")

    def test_tvs_beside_the_plug(self):
        vbus = next(p for p in self.fp["J3"]["pads"] if p["number"] == "A4")
        d3 = next(p for p in self.fp["D3"]["pads"] if p["net"] == "VKEY")
        self.assertLess(((vbus["pos"][0] - d3["pos"][0]) ** 2 + (vbus["pos"][1] - d3["pos"][1]) ** 2) ** 0.5, 7.0)

    def test_every_port_part_is_on_the_front(self):
        """Economic assembly places the front only; J3 is the one exception, fitted by hand."""
        for ref in PORT_PARTS | {"R17"}:
            with self.subTest(ref=ref):
                self.assertEqual(self.fp[ref]["layer"], "F.Cu")

    def test_port_led_and_sbu_resistor_beside_the_plug(self):
        """In the strip left of the glass, by the plug: D4 shows a key is powered, where it is plugged."""
        gx0, gy0, gx1, gy1 = self.gen["GLASS"]
        for ref in ("D4", "R21", "R22"):
            with self.subTest(ref=ref):
                pads = self.fp[ref]["pads"]
                self.assertLess(max(p["bbox"][2] for p in pads), gx0, "left of the glass")
                self.assertLess(max(p["bbox"][3] for p in pads), 13.0, "by the plug")


if __name__ == "__main__":
    unittest.main()
