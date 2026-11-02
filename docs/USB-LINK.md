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
drops the front of a long write. On the PicoQuorumKey, a 600-byte line written at once came out as
its last 318 bytes, every time; written in 64-byte pieces it came out whole (2026-11-02). A log line
printed between two pieces can land inside an answer; the host then skips that answer.

| `op` | What it does | Answer |
|---|---|---|
| `hello` | names the console | `proto`, `mode` (`console`, `setup` or `stopped`), `board`, `image`, `version`, `release` (the fingerprint), `build` |
| `status` | what it knows now | the console: `state`, `ready`, `serial`, `profile`, `owner`, `key` (compressed), `pinned`, `pinWhy`, `counter`, `watchdog`, `wifi` {`up`, `ssid`, `saved`}, `safes` [{`chainId`, `address`, `name`, `ok`, `threshold`, `owners`, `nonce`, `isOwner`, `queued`, `waiting`}], `safesFrom`. In Wi-Fi setup: `hotspot`, `view`, `joining`, `result`, `msg`, `wifi` |
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
| Three buttons (Feather, PicoQuorumKey) | D1 | D2 held 2 s (3 s red) | D0, one press |
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
  checked on the PicoQuorumKey on 2026-11-02.
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
