# The test ladder: from a simulated Safe to Ethereum mainnet

This is the tracker for getting the console's approvals from the laptop to real chains. Each rung
runs the same firmware and the same approval: someone proposes, the console shows it, you hold A,
and the Safe executes. Only the Safe and the money behind it change from rung to rung. Tick boxes
as things land, and link the evidence (a buildlog entry, an explorer link).

**How a chip key owns a Safe**, on every rung:

- **The owner.** Each key sits behind its own SafeWebAuthnSignerProxy, Safe's audited passkey
  signer (safe-modules passkey v0.2.1). The owner address is that proxy.
  - The console computes it itself (`firmware/webauthn.py`, pinned in `quorum_cfg.py` `"signer"`).
  - It's the same address on every chain.
- **The signature.** The console signs a WebAuthn assertion over the safeTxHash it computed from
  the fields on its own screen.
- **The contracts.** The factory, the Daimo verifier and the P-256 precompile are on Base, Base
  Sepolia, OP and Ethereum mainnet. They were checked onchain on 2026-09-25.

| # | Rung | Where | Who signs | Status |
|---|---|---|---|---|
| 0 | **Simulated** | `tools/quorum serve`, no chain | Alice and Bob (simulated), the real Pico | ✅ 2026-09-24, the real Pico ([buildlog](../buildlog/BUILDLOG.md)) |
| 1 | **Local fork** | `tools/quorum up`: Safe 1.4.1 on an Anvil fork of Base, chain 31337 | Alice and Bob, the chip | ✅ emulator (`tools/quorum e2e`) · ☐ real Pico |
| 2 | **Base Sepolia** | testnet: the Safe web app and `api.safe.global` | your browser wallet, the chip | ☐ rehearsal with the emulator · ☐ real Pico |
| 3 | **Base** | a few dollars | your browser wallet, the chip | ☐ |
| 4 | **Ethereum mainnet** | a few dollars (base fee about 0.05 gwei in Sept 2026) | your browser wallet, the chip | ☐ |

## Tools

Everything is `tools/quorum`. `tools/quorum doctor` checks what's installed.

| Command | What |
|---|---|
| `serve` | the simulated Family Safe (rung 0) |
| `up [--manual-exec]` | anvil forking Base, plus the service on a real Safe (rung 1). `--manual-exec` makes it wait for `live exec`, as Safe's real service does |
| `e2e` | rung 1 end to end with the emulator's chip, checked onchain |
| `live key [--from URL \| --usb \| --emu]` | the console's P-256 key and its owner address, kept in `live.json` (public values only) |
| `live enroll --chain C` | deploy the key's signer proxy (about 110k gas) |
| `live status --chain C --safe 0x…` | the Safe and its queue, every signature checked here |
| `live rehearse --chain C` | the emulator's console, with a throwaway key, signs on the real service: the spike before the Pico |
| `live exec --chain C NONCE` | execute, with the signatures laid out right (see [Known issues](#known-issues)) |

`C` is `local`, `basesep`, `base` or `eth`.

**How live sends.** Writes go through **your browser wallet**, the one you co-sign with in the Safe
web app: `live` opens a one-page form on 127.0.0.1 and the wallet shows the transaction and asks.
`--account NAME` sends from a Foundry keystore instead, and asks you to type `yes`.

- Before either, the terminal shows the destination, the value, what it does and the estimated
  cost.
- No private key ever passes through these tools.
- Every send is logged in `tools/mock-tx-service/live.json` (gitignored).

## Rung 1: the local fork

- [x] A real Safe 1.4.1 on a fork of Base, the Family Safe at its pinned address, funded with ETH and USDC
- [x] The chip's signature through the signer proxy, checked with `isValidSignature`, and the transaction executes (`e2e`, about 110k gas with the precompile)
- [x] Refusals still hold on a real chain: the tampered transaction is never signed
- [x] The live tools rehearsed against it: `live enroll`, `live rehearse`, and `live exec` through the wallet page
- [ ] **The real Pico** (with you at the board):
  1. `tools/quorum up`. It prints the `QUORUM_URL` line.
  2. Put that line in the board's `secrets.py`, then `tools/emu ship quorum`.
  3. The Pico announces, and its signer proxy becomes an owner.
  4. `tools/quorum demo`, then approve #0 on the Pico. The Safe executes on the fork.
  5. Write it up in the buildlog.

## Rung 2: Base Sepolia

**Before you start:**
- [ ] A browser wallet (MetaMask, Rabby…) with some Base Sepolia ETH, from the Superchain faucet
      (console.optimism.io/faucet), Coinbase's CDP faucet, or Sepolia ETH bridged over.
- [ ] A Safe API key from developer.safe.global:
  - `export SAFE_API_KEY=…` in your shell for the tools.
  - `QUORUM_API_KEY` in the board's `secrets.py`.
  - Never in the repo. Without a key the service allows 2 requests a second and 5,000 a month.

**Rehearsal: the emulator's throwaway key.** No hardware, and it settles the biggest unknown, whether
`api.safe.global` takes the console's confirmation.
- [ ] `tools/quorum live key --emu`
- [ ] `tools/quorum live enroll --chain basesep`
- [ ] Create a Safe in app.safe.global on Base Sepolia:
  - owners: your wallet, and the signer address `live key` printed
  - threshold 2
- [ ] `tools/quorum live status --chain basesep --safe 0x…`. Then send the Safe 0.001 ETH.
- [ ] In the web app, propose sending 0.0001 ETH somewhere, and sign it with your wallet.
- [ ] `tools/quorum live rehearse --chain basesep`: the service holds the emulator's confirmation.
- [ ] `tools/quorum live exec --chain basesep <nonce>`, sent from your wallet. Record the explorer link.

**The real Pico** (with you at the board). Its own key needs its own Safe, or it has to be added to
the rehearsal Safe as an owner.
- [ ] `tools/quorum live key --usb`. Check the address against the Pico's owners page (B, This key).
- [ ] `live enroll`, then a Safe with your wallet and the Pico's signer.
- [ ] On the board, in `secrets.py`:
  - `QUORUM_URL = "https://api.safe.global/tx-service/basesep"`
  - `QUORUM_SAFE = {…}`, `QUORUM_API_KEY`, `QUORUM_POLL_S = 20`
  - Then `tools/emu ship quorum`.
- [ ] Propose in the web app, approve on the Pico, `live exec`. Record the link in the buildlog.
- [ ] Measure the Pico's free heap after HTTPS and a real queue response. Real responses carry
      `dataDecoded`, so lower the `limit` if it doesn't fit.

## Rung 3: Base, a few dollars

Same steps as rung 2 with `--chain base` and `QUORUM_URL = ".../tx-service/base"`.

**Costs.** About $5 of ETH on Base in your wallet is plenty. Each of these is a fraction of a cent:
signer 110k gas, a Safe 310k, an execution 110k.

**Before any real money, on the board** (and the chip: [LOCKING.md](LOCKING.md)):
- [ ] `ENABLE_NETWORK_CONSOLE = False`. The network console is a passwordless REPL, and it can sign.
- [ ] `ALLOW_GENKEY = False` and `ALLOW_LOCK = False`.
- [ ] Don't make a new key in slot 0 while it owns a Safe. The owner address comes from the key, so
      a new key is a new owner, and the old one is gone. The plan is to lock slot 0 (only) once rung 2
      has proven it: [LOCKING.md](LOCKING.md).
- [ ] The Safe keeps a second owner that isn't the chip: your wallet. Losing the Pico must not lose
      the funds.

**Milestone:**
- [ ] A remote approval: the Pico on a different Wi-Fi, the proposal from your wallet.

## Rung 4: Ethereum mainnet, a few dollars

Same steps with `--chain eth` and `QUORUM_URL = ".../tx-service/eth"`.

- Checked onchain: the passkey factory has the same code as on Base, and the Daimo verifier, the
  P-256 precompile (Fusaka, EIP-7951), Safe 1.4.1 and `api.safe.global/tx-service/eth` are all
  there.
- At 0.05 gwei an execution is about 5.5e-6 ETH. Check `cast base-fee` first: L1 gas moves more
  than Base's.
- [ ] The same checklist as rung 3, then one approval.

## Known issues

- **The Safe web app can't execute these.** With a threshold of 2 or more, it drops a contract
  signature's data and the Safe reverts with GS021. Propose and sign there, then execute with
  `tools/quorum live exec`.
- **The signer proxy must be deployed before the console confirms.** The service checks the
  signature with an `eth_call` to it. `live enroll` does the deploy.
- **Service quota.** The console polls every `QUORUM_POLL_S` seconds, then every
  `QUORUM_IDLE_POLL_S` (default 120) after 10 quiet minutes. Each poll is 2 requests.
- **Rejecting on the console doesn't reject on the Safe.** Y only hides the transaction on that
  console, and the queue stays blocked at that nonce until someone replaces it. Rejecting it on the
  Safe itself would need its own proposal.
- **Anvil's public test accounts are booby-trapped on real chains.** On Base mainnet each carries an
  EIP-7702 sweeper. The fork wipes it; never send anything to them for real.
- **OP Sepolia has no hosted Safe service.** OP mainnet does (`oeth`), if we want it later.
- **Later:** Safe's main branch adds native P-256 owners (unreleased and unaudited). They would
  replace the proxy and the WebAuthn wrapper. All of that lives in `firmware/webauthn.py`.

## Open questions

- Should Y also offer to propose the Safe's own rejection (a zero-value self-call at the same
  nonce)?
- Which slot, and when to lock it: slot 0 as it is now, or a fresh key in a dedicated slot for real
  money?
- Is a browser-wallet executor enough for rung 3 and up, or does the console want to execute too
  (it would need gas money on a hot key)?
