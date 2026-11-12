<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/lockup-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/brand/lockup-light.svg">
    <img alt="Picoquorum" src="docs/brand/lockup-light.svg" width="420">
  </picture>
</p>

<p align="center">
  <strong>Several people, several keys, one Safe.</strong><br>
  Hardware approvals for <a href="https://safe.global">Safe</a> multisig wallets.
</p>

<p align="center">
  <a href="https://picoquorum.app/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fpicoquorum.app%2F&label=site&up_message=live&up_color=34C759&labelColor=0B0D11"></a>
  <a href="https://x.com/picoquorum"><img alt="Follow @picoquorum on X" src="https://img.shields.io/badge/X-%40picoquorum-F2F4F7?logo=x&logoColor=F2F4F7&labelColor=0B0D11"></a>
  <a href="https://picoquorum.app/console/"><img alt="Try the console in your browser" src="https://img.shields.io/badge/console-try%20it%20in%20your%20browser-7A92FF?labelColor=0B0D11"></a>
  <a href="https://github.com/jmcpheron/pico-quorum/actions/workflows/site-check.yml"><img alt="Site check: GitHub Pages serves exactly this source" src="https://github.com/jmcpheron/pico-quorum/actions/workflows/site-check.yml/badge.svg"></a>
  <a href="https://github.com/jmcpheron/pico-quorum/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/jmcpheron/pico-quorum/actions/workflows/ci.yml/badge.svg"></a>
  <br>
  <a href="docs/RELEASES.md"><img alt="Firmware version" src="docs/releases/badges/firmware.svg"></a>
  <a href="docs/RELEASES.md#signing"><img alt="Releases are SSH-signed tags" src="https://img.shields.io/badge/releases-SSH--signed%20tags-34C759?labelColor=0B0D11"></a>
  <a href="https://github.com/jmcpheron/pico-quorum/actions/workflows/release.yml"><img alt="Release" src="https://github.com/jmcpheron/pico-quorum/actions/workflows/release.yml/badge.svg"></a>
  <a href="#the-build-youre-looking-at"><img alt="The console's release fingerprint: its blockie, and its first and last 8 hex digits" src="docs/releases/badges/console.svg"></a>
  <br>
  <a href="docs/LADDER.md"><img alt="Safe 1.3.0 and later" src="https://img.shields.io/badge/Safe-%E2%89%A5%201.3.0-34C759?labelColor=0B0D11"></a>
  <a href="docs/guide/NETWORKS.md"><img alt="Chains: Base and Ethereum" src="https://img.shields.io/badge/chains-Base%20%C2%B7%20Ethereum-627EEA?labelColor=0B0D11"></a>
  <a href="#license"><img alt="Licenses: MIT code, CERN-OHL-W hardware, CC BY-SA docs" src="https://img.shields.io/badge/license-MIT%20%C2%B7%20CERN--OHL--W%20%C2%B7%20CC%20BY--SA-98A0AC?labelColor=0B0D11"></a>
</p>

<p align="center">
  <img src="docs/quorum-ui/v2/boot/orbit-lite.gif" width="240" alt="The Picoquorum boot screen: five owners, three sign, and their triangle turns into the Ethereum diamond">
</p>

Picoquorum is a small console that is **one owner of a Safe**. Each signer's key is a secure element,
on the console's board or on a small key that plugs in. The console shows what a transaction does on
its own screen, works out the Safe transaction hash itself, and asks the key to sign only after you
have seen every page and held the green **Sign** button. **Reject** is red and easy.

The same console also runs [in your browser](https://picoquorum.app/console/), with
your own passkey as its key. That version is one short folder you can read, check against this
README, and sign from on your own computer.

### A pico quorum

A *pico quorum* is a small group that agrees before anything moves: a family's savings, a club's
treasury, a two-person company, a project's release keys. Two of three. Three of five. Too small for
a custody desk, too important for one laptop. Picoquorum gives each person in that group the same
small box and their own key, and makes every approval a deliberate thing you do with your hands.

> **Experimental.** Early design. Use a testnet first, and only small amounts on mainnet. The Safe's
> threshold is the real control: always keep owners on the Safe that are not this console.

## Mono, the reference console

<p align="center">
  <img src="hardware/mono/renders/mono-3q.jpg" width="380" alt="Mono's board: the 1.14-inch screen at the top, D0, D1 and D2 in a row under it, the key chips' sites below them, the RP2350 in the middle, and the USB-C at the bottom end">
</p>

**Mono** is the hardware Picoquorum is working toward, and the one the rest is measured against: the
reference standard for a console. Mono is a working name.

- **What it is.** A 40 × 89.5 mm bar: a 1.14″ screen, three buttons under it, an RP2350, and the
  secure element soldered on. It has no radio at all. Its USB-C reaches a serial chip and nothing
  else: a computer passes on Safe's queue, and has no say in what gets signed.
- **Where it stands.** A design, written by a script and checked by KiCad and against JLCPCB's limits
  ([hardware/mono](hardware/mono/README.md)). Not ordered, and nothing is built. The board it comes
  from, [console-rp](hardware/console-rp/README.md), is on the bench: five boards, the first one up
  on a bench script. The console's firmware for these two isn't written yet. Today the firmware
  runs on the [dev console](hardware/DEV-CONSOLE.md) and [in your browser](https://picoquorum.app/console/).
- **Its case.** Two first drafts, drawn by scripts and not printed: [the case](cad/consoles/README.md#mono),
  and [an industrial variant](cad/consoles/README.md#mono-industrial) with cut corners
  and grooves down its sides ([`cad/consoles/mono_ind.py`](cad/consoles/mono_ind.py);
  `tools/case build mono-industrial` rebuilds it).
- **A dev board kit, possibly.** Mono may become a kit for developers. Nothing is for sale, and no
  date is set.

<p align="center">
  <img src="cad/consoles/out/mono_ind/mono_ind_front.png" width="820" alt="Mono's case, industrial: in the hand with four screws in the face, the back with the name, and the left side with its grooves and cut corners">
</p>

**For developers and contributors.** We may open Mono up to a first few developers and contributors
before anything wider. A sign-up sheet will come later. Until then, watch this repository or follow
[@picoquorum](https://x.com/picoquorum), and try the firmware as it is today: in
[your browser](https://picoquorum.app/console/), or on a [dev console](hardware/DEV-CONSOLE.md) you
build for about $35.

The two ESP32-S3 boards made before it, with their own Wi-Fi, are in
[hardware/prototypes](hardware/prototypes/README.md), and the designs before those in
[hardware/archive](hardware/archive/README.md). Every board and build, and where each stands:
[hardware/README.md](hardware/README.md).

## Four ideas

### 1. A key that can't leak

The key is a secure element: soldered on the console's board, or on a small board you plug in. Its
P-256 private key is generated inside the chip, never leaves it, and never exists as a seed phrase. There is nothing to write down,
photograph or phish. The chip has no command that reads a private key out, it is locked after
provisioning, and the console asks it to sign only a hash the console worked out itself.

Each key owns the Safe through Safe's audited passkey signer
([`firmware/webauthn.py`](firmware/webauthn.py)), with the same owner address on every chain. The
contracts it relies on were checked onchain on Base and Ethereum.

**The USB-C key.** [key-c P2](hardware/key-pcb/key-c-usbc/README.md) is the key as a part you can
hold: an ATECC608C behind a USB-C receptacle on a 16 × 36 mm board, with an ESD
array between the connector and the chip.
- The receptacle is plain wires, not USB: D+ carries SDA, D− carries SCL, and VBUS is key power
  that the console switches on only when the key is fully in.
- 5.1 kΩ on each CC pin tells the console a key is present.
- Five boards were assembled by JLCPCB and read on the bench from 2026-10-16. One went through the
  key ceremony on 2026-10-22 and is a Safe owner.

| parts side | back |
|---|---|
| <img src="hardware/key-pcb/key-c-usbc/renders/key-c-P2-3q-top.jpg" width="360" alt="key-c P2, parts side"> | <img src="hardware/key-pcb/key-c-usbc/renders/key-c-P2-3q-bottom.jpg" width="360" alt="key-c P2, back, with the Picoquorum mark"> |

Mono and console-rp carry the same chip soldered on. The dev console's key is an ATECC608 breakout or
an Infineon OPTIGA Trust M. The other key designs (card edge, pogo pads) are in
[`hardware/key-pcb/`](hardware/key-pcb/README.md).
How a chip is locked: [docs/LOCKING.md](docs/LOCKING.md) and [docs/TRUSTM.md](docs/TRUSTM.md).
What a sealed key can't protect you from: [docs/SECURITY.md](docs/SECURITY.md).

### 2. A simple console that checks on its own

The console is a small board with a screen and a few buttons, running a small amount of MicroPython
you can read. Today that is the dev console, a Raspberry Pi Pico 2 W with a 240 × 240 screen;
[Mono](#mono-the-reference-console) is the board it is headed for. It doesn't take anyone's word for
a transaction: not your
laptop's, not your browser's, not Safe{Wallet}'s, and not the transaction service's.

- **Its own hash.** It rebuilds the Safe's EIP-712 transaction hash from the fields it shows, for
  the chain and Safe it was set up for, and its key signs that hash and nothing else. A service
  that lies about the hash, the Safe or the chain gets a refusal, not a signature.
- **Its own words.** It decodes each call into plain language. Anything that changes who controls
  the Safe, or can't be undone, is a red page, red all over.
- **Its own screen.** You page through every screen before Sign is allowed, then hold it for two
  seconds. The verify code (the hash's last eight characters and its blockie) is there to check
  with whoever proposed it.
- **Its own path.** The dev console talks to the transaction service over its own Wi-Fi and TLS,
  checking certificates against the roots it carries: nothing on your computer is in the loop. Mono
  has no radio. A computer will pass Safe's queue to it over USB, and because the console works out
  every hash itself, that computer has no say in what gets signed.

| | | | |
|---|---|---|---|
| <img src="docs/quorum-ui/shots/02-approve-summary.png" width="180" alt="Send 0.05 ETH to Carol, 1 of 2 signed, yours makes it 2 of 2"> | <img src="docs/quorum-ui/shots/13-owner-red-page.png" width="180" alt="A red page: add owner 0xdead…beef, not in the address book"> | <img src="docs/quorum-ui/shots/11-batch-verify.png" width="180" alt="Check with the proposer: the Safe tx hash ends in f924 aa08, with its blockie"> | <img src="docs/quorum-ui/shots/05-approve-hold.png" width="180" alt="Keep holding A: a progress bar, let go to cancel"> |
| **Plain language.** What it does, who it pays, who has signed. | **Red pages.** Owners, thresholds, anything that can't be undone. | **A verify code.** To check with the proposer. | **Hold to sign.** Two seconds on a guarded button. |

That independence is the point. A second check is only worth something if it fails differently from
the first: different hardware, different code, a different network path, a different person looking
at it. More screens: [docs/quorum-ui](docs/quorum-ui/README.md).

### 3. One owner in a multisig

Picoquorum is never the whole wallet. It is one owner among several, and it is built to sit next to
the others: a hardware wallet, a passkey, Safe{Wallet} in a browser, another Picoquorum in another
house. The project's own Safe is planned around one rule ([docs/GOVERNANCE.md](docs/GOVERNANCE.md)),
and we suggest it for yours: **no technology, and no person, holds a threshold's worth of keys.**

- **Standard Safe.** Any Safe from 1.3.0 on, on Base and Ethereum. Propose anywhere; the console
  reads the same queue Safe{Wallet} does.
- **The app** ([launch it](https://picoquorum.app/app/)) opens any Safe, proposes,
  checks every confirmation in your browser, and executes with your wallet. It holds no key.
- **Several Safes, several chains.** One console watches up to 4 Safes on Base Sepolia, Base and
  Ethereum, with one queue across them ([networks](docs/guide/NETWORKS.md)).
- **A pico quorum per Safe.** A family Safe at 2 of 3, a team Safe at 3 of 5, each owner with a
  console and a key of their own.

### 4. A short stack you can check yourself

[The console page](https://picoquorum.app/console/) runs the console's firmware,
file for file, on MicroPython for WebAssembly, with your passkey (Touch ID, Windows Hello, a phone,
a security key) as its key. It is one folder, it loads nothing from the rest of the site, and it can
reach only Safe's transaction service: its Content-Security-Policy says so, and the browser enforces
it.

| in the folder | |
|---|---|
| `firmware/` | the console image a Pico runs, as plain files: about 11,000 lines of MicroPython |
| `shims/` | Python in place of the Pico's hardware: about 630 lines |
| `console.js`, `worker.js`, `web/`, `core/` | the page: about 1,100 lines of JavaScript |
| `vendor/micropython/` | MicroPython 1.26 for WebAssembly, pinned by its hash: the one part built elsewhere |

That is short enough to read, and you can check it without trusting the site that sent it:
- **Save a copy.** `SHA256SUMS` lists every file: fetch them, then `sha256sum -c SHA256SUMS`. There
  is no build step; these are the files that run.
- **Hold it up to this README.** `firmware/`, hashed with `sha256sum` in a one-line loop, gives the
  console's release fingerprint in [the build table](#the-build-youre-looking-at): the same one a
  Pico running that release shows on its Device screen.
- **Rebuild it.** `cd emu && npm ci && node build.mjs` writes the same bytes. CI checks that on every
  push, and a check from outside compares what Pages serves with the source every six hours.
- **Sign from your copy.** Run `python3 -m http.server` in the folder and open `localhost:8000`. A
  passkey belongs to the site that made it, so one made on your copy can be asked to sign by your
  copy and never by a later version of the site. Its owner address works on a Safe like any other.

The commands: [docs/guide/BROWSER.md](docs/guide/BROWSER.md). The screen is still drawn by your
computer, and the passkey's prompt never shows the transaction, so the hardware console is the
stronger owner: keep passkey owners below the threshold.

## Try it

- **[The site](https://picoquorum.app/)**, with the app.
- **[The console in your browser](https://picoquorum.app/console/)**: the same
  firmware in MicroPython on WebAssembly, with your own passkey as its key. Save it, check it and
  run your own copy ([how](docs/guide/BROWSER.md); the design: [EMU-WEB.md](docs/EMU-WEB.md)).
- **[Learn](https://picoquorum.app/learn/)**: short explainer videos on why a multisig and what the
  console adds to one. The videos are on their way; [their scripts](docs/videos/README.md) are here
  to read.
- **[The owner's guide](docs/guide/README.md)**: from a board to a console that signs for your
  Safes.
- **Build a dev console**: a Pico 2 W, a Waveshare Pico-LCD-1.3 and an ATECC608 breakout, about
  $35 with no soldering ([build guide](hardware/DEV-CONSOLE.md), [parts](hardware/bom/README.md)).
- **On a laptop**, no hardware: `tools/quorum e2e` runs a whole approval with the emulator against a
  Safe 1.4.1 on an Anvil fork of Base ([details](tools/mock-tx-service/README.md)).
- **The hash, checked**: `python3 test-vectors/run.py` runs every vector in
  [`test-vectors/`](test-vectors/), including real mainnet Safe transactions, on CPython; CI runs
  them on MicroPython 1.26 too.

## The build you're looking at

Every firmware image has a **release fingerprint**: one SHA-256 over its source files
([docs/releases](docs/releases/README.md)). A console shows its blockie and first 8 hex digits on the
Device screen; the console page shows the same picture for the same files, and its `firmware/`
folder hashes to it with `sha256sum` ([how](docs/guide/BROWSER.md#2-hold-it-up-to-the-readme)); the
app's Releases page lists each release's. The badges above and this table name the source in this commit, so you can hold a
console up to the README:

<!-- build:begin (node tools/releases/badge.mjs writes this table) -->

| | image | release fingerprint |
|---|---|---|
| <img src="docs/releases/badges/console-blockie.svg" width="32" height="32" alt=""> | **console** | `1eebbf43e652aa289b9495c5dc66a7878e00a54e2f4c9bd2fbc4934a382bc033` |
| <img src="docs/releases/badges/ceremony-blockie.svg" width="32" height="32" alt=""> | **ceremony** | `b023b563b115e06aa9250c192d3c22fa1e07107a50e41ea9462649564e6f7aea` |
| <img src="docs/releases/badges/brand-blockie.svg" width="32" height="32" alt=""> | **brand** | `4fb1d81abf7c37040f02c0d110f9423db2202626df3c7a4a8330c3cb7a718670` |
| <img src="docs/releases/badges/dual-blockie.svg" width="32" height="32" alt=""> | **dual** | `27b254630a065e6c7dc811374a5d2837dee3486b7cd1cc761c546a3758bb9b0d` |

<!-- build:end -->

How a release is trusted ([docs/RELEASES.md](docs/RELEASES.md)):
- **Signed tags.** A release is an SSH-signed tag, `fw-<version>`, checked against
  [`.github/allowed_signers`](.github/allowed_signers) before anything is built.
- **Reproducible pages.** CI rebuilds the app and the console page from source and fails if they
  differ from what is committed. The site check then compares what GitHub Pages serves, byte for byte,
  with the commit it deployed.
- **Approved by a Safe.** The project Safe will approve each release on chain, signed on Picoquorum
  consoles, and the app then shows **Approved by the project Safe**. The code is ready; the Safe
  comes at launch ([docs/GOVERNANCE.md](docs/GOVERNANCE.md)).

## Where it stands

Picoquorum is built in public. **[docs/STATUS.md](docs/STATUS.md)** is the one page for what exists
today: the name (picoquorum.eth) and the domains, every Safe and key with its address, the contracts
the console relies on, and what's next.

The [test ladder](docs/LADDER.md) tracks each chain:
- ✅ a simulated Safe and a local fork, on the real Pico
- ✅ Base Sepolia, end to end over HTTPS on the real Pico
- Base with a few dollars: the Safe is checked and a chip's confirmation has executed there; the
  console's own approval is next
- then Ethereum mainnet, whose contracts have been checked onchain

The hardware, board by board, is in [hardware/README.md](hardware/README.md). The design and the open
questions are in the [kickoff](docs/KICKOFF.md), and the project Safe's plan in
[GOVERNANCE.md](docs/GOVERNANCE.md). Dated notes and photos, mistakes included, are in
[`buildlog/`](buildlog/).

## Layout

| path | what |
|---|---|
| `firmware/` | the console in MicroPython: `quorum.py` and `quorum_ui.py` (the console), `safe_tx.py` (the Safe hash), `decode.py`, `txservice.py`, `webauthn.py`, the chip drivers `trustm.py` and `atecc.py` |
| `hardware/` | the boards ([index](hardware/README.md)): `mono/` (the reference console) and `console-rp/` (the board on the bench); `key-pcb/` (the keys, [key-c](hardware/key-pcb/key-c-usbc/README.md) among them); the dev console and its `wiring/` ([Build 1](hardware/wiring/BUILD1.md), [perfboard](hardware/wiring/SOLDERING.md), [breadboard](hardware/wiring/BREADBOARD.md), [on an ESP32](hardware/wiring/ESP32.md)) and `bom/`; `prototypes/` (the two ESP32-S3 boards); `archive/` (earlier designs) |
| `cad/` | the printed cases, drawn by scripts ([index](cad/README.md)): Mono's and its industrial variant in `cad/consoles/` |
| `docs/` | everything to read ([index](docs/README.md)), and the site GitHub Pages serves: the front page, `app/`, `console/`, `brand/` |
| `web/` | the app's source; `npm run build` writes `docs/app/` |
| `emu/` | the console in a browser: MicroPython in WebAssembly and a virtual secure element. `build.mjs` writes the console page (`docs/console/`); `tools/emu` adds an editor and the case in 3D, for development |
| `test-vectors/` | Safe transactions with known-correct hashes, and the suites CI runs |
| `tools/` | `quorum` (Safes on a fork and on chain), `fw` (build and push images), `emu`, `usb`, `release`, `releases/`, `brand/`, `keypcb` (the boards), `case` (the printed cases), `wiring`, `wiring-esp32` |
| `contracts/` | Picoquorum's own contracts, when there are any; today each key owns a Safe through Safe's passkey signer |
| `buildlog/` | dated notes and photos |

The name, the mark and the colours: [docs/BRAND.md](docs/BRAND.md). `tools/brand/lockup.py` draws the
logo at the top of this page.

## Credit

Picoquorum exists because of [picowallet](https://github.com/austintgriffith/picowallet) by
**Austin Griffith**. picowallet proved that a Raspberry Pi Pico can drive a secure element from
MicroPython, rebuild an EIP-712 digest on the device, show it on its own screen, and sign with a
key that never leaves the chip, all on mainnet. Picoquorum began as a fork of it and is still
built on it:
- the ATECC608 and Trust M drivers, the display driver, keccak and P-256, blockies and the WiFi join;
- the emulator that runs the console in your browser.

Each of those files says so on its first line, under Austin's MIT license. Fixes to the drivers go
back upstream ([docs/UPSTREAM-TRACKING.md](docs/UPSTREAM-TRACKING.md)). Everything else this project
uses is credited in [NOTICE](NOTICE).

Picoquorum runs on Raspberry Pi Pico 2 W. It is not affiliated with Raspberry Pi or Safe.

## License

| | license |
|---|---|
| Code and firmware: `firmware/`, `emu/`, `web/`, `tools/`, `test-vectors/`, the built site | [MIT](LICENSE) |
| Hardware: `hardware/` (the console and key boards, wiring, parts lists) | [CERN-OHL-W-2.0](LICENSE-HARDWARE) |
| Docs, the build log, photos and screenshots | [CC BY-SA 4.0](LICENSE-DOCS) |
| The name Picoquorum and its mark | not licensed: [TRADEMARK.md](TRADEMARK.md) |

Hardware made from these sources must show where the source is ([hardware/README.md](hardware/README.md#license)).
Third-party parts and their licenses are in [NOTICE](NOTICE).
