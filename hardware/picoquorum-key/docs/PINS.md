# The `picoquorum-key` pin profile

*2026-10-25. The GPIO table rev B is built on, as wired in `tools/gen/circuit.py` and the generated
schematic. It is a new profile under spec rule 2. The console firmware has carried it since
2026-10-24, as `picoquorum-key` in PicoQuorum's `firmware/board.py`; it reaches a board with the
next release. The constants are also in
[../firmware/profile/picoquorum_key.py](../firmware/profile/picoquorum_key.py).*

*Rev B adds the key port's four pins (GPIO1, 2, 38, 39), all from pins rev A left free, and
changes none of rev A's. The console image doesn't know them yet ("In the console image", below).*

## Why a new profile

The firmware's original `feather-s3` profile mirrors an Adafruit Feather: Reject on GPIO0 (the BOOT
strap), Next and Sign active-high with pull-downs, the screen on GPIO35/36 (lost on octal-PSRAM
modules), the backlight on GPIO45 (a strap). On a board of our own none of that is forced on us.
`picoquorum-key` buys:

- **No UI button on a strap.** Holding any button at plug-in can't enter the ROM bootloader.
- **One polarity for every button:** to ground, internal pull-up. No external resistors.
- **Short button tracks.** The three buttons are on GPIO42–40, module pins 35–33. With the module
  on the back, that castellation column faces the button column, so no button track crosses the
  module.
- **The screen on the S3's IO_MUX SPI pins** (SPI2 / "FSPI": SCK 12, MOSI 11), the pins MicroPython's
  `SPI(1)` defaults to on `ESP32_GENERIC_S3`. Clean 40 MHz without GPIO-matrix routing.
- **GPIO35–37 unconnected**, so an R8 (octal PSRAM) module would also work.
- **Straps left at their defaults**: 45 and 46 unconnected, 0 only on BOOT, 3 unconnected.

GPIO39–42 double as the pad JTAG pins (MTCK, MTDO, MTDI, MTMS). The S3 routes JTAG to its own USB
by default and only switches to the pads through an eFuse this console never burns. So they are
plain GPIOs here, and a pressed button can't disturb a debugger.

## The table

Pin numbers are the ESP32-S3-WROOM-1's castellations (datasheet section 3), checked against
KiCad 10's `RF_Module:ESP32-S3-WROOM-1` symbol.

| function | GPIO | module pin | net | electrical |
|---|---|---|---|---|
| screen SCK | 12 | 20 | LCD_SCK | SPI(1) `sck`, IO_MUX |
| screen MOSI | 11 | 19 | LCD_MOSI | SPI(1) `mosi`, IO_MUX |
| screen CS | 10 | 18 | LCD_CS | active low |
| screen DC | 9 | 17 | LCD_DC | high = data |
| screen RST | 14 | 22 | LCD_RST | active low; R5 10k pull-up holds the panel out of reset |
| backlight BL | 21 | 23 | LCD_BL | high = on; PWM (LEDC); drives the NPN of the high-side switch |
| D0 Reject | 42 | 35 | BTN_REJECT | to GND when pressed; `Pin.PULL_UP` |
| D1 Next | 41 | 34 | BTN_NEXT | same |
| D2 Sign / Open | 40 | 33 | BTN_SIGN | same |
| key SDA | 16 | 9 | I2C_SDA | 4.7k to 3.3 V |
| key SCL | 17 | 10 | I2C_SCL | 4.7k to 3.3 V |
| status LED | 48 | 25 | LED | high = on, 1k series |
| BOOT | 0 | 27 | BOOT | tact to GND, 10k to 3.3 V |
| USB D− | 19 | 13 | USB_DN_MCU | through 0 Ω link R13 to the connector's D− |
| USB D+ | 20 | 14 | USB_DP_MCU | through 0 Ω link R12 to the connector's D+ |
| UART0 TX | 43 | 37 | UART_TX | debug pad TP4 only |
| UART0 RX | 44 | 36 | UART_RX | debug pad TP5 only |
| EN | – | 3 | EN | 10k to 3.3 V, 1 µF to GND, RESET tact to GND, pad TP3 |
| key port CC | 1 | 39 | KEY_CC | R17 47k to 3.3 V (every board), R18 1k to the plug's A5; low with a key-c in; ADC1_CH0; pad TP9 |
| key port enable | 2 | 38 | KEY_EN | R15 100k to GND; high powers the key (U5); pad TP10 |
| key port SDA | 38 | 31 | KEY2_SDA | R19 2.2k to VKEY; `I2C(1)`; pad TP13 |
| key port SCL | 39 | 32 | KEY2_SCL | R20 2.2k to VKEY; `I2C(1)`; pad TP14 |
| unconnected | 4–8, 13, 15, 18, 47 | 4–7, 12, 21, 8, 11, 24 | | free GPIOs, no copper |
| unconnected strap | 3, 45, 46 | 15, 26, 16 | | left floating on purpose |
| unconnected | 35–37 | 28–30 | | reserved for R8 modules' PSRAM |
| 3V3 | – | 2 | +3V3 | 22 µF + 100 nF beside the module |
| GND | – | 1, 40, 41 | GND | 41 is the exposed pad; needn't be soldered |

## Straps at reset (datasheet Table 4-1)

| strap | state | held by |
|---|---|---|
| GPIO0 | high → normal boot | 10k pull-up R4; BOOT tact pulls it low for download mode |
| GPIO45 | low → VDD_SPI = 3.3 V | internal pull-down; unconnected |
| GPIO46 | low | internal pull-down; unconnected |
| GPIO3 | don't care | JTAG source only matters with an eFuse this console never burns |

## In MicroPython

```python
from machine import Pin, SPI, I2C, PWM

spi  = SPI(1, baudrate=40_000_000, sck=Pin(12), mosi=Pin(11))   # SPI(1) == FSPI on the S3
cs, dc, rst = Pin(10, Pin.OUT, value=1), Pin(9, Pin.OUT), Pin(14, Pin.OUT, value=1)
bl   = PWM(Pin(21), freq=1000, duty_u16=0)                        # off until the image is drawn
d0, d1, d2 = (Pin(n, Pin.IN, Pin.PULL_UP) for n in (42, 41, 40))  # pressed == 0
i2c  = I2C(0, scl=Pin(17), sda=Pin(16), freq=100_000)             # ATECC608C at 0x60
led  = Pin(48, Pin.OUT)

# the key port (rev B)
key_cc   = Pin(1, Pin.IN)                     # R17 pulls it up: 0 = a key-c in. No internal pull-up
key_en   = Pin(2, Pin.OUT, value=0)           # 1 powers the key and lights D4; wait ~10 ms before talking to it
key_i2c  = I2C(1, scl=Pin(39), sda=Pin(38), freq=100_000)        # a key-c at 0x60, only while key_en is 1
```

Screen geometry is unchanged from the spec: 240 × 135 landscape, column offset 40, row offset 53,
`MADCTL = 0x60`, inversion on, rail rows 7, 67 and 127.

## In the console image

`firmware/board.py` has a `picoquorum-key` profile: the pins above, every button pulled up and
pressed low (`HIGH = ()`), `POWER = None` (nothing to switch on at start), `NOT_KEYS = ()` (nothing
else on the bus). It keeps the Feather's three-button UI (`THREE`), screen geometry and rail. The
screen driver, the key driver and the UI don't change. The release fingerprint changed, because the
profile is part of the image.

The image has one build for every S3, so it tells this board from the Feather by looking. At start
it reads GPIO16 and 17 as inputs with only the S3's internal pull-downs (about 45k) on them. Here
R6 and R7 (4.7k) pull both high, so it picks `picoquorum-key`. The Feather, console-s3 and the
wings leave both free, so they read low and stay `feather-s3`. **Keep pull-ups on 16 and 17**: a
later revision without them would get the Feather's profile, which drives GPIO40–42 as outputs.

Checked on the laptop, not yet on a board: PicoQuorum's `test-vectors/feather_s3_test.py` runs the
profile on a stand-in S3 with 16/17 pulled up, and `test-vectors/run-console.mjs` runs the
three-button console on it in the emulator.

**The key port is not in the console image yet.** The image drives none of GPIO1, 2, 38 or 39, so R15 holds KEY_EN low and a key-c on the plug gets no power: a rev B board runs the console
exactly as rev A does, with the soldered chip. What the image needs, as a later change and a new
release fingerprint:

- the four pins in the `picoquorum-key` profile, other profiles `None`;
- `signer.detect()` learns the second bus: when KEY_CC reads low, drive KEY_EN high, wait about
  10 ms (the key's 200 nF and U5's soft start), scan I2C(1); when it reads high, drive KEY_EN low
  and drop that signer. The soldered chip is read as today;
- `same_chip()` already re-reads the serial just before a signature, on whichever chip is about to
  sign, so a key swapped mid-approval is caught. That stays the hot-swap check;
- **which key signs when both are in** is a product decision still open: the plan's proposal is the
  plugged key when CC shows one and `QUORUM_EXPECT` pins it, else the soldered chip, named on the
  splash and the Sign page;
- the port's LED (D4) and a key-c P3's own (through R21 on SBU) run off VKEY: they are on while
  the key is powered, and no pin drives them. U5's FAULT is left open, so an overload looks to the
  image like a key that doesn't answer. Both were GPIOs in the plan (13 and 47); rev A's routing
  closes in module pins 21 and 24, so rev B leaves them open (DESIGN.md, "The key port").

`firmware/smoke/smoke.py` already drives the port (BRINGUP.md), and `tests/test_twin.py` runs it
against the board's nets with a modelled key-c.
