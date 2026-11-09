# 5. A key with no backup

*Draft script, 2026-11-09. Not recorded.*

| | |
|---|---|
| for | anyone about to be an owner, and people who ask "what if I lose it?" |
| length | about 2:10 (320 words) |
| the one idea | A Picoquorum key can't be copied. That is what makes it safe to hold, and it is why it must never be the only way in. The other owners are the backup. |

## Script

*Shows: a key board in a hand.*

This key can't be backed up. Not by you, not by us, not by anyone who takes it apart.

That is a feature. It is also a bug. Which one depends on how you use it.

**The feature**

*Shows: a seed phrase on paper, then a photo of it, then a copy in a cloud folder.*

A backup is a copy. A seed phrase is a key built to be copied: on paper, in a photo, in a
password manager. Every copy is one more thing to steal, and you can't tell if one was made.

*Shows: the chip, the key drawn inside.*

A Picoquorum key is made inside a secure element. The chip has no command that reads it out. Then
the chip is locked, and the locks can't be undone. There is one copy, and you know where it is.

So nobody can phish it. There are no words to type into a fake page. Nobody can photograph it. To
use it, they need the thing itself.

**The bug**

*Shows: the key dropped down a drain.*

Lose it, or break it, and that key is gone. There is nothing to restore.

*Shows: a wallet with one key, lost. Then a box marked "locked for good".*

If that key were the only key to a wallet, this would be a terrible design. One accident and the
funds are locked for good.

**Why it works**

*Shows: a Safe, 2 of 3. One owner greys out. The other two swap in a new one.*

It is never the only key. It is one owner of a multisig. Lose it, and the other owners still reach
the threshold. Their first job is to swap the lost key for a new one. The Safe keeps its address
and everything in it.

The key has no backup. The Safe's other owners are the backup.

**What that asks of you**

*Shows: three rules, one at a time.*

Keep spare owners. In a two-of-two, one lost key locks the Safe. Two of three, or three of five,
can lose one and carry on.

Mix the kinds. No one technology should hold a threshold's worth of keys. No one person should
either.

And if a key is lost, or was out of your hands, replace it now. Don't wait for the second one to
go.

*Shows: picoquorum.app.*

Picoquorum is open source and experimental. Start on a testnet, and keep amounts small.

## Check before recording

- "Can't be undone": the ATECC608's locks ([LOCKING.md](../LOCKING.md)). The Trust M key is sealed
  in its own way ([TRUSTM.md](../TRUSTM.md)). If a Trust M is on screen, don't say "locks".
- "The chip's key has no backup, and can't have one. The Safe's other owners are the backup."
  ([mainnet/RUNBOOK.md](../mainnet/RUNBOOK.md), section 8).
- "Swap the lost key for a new one": `swapOwner`, signed by the threshold's worth of the remaining
  owners ([mainnet/COSIGNERS.md](../mainnet/COSIGNERS.md), section 4).
- "To use it, they need the thing itself": true, and someone who has the thing can use it. There is
  no chip PIN, and a board that was out of your hands should be treated as having signed
  ([SECURITY.md](../SECURITY.md), [mainnet/THREAT-MODEL.md](../mainnet/THREAT-MODEL.md)). That is
  why the last rule is in the script. Don't cut it.
- "No one technology, no one person": [GOVERNANCE.md](../GOVERNANCE.md).
- The board's Wi-Fi password and API key do have a backup (`tools/fw backup`). That is the board's
  settings, not the key. The script doesn't mention it; don't show it.

## For X

> This key can't be backed up. Feature or bug?
>
> Feature: one copy, in a chip, nothing to phish or photograph.
> Bug: lose it and it's gone.
>
> So it's never the only key. The Safe's other owners are the backup.
>
> picoquorum.app/learn

The cut: the opening and "Why it works", about 60 seconds.
