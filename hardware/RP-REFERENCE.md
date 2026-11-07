# The RP consoles: the parts every one has

*A reference, 2026-11-07. Drawn from [console-rp](console-rp/README.md) (five built, the first up on
the bench) and [Mono](mono/README.md) (routed, not ordered). It describes no one board: no pins, no
shape, no layout. Each board's own README has those.*

This is the family of consoles on a Raspberry Pi chip with no radio. Each is one board, soldered
by the factory: the chip and its circuit, a USB-C for power and a serial link, a 1.14″ screen,
three buttons, an ATECC608C that holds the key, and a site for a second key. A person programs it
through pads on the back. The computer on the cable relays the Safe's queue and has no say in what
gets signed.

```
   computer (the relay) ── USB-C ── USB serial bridge ── UART ── RP2350A ── I2C ── ATECC608C (the key that signs)
   power, and a serial line                                       │  │  │
   nothing else                                                   │  │  └─ I2C ── a second key's site, switched off
                                                                  │  └──── SPI ── the 1.14″ screen
                                                                  └─────── three buttons, an LED
   pads on the back, for a pogo jig: SWD, RUN, BOOT, the RP2350's own USB, 3V3, GND
```

## The parts

| block | part | why this one |
|---|---|---|
| the chip | RP2350A (QFN-60) | no radio on the chip, so nothing to keep switched off and no antenna. The stock MicroPython for the Pico 2 runs on it |
| its circuit | Raspberry Pi's minimal design: a 3.3 µH inductor (marked for polarity), a 12 MHz crystal (ABM8-272-T3) with its 15 pF and 1 kΩ, and a 100 nF at each power pin | Raspberry Pi says to copy their values and their layout round the chip, the inductor the right way round. Both boards do |
| the flash | W25Q128JV, 16 MB, QSPI | Basic at JLCPCB. The image uses 4 MB of it |
| power in | USB-C receptacle, 5.1 kΩ on CC1 and CC2, a USBLC6-2SC6 on D+ and D− | 5 V from any USB port; ESD at the connector |
| 3.3 V | an LDO from VBUS | a SOT-23 part (XC6206, 200 mA) ran warm on paper on console-rp, so Mono has a SOT-223 (LDL1117, 1.2 A) |
| the link | a USB serial bridge: CH343P (CDC-ACM, no driver needed) to one of the RP2350's UARTs | the only thing the USB-C's data lines reach ([below](#usb-power-and-a-serial-line-nothing-else)) |
| the key | ATECC608C-SSHDA-T (SOIC-8) on its own I2C bus, 4.7 kΩ pull-ups to 3.3 V | the SOIC because JLCPCB stocks it; it signs only the hash the console rebuilt |
| a second key's site | its own I2C bus; a current-limited load switch (AP22653) on its own supply, off at reset; pull-ups to that supply; ESD on its lines; footprints for an ATECC608C or an OPTIGA Trust M, and holes for a breakout | not fitted by default ([below](#a-second-key-swappable)) |
| the screen | the 8-pin 1.14″ 240 × 135 ST7789V panel, its ribbon in a 0.5 mm ZIF | fitted by hand. The backlight is switched by a transistor on a GPIO, pulled down so it is off at reset |
| buttons | three tactile switches, each to ground | the RP2350's own pull-ups, pressed low. No reset or BOOTSEL button: the jig has those |
| an LED | one, on a GPIO | for the bench |
| the jig's pads | 1.5 mm pads on the back at 2.54 mm: SWCLK, SWDIO, RUN, BOOT, D+, D−, 3V3, GND | programming by pogo pins ([below](#programming-by-pogo-pins)) |
| holes | M2 or M2.5, one near each corner | for the case, and to locate the jig |

Every part the factory fits sits on one side, so JLCPCB's one-sided assembly does the whole board
but the screen. console-rp's parts came to about $8.70 a board at one-piece prices and $6.60 at
100, with the panel about $2.50 more.

## The ideas every board keeps

### No radio

The RP2350A has none. The console reaches the world only through the cable it is powered by.

### USB: power and a serial line, nothing else

The RP2350's own USB carries MicroPython's REPL. From the REPL a program could make the key sign any
digest, or put the chip in its bootloader and write a new image. On a console that stays plugged
into a computer, that would hand the computer the key. So the separation is in the wiring:
- the USB-C's D+ and D− reach the ESD part and the serial bridge, and nothing else;
- the bridge's TX and RX reach a UART that MicroPython never puts its REPL on;
- the bridge's DTR and RTS go nowhere, so the computer can't reset the chip or hold BOOTSEL;
- the RP2350's own USB, SWD, RUN and BOOT reach only the pads on the back;
- no net but power and ground joins the USB-C to the RP2350.

Each board's generator reads KiCad's netlist back and stops if any of this isn't so. What goes over
the serial line, and why it never signs, is [docs/USB-LINK.md](../docs/USB-LINK.md).

### One key on one bus

The key that signs has an I2C bus to itself. Two ATECC608s can't share a bus, since both answer at
0x60, and a fault on another bus can't take this one down.

### A second key, swappable

The second site lets a board carry or take a second chip, soldered or on a breakout in its holes:
- its own I2C bus, for the same reasons as the first;
- its own supply through a current-limited switch, held off by a pull-down at reset, so nothing is
  powered there until the firmware asks. The switch discharges its output when off and blocks
  current back into 3.3 V;
- pull-ups to that switched supply, never to 3.3 V, so a chip that is off isn't fed through its
  pins;
- ESD on its lines, for a chip plugged in and out.

The way to swap is with that supply off. Using the site at all needs a firmware profile, which is a
new release, and making a second chip sign is the owner's decision ([AGENTS.md](../AGENTS.md),
rules 1 and 2). The site adds no way to sign and no way to read a key out.

### Programming by pogo pins

There is no header and no button for it. A jig of pogo pins presses on the pads on the back, held in
place by two of the board's holes, and loads the image over SWD. RUN lets it reset the board, BOOT
(QSPI_SS through 1 kΩ) to ground at reset starts the RP2350's USB boot, and D+ and D− are the
RP2350's own USB for that. The 3V3 pad is for measuring only: the board is powered through its
USB-C. Nothing on the pads is reachable through the cable, so loading an image needs the board in
hand. Loading is not the key ceremony, and writes nothing to the key chip.

### Secure boot, as a capability

The RP2350 can be set, in its one-time-programmable memory, to boot only images signed with a key
whose hash is written there, and its debug port can be locked. Both are one way, like the
ATECC608's locks ([docs/LOCKING.md](../docs/LOCKING.md)). The board needs no extra parts for them:
the jig's pads are enough to set them.

What they would stop is someone with the board for a few minutes loading firmware that shows one
thing and has the key sign another. What they don't cover:
- secure boot checks the MicroPython image, not the `.py` files in its filesystem, so the
  console's code would have to be frozen into our own pinned MicroPython build, and that signed;
- with debug locked, the jig can't fix a board, so updates would go through the signed boot path.

None of this is set on any board yet. The plan is to try both on a spare console-rp first
([CONSOLE-RP-PLAN-2026-11-04.md](../CONSOLE-RP-PLAN-2026-11-04.md), "The RP2350's own locks").

## What each board decides

Not fixed here: the shape and size, where each part sits, which GPIO does what, the regulator, the
backlight's supply, whether the second key's site is on the board, and the silkscreen. Each board's
README and pin table have them:

| board | where it stands |
|---|---|
| [console-rp](console-rp/README.md) | 72 × 36 mm. Five built; the first runs a bench script; the console's firmware for it isn't written. Has RESET and BOOTSEL buttons and a bench header in place of the pogo pads, and no second key's site |
| [Mono](mono/README.md) | 40 × 89.5 mm. Routed, fab files pass `tools/keypcb jlc mono`; not ordered. The first with the pogo pads and the second key's site |
