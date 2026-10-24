#!/usr/bin/env python3
"""Printable mockups of the S3 boards: the board with its front parts and panel as one solid, and
the ESP32-S3 module as a second, to print apart and glue to the back (README.md).

    tools/mockup/mockup.py [console-s3|picoquorum-key ...]     # both, if none named

Reads the routed .kicad_pcb with KiCad's Python (facts.py), the panel's place from the board's own
generator, and builds the solids in FreeCAD (build.py). Writes <board dir>/mockup/<board>-board.stl
and <board>-module.stl.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KICAD_PY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
KICAD_PY = KICAD_PY if os.path.exists(KICAD_PY) else "python3"   # on Linux, KiCad's pcbnew is in the system Python
FREECAD = os.environ.get("FREECADCMD") or shutil.which("freecadcmd") or next(
    (p for p in ("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",) if os.path.exists(p)), None)

# Heights in mm, by footprint name prefix, first match. console-s3's generator gives its own
# (jlc_spec()["fit"]["heights"]), which come first; these are PicoQuorumKey's (its
# tests/test_3d.py: switches 3.8, J1 3.2, J2 1.0) and typical datasheet figures for the rest.
HEIGHTS = [("R_0603", 0.55), ("C_0603", 0.9), ("C_0805", 1.25), ("LED_0603", 0.8), ("SOT-223", 1.8),
           ("SOT-23-5", 1.25), ("SOT-23-6", 1.45), ("SOT-23", 1.2), ("DFN-8", 0.6), ("FPC", 1.0),
           ("SW_Tact_4.5x4.5", 3.8), ("USB_C_Receptacle_HRO", 3.2)]
# ESP32-S3-WROOM-1: 18 x 25.5 x 3.1 (datasheet); its antenna end 6 mm, as console-s3's MOD_ANT.
# The board and shield split of the 3.1 mm and the shield's inset are rough.
MODULE = {"w": 18.0, "l": 25.5, "t": 3.1, "pcb": 0.8, "ant": 6.0, "shield_inset": 0.75}


def console_s3():
    import importlib.util
    path = os.path.join(ROOT, "hardware", "console-s3", "gen_console_s3.py")
    s = importlib.util.spec_from_file_location("gen_console_s3", path)
    g = importlib.util.module_from_spec(s)
    s.loader.exec_module(g)
    fit = g.jlc_spec()["fit"]
    solids = {x["name"]: x for x in fit["solids"]}
    panel = [solids["glass"]["box"], solids["ribbon fold"]["box"]]
    return {"pcb": os.path.join(ROOT, "hardware", "console-s3", "console-s3", "console-s3.kicad_pcb"),
            "out": os.path.join(ROOT, "hardware", "console-s3", "mockup"),
            "heights": list(fit["heights"].items()), "default_height": fit["default_height"],
            "panel": panel, "panel_top": solids["glass"]["z"][1]}


def picoquorum_key():
    # Its generator's numbers are y down from the top-left corner; the board's (facts.py) y up from
    # the bottom-left. The panel: 1.5 mm foam tape and the panel's 1.6 mm "with FPC folded"
    # (DESIGN.md, tests/test_3d.py); the fold up to 0.5 mm proud of the glass's end.
    base = os.path.join(ROOT, "hardware", "picoquorum-key")
    src = open(os.path.join(base, "tools", "gen", "gen_pcb.py")).read()
    c = {}
    for name in ("W, H, CORNER", "GLASS", "FOLD_Y"):
        line = re.search(r"^%s = .*$" % re.escape(name), src, re.M).group(0)
        exec(line.split("#")[0], {}, c)
    H, (gx0, gy0, gx1, gy1), (fy0, fy1) = c["H"], c["GLASS"], c["FOLD_Y"]
    return {"pcb": os.path.join(base, "hardware", "picoquorum-key", "picoquorum-key.kicad_pcb"),
            "out": os.path.join(base, "mockup"), "heights": [], "default_height": 1.0,
            "panel": [[gx0, H - gy1, gx1, H - gy0], [gx1, H - fy1, gx1 + 0.5, H - fy0]],
            "panel_top": 1.5 + 1.6}


BOARDS = {"console-s3": console_s3, "picoquorum-key": picoquorum_key}


def main(names):
    if not FREECAD:
        sys.exit("mockup: FreeCAD's freecadcmd not found (FREECADCMD)")
    for name in names or BOARDS:
        b = BOARDS[name]()
        print(name, flush=True)
        os.makedirs(b["out"], exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            facts, spec = os.path.join(tmp, "facts.json"), os.path.join(tmp, "spec.json")
            r = subprocess.run([KICAD_PY, os.path.join(HERE, "facts.py"), b["pcb"], facts], capture_output=True, text=True)
            if r.returncode:
                sys.exit(r.stdout + r.stderr)
            json.dump({"heights": b["heights"] + HEIGHTS, "default_height": b["default_height"], "switch_body": 0.55,
                       "panel": b["panel"], "panel_top": b["panel_top"], "module": MODULE}, open(spec, "w"))
            r = subprocess.run([FREECAD, os.path.join(HERE, "build.py")], capture_output=True, text=True,
                               env=dict(os.environ, MOCKUP=f"{facts}:{spec}:{b['out']}:{name}"))
            out = [l for l in r.stdout.splitlines() if l.startswith("  ")]
            print("\n".join(out))
            if r.returncode or len(out) < 2:
                sys.exit(r.stdout[-3000:] + r.stderr[-3000:])


if __name__ == "__main__":
    main(sys.argv[1:])
