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
anything on real hardware, and `trustm.py` has not run against a Trust M in this repo.

## How to merge

```sh
git remote add upstream https://github.com/austintgriffith/picowallet   # once
git fetch upstream
git log --oneline 72539d5..upstream/main          # what is new
git diff 72539d5 upstream/main -- firmware/atecc.py firmware/trustm.py firmware/keccak.py
git merge upstream/main                           # a merge commit, never a rebase
python3 test-vectors/run.py && python3 tools/check_config   # must still pass
```

Then update the table above and add a line to the log below.

## Files to watch

`firmware/atecc.py`, `firmware/trustm.py`, `firmware/keccak.py`, `firmware/eip712.py`,
`app/packages/foundry/contracts/TrustMAttest.sol`, `SECURITY.md`, `CLEARSIGNING.md`.

## Log

- 2026-09-24: forked as PicoQuorum. Upstream checked at `72539d5`, nothing merged yet.
- 2026-09-24: merged upstream through `72539d5` (20 commits); conflicts resolved as above.
