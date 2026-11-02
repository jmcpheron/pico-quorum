// #/device: a PicoQuorum console on this computer's USB, through Web Serial (Chrome and Edge on a
// computer). The page talks the console's USB link (firmware/usblink.py, docs/USB-LINK.md): it
// reads what the console is and knows, and can send it a Wi-Fi network and the Safes it watches.
// The console shows each on its own screen and saves it only when the person holds D2 there.
// Nothing here can make the console sign, and nothing reads its key: the link has no such request.
// Everything the console sends is untrusted, and drawn with textContent (h() in main.mjs).

// ----------------------------------------------------------------------------- the link
// USB vendor ids the chooser offers: Espressif (an S3's own USB), Adafruit, Raspberry Pi, WCH (CH34x).
export const FILTERS = [0x303a, 0x239a, 0x2e8a, 0x1a86].map((usbVendorId) => ({ usbVendorId }));
const MAX_BUF = 65536;

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
  }

  async open() {
    await this.port.open({ baudRate: 115200 });
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

  line(l) {
    if (!l.startsWith('{"pq":')) { if (l) this.onlog?.(l); return; }
    let a;
    try { a = JSON.parse(l); } catch { return; }
    const w = this.waiting.get(a.id);
    if (w) { this.waiting.delete(a.id); w(a); }
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
  "picoquorum-key": ["PicoQuorumKey", "D0", "D1", "D2"],
  "feather-s3": ["Feather ESP32-S3 Reverse TFT", "D0", "D1", "D2"],
  "feather-knob": ["ESP32-S3 TFT Feather with a knob", "Boot", "a turn", "the knob's push"],
  waveshare: ["Pico with the Waveshare 1.3\" screen", "Y", "the joystick", "A"],
  build1: ["Build 1", "B", "a turn", "the knob, pressed down"],
  esp32: ["ESP32 with a knob", "B", "a turn", "the knob, pressed down"],
};
export const boardName = (b) => (BOARDS[b] || [b || "an unknown board"])[0];
export const keysOf = (b) => { const k = BOARDS[b] || BOARDS.waveshare; return { no: k[1], page: k[2], yes: k[3] }; };
/** The console page's body for this board: three buttons, or the Pico's. */
export const twinBoard = (b) => (["picoquorum-key", "feather-s3", "feather-knob"].includes(b) ? (b === "feather-knob" ? "feather-s3" : b) : "waveshare");

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
  const state = { link: null, port: null, hello: null, status: null, closing: false };

  fill(main,
    h("section", { class: "hero" }, h("h1", { text: "Your device" }),
      h("p", { class: "lede", text: "Plug your PicoQuorum console into this computer and connect it here. The page reads what it is, and can send it your Wi-Fi and the Safes it watches." }),
      h("p", { class: "muted", text: "The console shows each one on its own screen and saves it only when you hold its Sign button. Nothing on this page can make it sign, read its key or change its chip." })),
    h("section", { class: "card" }, h("h2", { text: "Connect" }),
      supported
        ? h("p", { class: "muted", text: "Chrome asks which port: pick the one named USB JTAG/serial, usbmodem or PicoQuorum." })
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
    if (state.link) { state.closing = true; await state.link.close(); state.closing = false; state.link = null; }
    const link = new Link(port);
    try { await link.open(); } catch (e) { return e; }
    state.link = link; state.port = port;
    link.onclose = () => { if (!state.closing && state.link === link) lost(); };
    return null;
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
    const a = state.hello, st = state.status;
    fill(body,
      deviceCard(ui, a, st),
      st.mode === "console" ? keyCard(ui, a, st) : null,
      wifiCard(ui, a, st, ask),
      st.mode === "console" ? safesCard(ui, a, st, ask) : setupNote(ui, st),
      h("p", { class: "row" },
        h("button", { class: "btn", type: "button", text: "Read it again", onclick: () => refresh() }),
        h("button", { class: "btn", type: "button", text: "Disconnect", onclick: async () => {
          state.closing = true; await state.link?.close(); state.link = null; state.closing = false; fill(body); log.add("muted", "Disconnected");
        } })));
    const p = main.querySelector("[data-practice]");
    if (p) p.replaceWith(practice(ui, a.board));
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
  }
}

function deviceCard(ui, a, st) {
  const { h, badge, ident, shortFp } = ui;
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
    st.mode === "setup" ? h("p", {}, badge("warn", "Wi-Fi setup"), " It has no network yet, so it shows its hotspot: send it one below, or join the hotspot from a phone.") : null,
    st.mode === "stopped" ? h("p", {}, badge("bad", "Stopped"), " The console didn't start. Its screen and error.log say why; tools/fw logs reads it in maintenance.") : null);
}

function keyCard(ui, a, st) {
  const { h, badge, ident } = ui;
  if (!st.owner) {
    return h("section", { class: "card" }, h("h2", { text: "Key" }),
      h("p", {}, badge("warn", "No key yet"), st.serial ? ` chip ${st.serial}` : " No chip answered."),
      h("p", { class: "muted", text: "A new chip's key is made on the console itself, in the ceremony: see the pictures below. Nobody, this page included, ever sees the key." }));
  }
  return h("section", { class: "card" }, h("h2", { text: "Key" }),
    h("div", { class: "addr" }, ident(st.owner, 36),
      h("div", { class: "addr-body" },
        h("div", { class: "addr-top" }, h("strong", { text: "Its owner address" }),
          st.pinned ? badge("ok", "Pinned") : badge("warn", "Not pinned"),
          st.counter != null ? badge("muted", `used ${st.counter} times`) : null),
        h("div", { class: "addr-line" }, h("code", { class: "mono", text: st.owner })))),
    h("p", { class: "small muted", text: `Chip ${st.serial} (${st.profile}). The console shows this picture on its Key screen; it's a signer contract, not a wallet: never send funds to it.` }),
    st.pinned ? null : h("p", { class: "small" }, "Not pinned: the console signs nothing until it is. ", h("code", { text: "tools/fw pin" }), " on the computer that set it up pins this chip."),
    st.key ? h("p", {}, h("a", { class: "btn", href: `#/k/${st.key}`, text: "Make it an owner of a Safe" }),
      " ", h("span", { class: "small muted", text: "Deploy its signer, then propose adding it." })) : null);
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

function safesCard(ui, a, st, ask) {
  const { h, fill, badge, ident, short } = ui;
  const now = st.safes || [];
  const saved = ui.savedSafes().filter((s) => ui.chainIds[s.chain]);
  const boxes = saved.map((s, i) => h("label", { class: "check" },
    h("input", { type: "checkbox", "data-i": String(i), checked: now.some((x) => x.address === s.address.toLowerCase() && x.chainId === ui.chainIds[s.chain]) }),
    ident(s.address, 20), h("span", { text: ` ${s.name || short(s.address)} ` }), h("span", { class: "muted small", text: `${ui.CHAINS[s.chain].name} · ${short(s.address)}` })));
  const out = h("div", {});
  const send = h("button", { class: "btn go", type: "button", text: "Send to the device" });
  send.onclick = () => {
    const picked = boxes.map((b, i) => (b.querySelector("input").checked ? saved[i] : null)).filter(Boolean);
    if (!picked.length) return fill(out, h("p", { class: "warn-text", text: "Pick at least one Safe." }));
    if (picked.length > 4) return fill(out, h("p", { class: "warn-text", text: "A console watches four Safes at most." }));
    ask("safes", { safes: linkSafes(picked, ui.chainIds) }, out);
  };
  return h("section", { class: "card" }, h("h2", { text: "Safes it watches" }),
    now.length
      ? h("ul", { class: "owners" }, ...now.map((s) => h("li", { class: "with-ident" }, ident(s.address, 28),
          h("div", { class: "addr-body" },
            h("div", { class: "addr-top" }, h("strong", { text: s.name }), badge("muted", ui.chainName(s.chainId)),
              s.isOwner === true ? badge("ok", "This key is an owner") : s.isOwner === false ? badge("warn", "Not an owner yet") : null,
              s.threshold ? badge("muted", `${s.threshold} of ${s.owners}`) : null,
              s.waiting ? badge("warn", `${s.waiting} waiting`) : null),
            h("div", { class: "small" }, h("code", { class: "mono", text: s.address }), s.ok ? null : h("span", { class: "muted", text: ` · ${s.err}` }))))))
      : h("p", {}, badge("warn", "None yet"), " The console shows Your key is ready, or No Safe."),
    st.safesFrom ? h("p", { class: "small muted", text: `From ${st.safesFrom}.` }) : null,
    h("h3", { text: "Send it the Safes to watch" }),
    saved.length
      ? h("div", { class: "checks" }, ...boxes)
      : h("p", { class: "small muted" }, "No saved Safes in this browser. ", h("a", { href: "#/", text: "Open a Safe" }), " and save it, then come back."),
    h("p", { class: "small muted", text: "Up to four. They replace the ones it watches now. The console lists them page by page before you hold to save." }),
    saved.length ? h("div", { class: "row" }, send) : null, out);
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
    h("h3", { text: "How a new key is made: the ceremony" }),
    h("p", { class: "small muted", text: "On a console with a new chip, the steps go like this. These are pictures of the real screens: nothing runs here, and no chip is asked anything." }),
    h("ol", { class: "shots" }, ...CEREMONY.map(([f, cap]) => h("li", {},
      h("img", { src: `../quorum-ui/feather-setup/${f}.png`, alt: cap, loading: "lazy", width: "300", height: "135" }),
      h("span", { class: "small", text: cap })))));
}

function hotspot(ui) {
  const { h } = ui;
  return h("section", { class: "card quiet" }, h("h2", { text: "Without a computer: the hotspot" }),
    h("p", { class: "muted", text: "A console with no Wi-Fi shows a QR code and its own hotspot. Scan it with a phone, pick your network and type its password there. The console joins it, saves it and restarts." }));
}
