<!--
Paste-ready issue for https://github.com/safe-global/safe-wallet-monorepo/issues/new (template: "Bug report").
Title goes in the title field; everything below the line goes in the body. Add the screenshot where marked.
-->

**Title:** Executing a queued tx fails with GS021 when a confirmation is an EIP-1271 contract signature

---

## Bug description

Safe{Wallet} can't simulate or execute a queued transaction when one of its confirmations is an EIP-1271 **contract signature** and the transaction has two or more signatures. The contract owner can be a nested Safe, or a passkey signer such as `SafeWebAuthnSignerProxy`.

The Execute screen shows "Simulation failed" and "Cannot estimate", then *This transaction will most likely fail. To save gas costs, reject this transaction. Error code GS021*.

The Transaction Service accepts the confirmation, since it checks it with `isValidSignature`. The same transaction executes onchain when the signatures are laid out with the contract signature's data after the static parts.

The cause looks like the one diagnosed in #3673, which was closed as not planned: `createExistingTx` adds every confirmation as a plain signature, so a contract signature's data isn't laid out as a dynamic part.

## Environment

- Browser: Chrome
- Wallet: MetaMask
- Chain: Base Sepolia
- Safe: 1.5.0 L2, 2-of-3
- Owners: an EOA, a `SafeWebAuthnSignerProxy` (safe-modules passkey v0.2.1), and a second EOA

## Steps to reproduce

1. Use a Safe whose owners include a contract signer and at least one EOA, with a threshold of 2. The contract signer can be a passkey `SafeWebAuthnSignerProxy` or another Safe.
2. In Safe{Wallet}, propose a transaction and sign it with the EOA.
3. Confirm it with the contract owner: `POST /api/v1/multisig-transactions/{safeTxHash}/confirmations/` with its contract signature (v = 0). The service answers `201`.
4. Open the transaction in Safe{Wallet} and click **Execute**.

### Public example

Safe [`0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43`](https://sepolia.basescan.org/address/0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43) on Base Sepolia, nonce 3 (`safeTxHash 0x8d804e8e…`, a `swapOwner`).

The Transaction Service holds two confirmations for it:

| Owner | Type | Stored length |
|---|---|---|
| `0x2843705391b7E2cf06b0b964b532Ad9891535E53` (`SafeWebAuthnSignerProxy`) | `CONTRACT_SIGNATURE` | 385 bytes: `{owner}{offset = 65}{00}{length}{WebAuthn data}` |
| `0x61D24DE770314Eab9c267E47A968FC556744637F` | `EOA` | 65 bytes |

We simulated `execTransaction` at block 47276343, one block before the transaction executed:

- **The bytes Safe{Wallet} builds** (the two stored signatures sorted by signer and concatenated whole, 450 bytes) revert with **GS021**. The contract signature's offset is still 65, which is inside the 130-byte static part.
- **The same signatures laid out by protocol-kit's `buildSignatureBytes`,** with the confirmation added as a contract signature (offset 130, data after both static parts, also 450 bytes), succeed. These are the bytes that executed in [0xb8ee9c98…](https://sepolia.basescan.org/tx/0xb8ee9c98c966d24a85b115c1979c060e2cad9fd752d473ba25235df827c88c61), as logged by the Safe's `SafeMultiSigTransaction` event.

## Expected result

The transaction simulates and executes. That's what happens when the confirmation is added to the `SafeTransaction` as a contract signature, which protocol-kit already supports.

## Obtained result

GS021 in simulation, and Execute can't estimate a fee.

[`createExistingTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/web/src/services/tx/tx-sender/create.ts#L131-L141) adds every stored confirmation like this:

```ts
safeTx.addSignature({ signer, data, staticPart: () => data, dynamicPart: () => '', isContractSignature: false })
```

A contract owner's confirmation is stored as `{owner}{offset = 65}{00}{length}{data}`. Added as a plain signature, `buildSignatureBytes` concatenates it whole and keeps the offset at 65. With two signatures the static part is 130 bytes, and `checkNSignatures` requires `s >= requiredSignatures * 65`, so the Safe reverts with GS021.

Mobile has the same code in [`addSignaturesToTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/mobile/src/services/tx/tx-sender/create.ts#L40-L50).

A fix could rebuild stored confirmations as `EthSafeSignature`, and for `v = 0` add just the data after the length word with `isContractSignature: true`. `buildSignatureBytes` then lays the signatures out correctly. I have a small patch with a unit test built from the example above, and can open a PR.

## Screenshots

<!-- attach: the Execute screen with "Simulation failed", "Cannot estimate" and "Error code GS021" -->
