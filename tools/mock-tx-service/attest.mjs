// tools/quorum verify BUNDLE [--chain basesep,base,eth] [--safe CHAIN:0x..[,CHAIN:0x..]]
//
// A Trust M signer's ceremony record (tools/fw attest writes it; docs/mainnet/attest/ keeps them),
// checked by anyone, with no board and none of the firmware: Node's own X.509, noble's P-256 and
// viem. Every value is recomputed from the chip's raw bytes in the bundle:
//   1. the factory certificate (E0E0) is signed by Infineon's CA, pinned here by its public key
//   2. the binding (F1D1): the certificate's key (E0F0) signed this UID + E0F1 + this public key
//   3. the record (F1D0) names this chip and that key, and the owner address follows from the key
//      through Safe's passkey signer (factory, singleton and verifiers from firmware/quorum_cfg.py)
//   2b. live: the factory key signed a fresh challenge from the laptop when the record was made, so
//      the chip still held its certificate's key then (a stored binding outlives a swapped E0F0)
//   4. the lifecycle the chip reported: key, record and binding sealed; the spares frozen or not;
//      Infineon's factory key and certificate with their rules as they came (Change NEV): TM2
//      showed both can be rewritten, and E0F0 replaced, while their LcsO is below operational
//   5. on each chain: the factory's getSigner gives the same owner; whether its proxy is deployed;
//      with --safe, whether it is an owner and the Safe's threshold
// What it cannot show: E0F0 signs whatever it is asked, so the binding proves a genuine Trust M
// signed the statement, not on its own that the key lives in that chip; and the lifecycle in the
// bundle is what the chip told the board that read it. docs/mainnet/THREAT-MODEL.md has the rest.
import { createHash, createPublicKey, X509Certificate } from "node:crypto";
import { readFileSync } from "node:fs";
import { p256 } from "@noble/curves/p256";
import { createPublicClient, getAddress, http, parseAbi } from "viem";
import { base, baseSepolia, mainnet } from "viem/chains";
import { CFG } from "./sim.mjs";
import { p256Owner } from "./sigs.mjs";

// Infineon's CAs by issuer name, as firmware/tmcfg.py pins them (from TrustMAttest's test, matched
// by TM1's certificate on 2026-09-28).
const CAS = {
  "Infineon OPTIGA(TM) Trust M CA 101": [
    "97337734AD7423A14BF40FD4EE1D27AF8ED05AE87970C74DFE29889B499AD2D0",
    "1EA249AE7910F052C59D85514A8215E2D63E4730CDFB5CC153BBCC00A7E6408B"],
};
const CHAINS = {
  basesep: { chain: baseSepolia, rpc: process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org", explorer: "https://sepolia.basescan.org" },
  base: { chain: base, rpc: process.env.BASE_RPC || "https://mainnet.base.org", explorer: "https://basescan.org" },
  eth: { chain: mainnet, rpc: process.env.ETH_RPC || "https://ethereum-rpc.publicnode.com", explorer: "https://etherscan.io" },
};
const ABI = parseAbi([
  "function getSigner(uint256 x, uint256 y, uint176 verifiers) view returns (address)",
  "function getOwners() view returns (address[])",
  "function getThreshold() view returns (uint256)",
]);
const KEY = 0xe0f1, OPERATIONAL = 0x07, LCSO_BELOW_OP = "e1fc07";
const SPARES = ["E0F2", "E0F3", "E0FC", "E0FD", "E0E1", "E0E8", "E0EF", "E120", "E121", "E122", "E123",
  ...Array.from({ length: 10 }, (_, i) => (0xf1d2 + i).toString(16).toUpperCase()), "F1E0", "F1E1"];
const BIND_DOMAIN = Buffer.from("PicoQuorum Trust M key binding v1");

const args = process.argv.slice(3);
const opt = (k) => (args.includes(k) ? args[args.indexOf(k) + 1] : null);
const file = args.find((a, i) => !a.startsWith("--") && !(i > 0 && args[i - 1].startsWith("--")));
const hex = (h) => Buffer.from(h || "", "hex");
const sha256 = (...parts) => createHash("sha256").update(Buffer.concat(parts)).digest();
const b32 = (big) => Buffer.from(big.toString(16).padStart(64, "0"), "hex");
const rows = [];
let failed = 0;
function row(ok, what, detail = "") {
  rows.push([ok, what, detail]);
  if (ok === false) failed++;
  console.log(`${ok === true ? "pass" : ok === false ? "FAIL" : "note"}  ${what}${detail ? `\n      ${detail}` : ""}`);
}

if (!file) {
  console.error("usage: tools/quorum verify BUNDLE.json [--chain basesep,base,eth] [--safe CHAIN:0x..[,CHAIN:0x..]]");
  process.exit(2);
}
const B = JSON.parse(readFileSync(file, "utf8"));
if (B.format !== "picoquorum-trustm-attest-1") {
  console.error(`${file}: not a Trust M attestation bundle (format ${B.format})`);
  process.exit(2);
}

// --- the chip -------------------------------------------------------------------------------------
const uid = hex(B.uid);
const serial = uid.subarray(11, 21).toString("hex");
console.log(`Trust M ${serial} (UID ${B.uid}), read ${B.made} by ${B.board ? "board " + B.board : "?"} firmware ${B.firmware || "?"}\n`);
row(uid.length === 27 && serial === B.serial, "UID: 27 bytes, the serial is its batch and wafer position", serial);

// 1. the certificate (E0E0: C0, length, chain length, certificate length, DER)
const raw = hex(B.cert);
const der = raw[0] === 0xc0 ? raw.subarray(9, 9 + raw.readUIntBE(6, 3)) : raw;
let e0f0 = null;
try {
  const cert = new X509Certificate(der);
  const issuer = (cert.issuer.match(/CN=([^\n]+)/) || [])[1];
  const ca = CAS[issuer];
  const caKey = ca && createPublicKey({ key: { kty: "EC", crv: "P-256", x: Buffer.from(ca[0], "hex").toString("base64url"),
    y: Buffer.from(ca[1], "hex").toString("base64url") }, format: "jwk" });
  const jwk = cert.publicKey.export({ format: "jwk" });
  row(!!ca && cert.verify(caKey), `factory certificate signed by ${issuer || "?"}`,
    `serial ${cert.serialNumber.toLowerCase()}, subject ${cert.subject.replace(/\n/g, ", ")}, valid ${cert.validFrom} to ${cert.validTo}`);
  e0f0 = Buffer.concat([Buffer.from([4]), Buffer.from(jwk.x, "base64url"), Buffer.from(jwk.y, "base64url")]);
} catch (e) {
  row(false, "factory certificate: does not parse as an X.509 certificate with a P-256 key", e.message);
}

// 3 (first: the binding needs the key). The record, F1D0: "PQ" | 2 | profile | serial(10) | OID | flags | qx | qy | owner | date | build
const rec = hex(B.record);
const ok3 = rec.length >= 110 && rec.subarray(0, 2).toString() === "PQ" && rec[2] === 2;
const qx = ok3 ? BigInt("0x" + rec.subarray(18, 50).toString("hex")) : 0n;
const qy = ok3 ? BigInt("0x" + rec.subarray(50, 82).toString("hex")) : 0n;
const recOwner = ok3 ? getAddress("0x" + rec.subarray(82, 102).toString("hex")) : null;
const made = ok3 ? new Date(rec.readUInt32BE(102) * 1000).toISOString().slice(0, 10) : "?";
row(ok3 && rec.subarray(4, 14).toString("hex") === serial && rec.readUInt16BE(14) === KEY,
  "record (F1D0): this chip's serial, the key in E0F1", ok3 ? `key ${qx.toString(16).padStart(64, "0").slice(0, 8)}, written ${made}, build ${rec.subarray(106, 110).toString("hex")}` : "no PicoQuorum record");
const owner = ok3 ? p256Owner(CFG.signer, "0x" + qx.toString(16), "0x" + qy.toString(16)) : null;
row(ok3 && owner === recOwner, "owner address: computed from the key, the same as the record says", owner || "");

// 2. the binding, F1D1: "PB" | 1 | r | s | SHA-256(cert DER)[:16]
const bind = hex(B.binding);
const okB = bind.length >= 83 && bind.subarray(0, 2).toString() === "PB" && bind[2] === 1;
const sameCert = okB && bind.subarray(67, 83).equals(sha256(der).subarray(0, 16));
const digest = sha256(BIND_DOMAIN, uid, Buffer.from([0xe0, 0xf1]), b32(qx), b32(qy));
const sigOk = okB && !!e0f0 && p256.verify({ r: BigInt("0x" + bind.subarray(3, 35).toString("hex")), s: BigInt("0x" + bind.subarray(35, 67).toString("hex")) },
  digest, e0f0, { prehash: false, lowS: false });
row(sameCert && sigOk, "binding (F1D1): the factory key E0F0 signed this UID + E0F1 + this public key",
  "proves a genuine Trust M signed the statement; E0F0 signs what it is asked, so not on its own that the key is inside");

// 2b. the live challenge (records made since 2026-10-01): the chip held the certificate's key then
if (B.live) {
  const ld = sha256(Buffer.from("PicoQuorum Trust M attest v1"), uid, hex(B.live.nonce));
  const liveOk = !!e0f0 && p256.verify({ r: BigInt("0x" + B.live.r), s: BigInt("0x" + B.live.s) }, ld, e0f0, { prehash: false, lowS: false });
  row(liveOk, "live: the factory key signed a fresh challenge, under the certificate's key",
    liveOk ? "the chip still held its Infineon key when this record was made" : "the chip's E0F0 is NOT the certificate's key any more");
} else row(null, "live: not in this record (made before the live challenge existed); run tools/fw attest again");

// 4. the lifecycle, as the chip reported it to the board that read it
const meta = (oid) => {
  const m = B.metadata?.[oid];
  if (!m) return null;
  const b = hex(m), out = {};
  for (let i = 2; i < 2 + b[1]; i += 2 + b[i + 1]) out[b[i].toString(16)] = b.subarray(i + 2, i + 2 + b[i + 1]).toString("hex");
  return { lcso: out.c0 ? parseInt(out.c0, 16) : null, change: out.d0 || "", exec: out.d3 || "", algo: out.e0 || "" };
};
const sealed = ["E0F1", "F1D0", "F1D1"].map((o) => [o, meta(o)]);
row(sealed.every(([, m]) => m && m.lcso === OPERATIONAL && m.change === LCSO_BELOW_OP),
  "sealed (as reported): E0F1, F1D0, F1D1 lifecycle operational, Change LcsO<op", sealed.map(([o, m]) => `${o} ${m ? "LcsO " + m.lcso : "missing"}`).join(", "));
const k = meta("E0F1");
row(k && k.algo === "03" && k.exec === "00", "E0F1: a P-256 key, signing open to the board (Execute ALW: no PIN)");
const f0 = meta("E0F0"), fc = meta("E0E0");
row(f0 && fc && f0.change === "ff" && fc.change === "ff", "Infineon's factory key and certificate: Change NEV, as they came",
  `E0F0 Change ${f0 ? f0.change : "?"}, LcsO ${f0 ? f0.lcso : "?"}; E0E0 Change ${fc ? fc.change : "?"}, LcsO ${fc ? fc.lcso : "?"}`);
const sp = SPARES.map((o) => [o, meta(o)]).filter(([, m]) => m);
const frozen = sp.filter(([, m]) => m.lcso === OPERATIONAL && ["ff", LCSO_BELOW_OP].includes(m.change));
const open = sp.filter(([, m]) => m.lcso < OPERATIONAL);
row(open.length ? null : true, `spares (as reported): ${frozen.length} of ${sp.length} frozen`,
  open.length ? `still writable: ${open.map(([o]) => o).join(" ")}` : "nothing else on the chip can be written or get a key");

// 5. the chains
const chains = (opt("--chain") || "").split(",").filter(Boolean);
const safes = (opt("--safe") || "").split(",").filter(Boolean).map((s) => s.split(":"));
for (const name of [...new Set([...chains, ...safes.map(([c]) => c)])]) {
  const c = CHAINS[name];
  if (!c) { row(false, `--chain ${name}: one of ${Object.keys(CHAINS).join(", ")}`); continue; }
  if (!owner) break;
  const pub = createPublicClient({ chain: c.chain, transport: http(c.rpc) });
  try {
    const got = getAddress(await pub.readContract({ address: CFG.signer.factory, abi: ABI, functionName: "getSigner",
      args: [qx, qy, BigInt(CFG.signer.verifiers)] }));
    row(got === owner, `${c.chain.name}: the passkey factory's getSigner gives the same owner`, got);
    const code = await pub.getCode({ address: owner });
    row(null, `${c.chain.name}: signer proxy ${code ? "deployed" : "not deployed yet (tools/quorum live enroll)"}`, `${c.explorer}/address/${owner}`);
    for (const [, safe] of safes.filter(([cn]) => cn === name)) {
      const [owners, threshold] = await Promise.all([pub.readContract({ address: safe, abi: ABI, functionName: "getOwners" }),
        pub.readContract({ address: safe, abi: ABI, functionName: "getThreshold" })]);
      row(owners.map((o) => getAddress(o)).includes(owner), `${c.chain.name}: an owner of Safe ${getAddress(safe)}`,
        `${threshold} of ${owners.length}: ${owners.map((o) => o.slice(0, 6) + "…" + o.slice(-4)).join(", ")}`);
    }
  } catch (e) {
    row(false, `${c.chain.name}: could not read the chain`, e.shortMessage || e.message);
  }
}

console.log(`\n${failed ? `${failed} FAILED` : "verify: every check passes"} (${rows.length} lines)`);
process.exit(failed ? 1 : 0);
