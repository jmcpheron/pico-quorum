"""The picoquorum-key board profile, as constants.

This is the hand-off to the console firmware: the values its board profile table needs for a
`"picoquorum-key"` entry. Adapt the names to the firmware's own profile shape; the numbers are the
contract (docs/PINS.md). Changing any of them is a new profile and a new release fingerprint.
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

# misc
LED = 48                    # high is on
POWER = None                # nothing to switch on at start
BOOT = 0                    # recovery strap only; never read as a button
UART0_TX, UART0_RX = 43, 44
USB_DM, USB_DP = 19, 20
