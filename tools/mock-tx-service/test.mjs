// The simulation checks itself. Every scenario's transaction, as the API serves it, must hash the
// same in viem (here) and in the console's firmware/safe_tx.py (through python3). P-256
// confirmations must verify, and forged or blind ones must not. Exit 1 on any failure.
//   node tools/mock-tx-service/test.mjs      (or: cd tools/mock-tx-service && npm test)
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { p256 } from "@noble/curves/p256";
import { privateKeyToAccount } from "viem/accounts";
import { BOOK, PEOPLE, ROOT, apiList, apiSafe, apiTx, confirm, fresh, p256Owner, registerDevice } from "./sim.mjs";
import { SCENARIOS, run } from "./scenarios.mjs";

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
const chipSign = (hash) => hex(p256.sign(hash.slice(2), sk, { prehash: false, lowS: true }).toCompactRawBytes());

function firmwareHashes(chainId, txs) {
  const py = `import sys, json
sys.path.insert(0, ${JSON.stringify(fileURLToPath(new URL("firmware", ROOT)))})
import safe_tx
for t in json.load(sys.stdin):
    print("0x" + safe_tx.from_service(${chainId}, t).hex())`;
  const r = spawnSync("python3", ["-c", py], { input: JSON.stringify(txs), encoding: "utf8" });
  if (r.status) throw new Error(r.stderr);
  return r.stdout.trim().split("\n");
}

// The pinned names match the simulated signers' keys.
check(BOOK.ALICE === PEOPLE.alice.address && BOOK.BOB === PEOPLE.bob.address, "quorum_cfg.py ALICE and BOB are anvil accounts 1 and 2");
check(BOOK.CAROL === privateKeyToAccount("0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6").address,
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
  const [send] = await run(st, "send-eth");
  check(send.confirmations.length === 1, "send-eth: Alice's ECDSA confirmation recorded");
  const flipped = chipSign(send.trueHash).replace(/.$/, (c) => (c === "0" ? "1" : "0"));
  check(!(await confirm(st, send, flipped)).ok, "a P-256 signature with one bit changed is refused");
  check((await confirm(st, send, chipSign(send.trueHash))).ok, "the console's P-256 confirmation verifies");
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

console.log(failed ? `${failed} FAILED` : "all pass");
process.exit(failed ? 1 : 0);
