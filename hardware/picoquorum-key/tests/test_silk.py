"""Silkscreen: fab legibility limits, the labels that must be there, and that they say the truth.

Reads the board-level silk (not the footprint libraries' own) from pcb_facts.py. DRC's silk checks
(silk over pads, silk on silk, silk at the edge) run in test_mutation's clean control, which fails on
any warning, so this file covers what DRC cannot: size limits, mirroring, and meaning.
"""
import unittest

import common

MIN_LINE = 0.15         # JLCPCB: thinner silk lines can disappear
MIN_TEXT, MIN_STROKE = 1.0, 0.15
EDGE = 0.5              # mm from the board edge
BUTTONS = {"BOOT": "SW6", "RESET": "SW7"}   # label -> the switch it names
BELOW_MAX, ACROSS_MAX = 5.0, 3.0    # a label sits this far under, and this far across from, its switch centre


def centre(item):
    b = item["bbox"]
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


class Silk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = common.board_facts()
        cls.items = cls.facts["silk"]
        cls.texts = [i for i in cls.items if i["class"] == "PCB_TEXT"]
        cls.shapes = [i for i in cls.items if i["class"] != "PCB_TEXT"]
        cls.nets = {k: v.lstrip("/") for k, v in common.pcb_pad_nets().items()}

    def label(self, text, layer):
        found = [t for t in self.texts if t["text"] == text and t["layer"] == layer]
        self.assertEqual(len(found), 1, "%r on %s: expected one, found %d" % (text, layer, len(found)))
        return found[0]

    def test_there_is_silk_to_check(self):
        self.assertGreater(len(self.texts), 20)
        self.assertGreater(len(self.shapes), 20)

    def test_lines_are_thick_enough_to_print(self):
        # a filled shape (the logos, the 8-bit art) has no line: only its outline's width is 0
        thin = [(s["layer"], s["bbox"], s["width"]) for s in self.shapes if s["width"] < MIN_LINE - 1e-6 and not s["filled"]]
        self.assertEqual(thin, [], "silk lines under %s mm" % MIN_LINE)

    def test_text_is_big_and_bold_enough_to_read(self):
        bad = [(t["text"], t["height"], t["thickness"]) for t in self.texts
               if t["height"] < MIN_TEXT - 1e-6 or t["thickness"] < MIN_STROKE - 1e-6]
        self.assertEqual(bad, [], "text under %s mm high or %s mm stroke" % (MIN_TEXT, MIN_STROKE))

    def test_back_text_is_mirrored_and_front_text_is_not(self):
        wrong = [(t["text"], t["layer"]) for t in self.texts if t["mirrored"] != t["layer"].startswith("B.")]
        self.assertEqual(wrong, [])

    def test_everything_stays_off_the_board_edge(self):
        w, h = self.facts["board"]["w"], self.facts["board"]["h"]
        out = [(i.get("text", "shape"), i["bbox"]) for i in self.items
               if i["bbox"][0] < EDGE or i["bbox"][1] < EDGE or i["bbox"][2] > w - EDGE or i["bbox"][3] > h - EDGE]
        self.assertEqual(out, [], "silk within %s mm of the edge" % EDGE)

    def test_board_name_and_revision(self):
        """The name itself is drawn (filled shapes from silk_art.py's logos); the text says where it lives."""
        self.label("PicoQuorum.app", "F.Silkscreen")
        self.label("PicoQuorum.app", "B.Silkscreen")
        self.label("KEY, REV B", "B.Silkscreen")
        self.label("KEY PORT", "F.Silkscreen")

    def test_key_port_label_sits_beside_the_plug(self):
        """KEY PORT is by the plug's slot, at the top-left, not across the board."""
        cx, cy = centre(self.label("KEY PORT", "F.Silkscreen"))
        px, py = self.facts["footprints"]["J3"]["pos"]
        self.assertLess(abs(cx - px), 15.0)
        self.assertLess(cy - py, 8.0)

    def test_back_legend_says_one_owner_not_one_key(self):
        """With the key port a board can hold two keys: the back no longer says ONE KEY."""
        self.label("ONE OWNER", "B.Silkscreen")
        self.assertEqual([t for t in self.texts if t["text"] == "ONE KEY"], [])
        for side in ("F.Silkscreen", "B.Silkscreen"):
            self.assertGreater(len([s for s in self.shapes if s["layer"] == side and s["filled"]]), 10, side)

    def test_each_button_label_sits_just_under_the_switch_it_names(self):
        for text, ref in BUTTONS.items():
            with self.subTest(label=text):
                cx, cy = centre(self.label(text, "F.Silkscreen"))
                sx, sy = self.facts["footprints"][ref]["pos"]
                self.assertLess(abs(cx - sx), ACROSS_MAX, "%s is %.1f mm across from %s" % (text, cx - sx, ref))
                self.assertTrue(0 < cy - sy < BELOW_MAX, "%s is %.1f mm below %s" % (text, cy - sy, ref))

    def test_a_button_label_is_never_nearer_another_switch(self):
        sw = {r: self.facts["footprints"][r]["pos"] for r in BUTTONS.values()}
        for text, ref in BUTTONS.items():
            c = centre(self.label(text, "F.Silkscreen"))
            nearest = min(sw, key=lambda r: (sw[r][0] - c[0]) ** 2 + (sw[r][1] - c[1]) ** 2)
            self.assertEqual(nearest, ref, "%s reads as %s's label" % (text, nearest))

    def test_every_test_pad_is_named_for_its_net(self):
        """The back-side text under TP1-TP14 is that pad's net, shortened as silk_art.pad_label does
        (UART_TX -> TX, KEY_CC -> KCC, KEY2_SDA -> KSDA), and is the text nearest that pad."""
        pads = {r: f for r, f in self.facts["footprints"].items() if r.startswith("TP")}
        self.assertEqual(len(pads), 14)
        back = [t for t in self.texts if t["layer"] == "B.Silkscreen"]
        for ref, fp in pads.items():
            with self.subTest(pad=ref):
                net = (fp["pads"][0]["net"].lstrip("/").replace("UART_", "").replace("I2C_", "")
                       .replace("KEY2_", "K").replace("KEY_", "K"))
                px, py = fp["pos"]
                near = min(back, key=lambda t: (centre(t)[0] - px) ** 2 + (centre(t)[1] - (py + 1.9)) ** 2)
                self.assertEqual(near["text"], net)
                self.assertLess(abs(centre(near)[0] - px), 1.0)

    def test_usb_data_legend_matches_the_links_in_the_design(self):
        """The back says R12+R13 are the USB data links: they must sit in D+ and D-."""
        self.label("R12+R13 = USB DATA", "B.Silkscreen")
        self.assertIn("USB_DP", {self.nets[("R12", "1")], self.nets[("R12", "2")]})
        self.assertIn("USB_DN", {self.nets[("R13", "1")], self.nets[("R13", "2")]})

    def test_flash_legend_names_buttons_on_the_right_nets(self):
        """BOOT+RESET = FLASH: SW6 pulls GPIO0 (net BOOT) and SW7 pulls EN."""
        self.label("BOOT+RESET = FLASH", "B.Silkscreen")
        self.assertIn("BOOT", {self.nets[("SW6", "1")], self.nets[("SW6", "2")]})
        self.assertIn("EN", {self.nets[("SW7", "1")], self.nets[("SW7", "2")]})


if __name__ == "__main__":
    unittest.main()
