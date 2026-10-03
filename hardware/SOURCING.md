# Sourcing and batches

*Started 2026-10-02. Nothing has been batch-ordered yet.*

A key is only as trustworthy as the chip inside it and the hands it passed through. This page covers
where parts come from, what each source can promise, and how a group batch order works. The
principle behind it is [Parts from people](../PRINCIPLES.md#8-parts-from-people).

## Sourcing tiers

Every tier is allowed. What matters is that each part's tier is written down, so the owners of a
Safe know what they're trusting.

| tier | who | how parts get here | what it can promise | what it can't |
|---|---|---|---|---|
| 1. Hobbyist | anyone, today's dev console | Amazon, Adafruit, a friend's parts drawer | the part works and passes the ceremony | where it's been, or that it's the part the label says |
| 2. Distributor | anyone with an account | Digi-Key, Mouser, LCSC | an authorised channel and a lot code you can trace back to the maker | what happened to it after it left the distributor |
| 3. Co-op batch | a group splitting one order | one distributor or fab order, opened on camera and split | tier 2, plus a public record: order, lot codes, unboxing, who got which part | that the person who opened it is honest, so more than one person watches |
| 4. Trusted line | a partner assembler | parts and boards that never leave their custody records | a chain of custody from the distributor to the finished key | anything they don't record, and they become someone you trust |
| 5. Independent testing | a third-party lab or co-op | samples pulled from a tier 3 or 4 batch | that the samples match the published design and the chip is genuine | anything about the parts that weren't sampled |

Tiers combine. A tier 3 batch with tier 5 sampling is a good target for the first real keys.

## What the chip proves on its own

Some chips carry a factory identity that no reseller can fake.

- **OPTIGA Trust M:** each chip has a factory certificate from Infineon's CA. The console checks it
  against the pinned CA key, and the factory key signs a statement binding the new signing key to
  that certificate. `TrustMAttest` can check the certificate on chain
  ([TRUSTM.md](../docs/TRUSTM.md)).
- **ATECC608C** (the rev A key): a serial number and Microchip's config table, with no factory
  certificate. Microchip's Trust&Go variant has one, but it ships configured and locked at the
  factory, so it can't take the quorum v1 config
  ([PROVISIONING.md](../docs/PROVISIONING.md)).

A factory certificate proves the chip is genuine. It doesn't prove who handled it, which is why the
tiers still matter.

**Later:** a certificate authority, a co-op or a test lab could sign each key's provisioning record
(serial, public key, owner address, batch, date). Then anyone could check that a key went through a
witnessed ceremony, not just that its chip is genuine. Nothing is built for this yet.

## The ceremony is the backstop

Whatever the tier, every key goes through the same steps before it's handed out
([PROVISIONING.md](../docs/PROVISIONING.md),
[ceremony outline](../docs/KICKOFF.md#provisioning-ceremony-outline)):

1. Verify the chip: its factory certificate where it has one, its revision and its factory config.
2. Write and lock the chip's config.
3. Generate the key inside the chip.
4. Test before sealing: test signatures must verify before the key's slot is locked.
5. Seal the key and lock the chip. This can't be undone.
6. Check the owner address on the laptop and on chain, record the serial, public key and owner
   address, and label the key with its fingerprint.

A chip that fails any step is discarded and logged, never fixed and reused.

## How a batch order works

1. **Announce it** in a GitHub issue: what's being made (for example key PCB rev A), the files at a
   tagged commit, the price per unit including shipping, the deadline, and who opens the box.
2. **Collect the count** in the issue. People say how many they want; nobody pays before the order
   total is known.
3. **Order** from the published files only: the gerbers, BOM and CPL from the tagged commit
   ([key-pcb/ORDERING.md](key-pcb/ORDERING.md)). Post the order confirmation and the distributor's
   lot codes, with prices and personal details removed.
4. **Open it on camera,** with a second person watching if possible. Write a dated
   [buildlog/](../buildlog/) entry with photos, the lot codes, and anything that went wrong.
5. **Split and ship.** Each package gets the lot record and its tier. If the keys were provisioned
   for the buyer, it also gets the provisioning record.
6. **Close the issue** with links to the buildlog entry and any test results.

The first candidate is key PCB rev A, with its parts in [bom/README.md](bom/README.md). Until the
ATECC608C SOIC is back in stock, the assembled UDFN board (key-b) is the likelier run.

## Making and selling them

The hardware in `hardware/` and `cad/key/` is [CERN-OHL-S-2.0](LICENSE). Anyone can make keys and
sell them. Anyone who ships a changed design has to publish the change under the same licence. We
ask makers to state their tier on what they sell.

**Not yet sellable: consoles in the current case.** The dev console's case in
[cad/console](../cad/console/README.md) is built from CC BY-NC parts, which forbid commercial use.
Before consoles can be batched for sale, they need an original case drawn from scratch.
