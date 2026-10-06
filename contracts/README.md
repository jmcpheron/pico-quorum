# contracts

The Safe owner contract that lets a secure-element P-256 key sign for a Safe, with tests and
deploy scripts.

PicoQuorum contracts will go here.

For now there is nothing to deploy of our own. Each chip key owns a Safe through Safe's audited
passkey signer (safe-modules passkey v0.2.1, `SafeWebAuthnSignerFactory.createSigner`). The
addresses and the proxy code are pinned in `firmware/quorum_cfg.py` `"signer"`, and the packaging
is in `firmware/webauthn.py`.

## Open

- [x] Signature shape: Safe's audited WebAuthn/passkey signer, one proxy per key
- [x] Chains: Base and Ethereum. The signer's verifiers are the P-256 precompile at 0x100, with Daimo as fallback
- [ ] Deterministic deployment addresses, checked against provisioning records
- [ ] Whether the owner contract should require on-chain proof of a genuine chip (picowallet's
      `TrustMAttest` checks a Trust M's Infineon certificate; `web/src/attest.mjs` does it off chain)
