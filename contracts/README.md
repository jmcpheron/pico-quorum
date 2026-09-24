# contracts

The Safe owner contract that lets a secure-element P-256 key sign for a Safe, with tests and
deploy scripts.

For now the only Foundry project is the inherited picowallet one in
[`../app/packages/foundry`](../app/packages/foundry) (`ChipAccount`, a single-owner vault that is
not a Safe). PicoQuorum contracts will go here.

## Open

- [ ] Signature shape: Safe's audited WebAuthn/passkey signer (first choice) vs a custom ERC-1271
      signer
- [ ] Chain: Base, with the RIP-7212 P-256 precompile
- [ ] Deterministic deployment addresses, checked against provisioning records
- [ ] Whether to bring over upstream's `TrustMAttest` for on-chain proof of a genuine chip
