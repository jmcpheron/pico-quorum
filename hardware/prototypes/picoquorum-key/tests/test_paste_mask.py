"""Solder paste and solder mask, read back from the Gerbers JLCPCB will build the stencil and mask from.

test_fab_files already checks that every opening is a pad and every pad has its opening, that paste
is never bigger than its pad, and the mask webs between nets. This module checks how well the
stencil will print and what the mask leaves bare:
- stencil aperture area ratio (IPC-7525: opening area / wall area >= 0.66) and aspect ratio
  (width / thickness >= 1.5) at a 0.12 mm stencil, and the thickest stencil every opening tolerates;
- paste coverage per pad, and both ends of every two-pad part getting the same paste (unequal paste
  pulls a small part up on one end in reflow);
- the steel between neighbouring apertures (a stencil web too thin tears or smears);
- paste only on parts JLCPCB places (paste on an unplaced pad leaves a solder blob);
- every mask opening at least as big as its copper (an opening that falls short leaves mask on the pad);
- no other net's track bare in, or within JLCPCB's mask-to-trace minimum of, a pad's mask opening.
Pictures: hardware/out/scratch/test/paste/closeups.svg (copper, mask, paste and area ratio for the
fine-pitch parts) and front-paste.svg (every aperture coloured by its area ratio).
"""
import csv
import math
import os
import unittest

import common
import gerber
import jlc_limits as jlc

ZIP = os.environ.get("CONSOLE_FAB_ZIP", os.path.join(common.OUT, "picoquorum-key-gerbers.zip"))
# the port board's CPL: one stencil serves both, and only the port board places a part on every
# pasted pad (on a base board the port's pads get paste and no part, DESIGN.md)
CPL = os.environ.get("CONSOLE_CPL_CSV", os.path.join(common.OUT, "cpl-port.csv"))
STENCIL_T = 0.12          # mm: JLCPCB's standard stencils are 0.10-0.20 mm and its engineers pick one per
STENCIL_CHOICES = (0.10, 0.12, 0.15, 0.18, 0.20)   # design unless told; 0.12 is the usual for 0603 and 0.5 mm pitch
AREA_RATIO_MIN = 0.66     # IPC-7525: below this, paste sticks in the aperture instead of printing
ASPECT_MIN = 1.5          # IPC-7525: narrowest side over thickness
STENCIL_WEB_MIN = 0.10    # mm of steel between two apertures
BALANCE_TOL = 0.10        # two-pad parts: the two ends' paste areas within 10 %
COVERAGE = (0.5, 1.0)     # paste area over pad area
CLOSEUPS = ["J2", "U4", "U2", "U3", "J1", "Q1", "C6"]
NOTES = []


def area(ap):
    hx, hy = ap.half
    r = ap.params[0] if ap.kind == "RoundRect" else (min(hx, hy) if ap.kind == "O" else 0.0)
    if ap.kind == "C":
        return math.pi * hx * hx
    return 4 * hx * hy - (4 - math.pi) * r * r


def perimeter(ap):
    hx, hy = ap.half
    r = ap.params[0] if ap.kind == "RoundRect" else (min(hx, hy) if ap.kind == "O" else 0.0)
    if ap.kind == "C":
        return 2 * math.pi * hx
    return 4 * (hx + hy) - 8 * r + 2 * math.pi * r


def area_ratio(ap, t):
    return area(ap) / (perimeter(ap) * t)


def thickest(ap):
    """Thickest stencil (mm) that still meets both IPC ratios for this aperture."""
    return min(area(ap) / (perimeter(ap) * AREA_RATIO_MIN), 2 * min(ap.half) / ASPECT_MIN)


def seg_to_opening(a, b, x, y, ap):
    """Distance from a track's centre line (a to b) to a mask opening's edge (0 if it crosses in):
    a rounded rectangle is the inner rectangle grown by its corner radius."""
    hx, hy = ap.half
    r = ap.params[0] if ap.kind == "RoundRect" else (min(hx, hy) if ap.kind in ("O", "C") else 0.0)
    ix, iy = hx - r, hy - r
    n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.01))
    best = float("inf")
    for i in range(n + 1):
        px = a[0] + (b[0] - a[0]) * i / n - x
        py = a[1] + (b[1] - a[1]) * i / n - y
        dx, dy = max(abs(px) - ix, 0.0), max(abs(py) - iy, 0.0)
        best = min(best, max(math.hypot(dx, dy) - r, 0.0))
    return best


@unittest.skipUnless(os.path.exists(ZIP), "no Gerber zip: run tools/export.sh " + common.REV)
class PasteMask(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = common.board_facts()
        cls.H = cls.f["board"]["h"]
        layers = {}
        for name, text in gerber.read_zip(ZIP).items():
            if not name.endswith((".drl", ".gbrjob")):
                g = gerber.Gerber(text)
                layers[g.attrs.get("FileFunction", name)] = g
        cls.layers = layers
        cls.pads = [(ref, p) for ref, fp in cls.f["footprints"].items() for p in fp["pads"]]
        # every flash on a layer, tied to the board pad at its position: [(x, y, aperture, ref, pad)]
        cls.paste = cls.tie("Paste,Top", "F.Paste", "paste")
        cls.cu = {"F": cls.tie("Copper,L1,Top", "F.Cu", "copper"), "B": cls.tie("Copper,L2,Bot", "B.Cu", "copper")}
        cls.mask = {"F": cls.tie("Soldermask,Top", "F.Mask", "mask"), "B": cls.tie("Soldermask,Bot", "B.Mask", "mask")}

    @classmethod
    def tearDownClass(cls):
        cls.draw()
        if NOTES:
            print("\npaste and mask notes (pictures in %s):\n  " % common.scratch("paste") + "\n  ".join(NOTES))

    @classmethod
    def tie(cls, fn, layer, key):
        cands = [(ref, p) for ref, p in cls.pads if layer in p[key]]
        out = []
        for x, y, ap in cls.layers[fn].flashes:
            bx, by = x, cls.H - y
            best = min(cands, key=lambda rp: gerber.dist(bx, by, rp[1]["pos"][0], rp[1]["pos"][1]), default=None)
            if best and gerber.dist(bx, by, best[1]["pos"][0], best[1]["pos"][1]) < 0.05 and ap.half:
                out.append((bx, by, ap, best[0], best[1]))
        return out

    def copper_of(self, side, ref, pad):
        return next(c for c in self.cu[side] if c[3] == ref and c[4] is pad)

    # --- stencil printability ---------------------------------------------------------------
    def test_stencil_area_and_aspect_ratios(self):
        worst = []
        for x, y, ap, ref, p in self.paste:
            ar = area_ratio(ap, STENCIL_T)
            asp = 2 * min(ap.half) / STENCIL_T
            worst.append((ar, asp, thickest(ap), "%s.%s" % (ref, p["number"]), ap.size))
            with self.subTest(pad="%s.%s" % (ref, p["number"])):
                self.assertGreaterEqual(ar, AREA_RATIO_MIN, "area ratio at %.2f mm" % STENCIL_T)
                self.assertGreaterEqual(asp, ASPECT_MIN, "aspect ratio at %.2f mm" % STENCIL_T)
        worst.sort()
        ar, asp, t, name, size = worst[0]
        tmax = min(w[2] for w in worst)
        ok = [c for c in STENCIL_CHOICES if c <= tmax + 1e-9]
        NOTES.append("stencil at %.2f mm: lowest area ratio %.2f on %s (%.2f x %.2f mm), IPC minimum %.2f"
                     % (STENCIL_T, ar, name, size[0], size[1], AREA_RATIO_MIN))
        NOTES.append("thickest stencil every aperture tolerates: %.3f mm (limited by %s) -> of JLCPCB's standard "
                     "%s mm, choose %s" % (tmax, min(worst, key=lambda w: w[2])[3],
                                            "/".join("%.2f" % c for c in STENCIL_CHOICES), " or ".join("%.2f" % c for c in ok)))

    def test_stencil_webs(self):
        webs = []
        for i, (ax, ay, aa, ar_, ap_) in enumerate(self.paste):
            for bx, by, ba, br, bp in self.paste[i + 1:]:
                gx = abs(ax - bx) - aa.half[0] - ba.half[0]
                gy = abs(ay - by) - aa.half[1] - ba.half[1]
                if gx < 0 and gy < 0:
                    continue                    # overlapping: one opening (J1's stacked A/B contacts)
                if gx < 1 and gy < 1:
                    webs.append((math.hypot(max(gx, 0), max(gy, 0)), "%s.%s" % (ar_, ap_["number"]), "%s.%s" % (br, bp["number"])))
        thin = sorted(w for w in webs if w[0] < STENCIL_WEB_MIN)
        self.assertEqual(thin, [], "stencil steel under %.2f mm between apertures" % STENCIL_WEB_MIN)
        w = min(webs)
        NOTES.append("thinnest stencil web: %.3f mm, between %s and %s" % w)

    # --- how much paste, and where -------------------------------------------------------------
    def test_paste_coverage_per_pad(self):
        """Per copper pad: a window-pane aperture's panes (common.pane_of) add up on their pad."""
        paste = {}
        for i, (x, y, ap, ref, p) in enumerate(self.paste):
            pad = common.pane_of(self.f["footprints"][ref], p)
            paste.setdefault((ref, id(pad)) if pad else i, [ref, pad or p, 0.0])[2] += area(ap)
        big = []
        for ref, p, pa in paste.values():
            cu = self.copper_of("F", ref, p)[2]
            cov = pa / area(cu)
            with self.subTest(pad="%s.%s" % (ref, p["number"])):
                self.assertGreaterEqual(cov, COVERAGE[0] - 1e-6)
                self.assertLessEqual(cov, COVERAGE[1] + 1e-6)
            if area(cu) > 4.0:
                big.append("%s.%s %.1f mm2 at %.0f %%" % (ref, p["number"], area(cu), 100 * cov))
        if big:
            NOTES.append("large pads (paste coverage): %s. Over ~4 mm2 a full aperture can float the part; "
                         "a window-pane aperture at 50-80 %% is the usual fix if it shows up in reflow" % "; ".join(big))

    def test_two_pad_parts_get_equal_paste_on_each_end(self):
        by_ref = {}
        for x, y, ap, ref, p in self.paste:
            by_ref.setdefault(ref, []).append(area(ap))
        for ref, areas in sorted(by_ref.items()):
            if len(areas) != 2:
                continue
            with self.subTest(part=ref):
                self.assertLessEqual(abs(areas[0] - areas[1]) / max(areas), BALANCE_TOL)

    def test_paste_only_on_parts_jlcpcb_places(self):
        with open(CPL, newline="") as f:
            placed = {r["Designator"] for r in csv.DictReader(f)}
        stray = sorted({ref for x, y, ap, ref, p in self.paste if ref not in placed})
        self.assertEqual(stray, [], "paste on parts not in the CPL")
        missing = sorted(r for r in placed if self.f["footprints"][r]["layer"] == "F.Cu"
                         and not any(ref == r for _, _, _, ref, _ in self.paste))
        self.assertEqual(missing, [], "placed front parts with no paste at all")

    # --- solder mask -------------------------------------------------------------------------
    def test_mask_openings_cover_their_copper(self):
        short = []
        for side in ("F", "B"):
            for x, y, ap, ref, p in self.mask[side]:
                if p["attr"] == "NPTH" or not any(c[3] == ref and c[4] is p for c in self.cu[side]):
                    continue
                cu = self.copper_of(side, ref, p)[2]
                ex = min(ap.half[0] - cu.half[0], ap.half[1] - cu.half[1])
                if ex < -1e-6:
                    short.append(("%s.%s" % (ref, p["number"]), side, round(ex, 3)))
        self.assertEqual(short, [], "mask opening smaller than its copper")

    def test_other_nets_stay_clear_of_pad_openings(self):
        """No other net's track bare in a pad's opening (it would solder to the pad), and at least
        JLCPCB's mask-to-trace minimum from the opening's edge, so mask registration can't bare it."""
        close = []
        for side, layer in (("F", "F.Cu"), ("B", "B.Cu")):
            tracks = [t for t in self.f["tracks"] if t["layer"] == layer]
            for x, y, ap, ref, p in self.mask[side]:
                for t in tracks:
                    if t["net"] == p["net"]:
                        continue
                    lo = min(t["a"][0], t["b"][0]) - 2, max(t["a"][0], t["b"][0]) + 2
                    if not lo[0] < x < lo[1] or not min(t["a"][1], t["b"][1]) - 2 < y < max(t["a"][1], t["b"][1]) + 2:
                        continue
                    gap = seg_to_opening(t["a"], t["b"], x, y, ap) - t["w"] / 2
                    close.append((round(gap, 3), "%s.%s" % (ref, p["number"]), t["net"]))
        bad = sorted(set(c for c in close if c[0] < jlc.MASK_TO_TRACE_MIN))
        self.assertEqual(bad, [], "other-net track within %.2f mm of a pad's mask opening" % jlc.MASK_TO_TRACE_MIN)
        NOTES.append("closest other-net track to a pad's mask opening: %.3f mm (%s, %s); JLCPCB minimum %.2f"
                     % (min(close) + (jlc.MASK_TO_TRACE_MIN,)))

    # --- pictures ----------------------------------------------------------------------------
    @classmethod
    def draw(cls):
        def colour(ar):
            if ar < AREA_RATIO_MIN:
                return "#d1342f"
            t = min(1.0, (ar - AREA_RATIO_MIN) / 0.6)
            return "#%02x%02x%02x" % (int(230 - 150 * t), int(170 + 40 * t), int(60 + 60 * t))

        def rect(x, y, ap, **kw):
            hx, hy = ap.half
            r = ap.params[0] if ap.kind == "RoundRect" else 0
            attrs = " ".join('%s="%s"' % (k.replace("_", "-"), v) for k, v in kw.items())
            return '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" rx="%.3f" %s/>' % (x - hx, y - hy, 2 * hx, 2 * hy, r, attrs)

        fps = cls.f["footprints"]
        out = common.scratch("paste")
        # closeups: one panel per part, 30 px per mm
        S, PAD, COLS = 30.0, 1.2, 4
        panels = []
        for ref in CLOSEUPS:
            if ref not in fps or not fps[ref].get("courtyard"):
                continue
            x0, y0, x1, y1 = fps[ref]["courtyard"]
            panels.append((ref, x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD))
        cell = max(max(b[3] - b[1], b[4] - b[2]) for b in panels) * S
        W = int(COLS * (cell + 20) + 20)
        Hh = int(math.ceil(len(panels) / COLS) * (cell + 50) + 70)
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica, Arial, sans-serif">' % (W, Hh),
               '<rect width="100%" height="100%" fill="#fafaf7"/>',
               '<text x="20" y="28" font-size="16" font-weight="bold">Front paste and mask, close up (stencil %.2f mm)</text>' % STENCIL_T,
               '<text x="20" y="48" font-size="11" fill="#555">gold: copper pad / dashed blue: mask opening / filled: stencil aperture, '
               'coloured by IPC area ratio (red under %.2f) / thin lines: tracks</text>' % AREA_RATIO_MIN]
        for i, (ref, bx0, by0, bx1, by1) in enumerate(panels):
            ox, oy = 20 + (i % COLS) * (cell + 20), 70 + (i // COLS) * (cell + 50)
            sc = cell / max(bx1 - bx0, by1 - by0)
            svg.append('<g transform="translate(%.1f %.1f)">' % (ox, oy))
            svg.append('<clipPath id="c%d"><rect width="%.1f" height="%.1f"/></clipPath>' % (i, cell, cell))
            svg.append('<rect width="%.1f" height="%.1f" fill="#1f4a2c"/>' % (cell, cell))
            svg.append('<g clip-path="url(#c%d)"><g transform="scale(%.4f) translate(%.4f %.4f)">' % (i, sc, -bx0, -by0))
            for t in cls.f["tracks"]:
                if t["layer"] == "F.Cu":
                    svg.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#b5873a" stroke-opacity="0.55" '
                               'stroke-width="%.3f" stroke-linecap="round"/>' % (t["a"][0], t["a"][1], t["b"][0], t["b"][1], t["w"]))
            for x, y, ap, r, p in cls.cu["F"]:
                svg.append(rect(x, y, ap, fill="#e0b04a"))
            for x, y, ap, r, p in cls.mask["F"]:
                svg.append(rect(x, y, ap, fill="none", stroke="#6fc3ff", stroke_width="0.03", stroke_dasharray="0.08 0.05"))
            for x, y, ap, r, p in cls.paste:
                ar = area_ratio(ap, STENCIL_T)
                svg.append(rect(x, y, ap, fill=colour(ar), fill_opacity="0.85", stroke="#222", stroke_width="0.01"))
                if r == ref:
                    svg.append('<text x="%.3f" y="%.3f" font-size="%.3f" text-anchor="middle" fill="#111">%.2f</text>'
                               % (x, y + 0.06, min(0.22, 1.4 * min(ap.half)), ar))
            svg.append('</g></g>')
            near = [area_ratio(ap, STENCIL_T) for x, y, ap, r, p in cls.paste if r == ref]
            label = "%s: lowest area ratio %.2f" % (ref, min(near)) if near else "%s: no paste" % ref
            svg.append('<text x="0" y="%.1f" font-size="12">%s</text></g>' % (cell + 16, label))
        svg.append('</svg>')
        with open(os.path.join(out, "closeups.svg"), "w") as f:
            f.write("\n".join(svg))

        # the whole front, apertures coloured by area ratio
        S2 = 16.0
        Wb, Hb = cls.f["board"]["w"], cls.f["board"]["h"]
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica, Arial, sans-serif">'
               % (Wb * S2 + 40, Hb * S2 + 90),
               '<rect width="100%" height="100%" fill="#fafaf7"/>',
               '<text x="20" y="26" font-size="15" font-weight="bold">Front stencil, by area ratio at %.2f mm</text>' % STENCIL_T]
        for k, (lo, lab) in enumerate([(0.5, "&lt; %.2f" % AREA_RATIO_MIN), (0.7, "0.70"), (0.95, "0.95"), (1.3, "1.3+")]):
            svg.append('<rect x="%d" y="38" width="14" height="10" fill="%s"/><text x="%d" y="47" font-size="10">%s</text>'
                       % (20 + 70 * k, colour(lo), 38 + 70 * k, lab))
        svg.append('<g transform="translate(20 60) scale(%.3f)">' % S2)
        svg.append('<rect width="%.2f" height="%.2f" rx="1.5" fill="#1f4a2c"/>' % (Wb, Hb))
        for x, y, ap, r, p in cls.cu["F"]:
            svg.append(rect(x, y, ap, fill="#e0b04a", fill_opacity="0.5"))
        for x, y, ap, r, p in cls.paste:
            svg.append(rect(x, y, ap, fill=colour(area_ratio(ap, STENCIL_T))))
        for ref, fp in fps.items():
            if fp["layer"] == "F.Cu" and any(r == ref for _, _, _, r, _ in cls.paste):
                svg.append('<text x="%.2f" y="%.2f" font-size="0.9" fill="#fff" fill-opacity="0.8">%s</text>'
                           % (fp["courtyard"][0] if fp.get("courtyard") else fp["pos"][0],
                              (fp["courtyard"][1] - 0.2) if fp.get("courtyard") else fp["pos"][1], ref))
        svg.append('</g></svg>')
        with open(os.path.join(out, "front-paste.svg"), "w") as f:
            f.write("\n".join(svg))

    def test_pictures_are_well_formed(self):
        """The two SVGs are drawn in tearDownClass; draw them now too and parse them as XML."""
        import xml.etree.ElementTree as ET
        self.draw()
        for name in ("closeups.svg", "front-paste.svg"):
            with self.subTest(picture=name):
                ET.parse(os.path.join(common.scratch("paste"), name))


if __name__ == "__main__":
    unittest.main()
