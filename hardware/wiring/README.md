# wiring

Console and key schematics and pinouts. Draft only.

## Key connector: draft pinout

| Plug | Contact | Signal |
|---|---|---|
| ¼″ TRS | Tip | SDA |
| ¼″ TRS | Ring | SCL |
| ¼″ TRS | Sleeve | GND |
| 3.5 mm | Tip | VCC (3.3 V, console-switched) |
| 3.5 mm | Ring | Spare |
| 3.5 mm | Sleeve | GND |

## Design rules

- The shorter 3.5 mm plug mates last and breaks first, which sequences power mechanically.
- The console enables key power **only** after the switched jack's detect contact confirms full
  insertion, and cuts it immediately on removal.
- Key VCC gets a current-limited load switch, so a stray headphone or guitar cable can't do damage.
- SDA, SCL, and VCC get ESD/TVS protection at the jacks.
- I2C pull-ups live on the console side.
- Both jacks mount on one rigid bracket or PCB. One plug on the key gets slight float so it
  self-aligns.

## Prototype pinout (Rev P)

The first order ([bom](../bom/README.md)) has **mono** ¼″ jacks and 3-pin (unswitched) 3.5 mm
jacks. The ¼″ jack has no ring, so the draft pinout above doesn't fit. Rev P uses those parts:

| Plug | Contact | Signal |
|---|---|---|
| ¼″ TS | Tip | GND. With nothing plugged in, the jack's tip switch rests on the tip spring, which gives insertion detect |
| ¼″ TS | Sleeve | GND |
| 3.5 mm | Tip | VCC (3.3 V, console-switched) |
| 3.5 mm | Ring | SDA |
| 3.5 mm | Sleeve | SCL |

Why it may beat the draft, not just stand in for it:

- The ¼″ plug carries only ground. Plugging in or pulling out can't drag a live contact across
  anything, and a guitar cable in the ¼″ jack just gets grounded.
- The ¼″ jack's tip switch gives insertion detect, so the 3.5 mm jack doesn't need switch contacts.
  With the jack's tip lug on GND and the switch lug on a pulled-up GPIO, the GPIO reads low with no
  key and high with a key in. It returns low the moment the plug leaves, whether or not the key is
  powered.
- A headphone in the 3.5 mm jack on its own never trips detect, so VCC never turns on.
- It only needs mono ¼″ parts, which are cheaper, sturdier and easier to find.

Costs and risks:

- There's no spare contact.
- The 3.5 mm sleeve carries SCL. Its metal barrel must stay inside the key's plastic handle.
- On removal, the 3.5 mm tip (VCC) can wipe across the ring spring (SDA) for a moment before the
  ¼″ tip switch closes. The original draft has the same race: its VCC tip wipes the ring and then
  the GND sleeve. Two things cover it: the current limit on key VCC, and firmware that cuts power
  on the detect edge. Test this in Proto 1.
- It depends on the ¼″ jack having a tip-switch lug (see the bom arrival checklist). If it has only
  two lugs, Proto 1 runs without hardware detect: power on after a dial press, then look for the
  chip on the bus. Detect then waits for switched jacks.

- [ ] Decide: Rev P or the draft TRS pinout for real keys

## Pico GPIO map (console prototype)

The screen reuses the Waveshare Pico-LCD-1.3 pins, and Sign and Reject reuse its A and B pins. That
way `firmware/lcd.py` and the inherited key handling need only a new panel init, not new pins.

| GPIO | Pico pin | signal | notes |
|---|---|---|---|
| GP4 | 6 | KEY_SDA | I2C0, the `atecc.py` / `trustm.py` default |
| GP5 | 7 | KEY_SCL | |
| GP6 | 9 | KEY_DETECT | input, pull-up. Low = no key |
| GP7 | 10 | KEY_PWR_EN | P-FET gate. **Low = key powered.** A 10 k pull-up keeps it off through boot |
| GP8 | 11 | LCD_DC | |
| GP9 | 12 | LCD_CS | |
| GP10 | 14 | LCD_SCK | SPI1 |
| GP11 | 15 | LCD_MOSI | labeled SDA or DIN on most modules. This is SPI, not I2C |
| GP12 | 16 | LCD_RST | |
| GP13 | 17 | LCD_BL | PWM |
| GP14 | 19 | STATUS_LED | through 330 Ω to 1 kΩ |
| GP15 | 20 | SIGN | to GND when pressed, internal pull-up (was Waveshare A) |
| GP17 | 22 | REJECT | to GND when pressed, internal pull-up (was Waveshare B) |
| GP20 | 26 | ENC_A | internal pull-up |
| GP21 | 27 | ENC_B | internal pull-up |
| GP22 | 29 | ENC_SW | to GND when pressed, internal pull-up |
| GP28 | 34 | BATT_SENSE | 100 k / 100 k divider, as in [`SOLDERING.md`](../../SOLDERING.md) |
| — | 36 | 3V3 OUT | screen, key power switch, pull-ups |
| — | 39 | VSYS | battery through the 1N5817, as in `SOLDERING.md` |
| — | 3, 8, 13, 18, 23, 28, 33, 38 | GND | |

Free for later: GP0–GP3, GP16, GP18, GP19, GP26, GP27. GP0/GP1 stay free for a UART debug header.
Possible uses: flip-cover "arm" switch, glow LED on the spare key contact, a second status LED.

## Wiring by part

### Screen (one module from the 6-pack)

| module pin | to |
|---|---|
| VCC | 3V3 (36) |
| GND | GND |
| SCL / SCK / CLK | GP10 |
| SDA / MOSI / DIN | GP11 |
| RES / RST | GP12 |
| DC / RS / A0 | GP8 |
| CS | GP9 |
| BLK / BL / LED | GP13, but only if the module switches the backlight through its own transistor. If not, tie it to 3V3 for now |
| MISO, touch pins (T_*), SD pins | leave unconnected. If there's a T_CS or SD_CS, tie it to 3V3 so it stays off the bus |

Firmware: `lcd.py` is a 240×240 ST7789 driver. A 320×240 panel needs a 150 KB framebuffer, which
fits in the Pico 2 W's 520 KB. A 480×320 panel (3.5″) needs 300 KB, too big for a single buffer, so
it would have to draw in strips. ILI9341 and ILI9488 panels need their own init sequence.

### Sign and Reject (DaierTek foot switches)

These are two-lug SPST, normally open. One lug goes to the GPIO, the other to GND, with the
internal pull-up on. It reads 0 when pressed, like the Waveshare keys. Firmware debounces them.
Sign still needs its 2 s hold.

### Rotary encoder (EC11)

```
      A   C   B            SW  SW
      │   │   │             │   │
    GP20 GND GP21         GP22 GND
```

The pins may be arranged differently on this part, so meter them. The internal pull-ups are enough
on a breadboard. On perfboard, add 10 kΩ to 3V3 and 10 nF to GND on A and B if it's jittery.
Decode with a PIO state machine or pin IRQs.

### Status LED

GP14 → 330 Ω (red or amber) or 1 kΩ (green or blue, which look bright even at low current) → LED
anode, cathode to GND.

### Key power, detect and I2C (Proto 1)

```
               10 k
3V3 ──┬───────/\/\/─────┐
      │                │
      S                │
    P-FET   G ─────────┴──── GP7    high = key off (default), low = key on
      D                             (AO3401 or similar logic-level P-FET)
      │
     47 Ω              current limit, ~70 mA into a dead short
      │
  KEY_VCC ──┬── 100 nF ── GND
            ├── 10 k ──── GND       discharges KEY_VCC when off
            ├──────────────────────────── 3.5 mm jack TIP
            ├── 4.7 k ──┬── GP4 (SDA) ─── 3.5 mm jack RING
            └── 4.7 k ──┼── GP5 (SCL) ─── 3.5 mm jack SLEEVE
                        (pull-ups to KEY_VCC, not 3V3)

¼″ jack TIP lug ───── GND
¼″ jack SLEEVE ────── GND
¼″ jack SWITCH lug ── GP6, 10 k to 3V3      low = no key, high = key in
```

- The pull-ups go to switched KEY_VCC, not 3V3. Pulled up to 3V3, they'd feed an unpowered key
  through its I2C pins.
- Before cutting power, firmware sets GP4 and GP5 as plain inputs, so the Pico doesn't feed the key
  either.
- Voltage drop: an ATECC608 draws up to ~14 mA while signing, so 47 Ω drops ~0.7 V and the chip
  sees ~2.6 V (its minimum is 2.0 V). Measure the Trust M's peak current before using it here.
- The Adafruit breakouts already have 10 kΩ pull-ups to their own VIN, which is KEY_VCC. The 4.7 kΩ
  pull-ups are for bare-chip keys later. With a breakout key, skip them or keep both; either works.
- Proto 2 replaces the FET and the 47 Ω with a current-limited load switch and adds a TVS array at
  the jacks.

Firmware sequence:

1. Poll GP6 every few ms, or use a pin IRQ. When it reads high and stays high for ~50 ms, drive GP7
   low, wait ~5 ms, set up I2C, and look for the chip (ATECC608 at 0x60, 0x35 or 0x6A; Trust M at
   0x30).
2. When GP6 falls, drive GP7 high at once (in the IRQ, not the UI loop), then set GP4 and GP5 as
   inputs.

### Prototype key (pigtail)

An Adafruit ATECC608 breakout wired to one pancake ¼″ plug and one 3.5 mm plug, held at the jack
spacing with hot glue or a printed clip:

| breakout pad | plug contact |
|---|---|
| VIN | 3.5 mm tip |
| SDA | 3.5 mm ring |
| SCL | 3.5 mm sleeve |
| GND | ¼″ tip **and** ¼″ sleeve (and the ring, if the pancake plug turns out to be TRS) |

Map the breakout pads with a meter, not by STEMMA QT wire color (see `SOLDERING.md` §1).

## Prototype stages

1. **Proto 0: bench, breadboard, no jacks.** Pico 2 W, one screen, encoder, two foot switches,
   status LED. The ATECC608 breakout goes straight to GP4/GP5 and 3V3. Goals: get `lcd.py` running
   on the chosen screen, drive the UI from the encoder and buttons, and sign with the existing flow.
   Try the screens side by side: long addresses, QR scanning, brightness.
2. **Proto 1: the key connector.** Jacks on one bracket (the 3.5 mm jack is PCB-mount, so a scrap
   of perfboard; the ¼″ jack mounts through a panel). Add the P-FET key power and detect circuit,
   plus a pigtail key. Goals: insert, detect, power, find the chip, sign, pull out. Repeat 100×
   without a missed detect or a brown-out. Then plug in a stray headphone and a guitar cable, and
   check the removal race on a scope or logic analyzer if one is handy.
3. **Proto 2: the console.** Load switch and TVS, the 18650 with the MEETOOT contacts in a printed
   holder, a latching power switch, perfboard or the first PCB, and a printed enclosure with the
   Sign guard.

## Open

- [x] Pico GPIO assignment: see the map above (prototype; revisit once the screen is chosen)
- [ ] Load switch and TVS part numbers (candidates in the [bom](../bom/README.md#still-needed))
- [ ] Does the ATECC608 or the Trust M need anything beyond a decoupling cap on the key side?
- [ ] Jack spacing and bracket: measure the pancake plug and both jack bodies once they arrive
