# Firmware releases

A release is **year.month.n**: the n-th of that month. The number is in `firmware/manifest.json`
(`"version"`). `tools/fw build` writes it into the board's `build.py` next to the commit, the Device
screen shows `2026.10.1 · <commit>`, and the boot line in `log.txt` carries both. Each release has a
git tag, `fw-<version>`.

**The release fingerprint** names what a board runs: the SHA-256 of the image's source files
(`tools/releases/fingerprint.mjs`; [`releases/`](releases/README.md) has the definition). `tools/fw build`
writes it into `build.py` as `RELEASE`, and the Device screen shows its blockie and first 8 hex
digits (`4c86·c754`). The emulator computes it over the files it runs, so the same release shows
the same picture in the browser. The app's Releases page lists each release's fingerprint.
The README's badges and build table show each image's blockie with its first and last 8 digits;
`node tools/releases/badge.mjs` writes them (`docs/releases/badges/`), and CI fails when they don't
name the source. Run it, as you rebuild `docs/emu`, whenever the firmware or its version changes.

**To make one** (from a clean `main`):
1. Set `"version"` in `firmware/manifest.json`, and write its `## <version> (<date>)` entry below.
2. `tools/release manifest` writes `docs/releases/<version>.json` (each image's fingerprint, the
   hash of every source file, the hash of each web build's `BUILD.json`) and its line in
   `docs/releases/index.json`. Rebuild the web pages first if anything in them changed. Commit all of it.
3. `tools/release check`: the tree is clean, the tag doesn't exist yet, the entry is here, the
   manifest matches the source, and the fast tests pass.
4. `tools/release tag --push` signs `fw-<version>` with your SSH key, checks the signature against
   `.github/allowed_signers` (deleting the tag if it doesn't check), and pushes it.
5. `.github/workflows/release.yml` takes it from there:
   - It refuses a lightweight, unsigned or unknown-key tag.
   - It checks the version, this entry and the manifest again, and runs all of CI on the tagged commit.
   - It builds the three images and publishes a GitHub Release with:
     - a zip of each image;
     - `release.json` (each built file's hash, the commit, the fingerprints);
     - the manifest;
     - `SHA256SUMS`.
6. `tools/fw push console --all` puts it on every board on USB. `tools/fw verify` shows each board's
   release fingerprint, which must match the manifest's.

CI (`.github/workflows/ci.yml`) runs every suite on each pull request and push to `main`, builds the
images, and fails if `docs/` differs from a rebuild of the web pages. Pages serves only what the
source makes.

`.github/workflows/site-check.yml` checks that from outside. After every Pages deploy and every six
hours, it fetches what the site serves and compares each byte with `docs/` at the deployed commit,
and opens an issue on any difference. By hand: `tools/release check-site`. The app's Releases page
says which release the page you're on is.

### Signing

Tags are signed with an SSH key; git and GitHub both understand it. Keep the key in hardware if you
can:
- **Mac Secure Enclave:** the [Secretive](https://github.com/maxgoedjen/secretive) app makes a
  P-256 key (`ecdsa-sha2-nistp256`) that never leaves the chip. It is the same curve as the
  console's own keys.
- **YubiKey:** `ssh-keygen -t ed25519-sk -O resident` makes a key that needs a touch for each signature.

Once:
```sh
git config --global gpg.format ssh
git config --global user.signingkey "<the public key, or the path to its .pub file>"
git config --global tag.gpgSign true
```
- Add the public key to GitHub as a **signing key** (Settings → SSH and GPG keys → New SSH key → Key type:
  Signing Key). GitHub then shows the tag as Verified.
- Add the key to `.github/allowed_signers` as `<your git email> namespaces="git" <public key>`, in a
  reviewed commit. That file decides who can release.

**On GitHub** (Settings → Rules → Rulesets), two rulesets close the gaps CI can't:
- **`main`:** require pull requests and the CI checks `firmware`, `fwbuild` and `web`; block force pushes.
- **Tags `fw-*`:** restrict creation, update and deletion to the maintainers. Otherwise anyone with
  push access could take a release name, even though CI would refuse to publish it.

### Approval by the project Safe

The tag says who cut a release. The project Safe says the project stands behind it (`docs/GOVERNANCE.md`).

1. **Propose:** `tools/release approval` prints the Safe transaction:
   - a delegatecall to Safe's SignMessageLib 1.4.1, `signMessage(D)`;
   - D is the EIP-712 `PicoQuorumRelease(version, firmware, manifest)`;
   - a short origin note names the release.

   Propose it from the app's **Releases** page (**Propose approval**), or with any Safe tool.
2. **Approve:** each owner's console shows **Approve release …** with the firmware fingerprint's
   blockie, and whether it is the release running on that console. It refuses any message that
   isn't a release whose note gives exactly the calldata's digest.
3. **Check:** once executed, `isValidSignature(D, "0x")` on the Safe returns `0x1626ba7e` for good,
   even after owners change. The Releases page shows **Approved by the project Safe**.

`docs/releases/<version>.json` never changes after its tag: its SHA-256 is part of D. Later facts
(the commit, the approval) go in `index.json`.

`tools/vectors/release.mjs` checks the hashing against a real Safe on Ethereum.
`tools/quorum release-e2e` runs the whole approval on a fork:
- the console signs it, and it executes;
- `isValidSignature` holds, and still holds after the console's owner is removed.

## 2026.10.9 (2026-10-03)

**Fix: Build 1 sometimes stopped on boot** with "MemoryError … allocating 1280 bytes" and 221 KB
free. The boot art kept drawing on its timer while the console's modules loaded, and its small
objects ended up between theirs: the largest free block left was 17-26 KB, and sometimes not even
1.3 KB at the moment the code needed it. The art now pauses until the modules have loaded: they
load in 0.9 s instead of 3.5 s, and a 95 KB block is left.

## 2026.10.8 (2026-10-02)

**Fix: OSError 12 on HTTPS calls**, including a confirmation that was signed but never sent.
Measured on the board, with the heap full except for one hole:
- **The TLS session alone** fails in 28 KB, takes ~8 s in 32 KB (the old reserve, so calls ran on
  the edge) and 0.9 s in 36 KB. The reserve is now **40 KB**.
- **The response body** was read in 1 KB pieces and joined while the connection was still open.
  A 6.7 KB queue then needed a **48 KB** hole. Now it is read into a 16 KB buffer kept from boot,
  and copied out only after the connection closes. The same queue fits in a 32 KB hole, in 0.75 s.
  A queue over 16 KB is asked for again as 3 transactions, as before.

## 2026.10.7 (2026-10-02)

**Build 1's knob keeps up:** a detent reaches the screen in ~140 ms, down from ~2.1 s.
- **Redraws:** the screen is drawn in 8 strips, and each strip re-ran the whole screen's code.
  The blockies rebuilt their pattern every strip (~1.3 s a frame), and text widths were measured
  again every strip (~0.6 s). Both are kept now, so a whole frame is ~350 ms.
- **Only what moved:** a turn that only moves the focus (the grid, the queue list, Device, the
  review's SIGN/REJECT/BACK bar, Send again) redraws just the strips it touches, usually 1-3 of 8.
- **The encoder's interrupts are hard ones,** so no steps are lost while the board is busy.
- **Polls stay out of the way:** none starts until the knob has been still for 3 s. One stops
  between its calls if the knob turns, and is asked again once it is quiet. Turns that piled up
  meanwhile move the focus at most 3 places. Home shows "checking…" while a poll runs.

**The Sign button only signs** (boards with the knob). On a review it signs as before; anywhere
else it opens nothing and says "Sign button: only for signing". The knob does the browsing.

## 2026.10.6 (2026-10-02)

**Build 1's screen turned 180°** for its new case: MADCTL 0x60 (MX|MV) in place of 0xA0 on the
2.8". The 1.8" profile and the Waveshare are unchanged.

## 2026.10.5 (2026-10-02)

**Fix: Build 1 froze at "screen: ok" on boot.**
- **The cause:** with two Wi-Fi networks saved (one from Wi-Fi setup, one from `secrets.py`),
  the boot asked the radio to scan for the one in range at the moment the boot art started
  drawing on its timer. The scan never came back, and the board stopped answering on USB too.
- **Now:** the boot joins the newest saved network with no scan. If that one is out of range, the
  console's retry walks the others, one every 30 s.
- This is the merge of Wi-Fi setup (#18) with the quick boot.

## 2026.10.4 (2026-10-01)

**Home is a grid to browse when nothing waits for this key:** each Safe, Recent (the last
signatures sent, kept in `recent.json`), the chip and the device. When a request arrives, home is
the queue list as before. The chip's blockie also sits small in the header. Walkthrough:
[quorum-ui/v2](quorum-ui/v2/README.md).

## 2026.10.3 (2026-10-01)

**The loaded chip's blockie on the boot screen.** Once the console has read its chip, the owner's
blockie appears under the tagline, with the chip's name and short address. It's red if the chip
isn't the pinned one. The walkthrough: [quorum-ui/v2](quorum-ui/v2/README.md).

## 2026.10.2 (2026-10-01)

**The fix:** Device → Wi-Fi on Build 1.
- **What went wrong:** the knob's press that chose Wi-Fi is also Build 1's maintenance key at power-up. The console restarted while the knob was still down, so the board came up in maintenance (a blank screen).
- **The console now waits** for the knob to be let go before it restarts, and says so on screen.
- **At boot, a pending Wi-Fi request outranks a held key.** The request is taken once, and the `maint` file still wins.

## 2026.10.1 (2026-10-01)

The first numbered release. It brings three lines of work together on the production console:

- **The quick boot:** the boot art draws on a timer while WiFi joins and the console starts.
  - The Trust M's certificate checks are remembered between boots (`tmproof.txt`).
  - It also has the boot mark and taglines.
- **Wi-Fi setup at power-up:** the console's own hotspot with a QR code, or the on-screen
  keyboard (the joystick, or the knob).
  - Networks are kept in `wifi.json`.
  - Hold Y while plugging in, or pick **Device → Wi-Fi**, the way in on Build 1's knob.
- **The Trust M, ready for the mainnet work:**
  - **T9 freezes the 23 spares and Infineon's own three objects.** TM2 showed those three can
    otherwise be rewritten.
  - **T8 checks live** that the factory key is still the certificate's.
  - **The Chip page** shows the spares.
  - `tools/fw ceremony start|finish`, `tools/fw attest` and `tools/quorum verify`, with a live
    challenge.
  - The details: [TRUSTM.md](TRUSTM.md) and [mainnet/](mainnet/README.md).

**Boards:**
- The Waveshare (`025997e6…`), with TM1.
- Build 1 (`aee390c5…`), with ATECC chip 2.
