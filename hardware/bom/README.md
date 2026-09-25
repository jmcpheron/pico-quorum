# bom

## Ordered: first prototype parts (2026-09-24, Amazon)

Two orders, both due 2026-09-25. Descriptions are the listing titles, some cut short. Rows marked
**check** have a detail the listing doesn't settle and that changes the wiring. Check those when the
box arrives and fill in the result.

| # | part (listing title) | qty | for | notes |
|---|---|---|---|---|
| 1 | Lonely Binary 6-Pack SPI TFT LCD Display Kit, 0.96″–3.5″, for 3.3 V MCUs | 6 screens | console screen candidates | Covers the 2.0″ vs 2.8″ comparison in KICKOFF, and more. **Check:** list each module below |
| 2 | uxcell a12062600ux0366, 3-pin PCB-mount female 3.5 mm stereo jack | 10 | console key socket, 3.5 mm side | TRS, 3 pins. **No switch contacts**, so it can't detect insertion |
| 3 | DaierTek SPST momentary soft-touch foot switch, normally open, 2-pin (stomp box) | 13 | Sign and Reject button candidates | Metal stomp-style actuator, light touch. Color comes from a cap or the panel |
| 4 | Konohan EC11 rotary encoder, with knobs | 10 | paging dial | EC11 with push switch: 3 pins (A, C, B) plus 2 for the switch |
| 5 | 3.5 mm TRS 3-pole stereo male plug, solder type ("repair plug") | 10 | key, 3.5 mm side | |
| 6 | Auto-plaza 1/4″ enclosed **mono** jack | 10 | console key socket, ¼″ side | Mono means tip and sleeve only, no ring, so the draft TRS pinout won't fit (see [wiring](../wiring/README.md#prototype-pinout-rev-p)). **Check:** does it have a third lug (a tip switch)? |
| 7 | Pancake 1/4″ (6.3 mm) plugs, right angle | 10 | key, ¼″ side | Low-profile right-angle plugs suit a key handle. **Check:** mono (TS) or stereo (TRS)? Solder or screw terminals? |
| 8 | MEETOOT 18650 battery negative spring contacts (spring + plate) | 40 | console battery holder built into the case | Same power circuit as [`SOLDERING.md`](../../SOLDERING.md) §2 |

Order totals were $64.64 (the screen kit) and $97.53 (items 2–8).

### Arrival checklist

- [ ] Screen kit: record each module (size, resolution, controller printed on the back, pin labels,
      touch or SD slot, whether the backlight pin has its own transistor)

  | size | resolution | controller | pins | notes |
  |---|---|---|---|---|
  | | | | | |

  Kits like this often ship ST7735 (0.96″, 1.8″), ST7789 (1.3″/1.54″, 2.0″), ILI9341 (2.4″/2.8″)
  and ILI9488 or ST7796 (3.5″) modules, but go by what's printed on the board.
- [ ] ¼″ jack (#6): 2 lugs or 3? With a meter, find which lug touches the tip spring with nothing
      plugged in. That third lug is the tip switch.
- [ ] Pancake plug (#7): TS or TRS?
- [ ] EC11 (#4): check detents per turn and whether it pulses once or twice per detent. Firmware
      needs to know.
- [ ] Foot switch (#3): press it with a thumb. Is it too stiff for Sign or Reject? Measure the
      mounting hole (usually 12 mm).
- [ ] 3.5 mm jack (#2): map the 3 pins to T, R, S with a plug and a meter.

## First-order checklist (from KICKOFF)

- [ ] Raspberry Pi Pico 2 W (×2): not in these orders. Confirm on hand
- [ ] Adafruit ATECC608 breakout, STEMMA QT (×2–3): not in these orders. Confirm on hand
- [ ] Adafruit Trust M breakout (×2–3): not ordered yet
- [x] Momentary push buttons: DaierTek soft-touch foot switches (#3). Thumb-sized arcade or panel
      buttons in green and red are still worth trying for feel
- [ ] Flip-up switch cover or guard hardware: not ordered yet
- [ ] ¼″ plugs and jacks: partly. Ordered **mono** (#6, #7), not stereo switched. Works with the Rev P pinout
- [ ] 3.5 mm plugs and jacks: partly. Ordered (#2, #5), but the jacks aren't switched
- [x] Rotary encoder with push switch (#4)
- [x] 2.0″ and 2.8″ 320×240 screens: in the 6-pack (#1), if the check above confirms it
- [ ] Load switch and ESD/TVS parts: not ordered yet
- [ ] Status LEDs, resistors, capacitors: not ordered yet

## Still needed

Enough for two consoles and a handful of keys. For the bench prototype (Proto 0/1 in
[wiring](../wiring/README.md#prototype-stages)):

| part | qty | why |
|---|---|---|
| Pico 2 W, ATECC608 breakouts | if not on hand | brains and keys |
| Solderless breadboard, male-male and male-female jumpers | 2 | Proto 0 |
| Resistor kit (at least 47 Ω, 330 Ω, 1 kΩ, 4.7 kΩ, 10 kΩ, 100 kΩ) | 1 | pull-ups, LED, key VCC limit, battery gauge |
| Ceramic capacitors, 100 nF and 10 nF | 20 | decoupling, encoder RC |
| 5 mm or 3 mm LEDs (green, red, amber) | a few | status LED |
| P-channel MOSFET, logic-level (AO3401 on a SOT-23 adapter, or a through-hole part rated for V<sub>GS</sub> −2.5 V) | 5 | key VCC switch for Proto 1 |
| 1N5817 Schottky, protected 18650 cells, SPST switch | per [`SOLDERING.md`](../../SOLDERING.md) | console battery |
| Latching power switch (3PDT stomp, as upstream, or a toggle) | 2 | KICKOFF calls for latching. The DaierTek switches are momentary |
| Perfboard, 26–30 AWG hookup wire, heat shrink, header pins | | Proto 1 |

For the real console (Proto 2):

| part | qty | why |
|---|---|---|
| Current-limited load switch, e.g. TI TPS2553 (adjustable limit, SOT-23-6) or Diodes AP22802 | 5 | key VCC, per the design rules |
| 4-channel low-cap TVS array, e.g. TI TPD4E05U06 | 5 | ESD on VCC, SDA, SCL at the jacks |
| Switched 3.5 mm jacks (5-pin PJ-307/PJ-313 style) | 5 | only if the ¼″ tip switch can't detect insertion |
| Stereo (TRS) ¼″ switched jacks + TRS plugs | 5 each | only if we go back to the draft TRS pinout |
| SOT-23 / SOT-23-6 breakout boards | 10 | to prototype the SMD parts above |

Add part numbers, prices and links as parts are picked. The inherited picowallet parts list is in
the upstream half of [`../../README.md`](../../README.md).
