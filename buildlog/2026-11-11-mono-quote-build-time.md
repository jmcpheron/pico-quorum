# A second Mono quote at JLCPCB: assembly reads 3–4 days

Jason McPheron has an order of 20 [Mono](../hardware/mono/README.md) boards at JLCPCB that was
taking longer than the orders of five did. To see why, he uploaded the files again as a new quote
and read its last page. **This quote was not ordered.** It is logged for what it says about build
time.

What this page is from: one screenshot of JLCPCB's Quote & Order page for the project
`mono-gerbers-2`, saved there on 11 November at 20:28, and what Jason said about it on 2026-11-12.
The page shows no name, address or order number. It doesn't show the quantity either: Jason's
order is 20, and the quote is taken to be the same, unchecked. The real order is on
[its own page](2026-11-09-mono-order.md), from its invoice.

## What the quote says

| | |
|---|---|
| Project | `mono-gerbers-2` |
| Assembly | **Standard PCBA** (the page's own heading) |
| Build time, PCB | 24 hours, $0.00 |
| Build time, assembly | **3–4 days, $0.00** (selected), or **2–3 days, $49.63** |
| Weight | 1.85 kg |
| Total | **$265.69**, before shipping and import |

| line | |
|---|---|
| Engineering fee | $4.00 |
| Via covering | $0.00 |
| Surface finish | $1.70 |
| Board | $12.10 |
| Confirm Production file | $0.00 |
| **PCB** | **$17.80** |
| Setup fee | $25.75 |
| Stencil | $8.27 |
| Panel | $0.00 |
| Large size | $0.00 |
| Components, 28 items | $159.71 |
| Feeders loading fee | $43.40 |
| SMT assembly | $9.78 |
| Confirm Parts Placement | $0.45 |
| Packaging fee | $0.53 |
| **Standard PCBA** | **$247.89** |

Each group's lines add up to its subtotal, and the two subtotals to the total.

## Against the orders of five

| | assembly | build time, assembly | setup | stencil |
|---|---|---|---|---|
| [console-s3](2026-10-24-console-s3-order.md), 5 boards | Economic | 1–2 days | $8.24 | $1.55 |
| [console-rp](2026-10-29-console-rp-order.md), 5 boards | not on its page; planned Economic | 1–2 days | not recorded | not recorded |
| this quote | Standard | 3–4 days, or 2–3 for $49.63 | $25.75 | $8.27 |

- **The orders of five didn't have this.** Both logged 1–2 days of assembly, and neither page
  records a choice of build time or a charge for a faster one.
- **The PCB is still 24 hours.** The extra days are assembly's.
- **The likely reason is Standard assembly, not a busy factory.** The quote is on Standard.
  console-s3's order was on Economic, and console-rp's was planned so (its page doesn't record the
  type or its fees). The setup fee and stencil are about three and five times console-s3's, and
  "Feeders Loading fee" is a line the earlier pages don't have. This is read from the fees, not
  from anything JLCPCB said.
- **Why the quote is on Standard isn't known.** The quantity, something on the board, or a box
  ticked on the quote's first page could each do it. Mono's README plans Economic, one side.
  Whether Economic was offered at this quantity wasn't recorded.
- **3–4 days is the one selected** in the screenshot. Whether the page opens that way wasn't
  recorded.
- **The weight fits 20 boards.** console-rp's five were 0.41 kg on its order page, 0.08 kg a
  board; 1.85 kg over 20 is 0.09 kg.

## What this means for the real order

Its invoice ([the order](2026-11-09-mono-order.md)) gives 20 boards and $275.26 for them, $9.57
more than this quote, but not the assembly type or build time. If it is also on Standard at the free build time, 3–4 working days
of assembly after the boards are made, against 1–2 for the fives, would account for the wait
without anything having gone wrong.

## Still to record

- [x] The real order of 20: [its invoice](2026-11-09-mono-order.md). Its order page is still to come
- [ ] The real order's assembly type, the build time chosen, and its status and dates
- [ ] This quote's quantity, from its PCB tab
- [ ] Whether Economic assembly is offered for Mono at 20, and what forces Standard if not
- [ ] For the next run: whether the 2–3 day option ($49.63 here) is worth it
