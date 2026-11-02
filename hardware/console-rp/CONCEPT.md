# console-rp rev B: a board you can count the parts of, built end to end by JLCPCB

*Concept, 2026-11-02. A plan: nothing drawn, ordered or flashed. Rev A ([README.md](README.md)) was
never ordered, so rev B edits the design in place at the next round; rev A's renders stay as the
before picture. Prices and stock are JLCPCB's and LCSC's on the date given.*

Rev A is the console on a bare RP2350A with no radio: USB-C power, a CH343P serial bridge, the
ATECC608C on the board, a 1.14″ panel in a ZIF. Two things ask for a revision.

1. **The Ledger reseller implants, October 2026.** Devices sold through an authorized reseller
   carried an extra board that read recovery phrases off the screen and sent them over cellular.
   Ledger's chip check and Trezor's signed-firmware check both pass such a device: the real chip and
   the real firmware are untouched. The answer proposed in the trade press (Joe Grand, Cointelegraph,
   2026-10-14) is an enclosure that shows the parts, so an extra radio has nowhere to hide.
2. **A panel fitted by hand doesn't scale, and is a seam.** Rev A's panel is bought apart, clipped
   into the ZIF and stuck on foam by hand. Every ribbon and ZIF is a place to put a tap, and a panel
   a person fits is a panel another person can swap.

So rev B aims at a board that is cheap, that JLCPCB builds whole, and whose owner can check with a
phone camera, a part count and a USB power meter. Not "secure" and not "audited": *tamper-visible*.
An owner can check the count, the outlines, that J3 is empty, the tail's length, that nothing sits
between glass and board, and the current it draws. An owner can't check traces, firmware or the chip
by looking; those stay with the fingerprint and the key's attestation ([ATTESTED-KEYS.md](../../docs/ATTESTED-KEYS.md)).

## Panels JLCPCB solders itself

JLCPCB's assembly library (Displays, LCD Screen, read 2026-11-02) has three ST7789 SPI panels marked
"assembly supported, Standard only, wave soldering, difficulty high". Wave soldering on a panel means
the factory solders its FPC tail to pads, by hand or hot bar; it isn't a reflow part.

| LCSC | part | size | panel | stock | 1 pc | notes |
|---|---|---|---|---|---|---|
| C2890618 | Wisevision N114-2413THBIG01-H13 | 1.14″ | 240 × 135 ST7789V | 517 | $1.91 at 48 | the size rev A draws for |
| C5329582 | HS HS20HS072RX | 2.0″ | 320 × 240 ST7789T3, FPC tail, four LEDs at 80 mA, 51.8 × 36.2 mm | 1,410 | $3.59 | `board.py` already runs a "2.0" as 320 × 240 landscape |
| C5329583 | HS HS24CG003-ARX | 2.4″ | 320 × 240 ST7789 | 362 | $4.09 | the same, bigger |

All three are Extended. **No 1.3″ or 1.54″ 240 × 240 panel is in the library,** so the `waveshare`
pages can't be machine-placed today. A consigned panel (LCSC or Taobao: "1.3 inch IPS 240x240 ST7789
12PIN", "1.54 inch 240x240 ST7789 FPC") is possible on Standard assembly, with a handling fee and
minimums not yet asked; not for a first order. The 1.54″ 128 × 128 SH1107 OLED (C5123566, $3.84) is
placeable but 128 × 128 is below even the small page set's 160 × 128 (`board.py`'s `SMALL`).

**Both panels mean new firmware.** `feather-s3` is an ESP32-S3 pin map; console-rp needs a profile of
its own either way, and that is a new release fingerprint (AGENTS.md rule 2).
- **B1, the 1.14″:** the `THREE` 240 × 135 pages (`quorum_ui_s.py`) on new pins. The board, D0 D1 D2
  and `slot()` stay as drawn. The least work.
- **B2, the 2.0″:** `THREE` on 320 × 240 too (`RAIL_Y`, the footer slots), a board of about 85 × 42 mm
  (measure the part), and a backlight decision. Four LEDs at 80 mA on top of the board's 0.12 A puts
  the XC6206 at its 0.2 A rating and about 136 °C over the air by the datasheet's figure. Three ways
  out: run the backlight at 20–30 mA by PWM on GPIO13 (indoors that is plenty); feed it from VBUS
  through Q1 with an 0805 series resistor; or an AP2112K-3.3 (600 mA, SOT-23-5). Bigger text for
  addresses is the reason to do this.

Which goes first is decided at order time. Step 1 below gates both.

**To verify at order time,** since the part pages hide them and the datasheets sit behind LCSC's
scripts: the FPC's pin count, pitch and order; whether the factory peels and sticks the panel's own
tape, or the glass hangs on its tail; and where the glass lands, to what tolerance.

## What the board must give a factory-soldered tail

- Pads from the panel's datasheet: 2.5–3 mm long, mask-defined with about 0.1 mm relief, no via in
  a pad or within 0.5 mm of one (`tools/jlc` check 5 holds this already).
- A silkscreen line where the FPC's end and edge sit, so the operator lines it up.
- A bare strip under the flex's run, and about 3 mm clear on the hot bar's side.
- Pads the tail reaches **without a fold**, at the glass's edge. A fold is a hand step again, and rev
  A's 1.14″ tail is short: measure it against the pad row before the layout.
- The glass as a keep-out *and* a courtyard, so DRC catches a part under it. Rev A allows `LCD1` no
  courtyard in `jlc_spec()`; rev B drops that allowance.
- A CPL row for the panel with a real centre and rotation. JLCPCB's placement preview is where the
  glass's position is confirmed.
- The buttons align to the board, not the panel: a hand-set panel lands within about ±0.5 mm, and
  `slot()` puts D0 D1 D2 under the footer slots to 0.1 mm. The case's window gets 1 mm of slack.

## Standard assembly: what it costs

Rev A quotes Economic. From what the repo already records: Economic fees are $8.18 setup, $1.53
stencil and $3.07 a feeder ([console-s3's CONCEPT.md](../console-s3/CONCEPT.md#cost), 2026-10-22);
Standard needs a 70 × 70 mm panel with rails and fiducials and costs about $25 setup a side plus
handling and fixtures ([key-pcb's ORDERING.md](../key-pcb/ORDERING.md)), about $55 an order in all.
So **about $45 an order over Economic: about $9 a board at 5, about $2.25 at 20,** before the panel's
own Extended fee and whatever "difficulty high" adds. Rev A's 72 × 36 mm goes 2-up to reach 70 × 70.
JLCPCB X-rays QFN and BGA joints as a matter of course; it sells no potting or coating.

## The moves, ranked

### A. Countable

1. **No part on the back.** Already so. The pour and the vias stay (Raspberry Pi's DVDD tracks run
   there). Add one silkscreen line: *nothing is fitted on this side*.
2. **Nothing under the glass.** The pad row, the backlight switch and the 0402s move out from under
   the panel. That removes *our* parts from the hidden volume; it doesn't remove the volume, and that
   volume is where a Ledger-style implant goes. **Open, both answers stated:**
   - (a) **a cutout in the board under the glass,** the panel bridging it on its long edges. A phone
     camera from the back then sees nothing between glass and board. It costs routing room.
   - (b) **the panel flat on its own tape,** no foam, about 0.3 mm gap, the glass's outline printed on
     the silkscreen so a lifted edge shows. Cheaper, less checkable.
   The panel module is the one black box either way: a chip on glass under tape, on a multi-layer
   flex. Say so. (a) plus a thickness and photo comparison is the compensation, not a pretence.
3. **A part census the generator writes.** Not "6 chips": U2, U3, Q1 and Q2 are all SOT-23, and a
   seventh SOT-23 would pass. The whole count, derived from `PARTS` so it can't go stale, on the
   silkscreen: *N parts: 6 ICs, 4 SOT-23, 1 inductor, 1 crystal, 5 switches, 1 LED, M 0402s*. A
   silkscreen outline round every fitted part. The rule for an owner: every part inside an outline,
   no outline empty, and anything bigger than a grain of rice that isn't on the list is wrong. An
   MFF2 eSIM is 5 × 6 mm; the smallest cellular modules are 10 × 10 mm. Neither fits in an 0402's
   outline.
4. **One connector.** The USB-C, and nothing else. The ZIF goes (the pads replace it). J3 stays as
   bare holes, tinned and empty in the reference photo, with a silkscreen note that anything
   soldered there is a tamper sign. Bare holes are the easiest place to solder an implant, so the
   note has to say it.
5. **Two layers.** The only copper is the copper you can see; no inner layer can carry a trace
   antenna. Green or yellow mask, the clearest over copper at JLCPCB's prices; not white, not black.
   Don't claim an owner can check traces by eye: nobody compares 0.2 mm lines to a Gerber.
6. **Reference photos, in [renders/](renders/)** keyed by board revision and commit: parts side and
   back, at a stated scale and lighting, and a "phone-camera check" paragraph that says what to
   compare. Not in `docs/releases/`: those files never change after a tag, and the board is not the
   firmware. The back silkscreen carries the revision and a URL that lands on the photos; that is
   rev A's open picoquorum.dev item.
7. **The USB meter is the radio detector.** The board draws under 0.12 A, and its regulator can't
   feed a modem, so an implant must draw from VBUS; a cellular burst is hundreds of milliamps to 2 A.
   Print the expected draw by the USB-C (the generator knows it: `jlc_spec()`'s regulator amps) and
   tell owners to plug in through a $10 USB-C meter. Anything over it, or any burst, is foreign.
8. **No battery.** An implant runs only while the console is plugged in, and the owner is looking
   at the screen. The Ledger implant relied on its own power. State it as a property.
9. **A clear case.** Two laser-cut acrylic sheets on the existing H1–H4 holes, four screws, the
   parts side photographable through it. Not JLC3DP's Transparent 8001 SLA first: it comes out
   cloudy and yellows. Tamper-visible, not tamper-evident; no stickers, which are cheap to fake, as
   Ledger itself says.

### B. The BOM is a whitelist

A "no radio, no battery part" rule can't be checked as a category: `tools/jlc/parts.json` has no
category field. The stronger rule: **every LCSC number in the BOM is in `parts.json`, and
`parts.json` is the whitelist.** A part not read and written down there doesn't get placed.

### C. Not now, with the reason

- **RP2350 secure boot with a vendor key.** It locks the owner out of an open console, and it has
  published bypasses (Muench, Courdesses, Hextree, 2024–25). Revisit as an owner-burned key.
- **Potting or a tamper mesh.** It hides the board, the opposite of the aim, and JLCPCB doesn't
  sell it.
- **Dropping the bench USB pair (R13, R14) from J3.** A person with the board has SWD anyway, and it
  removes the UF2 bring-up path. It stays rev A's $3 Extended-fee question, not a security move.
- **The RP2354A** (flash in the package, one chip fewer to count): sold by the reel, not at LCSC.

## Open

- [ ] Under the glass: the cutout, or the panel flat on tape.
- [ ] Which panel first; the backlight's power if the 2.0″.
- [ ] Does the factory stick the glass down, or does it hang on its tail.
- [ ] The acrylic case drawing, and the Sign button's guard: the open item on every console board.
- [ ] `fab/bom.csv` beside this file is an earlier write of the BOM (the same parts, in another
      order); the fab files are in `console-rp/fab/`. Remove it at the next generator run.

## Steps, in later rounds

1. **Buy one of each candidate panel,** as a parts pre-order or a two-board Standard run with only
   the pad row on it: the pin order, the pitch, how the glass is fixed, and the real Standard fee.
   Nothing is written to any board.
2. **Edit `gen_console_rp.py` in place:** the pad footprint, the glass's keep-out and courtyard, the
   part census and outlines, the back-side line, the current label; then `tools/keypcb
   gen-console-rp check` and `tools/keypcb jlc console-rp`.
3. **A `console-rp` firmware profile,** a new release fingerprint, once a board exists.
