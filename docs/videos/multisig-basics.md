# 2. Two of three: a multisig in two minutes

*Draft script, 2026-11-09. Not recorded.*

| | |
|---|---|
| for | people new to crypto, or new to holding it for a group |
| length | about 1:45 (250 words) |
| the one idea | A multisig is a shared account that needs several approvals, so no one person and no one mistake can move the money. |

No jargon. "Key", "owner", "approve" and "multisig" are the only terms, and each is said in plain
words first. No hashes, no chips, no contract names.

## Script

*Shows: a bank card and a PIN.*

A normal crypto wallet works like a bank card with the PIN written on it. Whoever holds it can
spend everything.

*Shows: a safe-deposit box with two keyholes.*

A multisig works like a safe-deposit box with more than one lock. It takes several keys to open,
and different people hold them.

*Shows: three people, each with a key. A label: 2 of 3.*

You choose two numbers: how many owners there are, and how many of them must approve. Two of three
is the usual start. Three people each hold a key. Any two can approve a payment. No one can do it
alone.

*Shows: one of the three keys stolen. Nothing moves.*

If one key is stolen, the thief has one approval, and one is not enough.

*Shows: one key lost. The other two swap in a new key.*

If one key is lost, the other two still open the box. Then they do one more thing together: they
take the lost key off the list and put a new one on.

*Shows: a family, a club, a two-person company.*

That is why groups use one. A family's savings. A club's treasury. A small company. It also works
for one person: three keys of your own, kept in three places.

*Shows: a payment waiting, 1 of 2 approved, then 2 of 2, then sent.*

Day to day, it goes like this. One owner proposes a payment. It waits. Each owner looks at it and
approves or rejects. When enough have approved, it is sent.

*Shows: the console next to a phone and a laptop.*

An owner's key can live in an app, in a hardware wallet, or in a Picoquorum console: a small box
with its own screen, made for exactly this job. It shows you the payment in plain words, and you
hold a button to approve.

*Shows: picoquorum.app.*

Picoquorum is open source and experimental. See how an approval looks at picoquorum.app.

## Check before recording

- "Take the lost key off the list and put a new one on" is Safe's `swapOwner`, and it needs the
  threshold's worth of the remaining owners ([mainnet/COSIGNERS.md](../mainnet/COSIGNERS.md),
  section 4).
- "Three keys of your own" is allowed, but the project's own rule is that no person holds a
  threshold's worth ([GOVERNANCE.md](../GOVERNANCE.md)). Keep the line as a plain fact about
  multisigs, or cut it.
- "Approves or rejects": the app proposes a rejection as its own transaction at the same nonce
  ([web/README.md](../../web/README.md)). The script doesn't go into that.
- The safe-deposit box is a picture, not a claim about any bank.

## For X

> New to multisigs? It's a shared account with more than one lock.
>
> 2 of 3: three people hold keys, any two approve, no one acts alone. One stolen key moves nothing.
> One lost key gets replaced.
>
> Two minutes: picoquorum.app/learn

The cut: from the safe-deposit box to "put a new one on", about 60 seconds.
