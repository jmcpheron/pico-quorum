# The board half of tools/board/newboard.py: a new ESP32-S3 board's parts, checked from RAM under bare
# MicroPython 1.26.x. It saves no file and changes nothing on either chip: the ATECC608 is asked only
# for its public serial number and lock bytes, which any caller may read. Each result is one line,
# "@ <check> ok|FAIL|info|look <detail>", for the laptop to tally; "~" lines are events.
# The laptop puts CFG = {...} in front of this file.
import sys, time, gc, esp, esp32, machine, framebuf
from machine import Pin, SPI, I2C, PWM

try:
    CFG
except NameError:
    CFG = {}
BUTTON_S, SOAK_S = CFG.get("buttons_s", 60), CFG.get("soak_s", 20)

# firmware/board.py's pins. Buttons are (name, GPIO, level when pressed). console-s3 uses the
# feather-s3 profile: D0 shares GPIO0 with BOOT, D1 and D2 are pulled down and pressed high.
PROFILES = {
    "picoquorum-key": dict(SCK=12, MOSI=11, CS=10, DC=9, RST=14, BL=21, SDA=16, SCL=17, LED=48,
                           BUTTONS=(("D0", 42, 0), ("D1", 41, 0), ("D2", 40, 0), ("BOOT", 0, 0))),
    "console-s3": dict(SCK=36, MOSI=35, CS=42, DC=40, RST=41, BL=45, SDA=3, SCL=4, LED=13,
                       BUTTONS=(("D0", 0, 0), ("D1", 1, 1), ("D2", 2, 1))),
}
W, H, XOFF, YOFF, MADCTL = 240, 135, 40, 53, 0x60
RAIL_Y = (7, 67, 127)
RESETS = {1: "power-on, RESET or brownout", 2: "hard", 3: "watchdog", 4: "deep sleep", 5: "soft"}
results = []


def res(name, status, detail=""):
    results.append((name, status))
    print("@ %s %s %s" % (name, status, detail))


def sw(c):              # framebuf keeps RGB565 little-endian; the ST7789 reads it big-endian
    return ((c & 0xFF) << 8) | (c >> 8)


RED, GREEN, BLUE, WHITE, BLACK = sw(0xF800), sw(0x07E0), sw(0x001F), 0xFFFF, 0
GREY, AMBER = sw(0x4208), sw(0xFD20)


def pulled_up(*pins):   # board.py's rule: high against the S3's own pull-down means a board pull-up
    ps = [Pin(n, Pin.IN, Pin.PULL_DOWN) for n in pins]
    time.sleep_us(100)
    up = all(p.value() for p in ps)
    for n in pins:
        Pin(n, Pin.IN, None)
    return up


# --- the screen ------------------------------------------------------------------------------
class Panel:
    def __init__(self, P):
        self.spi = SPI(1, baudrate=20_000_000, sck=Pin(P["SCK"]), mosi=Pin(P["MOSI"]))
        self.cs, self.dc = Pin(P["CS"], Pin.OUT, value=1), Pin(P["DC"], Pin.OUT, value=0)
        self.rst = Pin(P["RST"], Pin.OUT, value=1)
        self.buf = bytearray(W * H * 2)
        self.fb = framebuf.FrameBuffer(self.buf, W, H, framebuf.RGB565)

    def cmd(self, c, data=b""):
        self.cs(0); self.dc(0); self.spi.write(bytes([c]))
        if data:
            self.dc(1); self.spi.write(data)
        self.cs(1)

    def init(self):
        self.rst(0); time.sleep_ms(20); self.rst(1); time.sleep_ms(120)
        self.cmd(0x01); time.sleep_ms(150)          # SWRESET
        self.cmd(0x11); time.sleep_ms(120)          # SLPOUT
        self.cmd(0x3A, b"\x55")                     # 16-bit colour
        self.cmd(0x36, bytes([MADCTL]))             # landscape, buttons on the left
        self.cmd(0x21); self.cmd(0x13); self.cmd(0x29)

    def show(self):
        x0, x1, y0, y1 = XOFF, XOFF + W - 1, YOFF, YOFF + H - 1
        self.cmd(0x2A, bytes([x0 >> 8, x0 & 255, x1 >> 8, x1 & 255]))
        self.cmd(0x2B, bytes([y0 >> 8, y0 & 255, y1 >> 8, y1 & 255]))
        self.cmd(0x2C)
        self.cs(0); self.dc(1); self.spi.write(self.buf); self.cs(1)


# --- the ATECC608: wake, the public serial and lock bytes, idle ----------------------------------
def crc16(data):
    crc = 0
    for b in data:
        for s in range(8):
            fb = ((b >> s) & 1) ^ ((crc >> 15) & 1)
            crc = (crc << 1) & 0xFFFF
            if fb:
                crc ^= 0x8005
    return bytes([crc & 0xFF, crc >> 8])


def wake(i2c):
    try:
        i2c.writeto(0x00, b"\x00")          # SDA low long enough at 100 kHz; the NACK is expected
    except OSError:
        pass
    time.sleep_ms(2)


def read_word(i2c, word):                   # Read, config zone, 4 bytes
    body = bytes([7, 0x02, 0x00, word, 0])
    i2c.writeto(0x60, b"\x03" + body + crc16(body))
    time.sleep_ms(2)
    r = i2c.readfrom(0x60, 7)
    if r[0] != 7 or crc16(r[:5]) != r[5:7]:
        raise OSError("bad answer " + r.hex())
    return r[1:5]


def key_chip(P):
    sda, scl = Pin(P["SDA"], Pin.IN), Pin(P["SCL"], Pin.IN)
    if not (sda() and scl()):
        res("key-bus", "FAIL", "SDA reads %d, SCL %d with nothing driving them: a short to GND or "
            "a missing pull-up" % (sda(), scl()))
        return None
    i2c = I2C(0, scl=Pin(P["SCL"]), sda=Pin(P["SDA"]), freq=100_000)
    wake(i2c)
    found = i2c.scan()
    if 0x60 not in found:
        res("key-bus", "FAIL", "nothing at 0x60 (found %s): U2's joints, pin 1's way round, SDA/SCL"
            % [hex(a) for a in found])
        return None
    res("key-bus", "ok", "0x60" + ("" if found == [0x60] else ", and also %s" % [hex(a) for a in found if a != 0x60]))
    try:
        wake(i2c)
        if i2c.readfrom(0x60, 4) != b"\x04\x11\x33\x43":
            raise OSError("no wake token")
        w0, w2, w3, w21 = (read_word(i2c, n) for n in (0, 2, 3, 21))
        i2c.writeto(0x60, b"\x02")          # idle
    except OSError as e:
        res("key-chip", "FAIL", "answers at 0x60 but not cleanly: %s" % e)
        return None
    sn = w0 + w2 + w3[:1]
    good = sn[:2] == b"\x01\x23" and sn[8] == 0xEE
    res("key-chip", "ok" if good else "FAIL", "serial " + sn.hex() + ("" if good else " (expected 0123...ee)"))
    lk = {0x55: "unlocked", 0x00: "locked"}
    res("key-locks", "info", "config %s, data %s%s" % (lk.get(w21[3], hex(w21[3])), lk.get(w21[2], hex(w21[2])),
        " (factory fresh)" if w21[2] == w21[3] == 0x55 else ""))
    return sn.hex()


# --- the button tester -----------------------------------------------------------------------
def draw(lcd, name, btns, count, down, title, line2, serial):
    fb = lcd.fb
    fb.fill(BLACK)
    rails = [b for b in btns if b[0] != "BOOT"]
    for i, (n, g, lvl) in enumerate(rails):
        y = (0, 46, 92)[i]
        c = GREEN if down[n] else (GREY if count[n] else AMBER)
        fb.fill_rect(0, y, 64, 43, c)
        ty = RAIL_Y[i] - 3 if i else 4      # the name level with the button itself
        fb.text(n, 6, ty, BLACK)
        fb.text("x%d" % count[n], 30, ty, BLACK)
    fb.text(title, 72, 4, WHITE)
    fb.text(name, 72, 20, GREY)
    fb.text(line2, 72, 40, WHITE)
    if serial:
        fb.text("key " + serial[:8], 72, 60, GREY)
        fb.text("    " + serial[8:], 72, 70, GREY)
    if any(b[0] == "BOOT" for b in btns):
        fb.text("BOOT x%d" % count["BOOT"], 72, 90, GREEN if down["BOOT"] else WHITE)
    fb.text("amber: not yet", 72, 106, AMBER)
    fb.text("grey: seen", 72, 118, GREY)
    lcd.show()


def main():
    t0 = time.ticks_ms()
    name = CFG.get("board") or "auto"
    if name == "auto":
        name = "picoquorum-key" if pulled_up(16, 17) else "console-s3"
    P = PROFILES[name]
    res("board", "info", name + " pins")
    res("micropython", "info", sys.version.split("; ")[-1])
    res("reset-cause", "info", "%s, up %d ms" % (RESETS.get(machine.reset_cause(), machine.reset_cause()), t0))
    fl = esp.flash_size()
    res("flash", "ok" if fl == 8 * 1024 * 1024 else "FAIL", "%d MB (N8R2 has 8)" % (fl >> 20))
    gc.collect()
    free = gc.mem_free()
    res("psram", "ok" if free > 1_000_000 else "FAIL", "%d kB free on the heap (%s)" %
        (free >> 10, "the PSRAM is on it" if free > 1_000_000 else "no PSRAM: not an R2, or its joints"))
    res("temperature", "info", "%d C, the S3's own sensor" % esp32.mcu_temperature())

    btns = P["BUTTONS"]
    pins = [(n, Pin(g, Pin.IN, Pin.PULL_UP if lvl == 0 else Pin.PULL_DOWN), lvl) for n, g, lvl in btns]
    time.sleep_ms(5)
    stuck = [n for n, p, lvl in pins if p() == lvl]
    res("buttons-at-rest", "FAIL" if stuck else "ok", ("%s reads pressed with no hand on it: a bridge, "
        "or a button held" % ", ".join(stuck)) if stuck else "none reads pressed")

    serial = key_chip(P)

    led = Pin(P["LED"], Pin.OUT, value=0)
    bl = PWM(Pin(P["BL"]), freq=1000, duty_u16=0)
    lcd = Panel(P)
    lcd.init()
    fb = lcd.fb
    fb.fill_rect(0, 0, W, 45, RED); fb.fill_rect(0, 45, W, 45, GREEN); fb.fill_rect(0, 90, W, 45, BLUE)
    fb.text("TOP", 100, 18, WHITE)
    lcd.show()
    time.sleep(1)                           # drawn, backlight still off: the panel stays dark
    bl.duty_u16(65535)
    time.sleep(1.5)
    bl.duty_u16(65535 // 4)
    time.sleep(0.7)
    bl.duty_u16(65535)
    res("screen", "look", "dark 1 s, then red (TOP, upright) / green / blue bands, dimmed once, then "
        "the button tester: each box level with its button")

    count = {n: 0 for n, _, _ in pins}
    down = {n: False for n, _, _ in pins}
    alone = {n: False for n, _, _ in pins}      # seen pressed with no other button down: two that only
    together = {}                               # ever move as one are bridged, not pressed together
    phase, end = "buttons", time.ticks_add(time.ticks_ms(), BUTTON_S * 1000)
    title, beat, dirty = "press each", time.ticks_ms(), True
    while True:
        now = time.ticks_ms()
        for n, p, lvl in pins:
            d = p() == lvl
            if d != down[n]:
                time.sleep_ms(10)               # still so 10 ms later: a press, not a bounce
                if (p() == lvl) == d:
                    down[n], dirty = d, True
                    if d:
                        count[n] += 1
                    print("~ %s %s %d" % ("press" if d else "release", n, time.ticks_diff(now, t0)))
        held = [n for n, p, lvl in pins if p() == lvl]
        if len(held) == 1:
            alone[held[0]] = True
        elif len(held) > 1:
            together[" and ".join(held)] = 1
        if phase == "buttons" and all(alone.values()) and not any(down.values()):
            res("buttons", "ok", " ".join("%s x%d" % (n, count[n]) for n, _, _ in pins) + ", each alone")
            phase, end, title, dirty = "soak", time.ticks_add(now, SOAK_S * 1000), "watching", True
        elif time.ticks_diff(end, now) <= 0:
            if phase == "buttons":
                never = [n for n in count if not count[n]]
                stuck = [n for n in count if count[n] and not alone[n]]
                why = ["never pressed in %d s: %s" % (BUTTON_S, " ".join(never))] if never else []
                if stuck:
                    why.append("%s only read pressed with another button down (%s): bridged, at the "
                               "module's pins or the switches' tracks" % (" ".join(stuck), ", ".join(together)))
                res("buttons", "FAIL", "; ".join(why))
            res("soak", "ok", "%d s more on USB without a restart" % SOAK_S)
            break
        if time.ticks_diff(now, beat) >= 1000:
            beat = now
            led(not led())
            print(". %d" % time.ticks_diff(now, t0))
            dirty = True
        if dirty:
            left = max(0, time.ticks_diff(end, now) // 1000)
            draw(lcd, name, btns, count, down, title, ("%d s left" % left) if phase == "buttons"
                 else "for restarts %d s" % left, serial)
            dirty = False
        time.sleep_ms(5)

    fails = [n for n, s in results if s == "FAIL"]
    fb.fill(GREEN if not fails else RED)
    fb.text("PASS" if not fails else "FAIL", 100, 30, BLACK)
    for i, n in enumerate(fails[:6]):
        fb.text(n, 72, 54 + 12 * i, BLACK)
    fb.text("see the laptop", 64, 120, BLACK)
    lcd.show()
    led(0)
    print("@ done info %d ms" % time.ticks_diff(time.ticks_ms(), t0))


main()
