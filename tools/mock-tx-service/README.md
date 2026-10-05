# The Family Safe on the laptop (`tools/quorum`)

A stand-in for Safe's transaction service that the console polls over WiFi. Behind it is the Family
Safe in one of two modes:

- **simulated** (`tools/quorum serve`): no chain. Quick, used for the screenshots and the tests.
- **forked** (`tools/quorum up`): a real Safe 1.4.1 on an Anvil fork of Base. The chip's
  approvals execute for real. This is test-ladder rung 1 in [KICKOFF](../../docs/KICKOFF.md#test-ladder).

## The service

- **The console's endpoints.** It answers the ones the console uses, at the real service's paths
  and in its shapes:
  - `GET /api/v1/safes/{safe}/`
  - `GET /api/v2/safes/{safe}/multisig-transactions/`
  - `POST /api/v1/multisig-transactions/{hash}/confirmations/`

  The console's code (`firmware/txservice.py`) needs only a URL change to talk to `api.safe.global`.
- **The Safe.** It is `firmware/quorum_cfg.py`'s: the Family Safe on chain 31337, 2 of 3.
  - ALICE and BOB are simulated co-signers. They are anvil's test accounts 1 and 2, and they sign
    real ECDSA.
  - The third owner is whichever console announces its P-256 key on `/sim/device`.
- **How a chip key owns the Safe.** It goes through its own SafeWebAuthnSignerProxy: Safe's
  audited passkey signer, safe-modules passkey v0.2.1, whose addresses are pinned in
  `quorum_cfg.py` `"signer"`.
  - The owner is the proxy's CREATE2 address, which the console computes itself.
  - The console confirms with a contract signature (v = 0) carrying a WebAuthn assertion over the
    safeTxHash (`firmware/webauthn.py`). `sigs.mjs` is the laptop's side of that.
- **Confirmations** are checked the way the Safe would check them, against viem's hash of the
  fields:
  - ECDSA: `recoverAddress`.
  - Contract signatures:
    - simulated: the WebAuthn message is rebuilt and the P-256 signature verified with noble
    - forked: the proxy's own `isValidSignature`, as Safe's transaction service does it

  A signature over a hash the service lied about is caught and logged as blind signing.
- **Execution** happens at threshold:
  - simulated: the nonce moves on, and owner and threshold changes take effect.
  - forked: `execTransaction` runs from anvil account 0, with the signatures laid out by
    `sigs.packSignatures`. A transaction that would revert stays queued, and the reason (a Safe
    `GSxxx` code) is shown.

## Commands

```sh
tools/quorum doctor           # node, python3, anvil, the emulator, the fork RPC, the LAN address
tools/quorum serve            # simulated: port 8787 (QUORUM_PORT), state in state.json; dashboard at /
tools/quorum up [--refork]    # forked: anvil on 127.0.0.1:8545 + the service on 8787; Ctrl-C stops both
tools/quorum e2e              # the console on the emulator approves on a fork (ports 8546, 8798)
tools/quorum release-e2e      # the console approves a PicoQuorum release on a fork; the approval holds on chain (8547, 8799)
tools/quorum scenarios        # the stories: sends, a batch, red ones, a lying service, a conflict
tools/quorum demo             # fresh Safe with the standard queue (on the fork: rolled back to setup)
tools/quorum propose refund --by bob
tools/quorum confirm 2 --as alice
tools/quorum status | log
tools/quorum shots [story..]  # docs/quorum-ui/shots, from the emulator (own simulated Safes on 8799 and 8797)
tools/quorum live key|enroll|status|rehearse|exec --chain local|basesep|base|eth   # real chains (live.mjs)
node tools/mock-tx-service/test.mjs
```

**A second simulated Safe**, for a console that watches two (`QUORUM_SAFES`): run another server
with its own port and state, and name the Safe it simulates:

```sh
QUORUM_STATE=/tmp/s2.json QUORUM_SIM_SAFE="84532:0x5a5a…5a5a:Test Safe" node tools/mock-tx-service/server.mjs --port 8798
```

The console's `secrets.py` gives each Safe its own `"url"`. `tools/quorum shots two` does exactly
this.

The live chains, and how far each one has got, are in [docs/LADDER.md](../../docs/LADDER.md).
`live` never holds a private key. It sends through your browser wallet (`wallet.html`, served on
127.0.0.1), or with `--account` from a Foundry keystore.

## The forked Safe (`up`)

- **Needs** Foundry: `curl -L https://foundry.paradigm.xyz | sh`, then
  `~/.foundry/bin/foundryup -i v1.8.3`. The tools find `~/.foundry/bin` on their own.
- **The fork.** Anvil forks Base mainnet (`QUORUM_FORK_RPC`, default `https://mainnet.base.org`)
  at one block, as chain 31337. Nothing signed on it is valid on Base: the chain ID is in every
  safeTxHash.
  - The first run picks the block and keeps it in `fork.json` (gitignored). Later runs fork the
    same state from anvil's cache, because the public RPC rate-limits. `--refork` picks a new
    block.
  - Safe 1.4.1, the passkey signer factory, USDC, Uniswap and the P-256 precompile are all there
    because they are on Base.
- **Setup** (`chain.mjs`) runs every time and does the same thing each time:
  - It creates the Family Safe (Alice, Bob, threshold 2, salt "PicoQuorum Family Safe") at the
    address pinned in `quorum_cfg.py`.
  - It gives the Safe 10 ETH and 10,000 USDC.
  - It snapshots the chain, so `demo` and `reset` roll back to that point.
- **A console joins** when it announces: the factory deploys its signer proxy, and the proxy is
  added as an owner.
  - The add is done by impersonating the Safe, so no nonce is used, the same as in the simulation.
  - On a live chain the other owners sign that change. The `add-owner` scenario is a real one.
- **Anvil's test accounts are booby-trapped on Base.** Their keys are public. On Base mainnet each
  of them carries an EIP-7702 delegation to a sweeper that forwards any ETH it receives. The fork
  inherits that code, so setup wipes it from the executor, Alice, Bob, Carol and Savings. **Never
  send anything to these addresses on a real chain.**
- **Point the Pico at it:** `up` prints the `QUORUM_URL` line for `secrets.py`.

`emu-chip.json` is a virtual ATECC608 with a throwaway key in slot 0. The screenshots and `e2e`
use it, so the same key shows in every picture. It is not a real key.
