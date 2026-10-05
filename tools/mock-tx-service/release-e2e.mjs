// tools/quorum release-e2e: a PicoQuorum release approved by a Safe, end to end, on a real chain and
// no hardware (docs/GOVERNANCE.md). An Anvil fork of Base (port 8547), the forked Family Safe behind
// the service (8799), and the console firmware on the emulator with its virtual ATECC608:
//   1. Alice proposes that the Safe approve this checkout's release (a delegatecall to Safe's
//      SignMessageLib, signMessage(D), the release named in the origin note) and signs it; the
//      service also queues a forged one, whose note names another release than its digest
//   2. the console opens #0 ("Approve release ..."), pages through it, holds A: its key signs, and
//      execTransaction runs on the fork
//   3. the console opens the forged #1: refused, and nothing is sent
// Then the chain: isValidSignature(D, "0x") on the Safe returns 0x1626ba7e and signedMessages(M) is
// 1; after the console's owner is removed (Alice and Bob, executed), the approval still holds; a
// release nobody approved does not. Needs Foundry (anvil) and emu/node_modules.
import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createPublicClient, createWalletClient, encodeFunctionData, getAddress, hashTypedData, http, parseAbi } from "viem";
import { forkBlock, startAnvil } from "./fork.mjs";
import { CFG, PEOPLE, TYPES } from "./sim.mjs";
import { EXECUTOR, SAFE_ABI } from "./chain.mjs";
import { packSignatures } from "./sigs.mjs";
import { RELEASE_ABI, approvalTx, releaseDigest, safeMessageHash } from "./release.mjs";
import { imageFingerprint, manifest } from "../releases/fingerprint.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const ANVIL_PORT = Number(process.env.QUORUM_E2E_ANVIL_PORT || 8547);
const PORT = Number(process.env.QUORUM_E2E_PORT || 8799);
const BASE = `http://localhost:${PORT}`;
const SAFE = getAddress(CFG.safes[0].address);
const REL = { version: manifest().version, firmware: "0x" + imageFingerprint("console"), manifest: "0x" + "5f".repeat(32) };
const D = releaseDigest(REL);
const tmp = mkdtempSync(join(tmpdir(), "quorum-release-e2e-"));
const shot = join(tmp, "result.png");

let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };

const block = await forkBlock();
console.log(`fork of Base at block ${block}, anvil on ${ANVIL_PORT}, service on ${PORT}; release ${REL.version}, D ${D.slice(0, 14)}…`);
const anvil = await startAnvil(ANVIL_PORT, block);
const server = spawn(process.execPath, [join(ROOT, "tools/mock-tx-service/server.mjs"), "--chain", anvil.url, "--port", String(PORT)],
  { env: { ...process.env, QUORUM_STATE: join(tmp, "state.json") }, stdio: ["ignore", "pipe", "pipe"] });
let log = "";
server.stdout.on("data", (d) => (log += d));
server.stderr.on("data", (d) => (log += d));
const stop = () => { server.kill(); anvil.child.kill(); };

try {
  for (let i = 0; ; i++) {
    try { await fetch(BASE + "/sim/state"); break; } catch {}
    if (server.exitCode !== null || i > 600) throw new Error("the service did not start:\n" + log);
    await new Promise((r) => setTimeout(r, 100));
  }
  const chain = createPublicClient({ transport: http(anvil.url) });
  const approved = (digest) => chain.readContract({ address: SAFE, abi: RELEASE_ABI, functionName: "isValidSignature", args: [digest, "0x"] })
    .then((r) => r === "0x1626ba7e", () => false);
  check(!(await approved(D)), "before: the Safe has not approved the release");
  await fetch(BASE + "/sim/reset", { method: "POST", headers: { "content-type": "application/json" },
                                     body: JSON.stringify({ scenarios: ["release", "release-forged"], keepDevices: false }) });

  const chip = join(tmp, "chip.json");
  copyFileSync(new URL("emu-chip.json", import.meta.url), chip);
  const r = spawnSync(process.execPath, [join(ROOT, "emu/headless.mjs"), "quorum", "--app", BASE, "--chip", chip, "--quiet",
    "--wait", "4000",
    "--key", "A", "--wait", "300", "--key", "down", "--wait", "300", "--key", "A", "--wait", "300",   // open #0, page, to verify
    "--hold", "A", "--wait", "2400", "--release", "A", "--wait", "5000", "--shot", shot,             // hold to sign; the service executes
    "--key", "A", "--wait", "1500", "--key", "down", "--wait", "300", "--key", "A", "--wait", "300", // home, open the forged #1
    "--key", "A", "--wait", "1000"], { cwd: ROOT, encoding: "utf8" });
  check(r.status === 0 && !/Traceback/.test(r.stdout + r.stderr), "the console ran on the emulator without an error");

  const st = await (await fetch(BASE + "/sim/state")).json();
  const me = st.owners.find((o) => o.kind === "p256");
  check(!!me, `the console's key became an owner: signer proxy ${me?.address}`);
  const [appr, forged] = st.txs;
  check(appr?.operation === 1 && getAddress(appr.to) === getAddress(approvalTx(REL).to) && appr.origin === approvalTx(REL).origin,
    "#0 is the approval: a delegatecall to SignMessageLib, the release in its origin note");
  check(!!appr?.confirmations.find((c) => c.owner === me?.address && c.signatureType === "CONTRACT_SIGNATURE"), "#0 has the console's contract signature");
  check(appr?.isExecuted && appr.isSuccessful, `#0 executed onchain: ${appr?.transactionHash}`);
  check(forged && !forged.isExecuted && !forged.confirmations.some((c) => c.owner === me?.address), "the forged #1 got no signature from the console");

  check(await approved(D), `the chain: isValidSignature(D, "0x") on the Safe is 0x1626ba7e: release ${REL.version} is approved`);
  const M = safeMessageHash(31337, SAFE, D);
  check((await chain.readContract({ address: SAFE, abi: RELEASE_ABI, functionName: "signedMessages", args: [M] })) === 1n, "and signedMessages(M) is 1, for good");

  // the console's owner goes: Alice and Bob remove it, executed from anvil's account 0
  const owners = await chain.readContract({ address: SAFE, abi: SAFE_ABI, functionName: "getOwners" });
  const threshold = await chain.readContract({ address: SAFE, abi: SAFE_ABI, functionName: "getThreshold" });
  const nonce = await chain.readContract({ address: SAFE, abi: SAFE_ABI, functionName: "nonce" });
  const i = owners.findIndex((o) => getAddress(o) === getAddress(me.address));
  const prev = i === 0 ? "0x0000000000000000000000000000000000000001" : owners[i - 1];
  const data = encodeFunctionData({ abi: parseAbi(["function removeOwner(address prevOwner, address owner, uint256 _threshold)"]),
    functionName: "removeOwner", args: [prev, me.address, threshold > BigInt(owners.length - 1) ? BigInt(owners.length - 1) : threshold] });
  const f = { to: SAFE, value: 0n, data, operation: 0, safeTxGas: 0n, baseGas: 0n, gasPrice: 0n,
    gasToken: "0x0000000000000000000000000000000000000000", refundReceiver: "0x0000000000000000000000000000000000000000", nonce };
  const h = hashTypedData({ domain: { chainId: 31337, verifyingContract: SAFE }, types: TYPES, primaryType: "SafeTx", message: f });
  const confs = await Promise.all(["alice", "bob"].map(async (who) => ({ owner: PEOPLE[who].address, signature: await PEOPLE[who].sign({ hash: h }) })));
  const signatures = packSignatures(confs);       // ECDSA over the hash itself: v 27/28, as the service stores them
  const wallet = createWalletClient({ account: EXECUTOR, transport: http(anvil.url) });
  const tx = await wallet.writeContract({ chain: null, address: SAFE, abi: SAFE_ABI, functionName: "execTransaction",
    args: [f.to, f.value, f.data, f.operation, f.safeTxGas, f.baseGas, f.gasPrice, f.gasToken, f.refundReceiver, signatures] });
  const rc = await chain.waitForTransactionReceipt({ hash: tx });
  const after = await chain.readContract({ address: SAFE, abi: SAFE_ABI, functionName: "getOwners" });
  check(rc.status === "success" && !after.some((o) => getAddress(o) === getAddress(me.address)), "the console's owner is removed (Alice and Bob, executed)");
  check(await approved(D), "the approval still holds with the owners changed: it is on chain, not a list of signatures");
  check(!(await approved(releaseDigest({ ...REL, version: "2099.1.1" }))), "a release nobody approved is not");
  if (failed) console.log("\nservice log:\n" + log.split("\n").slice(-25).join("\n"));
} catch (e) {
  failed++;
  console.log("FAIL  " + (e.shortMessage || e.message));
  console.log("\nservice log:\n" + log.split("\n").slice(-25).join("\n"));
} finally {
  stop();
}
if (failed || process.env.QUORUM_E2E_KEEP) console.log(`the console's screen after signing: ${shot}`);
else rmSync(tmp, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : "all pass: the console approved a release, and the Safe's approval is on chain for good");
process.exit(failed ? 1 : 0);
