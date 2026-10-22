# Started in picowallet by Austin Griffith (MIT): https://github.com/austintgriffith/picowallet
# The screen and the keys, for the board in board.py (secrets.BOARD):
#   waveshare: Pico-LCD-1.3, 240x240 ST7789 over SPI1, joystick and A/B/X/Y
#              (pins from waveshare.com/wiki/Pico-LCD-1.3)
#   build1:    2.0" 240x320 ST7789 run landscape as 320x240 on the same SPI pins, the knob
#              (knob.py) and A/B/X/Y (hardware/wiring/BUILD1.md). The console draws at
#              full native resolution, using small horizontal strips.
#   esp32:     build1's screen and knob on an ESP32's VSPI (hardware/wiring/ESP32.md)
#   feather-s3: the Feather ESP32-S3 Reverse TFT's own 240x135 ST7789 and its buttons D0, D1, D2
#              (hardware/wiring/FEATHER-S3.md)
# W and H are the size the apps draw, in pixels; draw with them rather than with numbers.
#
# Bands (board.BANDS > 1, the 320x240 panels): the framebuffer holds one horizontal strip of the
# screen, W x BAND_H. A frame is drawn once per strip by LCD.frames(draw, ...): every drawing call
# is shifted into the strip, framebuf clips the rest, and show() sends the strip to its rows. The
# drawing code doesn't know; it only has to start from frames() (quorum.py, splash.py do).
from machine import Pin, SPI, PWM
import framebuf, time
import board

BOARD, KNOB, THREE, W, H, SMALL = board.BOARD, board.KNOB, board.THREE, board.W, board.H, board.SMALL
DC, CS, SCK, MOSI, RST, BL = board.DC, board.CS, board.SCK, board.MOSI, board.RST, board.BL
KEYS = board.KEYS


def color(r, g, b):
    """RGB888 -> RGB565, byte-swapped because framebuf is little-endian and the panel wants big-endian."""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


BLACK, WHITE = color(0, 0, 0), color(255, 255, 255)
RED, GREEN, BLUE = color(255, 0, 0), color(0, 255, 0), color(0, 0, 255)
YELLOW, GREY, DARK = color(255, 220, 0), color(120, 120, 120), color(30, 30, 30)


# The one 115 KB framebuffer, allocated the moment lcd is imported. On an RP2040 board (264 KB
# RAM) a block that big is only available on a fresh heap: after a 20 KB module like quorum_ui.py
# has been compiled the heap is too fragmented and LCD() dies with MemoryError. So anything that
# runs a big module (main.py, the emulator's send) imports lcd first, and LCD() reuses this.
BANDS = board.BANDS
BAND_H = H // BANDS
_BUF = bytearray(W * BAND_H * 2)


class LCD(framebuf.FrameBuffer):
    def __init__(self):
        self.width, self.height = W, H
        self.y0, self.band_h = 0, BAND_H     # the strip in the buffer: rows y0 .. y0 + band_h - 1
        self.cs = Pin(CS, Pin.OUT, value=1)
        self.rst = Pin(RST, Pin.OUT, value=1)
        self.dc = Pin(DC, Pin.OUT, value=1)
        self.spi = SPI(board.SPI_ID, board.SPI_BAUD, polarity=0, phase=0, sck=Pin(SCK), mosi=Pin(MOSI), miso=None)
        self.bl = PWM(Pin(BL))
        self.bl.freq(1000)
        self.backlight(100)
        self.buffer = _BUF
        super().__init__(self.buffer, W, BAND_H, framebuf.RGB565)
        self._init_panel()

    def backlight(self, pct):
        self.bl.duty_u16(int(65535 * pct / 100))

    def _cmd(self, cmd, data=None):
        self.dc(0); self.cs(0); self.spi.write(bytes([cmd])); self.cs(1)
        if data:
            self.dc(1); self.cs(0); self.spi.write(bytes(data)); self.cs(1)

    def _init_panel(self):
        if board.INIT == "plain":
            self._init_build1()
            return
        self.rst(1); time.sleep_ms(10); self.rst(0); time.sleep_ms(10); self.rst(1); time.sleep_ms(120)
        self._cmd(0x36, [0x70])        # memory access: landscape, matches Waveshare demo
        self._cmd(0x3A, [0x05])        # 16-bit color
        self._cmd(0xB2, [0x0C, 0x0C, 0x00, 0x33, 0x33])
        self._cmd(0xB7, [0x35])
        self._cmd(0xBB, [0x19])
        self._cmd(0xC0, [0x2C])
        self._cmd(0xC2, [0x01])
        self._cmd(0xC3, [0x12])
        self._cmd(0xC4, [0x20])
        self._cmd(0xC6, [0x0F])
        self._cmd(0xD0, [0xA4, 0xA1])
        self._cmd(0xE0, [0xD0, 0x04, 0x0D, 0x11, 0x13, 0x2B, 0x3F, 0x54, 0x4C, 0x18, 0x0D, 0x0B, 0x1F, 0x23])
        self._cmd(0xE1, [0xD0, 0x04, 0x0C, 0x11, 0x13, 0x2C, 0x3F, 0x44, 0x51, 0x2F, 0x1F, 0x1F, 0x20, 0x23])
        self._cmd(0x21)                # inversion on
        self._cmd(0x11)                # sleep out
        time.sleep_ms(120)
        self._cmd(0x29)                # display on

    def _init_build1(self):
        """A bare ST7789 (build1, the Feather): its own power-on defaults, as bench1.py's Screen."""
        self.rst(1); time.sleep_ms(10); self.rst(0); time.sleep_ms(20); self.rst(1); time.sleep_ms(150)
        self._cmd(0x01)                # software reset
        time.sleep_ms(150)
        self._cmd(0x11)                # sleep out
        time.sleep_ms(120)
        self._cmd(0x3A, [0x55])        # 16-bit color
        self._cmd(0x36, [board.MADCTL])
        self._cmd(0x21)                # inversion on (IPS)
        self._cmd(0x13)                # normal display mode
        self._cmd(0x29)                # display on
        time.sleep_ms(20)
        if (board.PANEL_W, board.PANEL_H) != (W, H):
            self._clear_panel()

    def _clear_panel(self):
        """Black over the whole panel, margins included, from the buffer while it is still all zeros."""
        n = board.PANEL_W * board.PANEL_H * 2
        self._window(0, 0, board.PANEL_W, board.PANEL_H)
        self.dc(1); self.cs(0)
        mv = memoryview(self.buffer)
        while n > 0:
            k = min(n, len(mv))
            self.spi.write(mv[:k])
            n -= k
        self.cs(1)

    def _window(self, x, y, w, h):
        x, y = x + board.RAM_X, y + board.RAM_Y      # the Feather's panel starts at (40, 53) in RAM
        self._cmd(0x2A, [x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF])
        self._cmd(0x2B, [y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF])
        self._cmd(0x2C)

    def frames(self, draw, *args, rows=None):
        """Run draw(*args) once per band; draw ends with show() as always. One band: just once.
        rows, [(y0, y1), ...] in screen rows: only the bands they touch; the rest of the panel keeps
        what it shows (a knob turn that moved the focus, quorum.turned)."""
        if BANDS == 1:
            return draw(*args)
        try:
            for y0 in range(0, H, BAND_H):
                if rows and not any(a < y0 + BAND_H and b > y0 for a, b in rows):
                    continue
                self.y0 = y0
                draw(*args)
        finally:
            self.y0 = 0

    def show(self):
        self._window(board.X_OFF, board.Y_OFF + self.y0, W, BAND_H)
        self.dc(1); self.cs(0); self.spi.write(self.buffer); self.cs(1)

    def big_text(self, s, x, y, c, scale=2):
        """framebuf's 8x8 font scaled up. Slow-ish, fine for a few words."""
        w = 8 * len(s)
        tmp = framebuf.FrameBuffer(bytearray(w * 8 // 8), w, 8, framebuf.MONO_HLSB)
        tmp.text(s, 0, 0, 1)
        for yy in range(8):
            for xx in range(w):
                if tmp.pixel(xx, yy):
                    self.fill_rect(x + xx * scale, y + yy * scale, scale, scale, c)

    def center_text(self, s, y, c, scale=1):
        x = (self.width - 8 * len(s) * scale) // 2
        if scale == 1:
            self.text(s, x, y, c)
        else:
            self.big_text(s, x, y, c, scale)


LONG_MS, REPEAT_MS = 1000, 500


class Keys:
    """Every key on the board by name. On build1 the knob adds "down"/"up" (a detent each way) and
    "press" (its push), and A/B/X/Y read high until they are wired. On the Feather (THREE), D1 is
    two keys: "D1" when it is let go within LONG_MS, "D1L" once it has been held that long, again
    every REPEAT_MS while it stays down."""

    def __init__(self):
        self.pins = {k: Pin(p, Pin.IN, Pin.PULL_DOWN if p in board.HIGH else Pin.PULL_UP) for k, p in KEYS.items()}
        self.down = {k: int(p in board.HIGH) for k, p in KEYS.items()}     # the level that means pressed
        self.last = {k: False for k in KEYS}
        self.long = "D1" if THREE else None
        self.since = self.next = 0
        self.knob = None
        if KNOB:
            import knob
            self.knob = knob.Knob()

    def pressed(self):
        """Names of keys that went down since the last call (D1 on the Feather: see the class)."""
        out = self.knob.pressed() if self.knob else []
        now = time.ticks_ms()
        for k, p in self.pins.items():
            v = p.value() == self.down[k]
            if k == self.long:
                if v and not self.last[k]:
                    self.since, self.next = now, LONG_MS
                elif v and time.ticks_diff(now, self.since) >= self.next:
                    out.append(k + "L")
                    self.next += REPEAT_MS
                elif not v and self.last[k] and self.next == LONG_MS:
                    out.append(k)
            elif v and not self.last[k]:
                out.append(k)
            self.last[k] = v
        return out

    def held(self, k):
        if self.knob and k == "press":
            return self.knob.held()
        return self.pins[k].value() == self.down[k]


class BandLCD(LCD):
    """LCD for board.BANDS > 1: every call takes screen coordinates and lands in the current band.
    Anything wholly outside the band is skipped before framebuf sees it."""

    def _out(self, y, h):
        return y + h <= self.y0 or y >= self.y0 + BAND_H

    def fill(self, c):
        super().fill(c)

    def pixel(self, x, y, *c):
        return super().pixel(x, y - self.y0, *c)

    def hline(self, x, y, w, c):
        if not self._out(y, 1):
            super().hline(x, y - self.y0, w, c)

    def vline(self, x, y, h, c):
        if not self._out(y, h):
            super().vline(x, y - self.y0, h, c)

    def line(self, x0, y0, x1, y1, c):
        if not self._out(min(y0, y1), abs(y1 - y0) + 1):
            super().line(x0, y0 - self.y0, x1, y1 - self.y0, c)

    def rect(self, x, y, w, h, c, f=False):
        if not self._out(y, h):
            super().rect(x, y - self.y0, w, h, c, f)

    def fill_rect(self, x, y, w, h, c):
        if not self._out(y, h):
            super().fill_rect(x, y - self.y0, w, h, c)

    def text(self, s, x, y, c=1):
        if not self._out(y, 8):
            super().text(s, x, y - self.y0, c)

    def ellipse(self, x, y, xr, yr, c, f=False, m=15):
        if not self._out(y - yr, 2 * yr + 1):
            super().ellipse(x, y - self.y0, xr, yr, c, f, m)

    def poly(self, x, y, coords, c, f=False):
        super().poly(x, y - self.y0, coords, c, f)

    def blit(self, fb, x, y, key=-1, palette=None):
        super().blit(fb, x, y - self.y0, key, palette)


if BANDS > 1:
    LCD = BandLCD
