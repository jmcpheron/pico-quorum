# Safe{Wallet}: GS021 when a confirmation is a contract signature

The Safe web app can't execute a transaction that a PicoQuorum key approved once there are two or
more signatures. It fails with GS021 because the chip's approval is an EIP-1271 contract signature,
and the web app rebuilds every stored confirmation as a plain signature. Until this is fixed
upstream, `tools/quorum live exec` executes instead.

**Jason submits everything to Safe by hand.** This folder holds the drafts and the evidence:

| File | What |
|---|---|
| [ISSUE.md](ISSUE.md) | The issue, ready to paste: title plus body in their bug-report template. The reproduction script is inlined in a `<details>` block |
| [PR.md](PR.md) | The pull request, ready to paste: their PR template, with the Mermaid summary they require for AI-authored PRs and the CLA line. Replace `#ISSUE` with the issue number |
| [repro/](repro/) | `repro.mjs`, the self-contained reproduction: Anvil fork of Base Sepolia, throwaway keys, protocol-kit's own `buildSignatureBytes` for both layouts. It also prints the test fixtures (`--fixture`) |
| [0001-fix-keep-EIP-1271-contract-signatures-when-rebuildin.patch](0001-fix-keep-EIP-1271-contract-signatures-when-rebuildin.patch) | The fix and its test, one commit made with `git format-patch` against their `dev` at `5717e3a` |

## Before submitting: privacy

ISSUE.md, PR.md and the patch name no personal address, Safe or transaction. The patch's test
fixture comes from throwaway keys on a local fork. Keep it that way:

- [ ] **Screenshots:** attach only the redacted copies in `temp-safe-screenshots/redacted/` (local
  and gitignored). There are four from the desktop browser, and `20`–`23` from a mobile browser.
  The mobile ones are the web app on a phone, not Safe's mobile app. They were made from macOS text recognition and checked by running it again: no
  address, ENS name or timestamp is left, and no identicon either. Look them over once more before
  uploading.
- [ ] **No Tenderly link.** The in-app simulation link is public and shows the Safe and both
  signatures.
- [ ] **Nothing from the evidence log below.** It names personal addresses and Safes, which is fine
  in this private repo but not upstream.
- [ ] **Commit author.** The patch carries `Jason McPheron <jason.mcpheron@gmail.com>` as author,
  and that shows on the PR. To use GitHub's private address instead, run
  `git commit --amend --reset-author` after setting `git config user.email <id>+jmcpheron@users.noreply.github.com`.
  The id is in GitHub → Settings → Emails.

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

**Review, 2026-09-25.** A review of the drafts led to:
- narrowing the claim to a threshold of 2 or more (with a 1-of-2 control that works)
- keeping observed results, code analysis and untested scope apart
- a self-contained reproduction
- exact mobile scope
- the parser's rule stated and tested: it reads the encoded offset, requires it past the static
  part, and requires the data to run exactly to the end
- tests for both signer orders, multiple contract signatures, unchanged eth_sign and v = 1, and
  malformed input
- the wording fixes

All adopted. The Safe.sol link now points at the GS021 check itself (L306-L316); the suggested
range stopped short of it.

What's been verified so far:
- On a private fork of Base Sepolia: the fixture Safe (throwaway keys) reverts with GS021 in the web
  app's layout and executes in the fixed one.
- On a fresh fork with `repro/repro.mjs`:
  - a 2-of-2 (EOA, contract) and a 3-of-3 (contract, EOA, contract) revert with GS021 in the
    current layout, and execute in the fixed one: `ExecutionSuccess`, the recipient paid, and the
    logged bytes equal the fixed layout
  - a 1-of-2 control works both ways
- Locally, on a focused install:
- The 11 unit tests pass in a node environment.
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

## Evidence log (private: names personal addresses, don't paste upstream)

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
- **The web app on mainnet** showed "Simulation failed" in Safe Shield and "Cannot estimate", then
  *This transaction will most likely fail… GS021*. Clicking Execute gave *Could not submit the
  transaction. Error code GS021*.
  - Four screenshots, before, during and after, are in `temp-safe-screenshots/` (local only), with
    redacted copies in `redacted/`.
  - Tenderly simulation (public link, private use only):
    https://dashboard.tenderly.co/public/safe/safe-apps/simulator/7afa3560-c7f6-44df-a583-f2b1e560fe46
- **Still to capture:** the app version and the execution tx.

### 2026-09-25, a private fork of Base Sepolia: the public fixture

- **The Safe.** Throwaway keys: EOA `0x27d0D792…A43E` and passkey signer `0x4D5Df238…5E91`, which
  own a fresh 2-of-2 Safe 1.5.0 at `0x28EB931d…7A71` on an Anvil fork (block 47295478). None of it
  is on a public chain.
- **The result.** The web app's layout (450 bytes) reverts with GS021. The fixed layout (450 bytes)
  executes (`ExecutionSuccess`), and the `SafeMultiSigTransaction` event logs exactly those bytes.
  That is the patch's test fixture.
