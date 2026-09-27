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
# Names are hints: every screen that shows one also shows the full address. "book" is the laptop's
# Anvil accounts, so it names addresses only on "bookChains": on Base mainnet those same addresses
# carry EIP-7702 sweepers (docs/LADDER.md), and a friendly name there would be a lie.
#
# "delegates" is empty on purpose: the console refuses any delegatecall except a multiSend to a
# pinned batcher or a call to a contract pinned here (decode.review). Add one only for a contract
# you have read, such as Safe's own migration or SignMessageLib.
#
# "contracts" is the console's own list of contracts it recognises: [name, logo, {selector:
# [signature, what the call does]}]. A contract on it gets its logo and "known" on screen; any
# other contract a transaction calls gets the unknown-contract alert. "Known" means pinned here,
# never what the service or a block explorer says. The Uniswap router is Base mainnet's (Permit2
# is the same on every chain). Each USDC is Circle's on its chain.
# The lists are per chain: "tokens", "batchers", "contracts" and "delegates" are keyed by chain ID,
# and "*" holds the addresses that are the same contract on every chain (Safe's singleton-factory
# deployments, Permit2). "sameAs" makes a chain use another's lists: the Anvil fork of Base (31337)
# has Base's contracts at Base's addresses. A chain with no entry recognises only the "*" ones.
#
# "services" is Safe's transaction service for each chain, so a Safe in secrets.QUORUM_SAFES needs
# only its chainId: the console asks that chain's service, never one the board's secrets.py could
# point at the wrong chain. secrets.QUORUM_URL overrides it for the laptop's simulation and fork.
#
# "system" is the consensus layer's contracts on each chain that has a beacon chain (Pectra, May
# 2025): a Safe that is a validator's withdrawal address asks for a partial withdrawal or an exit
# (EIP-7002), a consolidation or the switch to compounding (EIP-7251) by calling them, and tops up
# or creates a validator through the deposit contract. decode.py reads their calldata exactly (no
# ABI to trust). Base and other L2s have none. "validatorFeeWarn" is the fee (the value sent with a
# request, in wei) above which a request is yellow: the fee is normally 1 wei, and overpaying is
# never refunded.
#
# "signer" is how this key owns a Safe (webauthn.py): Safe's passkey signer, safe-modules passkey
# v0.2.1, the same addresses on Base, Base Sepolia, OP and the Base fork. "proxyCode" is the
# SafeWebAuthnSignerProxy creation code the factory deploys (its bytes 1653-2090), so the console
# computes its own owner address. The factory is at the same address on Ethereum too; tools/vectors
# checks it there before a Safe on chain 1 is trusted to this key (docs/LADDER.md rung 4). "verifiers" is the P-256 precompile at 0x100 first, then the Daimo
# verifier as fallback (about 100k gas instead of 455k). It is part of the owner address: change it
# and every key becomes a different owner, so it stays as it is. tools/vectors checks all of this
# against the deployed factory.
CFG = {
    "safes": [
        {"chainId": 31337, "address": "0xf77e6235ea5ce79d6d823b332276cac99ea77666", "name": "Family Safe"}
    ],
    "bookChains": [31337],
    "book": {
        "0x70997970c51812dc3a010c7d01b50e0d17dc79c8": "Alice",
        "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc": "Bob",
        "0x90f79bf6eb2c4f870365e785982e1f101e93b906": "Carol",
        "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65": "Savings"
    },
    "services": {
        "1": "https://api.safe.global/tx-service/eth",
        "8453": "https://api.safe.global/tx-service/base",
        "84532": "https://api.safe.global/tx-service/basesep"
    },
    "sameAs": {"31337": "8453"},
    "tokens": {
        "8453": {"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ["USDC", 6]},
        "84532": {"0x036cbd53842c5426634e7929541ec2318f3dcf7e": ["USDC", 6]},
        "1": {"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ["USDC", 6]}
    },
    "delegates": {},
    "batchers": {
        "*": {
            "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": "MultiSendCallOnly 1.4.1",
            "0x40a2accbd92bca938b02010e17a5b8929b49130d": "MultiSendCallOnly 1.3.0"
        }
    },
    "contracts": {
        "*": {
            "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": ["Safe MultiSend", "safe", {}],
            "0x40a2accbd92bca938b02010e17a5b8929b49130d": ["Safe MultiSend", "safe", {}],
            "0x000000000022d473030f116ddee9f6b43ac78ba3": ["Uniswap Permit2", "uniswap", {}]
        },
        "8453": {
            "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ["USDC", "usdc", {}],
            "0x6ff5693b99212da76ad316178a184ab56d299b43": ["Uniswap Router", "uniswap", {
                "3593564c": ["execute(bytes,bytes[],uint256)", "Swap on Uniswap"],
                "24856bc3": ["execute(bytes,bytes[])", "Swap on Uniswap"]
            }]
        },
        "84532": {"0x036cbd53842c5426634e7929541ec2318f3dcf7e": ["USDC", "usdc", {}]},
        "1": {"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ["USDC", "usdc", {}]}
    },
    "system": {
        "1": {"0x00000961ef480eb55e80d19ad83579a64c007002": "withdraw", "0x0000bbddc7ce488642fb579f8b00f3a590007251": "consolidate", "0x00000000219ab540356cbb839cbe05303d7705fa": "deposit"},
        "11155111": {"0x00000961ef480eb55e80d19ad83579a64c007002": "withdraw", "0x0000bbddc7ce488642fb579f8b00f3a590007251": "consolidate", "0x7f02c3e3c98b133055b8b348b2ac625669ed295d": "deposit"},
        "560048": {"0x00000961ef480eb55e80d19ad83579a64c007002": "withdraw", "0x0000bbddc7ce488642fb579f8b00f3a590007251": "consolidate", "0x00000000219ab540356cbb839cbe05303d7705fa": "deposit"}
    },
    "validatorFeeWarn": 10000000000000000,
    "signer": {
        "factory": "0x1d31f259ee307358a26dfb23eb365939e8641195",
        "singleton": "0x4e27b51350e6c2083ee19011120f50dafec5ca50",
        "verifiers": "0x0100c2b78104907f722dabac4c69f826a522b2754de4",
        "proxyCode": "610100346100ad57601f6101b538819003918201601f19168301916001600160401b038311848410176100b2578084926080946040528339810103126100ad578051906001600160a01b03821682036100ad5760208101516040820151606090920151926001600160b01b03841684036100ad5760805260a05260c05260e05260405160ec90816100c98239608051816082015260a05181604d015260c051816027015260e0518160010152f35b600080fd5b634e487b7160e01b600052604160045260246000fdfe7f000000000000000000000000000000000000000000000000000000000000000060b63601527f000000000000000000000000000000000000000000000000000000000000000060a03601527f000000000000000000000000000000000000000000000000000000000000000036608001523660006080376000806056360160807f00000000000000000000000000000000000000000000000000000000000000005af43d600060803e60b1573d6080fd5b3d6080f3fea26469706673582212201660515548d15702d720bbc046b457ca85e941a4559ab9f9518488e4c82e5ee964736f6c634300081a0033"
    },
    "chains": {
        "1": "Ethereum",
        "11155111": "Sepolia",
        "560048": "Hoodi",
        "8453": "Base",
        "84532": "Base Sepolia",
        "31337": "Local"
    }
}
