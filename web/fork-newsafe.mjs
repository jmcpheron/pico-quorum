// New Safe (src/newsafe.mjs) against the real contracts, on an Anvil fork of Base Sepolia, with anvil's
// public test keys and a throwaway P-256 key. Not in CI: it needs anvil (foundryup -i v1.8.3) and the
// public RPC.   cd web && node fork-newsafe.mjs        (FORK_RPC= to fork another chain)
// It makes the Safe as the page does, checks what checkNew checks, then walks a recovery: the
// guardian starts it, it can't finish before 7 days, and after them the Safe is the wallet's alone.
// Candide refuses a guardian that is an owner, so the recovery address is another address (anvil #1).
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";
import { createPublicClient, createWalletClient, getAddress, http, parseAbi } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { baseSepolia } from "viem/chains";
import { p256 } from "@noble/curves/p256";
import { writeConfig } from "./config.mjs";

writeConfig();
const { CFG, SAFE_ABI } = await import("./src/safe.mjs");
const N = await import("./src/newsafe.mjs");
const { p256Owner } = await import("../tools/mock-tx-service/sigs.mjs");

const RPC = process.env.FORK_RPC || "https://sepolia.base.org", PORT = 8547, URL = `http://127.0.0.1:${PORT}`;
const anvil = spawn(process.env.ANVIL || join(homedir(), ".foundry/bin/anvil"), ["--fork-url", RPC, "--port", String(PORT), "--silent"], { stdio: "inherit" });
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };
try {
  const pub = createPublicClient({ chain: baseSepolia, transport: http(URL) });
  for (let i = 0; i < 100; i++) { try { await pub.getBlockNumber(); break; } catch { await new Promise((r) => setTimeout(r, 200)); } }
  const me = privateKeyToAccount("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80");   // anvil #0
  const w = createWalletClient({ account: me, chain: baseSepolia, transport: http(URL) });
  const back = privateKeyToAccount("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d");  // anvil #1: the recovery address
  const g = createWalletClient({ account: back, chain: baseSepolia, transport: http(URL) });
  const full = p256.getPublicKey(p256.utils.randomPrivateKey(), false);
  const qx = BigInt("0x" + Buffer.from(full.slice(1, 33)).toString("hex")), qy = BigInt("0x" + Buffer.from(full.slice(33)).toString("hex"));
  const owner = getAddress(p256Owner(CFG.signer, "0x" + qx.toString(16).padStart(64, "0"), "0x" + qy.toString(16).padStart(64, "0")));

  const safe = await N.predict(pub, me.address, owner, back.address, qx, qy);
  check(!(await pub.getCode({ address: safe })), `predicted ${safe}: nothing there yet`);
  const rc = await pub.waitForTransactionReceipt({ hash: await w.sendTransaction(N.createCall(me.address, owner, back.address, qx, qy)) });
  check(rc.status === "success" && !!(await pub.getCode({ address: safe })), `one transaction made it, at the predicted address (${rc.gasUsed} gas)`);
  for (const [ok, what] of await N.checkNew(pub, safe, me.address, owner, back.address)) check(ok, what);
  const again = await pub.call({ account: me.address, ...N.createCall(me.address, owner, back.address, qx, qy) }).then(() => true, () => false);
  check(!again, "the same wallet and key can't make a second Safe at that address");

  const R = parseAbi(["function confirmRecovery(address wallet, address[] newOwners, uint256 newThreshold, bool execute)",
    "function finalizeRecovery(address wallet)"]);
  await pub.waitForTransactionReceipt({ hash: await g.writeContract({ address: N.NEW_SAFE.recovery, abi: R, functionName: "confirmRecovery", args: [safe, [me.address], 1n, true] }) });
  const fin = () => pub.simulateContract({ account: me.address, address: N.NEW_SAFE.recovery, abi: R, functionName: "finalizeRecovery", args: [safe] }).then(() => true, () => false);
  const wait = async (s) => { await pub.request({ method: "evm_increaseTime", params: [s] }); await pub.request({ method: "evm_mine", params: [] }); };
  check(!(await fin()), "the recovery address starts a recovery; it can't be finalized at once");
  await wait(N.NEW_SAFE.days * 86400 - 60);
  check(!(await fin()), `nor a minute before ${N.NEW_SAFE.days} days`);
  await wait(61);
  await pub.waitForTransactionReceipt({ hash: await w.writeContract({ address: N.NEW_SAFE.recovery, abi: R, functionName: "finalizeRecovery", args: [safe] }) });
  const [owners, t] = await Promise.all([pub.readContract({ address: safe, abi: SAFE_ABI, functionName: "getOwners" }), pub.readContract({ address: safe, abi: SAFE_ABI, functionName: "getThreshold" })]);
  check(owners.length === 1 && getAddress(owners[0]) === me.address && t === 1n, `after ${N.NEW_SAFE.days} days: finalized, the wallet alone, 1 of 1`);
} catch (e) { check(false, e.shortMessage || e.message); } finally { anvil.kill(); }
console.log(failed ? `${failed} failed` : "all pass");
process.exit(failed ? 1 : 0);
