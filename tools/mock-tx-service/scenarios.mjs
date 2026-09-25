// The stories tools/quorum can queue on the simulated Safe. Each one proposes one transaction (two
// for "conflict"), built from the pinned config's names so the console's address book matches.
// The first group are ordinary; the rest are the red screens and the lies the console must catch.
import { concat, encodeFunctionData, encodePacked, maxUint256, parseAbi, parseEther, parseUnits, size } from "viem";
import { BOOK, CFG, propose, signAs } from "./sim.mjs";

const USDC = Object.keys(CFG.tokens)[0];
const MULTISEND = Object.keys(CFG.batchers)[0];                   // MultiSendCallOnly 1.4.1
const STRANGER = "0xdead00000000000000000000000000000000beef";    // in no address book
const MYSTERY = "0xc0ffee254729296a45a3885639ac7e10f9d54979";     // a contract nobody described
const OTHER_SAFE = "0x5afe00000000000000000000000000000000bad0";

const erc20 = parseAbi(["function transfer(address to, uint256 amount)"]);
const safeAbi = parseAbi(["function addOwnerWithThreshold(address owner, uint256 _threshold)",
                          "function changeThreshold(uint256 _threshold)"]);
const multiSendAbi = parseAbi(["function multiSend(bytes transactions)"]);
const mystery = parseAbi(["function claim(uint256 id)"]);

const usdc = (to, amount) => encodeFunctionData({ abi: erc20, functionName: "transfer", args: [to, parseUnits(amount, 6)] });
const entry = (to, value, data) =>
  encodePacked(["uint8", "address", "uint256", "uint256", "bytes"], [0, to, value, BigInt(size(data)), data]);

// build(safe) -> [SafeTx fields, extra propose options]
export const SCENARIOS = {
  "send-eth": {
    about: "Alice sends 0.05 ETH to Carol, and signs it", by: "alice", sign: true,
    build: () => [{ to: BOOK.CAROL, value: parseEther("0.05") }],
  },
  "send-usdc": {
    about: "Bob sends 250 USDC to Savings, and signs it", by: "bob", sign: true,
    build: () => [{ to: USDC, data: usdc(BOOK.SAVINGS, "250") }],
  },
  batch: {
    about: "Alice batches 0.01 ETH to Carol and 100 USDC to Bob (MultiSendCallOnly), and signs it", by: "alice", sign: true,
    build: () => [{
      to: MULTISEND, operation: 1,
      data: encodeFunctionData({ abi: multiSendAbi, functionName: "multiSend",
        args: [concat([entry(BOOK.CAROL, parseEther("0.01"), "0x"), entry(USDC, 0n, usdc(BOOK.BOB, "100"))])] }),
    }],
  },
  "add-owner": {
    about: "Bob adds a stranger as a fourth owner (red), and signs it", by: "bob", sign: true,
    build: (safe) => [{ to: safe, data: encodeFunctionData({ abi: safeAbi, functionName: "addOwnerWithThreshold", args: [STRANGER, 2n] }) }],
  },
  threshold: {
    about: "Alice lowers the threshold to 1 (red), and signs it", by: "alice", sign: true,
    build: (safe) => [{ to: safe, data: encodeFunctionData({ abi: safeAbi, functionName: "changeThreshold", args: [1n] }) }],
  },
  refund: {
    about: "A send to Carol that also pays a USDC gas refund to a stranger (red)", by: "alice", sign: true,
    build: () => [{ to: BOOK.CAROL, value: parseEther("0.01"), baseGas: 50000n, gasPrice: 1000n, gasToken: USDC, refundReceiver: STRANGER }],
  },
  "unknown-call": {
    about: "Bob calls a contract the console has no decoder for (red)", by: "bob", sign: true,
    build: () => [{ to: MYSTERY, data: encodeFunctionData({ abi: mystery, functionName: "claim", args: [7n] }) }],
  },
  "delegate-unknown": {
    about: "Bob delegatecalls an unknown contract: it would run as the Safe (red)", by: "bob", sign: true,
    build: () => [{ to: MYSTERY, operation: 1, data: encodeFunctionData({ abi: mystery, functionName: "claim", args: [7n] }) }],
  },
  tampered: {
    about: "The service shows 0.05 ETH to Carol but asks for a signature over 5 ETH to a stranger", by: "alice", sign: false,
    build: () => [{ to: BOOK.CAROL, value: parseEther("0.05") }, { lie: { to: STRANGER, value: parseEther("5").toString() } }],
  },
  "wrong-safe": {
    about: "The service slips in a transaction for a different Safe", by: "alice", sign: false,
    build: () => [{ to: BOOK.CAROL, value: parseEther("1") }, { reportSafe: OTHER_SAFE }],
  },
  conflict: {
    about: "Two proposals for the same number: Alice sends 1 ETH to Carol, Bob proposes to reject it", by: "alice", sign: true,
    build: () => [{ to: BOOK.CAROL, value: parseEther("1") }],
    then: { by: "bob", sign: true, build: (safe) => [{ to: safe }] },
  },
};

export async function run(st, name, by) {
  const sc = SCENARIOS[name];
  if (!sc) throw new Error(`no scenario ${name}; try: ${Object.keys(SCENARIOS).join(", ")}`);
  const out = [];
  let nonce;
  for (const step of [sc, sc.then].filter(Boolean)) {
    const [fields, extra = {}] = step.build(st.address);
    const who = (step === sc && by) || step.by;
    const tx = propose(st, { ...fields, ...(nonce !== undefined ? { nonce } : {}) }, { proposer: who, scenario: name, ...extra });
    nonce = tx.nonce;
    if (step.sign) await signAs(st, who, tx);
    out.push(tx);
  }
  return out;
}

// The standard queue for a session and for tools/quorum shots.
export const DEMO = ["send-eth", "batch", "add-owner", "tampered", "unknown-call"];
