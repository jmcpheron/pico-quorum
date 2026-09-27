// Writes test-vectors/safe_tx.json. The expected hashes come from viem's hashTypedData and
// hashDomain, an implementation that shares no code with firmware/safe_tx.py. Never generate
// expected values with the firmware itself: a vector that checks the code against itself
// proves nothing.
//
// "expect" is what firmware/decode.py must say about a vector (its one-line summary, and each
// item's title and level), written by hand here from what the transaction does. Amounts are
// formatted with viem's formatUnits, not the firmware's.
//
//   cd tools/vectors && npm install && npm run gen
import { readFileSync, writeFileSync } from "node:fs";
import { encodeFunctionData, encodePacked, formatEther, hashDomain, hashTypedData, maxUint256, parseAbi, size, concat } from "viem";

const types = {
  SafeTx: [
    { name: "to", type: "address" },
    { name: "value", type: "uint256" },
    { name: "data", type: "bytes" },
    { name: "operation", type: "uint8" },
    { name: "safeTxGas", type: "uint256" },
    { name: "baseGas", type: "uint256" },
    { name: "gasPrice", type: "uint256" },
    { name: "gasToken", type: "address" },
    { name: "refundReceiver", type: "address" },
    { name: "nonce", type: "uint256" },
  ],
};

const ZERO = "0x0000000000000000000000000000000000000000";
const SAFE_A = "0x1111111111111111111111111111111111111111"; // made-up Safe addresses
const SAFE_B = "0x5afe000000000000000000000000000000005afe";
const ALICE = "0x000000000000000000000000000000000000a11c";
const BOB = "0x0000000000000000000000000000000000000b0b";
const USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913";
const MULTISEND_CALL_ONLY_141 = "0x9641d764fc13c8b624c04430c7356c1c7c8102e2";
const SIM_SAFE = "0xf77e6235ea5ce79d6d823b332276cac99ea77666"; // firmware/quorum_cfg.py's Family Safe
const SIM_BOB = "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc";  // anvil account 2, Bob in quorum_cfg.py
const UNI_ROUTER = "0x6ff5693b99212da76ad316178a184ab56d299b43"; // quorum_cfg.py's Uniswap Router (Base)
const PERMIT2 = "0x000000000022d473030f116ddee9f6b43ac78ba3";

const erc20 = parseAbi(["function transfer(address to, uint256 amount)"]);
const erc20Approve = parseAbi(["function approve(address spender, uint256 amount)"]);
const safeAbi = parseAbi(["function addOwnerWithThreshold(address owner, uint256 _threshold)",
                          "function changeThreshold(uint256 _threshold)"]);
const claimAbi = parseAbi(["function claim(uint256 id)"]); // a function decode.py does not know
const routerAbi = parseAbi(["function execute(bytes commands, bytes[] inputs, uint256 deadline)"]);
const multiSendAbi = parseAbi(["function multiSend(bytes transactions)"]);

// Validators (EIP-7002, EIP-7251, the deposit contract): the consensus layer's contracts on
// Ethereum, pinned in quorum_cfg.py "system". Made-up 48-byte pubkeys; none is in a validator list,
// so an otherwise plain request is yellow.
const WITHDRAW_REQ = "0x00000961ef480eb55e80d19ad83579a64c007002";
const CONSOLIDATION_REQ = "0x0000bbddc7ce488642fb579f8b00f3a590007251";
const DEPOSIT = "0x00000000219ab540356cbb839cbe05303d7705fa";
const PK1 = "0x8c39dfb5ebaafdd4533943270804709fd6b150feec1beff11c76dc54c17c65e3198c490aa58205771b07711436992358";
const PK2 = "0x8a2dbdd6d921d9ec2fd7e43ae3475630f72fb27c77cdba6761d84ec2fabe459c664060f7e6904cc0b55ef93254f7807f";
const withdrawal = (pk, gwei) => concat([pk, encodePacked(["uint64"], [gwei])]);
const depositAbi = parseAbi(["function deposit(bytes pubkey, bytes withdrawal_credentials, bytes signature, bytes32 deposit_data_root)"]);
const depositData = (pk, type, addr) => encodeFunctionData({ abi: depositAbi, functionName: "deposit",
  args: [pk, concat([type, "0x0000000000000000000000", addr]), "0x" + "ab".repeat(96), "0x" + "cd".repeat(32)] });

const tx = (o) => ({
  to: ZERO, value: 0n, data: "0x", operation: 0, safeTxGas: 0n, baseGas: 0n, gasPrice: 0n,
  gasToken: ZERO, refundReceiver: ZERO, nonce: 0n, ...o,
});

// One MultiSend entry: operation (1) to (20) value (32) dataLength (32) data
const packed = (to, value, data) =>
  encodePacked(["uint8", "address", "uint256", "uint256", "bytes"], [0, to, value, BigInt(size(data)), data]);

const transferData = encodeFunctionData({ abi: erc20, functionName: "transfer", args: [BOB, 1_500_000n] });
const multiSendData = encodeFunctionData({
  abi: multiSendAbi,
  functionName: "multiSend",
  args: [concat([packed(ALICE, 10n ** 16n, "0x"), packed(USDC_BASE, 0n, transferData)])],
});

// 12345678.9 -> "12,345,678.9", the way decode.py groups whole units
const grouped = (s) => {
  const [w, f] = s.split(".");
  return BigInt(w).toLocaleString("en-US") + (f ? "." + f : "");
};
const ok = (title) => [title, "ok"];
const red = (title) => [title, "red"];

const cases = [
  ["eth-send-base", "Send 1.5 ETH to Alice on Base", 8453, SAFE_A,
    tx({ to: ALICE, value: 1_500_000_000_000_000_000n, nonce: 0n }),
    { summary: "Send 1.5 ETH", items: [ok("SEND ETH")] }],
  ["eth-send-base-sepolia", "Same send on Base Sepolia: the chain ID alone must change the hash", 84532, SAFE_A,
    tx({ to: ALICE, value: 1_500_000_000_000_000_000n, nonce: 0n }),
    { summary: "Send 1.5 ETH", items: [ok("SEND ETH")] }],
  ["erc20-transfer", "Send 1.5 USDC (6 decimals) to Bob", 8453, SAFE_B,
    tx({ to: USDC_BASE, data: transferData, nonce: 7n }),
    { summary: "Send 1.5 USDC", items: [ok("SEND USDC")] }],
  ["multisend-delegatecall", "Batch via MultiSendCallOnly 1.4.1 (operation 1, delegatecall)", 8453, SAFE_B,
    tx({ to: MULTISEND_CALL_ONLY_141, data: multiSendData, operation: 1, nonce: 8n }),
    { summary: "Batch: 2 actions", items: [ok("SEND ETH"), ok("SEND USDC")] }],
  ["gas-refund", "Nonzero safeTxGas, baseGas, gasPrice, gasToken and refundReceiver (a red-screen case)", 8453, SAFE_A,
    tx({ to: ALICE, value: 1n, safeTxGas: 60000n, baseGas: 21000n, gasPrice: 1_000_000_000n,
         gasToken: USDC_BASE, refundReceiver: BOB, nonce: 42n }),
    { summary: "Send 0.000000000000000001 ETH", items: [ok("SEND ETH"), red("GAS REFUND")] }],
  ["add-owner", "Safe calls itself: addOwnerWithThreshold(Bob, 2) (a red-screen case)", 84532, SAFE_A,
    tx({ to: SAFE_A, data: encodeFunctionData({ abi: safeAbi, functionName: "addOwnerWithThreshold", args: [BOB, 2n] }),
         nonce: 3n }),
    { summary: "Add owner", items: [red("ADD OWNER")] }],
  ["big-nonce", "Large value and nonce, to catch uint256 encoding mistakes", 1, SAFE_B,
    tx({ to: BOB, value: 2n ** 255n + 12345n, nonce: 2n ** 64n + 1n }),
    { summary: `Send ${grouped(formatEther(2n ** 255n + 12345n))} ETH`, items: [ok("SEND ETH")] }],
  ["threshold-change", "Safe calls itself: changeThreshold(1) (a red-screen case)", 84532, SAFE_A,
    tx({ to: SAFE_A, data: encodeFunctionData({ abi: safeAbi, functionName: "changeThreshold", args: [1n] }), nonce: 4n }),
    { summary: "Approvals needed: 1", items: [red("THRESHOLD")] }],
  ["unknown-call", "A call decode.py has no decoder for: it must say so, in red", 8453, SAFE_B,
    tx({ to: ALICE, data: encodeFunctionData({ abi: claimAbi, functionName: "claim", args: [7n] }), nonce: 9n }),
    { summary: "Unknown call", items: [red("UNKNOWN CALL")] }],
  ["unlimited-approve", "USDC approve(Bob, max uint256): the spender can take everything, forever", 8453, SAFE_B,
    tx({ to: USDC_BASE, data: encodeFunctionData({ abi: erc20Approve, functionName: "approve", args: [BOB, maxUint256] }),
         nonce: 10n }),
    { summary: "Approve UNLIMITED USDC", items: [red("APPROVE USDC")] }],
  ["delegatecall-unknown", "Delegatecall to a contract that is not a known batcher", 8453, SAFE_B,
    tx({ to: BOB, data: encodeFunctionData({ abi: claimAbi, functionName: "claim", args: [7n] }), operation: 1, nonce: 11n }),
    { summary: "Delegatecall", items: [red("DELEGATECALL")] }],
  ["rejection", "The Safe app's on-chain rejection: an empty call from the Safe to itself", 84532, SAFE_A,
    tx({ to: SAFE_A, nonce: 5n }),
    { summary: "On-chain rejection", items: [ok("REJECTION")] }],
  ["uniswap-approve", "USDC approve(Uniswap Permit2, 500): a known spender, a bounded amount", 8453, SAFE_B,
    tx({ to: USDC_BASE, data: encodeFunctionData({ abi: erc20Approve, functionName: "approve", args: [PERMIT2, 500_000_000n] }),
         nonce: 12n }),
    { summary: "Approve 500 USDC", items: [ok("APPROVE USDC")] }],
  ["uniswap-swap", "A call the pinned Uniswap Router knows by name but decode.py cannot read in detail: yellow", 8453, SAFE_B,
    tx({ to: UNI_ROUTER, value: 100_000_000_000_000_000n, nonce: 13n,
         data: encodeFunctionData({ abi: routerAbi, functionName: "execute", args: ["0x0b00", ["0x1234", "0x5678"], 1790000000n] }) }),
    { summary: "Swap on Uniswap", items: [["CONTRACT CALL", "warn"]] }],
  ["withdraw-partial", "EIP-7002 partial withdrawal of 1.5 ETH (1,500,000,000 Gwei), fee 1 wei", 1, SAFE_A,
    tx({ to: WITHDRAW_REQ, value: 1n, data: withdrawal(PK1, 1_500_000_000n), nonce: 20n }),
    { summary: "Withdraw 1.5 ETH", items: [["WITHDRAW", "warn"]] }],
  ["exit-full", "EIP-7002 with amount 0: a full exit (a red-screen case)", 1, SAFE_A,
    tx({ to: WITHDRAW_REQ, value: 1n, data: withdrawal(PK1, 0n), nonce: 21n }),
    { summary: "Exit validator", items: [red("EXIT VALIDATOR")] }],
  ["withdraw-malformed", "A withdrawal request one byte short: not a request (red)", 1, SAFE_A,
    tx({ to: WITHDRAW_REQ, value: 1n, data: withdrawal(PK1, 1n).slice(0, -2), nonce: 22n }),
    { summary: "Malformed withdrawal request", items: [red("BAD REQUEST")] }],
  ["consolidate", "EIP-7251: consolidate PK2 into PK1 (a red-screen case)", 1, SAFE_A,
    tx({ to: CONSOLIDATION_REQ, value: 1n, data: concat([PK2, PK1]), nonce: 23n }),
    { summary: "Consolidate validators", items: [red("CONSOLIDATE")] }],
  ["switch-compounding", "EIP-7251 with source = target: switch PK1 to 0x02 credentials", 1, SAFE_A,
    tx({ to: CONSOLIDATION_REQ, value: 1n, data: concat([PK1, PK1]), nonce: 24n }),
    { summary: "Switch to compounding", items: [["COMPOUNDING", "warn"]] }],
  ["deposit-own-creds", "32 ETH deposit whose 0x02 withdrawal credentials name this Safe", 1, SAFE_A,
    tx({ to: DEPOSIT, value: 32_000_000_000_000_000_000n, data: depositData(PK2, "0x02", SAFE_A), nonce: 25n }),
    { summary: "Deposit 32 ETH", items: [ok("DEPOSIT")] }],
  ["deposit-foreign-creds", "32 ETH deposit whose 0x01 withdrawal credentials pay Bob, not this Safe (red)", 1, SAFE_A,
    tx({ to: DEPOSIT, value: 32_000_000_000_000_000_000n, data: depositData(PK2, "0x01", BOB), nonce: 26n }),
    { summary: "Deposit 32 ETH", items: [red("DEPOSIT")] }],
  ["validator-batch", "Two partial withdrawals in one MultiSendCallOnly batch, the second with a 0.05 ETH fee", 1, SAFE_A,
    tx({ to: MULTISEND_CALL_ONLY_141, operation: 1, nonce: 27n, data: encodeFunctionData({ abi: multiSendAbi, functionName: "multiSend",
      args: [concat([packed(WITHDRAW_REQ, 1n, withdrawal(PK1, 1_000_000_000n)), packed(WITHDRAW_REQ, 50_000_000_000_000_000n, withdrawal(PK2, 1_000_000_000n))])] }) }),
    { summary: "Batch: 2 actions", items: [["WITHDRAW", "warn"], ["WITHDRAW", "warn"]] }],
  ["withdraw-on-base", "The same request on Base, which has no such contract: an unknown call (red)", 8453, SAFE_A,
    tx({ to: WITHDRAW_REQ, value: 1n, data: withdrawal(PK1, 1_500_000_000n), nonce: 28n }),
    { summary: "Unknown call", items: [red("UNKNOWN CALL")] }],
  ["sim-send", "The simulated Safe (chain 31337, tools/quorum): send 0.05 ETH to Bob", 31337, SIM_SAFE,
    tx({ to: SIM_BOB, value: 50_000_000_000_000_000n, nonce: 0n }),
    { summary: "Send 0.05 ETH", items: [ok("SEND ETH")] }],
];

const vectors = cases.map(([name, description, chainId, safe, m, expect]) => {
  const domain = { chainId, verifyingContract: safe };
  return {
    name, description, chainId, safe, expect,
    tx: Object.fromEntries(Object.entries(m).map(([k, v]) => [k, typeof v === "bigint" ? v.toString() : v])),
    domainSeparator: hashDomain({ domain, types: { EIP712Domain: [
      { name: "chainId", type: "uint256" }, { name: "verifyingContract", type: "address" }] } }),
    safeTxHash: hashTypedData({ domain, types, primaryType: "SafeTx", message: m }),
  };
});

// Real executed transactions (fetch-real.mjs). Two independent sources must agree: the hash
// Safe's service published and viem's hash of the same fields.
const real = JSON.parse(readFileSync(new URL("real-safe-txs.json", import.meta.url), "utf8"));
real.forEach((r, i) => {
  const m = { ...r.tx, value: BigInt(r.tx.value), safeTxGas: BigInt(r.tx.safeTxGas), baseGas: BigInt(r.tx.baseGas),
              gasPrice: BigInt(r.tx.gasPrice), nonce: BigInt(r.tx.nonce) };
  const domain = { chainId: r.chainId, verifyingContract: r.safe };
  const h = hashTypedData({ domain, types, primaryType: "SafeTx", message: m });
  if (h.toLowerCase() !== r.safeTxHash.toLowerCase()) throw new Error(`viem disagrees with Safe service on ${r.transactionHash}`);
  vectors.push({
    name: `real-${i}`, description: `Executed on chain ${r.chainId}, tx ${r.transactionHash}; hash from Safe's transaction service`,
    chainId: r.chainId, safe: r.safe, tx: r.tx,
    domainSeparator: hashDomain({ domain, types: { EIP712Domain: [
      { name: "chainId", type: "uint256" }, { name: "verifyingContract", type: "address" }] } }),
    safeTxHash: r.safeTxHash,
  });
});

const out = {
  source: "viem hashTypedData (tools/vectors/gen.mjs), real-* also Safe transaction service; Safe >= 1.3.0 EIP-712 domain {chainId, verifyingContract}",
  vectors,
};
writeFileSync(new URL("../../test-vectors/safe_tx.json", import.meta.url), JSON.stringify(out, null, 2) + "\n");
console.log(`wrote ${vectors.length} vectors`);
