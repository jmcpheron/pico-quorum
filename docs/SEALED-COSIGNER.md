# Sealed Cosigner: a shared profile for hardware owners of a multisig

> **A draft proposal (2026-10-30).** Nothing here is built as written, and it hasn't been shown to the
> wedgie and Instant Wallet side yet. It was written from PicoQuorum's side after reading Instant Wallet
> (`clawdbotatg/instant-wallet` d1e881e), its device app Safe Signer (`clawdbotatg/wedgie-safe` ef6af46,
> safe-46) and the wedgie firmware (`clawdbotatg/wedgie-dev` 4df5753). What it says about those projects
> is our reading of their code and docs, not theirs: they should correct it. If both sides agree, the
> spec moves out of this repository ([where it lives](#where-it-lives)).

## In one paragraph

PicoQuorum and the wedgie grew from the same project (picowallet) and arrived at the same device
without agreeing on it. That device is a small box with a key made inside a secure element. The
key is one owner of a Safe through Safe's passkey signer. The box rebuilds the hash it signs from
the transaction's fields, shows what the transaction does on its own screen, and signs only after
a person acts. This proposal names that device a **sealed cosigner**. It writes down what both
projects already do, fixes the few places where they differ, and adds levels a device can claim.
Shared test vectors would check every claim. The aim is that any app can use any sealed cosigner,
and a person can tell how much each one is worth.

## Ingredient, not recipe

A wallet is a recipe. Instant Wallet is one: a passkey, a wedgie, a recovery address and a daily
limit, on a Safe. A pico quorum is another: three to five people, each with a console and a key, on
one Safe. A company treasury run to [SEAL's multisig guidance](https://frameworks.securityalliance.org/)
is a third. There will be more.

A sealed cosigner is one **ingredient** those recipes can use, and this spec is the label on it.
The layers, from the ground up:

| layer | what it is | examples | who sets it |
|---|---|---|---|
| suppliers | chips and boards | Microchip ATECC608, Infineon OPTIGA Trust M, Raspberry Pi RP2350, JLCPCB | the vendors' datasheets |
| the kitchen | the account and the chain's rules | Safe, its passkey signer and Transaction Service; EIP-712, EIP-1271, the P-256 precompile | Safe, Ethereum's EIPs and ERCs |
| **the ingredient** | **a sealed cosigner** | **a PicoQuorum console, a wedgie running Safe Signer** | **this spec** |
| recipes | how a wallet combines owners, limits, delays and recovery | Instant Wallet's levels, a pico quorum, a DAO treasury | each wallet |
| the table | the app a person uses | the PicoQuorum app, instantwallet.io, Safe{Wallet} | each app |

The spec stays in its own layer. It says nothing about thresholds, delays, limits or recovery. Those
belong to the recipe. It also doesn't choose a chip or a board. It says what any chip and board
must do to be called a sealed cosigner, and how to check that.

## The name

**Sealed Cosigner**, short **SC**. The wire version is `sc/1`, and the levels are SC1 to SC4.
- *Sealed*: the key is made in the chip and can't leave or be replaced. It is also the word both
  projects already use.
- *Cosigner*: it is never the whole wallet, only one owner among several.

Names left out:
- **Cosign** is Sigstore's signing tool.
- **SEAL** is the Security Alliance, which we may want to work with.
- **Quorum** is PicoQuorum's brand and an older enterprise blockchain.
- **Hardware wallet** suggests a device that holds the whole wallet, which this is not.

## Why now: what both projects already share

| | PicoQuorum | wedgie + Safe Signer |
|---|---|---|
| the key | P-256, made in an ATECC608 or Trust M, sealed | the same chips, sealed (`safe_key.py`) |
| how it owns a Safe | Safe's passkey signer v0.2.1, one `SafeWebAuthnSignerProxy` per key | the same |
| the envelope | a WebAuthn assertion built on the device (`firmware/webauthn.py`) | the same shape (`safe.py`) |
| what it is given | the transaction's fields; it rebuilds the safeTxHash | the same: `safe_sign` carries fields, never a hash |
| a check for people | the hash's last 8 hex digits and its blockie | a blockie of the hash on the first page |
| refusals | delegatecall outside pinned contracts; a gas refund is a red page, not a refusal | delegatecall outside MultiSend, and gas refunds |
| Safe{Wallet} bug | GS021 on contract signatures, reported as #8808 (`docs/upstream/`) | cited as the reason to execute elsewhere |

Where they differ, and what this spec would settle:
1. **One key, two owner addresses.** The owner address depends on the signer's `verifiers` value.
   PicoQuorum and Instant Wallet use the P-256 precompile with Daimo's verifier as fallback. Safe
   Signer's `safe_addr.py` uses the precompile alone. So the address a wedgie shows is not the one
   Instant Wallet adds.
2. **Push or pull.** The wedgie signs what the host sends it, for any Safe, and shows which.
   PicoQuorum pulls its queue from Safe's service, and signs only for Safes and chains it has
   pinned. Both are safe, because the device rebuilds the hash, but they can't talk to each other.
3. **The link.** The wedgie's signing messages share a USB line with MicroPython's REPL, which it
   closes in software. PicoQuorum's dev consoles leave the USB REPL open
   ([SECURITY.md](SECURITY.md)). console-rp closes it in hardware: the USB-C reaches only a serial
   bridge ([hardware/console-rp](../hardware/console-rp/README.md)).
4. **What can't be read.** The wedgie shows a call it can't read in red and still lets A sign it.
   PicoQuorum refuses anything it doesn't recognise.
5. **Clear signing.** The wedgie checks ERC-7730 descriptors against roots it carries. PicoQuorum
   decodes calls against contracts pinned in its config.
6. **Proof.** The wedgie proves its chip with the Trust M's Infineon certificate, and its firmware
   with signed install lists. PicoQuorum proves releases with fingerprints and signed tags, and
   has designed an attestation chain for its keys ([ATTESTED-KEYS.md](ATTESTED-KEYS.md)).

## What a sealed cosigner is

A device is a sealed cosigner when all of these hold:
1. **A sealed key.** A P-256 key generated inside a secure element. It can't be read out, replaced
   or regenerated once sealed.
2. **One owner.** The key owns an account as one owner among several, through a binding this spec
   names ([part 2](#2-the-owner-binding)).
3. **Its own hash.** It is given fields, never a hash. It rebuilds what it signs from the fields it
   shows.
4. **Its own screen.** It shows the chain, the account and every call, in words it decoded itself.
   It never shows text the host wrote as fact.
5. **A person acts.** It signs only after a deliberate action on the device. Refusing is always one
   easy action.
6. **A closed link.** Nothing that reaches the device over its link to the host can run code, reach
   a debugger or bootloader, or ask the key to sign a digest.

## Borders

**In scope:**
- the key and how it is sealed;
- how the key becomes an account owner, and the exact owner address;
- what the device signs, how it rebuilds it, and the floor of what it must show and refuse;
- the messages between a host and the device, and how they travel;
- how a device proves its key is in a sealed chip, and that its firmware is the published one;
- the levels, and the test vectors that check each one.

**Out of scope:**
- **Account policy:** thresholds, delays, daily limits, roles, recovery, travel locks. These are
  recipe choices (Instant Wallet's `PLAN.md`, PicoQuorum's `GOVERNANCE.md`).
- **Being a whole wallet:** a seed phrase, a backup, a key that can be exported.
- **Sending and gas:** relays, bundlers, paymasters.
- **Being a FIDO authenticator.** The envelope looks like WebAuthn because Safe's signer checks
  WebAuthn, but the device doesn't speak CTAP. A browser's passkey prompt can't show the
  transaction, so that path would be blind signing.
- **secp256k1 keys** in `sc/1`. The chips both projects use sign P-256.
- **Board designs, cases and brands.**

One rule crosses the border, and it is written for recipes: **no single device should hold a
threshold's worth of owners.** Instant Wallet adds one wedgie as two owners, with a threshold of 3. PicoQuorum's
governance says no technology and no person holds a threshold's worth. Both pass. A recipe that
adds a sealed cosigner should say how many owners it fills.

## The spec, in seven parts

This is an outline. Each part would get exact text and test vectors in the neutral repository.

### 1. The key

- P-256 (secp256r1), generated by the secure element, never outside it.
- Sealed: the slot or object is locked so the key can't be regenerated, replaced or exported.
- The device names its **chip class** in `hello`: `atecc608a`, `atecc608b`, `atecc608c`,
  `optiga-trust-m-v1`, `optiga-trust-m-v3`, and so on.
- Signatures are low-s on the wire. The binding below accepts either s, so this keeps outputs
  comparable across devices.

### 2. The owner binding

`sc/1` has one binding, the one both projects use today: **Safe's passkey signer, safe-modules
passkey v0.2.1.**

| | value |
|---|---|
| factory | `0x1d31F259eE307358a26dFb23EB365939E8641195` |
| singleton | `0x4e27b51350e6c2083ee19011120f50dafec5ca50`, as in `firmware/quorum_cfg.py` |
| verifiers | `(0x100 << 160) \| 0xc2b78104907F722DABAc4C69f826a522B2754De4`: the P-256 precompile, then Daimo's verifier |
| owner address | CREATE2 by the factory, salt 0, over the proxy's creation code and `(singleton, x, y, verifiers)` |

**The verifiers value is part of the address**, so the spec fixes it. A second owner for the same
key (Instant Wallet's "counts twice") uses a second named value. `sc/1` would list it:
- `0xc2b78104907F722DABAc4C69f826a522B2754De4` alone, which is Instant Wallet's
  `VERIFIERS_SLOT2`.

**The envelope**, as `firmware/webauthn.py` builds it:
- `authenticatorData = sha256(rpId) ‖ 0x05 ‖ 00000000`. The flags say user present and user
  verified; the counter is 0.
- `clientDataJSON = {"type":"webauthn.get","challenge":"<base64url(hash)>",<fields>}`.
- The chip signs `sha256(authenticatorData ‖ sha256(clientDataJSON))`.
- The Safe signature is a contract signature (v = 0) carrying
  `abi.encode(bytes authenticatorData, string clientDataFields, uint256 r, uint256 s)`.

The contract ignores `rpId` and `origin`. Each device class keeps its own (`picoquorum`,
`https://wedgie.dev`), listed in the spec's registry so a signature on chain says which kind of
device made it. That label is **informational only**: anyone can write any origin, so nothing may
trust it.

**Later bindings.** Safe's core contracts have native P-256 owners on `main` (signature v = 2, no
proxy, no envelope; reported in Instant Wallet's `WEDGIE-SAFE.md`, not in a release). It would be
`sc/2`'s first new binding. A device keeps every binding in one module, as PicoQuorum keeps all of
it in `webauthn.py`, so a new one changes one file. Other P-256 accounts (ERC-4337 accounts with
passkey owners) are candidates, none checked.

### 3. What it signs

- **Safe transactions.** All ten `SafeTx` fields, plus the chain id and the Safe's address. The
  device computes the EIP-712 safeTxHash itself, for the Safe's version. A host's hash, if one is
  sent, is only compared with it, never signed.
- **Text messages (MAY).** A `personal_sign` text as a SafeMessage for the Safe (EIP-1271), shown
  in full, with its hash worked out on the device. The wedgie does this today.
- **Typed data:** not in `sc/1`. Neither device can show it faithfully yet.
- **Nothing else.** No command signs a digest the host supplies.

### 4. What it must show and refuse

This is a floor. A device may refuse more.

**Every transaction shows:** the chain, the account (its address and blockie), and every call. A
batch through MultiSend is decoded call by call.

**Red pages:**
- changes to owners, threshold, modules, guards or the fallback handler;
- an unlimited approval;
- any call the device can't decode exactly.

A red page stays red. Whether A can still sign a call the device couldn't read is the device's
policy, declared in `hello` (`"unreadable": "refuse"` or `"red"`).

**Refused, whatever is held:**
- an operation other than call or delegatecall;
- a delegatecall to anything but a MultiSend or MultiSendCallOnly the device knows for that
  chain, or to a contract the device has pinned;
- a delegatecall inside a batch;
- a gas refund: `gasPrice ≠ 0`, which pays whoever executes out of the Safe, beside the calls.
  The wedgie refuses this today. PicoQuorum shows it as a red page and would have to change.

**The verify code:** the last 8 hex digits of the safeTxHash and its blockie. The blockie is
ethereum-blockies, seeded with the lowercase `0x`-prefixed hash, as both projects already draw
it. The vectors pin the exact seed and pixels, so a phone, a computer and a device draw the same
picture. Instant Wallet's three match words (its v2 protocol) are dropped in favour of this.

**The action:** every page is shown before signing is possible, and then a deliberate press or
hold. PicoQuorum holds for 2 seconds, and 3 for a red page. The wedgie takes a press of A after
the last page. The spec requires "deliberate"; the device declares which it uses.

### 5. The messages (`sc/1`)

One JSON object per line, UTF-8, each with an `id`. The starting point is Safe Signer's protocol,
which already works with Instant Wallet. `sc/1` keeps its message names so the wedgie changes
little:

| from host | reply | what |
|---|---|---|
| `hello` | `hello` | who the device is, and what it can do (below) |
| `safe_data` | `safe_data` | a piece of a large calldata, before `safe_sign` (`"data": "@"`) |
| `safe_clear` | `safe_clear` | an ERC-7730 descriptor bundle the device checks against its own roots (MAY) |
| `safe_sign` | `safe_sig` or `refused` | the transaction's fields. Returns the safeTxHash it computed and the envelope's parts |
| `safe_message` | `safe_sig` or `refused` | a text message (MAY) |

`hello` adds an `sc` object to what Safe Signer sends today:

```jsonc
"sc": {
  "v": 1,
  "level": "SC2",
  "chip": "atecc608c",
  "owners": [{ "binding": "safe-passkey-0.2.1", "verifiers": "0x0100c2b7…54de4", "address": "0x…" }],
  "pins": [{ "chainId": 8453, "safe": "0x…" }],   // empty: any Safe, shown on every page
  "unreadable": "refuse",
  "action": "hold-2s",
  "firmware": { "fingerprint": "9842bbed…", "source": "https://github.com/…" },
  "maxLine": 6000, "chunk": 4000
}
```

**Pinned or open.** A device with pins refuses a `safe_sign` for any other chain and Safe. That
way PicoQuorum can accept pushed transactions without signing for an account it wasn't set up
for. A device without pins shows the account on every page, as the wedgie does.

**Pull mode (an extension).** A device with no network of its own can ask the host to fetch for
it, as console-usb and console-rp plan to: `{"t": "req", "url": …}`, only to services the device
pins. It runs on the same link as the messages above. The host still can't name a digest.

**Transports.** The messages are the same on each:
- **USB serial:** CDC-ACM. On a device whose USB reaches the processor, the REPL must be closed. On
  one with a bridge (console-rp's CH343P), the bridge's DTR and RTS reach nothing. Hosts use Web
  Serial (Chromium) or a native tool.
- **A file drive:** the wedgie's iPhone path, a line written to a USB drive.
- **QR, later:** for devices with a camera, or a phone as the camera. ERC-4527 is the existing
  pattern for air-gapped wallets, and the spec would bind to it rather than invent one.

### 6. Proving the key

An **attestation statement** binds three things: a chip of a named class, the key inside it, and
the owner address. Anyone can check it, onchain with the P-256 precompile, or offline.
- **Trust M:** the chip's factory key, under Infineon's certificate, signs the binding. Safe
  Signer's "prove it's you" (`safe_msg.py`) already does this.
- **ATECC608:** it has no factory certificate, so a bench makes and seals an attestation key, and
  a brand key vouches for the bench ([ATTESTED-KEYS.md](ATTESTED-KEYS.md)).

`sc/1` would fix the statement's bytes and how to verify it, not who may be a bench. A wallet
decides which roots it trusts, as a browser decides which certificate authorities it trusts.

### 7. Proving the firmware

- `hello` reports a **release fingerprint**: one SHA-256 over the image, defined so anyone can
  recompute it from the published source.
- Releases are signed, and the source is public.
- **Verified boot**, for SC4: the processor runs only images signed by the release key. On an
  RP2350, that is the key's hash in OTP and secure boot switched on.
- **The key works only under verified firmware.** The secure element refuses to sign unless signed
  firmware unlocks it, with a secret only signed firmware can read. The wedgie plans this for the
  Trust M (`PLAN-TRUST.md` phase 4). For the ATECC608 it is still to design: a new, permanent
  chip profile, checked against the datasheet first.

## Levels

Each level includes the ones below it, and each is checked by test vectors and a written claim.

| level | name | what it adds |
|---|---|---|
| **SC1** | Own hash | the seven-point definition above; the owner binding; the show-and-refuse floor; the hash, envelope, address and blockie vectors |
| **SC2** | Speaks sc/1 | the messages, so any `sc/1` app can drive it; `hello` tells the truth about the device |
| **SC3** | Attested key | an attestation statement a third party can check |
| **SC4** | Verified firmware | verified boot, a reproducible release, and a key that works only under signed firmware |

Where the devices stand, by our reading:
- **PicoQuorum console (Wi-Fi):** SC1 in substance, and the owner binding already matches. No
  `sc/1` messages. SC3 is designed and half built on the emulator. Not SC4: no secure boot, and
  the USB REPL is open to someone holding the board.
- **PicoQuorum console-rp:** routed for SC1's closed link in hardware, and the RP2350 can do SC4.
  Its firmware isn't written.
- **wedgie with Safe Signer:** SC1 in substance, except the verifiers value. Its link is closed in
  software. Its protocol is the base of `sc/1`. Its Trust M "prove it's you" is most of SC3. Not
  SC4: an RP2040 has no secure boot, and the wedgie's own docs say so.

## Test vectors are the standard

The prose says what to do; the vectors say whether it was done. A neutral repository would hold:
- **Safe hashes:** fields to safeTxHash, across Safe versions and chains, including real mainnet
  transactions. PicoQuorum's `test-vectors/` already has these.
- **Envelopes:** a hash and `rpId` to `authenticatorData`, `clientDataJSON` and the digest the chip
  signs. Then a fixed test key's signature to the exact Safe signature bytes.
- **Owner addresses:** a key and a verifiers value to an address, checked against the deployed
  factory on each chain.
- **Pages:** a transaction to the red pages and refusals it must produce (the floor in part 4).
  Every refusal gets a vector: each unpinned delegatecall, a gas refund, a delegatecall inside a
  batch.
- **Blockies:** a hash to its 8 × 8 cells and colours.
- **Messages:** a conversation and the replies, including hostile hosts: overlong lines, a
  `safe_sign` for an unpinned Safe, a hash that doesn't match.

They would be plain JSON, with a runner in Python (CPython and MicroPython) and one in JavaScript.
Test keys only, never a real one.

## Where it lives

1. **Now: here, as this draft.** It is PicoQuorum's proposal until the other side has read it.
2. **Then: a neutral repository,** in a small GitHub organisation named for the spec (for example
   `sealed-cosigner`), not under either project. It would hold the spec, the vectors, the runners
   and the origin registry. Each project pins a version of it.
   - **CC0 for everything.** Anyone can embed the vectors, and the text can go into an ERC
     unchanged (ERCs are CC0).
   - **Editors:** one from each implementation. A change to a level needs a second implementation
     to pass it.
   - **No trademark,** and no product names in the levels.
3. **Later, maybe, ERCs.** Once two devices interoperate, propose the parts every Ethereum app
   could use: the hardware-key binding to Safe's passkey signer (the envelope and the fixed
   verifiers), and possibly the `sc/1` messages. Discussed first on Ethereum Magicians. Only after
   real devices work, not before.

PicoQuorum's own work stays here: console-rp's secure boot recipe, its chip profiles, its release
process. These are how one device reaches SC4, not the standard itself.

## How it meets the systems around it

| system | how it meets this spec | status |
|---|---|---|
| Safe (contracts) | passkey signer v0.2.1 is `sc/1`'s binding; native P-256 owners could be `sc/2`'s | in use; native owners not released |
| Safe Transaction Service | stores a sealed cosigner's confirmations as contract signatures; both projects post there | in use |
| Safe{Wallet} | GS021 when executing with contract signatures; PicoQuorum sent issue #8808 and PR #8809 | upstream |
| EIP-712, EIP-1271 | the hash and how the Safe checks the owner | in use |
| RIP-7212, EIP-7951 | the P-256 precompile at 0x100 on L2s and on Ethereum; first in the verifiers value | in use |
| ERC-7730 | clear-signing descriptors; the wedgie already checks them against its roots | MAY in `sc/1` |
| ERC-4527 | the QR pattern for air-gapped wallets; a future transport | not started |
| WebAuthn (W3C) | the envelope's shape, because the signer checks WebAuthn; not an authenticator | in use, by design |
| Web Serial (WICG) | how a browser app reaches a USB cosigner (Chromium only) | in use by the wedgie |
| Microchip, Infineon | chip classes; Infineon's certificate is a ready SC3 root | in use |
| Raspberry Pi RP2350 | secure boot and OTP for SC4 | to rehearse on a Pico 2 |

People and groups to show it to once both projects agree. None has been asked.
- **Safe**, for the binding and native P-256 owners.
- **The Ethereum Foundation's** clear-signing and wallet security work, for ERC-7730 and the
  levels.
- **SEAL**, whose multisig frameworks could point signers at a level.
- **Walletbeat**, which rates wallets and could rate cosigners by level.
- **OSHWA**, if console-rp is certified as open hardware.

## Open questions, for both projects

1. **The verifiers value.** This draft picks precompile + Daimo, which PicoQuorum and Instant
   Wallet already use. Safe Signer's own screen would change its address.
2. **Push into PicoQuorum.** Accepting `safe_sign` for pinned Safes is a new way to sign in
   AGENTS.md's terms, so it needs a yes before it is built. It doesn't change rule 1: the console
   still signs only the hash it worked out.
3. **The refusal floor.** The wedgie lets A sign a red unreadable call. Is "declared in `hello`"
   enough, or should SC1 require a refusal? And PicoQuorum would have to start refusing gas
   refunds.
4. **Counting twice.** One press can fill two owners. Should the device be told, and show
   "counts as 2 owners"?
5. **The `origin` registry.** Worth having, or noise?
6. **Text messages.** In `sc/1`, or later?
7. **Levels and the REPL.** Is a link closed in software (the wedgie) the same SC1 as one closed in
   wiring (console-rp)? This draft says yes, if no vector can get through.
8. **The neutral organisation's name,** and who the editors are.

## What was checked, and how

- Read on 2026-10-29 and 30:
  - Instant Wallet's README, `CONCEPT.md`, `docs/PROTOCOL.md`, `PLAN.md`, `WEDGIE-SAFE.md`,
    `MULTI-SIGNER.md`, `KEY-ROLLING.md`, `SAFE-APP.md`, and `web/lib/safe/wedgie.ts` and
    `config.ts`;
  - Safe Signer's README, and its `safe.py`, `safe_addr.py`, `safe_blockie.py` and `safe_7730.py`
    headers;
  - the wedgie's README, `SECURITY-ROADMAP.md`, `PLAN-TRUST.md` and `PLAN-PIN.md`, and how its
    `main.py`, `boot.py` and `wedgie.py` close Ctrl-C.
- The verifiers values were compared as written in `firmware/quorum_cfg.py`, Instant Wallet's
  `config.ts` and Safe Signer's `safe_addr.py`. They were not computed against a chain.
- Nothing in either project was run for this draft. No vectors exist yet beyond PicoQuorum's own.
