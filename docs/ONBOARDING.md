# Onboarding: giving someone a key

> **A proposal (2026-10-22).** Nothing here is built unless it says so. It starts from what chip 3
> needed after its ceremony (a pin, a Safe, a signer, an owner change: four laptop commands and the
> Safe app) and asks what that looks like for a person who isn't the one who built the console.
> The screens are drafted for the Feather (240 × 135, three buttons), the console the next work is on.

## The idea in one paragraph

A PicoQuorum console is useful because someone other than you holds it: a parent, a sibling, a
co-founder, a friend who'd be there in an emergency. That person may use it once a year, or only
once, after something has gone wrong. So the console has to explain itself after a year in a
drawer. The person holding it has three jobs and no others: keep it, check before approving, and
say if it's lost. Everything technical (the Safe, the signer, gas, execution) stays with the
person who set it up, or with a named helper when that person can't. The console's screens, a
printed card and one QR code carry the rest.

## Who's who

| | Who | What they do |
|---|---|---|
| **The organizer** | Technical. Today, you. | Shapes the Safe, prepares each console, adds each key as an owner, proposes and executes transactions, writes the card |
| **The keyholder** | Anyone you trust. Not technical. | Holds one console and its key. Approves or rejects when asked. Says if it's lost |
| **The other owners** | The rest of the Safe: a hardware wallet, another keyholder, a paper seed | Approve as usual. Check a new key before adding it ([COSIGNERS.md](mainnet/COSIGNERS.md)) |
| **The helper** | Technical, named on the card. A friend, or a lawyer with an owner key | Proposes and executes when the organizer can't: the emergency path doesn't depend on the organizer |

## What we ask of a keyholder

**Their three jobs:**
1. **Keep it** somewhere safe and findable, with its card. Like a spare house key, not like cash:
   it alone can't move money.
2. **Approve only what someone told you about, by voice.** Plug it in, read every page, and hold
   Sign only if it matches what you were told. Anything else: Reject, and call.
3. **Say if it's lost**, or if it was out of your hands. The other owners swap it out.

**What they never need:** a seed phrase or a backup (there's nothing to write down), a laptop, an
app, gas, crypto knowledge, or a firmware update. They never execute anything, and nobody should
ever ask them to send funds to the console's address: it's a signer, not a wallet.

**What they should expect:**
- Being asked rarely, and always by someone they know, by voice. An urgent request that arrives only
  by text or email is the attack this protects against ([COSIGNERS.md](mainnet/COSIGNERS.md)).
- A check twice a year (below), five minutes each.
- The console shows the Safe's name and address. Anyone who finds it can look the Safe up, so keep it as
  private as a bank statement.

## Three ways to give someone a key

| | A. Ready to use | B. Made at the handover | C. A passkey in the browser |
|---|---|---|---|
| **What arrives** | A console with its key made, sealed, pinned, an owner of the Safe | A console and a branded key with no key inside yet | Nothing: the console page on their phone or laptop ([BROWSER.md](guide/BROWSER.md)) |
| **Their part** | Plug in, Wi-Fi by phone | Plug in, Wi-Fi, then make and seal their key: two arms and two holds, with you beside them | Make a passkey, share its link |
| **What they trust you for** | Everything about the setup. A dishonest bench can plant a known key before the seal ([BRANDED-KEYS.md](BRANDED-KEYS.md)) | Only the console's firmware. Nobody chose their key, you included | Their passkey provider (it syncs to their account) |
| **Exists today** | Yes, with laptop tools (chip 3's path) | Partly: the claim (U1–U5) runs in the emulator on the Pico. Not on the Feather, and key 0000 doesn't exist yet | Yes |

**Recommended:**
- **A for family**, where the organizer is the person they'd trust anyway. The Safe still survives
  a lost console or a stolen key. Hold the handover in person so their first approval is with you
  there.
- **B for anyone who should be a check on you**: a co-founder, a club treasurer, a second
  maintainer ([GOVERNANCE.md](GOVERNANCE.md)). Their key is only independent if they made it.
- **C as a second key**, or for someone who will never keep a device.

## The Safe it joins

Before any console goes out:
- **No one person holds the threshold.** Your own keys together stay below it. 2 of 3 is the
  smallest useful shape: your wallet, your console, their console.
- **Someone besides you can propose and execute.** Only an owner's wallet (or a delegate) can
  propose, and the console never proposes or executes. If every wallet key is yours, the Safe
  can't act without you. Give the helper a wallet owner key, or a delegate.
- **At least one owner isn't a PicoQuorum**, as the README says. The 3-of-5 in
  [KICKOFF.md](KICKOFF.md#target-multisig-shape-for-reference) is the long-term shape.
- **A drill before real money:** one small transaction that every keyholder approves.

## The journey

### 1. Prepare (the organizer, at home)

1. The key: made, sealed and checked on the laptop (A), or a branded key left for the handover (B).
2. The console image, the Safes it watches, and the keyholder's name. Wi-Fi stays empty: they set
   their own.
3. **A only:** pin the key, deploy its signer, and add it as an owner. Today that's laptop
   commands ([SETUP.md](guide/SETUP.md) steps 4–6). Proposed: scan the console's QR code with your
   phone, and the app does the signer and the owner change from there (below).
4. Print the card.

### 2. Hand over (together, one short visit)

1. **Plug in.** Wi-Fi setup opens: their phone scans the QR, picks their network, types its
   password.
2. **The console says whose it is:** "Sam's key for the Family Safe. 2 of 3 keys needed."
3. **B only:** they make and seal their key, then you scan its QR and add it from your phone.
4. **The first approval:** you propose a test (0 ETH to the Safe itself) and phone them, even
   though you're in the same room. They read it, hold Sign, and see "Signed: 2 of 3".
5. **The card** goes in the drawer with the console.

### 3. When asked to approve

They get a call: "There's a transaction on the Family Safe. It sends 0.5 ETH to the new account
at the bank." They plug the console in. Home shows **1 waiting**. They open it, page through, and
compare it with what they were told. Then they hold Sign, or Reject and call back. Executing it is
the organizer's (or the helper's) job, in the app.

### 4. Twice a year: the check

Plug in and choose **Check**. In one screen, with nothing signed:
- the key answers, and it's the pinned one
- **"Used 0 times since 22 Oct"**: the chip's counter only goes up, so a console borrowed and
  misused shows it here
- still an owner of the Family Safe, 2 of 3
- the service answered, and its certificate was checked

Anything else: call the organizer. Organizers can make this a drill instead: a 0 ETH test approved
by every keyholder each spring.

### 5. Lost, stolen, or out of their hands

They call the organizer or any other owner. The other owners propose **Replace owner** in the app
(it's red on every console) and execute it. Until then they treat the lost key as able to sign:
one signature, never the threshold.

### 6. In an emergency

The organizer can't act: ill, lost their keys, or gone. The card's back says what to do:
1. Call the helper, and the other owners by name.
2. The helper proposes what's needed, often moving everything to a new Safe the family controls.
3. Each keyholder approves it after a **voice** call with the helper or another owner. This is the
   moment an attacker would pick, so the voice rule matters most here.
4. The helper executes it in the PicoQuorum app. The Safe web app can't execute a contract
   signature once the threshold is 2 or more ([COSIGNERS.md](mainnet/COSIGNERS.md#3-execution)).

## What the console says, state by state

Each state talks to the keyholder first, in plain words, and shows the organizer what to do next.
Chip terms and file names move to the Device screen. Drafts for the Feather:

| State | Today | Proposed |
|---|---|---|
| No Wi-Fi saved | Wi-Fi setup, QR | as today (on the Feather, its fixed hotspot isn't checked on the board yet) |
| No key in | "No chip" | **Plug in your key** · the slot it goes in · D2 Check again |
| Another key | "Not the pinned key" | **This isn't Sam's key.** This console is set up for key `9ba1…`. · D0 Back |
| Key ready, no Safe | **built:** "Your key is ready" · D2 Code | **Your key is ready.** Next, it's added to a Safe. · Show this to the person setting it up. · D2 Show the code |
| A Safe, not an owner yet | **built:** "Not an owner yet" on home, and Key past Owners and Device | **Waiting to be added** to the Family Safe. · D2 Show the code |
| Ready | home | **Family Safe** · 2 of 3 · Nothing to sign |
| Something waiting | home, a count | **1 waiting** · D2 Open |
| A review | pages, hold | as today, with a first page that asks: **Expecting this?** If nobody told you about it by voice, Reject. |
| Check | not yet | the four lines above · D0 Back |
| About | not yet | **Sam's key for the Family Safe.** 2 of 3 keys are needed. It can't move money alone. Lost it? Tell Jason. · D1 Practice |

**Practice** walks a built-in example transaction through the real review screens, then says:
"That's how it works. Nothing was signed." Useful at the handover, and after a year in a drawer.
It never asks the chip for anything.

## The QR code

The console shows a QR code only when there's a next step, and the code says only public things:
- **The set-up link** (proposed): `https://picoquorum.app/app/#/k/03…`, the key's 33-byte compressed
  public key, 97 characters. That's a version-5 code, 37 modules a side, 111 px at 3 px a
  module, which fits the 135 px screen. The organizer's phone opens the app on a page that:
  - works the owner address out again and draws its picture, to compare with the console's
  - checks the passkey factory's `getSigner` agrees
  - deploys the signer from any wallet (the app's deploy links do this today, as `#/signer/x/y`,
    169 characters: too long for this screen)
  - proposes **Add owner** to a Safe the wallet owns
- **The owner address alone**, for the Safe app's own Add owner: 42 characters, a version-3 code,
  29 modules, 116 px at 4 px a module.

**The link should be the default.** A QR with a bare address invites a wallet to *send* to it, and
the owner address is a signer contract, not a wallet. The link's page says so before anything
else, as the claim's last screen does.

The code goes one way, console to phone. Nothing comes back over USB or Wi-Fi, so it's the
air-gapped path for a key set up far from the organizer's laptop. The phone sees only public values,
the same ones a co-signer checks.

## The card

Printed by the app from the Safe's live state, so it's right on the day it's printed.

**Front, for the keyholder:**
- what it is: "Your key for the Family Safe. 2 of 3 keys are needed. It can't move money alone."
- the three jobs, and the voice rule
- the console's picture (the key's blockie) and the last 4 characters of its address
- plugging it in: any USB-C charger, and the Wi-Fi steps

**Back, for an emergency:**
- the helper and the other owners: names and phone numbers (on paper only, never on the console)
- the Safe's name, chains, threshold and address, as a QR to the app
- "Anyone asking you to approve something urgently by text or email: call first."

## What exists today

| | Today | Where |
|---|---|---|
| Wi-Fi setup by phone | yes; the Feather's fix is emulator-checked only | `wifisetup.py` |
| Make and seal a key on the console | yes, C1–C10 (chip 3, on the Feather) | `provision.py`, `setup_s.py` |
| The keyholder makes their key (the claim) | Pico, emulator only; needs key 0000 | `claim.py`, [BRANDED-KEYS.md](BRANDED-KEYS.md) |
| Pin the key | laptop: `tools/fw pin` | |
| The Safes it watches | laptop: `tools/quorum live pico`, or `secrets.py` by hand | |
| The owner address on the console | at C7, and the Pico's This key screen; the Feather has no key screen yet | |
| A QR of the key | **the Feather's Key screen**: the owner address, EIP-55 (2026-10-22, emulator) | `quorum_ui_s.draw_key` |
| Deploy the signer | laptop, or the app's deploy link from any wallet | `#/signer/x/y` |
| Add owner, replace owner | the app (prefilled: `#/safe/<chain>/<Safe>/new/add/<owner>`), or the Safe app | `web/src/propose.mjs` |
| Execute | the app, or `tools/quorum live exec` | |
| A use the console didn't make | flagged on home | `quorum.py` |
| Whose key it is, About, Check, Practice, the card | no | |

## What to build, in order

Each firmware step is a new console release fingerprint. Chip 3 is the test case throughout: it is
sealed, and it isn't an owner of anything yet.
1. **The Feather's key screen and its QR**, with the no-Safe and not-an-owner states rewritten
   around it. First the owner address, since it needs nothing new from the app. **Built
   2026-10-22**, in the emulator ([shots 23–27](quorum-ui/feather/README.md)); the code decodes
   (CoreImage) to the address on the screen. Not yet on the board.
2. **The set-up link** in the app (`#/k/<compressed key>`: compare, deploy, Add owner) and as the
   console's QR code. Then chip 3 joins Safe `0x5617…DC41` that way, from a phone, without a laptop.
3. **Whose key it is:** a keyholder's name in `secrets.py`, the About screen, and the card page in
   the app.
4. **Check:** the four lines, with the date of the last check (the console has the date once it's
   on Wi-Fi).
5. **Practice.**
6. **The claim on three buttons**, for B. It needs key 0000 first ([KEY-RUNBOOK.md](KEY-RUNBOOK.md)).

## Decisions for you

1. **The default for someone else's key:** A, ready to use (recommended for family), or B, made at
   the handover (needs step 6)?
2. **The keyholder's name on the console:** names only, phone numbers on the card (recommended)?
3. **The "Expecting this?" page:** on every review on a keyholder's console, or only for red ones?
4. **The QR:** the set-up link (an app change, recommended), the address only, or both?
5. **The helper:** a wallet owner key in the Safe, or a delegate who can propose but not approve?
