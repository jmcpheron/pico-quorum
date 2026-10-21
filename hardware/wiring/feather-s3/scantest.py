# Feather ESP32-S3 Reverse TFT bench test: screen, buttons, battery, live I2C scan.
# Standalone; not part of the console image.
from machine import Pin, SPI, SoftI2C
import framebuf, struct, time

W, H = 240, 135
MADCTL, XOFF, YOFF = 0x60, 40, 53     # landscape; try 0xA0 with 40, 52 if it is upside down

Pin(7, Pin.OUT, value=1)              # TFT + I2C power
bl = Pin(45, Pin.OUT, value=0)
cs, dc, rst = Pin(42, Pin.OUT, value=1), Pin(40, Pin.OUT), Pin(41, Pin.OUT)
spi = SPI(1, baudrate=40_000_000, sck=Pin(36), mosi=Pin(35))

def cmd(c, data=None):
    cs(0); dc(0); spi.write(bytes([c]))
    if data:
        dc(1); spi.write(data)
    cs(1)

rst(0); time.sleep_ms(50); rst(1); time.sleep_ms(150)
cmd(0x01); time.sleep_ms(150)         # software reset
cmd(0x11); time.sleep_ms(120)         # sleep out
cmd(0x3A, b"\x55")                    # 16-bit colour
cmd(0x36, bytes([MADCTL]))
cmd(0x21)                             # inversion on (this panel needs it)
cmd(0x13); cmd(0x29); time.sleep_ms(20)
bl(1)

buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)

def rgb(r, g, b):                     # big-endian RGB565, as the panel wants
    v = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
    return (v & 0xFF) << 8 | v >> 8

BLACK, WHITE = rgb(0, 0, 0), rgb(255, 255, 255)
RED, GREEN, YELLOW, BLUE, GREY = rgb(255, 80, 60), rgb(80, 230, 80), rgb(250, 230, 60), rgb(80, 140, 255), rgb(90, 90, 90)

def show():
    cmd(0x2A, struct.pack(">HH", XOFF, XOFF + W - 1))
    cmd(0x2B, struct.pack(">HH", YOFF, YOFF + H - 1))
    cmd(0x2C, buf)

_g = bytearray(8)
_gf = framebuf.FrameBuffer(_g, 8, 8, framebuf.MONO_HLSB)
def text(s, x, y, c, k=2):            # the 8x8 font, scaled by k
    for ch in s:
        _gf.fill(0); _gf.text(ch, 0, 0, 1)
        for row in range(8):
            bits = _g[row]
            for col in range(8):
                if bits & (0x80 >> col):
                    fb.fill_rect(x + col * k, y + row * k, k, k, c)
        x += 8 * k

d0 = Pin(0, Pin.IN, Pin.PULL_UP)      # D0: low when pressed
d1 = Pin(1, Pin.IN, Pin.PULL_DOWN)    # D1, D2: high when pressed
d2 = Pin(2, Pin.IN, Pin.PULL_DOWN)
i2c = SoftI2C(sda=Pin(3, Pin.IN, Pin.PULL_UP), scl=Pin(4, Pin.IN, Pin.PULL_UP), freq=100_000)

def battery():
    try:
        r = i2c.readfrom_mem(0x36, 0x02, 2)
        return "%.2f V" % ((r[0] << 8 | r[1]) * 78.125e-6)
    except OSError:
        return "--"

def scan():
    try:
        i2c.writeto(0, b"\x00")       # wake token: a sleeping ATECC608 does not ACK
    except OSError:
        pass
    time.sleep_ms(3)
    return i2c.scan()

last = None
while True:
    found = scan()
    chip = 0x60 in found
    btn = ("D0 " if not d0() else "") + ("D1 " if d1() else "") + ("D2" if d2() else "")
    state = (tuple(found), btn, chip)
    fb.fill(BLACK)
    fb.rect(0, 0, W, H, GREY)
    text("PQ BENCH", 8, 6, RED)
    text("BAT " + battery(), 8, 30, GREEN)
    text("I2C " + (" ".join("%02X" % a for a in found) or "none"), 8, 54, BLUE)
    text("CHIP 60 " + ("YES" if chip else "no"), 8, 78, GREEN if chip else YELLOW)
    text("BTN " + (btn or "-"), 8, 102, WHITE)
    show()
    if state != last:
        print("i2c", [hex(a) for a in found], "chip", chip, "buttons", btn or "-")
        last = state
    time.sleep_ms(300)
