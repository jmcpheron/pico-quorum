# Mono board 1

Written by [`boardlog.py`](../../bench/boardlog.py), an entry a step, the newest last.

## 2026-11-17 19:55

Bring-up, steps 1 to 4 of BRINGUP.md. Loaded over SWD through wires soldered to SWCLK, GND and SWDIO: MicroPython v1.26.1 and stage0.py (MicroPython's piece failed three times and went on the fourth). CHIP_ID 30004927, XOSC_STATUS 81001000. stage0's facts: RP2350 id 08533e36067dd71e; I2C0: 60; ATECC608 rev 00006005, serial 012338eb2797f690ee, data open, config open; KEY 2: off 00 on 11, empty. D0, D1 and D2 each counted. By eye, as the person at the bench answered: the white frame, red green blue, upright with D0 left, each box green and the LED lit. check.py's row is in BOARDS.md. 3V3, RUN and DVDD were metered and said to look good; the figures were not written down. USB serial 5D2F0290041.

- repository at `91aaa81`
- state: Brought up, the chip as it came

## 2026-11-17 19:55

Step 6: console-rp's image, build daaa14e, release f24d·22db, loaded with swdload.py --no-micropython. The screen: a red Not prepared, chip 012338eb2797f690ee (a photo). Not checked: the footer's caps, the link at 460800, step 5's current and temperature.

- repository at `91aaa81`
- state: Brought up, the chip as it came. console-rp's image ran on it

## 2026-11-17 19:55

Step 7 begun: prepare-rp, build 91aaa81, release 4e98·1658, loaded with swdload.py --no-micropython and a bench secrets.py holding only ALLOW_LOCK = True (one piece failed once and went on the second try). Nothing on the chip has changed at this entry: C3, the config lock, waits for the arm and the hold on the board.

- repository at `91aaa81`

## 2026-11-17 20:10

Step 7: the chip prepared, on the board, by the person at the bench (the arm and the hold). prep-log.txt: C1 ok (rev 00006005 ATECC608C, zones unlocked, the factory table, the config saved as the snapshot); C2 ok (34 bytes changed, reads back as quorum v1, config CRC e382); C3 ok, the config zone locked, which is permanent; P4 ok (config locked, quorum-v1, data zone open, slot 0 not sealed and empty, counter 0 at 0). Then swdload.py --dump, read only: prep-log.txt and the snapshot, kept here. tools/check_config --summary on the snapshot gives the same CRC, e382, for the quorum-v1 lock. This chip can't take the branded table now.

- kept [`prep-log.txt`](prep-log.txt), sha256 `50c188fe5bf9c991b1de1962241288457937652f42491694ff244956d8b17157`
- kept [`snapshot-012338eb2797f690ee.bin`](snapshot-012338eb2797f690ee.bin), sha256 `0b123d91ed8f9a71fb4b19267947052cb4f0890376caa3aff88888b58dbf827c`
- repository at `91aaa81`
- state: Prepared 2026-11-17 (quorum v1, config CRC e382). No key

## 2026-11-17 20:13

console-rp's image again, build daaa14e, release f24d·22db, loaded with swdload.py --no-micropython and no secrets.py: the whole filesystem is new, so the bench's ALLOW_LOCK file is gone from the board. Every piece went on the first try. What the screen shows is not yet written here.

- repository at `91aaa81`

## 2026-11-18 22:37

The link at the console's rate, 460800, read through the USB-C: a hi and a status ask, four asks, four answers. The status: image console-rp, version 2026.11.3, profile quorum-v1, state C4, mode key, serial 012338eb2797f690ee, counter 0, ok true; the link up, 94064 bytes free, no garbage, timeouts or drops. Asked by a few lines using relay.py's open_serial, with no network; relay.py itself was not run. CHIP_ID still reads 30004927 through the soldered wires. This is the first time a Mono's link answered at 460800. Not seen by anyone yet: what the screen shows.

- repository at `c7da2a5`
