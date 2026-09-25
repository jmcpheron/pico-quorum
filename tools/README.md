# tools

Inherited picowallet scripts (`pico`, `push`, `emu`, `qr`, `wiring`, the `zez*` case generators
and more) are unchanged; see the upstream half of [`../README.md`](../README.md).

PicoQuorum additions:

- [`vectors/`](vectors/): generates the Safe hash test vectors, and what `firmware/decode.py` must
  say about each one
- `quorum` and [`mock-tx-service/`](mock-tx-service/): a simulated 2-of-3 Safe for the console,
  serving Safe's transaction-service endpoints on the laptop, with two simulated co-signers. It
  also regenerates the screenshot walkthrough in [`../docs/quorum-ui/`](../docs/quorum-ui/).

Still to come: provisioning scripts.
