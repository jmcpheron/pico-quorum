// tools/quorum e2e: one approval, end to end, on a real chain and no hardware. An Anvil fork of
// Base (its own port, 8546), the forked Family Safe behind the service (8798), and the console
// firmware on the emulator with its virtual ATECC608 (emu-chip.json, a throwaway key):
//   1. the console announces; its key's signer proxy is deployed and made an owner
//   2. Alice proposes 0.05 ETH to Carol and signs; the service also queues a tampered transaction
//   3. the console opens #0, pages through it, holds A: the chip signs, the service checks the
//      signature with the proxy's isValidSignature, and execTransaction runs on the fork
//   4. the console opens the tampered #1: refused, and nothing is sent
// Then the chain itself is asked: the Safe's nonce, Carol's balance, the execution receipt.
// Exit 1 on any failure. Needs Foundry (anvil) and emu/node_modules. QUORUM_E2E_KEEP=1 keeps the
// screenshot of the console after signing.
import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createPublicClient, getAddress, http, parseEther } from "viem";
import { forkBlock, startAnvil } from "./fork.mjs";
import { BOOK, CFG } from "./sim.mjs";
import { SAFE_ABI } from "./chain.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const ANVIL_PORT = Number(process.env.QUORUM_E2E_ANVIL_PORT || 8546);
const PORT = Number(process.env.QUORUM_E2E_PORT || 8798);
const BASE = `http://localhost:${PORT}`;
const SAFE = getAddress(CFG.safes[0].address);
const tmp = mkdtempSync(join(tmpdir(), "quorum-e2e-"));
const shot = join(tmp, "result.png");

let failed = 0;
const check = (ok, what) => {
  console.log(`${ok ? "pass" : "FAIL"}  ${what}`);
  if (!ok) failed++;
};

const block = await forkBlock();
console.log(`fork of Base at block ${block}, anvil on ${ANVIL_PORT}, service on ${PORT}`);
const anvil = await startAnvil(ANVIL_PORT, block);
const server = spawn(process.execPath, [join(ROOT, "tools/mock-tx-service/server.mjs"), "--chain", anvil.url, "--port", String(PORT)],
  { env: { ...process.env, QUORUM_STATE: join(tmp, "state.json") }, stdio: ["ignore", "pipe", "pipe"] });
let log = "";
server.stdout.on("data", (d) => (log += d));
server.stderr.on("data", (d) => (log += d));
const stop = () => {
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
  const carol0 = await chain.getBalance({ address: BOOK.Carol });
  await fetch(BASE + "/sim/reset", { method: "POST", headers: { "content-type": "application/json" },
                                     body: JSON.stringify({ scenarios: ["send-eth", "tampered"], keepDevices: false }) });

  const chip = join(tmp, "chip.json");
  copyFileSync(new URL("emu-chip.json", import.meta.url), chip);
  const r = spawnSync(process.execPath, [join(ROOT, "emu/headless.mjs"), "quorum", "--app", BASE, "--chip", chip, "--quiet",
    "--wait", "4000",
    "--key", "A", "--wait", "300", "--key", "down", "--wait", "300", "--key", "A", "--wait", "300",   // open #0, page, to verify
    "--hold", "A", "--wait", "2400", "--release", "A", "--wait", "5000", "--shot", shot,             // hold to sign; the service executes
    "--key", "A", "--wait", "1500", "--key", "down", "--wait", "300", "--key", "A", "--wait", "300", // home, open the tampered #1
    "--key", "A", "--wait", "1000"], { cwd: join(ROOT, "emu"), encoding: "utf8" });
  check(r.status === 0 && !/Traceback/.test(r.stdout + r.stderr), "the console ran on the emulator without an error");

  const st = await (await fetch(BASE + "/sim/state")).json();
  const me = st.owners.find((o) => o.kind === "p256");
  check(!!me, `the console's key became an owner: signer proxy ${me?.address}`);
  check(!!me && !!(await chain.getCode({ address: me.address })), "its signer proxy is deployed on the fork");
  const [send, lie] = st.txs;
  const mine = send?.confirmations.find((c) => c.owner === me?.address);
  check(!!mine && mine.signatureType === "CONTRACT_SIGNATURE", "#0 has the console's contract signature");
  check(send?.isExecuted && send.isSuccessful && /^0x[0-9a-f]{64}$/.test(send.transactionHash || ""), `#0 executed onchain: ${send?.transactionHash}`);
  const receipt = send?.transactionHash ? await chain.getTransactionReceipt({ hash: send.transactionHash }) : null;
  check(receipt?.status === "success" && getAddress(receipt.to) === SAFE, `the receipt: execTransaction on the Safe, ${receipt?.gasUsed} gas`);
  check(Number(await chain.readContract({ address: SAFE, abi: SAFE_ABI, functionName: "nonce" })) === 1, "the Safe's nonce onchain is 1");
  check((await chain.getBalance({ address: BOOK.Carol })) - carol0 === parseEther("0.05"), "Carol has exactly 0.05 ETH more");
  check(lie && !lie.isExecuted && !lie.confirmations.some((c) => c.owner === me?.address), "the tampered #1 got no signature from the console");
  check(!/blind signing/.test(log), "no blind signature was attempted");
  if (failed) console.log("\nservice log:\n" + log.split("\n").slice(-25).join("\n"));
} catch (e) {
  failed++;
  console.log("FAIL  " + e.message);
} finally {
  stop();
}
if (failed || process.env.QUORUM_E2E_KEEP) console.log(`the console's screen after signing: ${shot}`);
else rmSync(tmp, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : "all pass: the chip's signature executed a real Safe transaction on the fork");
process.exit(failed ? 1 : 0);
