// tools/releases/site.mjs against a site it can lie to: docs/ served from this checkout passes, then
// the same site with one byte of the app changed, a file missing, a BUILD.json that vouches for a
// changed file, and a release manifest swapped, each fail. The status line names a release and its
// approval when a build's BUILD.json is one. No network.
//   node tools/releases/site-test.mjs
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { BUILDS, checkSite, localReader } from "./site.mjs";

const sha256 = (b) => createHash("sha256").update(b).digest("hex");
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };
const local = localReader(null);

// a "live site" reading the checkout, with changes on top
const site = (changes = {}) => async (path) => (path in changes ? changes[path] : local(path));

let r = await checkSite(site(), local);
check(!r.failed.length, `the site as built passes (${r.rows.length} checks)`);
check(r.status.every((s) => /development build|release/.test(s)), `status: ${r.status.join("; ")}`);

const appJs = local("app/app.js");
const tampered = Buffer.concat([appJs.subarray(0, 100), Buffer.from("/*x*/"), appJs.subarray(100)]);
r = await checkSite(site({ "app/app.js": tampered }), local);
check(r.failed.some((f) => /app: every one.*app\.js/.test(f)), "one changed file in the app: caught, and named");

r = await checkSite(site({ "app/app.css": null }), local);
check(r.failed.some((f) => /app\.css \(missing\)/.test(f)), "a file the build lists, missing from the site: caught");

const build = JSON.parse(local("app/BUILD.json").toString());
build.files["app.js"] = sha256(tampered);
r = await checkSite(site({ "app/app.js": tampered, "app/BUILD.json": Buffer.from(JSON.stringify(build, null, 2) + "\n") }), local);
check(r.failed.some((f) => /app\/BUILD\.json as served/.test(f)), "a changed file with a BUILD.json that vouches for it: caught (BUILD.json isn't the repository's)");

r = await checkSite(site({ "index.html": Buffer.from("<!doctype html><p>hi</p>") }), local);
check(r.failed.some((f) => /\.\.\/index\.html/.test(f)), "the front page (listed in the app's BUILD.json) changed: caught");

r = await checkSite(site({ "releases/index.json": Buffer.from('{"releases":[]}') }), local);
check(r.failed.some((f) => /releases\/index\.json/.test(f)), "the release list changed: caught");

// a build that is a release, approved or not
const fake = { releases: [{ version: "2026.10.9", manifest: "2026.10.9.json", digest: "0x" + "ab".repeat(32),
  web: Object.fromEntries(BUILDS.map((b) => [b, local(`${b}/BUILD.json`) ? sha256(local(`${b}/BUILD.json`)) : null])) }] };
const withRel = (path) => (path === "releases/index.json" ? Buffer.from(JSON.stringify(fake)) : path === "releases/2026.10.9.json" ? Buffer.from("{}") : local(path));
r = await checkSite(withRel, withRel, { approved: async () => true });
check(r.status.some((s) => /app: release 2026\.10\.9, approved by the project Safe/.test(s)), "a build that is a release: named, with its approval");
r = await checkSite(withRel, withRel, { approved: async () => false });
check(r.status.some((s) => /NOT approved/.test(s)), "and when the project Safe hasn't approved it, it says so");

console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
