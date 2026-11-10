# Security

## Reporting a vulnerability

Please report it privately: [open a security advisory](https://github.com/jmcpheron/pico-quorum/security/advisories/new)
on this repository. Don't open a public issue for anything that could put a Safe's funds or a key at
risk. Picoquorum is experimental and maintained by one person, so expect a reply within a few days,
not hours.

## Picoquorum console (the production image)

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

**USB.** From 2026.11.1 the running console holds USB itself ([USB-LINK.md](USB-LINK.md)): a
computer gets the link's few requests and never the REPL. Ctrl-C is off from the first line of
`boot.py`, and `main.py` ends in a loop that never returns. The link reads what the console already
shows, and writes Wi-Fi, the Safes or the maint file only when the person holds Sign on the
console's own screen. It never signs and never touches the chip. The REPL is reachable only in
maintenance: the maintenance key held at power-up, or the link's maint ask, accepted on the screen.
This replaced the 2026-09-25 decision to keep the USB REPL on.

**Still open to whoever holds the board:**
- The ROM bootloader. Anything holding the USB port can still put an ESP32-S3 into its ROM
  bootloader with the DTR and RTS lines and write new firmware (esptool does this, and esptool-js
  does it from Chrome); a Pico reboots to BOOTSEL on a 1200-baud touch. New firmware can make the
  chip sign anything. Closing the REPL only removes the quiet way in, through the console's own
  Python. Secure boot, and turning off USB download, close the rest; both are permanent eFuse
  settings on the S3, and neither is done.
- There is no chip PIN (see [PROVISIONING.md](PROVISIONING.md)).
- Anyone with the board in maintenance, or with the chip's I2C bus, can have the chip sign any
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
