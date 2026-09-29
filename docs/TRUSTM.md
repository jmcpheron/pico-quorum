# The OPTIGA Trust M beside the ATECC608

The board signs with either secure element. It finds out which one is on I2C0 at every boot and
uses the same console, the same pin (`QUORUM_EXPECT`) and the same Safe owner scheme (a P-256
passkey signer). The Trust M gets its own profile, **quorum-tm1**, and its own ceremony. Both
were built and tested in the emulator first. On a real chip, the steps up to the seal have been
run. The seal itself has not.

Decisions (2026-09-28):
- **The key:** a new P-256 key, made on the chip in **E0F1**.
- **The binding:** the factory key **E0F0** signs a statement binding the new key to the chip's Infineon certificate.
- **No use limit and no PIN** in the first profile, as on quorum v1.
- **Irreversible steps** each wait for an explicit yes, and go on a sacrificial chip first.

## Which chip is in

`signer.detect()`:
1. One wake token for a sleeping ATECC, then `i2c.scan()`.
2. A short poll of the Trust M's state register at 0x30. **A sleeping Trust M NACKs its address, so `scan()` alone misses it**: on the real board `scan()` returned `[]` with a Trust M on the bus.

`signer.load(soft, pins)` then picks one:

| On the bus | Signer |
|---|---|
| ATECC608 (0x60, 0x35, 0x6A) | `ChipSigner`, as before |
| Trust M (0x30) | `TrustMSigner` |
| both | the pinned one (`QUORUM_EXPECT`); none pinned: the ATECC, and it logs that |
| neither | `NoSigner` (production), or the software key (development) |

The console never names a chip type. It goes through `serial(fresh)`, `pubkey()`, `sign()`,
`key_row()`, `profile()`, `use_counter()`, `needs_ceremony()` and `info()`. `main_dual.which()`
routes a fresh or half-done Trust M to the ceremony, the same as an ATECC.

A Trust M pin names the object instead of a slot number:
```python
{"serial": "0a091b5c000b0062006c", "slot": 0xE0F1, "owner": "0x…", "locked": True, "chip": "trustm"}
```
- **The serial** is UID bytes 11–20: batch number and wafer X/Y. The UID's tail is the firmware id and build, which is the same across a batch, so screens that show `serial[-8:]` show the wafer position.

## quorum-tm1

| Object | What it holds | Factory state (read off the real chip) | After the seal |
|---|---|---|---|
| E0F1 | the Safe key, P-256, key usage Sign, Execute ALW | empty, LcsO creation, Change `LcsO<op` | LcsO operational: GenKeyPair can never run on it again |
| F1D0 | the record, 110 bytes: `PQ`, v2, profile, serial, key OID, **qx, qy**, owner, date, build | 140 bytes, zeros, Change `LcsO<op`, Read ALW | frozen |
| F1D1 | the binding, 83 bytes: `PB`, v1, E0F0's (r, s) over `binding_digest`, SHA-256(cert)[:16] | as F1D0 | frozen |
| E0F0 | Infineon's factory key, certified in E0E0 | Change NEV, Execute ALW, P-256, usage Auth | untouched |

- **Why the public key is in F1D0:** a Trust M never returns the public half of a private-key object. GenKeyPair gives it once, and the record keeps it.
  - The console computes the owner from the record and checks it against the pin.
  - A record that lied would fail the pin. Signatures from a different key would fail on chain.
- **The binding:** `binding_digest = SHA-256("PicoQuorum Trust M key binding v1" ‖ UID ‖ E0F1 ‖ qx ‖ qy)`, signed by E0F0.
  - With E0E0's certificate, anyone can check that a genuine Trust M holds the key.
  - `TrustMAttest.sol` can check E0F0's certificate on chain today; checking the binding on chain is a later step.
- **The seal:** raise LcsO to operational on F1D1, F1D0, then E0F1. It changes nothing else.
  - The factory Change condition on all three is already `LcsO < operational`, so the seal freezes them.
  - A lifecycle state never goes down.

## The ceremony (`firmware/provision_tm.py`)

| Step | What | Reversible? |
|---|---|---|
| T1 Pre-flight | UID, LcsA, security events. The certificate is verified against Infineon's CA key on the Pico, and E0F0 signs a probe that verifies under the certificate's key. Checks E0F1, F1D0 and F1D1 are factory. Saves every object's metadata to `snapshot-tm-<serial>.json` | read-only |
| T2 Make the key | GenKeyPair in E0F1 (ALLOW_GENKEY, the arm, a 3 s hold) | yes, it can be made again until T7 |
| T3 Test | Two signatures (a plain digest and a WebAuthn assertion), verified on the Pico, low s | read-only |
| T4 Bind | E0F0 signs the binding, verified under the certificate | read-only |
| T5 Owner | The owner address, to compare on the laptop | read-only |
| T6 Record | F1D0 and F1D1 written and read back | yes, until T7 |
| T7 **Seal** | LcsO operational on F1D1, F1D0, E0F1 (ALLOW_LOCK, the arm, a 3 s hold) | **no** |
| T8 Done | Checks everything is sealed, the record matches, the binding verifies and the key still signs. Registers the chip in `chips.json` | read-only |

- **Resuming:** the step is worked out from the chip every time.
  - Before T6, a reboot means T2 again, because the key's public half exists only in that session.
  - After T6, a reboot resumes at T3 with the key from the record, and T3 proves the record matches the key.
- **What the ceremony never writes:** E0F0, E0E0, or anything outside E0F1, F1D0 and F1D1.
- **No destructive refusal tests:** nothing tries a write that a sealed or factory object ought to refuse. If such a test failed, it would destroy what it was testing.

On the board, the flow matches the ATECC's (`docs/PROVISIONING.md`):
1. `tools/fw push dual`.
2. `tools/fw allow on`.
3. `tools/fw restart`.
4. A on the ceremony banner, then T1–T8.
5. `tools/fw allow off`.
6. `tools/fw pin`.

X on the banner shows each object's lifecycle and access conditions, read-only.

## What the real chip showed (2026-09-28)

The chip: Adafruit 4351, UID `cd16338401001c000100000a091b5c000b0062006c801010710809`, serial `0a091b5c000b0062006c`.

**What it is:**
- Firmware 80101071, build 0809. The certificate comes from **"Infineon OPTIGA(TM) Trust M CA 101"**, serial `1d560a9b`, subject "Infineon IoT Node".
- CA 101 and build 0809 look like the first-generation Trust M (V1). **Confirm this with Infineon's documents before relying on it.**
- It matters for a PIN: the later generation's authorization references (the "Auto" access condition) are what a PIN would need.
- LcsA is operational.

**Certificate and signing:**
- **The certificate verifies against the pinned CA 101 key on the Pico**, in 1.4 s (`p256.verify` in MicroPython).
- E0F0 signs, and its signature verifies under the certificate's key. CalcSign takes about 150 ms, including opening a session.

**The security event counter (E0C5):**
- **A private-key use is paid from an idle credit first.** The chip builds the credit while it
  sits idle. Only once the credit is spent does a CalcSign raise the counter, by 1, with E0F0 and
  E0F1 alike.
  - On the console after about 10 minutes idle, 8 signatures in a row left the counter at 0.
    From then on it rose by 1 per signature, reaching 7 after 12.
  - Right after a busy spell (the first bench runs), every signature counted at once.
- Refused commands do not raise it (tried: a bad OID, CalcSign on an empty key, reading a key object).
- It falls back by 1 about every 5 s. This is the Trust M's brake on bursts: past a threshold the chip slows down.
- So a normal approval reads "0 → 0", and a signature adds at most 1. The console flags only a rise larger than 1.

**Error codes (F1C2):** 0x01 unknown OID, 0x07 reading a key object's data, 0x0B CalcSign with an empty key.

**T1–T6 passed on this chip**, driven headlessly from the laptop (firmware mounted over USB, flags injected in RAM, nothing written to the board's flash):
- Key `ef677807…`, qx `0xef6778077c0bf33ca82391a38d941cf33515da7900f02931e7c83399ee681719`
- Owner `0x47c0998C6a7A1955794071b9f4058e7814178f35`, the same on the Pico and on the laptop (viem)
- E0F1, F1D0 and F1D1 are still at LcsO creation: **not sealed**

**Not yet seen on silicon**, to try on a sacrificial chip:
- T7 itself.
- That GenKeyPair on a sealed E0F1 and SetDataObject on a sealed F1D0 are refused.
- Whether GenKeyPair raises the security event counter.
- The rules for writing metadata.

The emulator models these the way the manual describes them (`emu/core/shims/trustm_sim.py`).

**The console on the real chip (2026-09-28).** The dual image ran with TM1 pinned as `locked: False`, against the laptop's mock Safe (`tools/quorum serve`), with nothing on chain.
- **Boot:** the pin passed, the factory binding verified in 2.6 s, and 147 KB of heap was free.
- **Signing:** the console joined the Family Safe as owner `0x47c0…8f35`, and you approved #0.
- **The mock:** it verified the WebAuthn P-256 signature (low s), and #0 executed.
- **The board's log:** "signed #0 … sec 0->0". That reading is what uncovered the idle credit.

## On the screens

While it signs, the console shows short facts read from the chip itself (`tmcfg.info_lines`, `quorum.chip_info`):
- **Signing:**
  - "Infineon OPTIGA Trust M, CC EAL6+"
  - "Key E0F1 made on-chip, sealed (LcsO op)"
  - "Bound to Infineon cert, CA 101" (checked once at boot)
  - "Security event counter: n"
- **Sending:** the signing time and the counter after the signature ("unchanged" after idle, "+1" in a burst).
- **Result:** if the counter rose by more than the signature, the result screen says so and `log.txt` records it.
- **Device screen:** the Trust M shows `E0F1 locked · Trust M`, and a Security row where the ATECC has Key uses.
- **Chip pages** (Device → Chip: A, or the knob), for reading at leisure what the Signing screen flashes:
  - **the chip:** part, CC EAL6+, firmware, serial, wafer, lifecycle, the security counter
  - **the factory certificate:** issuer, subject, serial, validity, the CA check, the factory key E0F0
  - **the signing key:** E0F1, sealed or not, its access rules, public key, owner, the binding, when the record was written
  - All of it is read off the chip when the pages open; long rows continue on the next page. An ATECC gets a page of its own (part, config, slot 0).
- **Boot checks both links of the chain:** the certificate against the pinned Infineon CA key, and the binding under the certificate (about 4 s in all on the Pico). "Bound to Infineon cert" is shown only when both pass.
- **ATECC:** its own lines (part, sealed slot, key uses).

Walkthrough: `docs/quorum-ui/README.md`, iteration 5.

## The emulator

- **`trustm_sim.py`:** a virtual Trust M at 0x30. It speaks the registers, the IFX frames and the APDUs above. Its factory state is the real chip's, and its certificate comes from a test CA that `tmcfg` accepts only off the Pico.
- **`tools/emu chip`** takes `trustm-fresh`, `trustm-sealed`, `both`, or `atecc`.
- **`node test-vectors/run-trustm.mjs`** runs 70 checks:
  - the real chip's bytes
  - detection
  - the whole ceremony and resuming after reboots
  - the gates
  - the console signing and what it shows
  - the dual image
- **`tools/quorum shots trustm`** redraws the walkthrough's Trust M screens.
