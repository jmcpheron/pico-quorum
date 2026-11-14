# Branded chips and sponsored gas: a plan (2026-11-09)

A plan for the next step after the console-rp's first signature. Every chip can be branded, by
choice: key 0000 signs it at the bench, and the customer's console checks it and makes the key. A
branded key that is registered gets its Safe transactions on Base paid for, out of a public
treasury. Like the console-rp plans, it's a plan to argue with, not a decision record. Decisions
are marked **Decide**.

It pulls together what is already written, and adds what the console-rp changes:
- [docs/BRANDED-KEYS.md](docs/BRANDED-KEYS.md): the bench brands the chip, the user makes the key.
- [docs/ATTESTED-KEYS.md](docs/ATTESTED-KEYS.md): the attestation key, the registry, the relay and
  the treasury.
- [docs/KEY-RUNBOOK.md](docs/KEY-RUNBOOK.md): the sessions on the five key-c 608Cs.
- [CONSOLE-RP-PLAN-2026-11-04.md](hardware/console-rp/PLAN-2026-11-04.md): the board with no radio, and the
  relay over its USB-C.
- [LAUNCH.md](LAUNCH.md) section 6: the brand, the membership list and its Merkle root.

## In one paragraph

A Picoquorum console is a second, independent view of a Safe transaction. It decodes the fields
itself, works out the Safe transaction hash itself, and signs only that hash, after every page is
seen and Sign is held. The short hash and its blockie are the check to compare with someone the
computer can't reach. This plan adds two things around that, and changes neither. First, an
optional brand: key 0000 signs each physical chip at the bench, so the customer can check where
their chip came from. Second, a relay on Base: it pays the gas for Safes that a registered branded
key owns, out of a treasury anyone can audit. The chip still signs only a Safe hash. The relay,
the treasury and the list all live on chain, under the project Safe.

## Where things stand

**Built, and walked on the emulator only** (KEY-RUNBOOK.md, 2026-10-18):
- the brand bench, B1–B7, with quorum v3 and an attestation key sealed in slot 1;
- the claim, U1–U5, in the dual image;
- the three-button key picker (`firmware/keypick_s.py`), for the claim and the unbranded
  ceremony.

**Not done:**
- No 608C from the order has been written or locked.
- Key 0000 doesn't exist.
- The claim's attestation step, U4a, isn't built, and the driver has neither GenKey's digest mode
  nor the internal Sign.
- The registry, the relay, the treasury and the Merkle root aren't built.
- On the console-rp:
  - there is no board profile;
  - the link isn't on UART1;
  - the USB relay isn't built.
- Secure boot and the SWD lock are off on every board.

## What the customer trusts, said plainly

Everything below rests on the console being honest. Today nothing proves that:
- **Secure boot is off, and J3 is open.** Anyone holding a console-rp with a debug probe can load
  firmware that signs anything. The USB-C can't do this, because it reaches only the CH343P. The
  board in someone's hands can.
- **The release fingerprint comes from the firmware itself.** `hello` over the link reports it, so a
  bad firmware can lie about it.
- **Names are hints.** Safe names, the address book and any name a computer loads are labels. Every
  screen that shows one also shows the full address. A label loaded over the cable needs the
  press and hold, but a person who doesn't read can still accept a bad one.

So the brand proves things about the chip, not the console. Board #2's secure boot and SWD lock
experiments ([the console-rp plan](hardware/console-rp/PLAN-2026-11-04.md)) come before any claim that a
shipped console is the one we built.

## Two keys: the customer chooses

Both are already designed (KEY-RUNBOOK.md, "Two paths"). On both, the customer's console makes the
key, and nobody else chooses it.

| | Vanilla | Branded |
|---|---|---|
| The chip arrives | as it left the factory | branded by key 0000, both zones locked, slot 0 empty |
| The customer's console runs | the whole ceremony, C1–C10, every lock included | the claim, U1–U5 (U4a too, if attested): check, make, seal |
| What the customer trusts | nothing but their console | that, and that the bench locked the config so only the chip's own GenKey fills slot 0. The console checks the locks itself |
| The risk | a slip with a permanent lock bricks the chip | the bench takes the risky steps, where they are practised |
| A number and a label | no | yes: 0042, its brand blockie, a QR code |
| In the list, and the badge | no | yes, once claimed |
| Sponsored gas | no | yes, once registered (below) |
| Privacy | no public link from chip to owner | registering links the serial to the owner address in public |

**The vanilla key stays a first-class choice.** It is for people who want to trust no one and will
take the risk. The product page says what each one costs and gives.

## Key 0000 signs every chip

The brand key is a Picoquorum key itself, number 0000 (BRANDED-KEYS.md point 3). This plan keeps
everything there and adds how it is handled.

**What it signs.** One brand digest per chip, at B5:
`SHA-256("PicoQuorum brand v2" ‖ OTP record ‖ slot 8 bytes 224–287)`. The digest covers the chip's:
- serial;
- revision;
- config checksum;
- batch and number;
- bench build;
- attestation key.

Key 0000 signs nothing else in the brand image, and it is never a Safe owner.

**Its counter is the public tally.** LimitedUse counts every use in counter 0, which only goes up.
- After each batch, the bench publishes the counter's value beside the batch file.
- The count must equal: chips branded, plus the uses the bench logged (its own checks, and the
  public-key reads after its data lock).
- A counter above that means key 0000 signed something it shouldn't have.

**How it is kept.**
- Unplugged, in a drawer, between batches.
- It is plugged in only for B5. Each plug-in is logged with the batch.
- The ceremony log and its public half are published. Its public half is pinned in
  `quorum_cfg.py` (`brandKeys`), and later named by `org.picoquorum.brand` under picoquorum.eth.

**On the console-rp, the chip is on the board.** The ATECC608C is soldered on I2C0. The key-c's
bench unplugs the chip and plugs in key 0000 for B5 (KEY-RUNBOOK.md session 3). A console-rp can't
do that.
- Rev B's key port, at the top of the board ([the rev B plan](hardware/console-rp/REV-B-PLAN-2026-11-05.md)),
  is the place for key 0000. The bench plugs it into the board being branded.
- The board's own chip and key 0000 both answer at 0x60. So the key port needs its own bus, or the
  bench must switch the board's chip off the bus while key 0000 signs.
- **Decide:** the key port's bus on rev B, before its routing is fixed.

**Rotating it.** The firmware lists brand keys by id. A retired key stays listed for the batches it
signed. A second bench gets its own key, certified by key 0000 (BRANDED-KEYS.md point 5).

## What the customer checks when it arrives

**On the console, with no network** (U1, as built):
1. Key 0000's signature over the chip's brand.
2. The record's serial, revision and config checksum match the chip in front of it.
3. Both zones read locked, and slot 0 is empty.
4. The use counter reads 0: "Never used: 0 signatures."
5. The number and the brand blockie on the screen match the bag's label.

**After the claim, in the browser** (U4a and the app):
6. The attestation: the chip's attestation key, named in its brand, signed a statement about the
   new key that only the chip can build. A copied brand on a fake chip can't produce it, because
   the attestation key can't be read out or made to sign a host's digest.
7. The app checks the bundle in the browser, as it checks Trust M bundles today
   (`tools/mock-tx-service/attest.mjs`). That check doesn't rest on the console's firmware.
8. The list: the serial is in a published batch, and nobody has claimed it before.

**Check 7 matters most on the console-rp.** There the project loaded both the chip's brand and the
console's firmware. So U1 on that board is the project checking its own work. The browser check,
from public bytes, is the independent one.

### The customer's mark: the claim's challenge

After the bench locks, the chip takes only two writes: making slot 0's key, and sealing it. So the
claim can't write anything else to the chip. What it can do is choose the challenge in U4a's Nonce:
- **A recent Base block hash.** It proves the key was made after that block.
- **A hash of something the customer chose.** For example, a phrase they keep. It ties the
  attestation to them without saying who they are.
- **Decide:** the block hash alone, or the block hash and the customer's value hashed together.

Picking the owner blockie stays as built: New makes another key, as often as the customer likes,
until Keep. Choosing among a few dozen by eye costs a few bits out of about 256. A blockie the
customer chose is one they will notice if it ever changes.

### Getting the bundle off a board with no radio

The bundle is public bytes, about 300 of them.
- **A QR code at U5.** `firmware/qrcode.py` already draws QR codes. It needs no new link request.
  It may need more than one code on a 240×135 screen.
- **A read on the USB link.** The link answers only from what the console already knows, so it
  would read the bundle U4a saved, not ask the chip. This adds a request to `docs/USB-LINK.md`,
  so ask first.
- **Proposed:** the QR first. Add the link read with the relay, once rule 1 is reworded.

## The list and its Merkle root

The batch files come first, in git: `docs/registry/brands/batch-<n>.json` (BRANDED-KEYS.md point
6). The root comes later, on chain.

**A leaf.** `SHA-256("Picoquorum leaf v1" ‖ serial ‖ OTP record ‖ slot 8 bytes 0–287)`. That is one
leaf per chip key 0000 signed, with no owner in it. Whoever holds a chip can work out its leaf.

**A root per batch.** The project Safe posts it, in one transaction, approved on consoles.
- What it adds over a file in git:
  - the project commits, at a known time, to exactly which chips it branded;
  - a chip added later needs another root, and the project Safe's quorum;
  - the leaf count can be checked against key 0000's counter.
- What it doesn't add: proof that the silicon is genuine. That is the attestation's job, and it
  rests on the bench.
- **Decide:** where it lives. Either a registry contract on Base, beside the relay, or a text record
  under picoquorum.eth on Ethereum. The relay reads it on Base, so the contract is the simpler
  choice.

**A claim** adds the owner address against the serial, once. A second claim on a serial is refused
and logged: it means a copied brand, or a bug.

## Sponsored gas on Base

ATTESTED-KEYS.md has the shape. This plan picks a first version and an order.

**What it pays for.** A Safe transaction on Base, when one of its confirmations is from a
registered owner. The relay checks every signature as the Safe will. Then it sends
`execTransaction` from its relayer key. On the console-rp, the whole path needs no wallet:
1. The app fetches the queue.
2. The console shows the transaction and signs over the USB-C.
3. The app hands the signature to Safe's service.
4. The relay sends the transaction once the threshold is met.

**Registering.** Registering is a Safe transaction, from a Safe the attested key owns, to the
registry contract. The contract checks the bundle and the Merkle proof, and that the sender is a
Safe with that owner.
- The chip still signs only a Safe hash. There is no "log in to the relay" message.
- Until the console has a decoder for the call, it shows it red and unread. "Register key 0042 for
  gas" is a firmware change and a new release.
- Registering is optional. A branded key that never registers works as an owner, and stays
  unlinked in public.

**The first version: a plain relayer, not ERC-4337.**
- Its rules aren't enforced on chain, but every top-up and every relayed transaction is public. So
  anyone can add up what it spent, and on whose behalf.
- ERC-4337 (Safe4337Module, a bundler, a paymaster that reads the registry) enforces the rules on
  chain. But it is a new dependency and a new module on every Safe. Leave it for later, as LAUNCH.md
  section 4 and HEGOTA-WATCH.md do.

**Limits.**
- They apply per serial, not per Safe: one key can own many Safes.
- A cap per serial per day, and a cap on gas per transaction.
- The project Safe sets the limits, and can revoke a bench key or a brand key. It can't register
  or unregister a key for anyone.

**The treasury.** A Safe on Base, owned by the project Safe. It is separate from the project Safe,
so the relay's money is ring-fenced, and its balance is the relay's budget.
- It tops up the relayer key in small amounts. Each top-up is a Safe transaction approved on
  consoles.
- What funds it: a share of each batch's sales, sent in one transaction per batch, with a note
  naming the batch. Anyone can compare that with the batch file and the price.
- Don't tie a buyer's paying wallet to a serial in public. After the claim, that would show who
  owns which Safe (ATTESTED-KEYS.md).
- Get legal advice before a product page promises buyers a share of money, or a say in spending it.

**Base Sepolia first.** The same relay, registry and treasury run on Base Sepolia, with the
test-ETH faucet BRANDED-KEYS.md describes, once per claimed serial. Measure the gas a relayed
transaction and a registration really cost there. Set mainnet's caps from those numbers, not from
guesses.

## What changes in the rules

None of this is changed by this pull request. Each one is asked for, and decided, first.
- **AGENTS.md rule 1.** The relay over the USB-C needs the wording the console-rp plan proposes: the
  link may carry a transaction in and a signature out. The console still signs only the hash it
  worked out. This is a decision the plan already marks.
- **Rule 2: the image on a shipped console-rp.**
  - The console image has no GenKey and no lock, and must stay that way. A customer's console-rp
    can't be reflashed over its USB-C, so the claim must ship on the board.
  - Proposed: ship the dual image. At every boot it sends an unsealed branded chip to the claim, a
    fresh chip to the ceremony, and the pinned chip to the console (`firmware/main_dual.py`).
  - On the bench, a board goes back to the console image once its chip is pinned. A customer's
    console-rp can't, so the ceremony and the claim would stay on it for good.
  - **Decide:** whether that's acceptable for customer boards, or whether a claim-only image should
    route to the console for good once slot 0 is sealed.
- **Gates.** BRANDED-KEYS.md point 9 proposes dropping `ALLOW_*` for the claim, keeping the hold.
  A customer has no laptop to edit `secrets.py` with. It loosens a guard, so it is for review.
- **New network calls and services:**
  - the relay;
  - the faucet;
  - the app reading the registry or the root;
  - posting a bundle.

  AGENTS.md says ask before each.
- **A first contract.** The registry is Picoquorum's first. It needs review before anything is
  deployed, on Base Sepolia included.

## Decide

**Before the first real branded chip.** These freeze at B3 or B6:
- [ ] The attestation key in slot 1, or no attestation. Without it, the relay can only trust
      "first claim per serial", and a copied brand could take the gas.
- [ ] The quorum v3 rows, decoded independently by `tools/check_config`.
- [ ] The v3 record and slot 8's layout, and the `"PicoQuorum brand v2"` prefix.
- [ ] The spare bytes stay zeros: slot 8's 288–415 and OTP's 49–63.

**Before rev B's routing is fixed:**
- [ ] Key 0000 on the key port: its own bus, or a way to take the board's chip off I2C0 at B5.

**Before the claim ships on a console-rp:**
- [ ] The image a customer's console-rp ships with (above).
- [ ] The claim's gates.
- [ ] The challenge: a block hash, the customer's value, or both.
- [ ] The QR, the link read, or both.
- [ ] Secure boot and the SWD lock, from board #2.

**Before the relay:**
- [ ] AGENTS.md rule 1, reworded for the USB relay.
- [ ] Where the Merkle root lives.
- [ ] The relay's limits, and the treasury's share of sales.
- [ ] A review of the registry contract.

## The order of work

Each item that changes firmware is a new release fingerprint. Each permanent step waits for a yes
at the time, on a spare first (LOCKING.md).

1. **Silicon first.** KEY-RUNBOOK.md session 1 on a spare 608C:
   - the driver's GenKey digest mode and internal Sign;
   - the internal-sign message, byte for byte;
   - an internal Sign over a host's TempKey, refused;
   - PrivWrite on slot 0 after the data lock, refused.
2. **Key 0000.** KEY-RUNBOOK.md session 2: its ceremony, its record published, and its public
   half pinned in a release.
3. **The console-rp profile and the link on UART1** (the console-rp plan, items 1 and 2).
4. **U4a and the QR**, on the virtual chip, with a reboot after every step and the refusals.
5. **One branded key-c**, claimed on a console, end to end. Then one branded console-rp, with key
   0000 on its key port.
6. **The bundle check** in the app, shared with `tools/quorum verify`.
7. **Batch files** in `docs/registry/brands/`, with key 0000's counter after each batch.
8. **On Base Sepolia, each asked for first:**
   - the registry contract and its review;
   - the treasury Safe;
   - the plain relayer;
   - the faucet.
9. **The first relayed transaction:** a Base Sepolia Safe, owned by a registered console-rp, its
   gas paid by the treasury.
10. **Mainnet**, with caps from step 9's numbers, and the Merkle root of the first real batch.

## What this plan doesn't do

- It changes no code, no firmware and no chip.
- It doesn't make the console's firmware provable. Secure boot does that, and it isn't on yet.
- It doesn't prove the chip is genuine silicon. An ATECC608 has no factory certificate. The
  attestation key proves the key lives in a chip the bench branded, and so rests on the bench.
- It doesn't put money, access or tiers on the chip. The chip carries identity only. Everything
  that changes over time lives on chain, under the project Safe.
