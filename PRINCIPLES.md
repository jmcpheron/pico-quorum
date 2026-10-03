# PicoQuorum principles

**Keys that can't leak.**

Self-custody usually comes down to one of two bargains. You can keep a seed phrase, twelve words
that are the whole key, which can be photographed, phished, or lost in a house fire. Or you can
trust one company's stack, from the chip up to the app, and hope it never fails. We want a third
option that people can understand, check, and build themselves.

Start with a key that is born inside a chip and can never leave it. It isn't written down and it
isn't exported or backed up. It can't be copied, so you always know where it is: if you're holding
it, it's yours. If it's gone, it was lost or stolen, and you know that today, not when the funds
move.

One key is still one point of failure, so no key stands alone. Each one is a single owner of a
multisig, and the quorum carries the weight. Lose a key and the other owners rotate it out. This
used to need custom cryptography. Now it doesn't: P-256, the curve these chips sign with, is native
on Ethereum since Fusaka ([EIP-7951](https://eips.ethereum.org/EIPS/eip-7951)) and on the rollups
([RIP-7212](https://github.com/ethereum/RIPs/blob/master/RIPS/rip-7212.md)). Safe's audited passkey
signer accepts these keys as owners, so we deploy no contracts of our own.

PicoQuorum is our attempt to show what that makes possible, teach it, and build it in the open.

## The principles

### 1. Keys that can't leak

The private key is generated inside the secure element. It never leaves the chip and never exists
as a seed phrase. After the provisioning ceremony locks the chip, nothing can read it, replace it
or make a second one ([PROVISIONING.md](docs/PROVISIONING.md), [LOCKING.md](docs/LOCKING.md)).

A key that can't be copied makes holding it mean something. Someone who steals it can use it while
they hold it, but they can't keep a copy after you take it back. And you'll notice it's missing.

### 2. Lose a key, not the Safe

Every chip key is one owner of a multisig. Losing one costs a signature toward the threshold, never
the funds. The other owners can still execute, and they rotate the lost key out
([SECURITY.md](docs/SECURITY.md)). A key you can't back up is only safe inside a quorum that doesn't
need it.

### 3. Mix your defences

No single technology should hold more than two keys. The shape we aim for is 3 of 5: a warm wallet
that proposes and pays gas, a conventional hardware wallet off-site, two PicoQuorum keys with
trusted people, and a paper seed sealed away for disaster recovery
([target shape](docs/KICKOFF.md#target-multisig-shape-for-reference)). Chip keys add to good
practice. They don't replace it.

### 4. Nothing signs unseen

The console decodes each transaction into plain language and rebuilds its hash from the same fields
it shows. Only that hash goes to the chip. A digest it didn't compute is never signed, and a service
that lies about a hash is refused ([safe_tx.py](firmware/safe_tx.py), checked against every vector
in [test-vectors/](test-vectors/)).

### 5. A separate stack

Your phone and laptop run huge operating systems, share their supply chains, and share their bugs.
The console is a microcontroller with no operating system. Its whole image is about nine thousand
lines of MicroPython, small enough for one person to read. When it agrees with your wallet app on
what a transaction does, that's a real second opinion: a different stack, with different code and
different failure modes.

### 6. Use what the chain already speaks

We use P-256 natively and stick to contracts that are already audited. We write nothing on chain
unless we have to. Safe comes first because it's the most widely used and audited multisig. Any
smart account that checks P-256 can come later, and frame transactions
([EIP-8141](https://eips.ethereum.org/EIPS/eip-8141)) may let the console submit approvals itself
([HEGOTA-WATCH.md](docs/HEGOTA-WATCH.md)).

### 7. Source for everything

The firmware, the key PCB, the case, the parts list, the ceremony scripts and the build log, mistakes
included, all live in git ([hardware/](hardware/), [cad/](cad/), [buildlog/](buildlog/)). If you
can't rebuild it from the repo, it isn't open. The hardware is licensed so it stays that way: anyone
can make and sell keys, and anyone who changes the design publishes the change
([CERN-OHL-S-2.0](hardware/LICENSE)).

### 8. Parts from people

A chip can come from a hobbyist's drawer, a co-op batch order, a trusted assembly line or an
independent test lab. Each of these has a place, as long as it says what it can and can't promise.
Trust is layered and stated, never assumed. Every key, wherever it came from, passes the same
ceremony before it's locked ([hardware/SOURCING.md](hardware/SOURCING.md)).

### 9. Easy to understand

Approving a transaction is a physical ceremony. You plug in your key, read the transaction in plain
words, and hold the guarded green Sign button. Reject is red and easy. If a step can't be explained
on the card that comes with the key, the step is too complicated and we simplify it
([owner's guide](docs/guide/README.md)).

### 10. Honest about limits

This is experimental hardware, for testnet and pocket change. We say what isn't protected yet as
plainly as what is: today there's no chip PIN, the USB REPL is on, and there's no secure boot
([SECURITY.md](docs/SECURITY.md#picoquorum-console-the-production-image)). Trust gets earned with a
track record.

## What this is for

The point isn't really to sell a device. It's to find out whether self-custody built on these
values has a real place in the world: keys that can't leak, quorums that heal, a separate stack,
and supply chains anyone can join. Building the thing is how we find out.

Start with [CONTRIBUTING.md](CONTRIBUTING.md). You can run the whole approval flow on a laptop
with no hardware, build a dev console for about $35, or get in on the next batch of keys.
