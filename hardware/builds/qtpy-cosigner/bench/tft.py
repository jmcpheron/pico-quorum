# The Lonely Binary 1.8" 128x160 ST7735S on the QT Py ESP32 Pico's pads
# (hardware/builds/qtpy-cosigner/README.md), landscape as 160x128, as board.py runs build1's 1.8":
# MY|MV with the header on the right, inversion on, no RAM offset. Checked on the board 2026-10-28.
# A full-screen framebuffer, scaled text.
from machine import Pin, SPI
import framebuf, struct, time

W, H = 160, 128
MADCTL = 0xA0

_bl = Pin(15, Pin.OUT, value=0)       # A3
_cs, _dc, _rst = Pin(26, Pin.OUT, value=1), Pin(25, Pin.OUT), Pin(27, Pin.OUT)    # A0, A1, A2
_spi = SPI(1, baudrate=24_000_000, sck=Pin(14), mosi=Pin(13))     # SCK, MO: HSPI's own pins


def _cmd(c, data=None):
    _cs(0); _dc(0); _spi.write(bytes([c]))
    if data:
        _dc(1); _spi.write(data)
    _cs(1)


_rst(0); time.sleep_ms(50); _rst(1); time.sleep_ms(150)
_cmd(0x01); time.sleep_ms(150)
_cmd(0x11); time.sleep_ms(120)
_cmd(0x3A, b"\x05")
_cmd(0x36, bytes([MADCTL]))
_cmd(0x21)
_cmd(0x13); _cmd(0x29); time.sleep_ms(20)
_bl(1)

buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)


def rgb(r, g, b):                     # big-endian RGB565, as the panel wants
    v = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
    return (v & 0xFF) << 8 | v >> 8


BLACK, WHITE, GREY = rgb(0, 0, 0), rgb(255, 255, 255), rgb(110, 110, 110)
RED, GREEN, YELLOW, BLUE = rgb(255, 80, 60), rgb(80, 230, 80), rgb(250, 230, 60), rgb(80, 140, 255)


def show():
    _cmd(0x2A, struct.pack(">HH", 0, W - 1))
    _cmd(0x2B, struct.pack(">HH", 0, H - 1))
    _cmd(0x2C, buf)


_g = bytearray(8)
_gf = framebuf.FrameBuffer(_g, 8, 8, framebuf.MONO_HLSB)


def text(s, x, y, c, k=2):            # the 8x8 font, scaled by k
    if k == 1:
        fb.text(s, x, y, c)
        return
    for ch in s:
        _gf.fill(0); _gf.text(ch, 0, 0, 1)
        for row in range(8):
            bits = _g[row]
            for col in range(8):
                if bits & (0x80 >> col):
                    fb.fill_rect(x + col * k, y + row * k, k, k, c)
        x += 8 * k
