# Console v2: a board you can order

*Exploration, 2026-10-02. Nothing here is ordered or laid out yet. It picks parts and an approach
so that the console's PCB can be drawn next. Part numbers and stock were checked on 2026-10-02.*

Build 1 is a Pico, a screen and a knob on a breadboard, with jumper wires. v2 turns that into one
PCB that a fab such as JLCPCB can assemble. It has a better dial, and a Sign button that lights up
only when there's something to sign. Its key socket follows the
[key interface](../key-interface/SPEC.md), so keys from any batch fit any console.

Goals:

- **Parts the fab places**, or parts that drop into a socket. The hand work is limited to the
  Pico, the screen and the battery.
- **A dial that feels quick.** Every detent moves the screen by exactly one step, even while the
  console is busy.
- **Sign is dark until it means something.** The Sign button glows only when the console has
  computed the hash and is ready to sign.
- **Keys are interchangeable.** The key socket and its power follow the key interface standard, so
  a batch of rev A keys from any fab works.
- **Open files.** A shopping list, the KiCad project, and the fab outputs, the same way
  [key-pcb](../key-pcb/README.md) is done.

## 1. The knob today: mostly firmware

The Build 1 knob felt slow and missed turns. The wiring and the cheap EC11 aren't the main cause.
The firmware is:

1. The encoder's pin interrupts were **soft** interrupts. On the rp2 port a soft interrupt is
   queued and runs only when Python gets to it.
2. The console's UI runs in a 50 ms timer callback (`quorum.tick`). A redraw on the 320×240 panel
   runs the whole `U.draw` eight times, once per band (`board.BANDS`), and sends 150 KB over SPI.
   That's a few hundred milliseconds in which the queued edge handlers can't run.
3. A queued handler reads the pins **when it runs**, not when the edge happened. By then the
   encoder has moved on several states. The quadrature table scores a jump of two states as 0, so
   those steps vanish.
4. While the console polls the transaction service, the timer is switched off
   (`timer.deinit()` around `net_work()`). The knob is dead for the whole HTTPS call.

**The fix, on this branch:** `firmware/knob.py` and `firmware/bench1.py` register the encoder
interrupts with `hard=True`. A hard handler runs at the edge, even during a redraw or an HTTPS
call, and reads the pins at the right moment. The handler doesn't allocate, which is what hard
interrupts on MicroPython need. **This has not been run on the board yet.** To test it:

- In `bench1`, spin the knob fast. The count should match the detents, with none lost.
- On the console, turn the knob during a redraw and during a poll. Every detent should land once
  the screen catches up.

**One more thing to check on the bench:** `STEPS_PER_CLICK = 4` suits an EC11 that goes through a
full quadrature cycle per detent. That's most of them, such as a 20-detent, 20-pulse part. A
30-detent, 15-pulse encoder makes half a cycle per detent and needs 2. With 4, it moves only on
every other click, which also feels "slow". In `bench1`, turn one click at a time and watch
KNOB. If it moves on every other click, set it to 2.

**Later firmware,** if it's still not crisp enough:
- Decode quadrature in a PIO state machine. The counting then happens in hardware and costs Python
  nothing.
- Redraw only what the knob changed, instead of the full eight-band frame.

Better hardware still helps. A good encoder bounces less, has a firmer detent, and lasts longer.
But it won't fix lost interrupts. Do the firmware first, and judge the part after.

## 2. Navigation: dial, joystick, or both

| option | feel | for a fab | GPIO | verdict |
|---|---|---|---|---|
| **Genuine EC11-pattern encoder** (Alps EC11E, Bourns PEC11R) | crisp detents, low bounce | through-hole. JLCPCB solders THT, or you do. The footprint is the same as the clone's | 3 | **rev A.** It's what Build 1 has, only better, and every EC11 fits one footprint |
| **Alps RKJXT1F42001** "multi control device": dial + 4-way tilt + push in one | car-stereo knob | SMD/THT hybrid, one part | 7 | **evaluate.** Dial for paging, tilt for left/right between Safes, push for select. Worth a bench test |
| Illuminated RGB encoder (Bourns PEL12T) | as a PEC11, with an LED in the shaft | THT, 3 LED pins | 3 + 3 | no: the glow belongs on Sign, not on the knob |
| 5-way nav switch (Alps SKQU/SKRH, the Waveshare's joystick) | small, clicky | SMD, cheap | 5 | no: it's what the dev console has, and nobody liked paging with it |
| Thumbwheel encoder (side-mounted, like a mouse wheel) | fast scrolling, one thumb | SMD/THT | 3 | later, if the case becomes a handheld you grip |
| Magnetic angle sensor (AS5600) + magnet, or a haptic knob (SmartKnob) | contactless, no bounce, programmable detents | an I2C sensor plus mechanics, or a BLDC motor and driver | I2C | v3 idea. Lovely, but it's a project in itself |

**Pick for rev A:** an EC11-pattern footprint with a genuine part fitted (§7 has the numbers).
**On the bench now:** an RKJXT, to see whether dial-plus-tilt beats a plain dial. If it wins, rev
A gets its footprint instead. The pin map in §5 has room for it.

## 3. The Sign button, with a light under it

### How it behaves

The light is part of the ceremony. It is off unless the console can sign right now.

| state | Sign light | Reject |
|---|---|---|
| idle, home, Wi-Fi, menus | off | off |
| reviewing a transaction (paging with the dial) | off | off, or a dim red |
| the hash is computed and checked, the key is in and ready | **slow green breathing**, about 1.5 s per breath | dim red |
| Sign held | solid green, brightening as the on-screen bar fills | off |
| signed and sent | one bright green flash, then off | off |
| refused or failed | one red flash, then off | off |
| a red-screen transaction (owner change, delegatecall…) | **amber** breathing instead of green | dim red |

The rule a signer learns is: **if Sign isn't glowing, the console won't sign.** The firmware
turns the light on from the same code that arms Sign, so the light and the arming can't disagree.
It's a cue, not a security boundary: the screen and the hash are still what count.

### The hardware

**Recommended: a keyboard switch with an RGB LED under a frosted keycap.** Mechanical keyboards do
exactly this by the thousand, and every part is made for assembly by a fab:

- **A hot-swap socket** (Kailh, for MX or for Choc) is reflowed onto the PCB by the fab. The switch
  presses in by hand and can be changed without solder. That lets the Sign switch be heavy and
  tactile while Reject is light, and anyone can try their own.
- **A reverse-mount addressable RGB LED** (SK6812MINI-E) sits on the PCB's underside and shines up
  through a hole into the switch's LED window. JLCPCB places it.
- **A translucent or frosted keycap.** Clear and "pudding" MX caps are stock items. A
  resin-printed cap with SIGN engraved also works.
- **One GPIO drives every light:** Sign, Reject and the status LED, chained. MicroPython's
  `neopixel` module drives them from PIO, with no timer work.

**The guard is the case.** The Sign key sits at the bottom of a well, a raised ring about 4 mm
proud of the keycap, so a thumb has to mean it. That, with the 2 s hold already in the firmware,
covers the kickoff's "raised guard". A flip cover can still come later. Reject sits flush, and is
unguarded and instant, as before.

| other ways to light the button | why not first |
|---|---|
| A tact switch with a built-in LED (12 mm, single colour) | One colour: it can't show amber for red-screen transactions. A smaller cap, and a cheaper feel |
| A 16 mm metal panel button with an RGB ring (Adafruit and others) | Lovely feel and looks. But it's panel-mount, so it's wired by hand into the case, the ring needs a resistor per colour, and three GPIOs |
| An arcade button with an LED | Too big for a pocket console. It's the right choice for a desk-sized one |

## 4. The board

```
   Pico's micro-USB ── VBUS (pin 40) ── charger ── 1S LiPo (JST-PH)
                                                        └── slide switch ── Schottky ── VSYS (pin 39)

   ┌─────────────── PCB (rev A, about 70 × 100 mm, 2 layers, JLCPCB PCBA) ──────────────┐
   │  screen module (2.0″ or 2.8″, 8-pin header, on standoffs above the Pico)           │
   │  Pico 2 W, soldered by its castellations, or on 2×20 sockets                         │
   │  EC11 knob (THT)      Sign: hot-swap socket + SK6812MINI-E (underside)             │
   │                       Reject: hot-swap socket + SK6812MINI-E                       │
   │  key socket: 8/16 card-edge, top row ── ESD array ── 4.7 k pull-ups to KEY_VCC     │
   │  load switch: 3.3 V → KEY_VCC, EN = GP6, quick output discharge                    │
   │  battery divider to GP28, status LED (third in the chain), SWD and UART pads       │
   └─────────────────────────────────────────────────────────────────────────────────────┘
```

**Decisions in it:**

- **The Pico 2 W stays a module on rev A.** It's certified, it has its radio and flash, and it is
  the board everything so far ran on. Its castellated edge solders flat onto the PCB, by hand or
  by the fab, or it goes on sockets for a first spin. Doing the RP2350 and Raspberry Pi's RM2
  radio module chip-down is rev B work, worth it only at volume (§8).
- **The screen stays a module** on an 8-pin header, the same 8 wires as Build 1, so `lcd.py`
  doesn't change. A bare panel on an FPC connector saves height and cost, and it comes later.
- **Key power gets a real load switch.** It replaces GP6 feeding the key directly, and closes
  HANDOFF's open decision. GP6 becomes the switch's enable. The switch limits current, and its
  quick output discharge drops VCC fast when DETECT lifts.
- **DETECT gets a hard interrupt** that turns VCC off at once, as the key interface asks (1 ms),
  instead of waiting for the next UI tick.
- **The I2C pull-ups go to 4.7 kΩ** to switched key VCC, as key-pcb's open list suggests.
- **There's ESD on the console side too,** a second USBLC6-2SC6 at the socket.
- **A 1S LiPo replaces the 18650.** A pouch cell with a protection board is lighter and thinner.
  The charger is on the board and charges from the Pico's VBUS pin, and the cell plugs into a
  JST-PH. The cell reaches VSYS through the switch and a Schottky, the way the Pico datasheet draws
  it, and the Pico's own VBUS diode handles USB. The Pico's micro-USB stays at the case edge for
  power, the REPL and flashing. A USB-C socket on the board would need the Pico's D+ and D− test
  pads wired across, so it waits for rev B.

## 5. Pin map, v2

Build 1's pins, with the new parts added. The only firmware changes are the LED chain, and GP6
driving a switch's enable pin instead of the key.

| GPIO | pin | v2 | Build 1 | change |
|---|---|---|---|---|
| GP1 | 2 | knob push | same | |
| GP2, GP3 | 4, 5 | knob A, B | same | |
| GP4, GP5 | 6, 7 | key SDA, SCL | same | 4.7 k pull-ups to KEY_VCC |
| GP6 | 9 | key VCC enable | key VCC itself | drives the load switch |
| GP7 | 10 | key DETECT | same | hard interrupt |
| GP8–GP13 | 11–17 | screen DC, CS, SCK, MOSI, RST, BL | same | |
| GP14 | 19 | tilt up (RKJXT only) | free | |
| GP15 | 20 | **Sign** | A, reserved | wired |
| GP16, GP18, GP20 | 21, 24, 26 | tilt left, down, right (RKJXT only) | free | the Waveshare joystick's own pins |
| GP17, GP19 | 22, 25 | B, X: not fitted | reserved | |
| GP21 | 27 | **Reject** | Y, reserved | wired |
| GP22 | 29 | **LED chain data**: Sign, Reject, status | free | new |
| GP26 | 31 | key RST | same | |
| GP27 | 32 | key ID (ADC1) | same | 10 k pull-up to KEY_VCC, as in the spec |
| GP28 | 34 | battery sense (ADC2) | same | |
| GP0 | 1 | free | free | |

GP23, GP24, GP25 and GP29 still belong to the radio.

## 6. The case

With a PCB, the case stops being a box around loose parts:

- **Two printed shells screwed to the PCB's mounting holes**, with M2.5 heat-set inserts. The PCB
  is the chassis.
- **The key socket opens on the top edge.** The key goes straight down in, so its label faces the
  signer.
- The screen sits in a window above the Pico. The knob is on the right. The **Sign well** goes
  where the right thumb lands, with Reject flush below it.
- **For batches,** the shell can come from JLCPCB's own 3D printing service (JLC3DP: SLA resin or
  MJF nylon) in the same order as the boards. Keycaps can be stock MX caps, or SLA clear resin.
- The case generator (`cad/console/gen.py`) keeps its parametric approach. It takes the board
  outline and the part centres from the KiCad file, so the case re-fits whenever the PCB moves.

## 7. Parts

### Bench evaluation: buy these before laying out the board

These let the knob, the light and the switches be tried on Build 1 with jumper wires, before
anything is committed to copper.

| part | qty | why | about |
|---|---|---|---|
| Bourns PEC11R-4220F-S0024 (20 detents, 20 pulses, push) | 2 | the genuine EC11-pattern knob | $2–3 |
| Alps EC11E15244G1 (push) | 2 | the other genuine one, to compare | $2–3 |
| Alps RKJXT1F42001 (dial + 4-way + push) | 1–2 | dial-plus-tilt | $5–8 |
| Adafruit NeoKey Socket Breakout (4978): one MX hot-swap socket + a reverse-mount NeoPixel | 2–3 | exactly the Sign design, on jumper wires | $2 |
| MX switches: a tactile and a linear, a few of each | 4–6 | the Sign feel vs the Reject feel | $5 |
| clear or frosted MX keycaps | a pack | the glow through the cap | $5–10 |
| a 1S LiPo, 1000–2000 mAh with a protection board, JST-PH | 1 | the v2 battery | $8–12 |

### Rev A board: what the fab places

| part | ref | why |
|---|---|---|
| EC11-pattern encoder with push (Bourns PEC11R or Alps EC11E) | ENC1 | the knob, THT |
| Kailh MX hot-swap socket, ×2 | SW1, SW2 | Sign and Reject |
| SK6812MINI-E, ×3 | LED1–3 | Sign, Reject, status |
| card-edge socket, 0.100″, 8/16 positions | J1 | the key. THT, hand-soldered: the Sullins body isn't reflow-rated |
| USBLC6-2SC6 | U3 | ESD at the key socket |
| load switch with quick output discharge (e.g. TI TPS22917) | U4 | switched KEY_VCC |
| MCP73831-2 or equivalent LiPo charger | U5 | charging from USB |
| Schottky (e.g. MBR120 / 1N5817 in SMD), slide switch, JST-PH | | battery path |
| 4.7 k ×2, 10 k ×1, 100 k ×2, 100 nF, 4.7 µF | | pull-ups, ID, battery divider, decoupling |
| Pico 2 W | U1 | hand-soldered, or on sockets |
| 2.0″ or 2.8″ ST7789 SPI module | | on its header |

## 8. Making them in batches

| | rev A (now) | rev B (if it gets used) |
|---|---|---|
| MCU | a Pico 2 W module | RP2350 chip-down + RM2 radio module + QSPI flash |
| screen | a module on a header | a bare panel on an FPC connector |
| assembly | JLCPCB places the SMD parts. The Pico, the screen, the encoder and the key socket are soldered by hand | everything by the fab except the cell |
| quantity | 5 | 20–100 |
| hand time per console | about 30 min | about 5 min |

**Keys come separately.** Any batch that meets the [key interface](../key-interface/SPEC.md)
works. Rev A keys are already drawn and can be ordered now
([ORDERING.md](../key-pcb/ORDERING.md)).

**A console kit** for somebody else to build could be the rev A board assembled, plus a Pico,
a screen and a cell, with the BOM and the firmware image.

## 9. Order of work

1. **Firmware knob fix on Build 1** (this branch). Check the count and STEPS_PER_CLICK on the bench.
2. **Buy the bench evaluation parts.** Wire a NeoKey socket's NeoPixel to GP22 and its switch to
   GP15. Write the Sign light states (§3) in a small firmware module. Compare the encoders and the
   RKJXT.
3. **Order key PCB rev A,** and test-fit it in the socket. That settles the key interface's open
   points.
4. **Draw console rev A in KiCad,** generated like key-pcb (`gen.py`, `tools/keypcb`-style checks
   and fab outputs). Order 5 assembled.
5. **Case for rev A**, from the board outline.
6. **Rev B** only once rev A has seen real use.

## 10. Open

- [ ] Is the knob crisp after the hard-interrupt fix? Measure before buying anything
- [ ] Dial only, or the RKJXT's dial-plus-tilt
- [ ] MX or Choc (low-profile) for Sign and Reject. Choc makes a thinner console, and MX has more
      switches and caps
- [ ] SK6812MINI-E supply: 3.3 V, or a 5 V/VSYS rail with a level shifter on the data line (§7 notes)
- [ ] Pico 2 W soldered flat by its castellations, or on sockets
- [ ] 2.0″ or 2.8″ screen for v2 (the 2.8″ is proven on the bench)
- [ ] Case: a handheld you grip, or a desk console you put down
