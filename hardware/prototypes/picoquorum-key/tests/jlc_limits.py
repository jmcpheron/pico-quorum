"""JLCPCB's manufacturing limits for a 2-layer, 1.6 mm, 1 oz board, in one place.

Source: https://jlcpcb.com/capabilities/pcb-capabilities, read 2026-10-23. Re-read it before each
order: the numbers change, and a test that passes against stale limits proves nothing.
Where the project's own rules (hardware/picoquorum-key/picoquorum-key.kicad_pro) are stricter, that's fine:
these are the floor, not the target.
"""
SOURCE = "https://jlcpcb.com/capabilities/pcb-capabilities (read 2026-10-23)"

# copper
TRACK_MIN = 0.10                # trace width, 1 oz
SPACE_MIN = 0.10                # trace to trace
PAD_TO_PAD_MIN = 0.15           # SMD pad to pad, different nets
COPPER_TO_OUTLINE_MIN = 0.20    # copper to a routed edge

# vias: "via diameter should be 0.1 mm (0.15 preferred) larger than the hole"
VIA_DRILL_MIN = 0.15
VIA_DIAMETER_MIN = 0.25
VIA_RING_MIN = 0.05             # (diameter - drill) / 2
VIA_RING_PREFERRED = 0.075
VIA_TO_VIA_MIN = 0.20           # hole to hole
VIA_HOLE_TO_TRACK_MIN = 0.20

# plated through holes (component holes and plated slots)
PTH_DRILL_MIN = 0.15
PTH_RING_MIN = 0.18             # 2-layer, 1 oz: absolute minimum
PTH_RING_PREFERRED = 0.25
PAD_HOLE_TO_HOLE_MIN = 0.45
PTH_TO_TRACK_MIN = 0.28         # 0.35 recommended
PLATED_SLOT_WIDTH_MIN = 0.50    # length at least 2x width

# non-plated holes
NPTH_DRILL_MIN = 0.50
NPTH_SLOT_WIDTH_MIN = 1.00
NPTH_TO_TRACK_MIN = 0.20

DRILL_MAX = 6.30               # largest drill bit

# drill tolerance: a finished hole can come out this much larger / smaller
DRILL_TOL_PLUS, DRILL_TOL_MINUS = 0.13, 0.08
HOLE_POSITION_TOL = 0.075

# solder mask and silk
MASK_DAM_MIN = 0.10             # green mask between two openings
MASK_TO_TRACE_MIN = 0.09        # mask opening edge to a neighbouring trace
SILK_LINE_MIN = 0.15
SILK_TEXT_MIN = 1.0
SILK_TO_PAD_MIN = 0.15
