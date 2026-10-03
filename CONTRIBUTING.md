# Contributing

Start with the [principles](PRINCIPLES.md). They decide what gets built and what doesn't. Then pick
whichever of these fits.

> **Experimental.** Testnet and pocket change only. Don't put money you can't lose behind a console
> or a key from this repo.

## Try it with no hardware

Everything below runs on a laptop. You need Python 3 and Node.

```sh
python3 test-vectors/run.py     # the Safe hash, on CPython
tools/emu                       # the virtual dev console, with a virtual ATECC608
tools/quorum e2e                # one whole approval: a Safe on an Anvil fork of Base, the emulator signs
```

`tools/quorum e2e` needs [Foundry](https://getfoundry.sh)'s Anvil; `tools/quorum doctor` checks
what's missing. The details are in [tools/mock-tx-service](tools/mock-tx-service/README.md) and
[emu/README.md](emu/README.md).

## Build a dev console

A Pico 2 W, a Waveshare Pico-LCD-1.3 and an ATECC608 breakout cost about $35, with no soldering.
See the [build guide](docs/picowallet.md), the [parts](hardware/bom/README.md) and the
[owner's guide](docs/guide/README.md).

## Rules every change keeps

- **Every vector passes.** A change near the hash, the decoder or the signature passes
  `python3 test-vectors/run.py` and `node test-vectors/run-micropython.mjs`
  ([test-vectors/](test-vectors/README.md)). Expected values come from the generators, never from
  the firmware, and nobody edits them by hand.
- **Nothing signs a digest the console didn't compute** from the fields it showed.
- **The chip drivers barely change.** `firmware/atecc.py` and `firmware/trustm.py` are upstream's.
  Fixes go back to [picowallet](https://github.com/austintgriffith/picowallet) first
  ([UPSTREAM-TRACKING.md](docs/UPSTREAM-TRACKING.md)).
- **No new contracts** while an audited one will do.
- **Say what isn't protected.** A change that opens or closes a gap updates
  [SECURITY.md](docs/SECURITY.md).

## Write it down

- Work on the bench gets a dated entry in [buildlog/](buildlog/), mistakes included. A failed
  attempt written down saves the next person a weekend.
- Docs follow the voice in [BRAND.md](docs/BRAND.md#voice): short sentences, plain words, "3 of 5"
  rather than "3/5", and no exclamation marks.
- A decision gets moved out of "Open decisions" in the [kickoff](docs/KICKOFF.md) with a one-line
  reason.

## Hardware

- Change the boards through their generators and checks: `tools/keypcb check | fab | render` for
  the [key PCB](hardware/key-pcb/README.md), and the generators in [cad/](cad/) for the case. Once
  a board has been edited by hand in KiCad, keep editing it by hand
  ([ORDERING.md](hardware/key-pcb/ORDERING.md)).
- Commit the generated outputs (gerbers, BOM, CPL, renders, STLs) with the source, so anyone can
  order from any commit.

## Join a batch

Group orders for keys and boards are announced as GitHub issues. How they work, and what each kind
of parts source can promise, is in [hardware/SOURCING.md](hardware/SOURCING.md). If you run a fab,
a test lab, a co-op or a certificate authority and want to help, open an issue.

## Licences

Each contribution goes in under the licence of the directory it touches:

| what | licence |
|---|---|
| firmware, tools, emulator, app, docs | MIT ([LICENSE](LICENSE)) |
| `hardware/` and `cad/key/` | CERN-OHL-S-2.0 ([hardware/LICENSE](hardware/LICENSE)) |
| the borrowed case parts in `cad/console/` | CC BY-NC, as attributed in [NOTICE](NOTICE) |

Don't add parts with a non-commercial or no-derivatives licence outside `cad/console/`. They'd
block the batches.
