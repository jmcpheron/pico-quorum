#!/usr/bin/env bash
# Render picoquorum-key as a finished device: the ER-TFT1.14-2 panel on its foam tape showing a mock
# screen, and the module fitted on the back. Works on a scratch copy; the real board is not touched.
#
#   tools/render/render_with_panel.sh        -> docs/img/rev-a-device-{top,iso,back}.png
#
# Needs uv (for Pillow) and kicad-cli.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$HERE/hardware/out/scratch/render"
BRD_DIR="$WORK/board"                     # ${KIPRJMOD}/../lib must resolve: see the symlink below
mkdir -p "$BRD_DIR"
ln -sfn "$HERE/hardware/lib" "$WORK/lib"

uv run -q --no-project --with pillow==12.3.0 python3 "$HERE/tools/render/panel_model.py" "$WORK"

SRC="$HERE/hardware/picoquorum-key/picoquorum-key.kicad_pcb"
PCB="$BRD_DIR/picoquorum-key-device.kicad_pcb"
python3 - "$SRC" "$PCB" "$WORK/panel.wrl" <<'PY'
import sys, uuid
src, dst, wrl = sys.argv[1:4]
s = open(src).read()
# fit the module (DNP on the real board) so the back render shows it
i = s.index('(property "Reference" "U1"'); a = s.rfind('\n\t(footprint ', 0, i); b = s.find('\n\t(footprint ', i)
s = s[:a] + s[a:b].replace("(attr smd dnp)", "(attr smd)", 1) + s[b:]
u = lambda: str(uuid.uuid4())
panel = f'''
	(footprint "render:ER-TFT1.14-2"
		(layer "F.Cu")
		(uuid "{u()}")
		(at 124.5 77.3)
		(property "Reference" "LCD1" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{u()}")
			(effects (font (size 1 1) (thickness 0.15))))
		(property "Value" "ER-TFT1.14-2" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{u()}")
			(effects (font (size 1 1) (thickness 0.15))))
		(attr board_only exclude_from_pos_files exclude_from_bom)
		(model "{wrl}" (offset (xyz 0 0 1.5)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
	)'''
k = s.rindex("\n)")
open(dst, "w").write(s[:k] + panel + s[k:])
PY
cp "$HERE/hardware/picoquorum-key/picoquorum-key.kicad_pro" "$BRD_DIR/picoquorum-key-device.kicad_pro"
cp "$HERE/hardware/picoquorum-key/fp-lib-table" "$BRD_DIR/" 2>/dev/null || true

R=(kicad-cli pcb render --quality high --floor --background opaque)
"${R[@]}" -w 1600 -h 2000 --side top -o "$HERE/docs/img/rev-a-device-top.png" "$PCB" >/dev/null 2>&1
"${R[@]}" -w 2400 -h 1800 --rotate '-48,0,32' --zoom 1.15 --perspective -o "$HERE/docs/img/rev-a-device-iso.png" "$PCB" >/dev/null 2>&1
"${R[@]}" -w 1600 -h 2000 --side bottom -o "$HERE/docs/img/rev-a-device-back.png" "$PCB" >/dev/null 2>&1
echo "wrote docs/img/rev-a-device-{top,iso,back}.png"
