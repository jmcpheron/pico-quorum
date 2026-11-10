# 6. When the hardware fails

*Draft script, 2026-11-09. Not recorded. The second half of the hardware pair: it uses the picture
from [Inside the console](inside-the-console.md), and the two can be recorded as one video.*

| | |
|---|---|
| for | hardware and security people |
| length | about 2:30 (360 words) |
| the one idea | Every way this box can fail, break or be tampered with ends in the same place: one owner's vote, lost or misused. It is built to be an owner you can lose. |

Six cases, each on the same board picture, each ending on the same counter: "1 of 3". The counter
is the argument.

## Script

*Shows: the board with its three zones. A counter in the corner: "at risk: 0 of 3".*

Any hardware can fail. So here is each way this console can, and what each one costs.

**It dies**

*Shows: the board goes dark.*

A part fails. The screen cracks. Coffee. The key in its chip can't be copied, so that owner is
gone. The other owners still reach the threshold, and they swap in a new key. Cost: one owner.

**The firmware gets it wrong**

*Shows: the white zone flickers. The screen says one thing while a different hash goes to the key.*

A bug, or a glitch in the microcontroller, and the console signs something it didn't show. That is
the worst thing the console can do. Cost: one signature. The other owners check on their own
devices, and theirs didn't glitch.

**Someone changes the firmware**

*Shows: a hand, a jig on the back of the board.*

A person with the board in their hands writes their own firmware. Now the screen can lie, or the
chip can be asked to sign with no screen at all. Secure boot would narrow this, and it isn't on.
Cost: one signature.

**Someone swaps the chip**

*Shows: the green chip lifted off, another put down. Its address is different. The console shows a
refusal.*

This one is different. A new chip has a new key, and a new key has a new address. That address is
not an owner of the Safe, so its signatures count for nothing. The console also remembers which
chip is its own, and checks before every signature. A swapped chip breaks the console. It doesn't
fool anyone.

**Someone cracks the chip**

*Shows: the green chip under a microscope.*

Suppose a lab gets the key out of the secure element. These chips are built to resist that, and
nobody should promise it is impossible. Then the attacker holds one owner's key, and can sign
without the console. Cost, again: one signature.

**Someone swaps the whole console**

*Shows: the console taken from a drawer, a look-alike left in its place.*

A look-alike has no key, so it can't sign for the Safe. What it can do is hide that the real one is
gone. That matters, and the next video is about it.

**Why this is not a hardware wallet's problem**

*Shows: a hardware wallet. Arrows: "get the seed", "trick one signature". Both end at "everything".*

With a hardware wallet, tampering has a prize. Get the seed phrase out, or trick one signature, and
you have everything.

*Shows: the console. Every arrow from the six cases ends at "1 of 3".*

Here, every road ends at one vote out of several. Tampering buys what stealing the box buys, and
no more.

*Shows: the counter changes to "at risk: 2 of 3", in red.*

One vote is not nothing. It counts if another owner is already lost, or if the threshold is low.
So when a console fails or goes missing, replace it. Don't wait.

*Shows: picoquorum.app.*

Picoquorum is experimental. It is one owner, and the Safe's threshold is the real control.

## Check before recording

- **"The console remembers which chip is its own"**: `QUORUM_EXPECT` names the chip's serial, the
  slot, its lock and the owner address its key must produce, checked at start and right before
  each signature ([SECURITY.md](../SECURITY.md), "The pin"). A board with no pin shows **Not
  pinned** ([guide/TROUBLESHOOTING.md](../guide/TROUBLESHOOTING.md)). Someone who can swap the chip
  can also change the firmware and the pin, so the pin guards against mistakes. What stops the
  swap from mattering is the address, and that is the line the script leans on.
- **"A new key has a new address"**: the owner address follows from the public key through Safe's
  passkey signer ([mainnet/THREAT-MODEL.md](../mainnet/THREAT-MODEL.md)).
- **"Secure boot isn't on"**: [SECURITY.md](../SECURITY.md), [STATUS.md](../STATUS.md). Rewrite the
  third case if it is.
- **"A glitch in the microcontroller"**: Raspberry Pi's RP2350-E24 erratum is about glitch attacks
  on the A2 stepping ([hardware/mono/README.md](../../hardware/mono/README.md), "Open"). Don't name
  a stepping unless it has been checked on the boards.
- **"Built to resist that"**: the Trust M is certified CC EAL6+
  ([mainnet/THREAT-MODEL.md](../mainnet/THREAT-MODEL.md)). Find and cite the ATECC608C's own
  claims before saying more about it. Nobody here has tried to crack either chip.
- **"The chip can be asked to sign with no screen"**: anyone on the chip's bus can have it sign any
  digest. On an ATECC608 the counter shows it; a Trust M keeps no record
  ([SECURITY.md](../SECURITY.md), [mainnet/THREAT-MODEL.md](../mainnet/THREAT-MODEL.md)).
- **"Theirs didn't glitch"** assumes the other owners are other kinds of device. If every owner is
  a Picoquorum console on the same release, one firmware bug is in all of them
  ([GOVERNANCE.md](../GOVERNANCE.md): no technology holds a threshold's worth of keys). Keep the
  owners in the picture mixed.
- The hardware wallet comparison is about the design, not any maker. No brand on screen.

## For X

> Six ways a Picoquorum console can fail: it dies, it glitches, someone reflashes it, swaps the
> chip, cracks the chip, or swaps the whole box.
>
> Each one costs the same thing: one vote out of several. That's the design.
>
> picoquorum.app/learn

The cut: "Someone swaps the chip", about 30 seconds. It is the one people ask about.
