// tools/quorum shots: every screen in docs/quorum-ui/README.md, captured from the emulator running
// the real firmware against the simulated Safe. Same input, same pixels: the Safe starts fresh
// for each story, and the console's chip is emu-chip.json (a virtual ATECC608 with a throwaway key
// in slot 0; copied per story, so the file never changes), or emu-trustm.json for the Trust M story. Runs its own mock on port 8799 with
// its own state, so a session on 8787 is left alone.
import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { DEMO } from "./scenarios.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SHOTS = join(ROOT, "docs", "quorum-ui", "shots");
const PORT = 8799;
const BASE = `http://localhost:${PORT}`;
// "two": a console that watches two Safes (QUORUM_SAFES), the Family Safe here and a simulated
// Safe on Base Sepolia from a second mock on PORT2, each named with its own "url".
const PORT2 = 8797;
const BASE2 = `http://localhost:${PORT2}`;
const SAFE2 = "0x5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a";
const tmp = mkdtempSync(join(tmpdir(), "quorum-shots-"));
// tools/quorum shots [story ...], or tools/quorum shots --fonts inter,plex: FONT_STORIES in each
// candidate font set (tools/fonts/gen.py --try) into docs/quorum-ui/v2/fonts/SET/
let only = process.argv.slice(3);
let fontsets = [null];
if (only[0] === "--fonts") {
  fontsets = only[1].split(",");
  only = only.slice(2);
}

// A step is a string: "key A", "keys down,down,A", "hold A", "release A", "wait MS", "shot NAME",
// "exec CODE", or "frozen-hold MS" (the hold overlay drawn at MS in, with the timer stopped so the
// bar is the same every run; the page goes back to normal after the shot).
const STORIES = [
  ["home", DEMO, ["shot 01-home"]],
  ["approve", DEMO, [
    "key A", "shot 02-approve-summary", "key down", "shot 03-approve-send", "key A", "shot 04-approve-every-page-first",
    "frozen-hold 1000", "shot 05-approve-hold", "hold A", "wait 2300", "release A", "wait 800", "shot 06-approve-signed",
    "key A", "wait 1500", "shot 07-approve-home-after"]],
  ["batch", DEMO, ["keys down,A", "shot 08-batch-summary", "key down", "shot 09-batch-call-1", "key down", "shot 10-batch-call-2",
    "key down", "shot 11-batch-verify"]],
  ["owner", DEMO, ["keys down,down,A", "shot 12-owner-summary", "key down", "shot 13-owner-red-page", "key down",
    "hold A", "wait 2300", "release A", "wait 100", "shot 14-owner-let-go-early", "frozen-hold 2000", "shot 15-owner-hold-red"]],
  ["lie", DEMO, ["keys down,down,down,A", "shot 16-lie-refused", "key down", "shot 17-lie-claimed", "key A", "shot 18-lie-cant-sign"]],
  ["unknown", DEMO, ["keys down,down,down,down,A", "shot 19-unknown-summary", "key down", "shot 20-unknown-red-page",
    "key down", "shot 20b-unknown-calldata"]],
  ["reject", DEMO, ["key A", "key Y", "wait 200", "shot 21-reject-home"]],
  ["reds", ["refund", "delegate-unknown", "threshold", "wrong-safe"], [
    "shot 22-reds-home", "key A", "key down", "key down", "shot 23-refund-red-page", "key B",
    "keys down,A", "shot 24-delegatecall-refused", "key B",
    "keys down,A", "key down", "shot 25-threshold-red-page", "key B",
    "keys down,A", "shot 26-wrong-safe-refused"]],
  ["conflict", ["conflict"], ["shot 27-conflict-home", "key A", "shot 28-conflict-summary", "keys B,down,A,down", "shot 29-conflict-rejection-page"]],
  ["owners", DEMO, ["key B", "shot 30-owners"]],
  ["device", DEMO, ["key X", "wait 400", "shot 31-device"]],
  ["offline", null, ["shot 32-no-service"]],
  ["identity", ["send-usdc", "uniswap-approve", "uniswap-swap", "batch", "unknown-call"], [
    "shot 37-identity-home", "key A", "shot 38-identity-usdc-summary",
    "keys B,down,A", "key down", "shot 39-identity-uniswap-spender",
    "keys B,down,A", "shot 40-identity-uniswap-swap-summary", "key down", "shot 41-identity-uniswap-swap-page",
    "keys B,down,A", "shot 42-identity-safe-multisend"]],
  ["v150", ["send-eth"], ["shot 43-version-1.5.0"], { version: "1.5.0" }],
  ["v130", ["send-eth"], ["key B", "shot 44-version-1.3.0-L2-owners"], { version: "1.3.0+L2" }],
  ["vold", ["send-eth"], ["shot 45-version-too-old", "key A", "shot 46-version-too-old-summary"], { version: "1.1.1" }],
  ["two", ["send-eth", "send-usdc"], ["wait 3000", "shot 47-two-safes-home", "keys down,down", "shot 48-two-safes-other-chain",
    "key A", "shot 49-two-safes-review", "keys B,B", "shot 50-two-safes-owners"], { two: ["send-eth"] }],
  // The console on an OPTIGA Trust M (emu-trustm.json: a virtual Trust M sealed as quorum-tm1, no ATECC on the bus).
  // Signing is one blocking step on the device, so its two screens are drawn here with the console's
  // own functions, the timer stopped, before the real hold signs.
  ["trustm", DEMO, ["shot 51-trustm-home", "key A", "key down",
    `exec import quorum_ui; quorum.timer.deinit(); quorum.work_info[:] = quorum.chip_info(); quorum.d.frames(quorum_ui.draw_working, quorum, "Signing", "The chip signs the hash computed here")`,
    "shot 52-trustm-signing",
    `exec import quorum_ui; quorum.work_info[:] = quorum.signed_info(148, 0, 1); quorum.d.frames(quorum_ui.draw_working, quorum, "Sending", "To the transaction service")`,
    "shot 53-trustm-sending",
    "exec quorum.work_info[:] = []; quorum.dirty = True; quorum.start_timer()", "wait 300",
    "key A", "hold A", "wait 2300", "release A", "wait 800", "shot 54-trustm-signed",
    "key A", "wait 1500", "key X", "wait 400", "shot 55-trustm-device"], { trustm: true }],
  ["light", DEMO, ["exec import quorum_ui; quorum_ui.use('light'); quorum.dirty = True", "shot 33-light-home", "key A", "shot 34-light-summary",
    "keys B,down,down,A,down", "shot 35-light-red-page", "key down", "shot 36-light-verify"]],
];

// A few screens that show every size of type, for comparing font sets (docs/quorum-ui/v2/FONTS.md).
const FONT_STORIES = [
  ["home", DEMO, ["shot 01-home"]],
  ["approve", DEMO, ["key A", "shot 02-approve-summary", "key down", "shot 03-approve-send"]],
  ["batch", DEMO, ["keys down,A", "key down", "key down", "key down", "shot 11-batch-verify"]],
  ["owner", DEMO, ["keys down,down,A", "key down", "shot 13-owner-red-page"]],
  ["lie", DEMO, ["keys down,down,down,A", "shot 16-lie-refused"]],
];

function args(steps, OUT) {
  const out = [];
  for (const s of steps) {
    const [k, ...rest] = s.split(" ");
    const v = rest.join(" ");
    if (k === "key") out.push("--key", v, "--wait", "250");
    else if (k === "keys") for (const x of v.split(",")) out.push("--key", x, "--wait", "250");
    else if (k === "hold" || k === "release" || k === "wait" || k === "exec") out.push("--" + k, v);
    else if (k === "shot") out.push("--wait", "150", "--shot", join(OUT, v + ".png"));
    else if (k === "frozen-hold") {
      out.push("--exec", `import time, quorum_ui; quorum.timer.deinit(); quorum.msg = ""; quorum.state = "hold"; quorum.hold_t0 = time.ticks_add(time.ticks_ms(), -${v}); quorum_ui.draw(quorum)`);
      out.push("--shot", "@next");
      out.push("--exec", `quorum.state = "review"; quorum.dirty = True; quorum.start_timer()`);
    } else throw new Error("bad step " + s);
  }
  // "@next" takes the name of the shot that follows the frozen hold
  for (let i = 0; i < out.length; i++) {
    if (out[i] !== "@next") continue;
    const j = out.indexOf("--shot", i + 1);
    out[i] = out[j + 1];
    out.splice(j - 2, 4);      // drop the following "--wait 150 --shot NAME": the frozen one replaces it
  }
  return out;
}

async function post(path, body, base = BASE) {
  const r = await fetch(base + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
}

const server = spawn(process.execPath, [join(ROOT, "tools/mock-tx-service/server.mjs"), "--port", String(PORT)],
  { env: { ...process.env, QUORUM_STATE: join(tmp, "state.json") }, stdio: "ignore" });
const server2 = spawn(process.execPath, [join(ROOT, "tools/mock-tx-service/server.mjs"), "--port", String(PORT2)],
  { env: { ...process.env, QUORUM_STATE: join(tmp, "state2.json"), QUORUM_SIM_SAFE: `84532:${SAFE2}:Test Safe` }, stdio: "ignore" });
for (const b of [BASE, BASE2]) {
  for (let i = 0; ; i++) {
    try { await fetch(b + "/sim/state"); break; } catch { if (i > 40) throw new Error("mock did not start"); }
    await new Promise((r) => setTimeout(r, 100));
  }
}
const twoSecrets = join(tmp, "two.py");
writeFileSync(twoSecrets, `QUORUM_SAFES = [
    {"chainId": 31337, "address": "0xf77e6235ea5ce79d6d823b332276cac99ea77666", "name": "Family Safe", "url": "${BASE}"},
    {"chainId": 84532, "address": "${SAFE2}", "name": "Test Safe", "url": "${BASE2}"},
]
`);

let failed = 0;
for (const fontset of fontsets) {
  const OUT = fontset ? join(ROOT, "docs", "quorum-ui", "v2", "fonts", fontset) : SHOTS;
  mkdirSync(OUT, { recursive: true });
  for (let [name, queue, steps, opts = {}] of fontset ? FONT_STORIES : STORIES) {
    if (only.length && !only.includes(name)) continue;
    if (fontset) steps = [`exec import fonts; fonts.use('${fontset}'); quorum.dirty = True`, "wait 300", ...steps];
    for (const f of readdirSync(OUT)) if (steps.some((s) => s === `shot ${f.replace(/\.png$/, "")}`)) rmSync(join(OUT, f));
    if (queue) await post("/sim/reset", { scenarios: queue, keepDevices: false, version: opts.version });
    if (opts.two) await post("/sim/reset", { scenarios: opts.two, keepDevices: false }, BASE2);
    const chip = join(tmp, "chip.json");
    copyFileSync(new URL(opts.trustm ? "emu-trustm.json" : "emu-chip.json", import.meta.url), chip);
    const app = queue ? BASE : "http://localhost:1";      // "offline": nothing answers
    const r = spawnSync(process.execPath, [join(ROOT, "emu/headless.mjs"), "quorum", "--app", app, "--chip", chip, "--quiet",
      ...(opts.two ? ["--secrets", twoSecrets] : []),
      "--wait", "3000", ...args(steps, OUT)], { cwd: join(ROOT, "emu"), encoding: "utf8" });
    const shots = (r.stdout.match(/\[shot\]/g) || []).length;
    const bad = r.status !== 0 || /Traceback/.test(r.stdout + r.stderr);
    console.log(`${bad ? "FAIL" : "ok  "}  ${(fontset ? fontset + " " : "") + name.padEnd(9)} ${shots} shots`);
    if (bad) {
      failed++;
      console.log((r.stdout + r.stderr).split("\n").filter((l) => !l.startsWith("[shot]")).slice(-15).join("\n"));
    }
  }
  console.log(`shots in ${OUT}`);
}
server.kill();
server2.kill();
rmSync(tmp, { recursive: true, force: true });
if (failed) console.log(`${failed} stories failed`);
process.exit(failed ? 1 : 0);
