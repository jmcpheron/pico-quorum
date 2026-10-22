// firmware/manifest.json against the firmware itself: each image is exactly what its main and
// boot.py import, the console image carries nothing else that can use the chip, no image carries
// secrets, and the ceremony and brand images have no Safe console in them.
//   node test-vectors/manifest.mjs
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { FIRMWARE } from "../emu/core/workspace.mjs";
import { dependencies } from "../emu/core/ship.mjs";

const M = JSON.parse(readFileSync(join(FIRMWARE, "manifest.json"), "utf8"));
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? "pass" : "FAIL"}  ${what}`); if (!ok) failed++; };
const src = (f) => readFileSync(join(FIRMWARE, f), "utf8");
const closure = (...mods) => [...new Set(mods.flatMap((m) => dependencies(m)))].sort();

// Apps and screens that can use the chip other than the console's one signature path.
const NOT_IN_CONSOLE = ["chipcheck.py", "slots.py", "chipmap.py", "learn.py", "snakelab.py", "ceremony.py",
  "chipapp.py", "provision.py", "provision_tm.py", "main_ceremony.py", "brand.py", "main_brand.py",
  "claim.py", "brand_ui.py", "setup_s.py"];
// qrcode.py is not on the list: it only turns text into a picture (the Wi-Fi setup screen, wifisetup.py).
// Signer and driver calls that change the chip. Only signer.py and the drivers may even name them
// (atecc.py; trustm_q.py for the Trust M: trustm.py itself has none).
const PERMANENT = /\.(genkey\w*|lock_\w+|provision\w*|write_config|restore_snapshot|write_note|write_data|write_otp|write_record\w*|gen_keypair|set_data|set_lifecycle|set_meta\w*)\(/;
const DRIVERS = ["signer.py", "atecc.py", "trustm_q.py"];

for (const [name, img] of Object.entries(M.images)) {
  const files = [...img.files].sort();
  check(files.every((f) => existsSync(join(FIRMWARE, f))), `${name}: every file exists`);
  const want = closure("boot", img.main.replace(/\.py$/, ""));
  const extra = files.filter((f) => !want.includes(f)), missing = want.filter((f) => !files.includes(f));
  check(!extra.length && !missing.length, `${name}: the list is the import closure of boot.py + ${img.main}` +
    (extra.length ? `; not imported: ${extra}` : "") + (missing.length ? `; missing: ${missing}` : ""));
  check(!files.some((f) => /^secrets/.test(f)), `${name}: no secrets file`);
  check(src(img.main).startsWith(`# picoquorum-image: ${name}\n`), `${name}: ${img.main} carries the image marker`);
}

const con = M.images.console.files;
const bad = con.filter((f) => NOT_IN_CONSOLE.includes(f));
check(!bad.length, "console: none of the legacy apps, the chip map or the ceremony" + (bad.length ? ` (found ${bad})` : ""));
check(/import quorum/.test(src("main_console.py")) && !/wallet/.test(src("main_console.py")), "console: main imports quorum, not the wallet");
for (const f of con.filter((f) => f.endsWith(".py") && !DRIVERS.includes(f))) {
  const hits = src(f).split("\n").filter((l) => PERMANENT.test(l) && !/^\s*#/.test(l));
  check(!hits.length, `console: ${f} calls nothing that changes the chip` + (hits.length ? `: ${hits[0].trim()}` : ""));
}
const signs = con.filter((f) => f.endsWith(".py") && !DRIVERS.includes(f))
  .flatMap((f) => src(f).split("\n").map((l, i) => [f, i, l])).filter(([, , l]) => /\bsig\.sign\(|\.chip\.sign\(/.test(l));
const q = src("quorum.py").split("\n");
const inSignIt = (i) => { for (let j = i; j >= 0; j--) if (/^def /.test(q[j])) return q[j].startsWith("def sign_it("); return false; };
check(signs.length === 1 && signs[0][0] === "quorum.py" && inSignIt(signs[0][1]), "console: the chip signs from one place only, quorum.sign_it");
// The browser emulator's passkey makes whole assertions (sig.assertion): from sign_it too, and only there.
const asserts = con.filter((f) => f.endsWith(".py") && !DRIVERS.includes(f))
  .flatMap((f) => src(f).split("\n").map((l, i) => [f, i, l])).filter(([, , l]) => /\bsig\.assertion\(/.test(l));
check(asserts.length === 1 && asserts[0][0] === "quorum.py" && inSignIt(asserts[0][1]), "console: a passkey's assertion is asked for from quorum.sign_it only");
check(!con.includes("passkey.py"), "console: no image carries the emulator's passkey module");
check(!/\bsig\.use\(/.test(con.map((f) => (f.endsWith(".py") ? src(f) : "")).join("\n")), "console: nothing switches the active slot");

// tools/fw build compiles every module but boot.py and main.py with plain mpy-cross (no -march):
// a native or viper function in them would not survive that.
for (const [name, img] of Object.entries(M.images)) {
  const nat = img.files.filter((f) => f.endsWith(".py") && /@micropython\.(native|viper)/.test(src(f)));
  check(!nat.length, `${name}: no @micropython.native/viper code (it goes on as bytecode .mpy)` + (nat.length ? `: ${nat}` : ""));
}

const cer = M.images.ceremony.files;
check(!cer.includes("quorum.py") && !cer.includes("txservice.py"), "ceremony: no Safe console and no transaction service");
const brd = M.images.brand.files;
check(!brd.includes("quorum.py") && !brd.includes("txservice.py"), "brand: no Safe console and no transaction service");
check(!M.images.dual.files.includes("brand.py") && !cer.includes("brand.py"), "brand.py is on the brand image only");
check(M.images.dual.files.includes("claim.py") && brd.includes("claim.py") && !cer.includes("claim.py"),
  "claim.py is on the dual image (the claim) and the brand image (the spare's S steps) only");
check(M.preserve.some((p) => p === "secrets.py"), "secrets.py is preserved by every push");
console.log(failed ? `${failed} FAILED` : "manifest: all pass");
process.exit(failed ? 1 : 0);
