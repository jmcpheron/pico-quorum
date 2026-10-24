"""Digital twin: run firmware/smoke/smoke.py, unmodified, against the board's pad nets.

The healthy board must pass every expectation; each miswired variant (two module pins exchanged)
must fail at least one, or the twin is not actually looking at the wiring.
"""
import contextlib
import io
import os
import sys
import unittest

import common

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "twin"))
import board_model as bm  # noqa: E402

SMOKE = os.path.join(common.ROOT, "firmware", "smoke", "smoke.py")
RED, GREEN, BLUE, WHITE = 0xF800, 0x07E0, 0x001F, 0xFFFF
XOFF, YOFF, RAIL_Y = 40, 53, (7, 67, 127)
# physical switch -> what smoke.py should report when it is pressed (docs/PINS.md)
SWITCHES = (("SW1", "D0 Reject"), ("SW2", "D1 Next"), ("SW3", "D2 Sign"))


class Run:
    pass


def run_smoke(pad_nets):
    world = bm.World(pad_nets)
    run = Run()
    run.world, run.probes = world, {}

    def press(i, ref):
        def go(w):
            w.pressed.add(ref)
        return go

    def probe(i):
        def go(w):
            if i < 3:
                run.probes[i] = w.panel.ram.get((5 + XOFF, RAIL_Y[i] + YOFF))
        return go

    def release(ref):
        return lambda w: w.pressed.discard(ref)

    for i, (ref, _label) in enumerate(SWITCHES):
        t = 5.0 + 0.8 * i
        world.at(t, press(i, ref))
        world.at(t + 0.30, probe(i))
        world.at(t + 0.50, release(ref))

    restore = bm.install(world)
    out = io.StringIO()
    try:
        with open(SMOKE) as f:
            code = compile(f.read(), SMOKE, "exec")
        with contextlib.redirect_stdout(out):
            try:
                exec(code, {"__name__": "smoke"})
            except KeyboardInterrupt:
                pass                                   # smoke.py loops until Ctrl-C
    finally:
        restore()
    run.log = out.getvalue().splitlines()
    return run


def problems(run):
    """Everything wrong with this run, as strings; empty means the board behaved."""
    w, p, ram, bad = run.world, run.world.panel, run.world.panel.ram, []
    if not w.panel_ready():
        bad.append("panel connector has no 3V3/GND")
    missing = {0x01, 0x11, 0x3A, 0x36, 0x21, 0x13, 0x29} - set(p.cmds)
    if missing:
        bad.append("panel never saw init commands %s" % sorted(hex(c) for c in missing))
    if p.madctl != 0x60 or p.colmod != 0x55:
        bad.append("panel MADCTL/COLMOD = %s/%s" % (p.madctl, p.colmod))
    first = w.first_light_ram
    if first is None:
        bad.append("backlight never came on (chain GPIO21 -> R9 -> Q2 -> Q1 -> R11 -> LEDA is not wired)")
    else:
        for name, x, y, colour in (("red", 120, 20, RED), ("green", 120, 65, GREEN), ("blue", 120, 110, BLUE)):
            if first.get((x + XOFF, y + YOFF)) != colour:
                bad.append("%s band missing when the backlight came on" % name)
    white = sum(1 for (x, y), c in ram.items() if c == WHITE and 24 <= x - XOFF <= 90 and 54 <= y - YOFF <= 76)
    if white < 50:
        bad.append("banner not drawn (%d white pixels)" % white)
    if not any("ATECC608 serial: 01 23" in l and l.split("(")[0].rstrip().endswith("EE") for l in run.log):
        bad.append("ATECC serial not read")
    pressed = [l.split("pressed: ")[1] for l in run.log if "pressed:" in l]
    if pressed != [label for _, label in SWITCHES]:
        bad.append("buttons reported %s" % pressed)
    for i in range(3):
        if run.probes.get(i) != GREEN:
            bad.append("rail tick %d did not turn green while its switch was held" % i)
        if ram.get((5 + XOFF, RAIL_Y[i] + YOFF)) != WHITE:
            bad.append("rail tick %d did not return to white" % i)
    edges = [v for _, v in w.led_events]
    if len(edges) < 10 or set(edges) != {0, 1}:
        bad.append("status LED not toggling through R8/D1 (%d edges)" % len(edges))
    return bad


def swapped(nets, a, b):
    out = dict(nets)
    out[("U1", str(a))], out[("U1", str(b))] = nets[("U1", str(b))], nets[("U1", str(a))]
    return out


MISWIRES = {
    "LCD_MOSI and LCD_SCK exchanged": (19, 20),
    "LCD_DC and LCD_CS exchanged": (17, 18),
    "BTN_SIGN and BTN_NEXT exchanged": (33, 34),
    "I2C_SDA and I2C_SCL exchanged": (9, 10),
    "LCD_BL and LED exchanged": (23, 25),
    "BTN_REJECT moved to unused pin 31": (35, 31),
}


class Twin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nets = common.pcb_pad_nets()
        cls.healthy = run_smoke(cls.nets)

    def test_healthy_board_passes_every_expectation(self):
        self.assertEqual(problems(self.healthy), [], "\n".join(self.healthy.log[-12:]))

    def test_miswired_boards_are_caught(self):
        for name, (a, b) in MISWIRES.items():
            with self.subTest(miswire=name):
                found = problems(run_smoke(swapped(self.nets, a, b)))
                self.assertTrue(found, "the twin did not notice: " + name)

    def test_i2c_scan_finds_only_the_key(self):
        # The ATECC ignores the bus while asleep, so smoke.py must wake it before it scans.
        scan = next(l for l in self.healthy.log if "i2c scan" in l)
        self.assertIn("i2c scan: ['0x60'] ", scan)


if __name__ == "__main__":
    unittest.main()
