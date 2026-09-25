// Snapshots a few executed transactions from Safe's transaction service into real-safe-txs.json,
// with the safeTxHash the service published. gen.mjs turns them into vectors and checks that viem
// agrees with the service before writing anything. Rerun only to refresh the snapshot.
//
//   node fetch-real.mjs
import { writeFileSync } from "node:fs";

// The Safe{DAO} treasury on Ethereum mainnet: public, active, Safe >= 1.3.0.
const SOURCES = [{ chainId: 1, service: "eth", safe: "0x8CF60B289f8d31F737049B590b5E4285Ff0Bd1D1", limit: 2 }];

const out = [];
for (const { chainId, service, safe, limit } of SOURCES) {
  const url = `https://api.safe.global/tx-service/${service}/api/v2/safes/${safe}/multisig-transactions/?executed=true&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  for (const t of (await res.json()).results) {
    out.push({
      chainId, safe: t.safe, source: url, transactionHash: t.transactionHash,
      tx: { to: t.to, value: t.value, data: t.data ?? "0x", operation: t.operation, safeTxGas: String(t.safeTxGas),
            baseGas: String(t.baseGas), gasPrice: String(t.gasPrice), gasToken: t.gasToken,
            refundReceiver: t.refundReceiver, nonce: String(t.nonce) },
      safeTxHash: t.safeTxHash,
    });
  }
}
writeFileSync(new URL("real-safe-txs.json", import.meta.url), JSON.stringify(out, null, 2) + "\n");
console.log(`saved ${out.length} real transactions`);
