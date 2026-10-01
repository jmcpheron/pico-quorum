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
//   live propose --chain C WHAT --by console|browser | --account NAME [--nonce N] [--dry-run]
//                       start a transaction without the Safe web app (propose.mjs, docs/guide/PROPOSING.md).
//                       WHAT: send TO ETH | call TO DATA [--value ETH] | swap-owner OLD NEW [OLD NEW..] |
//                       add-owner NEW [--threshold N] | remove-owner OLD [--threshold N] | threshold N | reject NONCE.
//                       --account/--browser: an owner's wallet or a delegate's signs it, and it goes to the service.
//                       --by console: this laptop serves it to consoles on the LAN (live pico --stage points
//                       one here); the first console signature goes to the service as the proposal, and
//                       --collect forwards the rest. --by console --no-service: never ask Safe's service;
//                       collect the consoles' signatures here and execute at the threshold.
//                       --chain local only: --by alice|bob, the simulated owners.
//   live delegate list|add DELEGATE [--label L]|remove DELEGATE --chain C (--account NAME | --browser)
//                       a delegate may propose but never sign; an owner's ordinary wallet adds or removes one
//   live pico --chain C[,C..] [--safe 0x..] [--name NAME]   several chains: a Safe on each (QUORUM_SAFES);
//                       one chain: --safe A,B[,..] --name N1,N2[,..] watches several Safes there (up to 4)
//                       point the Pico's console at chain C (or several): the board's secrets.py gets
//                       each chain's pinned Safe (QUORUM_SAFES; the console finds each chain's service
//                       itself), the old file is kept as secrets.bak, and the console restarts. The API key and everything else stay.
//                       --chain local: tools/quorum on this Mac (the fork or the simulation), no QUORUM_SAFE.
//                       --stage (one chain): the Safe is asked about at this laptop's live propose --by
//                       console instead of Safe's service; run it again without --stage to point back.
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
import { networkInterfaces, tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline/promises";
import { fileURLToPath } from "node:url";
import {
  createPublicClient, encodeFunctionData, formatEther, getAddress, hashTypedData, http, isAddress, recoverAddress, size, toHex,
} from "viem";
import { base, baseSepolia, foundry, mainnet } from "viem/chains";
import { CFG, PEOPLE, delegateTypedData, safeTxHash } from "./sim.mjs";
import { EXECUTOR, PASSKEY_ABI, SAFE_ABI, execArgs, reason } from "./chain.mjs";
import { foundryBin } from "./fork.mjs";
import { p256Owner, packSignatures, parse } from "./sigs.mjs";
import { KINDS, Stage, build, fields, proposalBody, safeOnchain, safeTxTypedData, signerOf, typedJson } from "./propose.mjs";

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
const LIVE_FILE = process.env.QUORUM_LIVE_FILE || fileURLToPath(new URL("live.json", import.meta.url));

const [, ...rest] = process.argv.slice(2);
const sub = rest[0];
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const flag = (k) => rest.includes(k);
const BOOLEAN = ["--usb", "--emu", "--yes", "--no-open", "--browser", "--no-service", "--collect", "--dry-run", "--stage"];
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

// A write to the service: -> [status, parsed body].
async function servicePost(n, path, body, method = "POST") {
  const headers = { "content-type": "application/json", ...(API_KEY && n.name !== "local" ? { Authorization: "Bearer " + API_KEY } : {}) };
  let r;
  try {
    r = await fetch(n.service + path, { method, headers, body: JSON.stringify(body) });
  } catch (e) {
    return [0, { detail: `${n.service} did not answer: ${e.cause?.code || e.message}` }];
  }
  const text = await r.text();
  let out;
  try {
    out = text ? JSON.parse(text) : {};
  } catch {
    out = { detail: text.slice(0, 200) };
  }
  return [r.status, out];
}

// The service's complaint in one line ({"nonFieldErrors": [..]}, {"detail": ..}, {"field": [..]}).
const complaint = (out) => (out.detail || out.nonFieldErrors?.[0] || Object.entries(out).map(([k, v]) => `${k}: ${[v].flat()[0]}`)[0] || "").toString();

// This computer's address on the LAN, for a Pico to reach: en0/en1 on a Mac, else the first
// non-internal IPv4 interface.
function lanIp() {
  for (const ifc of ["en0", "en1"]) {
    const ip = spawnSync("ipconfig", ["getifaddr", ifc], { encoding: "utf8" }).stdout?.trim();
    if (ip) return ip;
  }
  for (const list of Object.values(networkInterfaces())) {
    for (const a of list || []) if (a.family === "IPv4" && !a.internal) return a.address;
  }
  return "";
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
      kind = parse(c.signature).kind;
      if (kind === "approved") ok = true;      // approveHash onchain: the Safe checks approvedHashes itself
      else ok = (await signerOf(n.pub, mine, c.signature)).owner === who;
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
  await executeWith(n, safe, t, c.mine, c.good.filter((g) => g.ok), Number(info.threshold));
}

// execTransaction with the first `threshold` of these checked confirmations, laid out right.
async function executeWith(n, safe, t, hash, valid, threshold) {
  if (valid.length < threshold) die(`${valid.length} valid of ${threshold} needed`);
  const args = execArgs(t, packSignatures(valid.slice(0, threshold)));
  try {
    await n.pub.simulateContract({ address: safe, abi: SAFE_ABI, functionName: "execTransaction", args });
  } catch (e) {
    die(`it would revert: ${reason(e)}`);
  }
  const moves = `${formatEther(BigInt(t.value))} ETH to ${getAddress(t.to)}${t.data && t.data !== "0x" ? ` with ${size(t.data)} bytes of call data` : ""}`;
  const receipt = await send(n, {
    to: safe, value: 0n, data: encodeFunctionData({ abi: SAFE_ABI, functionName: "execTransaction", args }),
    what: `Execute Safe transaction #${t.nonce} (${hash.slice(0, 10)}..${hash.slice(-8)}) on ${safe}: the Safe sends ${moves}. ` +
          `${valid.length} of ${threshold} confirmations checked here.`,
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

// ----------------------------------------------------------------------------- propose
// Someone other than the Safe web app signs: the simulated owners on the fork, a Foundry keystore
// (an owner or a delegate), or the browser's wallet. typed: EIP-712 data with bigints.
// -> {signer, signature}, the signer recovered from the signature itself.
async function signTyped(n, typed, what, rows) {
  const hash = hashTypedData(typed);
  const by = opt("--by");
  let signature;
  if (n.name === "local" && PEOPLE[by]) {
    signature = await PEOPLE[by].sign({ hash });
  } else if (opt("--account")) {
    const bin = foundryBin("cast");
    if (!bin) die("no cast: foundryup -i v1.8.3");
    const pw = opt("--password-file");
    console.log(`\nsigning with keystore ${opt("--account")} (it signs ${hash}; nothing is sent onchain)`);
    const r = spawnSync(bin, ["wallet", "sign", "--no-hash", hash, "--account", opt("--account"), ...(pw ? ["--password-file", pw] : [])],
                        { stdio: ["inherit", "pipe", "inherit"], encoding: "utf8" });
    signature = (r.stdout || "").trim().match(/0x[0-9a-fA-F]{130}/)?.[0];
    if (r.status !== 0 || !signature) die("cast wallet sign failed");
  } else if (by === "browser" || flag("--browser")) {
    signature = await browserSign(n, typed, what, rows);
  } else {
    die(`who signs? --account NAME (a Foundry keystore) | --browser${n.name === "local" ? " | --by alice|bob" : ""}`);
  }
  return { signer: await recoverAddress({ hash, signature }), signature };
}

// The browser's wallet signs typed data (eth_signTypedData_v4) on a page on 127.0.0.1, as
// browserSend has it send a transaction. -> the signature.
async function browserSign(n, typed, what, rows) {
  const port = Number(process.env.QUORUM_WALLET_PORT || 8790);
  const page = readFileSync(new URL("sign.html", import.meta.url), "utf8");
  const body = JSON.stringify({ chainId: n.chain.id, chainName: n.chain.name, rpc: n.rpc, explorer: n.explorer, what, rows, typedData: typedJson(typed) });
  const hash = hashTypedData(typed);
  return new Promise((resolve, reject) => {
    const server = createServer(async (req, res) => {
      if (req.method === "GET" && req.url === "/") return res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }).end(page);
      if (req.method === "GET" && req.url === "/req") return res.writeHead(200, { "Content-Type": "application/json" }).end(body);
      if (req.method === "POST" && req.url === "/signed") {
        let raw = "";
        for await (const c of req) raw += c;
        let got = {};
        try {
          got = JSON.parse(raw);
        } catch {}
        const signer = /^0x[0-9a-fA-F]{130}$/.test(got.signature || "") ? await recoverAddress({ hash, signature: got.signature }).catch(() => null) : null;
        if (!signer || !isAddress(got.account || "") || signer !== getAddress(got.account)) {
          return res.writeHead(400, { "Content-Type": "application/json" }).end(JSON.stringify({ error: "the signature is not that account's" }));
        }
        res.writeHead(200, { "Content-Type": "application/json" }).end("{}");
        server.close();
        console.log(`  signed in the browser by ${signer}`);
        return resolve(got.signature);
      }
      res.writeHead(404).end();
    });
    server.on("error", reject);
    server.listen(port, "127.0.0.1", () => {
      const url = `http://127.0.0.1:${port}/`;
      console.log(`\nOpen ${url} in the browser that has your wallet, check it there, and sign. Signing sends nothing onchain.`);
      if (!flag("--no-open")) spawn("open", [url], { stdio: "ignore" }).on("error", () => {});
    });
  });
}

async function propose() {
  const n = net();
  const safe = theSafe(n);
  const byConsole = opt("--by") === "console";
  const noService = flag("--no-service");
  if (noService && !byConsole) die("--no-service goes with --by console: with no service, the consoles sign at this laptop");
  if (!words.length) die(`what to propose?\n  ${Object.values(KINDS).join("\n  ")}`);
  const info = await safeOnchain(n.pub, safe);
  let call;
  try {
    call = build(words, info, { value: opt("--value"), threshold: opt("--threshold") });
  } catch (e) {
    die(e.message);
  }
  // The nonce: the one given, or the next free one: after the Safe's own and after the service's queue.
  let nonce = call.nonce ?? (opt("--nonce") !== undefined ? Number(opt("--nonce")) : info.nonce);
  let waiting = [];
  if (!noService) {
    const q = await service(n, `/api/v2/safes/${safe}/multisig-transactions/?executed=false&nonce__gte=${info.nonce}&ordering=nonce&limit=20`);
    if (!q) die(`${n.service} does not know ${safe}. Add it in the Safe web app, or use --by console --no-service`);
    waiting = q.results;
    if (call.nonce === undefined && opt("--nonce") === undefined && waiting.length) nonce = Math.max(...waiting.map((t) => Number(t.nonce))) + 1;
  }
  if (!Number.isInteger(nonce) || nonce < info.nonce) die(`nonce ${nonce}: the Safe is at ${info.nonce}, so anything below is spent`);
  const f = fields(call, nonce);
  const hash = safeTxHash(n.chain.id, safe, f);
  const onchain = await n.pub.readContract({ address: safe, abi: SAFE_ABI, functionName: "getTransactionHash", args: [
    f.to, BigInt(f.value), f.data, f.operation, 0n, 0n, 0n, f.gasToken, f.refundReceiver, BigInt(f.nonce)] });
  if (onchain !== hash) die(`the Safe hashes it to ${onchain}, this tool to ${hash}: stop and find out why`);
  const code = hash.slice(-8);
  const rows = [["Safe", `${safe} on ${n.chain.name}, ${info.threshold} of ${info.owners.length}`], ["To", f.to],
                ["Value", `${formatEther(BigInt(f.value))} ETH`], ["Data", `${size(f.data)} bytes`],
                ["Operation", f.operation ? "delegatecall (MultiSend)" : "call"], ["Nonce", String(nonce)], ["safeTxHash", hash], ["Verify code", code]];
  console.log(`\n${call.what}\n${rows.map(([k, v]) => `  ${k.padEnd(11)} ${v}`).join("\n")}`);
  for (const t of waiting.filter((t) => Number(t.nonce) === nonce)) {
    console.log(`  !! #${nonce} already waits in the queue (${t.safeTxHash.slice(0, 10)}..): only one of them can ever execute`);
  }
  if (flag("--dry-run")) return console.log("\n--dry-run: nothing signed, nothing sent");

  if (byConsole) return proposeByConsole(n, safe, f, hash, info, noService);

  const { signer, signature } = await signTyped(n, safeTxTypedData(n.chain.id, safe, f), call.what, rows);
  const owner = info.owners.includes(signer);
  console.log(`  ${signer} signed it: ${owner ? `an owner, so it counts as 1 of ${info.threshold}` : "not an owner, so the service takes it only from a delegate, and it counts for nothing"}`);
  await submit(n, safe, f, hash, signer, signature);
  console.log(`\nqueued #${nonce}. Consoles show it at their next poll, verify code ${code}.\n` +
              `When ${info.threshold} have signed: tools/quorum live exec --chain ${n.name} ${nonce}`);
}

async function submit(n, safe, f, hash, sender, signature) {
  const [status, out] = await servicePost(n, `/api/v1/safes/${safe}/multisig-transactions/`, proposalBody(safe, f, hash, sender, signature));
  if (status !== 201 && status !== 200) die(`the service refused the proposal (HTTP ${status}): ${complaint(out)}`);
  console.log(`  ${n.service} took the proposal from ${sender}`);
}

// The console path: this laptop is Safe's service for this one transaction, on the LAN. Every
// confirmation is checked onchain as it arrives and kept in live.json, so a restart with the same
// command picks them up again.
async function proposeByConsole(n, safe, f, hash, info, noService) {
  const port = Number(process.env.QUORUM_STAGE_PORT || 8791);
  const remember = (t) => {
    const live = saved();
    live.staged = { ...live.staged, [hash]: { chain: n.name, safe, fields: f, confirmations: t.confirmations } };
    keep(live);
  };
  const stage = new Stage({ pub: n.pub, safe, port, onChange: remember });
  const kept = (saved().staged?.[hash]?.confirmations || []).filter((c) => info.owners.includes(c.owner));
  const t = stage.add(f, hash, kept);
  try {
    await stage.start();
  } catch (e) {
    die(`can't serve on port ${port}: ${e.code || e.message} (QUORUM_STAGE_PORT picks another)`);
  }
  const url = `http://${lanIp() || "<this computer's LAN address>"}:${port}`;
  console.log(`\nServing it to consoles at ${url}${noService ? ". Safe's service is never asked." : ": Safe's service gets it once a console signs."}`);
  if (kept.length) console.log(`  ${kept.length} signature(s) kept from before (live.json)`);
  console.log(`Point a console here (a board on USB):  tools/quorum live pico --chain ${n.name} --stage` +
              `\n  or in its secrets.py: QUORUM_SAFES = [{"chainId": ${n.chain.id}, "address": "${safe.toLowerCase()}", "name": "Stage", "url": "${url}"}]` +
              `\nOn the console: open it, read every page, check the verify code ${hash.slice(-8)}, hold Sign.` +
              `\nAfterwards point it back:  tools/quorum live pico --chain ${n.name}\n`);
  const valid = () => t.confirmations.filter((c) => info.owners.includes(c.owner));
  const done = () => {
    stage.close();
    const live = saved();
    delete live.staged?.[hash];
    keep(live);
  };
  if (noService) {
    console.log(`waiting for ${info.threshold} signatures...`);
    await stage.until(() => valid().length >= info.threshold);
    stage.close();
    await executeWith(n, safe, t, hash, valid(), info.threshold);
    return done();
  }
  console.log("waiting for a console's signature...");
  await stage.until(() => valid().length >= 1);
  const [first, ...more] = valid();
  await submit(n, safe, f, hash, first.owner, first.signature);
  const sent = new Set([first.owner]);
  const forward = async () => {
    for (const c of valid().filter((c) => !sent.has(c.owner))) {
      const [status, out] = await servicePost(n, `/api/v1/multisig-transactions/${hash}/confirmations/`, { signature: c.signature });
      if (status === 201 || status === 200) console.log(`  forwarded ${c.owner}'s signature`);
      else console.log(`  !! the service refused ${c.owner}'s signature (HTTP ${status}): ${complaint(out)}`);
      sent.add(c.owner);
    }
  };
  if (more.length) await forward();
  if (flag("--collect")) {
    console.log(`--collect: forwarding each new signature until ${info.threshold}; Ctrl-C to stop`);
    await stage.until(async () => {
      await forward();
      return sent.size >= info.threshold;
    });
  }
  done();
  console.log(`\nqueued #${f.nonce} at Safe's service with ${sent.size} of ${info.threshold}. Point the console back:` +
              `  tools/quorum live pico --chain ${n.name}\nWhen ${info.threshold} have signed: tools/quorum live exec --chain ${n.name} ${f.nonce}`);
}

// ----------------------------------------------------------------------------- delegate
async function delegate() {
  const n = net();
  const safe = theSafe(n);
  const [verb, who] = words;
  if (verb === "list" || !verb) {
    const q = await service(n, `/api/v2/delegates/?safe=${safe}&limit=50`);
    if (!q?.results?.length) return console.log(`${safe} on ${n.chain.name}: no delegates`);
    for (const d of q.results) console.log(`  ${d.delegate}  added by ${d.delegator}${d.label ? `  "${d.label}"` : ""}${d.safe ? "" : "  (every Safe of that owner)"}`);
    return;
  }
  if (!["add", "remove"].includes(verb)) die("live delegate list | add DELEGATE [--label L] | remove DELEGATE");
  if (!isAddress(who || "")) die(`live delegate ${verb} DELEGATE: the delegate's address`);
  const d = getAddress(who);
  const info = await safeOnchain(n.pub, safe);
  if (verb === "add" && info.owners.includes(d)) die(`${d} is already an owner; a delegate is for an address that is not`);
  const what = verb === "add" ? `Let ${d} propose transactions for ${safe} (it can never sign one)` : `Stop ${d} proposing for ${safe}`;
  console.log(`\n${what}\n  the signature is good for this hour only, and moves nothing`);
  const { signer, signature } = await signTyped(n, delegateTypedData(n.chain.id, d), what,
    [["Safe", `${safe} on ${n.chain.name}`], ["Delegate", d], ["Signs", "an owner (to add), or the owner or the delegate (to remove)"]]);
  if (verb === "add" && !info.owners.includes(signer)) die(`${signer} is not an owner of ${safe}: only an owner adds a delegate`);
  const delegator = getAddress(opt("--delegator") || signer);
  const [status, out] = verb === "add"
    ? await servicePost(n, "/api/v2/delegates/", { safe, delegate: d, delegator, signature, label: opt("--label", "PicoQuorum proposer") })
    : await servicePost(n, `/api/v2/delegates/${d}/`, { safe, delegator, signature }, "DELETE");
  if (status < 200 || status > 299) die(`the service refused it (HTTP ${status}): ${complaint(out)}`);
  console.log(verb === "add" ? `${d} may now propose for ${safe}: tools/quorum live propose --chain ${n.name} ... --account <its keystore>`
                             : `${d} is no longer a delegate of ${safe}`);
}

// ----------------------------------------------------------------------------- pico
async function pico() {
  // --chain basesep,base,eth: the console watches a Safe on each (QUORUM_SAFES), each asked about
  // at its own chain's service (firmware/quorum_cfg.py "services"). local stands alone: the
  // laptop's service, at QUORUM_URL.
  const names = (opt("--chain") || "").split(",").filter(Boolean);
  if (!names.length || names.some((x) => !CHAINS[x])) die(`--chain ${Object.keys(CHAINS).join(" | ")}, or several: --chain basesep,base,eth`);
  if (names.includes("local") && names.length > 1) die("--chain local stands alone (the laptop's service)");
  if (flag("--stage") && (names.length > 1 || (opt("--safe") || "").includes(","))) die("--stage is for one Safe on one chain");
  if (names.length > 1 && (opt("--safe") || opt("--name"))) die("--safe and --name are for one chain; with several, each chain's Safe comes from live.json");
  let lines;
  if (names[0] === "local") {
    const ip = lanIp();
    if (!ip) die("no LAN address for the Pico to reach this computer");
    lines = [`QUORUM_URL = ${JSON.stringify(`http://${ip}:${process.env.QUORUM_PORT || 8787}`)}`];
  } else {
    const live = saved();
    // --safe A,B (and --name N1,N2) on ONE chain: the console watches several Safes there. Nothing is
    // saved as the chain's default Safe in live.json (theSafe does that for a single --safe).
    const many = names.length === 1 && (opt("--safe") || "").includes(",");
    if (many && (opt("--safe").split(",").length > 4)) die("the console watches at most 4 Safes");
    let safes;
    if (many) {
      const c = CHAINS[names[0]];
      const labels = (opt("--name") || "").split(",").filter(Boolean);
      safes = opt("--safe").split(",").map((a, i) => ({ chainId: c.chain.id, address: getAddress(a.trim()).toLowerCase(),
        name: labels[i] || (i === 0 ? live.names?.[names[0]] || `${c.chain.name} Safe` : `${c.chain.name} Safe ${i + 1}`) }));
      if (new Set(safes.map((x) => x.address)).size !== safes.length) die("the same Safe twice");
    } else {
      safes = names.map((name) => {
        const c = CHAINS[name];
        const safe = theSafe({ ...c, name });
        const label = (names.length === 1 && opt("--name")) || live.names?.[name] || `${c.chain.name} Safe`;
        live.names = { ...live.names, [name]: label };
        return { chainId: c.chain.id, address: safe.toLowerCase(), name: label };
      });
      keep(live);
    }
    if (flag("--stage")) {
      // the Safe asked about at this laptop's live propose --by console, not at Safe's service
      const ip = lanIp();
      if (!ip) die("no LAN address for the Pico to reach this computer");
      safes[0].url = `http://${ip}:${process.env.QUORUM_STAGE_PORT || 8791}`;
    }
    lines = [`QUORUM_SAFES = [\n    ${safes.map((x) => JSON.stringify(x)).join(",\n    ")}\n]`];
  }
  console.log(`the Pico's console, to ${names.map((x) => CHAINS[x].chain.name).join(" + ")}:\n  ${lines.join("\n  ")}`);
  const code = `import os
new = ${JSON.stringify(lines.join("\n"))}
with open('secrets.py') as f:
    old = f.read()
with open('secrets.bak', 'w') as f:
    f.write(old)
keep, skip = [], False
for l in old.split(chr(10)):
    k = l.split('=')[0].strip()
    if skip:
        skip = not l.startswith(']')
        continue
    if k == 'QUORUM_SAFES' and l.rstrip().endswith('['):
        skip = True
        continue
    if k in ('QUORUM_URL', 'QUORUM_SAFE', 'QUORUM_SAFES') or l.startswith('# Base Sepolia (docs/LADDER.md') or l.startswith('# the network, written by'):
        continue
    keep.append(l)
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
  if (/picoquorum-image: (console|dual)/.test(main)) {
    // then hands off for 30 s: any mpremote command starts with Ctrl-C, which would stop the
    // console mid-start (tools/fw restart, 2026-09-26)
    spawnSync(`${ROOT}tools/usb`, ["exec", "import machine; machine.reset()"], { encoding: "utf8", timeout: 10000 });
    await new Promise((res) => setTimeout(res, 30000));
  } else {
    r = spawnSync(`${ROOT}tools/emu`, ["ship", "quorum"], { encoding: "utf8", timeout: 180000 });
    if (!/running quorum/.test(r.stdout + r.stderr)) die(`the restart did not report back:\n${(r.stdout + r.stderr).slice(-600)}`);
  }
  const check = "import quorum as q; print('NOW', 'net', q.net_ok, q.net_err, '|', ' | '.join('%d %s %s nonce %s me-owner %s' % (w['chain'], w['addr'], w['name'], w['info'].get('nonce'), q.me in q.owners(w)) for w in q.WATCH))";
  for (let i = 0; i < 12; i++) {
    await new Promise((res) => setTimeout(res, 5000));
    r = spawnSync(`${ROOT}tools/usb`, ["exec", check], { encoding: "utf8" });
    const now = (r.stdout || "").match(/NOW .*/);
    if (now && / net True /.test(now[0])) return console.log("  " + now[0]);
    if (i === 11) console.log("  " + (now ? now[0] : "no answer from the board") + "\n  (still joining WiFi or the service? it keeps trying)");
  }
}

const cmds = { key, enroll, status, exec, rehearse, pico, propose, delegate };
if (!cmds[sub]) die("usage: tools/quorum live key | enroll | status | rehearse | exec | pico | propose | delegate   (see tools/mock-tx-service/live.mjs)");
await cmds[sub]();
