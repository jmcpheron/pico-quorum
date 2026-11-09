# Explainer videos: the scripts

*Started 2026-11-09. Nine draft scripts. No video is recorded yet.*

Short videos that explain why a multisig, and what Picoquorum adds to one. The videos are made in
another project. This folder holds what they say: one script per video, written and checked here,
next to the docs they draw on. [The Learn page](https://picoquorum.app/learn/) (built from
[`web/src/learn.html`](../../web/src/learn.html)) has a card for each, with a box where its
thumbnail will go.

**Handing this to a studio?** [BRIEF.md](BRIEF.md) is the brief: what the project is, what each
video needs, what we can hand over, and what a quote should cover. [videos.json](videos.json) is
the same list as data.

The videos are in three areas, as on the Learn page.

**Start here**: why a multisig, and what an approval looks like.

| | video | for | length | status |
|---|---|---|---|---|
| 1 | [One seed phrase, one point of failure](seed-phrase.md) | everyone | 2:20 | draft script |
| 2 | [Two of three: a multisig in two minutes](multisig-basics.md) | new to crypto | 1:45 | draft script |
| 3 | [The multisig is the wallet](cosigner.md) | wallet users | 2:00 | draft script |
| 4 | [One approval, start to finish](one-approval.md) | everyone: the demo | 2:00 | draft script |

**The hardware**: the board, zone by zone, and how it fails. Drawn on
[Mono](../../hardware/mono/README.md), the board planned for developer kits. Videos 5 and 6 share
one picture and can be recorded as one.

| | video | for | length | status |
|---|---|---|---|---|
| 5 | [Inside the console](inside-the-console.md) | the technical | 3:15 | draft script |
| 6 | [When the hardware fails](hardware-failures.md) | the technical | 2:30 | draft script |

**Being an owner**: what holding a key asks of you.

| | video | for | length | status |
|---|---|---|---|---|
| 7 | [A new key, from the bench to your Safe](new-key.md) | someone about to get a key | 3:45 | draft script; mostly a plan |
| 8 | [A key with no backup](no-backup.md) | owners | 2:10 | draft script |
| 9 | [What it protects, and what it doesn't](threat-model.md) | owners, and their co-owners | 2:30 | draft script |

The lengths are targets, at about 150 spoken words a minute.

## How a script is laid out

- **The one idea.** What a viewer should be able to say afterwards, in a sentence.
- **Script.** What is said, in order. A line in italics that starts *Shows:* is what is on screen
  while it is said.
- **Check before recording.** Each claim that could go out of date, and the doc that settles it. The
  project changes fast: read this list again on the day.
- **For X.** A draft post for [@picoquorum](https://x.com/picoquorum), and the cut to use if the
  whole video is too long for it.

## Rules for every script

- **A plan is called a plan.** A video about something proposed and not built
  ([A new key](new-key.md) is the first) says so in its first line, and keeps "planned" on screen
  for each step that isn't built.
- **Say what is true today.** If something is planned and not done (secure boot is the standing
  example), the script says "not yet". [SECURITY.md](../SECURITY.md) and [STATUS.md](../STATUS.md)
  win over any script.
- **Say "experimental".** Every video says it once: early design, a testnet first, small amounts on
  mainnet, and the Safe's threshold is the real control.
- **Never call it secure or audited.** Say what it does and what was checked.
- **It is a cosigner, not a wallet.** One owner of a Safe, next to owners of other kinds.
- **No real keys on screen.** No seed phrase, API key or Wi-Fi password in any frame, and only
  testnet Safes and the emulator's test keys in a demo. A seed phrase shown as a prop is made up
  for the shot and never used.
- **Plain words, short sentences**, as in the rest of the docs.
- Picoquorum is not affiliated with Safe or Raspberry Pi. A video that shows either says so in its
  description.

## When a video is ready

1. Set its status in the table above and in `videos.json`, and add its link to both.
2. In `web/src/learn.html`, put its thumbnail in the card (a file under `web/src/`, copied by
   `web/build.mjs` like the handheld's card) and make the card link to the video.
3. A link out needs nothing else. A player embedded in the page needs the page's
   Content-Security-Policy changed (`frame-src` or `media-src`), and that is a decision to make on
   its own, not a copy edit.
4. `cd web && npm run build && npm test`, and commit what it writes.

## Ideas not written yet

Start here:
- **Why the hash.** What a Safe transaction hash is, and why the console works it out itself.
- **Red pages.** What the console treats as dangerous, and why those pages are red all over.
- **Onboarding cuts.** The same ideas at 30 seconds each, for X: one for newcomers, one for wallet
  users, one for hardware people.

The hardware:
- **Sealing a key.** The key ceremony, and locks that can't be undone ([LOCKING.md](../LOCKING.md)).
- **Check it yourself.** The console page is one folder: save it, hash it, hold it up to the
  README's fingerprint, sign from your own copy ([guide/BROWSER.md](../guide/BROWSER.md)). And the
  same fingerprint on a board's Device screen.
- **Is this chip real?** What a key's attestation proves, and what it can't
  ([mainnet/THREAT-MODEL.md](../mainnet/THREAT-MODEL.md), "What the binding proves").
- **Build a dev console**, and then **the developer kit**: what is in the box and the first
  approval on a testnet ([hardware/DEV-CONSOLE.md](../../hardware/DEV-CONSOLE.md)). The kit's video
  waits for the kit.
- **Secure boot, when it is on.** What was burned, what it stops, and what it cost.

Being an owner:
- **A console is lost: what happens next.** The other owners swap it out, step by step, on a
  testnet Safe ([mainnet/COSIGNERS.md](../mainnet/COSIGNERS.md), section 4). The follow-on to
  videos 8 and 9.
- **Giving someone a key.** The keyholder's three jobs, the handover, the card in the drawer and
  the voice rule ([ONBOARDING.md](../ONBOARDING.md)). For the person who sets a Safe up for others.
- **The gas relay and its treasury**, once they exist ([ATTESTED-KEYS.md](../ATTESTED-KEYS.md)).
- **No technology, and no person, holds a threshold.** How to pick the owners of a Safe
  ([GOVERNANCE.md](../GOVERNANCE.md), [mainnet/CONFIGURATION.md](../mainnet/CONFIGURATION.md)).
- **For the other owners.** What a console's confirmation means when you are a co-signer, and
  what to check on your own device anyway ([mainnet/COSIGNERS.md](../mainnet/COSIGNERS.md)).
