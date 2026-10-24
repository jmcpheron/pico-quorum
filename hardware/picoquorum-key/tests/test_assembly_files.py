"""The assembly files (bom.csv, cpl.csv in hardware/out/rev-a), read back against the board.

JLCPCB assembles from two files: the BOM says which LCSC part goes where, the CPL (placement)
file says where each part's centre goes and how far to turn it. What can go wrong there doesn't
show up in DRC:

- a part missing from one file, or present when it shouldn't be (DNP U1, test pads, holes);
- an LCSC number that drifted from tools/gen/circuit.py;
- a position in the wrong frame (CPL is bottom-left origin, Y up);
- a footprint whose origin isn't the part's centre (JLCPCB places the body centre at Mid X/Y);
- a rotation in KiCad's convention where JLCPCB's differs. JLCPCB's 0 degrees is the part as drawn
  in its own (EasyEDA) library, so the check takes that footprint from hardware/lib/jlc.pretty,
  places it with the CPL's own numbers, and requires its pads to land on the board's pads.
  Parts without a JLCPCB footprint in the repo are listed, not passed.

It also writes hardware/out/scratch/test/assembly/placement-top.svg: every placed part with its
pin 1 marked and JLCPCB's footprint (where known) drawn where the CPL puts it, to compare with the
placement preview JLCPCB shows before you pay.
"""
import csv
import json
import math
import os
import unittest

import common
import circuit
from sexp import find, find_all, parse

OUT = os.path.join(common.ROOT, "hardware", "out", "rev-a")
BOM = os.environ.get("CONSOLE_BOM_CSV", os.path.join(OUT, "bom.csv"))
CPL = os.environ.get("CONSOLE_CPL_CSV", os.path.join(OUT, "cpl.csv"))
ROTATIONS = os.path.join(common.ROOT, "tools", "rotations.json")
JLC_LIB = os.path.join(common.ROOT, "hardware", "lib", "jlc.pretty")
# LCSC number -> JLCPCB's own footprint (fetched by tools/fetch_parts.sh)
JLC_FOOTPRINTS = {
    "C2919492": "FPC-SMD_8P-P0.50_HDGC_0.5K-HX-8PWB",
    "C2897501": "SW-SMD_4P-L4.5-W4.5-P3.00-LS6.8",
}
# Where our footprint numbers a pad differently from JLCPCB's on purpose: JLCPCB pad -> ours
# ('' = unnumbered). The tact's two terminals are the diagonal pads; the ZIF's hold-downs are MP.
RENUMBERED = {
    "C2897501": {"2": "", "3": "", "4": "2"},
    "C2919492": {"9": "MP", "10": "MP"},
}
CENTRE_TOL = 0.1        # mm: footprint origin vs. the centre of its pads
LAND_TOL = 0.05         # mm: a JLCPCB pad, placed by the CPL, vs. the board's pad
POLARISED = ("D", "J", "Q", "U")
NOTES = []


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def mmv(s):
    return float(s.replace("mm", ""))


def footprint_pads(path):
    """[(number, x, y, w, h)] from a .kicad_mod, in its own frame (Y down)."""
    out = []
    for p in find_all(parse(open(path).read()), "pad"):
        at, size = find(p, "at"), find(p, "size")
        rot = float(at[3]) if len(at) > 3 else 0.0
        w, h = float(size[1]), float(size[2])
        if round(rot) % 180 == 90:
            w, h = h, w
        out.append((str(p[1]), float(at[1]), float(at[2]), w, h))
    return out


def place(x, y, deg, ox, oy):
    """A footprint-local point (Y down) turned by `deg` (KiCad's sense: counter-clockwise as seen
    from the front) and moved to (ox, oy)."""
    a = math.radians(deg)
    return ox + x * math.cos(a) + y * math.sin(a), oy - x * math.sin(a) + y * math.cos(a)


@unittest.skipUnless(os.path.exists(BOM) and os.path.exists(CPL), "no bom.csv/cpl.csv: run tools/export.sh rev-a")
class AssemblyFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = common.board_facts()
        cls.H = cls.f["board"]["h"]
        cls.bom = read_csv(BOM)
        cls.cpl = {r["Designator"]: r for r in read_csv(CPL)}
        cls.lcsc_of = {}
        for row in cls.bom:
            for ref in row["Designator"].split(","):
                cls.lcsc_of[ref.strip()] = row["LCSC Part #"]
        cls.parts = {p.ref: p for p in circuit.PARTS}
        with open(ROTATIONS) as f:
            cls.offsets = json.load(f).get("offsets", {})
        write_svg(cls, os.path.dirname(common.scratch("assembly", "placement-top.svg")))

    @classmethod
    def tearDownClass(cls):
        if NOTES:
            print("\nassembly file notes:\n  " + "\n  ".join(NOTES))

    def placed(self):
        """Footprints JLCPCB should place: front, has copper pads, not DNP, not excluded."""
        return {r for r, fp in self.f["footprints"].items()
                if fp["layer"] == "F.Cu" and not fp["dnp"] and not fp["exclude_pos"]
                and any(p["copper"] and p["attr"] != "NPTH" for p in fp["pads"])}

    # --- the two files agree with each other and with the board ------------------------------
    def test_bom_and_cpl_name_the_same_parts(self):
        self.assertEqual(sorted(self.lcsc_of), sorted(self.cpl))

    def test_every_placeable_part_is_placed_and_nothing_else(self):
        self.assertEqual(sorted(self.cpl), sorted(self.placed()))
        for ref in ("U1", "TP1", "H1"):
            self.assertNotIn(ref, self.cpl, "%s must not be in the CPL" % ref)

    def test_no_designator_twice(self):
        refs = [r.strip() for row in self.bom for r in row["Designator"].split(",")]
        self.assertEqual(len(refs), len(set(refs)))

    def test_lcsc_numbers_match_circuit_py(self):
        for ref, lcsc in self.lcsc_of.items():
            with self.subTest(ref=ref):
                self.assertTrue(lcsc.startswith("C"), "no LCSC number")
                self.assertEqual(lcsc, self.parts[ref].lcsc)

    def test_positions_are_the_board_positions_in_the_cpl_frame(self):
        for ref, row in self.cpl.items():
            x, y = self.f["footprints"][ref]["pos"]
            with self.subTest(ref=ref):
                self.assertEqual(row["Layer"], "Top")
                self.assertAlmostEqual(mmv(row["Mid X"]), x, delta=0.001)
                self.assertAlmostEqual(mmv(row["Mid Y"]), self.H - y, delta=0.001)

    def test_rotations_are_kicads_plus_the_offset_table(self):
        for ref, row in self.cpl.items():
            fp = self.f["footprints"][ref]
            off = sum(v for k, v in self.offsets.items() if k in fp["lib"])
            with self.subTest(ref=ref):
                self.assertAlmostEqual((float(row["Rotation"]) - fp["rot"] - off) % 360, 0, delta=0.01)

    # --- placement against the part itself ---------------------------------------------------
    def test_footprint_origin_is_the_part_centre(self):
        """JLCPCB puts the body centre at Mid X/Y. An origin elsewhere shows up as a shifted part."""
        off = {}
        for ref in self.cpl:
            fp = self.f["footprints"][ref]
            pads = fp["pads"]
            x0 = min(p["bbox"][0] for p in pads); x1 = max(p["bbox"][2] for p in pads)
            y0 = min(p["bbox"][1] for p in pads); y1 = max(p["bbox"][3] for p in pads)
            d = math.hypot((x0 + x1) / 2 - fp["pos"][0], (y0 + y1) / 2 - fp["pos"][1])
            if d > CENTRE_TOL:
                off[ref] = round(d, 2)
        if off:
            NOTES.append("footprint origin away from the pad centre (mm): %s; check JLCPCB's placement "
                         "preview for these" % off)
        unexpected = {r: d for r, d in off.items() if not r.startswith(("J", "U3"))}
        self.assertEqual(unexpected, {}, "only the connectors and the SOT-223 are expected off-centre")

    def test_jlc_footprints_land_on_the_board_pads(self):
        """Place JLCPCB's own footprint with the CPL's numbers; each of its pads must land on a board pad."""
        checked, unchecked = [], set()
        for ref, row in sorted(self.cpl.items()):
            lcsc = self.lcsc_of[ref]
            if lcsc not in JLC_FOOTPRINTS:
                unchecked.add(lcsc)
                continue
            checked.append(ref)
            ref_pads = footprint_pads(os.path.join(JLC_LIB, JLC_FOOTPRINTS[lcsc] + ".kicad_mod"))
            board = [p for p in self.f["footprints"][ref]["pads"] if p["copper"]]
            ox, oy = mmv(row["Mid X"]), self.H - mmv(row["Mid Y"])
            for num, x, y, w, h in ref_pads:
                bx, by = place(x, y, float(row["Rotation"]), ox, oy)
                near = min(board, key=lambda p: math.hypot(p["pos"][0] - bx, p["pos"][1] - by))
                with self.subTest(ref=ref, jlc_pad=num):
                    self.assertLess(math.hypot(near["pos"][0] - bx, near["pos"][1] - by), LAND_TOL,
                                    "JLCPCB's pad %s lands %.2f mm from the nearest board pad: rotation or origin is off"
                                    % (num, math.hypot(near["pos"][0] - bx, near["pos"][1] - by)))
                    self.assertEqual(near["number"], RENUMBERED.get(lcsc, {}).get(num, num),
                                     "pad numbers disagree: placed turned round?")
        NOTES.append("rotation checked against JLCPCB's own footprint: %s" % ", ".join(checked))
        NOTES.append("no JLCPCB footprint in the repo to check rotation against: %s "
                     "(tools/fetch_parts.sh <C-number> adds one; until then, check these in JLCPCB's preview)"
                     % ", ".join(sorted(unchecked)))
        self.assertTrue(checked)

    def test_pin_one_table_for_the_polarised_parts(self):
        """Not a pass/fail on its own: prints where pin 1 sits on each polarised part, as you will see
        it in JLCPCB's preview (board front up), so the red pin-1 dots there can be compared."""
        rows = []
        for ref in sorted(r for r in self.cpl if r.startswith(POLARISED)):
            fp = self.f["footprints"][ref]
            p1 = next((p for p in fp["pads"] if p["number"] in ("1", "A1")), None)
            self.assertIsNotNone(p1, "%s has no pad 1" % ref)
            dx, dy = p1["pos"][0] - fp["pos"][0], p1["pos"][1] - fp["pos"][1]
            rows.append("%-3s pin %s %s of centre" % (ref, p1["number"], compass(dx, dy)))
        NOTES.append("pin 1, as seen from the front: " + "; ".join(rows))


def compass(dx, dy):
    """'upper left' style description of an offset in the board frame (Y down)."""
    v = "upper" if dy < -0.2 else "lower" if dy > 0.2 else ""
    h = "left" if dx < -0.2 else "right" if dx > 0.2 else ""
    return (" ".join(s for s in (v, h) if s)) or "at the centre"


def write_svg(cls, out_dir):
    W, H = cls.f["board"]["w"], cls.H
    body = ['<rect x="0" y="0" width="%s" height="%s" fill="#1d3b2a" rx="1.5"/>' % (W, H)]
    for ref, row in sorted(cls.cpl.items()):
        fp = cls.f["footprints"][ref]
        for p in fp["pads"]:
            if not p["copper"] or p["attr"] == "NPTH":
                continue
            x0, y0, x1, y1 = p["bbox"]
            pin1 = p["number"] in ("1", "A1") and ref.startswith(POLARISED)
            body.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="%s"/>'
                        % (x0, y0, x1 - x0, y1 - y0, "#ff5050" if pin1 else "#c9c9c9"))
        lcsc = cls.lcsc_of[ref]
        ox, oy = mmv(row["Mid X"]), H - mmv(row["Mid Y"])
        if lcsc in JLC_FOOTPRINTS:
            for num, x, y, w, h in footprint_pads(os.path.join(JLC_LIB, JLC_FOOTPRINTS[lcsc] + ".kicad_mod")):
                corners = [place(x + sx * w / 2, y + sy * h / 2, float(row["Rotation"]), ox, oy)
                           for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                body.append('<polygon points="%s" fill="none" stroke="#4fb3ff" stroke-width="0.08"/>'
                            % " ".join("%.3f,%.3f" % c for c in corners))
        # CPL centre and the direction of the part's 0-degree axis after rotation
        ex, ey = place(1.2, 0, float(row["Rotation"]), ox, oy)
        body.append('<circle cx="%.3f" cy="%.3f" r="0.25" fill="#ffd24f"/>' % (ox, oy))
        body.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#ffd24f" stroke-width="0.12"/>' % (ox, oy, ex, ey))
        body.append('<text x="%.3f" y="%.3f" font-size="1.0" fill="#ffffff" font-family="sans-serif">%s %s</text>'
                    % (ox + 0.4, oy - 0.4, ref, row["Rotation"]))
    body.append('<text x="0.5" y="%.2f" font-size="0.9" fill="#cccccc" font-family="sans-serif">'
                'grey: board pads, red: pin 1, blue: JLCPCB footprint placed by cpl.csv, yellow: CPL centre and 0-degree axis</text>' % (H + 1.5))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -1 %s %s" width="%smm" height="%smm">\n%s\n</svg>\n'
           % (W + 2, H + 4, (W + 2) * 4, (H + 4) * 4, "\n".join(body)))
    with open(os.path.join(out_dir, "placement-top.svg"), "w") as f:
        f.write(svg)


if __name__ == "__main__":
    unittest.main()
