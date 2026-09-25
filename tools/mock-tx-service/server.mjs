// A stand-in for Safe's transaction service, for the console to poll over WiFi. It answers the
// few endpoints the console uses, at the same paths and in the same shapes as
// api.safe.global/tx-service, so pointing the console at the real service later is a URL change.
// /sim/* is the simulation's own control surface (tools/quorum, the dashboard at /).
//
//   node tools/mock-tx-service/server.mjs [--port 8787]      (or: tools/quorum serve)
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { apiList, apiSafe, apiTx, confirm, decline, find, fresh, load, registerDevice, save, say, signAs } from "./sim.mjs";
import { DEMO, SCENARIOS, run } from "./scenarios.mjs";

const argv = process.argv.slice(2);
const PORT = Number((argv.includes("--port") && argv[argv.indexOf("--port") + 1]) || process.env.QUORUM_PORT || 8787);
let st = load();

function send(res, code, body) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  res.writeHead(code, {
    "Content-Type": typeof body === "string" ? "text/html; charset=utf-8" : "application/json",
    "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "content-type",
  });
  res.end(text);
}

async function readJson(req) {
  let raw = "";
  for await (const c of req) raw += c;
  return raw ? JSON.parse(raw) : {};
}

const routes = [
  // --- Safe's transaction service -----------------------------------------------------------------
  ["GET", /^\/api\/v1\/safes\/(0x[0-9a-fA-F]{40})\/?$/, (m) =>
    m[1].toLowerCase() === st.address.toLowerCase() ? [200, apiSafe(st)] : [404, { detail: "Not found." }]],
  ["GET", /^\/api\/v2\/safes\/(0x[0-9a-fA-F]{40})\/multisig-transactions\/?$/, (m, q) =>
    m[1].toLowerCase() === st.address.toLowerCase() ? [200, apiList(st, q)] : [200, { count: 0, next: null, previous: null, results: [] }]],
  ["GET", /^\/api\/v1\/multisig-transactions\/(0x[0-9a-fA-F]{64})\/?$/, (m) => {
    const t = find(st, m[1]);
    return t ? [200, apiTx(st, t)] : [404, { detail: "Not found." }];
  }],
  ["POST", /^\/api\/v1\/multisig-transactions\/(0x[0-9a-fA-F]{64})\/confirmations\/?$/, async (m, q, body) => {
    const t = find(st, m[1]);
    if (!t) return [404, { detail: "Not found." }];
    const r = await confirm(st, t, body.signature || "0x");
    if (!r.ok) say(st, `refused a confirmation for #${t.nonce}: ${r.error}`);
    return r.ok ? [201, { signature: body.signature }] : [400, { detail: r.error }];
  }],
  // --- the simulation -------------------------------------------------------------------------------
  ["GET", /^\/$/, () => [200, readFileSync(new URL("dashboard.html", import.meta.url), "utf8")]],
  ["GET", /^\/sim\/state$/, () => [200, { ...st, scenarios: Object.fromEntries(Object.entries(SCENARIOS).map(([k, v]) => [k, v.about])) }]],
  ["POST", /^\/sim\/device$/, (m, q, b) => {
    const o = registerDevice(st, b);
    return [200, { owner: o.address, owners: st.owners.map((o) => o.address), threshold: st.threshold }];
  }],
  ["POST", /^\/sim\/propose$/, async (m, q, b) => {
    const txs = await run(st, b.scenario, b.by);
    return [200, { proposed: txs.map((t) => ({ nonce: t.nonce, safeTxHash: t.safeTxHash })) }];
  }],
  ["POST", /^\/sim\/confirm$/, async (m, q, b) => {
    const t = find(st, b.ref);
    if (!t) return [404, { detail: `no pending transaction ${b.ref}` }];
    const r = await signAs(st, b.as, t);
    return [r.ok ? 200 : 400, r];
  }],
  ["POST", /^\/sim\/declined$/, (m, q, b) => {
    const t = find(st, b.safeTxHash || "");
    if (t) decline(st, t, b.by || "a device");
    return [200, { ok: !!t }];
  }],
  ["POST", /^\/sim\/reset$/, async (m, q, b) => {
    const devices = st.owners.filter((o) => o.kind === "p256");
    st = fresh();
    if (b.keepDevices !== false) for (const d of devices) registerDevice(st, { name: d.device, qx: d.qx, qy: d.qy });
    say(st, "reset: a fresh Safe, nonce 0, 2 of " + st.owners.length);
    for (const name of b.demo ? DEMO : b.scenarios || []) await run(st, name);
    return [200, { ok: true }];
  }],
];

createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  if (req.method === "OPTIONS") return send(res, 204, "");
  for (const [method, re, fn] of routes) {
    const m = url.pathname.match(re);
    if (!m || method !== req.method) continue;
    try {
      const [code, body] = await fn(m, url.searchParams, req.method === "POST" ? await readJson(req) : {});
      save(st);
      if (req.method !== "GET" || code >= 400) console.log(`  ${req.method} ${url.pathname} -> ${code}`);  // polls stay quiet
      return send(res, code, body);
    } catch (e) {
      console.log(`  ${req.method} ${url.pathname} -> 500 ${e.message}`);
      return send(res, 500, { detail: e.message });
    }
  }
  send(res, 404, { detail: "Not found." });
}).listen(PORT, "0.0.0.0", () => {
  say(st, `simulated Safe ${st.name} ${st.address} on chain ${st.chainId}: ${st.threshold} of ${st.owners.length}, nonce ${st.nonce}`);
  say(st, `listening on http://0.0.0.0:${PORT} (dashboard: http://localhost:${PORT}/)`);
});
