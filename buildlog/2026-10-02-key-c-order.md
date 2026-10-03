# key-c P2 ordered: the first key board

The first key board actually ordered is the USB-C proposal, not rev A. It's an ATECC608C (I2C,
SOIC-8) behind a USB-C receptacle used as plain wires, with JLCPCB assembling all 5. The design is
in [hardware/key-pcb/PROPOSALS.md](../hardware/key-pcb/PROPOSALS.md), and the files as ordered are
commit `ac34fc55` on `key-pcb-learn`.

## The order

| | |
|---|---|
| Placed | 2026-10-02 16:10, JLCPCB order **W2026100307101209** |
| PCB | **Y4-13710122A** (customer code 13710122A, order Y4), production order 86289523 |
| PCBA | Economic, top side, SMT026100263772 (JLCPCB's number, cut short on screen) |
| Quantity | 5 boards, 5 assembled |
| Board | 2 layers, 16 × 36 mm, 1.6 mm FR-4, LeadFree HASL, blue mask, white silkscreen, 1 oz, tented vias, 0.3 mm via holes, "Remove Mark", deburred edges |
| Approvals | Confirm Production file: yes. Confirm Parts Placement: yes |
| Tooling holes | added by JLCPCB (Economic) |
| Shipping | Global Standard Direct Line, 8–13 business days |
| Cost | PCB $6.22, PCBA $22.95 (after a $10 new-customer coupon), shipping $7.51, sales tax $2.28. **Total $38.96**, about $7.80 per assembled key |
| Timing | factory closed Oct 1–4 for the holiday; estimated ship date 2026-10-04 |

## Parts, as JLCPCB matched them

From the order's parts page. The maker is read from the part number.

| ref | part | MPN | maker | LCSC | JLCPCB type |
|---|---|---|---|---|---|
| U1 | secure element, I2C, SOIC-8 | ATECC608C-SSHDA-T | Microchip | C28975195 | Extended |
| U2 | 2-line ESD array, SOT-23-6 (3.5 pF, 5.25 V) | USBLC6-2SC6 | STMicroelectronics | C7519 | Extended |
| J1 | USB-C receptacle, 16 pins, 5 A, 7.35 mm | HC-TYPE-C-16P-01A | HCTL | C2894897 | Extended, plus a $0.03/pc special-handling fee |
| C1, C2 | 100 nF 16 V X7R ±10 %, 0402 | CL05B104KO5NNNC | Samsung Electro-Mechanics | C1525 | Basic |
| R1, R2 | 5.1 kΩ 50 V 62.5 mW thick film, 0402 | 0402WGF5101TCE | UNI-ROYAL | C25905 | Basic |
| TP1–TP4 | test pads on the back | (copper only, not assembled) | | | |

- **U1 is the SSHDA part, the I2C version.** SSHCZ is single-wire and would never answer the
  console.
- **JLCPCB buys a few spares** of the small parts (7 of U2 for 5 boards, for example).
- **The quote:** components $11.70, extended-part fees $9.27 (3 × $3.09), setup $8.24, stencil
  $1.55.

## The files

| what | SHA-256 |
|---|---|
| `key-c-usbc-gerbers.zip`, as uploaded | `99a6dbb54376a3be0319bdf24b05c34b59a89f06e64d144d533db4c7fc5d8c3a` |
| `bom.csv` | `35e4c74bba236b069fb0b4d20083d5f99ac83824c5c7ac436c0a2607fca88ca0` |
| `cpl.csv` | `71cbe0855ffa0489ed827248a1cd9645d6a2e000b907d65cbb106b7b41ee7704` |
| JLCPCB's production file, `key-c-usbc-gerbers_Y4.zip` | `d201d93096be3f5b463d4a1935a87e5e4cd1961694f1fbb1d9a71d7d4b7bfa9f` |

## Checking JLCPCB's production file

They send back their own CAM output (`ok/`, made with jlccam) next to the upload (`yg/`). Compared
against the design:
- **The input is unchanged.** `yg/` is byte-identical to the uploaded files, all 11 of them.
- **Drills match.**
  - All 29 of ours are there, at **0.000 mm** offset.
  - The 22 vias stay 0.30 mm.
  - The shell-leg slots went from 0.60 to 0.75 mm, the peg holes from 0.65 to 0.70 mm and the
    lanyard hole from 3.00 to 3.05 mm. That's plating allowance.
  - **They added 2 tooling holes, 1.152 mm**, at (2.1, 2.2) and (11.8, 34.4) mm from the
    bottom-left corner. Both are in plain ground pour with the pour cleared around them, away from
    any trace, the logo and the connector.
- **Copper** is the same except that cleared pour, plus a hair of etch allowance on the edges.
- **Silkscreen:** the logo and all the text are intact. Only marks touching pads were trimmed.
- **Mask:** the usual fab additions. There's a mask-free strip along the board edge, openings at
  the tooling holes and slightly larger pad openings.
- **Settings** in their parameter file: lead-free HASL, blue/white, vias covered, no order mark,
  16 × 36 mm, auto-CAM passed.
- Checked again by hand in KiCad's GerbView, then **confirmed**.

## Placement, in JLCPCB's preview

- **U1 and U2 came up turned 90°.** Each was rotated until its pin-1 dot sat at the silkscreen
  triangle and its legs were on the pads.
- **J1 was nudged slightly** onto its pads. In the 3D view its pegs drop into the peg holes and its
  shell tabs into the slots.
- **C1, C2, R1 and R2** were left as placed.
- **These changes live in JLCPCB's system, not in the file.** The `cpl.csv` you can download from
  the order is byte-identical to the one uploaded (same SHA-256 as above). The rotations and the
  nudge will only show up in the parts-placement confirmation.

## Still to record

- [ ] The PCBA's final parts list, from **Product Details** on the order. It should confirm C2 on
      the C1525 line and the quantities JLCPCB bought
- [ ] The parts-placement confirmation
- [ ] Tracking, arrival, and the first bench test (the console end needs its protected VBUS switch
      and separate CC sensing first: see PROPOSALS.md)
