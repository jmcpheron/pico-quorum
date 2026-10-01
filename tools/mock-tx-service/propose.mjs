// Starting a Safe transaction without the Safe web app: the parts of tools/quorum live propose and
// live delegate that need no terminal (live.mjs is the command line around them).
//
// Safe's transaction service lists a transaction only once an owner or a delegate has signed it.
// The console signs only what the service lists. So a Safe whose only working owners are consoles
// needs some other way in, and these are the ways:
//   - an owner's ordinary wallet signs the proposal: a Foundry keystore, or the browser's wallet
//   - a delegate signs it: a laptop key an owner registered beforehand, which may propose but whose
//     signature never counts
//   - a console signs it: the laptop serves this one transaction to the console over the LAN, the
//     way Safe's service would (Stage below), the console shows it and signs it after the hold, and
//     that signature, a contract signature checked onchain here, goes to Safe's service as the
//     proposal. Or, with no service at all, the laptop collects the consoles' signatures itself and
//     executes when there are enough.
// None of these trusts the laptop: the console hashes the fields it shows, and the Safe checks
// every signature against that hash.
import { createServer } from "node:http";
import {
  concat, encodeFunctionData, encodePacked, formatEther, getAddress, hashMessage, isAddress, keccak256, parseAbi, parseEther, recoverAddress,
  size, slice, toHex,
} from "viem";
import { ERC1271_ABI, SAFE_ABI } from "./chain.mjs";
import { TYPES, ZERO, apiList, apiTx } from "./sim.mjs";
import { parse } from "./sigs.mjs";

export const SENTINEL = "0x0000000000000000000000000000000000000001";      // the head of the Safe's owner list
export const MULTISEND = "0x9641D764fC13c8B624c04430C7356C1C7C8102e2";     // MultiSendCallOnly 1.4.1, a pinned batcher (quorum_cfg.py)
const MAGIC = "0x1626ba7e";
const OWNER_ABI = parseAbi([
  "function addOwnerWithThreshold(address owner, uint256 _threshold)",
  "function removeOwner(address prevOwner, address owner, uint256 _threshold)",
  "function swapOwner(address prevOwner, address oldOwner, address newOwner)",
  "function changeThreshold(uint256 _threshold)",
]);
const MULTISEND_ABI = parseAbi(["function multiSend(bytes transactions) payable"]);
const GUARD_SLOT = keccak256(toHex("guard_manager.guard.address"));
const HANDLER_SLOT = keccak256(toHex("fallback_manager.handler.address"));

export const KINDS = {
  send: "send TO ETH                     send ETH from the Safe",
  call: "call TO DATA [--value ETH]      call a contract (the console shows unknown contracts red)",
  "swap-owner": "swap-owner OLD NEW [OLD NEW..]  replace owners; two or more pairs go in one MultiSend",
  "add-owner": "add-owner NEW [--threshold N]   add an owner (the threshold stays unless given)",
  "remove-owner": "remove-owner OLD [--threshold N]",
  threshold: "threshold N                     change the threshold",
  reject: "reject NONCE                    an empty transaction at NONCE, to replace whatever waits there",
};

// The Safe keeps its owners as a linked list, and removeOwner and swapOwner name the owner before
// the one they change. owners: getOwners() order.
export function prevOwner(owners, owner) {
  const i = owners.findIndex((o) => getAddress(o) === getAddress(owner));
  if (i < 0) throw new Error(`${owner} is not an owner`);
  return i === 0 ? SENTINEL : getAddress(owners[i - 1]);
}

// Calls in MultiSend's packed form: operation, to, value, data length, data, one after another.
export function multiSend(calls) {
  const packed = concat(calls.map((c) => encodePacked(["uint8", "address", "uint256", "uint256", "bytes"],
    [0, getAddress(c.to), c.value || 0n, BigInt(size(c.data)), c.data])));
  return encodeFunctionData({ abi: MULTISEND_ABI, functionName: "multiSend", args: [packed] });
}

const addr = (a, what) => {
  if (!isAddress(a || "")) throw new Error(`${what}: ${a === undefined ? "missing" : `${a} is not an address`}`);
  return getAddress(a);
};

// What the words ask for, as a call from the Safe: {to, value, data, operation, what} (and nonce for
// reject). safe: {address, owners (getOwners order), threshold}. opts: {value, threshold} from flags.
export function build(words, safe, opts = {}) {
  const [kind, ...a] = words;
  const owners = safe.owners.map((o) => getAddress(o));
  const isOwner = (x) => owners.includes(x);
  const self = (data, what) => ({ to: safe.address, value: 0n, data, operation: 0, what });
  const threshold = (t, n) => {
    const v = Number(t);
    if (!Number.isInteger(v) || v < 1 || v > n) throw new Error(`threshold ${t}: it must be 1 to ${n}`);
    return v;
  };
  switch (kind) {
    case "send": {
      const to = addr(a[0], "send TO");
      if (!a[1] || !/^\d*\.?\d+$/.test(a[1])) throw new Error("send TO ETH: how much, in ETH (0.01, say)");
      const value = parseEther(a[1]);
      return { to, value, data: "0x", operation: 0, what: `Send ${formatEther(value)} ETH to ${to}` };
    }
    case "call": {
      const to = addr(a[0], "call TO");
      if (!/^0x([0-9a-fA-F]{2})*$/.test(a[1] || "")) throw new Error("call TO DATA: the call data, 0x and an even number of hex digits");
      const value = opts.value ? parseEther(opts.value) : 0n;
      return { to, value, data: a[1], operation: 0, what: `Call ${to} with ${size(a[1])} bytes${value ? ` and ${formatEther(value)} ETH` : ""}` };
    }
    case "swap-owner": {
      if (!a.length || a.length % 2) throw new Error("swap-owner OLD NEW [OLD NEW..]: pairs of addresses");
      const list = [...owners];
      const calls = [];
      const lines = [];
      for (let i = 0; i < a.length; i += 2) {
        const [old, neu] = [addr(a[i], "swap-owner OLD"), addr(a[i + 1], "swap-owner NEW")];
        if (!list.includes(old)) throw new Error(`${old} is not an owner${isOwner(old) ? " any more (swapped above)" : ""}`);
        if (list.includes(neu)) throw new Error(`${neu} is already an owner`);
        calls.push({ to: safe.address, value: 0n, data: encodeFunctionData({ abi: OWNER_ABI, functionName: "swapOwner", args: [prevOwner(list, old), old, neu] }) });
        list[list.indexOf(old)] = neu;           // the list after this swap, for the next one's prevOwner
        lines.push(`${old} -> ${neu}`);
      }
      if (calls.length === 1) return self(calls[0].data, `Replace owner ${lines[0]}`);
      return { to: MULTISEND, value: 0n, data: multiSend(calls), operation: 1,
               what: `Replace ${calls.length} owners in one MultiSend: ${lines.join(", ")}` };
    }
    case "add-owner": {
      const neu = addr(a[0], "add-owner NEW");
      if (isOwner(neu)) throw new Error(`${neu} is already an owner`);
      const t = threshold(opts.threshold ?? safe.threshold, owners.length + 1);
      return self(encodeFunctionData({ abi: OWNER_ABI, functionName: "addOwnerWithThreshold", args: [neu, BigInt(t)] }),
                  `Add owner ${neu}, then ${t} of ${owners.length + 1}`);
    }
    case "remove-owner": {
      const old = addr(a[0], "remove-owner OLD");
      if (!isOwner(old)) throw new Error(`${old} is not an owner`);
      const t = threshold(opts.threshold ?? Math.min(safe.threshold, owners.length - 1), owners.length - 1);
      return self(encodeFunctionData({ abi: OWNER_ABI, functionName: "removeOwner", args: [prevOwner(owners, old), old, BigInt(t)] }),
                  `Remove owner ${old}, then ${t} of ${owners.length - 1}`);
    }
    case "threshold": {
      const t = threshold(a[0], owners.length);
      return self(encodeFunctionData({ abi: OWNER_ABI, functionName: "changeThreshold", args: [BigInt(t)] }),
                  `Change the threshold to ${t} of ${owners.length}`);
    }
    case "reject": {
      if (!/^\d+$/.test(a[0] || "")) throw new Error("reject NONCE");
      return { ...self("0x", `Reject #${a[0]}: an empty transaction at that nonce, so nothing else can run there`), nonce: Number(a[0]) };
    }
    default:
      throw new Error(`what to propose?\n  ${Object.values(KINDS).join("\n  ")}`);
  }
}

// The SafeTx fields for a call at a nonce, as the service and sim.safeTxHash take them: no gas
// refund, so nothing is paid to whoever executes.
export function fields(call, nonce) {
  return { to: getAddress(call.to), value: String(call.value), data: call.data || "0x", operation: call.operation, safeTxGas: "0",
           baseGas: "0", gasPrice: "0", gasToken: ZERO, refundReceiver: ZERO, nonce: String(nonce) };
}

// EIP-712 for a wallet's eth_signTypedData_v4: plain JSON, numbers as strings.
export function typedJson(td) {
  const domainTypes = [["name", "string"], ["version", "string"], ["chainId", "uint256"], ["verifyingContract", "address"]]
    .filter(([k]) => td.domain[k] !== undefined).map(([name, type]) => ({ name, type }));
  return JSON.parse(JSON.stringify({ ...td, types: { EIP712Domain: domainTypes, ...td.types } }, (k, v) => (typeof v === "bigint" ? v.toString() : v)));
}

export function safeTxTypedData(chainId, safe, f) {
  const message = { ...f, value: BigInt(f.value), safeTxGas: BigInt(f.safeTxGas), baseGas: BigInt(f.baseGas), gasPrice: BigInt(f.gasPrice),
                    nonce: BigInt(f.nonce) };
  return { domain: { chainId, verifyingContract: getAddress(safe) }, types: TYPES, primaryType: "SafeTx", message };
}

// The body of POST /api/v1/safes/{safe}/multisig-transactions/ (the service's SafeMultisigTransaction).
export function proposalBody(safe, f, hash, sender, signature) {
  return { safe: getAddress(safe), ...f, data: f.data === "0x" ? null : f.data, nonce: Number(f.nonce), contractTransactionHash: hash,
           sender: getAddress(sender), signature, origin: "PicoQuorum" };
}

// Who made this signature over hash, checked the way the Safe checks it at execution: an ECDSA
// owner's address by recovery (eth_sign too), a contract owner's by asking it (isValidSignature).
// -> {owner, kind}; throws when it does not check out.
export async function signerOf(pub, hash, signature) {
  const p = parse(signature);
  if (p.kind === "ecdsa") {
    const v = Number(BigInt(slice(signature, 64, 65)));
    const owner = v > 30 ? await recoverAddress({ hash: hashMessage({ raw: hash }), signature: slice(signature, 0, 64) + toHex(v - 4, { size: 1 }).slice(2) })
                         : await recoverAddress({ hash, signature });
    return { owner, kind: "ecdsa" };
  }
  if (p.kind === "contract") {
    const r = await pub.readContract({ address: p.owner, abi: ERC1271_ABI, functionName: "isValidSignature", args: [hash, p.data] }).catch(() => "");
    if (r !== MAGIC) throw new Error(`${p.owner}'s isValidSignature refused it`);
    return { owner: p.owner, kind: "contract" };
  }
  throw new Error("an approveHash marker, not a signature");
}

// The Safe as Safe's service describes it, read from the chain instead.
export async function safeOnchain(pub, safe) {
  const read = (functionName) => pub.readContract({ address: safe, abi: SAFE_ABI, functionName });
  const [owners, threshold, nonce, version, singleton, handler, guard] = await Promise.all([
    read("getOwners"), read("getThreshold"), read("nonce"), read("VERSION"), pub.getStorageAt({ address: safe, slot: "0x0" }),
    pub.getStorageAt({ address: safe, slot: HANDLER_SLOT }), pub.getStorageAt({ address: safe, slot: GUARD_SLOT })]);
  const word = (w) => getAddress("0x" + (w || "0x").slice(-40).padStart(40, "0"));
  return { address: getAddress(safe), owners: owners.map((o) => getAddress(o)), threshold: Number(threshold), nonce: Number(nonce),
           version, masterCopy: word(singleton), fallbackHandler: word(handler), guard: word(guard), modules: [] };
}

// ----------------------------------------------------------------------------- the stage
// Safe's service for one Safe and the transactions proposed here, on the LAN, for consoles pointed
// at it (tools/quorum live pico --stage). The Safe itself (owners, threshold, nonce) is read from
// the chain, so this works with Safe's service down. Each confirmation is checked as the Safe will
// check it before it is kept. The console's simulation hooks (/sim/device, /sim/declined) answer
// as a real service would: there is no simulation to join, and a decline is only logged.
export class Stage {
  // pub: a viem public client for the Safe's chain. onChange(tx): after each new confirmation.
  constructor({ pub, safe, port, log = console.log, onChange = () => {} }) {
    Object.assign(this, { pub, safe: getAddress(safe), port, log, onChange, txs: [], info: null, read: 0, waiters: [] });
  }

  add(f, hash, confirmations = []) {
    const t = { safe: this.safe, ...f, safeTxHash: hash, proposer: null, submissionDate: new Date().toISOString(), confirmations: [...confirmations],
                isExecuted: false, executionDate: null, transactionHash: null, declined: [] };
    this.txs.push(t);
    return t;
  }

  async safeInfo() {
    if (!this.info || Date.now() - this.read > 2000) {
      this.info = await safeOnchain(this.pub, this.safe);
      this.read = Date.now();
    }
    return this.info;
  }

  async confirm(t, signature) {
    let s;
    try {
      s = await signerOf(this.pub, t.safeTxHash, signature);
    } catch (e) {
      return [400, { detail: e.message }];
    }
    const info = await this.safeInfo();
    if (!info.owners.includes(s.owner)) return [400, { detail: `Signer=${s.owner} is not an owner` }];
    if (t.confirmations.some((c) => c.owner === s.owner)) return [400, { detail: `${s.owner} already confirmed` }];
    t.confirmations.push({ owner: s.owner, submissionDate: new Date().toISOString(), transactionHash: null, signature,
                           signatureType: s.kind === "ecdsa" ? "EOA" : "CONTRACT_SIGNATURE" });
    this.log(`  signed by ${s.owner} (${s.kind === "ecdsa" ? "ECDSA" : "contract signature, its isValidSignature said yes"}): ` +
             `${t.confirmations.length} of ${info.threshold}`);
    this.onChange(t);
    this.wake();
    return [201, { signature }];
  }

  wake() {
    for (const w of this.waiters.splice(0)) w();
  }

  // Resolves once pred() is true, checked after every confirmation or decline.
  async until(pred) {
    while (!(await pred())) await new Promise((r) => this.waiters.push(r));
  }

  async route(method, path, q, body) {
    const safeIs = (a) => getAddress(a) === this.safe;
    let m;
    if (method === "GET" && (m = path.match(/^\/api\/v1\/safes\/(0x[0-9a-fA-F]{40})\/?$/))) {
      return safeIs(m[1]) ? [200, await this.safeInfo()] : [404, { detail: "Not found." }];
    }
    if (method === "GET" && (m = path.match(/^\/api\/v2\/safes\/(0x[0-9a-fA-F]{40})\/multisig-transactions\/?$/))) {
      if (!safeIs(m[1])) return [200, { count: 0, next: null, previous: null, results: [] }];
      const info = await this.safeInfo();
      for (const t of this.txs) if (Number(t.nonce) < info.nonce) t.isExecuted = true;      // spent onchain: gone from the queue
      return [200, apiList({ threshold: info.threshold, txs: this.txs }, q)];
    }
    if (method === "GET" && (m = path.match(/^\/api\/v1\/multisig-transactions\/(0x[0-9a-fA-F]{64})\/?$/))) {
      const t = this.txs.find((t) => t.safeTxHash === m[1].toLowerCase());
      return t ? [200, apiTx({ threshold: (await this.safeInfo()).threshold }, t)] : [404, { detail: "Not found." }];
    }
    if (method === "POST" && (m = path.match(/^\/api\/v1\/multisig-transactions\/(0x[0-9a-fA-F]{64})\/confirmations\/?$/))) {
      const t = this.txs.find((t) => t.safeTxHash === m[1].toLowerCase());
      return t ? this.confirm(t, body.signature || "0x") : [404, { detail: "Not found." }];
    }
    if (method === "POST" && path === "/sim/declined") {
      const t = this.txs.find((t) => t.safeTxHash === String(body.safeTxHash || "").toLowerCase());
      if (t) {
        t.declined.push(body.by || "a console");
        this.log(`  ${body.by || "a console"} declined it: nothing signed. The console hides it until it restarts.`);
        this.wake();
      }
      return [200, { ok: !!t }];
    }
    return [404, { detail: "Not found." }];
  }

  start(host = "0.0.0.0") {
    this.server = createServer(async (req, res) => {
      const url = new URL(req.url, "http://x");
      let raw = "";
      for await (const c of req) raw += c;
      let code;
      let out;
      try {
        [code, out] = await this.route(req.method, url.pathname, url.searchParams, raw ? JSON.parse(raw) : {});
      } catch (e) {
        [code, out] = [500, { detail: e.shortMessage || e.message }];
      }
      if (code >= 400 && url.pathname !== "/sim/device") this.log(`  ${req.method} ${url.pathname} -> ${code} ${out.detail || ""}`);
      res.writeHead(code, { "Content-Type": "application/json" }).end(JSON.stringify(out));
    });
    return new Promise((resolve, reject) => {
      this.server.on("error", reject);
      this.server.listen(this.port, host, resolve);
    });
  }

  close() {
    this.server?.close();
    this.server?.closeAllConnections?.();
  }
}
