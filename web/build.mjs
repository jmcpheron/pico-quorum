// Builds the app into docs/app/, the front page into docs/index.html and the handheld's page into
// docs/handheld/, which GitHub Pages serves
// with the rest of docs/:
//   cd web && npm ci && npm run build
// One bundle (esbuild; viem and noble pinned in package.json), the stylesheet, the fonts, and
// index.html with subresource-integrity hashes for both. The front page is static HTML and its own
// stylesheet (home.css), no script, and uses the app's fonts. The page's pinned values come from
// firmware/quorum_cfg.py (config.mjs). BUILD.json records the hash of every file, so anyone can
// rebuild from the same commit and compare.
import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { writeConfig } from "./config.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "../docs/app");
mkdirSync(join(OUT, "fonts"), { recursive: true });
writeConfig();

// tools/mock-tx-service/sigs.mjs is bundled as is; its viem and noble resolve to this package's
// pinned copies, so the bundle holds one of each. An alias does it: esbuild resolves an aliased
// import from the working directory (web/), not from the importing file. A resolve plugin did this
// before, and any plugin that redirected a path let the module order, and so the minified names,
// change about one build in eight (2026-10-05), which CI's rebuild check would trip on.
const pinned = { viem: "viem", "@noble/curves": "@noble/curves", "@noble/hashes": "@noble/hashes" };
const meta = await build({
  entryPoints: [join(HERE, "src/main.mjs")], bundle: true, minify: true, format: "esm", target: "es2022",
  outfile: join(OUT, "app.js"), legalComments: "eof", alias: pinned, logLevel: "warning", absWorkingDir: HERE,
  banner: { js: "// PicoQuorum Execute page. Source: web/ in github.com/jmcpheron/pico-quorum" }, metafile: true,
});
const outside = Object.keys(meta.metafile.inputs).filter((f) => /node_modules/.test(f) && !f.startsWith("node_modules/"));
if (outside.length) throw new Error(`dependencies bundled from outside web/node_modules: ${outside.slice(0, 3).join(", ")}`);
copyFileSync(join(HERE, "src/app.css"), join(OUT, "app.css"));
const fonts = {
  "next-400.woff2": "@fontsource/atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-400-normal.woff2",
  "next-700.woff2": "@fontsource/atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-700-normal.woff2",
  "mono-500.woff2": "@fontsource/atkinson-hyperlegible-mono/files/atkinson-hyperlegible-mono-latin-500-normal.woff2",
  "mono-700.woff2": "@fontsource/atkinson-hyperlegible-mono/files/atkinson-hyperlegible-mono-latin-700-normal.woff2",
};
for (const [to, from] of Object.entries(fonts)) copyFileSync(join(HERE, "node_modules", from), join(OUT, "fonts", to));
copyFileSync(join(HERE, "node_modules/@fontsource/atkinson-hyperlegible-next/LICENSE"), join(OUT, "fonts/LICENSE-OFL.txt"));

const sri = (f) => "sha384-" + createHash("sha384").update(readFileSync(join(OUT, f))).digest("base64");
const sha = (f) => createHash("sha256").update(readFileSync(join(OUT, f))).digest("hex");
const build8 = sha("app.js").slice(0, 8);
writeFileSync(join(OUT, "index.html"), readFileSync(join(HERE, "src/index.html"), "utf8")
  .replace("%%CSS_SRI%%", sri("app.css")).replace("%%JS_SRI%%", sri("app.js")).replace("%%BUILD%%", build8));
copyFileSync(join(HERE, "src/home.css"), join(OUT, "../home.css"));
writeFileSync(join(OUT, "../index.html"), readFileSync(join(HERE, "src/home.html"), "utf8").replace("%%HOME_CSS_SRI%%", sri("../home.css")));

// The handheld's page (docs/handheld/), kept for links already shared: static like the front page, with
// the case's own assembly pictures and its share card (web/handheld-card.py), and the front page's
// pictures of the other hardware. All copied as they are, so a picture's source is its only copy.
const CASE = "../hardware/builds/pico-sign-handheld/case/out/assembly/";
const steps = ["00-colours", "00-exploded", "00-printed-parts", "00-hardware", "01-tub-inserts", "02-feet", "03-key-plug",
  "04-breadboard", "05-plate-inserts", "06-guard", "07-guard-in", "08-knob", "09-screen", "10-spacers", "11-carrier",
  "12-pico", "13-wires", "14-close", "15-key", "16-done"];
const pictures = {
  "../handheld/card.png": "src/handheld-card.png",
  ...Object.fromEntries(steps.map((s) => [`../handheld/img/${s}.png`, `${CASE}${s}.png`])),
  "../img/key-c.jpg": "../hardware/key-pcb/key-c-usbc/renders/key-c-P2-3q-top.jpg",
  "../img/console-rp.jpg": "../hardware/console-rp/renders/console-rp-3q.jpg",
};
mkdirSync(join(OUT, "../handheld/img"), { recursive: true });
mkdirSync(join(OUT, "../img"), { recursive: true });
for (const [to, from] of Object.entries(pictures)) copyFileSync(join(HERE, from), join(OUT, to));
writeFileSync(join(OUT, "../handheld/index.html"), readFileSync(join(HERE, "src/handheld.html"), "utf8").replace("%%HOME_CSS_SRI%%", sri("../home.css")));
const files = ["index.html", "app.js", "app.css", ...Object.keys(fonts).map((f) => "fonts/" + f), "../index.html", "../home.css",
  "../handheld/index.html", ...Object.keys(pictures)];
writeFileSync(join(OUT, "BUILD.json"), JSON.stringify({
  note: "SHA-256 of every file web/build.mjs wrote (../ is docs/, the front page). Rebuild from the same commit (cd web && npm ci && npm run build) and compare.",
  build: build8, files: Object.fromEntries(files.map((f) => [f, sha(f)])),
}, null, 2) + "\n");
console.log(`docs/app: build ${build8}, app.js ${(readFileSync(join(OUT, "app.js")).length / 1024).toFixed(0)} KB`);
