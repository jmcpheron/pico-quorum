# The console in your browser: read it, check it, run your own copy

[The console page](https://picoquorum.app/console/) runs the console's firmware in
your browser, with your own passkey (Touch ID, Windows Hello, a phone, a security key) as its key.
It is one folder. It loads nothing from the rest of the site, and the firmware in it is the console
image a Pico runs, as plain files. So you can read all of it, check it against the release, and
sign from a copy on your own computer that changes only when you change it.

> **What it can't do.** The screen is drawn by your computer, and the passkey's prompt never shows
> the transaction. A copy you checked rules out "the site changed the page". It does nothing about
> malware on the computer. Keep passkey owners below the Safe's threshold
> ([EMU-WEB.md](../EMU-WEB.md#limits-to-say-out-loud)).

## What is in the folder

| | what | size |
|---|---|---|
| `firmware/` | The console image ([`firmware/manifest.json`](../../firmware/manifest.json)): the same files a Pico runs, in MicroPython. Together they hash to the release fingerprint. | about 11,000 lines, and 10 data files (fonts and TLS roots) |
| `shims/` | Python in place of the Pico's hardware: its pins, screen and Wi-Fi, and your passkey as its key ([`emu/core/shims/`](../../emu/core/shims/)). Only the ones the console uses: no virtual chips | about 630 lines |
| `console.js`, `worker.js`, `web/`, `core/`, `shared/`, `coi.js`, `sw.js` | The page's JavaScript: the buttons, your passkey, and the worker MicroPython runs in | about 1,100 lines |
| `vendor/micropython/` | MicroPython 1.26 for WebAssembly | about 520 KB |
| `index.html`, `console.css`, `fonts/`, `brand/` | The page's words and looks | |
| `boot.json` | The release fingerprint, a `build.py` naming the release, and the files to boot | |
| `SHA256SUMS`, `BUILD.json` | The SHA-256 of every file | |

The page shows the exact counts; `node emu/build.mjs` works them out as it writes the folder.

MicroPython's WebAssembly is the one part built elsewhere, by the MicroPython project. It comes from
npm, pinned by its hash in [`emu/package-lock.json`](../../emu/package-lock.json), so everyone gets
the same bytes. Everything else is source you can read as it is.

**The page can reach one thing outside its folder:** Safe's transaction service
([`quorum_cfg.py`](../../firmware/quorum_cfg.py) `"services"`: today `https://api.safe.global`, for
every chain). That isn't just what the code happens to do. The page's Content-Security-Policy allows
that host and nothing else, and `sw.js` sends the same policy as a header, so it also binds the
worker that makes the firmware's calls. The browser refuses any other request. You can read the
whole rule in one line of `index.html`.

[`emu/e2e-static.mjs`](../../emu/e2e-static.mjs) checks in Chromium, on every push:
- the page asks for nothing outside its folder, and any other host is refused, in the page and in
  its worker;
- the folder runs on its own;
- it signs a transaction through its own buttons, against a stand-in for Safe's service that checks
  the signature the way the Safe does.

## Where to start reading

The path from Safe's queue to your signature, by file and function:

| step | where |
|---|---|
| Ask Safe's service for the Safe and its queue | `firmware/txservice.py` (`Service`, `safe_info`, `pending`), `firmware/policy.py` (`service_url`, `valid_info`) |
| Hash each transaction itself, from the fields it shows | `firmware/safe_tx.py` (`from_service`, `safe_tx_hash`), `firmware/quorum.py` `entry` |
| Say what it does, in red when it changes who controls the Safe | `firmware/decode.py` (`review`) |
| Sign only after every page is seen and A is held | `firmware/quorum.py` (`can_sign`, `press_sign`, `hold_tick`) |
| Ask your passkey | `firmware/quorum.py` `sign_it` → `shims/passkey.py` `PasskeySigner.assertion` → `worker.js` `askPage` → `web/browser.mjs` `passkeyGet`: the one-time note, then WebAuthn over the hash the console computed, checked against your key before the console gets it |
| Pack it and post it | `firmware/webauthn.py` (`contract_signature`), `firmware/quorum.py` `post`, `firmware/txservice.py` `confirm` |
| Your owner address | `firmware/webauthn.py` `owner_address`; the page's `web/browser.mjs` `passkeyOwner` works out the same one |

Some of `firmware/` never runs in a browser. It stays so that the folder is the console image and
hashes to the release a Pico runs:
- the chip drivers (`atecc.py`, `chipcfg.py`, `trustm.py`, `trustm_q.py`, `tmcfg.py`): your
  passkey is the key;
- `boot.py` and `main_console.py`: the page starts the console itself;
- Wi-Fi setup (`wifisetup.py`, `qrcode.py`);
- the knob and the small screen of other boards (`knob.py`, `quorum_ui_s.py`), and the boot art
  (`bootart.py`);
- `vhttp.py` and the three TLS roots (`ca_*.bin`): your browser does TLS.

## 1. Save a copy

`SHA256SUMS` lists every file, in the format `sha256sum` reads:

```sh
mkdir pq-console && cd pq-console
site=https://picoquorum.app/console
curl -fsSO "$site/SHA256SUMS" && curl -fsSO "$site/BUILD.json"
cut -c67- SHA256SUMS | while read -r f; do curl -fsS --create-dirs -o "$f" "$site/$f"; done
sha256sum -c SHA256SUMS            # macOS: shasum -a 256 -c SHA256SUMS
```

Every line should end in `OK`. There is no build step: these are the files that run.

That shows the files match the list, but the list came from the same site. The next two steps tie
it to something else.

## 2. Hold it up to the README

A release fingerprint is one SHA-256 over an image's files: a line `name \0 sha256(file) \n` for
each, sorted by name ([`tools/releases/fingerprint.mjs`](../../tools/releases/fingerprint.mjs)).
`firmware/` is exactly the console image, so:

```sh
cd firmware
for f in $(LC_ALL=C ls); do printf '%s\0%s\n' "$f" "$(sha256sum "$f" | cut -c1-64)"; done | sha256sum
# macOS: shasum -a 256 in both places
```

That prints the **console** fingerprint in [the README's build table](../../README.md#the-build-youre-looking-at).
Its first 8 digits and its blockie are what the page shows under its title, and what a Pico
running the same release shows on its Device screen. The page works it out again in your browser,
over the files it boots, before it runs them.

Once releases are tagged, the app's [Releases page](https://picoquorum.app/app/#/releases)
lists each one's fingerprint, and `docs/releases/<version>.json` the SHA-256 of each file in it.

## 3. Check it against the source

With a checkout of the repository:

```sh
git clone https://github.com/jmcpheron/pico-quorum && cd pico-quorum
cd emu && npm ci && node build.mjs && cd ..
git status --porcelain docs/console      # prints nothing: the folder is what this source makes
diff -r docs/console ../pq-console       # your copy from step 1: no differences
```

- **Reproducible.** `npm ci` installs exactly what the lockfile pins. CI makes the same rebuild on
  every push and fails if it differs from what is committed.
- **Watched from outside.** After every deploy and every six hours,
  [`site-check.yml`](../../.github/workflows/site-check.yml) compares each file Pages serves with
  the commit it deployed. By hand: `tools/release check-site`.
- **Signed releases.** For a release, check its tag before you rebuild:
  `git -c gpg.ssh.allowedSignersFile=.github/allowed_signers tag -v fw-<version>`. The release's
  manifest names the SHA-256 of `console/BUILD.json` ([RELEASES.md](../RELEASES.md)).

## 4. Run your copy

```sh
cd pq-console
python3 -m http.server 8000 --bind 127.0.0.1
```

Open **http://localhost:8000/**: `localhost`, not `127.0.0.1`, because passkeys need a name, not
an address. The first visit reloads once: `sw.js` turns on the cross-origin isolation the console
needs, so any static server works, with no headers of its own.

A site can send a different page on any visit, and a page can't vouch for itself
([EMU-WEB.md](../EMU-WEB.md#where-the-code-comes-from)). Your copy changes only when you replace
its files. For a new release, save it next to the old one, check it the same way, and
`diff -r old new` shows exactly what changed: the firmware is plain text.

## 5. Its own passkey

A passkey belongs to the site that made it: the host name, whatever the port. The console page
makes yours for the host it is on.

- **Made on the site** (`picoquorum.app`): any page on that host can ask it to sign, behind
  your fingerprint. That includes every version of this page the site serves from now on.
- **Made on your copy** (`localhost`): only pages on `localhost` can. Nothing the site serves later
  can, so the code you checked is the code that can use the key.

**The same Safe owner, either way.** The owner address follows from the passkey's public key alone.
Safe's passkey signer doesn't look at the site, and
[`tools/vectors/passkey.mjs`](../../tools/vectors/passkey.mjs) showed a `localhost` passkey's
signature valid on Base Sepolia, Base and Ethereum. Your copy shows its owner address: share its
deploy link to any wallet to deploy its signer, and have a wallet that owns the Safe propose adding
it, as on the site.

**But a different passkey.** One made on your copy is not the one made on the site, so it is a
different owner. Decide where you will sign before you add the owner: moving later is an owner swap
on the Safe.

Mind these:
- **`localhost` is every port.** Anything else you serve on `localhost` could ask for the passkey,
  behind your fingerprint. Run only this there, and stop the server when you're done.
- **Your copy has its own storage.** Safes saved in the app on the site aren't there: add them on
  the console's screen. Its links to the app go to the app on the site and carry only public things:
  a public key in the deploy link, an owner address and a Safe in Add owner.
- **No Safe API key, unless you set one.** The console works without one and polls Safe's service
  every 60 s instead of 20 s ([NETWORKS.md](NETWORKS.md)).
