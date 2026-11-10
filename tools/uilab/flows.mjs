// The UI lab's flows: what a person does on the three-button console, one press at a time.
// tools/uilab/build.mjs presses them on the emulator (walk.py) and writes the map and the explorer.
//
// A flow: { id, title, about, setup, steps }.
//   setup   Python run in walk.py before the first frame: the queue served, or a state put on.
//   steps   [what, note]. what is "D0" "D1" "D1L" (D1 held 1 s) "D2", "hold D2" (pressed, kept
//           down), "wait 1200" (ms pass, the key stays down) or "release". note says what to look at.
//
// Add a flow when a feature adds a screen or a button changes what it does. The build fails when the
// firmware can draw a screen no flow reaches (NOT_WALKED below is where a reason goes instead).

/** The boards walked. console-rp (Mono runs its image) joins when its image is on main. */
export const BOARDS = [
  { id: "feather-s3", name: "Feather ESP32-S3 Reverse TFT", about: "240 × 135, three buttons down the left edge, a rail naming each" },
];

/** A screen quorum_ui_s.draw can draw, or a button on one, that no flow walks, and why. */
export const NOT_WALKED = {
  screens: {
    owners: "the knob boards' Owners screen: on three buttons Owners is a tab on home",
    recent: "what this key signed lately, opened from the big screens' status home: three buttons have no way to it",
    working: "Signing and Sending: drawn inside a signature, between two ticks. They are the frames on the way to result/signed",
  },
  rows: {
    "Device tab, Wi-Fi": "restarts into Wi-Fi setup (wifisetup.py), another program with screens of its own",
    "Device tab, Practice": "opens the practice ceremony (practice.py), which reads the buttons itself",
    "an ask, accepted": "D2 held on an ask writes what was asked and restarts the console",
    "crashed, D2 held 3 s": "restarts the console",
  },
};

const HOME = `home(queue("three"))`;

export const FLOWS = [
  {
    id: "tabs", title: "Home: the four tabs", setup: HOME,
    about: "D0 is level with the tabs along the top and moves to the next one, round.",
    steps: [
      ["D0", "Owners: who can approve."],
      ["D0", "Key: this key's fingerprint and picture."],
      ["D0", "Device: one row each for Chip, Wi-Fi, Practice and About."],
      ["D0", "Round to Queue."],
    ],
  },
  {
    id: "queue", title: "Home: down the queue", setup: HOME,
    about: "D1 is level with the list. A press moves down and round; held 1 s it moves up.",
    steps: [
      ["D1", "The unknown call, in red."],
      ["D1", "The refused one."],
      ["D1", "Round to the first."],
      ["D1L", "D1 held: up, round to the last."],
    ],
  },
  {
    id: "approve", title: "Approve a send", setup: HOME,
    about: "D2 does what the bar along the bottom says. On a review it shows each page not yet seen, then signs when held 2 s.",
    steps: [
      ["D2", "Open #0. The rail: Reject, Next, and See, with how many pages are left."],
      ["D2", "The amount."],
      ["D2", "Who it goes to, in full, with its blockie."],
      ["D2", "Who has approved."],
      ["D2", "The verify code, worked out here."],
      ["D2", "The whole hash. Every page seen: D2 says Sign."],
      ["hold D2", "Held: the rail starts to fill."],
      ["wait 700", "0.7 s."],
      ["wait 700", "1.4 s. Let go now and nothing is signed."],
      ["wait 600", "2 s: Signing, Sending, then Signed."],
      ["release", "D2 says OK."],
      ["D2", "Home again."],
    ],
  },
  {
    id: "read", title: "Read a review with D1", setup: HOME,
    about: "D1 turns the pages, round from the last to the first. Held, it goes back; held on the first page it leaves without rejecting.",
    steps: [
      ["D2", "Open #0."],
      ["D1", "Next page."],
      ["D1", "Next."],
      ["D1L", "D1 held: back one."],
      ["D1L", "Back to the first page."],
      ["D1L", "Held on the first page: out, not rejected."],
    ],
  },
  {
    id: "reject", title: "Reject", setup: HOME,
    about: "D0 rejects with one press, on any page.",
    steps: [
      ["D2", "Open #0."],
      ["D1", "Any page."],
      ["D0", "Rejected on this console. Home says so."],
    ],
  },
  {
    id: "let-go", title: "Let go early", setup: `home(queue("send"))`,
    about: "A hold that stops short signs nothing.",
    steps: [
      ["D2", "Open."], ["D2", ""], ["D2", ""], ["D2", ""], ["D2", ""], ["D2", "Every page seen."],
      ["hold D2", "Pressed."],
      ["release", "A short press is a hold that ended at once: not signed."],
      ["hold D2", "Held again."],
      ["wait 700", "0.7 s."],
      ["wait 700", "1.4 s."],
      ["release", "Let go: not signed, and the page says so."],
    ],
  },
  {
    id: "reject-held", title: "Reject while Sign is held", setup: `home(queue("send"))`,
    about: "D0 still rejects during the hold.",
    steps: [
      ["D2", "Open."], ["D2", ""], ["D2", ""], ["D2", ""], ["D2", ""], ["D2", "Every page seen."],
      ["hold D2", "Held."],
      ["wait 700", "0.7 s."],
      ["D0", "D0 with D2 still down: rejected, nothing signed."],
      ["release", "Letting go of D2 now does nothing."],
    ],
  },
  {
    id: "red", title: "A red transaction", setup: `home(queue("owner"))`,
    about: "Swapping an owner is red on every page, and Sign takes 3 s.",
    steps: [
      ["D2", "Open: red."],
      ["D2", "The call."],
      ["D2", "The owner going out."],
      ["D2", "The owner coming in."],
      ["D2", "Who has approved."],
      ["D2", "The verify code."],
      ["D2", "The hash. Every page seen."],
      ["hold D2", "Held: the rail fills in red."],
      ["wait 1200", "1.2 s."],
      ["wait 1200", "2.4 s: a plain send would be signed by now."],
      ["wait 600", "3 s: signed."],
      ["release", ""],
      ["D2", "Home."],
    ],
  },
  {
    id: "refused", title: "A refused transaction", setup: HOME,
    about: "The service's hash is not the one the fields give. The console won't sign it, whatever is pressed.",
    steps: [
      ["D1", ""], ["D1", "The refused one."],
      ["D2", "Open: Refused, and why."],
      ["D2", "Sign says why it can't."],
      ["D1", "What the service claims."],
      ["D0", "Reject is still one press."],
    ],
  },
  {
    id: "owners", title: "Look at an owner", setup: HOME,
    about: "The Owners tab lists who can approve. D2 shows the one in focus in full.",
    steps: [
      ["D0", "Owners."],
      ["D1", "The next owner."],
      ["D2", "In full, with its blockie."],
      ["D1", "Nothing: one page."],
      ["D0", "Back to the tab."],
    ],
  },
  {
    id: "key", title: "This key's code", setup: HOME,
    about: "The Key tab's code is the app's set-up link as a QR code.",
    steps: [
      ["D0", ""], ["D0", "Key."],
      ["D2", "The code."],
      ["D1", "The owner address in full."],
      ["D1", "The code again."],
      ["D0", "Back to the tab."],
    ],
  },
  {
    id: "device", title: "Device: the chip, and About", setup: HOME,
    about: "The Device tab's rows. D1 moves down them, D2 opens the one in focus.",
    steps: [
      ["D0", ""], ["D0", ""], ["D0", "Device."],
      ["D2", "Chip: its own pages."],
      ["D1", "Next page."],
      ["D1L", "D1 held: back."],
      ["D0", "Back to the tab."],
      ["D1", "Wi-Fi."], ["D1", "Practice."], ["D1", "About."],
      ["D2", "The device's facts."],
      ["D0", "Back to the tab."],
      ["D1", "Round to Chip."],
    ],
  },
  {
    id: "not-sent", title: "Signed, but not sent", setup: `home(queue("send")); fail_posts(True)`,
    about: "The service doesn't answer. The signature is kept, and D2 sends it again.",
    steps: [
      ["D2", "Open."], ["D2", ""], ["D2", ""], ["D2", ""], ["D2", ""], ["D2", "Every page seen."],
      ["hold D2", "Held."],
      ["wait 2000", "Signed, and the service did not take it."],
      ["release", ""],
      ["D2", "Send again: still down."],
      ["D0", "Back. The signature is kept for later."],
    ],
    after: `fail_posts(False)`,
  },
  {
    id: "ask", title: "The computer asks", setup: `home(queue("three")); ask_safes()`,
    about: "An ask over the USB link is shown page by page. D0 refuses with one press.",
    steps: [
      ["wait 100", "The ask comes up over home."],
      ["D1", "Its next page."],
      ["D2", "See every page first."],
      ["D0", "Refused: nothing saved."],
    ],
  },
  {
    id: "no-chip", title: "No chip", setup: `home(queue("three")); Q.state = "nochip"`,
    about: "No key on the bus. D2 looks again.",
    steps: [["D2", "The chip is there: home."]],
  },
  {
    id: "pin", title: "A chip that isn't pinned", setup: `home(queue("three")); Q.state, Q.pin_why = "pinfail", "this chip is not one of the 1 pinned"`,
    about: "Nothing is signed with a chip the console was not told to expect. D2 checks again.",
    steps: [["D2", "The chip matches its pin: home."]],
  },
  {
    id: "set-up", title: "No Safe yet", setup: `home(); Q.state = "unconfigured"`,
    about: "A console being set up: the key is ready, and D2 shows its code.",
    steps: [
      ["D2", "The key's code."],
      ["D0", "Back."],
    ],
    after: `Q.state = "home"`,
  },
  {
    id: "crashed", title: "Crashed", setup: `home(); Q.state = "crashed"`,
    about: "After too many failures in a row the console stops somewhere plain that signs nothing.",
    steps: [["D0", "Nothing. Only D2, held 3 s, restarts."]],
    after: `Q.state = "home"`,
  },
];
