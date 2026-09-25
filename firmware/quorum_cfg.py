# PicoQuorum's pinned config: which Safe this console signs for, and the names it may show. The
# transaction service is untrusted (docs/SECURITY.md), so none of this comes from it.
#
# CFG is written as JSON on purpose (double quotes, no True/None, no trailing commas):
# tools/mock-tx-service reads this same file, so the simulated Safe and the console agree.
#
# Chain 31337 is the simulated Safe (tools/quorum). The token and batcher addresses are Base
# mainnet's, so the same list fits the Anvil fork of Base in the test ladder's rung 1.
# Names are hints: every screen that shows one also shows the full address.
CFG = {
    "safes": [
        {"chainId": 31337, "address": "0x5afe00000000000000000000000000000000a11e", "name": "FAMILY SAFE"}
    ],
    "book": {
        "0x70997970c51812dc3a010c7d01b50e0d17dc79c8": "ALICE",
        "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc": "BOB",
        "0x90f79bf6eb2c4f870365e785982e1f101e93b906": "CAROL",
        "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65": "SAVINGS"
    },
    "tokens": {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ["USDC", 6]
    },
    "batchers": {
        "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": "MultiSendCallOnly 1.4.1",
        "0x40a2accbd92bca938b02010e17a5b8929b49130d": "MultiSendCallOnly 1.3.0"
    },
    "chains": {
        "1": "ETHEREUM",
        "8453": "BASE",
        "84532": "BASE SEPOLIA",
        "31337": "LOCAL"
    }
}
