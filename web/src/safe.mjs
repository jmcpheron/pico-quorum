// The Safe side of the page, with no DOM in it so web/test.mjs can drive it: the chains, the
// transaction service, the Safe read onchain, every confirmation checked, and execTransaction built
// with the confirmations laid out right (sigs.packSignatures, the same code tools/quorum live exec
// uses). Safe{Wallet} can't do that last part when a contract signature is one of two or more (GS021,
// docs/upstream/safe-wallet-gs021/).
//
// Trust: owners, threshold and nonce come from the Safe itself over RPC, not from the service. The
// service is only the queue: every transaction's hash is recomputed here and by the Safe, and every
// confirmation is checked (ECDSA recovered, contract signatures asked of the owner contract).
import { checkApproval } from "../../tools/mock-tx-service/release.mjs";
import {
  createPublicClient, decodeEventLog, encodeFunctionData, formatEther, getAddress, hashMessage, hashTypedData, http,
  parseAbi, recoverAddress, size, slice, toHex,
} from "viem";
import { base, baseSepolia, mainnet } from "viem/chains";
import { p256Owner, packSignatures, parse } from "../../tools/mock-tx-service/sigs.mjs";
import { CFG } from "./config.gen.mjs";

export { CFG };
export const MAGIC = "0x1626ba7e";
export const ZERO = "0x0000000000000000000000000000000000000000";

// The chains the console knows (firmware/quorum_cfg.py "services"), with public RPCs that answer
// browsers. Each can be overridden in Settings.
export const CHAINS = {
  basesep: { id: 84532, chain: baseSepolia, name: "Base Sepolia", rpc: "https://sepolia.base.org",
             explorer: "https://sepolia.basescan.org", test: true },
  base: { id: 8453, chain: base, name: "Base", rpc: "https://mainnet.base.org", explorer: "https://basescan.org" },
  eth: { id: 1, chain: mainnet, name: "Ethereum", rpc: "https://ethereum-rpc.publicnode.com", explorer: "https://etherscan.io" },
};
for (const c of Object.values(CHAINS)) c.service = CFG.services[String(c.id)];
export const chainById = (id) => Object.entries(CHAINS).find(([, c]) => c.id === Number(id))?.[0];

export const SAFE_ABI = parseAbi([
  "function getOwners() view returns (address[])",
  "function getThreshold() view returns (uint256)",
  "function nonce() view returns (uint256)",
  "function VERSION() view returns (string)",
  "function getTransactionHash(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, uint256 _nonce) view returns (bytes32)",
  "function execTransaction(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, bytes signatures) payable returns (bool)",
  "event ExecutionSuccess(bytes32 indexed txHash, uint256 payment)",
  "event ExecutionFailure(bytes32 indexed txHash, uint256 payment)",
]);
export const ERC1271_ABI = parseAbi(["function isValidSignature(bytes32 hash, bytes signature) view returns (bytes4)"]);
export const SIGNER_ABI = parseAbi([
  "function getConfiguration() view returns (uint256 x, uint256 y, uint176 verifiers)",
  "function getSigner(uint256 x, uint256 y, uint176 verifiers) view returns (address)",
  "function createSigner(uint256 x, uint256 y, uint176 verifiers) returns (address)",
]);

// EIP-712 SafeTx, as sim.mjs and firmware/safe_tx.py hash it.
export const TYPES = {
  SafeTx: [
    { name: "to", type: "address" }, { name: "value", type: "uint256" }, { name: "data", type: "bytes" },
    { name: "operation", type: "uint8" }, { name: "safeTxGas", type: "uint256" }, { name: "baseGas", type: "uint256" },
    { name: "gasPrice", type: "uint256" }, { name: "gasToken", type: "address" },
    { name: "refundReceiver", type: "address" }, { name: "nonce", type: "uint256" },
  ],
};
export function fields(t) {
  return { to: getAddress(t.to), value: BigInt(t.value), data: t.data || "0x", operation: Number(t.operation),
           safeTxGas: BigInt(t.safeTxGas), baseGas: BigInt(t.baseGas), gasPrice: BigInt(t.gasPrice),
           gasToken: getAddress(t.gasToken || ZERO), refundReceiver: getAddress(t.refundReceiver || ZERO), nonce: BigInt(t.nonce) };
}
export function safeTxHash(chainId, safe, t) {
  return hashTypedData({ domain: { chainId, verifyingContract: getAddress(safe) }, types: TYPES, primaryType: "SafeTx", message: fields(t) });
}
// The console's verify code: the hash's last 8 hex characters (firmware/safe_tx.py verify_code).
export const verifyCode = (h) => `${h.slice(-8, -4)} ${h.slice(-4)}`.toLowerCase();

// Every read the page makes goes through this client, often of a contract named in a link (a Safe, the
// owners it lists). ccipRead: false: such a contract can't have the visitor's browser fetch a URL it
// chooses (EIP-3668 offchain lookups), which viem otherwise follows.
export function client(name, rpc) {
  const c = CHAINS[name];
  return createPublicClient({ chain: c.chain, ccipRead: false, transport: http(rpc || c.rpc, { batch: true, retryCount: 2 }) });
}

// ----------------------------------------------------------------------------- the service
export class Service {
  constructor(name, apiKey, fetchImpl = globalThis.fetch.bind(globalThis)) {
    this.url = CHAINS[name].service;
    this.key = (apiKey || "").trim();
    this.fetch = fetchImpl;
  }
  async get(path) {
    const r = await this.fetch(this.url + path, { headers: this.key ? { Authorization: "Bearer " + this.key } : {} });
    if (r.status === 404) return null;
    if (r.status === 429) throw new Error("Safe's transaction service says too many requests. Add your own API key in Settings (developer.safe.global).");
    if (r.status === 401 || r.status === 403) throw new Error(`Safe's transaction service refused the request (HTTP ${r.status}). Check the API key in Settings.`);
    if (!r.ok) throw new Error(`Safe's transaction service: HTTP ${r.status}`);
    return r.json();
  }
  // A POST; the service's 4xx answers carry a reason, which is shown as is (it's text, drawn with textContent).
  async post(path, body) {
    const headers = { "Content-Type": "application/json", ...(this.key ? { Authorization: "Bearer " + this.key } : {}) };
    const r = await this.fetch(this.url + path, { method: "POST", headers, body: JSON.stringify(body) });
    if (r.ok) return r.status === 204 ? null : r.json().catch(() => null);
    if (r.status === 429) throw new Error("Safe's transaction service says too many requests. Add your own API key in Settings (developer.safe.global).");
    const text = await r.text().catch(() => "");
    let why = text;
    try { why = Object.values(JSON.parse(text)).flat(Infinity).filter((x) => typeof x === "string" || typeof x === "number").join(" "); } catch {}
    throw new Error(`Safe's transaction service refused it (HTTP ${r.status})${why ? `: ${why.slice(0, 400)}` : ""}`);
  }
  info(safe) { return this.get(`/api/v1/safes/${safe}/`); }
  propose(safe, body) { return this.post(`/api/v2/safes/${safe}/multisig-transactions/`, body); }
  confirm(hash, signature) { return this.post(`/api/v1/multisig-transactions/${hash}/confirmations/`, { signature }); }
  queue(safe, nonce) {
    return this.get(`/api/v2/safes/${safe}/multisig-transactions/?executed=false&nonce__gte=${nonce}&ordering=nonce&limit=20`);
  }
  recent(safe) { return this.get(`/api/v2/safes/${safe}/multisig-transactions/?executed=true&ordering=-nonce&limit=5`); }
}

// ----------------------------------------------------------------------------- the Safe, onchain
export async function readSafe(pub, safe) {
  const address = getAddress(safe);
  const code = await pub.getCode({ address });
  if (!code) return { address, missing: true };
  const read = (functionName) => pub.readContract({ address, abi: SAFE_ABI, functionName });
  const [owners, threshold, nonce, version, balance] = await Promise.all([
    read("getOwners"), read("getThreshold"), read("nonce"), read("VERSION").catch(() => "?"), pub.getBalance({ address })]);
  return { address, owners: owners.map((o) => getAddress(o)), threshold: Number(threshold), nonce: Number(nonce), version, balance };
}

// What each owner is: a wallet (no code, or an EIP-7702 delegation, which still signs as a wallet), a passkey signer proxy whose key we can name (its
// configuration recomputes to its own address through the factory in quorum_cfg.py), or some other
// contract. -> {kind: "wallet"|"passkey"|"contract", qx?, qy?, fingerprint?}
export async function ownerKind(pub, owner) {
  const code = await pub.getCode({ address: owner }).catch(() => null);
  if (!code) return { kind: "wallet" };
  if (code.toLowerCase().startsWith("0xef0100") && size(code) === 23) return { kind: "wallet", delegated: getAddress(slice(code, 3)) };
  try {
    const [x, y, verifiers] = await pub.readContract({ address: owner, abi: SIGNER_ABI, functionName: "getConfiguration" });
    const qx = toHex(x, { size: 32 }), qy = toHex(y, { size: 32 });
    if (BigInt(verifiers) === BigInt(CFG.signer.verifiers) && p256Owner(CFG.signer, qx, qy) === getAddress(owner))
      return { kind: "passkey", qx, qy, fingerprint: qx.slice(2, 10) };
  } catch {}
  return { kind: "contract" };
}

// ----------------------------------------------------------------------------- one queued transaction
// -> {hash, problems: [..], confirmations: [{owner, kind, ok, why, console}], valid: [..]}
export async function checkTx(pub, chainId, safe, owners, t, { onchainHash = true } = {}) {
  const mine = safeTxHash(chainId, safe, t);
  const problems = [];
  if (getAddress(t.safe) !== getAddress(safe)) problems.push(`the service lists it for another Safe, ${t.safe}`);
  if (mine !== t.safeTxHash) problems.push(`the service's hash ${t.safeTxHash} is not the hash of its own fields (${mine})`);
  if (onchainHash) {
    const f = fields(t);
    const theirs = await pub.readContract({ address: getAddress(safe), abi: SAFE_ABI, functionName: "getTransactionHash",
      args: [f.to, f.value, f.data, f.operation, f.safeTxGas, f.baseGas, f.gasPrice, f.gasToken, f.refundReceiver, f.nonce] });
    if (theirs !== mine) problems.push(`the Safe hashes these fields to ${theirs}, not ${mine}`);
  }
  const confirmations = await Promise.all((t.confirmations || []).map(async (c) => {
    const owner = getAddress(c.owner);
    const out = { owner, signature: c.signature, kind: "?", ok: false, why: "", console: false };
    try {
      const p = parse(c.signature);
      out.kind = p.kind;
      if (p.kind === "contract") {
        out.console = /"origin":"picoquorum"/.test(p.clientDataFields);
        if (p.owner !== owner) out.why = `the signature names ${p.owner}`;
        else {
          const r = await pub.readContract({ address: owner, abi: ERC1271_ABI, functionName: "isValidSignature", args: [mine, p.data] }).catch(() => "");
          out.ok = r === MAGIC;
          if (!out.ok) out.why = "the owner contract does not accept it for this hash";
        }
      } else if (p.kind === "ecdsa") {
        const v = Number(BigInt(slice(c.signature, 64, 65)));
        const signer = v > 30
          ? await recoverAddress({ hash: hashMessage({ raw: mine }), signature: slice(c.signature, 0, 64) + toHex(v - 4, { size: 1 }).slice(2) })
          : await recoverAddress({ hash: mine, signature: c.signature });
        out.ok = signer === owner;
        if (!out.ok) out.why = `it recovers to ${signer}`;
      } else if (p.kind === "approved") {
        out.ok = true;                 // approveHash onchain: the Safe checks approvedHashes itself
      }
    } catch (e) {
      out.why = e.shortMessage || e.message;
    }
    if (!owners.includes(owner)) {
      out.ok = false;
      out.why = out.why || "not an owner of this Safe";
    }
    return out;
  }));
  return { hash: mine, problems, confirmations, valid: confirmations.filter((c) => c.ok) };
}

// execTransaction's arguments with the first `threshold` valid confirmations packed (sorted by owner,
// contract signature data after the 65-byte slots).
export function execCall(t, valid, threshold) {
  const f = fields(t);
  const signatures = packSignatures(valid.slice(0, threshold).map((c) => ({ owner: c.owner, signature: c.signature })));
  const args = [f.to, f.value, f.data, f.operation, f.safeTxGas, f.baseGas, f.gasPrice, f.gasToken, f.refundReceiver, signatures];
  return { args, signatures, data: encodeFunctionData({ abi: SAFE_ABI, functionName: "execTransaction", args }) };
}

// The revert reason viem found (a Safe error code such as GS026), else its short message.
export function reason(e) {
  const r = e.walk?.((x) => x.reason || x.data?.errorName);
  return r?.reason || r?.data?.errorName || e.shortMessage || e.message;
}
export const GS = {
  GS013: "the inner call failed and the transaction set no safeTxGas or gasPrice, so the Safe reverts",
  GS020: "the packed signatures are too short",
  GS021: "a contract signature's data points outside the signatures (the Safe web app's bug)",
  GS022: "a contract signature's data is cut short",
  GS023: "a contract signature's length points past the end",
  GS024: "an owner contract rejected its signature",
  GS025: "an approved hash is not approved onchain",
  GS026: "a signer is not an owner, or the signers are out of order",
};

// Did the Safe's inner call succeed? A receipt can be a success while the Safe logged ExecutionFailure.
export function outcome(receipt, safe) {
  for (const log of receipt.logs) {
    if (getAddress(log.address) !== getAddress(safe)) continue;
    try {
      const ev = decodeEventLog({ abi: SAFE_ABI, data: log.data, topics: log.topics });
      if (ev.eventName === "ExecutionSuccess") return "success";
      if (ev.eventName === "ExecutionFailure") return "failure";
    } catch {}
  }
  return receipt.status === "success" ? "unknown" : "reverted";
}

export const eth = (wei) => {
  const s = formatEther(BigInt(wei));
  return s.includes(".") && s.split(".")[1].length > 6 ? Number(s).toFixed(6) : s;
};
export const dataBytes = (d) => (d && d !== "0x" ? size(d) : 0);

// One of the config's per-chain lists, as firmware/decode.py for_chain reads it: "*" and the chain's own.
export function forChain(key, chainId) {
  const c = String(chainId);
  const own = CFG.sameAs?.[c] ?? c;
  return { ...(CFG[key]?.["*"] || {}), ...(CFG[key]?.[own] || {}) };
}
// A contract the console knows by name, else null.
export function knownName(chainId, address) {
  const a = String(address).toLowerCase();
  const c = forChain("contracts", chainId)[a];
  return c ? c[0] : forChain("batchers", chainId)[a] || forChain("delegates", chainId)[a] || null;
}
// What the console will refuse outright, as firmware/decode.py's top level does (not what it finds
// inside a batch). -> "" or why.
export function consoleRefuses(chainId, t) {
  const op = Number(t.operation);
  if (op !== 0 && op !== 1) return `Operation ${op} is neither a call nor a delegatecall. The console will refuse it.`;
  if (op !== 1) return "";
  const a = String(t.to).toLowerCase();
  if (forChain("delegates", chainId)[a]) return "";
  // SignMessageLib: only a PicoQuorum release whose origin note gives exactly the calldata's digest
  if (forChain("messages", chainId)[a]) { const why = checkApproval(t); return why ? `The console signs only PicoQuorum releases here: ${why}.` : ""; }
  if (forChain("batchers", chainId)[a] && String(t.data || "").toLowerCase().startsWith("0x8d80ff0a")) return "";
  return "A delegatecall to a contract the console hasn't pinned. The console will refuse to sign it.";
}
