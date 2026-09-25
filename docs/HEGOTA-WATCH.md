# Hegotá watch

> **Living notes (started 2026-09-25).** Hegotá is the Ethereum fork after Glamsterdam, expected
> in 2027. Nothing below is final. "Considered" status doesn't mean an EIP will ship. Update this
> file as EIPs move, and move anything that changes a PicoQuorum decision into the
> [kickoff](KICKOFF.md).

Why this matters to us: the key signs with **P-256** and only P-256. It can approve a Safe
transaction through a P-256 owner contract, but it can't *send* one: today an ordinary secp256k1
account holding ETH has to submit `execTransaction`. Most of the Hegotá account work is about
letting an account's code decide what counts as a valid signature. PicoQuorum is already built
that way.

## Worth watching

| EIP | What it is | What it could mean for PicoQuorum |
|---|---|---|
| [8141](https://eips.ethereum.org/EIPS/eip-8141) Frame transactions | A transaction made of frames: one validates, one approves gas payment, one executes | **The console sends the transaction itself.** A validation frame checks the chip's P-256 signature, and the account or a sponsor pays the gas, possibly in a token instead of ETH. The last approver presses Sign and the console submits over Wi-Fi: no browser wallet, no ETH-funded EOA. Simplifies [test ladder](KICKOFF.md#test-ladder) rung 3. |
| Tx assertions via state-diff opcode (number not yet confirmed here) | A frame can assert what the transaction changed | **Enforce what the screen showed.** The console could add a closing assertion ("only 50 USDC leaves the Safe, to 0xabc…") so a hidden delegatecall or surprise side effect reverts. The chip would sign the *outcome*, not just a hash. We haven't read this EIP yet; this is from its title. |
| [8250](https://eips.ethereum.org/EIPS/eip-8250) Keyed nonces | Many independent nonce lanes per account | **Parallel approval queues** (say "payroll" and "treasury moves") so one stuck proposal doesn't block the rest. Catch: Safe keeps its nonce in its own contract, so this needs a frame-native multisig or a future Safe. |
| [8272](https://eips.ethereum.org/EIPS/eip-8272) Recent roots | Frames can reference recent state roots | Mostly for privacy-pool withdrawals and expiring transactions. Maybe approvals that expire; low priority for us. |
| [8151](https://eips.ethereum.org/EIPS/eip-8151) Account-code-restricted ecRecover, [8298](https://eips.ethereum.org/EIPS/eip-8298) SETCODEFROM | Paths for accounts to leave secp256k1 keys behind | Our signers never had a k1 key. Good for the ecosystem's direction, nothing to build. |
| ML-DSA verification precompiles | Cheap on-chain post-quantum signature checks | **Post-quantum keys, but not with today's chips.** Neither the ATECC608 nor the Trust M makes ML-DSA signatures, and signing on the Pico would break "the key never leaves the chip". A new chip is a new key revision, not a new console. A hybrid owner that requires both P-256 and ML-DSA per approval is the goal to aim for. |

## Little or no effect

Removing bloom filters, dropping the storage-clear refund and refund cap, the unified tx content
floor, bumping zero-nonce storage accounts' nonces, call/return opcodes, reserving EXTENSION
(0xae), TCREATE, deactivating SELFDESTRUCT, EVM-ifying the identity precompile, and reading
BLOCKHASH from storage. At most these nudge gas costs.

## What this changes now

Nothing for rungs 1 and 2: a Safe with a P-256 owner, submitted by a browser wallet
([LADDER.md](LADDER.md)). The owner contract's signature format has since been chosen
(2026-09-25): a WebAuthn assertion over the safeTxHash, checked by Safe's passkey signer
(`firmware/webauthn.py`). A validation frame can check that same assertion, so the key would sign
nothing new.

## Sources

- [EF Protocol: The Hegotá EIP opinion post and tier list](https://blog.ethereum.org/2026/09/07/protocol-hegota-eips)
- [EIP-8081: Hardfork meta, Hegotá](https://eips.ethereum.org/EIPS/eip-8081)
- [Frames as final transaction type (ETH Daily)](https://ethdaily.io/frames-as-final-transaction-type)
- [frametx-kit: hegota-testnet and EIP-8250 keyed nonces](https://github.com/JustaLab-co/frametx-kit/pull/25)
- [Ethereum sets 2029 quantum target as Hegotá takes shape (crypto.news)](https://crypto.news/ethereum-sets-2029-quantum-target-as-hegota-takes-shape/)
- nixo.eth's summary of the features moved to "considered" (X, 2026-09-24)
