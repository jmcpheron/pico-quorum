# Tracking upstream picowallet

PicoQuorum keeps picowallet's secure-element drivers and changes them as little as possible, so
their fixes can come across cleanly. This file is where the fork point, merges, and the files worth
watching get recorded.

## Where we are

| | commit | date |
|---|---|---|
| Fork point | `87c717c` | 2026-09-13 |
| Our picowallet work on top (chip map, config fix, wiring) | through `35c744c` | 2026-09-19 |
| Upstream merged through | `72539d5` | 2026-09-21 (merged 2026-09-24) |

What the 2026-09-24 merge brought in: `firmware/trustm.py` (OPTIGA Trust M driver),
`TrustMAttest.sol` and its test, the USB wallet (`usbwallet.py`, `main_usb.py`, `USB.md`,
WebSerial in the app), `blockies.py`, `tools/check_config`, `CLEARSIGNING.md`, and emulator
serial stdin.

How the conflicts were resolved (keep this in mind on the next merge):

- **`firmware/atecc.py`**: this fork's driver is the base (slot decoding, address scan, guarded
  writes and locks that the chip map depends on). From upstream: `SDA`/`SCL` from `secrets.py`
  and `make_i2c` (SoftI2C for non-hardware pin pairs), the `CONFIG` asserts and `CONFIG_SHA256`
  fingerprint, config writes in batches of 8 words per wake (watchdog fix seen on silicon), and
  `verify_config()`. The two `CONFIG` tables were already byte for byte identical.
- **`firmware/signer.py`**: this fork's. `lock_config()` locks what is on the chip;
  `provision()` writes the proven table, verifies it, then locks.
- **`firmware/usbwallet.py`** (upstream's, adapted): its lock-config and setup ops call
  `provision()` rather than `lock_config()`. The A press on its provisioning screen arms the
  signer for that one action, since this fork refuses permanent actions unless armed.
- **`firmware/wallet.py`**: this fork's splash WiFi join, wrapped in try/except for boards
  without a WiFi chip (upstream's fix).
- **`firmware/secrets.example.py`**, **`emu/web/worker.js`**, **`README.md`**: both sides kept.

Checked after the merge: `tools/check_config` ok; `test-vectors` 9/9 on CPython and
MicroPython; the emulator boots the WiFi wallet, the chip map and the USB wallet, and USB setup
provisions a blank virtual chip; `forge test` 40/40, including TrustMAttest 6/6. Not checked:
anything on real hardware, and `trustm.py` has not run against a Trust M in this repo. (It has
since: 2026-09-28, unchanged, under `trustm_q.py`. See docs/TRUSTM.md.)

## What is still from picowallet

These files started in picowallet, by Austin Griffith (MIT), and each says so at its top:

| | files |
|---|---|
| Chip drivers | `firmware/atecc.py` (its transport core), `firmware/trustm.py` |
| Crypto and display helpers | `firmware/keccak.py`, `firmware/p256.py`, `firmware/lcd.py` (the ST7789 core), `firmware/blockies.py`, `firmware/net.py` (WLAN join) |
| The emulator | `emu/core/runtime.mjs`, `png.mjs`, `workspace.mjs`, `ship.mjs`, `devices.mjs`, `usbinfo.py`; the shims `machine.py`, `_bootstrap.py`, `network.py`, `requests.py`, `socket.py`, `rp2.py`; `emu/headless.mjs`, `emu/cli.mjs`, `emu/server.mjs`, the dev page in `emu/web/` (not `browser.mjs`) |
| Tools | `tools/emu`, the start of `tools/check_config` |

Removed on 2026-10-06, before the repository went public, because PicoQuorum doesn't use them:
the single-owner vault app (`app/`: Scaffold-ETH 2, `ChipAccount`, `TrustMAttest`), the case
(`cad/console/`, with the Plass and Zez0000 parts), the Pi signer and SeedSigner parts
(`reference/`), the wallet firmware (`wallet.py`, `usbwallet.py`, `mock.py`, `demo.py`,
`keytest.py`, `vid.py`, `eip712.py`, `main.py`, `main_usb.py`, `power.py`), the case and WiFi-console
tools (`pico`, `push`, `qr`, `shot`, `gif2pv`, `lid`, `zez*`), the 3D view, and the picowallet notes
(`picowallet.md`, `PLAN-picowallet.md`, `HANDOFF.md`, `USB.md`, `CLEARSIGNING.md`, `TESTPLAN.md`,
`UPSTREAM.md`, `UPSTREAM-ISSUE.md`, the 2026-09-05 build-log entries and photos). They are all in
this repository's history, and in [picowallet](https://github.com/austintgriffith/picowallet).

## How to bring a fix across

A whole merge would mostly be conflicts now: upstream edits files this repo no longer has. Bring
fixes across file by file instead:

```sh
git remote add upstream https://github.com/austintgriffith/picowallet   # once
git fetch upstream
git log --oneline 72539d5..upstream/main -- firmware/atecc.py firmware/trustm.py firmware/keccak.py firmware/p256.py firmware/lcd.py
git diff 72539d5 upstream/main -- firmware/trustm.py | git apply -3    # one file at a time
python3 test-vectors/run.py && python3 tools/check_config               # must still pass
```

A change to a console-image file changes the release fingerprint: rebuild the pages and badges
([RELEASES.md](RELEASES.md)). Then update the table above and add a line to the log below.

- `firmware/atecc.py`, `firmware/trustm.py`: change them as little as possible, so upstream's
  fixes apply cleanly; put PicoQuorum's needs in new modules (`trustm_q.py`, `chipcfg.py`).

## Files to watch

`firmware/atecc.py`, `firmware/trustm.py`, `firmware/keccak.py`, `firmware/p256.py`, and upstream's
`SECURITY.md`.

## Log

- 2026-09-24: forked as PicoQuorum. Upstream checked at `72539d5`, nothing merged yet.
- 2026-09-24: merged upstream through `72539d5` (20 commits); conflicts resolved as above.
- 2026-09-24: merged the PicoQuorum restructure (`picoquorum-rung1`: `docs/`, `hardware/wiring/`,
  `cad/console/`). `USB.md` and `CLEARSIGNING.md` moved into `docs/`; upstream's README changes
  carried into `docs/picowallet.md`.
- 2026-10-06: before going public, removed the picowallet-only files listed above, and credited
  picowallet at the top of every file still from it. Nothing merged; upstream not checked.
