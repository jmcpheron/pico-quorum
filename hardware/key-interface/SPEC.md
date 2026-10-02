# Key interface, version 0 (draft)

*Drafted 2026-10-02 from key PCB rev A. Nothing here is frozen until a rev A key has been seated in
a real socket and signed through it.*

This is the contract between a **key** and a **console**. Any key that meets it fits any console
that meets it, whoever made either one. A batch of keys from one fab therefore works in consoles
from another fab, and in a console somebody else built from these files. The reference designs
are [key PCB rev A](../key-pcb/README.md) for the key and [console v2](../console-v2/README.md)
for the console.

Words: **must** is required, **should** is strongly recommended, and **may** is allowed.

## 1. Mechanical: the blade

The key is a PCB whose leading edge is the plug. It goes into a stock 0.100″ card-edge socket.

| what | value | notes |
|---|---|---|
| board thickness | 1.6 mm (0.062″) ±10 % | what 0.062″-card sockets take |
| contact pitch | 2.54 mm (0.100″) | |
| positions | 8, top side only | the bottom row of a dual-readout socket is unused |
| blade width | 22.35 mm, +0 / −0.38 mm | an 8-position 0.062″ card per EDAC: 0.888″ +0/−0.015″ |
| finger width | 1.40 mm | |
| finger end | 8.5 mm from the leading edge, every finger | the contact lands about 4.3 mm in |
| leading corners | 0.8 mm chamfer | |
| keying | a 2.03 mm slot at position 6, 6.0 mm deep | **open: in-contact or between-contacts key**, see [key-pcb](../key-pcb/README.md#open) |
| finish | ENIG or harder gold | never HASL: tin fingers wear and oxidise |

The fingers are staggered so the contacts mate in a fixed order:

| finger start from the edge | positions | mates |
|---|---|---|
| 0.5 mm (long) | GND | first in, last out |
| 1.25 mm (mid) | SDA, SCL, VCC, ID, RST | second |
| 2.0 mm (short) | DETECT | last in, first out |

A key put in upside down meets nothing on the console. DETECT never closes, so it is never
powered.

## 2. Electrical: the pins

| pos | signal | key side | console side |
|---|---|---|---|
| 1 | GND | ground | ground |
| 2 | SDA | the secure element's SDA, no pull-up | I2C data, pull-up to switched VCC |
| 3 | SCL | the secure element's SCL, no pull-up | I2C clock, pull-up to switched VCC |
| 4 | VCC | supply in | switched 3.3 V |
| 5 | ID | resistor to GND, or open | pull-up to switched VCC, read by an ADC |
| 6 | *key slot* | no copper | no contact, or the socket's key insert |
| 7 | RST | the chip's reset if it has one (Trust M), else open | push-pull GPIO, held high while powered |
| 8 | DETECT | tied to GND on the key | input with a pull-up to the console's 3.3 V |

**Supply**

- The console must give 3.3 V ±5 % on VCC, at up to 100 mA continuous.
- The console must switch VCC with a load switch, and should limit it to about 200 mA, so that a
  shorted key can't pull down the console. A GPIO pin as the supply is a bench shortcut, not
  compliance.
- When it switches off, VCC should fall below 0.3 V within 10 ms. An output-discharge load switch
  does this.
- A key must draw no more than 50 mA on average, with peaks up to 100 mA, and should hold no more
  than 1 µF on VCC.

**I2C**

- The key must have no pull-ups. They live on the console, 4.7 kΩ to switched VCC. Never put them
  on the always-on 3.3 V, which would feed a switched-off chip through its bus pins.
- Up to 400 kHz. Consoles should start at 100 kHz.
- Reserved addresses: 0x60, 0x35 and 0x6A for an ATECC608, and 0x30 for an OPTIGA Trust M. A key
  must answer at one of them. A new chip family gets its address added here first.

**Protection**

- A key must have ESD protection on SDA, SCL and VCC, between the fingers and the chip.
  Rev A uses a USBLC6-2SC6.
- A console should have its own ESD array at the socket.
- Neither side may drive SDA, SCL, ID or RST while VCC is off.

## 3. Sequence

The console must do this. Nothing in it is optional.

1. **Wait for DETECT.** DETECT must read low for 200 ms without a break.
2. **Power up.** Switch VCC on and wait 5 ms. Then drive RST high.
3. **Read the ID.** Read the ID pin on the ADC (§4).
4. **Find the chip.** Scan the reserved addresses, up to 3 tries. If nothing answers, VCC goes off,
   the console says "not a key", and it waits for DETECT to go high.
5. **Power down on removal.** The moment DETECT goes high, VCC goes off within 1 ms. SDA, SCL, RST
   and ID then go to inputs with no pull-ups. 1 ms means a hard interrupt on DETECT, not a poll
   in the UI tick: DETECT breaks 1.5 mm before the signal fingers do, which is only a few
   milliseconds on a brisk pull.

A key must survive being pulled out at any point in this sequence, including in the middle of a
signature, without damage. A key should not be left in a state that needs anything more than a
fresh power-up to recover.

## 4. Key ID

The ID pin tells the console what's on the key before it says a word on I2C. The key has a single
resistor R_ID from ID to GND. The console has 10 kΩ from ID to switched VCC. It reads the ratio
on the ADC, so supply tolerance cancels out.

| R_ID (1 %) | ratio V_ID / VCC | means |
|---|---|---|
| open | > 0.95 | not stated. Probe I2C (every rev A key) |
| 0 Ω | < 0.05 | reserved: test fixture |
| 2.2 kΩ | 0.18 | ATECC608, Safe passkey owner (P-256) |
| 4.7 kΩ | 0.32 | OPTIGA Trust M, Safe passkey owner (P-256) |
| 10 kΩ | 0.50 | reserved |
| 22 kΩ | 0.69 | reserved |
| 47 kΩ | 0.82 | reserved |

Neighbouring codes are at least 0.13 apart, so a 1 % resistor and a 12-bit ADC tell them apart
easily. *Proposal:* nothing reads ID yet, and rev A leaves R_ID unfitted.

## 5. What a key carries

- **One signing key, generated inside the chip,** that never leaves it. This standard says nothing
  about how a key is provisioned. That's in [PROVISIONING.md](../../docs/PROVISIONING.md).
- **A visible serial.** Put the chip's serial or its short form on the silkscreen or the label, so
  that a person can match the key in their hand to the owner on the Safe.
- **No other active parts on the bus.** A glow LED is fine if it runs off VCC and draws within the
  budget above.

## 6. Checking a key or a console

**A key passes when:**
- DETECT to GND reads under 1 Ω.
- VCC to GND doesn't beep, and reads more than 10 kΩ.
- SDA and SCL don't beep to GND, to VCC or to each other.
- In a reference console, `import bench1` scans it at a reserved address and reads its serial.

**A console passes when:**
- With no key in, VCC reads 0 V, and SDA and SCL float.
- With a test plug in that has DETECT tied to GND and nothing else, VCC comes up after about 200 ms,
  the console scans, finds nothing, says "not a key", and turns VCC off.
- Pulling a rev A key out while it is signing leaves the key working on the next insert.

## 7. Versions

This is version 0. A version 0 key and a version 0 console are compatible. A change that breaks
that, such as a new pin assignment, a new voltage or a different blade, makes a new version. A new
version uses a different key-slot position, so old keys don't fit new sockets.

Open before version 1:

- [ ] Seat rev A in the Sullins and EDAC sockets, and confirm the width, the finger depth and the
      keying
- [ ] Pick the key-slot style (in-contact or between-contacts)
- [ ] Measure ATECC608 and Trust M peak current, and settle the 100 mA budget
- [ ] Try the ID codes on a real ADC
