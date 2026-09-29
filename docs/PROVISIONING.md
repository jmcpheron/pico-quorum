# Provisioning a fresh ATECC608: quorum v1

Chip #1 (`0123f3acfd2a826bee`) runs Microchip's test table (`test_ecc608_configdata`), inherited
through Austin's Pi code. It works, but it was never meant for a wallet:

- the CountMatch trap in slot 10
- a clear-writable IO-protection slot
- three signing slots
- an open data zone

Every chip from #2 on gets **quorum v1**, a table written for one job: a P-256 key that is one owner
of a Safe. The table lives in [`firmware/chipcfg.py`](../firmware/chipcfg.py). The ceremony that
writes and seals it lives in [`firmware/provision.py`](../firmware/provision.py) and runs from the
ceremony image.

## Decisions (2026-09-25)

- **No chip PIN.**
  - The Safe's threshold is the protection: a stolen Pico gives one signature of the two needed,
    and the other owners can rotate it out.
  - The ATECC608 has no lockout after failed attempts. At about 40 tries a second over I2C, a
    6-digit PIN falls in about 7 hours.
  - A PIN's rules can only be tested after the irreversible data lock.
  - See [the PIN variant](#the-pin-variant-costed-not-chosen) below. The Trust M has its own
    profile and ceremony now ([TRUSTM.md](TRUSTM.md)), also without a PIN. Revisit it with the Trust M,
    which does lock out.
- **A key-use counter.** LimitedUse on slot 0 ties every use of the key to counter 0, which the
  console shows. CountMatch is off, so the only cap is the counter's own maximum of 2,097,151.
  - On silicon (chip 2), once the data zone is locked, a public-key read (GenKey mode 0) counts as a
    use too; before the lock, and on chip 1, it did not.
  - The console accounts for its own reads: it takes the count before it reads the key, and before
    a signature it re-reads only the serial of a sealed slot. Only uses it didn't make are flagged.
- **One key, sealed.** Slots 1-15 are dead. There is no spare key: a second key in the same chip
  would fail with the first, and recovery is the Safe's other owners.

## The table

```
  0: 01 23 00 00 00 00 60 00 00 00 00 00 ee 00 00 00   the chip's own bytes (never written)
 16: c0 00 00 00 a1 2f 9f 8f 9f 8f 9f 8f 9f 8f 9f 8f
 32: 9f 8f 9f 8f 9f 8f 9f 8f 9f 8f 9f 8f 9f 8f 9f 8f
 48: 9f 8f 9f 8f ff ff ff ff 00 00 00 00 ff ff ff ff
 64: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
 80: 00 00 00 00 00 00 55 55 ff ff 00 00 00 00 00 00
 96: 33 00 1c 00 1c 00 1c 00 1c 00 1c 00 1c 00 1c 00
112: 1c 00 1c 00 1c 00 1c 00 1c 00 1c 00 1c 00 1c 00
sha256 aadcf1ea51b86a8f71c19823c5eea2adbd683221180496622db2c54b66e8abef
```

### Slot 0, the signing key: SlotConfig `0x2FA1`, KeyConfig `0x0033`

This is chip #1's proven slot 0 (`0x2FAF`/`0x0033`) with internal sign and ECDH taken away.

**SlotConfig:**

| Bits | Field | Value | Meaning |
|---|---|---|---|
| 0-3 | ReadKey | `0001` | External Sign only. No internal sign, no ECDH. |
| 5 | LimitedUse | 1 | Every signature raises counter 0 first. At the cap, Sign fails. |
| 7 | IsSecret | 1 | Required for Sign. |
| 12-15 | WriteConfig | `0010` | The Write command never. GenKey allowed. PrivWrite forbidden, so no key can be imported. |

**KeyConfig:**

- Private, PubInfo (the public key can be read), KeyType 4 (P-256), Lockable.
- No ReqRandom, ReqAuth or AuthKey.

The slot is sealed by the slot lock after GenKey (C6). Datasheet §2.4.3: after that, "modification
via PrivWrite, Write, GenKey, and/or DeriveKey is permanently prohibited".

### Slots 1-15, dead: SlotConfig `0x8F9F`, KeyConfig `0x001C`

This is chip #1's slot 6 row, which has run locked since 2026-09-17.

- Data type (KeyType 7): no Sign, GenKey or PrivWrite.
- IsSecret: never readable.
- WriteConfig `1000`: the Write command never, and not a DeriveKey target.
- ReadKey `F`, because 0 would make a slot a copy source for CheckMac.
- Not lockable.

The ceremony zeroes them before the data lock, and nothing can write them after it.

### The header

| Byte(s) | Field | Value | Why |
|---|---|---|---|
| 16 | I2C address | `C0` | 0x60, unchanged. |
| 18 | CountMatch | `00` | Off: no slot-10 trap. |
| 19 | ChipMode | `00` | 1.3 s watchdog, which the driver assumes. |
| 52-67 | Counters | 0 / 0 | Both start at zero. |
| 68-83 | UseLock, VolatileKeyPermission, SecureBoot, KdfIv | `00` | Off. |
| 88-89 | SlotLocked | `FF FF` | Required. A cleared bit for slot 0 at the config lock would lock the slot before it ever had a key. |
| 90-91 | ChipOptions | `00 00` | No IO protection and no KDF AES. IO protection only covers ECDH, KDF and Verify-MAC outputs, none of which this chip allows. |
| 92-95 | X509 | `00` | Unused. |

### Guards

- `chipcfg.py` asserts the table's fingerprint and shape at import.
- `python3 tools/check_config` decodes every slot again from the datasheet's bit tables,
  independently of `atecc.decode_slot`.
- The driver's WriteConfig decode was fixed for this: the old one was right only for code `0000`.

## Locks that the chip checks

A lock without a CRC is how a table bug bricked a chip on 2026-09-15. Both zone locks here carry a
summary CRC, and the chip refuses to lock unless what it holds matches the summary exactly.

- **Config lock (C3):** mode `0x00`, summary = CRC-16 of the 128 bytes the zone must hold.
  - That is the reviewed table, with the chip's own bytes 0-15 and 84-85 and the lock bytes still
    `55 55`.
  - It is built from the table, never from a readback.
- **Data lock (C9):** mode `0x01`, summary = CRC-16 of every slot that is not a private key (slots
  1-15, zeroed at C8), then the 64-byte OTP zone. Private keys are never in this CRC (datasheet,
  Lock).
- **Slot lock (C6):** mode `0x82`. It ignores the summary.

`python3 tools/check_config --summary <snapshot>` prints the config CRC for a chip, from the
factory dump that C1 saves. Compare it with what the device shows at C2.

## The OTP record

The OTP record is written at C8 and frozen by C9. It is 64 bytes, integers big-endian:

| Offset | Size | Content |
|---|---|---|
| 0 | 2 | `PQ` |
| 2 | 1 | Version 1 |
| 3 | 1 | Profile (1 = quorum v1) |
| 4 | 9 | Serial |
| 13 | 1 | Key slot |
| 14 | 2 | Flags |
| 16 | 16 | SHA-256(qx‖qy), first 16 bytes |
| 32 | 20 | Owner address |
| 52 | 4 | Date |
| 56 | 4 | Build |
| 60 | 4 | Counter 0 |

The record is advisory: the console always checks the live key.

## The ceremony

It runs on the ceremony image: `tools/fw push ceremony`.
- A refuses on a board whose `secrets.py` pins a chip (`QUORUM_EXPECT`), so take the pin out
  first.
- On the device, A on the banner opens PROVISION.
- The step comes from the chip's own state, so a reboot at any point resumes where the chip is.

**Getting the board ready:**
1. `tools/fw push dual`, with the `ALLOW_*` flags still False and the old chip still on. The dual
   image holds both the console and the ceremony. At every boot it reads the chip on the bus:
   - the pinned chip boots the console, under production rules
   - a fresh chip, or a quorum v1 chip whose data zone is still open, boots the ceremony
   - anything else boots the console, which shows Not pinned or No chip

   So you can swap chips back and forth during the provisioning. Once the new chip is sealed,
   enrolled and pinned, the board goes back to `tools/fw push console`.
   (`tools/fw push ceremony --pinned-chip-ok` is the ceremony alone.)
2. Unplug, swap the chip, plug in. The banner names the new chip ("CHIP 2 … FRESH"), in its light
   colours (`chips.json`).
3. Only then run `tools/fw allow on` and `tools/fw restart`. `allow on` refuses while the pinned
   chip is on the bus.
4. After C10, run `tools/fw allow off`.

Permanent steps also need the B+Y arm (held 3 s, lasts 60 s) and A held for 3 s.

| Step | What | Checks | Permanent? |
|---|---|---|---|
| C1 | Pre-flight | At 0x60, revision `6002`/`6003` matching bytes 4-7, zones `55 55`, SlotLocked `FF FF`, byte 16 `C0`, Random's unlocked pattern, self-test, the factory table. Saves `snapshot-<serial>.bin` | no |
| C2 | Write quorum v1 | Readback is quorum v1; shows the config CRC | no, rewritable |
| C3 | Config lock with CRC | Byte 87 = `00`, still quorum v1, Random live, slot 0 decodes right | **yes** |
| C4 | GenKey slot 0 | KeyValid, the public key reads back, GenKey on slot 1 refused | replaceable until C6 |
| C5 | Two test signatures, a plain digest and a WebAuthn assertion | Both verify on the Pico, counter +2, Sign on slot 1 refused | no |
| C6 | Slot-lock slot 0 | `FE FF`, the same public key, signs and verifies | **yes** |
| C7 | Owner address | Compare with `tools/fw verify --baseline` on the laptop, and with the factory's `getSigner` on Base | no |
| C8 | Zero-fill slots 1-15, record into OTP | The data CRC it will need | rewritable until C9 |
| C9 | Data lock with CRC | Byte 86 = `00`, OTP holds the record, slot 1 unreadable, OTP frozen, signs and verifies | **yes** |
| C10 | Summary | quorum v1 locked `00/00`, slot 0 sealed, the record matches the key; set `ALLOW_*` back to False | no |

The slot lock comes before the data lock on purpose. While the data zone is open, a plaintext
PrivWrite could put a known key into slot 0 (LOCKING.md).

**Then, each with its own explicit yes:**
1. `tools/quorum live enroll` deploys the signer proxy.
2. `swapOwner` on the Base Safe. It needs 2 of 3; chip #1 can co-sign its own replacement, and the
   console decodes the owner change in red.
3. `tools/fw push console`, then `tools/fw pin` with the new chip.

### Dry run and what is still uncertain

`node test-vectors/run-ceremony.mjs` runs all of C1-C10 on the emulator's virtual chip (608A and
608B), with a reboot after every step. It also runs the refusals:
- a table one bit off
- no arm
- no `ALLOW_LOCK`
- the data lock without the zero fill
- GenKey on the sealed slot
- the counter cap

Then it has the console sign with the sealed chip.

**What only silicon can settle:**
- **The summary's byte order in the Lock command** (assumed `crc[0] | crc[1] << 8`, as cryptoauthlib
  sends it). A wrong guess makes the chip refuse the lock, which locks nothing.
- **The exact data-CRC layout.** Same: a refusal is harmless.
- **Whether 4-byte writes into the secret slots' tails are accepted before the data lock.** If
  not, C8 reports it, and the fallback is the unchecked data lock (`0x81`), by explicit decision
  only.

**A spare breakout (about $6) run through C1-C9 first settles all three.** Without one, every
unknown is either harmless (a CRC lock that refuses locks nothing) or has a fallback before
anything irreversible.

## The PIN variant (costed, not chosen)

**Delta from quorum v1:**
- slot 0 KeyConfig `B3 09`: ReqAuth, with AuthKey slot 9
- slot 9 SlotConfig `BF 8F`: LimitedUse, so failed attempts count too
- slot 9 KeyConfig `5C 00`: ReqRandom

Before the data lock, slot 9 would get K = PBKDF2-HMAC-SHA256(PIN, "pico-quorum pin v1" ‖ serial).

**What it would need:**
- three new commands in the driver: Nonce in random mode, CheckMac, and a Sign in the same wake
- a CheckMac before every Sign and every public-key read

**Why not now:**
- There is no lockout after failed tries.
- A forgotten PIN makes the chip useless.
- It gives no protection against compromised firmware.
- The datasheet contradicts itself on which CheckMac mode grants authorization, and one reading
  would be a full bypass.
- All of it can only be tested after the irreversible data lock.

With a PIN, the WebAuthn UV flag (`webauthn.FLAGS`) would be enforced by the chip. Without it, UV is
the firmware's word that someone held A on the device that showed the transaction.
