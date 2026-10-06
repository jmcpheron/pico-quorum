// tools/quorum: run and drive the Family Safe, simulated or on an Anvil fork of Base.
//   serve [--port 8787]            the mock transaction service + dashboard, in the foreground
//   up [--refork] [--manual-exec]  a real Safe: anvil forking Base (127.0.0.1:8545) + the service on
//                                  it, in the foreground; Ctrl-C stops both (chain.mjs, fork.mjs).
//                                  --manual-exec: nothing executes until `live exec --chain local`
//   e2e                            the console on the emulator approves on the fork (e2e.mjs)
//   doctor                         is everything here that up, e2e and the tests need
//   live key|enroll|status|rehearse|exec   the console's key on Base Sepolia, Base or Ethereum (live.mjs, docs/LADDER.md)
//   verify BUNDLE [--chain C,..] [--safe C:0x..]   a Trust M signer's ceremony record, checked by anyone (attest.mjs)
//   demo                           fresh Safe with the standard queue (scenarios.mjs DEMO)
//   reset [scenario ...] [--version 1.3.0]   fresh Safe (registered consoles stay owners), then those
//   propose SCENARIO [--by bob]    queue one story; `scenarios` lists them
//   confirm NONCE|HASH --as alice  a co-signer confirms
//   status                         the Safe, its owners and the queue
//   log [N]                        the last N events
//   ip                             this Mac's LAN address, for QUORUM_URL in the Pico's secrets.py
//   shots                          regenerate docs/quorum-ui/shots with the emulator (shots.mjs)
import { execSync, spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The repo's .env (gitignored; .env.example is the template): the Safe API key and optional RPCs.
// A variable already set in the shell wins.
const ENV_FILE = fileURLToPath(new URL("../../.env", import.meta.url));
if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);

const [cmd = "status", ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const words = rest.filter((w, i) => !w.startsWith("--") && !(i > 0 && rest[i - 1].startsWith("--")));
const BASE = `http://localhost:${process.env.QUORUM_PORT || 8787}`;

async function call(path, body) {
  let r;
  try {
    r = await fetch(BASE + path, body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {});
  } catch {
    console.error(`nothing answers at ${BASE}: start it with tools/quorum serve`);
    process.exit(1);
  }
  const out = await r.json();
  if (!r.ok) {
    console.error(out.detail || out.error || JSON.stringify(out));
    process.exit(1);
  }
  return out;
}

function lanIp() {
  for (const ifc of ["en0", "en1"]) {
    try {
      const ip = execSync(`ipconfig getifaddr ${ifc}`, { encoding: "utf8" }).trim();
      if (ip) return ip;
    } catch {}
  }
  return "";
}

async function status() {
  const st = await call("/sim/state");
  const name = (a) => (st.owners.find((o) => o.address.toLowerCase() === a.toLowerCase()) || {}).name || a.slice(0, 10);
  console.log(`${st.name} ${st.address}  v${st.version}  chain ${st.chainId}  nonce ${st.nonce}  ${st.threshold} of ${st.owners.length}`);
  if (st.chain) console.log(`  a real Safe on the Anvil fork of Base (${st.chain.rpc}), block ${st.chain.block}: ${st.chain.eth} ETH, ${st.chain.usdc} USDC`);
  for (const o of st.owners) console.log(`  owner ${o.name.padEnd(9)} ${o.address}  ${o.kind === "p256" ? "P-256, " + o.device : "ECDSA"}`);
  const pending = st.txs.filter((t) => !t.isExecuted && Number(t.nonce) >= st.nonce);
  console.log(pending.length ? "queue:" : "queue: empty");
  for (const t of pending) {
    const who = t.confirmations.map((c) => name(c.owner)).join(", ") || "nobody";
    const flags = [t.trueHash !== t.safeTxHash && "LIES", t.safe !== st.address && "OTHER SAFE", t.declined.length && "rejected by " + t.declined.join(", "),
                   t.revert && "would revert: " + t.revert].filter(Boolean);
    console.log(`  #${t.nonce} ${t.scenario.padEnd(16)} ${t.safeTxHash.slice(0, 10)}..${t.safeTxHash.slice(-8)}  ${t.confirmations.length}/${st.threshold} (${who})${flags.length ? "  [" + flags.join("; ") + "]" : ""}`);
  }
  const done = st.txs.filter((t) => t.isExecuted);
  if (done.length && st.chain) for (const t of done) console.log(`executed #${t.nonce} ${t.scenario.padEnd(16)} tx ${t.transactionHash}${t.isSuccessful === false ? "  (the call failed)" : ""}`);
  else if (done.length) console.log(`executed: ${done.map((t) => "#" + t.nonce + " " + t.scenario).join(", ")}`);
}

async function up() {
  const { FORK_RPC, forkBlock, startAnvil } = await import("./fork.mjs");
  const port = Number(process.env.QUORUM_ANVIL_PORT || 8545);
  const block = await forkBlock(rest.includes("--refork"));
  console.log(`anvil: forking Base at block ${block} (${FORK_RPC}) as chain 31337 on 127.0.0.1:${port}`);
  const anvil = await startAnvil(port, block);
  const svc = spawn(process.execPath, [new URL("server.mjs", import.meta.url).pathname, "--chain", anvil.url,
                                       "--port", String(process.env.QUORUM_PORT || 8787),
                                       ...(rest.includes("--manual-exec") ? ["--manual-exec"] : [])], { stdio: "inherit" });
  const ip = lanIp();
  if (ip) console.log(`for the Pico's secrets.py:  QUORUM_URL = "http://${ip}:${process.env.QUORUM_PORT || 8787}"`);
  const stop = () => {
    svc.kill();
    anvil.child.kill();
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  svc.on("exit", (code) => {
    anvil.child.kill();
    if (code) console.error("the service stopped. If anvil could not fetch the pinned block, try: tools/quorum up --refork");
    process.exit(code ?? 0);
  });
}

async function doctor() {
  const { FOUNDRY, FORK_RPC, anvilVersion, foundryBin } = await import("./fork.mjs");
  let bad = 0;
  const line = (ok, what, fix = "") => {
    console.log(`${ok ? "ok  " : "NO  "}  ${what}${ok || !fix ? "" : "\n        " + fix}`);
    if (!ok) bad++;
  };
  const major = Number(process.versions.node.split(".")[0]);
  line(major >= 20, `node ${process.versions.node}`, "node 20 or newer");
  const py = spawnSync("python3", ["--version"], { encoding: "utf8" });
  line(py.status === 0, `python3 ${(py.stdout || py.stderr || "").trim().replace("Python ", "")} (test-vectors/run.py, test.mjs)`, "install python3");
  const v = anvilVersion();
  line(!!v, `anvil ${v || "missing"}${v && v !== FOUNDRY.slice(1) ? ` (tested with ${FOUNDRY})` : ""}${foundryBin("anvil")?.includes("/") ? " from ~/.foundry/bin" : ""}`,
    `curl -L https://foundry.paradigm.xyz | sh, then: ~/.foundry/bin/foundryup -i ${FOUNDRY}`);
  line(!!foundryBin("cast"), "cast (tools/quorum live)", `foundryup -i ${FOUNDRY}`);
  line(existsSync(new URL("../../emu/node_modules", import.meta.url)), "emu/node_modules (e2e, shots, run-micropython.mjs)", "(cd emu && npm ci)");
  try {
    const r = await fetch(FORK_RPC, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_chainId", params: [] }), signal: AbortSignal.timeout(8000) });
    const id = Number((await r.json()).result);
    line(id === 8453, `fork RPC ${FORK_RPC}: chain ${id}`, "QUORUM_FORK_RPC must be a Base mainnet RPC");
  } catch (e) {
    line(false, `fork RPC ${FORK_RPC}: ${e.message}`, "set QUORUM_FORK_RPC to a Base RPC that answers");
  }
  const ip = lanIp();
  line(!!ip, `LAN address ${ip || "none"} (the Pico reaches the service here)`);
  const ignored = spawnSync("git", ["check-ignore", "-q", ENV_FILE]).status === 0;
  line(!existsSync(ENV_FILE) || ignored, `.env ${existsSync(ENV_FILE) ? (ignored ? "present, gitignored" : "present and NOT gitignored") : "absent"}`,
    "add .env to .gitignore before putting anything in it");
  line(!!process.env.SAFE_API_KEY, `Safe API key ${process.env.SAFE_API_KEY ? "set" : "not set"} (live on Base Sepolia, Base, Ethereum)`,
    "put SAFE_API_KEY=... in .env (from developer.safe.global)");
  process.exit(bad ? 1 : 0);
}

if (cmd === "serve") {
  await import("./server.mjs");
} else if (cmd === "up") {
  await up();
} else if (cmd === "e2e") {
  await import("./e2e.mjs");
} else if (cmd === "release-e2e") {
  await import("./release-e2e.mjs");
} else if (cmd === "doctor") {
  await doctor();
} else if (cmd === "live") {
  await import("./live.mjs");
} else if (cmd === "verify") {
  await import("./attest.mjs");
} else if (cmd === "demo") {
  await call("/sim/reset", { demo: true });
  await status();
} else if (cmd === "reset") {
  await call("/sim/reset", { scenarios: words, version: opt("--version") });
  await status();
} else if (cmd === "propose") {
  const out = await call("/sim/propose", { scenario: words[0], by: opt("--by") });
  console.log(out.proposed.map((p) => `#${p.nonce} ${p.safeTxHash}`).join("\n"));
} else if (cmd === "confirm") {
  const out = await call("/sim/confirm", { ref: words[0], as: opt("--as", "bob") });
  console.log(`${out.name} confirmed`);
} else if (cmd === "status") {
  await status();
} else if (cmd === "log") {
  const st = await call("/sim/state");
  console.log(st.log.slice(-Number(words[0] || 30)).join("\n"));
} else if (cmd === "scenarios") {
  const st = await call("/sim/state");
  for (const [k, v] of Object.entries(st.scenarios)) console.log(`${k.padEnd(18)} ${v}`);
} else if (cmd === "ip") {
  const ip = lanIp();
  console.log(ip ? `QUORUM_URL = "http://${ip}:${process.env.QUORUM_PORT || 8787}"` : "no LAN address on en0/en1");
} else if (cmd === "shots") {
  await import("./shots.mjs");
} else {
  console.error("usage: tools/quorum serve | up [--refork] [--manual-exec] | e2e | doctor | live key|enroll|status|rehearse|exec | verify BUNDLE | demo | reset [scenario..] | propose SCENARIO [--by bob] | confirm NONCE --as alice | status | log [N] | scenarios | ip | shots");
  process.exit(2);
}
