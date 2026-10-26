"""Pin contract: module pin, GPIO and net must agree in every place the repo states them.

Sources compared:
  - KiCad's RF_Module:ESP32-S3-WROOM-1 symbol (independent module pin -> GPIO ground truth)
  - docs/PINS.md table
  - tools/gen/circuit.py (what the schematic is generated from)
  - the routed .kicad_pcb pad nets
  - firmware/profile/picoquorum_key.py and firmware/smoke/smoke.py (read with ast, never imported)
"""
import ast
import os
import re
import unittest

import common
import circuit  # tools/gen/circuit.py, via common's sys.path

STRAPS = {0, 3, 45, 46}

# firmware constant -> net it must land on
PROFILE_NETS = {
    "SPI_SCK": "LCD_SCK", "SPI_MOSI": "LCD_MOSI", "LCD_CS": "LCD_CS", "LCD_DC": "LCD_DC",
    "LCD_RST": "LCD_RST", "LCD_BL": "LCD_BL", "D0": "BTN_REJECT", "D1": "BTN_NEXT", "D2": "BTN_SIGN",
    "I2C_SDA": "I2C_SDA", "I2C_SCL": "I2C_SCL", "LED": "LED",
    "BOOT": "BOOT", "UART0_TX": "UART_TX", "UART0_RX": "UART_RX", "USB_DM": "USB_DN_MCU",
    "USB_DP": "USB_DP_MCU",
    "KEY2_SDA": "KEY2_SDA", "KEY2_SCL": "KEY2_SCL", "KEY_CC": "KEY_CC", "KEY_EN": "KEY_EN",
}
PORT = ("KEY2_SDA", "KEY2_SCL", "KEY_CC", "KEY_EN")   # same names in both files
SMOKE_NETS = {
    "SCK": "LCD_SCK", "MOSI": "LCD_MOSI", "CS": "LCD_CS", "DC": "LCD_DC", "RST": "LCD_RST",
    "BL": "LCD_BL", "SDA": "I2C_SDA", "SCL": "I2C_SCL", "LED": "LED",
}
SMOKE_NETS.update({k: k for k in PORT})
SMOKE_BUTTON_NETS = {"D0 Reject": "BTN_REJECT", "D1 Next": "BTN_NEXT", "D2 Sign": "BTN_SIGN"}


def _numbers(cell):
    """'4-8, 13' -> [4,5,6,7,8,13]; a lone dash means none."""
    out = []
    for tok in re.split(r"\s*,\s*", cell.strip()):
        m = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", tok)
        if m:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
        elif tok.isdigit():
            out.append(int(tok))
    return out


def pins_md_rows():
    """[(function, [gpio], [module pin], [net])] from the table in docs/PINS.md."""
    with open(os.path.join(common.ROOT, "docs", "PINS.md")) as f:
        text = f.read()
    block = text.split("## The table")[1].split("\n## ")[0]
    rows = []
    for line in block.splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| function"):
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        func, gpio, pin, net = cells[:4]
        nets = [n.strip() for n in net.split(",") if n.strip()]
        rows.append((func, _numbers(gpio), _numbers(pin), nets))
    return rows


def firmware_constants(path):
    """Top-level NAME = literal / A, B = literal, literal assignments, plus SPI(...) baudrate."""
    with open(path) as f:
        tree = ast.parse(f.read())
    consts, baud = {}, None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            tgt, val = node.targets[0], node.value
            try:
                if isinstance(tgt, ast.Name):
                    consts[tgt.id] = ast.literal_eval(val)
                elif isinstance(tgt, ast.Tuple) and isinstance(val, ast.Tuple):
                    for t, v in zip(tgt.elts, val.elts):
                        consts[t.id] = ast.literal_eval(v)
                elif isinstance(tgt, ast.Tuple):
                    for t, v in zip(tgt.elts, ast.literal_eval(val)):
                        consts[t.id] = v
            except (ValueError, TypeError):
                pass
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "SPI":
            for kw in node.keywords:
                if kw.arg == "baudrate":
                    baud = ast.literal_eval(kw.value)
    return consts, baud


class PinContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pcb = common.pcb_pad_nets()
        cls.u1 = {pin: net for (ref, pin), net in cls.pcb.items() if ref == "U1"}
        cls.circ_u1 = next(p for p in circuit.PARTS if p.ref == "U1").nets
        cls.rows = pins_md_rows()
        cls.profile, cls.profile_baud = firmware_constants(
            os.path.join(common.ROOT, "firmware", "profile", "picoquorum_key.py"))
        cls.smoke, cls.smoke_baud = firmware_constants(
            os.path.join(common.ROOT, "firmware", "smoke", "smoke.py"))

    def net_on_gpio(self, gpio):
        return self.u1[str(common.pin_of_gpio(gpio))]

    # --- the symbol is the ground truth for pin <-> GPIO -----------------------------------
    def test_symbol_has_41_pins(self):
        self.assertEqual(len(common.esp32s3_symbol_pins()), 41)

    def test_pins_md_gpio_matches_symbol(self):
        checked = 0
        for func, gpios, pins, nets in self.rows:
            if len(gpios) == len(pins) and gpios:
                for g, p in zip(gpios, pins):
                    with self.subTest(func=func, gpio=g, pin=p):
                        self.assertEqual(common.gpio_of_pin(p), g)
                        checked += 1
            elif gpios and not nets:  # "unconnected" rows: compare as sets, order is not paired
                with self.subTest(func=func):
                    self.assertEqual({common.gpio_of_pin(p) for p in pins}, set(gpios))
                    checked += 1
        self.assertGreater(checked, 20)

    # --- PINS.md vs circuit.py vs the routed board ---------------------------------------
    def expected_pin_nets(self):
        for func, gpios, pins, nets in self.rows:
            if nets and len(nets) == len(pins):
                yield func, list(zip(pins, nets))
            elif len(nets) == 1:           # GND on pins 1, 40, 41
                yield func, [(p, nets[0]) for p in pins]
            elif not nets:                 # unconnected rows
                yield func, [(p, None) for p in pins]

    def test_pins_md_vs_circuit(self):
        for func, pairs in self.expected_pin_nets():
            for pin, net in pairs:
                with self.subTest(func=func, pin=pin):
                    self.assertEqual(self.circ_u1.get(str(pin)), net)

    def test_pins_md_vs_routed_board(self):
        n = 0
        for func, pairs in self.expected_pin_nets():
            for pin, net in pairs:
                with self.subTest(func=func, pin=pin):
                    got = self.u1[str(pin)]
                    if net is None:
                        self.assertTrue(common.is_nc(got), "%s should be unconnected, is %s" % (func, got))
                    else:
                        self.assertEqual(got, net)
                    n += 1
        self.assertEqual(n, 41, "PINS.md should account for every module pin exactly once")

    def test_every_module_pin_in_pins_md(self):
        seen = [p for _, _, pins, _ in self.rows for p in pins]
        self.assertEqual(sorted(seen), list(range(1, 42)))

    # --- firmware constants land on the right nets -------------------------------------
    def _check_profile(self, consts, mapping, label):
        for name, net in mapping.items():
            with self.subTest(source=label, const=name):
                self.assertIn(name, consts)
                self.assertEqual(self.net_on_gpio(consts[name]), net,
                                 "%s=GPIO%d is not on net %s" % (name, consts[name], net))

    def test_profile_constants_land_on_nets(self):
        self._check_profile(self.profile, PROFILE_NETS, "picoquorum_key.py")

    def test_smoke_constants_land_on_nets(self):
        self._check_profile(self.smoke, SMOKE_NETS, "smoke.py")
        for label, gpio in self.smoke["BUTTONS"]:
            with self.subTest(button=label):
                self.assertEqual(self.net_on_gpio(gpio), SMOKE_BUTTON_NETS[label])

    def test_smoke_matches_profile(self):
        pairs = {"SCK": "SPI_SCK", "MOSI": "SPI_MOSI", "CS": "LCD_CS", "DC": "LCD_DC", "RST": "LCD_RST",
                 "BL": "LCD_BL", "SDA": "I2C_SDA", "SCL": "I2C_SCL", "LED": "LED",
                 "KEY_ADDR": "KEY_ADDR", "W": "LCD_W", "H": "LCD_H", "XOFF": "LCD_XOFF",
                 "YOFF": "LCD_YOFF", "MADCTL": "LCD_MADCTL", "RAIL_Y": "RAIL_Y"}
        pairs.update({k: k for k in PORT})
        for s, p in pairs.items():
            with self.subTest(const=s):
                self.assertEqual(self.smoke[s], self.profile[p])
        smoke_buttons = [g for _, g in self.smoke["BUTTONS"]]
        self.assertEqual(smoke_buttons, [self.profile[k] for k in ("D0", "D1", "D2")])

    def test_smoke_spi_not_faster_than_profile(self):
        # running slower than the profile during bring-up is fine; faster would not be.
        self.assertLessEqual(self.smoke_baud, self.profile["SPI_BAUD"])

    # --- straps ------------------------------------------------------------------------------
    def test_no_button_or_ui_pin_on_a_strap(self):
        for name in ("D0", "D1", "D2", "LED", "LCD_BL", "LCD_CS", "LCD_DC", "LCD_RST") + PORT:
            with self.subTest(const=name):
                self.assertNotIn(self.profile[name], STRAPS)

    def test_key_port_keeps_off_the_octal_psram_and_the_board_id(self):
        """Not on GPIO35-37 (R8 modules' PSRAM), nor 16/17: their pull-ups are how the image knows this board."""
        for name in PORT:
            with self.subTest(const=name):
                self.assertNotIn(self.profile[name], (16, 17, 35, 36, 37))
        self.assertEqual((self.profile["I2C_SDA"], self.profile["I2C_SCL"]), (16, 17))
        self.assertNotEqual(self.profile["KEY2_I2C_ID"], self.profile["I2C_ID"])

    def test_key_port_cc_is_an_adc1_pin(self):
        """A later image may read a key ID resistor on CC: ADC1 is GPIO1-10, and works with Wi-Fi on."""
        self.assertIn(self.profile["KEY_CC"], range(1, 11))

    def test_strap_pins_as_documented(self):
        # GPIO0: BOOT net only, which must hold exactly the module, R4 pull-up, SW6 and TP8.
        self.assertEqual(self.net_on_gpio(0), "BOOT")
        members = {ref for (ref, _), n in self.pcb.items() if n == "BOOT"}
        self.assertEqual(members, {"U1", "R4", "SW6", "TP8"})
        for gpio in (3, 45, 46):
            with self.subTest(gpio=gpio):
                self.assertTrue(common.is_nc(self.net_on_gpio(gpio)))

    def test_buttons_are_pull_ups_to_ground_with_no_external_resistor(self):
        for net in ("BTN_REJECT", "BTN_NEXT", "BTN_SIGN"):
            with self.subTest(net=net):
                members = sorted(ref for (ref, _), n in self.pcb.items() if n == net)
                self.assertEqual(len(members), 2, members)
                self.assertTrue(any(m == "U1" for m in members))
                self.assertTrue(any(m.startswith("SW") for m in members))

    def test_i2c_pullups_in_spec_range(self):
        with open(os.path.join(common.ROOT, "docs", "SPEC.md")) as f:
            spec = f.read()
        m = re.search(r"Pull-ups\*\* of ([\d.]+)k to ([\d.]+)k", spec)
        lo, hi = float(m.group(1)), float(m.group(2))
        for net, ref in (("I2C_SDA", "R6"), ("I2C_SCL", "R7")):
            with self.subTest(net=net):
                part = next(p for p in circuit.PARTS if p.ref == ref)
                self.assertIn("+3V3", part.nets.values())
                self.assertIn(net, part.nets.values())
                self.assertTrue(lo <= float(part.value.rstrip("k")) <= hi)

    # --- the routed board agrees with the schematic, pad by pad -----------------------------
    def test_pcb_pad_nets_equal_schematic_pad_nets(self):
        sch = common.sch_pad_nets()
        bad = []
        for (ref, pin), net in sch.items():
            got = self.pcb.get((ref, pin))
            if got is None:
                bad.append("%s.%s missing from PCB" % (ref, pin))
            elif common.is_nc(net) != common.is_nc(got) or (not common.is_nc(net) and net != got):
                bad.append("%s.%s: schematic %s, PCB %s" % (ref, pin, net, got))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
