# Networks

| Chain | ID | Service | Status |
|---|---|---|---|
| Base Sepolia (testnet) | 84532 | `api.safe.global/tx-service/basesep` | tested end to end on the Pico |
| Base | 8453 | `api.safe.global/tx-service/base` | signer deployed, Safe checked; first approval pending ([LADDER](../LADDER.md#rung-3-base-a-few-dollars)) |
| Ethereum | 1 | `api.safe.global/tx-service/eth` | contracts checked onchain; no Safe yet ([LADDER](../LADDER.md#rung-4-ethereum-mainnet-a-few-dollars)) |
| Local (laptop) | 31337 | `tools/quorum`, set with `QUORUM_URL` | development only; nothing signed here is valid anywhere else |

The chain → service table is built into the console (`firmware/quorum_cfg.py` `"services"`).

## One key, a Safe on each chain

A Safe exists on one chain. The same Safe address on another chain is a different Safe, or no
Safe at all. So "the console on Base and Ethereum" means a Safe on each, with the console as an
owner of both.

The console's owner address is the same on every chain. It comes from the key and Safe's passkey
signer contracts, and those sit at the same addresses on Base, Base Sepolia and Ethereum
(`tools/vectors/webauthn.mjs --chain eth` checks this against a chain). You still deploy the small
signer contract once on each chain (`tools/quorum live enroll --chain C`) before that chain's
Safe accepts the console's signatures.

## Watching several Safes

`QUORUM_SAFES` in the board's `secrets.py` lists up to 4 Safes, on any mix of chains (two on the
same chain is fine too):

```python
QUORUM_SAFES = [
    {"chainId": 8453, "address": "0x...", "name": "Family Safe"},
    {"chainId": 1, "address": "0x...", "name": "Vault"},
]
```

`tools/quorum live pico --chain base,eth` writes this for you.

- **Polling.** The console asks about one Safe per poll, in turn. With an API key it polls every
  20 s, or every 10 minutes after 10 quiet minutes. So with two Safes, each is asked about every
  40 s while you're using it. That spends the API key's monthly quota at the same rate as one
  Safe. Lower `QUORUM_POLL_S` for faster updates; Device (X) counts requests since boot.
- **Just after boot**, each Safe is asked about once straight away. After you sign, that Safe is
  asked again at once.
- **One service down** doesn't hide the others: home says `1 offline`, and Device names which one.
- **Why can't a transaction be signed on the wrong chain?** The chain ID is part of every Safe
  transaction hash. The console takes it from its own list, never from the service. A transaction
  hashed for Base Sepolia but served as Ethereum's is refused.

## What the console recognises, per chain

Tokens, batchers and known contracts are listed per chain in `quorum_cfg.py`. `"*"` holds the
addresses that are the same contract on every chain: Safe's MultiSendCallOnly 1.4.1 and 1.3.0,
and Permit2. So Circle's USDC shows as **USDC · known** only on its own chain. On any other chain
that address is an unknown contract, and the console says so.

## Adding a chain

The chain needs a hosted Safe transaction service (OP Sepolia has none; OP mainnet has one, at
`oeth`), and Safe's passkey signer contracts deployed at the pinned addresses.

1. Check the signer there, read only:
   `node tools/vectors/webauthn.mjs --chain <name>`. This needs an entry in that script's
   `CHAINS`.
2. In `firmware/quorum_cfg.py`, add the service under `"services"`, the chain's name under
   `"chains"`, and its tokens and contracts under their chain ID. Give it a pill colour in
   `quorum_ui.py` `CHAIN`.
3. Add it to `CHAINS` in `tools/mock-tx-service/live.mjs`, so `live enroll`, `status`, `exec`
   and `pico` know it.
4. Run the tests (`node test-vectors/run-console.mjs`, `node tools/mock-tx-service/test.mjs`),
   then `tools/fw push console`: the chain list is part of the image.
