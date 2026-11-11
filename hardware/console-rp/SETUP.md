# console-rp: setting one up

*What exists on 2026-11-10, as board #2 was set up. The app's relay isn't written yet, so today the
computer runs `tools/relay/relay.py`. Every swdload line below runs from the repository's root as
`uv run --no-project --with littlefs-python==0.19.0 python hardware/console-rp/bench/swdload.py …`,
through J3 and a debug probe ([bench/BRINGUP.md](bench/BRINGUP.md)).*

## At the bench, before it ships

The bench prepares the chip and never makes a key in it.

1. **`prepare-rp`, with a bench `secrets.py`** that holds only `ALLOW_LOCK = True`, made in a temp
   folder and never committed: `swdload.py --image build/prepare-rp-<sha> --secrets PATH`. On the
   screen it writes the chip's config (C1-C3, the quorum v1 table) and locks it. That lock is
   permanent ([docs/LOCKING.md](../../docs/LOCKING.md)). Then P4 reads and changes nothing: the
   config locked, the data zone open, slot 0 not sealed, no key in it, counter 0 at 0. It writes
   `prep-log.txt` and stops.
2. **`swdload.py --dump DIR`**, read only: `prep-log.txt` and the chip's config, to keep.
3. **`console-rp`, with no `secrets.py`:** `swdload.py --no-micropython --image
   build/console-rp-<sha>`. The board comes up on "Your key: No key yet: a new chip".

## The owner, on the device

The key is made in the chip, on the owner's press; only its public half ever leaves it. The caps are
■ (D0: back, reject), ● (D1: next) and ▲ (D2: do).

1. **▲ Make.** The chip makes the key in slot 0. Its blockie and owner address come up.
2. **■ New** makes another, **● Full** shows the address in full, and **▲ Choose** takes it.
3. **Keep is red: hold ▲ 3 s.** The console tests the key on fixed digests (five signatures), seals
   slot 0, writes the record, locks the data zone, checks the chip and writes `pin.json`, about 20 s.
   All of it is permanent. ■ Back before the hold changes nothing.
4. **"Your key: pinned": ▲ Start.** The console restarts, pinned to its chip.

What can stop it:
- **A restart between Make and Keep:** the key from before is replaced. Make is forced again, so a
  key put in while the data zone was open can't survive.
- **A restart during Keep:** after the seal, a red Finish (hold ▲ 3 s) locks the data zone; after
  the data lock, ▲ Check pins it. Either goes on only if the record (`keyflow.json`) matches.
- **"Not prepared"** (red): the chip was never set up at the bench. Nothing on it changed.
- **"Sealed elsewhere"** (red): its key was sealed, but not by this console. Nothing is locked or
  pinned.

## A Safe

1. **The Key page's QR** is `https://picoquorum.app/app/#/k/<the key>`. On a phone it opens the app's
   set-up page: a new Safe with this key and the owner's wallet, or this key added to a Safe
   ([docs/ONBOARDING.md](../../docs/ONBOARDING.md), The QR code).
2. **On the computer:** `python3 tools/relay/relay.py PORT --safes basesep:0xSAFE:Name`, with PORT
   the CH343P (`/dev/cu.usbmodem…` on a Mac). The console shows the Safe on a page of its own, then
   a page saying it replaces the Safes it watches. See each, then hold ▲. It writes `safes.json` and
   restarts.
3. **Then leave the relay running.** The console asks for the queue from its home screen. If the
   relay stops, it says "no relay: open the app".

## Signing

- A transaction in the queue comes up on home. Each page has to be seen (●). ▲ held 2 s signs, 3 s
  if any page is red. ■ rejects, one press.
- The console rebuilds the transaction's hash from what it showed, signs that, and posts the
  confirmation through the relay (AGENTS.md rule 1).
- A screen that only shows (Key, owners, device, recent, chip) goes back home after 2 minutes with
  no key press, so the console keeps asking.

## Loading a board that has a key

Never a plain load: it wipes `pin.json` and `keyflow.json`. Without them the console finds its chip
sealed by someone else and stops on "Sealed elsewhere", until the dumped files go back.

1. `swdload.py --dump DIR` (about 4 minutes; the console keeps running).
2. `swdload.py --no-micropython --image build/console-rp-<sha> --keep DIR`. It writes the whole
   filesystem, 24 pieces of 128 KB, in about 3 minutes, with the dumped files in it. The console
   doesn't run while it writes.

The counter goes up by one at each start: reading the public key counts as a use on a data-locked
608. J3's pogo contact can drop mid-write. swdload tries each piece five times, with pauses to press
the pins down between them. If a piece still fails, check that a small SWD read answers, and run
the same load again: the whole filesystem.

## Not done

- **The app's Device page as the relay** (`#/device`) is written and checked in Chromium against a
  fake console, but not yet on a board.
- **An update for an owner:** the USB-C reaches only the CH343P, so a new image needs J3 and SWD.
- **Frozen modules,** for more heap than the 70-80 KB free with the console running.
