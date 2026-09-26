// tools/fw: the Pico as a production device, over USB (mpremote). Everything here reads the board
// first and says what it will do; the commands that write ask for a typed "yes".
//
//   build console|ceremony   build/<image>-<sha>/: the manifest's files, main.py, and build.py (IMAGE,
//                            BUILD = git sha, DATE, FILES). Never committed.
//   backup                   every file on the board into backups/<board-id>/<UTC>/ (gitignored,
//                            chmod 700: it holds the board's secrets.py), each checked by SHA-256
//                            against a hash computed on the board. Read-only on the board.
//   verify [--baseline]      read-only: the board's files against the manifest and this checkout,
//                            stale files, the secrets.py flags (names and booleans only), the
//                            console's live state. --baseline also reads the chip itself.
//   logs                     log.txt, log.1.txt and error.log into backups/<board-id>/logs-<UTC>/
//   pin                      read the chip (serial, slot 0's key and lock), compute its owner here,
//                            compare it with tools/mock-tx-service/live.json, and write QUORUM_EXPECT
//                            into the board's secrets.py (the old file is kept as secrets.bak).
//   push console|ceremony    backup, then the plan (copy, delete stale, keep, ask), "yes", then:
//                            maintenance, copy, check every hash, delete stale, leave maintenance.
//   restore DIR [--exact] [--secrets]   a backup back onto the board (secrets.py only with --secrets;
//                            --exact also deletes files that are not in the backup)
//   measure tls              runs tools/board/measure_tls.py on the board, in RAM only
//   restart                  machine.reset(), hands off for 30 s while the console starts, then verify
//
// Port: $PICO_PORT, else the first /dev/cu.usbmodem* (mac) or /dev/ttyACM* (linux).
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline/promises";
import { MPREMOTE, serialPorts } from "../../emu/core/devices.mjs";
import { FIRMWARE, ROOT } from "../../emu/core/workspace.mjs";

const M = JSON.parse(readFileSync(join(FIRMWARE, "manifest.json"), "utf8"));
const argv = process.argv.slice(2);
const cmd = argv[0];
const has = (k) => argv.includes(k);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");
const stamp = () => new Date().toISOString().replace(/[:]/g, "").replace(/\.\d+Z$/, "Z");
const glob = (p) => new RegExp("^" + p.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$");
const matches = (list, f) => list.some((p) => glob(p).test(f));

function die(msg) {
  console.error("tools/fw: " + msg);
  process.exit(1);
}

let PORT = null;
function port() {
  if (!PORT) PORT = process.env.PICO_PORT || serialPorts()[0];
  if (!PORT) die("no Pico on USB (looked for /dev/cu.usbmodem* and /dev/ttyACM*; set PICO_PORT=...)");
  return PORT;
}

// One mpremote session. resume: attach without a soft reset (whatever runs keeps running).
function mp(args, { resume = true, timeout = 30000 } = {}) {
  const r = spawnSync(MPREMOTE, ["connect", port(), ...(resume ? ["resume"] : []), ...args], { encoding: "utf8", timeout });
  return { code: r.status, out: (r.stdout || "") + (r.stderr || ""), timedOut: r.error?.code === "ETIMEDOUT" };
}

function run(code, opts) {
  const r = mp(["exec", code], opts);
  if (r.timedOut) die(`no answer from the board in time. If the USB link is wedged, unplug the Pico and plug it back in.\n${r.out.slice(-400)}`);
  if (r.code !== 0) die(`the board did not run it:\n${r.out.slice(-800)}`);
  return r.out;
}

// A tagged line of JSON printed by the board.
function tagged(out, tag) {
  const line = out.split(/\r?\n/).find((l) => l.startsWith(tag + ":"));
  if (!line) die(`no ${tag} from the board:\n${out.slice(-800)}`);
  return JSON.parse(line.slice(tag.length + 1));
}

// Every file on the board with its size and SHA-256, computed there.
const LIST_PY = `import os, hashlib, json, binascii
def _walk(d):
    out = []
    for n in os.listdir(d or "/"):
        p = d + "/" + n if d else n
        st = os.stat(p)
        if st[0] & 0x4000:
            out += _walk(p)
        else:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while True:
                    b = f.read(1024)
                    if not b:
                        break
                    h.update(b)
            out.append([p, st[6], binascii.hexlify(h.digest()).decode()])
    return out
print("FILES:" + json.dumps(_walk("")))`;

// Whatever app runs on its timer (the console, the legacy wallet, the ceremony's chip map) is paused
// while files are read: anything it prints lands in the middle of mpremote's transfer, and the
// first backup of the wallet Pico came back corrupted that way and wedged its USB link (2026-09-26).
// The watchdog, if the console started one, is told to wait 10 minutes, then set back to 5 s.
const PAUSE_PY = `import sys, json
_p = []
try:
    import watch
    watch.hold(600000)
except (ImportError, AttributeError):
    pass
for _n in ("quorum", "wallet", "chipapp"):
    _m = sys.modules.get(_n)
    if _m and getattr(_m, "timer", None) and hasattr(_m, "stop"):
        _m.stop()
        _p.append(_n)
print("PAUSED:" + json.dumps(_p))`;
let paused = null;
function pause() {
  if (paused === null) paused = tagged(run(PAUSE_PY), "PAUSED");
}
function unpause() {
  if (!paused || !paused.length) return (paused = null);
  run(`import sys
for _n in ${JSON.stringify(paused)}:
    sys.modules[_n].start_timer()
try:
    import watch
    watch.hold(5000)
except (ImportError, AttributeError):
    pass
print("RESUMED")`);
  console.log(`(${paused.join(", ")} paused while reading, running again)`);
  paused = null;
}

function boardFiles(opts) {
  return tagged(run(LIST_PY, opts), "FILES").map(([name, size, sha]) => ({ name, size, sha }));
}

function boardId() {
  return tagged(run("import machine, binascii, json\nprint('UID:' + json.dumps(binascii.hexlify(machine.unique_id()).decode()))"), "UID");
}

// secrets.py as names and harmless values: booleans, numbers, None, URLs, the Safe and the pin.
// The WiFi password and the API key show only as <set>.
const FLAGS_PY = `import json
try:
    _s = {}
    exec(open("secrets.py").read(), _s)      # the file as it is now, not a module the app imported earlier
    _o = {}
    for _k in _s:
        if _k.startswith("_"):
            continue
        _v = _s[_k]
        if _v is None or isinstance(_v, (bool, int)) or _k in ("QUORUM_URL", "QUORUM_SAFE", "QUORUM_EXPECT", "QUORUM_THEME", "WIFI_SSID", "HOSTNAME", "DEVICE_NAME"):
            _o[_k] = _v
        else:
            _o[_k] = "<set>"
    print("FLAGS:" + json.dumps(_o))
except OSError:
    print("FLAGS:null")`;

// What the running console knows about itself (production image, or a dev board running quorum).
const LIVE_PY = `import sys, json, gc
q = sys.modules.get("quorum")
o = None
if q:
    import image
    o = {"image": image.IMAGE, "build": image.BUILD, "state": q.state, "me": q.me, "serial": q.serial, "slot": q.sig.slot if q.sig else None,
         "pin_ok": q.pin_ok, "pin_why": q.pin_why, "counter": q.counter, "outside": q.outside, "net_ok": q.net_ok, "net_err": q.net_err,
         "chain": q.CHAIN, "safe": q.SAFE_ADDR, "tls": q.svc.tls if q.svc else None, "requests": q.svc.requests if q.svc else None,
         "queue": len(q.queue), "owner": q.me in q.owners(), "free": gc.mem_free()}
    try:
        import watch
        o["watchdog"] = watch.running()
    except ImportError:
        pass
print("LIVE:" + json.dumps(o))`;

// The chip itself: serial, slot 0's public key, the lock bytes and counter 0. Read-only.
const CHIP_PY = `import json, atecc
c = atecc.ATECC608()
cfg = c.read_config_all()
x, y = c.pubkey(0)
row = atecc.decode_slot(cfg, 0)
print("CHIP:" + json.dumps({"serial": "".join("%02x" % b for b in c.serial()), "revision": "".join("%02x" % b for b in c.revision()),
      "qx": "0x%064x" % x, "qy": "0x%064x" % y, "lockBytes": "".join("%02x" % b for b in cfg[86:90]),
      "slot0": {"kind": row["kind"], "locked": row["locked"], "limitedUse": row["limitedUse"], "extSign": row["extSign"]},
      "counter0": c.counter(0)}))`;

async function ask(q) {
  if (has("--yes")) return true;
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const a = (await rl.question(q + " Type yes to go on: ")).trim();
  rl.close();
  return a === "yes";
}

// ----------------------------------------------------------------------------- build
function gitBuild() {
  const sha = spawnSync("git", ["rev-parse", "--short", "HEAD"], { cwd: ROOT, encoding: "utf8" }).stdout.trim();
  const dirty = spawnSync("git", ["status", "--porcelain", "firmware"], { cwd: ROOT, encoding: "utf8" }).stdout.trim();
  return sha + (dirty ? "+dirty" : "");
}

// Every module but boot.py and main.py goes on the board compiled (.mpy), by the mpy-cross of the
// board's own MicroPython. Compiling a module on the Pico leaves its heap in pieces: the console
// image, compiled there, failed to load a 5.8 KB font with 191 KB free (2026-09-26). A .mpy loads
// without the compiler. Same source, same mpy-cross: the same bytes, so builds can be compared.
const MPY_CROSS = ["uvx", "--quiet", "--from", "mpy-cross==1.26.1.post2", "mpy-cross"];
function mpyCross(src, out, name) {
  const r = spawnSync(MPY_CROSS[0], [...MPY_CROSS.slice(1), "-s", name, "-o", out, src], { encoding: "utf8" });
  if (r.status !== 0) die(`mpy-cross failed on ${name}:\n${r.stdout}${r.stderr}`);
}

function build(image, { quiet = false } = {}) {
  const img = M.images[image];
  if (!img) die(`no image "${image}" in firmware/manifest.json (${Object.keys(M.images).join(", ")})`);
  const id = gitBuild();
  const dir = join(ROOT, "build", `${image}-${id}`);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const files = {};
  for (const f of img.files) {
    let to = f === img.main ? "main.py" : f;
    if (to.endsWith(".py") && to !== "main.py" && to !== "boot.py") {
      to = to.replace(/\.py$/, ".mpy");
      mpyCross(join(FIRMWARE, f), join(dir, to), f);
    } else copyFileSync(join(FIRMWARE, f), join(dir, to));
    files[to] = sha256(readFileSync(join(dir, to))).slice(0, 12);
  }
  const py = `# written by tools/fw build; never committed\nIMAGE = ${JSON.stringify(image)}\nBUILD = ${JSON.stringify(id)}\nDATE = ${Math.floor(Date.now() / 1000)}\nFILES = ${JSON.stringify(files)}\n`;
  writeFileSync(join(dir, "build.py"), py);
  return { image, id, dir, names: [...Object.keys(files), "build.py"] };
}

// ----------------------------------------------------------------------------- backup
function backup() {
  pause();
  const uid = boardId();
  const files = boardFiles();
  const dir = join(ROOT, "backups", uid, stamp());
  mkdirSync(dir, { recursive: true });
  chmodSync(join(ROOT, "backups"), 0o700);
  const cps = [];
  for (const f of files) {
    mkdirSync(dirname(join(dir, f.name)), { recursive: true });
    cps.push("cp", ":" + f.name, join(dir, f.name), "+");
  }
  cps.push("exec", "print('COPIED')");
  const r = mp(cps, { timeout: 240000 });
  if (r.code !== 0 || !/COPIED/.test(r.out)) die(`the copy did not finish (the USB link can wedge: tools/usb reset, then again):\n${r.out.slice(-600)}`);
  const bad = [], moved = [];
  for (const f of files) {
    const p = join(dir, f.name);
    const got = existsSync(p) ? readFileSync(p) : null;
    if (got && got.length === f.size && sha256(got) === f.sha) continue;
    if (/^(log(\.1)?\.txt|error\.log|counter-.*\.txt)$/.test(f.name) && got) moved.push(f.name);   // the running console writes these
    else bad.push(f.name + (got ? ` (${got.length} of ${f.size} bytes)` : " (missing)"));
  }
  if (bad.length) die(`the backup in ${dir} does not match the board: ${bad.join(", ")}`);
  writeFileSync(join(dir, "SHA256SUMS"), files.map((f) => `${sha256(readFileSync(join(dir, f.name)))}  ${f.name}`).join("\n") + "\n");
  const flags = tagged(run(FLAGS_PY), "FLAGS");
  writeFileSync(join(dir, "board.json"), JSON.stringify({ board: uid, when: new Date().toISOString(), files, flags }, null, 1) + "\n");
  console.log(`backup: ${files.length} files, ${files.reduce((a, f) => a + f.size, 0)} bytes, every hash checked -> ${dir}`);
  if (moved.length) console.log(`  (${moved.join(", ")} changed while copying: the console writes them; the copies are as read)`);
  console.log(`  it holds the board's secrets.py: keep a copy somewhere outside the repo, and never commit it`);
  unpause();
  return { dir, files, uid };
}

// ----------------------------------------------------------------------------- verify
async function verify({ baseline = false } = {}) {
  const live = tagged(run(LIVE_PY), "LIVE");      // before pausing: the console's own view, as it runs
  pause();
  const files = boardFiles();
  let ok = true;
  const mainSrc = files.some((f) => f.name === "main.py") ? run("print(open('main.py').read()[:120])") : "";
  const image = (/# picoquorum-image: (\w+)/.exec(mainSrc) || [])[1] || null;
  const onBoard = files.some((f) => f.name === "build.py") ? run("import build\nprint('BUILD:' + build.BUILD)").match(/BUILD:(\S+)/)?.[1] : null;
  console.log(`image: ${image || "none (a development board: main.py is " + (/wallet/.test(mainSrc) ? "the legacy wallet" : "something else") + ")"}${onBoard ? ", build " + onBoard : ""}`);
  if (image) {
    const b = build(image);          // this checkout, built the same way a push would
    const want = new Map(b.names.filter((n) => n !== "build.py").map((n) => [n, sha256(readFileSync(join(b.dir, n)))]));
    const differ = [...want].filter(([n, h]) => files.find((f) => f.name === n)?.sha !== h).map(([n]) => n);
    if (differ.length) { ok = false; console.log(`  differs from this checkout: ${differ.join(", ")}`); }
    else console.log(`  every file of the ${image} image matches this checkout (${want.size})`);
    const stale = files.map((f) => f.name).filter((n) => !want.has(n) && n !== "build.py" && !matches(M.preserve, n));
    if (stale.length) { ok = false; console.log(`  not part of the image: ${stale.join(", ")}`); }
  }
  const flags = tagged(run(FLAGS_PY), "FLAGS") || {};
  console.log("secrets.py:");
  for (const [k, v] of Object.entries(flags)) console.log(`  ${k} = ${JSON.stringify(v)}`);
  if (flags.ENABLE_NETWORK_CONSOLE) { ok = false; console.log("  !! ENABLE_NETWORK_CONSOLE is True (the production image ignores it; fix it anyway)"); }
  for (const k of ["ALLOW_LOCK", "ALLOW_GENKEY", "ALLOW_SOFT_KEY"]) if (flags[k]) console.log(`  !! ${k} is True${image === "console" ? " (ignored by the console image)" : ""}`);
  if (live) {
    console.log("console:");
    for (const [k, v] of Object.entries(live)) console.log(`  ${k}: ${JSON.stringify(v)}`);
    if (image === "console" && !(live.pin_ok && live.watchdog)) ok = false;
  } else console.log("console: not running");
  if (baseline) {
    const chip = tagged(run(CHIP_PY), "CHIP");
    console.log("chip:");
    for (const [k, v] of Object.entries(chip)) console.log(`  ${k}: ${JSON.stringify(v)}`);
    console.log(`  owner (computed here): ${await ownerOf(chip.qx, chip.qy)}`);
  }
  unpause();
  console.log(ok ? "verify: all as expected" : "verify: see the lines above");
  return ok;
}

// The owner address a key gets through Safe's passkey signer, computed with viem (tools/mock-tx-service).
async function ownerOf(qx, qy) {
  const { p256Owner } = await import("../mock-tx-service/sigs.mjs");
  const { CFG } = await import("../mock-tx-service/sim.mjs");
  return p256Owner(CFG.signer, qx, qy);
}

// ----------------------------------------------------------------------------- logs
function logs() {
  pause();
  const uid = boardId();
  const have = boardFiles().map((f) => f.name).filter((n) => /^(log(\.1)?\.txt|error\.log)$/.test(n));
  if (!have.length) { unpause(); return console.log("no log files on the board yet"); }
  const dir = join(ROOT, "backups", uid, "logs-" + stamp());
  mkdirSync(dir, { recursive: true });
  const r = mp(have.flatMap((n) => ["cp", ":" + n, join(dir, n), "+"]).concat(["exec", "print('COPIED')"]));
  if (!/COPIED/.test(r.out)) die(r.out.slice(-600));
  unpause();
  console.log(`logs -> ${dir}`);
  for (const n of have) {
    const lines = readFileSync(join(dir, n), "utf8").trimEnd().split("\n");
    console.log(`--- ${n} (last ${Math.min(30, lines.length)} of ${lines.length})`);
    console.log(lines.slice(-30).join("\n"));
  }
}

// ----------------------------------------------------------------------------- maintenance
async function waitForBoard(ms = 45000) {
  const t0 = Date.now();
  await sleep(2500);
  while (Date.now() - t0 < ms) {
    if (serialPorts().includes(port())) {
      const r = mp(["exec", "print('UP')"], { timeout: 20000 });
      if (/UP/.test(r.out)) return;
    }
    await sleep(1500);
  }
  die("the board did not come back on USB: unplug it and plug it back in holding B (maintenance), then run this again");
}

async function enterMaintenance() {
  run("open('maint', 'w').close()\nimport os\nif hasattr(os, 'sync'): os.sync()\nprint('MAINT')");
  mp(["exec", "import machine; machine.reset()"], { timeout: 8000 });
  await waitForBoard();
}

// Out of maintenance: a reset, then hands off. Anything mpremote sends starts with Ctrl-C, and
// while boot.py and main.py are still running that interrupts them: the first push's check did
// exactly that, and the console never started (2026-09-26). So: wait for the port, then 30 s.
async function leaveMaintenance() {
  run("import os\ntry:\n    os.remove('maint')\nexcept OSError:\n    pass\nif hasattr(os, 'sync'): os.sync()\nprint('LEFT')");
  await restartHandsOff();
}

async function restartHandsOff(settle = 30000) {
  mp(["exec", "import machine; machine.reset()"], { timeout: 8000 });
  const t0 = Date.now();
  await sleep(3000);
  while (!serialPorts().includes(port())) {
    if (Date.now() - t0 > 30000) die("the board did not come back on USB");
    await sleep(500);
  }
  console.log(`restarted; leaving it alone for ${settle / 1000} s while boot.py and the console start`);
  await sleep(settle);
}

// Copy [local, remote] pairs with whatever runs paused (in maintenance nothing does; a legacy
// board's wallet ignores maint and is paused instead), then check every hash on the board. No soft
// reset: it would run boot.py's WiFi wait again (up to 12 s, longer than mpremote waits for the
// REPL) and leave a running watchdog unfed.
function copyChecked(pairs) {
  pause();
  for (let i = 0; i < pairs.length; i += 30) {
    const args = pairs.slice(i, i + 30).flatMap(([from, to]) => ["cp", from, ":" + to, "+"]);
    args.push("exec", "import os\nif hasattr(os, 'sync'): os.sync()\nprint('SYNCED')");
    const r = mp(args, { resume: true, timeout: 240000 });
    if (r.code !== 0 || !/SYNCED/.test(r.out)) die(`the copy failed (maint is still on the board, so it will boot into maintenance):\n${r.out.slice(-600)}`);
  }
  const now = new Map(boardFiles().map((f) => [f.name, f.sha]));
  const bad = pairs.filter(([from, to]) => now.get(to) !== sha256(readFileSync(from))).map(([, to]) => to);
  if (bad.length) die(`these did not land intact: ${bad.join(", ")} (the board stays in maintenance; push again)`);
  paused = null;          // leaveMaintenance restarts the board; nothing to resume
}

function removeOnBoard(names) {
  if (!names.length) return;
  run(`import os\nfor n in ${JSON.stringify(names)}:\n    os.remove(n)\nif hasattr(os, 'sync'): os.sync()\nprint('REMOVED')`);
}

// ----------------------------------------------------------------------------- push
async function push(image) {
  const b = build(image);
  if (b.id.endsWith("+dirty") && !has("--dirty-ok")) die(`firmware/ has uncommitted changes: commit them (the build id names a commit) or pass --dirty-ok`);
  const flags = tagged(run(FLAGS_PY), "FLAGS") || {};
  if (image === "ceremony" && flags.QUORUM_EXPECT && !has("--pinned-chip-ok"))
    die(`this board pins a chip (QUORUM_EXPECT ${JSON.stringify(flags.QUORUM_EXPECT)}): the ceremony image is for a fresh chip. Take QUORUM_EXPECT out first, or pass --pinned-chip-ok`);
  if (image === "console" && !flags.QUORUM_EXPECT)
    console.log("note: no QUORUM_EXPECT in the board's secrets.py yet: the console will start on the Not pinned screen (tools/fw pin)");
  const { dir: bdir, files } = backup();
  const board = new Map(files.map((f) => [f.name, f.sha]));
  const copy = b.names.filter((n) => board.get(n) !== sha256(readFileSync(join(b.dir, n))));
  const keep = files.map((f) => f.name).filter((n) => matches(M.preserve, n));
  const flagged = files.map((f) => f.name).filter((n) => matches(M.flag, n));
  const stale = files.map((f) => f.name).filter((n) => !b.names.includes(n) && !matches(M.preserve, n) && !matches(M.flag, n));
  console.log(`\npush ${image} ${b.id} to ${port()}:`);
  console.log(`  copy (${copy.length}): ${copy.join(" ") || "nothing, it is all there"}`);
  console.log(`  delete, not part of the image (${stale.length}): ${stale.join(" ") || "none"}`);
  console.log(`  keep (${keep.length}): ${keep.join(" ")}`);
  if (flagged.length) console.log(`  a software key is on the board: ${flagged.join(" ")} (kept; delete it by hand once you are sure)`);
  console.log(`  backup to restore from: ${bdir}`);
  if (!(await ask("\nThe board goes into maintenance, gets these files, and restarts."))) die("nothing changed");
  await enterMaintenance();
  copyChecked(copy.map((n) => [join(b.dir, n), n]));
  removeOnBoard(stale);
  console.log(`copied ${copy.length}, deleted ${stale.length}, every hash checked. Restarting out of maintenance...`);
  await leaveMaintenance();
  await verify();
}

// ----------------------------------------------------------------------------- restore
// The board's own records (logs, counters, snapshots, slot.txt: manifest "preserve") are never
// rolled back or deleted: a backup's copy goes on only where the board has none. secrets.py only
// with --secrets. --exact deletes the rest of what the backup does not have, never a preserved or
// flagged file. A fresh backup is taken first.
async function restore(dir) {
  if (!dir || !existsSync(join(dir, "SHA256SUMS"))) die("restore DIR: a folder that tools/fw backup made (it has SHA256SUMS)");
  const sums = readFileSync(join(dir, "SHA256SUMS"), "utf8").trim().split("\n").map((l) => l.split(/\s+/)).map(([h, n]) => ({ h, n }));
  const withSecrets = has("--secrets");
  const secret = (n) => /^secrets/.test(n);
  const kept = (n) => matches(M.preserve, n) || matches(M.flag, n);
  const { files: nowFiles } = backup();
  const now = nowFiles.map((f) => f.name);
  const put = sums.filter(({ n }) => n !== "maint" && (secret(n) ? withSecrets : !kept(n) || !now.includes(n)));
  for (const { h, n } of put) if (sha256(readFileSync(join(dir, n))) !== h) die(`${n} in the backup no longer matches its SHA256SUMS line`);
  const drop = has("--exact") ? now.filter((n) => n !== "maint" && !sums.some((s) => s.n === n) && !kept(n) && !secret(n)) : [];
  console.log(`restore ${dir}:\n  copy ${put.length} files${withSecrets ? " (secrets.py too)" : " (not secrets.py)"}\n  delete ${drop.length}: ${drop.join(" ") || "none"}`);
  if (!(await ask("The board goes into maintenance first."))) die("nothing changed");
  await enterMaintenance();
  copyChecked(put.map(({ n }) => [join(dir, n), n]));
  removeOnBoard(drop);
  await leaveMaintenance();
  console.log("restored; the board restarted");
}

// ----------------------------------------------------------------------------- pin
async function pin() {
  pause();
  const chip = tagged(run(CHIP_PY), "CHIP");
  unpause();
  const owner = await ownerOf(chip.qx, chip.qy);
  const livePath = join(ROOT, "tools/mock-tx-service/live.json");
  const known = existsSync(livePath) ? JSON.parse(readFileSync(livePath, "utf8")).key : null;
  const expect = { serial: chip.serial, slot: 0, owner, locked: chip.slot0.locked };
  console.log(`chip ${chip.serial} (revision ${chip.revision}), slot 0: ${chip.slot0.kind}, ${chip.slot0.locked ? "locked" : "NOT locked"}, key ${chip.qx.slice(2, 10)}`);
  console.log(`owner computed here: ${owner}`);
  if (known?.owner) console.log(`owner enrolled (live.json): ${known.owner} ${known.owner.toLowerCase() === owner.toLowerCase() ? "= same" : "!! DIFFERENT"}`);
  if (!chip.slot0.locked) console.log("!! slot 0 is not locked: the console will refuse it unless the pin says locked: False");
  const line = `QUORUM_EXPECT = ${JSON.stringify(expect).replace(/true/g, "True").replace(/false/g, "False")}`;
  console.log(`\nthe board's secrets.py gets:\n  ${line}`);
  if (!(await ask("The old secrets.py is kept as secrets.bak."))) die("nothing changed");
  const code = `import os
new = ${JSON.stringify(line)}
with open('secrets.py') as f:
    old = f.read()
with open('secrets.bak', 'w') as f:
    f.write(old)
keep = [l for l in old.split(chr(10)) if l.split('=')[0].strip() != 'QUORUM_EXPECT' and not l.startswith('# the pinned chip')]
while keep and not keep[-1].strip():
    keep.pop()
with open('secrets.py', 'w') as f:
    f.write(chr(10).join(keep) + chr(10) + '# the pinned chip, written by tools/fw pin' + chr(10) + new + chr(10))
if hasattr(os, 'sync'): os.sync()
print('WROTE', os.stat('secrets.py')[6])`;
  console.log(run(code).match(/WROTE.*/)[0] + " bytes; restart the console (unplug and plug in) to use it");
}

// ----------------------------------------------------------------------------- measure
// One script with the roots and vhttp.py inlined, run from RAM after a soft reset (the app on the
// board stops; boot.py joins WiFi again). Nothing is written to flash. Unplug and replug afterwards
// to get the app back.
function measure(what) {
  if (what !== "tls") die("measure tls");
  const vm = M.images.console.files;
  const ca = vm.filter((f) => /^ca_.*\.bin$/.test(f)).map((f) => `bytes.fromhex("${readFileSync(join(FIRMWARE, f)).toString("hex")}")`);
  const script = `# generated by tools/fw measure tls\n_CA = [${ca.join(", ")}]\n_VHTTP = ${JSON.stringify(readFileSync(join(FIRMWARE, "vhttp.py"), "utf8"))}\n`
    + readFileSync(join(ROOT, "tools/board/measure_tls.py"), "utf8");
  const tmp = join(ROOT, "build", "measure_tls_run.py");
  mkdirSync(dirname(tmp), { recursive: true });
  writeFileSync(tmp, script);
  const wd = run("import sys\nw = sys.modules.get('watch')\nprint('WATCHDOG:' + str(bool(w and w.running())))");
  if (/WATCHDOG:True/.test(wd)) die("the console's watchdog is running, and a soft reset would leave it unfed: put the board in maintenance first (hold B while plugging it in), then measure");
  console.log("the board soft-resets (its app stops) and runs the measurement from RAM; about a minute...");
  const r = mp(["run", tmp], { resume: false, timeout: 300000 });
  console.log(r.out);
  if (r.code !== 0 || !/RESULT ok=10\/10 refused=4\/4/.test(r.out)) process.exit(1);
}

// ----------------------------------------------------------------------------- main
const cmds = {
  build: () => { const b = build(argv[1] || die("build console|ceremony")); console.log(`built ${b.image} ${b.id}: ${b.names.length} files in ${b.dir}`); },
  backup: () => backup(),
  verify: async () => process.exit((await verify({ baseline: has("--baseline") })) ? 0 : 1),
  logs: () => logs(),
  pin: () => pin(),
  push: () => push(argv[1] || die("push console|ceremony")),
  restore: () => restore(argv[1]),
  measure: () => measure(argv[1]),
  restart: async () => { await restartHandsOff(); await verify(); },
};
if (!cmds[cmd]) die("usage: tools/fw build IMAGE | backup | verify [--baseline] | logs | pin | push IMAGE | restore DIR [--exact] [--secrets] | measure tls");
await cmds[cmd]();
