# console-rp: the RP2350's pins

*Written by `gen_console_rp.py`; don't edit by hand.*

| GPIO | RP2350A pin | net | what | board.py's Pico default |
|---|---|---|---|---|
| 2 | 4 | `BTN_D0` | D0, to GND: pull-up inside, pressed low |  |
| 3 | 5 | `BTN_D1` | D1, to GND: pull-up inside, pressed low |  |
| 4 | 7 | `SDA` | I2C0 SDA, the key's bus, 4.7k to 3.3 V | SDA |
| 5 | 8 | `SCL` | I2C0 SCL, the key's bus, 4.7k to 3.3 V | SCL |
| 6 | 9 | `BTN_D2` | D2, to GND: pull-up inside, pressed low |  |
| 8 | 12 | `LCD_DC` | the screen's RS | DC |
| 9 | 13 | `LCD_CS` | the screen's CS | CS |
| 10 | 14 | `LCD_SCK` | SPI1 SCK, the screen's SCL | SCK (SPI1) |
| 11 | 15 | `LCD_MOSI` | SPI1 TX, the screen's SDA | MOSI (SPI1) |
| 12 | 16 | `LCD_RST` | the screen's RESET | RST |
| 13 | 17 | `LCD_BL` | backlight, high is on; 4.7k down | BL |
| 20 | 32 | `LINK_TX` | UART1 TX to the CH343P's RXD |  |
| 21 | 33 | `LINK_RX` | UART1 RX from the CH343P's TXD |  |
| 25 | 37 | `LED` | red LED, high is on |  |

Also: QSPI to the flash (pins 55–60), XIN/XOUT to the crystal, RUN to RESET, SWCLK/SWDIO and
USB_DP/DM (through 27 R) to J3 only. Not connected: GPIO 0, 1, 7, 14–19, 22–24 and 26–29.
