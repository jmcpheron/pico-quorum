"""A digital twin of picoquorum-key for running the real MicroPython firmware under CPython.

The fake `machine` and `time` modules are wired through the board's pad nets, not through the
firmware's own constants: GPIO n reaches module pin p (KiCad's symbol), p sits on a net (the PCB),
and a peripheral sees a signal only if its pad is on that same net. A miswired board therefore
behaves wrongly here the way it would on the bench.

Modelled: buttons (pull-up, pressed to ground), the ST7789 panel behind the 8-pin connector (init
commands and RAM writes), the backlight and LED drive chains (topology only; the analog is in
test_spice), and an ATECC608 on I2C (asleep until woken). Time is virtual: sleeps advance a clock,
and a KeyboardInterrupt ends smoke.py's endless loop.
"""
import sys
import types

import common

PANEL_PINS = ("LEDA", "GND", "RESET", "RS", "SDA", "SCL", "VDD", "CS")   # panel pin 1..8 (DESIGN.md)


class Atecc:
    SERIAL_CONFIG = bytes.fromhex("0123 1234 00006003 56789abc EE 00 C0 00".replace(" ", ""))   # 16 config bytes

    def __init__(self, acks_scan_while_asleep=False):
        self.awake = False
        self.response = b""
        self.acks_scan_while_asleep = acks_scan_while_asleep

    @staticmethod
    def crc(data):
        crc = 0
        for b in data:
            for s in range(8):
                bit = (b >> s) & 1
                top = (crc >> 15) & 1
                crc = (crc << 1) & 0xFFFF
                if bit != top:
                    crc ^= 0x8005
        return bytes([crc & 0xFF, crc >> 8])

    def wake(self):
        self.awake = True
        self.response = bytes.fromhex("04113343")      # wake token

    def write(self, buf):
        if not self.awake:
            raise OSError(19)
        if buf[:1] == b"\x02":                      # idle
            self.awake, self.response = False, b""
        elif buf[:1] == b"\x03" and buf[2] == 0x02:  # command, Read opcode
            assert self.crc(buf[1:-2]) == buf[-2:], "bad command CRC from the firmware"
            zone, addr = buf[3], buf[4] | buf[5] << 8
            assert zone == 0, "twin only models the config zone"
            word = self.SERIAL_CONFIG[addr * 4:addr * 4 + 4]
            body = bytes([7]) + word
            self.response = body + self.crc(body)

    def read(self, n):
        if not self.awake:
            raise OSError(19)
        out, self.response = self.response[:n], self.response[n:]
        return out


class Panel:
    """ST7789 behind J2: decodes commands and RAM writes, only while powered and wired up."""

    def __init__(self):
        self.cmds = []
        self.colmod = self.madctl = None
        self.ram = {}
        self.window = [0, 239, 0, 134]
        self.cmd = None
        self.args = []
        self.cursor = None
        self.half = None

    def byte(self, is_data, b):
        if not is_data:
            self.cmd, self.args, self.half = b, [], None
            self.cmds.append(b)
            if b == 0x2C:
                self.cursor = [self.window[0], self.window[2]]
            return
        if self.cmd == 0x2A and len(self.args) < 4:
            self.args.append(b)
            if len(self.args) == 4:
                self.window[0:2] = [self.args[0] << 8 | self.args[1], self.args[2] << 8 | self.args[3]]
        elif self.cmd == 0x2B and len(self.args) < 4:
            self.args.append(b)
            if len(self.args) == 4:
                self.window[2:4] = [self.args[0] << 8 | self.args[1], self.args[2] << 8 | self.args[3]]
        elif self.cmd == 0x36:
            self.madctl = b
        elif self.cmd == 0x3A:
            self.colmod = b
        elif self.cmd == 0x2C:
            if self.half is None:
                self.half = b
            else:
                x0, x1, y0, y1 = self.window
                self.ram[tuple(self.cursor)] = self.half << 8 | b
                self.half = None
                self.cursor[0] += 1
                if self.cursor[0] > x1:
                    self.cursor[0], self.cursor[1] = x0, self.cursor[1] + 1 if self.cursor[1] < y1 else y0


class World:
    def __init__(self, pad_nets, acks_scan_while_asleep=False):
        self.nets = pad_nets
        self.t_ms = 0
        self.events = []                  # (t_ms, callable) sorted on use
        self.pressed = set()
        self.pins = []
        self.panel = Panel()
        self.atecc = Atecc(acks_scan_while_asleep)
        self.pwm_events = []              # (t_ms, net, duty, lit)
        self.led_events = []
        self.first_light_ram = None
        self.stop_at_ms = 12_000

    # --- board lookups -------------------------------------------------------------------------
    def net(self, ref, pad):
        return self.nets.get((ref, str(pad)), "")

    def gpio_net(self, gpio):
        return self.net("U1", common.pin_of_gpio(gpio))

    def panel_net(self, name):
        return self.net("J2", 9 - (PANEL_PINS.index(name) + 1))     # panel pin k sits on J2 pad 9 - k

    def level(self, net):
        """Logic level on a net: a driving output pin wins; else a resistor to 3V3 reads high; else None."""
        if not net or common.is_nc(net):
            return None
        for p in self.pins:
            if p.mode == Pin.OUT and p.net == net:
                return p.val
        for (ref, pad), n in self.nets.items():
            if ref.startswith("R") and n == net:
                other = self.net(ref, "2" if pad == "1" else "1")
                if other == "+3V3":
                    return 1
        return None

    def pulled_low_by_switch(self, net):
        for ref in self.pressed:
            a, b = self.net(ref, 1), self.net(ref, 2)
            if (a == net and b == "GND") or (b == net and a == "GND"):
                return True
        return False

    def panel_ready(self):
        return self.panel_net("VDD") == "+3V3" and self.panel_net("GND") == "GND"

    def has_pullup(self, net):
        return any(ref.startswith("R") and n == net and self.net(ref, "2" if pad == "1" else "1") == "+3V3"
                   for (ref, pad), n in self.nets.items())

    def backlight_chain_ok(self, gpio_net):
        """GPIO -> R9 -> Q2 base; Q2 collector -> Q1 gate; Q1 drain -> R11 -> panel LEDA; Q2 emitter, panel GND on ground."""
        n = self.net
        return (gpio_net and gpio_net == n("R9", 1) and n("R9", 2) == n("Q2", 1) and n("Q2", 2) == "GND"
                and n("Q2", 3) == n("Q1", 1) and n("Q1", 2) == "+5V" and n("Q1", 3) == n("R11", 1)
                and n("R11", 2) == self.panel_net("LEDA") and self.panel_net("GND") == "GND")

    def led_chain_ok(self, gpio_net):
        n = self.net
        return gpio_net and gpio_net == n("R8", 1) and n("R8", 2) == n("D1", 2) and n("D1", 1) == "GND"

    # --- virtual time ----------------------------------------------------------------------------
    def sleep_ms(self, ms):
        end = self.t_ms + ms
        for t, fn in sorted(self.events, key=lambda e: e[0]):
            if self.t_ms <= t < end:
                self.t_ms = t
                fn(self)
        self.events = [e for e in self.events if e[0] >= end]
        self.t_ms = end
        if self.t_ms >= self.stop_at_ms:
            raise KeyboardInterrupt

    def at(self, seconds, fn):
        self.events.append((int(seconds * 1000), fn))


class Pin:
    IN, OUT, PULL_UP, PULL_DOWN = 0, 1, 2, 3
    world = None

    def __init__(self, gpio, mode=IN, pull=None, value=None):
        self.gpio, self.mode, self.pull, self.val = gpio, mode, pull, 0 if value is None else value
        self.net = self.world.gpio_net(gpio)
        self.world.pins.append(self)

    def __call__(self, v=None):
        if v is None:
            return self.value()
        self.val = int(bool(v))
        if self.net and self.world.led_chain_ok(self.net):
            self.world.led_events.append((self.world.t_ms, self.val))

    def value(self, v=None):
        if v is not None:
            self.val = int(bool(v))
            return None
        if self.mode == Pin.OUT:
            return self.val
        if self.world.pulled_low_by_switch(self.net):
            return 0
        return 1 if self.pull == Pin.PULL_UP else 0


class PWM:
    def __init__(self, pin, freq=1000, duty_u16=0):
        self.pin = pin
        self.duty_u16(duty_u16)

    def duty_u16(self, d=None):
        if d is None:
            return self.d
        self.d = d
        w = self.pin.world
        lit = bool(d) and bool(w.backlight_chain_ok(self.pin.net))
        w.pwm_events.append((w.t_ms, self.pin.net, d, lit))
        if lit and w.first_light_ram is None:
            w.first_light_ram = dict(w.panel.ram)


class SPI:
    def __init__(self, bus, baudrate=1_000_000, sck=None, mosi=None):
        self.sck, self.mosi, self.world = sck, mosi, sck.world

    def write(self, data):
        w = self.world
        if not w.panel_ready():
            return
        if self.sck.net != w.panel_net("SCL") or self.mosi.net != w.panel_net("SDA"):
            return                                           # clock or data never reach the panel
        if w.level(w.panel_net("CS")) != 0:
            return                                           # not selected (or CS not connected)
        dc = w.level(w.panel_net("RS"))
        if dc is None:
            return
        for b in data:
            w.panel.byte(bool(dc), b)


class I2C:
    def __init__(self, bus, scl=None, sda=None, freq=400_000):
        self.scl, self.sda, self.world = scl, sda, scl.world

    def present(self):
        w = self.world
        return (self.sda.net == w.net("U2", 5) and self.scl.net == w.net("U2", 6)
                and w.net("U2", 8) == "+3V3" and w.net("U2", 4) == "GND"
                and w.has_pullup(self.sda.net) and w.has_pullup(self.scl.net))

    def scan(self):
        if self.present() and (self.world.atecc.awake or self.world.atecc.acks_scan_while_asleep):
            return [0x60]
        return []

    def writeto(self, addr, buf):
        if addr == 0x00:                                    # wake: SDA low long enough
            if self.present():
                self.world.atecc.wake()
            raise OSError(19)                               # nothing ACKs address 0
        if addr != 0x60 or not self.present():
            raise OSError(19)
        self.world.atecc.write(bytes(buf))

    def readfrom(self, addr, n):
        if addr != 0x60 or not self.present():
            raise OSError(19)
        return self.world.atecc.read(n)


def install(world):
    """Put fake `machine` and `time` into sys.modules; return a function that restores the originals."""
    Pin.world = world
    machine = types.ModuleType("machine")
    machine.Pin, machine.SPI, machine.I2C, machine.PWM = Pin, SPI, I2C, PWM
    fake_time = types.ModuleType("time")
    fake_time.sleep_ms = world.sleep_ms
    fake_time.sleep = lambda s: world.sleep_ms(int(s * 1000))
    fake_time.ticks_ms = lambda: world.t_ms
    fake_time.ticks_diff = lambda a, b: a - b
    saved = {k: sys.modules.get(k) for k in ("machine", "time")}
    sys.modules["machine"], sys.modules["time"] = machine, fake_time

    def restore():
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return restore
