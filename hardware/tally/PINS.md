# Tally: the RP2350's pins

*Written by `gen_tally.py`; don't edit by hand.*

console-rp's and Mono's pins, so one board profile can serve all three.

| GPIO | RP2350A pin | net | what |
|---|---|---|---|
| 2 | 4 | `BTN_D0` | D0, to GND: pull-up inside, pressed low |
| 3 | 5 | `BTN_D1` | D1, to GND: pull-up inside, pressed low |
| 4 | 7 | `SDA` | I2C0 SDA, the key's bus, 4.7k to 3.3 V |
| 5 | 8 | `SCL` | I2C0 SCL, the key's bus, 4.7k to 3.3 V |
| 6 | 9 | `BTN_D2` | D2, to GND: pull-up inside, pressed low |
| 8 | 12 | `LCD_DC` | the screen's RS |
| 9 | 13 | `LCD_CS` | the screen's CS |
| 10 | 14 | `LCD_SCK` | SPI1 SCK, the screen's SCL |
| 11 | 15 | `LCD_MOSI` | SPI1 TX, the screen's SDA |
| 12 | 16 | `LCD_RST` | the screen's RESET |
| 13 | 17 | `LCD_BL` | backlight, high is on; 4.7k down |
| 20 | 32 | `LINK_TX` | UART1 TX to the CH343P's RXD |
| 21 | 33 | `LINK_RX` | UART1 RX from the CH343P's TXD |
| 25 | 37 | `LED` | red LED, high is on |

Also: QSPI to the flash (pins 55 to 60), XIN and XOUT to the crystal, and on the back's pads and J3:
SWCLK and SWDIO (each through 100 R) and RUN. The chip's own USB (pins 51 and 52) reaches nothing.
Not connected: GPIO 0, 1, 7, 14, 15, 16, 17, 18, 19, 22, 23, 24, 26, 27, 28, 29.
