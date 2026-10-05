# emu: the virtual Pico wallet

Real MicroPython (the WebAssembly build of 1.26, the board runs 1.26.1) running the firmware in
`firmware/` unchanged, with the `machine`/`network`/`requests` modules replaced by shims that talk
to the page. The screen is captured from the ST7789 SPI stream, so what you see is the exact
framebuffer. The device is drawn in 3D from the case STLs in `cad/console/zez0000/`.

```
tools/emu                 # start the server, open http://localhost:4242
tools/emu run hello       # reboot + import emu/sketches/hello.py
tools/emu key A           # press a button (A B X Y up down left right press), key right:300 holds
tools/emu shot            # emu/shots/latest.png
tools/emu exec 'mock.goto("send")'
tools/emu log             # console lines
tools/emu chip ready      # the virtual ATECC608: config locked + key in slot 0 (fresh = blank part, show = state)
tools/emu devices         # boards on USB (serial ports, bootloader drives)
tools/emu ship hello      # copy hello.py (+ imports) to the Pico on USB and run it (--port /dev/cu.usbmodemN, --boot: run at power-up too)
tools/emu flash --port /dev/cu.usbmodemN [--wifi]   # MicroPython onto any board (also works on a BOOTSEL drive without --port)
tools/emu headless mock --wait 300 --key right --shot emu/shots/x.png    # no browser
```

Page: the device menu lists every board on USB; for one that is not running MicroPython the
send button becomes ⚡ install MicroPython. The module menu top left picks what ▶ run, ↻ reset and
⇪ send to Pico act on (only modules
that show something are listed: they start themselves at import, or the server knows their entry
point, `ENTRY` in `core/workspace.mjs`). Left = files, editor (Cmd/Ctrl+Enter runs the open file),
console with a REPL; right = the device (orbit with the mouse, click the caps) or the flat view.
Keyboard: W A S D and space for the joystick, numpad 9 6 3 . for A B X Y (top-row 9 6 3 . work
too), after clicking the device. The 3D view labels each button with its key.

The flash also gets a `build.py` like the one `tools/fw build` writes for a Pico (`IMAGE = "emu"`, the
manifest's version, the commit, and `RELEASE`, the release fingerprint of the console files as
served here). The toolbar shows the fingerprint's blockie, the same picture as on a Pico's Device screen running
the same files. `--file build.py=PATH` in headless replaces it.

The flash is `firmware/*.py` and `*.bin` (never `secrets.py`; a stub is generated with
`APP_URL = "/app"`, which the server proxies to the wallet app, `--app http://host:port`,
default `http://localhost:3001`) plus `emu/sketches/*` on top. Saving in the editor writes to disk.

## On GitHub Pages

`node emu/build.mjs` (after `npm ci` here) writes `docs/emu/`, the same page as a static site:
[jmcpheron.github.io/pico-quorum/emu/](https://jmcpheron.github.io/pico-quorum/emu/). Commit it, as with
`docs/app/`. CI rebuilds it and fails if the committed copy differs.

- **Boot data:** `boot.json`, written at build time. It is what `/ctl/boot` answers here, for
  `firmware/` alone, plus a `build.py` with `IMAGE "web"` and the console's release fingerprint.
- **COOP/COEP:** `coi.js` and `sw.js`. Pages can't send headers, so a service worker adds them to the
  folder's own files. The first visit reloads once.
- **Kept in the visitor's browser** (localStorage):
  - the chip state;
  - a **random software key** (`key.bin`), never the fixed test key the local emulator uses;
  - edited files.
- **The release fingerprint is computed again in the page** over the files it boots. An edited
  console file shows another blockie, marked *edited*. The firmware's own `image.RELEASE` agrees.
- **The console runs on the Safes saved in the app** (same origin), with the app's Safe API key
  and no `APP_URL`, so it asks Safe's own service for each chain. With none saved, the module is
  `mock`.
- **No USB, no control channel.** `tools/emu` stays the local path.

**Your passkey as the key** (both hosts). The toolbar's **key** menu picks the virtual chip or **your
passkey**, and **make a passkey** creates one with WebAuthn for this site: Touch ID, Windows Hello, a
phone or a security key, P-256 (ES256).
- **What the console gets:** the public key, kept in the browser. The console computes its owner
  address from it, as for a chip.
- **When it signs:** `shims/passkey.py` asks the page, through a shared buffer while Python waits,
  for a WebAuthn assertion over the safeTxHash computed on screen. `quorum.sign_it` packs it exactly
  as a chip's.
- **Before handing it over,** the page checks the assertion's shape, the UV flag, and the signature
  against the key.
- **The first time,** a note says the authenticator won't show the transaction.

`tools/vectors/passkey.mjs` showed a real browser's assertion passes Safe's passkey signer on Base
Sepolia, Base and Ethereum. `test-vectors/passkey.json` pins the firmware's packing of it. Headless:
`--passkey` signs with a software passkey (`core/softpasskey.mjs`).

**The console page** ([…/pico-quorum/console/](https://jmcpheron.github.io/pico-quorum/console/),
`emu/console/`, written to `docs/console/` by the same build): the console alone, its screen with the
joystick and A B X Y as on the board, for anyone without a Pico. No editor, no 3D case, no module
menu; it always runs the quorum console with your passkey as the key, and the files exactly as built.
- **First visit:** it asks you to **make a passkey**, then to save a Safe in the app.
- **It runs `docs/emu/`'s** `boot.json`, worker and MicroPython (`web/browser.mjs` is shared by both
  pages), and shows the same release blockie.
- **Its own** `coi.js`, `sw.js`, CSP (no inline script or style) and `BUILD.json`. It also has a
  one-line `worker.js` importing the emulator's: a worker's own script goes through the service
  worker whose scope holds its URL, so it must sit under `/console/` to be isolated.

The front page and the app link to the console page; it links to the emulator for developers.

`node emu/e2e-static.mjs` serves `docs/` like Pages and checks all of that in Chromium, both pages.

## Give it to your AI

`emu/SKILL.md` is the skill file. It tells an AI what the screen and buttons are, how to write a
sketch, how to run it here (`tools/emu run`, `key`, `shot`), and how to put it on the real Pico.
Hand it over with a checkout of this repo (the skill runs `tools/emu`, which needs node). In
Claude Code it loads on its own from `.claude/skills/pico-emu`; say "build Tetris for the Pico
wallet" or `/pico-emu`. The page links to it too (top right, "skill file for your AI", also at
http://localhost:4242/skill).

What is modeled: pins (keys pull low when pressed), SPI display window commands, the SPI transfer
time (24 MHz cap until `machine.freq(cpu, peri)` raises the peripheral clock, like rp2), PWM
backlight, `Pin("LED")` (the base glows), `Timer` periodic/one-shot, `Pin.irq`, `machine.reset()`,
a 448 KB heap, and a virtual ATECC608 on I2C at 0x60 (`core/shims/atecc_sim.py`: the packet
protocol, config zone and its locks, the slot table, GenKey, Nonce + Sign, Random, Info; state in
`emu/chip.json`, blank part until provisioned). Not modeled: the chip's OTP/data reads, MAC and
encrypted transfers, sockets, PIO, native/viper code generation (runs as bytecode), real timing of
Python itself (wasm is much faster than the RP2350).

Needs node 18+ and `npm install` in `emu/` (done by `tools/emu` on first run). No build step.
