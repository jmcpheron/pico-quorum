"""Golden images: the board's pictures compared with approved copies, so an unintended change shows.

Two kinds of picture, each held to its copy in tests/golden/:
- fab layers: every Gerber layer and the drill file in the zip JLCPCB gets, drawn to pixels by
  tests/raster.py (not KiCad's plotter), 16 px per mm. These don't depend on the KiCad version.
- renders: kicad-cli's 3D view of the top and bottom. These do, so they are skipped when the
  KiCad that made the golden copies isn't the one running.

A change is any pixel that differs; neighbouring changed pixels are grouped, and each group is
reported in board millimetres with the parts under it. The test fails on any group, whatever its
size: a moved part, a re-route, a silk edit all count. That's the point: nothing changes without
someone looking. When the change is intended, approve it:

  CONSOLE_BLESS=1 tools/test.sh test_visual     # overwrite tests/golden/ with the current pictures

Pictures, in hardware/out/scratch/test/visual/: sheet.png (every current picture: F.Cu, B.Cu,
F.Mask, B.Mask, F.Paste, F.Silk, B.Silk, outline, drill, then the top and bottom renders), and for
each changed picture <name>-diff.png (approved | now | changed pixels red, each group boxed).
"""
import hashlib
import json
import os
import unittest
from collections import deque

import common
import gerber
import pngio
import raster

GOLDEN = os.path.join(common.ROOT, "tests", "golden")
ZIP = os.environ.get("CONSOLE_FAB_ZIP", os.path.join(common.OUT, "picoquorum-key-gerbers.zip"))
BLESS = os.environ.get("CONSOLE_BLESS") == "1"
SCALE = 16                       # px per mm for the fab layers
MARGIN = 1.0                     # mm round the board outline
RENDER_SIZE = (1000, 1060)
BLOCK = 12                       # px (0.75 mm on the fab layers): changes closer than this are one group
CHANNEL_TOL = 8                  # a render pixel differing by less than this in every channel is the same
LAYERS = [  # (name, Gerber FileFunction or "drill", colour)
    ("F_Cu", "Copper,L1,Top", (214, 160, 60)), ("B_Cu", "Copper,L2,Bot", (90, 160, 220)),
    ("F_Mask", "Soldermask,Top", (90, 200, 120)), ("B_Mask", "Soldermask,Bot", (90, 200, 160)),
    ("F_Paste", "Paste,Top", (200, 200, 200)), ("F_Silk", "Legend,Top", (245, 245, 245)),
    ("B_Silk", "Legend,Bot", (230, 230, 200)), ("Edge", "Profile,NP", (240, 220, 60)),
    ("Drill", "drill", (240, 90, 90)),
]
RENDERS = [("render_top", "top"), ("render_bottom", "bottom")]
NOTES = []


def kicad_version():
    r = common.run(["kicad-cli", "version"])
    return r.stdout.strip()


def changed_groups(a, b, tol=0):
    """Groups of differing pixels between two same-sized images: [(x0, y0, x1, y1, n pixels)]."""
    if (a.width, a.height) != (b.width, b.height):
        return [(0, 0, a.width, a.height, a.width * a.height)]
    bw, bh = (a.width + BLOCK - 1) // BLOCK, (a.height + BLOCK - 1) // BLOCK
    blocks = {}
    for y in range(a.height):
        ra, rb = a.rows[y], b.rows[y]
        if ra == rb:
            continue
        ca, cb = a.channels, b.channels
        for x in range(a.width):
            pa, pb = ra[x * ca:x * ca + 3], rb[x * cb:x * cb + 3]
            if pa != pb and (tol == 0 or max(abs(pa[i] - pb[i]) for i in range(3)) > tol):
                k = (x // BLOCK, y // BLOCK)
                e = blocks.get(k)
                if e is None:
                    blocks[k] = [x, y, x, y, 1]
                else:
                    e[0], e[1], e[2], e[3], e[4] = min(e[0], x), min(e[1], y), max(e[2], x), max(e[3], y), e[4] + 1
    groups, seen = [], set()
    for k in blocks:
        if k in seen:
            continue
        q, box = deque([k]), [10 ** 9, 10 ** 9, -1, -1, 0]
        seen.add(k)
        while q:
            c = q.popleft()
            e = blocks[c]
            box = [min(box[0], e[0]), min(box[1], e[1]), max(box[2], e[2]), max(box[3], e[3]), box[4] + e[4]]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (c[0] + dx, c[1] + dy)
                    if n in blocks and n not in seen:
                        seen.add(n)
                        q.append(n)
        groups.append(tuple(box))
    return sorted(groups, key=lambda g: -g[4])


class Visual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # the real board's pictures go to scratch/test/visual; another board (CONSOLE_PCB) gets its own
        tag = "" if common.PCB == os.path.join(common.PRJ, "picoquorum-key.kicad_pcb") else \
            "-" + hashlib.md5(common.PCB.encode()).hexdigest()[:8]
        cls.out = common.scratch("visual" + tag)
        cls.f = common.board_facts()
        cls.W, cls.H = cls.f["board"]["w"], cls.f["board"]["h"]
        cls.current = {}                         # name -> png path (current)
        cls.mm_of = {}                           # name -> function (px, py) -> board (x, y) in mm
        cls.side = {}
        meta_path = os.path.join(GOLDEN, "golden.json")
        cls.meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
        cls.kicad = kicad_version()

    @classmethod
    def tearDownClass(cls):
        cls.sheet()
        if BLESS:
            os.makedirs(GOLDEN, exist_ok=True)
            with open(common.PCB, "rb") as fh:
                board_sha = hashlib.sha256(fh.read()).hexdigest()[:16]
            cls.meta.update({"kicad": cls.kicad, "board_sha256": board_sha, "zip": os.path.relpath(ZIP, common.ROOT),
                             "pictures": sorted(cls.current)})
            with open(os.path.join(GOLDEN, "golden.json"), "w") as fh:
                json.dump(cls.meta, fh, indent=1)
        if NOTES:
            print("\nvisual notes (pictures in %s):\n  " % cls.out + "\n  ".join(NOTES))

    # --- making the pictures -----------------------------------------------------------------
    def fab_pictures(self):
        files = gerber.read_zip(ZIP)
        layers, drills = {}, []
        for name, text in files.items():
            if name.endswith(".drl"):
                drills.append(gerber.Drill(text))
            elif not name.endswith(".gbrjob"):
                g = gerber.Gerber(text)
                layers[g.attrs.get("FileFunction", name)] = g
        window = (-MARGIN, -MARGIN, self.W + MARGIN, self.H + MARGIN)
        made = {}
        for name, fn, colour in LAYERS:
            if fn == "drill":
                r = raster.draw_drill(drills, window, SCALE)
            else:
                r, skipped = raster.draw_gerber(layers[fn], window, SCALE)
                if skipped:
                    NOTES.append("%s: %d flashes with an aperture the rasteriser can't draw" % (name, skipped))
            path = os.path.join(self.out, name + ".png")
            pngio.write(path, r.to_image(colour))
            made[name] = path
            self.mm_of[name] = lambda px, py: (px / SCALE - MARGIN, py / SCALE - MARGIN)
            self.side[name] = "B" if name.startswith("B_") else "F"
        return made

    def render_pictures(self):
        made = {}
        for name, side in RENDERS:
            path = os.path.join(self.out, name + ".png")
            r = common.run(["kicad-cli", "pcb", "render", "--quality", "basic", "--background", "opaque",
                            "-w", str(RENDER_SIZE[0]), "-h", str(RENDER_SIZE[1]), "--side", side, "-o", path, common.PCB])
            if not os.path.exists(path):
                raise RuntimeError(r.stdout + r.stderr)
            img = pngio.read(path)
            bg = img.rgb(0, 0)
            xs, ys = [], []
            for y in range(0, img.height, 2):
                row = img.rows[y]
                for x in range(0, img.width, 2):
                    if tuple(row[x * img.channels:x * img.channels + 3]) != bg:
                        xs.append(x)
                        ys.append(y)
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            mirror = side == "bottom"

            def mm(px, py, x0=x0, x1=x1, y0=y0, y1=y1, mirror=mirror):
                bx = (px - x0) / (x1 - x0) * self.W
                return (self.W - bx if mirror else bx), (py - y0) / (y1 - y0) * self.H
            self.mm_of[name] = mm
            self.side[name] = "B" if mirror else "F"
            made[name] = path
        return made

    # --- comparing ---------------------------------------------------------------------------
    def compare(self, name, path, tol=0):
        self.current[name] = path
        gold = os.path.join(GOLDEN, name + ".png")
        if BLESS:
            os.makedirs(GOLDEN, exist_ok=True)
            with open(path, "rb") as src, open(gold, "wb") as dst:
                dst.write(src.read())
            return []
        if not os.path.exists(gold):
            self.fail("no approved copy of %s: run CONSOLE_BLESS=1 tools/test.sh test_visual" % name)
        a, b = pngio.read(gold), pngio.read(path)
        groups = changed_groups(a, b, tol)
        if groups:
            self.diff_sheet(name, gold, path, a, groups)
        return groups

    def describe(self, name, groups):
        mm = self.mm_of[name]
        side = self.side[name]
        out = []
        for x0, y0, x1, y1, n in groups[:12]:
            (ax, ay), (bx, by) = mm(x0, y0), mm(x1 + 1, y1 + 1)
            bx0, bx1, by0, by1 = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
            parts = sorted(r for r, fp in self.f["footprints"].items() if fp.get("courtyard")
                           and fp["layer"].startswith(side) and fp["courtyard"][0] < bx1 + 0.5
                           and fp["courtyard"][2] > bx0 - 0.5 and fp["courtyard"][1] < by1 + 0.5 and fp["courtyard"][3] > by0 - 0.5)
            out.append("  x %.1f-%.1f, y %.1f-%.1f mm, %d px%s" % (bx0, bx1, by0, by1, n,
                                                                   (": near " + ", ".join(parts[:6])) if parts else ""))
        if len(groups) > 12:
            out.append("  ... and %d more" % (len(groups) - 12))
        return "\n".join(out)

    def check(self, name, path, tol=0):
        groups = self.compare(name, path, tol)
        if groups:
            self.fail("%s changed in %d place(s) (see %s):\n%s\nIf intended: CONSOLE_BLESS=1 tools/test.sh test_visual"
                      % (name, len(groups), os.path.join(self.out, name + "-diff.png"), self.describe(name, groups)))

    def test_fab_layers_match_the_approved_copies(self):
        self.assertTrue(os.path.exists(ZIP), "no Gerber zip: run tools/export.sh " + common.REV)
        for name, path in self.fab_pictures().items():
            with self.subTest(layer=name):
                self.check(name, path)

    def test_renders_match_the_approved_copies(self):
        made = self.render_pictures()
        if not BLESS and self.meta.get("kicad") and self.meta["kicad"] != self.kicad:
            self.current.update(made)
            self.skipTest("renders approved with KiCad %s, running %s: re-approve after checking them"
                          % (self.meta["kicad"], self.kicad))
        for name, path in made.items():
            with self.subTest(render=name):
                self.check(name, path, CHANNEL_TOL)

    # --- pictures ----------------------------------------------------------------------------
    def diff_sheet(self, name, gold, path, a, groups):
        """<name>-diff.png: approved | now | changes (the current picture greyed, changed pixels red,
        each group boxed), scaled down to fit 540 px high; a changed pixel survives the scaling."""
        b = pngio.read(path)
        k = max(1, -(-a.height // 540))
        w, h = a.width // k, a.height // k
        gap = 12
        sheet = pngio.blank(3 * w + 4 * gap, h + 2 * gap, (250, 250, 247))
        for y in range(h):
            out = sheet.rows[gap + y]
            for x in range(w):
                sx, sy = x * k, y * k
                pa, pb = a.rgb(sx, sy), b.rgb(sx, sy)
                hit = any(a.rgb(sx + i, sy + j) != b.rgb(sx + i, sy + j)
                          for i in range(k) for j in range(k) if sx + i < a.width and sy + j < a.height)
                g = 150 + sum(pb) // 9
                for col, px in ((0, pa), (1, pb), (2, (255, 32, 32) if hit else (g, g, g))):
                    o = (gap + col * (w + gap) + x) * 3
                    out[o:o + 3] = bytes(px)
        x_off = gap + 2 * (w + gap)
        for x0, y0, x1, y1, n in groups:
            bx0, by0 = max(x0 // k - 3, 0), max(y0 // k - 3, 0)
            bx1, by1 = min(x1 // k + 3, w - 1), min(y1 // k + 3, h - 1)
            for x in range(bx0, bx1 + 1):
                for yy in (by0, by1):
                    sheet.rows[gap + yy][(x_off + x) * 3:(x_off + x) * 3 + 3] = b"\xc0\x00\x00"
            for y in range(by0, by1 + 1):
                for xx in (bx0, bx1):
                    sheet.rows[gap + y][(x_off + xx) * 3:(x_off + xx) * 3 + 3] = b"\xc0\x00\x00"
        pngio.write(os.path.join(self.out, name + "-diff.png"), sheet)

    @classmethod
    def sheet(cls):
        """sheet.png: every current picture, fab layers first (in LAYERS order), then the renders."""
        names = [n for n, _, _ in LAYERS if n in cls.current] + [n for n, _ in RENDERS if n in cls.current]
        if not names:
            return
        imgs = [pngio.read(cls.current[n]) for n in names]
        cols, cell_h, gap = 4, 300, 10
        thumbs = []
        for img in imgs:
            k = max(1, -(-img.height // cell_h))
            t = pngio.blank(img.width // k, img.height // k)
            for y in range(t.height):
                src, dst = img.rows[y * k], t.rows[y]
                for x in range(t.width):
                    i = x * k * img.channels
                    dst[x * 3:x * 3 + 3] = src[i:i + 3]
            thumbs.append(t)
        cw = max(t.width for t in thumbs)
        rows = -(-len(thumbs) // cols)
        sheet = pngio.blank(cols * (cw + gap) + gap, rows * (cell_h + gap) + gap, (250, 250, 247))
        for i, t in enumerate(thumbs):
            ox, oy = gap + (i % cols) * (cw + gap), gap + (i // cols) * (cell_h + gap)
            for y in range(t.height):
                sheet.rows[oy + y][ox * 3:(ox + t.width) * 3] = t.rows[y]
        pngio.write(os.path.join(cls.out, "sheet.png"), sheet)

if __name__ == "__main__":
    unittest.main()
