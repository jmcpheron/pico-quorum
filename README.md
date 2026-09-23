# PicoQuorum

A thumb-operated hardware signer for [Safe](https://safe.global) multisig wallets. Each person
holds a key with a secure element in it. The console fetches the pending Safe transaction and
decodes it into plain language. It computes the Safe transaction hash itself from the fields it
shows, and signs only when you hold the green button. The private key is generated inside the chip,
never leaves it, and never exists as a seed phrase.

**The multisig is the star.** Several people, several keys, one Safe, and a deliberate ceremony for
every approval. The plan, the hardware and the open questions are in the
[kickoff](docs/KICKOFF.md).

> **Experimental.** Testnet and pocket change only. Nothing here has a track record yet.

## Where it stands

The plug-in keys and the console hardware are still on paper. The **dev console** is the picowallet
this repo forked: a Pico 2 W, a Waveshare Pico-LCD-1.3 and an ATECC608 breakout, about $35 with no
soldering ([build guide](docs/picowallet.md), [parts](hardware/bom/README.md)).

The current milestone is test ladder rung 1: a 1-of-1 Safe on a local fork of Base. The chip's
P-256 key is registered as the Safe's owner through Safe's audited passkey (WebAuthn) signer. The
milestone is met when that Safe executes a transaction after a button press.

## Rung 1, locally

Prerequisites:
- [Foundry](https://getfoundry.sh) (`forge`, `anvil`, `cast`)
- Node 20+ and [uv](https://docs.astral.sh/uv/)
- `BASE_RPC_URL`: any Base mainnet RPC. The public `https://mainnet.base.org` works for light use.

```sh
tools/quorum fork                           # terminal 1: anvil forking Base, as chain 31337
tools/quorum serve --auto-exec              # terminal 2: the mock Safe transaction service
tools/emu chip ready                        # a provisioned virtual ATECC608 in the emulator
tools/quorum safe --from-emu                # signer + 1-of-1 Safe for that key, funded with 1 ETH
tools/emu --mode safe                       # the dev console, running firmware/quorum.py
tools/quorum propose send 0.01 ETH to 0x000000000000000000000000000000000000dEaD
```

The console shows the Safe, the action, any red warnings, and the last 8 characters of the hash.
Hold **A** for 2 s to sign; **Y** rejects. The mock checks the signature on the fork and executes
the Safe transaction. For the real board, use `tools/quorum safe --from-pico` and put the printed
lines in `firmware/secrets.py`.

`tools/check` runs every test:
- the golden vectors, certified against Safe's deployed contracts on a Base fork
- the firmware's hash and signature code against the same vectors, under CPython and under the
  emulator's MicroPython
- the mock service's tests

## Layout

| path | what |
|---|---|
| `docs/` | [kickoff](docs/KICKOFF.md), [security model](docs/SECURITY.md), the picowallet [build guide](docs/picowallet.md), [chip map](docs/CHIPMAP.md), [test plan](docs/TESTPLAN.md), [upstream notes](docs/UPSTREAM.md) |
| `hardware/` | `wiring/` ([perfboard build](hardware/wiring/SOLDERING.md)), `bom/`, `key-pcb/` |
| `cad/` | `console/` (the dev console's case, generators and measurements), `key/` |
| `firmware/` | MicroPython for the Pico. `quorum.py` is the Safe app; `safetx.py`, `webauthn.py`, `decode.py` are its layers; `atecc.py` and `signer.py` are the chip; `wallet.py` is picowallet's vault app |
| `contracts/` | Foundry: interfaces to Safe's deployed contracts, vector generation, fork tests, the local Safe script |
| `test-vectors/` | Safe transaction hashes, WebAuthn signatures and decoder cases with known-correct answers |
| `tools/` | `quorum` and `mock-tx-service/` (the local Safe setup), `vectors`, `check`, `emu` (the virtual dev console), `usb`/`push`/`pico` (the real board), the case generators |
| `emu/` | the virtual dev console: MicroPython in WebAssembly, a virtual ATECC608, the case in 3D |
| `app/` | picowallet's single-owner vault app (Scaffold-ETH 2) |
| `buildlog/` | dated notes and photos, including the mistakes |
| `reference/` | the Pi signer picowallet grew out of; SeedSigner cap parts |

## Credit

PicoQuorum is a fork of [picowallet](https://github.com/austintgriffith/picowallet) by
**Austin Griffith**. picowallet proved that a Pico can drive an ATECC608 from MicroPython, rebuild
an EIP-712 digest on the device, and sign with a key that never leaves the chip, all on mainnet with
an audited vault. The chip driver is still upstream's, and fixes go back upstream
([docs/UPSTREAM.md](docs/UPSTREAM.md)). Case parts by Tomáš Plass and Zez0000 (CC BY-NC).
Everything else is attributed in [NOTICE](NOTICE).

## License

MIT (see [LICENSE](LICENSE)) except where [NOTICE](NOTICE) says otherwise: the case STLs are
CC BY-NC.
