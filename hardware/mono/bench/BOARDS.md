# Mono: the boards

Under [Bring-up](#bring-up), one row a board, added by [`check.py`](check.py) at step 4 of [BRINGUP.md](BRINGUP.md): what
`stage0.py` read and what the person at the bench saw. The USB serial is the CH343P's, the end of
the port's name on a Mac. The key chip's serial is what the console logs later. What happens to a
board after bring-up (prepared, a key made, sealed) goes in its own log, below.

## Where each stands

Each board's history is in its own folder, [`../boards/NN/`](../boards/), written by
[`boardlog.py`](boardlog.py): an entry a step, with the files that step left. This table is each
board's last state. The number is written on the board's back. Kept out of the repository: a board's
`secrets.py`, `pin.json`, `keyflow.json` and `safes.json`, raw relay logs, and an owner's address.

<!-- states: boardlog.py writes between these lines -->
| board | since | state | its log |
|---|---|---|---|
| 1 | 2026-11-20 | Sealed and pinned 2026-11-20 (quorum v1, config CRC e382, data CRC c4a7). Watches one Safe. Signed once, 2026-11-20, and that transaction was executed | [boards/01](../boards/01/LOG.md) |
<!-- /states -->

## Bring-up

| board | date | USB serial | RP2350 id | key chip | key | KEY 2 | buttons | by eye | result |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-17 | `5D2F0290041` | `08533e36067dd71e` | `012338eb2797f690ee` | rev 00006005, data open, config open | off 00 on 11, empty | D0 D1 D2 | as it should be | pass |
