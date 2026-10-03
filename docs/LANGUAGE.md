# Words we use

How to describe the key, the console and the multisig accurately, for anyone writing about
PicoQuorum: docs, talks, posts, the [video](video/BRIEF.md). The one-line version:

> **A clone-proof key inside a loss-tolerant quorum.**

## The key: a non-exportable key in a secure element

The key's private key is **generated on the chip, never leaves it, and can't be copied**. The chip
is a **secure element**: a small, separate, tamper-resistant chip built to make and keep secrets.

It is **not a trusted execution environment (TEE)**. A TEE (Arm TrustZone, Intel SGX, a phone's
secure world) is a walled-off part of a main processor that runs general code. The secure element
is **fixed-function**. It can do only a few things:
- make a key
- sign a 32-byte digest
- give out the public key
- count uses

There's no command that exports the key, and you can't load code onto the chip. After the
[ceremony](PROVISIONING.md) seals it, nothing can replace the key or add a second one. Its close
relatives are smart cards, YubiKeys and device-bound passkeys, not phone enclaves.

### What the chip guarantees, and what it doesn't

| the chip guarantees | the chip doesn't |
|---|---|
| The key stays **secret**: it can't be read out, copied or cloned. | Know what it signs. It signs any digest it's handed. |
| On the ATECC608, every signature raises a counter nobody can lower. | Ask for a PIN. Today it has none ([SECURITY.md](SECURITY.md)). |
| On a Trust M, a factory certificate proves the chip is genuine (**attestation**). | Prove where it's been. The ATECC608C has no certificate; its ceremony record is the evidence ([SOURCING.md](../hardware/SOURCING.md)). |

That gap is why the **console** exists. It's a **trusted display**: it decodes the transaction,
rebuilds the hash from what it shows, and only then hands that hash to the chip. "What you see is
what you sign."

> **The chip guards the secret. The console guards the meaning.**

## No silent compromise

A seed phrase can be photographed or copied without anyone knowing. The attacker can wait months
before using it. A non-exportable key can only be misused by taking the key itself, and that gets
noticed: if it's in your hand, it's yours, and if it's gone, you know.

So the chip key is **clone-proof but not loss-proof**. It can still be lost or stolen, and while a
thief holds it, it can sign. What it can't be is copied in secret.

## The multisig: a loss-tolerant quorum

A multisig is the mirror image. It survives losing a key, but it's only as strong as its weakest
key, and a key that can be copied in secret is weak. Put the two together and each covers the
other's gap.

| idea | what it means here |
|---|---|
| **Threshold authorization** | M of N owners must sign, say 3 of 5. No one key can act alone. |
| **Signer diversity** | Different chips, vendors, software and people hold the keys. No single technology holds more than two. |
| **Common-mode failure** | One flaw that breaks many keys at once, like a bad firmware update or a backdoored chip batch. Diversity is the defence. |
| **Defence in depth** | The secure element, the console's rehash, the quorum and the paper recovery key are separate layers. Each one has to fail for funds to move wrongly. |
| **Rotation** | The other owners revoke a lost or stolen key and add a new one. A compromise has a recovery path. |
| **Recovery key** | A conventional seed, sealed away, for disaster recovery. It's the one key that's allowed to be copyable, because it's locked away. |

## The console

A microcontroller (the RP2350 on a Raspberry Pi Pico 2 W) with **no operating system**, running
one small MicroPython image. It's a **separate stack** from your phone and laptop, so it's a second
opinion that doesn't share their failure modes. It's not a TEE either. The RP2350 has TrustZone-M
and secure boot, and we don't use either yet ([SECURITY.md](SECURITY.md)).

## Say, and don't say

| say | don't say | why |
|---|---|---|
| non-exportable, generated on the chip | stored on the chip | "stored" suggests it was put there and could come out |
| can't be copied or cloned | can't be stolen | it can be stolen; it can't be copied |
| secure element | TEE, enclave, secure enclave | a TEE runs general code; the chip is fixed-function |
| tamper-resistant | tamper-proof, unhackable | nothing is proof against everything |
| hardware-bound key | hardware wallet | a hardware wallet usually has a seed to back up; this key has none |
| attested (Trust M only) | certified, verified chip | only the Trust M has a factory certificate |
| no silent compromise | zero risk, fully secure | a stolen key can still sign until it's rotated out |
| threshold, 3 of 5 | 3/5, majority | the threshold is a set number, not always a majority |
| rotate out | revoke the key on the chip | rotation happens in the Safe; the chip itself never changes |
| online signer, Wi-Fi console | cold storage, air-gapped | the console talks to the transaction service over Wi-Fi |
| a key with no seed phrase | seedless backup | there is no backup; the quorum is the backup |
