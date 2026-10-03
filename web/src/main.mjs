// The PicoQuorum page: open a Safe, see its owners and queue, check every confirmation, and execute
// with the signatures laid out right. Keys: the registry (docs/registry/keys.json), each bundle checked
// in the browser, and a key's signer deployed from the wallet. Everything is drawn with textContent:
// the queue comes from Safe's service and is untrusted.
import { encodeFunctionData, getAddress, isAddress } from "viem";
import { verifyBundle } from "./attest.mjs";
import {
  CFG, CHAINS, GS, SAFE_ABI, SIGNER_ABI, Service, checkTx, client, consoleRefuses, dataBytes, eth, execCall, knownName, outcome,
  ownerKind, readSafe, reason, verifyCode,
} from "./safe.mjs";
import { wallet } from "./wallet.mjs";

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
const nameOf = (a) => registryNames[a.toLowerCase()] || store.get("names", {})[a.toLowerCase()] || "";
const registryNames = {};

function copyButton(text, label = "Copy") {
  const b = h("button", { class: "mini", type: "button", "aria-label": `${label} ${text}`, text: label });
  b.onclick = async () => {
    try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; } catch { b.textContent = "Couldn't copy"; }
    setTimeout(() => (b.textContent = label), 1400);
  };
  return b;
}
function explorer(name, kind, x, text = "Explorer") {
  return h("a", { class: "mini", href: `${CHAINS[name].explorer}/${kind}/${x}`, target: "_blank", rel: "noopener", text });
}
const badge = (tone, text, title) => h("span", { class: `badge ${tone}`, title }, text);

// An address as people compare it: the name, then the whole address in mono.
function address(name, a, extra = []) {
  const n = nameOf(a);
  return h("div", { class: "addr" },
    h("div", { class: "addr-top" }, n ? h("strong", { text: n }) : null, ...extra),
    h("div", { class: "addr-line" }, h("code", { class: "mono", text: getAddress(a) }), copyButton(getAddress(a)), explorer(name, "address", a)));
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
      h("span", { class: "dot", "aria-hidden": "true" }), short(wallet.account), onChain ? ` · ${onChain.name}` : ` · chain ${wallet.chainId}`));
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

function home() {
  const saved = store.get("safes", []);
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
      h("ul", { class: "list" }, ...saved.map((s) => h("li", {},
        h("a", { href: `#/safe/${s.chain}/${s.address}` }, h("strong", { text: s.name || short(s.address) }),
          h("span", { class: "muted", text: ` · ${CHAINS[s.chain]?.name || s.chain}` })),
        h("code", { class: "mono small", text: s.address }))))) : null,
    h("section", { class: "card quiet" }, h("h2", { text: "What is PicoQuorum?" }),
      h("p", {}, "A hardware approval console for Safe multisig wallets: a Raspberry Pi Pico 2 W with a screen and two buttons, and a sealed Infineon Trust M key that plugs in. It decodes each queued transaction on its own screen, and signs only when you hold Sign."),
      h("p", {}, h("a", { href: REPO, text: "The project on GitHub" }), " · ", h("a", { href: "#/keys", text: "Verified keys" }))),
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
  const saved = store.get("safes", []);
  const mine = saved.find((s) => s.chain === name && s.address === safe);
  const title = mine?.name || (safe === DEMO.address && name === DEMO.chain ? DEMO.name : `Safe ${short(safe)}`);

  const body = h("div", {}, h("p", { class: "muted", text: "Reading the Safe…" }));
  const saveBtn = h("button", { class: "btn", type: "button", text: mine ? "Saved" : "Save to your Safes", disabled: !!mine });
  saveBtn.onclick = () => {
    const label = prompt("A name for this Safe (only kept in this browser):", title) ?? title;
    store.set("safes", [...store.get("safes", []).filter((s) => !(s.chain === name && s.address === safe)), { chain: name, address: safe, name: label }]);
    saveBtn.textContent = "Saved";
    saveBtn.disabled = true;
  };
  const refresh = h("button", { class: "btn", type: "button", text: "Refresh", onclick: () => route() });
  fill($main(), 
    h("section", { class: "safe-head" },
      h("div", {}, h("h1", { text: title }),
        h("div", { class: "chips" }, badge(c.test ? "warn" : "eth", c.test ? `${c.name} · testnet` : `${c.name} · mainnet`))),
      h("div", { class: "row" }, saveBtn, copyButton(location.href, "Copy link"), refresh,
        h("a", { class: "btn", href: `https://app.safe.global/transactions/queue?safe=${name}:${safe}`, target: "_blank", rel: "noopener", text: "Safe{Wallet}" }))),
    h("div", { class: "addr-line big" }, h("code", { class: "mono", text: safe }), copyButton(safe), explorer(name, "address", safe)),
    body);

  try {
    const [onchain, info, keys] = await Promise.all([readSafe(pub, safe), svc.info(safe).catch((e) => ({ error: e })), byOwner()]);
    if (onchain.missing) throw new Error(`There's no contract at ${safe} on ${c.name}. Check the network.`);
    const kinds = await Promise.all(onchain.owners.map((o) => ownerKind(pub, o)));
    const summary = h("p", { class: "summary" },
      h("strong", { text: `${onchain.threshold} of ${onchain.owners.length}` }), ` · nonce ${onchain.nonce} · v${onchain.version} · ${eth(onchain.balance)} ETH`);
    const owners = h("section", { class: "card" }, h("h2", { text: "Owners" }),
      h("ul", { class: "owners" }, ...onchain.owners.map((o, i) => h("li", {}, address(name, o, [keyBadge(keys[o], kinds[i])]),
        keys[o] ? h("a", { class: "small", href: `#/key/${o}`, text: "See its checks" }) : renameLink(o)))),
      h("p", { class: "small muted", text: "Read from the Safe itself, not from Safe's service." }));

    const queue = h("section", { class: "card" }, h("h2", { text: "Queue" }));
    if (info?.error) add(queue, h("p", { class: "bad", text: info.error.message }));
    else if (!info) add(queue, h("p", { class: "muted", text: `Safe's transaction service doesn't list this Safe on ${c.name}, so there is no queue to show.` }));
    else {
      const q = await svc.queue(safe, onchain.nonce);
      if (!q?.results?.length) add(queue, h("p", { class: "muted", text: "Nothing waiting. Propose in Safe{Wallet}; it shows up here once owners have signed." }));
      for (const t of q?.results || []) add(queue, await txCard(name, safe, onchain, t, keys));
    }
    fill(body, summary, owners, queue);
  } catch (e) {
    fail(body, e);
  }
}

function renameLink(o) {
  return h("button", { class: "linkish small", type: "button", text: nameOf(o) ? "Rename" : "Name this owner", onclick: () => {
    const n = prompt("A name for this owner (only kept in this browser):", nameOf(o));
    if (n == null) return;
    const names = store.get("names", {});
    if (n.trim()) names[o.toLowerCase()] = n.trim(); else delete names[o.toLowerCase()];
    store.set("names", names);
    route();
  } });
}

function describe(chainId, t) {
  const v = BigInt(t.value);
  const method = t.dataDecoded?.method;
  const to = knownName(chainId, t.to) || nameOf(t.to) || short(getAddress(t.to));
  if (!dataBytes(t.data)) return v ? `Send ${eth(v)} ETH to ${to}` : `Call ${to} with nothing`;
  return `${method ? `${method}` : "Call"} on ${to}${v ? ` with ${eth(v)} ETH` : ""}`;
}

async function txCard(name, safe, onchain, t, keys) {
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
      h("div", { class: "vcode", title: "The console's verify code: the last 8 characters of the transaction's hash" },
        h("span", { class: "muted small", text: "Verify code" }), h("code", { text: verifyCode(check.hash) }))),
    h("dl", {},
      h("dt", { text: "To" }), h("dd", {}, h("code", { class: "mono", text: getAddress(t.to) }), knownName(c.id, t.to) ? ` (${knownName(c.id, t.to)})` : ""),
      h("dt", { text: "Value" }), h("dd", { text: `${eth(t.value)} ETH` }),
      h("dt", { text: "Data" }), h("dd", { text: dataBytes(t.data) ? `${dataBytes(t.data)} bytes${t.dataDecoded?.method ? ` · the service reads it as ${t.dataDecoded.method}` : ""}` : "none" }),
      h("dt", { text: "Operation" }), h("dd", { class: Number(t.operation) === 1 ? "bad" : "", text: Number(t.operation) === 1 ? "delegatecall" : "call" }),
      h("dt", { text: "Hash" }), h("dd", {}, h("code", { class: "mono small", text: check.hash }))),
    refuse ? h("p", { class: "bad", text: refuse }) : null,
    ...check.problems.map((p) => h("p", { class: "bad", text: p })),
    h("h4", { text: `Confirmations · ${check.valid.length} of ${onchain.threshold}` }),
    h("ul", { class: "confs" }, ...check.confirmations.map((x) => h("li", { class: x.ok ? "" : "invalid" },
      h("span", { class: `tick ${x.ok ? "ok" : "bad"}`, "aria-hidden": "true", text: x.ok ? "✓" : "✕" }),
      h("div", {},
        h("div", { class: "addr-top" }, h("strong", { text: nameOf(x.owner) || short(x.owner) }),
          keyBadge(keys[x.owner]), x.console ? badge("muted", "signed on a console", "The WebAuthn data names PicoQuorum. Anyone can write that; the check is the signature.") : null,
          badge("muted", { ecdsa: "wallet signature", contract: "contract signature", approved: "approved onchain" }[x.kind] || x.kind)),
        h("code", { class: "mono small", text: x.owner }),
        x.ok ? null : h("div", { class: "bad small", text: x.why || "not valid" })))),
      ...(check.confirmations.length ? [] : [h("li", { class: "muted", text: "No confirmations yet." })])),
  );
  const act = h("div", { class: "act" });
  add(card, act);
  if (check.problems.length) add(act, h("p", { class: "bad", text: "Don't execute this one: the hash doesn't check out." }));
  else if (!current) add(act, h("p", { class: "muted", text: `Waits for #${onchain.nonce} to run first.` }));
  else if (!enough) add(act, h("p", { class: "muted", text: `Needs ${onchain.threshold - check.valid.length} more valid confirmation${onchain.threshold - check.valid.length > 1 ? "s" : ""}.` }));
  else {
    const go = h("button", { class: "btn go", type: "button", text: "Execute with wallet" });
    const log = steps();
    go.onclick = () => execute(name, safe, t, check, onchain, go, log).catch((e) => { log.add("bad", e.shortMessage || e.message); go.disabled = false; });
    add(act, h("div", { class: "row" }, go, h("span", { class: "small muted", text: `Uses ${onchain.threshold} of the ${check.valid.length} valid confirmations. Your wallet shows it and asks before anything is sent.` })), log.el);
  }
  return card;
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
    h("section", { class: "card" }, h("h2", { text: "Check a bundle" }),
      h("p", { class: "muted", text: "Pick an attest-<serial>.json from tools/fw attest. It's checked here; nothing leaves your browser." }),
      h("label", { class: "btn", for: "bundle", text: "Choose a bundle…" }), file, checkOut));
  try {
    const reg = await registry();
    fill(list, h("ul", { class: "owners" }, ...reg.map((k) => h("li", {},
      h("div", { class: "addr-top" }, h("strong", { text: k.name }), keyBadge(k), k.holder ? h("span", { class: "muted small", text: `held by ${k.holder}` }) : null),
      h("code", { class: "mono", text: k.owner }),
      h("div", { class: "small" }, h("a", { href: `#/key/${k.owner}`, text: "Checks, and add it to a Safe" }), k.why ? h("span", { class: "bad", text: ` · ${k.why}` }) : null)))));
  } catch (e) { fail(list, e); }
}

function resultCard(r, label) {
  return h("div", { class: "result" },
    h("p", {}, h("strong", { text: label }), " · ", r.failed ? badge("bad", `${r.failed} failed`) : badge("ok", "every check passes")),
    r.owner ? h("p", {}, "Owner address ", h("code", { class: "mono", text: r.owner }), " ", copyButton(r.owner)) : null,
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
      h("section", { class: "hero" }, h("h1", { text: k.name }), h("div", { class: "chips" }, keyBadge(k)),
        k.note ? h("p", { class: "muted", text: k.note }) : null,
        h("p", {}, "Bundle: ", h("a", { href: k.bundleUrl, text: k.bundle.split("/").pop() }), k.holder ? ` · held by ${k.holder}` : "")),
      h("section", { class: "card" }, h("h2", { text: "The checks" }), k.result ? resultCard(k.result, `Trust M ${k.serial}`) : h("p", { class: "bad", text: k.why })),
      h("section", { class: "card" }, h("h2", { text: "Add this key to a Safe" }),
        h("p", {}, "Its owner address is the same on every chain: ", h("code", { class: "mono", text: o }), " ", copyButton(o)),
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

// ----------------------------------------------------------------------------- settings
function settingsView() {
  const key = h("input", { type: "password", id: "apikey", value: store.get("apiKey", ""), autocomplete: "off", placeholder: "Optional" });
  const rpcs = store.get("rpc", {});
  const rpcInputs = Object.entries(CHAINS).map(([name, c]) => [name, h("input", { type: "url", id: `rpc-${name}`, value: rpcs[name] || "", placeholder: c.rpc })]);
  const saved = h("p", { class: "small muted", role: "status" });
  fill($main(), 
    h("section", { class: "hero" }, h("h1", { text: "Settings" }), h("p", { class: "muted", text: "Kept in this browser only. Nothing here is sent anywhere except to the service or RPC it's for." })),
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
        if (!confirm("Forget your saved Safes, names, API key and RPCs in this browser?")) return;
        for (const k of ["safes", "names", "apiKey", "rpc"]) try { localStorage.removeItem("pq." + k); } catch {}
        route();
      } })), saved);
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
  if (parts[0] === "safe") return safeView(parts[1], parts[2]);
  if (parts[0] === "keys") return keysView();
  if (parts[0] === "key") return keyView(parts[1]);
  if (parts[0] === "settings") return settingsView();
  return notFound();
}
window.addEventListener("hashchange", route);
renderWallet();
registry().catch(() => {});
route();
