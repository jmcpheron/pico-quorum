# Instructions for AI coding agents

PicoQuorum is a console that is one owner of a Safe multisig: it shows what a transaction does,
works out its hash itself, and has a key that can't leak sign only that hash. The README says how
the pieces fit; read it, and the doc for the part you are changing, before you change it.

Do what was asked and no more. Keep changes small and plain, like the code around them. Don't add a
dependency, a network call or a new way to sign without asking first.

## Never weaken these

1. **The console signs only the hash it worked out.**
   - The key signs in one place, `quorum.sign_it` (`firmware/quorum.py`), over the Safe transaction
     hash rebuilt from the fields on the screen (`firmware/safe_tx.py`).
   - It never signs a hash or digest that Safe's service, the app or a page hands it.
   - Every page is seen and Sign is held before it signs. Red pages stay red, and Reject stays one
     easy press.
   - `test-vectors/manifest.mjs` checks the signing site, and `test-vectors/run-console.mjs` the
     refusals.
2. **The console image is exactly what it imports.**
   - `firmware/manifest.json` lists each image. Nothing in the console image may change the chip
     (genkey, lock, write); `test-vectors/manifest.mjs` checks both.
   - A firmware change moves the release fingerprint. The README's build table
     (`node tools/releases/badge.mjs`) and the console page are refreshed when a release is cut;
     between releases CI only warns that they're behind.
3. **Keys stay in their chips, and locks are permanent.**
   - Never add a command that reads a private key out, or that signs an arbitrary digest.
   - An ATECC608's locks can't be undone (`docs/LOCKING.md`). Don't provision, lock, run a key
     ceremony, or write to a board (`tools/fw push`, `tools/fw ceremony`, `tools/emu ship`,
     `tools/emu flash`) unless the person asked for exactly that.
4. **The console page is one folder that holds everything it runs** (`docs/console/`, built from
   `emu/console/` by `emu/build.mjs`).
   - It loads nothing from the rest of the site.
   - Its Content-Security-Policy allows the folder and the hosts of `quorum_cfg.py`'s `"services"`,
     nothing else. `sw.js` sends the same policy as a header, so it binds the worker too.
   - No inline scripts or styles.
   - The visitor's passkey is its only key: no software key, no virtual chips.
   - Its `firmware/` is the whole console image, so it hashes to the release fingerprint.
   - `emu/e2e-static.mjs` checks all of this in Chromium, signing included.
5. **The app holds no key.** It checks every confirmation itself.
   - It draws untrusted text (anything from Safe's service, a chain or a link) with `textContent`.
   - Its viem client keeps `ccipRead: false` (`web/src/safe.mjs`).
6. **`docs/` holds built files: never edit them by hand.**
   - `cd web && npm ci && npm run build` writes `docs/app/`, `docs/index.html` and `docs/home.css`.
   - `cd emu && npm ci && node build.mjs` writes `docs/console/` and `docs/emu/`, at a release.
   - Commit what they write. CI rebuilds both: the app's `docs/` fails on any difference, the
     console's only warns. And
     `.github/workflows/site-check.yml` compares what Pages serves with the commit.
   - `docs/releases/<version>.json` never changes after its tag.
7. **No secrets in the repository**, nor in tests, logs, screenshots or pull requests.
   - `firmware/secrets.py`, `.env` and board backups (`backups/`) stay out; `.gitignore` lists them.
   - Use the emulator's test keys and disposable testnet wallets, never a real key, seed phrase or
     API key.
8. **The supply chain stays pinned.**
   - Each package (`emu/`, `web/`, `tools/mock-tx-service/`, `tools/vectors/`) pins exact versions,
     and its lockfile pins every package by hash.
   - Install with `npm ci`, never `npm install`. Its `.npmrc` turns install scripts off.
   - GitHub Actions are pinned by commit, and each job gets the least permissions it needs.
9. **Releases are SSH-signed tags** made by `tools/release` (`docs/RELEASES.md`). Don't create, move
   or delete `fw-*` tags.

## Before you push

Run what CI runs for the parts you changed (`.github/workflows/ci.yml`):

```sh
python3 test-vectors/run.py && python3 test-vectors/fingerprint_test.py    # the Safe hash on CPython
(cd emu && npm ci)
node test-vectors/run-micropython.mjs && node test-vectors/manifest.mjs    # MicroPython, the images
node test-vectors/run-console.mjs                                          # the console's screens, refusals, signing
(cd tools/mock-tx-service && npm ci)
(cd web && npm ci && npm test && npm run build && npm run e2e)             # the app
(cd emu && node build.mjs && node e2e-static.mjs)                          # the console page, in Chromium
node tools/releases/site-test.mjs
```

The browser checks need Chromium: `PQ_CHROMIUM=/path/to/chrome` if playwright-core has none of its
own. After the builds, `git status`: `docs/` changes only if you changed what it is built from.

Say exactly what ran, what didn't, and what you assumed. Don't call a change secure or audited.

## Writing

The docs use short sentences and plain words, and say what was checked and how. Match them, and
keep comments as dense as the code around them.
