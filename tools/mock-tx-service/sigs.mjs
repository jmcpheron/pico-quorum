// Owner signatures as the Safe sees them, shared by the simulated Safe (sim.mjs), the forked one
// (chain.mjs) and the live tool (live.mjs). Written against viem and noble, never the firmware, so
// a console signature that passes here was packed right by firmware/webauthn.py.
//
// A chip key owns the Safe through its SafeWebAuthnSignerProxy (quorum_cfg.py "signer"). Its
// confirmation is a contract signature (v = 0): the proxy's address, an offset, and the data the
// proxy checks, a WebAuthn assertion whose challenge is the safeTxHash:
//   r = owner, s = 65, v = 0, then uint256 length, then abi.encode(bytes authenticatorData,
//   string clientDataFields, uint256 r, uint256 s)
import { createHash } from "node:crypto";
import { p256 } from "@noble/curves/p256";
import {
  bytesToHex, concat, decodeAbiParameters, encodeAbiParameters, getAddress, getContractAddress, hexToBytes, pad,
  size, slice, toHex,
} from "viem";

const sha256 = (b) => createHash("sha256").update(b).digest();

// The proxy the passkey factory deploys for a key: CREATE2, salt 0, over its creation code and
// constructor arguments. firmware/webauthn.owner_address computes the same thing on the console.
export function p256Owner(signer, qx, qy) {
  const args = encodeAbiParameters([{ type: "address" }, { type: "uint256" }, { type: "uint256" }, { type: "uint176" }],
    [signer.singleton, BigInt(qx), BigInt(qy), BigInt(signer.verifiers)]);
  return getContractAddress({ opcode: "CREATE2", from: signer.factory, salt: pad("0x00", { size: 32 }),
                              bytecode: concat(["0x" + signer.proxyCode, args]) });
}

// One owner's confirmation, as posted to the service. -> {kind: "ecdsa"}, {kind: "approved"}, or {kind: "contract",
// owner, data, authenticatorData, clientDataFields, r, s}; throws on anything else.
export function parse(signature) {
  const n = size(signature);
  if (n === 65 && hexToBytes(signature)[64] >= 27) return { kind: "ecdsa" };      // 31/32: eth_sign
  if (n === 65 && hexToBytes(signature)[64] === 1) return { kind: "approved" };   // approveHash onchain
  if (n < 97 || hexToBytes(signature)[64] !== 0) throw new Error(`not an ECDSA (65 bytes) or contract (v = 0) signature, ${n} bytes`);
  const owner = getAddress(slice(signature, 12, 32));
  const offset = Number(BigInt(slice(signature, 32, 64)));
  if (offset !== 65) throw new Error(`a single contract signature's data starts at 65, not ${offset}`);
  const len = Number(BigInt(slice(signature, 65, 97)));
  if (97 + len !== n) throw new Error(`contract signature data is ${n - 97} bytes, its length says ${len}`);
  const data = slice(signature, 97);
  const [authenticatorData, clientDataFields, r, s] = decodeAbiParameters(
    [{ type: "bytes" }, { type: "string" }, { type: "uint256" }, { type: "uint256" }], data);
  return { kind: "contract", owner, data, authenticatorData, clientDataFields, r, s };
}

// What the proxy has the P-256 key sign for a challenge (the safeTxHash).
export function webauthnDigest(challenge, authenticatorData, clientDataFields) {
  const json = `{"type":"webauthn.get","challenge":"${Buffer.from(hexToBytes(challenge)).toString("base64url")}",${clientDataFields}}`;
  return sha256(Buffer.concat([Buffer.from(hexToBytes(authenticatorData)), sha256(Buffer.from(json))]));
}

// The proxy's check, off chain: the UV flag, then P-256 over the WebAuthn digest (any s, as the
// contract allows). Returns "" when valid, else why not.
export function checkWebAuthn(challenge, w, qx, qy) {
  const ad = hexToBytes(w.authenticatorData);
  if (ad.length < 37) return "authenticatorData is too short";
  if (!(ad[32] & 0x04)) return "authenticatorData lacks the user-verified flag the signer requires";
  const pub = "04" + BigInt(qx).toString(16).padStart(64, "0") + BigInt(qy).toString(16).padStart(64, "0");
  const ok = p256.verify(new p256.Signature(w.r, w.s), webauthnDigest(challenge, w.authenticatorData, w.clientDataFields),
                         pub, { prehash: false, lowS: false });
  return ok ? "" : "the P-256 signature does not verify";
}

// s above n/2. The Safe's signer allows it (verifySignatureAllowMalleability); the console never makes one.
export const highS = (s) => BigInt(s) > p256.CURVE.n / 2n;

// Every confirmation laid out for execTransaction: sorted by owner, each a 65-byte slot, contract
// signatures pointing past the slots at their data. confirmations: [{owner, signature}].
export function packSignatures(confirmations) {
  const sorted = [...confirmations].sort((a, b) => (BigInt(a.owner) < BigInt(b.owner) ? -1 : 1));
  const statics = [];
  const dynamics = [];
  let offset = 65 * sorted.length;
  for (const c of sorted) {
    const p = parse(c.signature);
    if (p.kind === "ecdsa") {
      statics.push(c.signature);
      continue;
    }
    statics.push(concat([pad(p.owner, { size: 32 }), toHex(BigInt(offset), { size: 32 }), "0x00"]));
    const d = concat([toHex(BigInt(size(p.data)), { size: 32 }), p.data]);
    dynamics.push(d);
    offset += size(d);
  }
  return concat([...statics, ...dynamics]);
}

// A contract signature from a software P-256 key: for tests and simulated consoles only. The real
// console packs its own (firmware/webauthn.py) and tests check that one.
export function softContractSignature(sk, owner, challenge) {
  const authenticatorData = bytesToHex(Buffer.concat([sha256(Buffer.from("picoquorum")), Buffer.from([5]), Buffer.alloc(4)]));
  const clientDataFields = '"origin":"picoquorum"';
  const sig = p256.sign(webauthnDigest(challenge, authenticatorData, clientDataFields), sk, { prehash: false, lowS: true });
  const data = encodeAbiParameters([{ type: "bytes" }, { type: "string" }, { type: "uint256" }, { type: "uint256" }],
    [authenticatorData, clientDataFields, sig.r, sig.s]);
  return concat([pad(owner, { size: 32 }), toHex(65n, { size: 32 }), "0x00", toHex(BigInt(size(data)), { size: 32 }), data]);
}
