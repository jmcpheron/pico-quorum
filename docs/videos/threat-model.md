# 8. What it protects, and what it doesn't

*Draft script, 2026-11-09. Not recorded.*

| | |
|---|---|
| for | anyone about to be an owner, and the other owners of their Safe |
| length | about 2:30 (380 words) |
| the one idea | The console guards against a lying screen and a leaked secret. It does not guard itself: there is no PIN and no fingerprint, so whoever holds it can use it. Keep it safe, notice fast when it's gone, and don't advertise where it is. |

The plainest video of the set, and the one with no selling in it. A person talks to the camera,
with the console on the table.

## Script

*Shows: the console on a table.*

Here is what this console protects you from, and what it doesn't. Both halves matter.

**What it protects from**

*Shows: a laptop showing "Send 0.05 ETH to Carol". The console beside it shows a different, red
page.*

A lying screen. A fake web page, a hacked browser or a bad link can show you one transaction and
ask you to sign another. The console works out what it is signing by itself and shows it on its
own screen. If the laptop lies, the two don't match, and you see it.

*Shows: a hash handed to the console. A refusal.*

A lying service. The console never signs a hash it is handed. A wrong hash, a wrong Safe or a wrong
chain gets a refusal.

*Shows: a seed phrase on paper, crossed out.*

A leaked secret. There is no seed phrase. The key was made in a chip and can't be read out. Nothing
to phish, photograph or find in a drawer.

*Shows: a Wi-Fi symbol, crossed out.*

And on the boards with no radio, there is nothing to reach from across the room.

**What it doesn't**

*Shows: a hand picks the console up off the table.*

It doesn't protect itself. There is no PIN. No password. No fingerprint. Whoever holds it can press
its buttons and approve what is waiting. With tools, they can do more.

That is on purpose, and it is a real limit. Treat it like a key to a building. It is not a key
that knows your face.

*Shows: a person reading a page and holding Sign anyway.*

It doesn't protect you from you. If the screen says the right thing and you approve a bad
transaction, it is signed.

*Shows: a Safe, 2 of 3, two owners shaking hands.*

And it doesn't protect you from the other owners. A threshold's worth of them can do anything.

**So, three habits**

*Shows: the console going into a locked drawer.*

One. Keep it somewhere safe. Physical security is the security here. Locked, out of sight, not in
a bag.

*Shows: an empty drawer. A calendar with a tick each week.*

Two. Know fast when it's gone. Keep it where you would notice. Look at it on a schedule. If it was
out of your hands, assume it signed something. Tell the other owners and replace it.

*Shows: a Safe's owner list, addresses only. Then a map with no pins on it.*

Three. Don't advertise. The owners' addresses are public, onchain. Who holds each one, and where it
is kept, doesn't have to be. The other owners need to know. Nobody else does.

Hiding is not the defence. The threshold is. But a thief can't take what they can't find.

*Shows: the console among other owners.*

One console is one vote. Losing it should be a chore, not a disaster. Set your Safe up so that it
is.

*Shows: picoquorum.app, the security model's link.*

Picoquorum is experimental. The full list of what it can't do is written down, and linked below.

## Check before recording

- **"No PIN, no password, no fingerprint"**: true of every board and both chips as of 2026-11-09
  ([SECURITY.md](../SECURITY.md), "There is no chip PIN"; [PROVISIONING.md](../PROVISIONING.md)). A
  PIN gate is an open decision ([STATUS.md](../STATUS.md), "Open decisions"). If one ships, this
  video is rewritten, not patched.
- **"With tools, they can do more"**: with the board in maintenance, or on the chip's bus, the chip
  signs any digest, including a transaction never shown ([SECURITY.md](../SECURITY.md), "Still open
  to whoever holds the board"). One signature.
- **"Assume it signed something"**: [mainnet/THREAT-MODEL.md](../mainnet/THREAT-MODEL.md), "If it
  was out of sight, rotate it". An ATECC608's counter only goes up, and the console flags a rise it
  didn't cause; a Trust M keeps no record. Don't say "the console will tell you" without naming
  the chip.
- **"If the laptop lies, you see it"**: only if you read the console's pages. And a lying service
  can still show the wrong owners or count on the console's screen; it can't change what is signed
  ([SECURITY.md](../SECURITY.md), "The network").
- **"Nothing to reach from across the room"**: console-rp and Mono have no radio. The Pico 2 W and
  ESP32-S3 builds use Wi-Fi. Don't show those during the line.
- **The console in a browser is a different owner**: the computer draws its screen and the passkey's
  prompt never shows the transaction ([guide/BROWSER.md](../guide/BROWSER.md)). This video is about
  the hardware.
- **"Don't advertise"** is this script's advice. No doc says it yet. If it stays, add it to the
  owner's guide so the video has something to point at. The project's own Safe names what it is
  for ([GOVERNANCE.md](../GOVERNANCE.md)); the advice is about who holds a key and where, not about
  hiding that a Safe exists.
- **"Look at it on a schedule"** is also new advice. A look-alike left in a console's place is the
  case it answers ([When the hardware fails](hardware-failures.md)). The Device screen shows the
  release fingerprint and the key; say what to check once the guide does.
- The description links [SECURITY.md](../SECURITY.md), the
  [threat model](../mainnet/THREAT-MODEL.md) and the
  [recommended configuration](../mainnet/CONFIGURATION.md).

## For X

> What a Picoquorum console doesn't do: protect itself.
>
> No PIN. No fingerprint. Whoever holds it can use it. So:
> 1. Keep it locked away.
> 2. Know fast when it's gone, and replace it.
> 3. Don't say who holds a key, or where.
>
> The plain version: picoquorum.app/learn

The cut: "What it doesn't" and the three habits, about 90 seconds.
