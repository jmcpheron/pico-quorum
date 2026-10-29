#!/usr/bin/env python3
"""Takes what console-rp copies from Raspberry Pi's minimal RP2350A board: the footprints round the
chip, where each part sits from the chip's centre, and the power copper there (the regulator's
pours, the rings under the chip, the DVDD and 3V3 tracks and vias), and the crystal's corner below it. Writes lib/pqrp.pretty/RPi_*,
rpi_minimal.json and lib/RPI-MINIMAL-LICENSE.txt, which gen_console_rp.py reads; the repo keeps
them, so the generator needs no download.

Raspberry Pi's design is MIT (its LICENSE.txt, copied beside the footprints):
  curl -LO https://datasheets.raspberrypi.com/rp2350/Minimal-KiCAD.zip && unzip Minimal-KiCAD.zip
  <KiCad's python3> rpi_minimal.py RPI-RP2350A-MINIMAL_R4-S1_public

Their board and ours put U1 at 0 degrees with the same pad positions, so their copper lands on our
pads by moving it to our U1's centre.
"""
import json, os, re, shutil, sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "lib", "pqrp.pretty")
KI3D = "${KICAD10_3DMODEL_DIR}"

# their footprint -> our name for it, and the stock 3D model to show (theirs are embedded STEPs)
FOOTPRINTS = {
    "rpi_rp2350a_vias": ("RPi_RP2350A_QFN-60_7x7mm_P0.4mm_ThermalVias", "Package_DFN_QFN.3dshapes/QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm.step"),
    "abracon_aota-b201610s3r3-101-t": ("RPi_L_Abracon_AOTA-B201610", "Inductor_SMD.3dshapes/L_Murata_DFE201610P.step"),
    "generic_capc1005x50_wide": ("RPi_C_0402_wide", "Capacitor_SMD.3dshapes/C_0402_1005Metric.step"),
    "generic_capc1005x50": ("RPi_C_0402", "Capacitor_SMD.3dshapes/C_0402_1005Metric.step"),
    "generic_resc1005x35": ("RPi_R_0402", "Resistor_SMD.3dshapes/R_0402_1005Metric.step"),
    "generic_xtalcc320x250x80-4": ("RPi_Crystal_SMD_3225-4Pin_3.2x2.5mm", "Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.step"),
}
# their parts round the chip -> ours. Their 3V3 100n caps by the pin each sits at; our C9 (pin 45)
# has no twin, theirs C17 serving pins 44 and 45 together. Their USB resistors have the chip on pin
# 2, ours on pin 1, so ours turn round
PARTS = {"U1": "U1", "L1": "L1", "C6": "C1", "C7": "C2", "C9": "C3", "R3": "R1",
         "C13": "C4", "C15": "C5", "C18": "C6", "C16": "C7", "C14": "C8", "C17": "C13", "C12": "C14",
         "C8": "C10", "C10": "C11", "C11": "C12", "R2": "R2", "R7": "R14", "R8": "R13",
         "X1": "Y1", "C3": "C15", "C4": "C16"}
TURN = {"R14", "R13"}
NETS = {"+3V3": "+3V3", "+1V1": "/DVDD", "/VREG_AVDD": "/VREG_AVDD", "/VREG_LX": "/VREG_LX", "GND": "GND",
        "Net-(U1-USB_DP)": "/RP_DP", "Net-(U1-USB_DM)": "/RP_DM",
        "/XIN": "/XIN", "/XOUT": "/XOUT", "Net-(C4-Pad1)": "/XTAL_OUT"}
DRILL = 0.3                              # their vias' 0.25 mm holes, at the 0.3 our rules (and JLCPCB's base price) ask for
# from the chip's centre: copper wholly inside one is copied. Round the chip, and the crystal's corner below it
WINDOWS = [(-7.6, -8.2, 7.6, 7.4), (-3.3, 7.4, 3.3, 14.8)]


def main(src):
    pcb = next(os.path.join(src, f) for f in os.listdir(src) if f.endswith(".kicad_pcb"))
    b = pcbnew.LoadBoard(pcb)
    mm = pcbnew.ToMM
    u1 = b.FindFootprintByReference("U1")
    ox, oy = mm(u1.GetPosition().x), mm(u1.GetPosition().y)
    assert u1.GetOrientationDegrees() == 0
    rel = lambda p: [round(mm(p.x) - ox, 4), round(mm(p.y) - oy, 4)]
    inside = lambda q: any(w[0] <= q[0] <= w[2] and w[1] <= q[1] <= w[3] for w in WINDOWS)

    os.makedirs(LIB, exist_ok=True)
    out = {"source": os.path.basename(pcb), "parts": {}, "tracks": [], "vias": [], "zones": []}
    saved = set()
    for theirs, ours in PARTS.items():
        fp = b.FindFootprintByReference(theirs)
        lib_name = fp.GetFPID().GetLibItemName().wx_str()
        name, model = FOOTPRINTS[lib_name]
        out["parts"][ours] = {"theirs": theirs, "fp": "pqrp:" + name, "at": rel(fp.GetPosition()),
                              "rot": round((fp.GetOrientationDegrees() + (180 if ours in TURN else 0) + 180) % 360 - 180, 3)}
        if name in saved:
            continue
        saved.add(name)
        f = pcbnew.FOOTPRINT(fp)
        f.SetPosition(pcbnew.VECTOR2I(0, 0))
        f.SetOrientationDegrees(0)
        for p in f.Pads():
            p.SetNetCode(0)
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pcbnew.ToMM(p.GetDrillSize().x) < DRILL:
                p.SetDrillSize(pcbnew.VECTOR2I_MM(DRILL, DRILL))      # U1's nine vias in its pad
        f.SetReference("REF**")
        f.SetValue(name)
        f.SetFPID(pcbnew.LIB_ID("pqrp", name))
        f.Models().clear()
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = f"{KI3D}/{model}"
        f.Models().append(m)
        pcbnew.FootprintSave(LIB, f)
        # their parts database's fields (a Windows datasheet path, a 4.7uF description on every 0402):
        # only Reference, Value and Footprint stay, and Datasheet and Description go empty
        path = os.path.join(LIB, name + ".kicad_mod")
        text = open(path).read()
        out_lines, skip = [], 0
        for line in text.split("\n"):
            if skip:
                skip += line.count("(") - line.count(")")
                continue
            if line.startswith("\t(property ki_"):        # their symbols' footprint filters
                continue
            m = re.match(r'\t\(property "([^"]+)" "', line)
            if m and m.group(1) not in ("Reference", "Value", "Footprint"):
                skip = line.count("(") - line.count(")")
                if m.group(1) not in ("Datasheet", "Description"):
                    continue
                line = re.sub(r'^(\t\(property "[^"]+" )".*?"', r'\1""', line)
                skip = 0
                out_lines.append(line)
                continue
            out_lines.append(line)
        open(path, "w").write("\n".join(out_lines))

    for t in b.GetTracks():
        net = NETS.get(t.GetNetname())
        if not net:
            continue
        if t.GetClass() == "PCB_VIA":
            at = rel(t.GetPosition())
            if inside(at):
                out["vias"].append({"net": net, "at": at, "dia": mm(t.GetWidth(pcbnew.F_Cu)), "drill": max(DRILL, mm(t.GetDrillValue()))})
        else:
            a, c = rel(t.GetStart()), rel(t.GetEnd())
            if inside(a) and inside(c):
                out["tracks"].append({"net": net, "layer": t.GetLayerName(), "a": a, "b": c, "w": mm(t.GetWidth())})
    # Tracks that only met their 3V3 pour (theirs covers the front; ours is ground) end on nothing
    # here: leave them out, until every end meets a pad, a via, a pour or a track of its net
    pads = [(NETS.get(p.GetNetname()), p) for r in PARTS for p in b.FindFootprintByReference(r).Pads()]
    pours = [(NETS.get(z.GetNetname()), z) for z in b.Zones() if not z.GetIsRuleArea()]
    def near(q, a, c, w):
        dx, dy = c[0] - a[0], c[1] - a[1]
        t = 0 if dx == dy == 0 else max(0, min(1, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        return ((q[0] - a[0] - t * dx) ** 2 + (q[1] - a[1] - t * dy) ** 2) ** 0.5 <= w / 2 + 1e-4
    def met(k, q):
        t = out["tracks"][k]
        pt = pcbnew.VECTOR2I_MM(q[0] + ox, q[1] + oy)
        layer = b.GetLayerID(t["layer"])
        same = lambda e, f: abs(e[0] - f[0]) + abs(e[1] - f[1]) < 1e-3
        other = t["b"] if q is t["a"] else t["a"]          # this track's other end
        # q meets a track at their shared joint only if q is that joint: a short piece whose far end
        # falls back on the joint (theirs, 0.007 mm, at C17) meets nothing
        return (any(o is not t and o["net"] == t["net"] and o["layer"] == t["layer"] and near(q, o["a"], o["b"], o["w"])
                    and not any(same(e, other) and not same(e, q) and near(q, e, e, o["w"]) for e in (o["a"], o["b"]))
                    for o in out["tracks"])
                or any(v["net"] == t["net"] and near(q, v["at"], v["at"], v["dia"]) for v in out["vias"])
                or any(n == t["net"] and p.IsOnLayer(layer) and p.HitTest(pt) for n, p in pads)
                or any(n == t["net"] and z.IsOnLayer(layer) and z.Outline().Contains(pt) and z.GetAssignedPriority() > 0 for n, z in pours))
    while True:
        loose = [k for k, t in enumerate(out["tracks"]) if not (met(k, t["a"]) and met(k, t["b"]))]
        if not loose:
            break
        for k in reversed(loose):
            print(f"  left out: {out['tracks'][k]}")
            del out["tracks"][k]
    for z in b.Zones():
        net = NETS.get(z.GetNetname())
        o = z.Outline()
        pts = [rel(o.CVertex(i)) for i in range(o.TotalVertices())]
        if not net or z.GetIsRuleArea() or not all(inside(q) for q in pts):
            continue
        out["zones"].append({"net": net, "layer": b.GetLayerName(z.GetLayerSet().Seq()[0]), "priority": z.GetAssignedPriority(),
                             "clearance": mm(z.GetLocalClearance() or 0), "min_width": mm(z.GetMinThickness()),
                             "solid": z.GetPadConnection() == pcbnew.ZONE_CONNECTION_FULL,
                             "thermal": [mm(z.GetThermalReliefGap()), mm(z.GetThermalReliefSpokeWidth())], "pts": pts})
    with open(os.path.join(HERE, "rpi_minimal.json"), "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    shutil.copy(os.path.join(src, "LICENSE.txt"), os.path.join(HERE, "lib", "RPI-MINIMAL-LICENSE.txt"))
    print(f"{len(saved)} footprints, {len(out['parts'])} parts, {len(out['tracks'])} tracks, {len(out['vias'])} vias, "
          f"{len(out['zones'])} pours from {out['source']}")


if __name__ == "__main__":
    main(sys.argv[1])
