// What a page needs to run the console from GitHub Pages, shared by the emulator (web/app.js) and
// the plain console page (docs/console/, emu/console/): boot.json, the release fingerprint of what
// boots, the Safes saved in the app, a per-browser software key, and the visitor's own passkey.
// Relative URLs here resolve against this file (emu/web/), so both pages find the same boot.json.
import { assertionParts, b64url, derToRS, recoverKeys, spkiXY, unhex } from "../core/webauthn-assert.mjs";

export const local = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

// ---- keys ---------------------------------------------------------------------------------------
export const KEY_ORDER = ["A", "B", "X", "Y", "up", "down", "left", "right", "press"];
// keyboard -> device. Joystick: W A S D (or the arrows) + space. Buttons: numpad 9 6 3 . (top row too).
const KEYMAP = { w: "up", a: "left", s: "down", d: "right", " ": "press", 9: "A", 6: "B", 3: "X", ".": "Y",
  ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "press" };
const CODEMAP = { Numpad9: "A", Numpad6: "B", Numpad3: "X", NumpadDecimal: "Y", Space: "press" };
export const keyOf = (e) => CODEMAP[e.code] || KEYMAP[e.key] || KEYMAP[e.key.toLowerCase()];

// ---- the release fingerprint --------------------------------------------------------------------
// tools/releases/fingerprint.mjs, in the browser: sha256 over "name \0 sha256(file) \n" lines of the
// console image's files, sorted. Taken over what the page boots, so it names exactly that.
const enc = new TextEncoder();
export const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
export async function fingerprint(names, payload) {
  if (!names.length || !crypto.subtle) return "";
  const byName = new Map(payload.map((f) => [f.name, f]));
  let lines = "";
  for (const n of [...new Set(names)].sort()) {
    const f = byName.get(n);
    if (!f) return "";
    const bytes = f.text !== undefined ? enc.encode(f.text) : Uint8Array.from(atob(f.b64), (c) => c.charCodeAt(0));
    lines += `${n}\0${hex(await crypto.subtle.digest("SHA-256", bytes))}\n`;
  }
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(lines)));
}

/** build.py's RELEASE set to the fingerprint of the payload that boots; returns that fingerprint. */
export async function stampRelease(consoleFiles, payload) {
  const fp = await fingerprint(consoleFiles || [], payload);
  const bp = payload.find((f) => f.name === "build.py");
  if (bp && fp) bp.text = bp.text.replace(/^RELEASE = .*$/m, `RELEASE = ${JSON.stringify(fp)}`);
  return fp;
}

/** The fingerprint's blockie and first 8 hex digits in el, as a Pico's Device screen shows them;
 *  marked when the files differ from the release the page was built from. */
export async function showRelease(el, fp, built) {
  if (!el || !fp) return;
  const { blockieSrc } = await import("../shared/blockies.mjs");
  const img = document.createElement("img");
  img.src = blockieSrc("0x" + fp);
  img.alt = "";
  const changed = built && fp !== built;
  el.replaceChildren(img, `release ${fp.slice(0, 4)}·${fp.slice(4, 8)}${changed ? " (edited)" : ""}`);
  el.classList.toggle("edited", !!changed);
  el.title = `release fingerprint ${fp}: the same blockie as on a Pico's Device screen running these files` +
    (changed ? `. Edited here: the files as built give ${built.slice(0, 8)}.` : "");
}

// ---- boot.json -------------------------------------------------------------------------------------
export const EDIT = "emu.file:";       // + name: a file edited or made in the emulator, in this browser
const ENTRY_OF = { demo: "demo.run()", wallet: "wallet.start()", usbwallet: "usbwallet.start()", quorum: "quorum.start()" };

/** boot.json (emu/build.mjs: the firmware, the shims, build.py). edits: the emulator's edits in this
 *  browser on top; the console page runs the files exactly as built. */
export async function staticBoot({ edits = false } = {}) {
  const b = await (await fetch(new URL("../boot.json", import.meta.url), { cache: "no-cache" })).json();
  const byName = new Map(b.files.map((f) => [f.name, f]));
  for (let i = 0; edits && i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (!k || !k.startsWith(EDIT)) continue;
    try {
      const { text, src } = JSON.parse(local.get(k));
      const name = k.slice(EDIT.length), mod = name.replace(/\.py$/, "");
      const runnable = name.endsWith(".py") && (!!ENTRY_OF[mod] || mod === "main" || /^(start|run|main)\(\)\s*$/m.test(text));
      byName.set(name, { ...(byName.get(name) || { name, src: src || "sketches", entry: ENTRY_OF[mod] || "" }), text, runnable });
    } catch {}
  }
  return { ...b, files: [...byName.values()] };
}

// ---- the app's Safes ------------------------------------------------------------------------------
// The Safes saved in the app ({chain, address, name}; same origin, so the same localStorage), as
// secrets.py's QUORUM_SAFES, and the app's Safe API key. APP_URL is None (boot.json appUrl null), so
// the console asks Safe's own service for each chain, as a production console does.
export const CHAIN_IDS = { eth: 1, base: 8453, basesep: 84532 };
export function appSafes() {
  try { return (JSON.parse(local.get("pq.safes") || "[]") || []).filter((s) => CHAIN_IDS[s.chain] && /^0x[0-9a-fA-F]{40}$/.test(s.address)); }
  catch { return []; }
}
export function staticSecrets() {
  const safes = appSafes().map((s) => ({ chainId: CHAIN_IDS[s.chain], address: s.address, name: String(s.name || "Safe").slice(0, 40) }));
  let key = "";
  try { key = JSON.parse(local.get("pq.apiKey") || '""'); } catch {}
  return "\n# from the app's saved Safes and settings, in this browser\n" +
    (safes.length ? `QUORUM_SAFES = ${JSON.stringify(safes)}\n` : "") +
    (key ? `QUORUM_API_KEY = ${JSON.stringify(key)}\n` : "");
}

// The software key (key.bin): random, made once in this browser and kept there. The fixed test key
// the local emulator uses would be anyone's on a public page.
export function browserKey() {
  let h = local.get("emu.keybin");
  if (!/^[0-9a-f]{64}$/.test(h || "")) { h = hex(crypto.getRandomValues(new Uint8Array(32))); local.set("emu.keybin", h); }
  return Uint8Array.from(h.match(/../g), (x) => parseInt(x, 16));
}

// ---- your passkey ---------------------------------------------------------------------------------
// The visitor's own passkey as the console's key (shims/passkey.py). Made here with WebAuthn, for
// this site (rpId: this host); its public key is kept in this browser and handed to the console at
// boot. The private key never leaves the authenticator: Touch ID, Windows Hello, a phone, a
// security key. The console asks for an assertion over the hash it computed; the person approves
// with the authenticator, which never shows the transaction: what they approve is the console's screen.
export const keyMode = () => (local.get("emu.key") === "passkey" ? "passkey" : "chip");
export const setKeyMode = (m) => local.set("emu.key", m === "passkey" ? "passkey" : "chip");
export const passkeyCred = () => { try { return JSON.parse(local.get("emu.passkey") || "null"); } catch { return null; } };

/** Make the passkey (the OS asks), keep its public key here. -> the credential, or throws. */
export async function makePasskey() {
  if (!window.PublicKeyCredential) throw new Error("this browser has no WebAuthn");
  const c = await navigator.credentials.create({ publicKey: {
    rp: { name: "PicoQuorum console", id: location.hostname },
    user: { id: crypto.getRandomValues(new Uint8Array(16)), name: "PicoQuorum console key", displayName: "PicoQuorum console key" },
    challenge: crypto.getRandomValues(new Uint8Array(32)),
    pubKeyCredParams: [{ type: "public-key", alg: -7 }],        // ES256: P-256, what Safe's passkey signer verifies
    authenticatorSelection: { userVerification: "required", residentKey: "preferred" },
    attestation: "none", timeout: 120000 } });
  if (c.response.getPublicKeyAlgorithm && c.response.getPublicKeyAlgorithm() !== -7) throw new Error("the passkey isn't P-256 (ES256)");
  const flags = new Uint8Array(c.response.getAuthenticatorData())[32];
  const transports = (c.response.getTransports && c.response.getTransports()) || [];
  const cred = { id: b64url(new Uint8Array(c.rawId)), ...spkiXY(c.response.getPublicKey()), rpId: location.hostname,
    attachment: transports.includes("hybrid") ? "hybrid" : c.authenticatorAttachment === "platform" ? "platform" : "security-key",
    synced: !!(flags & 0x10), made: new Date().toISOString().slice(0, 10) };
  local.set("emu.passkey", JSON.stringify(cred));
  setKeyMode("passkey");
  return cred;
}

/** A passkey you already have for this site (made in another browser, or synced from another
 *  device): you pick it, it signs twice (two prompts), and its public key is worked out from the two
 *  signatures, checked, and kept here. -> the credential, or throws. */
export async function usePasskey() {
  if (!window.PublicKeyCredential) throw new Error("this browser has no WebAuthn");
  const once = async (id) => {
    const a = await navigator.credentials.get({ publicKey: {
      challenge: crypto.getRandomValues(new Uint8Array(32)), rpId: location.hostname, userVerification: "required", timeout: 120000,
      ...(id ? { allowCredentials: [{ type: "public-key", id }] } : {}) } });      // first: any passkey for this site
    const ad = new Uint8Array(a.response.authenticatorData), cdj = new Uint8Array(a.response.clientDataJSON);
    const signed = new Uint8Array([...ad, ...new Uint8Array(await crypto.subtle.digest("SHA-256", cdj))]);
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", signed));
    const { r, s } = derToRS(a.response.signature);
    return { a, ad, keys: recoverKeys(digest, r, s) };
  };
  const one = await once(null);
  const two = await once(new Uint8Array(one.a.rawId));
  const both = one.keys.filter((k) => two.keys.some((m) => m.x === k.x && m.y === k.y));
  if (both.length !== 1) throw new Error("couldn't work out that passkey's public key from its signatures");
  const { x, y } = both[0];
  const cred = { id: b64url(new Uint8Array(one.a.rawId)), x, y, rpId: location.hostname,
    attachment: one.a.authenticatorAttachment === "cross-platform" ? "security-key" : "platform",
    synced: !!(two.ad[32] & 0x10), made: new Date().toISOString().slice(0, 10), found: true };
  local.set("emu.passkey", JSON.stringify(cred));
  setKeyMode("passkey");
  return cred;
}

export async function passkeyGet(challenge) {
  const cred = passkeyCred();
  if (!cred) throw new Error("no passkey in this browser");
  if (local.get("emu.passkey-noted") !== "1") {
    const go = confirm("Before your passkey signs:\n\nTouch ID (or Windows Hello, or your phone) won't show the transaction. What you approve is the console's screen here, which this browser draws.\n\nOn a computer you don't trust, use a hardware key instead. Keep passkey owners below the Safe's threshold.\n\nSign with your passkey?");
    if (!go) throw new Error("NotAllowedError: you chose not to sign");
    local.set("emu.passkey-noted", "1");
  }
  const a = await navigator.credentials.get({ publicKey: {
    challenge: unhex(challenge), rpId: cred.rpId, userVerification: "required", timeout: 120000,
    allowCredentials: [{ type: "public-key", id: Uint8Array.from(atob(cred.id.replace(/-/g, "+").replace(/_/g, "/")), (ch) => ch.charCodeAt(0)) }] } });
  const parts = assertionParts(challenge, a.response.authenticatorData, a.response.clientDataJSON, a.response.signature);
  // checked here against the key the console was given, before it is posted anywhere
  const key = await crypto.subtle.importKey("raw", unhex("04" + cred.x + cred.y), { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
  const rs = unhex(parts.r.padStart(64, "0") + parts.s.padStart(64, "0"));
  const signed = new Uint8Array([...unhex(parts.ad), ...new Uint8Array(await crypto.subtle.digest("SHA-256", a.response.clientDataJSON))]);
  if (!(await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, key, rs, signed))) throw new Error("that passkey isn't the one this console was given");
  return parts;
}

/** The worker's question (askPage in worker.js): answer into the shared buffer, then wake it. */
export async function answer(rpcSab, m) {
  let out;
  try {
    if (m.what === "passkey") out = await passkeyGet(m.args.challenge);
    else throw new Error("unknown question " + m.what);
  } catch (e) { out = { error: `${e.name && e.name !== "Error" ? e.name + ": " : ""}${e.message || e}` }; }
  const bytes = new TextEncoder().encode(JSON.stringify(out));
  const ctl = new Int32Array(rpcSab, 0, 2);
  new Uint8Array(rpcSab, 8).set(bytes.slice(0, 65536));
  Atomics.store(ctl, 1, Math.min(bytes.length, 65536));
  Atomics.store(ctl, 0, 1);
  Atomics.notify(ctl, 0);
}

/** RGB565 big-endian frame (from the worker) into ImageData. */
export function paintFrame(buf, img) {
  const b = new Uint8Array(buf), d = img.data;
  for (let i = 0, o = 0; i < b.length; i += 2, o += 4) {
    const c = (b[i] << 8) | b[i + 1];
    d[o] = (c >> 8) & 0xf8; d[o + 1] = (c >> 3) & 0xfc; d[o + 2] = (c << 3) & 0xf8; d[o + 3] = 255;
  }
}
