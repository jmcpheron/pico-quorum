"""The electrical-test netlist against the schematic, and the BOM and CPL against the board and
LCSC's parts. Plain Python. Run by `tools/keypcb jlc`, not by hand:

    python3 netlist_check.py board.d356 netlist.xml bom.csv cpl.csv facts.json parts.json

board.d356 is `kicad-cli pcb export ipcd356` (what a fab's flying probe tests against), netlist.xml
`kicad-cli sch export netlist --format kicadxml`. Every line it prints starts "ok", "warn", "FAIL" or
"info".
"""
import csv, json, math, os, sys
import xml.etree.ElementTree as ET


def say(kind, text):
    print(f"  {kind:<4} {text}")
    return kind == "FAIL"


def d356_nets(path):
    """{(ref, pad): net} from IPC-D-356's 317 (through-hole) and 327 (SMD) records. Net names are
    cut to 14 characters there; N/C is no net."""
    out = {}
    for line in open(path):
        if line[:3] not in ("317", "327") or line[3:6] == "VIA" or "VIA" in line[20:30]:
            continue
        net, ref, pad = line[3:17].strip(), line[20:26].strip(), line[27:31].strip()
        if not ref or ref == "VIA" or not pad:
            continue
        out[(ref, pad)] = "" if net == "N/C" else net
    return out


def sch_nets(path):
    out = {}
    for net in ET.parse(path).getroot().iter("net"):
        name = net.get("name")
        for node in net.iter("node"):
            out[(node.get("ref"), node.get("pin"))] = "" if name.startswith("unconnected-") else name
    return out


def groups(nets):
    """The nets as sets of pins, for nets with two or more pins."""
    g = {}
    for k, n in nets.items():
        if n:
            g.setdefault(n, set()).add(k)
    return {n: frozenset(v) for n, v in g.items() if len(v) > 1}


def netlist(d356, xml):
    print("3. the electrical-test netlist against the schematic")
    bad = False
    a, b = d356_nets(d356), sch_nets(xml)
    ga, gb = groups(a), groups(b)
    sa, sb = set(ga.values()), set(gb.values())
    only_a = [sorted(f"{r}.{p}" for r, p in s)[:4] for s in sa - sb]
    only_b = [sorted(f"{r}.{p}" for r, p in s)[:4] for s in sb - sa]
    bad |= say("FAIL" if only_a or only_b else "ok", f"{len(sa)} nets of two or more pads, the same pads in each, in both"
               if not (only_a or only_b) else f"nets in the board's test file only: {only_a[:4]}; in the schematic only: {only_b[:4]}")
    named = {n[:14] for n in gb}
    lost = sorted(n for n in ga if n not in named)
    bad |= say("FAIL" if lost else "ok", "every net's name, as far as IPC-D-356's 14 characters go" if not lost else f"names not in the schematic: {lost[:6]}")
    return bad


def bom_cpl(bomp, cplp, facts, parts):
    print("4. the BOM and CPL against the board and LCSC")
    bad = False
    fps = {f["ref"]: f for f in facts["footprints"]}
    pads = {}
    for p in facts["pads"]:
        pads.setdefault(p["ref"], []).append(p)
    bom = list(csv.DictReader(open(bomp)))
    cpl = {r["Designator"]: r for r in csv.DictReader(open(cplp))}
    in_bom = {ref: line for line in bom for ref in line["Designator"].split(",")}
    a, b = set(in_bom), set(cpl)
    bad |= say("FAIL" if a != b else "ok", f"{len(a)} parts, each in both the BOM and the CPL" if a == b else
               f"in the BOM, not the CPL: {sorted(a - b)}; in the CPL, not the BOM: {sorted(b - a)}")
    skip = sorted(r for r, f in fps.items() if f["dnp"] or f["no_pos"] or f["no_bom"])
    wrong = sorted(set(skip) & (a | b))
    bad |= say("FAIL" if wrong else "ok", f"not fitted by JLCPCB, and in neither file: {', '.join(skip)}" if not wrong else
               f"marked not fitted, but in the BOM or CPL: {wrong}")
    unpriced = sorted(r for r, f in fps.items() if r not in skip and r not in a)
    if unpriced:
        say("warn", f"fitted on the board but in no BOM line (no LCSC number?): {unpriced}")

    off = []
    for ref, r in cpl.items():
        f = fps.get(ref)
        if not f:
            continue
        x, y = float(r["Mid X"].rstrip("m")), float(r["Mid Y"].rstrip("m"))
        side = "F" if r["Layer"] == "Top" else "B"
        if math.dist((x, y), f["at"]) > 0.001 or side != f["side"]:
            off.append(f"{ref} CPL ({x}, {y}) {r['Layer']}, board {tuple(f['at'])} {f['side']}")
    bad |= say("FAIL" if off else "ok", "each CPL row at its part's place and side on the board" if not off else f"CPL rows off their parts: {off[:4]}")

    mism = []
    for line in bom:
        lcsc, ref = line["LCSC Part #"], line["Designator"].split(",")[0]
        p = parts.get(lcsc)
        if not p:
            mism.append(f"{lcsc} ({line['Designator']}) is not in parts.json")
            continue
        mine = [q for q in pads.get(ref, []) if q["num"] and q["kind"] in ("smd", "pth", "conn") and q["num"] not in ("SH",)]
        smd = {q["num"] for q in mine if q["kind"] == "smd"}
        mine = [q for q in mine if not (q["kind"] == "pth" and q["num"] in smd)]      # thermal vias in a pad are that pad
        if len(mine) != p["pads"]:
            mism.append(f"{line['Designator']} {line['Footprint']}: {len(mine)} pads, {lcsc} has {p['pads']}")
        if p["pitch"]:
            d = min((math.dist(u["at"], v["at"]) for u in mine for v in mine if u["num"] != v["num"] and math.dist(u["at"], v["at"]) > 0.01), default=0)
            if abs(d - p["pitch"]) > 0.02:
                mism.append(f"{line['Designator']} {line['Footprint']}: pitch {d:.3f}, {lcsc} {p['pitch']}")
        if p["value"] is not None and line["Comment"] != p["value"]:
            mism.append(f"{line['Designator']}: value {line['Comment']!r}, {lcsc} is {p['value']!r} ({p['mpn']})")
    bad |= say("FAIL" if mism else "ok", f"{len(bom)} BOM lines: each footprint's pads and pitch, and each value, LCSC's part's" if not mism
               else f"BOM against LCSC's parts: {mism[:6]}")
    rot = sorted({(f["fp"], r["Rotation"]) for ref, r in cpl.items() for f in [fps.get(ref)] if f})
    say("info", "rotations to hold against JLCPCB's preview: " + ", ".join(f"{fp} {r}" for fp, r in rot))
    return bad


def main():
    d356, xml, bomp, cplp, factsp, partsp = sys.argv[1:7]
    facts, parts = json.load(open(factsp)), json.load(open(partsp))
    bad = netlist(d356, xml)
    bad |= bom_cpl(bomp, cplp, facts, parts)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
