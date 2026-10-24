"""Compare the schematic's exported netlist with circuit.py, pin by pin.

  kicad-cli sch export netlist --format kicadsexpr -o /tmp/x.net hardware/picoquorum-key/picoquorum-key.kicad_sch
  python3 tools/gen/check_netlist.py /tmp/x.net
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sexp import parse, find, find_all  # noqa: E402
import circuit  # noqa: E402

tree = parse(open(sys.argv[1]).read())
got = {}
for net in find_all(find(tree, "nets"), "net"):
    name = str(find(net, "name")[1]).lstrip("/")
    for node in find_all(net, "node"):
        got[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name

comps = {str(find(c, "ref")[1]): c for c in find_all(find(tree, "components"), "comp")}
bad = 0
for p in circuit.PARTS:
    if not p.on_board:
        continue
    if p.ref not in comps:
        print("missing component", p.ref); bad += 1
        continue
    fp = str(find(comps[p.ref], "footprint")[1]) if find(comps[p.ref], "footprint") else ""
    if fp != p.footprint:
        print(f"{p.ref}: footprint {fp!r} != {p.footprint!r}"); bad += 1
    for pin, net in p.nets.items():
        g = got.get((p.ref, pin))
        if net is None:
            if g and not g.startswith("unconnected-"):
                print(f"{p.ref}.{pin}: expected NC, got {g}"); bad += 1
        elif g != net:
            print(f"{p.ref}.{pin}: expected {net}, got {g}"); bad += 1
nets = {}
for (ref, pin), n in got.items():
    nets.setdefault(n, []).append(f"{ref}.{pin}")
single = [n for n, v in nets.items() if len(v) < 2 and not n.startswith("unconnected-")]
for n in single:
    print("net with one pin:", n, nets[n]); bad += 1
print(f"{len(comps)} components, {len([n for n in nets if not n.startswith('unconnected-')])} nets, {bad} problems")
sys.exit(1 if bad else 0)
