// Can a laptop's passkey be a PicoQuorum owner? The browser emulator's passkey key (docs/EMU-WEB.md)
// rests on this: a real WebAuthn assertion from a browser, made over a safeTxHash, packed the way
// firmware/webauthn.py packs the chip's, passes Safe's deployed passkey signer.
//
// Chromium makes a passkey on a virtual platform authenticator with user verification (the path
// Touch ID and Windows Hello take, minus the finger), then signs the eth-send-base safeTxHash
// from test-vectors/safe_tx.json. The browser writes its own authenticatorData and
// clientDataJSON, so this also checks what webauthn.py assumes: clientDataJSON starts with type
// and challenge, and everything after the challenge is the "clientDataFields" the contract takes.
// Then, read only on each chain's public RPC: the factory's getSigner(x, y, verifiers) and
// isValidSignatureForSigner(safeTxHash, ...), with s as the browser gave it and flipped.
//
//   cd tools/vectors && npm install && node passkey.mjs [--chain basesep|base|eth ...] [--write]
// --write keeps this assertion as test-vectors/passkey.json once every chain asked accepts it, so
// test-vectors/run.py checks firmware/webauthn.py packs a real browser's assertion the same way.
//   PQ_CHROMIUM=/path/to/chrome if playwright-core has no Chromium of its own
import { createServer } from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";
import { p256 } from "@noble/curves/p256";
import { concat, createPublicClient, encodeAbiParameters, http, pad, parseAbi, size, toHex } from "viem";
import { base, baseSepolia, mainnet } from "viem/chains";

const ROOT = new URL("../../", import.meta.url);
const src = readFileSync(new URL("firmware/quorum_cfg.py", ROOT), "utf8");
const SIGNER = JSON.parse(src.slice(src.indexOf("{", src.indexOf("CFG =")))).signer;
const HASH = JSON.parse(readFileSync(new URL("test-vectors/safe_tx.json", ROOT), "utf8")).vectors
  .find((v) => v.name === "eth-send-base").safeTxHash;
const CHAINS = {
  basesep: [baseSepolia, process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org"],
  base: [base, process.env.BASE_RPC || "https://mainnet.base.org"],
  eth: [mainnet, process.env.ETH_RPC || "https://ethereum-rpc.publicnode.com"],
};
const argv = process.argv.slice(2);
const nets = argv.flatMap((a, i) => (argv[i - 1] === "--chain" ? [a] : []));
for (const n of nets) if (!CHAINS[n]) throw new Error(`--chain ${n}: one of ${Object.keys(CHAINS).join(", ")}`);

// localhost is a secure context, so WebAuthn works on plain http there; the rpId is "localhost".
// The contract ignores the rpIdHash, so the owner and the check are the same for any domain.
const srv = createServer((_, r) => r.end("<!doctype html><title>passkey</title>")).listen(0);
const browser = await chromium.launch({ executablePath: process.env.PQ_CHROMIUM || undefined, args: ["--no-proxy-server"] });
let got;
try {
  const page = await browser.newPage();
  await page.goto(`http://localhost:${srv.address().port}/`);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: {
    protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true,
    isUserVerified: true, automaticPresenceSimulation: true } });
  got = await page.evaluate(async (hash) => {
    const hx = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
    const c = await navigator.credentials.create({ publicKey: {
      rp: { name: "PicoQuorum", id: "localhost" },
      user: { id: crypto.getRandomValues(new Uint8Array(16)), name: "emu", displayName: "Emulator key" },
      challenge: crypto.getRandomValues(new Uint8Array(32)), pubKeyCredParams: [{ type: "public-key", alg: -7 }],
      authenticatorSelection: { authenticatorAttachment: "platform", userVerification: "required", residentKey: "preferred" } } });
    const a = await navigator.credentials.get({ publicKey: {
      challenge: Uint8Array.from(hash.slice(2).match(/../g), (x) => parseInt(x, 16)), rpId: "localhost",
      userVerification: "required", allowCredentials: [{ type: "public-key", id: c.rawId }] } });
    return { spki: hx(c.response.getPublicKey()), ad: hx(a.response.authenticatorData),
             cdj: new TextDecoder().decode(a.response.clientDataJSON), der: hx(a.response.signature) };
  }, HASH);
} finally {
  await browser.close();
  srv.close();
}

// The public key is the last 64 bytes of the SPKI (uncompressed point, 04 || x || y).
const qx = BigInt("0x" + got.spki.slice(-128, -64)), qy = BigInt("0x" + got.spki.slice(-64));
const head = `{"type":"webauthn.get","challenge":"${Buffer.from(HASH.slice(2), "hex").toString("base64url")}",`;
if (!got.cdj.startsWith(head) || !got.cdj.endsWith("}")) throw new Error("clientDataJSON is not shaped as the contract rebuilds it: " + got.cdj);
const fields = got.cdj.slice(head.length, -1);
const flags = parseInt(got.ad.slice(64, 66), 16);
const sig = p256.Signature.fromDER(got.der);
const low = sig.normalizeS(), high = { r: low.r, s: p256.CURVE.n - low.s };
console.log(`clientDataJSON    ${got.cdj}`);
console.log(`clientDataFields  ${fields}`);
console.log(`flags 0x${flags.toString(16).padStart(2, "0")}: UP ${flags & 1 ? "yes" : "NO"}, UV ${flags & 4 ? "yes" : "NO"} (the contract needs UV)`);

const abi = parseAbi([
  "function getSigner(uint256 x, uint256 y, uint176 verifiers) view returns (address)",
  "function isValidSignatureForSigner(bytes32 message, bytes signature, uint256 x, uint256 y, uint176 verifiers) view returns (bytes4)",
]);
const pack = (s) => encodeAbiParameters([{ type: "bytes" }, { type: "string" }, { type: "uint256" }, { type: "uint256" }],
  ["0x" + got.ad, fields, s.r, s.s]);
let bad = !(flags & 4);
for (const n of nets.length ? nets : Object.keys(CHAINS)) {
  const [chain, rpc] = CHAINS[n];
  const c = createPublicClient({ chain, transport: http(rpc) });
  const owner = await c.readContract({ address: SIGNER.factory, abi, functionName: "getSigner", args: [qx, qy, BigInt(SIGNER.verifiers)] });
  const ask = (s) => c.readContract({ address: SIGNER.factory, abi, functionName: "isValidSignatureForSigner",
    args: [HASH, pack(s), qx, qy, BigInt(SIGNER.verifiers)] });
  const [lo, hi] = [await ask(low), await ask(high)];
  bad += lo !== "0x1626ba7e";
  console.log(`${lo === "0x1626ba7e" ? "pass" : "FAIL"}  ${chain.name.padEnd(13)} owner ${owner}  low s ${lo}  high s ${hi}`);
}
if (argv.includes("--write") && !bad) {
  const owner = (await createPublicClient({ chain: baseSepolia, transport: http(CHAINS.basesep[1]) }).readContract({ address: SIGNER.factory, abi,
    functionName: "getSigner", args: [qx, qy, BigInt(SIGNER.verifiers)] })).toLowerCase();
  const signature = pack(low);
  // the Safe's layout for a contract owner's confirmation, as webauthn.contract_signature makes it
  const contractSignature = concat([pad(owner), pad(toHex(65)), "0x00", pad(toHex(size(signature))), signature]);
  writeFileSync(new URL("test-vectors/passkey.json", ROOT), JSON.stringify({
    note: "A real browser passkey's assertion (Chromium, virtual platform authenticator with user verification) over safe_tx.json's eth-send-base safeTxHash, accepted by Safe's passkey signer on every chain asked (tools/vectors/passkey.mjs --write). webauthn_check.check_passkey: firmware/webauthn.py packs it to the same bytes.",
    signer: { factory: SIGNER.factory, singleton: SIGNER.singleton, verifiers: SIGNER.verifiers },
    chains: nets.length ? nets : Object.keys(CHAINS),
    vectors: [{ name: "chromium-platform", safeTxHash: HASH, qx: "0x" + got.spki.slice(-128, -64), qy: "0x" + got.spki.slice(-64),
      authenticatorData: "0x" + got.ad, clientDataJSON: got.cdj, clientDataFields: fields, r: toHex(low.r), s: toHex(low.s),
      owner, signature, contractSignature }],
  }, null, 2) + "\n");
  console.log("wrote test-vectors/passkey.json");
}
process.exit(bad ? 1 : 0);
