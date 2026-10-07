# Branded keys: from our bench to the owner's first Safe

> **Plan, 2026-10-07. Nothing here runs yet.** It builds on the brand-key sketch on the
> `brand-key-docs` branch ([#41](https://github.com/jmcpheron/pico-quorum/pull/41), closed without
> merging: `docs/BRANDKEY.md` and `docs/launch/`), settles some of what it left open, and adds a
> key's first Safe. Every permanent step goes on a sacrificial chip first
> ([LOCKING.md](LOCKING.md)).

## In short

- **Every key we ship is an ATECC608**, the 608C on [key-c](../hardware/key-pcb/key-c-usbc/README.md).
  Decided 2026-10-07. The Trust M stays the project Safe's own key.
- **We brand each chip at our bench.** It gets PicoQuorum's table (quorum-v2), a brand key made
  inside it, and a stamp in its OTP zone. We record the brand key, and the project Safe approves the
  list. The Safe key's slot stays empty.
- **The owner makes the Safe key at home,** on their own console, and seals it. Then the brand key
  signs a statement the chip composes itself: this key is slot 0's, on this chip, under these rules,
  and sealed. Anyone can check it against the approved list.
- **The statement earns a first Safe:** a 1-of-1 on Base whose only owner is the new key. The
  project pays to deploy it and gets no control over it. It is the Safe the owner grows into a 2 of 3.

## What changed from the sketch

- **No owner record on the chip** (the sketch's slot 9). The owner's ceremony has one permanent
  step, and after it nothing on the chip can change but its counters.
- **The owner's steps run in the dual image.** The console image still can't change a chip.
- **The byte layouts are checked** against Microchip's cryptoauthlib ([below](#what-was-checked-for-this-plan)).
- **A key's first Safe,** paid for by the project, with the statement as the voucher.

## How a key travels

1. **Bench (B1–B10).** We brand the chip and add its number, serial and brand public key to a ring
   file.
2. **Approval.** The project Safe approves the ring, the way it approves a release.
3. **Shipping.** The key goes out with a card: its number, serial and brand-key fingerprint.
4. **Home (H1–H6).** The owner's console makes the Safe key, seals it and gets the statement. It
   shows the owner address, the first Safe's address and the statement as a QR code.
5. **Binding.** The owner scans the QR code. The app checks the statement against the approved
   ring, then shows the badge and the first Safe.
6. **Deploy.** The project deploys the key's signer and the first Safe on Base.
7. **Growing.** The owner adds owners and raises the threshold to 2.

## Why the owner makes the key

A key made at our bench could have signed something before it shipped. The first Safe's address
follows from the key, so anyone who held the chip could pre-sign a payout from that Safe and wait
for it to be funded. A key the owner makes on arrival can't have signed anything.

- **The bench never touches slot 0.** After the data lock (B8) nothing can import a key, and the
  owner's GenKey (H2) replaces whatever slot 0 held.
- **H1 refuses a chip whose slot 0 is already sealed.** That key could have signed already, and it
  can't be replaced.
- **Counter 0 arrives at 0.** Every use of slot 0 raises it ([PROVISIONING.md](PROVISIONING.md)), so
  a key used in transit shows. H2 replaces that key anyway.

Nobody at the bench, us included, can know or choose an owner's key, short of breaking the chip.

## The chip: quorum-v2

| | quorum v1 (chips #1 and #2, keys you build) | quorum-v2 (branded keys) |
|---|---|---|
| Slot 0 | the Safe key: P-256, made by GenKey, external Sign only, no import, LimitedUse. Made and sealed at C4–C6 | the same row. Made and sealed by the owner (H2, H4) |
| Slot 1 | dead | the brand key: P-256, made by GenKey, **internal Sign only**, no import. Made and sealed at the bench (B4, B6) |
| Slots 2–15 | dead | dead |
| OTP zone | the owner record (C8) | the brand stamp (B7) |
| Config lock | C3 | B3 |
| Data lock | C9, after the key is made | B8, before the key is made |

**Slot 1:** SlotConfig `0x2082`, KeyConfig `0x0033`.
- ReadKey `0010`: internal signatures only. No external Sign, no ECDH.
- IsSecret, and WriteConfig `0010`: GenKey only, never Write or PrivWrite.
- KeyConfig is slot 0's: private, PubInfo, P-256, lockable.

`chipcfg.py` gets `QUORUM_V2` with its own fingerprint and asserts, as `QUORUM_V1` has, and
`tools/check_config` decodes it again from the datasheet's tables.

**The brand stamp, 64 bytes in OTP:** `PQ`, version 2, the profile, the serial, the key's number and
ring, the first 16 bytes of the SHA-256 of the brand public key, the date and the bench's build. It
lets a console show "Key 42 · ring 6" with no network. Anyone can read it and copy it, so it proves
nothing. The brand key does the proving.

**No owner record on the chip.** After H4 every zone and both key slots are locked, so no image a
board runs can change anything on the chip but its counters. The record was advisory anyway: the
console always checks the live key.

**What must hold, on the virtual chip and then on silicon:**
- Slot 0 takes GenKey after the data lock. WriteConfig's GenKey bit says so, and the virtual chip
  models it that way.
- Slots can be locked after the data lock: "either before or after" ([LOCKING.md](LOCKING.md)).
- No slot holds a public key, so GenKey's public-key-digest mode has nothing else to describe.

## How the chip vouches for its key

Three commands, run by the owner's console at H5:

1. **Nonce, pass-through.** A 32-byte challenge goes into TempKey. At home it is a fixed tag, so the
   statement doesn't have to carry it. A live check later uses the checker's own challenge.
2. **GenKey, digest mode (`0x08`), slot 0.** The chip works out slot 0's public key and replaces
   TempKey with a SHA-256 over it. TempKey's flags now say it came from GenKey, on slot 0.
3. **Sign, internal mode with the serial (`0x40`), slot 1.** The brand key signs a 55-byte message
   the chip builds itself.

```
TempKey = SHA-256( challenge ‖ 40 08 00 00 ‖ SN[8] ‖ SN[0..1] ‖ 25 zeros ‖ qx ‖ qy )     over 128 bytes
message = TempKey ‖ 41 40 01 00 ‖ A1 2F 33 00 ‖ 50 ‖ 00 00
          ‖ SN[8] ‖ SN[4..7] ‖ SN[0..1] ‖ SN[2..3] ‖ 00 ‖ 00 00                               55 bytes
the brand key signs SHA-256(message)
```

- `A1 2F 33 00` is slot 0's SlotConfig and KeyConfig.
- `50` is TempKey's flags: GenKey, slot 0, a pass-through challenge.
- Byte 52 (the `00` after the serial) is `00` only when slot 0 is locked.

The checker needs no secret, so anyone can run it. It rebuilds both from public values and checks
one signature with the brand public key. It also checks:
- the serial and brand key are in a ring the project Safe approved, and not revoked;
- slot 0's rules are quorum-v2's: external Sign only and no import, so the key can't leave the chip
  or be put into it;
- the flags say GenKey on slot 0, and byte 52 says sealed;
- the owner address follows from `qx, qy` through Safe's passkey factory, as `webauthn.py` works it
  out.

**Why slot 1 can't lie.** It never signs a digest it is handed. Every message starts with a TempKey
the chip made, and carries the rules and the lock of the slot it describes.

**What a statement proves:** the Safe key was made in a chip we branded, can't be exported, and is
sealed. **What it doesn't:**
- who holds the key, or who pressed Sign: that is the Safe's threshold;
- that the silicon is genuine. A blank ATECC608 has no factory certificate, so a counterfeit that
  passed our bench would pass. Buy through JLCPCB or LCSC, and re-read a sample;
- anything beyond the project Safe's word: a Safe that approves a bad ring can badge software keys.

## The bench ceremony

On the ceremony image, at our bench. Permanent steps need the arm and a held A, as C1–C10 do.

| Step | What | Checks | Permanent? |
|---|---|---|---|
| B1 | Pre-flight | as C1, with the 608C: at `0x60`, the revision, zones open, the factory table, self-test. Saves a snapshot | no |
| B2 | Write quorum-v2 | the readback is quorum-v2; shows the config CRC | no |
| B3 | Config lock with CRC | still quorum-v2; slots 0 and 1 decode right | **yes** |
| B4 | GenKey slot 1: the brand key | KeyValid; the public key reads back | until B6 |
| B5 | Brand-key checks | an external Sign with slot 1 is refused; a statement about slot 1 itself verifies | no |
| B6 | Seal slot 1 | the same public key | **yes** |
| B7 | Zero-fill slots 2–15; the stamp into OTP | the data CRC it will need | until B8 |
| B8 | Data lock with CRC | OTP frozen; slot 0 empty, by Info's KeyValid rather than a key read, so counter 0 stays at 0 | **yes** |
| B9 | Record | number, serial and brand public key into the ring file and the inventory; the screen shows the brand key's fingerprint | no |
| B10 | Label and pack | the card: number, serial, the brand key's fingerprint, a QR code to the key's page | no |

A tampered bench laptop could list a brand key it controls. So the bench console shows each brand
key's fingerprint at B9, and before the vote a second machine re-reads a sample of the ring's chips.

## The owner's ceremony

On the owner's console, in the dual image. Today it boots the ceremony for a fresh or half-done chip
and the console for a pinned one ([`main_dual.py`](../firmware/main_dual.py)). It learns one more
case: a branded chip whose slot 0 is open gets these steps.

| Step | What | Checks | Permanent? |
|---|---|---|---|
| H1 | Pre-flight | quorum-v2, both zones locked, slot 1 sealed, slot 0 open, counter 0 at 0; the stamp's number and the brand key's fingerprint, to compare with the card | no |
| H2 | Make the Safe key: GenKey slot 0 | the public key | until H4 |
| H3 | Two test signatures: a digest and a WebAuthn assertion | both verify on the Pico; counter 0 rises | no |
| H4 | Seal slot 0 | the same public key; it signs and verifies | **yes** |
| H5 | The statement | it verifies here under the brand key, and byte 52 says sealed | no |
| H6 | Done | the owner address, the first Safe's address, the statement as a QR code. Pins the chip and adds the first Safe to the console's Safes, as `tools/fw pin` and `tools/quorum live pico` do from a laptop | no |

- **H1 refuses a chip whose slot 0 is sealed,** and says so plainly if counter 0 isn't 0 on arrival.
- **A reboot before H4 goes back to H2.** A key costs nothing until it is sealed, and the board
  seals only a key it has just made and tested.

The console image gets no new powers over the chip. It can't make a key or a statement, and
`quorum.sign_it` stays its only signing site ([`manifest.mjs`](../test-vectors/manifest.mjs) checks both). Statements come from
the ceremony images only.

## Recording the keys

- **A ring file per ring,** `docs/registry/rings/ring-N.json`: each key's number, serial and brand
  public key. It never changes once approved. The rings are the ones in `docs/launch/` on the
  branch: ring n holds the n-bit numbers.
- **The project Safe approves a ring like a release** ([GOVERNANCE.md](GOVERNANCE.md)).
  - A delegatecall to SignMessageLib over the EIP-712 `PicoQuorumRing(ring, root, count, file)`,
    with a note.
  - Each owner's console shows **Approve ring 6 · #32–63 · 32 keys**, and refuses a note that
    doesn't match the digest.
  - `root` is the Merkle root of the entries, so a contract could check one key later without a new
    vote.
- **A revocation** is one more approval, `PicoQuorumRevoke(number, reason)`. It takes the badge
  away. It doesn't take the key out of any Safe: that Safe still has to swap it out.
- **Real rings wait for the project Safe** ([LAUNCH.md](../LAUNCH.md) section 3). Until then,
  rehearse on a fork and on Base Sepolia, with a test Safe as the issuer.

## A key's first Safe

**What the owner gets:** a Safe on Base, 1 of 1, whose only owner is the new key.
- **Its address needs no network.** A Safe's address follows from the factory, the singleton, the
  setup and a salt. With those pinned in `quorum_cfg.py`, the console works it out at H6, and the app
  gets the same one. Funds sent to it before the deploy wait there.
- **The owner address itself can't hold funds.** It is the key's signer, a contract that only checks
  signatures. The Safe is the address to use.

**Who pays.** The deploy is two small contracts: the key's signer (about 110k gas,
[SETUP.md](guide/SETUP.md)) and the Safe, a proxy of Safe's audited singleton. On Base that should
cost cents; measure it on Base Sepolia first. The wallet that deploys gets no control: the owner is
part of the setup the address commits to.

| | How | For | Against |
|---|---|---|---|
| **The project Safe, in batches** (recommended first) | a MultiSend of the two factory calls for each newly bound key, approved on the owners' consoles | no hot key, no server, no new network call; every deploy we paid for is on the project Safe's record | hours or days, not instant; the console has to decode the two factory calls |
| A sponsor service | checks the statement and deploys at once, from a funded key | instant: online, and the Safe is there | a service to run, a hot key, and a new network call for the app or the console: AGENTS.md says ask first |
| Any wallet | the app's deploy button | free for the project; nothing on chain ties the Safe to us | not paid for by the project |

Until the project Safe exists, a maintainer's wallet can send the same batch from `tools/quorum`.

**One per key.** The statement is the voucher. A chip seals one key, so the project pays for at most
one first Safe per key it shipped. A passkey can't be a voucher, since anyone can make thousands, so
a passkey's first Safe (the `claude/passkey-onboarding` branch) stays paid for by its owner.

**Using it.** A Safe can't send its own transactions, and the key can't pay gas. So:
- **The console proposes.** In a 1-of-1 no other owner can, and Safe's service hides unsigned
  proposals. The onboarding branch built this: the console works out the hash from the fields and
  signs in `quorum.sign_it`.
- **A wallet sends it** and pays the gas.
- **Refunds paid by the Safe don't fit.** A gas refund is a red page on the console (`decode._gas`),
  so every transaction would be red. ERC-4337 would mean a new kind of hash for the console to
  rebuild. Hegotá's frame transactions may let a sponsor pay ([HEGOTA-WATCH.md](HEGOTA-WATCH.md)).
  Both are later decisions.

**Growing to 2 of 3** is one batch: add two owners and set the threshold to 2. The onboarding branch
builds it (`growCall`) for a hot wallet and a hardware wallet; a second branded key works too. The
console shows each new owner on a red page, and the new hot wallet sends it and pays. From then on
the README's rule holds: no technology holds a threshold's worth of keys.

**A chip can't be backed up.** A 1-of-1 is lost with its key. So the first Safe is labelled a
starter, for small amounts, and "add a second owner" is the next screen on the console and in the
app.

**What becomes public.** A deploy from the project Safe says "this Safe belongs to a PicoQuorum key".
A published statement says which one. Both are the owner's choice: they can deploy it from their own
wallet and keep the statement to themselves.

## Order of work

Each firmware change is a new release fingerprint: run `node tools/releases/badge.mjs` and rebuild
the console page ([AGENTS.md](../AGENTS.md)).

**1. On the emulator.** No chip is touched.
- [ ] `atecc.py`: GenKey's digest mode and internal Sign.
- [ ] The virtual chip (`emu/core/shims/atecc_sim.py`): TempKey's flags, GenKey's digest mode,
      internal Sign, and their refusals. Today it models external Sign only.
- [ ] `chipcfg.py`: `QUORUM_V2`, the brand stamp, the 608C in `REVISIONS`; `tools/check_config`.
- [ ] A statement checker in Python and in JavaScript, and `test-vectors/brandkey.json`.
- [ ] `provision.py`: B1–B10 beside C1–C10, and H1–H6. `main_dual.py` routes to them.
- [ ] `test-vectors/run-ceremony.mjs`: both ceremonies with a reboot after every step, and the
      refusals: slot 0 sealed on arrival, a used counter, an external Sign on slot 1, a brand key on
      no ring.
- [ ] `test-vectors/manifest.mjs`: statements only from the ceremony images.

*Gate: CI green.*

**2. One sacrificial key-c.**
- [ ] Bring-up: the 608C's revision and factory table into C1 and B1. C1 takes only the 608A and
      608B today.
- [ ] B1–B10, H1–H6 and every refusal, on silicon.
- [ ] The chip's own statements into `brandkey.json`. A model checked only against itself proves
      nothing.
- It settles:
  - whether internal Sign works before the data lock (if not, B5 moves after B8);
  - whether GenKey's digest mode takes a pass-through challenge (if not, a random nonce, and the
    checker gets the chip's random output too);
  - GenKey on slot 0, and slot locks, after the data lock.

*Gate: every step and refusal passes on the chip, and its statement passes the app's checker.*

**3. Recording keys.**
- [ ] The ring file, and a ring tool beside `tools/release`: the digest, the note, the check.
- [ ] `decode.py`: `PicoQuorumRing` and `PicoQuorumRevoke`, as strict as releases.
- [ ] The app's Keys page: rings, statements, the badge.
- [ ] A ring approved on a fork, then on Base Sepolia.

*Gate: the app shows a test key as branded, from an approval on Base Sepolia.*

**4. The first Safe.**
- [ ] `quorum_cfg.py`: Safe's singleton, proxy factory, fallback handler and proxy code, so the
      console works out the address. The two factories under `contracts`, so it decodes a deploy
      batch.
- [ ] The owner's steps show the first Safe at H6. The console lists it as not deployed until the
      service knows it, and proposes (from the onboarding branch).
- [ ] The statement as one QR code: the serial, the compressed key and the signature, 106 bytes as
      base45. That fits version 6, the largest `qrcode.py` draws.
- [ ] The app: a bind page from the QR code, the first Safe's state, growing to 2 of 3.
- [ ] `tools/quorum`: the deploy batch. `tools/fw attest` for an ATECC608, which it refuses today:
      the statement over USB.

*Gate: a test key goes from the bench to a 2-of-3 on Base Sepolia, its deploy paid by a test issuer.*

**5. The first ring.**
- [ ] A bench runbook: the image, each chip, the inventory (gitignored), the second machine's
      re-read, the cards.
- [ ] The project Safe approves the ring. Then we ship.
- [ ] Docs: quorum-v2 into PROVISIONING.md, a branded key's path into the owner's guide
      ([SETUP.md](guide/SETUP.md)), and the registry's README.

## Decisions for Jason

1. **Who pays for what.** Recommended: the deploy only. Gas for later transactions stays with the
   owner's wallet until a relayer or ERC-4337 is decided.
2. **How the deploy goes out.** Recommended: the project Safe in batches. Decide on a sponsor service
   before the first public ring.
3. **No owner record on the chip.** Recommended: drop slot 9.
4. **The first Safe's version.** Recommended: 1.4.1 L2. 1.4.1 is the project Safe's version, and the
   console already pins its MultiSend and SignMessageLib. The test Safes and the onboarding branch
   use 1.5.0 L2, so that branch would change.
5. **The first ring.** Genesis, #1–7, as in `docs/launch/`, or fewer to start.
6. **Later: owners without a laptop.** Whether the dual image can hand over to the console image by
   itself, and whether the owner's steps need `tools/fw allow on`.

## What was checked for this plan

- **This repo, 2026-10-07:** `chipcfg.py`, `provision.py`, `atecc.py`, `main_dual.py`,
  `atecc_sim.py`, `test-vectors/manifest.mjs`, `decode.py` (gas refunds), `qrcode.py` (versions 1 to
  6), and the branches `brand-key-docs` and `claude/passkey-onboarding`.
- **Microchip's cryptoauthlib, `main`, 2026-10-07:**
  - The two layouts above are `atcah_gen_key_msg` and `atcah_sign_internal_msg` in
    `lib/host/atca_host.c`.
  - Byte 52 is `00` when the slot of TempKey's key is locked.
  - GenKey's digest mode is `0x08`, and internal Sign with the serial is `0x40`
    (`lib/calib/calib_command.h`).
- **The QR code:** `qrcode.py`, run with CPython, encodes 106 random bytes as base45 (159
  characters) at version 6, level L, and still does with a 25-character link in front.
- **Not checked:** which TempKey sources the chip accepts for internal Sign, and whether it signs
  before the data lock. The datasheet's rules, then the sacrificial chip, settle both (step 2).
- Nothing was run on a chip or on the emulator.
