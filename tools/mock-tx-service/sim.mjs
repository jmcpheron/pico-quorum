// The Safe behind tools/quorum: its owners, threshold and nonce, the queue of transactions, and
// the checks a real Safe makes on each confirmation. Two backends share this file:
//   - simulated (the default): no chain. When a transaction has enough confirmations it
//     "executes" here (the nonce moves on, owner and threshold changes take effect), the way the
//     proposer's wallet would execute it for real.
//   - forked (useChain, tools/quorum up): the Safe is a real Safe 1.4.1 on an Anvil fork of Base
//     (chain.mjs). Owners, threshold and nonce are read from it, contract signatures are checked
//     with isValidSignature, and at threshold execTransaction runs for real.
// Either way the queue lives here, as it does in Safe's transaction service.
//
// Hashes come from viem, which shares no code with the console's firmware/safe_tx.py. So a
// console confirmation that verifies here proves the console hashed the same fields it showed.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { concat, decodeFunctionData, getAddress, hashTypedData, keccak256, parseAbi, recoverAddress } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import * as sigs from "./sigs.mjs";

export const ROOT = new URL("../../", import.meta.url);
let STATE_FILE = process.env.QUORUM_STATE || fileURLToPath(new URL("state.json", import.meta.url));
export function stateFile(name) {        // the forked Safe keeps its queue apart from the simulated one
  if (!process.env.QUORUM_STATE) STATE_FILE = fileURLToPath(new URL(name, import.meta.url));
}
export const ZERO = "0x0000000000000000000000000000000000000000";

// The console's pinned config is the one source for the Safe and its names (it is JSON on purpose).
export function loadCfg() {
  const src = readFileSync(new URL("firmware/quorum_cfg.py", ROOT), "utf8");
  return JSON.parse(src.slice(src.indexOf("{", src.indexOf("CFG ="))));
}
export const CFG = loadCfg();
export const BOOK = Object.fromEntries(Object.entries(CFG.book).map(([a, n]) => [n, getAddress(a)]));  // name -> address

// The simulated co-signers: anvil's well-known test accounts 1 and 2, which quorum_cfg.py names
// Alice and Bob. Never real keys.
export const PEOPLE = {
  alice: privateKeyToAccount("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"),
  bob: privateKeyToAccount("0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"),
};

export const TYPES = {
  SafeTx: [
    { name: "to", type: "address" }, { name: "value", type: "uint256" }, { name: "data", type: "bytes" },
    { name: "operation", type: "uint8" }, { name: "safeTxGas", type: "uint256" }, { name: "baseGas", type: "uint256" },
    { name: "gasPrice", type: "uint256" }, { name: "gasToken", type: "address" },
    { name: "refundReceiver", type: "address" }, { name: "nonce", type: "uint256" },
  ],
};
const FIELDS = ["to", "value", "data", "operation", "safeTxGas", "baseGas", "gasPrice", "gasToken", "refundReceiver", "nonce"];
const safeAbi = parseAbi([
  "function addOwnerWithThreshold(address owner, uint256 _threshold)",
  "function removeOwner(address prevOwner, address owner, uint256 _threshold)",
  "function swapOwner(address prevOwner, address oldOwner, address newOwner)",
  "function changeThreshold(uint256 _threshold)",
]);

export function safeTxHash(chainId, safe, f) {
  const message = { ...f, value: BigInt(f.value), safeTxGas: BigInt(f.safeTxGas), baseGas: BigInt(f.baseGas),
                    gasPrice: BigInt(f.gasPrice), nonce: BigInt(f.nonce), data: f.data || "0x" };
  return hashTypedData({ domain: { chainId, verifyingContract: safe }, types: TYPES, primaryType: "SafeTx", message });
}

// ----------------------------------------------------------------------------- the backend
let chain = null;       // chain.mjs's Chain while the Safe is the forked one, else simulated
let autoExec = true;    // false: like Safe's real service, never execute; tools/quorum live exec does

export function useChain(c, { manualExec = false } = {}) {
  chain = c;
  autoExec = !manualExec;
}

// ----------------------------------------------------------------------------- state
export function fresh() {
  const s = CFG.safes[0];
  return {
    chainId: s.chainId, address: getAddress(s.address), name: s.name, nonce: 0, threshold: 2, version: "1.4.1",
    owners: [{ address: PEOPLE.alice.address, name: "Alice", kind: "eoa" }, { address: PEOPLE.bob.address, name: "Bob", kind: "eoa" }],
    txs: [], log: [], clock: 0,
  };
}

export function load() {
  return existsSync(STATE_FILE) ? JSON.parse(readFileSync(STATE_FILE, "utf8")) : fresh();
}

export function save(st) {
  writeFileSync(STATE_FILE, JSON.stringify(st, null, 2) + "\n");
}

export function say(st, msg) {
  const line = `${new Date().toISOString().slice(11, 19)}  ${msg}`;
  st.log.push(line);
  if (st.log.length > 200) st.log.shift();
  console.log(line);
}

// A fixed, advancing clock for submissionDate: the same story always produces the same JSON.
function stamp(st) {
  st.clock += 1;
  return new Date(Date.UTC(2026, 8, 24, 12, 0, st.clock)).toISOString();
}

export function nameOf(st, a) {
  const o = st.owners.find((o) => o.address.toLowerCase() === a.toLowerCase());
  if (o) return o.name;
  const b = Object.entries(BOOK).find(([, x]) => x.toLowerCase() === a.toLowerCase());
  return b ? b[0] : a.slice(0, 6) + ".." + a.slice(-4);
}

// ----------------------------------------------------------------------------- the console's key
// A P-256 key cannot be a Safe owner by itself. It owns the Safe through the SafeWebAuthnSignerProxy
// the passkey factory deploys for it (quorum_cfg.py "signer"), and that proxy's address is the
// owner, computed the same way the console computes it for itself (firmware/webauthn.py).
export function p256Owner(qx, qy) {
  return sigs.p256Owner(CFG.signer, qx, qy);
}

export function registerDevice(st, { name, qx, qy }) {
  const address = p256Owner(qx, qy);
  let o = st.owners.find((o) => o.address === address);
  if (!o) {
    o = { address, name: "This key", kind: "p256", device: name, qx, qy };
    st.owners.push(o);
    say(st, `${name} joined as an owner: P-256 key ${qx.slice(2, 10)}.. -> signer ${address} (now ${st.threshold} of ${st.owners.length})`);
  } else {
    o.device = name;
  }
  return o;
}

// registerDevice, and on the fork the owner made real: the signer proxy deployed and added to the Safe.
export async function joinDevice(st, dev) {
  const o = registerDevice(st, dev);
  if (chain) await chain.enroll(st, o);
  return o;
}

// A fresh Safe: on the fork, the chain goes back to how setup left it.
export async function freshSafe() {
  const st = fresh();
  if (chain) {
    await chain.reset();
    await chain.refresh(st);
  }
  return st;
}

// ----------------------------------------------------------------------------- the queue
export function nextNonce(st) {
  return Math.max(st.nonce, ...st.txs.filter((t) => !t.isExecuted).map((t) => Number(t.nonce) + 1));
}

// fields: the SafeTx fields. opts: proposer (alice|bob), sign (the proposer confirms),
// lie (fields the service reports a hash for, instead of the ones it shows), reportSafe, scenario.
export async function propose(st, fields, opts = {}) {
  const f = { value: "0", data: "0x", operation: 0, safeTxGas: "0", baseGas: "0", gasPrice: "0", gasToken: ZERO,
              refundReceiver: ZERO, nonce: nextNonce(st), ...fields };
  for (const k of ["value", "safeTxGas", "baseGas", "gasPrice", "nonce"]) f[k] = String(f[k]);
  f.to = getAddress(f.to); f.gasToken = getAddress(f.gasToken); f.refundReceiver = getAddress(f.refundReceiver);
  const safe = opts.reportSafe ? getAddress(opts.reportSafe) : st.address;
  const trueHash = safeTxHash(st.chainId, st.address, f);
  const reported = opts.lie ? safeTxHash(st.chainId, st.address, { ...f, ...opts.lie })
    : opts.reportSafe ? safeTxHash(st.chainId, safe, f) : trueHash;
  const by = PEOPLE[opts.proposer || "alice"];
  const tx = {
    safe, ...f, safeTxHash: reported, trueHash, proposer: by.address, submissionDate: stamp(st),
    confirmations: [], isExecuted: false, executionDate: null, transactionHash: null,
    scenario: opts.scenario || "", declined: [],
  };
  if (chain) await chain.checkHash(st, f, trueHash);
  st.txs.push(tx);
  say(st, `${nameOf(st, by.address)} proposed #${tx.nonce} ${opts.scenario || ""} ${reported.slice(0, 10)}..` +
    (opts.lie ? "  (the service LIES: the hash is for other fields)" : "") + (opts.reportSafe ? "  (reported for another Safe)" : ""));
  return tx;
}

export function find(st, ref) {
  ref = String(ref).toLowerCase();
  if (/^\d+$/.test(ref)) return st.txs.filter((t) => !t.isExecuted && t.nonce === ref).pop();
  return st.txs.find((t) => t.safeTxHash.toLowerCase().startsWith(ref));
}

export async function signAs(st, who, tx) {
  const sig = await PEOPLE[who].sign({ hash: tx.trueHash });
  return confirm(st, tx, sig);
}

// Check one signature the way the Safe would at execution (against the hash of the fields),
// then record it. ECDSA (65 bytes) by an owner, or a contract signature (v = 0) from an owner
// contract: a console's signer proxy, checked off chain here (WebAuthn, sigs.mjs) or by the proxy
// itself on the fork (isValidSignature), which is what Safe's transaction service does.
export async function confirm(st, tx, signature) {
  let p;
  try {
    p = sigs.parse(signature);
  } catch (e) {
    return { ok: false, error: e.message };
  }
  if (p.kind === "ecdsa") {
    const a = await recoverAddress({ hash: tx.trueHash, signature });
    const owner = st.owners.find((o) => o.address === a);
    if (!owner) return { ok: false, error: `signer ${a} is not an owner` };
    return record(st, tx, owner, "EOA", signature, "ECDSA");
  }
  const owner = st.owners.find((o) => o.address === p.owner);
  if (!owner) return { ok: false, error: `signer ${p.owner} is not an owner` };
  const why = await contractCheck(owner, tx.trueHash, p);
  if (!why) {
    const note = chain ? "the signer proxy's isValidSignature said yes" : `WebAuthn P-256 verified, ${sigs.highS(p.s) ? "high s" : "low s"}`;
    return record(st, tx, owner, "CONTRACT_SIGNATURE", signature, note);
  }
  if (tx.trueHash !== tx.safeTxHash && !(await contractCheck(owner, tx.safeTxHash, p))) {
    say(st, `!! ${owner.device || owner.name} signed the hash the service reported for #${tx.nonce}, not the fields it showed: blind signing`);
    return { ok: false, error: "signature is for the reported hash, not the transaction's fields" };
  }
  return { ok: false, error: `${owner.name}'s signature does not verify over this transaction: ${why}` };
}

// "" when owner's contract signature p is valid for hash, else why not.
async function contractCheck(owner, hash, p) {
  if (chain) return (await chain.isValidSignature(owner.address, hash, p.data)) ? "" : "isValidSignature refused it";
  if (owner.kind !== "p256") return "not a console key this simulation knows";
  return sigs.checkWebAuthn(hash, p, owner.qx, owner.qy);
}

async function record(st, tx, owner, type, signature, note) {
  if (tx.isExecuted) return { ok: false, error: "already executed" };
  if (tx.confirmations.some((c) => c.owner === owner.address)) return { ok: false, error: `${owner.name} already confirmed` };
  tx.confirmations.push({ owner: owner.address, submissionDate: stamp(st), transactionHash: null, signature, signatureType: type });
  say(st, `${owner.name} confirmed #${tx.nonce} (${note}): ${tx.confirmations.length} of ${st.threshold}`);
  await execute(st);
  return { ok: true, owner: owner.address, name: owner.name };
}

export function decline(st, tx, by) {
  tx.declined.push(by);
  say(st, `${by} REJECTED #${tx.nonce} on the device (nothing is sent to the Safe; the proposer can replace it)`);
}

// Execute whatever is ready, in nonce order, as the proposer's wallet would. Other transactions
// at the same nonce can never run after that; the service drops them from the queue. On the fork
// this is execTransaction for real; one that would revert stays in the queue with the reason.
export async function execute(st) {
  for (;;) {
    const t = st.txs.find((t) => !t.isExecuted && Number(t.nonce) === st.nonce && t.trueHash === t.safeTxHash &&
                                 t.safe === st.address && t.confirmations.length >= st.threshold);
    if (!t) return;
    if (chain && !autoExec) {
      if (!t.ready) say(st, `#${t.nonce} ${t.scenario} has ${t.confirmations.length} of ${st.threshold}: ready for tools/quorum live exec --chain local ${t.nonce}`);
      t.ready = true;
      return;
    }
    if (chain) {
      const r = await chain.execute(st, t);
      if (!r.ok) {
        if (t.revert !== r.reason) say(st, `#${t.nonce} ${t.scenario} has ${t.confirmations.length} of ${st.threshold} but would revert onchain: ${r.reason}`);
        t.revert = r.reason;
        return;
      }
      Object.assign(t, { isExecuted: true, executionDate: stamp(st), transactionHash: r.hash, isSuccessful: r.success, revert: null });
      await chain.refresh(st);
      say(st, `EXECUTED #${t.nonce} ${t.scenario} onchain: tx ${r.hash.slice(0, 12)}.., ${r.gasUsed} gas${r.success ? "" : ", but the Safe says the call FAILED"}. ` +
        `Now ${st.threshold} of ${st.owners.length}, nonce ${st.nonce}`);
      continue;
    }
    t.isExecuted = true;
    t.executionDate = stamp(st);
    t.transactionHash = keccak256(concat([t.trueHash, "0x01"]));
    st.nonce += 1;
    const effect = apply(st, t);
    say(st, `EXECUTED #${t.nonce} ${t.scenario}${effect ? ": " + effect : ""}. Safe nonce is now ${st.nonce}`);
  }
}

function apply(st, t) {
  if (t.to !== st.address || !t.data || t.data === "0x") return "";
  let call;
  try {
    call = decodeFunctionData({ abi: safeAbi, data: t.data });
  } catch {
    return "";
  }
  const [a0, a1, a2] = call.args;
  if (call.functionName === "addOwnerWithThreshold") {
    st.owners.push({ address: getAddress(a0), name: nameOf(st, a0), kind: "eoa" });
    st.threshold = Number(a1);
  } else if (call.functionName === "removeOwner") {
    st.owners = st.owners.filter((o) => o.address !== getAddress(a1));
    st.threshold = Number(a2);
  } else if (call.functionName === "swapOwner") {
    const o = st.owners.find((o) => o.address === getAddress(a1));
    if (o) Object.assign(o, { address: getAddress(a2), name: nameOf(st, a2), kind: "eoa" });
  } else if (call.functionName === "changeThreshold") {
    st.threshold = Number(a0);
  }
  return `${call.functionName}, now ${st.threshold} of ${st.owners.length}`;
}

// ----------------------------------------------------------------------------- the API's shapes
// As Safe's transaction service returns them (api.safe.global/tx-service), minus what the
// console never reads. "data" is null when empty, as the real service sends it.
export function apiSafe(st) {
  return {
    address: st.address, nonce: st.nonce, threshold: st.threshold, owners: st.owners.map((o) => o.address),
    masterCopy: st.masterCopy || "0x41675C099F32341bf84BFc5382aF534df5C7461a", modules: [],
    fallbackHandler: st.fallbackHandler || ZERO, guard: ZERO, version: st.version || "1.4.1",
  };
}

export function apiTx(st, t) {
  const out = { safe: t.safe };
  for (const k of FIELDS) out[k] = t[k];
  out.data = t.data && t.data !== "0x" ? t.data : null;
  return {
    ...out, executionDate: t.executionDate, submissionDate: t.submissionDate, modified: t.submissionDate,
    transactionHash: t.transactionHash, safeTxHash: t.safeTxHash, proposer: t.proposer,
    isExecuted: t.isExecuted, isSuccessful: t.isExecuted ? t.isSuccessful ?? true : null, confirmationsRequired: st.threshold,
    confirmations: t.confirmations, trusted: true, dataDecoded: null,
  };
}

export function apiList(st, q) {
  let r = st.txs;
  if (q.get("executed") === "false") r = r.filter((t) => !t.isExecuted);
  if (q.get("executed") === "true") r = r.filter((t) => t.isExecuted);
  if (q.has("nonce__gte")) r = r.filter((t) => Number(t.nonce) >= Number(q.get("nonce__gte")));
  if (q.has("nonce")) r = r.filter((t) => Number(t.nonce) === Number(q.get("nonce")));
  r = [...r].sort((a, b) => (q.get("ordering") === "-nonce" ? -1 : 1) * (Number(a.nonce) - Number(b.nonce)));
  const limit = Number(q.get("limit") || 20);
  return { count: r.length, next: null, previous: null, results: r.slice(0, limit).map((t) => apiTx(st, t)) };
}
