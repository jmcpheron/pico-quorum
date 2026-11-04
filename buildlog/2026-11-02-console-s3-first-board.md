# console-s3 rev A: the first board

The five boards from [the order](2026-10-24-console-s3-order.md) came on 2026-11-02. Board 1 is the
first ESP32-S3 board of our own design to run. Jason soldered the WROOM-1 on by hand, from a reel
of tape, and put the panel in its ZIF. The rest of this page is what was run on it from the Mac,
in order, and what came back.

## 1. On USB with an empty module

- It came up as Espressif's `USB JTAG_serial debug unit` (303A:1001), serial
  `A4:CB:8F:B0:C8:B8`, on `/dev/cu.usbmodem3101`. That is the S3's own USB, through J1 and U4, so
  D+ and D− are the right way round and the 3.3 V regulator (U3) runs the module.
- The ROM printed `ESP-ROM:esp32s3-20210327`, then `boot:0x28 (SPI_FAST_FLASH_BOOT)` and
  `invalid header: 0xffffffff` over and over: the flash is empty. `boot:0x28` means GPIO0 read
  high at reset, so R5 holds it up, and neither D0 nor BOOT is shorted.
- It left USB every 5 to 6 s and came back, with the port closed. That is what a module with an
  empty flash does; Jason has seen it on new modules before.
- Opening the port from the Mac restarted it too: those restarts said
  `rst:0x15 (USB_UART_CHIP_RESET)`, a reset asked for over USB, every time the port was opened.
- Once, it stayed off USB for more than 10 s, until RESET was pressed. Not explained, and not
  seen again.

## 2. What the module is (esptool 5.6.0, read only)

```
Chip type:          ESP32-S3 (QFN56) (revision v0.2)
Features:           Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz, Embedded PSRAM 2MB (AP_3v3)
Crystal frequency:  40MHz
USB mode:           USB-Serial/JTAG
MAC:                a4:cb:8f:b0:c8:b8
Manufacturer: c8   Device: 4017   Detected flash size: 8MB
Flash type set in eFuse: quad (4 data lines)   Flash voltage set by eFuse: 3.3V
```

8 MB flash and 2 MB quad PSRAM: the N8R2 the design asks for, not an R8, whose octal PSRAM would
take GPIO35–37 (the screen's MOSI and SCK). esptool reset the S3 into its loader by itself; BOOT
and RESET weren't needed.

## 3. MicroPython 1.26.1

`ESP32_GENERIC_S3-20250911-v1.26.1.bin` from micropython.org, SHA-256
`d6c48687f684cc7c002a0a4acd258f881c4b391f3ef121726a3b7cd285dcdbbc`, the same file and hash as the
PicoQuorumKey's.

```sh
esptool --chip esp32s3 --port /dev/cu.usbmodem3101 erase-flash                   # 2.7 s
esptool --chip esp32s3 --port /dev/cu.usbmodem3101 --baud 460800 \
  write-flash -z 0 ESP32_GENERIC_S3-20250911-v1.26.1.bin                         # 5.8 s, hash verified
```

In the REPL, over plain serial with DTR and RTS low:

| asked | answer |
|---|---|
| `sys.version` | `3.4.0; MicroPython v1.26.1 on 2025-09-11` |
| `sys.implementation._machine` | `Generic ESP32S3 module with ESP32S3` |
| `esp.flash_size()` | 8388608 |
| `gc.mem_free()` | 2056112: the PSRAM is on the heap |
| `machine.freq()` | 160000000 |
| `esp32.mcu_temperature()` | 22 (°C, the chip's own sensor) |

## 4. Smoke test

PicoQuorumKey's `smoke.py` with console-s3's pins, `board.py`'s `"feather-s3"` (DESIGN.md, Pins),
without its key-port part. It ran from RAM (raw-paste mode, as `mpremote run` does), so nothing was
saved on the board. It reads the ATECC608C's public serial and nothing else from it.

```
[smoke] idle D0/BOOT reads 1 ok
[smoke] idle D1 reads 0 ok
[smoke] idle D2 reads 0 ok
[smoke] backlight OFF; 2 s
[smoke] backlight ON: red top, green, blue
[smoke] backlight 25 %
[smoke] text upright? ticks level with D0 D1 D2?
[smoke] i2c scan: ['0x60']
[smoke] ATECC serial: 012383e06f28dbe1ee
[smoke] press D0 D1 D2 BOOT; LED blinks 2 Hz
[smoke] pressed: D1
[smoke] pressed: D2
```

- **Buttons at rest:** D0 reads high (R5 up), D1 and D2 low (R6, R7 down): none stuck.
- **I2C:** only 0x60 on the bus. The ATECC608C (U2, placed by JLCPCB) woke and gave its serial,
  `01 23 … EE` as every ATECC608 does, with good CRCs.
- **D1 and D2** were pressed and seen.
- Then the board left USB, before D0 or BOOT was seen. It came back by itself, and
  `machine.reset_cause()` said 1, `PWRON_RESET`, with `ticks_ms()` at 18 s when asked.
  MicroPython gives that one number for power-on, the RESET button and a brownout alike.

Jason watched the screen: it looked right, so the panel, its ZIF, the backlight switch (Q1, Q2) and
the picture's turn all work. He had pressed D0, D1, D2 and BOOT, in that order; the log caught only
D1 and D2.

## 5. Chasing the restart

A smaller script, also from RAM, read GPIO0 (D0 and BOOT both pull it low) every 5 ms and printed
each change, and a line every 5 s to show it was alive.

| run | asked to press | what the board printed |
|---|---|---|
| 1 | D0 three times, then BOOT | alive at 5 and 10 s, then off USB before 15 s; no press seen |
| 2 | nothing, 60 s | alive every 5 s to 60 s: it doesn't restart by itself |
| 3 | D0 once | GPIO0 low at 15654 ms, high at 15900; stayed up |
| 4 | BOOT once | GPIO0 low at 8699 ms, high at 8950; stayed up |

So D0 and BOOT each pull GPIO0 low and neither restarts the board. Pressed alone, neither caused the
restarts in the smoke test and run 1. Jason had pressed the top-right button for BOOT, the right one.

## 6. An on-screen button tester, and the restarts are the board being moved

`buttons_s3.py`, from RAM: a box per button level with its rail (D0 and BOOT share GPIO0, so one
box), lit green while it is down, with a count; the last press in large letters; uptime, the
reset cause and the chip's temperature. The LED is on while any button is down. A restart turns the
backlight off, so it shows as the screen going dark.

- First start: off USB before its first line. Back with `PWRON_RESET` and 3.8 s of uptime.
- The S3's own reset register, `RTC_CNTL_RESET_STATE_REG` (0x60008038), read `0xf041`: both cores
  `0x1`, POWERON, not `0xf` (brownout). On the S3, POWERON is the power going or EN going low.
- Second start: GPIO0 read low 25 ms in and stayed low; D2 (28.1 s) and D1 (30.1, 30.5 s) came and
  went; off USB at about 31 s, back in MicroPython (so GPIO0 was high again at that reset). Jason:
  the D0/BOOT box was green the whole time, D1 and D2 lit when pressed, he pressed D0/BOOT twice and
  then it went dark, and he was holding and moving the board.
- The hands-off run (run 2 above) stayed up 60 s.

## 7. D0 and BOOT do nothing once the screen runs: GPIO0 is bridged to GPIO35

Jason: in the tester, D0 and BOOT did nothing; the box stayed green. Yet in runs 3 and 4, with no
screen set up, both pulled GPIO0 low cleanly. So something in the screen's set-up held GPIO0 low.

`g0probe.py` read GPIO0 after each set-up step: 1 at the start, after the LED, CS, DC and RST
pins; **0 from `SPI(1, sck=36, mosi=35)` on**, through the panel's reset, SLPOUT and the backlight
PWM; 1 again after `spi.deinit()`. The same with `miso=None`, as `lcd.py` makes it.

`g0follow.py` then drove neighbours as plain outputs, low then high, and read GPIO0:

| driven | GPIO0 low / high / released |
|---|---|
| GPIO35, MOSI, module pin 28 | **0 / 1 / 1** |
| GPIO45, BL, module pin 26 | 1 / 1 / 1 |
| GPIO36, SCK, module pin 29 | 1 / 1 / 1 |
| GPIO40, DC, module pin 33 | 1 / 1 / 1 |

GPIO0 follows GPIO35 and nothing else: the two are joined. The idle SPI holds MOSI low, which
holds D0 and BOOT low against R5's 10k. In the board they are separate nets on neighbouring pads,
U1 pad 27 `/BTN_D0` and pad 28 `/LCD_MOSI`, 0.9 mm wide at 1.27 mm pitch, so 0.37 mm apart; DRC is
clean, and JLCPCB tested every bare board with flying probes. Pads 27 and 28 are the first two on
the module's long side along the D0/BOOT edge, at its inner end (away from the antenna): board x
40.0 and 41.3 mm, 2.2 mm in from that edge. A solder bridge there, from soldering the module by hand,
is the likely cause. Not yet looked at under a loupe.

It also explains the smoke test: D0 read high before the screen was set up, and the press after it
never showed.

## 8. Reflowed, and D0 and BOOT work with the SPI on

Jason reflowed one side of the module and put the board back on USB without the panel.

- `g0follow.py` again: GPIO0 read 1 with GPIO35 low, high and released, and with the other three.
  The bridge is gone.
- `buttons_serial.py`, from RAM: the screen's SPI as `lcd.py` makes it (`miso=None`), a whole
  240 × 135 frame written every second with no panel there, and the buttons printed as they changed.
  At rest, with the SPI on: D0/BOOT, D1, D2 all up. Then 7 D0/BOOT presses (each down 115-210 ms),
  3 D1, 5 D2 (one of them 16 ms, a light tap), every one down and up. It printed every 10 s to
  130 s, when it was stopped, with no restart while Jason pressed and handled it.
- The LED lit while a button was down. It is red, below BOOT: D1 is a red 0603 (C2286) at
  (55.0, 13.4) in the generator, so that is as drawn.

Then with the panel back in its ZIF, the on-screen tester (`buttons_s3.py`, SPI with `miso=None`):
it started with every button up, and logged 9 D0/BOOT, 6 D1 and 5 D2 presses in the first 46 s,
each down and up. Jason: the screen looks right, and the board stayed up while he held it. So pad
28 still carries MOSI after the wick, and D0, BOOT, D1, D2, the LED and the screen all work
together.

## 9. Wi-Fi, with the module on the back

`wifitest.py`, from RAM: it joined the bench network (the SSID and password from the gitignored
`firmware/secrets.py`, put into a scratch copy of the script for the run and deleted after; never
printed), then kept the radio busy against a small TCP peer on the Mac (192.168.0.160, port 8765,
on the same network): 20 s of download, 20 s of upload, then 60 s of upload without a pause. Panel
in, backlight on from the last test, board on the desk. Where the access point is wasn't noted.

| | |
|---|---|
| tx power | 20.0 dBm (MicroPython's default) |
| scan | the network on channel 10 at −73 dBm |
| joined | in 4704 ms, address 192.168.0.163 |
| RSSI while busy | −66 to −84 dBm, mostly about −70 |
| download, 20 s | 9000 kB in 21.1 s, 426 kB/s (the Mac: 442-547 kB/s per 1 MB) |
| upload, 20 s | 5095 kB in 20.1 s, 253 kB/s (the Mac received all 5095424 bytes) |
| upload, 60 s | 20885 kB in 60.0 s, 348 kB/s (the Mac received all 20885504 bytes) |
| S3's own temperature | 34 °C before, 41 °C downloading, 51 °C after the minute of upload |
| at the end | still connected; no restart through it all |

So the antenna at the board's edge works, and the supply carried a minute of 20 dBm sending without
a brownout. U3's own temperature, which DESIGN.md asks for, was not measured: it sits under the
glass, and the S3's sensor is the die's, not the regulator's. Measure it with the panel out, or
with an IR thermometer through the gap.

## 10. The console, as a demo board

To walk through a review on the real hardware: the console image of the working tree
(`tools/fw build console --dirty-ok`: 2026.11.2, `15ab42a8+dirty`, release 118c·8e6e) without its
`build.py`, so the board runs as a development board, plus a demo `secrets.py` (not in the repo):
the bench Wi-Fi, `QUORUM_URL` the simulated Family Safe on the Mac (`tools/quorum serve`),
`ALLOW_SOFT_KEY = True`, and `ATECC_SDA = 5`, `ATECC_SCL = 6`. GPIO5 and 6 go nowhere on this
board, so nothing answers there and the console signs with a throwaway P-256 key on flash; the
ATECC608C, on GPIO3 and 4, is never addressed.

- Before the copy, the board was off USB again, until RESET was pressed: like the first dropout of
  the day, it didn't come back by itself.
- The copy (raw REPL over plain serial, each file's SHA-256 checked on the board) stopped after 9
  files: the board restarted, POWERON, and came back by itself. It was off USB again a minute
  later, idle at the REPL. Run again, it copied the other 47, and all 55 hashes matched.
- Restarted into the console: Wi-Fi up at 4.4 s, then `no chip (nothing answers on I2C0), using
  software key`. The service logged `console-s3 demo joined as an owner: P-256 key 9a503712.. ->
  signer 0xD3fd94fe…5005`.
- `tools/quorum demo`: the Family Safe at nonce 0 with the standard queue: #0 send-eth, #1 batch,
  #2 add-owner, #3 tampered (the service lies about the hash), #4 unknown-call.

## 11. The restarts

Since the reflow, none: through the serial button run and the screen tester, with the board in
Jason's hand. Before it, five restarts, each `PWRON_RESET`, the register saying POWERON, and each
while the board was being held. What caused them isn't known; the bridge alone doesn't explain
them (run 1 had no SPI running when it restarted). The reflow went over a whole side of the
module, so it may have mended a second joint too. Keep watching for it.

The first notes on them, before the reflow: every restart so far came while the board was in a hand. The guess: a joint that opens when the board
flexes, on the module's hand-soldered pins 1-3 (GND, 3V3, EN) or J1's VBUS and GND, or the cable;
and GPIO0 low from a grip on BOOT, at the top-right corner, or from the same flexing. Not yet
checked.

Later, three more dropouts while the demo's files were being copied (section 10), each needing
RESET or coming back by itself, and each while the board was being handled.

## 12. The panel's metal back, taped

The panel was loose on the board, not yet on its foam tape (DESIGN.md: 2 mm under the glass).
Its back is bare metal, and under the glass sit U3 (the 3.3 V regulator), C1 and C2 (on VBUS and
3V3), Q1, Q2 and the backlight's resistors, U2 and its pull-ups. Metal across any two of their
pads, grounded or not, takes 3.3 V or VBUS down: a POWERON restart, as the register said every
time. Jason taped the panel's back with an insulating layer. Since then, in his hand: stable. Not
proven by a test (nobody pressed the panel down on purpose); whether the metal is grounded wasn't
metered. The foam tape is still to fit.

## 13. A UI lab for the three buttons, then Tabs

Three ways round the console on three side buttons, over a made-up queue (`uilab.py`, kept out of
the repository): A, Menu (D0 opens a menu at the top); B, Tabs (each button works the strip level
with it: D0 the tabs, D1 the list, D2 the bar along the bottom); C, Cards (one thing a screen,
D0 Prev, D1 Next). It signs nothing, calls no chip and writes nothing.

On the board it ran from RAM in maintenance: the USB link's `maint` ask, accepted on the screen
with D2 held; the `maint` file it leaves was deleted before the lab started, so RESET goes back
to the console. Alongside, a local page ran the same file on the emulator in Chrome
(http://127.0.0.1:4321/), reloading itself on every edit.

| time | what |
|---|---|
| 23:12:46 | lab up from RAM, 1.8 MB free |
| 23:19:16 | second version (Tabs first, a Layout list, → for Tab and ● for Open) |
| 23:20:12 | the USB port went away after a D0 press in the lab. Not known whether that was RESET or a dropout |

Jason chose Tabs. It is now the home on three buttons in the firmware (`quorum.py` `tabs_key`,
`quorum_ui_s.py` `draw_tabs`): Queue, Owners, Key and Device, the rail an icon over a word, the
review and signing keys unchanged. Release ee25·f632 (2026.11.2, untagged). Not on this board yet:
it was unplugged after the lab.
