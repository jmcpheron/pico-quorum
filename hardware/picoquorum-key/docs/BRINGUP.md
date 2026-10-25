# Building and bringing up a board

*2026-10-23. Per board, about 30 minutes once the parts are on the bench.*

## What you need

- the assembled board from JLCPCB (key chip U2 already placed), a WROOM-1-N8R2, a panel, foam tape
- a temperature-controlled iron (fine chisel tip), flux pen, 0.5 mm solder, wick, isopropyl
- a multimeter, a USB-C cable to the Mac, `esptool` and `mpremote` (both already on this Mac)
- MicroPython `ESP32_GENERIC_S3` 1.26.1 `.bin` from https://micropython.org/download/ESP32_GENERIC_S3

## 1. The bare board

Before any hand soldering:

- Meter 3V3 pad to GND for shorts: expect kΩ or more, not zero.
- Plug in USB. Expect 3.3 V ± 0.1 V on TP1 (+3V3) and 5 V on TP11 (+5V). The backlight switch
  must be off: J2 pad 8 (LEDA, the pad nearest the USB end) near 0 V.
- Unplug.

## 2. Check the key (U2, UDFN-8)

JLCPCB placed it. Check under a loupe that its pin-1 dot matches the silkscreen triangle and that no
pads are bridged (they are 0.5 mm apart, and hidden under the part's edge: look at the fillets).
Meter SDA and SCL to 3V3: ~4.7 kΩ each, and neither shorted to GND.

## 3. Solder the module (U1, back face)

- Flux all 41 pads. Position the module on the **back**: antenna end flush with the board's top
  edge, the antenna area over the empty band. Pin 1 (GND, nearest the antenna) matches the
  silkscreen's pin-1 mark. The pads run 1 mm past the castellations for the iron.
- Tack pin 1 and the opposite corner. Check that every castellation sits on its pad.
- Drag-solder each side with a well-tinned tip and plenty of flux. The castellations wick solder
  from the pad up the half-hole; a clean fillet in each half-hole is the sign.
- Leave the exposed pad (41) unsoldered (datasheet section 9 allows it).
- Clean with isopropyl. Meter 3V3 to GND again for shorts, then EN to 3V3 (10 kΩ).

## 4. Flash MicroPython

```sh
esptool --chip esp32s3 --port /dev/cu.usbmodem* erase_flash
esptool --chip esp32s3 --port /dev/cu.usbmodem* write_flash -z 0 ESP32_GENERIC_S3-20250911-v1.26.1.bin
mpremote
```

The S3's own USB enumerates as `/dev/cu.usbmodem…`. If esptool can't enter download mode by itself:
hold BOOT, tap RESET, release BOOT, retry. In the REPL:

```python
import esp, esp32, gc
esp.flash_size()          # 8388608 for N8R2
gc.mem_free()             # ~ 8 MB with 2 MB PSRAM mapped; a few hundred kB without
```

If `gc.mem_free()` shows no PSRAM, the module is not an R2 or the build is wrong; stop here.

## 5. Panel and smoke test

- Put 1.5 mm foam tape on the board at the glass outline's left and right ends, liners still on.
- Flip J2's actuator up (it hinges at the rear, the side away from the fold). Hold the panel face
  up beside the board's right edge, fold its ribbon back under the glass, and slide it fully into
  J2 from the right. The contacts are double-sided, so the ribbon's face can't be wrong. Press
  the actuator down.
- Lay the panel over the glass outline. Don't peel the tape's top liners until the test passes.

```sh
mpremote cp firmware/smoke/smoke.py :smoke.py
mpremote run firmware/smoke/smoke.py
```

The test, in order, and what passing looks like:

| step | passes when |
|---|---|
| backlight | stays off for 1 s, then comes up (GPIO21 driving the NPN); dims at 25 % |
| screen | three colour bands then the text `picoquorum-key` **upright**, with the buttons on the left |
| rails | three short ticks at rows 7, 67 and 127 at the left edge, level with the three switches |
| buttons | each of D0 D1 D2 (GPIO42–40) prints its name when pressed and lights its rail tick |
| LED | blinks at 2 Hz throughout |
| key bus | `i2c scan: ['0x60']` and nothing else |
| key | `ATECC608 serial: 01 23 ... EE` (9 bytes, first `01 23`, last `EE`), and the chip answers at 0x60 after wake |

Anything else is a hardware fault to find before the console image goes on. The test reads only
the chip's public serial number; it signs nothing and reads no key (rule 3).

## 6. Finish

- Peel the tape, press the panel down square to the rail ticks.
- Write the board's serial (from the test) and the module's lot on the back in pencil, or in the
  project log.
- The console image and the ceremony are PicoQuorum's steps (`tools/fw push console`), from a
  release that has the `picoquorum-key` profile; 2026.10.12 and earlier don't
  ([PINS.md](PINS.md#in-the-console-image)).

## 7. The key port (optional)

Only for a board that gets the port ([DESIGN.md](DESIGN.md#the-key-port-optional), parts in
[BOM.md](BOM.md#the-key-port-fitted-by-hand-optional)). Do it after the smoke test passes, so a fault
here isn't mistaken for one elsewhere. Everything is on the back, beside the module.

- Solder the small parts first: U5, U6 (pin 1 at the silkscreen dot), D2 (its band, the cathode,
  toward VKEY), then R15–R19, C9 and C10.
- Then the plug, J3: its body past the left edge, its back pressed against the edge, its twelve
  tails on their pads. Tack the two outer shell pads, check the tails line up, flux, and drag-solder
  the row (0.5 mm pitch). Solder all four shell pads well: they hold it.
- Meter, unplugged: VKEY (J3's A4 or the top of C10) to GND not a short; IO1 (TP9) to 3V3 about
  23 kΩ; IO2 (TP10) to 3V3 about 10 kΩ.
- Plug in USB, no key: TP9 at 3.3 V, VKEY about 3.3 V.
- Put key-c on: TP9 falls to about 0.6 V. Take it off: back to 3.3 V.
- In the REPL, with key-c on:

```python
from machine import Pin, I2C
Pin(1, Pin.IN).value()                         # 0: a key is in; 1: none
I2C(1, scl=Pin(38), sda=Pin(39)).scan()        # [96]: the plugged key at 0x60
I2C(0, scl=Pin(17), sda=Pin(16)).scan()        # [96]: U2, alone on its own bus
```

This reads nothing from either chip but its address. The console image doesn't use the port yet
([PINS.md](PINS.md#the-key-ports-pins)).

## Checks worth a minute each

- 3V3 under Wi-Fi: with the console image scanning, 3V3 stays above 3.2 V at the pad.
- Straps at reset: TP8 (BOOT, GPIO0) high with a meter while holding RESET. 45 and 46 have no
  pads; their defaults show as a normal boot.
- esptool reaches the bootloader both ways: BOOT+RESET by hand, and with no buttons.
- Backlight off at reset: unplug, plug in, the panel stays dark until software asks.
