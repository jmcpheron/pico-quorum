> **Living brainstorm (started 2026-10-03).** Options, not decisions. Move anything settled into the [kickoff](KICKOFF.md) with a one-line reason.

# PicoQuorum: our own Safe web interface, a PicoQuorum PKI on the Trust M, and signed firmware

A brainstorm, not a build plan yet. It lays out what is feasible, what each option costs, and a
recommended order. Nothing here is decided.

## Context

- Safe{Wallet} can't execute a queued transaction once a Pico's confirmation (an EIP-1271 contract
  signature) is one of the ones the Safe checks and the threshold is 2 or more: GS021. The web app
  rebuilds every stored confirmation as a plain signature, so the contract signature's offset stays
  at 65 (`docs/upstream/safe-wallet-gs021/`). Issue #8808 and PR #8809 went up on 2026-09-25; CI was
  never approved and there has been no review. The same bug was reported in 2024 as #3673 and closed
  "not planned". Safe Pro launches on 6 October 2026, so the team is busy with something else.
- Today the workaround is `tools/quorum live exec`, which lays the signatures out correctly
  (`tools/mock-tx-service/sigs.mjs` `packSignatures`) and hands the transaction to the browser
  wallet through `wallet.html`. That is already most of an "Execute" web page.
- The Trust M path is far along: quorum-tm1 profile, T1–T10 ceremony, attest bundles, `tools/quorum
  verify` for co-signers (`docs/TRUSTM.md`, `docs/mainnet/`). TM1 approved on Base Sepolia.
- Open "later" items already in the docs: RP2350 secure boot, closing the USB REPL, a PIN (needs a
  newer Trust M generation), a use record on the Trust M (`docs/mainnet/CONFIGURATION.md`).

Two facts checked today that shape the options:
- **TM1 and TM2 are first-generation Trust M (V1).** Infineon's overview says V1 certificates come
  from ECC Root CA1 / Int. CA 101; V3 and Express come from Root CA2 / Int. CA 306. Our chips say
  CA 101. V3 adds the shielded I2C connection, protected update of keys and metadata (not just data),
  HKDF, and more curves. The "Auto" (authorization reference) access condition and the PBS/Auth-Ref
  secrets are what Express and MTR ship with, on V3 silicon.
- **RP2350 secure boot has published bypasses.** Five fault-injection attacks (voltage, EM, laser)
  broke it in the RP2350 Hacking Challenge (WOOT '25). Secure boot still stops "plug in a USB cable
  and run your own code", which is our actual gap. It is not a boundary against a lab.

## The short version

1. **Fixing GS021 ourselves is a two-day static page, not a project.** `live exec` already does it.
   Make it a page on a PicoQuorum domain, used beside Safe{Wallet} for the one step that fails.
2. **A bespoke PicoQuorum web app is worth it, but for the device features, not as a Safe{Wallet}
   replacement.** Propose, show what the console will show (same `decode.py` and `safe_tx.py`, run
   in the browser with the emulator's WebAssembly MicroPython), show which owner is a sealed chip,
   execute correctly, propose rejections. Keep Safe's transaction service as the queue.
3. **Don't self-host a patched Safe{Wallet}.** It needs its own Client Gateway and Redis, a Safe API
   key server-side, and a monorepo to keep in sync. The one bug it fixes is covered by item 1.
4. **A domain certificate helps the browser trust our site and lets the console pin our server. It
   has nothing to do with the chip's certificate slots.** Those are for the device's identity.
5. **A PicoQuorum CA on the Trust M is the real "ecosystem" piece:** our own device certificate in
   E0E1, chained under the Infineon factory certificate, written during the ceremony. Co-signers,
   the web app and any relay can then recognise a genuine PicoQuorum key with one check.
6. **Move real keys to Trust M V3.** It is the only way to a pairing secret (shielded connection),
   a PIN-like unlock (Auto), and signed in-field updates (protected update). V1 can do none of these.
7. **Signed firmware is MicroPython frozen into a custom build, sealed with `picotool`, with the
   REPL closed.** It is the step that turns "whoever holds the board can sign" into "whoever holds
   the board and a fault-injection rig". Pair it with the Trust M's shielded connection so a stolen
   key chip is useless on any other board.

---

## Part 1: a web interface for signing and executing

### Tier 0: an Execute page (fixes GS021 today)

What: a static page at `https://<picoquorum-domain>/execute` that takes a chain and a Safe, lists
queued transactions from `api.safe.global`, checks every confirmation (ECDSA recover, contract
signatures via `isValidSignature` over a public RPC), packs them with `packSignatures`, and hands
`execTransaction` to the browser wallet (EIP-1193). Everything else stays in Safe{Wallet}.

Reuse, all in `tools/mock-tx-service/`: `live.mjs` (`status`, `exec`), `sigs.mjs` (`parse`,
`packSignatures`, `p256Owner`), `wallet.html` (the EIP-1193 form), `chain.mjs` (the
`isValidSignature` check). It becomes one bundled page (esbuild, viem and noble pinned).

Decisions it forces:
- **API key.** Safe's service rate-limits without a key (2 req/s, 5,000/month). A static page can't
  hide a key. Options: the user pastes their own key into the page (kept in localStorage), or a
  tiny proxy (a Cloudflare Worker) holds the key and allow-lists our origin. Start with paste-your-
  own; it's what the Pico already does with `QUORUM_API_KEY`.
- **RPC.** Public RPCs for Base and Ethereum are fine for `eth_call`. Make it configurable.
- **Hosting.** GitHub Pages or Cloudflare Pages on the domain; the certificate is automatic (Let's
  Encrypt). No server, so there is no server to compromise. CSP, SRI on the one bundle, no
  third-party scripts, no analytics. Optionally pin the build to IPFS too.

Effort: about 2 days. Risk: low; the signature packing is already proven on Base Sepolia and Base.

### Tier 1: self-host Safe{Wallet} with our patch (not recommended)

The web app talks to the Safe Client Gateway, not the transaction service. Running our own front
end means running our own gateway (Node, Redis, `TX_SERVICE_API_KEY`) or a CORS proxy, tracking a
large monorepo (yarn 4, Next.js, Expo) through Safe Pro's churn, and re-applying the patch on each
sync. We would own a copy of their whole surface to fix one function. It also doesn't gain any
PicoQuorum feature. Pass, unless the PR dies and a co-signer insists on Safe's exact UI.

### Tier 2: a PicoQuorum web app

Scope: the things only we can do, on top of Tier 0.

| Feature | Why it's ours | How |
|---|---|---|
| **"What the console will show"** | The console decodes with `firmware/decode.py` and hashes with `safe_tx.py`. Run the same files in the browser so the proposer sees the exact pages, red ones included, before proposing. | The emulator already runs MicroPython in WebAssembly (`emu/core/runtime.mjs`). Load `safe_tx.py`, `decode.py`, `quorum_cfg.py` headless; render the pages as HTML. |
| **Which owner is a PicoQuorum key** | Our contract signatures carry `"origin":"picoquorum"` in `clientDataFields`; owners that are `SafeWebAuthnSignerProxy` instances can be matched to attest bundles. | Parse confirmations (`sigs.mjs` `parse`); fetch `attest-<serial>.json`; run the `tools/quorum verify` checks (`attest.mjs`) in the browser; show a badge: "sealed Trust M, Infineon cert OK, binding OK, factory key live". |
| **Propose** | Safe{Wallet} proposing works, but our page can refuse what the console will refuse (unpinned delegatecall, wrong Safe) before it is queued. | `POST /api/v1/safes/{safe}/multisig-transactions/` with the EOA's EIP-712 signature from the browser wallet. |
| **Reject** | "Rejecting on the console doesn't reject on the Safe" (LADDER known issue). | Propose the zero-value self-call at the same nonce, sign it. |
| **Execute** | Tier 0. | As above. |
| **Owner ceremonies** | `swapOwner` / `addOwnerWithThreshold` for a new chip, from the attest bundle, with the address checked three ways. | Build the Safe call from the bundle's owner address; verify `getSigner` agrees onchain first. |
| **Fleet view** | Several Safes on several chains, like `QUORUM_SAFES`. | Same queue view across chains. |

Architecture: still a static SPA. No backend unless we want push or a shared key (see "a relay"
below). Browser wallet via EIP-1193 first; WalletConnect later if a co-signer needs a phone wallet.

Effort: 2–4 weeks for a usable first version, most of it UI. The in-browser MicroPython piece is a
few days because the emulator already does the hard part.

### How the console talks to the web app: three transports

1. **Keep Wi-Fi polling of `api.safe.global` (status quo).** The web app and the console never talk;
   Safe's service is the shared queue. Simplest. No change on the Pico.
2. **A PicoQuorum relay.** A small server the console polls instead of Safe's service: it proxies
   the queue with one server-side API key, pins our own TLS root in `firmware/vhttp.py` (we issue
   our own CA for device↔relay, separate from the public web certificate), authenticates each
   console by a chip-signed challenge (Part 2), hosts attest bundles and an address book, and could
   push ("a transaction is waiting") instead of polling. It is a trusted-ish component: it can lie
   about owners and threshold, never about what gets signed (the rehash holds). Worth it only once
   there are several consoles and people.
3. **USB courier mode (WebSerial).** The web app sends the raw fields over USB, the console
   rehashes, shows, signs, and the browser posts the confirmation. This is picowallet's model
   (`firmware/usbwallet.py`, `docs/USB.md`, `app/.../services/usb/link.ts`), so the protocol
   exists. It removes Wi-Fi, the API key on the board, and NTP from the console entirely. Chrome
   only. A good "desk" mode and a good fallback when Wi-Fi is awkward.

Recommendation: 1 now, 3 as a cheap add-on when the web app exists, 2 only with a fleet.

### What a domain and a valid certificate buy, and don't

- Buy: browsers trust the site; co-signers can be sent a link; the console can pin our relay's
  certificate (or our own root) instead of Amazon's roots.
- Don't buy: anything on the chip. A website certificate can't live usefully in a Trust M slot; the
  Pico's TLS (mbedTLS inside MicroPython) does server-certificate checks in software, and offloading
  a TLS client key into the chip would mean patching MicroPython's SSL module in C. Not worth it.
  Device authentication should be at the application layer: the chip signs a challenge, the server
  checks the chain (Part 2). That is what `tools/fw attest` already does on the laptop.

---

## Part 2: the Trust M, our own certificates, and an "ecosystem"

### What the chip can hold

Trust M objects we don't use yet (frozen as spares by T9 today, `tmcfg.SPARES`): certificate slots
E0E1, E0E8 (trust anchor), E0EF; key slots E0F2, E0F3; counters E120–E123; data F1D2–F1DB. On a V3
part also the shielded-connection secret E140 and an authorization reference.

### A PicoQuorum CA

Two levels, one offline root, one issuing key:

```
Infineon ECC Root CA1 (V1) / CA2 (V3)        PicoQuorum Root (offline, HSM or sealed chip)
        │                                             │
  Int. CA 101 / 306                             PicoQuorum Ceremony CA
        │                                             │
  E0E0: factory cert for E0F0  ──binding──►  E0E1: device cert for E0F1
                                              subject: chip serial, profile, build
                                              extension: SHA-256(E0E0 cert), owner address
```

During the ceremony (a new step after T6, before the seal): the laptop's ceremony tool signs a
certificate for the E0F1 public key with the Ceremony CA key, the Pico writes it to E0E1, and T7
seals E0E1 with the rest. Attest bundles then carry the chain, and `tools/quorum verify` (and the
web app badge) check both: "a genuine Trust M holds this key" (Infineon) and "PicoQuorum provisioned
it under this profile and build" (us).

What it enables:
- **Recognition.** Anyone can tell a PicoQuorum key from any P-256 passkey, offline, from the
  owner proxy's public key alone, if we publish the Ceremony CA cert.
- **Device authentication to a relay** (transport 2): the console answers a challenge with E0F1 (or
  a second key in E0F2 so the Safe key never signs anything but Safe hashes). The relay checks the
  chain, and only enrolled consoles see the queue or get an API key.
- **Revocation and inventory.** A CRL or a signed list of retired serials, which the web app and
  the console can read.
- **Onchain, later.** `TrustMAttest.sol` already verifies Infineon's chain. A guard or a registry
  could require attested owners. Keep it off-chain until there is a reason.

What it doesn't fix: the chip signs any digest it is handed. A certificate says who made the key,
not who pressed Sign. That part is below.

### V1 versus V3, and why real keys should be V3

| Capability | V1 (TM1, TM2, CA 101) | V3 (CA 306) | What it would do for us |
|---|---|---|---|
| Shielded connection (encrypted I2C, secret in E140) | no | yes | **Pair a key to its console(s).** Set E0F1's Execute condition to `Conf(E140)`: the key signs only over a channel keyed by a secret the console holds. A stolen key is inert on a stranger's board. |
| Authorization reference, `Auto(oid)` | no | yes | **A PIN.** The console derives a secret from the PIN typed on the knob and proves it to the chip; E0F1 Execute = `Auto(oid)`. The chip's security event counter throttles guessing. The PIN-derived secret never has to sit in flash. |
| Protected update (keys and metadata, signed by a trust anchor in E0E8) | data only | yes | **Signed field updates** of records, address books, even a re-key, authorised only by PicoQuorum's update key. Our own "boot signing" for what lives on the chip. |
| HKDF, more curves | no | yes | Deriving session and pairing keys cleanly. |
| CalcSign, GenKeyPair, certificates, factory key, LcsO seals | yes | yes | Everything quorum-tm1 does today. |

The driver impact: `firmware/trustm.py` (upstream) and `trustm_q.py` already speak the APDUs V3
shares with V1. New work: the shielded-connection presentation layer (AES-128-CCM over the IFX
frames; MicroPython has AES-ECB/CBC in `cryptolib`, so CCM is built by hand) and the `Auto`
handshake. The emulator's `trustm_sim.py` would need both too. Order of magnitude: 1–2 weeks of
firmware plus a sacrificial V3 chip or two.

Caveat to confirm on silicon before relying on it: whether the V3 "Auto" condition can be set on a
key object's Execute by us (a blank V3), not only on Express parts. The configuration guide
describes it generally, so it should.

### Pre-configured chips: who provisions

| Route | What you get | Fit for us |
|---|---|---|
| **Our ceremony on blank V3 parts** (today's model, V3 silicon) | E0F1 key, record, binding, our E0E1 cert, our E0E8 trust anchor, E140 pairing secret, Auto reference, seals. | Yes. It is what T1–T10 already does, with three more objects written. Dozens to hundreds of chips. |
| **Trust M Express** | Infineon-provisioned keys and certs, downloadable from CIRRENT Cloud ID, plus PBS and Auth-Ref per chip. MOQ about 4,000. | Not for us: the certificates are Infineon's, not PicoQuorum's, and the Safe key still has to be made in our ceremony. |
| **Trust M Fit** (custom factory provisioning) | Our CA's certs written at Infineon's CC facility. MOQ in the tens of thousands. | Only if this ever becomes a product at scale. |

So "pre-configured PicoQuorum chips" means: we buy blank V3s, run the ceremony, and hand out
sealed keys with a printed fingerprint and an attest bundle. The ecosystem is the Ceremony CA cert
plus the verify tool, both public.

### "Pico-style boot signing": signed firmware on the RP2350

What it takes:
1. **Freeze the console into the MicroPython binary.** Secure boot signs the flashed image, not the
   `.py` files on LittleFS. The console (`firmware/manifest.json`'s console image) becomes frozen
   modules in a custom MicroPython build (a `manifest.py`), so the whole thing is one signed binary.
   `tools/fw verify` then compares a build hash, not file hashes.
2. **Seal and lock.** `picotool seal --sign` with a secp256k1 signing key (that's the RP2350's
   choice, unrelated to our P-256 keys), hash into OTP, `SECURE_BOOT_ENABLE`. Irreversible per board.
   Optionally encrypt the image with an OTP key so the flash isn't readable in the clear.
3. **Close the REPL** in that image (`docs/mainnet/CONFIGURATION.md` lists it as later). Tooling
   then needs another path: a signed update over USB (the bootrom's UF2 path only accepts signed
   images once secure boot is on), or BOOTSEL + signed UF2. Logs and `fw verify` move to a
   read-only USB-serial command set with no `exec`.
4. **Bind the chip to the image.** With the pairing secret for the shielded connection stored in
   the encrypted image or derived from an OTP value, the Trust M signs only for PicoQuorum firmware
   on that board. That is the piece that makes a stolen key chip, or a stolen board with a REPL,
   not a free signature.

What it buys, honestly: it closes "anyone with a USB cable" (`docs/SECURITY.md`, THREAT-MODEL
"what you can't rely on"). It does not close fault injection; the published attacks reactivate
debug and bypass signature checks. The Safe's threshold stays the real control, as it is today.

Costs: a custom MicroPython build per release (CI job), one sacrificial Pico 2 W per OTP mistake
(`hardware/HANDOFF.md` already says "spare board only"), and the dev loop gets slower because
nothing can be pushed with `mpremote` to a sealed board. Keep an unsealed dev board forever.

### Where the Trust M helps with signing things other than Safe hashes

- **VerifySign with a trust anchor in E0E8:** the chip verifies a P-256 signature against the
  PicoQuorum update key in about 100 ms, versus 1.4 s for `p256.verify` in MicroPython. Signed
  bundles the console could check this way: the per-chain known-contracts and token list
  (`quorum_cfg.py`), an address book, a retired-serials list, a relay's response. The web app would
  sign these with the same key the chip trusts.
- **A use record.** Counters E120–E123 are frozen spares today. On V3 a counter can be tied to a
  key's Execute (`Int(counter)`), which gives the Trust M the use count the ATECC has
  (`docs/mainnet/CONFIGURATION.md` "later"). Worth folding into the V3 profile.

---

## Part 3: what the GS021 episode says

- Safe's UI is a dependency we don't control and whose incentives (Safe Pro, teams, policies) point
  away from EIP-1271 passkey-style owners in a plain 2-of-3. The bug has been known since 2024.
- Our stack doesn't need their UI: the transaction service API, the contracts, and protocol-kit's
  layout rules are all public and stable. Tier 0 removes the dependency for the one step that
  breaks; Tier 2 removes it for proposing too.
- Keep the PR open; a static Execute page and the PR are not in conflict. If #8809 merges, Tier 0
  stays useful as the attested-owner view, and Safe{Wallet} becomes usable for the rest.

---

## Recommended path

| Phase | What | Depends on | Effort |
|---|---|---|---|
| **A. Execute page** | Tier 0 on a PicoQuorum domain, from `live.mjs` + `sigs.mjs` + `wallet.html`. Paste-your-own API key. | the domain | ~2 days |
| **B. Attested-owner badge** | `attest.mjs` checks in the browser; publish attest bundles at the domain. | A | ~3 days |
| **C. Ceremony CA** | A PicoQuorum root and Ceremony CA; a new ceremony step writes E0E1; `verify`, the badge and the bundle format gain the second chain. Run on a sacrificial chip first. | B | ~1 week |
| **D. Buy V3 chips** | Confirm the part (CA 306 in E0E0, firmware 3.x), design quorum-tm2: E0F1 + Conf(E140) pairing + Auto PIN + Int(E120) use counter + E0E1 cert + E0E8 trust anchor. Shielded-connection layer in `trustm_q.py` and `trustm_sim.py`. | C | 2–3 weeks |
| **E. Web app** | Tier 2: propose, in-browser decode via the emulator runtime, reject, owner ceremonies, fleet view. | A, B | 2–4 weeks |
| **F. Signed firmware** | Frozen MicroPython build, `picotool seal`, REPL closed, signed-update path, OTP on a spare board, then Build 1. Pairing secret from the sealed image. | D | 2–3 weeks |
| **G. Relay (optional)** | Only with several consoles: proxy, device auth by chain, push, pinned root. | C, E | 2 weeks |

Phases A and B are cheap and remove the pain now. C and D are the "ecosystem" and the chip's
security story. E is the product. F is the board's security story. G waits for a fleet.

## Open questions for Jason

1. Domain: what name, and is a static host (Cloudflare Pages / GitHub Pages) acceptable, or do you
   want a server from day one (which changes the API-key story)?
2. Who are the users of the web app: you and your co-signers only, or anyone with a PicoQuorum key?
   The answer decides whether paste-your-own API key is acceptable long term.
3. Chips: willing to buy V3 parts (bare SLS32AIA010ML/MK or a V3 breakout) and retire TM1/TM2 to
   dev duty? Everything in Part 2 beyond the CA depends on it.
4. The PIN: on the console's knob (digits) or a hold-pattern on the buttons? It decides the UI work
   in D.
5. Secure boot: comfortable sacrificing a Pico 2 W or two to OTP mistakes, and losing `mpremote`
   push on sealed boards?
6. Keep pushing #8809 (nudge a maintainer after Safe Pro ships), or let it sit now that Tier 0 is
   planned?

## Verification, per phase

- **A/B:** against the Base Sepolia Safe `0xEDED…0a43` and the fork (`tools/quorum up`): the page
  must execute a 2-of-3 with a Pico confirmation where Safe{Wallet} shows GS021; the badge must go
  green for TM1's bundle and red for TM2's (its factory key was replaced).
- **C:** `node test-vectors/run-trustm.mjs` extended with the E0E1 step on the emulator; a
  sacrificial chip through the full ceremony; `tools/quorum verify` checks both chains; a tampered
  E0E1 fails.
- **D:** on a sacrificial V3: Conf(E140) refuses CalcSign on a plain channel and accepts it shielded;
  Auto refuses the wrong PIN and the security event counter rises; the use counter increments per
  signature; all with the refusal scripts pattern in `tools/board/tm_refusals.py`.
- **E:** the browser's decode pages equal the emulator's shots for every story in
  `tools/quorum scenarios`; proposing from the page produces a queue the console approves.
- **F:** a spare Pico 2 W: an unsigned image refuses to boot, the signed image runs the console,
  `tools/fw verify` passes against the build hash, the REPL is gone, and a signed update applies.
