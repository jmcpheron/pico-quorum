"""The picoquorum-key board profile, as constants.

The console firmware carries these as the `"picoquorum-key"` profile in PicoQuorum's
`firmware/board.py`, under its own names; the numbers are the contract (docs/PINS.md). Changing any
of them is a new profile and a new release fingerprint.

The key port's pins (rev B, the KEY_ constants below) are not in the console image yet: until a
release carries them, only the smoke test drives them, and the port's key gets no power.
"""

NAME = "picoquorum-key"

# screen: ST7789 240x135 landscape, SPI(1) on the S3's IO_MUX pins
SPI_ID = 1
SPI_SCK, SPI_MOSI = 12, 11
SPI_BAUD = 40_000_000
LCD_CS, LCD_DC, LCD_RST = 10, 9, 14
LCD_BL = 21                 # high is on; PWM-capable; off at reset by hardware
LCD_W, LCD_H = 240, 135
LCD_XOFF, LCD_YOFF = 40, 53
LCD_MADCTL = 0x60
LCD_INVERT = True
RAIL_Y = (7, 67, 127)       # the rows D0, D1, D2 sit level with

# buttons: all to ground when pressed, internal pull-ups. Pressed reads 0.
D0, D1, D2 = 42, 41, 40     # Reject, Next, Sign/Open (module pins 35, 34, 33)
BUTTON_ACTIVE_LOW = True    # applies to all three
BUTTON_PULL = "up"

# the key
I2C_ID = 0
I2C_SDA, I2C_SCL = 16, 17
I2C_FREQ = 100_000
KEY_ADDR = 0x60
NOT_KEYS = ()               # nothing else on the bus

# the key port (rev B): a key-c on a USB-C plug, on a bus of its own (it is at 0x60 too)
KEY2_I2C_ID = 1
KEY2_SDA, KEY2_SCL = 38, 39 # 2.2k to VKEY: no pull-ups while the key is off
KEY_CC = 1                  # low (about 0.32 V) with a key-c in; high with none, or on a board without the port
KEY_EN = 2                  # high powers the key and lights the port's LED; pulled down, so off at reset and
                            # under an image that doesn't know it
KEY_POWER_MS = 10           # after KEY_EN goes high: the key's 200 nF and the switch's soft start

# misc
LED = 48                    # high is on
POWER = None                # nothing to switch on at start
BOOT = 0                    # recovery strap only; never read as a button
UART0_TX, UART0_RX = 43, 44
USB_DM, USB_DP = 19, 20
