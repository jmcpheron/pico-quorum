# Key setup: a key-c's ATECC608C on the ESP32 bench

How the five key-c boards from the JLCPCB order (P2, ATECC608C) get their keys, one chip at a time,
on the ESP32-WROVER of [ESP32.md](../hardware/wiring/ESP32.md). The batch runbook that LAUNCH.md
section 6 asks for.

> **Status, 2026-10-16.** The firmware for all of this is built and walks on the emulator: the 608C,
> the brand bench with key 0000 by a swap, and the claim. None of it has run on a 608C yet. No chip
> from the order has been written or locked. Locks are permanent ([LOCKING.md](LOCKING.md)), so the
> spare goes first, and every permanent step waits for your yes at the time.

## Two paths, and your console makes the key on both

| | Branded | Unbranded |
|---|---|---|
| **The bench** | B1–B7 ([BRANDED-KEYS.md](BRANDED-KEYS.md)): quorum v2, a brand record signed by key 0000, both zone locks, no key | nothing: the chip stays as it came from the factory |
| **The user's console** | the claim, U1–U5: checks the brand, makes the key, seals it | the whole ceremony, C1–C10 ([PROVISIONING.md](PROVISIONING.md)) |
| **What the user trusts** | the brand says the bench locked the zones, and the console checks both locks itself | nothing: the console runs every permanent step |
| **Image on the console** | `dual`: it routes the chip to the claim | `dual`: it routes the chip to the ceremony |
| **The key** | made by the user's console, after the bench's data lock (GenKey only) | made by the user's console, in C4 |

Either way, nobody but the user's console chose the key. The brand is the option: it adds key
0000's signature and a label number, and it moves the risky locks onto the bench.

## The rig

- **The ESP32-WROVER** on the breadboard, with the 2.8″ screen and the EC11 knob, on USB at
  `/dev/cu.usbserial-310`. Set `PICO_PORT=/dev/cu.usbserial-310` for every `tools/fw` command, in
  case another board is plugged in.
- **One key-c on IO21 (SDA, its D+) and IO22 (SCL, its D−)**, with VBUS and GND to the 3.3 V rails.
  - 2026.10.11 turns on the ESP32's own pull-ups.
  - Also fit 4.7 kΩ from IO21 and from IO22 to 3V3, for margin.
- **One chip on the bus at a time.** Both a key-c and key 0000 answer at 0x60. At B5 the bench asks
  for the swap on its screen. On 2026-10-16 the ESP32 survived 11 plug-ins with the power on.
- **The knob only**: turn to choose, press to do it. On a permanent or GenKey step, hold 3 s to arm,
  let go, then hold 3 s again to do it.
- **The laptop**: `tools/fw`, with `backups/` and `chips/` kept local (both gitignored).
- **Pushes over the ESP32's serial bridge are slow:** a backup takes about 3.5 minutes and a push
  about 5. If a push stops part way, the board stays in maintenance, and a second push finishes it.

## Before any chip

1. The firmware with the 608C in it (2026.10.11 or later), committed. `tools/fw push` refuses
   uncommitted firmware.
2. The emulator walks, all passing:
   ```sh
   node test-vectors/run-ceremony.mjs && node test-vectors/run-brand.mjs
   ```
3. `tools/fw verify` matches the image on the board.

## Session 1: the spare, branded with the test key

Which chip: any one of the five. Write its serial in `chips/CHIPS.md` first. It stays a spare for
good: its brand is the test bench's (`T0001`), which no console takes as a brand.

1. `tools/fw push brand --yes` (with no brand key pinned, the brand image uses the test key).
2. `! tools/fw allow on`, then `tools/fw restart`. You run `allow on` yourself.
3. On the screen:

   | Step | What | Your yes |
   |---|---|---|
   | B1 | Pre-flight: the 608C (`00006005`), the factory table, saved as `snapshot-<serial>.bin` | |
   | B2 | Write quorum v2. Compare its CRC on the laptop: `tools/check_config --summary <snapshot> --v2` | |
   | B3 | Lock the config | **yes, after the CRCs match** |
   | B4 | The record into OTP, zeros into slots 1–15 | |
   | B5 | The test key signs; slot 8 | |
   | B6 | Lock the data zone | **yes** |
   | B7 | Read it all back | |
   | S1 | GenKey after the data lock | **yes** |
   | S2 | Two test signatures | |
   | S3 | Seal slot 0 | **yes** |

4. `tools/fw allow off`, then `tools/fw backup`. Copy `brand-log.txt` off the board.
5. Write it up in the build log. It settles these on a 608C:
   - GenKey after the data lock;
   - slot 8 readable in the clear, and inside the data CRC;
   - counter 0 at B7, which is 0 if KeyValid kept the bench's slot 0 read away;
   - how long U1's P-256 verify takes on the ESP32.

**Stop here for your review.** The other four chips stay as they came.

## Session 2: key 0000

Which chip: one of the four left. It becomes the brand key for good.

1. `tools/fw ceremony start` (the dual image), then `! tools/fw allow on`, then `tools/fw restart`.
2. C1–C10, quorum v1 ([PROVISIONING.md](PROVISIONING.md)), with your yes at C3, C6 and C9. It is
   **never enrolled as a Safe owner**.
3. `tools/fw allow off`. Record its serial, public key (qx, qy), counter and the ceremony's log.
   They are published, as BRANDED-KEYS.md point 3 says.
4. Pin it in `firmware/quorum_cfg.py`:
   ```
   "brandKeys": {"<SHA-256(qx || qy)[:16] hex>": {"qx": "<64 hex>", "qy": "<64 hex>", "serial": "<18 hex>"}}
   ```
   That is a firmware change, so it is a new release (2026.10.12): bump `firmware/manifest.json`,
   then `node tools/releases/badge.mjs`, `cd emu && node build.mjs` and `cd web && npm run build`.
   You make the tag with `tools/release`.

## Session 3, after you decide: branding with key 0000, then a claim

Not yet planned in detail. In short:

1. **On the bench:** `tools/fw push brand` with release B. B1–B7 as in session 1, but at B5:
   1. unplug the chip;
   2. plug in key 0000 and wait while it signs;
   3. plug the chip back in.
   - A real brand stops at B7, with no key.
   - Before each chip, set `BRAND_BATCH` and `BRAND_SEQ` in the board's `secrets.py`. They make the
     label number: bench 0 prints just the sequence, `0002`.
2. **On a console** (here the same ESP32): `tools/fw ceremony start`, `! tools/fw allow on`,
   `tools/fw restart`, plug the branded chip in.
   - The dual image routes it to the claim: U1 checks the brand, U2 makes the key, U3 tests it, U4
     seals it, and U5 shows the owner address.
   - Then `tools/fw ceremony finish` pins it and puts the console back.
3. **Optionally, one chip the unbranded way:** the dual image routes a factory chip to C1–C10 on the
   console.

The bench and the console are the same ESP32 in this round. That shows the flow, not yet the trust
split. For the split, the bench and the user's console are different boards.

## What is written down per chip

- `chips/CHIPS.md` (local): serial, which chip it is (spare, key 0000, a user's), its number, its
  locks and when, its owner address.
- `brand-log.txt` and `claim-log.txt` from the board, kept by every push. They are copied off after
  each session.
- `tools/fw backup` after each session, in `backups/` (local).
- The build log: what ran, what didn't, and anything the silicon did that the emulator didn't
  predict.

## Not covered yet

- PrivWrite refused after the data lock: it needs a driver command that doesn't exist.
- The registry and `tools/fw attest` for an ATECC608.
- The label printer, and the app's check page behind the label's QR code.
- Brand lines on the console's Chip page.
- The claim without `ALLOW_*` (BRANDED-KEYS.md point 9). That loosens a guard, so it is for review.
