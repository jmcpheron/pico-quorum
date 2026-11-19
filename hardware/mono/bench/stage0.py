# Mono bring-up: the first program on a new board, on the stock Pico 2 MicroPython. It is console-rp's
# stage0.py (../../console-rp/bench/) on the same pins, with what Mono adds: KEY 2's switch and bus,
# and the facts sent again when the computer asks, since Mono has no RESET button to start it over.
# One file and nothing else. It changes nothing on the key: it reads its revision and its config
# zone, nothing more.
#   - the screen: a 1-pixel white frame round the edge (a side missing means the RAM offset is
#     wrong), red/green/blue swatches (swapped means BGR), and which way is up
#   - D0 D1 D2: a box for each along the bottom, lit while held, with a count
#   - the red LED on GPIO25: blinks at start, then follows any key
#   - the RP2350: the board MicroPython says it is, the clock, free RAM, the unique id
#   - the key on I2C0 (GPIO4/5): the bus scan, the ATECC608's revision and serial, its two locks
#   - KEY 2, nothing fitted: its supply (VKEY) off, then on by GPIO7, read through its bus's pull-ups,
#     which go to VKEY alone (R17, R18): both low when off, both high when on. Then I2C1's scan
#     (GPIO14/15), which should find nothing. It is left off.
#   - the link: a line on UART1 (GPIO20/21, to the CH343P and the USB-C) every 2 s, and what comes
#     back. A line holding `facts` is answered with every fact again (check.py asks).
# All three keys held for 1 s turns the picture over (MADCTL 0x60 <-> 0xA0).
#
# Load it over SWD through the jig's pads (BRINGUP.md), from the repository's root:
#   swdload.py RPI_PICO2-20250911-v1.26.1.uf2 main.py=hardware/mono/bench/stage0.py
# It then runs at every power-up from the USB-C.
import sys
import os
import gc
import time
import struct
import machine
import framebuf
from machine import Pin, SPI, I2C, UART

W, H = 240, 135
TURNS = ((0x60, 40, 53), (0xA0, 40, 52))    # (MADCTL, column, row) of the 135x240 window in the ST7789's RAM
turn = 0

# ----------------------------------------------------------------------------- the screen (PINS.md)
_bl = Pin(13, Pin.OUT, value=0)
_cs, _dc, _rst = Pin(9, Pin.OUT, value=1), Pin(8, Pin.OUT, value=1), Pin(12, Pin.OUT, value=1)
_spi = SPI(1, baudrate=24_000_000, sck=Pin(10), mosi=Pin(11), miso=None)     # no MISO: SPI1's default is GPIO8, the DC line
_dc.init(Pin.OUT, value=1)              # and DC back as an output after the SPI, should a port take it anyway


def _cmd(c, data=None):
    _cs(0); _dc(0); _spi.write(bytes([c]))
    if data:
        _dc(1); _spi.write(data)
    _cs(1)


def panel():
    _rst(0); time.sleep_ms(20); _rst(1); time.sleep_ms(150)
    _cmd(0x01); time.sleep_ms(150)      # software reset
    _cmd(0x11); time.sleep_ms(120)      # out of sleep
    _cmd(0x3A, b"\x55")                 # 16 bits a pixel
    _cmd(0x36, bytes([TURNS[turn][0]]))
    _cmd(0x21)                          # inversion on: an IPS panel
    _cmd(0x13); _cmd(0x29); time.sleep_ms(20)
    _bl(1)


buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)


def rgb(r, g, b):                       # big-endian RGB565, as the panel wants it
    v = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
    return (v & 0xFF) << 8 | v >> 8


BLACK, WHITE, GREY, DIM = rgb(0, 0, 0), rgb(255, 255, 255), rgb(150, 150, 150), rgb(40, 44, 52)
RED, GREEN, BLUE = rgb(255, 0, 0), rgb(0, 255, 0), rgb(0, 0, 255)
CYAN, YELLOW, BAD = rgb(0, 229, 255), rgb(250, 220, 60), rgb(255, 90, 70)


def show():
    _, x, y = TURNS[turn]
    _cmd(0x2A, struct.pack(">HH", x, x + W - 1))
    _cmd(0x2B, struct.pack(">HH", y, y + H - 1))
    _cmd(0x2C, buf)


# ----------------------------------------------------------------------------- keys, LED, link
NAMES = ("D0", "D1", "D2")
keys = [Pin(n, Pin.IN, Pin.PULL_UP) for n in (2, 3, 6)]    # to GND, pressed low (no pull-downs: RP2350-E9)
counts = [0, 0, 0]
led = Pin(25, Pin.OUT, value=0)
sent = got = 0
heard = ""
tail = b""                              # the last bytes heard: `facts` may come in two reads
link = UART(1, 115200, tx=Pin(20), rx=Pin(21))


# ----------------------------------------------------------------------------- the key (read only)
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100_000)
WAKE_OK = b"\x04\x11\x33\x43"


def crc16(data):
    crc = 0
    for b in data:
        for shift in range(8):
            data_bit = (b >> shift) & 1
            crc_bit = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if data_bit != crc_bit:
                crc ^= 0x8005
    return bytes([crc & 0xFF, crc >> 8])


def wake():
    for _ in range(3):
        try:
            i2c.writeto(0, b"\x00")     # SDA low long enough to be the wake token
        except OSError:
            pass
        time.sleep_ms(3)
        try:
            if i2c.readfrom(0x60, 4) == WAKE_OK:
                return True
        except OSError:
            pass
        try:
            i2c.writeto(0x60, b"\x01")  # sleep, then try again
        except OSError:
            pass
        time.sleep_ms(10)
    return False


def command(op, p1, p2, n, wait_ms):
    """One command with no data: Info (0x30) or Read (0x02). -> its n bytes of answer."""
    pkt = bytes([7, op, p1]) + struct.pack("<H", p2)
    i2c.writeto(0x60, b"\x03" + pkt + crc16(pkt))
    time.sleep_ms(wait_ms)
    r = i2c.readfrom(0x60, n + 3)
    if r[0] != n + 3 or crc16(r[:-2]) != r[-2:]:
        raise OSError("bad answer %s" % r.hex())
    return r[1:-2]


# A fact is (line, mark): True as it should be, False a fault, None neither.
def key_facts():
    try:
        found = i2c.scan()
    except OSError as e:
        return [("I2C0: %r" % e, False)]
    out = [("I2C0: " + (" ".join("%02x" % a for a in found) or "nothing"), None)]
    if 0x60 not in found and not wake():
        return out + [("no ATECC608 at 60", False)]
    try:
        if not wake():
            return out + [("60 doesn't wake", False)]
        rev = command(0x30, 0x00, 0x0000, 4, 2)            # Info: revision
        b0 = command(0x02, 0x80, 0x0000, 32, 3)            # Read: config block 0
        b2 = command(0x02, 0x80, 0x0010, 32, 3)            # Read: config block 2 (the locks)
        i2c.writeto(0x60, b"\x01")
        serial = (b0[0:4] + b0[8:13]).hex()
        lock = lambda v: "locked" if v == 0x00 else "open" if v == 0x55 else "%02x" % v
        return out + [("ATECC608 rev %s" % rev.hex(), True), ("serial " + serial, None),
                      ("data %s, config %s" % (lock(b2[22]), lock(b2[23])), None)]
    except OSError as e:
        return out + [("key: %s" % e, False)]


# ----------------------------------------------------------------------------- KEY 2 (nothing fitted)
def key2_fact():
    """VKEY off, then on, each read on SDA2 and SCL2 with no pull of the RP2350's: R17 and R18 to VKEY
    are all that holds them, 5.3k to ground through the switch's 600 R when it is off (under the 8.2k
    RP2350-E9 asks for). Then I2C1's scan. Left off, GPIO7 an input again: R20 holds it low."""
    pins = lambda: "%d%d" % (Pin(14, Pin.IN, None).value(), Pin(15, Pin.IN, None).value())
    en = Pin(7, Pin.OUT, value=0)
    time.sleep_ms(30)                   # VKEY drains through the 600 R in a few milliseconds
    off = pins()
    en(1)
    time.sleep_ms(10)                   # the switch's rise: 1 ms at most
    on = pins()
    found = "not scanned"               # a stuck bus would take the scan a timeout at every address
    if on == "11":
        try:
            found = " ".join("%02x" % a for a in I2C(1, sda=Pin(14), scl=Pin(15), freq=100_000).scan()) or "empty"
        except OSError as e:
            found = "%r" % e
    en(0)
    for n in (14, 15, 7):
        Pin(n, Pin.IN, None)
    ok = off == "00" and on == "11"
    return ("KEY 2: off %s on %s, %s" % (off, on, found), False if not ok else True if found == "empty" else None)


# ----------------------------------------------------------------------------- what it is
def board_facts():
    try:
        name = os.uname().machine
    except AttributeError:
        name = sys.platform
    v = sys.implementation.version
    gc.collect()
    return [(name.replace("Raspberry Pi ", "").replace(" with ", ", ")[:29], None),
            ("MicroPython %d.%d.%d" % v[:3], None),
            ("%d MHz, %d KB free" % (machine.freq() // 1_000_000, gc.mem_free() // 1024), None),
            ("id " + machine.unique_id().hex(), None)]


def tell(facts):
    """Every fact down the link, a fault as `FAIL:`, then how many: check.py reads up to that line."""
    for line, mark in facts:
        link.write("%s %s\r\n" % ("FAIL:" if mark is False else "fact:", line))
    link.write("facts: %d\r\n" % len(facts))


# ----------------------------------------------------------------------------- the picture
def draw(facts, down):
    fb.fill(BLACK)
    fb.rect(0, 0, W, H, WHITE)                          # each edge one pixel in: all four should show
    fb.fill_rect(1, 1, W - 2, 12, DIM)
    fb.text("Mono bring-up", 4, 3, WHITE)
    fb.text("^ up", W - 70, 3, YELLOW)
    for i, (c, n) in enumerate(((RED, "R"), (GREEN, "G"), (BLUE, "B"))):
        fb.fill_rect(W - 28 + i * 9, 3, 8, 8, c)
    y = 15
    for line, mark in facts:
        fb.text(line[:29], 4, y, GREEN if mark else BAD if mark is False else WHITE)
        y += 9
    fb.text(("link: %d out, %d in %s" % (sent, got, heard))[:29], 4, y, CYAN)
    bw = (W - 4 * 4) // 3                              # D0 D1 D2 in a row, as on the board
    for i in range(3):
        x = 4 + i * (bw + 4)
        if down[i]:
            fb.fill_rect(x, H - 22, bw, 18, GREEN)
        else:
            fb.rect(x, H - 22, bw, 18, GREY)
        fb.text("%s %d" % (NAMES[i], counts[i]), x + 6, H - 17, BLACK if down[i] else WHITE)
    show()


def main():
    global turn, sent, got, heard, tail
    panel()
    for _ in range(3):
        led(1); time.sleep_ms(120); led(0); time.sleep_ms(120)
    facts = board_facts() + key_facts() + [key2_fact()]
    print("Mono bring-up")
    for line, mark in facts:
        print("  " + line + ("   <- FAIL" if mark is False else ""))
    tell(facts)
    prev = [False] * 3
    all_since = None
    t_link = time.ticks_ms()
    dirty = True
    while True:
        now = time.ticks_ms()
        down = [p() == 0 for p in keys]
        for i in range(3):
            if down[i] and not prev[i]:
                counts[i] += 1
                print("%s pressed (%d)" % (NAMES[i], counts[i]))
        if down != prev:
            dirty = True
        led(1 if any(down) else 0)
        if all(down):
            if all_since is None:
                all_since = now
            elif time.ticks_diff(now, all_since) > 1000:
                turn, all_since = 1 - turn, None
                _cmd(0x36, bytes([TURNS[turn][0]]))
                print("turned over: MADCTL 0x%02x" % TURNS[turn][0])
                dirty = True
        else:
            all_since = None
        if time.ticks_diff(now, t_link) >= 2000:
            t_link = now
            sent += 1
            link.write("Mono bring-up %d: D0 %d D1 %d D2 %d\r\n" % (sent, counts[0], counts[1], counts[2]))
            dirty = True
        n = link.any()
        if n:
            data = link.read(n)
            got += len(data)
            heard = "".join(chr(c) if 32 <= c < 127 else "." for c in data)[-12:]
            tail = (tail + data)[-16:]
            if b"facts" in tail:
                tail = b""
                tell(facts)
            else:
                link.write(b"heard: " + data + b"\r\n")
            print("link heard %r" % data)
            dirty = True
        if dirty:
            draw(facts, down)
            dirty = False
        prev = down
        time.sleep_ms(20)


main()
