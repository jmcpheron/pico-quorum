# TROPIC01: notes on a third secure element

> **Notes (2026-10-19). Nothing here is built, ordered or tested.** Tropic Square's TROPIC01 is an
> open-design secure element from Prague, in volume production. These notes say what it could give
> PicoQuorum, what it would cost us, and how to start with a devboard. Every fact about the chip
> comes from Tropic Square's own documents (listed at the end). None of it has been checked on
> silicon here.

## In one paragraph

TROPIC01 signs P-256 ECDSA, so it fits the console's passkey owner scheme as it is: the same
`webauthn.py` digest, the same Safe passkey signer, the same owner address on every chain. What it
adds is a design we can read: the RTL, the RISC-V firmware and the crypto coprocessor's firmware are
public, and so are the test reports and a security advisory. What it changes is the bus and the
trust model. It talks SPI, not I2C, and every command runs inside an encrypted session that needs a
**pairing key**, an X25519 private key the console has to hold. That is a secret on the Pico, and
the console has none today.

## How it compares

| | ATECC608 | OPTIGA Trust M | TROPIC01 |
|---|---|---|---|
| Curves that sign | P-256 | P-256, P-384, P-521, others | **P-256** (ECDSA), Ed25519 (EdDSA) |
| secp256k1 | no | no | no |
| What the sign command takes | a 32-byte digest | a digest | a 32-byte hash (`ECDSA_Sign`, `MSG_HASH`) |
| Bus | I2C | I2C | **4-wire SPI**, 3.0–3.6 V |
| Session | plaintext (an optional IO key) | plaintext or shielded | **always encrypted**: `Noise_KK1_25519_AESGCM_SHA256` |
| Key slots | 16 slots, mixed use | a few key objects | 32 ECC slots, 512 data slots of up to 475 bytes |
| Factory identity | none | a certificate for factory key E0F0, which can sign | a certificate for the chip's **X25519 session key**, chained to Tropic Square's root |
| Can the factory identity sign a statement about a new key? | no | yes (TRUSTM.md's binding) | **no**: it only authenticates the session |
| Locks | config, data and slot locks, permanent | lifecycle states, only go up | per-command, per-pairing-key access bits. R-Config bits can be set back; **I-Config bits only go 1 → 0** |
| PIN support | none we use | none we use | MAC-and-Destroy: 128 slots, a hardware-limited PIN check |
| Counters | 2 | several | 16 × 32-bit monotonic counters |
| Package | SOIC-8, UDFN | USON-10 | **QFN32, 4 × 4 mm, 0.4 mm pitch** |
| Sign time (datasheet) | not compared here | not compared here | **199 ms**, plus 163 ms for each session handshake |
| Design open? | no | no (NDA-free docs) | RTL, app firmware, SPECT firmware open; bootloader, analog blocks and layout closed |

## Pros

1. **We can read the chip.** "The console image is exactly what it imports" is the console's rule.
   We know of no other secure element that publishes this much of itself. Its RTL is in
   `tropicsquare/tropic01-rtl`, and the firmware in `ts-tr01-app` and `ts-spect-fw`. The bootloader is not open (Tropic Square cites its silicon IP providers), and
   neither are the analog parts or the layout.
2. **They publish what goes wrong.** The tropic01 repository holds seven security reports
   (PUF, AES-GCM, ISAP, TRNG, decapsulation, fault injection) and one public advisory
   (below). That matches how this project writes its own docs: what was checked, and how.
3. **P-256 fits as is.** `ECDSA_Sign` takes a 32-byte hash, so `quorum.sign_it` hands it the same
   WebAuthn digest it hands the ATECC and the Trust M. The Safe side doesn't change. `ECC_Key_Read`
   returns the public key, so no record has to hold it (unlike the Trust M, TRUSTM.md).
4. **The chip says where a key came from.** `ECC_Key_Read` returns `ORIGIN`: made on the chip
   (`ECC_Key_Generate`) or written into it (`ECC_Key_Store`). Read over an authenticated session, that
   is a check the console can make at every boot.
5. **A key on its own is useless.** No command runs without a session, and no session opens without
   a pairing key. Someone who picks up a lost key board can't make it sign. The ATECC608 signs for
   anyone who can reach its pins.
6. **A real PIN, later.** MAC-and-Destroy is a PIN check where each wrong try burns a slot in
   hardware. Trezor Safe 7 uses it for exactly that. The first profiles have no PIN (TRUSTM.md); this
   is the chip that would make one worth adding.
7. **Fine-grained, permanent locks.** Every command has an access field per group of eight slots,
   and per pairing key. Clearing a bit in I-Config forbids that command for good. So "slot 0's key
   can never be erased or replaced, and only the console's pairing key may sign with it" is one
   I-Config write, not a whole zone lock.
8. **Already paired with a Trust M elsewhere.** Trezor Safe 7 pairs TROPIC01 with an OPTIGA Trust M, the chip
   TM1 already uses here. That is some evidence the two can live side by side.
9. **There is a model.** Tropic Square's `ts-tvl` is a Python model of the chip that libtropic's
   tutorials run against. It is a reference to test an emulator shim against, beside
   `emu/core/shims/atecc_sim.py` and `trustm_sim.py`.
10. **Cheap to try.** A standalone sample is €5 and a Mini Board €9.50 (prices below).

## Cons

1. **The console would hold a secret.** The pairing private key has to live on the Pico. Today a
   stolen console with no key gives a thief nothing, and `firmware/` holds no secret. Where it
   would live is the first open question (below).
2. **A lost pairing key is a dead key board.** If the console dies and nobody kept the pairing key,
   the key board can't sign again, even though its key is fine. A Safe should have other owners
   anyway (the README's rule), but this is a new way to lose an owner.
3. **The default pairing key is public.** Every chip ships with Tropic Square's key in pairing slot
   0, and its private half is in libtropic (`src/libtropic_default_sh0_keys.c`). Tropic Square's
   note says to use it once: write our own key to another slot, then invalidate slot 0. Until then,
   anyone with libtropic can talk to the chip. A chip that comes with only our key needs a custom
   part number from Tropic Square.
4. **The session crypto is new code on the console.** X25519, AES-GCM and SHA-256 (with HKDF) have
   to run on the Pico, in a Noise handshake. MicroPython has SHA-256, and `cryptolib` has AES. X25519
   and GCM would be new pure-Python code, as `p256.py` is today. Its speed on the RP2350 is not
   measured. The other path, libtropic as a C module, means a custom MicroPython build (below).
5. **SPI, not I2C.** Four signals instead of two. key-c carries only SDA and SCL on D+ and D−
   (`hardware/key-pcb/PROPOSALS.md`). A TROPIC01 key needs a different plug, or two more contacts.
6. **QFN32 at 0.4 mm pitch.** Not hand-solderable the way key-a's SOIC-8 is. JLCPCB can place it;
   a bench build means the Mini Board or a stencil and hot air.
7. **Its certificate doesn't vouch for a key.** The chip's certificate proves the session is with a
   genuine TROPIC01. It doesn't sign "this public key was made on this chip". So a gas relay
   ([ATTESTED-KEYS.md](ATTESTED-KEYS.md)) still couldn't check that on its own. The bench would
   still make an attestation key, as that proposal plans for the ATECC. The Trust M stays the only
   chip here whose factory key can sign a binding.
8. **A known fault-injection attack.** Advisory `ODR_TR01_SA_2026012900` (disclosed 2026-06-03,
   CVSS 5.7): a laser fault during boot can skip the firmware signature check and run an attacker's
   firmware. It needs the chip desoldered and decapsulated, a lab Tropic Square puts at over €30,000,
   and 3–4 weeks. It affects every production part. A silicon fix is "in development". For a key
   in a 2-of-3 Safe that is a small risk, but it should be in our threat model in writing.
9. **No certification we can point to.** The page sells openness, not a Common Criteria or FIPS
   certificate. That is a choice, not a flaw, but the Trust M has one and the TROPIC01 doesn't
   claim one.
10. **Young parts and young firmware.** Application firmware is at 2.x, the user API at 1.4, and
    libtropic at 4.2. The chip's firmware is updated in the field (libtropic ships the update
    files, `TROPIC01_fw_update_files`), so we would have to pin a firmware version, as we pin
    MicroPython.
11. **Pairing key slots don't like the cold.** They live in I-Memory, rated −20 °C to 85 °C, and
    firmware before 2.0.0 fails a pairing key write silently outside that range.

## What it unlocks

- **A key that is bound to its console.** The key signs only for the console that holds its pairing
  key. With a second pairing key held by the owner (on paper, in another console), losing the
  console stops being fatal. That is a choice we would make per profile.
- **A PIN on the key itself.** MAC-and-Destroy, with tries counted by the chip, not the Pico. The
  console would ask for the PIN on its own screen before it opens a session.
- **A use counter we can trust.** The 16 monotonic counters could count signatures, as LimitedUse
  does on the ATECC, but checked through a session nobody else can open.
- **A boot check that is more than a serial.** At every boot the console verifies the chip's
  certificate chain to Tropic Square's root, opens a session, reads slot 0, checks `ORIGIN` is
  "generated", and compares the owner with the pin. The ATECC608 can give us only a serial.
- **An audit trail down to silicon.** For a project that publishes its own fingerprint and its own
  CI checks, a chip whose RTL and firmware we can cite by commit is the same story told one layer
  further down.

## What it doesn't unlock

- **No EOA owner.** No secp256k1, so the key can't be a plain Ethereum account. It stays a passkey
  signer, as every key here is.
- **Ed25519 doesn't help a Safe.** Safe has no Ed25519 signer. It could sign other things (a release
  note, a bench record), nothing onchain.
- **No transferable attestation** (Con 7).

## Open questions

These need an answer, with evidence, before any I-Config write or pairing key invalidation. Both
are permanent.

1. **Where the console's pairing key lives.**
   - In `secrets.py`, like the Wi-Fi password: simplest, and anyone with the console's flash has it.
   - In the RP2350's OTP, with its page locks: harder to read, but a permanent write to the board
     (AGENTS.md: only when asked for exactly that).
   - Made by the key ceremony on the console and never shown, with a second one for the owner to
     keep: closest to "a key that can't leak", and the most to get wrong.
2. **Pure MicroPython or a C module.**
   - Pure MicroPython keeps the console image as it is: every byte that runs is in
     `firmware/manifest.json`. X25519 and AES-GCM would need test vectors in `test-vectors/`, run
     on CPython and MicroPython, the way the Safe hash is checked today.
   - libtropic as a user C module (it has an RP2040/RP2350 port, `hal/rpi-pico/`, community
     maintained) is faster and is the vendor's code. But the release fingerprint covers the `.py`
     files, not MicroPython itself. A custom MicroPython build would have to be pinned and
     fingerprinted too, and that is a bigger change than the chip.
3. **The plug.** A key with SPI needs four signals plus power and ground.
   - USB-C's SBU1 and SBU2 could carry two of them, but they swap when the plug flips. CC would
     have to tell the console which way round it is.
   - A pogo key with seven pads (key-d has five) is simpler.
   - Or a key that keeps an I2C chip and adds nothing.
4. **Which Pico pins.** On the Waveshare build, GP2–5, GP8–13 and GP15–21 are taken, and GP6 and GP7
   are key-c's (`firmware/board.py`, PROPOSALS.md). The free ones (GP0, GP1, GP14, GP22, GP26–28)
   don't make a full hardware SPI0, so it would be `SoftSPI` or a moved pin. At 1–4 MHz, SoftSPI
   should be enough for a command every few seconds. Not measured.
5. **Which firmware we pin.** The chip's application and SPECT firmware versions, and whether the
   console refuses a chip whose firmware it doesn't know (`Get_Info_Req` reports them).
6. **What the profile forbids.** Probably: `ECC_Key_Erase`, `ECC_Key_Store` and `ECC_Key_Generate` on
   slot 0's group after the ceremony; `ECDSA_Sign` only from the console's pairing slot; no
   `I_Config_Write` after the seal. Each one is permanent, so each one goes on a sacrificial chip
   first, as T9 did on TM2.

## Ordering a devboard

From Tropic Square's order form (2026-10-19). Prices are without VAT. An order is reviewed, then
they email the final shipping cost (€35–55+ outside the EU), then you pay. The form asks for a
purpose and a description of the use.

| Board | Price | What it is | For us |
|---|---|---|---|
| **Mini Board** | €9.50 | 17 × 12 mm module, castellated SPI pads | **The one to wire to the dev console.** Breadboard it, or solder it like a part |
| **MIKROE Click** (third party) | €20 | mikroBUS SPI board | Also jumper-wireable; MikroE's own libraries |
| **USB DevKit** (TS1303) | €50 | STM32U5 + TROPIC01 on a USB stick, the API over a serial terminal | Learn the chip from a laptop with libtropic's `tropic01_util`, no Pico code at all |
| Raspberry Pi Shield (TS1501) | €20 | 40-pin header, SPI | Only if we test from a Pi with libtropic's Linux examples |
| Arduino Shield | €20 | Arduino SPI header | Not needed |
| Standalone Sample | €5 | the bare QFN32 chip | For a key PCB, later |

**A first order:** one USB DevKit, two Mini Boards and two or three standalone samples, about
€85 before shipping. Tell them the use honestly: a prototype secure element for a Safe multisig
signer, open source, MicroPython on a Raspberry Pi Pico 2 W.

**Before it arrives** (no hardware, nothing permanent):
1. Install `ts-tvl` and run libtropic's model tutorials on a laptop: the handshake, `ECC_Key_Generate`,
   `ECDSA_Sign`, `ECC_Key_Read`.
2. Check a model signature against `firmware/webauthn.py`: sign a WebAuthn digest with P-256 in
   the model, and verify it with the console's own P-256 code.
3. Write the Noise handshake in MicroPython against the model, and time X25519 on a Pico 2 W.
   This answers open question 2.

**When it arrives** (each step stops before anything permanent):
1. **USB DevKit:** read the chip ID, the certificate store and the firmware versions. Verify the
   certificate chain on a laptop. Ping over the default pairing key.
2. **Mini Board on the dev console:** SoftSPI on free pins, `Get_Info_Req`, then a session with the
   default pairing key, then a key in a spare slot, then a signature verified on the Pico.
3. **An onchain check, as LOCKING.md did for the ATECC:** the passkey factory's `getSigner` for the
   new key, and `isValidSignatureForSigner` on Base Sepolia for a test hash. No deploy, no funds.
4. **Only then, on a sacrificial Mini Board:** write our pairing key, invalidate slot 0, clear the
   I-Config bits. Read back every refusal, as TM2 did for the Trust M.
5. Record each step in the [buildlog](../buildlog/BUILDLOG.md). If it goes on, it gets its own
   profile, ceremony and doc, like [TRUSTM.md](TRUSTM.md).

## Sources

Read 2026-10-19:
- Product page: https://www.tropicsquare.com/tropic01
- Order form: https://www.tropicsquare.com/order-devboard-form
- Developer zone: https://tropicsquare.com/tropic01-developer-zone
- https://github.com/tropicsquare/tropic01, `doc/`:
  - datasheet rev A.11
  - user API 1.4.0
  - application notes 002 (PIN verification), 003 (identity and PKI), 005 (first pairing key)
    1.3, 006 (config objects), 007 (firmware update), 008 (security architecture)
  - security reports `ODR_TR01_PSR_001`–`006`
  - security advisory `ODR_TR01_SA_2026012900`
  - catalog list 0.2
- libtropic 4.2.0: https://github.com/tropicsquare/libtropic (`include/libtropic.h`, `hal/rpi-pico/`,
  `docs/compatibility/`)
- Trezor's note on how Safe 7 uses it:
  https://trezor.io/guides/trezor-devices/trezor-safe-7/what-is-the-tropic-01-chip

The ATECC608 and Trust M columns come from [LOCKING.md](LOCKING.md), [TRUSTM.md](TRUSTM.md) and the
code.
