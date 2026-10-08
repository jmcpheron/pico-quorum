# The EC11 knob (board.py "build1" and "esp32"): the same pressed()/held() shape as lcd.Keys, so
# the apps read it like keys. One detent clockwise is "down" (next), anticlockwise "up"; the push
# is "press".
# Quadrature on edge interrupts on both pins, as in bench1.py, so no step is lost between polls.
# The interrupts are hard: a soft one waits behind the UI tick (a redraw is 8 bands of Python plus
# SPI) and reads the pins only when it finally runs, so the edges in between were lost and the knob
# felt slow. A hard handler reads the pins at the edge. It must not allocate: small ints only.
# The ESP32 has no hard pin interrupts in MicroPython; its pulse counter (machine.Encoder, the PCNT)
# counts the same quadrature steps in hardware instead, with the same sign, so no edge is lost
# there either. Its glitch filter drops pulses under 10 us.
import time
import machine
from machine import Pin
import board

STEPS_PER_CLICK = 4     # most EC11s: 4 quadrature steps per detent. Two events per click -> 2
DEBOUNCE_MS = 20
FILTER_NS = 10_000      # ESP32 only: the counter's filter, at most 12.8 us
_QUAD = (0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0)


class Knob:
    def __init__(self):
        self.a = Pin(board.ENC_A, Pin.IN, Pin.PULL_UP)
        self.b = Pin(board.ENC_B, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(board.ENC_SW, Pin.IN, Pin.PULL_UP)
        self.state = (self.a.value() << 1) | self.b.value()
        self.steps = 0          # quadrature steps not yet handed out as clicks
        self.down = False       # the push, debounced
        self.since = time.ticks_ms()
        self.enc = None
        if board.ESP32:
            self.enc = machine.Encoder(0, self.a, self.b, phases=4, filter_ns=FILTER_NS)
            return
        self.a.irq(self._edge, Pin.IRQ_RISING | Pin.IRQ_FALLING, hard=True)
        self.b.irq(self._edge, Pin.IRQ_RISING | Pin.IRQ_FALLING, hard=True)

    def _edge(self, _):
        s = (self.a.value() << 1) | self.b.value()
        self.steps += _QUAD[(self.state << 2) | s]
        self.state = s

    def pressed(self):
        """"down"/"up" once per detent turned since the last call, then "press" if the push went down."""
        out = []
        if self.enc:
            self.steps += self.enc.value(0)     # read and zeroed in one call; no interrupt touches steps here
        irq = machine.disable_irq()
        n = int(self.steps / STEPS_PER_CLICK)
        self.steps -= n * STEPS_PER_CLICK
        machine.enable_irq(irq)
        out.extend(["down"] * n if n > 0 else ["up"] * -n)
        now = time.ticks_ms()
        v = self.sw.value() == 0
        if v != self.down and time.ticks_diff(now, self.since) >= DEBOUNCE_MS:
            self.down, self.since = v, now
            if v:
                out.append("press")
        return out

    def pending(self):
        """A detent turned or the push down, not yet read: quorum.poll stops between calls for it."""
        s = self.steps + (self.enc.value() if self.enc else 0)
        return s >= STEPS_PER_CLICK or s <= -STEPS_PER_CLICK or self.sw.value() == 0

    def held(self):
        return self.sw.value() == 0
