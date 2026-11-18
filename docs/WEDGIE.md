# Wedgie: where picowallet went

Picoquorum grew from Austin Griffith's [picowallet](https://github.com/austintgriffith/picowallet).
picowallet's last commit is `91c94e7`, 2026-10-02. Austin's work on the same hardware idea now
happens in **wedgie** ([wedgie.dev](https://wedgie.dev)), kept by his agent account
[clawdbotatg](https://github.com/clawdbotatg). This note says what wedgie is, how it sits next to
Picoquorum, and what in it is worth watching.

Read on 2026-11-17: [wedgie-dev](https://github.com/clawdbotatg/wedgie-dev) at `089868f`
(2026-11-16, firmware 0.3.87) and [wedgie-safe](https://github.com/clawdbotatg/wedgie-safe) at
`edf7186` (2026-11-16, safe-76). Everything below is from reading those two repositories. Nothing
of wedgie's was run here, and no wedgie has been on this bench.

## What it is

A wedgie is a pocket computer made from three parts off the shelf, with no soldering: a Raspberry
Pi Pico, a Waveshare Pico-LCD-1.3, and a secure chip (an Adafruit OPTIGA Trust M breakout, or an
ATECC608) **wedged** into the gap between the two boards. The chip's four wires go into the hat's
header, in the same sockets as the Pico's pins. That is where the name comes from
([LORE.md](https://github.com/clawdbotatg/wedgie-dev/blob/main/LORE.md)).

These are the same three parts as picowallet and as Picoquorum's
[dev console](../hardware/DEV-CONSOLE.md), on the same pins: the chip on GP4 and GP5, A on GP15,
Y on GP21.

It runs MicroPython and the wedgie firmware, and boots straight into one app. Apps are games,
tools, and **Safe Signer**, which makes the wedgie an owner of a Safe. wedgie.dev sells it built
or as a kit (BuidlGuidl), and everything is MIT, the case and the art included.

| | where |
|---|---|
| The site and the firmware | [clawdbotatg/wedgie-dev](https://github.com/clawdbotatg/wedgie-dev) |
| Safe Signer, the app that signs for a Safe | [clawdbotatg/wedgie-safe](https://github.com/clawdbotatg/wedgie-safe) |
| The other apps, one repository each | `clawdbotatg/wedgie-*`; the shelf is wedgie-dev's `community.json`, each app pinned to a reviewed commit |
| The guides, written for people and for AI agents | [wedgie.dev/skill.md](https://wedgie.dev/skill.md) (the index), then `usb.md`, `build.md`, `safe.md`, `security.md`, `code.md`, `trustm.md` |
| A wedgie in a browser tab, no hardware | [wedgie.dev/virtual](https://wedgie.dev/virtual) |
| The Safe page that goes with it | [wedgie.dev/safe](https://wedgie.dev/safe) |
| The passkey Safe wallet a wedgie hardens | [instantwallet.io](https://instantwallet.io), [clawdbotatg/instant-wallet](https://github.com/clawdbotatg/instant-wallet) |
| The case | [clawdbotatg/clawd-pico-case](https://github.com/clawdbotatg/clawd-pico-case) |

## The same as Picoquorum

Safe Signer and the Picoquorum console came to the same design from the same start:

- **The key is P-256, made inside the chip, and never leaves it.** Neither chip does secp256k1, so
  the key is never a plain Ethereum account.
- **On chain it is a Safe owner through Safe's passkey signer** (`SafeWebAuthnSignerFactory`,
  safe-modules passkey 0.2.1), a contract signature with `v = 0`. The device writes
  `authenticatorData` and `clientDataJSON` itself, with the Safe transaction hash as the challenge.
  Only the origin field differs: `"https://wedgie.dev"` there, `"picoquorum"` here
  (`firmware/webauthn.py`).
- **The device works out the Safe transaction hash from the fields.** The computer sends fields,
  never a hash to sign. Rule 1 of [AGENTS.md](../AGENTS.md) here; "the wedgie trusts nothing plugged
  into it" there ([EXPECTATIONS.md](https://github.com/clawdbotatg/wedgie-dev/blob/main/EXPECTATIONS.md)).
- **Its own screen says what will happen, and only a real press signs.** Green is yes, red is no.
- **Both hit the same Safe{Wallet} bug.** Safe{Wallet} can't execute a transaction that a contract
  signature confirmed: it fails with GS021. wedgie's docs send people to
  [issue #8808](https://github.com/safe-global/safe-wallet-monorepo/issues/8808) for it, which is
  the issue Picoquorum opened ([upstream/safe-wallet-gs021/](upstream/safe-wallet-gs021/)). Each
  project executes from its own page instead.

## Where they differ

| | wedgie | Picoquorum |
|---|---|---|
| What it is | a pocket computer: one app at a time, from a shelf of them | a console that does one thing: approve for a Safe |
| What runs on it | a signed core, plus the app, plus anything put on after a yes to FULL CONTROL (a red border stays on the screen) | one image that is exactly what it imports, with one fingerprint ([RELEASES.md](RELEASES.md)) |
| Who signs releases | two release keys (a Mac's Secure Enclave, a YubiKey); the wedgie checks the signed list before it installs | SSH-signed tags, and the project Safe approves each release's fingerprint ([GOVERNANCE.md](GOVERNANCE.md)); the console shows its fingerprint for you to compare |
| How a transaction arrives | over USB, from wedgie.dev/safe in Chrome or Edge | the dev console fetches it itself over its own Wi-Fi and TLS; the USB link never signs ([USB-LINK.md](USB-LINK.md)) |
| Before it signs | green (A) signs; what it can't read is red, and A still signs ("warn, don't block") | every page is seen first, then Sign is held for two seconds |
| What it reads | its own decoders, plus ERC-7730 descriptors with a Merkle proof to a root built into the app | its own decoders (`firmware/decode.py`) |
| The key | made on first start, then locked for good; one per wedgie | made in a ceremony or branded at the bench ([PROVISIONING.md](PROVISIONING.md), [BRANDED-KEYS.md](BRANDED-KEYS.md)); several keys, on the board or on plug-in keys |
| Hardware | the three parts, in a printed case | the same three parts as the dev console; [Mono](../hardware/mono/README.md) is the board it is headed for |
| The browser version | a virtual wedgie with a software Trust M | [the console page](https://picoquorum.app/console/), with the visitor's passkey as its only key |
| License | MIT, everything | MIT code, CERN-OHL-W hardware, CC BY-SA docs |

wedgie's guides say plainly what it doesn't stop
([security.md](https://wedgie.dev/security.md), "Honest limits"). Two of them matter to anyone
building on these parts:

- **An app runs with the whole chip.** The Safe key is locked so nothing can replace it, but any
  code on the wedgie can sign with it. This is the reason Picoquorum's console image holds nothing
  else that can use the chip.
- **The chip's wires are plain I2C.** Something on the same wires can answer as the chip, or
  change the hash on its way to be signed. Picoquorum's dev console has the chip on the same two
  wires. This note does not say what Picoquorum does about it: that belongs in
  [SECURITY.md](SECURITY.md).

Also there, as on any RP2040 or RP2350 without secure boot: whoever holds the board can hold
BOOTSEL, flash their own firmware, and sign with the key.

## Worth watching

None of this has been brought across. Each is a thing to read before the next change to the same
part here.

- **`firmware/trustm.py`.** wedgie's copy has two fixes ours doesn't. `wait_response` waits 10 s,
  not 1 s: a factory-key signature took over a second on a real board (their note, 2026-10-11).
  And the link's frame numbers are shared by every session: with one set per session, a second
  session's reset left the first waiting out its whole timeout. Ours is still picowallet's file,
  one line apart.
- **`firmware/p256.py`.** wedgie's is verify only: "its point math is not constant-time, so signing
  here would leak the key by timing." Ours still has `sign`: the emulator's virtual chips use it, and so does the software key in
  `signer.py` that the console image ignores ([SECURITY.md](SECURITY.md)).
- **Signature checks on the Trust M.** Since 0.3.64 the wedgie checks release signatures on the
  chip: 0.2 s, where pure Python took 2.4 s.
- **`firmware/optiga.py` and [trustm.md](https://wedgie.dev/trustm.md).** The whole Trust M
  command set (ECDH, counters, protected storage, chained frames for the 1 KB certificate), with
  times measured on a real chip.
- **Clear signing.** `wire/README.md` in wedgie-dev, and `safe_7730.py` in wedgie-safe: ERC-7730
  descriptors sent ahead of the transaction, each with a Merkle proof. The host can leave one
  out, never change it.
- **A PIN the chip checks.** `docs/PLAN-PIN.md`: the Trust M's shielded connection, keyed from a
  PIN, so a flashed board can't sign. A plan there, not built.
- **`docs/PLAN-TRUST.md` and `docs/SECURITY-ROADMAP.md`.** Why a wedgie trusts what it runs, the
  holes in order, and release hashes on chain as a later stage.
- **The wiring lesson.** "Trust the order, not the colors": a STEMMA QT plug runs GND, V+, SDA,
  SCL from one end, and cables don't agree on colors (LORE.md, 2026-09-14).

## Nothing of wedgie's is in this repository

The files here that came from Austin are picowallet's, listed in
[UPSTREAM-TRACKING.md](UPSTREAM-TRACKING.md) and [NOTICE](../NOTICE). If a wedgie file or fix comes
across, it is MIT, Copyright (c) 2026 Austin Griffith: say so on the file's first line and add it
to NOTICE, as for picowallet. A change to a console-image file is a new release fingerprint.
