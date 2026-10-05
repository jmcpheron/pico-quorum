// The PicoQuorum console in a page: the console's screen and buttons, nothing else. The same firmware
// as the Pico (the emulator's boot.json, run by its worker), the quorum console only, with your own
// passkey as its key and the Safes you saved in the app. emu/build.mjs writes it to docs/console/.
// The emulator (../emu/) is the developer's page: an editor, the 3D case, every module.
import {
  KEY_ORDER, answer, appSafes, browserKey, keyOf, local, makePasskey, paintFrame, passkeyCred, showRelease,
  stampRelease, staticBoot, staticSecrets, usePasskey,
} from "../emu/web/browser.mjs";

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

function panel() {
  const cred = passkeyCred();
  $("#key").replaceChildren(...(cred
    ? [`your passkey, for ${cred.rpId} (${cred.synced ? "synced by your account" : "kept on that device"}) · `, el("a", { href: "../app/#/passkey", textContent: "use it in a Safe" })]
    : ["none yet"]));
  const safes = appSafes();
  $("#safes").replaceChildren(...(safes.length
    ? [`${safes.map((s) => s.name || s.address.slice(0, 8)).join(", ")} · `, el("a", { href: "../app/", textContent: "change in the app" })]
    : ["none saved · ", el("a", { href: "../app/", textContent: "open a Safe in the app" })]));
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
  panel();
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
    return overlay(el("h2", { textContent: "No Safe to watch yet" }),
      el("p", { textContent: "The console watches the Safes you save in the app. Open a Safe there, save it, and come back." }),
      el("a", { className: "go", href: "../app/", textContent: "Open the app" }),
      el("p", { className: "small" }, "To add this console's key to a Safe: ", el("a", { href: "../app/#/passkey", textContent: "your passkey in the app" }), " has its owner address, deploys its signer, and proposes adding it."));
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
const typing = (t) => t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
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
