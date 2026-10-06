# PicoQuorum: Project Kickoff

> **Living draft.** The design is still changing. Edit this file as decisions get made, and move
> settled decisions out of "Open decisions" with a one-line reason.

**Repo:** https://github.com/jmcpheron/pico-quorum

A physical approval device for [Safe](https://safe.global) multisig wallets. Each signer holds a plug-in secure-element key; the console shows what a transaction does and signs only when you press Sign.

## Status

Where things stand today, with every Safe, key and address: [STATUS.md](STATUS.md). The per-chain
test steps: [LADDER.md](LADDER.md).

This kickoff is the design: what PicoQuorum is for, the hardware and firmware layers, and the
decisions still open. The hardware below (plug-in keys, the console with its guarded button and
dial) is still being built. Until it is, the **dev console** is the build picowallet started from: a
Pico 2 W, a Waveshare Pico-LCD-1.3 and an ATECC608 breakout
([DEV-CONSOLE.md](../hardware/DEV-CONSOLE.md)). Build 1, the first console with the real parts, is on
the bench ([BUILD1.md](../hardware/wiring/BUILD1.md)).

## What this is

PicoQuorum is a physical approval device for Safe multisig accounts. Each signer holds a **key**: a chunky dual plug with a secure element in its handle (an ATECC608 today; the Infineon OPTIGA Trust M is still an option, see [Open decisions](#open-decisions)). The key plugs into a **console**: a Raspberry Pi Pico–based box with a screen, a paging dial, a guarded green **Sign** button and an easy red **Reject** button, both pressed with a thumb.

The console fetches pending Safe transactions and decodes them into plain language. It computes the Safe transaction hash itself, and only then asks the key to sign. Each private key is generated inside its chip, never leaves it, and never exists as a seed phrase.

**The multisig is the star.** The console and keys exist to make distributed custody physical and understandable: several people, several keys, one Safe, and a clear, deliberate ceremony for every approval.

## Credit and upstream

This project is forked from **Austin Griffith's [picowallet](https://github.com/austintgriffith/picowallet)** (MIT): a Pico 2 W, a Waveshare Pico-LCD-1.3 and a Microchip **ATECC608** secure element. That project proved a Pico can drive a secure element from MicroPython, rebuild an EIP-712 digest on-device, show a signing request, take a button press, and return a real P-256 signature that moved funds on Ethereum mainnet. Its secure-element drivers, display and crypto helpers, and its emulator are still at the heart of this repo, credited in each file. Its single-owner vault app, its case and its notes were removed on 2026-10-06, before the repository went public; they live on in picowallet's own repository.

Upstream has since added an **OPTIGA Trust M** driver (`firmware/trustm.py`: physical and link layers, APDU session, factory-certificate read, CalcSign) and a `TrustMAttest` contract (in picowallet's repository) that proves on chain that a P-256 key lives in a real Trust M. Both were merged here on 2026-09-24, and the contract was removed with the vault app on 2026-10-06; see [`UPSTREAM-TRACKING.md`](UPSTREAM-TRACKING.md).

- [x] Add upstream link, license check, and attribution to `README.md` and `NOTICE`
- [ ] Keep the upstream secure-element drivers (`firmware/atecc.py`, `firmware/trustm.py`) and change them as little as possible
- [ ] Track upstream driver fixes (see [`UPSTREAM-TRACKING.md`](UPSTREAM-TRACKING.md))

What's different here: a multisig-first design, on-device Safe transaction decoding and hash verification, plug-in keys, a physical console design, and a provisioning ceremony that locks keys before distribution.

## Goals

- Sign real Safe transactions with a secure-element key, verified onchain
- Compute the Safe EIP-712 transaction hash on-device from the same fields shown on screen. **Never blind-sign a digest.** (Started: `firmware/safe_tx.py`, checked by `test-vectors/`.)
- Show layperson-friendly transaction details, warnings, and verification codes
- Poll Safe's transaction service over Wi-Fi, so a remote signer only needs the console and their key
- Provision, test, and lock keys in a documented ceremony before handing them out
- Keep everything open: firmware, contracts, wiring, BOM, and CAD all live in this repo

## Non-goals (for now)

- Holding meaningful funds. This is experimental hardware, so it stays on testnet or pocket change until it has a long track record.
- Tamper resistance, potting, or production enclosures
- Wallets other than Safe
- Bluetooth

## System overview

| Part | What it is |
|---|---|
| **Key** | A ¼″ stereo plug and a 3.5 mm plug, rigidly joined. The different sizes mean it only goes in one way, and it can't rotate, so the label always faces up. Inside: the secure element on a tiny PCB, a decoupling cap, and an optional glow LED behind a translucent window. |
| **Console** | Pico 2 W (preferred for secure boot), screen, rotary encoder, momentary Sign and Reject buttons, latching power switch, status LED, and a dual key socket with insertion detection. |
| **Safe side** | A Safe on Base, with each key an owner through its own SafeWebAuthnSignerProxy (Safe's audited passkey signer). The console signs a WebAuthn assertion whose challenge is the safeTxHash it computed. |

## Hardware

### Secure element

| Option | Use | Notes |
|---|---|---|
| Adafruit ATECC608 breakout (STEMMA QT) | Development now | What upstream uses; driver, chip explorer and provisioning flow already in `firmware/` |
| Bare ATECC608 (2×3 mm UDFN or SOIC-8) on a custom key PCB | Real keys, option A | Same driver as development |
| Adafruit Trust M breakout | Evaluation | `firmware/trustm.py` (from upstream) drives it; `TrustMAttest` proves the factory identity on chain |
| Bare Trust M (~3×3 mm) on a custom key PCB | Real keys, option B | Fits the plug handle on a board ~6–8 mm wide |

- [ ] Choose the chip for real keys: ATECC608 or Trust M (and which variant / firmware version)
- [ ] **Critical:** find out whether signing can be gated behind a PIN with attempt limiting. A portable key without one is a live key if stolen.
  - ATECC608: a slot can require prior authorization by a secret-derived key (CheckMac / auth key), and a monotonic counter can cap uses (LimitedUse). No built-in attempt lockout, so the limit would have to come from the counter.
  - Trust M: authorization-reference access conditions and a security event counter that throttles repeated failures.
- [ ] Document the key-slot metadata and lock / lifecycle-state procedure for the chosen chip (for the ATECC608, the config, data and slot locks are already walked through in [CHIPMAP.md](CHIPMAP.md), [LOCKING.md](LOCKING.md) and [PROVISIONING.md](PROVISIONING.md))

### Key connector: draft pinout

| Plug | Contact | Signal |
|---|---|---|
| ¼″ TRS | Tip | SDA |
| ¼″ TRS | Ring | SCL |
| ¼″ TRS | Sleeve | GND |
| 3.5 mm | Tip | VCC (3.3 V, console-switched) |
| 3.5 mm | Ring | Spare |
| 3.5 mm | Sleeve | GND |

Build 1 tries a 3.5 mm + 2.5 mm TRRS pair instead (8 contacts: DETECT, key RST and an ID line fit):
[hardware/wiring/BUILD1.md](../hardware/wiring/BUILD1.md).

The key PCB's rev A, being prototyped, drops the plugs: **the PCB is the plug.** The board has gold
fingers on one edge and goes into a card-edge socket. Fingers of different lengths do the
sequencing in copper (GND first, DETECT last), a slot keys it, and it uses Build 1's GPIOs. See
[hardware/key-pcb](../hardware/key-pcb/README.md).

Design rules:

- The shorter 3.5 mm plug mates last and breaks first, which sequences power mechanically.
- The console enables key power **only** after the switched jack's detect contact confirms full insertion, and cuts it immediately on removal.
- Key VCC gets a current-limited load switch, so a stray headphone or guitar cable can't do damage.
- SDA, SCL, and VCC get ESD/TVS protection at the jacks.
- I2C pull-ups live on the console side.
- Both jacks mount on one rigid bracket or PCB. One plug on the key gets slight float so it self-aligns.

### Controls

- **Sign:** momentary push button on a green panel, with a raised guard or flip-up cover so it's hard to press by accident. Hold for ~2 s while an on-screen progress bar fills.
- **Reject:** momentary push button, unguarded and instant. Saying no should always be easy.
- **Placement:** buttons sit where thumbs land, with on-screen labels directly beside or above each one (for example, "SIGN" in the screen's upper right next to the green button, "REJECT" lower down). Layout TBD in CAD.
- **Navigation:** rotary encoder with push. Turn to page; push to return to the summary.
- **Power:** latching switch. The 3PDT stomp switch gag from the upstream case is welcome here.
- **Status LED:** blinks when a transaction is pending.
- Optional: detect the flip cover opening as an "arm" signal.

On the dev console: A (top of the column, green bar) is Sign, held 2 s; Y (bottom, red bar) is Reject; the joystick pages.

### Screen candidates

- [ ] 2.0″ 320×240 SPI LCD (Pico-compatible)
- [ ] 2.8″ 320×240 (Pico-compatible; touch optional and probably unused)
- [ ] Compare how readable long addresses are, how well QR codes scan, and power draw
- [ ] Ordered 2026-09-24: a 6-pack of SPI panels (0.96″ 80×160 and 1.8″ 128×160 ST7735S; 2.0″, 2.4″ and
  2.8″ 240×320 ST7789; 3.5″ 320×480 ST7796). How the approval flow reflows on each, and the order of
  work: [quorum-ui/SCREENS.md](quorum-ui/SCREENS.md)

## Safe integration: firmware layers

1. **Secure-element driver**, inherited from upstream: `firmware/atecc.py` and `firmware/trustm.py`.
2. **Safe hash:** EIP-712 domain (chain ID and Safe address) plus the SafeTx struct, with Keccak computed on-device. Golden test vectors live in `test-vectors/`, and every change must pass all of them. *(Done: `firmware/safe_tx.py`.)*
3. **Signature packaging** into the format the owner contract expects: a WebAuthn assertion inside a Safe contract signature. *(Done: `firmware/webauthn.py`.)*
4. **Transaction service client:** list pending transactions and post confirmations, with the API key kept in config.
5. **Decoder and display:** plain-language actions, warnings, and verification pages.

## Screen content

- **Summary:** Safe nickname; chain name with a color band; short Safe address; nonce shown as "transaction #N"; approval status such as "1 of 3 so far, you'd be #2"; who has signed, using a local address book.
- **Action:** plain English ("Send 1.5 ETH to …"). Token amounts use proper decimals from a built-in token list. Known addresses show address-book names. Unknown addresses appear in 4-character chunks with a first-time-recipient flag. Batched actions are unpacked one per page.
- **Warnings (red screens):** owner add, remove, or swap; threshold change; module or guard changes; delegatecall; nonzero gas-refund fields; undecodable calls ("Don't sign unless you were told exactly what to expect").
- **Verify:** the last 8 characters of the Safe transaction hash in large type, for phone-call confirmation. Also three QR codes: the full hash, the signature (for air-gapped fallback), and the owner address (for setup).

## Test ladder

Tracked in [LADDER.md](LADDER.md): each rung's status, the commands, the evidence, and the checklist
before real money.

1. **Local:** an Anvil fork of Base on the laptop, plus a mock transaction service that implements only the endpoints the console uses (`tools/quorum up`). The console connects over home Wi-Fi. The fork runs as chain 31337, so nothing signed on it is valid on real Base. Milestone: a Safe executes after a button press. *(Done with the emulator's chip, `tools/quorum e2e`; the real Pico is next.)*
2. **Base Sepolia:** the real Safe web app and transaction service. Milestone: a 2-of-3 with one browser wallet and two consoles.
3. **Base mainnet with pocket change:** a remote signer on their own Wi-Fi. Milestone: a real remote approval.
4. **Ethereum mainnet with pocket change:** the same approval on L1. The passkey signer, the P-256 precompile (Fusaka) and Safe's service are all there, and an execution costs about a cent at 2026 gas.

## Provisioning ceremony (outline)

1. Verify each chip's factory identity (Infineon certificate for Trust M; Microchip Trust&Go certificate or the serial number for ATECC608), and discard any failures.
2. Generate a signing key in an application key slot, and have the factory identity key sign a statement binding that key to the chip.
3. **Test before locking:** create a throwaway testnet Safe, sign with every key, and run a rotation drill.
4. Lock the key-slot metadata and advance the chip's lifecycle state. This is irreversible.
5. Deploy owner contracts at deterministic addresses and check them against the provisioning records.
6. Assemble each key, label it with its fingerprint, and hand it out with an instruction card.

## Target multisig shape (for reference)

A 3-of-5 where no single technology holds more than two keys: a warm wallet (proposes transactions and pays gas), a conventional hardware wallet off-site, two PicoQuorum keys held by trusted people, and a paper seed sealed with a lawyer. More keys can move to PicoQuorum only after the hardware earns trust.

## Repo layout

```
docs/            kickoff, security model, provisioning ceremony, signer instructions, the owner's guide
hardware/
  DEV-CONSOLE.md the no-solder dev console
  wiring/        console and key schematics, pinouts (SOLDERING.md: the dev console's perfboard)
  bom/           parts lists and sourcing notes
  key-pcb/       key board design
firmware/        MicroPython (upstream drivers plus Safe layers; safe_tx.py so far)
contracts/       PicoQuorum's own contracts, when there are any
tools/           mock transaction service, provisioning scripts, vector generator, emulator and board tools
test-vectors/    Safe transactions with known-correct hashes
```

These live outside the kickoff layout:
- `emu/`: the console in a browser.
- `web/`: the app's source.
- `buildlog/`: dated notes and photos.

## First parts order

See [`hardware/bom/README.md`](../hardware/bom/README.md).

## Open decisions

- [ ] Secure element for real keys: ATECC608 (driver here) vs Trust M (driver and on-chain attestation upstream)
- [x] WebAuthn-shaped signatures vs. a custom ERC-1271 signer: Safe's passkey signer, one SafeWebAuthnSignerProxy per key, verifiers = the P-256 precompile then Daimo. No contract of our own. (Safe's unreleased native P-256 owners could replace the proxy later; the packaging is all in `webauthn.py`.)
  - Keep the format reusable by Hegotá frame transactions; see [Hegotá watch](HEGOTA-WATCH.md). A WebAuthn assertion is what a P-256 validation frame would check too, so the chip signs nothing new.
- [ ] Whether a PIN/authorization is feasible on the chosen chip
- [ ] Screen size
- [ ] Button choice and layout (beside the screen vs. below it)
- [ ] Flip cover vs. guard fence
- [ ] Printed vs. aluminum enclosure
- [ ] Faceplate name: "PicoQuorum" or just "Quorum"
- [x] When to prune the inherited single-token code: done 2026-10-06 (`app/` ChipAccount/USDS, the Waveshare case, the Pi signer)
