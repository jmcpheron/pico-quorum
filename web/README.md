# web: the front page and the app

Two static pages, served by GitHub Pages from `docs/`:

- **The front page**, `docs/index.html` (from `src/home.html` and `src/home.css`): what PicoQuorum is,
  how an approval goes, the console's screens, where it stands, and a big green **Launch app**.
  No script.
- **The app**, `docs/app/` (from `src/main.mjs`), described below.

The app closes the loop on a PicoQuorum Safe:
open any Safe, see its owners and queue, check every confirmation in the browser, and execute with
the signatures laid out the way the Safe expects. Safe{Wallet} can't do that last step when a
contract signature (a PicoQuorum key's) is one of two or more confirmations: GS021
(`docs/upstream/safe-wallet-gs021/`). This is `tools/quorum live exec`, without the terminal.

What it does:

- **Safes.** Open a Safe by chain and address (or a `basesep:0x…` / Safe{Wallet} link). Owners,
  threshold and nonce are read from the Safe over RPC, not from Safe's service. Links are
  shareable (`#/safe/basesep/0x…`), and Safes can be saved in the browser.
- **Queue.** From Safe's transaction service. Each transaction's hash is recomputed here and by the
  Safe, the console's verify code is shown, every confirmation is checked (ECDSA recovered, contract
  signatures asked of the owner contract), and anything the console would refuse outright is flagged.
- **Propose.** **New transaction** on a Safe builds a send (ETH or a token), an owner change
  (add, remove, replace), a threshold change, a rejection or a contract call, all plain calls with
  no gas refund. The review shows the verify code and hash blockie the console will show. The
  wallet signs the SafeTx (EIP-712) as one owner, the signature is checked to come from it, and it
  goes to Safe's service (`src/propose.mjs`). A queued transaction can be confirmed from the wallet
  (**Confirm with wallet**) or cancelled with **Propose a rejection** at its nonce.
- **Execute.** The first `threshold` valid confirmations are packed by `tools/mock-tx-service/sigs.mjs`
  (the same file the laptop tools and tests use), simulated against the chain, then sent by the
  browser wallet (EIP-1193 / EIP-6963). The page holds no key.
- **Keys.** `docs/registry/keys.json` lists keys with attestation bundles. Each bundle is checked in
  the browser (`src/attest.mjs`, the same checks as `tools/quorum verify`), and a listed owner that
  passes gets a **Verified PicoQuorum key** badge. A key's page shows the checks, and deploys its
  signer proxy on a chain from the wallet (`tools/quorum live enroll`). Any bundle can be checked
  locally under **Check a bundle**.
- **Releases.** `docs/releases/index.json` (from `tools/release`), each release with its
  fingerprint's blockie. Type the eight digits from a console's Device screen to see which release
  it runs.
- **Blockies.** Every Safe, owner, key, recipient and confirmation has its blockie, and each queued
  transaction shows its hash's blockie beside the verify code. `src/blockies.mjs` draws the same
  picture as the console (`firmware/blockies.py`), Safe{Wallet}, MetaMask and Etherscan: the seed is
  the address or hash in lower case.
- **Saved in the browser.** Saved Safes (rename, remove, with their last-seen threshold), the Safes
  opened lately, and an address book of names you give owners.
- **Settings.** The address book; a backup file of saved Safes and names, and restoring one (it
  merges, and leaves the API key and RPCs out); your own Safe API key (developer.safe.global) and
  RPC endpoints, kept in the browser.

## Build and test

```sh
cd tools/mock-tx-service && npm ci && cd ../../web
npm ci
npm test          # the browser's logic against the CLI verifier, sim.mjs, firmware/safe_tx.py, decode.py and blockies.py
npm run build     # writes docs/app/, docs/index.html and docs/home.css (commit them: Pages serves the branch)
npm run e2e       # the built app in Chromium: propose, confirm, reject, refusals (fake wallet, chain and service)
```

`e2e.mjs` needs a Chromium: `npx playwright-core install chromium` once, or `PQ_CHROMIUM=/path/to/chrome`.
Nothing leaves the machine: the wallet holds anvil's public test keys, and the chain and Safe's
service are fakes that make the real service's checks. `SHOTS=dir` keeps screenshots.

`build.mjs` bundles `src/main.mjs` with esbuild (viem and noble pinned in `package.json`), copies the
Atkinson Hyperlegible fonts (SIL OFL), writes `index.html` with subresource-integrity hashes, and
records every file's SHA-256 in `docs/app/BUILD.json`. It also writes the front page with an integrity
hash for its stylesheet; the front page uses the app's fonts. Rebuild from the same commit and compare.
The pinned values (passkey factory, services, known contracts) come from `firmware/quorum_cfg.py`.

## Trust

- The page is static: no server, no analytics, no third-party scripts or fonts, a strict CSP.
- The service is only a queue. Hashes and signatures are checked against the chain before anything
  is offered for execution, and the transaction is simulated first.
- Your wallet shows the transaction and asks. The Safe's threshold is the real control.
- A badge says a genuine Trust M holds the key and the owner address follows from it, not who holds
  the chip (`docs/mainnet/THREAT-MODEL.md`).

## Next

Owner ceremonies from a bundle, the console's decode pages in the
browser through the emulator's WebAssembly MicroPython, and a fleet view.
