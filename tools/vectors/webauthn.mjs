// Writes test-vectors/webauthn.json: how firmware/webauthn.py must pack a chip signature for the
// Safe, with every expected value made here by other code (node:crypto for SHA-256, viem for ABI,
// CREATE2 and keccak, noble for P-256). Then each vector is put to the real contracts on Base
// Sepolia over its public RPC, read only, nothing deployed:
//   - the owner address must equal the passkey factory's getSigner(x, y, verifiers)
//   - the packed signature must pass isValidSignatureForSigner(safeTxHash, ...), the check the
//     Safe makes through the owner's proxy at execution time
// Nothing is written unless the chain agrees with every vector.
//
// --chain base|eth puts the same vectors to that chain's deployment instead, and writes nothing:
// a check that the passkey signer there gives this key the same owner and accepts its signatures
// (before a Safe on that chain is trusted to the console; docs/LADDER.md). It also asks the P-256
// precompile at 0x100 directly, since the verifiers fall back to Daimo's contract without it.
//
//   cd tools/vectors && npm install && node webauthn.mjs [--chain base|eth]
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { p256 } from "@noble/curves/p256";
import {
  concat, createPublicClient, encodeAbiParameters, getContractAddress, http, pad, parseAbi, size, toHex,
} from "viem";
import { base, baseSepolia, mainnet } from "viem/chains";

const ROOT = new URL("../../", import.meta.url);
const src = readFileSync(new URL("firmware/quorum_cfg.py", ROOT), "utf8");
const SIGNER = JSON.parse(src.slice(src.indexOf("{", src.indexOf("CFG =")))).signer;
const CHAINS = {
  basesep: [baseSepolia, process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org"],
  base: [base, process.env.BASE_RPC || "https://mainnet.base.org"],
  eth: [mainnet, process.env.ETH_RPC || "https://ethereum-rpc.publicnode.com"],
};
const argv = process.argv.slice(2);
const NET = argv.includes("--chain") ? argv[argv.indexOf("--chain") + 1] : "basesep";
if (!CHAINS[NET]) throw new Error(`--chain ${NET}: one of ${Object.keys(CHAINS).join(", ")}`);
const [CHAIN, RPC] = CHAINS[NET];

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

const client = createPublicClient({ chain: CHAIN, transport: http(RPC) });
let bad = 0;
{
  // the precompile itself (RIP-7212 on the L2s, EIP-7951 on Ethereum): 1 for a good signature
  const k = p256.utils.randomPrivateKey();
  const pub = p256.getPublicKey(k, false);
  const msg = sha256(Buffer.from("picoquorum precompile check"));
  const sg = p256.sign(msg, k, { prehash: false });
  const input = concat([hex(msg), pad(toHex(sg.r)), pad(toHex(sg.s)), hex(pub.slice(1, 33)), hex(pub.slice(33))]);
  const { data } = await client.call({ to: "0x0000000000000000000000000000000000000100", data: input });
  console.log(`${data && BigInt(data) === 1n ? "pass" : "note"}  P-256 precompile at 0x100 on ${CHAIN.name}: ${data && BigInt(data) === 1n ? "live" : "absent (Daimo's verifier is used, about 4x the gas)"}`);
}
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
  console.error(`${bad} vector(s) disagree with the deployed contracts on ${CHAIN.name}; nothing written`);
  process.exit(1);
}
if (NET !== "basesep") {
  console.log(`all ${vectors.length} vectors agree with the passkey signer on ${CHAIN.name} (chain ${CHAIN.id}); nothing written`);
  process.exit(0);
}
const out = new URL("test-vectors/webauthn.json", ROOT);
writeFileSync(out, JSON.stringify({
  about: "Made by tools/vectors/webauthn.mjs; each vector checked against the passkey factory on Base Sepolia (getSigner, isValidSignatureForSigner). Do not edit by hand.",
  signer: { factory: SIGNER.factory, singleton: SIGNER.singleton, verifiers: SIGNER.verifiers },
  vectors,
}, null, 2) + "\n");
console.log(`wrote ${vectors.length} vectors to test-vectors/webauthn.json`);
