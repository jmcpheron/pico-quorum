# Status: what's deployed, what's used, what's next

The one page for where PicoQuorum stands: its names, its Safes, its keys, the contracts it relies
on, and the plan. Everything on chain here was read on chain on the date given; check it again
before relying on it. The design is in [KICKOFF.md](KICKOFF.md), the per-chain test steps in
[LADDER.md](LADDER.md), and the project Safe's plan in [GOVERNANCE.md](GOVERNANCE.md).

*Last checked: 2026-10-06.*

## Names and domains

| | | |
|---|---|---|
| **picoquorum.eth** | owner and registrant `0x682De3ad16F47Acd01e97A73f1619be93672a9f3` (Jason's hardware wallet, an EOA) | Unwrapped. ENS Public Resolver `0xF29100983E058B709F3D539b0c765937B804AC15`; ETH address record: the hardware wallet; no contenthash. Expires **2031-10-06**. |
| **picoquorum.app** | Jason | The site, on GitHub Pages (`docs/CNAME`; DNS at Porkbun). The old address, https://jmcpheron.github.io/pico-quorum/, redirects to it. |
| **picoquorum.com, .org, .dev** | Jason | Redirects to picoquorum.app only. They never serve the site: a passkey belongs to the domain that made it, so a console served from two domains would split its passkeys. |
| **GitHub** | [jmcpheron/pico-quorum](https://github.com/jmcpheron/pico-quorum) | Public from 2026-10. Releases are SSH-signed tags ([RELEASES.md](RELEASES.md)). |

The plan for the name ([GOVERNANCE.md](GOVERNANCE.md#ens)): once the project Safe exists, make it
the name's owner and manager, and set `addr` (Ethereum and Base) to the Safe and `url` to
`https://picoquorum.app`. Consider extending the registration to 10 years.

## Safes

Read on chain 2026-10-06. Owners are listed with what they are; the full addresses are in the
tables below.

| chain | Safe | version | threshold | owners | what it's for |
|---|---|---|---|---|---|
| Base Sepolia | [`0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43`](https://sepolia.basescan.org/address/0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43) | 1.5.0 L2 | 2 of 3 | MetaMask, chip #1, chip #2 | rung 2, the rehearsal Safe; the app's default test Safe |
| Base Sepolia | [`0x5617d3c3180E6dcEb391D4de57fA7d57EaC8DC41`](https://sepolia.basescan.org/address/0x5617d3c3180E6dcEb391D4de57fA7d57EaC8DC41) | 1.5.0 L2 | 3 of 6 | MetaMask, the other wallet, chip #1, chip #2, TM1, and the unlabelled P-256 signer `0x6e5D…E933` | the Trust M rehearsal |
| Base | [`0xDebDE58b3ed0867d19285f6C8B0d81AdBC326Da9`](https://basescan.org/address/0xDebDE58b3ed0867d19285f6C8B0d81AdBC326Da9) | 1.5.0 L2 | 2 of 3 | MetaMask, chip #1, `0xb78e…AdBD8` | rung 3. Nonce 1: #0, 0.000001 ETH confirmed by `0xb78e…` and chip #1, executed 2026-09-26 ([tx](https://basescan.org/tx/0x1b682d376629601808c21cf52cbaddb6e17f57779ef1affd81222c50f1262abb)). Holds 0.000066 ETH. |
| Ethereum | none yet | | | | the project Safe will be here and on Base, at one address |

## Keys

Each key owns a Safe through Safe's passkey signer: its owner address is a
`SafeWebAuthnSignerProxy`, the same on every chain, and its signatures only count on a chain where
the proxy is deployed.

| key | owner address | deployed on |
|---|---|---|
| **TM1**, Infineon OPTIGA Trust M, sealed 2026-09-29 ([TRUSTM.md](TRUSTM.md)) | `0x47c0998C6a7A1955794071b9f4058e7814178f35` | Base Sepolia |
| **Chip #1**, ATECC608 `0123f3acfd2a826bee`, slot 0, sealed 2026-09-25 ([LOCKING.md](LOCKING.md)) | `0x2843705391b7E2cf06b0b964b532Ad9891535E53` | Base Sepolia, Base |
| Chip #1, slot 2 | `0x3ca6AE8f102083B8290Adc96A653C6580C19594F` | none |
| **Chip #2**, ATECC608 `01230e6b8fa23e70ee`, quorum v1 ([PROVISIONING.md](PROVISIONING.md)) | `0x99eDACCAd92537B9146dD0804635bC6dEF7f6b88` | Base Sepolia, Base |
| An unlabelled P-256 signer: a passkey or a key (to label) | `0x6e5Dbb4c283cf1Fa504c946E11fB5Ba5e579E933` | Base Sepolia |

The app's key registry is [registry/keys.json](registry/keys.json). The emulator's keys
(`tools/mock-tx-service/emu-*.json`) are public test keys: never an owner of anything (the last one,
`0xaA87…77b3`, was removed from the Base Sepolia Safe).

## Jason's wallets

| address | what |
|---|---|
| `0x682De3ad16F47Acd01e97A73f1619be93672a9f3` | the hardware wallet: owns picoquorum.eth; one of the project Safe's three owners to be |
| `0x61D24DE770314Eab9c267E47A968FC556744637F` | MetaMask (an EIP-7702 smart account on Base Sepolia): an owner of all three Safes |
| `0x1289f94BCC60eD9F894AB9D5a54C21b3D4B3f2DA` | the other wallet: an owner of the Base Sepolia 3-of-6 |
| `0xb78e3371CE3F61d5D2AB53Cf33059680958AdBD8` | an owner of the Base Safe (confirmed Jason's, 2026-10-06) |

## Contracts PicoQuorum uses

None of its own ([contracts/](../contracts/README.md)). The firmware pins everything it trusts in
[`firmware/quorum_cfg.py`](../firmware/quorum_cfg.py), and the app reads the same file: that file
is the source of truth, and this list follows it.

| contract | address (the same on Ethereum, Base and Base Sepolia) | used for |
|---|---|---|
| Safe | any Safe from 1.3.0 on ([LADDER.md](LADDER.md)) | the multisig itself. The mainnet plan is 1.4.1 L1 ([mainnet/CONFIGURATION.md](mainnet/CONFIGURATION.md)) |
| SafeWebAuthnSignerFactory (safe-modules passkey 0.2.1) | `0x1d31F259eE307358a26dFb23EB365939E8641195` | deploys each key's owner proxy |
| SafeWebAuthnSignerSingleton | `0x4E27b51350e6c2083EE19011120F50DAfEc5CA50` | the proxies' code |
| P-256 verifiers | the precompile at `0x…0100`, then Daimo's `0xc2b78104907F722DABAc4C69f826a522B2754De4` | checking the keys' signatures |
| SignMessageLib 1.4.1 | `0xd53cd0aB83D845Ac265BE939c57F53AD838012c9` | release approvals ([RELEASES.md](RELEASES.md)) |
| MultiSendCallOnly 1.4.1 and 1.3.0 | `0x9641d764fc13c8B624c04430C7356C1C7C8102e2`, `0x40A2aCCbd92BCA938b02010E17A5b8929b49130D` | batches the console decodes |
| Permit2, USDC, the Uniswap router on Base | in `quorum_cfg.py` | decoded on the console's screen |

Services: Safe's transaction service at `api.safe.global` (Ethereum, Base, Base Sepolia), the only
host the console page may reach.

## Releases

- **Firmware 2026.10.10** in source: console `817a·5ae6`, ceremony `0ab8·c357`, dual `68a7·846e`
  ([RELEASES.md](RELEASES.md), and the README's build table).
- Tags `fw-2026.10.1` to `fw-2026.10.5` exist. `.github/allowed_signers` holds no key yet, so
  `release.yml` turns down any new tag until one is added.
- No release is approved by a project Safe: there isn't one yet.

## Hardware

- **The dev console** (Waveshare, [DEV-CONSOLE.md](../hardware/DEV-CONSOLE.md)) runs the console
  image, with chip #1 or TM1.
- **Build 1** (2.0″ screen, knob, TRRS jacks) is on the bench ([BUILD1.md](../hardware/wiring/BUILD1.md)).
- **key-c P2**, the USB-C key: five boards at JLCPCB, estimated to finish 2026-10-07; bring-up is
  next ([key-c](../hardware/key-pcb/key-c-usbc/README.md)).
- **Trust M:** TM1 sealed and approving on Base Sepolia; TM2 was the sacrificial chip (T9 done).

## The test ladder

From [LADDER.md](LADDER.md):

| rung | where | state |
|---|---|---|
| 0, 1 | simulated; an Anvil fork of Base | done, on the real Pico (2026-09-24, 09-25) |
| 2 | Base Sepolia | done, end to end over HTTPS on the real Pico (2026-09-25) |
| 3 | Base, a few dollars | the Safe is checked and chip #1's confirmation executed #0 (2026-09-26); funding it and the console's own approval on Base are next |
| 4 | Ethereum | contracts checked on chain; no Safe yet |

## Next

1. **Public.** The repository goes public (this page is part of that sweep).
2. **The domain.** picoquorum.app serves the site. Left: Enforce HTTPS once GitHub has its
   certificate, and .com, .org and .dev forwarding to it ([LAUNCH.md](../LAUNCH.md)).
3. **The project Safe** on Ethereum and Base, 2 of 3: a Trust M key, the hardware wallet
   `0x682D…a9f3`, and a passkey made on picoquorum.app ([GOVERNANCE.md](GOVERNANCE.md#first-steps)).
4. **picoquorum.eth to the Safe**, with its records.
5. **The first approved release:** an SSH key in `.github/allowed_signers`, a tag, and the Safe's
   approval.
6. **Rungs 3 and 4:** the console's own approval on Base, then Ethereum.
7. **key-c bring-up** on the bench.

## Open decisions

Hardware (from the Build 1 bench and the kickoff):
- **The production key's chip:** Trust M (attempt throttling) or ATECC608 (needs a counter-based
  limit). key-c carries an ATECC608C; the mainnet plan uses a Trust M.
- **The slot plan** before locking any ATECC: which slot signs, what's lockable, a CheckMac or PIN
  gate. The config lock freezes all of it.
- **The connector:** key-c's USB-C plug is the one in production; the card-edge and pogo designs
  stay in [key-pcb/](../hardware/key-pcb/README.md).
- **Key power:** GP6 directly, or a PNP high-side switch. Measure whether a Sign holds up on GP6.
- **KEY ID on GP27:** resistor codes per key type, or leave it unused.
- **Secure boot on the RP2350:** on a spare board only, and later. Enabling it burns OTP.
- **The enclosure:** buttons, a guard or cover over Sign, printed or aluminum, the faceplate name
  ([KICKOFF.md](KICKOFF.md#open-decisions)).
