// The browser wallet, through EIP-1193. Wallets announce themselves by EIP-6963; window.ethereum is
// the fallback. The page never holds a key: the wallet shows every transaction and asks.
const found = new Map();          // rdns -> {info, provider}
const listeners = new Set();
if (typeof window !== "undefined") {
  window.addEventListener("eip6963:announceProvider", (e) => {
    const { info, provider } = e.detail || {};
    if (info?.rdns && provider) found.set(info.rdns, { info, provider });
    for (const f of listeners) f();
  });
  window.dispatchEvent(new Event("eip6963:requestProvider"));
}

export const wallet = {
  provider: null,
  name: "",
  account: null,
  chainId: null,
  onChange(f) { listeners.add(f); },
  available() {
    const list = [...found.values()].map(({ info, provider }) => ({ id: info.rdns, name: info.name, icon: info.icon, provider }));
    if (!list.length && typeof window !== "undefined" && window.ethereum) list.push({ id: "injected", name: "Browser wallet", provider: window.ethereum });
    return list;
  },
  async connect(id) {
    const choice = this.available().find((w) => w.id === id) || this.available()[0];
    if (!choice) throw new Error("No wallet in this browser. Install MetaMask, Rabby or another wallet extension, then reload.");
    const p = choice.provider;
    const [account] = await p.request({ method: "eth_requestAccounts" });
    this.provider = p;
    this.name = choice.name;
    this.account = account;
    this.chainId = parseInt(await p.request({ method: "eth_chainId" }), 16);
    p.on?.("accountsChanged", (a) => { this.account = a[0] || null; for (const f of listeners) f(); });
    p.on?.("chainChanged", (c) => { this.chainId = parseInt(c, 16); for (const f of listeners) f(); });
    for (const f of listeners) f();
    return account;
  },
  // c: an entry of safe.mjs CHAINS, rpc: the RPC in use for it
  async ensureChain(c, rpc) {
    const hex = "0x" + c.id.toString(16);
    if (this.chainId === c.id) return;
    try {
      await this.provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: hex }] });
    } catch (e) {
      if (e.code !== 4902) throw e;
      await this.provider.request({ method: "wallet_addEthereumChain", params: [{ chainId: hex, chainName: c.name, rpcUrls: [rpc],
        nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 }, blockExplorerUrls: [c.explorer] }] });
    }
    this.chainId = parseInt(await this.provider.request({ method: "eth_chainId" }), 16);
    if (this.chainId !== c.id) throw new Error(`Your wallet is still on chain ${this.chainId}. Switch it to ${c.name}.`);
  },
  async send(tx) {
    const p = { from: this.account, to: tx.to, data: tx.data, value: "0x" + (tx.value || 0n).toString(16) };
    if (tx.gas) p.gas = "0x" + tx.gas.toString(16);
    return this.provider.request({ method: "eth_sendTransaction", params: [p] });
  },
};
