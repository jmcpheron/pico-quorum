#!/usr/bin/env python3
"""Turn kicad-cli's BOM and position CSVs into JLCPCB's BOM and CPL, one pair per fit.

  python3 tools/jlc_bom_cpl.py --bom kicad-bom.csv --pos pos.csv --rotations rotations.json --out dir

BOM in  (kicad-cli sch export bom, grouped): Reference,Value,Footprint,LCSC,MPN,Fit,Qty,DNP
The JLCPCB "Comment" is the MPN where one is set, else the value.
POS in  (kicad-cli pcb export pos --format csv): Ref,Val,Package,PosX,PosY,Rot,Side
BOM out: Comment,Designator,Footprint,LCSC Part #
CPL out: Designator,Mid X,Mid Y,Layer,Rotation

Every board is the same copper; the Fit field says which boards get a part assembled. bom.csv and
cpl.csv are the base board (Fit "base"); bom-port.csv and cpl-port.csv add the key port's parts
(Fit "port"). One Gerber zip serves both.

Rows without an LCSC number, and DNP rows, are dropped from both files and listed on stderr.
Rotation offsets from rotations.json (substring match on the footprint name) are added to KiCad's
angle and normalised to [0, 360).
"""
import argparse, csv, json, sys, pathlib


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def split_refs(s):
    out = []
    for part in s.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:                                   # a range like R3-R5
            a, b = part.split("-", 1)
            prefix = a.rstrip("0123456789")
            lo, hi = int(a[len(prefix):]), int(b[len(prefix):])
            out += [f"{prefix}{i}" for i in range(lo, hi + 1)]
        else:
            out.append(part)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bom", required=True)
    ap.add_argument("--pos", required=True)
    ap.add_argument("--rotations", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    offsets = {}
    if a.rotations and pathlib.Path(a.rotations).exists():
        offsets = json.load(open(a.rotations)).get("offsets", {})

    bom_rows = read_csv(a.bom)
    pos_rows = {r["Ref"]: r for r in read_csv(a.pos)}
    fits = sorted({(r.get("Fit") or "base").strip() for r in bom_rows}, key=lambda f: f != "base")
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bad = False
    for fit in fits:
        rows = [r for r in bom_rows if (r.get("Fit") or "base").strip() in ("base", fit)]
        suffix = "" if fit == "base" else "-" + fit
        print(f"-- fit {fit}:", file=sys.stderr)
        bad |= write_pair(rows, pos_rows, offsets, out / f"bom{suffix}.csv", out / f"cpl{suffix}.csv")
    if bad:
        sys.exit(2)


def write_pair(bom_rows, pos_rows, offsets, bom_path, cpl_path):
    placed, skipped = {}, []
    out_bom = []
    for r in bom_rows:
        refs = split_refs(r.get("Reference", ""))
        lcsc = (r.get("LCSC") or "").strip()
        dnp = (r.get("DNP") or "").strip().lower() in ("1", "true", "yes", "dnp")
        if not lcsc or dnp:
            skipped.append((", ".join(refs), r.get("Value", ""), "DNP" if dnp else "no LCSC"))
            continue
        fp = r.get("Footprint", "")
        same = next((b for b in out_bom if b["LCSC Part #"] == lcsc), None)
        if same:                                  # one line per C-number (e.g. 7 identical switches)
            same["Designator"] += "," + ",".join(refs)
        else:
            out_bom.append({"Comment": (r.get("MPN") or "").strip() or r.get("Value", ""), "Designator": ",".join(refs),
                            "Footprint": fp.split(":")[-1], "LCSC Part #": lcsc})
        for ref in refs:
            placed[ref] = fp

    out_cpl = []
    missing_pos = []
    for ref, fp in sorted(placed.items()):
        p = pos_rows.get(ref)
        if not p:
            missing_pos.append(ref)
            continue
        rot = float(p["Rot"])
        for key, off in offsets.items():
            if key in fp:
                rot += float(off)
                break
        rot %= 360.0
        out_cpl.append({"Designator": ref, "Mid X": f'{float(p["PosX"]):.4f}mm',
                        "Mid Y": f'{float(p["PosY"]):.4f}mm',
                        "Layer": "Top" if p["Side"].lower().startswith("t") or p["Side"].lower() == "front" else "Bottom",
                        "Rotation": f"{rot:.1f}"})

    with open(bom_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writeheader(); w.writerows(out_bom)
    with open(cpl_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writeheader(); w.writerows(out_cpl)

    print(f"{bom_path.name}: {len(out_bom)} lines, {cpl_path.name}: {len(out_cpl)} parts", file=sys.stderr)
    if skipped:
        print("not in the assembly files:", file=sys.stderr)
        for refs, val, why in skipped:
            print(f"  {refs:24} {val:24} {why}", file=sys.stderr)
    if missing_pos:
        print("in BOM but not in the front position file (back side? THT?):", ", ".join(missing_pos), file=sys.stderr)
        return True
    return False


if __name__ == "__main__":
    main()
