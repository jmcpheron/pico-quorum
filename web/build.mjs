// Builds the Execute page into docs/app/, which GitHub Pages serves with the rest of docs/:
//   cd web && npm ci && npm run build
// One bundle (esbuild; viem and noble pinned in package.json), the stylesheet, the fonts, and
// index.html with subresource-integrity hashes for both. The page's pinned values come from
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
// pinned copies, so the bundle holds one of each.
const fromHere = {
  name: "deps-from-web",
  setup(b) {
    b.onResolve({ filter: /^(viem|@noble\/)/ }, async (args) => {
      if (args.pluginData === "here") return;
      const r = await b.resolve(args.path, { resolveDir: HERE, kind: args.kind, pluginData: "here" });
      return r.errors.length ? { errors: r.errors } : { path: r.path };
    });
  },
};
await build({
  entryPoints: [join(HERE, "src/main.mjs")], bundle: true, minify: true, format: "esm", target: "es2022",
  outfile: join(OUT, "app.js"), legalComments: "eof", plugins: [fromHere], logLevel: "warning",
  banner: { js: "// PicoQuorum Execute page. Source: web/ in github.com/jmcpheron/pico-quorum" },
});
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
const files = ["index.html", "app.js", "app.css", ...Object.keys(fonts).map((f) => "fonts/" + f)];
writeFileSync(join(OUT, "BUILD.json"), JSON.stringify({
  note: "SHA-256 of every file web/build.mjs wrote. Rebuild from the same commit (cd web && npm ci && npm run build) and compare.",
  build: build8, files: Object.fromEntries(files.map((f) => [f, sha(f)])),
}, null, 2) + "\n");
console.log(`docs/app: build ${build8}, app.js ${(readFileSync(join(OUT, "app.js")).length / 1024).toFixed(0)} KB`);
