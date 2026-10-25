"""Build the project symbol library hardware/lib/console.kicad_sym: the symbols KiCad's own
libraries lack.

  python3 tools/gen/make_symbols.py

  console:AP22653             Diodes AP22653W6-7, current-limited high-side switch (SOT-26). The pins
                              are feather-wing's symbol's: 1 IN, 2 GND, 3 EN, 4 FAULT, 5 ILIM, 6 OUT
  console:USB_C_Plug_12P      HRO TYPE-C-31-G-03, a 12-contact USB-C plug: A1-A7, A12, B9-B12 and the
                              shell. Its datasheet's pin table names them
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "hardware/lib/console.kicad_sym")


def _font(hide=False):
    return "(effects (font (size 1.27 1.27))%s)" % (" (hide yes)" if hide else "")


def _pin(kind, num, name, x, y, angle):
    return (f'(pin {kind} line (at {x} {y} {angle}) (length 2.54) '
            f'(name "{name}" {_font()}) (number "{num}" {_font()}))')


def box(name, ref, fp, ds, desc, w, h, pins):
    """pins: (number, name, type, side L/R/B, offset along the side)."""
    ps = []
    for num, pname, kind, side, off in pins:
        if side == "L":
            ps.append(_pin(kind, num, pname, -w - 2.54, off, 0))
        elif side == "R":
            ps.append(_pin(kind, num, pname, w + 2.54, off, 180))
        else:
            ps.append(_pin(kind, num, pname, off, -h - 2.54, 90))
    props = [("Reference", ref, 0, h + 1.27, False), ("Value", name, 0, -h - 1.27, False),
             ("Footprint", fp, 0, 0, True), ("Datasheet", ds, 0, 0, True), ("Description", desc, 0, 0, True)]
    pr = "\n  ".join(f'(property "{k}" "{v}" (at {x} {y} 0) {_font(hide)})' for k, v, x, y, hide in props)
    return (f'(symbol "{name}" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
            f'  {pr}\n'
            f'  (symbol "{name}_0_1" (rectangle (start {-w} {h}) (end {w} {-h}) (stroke (width 0.254) (type default)) (fill (type background))))\n'
            f'  (symbol "{name}_1_1"\n    ' + "\n    ".join(ps) + ")\n  (embedded_fonts no))")


SWITCH = box(
    "AP22653", "U", "Package_TO_SOT_SMD:SOT-23-6",
    "https://www.diodes.com/assets/Datasheets/AP22652_53_52A_53A.pdf",
    "Diodes AP22653: current-limited high-side switch, reverse blocking, output discharge, active-high EN, SOT-26",
    7.62, 5.08,
    [("1", "IN", "power_in", "L", 2.54), ("3", "EN", "input", "L", -2.54),
     ("6", "OUT", "power_out", "R", 2.54), ("4", "~{FAULT}", "open_collector", "R", -2.54),
     ("2", "GND", "power_in", "B", -2.54), ("5", "ILIM", "passive", "B", 2.54)])

PLUG_NAMES = [("A1", "GND"), ("A2", "SSTXp1"), ("A3", "SSTXn1"), ("A4", "VBUS"), ("A5", "CC"),
              ("A6", "D+"), ("A7", "D-"), ("A12", "GND"),
              ("B9", "VBUS"), ("B10", "SSRXn1"), ("B11", "SSRXp1"), ("B12", "GND")]
PLUG = box(
    "USB_C_Plug_12P", "J", "console:USB_C_Plug_HRO_TYPE-C-31-G-03_Edge",
    "https://www.lcsc.com/datasheet/C840338.pdf",
    "USB-C plug, 12 contacts and the shell, right angle at a board edge (HRO TYPE-C-31-G-03)",
    7.62, 10.16,
    [(n, name, "passive", "L" if n.startswith("A") else "R", 8.89 - 2.54 * i)
     for i, (n, name) in enumerate(PLUG_NAMES[:8])] +
    [(n, name, "passive", "R", 8.89 - 2.54 * i) for i, (n, name) in enumerate(PLUG_NAMES[8:])] +
    [("SH", "SHIELD", "passive", "B", 0)])


def main():
    with open(OUT, "w") as f:
        f.write("(kicad_symbol_lib (version 20241209) (generator \"make_symbols.py\") (generator_version \"10.0\")\n"
                + SWITCH + "\n" + PLUG + "\n)\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
