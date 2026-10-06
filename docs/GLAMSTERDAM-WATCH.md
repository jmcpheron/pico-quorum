# Glamsterdam watch

> **Living notes (started 2026-10-06).** Glamsterdam is the Ethereum fork after Fusaka. It went live
> on **Sepolia** on 2026-10-06 at 13:53:36 UTC. Hoodi and mainnet have no date yet. Update this file
> as it moves. The fork after it is in [HEGOTA-WATCH.md](HEGOTA-WATCH.md).

**It is not on Base, nor on Base Sepolia.** Base runs its own forks (Azul, Beryl, Cobalt, Denim in
2026), and none of them lists a Glamsterdam EIP ([docs.base.org/upgrades](https://docs.base.org/upgrades/overview),
read 2026-10-06). PicoQuorum's test Safes are on Base Sepolia, so nothing here changes them yet.
To try Glamsterdam today, use Ethereum Sepolia (chain 11155111). The console has no service for it
(`quorum_cfg.py` "services"), so that would mean a firmware change and a new release.

What it doesn't change: the console signs a WebAuthn assertion over the safeTxHash, and Safe's
passkey signer checks it through the P-256 precompile (EIP-7951 on Ethereum since Fusaka). Nothing
in Glamsterdam touches either.

## Worth watching

| EIP | What it is | What it could mean for PicoQuorum |
|---|---|---|
| [7708](https://eips.ethereum.org/EIPS/eip-7708) ETH transfers emit a log | Every ETH transfer, including one made inside a contract call, logs an ERC-20 `Transfer(from, to, value)` from `0xff…fe` | **See a Safe get funded without tracing.** A Safe's incoming ETH from another contract leaves no log today. The app could watch a practice Safe's address ([ONBOARDING.md](ONBOARDING.md)) with one `eth_getLogs` and say "it arrived", before the Safe is even deployed. |
| [8037](https://eips.ethereum.org/EIPS/eip-8037) State creation gas | New state is priced per byte: a new account 25,000 → 183,600 gas, a new storage slot 20,000 → 97,920, contract code about 8× | **Deploying costs much more on Ethereum.** A Safe proxy and a passkey signer are each a new account with code and storage. Measure the practice Safe's one deploy transaction on Sepolia before the project Safe ([GOVERNANCE.md](GOVERNANCE.md)) is made on Ethereum. |
| [2780](https://eips.ethereum.org/EIPS/eip-2780), [8038](https://eips.ethereum.org/EIPS/eip-8038), [7778](https://eips.ethereum.org/EIPS/eip-7778), [7976](https://eips.ethereum.org/EIPS/eip-7976), [7981](https://eips.ethereum.org/EIPS/eip-7981) The other repricings | Intrinsic gas split into its parts, state access repriced, no refunds in block gas, dearer calldata and access lists | **Gas estimates move.** The app estimates each send and adds 30%; it hardcodes no gas. The EF warns about code that assumes how much gas is left, and Safe's `execTransaction` checks `gasleft()` against `safeTxGas`. PicoQuorum always proposes `safeTxGas` 0, so the check is trivial, but run a passkey-signed `execTransaction` on Sepolia to be sure. |
| [7997](https://eips.ethereum.org/EIPS/eip-7997) Deterministic factory | A CREATE2 factory at `0x4e59…956C` on every chain, without the keyless-transaction trick | **The same addresses on a new chain.** A passkey's owner address is the same everywhere only where Safe's passkey factory is at the same address. A standard factory makes that easier to guarantee on the next chain. Nothing to build. |
| [7954](https://eips.ethereum.org/EIPS/eip-7954) Larger contracts, [8246](https://eips.ethereum.org/EIPS/eip-8246) No SELFDESTRUCT burn | A higher contract size limit; SELFDESTRUCT can no longer burn ETH | Nothing for the console. 8246 makes 7708's logs complete. |

## Little or no effect

[7732](https://eips.ethereum.org/EIPS/eip-7732) (enshrined proposer-builder separation) and
[7928](https://eips.ethereum.org/EIPS/eip-7928) (block-level access lists) change how blocks are
built and checked, not what a transaction does. [7843](https://eips.ethereum.org/EIPS/eip-7843)
(SLOTNUM), [8024](https://eips.ethereum.org/EIPS/eip-8024) (SWAPN, DUPN, EXCHANGE), 7688, 8045, 8061
and 8282 are consensus or compiler matters.

## What to check, and how

1. On Ethereum Sepolia, deploy a practice Safe with `practiceSafe()` (`web/src/safe.mjs`) and
   compare its gas with the same transaction on Base Sepolia.
2. Execute a passkey-signed transaction there (`tools/quorum live exec`, [LADDER.md](LADDER.md)).
3. Send ETH to a Safe from a contract, and find the 7708 log with `eth_getLogs`.

None of this has been run yet.

## Sources

- [Glamsterdam testnet announcement (EF blog, 2026-09-17)](https://blog.ethereum.org/2026/09/17/glamsterdam-testnet-announcement)
- [ethereum.org: Glamsterdam](https://ethereum.org/roadmap/glamsterdam/)
- [Base upgrades](https://docs.base.org/upgrades/overview)
- The EIPs linked above, read 2026-10-06.
