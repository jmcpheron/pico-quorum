# Security

## Reporting a vulnerability

Please report it privately: [open a security advisory](https://github.com/jmcpheron/pico-quorum/security/advisories/new)
on this repository. Don't open a public issue for anything that could put a Safe's funds or a key at
risk. PicoQuorum is experimental and maintained by one person, so expect a reply within a few days,
not hours.

## PicoQuorum console (the production image)

The Pico is one owner of a Safe multisig. Losing it, or everything on it, costs one signature
toward the threshold, never the Safe: the other owners can execute without it and rotate it out.

**The signing boundary is the device's own rehash.**
- The transaction service is untrusted. Each transaction is rehashed on the Pico (EIP-712, with the
  chain and the Safe pinned) from the same fields `decode.py` puts on the screen.
- A service hash that differs means the transaction is refused.
- The chip signs a WebAuthn assertion over the hash computed on the device, only after every page
  was seen and A was held (3 s for red).
- A delegatecall is refused unless it is a multiSend to a pinned batcher or goes to a pinned
  delegate, and so is any operation other than call and delegatecall.
- With several Safes (`QUORUM_SAFES`), each transaction is hashed with its own Safe's pinned chain
  and address, and its signature goes to that chain's service (pinned in `quorum_cfg.py`). A
  transaction served for one Safe but hashed for another chain or Safe is refused. Known
  contracts and tokens are per chain, so an address pinned on Base is unknown on Ethereum.

**What is on the board.** Exactly the console image in `firmware/manifest.json`; `tools/fw verify`
checks every hash.
- `quorum.sign_it` is the only code in the image that asks the chip to sign.
- Nothing in the image can make, replace, switch or lock a key; the ceremony image does that.
- `ALLOW_*` flags, a software-key fallback and the WiFi REPL are all ignored by this image.

**The pin.** `QUORUM_EXPECT` names the chip's serial, the slot, its lock and the owner address its
key must produce. The console checks it at start and again right before each signature. A chip
swapped on the board, or another slot, signs nothing.

**The counter is an audit hint, not a lock.**
- Slot 0 has LimitedUse, so the chip raises counter 0 before every signature.
- The console shows the count and flags any rise it did not cause ("signed outside this console").
- Anyone on the chip's bus can raise the counter, but nobody can lower it. So a hidden signature
  shows up, and a raised count can mean a false alarm.

**Still open to whoever holds the board:**
- The USB REPL stays on, a decision made on 2026-09-25, because the tooling uses it.
- There is no chip PIN (see [PROVISIONING.md](PROVISIONING.md)).
- Anyone with the board and a USB cable, or with the chip's I2C bus, can have the chip sign any
  digest. That is one owner's signature, and it shows up in the counter.
- The WebAuthn "user verified" flag is the firmware's word that someone held A, not a
  chip-enforced factor.
- There is no secure boot. The RP2350's is on the list.

**The network.**
- HTTPS to api.safe.global checks the server's certificate against three pinned roots
  (`firmware/vhttp.py`). The clock comes from NTP, never earlier than the build.
- The API key goes only over that connection, and only after the handshake.
- TLS protects the API key, the owner and threshold display and the service's availability; the
  rehash protects the signature.
- The Safe's owners and threshold come from the service: a lying service can mislead the display,
  not what is signed.

**The chip's config.**
- Chip #1 runs Microchip's test table (LOCKING.md).
- Fresh chips get quorum v1: one sealed key, everything else dead, every zone locked against a CRC
  the chip checks ([PROVISIONING.md](PROVISIONING.md)).
