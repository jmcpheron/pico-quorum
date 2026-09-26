# picowallet build log

## 2026-09-05 — parts on the bench

Three parts, all from Amazon. Pico plugs face-down into the LCD board's female header. The ATECC608 breakout fits in the ~11 mm gap between them.

![stack end-on, ATECC wedged inside](images/2026-09-05-01-stack-end-atecc-inside.jpg)
![Pico-LCD-1.3 top: joystick, screen, A/B/X/Y](images/2026-09-05-04-pico-lcd-1.3-top.jpg)
![Pico 2 W](images/2026-09-05-05-pico-2-w.jpg)

Decisions today:
- Screen and buttons work out of the box through the header. Only the ATECC and the battery need wires.
- ATECC gets 4 soldered wires to the Pico (3V3, GND, GP4 SDA, GP5 SCL). The LCD board eats every pin, no pass-through, so no jumper trick.
- Battery: solder it too, keep it in the gap.
- WiFi/Bluetooth stay on for v1. Idea: send a tx to the device over the radio, it shows it on screen, you approve, it sends the signature back.

## 2026-09-05 — first boot

Pico 2 W plugged into the omen box (Arch laptop, `ssh austin@omen.local`). Blank Pico shows up as a USB drive `RP2350`, no LED, no other sign of life. That's normal.

- Flashed MicroPython v1.26.1 (`RPI_PICO2_W-20250911-v1.26.1.uf2`) by copying it onto the `RP2350` drive.
- Board reboots as `/dev/ttyACM0`. `mpremote` installed on omen via pipx. Added `austin` to `uucp` group for serial access.
- `firmware/main.py` blinks the onboard LED. First light.

Workflow from the Mac: `scp` a file to omen, then `mpremote connect /dev/ttyACM0 cp file :file` and `mpremote reset`.

## 2026-09-05 — WiFi console

Going through omen's USB was a detour. The Pico 2 W has WiFi, so now it joins the house network on boot and listens for a console on TCP 2323. From the Mac:

```
./tools/pico ls
./tools/pico exec 'print(1)'
./tools/pico cp firmware/main.py :main.py
```

That is `mpremote connect socket://picowallet.local:2323 resume ...`. mDNS name `picowallet.local` works from the Mac. `firmware/secrets.py` (gitignored) holds the WiFi creds, template in `secrets.example.py`.

No SSH: MicroPython has no SSH server. The console has no password either, anyone on the LAN can run code on it. Fine for dev, not for the shipped firmware. LED: fast blink while joining WiFi, solid with a short blink every 2 s once up.

Gotcha: mpremote soft-resets the board before the first command, which reruns main.py and kills the socket. Always pass `resume` (the wrapper does).

## 2026-09-05 — screen and buttons

Pico stacked onto the Pico-LCD-1.3. `firmware/lcd.py` is a small ST7789 driver (SPI1 at 62.5 MHz, framebuf RGB565, PWM backlight) plus a `Keys` class for A/B/X/Y and the joystick. `firmware/ui.py` draws a title, the IP, and the last key pressed. Screen and all buttons confirmed working.

Lesson, cost an hour: on the rp2 port the network console (`os.dupterm` on a socket) is only read while the REPL is idle. A blocking `while True` in main.py makes the board deaf over WiFi, and Ctrl-C from the socket never lands. Fix: the UI runs from `machine.Timer(period=30ms)` and main.py returns to the REPL. The timer callback is scheduled (soft), so framebuf and SPI work inside it. Keep the callback quiet: prints from it would corrupt mpremote's raw REPL.

`boot.py` starts WiFi + console before main.py, so a broken main.py can still be fixed remotely.

`tools/push` copies all of `firmware/` and reboots via a one-shot Timer (so mpremote returns before the socket drops). macOS has no `timeout` command, that bit me too.

USB rescue path: the Pico's USB goes to the omen laptop. Device path there is `/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_*-if00` (the ttyACM number changes on each reboot).

## 2026-09-05 — the chip is on the wallet, no solder

The Adafruit ATECC608 from the Pi (serial `01235e6763cc8d97ee`, the key that owns the mainnet vault)
moved onto the Pico with zero solder: a STEMMA QT cable into the breakout, the four wires pushed into
the LCD board's female header beside the Pico pins (GP4 SDA blue, GP5 SCL yellow, 3V3 red, GND black),
breakout tucked in the gap. `i2c.scan()` finds `0x60`, the chip signs in 151 ms.

Firmware now: `atecc.py` driver, `signer.py` (chip if present, else software key), `wallet.py` loop
(announce, poll, show, sign on A), and the digest is rebuilt on the device from the displayed fields
before anything is shown. The home screen shows the vault's dollar balance and pairing state.
Local test stack: fork of the ATECC608-demo app on port 3001 against anvil.

![the stack with the four wires and the ATECC breakout](images/2026-09-05-06-atecc-stack-wired.jpg)
![ATECC608 breakout in the gap](images/2026-09-05-07-atecc-in-the-gap.jpg)
![home screen: $1000.00 USDS paired](images/2026-09-05-08-home-screen-1000-usds.jpg)
![home screen, atecc608 in the corner](images/2026-09-05-09-home-screen-paired.jpg)

## 2026-09-05 — first signed transfer from the wallet

Whole loop, end to end, on the local chain: `POST /api/requests` for 5 USDS to atg.eth, the wallet
rebuilt the EIP-712 digest from the fields and it matched, showed "SIGN? $5 USDS to atg.eth,
A = sign B = reject", Austin pressed A, the ATECC608 signed in 150 ms, the app's relay called
`executeTransfer`, confirmed in tx `0xc7c6f72a…`. Vault 1000 → 995 USDS, nonce 0 → 1. Screen:
"SENT $5 to atg.eth". Same chip, same key that owns the mainnet vault.

Bug of the day: two soft Timers plus a blocking HTTP call fill the rp2 scheduler queue (8 deep) and
the WiFi console's accept callback gets dropped, which shows up as "connection reset by peer" forever.
One 50 ms timer now, and it stops itself during sign + relay.

## 2026-09-05 — first mainnet transfer from the wallet

5 USDS to atg.eth, signed on the ATECC608 wedged into the Pico, relayed by the app on port 3001.
Tx [`0x0fbd390b…`](https://etherscan.io/tx/0x0fbd390b3e82bc4566f9ef9c66c178e58904debaf728ec9d941b4090610c6257),
81,715 gas. Vault 124.56 → 119.56 USDS, nonce 6 → 7. Screen: green SIGN bar, press A, "SENT",
then the home screen flashed "-$5.00".

Bumps on the way, all fixed:
- Two copies of the site were running (yesterday's on :3000, the fork on :3001). A Send on :3000
  never reaches the wallet. Use :3001.
- The app had no reject path, so a Y press left the request pending and reserved its amount; the
  next proposal failed the balance check. Added `POST /api/requests/[id]/reject`.
- Mainnet latency wedged the WiFi console (scheduler queue). Timer now pauses around HTTP, the
  console drains accepts from the tick, the app caches chain reads for 5 s.
- Two signed attempts failed on "insufficient funds" while the relay held 0.000008 ETH. It needs
  about 0.000012 ETH per send at tonight's gas. Funded with 0.001 ETH.

Home screen now: balance big, small QR of the vault, chain label, pairing dot, warning line.
Confirm screen: green SIGN bar in line with A, red REJECT bar in line with Y, details on down.

![the wallet in its case](images/2026-09-05-18-hero-case-on-black.jpg)
![case, portrait](images/2026-09-05-19-case-portrait.jpg)
![SIGN? $69 to atg.eth in front of the site](images/2026-09-05-20-sign-screen-69-usds.jpg)

## 2026-09-05 — provisioning from the wallet, and the repo goes public-ready

`atecc.py` grew `write_config`, `lock_config` and `genkey_new`, so a fresh chip can be locked
and given a key from the app's Setup page without a Pi. Both are gated by `ALLOW_LOCK` /
`ALLOW_GENKEY` in `secrets.py` on the device, default off; with them off the wallet refuses the
commands (checked on the real chip). The lock and new-key paths have NOT yet run on a fresh chip;
the config bytes and command sequence are the ones the Pi signer used successfully on 2026-09-04.

Photos: feet cropped or dropped, files renamed by content, five good shots added. README rewritten
as the build guide: order, print, assemble, flash, set up the chip, run, change it.

Then 69 USDS to atg.eth, same way: [`0x87638ae1…`](https://etherscan.io/tx/0x87638ae169eccb9f002d4eb6ce8b60e7d6603e4d3d4e562164ea10e9023f9313). That is the one in the tweet.

![the details page, joystick down on the sign screen](images/2026-09-05-23-details-screen.jpg)
![v0 case on the printer](images/2026-09-05-24-case-on-the-printer.jpg)

## 2026-09-17 — the KEYS screen, a virtual chip, and a bug in the config table

No hardware in this session, all of it on the emulator, on branch
`claude/pico-wallet-signing-keys-uyr7mc` of the jmcpheron fork.

The wallet now knows the ATECC608 has 16 slots, not just slot 0. X on the home screen opens a
KEYS screen: the slot table as the config zone types it (P256 / PUB / AES / DATA), which slot
signs, NEW KEY in a slot, SHOW PUBLIC KEY, and the three permanent locks (config zone, data zone,
one slot) each behind a red hold-A screen and the `ALLOW_*` flags. `signer.py` has one shape for
the chip and the software key, active slot in `slot.txt`.

To test it without a chip, the emulator grew a virtual ATECC608 on I2C at 0x60 that speaks the
real packet protocol (wake token, `0x03` command packets, CRC-16), so `atecc.py` runs against it
unchanged. It starts as a blank part. `tools/emu chip fresh|ready|show`. Config lock, GenKey in
slots 0/2/7, a signature that verifies, slot lock and data-zone lock all walked through with
screenshots.

Bug of the day, and a bad one: `atecc.py`'s `CONFIG` was not the table the Pi wrote to chip #1.
It was the ATECC508 test table with an extra row of `0xFF` at bytes 96-111 and the last row
dropped. Those bytes are KeyConfig for slots 0-7, so every one of them decoded to "not an ECC
key". Locking a fresh chip with it (README step 5, the Setup page button) would have made slot 0
unable to ever hold a P-256 key, permanently. It never bit anyone because the lock path has never
run on a fresh chip. Fixed by copying the Pi's bytes; with the real table only slots 0, 2 and 7
are P-256 private keys, not 0-7 as the old handoff said. Notes for upstream in `docs/UPSTREAM.md`.

Also on the branch: `hardware/wiring/SOLDERING.md` with the perfboard wiring (chip on GP4/GP5/GND 8/3V3 36, an
18650 behind a switch and a Schottky into VSYS, 100k/100k divider to GP28 for a gauge),
`power.py` for the gauge, a read-only `chipcheck.py` report, `tools/usb` for deploying over USB
serial, and `docs/TESTPLAN.md` for the next session.

Lesson from the emulator: a top-level `raise SystemExit` in a module you `import` at the
MicroPython REPL soft-reboots the board. `chipcheck.py` runs inside a function now.

## 2026-09-16 — a fresh chip, read only

The perfboard build's first session with the chip: an Adafruit ATECC608 breakout (4314) on the
Pico's pin tails per `hardware/wiring/SOLDERING.md` (VIN 36, GND 8, SDA 6, SCL 7), the 18650 holder, switch,
Schottky and divider wired as well, no cell in the holder, USB only. Firmware: branch
`claude/pico-wallet-signing-keys-uyr7mc` with upstream `main` (`87c717c`) merged in first,
MicroPython v1.26.1 (2025-09-11), deployed with `tools/usb push` from the Mac on
`/dev/cu.usbmodem112301`.

Rule for today: `ALLOW_LOCK = False`, `ALLOW_GENKEY = False`. Nothing written to the chip.

**Before the flash.** Upstream had moved 21 commits past the branch point. The one that mattered
here is `261b373`: a reset straight after a copy lost writes on LittleFS (atecc.py landed at 3584
of 7021 bytes). `tools/usb push` did exactly that sequence, so it now soft-resets first, chains
every copy, calls `os.sync()`, and only then resets. The merge also brought the NO CHIP screen,
the secrets-less boot and demo/vid. Rehearsed on the emulator (blank virtual chip: home, KEYS,
chip page, chipcheck; provisioned: slot 0 ACTIVE), then a read-only I2C scan on the board before
copying anything: `['0x60']`, first try.

**First power, USB only.** The board was already up on the mock screens; after the push it came
back on the wallet's home screen: `X keys`, red dot, `no key`, WiFi joined (secrets.py with real
credentials, console off, app URL a placeholder so the log says `net: OSError(-2,)`). No
`error.log`. Every `.py` on the board matched its local size (`os.stat`). The serial port took
over 10 s to come back after the hard reset.

**What an untouched chip reports.** `tools/usb exec 'import wallet; wallet.stop()'` then
`tools/usb run firmware/chipcheck.py`, three times over the session (twice before the KEYS walk,
once after). The whole output, verbatim:

```
== picowallet chipcheck ==
i2c scan: ['0x60']
using address: 0x60
wake: ok (3 ms)
serial:   0123f3acfd2a826bee
revision: 00006002 (ATECC608A)
i2c address byte 16: 0xc0 (7-bit 0x60)
config zone: unlocked   data zone: unlocked   (byte 87 = 0x55, byte 86 = 0x55; 0x55 = unlocked, 0x00 = locked)
slot locked bytes 88-89: ff ff
raw config zone (128 bytes, 16 per row):
    0: 01 23 f3 ac 00 00 60 02 fd 2a 82 6b ee c1 55 00
   16: c0 00 00 00 83 20 87 20 8f 20 c4 8f 8f 8f 8f 8f
   32: 9f 8f af 8f 00 00 00 00 00 00 00 00 00 00 00 00
   48: 00 00 af 8f ff ff ff ff 00 00 00 00 ff ff ff ff
   64: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
   80: 00 00 00 00 00 00 55 55 ff ff 00 00 00 00 00 00
   96: 33 00 33 00 33 00 1c 00 1c 00 1c 00 1c 00 1c 00
  112: 3c 00 3c 00 3c 00 3c 00 3c 00 3c 00 3c 00 1c 00
matches the reference table (bytes 16-83, 88-127): no
slot table as the chip has it:
  slot kind  ext-sign genkey privwrite pubinfo lockable locked  key
     0 P256  True     True   False     True    True     False   -
     1 P256  True     True   False     True    True     False   -
     2 P256  True     True   False     True    True     False   -
     3 DATA  False    False  False     False   False    False   -
     4 DATA  False    False  False     False   False    False   -
     5 DATA  False    False  False     False   False    False   -
     6 DATA  False    False  False     False   False    False   -
     7 DATA  False    False  False     False   False    False   -
     8 DATA  False    False  False     False   True     False   -
     9 DATA  False    False  False     False   True     False   -
    10 DATA  False    False  False     False   True     False   -
    11 DATA  False    False  False     False   True     False   -
    12 DATA  False    False  False     False   True     False   -
    13 DATA  False    False  False     False   True     False   -
    14 DATA  False    False  False     False   True     False   -
    15 DATA  False    False  False     False   False    False   -
random (32 bytes): ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000
NOTE: config zone is unlocked. GenKey and Sign will refuse (status 0x0f) until it is locked; that is normal.
== end ==
```

Read off it:
- I2C scan found `['0x60']`, nothing else.
- Serial `0123f3acfd2a826bee`, revision `00006002` = 608A, address byte 16 `0xc0`.
- Config zone unlocked (byte 87 = 0x55), data zone unlocked (byte 86 = 0x55), SlotLocked `ff ff`.
- The factory slot table is not blank: SlotConfig `2083 2087 208f` and KeyConfig `0033` for slots
  0, 1, 2, so Microchip ships them as P-256 private keys, external sign, GenKey allowed; slots 3
  to 15 data, 8 to 14 lockable. `matches the reference table: no`, as expected.
- Random did NOT change between runs: `ffff0000` repeated. Datasheet behaviour before the config
  lock (a fixed test pattern). The test plan expected it to differ; corrected.
- Second and third runs: serial, config and random byte-identical (only the wake time moved, 3 to
  4 ms).

This is the "as shipped" state.

**The KEYS screen on the real chip.** X: header `KEYS atecc608 cfg OPEN`, rows 0 to 2 `P256`, the
rest `DATA` (the emulator's blank part shows `-` everywhere; its fresh table should be these
factory bytes). X again: the chip page, `i2c 0x60`, the serial, `rev 00006002 608A`, `permanent
actions off`, `config zone OPEN`. Cursor on `WRITE + LOCK CONFIG (off)`, A: the red ERROR naming
ALLOW_LOCK, nothing changed. RAW CONFIG ZONE agreed with the dump, row 80 ended `55 55`. RANDOM
twice: `ffff0000...` both times, as above. Slot 0: `P256` with the `(off)` item. Chipcheck after
the walk: byte 87 still `0x55`.

**Timings.** Wake 3 to 4 ms; the whole chipcheck (config read, slot decode, random) well under a
second. Nothing flaky over the session.

**Battery** (wired, cell out, switch off): `power.status()` said `usb: True` via `WL_GPIO2`, and
`vbat: 1.08` where 0 was expected. With the switch off the divider's top is open, so the volt at
GP28 is most likely the Schottky's reverse leakage from VSYS through the divider. The home screen
showed an empty bar and `1.1V` instead of `usb`. Fixed in `power.py`: anything under 2.5 V counts
as no cell (a protected 18650 cuts off near 2.5 V, and the Pico's regulator quits before that).

Decisions today:
- Locking waits. The app side (vault deployment, recovery address) is not planned yet, and the key
  made at lock time is the one the next vault gets.
- The perfboard layout stays; the chip answered first try.

Gotchas:
- A hard reset drops the USB port for over 10 s; anything scripted must wait for
  `/dev/cu.usbmodem*` before the next mpremote call.
- Random before the lock is a fixed pattern, and the factory table already types slots 0 to 2 as
  P-256: two things the emulator's chip model does not do. Both in `docs/UPSTREAM.md` for `atecc_sim.py`.

Not done today, on purpose: config lock, GenKey, data-zone lock, slot lock. The chip leaves this
session exactly as it arrived. Not done for lack of a cell: TESTPLAN phase 5. Next: the battery
phase when a cell is here; `docs/TESTPLAN.md` phase 6 when the vault deployment is planned.

## 2026-09-17 — the map, the ceremony, and the chip is sealed

The chip UI grew a look: the map is the die itself, drawn as a floor plan with the CONFIG strip,
the 4x4 field of slots coloured by kind, OTP, COUNTERS and the LAB docked below; DATA is a grid
of tiles; menus carry class badges; headers are tinted by zone; 25 sixteen-pixel icons, a palette
in `theme.py`; the boot screen got a navy gradient and a rainbow leg chase. Icons are packed from
ASCII art at import (the first draw of a screen paid 8 ms per icon before that). On the panel a
`show()` is 46 ms and the busiest screen draws in about 70 ms. Two new actions: SIGN TEST on a key
slot (sign, verify on the Pico, read counter 0) and WRITE A NOTE on a clear data slot. Two guards
before the lock: `CONFIG` is checked at import for a P-256 slot 0, and `lock_config()` reads the
zone back and refuses unless the table matches and slot 0 decodes right. `docs/CHIPMAP.md` has it all.

Then the finale on the one chip, flags flipped in `secrets.py` and pushed. Jason at the device,
me reading the chip from the laptop between steps:

- WRITE WALLET CONFIG (the chip had been restored to its original bytes earlier): 49 bytes
  changed, read back identical, config still open. chipcheck: `matches the reference table: yes`.
- Hold B+Y, `! LOCK CONFIG FOREVER`, hold A three seconds: the CONFIG strip pulsed, a flash, the
  padlock closed, RULES SEALED ("the cool sealed animation"). chipcheck: byte 87 = `0x00`, slots
  0/2/7 `P256 empty`. Random live: two different 32-byte values. SelfTest all pass.
- OTP from the map: NOT ALLOWED, status 0x0F. Not a bug on our side of the wire: with the config
  zone locked and the data zone still open the chip accepts clear writes into slots and OTP but
  reads nothing back until the data zone is locked too. Every Data and OTP read refused, clear and
  secret slots alike. Neither the firmware nor the emulator knew; both do now (write-only state on
  the map, the reason on the refusal screen, the note reports "read back after data lock").
- NEW KEY in slot 0: KEY CREATED, `a427c739`. Then Jason unplugged USB, ran the wallet on the
  18650 and made another key on battery; back on USB, rebooted, a third: `cc01b14a`. Counters 0
  and 0 throughout, which is right: GenKey does not spend a count, signing does.
- The control experiment for upstream: GenKey on slot 3 (KeyType 7 but GenKey allowed by its
  SlotConfig, the shape of every slot 0-7 in upstream's table) refused with 0x0F; slot 0 untouched.
- One rewrite while it happened: the red screen now leads with what is LOST (the key being
  replaced and its fingerprint, in red; "nothing, the slot is empty" otherwise; for the locks, the
  abilities that go away).

Decisions today:
- Slot 0 stays replaceable; LOCK SLOT waits for a vault deployed with it.
- The data zone stays open; the note in slot 12 and the OTP wait for that decision.
- Slot 7 is where a brought key would go (PrivWrite, encrypted against the write-only secret in
  slot 4); a seed phrase via SLIP-10 nist256p1 is the idea. Not built.
- The upstream issue has its silicon evidence now (docs/UPSTREAM.md section 1 and the draft at the end).

Gotchas:
- My checkpoint script ended with a reset and rebooted the wallet under Jason's hands. Pause the
  timer (`wallet.stop()`), read, `wallet.start_timer()`: the screen stays where it was.
- The plan said slot 8 was 416 bytes of clear data. Under the wallet config it is secret (write
  never, read never in clear); the clear ones are 12 and 13.
- Reads of Data and OTP need the data lock, not just the config lock.

Later the same evening: the red screen's doomed key went cyan at double size, the one thing on
that screen that is not red ("this is the unique thing that's going to be deleted"). Jason made
a fourth key with it (`9fad2e82`), then SIGN TEST twice: SIGNATURE VERIFIED both times and counter 0
went 1, 2, on the screen and from the laptop. `docs/UPSTREAM-ISSUE.md` is the short version for Austin.

Not done today, on purpose: LOCK SLOT 0, LOCK DATA ZONE, PrivWrite, the note in slot 12, slot 2.
Flags back to False and pushed.

## 2026-09-24 — the Safe console on the Pico: the chip approves its first Safe transactions

The PicoQuorum console (branch `quorum-ui`) ran on the real board for the first time. Its code is
`firmware/quorum.py`, `quorum_ui.py`, `decode.py` and `txservice.py`, with the new
anti-aliased fonts. On the other end was `tools/quorum`, a simulated 2-of-3 Safe on the Mac:
Family Safe, chain 31337, at `192.168.4.25:8787`, with Alice and Bob as simulated co-signers.
Screens and flows are in `docs/quorum-ui/README.md`.

**The board as found:**
- MicroPython 1.26.1 (`RPI_PICO2_W`), `main.py` = the WiFi wallet.
- Chip: config locked, data zone open, key in slot 0 = `9fad2e82`, unchanged since 09-17.
- Heap is 457 KB in all:

  | Loaded | Free |
  |---|---|
  | after boot (boot.py had already drawn the splash, so the framebuffer was in) | 300 KB |
  | with `wallet` imported | 198 KB |
  | with the boot animations' fonts and drawing code | 206 KB |

  That's room enough for the console.

**What changed on the board:**
- Backed up `main.py`, `slot.txt`, `snake.hi`/`snake.top` and the config snapshot.
- Appended `QUORUM_URL = "http://192.168.4.25:8787"` to `secrets.py`; nothing else in it touched.
- `tools/emu ship bootfx`, then `tools/emu ship quorum`. Both are one-off runs; `main.py` was not
  changed.
- Newer `net.py` and `splash.py` came along. They're still compatible with the old wallet.

**The boot screen options** (`emu/sketches/bootfx.py`, GIFs in `docs/quorum-ui/boot/`), timed on
the chip:

| Option | Average frame | Worst frame |
|---|---|---|
| quorum | 54 ms | 81 ms |
| plug in | 61 ms | 97 ms |
| checklist | 67 ms | 84 ms |
| hash rain | 115 ms | 150 ms |

`show()` alone is 46 ms of every frame, so the push to the panel, not the drawing, sets the
pace. Hash rain runs at about half its GIF's speed.

**The session.** The Pico joined WiFi, announced its P-256 key and became the Safe's third
owner (stand-in owner address `0x3EC9…74A7`). Jason at the device, times PDT:

| Time | # | Transaction | On the Pico | The Safe |
|---|---|---|---|---|
| 20:33 | 0 | Alice: 0.05 ETH to Carol | rejected (Y), reopened, held A 2 s | P-256 verified, low s, 2 of 2, executed |
| 20:34 | 1 | Alice: batch via Safe MultiSend (0.01 ETH, 100 USDC) | signed | verified, executed |
| 20:34 | 3 | Bob: add a stranger as an owner (red) | rejected | still 1 of 2 |
| 20:34 | 2 | Alice: approve 500 USDC to Uniswap Permit2 | signed | verified, executed; nonce now 3 |
| — | 4 | The service lies about the hash | refused on the device | nothing ever posted |
| 20:35 | 5 | Bob: call an unknown contract (red) | rejected | still 1 of 2 |

Every signature came from the ATECC608, over a hash the Pico computed itself from the fields it
showed. The Mac checked each one independently: viem's hash, and `@noble/curves` P-256 against
the key the Pico announced. The lying transaction never got a signature. Had the Pico signed the
hash the service reported, the mock would have logged it as blind signing.

Decisions today:
- `main.py` stays the wallet for now; the console runs one-off until it's chosen as the boot app.
- `QUORUM_URL` stays in the board's `secrets.py`.

Gotchas:
- A rejection on the console isn't a rejection on the Safe. #3 (the owner change) now blocks the
  queue at nonce 3, so #4 and #5 could never execute until #3 is signed or replaced by an on-chain
  rejection. That's iteration 1's open question about what Y should do, now shown on hardware.
- The mock server had been started before the day's changes (new names, the Uniswap scenarios,
  the Safe version), so it answered with old code. Restart `tools/quorum serve` after editing
  `tools/mock-tx-service/`.
- `tools/emu ship quorum` reports "blocking loop" because `quorum.start()` joins WiFi for up to
  12 s before returning. The console was fine; it just outlasted ship's short watch.

Not done today, on purpose: making `quorum` the boot app (`main.py`), any lock on the chip, the
on-chain rejection, and a real chain.

## 2026-09-25 — the chip, read before deciding on any lock

A read-only look at the one chip (`0123f3acfd2a826bee`) before any more locks. The analysis and
the decision are in [docs/LOCKING.md](../docs/LOCKING.md).

**What I did to the board:** the console's timer was paused around each read and restarted, and
the screen stayed where it was. Nothing was written. The reads were the config zone, the lock
bytes, both counters, and each P-256 slot's public key (GenKey in public mode).

**What the chip holds:**
- The config zone has been locked since 09-17. The data zone is open and no slot is locked.
- The config matches the wallet table exactly. Byte 52 differs only because it is counter 0,
  which reads 7. That table turned out to be cryptoauthlib's `test_ecc608_configdata`.
- Keys: slot 0 `9fad2e82…` (lockable, LimitedUse), slot 2 `82004df5…` (not lockable), slot 7
  empty.
- Config byte 18 = `0xA1`: the 608A's CountMatch is on, with its limit in slot 10, which was never
  written.

**Checked onchain, free and read only:**
- The owner addresses the console computes, `0x2843…5E53` for slot 0 and `0x3ca6…594F` for slot 2,
  equal the passkey factory's `getSigner` on Base Sepolia, Base and Ethereum.
- Slot 2 signed the WebAuthn digest of a test safeTxHash. `isValidSignatureForSigner` answered
  `0x1626ba7e` on all three chains, for both the high-s signature as the chip made it and the
  low-s one. A wrong-hash control answered `0x00000000`. Counter 0 didn't move.

Gotchas:
- A data-zone lock would make slot 10's unknown bytes the permanent cap on slot 0's signatures,
  unless slot 10 is written first.
- While the data zone is open, a plaintext PrivWrite can put a known key into any private slot.
  Only a slot lock stops that.

## 2026-09-25 — rung 1 on the real Pico: the chip's approval executes on a real Safe

The console with layer 3 (`firmware/webauthn.py`) went on the board with `tools/emu ship quorum`,
and `main.py` wasn't touched. Behind it, `tools/quorum up` ran a real Safe 1.4.1 on an Anvil fork
of Base (chain 31337, block 51760581): the Family Safe at `0xf77e…7666`.

**The run:**
- The Pico announced key `9fad2e82…` (slot 0). The laptop computed its signer proxy `0x2843…5E53`,
  the board computed the same address itself, and the passkey factory's `getSigner` agreed.
- The factory deployed the proxy on the fork and it became the third owner (2 of 3).
- `tools/quorum demo` queued the stories. Jason opened **#0 Send 0.05 ETH** (Alice had signed) and
  held A.
  - The console posted a WebAuthn contract signature.
  - The service checked it with the proxy's own `isValidSignature`.
  - The Safe executed it: `execTransaction` in 109,488 gas, nonce 0 → 1.
- The same slot 0 signature, checked against the real deployed signer on Base Sepolia, Base and
  Ethereum with `isValidSignatureForSigner`, answered `0x1626ba7e` on all three. The s value was
  low. Counter 0 went 7 → 8. Nothing locked.

**Bug of the day:** the first attempt failed on memory, not on the chain. Jason had toured the chip
map (the lock ceremony, the key's QR). After that, the console's biggest font (`qf_bold26.bin`,
one 10.9 KB block, loaded on first use) no longer fit in the fragmented heap, and every redraw of
a review page raised `MemoryError`.
- The screen stopped updating, and #0 got rejected twice from a console that couldn't draw. The
  rejects were console-only and never reached the Safe.
- Fixed now by a fresh start plus loading both big fonts by hand. Fixed for good by `quorum.start()`
  loading every font while the heap is whole.

Gotchas:
- The demo queue on the fork looks exactly like the simulated one, on purpose. The tells are the
  Safe's address (`0xf77e…7666`), "This key" on the owners page, and the dashboard's "a real Safe
  on the Anvil fork of Base".
- The console fetches only from its home screen; on the chip map it doesn't poll.

## 2026-09-25 — rung 2: the chip's approval on Base Sepolia, accepted by Safe's own service

**Setup:**
- Jason's MetaMask (`0x61D2…637F`, Base Sepolia ETH from a faucet) paid for two `createSigner`
  calls through `tools/quorum live enroll`: the emulator's key (`0xaA87…77b3`) and the Pico's slot 0
  (`0x2843…5E53`).
- In the Safe web app he made a 2-of-3 Safe with those three owners: `0xEDEDC0063B23A309f4cAdA5e1225Ef21D8A30a43`.
  It's Safe 1.5.0 L2, and its code and fallback handler match safe-deployments.
- The Safe API key is in the repo's gitignored `.env`. With it the service allows 50,000 requests
  a month, against 5,000 without.

**Rehearsal: the emulator.**
- Jason proposed #0 (0.0001 ETH) in the web app and signed it with MetaMask.
- `live rehearse` ran the console on the emulator against api.safe.global. It showed #0, signed it,
  and the service took the contract signature: 2 of 2.
- `live exec` sent `execTransaction` through MetaMask:
  [tx](https://sepolia.basescan.org/tx/0x1b2adb3e8a860ab0c8802aaa4af48a13260b4b42749a9e53a135e846d4f370d8).
  - The trace: the Safe's part was 105,584 gas, with the P-256 precompile (3,450) doing the check.
  - The rest of the 270k was MetaMask. Jason's account is an EIP-7702 smart account (MetaMask's
    DeleGator), so MetaMask relayed the call through its DelegationManager with fee hooks.

**The real Pico:**
- Two memory fixes first:
  - The chip map now loads only on X. At start it had left no block over 8 KB, and TLS failed with
    OSError 12.
  - An HTTPS reserve.
- The console then read the Safe straight from api.safe.global.
- Jason proposed #1 and the Pico showed it with the hash verified. He held A and the chip signed in
  155 ms, but the POST failed with OSError 12: after the review the heap was in pieces again (154 KB
  free, nothing over 8 KB).
- The console kept the signature. It was copied off the board and checked against the Pico's proxy
  on Base Sepolia (`isValidSignature` = `0x1626ba7e`), then posted unchanged from the laptop. The
  service answered **201**.
- `live exec`: [tx](https://sepolia.basescan.org/tx/0xe719116d86a019098679ba9b7d5e5263fed8c6fc4cd7181f573b4b3fa3860fde),
  `ExecutionSuccess`, nonce 2.
- That completes the slot 0 checklist's last gate before the lock (docs/LOCKING.md).

**Fixes on the board for the Pico's own POST:**
- `txservice.py` holds a 32 KB block from the start and frees it only during each HTTPS call.
- HTTPS calls get a 15 s timeout: a full TLS handshake on the Pico takes 1–2 s, sometimes more than
  the LAN's 5 s.

Gotchas:
- The Safe web app with a 1.5.0 Safe: the version pill `Safe v1.5.0+L2` runs into "Synced" on the
  console's home screen. Cosmetic.
- MicroPython doesn't flush a file until it is closed. A one-line `open(...).write(...)` backup came
  out 0 bytes.

**Later the same evening: the Pico alone.** With the reserve and the 15 s timeout, every poll in a
three-minute watch succeeded. Jason proposed #2 (0.000067 ETH back to his MetaMask). The Pico
fetched it from api.safe.global, showed it, and signed after the hold (154 ms). It posted the
confirmation itself (`confirmed #2`), and `live exec` executed it:
[tx](https://sepolia.basescan.org/tx/0xa046bd0c4289c9c8e75bb75aca40b6a09afea4c5f446f80e24c5fb6a393d9daf),
Safe nonce 3. Counter 0: 13. Slot 0 still `9fad2e82…`, unlocked.

## 2026-09-25 — slot 0 sealed

The last gate in docs/LOCKING.md was rung 2, now passed, so Jason locked slot 0 on the board.
- Before: `ALLOW_GENKEY` was set to False, because NEW KEY sits beside LOCK SLOT in slot 0's menu.
- The lock: X → DATA → slot 0 → `! LOCK SLOT FOREVER`, armed with B+Y, hold A. **KEY SEALED.**

**Checked from the laptop right after:**
- SlotLocked bytes 88–89 = `fe ff`: slot 0 locked, the others open. The config zone is still
  locked, and the data zone is still open by design (CountMatch in slot 10 stays unsprung).
- The public key read back byte for byte as the enrolled one. The sealed key is Safe owner
  `0x2843705391b7E2cf06b0b964b532Ad9891535E53` on every chain.
- The chip still signs. A new WebAuthn signature (counter 13 → 14) passed the passkey factory's
  `isValidSignatureForSigner` on Base Sepolia, Base and Ethereum, and the deployed proxy's own
  `isValidSignature` on Base Sepolia.
- `ALLOW_LOCK` and `ALLOW_GENKEY` are both back to False on the board.

Not done on purpose: asking the chip for a NEW KEY on slot 0 to watch it refuse. If the lock had
not taken, that test would have replaced the key.

## 2026-09-26 — the production console, and quorum v1 for fresh chips

Branch `firmware-production`. The walkthrough with every new screen is in
[docs/firmware-production/](../docs/firmware-production/).

**The console image.**
- `firmware/manifest.json` lists exactly what goes on the board. `main_console.py` boots straight
  into the console, and B at power-up gives maintenance.
- The legacy wallet, the USB wallet, the demos and the chip map are out of the image.
- In this image:
  - `QUORUM_EXPECT` pins the chip, slot and owner, checked at start and before each signature.
  - Counter 0 is shown and checked for signatures made outside the console.
  - A delegatecall to a contract that isn't pinned is refused.
  - HTTPS checks the certificate against three pinned roots.
  - There is a deadline watchdog, `log.txt`, and a crashed state.
  - The `ALLOW_*` flags, the software key and the WiFi REPL are ignored.
- `tools/fw` builds, backs up, pushes, verifies, pins and restores, checking every hash.

**Quorum v1** is PicoQuorum's own ATECC608 table ([docs/PROVISIONING.md](../docs/PROVISIONING.md)).
- Slot 0 is the only key: external Sign only, LimitedUse, no PrivWrite, sealed after GenKey.
- Slots 1-15 are dead, CountMatch is off, and there is no IO protection.
- Both zone locks carry the CRC the chip checks.
- The ceremony (C1-C10) runs on the virtual chip, on a 608A and a 608B, with a reboot after every
  step.

**Mistakes:**
- The first `tools/fw backup` read files over `mpremote resume` while the board's console was
  running. Something the console printed landed inside the transfer: mpremote failed to parse
  `atecc.py`'s bytes, and a minute later the Pico's USB serial stopped answering, even to a raw
  write. It needs a replug. Nothing was written to the board. `tools/fw` now pauses whatever app
  runs (and holds the watchdog off) while it reads, then resumes it.
- `atecc.decode_slot` had decoded WriteConfig wrong since the fork: `wc >> 1` indexing is right only
  for `0000`. The chip map labelled slot 0 "pubinvalid" when it is "never". Only `== "clear"` was
  ever acted on, so nothing wrong was done with it.
- MicroPython strings have no `ljust`. The OTP record would have raised at C8 on the board; the
  ceremony's dry run caught it.

**On the board, 2026-09-26, nothing written to flash:**
- **Backup:** `tools/fw backup` got 52 files, every hash checked, with the wallet paused while
  reading. `verify --baseline` read chip #1 as expected:
  - `0123f3acfd2a826bee`, 608A
  - key `9fad2e82…`, owner `0x2843…5E53`, computed on the laptop
  - lock bytes `55 00 fe ff`
  - counter 0 = 16: 14 at the seal, +1 the Base mainnet GS021 confirmation, +1 not yet accounted for
- **TLS hazard confirmed:** plain `requests` on the board accepted `self-signed.badssl.com`.
- **Dates are checked:** before NTP the board's clock said 2021 and a verified call was refused
  ("validity starts in the future").
- **The console image compiled on the Pico failed to start.** It was run from `mpremote mount`, so
  nothing went to flash. It had 191 KB free, but no block over 5.7 KB, and a 5.8 KB font would not
  load. Compiling modules on the device leaves the heap in pieces.
- **The fix:**
  - `tools/fw build` now compiles every module but `boot.py` and `main.py` with mpy-cross 1.26.1
    (`.mpy` v6.3, the board's own).
  - `main_console.py` loads the fonts and the HTTPS reserve before anything else.
- **The same image, compiled, from the mount:**
  - It starts. Not pinned (no `QUORUM_EXPECT` in the test file), TLS mode `verified`.
  - 8 of 8 verified polls to api.safe.global, 0.8–1.0 s typically, 7 s at worst.
  - 114 KB free after polling, largest block 10.7 KB, the 32 KB reserve back after every call.
  - badssl.com refused on the certificate itself: expired, wrong host (CN mismatch), self-signed,
    untrusted root.

**The production console on the board, 2026-09-26.**
- **Pin:** `tools/fw pin` read chip #1 and computed owner `0x2843…5E53` on the laptop, equal to
  the enrolled one (live.json), then wrote `QUORUM_EXPECT`.
- **Push:** `tools/fw push console` (build `20464b0`) took a fresh backup, copied 28 files
  (compiled `.mpy`, `main.py`, the roots, `build.py`), deleted the 36 legacy files, and checked
  every hash.
- **Mistake:** the push's "is it back?" probe right after the reset sent Ctrl-C (every mpremote
  command does) while `main.py` was still starting. `quorum` never finished importing, so the
  console never started (it left no log, and no watchdog was running).
  - Fixed: after a reset, `tools/fw` waits for the port and then leaves the board alone for 30 s.
  - `tools/fw restart` does that plus `verify`.
  - The flag read now executes the file itself, instead of a `secrets` module the running app had
    imported before the pin was written.
- **After the restart:**
  - home on the Base Safe, pinned, watchdog on
  - TLS `verified`, connected, this key an owner
  - counter 16 (first look), 67 KB free
- **The queue:** #0 "Send 0.000001 ETH", 2 of 2, signed by this key. That is the GS021 evidence
  transaction, still waiting for `live exec`.
- **Log:** boot, pin ok, counter, watchdog on. The reset cause is 3 even for `machine.reset()`: on
  the RP2350 it goes through the watchdog.

**The production console's first real approval, Base Sepolia, 2026-09-26.**
- **Watchdog:** interrupts off for 12 s over USB. The board reset itself, and the console came back
  by itself (a second boot in `log.txt`: pin ok, watchdog on).
- **Approval:**
  1. `live pico --chain basesep`, then Jason proposed #4 (0.0000067 ETH) in the Safe web app and
     signed with MetaMask.
  2. The Pico fetched it over verified TLS. Jason paged through and held A. The log says
     `signed #4 … counter 17`, `confirmed #4`, with real timestamps now that NTP has set the clock.
  3. `live exec` checked both confirmations onchain and executed:
     [tx](https://sepolia.basescan.org/tx/0x52c6d35fd2dde9b63fe65a7de4b9df2016de0551b178d19a4ae0fc20d170cd1b).
     The Safe's nonce is 5.
- **Back to Base:** `live pico --chain base`. `tools/fw verify`: pinned, TLS verified, watchdog on,
  counter 17, all flags off.
- **Small fix:** `live pico` piled up its own comment line on every switch.
- **Power cycle** (Jason unplugged and replugged it). Reset cause 1 (power-on). The console came
  up by itself in 7 s: pin ok, watchdog on, home on the Base Safe, TLS verified, counter still 17,
  so nothing was signed outside the console.

## 2026-09-26 — chip 2 (`01230e6b8fa23e70ee`): quorum v1 on silicon

The first of five new Adafruit 4314 breakouts. It's also the first run of the three details only
silicon can settle (docs/PROVISIONING.md): the byte order of the CRC summary, the data-CRC layout,
and 4-byte writes into the secret slots' tails.

**Setup:**
- The dual image (build `814299d`) boots chip 1 into the Base console, and this chip into the
  ceremony: `chips.json` has it as chip 2, factory, light.
- `tools/fw allow on` refuses while the pinned chip is on the bus. It was run with chip 2 in, then
  `tools/fw restart`.

**Just before, with chip 1:** Base mainnet #0, the GS021 transaction (0.000001 ETH, confirmed by
MetaMask and chip 1), executed with `live exec`:
[tx](https://basescan.org/tx/0x1b682d376629601808c21cf52cbaddb6e17f57779ef1affd81222c50f1262abb).
The Safe's nonce is 1.

**C1-C3 on chip 2:**
- **C1:** all 8 checks passed, including SelfTest on an unlocked chip (not seen on silicon
  before). The factory table matches the known Adafruit dump except the serial and read-only byte
  14. It is an ATECC608A (`6002`). Snapshot saved.
- **C2:** the laptop computed config CRC `2232` from the pulled snapshot
  (`tools/check_config --summary`). The Pico showed `2232` after writing quorum v1.
- **C3:** the CRC-checked config lock (mode `0x00`, summary `2232`) was **accepted by the chip**.
  That settles the summary's byte order (`crc[0] | crc[1] << 8`) on silicon. Read from the
  laptop: lock bytes `55 00`, still quorum v1, Random live.
- **UI:** the first arm showed no feedback while B+Y were held, so a bar was added, plus "let go
  early: not armed" (build `d7c3493`).
- **C4:** GenKey made key `e199b2d7…` in slot 0; KeyValid, the public key reads back, GenKey on
  slot 1 refused. The owner was computed on the laptop and confirmed by the passkey factory's
  `getSigner` on Base and Base Sepolia: `0x99eDACCAd92537B9146dD0804635bC6dEF7f6b88`.
- **C5:** a plain digest and a WebAuthn assertion both signed and verified on the Pico; Sign on
  slot 1 refused.
- **C6:** slot 0 sealed, SlotLocked `fe ff`, the same key read back. Counter 0 = 4: C5's two test
  signatures, plus one before and one after the seal.
- **UI:** B+Y arm in either order, and a full bar waits for the let-go (build `2eaca51`).
- **C7:** the Pico showed `0x99edaccad92537b9146dd0804635bc6def7f6b88`, the same as the laptop
  and the factory.
- **C8 stopped: the third unknown, settled on silicon.** Before the data lock, the chip refuses
  4-byte writes (`0x0F`) into these secret, never-write slots. It accepts 32-byte writes, including
  one that starts at a slot's last, partial block (bytes 32-35 of slots 1-7, bytes 64-71 of slots
  9-15), presumably keeping the bytes that fit.
  - Probed from the laptop with zeros only, the same bytes C8 writes. The OTP zone was not touched:
    C8 stops before the record.
  - Fix: C8 writes whole 32-byte blocks, the last one at the tail. The virtual chip now refuses
    4-byte writes into those slots before the data lock, as this chip does. The data-CRC lock
    at C9 checks that the tails really hold zeros, and refuses (locking nothing) if not.
- **C8 (again), with the tail fix:** all green, data CRC `b10e`.
- **C9:** the CRC-checked data lock (mode `0x01`, summary `b10e`) was **accepted by the chip**.
  Lock bytes `00 00`. That settles the last two silicon questions: the tails took the zeros, and
  the data CRC is every slot that is not a private key, then the OTP zone. The laptop recomputed
  `b10e` from the record independently.
- **The OTP record:** quorum v1, `01230e6b8fa23e70ee`, slot 0, owner `0x99ed…6b88`, 2026-09-26
  05:46:37 UTC, build `c5226e9`, counter 4. Its key hash matches `e199b2d7…`.
- **Every silicon unknown from PROVISIONING.md is now answered.**
  - The config CRC summary's byte order: `crc[0] | crc[1] << 8`.
  - The data CRC's layout: as documented.
  - 4-byte writes into secret slots before the data lock: refused. A 32-byte write at a slot's
    partial last block works instead.
  - Chips 3-5 get the same ceremony (build `c5226e9` or later), with no probing.
