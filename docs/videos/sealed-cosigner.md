# 10. The sealed hardware cosigner

*Draft script, 2026-11-10. Not recorded. No card on the Learn page yet.*

| | |
|---|---|
| for | crypto-native people who know they should use a multisig, and don't, because it's a hassle |
| length | about 1:40 (250 words); short form |
| the one idea | A multisig owner doesn't have to be a wallet with a seed phrase. It can be a sealed chip with a screen. That is new, and more than one project is building it. |

Unlike the other nine, this one is first person and casual: the maker talking to camera. The rules
in [the README](README.md#rules-for-every-script) still hold.

## Script

**The hook** (0:00)

*Shows: the maker, to camera.*

We all know we should use a multisig for anything that matters. And most of us don't, because it's
a pain.

**The pain** (0:10)

*Shows: a made-up seed phrase on a card. Then three cards.*

Every owner on a multisig is another wallet. Every wallet is another seed phrase. How do I back it
up? How many copies? Where do I hide them?

*Shows: a phone call to a friend. A map, the two of them far apart.*

And then the off-site signer. Mine would be my college roommate. I'd trust him with anything, and
he has never touched crypto. Now I'm explaining seed phrases, which wallet to install, and how to
restore it three years from now.

**What changed** (0:35)

*Shows: a passkey prompt. Then three chips in a row, each with its maker's name under it
([the chip card](#the-chip-card)).*

Two things changed. Ethereum and the big L2s can now check the kind of signature a passkey makes.
And Safe has an audited passkey signer.

A secure chip that costs a few dollars makes that same kind of signature. So a chip can be an owner
of a Safe. The key is made inside the chip and can't be read out. No seed phrase. Nothing to write
down, photograph or phish.

**The thing** (0:55)

*Shows: the console. The approve page, then a thumb holding Sign as the bar fills.*

I call it a sealed hardware cosigner. This is my bare-bones one, Picoquorum: a chip, a small screen,
a few buttons. It shows what the transaction does. It works out the hash itself. It signs only when
you hold the button.

It can't send anything by itself. It's one vote.

*Shows: the roommate takes it out of a drawer, reads the screen, holds Sign.*

So my roommate gets a small box. I call him, he reads the screen, and he holds the button or he
doesn't.

**The catch** (1:15)

*Shows: the key dropped down a drain. A Safe, 2 of 3: one owner greys out, the other two swap in a
new one.*

The catch: no seed phrase means no backup. Lose it and that key is gone. So it's never the only key.
The other owners swap it out. They are the backup.

**The close** (1:30)

*Shows: a wedgie beside the console. Then picoquorum.app.*

I'm not the only one building this. Austin Griffith's wedgie does it too, and mine started as a fork
of his picowallet. It's open source and experimental: a testnet first, small amounts after. Try the
console in your browser at picoquorum.app.

## The details

What the script stands on, and what the animation can show. Each line that came from outside this
repository was read on 2026-11-10 and has its source at the end.

### What made it possible

Three things had to exist. The first two are the "EIP" of the script.

| | what it is | where |
|---|---|---|
| **RIP-7212** | A precompile at `0x100` that checks a P-256 (secp256r1) signature, for 3,450 gas | the L2s. Base is the one this project uses |
| **EIP-7951** | The same precompile at the same address on Ethereum, for 6,900 gas. It also fixes two checks RIP-7212 left out | Ethereum mainnet, with the Fusaka upgrade. Status: Final |
| **Safe's passkey signer** | A small contract per key (`SafeWebAuthnSignerProxy`) that is the Safe's owner. It checks a WebAuthn assertion with the precompile and answers through EIP-1271 | the same address on every chain; the factory is in [STATUS.md](../STATUS.md) |

Why P-256 matters: Ethereum's own accounts sign on a different curve, secp256k1. Passkeys, phones'
secure enclaves and these chips all sign on P-256. Before the precompile, a contract could check a
P-256 signature only with a few hundred thousand gas of Solidity. Now it is cheap enough to be an
everyday owner.

How the chip uses it: the console works out the Safe transaction hash (EIP-712), puts it in a
WebAuthn assertion as the challenge, and the chip signs that. To the Safe, the chip looks like a
passkey ([EMU-WEB.md](../EMU-WEB.md), `firmware/webauthn.py`).

A line for the screen: **"P-256 onchain: RIP-7212 on L2s, EIP-7951 on Ethereum."**

### The chip card

Three chips, drawn side by side, each with a label under it. Don't draw a score. Say what is open
and what is not.

| | ATECC608 | OPTIGA Trust M | TROPIC01 |
|---|---|---|---|
| **maker** | Microchip (US) | Infineon (Germany) | Tropic Square (Czech Republic), part of SatoshiLabs with Trezor |
| **signs P-256** | yes | yes | yes, by the maker's page |
| **the chip's design** | closed | closed | published for audit: the maker says the design is open to customers and the public |
| **the docs and host code** | a public datasheet, and Microchip's CryptoAuthLib | NDA-free docs, and a host library under MIT | an open SDK (libtropic) |
| **outside checks** | none named here | Common Criteria EAL6+, by Infineon's page | open to anyone; a hardware flaw was disclosed in 2026 |
| **in Picoquorum** | yes: the USB-C key, and two sealed chips that own test Safes | yes: one sealed chip, approving on Base Sepolia | no. Not tried |
| **seen in** | wedgie (either chip), Picoquorum | wedgie, Picoquorum, Trezor Safe 7 | Trezor Safe 7 |

A label under each, short enough to read in two seconds:
- **ATECC608 · Microchip · closed chip, open driver**
- **Trust M · Infineon · closed chip, certified, open driver**
- **TROPIC01 · Tropic Square · open design**

What the card must not say:
- That open means safe. TROPIC01's maker disclosed a hardware flaw in 2026, and Trezor says it
  can't be fixed by a firmware update. Open means it can be checked, and this one was.
- That certified means safe. EAL6+ is a lab's finding about the hardware, not about how a
  product uses it.
- That Picoquorum runs on TROPIC01. It doesn't. The line is "a third chip that could do this".

### The two projects

| | Picoquorum | wedgie |
|---|---|---|
| **by** | this repository | Austin and Gus Griffith ([wedgie.dev](https://wedgie.dev/)); the code is under `clawdbotatg` on GitHub |
| **the chip** | ATECC608 or Trust M | ATECC608 or Trust M |
| **the Safe hash** | worked out on the device | worked out on the device, by its Safe repo's README |
| **how it owns a Safe** | Safe's passkey signer | Safe's passkey signer |
| **the tie** | began as a fork of Austin's [picowallet](https://github.com/austintgriffith/picowallet) ([README](../../README.md#credit)) | |

That two projects landed on the same shape is the argument that this is a category.

### What the roommate does

From [ONBOARDING.md](../ONBOARDING.md), which is a proposal and says so. A keyholder has three jobs:
1. **Keep it**, like a spare house key. It alone can't move money.
2. **Approve only what someone told you about, by voice.** Read every page. Anything else: Reject,
   and call.
3. **Say if it's lost**, or if it was out of your hands.

What he never needs: a seed phrase, a wallet app, gas, or crypto knowledge. Someone technical still
sets the console up and adds its key to the Safe.

### The trade-offs, for a longer cut

- **No backup.** The other owners replace a lost key with `swapOwner`
  ([A key with no backup](no-backup.md)).
- **No PIN.** Whoever holds the board can use it. That is one vote, and a reason to say when it was
  out of your hands.
- **No secure boot yet.** Someone with the board and a computer can put other firmware on it
  ([SECURITY.md](../SECURITY.md)).
- **One vote, on purpose.** Keep a hardware wallet as another owner. No technology and no person
  holds a threshold's worth of keys ([GOVERNANCE.md](../GOVERNANCE.md)).

## Check before recording

- **Which board is on camera.** The README's console is a Pico 2 W with Wi-Fi, a 240 × 240 screen,
  a joystick and four buttons. [console-rp](../../hardware/console-rp/README.md) and
  [Mono](../../hardware/mono/README.md) have no radio, a 1.14-inch screen and three buttons; Mono is
  designed and not ordered. "A small screen, a few buttons" fits both. Any line about Wi-Fi, or
  about no radio, has to fit the board in the shot.
- "Sealed hardware cosigner" is this script's term. The other scripts say "a cosigner with a sealed
  key". Use one on screen.
- "Ethereum and the big L2s": this project has checked Base and Ethereum
  ([LADDER.md](../LADDER.md)). Name other chains only after checking them.
- "Safe has an audited passkey signer": the README's words. Name the auditor only after reading the
  report.
- "A few dollars": check a distributor's price for one chip on the day.
- "Can't be read out": the chip has no command for it, and it is locked after provisioning
  ([LOCKING.md](../LOCKING.md), [TRUSTM.md](../TRUSTM.md)).
- "Signs only when you hold the button" is true of the console image, not of the chip
  ([The multisig is the wallet](cosigner.md), its first check).
- The roommate scene shows a handover that [ONBOARDING.md](../ONBOARDING.md) proposes. Path A in it
  exists today with laptop tools. Don't show a step that isn't built without "planned" on screen.
- The chip card. Read each maker's page again:
  - the ATECC608's full datasheet has been public for some parts and under NDA for others. Check
    the ATECC608C's before "public datasheet" goes on screen;
  - what Tropic Square publishes was read from its site and from Trezor's, not from the
    repository itself. Open `github.com/tropicsquare/tropic01` and say what is there;
  - the state of the TROPIC01 flaw, and whether newer chips have it.
- wedgie: its site and its Safe repo's README were read, not its code. Ask Austin before saying
  what a wedgie does or doesn't have. "The first one I know of" is safer said of picowallet.
- EIP-7951's fork: [EMU-WEB.md](../EMU-WEB.md) says Fusaka. The EIP's own page doesn't name it.

## Sources

- [EIP-7951](https://eips.ethereum.org/EIPS/eip-7951): the address, the gas, and what it changes
  from RIP-7212.
- [wedgie.dev](https://wedgie.dev/) and
  [clawdbotatg/wedgie-safe](https://github.com/clawdbotatg/wedgie-safe).
- [Infineon: OPTIGA Trust M](https://infineon.com/OPTIGA-Trust-M) and
  [its host library](https://github.com/Infineon/optiga-trust-m).
- [Microchip: CryptoAuthLib](https://www.microchip.com/en-us/software-library/cryptoauthlib).
- [Tropic Square: TROPIC01](https://www.tropicsquare.com/tropic01),
  [Trezor: what is the TROPIC01 chip](https://trezor.io/guides/trezor-devices/trezor-safe-7/what-is-the-tropic-01-chip),
  and [Trezor's response to the TROPIC01 disclosure](https://trezor.io/blog/news/Trezor-response-TROPIC01-chip-disclosure-no-impact-to-your-funds).

## For X

> We all know we should use a multisig. Most of us don't: every owner is another seed phrase.
>
> New: a chip can be an owner of a Safe. Key made inside, can't be read out, no seed phrase.
> One vote, with its own screen.
>
> picoquorum.app/console

The cut: "Two things changed" to "It's one vote", about 40 seconds.
