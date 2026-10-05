// Proposing, with no DOM in it so web/test.mjs can drive it: each kind of transaction the page can
// build, the nonce it gets, what the wallet signs (EIP-712 SafeTx, the hash the console recomputes),
// the signature checked before anything is sent, and the body Safe's transaction service takes.
//
// Every kind is a plain call (operation 0) with no gas refund: the console refuses delegatecalls it
// hasn't pinned, and treats any gas field as worth a warning (firmware/decode.py).
import { approvalTx } from "../../tools/mock-tx-service/release.mjs";
import { encodeFunctionData, getAddress, isAddress, isHex, parseAbi, parseUnits, recoverAddress, size, slice, toHex } from "viem";
import { TYPES, ZERO, fields, forChain } from "./safe.mjs";

export const SENTINEL = "0x0000000000000000000000000000000000000001";
export const OWNER_ABI = parseAbi([
  "function addOwnerWithThreshold(address owner, uint256 _threshold)",
  "function removeOwner(address prevOwner, address owner, uint256 _threshold)",
  "function swapOwner(address prevOwner, address oldOwner, address newOwner)",
  "function changeThreshold(uint256 _threshold)",
]);
export const ERC20_ABI = parseAbi([
  "function transfer(address to, uint256 amount) returns (bool)",
  "function decimals() view returns (uint8)",
  "function symbol() view returns (string)",
  "function balanceOf(address owner) view returns (uint256)",
]);

// The kinds, in the order the page offers them. red: it changes who controls the Safe, and the
// console shows it on a red page.
export const KINDS = [
  { id: "eth", label: "Send ETH" },
  { id: "token", label: "Send a token" },
  { id: "add", label: "Add owner", red: true },
  { id: "remove", label: "Remove owner", red: true },
  { id: "swap", label: "Replace owner", red: true },
  { id: "threshold", label: "Change threshold", red: true },
  { id: "reject", label: "Rejection" },
  { id: "custom", label: "Contract call" },
  // The project Safe approving a PicoQuorum release (docs/GOVERNANCE.md): offered from the Releases page.
  { id: "release", label: "Approve a release", gov: true },
];

// The tokens the console names on this chain (firmware/quorum_cfg.py "tokens"): [{address, symbol, decimals}].
export const knownTokens = (chainId) =>
  Object.entries(forChain("tokens", chainId)).map(([a, [symbol, decimals]]) => ({ address: getAddress(a), symbol, decimals }));

// The linked list's previous entry, as removeOwner and swapOwner want it. getOwners() returns the
// list in order, starting after the sentinel.
export function prevOwner(owners, owner) {
  const i = owners.indexOf(getAddress(owner));
  if (i < 0) throw new Error(`${owner} isn't an owner of this Safe.`);
  return i === 0 ? SENTINEL : owners[i - 1];
}

// The nonce a new proposal takes: after the Safe's own and after everything already queued, as
// Safe{Wallet} picks it.
export const nextNonce = (onchainNonce, queued = []) => Math.max(onchainNonce, ...queued.map((t) => Number(t.nonce) + 1));

// A rejection: the Safe calling itself with nothing. Executed, it uses up the nonce and so cancels
// every other transaction at that nonce. The console shows it as REJECTION.
export const isRejection = (safe, t) =>
  getAddress(t.to) === getAddress(safe) && BigInt(t.value) === 0n && !(t.data && t.data !== "0x");

function addr(x, what) {
  const a = String(x || "").trim();
  if (!isAddress(a, { strict: false })) throw new Error(`${what}: that isn't an address. Paste 0x and 40 hex characters.`);
  const g = getAddress(a);
  if (g === ZERO || g === SENTINEL) throw new Error(`${what} can't be ${g}.`);
  return g;
}
function amount(x, decimals, what) {
  const s = String(x || "").trim();
  if (!/^\d+(\.\d+)?$/.test(s)) throw new Error(`${what}: write a number, such as 0.01.`);
  if ((s.split(".")[1] || "").length > decimals) throw new Error(`${what}: at most ${decimals} decimal places.`);
  return parseUnits(s, decimals);
}
function threshold(x, max) {
  const n = Number(x);
  if (!Number.isInteger(n) || n < 1 || n > max) throw new Error(`Approvals needed must be a whole number from 1 to ${max}.`);
  return n;
}

// One kind and the form's values -> {call: {to, value, data, operation}, title, red, warnings: [..]}.
// s: the Safe as read onchain {address, owners, threshold, balance}. Throws with a sentence for the page.
// For "token", input carries the token's decimals and symbol, read from the chain by the page.
export function buildCall(kind, input, s) {
  const safe = getAddress(s.address);
  const owners = s.owners.map((o) => getAddress(o));
  const n = owners.length;
  const warnings = [];
  const self = (data) => ({ to: safe, value: 0n, data, operation: 0 });
  const keepsQuorum = (t, count) => {
    if (t === 1 && count > 1) warnings.push("With 1 approval needed, any one owner can move everything alone.");
  };
  switch (kind) {
    case "release": {
      const r = input.releaseEntry;
      if (!r) throw new Error("Release: pick one.");
      const tx = approvalTx({ version: r.version, firmware: "0x" + r.fingerprints.console, manifest: "0x" + r.manifestSha256 });
      return { call: { to: getAddress(tx.to), value: 0n, data: tx.data, operation: 1, origin: tx.origin }, title: `Approve release ${r.version}`,
        release: { ...r, digest: tx.digest },
        warnings: ["The Safe signs this release's digest for good, with Safe's SignMessageLib (a delegatecall the console pins). Anyone can then check the approval on chain."] };
    }
    case "eth": {
      const to = addr(input.to, "To");
      const value = amount(input.amount, 18, "Amount");
      if (value === 0n) throw new Error("Amount: send more than 0.");
      if (to === safe) throw new Error("That's the Safe itself. Use Rejection to cancel a transaction.");
      if (s.balance != null && value > BigInt(s.balance)) warnings.push("The Safe holds less ETH than this right now. It will fail unless it's funded first.");
      return { call: { to, value, data: "0x", operation: 0 }, title: `Send ${input.amount} ETH`, warnings };
    }
    case "token": {
      const token = addr(input.token, "Token");
      const to = addr(input.to, "To");
      if (!Number.isInteger(input.decimals)) throw new Error("Token: its decimals couldn't be read. Is it an ERC-20 on this chain?");
      const value = amount(input.amount, input.decimals, "Amount");
      if (value === 0n) throw new Error("Amount: send more than 0.");
      if (input.balance != null && value > BigInt(input.balance)) warnings.push(`The Safe holds less ${input.symbol} than this right now.`);
      if (!input.known) warnings.push("This token isn't in the console's list, so the console shows the amount in raw units and in amber.");
      return { call: { to: token, value: 0n, data: encodeFunctionData({ abi: ERC20_ABI, functionName: "transfer", args: [to, value] }), operation: 0 },
               title: `Send ${input.amount} ${input.symbol}`, warnings };
    }
    case "add": {
      const owner = addr(input.owner, "New owner");
      if (owners.includes(owner)) throw new Error("That address is already an owner.");
      if (owner === safe) throw new Error("A Safe can't own itself.");
      const t = threshold(input.threshold, n + 1);
      keepsQuorum(t, n + 1);
      return { call: self(encodeFunctionData({ abi: OWNER_ABI, functionName: "addOwnerWithThreshold", args: [owner, BigInt(t)] })),
               title: `Add owner, ${t} of ${n + 1}`, red: true, warnings };
    }
    case "remove": {
      const owner = addr(input.owner, "Owner");
      if (n < 2) throw new Error("The Safe's last owner can't be removed.");
      const prev = prevOwner(owners, owner);
      const t = threshold(input.threshold, n - 1);
      keepsQuorum(t, n - 1);
      return { call: self(encodeFunctionData({ abi: OWNER_ABI, functionName: "removeOwner", args: [prev, owner, BigInt(t)] })),
               title: `Remove owner, ${t} of ${n - 1}`, red: true, warnings };
    }
    case "swap": {
      const old = addr(input.old, "Owner to replace");
      const owner = addr(input.owner, "New owner");
      if (owners.includes(owner)) throw new Error("The new owner is already an owner.");
      if (owner === safe) throw new Error("A Safe can't own itself.");
      const prev = prevOwner(owners, old);
      return { call: self(encodeFunctionData({ abi: OWNER_ABI, functionName: "swapOwner", args: [prev, old, owner] })),
               title: "Replace owner", red: true, warnings };
    }
    case "threshold": {
      const t = threshold(input.threshold, n);
      if (t === s.threshold) throw new Error(`The Safe already needs ${t}.`);
      keepsQuorum(t, n);
      return { call: self(encodeFunctionData({ abi: OWNER_ABI, functionName: "changeThreshold", args: [BigInt(t)] })),
               title: `Approvals needed: ${t} of ${n}`, red: true, warnings };
    }
    case "reject":
      return { call: self("0x"), title: "Rejection", warnings };
    case "custom": {
      const to = addr(input.to, "Contract");
      const value = String(input.amount || "").trim() ? amount(input.amount, 18, "ETH sent with it") : 0n;
      const data = String(input.data || "").trim() || "0x";
      if (!isHex(data, { strict: true }) || data.length % 2) throw new Error("Data: hex starting with 0x, two characters a byte.");
      if (size(data) > 0 && size(data) < 4) throw new Error("Data: a call starts with a 4-byte selector.");
      if (to === safe) warnings.push("The Safe calling itself changes its own settings. Check this is what you mean.");
      warnings.push("The console decodes only calls it knows. Anything else shows as an unknown contract call, in amber.");
      return { call: { to, value, data, operation: 0 }, title: "Contract call", warnings };
    }
  }
  throw new Error(`Unknown kind ${kind}`);
}

// The SafeTx a call becomes at a nonce: no refund, no gas fields.
export const safeTx = (call, nonce) => ({ ...call, value: String(call.value), safeTxGas: "0", baseGas: "0", gasPrice: "0", gasToken: ZERO,
  refundReceiver: ZERO, nonce: Number(nonce) });

// eth_signTypedData_v4's argument: SafeTx under the Safe's domain (Safe ≥ 1.3.0), numbers as decimal strings.
export function typedData(chainId, safe, t) {
  const f = fields(t);
  return {
    domain: { chainId: Number(chainId), verifyingContract: getAddress(safe) },
    types: { EIP712Domain: [{ name: "chainId", type: "uint256" }, { name: "verifyingContract", type: "address" }], ...TYPES },
    primaryType: "SafeTx",
    message: Object.fromEntries(Object.entries(f).map(([k, v]) => [k, typeof v === "bigint" ? v.toString() : v])),
  };
}

// A wallet's 65-byte signature over the hash, with v as the Safe wants it (27 or 28; some wallets
// say 0 or 1), checked to come from `account`. Smart-contract wallets sign differently and are refused.
export async function walletSignature(hash, sig, account) {
  if (!isHex(sig) || size(sig) !== 65) throw new Error("Your wallet returned something that isn't a 65-byte signature. Smart-contract wallets can't sign here yet.");
  let v = Number(BigInt(slice(sig, 64, 65)));
  if (v < 27) v += 27;
  if (v !== 27 && v !== 28) throw new Error(`Your wallet's signature has v = ${v}, which the Safe doesn't take.`);
  const signature = slice(sig, 0, 64) + toHex(v, { size: 1 }).slice(2);
  const signer = await recoverAddress({ hash, signature });
  if (signer !== getAddress(account)) throw new Error(`The signature comes from ${signer}, not your wallet ${getAddress(account)}. Nothing was sent.`);
  return signature;
}

// The body of POST /api/v2/safes/{safe}/multisig-transactions/ (Safe's own schema). Big numbers go
// as decimal strings, as Safe's own SDK sends them.
export function proposalBody(safe, t, hash, sender, signature) {
  const f = fields(t);
  return {
    safe: getAddress(safe), to: f.to, value: f.value.toString(), data: f.data === "0x" ? null : f.data, operation: f.operation,
    safeTxGas: "0", baseGas: "0", gasPrice: "0", gasToken: ZERO, refundReceiver: ZERO, nonce: Number(f.nonce),
    contractTransactionHash: hash, sender: getAddress(sender), signature, origin: t.origin || "PicoQuorum app",
  };
}
