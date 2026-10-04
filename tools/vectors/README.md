# tools/vectors

Generates [`../../test-vectors/safe_tx.json`](../../test-vectors/safe_tx.json) with viem, which
shares no code with `firmware/safe_tx.py`.

```sh
cd tools/vectors
npm install
node fetch-real.mjs   # optional: refresh real-safe-txs.json from Safe's transaction service
npm run gen           # rewrite ../../test-vectors/safe_tx.json
```

`gen.mjs` refuses to write if viem's hash of a real transaction differs from the `safeTxHash`
that Safe's service published.

`passkey.mjs` (`npm run passkey`) checks that a real browser passkey can be a PicoQuorum owner: Chromium
signs a safeTxHash with a virtual platform authenticator, and the deployed passkey factory on Base
Sepolia, Base and Ethereum must accept it packed as `firmware/webauthn.py` packs the chip's. Read only;
writes nothing. See [`docs/EMU-WEB.md`](../../docs/EMU-WEB.md).
