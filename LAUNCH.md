# Launch: the short-term list

What has to happen before PicoQuorum launches on its own domain, in order. It is a working list:
tick items as they land, and fold what's left into [docs/STATUS.md](docs/STATUS.md) after launch.
The plan behind each section is in the doc it links. Addresses here are public and already in
STATUS.md. Never put a seed phrase, a private key or an API key in this file.

*Written 2026-10-06 from a read of the repo; the line "today" in each section is what was found.*

## 1. The domain: picoquorum.app, before any passkey holds value

Today: the site is `jmcpheron.github.io/pico-quorum/`. There is no `docs/CNAME`, and DNS is
untouched. A passkey belongs to the host that made it (`location.hostname` in
`emu/web/browser.mjs`), so the move comes first. It also comes before the first release
manifest, which hashes the web builds.

- [ ] Verify picoquorum.app for GitHub Pages (account Settings → Pages). It asks for a TXT record at
      the registrar.
- [ ] DNS for picoquorum.app at the registrar. Check the values against GitHub's docs on the day.
  - [ ] the apex A and AAAA records to GitHub Pages;
  - [ ] `www` as a CNAME to `jmcpheron.github.io`;
  - [ ] if there's a CAA record, it allows Let's Encrypt.
- [ ] One pull request moves the site:
  - [ ] `docs/CNAME` holding `picoquorum.app`.
  - [ ] `SITE` in `tools/releases/site.mjs`. It fetches with `redirect: "error"`, so the site check
        fails every run once github.io redirects.
  - [ ] `SITE_APP` in `emu/console/console.js`, the app link for a copy run on localhost.
  - [ ] `emu/e2e-static.mjs` serves at `/`, not `/pico-quorum/`.
  - [ ] `node emu/build.mjs`, and commit what it writes.
  - [ ] The prose: README, [BROWSER.md](docs/guide/BROWSER.md), [EMU-WEB.md](docs/EMU-WEB.md),
        `emu/README.md`, STATUS.md and GOVERNANCE.md. BROWSER.md's `curl` step doesn't follow
        redirects.
- [ ] Set the custom domain, wait for the certificate, then tick Enforce HTTPS. Expect one failed
      site check in that gap.
- [ ] picoquorum.com, .org and .dev: the registrar's 301 forwarding to `https://picoquorum.app`. They
      never serve the site, or passkeys split. .dev is HSTS-preloaded like .app, so check that its
      forward answers over HTTPS.
- [ ] From a fresh browser profile, open the home page, the app, the console and the guide. Then the
      site-check workflow is green, and `tools/release check-site` passes.
- [ ] Passkeys made on github.io stop working there. Find out whether the unlabelled signer
      `0x6e5D…E933` on the Base Sepolia 3-of-6 is one. Label it, or remove it.

## 2. picoquorum.eth

Today: the owner is the hardware wallet `0x682D…a9f3`. The name is unwrapped, `addr` is the
hardware wallet, and it expires 2031-10-06. The plan is in [GOVERNANCE.md](docs/GOVERNANCE.md#ens).

- [ ] Now, from the hardware wallet: extend the registration toward 10 years.
- [ ] The seed phrase stays offline, out of the repo, chats and screenshots.
- [ ] After the project Safe exists (section 3):
  - [ ] make the Safe the name's owner and manager;
  - [ ] set the records in one `multicall`: `addr` for Ethereum and for Base (`0x80002105`), `url`
        `https://picoquorum.app`, and `text org.picoquorum.release`.
- [ ] Firmware: decode the Public Resolver's `setText`, `setAddr`, `setContenthash` and `multicall`.
      Without it, the console shows the handover as a red page it can't read. Either build it, or
      accept that red page knowingly.
- [ ] Decide on `picoquorum.eth.limo` and its contenthash. A console served from that host makes
      different passkeys. [EMU-WEB.md](docs/EMU-WEB.md) and GOVERNANCE.md disagree on this today.

## 3. The project Safe and the first release

Today: `quorum_cfg.py` `"project"` is empty. `.github/allowed_signers` holds no key, so
`release.yml` refuses any new tag. `docs/releases/index.json` lists no release. The steps are in
[GOVERNANCE.md](docs/GOVERNANCE.md#first-steps) and [RELEASES.md](docs/RELEASES.md).

- [ ] Make the project passkey on picoquorum.app, after section 1.
- [ ] Create the 2-of-3 Safe on Ethereum and on Base, at one address. Its owners are the Trust M
      key, the hardware wallet and the passkey.
- [ ] Deploy each P-256 owner's signer proxy on both chains.
- [ ] Commit the Safe's address as `quorum_cfg.py` `"project"`.
- [ ] Add an SSH signing key to `.github/allowed_signers`, and set the rulesets in RELEASES.md.
- [ ] Run `tools/release manifest`, then `check`, then `tag --push`. Then approve the release from
      the consoles.
- [ ] The repo is public now:
  - [ ] add `actions/attest-build-provenance` to `release.yml`, pinned by commit;
  - [ ] drop the comment there that says the repo is private.

## 4. The browser console and the app

Today: the console page ships no Safe. It reads the Safes saved in the browser (`pq.safes` in
localStorage), which it shares with the app on the same site. With none saved, it opens on "Add a
Safe to watch". It boots into the Base Sepolia test Safe `0xEDED…0a43` only because that browser
saved it on github.io. picoquorum.app starts with empty storage.

- [ ] Nothing to remove from the console. On a fresh profile at picoquorum.app, confirm it opens
      on "Add a Safe to watch".
- [ ] The app (`web/src/main.mjs`): drop the `DEMO` link to the test Safe, or label it plainly as
      testnet.
- [ ] The app (`web/src/safe.mjs`): put `base` first in `CHAINS`, so "Open a Safe" defaults to Base,
      not Base Sepolia. Fix the address placeholder to match.
- [ ] Update `web/test.mjs` and `web/e2e.mjs`, then rebuild `docs/app`.

## 5. Firmware ready for production

Today: the console image boots only into the Safe console, signs only with the pinned chip, checks
TLS against pinned roots, and shows "No Safe" rather than falling back to the laptop's test Safe.
What's left:

- [ ] `firmware/secrets.example.py` has `QUORUM_URL = "http://<mac-lan-ip>:8787"` uncommented. A
      board set up by copying the example as it stands sends every Safe to that address over plain
      HTTP. Comment it out.
- [ ] Decide whether production images refuse `QUORUM_URL` and a per-Safe `url`, or at least
      `http://` (`firmware/quorum.py`). That is a firmware change:
  - [ ] bump the version;
  - [ ] run `node tools/releases/badge.mjs`;
  - [ ] rebuild the console page.
- [ ] Rung 3 on Base ([LADDER.md](docs/LADDER.md)):
  - [ ] fund the Base Safe;
  - [ ] `tools/quorum live pico --chain base`;
  - [ ] one approval on Base;
  - [ ] one approval from another Wi-Fi;
  - [ ] copy the board backup outside the repo.
- [ ] Before consoles go to other people, decide what to close. [SECURITY.md](docs/SECURITY.md)
      lists what is still open to whoever holds the board: the USB REPL, no chip PIN, no secure
      boot. Secure boot burns OTP, so try it on a spare board only.
- [ ] Optional: the leftover "picowallet" strings: `chipmap.py` `NOTE_TEXT`, and the test-signature
      digest in the ceremony. The credits to picowallet stay.

## 6. Chips: provisioning fresh ATECC608s the PicoQuorum way (needed soon)

Today:
- **The decision.** Shipped keys are ATECC608 (key-c carries a 608C); the Trust M is for the
  project Safe's key. STATUS.md still lists this as open.
- **The chip's job.** Every fresh chip gets quorum v1 through the C1–C10 ceremony
  ([PROVISIONING.md](docs/PROVISIONING.md)), proven on chip #2. That is one sealed P-256 key in
  slot 0, slots 1–15 dead, and a use counter.
- **The only brand on the chip.** C8 writes a 64-byte record into OTP, and C9 freezes it. It starts
  with `PQ`, and it is full. Slots 1–15 can never be read, so nothing readable can be branded into
  them under quorum v1.
- **What isn't written down yet.** The repo has nothing on a quorum (a group of chips), a quorum ID
  or a Merkle tree.
- **The list there is.** The off-chain [key registry](docs/registry/README.md) covers Trust M
  only, and `tools/fw attest` refuses an ATECC608.

To do:

- [ ] STATUS.md: close the open decision on the production chip, as above.
- [ ] Before sealing chip #3, decide the brand and quorum record. Either:
  - a version 2 OTP record that makes room for a quorum ID; or
  - a quorum v2 table with one readable slot, written before the data lock. For example, slot 8
    could hold "PicoQuorum", the quorum ID and the record.

  Either way it is a new profile: decode it with `tools/check_config`, run
  `node test-vectors/run-ceremony.mjs`, and run it on a spare chip first. Locks are permanent
  ([LOCKING.md](docs/LOCKING.md)).
- [ ] Write the membership design down, in a short doc:
  - [ ] what a leaf is: the owner address, the serial, the public-key hash;
  - [ ] who adds a member: the project Safe;
  - [ ] where the Merkle root lives: a contract, or a text record under picoquorum.eth;
  - [ ] what checks it: the app's badge, as for the registry today.

  An ATECC608 has no factory certificate. So membership is the project's own statement, not proof
  of genuine silicon. A contract would be PicoQuorum's first, and the app reading the root is a new
  network call. Review both before building.
- [ ] Extend the registry and `tools/fw attest` to ATECC608 keys. That list is where the leaves come
      from.
- [ ] key-c bring-up. The P2 boards are due about 2026-10-07
      ([key-c](hardware/key-pcb/key-c-usbc/README.md)).
  - [ ] Read a 608C's revision and factory table. C1 accepts only 608A and 608B
        (`chipcfg.py` `REVISIONS`) and the Adafruit factory table (`provision.py` `c1`), so add the
        608C before any ceremony.
  - [ ] Practise C1–C9 on a spare.
- [ ] Write a batch runbook for chips 3 to N:
  - [ ] the dual image, swap the chip, `allow on`, C1–C10, `allow off`;
  - [ ] enroll;
  - [ ] the local inventory (gitignored);
  - [ ] a fingerprint label and an instruction card.
- [ ] Put the Source Location on the silkscreen at key-c P3 ([hardware/README.md](hardware/README.md),
      required by CERN-OHL).

## 7. Stale lines in the docs

- [ ] STATUS.md "Next" item 1, going public, is done.
- [ ] GOVERNANCE.md says `release.yml` adds build provenance. It doesn't yet (section 3).
- [ ] CHIPMAP.md says OTP writes aren't modelled or built. The emulator models them now.
- [ ] LOCKING.md's early "no LimitedUse" advice. quorum v1 uses LimitedUse.
