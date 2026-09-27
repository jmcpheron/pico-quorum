# tools

Inherited picowallet scripts (`pico`, `push`, `emu`, `qr`, `wiring`, the `zez*` case generators
and more) are unchanged; see the upstream half of [`../README.md`](../README.md).

PicoQuorum additions:

- [`vectors/`](vectors/): generates the Safe hash test vectors, and what `firmware/decode.py` must
  say about each one
- `quorum` and [`mock-tx-service/`](mock-tx-service/): the console's 2-of-3 Family Safe on the
  laptop, serving Safe's transaction-service endpoints with two simulated co-signers.
  - It runs simulated (`serve`), or as a real Safe on an Anvil fork of Base (`up`), where the
    chip's approvals execute.
  - `e2e` runs one approval end to end on the fork with the emulator.
  - It also regenerates the screenshot walkthrough in [`../docs/quorum-ui/`](../docs/quorum-ui/).

- `wiring-breadboard`: draws the breadboard version and the knob close-up for
  [`../hardware/wiring/BREADBOARD.md`](../hardware/wiring/BREADBOARD.md); `--check` compares its wire list

- `wiring-build1`: draws [`../hardware/wiring/build1-wiring.svg`](../hardware/wiring/build1-wiring.svg);
  `--check` compares its pin table with BUILD1.md, hardware/HANDOFF.md and `firmware/bench1.py`

- [`fonts/`](fonts/): renders the console's anti-aliased fonts (Atkinson Hyperlegible, OFL) into
  `firmware/qf_*.bin`; `firmware/fonts.py` draws them

Still to come: provisioning scripts.
