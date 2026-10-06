// Started in picowallet by Austin Griffith (MIT): https://github.com/austintgriffith/picowallet
// The emulated Pico lives in this Worker so a busy `while True` never freezes the page.
// Keys arrive through a SharedArrayBuffer (read even while Python is busy); frames and
// console lines go out with postMessage.
import { loadMicroPython } from "../vendor/micropython/micropython.mjs";
import { createDevice, KEY_ORDER } from "../core/runtime.mjs";

let dev = null;
let keys = null;
// Serial input ring: Int32 [head, tail] then bytes. The page writes at head, this thread reads at
// tail, so a `while True` in Python still sees new lines (postMessage would wait for it to end).
let serialCtl = null, serialBuf = null;
function stdinByte() {
  const t = Atomics.load(serialCtl, 1);
  if (t === Atomics.load(serialCtl, 0)) return null;
  const b = serialBuf[t % serialBuf.length];
  Atomics.store(serialCtl, 1, t + 1);
  return b;
}
let lastPost = 0, pendingPost = null;
const t0 = performance.now();
const mark = (w) => postMessage({ type: "mark", text: `[worker] ${w} at ${Math.round(performance.now() - t0)} ms` });

function post(frame) {
  lastPost = performance.now();
  const copy = frame.slice();
  postMessage({ type: "frame", buf: copy.buffer, frames: dev ? dev.frames : 0 }, [copy.buffer]);
}

function onFrame(frame) {
  const dt = performance.now() - lastPost;
  if (dt >= 15) { post(frame); return; }
  if (!pendingPost) pendingPost = setTimeout(() => { pendingPost = null; post(dev.frame); }, 16 - dt);
}

function xhr(method, url, body, headers, timeoutMs) {
  const x = new XMLHttpRequest();
  x.open(method, url, false);
  for (const [k, v] of Object.entries(headers)) x.setRequestHeader(k, v);
  x.send(body == null ? null : body);
  const hdrs = {};
  for (const line of x.getAllResponseHeaders().trim().split(/\r?\n/)) {
    const i = line.indexOf(":"); if (i > 0) hdrs[line.slice(0, i).trim().toLowerCase()] = line.slice(i + 1).trim();
  }
  if (x.status === 0) throw new Error("network error");
  return { status: x.status, text: x.responseText, headers: hdrs };
}

// The virtual chips' state (emu/chip.json) survives reboots: it lives on the server (tools/emu).
const CHIP_URL = new URL("../ctl/chip", import.meta.url).href;
const serverChip = {
  load() { const x = new XMLHttpRequest(); x.open("GET", CHIP_URL, false); x.send(); return x.status === 200 ? x.responseText : null; },
  save(s) { const x = new XMLHttpRequest(); x.open("POST", CHIP_URL, false); x.setRequestHeader("content-type", "application/json"); x.send(s); },
};

// A question only the page can answer (WebAuthn exists there, not in a worker), asked while Python
// waits: post it, block on the shared buffer until the page writes the answer. Int32 [ready, length]
// then the answer's bytes (JSON).
let rpcCtl = null, rpcBuf = null;
function askPage(what, args, timeoutMs = 180000) {
  if (!rpcCtl) return JSON.stringify({ error: "this page can't answer while Python runs (no SharedArrayBuffer)" });
  Atomics.store(rpcCtl, 0, 0);
  postMessage({ type: "rpc", what, args });
  if (Atomics.wait(rpcCtl, 0, 0, timeoutMs) === "timed-out") return JSON.stringify({ error: "no answer from the page" });
  return new TextDecoder().decode(rpcBuf.slice(0, Atomics.load(rpcCtl, 1)));
}
// The visitor's passkey, when the page picked one (m.passkey: its public key as JSON).
const pagePasskey = (info) => ({ info: () => info || null, get: (challenge) => askPage("passkey", { challenge }) });

onmessage = async (e) => {
  const m = e.data;
  try {
    if (m.type === "boot") {
      keys = new Int32Array(m.keys);
      if (m.serial) { serialCtl = new Int32Array(m.serial, 0, 2); serialBuf = new Uint8Array(m.serial, 8); }
      if (m.rpc) { rpcCtl = new Int32Array(m.rpc, 0, 2); rpcBuf = new Uint8Array(m.rpc, 8); }
      const files = {};
      for (const f of m.files) files[f.name] = f.text !== undefined ? f.text : Uint8Array.from(atob(f.b64), (c) => c.charCodeAt(0));
      dev = await createDevice({
        loadMicroPython, keys, files, shims: m.shims, appUrl: m.appUrl, heapsize: m.heapsize, mark,
        secrets: m.secrets, keyBin: m.keyBin, passkey: pagePasskey(m.passkey),
        http: xhr,
        chip: serverChip,
        stdin: serialCtl ? stdinByte : undefined,
        onFrame,
        onStdout: (line) => postMessage({ type: "out", line }),
        onPwm: (pin, frac) => postMessage({ type: "pwm", pin, frac }),
        onPin: (pin, v) => postMessage({ type: "pin", pin, v }),
        onReset: () => postMessage({ type: "reset" }),
      });
      postMessage({ type: "ready", files: dev.listFiles() });
      // "started" goes out first: a module with a `while True` never returns, so the page treats
      // a boot that is still inside run() after a moment as "running (busy loop)".
      if (m.run) { postMessage({ type: "started", id: m.id }); dev.run(m.run, m.entry); mark("ran " + m.run); postMessage({ type: "done", id: m.id }); }
    } else if (m.type === "run") {
      postMessage({ type: "started", id: m.id }); dev.run(m.name, m.entry); postMessage({ type: "done", id: m.id });
    } else if (m.type === "exec") {
      dev.exec(m.code); postMessage({ type: "done", id: m.id });
    } else if (m.type === "write") {
      dev.writeFile(m.name, m.data); postMessage({ type: "done", id: m.id });
    } else if (m.type === "keys") {
      keys.set(m.state); // fallback when SharedArrayBuffer is unavailable
    } else if (m.type === "send") {
      dev.writeStdin(m.line); // fallback without SharedArrayBuffer: only lands while Python is idle
    }
  } catch (err) {
    postMessage({ type: "out", line: String(err && err.message || err) });
    if (m.id) postMessage({ type: "done", id: m.id, error: String(err) });
  }
};
