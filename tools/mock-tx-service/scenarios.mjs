// The stories tools/quorum can queue on the simulated Safe. Each one proposes one transaction (two
// for "conflict"), built from the pinned config's names so the console's address book matches.
// The first group are ordinary; the rest are the red screens and the lies the console must catch.
import { concat, encodeFunctionData, encodePacked, maxUint256, parseAbi, parseEther, parseUnits, size } from "viem";
import { BOOK, CFG, forChain, propose, signAs } from "./sim.mjs";

const USDC = Object.keys(forChain("tokens", 31337))[0];
const MULTISEND = Object.keys(forChain("batchers", 31337))[0];                   // MultiSendCallOnly 1.4.1
const STRANGER = "0xdead00000000000000000000000000000000beef";    // in no address book
const MYSTERY = "0xc0ffee254729296a45a3885639ac7e10f9d54979";     // a contract nobody described
const [PERMIT2, UNI_ROUTER] = Object.entries(forChain("contracts", 31337)).filter(([, k]) => k[1] === "uniswap").map(([a]) => a);
const OTHER_SAFE = "0x5afe00000000000000000000000000000000bad0";
// The owner's own names (secrets.QUORUM_BOOK, tools/quorum book add) and what the console has paid
// before (seen.json), for the "names" stories: an ENS name, a label, one paid three times, and an
// address made to look like the ENS one (address poisoning: same first 4 and last 4 characters).
export const NAMED = {
  vitalik: "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",     // vitalik.eth, resolved both ways
  cold: "0x4b8a2f9c1d7e3a5b6c0d9e8f7a1b2c3d4e5f6071",        // "Cold storage", no ENS name
  repeat: "0x9e1f3c8d2a7b4e6f0c5d1a8b3e7f2c9d4a6b0e18",      // an exchange deposit address, paid 3 times
  first: "0x7c3e5a9d1b8f2e6c4a0d7b3f9e1c5a8d2b6f4e90",       // never seen
  poison: "0xd8da3b1e5f7c9a2d4e6f8b0c1d3e5f7a9b2c6045",      // looks like vitalik.eth
};
export const NAMED_BOOK = `QUORUM_BOOK = {"*": {"${NAMED.vitalik}": "vitalik.eth", "${NAMED.cold}": ["Cold storage"]}}\n`;
export const NAMED_SEEN = JSON.stringify({ 31337: { [NAMED.repeat]: 3, [NAMED.vitalik]: 1 } });

const erc20 = parseAbi(["function transfer(address to, uint256 amount)"]);
const safeAbi = parseAbi(["function addOwnerWithThreshold(address owner, uint256 _threshold)",
                          "function changeThreshold(uint256 _threshold)"]);
const multiSendAbi = parseAbi(["function multiSend(bytes transactions)"]);
const mystery = parseAbi(["function claim(uint256 id)"]);
const erc20Approve = parseAbi(["function approve(address spender, uint256 amount)"]);
const router = parseAbi(["function execute(bytes commands, bytes[] inputs, uint256 deadline)"]);

const usdc = (to, amount) => encodeFunctionData({ abi: erc20, functionName: "transfer", args: [to, parseUnits(amount, 6)] });
const entry = (to, value, data) =>
  encodePacked(["uint8", "address", "uint256", "uint256", "bytes"], [0, to, value, BigInt(size(data)), data]);

// build(safe) -> [SafeTx fields, extra propose options]
export const SCENARIOS = {
  "send-eth": {
    about: "Alice sends 0.05 ETH to Carol, and signs it", by: "alice", sign: true,
    build: () => [{ to: BOOK.Carol, value: parseEther("0.05") }],
  },
  "send-usdc": {
    about: "Bob sends 250 USDC to Savings, and signs it", by: "bob", sign: true,
    build: () => [{ to: USDC, data: usdc(BOOK.Savings, "250") }],
  },
  batch: {
    about: "Alice batches 0.01 ETH to Carol and 100 USDC to Bob (MultiSendCallOnly), and signs it", by: "alice", sign: true,
    build: () => [{
      to: MULTISEND, operation: 1,
      data: encodeFunctionData({ abi: multiSendAbi, functionName: "multiSend",
        args: [concat([entry(BOOK.Carol, parseEther("0.01"), "0x"), entry(USDC, 0n, usdc(BOOK.Bob, "100"))])] }),
    }],
  },
  "uniswap-approve": {
    about: "Alice lets Uniswap's Permit2 spend up to 500 USDC (a known contract), and signs it", by: "alice", sign: true,
    build: () => [{ to: USDC, data: encodeFunctionData({ abi: erc20Approve, functionName: "approve", args: [PERMIT2, parseUnits("500", 6)] }) }],
  },
  "uniswap-swap": {
    about: "Bob swaps 0.1 ETH on Uniswap's router: a known contract, a call it can't read in detail (yellow). The commands are made up, so on the fork it can never execute (GS013)", by: "bob", sign: true,
    build: () => [{ to: UNI_ROUTER, value: parseEther("0.1"),
      data: encodeFunctionData({ abi: router, functionName: "execute", args: ["0x0b00", ["0x1234", "0x5678"], 1790000000n] }) }],
  },
  "add-owner": {
    about: "Bob adds a stranger as a fourth owner (red), and signs it", by: "bob", sign: true,
    build: (safe) => [{ to: safe, data: encodeFunctionData({ abi: safeAbi, functionName: "addOwnerWithThreshold", args: [STRANGER, 2n] }) }],
  },
  threshold: {
    about: "Alice lowers the threshold to 1 (red), and signs it", by: "alice", sign: true,
    build: (safe) => [{ to: safe, data: encodeFunctionData({ abi: safeAbi, functionName: "changeThreshold", args: [1n] }) }],
  },
  "send-ens": {
    about: "Alice sends 1.5 ETH to vitalik.eth (pinned in QUORUM_BOOK), and signs it", by: "alice", sign: true,
    build: () => [{ to: NAMED.vitalik, value: parseEther("1.5") }],
  },
  "send-cold": {
    about: "Bob moves 2,000 USDC to the owners' Cold storage (a pinned label), and signs it", by: "bob", sign: true,
    build: () => [{ to: USDC, data: usdc(NAMED.cold, "2000") }],
  },
  "send-first": {
    about: "Alice sends 0.2 ETH to an address this console has never paid, and signs it", by: "alice", sign: true,
    build: () => [{ to: NAMED.first, value: parseEther("0.2") }],
  },
  "send-repeat": {
    about: "Bob sends 500 USDC to an address this console has paid 3 times, and signs it", by: "bob", sign: true,
    build: () => [{ to: USDC, data: usdc(NAMED.repeat, "500") }],
  },
  "send-poison": {
    about: "Alice sends 1.5 ETH to an address made to look like vitalik.eth's (red), and signs it", by: "alice", sign: true,
    build: () => [{ to: NAMED.poison, value: parseEther("1.5") }],
  },
  refund: {
    about: "A send to Carol that also pays a USDC gas refund to a stranger (red)", by: "alice", sign: true,
    build: () => [{ to: BOOK.Carol, value: parseEther("0.01"), baseGas: 50000n, gasPrice: 1000n, gasToken: USDC, refundReceiver: STRANGER }],
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
    build: () => [{ to: BOOK.Carol, value: parseEther("0.05") }, { lie: { to: STRANGER, value: parseEther("5").toString() } }],
  },
  "wrong-safe": {
    about: "The service slips in a transaction for a different Safe", by: "alice", sign: false,
    build: () => [{ to: BOOK.Carol, value: parseEther("1") }, { reportSafe: OTHER_SAFE }],
  },
  conflict: {
    about: "Two proposals for the same number: Alice sends 1 ETH to Carol, Bob proposes to reject it", by: "alice", sign: true,
    build: () => [{ to: BOOK.Carol, value: parseEther("1") }],
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
    const tx = await propose(st, { ...fields, ...(nonce !== undefined ? { nonce } : {}) }, { proposer: who, scenario: name, ...extra });
    nonce = tx.nonce;
    if (step.sign) await signAs(st, who, tx);
    out.push(tx);
  }
  return out;
}

// The standard queue for a session and for tools/quorum shots.
export const DEMO = ["send-eth", "batch", "add-owner", "tampered", "unknown-call"];
