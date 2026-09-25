# Locking the chip: what each lock does to the multisig

> **Living decision doc (started 2026-09-25).** Locks on the ATECC608 are permanent, so each one
> gets decided here first, with evidence, before anyone holds A on a red screen. Record what was
> done, and when, in the [buildlog](../buildlog/BUILDLOG.md).

## Chip #1: `0123f3acfd2a826bee`, the dev console's only chip

### Readout (2026-09-25, read only)

| | |
|---|---|
| Part | ATECC608A, revision `00006002` |
| Config zone | **locked** (2026-09-17) |
| Data zone | open |
| Slot locks | none (bytes 88–89 = `ff ff`) |
| Config | Byte for byte, the wallet table in `firmware/atecc.py`, which is cryptoauthlib's `test_ecc608_configdata`, Microchip's test config. The only byte that differs is 52, where the chip keeps counter 0. |
| Counter 0 | 7 |

| Slot | Kind | Key | Lockable | Notes |
|---|---|---|---|---|
| 0 | P-256 private | `9fad2e82…` | **yes** | GenKey allowed. **LimitedUse**: every signature counts against counter 0. The console's key. |
| 2 | P-256 private | `82004df5…` | **no** | GenKey allowed. Can never be sealed: a scratch key. |
| 7 | P-256 private | empty | yes | GenKey, and PrivWrite (an encrypted import) |
| 10 | "AES", clear writes always, not secret | never written | yes | **CountMatch** limit slot (config byte 18 = `0xA1`) |

### The multisig already works with this chip, with nothing locked

These checks are free, read only, and move no funds.

- **Owner addresses:**
  - slot 0 is `0x2843705391b7E2cf06b0b964b532Ad9891535E53`
  - slot 2 is `0x3ca6AE8f102083B8290Adc96A653C6580C19594F`

  These come from `firmware/webauthn.py`, and the deployed passkey factory's `getSigner` agrees on
  Base Sepolia, Base and Ethereum. Neither proxy is deployed yet.
- **A real chip signature, verified onchain.**
  - Slot 2 signed the WebAuthn digest of a test safeTxHash.
  - `isValidSignatureForSigner` returned `0x1626ba7e` on all three chains, for the signature as
    signed (high s) and normalized to low s.
  - A wrong-hash control returned `0x00000000`.
  - Counter 0 stayed at 7.

### What the locks do

The sources are the ATECC608A full datasheet (a preliminary copy, the only one public), the
ATECC508A complete datasheet (DS20005927A), and cryptoauthlib. Confidence is high unless marked.

- **Slot lock (slot 0).**
  - It is the only thing that makes slot 0's key permanent. It blocks GenKey (a new key), PrivWrite,
    Write and DeriveKey on that slot.
  - Sign and the public-key read keep working.
  - It does not need the data zone locked first: "either before or after the Data zone is locked".
  - For the multisig the owner address is a function of the key, so this is what makes the owner
    address permanent.
- **Data zone lock.**
  - It changes nothing about external signing.
  - It does not protect slot 0: GenKey can still replace the key unless the slot is locked.
  - It makes the clear slots readable (the note in 12, the snake table in 13) and enables internal
    signing, which we don't use.
  - It freezes the OTP zone as it is (all `ff`, never written) and freezes the "never write" slots
    with whatever the factory left in them. It gives up slot 7's encrypted import unless slot 4's
    secret is set first.
- **While the data zone is open,** a plaintext **PrivWrite can put a known key into any private
  slot**, whatever its rules say. That includes slot 0 unless it is slot-locked.
  - On a dev chip that only means an attacker with bus access could destroy an owner.
  - On a real key it matters before enrollment: an owner whose key someone else chose is not an
    owner you control. Real keys get locked right after GenKey, before they are enrolled.
- **CountMatch is a trap for the data-zone lock.**
  - After that lock, slot 10's first 8 bytes are the cap on counter 0 (a little-endian uint32, a
    multiple of 32, written twice). At the cap, Sign on slot 0 fails with `0x0F` from then on.
  - Slot 10 holds unknown factory bytes. Whether the cap is enforced before the data lock isn't
    documented (7 signatures worked).
  - Fix, before any data lock: write slot 10 block 0 as `E0 FF 1F 00 E0 FF 1F 00` followed by 24
    zeros (cap 2,097,120, the value Microchip's own test restores). Read it back after the lock,
    then lock slot 10 so nobody can lower it.
- **LimitedUse isn't a security boundary.** Anyone on the bus can raise counter 0. The maximum is
  2,097,151, so 7 used leaves about 2.1 million. It can't be changed now that the config is locked.

Not verified on silicon: the Lock error code for a refused lock, CountMatch before the data lock,
and the factory contents of the data slots.

### Recommendation

- **Lock slot 0 only, and only after the ladder has proven it.**
  - Leave the data zone open on this chip. Its lock buys nothing for the multisig, and it springs
    the CountMatch trap unless slot 10 is written first.
  - Keep slot 2 as the scratch key.
  - Keep slot 7 free for a future key.
- **Real keys (the chips on order) get their own config.** It is written for this job, not
  Microchip's test table:
  - a signing slot with no LimitedUse or CountMatch, GenKey only, and no PrivWrite
  - then a full provisioning ceremony: config lock, GenKey, verify, slot lock, data lock, and only
    then enrollment

### Checklist before locking slot 0

- [x] Owner address for slot 0's key = the factory's `getSigner` on Base Sepolia, Base, Ethereum
- [x] A real chip signature (slot 2) passes Safe's passkey signer onchain on all three
- [x] A slot 0 signature passes onchain too: the Pico's rung 1 approval (safeTxHash `0xdb29…0788`),
      `isValidSignatureForSigner` = `0x1626ba7e` on Base Sepolia, Base and Ethereum. Counter 0 went
      7 → 8 (2026-09-25).
- [x] The new console firmware on the board computes `0x2843…5e53` for "This key" itself
- [x] Rung 1 with the real Pico: approved on the fork, and it executed in 109,488 gas ([LADDER.md](LADDER.md))
- [x] Rung 2: api.safe.global accepted slot 0's confirmation on Base Sepolia (201), and `live exec`
      executed it: Safe `0xEDED…0a43` #1, [tx](https://sepolia.basescan.org/tx/0xe719116d86a019098679ba9b7d5e5263fed8c6fc4cd7181f573b4b3fa3860fde)
      (2026-09-25). The Pico signed, but its own POST failed on memory (OSError 12), so its held
      signature was posted from the laptop unchanged. The firmware fix is in `txservice.py`.
- [ ] Then LOCK SLOT 0 from the chip map (`ALLOW_LOCK = True`, armed, hold A), and afterwards:
  - [ ] SlotLocked bit 0 is clear (bytes 88–89 = `fe ff`)
  - [ ] the public key is unchanged: `9fad2e82…`
  - [ ] NEW KEY on slot 0 is refused
  - [ ] a signature still verifies onchain (counter + 1)
  - [ ] `ALLOW_LOCK` back to False
