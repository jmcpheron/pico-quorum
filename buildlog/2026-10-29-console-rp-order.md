# console-rp ordered: five boards

Five [console-rp](../hardware/console-rp/README.md) boards, made and fully assembled by JLCPCB.
This is the RP2350A console with no radio. Unlike console-s3, nothing goes on by hand except the
panel, which clips into J2. The files are the ones `tools/keypcb jlc console-rp` passed, at
`3b72de15` (PR #92).

What this page is from: the order page, its BOM page and JLCPCB's invoice, as pasted on
2026-10-29. Name, address, phone, email and card are left out, and so is the account's customer
code in the order numbers.

## The order

| | |
|---|---|
| Placed | 2026-10-29, paid 15:37; JLCPCB dates the invoice 2026-10-30. Batch **W…5225** |
| PCB | order **Y10**, production order …122A |
| PCBA | top side, **SMT…5612**; build time 1–2 days |
| Quantity | 5 boards, 5 assembled |
| Status | Data Preparation, both lines, when read |
| Board | 2 layers, 72 × 36 mm, 1.6 mm FR-4 TG135, 1 oz, LeadFree HASL, green mask, white ink-jet silkscreen, tented vias, 0.3 mm via holes (0.4/0.45 mm pads), "Remove Mark", ±0.2 mm outline, IPC Class 2, flying-probe test of every board |
| Stackup | not specified (JLCPCB's default for 2 layers) |
| Delivery | single PCBs, not a panel |
| Approvals | Production file: **No**. Parts placement: not on the pasted page |
| Shortage | "Require Full Quantity": all 5 or nothing |
| Build time | PCB 24 hours (PCBA only) |
| Weight | PCB 0.2 kg, PCBA 0.2 kg; 0.41 kg in all |
| Files | `console-rp-gerbers.zip`, `bom.csv`, `cpl.csv` (JLCPCB names the order `console-rp-gerbers_Y10`) |
| Shipping | UPS Express Saver, **DDP**: duties paid with the order |

## What it cost

From the invoice. The lines add up to the total.

| line | |
|---|---|
| PCB, Y10 | $5.20 |
| PCBA, SMT…5612 | $85.49 |
| **Merchandise** (5 × $18.14) | **$90.69** |
| Shipping | $30.37 |
| Subtotal | $121.06 |
| Sales and use tax | $7.02 |
| Import taxes | $31.75 |
| Duty and tax disbursement fee | $4.45 |
| **Total** | **$164.28**, about $32.86 a board |

- **No price breakdown for the PCBA was pasted.** Of its $85.49, the BOM lines below are $44.38.
  Nine Extended types at console-s3's $3.09 each would be $27.81. That leaves $13.30 for setup,
  stencil, the 252 joints a board and any other fee. Check it on the order page.
- **Import taxes are 35.0 % of the merchandise,** as on console-s3 (35.0 %). Sales tax is 7.7 %.
- **Shipping and import were $66.57** of the $164.28.
- **Not in this order:** the panels. The two in hand are the Walfront pair bought with console-s3
  ($16.28, [that order](2026-10-24-console-s3-order.md#parts-bought-elsewhere)), and they were
  checked against J2 ([The panel](../hardware/console-rp/README.md#the-panel)). Five boards need
  three more.

## Parts, as JLCPCB matched them

From the order's BOM page, top side, "Complete File". The page reads "33 parts detected" (the 33
lines of `bom.csv`) and "44 Parts confirmed". Every part comes from JLCPCB's stock, and each matches
`bom.csv`'s LCSC number.

| ref | value | MPN | LCSC | type | qty bought | cost |
|---|---|---|---|---|---|---|
| C1, C2, C3 | 4.7 µF | CL05A475MP5NRNC | C23733 | Basic | 15 | $0.2265 |
| C4–C14, C17, C21–C23, C25 | 100 nF | CL05B104KO5NNNC | C1525 | Basic | 80 | $0.2480 |
| C15, C16 | 15 pF | 0402CG150J500NT | C1548 | Basic | 10 | $0.0380 |
| C18, C19 | 10 µF | CL21A106KAYNNNE | C15850 | Basic | 10 | $0.4360 |
| C20, C24 | 1 µF | CL05A105KA5NQNC | C52923 | Basic | 10 | $0.0640 |
| D1 | red LED | KT-0603R | C2286 | Basic | 5 | $0.0385 |
| J1 | USB-C | TYPE-C-31-M-12 | C165948 | Extended | 5 | $0.9355 |
| J2 | panel ZIF | 0.5K-HX-8PWB (top and bottom contacts) | C2919492 | Extended | 7 | $0.6790 |
| L1 | 3.3 µH | AOTA-B201610S3R3-101-T | C42411119 | Extended | 6 | $2.1570 |
| Q1 | P-MOSFET | AO3401A | C15127 | Basic | 5 | $0.4800 |
| Q2 | NPN | SS8050 (range 200–350) | C2150 | Basic | 5 | $0.0740 |
| R1 | 33 Ω | 0402WGF330JTCE | C25105 | Basic | 5 | $0.0075 |
| R2, R3, R10, R12 | 1 kΩ | 0402WGF1001TCE | C11702 | Basic | 20 | $0.0260 |
| R4, R5 | 5.1 kΩ | 0402WGF5101TCE | C25905 | Basic | 10 | $0.0230 |
| R6, R7, R11 | 4.7 kΩ | 0402WGF4701TCE | C25900 | Basic | 15 | $0.0300 |
| R8 | 22 Ω | 0402WGF220JTCE | C25092 | Basic | 5 | $0.0070 |
| R9 | 10 kΩ | 0402WGF1002TCE | C25744 | Basic | 5 | $0.0120 |
| R13, R14 | 27 Ω | 0402WGF270JTCE | C25100 | Extended | 22 | $0.0286 |
| SW1–SW5 | D0, D1, D2, RESET, BOOTSEL | TS-1187A-B-A-B | C318884 | Basic | 25 | $0.5175 |
| U1 | RP2350A | RP2350A | C42411118 | Extended | 5 | $6.4770 |
| U2 | ESD array | USBLC6-2SC6 | C7519 | Extended | 7 | $1.2586 |
| U3 | 3.3 V LDO | XC6206P332MR-G | C5446 | Basic | 5 | $0.7395 |
| U4 | USB serial | CH343P | C2846043 | Extended | 5 | $4.9130 |
| U5 | secure element | ATECC608C-SSHDA-T | C28975195 | Extended | 5 | $8.7455 |
| U6 | 16 MB flash | W25Q128JVSIQ | C97521 | Basic | 5 | $12.9215 |
| Y1 | 12 MHz | ABM8-272-T3 | C20625731 | Extended | 5 | $3.2920 |

- **The lines add to $44.38.**
- **The nine Extended types** are J1, J2, L1, R13/R14, U1, U2, U4, U5 and Y1, as the README says.
- **U6 is the dearest part:** $12.92, $2.58 a chip, more than U5 ($1.75) or U1 ($1.30).
- **L1: JLCPCB bought 6** of the 6 it had. LCSC showed **0 in stock** afterwards (2026-10-29).
- **U1's line was cut off** in the paste, between SW5's and U1's text. Its $6.4770 for 5 is
  $1.30 each, the RP2350A's one-piece price.
- **Spares:** two each of J2 and U2, one L1, two 27 Ω and more of the passives.

## The files

The design files in the repository at `3b72de15` (2026-10-29), the last commit to touch `fab/`:

| what | SHA-256 |
|---|---|
| `console-rp-gerbers.zip` | `47e6527be01853576885b0319c054f45cfea9268a799e44db12ff8462a8b57f8` |
| `bom.csv` | `f8a9ae9ba26632020fc64cd5ca54e05375669e44e70e77fe36c97840bc0cb9f7` |
| `cpl.csv` | `9116137afa0ad6427d3d17513a0abb8d2e5c117f7a2395797c3b841ee5c7d7e5` |

**Not yet checked against what was uploaded.** Download the BOM and CPL from the order, and the
Gerbers if JLCPCB offers them, and compare hashes.

## What 100, 500 or 1000 would cost

An estimate, not a quote. It takes this order's structure and LCSC's price ladders, read on
2026-10-29 from the parts' product data, and assumes these:
- **Parts** at each part's ladder price for the quantity bought. Passives, LED and transistors stay
  at this order's own prices, under $0.20 a board in all.
- **Assembly:** setup $8.24 and stencil $1.55 (console-s3's Economic figures), nine Extended fees
  of $3.09 per order, and $0.0017 a joint for 252 joints.
- **PCB:** guessed at $15, $65 and $120 (no quote was run).
- **Shipping:** guessed at $90, $250 and $420, UPS DDP.
- **Taxes:** import 35 % and sales tax 7.7 % of the merchandise, as on this order; disbursement
  $4.45. Tariffs can change.

Checked against this order, the same rules give $31.74 import and $7.02 tax, as invoiced.

| boards | parts | merchandise | shipping | import + tax | total | a board |
|---|---|---|---|---|---|---|
| 5 (this order) | $44.38 | $90.69 | $30.37 | $43.22 | **$164.28** | **$32.86** |
| 100 | $642 | $737 | ~$90 | ~$320 | **~$1,150** | **~$11.50** |
| 500 | $2,982 | $3,299 | ~$250 | ~$1,414 | **~$4,960** | **~$9.90** |
| 1000 | $5,814 | $6,400 | ~$420 | ~$2,740 | **~$9,560** | **~$9.60** |

Add the panel: about $2.50 each in bulk (the README's figure, not checked), or $8.40 at
Walfront's 2-pack price.

- **Past 100, the parts set the price.** They are about $6.40 a board at 100 and $5.80 at 1000.
  The per-order fees ($38 setup, stencil and Extended) are $0.38 a board at 100 and $0.04 at 1000.
- **Import is the next biggest line:** 35 % of the merchandise, about $2.20 a board at 1000.
- **The dearest parts at 1000:** U6 $1.65, U1 $1.10, U5 $1.05, U4 $0.63, Y1 $0.39, L1 $0.21.
  U6 is 16 MB, and the Pico 2 image uses 4 MB. A 4 MB part would cost less. It wasn't priced, and
  changing it means a board change (the review's suggestion).
- **Stock limits it before price does** (LCSC, 2026-10-29):
  - L1: 0. Pre-order, or send our own.
  - Y1 (ABM8-272-T3): 830, short of 1000.
  - U5: 3,967. U1: 5,454. U6: 8,039. U4: 11,098.
- **Not counted:** the 5 bring-up boards' lessons (a revision would mean new setup and stencil),
  test and programming time, a case, and JLCPCB's Standard assembly if Economic doesn't take the
  quantity.

## Still to record

- [ ] The PCBA's price breakdown (setup, stencil, joints, fees)
- [ ] JLCPCB's parts-placement review, if there is one: L1's dot against `fab/check/cpl-overlay.png`
- [ ] The uploaded files' hashes, against the table above
- [ ] Three more panels, for five boards
- [ ] The production progress
- [ ] Tracking, arrival, and bring-up (the README's "Steps to a board")
