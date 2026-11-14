#!/usr/bin/env bash
# Run the board tests (tests/): pin contract, mutation testing of DRC/netlist checks, geometry, fab and
# assembly files, holes, JLC DRC rules, 3D fit (FreeCAD), paste and mask, golden images,
# ngspice analog corners, and the firmware digital twin.
#
#   tools/test.sh                 everything
#   tools/test.sh test_geometry   one module (any unittest arguments work)
#
# Nothing under hardware/picoquorum-key or hardware/out/rev-* is written: scratch files go to
# hardware/out/scratch/test/, and the script fails if the board files changed while it ran.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
for tool in kicad-cli ngspice; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 2; }
done
KP="${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3}"
[ -x "$KP" ] || { echo "KiCad's Python not found at $KP (set KICAD_PYTHON)" >&2; exit 2; }

snapshot() { find hardware/picoquorum-key hardware/out/rev-* hardware/lib firmware docs -type f ! -name '*.lck' -print0 2>/dev/null | sort -z | xargs -0 shasum; }
BEFORE="$(snapshot)"

status=0
(cd tests && python3 -W ignore -m unittest "${@:-discover}") || status=$?

AFTER="$(snapshot)"
if [ "$BEFORE" != "$AFTER" ]; then
  echo "FAIL: the tests changed project files:" >&2
  diff <(echo "$BEFORE") <(echo "$AFTER") >&2 || true
  exit 1
fi
exit $status
