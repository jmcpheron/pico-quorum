# Operator runbook: a Trust M from the bag to a mainnet Safe owner

Each step that writes to a chip, or sends a transaction, says so. **Mainnet gas only after an
explicit yes.**

**The chip inventory** is local and gitignored:
- `chips/TRUSTM.md`: the TM1–TM10 table and each chip's detail
- `chips/TRUSTM-LOG.md`: the dated log

Update both after every step below.

## 0. Before you start

- [ ] **The firmware.** The board runs a committed console image, and `tools/fw verify` says so.
      `ALLOW_*` are False.
- [ ] **A backup of the board outside the repo.** Use `tools/fw backup`, then copy the folder
      somewhere else. It holds `secrets.py`.
- [ ] **For a fresh chip:** label the breakout with the next TM number in marker, and fill in its
      row.
- [ ] **Before T9 on any chip:** decide whether it freezes the spare key slots E0F2/E0F3
      (CONFIGURATION.md, "Still open").

## 1. The ceremony (on the device)

**Swap the chip.** USB unplugged, chip in, USB back.

**Start:**
```sh
tools/fw ceremony start                 # a fresh chip
tools/fw ceremony start --unpin         # a pinned chip that needs T9 (TM1)
tools/fw ceremony start --keep-open E0F2,E0F3   # if a second key per chip stays possible
```
- One `yes` covers the whole start. It does three things:
  - writes `ALLOW_LOCK` and `ALLOW_GENKEY`
  - unpins the chip, if asked
  - pushes the dual image (after a backup)
- The board restarts into the ceremony.
- It notes what it changed in `backups/<board>/ceremony.json`.

**On the board:** PROVISION (A, or press the knob). Then each step:

| Step | What | Gate |
|---|---|---|
| T1 | read-only checks: Infineon certificate, factory key, every object as it came | — |
| T2 | make the key (E0F1) | two 3 s holds (arm, then do) |
| T3–T4 | test signatures; the factory key binds the key | — |
| T5 | the owner address: **compare it with `getSigner` on the laptop** before T6 | — |
| T6 | write the record and binding | — |
| T7 | **seal** the key, record and binding. PERMANENT | two 3 s holds, and an explicit yes for this chip |
| T8 | check the seal | — |
| T9 | **freeze the spares**: PERMANENT, never termination | two 3 s holds, and an explicit yes for this chip |
| T10 | done | — |

A sacrificial chip goes first for anything not yet seen on silicon. T9 is the first such step.
Its results go into `docs/TRUSTM.md`.

**Finish:**
```sh
tools/fw ceremony finish
```
- One `yes` again. It does four things:
  - turns `ALLOW_*` off
  - pins the chip
  - pushes the console image
  - verifies, and compares the pins with what `start` noted
- Any line with `!!` needs attention before you go on.

## 2. The ceremony record

```sh
tools/fw attest                                            # read-only
tools/quorum verify docs/mainnet/attest/attest-<serial>.json --chain eth
```
- Commit the bundle. It holds public values only.
- Send co-signers the link and [COSIGNERS.md](COSIGNERS.md).

## 3. Enroll on Ethereum (gas: say yes first)

```sh
tools/quorum live key --usb                 # this chip's key into live.json
tools/quorum live enroll --chain eth        # deploys its signer proxy: about 110k gas, no funds moved
tools/quorum verify docs/mainnet/attest/attest-<serial>.json --chain eth    # now "deployed"
```
- `enroll` checks `getSigner` against the console's own owner address before it sends.
- The browser wallet page shows the transaction and its cost.

**The proxy must exist before the Pico's first confirmation.** The service checks the signature
with an `eth_call` to it.

## 4. Become an owner

1. Every co-signer runs `tools/quorum verify … --chain eth`. A new chip goes on only after they
   have.
2. Propose in the Safe web app:
   - `addOwnerWithThreshold(owner, 3)` to grow,
   - or `swapOwner(prev, old, owner)` to replace.
3. The current owners sign. If a contract signature is on it, execute with
   `tools/quorum live exec --chain eth <nonce>`.
4. Point the console at the Safe:
   `tools/quorum live pico --chain eth --safe <SAFE> --name "<name>"` (several chains:
   `--chain base,eth`).
5. Check the console: `tools/fw verify` shows the Safe as `ok, owner`.

## 5. The first approval

- [ ] **Something small first:** a tiny ETH send to an address you own. Proposed by a co-signer.
- [ ] **On the Pico:** every page, the right chain and Safe, the full recipient address, the
      amount. Then hold.
- [ ] **On the Safe:** the web app shows the Pico's confirmation, and the service accepted it.
- [ ] **Execute** with `live exec`. Record the tx link in `chips/TRUSTM-LOG.md` and
      `docs/LADDER.md`.

## 6. Running it

- **Keep the device where only you can reach it.**
  - It has no PIN, and the USB port can make it sign.
  - When you are away, unplug it and lock it up.
- **Check the console's Device screen now and then:**
  - the security events
  - the pin
  - the service
- **The log:** `tools/fw logs` copies `log.txt`. A "sec" rise of more than 1 on a signature is
  flagged there.
- **Firmware updates:**
  1. Commit.
  2. `tools/fw push console`, which backs up first and keeps `secrets.py`.
  3. `tools/fw verify`.
- **Never `ceremony start` with a pinned mainnet chip in the board.**

## 7. Lost, stolen, compromised, or out of your hands

1. Tell the co-signers at once, by voice. Point them to COSIGNERS.md section 4.
2. Propose `swapOwner` to a new owner, or `removeOwner` keeping the threshold at 3, from a
   different device. Three other owners sign. Execute.
3. Mark the chip **retired** in `chips/TRUSTM.md`, with the date and the transaction.
4. **Never reuse a retired chip as an owner.** Its sealed key can't be replaced.

## 8. Backups and records

| What | Where | Secret? |
|---|---|---|
| `backups/<board>/<UTC>/` | the board's files, including `secrets.py` (WiFi password, API key) | yes: keep a copy off this laptop, encrypted |
| `docs/mainnet/attest/` | each chip's ceremony record | no: commit it |
| `chips/TRUSTM*.md` | the inventory and log | not secret, but local |
| `tools/mock-tx-service/live.json` | keys, Safes, sends | no secrets; local |

The chip's key has no backup, and can't have one. **The Safe's other owners are the backup.**
