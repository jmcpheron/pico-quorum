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

- `keypcb`: the key PCBs in [`../hardware/key-pcb/`](../hardware/key-pcb/), with KiCad 9's
  `kicad-cli`.
  - `check` runs ERC, then DRC with schematic parity.
  - `fab` writes the Gerber zip, and the BOM and CPL in JLCPCB's format.
  - `render` draws the top and bottom of each board.
  - `calc` works out the numbers behind the design: finger timing, I2C rise time, key power from
    a GPIO, and two ngspice runs. See [`../hardware/key-pcb/LEARN.md`](../hardware/key-pcb/LEARN.md).

- `brandkey-figures`: draws the figures in [`../docs/brandkey/`](../docs/brandkey/) for
  [`../docs/BRANDKEY.md`](../docs/BRANDKEY.md), and the Trust M object map in `../buildlog/images/`

- [`fonts/`](fonts/): renders the console's anti-aliased fonts (Atkinson Hyperlegible, OFL) into
  `firmware/qf_*.bin`; `firmware/fonts.py` draws them

- `fw` ([`board/fw.mjs`](board/fw.mjs)): the Pico as a production device, over USB.
  - `build console|ceremony` makes an image from `firmware/manifest.json`.
  - `backup` copies every file on the board, each checked by SHA-256, into `backups/` (gitignored).
  - `verify [--baseline]` is read-only: files, flags, the console's live state, and the chip.
  - `pin` writes `QUORUM_EXPECT` from the chip itself.
  - `push console|ceremony` backs up first, shows the plan and asks for a typed yes. Then it enters
    maintenance, copies, checks every hash, and deletes stale files.
  - Also `restore`, `logs`, and `measure tls` (run on the board from RAM).
  - `tools/usb push` no longer copies `secrets.py`, and refuses a production board.
- `check_config`: both ATECC608 tables, the legacy test table and quorum v1, with quorum v1 decoded
  again from the datasheet's bit tables. `--summary SNAPSHOT` prints a fresh chip's config CRC.
- [`board/shots.mjs`](board/shots.mjs): the walkthrough in
  [`../docs/firmware-production/`](../docs/firmware-production/).
