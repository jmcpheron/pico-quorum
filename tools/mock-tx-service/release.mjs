// A PicoQuorum release as the project Safe approves it: the digest D (firmware/release.py builds the
// same), the one Safe transaction that approves it, and how anyone checks the approval. Shared by
// tools/quorum, tools/release, tools/vectors and the app (web/src/main.mjs bundles it).
//
//   D = EIP-712 PicoQuorumRelease(string version, bytes32 firmware, bytes32 manifest)
//       domain {name: "PicoQuorum Release", version: "1"}
//   firmware: the console image's release fingerprint; manifest: sha256 of docs/releases/<version>.json
//
// The approval is a delegatecall from the Safe to Safe's SignMessageLib 1.4.1, signMessage(abi.encode(D)),
// which sets signedMessages[M] = 1 for good, M being the Safe's own message hash of D (its chain and
// address in the domain). It stays valid after owners change. Anyone checks it with one read:
// Safe.isValidSignature(D, "0x") == 0x1626ba7e (CompatibilityFallbackHandler), or signedMessages(M).
// The transaction's origin note names the release in short keys, since Safe's service keeps 200
// characters; the console recomputes D from it and refuses any mismatch.
import { concat, encodeAbiParameters, encodeFunctionData, hashTypedData, keccak256, parseAbi, toHex } from "viem";

export const SIGN_MESSAGE_LIB = "0xd53cd0aB83D845Ac265BE939c57F53AD838012c9";     // 1.4.1, the same on Ethereum, Base, Base Sepolia
export const COMPAT_HANDLER_141 = "0xfd0732Dc9E303f09fCEf3a7388Ad10A83459Ec99";
export const RELEASE_DOMAIN = { name: "PicoQuorum Release", version: "1" };
export const RELEASE_TYPES = {
  PicoQuorumRelease: [{ name: "version", type: "string" }, { name: "firmware", type: "bytes32" }, { name: "manifest", type: "bytes32" }],
};
export const RELEASE_ABI = parseAbi([
  "function signMessage(bytes _data)",
  "function isValidSignature(bytes32 _dataHash, bytes _signature) view returns (bytes4)",
  "function signedMessages(bytes32) view returns (uint256)",
  "function getMessageHashForSafe(address safe, bytes message) view returns (bytes32)",
]);
const SAFE_MSG_TYPEHASH = keccak256(toHex("SafeMessage(bytes message)"));
const DOMAIN_TYPEHASH = keccak256(toHex("EIP712Domain(uint256 chainId,address verifyingContract)"));
const hex32 = (h) => { const x = String(h).toLowerCase(); const v = x.startsWith("0x") ? x : "0x" + x; if (!/^0x[0-9a-f]{64}$/.test(v)) throw new Error(`not 32 bytes: ${h}`); return v; };

export function releaseDigest({ version, firmware, manifest }) {
  if (!/^\d{4}\.\d+\.\d+$/.test(version)) throw new Error(`version ${version}: year.month.n`);
  return hashTypedData({ domain: RELEASE_DOMAIN, types: RELEASE_TYPES, primaryType: "PicoQuorumRelease",
    message: { version, firmware: hex32(firmware), manifest: hex32(manifest) } });
}

/** The Safe's own hash of D (what SignMessageLib marks): its chain and address are in the domain. */
export function safeMessageHash(chainId, safe, digest) {
  const sep = keccak256(encodeAbiParameters([{ type: "bytes32" }, { type: "uint256" }, { type: "address" }], [DOMAIN_TYPEHASH, BigInt(chainId), safe]));
  const struct = keccak256(encodeAbiParameters([{ type: "bytes32" }, { type: "bytes32" }], [SAFE_MSG_TYPEHASH, keccak256(digest)]));
  return keccak256(concat(["0x1901", sep, struct]));
}

/** The origin note the console reads the release from. */
export const releaseOrigin = ({ version, firmware, manifest }) =>
  JSON.stringify({ pq: { v: version, f: hex32(firmware).slice(2), m: hex32(manifest).slice(2) } });

/** The Safe transaction that approves the release: to, value, data, operation, and its origin note. */
export function approvalTx(rel) {
  const digest = releaseDigest(rel);
  return { to: SIGN_MESSAGE_LIB, value: "0", operation: 1, digest, origin: releaseOrigin(rel),
    data: encodeFunctionData({ abi: RELEASE_ABI, functionName: "signMessage", args: [digest] }) };
}

/** The release an approval transaction names, checked the way the console checks it: "" if fine. */
export function checkApproval(t) {
  if (String(t.to).toLowerCase() !== SIGN_MESSAGE_LIB.toLowerCase() || Number(t.operation) !== 1) return "not a delegatecall to SignMessageLib";
  let o;
  try { o = typeof t.origin === "string" ? JSON.parse(t.origin) : t.origin; } catch { o = null; }
  const pq = o && o.pq;
  if (!pq || typeof pq.v !== "string") return "a message with no PicoQuorum release named for it";
  try {
    const want = approvalTx({ version: pq.v, firmware: pq.f, manifest: pq.m }).data.toLowerCase();
    return String(t.data).toLowerCase() === want && BigInt(t.value || 0) === 0n ? "" : "the release named doesn't match what the Safe would sign";
  } catch (e) { return `the release named can't be read (${e.message})`; }
}

/** Is this release approved by that Safe? One read: isValidSignature(D, "0x"), which reverts when not. */
export async function isApproved(client, safe, digest) {
  try {
    const r = await client.readContract({ address: safe, abi: RELEASE_ABI, functionName: "isValidSignature", args: [digest, "0x"] });
    return r === "0x1626ba7e";
  } catch { return false; }
}
