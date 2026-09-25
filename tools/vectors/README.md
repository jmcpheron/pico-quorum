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
