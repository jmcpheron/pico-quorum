# The UI lab: the three-button console's screens, mapped and walked

This is where the console's three-button UI is worked on: what each screen is, what each button
does on it, how one screen gets to the next, and what we have decided about all of it. It covers the
boards with a 240 × 135 screen and D0, D1, D2: the Feather, PicoquorumKey, console-rp and
[Mono](../../../hardware/mono/README.md), which runs console-rp's image.

| | |
|---|---|
| [MAP.md](MAP.md) | Every screen, what each button does on it, and every transition. Written by a script from the real firmware. |
| [The explorer](https://picoquorum.app/quorum-ui/lab/explore/) | The same flows in a browser: press D0, D1, D2 and watch the screens. On the site once this is on `main`. |
| [DECISIONS.md](DECISIONS.md) | What is settled, what is open, and why. |
| [`tools/uilab/flows.mjs`](../../../tools/uilab/flows.mjs) | The flows: what a person presses, step by step. The map and the explorer are made from these. |
| [Issues](https://github.com/jmcpheron/pico-quorum/issues/new/choose) | "A UI idea" and "A screen that reads wrong" are forms for this. |

The older walkthroughs are still the place for the big screen and for each board's pictures:
[the 240 × 240 console](../README.md), [the Feather](../feather/README.md), [other sizes](../SCREENS.md).

## Two layers

The console's UI is two layers, and the lab keeps them apart.

**The structure** is what the screens are and what the buttons do. It is the same on every
three-button board, and it carries the rules in [AGENTS.md](../../../AGENTS.md): every page seen
before Sign, Sign held, Reject one press.
- `firmware/quorum.py` holds the state (`state`, `tab`, `page`, what has been seen) and takes every
  press in one place, `three(k)`.
- `firmware/quorum_ui_s.py`'s `pages_of` says which pages a transaction has. `quorum.py` counts
  them for "see every page".

**The look** is how a screen is drawn and how it arrives: colours, type, where the buttons are
named, and any effect between two screens.
- `quorum.U` is the module that draws. On `main` it is `quorum_ui_s` for these boards, with a dark
  and a light theme (`QUORUM_THEME`).
- console-rp's CRT look, with its tear and lock effects, is a second module over the first
  (`quorum_ui_crt.py` and `crt.py`). It is in
  [pull request 113](https://github.com/jmcpheron/pico-quorum/pull/113), not on `main` yet.

A look may change every pixel. It may not change which pages there are, their order, what a button
does, or what must be seen before Sign. [DECISIONS.md](DECISIONS.md) has the rest, and the open
question of making the look a setting.

## How it is tested

```sh
(cd emu && npm ci)
node tools/uilab/build.mjs            # press every flow, write MAP.md and explore/
node tools/uilab/build.mjs --check    # CI's: what is committed is what the script writes
node tools/uilab/e2e.mjs              # the explorer in Chromium (PQ_CHROMIUM=/path/to/chrome)
node test-vectors/run-console.mjs     # the console's decisions, three buttons included
```

What the build does, and what it checks:
- It runs the firmware in `firmware/` on MicroPython for WebAssembly, with `test-vectors/console_test.py`'s
  fake service and clock and the emulator's virtual chip. It presses buttons through the console's
  own `tick`, so a press goes where it goes on a board.
- **A flow is a test.** A tick that raises stops the build.
- **Every screen is walked.** It reads the states `quorum_ui_s.draw` and `quorum.three` name. If one
  has no flow, the build fails until a flow reaches it or `flows.mjs` says why not.
- **The map is the diff.** `MAP.md` and `explore/map.json` are committed. A change to what a button
  does changes them, and CI fails until they are rebuilt, so the change shows in the pull request.
- Two runs write the same bytes (five in a row did, 2026-11-10). Three things are pinned for that:
  the virtual chip's key is a fixed test key, the clock is `console_test`'s, and the Device screen's
  free memory reads 1024 KB.

What it does not check:
- **A board.** The frames are the emulator's. Timing, the panel and the buttons' feel are checked
  on hardware.
- **Effects.** They are switched off for the pictures, as in the shots. On a look that has them the
  map records which effect each transition asked for, not how it plays.
- **Every press on every screen.** `MAP.md`, "Not walked yet", lists the buttons no flow presses.

## When a feature changes the UI

1. Say what changes in the issue or pull request: which screens, which buttons.
2. Change the firmware. A new state fails `node tools/uilab/build.mjs` until step 3 is done.
3. Add or change a flow in `tools/uilab/flows.mjs` so the new screen is reached and each button on
   it is pressed.
4. Run the build. Read the diff of `MAP.md`: the screens table, the buttons table, the transitions.
5. For a look with effects: every new row in "Every transition walked" has an effect or "none".
   Decide each one. The rules are in [DECISIONS.md](DECISIONS.md), "Effects".
6. If the change settles or reopens something, add it to `DECISIONS.md`.
7. Firmware changed, so the release fingerprint did: `node tools/releases/badge.mjs`, and rebuild
   the console page (AGENTS.md, rule 2).

## Adding a board, or a look

`tools/uilab/flows.mjs` lists the boards walked: the Feather today.

When console-rp's image is on `main`, its board joins the list. A trial on that branch
(2026-11-10, in a scratch copy, nothing committed) needed:
- `walk.py`'s `boot` to start it as that branch's `tools/board/shots_rp.mjs` does: a relay in place
  of Wi-Fi, and `quorum.U = quorum_ui_crt`;
- the Device flow changed, since console-rp has no Wi-Fi row. The build said so itself: "the
  firmware draws device and no flow reaches it".

With that, the map gained an effect column: 52 transitions, each with tear, short, strong, lock or
none. The explorer shows one board. It needs a way to pick one before a second is added.

## The folder

- `README.md` and `DECISIONS.md` are written by hand.
- `MAP.md` and everything in `explore/` are written by `node tools/uilab/build.mjs`. Don't edit them.
- The explorer's own files come from `tools/uilab/page/`. A frame's name is the start of the
  SHA-256 of its pixels, so the same picture is one file whichever flow reached it.
