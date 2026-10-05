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
const ABI = [...S.SAFE_ABI, ...P.ERC20_ABI, ...S.SIGNER_ABI];
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
const svc = { txs: [], refuseNext: null, posts: [] };
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
  await page.fill("#signer-key", `${x} ${y.slice(0, 63)}0`);
  await page.getByRole("button", { name: "Show its signer" }).click();
  check(/isn't a P-256 public key|Paste a deploy link/.test(await text("[role=alert]")), "#/signer: a key that isn't on the curve is refused");
  await page.fill("#signer-key", `https://jmcpheron.github.io/pico-quorum/app/#/signer/${x}/${y}`);
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

check(!errors.length, `no page errors${errors.length ? ": " + errors.join("; ") : ""}`);
check(!outside.length, `no request left the fakes${outside.length ? ": " + outside.join(", ") : ""}`);
await browser.close();
server.close();
console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
