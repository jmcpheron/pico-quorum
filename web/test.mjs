// The page's logic, checked without a browser or a chain. Exit 1 on any failure.
//   cd web && npm test
// 1. Every bundle in docs/mainnet/attest/: the browser's checks (src/attest.mjs) give the same verdict,
//    line by line, as tools/quorum verify (tools/mock-tx-service/attest.mjs); tampered copies fail.
// 2. A queued transaction with an ECDSA and a console (contract) confirmation: the hash matches
//    sim.mjs and firmware/safe_tx.py, both confirmations check, and execTransaction's signatures are
//    packed with the contract signature's data after the slots (the GS021 case).
// 3. The verify code matches the console's, and the console's top-level refusals match decode.py.
// 4. Blockies: the page draws the same picture as the console (firmware/blockies.py) for addresses
//    and transaction hashes.
// 5. Proposing: every kind the page builds is read by the console's own decoder (firmware/decode.py)
//    as what the page says it is; the typed data the wallet signs hashes to the console's hash; the
//    signature is checked and normalised; the body has what Safe's service requires.
// 6. Offchain lookups (EIP-3668) are never followed: against a local RPC whose contract answers every
//    read with OffchainLookup, the page's client refuses the read and its gateway is never asked,
//    where viem's default client asks it.
import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { writeConfig } from "./config.mjs";

writeConfig();
const { verifyBundle } = await import("./src/attest.mjs");
const S = await import("./src/safe.mjs");
const { softContractSignature, checkWebAuthn, parse } = await import("../tools/mock-tx-service/sigs.mjs");
const sim = await import("../tools/mock-tx-service/sim.mjs");
const { p256 } = await import("@noble/curves/p256");
const { privateKeyToAccount } = await import("viem/accounts");
const { getAddress, size, slice, hexToBigInt } = await import("viem");

const ROOT = fileURLToPath(new URL("../", import.meta.url));
let failed = 0;
const check = (ok, what) => {
  console.log(`${ok ? "pass" : "FAIL"}  ${what}`);
  if (!ok) failed++;
};

// ----------------------------------------------------------------------------- 1. bundles
const dir = `${ROOT}docs/mainnet/attest/`;
for (const f of readdirSync(dir).filter((x) => x.endsWith(".json"))) {
  const B = JSON.parse(readFileSync(dir + f, "utf8"));
  const cli = spawnSync(process.execPath, [`${ROOT}tools/mock-tx-service/attest.mjs`, "verify", dir + f], { encoding: "utf8" });
  const want = [...cli.stdout.matchAll(/^(pass|FAIL|note)  /gm)].map((m) => ({ pass: true, FAIL: false, note: null })[m[1]]);
  const got = verifyBundle(B, S.CFG.signer);
  check(want.length === got.rows.length && want.every((w, i) => w === got.rows[i].ok),
    `${f}: the browser's ${got.rows.length} checks agree with tools/quorum verify's ${want.length}`);
  check(got.owner === getAddress(cli.stdout.match(/0x[0-9a-fA-F]{40}/)[0]), `${f}: same owner address, ${got.owner}`);

  const flip = (h, at) => h.slice(0, at) + ((parseInt(h[at], 16) ^ 1).toString(16)) + h.slice(at + 1);
  const badCert = verifyBundle({ ...B, cert: flip(B.cert, B.cert.length - 10) }, S.CFG.signer);
  check(badCert.rows[1].ok === false, `${f}: a certificate with a changed signature byte fails`);
  const badKey = verifyBundle({ ...B, record: flip(B.record, 40) }, S.CFG.signer);
  check(badKey.rows.find((r) => r.what.startsWith("binding")).ok === false && badKey.owner !== got.owner,
    `${f}: a record with a changed key byte fails the binding and gives another owner`);
}

// ----------------------------------------------------------------------------- 2. a queued transaction
const chainId = 84532;
const safe = getAddress("0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43");
const alice = privateKeyToAccount("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d");   // anvil #1, a test key
const sk = p256.utils.randomPrivateKey();
const pub = p256.getPublicKey(sk, false);
const qx = "0x" + Buffer.from(pub.slice(1, 33)).toString("hex"), qy = "0x" + Buffer.from(pub.slice(33)).toString("hex");
const chip = (await import("../tools/mock-tx-service/sigs.mjs")).p256Owner(S.CFG.signer, qx, qy);
const t = { safe, to: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", value: "1000000000000000", data: null, operation: 0,
            safeTxGas: "0", baseGas: "0", gasPrice: "0", gasToken: S.ZERO, refundReceiver: S.ZERO, nonce: 7 };
const hash = S.safeTxHash(chainId, safe, t);
check(hash === sim.safeTxHash(chainId, safe, { ...t, data: "0x" }), "safeTxHash: the page and sim.mjs agree");
const py = spawnSync("python3", ["-c", `import sys, json; sys.path.insert(0, ${JSON.stringify(ROOT + "firmware")})
import safe_tx
t = json.load(sys.stdin)
h = safe_tx.from_service(${chainId}, t)
print("0x" + "".join("%02x" % b for b in h), safe_tx.verify_code(h))`], { input: JSON.stringify(t), encoding: "utf8" });
const [fwHash, fwCode] = py.stdout.trim().split(" ");
check(fwHash === hash, "safeTxHash: the page and the console's firmware/safe_tx.py agree");
check(S.verifyCode(hash).replace(" ", "") === fwCode, `verify code: ${S.verifyCode(hash)}, as the console shows it`);

t.safeTxHash = hash;
t.confirmations = [
  { owner: alice.address, signature: await alice.sign({ hash }) },
  { owner: chip, signature: softContractSignature(sk, chip, hash) },
];
// A chain that answers the two reads checkTx makes: the Safe's own hash, and the owner contract's check.
const fake = {
  async readContract({ functionName, args }) {
    if (functionName === "getTransactionHash") return S.safeTxHash(chainId, safe, { to: args[0], value: args[1], data: args[2], operation: args[3],
      safeTxGas: args[4], baseGas: args[5], gasPrice: args[6], gasToken: args[7], refundReceiver: args[8], nonce: args[9] });
    if (functionName === "isValidSignature") {
      const p = parse(t.confirmations[1].signature);
      return args[1] === p.data && !checkWebAuthn(args[0], p, qx, qy) ? S.MAGIC : "0xffffffff";
    }
    throw new Error(functionName);
  },
};
const owners = [alice.address, chip, getAddress("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC")];
const c = await S.checkTx(fake, chainId, safe, owners, t);
check(!c.problems.length, "checkTx: the service's hash, the fields' hash and the Safe's agree");
check(c.valid.length === 2, "checkTx: the ECDSA and the console's contract confirmation are both valid");
check(c.confirmations[1].console && c.confirmations[1].kind === "contract", "checkTx: the console's confirmation is a contract signature naming PicoQuorum");

const { signatures } = S.execCall(t, c.valid, 2);
const sorted = [alice.address, chip].sort((a, b) => (BigInt(a) < BigInt(b) ? -1 : 1));
check(size(signatures) > 130, "execCall: two 65-byte slots and the contract data after them");
const slotOf = (i) => slice(signatures, 65 * i, 65 * (i + 1));
const ci = sorted.indexOf(chip);
check(getAddress(slice(slotOf(ci), 12, 32)) === chip && hexToBigInt(slice(slotOf(ci), 32, 64)) === 130n,
  "execCall: the console's slot names its signer and points at byte 130, past both slots (65 is GS021)");
check(slice(slotOf(1 - ci), 0, 65) === t.confirmations[0].signature, "execCall: Alice's ECDSA signature fills its own slot");

const forged = { ...t, confirmations: [t.confirmations[0], { owner: chip, signature: softContractSignature(p256.utils.randomPrivateKey(), chip, hash) }] };
const c2 = await S.checkTx(fake, chainId, safe, owners, forged);
check(c2.valid.length === 1 && !c2.confirmations[1].ok, "checkTx: a contract signature from another key is not valid");
const lied = { ...t, value: "2000000000000000" };
const c3 = await S.checkTx(fake, chainId, safe, owners, lied);
check(c3.problems.length > 0, "checkTx: a service hash that isn't the fields' hash is a problem");
const outsider = { ...t, confirmations: [t.confirmations[0]] };
const c4 = await S.checkTx(fake, chainId, safe, [chip], outsider);
check(c4.valid.length === 0, "checkTx: a valid signature from someone who isn't an owner doesn't count");

// ----------------------------------------------------------------------------- 3. console refusals
check(S.consoleRefuses(8453, { operation: 0, to: t.to }) === "", "refuses: a call is fine");
check(S.consoleRefuses(8453, { operation: 1, to: t.to }).includes("refuse"), "refuses: a delegatecall to an unpinned contract");
check(S.consoleRefuses(8453, { operation: 1, to: "0x9641d764fc13c8b624c04430c7356c1c7c8102e2", data: "0x8d80ff0a00" }) === "",
  "refuses: not a multiSend delegatecall to a pinned batcher");
check(S.consoleRefuses(8453, { operation: 1, to: "0x9641d764fc13c8b624c04430c7356c1c7c8102e2", data: "0x12345678" }) !== "",
  "refuses: any other call to the batcher by delegatecall");

// ----------------------------------------------------------------------------- 4. blockies
const { blockie, rgb } = await import("./src/blockies.mjs");
// The last seed is a release fingerprint (tools/releases/fingerprint.mjs): the Device screen's blockie.
const seeds = [safe, alice.address, chip, S.ZERO, "0xffffffffffffffffffffffffffffffffffffffff", hash,
  "0x4c86c7541a45eb43f24c48c178409de889c5f86d467c886d444e9e30b9a00e0b"].map((x) => x.toLowerCase());
const fwBlockies = JSON.parse(spawnSync("python3", ["-c", `import sys, json; sys.path.insert(0, ${JSON.stringify(ROOT + "firmware")})
import blockies
out = []
for seed in json.load(sys.stdin):
    data, fg, bg, spot = blockies.build(seed)
    out.append([[min(v, 2) for v in data], [blockies.hsl_to_rgb(c) for c in (fg, bg, spot)]])
print(json.dumps(out))`], { input: JSON.stringify(seeds), encoding: "utf8" }).stdout);
seeds.forEach((seed, i) => {
  const b = blockie(seed);
  const same = JSON.stringify([b.data.map((v) => Math.min(v, 2)), [b.color, b.bg, b.spot].map(rgb)]) === JSON.stringify(fwBlockies[i]);
  check(same, `blockie of ${seed.slice(0, 10)}…: the same cells and colours as the console's`);
});
check(JSON.stringify(blockie(safe.toLowerCase()).data) !== JSON.stringify(blockie(alice.address.toLowerCase()).data), "blockies: two addresses, two pictures");

// ----------------------------------------------------------------------------- 5. proposing
const P = await import("./src/propose.mjs");
const { hashTypedData, decodeFunctionData, toHex: hex } = await import("viem");
const bob = privateKeyToAccount("0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a");     // anvil #2, a test key
const carol = getAddress("0x90F79bf6EB2c4f870365E785982E1f101E93b906");                                      // anvil #3's address
const S5 = { address: safe, owners: [alice.address, bob.address, chip], threshold: 2, balance: 10n ** 16n };
const usdc = P.knownTokens(84532)[0];
check(usdc?.symbol === "USDC" && usdc.decimals === 6, "known tokens: USDC on Base Sepolia, 6 decimals, from quorum_cfg.py");
const cases = [
  ["eth", { to: carol, amount: "0.001" }, "SEND ETH", "Send 0.001 ETH"],
  ["token", { token: usdc.address, to: carol, amount: "2.5", decimals: 6, symbol: "USDC", known: true }, "SEND USDC", "Send 2.5 USDC"],
  ["add", { owner: carol, threshold: "2" }, "ADD OWNER", "Add owner"],
  ["remove", { owner: bob.address, threshold: "2" }, "REMOVE OWNER", "Remove owner"],
  ["swap", { old: chip, owner: carol }, "SWAP OWNER", "Replace owner"],
  ["threshold", { threshold: "3" }, "THRESHOLD", "Approvals needed: 3"],
  ["reject", {}, "REJECTION", "On-chain rejection"],
  ["custom", { to: usdc.address, data: "0x095ea7b3" + "0".repeat(24) + carol.slice(2).toLowerCase() + "f".repeat(64) }, "APPROVE USDC", "Approve UNLIMITED USDC"],
  ["release", { releaseEntry: { version: "2026.10.6", fingerprints: { console: "4c86c7541a45eb43f24c48c178409de889c5f86d467c886d444e9e30b9a00e0b" }, manifestSha256: "5f".repeat(32) } },
    "RELEASE", "Approve release 2026.10.6"],
];
const built = cases.map(([kind, input]) => P.safeTx(P.buildCall(kind, input, S5).call, 9));
const consoleSees = JSON.parse(spawnSync("python3", ["-c", `import sys, json; sys.path.insert(0, ${JSON.stringify(ROOT + "firmware")})
import decode
from quorum_cfg import CFG
ctx = decode.context(CFG, ${JSON.stringify(safe)}, chain=84532)
out = []
for t in json.load(sys.stdin):
    r = decode.review(t, ctx)
    out.append({"title": r["items"][0]["title"], "what": r["items"][0]["what"], "level": r["level"], "refuse": r["refuse"],
                "to": r["items"][0].get("to"), "text": r["items"][0].get("text", "")})
print(json.dumps(out))`], { input: JSON.stringify(built.map((t) => ({ ...t, value: String(t.value) }))), encoding: "utf8" }).stdout);
cases.forEach(([kind, , title, what], i) => {
  const r = consoleSees[i], b = P.buildCall(kind, cases[i][1], S5);
  check(r.title === title && r.what.startsWith(what) && !r.refuse && (b.red ? r.level === "red" : true),
    `propose ${kind}: the console reads it as ${title}, "${r.what}"${b.red ? ", on a red page" : ""}`);
});
{
  const rel = built[cases.findIndex(([k]) => k === "release")];
  check(rel.operation === 1 && S.consoleRefuses(84532, rel) === "" && P.proposalBody(safe, rel, "0x" + "00".repeat(32), alice.address, "0x").origin === rel.origin,
    "propose release: a delegatecall to the pinned SignMessageLib the console accepts, its release named in the origin note sent to the service");
  const o = JSON.parse(rel.origin);
  check(S.consoleRefuses(84532, { ...rel, origin: JSON.stringify({ pq: { ...o.pq, v: "2026.10.7" } }) }) !== "" && S.consoleRefuses(84532, { ...rel, origin: null }) !== "",
    "the page flags what the console refuses: a note naming another release, or none");
}
check(consoleSees[2].to === carol.toLowerCase() && /becomes 2/.test(consoleSees[2].text), "propose add: the console names the new owner and the new threshold");
const rm = decodeFunctionData({ abi: P.OWNER_ABI, data: built[3].data });
check(rm.args[0] === alice.address && rm.args[1] === bob.address && rm.args[2] === 2n, "propose remove: prevOwner is the owner before it in the Safe's list");
const sw = decodeFunctionData({ abi: P.OWNER_ABI, data: built[4].data });
check(sw.args[0] === bob.address && sw.args[1] === chip, "propose swap: prevOwner of the last owner is the one before it");
check(P.prevOwner(S5.owners, alice.address) === P.SENTINEL, "prevOwner: the first owner's is the sentinel, 0x…01");
check(P.isRejection(safe, built[6]) && !P.isRejection(safe, built[0]), "isRejection: the Safe calling itself with nothing, and nothing else");
check(P.nextNonce(9, []) === 9 && P.nextNonce(9, [{ nonce: 9 }, { nonce: "11" }]) === 12, "nextNonce: after the Safe's own and after the queue");
const throws = (f) => { try { f(); return false; } catch { return true; } };
check(throws(() => P.buildCall("add", { owner: bob.address, threshold: "2" }, S5)), "propose add: an existing owner is refused");
check(throws(() => P.buildCall("add", { owner: carol, threshold: "5" }, S5)), "propose add: a threshold above the owners is refused");
check(throws(() => P.buildCall("remove", { owner: alice.address, threshold: "1" }, { ...S5, owners: [alice.address], threshold: 1 })), "propose remove: the last owner is refused");
check(throws(() => P.buildCall("eth", { to: carol, amount: "0.0000000000000000001" }, S5)), "propose eth: more than 18 decimals is refused");
check(throws(() => P.buildCall("eth", { to: safe, amount: "1" }, S5)), "propose eth: sending to the Safe itself is refused");
check(throws(() => P.buildCall("threshold", { threshold: "2" }, S5)), "propose threshold: the threshold it already has is refused");
check(P.buildCall("threshold", { threshold: "1" }, S5).warnings.length === 1, "propose threshold: 1 of 3 warns that one owner could act alone");
check(throws(() => P.buildCall("custom", { to: carol, data: "0x12" }, S5)), "propose custom: data shorter than a selector is refused");

// What the wallet signs is the console's hash, and the signature that comes back is checked.
const t5 = built[0];
const h5 = S.safeTxHash(chainId, safe, t5);
const td = JSON.parse(JSON.stringify(P.typedData(chainId, safe, t5)));        // as it crosses to the wallet
const uints = new Set(td.types.SafeTx.filter((f) => f.type.startsWith("uint")).map((f) => f.name));
const msg = Object.fromEntries(Object.entries(td.message).map(([k, v]) => [k, uints.has(k) ? BigInt(v) : v]));
const { EIP712Domain, ...types } = td.types;
check(EIP712Domain.length === 2 && hashTypedData({ domain: td.domain, types, primaryType: td.primaryType, message: msg }) === h5,
  "typedData: what the wallet signs hashes to the page's safeTxHash");
const py5 = spawnSync("python3", ["-c", `import sys, json; sys.path.insert(0, ${JSON.stringify(ROOT + "firmware")})
import safe_tx
h = safe_tx.from_service(${chainId}, json.load(sys.stdin))
print("0x" + "".join("%02x" % b for b in h))`], { input: JSON.stringify({ ...t5, safe, value: String(t5.value), data: null }), encoding: "utf8" });
check(py5.stdout.trim() === h5, "typedData: and to the console's own hash (firmware/safe_tx.py)");
const sig5 = await alice.signTypedData({ domain: td.domain, types, primaryType: td.primaryType, message: msg });
check(await P.walletSignature(h5, sig5, alice.address) === sig5, "walletSignature: a wallet's EIP-712 signature passes as is");
const v01 = sig5.slice(0, 130) + hex(Number(BigInt("0x" + sig5.slice(130))) - 27, { size: 1 }).slice(2);
check(await P.walletSignature(h5, v01, alice.address) === sig5, "walletSignature: v as 0/1 becomes 27/28");
let refused = "";
try { await P.walletSignature(h5, sig5, bob.address); } catch (e) { refused = e.message; }
check(/not your wallet/.test(refused), "walletSignature: a signature from another account is refused before anything is sent");
const body = P.proposalBody(safe, t5, h5, alice.address, sig5);
const required = ["baseGas", "contractTransactionHash", "gasPrice", "nonce", "operation", "safe", "safeTxGas", "sender", "to", "value"];
check(required.every((k) => body[k] !== undefined && body[k] !== null) && body.value === "1000000000000000" && body.data === null && body.nonce === 9,
  "proposalBody: every field Safe's service requires, value as a decimal string");
const back5 = { ...body, safeTxHash: body.contractTransactionHash, confirmations: [{ owner: body.sender, signature: body.signature }] };
const c5 = await S.checkTx(fake, chainId, safe, S5.owners, back5, { onchainHash: false });
check(!c5.problems.length && c5.valid.length === 1, "proposalBody: read back from the queue, the page checks it and counts the confirmation");

// ----------------------------------------------------------------------------- the built page
try {
  const js = readFileSync(`${ROOT}docs/app/app.js`, "utf8");
  check(!/from\s*["']node:/.test(js) && !/require\(["']node:/.test(js), "docs/app/app.js: no Node built-ins in the bundle");
  const built = JSON.parse(readFileSync(`${ROOT}docs/app/BUILD.json`, "utf8"));
  const sha = (await import("node:crypto")).createHash("sha256").update(readFileSync(`${ROOT}docs/app/app.js`)).digest("hex");
  check(built.files["app.js"] === sha, "docs/app/BUILD.json: matches app.js");
  const home = readFileSync(`${ROOT}docs/index.html`, "utf8");
  check(/<a class="btn go big" href="app\/">Launch app/.test(home) && !/%%/.test(home) && !/<script/i.test(home),
    "docs/index.html: the front page launches the app, has no script and no unfilled placeholder");
} catch (e) {
  check(false, `docs/app: ${e.message} (run npm run build)`);
}

// ---- your passkey, found again: its public key from two of its signatures (emu/core/webauthn-assert.mjs,
// used by the console page's "I already have one"), against noble's P-256
{
  const { p256 } = await import("@noble/curves/p256");
  const { recoverKeys } = await import("../emu/core/webauthn-assert.mjs");
  const hx = (b) => Buffer.from(b).toString("hex");
  let ok = 0, one = 0;
  for (let i = 0; i < 8; i++) {
    const sk = p256.utils.randomPrivateKey(), pk = p256.getPublicKey(sk, false), want = { x: hx(pk.slice(1, 33)), y: hx(pk.slice(33)) };
    const keys = [0, 1].map(() => { const d = crypto.getRandomValues(new Uint8Array(32)); const sg = p256.sign(d, sk, { lowS: i % 2 === 0 }); return recoverKeys(d, sg.r, sg.s); });
    if (keys.every((ks) => ks.some((k) => k.x === want.x && k.y === want.y))) ok++;
    const both = keys[0].filter((k) => keys[1].some((m) => m.x === k.x && m.y === k.y));
    if (both.length === 1 && both[0].x === want.x && both[0].y === want.y) one++;
  }
  check(ok === 8, "recoverKeys: every signature names its key among its candidates (low and high s)");
  check(one === 8, "recoverKeys: two signatures from one key name exactly that key");
  const p2 = p256.getPublicKey(p256.utils.randomPrivateKey(), false), d = new Uint8Array(32).fill(7), sg = p256.sign(d, p256.utils.randomPrivateKey());
  check(!recoverKeys(d, sg.r, sg.s).some((k) => k.x === hx(p2.slice(1, 33))), "recoverKeys: a signature by another key doesn't name this one");
}

// ---- the app's own passkey page links an owner into the Add owner form
{
  const src = readFileSync(new URL("./src/main.mjs", import.meta.url), "utf8");
  check(/parts\[0\] === "passkey"\) return passkeyView\(\)/.test(src) && /new\/add\/\$\{k\.owner\}/.test(src) && /owner: getAddress\(presetNonce\)/.test(src),
    "#/passkey: routed, links each saved Safe's Add owner with the owner filled in");
}

// ---- the console page's owner address (emu/web/browser.mjs, emu/core/keccak.mjs: no viem there):
// keccak-256 as noble's, EIP-55 as viem's, and the passkey's owner as p256Owner's
{
  const { keccak256 } = await import("../emu/core/keccak.mjs");
  const { keccak_256 } = await import("@noble/hashes/sha3");
  const B = await import("../emu/web/browser.mjs");
  const { p256Owner } = await import("../tools/mock-tx-service/sigs.mjs");
  const sizes = [0, 1, 31, 135, 136, 137, 271, 272, 1000];
  check(sizes.every((n) => { const d = crypto.getRandomValues(new Uint8Array(n)); return Buffer.from(keccak256(d)).equals(Buffer.from(keccak_256(d))); }),
    `keccak.mjs: the same as noble's keccak_256 (${sizes.join(", ")} bytes: the rate edges)`);
  const addrs = Array.from({ length: 6 }, () => "0x" + Buffer.from(crypto.getRandomValues(new Uint8Array(20))).toString("hex"));
  check(addrs.every((a) => B.checksum(a) === getAddress(a) && B.isAddress(a) && B.isAddress(getAddress(a)) && B.isAddress(a.toUpperCase().replace("0X", "0x"))),
    "browser.mjs checksum: viem's getAddress; lowercase, uppercase and checksummed are addresses");
  const wrong = (a) => { const c = getAddress(a), i = [...c].findIndex((ch, j) => j > 1 && /[a-fA-F]/.test(ch)); return c.slice(0, i) + (c[i] === c[i].toLowerCase() ? c[i].toUpperCase() : c[i].toLowerCase()) + c.slice(i + 1); };
  check(addrs.every((a) => !B.isAddress(wrong(a))) && !B.isAddress("0x1234") && !B.isAddress("base:" + addrs[0]), "and a wrong checksum capital, a short one or a prefixed one isn't");
  const cfg = B.consoleCfg([{ name: "quorum_cfg.py", text: readFileSync(new URL("../firmware/quorum_cfg.py", import.meta.url), "utf8") }]);
  check(JSON.stringify(cfg.signer) === JSON.stringify(S.CFG.signer), "consoleCfg reads the signer from quorum_cfg.py as web/config.mjs does");
  let same = 0;
  for (let i = 0; i < 4; i++) {
    const pk = p256.getPublicKey(p256.utils.randomPrivateKey(), false);
    const x = Buffer.from(pk.slice(1, 33)).toString("hex"), y = Buffer.from(pk.slice(33)).toString("hex");
    same += B.passkeyOwner({ x, y }, cfg.signer) === getAddress(p256Owner(S.CFG.signer, "0x" + x, "0x" + y));
  }
  check(same === 4, "passkeyOwner: the passkey's owner address is p256Owner's (sigs.mjs), checksummed");
}

// ----------------------------------------------------------------------------- 6. offchain lookups
{
  const { createServer } = await import("node:http");
  const { createPublicClient, encodeAbiParameters, encodeErrorResult, http, parseAbi } = await import("viem");
  const target = getAddress("0x000000000000000000000000000000000000dead");
  const CALLBACK = "0x12345678";
  let gateway = 0, lookup = "0x";
  const srv = createServer(async (req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    if (req.url.startsWith("/gateway/")) { gateway++; return res.end(JSON.stringify({ data: "0x" })); }
    let body = "";
    for await (const c of req) body += c;
    const answer = (m) => m.method !== "eth_call" ? { jsonrpc: "2.0", id: m.id, result: "0x2105" }
      : m.params[0].data.startsWith(CALLBACK) ? { jsonrpc: "2.0", id: m.id, result: encodeAbiParameters([{ type: "address[]" }], [[]]) }
      : { jsonrpc: "2.0", id: m.id, error: { code: 3, message: "execution reverted", data: lookup } };
    const msg = JSON.parse(body);
    res.end(JSON.stringify(Array.isArray(msg) ? msg.map(answer) : answer(msg)));
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const rpc = `http://127.0.0.1:${srv.address().port}/`;
  lookup = encodeErrorResult({
    abi: parseAbi(["error OffchainLookup(address sender, string[] urls, bytes callData, bytes4 callbackFunction, bytes extraData)"]),
    errorName: "OffchainLookup", args: [target, [rpc + "gateway/{sender}/{data}.json"], "0x1234", CALLBACK, "0x"],
  });
  const read = (c) => c.readContract({ address: target, abi: parseAbi(["function getOwners() view returns (address[])"]), functionName: "getOwners" });
  const refused = await read(S.client("base", rpc)).then(() => false, () => true);
  check(refused && gateway === 0, "client: a contract's offchain lookup (EIP-3668) is refused, and its URL is never fetched");
  await read(createPublicClient({ transport: http(rpc) })).catch(() => {});
  check(gateway > 0, "and the check is real: viem's default client would have fetched it");
  srv.close();
}

console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
