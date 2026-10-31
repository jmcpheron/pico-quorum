# The demo: a box that won't sign what it can't show

A short video for X, made around the Binance theft reported on 2026-10-29. Rehearse it on the
emulator before filming with the box.

## What is known about the theft, and what isn't

From the news on 2026-10-30 (CNBC, Al Jazeera, Axios, the Washington Post):
- Binance said about $6.3 billion in user funds was taken. That makes it the largest crypto theft on
  record.
- The first investigation tied it to **one engineer's compromised laptop**, which reached Binance's
  internal systems and made withdrawals.
- TRM Labs and Chainalysis attribute it to North Korea's TraderTraitor group. About $3 billion has
  been frozen.

Not confirmed in anything read so far: that account abstraction, a smart account module or blind
signing was involved. Don't say it was. Say what the box does about the part that is known: **the
laptop was trusted, and it shouldn't have been.**

The claim the demo can back up: *with a box like this as one of the keys, a compromised laptop can
show you anything, but it can't get this key to sign anything other than what this box shows.* It
can't make it sign alone, either: the Safe needs its other owners. Don't call it secure or audited.
It is a homemade prototype.

## The setup

- The laptop runs the simulated Family Safe: `tools/quorum serve`
  ([mock-tx-service](../../../tools/mock-tx-service/README.md)). On camera, this laptop is "the
  compromised laptop". It is: it serves the transactions, and in two of the stories it lies.
- The box runs the console image, with `QUORUM_URL = "http://<laptop-lan-ip>:8787"` in its
  `secrets.py`, on the same Wi-Fi.
- **The box runs off a USB power bank, not the laptop.** That's the point: no cable to the
  laptop, nothing it can type into.
- The keys: two provisioned key-cs, labelled. Key 1 is the box's owner key. Key 2 is any other
  provisioned key-c. Disposable test keys only, no real funds: the simulated Safe is chain 31337,
  so nothing signed is valid on any real chain.

Reset between takes: `tools/quorum demo` (a fresh Safe and the standard queue).

## The shots

Each scenario is one `tools/quorum propose <name>` on the laptop. The box picks it up on its next
poll.

1. **The honest one.** `send-eth`: Alice sends 0.05 ETH to Carol and signs. On the box, turn through
   the pages (to, amount, the hash worked out on the box), then stomp and hold: the bar fills, 2 s,
   signed. The laptop's dashboard shows the second approval and it executes. *"This is normal: one
   page, one stomp."*
2. **The laptop lies.** `tampered`: the laptop's screen shows 0.05 ETH to Carol, but the hash it
   asks the box to sign is for 5 ETH to a stranger. The box works the hash out itself from the
   fields it shows, so the signature it makes is over 0.05 ETH to Carol. The service checks it
   against the hash it asked for, they don't match, and it logs it as blind signing. Show the
   laptop's log. *"The laptop asked for one thing and showed another. The box signed what it showed,
   which is useless to the attacker."* (Check this on the emulator first: what the box shows and what
   the dashboard logs.)
3. **The quiet takeover.** `add-owner` or `threshold`: a stranger added as an owner, or the
   threshold dropped to 1. The box turns red, and Sign needs 3 s. Hit Reject: one press on the
   red button. *"This is the move that turns a multisig into a single key. The box says so in red."*
4. **The thing it won't do.** `delegate-unknown`: a delegatecall to a contract the box has never
   heard of, which would run its code as the Safe itself. The box refuses it outright: no hold
   long enough signs it. *"Some things no amount of 'just click approve' gets through."*

## The key swap

The box is a reader. The key is the owner. Swap the key and you swap who's signing.

1. Power off (pull the power bank's cable). Take Key 1 off the top, put Key 2 on. Power on.
2. The box reads Key 2 and shows that it's not an owner: "Not an owner yet". Open the waiting
   transaction and try to stomp: "Can't sign: this key is not an owner".
3. Swap back to Key 1, power on, and it signs as before.

Things to know before filming:
- **Swap keys with the power off.** The console reads the key at start. A key swapped in while
  it's running is caught right before signing ("the chip or its key changed since start") and
  nothing is signed. That's a good line for the video too, but it's the long way round.
- On the simulated Safe, the third owner is whichever console last announced its key
  (`/sim/device`). So Key 2 may become the owner on the next start. Check what happens on the
  emulator, and if it does, film Key 2 on a console that has `QUORUM_EXPECT` pinned to Key 1, which
  refuses any other chip ("this chip is not one of the pinned").
- The keys must already be provisioned. Nothing in this build provisions, writes or locks a chip.

## A narration to read over it

Written to be read aloud, about a minute.

> Yesterday's Binance theft started, as far as anyone knows, with one engineer's laptop. Once an
> attacker owns your laptop, they own everything it shows you. So here's a different idea. This is
> a homemade signing box. A Raspberry Pi Pico, a screen, a knob, and a guitar pedal switch. The key
> is this little board on top. It holds one owner key of a multisig, and the key can't leave the
> chip. Here's a normal payment. I turn through it on the box, not the laptop, and stomp to sign.
> Now the laptop lies. It shows me fifty thousandths of an ether to Carol, and asks for a signature
> on five ether to a stranger. The box doesn't take the laptop's word for it. It works out what it's
> signing from what's on its own screen, so the attacker gets a signature for the payment I saw,
> and nothing else. Here's someone quietly adding an owner. Red, and one press rejects it. And here's
> a call the box won't sign at all, no matter how long I stand on it. Swap the key, and the box
> becomes someone else's signer. It's a prototype, it's not audited, and it's one owner of several.
> But the idea is simple. The thing that shows you the transaction should be the thing that signs it.

Check the narration against what the box really shows on each screen before recording. Change the
words, not the box.
