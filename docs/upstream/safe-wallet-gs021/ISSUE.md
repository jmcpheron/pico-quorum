<!--
Paste-ready issue for https://github.com/safe-global/safe-wallet-monorepo/issues/new (template: "Bug report").
Title goes in the title field; everything below the line goes in the body.
PRIVACY: this text names no personal address, Safe or transaction. Attach only the REDACTED
screenshots (temp-safe-screenshots/redacted/, local only), and don't add the Tenderly link: it's
public and shows the Safe and its signatures. See README.md, "Before submitting".
-->

**Title:** Executing a queued tx fails with GS021 when a confirmation is an EIP-1271 contract signature

---

## Bug description

Safe{Wallet} can't simulate or execute a queued transaction when one of its confirmations is an EIP-1271 **contract signature** and the transaction has two or more signatures. The contract owner can be a nested Safe, or a passkey signer such as `SafeWebAuthnSignerProxy`.

The Execute screen shows "Simulation failed" and "Cannot estimate", then *This transaction will most likely fail. To save gas costs, reject this transaction. Error code GS021*. Clicking Execute anyway shows *Could not submit the transaction. Error code GS021*.

The Transaction Service accepts the confirmation, since it checks it with `isValidSignature`. The same transaction executes onchain when the signatures are laid out with the contract signature's data after the static parts.

The cause looks like the one diagnosed in #3673, which was closed as not planned: `createExistingTx` adds every confirmation as a plain signature, so a contract signature's data isn't laid out as a dynamic part.

## Environment

- Browser: Chrome
- Wallet: MetaMask
- Chain: Base Sepolia and Base. It isn't chain-specific.
- Safe: 1.5.0 L2, 2-of-3
- Owners: EOAs and a `SafeWebAuthnSignerProxy` (safe-modules passkey v0.2.1)

## Steps to reproduce

1. Use a Safe whose owners include a contract signer and at least one EOA, with a threshold of 2. The contract signer can be a passkey `SafeWebAuthnSignerProxy` or another Safe.
2. In Safe{Wallet}, propose a transaction and sign it with the EOA.
3. Confirm it with the contract owner: `POST /api/v1/multisig-transactions/{safeTxHash}/confirmations/` with its contract signature (v = 0). The service answers `201` and lists it as `CONTRACT_SIGNATURE`.
4. Open the transaction in Safe{Wallet} and click **Execute**.

We saw this on live Safes on Base Sepolia and on Base. We reproduced it on a local fork of Base Sepolia with a fresh 2-of-2 Safe 1.5.0 owned by throwaway keys: one EOA and one `SafeWebAuthnSignerProxy`.

The Transaction Service returns the two confirmations as:

| Owner | Stored signature |
|---|---|
| EOA | 65 bytes `{r}{s}{v}` |
| `SafeWebAuthnSignerProxy` | 385 bytes: `{owner}{offset = 65}{00}{length = 288}{abi-encoded WebAuthn data}` |

Calling `execTransaction` with each layout:

- **The bytes Safe{Wallet} builds** (both stored signatures sorted by signer and concatenated whole, 450 bytes) revert with **GS021**. The contract signature's offset is still 65, which is inside the 130-byte static part.
- **The same confirmations laid out by protocol-kit's `buildSignatureBytes`,** with the contract owner's added as a contract signature (offset 130, data after both static parts, also 450 bytes), **execute**. The Safe's `SafeMultiSigTransaction` event logs exactly these bytes.

I can share the live examples privately if that helps.

## Expected result

The transaction simulates and executes. That's what happens when the confirmation is added to the `SafeTransaction` as a contract signature, which protocol-kit already supports.

## Obtained result

GS021 in simulation, Execute can't estimate a fee, and submitting fails with GS021.

[`createExistingTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/web/src/services/tx/tx-sender/create.ts#L131-L141) adds every stored confirmation like this:

```ts
safeTx.addSignature({ signer, data, staticPart: () => data, dynamicPart: () => '', isContractSignature: false })
```

A contract owner's confirmation is stored as `{owner}{offset = 65}{00}{length}{data}`. Added as a plain signature, `buildSignatureBytes` concatenates it whole and keeps the offset at 65. With two signatures the static part is 130 bytes, and `checkNSignatures` requires `s >= requiredSignatures * 65`, so the Safe reverts with GS021.

Mobile has the same code in [`addSignaturesToTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/mobile/src/services/tx/tx-sender/create.ts#L40-L50).

A fix could rebuild stored confirmations as `EthSafeSignature`, and for `v = 0` add just the data after the length word with `isContractSignature: true`. `buildSignatureBytes` then lays the signatures out correctly. I have a small patch with a unit test built from the fork example above, and can open a PR.

## Screenshots

<!-- attach the redacted screenshots: the Execute screen with "Simulation failed" and "Cannot estimate",
     and the review screen with "Error code GS021" and "Could not submit the transaction" -->
