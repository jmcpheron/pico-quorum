// docs/emu/ (node emu/build.mjs) as GitHub Pages serves it: a plain static server under
// /pico-quorum/, no COOP/COEP headers. Chromium checks that the page isolates itself (the service
// worker), boots MicroPython from boot.json, shows the release fingerprint it was built with, gets
// keys through SharedArrayBuffer, keeps the chip state and a random software key in the browser,
// marks edited files, runs the console on the Safes saved in the app, and breaks no CSP rule. Then
// docs/console/: it asks for a passkey, then a Safe, then runs the console; its buttons reach it.
// Nothing leaves the machine: any other request is refused and counted.
//   cd emu && npm ci && node build.mjs && node e2e-static.mjs     (PQ_CHROMIUM=/path/to/chrome)
import { createServer } from "node:http";
import { readFileSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright-core";
import { ROOT } from "./core/workspace.mjs";

const DOCS = join(ROOT, "docs");
const BOOT = JSON.parse(readFileSync(join(DOCS, "emu", "boot.json"), "utf8"));
const short = `${BOOT.release.slice(0, 4)}·${BOOT.release.slice(4, 8)}`;
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".wasm": "application/wasm", ".stl": "model/stl", ".txt": "text/plain" };
const server = createServer((req, res) => {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (!path.startsWith("/pico-quorum/")) { res.writeHead(404); return res.end(); }
  let f = join(DOCS, normalize(path.slice("/pico-quorum/".length)).replace(/^(\.\.[/\\])+/, ""));
  try { if (statSync(f).isDirectory()) f = join(f, "index.html"); res.writeHead(200, { "Content-Type": TYPES[extname(f)] || "application/octet-stream" }); res.end(readFileSync(f)); }
  catch { res.writeHead(404); res.end(); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://localhost:${server.address().port}/pico-quorum/`;     // localhost, not 127.0.0.1: WebAuthn refuses an IP as the site

const browser = await chromium.launch({ executablePath: process.env.PQ_CHROMIUM || undefined, args: ["--no-proxy-server"] });
const ctx = await browser.newContext({ viewport: { width: 1300, height: 820 } });
const outside = [], csp = [], errors = [];
await ctx.route("**/*", (route) => { const u = route.request().url(); if (u.startsWith(BASE)) return route.continue(); outside.push(u); return route.abort(); });
const page = await ctx.newPage();
page.on("console", (m) => { if (/Content Security Policy|Refused to/.test(m.text())) csp.push(m.text()); });
page.on("pageerror", (e) => errors.push(e.message));

const log = () => page.locator("#log").innerText();
async function repl(code, expect, what) {
  await page.fill("#repl", code);
  await page.press("#repl", "Enter");
  try { await page.waitForFunction(([re, fl]) => new RegExp(re, fl).test(document.querySelector("#log").innerText), [expect.source, expect.flags], { timeout: 15000 }); check(true, what); }
  catch { check(false, `${what} (log ends: ${(await log()).slice(-200).replace(/\n/g, " | ")})`); }
}
async function booted() {
  await page.waitForFunction(() => self.crossOriginIsolated && /running|error/.test(document.querySelector("#conn")?.textContent || ""), null, { timeout: 60000 });
}

// 1. first visit: the service worker takes over, the page reloads once, isolated
await page.goto(BASE + "emu/");
await booted();
check(await page.evaluate(() => self.crossOriginIsolated && typeof SharedArrayBuffer === "function"), "Pages-like hosting: the page isolates itself (COOP/COEP from sw.js), SharedArrayBuffer available");
check(/running mock/.test(await page.locator("#conn").innerText()), "no Safes saved in the app: the Pico wallet (mock) runs");
await page.waitForSelector("#release img");
const rel = await page.locator("#release").innerText();
check(rel.includes(short) && !rel.includes("edited"), `the toolbar shows release ${short}, the fingerprint this build was made from, computed again in the browser`);
check(await page.locator("#ship").isHidden() && await page.locator("#device").isHidden(), "no USB controls on the static page");

// 2. Python runs, and keys reach it while it does
await repl("print(6 * 7)", /^42$/m, "the REPL runs Python on the virtual Pico");
await page.click("#stage");
await page.keyboard.down("9");                   // A, held
await repl("import _emu; print('A=%d' % _emu.pin_read(15))", /A=0/, "a held key reaches Python through SharedArrayBuffer (GP15 pulled low)");
await page.keyboard.up("9");

// 3. the chip state and the software key stay in this browser
await repl(`_emu.chip_save('{"e2e": 1}'); print('saved')`, /^saved$/m, "the chip state saves");
check(await page.evaluate(() => localStorage.getItem("emu.chip")) === '{"e2e": 1}', "it is kept in localStorage");
const key = await page.evaluate(() => localStorage.getItem("emu.keybin"));
check(/^[0-9a-f]{64}$/.test(key || "") && key !== "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20", "the software key is random, made in this browser (not the local emulator's fixed test key)");
await page.reload();
await booted();
await repl("import _emu; print('chip:' + _emu.chip_load())", /chip:\{"e2e": 1\}/, "after a reload the chip state is still there");
await repl("print('key:' + open('key.bin','rb').read().hex())", new RegExp(`key:${key}`), "and the same software key");

// 4. an edited console file: a different fingerprint, marked as edited
const cfg = BOOT.files.find((f) => f.name === "quorum_cfg.py").text;
await page.evaluate((t) => localStorage.setItem("emu.file:quorum_cfg.py", JSON.stringify({ text: t + "\n# edited\n", src: "firmware" })), cfg);
await page.reload();
await booted();
const rel2 = await page.locator("#release").innerText();
check(rel2.includes("edited") && !rel2.includes(short), `an edited console file: the toolbar says edited, with another fingerprint (${rel2.trim()})`);
await repl("import image; print('img:' + image.RELEASE[:8])", new RegExp(`img:(?!${BOOT.release.slice(0, 8)})[0-9a-f]{8}`), "and the firmware's own image.RELEASE is that other fingerprint, never the release's");
await page.evaluate(() => localStorage.removeItem("emu.file:quorum_cfg.py"));

// 5. Safes saved in the app: the console runs on them, against Safe's own service
await page.evaluate(() => { localStorage.setItem("pq.safes", JSON.stringify([{ chain: "basesep", address: "0x1234567890abcdef1234567890abcdef12345678", name: "Test Safe" }])); localStorage.setItem("pq.apiKey", JSON.stringify("k-e2e")); localStorage.removeItem("emu.main"); });
await page.reload();
await booted();
check(await page.locator("#main").inputValue() === "quorum", "with a Safe saved in the app, the console (quorum) is the module");
await repl("import secrets; print('safes:%d %s %s' % (secrets.QUORUM_SAFES[0]['chainId'], secrets.APP_URL, secrets.QUORUM_API_KEY))", /safes:84532 None k-e2e/, "its secrets.py: the saved Safe on Base Sepolia, the app's API key, no APP_URL");

// 6. your passkey: made with WebAuthn (a virtual platform authenticator with user verification,
// the path Touch ID takes), and the console's key: an assertion over a hash, checked in Python
const cdp = await ctx.newCDPSession(page);
await cdp.send("WebAuthn.enable");
const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", { options: {
  protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
page.on("dialog", (d) => d.accept());           // the one-time note before the first signature
await page.selectOption("#keymode", "passkey");
check(await page.locator("#mkpasskey").isVisible(), "key: your passkey, none yet: the page offers to make one");
await page.click("#mkpasskey");
await page.waitForFunction(() => !!localStorage.getItem("emu.passkey"), null, { timeout: 15000 });
await booted();
const cred = JSON.parse(await page.evaluate(() => localStorage.getItem("emu.passkey")));
check(cred.rpId === "localhost" && /^[0-9a-f]{64}$/.test(cred.x) && /^[0-9a-f]{64}$/.test(cred.y), "made a P-256 passkey for this site; its public key is kept in this browser, its private key never leaves the authenticator");
await repl("import signer; _s = signer.load(); print('signer:' + _s.name)", /signer:passkey/, "the console's signer is now the passkey");
const PY_CHECK = "import webauthn, hashlib, p256; _a, _f, _r, _t = _s.assertion('0x' + 'ab' * 32); _x, _y = _s.pubkey(); _c = '{\"type\":\"webauthn.get\",\"challenge\":\"%s\",%s}' % (webauthn.b64url(bytes([0xab] * 32)), _f); print('verified:%s uv:%d' % (p256.verify(_x, _y, hashlib.sha256(_a + hashlib.sha256(_c.encode()).digest()).digest(), _r, _t), _a[32] & 4))";
await repl(PY_CHECK, /verified:True uv:4/, "the passkey's assertion over a hash, rebuilt as Safe's signer rebuilds it, verifies in the console's own P-256 code, with UV");
await repl("print('fields:' + _f)", /fields:"origin":"http:\/\/localhost:\d+","crossOrigin":false/, "its clientData fields are the browser's own (origin, crossOrigin)");
await cdp.send("WebAuthn.setUserVerified", { authenticatorId, isUserVerified: false });
await repl("exec(\"try:\\n    _s.assertion('0x' + 'cd' * 32)\\nexcept Exception as _e:\\n    print('refused:' + str(_e))\")", /refused:.*(UV|verif|NotAllowedError)/i, "without user verification it is refused (by the browser, or the page checks the UV flag): the console gets an error, never a signature");

// 7. the console page (docs/console/): only the console, your passkey as its key. A fresh browser
// profile: no passkey, no Safes. It asks for each in turn, then runs the firmware from ../emu/.
const ctx2 = await browser.newContext({ viewport: { width: 1000, height: 900 } });
// the console may only reach Safe's service; the app (its passkey page) also reads each chain: refused, not counted
const offsite = (route) => {
  const u = route.request().url();
  if (u.startsWith(BASE)) return route.continue();
  if (!/\/app\//.test(route.request().frame()?.url() || "")) outside.push(u);
  return route.abort();
};
await ctx2.route("**/*", offsite);
const con = await ctx2.newPage();
con.on("console", (m) => { if (/Content Security Policy|Refused to/.test(m.text())) csp.push("console page: " + m.text()); });
con.on("pageerror", (e) => errors.push("console page: " + e.message));
await con.goto(BASE + "console/");
await con.waitForFunction(() => self.crossOriginIsolated && !document.querySelector("#overlay").hidden, null, { timeout: 30000 });
check(await con.evaluate(() => self.crossOriginIsolated), "console page: it isolates itself too (its own sw.js, which also covers the files it runs from ../emu/)");
check(/Make a passkey/.test(await con.locator("#overlay").innerText()), "no passkey yet: the screen asks you to make one");
await con.waitForSelector("#release img");
check((await con.locator("#release").innerText()).includes(short), `the bar shows release ${short}, computed in the browser over the files it runs`);
const cdp2 = await ctx2.newCDPSession(con);
await cdp2.send("WebAuthn.enable");
const auth2 = (await cdp2.send("WebAuthn.addVirtualAuthenticator", { options: {
  protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } })).authenticatorId;
check(/I already have one/.test(await con.locator("#overlay").innerText()), "it also offers to use a passkey you already have");
await con.click("#overlay .go:not(.alt)");
await con.waitForFunction(() => /No Safe/.test(document.querySelector("#overlay").innerText), null, { timeout: 15000 });
check(!!JSON.parse(await con.evaluate(() => localStorage.getItem("emu.passkey")))?.x, "Make a passkey: made, kept in this browser; next the screen asks for a Safe, with a link to the app");
check(/your passkey, for localhost/.test(await con.locator("#key").innerText()) && await con.locator('#key a[href="../app/#/passkey"]').count() === 1,
  "the panel names the key, your passkey for this site, and links to its page in the app");
const made = JSON.parse(await con.evaluate(() => localStorage.getItem("emu.passkey")));
const synced = (await cdp2.send("WebAuthn.getCredentials", { authenticatorId: auth2 })).credentials;
await con.evaluate(() => localStorage.setItem("pq.safes", JSON.stringify([{ chain: "basesep", address: "0x1234567890abcdef1234567890abcdef12345678", name: "Test Safe" }])));
await con.reload();
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
// the app's page for it: the owner address, the same on every chain, and the way into a Safe
const app2 = await ctx2.newPage();
await app2.goto(BASE + "app/#/passkey");
await app2.waitForSelector("h1:has-text('Your passkey')");
const owner2 = (await app2.locator(".card .inline-ident code").first().innerText()).trim();
check(/^0x[0-9a-fA-F]{40}$/.test(owner2) && await app2.locator('a[href*="/new/add/' + owner2 + '"]').count() === 1,
  `the app's Your passkey page: its owner address (${owner2.slice(0, 10)}…) and Add owner for the saved Safe, owner filled in`);
await ctx2.close();

// 8. the same passkey in another browser (iCloud Keychain syncing it to the iPhone, say): this one
// doesn't have its public key, so "I already have one" signs twice and works it out
const ctx3 = await browser.newContext({ viewport: { width: 1000, height: 900 } });
await ctx3.route("**/*", offsite);
const con3 = await ctx3.newPage();
con3.on("console", (m) => { if (/Content Security Policy|Refused to/.test(m.text())) csp.push("console page (found): " + m.text()); });
con3.on("pageerror", (e) => errors.push("console page (found): " + e.message));
const cdp3 = await ctx3.newCDPSession(con3);
await cdp3.send("WebAuthn.enable");
const auth3 = (await cdp3.send("WebAuthn.addVirtualAuthenticator", { options: {
  protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } })).authenticatorId;
for (const c of synced) await cdp3.send("WebAuthn.addCredential", { authenticatorId: auth3, credential: c });
await con3.goto(BASE + "console/");
await con3.waitForFunction(() => self.crossOriginIsolated && /I already have one/.test(document.querySelector("#overlay")?.innerText || ""), null, { timeout: 30000 });
await con3.click("#overlay .go.alt");
const found = await con3.waitForFunction(() => /No Safe/.test(document.querySelector("#overlay").innerText), null, { timeout: 20000 }).then(() => true, () => false);
const cred3 = JSON.parse(await con3.evaluate(() => localStorage.getItem("emu.passkey")) || "null");
check(found && cred3?.x === made.x && cred3?.y === made.y && cred3?.id === made.id,
  `I already have one: from two signatures, the same public key as where it was made${found ? "" : ` (overlay: ${(await con3.locator("#overlay").innerText()).slice(0, 160)})`}`);
const app3 = await ctx3.newPage();
await app3.goto(BASE + "app/#/passkey");
await app3.waitForSelector("h1:has-text('Your passkey')");
check((await app3.locator(".card .inline-ident code").first().innerText()).trim() === owner2, "so the same owner address: one passkey, one Safe owner, whichever device signs");
await ctx3.close();

check(!csp.length, `no CSP violations${csp.length ? ": " + csp.slice(0, 3).join(" | ") : ""}`);
check(!errors.length, `no page errors${errors.length ? ": " + errors.join("; ") : ""}`);
check(outside.every((u) => /safe\.global/.test(u)), `nothing left the machine but the console's calls to Safe's service (refused here)${outside.length ? `: ${[...new Set(outside.map((u) => new URL(u).host))].join(", ")}` : ""}`);
await browser.close();
server.close();
console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
