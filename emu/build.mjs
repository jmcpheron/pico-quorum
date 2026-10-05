#!/usr/bin/env node
// The emulator as a static site for GitHub Pages: writes docs/emu/ (commit it; Pages serves the
// branch). Same page as tools/emu, laid out like the server's URLs (web/, core/, vendor/, stl/,
// shared/) so the relative paths work under both. What the server did, done here once:
//   boot.json       the firmware (firmware/, no sketches), the shims, and a build.py (IMAGE "web",
//                   the version, BUILD "pages", RELEASE: the console's release fingerprint)
//   coi.js, sw.js   COOP/COEP for SharedArrayBuffer: Pages can't send headers, so a service worker
//                   adds them to this folder's own responses (the page reloads once, the first time)
//   index.html      <meta name="emu-host" content="static">, and a strict CSP
//   BUILD.json      the SHA-256 of every file written; rebuild from the same commit and compare
// The chip state, a software key and edits stay in the visitor's browser (web/app.js).
// And docs/console/: the console alone (emu/console/), the screen and buttons with your passkey as the
// key. It runs docs/emu's boot.json, worker and MicroPython, and has its own coi.js, sw.js, CSP and
// BUILD.json (the live-site check reads both).
//   node emu/build.mjs        (cd emu && npm ci first)
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { FIRMWARE, ROOT, isRunnable, entryFor, readShims, emuBuild } from "./core/workspace.mjs";

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
// So the console has a worker.js of its own, which imports ../emu/web/worker.js.
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
put("index.html", html);

// ----------------------------------------------------------------------------- docs/console
const CSRC = join(EMU, "console");
const cput = (rel, data) => write(CONSOLE, rel, data);
for (const f of ["console.js", "console.css"]) cput(f, readFileSync(join(CSRC, f)));
cput("coi.js", coi("the console"));
cput("sw.js", sw("the console's files, and the emulator's files it runs"));
cput("worker.js", '// The emulator\'s worker, started from this folder so that sw.js here gives it COOP/COEP.\nimport "../emu/web/worker.js";\n');
const ccsp = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",       // MicroPython's WebAssembly; no inline script at all
  "style-src 'self'",
  "img-src 'self' data:",                       // the release blockie
  "connect-src 'self' https:",                  // Safe's transaction service, per chain
  "worker-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");
let chtml = readFileSync(join(CSRC, "index.html"), "utf8");
if (/<script(?![^>]*\bsrc=)/.test(chtml) || /\sstyle=/.test(chtml)) throw new Error("emu/console/index.html: no inline scripts or styles (the CSP refuses them)");
chtml = chtml.replace('<meta charset="utf-8">\n', `<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="${ccsp}">\n<script src="coi.js"></script>\n`);
cput("index.html", chtml);

// ----------------------------------------------------------------------------- BUILD.json
function seal(dir, note) {
  const all = [];
  (function walk(d) { for (const f of readdirSync(d).sort()) { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : all.push(p); } })(dir);
  // Pages would run any file opening with YAML front matter through Jekyll and serve something else
  const jekyll = all.filter((p) => readFileSync(p).subarray(0, 4).toString() === "---\n");
  if (jekyll.length) throw new Error(`these would be rewritten by Jekyll on Pages (they open with ---): ${jekyll.map((p) => relative(dir, p)).join(", ")}`);
  const hashes = Object.fromEntries(all.map((p) => [relative(dir, p).split("\\").join("/"), sha256(readFileSync(p))]));
  write(dir, "BUILD.json", JSON.stringify({ note, release: b.release, files: hashes }, null, 2) + "\n");
  console.log(`${relative(ROOT, dir)}: release ${b.release.slice(0, 4)}·${b.release.slice(4, 8)}, ${all.length + 1} files, ${Math.round(all.reduce((n, p) => n + statSync(p).size, 0) / 1024)} KB`);
}
seal(OUT, "SHA-256 of every file emu/build.mjs wrote. Rebuild from the same commit (cd emu && npm ci && node build.mjs) and compare.");
seal(CONSOLE, "SHA-256 of every file emu/build.mjs wrote for the console page. It runs ../emu/'s boot.json, worker and MicroPython, which ../emu/BUILD.json lists. Rebuild from the same commit (cd emu && npm ci && node build.mjs) and compare.");
