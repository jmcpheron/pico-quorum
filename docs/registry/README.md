# The key registry

`keys.json` lists PicoQuorum keys whose attestation bundles anyone can check. The
[Execute page](../app/) reads it: when one of a Safe's owners is listed here and its bundle passes
every check, the owner gets a **Verified PicoQuorum key** badge.

A listing is a claim. The bundle is the evidence, and the page checks it in your browser every time,
with the same checks as `tools/quorum verify` (`tools/mock-tx-service/attest.mjs`):

1. the factory certificate in E0E0 is signed by Infineon's Trust M CA (pinned by its public key)
2. the binding in F1D1: Infineon's factory key signed this chip's UID, E0F1 and the key
3. the record in F1D0 names this chip and that key, and the owner address follows from the key through
   Safe's passkey signer factory (`firmware/quorum_cfg.py` "signer")
4. the live challenge, when the bundle has one: the chip still held its Infineon key when it was read
5. the lifecycle the chip reported: key, record and binding sealed

What a badge can't tell you is who holds the key, or who pressed Sign. That part is the Safe's
threshold. `docs/mainnet/THREAT-MODEL.md` has the rest.

## Add your key

1. Run the ceremony and seal the chip (`docs/PROVISIONING.md`, `docs/TRUSTM.md`).
2. Read the bundle off the board: `tools/fw attest`. It holds public values only.
3. Check it yourself: `tools/quorum verify attest-<serial>.json --chain base`.
4. Open a pull request that adds the bundle under `docs/mainnet/attest/` and an entry in `keys.json`:

```json
{
  "name": "a short name for the key",
  "holder": "your GitHub handle",
  "owner": "0x… (the owner address the bundle's key gives)",
  "serial": "the chip serial from the bundle",
  "bundle": "../mainnet/attest/attest-<serial>.json",
  "added": "YYYY-MM-DD"
}
```

You can also check a bundle on the page without listing it: open **Keys** and choose **Check a bundle**.
Nothing leaves your browser.
