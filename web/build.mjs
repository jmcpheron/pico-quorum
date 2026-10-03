// Builds the app into docs/app/, and the front page into docs/index.html, which GitHub Pages serves
// with the rest of docs/:
//   cd web && npm ci && npm run build
// One bundle (esbuild; viem and noble pinned in package.json), the stylesheet, the fonts, and
// index.html with subresource-integrity hashes for both. The front page is static HTML and its own
// stylesheet (home.css), no script, and uses the app's fonts. The page's pinned values come from
// firmware/quorum_cfg.py (config.mjs). BUILD.json records the hash of every file, so anyone can
// rebuild from the same commit and compare.
import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { writeConfig } from "./config.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "../docs/app");
mkdirSync(join(OUT, "fonts"), { recursive: true });
writeConfig();

// tools/mock-tx-service/sigs.mjs is bundled as is; its viem and noble resolve to this package's
// pinned copies, so the bundle holds one of each. Only imports from outside web/ go through here:
// sending every viem-internal import through the async resolve made the module order, and so the
// minified names, change from build to build.
const fromHere = {
  name: "deps-from-web",
  setup(b) {
    b.onResolve({ filter: /^(viem|@noble\/)/ }, async (args) => {
      if (args.pluginData === "here" || !relative(HERE, args.importer).startsWith("..")) return;
      const r = await b.resolve(args.path, { resolveDir: HERE, kind: args.kind, pluginData: "here" });
      return r.errors.length ? { errors: r.errors } : { path: r.path };
    });
  },
};
const meta = await build({
  entryPoints: [join(HERE, "src/main.mjs")], bundle: true, minify: true, format: "esm", target: "es2022",
  outfile: join(OUT, "app.js"), legalComments: "eof", plugins: [fromHere], logLevel: "warning", absWorkingDir: HERE,
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
const files = ["index.html", "app.js", "app.css", ...Object.keys(fonts).map((f) => "fonts/" + f), "../index.html", "../home.css"];
writeFileSync(join(OUT, "BUILD.json"), JSON.stringify({
  note: "SHA-256 of every file web/build.mjs wrote (../ is docs/, the front page). Rebuild from the same commit (cd web && npm ci && npm run build) and compare.",
  build: build8, files: Object.fromEntries(files.map((f) => [f, sha(f)])),
}, null, 2) + "\n");
console.log(`docs/app: build ${build8}, app.js ${(readFileSync(join(OUT, "app.js")).length / 1024).toFixed(0)} KB`);
