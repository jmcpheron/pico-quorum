# PicoQuorum keys: the explainer video

> **For the video tool, 2026-10-05.** Built from [the launch plan](README.md) and
> [the brand key](../BRANDKEY.md). The brand key, the rings and the ring approvals are designed,
> not built: the narration says "coming" for them. Everything the narration claims is in
> [Facts](#facts-the-narration-may-use).

## The film in one paragraph

Every crypto wallet rests on one secret, and that secret is a single point of failure. PicoQuorum
keys don't have one: each key is born inside a chip that can't give it up. Alone, that would be
scary; inside a Safe multisig, a lost key is just swapped out. Every key is branded at the bench by a
second key in the same chip that can only vouch for what the chip holds. The keys are numbered in
rings that double, 1, 2, 4 … 256, and the project's own multisig approves each ring on its owners'
consoles. The map fills in as little quorums form all over the internet. Anyone can start their own.

## Real today, and coming

| Piece | Status |
|---|---|
| The console: decodes Safe transactions, recomputes the hash, signs on a held button | Working on a real Raspberry Pi Pico 2 W |
| A secure-element key as a Safe owner, through Safe's passkey signer | Working: a Trust M approval executed on Base Sepolia, 2026-09-30 |
| The console in your browser | Working: the emulator on the project site |
| Release approvals by the project Safe | Built in the console, the app and the tools; the Safe itself is planned |
| The key board (key-c) | 5 boards in production at JLCPCB, the first order |
| The brand key, the rings, ring approvals, the ring map | Designed, coming |

## Direction

| | |
|---|---|
| Logline | Crypto keys that can't be copied, numbered in rings that double, approved by a quorum of the people who hold them. |
| Audience | Ethereum users who know what a seed phrase is; hardware hobbyists; people who will hold a key for someone they trust. |
| Length | Main cut about 4:50 (about 680 words of narration at 145 words a minute). A 60-second cut and a 15-second teaser. |
| Tone | A careful colleague. Short sentences, plain words, no hype, no exclamation marks. |
| Narrator | One calm voice. A beat of silence after every lock and every ring that opens. |
| Music | Low and steady. A soft rise as each ring doubles; one swell when the map fills. No drops. |
| Look | Dark ground, flat shapes, real close-ups of the board and the console's screens. |
| Type | Atkinson Hyperlegible Next for words; Atkinson Hyperlegible Mono for numbers, binary, addresses and hashes. |

### Colours

Colour always means something.

| Name | Hex | Means |
|---|---|---|
| Night | `#0B0D11` | the ground |
| Paper | `#F2F4F7` | words and numbers to read |
| Slate | `#98A0AC` | second lines, steps still running |
| Signed green | `#34C759` | signed, done, bound; the Sign button |
| Waiting amber | `#FFB830` | waiting to sign; look again |
| Ether | `#7A92FF` | the network; lines between keys that share a Safe |
| Reject red | `#FF5C54` | Reject, and every one-way door |
| Stake cyan | `#70D6FF` | what is at stake; a Pair or Quad highlighted |
| Seal gold | `#D9B44A` | the brand key, and seats on the project Safe (figures only, never on the console) |

### Motion and motifs

- **Rings that double.** Dots arrive ring by ring: 1, then 2, 4, 8, 16, 32, 64, 128, 256. Each ring
  takes the same time to draw, so each one feels twice as dense as the last.
- **Binary.** A key's number counts up in decimal, then flips to binary: 42 becomes `101010`. Six
  dots light under it, and drop the last one to reach its parent.
- **The notary in the chip.** The brand key is a small gold seal that only stamps what the chip
  shows it.
- **One-way doors.** Every lock is a door closing with no handle on the far side, and a beat of
  silence.
- **Constellations.** Thin blue lines join keys that share a Safe. Little quorums appear across the
  map like stars joining up.
- **Three of five.** The boot animation's mark (five owners, three sign, the triangle becomes the
  diamond) opens and closes the film. The mark is always three green, two amber, never all five,
  and never live status.
- **Nothing freezes; fade through the dark; fill from the bottom.** As the brand guide says.

## Script

### 1 · One secret · 0:00–0:15

- **VO:** "Every crypto wallet comes down to one secret. Usually it's twelve words on a piece of paper.
  Lose it, and you're locked out. Someone copies it, and you're robbed. One secret. One point of
  failure."
- **Visual:** A card of twelve blurred words. A phone snaps it; copies of the words scatter. A
  single key icon cracks.
- **On screen:** One secret · one point of failure

### 2 · The quorum · 0:15–0:40

- **VO:** "A multisig fixes that. A Safe has several owners, and a set number must agree before
  anything moves: three of five, say. Lose one key, and the others replace it. Steal one, and it
  isn't enough. PicoQuorum makes each of those keys a physical thing you hold, plug in and press."
- **Visual:** The boot animation: five amber owners land on a ring, three turn green, the triangle
  fills and turns into the Ethereum diamond.
- **On screen:** 3 of 5 must agree

### 3 · Meet the key · 0:40–1:00

- **VO:** "This is a PicoQuorum key: a small board with a secure chip on it. The USB-C socket is just
  sturdy wires into a PicoQuorum console; it isn't a USB device. And the most important thing about
  it is what it doesn't have: a seed phrase."
- **Visual:** The key-c render turning, front then back with the mark. Push in on the chip. The key
  slides into a console.
- **On screen:** No seed phrase · nothing to write down

### 4 · Inside the chip · 1:00–1:30

- **VO:** "The chip is a tiny vault with a rulebook. Before it's used, we write its rules and lock
  them forever. Its keys are made inside, from the chip's own randomness, and there's no command to
  read one out. You can ask it to sign. You can never ask it for the key. It signs with P-256, the
  passkey curve, and Safe accepts that as an owner."
- **Visual:** The chip as a floor plan of sixteen rooms with a rulebook strip on top; a padlock
  closes on the rulebook. "Read the key" hits a red refusal.
- **On screen:** Ask it to sign · never for the key

### 5 · The brand key · 1:30–2:00

- **VO:** "Every PicoQuorum key is branded at our bench. The chip makes a second key, its brand key,
  with one strict rule: it can only sign what the chip says about itself. It's a notary that lives
  inside the chip and only notarizes what it sees. Nobody, us included, ever sees it."
- **Visual:** The slot map: slot 1 turns gold, a seal settles on it, its padlock closes. Slot 0 stays
  empty, outlined, waiting.
- **On screen:** Brand key · signs only what the chip says about itself · coming

### 6 · Rings that double · 2:00–2:40

- **VO:** "Branded keys are numbered, in rings that double. One key, then two, then four, eight,
  sixteen, all the way to two hundred fifty-six: five hundred eleven in all. Each ring is one bigger
  than everything before it. Write a key's number in binary, and its length is its ring. Key
  forty-two is one-oh-one-oh-one-oh: ring six. Drop the last bit, and you get its parent, twenty-one.
  Four keys that share a prefix make a Quad: one family's quorum, side by side."
- **Visual:** The ring map builds ring by ring from the centre. A counter: 1, 3, 7, 15, 31, 63 … 511.
  Zoom to key 42: `42` flips to `101010`; a dashed line runs inward 42 → 21 → 10 → 5 → 2 → 1. A cyan
  arc marks the Quad #40–43, `1010xx`.
- **On screen:** 1 · 2 · 4 · 8 … 256 = 511 keys · Key 42 = 101010

### 7 · Signing a ring · 2:40–3:10

- **VO:** "No company issues these keys. A Safe does. The project's own Safe approves each ring the
  way it approves a firmware release. Each owner sees the ring's fingerprint on their own console
  and holds green. One transaction, and the whole ring is real. And a ring opens only when the one
  before it is half in use."
- **Visual:** The ring file scrolls past, then folds into one fingerprint. Three consoles side by
  side show "Approve ring 6 · #32–63 · 32 keys"; three green bars fill; the transaction lands; ring 6
  lights on the map.
- **On screen:** Approved by a quorum, not a company

### 8 · Your ceremony · 3:10–3:40

- **VO:** "When your key arrives, it's unbound. Plug it in and run your ceremony. The chip makes your
  Safe key in a slot nobody has touched, signs two tests, and seals it, forever. Then the brand key
  vouches: this key was born here, it can't leave, and it's sealed. Publish that, and your key shows
  its number and its badge."
- **Visual:** Ceremony screens on the console. Slot 0 fills green, its padlock closes, then the gold
  seal stamps it. A badge: "Verified PicoQuorum key · #42 · 101010".
- **On screen:** Born here · can't leave · sealed

### 9 · Every day · 3:40–3:58

- **VO:** "Day to day, the console shows each transaction in plain words and works out its
  fingerprint itself. If anything doesn't match, it refuses. Hold green for two seconds to sign.
  Press red to say no."
- **Visual:** The approval screens in order, a hold bar filling, one red refusal.
- **On screen:** Hold green 2 s to sign · press red to reject

### 10 · Little quorums everywhere · 3:58–4:30

- **VO:** "Watch the map fill in. Each line joins keys that share a Safe: a family's two of three, a
  hackerspace's three of five. That's the idea: little quorums all over the internet. The people
  holding seats on the project Safe decide how the PicoQuorum brand grows. And the code is open, so
  anyone can start their own quorum, with their own keys and their own name."
- **Visual:** The ring map fills; blue constellations appear one by one. Pull back: smaller ring maps
  of other quorums glow around it, each with its own colours.
- **On screen:** Little quorums, all over the internet

### 11 · Start here · 4:30–4:50

- **VO:** "PicoQuorum is open source and experimental, so use it with small amounts. Try the console
  in your browser today. The first rings are coming. No seed phrase. No token. Just a key, and the
  people you trust."
- **Visual:** The console on black, a key beside it. The boot animation ends on the lockup.
- **On screen:** [URL] · try it in your browser · experimental, small amounts only

### The 60-second cut

About 140 words, over scenes 1, 2, 5, 6, 7, 10 and 11:

> "Every crypto wallet comes down to one secret: twelve words on paper. Lose them, you're locked out.
> Leak them, you're robbed. PicoQuorum keys have no words. The secret is born inside a chip and never
> comes out. Inside a Safe multisig that's ideal: three of five keys agree, and a lost key is swapped
> out. Each key is branded at our bench by a notary inside the chip that can only vouch for what the
> chip holds. They're numbered in rings that double, one, two, four, up to two hundred fifty-six, and
> the project's own Safe approves each ring on its owners' consoles. Watch little quorums form on the
> map, or start your own: the code is open. No seed phrase. No token. Just a key."

### The 15-second teaser

> "One. Two. Four. Eight. Sixteen. Thirty-two. Five hundred eleven keys, each born inside a chip
> that can't give it up. Approved by a quorum. PicoQuorum."

Visual: the rings doubling on the beat, ending on the lockup and the URL.

## Graphics to build

| Graphic | What it shows | Start from |
|---|---|---|
| The ring map, animated | 511 dots on nine rings; filled, hollow and dim; gold seats; blue constellations | `docs/launch/rings.svg` |
| The key card | "Key 42 · 101010 · ring 6", with nine dots for the bits, 1s lit | new |
| Lineage | the dashed line 42 → 21 → 10 → 5 → 2 → 1 | `docs/launch/rings.svg` |
| The slot map | slot 0 the Safe key, slot 1 the brand key, the rulebook and its padlock | `docs/brandkey/slot-map.svg` |
| The two ceremonies | bench, the ring approval, home, the badge | `docs/brandkey/lifecycle.svg` |
| How the chip vouches | the three commands and the 55 bytes, simplified | `docs/brandkey/attestation.svg` |
| "Approve ring" on the console | title, "#32–63 · 32 keys", the root in mono, the hold bar | new, in the console's style (`docs/quorum-ui/shots/`) |
| The launch | phases and gates | `docs/launch/phases.svg` |
| Quorums all the way down | the PicoQuorum ring map among smaller maps of other quorums | new |

## The announcement

**Headline:** No seed phrase. No token. Just a key that can't be copied.
**Second line:** 1, 2, 4, 8 … 511 keys, approved by a quorum.

### Thread (8 posts)

1. Every crypto wallet comes down to one secret, usually 12 words on paper. Lose it and you're
   locked out. Leak it and you're robbed. PicoQuorum keys have no words: the secret is born inside a
   chip and never comes out. [video]
2. "What if I lose it?" That's the point. A PicoQuorum key is one owner of a Safe multisig: say 3 of
   5 must agree. Lose one and the other owners swap it out. Losing a key is a chore, not a
   catastrophe.
3. Every key is branded at the bench. The chip makes a second key that can only sign statements the
   chip writes about itself: a notary that lives in the chip. Nobody, us included, ever sees it.
4. The keys are numbered in rings that double: 1, 2, 4, 8, 16 … 256. 511 in all. Key 42 is 101010:
   ring 6, parent 21. Four keys that share a prefix make a Quad, one family's quorum.
5. No company issues them. The project's own Safe approves each ring, the way it approves a firmware
   release: every owner checks the ring's fingerprint on their console and holds green.
6. At home, your chip makes your Safe key, seals it, and the notary vouches: born here, can't leave,
   sealed. Anyone can check it. That's your badge.
7. Watch the map fill as little quorums form: a family's 2 of 3, a hackerspace's 3 of 5. The people
   holding seats decide how the brand grows. The code is open: start your own quorum, with your own
   name.
8. Open source, runs on Raspberry Pi Pico 2 W, built on Safe, forked from Austin Griffith's
   picowallet. Experimental: small amounts only. Try the console in your browser: [link]

## Facts the narration may use

| Fact | Value |
|---|---|
| Rings | 9 numbered rings of 1, 2, 4, 8, 16, 32, 64, 128 and 256 keys: 511 in all, then open keys |
| Ring of key k | the number of bits in k: key 42 = `101010`, ring 6 |
| Parent and children | parent k ÷ 2 rounded down; children 2k and 2k + 1 |
| Pair, Quad | 2 or 4 keys whose numbers differ only in the last 1 or 2 bits |
| First build (proposed) | #1–63, rings 1 to 6, 63 keys |
| Genesis | keys #1–7, rings 1 to 3; their holders take the project Safe's seats |
| A ring opens | when the ring before it is half bound, by an approval of the project Safe |
| Chip | Microchip ATECC608C on the key-c board, 16 × 36 mm |
| Signature | P-256, about 150 ms on the console |
| The two keys | slot 0, the Safe key (the owner's, made at home); slot 1, the brand key (made at the bench, internal signatures only) |
| Sign gesture | hold green 2 s; 3 s on red pages |
| Console | runs on Raspberry Pi Pico 2 W, MicroPython |
| Safe | Safe 1.4.1, with Safe's passkey signer as the chip's owner contract |
| The project Safe | one Safe at the same address on Ethereum and Base, 2 of 3 to start, handed over in stages |
| License | MIT, except the borrowed case files (CC BY-NC) |

## Glossary

| Term | In plain words |
|---|---|
| Seed phrase | words that can recreate a wallet's key; PicoQuorum keys don't have one |
| Multisig, Safe | a wallet that needs several keys to agree; Safe is the one PicoQuorum works with |
| Threshold | how many owners must sign |
| Secure element | a chip built to make a key, keep it, and sign without ever revealing it |
| Brand key | the chip's second key; it signs only the chip's own statements |
| Statement | the brand key's signed words: this key was made here, can't leave, and is sealed |
| Ring | all the keys whose numbers have the same number of bits |
| Ring approval | the project Safe's signature on a ring's fingerprint |
| Badge | what the app shows once a key's statement checks out |
| Quorum | any Safe whose owners include keys like these; also, any group that issues its own |

## Pronunciation

- **PicoQuorum:** "PEE-koh KWOR-um", one word.
- **ATECC608:** "A-T-E-C-C six-oh-eight".
- **P-256:** "P two-fifty-six".
- **101010:** "one-oh-one-oh-one-oh".
- **511:** "five hundred eleven".
- **Base Sepolia:** "base seh-POH-lee-uh".

## Say this, not that

| Say | Never say | Why |
|---|---|---|
| can't be exported; no command reads it out | unhackable, impossible to steal | chips can be attacked in labs; the multisig is the safety net |
| experimental; small amounts | bank-grade, guaranteed | no track record yet |
| numbers, rings, places | rare, floor, investment, value | numbers are places, not prices |
| a seat carries a duty | token, rewards, airdrop | there is no token |
| coming (brand key, rings, map) | available now | only the console, the Safe owner and the first boards exist |
| runs on Raspberry Pi Pico 2 W; works with Safe | made by, or approved by, either | compatibility wording only |

### Brand rules

- **PicoQuorum**, one word, two capitals. Never "Pico Quorum", "Picoquorum" or "PQ".
- The mark is always three of five. Never all five green, never rotated, never live status.
- Counts read "3 of 5", never "3/5". A middle dot separates facts on one line.
- No Raspberry Pi or Safe logos.
- Demo addresses only: no real owner address, personal Safe or co-signer's name.

## Assets in the repo

| Use | Path |
|---|---|
| The mark | `docs/brand/mark-dark.svg`, `docs/brand/mark-light.svg` |
| Boot animation | `docs/quorum-ui/v2/boot/orbit.gif`, `orbit-lite.gif`; stills `orbit-132.png` to `orbit-256.png` |
| The ring map, the launch | `docs/launch/rings.svg`, `docs/launch/phases.svg` |
| The brand key | `docs/brandkey/slot-map.svg`, `lifecycle.svg`, `attestation.svg`, `trust-chain.svg` |
| The key board | `hardware/key-pcb/key-c-usbc/renders/key-c-P2-3q-top.jpg`, `key-c-P2-3q-bottom.jpg` |
| The console | `buildlog/images/2026-09-05-18-hero-case-on-black.jpg`, `2026-09-05-19-case-portrait.jpg` |
| Inside the chip | `buildlog/images/chipmap-01-map.png`, `chipmap-10-refused.png`, `chipmap-14-sealed.png` |
| Approvals | `docs/quorum-ui/shots/02-approve-summary.png` to `06-approve-signed.png`; `16-lie-refused.png` |
| Ceremony screens | `docs/firmware-production/shots/66-ceremony-C4.png`, `70-ceremony-C6.png`, `71-ceremony-C6-result.png` |
| The brand guide, live | `docs/BRAND.html` |

## Fill in before rendering

- [ ] The URL and the call to action: the site, the browser console, a waitlist
- [ ] Whether the film says "coming", or waits until the brand key runs on a real chip
- [ ] Stop at ring 9 (511) or ring 8 (255)
- [ ] Pack prices and how numbers are given out
- [ ] Which key the film follows (42 is a placeholder)
