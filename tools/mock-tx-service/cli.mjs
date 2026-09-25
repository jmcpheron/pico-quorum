// tools/quorum: run and drive the simulated Safe.
//   serve [--port 8787]            the mock transaction service + dashboard, in the foreground
//   demo                           fresh Safe with the standard queue (scenarios.mjs DEMO)
//   reset [scenario ...]           fresh Safe (registered consoles stay owners), then those scenarios
//   propose SCENARIO [--by bob]    queue one story; `scenarios` lists them
//   confirm NONCE|HASH --as alice  a co-signer confirms
//   status                         the Safe, its owners and the queue
//   log [N]                        the last N events
//   ip                             this Mac's LAN address, for QUORUM_URL in the Pico's secrets.py
//   shots                          regenerate docs/quorum-ui/shots with the emulator (shots.mjs)
import { execSync } from "node:child_process";

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
  console.log(`${st.name} ${st.address}  chain ${st.chainId}  nonce ${st.nonce}  ${st.threshold} of ${st.owners.length}`);
  for (const o of st.owners) console.log(`  owner ${o.name.padEnd(9)} ${o.address}  ${o.kind === "p256" ? "P-256, " + o.device : "ECDSA"}`);
  const pending = st.txs.filter((t) => !t.isExecuted && Number(t.nonce) >= st.nonce);
  console.log(pending.length ? "queue:" : "queue: empty");
  for (const t of pending) {
    const who = t.confirmations.map((c) => name(c.owner)).join(", ") || "nobody";
    const flags = [t.trueHash !== t.safeTxHash && "LIES", t.safe !== st.address && "OTHER SAFE", t.declined.length && "rejected by " + t.declined.join(", ")].filter(Boolean);
    console.log(`  #${t.nonce} ${t.scenario.padEnd(16)} ${t.safeTxHash.slice(0, 10)}..${t.safeTxHash.slice(-8)}  ${t.confirmations.length}/${st.threshold} (${who})${flags.length ? "  [" + flags.join("; ") + "]" : ""}`);
  }
  const done = st.txs.filter((t) => t.isExecuted);
  if (done.length) console.log(`executed: ${done.map((t) => "#" + t.nonce + " " + t.scenario).join(", ")}`);
}

if (cmd === "serve") {
  await import("./server.mjs");
} else if (cmd === "demo") {
  await call("/sim/reset", { demo: true });
  await status();
} else if (cmd === "reset") {
  await call("/sim/reset", { scenarios: words });
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
  console.error("usage: tools/quorum serve | demo | reset [scenario..] | propose SCENARIO [--by bob] | confirm NONCE --as alice | status | log [N] | scenarios | ip | shots");
  process.exit(2);
}
