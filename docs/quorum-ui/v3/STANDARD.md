# PQ-REVIEW-1: what a sealed cosigner showed, bound into its signature

> **A draft, 2026-10-31.** Written for PicoQuorum and as a worked example of starting a standard.
> No implementation yet; nothing here is tested. The plan around it is in [README.md](README.md).
> Normative words (MUST, SHOULD, MAY) are as in RFC 2119.

## Abstract

A cosigner is a device that holds one owner key of a multisig and approves a transaction only after
showing it to a person. Today, a signature says only *that* a key approved a hash. PQ-REVIEW-1 lets it
also say *what the device showed*:
- a fixed set of **facts** a cosigner must work out and display for each kind of thing it signs
- a **class** for what the transaction can do: routine, attention or control
- a **registry** of known code, approved by the owners
- an **intent hash** over all of that, carried inside a Safe passkey signature's WebAuthn client
  data, where the existing signer contract already accepts it

No change to Safe's contracts is needed.

## Motivation

The two largest thefts in the field didn't break cryptography. In Feb 2025, Bybit's signers
approved a Safe transaction whose screen didn't show the delegatecall that replaced their Safe's code.
On Oct 29, 2026, Binance's own signing systems reportedly produced 50 valid EIP-7702 authorizations,
one per future nonce, that handed a hot wallet to an attacker contract. In both, keys signed what
they were handed.

A device that rebuilds the hash and decodes the transaction itself fixes that for its own owner. But
nobody else can tell which kind of device signed, or what it showed. Two questions have no common
answer today:
1. What must a cosigner show before it signs, so that two different devices show the same facts?
2. How can a signature carry, verifiably, what its device showed?

## Terms

- **Subject:** the 32-byte hash a cosigner approves: a `SafeTx` hash, a `SafeOp` hash, or a Safe
  message hash.
- **Subject type:** how the subject is built from fields. v1 defines `safe-tx`; `safe-op` and
  `safe-msg` are reserved for v1.1 (see [Extension points](#extension-points)).
- **Fact:** a key and a value the cosigner works out from the subject's fields, its registry and
  its own address book, never from the service that sent the request.
- **Class:** `routine`, `attention` or `control`, worked out from the facts.
- **Registry:** a list of contracts the owners have approved, each with its runtime code hash.

## Specification

### 1. Facts for `safe-tx`

A cosigner MUST work out these facts from the `SafeTx` fields, in this order. `i` counts calls from
0; a `MultiSendCallOnly` batch is one call per entry.

| key | value |
|---|---|
| `chain` | the chain id, decimal |
| `safe` | the Safe's address, EIP-55 |
| `nonce` | decimal |
| `op` | `call` or `delegatecall` |
| `call.i.to` | address, EIP-55 |
| `call.i.value` | wei, decimal |
| `call.i.fn` | the function's signature (`enableModule(address)`), or `0x` and the 4-byte selector if unknown, or `none` for a plain transfer |
| `call.i.arg.k` | each argument: addresses EIP-55, integers decimal, bytes as 0x-hex |
| `call.i.known` | the registry entry's `name@version` for `to` (and, for a control call, for its address argument), or `unknown` |
| `gas.refund` | `none`, or the token and receiver when `gasPrice > 0` |
| `class` | from section 2 |
| `reason.j` | one line per rule in section 2 that applied, by its id (`C1`, `C4`...) |

A cosigner MUST display every fact before it accepts a signature. It MAY word and arrange them as it
likes: the facts are normative, the pixels are not.

### 2. Class

The class is the worst that applies.

| id | the transaction... | class |
|---|---|---|
| C1 | calls the Safe itself to add, remove or swap an owner, or change the threshold | control |
| C2 | enables or disables a module, sets a guard or a fallback handler | control |
| C3 | delegatecalls anything but a registry entry with role `batcher` or `message` | control |
| C4 | approves a spender for an unlimited amount, or pays a gas refund | control |
| A1 | calls a contract it can't decode | attention |
| A2 | calls a decodable contract that isn't in the registry | attention |
| A3 | sends value to an address not in the cosigner's address book | attention |
| — | none of the above | routine |

### 3. Refusals

A cosigner MUST NOT sign, however it is asked:
- **R1:** a `control` transaction whose target, or whose module, guard, handler or singleton argument,
  isn't in the registry
- **R2:** any of a run of more than 3 queued transactions for one Safe with consecutive nonces and a
  `control` class, until the run is cleared
- a subject whose facts it can't work out

It MUST offer Reject as a single action, and MUST NOT accept Sign as a single action. For `control`,
it MUST require a separate arming action before the signing action.

### 4. Registry

An entry is `(name, version, role, chainId, address, codehash)`, with role one of `module`,
`handler`, `guard`, `singleton`, `batcher`, `message`, `delegate`, `contract`. The registry's root is
`keccak256` of the entries' ABI encodings, sorted by `(chainId, address)`, concatenated.

The owners approve a registry as a Safe message whose content is the EIP-712 hash of
`PQRegistry(bytes32 root,uint64 serial)`, under domain `{name: "PQ-REVIEW", version: "1"}`. A
cosigner MUST use only a registry it has seen approved by its Safe's threshold, and the highest
`serial` it has seen. It SHOULD show a registry change as `control`.

### 5. Intent hash

```
facts  = keccak256(abi.encode(bytes32[] h))   h[n] = keccak256(utf8(key_n ‖ "=" ‖ value_n)), in section 1's order
intent = EIP-712 hash of PQReview(uint8 version,bytes32 subject,uint8 class,bytes32 registry,bytes32 facts)
         domain {name: "PQ-REVIEW", version: "1", chainId: <chain>}
         version = 1; class: 0 routine, 1 attention, 2 control; registry = the root used
```

Any party with the transaction's fields and the registry can recompute it.

### 6. Binding into a Safe passkey signature

Safe's passkey signer verifies a WebAuthn assertion whose `clientDataJSON` is built as:

```
{"type":"webauthn.get","challenge":"<base64url(subject)>",<clientDataFields>}
```

`clientDataFields` is chosen by the signer and signed with the rest. A conforming cosigner MUST
append one field:

```
"pq":"1.<class digit>.<base64url(intent), no padding>"
```

For example, PicoQuorum's fields would go from `"origin":"picoquorum"` to
`"origin":"picoquorum","pq":"1.2.f3Kk…"`. On-chain verification is unchanged. Off-chain, a Safe
service, a co-signer or an auditor MAY recompute `intent` and compare.

### 7. Extension points

- **Subject types** add a facts table (section 1) and keep everything else. Reserved:
  - `safe-op`: Safe4337Module's `SafeOp`, its facts those of the `executeUserOp` call plus
    `paymaster`, `validAfter`, `validUntil`
  - `safe-msg`: a Safe message, its facts the decoded message
  - `eip-7702`: for a cosigner that holds an EOA key. Facts `chain`, `delegate`, `nonce`, `known`.
    Refusals: chain 0, a nonce other than the account's next one, a delegate not in the registry
- **New classes:** not in v1. A v2 would add them and change `version`.
- **Other signers:** a cosigner signing with ECDSA has no client data. It MAY publish the intent
  beside the signature; binding it needs a v2.

## Rationale

- **Facts, not screens.** Devices differ in size and wording. What two devices must agree on is what
  they worked out, so that's what is hashed.
- **Inside the WebAuthn client data,** because Safe's passkey signer already signs and accepts it.
  Carrying the intent costs nothing on-chain and needs no deployment.
- **The registry as a Safe message,** because the owners are the only authority a cosigner should
  trust, and PicoQuorum already checks release approvals this way.
- **ERC-7730** (clear-signing descriptors) describes how to *format* a contract's calls for a
  screen. PQ-REVIEW-1 describes what a cosigner must *attest* it showed. A 7730 descriptor can be
  how a cosigner decodes a call into section 1's facts; they fit together.
- **EIP-712** for the hashes, so a contract can check them later: a Safe guard could recompute
  `class` from the transaction and refuse one whose cosigner signature says otherwise.

## Backward compatibility

Safe's passkey signer is meant to take any `clientDataFields`. That has to be checked on a fork
(`tools/quorum up`) before this draft relies on it. A verifier that ignores the `pq` field is
unaffected.

## Test vectors

Planned in `test-vectors/review/`. Each holds a `SafeTx`, a registry, an address book, and the
expected facts, class, refusals and intent:
- a transfer
- the 4337 batch with the module in the registry
- the same batch without it (R1)
- a 4-nonce run of `enableModule` (R2)
- an unknown delegatecall
- a tampered request

A standard is as good as its vectors. Two implementations that agree on them (the MicroPython console
and a Rust `pq-review`) are the bar for calling this more than a draft.

## Security considerations

- **The intent proves what a device says it showed, not that a person read it,** nor that the
  device is honest. A compromised cosigner can produce a valid intent for a lie. Independent
  devices from different makers, and a guard that recomputes the class on-chain, reduce that.
- **The registry is the new high-value target.** Its approval should be `control` with a delay, and
  it should change rarely.
- **The facts can name people** (from the address book). Only their hash travels.
- **Replay:** the subject already binds chain, Safe and nonce; the intent binds the subject.

## How to grow a standard from this

This draft follows a pattern that works for small, sharp standards:
1. **Name the failure, with real incidents.** Not "security" in general: *a signature doesn't
   say what was shown.*
2. **Find the smallest surface two parties must agree on.** Here, the facts and one hash, not
   screens or wording.
3. **Reuse what's deployed.** EIP-712, Safe messages, the passkey signer's client data. Each
   reuse is an argument nobody has to win.
4. **Write the vectors before polishing the prose,** and get two independent implementations to
   agree on them.
5. **Leave named extension points** (subject types), and say what is out of scope for this version.
6. **Then take it outside:** a thread on Ethereum Magicians, a pull request to the ERCs repository as
   a draft ERC, and talks with the people behind ERC-7730 and Safe's passkey signer, whose work it
   leans on.
