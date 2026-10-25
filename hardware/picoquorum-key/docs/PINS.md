# The `picoquorum-key` pin profile

*2026-10-23. The GPIO table rev A is built on, as wired in `tools/gen/circuit.py` and the generated
schematic. It is a new profile under spec rule 2. The console firmware has carried it since
2026-10-24, as `picoquorum-key` in PicoQuorum's `firmware/board.py`; it reaches a board with the
next release. The constants are also in
[../firmware/profile/picoquorum_key.py](../firmware/profile/picoquorum_key.py).*

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
| spare | 1, 2 | 39, 38 | IO1, IO2 | to pads TP9, TP10 only; both are ADC1 inputs |
| unconnected | 4–8, 13, 15, 18, 38, 39, 47 | 4–7, 12, 21, 8, 11, 31, 32, 24 | | free GPIOs, no copper; 38 and 39 were PREV and BACK |
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
