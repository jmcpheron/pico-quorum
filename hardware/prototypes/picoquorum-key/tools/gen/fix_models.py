"""Make the two LCSC 3D models fit for a mechanical check (run once; the outputs are committed).

  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd tools/gen/fix_models.py

easyeda2kicad's models (hardware/lib/jlc.3dshapes, from tools/fetch_parts.sh) are drawn for a
picture, not a fit check:
- the tact switch is a generic 6.5 mm part, and its .step has its origin 2.9 mm up the body, so a
  STEP export sinks it through the board (KiCad scales a .wrl, but ignores scale on a .step);
- the ZIF's flip actuator is drawn standing open, 1.75 mm tall; fitted, it lies closed on the
  1.0 mm body, under the glass;
- both .step files sit up to 0.05 mm off their .wrl twins.

Each model is moved so its .step box matches its .wrl box, then both are cut at the part's real
height: the .step with a boolean, the .wrl by clamping its points (what sticks up flattens onto the
cut). Outputs, with no offset or scale needed in the footprint, go to hardware/lib/console.3dshapes:
  SW_Tact_4.5x4.5x3.8.{wrl,step}   cut at 3.8 mm: BOOMELE C2897501 is 4.5 x 4.5 x 3.8
  FPC_0.5mm_8P_closed.{wrl,step}   cut at 1.0 mm: actuator closed
freecadcmd can't write STEP colours, so the .step files are plain grey; renders use the .wrl.
"""
import os
import re

import FreeCAD as App
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__) if "__file__" in dir() else os.getcwd()))
if not os.path.isdir(os.path.join(ROOT, "hardware")):
    ROOT = os.getcwd()                     # freecadcmd may not set __file__
SRC = os.path.join(ROOT, "hardware/lib/jlc.3dshapes")
OUT = os.path.join(ROOT, "hardware/lib/console.3dshapes")
INCH = 2.54                                # KiCad's .wrl unit is 0.1 inch

MODELS = [  # source stem, output stem, height (mm)
    ("SW-SMD_4P-L4.5-W4.5-H6.5-P3.00-LS6.8", "SW_Tact_4.5x4.5x3.8", 3.8),
    ("FPC-SMD_8P-P0.50_HDGC_0.5K-HX-8PWB", "FPC_0.5mm_8P_closed", 1.0),
]
TRIPLE = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE]-?\d+)?) (-?\d+(?:\.\d+)?(?:[eE]-?\d+)?) (-?\d+(?:\.\d+)?(?:[eE]-?\d+)?)")


def wrl_box(text):
    pts = [tuple(float(v) * INCH for v in m.groups())
           for blk in re.findall(r"point \[(.*?)\]", text, re.S) for m in TRIPLE.finditer(blk)]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def clamp_wrl(text, height):
    top = height / INCH

    def block(m):
        def pt(t):
            x, y, z = t.groups()
            return "%s %s %s" % (x, y, ("%.4f" % top) if float(z) > top else z)
        return m.group(1) + TRIPLE.sub(pt, m.group(2)) + m.group(3)
    return re.sub(r"(point \[)(.*?)(\])", block, text, flags=re.S)


def main():
    os.makedirs(OUT, exist_ok=True)
    for src, dst, height in MODELS:
        wrl = open(os.path.join(SRC, src + ".wrl")).read()
        lo, _ = wrl_box(wrl)
        if abs(lo[2]) > 0.01:
            raise SystemExit("%s.wrl does not sit on z = 0" % src)
        shape = Part.read(os.path.join(SRC, src + ".step"))
        b = shape.BoundBox
        shape.translate(App.Vector(lo[0] - b.XMin, lo[1] - b.YMin, lo[2] - b.ZMin))
        cut = shape.common(Part.makeBox(100, 100, height, App.Vector(-50, -50, 0)))
        cut.exportStep(os.path.join(OUT, dst + ".step"))
        out = clamp_wrl(wrl, height).replace("easyeda2kicad.py", "easyeda2kicad.py, cut to %.1f mm by tools/gen/fix_models.py" % height, 1)
        open(os.path.join(OUT, dst + ".wrl"), "w").write(out)
        cb = cut.BoundBox
        print("%s: moved (%.2f, %.2f, %.2f), cut at %.1f -> %s, box z %.2f..%.2f"
              % (dst, lo[0] - b.XMin, lo[1] - b.YMin, lo[2] - b.ZMin, height, OUT, cb.ZMin, cb.ZMax))


main()
