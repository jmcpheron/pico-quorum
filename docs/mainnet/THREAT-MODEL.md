# Threat model: a Trust M PicoQuorum signer as one owner of a Safe

Written for the other owners. It says what you can rely on, what you can't, and what you can
check yourself.

## What the device is

- A Raspberry Pi Pico 2 W with a small screen and buttons or a knob.
- An Infineon OPTIGA Trust M secure element (CC EAL6+), on an Adafruit breakout.
- The chip holds one P-256 key. The key owns the Safe through Safe's own passkey signer
  (`SafeWebAuthnSignerProxy`, safe-modules passkey v0.2.1), so its owner address is a small
  contract, not an EOA.

## What you can rely on

**The key never leaves the chip.**
- It was made on the chip (GenKeyPair in object E0F1).
- After the seal (T7), the chip refuses to make it again or replace it.
- No command exports a private key.

**The device shows what it signs.**
- The console downloads the transaction and recomputes its Safe hash on the device, with the
  chain and Safe pinned.
- It shows the decoded fields on screens that must all be seen, and signs only after a held
  button.
- If the service's hash doesn't match the fields, it refuses.
- It refuses delegatecalls, except a multiSend to the pinned MultiSendCallOnly.
- Owner and threshold changes are red and need a 3 s hold.

**One owner, not the Safe.** Losing or compromising the device costs one signature out of the
three needed. The other owners can execute without it and rotate it out.

**You can check the chip yourself.**
- `tools/quorum verify attest-<serial>.json --chain eth` checks four things:
  - Infineon's CA signed the chip's certificate.
  - The chip's factory key signed the binding to this key.
  - The owner address follows from the key.
  - Ethereum's passkey factory agrees on that address.
- It needs Node, nothing else from the project, and no board. See COSIGNERS.md.

## What you can't rely on

**Whoever holds the device can make it sign anything.**
- The USB REPL is open, there is no PIN, and there is no secure boot.
- With the board and a cable, anyone can run their own code and have the chip sign any digest,
  including a Safe transaction you never saw.
- That is one signature. It still needs two more owners.

**A Trust M keeps no record of its signatures.**
- The ATECC version counts every use of its key in a counter that only goes up. The Trust M
  profile has no such counter.
- Its "security event counter" only rises under bursts and fades back at 1 every 5 s. It is a
  brake, not a log.
- Measured on a sacrificial chip, the brake slows a burst; it doesn't stop one. The first ~127
  signatures in a row run at about 7 a second. After that each one takes longer, settling near
  one every 5 seconds. That's still thousands an hour.
- So if the device was out of the operator's hands, assume it signed something, and rotate it
  out.

**What the binding proves.**
- The chip's factory key (E0F0) carries Infineon's certificate, and it signed the statement
  "this chip (UID) holds this key (E0F1, qx, qy)". That proves a genuine Trust M signed the
  statement.
- But E0F0 signs whatever it is asked. Someone holding a genuine chip could make such a
  statement for a key kept anywhere.
- What ties the key to the chip:
  - the record and the seal, read off the chip (the lifecycle values in the bundle)
  - the ceremony being run on the device
  - the operator's word

  Neither the lifecycle values nor the ceremony is signed by the chip.

**What the bundle reports.**
- The lifecycle and access conditions in `attest-<serial>.json` are what the chip told the board
  that read it. Firmware that lies could fake them.
- The certificate and binding checks can't be faked without Infineon's keys.

**The firmware is the operator's.**
- `tools/fw verify` checks that every file on the board matches a given commit of the
  repository. Only someone with the board can run it.
- A co-signer can't see from outside which firmware runs.

**The transaction service.**
- The owners, threshold and queue come from Safe's transaction service. A lying service can show
  wrong owners or a wrong count.
- It can't make the device sign a transaction other than the one shown, because the device
  recomputes the hash.

**Infineon's own objects before T9.** On a chip that has not been through T9, the factory key's
rules can be rewritten by anyone on the chip's bus, and the factory key replaced (shown on a test
chip). That can't touch the Safe key or fake Infineon's certificate. It can only break the chip's
proof of being genuine. T9 freezes those objects too, and `tools/quorum verify` now checks that the
factory key still answers a fresh challenge (`live:`) and still has Infineon's rules.

**The chip generation.** TM1 looks like a first-generation Trust M (Infineon CA 101, firmware
build 0809). This has not been confirmed from Infineon's documents. The later generation's
authorization features, which a PIN would need, may not be there.

**The breakout.** Adafruit 4351 is an evaluation board. The secure element resists physical
attack. The board, the I2C wires and the Pico do not.

## What follows

**Not for a key whose single compromise loses funds.** It is one owner among several, and the
others should be different kinds of device in different hands (CONFIGURATION.md).

**Treat it like a hardware wallet that has no PIN:**
- Keep it physically secure.
- If it was out of sight, rotate it.

**Before you sign anything the Pico also signed,** check what you are signing on your own device,
as you would anyway. A Pico confirmation means "the operator looked at this on the Pico". It does
not mean "this is safe".
