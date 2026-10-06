#!/usr/bin/env node
// The console page for GitHub Pages, docs/console/ (commit it; Pages serves the branch): the console
// alone (emu/console/), its screen and buttons, with your passkey as its key. One folder that holds
// everything it runs and loads nothing from the rest of the site, so a copy of the folder is the
// whole program (docs/guide/BROWSER.md):
//   firmware/       the console image (firmware/manifest.json), the same files a Pico runs, as plain
//                   files: their release fingerprint is the README's, worked out with sha256sum
//   shims/          the Python that stands in for the Pico's hardware, only what the console uses
//   boot.json       the release fingerprint, build.py (IMAGE "web", the version, BUILD "pages",
//                   RELEASE), and the files to boot
//   console.js, worker.js, web/, core/, shared/, vendor/micropython/
//                   the page, its worker, and MicroPython in WebAssembly
//   coi.js, sw.js   COOP/COEP for SharedArrayBuffer and the CSP, as headers: Pages can't send any,
//                   so a service worker adds them (the page reloads once, the first time)
//   fonts/, brand/  the site's typeface (from docs/app/fonts/, which web/build.mjs writes) and mark
//   SHA256SUMS      every file but BUILD.json, for sha256sum -c
//   BUILD.json      the SHA-256 of every file written; rebuild from the same commit and compare
//                   (CI does; the live-site check compares what Pages serves with it)
// And docs/emu/, where the emulator's page was: a redirect to the console, and its BUILD.json.
// The emulator itself, with its editor and 3D case, is tools/emu.
//   node emu/build.mjs        (cd emu && npm ci first)
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { FIRMWARE, ROOT, readShims, emuBuild } from "./core/workspace.mjs";
import { fingerprint, manifest } from "../tools/releases/fingerprint.mjs";

const EMU = dirname(fileURLToPath(import.meta.url));
const CONSOLE = join(ROOT, "docs", "console");
const MOVED = join(ROOT, "docs", "emu");
const MP = join(EMU, "node_modules", "@micropython", "micropython-webassembly-pyscript");
const sha256 = (b) => createHash("sha256").update(b).digest("hex");

for (const d of [CONSOLE, MOVED]) rmSync(d, { recursive: true, force: true });
const write = (dir, rel, data) => { const p = join(dir, rel); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, data); };
const put = (rel, data) => write(CONSOLE, rel, data);
const copy = (from, rel) => put(rel, readFileSync(from));

// ----------------------------------------------------------------------------- the page's code
const CSRC = join(EMU, "console");
for (const f of ["console.js", "console.css", "worker.js"]) copy(join(CSRC, f), f);
copy(join(EMU, "web", "browser.mjs"), "web/browser.mjs");
for (const f of ["runtime.mjs", "webauthn-assert.mjs", "keccak.mjs"]) copy(join(EMU, "core", f), `core/${f}`);
copy(join(ROOT, "web", "src", "blockies.mjs"), "shared/blockies.mjs");
const mpVersion = JSON.parse(readFileSync(join(MP, "package.json"), "utf8")).version;
for (const f of ["micropython.mjs", "micropython.wasm"]) copy(join(MP, f), `vendor/micropython/${f}`);
put("vendor/micropython/LICENSE.txt", `MicroPython ${mpVersion}, WebAssembly build (@micropython/micropython-webassembly-pyscript).\nMIT License, Copyright (c) 2013-2025 Damien P. George and others. https://github.com/micropython/micropython\n`);
// the site's typeface, as web/build.mjs wrote it for the app (committed, so always here), and its mark
for (const f of ["next-400.woff2", "next-700.woff2", "mono-500.woff2", "LICENSE-OFL.txt"]) copy(join(ROOT, "docs", "app", "fonts", f), `fonts/${f}`);
for (const f of ["mark-dark.svg", "mark-light.svg"]) copy(join(ROOT, "docs", "brand", f), `brand/${f}`);
// the code's license (MIT: Jason McPheron, and Austin Griffith for what came from picowallet), so a
// saved copy of the folder carries it
copy(join(ROOT, "LICENSE"), "LICENSE");

// ----------------------------------------------------------------------------- the firmware
// The console image as plain files, to read, diff and hash: test-vectors/manifest.mjs checks that it
// is everything boot.py and main_console.py import, and quorum is one of those.
const image = [...new Set(manifest().images.console.files)].sort();
const files = Object.fromEntries(image.map((f) => [f, readFileSync(join(FIRMWARE, f))]));
// BUILD "pages", not a commit: committing the build would change the commit it names
const b = emuBuild(files, { image: "web", build: "pages" });
for (const f of image) put(`firmware/${f}`, files[f]);
if (fingerprint(image, (n) => readFileSync(join(CONSOLE, "firmware", n))) !== b.release) throw new Error("docs/console/firmware/ doesn't hash to the release fingerprint");

// The shims the console uses: the passkey is its only key, so the virtual chips (atecc_sim,
// trustm_sim) and rp2 never load, and aren't here. Pages drops any file whose name starts with "_"
// (Jekyll), so a shim's path may differ from its module name.
const SHIMS = ["_bootstrap", "machine", "network", "requests", "socket", "passkey"];
const allShims = readShims(), shims = {};
for (const n of SHIMS) { shims[n] = `shims/${n.replace(/^_+/, "")}.py`; put(shims[n], allShims[n]); }

// boot.json: what the page fetches and boots, and build.py. DATE stays out of build.py so a rebuild
// of the same commit gives the same bytes.
const boot = { release: b.release, build: b.py.replace(/^DATE = .*\n/m, ""), firmware: image, shims };
put("boot.json", "{\n" + Object.entries(boot).map(([k, v]) => ` ${JSON.stringify(k)}: ${JSON.stringify(v)}`).join(",\n") + "\n}\n");

// ----------------------------------------------------------------------------- the network
// The page may reach this folder and Safe's transaction service, nothing else: the services in the
// quorum_cfg.py it boots (JSON on purpose), today one host for every chain.
const cfgSrc = files["quorum_cfg.py"].toString("utf8");
const cfg = JSON.parse(cfgSrc.slice(cfgSrc.indexOf("{", cfgSrc.indexOf("CFG ="))));
const hosts = [...new Set(Object.values(cfg.services).map((u) => new URL(u).origin))].sort();
if (!hosts.length || hosts.some((h) => !h.startsWith("https://"))) throw new Error(`quorum_cfg.py services: ${hosts}`);
const policy = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",       // MicroPython's WebAssembly; no inline script at all
  "style-src 'self'",
  "font-src 'self'",
  "img-src 'self' data:",                       // the blockies
  `connect-src 'self' ${hosts.join(" ")}`,      // Safe's transaction service
  "worker-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

// ----------------------------------------------------------------------------- COOP/COEP, and the CSP
// GitHub Pages can't send headers. The page needs SharedArrayBuffer (keys reach Python while it runs,
// and the worker waits on it for your passkey), which needs COOP/COEP; and the CSP must bind the
// worker, which makes the firmware's requests, where the page's <meta> tag doesn't reach. sw.js adds
// all of them to the folder's own responses. A page's subresources go through the service worker that
// controls the page; a worker's own script through the one whose scope holds its URL: worker.js is in
// this folder, so this one.
put("coi.js", `// GitHub Pages can't send COOP/COEP headers, and the console needs SharedArrayBuffer (keys reach
// Python while it runs). sw.js adds them to this folder's own responses; the first visit reloads
// once, when the worker has taken over. Cross-origin requests (Safe's service) are left alone.
(function () {
  if (self.crossOriginIsolated || !("serviceWorker" in navigator)) return;
  var KEY = "coi-reloaded:" + location.pathname;
  var once = function () { try { if (sessionStorage.getItem(KEY)) return; sessionStorage.setItem(KEY, "1"); } catch (e) { return; } location.reload(); };
  navigator.serviceWorker.register("sw.js").then(function () {
    if (navigator.serviceWorker.controller) once();
    else navigator.serviceWorker.addEventListener("controllerchange", once);
  }, function (e) { console.warn("no service worker, so no SharedArrayBuffer:", e); });
})();
`);
put("sw.js", `// coi.js registers this. The folder's own responses get COOP/COEP (for SharedArrayBuffer) and the
// page's Content-Security-Policy, which then binds its worker too: it may reach this folder and
// Safe's service, nothing else. Everything else goes to the network untouched.
const CSP = ${JSON.stringify(policy + "; frame-ancestors 'none'")};
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (new URL(r.url).origin !== self.location.origin) return;
  if (r.cache === "only-if-cached" && r.mode !== "same-origin") return;
  e.respondWith(fetch(r).then((res) => {
    if (!res || res.status === 0 || res.type === "opaqueredirect") return res;
    const h = new Headers(res.headers);
    h.set("Cross-Origin-Opener-Policy", "same-origin");
    h.set("Cross-Origin-Embedder-Policy", "require-corp");
    h.set("Cross-Origin-Resource-Policy", "same-origin");
    h.set("Content-Security-Policy", CSP);
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
  }));
});
`);

// ----------------------------------------------------------------------------- index.html
let html = readFileSync(join(CSRC, "index.html"), "utf8");
if (/<script(?![^>]*\bsrc=)/.test(html) || /\sstyle=/.test(html)) throw new Error("emu/console/index.html: no inline scripts or styles (the CSP refuses them)");
// What is in the folder, counted from the files just written, for the page to say
const lines = (rels) => rels.reduce((n, r) => n + (readFileSync(join(CONSOLE, r), "utf8").match(/\n/g) || []).length, 0);
const kb = (rels) => Math.round(rels.reduce((n, r) => n + statSync(join(CONSOLE, r)).size, 0) / 1024);
const n = (x) => x.toLocaleString("en-US");
const py = image.filter((f) => f.endsWith(".py")), data = image.length - py.length;
const js = ["console.js", "worker.js", "coi.js", "sw.js", "web/browser.mjs", "core/runtime.mjs", "core/keccak.mjs", "core/webauthn-assert.mjs", "shared/blockies.mjs"];
const stack = [
  ["firmware/", `The console image: the same ${image.length} files a Pico runs, in MicroPython. They hash to the release fingerprint.`,
    `${n(lines(py.map((f) => `firmware/${f}`)))} lines, and ${data} data files`],
  ["shims/", "Python in place of the Pico's hardware: its pins, screen and Wi-Fi, and your passkey as its key.", `${n(lines(Object.values(shims)))} lines`],
  ["console.js, worker.js, web/, core/, shared/, coi.js, sw.js", "The page's JavaScript: the buttons, your passkey, and the worker MicroPython runs in.", `${n(lines(js))} lines`],
  ["vendor/micropython/", `MicroPython ${mpVersion} for WebAssembly, the one part built elsewhere: by the MicroPython project, from npm, pinned by its hash.`,
    `${kb(["vendor/micropython/micropython.mjs", "vendor/micropython/micropython.wasm"])} KB`],
  ["index.html, console.css, fonts/, brand/", "This page: its words, its look, the site's typeface and mark.", ""],
];
html = html.replace(/ *<!-- stack:[^>]*-->\n/, '    <table class="stack">\n      <thead><tr><th>In the folder</th><th>Size</th></tr></thead>\n      <tbody>\n' +
  stack.map(([what, about, size]) => `        <tr><td><code>${what}</code><span>${about}</span></td><td>${size}</td></tr>\n`).join("") + "      </tbody>\n    </table>\n");
html = html.replace('<meta charset="utf-8">\n', `<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="${policy}">\n<script src="coi.js"></script>\n`);
put("index.html", html);

// ----------------------------------------------------------------------------- docs/emu
// The emulator's page used to be here. It is gone from the site (tools/emu keeps it, with the editor
// and the 3D case); old links land on the console.
write(MOVED, "index.html", `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; base-uri 'none'; form-action 'none'">
<meta http-equiv="refresh" content="0; url=../console/">
<meta name="robots" content="noindex">
<title>PicoQuorum · The console in your browser</title>
</head>
<body>
<p>The console in your browser is at <a href="../console/">../console/</a>. The emulator, with its editor and the 3D case, runs from a checkout of the repository: <code>tools/emu</code>.</p>
</body>
</html>
`);

// ----------------------------------------------------------------------------- BUILD.json
function seal(dir, note, { sums = false } = {}) {
  const walk = () => {
    const all = [];
    (function w(d) { for (const f of readdirSync(d).sort()) { const p = join(d, f); statSync(p).isDirectory() ? w(p) : all.push(p); } })(dir);
    return all;
  };
  const rel = (p) => relative(dir, p).split("\\").join("/");
  // Pages runs the site through Jekyll: it rewrites any file opening with YAML front matter, and
  // leaves out any file or folder whose name starts with "_" or "."
  const jekyll = walk().filter((p) => readFileSync(p).subarray(0, 4).toString() === "---\n" || /(^|\/)[_.]/.test(rel(p)));
  if (jekyll.length) throw new Error(`Jekyll on Pages would rewrite or drop these: ${jekyll.map(rel).join(", ")}`);
  // SHA256SUMS, in sha256sum's own format: every file but itself and BUILD.json, which lists it
  if (sums) write(dir, "SHA256SUMS", walk().map((p) => `${sha256(readFileSync(p))}  ${rel(p)}\n`).join(""));
  const all = walk();
  const hashes = Object.fromEntries(all.map((p) => [rel(p), sha256(readFileSync(p))]));
  write(dir, "BUILD.json", JSON.stringify({ note, release: b.release, files: hashes }, null, 2) + "\n");
  console.log(`${relative(ROOT, dir)}: release ${b.release.slice(0, 4)}·${b.release.slice(4, 8)}, ${all.length + 1} files, ${Math.round(all.reduce((n, p) => n + statSync(p).size, 0) / 1024)} KB`);
}
seal(CONSOLE, "SHA-256 of every file emu/build.mjs wrote for the console page, which holds everything it runs: firmware/ is the console image, and hashes to the release fingerprint. SHA256SUMS lists the same files for sha256sum -c. Rebuild from the same commit (cd emu && npm ci && node build.mjs) and compare.", { sums: true });
seal(MOVED, "The emulator's page is gone from the site: this sends its old address to ../console/. emu/build.mjs writes it.");
