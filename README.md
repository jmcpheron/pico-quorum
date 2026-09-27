# PicoQuorum

A physical approval device for [Safe](https://safe.global) multisig wallets. Each signer holds a
plug-in secure-element key; the console shows what a transaction does and signs only when you
press Sign.

The **key** is a ¼″ + 3.5 mm dual plug with a secure element in its handle. It plugs into a
**console**: a Pico 2 W with a screen, a paging dial, a guarded green **Sign** button and an easy
red **Reject** button. The console fetches pending Safe transactions, decodes them into plain
language, computes the Safe transaction hash itself from the fields it shows, and only then asks
the key to sign. The private key is generated inside the chip, never leaves it, and never exists as
a seed phrase.

**The multisig is the star.** Several people, several keys, one Safe, and a deliberate ceremony for
every approval. The plan, the hardware and the open questions are in the
[kickoff](docs/KICKOFF.md), a living draft.

> **Experimental.** Early design, testnet and pocket change only. Nothing here has a track record
> yet.

## Where it stands

The plug-in keys and the console hardware are still on paper. The **dev console** is the picowallet
this repo forked: a Pico 2 W, a Waveshare Pico-LCD-1.3 and an ATECC608 breakout, about $35 with no
soldering ([build guide](docs/picowallet.md), [parts](hardware/bom/README.md)).

What works so far:

- `firmware/safe_tx.py` computes the Safe (≥ 1.3.0) EIP-712 transaction hash on-device from the
  raw fields, plus the 8-character verify code. It passes every vector in
  [`test-vectors/`](test-vectors/), including real mainnet Safe transactions, on CPython and on
  MicroPython 1.26:

  ```sh
  python3 test-vectors/run.py
  ```

- **The console** (`firmware/quorum.py`, `quorum_ui.py`, `decode.py`, `txservice.py`):
  - It polls the transaction service, decodes each transaction into plain language with red pages
    for the dangerous ones, and refuses any transaction whose hash or Safe the service lies about.
  - It signs with the chip after you hold A. See the [screenshot walkthrough](docs/quorum-ui/README.md).
  - It ran on the real Pico on 2026-09-24.
- **The chip as a Safe owner** (`firmware/webauthn.py`):
  - Each key owns the Safe through Safe's audited passkey signer.
  - The console computes its own owner address, and signs a WebAuthn assertion over the safeTxHash
    it computed itself.
  - This is checked against the deployed contracts on Base Sepolia.
- **A real Safe on the laptop:**
  - `tools/quorum up` runs a Safe 1.4.1 on an Anvil fork of Base. The chip's approvals execute
    there.
  - `tools/quorum e2e` runs a whole approval with the emulator, no hardware
    ([details](tools/mock-tx-service/README.md)).
- Everything inherited from picowallet: the ATECC608 driver and chip explorer, the OPTIGA Trust M
  driver and `TrustMAttest` contract, on-device keccak/EIP-712, the screen and button UI, the USB
  wallet, and the emulator.

Next is the [test ladder](docs/LADDER.md), which tracks each step:
- rung 1 with the real Pico on the fork
- Base Sepolia with the Safe web app
- Base with a few dollars
- then Ethereum mainnet

## Layout

| path | what |
|---|---|
| `docs/` | [kickoff](docs/KICKOFF.md), [test ladder](docs/LADDER.md), [locking the chip](docs/LOCKING.md), [upstream tracking](docs/UPSTREAM-TRACKING.md), [Hegotá watch](docs/HEGOTA-WATCH.md), and picowallet's notes: [build guide](docs/picowallet.md), [security model](docs/SECURITY.md), [chip map](docs/CHIPMAP.md), [test plan](docs/TESTPLAN.md), [USB wallet](docs/USB.md), [clear signing](docs/CLEARSIGNING.md) |
| `hardware/` | [Build 1 handoff](hardware/HANDOFF.md), `wiring/` ([perfboard build](hardware/wiring/SOLDERING.md), [Build 1](hardware/wiring/BUILD1.md), [on a breadboard](hardware/wiring/BREADBOARD.md)), `bom/`, `key-pcb/` |
| `cad/` | `console/` (today the dev console's case, generators and measurements), `key/` |
| `firmware/` | MicroPython for the Pico: `safe_tx.py` (new), and picowallet's `wallet.py`, `usbwallet.py`, `atecc.py`, `trustm.py`, `signer.py` and crypto |
| `test-vectors/` | Safe transactions with known-correct hashes, and their runners |
| `contracts/` | the Safe P-256 owner contract (to come) |
| `tools/` | `vectors/` (the vector generator), `emu` (the virtual dev console), `usb`/`push`/`pico` (the real board), `check_config`, the case generators |
| `emu/` | the virtual dev console: MicroPython in WebAssembly, a virtual ATECC608, the case in 3D |
| `app/` | picowallet's single-owner vault app (Scaffold-ETH 2), with `TrustMAttest` |
| `buildlog/` | dated notes and photos, including the mistakes |
| `reference/` | the Pi signer picowallet grew out of; SeedSigner cap parts |

## Credit

PicoQuorum is a fork of [picowallet](https://github.com/austintgriffith/picowallet) by
**Austin Griffith** (MIT). picowallet proved that a Pico can drive a secure element from
MicroPython, rebuild an EIP-712 digest on the device, and sign with a key that never leaves the
chip, all on mainnet with an audited vault. The chip drivers are still upstream's, and fixes go
back upstream ([docs/UPSTREAM-TRACKING.md](docs/UPSTREAM-TRACKING.md)). Case parts by Tomáš Plass
and Zez0000 (CC BY-NC). Everything else is attributed in [NOTICE](NOTICE).

## License

MIT (see [LICENSE](LICENSE)) except where [NOTICE](NOTICE) says otherwise: the case STLs are
CC BY-NC.
