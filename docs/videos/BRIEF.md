# Explainer videos: the brief

*For a video studio or a freelancer quoting on this work. Written 2026-11-09. The same list as
data: [videos.json](videos.json). The scripts: [README.md](README.md).*

We want a set of short explainer videos for an open-source hardware project. Nine scripts are
drafted. This page says what the project is, what each video needs, what we can hand over, and
what we'd like a quote to cover.

## The project in one minute

Most crypto wallets come down to one secret, a seed phrase. Whoever has it has everything, and if
it is lost, so is everything. A **multisig** fixes that: a wallet with several owners, where
nothing moves until enough of them approve (say, two of three). **Safe** is the multisig we work
with.

**Picoquorum** is a small hardware console that is *one owner* of a Safe. Three things make it
different from a hardware wallet:

- **It has no seed phrase.** Its key is made inside a secure chip and can't be read out or copied.
- **It checks for itself.** It shows what a transaction does on its own screen, in plain words,
  and works out by itself exactly what it is about to sign. A lying web page or laptop gets a
  refusal.
- **It is not a wallet.** It holds no funds and can't send anything. It can only say yes or no to
  what the group proposed. You hold a button for two seconds to say yes.

It is open source, open hardware, early and experimental. It is built in public by one maintainer.
There is no company, no token and nothing for sale yet.

The site is [picoquorum.app](https://picoquorum.app/), and the console runs in a browser at
[picoquorum.app/console](https://picoquorum.app/console/): the fastest way to see what it does.
The project's own summary is the [README](../../README.md).

## Words you will meet

| word | meaning |
|---|---|
| seed phrase | 12 or 24 words that are a wallet's master secret |
| multisig | a wallet that needs several owners to approve |
| Safe | the multisig Picoquorum works with. A separate project; we are not affiliated |
| owner | one of the keys on a Safe's list |
| threshold | how many owners must approve: the "2" in "2 of 3" |
| console | the Picoquorum device: a screen, three buttons, a chip |
| key, secure element | the small chip that holds the signing key |
| cosigner | an owner that only approves; what the console is |
| approve, sign | the same act: hold the Sign button |
| red page | a console screen, red all over, for anything dangerous |
| verify code | eight characters and a small picture that two people compare |
| Mono | the console board the hardware videos are drawn on |

## Who watches

- **People new to crypto**, or new to holding it for a family, a club or a small company.
- **People who already use a wallet** and wonder what this adds.
- **Hardware and security people**, who will check every claim.
- **People about to hold a key** for someone else's Safe.

Each script names its audience. The videos will sit on [the Learn page](https://picoquorum.app/learn/)
and be posted by [@picoquorum](https://x.com/picoquorum) on X, so each one also needs a short cut.

## The videos

About 22 minutes in all. Each script gives the spoken lines, what is on screen for each, and the
short cut for X.

| # | video | length | what it needs on screen |
|---|---|---|---|
| | **Start here** | | |
| 1 | [One seed phrase, one point of failure](seed-phrase.md) | 2:20 | Simple motion graphics: a card of words, three keys round a box. Ends on the console |
| 2 | [Two of three: a multisig in two minutes](multisig-basics.md) | 1:45 | The friendliest one. People and keys, a box with more than one lock. No jargon, no screens of code |
| 3 | [The multisig is the wallet](cosigner.md) | 2:00 | Three kinds of wallet opening to the same card of words. A list of things crossed out |
| 4 | [One approval, start to finish](one-approval.md) | 2:00 | A screen recording of the app and the console, with hands. Little talk |
| | **The hardware** | | |
| 5 | [Inside the console](inside-the-console.md) | 3:15 | One picture of the board from above. Three zones light up in turn, and a transaction is followed across them |
| 6 | [When the hardware fails](hardware-failures.md) | 2:30 | The same board picture, six failure cases, each ending on the same counter |
| | **Being an owner** | | |
| 7 | [A new key, from the bench to your Safe](new-key.md) | 3:45 | A chip drawn as a box with padlocks, the console's screens, a label held up to a screen. Mostly a plan: "planned" stays on screen |
| 8 | [A key with no backup](no-backup.md) | 2:10 | A key board in a hand; simple graphics for copies of a secret, and for one owner being swapped |
| 9 | [What it protects, and what it doesn't](threat-model.md) | 2:30 | A person talking to camera with the console on a table, or the same in animation. The plainest one |

Videos 5 and 6 share one board picture and can be made as a pair. More are planned and not
written ([README.md](README.md#ideas-not-written-yet)); a quote that prices one more video of each
kind helps us plan.

## How it should look and sound

- **Calm and plain.** No hype, no countdowns, no coins raining down, no hooded hackers. The
  console's own screens are the model: dark ground, clear type, green for done, amber for waiting,
  red only for danger.
- **Colours** ([BRAND.md](../BRAND.md#colour)): night `#0B0D11`, paper `#F2F4F7`, slate `#98A0AC`,
  signed green `#34C759`, waiting amber `#FFB830`, ether `#7A92FF`.
- **Type**: Atkinson Hyperlegible Next, and Atkinson Hyperlegible Mono for addresses and codes. Both
  are free (SIL Open Font License).
- **The mark** is three of five dots joined in a triangle. Its files and rules are in
  [BRAND.md](../BRAND.md) and [docs/brand/](../brand/).
- **The name** is **Picoquorum**: one word, one capital. Never PicoQuorum, Pico Quorum or PQ.
- **Voice**: short sentences, plain words, as the scripts are written. A human voice or a good
  synthetic one are both fine; tell us which you priced.
- **Captions** on every video, burned in for the X cuts.

## What we can hand over

All of it is in the public repository, [github.com/jmcpheron/pico-quorum](https://github.com/jmcpheron/pico-quorum).

| what | where |
|---|---|
| The scripts | this folder |
| The logo and mark, as SVG | [docs/brand/](../brand/) |
| The boot animation | [docs/quorum-ui/v2/boot/](../quorum-ui/v2/boot/) |
| Screenshots of every console screen, 240 × 240 | [docs/quorum-ui/shots/](../quorum-ui/shots/) |
| The console running live, to record from | [picoquorum.app/console](https://picoquorum.app/console/) |
| The app, to record from | [picoquorum.app/app](https://picoquorum.app/app/) |
| 3D renders of the Mono board | [hardware/mono/renders/](../../hardware/mono/renders/) |
| The Mono board as a KiCad project, for new renders or a 3D model | [hardware/mono/](../../hardware/mono/) |
| Renders of the key and of an earlier console board | [hardware/key-pcb/key-c-usbc/renders/](../../hardware/key-pcb/key-c-usbc/renders/), [hardware/console-rp/renders/](../../hardware/console-rp/renders/) |
| Screens for the key ceremony (video 7) | [docs/branded-keys/](../branded-keys/) |

What we can't hand over yet: **a real Mono board on camera.** It is designed and not built. Until
one exists, the hardware videos use renders, and say so on screen.

## Rules the videos must keep

These are not style notes. A video that breaks one can't go out.

1. **Say only what the script says.** Each claim was checked against the project's docs. If a line
   needs to change to fit a shot, ask; don't reword a claim.
2. **Never say "secure", "unhackable", "audited" or "safe to use".** Say what it does.
3. **Say "experimental"** once in every video.
4. **It is a cosigner, not a wallet.** Never show funds going to the console or to its key.
5. **A plan is shown as a plan.** Where a script marks a step as not built, "planned" stays on
   screen.
6. **No real secrets on screen**: no real seed phrase, key, password or API key in any frame. A
   seed phrase used as a prop is made up for the shot. Demos use test networks only.
7. **No other company's logo**: no wallet brand, no chip maker's, no Safe logo, no Raspberry Pi
   logo. Picoquorum is not affiliated with Safe or Raspberry Pi.
8. **We check each video before it goes out**, against the "Check before recording" list at the
   end of its script. Some facts change month to month; please plan for one round of script changes
   close to delivery.

## What we'd like in a quote

- A price for **video 1 alone**, as a pilot.
- A price for **all nine**, and for each of the three areas.
- A price for **one more video** of each kind: motion graphics, screen recording, talking head.
- For each video: the full cut in 16:9, the short cut for X named in its script, a 9:16 version of
  the short cut, captions as a file (SRT or VTT), and a thumbnail at 1280 × 720.
- **The working files** (project files, illustrations, the board model), so later videos can reuse
  them. Say if that changes the price.
- How you'd handle **voice**, and **music** if any. Music must be cleared for the web and for X.
- **Rounds of changes** included, and your timeline for the pilot and for the set.
- Which of the nine you would do differently, and why. The scripts fix what is said, not how it
  looks.

**Licence.** The project's docs are under [CC BY-SA 4.0](../../LICENSE-DOCS), and we'd like to
publish the videos the same way. If any part can't be (stock footage, music, a voice), tell us in
the quote. The name and the mark are not covered by that licence
([TRADEMARK.md](../../TRADEMARK.md)).

**Not decided yet**, so not in this brief: the budget, the deadline and where the videos are
hosted. Ask.

## Contact

Jason McPheron, the maintainer: [@picoquorum](https://x.com/picoquorum) on X, or open an issue on
the repository.
