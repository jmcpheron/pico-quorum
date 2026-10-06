# The emulator on the web, signing with your laptop's passkey

> **Design notes (2026-10-04), being built (2026-10-05).** Built so far:
> - the check in `tools/vectors/passkey.mjs`;
> - release fingerprints (`docs/releases/`);
> - CI and signed releases (`docs/RELEASES.md`);
> - the emulator on Pages (`docs/emu/`), deprecated and then removed on 2026-10-06: `docs/emu/` is
>   a redirect to the console page, and `tools/emu` is the developer's page;
> - your passkey as the key: the toolbar's key menu, with `shims/passkey.py` and the page's WebAuthn;
> - the console page (`docs/console/`): the console alone, screen and buttons, your passkey as its
>   key. The demo below starts there. It shows the passkey's owner address (to add to a Safe) and
>   takes a Safe you already have by chain and address;
> - (2026-10-06) the console page is one folder with everything it runs, its firmware the console
>   image as plain files, so it can be saved, checked against the release fingerprint with
>   `sha256sum`, and run from a copy on `localhost` with a passkey of its own
>   ([guide/BROWSER.md](guide/BROWSER.md)). That is a sixth step for "Where the code comes from",
>   below: take the code out of the site's hands.
>
> The goal is a demo: open a link, the console runs in the page, and Touch ID or Windows Hello is the chip.

## Short answers

- **Hosting: GitHub Pages, not Vercel.** The emulator is already all client side (MicroPython in
  WebAssembly, in a Web Worker). It needs two things the Node server gives it today: COOP/COEP headers
  for `SharedArrayBuffer`, and a few `/ctl/*` routes. A small service worker sets the headers
  (the `coi-serviceworker` trick: one reload on first visit). Each route gets a static
  replacement, and the USB routes just aren't offered there. Vercel would only add real headers. It
  would also cost us the "static, no server, every file hashed in `BUILD.json`" story that
  `docs/app/` has. Cloudflare Pages or Netlify (a `_headers` file) are the fallback if the service
  worker gives trouble in a browser.
- **The EIP is RIP-7212 on the L2s and [EIP-7951](https://eips.ethereum.org/EIPS/eip-7951) on
  Ethereum.** Both are the P-256 (secp256r1) signature precompile at `0x100`. EIP-7951 went live on
  mainnet with Fusaka. The P-256 curve is the one passkeys, Secure Enclaves, TPMs, the ATECC608 and
  the Trust M all sign with.
- **Yes, a laptop passkey works, with no new contracts.** PicoQuorum keys already own Safes through
  Safe's *passkey* signer (`SafeWebAuthnSignerProxy`, `firmware/webauthn.py`). The console builds a
  WebAuthn assertion by hand, so the chip looks like a passkey to the Safe. A real passkey is the
  same thing natively.
- **Yes, on Ethereum.** The same factory, the same owner address, and the precompile is live on
  Ethereum, Base and Base Sepolia (below). On a chain without the precompile, the pinned verifiers
  fall back to Daimo's Solidity verifier, which costs more gas but still works.

## The framing: one console, bring your own key

**It's the same console.** The emulator runs `firmware/*.py` byte for byte. It's not a port and not
a lookalike. The screen is the frame the firmware sent over SPI. So the browser console is the
firmware, in a different body:

| | Pico console | Browser console |
|---|---|---|
| the code | `firmware/*.py`, release `2026.10.n` | the same files, the same release |
| what it computes | the safeTxHash from the fields on screen, the verify code, the blockie | the same |
| the screen | its own LCD | a canvas in a page on your computer |
| the buttons | its own, wired to the Pico | your keyboard |
| the key | a plug-in chip (ATECC608, Trust M) | **your own passkey** (Touch ID, Windows Hello, a phone, a YubiKey) |
| key cannot be copied out | yes | yes, except synced passkeys, which go to your Apple or Google account |
| the screen can't be faked by the computer | **yes** | **no** |

So "bring your own passkey" is the right name for it. Someone in the multisig who has no chip still
gets the same clear-signing screens and checks, with a key they already own. Later they can buy a
key, and the Safe swaps that owner for the chip's.

**The one thing it doesn't carry over is the last row.** The JavaScript sandbox protects your
computer from the page. It does nothing to protect the page from your computer. Malware, or a
browser extension allowed on the site, can redraw the canvas, or hand the passkey a different
challenge than the hash on screen. The Touch ID prompt says "sign in to jmcpheron.github.io"; it
never shows the transaction. So a passkey owner is safe from key theft but not from a compromised
computer. Two things limit the damage:
- **The quorum.** One passkey owner on a bad laptop is one wrong vote. The other owners' consoles
  compute the hash themselves and show the real transaction. Keep passkey owners below the threshold.
- **A cleaner body.** A dedicated browser profile with no extensions helps. A separate device helps
  much more: an old phone or tablet used only for this is close to a hardware console.

  A VM on the same laptop does less than it seems. It keeps out what runs inside it (extensions,
  other apps), but the host can still see and draw the VM's screen.

## Where the code comes from

The page is static, so what you run is whatever the server sent on this visit. GitHub Pages serves
it from the repo over HTTPS. Without more, trusting the page means trusting the GitHub account.
These steps narrow that, roughly from cheapest to strongest:

1. **Reproducible build and `BUILD.json`**, as the app does now. Anyone can rebuild the release's
   commit and compare hashes.
2. **The firmware's identity on screen.** The Device screen already shows `2026.10.n · <commit>`. The web build
   puts the firmware files' SHA-256 (and its blockie) there too, and so does `tools/fw build` for
   the Pico. The same release gives the same picture on both. Owners can compare across the room,
   or with `RELEASES.md`.
3. **Signed releases.** Sign the tag `fw-<version>`, and have a GitHub Actions build attest the
   built files (build provenance). A checker page, or `tools/quorum`, verifies them.
4. **Check the live site from outside.** A page can't vouch for itself. A service worker can't pin
   one either: the browser fetches the worker script from the site again, at least once a day, so
   whoever controls the site can replace it, and with it everything it pins.

   Instead, `tools/release check-site` fetches what Pages serves and compares every byte with
   `docs/` at the commit Pages deployed. `.github/workflows/site-check.yml` runs it after every
   deploy and every six hours, and opens an issue on any difference. The app's Releases page says
   which release the page is, and whether the project Safe approved it. That line is information for
   the visitor; the outside check is what proves it.
5. **Later, the quorum picks the code.** Put the build on IPFS, and have an ENS name the Safe owns
   point to it. Changing the web console then takes a Safe transaction that the owners approve on
   their consoles. Note: a passkey is tied to its domain, so moving there means new passkeys.

The same manifest hash ties the web build to the Pico. A Pico running `2026.10.n` and a browser
running `2026.10.n` show the same firmware identity, because they are the same files.

## How the emulator shows it

- **The screen stays identical.** No web-only screens and no restyling. It's the point of the demo,
  and it keeps `docs/quorum-ui` true for both.
- **The key is a plug-in, here too.** The 3D view shows the key-c board in the console's key port
  for a chip. For a passkey, a passkey key sits in that port (a fingerprint on its cap). On screen,
  the key changes and the console doesn't.
- **The firmware names the key and the body, through its existing hooks.** The signer's `name` and
  `info()` make the Chip page and the boot line say "Passkey · Touch ID · this Mac" (or "synced").
  The signing screen's line "The chip signs the hash computed here" takes its subject from the
  signer: "Your passkey signs…". The Device screen says "browser" next to the version and the
  firmware blockie. Those are the only places that differ, and all of them come from code that
  runs on the Pico too.
- **Beside the device, not on it:** the firmware hash and the release it matches. Also, before the
  first signature: "Touch ID won't show the transaction. What you approve is this screen. On a
  shared or untrusted computer, use a hardware key."

## What was checked

`tools/vectors/passkey.mjs`: Chromium makes a passkey on a virtual platform authenticator with user
verification (the code path Touch ID takes, without the finger). It signs a real safeTxHash from
`test-vectors/safe_tx.json`. The signature is packed exactly as `webauthn.encode` packs the chip's.
Then the script asks the deployed factory on each chain, read only:

```
clientDataJSON    {"type":"webauthn.get","challenge":"h1ky9BUZ…-G3IM","origin":"http://localhost:46539","crossOrigin":false}
clientDataFields  "origin":"http://localhost:46539","crossOrigin":false
flags 0x05: UP yes, UV yes (the contract needs UV)
pass  Base Sepolia  owner 0x94b5…3BC9  low s 0x1626ba7e  high s 0x1626ba7e
pass  Base          owner 0x94b5…3BC9  low s 0x1626ba7e  high s 0x1626ba7e
pass  Ethereum      owner 0x94b5…3BC9  low s 0x1626ba7e  high s 0x1626ba7e
```

`0x1626ba7e` is EIP-1271's "valid signature". The script also called the precompile at `0x100`
directly on Ethereum and Base, and it answered 1 on both. What this settles:

- The browser's clientDataJSON starts with `type` then `challenge`, as the contract rebuilds it.
  Everything after the challenge is the `clientDataFields` string, the same slot where the console
  puts `"origin":"picoquorum"`.
- The contract ignores the rpIdHash. So the owner address depends only on the public key, not on
  which site made the passkey.
- The verifier accepts high s as well. We should still normalize to low s, as `p256.py` and the
  signers do. It is harmless, and it stays correct if a future verifier gets stricter.

Run it: `cd tools/vectors && npm ci && npm run passkey` (`PQ_CHROMIUM=` if playwright-core has
no Chromium of its own; `--chain eth` for one chain).

## Why not a "virtual Trust M" backed by the passkey

It's tempting to keep `trustm_sim.py` and route its CalcSign to the laptop's key. That can't work.
CalcSign signs any 32-byte digest it is handed, and a passkey never does. A passkey signs only
`sha256(authenticatorData || sha256(clientDataJSON))`, and it writes both of those itself, putting
the real origin and its own flags and counter in them.

The console asks the chip for exactly that digest, built from authenticatorData and clientDataJSON
that the console writes itself. So the passkey has to come in one layer up: at "make an assertion
over this safeTxHash", not at "sign this digest". It is a third key technology next to the ATECC608
and the Trust M, which suits KICKOFF's "no single technology holds more than two keys" well.

## The firmware seam

Today `quorum.sign_it` does:

```python
ad, fields, digest = webauthn.assertion(e["mine"])
r, s = sig.sign(digest)
```

Add one method to the signer interface (`signer.py`), with a default for the chips:

```python
def assertion(self, challenge):          # -> (authenticatorData, clientDataFields, r, s)
    ad, fields, digest = webauthn.assertion(challenge)
    r, s = self.sign(digest)
    return ad, fields, r, s
```

`quorum.sign_it` calls `sig.assertion(e["mine"])` and nothing else changes. The challenge is still
the safeTxHash the console computed from the fields on screen, so it is still no blind signature.
`webauthn.contract_signature` and `owner_address` work on any (ad, fields, r, s) and (qx, qy).

A new `PasskeySigner` (only present in the emulator) maps the rest of the interface:

| Signer interface | Passkey |
|---|---|
| `pubkey()` | from `getPublicKey()` at creation, kept in the virtual chip's state |
| `assertion(c)` | `navigator.credentials.get({challenge: c, userVerification: "required"})`, DER to (r, s), low s |
| `sign(digest)` | refused: "a passkey signs only assertions" |
| `genkey()` / `needs_ceremony()` | `navigator.credentials.create`: the key ceremony is one Touch ID prompt |
| `serial()` | a short hash of the credential id |
| `use_counter()` | the authenticator's signCount (a YubiKey counts; iCloud and Google passkeys report 0) |
| `profile()` | `passkey`; `name` says which kind if the browser tells us |
| lock / slots | one slot, nothing to lock |

The bridge mirrors what `worker.js` does for HTTP and keys. WebAuthn isn't available in a worker, so
the `_emu.passkey_get` call posts to the page and blocks on `Atomics.wait`. The page runs the
WebAuthn call, writes the result into a SharedArrayBuffer and wakes the worker. To the console it's
a slow chip. The screen stays on "Signing · The chip signs the hash computed here" while the OS
prompt is up. Cancelling the prompt becomes "Not signed".

If there's no platform authenticator, the page can fall back to a **soft chip**: a non-extractable
WebCrypto P-256 key in IndexedDB. ECDSA-SHA256 over `ad || sha256(clientDataJSON)` is exactly the
digest the console wants, so the console writes the assertion as it does for the chips. There is no
prompt and no hardware. It is useful for CI and Firefox, and it is labelled as software.

## Hosting on Pages: what changes

> **Now (2026-10-06):** only the console page is on Pages (`docs/console/`, `emu/README.md`). It is
> one folder: the console image as plain files, only the shims it uses, its own small worker. Its
> CSP allows the folder and Safe's service and nothing else, and `sw.js` sends that as a header with
> COOP/COEP, so it binds the worker too. The emulator's page below, with the editor and the 3D case,
> stays local (`tools/emu`).

Built into `docs/emu/` by an `emu/build.mjs`, in the style of `web/build.mjs`: pinned dependencies,
SRI, and a `BUILD.json` of hashes. It is served under the same origin as the app, at
`/pico-quorum/emu/`.

| Today (`emu/server.mjs`) | On Pages |
|---|---|
| COOP/COEP headers | `coi-serviceworker.js`, vendored (no CDN, keeping the strict CSP) |
| `/vendor/*` from `node_modules` | copied at build time: MicroPython wasm (0.5 MB), CodeMirror, three.js |
| `GET /ctl/boot` (firmware + shims) | `boot.json` written at build time from `workspace.mjs`; about 0.9 MB of firmware |
| `/ctl/chip` (chip state) | IndexedDB in the browser, per visitor |
| `POST /ctl/file` (editor saves to disk) | saved in the browser, with a "download" button |
| `/ctl/events`, `/ctl/reply` (the CLI drives the page) | not offered; `tools/emu` stays the local path |
| `/ctl/devices`, `ship`, `flash` (USB) | not offered at first. Later, Web Serial could put a sketch on a real Pico from Chrome. |
| `/app` proxy (a laptop service, such as tools/quorum's mock) | not needed by the quorum console |
| case STLs (9.5 MB) | gone: the case left the repository on 2026-10-06, and every view is flat |

From the browser the console talks straight to Safe's transaction service. The `requests` shim
already does that with sync XHR, and CORS fetches are fine under COEP. Safe's API key comes from
the same `localStorage` the app uses for its setting (same origin), so it is set once for both.

## The demo

1. Open `…/pico-quorum/console/`. The screen asks you to make a passkey; the OS asks for Touch ID.
   With a Safe saved in the app, the console boots and shows its owner address and blockie,
   computed on the console by `webauthn.owner_address`. On your other device (the passkey synced
   there), choose **I already have one**: it signs twice and the page works out the same key.
2. In the app, **Keys → Your passkey** (`#/passkey`): deploy its signer on Base Sepolia, then **Add to**
   your test Safe, which opens Add owner with its address filled in.
3. Propose a send from the app. The emulated console picks it up, decodes it, and shows the verify
   code and hash blockie, the same screens as the hardware.
4. Hold A. Touch ID prompts. The confirmation goes to Safe's service, and the app shows it checked,
   then executes.

A phone works too: Chrome and Safari offer "use a phone or tablet" (hybrid, by QR code). A YubiKey
works as well (ES256).

## Limits to say out loud

- **The emulator is not a trusted display.** The console's point is a screen the computer can't
  draw on. In the browser, the "screen" is the page. A passkey owner made this way is a real owner
  and a fine demo or test key, but it isn't a console. On the app, it should show as "passkey", not
  as a PicoQuorum key.
- **No Verified badge.** Platform passkeys give `none` attestation. The badge means a genuine Trust M
  (`attest.mjs`), and that stays true. A YubiKey with `direct` attestation could be checked one day,
  the way the Infineon certificate is.
- **Synced passkeys live in the Apple or Google account.** iCloud Keychain and Google Password
  Manager copy the key to your other devices. For the threat model, that makes the account a
  separate trust domain, not one laptop. Windows Hello and YubiKeys stay on the device.
- **The rpId is `jmcpheron.github.io`.** Every Pages site under that account shares it, and any of
  them could ask for the passkey, behind a prompt. A credential is also tied to its rpId forever. A
  custom domain should come before anyone holds value with a passkey owner. Moving domains later
  means a new passkey, which is an owner change on the Safe (the address follows the key, not the
  domain).
- **Losing the stored public key** (cleared site data) doesn't lose the key. One assertion gives two
  candidate public keys, and a second one picks between them. Or the page can recover the key from
  any confirmation it already posted.

## Steps

1. `signer.assertion()` plus the `quorum.sign_it` change, with test vectors: no behaviour change for
   the chips. The signing line and Device screen take their wording from the signer.
   The firmware files' hash goes on the Device screen, on the Pico too.
2. `emu/build.mjs` writing `docs/emu/` with `boot.json` and the service worker; the emulator
   boots from Pages with the soft chip.
3. `PasskeySigner` and the worker/page bridge; the ceremony and signing screens on a real Mac.
4. App: show passkey owners as such; offer "deploy signer proxy" for them.
5. Signed tags plus build provenance for releases, and a check of the live site from outside it.
6. Custom domain, before anything but test Safes.
