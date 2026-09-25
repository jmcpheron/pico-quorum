# The simulated Safe (`tools/quorum`)

A stand-in for Safe's transaction service, so the console can be built and tested before there
is a chain or a Safe contract to talk to.

- **The console's endpoints.** It answers the ones the console uses, at the real service's paths
  and in its shapes:
  - `GET /api/v1/safes/{safe}/`
  - `GET /api/v2/safes/{safe}/multisig-transactions/`
  - `POST /api/v1/multisig-transactions/{hash}/confirmations/`

  The console's code (`firmware/txservice.py`) should need only a URL change to talk to
  `api.safe.global`.
- **The Safe.** It is `firmware/quorum_cfg.py`'s: FAMILY SAFE on chain 31337, 2 of 3.
  - ALICE and BOB are simulated. They are anvil's test accounts 1 and 2, and they sign real ECDSA.
  - The third owner is whichever console announces its P-256 key on `/sim/device`.
- **Confirmations** are checked the way the Safe would check them, against viem's hash of the
  fields:
  - 65 bytes: ECDSA.
  - 64 bytes: P-256 r‖s from a registered console.

  A signature over a hash the service lied about is caught and logged as blind signing.
- **Execution.** At threshold the transaction "executes": the nonce moves on, and owner and
  threshold changes take effect.

```sh
tools/quorum serve            # port 8787 (QUORUM_PORT), state in state.json (QUORUM_STATE); dashboard at /
tools/quorum scenarios        # the stories: sends, a batch, red ones, a lying service, a conflict
tools/quorum demo             # fresh Safe with the standard queue
tools/quorum propose refund --by bob
tools/quorum confirm 2 --as alice
tools/quorum status | log
tools/quorum shots [story..]  # docs/quorum-ui/shots, from the emulator (own mock on 8799)
node tools/mock-tx-service/test.mjs
```

`emu-chip.json` is a virtual ATECC608 with a throwaway key in slot 0. The screenshots use it, so
the same key shows in every picture. It is not a real key.
