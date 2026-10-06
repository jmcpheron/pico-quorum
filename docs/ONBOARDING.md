# Onboarding: a passkey's first Safe

A first visit to [the console page](console/) ends with a real Safe that the visitor's passkey
controls: a 1-of-1 on Base Sepolia, a test network. From there it grows into a 2-of-3 with their
everyday wallet and their hardware wallet. This page says how, what was checked, and what it
assumes.

## What a passkey is here

A passkey is a P-256 key made inside a device (Touch ID, Windows Hello, a phone, a security key).
It has no Ethereum address of its own. It owns a Safe through Safe's passkey signer, a small
contract whose address follows from the key: the same address on every chain
(`firmware/webauthn.py`). It can approve Safe transactions. It can't hold ETH, pay gas or send a
transaction. **The Safe holds the funds, and a wallet pays the gas.**

## The flow

1. **Make a passkey** on the console page. Unchanged.
2. **Your practice Safe.** The console page links to the app's `#/start/<x>/<y>` (`web/src/main.mjs`).
   - The app works out the Safe's address from the key alone (`practiceSafe`, `web/src/safe.mjs`):
     Safe 1.5.0 L2, the version of the project's test Safes, with the passkey's signer as its only
     owner, threshold 1. The address is real at once, and Base Sepolia ETH sent to it waits there.
   - **Deploy it**: one transaction from any wallet makes both the Safe and the passkey's signer.
     The Safe's `setup` calls the passkey factory through the console's pinned MultiSendCallOnly
     1.4.1. The wallet doesn't become an owner. A wallet on another device can send it from the
     shared link.
   - Once it is deployed, the app saves it to the Safes the console watches.
3. **Is your passkey backed up?** See the next section.
4. **Make it 2 of 3.** The app builds one batch: add the hot wallet at threshold 1, then the
   hardware wallet at threshold 2 (`growCall`, `web/src/propose.mjs`).
   - The app hands the batch to the console (`pq.propose` in this browser, which reaches the
     firmware as `secrets.QUORUM_PROPOSE`).
   - The console decodes it and shows each new owner on a red page. The person sees every page and
     holds Sign. The passkey signs the hash the console worked out itself.
   - **The console proposes it.** In a 1-of-1, no other owner can. Safe's service takes a proposal
     only from an owner, and lists an unsigned one as "untrusted", which the queue leaves out. So the
     console sends its signature as the proposal (`txservice.propose`).
   - The hot wallet then executes it from the Safe's page in the app and pays the gas.

## The exception to "two or more": a backed-up passkey

The app's advice is to keep a Safe's threshold at 2 or more. The practice Safe starts at 1 of 1,
and that's acceptable only when the passkey has a backup. A passkey can't be rebuilt from a seed
phrase: its private key is made inside the device and never leaves it. So a backup means one of two
things:

- **It is synced.** iCloud Keychain, Google Password Manager or 1Password copies it to the
  account's other devices. The device reports this itself (the BS flag, `cred.synced`). With `none`
  attestation the page can't verify it, so it says "your device says".
- **A second key can act.** A second owner, such as a passkey on another device or another
  provider.

**Test your backup**: on another device or browser, open the console page and choose "I already
have one". If it shows the same owner, the backup works. This uses the existing recovery
(`usePasskey`, `emu/web/browser.mjs`), and proves the key can be reached somewhere else.

**The domain is part of the key.** A passkey signs only on the site that made it (today
`jmcpheron.github.io`). If the console moves to `picoquorum.app` ([STATUS.md](STATUS.md)), every
passkey made on the old domain can't sign there, synced or not. Make that move before anyone treats
a passkey's Safe as a real wallet. WebAuthn's Related Origin Requests (`/.well-known/webauthn`) might
let old passkeys sign on the new domain. That hasn't been checked.

## What was checked

On Base Sepolia, 2026-10-06, with reads only:

- **The address**: `practiceSafe()` gives the same address as the 1.5.0 factory's own
  `createProxyWithNonce`, called with `eth_call`. Checked for TM1's key (`web/test.mjs` keeps it as a
  vector) and for a fresh key whose signer doesn't exist.
- **The deploy**: neither call reverted, so creating a signer that already exists is fine. Calling
  `createSigner` for TM1's deployed signer returns it.
- **Proposals**: Safe's service source (`safe_transaction_service/history/serializers.py`) takes a
  proposal whose `sender` is an owner contract, with a v=0 signature, checked by EIP-1271. That is
  the same check the chips' confirmations pass today.
- **Hiding unsigned proposals**: the queue the console reads (`/api/v2/…/multisig-transactions/`)
  lists only trusted ones by default (`views_v2.py`).

In tests: `test-vectors/console_test.py` `case_propose` covers proposing (the hash worked out on the
console, none taken from the page; red pages; resent after a restart). `web/test.mjs` covers the
address and the batch, which the console's own decoder reads as two owners added.

**Not yet run end to end on Base Sepolia**: a real passkey proposal accepted by Safe's hosted
service, and the execution after it.

## Relayer notes (not built)

A relayer would let someone with no wallet finish onboarding. On Base Sepolia only, it would:
- deploy practice Safes (`practiceSafe().deploy`);
- send fully signed `execTransaction`s.

**It doesn't weaken the console.** A relayer only submits. The Safe checks the passkey's signature
over the hash the console signed, so a relayer can't change what happens, only decide whether to
send it.

**What it costs:**
- a funded hot key, kept topped up;
- rate and abuse limits (one deploy per key, a few transactions a day);
- its host in the app's Content-Security-Policy;
- a service to run, which the project has none of today.

**Alternatives:**
- Safe4337Module with a bundler and a paymaster. The passkey would then sign a SafeOp hash, a new
  kind of hash for the console to rebuild and show (AGENTS.md rule 1), so it is a larger change.
- EIP-8141 frame transactions in Hegotá ([HEGOTA-WATCH.md](HEGOTA-WATCH.md)). A sponsor pays, and
  the console could send the transaction itself.

## Glamsterdam

Glamsterdam went live on Ethereum Sepolia, not Base Sepolia. What it could mean here is in
[GLAMSTERDAM-WATCH.md](GLAMSTERDAM-WATCH.md).
