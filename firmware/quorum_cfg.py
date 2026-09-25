# PicoQuorum's pinned config: which Safe this console signs for, and the names it may show. The
# transaction service is untrusted (docs/SECURITY.md), so none of this comes from it.
#
# CFG is written as JSON on purpose (double quotes, no True/None, no trailing commas):
# tools/mock-tx-service reads this same file, so the simulated Safe and the console agree.
#
# Chain 31337 is the Family Safe on the laptop (tools/quorum): simulated, or a real Safe 1.4.1 on
# an Anvil fork of Base (tools/quorum up). The address is the one Safe's proxy factory gives that
# Safe on any fork of Base (owners Alice and Bob, threshold 2, salt "PicoQuorum Family Safe"), so
# both agree; chain.mjs checks it. The token and batcher addresses are Base mainnet's, as on the fork.
# Names are hints: every screen that shows one also shows the full address.
#
# "contracts" is the console's own list of contracts it recognises: [name, logo, {selector:
# [signature, what the call does]}]. A contract on it gets its logo and "known" on screen; any
# other contract a transaction calls gets the unknown-contract alert. "Known" means pinned here,
# never what the service or a block explorer says. The Uniswap addresses are Base mainnet's
# (Permit2 is the same on every chain). The other USDCs are Circle's on Base Sepolia and Ethereum,
# for the live rungs (docs/LADDER.md).
# The lists are flat, not per chain: an address means the same thing on every chain here. Make
# them per chain before adding a chain where that is not true.
#
# "signer" is how this key owns a Safe (webauthn.py): Safe's passkey signer, safe-modules passkey
# v0.2.1, the same addresses on Base, Base Sepolia, OP and the Base fork. "proxyCode" is the
# SafeWebAuthnSignerProxy creation code the factory deploys (its bytes 1653-2090), so the console
# computes its own owner address. "verifiers" is the P-256 precompile at 0x100 first, then the Daimo
# verifier as fallback (about 100k gas instead of 455k). It is part of the owner address: change it
# and every key becomes a different owner, so it stays as it is. tools/vectors checks all of this
# against the deployed factory.
CFG = {
    "safes": [
        {"chainId": 31337, "address": "0xf77e6235ea5ce79d6d823b332276cac99ea77666", "name": "Family Safe"}
    ],
    "book": {
        "0x70997970c51812dc3a010c7d01b50e0d17dc79c8": "Alice",
        "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc": "Bob",
        "0x90f79bf6eb2c4f870365e785982e1f101e93b906": "Carol",
        "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65": "Savings"
    },
    "tokens": {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ["USDC", 6],
        "0x036cbd53842c5426634e7929541ec2318f3dcf7e": ["USDC", 6],
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ["USDC", 6]
    },
    "batchers": {
        "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": "MultiSendCallOnly 1.4.1",
        "0x40a2accbd92bca938b02010e17a5b8929b49130d": "MultiSendCallOnly 1.3.0"
    },
    "contracts": {
        "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": ["Safe MultiSend", "safe", {}],
        "0x40a2accbd92bca938b02010e17a5b8929b49130d": ["Safe MultiSend", "safe", {}],
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ["USDC", "usdc", {}],
        "0x036cbd53842c5426634e7929541ec2318f3dcf7e": ["USDC", "usdc", {}],
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ["USDC", "usdc", {}],
        "0x000000000022d473030f116ddee9f6b43ac78ba3": ["Uniswap Permit2", "uniswap", {}],
        "0x6ff5693b99212da76ad316178a184ab56d299b43": ["Uniswap Router", "uniswap", {
            "3593564c": ["execute(bytes,bytes[],uint256)", "Swap on Uniswap"],
            "24856bc3": ["execute(bytes,bytes[])", "Swap on Uniswap"]
        }]
    },
    "signer": {
        "factory": "0x1d31f259ee307358a26dfb23eb365939e8641195",
        "singleton": "0x4e27b51350e6c2083ee19011120f50dafec5ca50",
        "verifiers": "0x0100c2b78104907f722dabac4c69f826a522b2754de4",
        "proxyCode": "610100346100ad57601f6101b538819003918201601f19168301916001600160401b038311848410176100b2578084926080946040528339810103126100ad578051906001600160a01b03821682036100ad5760208101516040820151606090920151926001600160b01b03841684036100ad5760805260a05260c05260e05260405160ec90816100c98239608051816082015260a05181604d015260c051816027015260e0518160010152f35b600080fd5b634e487b7160e01b600052604160045260246000fdfe7f000000000000000000000000000000000000000000000000000000000000000060b63601527f000000000000000000000000000000000000000000000000000000000000000060a03601527f000000000000000000000000000000000000000000000000000000000000000036608001523660006080376000806056360160807f00000000000000000000000000000000000000000000000000000000000000005af43d600060803e60b1573d6080fd5b3d6080f3fea26469706673582212201660515548d15702d720bbc046b457ca85e941a4559ab9f9518488e4c82e5ee964736f6c634300081a0033"
    },
    "chains": {
        "1": "Ethereum",
        "8453": "Base",
        "84532": "Base Sepolia",
        "31337": "Local"
    }
}
