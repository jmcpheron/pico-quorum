// The console page's worker: MicroPython (WebAssembly) running the console image, off the page so its
// screen and buttons stay live. The page posts one message, "boot"; from then on:
//   keys      read from a SharedArrayBuffer the page writes, even while Python is busy
//   frames    each screen the firmware sends over its SPI, posted to the page to paint
//   HTTP      the firmware's calls to Safe's service, as synchronous XHR from here
//   passkey   the firmware asks for an assertion (shims/passkey.py); WebAuthn exists only in the
//             page, so this asks the page and waits on the shared buffer for its answer
// emu/build.mjs publishes it as worker.js in docs/console/. The local emulator's (emu/web/worker.js)
// does more: a serial line, the chip state on the server, running and editing modules.
import { loadMicroPython } from "./vendor/micropython/micropython.mjs";
import { createDevice } from "./core/runtime.mjs";

let dev = null, lastPost = 0, pending = null;

function post(frame) {
  lastPost = performance.now();
  const copy = frame.slice();
  postMessage({ type: "frame", buf: copy.buffer, frames: dev ? dev.frames : 0 }, [copy.buffer]);
}
function onFrame(frame) {                  // at most about one frame in 16 ms reaches the page
  const dt = performance.now() - lastPost;
  if (dt >= 15) return post(frame);
  if (!pending) pending = setTimeout(() => { pending = null; post(dev.frame); }, 16 - dt);
}

function xhr(method, url, body, headers) {
  const x = new XMLHttpRequest();
  x.open(method, url, false);
  for (const [k, v] of Object.entries(headers)) x.setRequestHeader(k, v);
  x.send(body == null ? null : body);
  if (x.status === 0) throw new Error("network error");
  const hdrs = {};
  for (const line of x.getAllResponseHeaders().trim().split(/\r?\n/)) {
    const i = line.indexOf(":"); if (i > 0) hdrs[line.slice(0, i).trim().toLowerCase()] = line.slice(i + 1).trim();
  }
  return { status: x.status, text: x.responseText, headers: hdrs };
}

// The page's answer comes back through Int32 [ready, length] and then its bytes (JSON).
let rpcCtl = null, rpcBuf = null;
function askPage(what, args, timeoutMs = 180000) {
  Atomics.store(rpcCtl, 0, 0);
  postMessage({ type: "rpc", what, args });
  if (Atomics.wait(rpcCtl, 0, 0, timeoutMs) === "timed-out") return JSON.stringify({ error: "no answer from the page" });
  return new TextDecoder().decode(rpcBuf.slice(0, Atomics.load(rpcCtl, 1)));
}

onmessage = async ({ data: m }) => {
  if (m.type !== "boot") return;
  try {
    rpcCtl = new Int32Array(m.rpc, 0, 2);
    rpcBuf = new Uint8Array(m.rpc, 8);
    const files = Object.fromEntries(m.files.map((f) => [f.name, f.text !== undefined ? f.text : f.bytes]));
    dev = await createDevice({
      loadMicroPython, keys: new Int32Array(m.keys), files, shims: m.shims, appUrl: null, secrets: m.secrets,
      keyBin: null,                       // no software key: the passkey is the only key
      passkey: { info: () => m.passkey, get: (challenge) => askPage("passkey", { challenge }) },
      http: xhr, onFrame,
      onStdout: (line) => postMessage({ type: "out", line }),
      onPwm: (pin, frac) => postMessage({ type: "pwm", pin, frac }),
      onReset: () => postMessage({ type: "reset" }),
    });
    dev.run("quorum", "quorum.start()");
  } catch (e) {
    postMessage({ type: "out", line: String((e && e.message) || e) });
  }
};
