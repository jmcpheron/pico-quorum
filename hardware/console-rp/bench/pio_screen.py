# console-rp: the screen driven by PIO instead of SPI1. Bench only, on the stock Pico 2 MicroPython.
# MicroPython runs the RP2350's peripheral clock at 48 MHz, so SPI1 can't go past 24 MHz (horsepower.py
# shows it). A PIO state machine runs from the 150 MHz system clock: two instructions a bit, so up to
# 75 MHz on the same pins (GPIO10 SCK, GPIO11 MOSI). DMA feeds it a frame while the CPU draws the next.
#
# Each rate shows a page, one-pixel lines and the rate in big type for 4 s: look at the panel for
# smears, wrong colours or a torn picture. The ST7789's datasheet asks for a write cycle of 16 ns
# or more (62.5 MHz). Nothing here touches the key.
#   uv run --no-project --with pyserial==3.5 python hardware/console-rp/bench/rawrepl.py PORT hardware/console-rp/bench/pio_screen.py
import gc
import time
import struct
import machine
import framebuf
import rp2
from machine import Pin

W, H = 240, 135
X0, Y0 = 40, 53
us, dt = time.ticks_us, time.ticks_diff
PIO0_TXF0, DREQ_PIO0_TX0 = 0x50200010, 0          # RP2350


def rgb(r, g, b):
    v = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
    return (v & 0xFF) << 8 | v >> 8


BG, INK, DIM, ACC = rgb(11, 13, 17), rgb(255, 255, 255), rgb(120, 126, 140), rgb(122, 146, 255)
RED, GREEN, BLUE, YEL = rgb(255, 0, 0), rgb(0, 255, 0), rgb(0, 0, 255), rgb(250, 220, 60)

bl = Pin(13, Pin.OUT, value=0)
cs, dc, rst = Pin(9, Pin.OUT, value=1), Pin(8, Pin.OUT, value=1), Pin(12, Pin.OUT, value=1)


@rp2.asm_pio(out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=True, pull_thresh=8, fifo_join=rp2.PIO.JOIN_TX,
             sideset_init=rp2.PIO.OUT_LOW, out_init=rp2.PIO.OUT_LOW)
def spi_tx():
    out(pins, 1).side(0)                # data out with the clock low (SPI mode 0)
    nop().side(1)                       # the panel takes it on the rising edge


sm = None
dma = rp2.DMA()


def start(bit_hz):
    global sm
    if sm:
        sm.active(0)
    sm = rp2.StateMachine(0, spi_tx, freq=2 * bit_hz, sideset_base=Pin(10), out_base=Pin(11))
    sm.active(1)


def drain():
    while sm.tx_fifo():
        pass
    time.sleep_us(2)                    # the last byte, still in the shift register


def put(b):
    for x in b:
        sm.put(x << 24)


def cmd(c, data=None):
    cs(0); dc(0); put((c,)); drain()
    if data:
        dc(1); put(data); drain()
    cs(1)


def panel():
    rst(0); time.sleep_ms(20); rst(1); time.sleep_ms(150)
    cmd(0x01); time.sleep_ms(150)
    cmd(0x11); time.sleep_ms(120)
    cmd(0x3A, b"\x55"); cmd(0x36, b"\x60"); cmd(0x21); cmd(0x13); cmd(0x29)
    bl(1)


def send(b, x=0, y=0, w=W, h=H):
    """Start a frame (or a window) going out by DMA; -> a function that waits for the end."""
    cmd(0x2A, struct.pack(">HH", X0 + x, X0 + x + w - 1))
    cmd(0x2B, struct.pack(">HH", Y0 + y, Y0 + y + h - 1))
    cs(0); dc(0); put((0x2C,)); drain(); dc(1)
    dma.config(read=b, write=PIO0_TXF0, count=len(b),
               ctrl=dma.pack_ctrl(size=0, inc_read=True, inc_write=False, treq_sel=DREQ_PIO0_TX0), trigger=True)

    def done():
        while dma.active():
            pass
        drain()
        cs(1)
    return done


bufs = [bytearray(W * H * 2), bytearray(W * H * 2)]
fbs = [framebuf.FrameBuffer(b, W, H, framebuf.RGB565) for b in bufs]


def big(f, s, x, y, c, k=3):
    """8x8 text drawn k times larger, for the rate."""
    t = bytearray(len(s) * 8 * 8 * 2)
    tf = framebuf.FrameBuffer(t, len(s) * 8, 8, framebuf.RGB565)
    tf.fill(BG)
    tf.text(s, 0, 0, c)
    for yy in range(8):
        for xx in range(len(s) * 8):
            p = tf.pixel(xx, yy)
            if p != BG:
                f.fill_rect(x + xx * k, y + yy * k, k, k, p)


def test_card(f, mhz):
    f.fill(BG)
    f.rect(0, 0, W, H, INK)
    big(f, "%.1f MHz" % mhz, 8, 8, YEL)
    f.text("PIO + DMA to the ST7789", 8, 40, INK)
    f.text("Send 1,000.00 USDC", 8, 54, INK)
    f.text("to 0x1111...1111", 8, 66, DIM)
    for i, c in enumerate((RED, GREEN, BLUE, INK)):
        f.fill_rect(8 + i * 30, 82, 26, 14, c)
    for x in range(132, 232, 2):        # one-pixel lines: a slipped bit smears them
        f.vline(x, 82, 14, INK)
    for x in range(8, 232, 4):
        f.pixel(x, 104, INK)
    f.text("look for smears or tears", 8, 118, DIM)


def frame_ms(b):
    gc.collect()
    t = us()
    for _ in range(10):
        send(b)()
    return dt(us(), t) / 10_000


def main():
    start(10_000_000)
    panel()
    results = []
    for mhz in (37.5, 50.0, 62.5, 75.0):
        start(int(mhz * 1_000_000))
        test_card(fbs[0], mhz)
        ms = frame_ms(bufs[0])
        results.append((mhz, ms))
        print("pio %.1f MHz: frame %.1f ms (%.0f fps max)" % (mhz, ms, 1000 / ms))
        time.sleep_ms(4000)
    # Double-buffered at the fastest rate the datasheet allows: draw frame n+1 while n goes out.
    start(62_500_000)
    pending, n, t = None, 0, us()
    while dt(us(), t) < 3_000_000:
        f = fbs[n & 1]
        f.fill(BG)
        x = (n * 3) % (W - 60)
        f.fill_rect(x, 40, 60, 60, ACC)
        f.text("62.5 MHz, double buffered", 4, 4, INK)
        f.text("frame %d" % n, 4, 120, DIM)
        if pending:
            pending()
        pending = send(bufs[n & 1])
        n += 1
    pending()
    print("pio 62.5 MHz double-buffered: %.1f fps" % (n * 1e6 / dt(us(), t)))
    test_card(fbs[0], 62.5)
    send(bufs[0])()
    sm.active(0)
    print("left on screen: the 62.5 MHz card")


main()
