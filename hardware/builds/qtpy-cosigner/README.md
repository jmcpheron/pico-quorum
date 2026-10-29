# The QT Py cosigner

| | |
|---|---|
| board | Adafruit QT Py ESP32-S3 with 2 MB PSRAM ([5700](https://www.adafruit.com/product/5700)); the QT Py ESP32 Pico ([5395](https://www.adafruit.com/product/5395)) has the same pads |
| key | Adafruit's ATECC608 breakout ([4314](https://www.adafruit.com/product/4314)) on a STEMMA QT cable |
| runs | the console image (`BOARD = "qtpy"`), over Wi-Fi, for a Base Sepolia Safe; [`bench/check.py`](bench/check.py) first |
| case | none yet |
| status | wired on a breadboard and checked 2026-10-28: a QT Py ESP32 Pico, the 1.8″ ST7735S, three buttons, an ATECC608A ([on the bench](#on-the-bench-2026-10-28)) |

The smallest console we can buy the parts for: a QT Py, a small SPI screen, an ATECC608 breakout
and two buttons, with a phone on its USB-C. The phone fetches the Safe's queue and posts the
signatures. The QT Py shows each transaction, rebuilds its hash, and has the key sign only that,
after you have seen every page and held Sign.

```
   Safe's service ── HTTPS ── phone (the relay) ── USB-C ── QT Py ESP32 ── STEMMA QT ── ATECC608
                              no key, no say in              screen, Boot + 2 buttons
                              what gets signed
```

It is [console-usb](../../console-usb/README.md)'s idea from bought boards: no radio in use, and a
link where the console asks and the phone only answers.

![the wiring](wiring.svg)

## What changed from the handoff, and why

The handoff (2026-10-29) asks for a QT Py, an ATECC608 breakout and an SPI screen, with an Android
phone as the host. The parts and the wiring are as it says. Four things are not:

- **No `SIGN <hash>` command.** The handoff has the phone send a 32-byte hash, the screen show it,
  and the chip sign it after a button press. That is a command that signs a digest the host hands
  over, which this project never adds ([AGENTS.md](../../../AGENTS.md), rules 1 and 3): a phone
  that lies about the hash gets a signature for whatever it likes, and a hash on a screen says
  nothing about what the transaction does. Also, the chip doesn't sign the Safe hash itself. Its
  key owns the Safe through Safe's passkey signer, so it signs
  `sha256(authenticatorData || sha256(clientDataJSON))`, with the Safe hash inside clientDataJSON
  ([`firmware/webauthn.py`](../../../firmware/webauthn.py)). So the console builds all of it:
  - the phone carries the queue as [console-usb's link](../../console-usb/README.md#the-link-what-the-computer-can-and-cant-do)
    does: the console asks for a URL on Safe's service, the phone answers with the body;
  - the console decodes the call, rebuilds the Safe hash from the fields it shows
    ([`firmware/safe_tx.py`](../../../firmware/safe_tx.py)), and the key signs only that;
  - no message names the chip, a digest or a signature to make.
- **The console image, not new Arduino firmware.** The handoff's firmware is PlatformIO and
  Arduino, reusing diykey's code. This repository's own Safe hash, decoder, passkey encoding and
  ATECC608 driver are MicroPython, tested on CPython and MicroPython against real Safe
  transactions (`test-vectors/`). The console image already runs on an ESP32-S3. A QT Py needs a
  board profile, not a rewrite in C++.
- **Three buttons, not one.** The console needs Reject, one easy press, apart from Sign, held. So
  three tactile switches: D0 (Reject and Back) on SDA, D1 (Next) on TX, D2 (Sign) on SCL. These
  are the Feather's `feather-s3` rules ([FEATHER-S3.md](../../wiring/FEATHER-S3.md)). Boot was D0
  at first, but it is small and on the board itself, so Reject got a switch of its own.
- **Later, not the QT Py's own USB.** On the S3 the USB-C is MicroPython's REPL, and the computer
  on the other end can restart the chip into its ROM flasher. On the ESP32 Pico the CH9102 is wired
  to UART0, the REPL, with Adafruit's auto-reset. Either way the phone could run any code on the
  board, and have the chip sign any digest. For the bench that is the same as any dev board. For a
  cosigner left plugged into a phone it isn't, so the link moves to UART1 on a serial bridge whose
  DTR and RTS go nowhere ([below](#later-the-link-on-a-serial-bridge)), as console-usb does.

## Which QT Py

Both have the same 14 pads, a STEMMA QT port on the back, Boot and Reset. Their GPIOs differ, so
the firmware goes by board, and this README gives both.

| | QT Py ESP32-S3 (5426, 5700) | QT Py ESP32 Pico (5395) |
|---|---|---|
| chip | ESP32-S3 | ESP32-PICO-V3-02 |
| USB | the chip's own; shows up as an Espressif device | a WCH CH9102 USB serial chip; shows up as a WCH serial port |
| PSRAM | none on 5426, 2 MB on 5700 | 2 MB |
| buy | **5700**. The console has run on an S3 with 2 MB of PSRAM (the Feather), never on one without | works for the link; no USB of its own for a later security-key mode |

Which one you have: read the chip's marking, or plug it into a computer and see which of the two
it shows up as.

## The pins

From CircuitPython's board files for the three boards (`pins.c`, 2026-10-29). Both S3 boards have
the same map.

| pad | S3 GPIO | Pico GPIO | what |
|---|---|---|---|
| **A0** | 18 | 26 | screen CS |
| **A1** | 17 | 25 | screen DC |
| **A2** | 9 | 27 | screen RST |
| **A3** | 8 | 15 | screen BL |
| **SCK** | 36 | 14 | screen SCL (the clock) |
| **MO** | 35 | 13 | screen MOSI |
| **TX** | 5 | 32 | D1, Next: a button to GND |
| **SCL** | 6 | 33 | D2, Sign: a button to GND |
| **SDA** | 7 | 4 | D0, Reject: a button to GND. Later the link's UART1 TX, and D0 moves to A3 |
| **RX** | 16 | 7 | the link, later: UART1 RX from the bridge's TXD |

And off the pads:

| | S3 GPIO | Pico GPIO | |
|---|---|---|---|
| Boot | 0 | 0 | not read. Held at reset it starts the ROM flasher |
| STEMMA QT SDA1, SCL1 | 41, 40 | 22, 19 | the key's bus: `I2C(1)` in MicroPython, `Wire1` in Arduino |
| NeoPixel, its power | 39, 38 | 5, 8 | unused |

- **No boot pins in use** but Boot itself. On the Pico, A3 is GPIO15, a boot pin that only
  silences the ROM's boot log. MI (GPIO12 there) sets the flash voltage at reset, so it is left
  free.
- **The SDA and SCL pads are not the key's bus.** On both boards the STEMMA QT port has a bus of its
  own. Here the pads are a button and the link.
- MI is free on both.

## The screen

The screen on the bench is Lonely Binary's 1.8″ 128 × 160 ST7735S, with 8 pins: BL, RST, DC, SCL,
MOSI, CS, 3V3 and GND. It runs as 160 × 128, as Build 1's 1.8″ does: MADCTL 0xA0, inversion on, no
RAM offset, SPI at 24 MHz. A 240 × 320 ST7789 set-up on it filled half the screen and left the rest
as noise, which is how to tell the two apart.

| screen | QT Py |
|---|---|
| GND | **GND** |
| 3V3 | **3V**. Not 5V unless the module says it takes 5 V |
| SCL | **SCK**. This is the SPI clock. Never the QT Py's SCL pad |
| MOSI (some modules print SDA) | **MO** |
| CS | **A0** |
| DC | **A1** |
| RST | **A2**, or tie it to 3V |
| BL | **A3**, or tie it to 3V for always on |

- Modules put these 8 pins in different orders. The diagram draws them in the order that wires
  cleanly; go by the labels printed on yours.
- The `qtpy` profile draws the console's small screens at 160 × 128, with the three buttons named
  in a footer, left to right ([the screens](../../../docs/quorum-ui/qtpy/README.md)).
- On jumper wires keep SPI at 24 MHz, as Build 1 does, until the picture is clean.

## The key

A STEMMA QT cable from the QT Py's port, on the back, to the breakout. No other wiring.

- The breakout answers at 0x60.
- The port's power is the QT Py's 3.3 V. CircuitPython's map names no pin that switches it, as
  the Feather's GPIO7 does.
- Before you change anything on the chip, find out whether it is configured and locked, and how.
  The console's Device screen and the bench reads tell you; nothing here writes or locks it. An
  ATECC608's locks can't be undone ([docs/LOCKING.md](../../../docs/LOCKING.md)).

## The buttons

| | QT Py | on a review | anywhere else |
|---|---|---|---|
| D0 | a tactile switch, **SDA** to **GND** | Reject: one press, on any page, even while Sign is held | Back |
| D1 | a tactile switch, **TX** to **GND** | the next page; held 1 s, the one before | the next row or choice |
| D2 | a tactile switch, **SCL** to **GND** | the next page not yet seen; once every page is seen, Sign, held 2 s (3 s when a page is red) | Open |

- All three are read with the chip's own pull-ups and pressed low. No resistors. None is a strap
  pin, so a press at power-up does nothing; held at power-up, D1 is maintenance and D2 Wi-Fi
  setup, as on the Feather.
- **One GND pad.** The screen and all three buttons need it. Join the buttons' ground legs, then splice
  that wire and the screen's GND to the pad, on a breadboard row or with a short Y-lead. Every
  ground symbol in the diagrams is that pad.
- Lay them out D0, D1, D2 from left to right under the screen: the footer names them in that order.
- A guarded Sign button is later.

## Later: the link on a serial bridge

![the link](link.svg)

| bridge | QT Py |
|---|---|
| TXD | **RX**, UART1 RX |
| RXD | **SDA**, UART1 TX |
| GND | **GND** |
| 5V | **5V**, through a Schottky (1N5817 or alike), its bar at the QT Py. Adafruit asks for a diode when 5V is an input |
| 3V3 | nothing |
| DTR, RTS | **nothing** |

- A 3.3 V USB serial breakout, a CP2102N or a CH340, whose DTR and RTS are pins you can leave
  unconnected. Not one wired for an ESP32's auto-reset.
- The phone gets a byte pipe to code the console runs. It can't reach the REPL, reset the QT Py or
  start its flasher: MicroPython never puts its REPL on UART1, and DTR and RTS go nowhere.
- The QT Py's own USB-C stays empty. Flashing is a person with the board: a cable there and Boot
  held, as today.
- The link takes the SDA pad. D0 moves to A3 (GPIO15 on the Pico, a strap that only silences the
  ROM's boot log), and the screen's BL is tied to 3V, always on.
- On the ESP32 Pico, the CH9102 is still on the board, on UART0; with nothing in its USB-C it
  carries nothing.

What the phone can do then is what any lying transaction service can do: show transactions that
don't exist, hold back ones that do, misstate the owners or who has signed, drop the signature on
its way out. It can't get a signature for anything but what the screen showed and you held Sign
for. The check that it shows you the right queue is yours: the verify code against the proposer's,
and the Safe's other owners. [console-usb](../../console-usb/README.md#the-link-what-the-computer-can-and-cant-do)
says the same at more length.

## The firmware it needs

- **The `qtpy` profile in `firmware/board.py`: written, for the ESP32 Pico.** `BOARD = "qtpy"` in
  `secrets.py` picks it on a plain ESP32; any other plain ESP32 is still `esp32`. The pins above,
  `THREE` with D0 D1 D2 pressed low, the 1.8″ as 160 × 128, the key on 22/19, nothing to power up.
  `quorum_ui_s.py` names the buttons in a footer, since there is no rail beside the screen.
  `test-vectors/run-console.mjs` runs the three-button suite on it (`main_qtpy`), and
  `node tools/board/shots_qtpy.mjs` draws its screens. On the board since 2026-10-28. An S3 QT Py would
  need its own pins, and `qtpy` read before the look at GPIO16/17, since the link holds RX high.
- **The link,** shared with console-usb: the console's requests to Safe's service on UART1 in
  place of HTTPS, and a relay on the phone. The handoff's first choice for the phone is a page in
  Chrome on Android over Web Serial or WebUSB; neither has been tried here with this board.
- **A bench script** in `bench/`, read-only, as [feather-knob's dial.py](../feather-knob/bench/dial.py):
  the screen the right way up, the three buttons, the key's serial at 0x60.

Each is a firmware change, so a new release fingerprint ([AGENTS.md](../../../AGENTS.md)).

## Steps

1. Wire the screen; the bench script draws on it. Done, 2026-10-28.
2. The key answers at 0x60; its serial on the screen. Done, 2026-10-28.
3. The `qtpy` profile: the console's screens on the QT Py, signing on a testnet over Wi-Fi, as the
   Feather does. Done, 2026-10-28: chip #1 confirmed a Base Sepolia transaction on the 3-of-6.
4. The link on the QT Py's own USB, from a desktop relay, on the bench.
5. The same from Android Chrome.
6. The link on the bridge. Now it is a cosigner you can leave plugged in.
7. A confirmation on Base Sepolia, then Base with a few dollars ([docs/LADDER.md](../../../docs/LADDER.md)).
8. The same on a Rabbit R1 running Android.

The handoff's three demos, as they come out here:
- **The match.** The phone shows the transaction and its verify code; the screen shows its own
  pages and the same code. Hold Sign; the confirmation goes back.
- **The mismatch.** A relay that changes a field: the screen shows the change and a different verify
  code. Reject. A relay that changes the hash the service claims: the console refuses before any
  page.
- **Portability.** Unplug it, plug it into another phone: the same key, the same owner address.

## Open

- **The ATECC608's key.** The bench's chip is an ATECC608A with the `legacy-test` config: config
  locked, data open. That is a test chip, for the emulator's flow and a testnet. A cosigner's own
  key is a ceremony on a chip set up for it ([docs/LOCKING.md](../../../docs/LOCKING.md)); nothing
  here writes or locks one.
- **USB host power on the R1** once it runs Android. If it gives none, an OTG Y-cable or a powered
  hub.
- **Web Serial or WebUSB on Android Chrome** with a CP2102N or a CH340: not tried.

## On the bench (2026-10-28)

A QT Py ESP32 Pico (5395): an ESP32-PICO-V3-02 with 8 MB of flash and 2 MB of PSRAM. On USB it is
a WCH CH9102 (1a86:55d4), `/dev/cu.usbserial-…` on a Mac. It came with Adafruit's self-test.

**1. MicroPython 1.26.1,** the `ESP32_GENERIC-SPIRAM` build from
[micropython.org](https://micropython.org/download/ESP32_GENERIC-SPIRAM/).
`ESP32_GENERIC-SPIRAM-20250911-v1.26.1.bin` had SHA-256
`7c8b439f08449d0ea9ea6d317f35dc5d3743f9e87173afa00caf1fed1f536ccc`. A plain ESP32's image goes at
0x1000; esptool reset the board into its flasher on its own, no buttons:

```sh
esptool --chip esp32 --port $PICO_PORT erase-flash
esptool --chip esp32 --port $PICO_PORT --baud 460800 write-flash -z 0x1000 ESP32_GENERIC-SPIRAM-20250911-v1.26.1.bin
```

It started with 2 MB of heap free, and the STEMMA QT bus (`I2C(1)` on 22/19) answered at 0x60.

**2. The bench check,** [`bench/check.py`](bench/check.py): the screen, the three buttons and the
key, read-only. It draws each button's box, lit while held, the bus and the key's serial, config and
locks, and four colour bars. D2 reads the key again. D1 shows slot 0's owner address, worked out as
the console does (`webauthn.owner_address`, from the public key and the factory in `quorum_cfg.py`),
with its blockie and a QR code, and whether it is the address on record for that serial.

```sh
B=hardware/builds/qtpy-cosigner/bench
mpremote connect $PICO_PORT fs mkdir :bench + \
  fs cp $B/board.py :bench/board.py + fs cp $B/tft.py :bench/tft.py + \
  fs cp firmware/atecc.py :bench/atecc.py + fs cp firmware/chipcfg.py :bench/chipcfg.py + \
  fs cp firmware/blockies.py :bench/blockies.py + fs cp firmware/qrcode.py :bench/qrcode.py + \
  fs cp firmware/webauthn.py :bench/webauthn.py + fs cp firmware/keccak.py :bench/keccak.py + \
  fs cp firmware/quorum_cfg.py :bench/quorum_cfg.py + \
  fs cp $B/check.py :bench/check.py + fs cp $B/main.py :main.py + reset
```

What it showed: the 1.8″ right way up, its colours and all four edges; D0, D1 and D2 each read
pressed and released, D1 and D2 together too, over the serial log; the key at 0x60 on every D2,
an ATECC608A, serial `0123f3acfd2a826bee`, `legacy-test`, config locked, data open. That is
chip #1 ([docs/LOCKING.md](../../../docs/LOCKING.md)): slot 0's owner address came out as
`0x2843705391b7E2cf06b0b964b532Ad9891535E53` in 1.6 s, the one in
[docs/STATUS.md](../../../docs/STATUS.md), whose signer proxy is deployed on Base Sepolia and Base.

**3. The console,** 2026-10-28. A `secrets.py` with `BOARD = "qtpy"`, Wi-Fi, a Safe API key,
the Base Sepolia 3-of-6 (`0x5617…DC41`, [docs/STATUS.md](../../../docs/STATUS.md)) and chip #1's
pin, then `PICO_PORT=/dev/cu.usbserial-… tools/fw push console` (build `6cf8b52f`). The push and
`tools/fw verify` passed: every file's hash, TLS verified, the Safe "ok, owner", the pin ok, 1.6 MB
free, the watchdog on.

**4. A signature,** 2026-10-28. A transaction proposed on the 3-of-6 from a browser wallet came into
the queue; the QT Py showed its pages, and Sign held on D2 posted chip #1's confirmation. TM1, the
Trust M key, confirmed the same transaction from its own console.

## What was checked

- The pads and GPIOs: CircuitPython's `pins.c` for `adafruit_qtpy_esp32s3_nopsram`,
  `adafruit_qtpy_esp32s3_4mbflash_2mbpsram` and `adafruit_qtpy_esp32_pico`, read 2026-10-29.
- `python3 hardware/builds/qtpy-cosigner/wiring.py --check`: both diagrams are what the script
  draws, and the pin table above is the script's.

- On the board, 2026-10-28: [on the bench](#on-the-bench-2026-10-28), above.
- The `qtpy` profile: `node test-vectors/run-console.mjs` (`main_qtpy`), on MicroPython in
  WebAssembly, and on the board, above.

Not checked: the S3 QT Py at all. The pad positions in the diagrams are
drawn to the board's size, not measured; go by the silkscreen.
