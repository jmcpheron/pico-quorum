#!/usr/bin/env bash
# Autoroute the picoquorum-key board with Freerouting, through KiCad's Specctra DSN/SES round trip.
#
#   FREEROUTING_JAR=~/.local/share/freerouting/freerouting-2.5.0.jar tools/autoroute.sh
#   (JAVA defaults to Homebrew's openjdk; PASSES defaults to 100)
#
# Needs Java 25+ (brew install openjdk) and Freerouting 2.5
# (https://github.com/freerouting/freerouting/releases). Neither is
# installed by this repo. The result is a starting point: review every route in KiCad (USB pair,
# SPI to the ZIF, 3V3 at the module, nothing in the antenna band), then run DRC.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PCB="$HERE/hardware/picoquorum-key/picoquorum-key.kicad_pcb"
WORK="$HERE/hardware/out/scratch/route"
KP="${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3}"
: "${FREEROUTING_JAR:?set FREEROUTING_JAR to the Freerouting .jar}"
JAVA="${JAVA:-/opt/homebrew/opt/openjdk/bin/java}"
mkdir -p "$WORK"

cp "$PCB" "$WORK/before-autoroute.kicad_pcb"
"$KP" "$HERE/tools/gen/specctra.py" export "$PCB" "$WORK/picoquorum-key.dsn"
"$JAVA" -Djava.awt.headless=true -jar "$FREEROUTING_JAR" \
  --gui.enabled=false --usage_and_diagnostic_data.disable_analytics=true \
  -de "$WORK/picoquorum-key.dsn" -do "$WORK/picoquorum-key.ses" -mp "${PASSES:-100}"
"$KP" "$HERE/tools/gen/specctra.py" import "$PCB" "$WORK/picoquorum-key.ses"
cp "$PCB" "$WORK/after-autoroute.kicad_pcb"

# tidy: re-drill thin-ring vias, widen neck-downs, add GND stitching vias, then drop any that DRC
# objects to (tools/gen/post_route.py, tools/gen/drc_prune.py)
"$KP" "$HERE/tools/gen/post_route.py" "$PCB"
for pass in 1 2 3; do        # removing a stray GND piece can leave the next one dangling
  kicad-cli pcb drc --severity-all --format json -o "$WORK/drc.json" "$PCB" >/dev/null || true
  "$KP" "$HERE/tools/gen/drc_prune.py" "$PCB" "$WORK/drc.json"
done
kicad-cli pcb drc --schematic-parity --severity-all --format report -o "$WORK/drc.txt" "$PCB" || true
grep -E "Found" "$WORK/drc.txt"
echo "board saved; the pre-route copy is $WORK/before-autoroute.kicad_pcb"
