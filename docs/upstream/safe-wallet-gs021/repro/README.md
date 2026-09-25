# Running the GS021 reproduction

`repro.mjs` shows Safe{Wallet}'s GS021 with a contract-owner confirmation, and the fix, on your
own machine. It needs about ten seconds and no keys or funds. Everything happens on a local Anvil
fork of Base Sepolia, with throwaway keys, and nothing is sent to a real chain.

## What you need

- **Node 20 or newer.** Check with `node --version`.
- **Foundry**, for `anvil`. Check with `~/.foundry/bin/anvil --version`, which should say 1.8.3. If
  it's missing: `curl -L https://foundry.paradigm.xyz | sh`, then `~/.foundry/bin/foundryup -i v1.8.3`.
  - The installer doesn't add Foundry to your `PATH`, so either use the full path as below, or run
    `export PATH="$HOME/.foundry/bin:$PATH"` in each terminal (or add it to `~/.zshrc`).
- **Internet**, for the fork's first reads from `https://sepolia.base.org`.

## Run it

**Terminal 1: the fork.** Leave it running.

```sh
~/.foundry/bin/anvil --fork-url https://sepolia.base.org --port 8547
```

It prints a banner and ends with `Listening on 127.0.0.1:8547`. Its test accounts aren't used.

**Terminal 2: the reproduction.**

```sh
cd ~/git/pico-quorum/docs/upstream/safe-wallet-gs021/repro
npm ci            # first time only: viem, @noble/curves and @safe-global/protocol-kit at the locked versions
node repro.mjs
```

## What you should see

```
fork of Base Sepolia at http://127.0.0.1:8547, block 47298253

2-of-2 EOA + passkey: Safe 1.5.0, 2-of-2; confirmations sorted by owner: EOA, contract
  current (createExistingTx) 450 bytes -> reverts GS021
  fixed (toSafeSignature)    450 bytes -> simulation OK
  executed with the fixed layout: ExecutionSuccess true, recipient +1000000000000 wei, logged signatures = fixed: true

3-of-3 passkey + EOA + passkey: Safe 1.5.0, 3-of-3; confirmations sorted by owner: contract, EOA, contract
  current (createExistingTx) 835 bytes -> reverts GS021
  fixed (toSafeSignature)    835 bytes -> simulation OK
  executed with the fixed layout: ExecutionSuccess true, recipient +1000000000000 wei, logged signatures = fixed: true

1-of-2 control: Safe 1.5.0, 1-of-2; confirmations sorted by owner: contract, EOA
  current (createExistingTx) 450 bytes -> simulation OK
  fixed (toSafeSignature)    450 bytes -> simulation OK
  executed with the fixed layout: ExecutionSuccess true, recipient +1000000000000 wei, logged signatures = fixed: true
```

Only the block number changes from run to run. How to read each line:

- **`current (createExistingTx)`** is the signatures laid out the way Safe{Wallet} does today:
  every confirmation added as a plain signature. With a threshold of 2 or 3, the Safe rejects them
  with GS021.
- **`fixed (toSafeSignature)`** is the same confirmations with the contract one added as a contract
  signature, the PR's fix. The simulation passes.
- **`executed with the fixed layout`** is the real `execTransaction` on the fork, checked three ways:
  - the Safe emitted `ExecutionSuccess`
  - the recipient received the 0.000001 ETH
  - the signature bytes the Safe logged are exactly the fixed layout
- **The 1-of-2 control** passes both ways, because a threshold of 1 only checks the first 65-byte
  slot. So the failure depends on a threshold of 2 or more.

## More

- **Run it again:** `node repro.mjs` restores the fork when it finishes, so it can run any number of
  times on the same anvil. Ctrl-C in terminal 1 stops the fork, and nothing is left behind.
- **Regenerate the unit-test fixtures:** `node repro.mjs --fixture` also prints a `FIXTURE {...}`
  line. The keys come from fixed seeds and the signatures are deterministic, so it matches the
  patch's test data byte for byte.
- **Another RPC:** `anvil --fork-url <your Base Sepolia RPC> --port 8547`. If the fork runs somewhere
  else, use `node repro.mjs --rpc http://127.0.0.1:<port>`.

**If something goes wrong:**
- `ECONNREFUSED 127.0.0.1:8547`: anvil isn't running, or it's on another port.
- `HTTP 429` from anvil: the public RPC is rate-limiting. Wait a moment, or use your own RPC.
- `createProxyWithNonce reverted`: an older copy of the script ran on this fork without cleaning
  up. Restart anvil.
