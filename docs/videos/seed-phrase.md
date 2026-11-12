# 1. One seed phrase, one point of failure

*Draft script, 2026-11-09. Not recorded.*

| | |
|---|---|
| for | everyone who holds crypto, or looks after it for a group |
| length | about 2:20 (350 words) |
| the one idea | A seed phrase is a single point of failure. A multisig removes it, and Picoquorum is a new kind of owner to put in one. |

The first half is about seed phrases and multisigs and never names the project. The second half is
where Picoquorum fits.

## Script

*Shows: twelve made-up words, handwritten on a card.*

Most crypto wallets come down to twelve words on a piece of paper. Whoever has the words has
everything. There is no second check, and no way to take it back.

*Shows: the card photographed by a phone. Then the card in a bin.*

That is a single point of failure, twice over. If someone copies the words, the money is gone. If
you lose the words, the money is gone.

*Shows: a browser wallet, a phone app and a hardware wallet in a row, the same card under each.*

A browser wallet, a phone app, a hardware wallet: they keep the words in different places, and some
keep them far better than others. But it is the same design. One secret, which has to stay hidden
from everyone and never be lost.

That is fine for pocket money. It is a bad way to hold savings, a club's treasury, a company's
funds or a project's release keys.

*Shows: three keys around one box. Two light up, and the box opens.*

The fix is an old one: don't let one key decide. A multisig is a wallet with a list of owners and a
number. Two of three. Three of five. Nothing moves until that many owners approve.

Now one stolen key moves nothing. And one lost key loses nothing: the other owners replace it.

*Shows: the three keys turn into three copies of the same laptop, looking at the same web page.*

There is a catch. If every owner is the same kind of wallet, on the same kind of laptop, reading the
same web page, then one bug or one fake page can fool all of them. A second check is only worth
something if it fails differently from the first.

*Shows: the console in a hand, its home screen on.*

That is where Picoquorum comes in. It is a small console that is one owner of a Safe multisig. Its
key is made inside a chip and can't be read out. It has no seed phrase: nothing to write down,
photograph or phish.

*Shows: the console's approve page, then a thumb holding Sign as the bar fills.*

It shows what a transaction does on its own screen. It works out the hash itself. And it signs only
after you have seen every page and held Sign.

*Shows: the three owners again: a hardware wallet, a passkey and the console.*

It is not a wallet. The multisig is the wallet. Picoquorum is one more owner, of a different kind,
to sit next to the ones you already have.

*Shows: picoquorum.app.*

It is open source and experimental: a reference design for a sealed hardware cosigner. Try the
console in your browser at picoquorum.app.

## Check before recording

- "Can't be read out", "no seed phrase": the key is made in the chip and the chip has no command
  that reads it ([README](../../README.md#1-a-key-that-cant-leak), [SECURITY.md](../SECURITY.md)).
  [SECURITY.md](../SECURITY.md) also lists what a sealed key does not protect against. Don't say
  "unhackable" or "can't be stolen".
- The seed-phrase wallets are not the enemy here. The README puts a hardware wallet next to the
  console as another owner. The claim is that no single one of them should hold the value alone.
- "Works out the hash itself", "every page", "held Sign": [SECURITY.md](../SECURITY.md), "The
  signing boundary".
- A seed phrase is twelve or twenty-four words. The card on screen is made up for the shot.

## For X

> Twelve words on paper. Copy them and the money is gone. Lose them and the money is gone.
>
> A multisig takes away the single point of failure. Picoquorum is a new kind of owner to put in
> one: a console with a sealed key and no seed phrase.
>
> picoquorum.app/learn

The cut: from the start to "the other owners replace it", about 70 seconds, ends on the three keys.
