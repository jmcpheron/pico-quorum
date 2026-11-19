# console-rp's customer image: the discussions

*Started 2026-11-14. The questions about the image an owner gets (`console-rp`, pull request #113),
each with where it stands: open, decided, or set aside. A decided one says when, why, and the
commit that did it. What was tried on the boards is in
[docs/USB-LINK.md](../../docs/USB-LINK.md#the-relay-console-rp), and how a board is set up in
[SETUP.md](SETUP.md).*

To add one: a bold line with the question, then what is there today, the choices, and what it
needs (a test, a yes, a release). When it is settled, move it to Decided with the date and the
commit.

## Open

- **An update for an owner.** Today a new image needs J3 and an SWD probe, at the bench
  ([SETUP.md](SETUP.md#not-done)). The USB-C reaches only the CH343P, and rev B keeps it that way
  ([REV-B-PLAN-2026-11-05.md](REV-B-PLAN-2026-11-05.md)). The choices: boards go back to the bench
  for updates, or a signed update over the link. The second is a new way in for code, not designed
  yet, and needs a yes before any work.
- **Frozen modules:** the console's code built into our own MicroPython. It would give more heap
  than the 55 to 60 KB free on home with two Safes, and secure boot means nothing without it
  ([PLAN-2026-11-04.md](PLAN-2026-11-04.md#the-rp2350s-own-locks)). Needs a yes.
- **The RP2350's own locks:** secure boot, and SWD locked after loading. Both are one-time. The
  plan says to try both on board #2 first. Neither has been tried. The plan has the first 20
  shipping without them, as development boards.
- **A review of the own-key gate** by someone else: `signer.own_key_step` and `firmware/keyflow.py`,
  the holds that allow GenKey, the seal and the data lock. Not done.
- **Where the gate is written down.** AGENTS.md rule 2 names it, and SETUP.md walks an owner
  through it. `docs/PROVISIONING.md` and `docs/BRANDED-KEYS.md` don't mention it yet.
- **When a memory restart counts.** A whole poll of either Safe starts the count of memory failures
  again. So a big queue that keeps failing while a small one reads never leads to a restart. The
  proposed fix: start again only when every Safe's last poll was whole. Not done.
- **What `relay.py` does when the port goes away** (an unplug). From its code it doesn't reconnect.
  Not tried.
- **The S3's key pick words.** console-rp says Seal and Replace since 0f908638. `keypick_s.py`, on
  the S3 boards, still says Make, New and Keep. Carry the words over, or leave it.
- **Board #1:** console-rp c77d4f85, a key made and not sealed. Its firmware is too old to answer
  the relay. A plain load is safe (no sealed key). The plan's stress test, stage 2, would seal it,
  enroll it on Base Sepolia and make 20 signatures. Each permanent step gets its own yes, and so
  does any testnet spend.
- **Branding for the first 20.** The plan has them unbranded, each owner making their own key, as
  now. Key 0000, the brand's root, doesn't exist
  ([PLAN-2026-11-04.md](PLAN-2026-11-04.md#the-brands-root-key)).
- **picoquorum.dev**, printed on the back, must reach the site and the source before boards ship.
  Today the site is picoquorum.app ([README.md](README.md#open)).
- **A release and the merge.** The last build is 0f908638, release f24d·22db, with no tag. Pull
  request #113 merged, then `tools/release` ([docs/RELEASES.md](../../docs/RELEASES.md)).

## Decided

- **No radio. The console asks over the USB-C, and a relay on the computer fetches** (2026-11-04,
  0c33ac2f). The RP2350A has none, and the USB-C reaches only the CH343P. The relay forwards only
  to `quorum_cfg.py`'s services and adds the API key. The console rebuilds every hash, so AGENTS.md
  rule 1 stands as written.
- **Two relays:** `tools/relay/relay.py` for the bench, with logs and hostile modes (b7a9632e), and
  the app's Device page for an owner (8074db25, 2026-11-10).
- **The console's log goes out over the link,** one way, as `{"t":"log"}`. There is no REPL to read
  it from.
- **The owner makes the key on the device.** The bench only prepares the chip: C1-C3, then a
  read-only check that no key is there (`prepare-rp`, 53f28883). The bench never makes a key.
- **The holds are the permission** for GenKey, the seal and the data lock. That holds in the
  console-rp image only, and on a quorum v1 chip the bench prepared (a0b07878). AGENTS.md rule 2
  names it (5cd69f80). A config write or lock is never in the image.
- **Only the key flow writes `pin.json`,** when the key is sealed. No request over the link can.
- **The CRT look from the start** (9927a2fb). A tear when something arrives or changes; a lock when
  the console worked it out and checked it. Nothing moves on a page that asks for a decision, and a
  press ends any effect, so Reject stays one press. Three glitches were compared on the bench and
  two kept (73bcb1d5). The footer draws the case's caps: ■ out, ● next, ▲ do.
- **One screen buffer, no second frame for the effects** (5049f2c6). 70 KB was free with the
  console running, and a second frame is 64.8 KB.
- **The key pick's words: Seal and Replace** (0f908638, 2026-11-12). "Each try replaces the last."
  It reads as one key, which each try replaces. console-rp only.
- **The Device page in tabs** (e1767250), and one list of Safes, the console's and the browser's
  (8fe87da8), after the first version proved confusing. Its words: key (in the chip), signer (its address,
  which a Safe lists), Safes.
- **A queue too long to read at once is read a few at a time.** A transaction too long even alone
  is red, "Too big to check", and can't be signed (dd82e30a, 2026-11-10).
- **A refusal is for the fields it was given,** not the hash (a30640ce). Found with the forged
  queue: the real copy stayed refused until a restart.
- **A screen that only shows goes home after 2 minutes alone** (0d617601), because the console
  polls only from home, its start and its saver. Left on the Key page it never polled.
- **No chip at the start: clock the bus free and look again,** and log why (f95d12fd,
  2026-11-11). One start in 100 on board #2 found no chip.
- **The signing room is set aside at the start** (9b790f9a, 8c33db6c). The chip is asked only when
  there is room to send what it signs. Found when nine signatures in a row ran out of memory.
- **A restart for memory only when real work fails** (d60dfb40, 2026-11-12): 3 failures with no
  whole poll between. Looking for 2 KB in one piece only logs. It had restarted board #2 four times
  while idle.
- **A board with a key is loaded with its files kept:** a dump right before, then `--keep`
  (e43cc4b2). A plain load wipes `pin.json`
  ([SETUP.md](SETUP.md#loading-a-board-that-has-a-key)).

## Set aside

- **Parsing an answer once** (a change to the link's protocol). Not needed since 862fba4f reads an
  answer's body where it lies.
- **A switchable USB hub** (`uhubctl`) for unplugs. The 20 unplugs were done by hand.
