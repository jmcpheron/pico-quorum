# 7. A new key, from the bench to your Safe

*Draft script, 2026-11-09. Not recorded. **Most of this is a plan, not a product**: it follows the
proposals in [BRANDED-KEYS.md](../BRANDED-KEYS.md), [ATTESTED-KEYS.md](../ATTESTED-KEYS.md) and
[ONBOARDING.md](../ONBOARDING.md). The script says "the plan" where it is one.*

| | |
|---|---|
| for | someone about to receive a key, and anyone who asks "how do I know nobody got to it first?" |
| length | about 3:45 (570 words) |
| the one idea | The bench marks the chip and makes no key. Your own console checks the mark, then makes the key in front of you. Funds go to your Safe, never to the key's address. |

Four parts: the bench, what arrives, the ceremony, and where funds go. Each part can be cut out as
a video of its own. "PLANNED" stays in a corner of the frame for every step that isn't built.

## Script

*Shows: a title card: "How a key gets to you. The plan."*

This is how a Picoquorum key is meant to get from a parts reel to your Safe. Some of it runs today.
Some is a plan, and the screen says which.

**The bench**

*Shows: a reel of chips. One chip, drawn empty, two open padlocks on it.*

A key starts as a secure element bought from a parts distributor. It arrives blank: no key, no
rules, nothing locked.

*Shows: the chip on a bench. Rules are written in. A padlock shuts.*

The project's bench does two things to it. It writes Picoquorum's rules for the chip and locks them
for good. One of the rules: nobody can load a key into this chip from outside. The chip can only
make its own.

*Shows: a small record: "Picoquorum key 0042, batch 3". A second chip, marked 0000, signs it. The
second padlock shuts.*

Then it brands the chip: a number, a batch, and a signature. The signature comes from key 0000,
which is itself a Picoquorum key, sealed in a chip like yours. Then the bench locks that too.

*Shows: the chip again. Both padlocks shut. The middle is still empty.*

What the bench does not do is make your key. The chip ships empty.

**What arrives**

*Shows: a small bag. A label: the number, a small picture, "No key inside yet."*

So this is what you get. A key with a number, a picture, and nothing inside.

*Shows: the key plugged into a console. The screen: "A Picoquorum key. No key inside it yet."*

Plug it into your console, and the console checks it before you do anything. Four things.

*Shows: four lines tick, one by one.*

The brand's signature is key 0000's. The chip is locked the way the brand says. No key has been
sealed in it. And it has never signed: zero uses.

*Shows: the label held up to the screen. Same number, same picture.*

Then your part: the number and the picture on the screen match the label in your hand.

*Shows: a red page: "Not a Picoquorum key."*

If any of that fails, the page is red and the console writes nothing. Stop there.

*Shows: the chip in an envelope, a hand reaching for it, bouncing off.*

Why this is enough to trust the post: someone who opens the envelope can't put a key they know
into the chip. The rules are locked. And if they make one and seal it, the console tells you this
key was claimed before.

**The ceremony**

*Shows: the screen: "Make your key". A thumb holds a button.*

Now you make the key. Hold the button, and the chip makes a key inside itself. Nobody chose it. Not
the bench, not the console, not you.

*Shows: "Testing your key". Two ticks.*

The console has it sign twice, as a test, and checks both.

*Shows: a red page: "Seal your key. Permanent." The bar fills slowly.*

Then you seal it. This is the step that can't be undone. After it, the key can't be changed or
replaced, by anyone. You can practise the whole thing first: practice writes nothing.

*Shows: "Your key is ready", an address and its picture.*

The console shows your owner address. That is what gets added to a Safe.

**Where funds go, and where they don't**

*Shows: the owner address, a coin flying toward it, a red cross.*

Don't send anything to that address. It looks like a wallet. It isn't. It is a signer: a small
contract that checks your key's signatures. It can't hold your funds for you.

*Shows: two boxes appear in order: "signer", then "Safe". The coin goes to the Safe.*

Two contracts get created, and both come after the ceremony. First the signer, at that address.
Then the Safe, or an owner change on a Safe that exists. Any wallet can pay for either. Funds go to
the Safe's address, on the chain where that Safe lives.

*Shows: a Safe, 1 of 1, then a second owner joins: 2 of 2, then 2 of 3.*

The plan is a starter Safe on a testnet, with your key as its one owner. That is where you start,
not where you stay. Add owners and raise the threshold before anything of value goes in.

**What the brand is for, later**

*Shows: a chain of links: key 0000, the brand, your chip, your key, your address.*

A brand lets anyone check that a key lives in a chip the bench marked. The plan builds on that: a
relay that pays the gas for branded keys, from a treasury anyone can read. Registering for it would
be your choice, and it would link your key's number to your address in public.

None of that is built. A key works as a Safe owner without it.

*Shows: picoquorum.app.*

Picoquorum is open source and experimental. The proposals are written down, and linked below.

## Check before recording

Read every one of these. This script describes more unbuilt things than any other.

- **What exists, as of 2026-11-09.** The bench half ran on a spare chip. The claim (U1–U5) walks on
  the emulator, not on silicon. **Key 0000 doesn't exist yet.** The bag label, the app's brand page,
  the starter Safe as an onboarding step, the registry, the relay and the treasury are not built
  ([BRANDED-KEYS.md](../BRANDED-KEYS.md), [ATTESTED-KEYS.md](../ATTESTED-KEYS.md), their first
  paragraphs). Record the claim's screens from the emulator and say so on screen.
- **Today's path is different.** The keys made so far went through the whole ceremony on the bench,
  C1–C10 ([PROVISIONING.md](../PROVISIONING.md)), and an owner can run that on their own console
  with a blank chip. If the video goes out before branded keys do, open with that.
- **"Nobody can load a key from outside"**: after the bench's data lock, slot 0 takes only the
  chip's own GenKey ([BRANDED-KEYS.md](../BRANDED-KEYS.md), "Why split it"). Before that lock, a
  dishonest bench could plant one, which is the reason for the split. `tools/check_config` must
  decode the table independently before any of this is said about a real chip.
- **"Four things"**: the brand signature under the pinned key, the record matching the chip, both
  zones locked, and slot 0 not sealed; the use count is shown beside them
  ([BRANDED-KEYS.md](../BRANDED-KEYS.md), "The technical decisions" and "The user").
- **What the brand can't prove.** An ATECC608 has no factory certificate, and a brand can be read
  off one chip and copied onto a fake. The attestation key is the proposed answer
  ([ATTESTED-KEYS.md](../ATTESTED-KEYS.md), "The gap in the brand as proposed"). The script says
  "a chip the bench marked", never "a genuine chip". Don't say the check proves the chip is real.
- **The console doing the checking has to be right too.** Its Device screen shows the release
  fingerprint to hold up to the README. The script leaves this out for length; put it in the
  description, or add a line.
- **"Not the console, not you"**: the key is the chip's GenKey. You can make it again until the
  seal, so "nobody chose it" means nobody could set its value.
- **"Practice writes nothing"**: built, Device → Practice, from release 2026.11.2, checked on the
  emulator ([ONBOARDING.md](../ONBOARDING.md), "What exists today").
- **"A signer, not a wallet"**: the owner address is a `SafeWebAuthnSignerProxy`, not deployed until
  someone deploys it, once on each chain, and the same address on every chain
  ([guide/NETWORKS.md](../guide/NETWORKS.md)). The claim's last screen says "Don't
  send ETH or tokens here. Funds go to your Safe."
- **"On the chain where that Safe lives"**: a Safe is a contract on one chain. Check
  [guide/NETWORKS.md](../guide/NETWORKS.md) for how the guide words this, and match it.
- **The starter Safe** is 1 of 1 on Base Sepolia in the proposal. The app's New Safe makes a
  2 of 2 with the scanning wallet and a recovery module ([ONBOARDING.md](../ONBOARDING.md), "What to
  build", step 2). Pick the one that is real on the day and redraw the last shot of that part.
- **The relay, the treasury, the registry.** All proposed. Each is a new service or the project's
  first contract, and needs review before it exists. Don't promise buyers gas, a share of anything
  or a say in spending: [ATTESTED-KEYS.md](../ATTESTED-KEYS.md), "Sales and the treasury share",
  says to get advice first. "Other benefits later" stays out of the script until one is written
  down.
- **Registering links a serial to an owner address in public.** That cuts against "don't
  advertise" in [What it protects, and what it doesn't](threat-model.md). The script says so; keep
  the line.
- **More than one chip supplier.** The Trust M comes with Infineon's certificate and has a
  different ceremony ([TRUSTM.md](../TRUSTM.md)). This script is the ATECC608 path. If a kit ships
  a Trust M, it needs its own version.

## For X

> Your Picoquorum key is meant to arrive empty.
>
> The bench marks the chip and locks its rules. It makes no key. Your own console checks the mark,
> then makes the key in front of you, and you seal it.
>
> The plan, and what's built so far: picoquorum.app/learn

The cuts: "What arrives" (about 60 seconds), and "Where funds go, and where they don't" (about 50
seconds). The second one is worth posting by itself.
