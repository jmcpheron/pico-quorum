# Mono: the boards

One row a board, added by [`check.py`](check.py) at step 4 of [BRINGUP.md](BRINGUP.md): what
`stage0.py` read and what the person at the bench saw. The USB serial is the CH343P's, the end of
the port's name on a Mac. The key chip's serial is what the console logs later. What happens to a
board after bring-up (prepared, a key made, sealed) goes in [the README](../README.md), as
console-rp's does.

| board | date | USB serial | RP2350 id | key chip | key | KEY 2 | buttons | by eye | result |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-17 | `5D2F0290041` | `08533e36067dd71e` | `012338eb2797f690ee` | rev 00006005, data open, config open | off 00 on 11, empty | D0 D1 D2 | as it should be | pass |
