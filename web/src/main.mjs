// The PicoQuorum page: open a Safe, see its owners and queue, check every confirmation, and execute
// with the signatures laid out right. Keys: the registry (docs/registry/keys.json), each bundle checked
// in the browser, and a key's signer deployed from the wallet: your passkey's, or anyone's from a
// deploy link (#/signer/<x>/<y>), from any wallet. Everything is drawn with textContent:
// the queue comes from Safe's service and is untrusted.
import { p256 } from "@noble/curves/p256";
import { encodeFunctionData, getAddress, isAddress } from "viem";
import { verifyBundle } from "./attest.mjs";
import { blockieSrc } from "./blockies.mjs";
import {
  ERC20_ABI, KINDS, buildCall, isRejection, knownTokens, nextNonce, proposalBody, safeTx, typedData, walletSignature,
} from "./propose.mjs";
import {
  CFG, CHAINS, GS, SAFE_ABI, SIGNER_ABI, Service, chainById, checkTx, client, consoleRefuses, dataBytes, eth, execCall, knownName, outcome,
  ownerKind, readSafe, reason, safeTxHash, verifyCode,
} from "./safe.mjs";
import { wallet } from "./wallet.mjs";
import { isApproved } from "../../tools/mock-tx-service/release.mjs";
import { p256Owner } from "../../tools/mock-tx-service/sigs.mjs";

const REPO = "https://github.com/jmcpheron/pico-quorum";
const DEMO = { chain: "basesep", address: "0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43", name: "PicoQuorum test Safe" };

// ----------------------------------------------------------------------------- small things
const store = {
  get(k, d) { try { const v = localStorage.getItem("pq." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("pq." + k, JSON.stringify(v)); } catch {} },
};
const rpcFor = (name) => store.get("rpc", {})[name] || CHAINS[name].rpc;
const pubs = {};
const pubFor = (name) => (pubs[name + rpcFor(name)] ||= client(name, rpcFor(name)));
const serviceFor = (name) => new Service(name, store.get("apiKey", ""));

const keep = (kids) => kids.flat().filter((c) => c != null && c !== false && c !== "");
function fill(el, ...kids) { el.replaceChildren(...keep(kids)); return el; }
function add(el, ...kids) { el.append(...keep(kids)); return el; }

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of keep(kids)) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}
const $main = () => document.getElementById("main");
const short = (a) => `${a.slice(0, 6)}…${a.slice(-4)}`;
const nameOf = (a) => registryNames[a.toLowerCase()] || store.get("names", {})[a.toLowerCase()] ||
  (myPasskey()?.owner.toLowerCase() === a.toLowerCase() ? "Your passkey" : "");
const registryNames = {};

// Saved Safes ({chain, address, name, threshold?, owners?}), the ones opened lately, and the names
// given to owners: all in this browser only, and in the backup file Settings writes.
const sameSafe = (a, b) => a.chain === b.chain && a.address === b.address;
const savedSafes = () => store.get("safes", []);

// Your passkey: made (or found) on the console page or in the emulator, which are this site too, so
// the same localStorage. Only its public key is here; the private key is in Touch ID, Windows Hello,
// a phone or a security key. Its owner address follows from the key, the same on every chain.
let passkeySeen = null;
function myPasskey() {
  let raw = null;
  try { raw = localStorage.getItem("emu.passkey"); } catch {}
  if (passkeySeen?.raw === raw) return passkeySeen.k;
  let k = null;
  try {
    const c = JSON.parse(raw || "null");
    if (c && /^[0-9a-f]{64}$/.test(c.x) && /^[0-9a-f]{64}$/.test(c.y)) k = { ...c, owner: getAddress(p256Owner(CFG.signer, "0x" + c.x, "0x" + c.y)) };
  } catch {}
  passkeySeen = { raw, k };
  return k;
}
const savedSafe = (s) => savedSafes().find((x) => sameSafe(x, s));
function saveSafe(s) {
  const list = savedSafes();
  const i = list.findIndex((x) => sameSafe(x, s));
  if (i >= 0) list[i] = { ...list[i], ...s }; else list.push(s);
  store.set("safes", list);
}
const forgetSafe = (s) => store.set("safes", savedSafes().filter((x) => !sameSafe(x, s)));
function noteRecent(s) {
  store.set("recent", [s, ...store.get("recent", []).filter((x) => !sameSafe(x, s))].slice(0, 6));
}
function nameSafe(s, fallback) {
  const label = prompt("A name for this Safe (only kept in this browser):", savedSafe(s)?.name || fallback);
  if (label == null) return false;
  saveSafe({ ...s, name: label.trim() || fallback });
  return true;
}
function nameOwner(o) {
  const n = prompt("A name for this address (only kept in this browser):", nameOf(o));
  if (n == null) return false;
  const names = store.get("names", {});
  if (n.trim()) names[o.toLowerCase()] = n.trim(); else delete names[o.toLowerCase()];
  store.set("names", names);
  return true;
}

function copyButton(text, label = "Copy") {
  const b = h("button", { class: "mini", type: "button", "aria-label": `${label} ${text}`, text: label });
  b.onclick = async () => {
    try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; } catch { b.textContent = "Couldn't copy"; }
    setTimeout(() => (b.textContent = label), 1400);
  };
  return b;
}
// The share sheet where there is one (a phone: AirDrop, Messages, mail to the computer with the
// wallet), else the clipboard.
function shareButton(url, label, title) {
  const b = h("button", { class: "mini", type: "button", text: label });
  b.onclick = async () => {
    if (navigator.share) {
      try { await navigator.share({ title, url }); return; } catch (e) { if (e?.name === "AbortError") return; }
    }
    try { await navigator.clipboard.writeText(url); b.textContent = "Link copied"; } catch { b.textContent = "Couldn't copy"; }
    setTimeout(() => (b.textContent = label), 1400);
  };
  return b;
}
function explorer(name, kind, x, text = "Explorer") {
  return h("a", { class: "mini", href: `${CHAINS[name].explorer}/${kind}/${x}`, target: "_blank", rel: "noopener", text });
}
const badge = (tone, text, title) => h("span", { class: `badge ${tone}`, title }, text);

// The blockie for an address or a hash (blockies.mjs): the picture the console, Safe{Wallet},
// MetaMask and Etherscan draw for it. Decoration beside the text, so no alt text of its own.
const ident = (x, size = 32) => h("img", { class: "blockie", src: blockieSrc(x), width: size, height: size, alt: "", "aria-hidden": "true" });

// An address as people compare it: its blockie, the name, then the whole address in mono.
function address(name, a, extra = []) {
  const n = nameOf(a);
  return h("div", { class: "addr" }, ident(a, 36),
    h("div", { class: "addr-body" },
      h("div", { class: "addr-top" }, n ? h("strong", { text: n }) : null, ...extra),
      h("div", { class: "addr-line" }, h("code", { class: "mono", text: getAddress(a) }), copyButton(getAddress(a)), explorer(name, "address", a))));
}

function steps() {
  const el = h("div", { class: "steps", role: "status", "aria-live": "polite" });
  return {
    el,
    run(text) { const s = h("div", { class: "step run" }, h("span", { class: "spin", "aria-hidden": "true" }), h("span", { text })); add(el, s); return s; },
    done(s, text, tone = "ok") { s.className = `step ${tone}`; fill(s, h("span", { class: "tick", "aria-hidden": "true", text: tone === "ok" ? "✓" : "!" }), h("span", { text })); },
    add(tone, ...kids) { const s = h("div", { class: `step ${tone}` }, h("span", { class: "tick", "aria-hidden": "true", text: tone === "ok" ? "✓" : tone === "bad" ? "!" : "·" }), h("span", {}, ...kids)); add(el, s); return s; },
  };
}

// A wallet's "no" is an answer, not an error.
const said = (e) => (e?.code === 4001 || /user (rejected|denied)/i.test(e?.message || "") ? "You declined in your wallet. Nothing was sent." : e.shortMessage || e.message || String(e));

function fail(where, e) {
  fill(where, h("section", { class: "card bad-card" }, h("h2", { text: "That didn't work" }), h("p", { text: e.shortMessage || e.message || String(e) })));
}

// ----------------------------------------------------------------------------- the registry
let registryP = null;
function registry() {
  return (registryP ||= (async () => {
    const url = new URL("../registry/keys.json", location.href);
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`the registry: HTTP ${r.status}`);
    const reg = await r.json();
    const out = [];
    for (const k of reg.keys || []) {
      const entry = { ...k, owner: getAddress(k.owner) };
      try {
        const B = await (await fetch(new URL(k.bundle, url), { cache: "no-cache" })).json();
        entry.result = verifyBundle(B, CFG.signer);
        entry.bundleUrl = new URL(k.bundle, url).href;
        entry.verified = entry.result.failed === 0 && entry.result.owner === entry.owner;
        if (entry.result.owner !== entry.owner) entry.why = `the listing says ${entry.owner}, the bundle's key gives ${entry.result.owner}`;
        else if (entry.result.failed) entry.why = `${entry.result.failed} check${entry.result.failed > 1 ? "s" : ""} failed`;
      } catch (e) {
        entry.verified = false;
        entry.why = `the bundle didn't load or parse: ${e.message}`;
      }
      registryNames[entry.owner.toLowerCase()] = entry.name;
      out.push(entry);
    }
    return out;
  })().catch((e) => { registryP = null; throw e; }));
}
const byOwner = async () => Object.fromEntries((await registry().catch(() => [])).map((k) => [k.owner, k]));

function keyBadge(k, kind) {
  if (k?.verified) return badge("ok", `Verified PicoQuorum key · ${k.name}`, "Its attestation bundle passes every check, in this browser");
  if (k) return badge("bad", `Listed key failed its checks · ${k.name}`, k.why);
  if (kind?.kind === "passkey") return badge("muted", `Passkey signer · key ${kind.fingerprint}`, "A Safe passkey signer, not in the PicoQuorum registry");
  if (kind?.kind === "wallet" && kind.delegated) return badge("muted", "Wallet · EIP-7702", `A wallet whose account delegates to ${kind.delegated}. It still signs as a wallet.`);
  if (kind?.kind === "wallet") return badge("muted", "Wallet");
  if (kind?.kind === "contract") return badge("muted", "Contract");
  return null;
}

// ----------------------------------------------------------------------------- header
function renderWallet() {
  const slot = document.getElementById("wallet");
  if (wallet.account) {
    const onChain = Object.values(CHAINS).find((c) => c.id === wallet.chainId);
    fill(slot, h("span", { class: "wallet-on", title: wallet.name },
      ident(wallet.account, 20), short(wallet.account), onChain ? ` · ${onChain.name}` : ` · chain ${wallet.chainId}`));
    return;
  }
  const b = h("button", { class: "btn", type: "button", text: "Connect wallet" });
  b.onclick = () => connect().catch((e) => alert(e.message));
  fill(slot, b);
}
async function connect() {
  const list = wallet.available();
  let id = list[0]?.id;
  if (list.length > 1) {
    const pick = prompt(`Which wallet?\n${list.map((w, i) => `${i + 1}. ${w.name}`).join("\n")}`, "1");
    if (pick == null) throw new Error("No wallet chosen.");
    id = list[Number(pick) - 1]?.id || id;
  }
  return wallet.connect(id);
}
wallet.onChange(renderWallet);

// ----------------------------------------------------------------------------- home
function parseSafe(text, fallbackChain) {
  const t = text.trim();
  const m = t.match(/(?:safe=)?\b(basesep|base|eth):(0x[0-9a-fA-F]{40})\b/);
  if (m) return { chain: m[1], address: getAddress(m[2]) };
  const a = t.match(/0x[0-9a-fA-F]{40}/)?.[0];
  if (a && isAddress(a, { strict: false })) return { chain: fallbackChain, address: getAddress(a) };
  return null;
}

function safeRow(s, saved) {
  const c = CHAINS[s.chain];
  const facts = [c?.name || s.chain, s.threshold ? `${s.threshold} of ${s.owners}` : null].filter(Boolean).join(" · ");
  return h("li", { class: "safe-row" }, ident(s.address, 40),
    h("div", { class: "addr-body" },
      h("a", { href: `#/safe/${s.chain}/${s.address}` }, h("strong", { text: s.name || short(s.address) }), h("span", { class: "muted", text: ` · ${facts}` })),
      h("code", { class: "mono small", text: s.address })),
    h("div", { class: "row tight" }, saved
      ? [h("button", { class: "mini", type: "button", text: "Rename", onclick: () => nameSafe(s, s.name || short(s.address)) && route() }),
         h("button", { class: "mini", type: "button", text: "Remove", onclick: () => confirm(`Remove ${s.name || s.address} from your Safes?`) && (forgetSafe(s), route()) })]
      : h("button", { class: "mini", type: "button", text: "Save", onclick: () => nameSafe(s, short(s.address)) && route() })));
}

function home() {
  const saved = savedSafes();
  const recent = store.get("recent", []).filter((r) => !saved.some((s) => sameSafe(s, r)) && CHAINS[r.chain]).slice(0, 4);
  const chainSel = h("select", { id: "chain", "aria-label": "Network" },
    ...Object.entries(CHAINS).map(([k, c]) => h("option", { value: k, text: c.name })));
  const input = h("input", { id: "safe", type: "text", placeholder: "0x… or basesep:0x…", autocomplete: "off", spellcheck: "false",
    "aria-label": "Safe address" });
  const err = h("p", { class: "bad small", role: "alert" });
  const form = h("form", { class: "open", onsubmit: (e) => {
    e.preventDefault();
    const s = parseSafe(input.value, chainSel.value);
    if (!s) return (err.textContent = "That isn't a Safe address. Paste 0x… (40 hex characters) or a Safe{Wallet} link.");
    location.hash = `#/safe/${s.chain}/${s.address}`;
  } }, h("div", { class: "row" }, chainSel, input, h("button", { class: "btn go", type: "submit", text: "Open" })), err);

  fill($main(), 
    h("section", { class: "hero" },
      h("h1", { text: "Execute what your quorum signed" }),
      h("p", { class: "lede", text: "Open any Safe to see its owners and queue. Every confirmation is checked here, then the signatures are laid out the way the Safe expects and your wallet sends the transaction." }),
      h("p", { class: "muted", text: "Safe{Wallet} can't execute a transaction when a PicoQuorum key is one of two or more confirmations: it fails with GS021. This page can. Nothing here holds a key." })),
    h("section", { class: "card" }, h("h2", { text: "Open a Safe" }), form,
      h("p", { class: "small muted" }, "Or try ",
        h("a", { href: `#/safe/${DEMO.chain}/${DEMO.address}`, text: DEMO.name }), " on Base Sepolia.")),
    saved.length ? h("section", { class: "card" }, h("h2", { text: "Your Safes" }),
      h("ul", { class: "list" }, ...saved.map((s) => safeRow(s, true))),
      h("p", { class: "small muted" }, "Kept in this browser. ", h("a", { href: "#/settings", text: "Back them up" }), " to move them to another.")) : null,
    recent.length ? h("section", { class: "card" }, h("h2", { text: "Opened lately" }),
      h("ul", { class: "list" }, ...recent.map((s) => safeRow(s, false)))) : null,
    h("section", { class: "card quiet" }, h("h2", { text: "What is PicoQuorum?" }),
      h("p", {}, "A hardware approval console for Safe multisig wallets: a Raspberry Pi Pico 2 W with a screen and two buttons, and a sealed Infineon Trust M key that plugs in. It decodes each queued transaction on its own screen, and signs only when you hold Sign."),
      h("p", {}, h("a", { href: "../", text: "About the project" }), " · ", h("a", { href: REPO, text: "Source" }), " · ", h("a", { href: "#/keys", text: "Verified keys" }))),
  );
  input.focus();
}

// ----------------------------------------------------------------------------- a Safe
async function safeView(name, addr) {
  if (!CHAINS[name] || !isAddress(addr, { strict: false })) return notFound();
  const c = CHAINS[name];
  const safe = getAddress(addr);
  const pub = pubFor(name);
  const svc = serviceFor(name);
  const key = { chain: name, address: safe };
  const mine = savedSafe(key);
  const title = mine?.name || (safe === DEMO.address && name === DEMO.chain ? DEMO.name : `Safe ${short(safe)}`);

  const body = h("div", {}, h("p", { class: "muted", text: "Reading the Safe…" }));
  const saveBtn = h("button", { class: "btn", type: "button", text: mine ? "Rename" : "Save to your Safes",
    onclick: () => nameSafe(key, title) && route() });
  const refresh = h("button", { class: "btn", type: "button", text: "Refresh", onclick: () => route() });
  fill($main(), 
    h("section", { class: "safe-head" },
      h("div", { class: "safe-title" }, ident(safe, 56),
        h("div", {}, h("h1", { text: title }),
          h("div", { class: "chips" }, badge(c.test ? "warn" : "eth", c.test ? `${c.name} · testnet` : `${c.name} · mainnet`),
            mine ? badge("muted", "Saved") : null))),
      h("div", { class: "row" }, h("a", { class: "btn go", href: `#/safe/${name}/${safe}/new`, text: "New transaction" }), saveBtn, copyButton(location.href, "Copy link"), refresh,
        h("a", { class: "btn", href: `https://app.safe.global/transactions/queue?safe=${name}:${safe}`, target: "_blank", rel: "noopener", text: "Safe{Wallet}" }))),
    h("div", { class: "addr-line big" }, h("code", { class: "mono", text: safe }), copyButton(safe), explorer(name, "address", safe)),
    body);

  try {
    const [onchain, info, keys] = await Promise.all([readSafe(pub, safe), svc.info(safe).catch((e) => ({ error: e })), byOwner()]);
    if (onchain.missing) throw new Error(`There's no contract at ${safe} on ${c.name}. Check the network.`);
    const facts = { threshold: onchain.threshold, owners: onchain.owners.length };
    noteRecent({ ...key, ...facts });
    if (mine) saveSafe({ ...key, ...facts });
    const kinds = await Promise.all(onchain.owners.map((o) => ownerKind(pub, o)));
    const pk = myPasskey();
    const summary = h("p", { class: "summary" },
      h("strong", { text: `${onchain.threshold} of ${onchain.owners.length}` }), ` · nonce ${onchain.nonce} · v${onchain.version} · ${eth(onchain.balance)} ETH`);
    const owners = h("section", { class: "card" }, h("h2", { text: "Owners" }),
      h("ul", { class: "owners" }, ...onchain.owners.map((o, i) => {
        // your passkey with no code here yet: its signatures can't be checked on this chain until its signer is deployed
        const bare = pk?.owner === o && kinds[i].kind === "wallet" && !kinds[i].delegated;
        return h("li", {}, address(name, o, [bare ? badge("warn", `Your passkey · signer not deployed on ${c.name}`, "Its signatures can't be checked here until it is") : keyBadge(keys[o], kinds[i])]),
          bare ? h("a", { class: "small", href: `#/signer/${pk.x}/${pk.y}`, text: "Deploy its signer" })
            : keys[o] ? h("a", { class: "small", href: `#/key/${o}`, text: "See its checks" }) : renameLink(o));
      })),
      h("p", { class: "small muted", text: "Read from the Safe itself, not from Safe's service." }));

    const queue = h("section", { class: "card" }, h("h2", { text: "Queue" }));
    if (info?.error) add(queue, h("p", { class: "bad", text: info.error.message }));
    else if (!info) add(queue, h("p", { class: "muted", text: `Safe's transaction service doesn't list this Safe on ${c.name}, so there is no queue to show.` }));
    else {
      const q = await svc.queue(safe, onchain.nonce);
      if (!q?.results?.length) add(queue, h("p", { class: "muted" }, "Nothing waiting. ", h("a", { href: `#/safe/${name}/${safe}/new`, text: "Propose a transaction" }), ", here or in Safe{Wallet}."));
      const rejected = new Set((q?.results || []).filter((t) => isRejection(safe, t)).map((t) => Number(t.nonce)));
      for (const t of q?.results || []) add(queue, await txCard(name, safe, onchain, t, keys, rejected));
    }
    fill(body, summary, owners, queue);
  } catch (e) {
    fail(body, e);
  }
}

function renameLink(o) {
  return h("button", { class: "linkish small", type: "button", text: nameOf(o) ? "Rename" : "Name this owner", onclick: () => nameOwner(o) && route() });
}

function describe(chainId, t) {
  if (t.safe && isRejection(t.safe, t)) return `Rejection of #${t.nonce}`;
  const v = BigInt(t.value);
  const method = t.dataDecoded?.method;
  const to = knownName(chainId, t.to) || nameOf(t.to) || short(getAddress(t.to));
  if (!dataBytes(t.data)) return v ? `Send ${eth(v)} ETH to ${to}` : `Call ${to} with nothing`;
  return `${method ? `${method}` : "Call"} on ${to}${v ? ` with ${eth(v)} ETH` : ""}`;
}

async function txCard(name, safe, onchain, t, keys, rejected = new Set()) {
  const c = CHAINS[name];
  const pub = pubFor(name);
  const card = h("article", { class: "tx" });
  let check;
  try {
    check = await checkTx(pub, c.id, safe, onchain.owners, t);
  } catch (e) {
    add(card, h("p", { class: "bad", text: `Couldn't check #${t.nonce}: ${e.shortMessage || e.message}` }));
    return card;
  }
  const current = Number(t.nonce) === onchain.nonce;
  const refuse = consoleRefuses(c.id, t);
  const enough = check.valid.length >= onchain.threshold;
  add(card, 
    h("header", {},
      h("div", {}, h("div", { class: "muted small", text: `#${t.nonce}${current ? " · next to run" : ` · after #${onchain.nonce}`}` }),
        h("h3", { text: describe(c.id, t) })),
      h("div", { class: "vcode", title: "The console's verify code and picture: the last 8 characters of the transaction's hash, and its blockie" },
        ident(check.hash, 48),
        h("div", {}, h("span", { class: "muted small", text: "Verify code" }), h("code", { text: verifyCode(check.hash) })))),
    h("dl", {},
      h("dt", { text: "To" }), h("dd", { class: "to" }, ident(t.to, 20), h("code", { class: "mono", text: getAddress(t.to) }),
        knownName(c.id, t.to) || nameOf(t.to) ? ` (${knownName(c.id, t.to) || nameOf(t.to)})` : ""),
      h("dt", { text: "Value" }), h("dd", { text: `${eth(t.value)} ETH` }),
      h("dt", { text: "Data" }), h("dd", { text: dataBytes(t.data) ? `${dataBytes(t.data)} bytes${t.dataDecoded?.method ? ` · the service reads it as ${t.dataDecoded.method}` : ""}` : "none" }),
      h("dt", { text: "Operation" }), h("dd", { class: Number(t.operation) === 1 ? "bad" : "", text: Number(t.operation) === 1 ? "delegatecall" : "call" }),
      h("dt", { text: "Hash" }), h("dd", {}, h("code", { class: "mono small", text: check.hash }))),
    refuse ? h("p", { class: "bad", text: refuse }) : null,
    ...check.problems.map((p) => h("p", { class: "bad", text: p })),
    h("h4", { text: `Confirmations · ${check.valid.length} of ${onchain.threshold}` }),
    h("ul", { class: "confs" }, ...check.confirmations.map((x) => h("li", { class: x.ok ? "" : "invalid" },
      h("span", { class: `tick ${x.ok ? "ok" : "bad"}`, "aria-hidden": "true", text: x.ok ? "✓" : "✕" }),
      ident(x.owner, 28),
      h("div", {},
        h("div", { class: "addr-top" }, h("strong", { text: nameOf(x.owner) || short(x.owner) }),
          keyBadge(keys[x.owner]), x.console ? badge("muted", "signed on a console", "The WebAuthn data names PicoQuorum. Anyone can write that; the check is the signature.") : null,
          badge("muted", { ecdsa: "wallet signature", contract: "contract signature", approved: "approved onchain" }[x.kind] || x.kind)),
        h("code", { class: "mono small", text: x.owner }),
        x.ok ? null : h("div", { class: "bad small", text: x.why || "not valid" })))),
      ...(check.confirmations.length ? [] : [h("li", { class: "muted none", text: "No confirmations yet." })])),
  );
  const act = h("div", { class: "act" });
  add(card, act);
  const mine = wallet.account && check.confirmations.some((x) => x.owner === getAddress(wallet.account));
  const extra = [
    !check.problems.length && !enough && !mine ? confirmButton(name, safe, t, check, onchain) : null,
    !isRejection(safe, t) && !rejected.has(Number(t.nonce))
      ? h("a", { class: "mini", href: `#/safe/${name}/${safe}/new/reject/${t.nonce}`, text: "Propose a rejection", title: `A transaction that does nothing at #${t.nonce}. Executed, it cancels this one.` }) : null,
  ];
  if (check.problems.length) add(act, h("p", { class: "bad", text: "Don't execute this one: the hash doesn't check out." }));
  else if (!current) add(act, h("p", { class: "muted", text: `Waits for #${onchain.nonce} to run first.` }));
  else if (!enough) add(act, h("p", { class: "muted", text: `Needs ${onchain.threshold - check.valid.length} more valid confirmation${onchain.threshold - check.valid.length > 1 ? "s" : ""}.` }));
  if (extra.some(Boolean)) add(act, h("div", { class: "row" }, extra[0]?.button, extra[1]), extra[0]?.el);
  if (!check.problems.length && current && enough) {
    const go = h("button", { class: "btn go", type: "button", text: "Execute with wallet" });
    const log = steps();
    go.onclick = () => execute(name, safe, t, check, onchain, go, log).catch((e) => { log.add("bad", said(e)); go.disabled = false; });
    add(act, h("div", { class: "row" }, go, h("span", { class: "small muted", text: `Uses ${onchain.threshold} of the ${check.valid.length} valid confirmations. Your wallet shows it and asks before anything is sent.` })), log.el);
  }
  return card;
}

// Add the connected wallet's confirmation to a queued transaction: it signs the hash this page
// recomputed (check.hash), the signature is checked, then posted to the service.
function confirmButton(name, safe, t, check, onchain) {
  const c = CHAINS[name];
  const log = steps();
  const button = h("button", { class: "btn", type: "button", text: "Confirm with wallet" });
  button.onclick = async () => {
    button.disabled = true;
    fill(log.el);
    try {
      if (!wallet.account) await connect();
      const me = getAddress(wallet.account);
      if (!onchain.owners.includes(me)) { log.add("bad", `Your wallet ${short(me)} isn't an owner of this Safe. Switch to an owner's account.`); button.disabled = false; return; }
      if (check.confirmations.some((x) => x.owner === me)) { log.add("ok", "Your wallet has already confirmed this one."); return; }
      let s = log.run(`Switching your wallet to ${c.name}…`);
      await wallet.ensureChain(c, rpcFor(name));
      log.done(s, `Wallet on ${c.name}`);
      s = log.run(`Waiting for your wallet to sign #${t.nonce}…`);
      const sig = await walletSignature(check.hash, await wallet.signTypedData(typedData(c.id, safe, t)), me);
      log.done(s, `Signed ${verifyCode(check.hash)}, and the signature checks out`);
      s = log.run("Sending it to Safe's transaction service…");
      await serviceFor(name).confirm(check.hash, sig);
      log.done(s, "Confirmed. Reading the queue again…");
      setTimeout(() => route(), 1200);
    } catch (e) { log.add("bad", said(e)); button.disabled = false; }
  };
  return { button, el: log.el };
}

async function execute(name, safe, t, check, onchain, go, log) {
  const c = CHAINS[name];
  const pub = pubFor(name);
  go.disabled = true;
  fill(log.el);
  if (!wallet.account) await connect();
  let s = log.run(`Switching your wallet to ${c.name}…`);
  await wallet.ensureChain(c, rpcFor(name));
  log.done(s, `Wallet on ${c.name}`);

  s = log.run("Checking the Safe hasn't moved on…");
  const now = await readSafe(pub, safe);
  if (now.nonce !== Number(t.nonce)) { log.done(s, `The Safe is at nonce ${now.nonce} now. Refresh.`, "bad"); return; }
  log.done(s, `Still at nonce ${now.nonce}`);

  const call = execCall(t, check.valid, onchain.threshold);
  s = log.run("Running it against the chain first…");
  try {
    await pub.simulateContract({ address: safe, abi: SAFE_ABI, functionName: "execTransaction", args: call.args, account: wallet.account });
  } catch (e) {
    const r = reason(e);
    const code = (r.match(/GS\d{3}/) || [])[0];
    log.done(s, `It would revert: ${r}${code && GS[code] ? ` (${GS[code]})` : ""}`, "bad");
    go.disabled = false;
    return;
  }
  log.done(s, "It runs");
  const gas = await pub.estimateGas({ account: wallet.account, to: safe, data: call.data }).catch(() => null);

  s = log.run("Waiting for your wallet…");
  const hash = await wallet.send({ to: safe, data: call.data, gas: gas ? (gas * 13n) / 10n : null });
  log.done(s, "Sent");
  s = log.run("Waiting for it to land…");
  add(log.el, h("p", { class: "small" }, explorer(name, "tx", hash, "See it on the explorer")));
  const receipt = await pub.waitForTransactionReceipt({ hash });
  const out = outcome(receipt, safe);
  if (out === "success") log.done(s, "Executed. The Safe ran it.");
  else if (out === "failure") log.done(s, "Mined, but the Safe's call failed (ExecutionFailure). The nonce is used.", "bad");
  else log.done(s, `Mined with status ${receipt.status}`, receipt.status === "success" ? "ok" : "bad");
  go.textContent = "Done";
  setTimeout(() => route(), 6000);           // the service takes a moment to see it
}

// ----------------------------------------------------------------------------- propose
// A new transaction for a Safe: pick what it does, review it with its verify code and picture (the
// console shows the same), sign it with the wallet as one owner's confirmation, and post it to Safe's
// transaction service. The wallet must be an owner; the console's owner then approves on its screen.
async function proposeView(name, addr, presetKind, presetNonce) {
  if (!CHAINS[name] || !isAddress(addr, { strict: false })) return notFound();
  const c = CHAINS[name];
  const safe = getAddress(addr);
  const pub = pubFor(name);
  const svc = serviceFor(name);
  const back = `#/safe/${name}/${safe}`;
  const title = savedSafe({ chain: name, address: safe })?.name || (safe === DEMO.address && name === DEMO.chain ? DEMO.name : `Safe ${short(safe)}`);
  const body = h("div", {}, h("p", { class: "muted", text: "Reading the Safe…" }));
  fill($main(),
    h("section", { class: "hero" },
      h("p", { class: "small" }, h("a", { href: back, text: `← ${title}` })),
      h("div", { class: "safe-title" }, ident(safe, 48),
        h("div", {}, h("h1", { text: "New transaction" }),
          h("div", { class: "chips" }, badge(c.test ? "warn" : "eth", c.test ? `${c.name} · testnet` : `${c.name} · mainnet`))))),
    body);
  try {
    const [s, info, keys] = await Promise.all([readSafe(pub, safe), svc.info(safe).catch((e) => ({ error: e })), byOwner()]);
    if (s.missing) throw new Error(`There's no contract at ${safe} on ${c.name}. Check the network.`);
    if (info?.error) throw info.error;
    if (!info) throw new Error(`Safe's transaction service doesn't list this Safe on ${c.name}, so it can't take a proposal.`);
    if (!/^1\.(?:[3-9]|\d\d)\./.test(s.version)) throw new Error(`This Safe is v${s.version}. The console and this page work with Safe 1.3.0 and later.`);
    const queued = (await svc.queue(safe, s.nonce))?.results || [];
    const releases = presetKind === "release" ? await releaseList().catch(() => []) : [];
    proposeForm(body, { name, c, safe, pub, svc, s, queued, keys, back, presetKind, presetNonce, releases });
  } catch (e) { fail(body, e); }
}

function proposeForm(body, { name, c, safe, pub, svc, s, queued, keys, back, presetKind, presetNonce, releases = [] }) {
  const tokens = knownTokens(c.id);
  const vals = { threshold: String(s.threshold), token: tokens[0]?.address || "other",
    // #/safe/<chain>/<safe>/new/add/<owner>: the owner filled in (your passkey's page links here)
    ...(isAddress(presetNonce || "", { strict: false }) ? { owner: getAddress(presetNonce) } : {}) };
  let kind = KINDS.some((k) => k.id === presetKind) ? presetKind : "eth";
  const queuedAt = (n) => queued.filter((t) => Number(t.nonce) === n);
  // A rejection goes where the transaction it cancels waits (the first queued, unless the link said
  // which); anything else after the queue.
  const defaultNonce = () => kind !== "reject" ? nextNonce(s.nonce, queued)
    : /^\d+$/.test(presetNonce || "") ? Number(presetNonce) : queued.length ? Number(queued[0].nonce) : s.nonce;
  const who = (a) => nameOf(a) || keys[a]?.name || "";
  const ownerLabel = (o) => `${who(o) ? who(o) + " · " : ""}${short(o)}`;

  const kinds = h("div", { class: "kinds", role: "radiogroup", "aria-label": "What it does" });
  const fields = h("div", { class: "fields" });
  const review = h("div", {});
  const book = h("datalist", { id: "book" }, ...[...new Set([...s.owners, ...Object.keys(store.get("names", {})).map((a) => getAddress(a))])]
    .map((a) => h("option", { value: a, label: who(a) || short(a) })));
  const stale = () => fill(review);

  const label = (id, text, hint) => [h("label", { for: id, text }), hint ? h("p", { class: "small muted hint", text: hint }) : null];
  const bind = (el, key) => { el.value = vals[key] ?? ""; el.addEventListener("input", () => { vals[key] = el.value; stale(); }); return el; };
  function addressField(key, text, hint) {
    const id = `f-${key}`;
    const pic = h("img", { class: "blockie", width: 28, height: 28, alt: "", "aria-hidden": "true" });
    const note = h("p", { class: "small muted hint" });
    const input = bind(h("input", { type: "text", id, list: "book", autocomplete: "off", spellcheck: "false", placeholder: "0x…", class: "mono-in" }), key);
    const show = () => {
      const v = input.value.trim();
      const ok = isAddress(v, { strict: false });
      pic.src = ok ? blockieSrc(v) : "";
      pic.style.visibility = ok ? "visible" : "hidden";
      const a = ok ? getAddress(v) : null;
      note.textContent = !a ? "" : a === safe ? "This Safe" : [who(a), s.owners.includes(a) ? "an owner" : ""].filter(Boolean).join(" · ") || "Not in your address book";
    };
    input.addEventListener("input", show);
    show();
    return [...label(id, text, hint), h("div", { class: "addr-in" }, pic, input), note];
  }
  function textField(key, text, hint, attrs = {}) {
    const id = `f-${key}`;
    return [...label(id, text, hint), bind(h(attrs.multiline ? "textarea" : "input", { id, autocomplete: "off", spellcheck: "false", ...(attrs.multiline ? { rows: 4 } : { type: "text" }), ...attrs, multiline: null }), key)];
  }
  function pick(key, text, options, hint) {
    const id = `f-${key}`;
    const el = h("select", { id }, ...options.map(([v, t]) => h("option", { value: v, text: t })));
    if (!options.some(([v]) => v === vals[key])) vals[key] = options[0]?.[0];
    return [...label(id, text, hint), bind(el, key)];
  }
  const counts = (max, of) => Array.from({ length: max }, (_, i) => [String(i + 1), `${i + 1} of ${of}`]);
  const n = s.owners.length;

  function drawFields() {
    for (const b of kinds.children) b.setAttribute("aria-checked", String(b.dataset.kind === kind));
    vals.nonce = String(defaultNonce());
    vals.threshold = String({ remove: Math.min(s.threshold, n - 1), threshold: s.threshold === n ? n - 1 : s.threshold + 1 }[kind] ?? s.threshold);
    const owners = s.owners.map((o) => [o, ownerLabel(o)]);
    const per = {
      eth: () => [...addressField("to", "To"), ...textField("amount", "Amount in ETH", `The Safe holds ${eth(s.balance)} ETH.`, { inputmode: "decimal", placeholder: "0.01" })],
      token: () => {
        const tokenRow = pick("token", "Token", [...tokens.map((t) => [t.address, `${t.symbol} · ${short(t.address)}`]), ["other", "Another token…"]]);
        const other = h("div", {}, vals.token === "other" ? addressField("tokenAddress", "Token address", "An ERC-20 on " + c.name + ". Its symbol and decimals are read from the chain.") : null);
        tokenRow.at(-1).addEventListener("change", () => fill(other, vals.token === "other" ? addressField("tokenAddress", "Token address") : null));
        return [...tokenRow, other, ...addressField("to", "To"), ...textField("amount", "Amount", null, { inputmode: "decimal", placeholder: "10" })];
      },
      add: () => [...addressField("owner", "New owner", "A wallet, or a PicoQuorum key's owner address (its key page has it)."),
        ...pick("threshold", "Approvals needed after", counts(n + 1, n + 1))],
      remove: () => [...pick("owner", "Owner to remove", owners), ...pick("threshold", "Approvals needed after", counts(n - 1, n - 1))],
      swap: () => [...pick("old", "Owner to replace", owners), ...addressField("owner", "New owner", "Takes the old owner's place, with the same vote. For a new PicoQuorum key, use its owner address.")],
      threshold: () => [...pick("threshold", "Approvals needed", counts(n, n).filter(([v]) => Number(v) !== s.threshold))],
      reject: () => [h("p", {}, "A transaction that does nothing. Once executed it uses up its nonce, so every other transaction waiting at that nonce can never run. It needs the same approvals as any other.")],
      release: () => {
        const row = pick("release", "Release", releases.map((r) => [r.version, `${r.version} · firmware ${shortFp(r.fingerprints.console)}`]),
          "The Safe approves this release for everyone who runs PicoQuorum. Each owner's console shows its firmware fingerprint before signing.");
        return releases.length ? row : [h("p", { class: "bad", text: "No releases listed (docs/releases/index.json)." })];
      },
      custom: () => [...addressField("to", "Contract"), ...textField("amount", "ETH sent with it", "Optional.", { inputmode: "decimal", placeholder: "0" }),
        ...textField("data", "Data", "The calldata, as hex. A plain call; delegatecalls aren't offered, and the console refuses unpinned ones.", { multiline: true, class: "mono-in", placeholder: "0x…" })],
    };
    const nonceId = "f-nonce";
    const nonceNote = h("p", { class: "small muted hint" });
    const nonceIn = bind(h("input", { type: "number", id: nonceId, min: String(s.nonce), step: "1", inputmode: "numeric" }), "nonce");
    const showNonce = () => {
      const v = Number(nonceIn.value);
      const at = queuedAt(v);
      nonceNote.className = "small hint " + (v < s.nonce ? "bad" : at.length ? "warn-text" : "muted");
      nonceNote.textContent = v < s.nonce ? `#${v} has already run. The Safe is at #${s.nonce}.`
        : at.length ? `#${v} already has ${at.length === 1 ? "a transaction" : `${at.length} transactions`} in the queue. Only one of them can ever run.`
        : v > nextNonce(s.nonce, queued) ? `Waits until every number before it has run.`
        : v === s.nonce ? "Next to run." : `Runs after #${v - 1}.`;
    };
    nonceIn.addEventListener("input", showNonce);
    showNonce();
    fill(fields, ...per[kind](), h("label", { for: nonceId, text: "Nonce" }), nonceIn, nonceNote);
    stale();
  }
  for (const k of KINDS.filter((k) => !k.gov || kind === k.id)) add(kinds, h("button", { type: "button", role: "radio", class: `kind${k.red ? " red" : ""}`, "data-kind": k.id, text: k.label,
    onclick: () => { kind = k.id; drawFields(); } }));

  const err = h("p", { class: "bad small", role: "alert" });
  const go = h("button", { class: "btn", type: "submit", text: "Review" });
  const form = h("form", { class: "propose", onsubmit: async (e) => {
    e.preventDefault();
    err.textContent = "";
    go.disabled = true;
    try { await reviewCard(review, await built()); review.scrollIntoView({ behavior: "smooth", block: "start" }); }
    catch (e2) { err.textContent = e2.shortMessage || e2.message; fill(review); }
    finally { go.disabled = false; }
  } }, fields, h("div", { class: "row" }, go), err);

  async function built() {
    const nonce = Number(vals.nonce);
    if (!Number.isInteger(nonce) || nonce < s.nonce) throw new Error(`Nonce: a whole number from ${s.nonce} up.`);
    let input = { ...vals, releaseEntry: releases.find((r) => r.version === vals.release) };
    if (kind === "token") {
      const token = vals.token === "other" ? vals.tokenAddress : vals.token;
      if (!isAddress(String(token || "").trim(), { strict: false })) throw new Error("Token: pick one, or paste its address.");
      const a = getAddress(token.trim());
      const read = (functionName, args = []) => pub.readContract({ address: a, abi: ERC20_ABI, functionName, args });
      const [decimals, symbol, balance] = await Promise.all([read("decimals"), read("symbol"), read("balanceOf", [safe])])
        .catch(() => { throw new Error(`Token: ${a} doesn't answer as an ERC-20 on ${c.name}.`); });
      const known = tokens.find((t) => t.address === a);
      if (known && known.decimals !== Number(decimals)) throw new Error(`Token: the chain says ${decimals} decimals, the console's list says ${known.decimals}. Stop and find out why.`);
      input = { ...input, token: a, decimals: Number(decimals), symbol: known?.symbol || String(symbol).slice(0, 12), balance, known: !!known };
    }
    const b = buildCall(kind, input, s);
    const t = safeTx(b.call, nonce);
    return { ...b, t, hash: safeTxHash(c.id, safe, t), replaces: queuedAt(nonce).length };
  }

  async function reviewCard(where, b) {
    const { t, hash } = b;
    const to = getAddress(t.to);
    const log = steps();
    const done = h("div", {});
    const sign = h("button", { class: "btn go", type: "button", text: "Sign and propose" });
    sign.onclick = () => signAndPropose(b, sign, log, done).catch((e) => { log.add("bad", said(e)); sign.disabled = false; });
    const warnings = [...b.warnings, b.replaces ? `#${t.nonce} already has a transaction in the queue. Only one of them can run.` : null].filter(Boolean);
    fill(where, h("section", { class: `card review${b.red ? " red" : ""}` },
      b.red ? h("p", { class: "red-banner", text: "Changes who controls the Safe. The console shows it on a red page." }) : null,
      h("h2", { text: b.title }),
      h("dl", { class: "fieldlist" },
        h("dt", { text: "To" }), h("dd", { class: "to" }, ident(to, 20), h("code", { class: "mono", text: to }),
          to === safe ? " (this Safe)" : knownName(c.id, to) || who(to) ? ` (${knownName(c.id, to) || who(to)})` : ""),
        h("dt", { text: "Value" }), h("dd", { text: `${eth(t.value)} ETH` }),
        h("dt", { text: "Data" }), h("dd", {}, dataBytes(t.data) ? h("code", { class: "mono small", text: t.data }) : "none"),
        h("dt", { text: "Operation" }), h("dd", { text: Number(t.operation) === 1 ? "delegatecall (Safe's SignMessageLib, pinned by the console)" : "call" }),
        ...(b.release ? [h("dt", { text: "Release" }), h("dd", { class: "to" }, ident("0x" + b.release.fingerprints.console, 20),
          h("code", { class: "mono", text: `${b.release.version} · firmware ${shortFp(b.release.fingerprints.console)}` })),
          h("dt", { text: "Digest" }), h("dd", {}, h("code", { class: "mono small", text: b.release.digest }))] : []),
        h("dt", { text: "Nonce" }), h("dd", { text: `#${t.nonce}` })),
      warnings.length ? h("ul", { class: "warns" }, ...warnings.map((w) => h("li", { text: w }))) : null,
      h("div", { class: "verify" }, ident(hash, 56),
        h("div", {}, h("div", { class: "muted small", text: "Verify code" }), h("code", { class: "vbig", text: verifyCode(hash) }),
          h("div", { class: "mono small muted", text: hash }))),
      h("p", { class: "small muted", text: "The console shows this code and picture before it signs. Tell the other owners to check it there." }),
      h("div", { class: "row" }, sign, h("span", { class: "small muted", text: `Your wallet asks you to sign it as one confirmation. Nothing moves until ${s.threshold} owners have approved and someone executes it.` })),
      log.el, done));
  }

  async function signAndPropose(b, sign, log, done) {
    const { t, hash } = b;
    sign.disabled = true;
    fill(log.el);
    fill(done);
    if (!wallet.account) await connect();
    const me = getAddress(wallet.account);
    let st = log.run("Checking your wallet is an owner…");
    const now = await readSafe(pub, safe);
    if (!now.owners.includes(me)) { log.done(st, `Your wallet ${short(me)} isn't an owner of this Safe. Switch your wallet to an owner's account.`, "bad"); sign.disabled = false; return; }
    if (t.nonce < now.nonce) { log.done(st, `#${t.nonce} has already run: the Safe is at #${now.nonce}. Change the nonce.`, "bad"); sign.disabled = false; return; }
    log.done(st, `${who(me) || short(me)} is an owner`);
    st = log.run(`Switching your wallet to ${c.name}…`);
    await wallet.ensureChain(c, rpcFor(name));
    log.done(st, `Wallet on ${c.name}`);
    st = log.run("Waiting for your wallet to sign…");
    const sig = await walletSignature(hash, await wallet.signTypedData(typedData(c.id, safe, t)), me);
    log.done(st, "Signed, and the signature checks out");
    st = log.run("Sending it to Safe's transaction service…");
    await svc.propose(safe, proposalBody(safe, t, hash, me, sig));
    log.done(st, `Proposed as #${t.nonce}`);
    sign.textContent = "Proposed";
    fill(done, h("div", { class: "done" },
      h("p", {}, h("strong", { text: "In the queue. " }), `Ask the other owners to approve it, and to check the verify code ${verifyCode(hash)} on the console.`),
      h("div", { class: "row" }, h("a", { class: "btn go", href: back, text: "See it in the queue" }), copyButton(`${b.title} · #${t.nonce} · verify code ${verifyCode(hash)}`, "Copy the code for the others"))));
  }

  fill(body,
    h("section", { class: "card" }, h("h2", { text: "What it does" }), kinds, book, form,
      h("p", { class: "small muted", text: `${s.threshold} of ${n} · the Safe is at #${s.nonce}${queued.length ? ` · ${queued.length} queued` : ""}. Your wallet signs as one owner.` })),
    review);
  drawFields();
}

// ----------------------------------------------------------------------------- keys
async function keysView() {
  const list = h("div", {}, h("p", { class: "muted", text: "Checking every bundle in your browser…" }));
  const file = h("input", { type: "file", accept: ".json,application/json", id: "bundle", class: "visually-hidden" });
  const checkOut = h("div", {});
  file.onchange = async () => {
    try {
      const B = JSON.parse(await file.files[0].text());
      fill(checkOut, resultCard(verifyBundle(B, CFG.signer), file.files[0].name));
    } catch (e) { fail(checkOut, e); }
  };
  fill($main(), 
    h("section", { class: "hero" }, h("h1", { text: "PicoQuorum keys" }),
      h("p", { class: "lede", text: "Each key here has an attestation bundle: what the chip says about itself, signed with Infineon's factory key. This page checks every bundle when it loads, with the same checks as tools/quorum verify." }),
      h("p", { class: "muted" }, "A badge says a genuine Trust M holds the key and the owner address follows from it. It doesn't say who holds the chip; that's the Safe's threshold. ",
        h("a", { href: `${REPO}/blob/main/docs/registry/README.md`, text: "Add your key" }), ".")),
    h("section", { class: "card" }, h("h2", { text: "Registry" }), list),
    h("section", { class: "card" }, h("h2", { text: "Your passkey" }), myPasskey()
      ? h("p", { class: "inline-ident" }, ident(myPasskey().owner, 20), h("code", { class: "mono", text: myPasskey().owner }), " · ",
          h("a", { href: "#/passkey", text: "deploy its signer, add it to a Safe" }))
      : h("p", { class: "muted" }, "No key needs to be a chip: ", h("a", { href: "../console/", text: "the console in your browser" }),
          " signs with a passkey (Touch ID, Windows Hello, a phone, a security key). Make one there, and its page here adds it to a Safe.")),
    h("section", { class: "card" }, h("h2", { text: "Someone's passkey signer" }),
      h("p", { class: "muted" }, "A passkey owner's signer has to be deployed on a chain before its signatures count there. Any wallet can do it, owner of the Safe or not. ",
        h("a", { href: "#/signer", text: "Deploy one from a deploy link" }), ".")),
    h("section", { class: "card" }, h("h2", { text: "Check a bundle" }),
      h("p", { class: "muted", text: "Pick an attest-<serial>.json from tools/fw attest. It's checked here; nothing leaves your browser." }),
      h("label", { class: "btn", for: "bundle", text: "Choose a bundle…" }), file, checkOut));
  try {
    const reg = await registry();
    fill(list, h("ul", { class: "owners" }, ...reg.map((k) => h("li", { class: "with-ident" }, ident(k.owner, 36),
      h("div", { class: "addr-body" },
        h("div", { class: "addr-top" }, h("strong", { text: k.name }), keyBadge(k), k.holder ? h("span", { class: "muted small", text: `held by ${k.holder}` }) : null),
        h("code", { class: "mono", text: k.owner }),
        h("div", { class: "small" }, h("a", { href: `#/key/${k.owner}`, text: "Checks, and add it to a Safe" }), k.why ? h("span", { class: "bad", text: ` · ${k.why}` }) : null))))));
  } catch (e) { fail(list, e); }
}

function resultCard(r, label) {
  return h("div", { class: "result" },
    h("p", {}, h("strong", { text: label }), " · ", r.failed ? badge("bad", `${r.failed} failed`) : badge("ok", "every check passes")),
    r.owner ? h("p", { class: "inline-ident" }, "Owner address ", ident(r.owner, 20), h("code", { class: "mono", text: r.owner }), " ", copyButton(r.owner)) : null,
    h("ul", { class: "checks" }, ...r.rows.map((x) => h("li", { class: x.ok === false ? "invalid" : "" },
      h("span", { class: `tick ${x.ok === true ? "ok" : x.ok === false ? "bad" : "note"}`, "aria-hidden": "true", text: x.ok === true ? "✓" : x.ok === false ? "✕" : "·" }),
      h("div", {}, h("div", { text: x.what }), x.detail ? h("div", { class: "muted small mono-ish", text: x.detail }) : null)))));
}

async function keyView(owner) {
  if (!isAddress(owner, { strict: false })) return notFound();
  const o = getAddress(owner);
  const out = h("div", {}, h("p", { class: "muted", text: "Checking…" }));
  fill($main(), out);
  try {
    const k = (await byOwner())[o];
    if (!k) throw new Error(`${o} isn't in the registry.`);
    const deploy = h("div", {});
    fill(out, 
      h("section", { class: "hero" }, h("div", { class: "safe-title" }, ident(o, 56), h("div", {}, h("h1", { text: k.name }), h("div", { class: "chips" }, keyBadge(k)))),
        k.note ? h("p", { class: "muted", text: k.note }) : null,
        h("p", {}, "Bundle: ", h("a", { href: k.bundleUrl, text: k.bundle.split("/").pop() }), k.holder ? ` · held by ${k.holder}` : "")),
      h("section", { class: "card" }, h("h2", { text: "The checks" }), k.result ? resultCard(k.result, `Trust M ${k.serial}`) : h("p", { class: "bad", text: k.why })),
      h("section", { class: "card" }, h("h2", { text: "Add this key to a Safe" }),
        h("p", { class: "inline-ident" }, "Its owner address is the same on every chain: ", ident(o, 20), h("code", { class: "mono", text: o }), " ", copyButton(o)),
        h("ol", { class: "how" },
          h("li", {}, "Deploy its signer on the chain you use (once per chain). Anyone can, and it moves no funds."),
          h("li", {}, "In Safe{Wallet}, add that address as an owner, and keep the threshold at 2 or more."),
          h("li", {}, "Point the console at the Safe. When a transaction it signed is ready, execute it here.")),
        deploy));
    if (k.result) await deployRows(deploy, k.result, o);
  } catch (e) { fail(out, e); }
}

async function deployRows(where, r, owner) {
  const qx = r.qx, qy = r.qy;
  const rows = await Promise.all(Object.entries(CHAINS).map(async ([name, c]) => {
    const pub = pubFor(name);
    try {
      const got = getAddress(await pub.readContract({ address: CFG.signer.factory, abi: SIGNER_ABI, functionName: "getSigner", args: [qx, qy, BigInt(CFG.signer.verifiers)] }));
      if (got !== owner) return h("li", { class: "bad", text: `${c.name}: the factory says ${got}, not ${owner}. Stop and find out why.` });
      const code = await pub.getCode({ address: owner });
      if (code) return h("li", {}, badge("ok", "deployed"), ` ${c.name} `, explorer(name, "address", owner));
      const b = h("button", { class: "btn", type: "button", text: `Deploy on ${c.name}` });
      const log = steps();
      b.onclick = async () => {
        b.disabled = true;
        try {
          if (!wallet.account) await connect();
          await wallet.ensureChain(c, rpcFor(name));
          const data = encodeFunctionData({ abi: SIGNER_ABI, functionName: "createSigner", args: [qx, qy, BigInt(CFG.signer.verifiers)] });
          const s = log.run("Waiting for your wallet…");
          const hash = await wallet.send({ to: CFG.signer.factory, data });
          log.done(s, "Sent");
          const s2 = log.run("Waiting for it to land…");
          const rc = await pub.waitForTransactionReceipt({ hash });
          log.done(s2, rc.status === "success" ? "Deployed" : "Reverted", rc.status === "success" ? "ok" : "bad");
        } catch (e) { log.add("bad", e.shortMessage || e.message); b.disabled = false; }
      };
      return h("li", {}, badge("muted", "not deployed"), ` ${c.name} `, b, log.el);
    } catch (e) {
      return h("li", { class: "muted", text: `${c.name}: couldn't read the chain (${e.shortMessage || e.message})` });
    }
  }));
  fill(where, h("h3", { text: "Its signer, chain by chain" }), h("ul", { class: "chains" }, ...rows));
}

// ----------------------------------------------------------------------------- your passkey
function passkeyView() {
  const k = myPasskey();
  if (!k) {
    return fill($main(), h("section", { class: "hero" }, h("h1", { text: "Your passkey" }),
      h("p", { class: "lede", text: "There's no passkey in this browser yet. Make one on the console page: Touch ID, Windows Hello, your phone or a security key. Made one already, in another browser or on your other device? Choose “I already have one” there." }),
      h("p", {}, h("a", { class: "btn go", href: "../console/", text: "Open the console" }))));
  }
  const deploy = h("div", {});
  const safes = savedSafes().filter((s) => CHAINS[s.chain]);
  const where = k.synced ? "synced by your account: every device signed in to it holds this key (iCloud Keychain, Google Password Manager…)"
    : k.attachment === "security-key" ? "on a security key: only that key holds it" : "kept on the device that made it";
  fill($main(),
    h("section", { class: "hero" },
      h("div", { class: "safe-title" }, ident(k.owner, 56), h("div", {}, h("h1", { text: "Your passkey" }),
        h("div", { class: "chips" }, badge(k.synced ? "warn" : "ok", k.synced ? "synced" : "one device"), badge("muted", `key ${k.x.slice(0, 8)}`)))),
      h("p", { class: "muted" }, `For ${k.rpId}, ${where}. `, k.found ? "Found here from its signatures; the same key as wherever it was made. " : "",
        "Only its public key is in this browser.")),
    h("section", { class: "card" }, h("h2", { text: "Add it to a Safe" }),
      h("p", { class: "inline-ident" }, "Its owner address is the same on every chain: ", ident(k.owner, 20), h("code", { class: "mono", text: k.owner }), " ", copyButton(k.owner)),
      h("ol", { class: "how" },
        h("li", {}, "Deploy its signer on the chain you use (once per chain). Anyone can, and it moves no funds. Your wallet pays the gas. No wallet on this device? ",
          shareButton(signerLink(k.x, k.y), "Share the deploy link", "Deploy my passkey's signer"), " and open it where MetaMask or Rabby is: any wallet can deploy it."),
        h("li", {}, "Propose adding it as an owner. The Safe's owners approve that as any transaction; keep the threshold at 2 or more.",
          safes.length
            ? h("ul", { class: "add-to" }, ...safes.map((s) => h("li", {},
                h("a", { href: `#/safe/${s.chain}/${getAddress(s.address)}/new/add/${k.owner}`, text: `Add to ${s.name || short(s.address)} (${CHAINS[s.chain].name})` }))))
            : h("p", { class: "small muted" }, "No saved Safes. ", h("a", { href: "#/", text: "Open a Safe" }), " and save it first.")),
        h("li", {}, "Then sign on ", h("a", { href: "../console/", text: "the console page" }), ": it shows each transaction, and Touch ID or Face ID approves what it shows.")),
      deploy),
    h("section", { class: "card" }, h("h2", { text: "Before it holds anything" }),
      h("ul", {},
        h("li", { text: "Count it as one owner, however many devices hold it. A synced passkey is as safe as the account that syncs it." }),
        h("li", { text: "Keep passkey owners below the Safe's threshold, and the owners on different kinds of key: a console's chip, a hardware wallet, a security key." }),
        h("li", { text: `It signs only on ${k.rpId}. If the console moves to another domain, this passkey can't sign there.` }),
        h("li", { text: "Touch ID and Face ID don't show the transaction. What you approve is the console's screen, which your browser draws." }))));
  deployRows(deploy, { qx: BigInt("0x" + k.x), qy: BigInt("0x" + k.y) }, k.owner);
}

// ----------------------------------------------------------------------------- anyone's passkey signer
// The owner address is a hash of the passkey's public key, so the address alone deploys nothing: a
// deploy link carries the key (x, y), and the page works the address out again to show what it
// deploys. createSigner is open to anyone, so the wallet here needn't own the Safe; it pays the gas.
const signerLink = (x, y) => new URL(`#/signer/${x}/${y}`, location.href.split("#")[0]).href;
const onCurve = (x, y) => { try { p256.ProjectivePoint.fromHex("04" + x + y).assertValidity(); return true; } catch { return false; } };

/** A deploy link, the key as x and y, or an uncompressed public key (04 x y) -> {x, y}, lowercase hex. */
function parseKey(text) {
  const t = String(text || "").trim();
  const link = t.match(/#\/signer\/([0-9a-fA-F]{64})\/([0-9a-fA-F]{64})\b/);
  if (link) return { x: link[1].toLowerCase(), y: link[2].toLowerCase() };
  const hexes = (t.match(/(?:0x)?[0-9a-fA-F]+/g) || []).map((x) => x.replace(/^0x/, "").toLowerCase());
  if (hexes.length === 2 && hexes.every((x) => x.length === 64)) return { x: hexes[0], y: hexes[1] };
  if (hexes.length === 1 && /^04[0-9a-f]{128}$/.test(hexes[0])) return { x: hexes[0].slice(2, 66), y: hexes[0].slice(66) };
  return null;
}

function signerForm() {
  const input = h("textarea", { id: "signer-key", rows: 3, spellcheck: "false", placeholder: "https://…/app/#/signer/…  or the key's x and y" });
  const why = h("p", { class: "bad", role: "alert" });
  const go = () => {
    const t = input.value.trim();
    const k = parseKey(t);
    if (k) return onCurve(k.x, k.y) ? (location.hash = `#/signer/${k.x}/${k.y}`) : (why.textContent = "That isn't a P-256 public key. Check it was copied whole.");
    if (isAddress(t, { strict: false })) {
      const pk = myPasskey();
      if (pk?.owner === getAddress(t)) return (location.hash = `#/signer/${pk.x}/${pk.y}`);
      why.textContent = "An owner address is a hash of the passkey's key, so it can't be deployed from the address alone. On the device with the passkey, open the console page (or Your passkey here) and share its deploy link.";
      return;
    }
    why.textContent = "Paste a deploy link, or the key's x and y (64 hex digits each).";
  };
  fill($main(),
    h("section", { class: "hero" }, h("h1", { text: "Deploy a passkey's signer" }),
      h("p", { class: "lede", text: "A passkey owns a Safe through a small signer contract. Until it's deployed on a chain, its signatures can't be checked there, and Safe's service refuses them. Any wallet can deploy it: it doesn't have to own the Safe, it moves no funds, it only pays the gas." })),
    h("section", { class: "card" }, h("h2", { text: "The passkey" }),
      h("p", { class: "muted", text: "Its deploy link, from the console page or Your passkey on the device that holds it (Share the deploy link)." }),
      input, h("div", { class: "row" }, h("button", { class: "btn go", type: "button", text: "Show its signer", onclick: go })), why,
      myPasskey() ? h("p", { class: "small muted" }, "Your own passkey: ", h("a", { href: "#/passkey", text: "Your passkey" }), ".") : null));
}

function signerView(x, y) {
  const k = parseKey(`#/signer/${x}/${y}`);
  if (!k || !onCurve(k.x, k.y)) {
    return fill($main(), h("section", { class: "hero" }, h("h1", { text: "That isn't a passkey's key" }),
      h("p", { class: "lede", text: "The link should end in two 64-digit hex numbers, the passkey's public key. Copy it again from the device that holds the passkey." }),
      h("p", {}, h("a", { href: "#/signer", text: "Paste a deploy link" }))));
  }
  const owner = getAddress(p256Owner(CFG.signer, "0x" + k.x, "0x" + k.y));
  const mine = myPasskey()?.owner === owner;
  const deploy = h("div", {});
  fill($main(),
    h("section", { class: "hero" },
      h("div", { class: "safe-title" }, ident(owner, 56), h("div", {}, h("h1", { text: mine ? "Your passkey's signer" : "A passkey's signer" }),
        h("div", { class: "chips" }, mine ? badge("ok", "Your passkey") : null, nameOf(owner) && !mine ? badge("muted", nameOf(owner)) : null, badge("muted", `key ${k.x.slice(0, 8)}`)))),
      h("p", { class: "muted" }, "Deploying it lets this passkey's signatures count on that chain. Any wallet can send it: yours needn't own the Safe, and it moves no funds; it pays the gas. No wallet here? ",
        shareButton(location.href, "Share this link", "Deploy a passkey's signer"), " and open it where MetaMask or Rabby is.")),
    h("section", { class: "card" }, h("h2", { text: "What it deploys" }),
      h("p", { class: "inline-ident" }, "The owner address, the same on every chain: ", ident(owner, 20), h("code", { class: "mono", text: owner }), " ", copyButton(owner)),
      h("p", { class: "small muted" }, "Check it is the address the console page shows under Owner, and the one in the Safe. It's worked out here from the key and Safe's passkey factory; each chain's factory must name the same address before the button sends anything."),
      deploy,
      h("details", { class: "small" }, h("summary", { text: "The key" }),
        h("p", {}, "x ", h("code", { class: "mono", text: "0x" + k.x })), h("p", {}, "y ", h("code", { class: "mono", text: "0x" + k.y })),
        h("p", { class: "muted" }, "Sent to the factory as createSigner(x, y, ", h("code", { class: "mono", text: CFG.signer.verifiers }), ") at ",
          h("code", { class: "mono", text: CFG.signer.factory }), "."))));
  deployRows(deploy, { qx: BigInt("0x" + k.x), qy: BigInt("0x" + k.y) }, owner);
}

// ----------------------------------------------------------------------------- settings
// What a backup holds: saved Safes and names. Not the API key or the RPCs, which are this browser's.
const BACKUP = "picoquorum-backup";
function backupFile() {
  const body = { kind: BACKUP, version: 1, safes: savedSafes(), names: store.get("names", {}) };
  const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(body, null, 2) + "\n"], { type: "application/json" })),
    download: `picoquorum-${new Date().toISOString().slice(0, 10)}.json` });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
// Merge a backup in: Safes by chain and address (the file's name wins), names by address. Everything
// is checked, since the file could come from anywhere.
function restore(B) {
  if (B?.kind !== BACKUP || !Array.isArray(B.safes) || typeof B.names !== "object") throw new Error("That isn't a PicoQuorum backup.");
  let safes = 0, names = 0;
  for (const x of B.safes) {
    if (!CHAINS[x?.chain] || !isAddress(String(x.address), { strict: false })) continue;
    const s = { chain: x.chain, address: getAddress(x.address), name: String(x.name || "").slice(0, 80) };
    if (Number.isInteger(x.threshold) && Number.isInteger(x.owners)) Object.assign(s, { threshold: x.threshold, owners: x.owners });
    saveSafe(s); safes++;
  }
  const book = store.get("names", {});
  for (const [a, n] of Object.entries(B.names || {})) {
    if (!isAddress(a, { strict: false }) || typeof n !== "string" || !n.trim()) continue;
    book[a.toLowerCase()] = n.trim().slice(0, 80); names++;
  }
  store.set("names", book);
  return `Added ${safes} Safe${safes === 1 ? "" : "s"} and ${names} name${names === 1 ? "" : "s"}.`;
}

function settingsView() {
  const key = h("input", { type: "password", id: "apikey", value: store.get("apiKey", ""), autocomplete: "off", placeholder: "Optional" });
  const rpcs = store.get("rpc", {});
  const rpcInputs = Object.entries(CHAINS).map(([name, c]) => [name, h("input", { type: "url", id: `rpc-${name}`, value: rpcs[name] || "", placeholder: c.rpc })]);
  const saved = h("p", { class: "small muted", role: "status" });
  const book = Object.entries(store.get("names", {}));
  const restored = h("p", { class: "small", role: "status" });
  const file = h("input", { type: "file", accept: ".json,application/json", id: "backup", class: "visually-hidden" });
  file.onchange = async () => {
    try { restored.className = "small"; restored.textContent = restore(JSON.parse(await file.files[0].text())); setTimeout(route, 1600); }
    catch (e) { restored.className = "small bad"; restored.textContent = e.message; }
  };
  fill($main(), 
    h("section", { class: "hero" }, h("h1", { text: "Settings" }), h("p", { class: "muted", text: "Kept in this browser only. Nothing here is sent anywhere except to the service or RPC it's for." })),
    h("section", { class: "card" }, h("h2", { text: "Address book" }),
      h("p", { class: "muted", text: "The names you've given owners. Keys in the registry are named for you." }),
      book.length
        ? h("ul", { class: "list" }, ...book.map(([a, n]) => h("li", { class: "safe-row" }, ident(a, 32),
            h("div", { class: "addr-body" }, h("strong", { text: n }), h("code", { class: "mono small", text: getAddress(a) })),
            h("div", { class: "row tight" },
              h("button", { class: "mini", type: "button", text: "Rename", onclick: () => nameOwner(a) && route() }),
              h("button", { class: "mini", type: "button", text: "Remove", onclick: () => {
                const names = store.get("names", {}); delete names[a]; store.set("names", names); route();
              } })))))
        : h("p", { class: "small muted", text: "No names yet. Name an owner from a Safe's page." })),
    h("section", { class: "card" }, h("h2", { text: "Back up and restore" }),
      h("p", {}, `Your ${savedSafes().length} saved Safe${savedSafes().length === 1 ? "" : "s"} and ${book.length} name${book.length === 1 ? "" : "s"}, as a file. Restoring adds to what's here. The API key and RPCs stay out of it.`),
      h("div", { class: "row" },
        h("button", { class: "btn", type: "button", text: "Download a backup", onclick: backupFile }),
        h("label", { class: "btn", for: "backup", text: "Restore from a file…" }), file), restored),
    h("section", { class: "card" }, h("h2", { text: "Safe API key" }),
      h("p", {}, "Safe's transaction service allows a few requests without a key. With your own from ", h("a", { href: "https://developer.safe.global", target: "_blank", rel: "noopener", text: "developer.safe.global" }), ", it allows plenty. It's sent to api.safe.global and nowhere else."),
      h("label", { for: "apikey", text: "API key" }), key),
    h("section", { class: "card" }, h("h2", { text: "RPC endpoints" }),
      h("p", { class: "muted", text: "Owners, threshold, nonce and every signature check are read through these. Leave blank for the public endpoint." }),
      ...rpcInputs.flatMap(([name, el]) => [h("label", { for: el.id, text: CHAINS[name].name }), el])),
    h("div", { class: "row" },
      h("button", { class: "btn go", type: "button", text: "Save", onclick: () => {
        store.set("apiKey", key.value.trim());
        store.set("rpc", Object.fromEntries(rpcInputs.map(([n, el]) => [n, el.value.trim()]).filter(([, v]) => /^https:\/\//.test(v))));
        saved.textContent = "Saved.";
      } }),
      h("button", { class: "btn", type: "button", text: "Forget everything", onclick: () => {
        if (!confirm("Forget your saved and recent Safes, names, API key and RPCs in this browser?")) return;
        for (const k of ["safes", "recent", "names", "apiKey", "rpc"]) try { localStorage.removeItem("pq." + k); } catch {}
        route();
      } })), saved);
}

// ----------------------------------------------------------------------------- releases
// docs/releases/index.json (tools/release manifest): each release's fingerprint, the SHA-256 of an
// image's source files (tools/releases/fingerprint.mjs). A console shows the same blockie and first 8
// hex digits on its Device screen, so a person can check which release their console runs.
const shortFp = (fp) => `${fp.slice(0, 4)}·${fp.slice(4, 8)}`;
let releasesP = null;
function releaseList() {
  return (releasesP ||= (async () => {
    const r = await fetch(new URL("../releases/index.json", location.href), { cache: "no-cache" });
    if (!r.ok) throw new Error(`the release list: HTTP ${r.status}`);
    return (await r.json()).releases || [];
  })());
}
// The project Safe (firmware/quorum_cfg.py "project"; docs/GOVERNANCE.md): a release it approved has
// isValidSignature(digest, "0x") == 0x1626ba7e there, for good (Safe's SignMessageLib).
const PROJECT = CFG.project && CFG.project.address ? { ...CFG.project, name: chainById(CFG.project.chainId) } : null;
async function approvalBadge(rel) {
  if (!PROJECT || !rel.digest) return null;
  try {
    const ok = await isApproved(pubFor(PROJECT.name), PROJECT.address, rel.digest);
    return ok ? badge("ok", "Approved by the project Safe", `isValidSignature(${rel.digest}, 0x) on ${PROJECT.address}`)
      : h("span", {}, badge("warn", "Not approved yet"), " ", h("a", { class: "small", href: `#/safe/${PROJECT.name}/${PROJECT.address}/new/release`, text: "Propose approval" }));
  } catch { return badge("warn", "Approval not checked"); }
}
// Which release this page is: its BUILD.json's SHA-256 is a release's manifest web hash (index.json
// "web.app"). Information, not proof: a compromised site could fake this too. The proof is checked
// from outside the site (tools/release check-site, .github/workflows/site-check.yml).
async function thisPage(rel) {
  try {
    const b = await (await fetch(new URL("BUILD.json", location.href), { cache: "no-cache" })).arrayBuffer();
    const h = [...new Uint8Array(await crypto.subtle.digest("SHA-256", b))].map((x) => x.toString(16).padStart(2, "0")).join("");
    return { hash: h, release: rel.find((r) => (r.web || {}).app === h) || null };
  } catch { return null; }
}
async function releasesView() {
  const list = h("div", {}, h("p", { class: "muted", text: "Loading the release list…" }));
  const find = h("input", { type: "text", id: "fp", class: "mono", placeholder: "4c86·c754", autocomplete: "off", spellcheck: "false", "aria-describedby": "fp-help" });
  const found = h("p", { role: "status" });
  const here = h("div", {}, h("p", { class: "muted", text: "Checking which build this page is…" }));
  fill($main(),
    h("section", { class: "hero" }, h("h1", { text: "Releases" }),
      h("p", { class: "lede", text: "Each firmware release has a fingerprint: a SHA-256 of the console's source files. Your console shows its blockie and first eight digits on the Device screen (on the home grid, press X)." }),
      h("p", { class: "muted" }, "The fingerprint is taken over the source, so a Pico and ", h("a", { href: "../console/", text: "the console in your browser" }), " running the same release show the same picture. One that matches no release here is a development build, or firmware that isn't ours."),
      h("p", { class: "muted" }, PROJECT ? `A release the project Safe approved says so: its owners approved it on their consoles, and the chain keeps it (${short(PROJECT.address)} on ${CHAINS[PROJECT.name]?.name || PROJECT.chainId}).`
        : "Releases will also be approved on chain by the project Safe, once it exists (docs/GOVERNANCE.md).")),
    h("section", { class: "card" }, h("h2", { text: "Which release is my console running?" }),
      h("label", { for: "fp", text: "The eight digits under Release on its Device screen" }), find,
      h("p", { id: "fp-help", class: "muted small", text: "Spaces and the middle dot don't matter." }), found),
    h("section", { class: "card" }, h("h2", { text: "This page" }), here),
    h("section", { class: "card" }, h("h2", { text: "All releases" }), list));
  try {
    const rel = await releaseList();
    thisPage(rel).then(async (p) => {
      if (!p) return fill(here, h("p", { class: "muted", text: "Couldn't read this page's BUILD.json." }));
      const status = p.release ? await approvalBadge(p.release) : null;
      fill(here,
        h("p", {}, p.release ? h("strong", { text: `This page is release ${p.release.version}. ` }) : h("strong", { text: "This page is a development build, not a release. " }), status),
        h("p", { class: "small muted" }, `Its BUILD.json hashes to ${p.hash.slice(0, 12)}…. A page can't vouch for itself, so the live site is also checked from outside, after every deploy (`,
          h("a", { href: `${REPO}/blob/main/docs/GOVERNANCE.md`, text: "how" }), ")."));
    });
    find.oninput = () => {
      const q = find.value.toLowerCase().replace(/[^0-9a-f]/g, "");
      if (q.length < 8) return void fill(found);
      const hits = rel.flatMap((x) => Object.entries(x.fingerprints || {}).filter(([, fp]) => fp.startsWith(q)).map(([img]) => `${x.version} (${img} image)`));
      fill(found, hits.length ? badge("ok", `Release ${hits.join(", ")}`) : badge("bad", "No release has that fingerprint"));
    };
    if (!rel.length) return fill(list, h("p", { class: "muted", text: "No releases recorded yet. The first tagged release (tools/release) adds one." }));
    fill(list, h("ul", { class: "owners" }, ...rel.map((x) => {
      const fp = (x.fingerprints || {}).console || "";
      const status = h("span", {});
      approvalBadge(x).then((b) => b && fill(status, b));
      return h("li", { class: "with-ident" }, fp ? ident("0x" + fp, 36) : null,
        h("div", { class: "addr-body" },
          h("div", { class: "addr-top" }, h("strong", { text: x.version }), fp ? h("code", { class: "mono", text: shortFp(fp) }) : null, status,
            h("span", { class: "muted small", text: [x.date, x.commit && `commit ${x.commit.slice(0, 7)}`].filter(Boolean).join(" · ") })),
          ...Object.entries(x.fingerprints || {}).map(([img, f]) => h("div", { class: "small" }, h("span", { class: "muted", text: `${img} ` }), h("code", { class: "mono", text: f }))),
          x.manifest ? h("div", { class: "small" }, h("a", { href: new URL(`../releases/${x.manifest}`, location.href).href, text: "Manifest" })) : null));
    })));
  } catch (e) { fail(list, e); }
}

function notFound() {
  fill($main(), h("section", { class: "hero" }, h("h1", { text: "Nothing here" }), h("p", {}, h("a", { href: "#/", text: "Back to the start" }))));
}

// ----------------------------------------------------------------------------- routing
function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  for (const a of document.querySelectorAll("nav a")) a.toggleAttribute("aria-current", a.getAttribute("href") === `#/${parts[0] || ""}` || (parts[0] === "safe" && a.getAttribute("href") === "#/"));
  window.scrollTo(0, 0);
  if (!parts.length) return home();
  if (parts[0] === "safe" && parts[3] === "new") return proposeView(parts[1], parts[2], parts[4], parts[5]);
  if (parts[0] === "safe") return safeView(parts[1], parts[2]);
  if (parts[0] === "keys") return keysView();
  if (parts[0] === "key") return keyView(parts[1]);
  if (parts[0] === "passkey") return passkeyView();
  if (parts[0] === "signer") return parts[1] ? signerView(parts[1], parts[2]) : signerForm();
  if (parts[0] === "settings") return settingsView();
  if (parts[0] === "releases") return releasesView();
  return notFound();
}
window.addEventListener("hashchange", route);
renderWallet();
registry().catch(() => {});
route();
