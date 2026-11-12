# 3. The multisig is the wallet

*Draft script, 2026-11-09. Not recorded.*

| | |
|---|---|
| for | people who already use a browser wallet or a hardware wallet |
| length | about 2:00 (280 words) |
| the one idea | A browser wallet, a phone app and a hardware wallet are all ways to hold a seed phrase. Picoquorum is something else: a cosigner with a sealed key, and the multisig is the wallet. |

## Script

*Shows: a browser extension, a phone app, a hardware wallet.*

A browser wallet. A phone app. A hardware wallet. They look like three kinds of thing. They are
three ways to hold the same thing: a seed phrase.

*Shows: each one opens to show the same twelve made-up words.*

The hardware wallet holds it best. But the words still exist, on paper, somewhere. Anyone who finds
them has every account they open, on every chain.

*Shows: a Safe, with a list of owners and "2 of 3".*

With a multisig, the wallet moves. The funds sit in a Safe, onchain. The Safe has a list of owners
and a threshold. What you hold is no longer the wallet. It is one vote.

*Shows: the console.*

So an owner doesn't need to be a wallet at all. It needs to do one job well: look at a transaction,
and say yes or no.

Picoquorum is built for that one job. Here is what it leaves out.

*Shows: each line as a crossed-out row.*

No seed phrase. The key is made inside a chip and stays there.

No accounts, no balances, no swap button. It can't send anything by itself.

No browser. It has its own screen, and its own code to work out what it is signing.

*Shows: the approve page, a red page, the hold bar.*

And here is what it keeps. It reads a transaction waiting in the Safe's queue. It says what the
transaction does, in plain language, with red pages for anything that changes who controls the
Safe. It works out the hash from what it showed you. Hold Sign, and its key signs that hash and
nothing else.

*Shows: a hardware wallet, a passkey and the console as three owners of one Safe.*

It doesn't replace your hardware wallet. Keep that as another owner. The point is that the owners
are different: different hardware, different code, a different person looking. Then one failure is
one vote, not the Safe.

*Shows: picoquorum.app.*

Picoquorum is open source and experimental. The whole console runs in your browser at
picoquorum.app.

## Check before recording

- "Signs that hash and nothing else" is true of the console image. A person with the board in
  maintenance, or on the chip's bus, can have the chip sign any digest
  ([SECURITY.md](../SECURITY.md), "Still open to whoever holds the board"). Keep the line about the
  console, not the chip.
- "Its own code to work out what it is signing": `firmware/safe_tx.py`, checked by
  `test-vectors/`.
- "Any Safe from 1.3.0 on, on Base and Ethereum" if the Safe's version or chain is mentioned
  ([README](../../README.md#3-one-owner-in-a-multisig)).
- The key owns the Safe through Safe's passkey signer contract. The script leaves that out; don't
  say the console's address is "a normal account".
- "Every account they open, on every chain" is about a standard seed phrase with no passphrase.

## For X

> A browser wallet, a phone app, a hardware wallet: three ways to hold a seed phrase.
>
> With a multisig, what you hold isn't the wallet. It's one vote. Picoquorum is built to be only
> that: no seed phrase, no balances, its own screen, a sealed key.
>
> picoquorum.app/learn

The cut: "With a multisig, the wallet moves" to "nothing else", about 75 seconds.
