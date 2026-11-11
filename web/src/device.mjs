// #/device: a Picoquorum console on this computer's USB, through Web Serial (Chrome and Edge on a
// computer). The page talks the console's USB link (firmware/usblink.py, docs/USB-LINK.md): it
// reads what the console is and knows, and can send it a Wi-Fi network and the Safes it watches.
// The console shows each on its own screen and saves it only when the person holds D2 there.
// Nothing here can make the console sign, and nothing reads its key: the link has no such request.
// Everything the console sends is untrusted, and drawn with textContent (h() in main.mjs).
//
// A console-rp has no radio: while this page is open it is the console's relay (relay.mjs). The
// console's own calls to Safe's service come up the cable as {"t":"req"} lines; the page checks each
// as tools/relay/relay.py does, makes it with this browser's API key, and sends back {"t":"res"}.
import { CFG } from "./config.gen.mjs";
import { HI_MS, Relay } from "./relay.mjs";

// ----------------------------------------------------------------------------- the link
// USB vendor ids the chooser offers: Espressif (an S3's own USB), Adafruit, Raspberry Pi, WCH (CH34x).
export const FILTERS = [0x303a, 0x239a, 0x2e8a, 0x1a86].map((usbVendorId) => ({ usbVendorId }));
const MAX_BUF = 65536;
const WCH = 0x1a86;         // a CH343P, wired to the console's UART1 (console-rp), runs at 460800 (firmware/link.py)
export const baudFor = (info) => (info?.usbVendorId === WCH ? 460800 : 115200);

/** One open port: JSON lines out, answers matched by id; any other line is the console's log. */
export class Link {
  constructor(port) {
    this.port = port;
    this.next = 1;
    this.waiting = new Map();
    this.buf = "";
    this.closed = false;
    this.onclose = null;
    this.onlog = null;
    this.onreq = null;
  }

  async open() {
    await this.port.open({ baudRate: baudFor(this.port.getInfo?.()) });
    // Low and left there: on an ESP32-S3's own USB, DTR and RTS edges reset it or start its ROM
    // bootloader. The console never needs them.
    try { await this.port.setSignals({ dataTerminalReady: false, requestToSend: false }); } catch {}
    this.writer = this.port.writable.getWriter();
    this.reading = this.read();
  }

  async read() {
    const dec = new TextDecoder();
    this.reader = this.port.readable.getReader();
    try {
      for (;;) {
        const { value, done } = await this.reader.read();
        if (done) break;
        this.buf += dec.decode(value, { stream: true });
        let i;
        while ((i = this.buf.indexOf("\n")) >= 0) {
          const line = this.buf.slice(0, i).trim();
          this.buf = this.buf.slice(i + 1);
          this.line(line);
        }
        if (this.buf.length > MAX_BUF) this.buf = "";
      }
    } catch { /* the port went away: the board restarted or was unplugged */ }
    this.closed = true;
    try { this.reader.releaseLock(); } catch {}
    for (const w of this.waiting.values()) w(null);
    this.waiting.clear();
    this.onclose?.();
  }

  // An answer starts {"pq":. A console-rp's own lines carry "t", in no set key order (MicroPython's
  // json): "req" goes to the relay, "log" is a log line. Anything else is a log line as it came.
  line(l) {
    if (!l) return;
    if (!l.startsWith("{")) { this.onlog?.(l); return; }
    let a;
    try { a = JSON.parse(l); } catch { if (!l.startsWith('{"pq":')) this.onlog?.(l); return; }
    if (!a || typeof a !== "object" || Array.isArray(a)) return;
    if (l.startsWith('{"pq":')) {
      const w = this.waiting.get(a.id);
      if (w) { this.waiting.delete(a.id); w(a); }
    } else if (a.t === "req") {
      this.onreq?.(a);
    } else if (a.t === "log") {
      this.onlog?.(String(a.m ?? ""));
    } else {
      this.onlog?.(l);
    }
  }

  /** One line as it is, for the relay's answers and its hi. */
  send(line) {
    if (this.closed) return;
    this.writer.write(new TextEncoder().encode(line + "\n")).catch(() => {});
  }

  /** One request: the answer, or null when none came in ms (or the port closed). */
  request(op, body = {}, ms = 4000) {
    if (this.closed) return Promise.resolve(null);
    const id = this.next++;
    return new Promise((resolve) => {
      const t = setTimeout(() => { this.waiting.delete(id); resolve(null); }, ms);
      this.waiting.set(id, (a) => { clearTimeout(t); resolve(a); });
      this.writer.write(new TextEncoder().encode(JSON.stringify({ id, op, ...body }) + "\n")).catch(() => {});
    });
  }

  async close() {
    this.closed = true;
    try { await this.reader?.cancel(); } catch {}
    try { await this.reading; } catch {}
    try { this.writer?.releaseLock(); } catch {}
    try { await this.port.close(); } catch {}
  }
}

/** hello, asked again until it answers or `ms` runs out: a console still starting doesn't yet. */
export async function hello(link, ms = 30000, tick = () => {}) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms && !link.closed) {
    const a = await link.request("hello", {}, 2500);
    if (a?.ok) return a;
    tick(Math.round((Date.now() - t0) / 1000));
  }
  return null;
}

// ----------------------------------------------------------------------------- what it is
export const BOARDS = {
  "picoquorum-key": ["PicoquorumKey", "D0", "D1", "D2"],
  "feather-s3": ["Feather ESP32-S3 Reverse TFT", "D0", "D1", "D2"],
  "feather-knob": ["ESP32-S3 TFT Feather with a knob", "Boot", "a turn", "the knob's push"],
  waveshare: ["Pico with the Waveshare 1.3\" screen", "Y", "the joystick", "A"],
  build1: ["Build 1", "B", "a turn", "the knob, pressed down"],
  esp32: ["ESP32 with a knob", "B", "a turn", "the knob, pressed down"],
  "console-rp": ["console-rp", "■ (D0)", "● (D1)", "▲ (D2)"],
};
export const boardName = (b) => (BOARDS[b] || [b || "an unknown board"])[0];
export const keysOf = (b) => { const k = BOARDS[b] || BOARDS.waveshare; return { no: k[1], page: k[2], yes: k[3] }; };
/** The console page's body for this board: three buttons, or the Pico's. */
export const twinBoard = (b) => (["picoquorum-key", "feather-s3", "feather-knob", "console-rp"].includes(b) ? (["feather-knob", "console-rp"].includes(b) ? "feather-s3" : b) : "waveshare");

/** The Safes to send, from the app's saved list ({chain, address, name}): the link's shape. */
export function linkSafes(saved, chainIds) {
  return saved.filter((s) => chainIds[s.chain]).map((s) => ({
    chainId: chainIds[s.chain], address: s.address.toLowerCase(),
    name: (s.name || "Safe").replace(/[^ -~]/g, "").slice(0, 24) || "Safe",
  }));
}

// The ceremony on three buttons, as the real screens show it (docs/quorum-ui/feather-setup/, drawn by
// tools/board/shots_feather_setup.mjs). Pictures: nothing runs, and no chip is asked anything.
export const CEREMONY = [
  ["01-banner", "A new chip: the console opens the ceremony, not the signing console."],
  ["02-c1", "C1 reads the chip and changes nothing. Each step says what it does before D2 does it."],
  ["05-c3", "C3 locks the chip's configuration: permanent, so it's red, and D2 does nothing yet."],
  ["06-c3-arming", "D0 and D1 held together for 3 s arm the permanent steps for 60 s."],
  ["09-c3-hold", "Then D2 held 3 s does the step. Let go early and nothing happens."],
  ["12-c4-result", "C4: the key is made inside the chip. Nobody, the console included, ever sees it."],
  ["15-c6-result", "C6 seals that key in its slot, so it can never be replaced."],
  ["16-c7-result", "C7: the key's owner address, to compare with the computer setting the console up."],
  ["21-c10-result", "Sealed. The console then pins this chip, and signs with nothing else."],
];

// ----------------------------------------------------------------------------- icons and tabs
// Line icons on a 24 grid, drawn in the text's colour (currentColor), so they follow the theme.
// Built as SVG elements: the app's CSP allows no inline styles.
const ICONS = {
  device: [["rect", { x: 5, y: 2, width: 14, height: 20, rx: 3 }], ["rect", { x: 8, y: 5, width: 8, height: 7, rx: 1 }],
    ["circle", { cx: 9, cy: 17, r: 1.1 }], ["circle", { cx: 12, cy: 17, r: 1.1 }], ["circle", { cx: 15, cy: 17, r: 1.1 }]],
  key: [["circle", { cx: 7.5, cy: 15.5, r: 4.5 }], ["path", { d: "M10.7 12.3 20 3M16.5 6.5l2.5 2.5M13.8 9.2l2 2" }]],
  vault: [["rect", { x: 3, y: 3, width: 18, height: 16, rx: 2 }], ["circle", { cx: 12, cy: 11, r: 4.5 }], ["circle", { cx: 12, cy: 11, r: 1.2 }],
    ["path", { d: "M12 6.5v1.6M12 13.9v1.6M7.5 11h1.6M14.9 11h1.6M7 19v2M17 19v2" }]],
  chip: [["rect", { x: 7, y: 7, width: 10, height: 10, rx: 1.5 }], ["path", { d: "M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4" }]],
  shield: [["path", { d: "M12 3 19 6v5c0 4.4-2.9 8-7 10-4.1-2-7-5.6-7-10V6z" }], ["path", { d: "m9 12 2 2 4-4" }]],
  plug: [["path", { d: "M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4" }]],
  people: [["circle", { cx: 9, cy: 8, r: 3.2 }], ["path", { d: "M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" }], ["circle", { cx: 17, cy: 9, r: 2.5 }],
    ["path", { d: "M16.5 14.2c2.6.2 4.5 2.3 4.5 5" }]],
};
export function icon(name, size = 20) {
  const NS = "http://www.w3.org/2000/svg", el = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
    return e;
  };
  const svg = el("svg", { viewBox: "0 0 24 24", width: size, height: size, fill: "none", stroke: "currentColor", "stroke-width": 1.8,
    "stroke-linecap": "round", "stroke-linejoin": "round", class: "icon", "aria-hidden": "true" });
  for (const [tag, attrs] of ICONS[name]) svg.append(el(tag, attrs));
  return svg;
}

/** tabs: [{id, icon, label, note, panel}]. One panel shows at a time; arrows move between tabs. */
function tabView(ui, tabs, cur, pick) {
  const { h } = ui;
  const btns = tabs.map((t) => h("button", { class: "dtab", type: "button", role: "tab", id: `dtab-${t.id}`, "aria-controls": `dpanel-${t.id}`,
    "aria-selected": String(t.id === cur), tabindex: t.id === cur ? "0" : "-1", onclick: () => pick(t.id) },
    icon(t.icon), h("span", { text: t.label }), t.note || null));
  const bar = h("div", { class: "dtabs", role: "tablist", "aria-label": "The console" }, ...btns);
  bar.addEventListener("keydown", (e) => {
    const i = tabs.findIndex((t) => t.id === cur), d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    pick(tabs[(i + d + tabs.length) % tabs.length].id, true);
  });
  return h("div", {}, bar, ...tabs.map((t) => h("div", { role: "tabpanel", id: `dpanel-${t.id}`, "aria-labelledby": `dtab-${t.id}`,
    hidden: t.id !== cur }, t.panel)));
}

// ----------------------------------------------------------------------------- the page
/**
 * ui: main.mjs's kit, { h, fill, add, badge, ident, steps, short, savedSafes, CHAINS, chainIds,
 * setupLink, releaseList, shortFp, main }.
 */
export function deviceView(ui) {
  const { h, fill, badge, ident, steps, main } = ui;
  const supported = typeof navigator !== "undefined" && "serial" in navigator;
  const connect = h("button", { class: "btn go", type: "button", text: "Connect a device", disabled: !supported });
  const log = steps();
  const body = h("div", {});
  const state = { link: null, port: null, hello: null, status: null, closing: false, relay: null, hi: null, events: [], logs: [], relayEl: null,
    tab: "device" };

  fill(main,
    h("section", { class: "hero" }, h("h1", { text: "Your device" }),
      h("p", { class: "lede", text: "Plug your Picoquorum console into this computer and connect it here. The page shows what it is and which Safes it watches, and can change them. A console with no Wi-Fi reaches Safe's service through this page: keep it open while you use the console." }),
      h("p", { class: "muted", text: "The console shows each one on its own screen and saves it only when you hold its Sign button. Nothing on this page can make it sign, read its key or change its chip." })),
    h("section", { class: "card" }, h("h2", { text: "Connect" }),
      supported
        ? h("p", { class: "muted", text: "Chrome asks which port: pick the one named USB JTAG/serial, usbmodem or Picoquorum." })
        : h("p", { class: "warn-text", text: "This browser can't talk to USB devices. Use Chrome or Edge on a computer. On a phone, or in Safari or Firefox, set up Wi-Fi with the console's own hotspot (below), and practise in the browser." }),
      h("div", { class: "row" }, connect), log.el),
    body,
    practice(ui, null),
    hotspot(ui));

  connect.onclick = async () => {
    connect.disabled = true;
    try {
      const port = await navigator.serial.requestPort({ filters: FILTERS });
      await open(port);
    } catch (e) {
      if (e?.name !== "NotFoundError") log.add("bad", e.message || String(e));      // NotFoundError: the chooser was closed
    } finally {
      connect.disabled = false;
    }
  };

  /** The port opened and watched, or the error that stopped it. */
  async function attach(port) {
    if (state.link) { stopHi(); state.closing = true; await state.link.close(); state.closing = false; state.link = null; }
    const link = new Link(port);
    try { await link.open(); } catch (e) { return e; }
    state.link = link; state.port = port;
    link.onclose = () => { stopHi(); if (!state.closing && state.link === link) lost(); };
    // Only a console-rp sends these. Each is checked before anything goes out (relay.mjs).
    state.relay = new Relay({ cfg: CFG, write: (l) => link.send(l), call: (r) => callService(r), onevent: (e) => relayEvent(e) });
    link.onreq = (m) => state.relay.handle(m);
    link.onlog = (l) => { state.logs.push(l.slice(0, 300)); if (state.logs.length > 40) state.logs.shift(); showRelay(); };
    return null;
  }

  /** The checked request made to its chain's service with this browser's API key (Settings). */
  function callService(r) {
    const name = Object.keys(ui.CHAINS).find((k) => String(ui.CHAINS[k].service || "").replace(/\/+$/, "") === r.base);
    if (!name) throw new Error("no chain here has that service");
    return ui.serviceFor(name).raw(r.method, r.path, r.body);
  }

  /** hi every 2 s, so the console knows its relay is there (link.SEEN_MS). */
  function startHi(max) {
    stopHi();
    if (Number.isInteger(max) && max > 0) state.relay.max = max;
    const link = state.link;
    link.send('{"t":"hi"}');
    state.hi = setInterval(() => link.send('{"t":"hi"}'), HI_MS);
  }
  function stopHi() { if (state.hi) clearInterval(state.hi); state.hi = null; }

  function relayEvent(e) {
    state.events.unshift(e);
    if (state.events.length > 8) state.events.pop();
    showRelay();
  }

  /** The relay card's live parts, filled in place: counts, the last requests, the console's log. */
  function showRelay() {
    const el = state.relayEl;
    if (!el || !state.relay) return;
    const c = state.relay.counts;
    el.counts.textContent = `${c.asked} asked: ${c.answered} answered, ${c.refused} refused, ${c.failed} failed`;
    fill(el.list, ...state.events.map((e) => h("li", { class: "small" },
      e.kind === "answered" ? badge(e.status >= 200 && e.status < 300 ? "ok" : "warn", String(e.status)) : badge("bad", e.kind),
      h("code", { class: "mono", text: ` ${e.method || ""} ${String(e.path || e.url || "").replace(/^\/api\//, "").slice(0, 70)}` }),
      h("span", { class: "muted", text: e.kind === "answered" ? ` ${e.bytes} bytes, ${e.ms} ms` : ` ${e.why}` }))));
    el.log.textContent = state.logs.join("\n");
  }

  async function open(port) {
    const s = log.run("Opening the port");
    const e = await attach(port);
    if (e) return log.done(s, `Couldn't open it: ${e.message}. Another program (tools/fw, mpremote, a serial monitor) may have it open.`, "bad");
    log.done(s, "Port open");
    await greet();
  }

  async function greet() {
    const w = log.run("Asking the console what it is");
    const a = await hello(state.link, 30000, (n) => { w.lastChild.textContent = `Asking the console what it is (${n} s; it may still be starting)`; });
    if (!a) {
      log.done(w, "No answer. It may be an older firmware without the USB link, or in maintenance. Update it with tools/fw push console.", "bad");
      return;
    }
    state.hello = a;
    log.done(w, `${boardName(a.board)}, ${a.image} ${a.version || a.build}`);
    if (a.link) startHi(a.link.max);
    await refresh();
  }

  /** The board restarts after saving, and comes back as a new port: open it when it does. */
  async function lost() {
    const s = log.run("The device went away: it restarts after saving. Waiting for it to come back");
    const info = state.port?.getInfo?.() || {};
    const t0 = Date.now();
    while (Date.now() - t0 < 45000) {
      await new Promise((r) => setTimeout(r, 1500));
      const ports = await navigator.serial.getPorts();
      for (const p of ports) {
        const i = p.getInfo();
        if (i.usbVendorId !== info.usbVendorId || i.usbProductId !== info.usbProductId) continue;
        if (await attach(p)) continue;       // still starting: try again
        log.done(s, "It's back");
        return greet();
      }
    }
    log.done(s, "It didn't come back. Press Connect again once it has started.", "bad");
  }

  async function refresh() {
    const st = await state.link?.request("status", {}, 6000);
    if (!st) return;
    state.status = st;
    render();
  }

  function render() {
    const a = state.hello, st = state.status, inConsole = st.mode === "console";
    state.relayEl = a.link ? relayParts(ui) : null;
    const n = (st.safes || []).length, waiting = (st.safes || []).reduce((t, x) => t + (x.waiting || 0), 0);
    const up = a.link ? true : !!st.wifi?.up;
    const tabs = [
      { id: "device", icon: "device", label: "Device", panel: h("div", {}, deviceCard(ui, a, st, (id) => pick(id)), inConsole ? null : setupNote(ui, st),
        h("p", { class: "row" },
          h("button", { class: "btn", type: "button", text: "Read it again", onclick: () => refresh() }),
          h("button", { class: "btn", type: "button", text: "Disconnect", onclick: async () => {
            stopHi(); state.closing = true; await state.link?.close(); state.link = null; state.closing = false; fill(body); log.add("muted", "Disconnected");
          } }))) },
      inConsole && { id: "signer", icon: "key", label: "Signer", note: st.owner && !st.pinned ? h("span", { class: "dot warn", title: "Not pinned" }) : null,
        panel: signerCard(ui, a, st) },
      inConsole && { id: "safes", icon: "vault", label: "Safes", note: h("span", { class: `count${waiting ? " warn" : ""}`, text: waiting ? `${waiting} waiting` : String(n) }),
        panel: safesCard(ui, a, st, ask) },
      { id: "link", icon: "plug", label: "Connection", note: h("span", { class: `dot ${up ? "ok" : "warn"}`, title: up ? "Connected" : "Not connected" }),
        panel: a.link ? state.relayEl.card : wifiCard(ui, a, st, ask) },
    ].filter(Boolean);
    if (!tabs.some((t) => t.id === state.tab)) state.tab = "device";
    function pick(id, focus) {
      state.tab = id;
      for (const t of tabs) {
        const b = body.querySelector(`#dtab-${t.id}`), p = body.querySelector(`#dpanel-${t.id}`);
        b.setAttribute("aria-selected", String(t.id === id)); b.tabIndex = t.id === id ? 0 : -1; p.hidden = t.id !== id;
        if (focus && t.id === id) b.focus();
      }
    }
    fill(body, tabView(ui, tabs, state.tab, pick));
    const p = main.querySelector("[data-practice]");
    if (p) p.replaceWith(practice(ui, a.board));
    if (a.link) main.querySelector("[data-hotspot]")?.remove();    // no radio, so no hotspot
    showRelay();
  }

  /** An ask: sent, then the console's answer once the person decides on its screen. */
  async function ask(op, payload, out) {
    const k = keysOf(state.hello?.board);
    const s = steps();
    fill(out, s.el);
    const w = s.run(`Sent. On the console: read every page, then hold ${k.yes} for 2 s. ${k.no} says no.`);
    const a = await state.link.request(op, payload, 130000);
    if (!a) return s.done(w, "No answer: the device may have restarted or been unplugged.", "bad");
    if (!a.ok) return s.done(w, `Not saved: ${a.why}`, "bad");
    s.done(w, "Accepted on the console and saved. It restarts with it now.");
    // A console-rp restarts behind its CH343P, which stays: the port doesn't go, so ask again.
    if (state.hello?.link) setTimeout(() => greet(), 2500);
  }
}

function deviceCard(ui, a, st, go) {
  const { h, badge, ident, shortFp, short } = ui;
  const rel = h("span", {});
  if (a.release) {
    // Information, as on the Releases page: the console says what it is, and could lie.
    Promise.all([ui.releaseList().catch(() => []), ui.browserRelease()]).then(([list, here]) => {
      const hit = list.find((x) => Object.values(x.fingerprints || {}).includes(a.release));
      ui.fill(rel, hit ? badge("ok", `Release ${hit.version}`) : badge("muted", "Not a published release"),
        here === a.release ? badge("ok", "Same as the console in this browser") : null);
    });
  }
  return h("section", { class: "card" }, h("h2", { text: "Device" }),
    h("div", { class: "addr" }, a.release ? ident("0x" + a.release, 36) : null,
      h("div", { class: "addr-body" },
        h("div", { class: "addr-top" }, h("strong", { text: boardName(a.board) }), badge("eth", a.image), rel),
        h("div", { class: "small" }, h("span", { class: "muted", text: "firmware " }), h("code", { class: "mono", text: `${a.version || "-"} · build ${a.build}` }),
          a.release ? h("span", {}, h("span", { class: "muted", text: " · release " }), h("code", { class: "mono", text: shortFp(a.release) })) : null))),
    h("p", { class: "small muted" }, "The picture and the eight digits are the console's Device screen's Release. ",
      h("a", { href: "#/releases", text: "Releases" }), " says which release has them."),
    st.mode === "console" ? glance(ui, a, st, go) : null,
    st.mode === "setup" ? h("p", {}, badge("warn", "Wi-Fi setup"), " It has no network yet, so it shows its hotspot: send it one below, or join the hotspot from a phone.") : null,
    st.mode === "stopped" ? h("p", {}, badge("bad", "Stopped"), " The console didn't start. Its screen and error.log say why; tools/fw logs reads it in maintenance.") : null);
}

/** The console in three lines, each opening its tab: its signer, its Safes, its way out. */
function glance(ui, a, st, go) {
  const { h, badge, short } = ui;
  const safes = st.safes || [], waiting = safes.reduce((t, x) => t + (x.waiting || 0), 0);
  const line = (ic, title, what, extra, tab, label) => h("li", {}, h("span", { class: `glance-icon ${ic}` }, icon(ic, 22)),
    h("div", { class: "addr-body" }, h("div", { class: "addr-top" }, h("strong", { text: title }), ...extra), h("div", { class: "small muted", text: what })),
    h("button", { class: "mini", type: "button", text: label, onclick: () => go(tab) }));
  return h("ul", { class: "glance" },
    line("key", "Signer", st.owner ? `${short(st.owner)}: the address a Safe lists among its signers` : "No key yet: it makes one on its own screen",
      [st.owner ? (st.pinned ? badge("ok", "Pinned") : badge("warn", "Not pinned")) : badge("warn", "No key")], "signer", "Its signer"),
    line("vault", safes.length === 1 ? "1 Safe" : `${safes.length} Safes`, safes.length ? safes.map((x) => x.name).join(", ") : "None yet",
      [waiting ? badge("warn", `${waiting} waiting`) : null], "safes", "Its Safes"),
    line("plug", "Connection", a.link ? "Through this page: keep it open while you use the console" : st.wifi?.up ? `Wi-Fi: ${st.wifi.ssid}` : "No Wi-Fi",
      [a.link || st.wifi?.up ? badge("ok", a.link ? "Relaying" : "Online") : badge("warn", "Offline")], "link", "How it connects"));
}

/** The relay's card (a console-rp): its parts, filled by showRelay as requests go by. */
function relayParts(ui) {
  const { h, badge } = ui;
  const counts = h("p", { class: "small muted" }), list = h("ul", { class: "relay-log" }), log = h("pre", { class: "small mono" });
  const card = h("section", { class: "card" }, h("h2", { text: "Its way to Safe's service: this page" }),
    h("p", {}, badge("ok", "Relaying"), " Keep this page open. The console has no radio: it reaches Safe's service only through this page, which makes each call for it."),
    h("p", { class: "small muted", text: "Only the console's own calls go out: its Safes, their queue, and its confirmations, to the services it pins. The API key in Settings goes on them, and never down the cable. The console checks every answer itself, as it checks Safe's service." }),
    counts, list,
    h("details", {}, h("summary", { text: "The console's log" }), log));
  return { card, counts, list, log };
}

// The chip as the console read it at boot (status "chip"): its model and locks, in a line.
export function chipFacts(c) {
  if (!c || !c.model) return "";
  const lock = (v, yes, no) => (v == null ? null : v ? yes : no);
  return [String(c.model), lock(c.configLocked, "config locked", "config open"), lock(c.dataLocked, "data locked", "data open"),
    c.keySealed ? "key slot sealed" : "key slot open"].filter(Boolean).join(" · ");
}

function signerCard(ui, a, st) {
  const { h, badge, ident, copyButton } = ui;
  const facts = chipFacts(st.chip);
  const own = a.board === "console-rp";     // makes its key on its own screen, and pins itself (keypick_rp.py)
  const part = (ic, title, ...body) => h("div", { class: "part" }, h("span", { class: "glance-icon" }, icon(ic, 22)), h("div", { class: "addr-body" }, h("strong", { text: title }), ...body));
  const what = h("p", { class: "muted", text: "The console signs with a key made inside its chip. On every chain the same small contract checks that key's signatures. That contract's address is the console's signer: it's what you add to a Safe, and what the Safe lists among its signers." });
  if (!st.owner) {
    return h("section", { class: "card" }, h("h2", { text: "Signer" }), what,
      part("chip", "Key, in the chip",
        h("p", {}, badge("warn", "No key yet"), st.serial ? ` chip ${st.serial}` : " No chip answered."),
        facts ? h("p", { class: "small muted", "data-chip": "", text: facts }) : null,
        own
          ? h("p", { class: "muted", text: "This console makes its key on its own screen: ▲ Make, then hold ▲ on the red Keep page. The chip makes it, and only its public half leaves the chip. Nobody, this page included, ever sees the key." })
          : h("p", { class: "muted", text: "The key is made in the ceremony, before the console is handed over: the ceremony image and tools/fw ceremony start, on a computer. Nobody, this page included, ever sees the key." }),
        own ? null : h("p", { class: "small", text: "To see how it goes, practise on the device: Practice on its No key screen, or Device then Practice. The ten steps, the arm and the holds, with its own buttons. It writes nothing to the chip." })));
  }
  return h("section", { class: "card" }, h("h2", { text: "Signer" }), what,
    part("chip", "Key, in the chip",
      h("div", { class: "addr-top" }, st.pinned ? badge("ok", "Pinned") : badge("warn", "Not pinned"),
        st.counter != null ? badge("muted", `used ${st.counter} times`) : null),
      h("div", { class: "small muted", text: `Chip ${st.serial} (${st.profile}${facts ? `: ${facts}` : ""}). Only the key's public half ever leaves it.` }),
      st.pinned ? null : own
        ? h("p", { class: "small", text: "Not pinned: the console signs nothing until it is. Finish the key on its screen: it pins itself." })
        : h("p", { class: "small" }, "Not pinned: the console signs nothing until it is. ", h("code", { text: "tools/fw pin" }), " on the computer that set it up pins this chip.")),
    part("shield", "Signer address, the same on every chain",
      h("div", { class: "addr-line" }, ident(st.owner, 24), h("code", { class: "mono", text: st.owner }), copyButton(st.owner)),
      h("div", { class: "small muted", text: "The console's Key screen shows this picture. It's a contract, not a wallet: never send funds to it." })),
    st.key ? h("p", {}, h("a", { class: "btn", href: `#/k/${st.key}`, text: "Add it to a Safe" }),
      " ", h("span", { class: "small muted", text: "A new Safe with it as a signer, or a proposal to add it to one." })) : null);
}

function wifiCard(ui, a, st, ask) {
  const { h, badge } = ui;
  const w = st.wifi || {};
  const ssid = h("input", { type: "text", id: "dev-ssid", autocomplete: "off", spellcheck: "false", maxlength: "32" });
  const pass = h("input", { type: "password", id: "dev-pass", autocomplete: "off", maxlength: "64" });
  const out = h("div", {});
  const send = h("button", { class: "btn go", type: "button", text: "Send to the device" });
  send.onclick = () => {
    const s = ssid.value.trim();
    if (!s) return ssid.focus();
    ask("wifi", { ssid: s, pass: pass.value }, out);
    pass.value = "";
  };
  return h("section", { class: "card" }, h("h2", { text: "Wi-Fi" }),
    h("p", {}, w.up ? badge("ok", `On ${w.ssid}`) : badge(st.mode === "setup" ? "warn" : "muted", st.mode === "setup" ? "No network yet" : "Not connected"),
      (w.saved || []).length ? h("span", { class: "small muted", text: ` saved: ${w.saved.join(", ")}` }) : null),
    h("label", { for: "dev-ssid", text: "Network name" }), ssid,
    h("label", { for: "dev-pass", text: "Password" }), pass,
    h("p", { class: "small muted", text: "Empty for an open network. It goes down the cable to the console only; the page keeps no copy." }),
    h("div", { class: "row" }, send), out);
}

// The most Safes a console watches (firmware/policy.py MAX_SAFES): each is a queue and its decoded
// transactions in its RAM.
export const MAX_SAFES = 4;

/**
 * The console keeps one list of Safes, and a safes ask replaces all of it. So the card is that one
 * list: what the console watches now, ticked, then the Safes saved in this browser, not ticked. What
 * stays ticked is what it will watch, and the page says what that adds and drops before it sends.
 * A Safe on the console that this browser never saved stays on the list: it used to have no box, so
 * sending another Safe dropped it without a word.
 */
export function safeRows(now, saved, chainIds) {
  const id = (c, a) => `${c}:${String(a).toLowerCase()}`;
  const rows = (now || []).map((s) => ({ chainId: s.chainId, address: String(s.address).toLowerCase(), name: s.name || "Safe", on: true, live: s }));
  for (const x of linkSafes(saved, chainIds))
    if (!rows.some((r) => id(r.chainId, r.address) === id(x.chainId, x.address))) rows.push({ ...x, on: false, live: null });
  return rows;
}

function safesCard(ui, a, st, ask) {
  const { h, fill, badge, ident, short, copyButton, explorer } = ui;
  const chainKey = (id) => Object.keys(ui.chainIds).find((c) => ui.chainIds[c] === id);
  const k = keysOf(a.board);
  const rows = safeRows(st.safes, ui.savedSafes(), ui.chainIds);
  const out = h("div", {}), sum = h("p", {});
  const send = h("button", { class: "btn go", type: "button", text: "Send this list to the console" });
  const boxes = rows.map((r) => h("input", { type: "checkbox", checked: r.on, "aria-label": `${r.name} on the console` }));
  const items = rows.map((r, i) => {
    const s = r.live, c = chainKey(r.chainId);
    return h("li", { class: "pick" }, h("label", { class: "pick-box" }, boxes[i], h("span", { class: "glance-icon vault" }, icon("vault", 22))),
      h("div", { class: "addr-body" },
        h("div", { class: "addr-top" }, h("strong", { text: r.name }), badge("muted", ui.chainName(r.chainId)),
          s ? badge("ok", "On the console") : badge("muted", "Saved in this browser"),
          s?.waiting ? badge("warn", `${s.waiting} waiting`) : null),
        h("div", { class: "addr-line" }, ident(r.address, 20), h("code", { class: "mono", text: r.address }), copyButton(r.address),
          c ? explorer(c, "address", r.address) : null, c ? h("a", { class: "mini", href: `#/safe/${c}/${r.address}`, text: "Open" }) : null),
        s ? h("div", { class: "addr-line small" }, icon("people", 16),
          h("span", { text: s.threshold ? `Needs ${s.threshold} of its ${s.owners} signers.` : "Its signers: not read yet." }),
          s.isOwner === true ? badge("ok", "This console is one") : s.isOwner === false ? badge("warn", "This console isn't one yet") : null,
          s.ok ? null : h("span", { class: "muted", text: ` · ${s.err}` })) : null));
  });
  const picked = () => rows.filter((r, i) => boxes[i].checked);
  function update() {
    const p = picked(), adds = p.filter((r) => !r.live), drops = rows.filter((r, i) => r.live && !boxes[i].checked);
    const names = (l) => l.map((r) => r.name).join(", ");
    send.disabled = !p.length || p.length > MAX_SAFES || (!adds.length && !drops.length);
    if (!p.length) return fill(sum, h("span", { class: "warn-text", text: "Tick at least one Safe." }));
    if (p.length > MAX_SAFES) return fill(sum, h("span", { class: "warn-text", text: `A console watches ${MAX_SAFES} Safes at most: untick ${p.length - MAX_SAFES}.` }));
    if (!adds.length && !drops.length) return fill(sum, h("span", { class: "muted", text: "That's the list it has now. Tick a Safe to add it, untick one to drop it." }));
    fill(sum, h("strong", { text: `It will watch ${p.length === 1 ? "1 Safe" : `${p.length} Safes`}: ${names(p)}.` }),
      adds.length ? h("span", { text: ` Adds ${names(adds)}.` }) : null,
      drops.length ? h("span", { class: "warn-text", text: ` Drops ${names(drops)}.` }) : null);
  }
  for (const b of boxes) b.onchange = update;
  update();
  send.onclick = () => ask("safes", { safes: picked().map(({ chainId, address, name }) => ({ chainId, address, name })) }, out);
  return h("section", { class: "card" }, h("h2", { text: "Safes on this console" }),
    h("p", { class: "muted", text: `It watches up to ${MAX_SAFES} Safes, and signs for each one it's a signer of. It keeps one list: sending replaces the whole list with the Safes ticked here.` }),
    rows.length
      ? h("ul", { class: "owners" }, ...items)
      : h("p", {}, badge("warn", "None yet"), " The console has no Safe, and this browser has none saved."),
    h("p", { class: "small muted" }, "To add a Safe that isn't listed, ", h("a", { href: "#/", text: "open it" }), " and save it, then come back."),
    rows.length ? sum : null,
    rows.length ? h("div", { class: "row" }, send) : null,
    rows.length ? h("p", { class: "small muted", text: `The console then shows each Safe on a page of its own, and last the list it replaces. See each with ${k.page}, then hold ${k.yes} for 2 s to save it; ${k.no} says no. It restarts with the new list.` }) : null,
    out);
}

function setupNote(ui, st) {
  const { h } = ui;
  return h("section", { class: "card" }, h("h2", { text: "Next" }),
    h("p", { class: "muted", text: "Once it's on Wi-Fi it restarts as the console. Connect again then, to see its key and send it the Safes it watches." }));
}

function practice(ui, board) {
  const { h } = ui;
  const b = twinBoard(board);
  return h("section", { class: "card", "data-practice": "" }, h("h2", { text: "Practise in the browser first" }),
    h("p", { class: "muted" }, "The console in your browser runs the same firmware, with a passkey as its key. Add a Safe there, then review and sign a test transaction on testnet, with the same buttons as ",
      board ? `your ${boardName(board)}.` : "your device."),
    h("p", {}, h("a", { class: "btn", href: `../console/?board=${b}`, text: "Open the console in the browser" })),
    board === "console-rp" ? null : ceremony(ui));
}

// How a key is made on the boards an organizer sets up. A console-rp makes its own on its screen
// (its Signer tab says how), so it gets none of this.
function ceremony(ui) {
  const { h } = ui;
  return h("div", {},
    h("h3", { text: "How a new key is made: the ceremony" }),
    h("p", { class: "small muted", text: "The organizer makes the key before the console is handed over, on the ceremony image. The steps go like this. These are pictures of the real screens: nothing runs here, and no chip is asked anything." }),
    h("ol", { class: "shots" }, ...CEREMONY.map(([f, cap]) => h("li", {},
      h("img", { src: `../quorum-ui/feather-setup/${f}.png`, alt: cap, loading: "lazy", width: "300", height: "135" }),
      h("span", { class: "small", text: cap })))),
    h("p", { class: "small muted", text: "To try the steps with the buttons, open Device, then Practice, on the console: in the browser or on the device. It writes nothing." }));
}

function hotspot(ui) {
  const { h } = ui;
  return h("section", { class: "card quiet", "data-hotspot": "" }, h("h2", { text: "Without a computer: the hotspot" }),
    h("p", { class: "muted", text: "A console with no Wi-Fi shows a QR code and its own hotspot. Scan it with a phone, pick your network and type its password there. The console joins it, saves it and restarts." }));
}
