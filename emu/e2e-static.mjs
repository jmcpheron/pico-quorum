// docs/emu/ (node emu/build.mjs) as GitHub Pages serves it: a plain static server under
// /pico-quorum/, no COOP/COEP headers. Chromium checks that the page isolates itself (the service
// worker), boots MicroPython from boot.json, shows the release fingerprint it was built with, gets
// keys through SharedArrayBuffer, keeps the chip state and a random software key in the browser,
// marks edited files, runs the console on the Safes saved in the app, and breaks no CSP rule.
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
const BASE = `http://127.0.0.1:${server.address().port}/pico-quorum/`;

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

check(!csp.length, `no CSP violations${csp.length ? ": " + csp.slice(0, 3).join(" | ") : ""}`);
check(!errors.length, `no page errors${errors.length ? ": " + errors.join("; ") : ""}`);
check(outside.every((u) => /safe\.global/.test(u)), `nothing left the machine but the console's calls to Safe's service (refused here)${outside.length ? `: ${[...new Set(outside.map((u) => new URL(u).host))].join(", ")}` : ""}`);
await browser.close();
server.close();
console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
