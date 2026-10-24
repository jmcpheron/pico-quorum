# console-s3 rev A ordered: five boards

The first console board ordered: [hardware/console-s3](../hardware/console-s3/DESIGN.md), five made
and assembled by JLCPCB, the module still to go on by hand. This is option A from
[ORDER-PLAN-2026-10-24.md](../ORDER-PLAN-2026-10-24.md): Economic assembly, front only. PicoQuorumKey
isn't in this order.

What this page is from: the PCB and PCBA lines of the order, the PCBA's price breakdown (a
screenshot), JLCPCB's invoice and its sales contract. Not yet seen: the BOM page as JLCPCB matched
it, and the receipts for the parts bought elsewhere (modules, panels).

## The order

| | |
|---|---|
| Placed | 2026-10-24; JLCPCB dates the invoice and contract 2026-10-25. Batch **W…1507** |
| PCB | order **Y6**, production order …122A (the account's customer code is left out here) |
| PCBA | Economic (setup $8.24 is Economic's), top side, **SMT…2244** |
| Quantity | 5 boards, 5 assembled |
| Status | Data Preparation, both lines, when read |
| Board | 2 layers, 64 × 22.86 mm, 1.6 mm FR-4 TG135, 1 oz, LeadFree HASL, green mask, white ink-jet silkscreen, tented vias, 0.3 mm via holes (0.4/0.45 mm pads), "Remove Mark", ±0.2 mm outline, IPC Class 2, flying-probe test of every board |
| Delivery | single PCBs, not a panel |
| Edges | not deburred ("Deburring/Edge rounding: No") |
| Approvals | Production file: **No**. Parts placement: **yes** ($0.45), pending |
| Shortage | "Require Full Quantity": all 5 or nothing |
| Build time | PCB 24 hours (PCBA only); assembly 1–2 days |
| Weight | PCB 0.14 kg, PCBA 0.18 kg |
| Files | `console-s3-gerbers.zip`, `bom.csv`, `cpl.csv` (JLCPCB names the order `console-s3-gerbers_Y6`) |
| Shipping | UPS Express Saver, **DDP**: duties paid with the order |

## What it cost

From the invoice. The lines add up to the total.

| line | |
|---|---|
| PCB, Y6 | $5.10 |
| PCBA, SMT…2244 | $45.75 |
| **Merchandise** (5 × $10.17) | **$50.85** |
| Shipping | $29.66 |
| Shipping discount | −$10.00 |
| Subtotal | $70.51 |
| Sales and use tax | $3.95 |
| Import taxes | $17.81 |
| Duty and tax disbursement fee | $4.45 |
| **Total** | **$96.72**, about $19.34 a board |

The PCBA's $45.75, from its price breakdown:

| | |
|---|---|
| Setup | $8.24 |
| Stencil | $1.55 |
| Components | $17.93 |
| Extended components fee | $15.45: 5 × $3.09, so five Extended part types |
| SMT assembly | $1.07 |
| Special components fee | $0.15 |
| Confirm parts placement | $0.45 |
| **These add to** | **$44.84** |

- **$0.91 isn't in the breakdown.** The screenshot's popup may have had another line out of view.
  Check it on the order page.
- **The five Extended types** are most likely the plan's U2, U3, U4, J1 and J2. Confirm on the BOM
  page.
- **The $0.15 special fee** is $0.03 × 5, the same as key-c's J1 (the same HCTL USB-C, C2894897).
  Most likely J1 again; the breakdown doesn't name it.
- **No small-board fee showed.** The plan warned of one for a side at 30 mm or less. The PCB line is
  $5.10 in all.
- **Not in this order:** the ESP32-S3 modules (LCSC, C2913204), the 1.14″ panels. The plan's $75–90
  counts them, so it can't be held against $96.72 until their receipts are in.
- **Shipping and import were $46** of the $96.72. Import taxes alone are 35 % of the merchandise.

Against the plan's figures: setup $8.24 (plan $8.18), stencil $1.55 ($1.53), Extended fees $15.45
(about $15).

## The files

The design files in the repository at `2c76e25` (2026-10-24), the last commit to touch `fab/`:

| what | SHA-256 |
|---|---|
| `console-s3-gerbers.zip` | `981659a1af8d4211ced5b98fefd6cf0fee05c22684e1d8c409c7603eceebbc82` |
| `bom.csv` | `17d619a182168daaf0002c4474c381d5098c370ec591d821170753e3c9183c0c` |
| `cpl.csv` | `25a60504b7f1c9146d39fed78f6eb906e833b8c459290d7458aa91458874962d` |

**Not yet checked against what was uploaded.** Download the BOM and CPL from the order, and the
Gerbers if JLCPCB offers them, and compare hashes as for key-c.

## Different from the plan

- **Confirm Production File: No.** The plan said yes. On key-c it showed where Economic assembly put
  its tooling holes, and that board is 16 mm wide; this one is 22.86 mm. The holes go in without
  that check. Look for them when the boards arrive, and on the placement preview if it shows them.

## Still to record

- [ ] The BOM page as JLCPCB matched it: each part, quantity bought, cost, Basic or Extended, and
      whether U2 (C23291019) was in stock
- [ ] The $0.91 the breakdown doesn't show
- [ ] The PCBA settings (paste, packaging, photo confirmation, customs category)
- [ ] The receipts for the parts bought elsewhere: modules, panels
- [ ] The uploaded files' hashes, against the table above
- [ ] JLCPCB's parts-placement review: pin 1 against `fab/check/cpl-overlay.png` for U2, U3, U4, Q1,
      Q2, D1, J1, J2. The overlay isn't committed: `tools/keypcb jlc console-s3` writes it
- [ ] Tracking, arrival, and the bench steps in the plan's "When they arrive"
