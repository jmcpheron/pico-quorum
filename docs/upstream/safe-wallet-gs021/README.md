# Safe{Wallet}: GS021 when a confirmation is a contract signature

The Safe web app can't execute a transaction that a PicoQuorum key approved once there are two or
more signatures. It fails with GS021 because the chip's approval is an EIP-1271 contract signature,
and the web app rebuilds every stored confirmation as a plain signature. Until this is fixed
upstream, `tools/quorum live exec` executes instead.

**Jason submits everything to Safe by hand.** This folder holds the drafts and the evidence:

| File | What |
|---|---|
| [ISSUE.md](ISSUE.md) | The issue, ready to paste: title plus body in their bug-report template |
| [PR.md](PR.md) | The pull request, ready to paste: their PR template, with the Mermaid summary they require for AI-authored PRs and the CLA line |
| [0001-fix-keep-EIP-1271-contract-signatures-when-rebuildin.patch](0001-fix-keep-EIP-1271-contract-signatures-when-rebuildin.patch) | The fix and its test, one commit made with `git format-patch` against their `dev` at `5717e3a` |

## Status

- [ ] Issue opened on safe-global/safe-wallet-monorepo: #____
- [ ] Fork `jmcpheron/safe-wallet-monorepo`, branch `fix/contract-signatures-existing-tx` from `dev`
- [ ] Patch applied, with "Fixes #____" added to the commit message
- [ ] Full install; the utils, web and mobile tests, type-check and lint pass on the fork
- [ ] CLA read (https://safe.global/cla)
- [ ] PR opened from the fork: #____

## Working on the fork

```sh
# after forking on GitHub
git clone https://github.com/jmcpheron/safe-wallet-monorepo.git && cd safe-wallet-monorepo
git remote add upstream https://github.com/safe-global/safe-wallet-monorepo.git
git fetch upstream
git checkout -b fix/contract-signatures-existing-tx upstream/dev

# the fix, as a commit with its original message and authorship
git am ../pico-quorum/docs/upstream/safe-wallet-gs021/0001-fix-keep-EIP-1271-contract-signatures-when-rebuildin.patch
# once the issue exists, add its number:
git commit --amend      # add a line "Fixes #NNNN" above "Refs #3673"

corepack enable && yarn install
yarn workspace @safe-global/utils test src/utils/__tests__/safeTransaction.test.ts
yarn workspace @safe-global/web test src/services/tx/tx-sender
yarn workspace @safe-global/utils type-check && yarn workspace @safe-global/web type-check && yarn workspace @safe-global/mobile type-check
yarn workspace @safe-global/utils lint && yarn workspace @safe-global/web lint
yarn prettier

git push -u origin fix/contract-signatures-existing-tx
# open the PR from the fork's branch into safe-global:dev, with PR.md as the description
```

If `git am` doesn't apply cleanly because `dev` has moved on, `git am --3way` usually does. The
change is small, so it can also be redone by hand: the helper and its test, plus two call sites.

What's been verified so far, locally, on a focused install:
- The 5 new unit tests pass in a node environment.
- Prettier is clean.

**Not yet run:**
- the package's default jsdom test environment
- the web and mobile test suites
- type-check and lint

The full install on the fork covers all three.

## How we know

- **What GS021 means.** In Safe's `checkNSignatures` it is "the contract signature's offset points
  inside the static part": `s < requiredSignatures * 65`.
- **Where the web app goes wrong.** Its
  [`createExistingTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/web/src/services/tx/tx-sender/create.ts#L131-L141)
  adds each confirmation with `staticPart: () => data, dynamicPart: () => '', isContractSignature: false`.
  - A contract owner's confirmation comes back from the service as
    `{owner}{offset = 65}{00}{length}{data}`, so it is concatenated whole, with its offset still at 65.
  - Mobile has the same code in
    [`addSignaturesToTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/mobile/src/services/tx/tx-sender/create.ts#L40-L50).
- **Safe already knows.** In [#3673](https://github.com/safe-global/safe-wallet-monorepo/issues/3673),
  reported for a nested Safe owner, a maintainer wrote in Aug 2024: *"the bug is likely here:
  create.ts … The dynamic part is always set to `''` which is wrong for nested Safe signatures."*
  It was closed as "not planned" in Feb 2026, with no fix.
- **Safe's own SDK can already do it.** protocol-kit's `EthSafeSignature(signer, data, true)` plus
  `buildSignatureBytes` lay contract signatures out correctly (offsets past all the static parts).
  The web app just never marks them as contract signatures.

## Evidence log

Add to this as it comes in: date, chain, what was seen, links.

### 2026-09-25, Base Sepolia

- **The Safe.** [`0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43`](https://sepolia.basescan.org/address/0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43):
  Safe 1.5.0 L2, 2-of-3.
  - Owners: MetaMask `0x61D2…637F`, the Pico's `SafeWebAuthnSignerProxy` `0x2843…5E53`, and later
    `0x1289…f2DA`.
- **The confirmations were accepted.** Every contract-signature confirmation POSTed to
  `api.safe.global/tx-service/basesep` got 201: the emulator's on #0, the Pico's on #1–#3.
- **The web app failed.** Execute on #1 and #3 showed "Simulation failed", "Cannot estimate",
  GS021. There's a screenshot of #3; the in-app simulation's "View" link is still to capture.
- **Reproduced for #3.** Simulating `execTransaction` at block 47276343, the block before it
  executed:
  - Safe{Wallet}'s bytes (stored signatures sorted by signer and concatenated, 450 bytes): **GS021**.
  - protocol-kit's layout with the contract signature marked: **OK**, byte for byte what executed in
    [0xb8ee9c98…](https://sepolia.basescan.org/tx/0xb8ee9c98c966d24a85b115c1979c060e2cad9fd752d473ba25235df827c88c61).
- **Executed another way.** `tools/quorum live exec`, which lays the signatures out the same way as
  protocol-kit, executed #0–#3.
  [#1](https://sepolia.basescan.org/tx/0xe719116d86a019098679ba9b7d5e5263fed8c6fc4cd7181f573b4b3fa3860fde)
  and [#2](https://sepolia.basescan.org/tx/0xa046bd0c4289c9c8e75bb75aca40b6a09afea4c5f446f80e24c5fb6a393d9daf)
  are the Pico's approvals.

### 2026-09-25, Base mainnet

- **The Safe.** [`0xDebDE58b3ed0867d19285f6C8B0d81AdBC326Da9`](https://basescan.org/address/0xDebDE58b3ed0867d19285f6C8B0d81AdBC326Da9):
  Safe 1.5.0 L2, 2-of-3.
  - Owners: MetaMask `0x61D2…637F`, the Pico's `SafeWebAuthnSignerProxy` `0x2843…5E53`
    (deployed on Base in [0xe5e8ad92…](https://basescan.org/tx/0xe5e8ad92e571fe4b66927d5d0ce079b4f22ec3f0bc498e2b0d4fcc230f030dab)),
    and `0xb78e…AdBD8`.
- **Two confirmations, both accepted.** #0 (`safeTxHash 0x4c1e4f18…cef63ad6`) sends 0.000001 ETH:
  - `0xb78e…` confirmed with an EOA signature (65 bytes).
  - The Pico posted its contract signature itself: `api.safe.global/tx-service/base` stored it as
    `CONTRACT_SIGNATURE`, 385 bytes.
- **Reproduced again,** simulating `execTransaction` at block 51784275, with #0 pending:
  - Safe{Wallet}'s layout (450 bytes, contract signature offset 65): **GS021**.
  - The fixed layout (450 bytes, offset 130): **OK**.
- **Still to capture:** the web app's Execute screen on mainnet (screenshot), its simulation link,
  the app version, and the execution tx.
