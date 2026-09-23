# PicoQuorum: Project Kickoff

**Repo:** https://github.com/jmcpheron/pico-quorum

A thumb-operated hardware signer for [Safe](https://safe.global) multisig wallets, with secure-element keys that plug in like guitar cables.

## Status (2026-09-22)

The hardware in the kickoff (plug-in keys, the console with its guarded button and dial) doesn't exist yet. Until
it does, the **dev console** is the picowallet this repo forked: a Pico 2 W, a Waveshare Pico-LCD-1.3 (240×240,
joystick, A/B/X/Y) and an Adafruit ATECC608 breakout. Its build guide is [picowallet.md](picowallet.md).
On the dev console, holding **A** for 2 s signs, **Y** rejects, and the joystick pages.

| Layer | Where it lives | State |
|---|---|---|
| 1. Secure-element driver | `firmware/atecc.py` (upstream), behind the backends in `firmware/signer.py` | works; a Trust M backend would be one more class in `signer.py` |
| 2. Safe hash | `firmware/safetx.py`, checked against `test-vectors/safe-tx/` | rung 1 |
| 3. Signature packaging | `firmware/webauthn.py`: WebAuthn-shaped, for Safe's passkey signer | rung 1 |
| 4. Transaction service client | `firmware/quorum.py`; the mock service is `tools/mock-tx-service/` | rung 1 (mock only) |
| 5. Decoder and display | `firmware/decode.py`, `firmware/quorum.py` | rung 1 |
| Contracts | `contracts/`: Foundry, fork tests against Safe's deployed contracts on Base | rung 1 |

[Test ladder](#test-ladder) rung 1 is the current milestone.

## What this is

PicoQuorum is a physical approval device for Safe multisig accounts. Each signer holds a **key**: a chunky dual plug with a secure element in its handle. The key plugs into a **console**: a Raspberry Pi Pico–based box with a screen, a paging dial, a guarded green **Sign** button and an easy red **Reject** button, both pressed with a thumb.

The console fetches pending Safe transactions and decodes them into plain language. It computes the Safe transaction hash itself, and only then asks the key to sign. Each private key is generated inside its chip, never leaves it, and never exists as a seed phrase.

**The multisig is the star.** The console and keys exist to make distributed custody physical and understandable: several people, several keys, one Safe, and a clear, deliberate ceremony for every approval.

## Credit and upstream

This project is a fork of **Austin Griffith's** [picowallet](https://github.com/austintgriffith/picowallet): a Pico 2 W, a Waveshare Pico-LCD-1.3, and a Microchip **ATECC608** secure element. picowallet proved several things:

- A Pico can drive an ATECC608 from MicroPython.
- It can rebuild an EIP-712 digest on the device from the same fields it shows.
- It can take a button press and return a real P-256 signature from a key generated inside the chip.
- It moved real money on Ethereum mainnet through its audited `ChipAccount` vault.

An earlier draft of this kickoff credited a "Pico + Trust M" project. That was wrong: upstream uses an ATECC608 and has no Trust M code.

- [x] Add upstream link, license check (MIT, © 2026 Austin Griffith, kept in `LICENSE`), and attribution to `README.md` and `NOTICE`
- [x] Upstream driver: `firmware/atecc.py` is upstream's own driver, in-tree because this repo is a fork. Change it as little as possible. The one real fix, the config table, is written up for Austin in [UPSTREAM.md](UPSTREAM.md).
- [ ] Track upstream driver fixes ([UPSTREAM.md](UPSTREAM.md), "Tracking upstream")

What's different here: a multisig-first design, on-device Safe transaction decoding and hash verification, plug-in keys, a physical console design, and a provisioning ceremony that locks keys before distribution.

## Goals

- Sign real Safe transactions with a secure-element key, verified onchain
- Compute the Safe EIP-712 transaction hash on-device from the same fields shown on screen. **Never blind-sign a digest.**
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
| **Safe side** | A Safe on Base, with each key registered as an owner through a P-256 signer contract. Try Safe's audited WebAuthn/passkey signer path first; fall back to a custom ERC-1271 signer. |

## Hardware

### Secure element

| Option | Use | Notes |
|---|---|---|
| Adafruit ATECC608 breakout (4314) | Development now | Driver in-tree (`firmware/atecc.py`), a virtual one in the emulator. Three P-256 key slots (0, 2, 7) under the wallet config. No factory certificate on this part. |
| Adafruit Trust M breakout | Evaluation | Has an Infineon factory certificate. No MicroPython driver yet. |
| Bare Trust M on a custom key PCB | Real keys | ~3×3 mm chip on a board ~6–8 mm wide, fits in the plug handle |

- [ ] Choose which Trust M variant and firmware version to standardize on
- [ ] **Critical:** find out whether authorization access conditions can gate signing behind a PIN with attempt limiting. A portable key without one is a live key if stolen. Ask this of both chips: the Trust M's authorization-reference access conditions, and the ATECC608's `ReqAuth`/`AuthKey` slot rules plus its monotonic counters.
- [ ] Document the key-slot metadata and lifecycle-state locking procedure. For the ATECC608, the config, data and slot locks are already walked through in [CHIPMAP.md](CHIPMAP.md).

### Key connector: draft pinout

| Plug | Contact | Signal |
|---|---|---|
| ¼″ TRS | Tip | SDA |
| ¼″ TRS | Ring | SCL |
| ¼″ TRS | Sleeve | GND |
| 3.5 mm | Tip | VCC (3.3 V, console-switched) |
| 3.5 mm | Ring | Spare |
| 3.5 mm | Sleeve | GND |

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

## Safe integration: firmware layers

1. **Secure-element driver**, inherited from upstream (`firmware/atecc.py`) and reached through `firmware/signer.py`.
2. **Safe hash:** EIP-712 domain (chain ID and Safe address) plus the SafeTx struct, with Keccak computed on-device. Golden test vectors live in `test-vectors/`, and every change must pass all of them (`tools/check`).
3. **Signature packaging** into the format the owner contract expects (WebAuthn-shaped for Safe's passkey signer; custom ERC-1271 only if that path fails).
4. **Transaction service client:** list pending transactions and post confirmations, with the API key kept in config.
5. **Decoder and display:** plain-language actions, warnings, and verification pages.

## Screen content

- **Summary:** Safe nickname; chain name with a color band; short Safe address; nonce shown as "transaction #N"; approval status such as "1 of 3 so far, you'd be #2"; who has signed, using a local address book.
- **Action:** plain English ("Send 1.5 ETH to …"). Token amounts use proper decimals from a built-in token list. Known addresses show address-book names. Unknown addresses appear in 4-character chunks with a first-time-recipient flag. Batched actions are unpacked one per page.
- **Warnings (red screens):** owner add, remove, or swap; threshold change; module or guard changes; delegatecall; nonzero gas-refund fields; undecodable calls (you should be told exactly what to expect).
- **Verify:** the last 8 characters of the Safe transaction hash in large type, for phone-call confirmation. Also three QR codes: the full hash, the signature (for air-gapped fallback), and the owner address (for setup).

## Test ladder

1. **Local:** an Anvil fork of Base on the laptop, plus a mock transaction service that implements only the endpoints the console uses. The console connects over home Wi-Fi. The fork runs as chain 31337, so nothing signed on it is valid on real Base. Milestone: a 1-of-1 Safe executes after a button press.
2. **Base Sepolia:** the real Safe web app and transaction service. Milestone: a 2-of-3 with one browser wallet and two consoles.
3. **Base mainnet with pocket change:** a remote signer on their own Wi-Fi. Milestone: a real remote approval.

## Provisioning ceremony (outline)

1. Verify each chip's factory certificate (Trust M), and discard any failures.
2. Generate a signing key in an application key slot, and have the factory identity key sign a statement binding that key to the chip.
3. **Test before locking:** create a throwaway testnet Safe, sign with every key, and run a rotation drill.
4. Lock the key-slot metadata and advance the chip's lifecycle state. This is irreversible.
5. Deploy owner contracts at deterministic addresses and check them against the provisioning records.
6. Assemble each key, label it with its fingerprint, and hand it out with an instruction card.

## Target multisig shape (for reference)

A 3-of-5 where no single technology holds more than two keys: a warm wallet (proposes transactions and pays gas), a conventional hardware wallet off-site, two PicoQuorum keys held by trusted people, and a paper seed sealed with a lawyer. More keys can move to PicoQuorum only after the hardware earns trust.

## Repo layout

```
docs/            kickoff, security model, provisioning ceremony, signer instructions, the picowallet notes
hardware/
  wiring/        console and key schematics, pinouts (SOLDERING.md: the dev console's perfboard)
  bom/           parts lists and sourcing notes
  key-pcb/       key board design
cad/
  console/       enclosure, button guard or cover, jack bracket (today: the dev console's case)
  key/           plug handle, end cap, label band
firmware/        MicroPython (upstream-derived driver plus Safe layers)
contracts/       Foundry project: signer setup, fork tests, deploy scripts
tools/           mock transaction service, provisioning scripts, emulator and board tools
test-vectors/    Safe transactions with known-correct hashes
```

These live outside the kickoff layout:
- `app/`: picowallet's Scaffold-ETH app for the single-owner vault. Its Foundry package can't leave the workspace without breaking `yarn deploy`.
- `emu/`: the virtual dev console.
- `buildlog/`: dated notes and photos.
- `reference/`: the Pi signer picowallet grew out of.

## First parts order

- Raspberry Pi Pico 2 W (×2)
- Adafruit Trust M breakout (×2–3)
- Momentary push buttons, thumb-sized, in green and red (a few candidates to compare feel)
- Flip-up switch cover or guard hardware
- ¼″ stereo plugs (solder type) and ¼″ stereo switched jacks, with extras
- 3.5 mm plugs (solder type) and 3.5 mm switched jacks, with extras
- Rotary encoder with push switch
- 2.0″ and 2.8″ 320×240 screens, one each to compare
- Load-switch and ESD/TVS parts, or breakouts for prototyping
- Status LEDs and assorted resistors and capacitors

The dev console's parts are in [hardware/bom](../hardware/bom/README.md).

## Open decisions

- [ ] WebAuthn-shaped signatures vs. a custom ERC-1271 signer (rung 1 tries Safe's passkey signer, v0.2.1)
- [ ] Whether a PIN/authorization is feasible on the Trust M (and on the ATECC608)
- [ ] Screen size
- [ ] Button choice and layout (beside the screen vs. below it)
- [ ] Flip cover vs. guard fence
- [ ] Printed vs. aluminum enclosure
- [ ] Faceplate name: "PicoQuorum" or just "Quorum"
