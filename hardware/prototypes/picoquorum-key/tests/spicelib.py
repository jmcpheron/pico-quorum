"""Build small ngspice decks from the board's real netlist and run them.

Connectivity comes from the schematic's exported netlist (so a rewired board changes the simulated
circuit) and component values from tools/gen/circuit.py. Transistor pin roles are read from KiCad's
own symbols, not assumed. Device models are generic: the decks check topology, bias and timing,
not the exact current of a particular manufacturer's part.
"""
import os
import re

import common
import circuit

NODE_FIX = {"GND": "0", "+5V": "P5V", "+3V3": "P3V3"}
MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6}

MODELS = """
.model MMBT3904 NPN(IS=6.734f XTI=3 EG=1.11 VAF=74.03 BF={bf} NE=1.259 ISE=6.734f IKF=66.78m XTB=1.5 BR=.7371 NC=2 RC=1 CJC=3.638p MJC=.3085 VJC=.75 FC=.5 CJE=4.493p MJE=.2593 VJE=.75 TR=239.5n TF=301.2p ITF=.4 VTF=4 XTF=2 RB=10)
* AO3401A: Rds(on) ~ 60 mOhm at Vgs = -4.5 V (KP*W/L = 4), threshold {vth} V
.model AO3401A PMOS(LEVEL=1 VTO={vth} KP=4 LAMBDA=0.01 CBD=40p CGSO=300p CGDO=100p IS=1e-12 RS=0.01 RD=0.01)
* 1.14in panel backlight: about 3.0 V at 13 mA; IS is set per corner to move Vf
.model PANELLED D(IS={panel_is} N=2.5 RS=2)
"""


def value(text):
    """'4.7k' -> 4700.0"""
    m = re.fullmatch(r"([\d.]+)\s*([pnumkM]?)", text.strip())
    return float(m.group(1)) * MULT.get(m.group(2), 1.0)


def node(net):
    return NODE_FIX.get(net, re.sub(r"\W", "_", net))


class Netlist:
    def __init__(self):
        self.nets = common.sch_pad_nets()
        self.parts = {p.ref: p for p in circuit.PARTS}

    def n(self, ref, pin):
        return node(self.nets[(ref, str(pin))])

    def two_pin(self, ref, scale=1.0):
        kind = ref[0]
        v = value(self.parts[ref].value) * scale
        return "%s %s %s %.6g" % (ref, self.n(ref, 1), self.n(ref, 2), v)

    def pmos(self, ref):
        roles = {n: p for p, n in common.symbol_pins("Transistor_FET", "AO3401A").items()}   # name -> number
        d, g, s = (self.n(ref, roles[r]) for r in ("D", "G", "S"))
        return "M%s %s %s %s %s AO3401A" % (ref, d, g, s, s)

    def npn(self, ref):
        roles = {n: p for p, n in common.symbol_pins("Transistor_BJT", "MMBT3904").items()}
        c, b, e = (self.n(ref, roles[r]) for r in ("C", "B", "E"))
        return "Q%s %s %s %s MMBT3904" % (ref, c, b, e)


def run_ngspice(deck, tag):
    path = common.scratch("spice", tag + ".cir")
    with open(path, "w") as f:
        f.write(deck)
    r = common.run(["ngspice", "-b", path])
    out = r.stdout + r.stderr
    vals = {}
    for m in re.finditer(r"^\s*([\w()#.\[\]]+)\s*=\s*([-+0-9.eE]+)(?:[ \t].*)?$", out, re.M):
        vals[m.group(1).lower()] = float(m.group(2))
    if not vals:
        raise RuntimeError("ngspice produced no results for %s:\n%s" % (tag, out[-1500:]))
    return vals
