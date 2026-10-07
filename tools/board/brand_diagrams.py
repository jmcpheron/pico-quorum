# The diagrams in docs/BRANDED-KEYS.md: quorum v2 on an ATECC608C, the brand record, a branded
# chip's life, and the bench. Plain SVG in the brand's dark colours (docs/BRAND.md), with the
# lockup from docs/brand/. The slot rules come from the proposal, not from firmware: no firmware
# has quorum v2 yet.
#   python3 tools/board/brand_diagrams.py [outdir]
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs/branded-keys")

BG, PANEL, TEXT, MUTED = "#0B0D11", "#161A21", "#F2F4F7", "#98A0AC"
OK, WARN, ETH, RED, LINE = "#34C759", "#FFB830", "#7A92FF", "#FF5C54", "#2A303A"
BENCH, USER, DEAD = ETH, OK, "#3A414C"
SANS = "Inter, Helvetica, Arial, sans-serif"
MONO = "JetBrains Mono, Menlo, Consolas, monospace"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def lockup(x, y, scale):
    """The dark lockup (mark and wordmark), its outer <svg> dropped."""
    s = open(os.path.join(ROOT, "docs/brand/lockup-dark.svg")).read()
    inner = s[s.index(">", s.index("<svg")) + 1:s.rindex("</svg>")]
    inner = inner[:inner.find("<title>")] + inner[inner.find("</title>") + 8:] if "<title>" in inner else inner
    return '<g transform="translate(%g,%g) scale(%g)">%s</g>' % (x, y, scale, inner)


def mark(x, y, scale):
    """The mark alone: five owners, three signed, their triangle."""
    return ('<g transform="translate(%g,%g) scale(%g)"><polygon points="16,4 23.05,25.71 8.95,25.71" fill="#5FDE7E"/>'
            '<circle cx="16" cy="4" r="3" fill="#34C759"/><circle cx="27.41" cy="12.29" r="2" fill="#FFB830"/>'
            '<circle cx="23.05" cy="25.71" r="3" fill="#34C759"/><circle cx="8.95" cy="25.71" r="3" fill="#34C759"/>'
            '<circle cx="4.59" cy="12.29" r="2" fill="#FFB830"/></g>') % (x, y, scale)


def t(x, y, s, size=14, fill=TEXT, weight=400, anchor="start", font=SANS):
    return '<text x="%g" y="%g" font-family="%s" font-size="%g" font-weight="%d" fill="%s" text-anchor="%s">%s</text>' % (
        x, y, font, size, weight, fill, anchor, esc(s))


def lines(x, y, rows, size=13, gap=17, fill=TEXT, anchor="start", font=SANS):
    return "".join(t(x, y + i * gap, r, size, fill, anchor=anchor, font=font) for i, r in enumerate(rows))


def box(x, y, w, h, fill=PANEL, stroke=LINE, r=10, sw=1.5, dash=None):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return '<rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s" stroke="%s" stroke-width="%g"%s/>' % (
        x, y, w, h, r, fill, stroke, sw, d)


def pill(x, y, label, color, size=12):
    w = 9 + len(label) * size * 0.58
    return box(x, y, w, size + 10, fill=color + "22", stroke=color, r=(size + 10) / 2, sw=1.2) + \
        t(x + w / 2, y + size + 3, label, size, color, 600, "middle")


def lock(x, y, color):
    """A padlock, 14 x 16."""
    return ('<g fill="none" stroke="%s" stroke-width="2"><path d="M%g %g v-4 a5 5 0 0 1 10 0 v4"/></g>'
            '<rect x="%g" y="%g" width="14" height="10" rx="2" fill="%s"/>') % (color, x + 2, y + 6, x, y + 6, color)


def arrow(x1, y1, x2, y2, color=MUTED):
    return ('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="2" marker-end="url(#a)"/>' % (x1, y1, x2, y2, color))


def svg(w, h, title, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">\n<title>%s</title>\n'
            '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker></defs>\n'
            '<rect width="%d" height="%d" rx="18" fill="%s"/>\n%s\n</svg>\n') % (w, h, w, h, esc(title), MUTED, w, h, BG, body)


def header(w, title, sub):
    return lockup(32, 26, 0.95) + t(w - 32, 44, title, 22, TEXT, 700, "end") + t(w - 32, 66, sub, 13, MUTED, anchor="end")


def keyc(x, y, label, color, num):
    """A key-c board from above: 36 x 16 mm, drawn 144 x 64, the mark on it."""
    return (box(x, y, 144, 64, fill="#14204A", stroke=color, r=8, sw=2) +
            box(x - 14, y + 18, 18, 28, fill="#C9CED6", stroke="#C9CED6", r=3) +
            box(x + 70, y + 18, 26, 26, fill="#111", stroke="#444", r=2) + t(x + 83, y + 35, "608C", 7, MUTED, anchor="middle") +
            mark(x + 104, y + 14, 1.15) + t(x + 72, y + 84, label, 13, color, 600, "middle") +
            t(x + 72, y + 101, num, 12, MUTED, anchor="middle", font=MONO))


# ----------------------------------------------------------------------------- 1. the chip map
def chip_map():
    W, H = 1000, 920
    o = [header(W, "quorum v2 on an ATECC608C", "PicoQuorum's chip configuration for a branded key (proposed)")]
    # legend
    lx = 32
    for color, label in ((BENCH, "written on the bench"), (USER, "made by your console"), (DEAD, "dead: zeros, never read")):
        o.append(box(lx, 96, 16, 16, fill=color, stroke=color, r=4) + t(lx + 24, 109, label, 13, MUTED))
        lx += 230
    o.append(lock(lx, 94, RED) + t(lx + 22, 109, "permanent lock", 13, MUTED))

    # config zone
    y = 140
    o.append(box(24, y, W - 48, 150, fill=PANEL))
    o.append(t(44, y + 30, "Config zone", 18, TEXT, 700) + t(170, y + 30, "128 bytes: what every slot may do", 13, MUTED))
    o.append(lock(W - 250, y + 15, RED) + t(W - 228, y + 30, "B3: locked with a CRC", 13, BENCH, 600))
    cells = [("0-15", "the chip's own", "serial, revision", DEAD), ("16", "I2C address", "0x60", BENCH),
             ("18", "CountMatch", "off", BENCH), ("20-51", "SlotConfig x16", "rules per slot", BENCH),
             ("52-67", "counters", "0 / 0", BENCH), ("86-87", "lock bytes", "data / config", BENCH),
             ("88-89", "SlotLocked", "slot 0 at U4", USER), ("96-127", "KeyConfig x16", "key types", BENCH)]
    cw = (W - 48 - 40 - 7 * 8) / 8
    for i, (b, name, val, c) in enumerate(cells):
        cx = 44 + i * (cw + 8)
        o.append(box(cx, y + 48, cw, 84, fill=c + "1f", stroke=c, r=8))
        o.append(t(cx + 10, y + 70, "bytes " + b, 11, MUTED, font=MONO) + t(cx + 10, y + 94, name, 13, TEXT, 600) +
                 t(cx + 10, y + 116, val, 12, c))

    # data zone
    y = 310
    o.append(box(24, y, W - 48, 412, fill=PANEL))
    o.append(t(44, y + 30, "Data zone", 18, TEXT, 700) + t(156, y + 30, "16 slots", 13, MUTED))
    o.append(lock(W - 290, y + 15, RED) + t(W - 268, y + 30, "B6: locked with a CRC, brand inside", 13, BENCH, 600))
    gx, gy, gw, gh, gap = 44, y + 50, (W - 48 - 40 - 3 * 12) / 4, 70, 12
    for n in range(16):
        r, c = divmod(n, 4)
        x, yy = gx + c * (gw + gap), gy + r * (gh + gap)
        if n == 0:
            continue
        if n == 8:
            o.append(box(x, yy, gw, gh, fill=BENCH + "26", stroke=BENCH, r=8, sw=2))
            o.append(t(x + 12, yy + 22, "slot 8 · 416 B", 12, MUTED, font=MONO) + t(x + 12, yy + 44, "brand signature", 14, TEXT, 700) +
                     t(x + 12, yy + 62, "clear read · never written", 11, BENCH))
        else:
            size = "36 B" if n < 8 else "72 B"
            o.append(box(x, yy, gw, gh, fill=DEAD + "55", stroke=DEAD, r=8))
            o.append(t(x + 12, yy + 22, "slot %d · %s" % (n, size), 12, MUTED, font=MONO) + t(x + 12, yy + 44, "dead", 14, MUTED, 600) +
                     t(x + 12, yy + 62, "zeros · never read or written", 11, MUTED))
    # slot 0, drawn last and larger: the key
    o.append(box(gx - 4, gy - 4, gw + 8, gh + 8, fill=USER + "26", stroke=USER, r=10, sw=2.5))
    o.append(t(gx + 10, gy + 18, "slot 0 · 36 B", 12, MUTED, font=MONO) + t(gx + 10, gy + 40, "YOUR KEY · P-256", 14, TEXT, 700) +
             t(gx + 10, gy + 58, "GenKey only · LimitedUse", 11, USER) + lock(gx + gw - 18, gy + 4, RED))
    # slot 0's rules, spelled out
    ry = gy + 4 * (gh + gap) + 14
    o.append(t(44, ry, "Slot 0's rules:", 13, TEXT, 700))
    o.append(t(160, ry, "Sign external only · no internal sign, no ECDH · PrivWrite never · public key readable · "
                        "counter 0 counts every use · sealed by your U4", 12, MUTED))

    # OTP
    y = 742
    o.append(box(24, y, W - 48, 154, fill=PANEL))
    o.append(t(44, y + 30, "OTP zone", 18, TEXT, 700) + t(146, y + 30, "64 bytes", 13, MUTED))
    o.append(lock(W - 250, y + 15, RED) + t(W - 228, y + 30, "B6: frozen with the data", 13, BENCH, 600))
    segs = [(2, "PQ"), (1, "v2"), (1, "prof"), (9, "serial"), (4, "rev"), (2, "CRC"), (2, "batch"), (4, "number"),
            (4, "date"), (4, "build"), (16, "brand key id"), (15, "zeros")]
    bx, bw = 44, W - 88
    x, low = bx, False
    for size, label in segs:
        w = bw * size / 64
        c = DEAD if label == "zeros" else BENCH
        o.append(box(x, y + 50, w - 2, 44, fill=c + "33", stroke=c, r=4, sw=1))
        if w > 30:
            o.append(t(x + w / 2 - 1, y + 77, label, 11, TEXT, anchor="middle"))
        else:
            o.append(t(x + w / 2 - 1, y + (122 if low else 108), label, 10, MUTED, anchor="middle"))
            low = not low
        x += w
    o.append(t(44, y + 144, "The brand record, version 2. No key fields: there is no key yet when the bench writes it.", 12, MUTED))
    return svg(W, H, "quorum v2 on an ATECC608C: the config zone, sixteen data slots and the OTP zone, and who writes each", "".join(o))


# ----------------------------------------------------------------------------- 2. the brand record
def brand_record():
    W, H = 1000, 470
    o = [header(W, "How a chip gets its brand", "B4 writes the record, B5 has key 0000 sign it, B6 locks both")]
    y = 120
    # the record
    o.append(box(32, y, 270, 150, fill=PANEL) + t(52, y + 30, "OTP · brand record", 15, TEXT, 700))
    o.append(lines(52, y + 56, ["PQ · v2 · quorum v2", "serial 0123e1…e1ee · 608C", "config CRC · batch 3 · 0042",
                                "date · bench build", "brand key id"], 12, 17, MUTED, font=MONO))
    o.append(arrow(306, y + 75, 340, y + 75))
    # the digest
    o.append(box(344, y + 30, 250, 90, fill=PANEL, stroke=WARN) + t(469, y + 58, "SHA-256(", 13, WARN, 600, "middle", MONO))
    o.append(t(469, y + 80, '"PicoQuorum brand v1"', 12, TEXT, anchor="middle", font=MONO) +
             t(469, y + 100, "‖ record )", 13, WARN, 600, "middle", MONO))
    o.append(arrow(598, y + 75, 640, y + 75))
    # key 0000
    o.append(keyc(664, y + 40, "key 0000 signs", BENCH, "the brand key"))
    o.append(arrow(812, y + 72, 862, y + 72))
    o.append(t(870, y + 68, "r ‖ s", 14, BENCH, 600, font=MONO) + t(870, y + 86, "64 B, low s", 11, MUTED))
    # slot 8
    y2 = 320
    o.append(box(32, y2, W - 64, 74, fill=PANEL))
    o.append(t(52, y2 - 10, "slot 8 · 416 bytes", 13, TEXT, 700))
    sx, sw = 52, W - 104
    o.append(box(sx, y2 + 16, sw * 64 / 416, 42, fill=BENCH + "40", stroke=BENCH, r=4) + t(sx + sw * 32 / 416, y2 + 42, "r ‖ s · 64 B", 12, TEXT, 600, "middle"))
    o.append(box(sx + sw * 64 / 416 + 2, y2 + 16, sw * 352 / 416 - 2, 42, fill=DEAD + "40", stroke=DEAD, r=4) +
             t(sx + sw * 240 / 416, y2 + 42, "zeros", 12, MUTED, anchor="middle"))
    o.append('<path d="M%g %g C %g %g, %g %g, %g %g" fill="none" stroke="%s" stroke-width="2" marker-end="url(#a)"/>' % (
        890, y + 100, 900, y + 190, 200, y2 - 60, sx + 50, y2 + 12, MUTED))
    o.append(t(32, 430, "The console checks it at U1: the signature under the pinned key 0000, the record's serial, revision and CRC "
                        "against the chip, and both zones locked.", 12, MUTED))
    o.append(t(32, 450, "The label's picture is the blockie of the digest's first 20 bytes.", 12, MUTED))
    return svg(W, H, "The brand record is hashed with a fixed prefix, signed by PicoQuorum key 0000, and the signature is stored in slot 8", "".join(o))


# ----------------------------------------------------------------------------- 3. a chip's life
def lifecycle():
    W, H = 1000, 400
    o = [header(W, "A branded key's life", "Four states. Each arrow is permanent.")]
    states = [("Factory", "from Microchip", ["config open", "data open", "anything can change"], DEAD, "chip"),
              ("Configured", "B3 · bench", ["config locked (CRC)", "data open", "brand not written yet"], BENCH, "lock"),
              ("Branded", "B6 · bench", ["data + OTP locked", "brand signed", "slot 0 empty, open"], BENCH, "mark"),
              ("Claimed", "U4 · your console", ["slot 0 sealed", "your key, made in the chip", "owner address fixed"], USER, "lock")]
    bw, gap, y = 205, 46, 130
    for i, (name, who, rows, c, icon) in enumerate(states):
        x = 32 + i * (bw + gap)
        o.append(box(x, y, bw, 170, fill=PANEL, stroke=c, sw=2))
        if icon == "mark":
            o.append(mark(x + bw - 50, y + 12, 1.2))
        elif icon == "lock":
            o.append(lock(x + bw - 34, y + 14, RED))
        o.append(t(x + 16, y + 34, name, 18, TEXT, 700) + t(x + 16, y + 56, who, 12, MUTED if c == DEAD else c, 600))
        o.append(lines(x + 16, y + 90, rows, 12, 22, MUTED))
        if i < 3:
            o.append(arrow(x + bw + 4, y + 85, x + bw + gap - 4, y + 85, RED))
    o.append(box(32, 318, 2 * bw + gap + bw + gap - 10, 6, fill=BENCH, stroke=BENCH, r=3) + t(32, 346, "the bench", 12, BENCH, 600))
    o.append(box(32 + 3 * (bw + gap) - 10, 318, bw + 10, 6, fill=USER, stroke=USER, r=3) + t(32 + 3 * (bw + gap), 346, "you", 12, USER, 600))
    o.append(t(W / 2, 382, "Ships here: branded, no key. Only the chip's own GenKey can fill slot 0.", 13, MUTED, anchor="middle"))
    return svg(W, H, "A branded key's life: factory, configured at B3, branded at B6 when it ships, claimed at U4 by the user", "".join(o))


# ----------------------------------------------------------------------------- 4. the bench
def bench():
    W, H = 1000, 480
    o = [header(W, "The branding bench", "One Pico, two key-c receptacles, one label printer")]
    # the Pico with its screen
    px, py = 380, 130
    o.append(box(px, py, 240, 250, fill="#0F3D24", stroke=OK, r=12, sw=2) + t(px + 120, py + 26, "Pico 2 W · brand image", 13, TEXT, 600, "middle"))
    o.append(box(px + 40, py + 42, 160, 160, fill="#000", stroke="#444", r=4))
    o.append(t(px + 52, py + 64, "BRAND quorum v2", 11, WARN, 600, font=MONO) + t(px + 52, py + 86, "B7 Label: OK", 11, OK, 600, font=MONO))
    o.append(lines(px + 52, py + 106, ["ok locked 00/00", "ok signed: 0000", "ok slot 0 empty"], 10, 16, OK, font=MONO))
    o.append(mark(px + 98, py + 160, 1.3) + t(px + 12, py + 216, "I2C0", 11, MUTED, font=MONO) + t(px + 228, py + 216, "I2C1", 11, MUTED, anchor="end", font=MONO))
    # receptacles
    o.append(arrow(px, py + 225, 290, py + 225, BENCH) + keyc(130, py + 192, "the chip being branded", BENCH, "swapped each time"))
    o.append(arrow(px + 240, py + 225, 700, py + 225, ETH) + keyc(722, py + 192, "key 0000, the brand key", ETH, "plugged in for good"))
    # laptop and printer
    o.append(box(130, py, 170, 92, fill=PANEL) + lines(146, py + 30, ["laptop", "tools/fw", "chips/ inventory"], 12, 20, MUTED))
    o.append(arrow(300, py + 46, px - 4, py + 46))
    o.append(box(722, py, 170, 92, fill=PANEL) + lines(738, py + 30, ["label printer", "number, picture,", "QR code"], 12, 20, MUTED))
    o.append(arrow(px + 244, py + 46, 718, py + 46))
    o.append(t(W / 2, 462, "Both ATECCs answer at 0x60, so each has its own I2C controller. atecc.ATECC608(sda, scl) already takes the pins.", 12, MUTED, anchor="middle"))
    return svg(W, H, "The branding bench: a Pico running the brand image, the chip being branded on I2C0, key 0000 on I2C1, a laptop and a label printer", "".join(o))


os.makedirs(OUT, exist_ok=True)
for name, fn in (("chip-map", chip_map), ("brand-record", brand_record), ("lifecycle", lifecycle), ("bench", bench)):
    with open(os.path.join(OUT, name + ".svg"), "w") as f:
        f.write(fn())
    print(name)
