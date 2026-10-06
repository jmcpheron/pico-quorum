#!/usr/bin/env node
// The browser pages for GitHub Pages (commit them; Pages serves the branch):
//
// docs/console/: the console alone (emu/console/), its screen and buttons, with your passkey as the
// key. One folder that holds everything it runs and loads nothing from the rest of the site, so a
// copy of the folder is the whole program (docs/guide/BROWSER.md):
//   firmware/       the console image (firmware/manifest.json), the same files a Pico runs, as plain
//                   files: their release fingerprint is the README's, worked out with sha256sum
//   shims/          the emulator's Python half: machine, network, requests and the rest
//   boot.json       which files to boot, and a build.py (IMAGE "web", the version, BUILD "pages",
//                   RELEASE: the release fingerprint)
//   web/, core/, shared/, vendor/micropython/   the page's runtime and MicroPython in WebAssembly
//   fonts/          the site's fonts, from docs/app/fonts/ (web/build.mjs writes them)
//   SHA256SUMS      every file but BUILD.json, for sha256sum -c
//
// docs/emu/: the emulator, deprecated on the site and linked from nowhere; tools/emu keeps it,
// with its editor and 3D case, for development. Same page as tools/emu, laid out like the server's
// URLs (web/, core/, vendor/, stl/, shared/) so the relative paths work under both.
//   boot.json       the firmware (firmware/, no sketches), the shims, and the same build.py
//   index.html      <meta name="emu-host" content="static">, a strict CSP, and a note that it moved
// The chip state, a software key and edits stay in the visitor's browser (web/app.js).
//
// Both have:
//   coi.js, sw.js   COOP/COEP for SharedArrayBuffer: Pages can't send headers, so a service worker
//                   adds them to the folder's own responses (the page reloads once, the first time)
//   BUILD.json      the SHA-256 of every file written; rebuild from the same commit and compare
//                   (CI does; the live-site check compares what Pages serves with it)
//   node emu/build.mjs        (cd emu && npm ci first)
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { FIRMWARE, ROOT, isRunnable, entryFor, readShims, emuBuild } from "./core/workspace.mjs";
import { fingerprint } from "../tools/releases/fingerprint.mjs";

const EMU = dirname(fileURLToPath(import.meta.url));
const OUT = join(ROOT, "docs", "emu");
const CONSOLE = join(ROOT, "docs", "console");
const NM = join(EMU, "node_modules");
const sha256 = (b) => createHash("sha256").update(b).digest("hex");

for (const d of [OUT, CONSOLE]) rmSync(d, { recursive: true, force: true });
const write = (dir, rel, data) => { const p = join(dir, rel); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, data); };
const put = (rel, data) => write(OUT, rel, data);
const copy = (from, rel) => put(rel, readFileSync(from));

// ----------------------------------------------------------------------------- the page's code
for (const f of ["app.js", "app.css", "worker.js", "device3d.js", "browser.mjs"]) copy(join(EMU, "web", f), `web/${f}`);
copy(join(EMU, "core", "runtime.mjs"), "core/runtime.mjs");
copy(join(EMU, "core", "webauthn-assert.mjs"), "core/webauthn-assert.mjs");
copy(join(EMU, "core", "keccak.mjs"), "core/keccak.mjs");
copy(join(ROOT, "web", "src", "blockies.mjs"), "shared/blockies.mjs");
// .txt, and never starting with "---": Pages runs .md files, and any file that opens with YAML front
// matter, through Jekyll, which rewrote this one (the live-site check caught it, 2026-10-05)
put("SKILL.txt", "# PicoQuorum emulator: the skill file for your AI (emu/SKILL.md in the repository)\n\n" + readFileSync(join(EMU, "SKILL.md"), "utf8"));

// ----------------------------------------------------------------------------- vendored libraries
const MP = join(NM, "@micropython", "micropython-webassembly-pyscript");
copy(join(MP, "micropython.mjs"), "vendor/micropython/micropython.mjs");
copy(join(MP, "micropython.wasm"), "vendor/micropython/micropython.wasm");
put("vendor/micropython/LICENSE.txt", `MicroPython ${JSON.parse(readFileSync(join(MP, "package.json"), "utf8")).version}, WebAssembly build (@micropython/micropython-webassembly-pyscript).\nMIT License, Copyright (c) 2013-2025 Damien P. George and others. https://github.com/micropython/micropython\n`);
copy(join(NM, "three", "build", "three.module.js"), "vendor/three/three.module.js");
for (const a of ["controls/OrbitControls.js", "loaders/STLLoader.js", "environments/RoomEnvironment.js"])
  copy(join(NM, "three", "examples", "jsm", a), `vendor/three/addons/${a}`);
copy(join(NM, "three", "LICENSE"), "vendor/three/LICENSE.txt");
for (const f of ["lib/codemirror.js", "lib/codemirror.css", "mode/python/python.js"]) copy(join(NM, "codemirror", f), `vendor/codemirror/${f}`);
copy(join(NM, "codemirror", "LICENSE"), "vendor/codemirror/LICENSE.txt");

// The four parts the 3D view draws (device3d.js), and whose they are.
for (const n of ["base_v5", "lid_v4", "button_cap_1", "joystick_cap_v3_2.00"]) copy(join(ROOT, "cad", "console", "zez0000", `${n}.stl`), `stl/${n}.stl`);
put("stl/NOTICE.txt", "Raspberry Pi Pico 2 Case - Waveshare 1.3\" LCD, by Zez0000\nhttps://makerworld.com/en/models/3230142-raspberry-pi-pico-2-case-waveshare-1-3-lcd\nCC BY-NC: attribution, non-commercial. See NOTICE in the PicoQuorum repository.\n");

// ----------------------------------------------------------------------------- boot.json
// What /ctl/boot answers under tools/emu, for the firmware alone (sketches are local experiments).
const files = {};
const list = readdirSync(FIRMWARE).filter((f) => !f.startsWith(".") && !/^secrets(\.example)?\.py$/.test(f) && /\.(py|bin|pv|txt|json)$/.test(f) && statSync(join(FIRMWARE, f)).isFile()).sort();
for (const f of list) files[f] = f.endsWith(".py") ? readFileSync(join(FIRMWARE, f), "utf8") : readFileSync(join(FIRMWARE, f));
// BUILD "pages", not a commit: committing the build would change the commit it names
const b = emuBuild(files, { image: "web", build: "pages" });
const boot = {
  files: [
    ...list.map((name) => {
      const data = files[name];
      if (!name.endsWith(".py")) return { name, src: "firmware", b64: data.toString("base64") };
      const mod = name.slice(0, -3);
      return { name, src: "firmware", text: data, runnable: isRunnable(mod, data), entry: entryFor(mod) };
    }),
    // DATE stays out of it so a rebuild of the same commit gives the same bytes
    { name: "build.py", src: "emu", text: b.py.replace(/^DATE = .*\n/m, ""), runnable: false, entry: "" },
  ],
  shims: readShims(),
  appUrl: null,                 // no wallet app to proxy to: the console uses Safe's service per chain
  release: b.release,
  consoleFiles: b.consoleFiles,
};
put("boot.json", JSON.stringify(boot));

// ----------------------------------------------------------------------------- COOP/COEP
// The reload flag is per folder: a tab that already reloaded for one page must reload for the other.
const coi = (what) => `// GitHub Pages can't send COOP/COEP headers, and ${what} needs SharedArrayBuffer (keys reach
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
`;
// A page's subresources, and its worker's imports, go through the service worker that controls the
// page whatever their URL; the worker's own script goes through the one whose scope holds its URL.
// So each page's worker script sits inside its own folder (web/worker.js).
const sw = (what) => `// COOP/COEP for ${what} (coi.js registers this). Same-origin responses get the headers;
// everything else goes to the network untouched.
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
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
  }));
});
`;
put("coi.js", coi("the emulator"));
put("sw.js", sw("the emulator's own files"));

// ----------------------------------------------------------------------------- index.html
let html = readFileSync(join(EMU, "web", "index.html"), "utf8");
const importmap = /<script type="importmap">([\s\S]*?)<\/script>/.exec(html)[1];
const csp = [
  "default-src 'self'",
  `script-src 'self' 'wasm-unsafe-eval' 'sha256-${createHash("sha256").update(importmap).digest("base64")}'`,
  "style-src 'self' 'unsafe-inline'",           // CodeMirror and three set element styles
  "img-src 'self' data: blob:",
  "connect-src 'self' https:",                  // Safe's transaction service, per chain
  "worker-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");
html = html.replace("<head>\n", `<head>\n<meta name="emu-host" content="static">\n<meta http-equiv="Content-Security-Policy" content="${csp}">\n<script src="coi.js"></script>\n`);
html = html.replace("<title>picowallet emulator</title>", "<title>PicoQuorum console emulator</title>");
html = html.replace(/<div class="brand">[^\n]*<\/div>/, '<a class="brand" href="../" title="PicoQuorum">pico<span>quorum</span> console</a> <a class="applink" href="../app/">app</a>');
html = html.replace("</header>\n", '</header>\n<p id="moved">This page is deprecated and will go away. The console is at <a href="../console/">../console/</a>: the same firmware, with your passkey as its key. The editor and the 3D case stay in <code>tools/emu</code>, in a checkout of the repository.</p>\n');
put("index.html", html);

// ----------------------------------------------------------------------------- docs/console
// Everything the console page runs, in its own folder; it loads nothing from ../emu/ or anywhere else
// on the site. The firmware is the console image, not all of firmware/: test-vectors/manifest.mjs
// checks that it is everything boot.py and main_console.py import, and quorum is one of those.
const CSRC = join(EMU, "console");
const cput = (rel, data) => write(CONSOLE, rel, data);
const ccopy = (from, rel) => cput(rel, readFileSync(from));
for (const f of ["console.js", "console.css"]) ccopy(join(CSRC, f), f);
for (const f of ["worker.js", "browser.mjs"]) ccopy(join(EMU, "web", f), `web/${f}`);
for (const f of ["runtime.mjs", "webauthn-assert.mjs", "keccak.mjs"]) ccopy(join(EMU, "core", f), `core/${f}`);
ccopy(join(ROOT, "web", "src", "blockies.mjs"), "shared/blockies.mjs");
for (const f of ["micropython.mjs", "micropython.wasm"]) ccopy(join(MP, f), `vendor/micropython/${f}`);
ccopy(join(OUT, "vendor", "micropython", "LICENSE.txt"), "vendor/micropython/LICENSE.txt");
// the site's typeface, as web/build.mjs wrote it for the app (committed, so always here)
for (const f of ["next-400.woff2", "next-700.woff2", "mono-500.woff2", "LICENSE-OFL.txt"]) ccopy(join(ROOT, "docs", "app", "fonts", f), `fonts/${f}`);
for (const f of ["mark-dark.svg", "mark-light.svg"]) ccopy(join(ROOT, "docs", "brand", f), `brand/${f}`);

// The console image as plain files, to read, diff and hash. Pages drops any file whose name starts
// with "_" (Jekyll), so a shim's path may differ from its module name: shimPaths maps one to the other.
const image = [...new Set(b.consoleFiles)].sort();
for (const f of image) cput(`firmware/${f}`, readFileSync(join(FIRMWARE, f)));
if (fingerprint(image, (n) => readFileSync(join(CONSOLE, "firmware", n))) !== b.release) throw new Error("docs/console/firmware/ doesn't hash to the release fingerprint");
const shims = readShims(), shimPaths = {};
for (const n of Object.keys(shims).sort()) { shimPaths[n] = `shims/${n.replace(/^_+/, "")}.py`; cput(shimPaths[n], shims[n]); }
// one file to a line, to read
const cboot = {
  files: [
    ...image.map((name) => {
      const path = `firmware/${name}`;
      if (!name.endsWith(".py")) return { name, src: "firmware", path };
      const mod = name.slice(0, -3);
      return { name, src: "firmware", path, runnable: isRunnable(mod, files[name]), entry: entryFor(mod) };
    }),
    boot.files.find((f) => f.name === "build.py"),
  ],
  shimPaths,
  appUrl: null,
  release: b.release,
  consoleFiles: b.consoleFiles,
};
cput("boot.json", "{\n" + Object.entries(cboot).map(([k, v]) => ` ${JSON.stringify(k)}: ` +
  (k === "files" ? `[\n${v.map((f) => "  " + JSON.stringify(f)).join(",\n")}\n ]` : JSON.stringify(v))).join(",\n") + "\n}\n");

cput("coi.js", coi("the console"));
cput("sw.js", sw("the console's own files"));
const ccsp = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",       // MicroPython's WebAssembly; no inline script at all
  "style-src 'self'",
  "font-src 'self'",
  "img-src 'self' data:",                       // the blockies
  "connect-src 'self' https:",                  // Safe's transaction service, per chain
  "worker-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");
let chtml = readFileSync(join(CSRC, "index.html"), "utf8");
if (/<script(?![^>]*\bsrc=)/.test(chtml) || /\sstyle=/.test(chtml)) throw new Error("emu/console/index.html: no inline scripts or styles (the CSP refuses them)");
// What is in the folder, counted from the files just written, for the page to say
const lines = (rels) => rels.reduce((n, r) => n + (readFileSync(join(CONSOLE, r), "utf8").match(/\n/g) || []).length, 0);
const kb = (rels) => Math.round(rels.reduce((n, r) => n + statSync(join(CONSOLE, r)).size, 0) / 1024);
const n = (x) => x.toLocaleString("en-US");
const py = image.filter((f) => f.endsWith(".py")), data = image.length - py.length;
const js = ["console.js", "coi.js", "sw.js", "web/worker.js", "web/browser.mjs", "core/runtime.mjs", "core/keccak.mjs", "core/webauthn-assert.mjs", "shared/blockies.mjs"];
const mpVersion = JSON.parse(readFileSync(join(MP, "package.json"), "utf8")).version;
const stack = [
  ["firmware/", `The console image: the same ${image.length} files a Pico runs, in MicroPython. They hash to the release fingerprint.`,
    `${n(lines(py.map((f) => `firmware/${f}`)))} lines, and ${data} data files`],
  ["shims/", "Python in place of the Pico's hardware: its pins, screen and Wi-Fi, and your passkey as its chip.", `${n(lines(Object.values(shimPaths)))} lines`],
  ["console.js, web/, core/, shared/, coi.js, sw.js", "The page's JavaScript: the buttons, your passkey, and the worker MicroPython runs in.", `${n(lines(js))} lines`],
  ["vendor/micropython/", `MicroPython ${mpVersion} for WebAssembly, the one part built elsewhere: by the MicroPython project, from npm, pinned by its hash.`,
    `${kb(["vendor/micropython/micropython.mjs", "vendor/micropython/micropython.wasm"])} KB`],
  ["index.html, console.css, fonts/, brand/", "This page: its words, its look, the site's typeface and mark.", ""],
];
chtml = chtml.replace(/ *<!-- stack:[^>]*-->\n/, '    <table class="stack">\n      <thead><tr><th>In the folder</th><th>Size</th></tr></thead>\n      <tbody>\n' +
  stack.map(([what, about, size]) => `        <tr><td><code>${what}</code><span>${about}</span></td><td>${size}</td></tr>\n`).join("") + "      </tbody>\n    </table>\n");
chtml = chtml.replace('<meta charset="utf-8">\n', `<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="${ccsp}">\n<script src="coi.js"></script>\n`);
cput("index.html", chtml);

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
seal(OUT, "SHA-256 of every file emu/build.mjs wrote. Rebuild from the same commit (cd emu && npm ci && node build.mjs) and compare.");
seal(CONSOLE, "SHA-256 of every file emu/build.mjs wrote for the console page, which holds everything it runs: firmware/ is the console image, and hashes to the release fingerprint. SHA256SUMS lists the same files for sha256sum -c. Rebuild from the same commit (cd emu && npm ci && node build.mjs) and compare.", { sums: true });
