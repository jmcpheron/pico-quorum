// A new Safe for a new key (docs/ONBOARDING.md, The QR code): one transaction from the wallet that
// scanned the console's code. The Safe is a SafeL2 1.4.1, the version the app and the console use,
// with two owners, that wallet and the key's signer, and threshold 2. Its setup runs one batch:
//   1. the key's signer, createSigner(x, y, verifiers), so the console's signatures count at once
//   2. Candide's Social Recovery Module, the 7-day deployment, enabled on the Safe
//   3. that wallet as its one guardian: lose the console, and the wallet alone can take the Safe
//      back after 7 days. Both owners together can cancel it until then.
// The batch goes through MultiSendCallOnly 1.5.0, whose `to = 0` means the Safe itself: the Safe's
// address isn't known while its own setup is being written. Every contract here is deployed and
// audited, at the same address on each chain the app knows (eth_getCode checked 2026-11-03). Nothing
// here signs: the wallet shows the transaction and sends it.
import { concat, encodeFunctionData, encodePacked, getAddress, getContractAddress, keccak256, pad, parseAbi, size } from "viem";
import { CFG, SAFE_ABI, SIGNER_ABI } from "./safe.mjs";

export const NEW_SAFE = {
  singleton: "0x29fcB43b46531BcA003ddC8FCB67FFE91900C762",       // SafeL2 1.4.1
  factory: "0x4e1DCf7AD4e460CfD30791CCC4F9c8a4f820ec67",         // SafeProxyFactory 1.4.1
  fallbackHandler: "0xfd0732Dc9E303f09fCEf3a7388Ad10A83459Ec99", // CompatibilityFallbackHandler 1.4.1
  setupBatch: "0xA83c336B20401Af773B6219BA5027174338D1836",      // MultiSendCallOnly 1.5.0
  recovery: "0x088f6cfD8BB1dDb1BB069CCb3fc1A98927D233f2",        // Candide SocialRecoveryModule, 7 days
  days: 7,
  saltNonce: 0n,              // one Safe per (wallet, key, guardian): the same three find the same address again
};

export const FACTORY_ABI = parseAbi([
  "function createProxyWithNonce(address singleton, bytes initializer, uint256 saltNonce) returns (address)",
  "function proxyCreationCode() pure returns (bytes)",
]);
export const SETUP_ABI = parseAbi([
  "function setup(address[] owners, uint256 threshold, address to, bytes data, address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)",
  "function enableModule(address module)",
  "function isModuleEnabled(address module) view returns (bool)",
]);
export const RECOVERY_ABI = parseAbi([
  "function addGuardianWithThreshold(address guardian, uint256 threshold)",
  "function getGuardians(address wallet) view returns (address[])",
  "function threshold(address wallet) view returns (uint256)",
]);
const MULTISEND_ABI = parseAbi(["function multiSend(bytes transactions) payable"]);
const ZERO = "0x0000000000000000000000000000000000000000";

// The setup's batch: each a CALL (operation 0) from the Safe. to = 0 is the Safe (MultiSendCallOnly 1.5.0).
export function setupCalls(guardian, qx, qy) {
  return [
    { to: CFG.signer.factory, data: encodeFunctionData({ abi: SIGNER_ABI, functionName: "createSigner", args: [qx, qy, BigInt(CFG.signer.verifiers)] }) },
    { to: ZERO, data: encodeFunctionData({ abi: SETUP_ABI, functionName: "enableModule", args: [NEW_SAFE.recovery] }) },
    { to: NEW_SAFE.recovery, data: encodeFunctionData({ abi: RECOVERY_ABI, functionName: "addGuardianWithThreshold", args: [guardian, 1n] }) },
  ];
}

export function initializer(wallet, owner, guardian, qx, qy) {
  const packed = concat(setupCalls(guardian, qx, qy).map((c) => encodePacked(["uint8", "address", "uint256", "uint256", "bytes"], [0, c.to, 0n, BigInt(size(c.data)), c.data])));
  return encodeFunctionData({ abi: SETUP_ABI, functionName: "setup",
    args: [[getAddress(wallet), getAddress(owner)], 2n, NEW_SAFE.setupBatch, encodeFunctionData({ abi: MULTISEND_ABI, functionName: "multiSend", args: [packed] }),
      NEW_SAFE.fallbackHandler, ZERO, 0n, ZERO] });
}

// The transaction the wallet sends: anyone could send it, but the owners and guardian are written in it.
export function createCall(wallet, owner, guardian, qx, qy) {
  return { to: NEW_SAFE.factory, data: encodeFunctionData({ abi: FACTORY_ABI, functionName: "createProxyWithNonce",
    args: [NEW_SAFE.singleton, initializer(wallet, owner, guardian, qx, qy), NEW_SAFE.saltNonce] }) };
}

// Where it will be: CREATE2 from the factory, the factory's own proxy code read from the chain.
export async function predict(pub, wallet, owner, guardian, qx, qy) {
  const code = await pub.readContract({ address: NEW_SAFE.factory, abi: FACTORY_ABI, functionName: "proxyCreationCode" });
  const salt = keccak256(encodePacked(["bytes32", "uint256"], [keccak256(initializer(wallet, owner, guardian, qx, qy)), NEW_SAFE.saltNonce]));
  return getContractAddress({ opcode: "CREATE2", from: NEW_SAFE.factory, salt, bytecode: concat([code, pad(NEW_SAFE.singleton, { size: 32 })]) });
}

// What the chain says the new Safe is, each line a check: [ok, what].
export async function checkNew(pub, safe, wallet, owner, guardian) {
  const [owners, threshold, on, guardians, gt, signer] = await Promise.all([
    pub.readContract({ address: safe, abi: SAFE_ABI, functionName: "getOwners" }),
    pub.readContract({ address: safe, abi: SAFE_ABI, functionName: "getThreshold" }),
    pub.readContract({ address: safe, abi: SETUP_ABI, functionName: "isModuleEnabled", args: [NEW_SAFE.recovery] }),
    pub.readContract({ address: NEW_SAFE.recovery, abi: RECOVERY_ABI, functionName: "getGuardians", args: [safe] }),
    pub.readContract({ address: NEW_SAFE.recovery, abi: RECOVERY_ABI, functionName: "threshold", args: [safe] }),
    pub.getCode({ address: owner }),
  ]);
  const same = (a, b) => a.length === b.length && a.every((x, i) => getAddress(x) === getAddress(b[i]));
  return [
    [same(owners.map((a) => getAddress(a)).sort(), [wallet, owner].map((a) => getAddress(a)).sort()), "Owners: your wallet and this key, no one else"],
    [threshold === 2n, "2 of 2: every transaction needs both"],
    [!!signer && signer !== "0x", "This key's signer is deployed"],
    [on && same(guardians, [guardian]) && gt === 1n, `Recovery is on (Candide, ${NEW_SAFE.days} days), with the recovery address as its only guardian`],
  ];
}
