# PicoQuorum brand guide

A physical approval device for Safe multisig wallets. Several people, several keys, one Safe.

Everything here comes from the boot screen: five owners appear, three of them sign, and their green
triangle turns into the Ethereum diamond. The name, the mark, the colours and the motion all follow
from that one picture.

The same guide as a page, with the boot screen running live, is [BRAND.html](BRAND.html). Open it
in a browser.

<img src="quorum-ui/v2/boot/orbit-lite.gif" width="240" alt="The PicoQuorum boot screen">

## Name

**PicoQuorum** is one word with two capitals. **Pico** is for the Raspberry Pi Pico it runs on.
**Quorum** is for the idea at its centre: a Safe needs a set number of owners to agree before
anything moves. The multisig is the star, and the name says so.

| Write | Never |
|---|---|
| PicoQuorum | ~~Pico Quorum~~ |
| the PicoQuorum console (the box with the screen) | ~~Picoquorum~~ |
| a PicoQuorum key (the plug-in secure element) | ~~PICOQUORUM~~, ~~PQ~~ |

When naming the board, use compatibility wording such as "runs on Raspberry Pi Pico 2 W". Never use
the Raspberry Pi logo or raspberry imagery.

## Mark

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="brand/mark-dark.svg">
  <img src="brand/mark-light.svg" width="128" alt="The PicoQuorum mark">
</picture>

The boot screen in miniature. Five owners sit evenly on a circle. The top owner and the two at the
bottom have signed: they are green, and the triangle between them is filled. The two who didn't sign
stay amber and smaller.

Files: [mark-dark.svg](brand/mark-dark.svg) for dark backgrounds,
[mark-light.svg](brand/mark-light.svg) for light ones.

### Geometry

| | |
|---|---|
| Points | 5, at −90° + 72°·k on a circle of radius *r* |
| Signed | Top, lower left, lower right. Dot radius *r*/4 |
| Waiting | Upper left and upper right. Dot radius *r*/6 |
| Triangle | Joins the three signed centres, filled with face green mixed 55% into the background |
| Order | Top signs first, then left, then right, as in the animation |

### Lockup

The mark goes on the left of the name, centred on it. On the panel the name is 26 px bold, the ring
radius is 12 px, the mark's centre is 13 px in from the lockup's left edge, and the word starts at
34 px. Scale those proportions.

### Size

Smallest use is 16 px, where the waiting dots shrink to a pixel and a half. Below that, use the green
triangle on its own.

### Don't

- **Make all five dots green.** That's unanimity. The mark is always three of five.
- **Colour the triangle blue.** Green means signed. Ether blue belongs to the diamond.
- **Rotate it or turn it upside down.** The first signer stays at the top.
- **Use it as live status.** The dots are artwork and never report real signatures
  (`firmware/bootart.py` says the same). Real signatures belong on the approval screens.

## Colour

Six colours carry the brand, and each one has a job. The panel is dark first; the light values are
the console's light theme. Values come from `firmware/quorum_ui.py`. RGB565 is what the Pico sends
to its 16-bit panel.

| Colour | Token | Means | Dark | 565 | Light | 565 |
|---|---|---|---|---|---|---|
| Night | `bg` | The ground. Everything fades in from it. | `#0B0D11` | `0x0862` | `#F5F6F8` | `0xF7BF` |
| Paper | `text` | Names, amounts, anything to read and compare. | `#F2F4F7` | `0xF7BE` | `#101318` | `0x1083` |
| Slate | `muted` | Taglines, steps still running, second-line detail. | `#98A0AC` | `0x9D15` | `#565E6A` | `0x52ED` |
| Signed green | `ok` | An owner who has signed, a step that is done, the Sign button. | `#34C759` | `0x362B` | `#16963E` | `0x14A7` |
| Waiting amber | `warn` | An owner who can sign and hasn't yet. Also: look again. | `#FFB830` | `0xFDC6` | `#A86600` | `0xAB20` |
| Ether | `eth` | The network: the diamond and its shading, the mainnet badge. | `#7A92FF` | `0x7C9F` | `#627EEA` | `0x63FD` |

### Shading ramps

The diamond and the quorum's face are lit from the upper left. Each face's colour is picked along a
ramp by how much it faces the light.

- **Diamond:** `#1E245C` to `#DAE2FF`
- **Quorum face:** `#006024` to `#78FF96`. Face green, where the triangle fills, is `#5FDE7E`.

### Outside the brand

These are for meaning only, never decoration.

- **Reject red** `#FF5C54` (light `#D02424`): the Reject button and anything that can't be undone.
  A red page is red all over.
- **Stake cyan** `#70D6FF` (light `#0068AA`): the thing at stake on a red page, such as the address
  that gains power or the amount. The only non-red colour there.

## Type

The console's job is to make people compare addresses and hashes before they sign. Atkinson
Hyperlegible, from the Braille Institute, was drawn to keep look-alike characters apart: capital I,
lower-case l and the digit 1 are three different shapes, and so are O and 0.

- **Atkinson Hyperlegible Next** sets words.
- **Atkinson Hyperlegible Mono** sets addresses, hashes and the verify code.

Both are SIL Open Font License. The firmware renders exactly these seven sizes
(`tools/fonts/gen.py`). Don't add an eighth.

| Token | Role | Face | Example |
|---|---|---|---|
| `bold26` | Headlines | Next Bold 26 | Send 0.05 ETH |
| `bold18` | Titles | Next Bold 18 | Add a new owner |
| `bold14` | Labels | Next Bold 14 | Family Safe · 3 of 5 |
| `sans14` | Body | Next Regular 14 | Nothing signs unseen |
| `sans12` | Captions | Next Regular 12 | Nonce 42 · proposed 2 hours ago |
| `mono13` | Addresses | Mono 500, 13 | `0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed` |
| `monob28` | Verify code | Mono 700, 28 | `3f9a c217` |

Open question: [FONTS.md](quorum-ui/v2/FONTS.md) compares five other sets for the words. Atkinson
Mono stays for addresses either way.

## Motion

The boot animation tells the brand's story in beats. These stills are emulator captures.

| | | |
|---|---|---|
| <img src="quorum-ui/v2/boot/orbit-132.png" width="200"> | <img src="quorum-ui/v2/boot/orbit-150.png" width="200"> | <img src="quorum-ui/v2/boot/orbit-198.png" width="200"> |
| **Sign.** Top, then left, then right. A ring goes out as each turns green. | **Fill.** Green pours up into their triangle. The two who didn't sign fade. | **Turn.** The triangle is one face of a pyramid. It turns into the Ethereum diamond. |
| <img src="quorum-ui/v2/boot/orbit-214.png" width="200"> | <img src="quorum-ui/v2/boot/orbit-256.png" width="200"> | <img src="quorum-ui/v2/boot/orbit-300.png" width="200"> |
| **Diamond.** It keeps spinning. | **Name.** The diamond grows, centres and dims; the lockup comes up in front. | **Rest.** Taglines cycle while the diamond keeps turning. |

### Rules

- **Nothing freezes.** Every frame is a function of one clock. While a boot step takes its time,
  waiting owners keep breathing and the diamond keeps turning.
- **Fade through the dark.** The panel has no transparency. A fade is a colour mix toward the
  background, so things arrive through their own dark shade.
- **Fill from the bottom.** Green pours up into the triangle with a bright surface line, then swells
  once in a soft glow. No flashes.
- **Land corner-forward.** The diamond's spin slows into 45° + 90°·n, its logo pose. A square
  pyramid repeats every 90°, so it can spin for as long as boot takes.

### Curves

- **Ease out**, `1 − (1 − t)³`: arrivals. Owners landing, lines drawing, signing rings.
- **Smoothstep**, `t²(3 − 2t)`: changes of state. The fill, the turn, the name and the taglines.

### Timing

One frame every 30 ms, as on the Pico.

| Moment | Frame | Time |
|---|---|---|
| Owners land, all amber | 64 | 1.92 s |
| Top owner signs | 76 | 2.28 s |
| Left owner signs | 100 | 3.00 s |
| Right owner signs: quorum | 124 | 3.72 s |
| Green fills the triangle | 138–160 | 4.14–4.80 s |
| The pyramid starts to turn | 174 | 5.22 s |
| The name comes up | 234–254 | 7.02–7.62 s |
| Taglines, one every | 38 | 1.14 s |

## Voice

A signing device should sound like a careful colleague. Short sentences, plain words, no hype. Talk
about owners, keys and the Safe, the things people can point at.

- **Steps.** A step in progress ends in an ellipsis and sits in slate beside a spinner: "Checking the
  chip…". When it's done, the ellipsis goes, the text turns white and a green check appears: "Chip
  verified".
- **Counts.** Write "3 of 5", never "3/5". It reads the same aloud as on screen.
- **Separators.** A middle dot separates facts on one line: "Family Safe · 3 of 5". No pipes, no
  slashes.
- **Tone.** Sentence case, no exclamation marks: "Ready", not "Ready!". Money is moving; the device
  stays even-tempered.
- **Buttons.** One verb each, saying exactly what happens. **Sign** is green and guarded; **Reject**
  is red and easy.

### Taglines (draft)

Placeholders until chosen:

- Your keys, your quorum
- Nothing signs unseen
- Hardware approvals for Safe
- Every hash checked here

"Hardware approvals for Safe" is compatibility wording. Don't use Safe's logo.

## Sources

`firmware/bootart.py`, `firmware/quorum_ui.py`, `tools/fonts/gen.py`, `docs/quorum-ui/v2/`.
