# docs

**The site's front page is [`index.html`](index.html); execute a Safe transaction, or check a key, in [the app](app/)** (both built from [`web/`](../web/README.md); the key list is [`registry/`](registry/README.md)).

**Owners start at [`guide/`](guide/README.md)**: setting up a console, using it, networks, and
troubleshooting.

- [`guide/`](guide/README.md): the owner's guide ([setup](guide/SETUP.md), [using it](guide/USING.md),
  [networks](guide/NETWORKS.md), [troubleshooting](guide/TROUBLESHOOTING.md))
- [`RELEASES.md`](RELEASES.md): firmware versions (year.month.n), what each holds, and how to make one
- [`mainnet/`](mainnet/README.md): a Trust M signer in a mainnet Safe. Written for co-signers too: checking a chip, the threat model, the recommended configuration, the operator's runbook
- [`SECURITY.md`](SECURITY.md): the console's trust model, then picowallet's
- [`PROVISIONING.md`](PROVISIONING.md): the quorum v1 chip config and the fresh-chip ceremony
- [`BRANDKEY.md`](BRANDKEY.md): branded keys, a design: a brand key beside the Safe key (quorum-v2), the bench
  and home ceremonies, the registry and the PicoQuorum Safe; figures in [`brandkey/`](brandkey/)
- [`LOCKING.md`](LOCKING.md): what each ATECC608 lock does to the multisig
- [`LADDER.md`](LADDER.md): the test ladder from a simulated Safe to Ethereum mainnet, and the `tools/quorum live` runbook
- [`firmware-production/`](firmware-production/README.md) and [`quorum-ui/`](quorum-ui/README.md): screenshot walkthroughs
- [`KICKOFF.md`](KICKOFF.md): what PicoQuorum is, goals, hardware, firmware layers, open decisions
- [`UPSTREAM-TRACKING.md`](UPSTREAM-TRACKING.md): fork point, unmerged upstream work, how to merge
- [`HEGOTA-WATCH.md`](HEGOTA-WATCH.md): EIPs in the next Ethereum fork that touch the console

The dev console's notes, from picowallet: [`picowallet.md`](picowallet.md) (build guide),
[`CHIPMAP.md`](CHIPMAP.md), [`TESTPLAN.md`](TESTPLAN.md), [`USB.md`](USB.md),
[`CLEARSIGNING.md`](CLEARSIGNING.md), [`HANDOFF.md`](HANDOFF.md),
[`PLAN-picowallet.md`](PLAN-picowallet.md), and the upstream notes [`UPSTREAM.md`](UPSTREAM.md) and
[`UPSTREAM-ISSUE.md`](UPSTREAM-ISSUE.md).

