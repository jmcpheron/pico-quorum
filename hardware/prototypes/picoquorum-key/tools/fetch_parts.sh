#!/usr/bin/env bash
# Pull symbol + footprint + 3D model for JLCPCB/LCSC parts that KiCad's bundled libraries lack,
# into hardware/lib/jlc.* using easyeda2kicad (run through uv, nothing installed globally).
#   tools/fetch_parts.sh            fetches the default list below
#   tools/fetch_parts.sh C123456    fetches one more part
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$HERE/hardware/lib/jlc"
mkdir -p "$HERE/hardware/lib"
PARTS=(
  C2919492   # HDGC 0.5K-HX-8PWB  FPC 0.5mm 8-pin flip-lock, double-sided contacts
  C2897501   # BOOMELE 4.5x4.5x3.8 tactile switch
  C2913204   # ESP32-S3-WROOM-1-N8R2 (3D model; footprint cross-check against RF_Module:ESP32-S3-WROOM-1)
)
if [ $# -gt 0 ]; then PARTS=("$@"); fi
for p in "${PARTS[@]}"; do
  echo "== $p"
  uvx easyeda2kicad --full --lcsc_id "$p" --output "$LIB" --overwrite
done
echo
echo "Add to the project libraries (Preferences > Manage Symbol/Footprint Libraries, project scope):"
echo "  symbols:    \${KIPRJMOD}/../lib/jlc.kicad_sym"
echo "  footprints: \${KIPRJMOD}/../lib/jlc.pretty"
echo "3D models land in hardware/lib/jlc.3dshapes; set KICAD_3DMODEL_DIR or the path in each footprint."
