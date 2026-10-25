"""ngspice checks of the analog corners the docs argue for in prose.

The circuits are rebuilt from the schematic's netlist (spicelib.Netlist), so rewiring the board
changes what is simulated. Models are generic; read the numbers as bias and timing, not as part data.
"""
import itertools
import math
import unittest
from concurrent.futures import ThreadPoolExecutor

import common
import spicelib as sl

PANEL_MAX_A = 0.020         # docs/SPEC: panel backlight limit, 20 mA
VT = 0.025852               # thermal voltage at 27 C
NOTES = []
NOMINAL = dict(v5=5.0, vf_shift=0.0, r11=1.0, bf=200, vth=-0.8, vh=3.3)


def backlight_deck(nl, tag, v5=5.0, v3=3.3, gpio=("high", 3.3), vf_shift=0.0, r11=1.0, bf=200, vth=-0.8):
    """Q1/Q2 backlight switch with the panel LED, built from the board's own nets."""
    panel_is = 9e-23 * math.exp(-vf_shift / (2.5 * VT))
    lines = ["* backlight switch " + tag, "V5 P5V 0 DC %g" % v5, "V3 P3V3 0 DC %g" % v3]
    for ref in ("R9", "R10", "R14"):
        lines.append(nl.two_pin(ref))
    lines.append(nl.two_pin("R11", r11))
    lines += [nl.pmos("Q1"), nl.npn("Q2")]
    gnode = nl.n("U1", 23)                                   # module pin 23 = LCD_BL
    kind, level = gpio
    if kind == "high":
        lines += ["VGPIO gsrc 0 DC %g" % level, "RGPIO gsrc %s 25" % gnode]     # ~25 ohm output stage
    else:                                                    # floating: only a leakage path remains
        lines.append("RLEAK %s %s %g" % (gnode, "0" if kind == "float_gnd" else "P3V3", level))
    anode, return_ = nl.n("J2", 8), nl.n("J2", 7)            # panel LEDA, panel GND
    lines += ["VPANEL %s anode_i 0" % anode, "DPANEL anode_i %s PANELLED" % return_]
    lines.append(sl.MODELS.format(bf=bf, vth=vth, panel_is=panel_is))
    lines += [".control", "op", "print i(vpanel) i(v5) v(%s) v(%s)" % (nl.n("Q1", 1), nl.n("R11", 1)), ".endc", ".end"]
    return "\n".join(lines)


def backlight(nl, tag, **kw):
    r = sl.run_ngspice(backlight_deck(nl, tag, **kw), tag)
    return dict(led=r["i(vpanel)"], supply=abs(r["i(v5)"]), gate=r["v(%s)" % nl.n("Q1", 1).lower()])


class Backlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nl = sl.Netlist()

    def test_dark_when_gpio21_floats(self):
        # At reset the S3 leaves GPIO21 high-impedance; R14 must hold Q2 (and so Q1) off.
        for kind, ohms in (("float_gnd", 1e7), ("float_vdd", 1e7), ("float_gnd", 1e9)):
            with self.subTest(leak=kind, ohms=ohms):
                r = backlight(self.nl, "off_%s_%g" % (kind, ohms), gpio=(kind, ohms))
                self.assertLess(abs(r["led"]), 1e-6, "panel LED current %.3g A" % r["led"])
                self.assertLess(r["supply"], 5e-6, "5 V rail draws %.3g A" % r["supply"])

    def test_dark_at_reset_even_with_a_pull_up_on_gpio21(self):
        # The docs argue "off at reset" for a floating pin. Margin check for the case that GPIO21
        # comes out of reset with a weak pull-up: find the smallest pull-up that still leaves the
        # backlight dark and require it to be below the S3's typical ~45 kOhm internal one.
        lo, hi = 1e3, 1e8                      # lo lights the backlight, hi does not
        for i in range(14):
            mid = math.sqrt(lo * hi)
            lit = backlight(self.nl, "pullup_bisect%02d" % i, gpio=("float_vdd", mid))["led"] > 100e-6
            lo, hi = (mid, hi) if lit else (lo, mid)
        threshold = math.sqrt(lo * hi)
        NOTES.append("backlight stays dark at reset with any pull-up on GPIO21 of %.0f kOhm or more "
                     "(typical S3 internal pull-up ~45 kOhm: %.1fx margin)" % (threshold / 1e3, 45e3 / threshold))
        self.assertLess(threshold, 45e3, "a ~45 kOhm pull-up on GPIO21 would light the backlight at reset")

    def test_nominal_current(self):
        r = backlight(self.nl, "nominal")
        self.assertTrue(0.010 < r["led"] < 0.016, "%.2f mA" % (r["led"] * 1e3))
        self.assertLess(r["gate"], 0.5, "Q2 should pull Q1's gate hard to ground")

    def test_current_stays_under_panel_limit_across_corners(self):
        corners = [dict(zip(("v5", "vf_shift", "r11", "bf", "vth", "vh"), c)) for c in itertools.product(
            (4.75, 5.25), (-0.2, 0.2), (0.99, 1.01), (100, 400), (-0.5, -1.3), (2.64, 3.3))]

        def run(item):
            i, c = item
            kw = dict(c)
            vh = kw.pop("vh")
            return c, backlight(self.nl, "corner%02d" % i, gpio=("high", vh), **kw)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(run, enumerate(corners)))
        worst = max(results, key=lambda cr: cr[1]["led"])
        lowest = min(results, key=lambda cr: cr[1]["led"])
        NOTES.append("backlight over %d corners: %.1f mA (worst) to %.1f mA (lowest); panel limit %g mA"
                     % (len(results), worst[1]["led"] * 1e3, lowest[1]["led"] * 1e3, PANEL_MAX_A * 1e3))
        for c, r in results:
            with self.subTest(**c):
                self.assertLess(r["led"], PANEL_MAX_A)
                self.assertGreater(r["led"], 0.005, "too dim")
                self.assertLess(r["gate"], 0.5, "Q1 not driven hard on")

    def test_no_back_feed_when_5v_is_absent(self):
        # Bench case: 3V3 supplied at TP1 with USB unplugged and the backlight GPIO driven high.
        r = backlight(self.nl, "no5v", v5=0.0, gpio=("high", 3.3))
        self.assertLess(abs(r["led"]), 1e-6)
        self.assertLess(r["supply"], 1e-6, "current flows into the 5 V rail from 3V3: %.3g A" % r["supply"])


class EnableDelay(unittest.TestCase):
    """EN = 10k to 3V3 with 1 uF to ground: it must rise after 3V3 is stable, whatever the supply ramp."""
    T_STBL = 50e-6          # Espressif power-up sequence: EN high at least ~50 us after the supply is stable
    VIH = 0.75 * 3.3        # EN input-high threshold, 0.75 x VDD

    def run_ramp(self, nl, ramp):
        lines = ["* EN delay", "V3 P3V3 0 PULSE(0 3.3 0 %g %g 1 2)" % (ramp, ramp), nl.two_pin("R3"), nl.two_pin("C4"),
                 ".control", "tran %g 100m" % min(ramp / 10, 20e-6),
                 "meas tran t_vdd WHEN v(p3v3)=2.97 RISE=1", "meas tran t_en WHEN v(%s)=%g RISE=1" % (nl.n("C4", 1), self.VIH),
                 ".endc", ".end"]
        return sl.run_ngspice("\n".join(lines), "en_%g" % ramp)

    def test_en_rises_after_3v3_is_stable(self):
        nl = sl.Netlist()
        for ramp in (100e-6, 1e-3, 10e-3):
            with self.subTest(ramp=ramp):
                r = self.run_ramp(nl, ramp)
                self.assertGreater(r["t_en"] - r["t_vdd"], self.T_STBL)

    def test_delay_matches_the_rc(self):
        nl = sl.Netlist()
        tau = sl.value("10k") * sl.value("1u")
        r = self.run_ramp(nl, 100e-6)
        self.assertAlmostEqual(r["t_en"], tau * math.log(4), delta=0.05 * tau * math.log(4))


class I2cRise(unittest.TestCase):
    """Standard mode (100 kHz): 30% to 70% rise time at most 1000 ns."""
    LIMIT = 1000e-9
    PIN_C = 10e-12          # two device pins plus pads
    TRACE_PF_PER_CM = 1.0   # conservative for a 2-layer board over a ground pour

    KEY_C = 30e-12          # the key port: the plug, a key-c's board and its chip, a guess with room in it

    def rise(self, nl, ref, cb):
        net = nl.n(ref, 2)
        lines = ["* i2c rise " + ref, "VS %s 0 DC 3.3" % nl.n(ref, 1), nl.two_pin(ref), "CB %s 0 %g" % (net, cb),
                 "S1 %s 0 ctl 0 SWM" % net, "VCTL ctl 0 PULSE(1 0 10u 1n 1n 1 2)", ".model SWM SW(VT=0.5 VH=0.1 RON=50 ROFF=1G)",
                 ".control", "tran 2n 30u",
                 "meas tran trise TRIG v(%s) VAL=0.99 RISE=1 TARG v(%s) VAL=2.31 RISE=1" % (net, net), ".endc", ".end"]
        return sl.run_ngspice("\n".join(lines), "i2c_%s_%d" % (ref, cb * 1e12))["trise"]

    def test_rise_time_with_routed_trace_capacitance(self):
        facts = common.board_facts()
        nl = sl.Netlist()
        for ref, net in (("R6", "I2C_SDA"), ("R7", "I2C_SCL")):
            length_cm = sum(t["len"] for t in facts["tracks"] if t["net"] == net) / 10
            cb = self.PIN_C + self.TRACE_PF_PER_CM * length_cm * 1e-12
            limit_cb = self.LIMIT / (0.8473 * sl.value(nl.parts[ref].value))
            NOTES.append("%s: %.1f cm routed, ~%.0f pF, rise %.0f ns (limit 1000 ns reached at ~%.0f pF)"
                         % (net, length_cm, cb * 1e12, self.rise(nl, ref, cb) * 1e9, limit_cb * 1e12))
            with self.subTest(net=net, margin="x2"):
                self.assertLess(self.rise(nl, ref, 2 * cb), self.LIMIT)

    def test_key_port_bus_rise_time(self):
        """The port's own bus: 2.2k to VKEY, the routed track, and a key-c on the plug."""
        facts = common.board_facts()
        nl = sl.Netlist()
        for ref, net in (("R19", "KEY2_SDA"), ("R20", "KEY2_SCL")):
            self.assertEqual(nl.n(ref, 1), "VKEY", "%s pulls up to VKEY, not 3V3" % ref)
            length_cm = sum(t["len"] for t in facts["tracks"] if t["net"] == net) / 10
            cb = self.PIN_C + self.KEY_C + self.TRACE_PF_PER_CM * length_cm * 1e-12
            NOTES.append("%s: %.1f cm routed, ~%.0f pF with a key-c, rise %.0f ns"
                         % (net, length_cm, cb * 1e12, self.rise(nl, ref, cb) * 1e9))
            with self.subTest(net=net, margin="x2"):
                self.assertLess(self.rise(nl, ref, 2 * cb), self.LIMIT)

    def test_sim_agrees_with_rc_formula(self):
        nl = sl.Netlist()
        r, cb = sl.value("4.7k"), 100e-12
        self.assertAlmostEqual(self.rise(nl, "R6", cb), 0.8473 * r * cb, delta=0.05 * 0.8473 * r * cb)


class KeyPortCc(unittest.TestCase):
    """GPIO1 reads the key port's CC line: R17 47k to 3V3, R18 1k to the plug's A5, a key-c's 5.1k Rd
    to ground. It must read a clean low with a key and a clean high without, as a plain GPIO."""
    VIL, VIH = 0.25 * 3.3, 0.75 * 3.3       # ESP32-S3 input thresholds, 0.25 and 0.75 x VDD
    RD = 5.1e3                               # key-c's Rd on each CC pin (key-pcb)

    def cc(self, rd=None, pull_up=None, tag=""):
        nl = sl.Netlist()
        lines = ["* key port CC " + tag, "V3 P3V3 0 DC 3.3", nl.two_pin("R17"), nl.two_pin("R18"),
                 "RD %s 0 %g" % (nl.n("R18", 2), rd if rd else 1e12)]
        if pull_up:
            lines.append("RPU P3V3 %s %g" % (nl.n("R17", 2), pull_up))
        lines += [".control", "op", "print v(%s)" % nl.n("R17", 2), ".endc", ".end"]
        return sl.run_ngspice("\n".join(lines), "cc_" + tag)["v(%s)" % nl.n("R17", 2).lower()]

    def test_a_key_reads_low_and_none_reads_high(self):
        low, high = self.cc(self.RD, tag="key"), self.cc(None, tag="none")
        NOTES.append("key port CC: %.2f V with a key-c, %.2f V with none (VIL %.2f V, VIH %.2f V)" % (low, high, self.VIL, self.VIH))
        self.assertLess(low, self.VIL)
        self.assertGreater(high, self.VIH)
        self.assertAlmostEqual(low, 3.3 * 6.1 / 53.1, delta=0.01)     # 1k + 5.1k under 47k

    def test_the_internal_pull_up_would_eat_the_margin(self):
        """Reported, not required: firmware reads CC with no internal pull-up, since R17 is on every board."""
        v = self.cc(self.RD, pull_up=45e3, tag="key_pu")
        NOTES.append("key port CC with the S3's ~45k pull-up on as well: %.2f V, %.2f V under VIL: leave it off" % (v, self.VIL - v))
        self.assertLess(v, self.VIL)


def tearDownModule():
    if NOTES:
        print("\nspice notes:\n  " + "\n  ".join(NOTES))


if __name__ == "__main__":
    unittest.main()
