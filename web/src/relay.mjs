// The app as console-rp's relay (docs/USB-LINK.md, "The relay (console-rp)"). The console has no radio:
// it asks, one {"t":"req"} line on its USB-C, and this page makes the call for it. The rules are
// tools/relay/relay.py's: only the paths firmware/txservice.py uses, only under the services
// firmware/quorum_cfg.py pins (CFG, config.gen.mjs), and the API key only on requests to Safe's own
// service, never down the cable. No DOM here, so web/test.mjs drives it.
//
// Nothing the console sends is trusted, and nothing that comes back is trusted by the console: it
// rebuilds every hash itself, as it does with Safe's service on the Wi-Fi boards (AGENTS.md rule 1).
export const MAX_URL = 400;
export const MAX_POST = 4096;
export const DEFAULT_MAX = 16 * 1024;     // the longest answer until hello says the console's (link.max)
export const UPSTREAM_MS = 12000;         // the console gives up at 15 s (link.TIMEOUT_MS): answer before that
export const HI_MS = 2000;                // the console counts the relay gone after 15 s of nothing (link.SEEN_MS)
const ADDR = "0x[0-9a-fA-F]{40}";
export const PATHS = [
  ["GET", new RegExp(`^/api/v1/safes/${ADDR}/$`)],
  ["GET", new RegExp(`^/api/v2/safes/${ADDR}/multisig-transactions/\\?executed=false&nonce__gte=\\d{1,20}&ordering=nonce&limit=\\d{1,2}(&offset=\\d{1,2})?$`)],
  ["POST", /^\/api\/v1\/multisig-transactions\/0x[0-9a-fA-F]{64}\/confirmations\/$/],
];

export const bases = (cfg) => Object.values(cfg.services || {}).map((b) => String(b).replace(/\/+$/, ""));

/** link.pinned's rules: plain ASCII, short, and nothing a server might read as something else. */
export function plain(url) {
  if (typeof url !== "string" || url.length > MAX_URL) return false;
  for (let i = 0; i < url.length; i++) { const c = url.charCodeAt(i); if (c < 33 || c >= 127) return false; }
  return !["..", "@", "#", "\\"].some((s) => url.includes(s));
}

/** A request line from the console -> {id, method, url, base, path, body}. Throws Error(why). */
export function checkReq(m, cfg) {
  if (!m || typeof m !== "object" || Array.isArray(m) || m.t !== "req" || !Number.isInteger(m.id)) throw new Error("not a request");
  const { m: method, url, body } = m;
  if (!["GET", "POST"].includes(method) || !plain(url)) throw new Error("not a plain GET or POST");
  const base = bases(cfg).find((b) => url.startsWith(b + "/"));
  if (!base) throw new Error("not a pinned service");
  const path = url.slice(base.length);
  if (!PATHS.some(([mm, rx]) => mm === method && rx.test(path))) throw new Error("not a path the console uses");
  if (method === "GET") {
    if (body != null) throw new Error("a GET with a body");
    return { id: m.id, method, url, base, path, body: null };
  }
  if (typeof body !== "string" || body.length > MAX_POST) throw new Error(`a POST body is JSON text of at most ${MAX_POST} bytes`);
  let b;
  try { b = JSON.parse(body); } catch { throw new Error("a POST body that isn't JSON"); }
  if (!(b && typeof b === "object" && !Array.isArray(b) && Object.keys(b).length === 1 && typeof b.signature === "string"
        && /^0x[0-9a-fA-F]{2,8000}$/.test(b.signature)))
    throw new Error('a confirmation is {"signature": "0x..."} and nothing else');
  return { id: m.id, method, url, base, path, body };
}

// ASCII only, as relay.py's json.dumps writes it: every character past 0x7f as a \u escape (a pair
// past 0xffff). The console undoes them in place (link._unescape).
const ascii = (s) => s.replace(/[\u0080-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));

/** The answer line: what the service said, or status 0 when it's longer than the console reads. */
export function answerLine(id, status, text, max = DEFAULT_MAX) {
  const line = ascii(JSON.stringify({ t: "res", id, status, body: String(text) }));
  return line.length <= max ? line : failLine(id, `answer too big: ${line.length} bytes`);
}
export const failLine = (id, err) => ascii(JSON.stringify({ t: "res", id: Number.isInteger(id) ? id : null, status: 0, err: String(err).slice(0, 80) }));

/**
 * One console's relay. write(line) sends a line down the cable; call(r) makes the checked request r
 * and returns {status, text}, or throws when nothing came back. onevent gets each request's outcome.
 */
export class Relay {
  constructor({ cfg, write, call, onevent = () => {} }) {
    Object.assign(this, { cfg, write, call, onevent, max: DEFAULT_MAX });
    this.counts = { asked: 0, answered: 0, refused: 0, failed: 0 };
  }

  async handle(m) {
    this.counts.asked++;
    let r;
    try {
      r = checkReq(m, this.cfg);
    } catch (e) {
      this.counts.refused++;
      this.write(failLine(m?.id, e.message));
      this.onevent({ kind: "refused", id: m?.id, why: e.message, url: String(m?.url ?? "").slice(0, 120) });
      return;
    }
    const t0 = Date.now();
    let got;
    try {
      got = await this.call(r);
    } catch (e) {
      this.counts.failed++;
      const err = e?.name === "AbortError" ? "no answer in 12 s" : String(e?.message || e).slice(0, 60);
      this.write(failLine(r.id, err));
      this.onevent({ kind: "failed", id: r.id, method: r.method, path: r.path, why: err, ms: Date.now() - t0 });
      return;
    }
    const line = answerLine(r.id, got.status, got.text, this.max);
    this.write(line);
    // A quote inside a body is escaped (\"), so this can only be failLine's own text.
    const tooBig = line.includes('"status":0,"err":"answer too big');
    this.counts[tooBig ? "failed" : "answered"]++;
    this.onevent({ kind: tooBig ? "failed" : "answered", id: r.id, method: r.method, path: r.path, status: tooBig ? 0 : got.status,
                   why: tooBig ? "answer too big for the console" : "", bytes: line.length, ms: Date.now() - t0 });
  }
}
