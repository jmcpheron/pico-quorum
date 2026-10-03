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
const seeds = [safe, alice.address, chip, S.ZERO, "0xffffffffffffffffffffffffffffffffffffffff", hash].map((x) => x.toLowerCase());
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

console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
