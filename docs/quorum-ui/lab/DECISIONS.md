# The three-button UI: what is decided, and what is open

One entry per decision. Each says what was decided, why, and where it lives in the code, so a
change to the code and a change to this page go in the same pull request. To question one, or to
add an open one, open an issue with the "A UI idea" form and name the entry.

The entries marked **settled** were read out of the code and its comments on 2026-11-10. They were
decided before this page existed; the dates of the original decisions are in the commits.

## Settled

### S1. Each button works the strip of screen level with it

D0 the tabs along the top, D1 the list in the middle, D2 the bar along the bottom. The screen says
what each does here, beside the button.
- **Why:** three buttons with no labels of their own. A person looks from the button to the screen
  next to it.
- **Where:** `firmware/quorum_ui_s.py` (`rail`, `draw_tabs`), `board.RAIL_Y`.
- **Varies by board:** on the Feather the buttons are down the left edge and the names are in a
  rail. On console-rp and Mono they are in a row under the screen, and the names go in a footer
  (pull request 113).

### S2. D0 is the way out, and on a review it is Reject

On home D0 is the next tab. On a review it rejects with one press, on any page, and while Sign is
held. Everywhere else it goes back.
- **Why:** AGENTS.md, rule 1: Reject stays one easy press. The same button is always the one that
  gets you out, so it never signs.
- **Where:** `quorum.three`. `test-vectors/console_test.py` `case_three` checks the press on every
  page and during the hold. [MAP.md](MAP.md) shows it: `hold/hash`, D0, `home/queue`.

### S3. D1 moves, and never decides

A press is the next row or page, round from the last to the first. Held 1 s it is the one before.
Held on a review's first page it leaves without rejecting.
- **Why:** one button for moving, so reading a transaction can't sign or reject it.
- **Where:** `quorum.three`, `lcd.Keys` (`D1L`).

### S4. D2 does what the bar says, and Sign is a hold

On home D2 opens what is in focus. On a review it shows the next page not yet seen and says how
many are left. Only when every page has been seen does it say Sign, and Sign is held: 2 s, 3 s when
a page is red. Letting go early signs nothing.
- **Why:** AGENTS.md, rule 1: every page is seen and Sign is held before the key signs.
- **Where:** `quorum.press_sign`, `quorum.hold_tick`.

### S5. Home is four tabs

Queue, Owners, Key, Device. The Device tab is rows: Chip, Wi-Fi, Practice, About.
- **Why:** the reason was not written down when it was built. What the layout gives: every
  top-level place is one press away, on the button level with the tabs, and D1 is left free to move
  inside the tab.
- **Where:** `quorum.TABS`, `quorum.DTAB`, `quorum.tabs_key`.

### S6. A look draws; it does not decide

The structure is `quorum.py`: the state, the buttons, what must be seen. A look is the module that
draws it (`quorum.U`). A look may change any pixel and add an effect as a screen arrives. It keeps
the same pages in the same order, the same thing on each button, red pages red, and the same count
for "see every page".
- **Why:** the look is the fun part and should be free to change. What a signature needs should not
  move when it does.
- **Where:** `quorum_ui_s.pages_of` is the one list of pages, and a look passes it through
  unchanged. `tools/uilab/build.mjs` reads the structure, not the pixels, to name each screen.

## Effects

These are console-rp's, from `firmware/crt.py` and `firmware/quorum_ui_crt.py` in pull request 113.
They are written down here so that a new screen gets one on purpose. They are settled on that
branch and not on `main`.

- **tear:** something arrives or changes. Opening a transaction, a new one on home, a tab, an ask
  from the computer, Refused.
- **strong tear:** a red page's first arrival. After it, the page is red and still.
- **short tear:** a page turn.
- **lock:** worked out here and checked. The verify code, the key's code, Signed.
- **none:** a redraw of what is already there: a poll that changed nothing, a message, a row moving,
  the hold filling.

The rules every effect keeps:
1. **An effect never stands between a person and a button.** Any press stops it at once, the page
   goes out whole, and the press still counts. Reject is still one press.
2. **Nothing moves on a page that asks for a decision.** Once a page has arrived it is still.
3. **No effect while Sign is held.**
4. **A red page stays red.** An effect may bring it in. It may not soften it.
5. **Every effect has a meaning,** and a screen gets the one that fits. A new kind of effect needs a
   new meaning first.

The check for a new screen: [MAP.md](MAP.md)'s "Every transition walked" has an effect column on a
board whose look has effects. Each row is tear, strong, short, lock or none, and each should be the
one above that fits.

## Open

### O1. Should the look be a setting?

Today the look comes with the image. On `main` there is one look with a dark and a light theme,
set in `secrets.py` (`QUORUM_THEME`). On console-rp the CRT look is put on by its image
(`main_rp.py`), and `crt.FX = False` sends every page out whole. The tests and the lab's pictures
run that way, so the plain version of every screen already exists and is drawn on every build.

The choices:
- **a. Leave it with the image.** Nothing to build. Someone who wants a still screen builds another
  image.
- **b. One switch: effects on or off.** A row on the Device tab. The look's colours and footer stay.
  It needs somewhere to keep the choice on a board with no `secrets.py`, and a screen to change it.
- **c. A choice of looks.** Each look is a module in the image. More to test: every look, on every
  screen.

A suggestion, not a decision: **b**. Effects are the part people may want off (motion, or a slow
panel), and the still pages are already tested. Whichever is chosen, it is a firmware change, so a
new release fingerprint.

### O2. Three buttons have no way to Recent

The big screen's status home opens Recent: what this key signed lately. `quorum.three` handles the
`recent` state, but no tab or row leads to it. Found by the lab's build, which refused to pass until
`flows.mjs` said why no flow reaches it. A fifth tab, a Device row, or leave it out?

### O3. A message stays 3 s, over whatever comes next

"See every page first · 1 more" is said when D2 shows the last unseen page. Press D2 again within
3 s and it is still on the screen under "Keep holding". Seen in this lab's first pictures, when the
walk pressed every 0.5 s; the walk now waits 3.5 s between presses, so the committed pictures don't
show it. Should a press clear the last message?

### O4. Which transitions have no effect, and should they?

On console-rp's branch, turning the Chip pages plays nothing, and turning the Key pages plays a
short tear. That is from a trial run of the lab's build on that branch (2026-11-10, not committed).
When its image is on `main`, the whole table is in `MAP.md` to go through.

### O5. Buttons nobody has pressed

[MAP.md](MAP.md), "Not walked yet", lists each state and the buttons no flow presses on it. Most do
nothing there. Each one a flow presses is one more row that is known and not assumed.
