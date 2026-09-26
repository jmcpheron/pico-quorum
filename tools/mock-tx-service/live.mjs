// tools/quorum live: the console's key on a real chain (Base Sepolia, Base, Ethereum), next to Safe's
// own web app and transaction service. The runbook is docs/LADDER.md.
//
//   live key [--from URL | --usb | --emu | --qx 0x.. --qy 0x..]
//                       read the console's P-256 key and print its owner address (its signer proxy).
//                       --from: a tools/quorum service the console announced to (default :8787);
//                       --usb: ask the Pico over USB (tools/usb); --emu: the emulator's virtual chip.
//                       Kept in live.json (gitignored), public values only.
//   live enroll --chain basesep|base|eth
//                       deploy the key's signer proxy with the passkey factory (createSigner)
//   live status --chain C [--safe 0x..]       the Safe, its owners and queue, from the service and onchain
//   live exec --chain C NONCE|SAFE_TX_HASH [--safe 0x..]
//                       execute a transaction with every confirmation laid out right. The Safe web app
//                       can't: it drops a contract signature's data when there are two or more (GS021).
//   live rehearse --chain C [--safe 0x..]
//                       the console on the emulator, with its throwaway virtual chip (live key --emu),
//                       against the real service: it opens the first transaction waiting for it, pages
//                       through, holds A, and the service's answer is printed. The spike before the Pico.
//   live pico --chain C [--safe 0x..] [--name NAME]
//                       point the Pico's console at chain C: the board's secrets.py gets that chain's
//                       service and its pinned Safe (QUORUM_URL, QUORUM_SAFE), the old file is kept as
//                       secrets.bak, and the console restarts. The API key and everything else stay.
//                       --chain local: tools/quorum on this Mac (the fork or the simulation), no QUORUM_SAFE.
//   --chain local       the rehearsal against tools/quorum up --manual-exec (the fork, anvil's account 0;
//                       --browser uses the wallet page there too, with a wallet pointed at the fork)
//
// Nothing here holds a private key. A write is sent by your browser wallet, the one that co-signs in
// the Safe web app: live serves a one-page form on 127.0.0.1:8790, and the wallet shows the
// transaction and asks. Or --account NAME [--password-file F] sends it with `cast send` from a
// Foundry keystore (~/.foundry/keystores) after you type yes (--yes skips that on Base Sepolia,
// never on Base or Ethereum). Either way the terminal first shows the destination, the value, what it does and
// the estimated cost, and every send is logged in live.json.
// The Safe API key (developer.safe.global) goes to the service as a bearer token: SAFE_API_KEY, from
// the repo's gitignored .env (cli.mjs loads it) or the shell. Without one the service allows only
// a few thousand requests a month.
import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline/promises";
import { fileURLToPath } from "node:url";
import {
  createPublicClient, encodeFunctionData, formatEther, getAddress, hashMessage, http, recoverAddress, size, slice, toHex,
} from "viem";
import { base, baseSepolia, foundry, mainnet } from "viem/chains";
import { CFG, safeTxHash } from "./sim.mjs";
import { ERC1271_ABI, EXECUTOR, PASSKEY_ABI, SAFE_ABI, execArgs, reason } from "./chain.mjs";
import { foundryBin } from "./fork.mjs";
import { p256Owner, packSignatures, parse } from "./sigs.mjs";

export const CHAINS = {
  basesep: { chain: baseSepolia, rpc: process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org",
             service: "https://api.safe.global/tx-service/basesep", explorer: "https://sepolia.basescan.org" },
  base: { chain: base, rpc: process.env.BASE_RPC || "https://mainnet.base.org",
          service: "https://api.safe.global/tx-service/base", explorer: "https://basescan.org", real: true },
  eth: { chain: mainnet, rpc: process.env.ETH_RPC || "https://ethereum-rpc.publicnode.com",
         service: "https://api.safe.global/tx-service/eth", explorer: "https://etherscan.io", real: true },
  // The rehearsal: tools/quorum up --manual-exec. Same commands, the fork and the local service,
  // and anvil's unlocked account 0 instead of a keystore.
  local: { chain: { ...foundry, name: "the Base fork (local)" }, rpc: `http://127.0.0.1:${process.env.QUORUM_ANVIL_PORT || 8545}`,
           service: `http://localhost:${process.env.QUORUM_PORT || 8787}`, explorer: null, unlocked: EXECUTOR.address },
};
const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const LIVE_FILE = fileURLToPath(new URL("live.json", import.meta.url));
const MAGIC = "0x1626ba7e";

const [, ...rest] = process.argv.slice(2);
const sub = rest[0];
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const flag = (k) => rest.includes(k);
const BOOLEAN = ["--usb", "--emu", "--yes", "--no-open", "--browser"];
const words = rest.slice(1).filter((w, i, a) => !w.startsWith("--") && !(i > 0 && a[i - 1].startsWith("--") && !BOOLEAN.includes(a[i - 1])));

function die(msg) {
  console.error(msg);
  process.exit(1);
}

const API_KEY = (process.env.SAFE_API_KEY || "").trim();

const link = (n, kind, x) => (n.explorer ? `${n.explorer}/${kind}/${x}` : x);

const saved = () => (existsSync(LIVE_FILE) ? JSON.parse(readFileSync(LIVE_FILE, "utf8")) : { safes: {} });
const keep = (live) => writeFileSync(LIVE_FILE, JSON.stringify(live, null, 2) + "\n");

function net() {
  const name = opt("--chain");
  if (!CHAINS[name]) die(`--chain ${Object.keys(CHAINS).join(" | ")}`);
  if (name !== "local" && !API_KEY) console.error("(no SAFE_API_KEY in .env: the service allows a few thousand requests a month without one)");
  const c = CHAINS[name];
  return { name, ...c, pub: createPublicClient({ chain: c.chain, transport: http(c.rpc) }) };
}

function theKey() {
  const qx = opt("--qx") || saved().key?.qx;
  const qy = opt("--qy") || saved().key?.qy;
  if (!qx || !qy) die("no key yet: run  tools/quorum live key  first (or pass --qx and --qy)");
  return { qx, qy, owner: p256Owner(CFG.signer, qx, qy) };
}

async function service(n, path) {
  const headers = API_KEY && n.name !== "local" ? { Authorization: "Bearer " + API_KEY } : {};
  const r = await fetch(n.service + path, { headers });
  if (r.status === 404) return null;
  if (!r.ok) die(`${n.service}${path}: HTTP ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

function theSafe(n) {
  const a = opt("--safe") || saved().safes?.[n.name];
  if (!a) die(`which Safe? pass --safe 0x.. once and it is kept in live.json`);
  if (opt("--safe")) {
    const live = saved();
    live.safes = { ...live.safes, [n.name]: getAddress(a) };
    keep(live);
  }
  return getAddress(a);
}

// ----------------------------------------------------------------------------- sending
// tx: {to, data, value (bigint), what}. Shows it, has it signed (the browser wallet, a keystore, or
// anvil's unlocked account on the fork), waits for the receipt, logs it. -> the receipt.
async function send(n, tx) {
  const to = getAddress(tx.to);
  const [gas, price] = await Promise.all([
    n.pub.estimateGas({ to, data: tx.data, value: tx.value, account: n.unlocked }).catch(() => null), n.pub.getGasPrice()]);
  console.log(`\n${tx.what}\n  chain   ${n.chain.name} (${n.chain.id})\n  to      ${to}\n  value   ${formatEther(tx.value)} ETH\n` +
    `  data    ${size(tx.data)} bytes\n  cost    ${gas ? `about ${gas} gas at ${Number(price) / 1e9} gwei = ${formatEther(gas * price)} ETH, plus a small L1 data fee` : "could not estimate (it may revert)"}`);
  let hash;
  if (flag("--browser")) {
    hash = await browserSend(n, { ...tx, to, gas });
  } else if (n.unlocked) {
    hash = castSend(n, to, tx, ["--unlocked", "--from", n.unlocked]);
  } else if (opt("--account")) {
    await yes(n);
    const pw = opt("--password-file");
    hash = castSend(n, to, tx, ["--account", opt("--account"), ...(pw ? ["--password-file", pw] : [])]);
  } else {
    hash = await browserSend(n, { ...tx, to, gas });
  }
  const receipt = await n.pub.waitForTransactionReceipt({ hash });
  const live = saved();
  live.history = [...(live.history || []), { when: new Date().toISOString(), chain: n.name, what: tx.what, tx: hash, status: receipt.status }];
  keep(live);
  if (receipt.status !== "success") die(`REVERTED: ${link(n, "tx", hash)}`);
  return receipt;
}

async function yes(n) {
  if (flag("--yes") && !n.real) return;
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const a = await rl.question(`Send it from keystore ${opt("--account")}? Type yes: `);
  rl.close();
  if (a.trim().toLowerCase() !== "yes") die("not sent");
}

function castSend(n, to, tx, who) {
  const bin = foundryBin("cast");
  if (!bin) die("no cast: foundryup -i v1.8.3");
  const r = spawnSync(bin, ["send", to, tx.data, "--value", tx.value.toString(), "--rpc-url", n.rpc, ...who, "--async"],
                      { stdio: ["inherit", "pipe", "inherit"], encoding: "utf8" });
  const hash = (r.stdout || "").trim().match(/0x[0-9a-fA-F]{64}/)?.[0];
  if (r.status !== 0 || !hash) die("cast send failed");
  return hash;
}

// One page on 127.0.0.1 hands the transaction to the browser's wallet (EIP-1193), which shows it
// and asks. The page reports the hash back; nothing else comes in.
async function browserSend(n, tx) {
  const port = Number(process.env.QUORUM_WALLET_PORT || 8790);
  const page = readFileSync(new URL("wallet.html", import.meta.url), "utf8");
  const body = JSON.stringify({ chainId: n.chain.id, chainName: n.chain.name, rpc: n.rpc, explorer: n.explorer, to: tx.to,
                                data: tx.data, value: toHex(tx.value), what: tx.what, gas: tx.gas ? toHex((tx.gas * 13n) / 10n) : null });
  return new Promise((resolve, reject) => {
    const server = createServer(async (req, res) => {
      if (req.method === "GET" && req.url === "/") return res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }).end(page);
      if (req.method === "GET" && req.url === "/tx") return res.writeHead(200, { "Content-Type": "application/json" }).end(body);
      if (req.method === "POST" && req.url === "/sent") {
        let raw = "";
        for await (const c of req) raw += c;
        let hash;
        try {
          hash = JSON.parse(raw).hash;
        } catch {}
        if (!/^0x[0-9a-fA-F]{64}$/.test(hash || "")) return res.writeHead(400).end();
        res.writeHead(200, { "Content-Type": "application/json" }).end("{}");
        server.close();
        console.log(`  sent from the browser wallet: ${link(n, "tx", hash)}`);
        return resolve(hash);
      }
      res.writeHead(404).end();
    });
    server.on("error", reject);
    server.listen(port, "127.0.0.1", () => {
      const url = `http://127.0.0.1:${port}/`;
      console.log(`\nOpen ${url} in the browser that has your wallet. Check it there, then send it from the wallet.`);
      if (!flag("--no-open")) spawn("open", [url], { stdio: "ignore" }).on("error", () => {});
    });
  });
}

// ----------------------------------------------------------------------------- key
async function key() {
  let qx, qy, source;
  if (opt("--qx")) {
    [qx, qy, source] = [opt("--qx"), opt("--qy"), "given"];
  } else if (flag("--usb")) {
    const code = `import sys
q = sys.modules.get("quorum")
if q and q.qx:
    print("KEY", q.qx, q.qy)
else:
    import signer
    x, y = signer.load().pubkey()
    print("KEY", "0x%064x" % x, "0x%064x" % y)`;
    const r = spawnSync(`${ROOT}tools/usb`, ["exec", code], { encoding: "utf8" });
    const m = (r.stdout || "").match(/KEY (0x[0-9a-f]{64}) (0x[0-9a-f]{64})/);
    if (!m) die(`the Pico did not answer with a key:\n${r.stdout}${r.stderr}`);
    [, qx, qy] = m;
    source = "usb";
  } else if (flag("--emu")) {
    const r = spawnSync(process.execPath, [`${ROOT}emu/headless.mjs`, "quorum", "--app", "http://localhost:1",
      "--chip", `${ROOT}tools/mock-tx-service/emu-chip.json`, "--wait", "1500", "--exec", "print('KEY', quorum.qx, quorum.qy)"],
    { cwd: `${ROOT}emu`, encoding: "utf8" });
    const m = (r.stdout || "").match(/KEY (0x[0-9a-f]{64}) (0x[0-9a-f]{64})/);
    if (!m) die(`the emulator did not print a key:\n${(r.stdout + r.stderr).slice(-600)}`);
    [, qx, qy] = m;
    source = "emu (emu-chip.json, a throwaway key)";
  } else {
    const from = opt("--from", `http://localhost:${process.env.QUORUM_PORT || 8787}`);
    let st;
    try {
      st = await (await fetch(from + "/sim/state")).json();
    } catch {
      die(`nothing answers at ${from}. Point the Pico at tools/quorum serve (it announces its key), or use --usb or --qx/--qy`);
    }
    const devices = st.owners.filter((o) => o.kind === "p256");
    if (devices.length !== 1) die(`${devices.length} consoles announced to ${from}; use --usb or --qx/--qy`);
    [qx, qy, source] = [devices[0].qx, devices[0].qy, `announced by ${devices[0].device} to ${from}`];
  }
  const owner = p256Owner(CFG.signer, qx, qy);
  const live = saved();
  live.key = { qx, qy, owner, source, fingerprint: qx.slice(2, 10) };
  keep(live);
  console.log(`key ${qx.slice(2, 10)} (${source})\n  qx ${qx}\n  qy ${qy}\nowner address (its signer proxy, the same on every chain): ${owner}`);
  console.log("check it against the Pico: B on the home screen, This key.");
}

// ----------------------------------------------------------------------------- enroll
async function enroll() {
  const n = net();
  const k = theKey();
  const args = [BigInt(k.qx), BigInt(k.qy), BigInt(CFG.signer.verifiers)];
  const onchain = getAddress(await n.pub.readContract({ address: CFG.signer.factory, abi: PASSKEY_ABI, functionName: "getSigner", args }));
  if (onchain !== k.owner) die(`the factory on ${n.chain.name} says ${onchain}, the console's rule says ${k.owner}: stop and find out why`);
  if (await n.pub.getCode({ address: k.owner })) {
    console.log(`${k.owner} is already deployed on ${n.chain.name}: ${link(n, "address", k.owner)}`);
    return;
  }
  const receipt = await send(n, {
    to: CFG.signer.factory, value: 0n, data: encodeFunctionData({ abi: PASSKEY_ABI, functionName: "createSigner", args }),
    what: `Deploy the signer proxy for key ${k.qx.slice(2, 10)}: Safe's passkey factory createSigner, making ${k.owner}. Moves no funds.`,
  });
  // A public RPC is several servers behind a load balancer, and the one that answers getCode can be
  // a block behind the one that returned the receipt (seen on mainnet.base.org), so ask a few times.
  let code;
  for (let i = 0; i < 10 && !code; i++) {
    code = await n.pub.getCode({ address: k.owner });
    if (!code) await new Promise((r) => setTimeout(r, 1500));
  }
  if (!code) die(`sent (${receipt.transactionHash}) but no code at ${k.owner} after 15 s: check ${link(n, "address", k.owner)}`);
  console.log(`deployed: ${link(n, "tx", receipt.transactionHash)}\nowner to add in the Safe web app: ${k.owner}`);
}

// ----------------------------------------------------------------------------- the Safe and its queue
async function checked(n, safe, t, info) {
  const f = { to: t.to, value: t.value, data: t.data || "0x", operation: t.operation, safeTxGas: t.safeTxGas, baseGas: t.baseGas,
              gasPrice: t.gasPrice, gasToken: t.gasToken, refundReceiver: t.refundReceiver, nonce: t.nonce };
  const mine = safeTxHash(n.chain.id, safe, f);
  const problems = [];
  if (mine !== t.safeTxHash) problems.push(`the service's hash ${t.safeTxHash} is not the fields' hash ${mine}`);
  const onchain = await n.pub.readContract({ address: safe, abi: SAFE_ABI, functionName: "getTransactionHash", args: [
    getAddress(f.to), BigInt(f.value), f.data, Number(f.operation), BigInt(f.safeTxGas), BigInt(f.baseGas), BigInt(f.gasPrice),
    getAddress(f.gasToken), getAddress(f.refundReceiver), BigInt(f.nonce)] });
  if (onchain !== mine) problems.push(`the Safe hashes it to ${onchain}`);
  const owners = info.owners.map((a) => getAddress(a));
  const good = [];
  for (const c of t.confirmations || []) {
    const who = getAddress(c.owner);
    let ok = false;
    let kind = "?";
    try {
      const p = parse(c.signature);
      kind = p.kind;
      if (p.kind === "contract") {
        ok = p.owner === who && (await n.pub.readContract({ address: who, abi: ERC1271_ABI, functionName: "isValidSignature", args: [mine, p.data] }).catch(() => "")) === MAGIC;
      } else if (p.kind === "ecdsa") {
        const v = Number(BigInt(slice(c.signature, 64, 65)));
        const signed = v > 30 ? await recoverAddress({ hash: hashMessage({ raw: mine }), signature: slice(c.signature, 0, 64) + toHex(v - 4, { size: 1 }).slice(2) })
                              : await recoverAddress({ hash: mine, signature: c.signature });
        ok = signed === who;
      } else if (p.kind === "approved") {
        ok = true;      // approveHash onchain: the Safe checks approvedHashes itself
      }
    } catch (e) {
      kind = e.message;
    }
    if (!owners.includes(who)) ok = false;
    good.push({ owner: who, signature: c.signature, ok, kind });
  }
  return { mine, problems, good };
}

async function status() {
  const n = net();
  const safe = theSafe(n);
  const info = await service(n, `/api/v1/safes/${safe}/`);
  if (!info) die(`${n.service} does not know ${safe} on ${n.chain.name}`);
  const me = saved().key?.owner;
  console.log(`${safe} on ${n.chain.name}: v${info.version}, nonce ${info.nonce}, ${info.threshold} of ${info.owners.length}`);
  console.log(`  balance ${(Number(await n.pub.getBalance({ address: safe })) / 1e18).toFixed(6)} ETH   ${link(n, "address", safe)}`);
  for (const o of info.owners) console.log(`  owner ${o}${me && getAddress(o) === getAddress(me) ? "  <- this console's key" : ""}`);
  if (me && !info.owners.map((a) => getAddress(a)).includes(getAddress(me))) console.log(`  (this console's key ${me} is not an owner)`);
  const q = await service(n, `/api/v2/safes/${safe}/multisig-transactions/?executed=false&nonce__gte=${info.nonce}&ordering=nonce&limit=10`);
  if (!q.results.length) console.log("queue: empty");
  for (const t of q.results) {
    const c = await checked(n, safe, t, info);
    const valid = c.good.filter((g) => g.ok).length;
    console.log(`  #${t.nonce} ${t.safeTxHash.slice(0, 10)}..${t.safeTxHash.slice(-8)}  ${valid}/${info.threshold} valid` +
      `${c.good.length > valid ? ` (${c.good.length - valid} not)` : ""}${me && c.good.some((g) => g.owner === getAddress(me)) ? ", signed by this console" : ""}` +
      `${c.problems.length ? "  !! " + c.problems.join("; ") : ""}`);
  }
}

async function exec() {
  const n = net();
  const safe = theSafe(n);
  const ref = words[0];
  if (!ref) die("which transaction? a nonce or a safeTxHash");
  const info = await service(n, `/api/v1/safes/${safe}/`);
  let t;
  if (/^0x[0-9a-fA-F]{64}$/.test(ref)) {
    t = await service(n, `/api/v1/multisig-transactions/${ref}/`);
  } else {
    const q = await service(n, `/api/v2/safes/${safe}/multisig-transactions/?executed=false&nonce=${Number(ref)}`);
    if (q.results.length > 1) die(`${q.results.length} transactions share nonce ${ref}: pass the safeTxHash`);
    t = q.results[0];
  }
  if (!t) die(`no such transaction for ${safe}`);
  if (getAddress(t.safe) !== safe) die(`that transaction is for ${t.safe}`);
  if (t.isExecuted) die(`already executed: ${link(n, "tx", t.transactionHash)}`);
  if (Number(t.nonce) !== Number(info.nonce)) die(`it is #${t.nonce}; the Safe is at nonce ${info.nonce}, so that one goes first`);
  const c = await checked(n, safe, t, info);
  if (c.problems.length) die(c.problems.join("\n"));
  for (const g of c.good) console.log(`  ${g.ok ? "valid  " : "INVALID"} ${g.kind.padEnd(8)} ${g.owner}`);
  const valid = c.good.filter((g) => g.ok);
  if (valid.length < Number(info.threshold)) die(`${valid.length} valid of ${info.threshold} needed`);
  const signatures = packSignatures(valid.slice(0, Number(info.threshold)));
  const args = execArgs(t, signatures);
  try {
    await n.pub.simulateContract({ address: safe, abi: SAFE_ABI, functionName: "execTransaction", args });
  } catch (e) {
    die(`it would revert: ${reason(e)}`);
  }
  const moves = `${formatEther(BigInt(t.value))} ETH to ${getAddress(t.to)}${t.data && t.data !== "0x" ? ` with ${size(t.data)} bytes of call data` : ""}`;
  const receipt = await send(n, {
    to: safe, value: 0n, data: encodeFunctionData({ abi: SAFE_ABI, functionName: "execTransaction", args }),
    what: `Execute Safe transaction #${t.nonce} (${c.mine.slice(0, 10)}..${c.mine.slice(-8)}) on ${safe}: the Safe sends ${moves}. ` +
          `${valid.length} of ${info.threshold} confirmations checked here.`,
  });
  console.log(`executed: ${link(n, "tx", receipt.transactionHash)}`);
}

// ----------------------------------------------------------------------------- rehearse
async function rehearse() {
  const n = net();
  const safe = theSafe(n);
  const k = theKey();
  if (!String(saved().key?.source || "").startsWith("emu")) die("the saved key is not the emulator's: run  tools/quorum live key --emu  first");
  const dir = mkdtempSync(join(tmpdir(), "quorum-rehearse-"));
  const secrets = join(dir, "live_secrets.py");
  writeFileSync(secrets, [`QUORUM_URL = ${JSON.stringify(n.service)}`,
    `QUORUM_SAFE = {"chainId": ${n.chain.id}, "address": ${JSON.stringify(safe.toLowerCase())}, "name": "Rehearsal"}`,
    API_KEY && n.name !== "local" ? `QUORUM_API_KEY = ${JSON.stringify(API_KEY)}` : "", "QUORUM_POLL_S = 30", ""].join("\n"));
  const chip = join(dir, "chip.json");
  copyFileSync(new URL("emu-chip.json", import.meta.url), chip);
  const [home, signed] = [join(dir, "1-queue.png"), join(dir, "2-after-signing.png")];
  console.log(`the emulator's console, key ${k.qx.slice(2, 10)} (owner ${k.owner}), against ${n.service} for ${safe}...`);
  const r = spawnSync(process.execPath, [`${ROOT}emu/headless.mjs`, "quorum", "--secrets", secrets, "--chip", chip, "--quiet",
    "--wait", "9000", "--shot", home, "--key", "A", "--wait", "400",
    ...Array(8).fill(["--key", "down", "--wait", "250"]).flat(),                      // every page, so A may sign
    "--hold", "A", "--wait", "3400", "--release", "A", "--wait", "9000", "--shot", signed], { cwd: `${ROOT}emu`, encoding: "utf8" });
  rmSync(secrets);                      // it holds the API key
  if (r.status !== 0 || /Traceback/.test(r.stdout + r.stderr)) die(`the emulator failed:\n${(r.stdout + r.stderr).slice(-800)}`);
  const info = await service(n, `/api/v1/safes/${safe}/`);
  const q = await service(n, `/api/v2/safes/${safe}/multisig-transactions/?executed=false&nonce__gte=${info.nonce}&ordering=nonce&limit=10`);
  const mine = q.results.filter((t) => (t.confirmations || []).some((c) => getAddress(c.owner) === k.owner));
  console.log(`screens: ${home}\n         ${signed}`);
  if (!mine.length) die("the service has no confirmation from this key yet: look at the screens");
  for (const t of mine) console.log(`the service holds this key's confirmation on #${t.nonce} ${t.safeTxHash}: ${t.confirmations.length} of ${t.confirmationsRequired}`);
  console.log(`next: tools/quorum live exec --chain ${n.name} ${mine[0].nonce}`);
}

// ----------------------------------------------------------------------------- pico
async function pico() {
  const name = opt("--chain");
  if (!CHAINS[name]) die(`--chain ${Object.keys(CHAINS).join(" | ")}`);
  const n = CHAINS[name];
  let url, safeLine = null;
  if (name === "local") {
    const ip = spawnSync("ipconfig", ["getifaddr", "en0"], { encoding: "utf8" }).stdout.trim();
    if (!ip) die("no LAN address on en0 for the Pico to reach this Mac");
    url = `http://${ip}:${process.env.QUORUM_PORT || 8787}`;
  } else {
    const safe = theSafe({ ...n, name });
    const label = opt("--name") || saved().names?.[name] || `${n.chain.name} Safe`;
    const live = saved();
    live.names = { ...live.names, [name]: label };
    keep(live);
    url = n.service;
    safeLine = `QUORUM_SAFE = ${JSON.stringify({ chainId: n.chain.id, address: safe.toLowerCase(), name: label })}`;
  }
  const lines = [`QUORUM_URL = ${JSON.stringify(url)}`, ...(safeLine ? [safeLine] : [])];
  console.log(`the Pico's console, to ${n.chain.name}:\n  ${lines.join("\n  ")}`);
  const code = `import os
new = ${JSON.stringify(lines.join("\n"))}
with open('secrets.py') as f:
    old = f.read()
with open('secrets.bak', 'w') as f:
    f.write(old)
keep = [l for l in old.split(chr(10)) if l.split('=')[0].strip() not in ('QUORUM_URL', 'QUORUM_SAFE') and not l.startswith('# Base Sepolia (docs/LADDER.md') and not l.startswith('# the network, written by')]
while keep and not keep[-1].strip():
    keep.pop()
with open('secrets.py', 'w') as f:
    f.write(chr(10).join(keep) + chr(10) + '# the network, written by tools/quorum live pico' + chr(10) + new + chr(10))
if hasattr(os, 'sync'): os.sync()
print('WROTE', len(old), '->', os.stat('secrets.py')[6], 'bytes; the old file is secrets.bak')`;
  let r = spawnSync(`${ROOT}tools/usb`, ["exec", code], { encoding: "utf8" });
  const wrote = (r.stdout || "").match(/WROTE .*/);
  if (!wrote) die(`the board did not take it:\n${r.stdout}${r.stderr}`);
  console.log("  " + wrote[0]);
  console.log("restarting the console...");
  // A production image (tools/fw push) starts the console itself at power-up: a reset is the
  // restart. A development board gets the console shipped and started, as before.
  const main = spawnSync(`${ROOT}tools/usb`, ["exec", "print('MAIN', open('main.py').read()[:60])"], { encoding: "utf8" }).stdout || "";
  if (/picoquorum-image: console/.test(main)) {
    // then hands off for 30 s: any mpremote command starts with Ctrl-C, which would stop the
    // console mid-start (tools/fw restart, 2026-09-26)
    spawnSync(`${ROOT}tools/usb`, ["exec", "import machine; machine.reset()"], { encoding: "utf8", timeout: 10000 });
    await new Promise((res) => setTimeout(res, 30000));
  } else {
    r = spawnSync(`${ROOT}tools/emu`, ["ship", "quorum"], { encoding: "utf8", timeout: 180000 });
    if (!/running quorum/.test(r.stdout + r.stderr)) die(`the restart did not report back:\n${(r.stdout + r.stderr).slice(-600)}`);
  }
  const check = "import quorum; print('NOW', quorum.CHAIN, quorum.SAFE_ADDR, quorum.SAFE.get('name'), quorum.BASE, 'net', quorum.net_ok, quorum.net_err, 'nonce', quorum.info.get('nonce'), 'me-owner', quorum.me in quorum.owners())";
  for (let i = 0; i < 12; i++) {
    await new Promise((res) => setTimeout(res, 5000));
    r = spawnSync(`${ROOT}tools/usb`, ["exec", check], { encoding: "utf8" });
    const now = (r.stdout || "").match(/NOW .*/);
    if (now && / net True /.test(now[0])) return console.log("  " + now[0]);
    if (i === 11) console.log("  " + (now ? now[0] : "no answer from the board") + "\n  (still joining WiFi or the service? it keeps trying)");
  }
}

const cmds = { key, enroll, status, exec, rehearse, pico };
if (!cmds[sub]) die("usage: tools/quorum live key | enroll | status | rehearse | exec | pico   (see tools/mock-tx-service/live.mjs)");
await cmds[sub]();
