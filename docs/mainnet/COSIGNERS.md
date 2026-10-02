# For the other owners of the Safe

One owner of our Safe is a PicoQuorum signer: a small device with a screen and a secure chip
that approves Safe transactions. This page covers four things:
- how to check that signer yourself before you accept it as an owner
- what changes for you (very little)
- why execution sometimes goes through a script
- what to do if the device is lost

The honest limits are in [THREAT-MODEL.md](THREAT-MODEL.md). Please read it once.

## 1. Check the signer before it becomes an owner

The operator publishes a ceremony record for each chip: `docs/mainnet/attest/attest-<serial>.json`
in this repository. It holds only public values, read off the chip:
- its ID
- Infineon's certificate
- the public key
- the binding statement
- the chip's lifecycle settings

**With Node 20 or later:**
```sh
git clone https://github.com/jmcpheron/pico-quorum && cd pico-quorum
tools/quorum verify docs/mainnet/attest/attest-<serial>.json --chain eth --safe eth:<SAFE ADDRESS>
```

**Every line should say `pass`.** What the lines mean:

| Line | Meaning |
|---|---|
| factory certificate signed by Infineon OPTIGA(TM) Trust M CA … | the chip is a genuine Infineon Trust M (Infineon's CA key is pinned in the tool) |
| record (F1D0) / owner address | the chip's record names its key, and the owner address follows from that key |
| binding (F1D1) | the chip's factory key signed "this chip holds this key" (read the caveat in THREAT-MODEL.md) |
| sealed (as reported) | the key, record and binding can never be changed |
| spares (as reported) | `note` until the ceremony's last step froze the rest of the chip; `pass` after |
| Ethereum: getSigner gives the same owner | Safe's own passkey factory, onchain, derives the same owner address from this key |
| Ethereum: an owner of Safe … | after it has been added |

**Without the tool, check the one line that matters onchain:**
1. On Etherscan, open Safe's passkey signer factory
   [`0x1d31f259ee307358a26dfb23eb365939e8641195`](https://etherscan.io/address/0x1d31f259ee307358a26dfb23eb365939e8641195#readContract).
2. Call `getSigner(x, y, verifiers)` with:
   - `x`, `y`: the public key printed in the record (`qx`, `qy` in [docs/TRUSTM.md](../TRUSTM.md) for TM1)
   - `verifiers` = `0x0100c2b78104907f722dabac4c69f826a522b2754de4`
3. It must return the owner address you are asked to add.

## 2. Day to day

- **Propose and sign as you always do,** in the Safe web app with your own wallet.
- **The Pico's approval** shows up as a confirmation from its owner address. It is a contract
  signature, verified onchain by its signer contract.
- **What a Pico approval means:** the operator saw the decoded transaction on the device,
  page by page, and held the button. The device recomputed the transaction hash itself. Check
  the transaction on your own device anyway.
- **The Pico refuses:**
  - a transaction whose hash doesn't match its fields
  - a transaction for another Safe or chain
  - any delegatecall except a batch through Safe's MultiSendCallOnly
- **It shows these red, for a long hold:**
  - owner and threshold changes
  - unknown contracts
  - gas refunds

## 3. Execution

**Why the Safe web app can't execute these.** Once a transaction carries the Pico's contract
signature, and the threshold is 2 or more, the web app cannot execute it. It fails with
`GS021`. That's a web app limitation, not a bad signature.

**What to do instead:**
- Execute with `tools/quorum live exec --chain eth <nonce>`.
  - It lays the signatures out correctly and sends from whatever wallet you choose.
  - Executing needs no owner key, only gas.
- Usually the operator does this. Anyone can.

## 4. If the device is lost, stolen, or was out of the operator's hands

**Treat its key as compromised.** It can still sign, and a Trust M keeps no record of its
signatures.

1. The Safe needs 3 of 5. The other 4 owners can still do everything.
2. Propose **swapOwner**(prev, the Pico's owner address, a new owner) in the Safe web app.
   - Or **removeOwner** with the threshold kept at 3 if there is no replacement yet.
   - Three owners other than the Pico sign. Execute it as in section 3, or from the web app if
     no contract signature is on it.
3. Until it is executed, look harder at anything that already carries the Pico's confirmation.

**Never accept an urgent owner change** that arrives only by chat. Confirm by voice, or in person.
