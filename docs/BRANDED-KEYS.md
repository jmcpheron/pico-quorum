# Branded keys: the bench brands the chip, the user makes the key

> **A proposal (2026-10-07). The bench half is built for a spare chip only** ([the first
> build](#the-first-build-a-spare-on-build-1)); claim and key 0000 are not. It answers LAUNCH.md section 6, "decide the
> brand and quorum record before sealing chip #3", and says what a user does with a branded key.
> The screens below are mockups in the console's own look (the fonts, colours and drawing kit of
> `firmware/quorum_ui.py`), drawn on the emulator. No firmware has these steps yet. Locks are permanent
> ([LOCKING.md](LOCKING.md)), so every new step goes on a spare chip first.

## The idea in one paragraph

Today the bench runs the whole ceremony, C1–C10 ([PROVISIONING.md](PROVISIONING.md)). The chip
leaves with its key made, sealed and recorded. The user has to take the bench's word that nobody
chose that key.

This proposal splits the ceremony in two:
- **The bench brands the chip.** It writes PicoQuorum's config and a signed brand record, then locks
  the config and data zones. It makes no key.
- **The user's console makes the key.** It checks the brand, makes the key inside the chip, and
  seals it.

After the bench's data lock, the only thing that can put a key into slot 0 is the chip's own
GenKey. So nobody chose the user's key, the bench included.

```mermaid
flowchart LR
  subgraph Bench["The bench (the project)"]
    B1[B1 pre-flight] --> B2[B2 write quorum v2] --> B3[B3 lock config<br/>PERMANENT]
    B3 --> B4[B4 brand record<br/>OTP + slot 8] --> B5[B5 brand key signs] --> B6[B6 lock data<br/>PERMANENT] --> B7[B7 check + label]
  end
  B7 -- "key-c in a bag:<br/>label + card" --> U1
  subgraph Console["The user's console"]
    U1[U1 check the brand] --> U2[U2 make your key] --> U3[U3 test signatures] --> U4[U4 seal it<br/>PERMANENT] --> U5[U5 owner address]
  end
  U5 --> A[The app: deploy the signer,<br/>starter Safe, test ETH]
```

<img src="branded-keys/lifecycle.svg" width="100%" alt="A branded key's life: factory, then configured at B3 on the bench, then branded at B6, when it ships with no key, then claimed at U4 by the user's console. Each step is permanent.">

## Why split it

| Who makes the key | What the user must trust | What can go wrong |
|---|---|---|
| **The bench, as today** | The bench didn't plant a key. While the data zone is open, a plaintext PrivWrite can put a known key into slot 0 before the slot lock, and nothing on the chip shows it afterwards (LOCKING.md). | A dishonest or compromised bench keeps a copy of every key. |
| **The user, from a factory chip** | Nothing. | The user runs every permanent step, with CRCs and silicon unknowns. A slip bricks a chip. 608C bring-up isn't done (LAUNCH.md section 6). |
| **Split (proposed)** | The brand says the bench locked the config and data zones. The user's console checks both locks itself. | After B6, PrivWrite on slot 0 is refused by the config (WriteConfig `0010`: GenKey only). The user's GenKey replaces anything that was there. |

The split keeps the risky steps on the bench, where they are practised. It gives the user the
one thing that matters: a key that only their console asked for.

## On the bench

### The rig

<img src="branded-keys/bench.svg" width="100%" alt="The branding bench: a Pico 2 W running the brand image, the chip being branded on I2C0, key 0000 on I2C1, a laptop with tools/fw, and a label printer.">

- **One Pico with two key-c receptacles:**
  - **The brand key**, PicoQuorum key 0000. It is a key-c board like every other, plugged in for good.
  - **The chip being branded**, an ATECC608C on a key-c board.
  - Both ATECCs answer at 0x60, so each gets one of the Pico's two I2C controllers. The driver
    already takes its pins as arguments (`atecc.ATECC608(sda, scl)`). The bench board needs the
    second receptacle wired.
- **A new `brand` image.** It holds B1–B7 and the brand signature. Like the ceremony image, it
  never goes on a user's console. It would be a fourth image in `firmware/manifest.json`, beside
  console, ceremony and dual, checked by `test-vectors/manifest.mjs`.
- **A label printer** on the laptop. It prints from what B7 reports.
- **The local inventory** (gitignored `chips/`), as for the chips so far (mainnet/RUNBOOK.md).

### The steps

B1–B3 are C1–C3 today, with a new table. B6 is C9. The new parts are B4, B5 and B7.

| Step | What | Permanent? |
|---|---|---|
| B1 Pre-flight | As C1. It also accepts the 608C revision, which `chipcfg.REVISIONS` lacks today. | no |
| B2 Write quorum v2 | quorum v1 with one change: slot 8 can be read in the clear (below). | no, rewritable |
| B3 Lock the config | With the CRC of the reviewed v2 table, as C3. | **yes** |
| B4 Brand | Zeros into slots 1–15 except 8. The brand record goes into OTP. No key is made. | until B6 |
| B5 Countersign | The brand key signs the record. The signature goes into slot 8. | until B6 |
| B6 Lock the data zone | With the CRC of every slot that is not a private key, plus OTP, so the brand is in the CRC. | **yes** |
| B7 Check + label | Read everything back, verify the signature, slot 0 empty, counter 0 = 0. Print the label. | read-only |

| B1: pre-flight | B3: lock the config | B4: write the brand |
|---|---|---|
| <img src="branded-keys/b1-preflight.png" width="240" alt="B1 A factory chip: ATECC608C self-test ok, nothing locked yet, factory table saved. The chip graphic is empty, both padlocks open."> | <img src="branded-keys/b3-config-lock.png" width="240" alt="B3 Lock the config, a red page: slot rules fixed for good, the chip checks the table's CRC first. The cfg padlock is ringed in red."> | <img src="branded-keys/b4-brand.png" width="240" alt="B4 Write the brand: PicoQuorum, quorum v2, key 0042, batch 3, zeros elsewhere; no key is made here. The OTP area now shows the mark and 0042."> |
| **B5: key 0000 signs it** | **B6: lock the data zone** | **B7: ready to ship** |
| <img src="branded-keys/b5-countersign.png" width="240" alt="B5 Key 0000 signs it: PicoQuorum key 0000, the brand key, on I2C1; signature into slot 8. Slot 8 fills in blue."> | <img src="branded-keys/b6-data-lock.png" width="240" alt="B6 Lock the data, a red page: the brand and every slot freeze for good; then only the chip's own GenKey can fill slot 0. The data padlock is ringed in red."> | <img src="branded-keys/b7-ready.png" width="240" alt="B7 Ready to ship: brand signed by key 0000, locked 00/00 and checked, no key inside, slot 0 empty. Both padlocks shut. Print the label 0042."> |

B2 (writing the table) looks like B4. For comparison, today's ceremony screens use the 8-pixel framebuf
font ([firmware-production/shots](firmware-production/shots/)):
[C1 pre-flight](firmware-production/shots/60-ceremony-C1.png),
[C3 lock the config](firmware-production/shots/64-ceremony-C3.png),
[C9 lock the data zone](firmware-production/shots/76-ceremony-C9.png).

### The technical decisions

The whole chip, as the bench leaves it and the user finishes it:

<img src="branded-keys/chip-map.svg" width="100%" alt="quorum v2 on an ATECC608C. Config zone, 128 bytes, locked at B3 with a CRC. Data zone: slot 0 is your P-256 key, GenKey only, LimitedUse, sealed at U4; slot 8, 416 bytes, holds the brand signature, readable and never written; slots 1 to 7 and 9 to 15 are dead, zeros, never read or written; locked at B6. OTP zone, 64 bytes: the brand record, frozen at B6.">

**1. Where the brand lives: OTP and slot 8.**
- **Why not OTP alone:** the 64-byte OTP zone is full with today's record, and a signature alone is
  64 bytes.
- **The two options from LAUNCH.md:**
  - **A.** A v2 OTP record with the signature kept off-chip, in the registry. The config table stays
    quorum v1. But only the app could check the brand, over the network, and the console couldn't.
  - **B.** A quorum v2 table with slot 8 (416 bytes) readable in the clear and never writable. The
    signature lives on the chip, and the console checks it at plug-in with no network.
- **Proposed: B.** U1 is the console checking the brand before the user does anything permanent.
  - Slot 8's row would be the dead slots' row with IsSecret cleared (SlotConfig about `0x8F1F`,
    KeyConfig `0x001C`).
  - `tools/check_config` must decode it independently before the table is fixed.
  - Every other slot stays as in quorum v1.

**2. What the brand says.** The OTP record, version 2. It has no key fields, because there is no key
yet:

| Offset | Size | Content |
|---|---|---|
| 0 | 2 | `PQ` |
| 2 | 1 | Version 2 |
| 3 | 1 | Profile (2 = quorum v2) |
| 4 | 9 | Serial |
| 13 | 4 | Revision (608A, B or C) |
| 17 | 2 | Config CRC (the one B3 locked with) |
| 19 | 2 | Batch |
| 21 | 1 | Bench id (0 for now: key 0000's own bench) |
| 22 | 3 | Sequence on that bench (42, printed as 0042) |
| 25 | 4 | Date |
| 29 | 4 | Bench build (the `brand` image's fingerprint, first 4 bytes) |
| 33 | 16 | Brand key id: SHA-256(qx‖qy)[:16] of the brand key |
| 49 | 15 | Zeros |

<img src="branded-keys/brand-record.svg" width="100%" alt="How a chip gets its brand: the OTP record is hashed with the prefix PicoQuorum brand v1, key 0000 signs the digest, and its r and s, 64 bytes, go into the start of slot 8, the rest zeros.">

Slot 8 holds the brand signature, with room kept for a bench certificate:
- **Bytes 0–63:** the brand key's (r, s), low s.
- **The digest it signs:** `SHA-256("PicoQuorum brand v1" ‖ OTP record)`.
- **Bytes 64–223: the bench certificate, all zeros in version 2.** It is kept for a second bench
  (point 5): that bench's id, its key's public half (qx‖qy), and key 0000's signature over both.
  While it is zeros, the brand key must be key 0000 itself.
- **Bytes 224–415:** zeros.

The console checks four things:
- the signature, under the pinned brand key
- that the record's serial, revision and config CRC match the chip in front of it
- that both zones read locked
- that the bench id is 0 and the certificate bytes are zeros. Until a second bench exists, any other
  value is refused, not guessed at.

**3. The brand key: a PicoQuorum key, number 0000.**
- **A PicoQuorum key brands the others.** The brand key is the product itself: a key-c board with an
  ATECC608C.
- **Not a laptop key.** A brand key in a file can leak, and a leaked brand key brands fakes. Key
  0000's private key was made in its chip and can't be read out, like every PicoQuorum key's.
- **It has today's whole ceremony, run by the project on the bench.** That is quorum v1, C1–C10
  ([PROVISIONING.md](PROVISIONING.md)), not the split below. It is the one key that can't be branded
  by another, so its record and the ceremony log are published instead.
- **Its use counter is a public tally.** LimitedUse counts every use in counter 0, which only goes
  up. Key 0000 signs once per chip branded. Its other uses are its own checks, and each public-key
  read once its data zone is locked (PROVISIONING.md). The bench logs those. A counter far above the
  chips in the registry plus the logged uses means it signed something else.
- **Never a Safe owner, and the brand image signs only brand digests.** Their fixed prefix keeps
  them apart from a WebAuthn digest.
- **It can't prove it is genuine silicon.** An ATECC608 has no factory certificate (point 7). What
  stands behind key 0000 is the project: its published record, and its key pinned in the firmware.
- **Its public half is pinned in `quorum_cfg.py`.** That is a firmware change and a new release
  fingerprint. It is also published in `docs/registry/`. Once the project Safe holds picoquorum.eth, a
  text record such as `org.picoquorum.brand` could name it, so changing the brand key would need the
  project Safe's quorum.
- **Rotating it:** the firmware lists brand keys by id. A retired key stays listed for the batches
  it branded.

**4. The label number and the brand picture.**
- **The number is a bench id and a sequence.** It is 1 byte for the bench and 3 bytes for the count
  on that bench, which is 256 benches and about 16.7 million chips each.
  - **Bench 0 prints just the sequence:** 0042. That is the only bench for now.
  - **Any other bench prints its id first:** B2-0042.
  - It goes on the label, in the record, and on the console's U1 screen.
- **The number is a name, not the security.** The chip's factory serial (9 bytes, set by
  Microchip) is what is unique, and key 0000's signature is what makes the brand hold. The number
  is how people refer to the chip: on the label, in the registry, in a support thread.
- **A number used up by a chip that fails** after B5 and before the B6 lock is logged with the
  reason. The registry lists it, so the gap isn't a mystery.
- **Sequential, on purpose:**
  - **Pros:** short and easy to compare, no collisions on one bench, and gaps are easy to spot.
  - **Cons:** one counter per bench, a burned number when a chip fails, and it shows how many were
    made. The bench id is what keeps one counter from limiting the project to one bench.
- **The picture:** the blockie of the brand digest's first 20 bytes. B7 and U1 both draw it, so the user
  matches the label to the chip by eye, as they already do for the verify code.

**5. More than one bench, later.** Nothing is built for this yet, but the record and slot 8 leave
room for it. Both are written once and frozen, so the room has to be there from the first chip.
- A new bench gets its own brand key, itself a PicoQuorum key, and a bench id.
- Key 0000 signs that bench's certificate: its id and its key's public half. The certificate goes
  into slot 8's bytes 64–223 of every chip that bench brands.
- **The console then checks two signatures:** key 0000's over the certificate, then the bench key's
  over the record.
- **The firmware still pins only key 0000,** so a new bench needs no firmware release.
- **A bench whose key leaks** is revoked in the registry without touching the others.
- **Key 0000 then signs only certificates.** It could live in a drawer between benches.
- **Further off, and not proposed:** numbers taken from a hash of the serial, with no counter;
  project Safe approval for each bench key; or other brands beside PicoQuorum's (TRADEMARK.md).

**6. The list.**
- The registry ([registry/README.md](registry/README.md)) covers Trust M only today, and `tools/fw
  attest` refuses an ATECC608.
- Each batch would add `docs/registry/brands/batch-<n>.json`: serial, number, OTP record and
  signature. All of it is public.
- A claim (below) adds the owner address to that serial's entry.
- One owner per serial: a second claim on the same serial is the sign of a copied brand.
- An onchain Merkle root (LAUNCH.md) can come later. It would be PicoQuorum's first contract.

**7. What the brand proves, and what it doesn't.**
- **It proves** the project's brand key signed this serial's record, with this config CRC, and that
  the chip in the console has that serial and that config, locked.
- **It doesn't prove** the physical chip is the one the bench branded.
  - An ATECC608 has no factory certificate. A fake chip, or a microcontroller pretending to be one,
    could copy a real chip's serial, OTP and slot 8.
  - What limits that: one claim per serial in the registry, and the label number in the user's
    hands.
  - **A stronger option, not proposed yet:** an attestation key in slot 1. The bench would make it
    and seal it, and the brand would certify it. At U2, the chip would sign a statement about slot 0's
    new key with it (GenKey's digest mode, then an internal Sign). That would prove slot 0's key was
    made in a branded chip. It needs driver commands that don't exist, and the internal message format
    must be confirmed against the datasheet and a spare chip. It is a later profile.
- **It says nothing about the user's key.** The user's console made that.

**8. The images.**
- **On the bench:** `brand` (B1–B7, the brand signature, both data locks).
- **On the user's console:** today's `dual` image routes a fresh chip to the ceremony. It would
  route a quorum v2 chip with both zones locked and slot 0 unsealed to **claim** (U1–U5).
  - Claim can only make slot 0's key and seal it. It can't write config, OTP or slot 8, and it can't
    lock a zone.
  - The console image still carries none of it (AGENTS.md rule 2).
- **The console image gets read-only brand lines** on its Chip page: "PicoQuorum key 0042, batch 3,
  brand checked".

**9. The user's gates.** Today a permanent step needs `ALLOW_*` set from the laptop, the B+Y arm,
and A held for 3 s.
- **Proposed for claim:** keep the arm and the hold, and drop `ALLOW_*`. The state check is the gate:
  claim offers its two writes only on a chip that is branded, locked 00/00 and unsealed. A user
  without a laptop can't edit `secrets.py`.
- **This loosens a guard, so it is for review, not assumed.**
- **After U5, claim writes the pin** (`QUORUM_EXPECT`) itself, as `tools/fw pin` does from the laptop
  today.

### What only silicon can settle (a spare 608C, before chip #3)

- GenKey on slot 0 after the data lock, on a slot that never had a key. LOCKING.md says the data
  lock doesn't stop GenKey, but no chip here has run it in that order.
- PrivWrite on slot 0 after the data lock: refused. Try it only on the spare.
- Slot 8 reads back in the clear after the lock, and its bytes are in the data CRC.
- The 608C's revision bytes and factory table (C1 knows 608A and B only).
- How long U1 takes on the Pico: one P-256 verify. The Trust M certificate check, also one verify,
  takes about 1.4 s.

## The chip on every screen

Every step, on the bench and on the user's console, shows the chip under its header, so the wizard
reads as the chip filling in:

<img src="branded-keys/chip-stages.png" width="240" align="right" alt="The chip graphic at four stages: 1 Factory, everything dashed and both padlocks open; 2 Branded, the OTP shows the PicoQuorum mark and 0042, slot 8 is blue, both padlocks shut, slot 0 still dashed; 3 Key made, slot 0 green; 4 Sealed, slot 0 green with a white border.">

- **The package** names the part, ATECC608C. Once branded, the PicoQuorum mark sits beside it.
- **The padlocks** for the config and data zones, open or shut.
- **The OTP zone:** dashed while empty, then blue with the mark and the key's number.
- **The sixteen slots:** 0–7 on top, 8–15 below.
  - Slot 0 is dashed green while it waits for the user's key, half green while it is made, and green
    once made. A white border means sealed.
  - Slot 8 turns blue when key 0000's signature goes in.
  - The dead slots go solid grey when the bench zeroes them.
- **What the step writes is ringed:** blue for the bench's writes, green for the user's key, red for
  a permanent lock.
- **On a chip whose brand fails,** the OTP shows "brand ?" in red.

<br clear="right">

## The user

### What arrives

- **A key-c board** (USB-C, ATECC608C) with the PicoQuorum mark on its back.
- **A bag label:**

  <img src="branded-keys/label-0042.svg" width="420" alt="Proposed label: PicoQuorum key 0042, batch 3, ATECC608C, the serial's last 8 characters, the brand picture, a QR code, and: No key inside yet. Your console makes it.">

  The picture is the same blockie the bench drew at B7 and the console draws at U1. The QR code
  opens the app's check page for this serial. That page doesn't exist yet: `#/brand/<serial>` is a
  proposed route.
- **A card** with the five steps below and one warning: if the console says the brand doesn't
  verify, stop.

### The claim, on the console

The user needs a PicoQuorum console, built or bought, on a release that carries claim. The Device
screen shows the release fingerprint, to compare with the README's build table.

1. **Plug the key in.** The console sees a branded, unclaimed chip and says so: "A PicoQuorum key.
   No key inside it yet." A starts.
2. **U1 Check the brand.** The console checks it with no network. Check that the label's number
   and picture match the screen.
3. **U2 Make your key.** B+Y to arm, then hold A for 3 s. You can make it again until U4.
4. **U3 Test signatures.** Two digests, signed and checked on the console.
5. **U4 Seal your key.** Arm, hold. Permanent.
6. **U5 Your owner address**, with its blockie. The console pins the chip and restarts into the
   console.

| Plug in | U1: the brand checks | U2: make your key |
|---|---|---|
| <img src="branded-keys/u0-welcome.png" width="240" alt="New key: the PicoQuorum mark, A PicoQuorum key, key 0042, batch 3. No key inside it yet: this console makes your key in the chip, in about a minute. A Start, Y Not now."> | <img src="branded-keys/u1-brand-ok.png" width="240" alt="Check the brand: Made by PicoQuorum. Signed by PicoQuorum key 0000, locked at the bench, never used, 0 signatures. Your label says 0042, with the brand picture. A It matches, Y It doesn't."> | <img src="branded-keys/u2-make-key.png" width="240" alt="Make your key: your key is made inside the chip. What this key is: signs your Safe's approvals; can't hold ETH, tokens or funds; can't be copied or read out. Armed, hold A for 3 s."> |
| **U3: test it** | **U4: seal it** | **U5: ready** |
| <img src="branded-keys/u3-test.png" width="240" alt="Testing your key: two test signatures, checked here. Nothing leaves this console."> | <img src="branded-keys/u4-seal.png" width="240" alt="Seal your key: Permanent. After this, your key can never be changed or replaced. Lose the chip, and your Safe's other owners swap it out. Hold A, the bar in red."> | <img src="branded-keys/u5-owner.png" width="240" alt="Your key is ready: the Safe owner address and its blockie. A signer, not a wallet: don't send ETH or tokens here. Funds go to your Safe."> |

### Plain words on the screen

The claim says what the key is in words a new owner can act on, not in chip terms:

| The screen says | Why |
|---|---|
| "No key inside it yet. This console makes your key." | The point of the split: the user's console makes the key. |
| "Signs your Safe's approvals." | All the key does. |
| "Can't hold ETH, tokens or funds." | The owner address is a signer contract, not a wallet (LAUNCH.md section 4). People will try to send funds to anything that looks like an address. |
| "Can't be copied or read out." | No seed phrase to write down, and nothing to back up. |
| "Never used: 0 signatures." | The use counter starts at 0, so the user sees nobody signed with this chip before them. |
| "Lose the chip, and your Safe's other owners swap it out." | Recovery is the Safe's threshold, not a backup. |
| "A signer, not a wallet. Don't send ETH or tokens here. Funds go to your Safe." | The same warning again, beside the address itself. |

**When the brand doesn't check out**, claim stops before anything is written:

<img src="branded-keys/u1-brand-bad.png" width="240" alt="Check the brand, on a red page: Not a PicoQuorum key. Its brand doesn't verify. Nothing was written to it. Don't use it. Tell the project the number on its label.">

Claim also refuses:
- a chip whose slot 0 is already sealed (claimed before)
- a chip whose zones aren't both locked
- a chip whose config CRC isn't the one in its record

### After the claim, in the app

The onboarding idea: a 1-of-1 starter Safe on Base Sepolia, with the project paying the gas.

1. **Deploy the signer.** The owner address is a `SafeWebAuthnSignerProxy` that isn't deployed
   yet. Any wallet can deploy it. A project relayer could too.
2. **A starter Safe**, 1 of 1, on Base Sepolia (LAUNCH.md section 4, "A new passkey gets a starter
   Safe"). Its address is the user's address for receiving funds.
3. **Test ETH from the project.** The project's own Safe tops up a faucet key, each top-up approved on
   consoles. The faucet funds a starter Safe once per claimed serial, so the brand doubles as the
   faucet's guard.
4. **Each send:** propose, check it on the console, hold Sign, and a wallet or the relayer sends it.
   The chip can't send a transaction itself: its key is P-256, and it signs only the Safe hash.
5. **Next:** add a second owner and raise the threshold to 2. A 1-of-1 is where you start, not where
   you stay.

The relayer and the faucet are each a new service and a new network call. AGENTS.md says to ask
before building either.

### The browser console

A passkey user has no chip, so there is no brand and no claim. They go straight to the starter
Safe. The brand only ever shows on hardware keys.

## What it would take

In order. Each item that changes firmware is a new release fingerprint.

1. **A spare 608C:** settle the silicon questions above.
2. **The quorum v2 table** in `chipcfg.py`, decoded by `tools/check_config`.
3. **`provision.py` split** into bench steps (B) and claim steps (U). Extend
   `test-vectors/run-ceremony.mjs` to walk both halves on the virtual chip, with a reboot after every
   step, plus the claim refusals above.
4. **The brand key:** key 0000 through C1–C10 on the bench, the second receptacle wired, its
   record in the registry, its key in `quorum_cfg.py`.
5. **The `brand` image** and the claim route in `dual`. Update `manifest.mjs` for both.
6. **The registry:** batch files, the ATECC entries, and `tools/fw attest` for a 608.
7. **The label:** `tools/board/brand_label.py` draws it today from fixed values. It would take them
   from B7's output.
8. **The app:** the check page behind the label's QR code, and the claim badge.

## The first build: a spare on Build 1

The bench half, B1–B7, runs on a **spare** ATECC608A (chip 5, `0123a431b1490801ee`) to settle the
silicon list above. It is the `brand` image (`tools/fw push brand`): `firmware/brand.py` for the
steps and checks, `firmware/brand_ui.py` for the screens above, built from the same kit as the
mockups.

- **B5 signs with a public test key, not key 0000.** Key 0000 doesn't exist yet. The record says
  bench `0xFF` (number `T0042`), and the brand check refuses it as a brand, so the spare can never
  pass as a branded key.
- **S1–S3 do the claim's key steps on the bench:** GenKey after the data lock, two signatures, the
  slot lock. They are tests, not the claim.
- **Every step's full result goes to `brand-log.txt`** on the board. The screen shows a few lines.
- **Not tested yet: PrivWrite refused after the data lock.** It needs a PrivWrite command, which the
  driver doesn't have.
- `node test-vectors/run-brand.mjs` walks it all on the virtual chip, with the refusals and the knob.

The screens as built, from `node tools/board/shots_bench.mjs` (the emulator's 240 px; Build 1 is
320 wide). The key and owner change on every run.

| B1: pre-flight | B2: written | B3: hold to lock |
|---|---|---|
| <img src="branded-keys/bench/b1.png" width="240" alt="B1 Pre-flight on the built screen: the factory chip, Do it or Back on the knob."> | <img src="branded-keys/bench/b2-done.png" width="240" alt="B2 done: quorum v2 written and read back, the config CRC to compare on the laptop."> | <img src="branded-keys/bench/b3-hold.png" width="240" alt="B3 Lock the config, red card, armed, the hold bar half full in red."> |
| **B5: the test key signs** | **B7: checked** | **S3: seal the spare's key** |
| <img src="branded-keys/bench/b5.png" width="240" alt="B5 Sign the brand: the test key signs, slot 8 ringed. The OTP shows T0042."> | <img src="branded-keys/bench/b7-done.png" width="240" alt="B7 Check it, done: record, slot 8 read in the clear, signature, and more in brand-log.txt."> | <img src="branded-keys/bench/s3-hold.png" width="240" alt="S3 Seal slot 0 on a red card, armed, the hold bar half full."> |

## How these pictures were made

- `node tools/board/shots_brand.mjs` draws the B and U screens and the chip card with
  `tools/board/brand_screens.py`, which uses `quorum_ui.py`'s drawing kit and fonts. It runs a virtual ATECC608 through C1–C4 for a
  real key and owner. The key is new
  on every run, so U4 and U5 change each time.
- `python3 tools/board/brand_diagrams.py` draws the four diagrams, in the brand's colours
  ([BRAND.md](BRAND.md)) with the lockup from `docs/brand/`. Their slot rules are the proposal's: no
  firmware has quorum v2 yet.
- `python3 tools/board/brand_label.py` draws the label with the firmware's `blockies.py` and
  `qrcode.py`.
- The serial `0123e100e1e1e1e1ee` is the emulator's virtual chip. Batch 3 and key 0042 are made
  up.
