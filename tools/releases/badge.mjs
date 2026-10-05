// The README's build badges: each firmware image's release fingerprint as the console shows it, its
// blockie and its first and last 8 hex digits, so a reader can hold the README up to a Device screen
// or the app's Releases page. They name the source in this checkout, the way docs/emu/BUILD.json does.
//
//   node tools/releases/badge.mjs           write docs/releases/badges/ and the README's build table
//   node tools/releases/badge.mjs --check   exit 1 if either differs from what this source makes (CI)
//
// docs/releases/badges/firmware.svg         the version in firmware/manifest.json
// docs/releases/badges/<image>.svg          a badge: blockie · image · 5869·4b0d…a11f·30d7
// docs/releases/badges/<image>-blockie.svg  the blockie alone, seed "0x" + fingerprint, as everywhere
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT, manifest, imageFingerprint } from "./fingerprint.mjs";
import { blockie, rgb } from "../../web/src/blockies.mjs";

const OUT = join(ROOT, "docs", "releases", "badges");
const README = join(ROOT, "README.md");
const BEGIN = "<!-- build:begin (node tools/releases/badge.mjs writes this table) -->";
const END = "<!-- build:end -->";

const hex = (c) => "#" + rgb(c).map((v) => v.toString(16).padStart(2, "0")).join("");
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");

/** The blockie as SVG paths in an 8×8 box at (x, y), scaled by s. */
function cells(fp, x = 0, y = 0, s = 1) {
  const { data, color, bg, spot } = blockie("0x" + fp);
  const d = ["", ""];
  data.forEach((v, i) => { if (v) d[v === 1 ? 0 : 1] += `M${i % 8} ${i >> 3}h1v1h-1z`; });
  return `<g transform="translate(${x} ${y}) scale(${s})" shape-rendering="crispEdges">` +
    `<path fill="${hex(bg)}" d="M0 0h8v8H0z"/><path fill="${hex(color)}" d="${d[0]}"/><path fill="${hex(spot)}" d="${d[1]}"/></g>`;
}

/** First and last 8, grouped in fours as the console groups them. */
export const ends = (fp) => `${fp.slice(0, 4)}·${fp.slice(4, 8)}…${fp.slice(-8, -4)}·${fp.slice(-4)}`;

// Shields' flat style, 20 px high. textLength pins each run's width, so the badge is the same size
// whatever font the viewer has. fp: draw that fingerprint's blockie before the label.
function badge(label, value, { fp, color = "#627EEA", mono = false, title = `${label}: ${value}` } = {}) {
  const lx = fp ? 22 : 6, ll = Math.round(label.length * 6.1), lw = lx + ll + 6;
  const vl = Math.round(value.length * (mono ? 6.7 : 6.1)), vw = vl + 12, w = lw + vw;
  const text = (x, s, len, m) =>
    `<text x="${x}" y="14" textLength="${len}" lengthAdjust="spacingAndGlyphs"${m ? ` font-family="DejaVu Sans Mono,Menlo,Consolas,monospace"` : ""}>${esc(s)}</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="20" role="img" aria-label="${esc(title)}">
<title>${esc(title)}</title>
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="${w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="${lw}" height="20" fill="#0B0D11"/><rect x="${lw}" width="${vw}" height="20" fill="${color}"/><rect width="${w}" height="20" fill="url(#s)"/></g>
${fp ? cells(fp, 4, 3, 14 / 8) + "\n" : ""}<g fill="#fff" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
${text(lx, label, ll)}
${text(lw + 6, value, vl, mono)}
</g>
</svg>
`;
}

const blockieSvg = (fp) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" width="64" height="64"><title>blockie of 0x${fp}</title>${cells(fp)}</svg>\n`;

function table(m, fps) {
  const rows = Object.keys(m.images).map((image) =>
    `| <img src="docs/releases/badges/${image}-blockie.svg" width="32" height="32" alt=""> | **${image}** | \`${fps[image]}\` |`);
  return [BEGIN, "", "| | image | release fingerprint |", "|---|---|---|", ...rows, "", END].join("\n");
}

export function render() {
  const m = manifest(), files = {}, fps = {};
  for (const image of Object.keys(m.images)) {
    const fp = (fps[image] = imageFingerprint(image, undefined, m));
    files[join(OUT, `${image}.svg`)] = badge(image, ends(fp), { fp, mono: true, title: `${image} ${m.version} · release fingerprint ${fp}` });
    files[join(OUT, `${image}-blockie.svg`)] = blockieSvg(fp);
  }
  files[join(OUT, "firmware.svg")] = badge("firmware", m.version, { color: "#16963E" });
  const readme = readFileSync(README, "utf8"), a = readme.indexOf(BEGIN), b = readme.indexOf(END);
  if (a < 0 || b < a) throw new Error(`README.md has no ${BEGIN} … ${END} block`);
  files[README] = readme.slice(0, a) + table(m, fps) + readme.slice(b + END.length);
  return files;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const files = render(), check = process.argv.includes("--check");
  const stale = Object.entries(files).filter(([p, s]) => !existsSync(p) || readFileSync(p, "utf8") !== s);
  if (check) {
    for (const [p] of stale) console.error(`stale: ${p.slice(ROOT.length + 1)}`);
    if (stale.length) {
      console.error("The README's build badges don't name this source. Run node tools/releases/badge.mjs, and commit.");
      process.exit(1);
    }
    console.log("build badges: current");
  } else {
    mkdirSync(OUT, { recursive: true });
    for (const [p, s] of stale) { writeFileSync(p, s); console.log(p.slice(ROOT.length + 1)); }
  }
}
