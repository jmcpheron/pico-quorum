# Ordering the key PCB

How to read rev A, check it, turn it into the files a fab wants, and order it. This is also a
first pass through the whole PCB loop. The design itself is in [README.md](README.md).

Prices and stock were looked up on 2026-10-02. Check them again, and trust the quote JLCPCB
shows over the numbers here.

## 1. What a PCB order is

| file | what it is | made by |
|---|---|---|
| **Gerbers** | one image per layer: copper top and bottom, solder mask, silkscreen, paste, and the outline (`Edge_Cuts`) | `tools/keypcb fab` → `fab/*-gerbers.zip` |
| **Drill files** | where the holes go: `PTH.drl` for plated holes (vias), `NPTH.drl` for the lanyard hole | in the same zip |
| **BOM** | bill of materials: which part goes on each designator, by LCSC number | `fab/bom.csv` |
| **CPL** | component placement list (also called a centroid or pick-and-place file): where each part's centre goes, which side, and its rotation | `fab/cpl.csv` |

A **bare board** order needs only the zip. An **assembled** order (PCBA) also needs the BOM and
CPL.

## 2. Open it in KiCad

1. Install KiCad 9 or newer from https://www.kicad.org/download/ (it's free).
2. Open `key-b-udfn/key-b-udfn.kicad_pro`. The project window has two editors.
   - **Schematic editor:** what connects to what. The blue notes explain the fingers.
   - **PCB editor:** where things are.
     - Press **Alt+3** for the 3D view.
     - **Board Setup → Board Stackup** shows ENIG and the edge connector.
     - **Board Setup → Constraints** has JLCPCB's limits.
3. Things worth doing, then undo with Ctrl+Z:
   - Click a finger on the board. Its length is its distance from the edge, and the length is
     what does the sequencing.
   - Drag C1 a few mm and run **Inspect → Design Rules Checker**. See what DRC complains about.
   - Hover over a track to see its net. The bottom layer carries only GND plus the one short VCC
     link under the ESD array.
4. The blade footprint is `lib/picoquorum.pretty/KeyBlade_7P_P2.54mm`. Open it in the Footprint
   Editor to see the staggered pads and the contact line on the Fab layer.

Once you edit a board by hand, keep editing it by hand. `gen.py` regenerates both boards from
scratch and would undo your changes.

## 3. Check it

`tools/keypcb check` runs three checks on each board:
- **ERC** (electrical rules check) on the schematic. It catches unconnected pins, two outputs
  driving each other, and a power pin with no source.
- **DRC** (design rules check) on the board. It catches tracks closer together than the fab can
  make, copper too near the edge, and missing connections.
- **Schematic parity.** It checks that the board and schematic agree, part for part and net for
  net.

Rev A passes all three with zero issues. In the GUI the same checks are **Inspect → Electrical
Rules Checker** and **Inspect → Design Rules Checker**, with "Test for parity" ticked.

## 4. Export

`tools/keypcb fab` rewrites `fab/` for both boards. In the GUI the same thing is
**File → Fabrication Outputs → Gerbers / Drill Files / Component Placement**.

All three measure from the board's bottom-left corner, which is set as the drill/place origin.

## 5. key-a: bare boards, chips soldered by hand

**Order at https://jlcpcb.com:**
1. Upload `key-a-soic/fab/key-a-soic-gerbers.zip`. It reads 22.35 × 32 mm, 2 layers.

| setting | choose | why |
|---|---|---|
| Layers | 2 | |
| PCB qty | 5 or 10 | 5 is the minimum. Locking a chip is permanent, so you want spares |
| Thickness | 1.6 mm | the socket takes a 0.062″ card |
| Surface finish | **ENIG** | gold on the pads, which makes the fingers gold. HASL would tin them |
| Gold fingers | **No** | JLCPCB's gold-finger option needs a board or panel of at least 50 × 50 mm. ENIG pads on the edge are rev A's fingers |
| Edge bevel / chamfer | none | not offered under 5 × 5 cm. Sand the leading edge lightly by hand if insertion feels sharp |
| Mask colour | any | |
| Mark on PCB | "Remove mark" if offered, or leave it | otherwise JLCPCB prints an order number somewhere on the silkscreen |

**Parts, from Digi-Key:**

| part | Digi-Key | qty |
|---|---|---|
| ATECC608C-SSHDA-B | 150-ATECC608C-SSHDA-B-ND | 10 |
| USBLC6-2SC6 | 497-5235-1-ND | 10 |
| 100 nF 0805 X7R | any, e.g. Yageo CC0805KRX7R9BB104 | 10 |

The ATECC608C-SSHDA-B showed **0 in stock at Digi-Key, due 14 Jan 2027**. You can:
- Check Mouser and Microchip Direct.
- Use the ATECC608B-SSHDA-B, which is pin-compatible. Before you lock one, check that
  [PROVISIONING.md](../../docs/PROVISIONING.md)'s quorum v1 config suits it.
- Let JLCPCB place key-a's parts after all. `key-a-soic/fab/bom.csv` lists ATECC608C-SSHDA-T as
  C28975195; see section 6.

**Soldering, in this order:**
1. **U2** first, while the area is open. Its pin 1 is the corner by the silkscreen triangle.
2. **U1.** Pin 1 is the dot on the chip, matched to the triangle by the footprint. Tack one corner,
   check the alignment, then do the rest with flux.
3. **C1.**
4. Leave **R1** empty.

**Meter it before it goes in**, the same checks as BUILD1:
- DETECT (finger 8) to GND (finger 1) **beeps**.
- VCC (finger 4) to GND does **not** beep.
- SDA and SCL don't beep to GND or to each other.

## 6. key-b: fully assembled by JLCPCB

1. Upload `key-b-udfn/fab/key-b-udfn-gerbers.zip`, with the same settings as key-a.
2. Turn on **PCB Assembly**: Economic, top side, 5 boards (2 minimum). Tooling holes: let JLCPCB add
   them if it asks.
3. Upload `fab/bom.csv` and `fab/cpl.csv`.

| ref | part | LCSC | JLCPCB stock on 2026-10-02 |
|---|---|---|---|
| U1 | ATECC608C-MAHDA-S (UDFN-8) | C23291019 | 28, extended |
| U2 | USBLC6-2SC6 (ST's own; ignore the look-alike clones) | C7519 | ~35k, extended |
| C1 | 100 nF 0402 X7R | C1525 | basic |

R1 (not fitted) and J1 (the fingers) aren't in the BOM on purpose.

**If U1 is short, pre-order it.**
- In JLCPCB's parts library, open C23291019 and use **Pre-order**. You pay up front, and the parts
  go into "My Parts Lib" once they reach JLCPCB's warehouse.
- Only then can they be assembled.
- Pre-orders can't be cancelled, and parts you buy there are for assembly only: JLCPCB won't send
  you loose chips.
- C23783731 (ATECC608C-MAVDA-S) is the same part rated to 100 °C, if that one has stock instead.

**In the placement preview, check every pin 1.**
- KiCad and JLCPCB don't always agree on a footprint's zero rotation.
- U1's pin 1 should sit by its silkscreen triangle, and so should U2's.
- If a part is turned, fix it in the preview. Rotations are in steps of 90°.

**The gold-finger question.**
- JLCPCB's Economic assembly doesn't support "gold fingers". Rev A doesn't ask for them: the
  fingers are ordinary ENIG pads at the edge.
- If JLCPCB's review flags them anyway, the reply is that they are plain ENIG edge pads, with no
  bevel and no hard gold.
- If they still refuse, there are two ways out:
  - **Standard assembly.** It needs a panel of at least 70 × 70 mm with rails and fiducials, for
    example 2 × 3 keys. It costs a lot more: about $25 setup per side, plus handling and fixtures.
  - **Bare boards with a stencil.** Order the boards bare with a stencil and reflow key-b yourself on
    a hot plate.

**Rough cost** for 5 assembled key-b boards:
- Economic setup $8.18.
- Stencil $1.53.
- Feeder loading $3.07 for each extended part, so two here.
- The parts themselves.
- The ENIG boards, which cost more than the $2 HASL headline price. ENIG adds roughly $10–20 on a
  small order.
- Shipping.

Lead time is about 1–2 weeks after the parts are in stock.

## 7. PCBWay instead

The same zip, BOM and CPL work at PCBWay. It offers three ways to source parts:
- **Turnkey:** PCBWay buys everything.
- **Kitted or consigned:** you ship the parts in.
- **Combo:** a mix of both.

To pin the exact ATECC608C variant, add a supplier link to the BOM row. PCBWay's limits for gold
fingers and small boards weren't checked here.

## 8. When the boards arrive

1. **Test-fit a bare board in the socket** before you solder anything.
   - It should seat fully and not rock sideways.
   - Every finger should touch its contact.
   - The keying slot should clear the key insert, if you fitted one.
2. **Wire the socket's top row to the Build 1 pins**, using [README.md](README.md#the-fingers).
   - SDA GP4, SCL GP5, VCC GP6, DETECT GP7, RST GP26, ID GP27, GND.
   - Use 4.7k or 10k pull-ups to switched VCC, as in BUILD1.
3. **`import bench1`** should print `key bus scan: ['0x60']` and a serial number once the key is in
   ([BUILD1.md](../wiring/BUILD1.md#order-of-work)).
4. **Practise provisioning on a spare first.** Config and data locks are permanent
   ([LOCKING.md](../../docs/LOCKING.md), [PROVISIONING.md](../../docs/PROVISIONING.md)).
