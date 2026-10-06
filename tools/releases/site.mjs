// The live site, checked from outside it. What a browser runs is whatever the site sends, and a page
// can't vouch for itself (a compromised site would fake any badge). So this looks from somewhere
// else: it fetches what GitHub Pages serves now and compares every byte with what the repository
// built (CI's rebuild check ties those to the source).
//
//   integrity  each web build's BUILD.json, and every file it lists, as served == the same files in
//              docs/ at the commit Pages deployed (or this checkout). Any difference fails.
//   releases   docs/releases/index.json and each <version>.json as served == the repository's.
//   status     which release each build is (its BUILD.json's SHA-256 is that release's
//              manifest web hash), and whether the project Safe approved it. Informational: between
//              releases the site is a development build, which is expected.
//
// tools/release check-site [URL] [--commit SHA]; .github/workflows/site-check.yml runs it after
// every Pages deploy and every six hours, and fails loudly when the site isn't what was built.
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./fingerprint.mjs";

const sha256 = (b) => createHash("sha256").update(b).digest("hex");
export const SITE = "https://picoquorum.app/";
export const BUILDS = ["app", "emu", "console"];

/** docs/<path> as the repository has it: at a commit, or in this checkout. null when absent. */
export function localReader(commit) {
  return (path) => {
    if (!commit) { const p = join(ROOT, "docs", path); return existsSync(p) ? readFileSync(p) : null; }
    const r = spawnSync("git", ["show", `${commit}:docs/${path}`], { cwd: ROOT, maxBuffer: 64 << 20 });
    return r.status === 0 ? r.stdout : null;
  };
}

/** GET a file from the live site, past the CDN's cache. null on 404. */
export function liveReader(base, fetchImpl = fetch) {
  const stamp = Date.now();
  return async (path) => {
    const r = await fetchImpl(new URL(path, base).href + `?check=${stamp}`, { cache: "no-store", redirect: "error" });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return Buffer.from(await r.arrayBuffer());
  };
}

/**
 * -> { failed: [what], rows: [[ok, what]], status: [string] }
 * live(path) and local(path) read docs/<path> from the site and from the repository.
 * approved(digest) -> true | false | null (no project Safe to ask); optional.
 */
export async function checkSite(live, local, { approved } = {}) {
  const rows = [], failed = [], status = [];
  const row = (ok, what) => { rows.push([ok, what]); if (!ok) failed.push(what); };
  const releases = JSON.parse((local("releases/index.json") || "{}").toString() || "{}").releases || [];
  for (const b of BUILDS) {
    const want = local(`${b}/BUILD.json`), got = await live(`${b}/BUILD.json`);
    if (!want) { row(!got, `${b}: not in the repository${got ? ", but the site serves one" : ""}`); continue; }
    if (!got) { row(false, `${b}: the site serves no ${b}/BUILD.json`); continue; }
    row(sha256(got) === sha256(want), `${b}/BUILD.json as served is the repository's (${sha256(got).slice(0, 12)})`);
    const files = JSON.parse(want.toString()).files || {};
    const bad = [];
    for (const [f, h] of Object.entries(files)) {
      const bytes = await live(`${b}/${f}`.replace(/^[^/]+\/\.\.\//, ""));
      if (!bytes || sha256(bytes) !== h) bad.push(`${f}${bytes ? "" : " (missing)"}`);
    }
    row(!bad.length, `${b}: every one of its ${Object.keys(files).length} files as served matches BUILD.json${bad.length ? `; differ: ${bad.slice(0, 5).join(", ")}` : ""}`);
    // which release this build is, and whether the project Safe approved it
    const h = sha256(want);
    const rel = releases.find((r) => (r.web || {})[b] === h);
    if (!rel) status.push(`${b}: a development build (not a release's)`);
    else {
      const ok = approved && rel.digest ? await approved(rel.digest) : null;
      status.push(`${b}: release ${rel.version}${ok === true ? ", approved by the project Safe" : ok === false ? ", NOT approved by the project Safe" : ""}`);
    }
  }
  for (const p of ["releases/index.json", ...releases.map((r) => `releases/${r.manifest}`)]) {
    const want = local(p), got = await live(p);
    row(!!want && !!got && sha256(want) === sha256(got), `${p} as served is the repository's`);
  }
  return { failed, rows, status };
}

/** The commit GitHub Pages last deployed, from the API (in Actions: gh with the job's token). */
export function pagesCommit(repo) {
  const r = spawnSync("gh", ["api", `repos/${repo}/pages/builds/latest`, "--jq", ".commit"], { encoding: "utf8" });
  return r.status === 0 && /^[0-9a-f]{40}$/.test(r.stdout.trim()) ? r.stdout.trim() : null;
}
