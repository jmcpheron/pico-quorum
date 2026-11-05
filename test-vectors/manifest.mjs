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
  "claim.py", "brand_ui.py"];
// qrcode.py is not on the list: it only turns text into a picture (the Wi-Fi setup screen, wifisetup.py).
// Nor are ceremony_ui.py and setup_s.py, the ceremony's screen: they call no chip, and the console's
// practice (practice.py) draws with them. The ceremony that writes (provision.py) stays out.
// Signer and driver calls that change the chip. Only signer.py and the drivers may even name them
// (atecc.py; trustm_q.py for the Trust M: trustm.py itself has none).
const PERMANENT = /\.(genkey\w*|lock_\w+|provision\w*|write_config|restore_snapshot|write_note|write_data|write_otp|write_record\w*|gen_keypair|set_data|set_lifecycle|set_meta\w*)\(/;
const DRIVERS = ["signer.py", "atecc.py", "trustm_q.py"];

for (const [name, img] of Object.entries(M.images)) {
  const files = [...img.files].sort();
  check(files.every((f) => existsSync(join(FIRMWARE, f))), `${name}: every file exists`);
  const want = closure((img.boot || "boot.py").replace(/\.py$/, ""), img.main.replace(/\.py$/, ""));
  const extra = files.filter((f) => !want.includes(f)), missing = want.filter((f) => !files.includes(f));
  check(!extra.length && !missing.length, `${name}: the list is the import closure of boot.py + ${img.main}` +
    (extra.length ? `; not imported: ${extra}` : "") + (missing.length ? `; missing: ${missing}` : ""));
  check(!files.some((f) => /^secrets/.test(f)), `${name}: no secrets file`);
  check(src(img.main).startsWith(`# picoquorum-image: ${name}\n`), `${name}: ${img.main} carries the image marker`);
}

const con = M.images.console.files;
const q = src("quorum.py").split("\n");
const inSignIt = (i) => { for (let j = i; j >= 0; j--) if (/^def /.test(q[j])) return q[j].startsWith("def sign_it("); return false; };
// The console's rules hold on console-rp's image too: it is the same console, over the link. Its one
// other thing, the owner's key made on the device (keyflow.py), is checked on its own below.
const KEYFLOW = ["keyflow.py"];
for (const [name, files] of [["console", con], ["console-rp", M.images["console-rp"].files]]) {
  const bad = files.filter((f) => NOT_IN_CONSOLE.includes(f));
  check(!bad.length, `${name}: none of the legacy apps, the chip map or the ceremony` + (bad.length ? ` (found ${bad})` : ""));
  for (const f of files.filter((f) => f.endsWith(".py") && !DRIVERS.includes(f) && !(name === "console-rp" && KEYFLOW.includes(f)))) {
    const hits = src(f).split("\n").filter((l) => PERMANENT.test(l) && !/^\s*#/.test(l));
    check(!hits.length, `${name}: ${f} calls nothing that changes the chip` + (hits.length ? `: ${hits[0].trim()}` : ""));
  }
  const signs = files.filter((f) => f.endsWith(".py") && !DRIVERS.includes(f) && !(name === "console-rp" && KEYFLOW.includes(f)))
    .flatMap((f) => src(f).split("\n").map((l, i) => [f, i, l])).filter(([, , l]) => /\bsig\.sign\(|\.chip\.sign\(/.test(l));
  check(signs.length === 1 && signs[0][0] === "quorum.py" && inSignIt(signs[0][1]), `${name}: the chip signs from one place only, quorum.sign_it`);
  // The browser emulator's passkey makes whole assertions (sig.assertion): from sign_it too, and only there.
  const asserts = files.filter((f) => f.endsWith(".py") && !DRIVERS.includes(f))
    .flatMap((f) => src(f).split("\n").map((l, i) => [f, i, l])).filter(([, , l]) => /\bsig\.assertion\(/.test(l));
  check(asserts.length === 1 && asserts[0][0] === "quorum.py" && inSignIt(asserts[0][1]), `${name}: a passkey's assertion is asked for from quorum.sign_it only`);
  check(!files.includes("passkey.py"), `${name}: no image carries the emulator's passkey module`);
}
check(/import quorum/.test(src("main_console.py")) && !/wallet/.test(src("main_console.py")), "console: main imports quorum, not the wallet");
// The practice ceremony (practice.py) reads the config zone and the serial, and asks nothing else of
// the chip; its screen (ceremony_ui.py, setup_s.py) asks nothing of it at all.
const code = (f) => src(f).split("\n").filter((l) => !/^\s*#/.test(l)).join("\n");
const chipCalls = (f) => [...code(f).matchAll(/\b(?:sig|s|self\.sig|self\.chip|S|signer|atecc|trustm\w*)\.(\w+)\(/g)].map((m) => m[1])
  .filter((c) => c !== "split");     // s.split(): a string
check(chipCalls("practice.py").every((c) => ["config", "serial"].includes(c)), "console: the practice only reads the chip (config, serial)" +
  (chipCalls("practice.py").every((c) => ["config", "serial"].includes(c)) ? "" : ` (calls ${chipCalls("practice.py")})`));
check(["ceremony_ui.py", "setup_s.py"].every((f) => chipCalls(f).every((c) => ["arm", "armed", "gate"].includes(c))),
  "console: the ceremony's screen calls no chip, only the signer's arm and gate");
check(/\bdef arm\(self\):\s+self\.c\.arm\(\)/.test(src("practice.py")) && !/\bS\.arm\(|import signer/.test(code("practice.py")),
  "console: the practice arms its own clock, never the signer's");
check(!/\bsig\.use\(/.test(con.map((f) => (f.endsWith(".py") ? src(f) : "")).join("\n")), "console: nothing switches the active slot");

// The USB link (usblink.py, docs/USB-LINK.md): in the console image, holding USB once the console
// runs, and never near the chip: it names no signer, driver or chip call, and writes nothing itself
// (the asks it passes on are written by quorum.py and wifisetup.py, once accepted on the screen).
const link = src("usblink.py");
check(con.includes("usblink.py"), "console: carries the USB link");
check(!/\b(sig|signer|atecc|trustm\w*|S)\.\w+\(|import (signer|atecc|trustm\w*)/.test(link) && !/\bopen\(/.test(link),
  "usblink: no signer, driver or chip call, and no file it writes itself");
const mainLines = src("main_console.py").trimEnd().split("\n");
check(/^\s+usblink\.run\(_quorum\)$/.test(mainLines.at(-1)) && /kbd_intr\(-1\)/.test(mainLines.slice(0, 20).join("\n")),
  "console: main.py turns Ctrl-C off first and ends by handing USB to the link, so it never returns to the REPL");
check(/kbd_intr\(-1\)/.test(src("boot.py").split("\n").slice(0, 8).join("\n")), "boot.py turns Ctrl-C off before anything else");

// console-rp (hardware/console-rp): no radio. Its MicroPython has no network module, and its image
// carries nothing that would use one: no Wi-Fi, no TLS, no certificates. Its one way out is the link
// on UART1 (link.py), which names no signer, driver or chip, writes no file, and can reach only the
// pinned services (link.pinned).
const rp = M.images["console-rp"];
const RADIO = /^\s*(?:import|from)\s+(network|socket|ssl|ntptime|bluetooth|net|vhttp|wifisetup|requests)\b/m;
const radio = rp.files.filter((f) => f.endsWith(".py") && f !== "txservice.py" && RADIO.test(src(f)));
check(!radio.length && !rp.files.some((f) => /^ca_.*\.bin$/.test(f)) && !rp.files.includes("net.py") && !rp.files.includes("vhttp.py"),
  "console-rp: no radio, no TLS, no certificates" + (radio.length ? ` (${radio})` : ""));
check(/try:\s+import requests[^\n]*\nexcept ImportError:/.test(src("txservice.py")), "console-rp: txservice's `requests` is only tried");
check(rp.board === "console-rp" && rp.boot === "boot_rp.py" && rp.files.includes("link.py") && !rp.files.includes("boot.py"),
  "console-rp: an image for one board, with its own boot and the link");
const lk = src("link.py");
check(!/\b(sig|signer|atecc|trustm\w*|S)\.\w+\(|import (signer|atecc|trustm\w*)/.test(lk) && !/\bopen\(/.test(lk),
  "link: no signer, driver or chip call, and no file it writes");
check(/def request\([^)]*\):[\s\S]*?if method not in \("GET", "POST"\) or not pinned\(url\):\s+raise LinkError/.test(lk),
  "link: a request goes only to a pinned service, and nothing is sent otherwise");
const rpLines = src("main_rp.py").trimEnd().split("\n");
check(/^usblink\.run\(_quorum\)$/.test(rpLines.at(-1)) && /kbd_intr\(-1\)/.test(rpLines.slice(0, 20).join("\n")),
  "console-rp: main.py turns Ctrl-C off first and ends in the link's loop, so it never returns to the REPL");
check(/kbd_intr\(-1\)/.test(src("boot_rp.py").split("\n").slice(0, 8).join("\n")) && !/dupterm/.test(src("boot_rp.py") + src("main_rp.py") + lk),
  "console-rp: boot.py turns Ctrl-C off first, and nothing puts the REPL on the link");
// console-rp's own key (keyflow.OwnKey on keypick_rp.py; signer.own_key_step): the customer makes it
// on the device, so this image carries GenKey, the seal and the data lock, and nothing else that changes
// a chip. No config write or lock (that is provision.py's, on the bench), no free digest signed.
const kf = code("keyflow.py");
const kfPerm = kf.split("\n").filter((l) => PERMANENT.test(l)).map((l) => l.trim().match(PERMANENT)[0]);
check(JSON.stringify([...new Set(kfPerm)].sort()) === JSON.stringify([".genkey(", ".genkey_new(", ".lock_data(", ".lock_slot(", ".write_data(", ".write_otp("]),
  "keyflow: GenKey (and the slot-1 refusal), the seal, the record and the data lock, and nothing else that changes a chip" + ` (${[...new Set(kfPerm)]})`);
check(!/\.(lock_config\w*|write_config|write_table|restore_snapshot|provision\w*)\(|import provision/.test(kf), "keyflow: never writes or locks a config zone");
const kfSigns = kf.split("\n").filter((l) => /\.sign\(/.test(l)).map((l) => l.trim());
check(kfSigns.length === 2 && kfSigns.includes("r, s = self.sig.sign(digest, 0)") && kfSigns.includes("self.chip.sign(bytes(32), 1)"),
  "keyflow: signs in _sign_ok, and once on slot 1 to see it refused");
const argsOf = (text, fn) => [...text.matchAll(new RegExp("\\b" + fn + "\\(", "g"))].map((m) => {
  let i = m.index + m[0].length, depth = 1;
  const start = i;
  while (depth && i < text.length) depth += { "(": 1, ")": -1 }[text[i++]] || 0;
  return text.slice(start, i - 1);
});
const signedWhat = argsOf(kf, "self\\._sign_ok");
check(signedWhat.length === 5 && signedWhat.every((x) => /^hashlib\.sha256\(b"[^"]*"\)\.digest\(\)$|^digest$/.test(x)) &&
  [...kf.matchAll(/^\s*\w+, \w+, digest = (.*)$/gm)].every((m) => m[1] === "webauthn.assertion(bytes(32))"),
  "keyflow: the digests it signs are fixed (SHA-256 of its own words, and a WebAuthn assertion over 32 zero bytes)");
const rpPy = rp.files.filter((f) => f.endsWith(".py"));
const arms = rpPy.flatMap((f) => code(f).split("\n").map((l) => [f, l])).filter(([, l]) => /\b(S|signer)\.arm\(/.test(l));
check(arms.length === 2 && arms.some(([f]) => f === "keypick_s.py") && arms.some(([f, l]) => f === "ceremony_ui.py" && l.trim() === "S.arm()") &&
  /def arm\(self\):\s+pass/.test(code("keypick_rp.py")) && /def step_run\(self, step\):[^]*?S\.arm\(10\)\n\s+try:\n[^\n]*\n\s+finally:\n\s+S\.disarm\(\)/.test(code("keypick_s.py")),
  "console-rp: only the key's screen arms the signer, for one call at a time (keypick_s.step_run); the ceremony screen's arm is off there");
const sg = src("signer.py");
const oks = sg.slice(sg.indexOf("def own_key_step("), sg.indexOf("\ndef _may("));
check(/image\.IMAGE != "console-rp"/.test(oks) && /cfg\[87\] != 0x00 or cfg\[86\] != 0x55/.test(oks) && /identify\(cfg\) != "quorum-v1"/.test(oks) &&
  /if cfg\[88\] & 1:\s+return op in \("genkey0", "lock_slot0"\)\s+return op == "lock_data"/.test(oks) &&
  (sg.match(/"console-rp"/g) || []).length === 1 && (oks.match(/"console-rp"/g) || []).length === 1,
  "signer: the own-key gate is console-rp only, a prepared quorum v1 chip only, GenKey and the seal of slot 0 then the data lock");
check((sg.match(/_may\(/g) || []).length === 3 && /def lock_config\(self\):[^]*?if not _allowed\("ALLOW_LOCK"\)/.test(sg) &&
  /def genkey\(self, slot=None\):[^]*?_may\("ALLOW_GENKEY", "genkey%d" % slot, self\.chip\)/.test(sg) && /S\._may\("ALLOW_LOCK", "lock_data", sig\.chip\)/.test(kf),
  "signer: the gate opens ChipSigner's genkey and lock_slot and keyflow's data lock, never a config lock");
const pinNamed = rpPy.filter((f) => /PIN_FILE|"pin\.json"/.test(code(f)));
check(JSON.stringify(pinNamed) === JSON.stringify(["keyflow.py", "policy.py"]) && /write_json\(policy\.PIN_FILE/.test(kf) &&
  !/open\(PIN_FILE, "w/.test(code("policy.py")), "console-rp: only the key flow writes pin.json; the console only reads it (policy.pin_file)");
const qc = closure("quorum");
check(!["keyflow.py", "keypick_rp.py", "keypick_s.py", "provision.py"].some((f) => qc.includes(f)), "quorum's closure has no key flow and no ceremony");
// prepare-rp (prepare.py, main_prep_rp.py): the bench half of console-rp's key. C1-C3 and a read-only
// check, never a key: no GenKey, no public-key read (on an empty slot that is a GenKey command), no seal.
const pr = M.images["prepare-rp"];
// provision.py's one radio line is C8's clock (an ntptime tried in date()): prepare-rp stops at P4.
const provRadio = src("provision.py").split("\n").filter((l) => RADIO.test(l)).map((l) => l.trim());
const prRadio = pr.files.filter((f) => f.endsWith(".py") && f !== "txservice.py" && RADIO.test(src(f)) &&
  !(f === "provision.py" && JSON.stringify(provRadio) === JSON.stringify(["import ntptime      # the record's date; boot.py joined the WiFi"])));
check(pr.board === "console-rp" && pr.boot === "boot_rp.py" && !prRadio.length && !pr.files.some((f) => /^ca_.*\.bin$|^(net|vhttp|quorum|txservice)\.py$/.test(f)),
  "prepare-rp: one board, no radio, no Safe console" + (prRadio.length ? ` (${prRadio})` : ""));
const prep = code("prepare.py");
check(/GENKEY = \(\)/.test(prep) && /PERMANENT = \("C3",\)/.test(prep) && /def read_key\(self\):\s+return None/.test(prep) &&
  /elif step in \("C1", "C2", "C3"\):\s+out = super\(\)\.run\(step\)\s+else:\s+out = self\.cother\(\)/.test(prep) &&
  !/ALLOW_GENKEY|\.genkey|\.lock_slot|\.lock_data|\.sign\(/.test(prep + code("main_prep_rp.py")),
  "prepare-rp: runs C1-C3 and its read-only check only; never GenKey, a public-key read, a seal or a signature");
const crtIn = Object.entries(M.images).filter(([, img]) => img.files.some((f) => f === "crt.py" || f === "quorum_ui_crt.py"));
check(crtIn.length === 1 && crtIn[0][0] === "console-rp" && rp.files.includes("crt.py") && rp.files.includes("quorum_ui_crt.py"),
  "the CRT screens (crt.py, quorum_ui_crt.py) are on the console-rp image only" + (crtIn.length ? ` (${crtIn.map((e) => e[0])})` : ""));
const crtSrc = src("crt.py") + src("quorum_ui_crt.py");
check(!/import (signer|atecc|trustm\w*|safe_tx|txservice|link)\b/.test(crtSrc) && !/\bopen\(/.test(crtSrc),
  "the CRT screens draw only: no signer, chip, hash, service or link, and no file");

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
