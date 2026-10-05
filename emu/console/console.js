// The PicoQuorum console in a page: the console's screen and buttons, nothing else. The same firmware
// as the Pico (the emulator's boot.json, run by its worker), the quorum console only, with your own
// passkey as its key and the Safes you saved in the app (or add here: the same list). It shows your
// passkey's owner address, the one to add to a Safe. emu/build.mjs writes it to docs/console/.
// The emulator (../emu/) is the developer's page: an editor, the 3D case, every module.
import {
  CHAIN_IDS, KEY_ORDER, answer, appSafes, browserKey, checksum, consoleCfg, forgetAppSafe, keyOf, local, makePasskey,
  paintFrame, passkeyCred, passkeyOwner, safeInfo, saveAppSafe, showRelease, stampRelease, staticBoot, staticSecrets, usePasskey,
} from "../emu/web/browser.mjs";
import { blockieSrc } from "../emu/shared/blockies.mjs";

const $ = (s) => document.querySelector(s);
const sab = typeof SharedArrayBuffer !== "undefined" && self.crossOriginIsolated ? new SharedArrayBuffer(16 * 4) : null;
const keys = sab ? new Int32Array(sab) : null;
const rpcSab = sab ? new SharedArrayBuffer(8 + 65536) : null;     // the worker's questions (your passkey)
const screen = $("#screen"), ctx = screen.getContext("2d"), img = ctx.createImageData(240, 240);
let worker = null;

// ---- what the page says around the screen ----------------------------------------------------------
function overlay(...kids) {
  const o = $("#overlay");
  o.hidden = !kids.length;
  o.replaceChildren(...kids);
}
const el = (tag, attrs = {}, ...kids) => { const e = Object.assign(document.createElement(tag), attrs); e.append(...kids); return e; };

const CHAIN_NAMES = { eth: "Ethereum", base: "Base", basesep: "Base Sepolia" };
const short = (a) => `${a.slice(0, 6)}…${a.slice(-4)}`;

// Your passkey's owner address: the passkey signer's address, worked out here from its public key
// and the factory in the console's own quorum_cfg.py. The console's screen computes the same one.
async function myOwner() {
  const cred = passkeyCred(), cfg = consoleCfg((await built).files);
  return cred && cfg ? passkeyOwner(cred, cfg.signer) : "";
}

/** The address with its blockie and a Copy button. */
function ownerLine(owner) {
  const copy = el("button", { className: "copy", type: "button", textContent: "Copy" });
  copy.onclick = async () => {
    try { await navigator.clipboard.writeText(owner); copy.textContent = "Copied"; } catch { copy.textContent = "Select it"; }
    setTimeout(() => { copy.textContent = "Copy"; }, 1500);
  };
  return el("div", { className: "owner" }, el("img", { className: "blockie", src: blockieSrc(owner), alt: "" }),
    el("code", { className: "addr", textContent: owner }), copy);
}

/** Adding a Safe you already have, by chain and address, to the list the app keeps too. A wallet that
 *  owns it adds your passkey as an owner; this only tells the console which Safes to watch. */
function addSafeForm() {
  const chain = el("select", { title: "The Safe's chain" },
    ...Object.keys(CHAIN_IDS).map((k) => el("option", { value: k, textContent: CHAIN_NAMES[k] || k, selected: k === "base" })));
  const address = el("input", { type: "text", placeholder: "Safe address, 0x… or base:0x…", spellcheck: false, autocomplete: "off" });
  const name = el("input", { type: "text", placeholder: "Name (optional)", maxLength: 80, autocomplete: "off" });
  const add = el("button", { className: "go", type: "button", textContent: "Add Safe" });
  const why = el("p", { className: "small bad" });
  address.oninput = () => {      // Safe{Wallet} copies "base:0x…" (EIP-3770): the prefix picks the chain
    const m = address.value.trim().match(/^([a-z]+):(0x[0-9a-fA-F]*)$/);
    if (m && CHAIN_IDS[m[1]]) { chain.value = m[1]; address.value = m[2]; }
  };
  const go = () => {
    try { saveAppSafe({ chain: chain.value, address: address.value, name: name.value }); start(); }
    catch (e) { why.textContent = e.message; }
  };
  add.onclick = go;
  for (const i of [address, name]) i.onkeydown = (e) => { if (e.key === "Enter") go(); };
  return el("div", { className: "add-safe" }, el("div", { className: "fields" }, chain, address, name, add), why);
}

/** Is your passkey an owner? Safe's service says (read only). Not yet: the app's add-owner page, the
 *  address filled in, where a wallet that owns the Safe proposes it. */
async function ownerStatus(where, s, owner) {
  try {
    const { owners, threshold } = await safeInfo(consoleCfg((await built).files), s);
    if (owner && owners.includes(owner.toLowerCase())) {
      where.className = "status ok";
      where.textContent = `your passkey is an owner · ${threshold} of ${owners.length}`;
    } else {
      where.className = "status warn";
      where.replaceChildren(`${threshold} of ${owners.length}, your passkey isn't an owner yet · `,
        ...(owner ? [el("a", { href: `../app/#/safe/${s.chain}/${checksum(s.address)}/new/add/${owner}`, textContent: "propose adding it" })] : []));
    }
  } catch (e) {
    where.className = "status";
    where.textContent = `couldn't check: ${e.message}`;
  }
}

async function panel() {
  const cred = passkeyCred(), owner = await myOwner();
  $("#key").replaceChildren(...(cred
    ? [`your passkey, for ${cred.rpId} (${cred.synced ? "synced by your account" : "kept on that device"}) · `, el("a", { href: "../app/#/passkey", textContent: "deploy its signer" })]
    : ["none yet"]));
  $("#owner-row").hidden = !owner;
  $("#owner").replaceChildren(...(owner ? [ownerLine(owner)] : []));
  const safes = appSafes();
  $("#safes").replaceChildren(safes.length
    ? el("ul", { className: "safes" }, ...safes.map((s) => {
        const status = el("span", { className: "status", textContent: "checking…" });
        const rm = el("button", { className: "link", type: "button", textContent: "Remove", title: "Stop watching it here and in the app. The Safe itself is unchanged." });
        rm.onclick = () => { forgetAppSafe(s); start(); };
        ownerStatus(status, s, owner);
        return el("li", {}, el("img", { className: "blockie", src: blockieSrc(s.address), alt: "" }),
          el("div", { className: "grow" }, el("div", {}, el("b", { textContent: s.name || "Safe" }), ` · ${CHAIN_NAMES[s.chain] || s.chain} · `,
            el("code", { textContent: short(checksum(s.address)), title: checksum(s.address) })), status), rm);
      }))
    : el("span", { className: "dim", textContent: "none yet" }));
  $("#add-safe").replaceChildren(...(cred && safes.length ? [addSafeForm()] : []));     // with none, the screen asks
}

function out(line) {
  const pre = $("#out");
  pre.textContent = (pre.textContent + line + "\n").split("\n").slice(-200).join("\n");
}

// ---- the console ---------------------------------------------------------------------------------
// The files exactly as built (no edits here), with build.py's RELEASE their fingerprint, computed
// again in this browser: the blockie in the bar is what this page runs, shown before anything else.
const built = (async () => {
  const b = await staticBoot();
  const files = b.files.map((f) => ({ ...f }));
  const fp = await stampRelease(b.consoleFiles, files);
  showRelease($("#release"), fp, b.release);
  return { ...b, files };
})();

async function boot() {
  if (worker) worker.terminate();
  const b = await built, payload = b.files;
  // ./worker.js imports the emulator's worker: a worker's own script is fetched under the service worker
  // whose scope holds its URL, so it has to live here for this folder's sw.js to isolate it
  worker = new Worker(new URL("worker.js", import.meta.url), { type: "module" });
  worker.onmessage = (e) => {
    const m = e.data;
    if (m.type === "frame") { paintFrame(m.buf, img); ctx.putImageData(img, 0, 0); screen.dataset.frames = String(m.frames); }
    else if (m.type === "out") out(m.line);
    else if (m.type === "rpc") answer(rpcSab, m);
    else if (m.type === "chip") local.set("emu.chip", m.data);
    else if (m.type === "reset") boot();
  };
  worker.onerror = (e) => out("worker: " + e.message);
  worker.postMessage({ type: "boot", id: 1, keys: sab, files: payload, shims: b.shims, appUrl: b.appUrl, run: "quorum", entry: "quorum.start()",
    secrets: staticSecrets(), chip: local.get("emu.chip"), keyBin: browserKey(), passkey: local.get("emu.passkey"), rpc: rpcSab });
}

async function start() {
  await panel();
  if (!sab) {
    // coi.js reloads the page once to turn SharedArrayBuffer on; still off means this browser can't
    return overlay(el("p", { textContent: "This browser can't run the console here: it needs SharedArrayBuffer (cross-origin isolation). Try a current Chrome, Edge, Safari or Firefox." }));
  }
  if (!passkeyCred()) {
    const go = el("button", { className: "go", textContent: "Make a passkey" });
    const have = el("button", { className: "go alt", textContent: "I already have one" });
    const why = el("p", { className: "small" });
    const act = (b, f, what) => async () => {
      go.disabled = have.disabled = true;
      try { await f(); start(); }
      catch (e) { why.textContent = `${what}: ${e.name && e.name !== "Error" ? e.name + ": " : ""}${e.message || e}`; go.disabled = have.disabled = false; }
    };
    go.onclick = act(go, makePasskey, "No passkey made");
    have.onclick = act(have, usePasskey, "No passkey");
    return overlay(el("h2", { textContent: "Your key is a passkey" }),
      el("p", { textContent: "This console signs with a passkey: Touch ID, Windows Hello, your phone or a security key. Its private key never leaves that device. The console shows its owner address, to add to a Safe." }),
      el("div", { className: "acts" }, go, have),
      el("p", { className: "small", textContent: "Made one already, in another browser or on your other device (iCloud Keychain syncs it)? Choose I already have one: it signs twice, and the page works out its public key. Same passkey, same owner." }),
      why);
  }
  if (!appSafes().length) {
    const owner = await myOwner();
    return overlay(el("h2", { textContent: "Add a Safe to watch" }),
      el("p", { textContent: "Your passkey signs as this owner, the same address on every chain:" }),
      ...(owner ? [ownerLine(owner)] : []),
      el("p", { className: "small" }, "A passkey isn't a wallet: it can't pay gas or send a transaction. A wallet that owns the Safe deploys its signer and proposes adding this address as an owner (",
        el("a", { href: "../app/#/passkey", textContent: "your passkey in the app" }), " does both). Then the console shows the Safe's queue, and your passkey confirms what it shows."),
      addSafeForm());
  }
  overlay();
  await boot();
}

// ---- buttons and keys ------------------------------------------------------------------------------
function setKey(name, down) {
  const i = KEY_ORDER.indexOf(name);
  if (i < 0 || !keys) return;
  Atomics.store(keys, i, down ? 1 : 0);
  for (const b of document.querySelectorAll(`[data-key="${name}"]`)) b.classList.toggle("down", down);
}
for (const b of document.querySelectorAll("[data-key]")) {
  const k = b.dataset.key;
  b.addEventListener("pointerdown", (e) => { e.preventDefault(); try { b.setPointerCapture(e.pointerId); } catch {} setKey(k, true); });
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) b.addEventListener(ev, () => setKey(k, false));
}
const typing = (t) => t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
window.addEventListener("keydown", (e) => {
  if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = keyOf(e);
  if (!k || (e.target.tagName === "BUTTON" && !e.target.dataset.key && (k === "press"))) return;
  e.preventDefault();
  if (!e.repeat) setKey(k, true);
});
window.addEventListener("keyup", (e) => { const k = keyOf(e); if (k) setKey(k, false); });
window.addEventListener("blur", () => { for (const k of KEY_ORDER) setKey(k, false); });
window.addEventListener("storage", (e) => { if (e.key === "pq.safes" || e.key === "pq.apiKey") start(); });   // saved in the app's tab

start();
