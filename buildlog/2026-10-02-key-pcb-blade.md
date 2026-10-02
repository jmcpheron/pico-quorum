# Key PCB rev A: the PCB is the plug

The first custom board. The plan was a secure element on a tiny board inside a dual-plug handle.
Instead, the board is the plug: gold fingers on one edge go into a card-edge socket on the console.
The design is in [hardware/key-pcb](../hardware/key-pcb/README.md). The order steps are in
[ORDERING.md](../hardware/key-pcb/ORDERING.md).

## Decided

- **Fingers sequence the contacts.** GND starts 0.5 mm from the edge, the signals at 1.25 mm, and
  DETECT at 2.0 mm, so GND mates first and DETECT last. DETECT is tied to GND on the key, so the
  console powers the key only at full depth. These are Build 1's GPIOs, so the firmware doesn't
  change.
- **Two boards, one blade.**
  - key-a: SOIC-8, bare boards, hand-soldered.
  - key-b: UDFN-8, assembled by JLCPCB.
  - Both have a USBLC6-2SC6 ESD array and a 100 nF cap. KEY ID and RST have fingers but nothing
    fitted.
- **ATECC608C first.** It is P-256 only, which is what the Safe passkey signer uses. A Trust M key
  (key-c) can use the same finger map.

## Found

- **No gold-finger option for this board.** JLCPCB's gold-finger option, with its bevel, needs a
  board or panel of at least 50 × 50 mm, and Economic assembly doesn't support gold fingers at all.
  Rev A orders plain ENIG instead, which plates every pad gold, fingers included, with no bevel.
- **The finger numbers come from EDAC.** EDAC is the one 0.100″ card-edge maker found that
  publishes the card side: 1.40 mm fingers, the contact point about 4.3 mm in, and a 2.03 mm
  in-contact key slot. Sullins (in stock) takes the same card but publishes no contact point.
- **KiCad's 2×3 mm DFN footprint is the wrong one for the ATECC608 UDFN.** Microchip's land
  pattern has its pad rows 2.90 mm apart, which is KiCad's `DFN-8-1EP_3x2mm_P0.5mm_EP1.3x1.5mm`.
- **The SOIC ATECC608C was out of stock at Digi-Key**, due January 2027.

## Checked

`tools/keypcb check` on both boards:
- ERC: 0 errors, 0 warnings.
- DRC: 0 violations, 0 unconnected, schematic parity clean.

`tools/keypcb fab` wrote the Gerber zips, BOMs and CPLs. Nothing has been ordered yet.
