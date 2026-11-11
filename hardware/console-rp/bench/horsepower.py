# console-rp: how much there is to work with. Bench only, on the stock Pico 2 MicroPython: the CPU,
# the heap, the hash the console rebuilds, drawing, the screen's SPI and DMA, and four kinds of
# animation, each timed and shown on the screen. It doesn't touch the key (I2C0 isn't opened).
#
# Needs keccak.py, safe_tx.py, qf_bold18.bin and qf_sans14.bin from firmware/ on the board's
# filesystem (put.py puts them there), then:
#   uv run --no-project --with pyserial==3.5 python hardware/console-rp/bench/rawrepl.py PORT hardware/console-rp/bench/horsepower.py
# Each result is one line "name: value". Results are in HORSEPOWER.md.
import gc
import os
import sys
import time
import struct
import machine
import micropython
import framebuf
from machine import Pin, SPI

W, H = 240, 135
X0, Y0 = 40, 53                         # the 240x135 window in the ST7789's RAM (MADCTL 0x60)
us = time.ticks_us
dt = time.ticks_diff


def out(name, value):
    print("%s: %s" % (name, value))


def rgb(r, g, b):
    v = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
    return (v & 0xFF) << 8 | v >> 8


BG, INK, DIM, ACC, RED = rgb(11, 13, 17), rgb(255, 255, 255), rgb(120, 126, 140), rgb(122, 146, 255), rgb(255, 69, 58)

# ----------------------------------------------------------------------------- the panel
bl = Pin(13, Pin.OUT, value=0)
cs, dc, rst = Pin(9, Pin.OUT, value=1), Pin(8, Pin.OUT, value=1), Pin(12, Pin.OUT, value=1)
spi = SPI(1, baudrate=25_000_000, sck=Pin(10), mosi=Pin(11), miso=None)
dc.init(Pin.OUT, value=1)


def cmd(c, data=None):
    cs(0); dc(0); spi.write(bytes([c]))
    if data:
        dc(1); spi.write(data)
    cs(1)


def panel():
    rst(0); time.sleep_ms(20); rst(1); time.sleep_ms(150)
    cmd(0x01); time.sleep_ms(150)
    cmd(0x11); time.sleep_ms(120)
    cmd(0x3A, b"\x55"); cmd(0x36, b"\x60"); cmd(0x21); cmd(0x13); cmd(0x29)
    bl(1)


def window(x, y, w, h):
    cmd(0x2A, struct.pack(">HH", X0 + x, X0 + x + w - 1))
    cmd(0x2B, struct.pack(">HH", Y0 + y, Y0 + y + h - 1))


def push(b, x=0, y=0, w=W, h=H):
    window(x, y, w, h)
    cmd(0x2C, b)


buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)


def timed(f, n=10):
    """-> mean ms of f() over n runs."""
    gc.collect()
    t = us()
    for _ in range(n):
        f()
    return dt(us(), t) / n / 1000


def label(s, sub=""):
    fb.fill_rect(0, 0, W, 12, BG)
    fb.text(s[:30], 2, 2, INK)
    if sub:
        fb.fill_rect(0, H - 11, W, 11, BG)
        fb.text(sub[:30], 2, H - 10, DIM)


# ----------------------------------------------------------------------------- the board
def board():
    out("micropython", "%s, %s" % (".".join(map(str, sys.implementation.version[:3])), os.uname().machine))
    out("cpu MHz", machine.freq() // 1_000_000)
    gc.collect()
    out("heap free KB", gc.mem_free() // 1024)
    big = 0                             # the largest one block: what a framebuffer can have
    for kb in range(480, 0, -8):
        try:
            b = bytearray(kb * 1024)
            big = kb
            del b
            break
        except MemoryError:
            pass
    gc.collect()
    out("largest block KB", big)
    s = os.statvfs("/")
    out("filesystem KB", "%d (%d free)" % (s[0] * s[2] // 1024, s[0] * s[3] // 1024))


# ----------------------------------------------------------------------------- the CPU
def py_loop(n):
    s = 0
    for i in range(n):
        s += i
    return s


@micropython.native
def native_loop(n):
    s = 0
    for i in range(n):
        s += i
    return s


@micropython.viper
def viper_loop(n: int) -> int:
    s = 0
    for i in range(n):
        s += i
    return s


def cpu():
    for name, f in (("python", py_loop), ("native", native_loop), ("viper", viper_loop)):
        gc.collect()
        t = us()
        f(100_000)
        out("loop %s M/s" % name, "%.2f" % (100_000 / dt(us(), t)))
    try:
        from keccak import keccak256
        import safe_tx
    except ImportError as e:
        out("keccak", "skipped (%s)" % e)
        return
    out("keccak 32 B ms", "%.1f" % timed(lambda: keccak256(b"\x00" * 32), 5))
    out("keccak 1 KB ms", "%.1f" % timed(lambda: keccak256(b"\x00" * 1024), 3))
    # A USDC transfer, as the console rebuilds it: the hash of the data, the struct, the domain.
    data = bytes.fromhex("a9059cbb" + "00" * 12 + "11" * 20 + "%064x" % 1_000_000)
    safe = "0x" + "22" * 20

    def one():
        safe_tx._domain_cache.clear()
        safe_tx.safe_tx_hash(8453, safe, "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", 0, data, 0, nonce=7)
    out("safe tx hash ms", "%.1f" % timed(one, 3))


# ----------------------------------------------------------------------------- drawing, in C
class Font:
    """fonts.py's Font, from a file, without lcd.py."""

    def __init__(self, path):
        b = bytearray(os.stat(path)[6])
        with open(path, "rb") as f:
            f.readinto(b)
        self.buf, self.height, self.first, self.count = b, b[3], b[5], b[6]
        self.data = memoryview(b)[8 + 8 * self.count:]
        self.glyphs = {}

    def glyph(self, c):
        g = self.glyphs.get(c)
        if g is None:
            i = ord(c) - self.first
            off, w, h, xo, yo, adv = struct.unpack_from("<HBBbbB", self.buf, 8 + 8 * i)
            g = self.glyphs[c] = (framebuf.FrameBuffer(self.data[off:off + h * ((w + 1) // 2)], w, h,
                                                       framebuf.GS4_HMSB) if w else None, xo, yo, adv)
        return g


def palette(fg, bg):
    p = framebuf.FrameBuffer(bytearray(32), 16, 1, framebuf.RGB565)
    for i in range(16):
        p.pixel(i, 0, rgb(*(bg[k] + (fg[k] - bg[k]) * i // 15 for k in range(3))))
    return p


def aa_text(f, s, x, y, pal, key):
    for c in s:
        g, xo, yo, adv = f.glyph(c)
        if g:
            fb.blit(g, x + xo, y + yo, key, pal)
        x += adv
    return x


def page(f18, f14, pal18, pal14):
    """A review page much like the console's: a title, five lines of text, a footer."""
    fb.fill(BG)
    aa_text(f18, "Send 1,000.00 USDC", 6, 6, pal18, BG)
    for i, s in enumerate(("to 0x1111… 1111 (new)", "on Base, nonce 7", "from Safe 0x2222…2222",
                           "hash 3f8e 01c2 … 9ad0", "page 1 of 3")):
        aa_text(f14, s.replace("…", "..."), 6, 32 + i * 17, pal14, BG)
    fb.fill_rect(0, H - 18, W, 18, rgb(30, 34, 44))
    fb.text("Reject      Next      Sign", 14, H - 13, INK)


def drawing():
    out("fill frame ms", "%.2f" % timed(lambda: fb.fill(BG), 20))
    out("8x8 text, 16 lines ms", "%.2f" % timed(lambda: [fb.text("0123456789abcdef0123456789abcd", 0, y * 8, INK)
                                                          for y in range(16)], 10))
    spr = bytearray(32 * 32 * 2)
    sfb = framebuf.FrameBuffer(spr, 32, 32, framebuf.RGB565)
    sfb.fill(ACC)
    out("blit 32x32 x50 ms", "%.2f" % timed(lambda: [fb.blit(sfb, (i * 37) % 200, (i * 13) % 100) for i in range(50)], 5))
    try:
        f18, f14 = Font("qf_bold18.bin"), Font("qf_sans14.bin")
    except OSError:
        out("aa page", "skipped (no qf_*.bin)")
        return None
    pal18, pal14 = palette((255, 255, 255), (11, 13, 17)), palette((200, 205, 215), (11, 13, 17))
    page(f18, f14, pal18, pal14)                      # once, to build each glyph
    out("aa page draw ms", "%.2f" % timed(lambda: page(f18, f14, pal18, pal14), 10))
    return lambda: page(f18, f14, pal18, pal14)


@micropython.viper
def plasma(b, t: int):
    """Every pixel worked out in Viper: the most a per-pixel effect could cost."""
    p = ptr16(b)
    for y in range(135):
        for x in range(240):
            v = ((x + t) ^ (y * 2 - t)) & 63
            c = (v >> 1) << 11 | v << 5 | (63 - v) >> 1
            p[y * 240 + x] = (c & 0xFF) << 8 | c >> 8


# ----------------------------------------------------------------------------- the screen's SPI
def spi_sweep(draw_page):
    global spi
    for want in (25_000_000, 37_500_000, 62_500_000, 75_000_000):
        spi = SPI(1, baudrate=want, sck=Pin(10), mosi=Pin(11), miso=None)
        dc.init(Pin.OUT, value=1)
        got = int(str(spi).split("baudrate=")[1].split(",")[0])
        if draw_page:
            draw_page()
        else:
            fb.fill(BG)
        for x in range(0, W, 2):                      # one-pixel lines: a slip shows as a smear
            fb.vline(x, 100, 16, INK)
        label("SPI %.1f MHz" % (got / 1e6), "asked %.1f" % (want / 1e6))
        ms = timed(lambda: push(buf), 10)
        out("spi asked %.1f got %.1f MHz, frame ms" % (want / 1e6, got / 1e6), "%.1f (%.0f fps max)" % (ms, 1000 / ms))
        time.sleep_ms(2500)


# ----------------------------------------------------------------------------- DMA: send while drawing
SPI1_BASE = 0x40088000                  # RP2350: SSPDR +0x08, SSPSR +0x0C, SSPDMACR +0x24
DREQ_SPI1_TX = 26


def dma_setup():
    try:
        import rp2
        d = rp2.DMA()
    except Exception as e:
        out("dma", "none (%s)" % e)
        return None
    machine.mem32[SPI1_BASE + 0x24] |= 2    # TXDMAE: the SPI asks the DMA for bytes
    return d


def dma_push(d, b, x=0, y=0, w=W, h=H):
    """Start sending b; -> a function that waits for it to finish and ends the write."""
    window(x, y, w, h)
    cs(0); dc(0); spi.write(b"\x2c"); dc(1)
    d.config(read=b, write=SPI1_BASE + 0x08, count=len(b),
             ctrl=d.pack_ctrl(size=0, inc_read=True, inc_write=False, treq_sel=DREQ_SPI1_TX), trigger=True)

    def done():
        t = us()
        while d.active():
            if dt(us(), t) > 200_000:
                raise OSError("DMA didn't finish")
        while machine.mem32[SPI1_BASE + 0x0C] & 0x10:     # BSY: the last byte still going out
            pass
        cs(1)
    return done


def dma_test(d):
    fb.fill(BG)
    label("DMA push")
    t = us()
    done = dma_push(d, buf)
    spare = 0
    while d.active():                   # what the CPU gets done while the frame goes out
        spare += 1
    done()
    ms = dt(us(), t) / 1000
    out("dma frame ms", "%.1f, CPU free while it runs (%d loops)" % (ms, spare))


# ----------------------------------------------------------------------------- animation
def run_for(ms, step):
    """-> frames a second of step(i) for ms milliseconds."""
    gc.collect()
    n, t = 0, us()
    while dt(us(), t) < ms * 1000:
        step(n)
        n += 1
    return n * 1000_000 / dt(us(), t)


def animations(d, draw_page):
    # 1. The whole frame redrawn and sent every time: a page sliding in.
    def slide(i):
        if draw_page:
            draw_page()
        else:
            fb.fill(BG)
        off = (i * 8) % W
        fb.scroll(-off, 0)
        fb.fill_rect(W - off, 0, off, H, BG)
        label("full frame: slide")
        push(buf)
    out("anim full frame fps", "%.1f" % run_for(3000, slide))

    # 2. The same, double-buffered: frame n goes out by DMA while frame n+1 is drawn.
    if d:
        b2 = bytearray(W * H * 2)
        fb2 = framebuf.FrameBuffer(b2, W, H, framebuf.RGB565)
        pair = ((buf, fb), (b2, fb2))
        state = [None]

        def slide2(i):
            b, f = pair[i & 1]
            f.fill(BG)
            x = (i * 4) % (W - 60)
            f.fill_rect(x, 30, 60, 60, ACC)
            f.text("double buffered", 4, 4, INK)
            if state[0]:
                state[0]()
            state[0] = dma_push(d, b)
        out("anim dma double-buffer fps", "%.1f" % run_for(3000, slide2))
        if state[0]:
            state[0]()
        del b2, fb2, pair

    # 3. Only what moved: a 44x44 block bouncing, sent as its own window.
    fb.fill(BG)
    label("dirty rect: 44x44", "only the block is sent")
    push(buf)
    s = bytearray(44 * 44 * 2)
    sf = framebuf.FrameBuffer(s, 44, 44, framebuf.RGB565)
    sf.fill(BG)
    sf.fill_rect(2, 2, 40, 40, ACC)
    pos = [10, 20, 2, 2]

    def bounce(i):
        pos[0] += pos[2]
        pos[1] += pos[3]
        if not 0 <= pos[0] <= W - 44:
            pos[2] = -pos[2]; pos[0] += 2 * pos[2]
        if not 12 <= pos[1] <= H - 55:
            pos[3] = -pos[3]; pos[1] += 2 * pos[3]
        push(s, pos[0], pos[1], 44, 44)
    out("anim 44x44 dirty rect fps", "%.0f" % run_for(3000, bounce))

    # 4. A busy spinner, 32x32, as while the key signs: 8 dots, one bright.
    fb.fill(BG)
    label("spinner 32x32", "as while the key signs")
    push(buf)
    sp = bytearray(32 * 32 * 2)
    spf = framebuf.FrameBuffer(sp, 32, 32, framebuf.RGB565)
    pts = ((16, 3), (25, 7), (29, 16), (25, 25), (16, 29), (7, 25), (3, 16), (7, 7))
    shades = [rgb(122 * k // 7, 146 * k // 7, 255 * k // 7) for k in range(8)]
    t0 = [us()]

    def spin(i):
        spf.fill(BG)
        for k, (x, y) in enumerate(pts):
            spf.ellipse(x, y, 3, 3, shades[(k - i) % 8], True)
        push(sp, 104, 52, 32, 32)
        while dt(us(), t0[0]) < 33_000:           # 30 fps: then how much of the CPU is it?
            pass
        t0[0] = us()

    busy = [0]

    def spin_cost(i):
        t = us()
        spf.fill(BG)
        for k, (x, y) in enumerate(pts):
            spf.ellipse(x, y, 3, 3, shades[(k - i) % 8], True)
        push(sp, 104, 52, 32, 32)
        busy[0] += dt(us(), t)
    n = 30
    for i in range(n):
        spin_cost(i)
    out("anim spinner frame ms", "%.2f (%.0f%% of the CPU at 30 fps)" % (busy[0] / n / 1000, busy[0] / n / 333))
    run_for(2000, spin)

    # 5. Every pixel, in Viper: a plasma.
    label("viper plasma")

    def pl(i):
        plasma(buf, i * 3)
        push(buf)
    out("anim viper plasma fps", "%.1f" % run_for(3000, pl))
    out("viper plasma draw ms", "%.1f" % timed(lambda: plasma(buf, 5), 5))


def main():
    panel()
    fb.fill(BG)
    label("console-rp: horsepower", "measuring...")
    push(buf)
    board()
    cpu()
    page = drawing()
    spi_sweep(page)
    d = dma_setup()
    if d:
        try:
            dma_test(d)
        except OSError as e:
            out("dma", "failed (%s)" % e)
            d = None
    animations(d, page)
    fb.fill(BG)
    label("done", "results went over the link")
    push(buf)
    gc.collect()
    out("heap free after KB", gc.mem_free() // 1024)


main()
