"""pico-sign's prism: the pictures for ASSEMBLY.md, drawn the way flat-pack instructions are. Each step's new
printed parts in amber, what's already done in white, the hardware in its own colours, black outlines,
arrows for where things go, and what the step needs along the bottom.

Run: uv run --python 3.11 --with cadquery --with matplotlib --with pillow \\
         python hardware/builds/pico-sign/case/assembly.py

Writes out/prism/assembly/*.png. The parts come from prism.py, so the pictures follow its numbers. The
drawing is its own: a z-buffer and outlines from where the part, the depth or the surface turns, numpy only.
"""
import math
import os
import sys

import numpy as np
import cadquery as cq
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prism as P

OUT = os.path.join(P.OUT, "assembly")

WHITE = (0.97, 0.97, 0.96)      # printed parts already in place
NEW = (0.99, 0.75, 0.36)        # this step's printed parts
BRASS = (0.90, 0.74, 0.40)
STEEL = (0.74, 0.75, 0.78)
DARK = (0.34, 0.34, 0.37)       # screws, nuts, switch bodies
BLACK = (0.20, 0.20, 0.22)
GLASS = (0.24, 0.26, 0.31)
BLUE = (0.45, 0.62, 0.86)
GREEN = (0.46, 0.74, 0.52)
RED = (0.86, 0.30, 0.26)
INK = (22, 22, 26)

N = np.array([0.0, -P.SF, P.CF])            # out of the plate's face
TH = math.radians(180 - P.A_F)              # the plate face down on the bench, as it prints
BENCH = np.array([[1, 0, 0], [0, math.cos(TH), -math.sin(TH)], [0, math.sin(TH), math.cos(TH)]])


# --- drawing ----------------------------------------------------------------------------------------------
_MESH = {}


def mesh(shape):
    k = id(shape)
    if k not in _MESH:
        vs, ts, n = [], [], 0
        for s in shape.vals():
            v, t = s.tessellate(0.08, 0.15)
            vs.append(np.array([p.toTuple() for p in v], float).reshape(-1, 3))
            ts.append(np.array(t, int).reshape(-1, 3) + n)
            n += len(v)
        _MESH[k] = (shape, np.concatenate(vs), np.concatenate(ts))
    return _MESH[k][1], _MESH[k][2]


def raster(X, Y, Z, T, wd, ht):
    """The nearest triangle at each pixel, and its depth."""
    zb = np.full(wd * ht, np.inf, np.float32)
    tb = np.full(wd * ht, -1, np.int64)
    ax, ay, az = X[T[:, 0]], Y[T[:, 0]], Z[T[:, 0]]
    bx, by, bz = X[T[:, 1]], Y[T[:, 1]], Z[T[:, 1]]
    cx, cy, cz = X[T[:, 2]], Y[T[:, 2]], Z[T[:, 2]]
    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    x0 = np.floor(np.minimum(np.minimum(ax, bx), cx)).clip(0, wd).astype(int)
    x1 = np.ceil(np.maximum(np.maximum(ax, bx), cx)).clip(0, wd).astype(int)
    y0 = np.floor(np.minimum(np.minimum(ay, by), cy)).clip(0, ht).astype(int)
    y1 = np.ceil(np.maximum(np.maximum(ay, by), cy)).clip(0, ht).astype(int)
    ok = (np.abs(area) > 1e-12) & (x1 > x0) & (y1 > y0)
    size = np.maximum(x1 - x0, y1 - y0)

    def frag(ids, kx, ky):
        g = lambda a: a[ids][:, None, None]
        gx = g(x0) + np.arange(kx)[None, None, :]
        gy = g(y0) + np.arange(ky)[None, :, None]
        px, py, A = gx + 0.5, gy + 0.5, g(area)
        wa = ((g(bx) - px) * (g(cy) - py) - (g(by) - py) * (g(cx) - px)) / A
        wb = ((g(cx) - px) * (g(ay) - py) - (g(cy) - py) * (g(ax) - px)) / A
        wc = 1 - wa - wb
        m = (wa >= -1e-6) & (wb >= -1e-6) & (wc >= -1e-6) & (gx < g(x1)) & (gy < g(y1))
        z = wa * g(az) + wb * g(bz) + wc * g(cz)
        pix = np.broadcast_to(gy * wd + gx, m.shape)
        return pix[m], z[m], np.broadcast_to(ids[:, None, None], m.shape)[m]

    def resolve(pix, z, t):
        if not len(pix):
            return
        o = np.lexsort((z, pix))
        pix, z, t = pix[o], z[o], t[o]
        first = np.r_[True, pix[1:] != pix[:-1]]
        pix, z, t = pix[first], z[first], t[first]
        w = z < zb[pix]
        zb[pix[w]], tb[pix[w]] = z[w], t[w]

    prev = 0
    for k in (1, 2, 4, 8, 16, 32, 64, 128):
        ids = np.nonzero(ok & (size > prev) & (size <= k))[0]
        prev, step = k, max(1, int(2e6 // (k * k)))
        for s in range(0, len(ids), step):
            resolve(*frag(ids[s:s + step], k, k))
    for i in np.nonzero(ok & (size > prev))[0]:
        resolve(*frag(np.array([i]), int(x1[i] - x0[i]), int(y1[i] - y0[i])))
    return zb, tb


def grow(m, r):
    for _ in range(r):
        g = m.copy()
        g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]
        m = g
    return m


class Shot:
    """Parts drawn from (az, el): the camera at that azimuth and elevation, looking at them. Items are
    (shape, colour, move): move a world vector. bench: the plate face down, as on the bench. fit: world
    points to frame instead of everything."""

    def __init__(self, items, az, el, size, bench=False, fit=None, pad=0.07, ss=2):
        a, e = math.radians(az), math.radians(el)
        fwd = -np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
        right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        self.M = np.array([right, up, fwd]) @ (BENCH if bench else np.eye(3))
        Vs, Ts, cols, parts, n = [], [], [], [], 0
        for i, (shape, color, mv) in enumerate(items):
            V, T = mesh(shape)
            Vs.append((V + mv) @ self.M.T); Ts.append(T + n); n += len(V)
            cols.append(np.repeat([color], len(T), 0)); parts.append(np.full(len(T), i))
        V, T = np.concatenate(Vs), np.concatenate(Ts)
        col, part = np.concatenate(cols), np.concatenate(parts)
        wd, ht = size[0] * ss, size[1] * ss
        pts = V[:, :2] if fit is None else (np.asarray(fit, float) @ self.M.T)[:, :2]
        lo, hi = pts.min(0), pts.max(0)
        self.s = min(wd * (1 - 2 * pad) / max(hi[0] - lo[0], 1e-6), ht * (1 - 2 * pad) / max(hi[1] - lo[1], 1e-6))
        self.c, self.ss, self.size = (lo + hi) / 2, ss, size
        X = (V[:, 0] - self.c[0]) * self.s + wd / 2
        Y = ht / 2 - (V[:, 1] - self.c[1]) * self.s
        zb, tb = raster(X, Y, V[:, 2], T, wd, ht)
        nrm = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None]
        light = np.array([-0.35, 0.55, -0.76]); light /= np.linalg.norm(light)
        shade = 0.70 + 0.30 * np.abs(nrm @ light)
        hit = tb >= 0
        img = np.ones((wd * ht, 3), np.float32)
        img[hit] = col[tb[hit]] * shade[tb[hit], None]
        pim = np.where(hit, part[tb.clip(0)], -1).reshape(ht, wd)
        zim = zb.reshape(ht, wd)
        nim = np.where(hit[:, None], nrm[tb.clip(0)], 0).astype(np.float32).reshape(ht, wd, 3)
        np.seterr(invalid="ignore")
        both_x = np.isfinite(zim[:, 1:]) & np.isfinite(zim[:, :-1])
        both_y = np.isfinite(zim[1:]) & np.isfinite(zim[:-1])
        zt = max(0.4, 5.0 / self.s)
        out = np.zeros((ht, wd), bool)
        out[:, 1:] |= (pim[:, 1:] != pim[:, :-1]) | (both_x & (np.abs(zim[:, 1:] - zim[:, :-1]) > zt))
        out[1:] |= (pim[1:] != pim[:-1]) | (both_y & (np.abs(zim[1:] - zim[:-1]) > zt))
        cos = math.cos(math.radians(32))
        crease = np.zeros((ht, wd), bool)
        crease[:, 1:] |= both_x & (np.abs((nim[:, 1:] * nim[:, :-1]).sum(-1)) < cos)
        crease[1:] |= both_y & (np.abs((nim[1:] * nim[:-1]).sum(-1)) < cos)
        img = img.reshape(ht, wd, 3)
        img[grow(crease, 1)] = np.array(INK) / 255 * 1.6
        img[grow(out, 2)] = np.array(INK) / 255
        img = img.reshape(size[1], ss, size[0], ss, 3).mean((1, 3))
        self.img = Image.fromarray((img.clip(0, 1) * 255).astype(np.uint8))
        self.d = ImageDraw.Draw(self.img)

    def at(self, p):
        q = self.M @ np.asarray(p, float)
        wd, ht = self.size[0] * self.ss, self.size[1] * self.ss
        return ((q[0] - self.c[0]) * self.s + wd / 2) / self.ss, (ht / 2 - (q[1] - self.c[1]) * self.s) / self.ss

    def arrow(self, a, b, w=5, color=INK):
        """An arrow from world point a to b."""
        arrow(self.d, self.at(a), self.at(b), w, color)

    def label(self, p, text, dx=0, dy=0, size=26):
        """A boxed label near world point p, with a line to it when moved off it."""
        x, y = self.at(p)
        if dx or dy:
            self.d.line([(x, y), (x + dx, y + dy)], fill=INK, width=2)
            self.d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=INK)
        box(self.d, (x + dx, y + dy), text, size)


def font(n):
    return ImageFont.load_default(size=n)


def txt(t):
    return t.replace("\u00d7", "x")     # the font has no multiplication sign


def arrow(d, a, b, w=5, color=INK):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    h = 6 * w
    tip = [(b[0] - h * math.cos(ang + s * 0.42), b[1] - h * math.sin(ang + s * 0.42)) for s in (-1, 1)]
    end = (b[0] - 0.8 * h * math.cos(ang), b[1] - 0.8 * h * math.sin(ang))
    d.line([a, end], fill=color, width=w)
    d.polygon([b] + tip, fill=color)


def box(d, xy, text, size=26):
    f = font(size)
    l, t, r, b = d.multiline_textbbox((0, 0), text, font=f, spacing=6)
    x, y = xy[0] - (r - l) / 2, xy[1] - (b - t) / 2
    d.rounded_rectangle([x - 12, y - 9, x + (r - l) + 12, y + (b - t) + 11], 8, fill=(255, 255, 255), outline=INK, width=2)
    d.multiline_text((x - l, y - t), text, font=f, fill=INK, spacing=6)


def page(name, n, title, panels, need=(), note=None):
    """A step: its number and title over its pictures side by side, what it needs under them."""
    rows = panels if isinstance(panels[0], list) else [panels]
    w = max(sum(p.width for p in r) for r in rows)
    head, foot = 120, (250 if need else 0) + (70 if note else 0)
    h = sum(max(p.height for p in r) for r in rows)
    im = Image.new("RGB", (w, head + h + foot), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.text((40, 18), str(n) if n is not None else "", font=font(80), fill=INK)
    d.text((160 if n is not None else 40, 44), title, font=font(40), fill=INK)
    y = head
    for r in rows:
        x, rh = 0, max(p.height for p in r)
        for i, p in enumerate(r):
            im.paste(p, (x, y))
            if i:
                d.line([(x, y + 20), (x, y + rh - 20)], fill=(200, 200, 205), width=2)
            x += p.width
        y += rh
    if note:
        d.text((40, y + 16), note, font=font(30), fill=INK)
        y += 70
    if need:
        d.line([(30, y + 6), (w - 30, y + 6)], fill=(200, 200, 205), width=2)
        x = 40
        for icon, count, text in need:
            im.paste(icon, (x, y + 22))
            d.text((x + icon.width + 8, y + 70), txt(count), font=font(46), fill=INK)
            d.text((x + 4, y + 22 + icon.height), txt(text), font=font(22), fill=INK)
            x += icon.width + 150
    name = "%02d-%s" % (n or 0, name)
    im.save(os.path.join(OUT, name + ".png"), optimize=True)
    print("wrote", os.path.join("hardware/builds/pico-sign/case/out/prism/assembly", name + ".png"))


# --- the hardware, each made along +z at the origin ---------------------------------------------------------
def wp(*shapes):
    w = cq.Workplane()
    for s in shapes:
        w = w.add(s.vals() if isinstance(s, cq.Workplane) else s)
    return w


def at(shape, u, v, w, flip=False):
    """A part made along +z put at (u, v) on the plate, its +z out of the plate's face (flip: into it), at w."""
    n = (0, P.SF, -P.CF) if flip else (0, -P.SF, P.CF)
    pl = cq.Plane(origin=P.world(u, v, w), xDir=(1, 0, 0), normal=n)
    return wp(*[s.moved(cq.Location(pl)) for s in shape.vals()])


def insert(od, length, hole):
    s = cq.Workplane("XY").circle(od / 2).circle(hole / 2).extrude(length)
    for z in (length * 0.3, length * 0.7):
        s = s.cut(cq.Workplane("XY").workplane(offset=z - 0.4).circle(od / 2 + 1).circle(od / 2 - 0.25).extrude(0.8))
    return s


def socket_screw(d, length, hd, hh, key):
    """Its head's underside at z = 0, the head up, the thread down."""
    s = cq.Workplane("XY").circle(d / 2).extrude(-length).union(cq.Workplane("XY").circle(hd / 2).extrude(hh))
    return s.cut(cq.Workplane("XY").workplane(offset=hh * 0.4).polygon(6, key / math.cos(math.pi / 6)).extrude(hh))


def countersunk(d, length, hd):
    """Its head's top at z = 0, flush; the thread down."""
    head = cq.Workplane("XY").circle(hd / 2).workplane(offset=-(hd - d) / 2).circle(d / 2).loft()
    s = head.union(cq.Workplane("XY").circle(d / 2).extrude(-length))
    return s.cut(cq.Workplane("XY").workplane(offset=-1.5).polygon(6, 2.0 / math.cos(math.pi / 6)).extrude(2))


def iron(pilot):
    """A soldering iron with an insert tip: the shoulder at z = 0, the pilot down into the insert."""
    s = cq.Workplane("XY").circle(pilot / 2).extrude(-4)
    s = s.union(cq.Workplane("XY").circle(3.6).workplane(offset=4).circle(2.5).loft())
    s = s.union(cq.Workplane("XY").workplane(offset=4).circle(2.5).extrude(36))
    return s, cq.Workplane("XY").workplane(offset=40).circle(6.5).extrude(40)


M3I = insert(5.0, 6.0, 3.0)
M3S = socket_screw(3.0, 8.0, 5.5, 3.0, 2.5)
M2S = socket_screw(2.0, P.PICO_SCREW, 3.8, 2.0, 1.5)
CSK = countersunk(3.0, 8.0, 6.0)
WASHER = cq.Workplane("XY").circle(3.5).circle(1.6).extrude(0.5)
FOOT = cq.Workplane("XY").slot2D(P.FOOT[1], P.FOOT[0], 90).extrude(2.5).edges(">Z").fillet(1.0)
IRON3 = iron(2.6)


def pressed(ins, length, u, v, entry, flip, lift, tool=None):
    """An insert lift mm out of its hole, which opens at w = entry and runs back (flip: forward, as on a boss);
    with the iron on it if a tool is given."""
    base = entry + length - lift if flip else entry - length + lift
    top = base - length if flip else base + length
    out = [(at(ins, u, v, base, flip), BRASS)]
    if tool:
        out += [(at(tool[0], u, v, top, flip), STEEL), (at(tool[1], u, v, top, flip), RED)]
    return out


# --- the parts, placed where they go ---------------------------------------------------------------------------
def build():
    g = {}
    g["body"], g["plate"] = P.body_and_plate()
    g["carrier"], _ = P.carrier_and_spacers()
    g["lock"] = P.plug_lock()
    si = {n: sh for sh, _, n in P.stand_ins()}
    su, sv = P.SCREEN_UV
    g["spacers"] = [P.pw(P.W_BOARD - P.SCREEN_PCB_T).center(*c).circle(P.SPACER_D / 2).circle(P.PIN_HOLE / 2)
                    .extrude(-P.SPACER) for c in P.screen_holes()]
    # the screen: glass, board, its 8-pin header on the back at the left
    hdr = cq.Workplane("XY").box(2.5, 20.3, 2.5, centered=(True, True, False))
    pins = wp(*[cq.Workplane("XY").box(0.64, 0.64, 6, centered=(True, True, False)).translate((0, (i - 3.5) * 2.54, 2.5))
                for i in range(8)])
    hu = P.HEADER_U
    w_hdr = P.W_BOARD - P.SCREEN_PCB_T
    g["screen"] = [(si["screen glass"], GLASS), (si["screen board"], BLUE),
                   (at(hdr, hu, sv, w_hdr, True), BLACK), (at(pins, hu, sv, w_hdr, True), BRASS)]
    # the sign switch and the knob, each with its nut on the front
    cu, s0 = P.CTRL_U, -P.PLATE - P.SIGN_RING_T
    g["switch"] = [(P.pw(s0).center(cu, P.SIGN_V).rect(P.SIGN_BODY, P.SIGN_BODY).extrude(-P.SIGN_DEPTH), DARK),
                   (P.pw(s0).center(cu, P.SIGN_V).circle(6).extrude(11.5 - s0), STEEL),
                   (P.pw(11.5).center(cu, P.SIGN_V).circle(6.3).extrude(1.5), STEEL)]
    g["switch nut"] = [(P.pw(0).center(cu, P.SIGN_V).polygon(6, 16).circle(6.1).extrude(2.5), STEEL)]
    g["ec11"] = [(P.pw(-P.PLATE).center(cu, P.KNOB_V).rect(12, 12).extrude(-6.5), DARK),
                 (P.pw(-P.PLATE).center(cu, P.KNOB_V).circle(3.5).extrude(P.PLATE + 5), STEEL),
                 (P.pw(5).center(cu, P.KNOB_V).circle(3).extrude(10), STEEL)]
    g["ec11 nut"] = [(P.pw(0).center(cu, P.KNOB_V).polygon(6, 11).circle(3.6).extrude(2), STEEL)]
    g["knob"] = [(P.pw(2.5).center(cu, P.KNOB_V).circle(9).extrude(14).faces(">Z").edges().fillet(1.5), BLACK),
                 (P.pw(16.5).center(cu, P.KNOB_V + 4).rect(0.8, 6).extrude(0.4), WHITE)]
    # the Pico, made with its USB end at x = 0, its parts on -z, its pins on +z; put on its posts
    pb = cq.Workplane("XY").box(51, 21, 1, centered=(False, True, False))
    for x, y in P.PICO_HOLES:
        pb = pb.cut(cq.Workplane("XY").center(x, y).circle(1.05).extrude(3, both=True))
    usb = cq.Workplane("XY").box(5.6, 8, 2.6, centered=False).translate((-P.USB_OVERHANG, -4, -2.6))
    chip = cq.Workplane("XY").box(7, 7, 0.9, centered=(True, True, False)).translate((26, 0, -0.9))
    strips = wp(*[cq.Workplane("XY").box(50.8, 2.5, 2.5, centered=(True, True, False)).translate((25.5, y, 1)) for y in (-8.89, 8.89)])
    ppins = wp(*[cq.Workplane("XY").box(0.64, 0.64, 6, centered=(True, True, False)).translate((25.5 + (i - 9.5) * 2.54, y, 3.5))
                 for i in range(20) for y in (-8.89, 8.89)])
    pa = (P.PICO_U0, P.PICO_V, P.W_PICO, True)
    g["pico"] = [(at(pb, *pa), GREEN), (at(usb, *pa), STEEL), (at(chip, *pa), BLACK), (at(strips, *pa), BLACK),
                 (at(ppins, *pa), BRASS)]
    # its micro-USB cable, the socket toward the carrier, out through the left wall's slot
    aw, u_end = P.W_PICO + 1.5, P.PICO_U0 - P.USB_OVERHANG
    cy, cz = P.world(0, P.PICO_V, aw)[1:]
    g["usb cable"] = [(P.pw(aw + 4).center(u_end - 10, P.PICO_V).rect(20, 11).extrude(-8), BLACK),
                      (P.pw(aw + 0.9).center(u_end + 2.5, P.PICO_V).rect(5, 6.8).extrude(-1.8), STEEL),
                      (cq.Workplane("YZ").circle(1.75).extrude(u_end - 20 + 45).translate((-45, cy, cz)), BLACK)]
    # the key's plug and its cable, and the key in its cartridge
    g["plug"] = [(si["plug overmold"], BLACK), (si["plug shell"], STEEL),
                 (cq.Workplane("XY").circle(2).extrude(-30).translate((P.KEY_X, P.KEY_Y, P.H - P.PLUG_L)), BLACK)]
    g["key"] = [(si["cartridge top"], NEW), (si["cartridge bottom"], (0.86, 0.60, 0.25)), (si["ATECC608"], BLACK)]
    # the hardware in place
    g["body inserts"] = [it for u, v in P.SCREWS for it in pressed(M3I, 6, u, v, -P.PLATE, False, 0)]
    g["boss inserts"] = [it for c in P.carrier_screws() for it in pressed(M3I, 6, *c, P.W_CARRIER, True, 0)]
    wc = P.W_CARRIER - P.CARRIER_T
    g["carrier screws"] = [it for c in P.carrier_screws() for it in
                           ((at(WASHER, *c, wc, True), STEEL), (at(M3S, *c, wc - 0.5, True), DARK))]
    g["pico screws"] = [(at(M2S, P.PICO_U0 + dx, P.PICO_V + dy, P.W_PICO - 1, True), DARK) for dx, dy in P.PICO_SCREWS]
    g["plate screws"] = [(at(CSK, u, v, 0), DARK) for u, v in P.SCREWS]
    fl = P.FOOT[1] + 2 * P.FOOT_CLEAR
    g["feet"] = [(FOOT.translate((x, y, -1.5)), BLACK) for x in (P.FOOT_X, P.W - P.FOOT_X)
                 for y in (P.FOOT_END + fl / 2, P.P3[0] - P.FOOT_END - fl / 2)]
    return g


def items(parts, move=(0, 0, 0), back=0.0, color=None):
    """(shape, colour) pairs as drawing items: moved by move, and back off the plate's face by back."""
    mv = np.array(move, float) - N * back
    return [(s, color or c, mv) for s, c in parts]


def ctr(shape):
    return np.array(shape.val().Center().toTuple())


def icon(parts, az=-55, el=30, size=170):
    return Shot(items(parts), az, el, (size, size), pad=0.14).img


# --- the steps ------------------------------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):           # a step taken out leaves no picture behind
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    g = build()
    body, plate, carrier, lock = g["body"], g["plate"], g["carrier"], g["lock"]
    NZ = np.array([0, 0, 1.0])
    ic = dict(m3i=icon([(M3I, BRASS)]), m3s=icon([(M3S, DARK)], el=15),
              m2s=icon([(M2S, DARK)], el=15), csk=icon([(CSK, DARK)], el=15), washer=icon([(WASHER, STEEL)], el=45),
              foot=icon([(FOOT, BLACK)], el=40), iron=icon([(IRON3[0], STEEL), (IRON3[1], RED)], el=10))
    done_plate = [(plate, WHITE)] + g["boss inserts"]
    n2 = len(P.PICO_SCREWS)

    # 0. the parts
    tiles = [("1 body: prism_body.stl", [(body, NEW)], -60, 28), ("1 plate: prism_plate.stl", [(plate, NEW)], -75, 14),
             ("1 carrier: prism_carrier.stl", [(carrier, NEW)], 115, 20),
             ("4 spacers, 7 x 4 mm:\nprism_spacers.stl", [(g["spacers"][0], NEW)], -55, 35),
             ("1 plug lock, 12 mm:\nprism_plug_lock.stl", [(lock, NEW)], -60, 25)]
    shots = []
    for name, parts, az, el in tiles:
        s = Shot(items(parts), az, el, (825, 520) if len(shots) < 2 else (550, 440), pad=0.13)
        s.d.multiline_text((24, 16), name, font=font(28), fill=INK, spacing=6)
        shots.append(s.img)
    page("printed-parts", None, "The printed parts", [shots[:2], shots[2:]])
    hw = [(ic["m3i"], "8×", "M3 insert, M3*6*5"),
          (ic["csk"], "4×", "M3 × 8 countersunk"), (ic["m3s"], "4×", "M3 × 8 socket head"),
          (ic["washer"], "4×", "M3 washer"), (ic["m2s"], "%d×" % n2, "M2 × 8 socket head"), (ic["foot"], "4×", "rubber strip")]
    blank = Image.new("RGB", (1650, 10), (255, 255, 255))      # just the strip of hardware
    page("hardware", None, "The hardware", [blank], need=hw)

    # the exploded view: from the right, so the stack behind the plate spreads out along its normal
    G = 240.0
    ex = items([(body, WHITE)] + g["body inserts"]) + items(g["feet"], move=(0, 0, -22))
    ex += items(g["plug"]) + items([(lock, WHITE)]) + items(g["key"], move=(0, 0, 45))
    ex += items(done_plate + g["switch"] + g["ec11"], move=N * G)
    ex += items(g["switch nut"] + g["ec11 nut"], move=N * (G + 14)) + items(g["knob"], move=N * (G + 30))
    ex += items(g["plate screws"], move=N * (G + 22))
    B = dict(screen=35, spacers=62, carrier=85, screws=108, pico=130, pico_screws=152)
    ex += items(g["screen"], move=N * G, back=B["screen"]) + items([(x, NEW) for x in g["spacers"]], move=N * G, back=B["spacers"])
    ex += items([(carrier, NEW)], move=N * G, back=B["carrier"])
    ex += items(g["carrier screws"], move=N * G, back=B["screws"])
    ex += items(g["pico"], move=N * G, back=B["pico"]) + items(g["pico screws"], move=N * G, back=B["pico_screws"])
    s = Shot(ex, -24, 22, (1650, 1150), pad=0.04)
    wl = lambda u, v, w, back: np.array(P.world(u, v, w)) + N * (G - back)
    for p, t, dx, dy in [(ctr(body) + (40, 20, 30), "body", 0, -90), (wl(20, 80, 0, 0), "plate", -40, -90),
                         (wl(P.SCREEN_UV[0] + 30, P.SCREEN_UV[1] + 24, P.W_BOARD - P.SCREEN_PCB_T, B["screen"]), "screen", 0, -130),
                         (wl(*P.screen_holes()[3], P.W_BOARD - P.SCREEN_PCB_T - P.SPACER, B["spacers"]), "spacers", 30, -170),
                         (wl(P.SCREEN_UV[0] + 30, P.SCREEN_UV[1] - 24, P.W_CARRIER - P.CARRIER_T, B["carrier"]), "carrier", -30, 130),
                         (wl(*P.carrier_screws()[3], P.W_CARRIER - P.CARRIER_T - 3, B["screws"]), "M3 screws", 40, -110),
                         (wl(P.PICO_U0 + 40, P.PICO_V, P.W_PICO - 1, B["pico"]), "Pico 2 W", 40, 150),
                         (ctr(g["key"][0][0]) + (0, 0, 45), "key", 110, 0), (ctr(g["feet"][3][0]) + (0, 0, -22), "feet", 0, 70)]:
        s.label(p, t, dx, dy)
    page("exploded", None, "Everything, pulled apart", [s.img])

    # 1. the body's inserts: all four, then one close, from inside the body, and as it ends, flush
    ov = Shot(items([(body, WHITE)]) + items([it for u, v in P.SCREWS for it in pressed(M3I, 6, u, v, -P.PLATE, False, 22)]),
              -28, 30, (900, 900), pad=0.06)
    for u, v in P.SCREWS:
        ov.arrow(np.array(P.world(u, v, -P.PLATE + 20)), np.array(P.world(u, v, -P.PLATE + 1)))
    u, v = P.SCREWS[0]
    blk = body.intersect(cq.Workplane("XY").box(34, 34, 34).translate(P.world(u, v, -P.PLATE - 6)))
    fit = [np.array(P.world(u + du, v + dv, w)) for du in (-12, 14) for dv in (-12, 12) for w in (-16, 26)]
    a = Shot(items([(blk, WHITE)] + pressed(M3I, 6, u, v, -P.PLATE, False, 5, IRON3)), -18, 28, (750, 900), fit=fit)
    a.arrow(np.array(P.world(u, v + 11, 22)), np.array(P.world(u, v + 11, 6)))
    a.label(np.array(P.world(u, v, 16)), "hot iron:\npress straight,\nno twisting", 170, -120, 24)
    b = Shot(items([(blk, WHITE)] + g["body inserts"][0:1]), -18, 28, (600, 900), fit=fit)
    b.label(np.array(P.world(u, v, -P.PLATE)), "flush with\nthe block's face", 100, -170, 24)
    page("body-inserts", 1, "The body: an insert in each corner block", [ov.img, a.img, b.img],
         need=[(ic["m3i"], "4×", "M3 insert"), (ic["iron"], "", "soldering iron, insert tip")])

    # 2. the feet
    s = Shot(items([(body, WHITE)] + g["body inserts"]) + items(g["feet"], move=(0, 0, -25)), -60, -42, (1650, 950))
    for sh, _ in g["feet"]:
        c = ctr(sh)
        s.arrow(c + (0, 0, -21), c + (0, 0, -4))
    page("feet", 2, "The body: the rubber strips into their pockets", [s.img], need=[(ic["foot"], "4×", "rubber strip, 6 × 35")],
         note="Peel each strip and press it into its pocket, round ends to the round ends.")

    # 3. the key's plug and its lock
    near = cq.Workplane("XY").box(40, 40, 44).translate((P.KEY_X, P.KEY_Y - 8, P.H - 18))
    hold = body.intersect(near)
    fit = [np.array((P.KEY_X + dx, P.KEY_Y + dy, P.H + dz)) for dx in (-16, 16) for dy in (-24, 4) for dz in (-42, 4)]
    low, out_ = np.array((0, 0, -P.LIFT)), np.array((0, -16, 0))
    top = np.array((P.KEY_X, P.KEY_Y, P.H - P.PLUG_L / 2))
    panels = []
    for i, (plug_mv, lock_mv, arr, text) in enumerate([
            (low + out_, None, (top + low + out_ + (0, -4, 0), top + low + (0, -6, 0)), "1  in from the front, low,\n   its cable down the slot"),
            (low, None, (top + low + (0, -8, -2), top + (0, -8, -2)), "2  push it up, the shell\n   through the top, flush"),
            (np.zeros(3), out_, (top + (0, -24, -P.PLUG_L / 2 - 4), top + (0, -10, -P.PLUG_L / 2 - 4)),
             "3  slide the lock in under it\n   until it clicks")]):
        its = items([(hold, WHITE)]) + items(g["plug"], move=plug_mv)
        if lock_mv is not None:
            its += items([(lock, NEW)], move=lock_mv)
        s = Shot(its, -62, -12, (550, 820), fit=fit)
        s.arrow(*arr)
        s.d.multiline_text((24, 18), text, font=font(26), fill=INK, spacing=6)
        panels.append(s.img)
    page("key-plug", 3, "The body: the key's USB-C plug, from inside", panels,
         need=[(icon(g["plug"][:2], el=20), "1×", "USB-C plug on its cable"), (icon([(lock, NEW)]), "1×", "the plug lock")])

    # 4. the plate's inserts, face down
    cs = P.carrier_screws()
    ov = Shot(items([(plate, WHITE)]) + items([it for c in cs for it in pressed(M3I, 6, *c, P.W_CARRIER, True, 20)]),
              -72, 48, (900, 900), bench=True, pad=0.05)
    for c in cs:
        ov.arrow(np.array(P.world(*c, P.W_CARRIER - 18)), np.array(P.world(*c, P.W_CARRIER - 2)))
    ov.label(np.array(P.world(P.SCREEN_UV[0], P.SCREEN_UV[1], 0)), "face down on a towel,\nthe window on the left", 0, 0, 24)
    c = cs[3]
    fit = [np.array(P.world(c[0] + du, c[1] + dv, w)) for du in (-12, 12) for dv in (-12, 12) for w in (0, P.W_CARRIER - 30)]
    near = cq.Workplane("XY").box(30, 30, 30).translate(P.world(*c, P.W_CARRIER + 4))
    a = Shot(items([(plate.intersect(near), WHITE)] + pressed(M3I, 6, *c, P.W_CARRIER, True, 5, IRON3)), -55, 28,
             (750, 900), bench=True, fit=fit)
    a.arrow(np.array(P.world(c[0] + 9, c[1], P.W_CARRIER - 22)), np.array(P.world(c[0] + 9, c[1], P.W_CARRIER - 10)))
    a.label(np.array(P.world(*c, P.W_CARRIER - 18)), "straight down,\nstop flush", -170, -60, 24)
    page("plate-inserts", 4, "The plate: an insert in each of the carrier's bosses", [ov.img, a.img],
         need=[(ic["m3i"], "4×", "M3 insert"), (ic["iron"], "", "soldering iron")],
         note="Try one first: if it goes in loose or won't go, the hole (M3_INSERT in prism.py) needs changing.")

    # 5. the switch and the knob
    fit = [np.array(P.world(P.CTRL_U + du, v, w)) for du in (-28, 28) for v in (12, 82) for w in (0, -P.PLATE - 30 - P.SIGN_DEPTH)]
    a = Shot(items(done_plate) + items(g["switch"] + g["ec11"], back=30), -40, 30, (820, 900), bench=True, fit=fit)
    for v in (P.SIGN_V, P.KNOB_V):
        a.arrow(np.array(P.world(P.CTRL_U + 15, v, -30)), np.array(P.world(P.CTRL_U + 15, v, -8)))
    a.label(np.array(P.world(P.CTRL_U, P.SIGN_V, -P.PLATE - 30 - P.SIGN_DEPTH)), "sign switch", -150, -30, 24)
    a.label(np.array(P.world(P.CTRL_U, P.KNOB_V, -P.PLATE - 36)), "knob (EC11)", 150, 60, 24)
    b = Shot(items(done_plate + g["switch"] + g["ec11"]) + items(g["switch nut"] + g["ec11 nut"], move=N * 18),
             -100, 12, (830, 900), fit=[np.array(P.world(P.CTRL_U + du, v, w)) for du in (-30, 30) for v in (10, 80) for w in (-30, 25)])
    for v in (P.SIGN_V, P.KNOB_V):
        b.arrow(np.array(P.world(P.CTRL_U, v, 26)), np.array(P.world(P.CTRL_U, v, 5)))
    b.label(np.array(P.world(P.CTRL_U, P.SIGN_V, 22)), "nuts on the front:\nsnug, not tight", -200, -60, 24)
    page("switch-knob", 5, "The plate: the sign switch and the knob, from behind", [a.img, b.img],
         need=[(icon(g["switch"] + g["switch nut"]), "1×", "12 mm momentary switch"),
               (icon(g["ec11"] + g["ec11 nut"]), "1×", "EC11 knob, its nut")],
         note="Solder their wires before the plate goes into the body (step 11).")

    # 6. the screen
    done6 = done_plate + g["switch"] + g["ec11"] + g["switch nut"] + g["ec11 nut"]
    s = Shot(items(done6) + items(g["screen"], back=30), -72, 46, (1650, 950), bench=True, pad=0.09)
    for hc in P.screen_holes():
        s.arrow(np.array(P.world(*hc, P.W_BOARD - 30)), np.array(P.world(*hc, P.W_BOARD - 6)))
    s.label(np.array(P.world(P.HEADER_U, P.SCREEN_UV[1], P.W_BOARD - 38)), ("header on the RIGHT,\naway from the Pico's USB" if P.HEADER_SIDE > 0 else "header on the LEFT\n(the firmware's way up)"),
            150 * P.HEADER_SIDE, -60, 26)
    s.label(np.array(P.world(P.SCREEN_UV[0], P.SCREEN_UV[1] - 20, P.W_BOARD - 32)), "glass down,\ninto the window", 260, 140, 26)
    page("screen", 6, "The plate: the screen onto its four pins", [s.img], need=[(icon(g["screen"]), "1×", '2.8" screen')],
         note="Peel the screen's film first. It drops on: the pins find its holes, and the board rests on the seats.")

    # 7. the spacers
    done7 = done6 + g["screen"]
    sp = [(x, NEW) for x in g["spacers"]]
    s = Shot(items(done7) + items(sp, back=22), -72, 46, (1650, 950), bench=True, pad=0.05)
    for hc in P.screen_holes():
        s.arrow(np.array(P.world(*hc, P.W_BOARD - P.SCREEN_PCB_T - 22)), np.array(P.world(*hc, P.W_BOARD - P.SCREEN_PCB_T - 6)))
    page("spacers", 7, "The plate: a spacer on each pin", [s.img], need=[(icon([sp[0]]), "4×", "spacer (printed)")])

    # 8. the carrier
    done8 = done7 + [(x, WHITE) for x in g["spacers"]]
    s = Shot(items(done8) + items([(carrier, NEW)], back=26) + items(g["carrier screws"], back=50),
             -72, 46, (1650, 1000), bench=True, pad=0.05)
    for c in P.carrier_screws():
        s.arrow(np.array(P.world(*c, P.W_CARRIER - 48)), np.array(P.world(*c, P.W_CARRIER - 32)))
        s.arrow(np.array(P.world(*c, P.W_CARRIER - 22)), np.array(P.world(*c, P.W_CARRIER - 6)))
    s.label(np.array(P.world(P.HEADER_U - 2.5 * P.HEADER_SIDE, P.SCREEN_UV[1], P.W_CARRIER - 30)),
            "the notch goes round\nthe screen's header", 120 * P.HEADER_SIDE, -170, 24)
    page("carrier", 8, "The plate: the carrier over the pins, four screws into the bosses", [s.img],
         need=[(icon([(carrier, NEW)], az=115, el=20), "1×", "the carrier"), (ic["m3s"], "4×", "M3 × 8 socket head"),
               (ic["washer"], "4×", "M3 washer")],
         note="The pins come up through the carrier. Tighten the screws evenly, a little at a time; they hold the screen down.")

    # 9. the Pico
    done9 = done8 + [(carrier, WHITE)] + g["carrier screws"]
    s = Shot(items(done9) + items(g["pico"], back=24) + items(g["pico screws"], back=44), -72, 46, (1650, 1000),
             bench=True, pad=0.09)
    for dx, dy in P.PICO_SCREWS:
        c = (P.PICO_U0 + dx, P.PICO_V + dy)
        s.arrow(np.array(P.world(*c, P.W_PICO - 42)), np.array(P.world(*c, P.W_PICO - 30)))
    for du in (-14, 14):
        s.arrow(np.array(P.world(P.PICO_U0 + 25.5 + du, P.PICO_V - 14, P.W_PICO - 20)),
                np.array(P.world(P.PICO_U0 + 25.5 + du, P.PICO_V - 14, P.W_PICO - 4)))
    s.label(np.array(P.world(P.PICO_U0 - 2, P.PICO_V, P.W_PICO - 24)), "USB to the LEFT edge", -60, 120, 26)
    s.label(np.array(P.world(P.PICO_U0 + 2, P.PICO_V, P.W_PICO - 2)), "no screws at the USB end:\nits plug needs the room",
            -40, 250, 24)
    s.label(np.array(P.world(P.PICO_U0 + 30, P.PICO_V + 9, P.W_PICO - 32)), "pins up, its parts\ndown to the carrier", 220, -120, 26)
    page("pico", 9, "The plate: the Pico on its posts", [s.img],
         need=[(icon(g["pico"]), "1×", "Pico 2 W, headers on"), (ic["m2s"], "%d×" % n2, "M2 × 8 socket head")])

    # 10. the wires
    done10 = done9 + g["pico"] + g["pico screws"]
    s = Shot(items(done10), -60, 40, (1650, 1000), bench=True, pad=0.06)
    su, sv = P.SCREEN_UV
    for p, t, dx, dy in [((P.HEADER_U, sv, P.W_BOARD - 9), "screen header: 8 wires\nto pins 11-17 and 36", 60, 230),
                         ((P.CTRL_U, P.SIGN_V, -P.PLATE - 2 - P.SIGN_DEPTH), "sign switch: pins 20, 18", 170, -150),
                         ((P.CTRL_U, P.KNOB_V, -P.PLATE - 6.5), "knob: pins 2, 3, 4, 5", 210, 90),
                         ((P.PICO_U0 + 12, P.PICO_V + 9, P.W_PICO - 9), "key's plug: pins 6, 7, 8, 36\n(+ two 4.7k pull-ups)", -120, -190)]:
        s.label(np.array(P.world(*p)), t, dx, dy, 24)
    page("wires", 10, "The wires: as the README's tables", [s.img],
         note="Dupont leads onto the headers. The key's plug wires come from the body: leave them long enough to reach.")

    # 11. into the body, the cable in its slot
    stack = done10 + g["usb cable"]
    inbody = [(body, WHITE)] + g["body inserts"] + g["feet"] + g["plug"] + [(lock, WHITE)]
    a = Shot(items(inbody) + items(stack, move=N * 70), -150, 20, (900, 950), pad=0.05)
    for u, v in ((P.W + 10, 20), (P.W + 10, 70)):
        a.arrow(np.array(P.world(u, v, 62)), np.array(P.world(u, v, 12)))
    cable_at = np.array(P.world(-14, P.PICO_V, P.W_PICO + 1.5))
    a.arrow(cable_at + N * 64, cable_at + N * 8)
    a.label(cable_at + N * 70, "plug the cable in first;\nit slides down the slot", -20, -150, 24)
    fit = [np.array(P.world(du, v, w)) for du in (-20, 8) for v in (48, 88) for w in (-36, 6)]
    b = Shot(items(inbody + stack), -150, 16, (750, 950), fit=fit)
    b.label(cable_at, "the plate closes\nthe slot", 0, 180, 24)
    page("into-body", 11, "Into the body, the Pico's cable down the slot", [a.img, b.img],
         need=[(icon(g["usb cable"][:2], el=20), "1×", "micro-USB cable")])

    # 12. the plate's screws
    whole = inbody + stack + g["switch"]
    s = Shot(items(whole) + items(g["plate screws"], move=N * 25), -62, 20, (1650, 1000), pad=0.05)
    for u, v in P.SCREWS:
        s.arrow(np.array(P.world(u, v, 24)), np.array(P.world(u, v, 4)))
    page("plate-screws", 12, "Four screws through the plate's corners", [s.img],
         need=[(ic["csk"], "4×", "M3 × 8 countersunk")], note="Snug, not tight: a countersunk head forced into plastic can split it.")

    # 13. the knob, the key
    whole += g["plate screws"] + g["switch nut"] + g["ec11 nut"]
    a = Shot(items(whole) + items(g["knob"], move=N * 30) + items(g["key"], move=(0, 0, 40)), -62, 20, (900, 950), pad=0.05)
    a.arrow(np.array(P.world(P.CTRL_U + 14, P.KNOB_V, 40)), np.array(P.world(P.CTRL_U + 14, P.KNOB_V, 18)))
    k = ctr(g["key"][0][0])
    a.arrow(k + (0, 0, 70), k + (0, 0, 52))
    a.label(k + (0, 0, 40), "the key, straight down\nonto its plug", 200, -60, 24)
    b = Shot(items(whole + g["knob"] + g["key"]), -42, 18, (750, 950), pad=0.06)
    page("done", 13, "The knob's cap, then a key on top", [a.img, b.img],
         need=[(icon(g["knob"]), "1×", "knob cap"), (icon(g["key"], el=20), "1×", "a key-c in its cartridge")])


if __name__ == "__main__":
    main()
