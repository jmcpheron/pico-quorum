// Writes test-vectors/release.json: what firmware/release.py and decode.py must compute for a
// PicoQuorum release approval, made here by viem (tools/mock-tx-service/release.mjs). Then put to a
// real Safe on Ethereum, read only, nothing deployed: Safe{DAO}'s treasury (its handler hashes Safe
// messages the same way as 1.4.1's):
//   - the handler's getMessageHashForSafe(safe, abi.encode(D)) must equal our M for that Safe
//   - isValidSignature(D, "0x") must fail as things are, and return 0x1626ba7e once signedMessages[M]
//     is set (an eth_call state override: exactly the slot SignMessageLib.signMessage(D) writes)
//   - SignMessageLib 1.4.1 must have the same code on Ethereum, Base and Base Sepolia
// Nothing is written unless the chain agrees.
//   cd tools/vectors && npm install && node release.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { createPublicClient, encodeAbiParameters, http, keccak256, pad, toHex } from "viem";
import { base, baseSepolia, mainnet } from "viem/chains";
import { SIGN_MESSAGE_LIB, RELEASE_ABI, approvalTx, checkApproval, releaseDigest, safeMessageHash } from "../mock-tx-service/release.mjs";
import { imageFingerprint } from "../releases/fingerprint.mjs";

const ROOT = new URL("../../", import.meta.url);
const SAFE = "0x8CF60B289f8d31F737049B590b5E4285Ff0Bd1D1";          // Safe{DAO} treasury, Ethereum
const eth = createPublicClient({ chain: mainnet, transport: http(process.env.ETH_RPC || "https://ethereum-rpc.publicnode.com") });

const cases = [
  ["this-checkout", { version: "2026.10.6", firmware: "0x" + imageFingerprint("console"), manifest: "0x" + "5f".repeat(32) }],
  ["first", { version: "2026.10.1", firmware: "0x" + "4c86c7541a45eb43f24c48c178409de889c5f86d467c886d444e9e30b9a00e0b", manifest: "0x" + "00".repeat(32) }],
  ["edges", { version: "2099.12.999", firmware: "0x" + "ff".repeat(32), manifest: "0x" + "01".repeat(32) }],
];
let bad = 0;
const vectors = [];
for (const [name, rel] of cases) {
  const tx = approvalTx(rel);
  const M = safeMessageHash(1, SAFE, tx.digest);
  const handlerM = await eth.readContract({ address: SAFE, abi: RELEASE_ABI, functionName: "getMessageHashForSafe", args: [SAFE, tx.digest] });
  const slot = keccak256(encodeAbiParameters([{ type: "bytes32" }, { type: "uint256" }], [M, 7n]));      // signedMessages: slot 7
  const ask = (override) => eth.readContract({ address: SAFE, abi: RELEASE_ABI, functionName: "isValidSignature", args: [tx.digest, "0x"],
    ...(override ? { stateOverride: [{ address: SAFE, stateDiff: [{ slot, value: pad(toHex(1)) }] }] } : {}) }).catch(() => "reverts");
  const [before, after] = [await ask(false), await ask(true)];
  const ok = handlerM === M && before === "reverts" && after === "0x1626ba7e" && checkApproval(tx) === "";
  bad += !ok;
  console.log(`${ok ? "pass" : "FAIL"}  ${name.padEnd(14)} D ${tx.digest.slice(0, 14)}…  M ${M === handlerM ? "= handler" : "!= handler " + handlerM}  unsigned ${before}, signed ${after}`);
  vectors.push({ name, ...rel, digest: tx.digest, to: SIGN_MESSAGE_LIB.toLowerCase(), operation: 1, data: tx.data, origin: tx.origin,
    safeMessageHash: { chainId: 1, safe: SAFE.toLowerCase(), hash: M } });
}
// the console refuses a digest the origin doesn't give; the generator agrees
const t = approvalTx(cases[0][1]);
const tampered = { ...t, origin: JSON.stringify({ pq: { ...JSON.parse(t.origin).pq, v: "2026.10.7" } }) };
bad += checkApproval(tampered) === "" ? 1 : 0;
const codes = await Promise.all([[mainnet, "https://ethereum-rpc.publicnode.com"], [base, "https://mainnet.base.org"], [baseSepolia, "https://sepolia.base.org"]]
  .map(([chain, rpc]) => createPublicClient({ chain, transport: http(rpc) }).getCode({ address: SIGN_MESSAGE_LIB })));
const same = codes.every((c) => c && c.length > 2 && c === codes[0]);
bad += !same;
console.log(`${same ? "pass" : "FAIL"}  SignMessageLib 1.4.1 at ${SIGN_MESSAGE_LIB}: ${same ? `the same ${(codes[0].length - 2) / 2} bytes on Ethereum, Base and Base Sepolia` : "differs or missing"}`);
if (bad) { console.log(`${bad} FAILED; nothing written`); process.exit(1); }
writeFileSync(new URL("test-vectors/release.json", ROOT), JSON.stringify({
  note: "PicoQuorum release approvals (firmware/release.py, decode.py): the digest, the approval transaction and its origin note, made by viem (tools/mock-tx-service/release.mjs) and checked against Safe{DAO}'s Safe on Ethereum by tools/vectors/release.mjs.",
  vectors,
}, null, 2) + "\n");
console.log("wrote test-vectors/release.json");
