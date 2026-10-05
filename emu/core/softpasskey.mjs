// A software passkey for tests and headless runs: a P-256 key in memory that answers like a
// platform authenticator does (authenticatorData with UP and UV, a browser-shaped clientDataJSON
// with an origin, a DER signature), so the console's passkey path runs without a browser. The
// browser itself is checked against the deployed contracts by tools/vectors/passkey.mjs.
//
//   const pk = softPasskey(); createDevice({ ..., passkey: pk }); pk.setUse(true)
// setUse(false), the default, leaves the console on its chip, as the page does in "chip" mode.
import { createHash, generateKeyPairSync, randomBytes, sign } from "node:crypto";
import { assertionParts, b64url, unhex } from "./webauthn-assert.mjs";

const sha256 = (b) => createHash("sha256").update(b).digest();

export function softPasskey({ rpId = "localhost", origin = "http://localhost:4242" } = {}) {
  const { privateKey, publicKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" });
  const xy = (v) => Buffer.from(v, "base64url").toString("hex").padStart(64, "0");
  const cred = { id: b64url(randomBytes(16)), x: xy(jwk.x), y: xy(jwk.y), rpId, kind: "software passkey (tests)", synced: false, made: "test" };
  let use = false, count = 0;
  return {
    cred,
    setUse(on) { use = !!on; },
    info() { return use ? JSON.stringify(cred) : null; },
    get(challengeHex) {
      try {
        count += 1;
        const ad = Buffer.concat([sha256(rpId), Buffer.from([0x05]), Buffer.from([count >>> 24, (count >>> 16) & 255, (count >>> 8) & 255, count & 255])]);
        const cdj = `{"type":"webauthn.get","challenge":"${b64url(unhex(challengeHex))}","origin":"${origin}","crossOrigin":false}`;
        const der = sign("sha256", Buffer.concat([ad, sha256(cdj)]), privateKey);       // ECDSA over sha256(ad || sha256(cdj))
        return JSON.stringify(assertionParts(challengeHex, ad, cdj, der));
      } catch (e) {
        return JSON.stringify({ error: String(e.message || e) });
      }
    },
  };
}
