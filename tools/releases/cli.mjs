// tools/release: make a PicoQuorum release from this checkout, and the checks CI makes on one.
//
// A release is a commit tagged fw-<version>, the tag SSH-signed by a key in .github/allowed_signers,
// with docs/releases/<version>.json committed in it: each image's release fingerprint and source
// hashes (tools/releases/fingerprint.mjs) and the hashes of the web builds' BUILD.json files.
// .github/workflows/release.yml checks all of that again, builds the firmware images and publishes
// a GitHub Release. docs/RELEASES.md has the steps.
//
//   tools/release check              everything a tag needs, without tagging (clean tree, version
//                                    not yet tagged, RELEASES.md entry, manifest current, fast tests)
//   tools/release manifest           write docs/releases/<version>.json and its entry in index.json
//   tools/release verify [VERSION]   the committed manifest matches this checkout (CI runs this)
//   tools/release tag [--push]       sign and create fw-<version>; check the signature against
//                                    .github/allowed_signers; push it with --push
//   tools/release approval [VERSION] the Safe transaction that has the project Safe approve it
//                                    (docs/GOVERNANCE.md): its digest, calldata and origin note
//   tools/release check-site [URL] [--commit SHA | --pages owner/repo]
//                                    the live site against what the repository built (site.mjs)
//   tools/release release-json --out FILE BUILD_DIR...   CI: release.json for the GitHub Release
//   tools/release notes VERSION      CI: that version's section of docs/RELEASES.md
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FIRMWARE, ROOT, imageFingerprint, manifest, short } from "./fingerprint.mjs";
import { approvalTx, isApproved, releaseDigest, safeMessageHash } from "../mock-tx-service/release.mjs";
import { SITE, checkSite, liveReader, localReader, pagesCommit } from "./site.mjs";

const RELEASES = join(ROOT, "docs", "releases");
const SIGNERS = join(ROOT, ".github", "allowed_signers");
const argv = process.argv.slice(2);
const cmd = argv[0];
const has = (k) => argv.includes(k);
const opt = (k) => (argv.includes(k) ? argv[argv.indexOf(k) + 1] : undefined);
const sha256 = (b) => createHash("sha256").update(b).digest("hex");
const tagOf = (v) => `fw-${v}`;
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; return ok; };

function die(msg) {
  console.error("tools/release: " + msg);
  process.exit(1);
}

function git(...a) {
  const r = spawnSync("git", a, { cwd: ROOT, encoding: "utf8" });
  return { ok: r.status === 0, out: (r.stdout || "").trim(), err: (r.stderr || "").trim() };
}

function run(what, command, args, cwd = ROOT) {
  const r = spawnSync(command, args, { cwd, encoding: "utf8" });
  return check(r.status === 0, what + (r.status === 0 ? "" : `\n${(r.stdout || "").split("\n").filter((l) => /FAIL|Error/.test(l)).slice(0, 8).join("\n")}${r.stderr ? "\n" + r.stderr.slice(-400) : ""}`));
}

// ----------------------------------------------------------------------------- the manifest
// What docs/releases/<version>.json says, computed from this checkout. "web" is the SHA-256 of each
// web build's BUILD.json, which itself lists the SHA-256 of every file that build wrote.
function computed() {
  const m = manifest();
  const images = {}, fingerprints = {};
  for (const [name, img] of Object.entries(m.images)) {
    fingerprints[name] = imageFingerprint(name, undefined, m);
    images[name] = { main: img.main, files: Object.fromEntries([...new Set(img.files)].sort().map((f) => [f, sha256(readFileSync(join(FIRMWARE, f)))])) };
  }
  const web = {};
  for (const [k, p] of [["app", "docs/app/BUILD.json"], ["emu", "docs/emu/BUILD.json"]])
    web[k] = existsSync(join(ROOT, p)) ? sha256(readFileSync(join(ROOT, p))) : null;
  return { version: m.version, fingerprints, web, images };
}

const manifestPath = (v) => join(RELEASES, `${v}.json`);
const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
const writeJson = (p, o) => writeFileSync(p, JSON.stringify(o, null, 2) + "\n");

// docs/releases/<version>.json is written once, before the tag, and never changed after: its SHA-256
// is in the tag's message and in the digest the project Safe approves. What comes later (the commit,
// the approval transaction) goes in index.json beside it.
function writeManifest() {
  const c = computed();
  const p = manifestPath(c.version);
  const old = existsSync(p) ? readJson(p) : {};
  if (old.version && git("ls-remote", "--tags", "origin", `refs/tags/${tagOf(c.version)}`).out)
    die(`${tagOf(c.version)} is already released: docs/releases/${c.version}.json stays as it is. Set a new version.`);
  writeJson(p, {
    note: "A PicoQuorum release, written by tools/release manifest and never changed after its tag. fingerprints: each image's release fingerprint (tools/releases/fingerprint.mjs). images: the SHA-256 of every source file. web: the SHA-256 of each web build's BUILD.json. The project Safe approves sha256(this file) with the console fingerprint (docs/GOVERNANCE.md).",
    version: c.version, date: old.date || new Date().toISOString().slice(0, 10),
    fingerprints: c.fingerprints, web: c.web, images: c.images,
  });
  const entry = indexEntry(c.version);
  const idxPath = join(RELEASES, "index.json");
  const idx = readJson(idxPath);
  const keep = (idx.releases || []).find((r) => r.version === c.version) || {};
  idx.releases = [{ ...entry, ...(keep.commit ? { commit: keep.commit } : {}), ...(keep.approval ? { approval: keep.approval } : {}) },
    ...(idx.releases || []).filter((r) => r.version !== c.version)]
    .sort((a, b) => b.version.localeCompare(a.version, "en", { numeric: true }));
  writeJson(idxPath, idx);
  console.log(`wrote docs/releases/${c.version}.json and its index entry`);
  for (const [k, v] of Object.entries(c.fingerprints)) console.log(`  ${k.padEnd(9)} ${short(v)}  ${v}`);
  for (const [k, v] of Object.entries(c.web)) console.log(`  web ${k.padEnd(5)} ${v || "(no build)"}`);
  console.log(`  manifest  ${entry.manifestSha256}\n  digest    ${entry.digest}  (what the project Safe approves)`);
}

// A release's line in index.json: what the app lists, and what the project Safe approves.
function indexEntry(version) {
  const m = readJson(manifestPath(version));
  const manifestSha256 = sha256(readFileSync(manifestPath(version)));
  return { version, date: m.date, fingerprints: m.fingerprints, web: m.web, manifest: `${version}.json`, manifestSha256,
    digest: releaseDigest({ version, firmware: "0x" + m.fingerprints.console, manifest: "0x" + manifestSha256 }) };
}

function approval() {
  const v = argv[1] || manifest().version;
  if (!existsSync(manifestPath(v))) die(`no docs/releases/${v}.json`);
  const e = indexEntry(v);
  const tx = approvalTx({ version: v, firmware: "0x" + e.fingerprints.console, manifest: "0x" + e.manifestSha256 });
  const project = (() => { try { const src = readFileSync(join(FIRMWARE, "quorum_cfg.py"), "utf8"); return JSON.parse(src.slice(src.indexOf("{", src.indexOf("CFG =")))).project; } catch { return null; } })();
  console.log(`Release ${v}: the project Safe approves digest ${tx.digest}`);
  console.log(`  firmware ${short(e.fingerprints.console)}  ${e.fingerprints.console}\n  manifest sha256 ${e.manifestSha256}\n`);
  console.log("The Safe transaction (propose it from the app's Releases page, or any Safe tool):");
  console.log(JSON.stringify({ to: tx.to, value: "0", data: tx.data, operation: 1, origin: tx.origin }, null, 2));
  if (project?.address) console.log(`\nOnce executed on chain ${project.chainId}: isValidSignature(${tx.digest}, 0x) on ${project.address} returns 0x1626ba7e` +
    `\n(the Safe's message hash: ${safeMessageHash(project.chainId, project.address, tx.digest)}).`);
  else console.log("\nNo project Safe in firmware/quorum_cfg.py \"project\" yet (docs/GOVERNANCE.md).");
}

// The committed manifest for a version, against this checkout. Returns the number of mismatches.
function verify(version) {
  const c = computed();
  version ||= c.version;
  const p = manifestPath(version);
  if (!check(existsSync(p), `docs/releases/${version}.json exists (tools/release manifest writes it)`)) return;
  const want = readJson(p);
  check(want.version === version && c.version === version, `firmware/manifest.json version is ${version}`);
  for (const [k, v] of Object.entries(c.fingerprints)) check(want.fingerprints?.[k] === v, `${k} fingerprint ${short(v)} matches the manifest`);
  for (const [k, v] of Object.entries(c.web)) check(want.web?.[k] === v, `web ${k} BUILD.json ${v ? v.slice(0, 12) : "(none)"} matches the manifest`);
  check(JSON.stringify(want.images) === JSON.stringify(c.images), "every source file's hash matches the manifest");
  const idx = readJson(join(RELEASES, "index.json"));
  const e = (idx.releases || []).find((r) => r.version === version);
  const need = indexEntry(version);
  check(e && JSON.stringify(e.fingerprints) === JSON.stringify(c.fingerprints), `docs/releases/index.json lists ${version} with these fingerprints`);
  check(e && e.manifestSha256 === need.manifestSha256 && e.digest === need.digest && JSON.stringify(e.web) === JSON.stringify(need.web),
    `index.json has its manifest's SHA-256, its web builds' hashes and the digest the project Safe approves`);
}

// ----------------------------------------------------------------------------- check and tag
function releasesEntry(v) {
  const md = readFileSync(join(ROOT, "docs", "RELEASES.md"), "utf8");
  const i = md.search(new RegExp(`^## ${v.replace(/\./g, "\\.")}\\b`, "m"));
  if (i < 0) return null;
  const rest = md.slice(i);
  const j = rest.slice(3).search(/^## /m);
  return (j < 0 ? rest : rest.slice(0, j + 3)).trim();
}

function preflight({ tests = true } = {}) {
  const v = manifest().version;
  console.log(`release ${v} (tag ${tagOf(v)})`);
  check(/^\d{4}\.\d{1,2}\.\d+$/.test(v), `the version is year.month.n`);
  check(git("status", "--porcelain").out === "", "the working tree is clean (commit everything first)");
  const branch = git("rev-parse", "--abbrev-ref", "HEAD").out;
  check(branch === "main", `on main (on ${branch})`);
  check(!git("rev-parse", "-q", "--verify", `refs/tags/${tagOf(v)}`).ok, `no local tag ${tagOf(v)} yet`);
  const remote = git("ls-remote", "--tags", "origin", `refs/tags/${tagOf(v)}`);
  check(remote.ok && remote.out === "", remote.ok ? `no tag ${tagOf(v)} on origin yet` : `origin answers (${remote.err.split("\n")[0]})`);
  check(!!releasesEntry(v), `docs/RELEASES.md has a "## ${v}" entry`);
  verify(v);
  if (tests) {
    run("python3 test-vectors/run.py", "python3", ["test-vectors/run.py"]);
    run("python3 test-vectors/fingerprint_test.py", "python3", ["test-vectors/fingerprint_test.py"]);
    run("node test-vectors/manifest.mjs", "node", ["test-vectors/manifest.mjs"]);
  }
  return v;
}

function tag() {
  const v = preflight();
  if (failed) die(`${failed} check${failed > 1 ? "s" : ""} failed; nothing tagged`);
  const fmt = git("config", "--get", "gpg.format").out, key = git("config", "--get", "user.signingkey").out;
  if (fmt !== "ssh" || !key) die("tags are SSH-signed: git config gpg.format ssh and git config user.signingkey <key> (docs/RELEASES.md, Signing)");
  if (!existsSync(SIGNERS) || !readFileSync(SIGNERS, "utf8").split("\n").some((l) => l.trim() && !l.startsWith("#")))
    die(".github/allowed_signers lists no key: CI would refuse the tag (docs/RELEASES.md, Signing)");
  const c = computed();
  const msg = [`PicoQuorum ${v}`, "", ...Object.entries(c.fingerprints).map(([k, f]) => `${k} ${f}`),
    `manifest docs/releases/${v}.json sha256 ${sha256(readFileSync(manifestPath(v)))}`, ""].join("\n");
  const dir = mkdtempSync(join(tmpdir(), "pq-tag-"));
  writeFileSync(join(dir, "msg"), msg);
  const t = git("tag", "-s", tagOf(v), "-F", join(dir, "msg"));
  rmSync(dir, { recursive: true, force: true });
  if (!t.ok) die(`git tag -s failed: ${t.err}`);
  const vv = git("-c", `gpg.ssh.allowedSignersFile=${SIGNERS}`, "tag", "-v", tagOf(v));
  if (!vv.ok) {
    git("tag", "-d", tagOf(v));
    die(`the tag's signature doesn't check against .github/allowed_signers, so CI would refuse it; tag deleted.\n${vv.err}`);
  }
  console.log(`signed ${tagOf(v)}: ${vv.err.split("\n").find((l) => /Good/.test(l)) || "good signature"}`);
  if (has("--push")) {
    const p = git("push", "origin", tagOf(v));
    if (!p.ok) die(`push failed: ${p.err}`);
    console.log(`pushed ${tagOf(v)}: .github/workflows/release.yml checks it and publishes the release`);
  } else console.log(`push it: git push origin ${tagOf(v)}`);
}

// ----------------------------------------------------------------------------- for CI
function releaseJson() {
  const out = opt("--out") || die("release-json --out FILE BUILD_DIR...");
  const dirs = argv.slice(1).filter((a, i, all) => a !== "--out" && all[i - 1] !== "--out");
  const c = computed();
  const commit = git("rev-parse", "HEAD").out;
  const builds = {};
  for (const d of dirs) {
    const py = readFileSync(join(d, "build.py"), "utf8");
    const field = (k) => (new RegExp(`^${k} = "([^"]*)"`, "m").exec(py) || [])[1];
    const image = field("IMAGE");
    if (field("RELEASE") !== c.fingerprints[image]) die(`${d}: build.py RELEASE ${field("RELEASE")} isn't the ${image} fingerprint ${c.fingerprints[image]}`);
    builds[image] = { build: field("BUILD"), release: field("RELEASE"),
      files: Object.fromEntries(readdirSync(d).filter((f) => f !== "build.py").sort().map((f) => [f, sha256(readFileSync(join(d, f)))])) };
  }
  writeJson(out, { version: c.version, tag: tagOf(c.version), commit, fingerprints: c.fingerprints, web: c.web,
    digest: existsSync(manifestPath(c.version)) ? indexEntry(c.version).digest : null,
    manifest: existsSync(manifestPath(c.version)) ? { path: `docs/releases/${c.version}.json`, sha256: sha256(readFileSync(manifestPath(c.version))) } : null,
    builds });
  console.log(`wrote ${out}`);
}

async function checkSiteCmd() {
  const base = argv.slice(1).find((a) => /^https?:/.test(a)) || SITE;
  const commit = opt("--commit") || (opt("--pages") ? pagesCommit(opt("--pages")) : null);
  if (opt("--pages") && !commit) die("couldn't read the commit Pages deployed (gh api .../pages/builds/latest)");
  const cfg = (() => { const src = readFileSync(join(FIRMWARE, "quorum_cfg.py"), "utf8"); return JSON.parse(src.slice(src.indexOf("{", src.indexOf("CFG =")))); })();
  let approved;
  if (cfg.project?.address) {
    const { createPublicClient, http } = await import("viem");
    const rpc = { 1: process.env.ETH_RPC || "https://ethereum-rpc.publicnode.com", 8453: "https://mainnet.base.org", 84532: "https://sepolia.base.org" }[cfg.project.chainId];
    const client = createPublicClient({ transport: http(rpc) });
    approved = (d) => isApproved(client, cfg.project.address, d);
  }
  console.log(`the live site ${base} against docs/ ${commit ? `at ${commit.slice(0, 12)} (what Pages deployed)` : "in this checkout"}`);
  const r = await checkSite(liveReader(base), localReader(commit), { approved });
  for (const [ok, what] of r.rows) check(ok, what);
  for (const s of r.status) console.log(`      ${s}`);
  console.log(failed ? `${failed} FAILED: the site is not serving what the repository built` : "the site serves exactly what the repository built");
}

const commands = {
  check: () => { preflight(); console.log(failed ? `${failed} FAILED` : "ready to tag"); },
  manifest: writeManifest,
  verify: () => { verify(argv[1]); console.log(failed ? `${failed} FAILED` : "the manifest matches this checkout"); },
  tag,
  "release-json": releaseJson,
  approval,
  "check-site": checkSiteCmd,
  notes: () => { const e = releasesEntry(argv[1] || manifest().version); if (!e) die(`no "## ${argv[1]}" in docs/RELEASES.md`); console.log(e); },
};
if (!commands[cmd]) die(`usage: tools/release ${Object.keys(commands).join(" | ")}`);
await commands[cmd]();
process.exit(failed ? 1 : 0);
