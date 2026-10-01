// tools/quorum e2e-propose: starting a transaction when the consoles are the only owners left who
// can sign, end to end on the fork with no hardware (docs/guide/PROPOSING.md). The same Anvil fork
// of Base and service as e2e (here on 8547 and 8799, the service with --manual-exec, as Safe's real
// one never executes), the console firmware on the emulator with its virtual ATECC608:
//   0. Alice adds a delegate (live delegate add), and it is listed
//   1. live propose --by console: the laptop serves a new transaction to the console on its own
//      port (the stage), the console signs it, and that contract signature goes to the service as
//      the proposal. Alice confirms; live exec executes it
//   2. live propose --by console --no-service: a MultiSend replacing Alice and Bob, never shown to
//      the service. Alice's and the console's signatures are collected at the stage, and it
//      executes at the threshold
// Then the chain itself is asked. Exit 1 on any failure. Needs Foundry and emu/node_modules.
import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { p256 } from "@noble/curves/p256";
import { createPublicClient, getAddress, http, parseEther } from "viem";
import { forkBlock, startAnvil } from "./fork.mjs";
import { BOOK, CFG, PEOPLE } from "./sim.mjs";
import { SAFE_ABI } from "./chain.mjs";
import { p256Owner } from "./sigs.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const ANVIL_PORT = Number(process.env.QUORUM_E2E_ANVIL_PORT || 8547);
const PORT = Number(process.env.QUORUM_E2E_PORT || 8799);
const STAGE_PORT = Number(process.env.QUORUM_E2E_STAGE_PORT || 8792);
const BASE = `http://localhost:${PORT}`;
const SAFE = getAddress(CFG.safes[0].address);
const DELEGATE = "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc";        // anvil #5: a key, never funded
const tmp = mkdtempSync(join(tmpdir(), "quorum-e2e-propose-"));
const env = { ...process.env, QUORUM_PORT: String(PORT), QUORUM_ANVIL_PORT: String(ANVIL_PORT), QUORUM_STAGE_PORT: String(STAGE_PORT),
              QUORUM_LIVE_FILE: join(tmp, "live.json"), SAFE_API_KEY: "" };

let failed = 0;
const check = (ok, what) => {
  console.log(`${ok ? "pass" : "FAIL"}  ${what}`);
  if (!ok) failed++;
};
const post = (path, body) => fetch(BASE + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
const state = async () => (await fetch(BASE + "/sim/state")).json();

// tools/quorum live ..., to the end. -> {status, out}
const live = (...args) => {
  const r = spawnSync(process.execPath, [join(ROOT, "tools/mock-tx-service/cli.mjs"), "live", ...args, "--chain", "local", "--safe", SAFE],
                      { env, encoding: "utf8", timeout: 120000 });
  return { status: r.status, out: r.stdout + r.stderr };
};

// tools/quorum live propose ..., in the background: resolves when it prints `ready`, and again
// (done) when it exits.
function liveBackground(args, ready) {
  const child = spawn(process.execPath, [join(ROOT, "tools/mock-tx-service/cli.mjs"), "live", "propose", ...args, "--chain", "local", "--safe", SAFE],
                      { env, stdio: ["ignore", "pipe", "pipe"] });
  let out = "";
  const done = new Promise((res) => child.on("exit", (status) => res({ status, out })));
  const started = new Promise((res, rej) => {
    const look = (d) => {
      out += d;
      if (out.includes(ready)) res(out);
    };
    child.stdout.on("data", look);
    child.stderr.on("data", look);
    child.on("exit", () => rej(new Error(`live propose exited before "${ready}":\n${out}`)));
  });
  return { child, started, done, out: () => out };
}

// The console on the emulator, pointed at the stage: it opens the first transaction, pages
// through every page, and holds A long enough for a red one.
const chip = join(tmp, "chip.json");
copyFileSync(new URL("emu-chip.json", import.meta.url), chip);
function consoleSigns(shot) {
  const secrets = join(tmp, "stage_secrets.py");
  writeFileSync(secrets, `QUORUM_SAFES = [{"chainId": 31337, "address": "${SAFE.toLowerCase()}", "name": "Stage", "url": "http://localhost:${STAGE_PORT}"}]\n`);
  const r = spawnSync(process.execPath, [join(ROOT, "emu/headless.mjs"), "quorum", "--app", "http://localhost:1", "--secrets", secrets, "--chip", chip, "--quiet",
    "--wait", "9000", "--key", "A", "--wait", "400", ...Array(14).fill(["--key", "down", "--wait", "200"]).flat(),
    "--hold", "A", "--wait", "3400", "--release", "A", "--wait", "6000", "--shot", shot], { cwd: join(ROOT, "emu"), encoding: "utf8" });
  return r.status === 0 && !/Traceback/.test(r.stdout + r.stderr);
}

const block = await forkBlock();
console.log(`fork of Base at block ${block}, anvil on ${ANVIL_PORT}, service on ${PORT}, stage on ${STAGE_PORT}`);
const anvil = await startAnvil(ANVIL_PORT, block);
const server = spawn(process.execPath, [join(ROOT, "tools/mock-tx-service/server.mjs"), "--chain", anvil.url, "--port", String(PORT), "--manual-exec"],
  { env: { ...process.env, QUORUM_STATE: join(tmp, "state.json") }, stdio: ["ignore", "pipe", "pipe"] });
let log = "";
server.stdout.on("data", (d) => (log += d));
server.stderr.on("data", (d) => (log += d));
const bg = [];
const stop = () => {
  for (const b of bg) b.child.kill();
  server.kill();
  anvil.child.kill();
};

try {
  for (let i = 0; ; i++) {
    try {
      await fetch(BASE + "/sim/state");
      break;
    } catch {}
    if (server.exitCode !== null || i > 600) throw new Error("the service did not start:\n" + log);
    await new Promise((r) => setTimeout(r, 100));
  }
  const chain = createPublicClient({ transport: http(anvil.url) });
  const owners = async () => (await chain.readContract({ address: SAFE, abi: SAFE_ABI, functionName: "getOwners" })).map((a) => getAddress(a));
  await post("/sim/reset", { scenarios: [], keepDevices: false });
  const key = JSON.parse(readFileSync(chip, "utf8")).keys["0"];
  const pub = p256.getPublicKey(BigInt("0x" + key), false);
  const hex = (b) => "0x" + Buffer.from(b).toString("hex");
  const me = p256Owner(CFG.signer, hex(pub.slice(1, 33)), hex(pub.slice(33, 65)));
  await post("/sim/device", { name: "emu", qx: hex(pub.slice(1, 33)), qy: hex(pub.slice(33, 65)) });
  check((await owners()).includes(me), `the console's signer proxy ${me} owns the Safe: 2 of ${(await owners()).length}`);

  // 0. a delegate
  const d = live("delegate", "add", DELEGATE, "--by", "alice", "--label", "laptop");
  check(d.status === 0, "Alice adds a delegate");
  check(live("delegate", "list").out.includes(DELEGATE), "the service lists it");

  // 1. the console's signature is the proposal
  const carol0 = await chain.getBalance({ address: BOOK.Carol });
  const p1 = liveBackground(["--by", "console", "send", BOOK.Carol, "0.01"], "waiting for a console's signature");
  bg.push(p1);
  await p1.started;
  check(consoleSigns(join(tmp, "1-signed.png")), "the console signed at the stage, on the emulator, without an error");
  const r1 = await Promise.race([p1.done, new Promise((r) => setTimeout(() => r({ status: "timeout", out: p1.out() }), 30000))]);
  check(r1.status === 0, `live propose --by console sent it to the service${r1.status ? `:\n${r1.out.slice(-600)}` : ""}`);
  let st = await state();
  const t1 = st.txs.find((t) => t.nonce === "0");
  check(t1 && getAddress(t1.proposer) === me, `the service lists #0, proposed by the console's owner ${t1?.proposer}`);
  check(t1?.confirmations.length === 1 && t1.confirmations[0].owner === me && t1.confirmations[0].signatureType === "CONTRACT_SIGNATURE",
        "its proposal signature counts as the console's confirmation");
  check((await post("/sim/confirm", { ref: "0", as: "alice" })).ok, "Alice confirms #0 at the service");
  const x1 = live("exec", "0");
  check(x1.status === 0 && /executed: 0x/.test(x1.out), "live exec executes #0");
  check((await chain.getBalance({ address: BOOK.Carol })) - carol0 === parseEther("0.01"), "Carol has exactly 0.01 ETH more");

  // 2. no service at all: Alice and Bob replaced in one MultiSend, signed at the stage
  const p2 = liveBackground(["--by", "console", "--no-service", "swap-owner", BOOK.Alice, BOOK.Savings, BOOK.Bob, BOOK.Carol], "waiting for 2 signatures");
  bg.push(p2);
  const out2 = await p2.started;
  const hash = out2.match(/safeTxHash\s+(0x[0-9a-f]{64})/)?.[1];
  check(!!hash && /MultiSend/.test(out2), `a MultiSend replacing two owners, ${hash?.slice(0, 10)}..`);
  const alice = await PEOPLE.alice.sign({ hash });
  const a = await fetch(`http://localhost:${STAGE_PORT}/api/v1/multisig-transactions/${hash}/confirmations/`,
                        { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ signature: alice }) });
  check(a.status === 201, "the stage takes Alice's signature");
  const forged = await fetch(`http://localhost:${STAGE_PORT}/api/v1/multisig-transactions/${hash}/confirmations/`,
                             { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ signature: await PEOPLE.bob.sign({ hash: "0x" + "11".repeat(32) }) }) });
  check(forged.status === 400, "and refuses a signature over something else");
  check(consoleSigns(join(tmp, "2-signed.png")), "the console signed the red MultiSend at the stage");
  const r2 = await Promise.race([p2.done, new Promise((r) => setTimeout(() => r({ status: "timeout", out: p2.out() }), 60000))]);
  check(r2.status === 0 && /executed: 0x/.test(r2.out), `live propose --no-service executed it${r2.status ? `:\n${r2.out.slice(-600)}` : ""}`);
  const now = await owners();
  check(now.includes(BOOK.Savings) && now.includes(BOOK.Carol) && now.includes(me) && !now.includes(BOOK.Alice) && !now.includes(BOOK.Bob),
        `the owners onchain: Savings, Carol and the console (${now.join(", ")})`);
  st = await state();
  check(!st.txs.some((t) => t.safeTxHash === hash), "the service never saw it");
  check(!/blind signing/.test(log), "no blind signature was attempted");
  if (failed) console.log("\nservice log:\n" + log.split("\n").slice(-25).join("\n"));
} catch (e) {
  failed++;
  console.log("FAIL  " + e.message);
} finally {
  stop();
}
if (failed || process.env.QUORUM_E2E_KEEP) console.log(`screens and live.json: ${tmp}`);
else rmSync(tmp, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : "all pass: consoles alone started, signed and executed Safe transactions on the fork");
process.exit(failed ? 1 : 0);
