"""JLCPCB's limits for a standard 2-layer board, 1 oz copper, green mask: the numbers every check in
tools/jlc holds a board to, and the KiCad rule file built from them (dru_text).

Read from https://jlcpcb.com/capabilities/pcb-capabilities on 2026-10-23 (the page has no version;
its mask section says "LDI equipment upgraded in June 2025"). Read the page again before each order:
JLCPCB changes it. Where the page gives a recommended value and an absolute one, the absolute one is
the limit and the other is a warning.
"""

SOURCE = "https://jlcpcb.com/capabilities/pcb-capabilities, read 2026-10-23"

# name: (mm, the page's words)
LIMITS = {
    "track": (0.10, "Min. trace width: 1- and 2-layer 0.10 mm (4 mil)"),
    "gap": (0.10, "Min. trace spacing: 1- and 2-layer 0.10 mm (4 mil)"),
    "via_drill": (0.15, "Min. via hole size/diameter 0.15/0.25mm"),
    "via_diameter": (0.25, "Min. via hole size/diameter 0.15/0.25mm"),
    "via_ring": (0.05, "Via diameter should be 0.1mm (0.15mm preferred) larger than via hole size: 0.05 a side"),
    "via_ring_preferred": (0.075, "the 0.15 mm preferred, 0.075 a side"),
    "pth_ring": (0.20, "PTH annular ring >=0.20mm"),
    "npth": (0.50, "Min. non-plated holes 0.50mm"),
    "slot": (0.50, "Min. plated slot width, 2-layer 0.5mm"),
    "via_hole_to_hole": (0.20, "Via hole-to-hole spacing 0.2mm"),
    "pad_hole_to_hole": (0.45, "Pad hole-to-hole spacing 0.45mm"),
    "via_hole_to_track": (0.20, "Via hole to track 0.2mm"),
    "pth_to_track": (0.28, "PTH to track: 0.35mm is recommended, minimum 0.28mm"),
    "npth_to_track": (0.20, "NPTH to track 0.2mm"),
    "edge": (0.20, "Copper clearance from routed board edges >=0.2 mm"),
    "mask_dam": (0.10, "Min. pad spacing (mask bridge) 0.10 mm green, red, yellow, blue, purple; 0.13 black, white"),
    "silk_line": (0.15, "Silkscreen minimum line width >=0.15mm"),
    "silk_text": (1.00, "Minimum text height 40 mil (1.0mm)"),
    "silk_to_pad": (0.15, "Pad to silkscreen 0.15mm"),
}


def mm(name):
    return LIMITS[name][0]


def dru_text():
    """The limits as a KiCad custom rule file. KiCad applies the strictest rule that matches, with its
    own project rules on top, so a board's own tighter numbers still hold."""
    r = [f"(version 1)\n# JLCPCB 2-layer limits, from tools/jlc/limits.py ({SOURCE})"]

    def rule(name, constraint, value, cond=None, layer=None):
        c = f' (condition "{cond}")' if cond else ""
        l = f' (layer "{layer}")' if layer else ""
        r.append(f'(rule "JLC {name}"{l}{c} (constraint {constraint} (min {value}mm)))')
    rule("track", "track_width", mm("track"))
    rule("gap", "clearance", mm("gap"))
    rule("via drill", "hole_size", mm("via_drill"), "A.Type == 'Via'")
    rule("via diameter", "via_diameter", mm("via_diameter"), "A.Type == 'Via'")
    rule("via ring", "annular_width", mm("via_ring"), "A.Type == 'Via'")
    rule("PTH ring", "annular_width", mm("pth_ring"), "A.Type == 'Pad' && A.Pad_Type == 'Through-hole'")
    rule("NPTH", "hole_size", mm("npth"), "A.Type == 'Pad' && A.Pad_Type == 'NPTH, mechanical'")
    rule("via hole to hole", "hole_to_hole", mm("via_hole_to_hole"))
    rule("pad hole to hole", "hole_to_hole", mm("pad_hole_to_hole"), "A.Type == 'Pad' && B.Type == 'Pad'")
    rule("hole to copper", "hole_clearance", mm("via_hole_to_track"))
    rule("PTH to track", "hole_clearance", mm("pth_to_track"), "A.Type == 'Pad' && A.Pad_Type == 'Through-hole' && B.Type == 'Track'")
    rule("edge", "edge_clearance", mm("edge"))
    rule("silk line", "text_thickness", mm("silk_line"), layer="?.Silkscreen")
    rule("silk text", "text_height", mm("silk_text"), layer="?.Silkscreen")
    rule("silk to pad", "silk_clearance", mm("silk_to_pad"), layer="?.Silkscreen")
    return "\n".join(r) + "\n"
