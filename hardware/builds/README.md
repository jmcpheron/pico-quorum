# builds

A build is a rig put together from bought boards: a Feather, a Pico and a screen, a key on some
wires. The boards we design have folders of their own in [`hardware/`](../README.md). Each build
here has one folder:

```
builds/<build>/
  README.md     what it is, its parts, its wiring, what it runs, its status
  bench/        scripts for this build only (optional)
  case/         its CadQuery generator, and its STLs in out/ (optional)
```

Each README opens with the same five rows: board, key, runs, case, status.

Older builds aren't here yet. They are listed with every other configuration in
[hardware/README.md](../README.md#every-configuration).

## Firmware

**The console image knows boards, not builds.** `firmware/board.py` has one profile per board
(`waveshare`, `build1`, `esp32`, `feather-s3`, `feather-knob`). A build whose pins match a profile
runs the console image with it, unchanged. A build gets a profile of its own only when the console must behave
differently on it. That is a firmware change, so it is a new release fingerprint (AGENTS.md).

**Demo and test screens for one build live in its `bench/`.** As in
[`wiring/feather-s3/`](../wiring/feather-s3/):
- standalone, copied to `/bench` on the board, never into `firmware/manifest.json`, so they are
  not part of any console image
- read-only on the chip: nothing makes, uses or reads a private key, writes or locks anything
- they may import `firmware/atecc.py` and `firmware/chipcfg.py`, copied next to them

## The builds

| build | board | key | runs |
|---|---|---|---|
| [feather-pigtail](feather-pigtail/README.md) | Feather ESP32-S3 Reverse TFT | a USB-C cable soldered to its pins | `feather-s3`; `bench/swap.py` |
| [feather-knob](feather-knob/README.md) | ESP32-S3 TFT Feather (5483) and an EC11 knob | a USB-C adapter on its header pins | `feather-knob`; `bench/dial.py` |
| [pico-stomp](pico-stomp/README.md) | Pico 2 W, the 2.4″ screen, an EC11 knob and a footswitch for Sign | a USB-C plug standing out of the lid | `build1`, `SCREEN = "2.4"`; `bench1.py` |
