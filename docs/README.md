# docs

**The site's front page is [`index.html`](index.html); execute a Safe transaction, or check a key, in [the app](app/)** (both built from [`web/`](../web/README.md); the key list is [`registry/`](registry/README.md)).

**Owners start at [`guide/`](guide/README.md)**: setting up a console, using it, networks, and
troubleshooting.

- [`guide/`](guide/README.md): the owner's guide ([setup](guide/SETUP.md), [using it](guide/USING.md),
  [networks](guide/NETWORKS.md), [troubleshooting](guide/TROUBLESHOOTING.md), [the console in your
  browser](guide/BROWSER.md))
- [`STATUS.md`](STATUS.md): **what exists today**: the name and domains, every Safe, key and address, the
  contracts the console relies on, and what's next
- [`RELEASES.md`](RELEASES.md): firmware versions (year.month.n), what each holds, and how to make one
- [`mainnet/`](mainnet/README.md): a Trust M signer in a mainnet Safe. Written for co-signers too: checking a chip, the threat model, the recommended configuration, the operator's runbook
- [`SECURITY.md`](SECURITY.md): how to report a vulnerability, and the console's trust model
- [`PROVISIONING.md`](PROVISIONING.md): the quorum v1 chip config and the fresh-chip ceremony
- [`LOCKING.md`](LOCKING.md): what each ATECC608 lock does to the multisig
- [`BRANDED-KEYS.md`](BRANDED-KEYS.md): a proposal: the bench brands each chip, the user's console makes its key
- [`ATTESTED-KEYS.md`](ATTESTED-KEYS.md): a proposal: an attestation key per chip, so a key can prove it is in a branded chip; the gas relay, its treasury and picoquorum.eth on top
- [`LADDER.md`](LADDER.md): the test ladder from a simulated Safe to Ethereum mainnet, and the `tools/quorum live` runbook
- [`firmware-production/`](firmware-production/README.md) and [`quorum-ui/`](quorum-ui/README.md): screenshot walkthroughs
- [`KICKOFF.md`](KICKOFF.md): what PicoQuorum is, goals, hardware, firmware layers, open decisions
- [`UPSTREAM-TRACKING.md`](UPSTREAM-TRACKING.md): what came from picowallet, and how its fixes come across
- [`HEGOTA-WATCH.md`](HEGOTA-WATCH.md): EIPs in the next Ethereum fork that touch the console
- [`EMU-WEB.md`](EMU-WEB.md): the console on GitHub Pages, with your own passkey as the key: the design, and its limits
- [`GOVERNANCE.md`](GOVERNANCE.md): the project Safe (Ethereum and Base), release approvals, the ENS name, and handing it over
- [`TRUSTM.md`](TRUSTM.md): the Trust M profile, its ceremony, and TM1 and TM2
- [`releases/`](releases/README.md): the release fingerprint, and each release's manifest
- [`BRAND.md`](BRAND.md): the name, the mark and the colours ([`TRADEMARK.md`](../TRADEMARK.md) for what you may do with them)
- [`upstream/`](upstream/README.md): issues and fixes PicoQuorum sends to other projects (Safe{Wallet})

The dev console: its [build guide](../hardware/DEV-CONSOLE.md), and [`CHIPMAP.md`](CHIPMAP.md), the
chip map on the ceremony image. PicoQuorum grew from Austin Griffith's
[picowallet](https://github.com/austintgriffith/picowallet); what came from it, and how its fixes
come across, is in [`UPSTREAM-TRACKING.md`](UPSTREAM-TRACKING.md).

