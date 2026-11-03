# 100 panels ordered from BuyDisplay

The panels for the demo batches and a possible developer pre-sale: 100 of the 1.14″ ER-TFT1.14-2,
the panel [console-s3](../hardware/console-s3/DESIGN.md)'s J2 was placed for
([ORDER-PLAN-2026-10-24.md](../ORDER-PLAN-2026-10-24.md)).

What this page is from: BuyDisplay's order confirmation email, pasted by Jason McPheron, and what
Jason said about the boards. Name, address, phone and email are left out.

## The order

| | |
|---|---|
| Placed | 2026-11-03, 1:45:51 PM. Order **#100103443** |
| Seller | BuyDisplay.com; shipper and exporter EastRising Technology Co., Ltd, China |
| Item | 1.14 inch Color 135x240 IPS TFT LCD Display Panel, ST7789, FPC connector |
| SKU | **ER-TFT1.14-2** |
| Quantity | **100** |
| Payment | PayPal Express Checkout, full payment in advance |
| Shipping | FedEx, DHL or TNT (the email doesn't say which) to Chino Hills, California |
| Invoice and tracking | **Not yet.** BuyDisplay sends the commercial invoice and shipment notice after it receives payment |

## What it cost

From the email. The lines add up to the total.

| line | |
|---|---|
| 100 × ER-TFT1.14-2 | $293.00 ($2.93 each) |
| Shipping and handling | $64.41 |
| Payment fee | $13.88 |
| **Total** | **$371.29**, **$3.71 a panel** |

- **Duties and brokerage aren't in it.** The email shows none. The JLCPCB order paid import taxes
  and fees up front (DDP); this one may be billed by the carrier at delivery. Unknown until the
  invoice or the carrier says. Record it here when it does.
- **Against the plan's figure:** CONCEPT.md and the plan count about $2.50 a panel. $2.93 is 17 %
  over that, and $3.71 landed is 48 % over, before any duty.
- **Shipping and the fee are 21 % of the total.** A second order at this size would pay the same
  kind of overhead again; a larger one spreads it.

## Panels on hand and on order

| | qty | source | status |
|---|---|---|---|
| "ST7789V LCD Display Module 1.14", 2-pack | 2 | Amazon, 2026-10-23, $16.28 | shipped for 2026-10-26; arrival not recorded here |
| ER-TFT1.14-2 | 100 | BuyDisplay, this order | placed; payment to confirm |

The Amazon pair's panel against J2 was never recorded
([the console-s3 page](2026-10-24-console-s3-order.md#parts-bought-elsewhere)). Whether the
BuyDisplay panel's flex fits J2 is also unchecked.

## Boards, as Jason reports them

Both first boards have arrived and both work, by Jason's report (2026-11-03): the **console-s3**
(five boards, JLCPCB) and the **PicoQuorumKey** (the "Pico key signer"), both with the ESP32-S3
module on castellations. The bench steps and what was measured go in their own logs, which are to be
merged later; this page doesn't restate them.

## Rough cost of one console-s3

Built from the figures on these pages. These are small-run prices, not a quote for a batch.

| | |
|---|---|
| Board and assembly, with U2, shipping and import | $19.34 (JLCPCB, 5 boards: $96.72 ÷ 5) |
| ESP32-S3 module | $4.31 (LCSC, 10 for $43.10) |
| Panel, landed | $3.71 (this order) |
| **About** | **$27.36** |

- **The JLCPCB figure carries fixed fees.** Setup $8.24, stencil $1.55 and the Extended-part fees
  ($15.45) don't grow with the quantity, so a larger run costs less a board. Get a quote at the
  planned size.
- **Not counted:** the hand-soldering of the module (about 15 minutes a board), flashing, the
  case or cable, and any duty on this order.
- **Supply chain, as it stands:** boards and parts from JLCPCB, modules from LCSC (6,413 in stock on
  2026-10-24), panels from BuyDisplay (one seller), and the ATECC608C (62 at JLCPCB and none at LCSC
  on 2026-10-24: the thin one). The panel is stocked by one seller here, so a second source is
  worth finding before a pre-sale.

## Still to record

- [ ] Payment confirmed, and BuyDisplay's invoice and tracking
- [ ] Carrier, delivery date, and any duty or brokerage charged
- [ ] On arrival: count, and the panel's flex pin count and pitch against J2 (8 pins, 0.5 mm)
- [ ] ER-TFT1.14-2 on a console-s3: fit, fold, backlight voltage and current
- [ ] Panel order of the next batch: quantity, and a second source
- [ ] The console-s3 and PicoQuorumKey bench results, once their logs merge
