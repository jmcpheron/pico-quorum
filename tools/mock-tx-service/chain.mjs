// The Family Safe as a real Safe 1.4.1 on an Anvil fork of Base (tools/quorum up). sim.mjs keeps
// the queue, as Safe's transaction service does; this file is the chain under it:
//   setup()        check the fork has Safe 1.4.1 and the passkey factory, create the Family Safe
//                  at its pinned address (quorum_cfg.py), fund it with ETH and USDC, snapshot
//   refresh(st)    owners, threshold, nonce and version, read from the Safe
//   enroll(st, o)  a console key made an owner: its signer proxy deployed by the factory, and
//                  added to the Safe (by impersonating the Safe, so no nonce is used, as in the sim)
//   isValidSignature(owner, hash, data)   the owner contract's own check, as the service makes it
//   execute(st, t) execTransaction with every confirmation laid out (sigs.packSignatures)
//   reset()        back to the snapshot setup took
//
// Every key here is one of anvil's well-known test accounts. The fork runs as chain 31337, so a
// signature made on it is not valid on Base: the chain ID is in every safeTxHash.
//
// Those accounts' keys are public, and on Base mainnet every one of them carries an EIP-7702
// delegation to a sweeper contract that forwards any ETH it receives. A fork inherits that code,
// so setup() wipes it from the addresses in the book: on the fork they are plain accounts again.
// Never send anything to them on a real chain.
import {
  createPublicClient, createTestClient, createWalletClient, decodeEventLog, encodeFunctionData, encodePacked,
  formatEther, formatUnits, getAddress, http, keccak256, pad, parseAbi, parseEther, parseUnits, toHex,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { foundry } from "viem/chains";
import { p256 } from "@noble/curves/p256";
import { BOOK, CFG, PEOPLE, ZERO, nameOf, say, safeTxHash } from "./sim.mjs";
import { packSignatures } from "./sigs.mjs";

// Safe 1.4.1's canonical deployments, the same on Base and on every fork of it.
export const SAFE_141 = {
  singleton: "0x29fcB43b46531BcA003ddC8FCB67FFE91900C762",        // SafeL2
  factory: "0x4e1DCf7AD4e460CfD30791CCC4F9c8a4f820ec67",          // SafeProxyFactory
  fallbackHandler: "0xfd0732Dc9E303f09fCEf3a7388Ad10A83459Ec99",  // CompatibilityFallbackHandler
};
export const FAMILY_SALT = BigInt(keccak256(toHex("PicoQuorum Family Safe")));
export const USDC = getAddress(Object.keys(CFG.tokens)[0]);      // Base's USDC (FiatToken)
const USDC_BALANCE_SLOT = 9n;                                     // FiatToken v2.2 balanceAndBlacklistStates
export const EXECUTOR = privateKeyToAccount("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80");  // anvil #0
const MAGIC = "0x1626ba7e";
const FUND_ETH = parseEther("10");
const FUND_USDC = parseUnits("10000", 6);

export const SAFE_ABI = parseAbi([
  "function setup(address[] _owners, uint256 _threshold, address to, bytes data, address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)",
  "function getOwners() view returns (address[])",
  "function getThreshold() view returns (uint256)",
  "function nonce() view returns (uint256)",
  "function VERSION() view returns (string)",
  "function getStorageAt(uint256 offset, uint256 length) view returns (bytes)",
  "function getTransactionHash(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, uint256 _nonce) view returns (bytes32)",
  "function execTransaction(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, bytes signatures) payable returns (bool)",
  "function addOwnerWithThreshold(address owner, uint256 _threshold)",
  "event ExecutionSuccess(bytes32 indexed txHash, uint256 payment)",
  "event ExecutionFailure(bytes32 indexed txHash, uint256 payment)",
]);
const FACTORY_ABI = parseAbi(["function createProxyWithNonce(address _singleton, bytes initializer, uint256 saltNonce) returns (address)"]);
export const PASSKEY_ABI = parseAbi([
  "function createSigner(uint256 x, uint256 y, uint176 verifiers) returns (address)",
  "function getSigner(uint256 x, uint256 y, uint176 verifiers) view returns (address)",
]);
export const ERC1271_ABI = parseAbi(["function isValidSignature(bytes32 hash, bytes signature) view returns (bytes4)"]);
const ERC20_ABI = parseAbi(["function balanceOf(address) view returns (uint256)"]);

export function execArgs(t, signatures) {
  return [getAddress(t.to), BigInt(t.value), t.data || "0x", Number(t.operation), BigInt(t.safeTxGas), BigInt(t.baseGas),
          BigInt(t.gasPrice), getAddress(t.gasToken), getAddress(t.refundReceiver), signatures];
}

// The revert reason viem found (a Safe error code such as GS026), else its short message.
export function reason(e) {
  const r = e.walk?.((x) => x.reason || x.data?.errorName);
  return r?.reason || r?.data?.errorName || e.shortMessage || e.message;
}

// Does the P-256 precompile answer (RIP-7212 / EIP-7951 at 0x100)? Without it the signer falls back
// to the Daimo verifier: slower, same result.
export async function hasP256Precompile(client) {
  const sk = p256.utils.randomPrivateKey();
  const pub = p256.getPublicKey(sk, false);
  const msg = keccak256(toHex("picoquorum precompile check"));
  const sig = p256.sign(msg.slice(2), sk, { prehash: false, lowS: true });
  const input = "0x" + [msg.slice(2), toHex(sig.r, { size: 32 }).slice(2), toHex(sig.s, { size: 32 }).slice(2),
    Buffer.from(pub.slice(1, 33)).toString("hex"), Buffer.from(pub.slice(33)).toString("hex")].join("");
  const r = await client.call({ to: "0x0000000000000000000000000000000000000100", data: input }).catch(() => ({}));
  return r.data === pad("0x01", { size: 32 });
}

export class Chain {
  constructor(rpc) {
    this.rpc = rpc;
    const chain = { ...foundry, name: "Base fork", rpcUrls: { default: { http: [rpc] } } };
    const transport = http(rpc);
    this.pub = createPublicClient({ chain, transport });
    this.test = createTestClient({ chain, mode: "anvil", transport });
    this.wallet = createWalletClient({ chain, transport });
    this.safe = getAddress(CFG.safes[0].address);
    this.snapshot = null;
    this.precompile = false;
  }

  async send(account, address, abi, functionName, args) {
    const hash = await this.wallet.writeContract({ account, address, abi, functionName, args });
    const receipt = await this.pub.waitForTransactionReceipt({ hash });
    if (receipt.status !== "success") throw new Error(`${functionName} reverted in ${hash}`);
    return receipt;
  }

  async setup() {
    const id = await this.pub.getChainId();
    if (id !== 31337) throw new Error(`chain ${id} at ${this.rpc}: the forked Safe runs only on the local fork (31337)`);
    for (const [what, a] of [["SafeL2 1.4.1", SAFE_141.singleton], ["SafeProxyFactory 1.4.1", SAFE_141.factory],
                             ["CompatibilityFallbackHandler 1.4.1", SAFE_141.fallbackHandler],
                             ["the passkey signer factory", CFG.signer.factory], ["USDC", USDC]]) {
      if (!(await this.pub.getCode({ address: a }))) throw new Error(`no ${what} at ${a}: is this a fork of Base?`);
    }
    const factoryCode = await this.pub.getCode({ address: CFG.signer.factory });
    if (!factoryCode.includes(CFG.signer.proxyCode)) throw new Error("quorum_cfg.py signer.proxyCode is not in the passkey factory's code");
    this.precompile = await hasP256Precompile(this.pub);
    this.swept = [];
    for (const a of new Set([EXECUTOR.address, ...Object.values(BOOK)])) {
      if (await this.pub.getCode({ address: a })) {
        await this.test.setCode({ address: a, bytecode: "0x" });
        this.swept.push(a);
      }
    }

    if (!(await this.pub.getCode({ address: this.safe }))) {
      const initializer = encodeFunctionData({ abi: SAFE_ABI, functionName: "setup", args: [
        [PEOPLE.alice.address, PEOPLE.bob.address], 2n, ZERO, "0x", SAFE_141.fallbackHandler, ZERO, 0n, ZERO] });
      const { result } = await this.pub.simulateContract({ account: EXECUTOR, address: SAFE_141.factory, abi: FACTORY_ABI,
        functionName: "createProxyWithNonce", args: [SAFE_141.singleton, initializer, FAMILY_SALT] });
      if (getAddress(result) !== this.safe) throw new Error(`the Family Safe would be at ${result}, quorum_cfg.py pins ${this.safe}`);
      await this.send(EXECUTOR, SAFE_141.factory, FACTORY_ABI, "createProxyWithNonce", [SAFE_141.singleton, initializer, FAMILY_SALT]);
    }
    if ((await this.pub.getBalance({ address: this.safe })) < FUND_ETH) await this.test.setBalance({ address: this.safe, value: FUND_ETH });
    if ((await this.usdc()) < FUND_USDC) {
      const slot = keccak256(encodePacked(["uint256", "uint256"], [BigInt(this.safe), USDC_BALANCE_SLOT]));
      await this.test.setStorageAt({ address: USDC, index: slot, value: toHex(FUND_USDC, { size: 32 }) });
      if ((await this.usdc()) !== FUND_USDC) throw new Error("could not give the Safe USDC (has FiatToken's storage layout changed?)");
    }
    this.snapshot = await this.test.snapshot();
    return {
      safe: this.safe, block: await this.pub.getBlockNumber(), precompile: this.precompile, swept: this.swept,
      eth: formatEther(await this.pub.getBalance({ address: this.safe })), usdc: formatUnits(await this.usdc(), 6),
    };
  }

  usdc() {
    return this.pub.readContract({ address: USDC, abi: ERC20_ABI, functionName: "balanceOf", args: [this.safe] });
  }

  read(functionName, args = []) {
    return this.pub.readContract({ address: this.safe, abi: SAFE_ABI, functionName, args });
  }

  async refresh(st) {
    const [owners, threshold, nonce, version, singleton, handler] = await Promise.all([
      this.read("getOwners"), this.read("getThreshold"), this.read("nonce"), this.read("VERSION"),
      this.pub.getStorageAt({ address: this.safe, slot: "0x0" }),
      this.pub.getStorageAt({ address: this.safe, slot: keccak256(toHex("fallback_manager.handler.address")) }),
    ]);
    const known = new Map(st.owners.map((o) => [o.address, o]));
    st.owners = owners.map((a) => known.get(a) || { address: a, name: nameOf(st, a), kind: "eoa" });
    st.threshold = Number(threshold);
    st.nonce = Number(nonce);
    st.masterCopy = getAddress("0x" + singleton.slice(-40));
    st.fallbackHandler = getAddress("0x" + handler.slice(-40));
    st.version = version + (st.masterCopy === getAddress(SAFE_141.singleton) ? "+L2" : "");
    st.chain = { rpc: this.rpc, block: Number(await this.pub.getBlockNumber()), precompile: this.precompile,
                 eth: formatEther(await this.pub.getBalance({ address: this.safe })), usdc: formatUnits(await this.usdc(), 6) };
  }

  async enroll(st, o) {
    const args = [BigInt(o.qx), BigInt(o.qy), BigInt(CFG.signer.verifiers)];
    const signer = await this.pub.readContract({ address: CFG.signer.factory, abi: PASSKEY_ABI, functionName: "getSigner", args });
    if (getAddress(signer) !== o.address) throw new Error(`the factory puts this key's signer at ${signer}, the console computed ${o.address}`);
    if (!(await this.pub.getCode({ address: signer }))) {
      await this.send(EXECUTOR, CFG.signer.factory, PASSKEY_ABI, "createSigner", args);
      say(st, `deployed ${o.device}'s signer proxy ${signer} with the passkey factory`);
    }
    if (!(await this.read("getOwners")).includes(signer)) {
      await this.test.impersonateAccount({ address: this.safe });
      try {
        await this.send(this.safe, this.safe, SAFE_ABI, "addOwnerWithThreshold", [signer, await this.read("getThreshold")]);
      } finally {
        await this.test.stopImpersonatingAccount({ address: this.safe });
      }
      say(st, `the Safe on the fork now lists ${signer} as an owner (added by impersonating the Safe; on a live chain the owners sign that change)`);
    }
    await this.refresh(st);
  }

  async checkHash(st, f, trueHash) {
    const onchain = await this.read("getTransactionHash", [getAddress(f.to), BigInt(f.value), f.data || "0x", Number(f.operation),
      BigInt(f.safeTxGas), BigInt(f.baseGas), BigInt(f.gasPrice), getAddress(f.gasToken), getAddress(f.refundReceiver), BigInt(f.nonce)]);
    if (onchain !== trueHash) throw new Error(`the Safe hashes #${f.nonce} to ${onchain}, viem to ${trueHash}`);
    if (safeTxHash(st.chainId, st.address, f) !== onchain) throw new Error("chain ID mismatch");
  }

  async isValidSignature(owner, hash, data) {
    try {
      return (await this.pub.readContract({ address: owner, abi: ERC1271_ABI, functionName: "isValidSignature", args: [hash, data] })) === MAGIC;
    } catch {
      return false;
    }
  }

  async execute(st, t) {
    const args = execArgs(t, packSignatures(t.confirmations));
    try {
      await this.pub.simulateContract({ account: EXECUTOR, address: this.safe, abi: SAFE_ABI, functionName: "execTransaction", args });
    } catch (e) {
      return { ok: false, reason: reason(e) };
    }
    const receipt = await this.send(EXECUTOR, this.safe, SAFE_ABI, "execTransaction", args);
    let success = false;
    for (const log of receipt.logs.filter((l) => getAddress(l.address) === this.safe)) {
      try {
        const ev = decodeEventLog({ abi: SAFE_ABI, data: log.data, topics: log.topics });
        if (ev.eventName === "ExecutionSuccess") success = true;
      } catch {}
    }
    return { ok: true, hash: receipt.transactionHash, success, gasUsed: Number(receipt.gasUsed) };
  }

  async reset() {
    if (this.snapshot === null) return;
    await this.test.revert({ id: this.snapshot });
    this.snapshot = await this.test.snapshot();
  }
}
