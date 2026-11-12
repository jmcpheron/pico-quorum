# Mono ordered: twenty boards

Twenty [Mono](../hardware/mono/README.md) boards, made and assembled by JLCPCB. It is the first
order of the reference console, and the first of more than five of anything here.

What this page is from: JLCPCB's invoice (one page, a PDF) as Jason McPheron gave it on
2026-11-12. Name, address, phone and email are left out, and so are the invoice number and the
long digits of the order numbers. The order page and its BOM page haven't been pasted, so much
that the other order pages record is missing here; it is listed under
[Still to record](#still-to-record).

## The order

| | |
|---|---|
| Placed | **2026-11-09**, read from the batch number, which looks like a date and time (13:46). Not confirmed by an order page |
| Invoice | dated 12/11/2026. The invoice was fetched on 2026-11-12, and console-rp's was dated the day it was fetched too, so this is likely not the day of the order |
| Batch | **W…4178** |
| Order | **SMT…0945-Y13**, one line: "Rigid Populated printed circuit board". The PCB and the assembly aren't split as on console-rp's invoice |
| Files | JLCPCB names the order `mono-gerbers_Y13`. Which commit's `mono/fab/` was uploaded isn't recorded |
| Quantity | **20** (1 set = 1 pc, 20 pcs) |
| Shipping | UPS Express Saver, **DDP**: duties paid with the order |
| Assembly type, build time, board options, status | **not on the invoice** |

## What it cost

From the invoice. The lines add up to the total.

| line | |
|---|---|
| **Merchandise** (20 × $13.76) | **$275.26** |
| Shipping | $50.30 |
| Subtotal | $325.56 |
| States sales and use tax | $21.33 |
| Import taxes | $96.35 |
| Duty and tax disbursement fee | $4.44 |
| **Total** | **$447.68**, **$22.38 a board** |

- **Import taxes are 35.0 % of the merchandise,** as on console-s3 and console-rp. Sales tax is
  7.7 %.
- **Shipping and import were $172.42** of the $447.68, 39 %.
- **Against console-rp's five:** $18.14 a board there and $13.76 here, before shipping and import;
  $32.86 and $22.38 with them. [That page's estimate](2026-10-29-console-rp-order.md) for
  console-rp was about $11.50 a board at 100. The two boards aren't the same, so this is a rough
  comparison.
- **Against the quote of two days later:** [the second quote](2026-11-11-mono-quote-build-time.md)
  read $265.69 for the boards and assembly, $9.57 less than this order's $275.26. Why isn't known:
  part prices move, and the two may not have had the same options ticked.
- **Not in this order:** the panels. The [100 from BuyDisplay](2026-11-03-panels-order.md) are for
  these, at $3.71 each landed, before any duty. That makes about **$26 a Mono** with its panel.
  The case, flashing and testing aren't counted.

## How long it is taking

The invoice doesn't give a build time or a status. What can be said from the dates:

- If it was placed on 2026-11-09, then 2026-11-12 is its third day.
- The second quote, on Standard assembly, read PCB 24 hours and assembly 3–4 days. If this order
  is on the same terms, it would leave the factory about four to five days after it was placed,
  and UPS comes after that. Three days in, that is not late.
- The orders of five read 1–2 days of assembly, so this one feeling slower fits the quote.
- Whether this order is on Standard, and which build time it has, is still unread.

## Still to record

- [x] Invoice: $447.68 for 20, UPS Express Saver, DDP
- [ ] The order page: date placed and paid, assembly type (Economic or Standard), build time,
      board options, approvals (production file, parts placement), status
- [ ] The PCBA's price breakdown, to set beside the second quote's
- [ ] The BOM page: parts as JLCPCB matched them, their tiers, any shortage, and L1's stock
- [ ] Which commit's fab files were uploaded
- [ ] Whether a panel was folded against a 1:1 print first
      ([Steps to a board](../hardware/mono/README.md#steps-to-a-board), step 1)
- [ ] Shipped and delivered dates, and the count on arrival
- [ ] Bring-up of the first board
