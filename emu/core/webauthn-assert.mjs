// A WebAuthn assertion as the console needs it from a passkey: what firmware/webauthn.py builds by
// hand for a chip, here taken apart from what a real authenticator wrote. Shared by the page
// (emu/web/app.js, navigator.credentials.get) and the test authenticator (core/softpasskey.mjs).
//
// Safe's passkey signer rebuilds clientDataJSON as
//   {"type":"webauthn.get","challenge":"<base64url(safeTxHash)>",<clientDataFields>}
// and checks the P-256 signature over sha256(authenticatorData || sha256(clientDataJSON)), with the
// UV flag set (tools/vectors/passkey.mjs checks a real browser's against the deployed contracts).
// So: the browser's clientDataJSON must start with exactly that type and challenge, and
// everything after the challenge, minus the closing brace, is clientDataFields.

const N = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551n;
export const hex = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
export const unhex = (h) => Uint8Array.from((h.startsWith("0x") ? h.slice(2) : h).match(/../g) || [], (x) => parseInt(x, 16));
export function b64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** DER ECDSA signature -> { r, s } as BigInt, s normalised to the low half (as p256.py and the chips give it). */
export function derToRS(der) {
  const d = new Uint8Array(der);
  if (d[0] !== 0x30) throw new Error("not a DER signature");
  let i = 2;
  const int = () => {
    if (d[i++] !== 0x02) throw new Error("bad DER integer");
    const n = d[i++];
    const v = BigInt("0x" + (hex(d.slice(i, i + n)) || "0"));
    i += n;
    return v;
  };
  const r = int();
  let s = int();
  if (s > N / 2n) s = N - s;
  if (!r || !s || r >= N) throw new Error("bad signature values");
  return { r, s };
}

/** The pieces the console packs, from what the authenticator returned, checked first. */
export function assertionParts(challengeHex, authenticatorData, clientDataJSON, signatureDer) {
  const ad = new Uint8Array(authenticatorData);
  const cdj = typeof clientDataJSON === "string" ? clientDataJSON : new TextDecoder().decode(clientDataJSON);
  const head = `{"type":"webauthn.get","challenge":"${b64url(unhex(challengeHex))}",`;
  if (!cdj.startsWith(head) || !cdj.endsWith("}"))
    throw new Error("the browser's clientDataJSON is not shaped the way the Safe rebuilds it");
  if (ad.length < 37) throw new Error("authenticatorData is too short");
  if (!(ad[32] & 0x04)) throw new Error("the passkey did not verify the user (UV), and the Safe requires it");
  const { r, s } = derToRS(signatureDer);
  const signCount = ((ad[33] << 24) | (ad[34] << 16) | (ad[35] << 8) | ad[36]) >>> 0;
  return { ad: hex(ad), fields: cdj.slice(head.length, -1), r: r.toString(16), s: s.toString(16), signCount };
}

/** The P-256 public key (x, y as hex) at the end of an uncompressed SPKI, as getPublicKey() returns. */
export function spkiXY(spki) {
  const b = new Uint8Array(spki);
  if (b.length < 65 || b[b.length - 65] !== 0x04) throw new Error("not an uncompressed P-256 key");
  return { x: hex(b.slice(-64, -32)), y: hex(b.slice(-32)) };
}
