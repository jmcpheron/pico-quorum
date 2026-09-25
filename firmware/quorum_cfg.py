# PicoQuorum's pinned config: which Safe this console signs for, and the names it may show. The
# transaction service is untrusted (docs/SECURITY.md), so none of this comes from it.
#
# CFG is written as JSON on purpose (double quotes, no True/None, no trailing commas):
# tools/mock-tx-service reads this same file, so the simulated Safe and the console agree.
#
# Chain 31337 is the simulated Safe (tools/quorum). The token and batcher addresses are Base
# mainnet's, so the same list fits the Anvil fork of Base in the test ladder's rung 1.
# Names are hints: every screen that shows one also shows the full address.
#
# "contracts" is the console's own list of contracts it recognises: [name, logo, {selector:
# [signature, what the call does]}]. A contract on it gets its logo and "known" on screen; any
# other contract a transaction calls gets the unknown-contract alert. "Known" means pinned here,
# never what the service or a block explorer says. The Uniswap addresses are Base mainnet's
# (Permit2 is the same on every chain); check them again before the Base fork in rung 1.
CFG = {
    "safes": [
        {"chainId": 31337, "address": "0x5afe00000000000000000000000000000000a11e", "name": "Family Safe"}
    ],
    "book": {
        "0x70997970c51812dc3a010c7d01b50e0d17dc79c8": "Alice",
        "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc": "Bob",
        "0x90f79bf6eb2c4f870365e785982e1f101e93b906": "Carol",
        "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65": "Savings"
    },
    "tokens": {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ["USDC", 6]
    },
    "batchers": {
        "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": "MultiSendCallOnly 1.4.1",
        "0x40a2accbd92bca938b02010e17a5b8929b49130d": "MultiSendCallOnly 1.3.0"
    },
    "contracts": {
        "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": ["Safe MultiSend", "safe", {}],
        "0x40a2accbd92bca938b02010e17a5b8929b49130d": ["Safe MultiSend", "safe", {}],
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ["USDC", "usdc", {}],
        "0x000000000022d473030f116ddee9f6b43ac78ba3": ["Uniswap Permit2", "uniswap", {}],
        "0x6ff5693b99212da76ad316178a184ab56d299b43": ["Uniswap Router", "uniswap", {
            "3593564c": ["execute(bytes,bytes[],uint256)", "Swap on Uniswap"],
            "24856bc3": ["execute(bytes,bytes[])", "Swap on Uniswap"]
        }]
    },
    "chains": {
        "1": "Ethereum",
        "8453": "Base",
        "84532": "Base Sepolia",
        "31337": "Local"
    }
}
