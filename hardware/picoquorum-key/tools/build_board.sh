#!/usr/bin/env bash
# Regenerate picoquorum-key from tools/gen/circuit.py and the placement in tools/gen/gen_pcb.py:
#   project footprints -> schematic -> ERC -> netlist -> netlist check -> placed board -> DRC
#
#   tools/build_board.sh            stops if the schematic or board was edited by hand / has tracks
#   tools/build_board.sh --force    rebuilds both from scratch (hand edits and routing are lost)
#
# Once routing starts in KiCad, the KiCad files are the truth: edit them there, not here.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PRJ="$HERE/hardware/picoquorum-key"
WORK="$HERE/hardware/out/scratch/build"
KP="${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3}"
FORCE="${1:-}"
mkdir -p "$WORK"
quiet() { grep -v -E "Fontconfig|stdpbase|memory leak|^Plotted|^Done" || true; }

echo "== footprints";  python3 "$HERE/tools/gen/make_footprints.py"
echo "== schematic";   python3 "$HERE/tools/gen/gen_sch.py" $FORCE
echo "== ERC"
kicad-cli sch erc --severity-all --exit-code-violations --format report -o "$WORK/erc.txt" "$PRJ/picoquorum-key.kicad_sch" 2>&1 | quiet \
  || { cat "$WORK/erc.txt"; exit 1; }
grep -E "ERC messages" "$WORK/erc.txt"
echo "== netlist"
kicad-cli sch export netlist --format kicadsexpr -o "$WORK/picoquorum-key.net" "$PRJ/picoquorum-key.kicad_sch" 2>&1 | quiet
python3 "$HERE/tools/gen/check_netlist.py" "$WORK/picoquorum-key.net"
echo "== board"
"$KP" "$HERE/tools/gen/gen_pcb.py" "$WORK/picoquorum-key.net" $FORCE 2>&1 | quiet
echo "== DRC (unrouted connections are expected until the board is routed)"
kicad-cli pcb drc --severity-all --schematic-parity --format report -o "$WORK/drc.txt" "$PRJ/picoquorum-key.kicad_pcb" 2>&1 | quiet
grep -E "^\*\* Found" "$WORK/drc.txt"
