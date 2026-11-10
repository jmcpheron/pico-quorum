// The UI lab's explorer (docs/quorum-ui/lab/explore/) in Chromium, served as GitHub Pages serves
// docs/: it asks for nothing outside the site and trips nothing in its Content-Security-Policy, its
// buttons walk the flows, a hold signs only once its time has really passed, and a press nobody
// walked says so. Nothing leaves the machine: any other request is refused and counted.
//   (cd emu && npm ci) && node tools/uilab/build.mjs && node tools/uilab/e2e.mjs     (PQ_CHROMIUM=/path/to/chrome)
import { createServer } from "node:http";
import { readFileSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { chromium } from "../../emu/node_modules/playwright-core/index.mjs";
import { ROOT } from "../../emu/core/workspace.mjs";

const DOCS = join(ROOT, "docs");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png",
  ".svg": "image/svg+xml", ".woff2": "font/woff2" };
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };

const missing = [];
const srv = createServer((req, res) => {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  let f = join(DOCS, normalize(path).replace(/^(\.\.[/\\])+/, ""));
  try { if (statSync(f).isDirectory()) f = join(f, "index.html"); res.writeHead(200, { "Content-Type": TYPES[extname(f)] || "application/octet-stream" }); res.end(readFileSync(f)); }
  catch { missing.push(path); res.writeHead(404); res.end(); }
});
await new Promise((r) => srv.listen(0, "127.0.0.1", r));
const BASE = `http://localhost:${srv.address().port}/`, PAGE = BASE + "quorum-ui/lab/explore/";

const browser = await chromium.launch({ executablePath: process.env.PQ_CHROMIUM || undefined, args: ["--no-proxy-server"] });
const ctx = await browser.newContext({ viewport: { width: 1100, height: 900 } });
const outside = [], errors = [];
await ctx.route("**/*", (route) => { const u = route.request().url(); if (u.startsWith(BASE)) return route.continue(); outside.push(u); return route.abort(); });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error" || /Content Security Policy|Refused to/.test(m.text())) errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(e.message));

const map = JSON.parse(readFileSync(join(DOCS, "quorum-ui/lab/explore/map.json"), "utf8")).boards[0];
const flow = (id) => map.flows.find((f) => f.id === id);
const at = () => page.evaluate(() => location.hash.slice(1));
const shown = async () => (await page.getAttribute("#screen", "src")).slice(6, 18);
const open = async (hash) => { await page.goto(PAGE + "#" + hash); await page.reload(); await page.waitForSelector("#D2"); };
const hold = async (key, ms) => {
  const b = await page.locator("#" + key).boundingBox();
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(ms);
  await page.mouse.up();
  await page.waitForTimeout(150);
};

await open("");
check((await page.locator("#flows button").count()) === map.flows.length && (await at()) === `${map.flows[0].id}/0`,
  `the page lists the ${map.flows.length} flows and opens on the first`);
check((await page.locator("#grid .tile").count()) >= 20 && (await page.locator("#screen").evaluate((i) => i.naturalWidth)) === map.w,
  "every screen has a tile, and the screen's picture loaded");

// a flow by the console's own buttons: D2 through every page, then held
const approve = flow("approve"), signAt = approve.steps.findIndex((s) => s.view === "result/signed");
await open("approve/0");
const presses = approve.steps.findIndex((s) => s.do === "hold D2");
for (let i = 0; i < presses; i++) await page.click("#D2");
check((await at()) === `approve/${presses}` && (await shown()) === approve.steps[presses - 1].to, `D2 pressed ${presses} times: every page, each its own frame`);
await hold("D2", 1500);
const early = await at();
check(early.startsWith("let-go/") && (await page.textContent("#facts")).includes("review/hash"),
  `Sign held 1.5 s and let go: not signed, back on the page (${early})`);
await open(`approve/${presses}`);
await hold("D2", 2600);
check((await at()) === `approve/${signAt + 2}` && (await page.textContent("#facts")).includes("result/signed"), "Sign held past 2 s, then let go: signed");

// a red page says so; a press off the flow goes where another flow walked it; D1 held is its own input
await open("red/1");
check(await page.locator("#device").evaluate((d) => d.classList.contains("red")), "a red transaction's page is marked red");
await open("approve/0");
await page.click("#D0");
check((await at()) === "tabs/1", "D0 on home, off the approve flow: the tabs flow takes over");
await open("read/3");
await hold("D1", 1300);
check((await at()) === "read/4", "D1 held 1 s: back one page");
await open("crashed/0");
await page.click("#D2");
check((await at()) === "crashed/0" && /No flow does this here yet/.test(await page.textContent("#note")), "a press no flow walked: it says so and stays");
await open("tabs/0");
await page.keyboard.press("1");
check((await at()) === "tabs/1", "1 on the keyboard is D0");
await page.click("#step");
await page.click("#back");
check((await at()) === "tabs/1", "Next and Back step through a flow");

check(!outside.length, `nothing asked for outside the site${outside.length ? ": " + outside.slice(0, 3).join(", ") : ""}`);
check(!missing.length, `every file the page asked for is there${missing.length ? ": " + missing.slice(0, 3).join(", ") : ""}`);
check(!errors.length, `no errors and nothing the Content-Security-Policy refused${errors.length ? ": " + errors.slice(0, 3).join(" | ") : ""}`);
await browser.close();
srv.close();
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
