# Starting a transaction without the Safe web app

The console signs only what is waiting in Safe's transaction service, and the service lists a
transaction only after an owner or a delegate has signed it. Usually that's your browser wallet
in the Safe web app. This page covers the other ways, for when that wallet is gone or the web app
can't help:

| Your situation | Use |
|---|---|
| An owner's ordinary wallet still works (a Ledger, a browser wallet, a Foundry keystore) | [An owner's wallet](#an-owners-wallet) |
| You want a backup proposer in place before anything goes wrong | [A delegate](#a-delegate) |
| Only consoles are left | [A console proposes](#a-console-proposes) |
| Only consoles are left, and Safe's service is down or won't take it | [No service at all](#no-service-at-all) |

All of them use `tools/quorum live propose`. None of them trusts the laptop: the console rebuilds
the hash from the fields it shows, and the Safe checks every signature against that hash.

**The console needs no new firmware for any of this.** Everything new runs on the laptop.

## What to propose

```
tools/quorum live propose --chain C WHAT ...
```

| WHAT | Does |
|---|---|
| `send TO ETH` | sends ETH from the Safe |
| `call TO DATA [--value ETH]` | calls a contract (the console shows a contract it doesn't know in red) |
| `swap-owner OLD NEW [OLD NEW..]` | replaces owners. Two or more pairs go in one MultiSend, so one approval round replaces them all |
| `add-owner NEW [--threshold N]` | adds an owner. The threshold stays as it is unless you give one |
| `remove-owner OLD [--threshold N]` | removes an owner |
| `threshold N` | changes the threshold |
| `reject NONCE` | an empty transaction at that nonce, so whatever else waits there can never run |

`--nonce N` picks the nonce; by default it is the next one after the service's queue.
`--dry-run` shows the transaction, its safeTxHash and its **verify code** (the hash's last 8
characters, which the console shows too) and stops before anything is signed.

**After losing owners, replace them first.** With 3 of 5 and only 3 keys left you have no margin:
one more lost key freezes the Safe. For example, to replace two lost seed-phrase owners with two
new addresses in one go:

```
tools/quorum live propose --chain base swap-owner 0xLOST1.. 0xNEW1.. 0xLOST2.. 0xNEW2.. --by console
```

The console shows owner changes as red pages, so they need the 3-second hold.

## An owner's wallet

When any owner with an ordinary key still works, it proposes and its signature is the first
approval:

```
tools/quorum live propose --chain base send 0xabc.. 0.01 --browser          # the browser's wallet
tools/quorum live propose --chain base send 0xabc.. 0.01 --account mykey    # a Foundry keystore
```

`--browser` opens a page on `127.0.0.1` where your wallet (MetaMask, Rabby, a Ledger through
them) signs the transaction as EIP-712 typed data. Signing sends nothing onchain and costs no gas.
The consoles then show it at their next poll.

## A delegate

A **delegate** is an extra address Safe's service lets propose for your Safe. It can never
sign: its signature counts for nothing, and it can't move funds. The worst a stolen delegate key
can do is put junk in the queue, and the consoles show that for what it is. Set one up **now**,
while an owner's ordinary wallet still works, and a laptop can always start transactions later.

1. Make a key for it, kept on the laptop:

   ```
   cast wallet new                                         # note the address and private key
   cast wallet import picoquorum-proposer --interactive    # paste the private key, set a password
   ```

2. Have an owner's wallet add it (an owner must sign this, and only an ordinary wallet can):

   ```
   tools/quorum live delegate add 0xDELEGATE.. --chain base --browser
   tools/quorum live delegate list --chain base
   ```

3. From then on the delegate proposes, and the consoles approve:

   ```
   tools/quorum live propose --chain base send 0xabc.. 0.01 --account picoquorum-proposer
   ```

`live delegate remove 0xDELEGATE.. --chain base --browser` takes it away again. A delegate is per
chain: add it on each chain whose Safe needs one.

## A console proposes

When only consoles are left, one of them signs the proposal. The laptop stands in for Safe's
service for this one transaction, on your LAN (the **stage**). The console polls it as it would
the real service, shows the transaction, and signs after the hold. The laptop checks that
signature onchain (the key's signer proxy, `isValidSignature`) and sends it to Safe's service as
the proposal, with the console's owner address as the proposer.

1. On the laptop, start it. It waits for a console:

   ```
   tools/quorum live propose --chain base send 0xabc.. 0.01 --by console
   ```

2. Point one console at the laptop. With the board on USB:

   ```
   tools/quorum live pico --chain base --stage
   ```

   Or edit its `secrets.py` by hand: the propose command prints the line, a `QUORUM_SAFES` entry
   with `"url": "http://<laptop>:8791"`.

3. On the console: open the transaction, read every page, check that the verify code matches the
   terminal's, and hold Sign. The terminal shows the signature arrive and sends the proposal.

4. Point the console back at Safe's service:

   ```
   tools/quorum live pico --chain base
   ```

5. The other consoles approve it as usual, and then anyone executes it:
   `tools/quorum live exec --chain base NONCE`.

With `--collect`, the stage stays up after the first signature and forwards each further one to
the service, until the threshold. Point every console at it, sign on each, then point them all
back.

Signatures that arrive are kept in `live.json`. If the command stops, run the same command again
and it picks them up.

## No service at all

If Safe's service is down, or won't take the proposal, the laptop can do the whole job.
`--no-service` keeps the stage up until enough owners have signed, then executes:

```
tools/quorum live propose --chain base swap-owner 0xLOST.. 0xNEW.. --by console --no-service --account gas-payer
```

Point every console that will sign at the laptop (`live pico --chain base --stage` on each), and
sign on each. When the threshold is reached, the laptop sends `execTransaction` from the account
you name: `--account` for a Foundry keystore, `--browser` for the wallet page. That account only
pays the gas, about 110k on Base. It needs a little ETH and nothing else: it has no say over the
Safe. Safe's service never sees the transaction. Once it's indexed onchain, the web app shows the
result.

## Executing

Whoever executes doesn't need to be an owner. `execTransaction` checks the signatures inside it,
not the sender, so any account with a little ETH can send it: a brand-new one is fine. Use
`tools/quorum live exec`, not the Safe web app: with two or more console signatures the web app
fails with GS021 ([TROUBLESHOOTING](TROUBLESHOOTING.md#the-safe-web-app-fails-with-gs021)).

## How far this is tested

- **On the fork, with the emulator:** `tools/quorum e2e-propose` passes. A console's signature is
  the proposal, the mock service takes it, and it executes. A two-owner MultiSend signed at the
  stage executes with no service. Alice adds a delegate. The mock service applies the real
  service's rules: the hash must match the fields, the sender must be an owner or a delegate, and
  the signature must be the sender's.
- **Not yet on a real chain.** Safe's real service already takes console signatures as
  confirmations. A console signature as the *proposal* goes through the same check there, but
  nobody has tried it yet. Try it on Base Sepolia first:
  1. `tools/quorum e2e-propose` on the laptop (Foundry, no hardware).
  2. `tools/quorum live propose --chain basesep send <your address> 0.0001 --by console --dry-run`.
  3. The same without `--dry-run`. Then `live pico --chain basesep --stage`, sign on the Pico,
     and `live pico --chain basesep` again.
  4. `tools/quorum live status --chain basesep`: the transaction is queued with the console's
     signature. Approve with the other owners, then `live exec`.
  5. Write down what happened in the buildlog, including the service's answer if it refused.
