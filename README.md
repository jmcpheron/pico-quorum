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

- Everything inherited from picowallet: the ATECC608 driver and chip explorer, the OPTIGA Trust M
  driver and `TrustMAttest` contract, on-device keccak/EIP-712, the screen and button UI, the USB
  wallet, and the emulator.

The next milestone is [test ladder](docs/KICKOFF.md#test-ladder) rung 1: a 1-of-1 Safe on a local
fork of Base that executes a transaction after a button press.

## Layout

| path | what |
|---|---|
| `docs/` | [kickoff](docs/KICKOFF.md), [upstream tracking](docs/UPSTREAM-TRACKING.md), [Hegotá watch](docs/HEGOTA-WATCH.md), and picowallet's notes: [build guide](docs/picowallet.md), [security model](docs/SECURITY.md), [chip map](docs/CHIPMAP.md), [test plan](docs/TESTPLAN.md), [USB wallet](docs/USB.md), [clear signing](docs/CLEARSIGNING.md) |
| `hardware/` | `wiring/` ([perfboard build](hardware/wiring/SOLDERING.md)), `bom/`, `key-pcb/` |
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
