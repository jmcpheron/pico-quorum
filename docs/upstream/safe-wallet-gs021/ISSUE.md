**Title:** Executing a queued tx fails with GS021 when a confirmation is an EIP-1271 contract signature

---

## Bug description

Safe{Wallet} can't simulate or execute a queued transaction in a Safe with a threshold of 2 or more when one of the confirmations the Safe has to check is an EIP-1271 contract signature. I reproduced this with a `SafeWebAuthnSignerProxy` (passkey signer) as the contract owner. Rebuilding the transaction keeps the contract signature's standalone offset of 65, which points inside the static signature region (threshold × 65 bytes), and the Safe reverts with GS021.

In the app, the Execute screen shows "Simulation failed" and "Cannot estimate", then *This transaction will most likely fail. To save gas costs, reject this transaction. Error code GS021*. Executing anyway gives *Could not submit the transaction. Error code GS021*. I saw the same in a desktop browser and a mobile browser.

The Transaction Service accepted the confirmation and returned it as `CONTRACT_SIGNATURE`.

#3673, reported for a nested Safe owner and closed as not planned, appears to have the same underlying cause.

## Environment

- Browser: Chrome (desktop), and a mobile browser
- Wallet: MetaMask
- Chain: Base Sepolia and Base. The suspected cause is in shared signature reconstruction code.
- Safe: 1.5.0 L2
- Contract owner: `SafeWebAuthnSignerProxy` (safe-modules passkey v0.2.1)

## Steps to reproduce

1. Use a Safe with a threshold of 2 whose owners include an EOA and a contract signer. I used a passkey `SafeWebAuthnSignerProxy`.
2. In Safe{Wallet}, propose a transaction and sign it with the EOA.
3. Confirm it with the contract owner: `POST /api/v1/multisig-transactions/{safeTxHash}/confirmations/` with its contract signature (v = 0). The service answers `201` and lists the confirmation as `CONTRACT_SIGNATURE`.
4. Open the transaction in Safe{Wallet} and click **Execute**.

### Self-contained reproduction (local fork, throwaway keys)

Step 3 is the hard part to set up by hand, so the script below does everything on a local Anvil fork of Base Sepolia with throwaway keys. It deploys passkey signers, creates Safes 1.5.0 (canonical deployments), and builds each Safe's confirmations in the form the Transaction Service returns them.

It then lays them out two ways with protocol-kit's `buildSignatureBytes`:
- **current:** each confirmation as a plain signature, as `createExistingTx` does today
- **fixed:** the contract confirmation as `EthSafeSignature(owner, data, true)`

Each layout is simulated. The fixed one is also executed, and the script checks `ExecutionSuccess`, the recipient's balance, and the signature bytes the Safe logged.

Versions: Foundry 1.8.3 (anvil), viem 2.56.8, @noble/curves 1.9.1, @safe-global/protocol-kit 8.0.7, Node 22. Forked at Base Sepolia block 47297886.

| Safe | Confirmations, sorted by owner | Current layout | Fixed layout |
|---|---|---|---|
| 2-of-2 | EOA, contract | reverts **GS021** | executes: `ExecutionSuccess`, recipient paid, logged bytes = fixed layout |
| 3-of-3 | contract, EOA, contract | reverts **GS021** | executes: `ExecutionSuccess`, recipient paid, logged bytes = fixed layout |
| 1-of-2 (control) | contract, EOA | simulates OK | simulates OK |

The control is consistent with the offset check below: with a threshold of 1 the static region is only 65 bytes, so an offset of 65 is still valid.

<details><summary>repro.mjs (package.json: viem 2.56.8, @noble/curves 1.9.1, @safe-global/protocol-kit 8.0.7)</summary>

```js
// Reproduces GS021 in Safe{Wallet}'s execution of a queued transaction with an EIP-1271
// contract-owner confirmation, and shows the fix, on a local Anvil fork of Base Sepolia with
// throwaway keys. Nothing touches a public chain.
//
// Safe{Wallet} rebuilds a queued tx from the Transaction Service's confirmations in
// createExistingTx, adding each one as a plain signature (staticPart = the stored bytes,
// dynamicPart = ''). This script builds the same two layouts with protocol-kit's own
// buildSignatureBytes:
//   current:  what createExistingTx does today
//   fixed:    the contract confirmation added as EthSafeSignature(owner, data, true)
// Each is simulated, and the fixed one is executed. The script checks ExecutionSuccess, the
// recipient's balance change, and the signature bytes the Safe's SafeMultiSigTransaction event
// logged.
//
//   Foundry 1.8.3:  anvil --fork-url https://sepolia.base.org --port 8547
//   npm install && node repro.mjs [--rpc http://127.0.0.1:8547] [--fixture]
//
// Contracts are Base Sepolia's canonical deployments: Safe 1.5.0 L2 (safe-deployments) and
// SafeWebAuthnSignerFactory (safe-modules passkey v0.2.1).
import { createHash } from "node:crypto";
import { p256 } from "@noble/curves/p256";
import { EthSafeSignature, buildSignatureBytes } from "@safe-global/protocol-kit";
import {
  concat, createPublicClient, createTestClient, createWalletClient, decodeEventLog, encodeAbiParameters,
  encodeFunctionData, getAddress, hashTypedData, http, keccak256, pad, parseAbi, size, toHex,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { baseSepolia } from "viem/chains";

const arg = (k, d) => (process.argv.includes(k) ? process.argv[process.argv.indexOf(k) + 1] : d);
const RPC = arg("--rpc", "http://127.0.0.1:8547");
const FIXTURE = process.argv.includes("--fixture");

const SAFE_L2_150 = "0xEdd160fEBBD92E350D4D398fb636302fccd67C7e";
const PROXY_FACTORY_150 = "0x14F2982D601c9458F93bd70B218933A6f8165e7b";
const FALLBACK_HANDLER_150 = "0x3EfCBb83A4A7AfcB4F68D501E2c2203a38be77f4";
const PASSKEY_FACTORY = "0x1d31F259eE307358a26dFb23EB365939E8641195";
const VERIFIERS = 0x0100c2b78104907f722dabac4c69f826a522b2754de4n;   // P-256 precompile, then the Daimo verifier
const ZERO = "0x0000000000000000000000000000000000000000";

const safeAbi = parseAbi([
  "function setup(address[] _owners, uint256 _threshold, address to, bytes data, address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)",
  "function execTransaction(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, bytes signatures) payable returns (bool)",
  "event ExecutionSuccess(bytes32 indexed txHash, uint256 payment)",
  "event SafeMultiSigTransaction(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, bytes signatures, bytes additionalInfo)",
]);
const factoryAbi = parseAbi(["function createProxyWithNonce(address _singleton, bytes initializer, uint256 saltNonce) returns (address)"]);
const passkeyAbi = parseAbi([
  "function createSigner(uint256 x, uint256 y, uint176 verifiers) returns (address)",
  "function getSigner(uint256 x, uint256 y, uint176 verifiers) view returns (address)",
]);

const chain = { ...baseSepolia, rpcUrls: { default: { http: [RPC] } } };
const pub = createPublicClient({ chain, transport: http(RPC) });
const test = createTestClient({ chain, mode: "anvil", transport: http(RPC) });
const wallet = createWalletClient({ chain, transport: http(RPC) });
const sha = (b) => createHash("sha256").update(b).digest();

// A throwaway account that pays for the setup on the fork.
const payer = privateKeyToAccount(keccak256(toHex("gs021 repro: payer")));
await test.setBalance({ address: payer.address, value: 10n ** 20n });
async function send(address, abi, functionName, args) {
  const hash = await wallet.writeContract({ account: payer, address, abi, functionName, args });
  const r = await pub.waitForTransactionReceipt({ hash });
  if (r.status !== "success") throw new Error(`${functionName} reverted`);
  return r;
}
const why = (e) => e.walk?.((x) => x.reason)?.reason || e.shortMessage;

// --- owners: an EOA, and passkey signers (SafeWebAuthnSignerProxy) for throwaway P-256 keys
const eoa = privateKeyToAccount(keccak256(toHex("gs021 repro: throwaway EOA")));
async function passkey(seed) {
  const sk = sha(`gs021 repro: throwaway P-256 key ${seed}`);
  const pk = p256.getPublicKey(sk, false);
  const x = BigInt(toHex(pk.slice(1, 33))), y = BigInt(toHex(pk.slice(33)));
  const owner = await pub.readContract({ address: PASSKEY_FACTORY, abi: passkeyAbi, functionName: "getSigner", args: [x, y, VERIFIERS] });
  return { sk, x, y, owner: getAddress(owner) };
}
// Passkeys whose addresses sort before and after the EOA, so both orders are covered.
const keys = [];
for (let i = 0; keys.length < 64 && (!keys.some((k) => BigInt(k.owner) < BigInt(eoa.address)) || keys.filter((k) => BigInt(k.owner) > BigInt(eoa.address)).length < 1); i++) keys.push(await passkey(i));
const before = keys.find((k) => BigInt(k.owner) < BigInt(eoa.address));
const after = keys.find((k) => BigInt(k.owner) > BigInt(eoa.address));
for (const k of [before, after]) await send(PASSKEY_FACTORY, passkeyAbi, "createSigner", [k.x, k.y, VERIFIERS]);

// --- confirmations in the form the Transaction Service returns them
async function eoaConfirmation(safeTxHash) {
  return { owner: eoa.address, signature: await eoa.sign({ hash: safeTxHash }) };          // 65 bytes, v = 27/28
}
function passkeyConfirmation(k, safeTxHash) {
  // A WebAuthn assertion whose challenge is the safeTxHash, as SafeWebAuthnSignerProxy checks it.
  const authenticatorData = Buffer.concat([sha("gs021.example"), Buffer.from([0x05]), Buffer.alloc(4)]);  // rpIdHash, UP|UV, counter
  const clientDataFields = '"origin":"https://gs021.example"';
  const clientDataJSON = `{"type":"webauthn.get","challenge":"${Buffer.from(safeTxHash.slice(2), "hex").toString("base64url")}",${clientDataFields}}`;
  const digest = sha(Buffer.concat([authenticatorData, sha(clientDataJSON)]));
  const sig = p256.sign(digest, k.sk, { prehash: false, lowS: true });
  const data = encodeAbiParameters([{ type: "bytes" }, { type: "string" }, { type: "uint256" }, { type: "uint256" }],
    [toHex(authenticatorData), clientDataFields, sig.r, sig.s]);
  // {owner}{offset = 65}{00}{length}{data}: a single contract signature, as it is stored.
  return { owner: k.owner, signature: concat([pad(k.owner, { size: 32 }), toHex(65n, { size: 32 }), "0x00", toHex(BigInt(size(data)), { size: 32 }), data]) };
}

// --- the two ways to rebuild them
function current(confirmations) {           // apps/web createExistingTx today
  return buildSignatureBytes(confirmations.map(({ owner, signature }) => ({
    signer: owner, data: signature, staticPart: () => signature, dynamicPart: () => "", isContractSignature: false,
  })));
}
function toSafeSignature(signer, signature) {   // the PR's helper
  const hex = signature.startsWith("0x") ? signature.slice(2) : signature;
  if (hex.length > 130 && hex.slice(128, 130) === "00") {
    const offset = Number.parseInt(hex.slice(64, 128), 16) * 2;
    const length = Number.parseInt(hex.slice(offset, offset + 64), 16) * 2;
    if (Number.isSafeInteger(offset) && offset >= 130 && Number.isSafeInteger(length) && offset + 64 + length === hex.length) {
      return new EthSafeSignature(signer, `0x${hex.slice(offset + 64)}`, true);
    }
  }
  return new EthSafeSignature(signer, signature);
}
const fixed = (confirmations) => buildSignatureBytes(confirmations.map(({ owner, signature }) => toSafeSignature(owner, signature)));

// --- one Safe, one transaction, both layouts
async function scenario(name, owners, threshold, confirm) {
  const init = encodeFunctionData({ abi: safeAbi, functionName: "setup", args: [owners.map((o) => o.owner ?? o.address), BigInt(threshold), ZERO, "0x", FALLBACK_HANDLER_150, ZERO, 0n, ZERO] });
  const salt = BigInt(keccak256(toHex(name)));
  const { result: safe } = await pub.simulateContract({ account: payer, address: PROXY_FACTORY_150, abi: factoryAbi, functionName: "createProxyWithNonce", args: [SAFE_L2_150, init, salt] });
  await send(PROXY_FACTORY_150, factoryAbi, "createProxyWithNonce", [SAFE_L2_150, init, salt]);
  await test.setBalance({ address: safe, value: 10n ** 16n });
  const recipient = getAddress(keccak256(toHex(`gs021 repro: recipient ${name}`)).slice(0, 42));
  const tx = { to: recipient, value: 10n ** 12n, data: "0x", operation: 0, safeTxGas: 0n, baseGas: 0n, gasPrice: 0n, gasToken: ZERO, refundReceiver: ZERO, nonce: 0n };
  const safeTxHash = hashTypedData({ domain: { chainId: chain.id, verifyingContract: safe }, primaryType: "SafeTx", message: tx, types: {
    SafeTx: [{ name: "to", type: "address" }, { name: "value", type: "uint256" }, { name: "data", type: "bytes" }, { name: "operation", type: "uint8" },
             { name: "safeTxGas", type: "uint256" }, { name: "baseGas", type: "uint256" }, { name: "gasPrice", type: "uint256" },
             { name: "gasToken", type: "address" }, { name: "refundReceiver", type: "address" }, { name: "nonce", type: "uint256" }] } });
  const confirmations = [];
  for (const o of confirm) confirmations.push(o === eoa ? await eoaConfirmation(safeTxHash) : passkeyConfirmation(o, safeTxHash));
  const args = (sigs) => [tx.to, tx.value, tx.data, tx.operation, tx.safeTxGas, tx.baseGas, tx.gasPrice, tx.gasToken, tx.refundReceiver, sigs];
  const order = [...confirmations].sort((a, b) => (BigInt(a.owner) < BigInt(b.owner) ? -1 : 1)).map((c) => (c.owner === eoa.address ? "EOA" : "contract")).join(", ");
  console.log(`\n${name}: Safe 1.5.0, ${threshold}-of-${owners.length}; confirmations sorted by owner: ${order}`);

  const out = { name, threshold, safeTxHash, confirmations };
  for (const [label, build] of [["current (createExistingTx)", current], ["fixed (toSafeSignature)", fixed]]) {
    const sigs = build(confirmations);
    try {
      await pub.simulateContract({ account: payer, address: safe, abi: safeAbi, functionName: "execTransaction", args: args(sigs) });
      console.log(`  ${label.padEnd(26)} ${size(sigs)} bytes -> simulation OK`);
      out[label.split(" ")[0]] = { bytes: sigs, simulation: "ok" };
    } catch (e) {
      console.log(`  ${label.padEnd(26)} ${size(sigs)} bytes -> reverts ${why(e)}`);
      out[label.split(" ")[0]] = { bytes: sigs, simulation: why(e) };
    }
  }
  // Execute the fixed layout: ExecutionSuccess, the recipient's balance, and the bytes the Safe logged.
  const balance0 = await pub.getBalance({ address: recipient });
  const r = await send(safe, safeAbi, "execTransaction", args(out.fixed.bytes));
  let success = false, logged = null;
  for (const l of r.logs.filter((l) => getAddress(l.address) === getAddress(safe))) {
    try {
      const ev = decodeEventLog({ abi: safeAbi, data: l.data, topics: l.topics });
      if (ev.eventName === "ExecutionSuccess") success = true;
      if (ev.eventName === "SafeMultiSigTransaction") logged = ev.args.signatures;
    } catch {}
  }
  const delta = (await pub.getBalance({ address: recipient })) - balance0;
  console.log(`  executed with the fixed layout: ExecutionSuccess ${success}, recipient +${delta} wei, logged signatures = fixed: ${logged?.toLowerCase() === out.fixed.bytes.toLowerCase()}`);
  out.executed = { success, delta: delta.toString(), logged };
  return out;
}

console.log(`fork of Base Sepolia at ${RPC}, block ${await pub.getBlockNumber()}`);
const results = [
  await scenario("2-of-2 EOA + passkey", [eoa, after], 2, [eoa, after]),
  await scenario("3-of-3 passkey + EOA + passkey", [before, eoa, after], 3, [before, eoa, after]),
  await scenario("1-of-2 control", [before, eoa], 1, [before, eoa]),
];
if (FIXTURE) console.log("\nFIXTURE " + JSON.stringify(results.map((r) => ({ name: r.name, threshold: r.threshold, confirmations: r.confirmations, executed: r.executed.logged }))));
```

</details>

## Expected result

The transaction simulates and executes, as it does when the contract confirmation is added to the `SafeTransaction` as a contract signature. protocol-kit already supports that.

## Obtained result

GS021: simulation fails, the fee can't be estimated, and submitting fails.

Why, from reading the code (not verified beyond the reproduction above):
- [`createExistingTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/web/src/services/tx/tx-sender/create.ts#L131-L141) adds every stored confirmation like this:

  ```ts
  safeTx.addSignature({ signer, data, staticPart: () => data, dynamicPart: () => '', isContractSignature: false })
  ```

- A contract owner's confirmation is stored standalone as `{owner}{offset = 65}{00}{length}{data}`. As a plain signature, `buildSignatureBytes` concatenates it whole and the offset stays 65.
- [`checkNSignatures`](https://github.com/safe-global/safe-smart-account/blob/v1.5.0/contracts/Safe.sol#L306-L316) checks the first `threshold` signatures and requires a contract signature's offset to be at least `threshold * 65`. With a threshold of 2 that is 130, so offset 65 reverts with GS021.

Mobile has the same plain-signature construction in [`addSignaturesToTx`](https://github.com/safe-global/safe-wallet-monorepo/blob/5717e3a/apps/mobile/src/services/tx/tx-sender/create.ts#L40-L50). I haven't tested the mobile app.

A fix could rebuild stored confirmations as `EthSafeSignature`, and for `v = 0` add only the data after the length word with `isContractSignature: true`, so `buildSignatureBytes` computes the offsets. I have a patch with unit tests and can open a PR.

## Related

- #3673: the same symptom with a nested Safe as the contract owner. I haven't reproduced the nested-Safe case.

## Screenshots

<!-- attach the redacted screenshots -->
