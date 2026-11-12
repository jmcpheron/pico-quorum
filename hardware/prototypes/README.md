# Early prototypes: the two ESP32-S3 boards

Two consoles on an ESP32-S3, each with its own Wi-Fi. They were designed apart in October 2026, to
order side by side and compare ([the order plan](ORDER-PLAN-2026-10-24.md)). Both were made, and the
first board of each runs. The work has since moved to the boards with no radio,
[console-rp](../console-rp/README.md) and then [Mono](../mono/README.md). These two are kept as
they were.

| | [console-s3](console-s3/DESIGN.md) | [PicoquorumKey](picoquorum-key/README.md) |
|---|---|---|
| shape | a stick, 64 × 22.86 mm | a badge, 50 × 53 mm (rev B) |
| the chip | ESP32-S3-WROOM-1-N8R2 on the back, soldered by hand | the same module, the same way |
| the screen | the 1.14″ 240 × 135 panel in a ZIF | the same |
| the key | ATECC608C on the board | UDFN ATECC608C on the board; rev B adds a key port for a [key-c](../key-pcb/key-c-usbc/README.md) |
| firmware | the `feather-s3` profile: it copies the Feather's pins | its own profile, `picoquorum-key`, which the image picks by the pull-ups on its key bus |
| where it stands | 5 boards came 2026-11-02. Board 1 runs ([its first day](../../buildlog/2026-11-02-console-s3-first-board.md)) | boards made, rev B. The first reported working, 2026-11-03 ([build log](../../buildlog/BUILDLOG.md)) |
| read first | [CONCEPT.md](console-s3/CONCEPT.md), [SPEC.md](console-s3/SPEC.md), [DESIGN.md](console-s3/DESIGN.md) | its [README](picoquorum-key/README.md) and [docs/](picoquorum-key/docs/DESIGN.md) |
| its case | the stick, [`cad/consoles/stick.py`](../../cad/consoles/README.md#the-stick-console-s3) | the badge, [`cad/consoles/badge.py`](../../cad/consoles/README.md#the-badge-picoquorumkey-rev-b) |

Around them:
- **The orders:** [console-s3's](../../buildlog/2026-10-24-console-s3-order.md), and
  [the 100 panels](../../buildlog/2026-11-03-panels-order.md) bought for its ZIF.
- **The Feather before them:** Adafruit's Feather ESP32-S3 Reverse TFT, where the console first ran
  on this chip and screen ([FEATHER-S3.md](../wiring/FEATHER-S3.md)).
- **Printable mock-ups** of both boards: [`tools/mockup/`](../../tools/mockup/README.md).

## What still reads these folders

- Mono's and console-rp's generators copy the screen's ZIF footprint from `console-s3/lib/pqs3.pretty/`.
- `tools/keypcb` knows console-s3 by name (`tools/keypcb check console-s3`), and `tools/case` builds
  the stick and the badge.
- `firmware/board.py` carries both pin profiles. Its comment names PicoquorumKey's pins at
  `hardware/picoquorum-key/docs/PINS.md`: they are at
  [picoquorum-key/docs/PINS.md](picoquorum-key/docs/PINS.md) now.

PicoquorumKey was built as a project of its own, with its own generators, tests and `tools/`. The
paths inside it start from its folder, so they didn't change. Where its files name another folder
of this repository in a description (`hardware/feather-wing`, `hardware/console-s3`), that is the
folder's place before 2026-11-11 ([what moved](../README.md#moved-on-2026-11-11)).
