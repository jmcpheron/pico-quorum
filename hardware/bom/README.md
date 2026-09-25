# bom

## First parts order

- [ ] Raspberry Pi Pico 2 W (×5; see [Picos](#picos))
- [ ] Adafruit ATECC608 breakout, STEMMA QT (×2–3), which the current firmware drives
- [ ] Adafruit Trust M breakout (×2–3), for evaluating `firmware/trustm.py`
- [ ] Momentary push buttons, thumb-sized, in green and red (a few candidates to compare feel)
- [ ] Flip-up switch cover or guard hardware
- [ ] ¼″ stereo plugs (solder type) and ¼″ stereo **switched** jacks, with extras (see [Jacks](#jacks-and-plugs))
- [ ] 3.5 mm stereo plugs (solder type) and 3.5 mm stereo **switched** jacks, with extras
- [ ] Optional: a cheap pack of plain 3-pin 3.5 mm TRS jacks for breadboard tests
- [ ] Rotary encoder with push switch
- [ ] 2.0″ and 2.8″ 320×240 screens, one each to compare
- [ ] Load-switch and ESD/TVS parts, or breakouts for prototyping
- [ ] Status LEDs and assorted resistors and capacitors

## Jacks and plugs

- **Console jacks must be switched.** A plain "3-pin" TRS jack has only tip, ring and sleeve
  contacts. The console turns key power on only after a switch contact in the jack confirms the
  plug is fully in (see [`../wiring/README.md`](../wiring/README.md)), so both jacks need extra
  switch contacts, usually sold as "switched" or "5-pin". Check the datasheet: the switch
  should open or close on insertion, not just touch the tip.
- **Why it matters:** VCC is on the 3.5 mm tip. While a plug slides in, the tip brushes past the
  ring and sleeve contacts, so without detection key power is live during insertion.
- **Plain 3-pin jacks are fine for the bench**, for example a 10-pack of 3.5 mm TRS panel jacks
  for about $8 (Amazon, GDQLCNXB store, 2026-09). Use them to wire a Trust M or ATECC608
  breakout through a real TRS connection and see how I2C behaves through the contacts. Don't
  design the console bracket around them.
- **Keys need plugs, not jacks:** solder-type ¼″ TRS and 3.5 mm TRS plugs, one of each per key.

## Picos

- **Pico 2 W** (RP2350) is the one with secure boot: boot only firmware signed with your key,
  plus Arm TrustZone and one-time-programmable (OTP) memory. The original Pico and Pico W
  (RP2040) have none. The console also needs the W for Wi-Fi.
- **Enabling secure boot writes OTP fuses and cannot be undone.** After that the board runs
  only signed images, which means building and signing MicroPython yourself. Buy about 5:
  - 2 unlocked development consoles
  - 2 for secure-boot experiments you can afford to get wrong
  - 1 spare
- **Check the RP2350 stepping** printed on the chip. Raspberry Pi's 2025 hacking challenge found
  fault-injection attacks on early RP2350 chips, and a later stepping fixed some of them. Worth
  knowing before relying on secure boot; not a reason to wait.

Add part numbers, prices and links as they get picked. The inherited picowallet parts list is in
the upstream half of [`../../README.md`](../../README.md).
