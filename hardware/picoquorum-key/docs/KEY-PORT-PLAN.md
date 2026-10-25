# Plan: an optional key port on PicoQuorumKey

*Drawn up 2026-10-25. A plan, not a design: nothing here is in `circuit.py` yet. Written for whoever
takes it on. It assumes the board is [picoquorum-key rev A](DESIGN.md), 44 × 53 mm, the module on
the back with its antenna at the top edge, right of centre. If the board meant is console-s3 the
circuit and the firmware parts hold as written; only the geometry section changes.*

## What it is

A place at the top-left corner of the board for a right-angle USB-C **plug** that points up out of
the top edge, next to the module. A [key-c](../../key-pcb/key-c-usbc/README.md) slides onto it. The
soldered ATECC608C (U2) stays. The port is a set of pads and footprints on every board, and its
parts are fitted only on the boards that want it. Nothing on a board without the port's parts does
anything.

The circuit behind the plug is the one the repo has already worked out twice, for console-a's key
port and for the [feather-wing](../../feather-wing/README.md): a current-limited power switch, ESD
on every line, pull-ups to the switched rail, and CC sensing so the console knows a key is in. Two
things are new here: the port gets **its own I2C bus**, because the soldered chip and a key-c both
answer at 0x60, and the key's power is **off by default**, so a board whose firmware doesn't know the
port never powers whatever is plugged into it.

## Decisions to make first

These change the drawing, so settle them before anyone opens `circuit.py`.

| decision | recommendation | why |
|---|---|---|
| Which plug | A **surface-mount horizontal plug** that sits on the front face with its tongue past the edge, so it works on a 1.6 mm board. Fallback: SHOU HAN's straddle plug TYPE-C 24P-GTJB 040 (C3151751), which wing-b uses, and a **0.8 mm board** | Every straddle plug grips the board between two rows of contacts and wants 0.80 ± 0.05 mm (wing-b's drawing). A whole 44 × 53 board at 0.8 mm flexes under the buttons and the glass. I found no stocked LCSC number for a horizontal male plug on 2026-10-25; LCSC's "Type-C plug" category and the makers' catalogues (SHOU HAN, Vistar) have them. Confirm stock and get the drawing before the footprint is drawn |
| Rev A or rev B | **Rev B.** Order rev A as planned and learn the panel and module fit from it | The port grows the board and moves the antenna rule area. Folding it into rev A re-routes the whole board before the first one has been in a hand |
| Where the port's parts go | **Front face, in a 6 mm strip added on the left**: the board becomes about 50 × 53 | Economic assembly places the front only. The front's top-left is full: D0–D2 at X 4.5 and the glass from X 9. The back's top-left is empty but is hand-soldered territory on Economic runs. Alternative, if the big batch goes to Standard two-sided assembly anyway: keep 44 × 53 and put the port's parts on the back beside the module ([below](#the-back-face-alternative)) |
| Which key signs when both are in | **The plugged key, when CC shows one and it is pinned; otherwise the soldered chip.** Shown on the splash and the Sign page | A product decision, not a hardware one. The firmware needs an answer before the port is useful. `secrets.QUORUM_EXPECT` already pins a list of chips (`policy.pick`) |

## Why its own bus

The soldered U2 is at 0x60 on GPIO16/17. A key-c is an ATECC608C at 0x60 too. Two chips at one
address on one bus both answer and neither is readable. The ways round it:

| way | cost | verdict |
|---|---|---|
| **A second I2C bus** on two spare GPIOs | two tracks, the pull-ups the port needs anyway; firmware learns a second bus | **do this** |
| Re-address U2 at the ceremony (config byte 16, before the config lock) | nothing on the board; every board's ceremony must set it, and a chip locked at 0x60 can't be changed. The two chips still share one bus, so a key going in or out can glitch a transaction with the soldered chip, and ESD at the plug lands on U2's lines | no |
| An I2C switch (PCA9543 or alike) | an extra part, and firmware changes anyway | no |
| Pads in parallel with U2's bus, as console-s3's test pads | works only when one chip is on the bus | not for this |

The S3 has two I2C controllers and routes them to any GPIO. The second bus keeps everything that
happens at the plug (hot-plug bounce, ESD, a shorted key, the pull-ups going away when VKEY is
off) off the soldered chip's lines. The pull-ups go to the switched rail, as on wing-a, and since
nothing else is on this bus there is no battery-gauge problem to work around
([feather-wing](../../feather-wing/README.md#pins), "switching the key off needs the bus of its own").

Keep `_pulled_up(16, 17)`, the board ID in `firmware/board.py`, untouched: the new bus is on other
pins.

## The circuit

```
+3V3 ──┬── U5 AP22653W6-7 ──┬── VKEY ── plug A4, A9 (and B4, B9 on a 24-pin plug)
       │   EN ── KEY_EN ── R15 100k ── GND     (off until firmware drives it high)
       │   ILIM ── GND (80 mA)                 FAULT ── KEY_FAULT, R16 10k to +3V3
       C9 100n at IN, C10 10 µF at OUT, D3 ESD5Z5V0 VKEY to GND at the plug
       │
       ├── R17 47k ── KEY_CC ── R18 1k ── plug A5           key-c's 5.1k Rd reads ~0.32 V; open reads 3.3 V
       │
KEY2_SDA ── R19 2.2k ── VKEY        plug A6 (D+)   ┐ U6 USBLC6-2SC6 at the plug, its rail on +3V3
KEY2_SCL ── R20 2.2k ── VKEY        plug A7 (D−)   ┘ never on VKEY
KEY_LED ── R21 100 Ω ── plug A8 + B8 (SBU), D4 ESD5Z5V0   ┐ U7 USBLC6-2SC6 covers CC and LED
KEY_LED ── R22 1k ── D5 green 0603 ── GND, beside the plug ┘
plug A1, A12, B1, B12, shell ── GND
```

Line by line, and where it differs from wing-a:

- **U5, the power switch** (AP22653W6-7, C2158037, extended): 80 mA limit, reverse blocking, output
  discharge, from always-on 3V3. The key needs under 20 mA. Reverse blocking is what stops a
  charger on an A-to-C cable putting 5 V onto 3V3 ([PROPOSALS.md](../../key-pcb/PROPOSALS.md#the-console-end-of-key-c)).
  **EN is pulled down, not up.** wing-a pulls it up so today's image powers the key with no firmware
  change. Here the second bus needs new firmware anyway, so the safer default costs nothing: a key
  on a board running an older image, or a board with the port's parts and no firmware for them,
  gets no power. C10 stays at 10 µF: U5 has to discharge it when the key goes off.
- **CC, one line, 47k.** Plugged straight onto a plug, a key-c shows a 5.1k Rd on both of its CC
  pins, so A5 meets one whichever way up (wing-b's reasoning). B5 (VCONN) stays open. With 47k
  instead of wing-a's 10k the line reads 0.32 V with a key and 3.3 V without, a clean digital
  low/high, so a plain GPIO with an interrupt does it and no ADC read is needed. Put it on an
  ADC1-capable pin anyway, so a later image can read a KEY ID resistor value
  ([key-pcb](../../key-pcb/README.md#the-fingers)). **R17 is fitted on every board**, port or not:
  it is what makes a board without the port read "no key" instead of a floating pin. Firmware
  enables the internal pull-up too, as a belt.
- **Pull-ups to VKEY, 2.2k.** The key has none. On VKEY, a key that is off isn't powered through
  its I2C pins. 2.2k because the plug's capacitance plus the key's is more than the soldered chip's
  2 cm of track; the ATECC608C wants a 300 ns rise.
- **ESD.** U6 on SDA/SCL and U7 on CC and LED, both USBLC6-2SC6 with their rail on 3V3, never on
  VKEY, so the CC pull-up can't feed the key through them. D3 on VKEY, D4 on the LED line, both
  at the plug.
- **The LED.** One GPIO, KEY_LED, drives two LEDs: D5 on the board beside the plug through 1k, and
  the plug's SBU pins through 100 Ω for a key-c P3's own LED ([its README](../../key-pcb/key-c-usbc/README.md#p3-the-led)).
  A8 and B8 are joined so one meets the key's B8 either way up. A P2 key has nothing on SBU and
  stays dark. Meaning, for the firmware: off, no key; on, key powered and read; blinking, a
  transaction waits for this key, as the status LED does today. wing-a drives the key's LED from
  the status LED pin instead, to need no firmware change; here a pin of its own is cleaner, since
  the firmware changes regardless.
- **FAULT** is a nice-to-have: it lets the console say "key port overload" in red instead of
  showing nothing. Drop R16 and the pin if the GPIO is wanted elsewhere.
- **The plug's pads.** A1, A12, B1, B12 and the shell to GND. B6, B7, B5 open. On a 16-pin plug there
  is no B row to speak of; wire what it has by the same names.

Nothing here adds a way to sign or to read a key out (rule 3). A plugged key signs the same hash,
through the same `quorum.sign_it`, as the soldered one (rule 1). AGENTS.md says not to add a new
way to sign without asking: this plan is the ask, and the answer is the person who ordered it.

## Pins

Proposed, from the module pins rev A leaves unconnected ([PINS.md](PINS.md)). None is a strap (0, 3,
45, 46), none is 35–37 (octal PSRAM), and 16/17 stay as they are. Pins 38 and 39 are at the top of
the module's left column, the castellations nearest the top-left corner, so the lines that go to
the plug go there. `tests/test_pin_contract.py` holds PINS.md, `circuit.py`, the board and the
firmware profile to one table, so every new line goes in all four.

| function | GPIO | module pin | net | electrical |
|---|---|---|---|---|
| key port CC | 1 | 39 | KEY_CC | 47k to 3V3 (always fitted), 1k to the plug's A5; ADC1_CH0 for later |
| key port enable | 2 | 38 | KEY_EN | 100k to GND; high = key powered |
| key port SDA | 38 | 31 | KEY2_SDA | 2.2k to VKEY; `I2C(1)` |
| key port SCL | 39 | 32 | KEY2_SCL | 2.2k to VKEY; `I2C(1)` |
| key port LED | 13 | 21 | KEY_LED | 1k to D5, 100 Ω to the plug's SBU |
| key port fault | 47 | 24 | KEY_FAULT | 10k to 3V3; low = overload (optional) |

TP9 and TP10 carry IO1 and IO2 today. They become KEY_CC and KEY_EN pads, which is useful on the
bench; `tests/test_silk.py` checks their labels against their nets, so the back silk changes with
them. Add two pads for KEY2_SDA and KEY2_SCL, so a key on wires can stand on the port's bus too.

## Where it goes

Numbers are from rev A's geometry table in [DESIGN.md](DESIGN.md). Recommended: the board grows
6 mm to the left, and everything rev A has keeps its place relative to the glass. In the new
frame rev A's X is X + 6.

```
 X:  0    3.5     12.5  15                             46  50
 Y 0 ╭─────┬────────┬────────────────────────────────────────╮
     │     │  plug  │ (body on the front, tongue up out     ░│   plug centred X ~8, body Y 0–7
     │     └────────┘  of the top edge)      ░ antenna band ░│   rule area now X 29.5–48.5 only
   7 ├─────┬────────────────────────────────────────────────┤
     │ U6  │ [D0]  ┌──────────────────────────┐ C3 C5     │
     │ U7  │       │ glass 31.0 × 17.6     ┌──┐╮          │
     │ D3  │ [D1]  │                      │J2│ )fold      │
     │ U5  │       │                      └──┘╯           │
     │ Rs  │ [D2]  └──────────────────────────┘ R6 R7     │
  26 ├─────┴────────────────────────────────────────────────┤
     │(o) D5  Q1 Q2 cluster   LED   U2 UDFN            (o) │
     ...
 back: WROOM-1 at X 30–48, Y 0–25.5, antenna end on the top edge
```

- **The plug** at the top-left corner, body on the front face, centred about X 8 so a key-c
  (16 mm wide) sits over the board, X 0–16, not past its edge. The shell's near side is then at
  about X 12.5, some 17 mm from the antenna rule area's near edge (X 29.5 in the new frame). The
  body (about 9 × 7 mm on a horizontal plug) sits in Y 0–7, above D0's cap, which starts at
  Y 8.45. Espressif's guidance for the PCB-antenna modules is to keep metal and copper clear of
  the antenna area and, where it can be had, about 15 mm from metal: so place the plug as far
  left as the key-c's width allows, and **measure Wi-Fi on the first board** (RSSI with no key,
  with a key-c in, and with the plug's pads bare). A key-c is a 16 × 36 mm board with a ground pour, standing 36 mm up beside
  the antenna; that, more than the shell, is the thing to measure.
- **The antenna rule area** shrinks from the full-width band (`ANT_BAND`, Y 0–7) to the module's
  antenna area plus 0.5 mm each side, the way console-s3 draws it (its 18 × 6 mm area and 0.5 mm,
  with the edge free beyond). Copper can then run to the plug's pads. Keep the band's Y 0–7 free
  of pour under the rest of the top edge anyway; the plug needs the room, not a pour.
- **The 6 mm strip**, X 0–6, Y 7–26: U5, U6, U7, D3 and the resistors, in a column. SOT-23-6 parts
  are 2.9 mm wide, so a single column fits with 0.2 mm clearance to the D0–D2 caps at X 8.25
  (rev A's 2.25 + 6). D5 and its resistor below Y 26, left of the Q1/Q2 cluster, where it shows
  under the glass's bottom-left corner.
- **Tracks.** KEY_CC, KEY_EN go to module pins 39 and 38 at the module's top-left corner: a run
  along Y ~8, under the glass, on the back. KEY2_SDA/SCL to pins 31 and 32 at the bottom-left of
  the module. KEY_LED and KEY_FAULT to the module's bottom edge. Nothing new crosses the fold
  window (Y 13.9–23.0 beside the glass's right edge) or the M2 keep-outs.
- **The mounting holes.** H1 and H3 stay 3 mm from the left edge, which is now 6 mm further out.
  A case made for rev A doesn't fit rev B; say so in the mockup README.
- **Mechanical.** The plug's 0.5 mm pads cannot take the pull of a key coming off. Choose a plug
  with shell legs on pads of their own (through-hole legs if a horizontal plug offers them), and
  make the case carry the load: keepers either side of the shell as the pigtail case v2 has
  them ([feather-pigtail](../../builds/feather-pigtail/README.md#v2-2026-10-24-the-plug-in-a-pocket)).
  The key-c stands 36 mm out of the top edge, over nothing: the case needs a slot and a recess for
  its board either way up, and the mockup (`tools/mockup`) and `tests/test_3d.py` need a key-c
  model on the plug to check it clears the glass, the module and the case.

### The back-face alternative

If the batch that gets the port is assembled Standard on both sides (CONCEPT.md puts that past
about 20 boards, and the module then goes on by machine too), the port can go on the **back**
beside the module and the board stays 44 × 53. The back's X 0–24, Y 0–35 is empty except the
test pads at Y 35 and 39. The plug sits at the top-left corner of the back face with its tongue
up; the key-c still comes out of the top edge, just offset to the back by the board's thickness.
Economic runs would then hand-solder the plug if they want it: 16 or 24 pads at 0.5 mm, harder
than the module's 40 at 1.5 mm. Pick this only if the small runs never want the port.

## How "optional" works in the files

The generator already does this for the module: U1 is `dnp=True`, so it is on the board and off
the assembly BOM and CPL (`export.sh` passes `--exclude-dnp`; `jlc_bom_cpl.py` drops DNP rows).
Extend that one notion:

1. In `circuit.py`, a `fit` field on `Part` (default `"base"`), `fit="port"` on every port part
   except R17, which is base. `gen_sch.py` writes `dnp=yes` for parts whose group isn't selected.
2. `tools/build_board.sh --variant port|base` chooses which groups are fitted, and
   `tools/export.sh rev-b` runs the export twice: `hardware/out/rev-b/` with `bom.csv`, `cpl.csv`
   (base) and `bom-port.csv`, `cpl-port.csv` (port). **One Gerber zip for both**: the copper,
   mask, paste and silk don't change with the variant. A test asserts the two exports' Gerbers
   are byte-identical and that every `fit="port"` reference is in one BOM and not the other.
3. Ordering a batch: upload the one Gerber zip; for the boards with the port, upload the `-port`
   BOM and CPL. JLCPCB bills the extra part types (the plug, U5, two USBLC6, the TVS: about five
   extended lines) only on that order.
4. Silkscreen is the same on both variants, so it says **KEY PORT** by the plug's outline and no
   more. On a bare board that reads as "a port could go here", which is true. The back's
   `ONE OWNER / ONE KEY` legend is no longer true of a port board; make it `ONE OWNER` with the
   key outline, or move it.
5. The paste layer carries the port's pads on every board. On a base board the stencil opens them
   and the machine puts paste on pads with no part. JLCPCB accepts that; if it ever asks, the
   answer is "DNP, intended". The exposed HASL pads on a base board are a cosmetic matter only.
6. The mockup STL and the renders get a `--variant` too, so the case can be tried against both.

## Firmware, in outline

A new release fingerprint (AGENTS.md rule 2), because the profile changes. Hardware shouldn't
wait for it, but the board is of no use with the port until it exists. What it needs:

- `board.py`, `picoquorum-key` profile: `KEY2_SDA, KEY2_SCL, KEY_CC, KEY_EN, KEY_LED, KEY_FAULT`.
  Other profiles leave them `None`. `firmware/profile/picoquorum_key.py` and `smoke.py` mirror them
  (`test_pin_contract.py`).
- `signer.detect()` scans I2C0 today. It learns the second bus: when `KEY_CC` reads low, drive
  `KEY_EN` high, wait about 10 ms for the key's 200 nF and U5's soft start, then scan `I2C(1)`.
  When CC goes high, drive `KEY_EN` low and drop that signer. The soldered chip is read as today.
- `same_chip()` already re-reads the serial right before a signature. It runs on whichever signer
  is about to sign, so a key swapped mid-approval is caught. Keep that; it is the hot-swap check.
- Which signer: the policy decision above. Both chips need an entry in `QUORUM_EXPECT`.
- The LED pin as the status LED's meaning for that key: off, on, blinking.
- The smoke test (`smoke.py`): CC level, EN toggling, a scan on the second bus, the LED.
- The port's bench script is the pigtail's `swap.py`, pointed at the second bus and `KEY_EN`.

Hot-swap on the wire is already proven for key-c (11 swaps on the bench, 2026-10-16; the receptacle's
VBUS and GND mate first). What this board adds is the power-sequenced part: the key gets VKEY only
once CC says it is at full depth, and loses it before anything else lets go.

## Tests to add

In `tests/`, beside the 125 that exist:

- `test_pin_contract.py`: the six new lines agree across PINS.md, `circuit.py`, the board and the
  profile.
- `test_assembly_files.py`: base and port exports as above; R17 in both; U1 in neither; the
  Gerbers identical.
- `test_geometry.py`: the plug's pads inside the board; the antenna rule area still covers the
  module's antenna area plus margin; no copper of any net inside it; the plug's shell at least
  the chosen distance from the rule area; D5 not under the glass.
- `test_3d.py`: a key-c model on the plug, either way up, clears the glass, the switches, the
  module and the case; the plug's tongue clears the top edge by its drawing.
- `test_silk.py`: KEY PORT by the plug, the renamed test pads, the changed back legend.
- A SPICE row in `test_spice.py` if it has one for the CC divider: 0.32 V with 5.1k, over 3 V open.

## Bring-up, per board with the port

1. Before any key: meter VKEY to GND, not a short; KEY_CC pad reads 3.3 V; KEY_EN pad reads 0 V;
   the plug's A6/A7 are open to U2's SDA/SCL (the two buses are separate).
2. Short the plug's A5 to GND through 5.1k: KEY_CC reads about 0.3 V.
3. Flash the image that knows the port. With no key the port LED stays off and `I2C(1)` scans
   empty.
4. Plug a key-c in. The LED comes on, the scan shows 0x60 on the second bus and nothing new on
   the first, and the soldered chip's serial is unchanged. Plug and unplug 20 times with the
   console on: no reset, the right serial each time, the soldered chip still answering.
5. Wi-Fi: RSSI at the same spot with no key, with a key, and on a base board. Write the three
   numbers in DESIGN.md.
6. A key-c P3: its LED follows the port LED.

## Docs to touch

DESIGN.md (a departures row, the geometry table, the circuits, the antenna rule area), PINS.md
(six rows and the unconnected list), SPEC.md ("ATECC608C alone at 0x60" becomes "alone on its bus";
a port paragraph under The key), BOM.md (the port column and its tiers), ORDERING.md (two BOM/CPL
sets, one Gerber zip), BRINGUP.md (the steps above), the mockup README, and the row for this board
in `hardware/README.md`.

## Open

- [ ] The plug: a horizontal surface-mount male plug with an LCSC number and stock, or the straddle
      plug and a 0.8 mm board. Get the drawing; check which face A1 lands on against a real plug
      before trusting the footprint (wing-b's note).
- [ ] How far from the antenna is enough: measure, then fix the plug's X.
- [ ] Which key signs when both are in, and what the screen shows.
- [ ] Whether FAULT earns its pin.
- [ ] The case: a slot for the key, keepers for the plug, and whether the four M2 holes move.
