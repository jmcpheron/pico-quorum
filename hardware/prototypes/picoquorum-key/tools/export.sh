#!/usr/bin/env bash
# Export JLCPCB fabrication files for picoquorum-key with kicad-cli (KiCad 10).
#   tools/export.sh <rev>        e.g. tools/export.sh rev-a   -> hardware/out/rev-a/
# Refuses to export if ERC or DRC report violations.
set -euo pipefail

REV="${1:?usage: tools/export.sh <rev>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PRJ="$HERE/hardware/picoquorum-key"
SCH="$PRJ/picoquorum-key.kicad_sch"
PCB="$PRJ/picoquorum-key.kicad_pcb"
OUT="$HERE/hardware/out/$REV"
GERB="$OUT/gerbers"
KICAD_CLI="${KICAD_CLI:-kicad-cli}"

mkdir -p "$GERB"

echo "== ERC"
"$KICAD_CLI" sch erc --exit-code-violations --severity-error --severity-warning \
  --format report -o "$OUT/erc.txt" "$SCH" || { cat "$OUT/erc.txt"; echo "ERC violations: fix before exporting"; exit 1; }

echo "== DRC"
"$KICAD_CLI" pcb drc --exit-code-violations --severity-error --severity-warning \
  --schematic-parity --refill-zones --format report -o "$OUT/drc.txt" "$PCB" \
  || { cat "$OUT/drc.txt"; echo "DRC violations: fix before exporting"; exit 1; }

echo "== Gerbers"
rm -f "$GERB"/*
"$KICAD_CLI" pcb export gerbers -o "$GERB/" \
  --layers "F.Cu,B.Cu,F.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
  --no-x2 --no-netlist --subtract-soldermask --use-drill-file-origin "$PCB"

echo "== Drill"
"$KICAD_CLI" pcb export drill -o "$GERB/" --format excellon --drill-origin plot \
  --excellon-separate-th --excellon-units mm "$PCB"

(cd "$GERB" && rm -f ../picoquorum-key-gerbers.zip && zip -q ../picoquorum-key-gerbers.zip ./*)

echo "== Position file (front, mm)"
"$KICAD_CLI" pcb export pos -o "$OUT/picoquorum-key-pos.csv" --format csv --units mm \
  --side front --smd-only --exclude-dnp --use-drill-file-origin "$PCB"

echo "== BOM"
"$KICAD_CLI" sch export bom -o "$OUT/picoquorum-key-kicad-bom.csv" \
  --fields "Reference,Value,Footprint,LCSC,MPN,Fit,\${QUANTITY},\${DNP}" \
  --labels "Reference,Value,Footprint,LCSC,MPN,Fit,Qty,DNP" \
  --group-by "Value,Footprint,LCSC,Fit" --exclude-dnp "$SCH"

echo "== JLCPCB BOM + CPL, one pair per fit: bom.csv/cpl.csv (base), bom-port.csv/cpl-port.csv (with the key port)"
python3 "$HERE/tools/jlc_bom_cpl.py" \
  --bom "$OUT/picoquorum-key-kicad-bom.csv" --pos "$OUT/picoquorum-key-pos.csv" \
  --rotations "$HERE/tools/rotations.json" --out "$OUT"

echo
echo "wrote $OUT"
ls -1 "$OUT"
