# The USB link

From 2026.11.1 a running console holds its USB serial port itself (`firmware/usblink.py`). A
computer can ask it a few things: the app's **Device** page in Chrome, `tools/fw` and
`tools/quorum live pico` do. The MicroPython REPL is not there while the console runs. It opens
only in maintenance.

## What it never does

- **It never signs.** There is no sign request, and nothing in `usblink.py` names the signer or the
  chip. `test-vectors/manifest.mjs` checks this, and `quorum.sign_it` is still the one place that
  signs.
- **It never reads a key out.** The status shows the public key and owner address the console
  already shows on its Key screen.
- **It never touches the chip.** Status is what the console already knows. A spy on the signer in
  `test-vectors/console_test.py` (`case_link`) checks that no request calls it.
- **It writes three files, and only when asked and accepted:** `wifi.json`, `safes.json` and
  `maint`. It never writes `secrets.py`, the pin (`QUORUM_EXPECT`), the `ALLOW_*` flags, the API key or
  the firmware.
- **It never sends a password or the API key.** Status lists saved Wi-Fi networks by name.

## How a request goes

One JSON object per line, each way, at 115200 baud. Every request has an `id`. Every answer starts
`{"pq":1,` and carries the same `id`. The console also prints logs on the same port; a host skips
any line that doesn't start `{"pq":`. A line longer than 2 KB is dropped.

The console writes each answer in pieces of 64 bytes. On an ESP32-S3's own USB, MicroPython 1.26.1
drops the front of a long write. On the PicoquorumKey, a 600-byte line written at once came out as
its last 318 bytes, every time; written in 64-byte pieces it came out whole (2026-11-02). A log line
printed between two pieces can land inside an answer; the host then skips that answer.

| `op` | What it does | Answer |
|---|---|---|
| `hello` | names the console | `proto`, `mode` (`console`, `setup` or `stopped`), `board`, `image`, `version`, `release` (the fingerprint), `build` |
| `status` | what it knows now | the console: `state`, `ready`, `serial`, `profile`, `owner`, `key` (compressed), `pinned`, `pinWhy`, `counter`, `chip` {`model`, `configLocked`, `dataLocked`, `keySealed`, as read at boot}, `watchdog`, `wifi` {`up`, `ssid`, `saved`}, `safes` [{`chainId`, `address`, `name`, `ok`, `threshold`, `owners`, `nonce`, `isOwner`, `queued`, `waiting`}], `safesFrom`. In Wi-Fi setup: `hotspot`, `view`, `joining`, `result`, `msg`, `wifi` |
| `wifi` | asks to save a network: `ssid`, `pass` (`wificfg.check`'s rules) | after the person decides |
| `safes` | asks to watch 1 to 4 Safes: `safes` [{`chainId`, `address`, `name`}] | after the person decides |
| `maint` | asks to restart into maintenance | after the person decides |
| `cancel` | takes an open ask off the screen | at once |

Before an ask reaches the screen, the console checks it:
- A Safe has only those three fields. A Safe's own service (`url`) comes only from `secrets.py`.
- Its chain must have a pinned service in `quorum_cfg.py`.
- A name is at most 24 plain characters.
- The same Safe can't appear twice.

A bad ask is answered at once with `"ok": false` and a reason, and nothing changes.

An ask answers `{"pq":1,"id":…,"ok":true,"kind":…}` once it is written, or `"ok":false` with
`why`:
- `refused on the device`;
- `busy: …`, when a review, a hold or a signature is under way (those are never interrupted), or
  another ask is open;
- `nobody accepted it in time`, after 120 s;
- `cancelled by the computer`.

## On the console's screen

An ask comes up like a review: every page has to be seen, then Sign is held.
- **Wi-Fi:** the network's name.
- **Safes:** each Safe on a page of its own (its name, chain, address in groups and blockie), then
  a page that says they replace the Safes it watches now.
- **Maintenance:** a red page; the hold is 3 s, as for a red transaction.

| | Pages | Accept | Refuse |
|---|---|---|---|
| Three buttons (Feather, PicoquorumKey) | D1 | D2 held 2 s (3 s red) | D0, one press |
| Waveshare | joystick | A held | Y or B |
| Knob (Build 1) | turn | the knob held down | B, or wait 120 s |

Once accepted, the console writes the file (a tmp file, then a rename), answers, and restarts 1.5 s
later. It reads `safes.json` before `secrets.py`'s `QUORUM_SAFES`. A new board in **Wi-Fi setup**
answers `hello`, `status` and `wifi` only: it shows the network, joins it after D2 (or A) is held
2 s, and saves it as the hotspot's page does.

## Ctrl-C and the REPL

- `boot.py` turns Ctrl-C off on its first line.
- `main.py` turns it off again on its first line, because MicroPython turns it back on for each
  file. Then `main.py` ends in `usblink.run()`, which never returns. A console that failed to
  start still ends there, so a failed start doesn't open the REPL.
- With Ctrl-C off, 0x03 (and Ctrl-A, Ctrl-B, Ctrl-D) reach the link as plain bytes. This was
  checked on the PicoquorumKey on 2026-11-02.
- The ceremony and brand images keep the REPL, because they are bench images (`tools/fw ceremony`).
  So does the dual image while it runs the ceremony or the claim.

**Maintenance** is the way to the REPL. Hold the maintenance key at power-up (D1 on three buttons,
B on the Waveshare, the knob on Build 1), or accept the link's `maint` ask. `tools/fw` sends that ask
by itself before anything that needs the REPL, prints "hold D2", and takes the board out of
maintenance when it's done. `tools/fw verify` reads a linked console through `hello` and `status`;
`--files` hashes every file, in maintenance.

## What it doesn't stop

Anything holding the USB port can still reflash the board:
- An ESP32-S3 enters its ROM bootloader from the DTR and RTS lines, and esptool or esptool-js
  (Chrome) can then write any firmware.
- A Pico reboots to BOOTSEL on a 1200-baud touch.

New firmware can make the chip sign anything, as in [SECURITY.md](SECURITY.md). The link closes
the quiet way in, the running console's own Python. Secure boot and turning off USB download close
the rest. On the S3 both are permanent eFuse settings, and neither is done.

The app's page and the tools keep DTR and RTS low. Toggling them resets an S3.

## The hosts

- **The app** (`web/src/device.mjs`, `#/device`): Web Serial in Chrome or Edge on a computer.
- **`tools/board/link.py`**: one request, one answer. It runs on pyserial 3.5, pinned, through
  `uv run`, as `tools/fw` and `tools/quorum live pico` call it.
- **`emu/core/devices.mjs`**: the emulator's device list asks `hello` before anything else.

## The relay (console-rp)

console-rp has no radio. Its USB-C reaches only a CH343P, wired to UART1 (GPIO 20 and 21); the REPL
and the RP2350's own USB are on J3, which isn't fitted
([hardware/console-rp/README.md](../hardware/console-rp/README.md)). So the one port carries two
things: the computer's requests above, and the console's own calls to Safe's service, which the
computer makes for it (`firmware/link.py`). The computer here is the relay.

- 8N1 at 460800, one JSON object a line each way.
- **The console asks:** `{"t":"req","id":7,"m":"GET","url":"…"}`, with `"body"` on a POST. The relay
  answers `{"t":"res","id":7,"status":200,"body":"…"}`, or status 0 and `"err"` when it couldn't.
- **The relay says `{"t":"hi"}`** every 2 s. After 15 s of nothing the console shows "no relay: open
  the app" and asks nothing until it hears one.
- **Logs go out** as `{"t":"log","m":"…"}`, each line of `log.txt` as it is written. Nothing comes
  back for them.
- **The computer's requests** are the table above, answered `{"pq":1,…}`. Only the `safes` ask is
  there: no `wifi`, with no radio, and no `maint`, whose REPL would be on J3, out of reach.

Before it sends anything, the console checks the URL (`link.pinned`): under one of
`quorum_cfg.py`'s `"services"`, plain ASCII, at most 400 characters, no `..`, `@`, `#` or `\`. A
development load (no `build.py`) also allows `secrets.QUORUM_URL`, the laptop's mock.

What comes back:
- Only an answer with the id the console waits for is read. Any other line is dropped and counted:
  `garbage`, `overlong`, `unsolicited`, `wrong_id`, `dup`, `nomem`, in the status's `link`.
- A line is at most 24 KB (`link.MAX_LINE`, hello's `link.max`). The relay sends a longer answer as
  status 0, `"answer too big: N bytes"`. The console then reads the queue 3 at a time (`&offset=`),
  and a page still too long one at a time. A transaction too long even alone is listed red in its
  place, "Too big to check", `#?`, and can't be signed. The rest of the queue is listed as usual.
- A body nested more than 64 deep is refused before `json.loads` (`txservice.shallow`).
- The console waits 15 s. The relay gives the service 12.
- The body is checked as Safe's service is checked on the Wi-Fi boards: the console rebuilds every
  hash from the fields it shows (AGENTS.md rule 1).

What it never does, on top of the list at the top:
- `link.py` imports no signer and writes no file; `test-vectors/manifest.mjs` checks both. No
  message names the chip, a digest or a signature.
- The console sends no API key: it has none. The relay adds its own, on requests to
  `api.safe.global` only.
- `pin.json` is written only by the key flow on the device, when the owner's key is sealed. No
  request writes it.

What the relay can still do is what a lying service can do: show transactions that don't exist,
hold back ones that do, drop a signature on its way out
([hardware/console-usb/README.md](../hardware/console-usb/README.md#the-link-what-the-computer-can-and-cant-do)).

The relays:
- `tools/relay/relay.py`, the bench's. [Its README](../tools/relay/README.md) says what it forwards,
  what it logs, and its hostile modes.
- The app's Device page (`#/device`: `web/src/device.mjs` and `web/src/relay.mjs`), in Chrome or
  Edge on a computer: the customer's. The same rules as the CLI, with the API key from the app's
  Settings. A CH343P (USB vendor 0x1a86) opens at 460800; the page says `hi` once hello's answer
  carries `link`, and hides the Wi-Fi card. Tried on board #2 (below).

What was checked:
- `case_relay` in `test-vectors/console_test.py`, with a fake relay: poll, review, sign and POST,
  and each hostile case, which ends dropped or refused, never signed.
- `tools/relay/relay_test.py`: URLs off the pin, other paths, sizes, and the API key never in a log.
- `web/test.mjs`: the same cases against `relay.mjs`, and the key only on Safe's own service.
  `web/e2e.mjs`: a fake console-rp on the Device page in Chromium, its calls made with the Settings
  key, one off the pin refused with nothing fetched, a confirmation posted as sent, its log drawn as
  text, and the key never down the cable.
- Board #2, 2026-11-09 and 10: a 12.5 h soak with 8842 status reads and 76 polls, no link faults;
  two signatures posted through `relay.py` (201) and executed on Base Sepolia. Until 862fba4f read
  an answer's body in place, a 2.4 KB queue found no block its size in the heap, every other poll.
- Board #2 on 0d617601, 2026-11-10, with an empty queue: each of `relay.py --hostile`'s link faults
  (garbage, overlong, unsolicited, wrong-id, dup, late, truncate, stall, nested, chatter) on every
  answer for a while. Each ended dropped and counted, or as one failed poll with the next one fine.
  A body nested 5000 deep runs `json.loads` out of memory, which the poll catches. No restart, no
  `nomem`, at least 80.8 KB free after a collection, and the largest free block 8.3 KB, read over SWD,
  as before the faults.
- Board #2, 2026-11-10, the forged queue: a real transaction (nonce 2, one of two confirmations)
  and `relay.py --hostile forge-queue`, which changes its value and keeps its hash. On 0d617601 the
  console showed it red ("a hash these fields do not produce"), Sign dimmed, and posted nothing. But
  the refusal stayed under the hash, so the real copy stayed refused until a restart. On a30640ce a
  refusal holds only for the fields it was given: a checked entry kept its fields against forged
  answers, and after a restart with the forged copy first, the console refused it.
- Board #2 on a30640ce, the same day: the Device page in Chrome relayed the real queue, with
  `relay.py` stopped. The console signed nonce 2, and the app showed its confirmation, 2 of 2,
  checked against the owner contract. The board's log has no start between the refusal and the
  signature (7263 s into the same start, counter 26), so the real copy replaced the refusal without
  a restart. Chrome opening the port didn't restart the board either.
- Board #2 on dd82e30a, the same day, with two Safes (2 of 2, and 3 of 6), the list sent from the
  Device page: both polled in turn, 61 to 74 KB free across the runs below.
- `relay.py --hostile big`, one real transaction in each queue: each queue of 10 came back "answer
  too big", then 3 at a time, then one at a time with `&offset=`, which Safe's service takes. Each
  transaction came up red as `#?`, and the next one at a time came back empty, which ends the queue.
  About 16 minutes of it, 65 KB free or more, no restart.
- `relay.py --hostile lose-post`: the confirmation went out and no answer came back. The console
  showed "Not sent", with the signature kept. ▲ Retry posted the same signature (201) with no new
  use of the key: the counter stayed at 30. The second time, the board was restarted instead of
  retried. 8 s into the next start, at its first poll, the console sent the kept signature (201).
- 100 restarts over SWD (`probe-rs reset`, which writes nothing), one every 13 s, with `relay.py`
  running. 99 came back on home, pinned, with both Safes polled, 12.8 to 15.2 s after the reset.
  The counter went up by exactly one each time, 32 to 131. 67.9 to 69.3 KB free, no link timeouts
  or garbage, and every start's reset cause 1. The 5th came up "No chip": nothing answered on I2C
  at the start, and the console stayed there, with ▲ Check again, until the next restart. The
  counter didn't move. 6 minutes later SDA and SCL both read high. Why the chip didn't answer is
  not known. Since f95d12fd a start that finds no chip clocks the bus free and looks again, and
  logs why ([hardware/console-rp/SETUP.md](../hardware/console-rp/SETUP.md#no-chip)). Board #2 runs
  f95d12fd since 2026-11-11 and its first start was as before (pinned, counter 153). No start has
  missed the chip since, so the looks again are checked in `console_test` (case_nochip) only.
- 20 unplugs of the USB-C by hand, with the SWD probe's GND, CLK and DIO still wired (no 3V3): 10
  out for about 3 s at home, 5 pulled again 2 to 3 s into the start, and 5 out for about 1 s. Every
  start after came back on home, pinned, about 7 s after its boot line, 67.5 to 67.8 KB free. The
  counter went from 131 to 152: one for each of the 20 starts, and one for the cut start that had
  read the chip before it lost power. The other cuts came before that read and used nothing. No
  error in the log. A dump over SWD after: every file there, `pin.json` and `keyflow.json` the same
  bytes as before dd82e30a's load, the JSON files parsing, no broken line in `log.txt`.
