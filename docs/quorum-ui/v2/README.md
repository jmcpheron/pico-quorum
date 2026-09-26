# PicoQuorum UI, v2: the plan, and the new boot screen

A redo of the console's look, starting with the boot screen. Each iteration adds a section here
with screenshots and what changed. Every picture is the real drawing code running in the emulator
(pixel-for-pixel the Pico's 240×240 panel, shown at 2×). Comment on any line in the pull request,
or edit the [change requests](#change-requests) list at the bottom straight in GitHub.

What came before: [the v1 walkthrough](../README.md) (the approval screens, iterations 1–3) and
its four [boot screen options](../README.md#boot-screen-options). The 2-of-3 "Quorum" triangle
there is where this one starts.

## The plan

1. **The boot screen** (this iteration): a 3-of-5 star whose quorum becomes the Ethereum diamond.
2. **Wire it to the real boot.** Each signature is a real boot step finishing, and the spin
   covers the slow ones (see [On the device](#on-the-device)).
3. **Type.** Five candidate sets on a specimen card and on six real screens: see
   [FONTS.md](FONTS.md). Waiting on your pick.
4. **Colour and graphics.** Bring the boot screen's palette and shapes into the approval screens:
   the home screen, the approvals row, and the moment of signing.
5. **Every screen, redone,** with before/after pairs like the v1 walkthrough.

## Iteration 1 (2026-09-26): star to Ethereum

<img src="boot/star.gif" width="60%">

`emu/sketches/ethboot.py`, 150 frames at the firmware's 50 ms tick (7.5 s, then the last frame
holds). `tools/emu run ethboot` plays it in the emulator; A replays it.

### Frame by frame

| | |
|---|---|
| <img src="boot/star-020.png"> | <img src="boot/star-035.png"> |
| **Five owners, ready.** A pen draws the star in one stroke, and each owner appears as it gets there. All five are amber, which means they can sign but haven't. The ones still waiting breathe slowly. | **Signing.** The top signs, then the left leg. Each one turns Ethereum blue and sends out a ring, and a blue line joins it to the top. |
| <img src="boot/star-046.png"> | <img src="boot/star-052.png"> |
| **Quorum.** The right leg signs and the base closes. That's the tall triangle made by the star's top and legs (36° at the tip). The two owners who didn't sign start to fade. | **The triangle fills in.** It's about to become a solid face. |
| <img src="boot/star-058.png"> | <img src="boot/star-070.png"> |
| **It's a pyramid, seen head-on.** The filled triangle is exactly one face of a square pyramid. The three signers sit on its tip and its two front corners. | **The camera pulls back and rises**, and the pyramid starts to turn. The signers ride their corners, then shrink away. |
| <img src="boot/star-080.png"> | <img src="boot/star-092.png"> |
| **The inverted pyramid rises** underneath, fading in from dark blue. | **The Ethereum diamond,** spinning on its axis. The gap between the two halves stays an even band at every angle. |
| <img src="boot/star-149.png"> | |
| **It slows to a stop** with a corner toward you: the logo's own pose. Then the name comes up. | |

### How it's drawn

- **The star** uses lines and filled circles, the same as the v1 option.
- **The diamond** is ten 3D points, turned and projected each frame. It's drawn as flat-shaded
  triangles with `framebuf.poly` (which runs in C), back faces dropped, far faces first. That's at
  most four triangles a frame, so it should cost about what the v1 Quorum option did on the board
  (54 ms a frame, most of it the 46 ms push to the panel). Not timed on the chip yet.
- **It lands on the logo whatever the speed.** A square pyramid looks the same every 90°, so the
  spin can run as long as the boot takes and still stop on a corner (45° + any number of quarter
  turns).
- **The handoff is exact.** The pyramid starts with the star triangle's proportions, so its face
  seen head-on *is* that triangle. It widens a little (0.33 → 0.37 half-base per
  unit of height) as it turns, to match the logo.
- **Colours:** amber (the theme's `warn`) means ready to sign. Signed is Ethereum's periwinkle
  (#627EEA) lifted to `(122, 146, 255)` so it reads on near-black. The diamond is shaded from dark
  indigo to pale lavender, lit from the upper left.
- **The shape is drawn here, not copied.** It's two pyramids built from points, not the
  Ethereum Foundation's artwork. Still, it's meant to read as their mark, so check their brand
  guidance before anything ships.

### What I'd change next (your call)

- **Jagged edges.** `framebuf.poly` doesn't anti-alias. At 2× in the GIF the steps show; on the
  1.3″ screen (about 260 pixels per inch) they're small. A cheap fix is a 1-pixel edge in an
  in-between colour.
- **A glint.** A highlight sweeping across the diamond once it lands.
- **The "not signed" owners** just fade out. They could slide back into the dark instead.
- **Timing.** The whole thing is 7.5 s. On the device, the star part would take as long as the
  real boot steps (see below), and the spin could be shorter once it's ready.

### Questions for you

1. **Blue or green for "signed"?** Ethereum blue ties it to the diamond. Green is what "signed"
   means on every other screen (the SIGN bar, the check marks).
2. **Amber means two things now.** Here it's "ready to sign". On the approval screens amber means
   caution (a yellow page). Keep amber here, or use something neutral (white, grey) for waiting?
3. **3 of 5, always?** The demo Family Safe is 2 of 3. Options:
   - The star is the brand mark and always 3 of 5, and only the line under the name shows the real
     Safe ("2 of 3 · ready").
   - Or draw the real Safe's owners (M points, the first N light up). But only 3 of 5 makes the
     triangle that becomes the diamond.
4. **Ethereum, or the chain it's on?** The Safe might live on Base. Keep the diamond regardless
   (it's all Ethereum), or end on the chain's own mark?

## On the device

This is a proposal; none of it is wired up yet. Today `firmware/splash.py` draws the boot checklist.

| Boot step | What the star shows |
|---|---|
| Screen up | the star draws in, five amber owners |
| WiFi joined | the top signs |
| The chip answers with its key | the left leg signs |
| The Safe found, through the service | the right leg signs, the quorum closes |
| Loading the queue | the diamond spins, as long as it takes |
| Ready | it lands on the logo, and the home screen follows |

- **If a step fails,** that owner turns red and the error goes where the name would be, like the
  checklist's error line today.
- **To try it on the board** without changing `main.py`: `tools/emu ship ethboot`. I haven't
  timed it on the chip yet.

## Type and graphics: where to go next

Today (v1, iteration 2): Atkinson Hyperlegible Next and Mono, seven sizes, rendered on the laptop
by `tools/fonts/gen.py` and drawn by the Pico with 16 levels of anti-aliasing. It was picked for
telling 0/O and 1/l/I apart, which matters on a device for comparing addresses. So:

- **Keep a hyperlegible mono for addresses and hashes,** whatever else changes.
- **A display face for names and headlines** is where the "better fonts" can come from. These are
  all open-licence and `gen.py` can render any of them. I'd put these side by side on the real
  screen:
  - **Inter Display + Inter.** Neutral, very clear at small sizes.
  - **Space Grotesk + JetBrains Mono.** More character, a bit "crypto".
  - **IBM Plex Sans + Plex Mono.** Engineered, calm.
  - **Manrope.** Round and friendly, with Atkinson Mono kept for addresses.
- **Graphics from the boot screen:**
  - The approvals row (`1 of 2 ● Alice ○ Bob ○ You`) becomes a small star or polygon of the
    Safe's owners.
  - Signing plays the ring and the colour change from the boot screen.
  - The home screen's corner carries a small still of the diamond.

## Run it yourself

```sh
tools/emu run ethboot                                   # play it in the emulator; A replays
tools/bootgifs --sketch ethboot --stills 20,35,46 star  # this page's GIF and stills
tools/emu ship ethboot                                  # a one-off run on the Pico
```

`tools/bootgifs` now takes `--sketch`, `--out` and `--stills`. It also builds each GIF's palette
from frames across the whole animation instead of only the last one. That kept the amber here, and
it gave the v1 hash-rain GIF back the blue it had lost.

## Change requests

Edit this list on GitHub: add a line, tick one off, or write under it. Each iteration starts here.

- [x] A new boot screen: a 3-of-5 star, the top and legs sign, the triangle becomes the top of a
      rotating Ethereum diamond (iteration 1)
- [x] Fonts: candidates side by side on real screens ([FONTS.md](FONTS.md))
- [ ] Pick a font set (FONTS.md, question 1)
- [ ] (add yours)
