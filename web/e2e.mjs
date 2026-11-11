// The app in a real browser, proposing and confirming end to end, with no chain and no funds:
//   cd web && npm run build && npm run e2e            (SHOTS=dir to keep screenshots)
// Chromium comes from playwright-core (npx playwright-core install chromium once), or set
// PQ_CHROMIUM to a Chrome or Chromium binary.
//
// Behind the page, three fakes stand in for the outside world, and every other request is refused:
// - A wallet (EIP-6963) holding anvil's public test keys. It signs EIP-712 as MetaMask does.
// - Base Sepolia: a Safe 1.4.1, 2 of 3 (Alice, Bob, Carol), at nonce 9, with USDC.
// - Safe's transaction service, with the real one's checks: the hash is the fields' hash, the sender
//   is an owner, and every signature recovers to its owner.
// - A console on USB (#/device): a fake navigator.serial that answers the USB link
//   (docs/USB-LINK.md) as the firmware does. The firmware's own end is tested in
//   test-vectors/console_test.py (case_link).
// Exit 1 on any failure.
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { mkdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import {
  decodeFunctionData, encodeFunctionResult, getAddress, parseAbi, parseEther, recoverAddress,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { p256 } from "@noble/curves/p256";
import { writeConfig } from "./config.mjs";

writeConfig();
const S = await import("./src/safe.mjs");
const P = await import("./src/propose.mjs");
const NS = await import("./src/newsafe.mjs");
const { p256Owner } = await import("../tools/mock-tx-service/sigs.mjs");

const DOCS = fileURLToPath(new URL("../docs/", import.meta.url));
const SHOTS = process.env.SHOTS;
if (SHOTS) mkdirSync(SHOTS, { recursive: true });
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };

// ----------------------------------------------------------------------------- the people (anvil's test keys)
const keys = {
  alice: "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
  bob: "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
  carol: "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
  mallory: "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a",
};
const who = Object.fromEntries(Object.entries(keys).map(([k, v]) => [k, privateKeyToAccount(v)]));
const DAVE = getAddress("0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc");   // anvil #5's address

// ----------------------------------------------------------------------------- the chain
const SAFE = getAddress("0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43");
const CHAIN_ID = 84532;
const USDC = P.knownTokens(CHAIN_ID)[0].address;
const chain = { owners: [who.alice.address, who.bob.address, who.carol.address], threshold: 2, nonce: 9, balance: parseEther("0.1"),
  deployed: new Set(), sent: new Map() };     // passkey signers deployed here; transactions sent, by hash
const FACTORY = getAddress(S.CFG.signer.factory);
const ABI = [...S.SAFE_ABI, ...P.ERC20_ABI, ...S.SIGNER_ABI, ...NS.FACTORY_ABI];
function ethCall({ to, data }) {
  const { functionName, args } = decodeFunctionData({ abi: ABI, data });
  const out = (v) => encodeFunctionResult({ abi: ABI, functionName, result: v });
  if (getAddress(to) === SAFE) {
    if (functionName === "getOwners") return out(chain.owners);
    if (functionName === "getThreshold") return out(BigInt(chain.threshold));
    if (functionName === "nonce") return out(BigInt(chain.nonce));
    if (functionName === "VERSION") return out("1.4.1");
    if (functionName === "getTransactionHash") {
      const [to2, value, data2, operation, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, nonce] = args;
      return out(S.safeTxHash(CHAIN_ID, SAFE, { to: to2, value, data: data2, operation, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, nonce }));
    }
  }
  if (getAddress(to) === getAddress(NS.NEW_SAFE.factory) && functionName === "proxyCreationCode") return out("0x6080604052");
  if (getAddress(to) === FACTORY && functionName === "getSigner") return out(p256Owner(S.CFG.signer, args[0], args[1]));
  if (getAddress(to) === USDC) {
    if (functionName === "decimals") return out(6);
    if (functionName === "symbol") return out("USDC");
    if (functionName === "balanceOf") return out(25_000_000n);
  }
  throw new Error("execution reverted");
}
function rpc(req) {
  const { id, method, params } = req;
  const ok = (result) => ({ jsonrpc: "2.0", id, result });
  try {
    if (method === "eth_chainId") return ok("0x" + CHAIN_ID.toString(16));
    if (method === "eth_blockNumber") return ok("0x100");
    if (method === "eth_getCode") return ok([SAFE, USDC, FACTORY, ...chain.deployed].includes(getAddress(params[0])) ? "0x6080604052" : "0x");
    if (method === "eth_getTransactionReceipt") {
      const tx = chain.sent.get(params[0]);
      return ok(tx && { transactionHash: params[0], transactionIndex: "0x0", blockHash: "0x" + "ab".repeat(32), blockNumber: "0x100", from: tx.from, to: tx.to,
        cumulativeGasUsed: "0x5208", gasUsed: "0x5208", effectiveGasPrice: "0x1", contractAddress: null, logs: [], logsBloom: "0x" + "00".repeat(256), status: "0x1", type: "0x2" });
    }
    if (method === "eth_getBalance") return ok("0x" + (getAddress(params[0]) === SAFE ? chain.balance : 0n).toString(16));
    if (method === "eth_call") return ok(ethCall(params[0]));
    return { jsonrpc: "2.0", id, error: { code: -32601, message: `the fake chain has no ${method}` } };
  } catch (e) {
    return { jsonrpc: "2.0", id, error: { code: 3, message: e.message } };
  }
}

// ----------------------------------------------------------------------------- Safe's transaction service
const SERVICE = S.CHAINS.basesep.service;
const svc = { txs: [], refuseNext: null, posts: [], auths: [] };
const recovers = async (hash, signature, owner) => {
  try { return (await recoverAddress({ hash, signature })) === getAddress(owner); } catch { return false; }
};
async function service(method, url, body) {
  const path = url.slice(SERVICE.length).split("?")[0];
  const q = new URL(url).searchParams;
  if (method === "GET" && path === `/api/v1/safes/${SAFE}/`)
    return [200, { address: SAFE, nonce: chain.nonce, threshold: chain.threshold, owners: chain.owners, version: "1.4.1" }];
  if (method === "GET" && path === `/api/v2/safes/${SAFE}/multisig-transactions/`) {
    const list = svc.txs.filter((t) => t.nonce >= Number(q.get("nonce__gte") || 0)).sort((a, b) => a.nonce - b.nonce);
    return [200, { count: list.length, next: null, previous: null, results: list }];
  }
  if (method === "POST") svc.posts.push({ path, body });
  if (method === "POST" && svc.refuseNext) { const r = svc.refuseNext; svc.refuseNext = null; return r; }
  if (method === "POST" && path === `/api/v2/safes/${SAFE}/multisig-transactions/`) {
    const b = body;
    for (const k of ["baseGas", "contractTransactionHash", "gasPrice", "nonce", "operation", "safe", "safeTxGas", "sender", "to", "value"])
      if (b[k] === undefined || b[k] === null) return [400, { [k]: ["This field is required."] }];
    const hash = S.safeTxHash(CHAIN_ID, SAFE, b);
    if (hash !== b.contractTransactionHash) return [422, { nonFieldErrors: [`Contract-transaction-hash=${b.contractTransactionHash} does not match provided contract-tx-hash=${hash}`] }];
    if (!chain.owners.includes(getAddress(b.sender))) return [422, { nonFieldErrors: [`Sender=${b.sender} is not an owner or delegate`] }];
    if (!(await recovers(hash, b.signature, b.sender))) return [422, { nonFieldErrors: ["Signature does not match sender"] }];
    if (b.nonce < chain.nonce) return [422, { nonFieldErrors: ["Nonce too low"] }];
    if (svc.txs.some((t) => t.safeTxHash === hash)) return [422, { nonFieldErrors: ["Transaction already exists"] }];
    svc.txs.push({ safe: SAFE, to: getAddress(b.to), value: String(b.value), data: b.data, operation: b.operation, gasToken: b.gasToken,
      safeTxGas: String(b.safeTxGas), baseGas: String(b.baseGas), gasPrice: String(b.gasPrice), refundReceiver: b.refundReceiver,
      nonce: Number(b.nonce), safeTxHash: hash, proposer: getAddress(b.sender), origin: b.origin, isExecuted: false,
      confirmationsRequired: chain.threshold, dataDecoded: null,
      confirmations: [{ owner: getAddress(b.sender), signature: b.signature, signatureType: "EOA" }] });
    return [201, null];
  }
  const m = path.match(/^\/api\/v1\/multisig-transactions\/(0x[0-9a-f]{64})\/confirmations\/$/);
  if (method === "POST" && m) {
    const t = svc.txs.find((x) => x.safeTxHash === m[1]);
    if (!t) return [404, { detail: "Not found." }];
    const owner = (await Promise.all(chain.owners.map(async (o) => (await recovers(t.safeTxHash, body.signature, o)) && o))).find(Boolean);
    if (!owner) return [422, { signature: ["Signer is not an owner"] }];
    if (t.confirmations.some((c) => c.owner === owner)) return [422, { signature: ["Signer has already signed"] }];
    t.confirmations.push({ owner, signature: body.signature, signatureType: "EOA" });
    return [201, { signature: body.signature }];
  }
  return [404, { detail: "Not found." }];
}

// ----------------------------------------------------------------------------- the wallet
const wallet = { as: "alice", signed: [], decline: false };
async function walletRequest({ method, params }) {
  const me = who[wallet.as];
  if (method === "eth_requestAccounts" || method === "eth_accounts") return [me.address.toLowerCase()];
  if (method === "eth_chainId") return "0x" + CHAIN_ID.toString(16);
  if (method === "wallet_switchEthereumChain") return null;
  if (method === "eth_sendTransaction") {         // only the passkey factory's createSigner, as the chain here knows it
    const tx = params[0];
    if (getAddress(tx.to) === getAddress(NS.NEW_SAFE.factory)) {   // a new Safe: kept to check, then declined
      wallet.newSafe = { from: tx.from, ...decodeFunctionData({ abi: NS.FACTORY_ABI, data: tx.data }) };
      throw { code: 4001, message: "User rejected the request." };
    }
    const { functionName, args } = decodeFunctionData({ abi: S.SIGNER_ABI, data: tx.data });
    if (getAddress(tx.to) !== FACTORY || functionName !== "createSigner") throw { code: -32000, message: "the test chain only takes createSigner" };
    const hash = "0x" + createHash("sha256").update(tx.data + chain.sent.size).digest("hex");
    chain.deployed.add(getAddress(p256Owner(S.CFG.signer, args[0], args[1])));
    chain.sent.set(hash, { ...tx, args });
    return hash;
  }
  if (method === "eth_signTypedData_v4") {
    if (wallet.decline) { wallet.decline = false; throw { code: 4001, message: "User rejected the request." }; }
    if (getAddress(params[0]) !== me.address) throw { code: 4100, message: "That account isn't connected." };
    const td = JSON.parse(params[1]);
    const { EIP712Domain, ...types } = td.types;
    const uints = new Set(types[td.primaryType].filter((f) => f.type.startsWith("uint")).map((f) => f.name));
    const message = Object.fromEntries(Object.entries(td.message).map(([k, v]) => [k, uints.has(k) ? BigInt(v) : v]));
    wallet.signed.push(td);
    return me.signTypedData({ domain: td.domain, types, primaryType: td.primaryType, message });
  }
  throw { code: 4200, message: `the test wallet has no ${method}` };
}
const WALLET_PAGE = () => {
  const listeners = {};
  const provider = {
    request: async (args) => {
      const r = await window.__wallet(JSON.stringify(args));
      const { ok, value, error } = JSON.parse(r);
      if (!ok) throw Object.assign(new Error(error.message), { code: error.code });
      return value;
    },
    on: (ev, f) => ((listeners[ev] ||= []).push(f)),
  };
  window.__walletEmit = (ev, v) => (listeners[ev] || []).forEach((f) => f(v));
  const announce = () => window.dispatchEvent(new CustomEvent("eip6963:announceProvider",
    { detail: Object.freeze({ info: { uuid: "e2e", name: "Test Wallet", icon: "data:,", rdns: "org.picoquorum.e2e" }, provider }) }));
  window.addEventListener("eip6963:requestProvider", announce);
  announce();
};

// The USB link's other end, for #/device: a scripted console that answers as firmware/usblink.py does.
// It keeps what it was sent in window.__dev, and saves an ask only when the test accepts it.
const FAKE_SERIAL = ({ release, safe }) => {
  const enc = new TextEncoder(), dec = new TextDecoder();
  const dev = window.__dev = { got: [], signals: [], filters: null, pending: null, down: false, opens: 0, buf: "", ctrl: null,
    rp: false, res: [], his: 0, raw: "",      // rp: a console-rp behind a CH343P, which sends its own calls for the page to relay
    wifi: { up: true, ssid: "bench", saved: ["bench"] },
    safes: [{ chainId: 84532, address: safe.toLowerCase(), name: "<b>Ops</b>", ok: true, err: "", threshold: 2, owners: 3, nonce: 9, isOwner: false, queued: 0, waiting: 0 }] };
  const say = (o) => dev.ctrl?.enqueue(enc.encode('{"pq":1,' + JSON.stringify(o).slice(1) + "\n"));
  const status = () => ({ mode: "console", name: "Picoquorum", state: "home", ready: "ok", serial: "0123e063aa", profile: "608C",
    owner: "0x5FbDB2315678afecb367f032d93F642f64180aa3", key: "02" + "ab".repeat(32), pinned: true, pinWhy: "", counter: 3,
    chip: { model: "<i>ATECC608C</i>", keySealed: true, configLocked: true, dataLocked: true },
    wifi: dev.rp ? undefined : dev.wifi, safes: dev.safes, safesFrom: "safes.json", ask: dev.pending?.op || null, watchdog: true,
    image: dev.rp ? "console-rp" : "console", version: "2026.11.1" });
  function handle(m) {
    if (m.t === "res") return dev.res.push(m);
    if (m.t === "hi") return dev.his++;
    dev.got.push(m);
    if (m.op === "hello" && dev.rp)
      return say({ id: m.id, ok: true, proto: 1, mode: "console", board: "console-rp", image: "console-rp", version: "2026.11.3", release, build: "0d617601", link: { max: 24576 } });
    if (m.op === "hello") return say({ id: m.id, ok: true, proto: 1, mode: "console", board: "picoquorum-key", image: "console", version: "2026.11.1", release, build: "cdab74db" });
    if (m.op === "status") return say({ id: m.id, ok: true, ...status() });
    if (m.op === "wifi" || m.op === "safes") {
      if (dev.pending) return say({ id: m.id, ok: false, why: "busy: another ask is on the screen" });
      dev.pending = m;
      return;
    }
    say({ id: m.id, ok: false, why: "unknown op" });
  }
  // The console's own lines, keys in its own order (MicroPython's json keeps none).
  dev.req = (o) => dev.ctrl?.enqueue(enc.encode(JSON.stringify(o) + "\n"));
  dev.log = (msg) => dev.ctrl?.enqueue(enc.encode(JSON.stringify({ m: msg, t: "log" }) + "\n"));
  dev.decide = (ok) => {
    const m = dev.pending; dev.pending = null;
    if (!ok) return say({ id: m.id, ok: false, why: "refused on the device", kind: m.op });
    if (m.op === "safes") dev.safes = m.safes.map((x) => ({ ...x, ok: true, err: "", threshold: 2, owners: 3, nonce: 9, isOwner: true, queued: 0, waiting: 0 }));
    else dev.wifi = { up: false, ssid: "", saved: [...dev.wifi.saved, m.ssid] };
    say({ id: m.id, ok: true, kind: m.op });
    setTimeout(() => {            // it restarts: the port goes, and comes back 2 s later
      dev.down = true; dev.ctrl?.error(new TypeError("The device has been lost.")); dev.ctrl = null;
      setTimeout(() => { dev.down = false; }, 2000);
    }, 300);
  };
  const port = {
    readable: null, writable: null,
    getInfo: () => (dev.rp ? { usbVendorId: 0x1a86, usbProductId: 0x55d3 } : { usbVendorId: 0x303a, usbProductId: 0x1001 }),
    async open({ baudRate }) {
      if (dev.down) throw new DOMException("Failed to open serial port.", "NetworkError");
      dev.opens++; dev.baud = baudRate;
      port.readable = new ReadableStream({ start: (c) => { dev.ctrl = c; } });
      port.writable = new WritableStream({ write(chunk) {
        const t = dec.decode(chunk);
        dev.raw += t;
        dev.buf += t;
        let i;
        while ((i = dev.buf.indexOf("\n")) >= 0) { const l = dev.buf.slice(0, i); dev.buf = dev.buf.slice(i + 1); handle(JSON.parse(l)); }
      } });
    },
    async setSignals(s) { dev.signals.push(s); },
    async close() { dev.ctrl = null; },
  };
  const serial = { async requestPort(o) { dev.filters = o.filters; return port; }, async getPorts() { return dev.down ? [] : [port]; } };
  Object.defineProperty(Navigator.prototype, "serial", { configurable: true, get: () => serial });
};

// ----------------------------------------------------------------------------- the page's own files
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
  ".woff2": "font/woff2", ".png": "image/png", ".gif": "image/gif" };
const server = createServer((req, res) => {
  let p = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^(\.\.[/\\])+/, "");
  let f = join(DOCS, p);
  try { if (statSync(f).isDirectory()) f = join(f, "index.html"); res.writeHead(200, { "Content-Type": TYPES[extname(f)] || "application/octet-stream" }); res.end(readFileSync(f)); }
  catch { res.writeHead(404); res.end(); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}/`;

// ----------------------------------------------------------------------------- the run
const browser = await chromium.launch({ executablePath: process.env.PQ_CHROMIUM || undefined, args: ["--no-proxy-server"] });
const ctx = await browser.newContext({ viewport: { width: 1200, height: 900 } });
const errors = [];
const outside = [];
await ctx.exposeFunction("__wallet", async (json) => {
  try { return JSON.stringify({ ok: true, value: await walletRequest(JSON.parse(json)) }); }
  catch (e) { return JSON.stringify({ ok: false, error: { code: e.code, message: e.message } }); }
});
await ctx.addInitScript(WALLET_PAGE);
const CONSOLE_RELEASE = JSON.parse(readFileSync(join(DOCS, "console/BUILD.json"), "utf8")).release;
await ctx.addInitScript(FAKE_SERIAL, { release: CONSOLE_RELEASE, safe: SAFE });
const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
await ctx.route("**/*", async (route) => {
  const r = route.request();
  const url = r.url();
  if (url.startsWith(BASE)) return route.continue();
  if (r.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
  if (url.startsWith(S.CHAINS.basesep.rpc)) {
    const body = JSON.parse(r.postData());
    const out = Array.isArray(body) ? body.map(rpc) : rpc(body);
    return route.fulfill({ status: 200, headers: CORS, contentType: "application/json", body: JSON.stringify(out) });
  }
  if (url.startsWith(SERVICE)) {
    svc.auths.push(r.headers().authorization || "");
    const [status, json] = await service(r.method(), url, r.postData() ? JSON.parse(r.postData()) : null);
    return route.fulfill({ status, headers: CORS, contentType: "application/json", body: json == null ? "" : JSON.stringify(json) });
  }
  if (url.startsWith(S.CHAINS.eth.rpc) || url.startsWith(S.CHAINS.base.rpc))       // the other chains: down, as far as the page knows
    return route.fulfill({ status: 503, headers: CORS, body: "" });
  outside.push(url);
  return route.abort();
});
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(e.message));
page.on("dialog", (d) => d.accept());
const shot = async (name) => SHOTS && page.screenshot({ path: join(SHOTS, `${name}.png`), fullPage: true });
const safeUrl = `${BASE}app/#/safe/basesep/${SAFE}`;
const text = (sel) => page.locator(sel).first().innerText();
const step = async (what, f) => { try { await f(); } catch (e) { check(false, `${what}: ${e.message.split("\n")[0]}`); } };

await step("a proposal from Alice", async () => {
  await page.goto(safeUrl);
  await page.getByText("Nothing waiting").waitFor();
  await page.getByRole("link", { name: "New transaction" }).click();
  await page.getByRole("heading", { name: "New transaction" }).waitFor();
  check((await page.getByRole("radio", { name: "Send ETH" }).getAttribute("aria-checked")) === "true", "new transaction: Send ETH is picked first");
  check((await page.locator("#f-nonce").inputValue()) === "9", "new transaction: the nonce is the Safe's, #9");
  await page.fill("#f-to", who.carol.address);
  check((await text(".addr-in + .hint")) === "an owner", "new transaction: the recipient is recognised as an owner");
  await page.fill("#f-amount", "0.01");
  await page.getByRole("button", { name: "Review" }).click();
  const want = S.safeTxHash(CHAIN_ID, SAFE, P.safeTx({ to: who.carol.address, value: parseEther("0.01"), data: "0x", operation: 0 }, 9));
  await page.locator(".review").waitFor();
  check((await text(".review .vbig")) === S.verifyCode(want), `review: verify code ${S.verifyCode(want)}, the hash the console will compute`);
  await shot("1-review");
  await page.getByRole("button", { name: "Sign and propose" }).click();
  await page.locator(".done").waitFor();
  await shot("2-proposed");
  const td = wallet.signed.at(-1);
  check(td?.domain.chainId === CHAIN_ID && getAddress(td.domain.verifyingContract) === SAFE && td.primaryType === "SafeTx",
    "wallet: asked to sign SafeTx for this Safe on Base Sepolia");
  const t = svc.txs[0];
  check(svc.txs.length === 1 && t.safeTxHash === want && t.proposer === who.alice.address && t.confirmations.length === 1,
    "service: took the proposal, with Alice's signature as the first confirmation");
});

await step("Bob confirms", async () => {
  await page.getByRole("link", { name: "See it in the queue" }).click();
  await page.locator(".tx").waitFor();
  check((await text(".tx h3")) === "Send 0.01 ETH to 0x90F7…b906" && /1 of 2/.test(await text(".tx h4")), "queue: the proposal, with 1 of 2 confirmations");
  check(!(await page.getByRole("button", { name: "Confirm with wallet" }).count()), "queue: no Confirm button for Alice, who has signed");
  wallet.as = "bob";
  await page.evaluate((a) => window.__walletEmit("accountsChanged", [a]), who.bob.address.toLowerCase());
  await page.getByRole("button", { name: "Refresh" }).click();
  await page.getByRole("button", { name: "Confirm with wallet" }).click();
  await page.getByText("Confirmed. Reading the queue again…").waitFor();
  await page.getByRole("button", { name: "Execute with wallet" }).waitFor({ timeout: 10000 });
  check(/2 of 2/.test(await text(".tx h4")) && svc.txs[0].confirmations.length === 2, "queue: Bob's confirmation makes it 2 of 2, ready to execute");
  await shot("3-confirmed");
});

await step("Carol's wallet declines, then she isn't asked twice", async () => {
  wallet.as = "carol";
  await page.evaluate((a) => window.__walletEmit("accountsChanged", [a]), who.carol.address.toLowerCase());
  await page.goto(`${safeUrl}/new`);
  await page.fill("#f-to", DAVE);
  await page.fill("#f-amount", "0.02");
  await page.getByRole("button", { name: "Review" }).click();
  check((await page.locator("#f-nonce").inputValue()) === "10", "new transaction: the next nonce is after the queue, #10");
  wallet.decline = true;
  await page.getByRole("button", { name: "Sign and propose" }).click();
  await page.getByText("You declined in your wallet. Nothing was sent.").waitFor();
  check(svc.txs.length === 1, "declined: nothing reached the service");
});

await step("a rejection", async () => {
  wallet.as = "alice";
  await page.evaluate((a) => window.__walletEmit("accountsChanged", [a]), who.alice.address.toLowerCase());
  await page.goto(safeUrl);
  await page.getByRole("link", { name: "Propose a rejection" }).click();
  await page.getByRole("heading", { name: "New transaction" }).waitFor();
  check((await page.getByRole("radio", { name: "Rejection" }).getAttribute("aria-checked")) === "true" && (await page.locator("#f-nonce").inputValue()) === "9",
    "rejection: from the queue, picked with the transaction's nonce, #9");
  await page.getByRole("button", { name: "Review" }).click();
  check(/already has a transaction/.test(await text(".review .warns")), "rejection: the review says only one of them can run");
  await page.getByRole("button", { name: "Sign and propose" }).click();
  await page.locator(".done").waitFor();
  const r = svc.txs.at(-1);
  check(r.nonce === 9 && P.isRejection(SAFE, r) && r.data === null, "rejection: the service holds the Safe calling itself with nothing at #9");
  await page.getByRole("link", { name: "See it in the queue" }).click();
  await page.locator(".tx").nth(1).waitFor();
  const titles = await page.locator(".tx h3").allInnerTexts();
  check(titles.includes("Rejection of #9") && !(await page.getByRole("link", { name: "Propose a rejection" }).count()),
    "queue: shows the rejection, and offers no second one");
  await shot("4-rejection");
});

await step("an owner change", async () => {
  await page.goto(`${safeUrl}/new`);
  await page.getByRole("radio", { name: "Add owner" }).click();
  await page.fill("#f-owner", DAVE);
  await page.selectOption("#f-threshold", "3");
  await page.getByRole("button", { name: "Review" }).click();
  check(await page.locator(".review.red .red-banner").isVisible(), "add owner: the review is red, as the console's page is");
  await shot("5-add-owner");
  await page.getByRole("button", { name: "Sign and propose" }).click();
  await page.locator(".done").waitFor();
  const t = svc.txs.at(-1);
  const { functionName, args } = decodeFunctionData({ abi: P.OWNER_ABI, data: t.data });
  check(t.nonce === 10 && functionName === "addOwnerWithThreshold" && args[0] === DAVE && args[1] === 3n && getAddress(t.to) === SAFE,
    "add owner: addOwnerWithThreshold(Dave, 3) on the Safe, at #10");
});

await step("a token", async () => {
  await page.goto(`${safeUrl}/new`);
  await page.getByRole("radio", { name: "Send a token" }).click();
  await page.fill("#f-to", DAVE);
  await page.fill("#f-amount", "1.5");
  await page.getByRole("button", { name: "Review" }).click();
  await page.locator(".review").waitFor();
  check((await text(".review h2")) === "Send 1.5 USDC", "token: USDC from the console's list, its decimals read from the chain");
  await page.getByRole("button", { name: "Sign and propose" }).click();
  await page.locator(".done").waitFor();
  const { args } = decodeFunctionData({ abi: P.ERC20_ABI, data: svc.txs.at(-1).data });
  check(getAddress(svc.txs.at(-1).to) === USDC && args[0] === DAVE && args[1] === 1_500_000n, "token: transfer(Dave, 1.5 USDC) on the token");
});

await step("refusals", async () => {
  const before = svc.txs.length;
  await page.goto(`${safeUrl}/new`);
  await page.getByRole("radio", { name: "Add owner" }).click();
  await page.fill("#f-owner", who.bob.address);
  await page.getByRole("button", { name: "Review" }).click();
  check(/already an owner/.test(await text("[role=alert]")), "form: adding an existing owner is refused before review");
  await page.getByRole("radio", { name: "Send ETH" }).click();
  await page.fill("#f-to", DAVE);
  await page.fill("#f-amount", "0.001");
  await page.getByRole("button", { name: "Review" }).click();
  svc.refuseNext = [422, { nonFieldErrors: ["Nonce too low"] }];
  await page.getByRole("button", { name: "Sign and propose" }).click();
  await page.getByText(/refused it \(HTTP 422\): Nonce too low/).waitFor();
  check(true, "service: its refusal is shown in its own words");
  const asked = wallet.signed.length;
  wallet.as = "mallory";
  await page.evaluate((a) => window.__walletEmit("accountsChanged", [a]), who.mallory.address.toLowerCase());
  await page.getByRole("button", { name: "Sign and propose" }).click();
  await page.getByText(/isn't an owner of this Safe/).waitFor();
  check(svc.txs.length === before && wallet.signed.length === asked, "not an owner: refused before the wallet is asked, and nothing sent");
  await shot("6-not-owner");
});

await step("releases", async () => {
  // docs/releases/index.json as served, plus one made-up release routed in to check the lookup
  const fp = "4c86c7541a45eb43f24c48c178409de889c5f86d467c886d444e9e30b9a00e0b";
  const appHash = createHash("sha256").update(readFileSync(join(DOCS, "app", "BUILD.json"))).digest("hex");
  await page.route("**/releases/index.json", (r) => r.fulfill({ status: 200, contentType: "application/json",
    body: JSON.stringify({ releases: [{ version: "2026.10.6", date: "2026-10-05", commit: "abc1234def", fingerprints: { console: fp }, web: { app: appHash } }] }) }));
  await page.goto(`${BASE}app/#/releases`);
  await page.getByText("4c86·c754").first().waitFor();
  check(await page.locator("img.blockie").count() >= 1, "releases: each release with its fingerprint's blockie and 4c86·c754");
  await page.fill("#fp", "4C86 c754");
  await page.getByText("Release 2026.10.6 (console image)").waitFor();
  await page.fill("#fp", "deadbeef");
  await page.getByText("No release has that fingerprint").waitFor();
  await page.getByText("This page is release 2026.10.6.").waitFor();
  check(true, "releases: this page knows which release it is (its BUILD.json is that release's)");
  check(true, "releases: the eight digits from a Device screen name the release, or say none does");
  await page.unroute("**/releases/index.json");
  await shot("7-releases");
});

await step("a passkey's signer, from a deploy link, with a wallet that owns no Safe", async () => {
  const pk = p256.getPublicKey(p256.utils.randomPrivateKey(), false);
  const x = Buffer.from(pk.slice(1, 33)).toString("hex"), y = Buffer.from(pk.slice(33)).toString("hex");
  const owner = getAddress(p256Owner(S.CFG.signer, "0x" + x, "0x" + y));
  await page.goto(`${BASE}app/#/signer`);
  await page.fill("#signer-key", owner);
  await page.getByRole("button", { name: "Show its signer" }).click();
  check(/can't be deployed from the address alone/.test(await text("[role=alert]")), "#/signer: an owner address alone is explained, not deployed (it's a hash of the key)");
  await page.fill("#signer-key", `${x} ${y.slice(0, 63)}${y.endsWith("0") ? "1" : "0"}`);   // y's last digit changed: off the curve
  await page.getByRole("button", { name: "Show its signer" }).click();
  check(/isn't a P-256 public key|Paste a deploy link/.test(await text("[role=alert]")), "#/signer: a key that isn't on the curve is refused");
  await page.fill("#signer-key", `https://picoquorum.app/app/#/signer/${x}/${y}`);
  await page.getByRole("button", { name: "Show its signer" }).click();
  await page.getByRole("button", { name: "Deploy on Base Sepolia" }).waitFor();
  check((await page.locator(".card .inline-ident code").first().innerText()).trim() === owner, `the deploy link's page: the owner address it deploys (${owner.slice(0, 10)}…), worked out from the key`);
  check(await page.getByText(/Ethereum: couldn't read the chain/).count() === 1, "a chain it can't read says so, and offers no button");
  wallet.as = "mallory";            // owns nothing here
  const before = chain.sent.size;
  await page.getByRole("button", { name: "Deploy on Base Sepolia" }).click();
  await page.getByText("Deployed").waitFor();
  const tx = [...chain.sent.values()].at(-1);
  check(chain.sent.size === before + 1 && getAddress(tx.from) === who.mallory.address && tx.args[0] === BigInt("0x" + x) && tx.args[1] === BigInt("0x" + y) && tx.args[2] === BigInt(S.CFG.signer.verifiers),
    "Deploy: any wallet (here one that owns no Safe) sends createSigner(x, y, verifiers) to the factory, and it lands");
  await shot("8-signer");
  await page.reload();
  await page.locator(".badge.ok", { hasText: "deployed" }).waitFor();
  check(await page.getByRole("button", { name: "Deploy on Base Sepolia" }).count() === 0, "opened again: deployed on Base Sepolia, no button");
  // your own passkey as an owner of the Safe, with no signer on this chain yet: the Safe page says so
  const pk2 = p256.getPublicKey(p256.utils.randomPrivateKey(), false);
  const x2 = Buffer.from(pk2.slice(1, 33)).toString("hex"), y2 = Buffer.from(pk2.slice(33)).toString("hex");
  const mine = getAddress(p256Owner(S.CFG.signer, "0x" + x2, "0x" + y2));
  await page.evaluate(([a, b]) => localStorage.setItem("emu.passkey", JSON.stringify({ id: "e2e", x: a, y: b, rpId: "127.0.0.1" })), [x2, y2]);
  chain.owners.push(mine);
  await page.goto(safeUrl);
  await page.getByText(/Your passkey · signer not deployed on Base Sepolia/).waitFor();
  check(await page.locator(`a[href="#/signer/${x2}/${y2}"]`).count() === 1, "the Safe page: your passkey as an owner, signer not deployed here, with its deploy link");
  chain.owners.pop();
  wallet.as = "alice";
});

await step("a new key's set-up link (#/k/<compressed key>): compare, deploy from any wallet, Add owner", async () => {
  const priv = p256.utils.randomPrivateKey();
  const full = p256.getPublicKey(priv, false), comp = Buffer.from(p256.getPublicKey(priv, true)).toString("hex");
  const x = Buffer.from(full.slice(1, 33)).toString("hex"), y = Buffer.from(full.slice(33)).toString("hex");
  const owner = getAddress(p256Owner(S.CFG.signer, "0x" + x, "0x" + y));
  await page.goto(`${BASE}app/#/k/${comp.slice(0, 2) === "02" ? "03" : "02"}${"f".repeat(64)}`);   // x = 2^256-1: not a field element
  await page.getByText("That isn't a key's set-up link").waitFor();
  check(await page.getByRole("button", { name: /^Deploy on/ }).count() === 0, "#/k: a key that isn't on the curve is refused, no Deploy button");
  await page.evaluate((a) => localStorage.setItem("pq.safes", JSON.stringify([{ chain: "basesep", address: a, name: "Family Safe" }])), SAFE);
  await page.goto(`${BASE}app/#/k/${comp}`);
  await page.getByRole("button", { name: "Deploy on Base Sepolia" }).waitFor();
  check((await page.locator(".card .inline-ident code").first().innerText()).trim() === owner, `#/k: the owner address (${owner.slice(0, 10)}…), worked out from the compressed key`);
  check(await page.getByText(/signer contract, not a wallet/).count() === 1, "#/k: says the owner address is not a wallet, before anything else");
  check(await page.locator(`a[href="#/safe/basesep/${SAFE}/new/add/${owner}"]`).count() === 1, "#/k: Add owner for each saved Safe, with this key filled in");
  wallet.as = "mallory";            // owns nothing here
  const before = chain.sent.size;
  await page.getByRole("button", { name: "Deploy on Base Sepolia" }).click();
  await page.getByText("Deployed").waitFor();
  const tx = [...chain.sent.values()].at(-1);
  check(chain.sent.size === before + 1 && getAddress(tx.from) === who.mallory.address && tx.args[0] === BigInt("0x" + x) && tx.args[1] === BigInt("0x" + y) && tx.args[2] === BigInt(S.CFG.signer.verifiers),
    "#/k Deploy: any wallet sends createSigner(x, y, verifiers) for the uncompressed key, and it lands");
  await shot("9-key-setup");
  // 2. Make a new Safe: the recovery address can't be an owner; the wallet is asked for the 1.4.1 factory's
  // createProxyWithNonce, this wallet and the key 2 of 2, the setup batch the fork test runs (fork-newsafe.mjs)
  await page.fill("#recovery", who.mallory.address);
  await page.getByRole("button", { name: "Make the Safe" }).click();
  await page.getByText(/can't be an owner/).waitFor();
  check(!wallet.newSafe, "New Safe: the connected wallet as its recovery address is refused, nothing asked of the wallet");
  await page.fill("#recovery", DAVE);
  await page.getByRole("button", { name: "Make the Safe" }).click();
  await page.getByText("You declined in your wallet. Nothing was sent.").waitFor();
  const ns = wallet.newSafe, want = NS.initializer(who.mallory.address, owner, DAVE, BigInt("0x" + x), BigInt("0x" + y));
  check(ns && getAddress(ns.from) === who.mallory.address && ns.functionName === "createProxyWithNonce" && getAddress(ns.args[0]) === getAddress(NS.NEW_SAFE.singleton)
    && ns.args[1] === want && ns.args[2] === NS.NEW_SAFE.saltNonce, "New Safe: the wallet is asked for createProxyWithNonce(SafeL2 1.4.1, the setup for this wallet, the key and the recovery address)");
  const setup = decodeFunctionData({ abi: NS.SETUP_ABI, data: ns.args[1] });
  check(setup.args[0].map((a) => getAddress(a)).join() === [who.mallory.address, owner].join() && setup.args[1] === 2n && getAddress(setup.args[2]) === getAddress(NS.NEW_SAFE.setupBatch),
    "New Safe: its owners are the wallet and the key, 2 of 2, set up through MultiSendCallOnly 1.5.0");
  delete wallet.newSafe;
  await page.goto(`${BASE}app/#/signer`);
  await page.fill("#signer-key", `https://picoquorum.app/app/#/k/${comp}`);
  await page.getByRole("button", { name: "Show its signer" }).click();
  await page.waitForURL(new RegExp(`#/k/${comp}$`));
  check(true, "#/signer: a pasted set-up link opens that key's page");
  await page.goto(`${BASE}app/#/signer`);
  await page.fill("#signer-key", "0x" + comp.toUpperCase());
  await page.getByRole("button", { name: "Show its signer" }).click();
  await page.waitForURL(new RegExp(`#/k/${comp}$`));
  await page.getByRole("button", { name: "Deploy on Base Sepolia" }).or(page.getByText("deployed", { exact: true })).first().waitFor();
  check((await page.locator(".card .inline-ident code").first().innerText()).trim() === owner, "#/signer: a pasted compressed key (0x, any case) opens its page, with its owner address");
  await page.evaluate(() => localStorage.removeItem("pq.safes"));
  wallet.as = "alice";
});

await step("#/device: a console on USB, its cards, a Safes ask accepted on it, a Wi-Fi ask refused", async () => {
  const dev = (f) => page.evaluate(f);
  await page.evaluate((safe) => localStorage.setItem("pq.safes", JSON.stringify([{ chain: "basesep", address: safe, name: "Team" }])), SAFE);
  await page.goto(`${BASE}app/#/device`);
  await page.getByRole("button", { name: "Connect a device" }).click();
  await page.getByText("PicoquorumKey", { exact: true }).waitFor();
  const d = await dev(() => window.__dev);
  check(d.filters.some((f) => f.usbVendorId === 0x303a) && d.baud === 115200, "#/device: the chooser offers Espressif's USB, and the port opens at 115200");
  check(d.signals.length && d.signals.every((s) => s.dataTerminalReady === false && s.requestToSend === false), "#/device: DTR and RTS are set low, and never high");
  await page.getByText("Same as the console in this browser").waitFor();
  check(true, "#/device: the device's release fingerprint matches the console page's");
  check(await page.locator('a[href="#/k/02' + "ab".repeat(32) + '"]').count() === 1, "#/device: the key's card links to its set-up page (#/k/<key>)");
  check((await page.locator("main").innerText()).includes("<b>Ops</b>"), "#/device: a Safe's name from the device is drawn as text");
  check((await page.locator("main").innerText()).includes("<i>ATECC608C</i> · config locked · data locked · key slot sealed"),
    "#/device: the chip's model and locks, as the console read them at boot, drawn as text");
  await shot("device-connected");

  await page.locator(".checks input").first().check();
  await page.getByRole("button", { name: "Send to the device" }).last().click();
  await page.getByText("hold D2 for 2 s").waitFor();
  const ask = await dev(() => window.__dev.pending);
  check(ask?.op === "safes" && JSON.stringify(ask.safes) === JSON.stringify([{ chainId: 84532, address: SAFE.toLowerCase(), name: "Team" }]),
    "#/device: the safes ask carries chainId, address and name only");
  await dev(() => window.__dev.decide(true));
  await page.getByText("Accepted on the console and saved").waitFor();
  await page.getByText("It's back").waitFor({ timeout: 15000 });
  await page.getByText("This key is an owner").waitFor();
  check((await dev(() => window.__dev.opens)) === 2, "#/device: after the restart the page opens the port again, and reads the new Safes");

  await page.fill("#dev-ssid", "home");
  await page.fill("#dev-pass", "a long password");
  await page.getByRole("button", { name: "Send to the device" }).first().click();
  await page.getByText("hold D2 for 2 s").waitFor();
  check((await page.inputValue("#dev-pass")) === "", "#/device: the password field is emptied once sent");
  await dev(() => window.__dev.decide(false));
  await page.getByText("Not saved: refused on the device").waitFor();
  const ops = await dev(() => window.__dev.got.map((m) => m.op));
  check(ops.every((o) => ["hello", "status", "wifi", "safes"].includes(o)), `#/device: the page asked only hello, status, wifi and safes (${[...new Set(ops)].join(", ")})`);
  await page.evaluate(() => localStorage.removeItem("pq.safes"));
});

await step("#/device: a console-rp, and the page as its relay", async () => {
  const dev = (f, a) => page.evaluate(f, a);
  const answer = async (id) => {
    await page.waitForFunction((i) => window.__dev.res.some((r) => r.id === i), id, { timeout: 8000 });
    return (await dev(() => window.__dev.res)).find((r) => r.id === id);
  };
  await page.goto("about:blank");
  await page.goto(`${BASE}app/#/device`);
  await page.evaluate(() => localStorage.setItem("pq.apiKey", JSON.stringify("e2e-key-5150")));
  await dev(() => { window.__dev.rp = true; });
  await page.getByRole("button", { name: "Connect a device" }).click();
  await page.getByText("Safe's service, through this page").waitFor();
  check((await dev(() => window.__dev.baud)) === 460800, "#/device: a CH343P (WCH) opens at 460800");
  check(await page.locator("#dev-ssid").count() === 0, "#/device: a console-rp has no Wi-Fi card");
  await page.waitForFunction(() => window.__dev.his >= 2, null, { timeout: 8000 });
  check(true, "#/device: the page says hi to the console every 2 s");

  const n0 = svc.auths.length;
  await dev((u) => window.__dev.req({ url: u, m: "GET", id: 11, t: "req" }), `${SERVICE}/api/v1/safes/${SAFE}/`);
  const r11 = await answer(11);
  check(r11.status === 200 && getAddress(JSON.parse(r11.body).address) === getAddress(SAFE), "#/device: the console's GET of its Safe made, and answered under its id");
  check(svc.auths.length === n0 + 1 && svc.auths.at(-1) === "Bearer e2e-key-5150", "#/device: made once, with the API key from Settings");

  await dev((s) => window.__dev.req({ t: "req", id: 12, m: "GET", url: `https://evil.example/api/v1/safes/${s}/` }), SAFE);
  const r12 = await answer(12);
  check(r12.status === 0 && r12.err === "not a pinned service" && svc.auths.length === n0 + 1 && !outside.some((u) => u.includes("evil.example")),
    "#/device: a call off the pin: refused, status 0, nothing fetched");

  const sig = "0x" + "11".repeat(65), p0 = svc.posts.length;
  const confirm = `${SERVICE}/api/v1/multisig-transactions/0x${"cd".repeat(32)}/confirmations/`;
  await dev(([u, b]) => window.__dev.req({ body: b, t: "req", m: "POST", url: u, id: 13 }), [confirm, JSON.stringify({ signature: sig })]);
  const r13 = await answer(13);
  check(svc.posts.length === p0 + 1 && JSON.stringify(svc.posts.at(-1).body) === JSON.stringify({ signature: sig }) && r13.status > 0,
    `#/device: a confirmation POSTed as the console sent it, and the service's answer (${r13.status}) sent back`);
  await dev(([u, b]) => window.__dev.req({ t: "req", id: 14, m: "POST", url: u, body: b }), [confirm, JSON.stringify({ signature: sig, to: SAFE })]);
  const r14 = await answer(14);
  check(r14.status === 0 && svc.posts.length === p0 + 1, "#/device: a POST with more than the signature: refused, nothing posted");

  await dev(() => window.__dev.log("<b>signed</b> #4"));
  await page.locator("summary", { hasText: "The console's log" }).click();
  await page.getByText("<b>signed</b> #4").waitFor();
  check(true, "#/device: the console's log lines, drawn as text");
  await page.getByText("4 asked: 2 answered, 2 refused, 0 failed").waitFor();
  check(!(await dev(() => window.__dev.raw)).includes("e2e-key-5150"), "#/device: the API key never down the cable");
  await shot("device-relay");
  await page.evaluate(() => localStorage.removeItem("pq.apiKey"));
});

await step("#/device without Web Serial: it says so, and still offers the console in the browser", async () => {
  const c2 = await browser.newContext();
  await c2.addInitScript(() => { delete Navigator.prototype.serial; });
  const p2 = await c2.newPage();
  p2.on("pageerror", (e) => errors.push(e.message));
  await p2.goto(`${BASE}app/#/device`);
  await p2.getByText("can't talk to USB devices").waitFor();
  check(await p2.getByRole("button", { name: "Connect a device" }).isDisabled(), "#/device: Connect is off without Web Serial");
  check(await p2.locator('a[href="../console/?board=waveshare"]').count() === 1, "#/device: the console in the browser is still offered");
  await c2.close();
});

check(!errors.length, `no page errors${errors.length ? ": " + errors.join("; ") : ""}`);
check(!outside.length, `no request left the fakes${outside.length ? ": " + outside.join(", ") : ""}`);
await browser.close();
server.close();
console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
