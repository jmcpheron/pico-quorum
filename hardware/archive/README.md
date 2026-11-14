# Archive: earlier boards and builds

Designs from October 2026 that the work has moved on from. None of the boards here
was ordered, and none of the builds was wired. They are kept because each was worked through and
checked, and later boards took parts from them. What the work is on now:
[Mono](../mono/README.md) ([hardware/](../README.md)).

Each folder is as it was on 2026-11-11, with its own README. The links in those READMEs were
brought up to date when the folders moved here; their text was not.

## Boards

| | what it was | where it stopped |
|---|---|---|
| [console-pcb/](console-pcb/README.md) (console-a P1) | Build 1 on one board: a Pico 2 W, the 2.8″ screen, a knob, and a USB-C plug for key-c. The options weighed are in [OPTIONS.md](console-pcb/OPTIONS.md) | drawn, its checks passing; the screen's size and the plug's fit not checked on a bench |
| [console-a/](console-a/README.md) | a second one-board console, on the Waveshare Pico-LCD-1.3's pins: a bare 1.3″ panel, a d-pad and A/B/X/Y, pads for the key | designed and checked 2026-10-07, not ordered ([ORDERING.md](console-a/ORDERING.md)) |
| [console-pocket/](console-pocket/README.md) | the pocket size, 51 × 85 mm: the Pico 2 W soldered on the back as a module, a bare 1.54″ panel, seven buttons | **don't order it as it is**: KiCad's DRC found 138 violations on 2026-10-23, from a rotation bug since fixed in its generator. Not regenerated |
| [console-usb/](console-usb/README.md) | the S3 console with no radio in use: the bare ESP32-S3 chip, no antenna, and a USB-C whose only data path is a CH340C serial bridge | placed, not routed. Its idea went on to console-rp, on a chip with no radio at all |
| [feather-wing/](feather-wing/README.md) (wing-a, wing-b) | a board behind Adafruit's Feather ESP32-S3 Reverse TFT, carrying a protected USB-C plug for key-c | checked in KiCad 2026-10-23, not ordered |

## Builds

Rigs put together from bought boards ([builds/](builds/README.md)). All four were written up and
none was wired.

| | what it was |
|---|---|
| [builds/feather-pigtail/](builds/feather-pigtail/README.md) | the Feather with a USB-C cable soldered to its pins for key-c, a tray and a bezel |
| [builds/feather-knob/](builds/feather-knob/README.md) | the ESP32-S3 TFT Feather with an EC11 knob in place of two buttons |
| [builds/pico-sign/](builds/pico-sign/README.md) | Build 1 as a box: a knob, a hold-to-sign switch, a key-c in a cartridge; its case, the prism, and [four case concepts](builds/pico-sign/case/CONCEPTS.md) |
| [builds/pico-sign-handheld/](builds/pico-sign-handheld/README.md) (Picoquorum Handheld) | pico-sign with the 2.4″ screen in a flat case, with [16 assembly steps](builds/pico-sign-handheld/ASSEMBLY.md). The site still has [its page](https://picoquorum.app/handheld/), kept for links already shared |

## What still reads these folders

Don't delete or rename these without changing what uses them:

| here | used by |
|---|---|
| `console-pocket/lib/picoquorum.pretty/PicoQuorum_Mark.kicad_mod` | Mono's and console-rp's generators copy the mark from it (`gen_mono.py`, `gen_console_rp.py`), as does console-usb's |
| `console-pocket/gen_console.py` | console-s3's and feather-wing's generators import it |
| `feather-wing/lib/pqwing.pretty/` | PicoquorumKey's `tools/gen/make_footprints.py` copies wing-b's plug |
| `builds/pico-sign/case/concepts.py` | the renderer every case in [`cad/consoles/`](../../cad/consoles/README.md) draws its pictures with, Mono's among them (`shell.py`) |
| `builds/pico-sign-handheld/case/out/assembly/` | `web/build.mjs` copies these pictures into the site's handheld page, and `web/handheld-card.py` draws its share card from them |
| `builds/feather-knob/` | where the firmware's `feather-knob` profile is written up. `firmware/board.py` and `firmware/lcd.py` name it at `hardware/builds/feather-knob/README.md`, its place before the move |

The tools still know these by name: `tools/keypcb check console-pocket` (and `console-a/console-a`,
`console-pcb/console-a`, `wing-a`, `wing-b`), and `tools/case build prism` (and `handheld`,
`feather-pigtail`, `pico-sign-concepts`, `pico-sign-wedge`).

## What was checked when the folders moved

No KiCad was to hand, so the generators that need it were not run. What was, on 2026-11-11:
- **Every path the generators and case scripts build** from their own place points at a file that
  is there.
- **feather-wing's self-check** (`gen_wing.py a --check`, `b --check`): clean.
- **The builds' checks:** `pico-sign/wiring.py --check` and `feather-knob/wiring.py --check` agree
  with `firmware/board.py`; `feather-pigtail/bench/swap_test.py` and `feather-knob/bench/dial_test.py`
  pass.
- **The cases** (`tools/case check`): the wedge rebuilds to the committed files. The prism, the
  concepts, the handheld and the Feather pigtail's tray rebuild with 16 files different from the
  committed ones, and with the same 16 at the commit before the move, on the same Linux machine. So
  those differences are older than the move; the committed files were left as they were.
- **Two checks fail here as they did before the move:** `console-a/gen.py check` (it no longer
  finds the key's default pins in `firmware/atecc.py`), and `console-pocket/gen_console.py --check`
  (the board [its README](console-pocket/README.md) says not to order).
