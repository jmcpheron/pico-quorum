# web: the Execute page

A static page, served by GitHub Pages from `docs/app/`, that closes the loop on a PicoQuorum Safe:
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
- **Execute.** The first `threshold` valid confirmations are packed by `tools/mock-tx-service/sigs.mjs`
  (the same file the laptop tools and tests use), simulated against the chain, then sent by the
  browser wallet (EIP-1193 / EIP-6963). The page holds no key.
- **Keys.** `docs/registry/keys.json` lists keys with attestation bundles. Each bundle is checked in
  the browser (`src/attest.mjs`, the same checks as `tools/quorum verify`), and a listed owner that
  passes gets a **Verified PicoQuorum key** badge. A key's page shows the checks, and deploys its
  signer proxy on a chain from the wallet (`tools/quorum live enroll`). Any bundle can be checked
  locally under **Check a bundle**.
- **Settings.** Your own Safe API key (developer.safe.global) and RPC endpoints, kept in the browser.

## Build and test

```sh
cd tools/mock-tx-service && npm ci && cd ../../web
npm ci
npm test          # the browser's logic against the CLI verifier, sim.mjs and firmware/safe_tx.py
npm run build     # writes docs/app/ (commit it: Pages serves the branch)
```

`build.mjs` bundles `src/main.mjs` with esbuild (viem and noble pinned in `package.json`), copies the
Atkinson Hyperlegible fonts (SIL OFL), writes `index.html` with subresource-integrity hashes, and
records every file's SHA-256 in `docs/app/BUILD.json`. Rebuild from the same commit and compare.
The pinned values (passkey factory, services, known contracts) come from `firmware/quorum_cfg.py`.

## Trust

- The page is static: no server, no analytics, no third-party scripts or fonts, a strict CSP.
- The service is only a queue. Hashes and signatures are checked against the chain before anything
  is offered for execution, and the transaction is simulated first.
- Your wallet shows the transaction and asks. The Safe's threshold is the real control.
- A badge says a genuine Trust M holds the key and the owner address follows from it, not who holds
  the chip (`docs/mainnet/THREAT-MODEL.md`).

## Next

Propose and reject from the page, owner ceremonies from a bundle, the console's decode pages in the
browser through the emulator's WebAssembly MicroPython, and a fleet view.
