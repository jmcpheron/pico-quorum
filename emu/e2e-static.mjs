// The console page (node emu/build.mjs) as GitHub Pages serves it at picoquorum.app: a plain static
// server at the root, no COOP/COEP headers. Chromium checks that emu/, where the emulator's page was,
// sends you to the console; that the console page isolates itself (its service worker), shows the release
// fingerprint, asks for a passkey and then a Safe, runs the console, and its buttons reach it; that it
// asks for nothing outside its folder; and that the same passkey works from another browser. Then the
// folder on its own: its SHA256SUMS and firmware/ checked as docs/guide/BROWSER.md does, and the
// folder served alone at the root of localhost, as a copy on your own computer. Then a real signature:
// Safe's service is tools/mock-tx-service/sim.mjs, the console signs through its own buttons with a
// virtual authenticator, and the confirmation must verify; no user verification, no signature; and
// the CSP refuses any other host, in the page and in its worker.
// Nothing leaves the machine: any other request is refused and counted.
//   cd emu && npm ci && node build.mjs && node e2e-static.mjs     (PQ_CHROMIUM=/path/to/chrome;
//   tools/mock-tx-service needs npm ci too)
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright-core";
import { ROOT } from "./core/workspace.mjs";

const DOCS = join(ROOT, "docs");
const BOOT = JSON.parse(readFileSync(join(DOCS, "console", "boot.json"), "utf8"));
const short = `${BOOT.release.slice(0, 4)}·${BOOT.release.slice(4, 8)}`;
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".wasm": "application/wasm", ".stl": "model/stl", ".txt": "text/plain", ".svg": "image/svg+xml", ".woff2": "font/woff2" };
/** A plain static server: dir served under prefix, nothing else. .asked: every path asked for (the
 *  server sees what the service worker fetches too, which the browser context's route doesn't). */
async function serve(dir, prefix) {
  const asked = [];
  const srv = createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
    asked.push(path);
    if (!path.startsWith(prefix)) { res.writeHead(404); return res.end(); }
    let f = join(dir, normalize(path.slice(prefix.length)).replace(/^(\.\.[/\\])+/, ""));
    try { if (statSync(f).isDirectory()) f = join(f, "index.html"); res.writeHead(200, { "Content-Type": TYPES[extname(f)] || "application/octet-stream" }); res.end(readFileSync(f)); }
    catch { res.writeHead(404); res.end(); }
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  return Object.assign(srv, { asked });
}
const server = await serve(DOCS, "/");
const BASE = `http://localhost:${server.address().port}/`;     // localhost, not 127.0.0.1: WebAuthn refuses an IP as the site
const SITE_APP = "https://picoquorum.app/app/";            // where a copy on localhost sends its app links

const browser = await chromium.launch({ executablePath: process.env.PQ_CHROMIUM || undefined, args: ["--no-proxy-server"] });
const outside = [], csp = [], errors = [];
const watch = (pg, what) => {
  pg.on("console", (m) => { if (/Content Security Policy|Refused to/.test(m.text())) csp.push(`${what}: ${m.text()}`); });
  pg.on("pageerror", (e) => errors.push(`${what}: ${e.message}`));
};

// 1. where the emulator's page was: its old address lands on the console
const ctx = await browser.newContext();
await ctx.route("**/*", (route) => { const u = route.request().url(); if (u.startsWith(BASE)) return route.continue(); outside.push(u); return route.abort(); });
const page = await ctx.newPage();
await page.goto(BASE + "emu/");
await page.waitForURL(BASE + "console/", { timeout: 15000 }).catch(() => {});
check(page.url() === BASE + "console/", `the emulator's old address, emu/, sends you to the console (${page.url().slice(BASE.length - 1)})`);
await ctx.close();

// 7. the console page (docs/console/): only the console, your passkey as its key. A fresh browser
// profile: no passkey, no Safes. It asks for each in turn, then runs the firmware.
const ctx2 = await browser.newContext({ viewport: { width: 1000, height: 900 } });
// the console may only reach Safe's service; the app (its passkey page) also reads each chain: refused, not counted
const offsite = (route) => {
  const u = route.request().url();
  if (u.startsWith(BASE)) return route.continue();
  if (!/\/app\//.test(route.request().frame()?.url() || "")) outside.push(u);
  return route.abort();
};
await ctx2.route("**/*", offsite);
const from = server.asked.length;                // from here on, the server hears only the console page
const con = await ctx2.newPage();
watch(con, "console page");
await con.goto(BASE + "console/");
await con.waitForFunction(() => self.crossOriginIsolated && !document.querySelector("#overlay").hidden, null, { timeout: 30000 });
check(await con.evaluate(() => self.crossOriginIsolated), "console page: it isolates itself too (its own sw.js)");
check(/Make a passkey/.test(await con.locator("#overlay").innerText()), "no passkey yet: the screen asks you to make one");
await con.waitForSelector("#release img");
check((await con.locator("#release").innerText()).includes(short), `the bar shows release ${short}, computed in the browser over the files it runs`);
const cdp2 = await ctx2.newCDPSession(con);
await cdp2.send("WebAuthn.enable");
const auth2 = (await cdp2.send("WebAuthn.addVirtualAuthenticator", { options: {
  protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } })).authenticatorId;
check(/I already have one/.test(await con.locator("#overlay").innerText()), "it also offers to use a passkey you already have");
await con.click("#overlay .go:not(.alt)");
await con.waitForFunction(() => /Add a Safe/.test(document.querySelector("#overlay").innerText), null, { timeout: 15000 });
check(!!JSON.parse(await con.evaluate(() => localStorage.getItem("emu.passkey")))?.x, "Make a passkey: made, kept in this browser; next the screen asks for a Safe");
const conOwner = (await con.locator("#overlay .owner .addr").innerText()).trim();
check(/^0x[0-9a-fA-F]{40}$/.test(conOwner) && (await con.locator("#owner .addr").innerText()).trim() === conOwner,
  `the screen and the panel show the passkey's owner address, to add to a Safe (${conOwner.slice(0, 10)}…)`);
check(!/Launch app|Connect wallet|deploy link|MetaMask|Rabby/.test(await con.locator("body").innerText()), "the page asks for no wallet: its passkey is its key");
check(await con.evaluate(() => ["key-row", "safes-row", "owner-row"].map((id) => document.getElementById(id).classList.contains("done")).join()) === "true,false,false",
  "the panel's steps: 1, the passkey, done; 2, a Safe, and 3, an owner, still to do");
const made = JSON.parse(await con.evaluate(() => localStorage.getItem("emu.passkey")));
check(/made for localhost/.test(await con.locator("#key").innerText()) && await con.locator(`#owner-how a[href="${SITE_APP}#/signer/${made.x}/${made.y}"]`).count() === 1,
  "the panel names the key, your passkey for this site, and (on localhost: a copy on your own computer) links an owner of the Safe to its signer's page in the app on the site, its key in the link");
check(await con.evaluate(() => document.querySelector("header nav a").href) === "https://picoquorum.app/guide/",
  "and the site's header links go to the site");
const synced = (await cdp2.send("WebAuthn.getCredentials", { authenticatorId: auth2 })).credentials;
// adding a Safe you already have, right there: a bad address is refused, Safe{Wallet}'s "basesep:0x…" picks the chain
await con.fill("#overlay .add-safe input >> nth=0", "0x1234");
await con.click("#overlay .add-safe .go");
check(/isn't an address/.test(await con.locator("#overlay .add-safe .bad").innerText()) && await con.evaluate(() => !localStorage.getItem("pq.safes")), "Add Safe: an address that isn't one is refused, nothing saved");
await con.fill("#overlay .add-safe input >> nth=0", "0x1234567890AbCdEf1234567890abcdef12345678");
await con.click("#overlay .add-safe .go");
check(/checksum/.test(await con.locator("#overlay .add-safe .bad").innerText()), "and so is one with the wrong checksum capitals");
await con.fill("#overlay .add-safe input >> nth=0", "basesep:0x1234567890abcdef1234567890abcdef12345678");
await con.locator("#overlay .add-safe input >> nth=0").dispatchEvent("input");
await con.fill("#overlay .add-safe input >> nth=1", "Test Safe");
await con.click("#overlay .add-safe .go");
const savedNow = JSON.parse(await con.evaluate(() => localStorage.getItem("pq.safes")) || "[]");
check(savedNow.length === 1 && savedNow[0].chain === "basesep" && savedNow[0].address === "0x1234567890AbcdEF1234567890aBcdef12345678" && savedNow[0].name === "Test Safe",
  `Add Safe: saved to the app's list, chain from the prefix, address checksummed (${JSON.stringify(savedNow)})`);
const drew = await con.waitForFunction(() => document.querySelector("#overlay").hidden && +(document.querySelector("#screen").dataset.frames || 0) > 0, null, { timeout: 60000 }).then(() => true, () => false);
check(drew, `with a passkey and a saved Safe, the console boots and draws its screen${drew ? "" : ` (output ends: ${(await con.evaluate(() => document.querySelector("#out").textContent)).slice(-400).replace(/\n/g, " | ")}; errors: ${errors.join("; ")})`}`);
const litNow = () => con.evaluate(() => { const d = document.querySelector("#screen").getContext("2d").getImageData(0, 0, 240, 240).data; let n = 0; for (let i = 0; i < d.length; i += 4) n += d[i] + d[i + 1] + d[i + 2] > 60; return n; });
let lit = await litNow();
for (let i = 0; i < 25 && lit <= 2000; i++) { await con.waitForTimeout(200); lit = await litNow(); }    // the splash draws in steps
check(lit > 2000, `the screen has something on it (${lit} lit pixels)`);
const shot = () => con.evaluate(() => document.querySelector("#screen").toDataURL());
await con.waitForTimeout(3000);                // past the splash, to the home grid
const before = await shot();
const pressed = async (sel) => { await con.locator(sel).dispatchEvent("pointerdown"); await con.waitForTimeout(250); await con.locator(sel).dispatchEvent("pointerup"); };
await pressed('[data-key="right"]');
let moved = false;
for (let i = 0; i < 20 && !moved; i++) { await con.waitForTimeout(150); moved = (await shot()) !== before; }
check(moved, "the on-screen joystick reaches the firmware: the screen changes");
const before2 = await shot();
await con.keyboard.down("ArrowLeft"); await con.waitForTimeout(250); await con.keyboard.up("ArrowLeft");
moved = false;
for (let i = 0; i < 20 && !moved; i++) { await con.waitForTimeout(150); moved = (await shot()) !== before2; }
check(moved, "and so does the keyboard (an arrow key)");
check(/Test Safe · Base Sepolia/.test(await con.locator("#safes").innerText()) && await con.locator("#safes .link").count() === 1,
  "the panel lists the Safe, with Remove");
await con.waitForFunction(() => !/checking/.test(document.querySelector("#safes .status").textContent), null, { timeout: 15000 }).catch(() => {});
check(/couldn't check/.test(await con.locator("#safes .status").innerText()), "its owner check asks Safe's service (refused here, and the page says so)");
check(await con.locator("#add-safe .add-safe").count() === 1, "and offers to add another");
const consoleAsked = new Set(server.asked.slice(from));
const strays = [...consoleAsked].filter((p) => !p.startsWith("/console/"));
check(consoleAsked.size > 60 && !strays.length, `the console page, its worker and MicroPython asked the site for nothing outside console/ (${consoleAsked.size} files)${strays.length ? `: ${strays.slice(0, 4).join(", ")}` : ""}`);
// the app's page for it: the owner address, the same on every chain, and the way into a Safe
const app2 = await ctx2.newPage();
await app2.goto(BASE + "app/#/passkey");
await app2.waitForSelector("h1:has-text('Your passkey')");
const owner2 = (await app2.locator(".card .inline-ident code").first().innerText()).trim();
check(/^0x[0-9a-fA-F]{40}$/.test(owner2) && await app2.locator('a[href*="/new/add/' + owner2 + '"]').count() === 1,
  `the app's Your passkey page: its owner address (${owner2.slice(0, 10)}…) and Add owner for the saved Safe, owner filled in`);
check(owner2 === conOwner, "the console page and the app show the same owner address");
await ctx2.close();

// 8. the same passkey in another browser (iCloud Keychain syncing it to the iPhone, say): this one
// doesn't have its public key, so "I already have one" signs twice and works it out
const ctx3 = await browser.newContext({ viewport: { width: 1000, height: 900 } });
await ctx3.route("**/*", offsite);
const con3 = await ctx3.newPage();
watch(con3, "console page (found)");
const cdp3 = await ctx3.newCDPSession(con3);
await cdp3.send("WebAuthn.enable");
const auth3 = (await cdp3.send("WebAuthn.addVirtualAuthenticator", { options: {
  protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } })).authenticatorId;
for (const c of synced) await cdp3.send("WebAuthn.addCredential", { authenticatorId: auth3, credential: c });
await con3.goto(BASE + "console/");
await con3.waitForFunction(() => self.crossOriginIsolated && /I already have one/.test(document.querySelector("#overlay")?.innerText || ""), null, { timeout: 30000 });
await con3.click("#overlay .go.alt");
const found = await con3.waitForFunction(() => /Add a Safe/.test(document.querySelector("#overlay").innerText), null, { timeout: 20000 }).then(() => true, () => false);
const cred3 = JSON.parse(await con3.evaluate(() => localStorage.getItem("emu.passkey")) || "null");
check(found && cred3?.x === made.x && cred3?.y === made.y && cred3?.id === made.id,
  `I already have one: from two signatures, the same public key as where it was made${found ? "" : ` (overlay: ${(await con3.locator("#overlay").innerText()).slice(0, 160)})`}`);
const app3 = await ctx3.newPage();
await app3.goto(BASE + "app/#/passkey");
await app3.waitForSelector("h1:has-text('Your passkey')");
check((await app3.locator(".card .inline-ident code").first().innerText()).trim() === owner2, "so the same owner address: one passkey, one Safe owner, whichever device signs");
await ctx3.close();

// 9. the folder as a copy: its SHA256SUMS and firmware/ checked the way docs/guide/BROWSER.md does
// with sha256sum, then the folder served alone at the root of localhost (python3 -m http.server)
const CON = join(DOCS, "console");
const sha = (b) => createHash("sha256").update(b).digest("hex");
const files = [];
(function walk(d, pre) { for (const f of readdirSync(d)) statSync(join(d, f)).isDirectory() ? walk(join(d, f), `${pre}${f}/`) : files.push(pre + f); })(CON, "");
const sums = readFileSync(join(CON, "SHA256SUMS"), "utf8").trim().split("\n").map((l) => [l.slice(0, 64), l.slice(66)]);
check(sums.every(([h, f]) => sha(readFileSync(join(CON, f))) === h) && sums.length === files.length - 2 &&
  files.filter((f) => f !== "SHA256SUMS" && f !== "BUILD.json").every((f) => sums.some(([, g]) => g === f)),
  `SHA256SUMS: every file in console/ but itself and BUILD.json, each hash right (${sums.length} files)`);
const fw = readdirSync(join(CON, "firmware")).sort();
const fwPrint = sha(fw.map((f) => `${f}\0${sha(readFileSync(join(CON, "firmware", f)))}\n`).join(""));
check(fwPrint === BOOT.release && fw.length === BOOT.firmware.length, `firmware/ is the console image, and hashes to its release fingerprint ${short}`);
check(!files.some((f) => /(^|\/)[_.]/.test(f)), "no file Jekyll would leave out on Pages (a name starting with _ or .)");

const alone = await serve(CON, "/");
const COPY = `http://localhost:${alone.address().port}/`;
const ctx4 = await browser.newContext({ viewport: { width: 1000, height: 900 } });
await ctx4.route("**/*", (route) => { const u = route.request().url(); if (u.startsWith(COPY)) return route.continue(); outside.push(u); return route.abort(); });
const con4 = await ctx4.newPage();
watch(con4, "console copy");
const cdp4 = await ctx4.newCDPSession(con4);
await cdp4.send("WebAuthn.enable");
await cdp4.send("WebAuthn.addVirtualAuthenticator", { options: {
  protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
await con4.goto(COPY);
await con4.waitForFunction(() => self.crossOriginIsolated && /Make a passkey/.test(document.querySelector("#overlay")?.innerText || ""), null, { timeout: 30000 });
await con4.click("#overlay .go:not(.alt)");
await con4.waitForFunction(() => /Add a Safe/.test(document.querySelector("#overlay").innerText), null, { timeout: 15000 });
const cred4 = JSON.parse(await con4.evaluate(() => localStorage.getItem("emu.passkey")));
check(cred4?.rpId === "localhost" && cred4.x !== made.x, "the folder alone, at the root of localhost: it isolates itself and makes a passkey of its own, for localhost");
await con4.fill("#overlay .add-safe input >> nth=0", "basesep:0x1234567890abcdef1234567890abcdef12345678");
await con4.locator("#overlay .add-safe input >> nth=0").dispatchEvent("input");
await con4.click("#overlay .add-safe .go");
const drew4 = await con4.waitForFunction(() => document.querySelector("#overlay").hidden && +(document.querySelector("#screen").dataset.frames || 0) > 0, null, { timeout: 60000 }).then(() => true, () => false);
await con4.waitForSelector("#release img");
check(drew4 && (await con4.locator("#release").innerText()).includes(short) && new Set(alone.asked).size > 60,
  `and boots the console, release ${short}, from nothing but the folder (${new Set(alone.asked).size} files asked for)`);
check(await con4.locator(`#owner-how a[href^="${SITE_APP}#/signer/"]`).count() === 1 && /^0x[0-9a-fA-F]{40}$/.test((await con4.locator("#owner .addr").innerText()).trim()),
  "it shows the copy's passkey's owner address, with its signer's page in the app on the site");
await ctx4.close();
alone.close();

// 10. signing, for real: Safe's service is tools/mock-tx-service/sim.mjs, in this process (its
// hashes come from viem, which shares no code with the firmware). The passkey is an owner of its Safe,
// Alice has proposed a send and signed it; the console reads the queue, the person sees every page and
// holds A, the passkey signs, and the posted confirmation must verify the way the Safe checks it.
const sim = await import("../tools/mock-tx-service/sim.mjs").catch((e) => {
  throw new Error(`tools/mock-tx-service needs its packages (cd tools/mock-tx-service && npm ci): ${e.message}`);
});
const st = { ...sim.fresh(), chainId: 84532, name: "Test Safe" };
const SVC = "https://api.safe.global/tx-service/basesep";
const posted = [], auths = new Set();
const ctx5 = await browser.newContext({ viewport: { width: 1000, height: 900 } });
await ctx5.route("**/*", async (route) => {
  const r = route.request(), u = r.url();
  if (u.startsWith(BASE)) return route.continue();
  if (!u.startsWith(SVC + "/")) { outside.push(u); return route.abort(); }
  const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "authorization, content-type", "access-control-allow-methods": "GET, POST" };
  if (r.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
  auths.add(r.headers().authorization || "");
  const url = new URL(u), path = url.pathname.slice(new URL(SVC).pathname.length);
  const reply = (status, body) => route.fulfill({ status, headers: { ...cors, "content-type": "application/json" }, body: JSON.stringify(body) });
  let m;
  if ((m = path.match(/^\/api\/v1\/safes\/(0x[0-9a-fA-F]{40})\/?$/))) return m[1].toLowerCase() === st.address.toLowerCase() ? reply(200, sim.apiSafe(st)) : reply(404, { detail: "Not found." });
  if ((m = path.match(/^\/api\/v2\/safes\/(0x[0-9a-fA-F]{40})\/multisig-transactions\/?$/))) return reply(200, sim.apiList(st, url.searchParams));
  if ((m = path.match(/^\/api\/v1\/multisig-transactions\/(0x[0-9a-fA-F]{64})\/?$/))) { const t = sim.find(st, m[1]); return t ? reply(200, sim.apiTx(st, t)) : reply(404, {}); }
  if ((m = path.match(/^\/api\/v1\/multisig-transactions\/(0x[0-9a-fA-F]{64})\/confirmations\/?$/)) && r.method() === "POST") {
    const t = sim.find(st, m[1]);
    const res = t ? await sim.confirm(st, t, JSON.parse(r.postData() || "{}").signature || "0x") : { ok: false, error: "no such transaction" };
    posted.push(res);
    return res.ok ? reply(201, {}) : reply(400, { detail: res.error });
  }
  return reply(404, { detail: "Not found." });
});
const con5 = await ctx5.newPage();
watch(con5, "console signing");
con5.on("dialog", (d) => d.accept());           // the one-time note before the first signature
const cdp5 = await ctx5.newCDPSession(con5);
await cdp5.send("WebAuthn.enable");
const auth5 = (await cdp5.send("WebAuthn.addVirtualAuthenticator", { options: {
  protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } })).authenticatorId;
await con5.goto(BASE + "console/");
await con5.waitForFunction(() => self.crossOriginIsolated && /Make a passkey/.test(document.querySelector("#overlay")?.innerText || ""), null, { timeout: 30000 });
await con5.click("#overlay .go:not(.alt)");
await con5.waitForFunction(() => /Add a Safe/.test(document.querySelector("#overlay").innerText), null, { timeout: 15000 });
const cred5 = JSON.parse(await con5.evaluate(() => localStorage.getItem("emu.passkey")));
const mine = sim.registerDevice(st, { name: "the console page's passkey", qx: "0x" + cred5.x, qy: "0x" + cred5.y });
const to = Object.values(sim.BOOK)[0];
const tx5 = await sim.propose(st, { to, value: "50000000000000000" }, { scenario: "send" });
await sim.signAs(st, "alice", tx5);
await con5.evaluate(() => localStorage.setItem("pq.apiKey", JSON.stringify("k-e2e")));
await con5.fill("#overlay .add-safe input >> nth=0", `basesep:${st.address}`);
await con5.locator("#overlay .add-safe input >> nth=0").dispatchEvent("input");
await con5.click("#overlay .add-safe .go");
await con5.waitForFunction(() => document.querySelector("#overlay").hidden && +(document.querySelector("#screen").dataset.frames || 0) > 0, null, { timeout: 60000 });
check((await con5.locator("#owner .addr").innerText()).trim() === mine.address, `the page's owner address is the one the Safe has as an owner (${mine.address.slice(0, 10)}…)`);
const statusOk = await con5.waitForFunction(() => /your passkey is an owner/.test(document.querySelector("#safes")?.innerText || ""), null, { timeout: 15000 }).then(() => true, () => false);
check(statusOk && await con5.evaluate(() => document.querySelector("#owner-row").classList.contains("done")),
  "the panel asks Safe's service, says the passkey is an owner, and marks step 3 done");

// count the page's WebAuthn requests, to know when the console asked the passkey
await con5.evaluate(() => { const get = navigator.credentials.get.bind(navigator.credentials); window.asked = 0; navigator.credentials.get = (o) => { window.asked++; return get(o); }; });
const holdA = async (ms) => { await con5.locator('[data-key="A"]').dispatchEvent("pointerdown"); await con5.waitForTimeout(ms); await con5.locator('[data-key="A"]').dispatchEvent("pointerup"); await con5.waitForTimeout(400); };
// Each press of A opens the transaction, or turns to a page not yet seen; once every page is seen,
// holding it signs. Without user verification first: the passkey is asked, and nothing is posted.
await cdp5.send("WebAuthn.setUserVerified", { authenticatorId: auth5, isUserVerified: false });
for (let i = 0; i < 12 && !(await con5.evaluate(() => window.asked)); i++) await holdA(2600);
await con5.waitForTimeout(1500);
check(await con5.evaluate(() => window.asked) > 0 && !posted.length,
  `without user verification the passkey is asked and refuses: nothing is posted (${await con5.evaluate(() => window.asked)} asked, ${posted.length} posted)`);
await cdp5.send("WebAuthn.setUserVerified", { authenticatorId: auth5, isUserVerified: true });
for (let i = 0; i < 12 && !posted.length; i++) await holdA(2600);
const conf = tx5.confirmations.find((c) => c.owner === mine.address);
check(posted.length === 1 && posted[0].ok && posted[0].owner === mine.address && conf?.signatureType === "CONTRACT_SIGNATURE",
  `held A after seeing every page: the passkey signed, and the confirmation verifies the way the Safe checks it: WebAuthn P-256, over the hash viem computes from the fields (${JSON.stringify(posted.map((p) => p.ok ? "ok" : p.error))})`);
check(tx5.isExecuted === true, "with Alice's, that makes 2 of 2: the Safe executes it");
check(auths.size === 1 && auths.has("Bearer k-e2e"), `every call to Safe's service carried the API key saved in the app (${[...auths].join(", ") || "none"})`);
// the network is Safe's service and this folder, enforced by the browser: in the page, and in the
// worker that makes the firmware's calls (its CSP comes from sw.js's header, not the page's <meta>)
const PROBE = "https://csp-probe.invalid/";
const probe = () => new Promise((done) => {
  self.addEventListener("securitypolicyviolation", (e) => done(e.effectiveDirective), { once: true });
  try { const x = new XMLHttpRequest(); x.open("GET", "https://csp-probe.invalid/", false); x.send(); } catch {}
  setTimeout(() => done(""), 3000);
});
const inPage = await con5.evaluate(probe);
const w5 = con5.workers()[0];
const inWorker = w5 ? await w5.evaluate(probe) : "no worker";
check(inPage === "connect-src" && inWorker === "connect-src", `a request to any other host is refused by the CSP, in the page (${inPage || "allowed"}) and in the worker (${inWorker || "allowed"})`);
await ctx5.close();
for (let i = csp.length - 1; i >= 0; i--) if (csp[i].includes(PROBE.slice(8, -1))) csp.splice(i, 1);     // the probes' own reports

check(!csp.length, `no CSP violations${csp.length ? ": " + csp.slice(0, 3).join(" | ") : ""}`);
check(!errors.length, `no page errors${errors.length ? ": " + errors.join("; ") : ""}`);
check(outside.every((u) => /safe\.global/.test(u)), `nothing left the machine but the console's calls to Safe's service (refused here)${outside.length ? `: ${[...new Set(outside.map((u) => new URL(u).host))].join(", ")}` : ""}`);
await browser.close();
server.close();
console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
