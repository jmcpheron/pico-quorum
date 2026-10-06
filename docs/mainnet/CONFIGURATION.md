# Recommended configuration: a Trust M signer in a 3-of-5 Safe on Ethereum

This is a recommendation for you to decide on. Nothing in it has been frozen on a chip.

**The short version:**
- The Safe's threshold is the security. The Pico is one owner of five.
- The chip locks one thing: the key. Which Safes it serves stays in the Pico's config and can
  change.
- Settle the spare-key-slot question before T9 runs on a chip.

## What protects what

| Layer | What it enforces | What it does not |
|---|---|---|
| **The Safe (3 of 5)** | No single owner, the Pico included, can move anything. Owners can be rotated out. | Three colluding or compromised owners. |
| **The console firmware** | It rehashes every transaction on the device, with the chain and Safe pinned, and shows every page. It refuses a hash mismatch, another Safe, and delegatecalls outside the pinned batchers. Red pages need a 3 s hold. | Anyone who holds the board with a USB cable. The REPL is open, so they can run their own code. |
| **The Trust M** | The key was made inside the chip and can never be exported, regenerated or replaced (T7). After T9, nothing else on the chip can be written or get a key. | **What it signs.** It signs any 32-byte digest it is handed. There is no PIN, no use limit and no record of each use. |

So whoever holds the board can make it sign anything, and **nothing on a Trust M records that
it happened.** (The ATECC's LimitedUse counter does.) That costs one signature toward three,
and the remedy is rotation (RUNBOOK.md, "Lost or compromised").

## Address lock-down: three options

Today the Safe address, the chain, the service and the batchers live in `secrets.py` and
`quorum_cfg.py` on the board's flash. Nothing checks those files at boot, and none of it is on
the chip.

**(a) Config only (reversible).**
- Pin the mainnet Safe in `QUORUM_SAFES` (`chainId: 1`) with `tools/quorum live pico`.
- Pin the chip with `tools/fw pin`.
- Check the board with `tools/fw verify`, which compares every file's hash with a checkout.
- Cost: none. The chip can move to another Safe later.
- Limit: anyone who can edit `secrets.py` can also flash firmware, so the pin protects against
  mistakes, not against the holder.

**(b) A signed config record, frozen on the chip.**
- One spare data object (F1D2) holds:
  - chain id 1
  - the Safe address
  - the passkey factory, singleton and verifiers
  - MultiSendCallOnly
- E0F0 signs it, the way it signed the key binding. Then T9 freezes it.
- The console refuses any other Safe or chain, and `tools/quorum verify` shows co-signers which
  Safe the chip was provisioned for.
- What it adds is **tamper evidence and a statement anyone can check**: "this chip was
  provisioned for this Safe". It is not a new barrier against the holder.
- Cost: **the chip is tied to that one Safe forever.** A Safe migration, a new Safe version, or
  moving the signer means a new chip. (There are 9 spares.)
- Not built yet. It needs firmware, a ceremony step and checks in `verify`.

**(c) (a) now; (b) only on a dedicated mainnet chip, if you still want it after (a) has run for a while.**

**Recommendation: (a), the Safe stays off the chip** (2026-10-01, after talking it through).
- The goal is a key that can never leave the chip and can serve any Safe. One sealed key gives
  one owner address, the same on every chain, so the same chip can be an owner of several Safes.
  The console watches up to 4, listed in its config.
- The Safe address and chain go into the hash the Pico computes, not into the chip. The chip
  signs 32 bytes and never sees either. So a signature for one Safe can't be replayed on another
  whatever the chip holds.
- An on-chip Safe record (b) would add only a frozen label, and the chip could never move to
  another Safe.

**Still open: the spare key slots.** T9 freezes E0F2 and E0F3 empty, so each chip holds exactly
one key and one owner address.
- Leaving them open (`--keep-open E0F2,E0F3`) would allow a second key per chip later. That key
  would be a second owner address, for a different Safe or role.
- The cost: firmware work (the console signs only with E0F1 today), and two more things for
  co-signers to check.
- **Decide before T9 runs on a chip.** A frozen empty slot can never get a key.

## The mainnet Safe

**Version.** Safe v1.4.1, the L1 singleton (`0x41675C099F32341bf84BFc5382aF534df5C7461a`, proxy
factory `0x4e1DCf7AD4e460CfD30791CCC4F9c8a4f820ec67`). Check both onchain (`cast code`) before you
deploy, and check the Safe's `VERSION()` and masterCopy after.

**Owners: 3 of 5, and no single kind of device can reach three.**
- One Trust M Pico, the subject of these docs.
- At most one more PicoQuorum signer (an ATECC Pico, say), so the firmware family holds at most
  2 of 5.
- At least three owners on hardware wallets from at least two vendors, held by at least two
  people, in at least two places.
- Without the Pico, the Safe must still reach 3. With 4 other owners it can.
- A cold "recovery" owner that signs only owner changes is a good fifth.

**Threshold changes and owner changes:**
- Agree on them offchain first, with a message to every owner.
- Never sign one under time pressure.
- The console shows them red and needs a 3 s hold. That is a prompt to stop, not a check.

**Delegatecall.** Keep the console's refusal. Only `multiSend` to the pinned MultiSendCallOnly
(1.4.1 or 1.3.0) is signable.

**Modules and guards.** None at the start.
- A module can move funds without the owners' signatures, so each one is a new owner in practice.
- If you want a delay on large transfers later, use an audited Delay module (Zodiac), installed
  as a red owner-change transaction.

**Execution.**
- Use `tools/quorum live exec --chain eth NONCE` from a separate hot wallet that holds only gas
  money. Executing doesn't need an owner.
- The Safe web app can't execute a transaction that carries a contract signature once the
  threshold is 2 or more (GS021), so co-signers should expect `live exec`.

**Tokens.** Mainnet USDC is already pinned in `quorum_cfg.py` with 6 decimals. Any other token
the Safe will hold should be added to `quorum_cfg.py`'s chain 1 list, after checking its
`symbol()` and `decimals()` onchain, so it shows by name and amount.

**The service.**
- `QUORUM_API_KEY`, a Safe developer key, is needed. Without one the quota is 5,000 requests a
  month.
- The console polls every 20 s, and every 600 s after 10 quiet minutes.

## The mainnet chip

**Use a fresh chip, not TM1.**
- TM1's key was made headless from the laptop on 2026-09-28, and it has a history of bench tests.
- A mainnet chip should have:
  - its own ceremony, run on the device
  - T9 run, with the spare key slots decided as above
  - a published `attest-<serial>.json`, checked by every co-signer before it is added

**The order:**
1. TM2 as the sacrificial chip: it confirms T9 and the refusals on silicon.
2. T9 on TM1.
3. The mainnet chip (TM3).

## Later, not in this round

- **RP2350 secure boot,** so only signed firmware runs.
- **A production image with the USB REPL closed.** The tooling would need another path.
- **A PIN on the key.** It needs a newer Trust M generation: TM1 looks like a first-generation
  part (CA 101, build 0809), which still has to be confirmed from Infineon's documents.
- **A use record on a Trust M,** such as a monotonic counter tied to the key, so that a hidden
  signature shows up the way it does on the ATECC.
