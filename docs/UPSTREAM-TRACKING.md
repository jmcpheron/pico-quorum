# Tracking upstream picowallet

PicoQuorum keeps picowallet's secure-element drivers and changes them as little as possible, so
their fixes can come across cleanly. This file is where the fork point, merges, and the files worth
watching get recorded.

## Where we are

| | commit | date |
|---|---|---|
| Last upstream commit in this repo | `87c717c` | 2026-09-13 |
| Our picowallet work on top (chip map, config fix, wiring) | through `35c744c` | 2026-09-19 |
| Upstream `main` last checked | `72539d5` | 2026-09-21 (checked 2026-09-24) |

Not merged yet: 20 upstream commits, including:

- **`firmware/trustm.py`**: OPTIGA Trust M driver (physical layer on GP4/GP5, IFX I2C link layer,
  APDU session, lifecycle / metadata / factory-cert reads, CalcSign, GetRandom). This is the
  Trust M option in `KICKOFF.md`.
- **`TrustMAttest.sol`**: proves on chain that a P-256 key lives in a genuine Trust M (the Infineon
  CA-signed factory cert checked with P256). This matters for the provisioning ceremony.
- **`atecc.py` config-table fix** (`cba49a2`, `521c5ff`, `187db86`): upstream's own fix for the
  shifted KeyConfig table that this fork found and fixed separately (`1526c95`, see
  `../UPSTREAM.md` and `../UPSTREAM-ISSUE.md`). Expect a conflict here and prefer upstream's
  table once it has been read back against a real chip.
- USB wallet (`usbwallet.py`, WebSerial), `CLEARSIGNING.md` research notes (ERC-7730 clear signing
  and more, relevant to the decoder).

## How to merge

```sh
git remote add upstream https://github.com/austintgriffith/picowallet   # once
git fetch upstream
git log --oneline 87c717c..upstream/main          # what is new
git diff 87c717c upstream/main -- firmware/atecc.py firmware/trustm.py firmware/keccak.py
git merge upstream/main                           # a merge commit, never a rebase
python3 test-vectors/run.py                       # must still pass
```

Then update the table above and add a line to the log below.

## Files to watch

`firmware/atecc.py`, `firmware/trustm.py`, `firmware/keccak.py`, `firmware/eip712.py`,
`app/packages/foundry/contracts/TrustMAttest.sol`, `SECURITY.md`, `CLEARSIGNING.md`.

## Log

- 2026-09-24: forked as PicoQuorum. Upstream checked at `72539d5`, nothing merged yet.
