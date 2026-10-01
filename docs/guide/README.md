# PicoQuorum: the owner's guide

PicoQuorum is a small console that is **one owner of your Safe multisig**. It watches your Safes
over WiFi, shows each pending transaction in plain language, and signs with a key sealed inside
its chip, but only after you have seen every page and held the green button.

> **Experimental.** Use it on testnets and with pocket change. Always keep at least one other
> owner on the Safe that is not this console (your browser wallet, say), so losing the console
> never loses the funds.

| Page | For |
|---|---|
| [SETUP.md](SETUP.md) | From a board with the console image to a console that signs for your Safes |
| [USING.md](USING.md) | The screens and buttons, approving, rejecting, and what red means |
| [NETWORKS.md](NETWORKS.md) | Which chains work, watching several Safes at once, adding a chain |
| [PROPOSING.md](PROPOSING.md) | Starting a transaction without the Safe web app: a wallet, a delegate, or the consoles alone |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | What each stop screen means and what to do |

**How it fits together.**

- **The Safe** lives on a chain (Base, Ethereum…). You make it, and add or remove owners, in the
  Safe web app (app.safe.global).
- **Safe's transaction service** (api.safe.global) holds the proposals that are waiting for
  signatures. The console reads from it and sends its signatures back. It never sends anything
  onchain itself.
- **The console doesn't trust the service.** It rebuilds each transaction's hash from the fields
  on its own screen, with the chain and the Safe it was set up for. Its key signs that hash and
  nothing else. A service that lies gets a refusal, not a signature.
- **Someone else executes.** Once enough owners have signed, anyone executes the transaction and
  pays the gas. Today that is `tools/quorum live exec`, because the Safe web app can't execute
  these (see [TROUBLESHOOTING](TROUBLESHOOTING.md#the-safe-web-app-fails-with-gs021)).

For how and why it works: [SECURITY.md](../SECURITY.md) (the trust model),
[PROVISIONING.md](../PROVISIONING.md) (making a key), [LADDER.md](../LADDER.md) (how far each
chain has been tested).
