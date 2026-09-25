// Writes test-vectors/webauthn.json: how firmware/webauthn.py must pack a chip signature for the
// Safe, with every expected value made here by other code (node:crypto for SHA-256, viem for ABI,
// CREATE2 and keccak, noble for P-256). Then each vector is put to the real contracts on Base
// Sepolia over its public RPC, read only, nothing deployed:
//   - the owner address must equal the passkey factory's getSigner(x, y, verifiers)
//   - the packed signature must pass isValidSignatureForSigner(safeTxHash, ...), the check the
//     Safe makes through the owner's proxy at execution time
// Nothing is written unless the chain agrees with every vector.
//
//   cd tools/vectors && npm install && node webauthn.mjs
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { p256 } from "@noble/curves/p256";
import {
  concat, createPublicClient, encodeAbiParameters, getContractAddress, http, pad, parseAbi, size, toHex,
} from "viem";
import { baseSepolia } from "viem/chains";

const ROOT = new URL("../../", import.meta.url);
const src = readFileSync(new URL("firmware/quorum_cfg.py", ROOT), "utf8");
const SIGNER = JSON.parse(src.slice(src.indexOf("{", src.indexOf("CFG =")))).signer;
const RPC = process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org";

const sha256 = (b) => createHash("sha256").update(b).digest();
const hex = (b) => "0x" + Buffer.from(b).toString("hex");
const b64url = (b) => Buffer.from(b).toString("base64url");

// What the console claims to be: see firmware/webauthn.py. Written out again here on purpose.
const RP_ID = "picoquorum";
const FLAGS = 0x05;
const FIELDS = '"origin":"picoquorum"';

const factoryAbi = parseAbi([
  "function getSigner(uint256 x, uint256 y, uint176 verifiers) view returns (address)",
  "function isValidSignatureForSigner(bytes32 message, bytes signature, uint256 x, uint256 y, uint176 verifiers) view returns (bytes4)",
]);

function owner(qx, qy) {
  const args = encodeAbiParameters([{ type: "address" }, { type: "uint256" }, { type: "uint256" }, { type: "uint176" }],
    [SIGNER.singleton, BigInt(qx), BigInt(qy), BigInt(SIGNER.verifiers)]);
  return getContractAddress({ opcode: "CREATE2", from: SIGNER.factory, salt: pad("0x00", { size: 32 }),
                              bytecode: concat(["0x" + SIGNER.proxyCode, args]) }).toLowerCase();
}

function vector(name, keySeed, safeTxHash) {
  const sk = sha256(Buffer.from("picoquorum webauthn vector key " + keySeed));
  const pub = p256.getPublicKey(sk, false);
  const qx = hex(pub.slice(1, 33)), qy = hex(pub.slice(33));
  const authenticatorData = Buffer.concat([sha256(Buffer.from(RP_ID)), Buffer.from([FLAGS]), Buffer.alloc(4)]);
  const clientDataJSON = `{"type":"webauthn.get","challenge":"${b64url(Buffer.from(safeTxHash.slice(2), "hex"))}",${FIELDS}}`;
  const digest = sha256(Buffer.concat([authenticatorData, sha256(Buffer.from(clientDataJSON))]));
  const sig = p256.sign(digest, sk, { prehash: false, lowS: true });
  const signature = encodeAbiParameters(
    [{ type: "bytes" }, { type: "string" }, { type: "uint256" }, { type: "uint256" }],
    [hex(authenticatorData), FIELDS, sig.r, sig.s]);
  const who = owner(qx, qy);
  const contractSignature = concat([pad(who, { size: 32 }), toHex(65n, { size: 32 }), "0x00",
                                    toHex(BigInt(size(signature)), { size: 32 }), signature]);
  return {
    name, qx, qy, owner: who, safeTxHash,
    authenticatorData: hex(authenticatorData), clientDataFields: FIELDS, clientDataJSON, digest: hex(digest),
    r: toHex(sig.r, { size: 32 }), s: toHex(sig.s, { size: 32 }), signature, contractSignature,
  };
}

// Challenges: safeTxHashes from test-vectors/safe_tx.json, plus two edge values whose base64url
// uses - and _ (0xfb.. / 0xff..) and one of all zeros.
const safeVectors = JSON.parse(readFileSync(new URL("test-vectors/safe_tx.json", ROOT), "utf8")).vectors;
const vectors = [
  vector("eth-send-base", 1, safeVectors.find((v) => v.name === "eth-send-base").safeTxHash),
  vector("erc20-transfer", 2, safeVectors.find((v) => v.name === "erc20-transfer").safeTxHash),
  vector("b64url-dash-underscore", 3, "0x" + "fbff".repeat(16)),
  vector("zero-hash", 4, "0x" + "00".repeat(32)),
];

const client = createPublicClient({ chain: baseSepolia, transport: http(RPC) });
let bad = 0;
for (const v of vectors) {
  const onchain = (await client.readContract({ address: SIGNER.factory, abi: factoryAbi, functionName: "getSigner",
    args: [BigInt(v.qx), BigInt(v.qy), BigInt(SIGNER.verifiers)] })).toLowerCase();
  const magic = await client.readContract({ address: SIGNER.factory, abi: factoryAbi, functionName: "isValidSignatureForSigner",
    args: [v.safeTxHash, v.signature, BigInt(v.qx), BigInt(v.qy), BigInt(SIGNER.verifiers)] });
  const ok = onchain === v.owner && magic === "0x1626ba7e";
  bad += !ok;
  console.log(`${ok ? "pass" : "FAIL"}  ${v.name.padEnd(24)} owner ${v.owner}${onchain === v.owner ? "" : " != chain " + onchain}  isValidSignature ${magic}`);
}
if (bad) {
  console.error(`${bad} vector(s) disagree with the deployed contracts on Base Sepolia; nothing written`);
  process.exit(1);
}
const out = new URL("test-vectors/webauthn.json", ROOT);
writeFileSync(out, JSON.stringify({
  about: "Made by tools/vectors/webauthn.mjs; each vector checked against the passkey factory on Base Sepolia (getSigner, isValidSignatureForSigner). Do not edit by hand.",
  signer: { factory: SIGNER.factory, singleton: SIGNER.singleton, verifiers: SIGNER.verifiers },
  vectors,
}, null, 2) + "\n");
console.log(`wrote ${vectors.length} vectors to test-vectors/webauthn.json`);
