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

## 2026-11-18 23:14

A photo of the screen under console-rp f24d·22db: Your key, Made here, 'An old key: Make replaces it', ▲ Make; the picture upright and whole. Over the link the state was C5 before this load: a key had been made on that image, not sealed, counter 0. Then console-rp build d3821ed, release cec2·b7ac, loaded with swdload.py --no-micropython and no secrets.py: Make on D0, and the Make page counts its starts. Loaded twice, the second by my mistake (the same image, written whole again); every piece went on the first try both times. After the second: the log over the link says 'start 1 at Make' at +5 s, then at +13 s 'C4 ok: new key 15bc0b8f; KeyValid ok; public key reads back ok; GenKey on slot 1 refused ok', so a press on the board made a key under the new image; state C5, counter 0. Not sealed. Not yet said by the person at the bench: what the new screens look like, and which button was pressed.

- repository at `d3821ed`
- state: Prepared 2026-11-17 (quorum v1, config CRC e382). A key made, not sealed

## 2026-11-20 20:32

Before the owner's key: read again, nothing written and nothing restarted. Over SWD through the soldered wires, CHIP_ID 30004927 and XOSC_STATUS 81001000. Over the link at 460800, a hello and a status ask with relay.py's open_serial, no hi and no network, both answered: image console-rp, version 2026.11.3, build d3821ed, release cec2·b7ac, profile quorum-v1, state C5, mode key, serial 012338eb2797f690ee, counter 0, ok true; the link up, 87952 bytes free, no garbage, timeouts or drops. The repository's tip, ed85223, builds console-rp to the same release, cec2·b7ac: no firmware commit since d3821ed. On the emulator at ed85223: manifest.mjs all pass; run-console.mjs 0 failed; run-ceremony.mjs 0 failed, the owner's Make, Replace and Seal on console-rp among them. A listener was then left on the link, sending nothing, to keep the console's log lines while the key is picked. Not checked: step 5's current and temperature, the footer's caps, which panel is in J2, and what the Make page says at this start.

- repository at `ed85223`

## 2026-11-20 20:44

The owner's key, made and sealed on the board by the person at the bench, under console-rp d3821ed, release cec2·b7ac. This was start 4 at Make since the load. 18 keys were made at this start, each a 'C4 ok' in the console's log (KeyValid, the public key read back, GenKey on slot 1 refused), and the 18th, d778a05c, was sealed. C5 ok: a plain digest and a WebAuthn digest verify, counter 0 to 2, Sign on slot 1 refused. C6 ok: slot 0 locked (FE FF), the same public key, signs and verifies. C7 ok. C8 ok: slots 1-15 zeroed, the record in OTP, data CRC c4a7. C9 ok: the data zone locked (86 = 00), OTP frozen, slot 1 unreadable, signs and verifies sealed. C10 ok: quorum v1, locked 00/00, slot 0 sealed, the record matches the key, counter 7, pin.json written. C5 to the end took about 20 s by the console's clock (+1132 s to +1152 s). Then the console restarted itself (reset cause 3) and came up 'pin ok', counter 8 at its first look. This is the first key sealed on a Mono, and both locks are permanent. How it was read: a listener on the link at 460800 that sent nothing heard the last ten keys and the seal, and log.txt from the dump has the whole start. After the restart, a hello and a status ask: mode console, pinned true, ATECC608C, config locked, data locked, key sealed, counter 9, no Safes, 68064 bytes free, no link faults. The watchdog is off: the code starts it only once the console has a Safe. Then swdload.py --dump, read only, 4 min 4 s, one piece read twice (blocks 608-639, the target did not answer once): chips.json, the counter's file, keyflow.json, log.txt, owners.txt and pin.json, kept out of the repository under backups/. A later load needs that dump, or a newer one, and --keep. Not seen by me: any screen. Not yet said by the person at the bench: what the pick, Seal and pinned pages look like, whether the caps sit over D0, D1 and D2, which panel is in J2. Not done: a Safe, a signature, step 5's current and temperature.

- repository at `ed85223`
- state: Sealed and pinned 2026-11-20 (quorum v1, config CRC e382, data CRC c4a7). No Safe yet

## 2026-11-20 21:50

A Safe, sent over the link and accepted on the board. Before it, one more start, by power (reset cause 1) with nothing listening: pin ok, counter 9 to 10. At +149 s of that start the log says 'heap: no 2048 bytes in one piece (largest 1984, 71680 free)', and no 'in one piece again' follows before the next restart at +1067 s. That start had no Safe and no relay, so nothing asked for memory. Then relay.py with --safes and one Safe on Ethereum mainnet, its address not kept here: the ask came up on the board and the person at the bench accepted it there. The console wrote safes.json and restarted itself (reset cause 3): pin ok, watchdog on at +6 s, counter 11. Through the relay it read the Safe (200, 580 bytes) and its queue (200, 131 bytes): 2 of 3 owners, this key one of them, nonce 0, nothing queued. Status after: home, ready, 68 to 70 KB free, no garbage, timeouts or failed requests; 5 polls in the first 7 minutes, each 200. This is the first Mono to watch a Safe. Each start since the seal cost one count: 8 to 9, 9 to 10, 10 to 11, and the log names no use outside the console. Then a second swdload.py --dump, read only, with the relay still running: the same files and safes.json, under backups/. The relay's logs are under hardware/console-rp/bench/runs/, which git ignores. Not done: a signature. Not seen by me: any screen.

- repository at `ed85223`
- state: Sealed and pinned 2026-11-20 (quorum v1, config CRC e382, data CRC c4a7). Watches one Safe. No signature yet

## 2026-11-20 22:53

A signature. Before it, two more starts by power, the person at the bench unplugging the board and plugging it back: counter 11 to 12 to 13, one for each, and the watchdog on after each. relay.py ended with a traceback each time the port went (OSError 6, Device not configured), so it was run again in a loop that waits for the port. After the second plug-in the link counted one garbage line, which it dropped; most likely a stray byte from the plug. Then one transaction was queued on the mainnet Safe at nonce 0, by the Safe's owner and not by me. The console read the queue (200, 1502 bytes) and listed it: 1 queued, 1 waiting for this key. It stayed in review from about 22:13 to 22:52, the console asking nothing in that time. Then the console's log: 'signed #0', counter 14, and the confirmation went out through the relay: 201, 840 bytes, 571 ms; then 'confirmed #0'. The next read of the queue (200, 2469 bytes) no longer has it waiting for this key: 1 queued, 0 waiting. The counter went up by exactly one for the signature, 13 to 14. Through the run: 45 status reads, 8 requests, 64 to 70 KB free, no timeouts, no failed requests, no nomem. This is the first signature from a Mono. Not checked by me: the signature against the owner's address by any means of my own (Safe's service took it with 201, and the console's next read agreed); what the review's pages showed; whether the transaction was executed. Still not said by the person at the bench: whether the caps sit over D0, D1 and D2, which panel is in J2, and step 5's current and temperature.

- repository at `ed85223`
- state: Sealed and pinned 2026-11-20 (quorum v1, config CRC e382, data CRC c4a7). Watches one Safe. Signed once, 2026-11-20

## 2026-11-20 22:54

The transaction it signed was executed: at 22:54 the console's status has the Safe's nonce at 1 and nothing queued (the queue's answer back to 132 bytes), where it was nonce 0 with one queued before. Read from the console's status through the relay; I looked at nothing on the chain myself. The board is on home, ready, counter 14, watchdog on, 64 KB free.

- repository at `ed85223`
- state: Sealed and pinned 2026-11-20 (quorum v1, config CRC e382, data CRC c4a7). Watches one Safe. Signed once, 2026-11-20, and that transaction was executed

## 2026-11-20 23:11

By the word of the person at the bench: they read the transaction on the board and signed it there, then executed it from another owner's account. It was on Ethereum mainnet. This is the first transaction a Mono has signed that went through.

- repository at `ed85223`
