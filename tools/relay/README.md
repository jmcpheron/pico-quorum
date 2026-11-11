# The relay (`tools/relay`)

console-rp has no radio. Its way out is the link on UART1, through the CH343P to the USB-C
(`firmware/link.py`). The console asks, one JSON line at a time; the relay on the computer answers.
`relay.py` is the bench's relay. The app's Device page will be the customer's.

```sh
python3 tools/relay/relay.py /dev/cu.usbmodem5CF90874511            # the board's CH343P
python3 tools/relay/relay.py PORT --safes basesep:0xSAFE:Test       # send the safes ask; hold D2 on the device
python3 tools/relay/relay.py PORT --hostile stall,dup,forge-queue --rate 0.05 --seed 1
python3 tools/relay/relay_test.py                                   # no board, no network
```

Python's standard library only. The serial port is opened with termios, at 460800 (on macOS through
`IOSSIOSPEED`). `--tcp HOST:PORT` takes a socket instead.

## What it forwards

Only what `firmware/txservice.py` asks, and only under a base in `firmware/quorum_cfg.py`'s
`"services"`. The URL rules are `link.pinned`'s: plain ASCII, no `..`, `@`, `#` or `\`. Then the path
must be one of:
- `GET /api/v1/safes/{safe}/`
- `GET /api/v2/safes/{safe}/multisig-transactions/?executed=false&nonce__gte=N&ordering=nonce&limit=N`,
  maybe with `&offset=N`: the queue a few at a time, when it is too long for one answer
- `POST /api/v1/multisig-transactions/{hash}/confirmations/` with `{"signature": "0x…"}` and nothing
  else, at most 4 KB

Anything else is answered with status 0, and nothing goes out. `--allow-base http://127.0.0.1:PORT`
adds the laptop's mock (`tools/mock-tx-service`) and its `/sim` endpoints. The console accepts that
base only on a development load: without build.py, `link.bases` adds `secrets.QUORUM_URL`.

An answer longer than hello's `link.max` goes back as status 0, "answer too big". The service gets
12 s; the console waits 15.

## The API key

`SAFE_API_KEY`, from the environment or from `.env` at the repository's root. It goes on requests to
`api.safe.global` only. It is not written to a log and not sent down the link: the console has no key.

## Logs

One folder for each run, `hardware/console-rp/bench/runs/<when>-<serial>/` (gitignored), one JSON
object a line:
- `relay.jsonl`: each request with its path, status, bytes, upstream and total ms, and the
  first 16 hex digits of the body's SHA-256; each refusal and why; noise; each fault and what the
  console should do with it.
- `console.jsonl`: the console's log lines (`{"t":"log"}`).
- `status.jsonl`: the console's status every `--status-s` (60): state, chip, link counts, heap free.

## Hostile modes

`--hostile` does one of these, at random, to a share `--rate` of the answers. Each should end refused
or dropped on the console, never signed.

| fault | what the console should do |
|---|---|
| `garbage` | drop four junk lines (counted), use the answer after them |
| `overlong` | drop a line past its buffer to its newline, use the answer after it |
| `unsolicited`, `wrong-id` | drop an answer under another id, use the right one |
| `dup` | use the first of two answers |
| `late` | time out; drop it when it comes later |
| `stall` | time out; the poll fails |
| `truncate`, `nested` | the poll fails |
| `forge-queue` | REFUSED: the value changed, the hash kept |
| `chatter` | drop the noise around the answer |
| `big` | read the queue a few at a time; its first transaction, padded past the line, refused as too big |
| `lose-post` | time out on the confirmation: "Not sent", kept to send again (▲ on that screen, or after a restart) |

`stall`, `late`, `truncate`, `nested`, `forge-queue` and `big` are done to GETs only, `lose-post` to
POSTs only.
