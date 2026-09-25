// The Anvil fork of Base under tools/quorum up and e2e. One block is picked on the first run and
// kept in fork.json (gitignored), so later runs fork the same state and anvil answers from its
// cache (~/.foundry/cache/rpc) instead of asking the public RPC again, which rate-limits.
//   QUORUM_FORK_RPC   the Base RPC to fork (default https://mainnet.base.org)
//   --refork          pick a new block
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const FORK_RPC = process.env.QUORUM_FORK_RPC || "https://mainnet.base.org";
export const FOUNDRY = "v1.8.3";          // the version this was built and tested with: foundryup -i v1.8.3
const FORK_FILE = fileURLToPath(new URL("fork.json", import.meta.url));

export function foundryBin(name) {
  const own = join(homedir(), ".foundry", "bin", name);
  if (spawnSync(name, ["--version"]).status === 0) return name;
  if (existsSync(own)) return own;
  return null;
}

export function anvilVersion() {
  const bin = foundryBin("anvil");
  if (!bin) return null;
  const m = spawnSync(bin, ["--version"], { encoding: "utf8" }).stdout.match(/Version: (\S+)/);
  return m ? m[1] : "?";
}

async function rpc(url, method, params = []) {
  const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" },
                               body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
  const j = await r.json();
  if (j.error) throw new Error(`${method}: ${j.error.message}`);
  return j.result;
}

export async function forkBlock(refork = false) {
  if (!refork && existsSync(FORK_FILE)) {
    const f = JSON.parse(readFileSync(FORK_FILE, "utf8"));
    if (f.rpc === FORK_RPC) return f.block;
  }
  const id = Number(await rpc(FORK_RPC, "eth_chainId"));
  if (id !== 8453) throw new Error(`${FORK_RPC} is chain ${id}, not Base (8453)`);
  const block = Number(await rpc(FORK_RPC, "eth_blockNumber"));
  writeFileSync(FORK_FILE, JSON.stringify({ rpc: FORK_RPC, block, picked: new Date().toISOString() }, null, 2) + "\n");
  return block;
}

// anvil on 127.0.0.1:port, forking Base at block, as chain 31337. Resolves once it answers.
export async function startAnvil(port, block, { quiet = true } = {}) {
  const bin = foundryBin("anvil");
  if (!bin) throw new Error(`no anvil: install Foundry with  foundryup -i ${FOUNDRY}  (see tools/mock-tx-service/README.md)`);
  const url = `http://127.0.0.1:${port}`;
  try {
    await rpc(url, "eth_chainId");
    throw new Error(`something already answers on ${url}; stop it (an old anvil?) or set QUORUM_ANVIL_PORT`);
  } catch (e) {
    if (e.message.startsWith("something")) throw e;
  }
  const child = spawn(bin, ["--fork-url", FORK_RPC, "--fork-block-number", String(block), "--chain-id", "31337",
    "--port", String(port), "--retries", "10", "--compute-units-per-second", "20", ...(quiet ? ["--silent"] : [])],
  { stdio: ["ignore", "ignore", "pipe"] });
  let err = "";
  child.stderr.on("data", (d) => (err += d));
  for (let i = 0; ; i++) {
    if (child.exitCode !== null) throw new Error(`anvil exited: ${err.trim().split("\n").pop()}`);
    try {
      await rpc(url, "eth_chainId");
      return { child, url };
    } catch {}
    if (i > 300) throw new Error("anvil did not answer in 30 s");
    await new Promise((r) => setTimeout(r, 100));
  }
}
