// A Trust M attestation bundle (tools/fw attest), checked in the browser: the same checks as
// tools/quorum verify (tools/mock-tx-service/attest.mjs), without Node's X.509. web/test.mjs runs both
// on every bundle in docs/mainnet/attest/ and requires the same verdict line by line.
//
// What a pass means is what it means there: a genuine Infineon Trust M signed a statement binding this
// UID to the key in E0F1, the record names that key, and the owner address follows from it. The
// lifecycle lines are what the chip told the board that read it. docs/mainnet/THREAT-MODEL.md.
import { p256 } from "@noble/curves/p256";
import { sha256 } from "@noble/hashes/sha2";
import { bytesToHex, concatBytes, hexToBytes, utf8ToBytes } from "@noble/hashes/utils";
import { getAddress } from "viem";
import { p256Owner } from "../../tools/mock-tx-service/sigs.mjs";

// Infineon's CAs by issuer name, as firmware/tmcfg.py and attest.mjs pin them.
export const CAS = {
  "Infineon OPTIGA(TM) Trust M CA 101": [
    "97337734AD7423A14BF40FD4EE1D27AF8ED05AE87970C74DFE29889B499AD2D0",
    "1EA249AE7910F052C59D85514A8215E2D63E4730CDFB5CC153BBCC00A7E6408B"],
};
const KEY = 0xe0f1, OPERATIONAL = 0x07, LCSO_BELOW_OP = "e1fc07";
const SPARES = ["E0F2", "E0F3", "E0FC", "E0FD", "E0E1", "E0E8", "E0EF", "E120", "E121", "E122", "E123",
  ...Array.from({ length: 10 }, (_, i) => (0xf1d2 + i).toString(16).toUpperCase()), "F1E0", "F1E1"];
const BIND_DOMAIN = utf8ToBytes("PicoQuorum Trust M key binding v1");
const LIVE_DOMAIN = utf8ToBytes("PicoQuorum Trust M attest v1");

const hex = (h) => hexToBytes((h || "").replace(/^0x/, ""));
const b32 = (big) => hexToBytes(big.toString(16).padStart(64, "0"));
const big = (b) => BigInt("0x" + (bytesToHex(b) || "0"));
const eq = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
const u16 = (b, i) => (b[i] << 8) | b[i + 1];
const u32 = (b, i) => ((b[i] << 24) >>> 0) + (b[i + 1] << 16) + (b[i + 2] << 8) + b[i + 3];

// ----------------------------------------------------------------------------- just enough DER
// -> {tag, start, header, len, end}: one TLV at i.
function tlv(b, i) {
  const tag = b[i];
  let len = b[i + 1], h = 2;
  if (len & 0x80) {
    const n = len & 0x7f;
    len = 0;
    for (let k = 0; k < n; k++) len = len * 256 + b[i + 2 + k];
    h = 2 + n;
  }
  if (i + h + len > b.length) throw new Error("DER runs past its end");
  return { tag, start: i, header: h, len, end: i + h + len, body: b.subarray(i + h, i + h + len) };
}
function children(b) {
  const out = [];
  for (let i = 0; i < b.length;) {
    const t = tlv(b, i);
    out.push(t);
    i = t.end;
  }
  return out;
}
const OID_CN = "550403";
function commonName(name) {                // Name: SEQUENCE of SET of SEQUENCE {OID, value}
  for (const rdn of children(name.body)) for (const atv of children(rdn.body)) {
    const [oid, val] = children(atv.body);
    if (bytesToHex(oid.body) === OID_CN) return new TextDecoder().decode(val.body);
  }
  return null;
}
function time(t) {                           // UTCTime YYMMDDHHMMSSZ or GeneralizedTime
  const s = new TextDecoder().decode(t.body);
  const y = t.tag === 0x17 ? (Number(s.slice(0, 2)) < 50 ? "20" : "19") + s.slice(0, 2) : s.slice(0, 4);
  const r = t.tag === 0x17 ? s.slice(2) : s.slice(4);
  return `${y}-${r.slice(0, 2)}-${r.slice(2, 4)}`;
}

// An X.509 certificate with a P-256 key, signed with ecdsa-with-SHA256. -> the parts the checks use.
export function parseCert(der) {
  const cert = tlv(der, 0);
  const [tbs, , sigVal] = children(cert.body);
  const f = children(tbs.body);
  const k = f[0].tag === 0xa0 ? 1 : 0;       // [0] version, when present
  const [serial, , issuer, validity, subject, spki] = f.slice(k);
  const [algo, keyBits] = children(spki.body);
  const pub = keyBits.body.subarray(1);      // BIT STRING: unused-bits byte, then 04 | x | y
  if (pub.length !== 65 || pub[0] !== 4) throw new Error("not an uncompressed P-256 key");
  if (!bytesToHex(algo.body).includes("2a8648ce3d030107")) throw new Error("the key is not on P-256");
  const [r, s] = children(tlv(sigVal.body.subarray(1), 0).body);      // BIT STRING: 00, then SEQUENCE {r, s}
  const [from, to] = children(validity.body);
  return {
    tbs: cert.body.subarray(tbs.start, tbs.end), r: big(r.body), s: big(s.body), pub,
    issuer: commonName(issuer), subject: commonName(subject), serial: bytesToHex(serial.body).replace(/^00/, ""),
    validFrom: time(from), validTo: time(to),
  };
}

function caKey(issuer) {
  const ca = CAS[issuer];
  return ca && hexToBytes("04" + ca[0] + ca[1]);
}

// Every check, in the CLI's order. -> {serial, owner, qx, qy, rows: [{ok: true|false|null, what, detail}], failed}
export function verifyBundle(B, signer) {
  const rows = [];
  const row = (ok, what, detail = "") => rows.push({ ok, what, detail });
  if (B.format !== "picoquorum-trustm-attest-1") throw new Error(`not a Trust M attestation bundle (format ${B.format})`);

  const uid = hex(B.uid);
  const serial = bytesToHex(uid.subarray(11, 21));
  row(uid.length === 27 && serial === B.serial, "UID: 27 bytes, the serial is its batch and wafer position", serial);

  // 1. the certificate (E0E0: C0, length, chain length, certificate length, DER)
  const raw = hex(B.cert);
  const der = raw[0] === 0xc0 ? raw.subarray(9, 9 + ((raw[6] << 16) | (raw[7] << 8) | raw[8])) : raw;
  let e0f0 = null;
  try {
    const c = parseCert(der);
    const key = caKey(c.issuer);
    const ok = !!key && p256.verify({ r: c.r, s: c.s }, sha256(c.tbs), key, { prehash: false, lowS: false });
    row(ok, `factory certificate signed by ${c.issuer || "?"}`, `serial ${c.serial}, subject CN=${c.subject}, valid ${c.validFrom} to ${c.validTo}`);
    e0f0 = c.pub;
  } catch (e) {
    row(false, "factory certificate: does not parse as an X.509 certificate with a P-256 key", e.message);
  }

  // 3. the record, F1D0: "PQ" | 2 | profile | serial(10) | OID | flags | qx | qy | owner | date | build
  const rec = hex(B.record);
  const ok3 = rec.length >= 110 && rec[0] === 0x50 && rec[1] === 0x51 && rec[2] === 2;
  const qx = ok3 ? big(rec.subarray(18, 50)) : 0n;
  const qy = ok3 ? big(rec.subarray(50, 82)) : 0n;
  const recOwner = ok3 ? getAddress("0x" + bytesToHex(rec.subarray(82, 102))) : null;
  const made = ok3 ? new Date(u32(rec, 102) * 1000).toISOString().slice(0, 10) : "?";
  const fingerprint = qx.toString(16).padStart(64, "0").slice(0, 8);
  row(ok3 && bytesToHex(rec.subarray(4, 14)) === serial && u16(rec, 14) === KEY, "record (F1D0): this chip's serial, the key in E0F1",
    ok3 ? `key ${fingerprint}, written ${made}, build ${bytesToHex(rec.subarray(106, 110))}` : "no PicoQuorum record");
  const owner = ok3 ? p256Owner(signer, "0x" + qx.toString(16), "0x" + qy.toString(16)) : null;
  row(ok3 && owner === recOwner, "owner address: computed from the key, the same as the record says", owner || "");

  // 2. the binding, F1D1: "PB" | 1 | r | s | SHA-256(cert DER)[:16]
  const bind = hex(B.binding);
  const okB = bind.length >= 83 && bind[0] === 0x50 && bind[1] === 0x42 && bind[2] === 1;
  const sameCert = okB && eq(bind.subarray(67, 83), sha256(der).subarray(0, 16));
  const digest = sha256(concatBytes(BIND_DOMAIN, uid, new Uint8Array([0xe0, 0xf1]), b32(qx), b32(qy)));
  let sigOk = false;
  try {
    sigOk = okB && !!e0f0 && p256.verify({ r: big(bind.subarray(3, 35)), s: big(bind.subarray(35, 67)) }, digest, e0f0, { prehash: false, lowS: false });
  } catch {}
  row(sameCert && sigOk, "binding (F1D1): the factory key E0F0 signed this UID + E0F1 + this public key",
    "proves a genuine Trust M signed the statement; E0F0 signs what it is asked, so not on its own that the key is inside");

  // 2b. the live challenge (records made since 2026-10-01)
  if (B.live) {
    let liveOk = false;
    try {
      const ld = sha256(concatBytes(LIVE_DOMAIN, uid, hex(B.live.nonce)));
      liveOk = !!e0f0 && p256.verify({ r: BigInt("0x" + B.live.r), s: BigInt("0x" + B.live.s) }, ld, e0f0, { prehash: false, lowS: false });
    } catch {}
    row(liveOk, "live: the factory key signed a fresh challenge, under the certificate's key",
      liveOk ? "the chip still held its Infineon key when this record was made" : "the chip's E0F0 is NOT the certificate's key any more");
  } else row(null, "live: not in this record (made before the live challenge existed); run tools/fw attest again");

  // 4. the lifecycle, as the chip reported it to the board that read it
  const meta = (oid) => {
    const m = B.metadata?.[oid];
    if (!m) return null;
    const b = hex(m), out = {};
    for (let i = 2; i < 2 + b[1]; i += 2 + b[i + 1]) out[b[i].toString(16)] = bytesToHex(b.subarray(i + 2, i + 2 + b[i + 1]));
    return { lcso: out.c0 ? parseInt(out.c0, 16) : null, change: out.d0 || "", exec: out.d3 || "", algo: out.e0 || "" };
  };
  const sealed = ["E0F1", "F1D0", "F1D1"].map((o) => [o, meta(o)]);
  row(sealed.every(([, m]) => m && m.lcso === OPERATIONAL && m.change === LCSO_BELOW_OP),
    "sealed (as reported): E0F1, F1D0, F1D1 lifecycle operational, Change LcsO<op", sealed.map(([o, m]) => `${o} ${m ? "LcsO " + m.lcso : "missing"}`).join(", "));
  const k = meta("E0F1");
  row(!!k && k.algo === "03" && k.exec === "00", "E0F1: a P-256 key, signing open to the board (Execute ALW: no PIN)");
  const f0 = meta("E0F0"), fc = meta("E0E0");
  row(!!f0 && !!fc && f0.change === "ff" && fc.change === "ff", "Infineon's factory key and certificate: Change NEV, as they came",
    `E0F0 Change ${f0 ? f0.change : "?"}, LcsO ${f0 ? f0.lcso : "?"}; E0E0 Change ${fc ? fc.change : "?"}, LcsO ${fc ? fc.lcso : "?"}`);
  const sp = SPARES.map((o) => [o, meta(o)]).filter(([, m]) => m);
  const frozen = sp.filter(([, m]) => m.lcso === OPERATIONAL && ["ff", LCSO_BELOW_OP].includes(m.change));
  const open = sp.filter(([, m]) => m.lcso < OPERATIONAL);
  row(open.length ? null : true, `spares (as reported): ${frozen.length} of ${sp.length} frozen`,
    open.length ? `still writable: ${open.map(([o]) => o).join(" ")}` : "nothing else on the chip can be written or get a key");

  const failed = rows.filter((r) => r.ok === false).length;
  return { serial, owner, qx, qy, fingerprint, made, rows, failed };
}
