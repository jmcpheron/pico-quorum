// The simulation checks itself. Every scenario's transaction, as the API serves it, must hash the
// same in viem (here) and in the console's firmware/safe_tx.py (through python3). The console's
// confirmations are packed by firmware/webauthn.py (through python3, with noble playing the chip)
// and must verify here; forged or blind ones must not. Exit 1 on any failure.
//   node tools/mock-tx-service/test.mjs      (or: cd tools/mock-tx-service && npm test)
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { p256 } from "@noble/curves/p256";
import { privateKeyToAccount } from "viem/accounts";
import { BOOK, PEOPLE, ROOT, apiList, apiSafe, apiTx, confirm, fresh, p256Owner, registerDevice } from "./sim.mjs";
import { SCENARIOS, run } from "./scenarios.mjs";
import { packSignatures, parse, softContractSignature } from "./sigs.mjs";

let failed = 0;
const check = (ok, what) => {
  console.log(`${ok ? "pass" : "FAIL"}  ${what}`);
  if (!ok) failed++;
};
const hex = (u8) => "0x" + Buffer.from(u8).toString("hex");

// A throwaway P-256 key standing in for the chip.
const sk = p256.utils.randomPrivateKey();
const pub = p256.getPublicKey(sk, false);
const dev = { name: "test-console", qx: hex(pub.slice(1, 33)), qy: hex(pub.slice(33)) };

function firmware(code, input) {
  const py = `import sys, json\nsys.path.insert(0, ${JSON.stringify(fileURLToPath(new URL("firmware", ROOT)))})\n${code}`;
  const r = spawnSync("python3", ["-c", py], { input: JSON.stringify(input), encoding: "utf8" });
  if (r.status) throw new Error(r.stderr);
  return r.stdout.trim();
}

function firmwareHashes(chainId, txs) {
  return firmware(`import safe_tx
for t in json.load(sys.stdin):
    print("0x" + safe_tx.from_service(${chainId}, t).hex())`, txs).split("\n");
}

// The console's owner address, and a confirmation the way the console makes it: firmware
// webauthn.py builds what the chip signs and packs the result; noble signs in the chip's place.
const fwOwner = firmware(`import quorum_cfg, webauthn
a = json.load(sys.stdin)
print(webauthn.owner_address(a[0], a[1], quorum_cfg.CFG["signer"]))`, [dev.qx, dev.qy]);
function chipSign(hash) {
  const [ad, fields, digest] = JSON.parse(firmware(`import webauthn
ad, fields, d = webauthn.assertion(json.load(sys.stdin))
print(json.dumps([ad.hex(), fields, d.hex()]))`, hash));
  const sig = p256.sign(digest, sk, { prehash: false, lowS: true });
  return "0x" + firmware(`import webauthn
a = json.load(sys.stdin)
print(webauthn.contract_signature(a[0], bytes.fromhex(a[1]), a[2], int(a[3]), int(a[4])).hex())`,
  [fwOwner, ad, fields, sig.r.toString(), sig.s.toString()]);
}

// The pinned names match the simulated signers' keys.
check(BOOK.Alice === PEOPLE.alice.address && BOOK.Bob === PEOPLE.bob.address, "quorum_cfg.py ALICE and BOB are anvil accounts 1 and 2");
check(BOOK.Carol === privateKeyToAccount("0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6").address,
  "quorum_cfg.py CAROL is anvil account 3");

// Every scenario: the served fields hash the same in viem and in the firmware.
for (const name of Object.keys(SCENARIOS)) {
  const st = fresh();
  registerDevice(st, dev);
  const txs = await run(st, name);
  const fw = firmwareHashes(st.chainId, txs.map((t) => ({ ...apiTx(st, t), safe: st.address })));
  txs.forEach((t, i) => {
    check(fw[i] === t.trueHash, `${name}: firmware hash of the served fields = viem's`);
    if (name === "tampered") check(t.safeTxHash !== t.trueHash, `${name}: the reported hash is not the fields' hash`);
    else if (name === "wrong-safe") check(t.safe !== st.address, `${name}: reported for another Safe`);
    else check(t.safeTxHash === t.trueHash, `${name}: the reported hash is honest`);
  });
}

// Confirmations, execution, and the Safe changing under it.
{
  const st = fresh();
  const me = registerDevice(st, dev);
  check(me.address === p256Owner(dev.qx, dev.qy) && st.owners.length === 3, "a console joins as the third owner");
  check(fwOwner === me.address.toLowerCase(), "firmware webauthn.owner_address = viem's CREATE2 of the signer proxy");
  const [send] = await run(st, "send-eth");
  check(send.confirmations.length === 1, "send-eth: Alice's ECDSA confirmation recorded");
  const good = chipSign(send.trueHash);
  check(good === softContractSignature(sk, me.address, send.trueHash).toLowerCase(),
    "firmware webauthn.py packs byte for byte what sigs.mjs packs");
  const s = parse(good).s;
  const flipped = good.replace(s.toString(16).padStart(64, "0"), (s ^ 1n).toString(16).padStart(64, "0"));
  check(flipped !== good && !(await confirm(st, send, flipped)).ok, "a signature with one bit of s changed is refused");
  check(!(await confirm(st, send, good.slice(0, -2))).ok, "a truncated signature is refused");
  check(!(await confirm(st, send, softContractSignature(sk, BOOK.Carol, send.trueHash))).ok, "a contract signature naming a non-owner is refused");
  check((await confirm(st, send, good)).ok, "the console's WebAuthn confirmation verifies");
  check(send.isExecuted && st.nonce === 1, "2 of 3: executed, nonce 1");
  const [lie] = await run(st, "tampered");
  const r = await confirm(st, lie, chipSign(lie.safeTxHash));
  check(!r.ok && /reported hash/.test(r.error), "signing the service's reported hash (blind) is caught");
  const [add] = await run(st, "add-owner", "bob");
  await confirm(st, add, chipSign(add.trueHash));
  check(!add.isExecuted, "add-owner waits: #1 (the lie) holds the nonce");
}
{
  const st = fresh();
  registerDevice(st, dev);
  const [add] = await run(st, "add-owner");
  check((await confirm(st, add, chipSign(add.trueHash))).ok && add.isExecuted, "add-owner executes with Bob + the console");
  check(st.owners.length === 4 && st.threshold === 2, "the Safe now has 4 owners, threshold 2");
  const [a, b] = await run(st, "conflict");
  check(a.nonce === b.nonce, "conflict: two proposals share a nonce");
  check(apiList(st, new URLSearchParams("executed=false&nonce__gte=1")).count === 2, "both are in the queue");
  check(apiSafe(st).owners.length === 4 && apiTx(st, b).data === null, "API shapes: owners list, empty data is null");
}

// Signatures laid out for execTransaction: sorted by owner, the contract signature's data after the slots.
{
  const st = fresh();
  const me = registerDevice(st, dev);
  const [send] = await run(st, "send-eth");
  const alice = send.confirmations[0];
  const mine = { owner: me.address, signature: chipSign(send.trueHash) };
  const packed = packSignatures([alice, mine]);
  const lo = BigInt(alice.owner) < BigInt(me.address) ? [alice, mine] : [mine, alice];
  const at = lo[0] === mine ? 0 : 65;
  check(BigInt("0x" + packed.slice(2 + 2 * at, 2 + 2 * (at + 32))) === BigInt(me.address) &&
        BigInt("0x" + packed.slice(2 + 2 * (at + 32), 2 + 2 * (at + 64))) === 130n,
    "packed: the console's slot names its signer and points past both slots (130)");
  check(packed.slice(2 + 2 * 130) === mine.signature.slice(2 + 2 * 65), "packed: its length and data follow the slots");
}

console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
