"""picoquorum-key rev B smoke test. MicroPython 1.26.x, ESP32_GENERIC_S3.

Run with:  mpremote run firmware/smoke/smoke.py

Exercises every part on the board once: backlight switch, ST7789 panel, the three rail buttons,
the status LED, the I2C bus and the ATECC608C's public serial number, and the key port: its CC
line, the key's power and LED, its own bus and a key-c's serial.
It signs nothing and reads no key (spec rule 3). No driver libraries needed.
"""
import time
from machine import Pin, SPI, I2C, PWM

# --- picoquorum-key profile (docs/PINS.md) -----------------------------------------------------
SCK, MOSI, CS, DC, RST, BL = 12, 11, 10, 9, 14, 21
BUTTONS = (("D0 Reject", 42), ("D1 Next", 41), ("D2 Sign", 40))
SDA, SCL, LED = 16, 17, 48
KEY_ADDR = 0x60
# the key port (rev B): its own bus, I2C(1)
KEY2_SDA, KEY2_SCL, KEY_CC, KEY_EN = 38, 39, 1, 2
# screen geometry (docs/SPEC.md): 240 x 135 landscape, offsets 40/53, MADCTL 0x60, inverted
W, H, XOFF, YOFF, MADCTL = 240, 135, 40, 53, 0x60
RAIL_Y = (7, 67, 127)

RED, GREEN, BLUE, WHITE, BLACK = 0xF800, 0x07E0, 0x001F, 0xFFFF, 0x0000


def log(*a):
    print("[smoke]", *a)


# --- ST7789 ---------------------------------------------------------------------------------
class ST7789:
    def __init__(self):
        self.spi = SPI(1, baudrate=20_000_000, sck=Pin(SCK), mosi=Pin(MOSI))
        self.cs = Pin(CS, Pin.OUT, value=1)
        self.dc = Pin(DC, Pin.OUT, value=0)
        self.rst = Pin(RST, Pin.OUT, value=1)

    def cmd(self, c, data=b""):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([c]))
        if data:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def init(self):
        self.rst(0); time.sleep_ms(20); self.rst(1); time.sleep_ms(120)
        self.cmd(0x01); time.sleep_ms(150)          # SWRESET
        self.cmd(0x11); time.sleep_ms(120)          # SLPOUT
        self.cmd(0x3A, b"\x55")                     # COLMOD 16-bit
        self.cmd(0x36, bytes([MADCTL]))             # MADCTL landscape
        self.cmd(0x21)                              # INVON
        self.cmd(0x13)                              # NORON
        self.cmd(0x29); time.sleep_ms(20)           # DISPON

    def window(self, x, y, w, h):
        x0, x1 = x + XOFF, x + XOFF + w - 1
        y0, y1 = y + YOFF, y + YOFF + h - 1
        self.cmd(0x2A, bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self.cmd(0x2B, bytes([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self.cmd(0x2C)

    def fill_rect(self, x, y, w, h, color):
        self.window(x, y, w, h)
        row = bytes([color >> 8, color & 0xFF]) * w
        self.cs(0); self.dc(1)
        for _ in range(h):
            self.spi.write(row)
        self.cs(1)

    # 5x7 glyphs for the few characters the banner needs
    FONT = {
        "c": (0x3E, 0x41, 0x41, 0x41, 0x22), "o": (0x38, 0x44, 0x44, 0x44, 0x38),
        "n": (0x7C, 0x08, 0x04, 0x04, 0x78), "s": (0x48, 0x54, 0x54, 0x54, 0x20),
        "l": (0x00, 0x41, 0x7F, 0x40, 0x00), "e": (0x38, 0x54, 0x54, 0x54, 0x18),
        "-": (0x08, 0x08, 0x08, 0x08, 0x08), "3": (0x21, 0x41, 0x45, 0x4B, 0x31),
        " ": (0, 0, 0, 0, 0),
    }

    def text(self, s, x, y, color, scale=3):
        for ch in s:
            cols = self.FONT.get(ch, self.FONT[" "])
            for cx, bits in enumerate(cols):
                for cy in range(7):
                    if bits >> cy & 1:
                        self.fill_rect(x + cx * scale, y + cy * scale, scale, scale, color)
            x += 6 * scale


# --- ATECC608: wake, read the serial number, idle ----------------------------------------------
def atecc_crc(data):
    crc = 0
    for b in data:
        for s in range(8):
            data_bit = (b >> s) & 1
            crc_bit = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if data_bit != crc_bit:
                crc ^= 0x8005
    return bytes([crc & 0xFF, crc >> 8])


def atecc_wake(i2c):
    # SDA held low >= 60 us: a 0x00 byte to address 0 at 100 kHz does it. The NACK is expected.
    try:
        i2c.writeto(0x00, b"\x00")
    except OSError:
        pass
    time.sleep_ms(2)
    r = i2c.readfrom(KEY_ADDR, 4)
    return r == b"\x04\x11\x33\x43"


def atecc_read_word(i2c, zone, addr):
    body = bytes([7, 0x02, zone, addr & 0xFF, addr >> 8])   # count, Read, param1, param2
    i2c.writeto(KEY_ADDR, b"\x03" + body + atecc_crc(body))
    time.sleep_ms(2)
    r = i2c.readfrom(KEY_ADDR, 7)
    if r[0] != 7 or atecc_crc(r[:5]) != r[5:7]:
        raise OSError("bad response %s" % r.hex())
    return r[1:5]


def atecc_serial(i2c):
    if not atecc_wake(i2c):
        raise OSError("no wake token from 0x60")
    w0 = atecc_read_word(i2c, 0x00, 0)      # config bytes 0-3
    w2 = atecc_read_word(i2c, 0x00, 2)      # config bytes 8-11
    w3 = atecc_read_word(i2c, 0x00, 3)      # config bytes 12-15
    i2c.writeto(KEY_ADDR, b"\x02")          # idle
    return w0 + w2 + w3[:1]                 # SN[0:4] + SN[8:13]


# --- the key port -----------------------------------------------------------------------------
def key_port():
    """CC, then power, the LED and the second bus. Returns the EN pin, or None with no key in."""
    cc = Pin(KEY_CC, Pin.IN)            # R17 pulls it up; the S3's own pull-up would lift a key's low to ~0.7 V
    en = Pin(KEY_EN, Pin.OUT, value=0)
    log("key port: CC reads", cc(), "(1: no key, or a board without the port; 0: a key-c in)")
    if cc():
        return None
    en(1)
    time.sleep_ms(20)
    log("key port: VKEY on; the port's LED (D4) and a key-c P3's own should be lit")
    i2c1 = I2C(1, scl=Pin(KEY2_SCL), sda=Pin(KEY2_SDA), freq=100_000)
    try:
        atecc_wake(i2c1)
    except OSError:
        pass
    log("key port i2c(1) scan:", [hex(a) for a in i2c1.scan()], "(expect ['0x60'] only)")
    try:
        sn = atecc_serial(i2c1)
        log("key-c serial:", " ".join("%02X" % b for b in sn), "(not the soldered chip's)")
    except OSError as e:
        log("key-c FAILED:", e)
    return en


# --- the test ---------------------------------------------------------------------------------
def main():
    led = Pin(LED, Pin.OUT, value=0)
    bl = PWM(Pin(BL), freq=1000, duty_u16=0)
    log("backlight should be OFF now; waiting 1 s")
    time.sleep(1)

    lcd = ST7789()
    lcd.init()
    lcd.fill_rect(0, 0, W, 45, RED)
    lcd.fill_rect(0, 45, W, 45, GREEN)
    lcd.fill_rect(0, 90, W, 45, BLUE)
    bl.duty_u16(65535)
    log("backlight ON, three bands: red top, green, blue bottom")
    time.sleep(1.5)
    bl.duty_u16(65535 // 4)
    log("backlight at 25 %")
    time.sleep(0.7)
    bl.duty_u16(65535)

    lcd.fill_rect(0, 0, W, H, BLACK)
    lcd.text("picoquorum-key", 24, 54, WHITE)
    for y in RAIL_Y:                                   # rail ticks, left edge
        lcd.fill_rect(0, max(0, y - 2), 12, 5, WHITE)
    log("banner upright? buttons on the LEFT, level with the three ticks?")

    i2c = I2C(0, scl=Pin(SCL), sda=Pin(SDA), freq=100_000)
    try:
        atecc_wake(i2c)                     # the ATECC ignores the bus while asleep, so wake it for the scan
    except OSError:
        pass
    found = [hex(a) for a in i2c.scan()]
    log("i2c scan:", found, "(expect ['0x60'] only)")
    try:
        sn = atecc_serial(i2c)
        log("ATECC608 serial:", " ".join("%02X" % b for b in sn),
            "(expect 9 bytes, starts 01 23, ends EE)")
    except OSError as e:
        log("ATECC608 FAILED:", e)

    key_port()
    try:
        atecc_wake(i2c)                     # U2 went idle after its serial; wake it to see it again
    except OSError:
        pass
    log("i2c(0) scan again:", [hex(a) for a in i2c.scan()], "(still ['0x60'] only: the buses are apart)")
    try:
        i2c.writeto(KEY_ADDR, b"\x02")      # idle
    except OSError:
        pass

    buttons = [(name, Pin(n, Pin.IN, Pin.PULL_UP)) for name, n in BUTTONS]
    log("press each button; Ctrl-C to stop. LED blinks at 2 Hz.")
    was = {name: 1 for name, _ in buttons}
    t = time.ticks_ms()
    while True:
        for i, (name, pin) in enumerate(buttons):
            v = pin()
            if v != was[name]:
                was[name] = v
                if v == 0:
                    log("pressed:", name)
                    if i < 3:
                        lcd.fill_rect(0, max(0, RAIL_Y[i] - 2), 12, 5, GREEN)
                else:
                    if i < 3:
                        lcd.fill_rect(0, max(0, RAIL_Y[i] - 2), 12, 5, WHITE)
        if time.ticks_diff(time.ticks_ms(), t) >= 250:
            t = time.ticks_ms()
            led(not led())
        time.sleep_ms(10)


main()
