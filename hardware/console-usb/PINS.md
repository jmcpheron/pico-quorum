# console-usb: the S3's pins

*Written by `gen_console_usb.py`; don't edit by hand.*

| GPIO | S3 pin | net | what | the Feather's |
|---|---|---|---|---|
| 0 | 5 | `BTN_D0` | D0, pulled up, low when pressed; the BOOT strap | D0 (low) |
| 1 | 6 | `BTN_D1` | D1, pulled down, high when pressed | D1 (high) |
| 2 | 7 | `BTN_D2` | D2, pulled down, high when pressed | D2 (high) |
| 3 | 8 | `SDA` | the key's I2C, 4.7k to 3.3 V | SDA |
| 4 | 9 | `SCL` | the key's I2C, 4.7k to 3.3 V | SCL |
| 13 | 18 | `LED` | red LED, high is on | LED |
| 17 | 23 | `LINK_TX` | UART1 TX to the CH340C's RXD |  |
| 18 | 24 | `LINK_RX` | UART1 RX from the CH340C's TXD |  |
| 19 | 25 | `DEV_D-` | the S3's own USB, to J3 only |  |
| 20 | 26 | `DEV_D+` | the S3's own USB, to J3 only |  |
| 35 | 40 | `LCD_MOSI` | the screen's SDA | MOSI |
| 36 | 41 | `LCD_SCK` | the screen's SCL | SCK |
| 40 | 45 | `LCD_DC` | the screen's RS | DC |
| 41 | 47 | `LCD_RST` | the screen's RESET | RST |
| 42 | 48 | `LCD_CS` | the screen's CS | CS |
| 43 | 49 | `U0TXD` | UART0 TX, through 510 R to J3 |  |
| 44 | 50 | `U0RXD` | UART0 RX, to J3 |  |
| 45 | 51 | `LCD_BL` | backlight, high is on; a strap: 10k down | BL |

Not connected: GPIO 5–12, 14, 21, 33, 34, 37–39, 46–48, LNA_IN, XTAL_32K_P/N (GPIO15/16), and
the in-package flash's and PSRAM's pins (SPICS1/GPIO26, SPIHD, SPIWP, SPICS0, SPICLK, SPIQ, SPID).
GPIO7, which the firmware drives high for the Feather's screen power, drives nothing here.
