# test-vectors

Safe transactions with known-correct hashes. **Every change to `firmware/safe_tx.py` (or to
`firmware/keccak.py`) must pass all of them.**

```sh
python3 test-vectors/run.py                 # CPython
(cd emu && npm install)                     # once
node test-vectors/run-micropython.mjs       # MicroPython 1.26, as on the Pico
```

Each run exits 1 on any mismatch.

## Where the expected values come from

Not from the firmware. `tools/vectors/gen.mjs` computes them with viem's `hashTypedData`:

- Made-up cases that cover a plain ETH send on Base and Base Sepolia, an ERC-20 transfer, a
  delegatecall to MultiSendCallOnly, nonzero gas-refund fields, an `addOwnerWithThreshold`, and
  uint256 edge values.
- `real-*` cases are executed transactions from the Safe{DAO} treasury on Ethereum mainnet. Their
  expected `safeTxHash` is the value Safe's transaction service published, and the generator
  checks that viem agrees before writing it.

Add a case in `tools/vectors/gen.mjs` and regenerate. Never edit `safe_tx.json` by hand.
