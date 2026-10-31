# Four directions for the cosigner's screens

> **A first draft, 2026-10-31, to pick from.** Each direction draws the same four screens:
> - a control change from unknown code (the warning)
> - a routine payment
> - holding to sign
> - home
>
> They are drawn by [`emu/sketches/ui_directions.py`](../../../emu/sketches/ui_directions.py) with the
> console's own drawing code and fonts. `node emu/render-cosigner-ui.mjs ui_directions <out> build1-2.4`
> (or `waveshare`) redraws them. Mock-ups only: no chip, no service, nothing signed, made-up
> transactions.

Two things are the same in all four, and come from the plan ([README.md](README.md)):
- **The controls.** Turn: pages. Push: open, or leave a review, with nothing sent. The sign switch: sign,
  held. **There is no Reject.** A cosigner can only not sign. A Safe transaction is cancelled when the
  owners execute another one at the same nonce, and the warning screens say so.
- **The content.** What it can do first, whether the code is known second, then the facts, all
  worked out on the device.

What changes is how it looks and how it speaks.

## The lead so far: the checklist (B's calm, C's rules)

*"You can read the whole screen."* After the first round, C's list won: every fact on its own line,
read top to bottom, and nothing on the screen pulling the eye somewhere else. B's big headline and
scattered colour did. So the checklist keeps C's structure on **every** screen, not only on
warnings, and takes B's calm: graphite, not black; hairlines between groups; one mixed-case title.

Drawn by [`emu/sketches/ui_checklist.py`](../../../emu/sketches/ui_checklist.py):
`node emu/render-cosigner-ui.mjs ui_checklist docs/quorum-ui/v3/checklist/320 build1-2.4` (or
`.../240 waveshare`).

| | | | |
|---|---|---|---|
| ![home](checklist/320/01-home.png) | ![payment](checklist/320/02-send.png) | ![warning](checklist/320/03-warn.png) | ![upgrade](checklist/320/04-upgrade.png) |
| **Home.** What waits, where, and the key. | **A payment.** Routine: green light, four facts, two actions. | **A module from nowhere.** Red light. Only the reasons are coloured. Sign is inhibited. | **Account upgrade, on purpose.** Amber. The code is verified; arm, then hold 3 s. |
| ![two at one nonce](checklist/320/05-conflict.png) | ![holding](checklist/320/06-hold.png) | ![signed](checklist/320/07-done.png) | |
| **Two at one nonce.** How cancelling works without a Reject: approve the no-op, and when it executes the other can't. | **Holding.** The bar, what is signed, and that nothing is sent yet. | **Signed.** What happens next. | |

At 240 × 240 in [`checklist/240/`](checklist/240/). The same lines, with short values.

**Its rules:**
1. **Every screen has one shape:**
   - the context line (Safe, chain, nonce, page)
   - a light and a title
   - the facts
   - a hairline, then what you can do
   - then what the device checked itself
2. **One fact a line:** `LABEL ...... value`. Labels in capitals, values as they are (`Carol`,
   `enableModule`). The dotted leader ties each value to its label, so the eye can run down
   either column.
3. **The light is the only block of colour.** Red WARNING, amber CAUTION, green ROUTINE or SIGNED,
   cyan SIGNING, amber REVIEW on home.
4. **In the list, colour marks a reason, never decoration.**
   - **red:** the line that makes it dangerous
   - **amber:** the line to be careful about
   - **green:** something the device checked
   - **cyan:** something you can do
   - **grey:** something you can't do now (`- SIGN .... INHIBITED`)
   - everything else is white
5. **What you can do is part of the list,** not a footer: `- SIGN .... HOLD 2 S`, `- LEAVE .... PUSH`,
   `- CANCEL .... OTHER TX AT N42`. The controls are the knob (turn, push) and the sign switch
   (`HOLD TO SIGN`).
6. **The last line is what the device worked out itself,** `+ HASH 5A3C..9E21 .... MADE HERE`, in
   green.
7. **Every value has a short form** for 240 wide, written with it.
8. **The console's own fonts** (Atkinson Hyperlegible Mono and Next), so nothing is added to the
   image.

## The four at 320 × 240 (the pico-sign build's 2.4″)

Rows: A, B, C, D. Columns: warning, payment, holding, home.

| | warning | payment | holding | home |
|---|---|---|---|---|
| **A** terminal | ![](directions/320/01-A-terminal-warn.png) | ![](directions/320/02-A-terminal-send.png) | ![](directions/320/03-A-terminal-hold.png) | ![](directions/320/04-A-terminal-home.png) |
| **B** instrument | ![](directions/320/05-B-instrument-warn.png) | ![](directions/320/06-B-instrument-send.png) | ![](directions/320/07-B-instrument-hold.png) | ![](directions/320/08-B-instrument-home.png) |
| **C** annunciator | ![](directions/320/09-C-annunciator-warn.png) | ![](directions/320/10-C-annunciator-send.png) | ![](directions/320/11-C-annunciator-hold.png) | ![](directions/320/12-C-annunciator-home.png) |
| **D** statement | ![](directions/320/13-D-statement-warn.png) | ![](directions/320/14-D-statement-send.png) | ![](directions/320/15-D-statement-hold.png) | ![](directions/320/16-D-statement-home.png) |

The same at 240 × 240 (the Waveshare 1.3″) is in [`directions/240/`](directions/240/).

## A. Terminal

*"This is low-level, and it matters."*

**The idea.** The machine speaks in its own voice: a bitmap font on an 8 px grid, capitals for labels,
pixel icons, and a coloured band that says what the transaction can do. It looks like a serial
console or a 16-bit system screen. It carries on the boot screen, so the whole device feels like one
object.

- **Good:** unmistakable, and serious in a way people read as "close to the metal". It costs
  nothing: the 8 × 8 font is built in, so there are no font files in the image and drawing is fastest.
  Every pixel is deliberate, so it renders the same on every panel.
- **Not so good:** the 8 × 8 font is small: about 1.1 mm tall on the 1.3″ Waveshare. Long lines don't
  fit in 30 columns, so values get cut to their short forms (`0xC0FF..4979`). Capitals everywhere make
  everything shout, so the band has to do the work. It reads as a style, which some people will find
  less professional.
- **Small screens:** works, but tight. It needs a short form of every string.

## B. Instrument

*"Quiet until it matters."*

**The idea.** A well-made measuring instrument, or Swiss typography. Graphite background, IBM Plex
Sans for words and Plex Mono for addresses and hashes. A clear ladder of type:
- a muted context line
- a coloured status dot and word
- one large headline
- labelled facts

No boxes, no bands, hairlines only. Colour is reserved for meaning: a thin red edge and red words
on the warning, nothing else. The amount is the headline on a payment, with the unit in grey.

- **Good:** the most professional of the four. Easy to read at a glance; the hierarchy does the work,
  not decoration. The anti-aliased type looks sharp on the small panels, not blocky. It would sit
  well next to the web app.
- **Not so good:** quiet can mean easy to miss. A warning has less visual weight than A's or C's
  red band, so it relies on the red edge, the status word and the locked Sign. Plex is about 30 KB of
  font files, added to the image (today's Atkinson Hyperlegible would do the same job at no cost).
- **Small screens:** works well at 240. The headline and the two-column facts collapse to one column.

## C. Annunciator

*"A cockpit, not an app."*

**The idea.** Aviation spent decades learning how to tell a crew something has gone wrong. This
borrows its discipline, the way an aircraft's warning display lists faults:
- black background, monospace capitals
- a master WARNING light top left
- each fact as one line with a dotted leader to its value
- a fixed colour grammar: **red** means warning, act; **amber** caution; **cyan** what you can do
  next; **green** normal or verified; **white** information

The actions are lines too: `-SIGN ...... INHIBITED`, `-CANCEL ...... EXEC N42 TX`.

- **Good:** the strongest warnings of the four. The colour grammar is strict, so a person learns it
  once and reads every screen fast. The dotted-leader lines line up like a checklist, so a long
  transaction stays scannable. It uses the console's existing Atkinson Hyperlegible Mono and bold,
  so nothing is added. It is quick to draw.
- **Not so good:** dense and jargon-shaped (`APPR`, `N42`, `EXEC`). It is the least friendly to a
  newcomer, and abbreviations must be chosen with care. It looks like equipment, so it may feel cold.
- **Small screens:** works at 240 once the footer drops to two items; the Sign state is in the body.

## D. Statement

*"Say it in one sentence you could read out loud."*

**The idea.** Each page is one plain sentence: *"Stop. This would let an unknown contract move
everything in the Safe."* or *"Send 0.05 ETH to Carol."* Then one line of why, then the hard facts in
small type, then one rounded bar that says what to do. Light paper background, Inter, a coloured
stripe across the top. The first word carries the page's colour: **Stop.** It is closest to a
well-made payment app, or a printed receipt.

- **Good:** the easiest to understand for someone who doesn't know Safe, modules or nonces. The
  sentence is what a person tells a co-signer on the phone. In daylight a light screen reads best.
  It feels finished and calm.
- **Not so good:** every kind of transaction needs a sentence template, and a wrong template is a
  security bug: the words *are* the review. It fits less per page, so long transactions are more
  pages. Light screens use more backlight and show a cheap TFT's uneven backlight and narrow viewing
  angle; the 2.4″ IPS is fine, the 1.3″ less so. Inter is about 30 KB of font files.
- **Small screens:** works at 240, but the sentences take most of the page.

## Side by side

| | A terminal | B instrument | C annunciator | D statement |
|---|---|---|---|---|
| reads as | a system console | a precision tool | flight equipment | a calm app |
| warning strength | strong (band) | medium (edge, word) | strongest (master light, grammar) | strong (Stop., stripe) |
| for a newcomer | medium | good | hard | best |
| facts per page | many, short | medium | many | few |
| on 240 × 240 | tight | good | good | roomy enough |
| added to the image | nothing | ~30 KB (Plex) or nothing (Atkinson) | nothing | ~30 KB (Inter) |
| drawing cost | lowest | low | low | low |
| main risk | looks like a style | warnings too quiet | jargon | wording is security-critical |

## The first recommendation, and what changed

The first recommendation was B's look for routine screens and C's rules only when something is red.
On a look at all four, the list was what worked: a person can read every line of it, and a routine
page and a warning are read the same way, with the colour only where the reason is. So the
checklist above uses C's shape everywhere. A's pixel art stays as the boot screen, the device's
signature.

## What it would take to go further with any of them

1. Draw the rest of the review in the checklist: page 2 of the warning and the upgrade, a
   multi-call batch, the registry page, the 240 × 135 Feather.
2. Hand it to two or three people who haven't seen the project, on the pico-sign build, and watch where they
   look first on the warning.
3. Then build it into the console's screens, 320 × 240 first.
