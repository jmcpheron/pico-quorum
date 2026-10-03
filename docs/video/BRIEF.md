# PicoQuorum explainer video: brief

*Handoff for whoever makes the explainer, written 2026-10-03. The story, the messages, a draft
script, the look, the footage we already have, and the lines the video must not cross.*

## The brief in one screen

| | |
|---|---|
| **Motto** | Keys that can't leak. |
| **Logline** | A signing key born inside a chip that it can never leave, made safe by a quorum that never needs any one key. |
| **Audience** | Crypto-curious people. They've heard of seed phrases and hardware wallets, but not multisig, P-256 or Safe. |
| **Main cut** | About 2:30, 16:9. |
| **Social cut** | 30 to 60 s, 9:16 and 1:1. |
| **Remember this** | If you're holding the key, it's yours. If it's gone, you know. And losing one never loses the funds. |
| **Then do this** | Read the [principles](../../PRINCIPLES.md), try it on a laptop, build a console, or join a batch. |

## What PicoQuorum is, and where it stands

PicoQuorum is open hardware for approving transactions from a shared crypto account (a Safe
multisig). Each person holds a **key**: a small board with a security chip that makes and keeps one
private key. The key plugs into a **console**, a tiny computer with a screen. The console shows what
a transaction does in plain words, checks it, and only then asks the key to sign.

The video must not show anything as built that isn't. Here's where everything stands:

| | state | what to show |
|---|---|---|
| The dev console: a Raspberry Pi Pico 2 W, a 1.3″ Waveshare screen and an ATECC608 chip | **real**, on the bench | photos, screen captures, new footage |
| The approval flow: decode, rehash, hold to sign, refusals | **real**, on the real Pico since 2026-09-24 | the screenshot walkthrough |
| End to end on Base Sepolia, a public test network | **real**, 2026-09-25 | screens, the Safe web app |
| The chip ceremony: verify, generate, test, seal, lock | **real** on the dev console | the ceremony screens |
| Key PCB rev A: the board is the plug, with gold fingers | **designed, not ordered** | renders, labelled "design" |
| The console with a guarded Sign button, a dial and a key socket | **concept** | sketches or animation, labelled "concept" |
| Real money on mainnet | **not yet** | nothing |

## The philosophy: the story spine

The whole video hangs on six beats, taken from [PRINCIPLES.md](../../PRINCIPLES.md).

1. **Two bad bargains.** Self-custody today means either a seed phrase (twelve words that are the
   whole key, which can be photographed, phished or burned) or trusting one company's stack from the
   chip to the app.
2. **A key born in a chip.** PicoQuorum's key is generated inside a security chip and never leaves
   it. It's never written down, exported, backed up or copied.
3. **Possession means something.** Because it can't be copied: if it's in your hand, it's yours. If
   it's gone, it was lost or stolen, and you know now, not when the funds move.
4. **The catch.** One key is still one point of failure. Lose it and it's gone.
5. **The quorum.** So every key is just one owner of a multisig: say 3 of 5 must sign. Lose a key, the
   others carry on and rotate it out. Mix in other kinds of keys (a hardware wallet, a warm wallet, a
   paper backup) so no single technology holds more than two.
6. **Why you can trust it, and join in.** Nothing signs unseen. It runs on a separate, simple stack.
   Everything is open, down to the circuit board, and parts can come from people as well as
   factories. It's early, it's honest about that, and it's open to you.

## Three key messages

| message | proof | source |
|---|---|---|
| **Keys that can't leak.** The key is born in the chip and can't be copied, so possession is the signal. | The ceremony seals the key; after the lock, no command can read, replace or add a key. | [PROVISIONING.md](../PROVISIONING.md) |
| **Lose a key, not the funds.** Each key is one owner of a multisig, and the quorum rotates a lost key out. | Keys own a Safe through Safe's audited passkey signer. No contracts of our own. | [SECURITY.md](../SECURITY.md), [KICKOFF.md](../KICKOFF.md) |
| **Open, checkable, yours to build.** The console shows and checks what it signs, and everything is in the open. | The hash is rebuilt on the device and tested against real mainnet Safe transactions. Firmware, PCB and case are all in the repo. | [README.md](../../README.md), [test-vectors/](../../test-vectors/README.md) |

## Words to use, in plain terms

| word | say it like this |
|---|---|
| secure element | a small security chip that makes a key and signs with it, and has no way to give the key out. Not a "TEE" or an "enclave" ([LANGUAGE.md](../LANGUAGE.md)) |
| non-exportable | the key can't be read out or copied, only used |
| no silent compromise | a seed phrase can be copied without anyone knowing; this key can only be misused by taking it, and you'd notice |
| private key | the secret that signs; whoever can use it can approve |
| seed phrase | twelve or twenty-four words that are a whole wallet's key, written down |
| multisig | a shared account that needs several people to approve |
| owner | one of the people, or keys, who can approve |
| threshold | how many owners must approve. Say "3 of 5", never "3/5" |
| quorum | enough owners agreeing for something to happen |
| Safe | the most widely used multisig on Ethereum. Use the name, never the logo |
| rotate out | the other owners remove a lost key and add a new one |
| P-256 | the kind of signature these chips make, which Ethereum now checks natively. Only name it if it helps |
| the rehash | the console works out the transaction's fingerprint itself, from what it shows you |

## Beat sheet: main cut (about 2:30)

The narration is a draft, about 300 words: roughly 2:10 of speech at 140 words a minute, which
leaves room for the visuals to breathe. Rewrite it freely, as long as the
[guardrails](#guardrails-what-the-video-must-not-say-or-show) hold.

| time | beat | narration (draft) | visuals | on screen |
|---|---|---|---|---|
| 0:00–0:12 | Cold open | Five people. Three signatures. Nothing moves until they agree. | The boot animation: five owners land, three turn green, the triangle fills and turns into the diamond. `orbit.gif` | PicoQuorum lockup |
| 0:12–0:30 | Two bad bargains | Most self-custody comes down to one of two bargains. Twelve words that are the whole key, which can be photographed, phished or lost in a fire. Or one company's stack, from the chip to the app, that you trust never to fail. | A seed phrase card being photographed by a phone; a stack of unbranded black boxes. New footage or motion graphics. | — |
| 0:30–0:48 | Born in a chip | PicoQuorum starts somewhere else. Its key is born inside a tiny security chip, and it never leaves. It isn't written down. It can't be exported, backed up or copied. | Macro of the ATECC608 between the boards; the ceremony's "sealed" screen. `2026-09-05-07-atecc-in-the-gap.jpg`, `chipmap-14-sealed.png` | Keys that can't leak |
| 0:48–1:02 | If it's gone, you know | That changes what holding a key means. If it's in your hand, it's yours. If it's gone, it was lost or stolen, and you know today, not when the money moves. | Hand closing around the key; an empty desk. New footage. Key PCB render, labelled design. | — |
| 1:02–1:14 | The catch | But one key is still one point of failure. So no key stands alone. | One key alone, then pull back to five. Motion graphic. | — |
| 1:14–1:40 | The quorum | Each key is one owner of a shared account, a multisig. Say three of five must sign. Lose a key and the others carry on, then rotate it out. Add a hardware wallet, a warm wallet and a paper backup, so no single kind of key holds more than two. | The 3-of-5 mark builds; one amber dot drops out and is replaced. The Owners screen. `mark-dark.svg`, `30-owners.png` | 3 of 5 · lose one, rotate it out |
| 1:40–2:00 | Nothing signs unseen | When it's your turn, the console says what the transaction does in plain words. It works out the transaction's fingerprint itself, from what it shows you, and only then asks the key to sign. If the server lies, it refuses. | Approval flow: summary, send, hold, signed. Then a red owner-change page and the refused lie. `02`, `03`, `05`, `06`, `13`, `16`–`18` | Nothing signs unseen |
| 2:00–2:15 | Open and separate | It runs on a microcontroller with no operating system: a second opinion that shares nothing with your laptop. The firmware, the circuit board and the case are all open, and the parts can come from people, not just factories. | KiCad board view, the case on the printer, a box of parts being split. `key-b-udfn-top.png`, `2026-09-05-24-case-on-the-printer.jpg` | Open down to the PCB |
| 2:15–2:35 | Honest, and an invitation | It's early: test networks and pocket change only, and we say what isn't protected yet. You can run it all on a laptop today, build a console for about thirty-five dollars, or join the next batch of keys. PicoQuorum. Keys that can't leak. | The dev console on black; the repo page; the lockup. `2026-09-05-18-hero-case-on-black.jpg` | github.com/jmcpheron/pico-quorum |

## Beat sheet: social cut (about 45 s)

About 80 words. Open on motion in the first second.

| time | narration (draft) | visuals |
|---|---|---|
| 0:00–0:08 | Your crypto key is probably twelve words on paper. Here's another way. | A seed phrase card, then a hard cut to the boot animation |
| 0:08–0:20 | A key born inside a chip that it never leaves. It can't be copied. If you're holding it, it's yours. If it's gone, you know. | Chip macro, hand closing around the key |
| 0:20–0:32 | One key can still be lost, so each one is just one owner of a multisig. Three of five sign. Lose one, rotate it out. | The 3-of-5 mark builds, a dot is replaced |
| 0:32–0:45 | Open hardware, down to the circuit board. Early, test networks only. PicoQuorum. Keys that can't leak. | PCB render, the lockup, the repo URL |

## Visual language

Everything comes from [BRAND.md](../BRAND.md); open [BRAND.html](../BRAND.html) in a browser to see
it live.

**Colour has a job.** Dark first.

| colour | hex (dark) | means |
|---|---|---|
| Night | `#0B0D11` | the ground; things fade in from it |
| Paper | `#F2F4F7` | text to read and compare |
| Slate | `#98A0AC` | secondary text, steps still running |
| Signed green | `#34C759` | an owner who has signed, a step done, the Sign button |
| Waiting amber | `#FFB830` | an owner who hasn't signed yet; "look again" |
| Ether | `#7A92FF` | the network: the diamond |
| Reject red | `#FF5C54` | only Reject and things that can't be undone |

**Type.** Atkinson Hyperlegible Next for words and Atkinson Hyperlegible Mono for addresses and
hashes. Both are free (SIL OFL). They keep look-alike characters apart, which is the point of a
device that makes you compare addresses.

**The mark.** Five owners on a circle; three have signed (green, joined by a filled triangle) and two
haven't (amber, smaller). It's always 3 of 5, the top owner stays at the top, and the triangle is
never blue.

**Motion.**
- Nothing freezes: waiting owners breathe, the diamond keeps turning.
- Fade through the dark, not through transparency.
- Green fills from the bottom with a bright surface line. No flashes.
- Arrivals ease out; changes of state use smoothstep.

**The signature motif** is the boot animation: owners land, three sign, green fills their triangle,
and it turns into the Ethereum diamond. It can open the video and close it.

## Voice and tone

Calm and certain, like a careful colleague who believes in something. The ideas can be a little
cyberpunk (self-custody, open supply chains, parts from people); the delivery never is. Short
sentences and plain words. No hype, no "revolutionary", no "unhackable", no exclamation marks.
Money is moving; the video stays even-tempered.

## Asset inventory

What already exists in the repo. The screen captures are the real firmware running in the
emulator, pixel for pixel the Pico's 240 × 240 panel, saved at 2×.

| what | path | notes |
|---|---|---|
| Boot animation | [`docs/quorum-ui/v2/boot/orbit.gif`](../quorum-ui/v2/boot/orbit.gif), [`orbit-lite.gif`](../quorum-ui/v2/boot/orbit-lite.gif), `orbit-*.png` stills | 360 × 360. Re-render larger from `firmware/bootart.py` if needed |
| Approval flow | [`docs/quorum-ui/shots/`](../quorum-ui/shots/) `01`–`07` | home, summary, send, every page first, hold, signed |
| Red pages | `13-owner-red-page.png`, `20-unknown-red-page.png`, `25-threshold-red-page.png` | owner change, unknown call, threshold change |
| Refusals | `16-lie-refused.png`–`18-lie-cant-sign.png`, `24-delegatecall-refused.png`, `26-wrong-safe-refused.png` | the service lied; the console won't sign |
| Owners, light theme | `30-owners.png`, `33`–`36` light | |
| Production and ceremony | [`docs/firmware-production/shots/`](../firmware-production/shots/) `60`–`79` | the C1–C10 ceremony; `53-signed-counter.png`, `54-outside-signatures.png` |
| Chip map | [`buildlog/images/`](../../buildlog/images/) `chipmap-*.png` | `chipmap-14-sealed.png`, `chipmap-15-grid-sealed.png` |
| Bench photos | `buildlog/images/2026-09-05-*.jpg` | the stack, the chip in the gap, the case, the hero shot, the printer |
| Key PCB renders | [`hardware/key-pcb/key-b-udfn/fab/`](../../hardware/key-pcb/key-b-udfn/fab/), [`key-a-soic/fab/`](../../hardware/key-pcb/key-a-soic/fab/) `*-top.png`, `*-bottom.png` | pads and fingers only, no part bodies; label as design |
| The mark | [`docs/brand/mark-dark.svg`](../brand/mark-dark.svg), [`mark-light.svg`](../brand/mark-light.svg) | vector |
| New screen captures | `tools/emu shot`, `tools/quorum shots` | any screen, at any time, the same bytes every run |

Two cautions:
- The 2026-09-05 bench photos run the earlier picowallet firmware (a single-owner vault showing a
  USDS balance). Use them for the hardware, not for the screens.
- [`docs/quorum-ui/boot/plugin.gif`](../quorum-ui/boot/plugin.gif) shows the old dual-plug key,
  which rev A replaced. Don't use it as the key.

## Footage still to shoot

- Hands holding the dev console, holding A to sign, the green check.
- A macro of the chip, and of the key PCB once rev A is ordered.
- The case printing, timelapse.
- KiCad on screen, turning the key board in 3D.
- Two or three people in different places, each signing the same transaction.
- A batch being opened on camera and split, once there is one.

## Guardrails: what the video must not say or show

- **Not a product pitch.** Nothing is for sale, it isn't an investment, and it isn't financial
  advice. Test networks and pocket change only.
- **Never "TEE", "enclave", "tamper-proof", "cold storage" or "air-gapped".** The chip is a
  fixed-function secure element and the console uses Wi-Fi. The full list is in
  [LANGUAGE.md](../LANGUAGE.md).
- **Never "unhackable" or "can't be stolen".** A stolen key can sign while the thief holds it. What
  it can't be is copied, so you know it's gone, and the quorum rotates it out.
- **Nothing on paper shown as real.** The console with the guarded button is a concept and the key
  PCB is a design. Label them.
- **No logos that aren't ours.** No Safe logo. No Raspberry Pi logo or raspberry imagery; say "runs
  on Raspberry Pi Pico 2 W".
- **The mark is always 3 of 5,** never all five green, and never shown as a real signing status.
- **Credit the origin.** PicoQuorum grew out of picowallet by Austin Griffith. A line in the end
  card is enough.
- **If security comes up, show the gaps too:** today there's no chip PIN, the USB REPL is on, and
  there's no secure boot.

## Claims checklist

Every factual line the video may use. Anything not here needs checking first.

| claim | source |
|---|---|
| The key is generated inside the chip, never leaves it, and never exists as a seed phrase | [README.md](../../README.md), [PROVISIONING.md](../PROVISIONING.md) |
| After the ceremony locks the chip, no key can be read, replaced or added | [PROVISIONING.md](../PROVISIONING.md) |
| Each key is one owner of a Safe; losing it costs one signature, never the Safe | [SECURITY.md](../SECURITY.md) |
| Keys own the Safe through Safe's audited passkey signer; no contracts of our own | [KICKOFF.md](../KICKOFF.md) |
| Ethereum checks P-256 natively since the Fusaka upgrade (EIP-7951); rollups via RIP-7212 | [PRINCIPLES.md](../../PRINCIPLES.md) |
| The console rebuilds the transaction hash itself and refuses a server that lies about it | [SECURITY.md](../SECURITY.md) |
| The hash code passes tests that include real mainnet Safe transactions | [test-vectors/README.md](../../test-vectors/README.md) |
| Signing ran on the real Pico on 2026-09-24, and end to end on Base Sepolia on 2026-09-25 | [README.md](../../README.md), [LADDER.md](../LADDER.md) |
| A dev console costs about $35, with no soldering | [README.md](../../README.md) |
| The console's whole image is about nine thousand lines of MicroPython | [PRINCIPLES.md](../../PRINCIPLES.md) |
| Hardware is CERN-OHL-S-2.0 (anyone can make and sell it, changes stay open); software is MIT | [NOTICE](../../NOTICE) |
| Target shape: 3 of 5, no single technology holding more than two keys | [KICKOFF.md](../KICKOFF.md#target-multisig-shape-for-reference) |

## Calls to action

- The repo: **github.com/jmcpheron/pico-quorum**
- What it stands for: [PRINCIPLES.md](../../PRINCIPLES.md)
- Try it with no hardware: `tools/emu` and `tools/quorum e2e` ([CONTRIBUTING.md](../../CONTRIBUTING.md))
- Build a dev console: [the build guide](../picowallet.md)
- Join a batch: [hardware/SOURCING.md](../../hardware/SOURCING.md)

## Open questions for the producer

- **Voice-over:** whose voice, and whether Jason appears on camera.
- **Music:** something low and steady, no drops. Open to suggestions.
- **Captions:** yes, burned in for the social cut.
- **Aspect ratios:** 16:9 for the main cut; 9:16 and 1:1 for social.
- **Concept console:** animate it from the kickoff's description, or leave it out until it's built.
